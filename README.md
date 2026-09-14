# Reversing-Offline-Search-Web

인터넷이 끊긴 Windows PC에서도 `dist/index.html`을 더블클릭하면 바로 열리는, 오프라인 한국어 리버싱 지식베이스 겸 검색 엔진입니다. CTF/워게임 대회 중 `call`, `positive sp value`, `16777619`, `main 어디` 처럼 아무렇게나 검색해도 실전에서 바로 쓸 수 있는 답을 찾는 것이 목표입니다.

## 현재 상태

**콘텐츠 1,110개 작성 완료** (원 계획 1,000개 + 드림핵 write-up 50개 + C 코드 분석 30개 + 타 아키텍처/언어·실전 팁 30개). 카테고리별 구성:

| 카테고리 | 개수 |
|---|---|
| assembly (x86/x64 어셈블리 사전) | 160 |
| windows-pe | 158 |
| linux-elf | 120 |
| static-analysis | 112 |
| dynamic-analysis | 97 |
| algorithms | 84 |
| binary-basics | 65 |
| triage | 59 |
| packing | 53 |
| writeup (드림핵 워게임 Bronze~Silver 리버싱 문제 50개) | 50 |
| dotnet-android | 35 |
| automation | 30 |
| c-analysis (C 소스 ↔ 어셈블리 대조 30개) | 30 |
| other-targets (PyInstaller/Go/Rust/WASM/ARM 30개) | 25 |
| tools | 32 |
| **합계** | **1,110** |

`writeup` 카테고리는 `dreamhack.io` 워게임 리버싱 카테고리의 실제 Bronze~Silver 티어 문제 50개를 조사해서 만든 글이다. 원문 write-up을 그대로 복제하지 않고, 실제 조사(공식 챌린지 페이지 + 공개 블로그)로 확인한 "문제 해결 패턴"을 한국어로 새로 서술했으며, 참고한 출처는 각 글의 "출처/검증" 섹션에 남겨 두었다. 공개된 상세 풀이를 찾지 못한 일부 문제는 그 사실을 명시하고 일반적인 접근법만 제시한다.

`c-analysis` 카테고리는 for/while/switch/구조체/포인터/재귀 등 흔한 C 코드 패턴이 실제 x86-64 어셈블리에서 어떻게 보이는지 C 소스와 손으로 작성한 정확한 어셈블리를 나란히 대조해서 보여준다. `other-targets` 카테고리는 x86/x64 PE/ELF 위주였던 기존 콘텐츠의 공백을 메운 것으로, PyInstaller/.pyc 리버싱, Go/Rust 바이너리, WebAssembly, ARM 기초(호출규약/Thumb 모드/QEMU 에뮬레이션)를 다룬다. 또한 `algorithms`/`automation` 카테고리의 100개 글에는 실제로 실행해서 검증한 완결된 Python 3 예제 스크립트(주석 포함)를 대폭 보강했다 — 역연산/솔버 코드를 처음 짜보는 사람도 그대로 따라할 수 있는 것이 목표다.

장문 가이드/레퍼런스/문제해결 유형이 섞여 있으며, x86/x64 어셈블리 니모닉은 mnemonic 하나만 검색해도 전용 글이 최상단에 뜨도록 설계되어 있습니다(Assembly Dictionary, `assembly` 카테고리).

완료된 항목:
- 콘텐츠 1,110개 (Phase 1~4 + 드림핵 write-up + C 코드 분석 + Python 예제 보강 + 타 아키텍처/언어)
- 툴 오프라인 킷 매니페스트(`tools/manifest.json`, 49개 도구) + 다운로드 스크립트(Phase 5)
- 프로젝트 자체 제작 SVG 다이어그램(Phase 6, `assets/images/diagrams/`)
- 검색 스모크 테스트 145개 쿼리 자동화(Phase 7, `tests/`)

## 빌드하기

Python 3 표준 라이브러리만 사용합니다 (외부 패키지 불필요).

```bash
python3 scripts/build.py       # content/articles/*.md -> dist/ 생성
python3 scripts/validate.py    # 중복/깨진 링크/frontmatter/placeholder/file:// 안전성 검증
```

