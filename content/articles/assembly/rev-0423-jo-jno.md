---
id: REV-0423
title: "JO와 JNO: 오버플로 플래그 기반 분기"
slug: "rev-0423-jo-jno"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - jo
  - jno
  - JO
  - JNO
  - jo 명령어
  - jno 명령어
  - overflow flag
  - 오버플로 플래그
  - OF 플래그
  - signed overflow
  - 부호 오버플로
  - integer overflow
  - 정수 오버플로
  - checked arithmetic
  - __builtin_add_overflow
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - jo 뭐임
  - jno가 뭐죠
  - 오버플로 분기
  - OF 플래그 분기
  - 정수 오버플로 탐지 분기
symptom_keywords:
  - add 다음에 jo가 나오는데 뭔지 모르겠음
  - jo가 jc랑 뭐가 다른지 모르겠음
  - imul 다음에 jo가 나옴
  - size 계산 코드에서 jo가 안 보임 취약점인가
  - 정수 오버플로 취약점 코드를 찾고 있음
---

## 한 줄 요약
`JO`/`JNO`는 오버플로 플래그(OF)만 검사해서 분기하는 명령으로, 직전 연산이 **부호 있는(signed)** 산술 결과의 표현 범위를 벗어났을 때 `JO`가 분기하며, 부호 없는(unsigned) 캐리 여부와는 완전히 별개다.

## 언제 검색해야 하나
- `ADD`/`SUB`/`IMUL` 뒤에 `jo`가 나오는데 `jc`(캐리 분기)와 뭐가 다른지 궁금할 때
- `size = count * elem_size` 같은 크기 계산 코드 뒤에 오버플로 점검이 있는지/없는지 확인해서 정수 오버플로 취약점을 찾을 때
- `__builtin_add_overflow` 같은 checked-arithmetic 코드가 어셈블리로 어떻게 나타나는지 확인할 때

## 핵심 개념

### 정확한 동작
- `JO` (Jump if Overflow): `OF = 1`이면 분기.
- `JNO` (Jump if Not Overflow): `OF = 0`이면 분기.

`OF`는 **부호 있는(signed) 산술 연산의 결과가 목적지 크기의 부호 있는 표현 범위(예: 32비트라면 -2147483648~2147483647)를 벗어났을 때** 1로 설정된다. 대표적으로 "양수+양수인데 결과가 음수로 나옴" 또는 "음수+음수인데 결과가 양수로 나옴" 같은 경우다.

### 오퍼랜드와 방향
`jo label`, `jno label` — 오퍼랜드는 분기 대상 레이블(rel8/rel32) 하나뿐이며, 조건 판정은 오직 OF 플래그만 읽는다.

### 결정적으로 중요한 구분: OF(부호 있는 오버플로) vs CF(부호 없는 캐리)
x86에는 "오버플로"를 나타내는 플래그가 두 개 있는데, 의미가 완전히 다르다.
- **CF (Carry Flag)**: 부호 없는(unsigned) 연산에서 결과가 표현 범위를 벗어났을 때(자리올림/빌림 발생) 설정. `JC`/`JB`로 분기.
- **OF (Overflow Flag)**: 부호 있는(signed) 연산에서 결과가 표현 범위를 벗어났을 때 설정. `JO`로 분기.

같은 덧셈 하나가 CF와 OF에 서로 다른 값을 남길 수 있다. 예를 들어:
```asm
mov     al, 0FFh   ; unsigned로 보면 255, signed로 보면 -1
add     al, 1
; 결과: al = 0x00
; CF = 1  (unsigned: 255+1 = 256, 8비트로 표현 못해 자리올림 발생 -> 캐리)
; OF = 0  (signed:   -1+1 = 0,   정상 범위 안 -> 오버플로 없음)
```
이 예시에서 `JC`는 분기하지만 `JO`는 분기하지 않는다 — 완전히 다른 두 가지 "넘침"을 각각 감지하는 것이다.

### 레지스터/메모리/플래그 영향
- 레지스터/메모리 영향 없음.
- 플래그를 전혀 바꾸지 않는다(OF를 포함해 읽기 전용).
- RIP: 분기 성립 시 목표 주소로, 아니면 다음 명령으로. 스택 변화 없음.

### 컴파일러 패턴: 언제 등장하는가
일반 C의 `int` 산술은 부호 있는 오버플로가 정의되지 않은 동작(UB)이라, 평범한 `int a + b`에서는 컴파일러가 보통 `JO` 점검을 넣지 않는다. `JO`/`JNO`가 실제로 나타나는 경우는:
- `__builtin_add_overflow`, `__builtin_mul_overflow` 같은 checked-arithmetic 내장 함수/인트린식을 명시적으로 쓴 코드.
- 보안이 중요한 크기 계산(할당 크기 `count * size` 등)에서 오버플로를 명시적으로 점검하는 하드닝된 코드.
- 오래된 `INTO`(Interrupt on Overflow) 명령과 짝을 이루던 BCD 연산 관례(현대 코드에서는 드묾).

```asm
mov     eax, 7FFFFFFFh   ; INT_MAX
add     eax, 1
jo      overflow_detected  ; signed overflow: INT_MAX+1 -> INT_MIN으로 wrap
```

