# 2026-02-01: Demo Packaging & Code Review

## 작업 요약

MVP 평가자를 위한 self-contained 데모 패키지 생성 및 전체 코드 리뷰 수행.

---

## 1. Demo Packaging

### 생성된 파일

| 파일 | 설명 |
|------|------|
| `scripts/demo.sh` | 원클릭 데모 시작 스크립트 |
| `scripts/package-demo.sh` | 데모 아카이브 생성 스크립트 |
| `Makefile` | 개발자용 명령어 모음 |
| `demo-package/docker-compose.yml` | API 전용 Docker 설정 |
| `demo-package/.env.example` | API 키 템플릿 |
| `demo-package/README.md` | 빠른 시작 가이드 |
| `demo-package/api/Dockerfile` | FastAPI 컨테이너 |

### 패키지 구성

```
my-awesome-ra-demo.tar.gz (96MB)
├── docker-compose.yml
├── .env.example
├── README.md
├── api/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   └── src/
└── data/
    ├── chroma/      # ChromaDB 인덱스 (84MB)
    └── pdfs/        # 29개 PDF (37MB)
```

### 사용법

```bash
./scripts/package-demo.sh        # 패키지 생성
tar xzf my-awesome-ra-demo.tar.gz
cd demo-package
cp .env.example .env             # API 키 설정
docker compose up -d             # 시작
# http://localhost:8000/docs     # Swagger UI
```

---

## 2. API 개선

### ChromaDB HNSW 설정 추가

```python
# 환경변수로 HNSW 파라미터 설정 가능
HNSW_SPACE=cosine
HNSW_M=16
HNSW_CONSTRUCTION_EF=100
HNSW_SEARCH_EF=50
HNSW_BATCH_SIZE=100
HNSW_SYNC_THRESHOLD=1000
```

### 검증 로직 추가

잘못된 환경변수 값으로 인한 크래시 방지:

```python
try:
    metadata[meta_key] = int(value)
except ValueError:
    logger.warning(f"Invalid integer for {env_key}: {value}, skipping")
```

---

## 3. Code Review 결과

### MVP 기준 무시 가능

| 이슈 | 이유 |
|------|------|
| 데모 비밀번호 하드코딩 | 의도적 공개 (MVP 데모용) |
| Rate Limiting 없음 | 평가자만 사용 |
| In-Memory 상태 저장 | 데모 세션 짧음 |

### 수정 완료

| 이슈 | 조치 |
|------|------|
| 코드 중복 (demo-package vs apps/api) | package-demo.sh 재실행으로 동기화 |
| HNSW 환경변수 검증 없음 | try/except 추가 |
| 미사용 imports | code-simplifier로 정리 |

### 긍정적 발견

- Pydantic 입력 검증 잘 구현됨
- Path traversal 보호 있음
- API 키 환경변수 관리
- CORS 설정 적절
- 파일 크기 모두 800줄 미만

---

## 4. Playwright E2E 검증

### 테스트 시나리오

1. http://localhost/login 접속
2. demo@example.com / Demo@2024!Secure 로그인
3. Demo Project 열기
4. 에디터에 "attention mechanism transformer" 텍스트 입력
5. Evidence Panel 자동 검색 확인
6. Vaswani2017Attention 결과 10개 반환 확인

### 결과

| 항목 | 상태 |
|------|------|
| 로그인 | PASS |
| Reference Library (28/29 문서) | PASS |
| Evidence Panel 자동 검색 | PASS |
| 검색 결과 표시 | PASS |
| API 연동 | PASS |

### 스크린샷

`.playwright-mcp/evidence-panel-working.png`

---

## 5. 커밋 목록

```
efcb094 refactor(api): cleanup unused imports and simplify code
3299637 fix(api): add validation for HNSW environment variables
6741394 chore: add frontend design skill and update gitignore
4057e80 feat(frontend): enhance Evidence Panel with auto-search and improved UX
d937a06 docs(scripts): document ChromaDB memory issue and solutions
55d0d0c feat(demo): add self-contained demo package structure
0a6fb57 feat(scripts): add demo startup and packaging tools
b93a2df refactor(api): improve ChromaDB HNSW configuration and chunking
```

---

## 6. 남은 작업

- [ ] Overleaf 서브모듈 커밋 (별도 관리)
- [ ] scripts/regenerate_seed.py 정리
- [ ] E2E 테스트 자동화 (CI)

---

## 참고

### Seed 데이터

- 29개 논문, 3,192개 임베딩
- 주요 논문: Vaswani2017Attention, Hu2021LoRA, Yang2025Qwen3

### 데모 계정

```
Email: demo@example.com
Password: Demo@2024!Secure
```