`dist/`는 GitHub에 함께 포함되므로 저장소를 받은 뒤 바로 `dist/index.html`을 더블클릭할 수 있습니다. 콘텐츠를 수정한 경우에는 빌드 명령으로 산출물을 갱신한 뒤 함께 커밋합니다.

빌드/검증은 idempotent합니다 — 연속으로 두 번 실행해도 같은 결과가 나옵니다.

## 검색 테스트

```bash
node tests/run-smoke-test.js   # tests/search-smoke-queries.txt의 145개 쿼리를 실제 검색 엔진으로 실행
```

Node.js의 `vm` 모듈로 빌드된 `dist/assets/search-index.js` + `assets/js/search.js`를 그대로 로드해서 실행하므로, 브라우저에서 `dist/index.html`을 열었을 때와 동일한 코드 경로를 검증합니다.

## 오프라인 사용법

1. 저장소의 `dist/` 폴더를 통째로 오프라인 PC(SSD 등)에 복사한다.
2. 인터넷 연결 없이 `dist/index.html`을 더블클릭해서 연다.
3. 검색창에 명령어, 레지스터, 에러 메시지, 상수, 증상 등을 아무렇게나 입력한다.

콘텐츠를 직접 수정했다면 먼저 `python3 scripts/build.py`로 `dist/`를 갱신합니다.

로컬 서버, Node, Python, CDN, 원격 폰트/이미지, `fetch()`/`XMLHttpRequest` 없이 순수 `file://`로 동작하도록 만들어져 있습니다. 이미지도 전부 로컬 SVG(`assets/images/`)만 사용합니다.

### 오프라인 툴킷 준비 (선택)

인터넷이 되는 PC에서 실제 리버싱 도구(IDA Free/Ghidra/x64dbg/GDB/Pwndbg/DIE/PE-bear 등 49종)를 미리 받아두려면:

```bash
# Linux/macOS
bash scripts/fetch-tools.sh

# Windows
powershell -ExecutionPolicy Bypass -File scripts\fetch-tools.ps1
```

`tools/manifest.json`에 기록된 공식 배포처에서 다운로드하고 SHA256을 자동 검증합니다. PyPI 패키지/apt 패키지처럼 직접 다운로드 URL이 없는 항목은 안내 메시지만 출력하니, `tools/manifest.json`의 `offline_install` 필드를 참고하세요. 받은 파일은 `offline-kit/`(git에서 제외됨) 아래에 저장되며, 다운로드 후에는 `python3 tools/verify-checksums.py`로 언제든 재검증할 수 있습니다.

## 저장소 구조

```text
content/articles/<category>/<slug>.md   # 글 원본 (frontmatter + markdown)
assets/css, assets/js                   # 손으로 작성한 사이트 정적 리소스
assets/images/diagrams/                 # 프로젝트 자체 제작 SVG 다이어그램
scripts/build.py                        # 빌드 스크립트 (마크다운 -> dist/)
scripts/mdlib.py                        # 의존성 없는 frontmatter/markdown 파서
scripts/validate.py                     # 콘텐츠/링크/검색 인덱스/file:// 안전성 검증
scripts/storage-report.py               # 카테고리별 디스크 사용량 리포트 (40GB 한도 대조)
scripts/fetch-tools.sh / .ps1           # 툴 오프라인 킷 다운로드 스크립트
tools/manifest.json                     # 오프라인 툴킷 매니페스트 (버전/URL/SHA256/라이선스)
tools/verify-checksums.py               # 다운로드된 툴 파일 체크섬 검증
research/sources.json                   # 리서치 출처 기록
tests/search-smoke-queries.txt          # 검색 스모크 테스트 쿼리 목록 (145개)
tests/run-smoke-test.js                 # 검색 스모크 테스트 실행 스크립트 (Node.js vm 샌드박스)
dist/                                   # 커밋된 오프라인 배포용 빌드 산출물
```

`reversing_analysis/`는 이 저장소와 무관한 별도 프로젝트이며 git에서 제외되어 있습니다.
