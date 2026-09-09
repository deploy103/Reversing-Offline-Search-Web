---
id: REV-0824
title: "멀티스레드 프로그램에서 특정 스레드만 멈추는 법"
slug: "rev-0824-thread-specific-breakpoint"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords: ["스레드별 브레이크포인트", "GDB break thread", "x64dbg TID 조건", "scheduler-locking", "특정 스레드만 멈추기", "thread-specific breakpoint"]
aliases: ["스레드 지정 브레이크포인트", "TID 조건부 브레이크포인트", "특정 스레드만 디버깅", "멀티스레드 브레이크포인트 필터링"]
symptom_keywords: ["여러 스레드가 같은 함수를 호출해서 브레이크포인트가 너무 자주 걸림", "관심 있는 스레드만 멈추고 싶음", "다른 스레드 때문에 원하는 스레드를 놓침", "스레드 ID로 브레이크포인트를 걸고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
여러 스레드가 같은 함수를 공유해서 호출할 때는 무조건 걸리는 일반 브레이크포인트 대신, GDB의 `break LOCATION thread N` / `condition N $_thread==2`나 x64dbg의 조건부 브레이크포인트에 TID 비교식을 넣어서 원하는 스레드가 그 위치를 지날 때만 멈추게 만들 수 있다.

## 언제 검색해야 하나
- 워커 스레드 여러 개가 동일한 함수(`process_item` 등)를 병렬로 호출해서, 관심 있는 한 스레드의 흐름만 보고 싶은데 다른 스레드에서도 계속 브레이크포인트가 걸릴 때
- 특정 TID(예: 메인 스레드가 아니라 두 번째로 생성된 워커 스레드)에서만 일어나는 버그나 로직을 추적하고 싶을 때
- 브레이크포인트를 걸어놓고 F9/`continue`를 스무 번씩 눌러야 원하는 스레드 차례가 오는 게 비효율적이라고 느껴질 때
- 스레드마다 다른 인자를 처리하는 코드에서, 그 중 하나의 인자 값으로 실행되는 스레드만 골라서 멈추고 싶을 때(예: 두 번째 워커 스레드가 처리하는 데이터만 보고 싶음)

## 핵심 개념

### "이 스레드일 때만" 조건을 브레이크포인트에 거는 두 가지 방법
1. **디버거가 기본 제공하는 스레드 필터 문법**을 쓴다. GDB는 브레이크포인트를 걸 때 `thread N`을 붙이면 그 스레드 번호에서 실행될 때만 멈춘다. `condition` 명령으로 `$_thread`라는 GDB 내장 변수(현재 실행 중인 스레드 번호)를 비교식에 넣을 수도 있다.
2. **범용 조건부 브레이크포인트에 TID/스레드 식별 표현식을 직접 넣는다.** x64dbg에는 GDB의 `thread N` 같은 전용 문법은 없지만, 조건부 브레이크포인트(REV-0183)의 Break condition 란에 현재 스레드 ID를 참조하는 표현식을 넣어 같은 효과를 낼 수 있다(x64dbg는 TID를 직접 노출하는 변수가 버전에 따라 다르므로, 우선 Threads 탭에서 원하는 스레드의 TID를 확인한 뒤 스크립트/조건식으로 비교하는 방식이 안전하다).

### GDB 스레드 번호(Thread ID) vs 운영체제 TID
GDB가 말하는 "스레드 번호"(`info threads`에 나오는 왼쪽 숫자, 예: `2`)는 GDB 내부에서 붙인 순번이고, 실제 OS의 TID(LWP 번호, `info threads` 출력의 `Thread 0x7ffff... (LWP 12345)` 부분)와는 다른 값이다. `break LOCATION thread 2`처럼 쓸 때는 GDB 번호(2)를 써야 하며, OS TID(12345)를 넣으면 안 된다. 이 둘을 헷갈리는 것이 가장 흔한 실수다.

### scheduler-locking으로 "지금 멈춘 스레드만 계속 실행"
`set scheduler-locking on`을 켜면 `step`/`next` 등으로 한 스레드만 진행시키는 동안 다른 스레드는 멈춰 있는다(기본값은 `replay` 또는 `off`로, step 중에도 다른 스레드가 스케줄링될 수 있다). 특정 스레드의 흐름을 다른 스레드 개입 없이 한 줄씩 추적하고 싶을 때 필수적인 옵션이다.

### 왜 조건부보다 우선 스레드 필터가 나은가
조건부 브레이크포인트(REV-0183, REV-0824의 표현식 방식)는 매번 브레이크포인트가 걸릴 때마다 조건식을 평가해야 하므로 스레드가 아주 많고 호출 빈도가 높으면 느려질 수 있다. GDB의 `thread N` 필터는 디버거 레벨에서 더 저수준으로 걸러주므로 대체로 더 빠르고 명확하다. 가능하면 전용 문법을 우선 쓰고, 전용 문법이 없는 도구(x64dbg 등)에서만 조건식으로 우회한다.

## 화면/코드에서 보이는 징후
- 브레이크포인트를 하나 걸었는데 로그/Hit Count가 스레드 개수만큼 빠르게 누적됨
- GDB `info threads` 결과에 여러 줄(예: `1`, `2`, `3`)이 있고, 그 중 특정 번호에서만 문제가 재현됨
- x64dbg Threads 탭에서 TID별로 서로 다른 Start Address(콜백 함수)가 보여서 "이건 워커 스레드, 이건 로거 스레드"처럼 역할이 나뉘어 있음이 짐작될 때

## 가장 먼저 할 것
GDB `info threads` 또는 x64dbg Threads 탭을 열어, 관심 있는 로직을 실행하는 스레드가 몇 번인지(GDB는 내부 번호, x64dbg는 TID) 먼저 파악한다. 이때 각 스레드의 Start Address를 IDA/Ghidra의 함수 이름과 대조하면 "이 스레드가 어떤 콜백을 실행 중인지" 바로 알 수 있다.

## 단계별 절차
### GDB
1. `info threads`로 전체 스레드 목록과 현재 실행 위치 확인
2. 대상 스레드 번호(예: 2)를 확인한 뒤 `break validate_input thread 2`처럼 위치와 스레드 번호를 함께 지정
3. 이미 걸어놓은 브레이크포인트에 나중에 조건을 추가하려면 `condition 1 $_thread==2`
4. 필요하면 `set scheduler-locking on`으로 이 스레드만 단독으로 스텝 실행되게 고정
5. `continue` 또는 `run` 후 원하는 스레드에서만 멈추는지 확인

### x64dbg
1. Threads 탭에서 대상 스레드의 TID 확인(예: `5200`)
2. 대상 위치에 일반 브레이크포인트를 건 뒤 우클릭 → Edit breakpoint(또는 Breakpoints 탭에서 편집)
3. Break condition에 현재 스레드 정보를 비교하는 표현식을 넣거나, x64dbg 스크립트 탭(REV-0814, 예정)에서 `bp` 이벤트 핸들러로 `TID`를 비교하는 조건부 로직을 작성
4. 조건이 안 맞아 멈추지 않은 히트는 로그(Log condition)로만 남기고 실제 정지는 대상 TID일 때만 발생하게 구성

## 명령어/단축키
GDB(Linux):
```
info threads
break validate_input thread 2
condition 1 $_thread==2
set scheduler-locking on
set scheduler-locking off
thread 2
```
x64dbg(Windows):
```
Threads 탭에서 TID 확인
bp validate_input
Edit breakpoint → Break condition
```

## 출력 해석
- GDB `break LOCATION thread N`으로 건 브레이크포인트는 `info breakpoints`에서 `stop only in thread N`이라는 문구로 표시되어, 나중에 다시 확인할 때도 조건이 걸려 있음을 바로 알 수 있다.
- `set scheduler-locking on` 상태에서 `next`를 눌렀는데도 다른 스레드가 실행된 흔적(다른 스레드가 만든 출력 등)이 보인다면, 커널/런타임 수준에서 이미 다른 스레드가 스케줄링된 상태였을 수 있으니 `info threads`로 각 스레드 상태를 다시 확인해야 한다.

## 흔한 실수
- GDB의 스레드 번호(내부 순번)와 OS TID(LWP 번호)를 혼동해서 `thread 12345`처럼 잘못된 값을 조건에 넣는 것
- `scheduler-locking`을 켜지 않은 채 특정 스레드만 스텝 실행하려다가, 다른 스레드가 끼어들어 예상과 다른 상태가 되는 것
- 스레드 필터 없이 조건부 표현식만으로 스레드를 구분하려다가, x64dbg/GDB 버전에 따라 원하는 스레드 식별 변수가 없어서 결국 못 거르는 것 — 이럴 땐 REV-0823에서 설명한 스레드 목록으로 먼저 TID/Start Address를 확실히 구분해두는 사전 작업이 필요
- 스레드 지정 브레이크포인트를 걸어놓고, 정작 프로그램을 재시작하면 스레드 번호/TID가 매번 달라진다는 사실을 잊고 예전 번호를 그대로 재사용하는 것

## 막혔을 때 다음 체크
- 애초에 프로세스/스레드 목록 자체가 헷갈리면 → REV-0823 여러 프로세스/스레드를 디버거로 동시에 다루는 법
- 일반적인 조건부 브레이크포인트 문법이 기억 안 나면 → REV-0183 x64dbg 조건부 Breakpoint 기초
- GDB에서 조건부 브레이크포인트를 더 깊이 알고 싶다면 → REV-0819 GDB에서 조건부 브레이크포인트(condition) 활용하기 (예정)
- pthread 생성 시점의 인자(콜백 함수 포인터)를 먼저 확인하고 싶다면 → REV-0638 libc 함수 사전: pthread_create 기초

## 미니 예제
```
(gdb) info threads
  Id   Target Id                         Frame
  1    Thread 0x7ffff7fc0740 (LWP 9001)  main () at chall.c:20
* 2    Thread 0x7ffff6f9e700 (LWP 9002)  worker (arg=0x1) at chall.c:42
  3    Thread 0x7ffff679d700 (LWP 9003)  worker (arg=0x2) at chall.c:42

(gdb) break validate_input thread 2
Breakpoint 1 at 0x4011a0: file chall.c, line 55, thread 2.
(gdb) continue
Breakpoint 1, validate_input (buf=...) at chall.c:55
```
스레드 3에서 `validate_input`이 여러 번 호출되어도 멈추지 않고, 스레드 2가 그 지점을 지날 때만 정확히 멈춘 것을 확인할 수 있다.

## 관련 글
- REV-0823 — 여러 프로세스/스레드를 디버거로 동시에 다루는 법
- REV-0183 — x64dbg 조건부 Breakpoint 기초
- REV-0638 — libc 함수 사전: pthread_create 기초
- REV-0819 — GDB에서 조건부 브레이크포인트(condition) 활용하기
- REV-0617 — 실행마다 API 호출 순서가 달라 보일 때(멀티스레드)

## 출처/검증
- GDB `break LOCATION thread N`, `condition`, `$_thread`, `set scheduler-locking` 명령: GNU GDB 공식 매뉴얼(Debugging with GDB) 기준.
- GDB 스레드 번호와 OS LWP/TID의 구분: GDB 공식 문서의 "Thread-Specific Breakpoints" 절 기준.
- x64dbg의 스레드별 조건부 제어 방식은 전용 문법이 없어 조건식/스크립트로 우회한다는 점은 x64dbg 공식 GitHub Wiki 및 커뮤니티 문서 기준 (2026-09-09 검증).
