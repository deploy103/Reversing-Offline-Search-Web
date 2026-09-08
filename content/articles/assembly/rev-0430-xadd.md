---
id: REV-0430
title: "XADD: 교환하며 더하기"
slug: "rev-0430-xadd"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - XADD
  - exchange and add
  - 교환하며 더하기
  - xadd 명령어
  - lock xadd
  - atomic increment
  - InterlockedExchangeAdd
  - fetch_add
  - atomic fetch and add
  - reference counting
  - 참조 카운트
aliases:
  - xadd가 뭔가요
  - xadd 명령
  - lock xadd가 뭐임
  - 원자적 덧셈 명령
  - 스레드 안전 카운터 어셈블리
symptom_keywords:
  - lock xadd가 뭔지 모르겠음
  - 참조 카운트 어셈블리
  - InterlockedExchangeAdd 어셈블리
  - fetch_add 어셈블리
  - 멀티스레드 카운터 증가 코드
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`XADD dst, src`는 "목적지의 원래 값을 소스에 백업해 두고, 목적지에는 두 값의 합을 저장"하는 명령으로, 앞에 `LOCK` 프리픽스를 붙인 `lock xadd`는 멀티스레드 환경에서 카운터를 원자적으로 증가/감소시키는(atomic fetch-and-add) 표준적인 방법이다.

## 언제 검색해야 하나
- `lock xadd`라는 낯선 조합을 디스어셈블리에서 만났을 때
- C++ `std::atomic<int>`의 `fetch_add`, `shared_ptr`의 참조 카운트 증가, Win32 `InterlockedExchangeAdd`가 실제로 어떤 어셈블리로 컴파일되는지 궁금할 때
- 멀티스레드 프로그램을 리버싱하다가 락 없이(lock-free) 카운터를 갱신하는 코드를 발견했을 때

## 핵심 개념

### XADD가 실제로 하는 일
`XADD dst, src`는 다음을 원자적이지 않은(prefix 없는) 상태에서도 하나의 명령으로 수행한다.
```
TEMP = SRC + DEST
SRC  = DEST      ; src에는 "더하기 전" dst의 원래 값이 남는다
DEST = TEMP       ; dst에는 두 값의 합이 저장된다
```
이름 그대로 "교환(eXchange)"과 "덧셈(ADD)"이 합쳐진 동작이다. 실행 후 `dst`에는 새로운 합계가, `src`(반드시 레지스터여야 함)에는 연산 전 `dst`의 원래 값이 남는다.

### Intel 문법과 오퍼랜드
```
XADD r/m8,  r8
XADD r/m16, r16
XADD r/m32, r32
XADD r/m64, r64
```
목적지(dst)는 레지스터 또는 메모리, 소스(src)는 반드시 레지스터여야 한다(즉시값이나 메모리는 소스로 올 수 없다). 실무에서는 dst가 메모리(공유 변수), src가 "더할 값이자 결과를 돌려받을 레지스터"인 경우가 압도적으로 많다.

### 방향과 원자성
`XADD` 자체는 `LOCK` 프리픽스 없이 쓰이면 일반 명령과 마찬가지로 원자적이지 않다. 하지만 이 명령이 나온다는 것 자체가 "이전 값을 알아야 하는 덧셈"이라는 특수한 목적을 시사하므로, 실제 멀티스레드 코드에서는 거의 항상 `lock xadd` 형태로 등장한다. `LOCK`이 어떻게 원자성을 보장하는지는 [REV-0432 — LOCK 프리픽스](./rev-0432-lock-prefix.md)에서 다룬다.

### 플래그 변화
`XADD`는 `ADD`와 동일하게 CF, OF, SF, ZF, AF, PF를 계산 결과(합계)에 맞춰 갱신한다.

### 스택/RSP/RIP 변화
스택에는 영향이 없다. `RIP`는 다음 명령으로 이동한다.

### 컴파일러/라이브러리가 만드는 전형적 패턴
- C++11 `std::atomic<T>::fetch_add(n)` (T가 정수형일 때)
- Windows API `InterlockedExchangeAdd`, `_InterlockedExchangeAdd` 인트린식
- `shared_ptr`/COM 객체의 `AddRef`/`Release` 참조 카운트 증가·감소 (감소는 `xadd`에 음수를 더하는 형태로도 자주 구현됨)
- 락 없는(lock-free) 통계 카운터, 시퀀스 번호 발급기

### IDA/Ghidra 디컴파일에서 보이는 모습
IDA는 `_InterlockedExchangeAdd(&counter, 1)` 같은 인트린식 함수 호출 형태로 정리해서 보여주는 경우가 많다. 인식하지 못하면 `iVar1 = *counter; *counter = iVar1 + 1;`처럼 원자성이 드러나지 않는 일반 코드로 잘못 단순화되어 보일 수 있으므로, 원문 디스어셈블리에서 `lock xadd`가 있는지 반드시 대조해야 한다.

### 리버싱에서의 의미
`lock xadd`는 이 코드가 멀티스레드를 고려한 동기화 코드라는 것을 알려주는 신호다. 특히 `AddRef`/`Release` 스타일의 참조 카운팅 객체를 식별할 때, 또는 경쟁 조건(race condition)이 있는지 분석할 때 이 명령의 위치를 먼저 찾아두면 스레드 안전성 관련 로직의 경계를 빠르게 파악할 수 있다.

