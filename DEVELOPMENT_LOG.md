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
- e6c282d

## 2026-09-08 23:50 KST — 진행상황 로그 주기 변경 안내
사용자 지시로 워크플로 변경:
- `DEVELOPMENT_LOG.md`는 이제부터 10개가 아니라 50개 작성마다 갱신 (rate limit로 중단될 경우를 대비한 복구용 기록이 목적)
- 로컬 git 커밋은 배치 단위로 크게 묶어도 됨
- `git push`는 1,000개 글 + 어셈블리 사전 + 툴킷 + 이미지 + 최종 검증까지 전부 끝난 뒤 마지막에 한 번만 수행 (그 전까지는 로컬 커밋만)

### 완료 (누적 59개 글)
- Phase 3 Assembly Dictionary 49개 전부 작성 완료 (REV-0039~0088, CALL 제외 — CALL은 Phase 1에서 이미 작성): MOV/MOVZX/MOVSX/LEA/XCHG/PUSH/POP/PUSHF·POPF/ADD/SUB/INC·DEC/MUL/IMUL/DIV/IDIV/NEG/AND/OR/XOR/NOT/TEST/CMP/SHL·SAL/SHR/SAR/ROL/ROR/JMP/JE·JZ/JNE·JNZ/JG·JGE·JL·JLE/JA·JAE·JB·JBE/RET/LEAVE/NOP/CMOVcc/SETcc/SYSCALL/SYSENTER·SYSEXIT/INT·INT0x80/REP/MOVS/STOS/LODS/SCAS/CMPS/CPUID/RDTSC/플래그 레지스터 개관
- `scripts/build.py`에 전역 로컬 `.md`→`.html` 링크 재작성 로직 추가 (`rewrite_local_md_links`) — 병렬 작성 시 글 본문 어디서든 다른 글을 마크다운 링크로 자유롭게 상호 참조할 수 있게 됨 (이전에는 `관련 글` 섹션의 특정 불릿 포맷만 처리했음)
- frontmatter 누락(aliases/symptom_keywords/source_ids) 3건, stale 관련 글 참조 1건, 필수 섹션 누락 경고 12건(가장 먼저 할 것/단계별 절차/명령어·단축키/막혔을 때 다음 체크) 전부 수정

### 검증
- `python3 scripts/build.py` → 59개 전부 빌드 성공
- `python3 scripts/validate.py` → PASS (오류 0, 경고 0)
- Node vm 스모크 테스트로 call/ret/lea/mov/movzx/movsx/cmp/test/jnz/jz/jg/ja/sar/shr/xor/and 등 어셈블리 니모닉 16개 전수 재확인 — 전부 자기 전용 글이 1위로 정확히 매칭

### 문제
- 없음 (경고까지 전부 해소)

### 다음 작업
- Phase 4: seed 300 나머지 카테고리(바이너리 기초, 처음 시작, Windows/PE, Linux/ELF, 정적분석, 동적분석, 알고리즘, 패킹, .NET/Android, 자동화, 툴 사용법) 병렬 작성 계속
- 50개(또는 자연스러운 배치 완료 시점)마다 이 로그 갱신

### Commit
- 3b6a24d

## 2026-09-09 01:30 KST — Phase 4 Wave 1 (seed 300 중 109개 추가, 누적 168개)

### 완료
- 처음 시작 카테고리 나머지 14개 (REV-0003~0008, 0011~0018) — 이제 REV-0001~0018 전부 완료
- 바이너리 기초 카테고리 나머지 18개 (REV-0019~0023, 0025, 0027~0038) — REV-0019~0038 전부 완료
- Linux/ELF 카테고리 나머지 24개 (REV-0089~0099, 0101~0113) — REV-0089~0113 전부 완료
- 정적분석 카테고리 나머지 26개 (REV-0142~0150, 0152~0168) — REV-0142~0168 전부 완료 (IDA 15개 + Ghidra/공통기법 13개)
- 알고리즘 패턴 카테고리 나머지 27개 (REV-0196~0207, 0209~0223) — REV-0196~0223 전부 완료
- 9개 병렬 에이전트(+1 no-op)로 작성, 이후 직접 build/validate 실행하며 발견된 문제 수정:
  - `관련 글` stale title 참조 59건 → 자동 재작성 스크립트로 일괄 수정 (title이 실제 frontmatter와 정확히 일치하도록)
  - `scripts/validate.py`의 "placeholder" 문자열 오탐 제거 (정상적인 한국어 기술 문서에서 영어 차용어로 쓰이는 경우까지 잡아내던 문제) — marker 목록에서 제거하고 나머지(tbd/todo/lorem ipsum 등)는 유지
  - 누락된 `미니 예제`/`명령어/단축키` 섹션 5건 직접 보완

