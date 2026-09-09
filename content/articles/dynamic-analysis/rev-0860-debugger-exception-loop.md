---
id: REV-0860
title: "디버거 안에서 예외가 계속 발생해서 진행이 안 될 때"
slug: "rev-0860-debugger-exception-loop"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg]
keywords:
  - exception pass to debuggee
  - 예외를 프로그램에 전달
  - SEH 예외
  - handle SIGSEGV
  - 예외가 계속 발생
  - first chance exception
symptom_keywords:
  - 실행하면 계속 예외 창이 뜸
  - F9 눌러도 계속 같은 곳에서 멈춤
  - continue 해도 계속 시그널이 뜸
  - 예외를 무시하고 진행하고 싶음
aliases:
  - 예외 반복 멈춤
  - first chance exception 계속 뜸
  - SIGSEGV 반복
  - 예외 통과시키는법
source_ids: ["SRC-X64DBG-DOCS", "SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
디버거는 기본적으로 프로그램 안에서 예외(SEH 예외, 시그널)가 발생하면 일단 멈추고 사용자에게 "이 예외를 프로그램에 그대로 전달할지, 아니면 디버거가 처리하고 끝낼지"를 물어보는데, 정상 동작의 일부로 예외를 던지고 받는 프로그램(특히 SEH 기반 안티디버깅이나 예외 기반 제어 흐름)은 이 예외를 계속 프로그램 쪽으로 "전달(pass)"해줘야만 실행이 정상적으로 이어진다.

## 언제 검색해야 하나
- x64dbg에서 `F9`(Run)를 눌러도 계속 똑같은 위치에서 "예외 발생" 메시지와 함께 멈출 때
- GDB에서 `continue`를 쳐도 매번 `Program received signal SIGSEGV`가 반복해서 뜨고 앞으로 진행이 안 될 때
- 프로그램이 SEH(Structured Exception Handling)를 이용해 정상적으로 예외를 던지고 자기 핸들러에서 받아 처리하는 구조인데, 디버거가 먼저 가로채서 멈추는 바람에 그 핸들러가 실행될 기회를 못 얻을 때
- "예외를 프로그램에 전달(pass exception to program)"이라는 옵션이 뭘 뜻하는지 모를 때

## 핵심 개념

### 디버거가 예외를 먼저 가로채는 이유
디버거는 대상 프로세스에 대해 예외 디버그 이벤트를 커널로부터 먼저 통지받는다(Windows의 디버그 이벤트, Linux의 ptrace stop). 이것이 "First-chance exception"이다. 이 시점에 디버거는 두 가지를 선택할 수 있다.
1. 예외를 프로그램의 예외 핸들러(SEH, `try/except`)나 시그널 핸들러에게 그대로 전달해서 프로그램이 원래 하려던 처리를 계속하게 한다.
2. 예외를 디버거가 가로챈 채로 멈춰 두고 사용자가 직접 조사하게 한다.

정상적으로 예외를 활용하는 프로그램(예: 0으로 나누기를 의도적으로 유발해 SEH 핸들러 안에서 특정 로직을 수행하는 안티디버깅/난독화 기법, REV-0539 참고)은 디버거가 예외를 계속 붙잡아 두면 그 핸들러가 실행되지 않으므로 프로그램 논리 자체가 앞으로 진행되지 않는다.

### x64dbg의 예외 처리 옵션
x64dbg는 `Options` → `Preferences` → `Exceptions` 탭에서 예외 코드별로 "무시하고 프로그램에 전달할지" 목록을 관리한다. 기본적으로 알려진 사용자 예외(0x406D1388 같은 디버거 이름 지정용 예외 등)는 자동으로 전달하도록 설정되어 있지만, `ACCESS_VIOLATION` 같은 예외는 기본적으로 디버거가 멈추도록 되어 있다. 실행창에서 예외가 뜰 때 `Shift+F9`(또는 "Pass exception to debuggee" 옵션이 붙은 실행 버튼)을 쓰면, 그 예외를 프로그램에 전달하면서 계속 실행한다.

### GDB의 시그널 처리(handle 명령)
GDB는 시그널마다 "정지할지(stop)", "출력할지(print)", "프로그램에 전달할지(pass)"를 각각 설정할 수 있다.
```
handle SIGSEGV nostop noprint pass
```
이렇게 설정하면 `SIGSEGV`가 발생해도 GDB가 멈추지 않고 곧바로 프로그램(및 그 프로그램이 등록한 시그널 핸들러)에 전달한다. 반대로 `nopass`를 쓰면 디버거가 시그널을 삼켜버려서 프로그램 쪽 핸들러가 실행되지 않는다.

### "계속 같은 곳에서 멈춘다"는 것의 의미
디버거가 예외 발생 지점에서 매번 똑같이 멈추는 것은 버그가 아니라, 아직 "이 예외를 프로그램에 전달"하는 선택을 하지 않았기 때문에 그 예외가 처리되지 못하고 다시 디버거로 돌아오는 것이다(pass하지 않고 그냥 다시 continue/run만 반복하면 같은 예외가 계속 재발생한다).

## 화면/코드에서 보이는 징후
- x64dbg 상태 표시줄에 "Access violation" 또는 사용자 정의 예외 코드가 반복적으로 뜨고, 같은 주소에서 멈춘다.
- GDB에서 `continue`를 칠 때마다 `Program received signal SIGSEGV, Segmentation fault.` 메시지가 계속 나온다.
- 코드 흐름상 `try/except`(SEH) 블록이나 `signal()`/`sigaction()` 등록 코드가 근처에 있는데, 그 핸들러 안쪽 코드가 전혀 실행되는 흔적이 없다.

## 가장 먼저 할 것
1. 이 예외가 프로그램 설계상 의도된 것인지(SEH/시그널 핸들러가 실제로 등록되어 있는지) 먼저 확인한다.
2. 의도된 것이라면, 그 예외를 디버거가 가로채지 말고 프로그램에 전달하도록 설정을 바꾼다.
3. 설정을 바꾼 뒤에도 같은 위치에서 멈춘다면, 이번엔 진짜 처리되지 않는 크래시(버그)로 보고 접근한다.

## 단계별 절차

**x64dbg**
1. 예외가 발생해 멈춘 상태에서, 실행 버튼 옆의 화살표(또는 단축키)로 "Pass exception to debuggee"가 적용된 실행을 선택한다(`Shift+F9`).
2. 여러 번 반복해서 나타나는 예외라면, `Options` → `Preferences` → `Exceptions`에서 해당 예외 코드를 "항상 전달" 목록에 추가해 매번 수동으로 선택하지 않게 한다.
3. 예외 전달 후 프로그램의 SEH 핸들러 코드에 브레이크포인트를 걸어(REV-0169) 그 핸들러가 실제로 실행되는지 확인한다.

**GDB / Pwndbg**
1. 현재 시그널 처리 설정을 확인한다.
   ```
   info signal SIGSEGV
   ```
2. 프로그램에 전달하도록 바꾼다.
   ```
   handle SIGSEGV nostop noprint pass
   ```
3. `continue`로 실행을 이어간다. 이제 `SIGSEGV`는 GDB를 멈추지 않고 프로그램의 시그널 핸들러(등록되어 있다면)로 바로 전달된다.
4. 특정 시그널이 발생하는 순간만 잡고 싶다면 `catch signal SIGSEGV`(REV-0642 참고)로 조건부로 잡는 방법도 있다.

## 명령어/단축키
- x64dbg: `Shift+F9`(예외를 프로그램에 전달하며 실행), `Options` → `Preferences` → `Exceptions`(예외 코드별 처리 규칙)
- GDB/Pwndbg: `handle SIG... [stop|nostop] [print|noprint] [pass|nopass]`, `info signal SIG...`, `catch signal SIG...`

## 출력 해석
- GDB `info signal SIGSEGV` 출력의 `Pass to program: No`는 현재 이 시그널이 프로그램에 전달되지 않고 있다는 뜻이므로, `pass`로 바꿔줘야 한다.
- x64dbg에서 예외를 전달한 뒤 프로그램이 그대로 죽는다면(핸들러가 없거나 핸들러가 다시 예외를 던진다면), 이는 프로그램 자체의 정상적인 크래시이지 디버거 설정 문제가 아니다.

## 흔한 실수
- 예외가 뜰 때마다 그냥 기본 "Run"만 눌러서(전달 없이) 예외를 디버거가 계속 삼키는 것 — 핸들러가 있는 프로그램이라면 반드시 "pass" 옵션으로 실행해야 한다.
- `handle SIGSEGV nostop noprint pass`를 걸어놓고 나서, 진짜 크래시(버그)가 나도 아무 메시지 없이 조용히 넘어가서 원인을 놓치는 것 — 분석이 끝나면 다시 `handle SIGSEGV stop print nopass`로 되돌리는 습관이 필요하다.
- SEH 기반 안티디버깅(REV-0539)에서 예외를 프로그램에 전달하지 않으면 핸들러 안의 "디버거가 없을 때만 taken되는 분기"가 항상 반대로 동작해서, 정상 실행 경로 자체를 오해하는 것.

## 막혔을 때 다음 체크
- 예외를 전달했는데도 핸들러가 실행되지 않는다면 → SEH 체인이나 시그널 등록 코드가 정말 존재하는지 정적 분석으로 다시 확인한다(REV-0134 SEH 기초).
- 이 예외가 안티디버깅 목적으로 보인다면 → REV-0871에서 원인을 좁히는 절차를 참고한다.
- 예외 발생 지점이 계속 똑같은 크래시라면 → REV-0859에서 설명한 JIT 팝업/크래시 분석 절차로 전환한다.

## 미니 예제
```
(gdb) run
Program received signal SIGSEGV, Segmentation fault.
0x0000000000401234 in check_value ()
(gdb) info signal SIGSEGV
Signal        Stop   Print   Pass to program   Description
SIGSEGV       Yes    Yes     No                Segmentation fault
(gdb) handle SIGSEGV nostop noprint pass
(gdb) continue
```
이후 `continue`부터는 `SIGSEGV`가 GDB를 멈추지 않고 프로그램의 시그널 핸들러로 바로 전달되어, 핸들러 안의 로직(예: 특정 값 세팅 후 원래 흐름 복귀)이 실제로 실행된다.

## 관련 글
- REV-0859 — Just-In-Time 디버거 팝업이 떠서 당황스러울 때
- REV-0871 — 안티디버깅 때문에 디버거에서 갑자기 종료될 때 원인 좁히기(실전)
- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가

## 출처/검증
- x64dbg 예외 처리 옵션(`Preferences` → `Exceptions`, 예외 전달)과 관련 실행 단축키: x64dbg 공식 문서(Introduction, Exceptions) 기준.
- GDB `handle` 명령과 `stop`/`print`/`pass` 옵션: GNU GDB 공식 매뉴얼 "Signals" 챕터 기준.
- 2026-09-09 검증.
