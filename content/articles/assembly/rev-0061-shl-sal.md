---
id: REV-0061
title: "SHL과 SAL: 왼쪽 시프트"
slug: "rev-0061-shl-sal"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - shl
  - SHL
  - sal
  - SAL
  - shl 명령어
  - sal 명령어
  - shift left
  - 왼쪽 시프트
  - 좌측 시프트
  - shl과 sal 차이
  - 2의 거듭제곱 곱셈
  - multiply by power of 2
  - fast multiply
  - "shl eax, 1"
  - "shl eax, 2"
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - shl 뭐임
  - sal 뭐임
  - shl이 뭐죠
  - shl 명령
  - SHL 명령어
  - 시프트 왼쪽
  - shl과 sal이 같은건지
symptom_keywords:
  - shl이 곱셈처럼 보이는데 왜인지 모르겠음
  - shl과 sal 차이가 뭔지 모르겠음
  - lea로 곱셈하는 이유
last_verified: "2026-09-08"
---

## 한 줄 요약
`SHL`(Shift Left)은 오퍼랜드의 모든 비트를 왼쪽으로 지정한 횟수만큼 밀고 빈 오른쪽 자리는 0으로 채우는 명령어이며, `SAL`(Arithmetic Shift Left)은 니모닉만 다를 뿐 완전히 동일한 명령어(같은 오피코드)다 — 흔히 정수를 2의 거듭제곱으로 빠르게 곱하는 데 쓰인다.

