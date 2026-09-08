---
id: REV-0062
title: "SHR: 논리 오른쪽 시프트"
slug: "rev-0062-shr"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - shr
  - SHR
  - shr 명령어
  - shr instruction
  - shift right
  - logical shift right
  - 논리 오른쪽 시프트
  - 오른쪽 시프트
  - shr과 sar 차이
  - unsigned divide
  - 부호없는 나눗셈
  - "shr eax, 1"
  - 2의 거듭제곱 나눗셈
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - shr 뭐임
  - shr이 뭐죠
  - shr 명령
  - SHR 명령어
  - 시프트 오른쪽
  - shr sar 차이가 뭔지
symptom_keywords:
  - shr과 sar 차이가 뭔지 모르겠음
  - 음수를 shr하면 왜 이상한 값이 나오는지
  - unsigned 나눗셈이 shr로 컴파일되는 이유
last_verified: "2026-09-08"
---

## 한 줄 요약
`SHR`(Shift Right, Logical)은 오퍼랜드의 모든 비트를 오른쪽으로 밀고 **빈 왼쪽(상위) 자리를 항상 0으로 채우는** 명령어로, 부호를 무시하고 값을 순수한 비트 패턴으로 취급한다 — 부호 없는(unsigned) 정수를 2의 거듭제곱으로 나누는 데 쓰인다.

