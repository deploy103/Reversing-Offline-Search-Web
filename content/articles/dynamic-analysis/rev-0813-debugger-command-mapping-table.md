---
id: REV-0813
title: "디버거별 명령어 대응표(GDB vs x64dbg vs WinDbg)"
slug: "rev-0813-debugger-command-mapping-table"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg, WinDbg]
keywords: ["gdb windbg 명령어 비교", "x64dbg windbg 단축키", "gdb break windbg bp", "디버거 명령어 대응표", "gdb step windbg t p"]
aliases: ["gdb x64dbg windbg 치트시트", "디버거 명령어 변환표", "다른 디버거로 갈아탈 때"]
symptom_keywords: ["gdb 명령을 windbg에서 뭐라고 치는지 모름", "x64dbg 단축키를 gdb 명령으로 옮기고 싶음", "windbg bp가 gdb의 뭐랑 같은지 모름", "디버거를 옮겼는데 명령어가 하나도 기억 안남"]
source_ids: ["SRC-GDB-DOCS", "SRC-X64DBG-DOCS", "SRC-WINDBG-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
GDB, x64dbg, WinDbg는 브레이크포인트 걸기/스텝 실행/메모리 보기 같은 핵심 동작을 모두 지원하지만 명령 이름과 문법이 셋 다 다르며, 이 표 하나로 "내가 늘 쓰던 도구의 그 명령이 다른 도구에서는 무엇인지" 바로 찾을 수 있다.

## 언제 검색해야 하나
- Linux ELF는 GDB로, Windows PE는 x64dbg나 WinDbg로 분석하다가 명령어가 헷갈릴 때
- 라이트업/문서가 자신이 안 쓰는 디버거 기준으로 적혀 있어서 자신의 도구 명령으로 바꿔야 할 때
- WinDbg를 처음 쓰는데 GDB의 `break`/`step`/`continue`에 대응하는 명령이 뭔지 급하게 찾을 때
- x64dbg의 F7/F8/F9 단축키가 다른 도구의 어떤 명령과 같은 동작인지 확인하고 싶을 때

## 핵심 개념
아래 표는 실전에서 가장 자주 쓰는 동작을 기준으로 세 도구의 명령을 나란히 정리한 것이다. x64dbg는 GUI 단축키가 기본이므로 단축키를 먼저, 괄호 안에 명령줄(커맨드 바) 입력용 명령을 함께 적었다.

| 동작 | GDB | x64dbg | WinDbg |
|---|---|---|---|
| 주소/함수에 브레이크포인트 | `break *ADDR` / `break FUNC` | `F2`(커서 위치) / (`bp ADDR`) | `bp ADDR` |
| 브레이크포인트 목록 | `info breakpoints` | Breakpoints 탭 | `bl` |
| 브레이크포인트 삭제 | `delete N` | 우클릭 삭제 / (`bpc ADDR`) | `bc N` |
| 브레이크포인트 활성화/비활성화 | `enable N` / `disable N` | (`bpe ADDR`) / (`bpd ADDR`) | `be N` / `bd N` |
| 조건부 브레이크포인트 | `condition N EXPR` | Edit breakpoint → Break condition | `bp ADDR "조건 스크립트"` |
| 프로그램 실행 시작 | `run` / `start` | `F9`(첫 진입점까지, 설정에 따라 다름) / (`run`) | `g` |
| 실행 재개(계속) | `continue` (`c`) | `F9` | `g` |
| 한 줄 소스 단위로 진입(step into) | `step` (`s`) | `F7` | `t` |
| 한 줄 소스 단위로 넘기기(step over) | `next` (`n`) | `F8` | `p` |
| 명령어 단위로 진입 | `stepi` (`si`) | `F7` | `t` |
| 명령어 단위로 넘기기 | `nexti` (`ni`) | `F8` | `p` |
| 현재 함수 끝까지 실행(step out) | `finish` | `Ctrl+F9`(Execute till return, `rtr`) | `gu` |
| 특정 위치까지 한 번에 실행 | `until *ADDR` / `advance FUNC` | 우클릭 → Run to Selection(`F4`) | `bp ADDR` 후 `g`, 또는 `pa ADDR` |
| 메모리 보기 | `x/NFU ADDR` | Dump 패널 / (`db`,`dw`,`dd`,`dq ADDR`) | `db`/`dw`/`dd`/`dq ADDR` |
| 레지스터 보기 | `info registers` / `p $rax` | Registers 패널 / (`r rax`로 설정) | `r` / `r rax` |
| 역참조 조건 워치포인트 | `watch EXPR` | 메모리 우클릭 → Breakpoint → Hardware, Access/Write | `ba w SIZE ADDR` |
| 디스어셈블 | `disassemble` | CPU/Disassembly 패널 | `u ADDR` |
| 콜스택(백트레이스) | `bt` | Call Stack 패널 | `k` |
| 지역 변수 보기 | `info locals` | (심볼 있을 때) Locals 패널 | `dv` |
| 프로세스 attach | `attach PID` | File → Attach | `.attach PID` |
| 프로세스 detach | `detach` | Debug → Detach | `.detach` |
| 디버깅 세션 재시작 | `run`(재실행) | Debug → Restart(`Ctrl+F2`) | `.restart` |
| 심볼/함수 검색 | `info functions REGEX` | Symbols 패널 / 검색창 | `x MODULE!PATTERN` |
| 메모리 값 검색 | `find` | Search for → 패턴 지정 | `s -a`/`s -b` |

## 화면/코드에서 보이는 징후
Linux 바이너리(ELF) 분석 라이트업에는 `(gdb)` 프롬프트가, Windows PE 분석 문서에는 x64dbg 스크린샷이나 WinDbg의 `0:000>` 프롬프트가 등장한다. 어느 쪽 문서를 보고 있는지에 따라 위 표의 어느 열을 참고할지가 정해진다.

## 가장 먼저 할 것
지금 실행하려는 동작(브레이크/스텝/메모리 확인 등)을 먼저 정하고, 위 표에서 그 행을 찾아 자신이 실제로 쓰는 디버거 열의 명령을 그대로 입력한다.

## 단계별 절차

**1) 원래 익숙한 디버거의 명령을 확인한다**
예: GDB에서 늘 쓰던 `break main; run; next; next`.

