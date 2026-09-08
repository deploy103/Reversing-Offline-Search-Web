---
id: REV-0431
title: "CMPXCHG: 비교 후 교환(원자적 연산 개념)"
slug: "rev-0431-cmpxchg"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - CMPXCHG
  - compare and exchange
  - compare-and-swap
  - CAS
  - 비교 후 교환
  - cmpxchg 명령어
  - lock cmpxchg
  - InterlockedCompareExchange
  - compare_exchange_strong
  - compare_exchange_weak
  - CMPXCHG8B
  - CMPXCHG16B
  - lock-free
aliases:
  - cmpxchg가 뭔가요
  - cmpxchg 명령
  - lock cmpxchg가 뭐임
  - compare and swap 어셈블리
  - cas 루프
symptom_keywords:
  - lock cmpxchg가 뭔지 모르겠음
  - compare_exchange 어셈블리
  - InterlockedCompareExchange 어셈블리
  - 스핀 재시도 루프가 뭔지 모르겠음
  - cas 실패시 재시도 루프
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CMPXCHG dst, src`는 "누산기(AL/AX/EAX/RAX)와 목적지를 비교해서 같으면 소스 값으로 교체하고, 다르면 목적지의 실제 값을 누산기로 가져오는" 명령으로, `LOCK` 프리픽스를 붙인 `lock cmpxchg`는 락 없는(lock-free) 자료구조와 원자적 연산(CAS, Compare-And-Swap)을 구현하는 핵심 building block이다.

## 언제 검색해야 하나
- `lock cmpxchg`가 반복문(재시도 루프) 안에서 쓰이는 코드를 만났을 때
- C++ `std::atomic::compare_exchange_strong`/`compare_exchange_weak`, Win32 `InterlockedCompareExchange`가 실제로 어떤 어셈블리로 컴파일되는지 궁금할 때
- 스핀락, 락 없는 스택/큐, 뮤텍스 내부 구현을 리버싱하고 있을 때

## 핵심 개념

### CMPXCHG가 실제로 하는 일
`CMPXCHG dst, src`는 크기에 맞는 고정 누산기 레지스터(8비트=AL, 16비트=AX, 32비트=EAX, 64비트=RAX)를 암묵적인 "기대값(expected)"으로 사용한다.
```
IF 누산기 == dst THEN
    ZF = 1
    dst = src              ; 교환 성공
ELSE
    ZF = 0
    누산기 = dst            ; 교환 실패, dst의 실제 값을 누산기로 반환
```
즉 "누산기에 넣어둔 예상 값과 목적지의 현재 값이 같을 때만 목적지를 새 값(src)으로 바꾼다"는 조건부 교환이다. 이것이 바로 CAS(Compare-And-Swap)의 하드웨어 구현이다.

### Intel 문법과 오퍼랜드
```
CMPXCHG r/m8,  r8      ; 누산기 = AL
CMPXCHG r/m16, r16      ; 누산기 = AX
CMPXCHG r/m32, r32      ; 누산기 = EAX
CMPXCHG r/m64, r64      ; 누산기 = RAX
```
목적지(dst)는 레지스터 또는 메모리, 소스(src)는 레지스터다. **누산기(AL/AX/EAX/RAX)는 오퍼랜드로 적혀 있지 않지만 암묵적으로 "기대하는 이전 값"을 담는 역할을 한다** — 반드시 실행 전에 미리 로드해 둬야 한다.

### 방향
비교는 "누산기 vs dst"로 이뤄지고(내부적으로 `dst - 누산기` 뺄셈), 교환이 일어나면 `dst = src`, 실패하면 `누산기 = dst`로 값이 되돌아온다. 소스(`src`) 자체는 절대 변하지 않는다.

### 플래그 변화
`ZF`는 비교 결과에 따라 세팅된다 — **`ZF=1`이면 교환이 성공(같았음)했다는 뜻**이지 실패가 아니다. 나머지 CF, OF, SF, AF, PF는 `dst - 누산기` 뺄셈을 수행한 것처럼 세팅된다.

### 확장판: CMPXCHG8B / CMPXCHG16B
32비트/64비트보다 더 넓은 폭(64비트 또는 128비트)을 한 번에 원자적으로 비교/교환해야 할 때 쓰는 명령이다. 포인터와 태그(버전 번호)를 묶어서 하나의 원자적 단위로 다루는 ABA 문제 완화 기법에서 자주 등장한다. 오퍼랜드는 `EDX:EAX`(비교값)와 `ECX:EBX`(새 값) 쌍으로, `CMPXCHG`보다 레지스터 사용이 고정되어 있어 더 특징적으로 보인다.

### 스택/RSP/RIP 변화
스택에는 영향이 없다. `RIP`는 다음 명령으로 이동한다.

### 컴파일러/라이브러리가 만드는 전형적 패턴: CAS 재시도 루프
`compare_exchange`는 실패할 수 있으므로(다른 스레드가 먼저 값을 바꿨을 때), 성공할 때까지 반복하는 루프와 함께 쓰이는 것이 표준 관용구다.
```
retry:
    mov  eax, [expected]        ; 누산기에 기대값 로드
    mov  ebx, new_value
    lock cmpxchg [shared_var], ebx
    jne  retry                   ; ZF=0(실패)이면 다시 시도 (eax에는 최신 값이 담겨 있음)
