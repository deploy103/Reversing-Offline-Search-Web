# DEVELOPMENT_LOG.md

AI가 중단되더라도 다음 작업자가 이어서 개발할 수 있도록 계속 갱신한다.

## Initial state
### 완료
- 프로젝트 요구사항 정의
- 300개 콘텐츠 계획 정의

### 다음 작업
- 저장소 생성
- 정적 사이트 skeleton
- 검색엔진 prototype
- 샘플 10개 글
- file:// smoke test

## Scope update — 2026-09-08 KST
### 변경
- 목표를 300개에서 1,000개 검색 엔트리로 확장
- 장문 500 / 레퍼런스 250 / 문제해결 250
- 완성본 전체 40GB hard limit
- 30~35GB soft target
- 기존 300개 계획은 seed로 유지하고 1,000개까지 확장

## 2026-09-08 22:40 KST
### 완료
- Private GitHub 저장소 `deploy103/Reversing-Offline-Search-Web` 생성 및 초기 push
- Phase 1 정적 사이트 골격 완성: `content/articles/<category>/<slug>.md` 구조, `scripts/build.py`(의존성 없는 마크다운 렌더러), `scripts/validate.py`, `assets/css/style.css`(light/dark), `assets/js/search.js`(2-gram/3-gram 한국어 검색), `assets/js/theme.js`
- 샘플 10개 글 작성 및 검증: REV-0001, REV-0002, REV-0009, REV-0010, REV-0024, REV-0026, REV-0071(CALL, 플래그십), REV-0100, REV-0151, REV-0208
- `dist/index.html`이 file:// 환경에서 fetch/XHR/module/원격 리소스 없이 동작하도록 구성
- `.gitignore`로 무관한 `reversing_analysis/` 프로젝트와 `dist/`, `offline-kit/` 대용량 바이너리 제외

### 검증
- `python3 scripts/build.py` 연속 2회 실행 결과 sha256 동일 (idempotent 확인)
- `python3 scripts/validate.py` → PASS (오류 0, 경고 0)
- `dist/` 전체 grep으로 `fetch(`, `XMLHttpRequest`, `type="module"`, 원격 `http(s)://` src/href 없음 확인
- Node.js vm 샌드박스로 실제 빌드된 `search-index.js` + `search.js`를 로드해 `tests/search-smoke-queries.txt` 39개 쿼리 전체 실행 (직접 실행, 추론 아님)
  - `call` → REV-0071, `positive sp value` → REV-0151, `16777619` → REV-0208, `2의 보수` → REV-0024, `main 어디` → REV-0009, `_libc_start_main` → REV-0009, `0xffffff` → REV-0026, `stripped elf` → REV-0010 등 정답 글이 1위로 정확히 매칭
  - 아직 전용 글이 없는 mnemonic/키워드(`ret`, `mov`, `xor`, `upx`, `ptrace`, `jz` 등)는 예상대로 fuzzy fallback 또는 무결과 — 10/1000 글만 존재하는 Phase 1 단계이므로 정상

### 문제
- 마크다운 컨버터가 중첩 리스트를 형제 `<li>`로 평탄화함 (현재 글에는 지장 없음, 추후 필요 시 개선)
- dynamic-analysis/packing/tools/automation 카테고리는 아직 글이 0개라 빈 상태로 표시됨 (Phase 3/4에서 채워짐)

### 다음 작업
- Phase 3: Assembly Dictionary 나머지 49개(REV-0039~0070, 0072~0088) 작성
- Phase 2: 웹 리서치 본격 수행, `research/sources.json` 채우기
- 10개 작성마다 build → validate → smoke test → 로그 → commit 반복

### Commit
- (다음 커밋에서 기록)
