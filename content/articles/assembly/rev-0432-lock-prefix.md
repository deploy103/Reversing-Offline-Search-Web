---
id: REV-0432
title: "LOCK 프리픽스와 원자적 연산 개념"
slug: "rev-0432-lock-prefix"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - LOCK prefix
  - LOCK 프리픽스
  - lock 접두사
  - atomic operation
  - 원자적 연산
  - bus lock
  - cache lock
  - lock xadd
  - lock cmpxchg
  - lock add
  - lock inc
  - 0xF0
  - InterlockedIncrement
aliases:
  - lock 프리픽스가 뭔가요
  - lock이 뭐임
  - lock add가 뭐임
  - 원자적 연산이 뭐죠
  - 스레드 안전 어셈블리
symptom_keywords:
  - lock이 붙은 명령이 뭔지 모르겠음
  - InterlockedIncrement 어셈블리
  - 멀티스레드 코드 어셈블리 분석
  - 스핀락 어셈블리 코드
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LOCK`은 독립된 명령이 아니라 특정 읽기-수정-쓰기(read-modify-write) 명령 앞에 붙이는 **1바이트 프리픽스(0xF0)**로, 이를 붙이면 그 명령이 메모리에 접근하는 동안 다른 CPU 코어가 같은 메모리에 끼어들지 못하도록 버스/캐시를 잠가서 **다중 코어 환경에서도 그 연산 전체가 원자적(atomic)으로 보이게** 만든다.

## 언제 검색해야 하나
- `lock add`, `lock inc`, `lock xchg`, `lock xadd`, `lock cmpxchg`, `lock or` 같은 조합을 디스어셈블리에서 처음 봤을 때
- 멀티스레드 프로그램을 리버싱하면서 "이 카운터/플래그는 여러 스레드가 동시에 건드려도 안전한가?"를 판단해야 할 때
- `InterlockedIncrement`, `std::atomic` 관련 API가 실제로 어떤 바이트로 컴파일되는지 궁금할 때

## 핵심 개념

### LOCK이 프리픽스라는 것의 의미
x86 명령어는 opcode 앞에 여러 종류의 프리픽스 바이트를 붙일 수 있다(반복 프리픽스 `REP`, 세그먼트 오버라이드 등). `LOCK`(바이트값 `0xF0`)도 그런 프리픽스 중 하나로, **그 자체로는 아무 동작도 정의하지 않고 바로 뒤에 오는 명령의 동작 방식을 바꾼다.** 디스어셈블러는 이를 `lock add ...`처럼 명령 이름 앞에 `lock` 단어를 붙여 표시한다.

### 어떤 명령에만 붙을 수 있는가
`LOCK`은 **메모리를 목적지로 하는 읽기-수정-쓰기형 명령**에만 붙을 수 있다. Intel SDM이 명시하는 허용 목록은 다음과 같다.
```
ADD, ADC, AND, BTC, BTR, BTS, CMPXCHG, CMPXCHG8B/16B,
DEC, INC, NEG, NOT, OR, SBB, SUB, XOR, XADD, XCHG
```
`XCHG`는 메모리 오퍼랜드가 있으면 `LOCK` 프리픽스가 없어도 **암묵적으로 항상 원자적**이라는 특이 사항이 있다([REV-0043 XCHG](./rev-0043-xchg.md) 참고). 그 외의 명령(예: `MOV`, `CMP`, `JMP`)에 `LOCK`을 붙이면 `#UD`(Invalid Opcode) 예외가 발생한다.

### 왜 필요한가 — 원자성의 문제
`counter++`처럼 보이는 코드도 CPU 수준에서는 "메모리에서 값을 읽기 → 레지스터에서 계산 → 메모리에 다시 쓰기"라는 세 단계로 나뉜다. 코어가 하나뿐이면 문제가 없지만, 여러 코어가 동시에 같은 메모리 주소에 대해 이 세 단계를 수행하면 두 코어가 같은 값을 읽어서 계산한 뒤 서로 덮어써 버려 증가분 하나가 사라지는 경쟁 조건(race condition)이 발생할 수 있다. `LOCK` 프리픽스는 "읽기부터 쓰기까지 전체 과정 동안 다른 코어가 이 메모리 주소에 개입하지 못하게" 보장해서 이 문제를 없앤다.