## 언제 검색해야 하나
- `shl eax, 2` 처럼 곱셈이 아닌데 곱셈처럼 동작하는 코드를 만났을 때
- `sal`이라는 니모닉을 처음 봐서 `shl`과 뭐가 다른지 궁금할 때
- 컴파일러가 `x * 4`를 `imul` 대신 `shl`로 바꾼 이유가 궁금할 때
- 시프트 후 오버플로/캐리 플래그가 어떻게 세팅되는지 정확히 알아야 할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
SHL dest, count
SAL dest, count     ; SHL과 완전히 동일 (어셈블러가 같은 오피코드로 인코딩)
```
- `dest`는 레지스터 또는 메모리, `count`는 즉시값(`1`) 또는 `CL` 레지스터.
- `dest = dest << count` — 비트를 왼쪽으로 `count`번 이동, 오른쪽(하위) 빈 자리는 0으로 채움.
- 예: `shl eax, 1`, `shl eax, 4`, `shl eax, cl`.
- **`count`는 마스킹된다**: 32비트 오퍼랜드는 count를 `& 0x1F`(0~31)로, 64비트 오퍼랜드는 `& 0x3F`(0~63)로 제한한다. 즉 `shl eax, 32`는 실제로 `shl eax, 0`과 같은 효과(값 변화 없음, 단 플래그는 count=0이므로 전혀 안 바뀜)를 낸다.

### SHL과 SAL은 왜 같은가
역사적으로 SAL은 "산술적 왼쪽 시프트"라는 이름으로 별도 정의됐지만, 왼쪽으로 시프트할 때는 부호 있는/없는 값이 똑같이 동작한다(부호 비트가 밀려 나가는 방향이라 signed/unsigned 구분이 시프트 자체에는 영향을 주지 않는다 — 오버플로 여부만 다를 뿐). 그래서 Intel은 SAL을 SHL의 별칭(alias)으로 정의했고, 어셈블러(NASM/MASM 등)는 `sal`을 써도 `shl`과 완전히 동일한 바이트 코드를 생성한다. 디스어셈블러는 대개 `shl`로만 표시하며, 소스 코드에 `sal`이라고 써도 디스어셈블한 결과는 `shl`로 보이는 경우가 많다.

### 레지스터/메모리에 미치는 효과
```
eax = 0000 0000 0000 0101   (5)
shl eax, 2
eax = 0000 0000 0001 0100   (20 = 5 * 4)
```
왼쪽으로 `n`번 시프트하는 것은 정확히 `2^n`을 곱하는 것과 같다(오버플로가 없다면).

### 플래그 변화
- **CF**: 마지막으로 밀려 나간 비트(최상위 쪽에서 빠져나간 비트) 값이 그대로 들어감
- **OF**: `count == 1`일 때만 정의됨 — 결과의 최상위 비트(부호 비트)와 CF가 다르면(즉 부호가 바뀌었으면) 1. `count > 1`인 경우 OF는 정의되지 않음(undefined)
- **SF/ZF/PF**: 결과값을 기준으로 정상적으로 세팅됨
- **AF**: 정의되지 않음
- **중요한 예외**: `count == 0`이면 **플래그가 전혀 바뀌지 않는다**(어떤 플래그도 갱신되지 않음). `shl eax, 0`은 값도 플래그도 그대로다.

### 신호 있음/없음(signed/unsigned) 관점
`SHL`은 부호 있는 값과 없는 값 모두에 대해 "왼쪽으로 비트 밀기 = 2배 곱하기"로 동일하게 동작한다. 다만 **부호 있는 값에서 시프트로 인해 부호 비트가 바뀌면(양수가 음수처럼 보이게 되면) 그건 오버플로**이며, 이 경우 OF=1(count=1일 때만 신뢰 가능)이 된다. 예: `eax = 0x40000000`(양수, 1073741824)에 `shl eax, 1`을 하면 `eax = 0x80000000`이 되어 signed로는 음수(-2147483648)로 뒤집힌다 — 이는 `int`형에서 오버플로가 발생한 것과 동일한 상황이다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴 — 2의 거듭제곱 곱셈 최적화
컴파일러는 상수를 곱하는 코드(`x * 4`, `x * 8` 등 2의 거듭제곱)를 만나면, 상대적으로 느린 `IMUL` 대신 더 빠른 `SHL`로 바꾼다. 예를 들어 배열 인덱싱(`arr[i]`, 요소 크기가 4바이트나 8바이트인 경우)에서 `i * 4`나 `i * 8` 계산이 `shl`로 컴파일되는 경우가 매우 흔하다. 다만 요소 크기가 3, 5, 12처럼 2의 거듭제곱이 아니면 컴파일러는 `LEA`(주소 계산 명령이지만 곱셈+덧셈에 자주 전용됨)나 `IMUL`을 대신 쓴다.

## 화면/코드에서 보이는 징후
- `shl eax, 1` — `x * 2`
- `shl eax, 2` — `x * 4` (흔히 4바이트 배열 인덱싱: `arr[i]`에서 `i*4`)
- `shl eax, 3` — `x * 8` (8바이트 배열/포인터 인덱싱)
- `shl eax, cl` — 시프트 양이 런타임에 결정되는 경우 (가변 비트 폭 연산, 커스텀 해시/체크섬)
- `lea eax, [eax*4+eax]` — 곱셈 5를 SHL 대신 LEA로 표현한 경우 (SHL만으로 표현 불가능한 계수)

## 가장 먼저 할 것
1. `count`가 상수인지 `cl` 레지스터인지 확인
2. 상수라면 `2^count`가 얼마인지 계산해서 "몇 배 곱셈"인지 파악
3. 결과가 배열 인덱싱 주소 계산에 쓰이는지, 순수 산술 계산인지 확인

## 단계별 절차

**1) 상수 시프트를 곱셈으로 환산**
```asm
shl eax, 3   ; eax = eax << 3 = eax * 8
```

**2) 배열 인덱싱 패턴 인식**
```asm
mov  eax, [i]
shl  eax, 2          ; eax = i * 4 (4바이트 요소 크기)
mov  ecx, [arr_ptr]
mov  edx, [ecx+eax]  ; arr[i]
```

**3) 가변 시프트(CL 사용) 인식**
```asm
mov  cl, [shift_amount]
shl  eax, cl
```
시프트 양이 데이터에 따라 달라지는 경우로, 커스텀 인코딩/해시 알고리즘에서 자주 보인다.

**4) 오버플로 여부 확인 (count=1인 경우만 OF 신뢰 가능)**
```asm
shl eax, 1
jo  overflowed   ; count=1이므로 OF가 유효, 부호가 뒤집혔으면 분기
```

## 명령어/단축키
- Python으로 검증: `x << n` (파이썬 정수는 무한 정밀도이므로 32/64비트 오버플로를 재현하려면 `(x << n) & 0xFFFFFFFF` 형태로 마스킹 필요, [REV-0026](../binary-basics/rev-0026-bit-masks.md) 참고)

## 출력 해석
- IDA/Ghidra는 `shl eax, n`을 대부분 `x << n` 또는 곧바로 `x * (1<<n)`으로 단순화하여 보여준다. 배열 인덱싱 문맥에서는 `arr[i]` 형태로 시프트 자체가 아예 사라지고 배열 접근 구문에 흡수되기도 한다.
- `count == 1`이고 그 결과를 `jo`로 검사하는 코드는 Ghidra에서 오버플로 검사 로직으로 별도 표시되지 않고 그냥 `if` 조건으로만 보일 수 있으니 디스어셈블리에서 직접 확인하는 게 정확하다.

## 흔한 실수
- `shl`과 `sal`을 서로 다른 동작을 하는 명령어라고 착각하는 것 — 완전히 동일한 명령어의 두 가지 이름(별칭)일 뿐이다.
- `shl eax, n`(count > 1)의 결과 OF 값을 신뢰하는 것 — Intel SDM에 따르면 count가 1이 아니면 OF는 정의되지 않는다(undefined). 오버플로 검사 로직이 있다면 count=1인 경우만 유효하다고 봐야 한다.
- `shl eax, 0`도 플래그를 세팅할 거라 착각하는 것 — count가 0이면 플래그는 아예 갱신되지 않는다.
- 큰 count 값(`shl eax, 40`처럼 32비트 레지스터에 32 이상)을 곧이곧대로 40번 시프트한다고 계산하는 것 — 실제로는 `40 & 0x1F = 8`이므로 8번만 시프트된다(x64 64비트 레지스터라면 `& 0x3F`).

## 막혔을 때 다음 체크
- `shl` 결과가 예상한 곱셈값과 다르면 → count가 31(또는 63)을 넘겨서 마스킹됐는지 확인.
- `shl` 뒤에 `jo`가 있는데 count가 1이 아니면 → 그 오버플로 검사는 신뢰할 수 없는 코드이거나(버그), 실제로는 다른 목적의 코드일 수 있음을 의심.
- 배열 인덱싱에서 시프트 계수가 이상하면(2도 3도 아닌 값) → 구조체 배열이거나 요소 크기가 2의 거듭제곱이 아니라서 컴파일러가 `LEA`/`IMUL`을 대신 썼을 가능성을 확인.

## 미니 예제

**예제 1 — 단순 2배 곱셈**
```c
int y = x * 2;
```
```asm
mov eax, [x]
shl eax, 1
```

**예제 2 — 배열 인덱스 주소 계산**
```c
int val = arr[i];   // int arr[], 요소 크기 4바이트
```
```asm
mov eax, [i]
shl eax, 2            ; i * 4
mov ecx, [arr]
mov edx, [ecx+eax]
```

**예제 3 — 가변 시프트**
```c
unsigned int y = x << shift_amount;
```
```asm
mov cl, [shift_amount]
mov eax, [x]
shl eax, cl
```

**예제 4 — 오버플로 검사 포함 곱셈**
```c
int y = x * 2;
if (__builtin_add_overflow_p(x, x, 0)) { handle_overflow(); }
```
```asm
mov eax, [x]
shl eax, 1
jo  handle_overflow
```

## 관련 글
- [REV-0062 — SHR: 논리 오른쪽 시프트](rev-0062-shr.md)
- [REV-0063 — SAR: 산술 오른쪽 시프트](rev-0063-sar.md)
- [REV-0064 — ROL: 왼쪽 Rotate](rev-0064-rol.md)
- [REV-0026 — 8비트 16비트 24비트 32비트 64비트 마스크](../binary-basics/rev-0026-bit-masks.md)

## 출처/검증
- SHL/SAL 명령어의 오퍼랜드/플래그 동작(SHL과 SAL의 동일성, count=0 시 플래그 미변경, count≠1 시 OF undefined 포함): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "SAL/SAR/SHL/SHR—Shift" 섹션 기준 (2026-09-08 검증).
- 2의 거듭제곱 곱셈에 대한 컴파일러의 SHL 치환 최적화: Agner Fog, "Optimizing subroutines in assembly language" 기준.