### 검증
- `python3 scripts/build.py` → 168개 전부 빌드 성공
- `python3 scripts/validate.py` → PASS (오류 0, 경고 0)
- Node vm 스모크 테스트 재실행 — main 어디/ida f5/ida strings/ida xref/signed unsigned/2의 보수/0xffffff/16777619/pie breakpoint/aslr/elf 처음/stripped elf 등 정확히 매칭 확인. upx/ptrace/IsDebuggerPresent/x64dbg string은 아직 해당 카테고리(패킹, x64dbg 전용 글) 미작성이라 예상대로 fuzzy fallback — Wave 2에서 해소 예정

### 문제
- 병렬 작성 에이전트가 `관련 글` 불릿에 부가 설명을 덧붙이는 경향이 있어(예: "제목 (./slug.md)") validate.py가 stale로 오탐 — 매 웨이브 종료 후 일괄 재작성 스크립트로 정리하는 것으로 대응 중. 다음 웨이브 프롬프트에서 "정확히 실제 title과 동일하게, 괄호 부가설명 금지"를 더 명시할 것.

### 다음 작업
- Phase 4 Wave 2: Windows/PE(28), 동적분석(27), 패킹/안티분석(18), .NET/Android(16), 자동화/Solver(16), 툴 사용법(27) — seed 300 중 남은 132개
- seed 300 완료 후 REQUIREMENTS.md 도메인 분포표 기준으로 1,000개까지 확장

### Commit
- e100cde

## 2026-09-09 03:15 KST — Phase 4 Wave 2 완료, Seed 300 전체 달성 (누적 300개)

### 완료
- Windows/PE 카테고리 28개 전부 (REV-0114~0141): PE 구조, DOS/COFF/Optional Header, RVA/VA, Import/Export Table, MS x64 및 x86 호출 규약, Shadow Space, PE-bear/DIE/x64dbg 첫 분석, IsDebuggerPresent 계열 안티디버깅 4종, TLS/SEH, .NET vs Native 구분 등
- 동적분석 카테고리 27개 전부 (REV-0169~0195): 브레이크포인트/스텝 개념 9개, x64dbg 8개, GDB/Pwndbg 10개 (PIE 브레이크포인트 포함)
- 패킹/안티분석 카테고리 18개 전부 (REV-0224~0241): UPX 식별/언패킹, entropy, self-modifying/CFF/opaque predicate, ptrace/IsDebuggerPresent/PEB/RDTSC/CPUID/예외 기반 안티디버깅
- .NET/Android 카테고리 16개 전부 (REV-0242~0257): dnSpyEx/ILSpy/CIL, APK/JADX/apktool/smali/Frida/JNI
- 자동화/Solver 카테고리 16개 전부 (REV-0258~0273): Python 변환 치트시트 8개(실제 실행 검증됨), pwntools/Z3/angr/Capstone/Unicorn 8개
- 툴 사용법 카테고리 27개 전부 (REV-0274~0300): IDA/Ghidra/x64dbg/GDB/Pwndbg 설치+단축키+10분 워크플로, DIE/PE-bear/ImHex/HxD/radare2/Cutter, 중복 없는 짧은 조합 치트시트(binutils, ltrace/strace), UPX/dnSpyEx/JADX 설치, Python 오프라인 패키지 준비
- **CONTENT_PLAN.md의 seed 300개 전부 완료** — 15개 병렬 에이전트(+이전 웨이브 9개)로 작성
- `관련 글` stale title 76건(59+15+2건 두 웨이브 합산) 재작성 스크립트로 정리
- 누락 섹션 경고 14건 직접 보완 (일부는 의도적으로 짧게 유지한 조합형 치트시트라 헤딩 문구만 자연스럽게 삽입해 해결, 내용 패딩 없음)

### 검증
- `python3 scripts/build.py` → 300개 전부 빌드 성공
- `python3 scripts/validate.py` → PASS (오류 0, 경고 0)
- Node vm 스모크 테스트 39개 쿼리 전체 재실행 — MASTER_PROMPT/REQUIREMENTS가 명시한 모든 필수 쿼리 정확히 매칭 확인: `x64dbg string`→REV-0179, `upx`→REV-0225, `ptrace`→REV-0234, `IsDebuggerPresent`→REV-0235, `pie breakpoint`→REV-0103, `aslr`→REV-0104, 그 외 call/ret/lea/mov 등 어셈블리 전부, `_libc_start_main`/`positive sp value`/`16777619`/`0xffffff`/`2의 보수` 등 전부 정확

### 문제
- 병렬 웨이브가 커질수록(15개) `관련 글` stale title 발생 빈도도 늘어남 — 매 웨이브 후 일괄 재작성 스크립트가 안정적으로 작동하고 있으나, 다음 확장 단계에서는 build.py 자체에 이 ���규화 로직을 내장하는 것을 고려할 것

