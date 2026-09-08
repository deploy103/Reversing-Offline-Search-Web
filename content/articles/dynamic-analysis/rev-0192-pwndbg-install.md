---
id: REV-0192
title: "Pwndbg 설치와 실행"
slug: "rev-0192-pwndbg-install"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pwndbg 설치", "pwndbg install", "pwndbg setup.sh", "gdbinit", "pwndbg 실행", "gdb 플러그인"]
aliases: ["pwndbg 설치법", "pwndbg 사용법 시작", "pwndbg 안켜짐", "pwndbg 설치 안됨", "gdb pwndbg 연결"]
symptom_keywords: ["pwndbg가 안 켜짐", "pwndbg 설치 오류", "gdb에서 context가 안 뜸", "pwndbg 명령어가 안 먹힘", "pwndbg import 에러"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg는 GDB의 기본 UX를 리버싱/exploit 개발에 맞게 확장하는 오픈소스 파이썬 플러그인으로, 공식 저장소를 클론한 뒤 제공되는 `setup.sh`를 실행하면 자동으로 `~/.gdbinit`에 등록되어, 이후 그냥 `gdb`를 켜기만 해도 레지스터/스택/디스어셈블리를 한 화면에 보여주는 `context` 기능이 기본 활성화된다.

## 언제 검색해야 하나
- 순정 GDB 화면이 텍스트만 잔뜩 나오고 한눈에 안 들어와서, IDA나 x64dbg처럼 레지스터/스택/코드를 한 화면에 보여주는 도구가 있는지 찾고 있을 때
- CTF 문제 풀이 글에서 `pwndbg>` 프롬프트나 `context`, `telescope`, `vmmap` 같은 명령을 보고 이게 뭔지 궁금할 때
- Pwndbg를 설치했는데 GDB를 켜도 여전히 순정 화면만 나올 때
- Pwndbg 설치 스크립트가 에러를 내면서 멈출 때
- 오프라인(인터넷 없는) 대회 PC에 미리 Pwndbg를 준비해두고 싶을 때

## 핵심 개념

### Pwndbg는 GDB 자체가 아니라 GDB의 확장이다
Pwndbg는 별도의 디버거가 아니라, GDB가 제공하는 파이썬 API(`gdb` 모듈)를 이용해 만들어진 **파이썬 스크립트 모음**이다. `~/.gdbinit` 파일에 이 스크립트를 로드하는 코드가 등록되면, GDB를 실행할 때마다 자동으로 Pwndbg가 함께 로드된다. 즉 "Pwndbg를 켠다"는 건 별도 프로그램을 실행하는 게 아니라 **그냥 평소처럼 `gdb ./chall`을 치는 것**이며, `.gdbinit` 설정이 되어 있다면 그 순간 자동으로 Pwndbg 환경이 적용된다.

### 설치 방법 — 공식 저장소 클론 + setup.sh
Pwndbg의 공식 설치 방법은 GitHub 저장소를 클론한 뒤 제공되는 설치 스크립트를 실행하는 것이다.
```bash
git clone https://github.com/pwndbg/pwndbg
cd pwndbg
./setup.sh
```
`setup.sh`는 필요한 파이썬 패키지 설치, GDB 버전 확인, 그리고 가장 중요하게는 **`~/.gdbinit`에 Pwndbg를 자동 로드하는 줄을 추가**하는 작업까지 전부 처리해준다. 스크립트가 끝나면 별도 설정 없이 바로 다음 GDB 세션부터 Pwndbg가 활성화된다.

### 오프라인 환경 준비 — 인터넷 없는 대회 PC 대비
CTF 대회장처럼 인터넷이 끊긴 환경에서 쓰려면, **인터넷이 되는 곳에서 미리** 저장소를 클론하고 `setup.sh`까지 실행해서 필요한 파이썬 의존성을 전부 설치해둔 뒤, 그 상태의 홈 디렉터리(`~/pwndbg`, `~/.gdbinit`, 그리고 `setup.sh`가 설치한 파이썬 가상환경/패키지)를 통째로 USB나 외장 SSD에 복사해가는 방식이 가장 안전하다. 설치 스크립트 자체가 네트워크에서 패키지를 받아오므로, 오프라인 상태에서 `setup.sh`를 새로 돌리면 실패한다.

### 설치 확인 — GDB를 켜보면 바로 알 수 있다
설치가 잘 됐다면 GDB를 켜자마자 프롬프트가 `pwndbg>`로 바뀌고, 시작 배너에 Pwndbg 버전 정보가 출력된다.
```bash
$ gdb ./chall
pwndbg: loaded 138 pwndbg commands and 46 shell commands. Type pwndbg [--shell | --all] [filter] for a list.
pwndbg> 
```
이 배너가 안 뜨고 그냥 순정 `(gdb)` 프롬프트만 보인다면, `~/.gdbinit`에 Pwndbg 로드 줄이 없거나 경로가 잘못됐다는 뜻이다.

### `~/.gdbinit` 직접 확인/수정하기
설치 스크립트가 자동으로 넣어주는 줄은 대략 다음과 같은 형태다.
```
source /home/user/pwndbg/gdbinit.py
```
이 파일을 열어 해당 줄이 있는지, 경로가 실제 클론한 위치와 일치하는지 확인한다. 여러 개의 GDB 확장(예: GEF, PEDA)을 동시에 등록해두면 서로 충돌해서 아무것도 제대로 안 뜰 수 있으므로, 한 번에 하나의 확장만 활성화하는 것이 안전하다.

### 실행 후 첫 화면 이해하기
Pwndbg가 로드된 상태에서 `start`나 `run`으로 프로세스를 멈추면, 순정 GDB와 달리 **`context`라는 통합 화면이 자동으로 출력**된다. 여기에는 레지스터, 현재 위치 주변 디스어셈블리, 스택 내용, 백트레이스가 한 화면에 색깔별로 정리되어 나온다. 이 자동 출력 기능이 Pwndbg를 쓰는 가장 큰 이유이며, 자세한 내용은 REV-0193에서 다룬다.

### 버전 확인 및 명령어 목록
```
pwndbg> pwndbg
```
또는
```
pwndbg> version
```
현재 설치된 Pwndbg가 제공하는 전체 명령어 목록을 보고 싶다면 `pwndbg`만 입력하면 카테고리별로 정리된 목록이 나온다. 문법이 기억 안 나는 개별 명령은 GDB의 `help` 뒤에 이름을 붙여서 확인할 수 있다.
```
pwndbg> help telescope
```

### 순정 GDB 명령은 그대로 다 쓸 수 있다
Pwndbg는 GDB를 대체하는 게 아니라 **추가 명령을 얹는 것**이므로, `break`, `run`, `stepi`, `x/`, `watch` 등 지금까지 배운 순정 GDB 명령은 전부 그대로 동작한다. 여기에 `context`, `telescope`, `vmmap`, `hexdump`, `search` 같은 Pwndbg 전용 명령이 추가로 생기는 것뿐이다.

## 화면/코드에서 보이는 징후
- GDB 시작 배너에 `pwndbg: loaded N pwndbg commands...` 문구가 뜸
- 프롬프트가 `(gdb)`가 아니라 `pwndbg>`로 바뀜
- `start`/`run`/`stepi` 등을 칠 때마다 색깔 있는 박스 형태의 레지스터/디스어셈블리/스택 화면이 자동으로 뜸
- 설치가 안 됐다면 순정 `(gdb)` 프롬프트만 나오고 `telescope`, `vmmap` 같은 명령이 `Undefined command` 에러를 냄

## 가장 먼저 할 것
`git clone`이 가능한 환경(인터넷 연결)에서 먼저 설치를 마쳐두고, `gdb` 아무 바이너리로 켜서 `pwndbg>` 프롬프트가 뜨는지부터 확인한다.

## 단계별 절차

**1) 저장소 클론**
```bash
git clone https://github.com/pwndbg/pwndbg
cd pwndbg
```

