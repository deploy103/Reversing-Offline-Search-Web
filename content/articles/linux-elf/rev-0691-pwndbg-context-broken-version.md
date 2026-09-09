---
id: REV-0691
title: "Pwndbg 버전 문제로 context가 깨져 보일 때"
slug: "rev-0691-pwndbg-context-broken-version"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pwndbg context 깨짐", "pwndbg 색깔 이상함", "pwndbg 화면 겹침", "pwndbg context-sections", "pwndbg TERM 문제"]
aliases: ["pwndbg context 안예쁨", "pwndbg ANSI 코드 그대로 출력", "pwndbg 레이아웃 깨짐"]
symptom_keywords: ["pwndbg context 화면이 겹쳐서 나옴", "pwndbg에서 이상한 코드가 텍스트로 그대로 보임", "pwndbg context 실행하면 파이썬 에러가 남", "pwndbg 업데이트 후 화면이 깨짐"]
source_ids: ["SRC-PWNDBG-DOCS", "SRC-GDB-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`context`(또는 자동 표시되는 REGISTERS/DISASM/STACK 패널) 화면이 겹치거나, `\x1b[1;32m` 같은 ANSI 이스케이프 코드가 글자 그대로 출력되거나, 패널 일부가 통째로 비어 보인다면 원인은 대부분 (1) 터미널이 컬러/이스케이프 코드를 제대로 해석 못 하거나, (2) `git pull`로 Pwndbg만 업데이트하고 `setup.sh`를 다시 안 돌려서 GDB 버전과 안 맞거나, (3) 터미널 폭이 좁아 레이아웃이 깨진 경우이며, 해결책은 실제 터미널에서 실행하기·재설치·`context-sections`로 패널을 줄이는 것이다.

## 언제 검색해야 하나
- `context`를 쳤는데 REGISTERS/DISASM/STACK/BACKTRACE 패널이 서로 겹쳐 보이거나 순서가 뒤섞여 보일 때
- 화면에 `\x1b[` 같은 이스케이프 시퀀스 문자가 색깔 대신 글자 그대로 찍힐 때
- `git pull`로 Pwndbg를 업데이트한 뒤부터 갑자기 `context`가 Python 트레이스백을 뱉거나 일부 패널이 사라졌을 때
- tmux나 IDE에 내장된 터미널에서 유독 Pwndbg 화면만 이상하게 보일 때

## 가장 먼저 할 것
`pwndbg> version`을 쳐서 지금 로드된 Pwndbg/GDB/Python 버전을 확인하고, 최근에 `git pull`이나 배포판 업그레이드로 GDB 버전이 바뀌었는지부터 떠올려본다. 버전이 바뀌었다면 재설치(`./setup.sh`)가 가장 먼저 할 조치다.

## 핵심 개념

### 원인 ① — 터미널이 ANSI 컬러/제어 코드를 해석하지 못함
Pwndbg의 `context` 화면은 색깔 구분과 커서 이동을 위해 ANSI 이스케이프 코드를 적극적으로 사용한다. 출력을 파일로 리다이렉트하거나(`gdb ... > log.txt`), 일부 IDE 내장 터미널·시리얼 콘솔처럼 이런 코드를 제대로 해석하지 못하는 환경에서 실행하면, 색깔 대신 `\x1b[1;32m` 같은 원본 코드가 텍스트로 그대로 보이거나 줄바꿈이 뒤죽박죽될 수 있다. `TERM` 환경변수가 `dumb`이거나 비어있는 경우도 같은 증상을 일으킨다.

### 원인 ② — GDB는 업그레이드됐는데 Pwndbg는 예전 상태(또는 그 반대)
`git pull`로 Pwndbg 저장소만 최신으로 당기고 `./setup.sh`를 다시 실행하지 않으면, 새 버전의 Pwndbg 코드가 예전에 설치해둔 Python 의존성 버전과 맞지 않아 일부 기능이 조용히 깨지거나 `context` 실행 중 Python 예외가 튀어나올 수 있다. 반대로 시스템 패키지 관리자가 GDB 자체를 업그레이드한 경우에도, Pwndbg가 그 GDB 버전의 API 변경을 반영하지 못해 특정 패널만 비거나 오류를 낼 수 있다. Pwndbg는 GDB의 내부 Python API에 상당히 의존하기 때문에 두 구성요소의 버전은 항상 같이 맞춰줘야 한다.

### 원인 ③ — 터미널 폭이 좁아서 레이아웃 계산이 깨짐
`context`는 여러 패널(REGISTERS, DISASM, STACK, BACKTRACE 등)을 현재 터미널의 컬럼 수에 맞춰 나란히 배치하려 시도한다. 터미널 창이 너무 좁으면(예: 80컬럼 이하로 tmux 창을 여러 개 분할한 경우) 레이아웃이 예상과 다르게 줄바꿈되어 뒤섞인 것처럼 보인다.

### 원인 ④ — 서로 다른 GDB 확장이 동시에 로드됨
`~/.gdbinit`에 Pwndbg뿐 아니라 GEF나 예전 버전 Pwndbg의 `source` 줄이 함께 남아있으면, 두 확장이 같은 이름의 명령어(`context`, `vmmap` 등)를 서로 덮어쓰며 충돌해 예측 불가능한 출력이 나올 수 있다.

## 화면/코드에서 보이는 징후
```text
pwndbg> context
\x1b[1;32m─────────\x1b[0m REGISTERS \x1b[1;32m─────────\x1b[0m
```
```text
pwndbg> context
Traceback (most recent call last):
  File "/home/user/pwndbg/pwndbg/commands/context.py", line ..., in context
    ...
```

## 단계별 절차

**1) 버전 확인**
```gdb
pwndbg> version
```
Pwndbg, GDB, Python 버전이 함께 출력된다. Pwndbg GitHub 저장소의 지원 버전 표(README)와 비교한다.