**2) 표에서 각 명령의 행을 찾는다**
`break` → "주소/함수에 브레이크포인트" 행, `run` → "프로그램 실행 시작" 행, `next` → "한 줄 소스 단위로 넘기기" 행.

**3) 대상 디버거 열의 명령/단축키로 치환한다**
WinDbg라면 `bp main`, `g`, `p`, `p` 순서가 된다.

**4) GUI 도구는 단축키 위치를 화면에서 직접 확인한다**
x64dbg는 F7/F8/F9가 상단 툴바 아이콘으로도 노출되어 있으므로, 단축키가 헷갈리면 툴바 아이콘에 마우스를 올려 툴팁으로 확인한다.

**5) 조건부 브레이크포인트처럼 문법 차이가 큰 항목은 별도 참조**
GDB `condition`/x64dbg Break condition/WinDbg `bp` 조건 스크립트는 문법 자체가 서로 다르므로, 각 도구 전용 문서(REV-0806, REV-0808)를 함께 확인한다.

## 명령어/단축키
```gdb
break / delete / condition / run / continue / step / next / stepi / nexti / finish / watch / bt / info registers / disassemble
```
```text
x64dbg: F2(브레이크포인트) F7(step into) F8(step over) F9(run/continue) Ctrl+F9(execute till return) F4(run to selection) Ctrl+F2(restart)
```
```text
WinDbg: bp / bc / bl / be / bd / g / t / p / gu / k / r / u / dv / .attach / .detach / .restart
```