## 화면/코드에서 보이는 징후
- `lock xadd dword ptr [rdi], eax` — `[rdi]`가 가리키는 공유 카운터에 `eax`를 원자적으로 더하고, 더하기 전 원래 값이 `eax`에 남음
- `xadd`가 함수 이름 없이 `mov ecx, 1` / `lock xadd [rbx], ecx` 형태로 함께 등장하면 참조 카운트 증가(`AddRef`류)일 가능성이 높음
- 음수 즉시값(`mov ecx, -1`)과 함께 쓰이면 참조 카운트 감소(`Release`류)일 가능성

## 가장 먼저 할 것
1. `LOCK` 프리픽스가 붙어 있는지 확인한다 — 붙어 있으면 원자적 연산, 없으면 단일 스레드 전제의 일반 코드일 가능성이 있다(드묾).
2. `src` 레지스터가 명령 실행 후 어떻게 쓰이는지 본다 — 그 값(연산 전 dst)을 버리면 단순 증가 카운터, 계속 쓰면 "이전 값 기반 로직"(예: 시퀀스 번호 발급)일 가능성이 있다.

## 단계별 절차
**1) 원자적 증가(참조 카운트) 패턴 인식**
```asm
mov  eax, 1
lock xadd dword ptr [rdi], eax    ; [rdi] += 1 (원자적), eax = 이전 값
```
→ `int old = InterlockedExchangeAdd(&counter, 1);` 형태로 해석한다.

**2) 감소 패턴 인식**
```asm
mov  eax, 0FFFFFFFFh   ; -1
lock xadd dword ptr [rdi], eax
cmp  eax, 1              ; 이전 값이 1이었다면(감소 후 0이 됨) 마지막 참조 -> 해제 로직
je   free_object
```
→ `shared_ptr`의 `Release()` 구현에서 자주 보이는, "카운트를 감소시키고 이전 값이 1이었으면(즉 방금 0이 됐으면) 객체를 파괴"하는 전형적인 패턴이다.

## 명령어/단축키
- IDA: F5 디컴파일 시 `_InterlockedExchangeAdd` 인트린식으로 표시되는지 확인
- x64dbg/GDB: `lock xadd` 명령에 브레이크포인트를 걸고 F7/stepi로 실행 전후 메모리 값과 레지스터 값을 비교

## 출력 해석
- 실행 후 `src` 레지스터 값 = 연산 **전** `dst`의 원래 값. `dst`(메모리) = 연산 **후** 합계.
- `lock xadd` 뒤에 그 `src`(이전 값)를 다시 비교하는 코드가 있다면, "카운트가 0이 됐는지/한계에 도달했는지"를 판별하는 로직일 가능성이 높다.

## 흔한 실수
- `XADD`를 그냥 `ADD` 두 번(더하기+저장)과 같다고 생각해서 `src`에 이전 값이 남는다는 사실을 놓치는 것.
- `LOCK` 프리픽스 없이 `xadd` 단독으로도 항상 원자적이라고 착각하는 것 — 원자성은 `LOCK` 프리픽스가 보장한다.
- 참조 카운트 감소 코드에서 `cmp eax, 1`을 "카운트가 1인지" 검사한다고 오해하는 것 — 정확히는 **감소하기 전** 값이 1이었는지(즉 감소 후 0이 됐는지)를 검사하는 것이다.

## 막혔을 때 다음 체크
- `LOCK` 프리픽스의 동작 원리 자체가 궁금하면 → [REV-0432 — LOCK 프리픽스](./rev-0432-lock-prefix.md)로 이동.
- 조건부 갱신(비교 후 교환)이 필요한 코드라면 → [REV-0431 — CMPXCHG](./rev-0431-cmpxchg.md)로 이동.
- 단순 값 교환만 하는 코드라면 → [REV-0043 — XCHG](./rev-0043-xchg.md)로 이동.

## 미니 예제
**예제 1 — 원자적 카운터 증가**
```c
std::atomic<int> counter;
int old = counter.fetch_add(1);
```
```asm
mov  eax, 1
lock xadd dword ptr [counter], eax
; eax = 증가 전 값
```

**예제 2 — 참조 카운트 감소 후 마지막 참조 검사**
```c
if (InterlockedExchangeAdd(&refcount, -1) == 1) {
    delete this;
}
```
```asm
mov  eax, 0FFFFFFFFh
lock xadd dword ptr [rdi+refcount_offset], eax
cmp  eax, 1
je   destroy_object
```

**예제 3 — LOCK 없이 쓰인 XADD (단일 스레드 전제 코드, 드문 경우)**
```asm
mov  eax, 5
xadd dword ptr [rsi], eax   ; lock 없음: 이 스레드 문맥 안에서만 원자적
```
이런 코드는 애초에 공유되지 않는 지역 데이터거나, 컴파일러가 특정 상황에서 `lock` 없이도 안전하다고 판단한 경우다. 발견하면 왜 `lock`이 빠졌는지(진짜 단일 스레드 전용인지) 문맥을 반드시 확인해야 한다.

## 관련 글
- REV-0043 — XCHG: 두 값 교환
- REV-0047 — ADD: 덧셈과 플래그
- REV-0431 — CMPXCHG: 비교 후 교환(원자적 연산 개념)
- REV-0432 — LOCK 프리픽스와 원자적 연산 개념

## 출처/검증
- `XADD` 연산 정의(TEMP=SRC+DEST; SRC=DEST; DEST=TEMP)와 Flags Affected: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "XADD—Exchange and Add" 섹션 기준 (2026-09-08 검증).
- `std::atomic::fetch_add`, `InterlockedExchangeAdd`가 `lock xadd`로 컴파일되는 관례: C++ 표준 라이브러리 구현체 및 Microsoft Learn "Interlocked Variable Access" 공식 문서 기준.
