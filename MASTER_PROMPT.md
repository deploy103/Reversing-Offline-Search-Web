# MASTER_PROMPT.md

너는 이 저장소의 수석 개발자이자 리버싱 기술 편집자다.

목표는 `Reversing-Offline-Search-Web`이라는 완전 오프라인 리버싱 검색 웹을 실제로 완성하는 것이다.

말만 계획하지 말고 저장소를 만들고, 조사하고, 코드를 작성하고, 글을 작성하고, 검증하고, Git에 커밋하면서 끝까지 진행하라.

## 시작 명령

현재 디렉터리가 비어 있다면:

```bash
mkdir Reversing-Offline-Search-Web
cd Reversing-Offline-Search-Web
git init
git branch -M main
gh repo create Reversing-Offline-Search-Web --private --source=. --remote=origin
```

그 뒤 제공된:
- `AGENTS.md`
- `REQUIREMENTS.md`
- `CONTENT_PLAN.md`
를 저장소 루트에 넣는다.

이미 작업 중인 저장소라면 새로 만들지 말고 복구 프로토콜부터 수행한다.

## 절대 목표

인터넷이 완전히 끊긴 Windows PC에서 SSD를 꽂고:

```text
dist/index.html
```

을 더블클릭하면 사이트가 열려야 한다.

그리고 검색창에 다음처럼 아무렇게나 넣어도 답을 찾을 수 있어야 한다:

```text
call
CALL 명령어
call rax
함수 호출
cmp jnz
test eax eax
positive sp value
_libc_start_main
-87097619
0xffffff
16777619
rdi rsi
rcx rdx
ida f5
x64dbg string
upx
ptrace
```

## 개발 순서

### Phase 0 — 복구
`AGENTS.md`의 Recovery Protocol 수행.

### Phase 1 — 골격
먼저 다음을 완성:
- 정적 사이트 구조
- 검색 UI
- 검색 인덱스 생성기
- Article renderer
- 관련 글
- category/tag filtering
- file:// 환경 지원
- light/dark 정도의 최소 UI
- no-CDN
- local assets

이 단계에서 샘플 글 10개로 검색을 먼저 완성한다.

### Phase 2 — 연구 데이터베이스
웹 검색을 대량으로 수행한다.

검색 대상:
- 공식 IDA/Hex-Rays 문서
- Ghidra 공식 문서
- x64dbg 공식 문서
- GDB 공식 문서
- Pwndbg 공식 문서
- radare2/rizin 공식 문서
- Intel/AMD x86 instruction reference
- Microsoft PE/Windows ABI 문서
- System V AMD64 ABI
- pwntools/Z3/angr 공식 문서
- CTFtime writeups
- DreamHack/각종 CTF 풀이 글
- reversing 교육 블로그
- tool-specific tutorials

각 자료는 `research/sources.json`에 기록.

검색 결과를 그대로 믿지 말고 서로 검증.

최신 UI/명령이 달라질 수 있는 툴은 현재 버전을 우선.
공식 문서끼리 단축키/동작 설명이 엇갈리면 실제 설치 버전으로 검증하고 "버전 차이" 박스를 작성한다.

### Phase 3 — Assembly Dictionary 먼저
초보자가 가장 자주 막히므로 어셈블리 명령어 사전을 우선 작성한다.

`CONTENT_PLAN.md`의 50개 Assembly 글을 먼저 작성.

특히 `CALL` 페이지는 아주 강하게 작성:
- return address
- RSP 변화
- direct/indirect
- call register/memory
- imported function
- SysV args
- Windows args
- xref
- step into/over
- return value RAX/EAX
- nested call
- call graph

모든 mnemonic을 `aliases`와 `keywords`에 넣어 단어 하나만 검색해도 최상위에 뜨게 한다.

### Phase 4 — 1,000개 콘텐츠
`CONTENT_PLAN.md` 순서대로 작업.

구성:
- 장문 가이드/튜토리얼 500개
- 레퍼런스/치트시트/사전 250개
- 오류/막힘/패턴 해결 250개

장문 글은 인터넷 없이 그 글 하나만 읽고 실제로 다음 행동을 할 수 있을 정도로 작성한다.
반대로 단순 mnemonic, 에러 메시지, API, 단축키 조회는 짧고 빠르게 찾을 수 있는 레퍼런스 형태로 만든다.

절대 1,000개 숫자를 맞추려고 내용만 살짝 바꾼 중복 글을 만들지 마라.

10개 작성할 때마다:
1. validate
2. search test
3. `DEVELOPMENT_LOG.md` 갱신
4. `state/progress.json` 갱신
5. commit