**2) 설치 스크립트 실행**
```bash
./setup.sh
```

**3) 새 터미널에서 GDB 실행해 확인**
```bash
gdb ./chall
```
`pwndbg>` 프롬프트와 로드 배너가 뜨는지 확인한다.

**4) 설치가 안 됐다면 `.gdbinit` 직접 확인**
```bash
cat ~/.gdbinit
```
`source /경로/pwndbg/gdbinit.py` 줄이 있는지, 경로가 맞는지 확인한다.

**5) 명령어 목록/도��말 확인**
```
pwndbg> pwndbg
pwndbg> help context
```

**6) 오프라인 사용을 위해 설치된 디렉터리와 `.gdbinit`을 백업**
인터넷이 끊긴 대회 PC로 통째로 복사해간다.

## 명령어/단축키
```bash
git clone https://github.com/pwndbg/pwndbg
cd pwndbg && ./setup.sh
gdb ./chall
```
GDB 내부: `pwndbg`, `version`, `help COMMAND`

## 출력 해석
- `pwndbg: loaded 138 pwndbg commands and 46 shell commands.`에서 숫자는 버전에 따라 다르며, 이 메시지 자체가 정상 로드의 증거다.
- `pwndbg>` 프롬프트가 보인다는 것은 GDB + Pwndbg가 정상적으로 결합됐다는 뜻이며, 이후 모든 순정 GDB 명령과 Pwndbg 전용 명령을 함께 쓸 수 있다.
- `Undefined command: "telescope"`처럼 Pwndbg 명령이 안 먹히면, 지금 켠 GDB 세션에 Pwndbg가 로드되지 않은 것이다 — `.gdbinit` 경로 문제일 가능성이 크다.

