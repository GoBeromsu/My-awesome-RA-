# Seed 임베딩 메모리 문제 이슈 정리

## 발생일: 2026-01-31 (업데이트: 2026-02-01)

---

## 1. 근본 원인: ChromaDB 메모리 누수
- HNSW C++ 메모리는 Python GC로 해제되지 않아 프로세스 단위로만 완전 해제
- `close()` 미지원 → 프로세스가 살아 있는 동안 메모리 누적

---

## 2. 우리가 한 주요 조치
- **PDF별 subprocess 처리**: `scripts/run_seed_stable.sh` + `_process_one.py`로 문서 단위 프로세스 격리
- **배치 스트리밍 업서트**: 임베딩을 배치로 받아 즉시 upsert, 리스트에 쌓지 않음
- **업서트 백오프**: SQLite/FS 락(`readonly/locked/busy`) 발생 시 지수 백오프로 재시도
- **PDF 복사 시점 변경**: 인덱싱 성공 후에만 `fixtures/seed/pdfs`에 복사 → 중단 시 SKIP 오판 방지
- **청크 병합**: 문장 경계로 잘려 너무 짧은 청크를 인접 청크와 병합해 청크 수/호출 수 감소
- **실행 옵션 확장**: `run_seed_stable.sh`에 `--reverse`, `--chunk-size`, `--overlap`, `--batch-size`, `--log-every`

---

## 3. 현재 기본 설정 (2026-02-01)
- `CHUNK_SIZE=1800`, `CHUNK_OVERLAP=200`
- `EMBED_BATCH_SIZE=3`
- 병합 로직: target 60~130% 범위에서 인접 짧은 청크를 합침
- 옵션으로 덮어쓰기 가능 (`run_seed_stable.sh` 및 env)

---

## 4. 최근 상태 / 남은 리스크
- Seed 디렉토리 초기화 후 재빌드 준비 완료 (`fixtures/seed` 비워둠)
- 긴 문서 처리 시 여전히 네트워크/시간 비용은 큼 → 배치/청크를 상황에 맞게 조절 필요
- Chroma 메모리 누수는 구조적 제약이므로 **문서 단위 subprocess** 전략 유지 필요

---

## 5. 사용 가이드 (예시 커맨드)
```bash
rm -rf fixtures/seed && mkdir -p fixtures/seed/pdfs
./scripts/run_seed_stable.sh --force --log-every 1 \
  --batch-size 3 --chunk-size 1800 --overlap 200
# 역순 처리 원하면 --reverse 추가
```

조정 팁:
- 더 빠르게: `--batch-size 4~5` 또는 `--chunk-size 2000 --overlap 250`
- 더 메모리 절약: `--batch-size 2`, 필요하면 청크 조금 더 줄이기

---

## 6. 실패 복구 체크리스트
- 중단 후 재시작: 같은 커맨드 재실행하면 완료된 문서는 SKIP
- 특정 문서 재처리: 해당 PDF/벡터 삭제 후 다시 실행
- 락/권한 에러 발생 시: seed 디렉토리 권한 확인 (`chmod -R u+rw fixtures/seed`)

---

## 7. 참고 자료
- Chroma HNSW 메모리 누수 이슈: chroma-core/chroma#5843, #5868
- Azure Vector chunking 스타트: ~512 tokens(~2k chars) + 25% overlap