## 출력 해석
세 도구 모두 "지금 실행이 멈춘 위치"를 알려주는 방식이 다르다. GDB는 멈추면 소스 줄과 함수명을 텍스트로 출력하고, x64dbg는 CPU 패널의 현재 명령어 줄에 화살표를 표시하며, WinDbg는 `Breakpoint N hit`류의 메시지 뒤에 현재 명령어 주소와 디스어셈블리 한 줄을 보여준다. 어느 도구든 "방금 멈췄다"는 신호 자체는 화면이 다시 그려지고 새 프롬프트가 뜨는 것으로 확인할 수 있다.

## 흔한 실수
- WinDbg의 `t`(trace, step into)를 GDB의 `t`(존재하지 않음, GDB의 step into는 `s`)와 같은 글자라고 착각하는 것 — 같은 알파벳이라도 도구마다 의미가 다르다.
- x64dbg의 `F7`/`F8`을 WinDbg의 `t`/`p`와 정확히 반대로 기억하는 것 — 표를 만들어 한 번 정리해두지 않으면 도구를 오갈 때마다 헷갈리기 쉽다.
- WinDbg `g`(go)가 GDB의 `run`과 `continue` 둘 다에 대응한다는 것을 모르고 "처음 실행"과 "재개"를 구분하는 별도 명령을 찾으려 하는 것 — WinDbg는 최초 실행도, 이후 재개도 모두 `g`다.
- x64dbg GUI 단축키만 알고 스크립트/커맨드 바에서 같은 동작을 어떻게 텍스트 명령으로 치는지 몰라 자동화(스크립트) 작성에서 막히는 것.

## 막혔을 때 다음 체크
- x64dbg 조건부 브레이크포인트 문법 자체가 궁금하면 → REV-0808 x64dbg 조건부 브레이크포인트 문법 참조.
- GDB의 watch/catch/tbreak 등 심화 명령이 궁금하면 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak).
- 레지스터/플래그 표시 명칭 차이가 궁금하면 → REV-0812 디버거별 레지스터/플래그 표시 명칭 대조표.

## 미니 예제
```text
목표: main 함수에 브레이크포인트를 걸고 실행한 뒤, 한 줄씩(호출은 넘기며) 세 번 진행하기

GDB    : break main → run → next → next → next
x64dbg : main에 F2 → F9 → F8 → F8 → F8
WinDbg : bp main → g → p → p → p
```
세 시퀀스 모두 동일한 디버깅 동작을 각자의 문법으로 표현한 것이다.

## 관련 글
- REV-0812 — 디버거별 레지스터/플래그 표시 명칭 대조표
- REV-0808 — x64dbg 조건부 브레이크포인트 문법 참조
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)

## 출처/검증
- GDB 명령(`break`/`delete`/`condition`/`run`/`continue`/`step`/`next`/`stepi`/`nexti`/`finish`/`until`/`advance`/`watch`/`x`/`info registers`/`disassemble`/`bt`/`info locals`/`attach`/`detach`/`find`): GDB 공식 온라인 매뉴얼("Debugging with GDB") 기준.
- x64dbg 명령/단축키(`bp`/`bpc`/`bpe`/`bpd`/`run`/`StepInto`(`sti`)/`StepOver`(`sto`)/`StepOut`(`rtr`)/F2·F7·F8·F9·Ctrl+F9 단축키): x64dbg 공식 문서(help.x64dbg.com) Breakpoint Control, Debug Control, GUI 메뉴 페이지 기준.
- WinDbg 명령(`bp`/`bc`/`bl`/`be`/`bd`/`g`/`t`/`p`/`gu`/`u`/`k`/`r`/`dv`/`.attach`/`.detach`/`.restart`/`s`): Microsoft 공식 WinDbg 명령 레퍼런스 문서 기준 (2026-09-09 조사).
