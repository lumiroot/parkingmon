#!/usr/bin/env python3
"""김해공항 주차장 모니터링 - 메인 실행 스크립트.

사용법:
    # 데이터 수집 + 웹 대시보드 동시 실행
    python main.py

    # 웹 대시보드만 실행
    python main.py --web-only

    # 데이터 수집만 한 번 실행
    python main.py --collect-once
"""

import argparse
import logging
import sys
import threading

from apscheduler.schedulers.background import BackgroundScheduler

import config
import db
from app import app
from collector import collect_and_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def start_scheduler():
    """5분 간격 데이터 수집 스케줄러를 시작합니다."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        collect_and_store,
        "interval",
        minutes=config.COLLECT_INTERVAL_MINUTES,
        id="parking_collector",
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "스케줄러 시작: %d분 간격으로 데이터를 수집합니다.",
        config.COLLECT_INTERVAL_MINUTES,
    )

    # 시작 직후 첫 수집 실행
    try:
        collect_and_store()
    except Exception as e:
        logger.error("초기 수집 실패 (스케줄러는 계속 동작합니다): %s", e)

    return scheduler


def main():
    parser = argparse.ArgumentParser(
        description="김해공항 주차장 모니터링"
    )
    parser.add_argument(
        "--web-only",
        action="store_true",
        help="웹 대시보드만 실행 (수집 없음)",
    )
    parser.add_argument(
        "--collect-once",
        action="store_true",
        help="데이터 수집을 한 번만 실행",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.WEB_PORT,
        help=f"웹 서버 포트 (기본: {config.WEB_PORT})",
    )
    args = parser.parse_args()

    # DB 초기화
    db.init_db()
    logger.info("데이터베이스 초기화 완료: %s", config.DB_PATH)

    if args.collect_once:
        try:
            count = collect_and_store()
            logger.info("수집 완료: %d개 주차장", count)
        except Exception as e:
            logger.error("수집 실패: %s", e)
            sys.exit(1)
        return

    scheduler = None
    if not args.web_only:
        if not config.SERVICE_KEY:
            logger.warning(
                "PARKING_API_KEY 환경변수가 설정되지 않았습니다. "
                "웹 스크래핑 모드로 수집을 시도합니다. "
                "안정적인 수집을 위해 공공데이터포털에서 API 키를 발급받으세요: "
                "https://www.data.go.kr/data/15063437/openapi.do"
            )
        scheduler = start_scheduler()

    try:
        logger.info(
            "웹 대시보드 시작: http://localhost:%d", args.port
        )
        app.run(host="0.0.0.0", port=args.port, debug=False)
    except KeyboardInterrupt:
        logger.info("종료 중...")
    finally:
        if scheduler:
            scheduler.shutdown()


if __name__ == "__main__":
    main()
