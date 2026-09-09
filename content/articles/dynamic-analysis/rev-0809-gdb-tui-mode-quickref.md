---
id: REV-0809
title: "GDB TUI 모드 빠른 참조"
slug: "rev-0809-gdb-tui-mode-quickref"
category: "dynamic-analysis"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb tui", "gdb tui enable", "gdb layout asm", "gdb layout regs", "gdb ctrl-x", "gdb 화면 분할 모드"]
aliases: ["gdb tui 모드", "gdb 화면 분할", "gdb layout 명령", "gdb tui 단축키"]
symptom_keywords: ["gdb tui 켜는법 모름", "gdb 화면이 깨짐", "gdb에서 소스코드랑 레지스터 같이 보고싶음", "gdb tui 창 전환 방법 모름", "gdb tui 끄는법"]
source_ids: ["SRC-GDB-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
GDB의 TUI(Text User Interface) 모드는 터미널 화면을 소스/어셈블리/레지스터/명령창으로 분할해서 보여주는 기능으로, `tui enable` 또는 `Ctrl-x a`로 켜고 `layout` 명령으로 어떤 창을 보여줄지 고르며 `Ctrl-x o`로 창 사이 포커스를 옮긴다.

## 언제 검색해야 하나
- 매번 `list`, `x/i $pc`를 따로 쳐서 소스/어셈블리를 확인하는 게 번거로울 때
- 레지스터 값이 바뀌는 걸 코드와 동시에 한 화면에서 보고 싶을 때
- TUI 화면이 깨져서 다시 정리하는 방법이 필요할 때
- TUI를 켰는데 스크롤/입력이 원하는 창에 안 먹혀서 창 포커스 전환법이 필요할 때

## 핵심 개념

### 켜기/끄기
```gdb
tui enable
tui disable
```
또는 단축키 `Ctrl-x a`(누른 채로 x, 그다음 a)로 TUI 모드를 켜고 끄는 것을 토글할 수 있다.

### layout — 어떤 창을 보여줄지 선택
```gdb
layout src      # 소스 코드 창만
layout asm      # 어셈블리 창만
layout split    # 소스 + 어셈블리 동시에
layout regs     # 현재 layout(src 또는 asm)에 레지스터 창 추가
layout next     # 다음 레이아웃으로 순환
layout prev     # 이전 레이아웃으로 순환
```
`layout src`/`layout asm`을 먼저 고른 상태에서 `layout regs`를 추가로 실행하면 레지스터 창까지 함께 보이는 3분할 화면이 된다.

### focus — 창 포커스 전환
```gdb
focus next
focus prev
focus src
focus asm
focus regs
focus split
```
TUI 상태에서 방향키/스크롤이 어느 창에 적용될지는 현재 포커스된 창에 따라 달라진다. 명령창(gdb 프롬프트)이 아닌 다른 창을 스크롤하고 싶을 때 `focus` 또는 아래의 `Ctrl-x o` 단축키로 옮긴다.

### 레지스터 창 그룹 전환
```gdb
tui reg general
tui reg system
tui reg float
tui reg next     # 다음 레지스터 그룹으로 순환
```
레지스터 창이 열려 있을 때 어떤 레지스터 그룹(범용/시스템/부동소수점)을 보여줄지 바꿀 수 있다.

### 창 크기 조절
```gdb
winheight SRC +5
winheight SRC -5
```
`winheight`(축약 `wh`)로 특정 창의 세로 높이를 늘리거나 줄인다.

### 화면이 깨졌을 때 새로고침
```gdb
Ctrl-l
```
TUI 화면이 다른 출력과 뒤섞여 깨졌을 때 `Ctrl-l`(refresh)로 다시 그린다.

## 화면/코드에서 보이는 징후
TUI를 켜면 터미널이 위쪽 소스/어셈블리/레지스터 창과 아래쪽 GDB 명령 프롬프트 창으로 나뉘고, 현재 실행 중인 줄 앞에 `B+>` 같은 브레이크포인트/현재 위치 표시가 붙는다. `next`, `step`, `continue` 등을 칠 때마다 위쪽 창들이 자동으로 갱신된다.

## 가장 먼저 할 것
브레이크포인트를 걸고 `run`으로 멈춘 상태에서 `layout regs`부터 켜본다. 소스가 없는 스트립 바이너리라면 `layout asm` 뒤에 `layout regs`를 추가하는 조합이 가장 실용적이다.

## 단계별 절차

**1) 프로그램을 멈춘 상태 만들기**
```gdb
break main
run
```