## 언제 검색해야 하나
- `shr eax, 1` 같은 코드가 나오는데 나눗셈처럼 보여서 무슨 나눗셈인지 궁금할 때
- 같은 시프트인데 `SHR`과 [`SAR`](rev-0063-sar.md)의 결과가 음수에서 다르게 나오는 이유가 궁금할 때
- 큰 양수(부호 있는 관점에서는 음수로 보이는)를 시프트했는데 결과가 예상과 다를 때
- unsigned 나눗셈이 왜 `DIV` 대신 `SHR`로 컴파일됐는지 궁금할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
SHR dest, count
```
- `dest`는 레지스터 또는 메모리, `count`는 즉시값 또는 `CL` 레지스터.
- `dest = dest >> count` (**논리적** 오른쪽 시프트: 빈 상위 비트는 항상 0으로 채움)
- 예: `shr eax, 1`, `shr eax, 3`, `shr eax, cl`.
- `count`는 32비트 오퍼랜드에서 `& 0x1F`, 64비트에서 `& 0x3F`로 마스킹된다 ([SHL/SAL](rev-0061-shl-sal.md)과 동일한 규칙).

### 레지스터/메모리에 미치는 효과 — "논리적"의 의미
```
eax = 1000 0000 0000 0000 0000 0000 0000 0000   (0x80000000)
shr eax, 1
eax = 0100 0000 0000 0000 0000 0000 0000 0000   (0x40000000)
```
`SHR`은 값을 **순수 비트 패턴(unsigned)**으로만 취급한다. 원래 최상위 비트(부호 비트)가 1이었든 0이었든 상관없이, 시프트 후 새로 생기는 빈 상위 비트는 **무조건 0**으로 채운다. 이것이 "논리적(logical)" 시프트라는 이름의 의미다 — 값의 부호를 전혀 고려하지 않고 순수하게 비트만 민다.

### 플래그 변화
- **CF**: 마지막으로 밀려 나간 비트(최하위 쪽에서 빠져나간 비트) 값이 그대로 들어감
- **OF**: `count == 1`일 때만 정의됨 — 시프트 전 원래 값의 최상위 비트(부호 비트)와 같음. (SHR로 상위 비트가 무조건 0이 되므로, 원래 부호 비트가 1이었다면 "부호가 바뀐 것"으로 간주해 OF=1)
- **SF/ZF/PF**: 결과값 기준으로 세팅
- **AF**: 정의되지 않음
- **count == 0**이면 플래그 전혀 변화 없음 (SHL과 동일한 규칙)

### 신호 있음/없음(signed/unsigned) — SHR이 unsigned 전용인 이유
**이것이 SHR을 이해하는 데 가장 중요한 부분이다.** `SHR`은 값을 항상 unsigned로 취급하고 상위 빈 자리를 0으로 채우기 때문에, **음수(부호 있는 관점에서)에 SHR을 적용하면 나눗셈으로서는 완전히 틀린 결과가 나온다.**

**구체적인 예시로 확인해보자**: `eax = 0xFFFFFFFE`라는 32비트 값이 있다고 하자.
- **signed(부호 있는) 해석**: 이 값은 -2다 (2의 보수).
- **unsigned(부호 없는) 해석**: 이 값은 4294967294다 (거의 최댓값).

여기에 `shr eax, 1`을 적용하면:
```
0xFFFFFFFE = 1111 1111 1111 1111 1111 1111 1111 1110
shr eax, 1 (모든 비트 오른쪽으로 1칸, 상위는 0으로 채움)
결과       = 0111 1111 1111 1111 1111 1111 1111 1111 = 0x7FFFFFFF
```
결과 `0x7FFFFFFF`는 **2147483647** (거의 int의 최댓값, signed로도 양수!)이다.

- **"−2를 2로 나누면 −1이어야 한다"**는 게 signed 나눗셈의 상식이지만, `SHR`로 계산한 결과는 전혀 다른 **2147483647**이 나왔다. `SHR`은 부호를 무시하고 "4294967294를 2로 나누면 2147483647"이라는, unsigned 관점에서는 정확하지만 signed 나눗셈으로는 완전히 틀린 계산을 한 것이다.
- 반대로 이 값을 signed로 올바르게 2로 나누려면 [`SAR`](rev-0063-sar.md)(산술 오른쪽 시프트)을 써야 한다. `sar eax, 1`을 적용하면 `0xFFFFFFFF`(-1)가 나와 signed 나눗셈 "−2 / 2 = −1"과 정확히 일치한다.

**결론**: `SHR`은 값이 **unsigned**라고 확신할 수 있을 때만 나눗셈 대체로 안전하다. 값이 signed일 가능성이 있다면 반드시 `SAR`이 쓰였는지 확인해야 하며, `SHR`이 쓰인 코드를 보면 그 변수는 컴파일러가 `unsigned`/`size_t` 계열 타입으로 판단했다는 강력한 단서가 된다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴 — unsigned 나눗셈 최적화
`unsigned int` 변수를 2의 거듭제곱 상수로 나누는 코드(`x / 2`, `x / 4`, `x / 8` 등, `x`가 unsigned)는 느린 `DIV` 대신 `SHR`로 컴파일되는 경우가 매우 흔하다. 이것이 **컴파일러가 SHR을 선택했다는 사실 자체가 그 변수의 타입이 unsigned라는 강력한 증거**가 되는 이유다. 반대로 같은 나눗셈이라도 변수가 signed(`int`)라면 컴파일러는 [`SAR`](rev-0063-sar.md)에 부가적인 보정 코드(반올림 처리를 위한 `ADD`)를 덧붙인 형태로 컴파일한다.

## 화면/코드에서 보이는 징후
- `shr eax, 1` — unsigned `x / 2`
- `shr eax, 3` — unsigned `x / 8`
- `shr eax, 8` / `shr eax, 16` — 바이트/워드 단위로 상위 비트를 끌어내리는 패턴 (특정 바이트 추출, 색상값의 R/G/B 채널 분리 등)
- `shr eax, 31` — 최상위 비트(부호 비트였던 자리)만 0/1로 추출 (unsigned 관점에서 "MSB가 켜져 있었나" 검사)
- `shr eax, cl` — 가변 시프트 (커스텀 해시/체크섬, 비트필드 언패킹)

## 가장 먼저 할 것
1. 결과가 [`SAR`](rev-0063-sar.md)이 아니라 정말 `SHR`인지 니모닉을 정확히 확인 (E 사용 여부: SHR vs SAR)
2. 원본 소스가 unsigned 타입일 가능성이 높다고 가정하고 문맥 확인
3. 시프트 대상 값이 음수(0x80000000 이상)일 수 있는 값이면 결과가 "논리적"으로 나온다는 점 명심

## 단계별 절차

**1) unsigned 나눗셈 인식**
```asm
mov  eax, [size]   ; size는 unsigned int 또는 size_t
shr  eax, 2         ; eax = size / 4
```

**2) 색상/비트필드 채널 분리**
```asm
mov  eax, [color]     ; 0xAARRGGBB
shr  eax, 16
and  eax, 0FFh         ; R 채널 추출
```

**3) SHR과 SAR을 같은 값에 적용해서 차이 직접 확인 (디버거 실습)**
```asm
mov eax, 0FFFFFFFEh   ; -2 (signed) / 4294967294 (unsigned)
shr eax, 1              ; 결과: 0x7FFFFFFF (완전히 다른 값, unsigned 나눗셈 결과)
```
```asm
mov eax, 0FFFFFFFEh
sar eax, 1              ; 결과: 0xFFFFFFFF (-1, signed 나눗셈 결과와 일치)
```
x64dbg나 GDB에서 위 두 코드를 직접 실행해 레지스터 값을 비교해보면 SHR/SAR 차이가 명확히 체감된다.

## 명령어/단축키
- Python으로 unsigned 시프트 재현: `(x & 0xFFFFFFFF) >> n` (파이썬은 부호 없는 시프트만 존재하므로 그대로 SHR과 동일)

## 출력 해석
- IDA/Ghidra는 대상 변수가 `unsigned int`/`uint`로 선언되어 있으면 `shr`을 `x / N` 또는 `x >> N`으로, 변수 타입 자체를 unsigned로 추론해서 보여준다.
- 만약 디컴파일된 의사코드에서 나눗셈 결과가 이상하게 크게 보인다면, 원본 변수가 사실 음수(signed)인데 SHR이 아니라 [SAR](rev-0063-sar.md)이 쓰였어야 할 코드를 잘못 읽고 있는 게 아닌지(또는 반대로 SAR을 SHR로 착각한 게 아닌지) 디스어셈블리 원문을 다시 확인해야 한다.

## 흔한 실수
- `SHR`과 `SAR`을 같은 명령어의 변형 정도로 가볍게 여기는 것 — 음수(또는 최상위 비트가 1인 값)에서는 결과가 완전히 다르다. 이건 x86에서 signed/unsigned를 구분하는 가장 대표적인 사례다.
- 부호 있는 변수(`int`)에 `SHR`이 쓰였다고 가정하고 나눗셈 값을 계산하는 것 — 컴파일러는 signed 나눗셈에는 SHR을 쓰지 않는다(SAR + 보정 코드를 쓴다). SHR이 보이면 그 값은 unsigned로 취급되고 있다고 봐야 한다.
- `shr eax, 31`의 결과를 "부호 비트를 signed로 그대로 가져온 것"이라 착각하는 것 — SHR은 논리 시프트이므로 결과는 항상 0 또는 1(unsigned 값)이지, 음수가 아니다.

## 막혔을 때 다음 체크
- SHR 결과가 나눗셈으로는 말이 안 되는 큰 값이 나온다면 → 원래 값이 음수(signed)였을 가능성을 의심하고, 실제로는 [SAR](rev-0063-sar.md)이 쓰였어야 하는지 코드를 다시 확인.
- 변수 타입이 signed인지 unsigned인지 애매하면 → SHR이 쓰였다면 unsigned, SAR이 쓰였다면 signed라는 이 문서의 결론을 역으로 적용해 타입을 추론.
- 시프트 후 AND 마스킹이 뒤따르면 → 비트필드/색상 채널 등 특정 비트 구간만 추출하는 언패킹 코드일 가능성이 높음.

## 미니 예제

**예제 1 — unsigned 나눗셈**
```c
unsigned int half = x / 2;   // x는 unsigned int
```
```asm
mov eax, [x]
shr eax, 1
```

**예제 2 — 바이트 추출 (색상 채널)**
```c
unsigned char green = (color >> 8) & 0xFF;
```
```asm
mov eax, [color]
shr eax, 8
and eax, 0FFh
```

**예제 3 — SHR과 SAR의 극명한 차이**
```c
unsigned int a = 0xFFFFFFFE;
unsigned int r1 = a >> 1;   // 0x7FFFFFFF (unsigned 시프트)

int b = -2;
int r2 = b >> 1;             // -1 (signed 시프트, 컴파일러는 SAR 사용)
```
```asm
mov eax, 0FFFFFFFEh
shr eax, 1        ; r1 = 0x7FFFFFFF

mov eax, 0FFFFFFFEh
sar eax, 1        ; r2 = 0xFFFFFFFF (-1)
```

**예제 4 — 최상위 비트만 추출**
```c
unsigned int msb = x >> 31;   // 0 또는 1
```
```asm
mov eax, [x]
shr eax, 31
```

## 관련 글
- [REV-0063 — SAR: 산술 오른쪽 시프트](rev-0063-sar.md)
- [REV-0061 — SHL과 SAL: 왼쪽 시프트](rev-0061-shl-sal.md)
- [REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교](rev-0060-cmp.md)

## 출처/검증
- SHR 명령어의 오퍼랜드/플래그 동작(논리 시프트 정의, CF/OF 규칙): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "SAL/SAR/SHL/SHR—Shift" 섹션 기준 (2026-09-08 검증).
- unsigned 나눗셈에 대한 컴파일러의 SHR 치환 최적화: Agner Fog, "Optimizing subroutines in assembly language" 기준.
