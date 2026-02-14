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

BODY_LOG_LIMIT = 4000


def _log_request(prepared):
    """curl -v 스타일로 요청을 로깅합니다."""
    lines = [f"> {prepared.method} {prepared.url}"]
    for k, v in prepared.headers.items():
        lines.append(f"> {k}: {v}")
    if prepared.body:
        lines.append(f"> body: {prepared.body!r:.{BODY_LOG_LIMIT}}")
    logger.info("HTTP 요청\n%s", "\n".join(lines))


def _log_response(response):
    """curl -v 스타일로 응답을 로깅합니다."""
    lines = [f"< {response.status_code} {response.reason}"]
    for k, v in response.headers.items():
        lines.append(f"< {k}: {v}")
    body = response.text
    if len(body) > BODY_LOG_LIMIT:
        body = body[:BODY_LOG_LIMIT] + f"\n... (truncated, total {len(response.text)} chars)"
    lines.append(f"<\n{body}")
    logger.info("HTTP 응답\n%s", "\n".join(lines))


def collect_via_api():
    """공공데이터포털 API를 통해 주차장 데이터를 수집합니다."""
    if not config.SERVICE_KEY:
        raise ValueError("PARKING_API_KEY 환경변수가 설정되지 않았습니다.")

    params = {
        "serviceKey": config.SERVICE_KEY,
        "schAirportCode": config.AIRPORT_CODE,
    }

    req = requests.Request(
        "GET", config.PARKING_API_URL,
        params=params, headers=REQUEST_HEADERS,
    )
    prepared = req.prepare()
    _log_request(prepared)
    response = requests.Session().send(prepared, timeout=15)
    _log_response(response)
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
    from bs4 import BeautifulSoup

    url = "https://www.airport.co.kr/gimhae/cms/frCon/index.do?MENU_ID=190"

    req = requests.Request("GET", url, headers=REQUEST_HEADERS)
    prepared = req.prepare()
    _log_request(prepared)
    response = requests.Session().send(prepared, timeout=15)
    _log_response(response)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    records = []

    # CSS selector: #contents > article > div.parking-status > ul > li > div > div.label-area
    for li in soup.select("div.parking-status ul li"):
        label_area = li.select_one("div.label-area")
        if not label_area:
            continue

        # 주차장명: span.label (예: "P1 여객주차장")
        name_el = label_area.select_one("span.label")
        # 잔여 대수: p.num-label (예: "10대")
        avail_el = label_area.select_one("p.num-label")
        # 주차율: div.on-progress[data-percent]
        progress_el = li.select_one("div.on-progress[data-percent]")

        if not name_el:
            continue

        parking_name = name_el.get_text(strip=True)

        # 잔여 대수 파싱 ("10대" → 10)
        available = 0
        if avail_el:
            avail_text = avail_el.get_text(strip=True)
            available = _parse_int(avail_text.replace("대", ""))

        # data-percent로 총 주차면/주차중 역산
        total = 0
        occupied = 0
        if progress_el:
            percent = float(progress_el.get("data-percent", "0"))
            if percent > 0 and available >= 0:
                # percent = occupied / total * 100
                # available = total - occupied
                # → total = available / (1 - percent/100)
                if percent >= 100:
                    # 만차: 잔여 0, 총 주차면은 알 수 없으므로 occupied만 기록
                    occupied = 0
                    total = 0
                else:
                    total = round(available / (1 - percent / 100))
                    occupied = total - available

        records.append({
            "parking_name": parking_name,
            "total": total,
            "occupied": occupied,
            "available": available,
        })

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
        logger.error("데이터 수집 실패: %s", e, exc_info=True)
        raise
