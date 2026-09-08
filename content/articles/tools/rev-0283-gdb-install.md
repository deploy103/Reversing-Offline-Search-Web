---
id: REV-0283
title: "GDB 설치와 기본 설정"
slug: "rev-0283-gdb-install"
category: "tools"
difficulty: "beginner"
platform: [linux, windows]
architecture: [x86, x64]
format: [ELF, PE]
tools: [GDB]
keywords: ["gdb 설치", "gdb install", "gdbinit", "gdb 버전 확인", "gdb offline install", "gdb apt install", "gdb 오프라인 설치"]
aliases: ["gdb 세팅", "gdb 초기 설정", "gdb 기본 설정", "GNU 디버거 설치"]
symptom_keywords: ["gdb 명령어가 없다고 뜸", "gdb: command not found", "gdb 버전이 너무 낮음", "대회장에서 gdb가 안 깔려있음", "gdbinit 어디에 만드나"]
source_ids: ["SRC-GDB-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB(GNU Debugger)는 리눅스 ELF 바이너리를 동적으로 분석하는 표준 디버거로, 대부분의 리눅스 배포판에 이미 설치되어 있거나 `apt install gdb` 한 줄로 설치되며, 대회 PC처럼 인터넷이 없는 환경에서는 미리 받아둔 `.deb` 패키지나 오프라인 설치 이미지로 준비해두는 것이 핵심이다.

## 언제 검색해야 하나
- 리눅스 환경(또는 WSL)에서 `gdb`를 처음 쳐봤는데 `command not found`가 뜰 때
- 대회 PC가 인터넷이 안 되는데 GDB가 없거나 버전이 너무 낮아서 미리 준비해야 할 때
- `gdb --version`으로 버전을 확인하고 최신 기능(예: `starti`, TUI 개선)이 되는지 판단하고 싶을 때
- 매번 같은 설정(`set disassembly-flavor intel` 등)을 반복 입력하기 귀찮아서 `.gdbinit`을 만들고 싶을 때
- Pwndbg 등 GDB 확장을 얹기 전에 순정 GDB부터 정상 동작하는지 확인하고 싶을 때

## 핵심 개념

### GDB는 무엇을 위한 도구인가
GDB는 컴파일된 프로그램을 실제로 실행시키면서 레지스터, 메모리, 스택을 관찰하고 원하는 지점에서 멈추게 하는 동적 분석 도구다. IDA/Ghidra 같은 정적 분석 도구가 "코드를 읽어서 추측"한다면, GDB는 "진짜로 돌려서 확인"한다. CTF 리버싱/pwn 문제에서 정적 분석으로 로직을 파악한 뒤 GDB로 실제 입력값과 메모리 상태를 검증하는 흐름이 표준이다.

### 대부분의 리눅스에는 이미 GDB가 있다
Ubuntu, Debian, Kali 같은 주요 배포판은 기본 이미지에 GDB를 포함하거나, 저장소에 항상 존재하는 필수 패키지로 취급한다. 따라서 "GDB 설치"라는 작업은 실제로는 아래 두 가지 중 하나로 끝나는 경우가 많다.
1. 이미 설치돼 있는지 확인만 하면 되는 경우
2. 최소 설치 이미지(예: 매우 가벼운 도커 컨테이너, 서버용 배포판)라서 패키지 매니저로 한 번 받아야 하는 경우

### 오프라인 대회 환경에서의 문제
경진대회/CTF 현장 PC는 보안상 인터넷이 차단된 경우가 많다. 이때 `apt install gdb`를 치면 실패한다. 대응 방법은 두 가지다.
- **사전에(인터넷이 되는 곳에서) `.deb` 패키지와 의존성을 통째로 내려받아 USB로 옮겨 설치**하는 방법 (`apt download gdb`, 또는 `apt-get install --download-only`)
- **대회 PC 이미지 자체에 GDB가 이미 포함된 배포판(Kali, Parrot 등)을 사용**하는 방법

둘 다 "인터넷은 준비 단계에서 딱 한 번만 필요하고, 이후에는 완전히 오프라인으로 동작한다"는 원칙을 따른다.

### `.gdbinit`는 GDB의 시작 설정 파일이다
GDB는 실행될 때마다 `~/.gdbinit`(홈 디렉터리) 또는 현재 디렉터리의 `.gdbinit`을 자동으로 읽어서 그 안의 명령을 순서대로 실행한다. 여기에 자주 쓰는 설정을 넣어두면 매번 손으로 칠 필요가 없다. Pwndbg를 설치하면 설치 스크립트가 이 파일에 `source ~/pwndbg/gdbinit.py` 한 줄을 자동으로 추가해준다.

## 화면/코드에서 보이는 징후
- 터미널에 `gdb`를 쳤는데 `bash: gdb: command not found`
- `gdb --version`이 `GNU gdb (Ubuntu ...) 8.1` 처럼 오래된 버전을 출력 (일부 최신 기능 미지원 가능)
- `gdb ./chall`을 쳤을 때 `(gdb)` 프롬프트가 뜨고 배너에 `Copyright (C) ...`, `This GDB was configured as "x86_64-linux-gnu"` 같은 문구가 보이면 정상 설치된 것
- `.gdbinit`을 만들었는데 GDB를 켤 때 `warning: File "~/.gdbinit" auto-loading has been declined`가 뜨는 경우 (보안상 기본 차단, `set auto-load safe-path` 설정 필요)

## 가장 먼저 할 것
터미널을 열고 `gdb --version`부터 쳐본다. 버전 정보가 정상 출력되면 이미 준비가 끝난 것이고, 별도 설치 작업이 필요 없다. `command not found`가 뜰 때만 아래 설치 절차로 넘어간다.

## 단계별 절차

**1) 설치 여부와 버전 확인**
```bash
gdb --version
which gdb
```

