---
id: REV-0291
title: "radare2 설치와 첫 명령"
slug: "rev-0291-radare2-install-first-command"
category: "tools"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["radare2"]
keywords: ["radare2 설치", "r2 첫 명령", "radare2 사용법", "aaa 분석", "radare2 windows 설치", "radare2 linux 설치"]
aliases: ["radare2 설치법", "r2 시작하기", "radare2 튜토리얼", "radare2 처음 쓰는 법"]
symptom_keywords: ["radare2 설치가 안됨", "r2 명령어를 모름", "radare2 처음 써봄", "r2 pdf 아무것도 안나옴"]
source_ids: ["SRC-RADARE2-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
radare2(줄여서 `r2`)는 설치 파일 하나 없이도 동작하는 무료 오픈소스 커맨드라인 리버싱 프레임워크로, `r2 -A ./chall` 한 줄만 치면 자동 분석까지 끝난 상태로 바이너리를 열 수 있다.

## 언제 검색해야 하나
- IDA/Ghidra를 설치할 수 없거나 GUI 자체가 없는 서버·컨테이너·CTF 원격 환경에서 바이너리를 분석해야 할 때
- 커맨드라인에서 빠르게 함수 목록, 디스어셈블리, 문자열을 확인하고 바로 스크립팅까지 연결하고 싶을 때
- radare2를 처음 설치했는데 어떤 명령부터 쳐야 할지 막막할 때

## 핵심 개념
radare2는 파일을 여는 "코어"(`r2`)와, 그 위에서 동작하는 여러 서브시스템으로 구성된다. 명령어 접두 문자 하나가 대체로 하나의 서브시스템에 대응한다는 규칙만 알아도 명령어 체계가 훨씬 덜 낯설어진다.

- `a` — Analysis (분석: 함수 경계 찾기, xref 만들기 등)
- `p` — Print (출력: 디스어셈블리, hex 덤프 등)
- `i` — Info (파일/헤더/임포트 정보)
- `s` — Seek (커서를 특정 주소로 이동)
- `f` — Flags (주소에 이름표 붙이기, IDA의 이름과 비슷한 개념)
- `d` — Debug (디버깅 실행)
- `V` — Visual mode (커맨드라인 안에서 동작하는 반쪽짜리 GUI)

즉 "디스어셈블리를 보고 싶다"는 `p`(print) 계열, "함수 목록을 찾고 싶다"는 `a`(analysis) 계열이라는 식으로 접근하면 명령어를 외우기보다 유추할 수 있다. radare2 자체는 순수 커맨드라인 도구이고, 같은 엔진을 GUI로 감싼 것이 Cutter(REV-0293)다 — 둘은 완전히 다른 도구가 아니라 같은 분석 엔진에 대한 두 가지 인터페이스라고 이해하면 된다.

## 화면/코드에서 보이는 징후
radare2를 켜야 하는 상황은 코드 화면이 아니라 "지금 내 손에 GUI 디스어셈블러가 없다"는 환경적 신호로 판단한다. SSH로 접속한 리눅스 서버, Docker 컨테이너, 혹은 그냥 커맨드라인이 더 빠르다고 느껴지는 순간이 전형적이다.

## 가장 먼저 할 것
설치가 끝났다면 아무 실행 파일이나 대상으로 다음을 쳐본다.
```bash
r2 -v
r2 -A ./chall
```
`-A`는 파일을 열면서 곧바로 전체 자동 분석(`aaa`와 동일)까지 수행하라는 옵션이다. 프롬프트가 `[0x00001149]>` 형태로 바뀌면 정상적으로 열린 것이다.

## 단계별 절차

### 1) 설치 — Linux
Debian/Ubuntu 계열은 배포판 저장소 버전이 오래된 경우가 많아 공식 설치 스크립트를 권장한다.
```bash
# 배포판 패키지(간단하지만 버전이 오래될 수 있음)
sudo apt install radare2

# 공식 설치 스크립트(최신 버전, 오프라인 대회 전 미리 실행해 둘 것)
git clone https://github.com/radareorg/radare2
cd radare2
sys/install.sh
```
오프라인 환경에서 쓸 계획이라면 대회장에 가기 전에 `git clone`과 `sys/install.sh`를 온라인 상태에서 미리 끝내 두어야 한다. `sys/install.sh`는 인터넷에서 소스를 받아 빌드하는 스크립트라 오프라인에서는 실행할 수 없다.

### 2) 설치 — Windows
공식 GitHub 릴리스 페이지(`https://github.com/radareorg/radare2/releases`)에서 `radare2-<버전>-w64.zip` 형태의 압축 파일을 받아 원하는 폴더에 풀기만 하면 된다. 별도의 설치 프로그램 실행이 필요 없는 "포터블" 배포이므로, 압축을 풀어둔 폴더 전체를 오프라인 대회용 USB/외장 SSD에 그대로 복사해 가도 동작한다.
```powershell
# 압축을 푼 폴더의 bin 디렉터리를 PATH에 추가하거나, 그 폴더 안에서 직접 실행
.\radare2-5.9.x-w64\bin\r2.exe -v
```

### 3) 첫 세션 — 자동 분석부터 함수까지
```bash
r2 -A ./chall
```
`-A` 없이 그냥 `r2 ./chall`로 열었다면 프롬프트 안에서 수동으로 분석을 돌린다.
```
[0x00001060]> aaa
```
`aaa`는 "분석을 세 단계까지(함수, 참조, 타입 추정 등) 반복해서 최대한 깊게 하라"는 의미다. 분석이 끝나면 함수 목록을 확인한다.
```
[0x00001060]> afl
```
`main`으로 이동해서 디스어셈블리를 본다.
```
[0x00001060]> s main
[0x00001149]> pdf
```
`pdf`(Print Disassemble Function)는 현재 커서(`s`로 이동한 위치)가 속한 함수 전체를 디스어셈블리로 보여준다.

### 4) 종료
```
[0x00001149]> q
```

## 명령어/단축키
| 명령 | 의미 |
|---|---|
| `r2 -A ./chall` | 파일을 열면서 자동 분석까지 수행 |
| `aaa` | 프롬프트 안에서 전체 자동 분석 수동 실행 |
| `afl` | 찾은 함수 목록 출력 |
| `s main` | `main` 심볼 위치로 커서 이동(seek) |
| `pdf` | 커서가 속한 함수 디스어셈블리 출력 |
| `iz` | `.rodata` 등에서 문자열 추출 |
| `q` | 종료 |

## 출력 해석
`pdf` 출력에서 왼쪽 열은 주소, 화살표(`;-- main:` 등)는 함수/블록 경계 표시, `;`로 시작하는 줄은 radare2가 자동으로 붙인 주석(예: 어떤 문자열을 참조하는지)이다. 분석(`aaa`)을 하지 않고 `pdf`를 치면 "함수를 찾을 수 없다"는 뜻의 빈 결과나 오류가 나올 수 있다 — 이건 파일이 잘못된 게 아니라 아직 함수 경계를 계산하지 않았기 때문이다.

## 버전 최신화 — r2env
radare2는 개발이 매우 활발해서 배포판 패키지 버전이 몇 달만 지나도 최신 기능(새 아키텍처 지원, 버그 수정)이 빠져있는 경우가 흔하다. 여러 버전을 나란히 관리하고 싶다면 공식 버전 관리 도구인 `r2env`를 쓸 수 있다.
```bash
pip install r2env
r2env init
r2env install radare2@latest
r2env use radare2@latest
```
이 방식도 결국 온라인에서 소스를 받아 빌드하므로, 오프라인 대회 전에 미리 원하는 버전을 설치해 두고 그 결과물(빌드된 바이너리)만 오프라인 매체에 복사해 가는 방식으로 준비해야 한다.

## 흔한 실수
- `aaa`(또는 `-A`)를 건너뛰고 바로 `pdf`, `afl`을 쳐서 "아무것도 안 나온다"고 당황하는 것 — radare2는 파일을 열어도 자동으로 분석하지 않는다(`-A` 옵션이나 `aaa` 명령을 명시해야 함).
- 명령어 대소문자를 헷갈리는 것 — `pdf`와 `PDF`, `afl`과 `aFL`은 전혀 다른 동작이다. radare2 명령어는 대소문자를 엄격히 구분한다.
- 큰 바이너리에서 `aaa` 대신 더 오래 걸리는 `aaaa`(실험적 심화 분석)를 습관적으로 돌려서 분석 시간이 과도하게 길어지는 것 — 처음에는 `aaa`로 충분하다.
- Windows에서 `r2.exe`가 있는 폴더를 PATH에 등록하지 않고 매번 전체 경로를 타이핑하는 것 — 대회 시작 전에 미리 PATH에 등록해 두면 편하다.

## 막혔을 때 다음 체크
- 명령어가 너무 많아서 뭘 써야 할지 모르겠다면 → [REV-0292 radare2 명령어 치트시트](./rev-0292-radare2-commands-cheatsheet.md)
- 커맨드라인이 아니라 마우스로 클릭하며 보고 싶다면 → [REV-0293 Cutter 설치와 기본 사용법](./rev-0293-cutter-install-usage.md)
- ELF 구조 자체(섹션, 세그먼트)가 궁금하면 → [REV-0091 readelf 기본 사용법](../linux-elf/rev-0091-readelf-basics.md)

## 미니 예제
```bash
$ r2 -A ./chall
[0x00001060]> afl
0x00001060    1 42   entry0
0x00001149    1 23   main
[0x00001060]> s main
[0x00001149]> pdf
            ; CALL XREF from entry0 @ 0x1084
┌ 23: int main (void);
│           0x00001149      55             push rbp
│           0x0000114a      4889e5         mov rbp, rsp
│           0x0000114d      bf04200000     mov edi, str.Enter_the_password
│           0x00001152      e8d9feffff     call sym.imp.puts
└           0x00001157      c3             ret
```
세 줄의 명령(`afl` → `s main` → `pdf`)만으로 `main`이 문자열을 출력하고 리턴한다는 흐름을 IDA 없이 확인했다.

## 관련 글
- REV-0292 — radare2 명령어 치트시트
- REV-0293 — Cutter 설치와 기본 사용법
- REV-0091 — readelf 기본 사용법
- REV-0096 — checksec 결과 읽는 법

## 출처/검증
- 설치 방법(`sys/install.sh`, GitHub 릴리스 zip)과 명령어 접두 체계(`a`/`p`/`i`/`s`/`f`/`d`/`V`): radare2 공식 문서 "The Radare2 Book"(https://book.rada.re) 및 프로젝트 공식 GitHub 저장소 README 기준.
- 이 문서의 명령어 예시는 실제 대회 환경에서 재현하며 검증하지 못했으며, radare2 버전에 따라 세부 출력 포맷(주석 색상, 박스 문자 등)이 다를 수 있다. 사용 전 `r2 -v`로 설치된 버전을 확인할 것.
