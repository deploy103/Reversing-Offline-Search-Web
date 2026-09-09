---
id: REV-0852
title: "함수 반환 직후로 브레이크포인트를 옮기고 싶은데 위치를 못 찾을 때"
slug: "rev-0852-cant-find-address-right-after-return"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg]
keywords: ["함수 반환 직후 브레이크포인트", "call 다음 주소", "finish 다음 주소", "리턴 직후 위치"]
aliases: ["함수 리턴 후 위치를 못찾음", "call 다음 명령어 주소 찾기", "return address 다음 지점"]
symptom_keywords: ["함수가 끝난 다음 어디로 가는지 모르겠다", "call 다음 줄이 안 보인다", "여러 군데서 호출되어 위치를 못 정한다", "인라인되어 ret이 안 보인다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
"함수가 끝난 직후"는 함수 안의 고정된 주소가 아니라 **그 함수를 호출한 지점(CALL 명령어) 바로 다음 명령어 주소**이므로, 함수가 여러 곳에서 호출되면 "반환 직후 위치"도 여러 개 존재한다 — 하나를 정확히 찍고 싶다면 `finish`로 실행 중에 자동으로 도달하거나, 콜스택에서 리턴 주소를 직접 읽어 그 주소에 걸어야 한다.

## 언제 검색해야 하나
- 어떤 함수가 리턴한 직후에 멈춰서 반환값이 레지스터에 어떻게 쓰이는지 보고 싶은데, 어느 주소에 브레이크포인트를 걸어야 할지 모를 때
- 같은 함수가 여러 위치에서 호출돼서 "반환 직후"가 한 곳이 아니라 헷갈릴 때
- 함수가 인라인되거나 최적화되어 명확한 `ret` 명령어나 `call` 지점을 디스어셈블리에서 못 찾을 때
- 예외/롱점프(`setjmp`/`longjmp`, SEH)로 정상적인 `ret` 경로를 안 타고 함수가 끝나는 경우

## 핵심 개념

### "반환 직후"는 호출자 쪽 주소다
함수 자체에는 "함수가 끝난 뒤의 위치"라는 개념이 없다. `ret` 명령은 스택에 저장된 리턴 주소로 점프할 뿐이고, 그 리턴 주소는 **그 함수를 호출한 `call` 명령어의 바로 다음 주소**다. 따라서 "반환 직후에 멈추고 싶다"는 요청은 실제로는 "이 함수를 호출한 그 특정 `call` 다음 주소에 멈추고 싶다"는 뜻으로 바꿔 생각해야 한다.

### 함수가 여러 곳에서 호출되면 "반환 직후"도 여러 곳
`strcmp`처럼 여러 지점에서 호출되는 함수라면, 그 함수의 "반환 직후"는 호출한 지점 수만큼 존재한다. 특정 한 번의 호출만 보고 싶다면 그 호출부(call site) 주소를 콜스택에서 확인해서 그 주소 하나에만 걸어야 하며, 함수 자체에 건 브레이크포인트로는 구분할 수 없다.

### finish는 "지금 실행 중인 그 함수 호출"의 리턴을 자동으로 찾아준다
주소를 몰라도 되는 가장 쉬운 방법은, 함수 안에서 멈춘 상태에서 `finish`(GDB) 또는 "Execute till return"(x64dbg에서 `Ctrl+F9`)을 쓰는 것이다. 이러면 GDB/x64dbg가 현재 스택 프레임의 리턴 주소를 자동으로 계산해 그 자리에 임시 브레이크포인트를 걸고 실행해준다 — 수동으로 주소를 찾을 필요가 없다.

### 인라인/꼬리 호출(tail call)이면 명시적인 call/ret이 없을 수 있다
컴파일러가 함수를 인라인시켰다면 애초에 `call` 명령어 자체가 존재하지 않아 "반환 직후"라는 개념이 사라진다. 꼬리 호출 최적화(tail call)의 경우 `call` 대신 `jmp`로 대체되어 있어 콜스택에 프레임이 하나 덜 보이고, `finish`가 예상과 다른 곳에서 멈추거나 "선택한 스택 프레임보다 바깥쪽 프레임이 없습니다" 같은 에러를 낼 수 있다.

## 화면/코드에서 보이는 징후
- 디스어셈블리에서 대상 함수를 호출하는 `call FUNC` 명령어가 여러 군데 보임
- `finish`를 썼는데 "Run till exit from #0 FUNC" 이후 예상과 다른 위치에서 멈춤(꼬리 호출/인라인 의심)
- x64dbg에서 함수 안에 진입했는데 Call Stack 창에 리턴 주소가 안 보이거나 이상한 값으로 보임(스택 손상 또는 프레임 포인터 생략 최적화)

## 가장 먼저 할 것
함수 안에서 이미 멈춰 있는 상태라면 주소를 직접 찾으려 하지 말고 우선 `finish`(GDB) / `Ctrl+F9`(x64dbg)부터 시도한다. 자동으로 올바른 리턴 지점까지 실행해준다.

## 단계별 절차

**1) 함수 안에서 멈춘 상태라면 finish로 자동 이동**
```gdb
(gdb) finish
Run till exit from #0  check_password (input=...) at chall.c:20
0x0000000000401530 in main () at chall.c:75
75      if (check_password(argv[1])) {
Value returned is $1 = 0
```
이 위치(`0x401530`)가 바로 "이번 호출"의 반환 직후 주소다.