**2) 완전 재설치**
```bash
cd ~/pwndbg
git pull
git submodule update --init --recursive
./setup.sh
```
Pwndbg와 그 의존성을 지금 시스템의 GDB/Python 버전에 맞춰 다시 맞춘다.

**3) `TERM`과 실제 터미널 확인**
```bash
echo $TERM
```
`dumb`이거나 비어있다면, 실제 터미널 에뮬레이터(GNOME Terminal, iTerm2, Windows Terminal + WSL 등)에서 직접 실행한다. tmux 안이라면 `tmux`가 `TERM=screen-256color`나 `tmux-256color`로 잘 설정되어 있는지 확인한다.

**4) 패널 구성 줄여서 폭 문제 완화**
```gdb
pwndbg> set context-sections "regs disasm stack backtrace"
```
필요 없는 패널(예: `code`, `expressions`)을 빼서 한 줄에 들어가는 정보량을 줄이면 좁은 터미널에서도 안정적으로 보인다. 터미널 자체를 넓히는 것이 가장 근본적인 해결책이다.

**5) `.gdbinit` 안에서 충돌하는 확장이 있는지 확인**
```bash
cat ~/.gdbinit
```
GEF와 Pwndbg의 `source` 줄이 동시에 있다면 하나만 남기고 정리한다.

## 명령어/단축키
```gdb
version
set context-sections "regs disasm stack backtrace"
show context-sections
```
```bash
echo $TERM
cd ~/pwndbg && git pull && ./setup.sh
cat ~/.gdbinit
```

## 출력 해석
- `version` 출력에서 Pwndbg 버전이 GitHub의 최신 릴리스보다 한참 오래됐다면 재설치가 필요하다는 신호다.
- `context` 실행 중 Python `Traceback`이 보이면 이는 레이아웃 문제가 아니라 실제 코드 버그/버전 불일치이므로, 트레이스백 마지막 줄의 예외 메시지를 그대로 복사해 Pwndbg GitHub Issues에서 검색해본다.
- `\x1b[`로 시작하는 문자열이 그대로 보이면 100% 터미널의 ANSI 해석 문제이지 Pwndbg 자체의 버그가 아니다.

## 흔한 실수
- `git pull`만 하고 `./setup.sh`를 다시 안 돌리는 것 — Pwndbg 코드와 설치된 Python 의존성 버전이 어긋나는 가장 흔한 원인이다.
- 출력을 파일로 리다이렉트해놓고 왜 색깔이 깨지냐고 헷갈리는 것 — 리다이렉트된 파일에는 애초에 색깔이 나올 수 없다(터미널이 아니므로).
- GEF를 써보려고 설치했다가 지우지 않고 Pwndbg도 같이 켜놓아서 두 확장이 충돌하는 것을 못 알아채는 것.
- 터미널 창을 여러 개로 잔뜩 쪼개놓고 Pwndbg가 "고장났다"고 생각하는 것 — 실제로는 단순히 폭이 부족해서 레이아웃이 접힌 것뿐이다.

## 막혔을 때 다음 체크
- 애초에 명령어 자체가 하나도 안 먹는다면 → REV-0690 Pwndbg가 설치는 됐는데 명령어가 안 먹을 때
- `vmmap`/`telescope` 사용법 자체가 궁금하면 → REV-0193 Pwndbg context telescope vmmap
- GDB 자체의 기본 명령어가 궁금하면 → REV-0284 GDB 명령어 치트시트

## 미니 예제
```bash
$ cd ~/pwndbg && git pull
Already up to date.
$ gdb ./chall
pwndbg> context
Traceback (most recent call last):
  ...
  AttributeError: module 'gdb' has no attribute 'Breakpoint'
$ gdb --version
GNU gdb (Ubuntu 15.0.50) ...
$ cd ~/pwndbg && ./setup.sh
$ gdb ./chall
pwndbg> context
──────────────────────────────[ REGISTERS ]──────────────────────────────
 RAX  0x0
...
```
시스템 GDB가 업그레이드된 뒤 Pwndbg 코드와 API가 어긋나 `context`가 트레이스백을 냈지만, `./setup.sh`를 다시 실행해 재설치하자 정상 출력됐다.

## 관련 글
- REV-0690 — Pwndbg가 설치는 됐는데 명령어가 안 먹을 때
- REV-0193 — Pwndbg context telescope vmmap
- REV-0284 — GDB 명령어 치트시트

## 출처/검증
- Pwndbg의 GDB 버전 의존성과 재설치(`setup.sh`) 필요성: Pwndbg 공식 저장소(pwndbg/pwndbg) README 및 공식 문서(pwndbg.re) 기준.
- `context-sections` 설정을 통한 패널 구성 변경: Pwndbg 공식 문서의 설정(config) 옵션 목록 기준.
- ANSI 이스케이프 코드와 `TERM` 환경변수의 터미널 해석 동작: 일반적인 터미널 에뮬레이터 및 tmux 공식 문서 기준 (2026-09-08 검증).