### 다음 작업
- CONTENT_PLAN.md를 REQUIREMENTS.md 도메인 분포표 기준 1,000개로 확장 (나머지 700개 계획 수립)
- 같은 웨이브 방식으로 700개 작성 계속
- 완료 후 Phase 5(툴 오프라인 킷) → Phase 6(이미지) → Phase 7(최종 검증)

### Commit
- 75701a7

## 2026-09-09 05:00 KST — Expansion 700 Wave 1: assembly 카테고리 확장 완료 (누적 410개)

### 완료
- CONTENT_PLAN.md를 REQUIREMENTS.md 도메인 분포표 기준 1,000개 전체 계획으로 확장(REV-0301~1000, 700개 신규) — 카테고리별 배분: assembly+110, windows-pe+130, linux-elf+95, static-analysis+85, dynamic-analysis+70, algorithms+55, binary-basics+45, triage+40, packing+35, dotnet-android+19, automation+14, tools+2. 중복 타이틀 0건 검증.
- assembly 카테고리 확장 110개 전부 작성(REV-0386~0495): SIMD 베이직(MOVAPS/PXOR 등), BT 계열, LOOP 계열, XLAT/ENTER, x87 FPU 스택, RIP-relative/SIB 주소지정, switch 점프테이블/스택 카나리/루프 언롤링/vtable/RTTI 컴파일러 관용구 심화, 레지스터 스필/인라인 함수 등 트러블슈팅 패턴까지 — 11개 병렬 에이전트
- **성능 최적화**: `scripts/validate.py`의 file:// 안전성 검사가 캐시 없이 매 링크마다 `resolve()+exists()`를 호출해 410개 글 기준 4분 15초 소요(WSL DrvFs 파일시스템 지연) → `(부모경로, URL)` 메모이제이션 캐시 추가로 27초로 단축 (9배 개선, 1,000개 확장 대비 필수)
- 관련 글 stale title 2건 즉시 수정, 누락 섹션 경고 10건(배치 6, `단계별 절차` 누락) 보완

### 검증
- `python3 scripts/build.py` → 410개 전부 빌드 성공 (14초)
- `python3 scripts/validate.py` → PASS (오류 0, 경고 0, 27초)
- Node vm 스모크 테스트 재확인 — 기존 매칭 전부 유지

### 문제
- 없음 (성능 이슈는 해결됨)

### 다음 작업
- Expansion 700 Wave 2: windows-pe 130개 (REV-0496~0625로 추정, CONTENT_PLAN.md 확인 후 진행)
- 이후 linux-elf(95) → static-analysis(85) → dynamic-analysis(70) → triage/binary-basics/algorithms(140) → packing/dotnet-android/automation/tools(70) 순으로 웨이브 계속

### Commit
- 47c5b4c

## 2026-09-09 06:30 KST — Expansion 700 Wave 2: windows-pe 카테고리 확장 완료 (누적 540개)

### 완료
- windows-pe 카테고리 확장 130개 전부 작성(REV-0496~0625): WinAPI 그룹별 레퍼런스(파일/레지스트리/프로세스/스레드/메모리/네트워크/CRT), PE 상수/플래그 치트시트, 하드웨어/소프트웨어 브레이크포인트·타이밍·SEH/VEH·self-debugging·부모프로세스 등 안티디버깅 심화, PE 심화 구조(.pdata/.reloc/.rsrc/버전정보/매니페스트/Delay-Load/Bound/Ordinal Import/Rich Header/Authenticode), 프로세스 할로잉/리플렉티브 DLL/API 해싱 개념, 실전 트러블슈팅(DLL 누락, x64dbg 로드 실패, anti-attach, 서명 검증 차단 등) — 13개 병렬 에이전트
- 3건 stale title, 1건 마크다운 오탐 링크(`Data Directory[1](Import Table)`가 링크로 오인식됨 — 괄호+대괄호 인접 패턴), 5개 파일의 `한 줄 요약`/`미니 예제` 누락 섹션 수정

### 검증
- `python3 scripts/build.py` → 540개 전부 빌드 성공
- `python3 scripts/validate.py` → PASS (오류 0, 경고 0)
- Node vm 스모크 테스트 재확인 — 기존 매칭 전부 유지

### 문제
- `텍스트[숫자](단어)` 형태의 산문이 마크다운 링크로 오인식되는 패턴 발견(1건) — 향후 콘텐츠 작성 시 대괄호+괄호 인접 표기 주의 필요, validate.py에 이 패턴 감지 체크 추가를 고려할 것

### 다음 작업
- Expansion 700 Wave 3: linux-elf 95개
- 이후 static-analysis(85) → dynamic-analysis(70) → triage/binary-basics/algorithms(140) → packing/dotnet-android/automation/tools(70)

### Commit
- (다음 로컬 커밋에서 기록, push는 전체 완료 후)