```
이 "읽기 → 새 값 계산 → CAS → 실패하면 재시도" 루프는 스핀락, 락 없는 스택 push/pop, 시퀀스 락 등 거의 모든 lock-free 자료구조의 뼈대다.

### IDA/Ghidra 디컴파일에서 보이는 모습
`_InterlockedCompareExchange(dst, new, expected)` 형태의 인트린식 호출로 정리되어 보이는 경우가 흔하다. 인식되지 않으면 재시도 루프가 일반 `while`문처럼만 보이고 원자성이 드러나지 않을 수 있으므로, 이런 루프를 보면 원문 디스어셈블리에서 `lock cmpxchg`가 있는지 확인하는 습관이 중요하다.

### 리버싱에서의 의미
`lock cmpxchg`가 반복문(재시도 루프) 안에 있다면 이는 거의 확실하게 lock-free 동기화 코드다. 이 위치를 찾아두면 (1) 멀티스레드 경쟁 조건이 있을 수 있는 지점, (2) 스핀락/뮤텍스의 내부 구현, (3) 안티치트/무결성 검사 같은 프로그램이 원자적으로 상태를 갱신하는 지점을 빠르게 식별할 수 있다.

## 화면/코드에서 보이는 징후
- `lock cmpxchg dword ptr [rbx], ecx` — `[rbx]`가 EAX와 같으면 ECX로 교체
- `cmpxchg` 직후 `jne`/`jnz`로 같은 위치(재시도 루프 시작)로 되돌아가는 패턴
- `lock cmpxchg8b`/`lock cmpxchg16b` — 더 넓은 폭의 CAS, 포인터+태그 조합 자료구조 의심

## 가장 먼저 할 것
1. `CMPXCHG` 직전에 누산기(EAX/RAX 등)에 어떤 값이 로드되는지 확인한다 — 그게 "기대값"이다.
2. `CMPXCHG` 직후 `ZF`를 검사하는 `Jcc`가 있는지, 있다면 실패 시 어디로 되돌아가는지(재시도 루프 여부) 확인한다.

## 단계별 절차
**1) 단발성 CAS 해석**
```asm
mov  eax, [expected_val]     ; 기대값을 누산기로
mov  ecx, [new_val]
lock cmpxchg [shared], ecx
je   success                  ; ZF=1이면 교환 성공
; 실패 시 eax에는 shared의 실제 최신 값이 담김
```

**2) 재시도 루프 해석**
```asm
retry:
mov  eax, [shared]           ; 최신 값 읽기
lea  ecx, [eax+1]             ; 새 값 계산 (예: +1)
lock cmpxchg [shared], ecx
jne  retry                    ; 실패하면 처음부터 다시
```
→ `std::atomic<int>::fetch_add`를 CAS 루프로 직접 구현한 것과 동등한 코드로 해석한다(실제 `fetch_add`는 보통 `lock xadd` 한 방으로 처리되지만, 더 복잡한 갱신 로직에는 CAS 루프가 쓰인다).

## 명령어/단축키
- IDA: F5 디컴파일 시 `_InterlockedCompareExchange` 인트린식으로 정리되어 보이는지 확인
- x64dbg/GDB: `lock cmpxchg`에 브레이크포인트를 걸고 ZF와 누산기 값을 F7/stepi로 단계별 관찰

## 출력 해석
- `ZF=1` → 비교값이 같았고 교환이 성공했다.
- `ZF=0` → 비교값이 달라서 교환이 실패했고, 누산기에는 목적지의 실제 최신 값이 담겨 있다(다음 재시도에 그대로 활용 가능).

## 흔한 실수
- `CMPXCHG` 실행 후 `ZF=1`을 "실패"로 잘못 읽는 것 — `ZF=1`은 성공(값이 같아서 교환됨)이다.
- 누산기(EAX 등)를 미리 로드하지 않고도 `CMPXCHG`가 알아서 비교 대상을 안다고 착각하는 것 — 반드시 실행 전에 "기대값"을 누산기에 넣어둬야 한다.
- `LOCK` 없이 `cmpxchg` 단독으로도 멀티코어에서 원자적이라고 착각하는 것.
- CAS 루프를 "왜 같은 코드를 반복하지?"라며 버그로 오해하는 것 — 경쟁이 있을 때 실패하고 재시도하는 것이 정상 동작이다.

## 막혔을 때 다음 체크
- `LOCK` 프리픽스 자체의 원리가 궁금하면 → [REV-0432 — LOCK 프리픽스](./rev-0432-lock-prefix.md)로 이동.
- 단순 원자적 덧셈이면 → [REV-0430 — XADD](./rev-0430-xadd.md)로 이동.
- 재시도 루프가 계속 실패하는 것처럼 보여서 디버깅이 어렵다면 → 다른 스레드가 개입하고 있을 가능성이 있으므로, 해당 스레드를 일시 정지(suspend)하고 단일 스레드로 재현되는지 확인한다.

## 미니 예제
**예제 1 — 단발성 CAS (성공/실패 분기)**
```c
int expected = 0, desired = 1;
bool ok = std::atomic_compare_exchange_strong(&flag, &expected, desired);
```
```asm
mov  eax, [expected]
mov  ecx, 1
lock cmpxchg [flag], ecx
setz al          ; ok = ZF
```

**예제 2 — 락 없는 카운터 CAS 재시도 루프**
```c
int old_val, new_val;
do {
    old_val = counter;
    new_val = old_val + 1;
} while (!compare_exchange(&counter, old_val, new_val));
```
```asm
retry:
mov  eax, [counter]
lea  ecx, [eax+1]
lock cmpxchg [counter], ecx
jne  retry
```

**예제 3 — CMPXCHG8B로 포인터+태그 원자적 갱신 (ABA 문제 완화)**
```asm
; EDX:EAX = 기대하는 (태그:포인터), ECX:EBX = 새 (태그:포인터)
lock cmpxchg8b qword ptr [rdi]
jne  retry
```

## 관련 글
- REV-0430 — XADD: 교환하며 더하기
- REV-0432 — LOCK 프리픽스와 원자적 연산 개념
- REV-0043 — XCHG: 두 값 교환
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교

## 출처/검증
- `CMPXCHG` 연산 정의(누산기 비교, ZF 세팅, 조건부 교환)와 `CMPXCHG8B`/`CMPXCHG16B`: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CMPXCHG—Compare and Exchange" 및 "CMPXCHG8B/CMPXCHG16B—Compare and Exchange Bytes" 섹션 기준 (2026-09-08 검증).
- `std::atomic::compare_exchange_*`, `InterlockedCompareExchange`의 CAS 재시도 루프 관용구: C++ 표준 라이브러리 구현체 및 Microsoft Learn "InterlockedCompareExchange function" 공식 문서 기준.
