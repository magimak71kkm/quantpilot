# Alembic 마이그레이션

## 개요
- 스키마 버전 관리를 `scripts/init_db.sql`(1회성 부트스트랩)에서 Alembic 리비전으로 전환.
- `alembic/env.py`가 `app.models.db.Base.metadata`를 참조 → 모델 변경 시 `alembic revision --autogenerate`로 리비전 생성.
- `QP_DATABASE_URL` 환경변수가 있으면 `alembic.ini`의 값을 덮어씀.

## 리비전 이력
| ID | 설명 |
|---|---|
| 0001 | 초기 스키마 (users · google_accounts · audit_logs · strategies · commits · commit_files · branches · tags · deployments) |
| 0002 | audit_logs 파티션 전환 + `archive.audit_prune_90d()` + `public.audit_next_partition()` (Postgres 전용) |

## 명령
```bash
# 1) 현재 상태 확인
alembic current

# 2) head까지 업그레이드
alembic upgrade head

# 3) 특정 리비전으로 롤백
alembic downgrade 0001

# 4) 모델 변경 후 새 리비전 생성 (자동 감지)
alembic revision --autogenerate -m "add xxx column"
```

## 컨테이너에서
```bash
docker compose exec proxy alembic upgrade head
```

## dev(SQLite) vs prod(PostgreSQL)
- 0002 리비전의 파티션 DDL은 PostgreSQL에서만 실행되도록 dialect 분기(op.get_bind().dialect.name)로 보호됨.
- SQLite 환경에서는 upgrade가 no-op으로 동작해 테스트에 영향이 없음.