### 동작 방식(개념 수준)
과거(단일 버스 시절) CPU는 `LOCK`이 붙으면 물리적으로 시스템 버스 전체를 잠그는 "버스 락(bus lock)"을 사용했다. 현대 멀티코어 CPU는 대부분 캐시 일관성 프로토콜(MESI 등)을 이용한 "캐시 락(cache lock)"으로 더 가볍게 구현하며, 해당 캐시 라인에 대한 배타적 소유권을 얻은 뒤 연산을 완료할 때까지 다른 코어가 그 라인에 접근하지 못하게 막는다. 리버서 입장에서는 이 세부 구현보다 "LOCK이 붙은 구간은 원자적으로 실행된다"는 결과만 알면 충분하다.

### 플래그/RIP/스택 변화
`LOCK` 프리픽스 자체는 플래그를 바꾸지 않는다. 뒤따르는 명령이 원래 정의된 대로 플래그를 바꿀 뿐이다. 스택이나 RIP에도 프리픽스 자체는 영향을 주지 않는다.

### 컴파일러/라이브러리가 만드는 전형적 패턴
- `InterlockedIncrement`/`InterlockedDecrement` (Win32) → `lock inc`/`lock dec` 또는 `lock xadd`
- `InterlockedExchangeAdd` → `lock xadd`
- `InterlockedCompareExchange` → `lock cmpxchg`
- `std::atomic<T>` 클래스의 대입/증감 연산자 → 위와 동일한 `lock` 계열 명령들
- 커널/드라이버 코드에서 공유 자료구조를 보호하는 스핀락 구현부

### IDA/Ghidra 디컴파일에서 보이는 모습
`lock` 프리픽스가 붙은 명령들은 `_InterlockedIncrement`, `_InterlockedExchangeAdd` 같은 인트린식 함수 호출로 정리되어 표시되는 경우가 많다. 원문 디스어셈블리를 볼 때는 `lock` 단어가 명령 앞에 그대로 남아 있으므로 놓치기 어렵다.

### 리버싱에서의 의미
`lock` 프리픽스가 붙은 명령의 위치를 모으면 그 프로그램이 여러 스레드에서 공유하는 데이터가 무엇인지(카운터, 플래그, 큐 포인터 등) 빠르게 지도화할 수 있다. 또한 [REV-0434 — PAUSE](./rev-0434-pause.md)와 결합된 스핀락 패턴을 찾을 때, `LOCK` 계열 명령의 위치가 그 시작점이 된다.

## 화면/코드에서 보이는 징후
- `lock inc dword ptr [rdi]`, `lock dec dword ptr [rdi]` — 원자적 증가/감소
- `lock xadd`, `lock cmpxchg`, `lock cmpxchg8b/16b` — 더 복잡한 원자적 연산(REV-0430, REV-0431 참고)
- `lock or dword ptr [flag], 1` — 원자적으로 비트 플래그를 세팅
- `lock bts`/`lock btr` — 원자적으로 특정 비트를 세팅/클리어(멀티스레드 비트마스크 조작)

## 가장 먼저 할 것
1. `lock` 프리픽스가 붙은 명령을 발견하면 뒤따르는 명령이 무엇인지부터 확인한다(`inc`/`dec`/`add`/`xadd`/`cmpxchg` 등).
2. 그 명령이 조작하는 메모리 주소가 무엇을 의미하는지(참조 카운트, 플래그, 큐 헤드 등) 문맥으로 파악한다.

## 단계별 절차
**1) 단순 원자적 증가 인식**
```asm
lock inc dword ptr [rbx]     ; [rbx]를 원자적으로 +1
```
→ `InterlockedIncrement((LONG*)ptr);`로 해석.

**2) 원자적 플래그 세팅 인식**
```asm
lock or dword ptr [flags], 4   ; flags의 bit 2를 원자적으로 세팅
```