**2) (인터넷이 되는 환경에서) 설치 또는 업데이트**

Debian/Ubuntu/Kali 계열:
```bash
sudo apt update
sudo apt install gdb
```

Fedora/RHEL 계열:
```bash
sudo dnf install gdb
```

Arch 계열:
```bash
sudo pacman -S gdb
```

**3) 오프라인 대회를 대비한 사전 다운로드 (인터넷 되는 곳에서 미리)**
```bash
# 현재 디렉터리에 gdb와 의존 패키지의 .deb를 받아둔다
apt-get install --download-only --reinstall gdb
# 또는 직접 다운로드만
apt download gdb
```
받은 `.deb` 파일들을 USB에 담아 대회 PC로 옮긴 뒤:
```bash
sudo dpkg -i gdb_*.deb
sudo apt-get install -f   # 의존성 에러가 나면 오프라인 저장소로 보완
```
가능하면 대회 전 리허설에서 실제 오프라인 PC에 이 과정을 한 번 미리 검증해두는 것이 안전하다.

**4) `.gdbinit` 기본 설정 만들기**
```bash
cat >> ~/.gdbinit << 'EOF'
set disassembly-flavor intel
set pagination off
set confirm off
EOF
```
- `disassembly-flavor intel`: AT&T 문법 대신 IDA/Ghidra와 동일한 Intel 문법으로 디스어셈블
- `pagination off`: 긴 출력이 `---Type <return>---`로 끊기지 않게 함
- `confirm off`: `kill` 같은 명령에서 y/n 확인을 생략(대회에서 속도 중요)

**5) 실제 바이너리로 정상 동작 확인**
```bash
gdb ./chall
(gdb) start
(gdb) info registers
(gdb) quit
```
`start` 이후 레지스터 목록이 정상 출력되면 설치와 설정이 모두 끝난 것이다.

## 명령어/단축키
| 목적 | 명령 |
|---|---|
| 버전 확인 | `gdb --version` |
| 바이너리 로드 | `gdb ./binary` |
| 인자와 함께 로드 | `gdb --args ./binary arg1 arg2` |
| 설정 파일 위치 | `~/.gdbinit` (사용자), `./.gdbinit` (프로젝트별) |
| 배치 모드(스크립트 실행 후 종료) | `gdb -q -x script.gdb --batch ./binary` |
| GDB 안에서 셸 실행 | `shell <명령어>` |

## 출력 해석
- `GNU gdb (Ubuntu 12.1-...) 12.1`처럼 배포판명과 버전이 함께 나오면 패키지 매니저로 설치된 정상 버전
- `Reading symbols from ./chall...`은 심볼 테이블을 읽었다는 뜻이며 `(No debugging symbols found)`가 붙어도 분석 자체는 가능하다(스트립된 바이너리에서는 원래 뜨는 정상 메시지)
- `auto-load safe-path` 경고는 보안 기능일 뿐 GDB가 고장난 것이 아니다. `.gdbinit`에 `set auto-load safe-path /` (신뢰하는 개인 환경에 한해)를 추가하면 사라진다

## 흔한 실수
- 대회 PC에 인터넷이 없다는 것을 전날까지 모르고 있다가 현장에서 `apt install`을 시도해 실패하는 경우 — 반드시 사전 리허설 필요
- `.gdbinit`을 홈 디렉터리가 아니라 엉뚱한 곳에 만들어서 설정이 전혀 적용되지 않는 경우
- 오래된 GDB(7.x대)를 그대로 쓰면서 최신 문서 기준 명령(`starti` 등)이 안 먹힌다고 착각하는 경우 — 버전부터 확인
- GDB 자체와 Pwndbg를 혼동해서, "GDB가 안 예쁘게 나온다"고 GDB를 재설치하는 경우 — 그건 Pwndbg 같은 확장을 안 깔아서 그런 것(REV-0285 참고)

## 막혔을 때 다음 체크
1. `which gdb`로 실제 실행 파일 경로가 잡히는지 확인
2. `echo $PATH`에 gdb가 설치된 디렉터리가 포함돼 있는지 확인
3. WSL을 쓰는 경우 Windows용 GDB가 아니라 WSL 내부(Linux) GDB를 쓰고 있는지 확인
4. `.gdbinit` 오류가 있으면 GDB 시작 시 오류 메시지가 뜨므로, 방금 추가한 줄부터 하나씩 지워보며 원인 분리
5. 그래도 안 되면 순정 GDB만으로 `gdb ./chall` → `start`가 되는지 먼저 확인한 뒤 Pwndbg 등 확장 문제인지 GDB 자체 문제인지 구분

## 미니 예제
```bash
$ gdb --version
GNU gdb (Ubuntu 12.1-0ubuntu1~22.04) 12.1
$ gdb ./chall
GNU gdb (Ubuntu 12.1-0ubuntu1~22.04) 12.1
Reading symbols from ./chall...
(No debugging symbols found in ./chall)
(gdb) start
Temporary breakpoint 1 at 0x1169
Starting program: /home/user/chall
Temporary breakpoint 1, 0x0000555555555169 in main ()
(gdb)
```

## 관련 글
- REV-0284 — GDB 명령어 치트시트
- REV-0285 — Pwndbg 설치와 오프라인 준비
- REV-0185 — GDB 실행 run start args 사용법
- REV-0192 — Pwndbg 설치와 실행

## 출처/검증
- GDB 공식 온라인 문서(sourceware.org)를 기준으로 시작/설정 관련 내용을 검증했다.
- 배포판별 패키지 설치 명령은 각 배포판 공식 패키지 매니저(apt/dnf/pacman) 기준 표준 사용법이다.
- 최종 확인일: 2026-09-08