## 흔한 실수
- `setup.sh`를 인터넷이 끊긴 상태에서 실행해서 파이썬 패키지 다운로드 단계에서 실패하는 것 — 반드시 온라인 상태에서 먼저 설치를 마쳐야 한다.
- 여러 GDB 확장(Pwndbg, GEF, PEDA)을 동시에 `.gdbinit`에 등록해서 서로 충돌하는 것 — 한 번에 하나만 활성화한다.
- 시스템에 여러 개의 파이썬 버전이 있을 때, GDB가 내부적으로 링크된 파이썬 버전과 Pwndbg가 설치를 시도한 파이썬 버전이 달라 임포트 에러가 나는 것 — `setup.sh`가 대부분 알아서 맞는 버전을 찾아주지만, 수동 설치 시 이 부분에서 자주 막힌다.
- `sudo`로 설치를 진행해서 `~/.gdbinit`이 root 계정에만 적용되고 실제 사용하는 일반 계정에는 적용되지 않는 것.

## 막혔을 때 다음 체크
- 설치는 됐고 `pwndbg>`도 뜨는데 구체적으로 뭘 볼 수 있는지 궁금하다면 → REV-0193 Pwndbg context telescope vmmap
- 순정 GDB의 기본 명령(break, run, x/)부터 다시 익히고 싶다면 → REV-0185 GDB 실행 run start args 사용법, REV-0186 GDB break와 address breakpoint

## 미니 예제
```bash
$ git clone https://github.com/pwndbg/pwndbg
$ cd pwndbg && ./setup.sh
...
Pwndbg is now installed! Please run `gdb` to get started.
$ gdb ./chall
pwndbg: loaded 138 pwndbg commands and 46 shell commands. Type pwndbg [--shell | --all] [filter] for a list.
pwndbg> start
────────────────────[ REGISTERS ]────────────────────
 RAX  0x0
 RBX  0x7fffffffe4a0
 ...
────────────────────[ DISASM ]────────────────────
 ► 0x555555555185 <main+8>    lea    rax, [rbp - 0x50]
   0x555555555189 <main+12>   mov    rdi, rax
...
pwndbg>
```

## 관련 글
- REV-0193 — Pwndbg context telescope vmmap
- REV-0185 — GDB 실행 run start args 사용법

## 출처/검증
- 설치 절차(`git clone` + `./setup.sh`, `.gdbinit` 자동 등록): Pwndbg 공식 저장소 및 공식 문서(pwndbg.re) "Installation" 섹션 기준.
- 로드 시 표시되는 명령 개수 배너, `pwndbg>` 프롬프트: Pwndbg 공식 문서 기준 (2026-09-08 검증).
