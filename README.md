# 김해공항 주차장 모니터링

김해공항 주차장의 실시간 주차 가능 대수를 수집하고 웹 대시보드로 시각화하는 시스템입니다.

## 기능

- 5분 간격 자동 데이터 수집 (공공데이터포털 API 또는 웹 스크래핑)
- 주차장별 현재 주차 가능 대수 및 점유율 표시
- 시계열 차트로 주차 가능 대수/점유율 추이 확인 (1시간 ~ 7일)
- 60초 간격 자동 새로고침

## 설치 및 실행

[uv](https://docs.astral.sh/uv/)를 사용합니다.

```bash
# 의존성 설치
uv sync

# 실행 (데이터 수집 + 웹 대시보드)
uv run python main.py

# 웹 대시보드만 실행
uv run python main.py --web-only

# 데이터 1회 수집
uv run python main.py --collect-once

# 포트 지정
uv run python main.py --port 8080
```

실행 후 `http://localhost:5000`에서 대시보드를 확인할 수 있습니다.

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `PARKING_API_KEY` | [공공데이터포털](https://www.data.go.kr/data/15063437/openapi.do) API 서비스키 | (미설정 시 웹 스크래핑) |
| `WEB_PORT` | 웹 서버 포트 | `5000` |

## 데이터 수집 방식

1. **공공데이터포털 API** - `PARKING_API_KEY` 환경변수 설정 시 사용. 안정적인 수집을 위해 권장됩니다.
2. **웹 스크래핑** - API 키 미설정 시 김해공항 홈페이지에서 직접 수집. 사이트 구조 변경에 영향을 받을 수 있습니다.