## 화면/코드에서 보이는 징후
```asm
imul    eax, ebx
jo      mul_overflow
```
```asm
add     eax, ebx
jno     no_overflow
```
크기/인덱스 계산 직후 `JO`/`JNO`가 있으면 명시적인 오버플로 방어 코드이고, **없으면** 그 계산 결과를 이후 `malloc`/배열 인덱싱에 그대로 쓰는지 확인해볼 가치가 있다 — 정수 오버플로로 인한 힙 오버플로/버퍼 오버플로 취약점의 전형적인 패턴이다.

## 가장 먼저 할 것
1. `JO`/`JNO` 앞의 연산이 `ADD`/`SUB`/`IMUL` 중 무엇인지 확인한다.
2. 그 값이 이후 메모리 할당 크기, 배열 인덱스, 버퍼 길이로 쓰이는지 추적한다.
3. 이 검사가 실제로 모든 경로에서 이뤄지는지, 아니면 우회 가능한 경로가 있는지 확인한다(CTF/취약점 분석 관점).

## 단계별 절차
```asm
mov     eax, [count]
imul    eax, [elem_size]
jo      alloc_fail          ; 곱셈 결과가 signed 32비트 범위를 벗어나면 실패 처리
mov     ecx, eax
call    malloc
```
1. `count * elem_size`를 계산.
2. `JO`가 있다면 이 곱셈이 오버플로됐는지 명시적으로 검사하고 있다는 뜻 — 안전하게 작성된 코드.
3. 만약 이 자리에 `JO` 검사 없이 곧바로 `call malloc`으로 넘어간다면, 오버플로된 작은 값으로 `malloc`이 호출되고 이후 그 작은 버퍼에 `count`개만큼 원소를 쓰면서 힙을 넘칠 수 있는 전형적인 취약점 패턴이다.

## 명령어/단축키
- IDA/Ghidra: 디컴파일 결과에서 `if (__builtin_add_overflow(...))` 형태로 명시적으로 나타나거나, Ghidra는 내부적으로 `SCARRYx()`/`SBORROWx()` 같은 pcode 헬퍼 함수로 표시하기도 한다.
- GDB/x64dbg: EFLAGS 창에서 `OF` 비트를 직접 확인한다.

## 출력 해석
- `OF=1`이면 `JO`가 분기, `OF=0`이면 `JNO`가 분기.
- 같은 상황에서 `CF`도 함께 확인해, "이건 unsigned wrap인가 signed overflow인가"를 구분한다.

## 흔한 실수
- `OF`(signed overflow)와 `CF`(unsigned carry)를 같은 것으로 착각하는 것 — "숫자가 너무 커졌다"는 느낌으로 뭉뚱그려 이해하면, `JO` 대신 써야 할 자리에 `JC`를 기대하거나 그 반대로 착각하기 쉽다. 위의 `0xFF + 1` 예시처럼 CF=1, OF=0인 상황이 흔하다.
- `int` 오버플로 검사가 항상 있을 거라고 가정하는 것 — 일반 C 컴파일러는 대부분의 평범한 `int` 산술에 `JO`를 넣지 않는다(UB이기 때문에 오히려 최적화로 아예 검사 자체를 제거해버리기도 한다). `JO`가 있다면 그건 개발자/보안 코드가 **명시적으로** 오버플로를 검사하고 있다는 신호다.
- 크기 계산에 `JO` 점검이 없는 것을 보고도 그냥 지나치는 것 — CTF/취약점 분석 관점에서 이건 정수 오버플로 취약점을 찾는 매우 효과적인 체크포인트다.

## 막혔을 때 다음 체크
- `JO`인지 `JC`인지 다시 정확히 구분했는가?
- 해당 값이 signed로 쓰이는지 unsigned로 쓰이는지 타입을 다시 확인했는가?
- 오버플로 검사가 없는 크기 계산 결과가 실제로 `malloc`/배열 접근에 쓰이는지 데이터 흐름을 끝까지 추적했는가?

## 미니 예제

**예제 1 — INT_MAX 경계에서의 signed overflow**
```c
int x = INT_MAX;
if (__builtin_add_overflow(x, 1, &x)) { handle_overflow(); }
```
```asm
mov     eax, 7FFFFFFFh
add     eax, 1
jo      overflow_detected
```

**예제 2 — 곱셈 오버플로 점검(안전한 크기 계산)**
```asm
mov     eax, [count]
imul    eax, [elem_size]
jo      alloc_fail
```

**예제 3 — CF는 세워지지만 OF는 안 세워지는 경계 사례**
```asm
mov     al, 0FFh
add     al, 1
jno     no_signed_overflow   ; CF=1 이지만 OF=0 이므로 이 분기를 탐
```

## 관련 글
- REV-0047 — ADD: 덧셈과 플래그
- REV-0048 — SUB: 뺄셈과 플래그
- REV-0051 — IMUL: Signed 곱셈과 컴파일러 패턴
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0422 — JS와 JNS: 부호 플래그 기반 분기
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- JO/JNO 명령어 동작과 OF 정의: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "Jcc—Jump if Condition Is Met" 섹션 기준 (2026-09-08 검증).
- signed overflow(OF)와 unsigned carry(CF)의 구분: Intel SDM Volume 1, 정수 산술 및 EFLAGS 챕터 기준.