**2) TUI 켜고 어셈블리+레지스터 보기**
```gdb
layout asm
layout regs
```

**3) 코드 실행하며 관찰**
```gdb
stepi
stepi
```
한 줄씩 실행할 때마다 위쪽 어셈블리/레지스터 창이 자동으로 갱신된다.

**4) 다른 창으로 포커스 옮겨서 스크롤**
```gdb
Ctrl-x o
```
포커스가 명령창에서 어셈블리 창으로 옮겨지면 방향키로 코드를 스크롤할 수 있다. 다시 `Ctrl-x o`를 누르면 다음 창으로 넘어간다.

**5) 화면이 깨지면 새로고침**
```gdb
Ctrl-l
```

**6) 다 봤으면 끄기**
```gdb
tui disable
```

## 명령어/단축키
```gdb
tui enable / tui disable       # TUI 모드 켜기/끄기
Ctrl-x a                        # TUI 모드 토글
layout src / asm / split / regs / next / prev
focus src / asm / regs / split / next / prev
Ctrl-x o                        # 창 포커스 다음으로 전환
Ctrl-x 2                        # 창 레이아웃(1개/2개) 전환
Ctrl-l                          # 화면 새로고침
tui reg general / system / float / next
winheight WIN +N / -N           # 창 높이 조절(축약 wh)
```

## 출력 해석
소스 창에서는 줄 번호 앞에 브레이크포인트가 걸린 줄이면 `B+`, 현재 실행 위치면 `>` 표시가 붙는다. 어셈블리 창에서는 현재 `$pc`가 가리키는 명령어 줄 앞에 화살표류 표시가 붙어 지금 실행될 명령어를 바로 알 수 있다. 레지스터 창에서는 직전 실행으로 값이 바뀐 레지스터가 강조(반전/색상)되어 어떤 레지스터가 방금 바뀌었는지 한눈에 보인다.

## 흔한 실수
- `layout regs`만 단독으로 실행하고 소스/어셈블리 창이 안 보인다고 헷갈리는 것 — `regs`는 기존 `src`/`asm` 레이아웃에 레지스터 창을 "추가"하는 개념이라, 먼저 `layout src` 또는 `layout asm`을 실행해둬야 한다.
- TUI 상태에서 방향키를 눌렀는데 코드가 안 움직이고 명령어 히스토리만 바뀌는 것 — 포커스가 아직 명령창에 있기 때문이며, `Ctrl-x o`로 포커스를 옮겨야 한다.
- 터미널 크기가 너무 작은 상태에서 TUI를 켜서 화면이 깨지는 것 — 터미널 창을 충분히 키우거나 `winheight`로 각 창 크기를 조절해야 한다.
- Pwndbg의 `context` 화면과 GDB TUI를 동시에 켜서 화면이 서로 겹치거나 중복 출력되는 것 — 둘 다 "레지스터/코드 자동 표시" 기능이라 보통 하나만 골라 쓰는 것이 깔끔하다.

## 막혔을 때 다음 체크
- TUI 대신 Pwndbg의 자동 `context` 화면으로 비슷한 정보를 보고 싶다면 → REV-0193 Pwndbg context telescope vmmap.
- 한 줄씩 실행하는 기본 명령(`stepi`/`nexti`/`continue`)이 헷갈리면 → REV-0187 GDB stepi nexti continue.
- 레지스터/플래그를 텍스트로만 확인하는 법이 궁금하면 → REV-0188 GDB info registers와 flags 확인.

## 미니 예제
```gdb
(gdb) break check_password
(gdb) run
(gdb) layout asm
(gdb) layout regs
(gdb) stepi
(gdb) Ctrl-x o
```
`check_password`에서 멈춘 뒤 어셈블리+레지스터 2분할 화면을 띄우고, `stepi`로 한 줄씩 실행하며 레지스터 창에서 값이 바뀌는 것을 확인하고, `Ctrl-x o`로 포커스를 어셈블리 창으로 옮겨 스크롤해보는 전형적인 흐름이다.

## 관련 글
- REV-0193 — Pwndbg context telescope vmmap
- REV-0187 — GDB stepi nexti continue
- REV-0188 — GDB info registers와 flags 확인
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)

## 출처/검증
- `tui enable`/`tui disable`/`Ctrl-x a`/`layout`/`focus`/`Ctrl-x o`/`Ctrl-l`/`tui reg`/`winheight` 명령과 단축키, 레이아웃별 창 구성: GDB 공식 온라인 매뉴얼("Debugging with GDB") "TUI Commands" 및 "TUI Configuration" 챕터 기준 (2026-09-09 검증).
