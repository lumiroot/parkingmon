import os

# 공공데이터포털 API 서비스키
# https://www.data.go.kr/data/15063437/openapi.do 에서 발급
SERVICE_KEY = os.environ.get("PARKING_API_KEY", "")

# 김해공항 코드
AIRPORT_CODE = "PUS"

# 수집 주기 (분)
COLLECT_INTERVAL_MINUTES = 5

# 데이터베이스 파일 경로
DB_PATH = os.path.join(os.path.dirname(__file__), "parking_data.db")

# 웹 서버 포트
WEB_PORT = int(os.environ.get("WEB_PORT", "5000"))

# API 엔드포인트
PARKING_API_URL = (
    "http://openapi.airport.co.kr/service/rest/"
    "AirportParkingCongestion/airportParkingCongestionRT"
)