글 숫자만 채우기 위해 짧고 중복된 쓰레기 글을 만들지 마라.

### Phase 5 — 툴 오프라인 킷
공식 배포처를 조사하고 `tools/manifest.json` 작성.

필드:
```json
{
  "name": "",
  "version": "",
  "platform": [],
  "official_url": "",
  "release_url": "",
  "sha256": "",
  "license": "",
  "offline_install": "",
  "local_path": ""
}
```

다운로드 스크립트:
- Windows PowerShell
- Linux shell

다운로드 후 반드시 SHA256 검증.

큰 바이너리는 일반 Git history에 넣지 않는다.

### Phase 6 — 이미지
설명에 도움이 되는 곳은 적극적으로 이미지를 넣는다.

우선 프로젝트가 직접 만든:
- IDA 화면 캡처
- Ghidra 화면 캡처
- x64dbg 화면 캡처
- PE-bear
- Detect It Easy
- GDB/Pwndbg
- 직접 만든 stack/call/flags diagram

을 사용.

외부 이미지는 라이선스를 확인하고 로컬 캐시한다.

이미지 하나마다 메타데이터를 남긴다.

### Phase 7 — 최종 검증
실제로 네트워크를 사용하지 않는 조건을 가정하고 `file://` smoke test.

검색 테스트 100개를 자동화한다.

반드시 포함:
- `call`
- `ret`
- `lea`
- `cmp`
- `test`
- `jnz`
- `jz`
- `xor`
- `sar`
- `_libc_start_main`
- `positive sp`
- `0xffffff`
- `16777619`
- `ida strings`
- `x64dbg string`
- `pie breakpoint`
- `ptrace`
- `IsDebuggerPresent`

## 콘텐츠 작성 방법

한 글은 블로그 글처럼 읽혀야 하지만 대회 중 빨리 볼 수 있어야 한다.

맨 위에:
- 한 줄 정답
- 이 글이 필요한 상황
- 30초 해결 절차

그 아래 상세 설명.

긴 글은 목차 추가.

명령어는 복붙 가능하게 code block.

Windows/Linux 명령을 혼합하지 말고 명확히 표시.

## 블로그/Writeup 조사

가능한 많은 관점의 글을 검색해서:
- 어떤 순서로 풀었는지
- 어디서 막혔는지
- 어떤 단서를 보고 알고리즘을 알아챘는지
- 어떤 툴을 썼는지
- 어떤 실수를 했는지
를 추출한다.

원문 자체보다 '문제 해결 패턴'을 데이터베이스화하는 것이 목적이다.

라이선스가 명확히 허용하면 원문/이미지 로컬 보관 가능.
그 외에는 한국어로 새로 설명하고 출처를 남긴다.

## 검색 별칭
초보자가 욕하거나 대충 입력해도 찾게 만들어라.

예:
```text
스택 씨발
스택 모르겠음
rsp 뭐임
함수 인자 어디
call 뭐임
main 어디
f5 안됨
디컴파일 개판
음수 왜나옴
and 왜함
xor 반복문
```

이런 표현을 실제 본문에 억지로 넣지 말고 `symptom_keywords` 또는 aliases에 넣는다.

## 개발일지
`DEVELOPMENT_LOG.md` 예:

```md
## 2026-09-08 22:10 KST
### 완료
- REV-0001 ~ REV-0010 작성
- search rank 개선

### 검증
- file:// OK
- 25 queries passed

### 문제
- Korean fuzzy match에서 일부 오탐

### 다음 작업
- REV-0011 ~ REV-0020
- 2-gram ranking 수정

### Commit
- abc1234
```

중단 직전 반드시 기록.

## 종료 조건
계획서만 쓰고 끝내지 마라.

최종적으로:
- 1,000개
- 검색
- Assembly Dictionary
- 설치법
- 단축키
- 이미지
- offline kit manifest
- file:// 테스트
- private GitHub push
까지 완료되어야 한다.


## 저장공간 한도

완성본 전체는 40GB를 절대 넘지 마라.
권장 목표는 30~35GB다.

텍스트 용량을 아끼려고 설명을 줄이지 마라.
공간 절약 우선순위:
1. 중복 파일 제거
2. 중복 이미지 제거
3. 불필요한 설치파일 버전 제거
4. 영상/GIF를 필요한 프레임 또는 정적 이미지로 대체
5. 동일 툴의 여러 구버전 제거

`scripts/storage-report.py`를 주기적으로 실행하고 개발일지에 현재 총 용량을 기록한다.
