---
id: REV-0063
title: "SAR: 산술 오른쪽 시프트"
slug: "rev-0063-sar"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - sar
  - SAR
  - sar 명령어
  - sar instruction
  - arithmetic shift right
  - 산술 오른쪽 시프트
  - 부호 유지 시프트
  - sign extension shift
  - 부호 확장 시프트
  - signed divide
  - 부호있는 나눗셈
  - "sar eax, 1"
  - "sar eax, 31"
  - abs 없이 절댓값
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - sar 뭐임
  - sar이 뭐죠
  - sar 명령
  - SAR 명령어
  - 시프트 부호유지
  - sar shr 차이가 뭔지
symptom_keywords:
  - sar과 shr 차이가 뭔지 모르겠음
  - 음수 나눗셈이 sar로 컴파일되는 이유
  - sar 31이 왜 나오는지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`SAR`(Shift Arithmetic Right)는 오퍼랜드를 오른쪽으로 밀되 **원래의 부호 비트(최상위 비트)를 그대로 복제해서 빈 왼쪽 자리를 채우는** 명령어로, 음수의 부호를 유지한 채 오른쪽 시프트를 수행한다 — 부호 있는(signed) 정수를 2의 거듭제곱으로 나누는 데 쓰인다.

## 언제 검색해야 하나
- `sar eax, 1`처럼 음수도 다뤄야 하는 나눗셈 코드를 만났을 때
- [`SHR`](rev-0062-shr.md)과 `SAR`이 왜 다른 결과를 내는지 구체적인 숫자로 이해하고 싶을 때
- `sar eax, 31` 처럼 시프트량이 레지스터 폭-1인 코드를 만나서 뭘 하는지 모를 때
- 분기 없이 절댓값(`abs()`)을 계산하는 코드에서 `sar`이 왜 등장하는지 궁금할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
SAR dest, count
```
- `dest`는 레지스터 또는 메모리, `count`는 즉시값 또는 `CL` 레지스터.
- `dest = dest >> count` (**산술적** 오른쪽 시프트: 빈 상위 비트를 원래 최상위 비트(부호 비트) 값으로 채움 — 부호 확장)
- 예: `sar eax, 1`, `sar eax, 31`, `sar eax, cl`.
- `count`는 32비트에서 `& 0x1F`, 64비트에서 `& 0x3F`로 마스킹 ([SHL/SAL](rev-0061-shl-sal.md), [SHR](rev-0062-shr.md)과 동일한 규칙).

### 레지스터/메모리에 미치는 효과 — "산술적"의 의미와 왜 부호가 보존되는가
```
eax = 1111 1111 1111 1111 1111 1111 1111 1110   (0xFFFFFFFE, signed -2)
sar eax, 1
eax = 1111 1111 1111 1111 1111 1111 1111 1111   (0xFFFFFFFF, signed -1)
```
`SAR`은 시프트하기 **전** 값의 최상위 비트(부호 비트)를 확인해서, 그 비트와 **똑같은 값**을 빈 상위 자리에 계속 채워 넣는다. 원래 값이 음수(부호 비트=1)였다면 채워지는 비트도 전부 1이 되고, 원래 값이 양수(부호 비트=0)였다면 SHR과 똑같이 0으로 채워진다. 이렇게 부호 비트를 그대로 복제해서 채우는 것을 **부호 확장(sign extension)**이라 부르며, 이것이 "산술적"이라는 이름의 의미다 — 2의 보수 정수의 부호를 산술적으로 올바르게 보존한다.

**왜 이 방식이 "올바른 부호 있는 나눗셈"인가**: 2의 보수 표현에서 오른쪽으로 1비트 시프트하면서 부호 비트를 복제하는 것은 정확히 "2로 나누고 내림(floor, 음의 무한대 방향으로 반올림)"과 같은 결과를 낸다. `-2를 2로 나누면 -1`이 정확히 나오는 이유다.

### 플래그 변화
- **CF**: 마지막으로 밀려 나간 비트(최하위 쪽에서 빠져나간 비트) 값이 그대로 들어감
- **OF**: `count == 1`일 때 **항상 0**으로 세팅됨 (SDM 명시: 산술 오른쪽 시프트는 정의상 부호를 보존하므로 오버플로가 발생할 수 없음). `count > 1`이면 undefined.
- **SF/ZF/PF**: 결과값 기준으로 세팅
- **AF**: 정의되지 않음
- **count == 0**이면 플래그 전혀 변화 없음

### 신호 있음/없음(signed/unsigned) — SAR이 signed 전용인 이유
[`SHR`](rev-0062-shr.md) 문서에서 다룬 것과 정확히 대칭되는 예시로 다시 확인하자. `eax = 0xFFFFFFFE`(-2)에 `sar eax, 1`을 적용하면:
```
0xFFFFFFFE = 1111 1111 1111 1111 1111 1111 1111 1110
sar eax, 1 (오른쪽으로 1칸, 부호 비트 1을 복제해서 채움)
결과       = 1111 1111 1111 1111 1111 1111 1111 1111 = 0xFFFFFFFF (-1)
```
`-2 / 2 = -1`, signed 나눗셈과 정확히 일치한다. 만약 여기서 `SHR`을 썼다면 `0x7FFFFFFF`(2147483647)이라는 전혀 엉뚱한 값이 나왔을 것이다([REV-0062](rev-0062-shr.md) 참고).

**정리하면**: 값이 부호 있는(signed) 정수일 가능성이 있다면 나눗셈용 시프트는 반드시 `SAR`이어야 하고, 순수 unsigned 값이라면 `SHR`이 쓰인다. **컴파일러가 SAR을 선택했다는 사실 자체가 해당 변수가 signed(`int` 등)라는 강력한 증거**이며, 반대도 마찬가지다.

### 정확하지 않은 반올림 — 컴파일러의 보정 코드
`SAR`은 나눗셈에서 항상 "내림(floor)"으로 반올림하지만, C의 정수 나눗셈(`/`)은 "0 방향으로 절삭(truncate toward zero)"한다. 이 둘은 **나눠지는 값이 음수이고 나머지가 있을 때** 다르게 동작한다. 예: `-3 / 2`는 C에서 `-1`(0 방향 절삭)이지만, `SAR eax, 1`을 그냥 적용하면 `-2`(내림)가 나와 서로 다르다. 그래서 컴파일러는 signed 나눗셈을 SAR로 최적화할 때 **부호가 음수인 경우를 보정하는 코드**(시프트 전에 `(2^n - 1)`을 더하는 형태)를 추가로 생성한다:
```asm
; int y = x / 4; (x가 음수일 수도 있는 경우의 전형적인 컴파일러 출력)
mov  eax, [x]
cdq                 ; eax를 64비트로 부호 확장해서 edx:eax 준비 (사실상 부호 비트를 edx 전체에 복제)
and  edx, 3         ; edx = (x가 음수면) 0x3, (양수면) 0
add  eax, edx        ; 음수일 때만 보정값 더함
sar  eax, 2          ; 이제 SAR로 나눠도 0 방향 절삭과 결과가 일치
```
이 `cdq`+`and`+`add`+`sar` 조합을 통째로 보면 "signed 나눗셈을 시프트로 최적화한 컴파일러 코드"라고 바로 인식할 수 있다.

### 스택/RSP/RIP 변화
없음.

### 부호 비트 브로드캐스트 — `sar reg, 31`(또는 `63`)
시프트량을 레지스터 폭에서 1을 뺀 값(32비트면 31, 64비트면 63)으로 주면, 결과는 **원래 값이 양수/0이면 전부 0(`0x00000000`), 음수면 전부 1(`0xFFFFFFFF`)**이 된다 — 즉 부호 비트 하나를 레지스터 전체에 "복사(broadcast)"하는 효과를 낸다. 이건 분기 없이(branchless) 부호에 따른 마스크를 만드는 매우 흔한 관용구다. 대표적으로 분기 없는 `abs()` 구현에 쓰인다:
```asm
; int abs(int x)
mov  eax, [x]
mov  edx, eax
sar  edx, 31        ; edx = 0(양수/0일 때) 또는 0xFFFFFFFF(음수일 때)
xor  eax, edx        ; 음수면 모든 비트 반전(1의 보수), 양수면 그대로
sub  eax, edx        ; 음수면 +1 더함(2의 보수 완성) = -x, 양수면 그대로
```

## 화면/코드에서 보이는 징후
- `sar eax, 1` — signed `x / 2`
- `sar eax, n` 앞에 `cdq`/`and`/`add`가 붙는 조합 — 음수 보정이 포함된 정확한 signed 나눗셈
- `sar eax, 31` (또는 `sar rax, 63`) — 부호 비트를 전체 레지스터로 브로드캐스트 (분기 없는 abs/min/max/부호 판정 코드)
- `sar eax, cl` — 가변 시프트 (드묾, 커스텀 알고리즘)

## 가장 먼저 할 것
1. 니모닉이 `SAR`인지 `SHR`인지부터 정확히 확인 (한 글자 차이지만 의미가 완전히 다름)
2. `SAR` 앞에 `cdq`+`and`+`add` 보정 코드가 있는지 확인 (있으면 정확한 signed 나눗셈)
3. 시프트량이 31/63이면 부호 브로드캐스트 패턴을 의심

## 단계별 절차

**1) 단순 signed 나눗셈(음수가 아니라고 컴파일러가 증명 가능한 경우) 인식**
```asm
mov eax, [x]
sar eax, 1     ; x / 2, 보정 코드가 없다면 x가 항상 짝수이거나 음수가 아님을 컴파일러가 알고 있는 경우
```

**2) 완전한 signed 나눗셈(보정 코드 포함) 인식**
```asm
mov  eax, [x]
cdq
and  edx, 3
add  eax, edx
sar  eax, 2      ; x / 4, 음수 절삭까지 정확히 재현
```

**3) 부호 브로드캐스트(abs 구현) 인식**
```asm
mov edx, eax
sar edx, 31
xor eax, edx
sub eax, edx
```
→ `eax = abs(eax)`로 해석.

**4) SHR과 직접 대조해서 signed/unsigned 판단**
같은 소스 값에 SHR을 적용한 코드와 SAR을 적용한 코드를 나란히 보면, 컴파일러가 그 변수를 어떤 타입으로 봤는지 바로 알 수 있다.

## 명령어/단축키
- Python으로 SAR 재현: `x >> n` (파이썬 정수는 원래 부호를 자동으로 보존하므로 그대로 SAR과 동일하게 동작 — 단, 32/64비트 폭 안에서 봐야 한다면 먼저 signed로 해석하는 변환 필요)

## 출력 해석
- IDA/Ghidra는 변수 타입이 `int`(signed)로 추론되면 `sar`을 `x / N` 또는 `x >> N`으로 보여주며, `cdq`+보정 코드 전체를 알아서 하나의 나눗셈 표현식으로 정리해준다(사람이 손으로 그 조합을 다 풀어볼 필요가 없다).
- `sar eax, 31` 패턴은 Ghidra에서 종종 `(x >> 0x1f)` 형태 그대로 남거나, 문맥에 따라 `abs()` 패턴으로 인식되어 더 단순화되기도 한다.

## 흔한 실수
- `SAR`과 `SHR`을 혼동하는 것 — 이 두 명령어의 차이가 x86에서 signed/unsigned를 구분하는 가장 대표적인 사례다. 반드시 니모닉을 한 글자씩 정확히 읽어야 한다.
- `sar eax, n`(count > 1)의 OF 값을 신뢰하는 것 — count가 1이 아니면 OF는 undefined다. (참고로 count=1일 때는 SDM이 OF=0으로 명시하므로 이 경우만 신뢰 가능.)
- `SAR`로 계산한 나눗셈이 C의 `/` 연산자와 완전히 동일하다고 가정하는 것 — 음수이면서 나누어떨어지지 않는 경우, 순수 SAR은 "내림"이라 C의 "0 방향 절삭"과 다르다. 컴파일러가 보정 코드(`cdq`+`and`+`add`)를 안 붙였다면, 그 값은 항상 나누어떨어지거나 항상 양수라는 걸 컴파일러가 증명했다는 뜻이다.
- `sar eax, 31`을 그냥 "쓸모없는 코드"로 넘기는 것 — 분기 없는 abs/min/max/부호 마스크 생성의 핵심 빌딩 블록이므로 CTF의 최적화된 코드에서 자주 나온다.

## 막혔을 때 다음 체크
- `SAR`인지 `SHR`인지 헷갈리면 → 이 문서와 [REV-0062](rev-0062-shr.md)의 동일한 값(`0xFFFFFFFE`) 예시를 나란히 비교해서 기억을 되짚는다.
- `sar` 앞에 이상한 `cdq`/`and`/`add` 조합이 보이면 → 이 문서의 "정확하지 않은 반올림" 절을 참고해 signed 나눗셈 보정 패턴임을 확인.
- `sar eax, 31` 뒤에 `xor`/`sub`가 이어지면 → 분기 없는 `abs()` 구현 관용구임을 확인.

## 미니 예제

**예제 1 — signed 나눗셈 (보정 없음, 컴파일러가 항상 비음수임을 증명한 경우)**
```c
int y = x / 2;   // x가 항상 짝수이거나 음수가 아님이 증명된 경우
```
```asm
mov eax, [x]
sar eax, 1
```

**예제 2 — 완전한 signed 나눗셈 (음수 보정 포함)**
```c
int y = x / 4;   // x가 음수일 수 있음
```
```asm
mov  eax, [x]
cdq
and  edx, 3
add  eax, edx
sar  eax, 2
```

**예제 3 — SHR과의 극명한 대조**
```c
int a = -2;
int r = a >> 1;   // -1 (컴파일러는 SAR 사용)
```
```asm
mov eax, 0FFFFFFFEh
sar eax, 1        ; 0xFFFFFFFF (-1) — SHR이었다면 0x7FFFFFFF
```

**예제 4 — 분기 없는 abs()**
```c
int abs_x = (x < 0) ? -x : x;
```
```asm
mov  eax, [x]
mov  edx, eax
sar  edx, 31       ; 부호 비트 브로드캐스트
xor  eax, edx
sub  eax, edx
```

## 관련 글
- [REV-0062 — SHR: 논리 오른쪽 시프트](rev-0062-shr.md)
- [REV-0061 — SHL과 SAL: 왼쪽 시프트](rev-0061-shl-sal.md)
- [REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교](rev-0060-cmp.md)
- [REV-0053 — IDIV: Signed 나눗셈](rev-0053-idiv.md)

## 출처/검증
- SAR 명령어의 오퍼랜드/플래그 동작(부호 확장, count=1 시 OF=0 명시): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "SAL/SAR/SHL/SHR—Shift" 섹션 기준 (2026-09-08 검증).
- signed 나눗셈에 대한 컴파일러의 CDQ+SAR 보정 최적화 패턴: Agner Fog, "Optimizing subroutines in assembly language" 기준.
- 분기 없는 abs() 구현(부호 비트 브로드캐스트) 관용구: Henry S. Warren Jr., "Hacker's Delight" 2장(정수 비트 트릭) 기준.