**3) LOCK이 허용되지 않는 명령에 잘못 붙은 것처럼 보이는 바이트를 만났을 때**
디스어셈블러가 `lock`을 이상한 명령 앞에 표시한다면 오프셋이 어긋난 잘못된 디스어셈블리(코드/데이터 경계 오류)일 가능성이 높다 — `LOCK`이 허용되는 명령 목록에 없는 니모닉 앞에 `lock`이 보이면 디스어셈블리 자체를 의심하고 재정렬해야 한다.

## 명령어/단축키
- IDA: F5 디컴파일에서 `_Interlocked*` 인트린식으로 표시되는지 확인
- x64dbg/GDB: `lock` 계열 명령에 브레이크포인트를 걸어 실행 전후 메모리 값을 비교(멀티스레드 디버깅 시 다른 스레드도 함께 멈추는지 확인)

## 출력 해석
- `lock` 프리픽스가 있는 명령의 실행 결과는 단일 스레드에서 실행한 것과 동일한 최종값을 항상 보장한다 — 디버거로 한 스레드만 관찰할 때는 `lock`이 없는 것과 겉보기 동작이 같아 보일 수 있으니, 원자성의 효과는 여러 스레드를 동시에 실행할 때만 체감된다.

## 흔한 실수
- `LOCK`이 아무 명령에나 붙을 수 있다고 생각하는 것 — 허용된 read-modify-write 명령이 아니면 `#UD` 예외가 난다.
- 단일 스레드 프로그램을 분석하면서 `lock` 프리픽스를 보고 "특별히 느리거나 이상한 코드"라고 오해하는 것 — 라이브러리 코드(malloc, 스레드 안전 로거 등)에서 관례적으로 들어가 있을 뿐 그 프로그램이 실제로 멀티스레드인지와는 별개일 수 있다.
- `LOCK`이 인터럽트도 완전히 막아준다고 오해하는 것 — 이는 다른 **코어**끼리의 메모리 접근 순서를 보장하는 것이 목적이며, 인터럽트/예외 처리와는 별개의 메커니즘이다(다만 실무 리버싱에서 이 구분이 중요한 경우는 드물다).

## 막혔을 때 다음 체크
- 원자적 덧셈의 구체적 동작이 궁금하면 → [REV-0430 — XADD](./rev-0430-xadd.md)
- 조건부 원자적 교환(CAS)이 궁금하면 → [REV-0431 — CMPXCHG](./rev-0431-cmpxchg.md)
- `lock` 계열 명령이 바쁜 대기(busy-wait) 루프 안에 있고 `pause`도 함께 보인다면 → [REV-0434 — PAUSE](./rev-0434-pause.md)로 이동해 스핀락 패턴인지 확인.

## 미니 예제
**예제 1 — 원자적 증가**
```c
InterlockedIncrement(&g_counter);
```
```asm
lock inc dword ptr [g_counter]
```

**예제 2 — 원자적 비트 플래그 세팅**
```c
std::atomic<unsigned int> flags;
flags.fetch_or(1u << 3);
```
```asm
lock or dword ptr [flags], 8
```

**예제 3 — 스핀락 획득에 쓰이는 lock cmpxchg (개념 예시)**
```asm
acquire:
mov  eax, 0            ; 기대값: 잠금 안 걸림(0)
mov  ecx, 1             ; 새 값: 잠금 걸림(1)
lock cmpxchg [lock_var], ecx
jne  acquire             ; 실패하면 계속 재시도 (스핀)
```
이 구조에 `PAUSE`를 추가하면 REV-0434에서 다루는 전형적인 스핀락 패턴이 완성된다.

## 관련 글
- REV-0430 — XADD: 교환하며 더하기
- REV-0431 — CMPXCHG: 비교 후 교환(원자적 연산 개념)
- REV-0434 — PAUSE: 스핀락 힌트 명령
- REV-0043 — XCHG: 두 값 교환
- REV-0047 — ADD: 덧셈과 플래그

## 출처/검증
- `LOCK` 프리픽스의 정의, 허용 명령 목록, 버스/캐시 락 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "LOCK—Assert LOCK# Signal Prefix" 섹션 기준 (2026-09-08 검증).
- `InterlockedIncrement`/`InterlockedCompareExchange` 등이 `lock` 계열 명령으로 컴파일되는 관례: Microsoft Learn "Interlocked Variable Access" 공식 문서 기준.