**2) 특정 호출부만 골라서 걸고 싶다면 콜스택에서 리턴 주소 확인**
```gdb
(gdb) backtrace
#0  check_password (input=0x7fffffffe420 "test") at chall.c:20
#1  0x0000000000401530 in main () at chall.c:75
```
`#1` 줄의 주소(`0x401530`)가 리턴 주소다. 다음 실행부터는 이 주소에 직접 브레이크포인트를 건다.
```gdb
(gdb) break *0x401530
```

**3) 여러 호출부 중 하나만 특정하고 싶다면 디스어셈블리로 call 지점 나열**
```gdb
(gdb) disassemble main
...
0x0000000000401520 <+80>:  call   0x401400 <check_password>
0x0000000000401525 <+85>:  mov    [rbp-0x4],eax
...
```
`call` 다음 명령어 주소(`0x401525`)가 바로 그 호출의 반환 직후 위치다.

**4) x64dbg에서는 Execute till return 사용**
CPU 창에서 함수 안에 있을 때 `Ctrl+F9`를 누르면 x64dbg가 현재 프레임의 `ret`을 자동으로 찾아 그 직후까지 실행한다.

**5) 인라인/꼬리 호출로 자동 탐색이 안 되면 프레임 포인터 없이 스택에서 직접 리턴 주소 추정**
```gdb
(gdb) x/4gx $rsp
```
스택 최상단 근처 값 중 코드 세그먼트 범위(바이너리 로드 주소 범위) 안에 있는 값이 리턴 주소일 가능성이 높다. `info proc mappings`(GDB)로 코드 영역 범위를 먼저 확인해두면 구분이 쉽다.

## 명령어/단축키
```gdb
(gdb) finish
(gdb) backtrace / bt
(gdb) disassemble FUNC
(gdb) break *ADDRESS
(gdb) x/4gx $rsp
(gdb) info proc mappings
```
```
x64dbg: Ctrl+F9 (Execute till return), Call Stack 창, Find References to call FUNC
```

## 출력 해석
- `finish` 출력의 두 번째 줄(`0x... in main () at chall.c:75`)이 바로 반환 직후 위치다. 이 주소를 그대로 다음 브레이크포인트 주소로 재사용할 수 있다.
- `backtrace`에서 `#1` 프레임의 주소가 리턴 주소다. 이 값은 항상 어떤 `call` 명령어의 "다음" 주소와 정확히 일치한다.
- `Value returned is $1 = ...`는 반환값이므로, 반환 직후 위치를 찾는 김에 반환값도 같이 확인할 수 있다(REV-0176 참고).
- 인라인/꼬리 호출로 프레임이 예상과 다르면 `disassemble`로 실제 `call`/`jmp` 명령을 직접 확인해야 한다.

## 흔한 실수
- 함수의 "끝(ret 명령어)" 자체에 브레이크포인트를 걸고 "반환 직후"라고 착각하는 것 — 그건 아직 리턴하기 "직전"이며, 진짜 반환 직후는 호출자 쪽 주소다.
- 여러 호출부가 있는 함수에 `break FUNC`만 걸어놓고 `finish`를 쓰면서, 어느 호출인지 구분 안 하고 뒤섞어서 분석하는 것.
- 인라인된 함수인데도 원본 소스 기준으로 "함수가 끝나는 지점"을 디스어셈블리에서 찾으려다 실패하는 것 — 애초에 별도의 `call`이 존재하지 않는지 먼저 확인해야 한다.
- x86 32비트 `stdcall`/`cdecl`처럼 반환 후 스택 정리(`add esp, N`)가 별도 명령으로 붙는 경우, 그 정리 명령까지 지나야 스택이 완전히 정상화된다는 것을 놓치는 것.

## 막혔을 때 다음 체크
- 반환값 자체를 확인하는 절차가 궁금하다면 → REV-0176 CALL 직후 반환값 확인하는 법.
- 함수를 빠져나오는 절차(Run Until Return) 기본 개념이 헷갈린다면 → REV-0171 Run Until Return과 함수 빠져나오기.
- 호출 직전 인자 확인이 필요하다면 → REV-0175 CALL 직전 함수 인자 확인하는 법.

## 미니 예제
```gdb
(gdb) break check_password
(gdb) run
(gdb) finish
Run till exit from #0  check_password (input=0x7fffffffe420 "test") at chall.c:20
0x0000000000401530 in main () at chall.c:75
75      if (check_password(argv[1])) {
Value returned is $1 = 0
(gdb) break *0x401530
Breakpoint 2 at 0x401530: file chall.c, line 75.
```
`finish`로 한 번 자동 이동해서 정확한 리턴 주소(`0x401530`)를 확인한 뒤, 그 주소를 그대로 다음 실행부터 쓸 고정 브레이크포인트로 등록했다.

## 관련 글
- REV-0176 — CALL 직후 반환값 확인하는 법
- REV-0171 — Run Until Return과 함수 빠져나오기
- REV-0175 — CALL 직전 함수 인자 확인하는 법

## 출처/검증
- `finish`/Run Until Return 동작과 콜스택 리턴 주소 계산 방식: GDB 공식 매뉴얼 "Continuing and Stepping" 챕터 기준.
- x86-64 호출 규약에서 `call`이 리턴 주소를 스택에 push하는 동작과 `ret`의 관계: System V AMD64 ABI 문서 기준 (2026-09-09 검증).
