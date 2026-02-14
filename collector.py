"""김해공항 주차장 데이터 수집기.

두 가지 수집 방식을 지원합니다:
1. 공공데이터포털 API (PARKING_API_KEY 환경변수 설정 시)
2. 김해공항 홈페이지 직접 스크래핑 (API 키 미설정 시 fallback)
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote

import requests

import config
import db

logger = logging.getLogger(__name__)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def collect_via_api():
    """공공데이터포털 API를 통해 주차장 데이터를 수집합니다."""
    if not config.SERVICE_KEY:
        raise ValueError("PARKING_API_KEY 환경변수가 설정되지 않았습니다.")

    params = {
        "serviceKey": config.SERVICE_KEY,
        "schAirportCode": config.AIRPORT_CODE,
    }

    response = requests.get(
        config.PARKING_API_URL,
        params=params,
        headers=REQUEST_HEADERS,
        timeout=15,
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)

    result_code = root.findtext(".//resultCode")
    if result_code != "00":
        result_msg = root.findtext(".//resultMsg", "Unknown error")
        raise RuntimeError(f"API error: {result_code} - {result_msg}")

    records = []
    for item in root.findall(".//item"):
        parking_name = (
            item.findtext("parkingAirportCodeName")
            or item.findtext("aprkName")
            or item.findtext("parkingName")
            or "Unknown"
        )
        total = _parse_int(
            item.findtext("parkingTotalSpace")
            or item.findtext("tpkCnt")
            or item.findtext("parkingTotalCnt")
            or "0"
        )
        occupied = _parse_int(
            item.findtext("parkingOccupiedSpace")
            or item.findtext("pkCnt")
            or item.findtext("parkingOccupiedCnt")
            or "0"
        )
        available = total - occupied if total >= occupied else 0

        records.append({
            "parking_name": parking_name,
            "total": total,
            "occupied": occupied,
            "available": available,
        })

    return records


def collect_via_scraping():
    """김해공항 홈페이지에서 직접 주차장 데이터를 스크래핑합니다."""
    url = (
        "https://www.airport.co.kr/gimhae/extra/parkingStatus/"
        "parkingMain.do"
    )

    response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
    response.raise_for_status()

    # 공항 사이트는 다양한 URL 패턴을 사용하므로 여러 패턴을 시도
    records = _parse_html_parking_data(response.text)

    if not records:
        # 대체 URL 시도
        alt_url = (
            "https://www.airport.co.kr/gimhae/cms/frCon/"
            "index.do?MENU_ID=190"
        )
        response = requests.get(alt_url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        records = _parse_html_parking_data(response.text)

    return records


def _parse_html_parking_data(html):
    """HTML에서 주차장 데이터를 파싱합니다."""
    records = []

    try:
        # 주차장 현황 테이블에서 데이터 추출
        # 일반적인 패턴: 주차장명 | 총 주차면 | 주차중 | 주차가능
        import re

        # 숫자와 주차장명 패턴 탐색
        # 주차장 이름 패턴: P1, P2, P3, 국내선, 국제선 등
        parking_patterns = [
            r"(P\d[^<]*|국내선[^<]*|국제선[^<]*|여객[^<]*|화물[^<]*)",
        ]

        # 테이블 row에서 데이터 추출 시도
        table_pattern = re.compile(
            r"<tr[^>]*>.*?</tr>", re.DOTALL | re.IGNORECASE
        )
        td_pattern = re.compile(
            r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE
        )

        for tr_match in table_pattern.finditer(html):
            tr_html = tr_match.group()
            tds = td_pattern.findall(tr_html)

            if len(tds) >= 3:
                name = re.sub(r"<[^>]+>", "", tds[0]).strip()
                if not name or not any(
                    kw in name
                    for kw in ["P1", "P2", "P3", "주차", "국내", "국제", "여객", "화물"]
                ):
                    continue

                numbers = []
                for td in tds[1:]:
                    cleaned = re.sub(r"<[^>]+>", "", td).strip()
                    cleaned = cleaned.replace(",", "")
                    if cleaned.isdigit():
                        numbers.append(int(cleaned))

                if len(numbers) >= 2:
                    total = numbers[0]
                    available = numbers[-1]
                    occupied = total - available

                    records.append({
                        "parking_name": name,
                        "total": total,
                        "occupied": occupied,
                        "available": available,
                    })

    except Exception as e:
        logger.warning("HTML 파싱 실패: %s", e)

    return records


def _parse_int(value):
    """문자열을 정수로 변환합니다."""
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def collect_and_store():
    """주차장 데이터를 수집하고 DB에 저장합니다."""
    collected_at = datetime.now().isoformat(timespec="seconds")

    try:
        if config.SERVICE_KEY:
            logger.info("API를 통해 데이터 수집 중...")
            records = collect_via_api()
        else:
            logger.info("웹 스크래핑으로 데이터 수집 중...")
            records = collect_via_scraping()

        if not records:
            logger.warning("수집된 데이터가 없습니다.")
            return 0

        for record in records:
            db.insert_record(
                collected_at=collected_at,
                parking_name=record["parking_name"],
                total=record["total"],
                occupied=record["occupied"],
                available=record["available"],
            )

        logger.info(
            "%d개 주차장 데이터 수집 완료 (%s)", len(records), collected_at
        )
        return len(records)

    except Exception as e:
        logger.error("데이터 수집 실패: %s", e)
        raise
