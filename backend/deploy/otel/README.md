# OpenTelemetry Tracing

## 동작 개요
- `app/core/tracing.py::install_tracing()` 가 `QP_OTEL_ENABLED=true` 일 때 활성화.
- FastAPI · HTTPX · SQLAlchemy 자동 계측.
- OTLP gRPC 로 Collector(`QP_OTEL_ENDPOINT`) 전송 → Jaeger 백엔드로 fan-out.
- `/health`, `/metrics` 는 트레이스 제외(과다 스팬 방지).

## 로컬 실행
```bash
cd deploy
docker compose \
  -f docker-compose.yml \
  -f otel/docker-compose.tracing.yml up -d

# proxy 에 tracing env 주입
docker compose exec -e QP_OTEL_ENABLED=true \
  -e QP_OTEL_ENDPOINT=http://otel-collector:4317 \
  proxy uvicorn app.main:app --host 0.0.0.0 --port 8080

# 트래픽 발생
curl -s http://localhost:8080/health
curl -s -X POST http://localhost:8080/versions/strategies \
  -H 'Authorization: Bearer <JWT>' -d '{"name":"trace-probe"}'

# Jaeger UI
open http://localhost:16686
```

## 자주 사용하는 커스텀 스팬 예시
```python
from app.core.tracing import get_tracer

tracer = get_tracer(__name__)

async def call_screener(uid: str, text: str):
    with tracer.start_as_current_span("ai.screener") as span:
        span.set_attribute("uid", uid)
        span.set_attribute("text.len", len(text))
        ...
```

## 트러블슈팅
| 증상 | 원인/조치 |
|---|---|
| Jaeger UI에 스팬이 없음 | `QP_OTEL_ENABLED=true` 확인, Collector 로그(`docker logs qp-otel-collector`) 확인 |
| gRPC connection refused | `QP_OTEL_ENDPOINT`가 컨테이너 네트워크 이름(`otel-collector:4317`)인지 확인 |
| 트레이스 사라짐 | `batch` processor 대기 시간(5s) 이후 flush — 요청 종료 뒤 잠시 대기 |
