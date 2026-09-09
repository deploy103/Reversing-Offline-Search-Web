---
id: REV-0379
title: "부동소수점 비교가 예상과 다르게 동작할 때"
slug: "rev-0379-float-compare-unexpected"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg]
keywords: ["부동소수점 비교", "NaN 비교", "ucomiss", "ucomisd", "float epsilon 비교"]
aliases: ["float 비교가 이상함", "NaN 비교 결과가 이상함", "부동소수점 같은 값인데 다르다고 나옴"]
symptom_keywords: ["float 값 두 개가 똑같아 보이는데 == 비교가 실패함", "NaN과 비교했는데 항상 false가 나옴", "jp 명령어가 왜 붙어있는지 모르겠음", "ucomiss 다음 조건 점프가 정수 비교랑 다름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
부동소수점(float/double) 비교가 정수 비교와 다르게 동작하는 건 버그가 아니라 IEEE 754 표준의 정상 규칙 때문이며, 특히 **NaN(Not a Number)은 자기 자신과 비교해도 항상 "같지 않다"**는 결과가 나오고, 계산 과정의 미세한 반올림 오차 때문에 수학적으로 같아야 할 값이 정확히 같지 않을 수 있다.

## 언제 검색해야 하나
- `float a == float b` 같은 비교가 수학적으로 분명히 같은 값인데 거짓으로 나올 때
- 디스어셈블리에서 `ucomiss`/`ucomisd` 다음에 `jp`(parity, 패리티 플래그) 조건 점프가 왜 붙어 있는지 궁금할 때
- 값이 `NaN`인지 확인하는 코드가 `if (x == x)`처럼 이상하게 자기 자신과 비교하는 형태로 보일 때
- 정수 비교와 부동소수점 비교의 조건 점프 명령어가 겉보기엔 비슷한데 플래그 해석이 다를 때

## 핵심 개념
정수는 하나의 비트 패턴이 하나의 값을 정확히 나타내지만, 부동소수점(IEEE 754)은 근사값을 저장하는 형식이라 몇 가지 특수한 비교 규칙이 있다.

**1) NaN은 그 무엇과 비교해도 "같지 않다"**: `0.0 / 0.0`이나 `sqrt(-1)`처럼 정의되지 않은 연산 결과는 NaN이 된다. IEEE 754 규칙상 `NaN == NaN`조차 **거짓(false)**이고, `NaN < x`, `NaN > x`, `NaN == x` 모두 **거짓**이다(단, `NaN != x`만 항상 참). 그래서 "이 값이 NaN인지 확인하고 싶다"는 코드는 종종 `if (x != x)`처럼 자기 자신과의 부등호 비교로 작성된다 — 정상적인 숫자라면 `x != x`는 항상 거짓이지만, NaN이라면 이 비교만 유일하게 참이 되기 때문이다.

**2) 부동소수점 비교는 정수와 다른 플래그를 쓴다**: x86/x64의 `UCOMISS`(single-precision)/`UCOMISD`(double-precision) 명령어는 비교 결과를 ZF, PF, CF 세 플래그에 담는데, 이 조합은 정수 비교(`CMP`)의 SF/OF/ZF/CF 조합과 다르다. 특히 **PF(Parity Flag)가 1로 세팅되면 "비교 불가(unordered)"**, 즉 피연산자 중 하나가 NaN이었다는 뜻이다. 그래서 부동소수점 비교 뒤에는 `jp`(PF=1이면 점프, parity/unordered 체크)가 자주 따라붙는데, 이는 "혹시 NaN이 껴서 비교 자체가 불가능한 상황인지"를 먼저 걸러내기 위한 코드다.

**3) 반올림 오차 때문에 "같아야 할 값"이 다를 수 있다**: `0.1 + 0.2`를 IEEE 754 double로 계산하면 수학적으로는 `0.3`이어야 하지만, 실제로는 `0.30000000000000004`가 나온다. `0.1`과 `0.2`가 2진 부동소수점으로 정확히 표현되지 않는 무한소수이기 때문에 발생하는 반올림 오차다. 그래서 부동소수점을 다루는 정상적인 코드는 `a == b`를 직접 쓰지 않고 `fabs(a - b) < EPSILON`(아주 작은 허용 오차 이내인지)처럼 비교하는 경우가 많다. 디스어셈블리에서 뺄셈 후 절댓값을 구하고 작은 상수와 비교하는 패턴이 보이면 바로 이 "epsilon 비교"다.

**정수 비교와의 결정적 차이**: 정수는 `a == b`가 정확히 대응하는 비트 패턴이 같은지만 보면 끝나지만, 부동소수점은 (1) NaN 여부, (2) 비트 패턴이 아닌 "수치적으로 충분히 가까운가"까지 함께 고려해야 하는 경우가 많다는 것이 핵심 차이다.

## 화면/코드에서 보이는 징후
- `ucomiss xmm0, xmm1` 또는 `ucomisd xmm0, xmm1` 다음에 `jp`(parity)와 `je`/`jne` 등이 같이 붙어 있는 코드
- 소스에서 `if (x != x)`처럼 겉으로는 항상 거짓일 것 같은 자기비교 조건이 있는 경우 — NaN 체크 관용구
- 뺄셈 결과에 절댓값(부호 비트 클리어)을 취한 뒤 아주 작은 상수(예: `1e-6`, `1e-9`)와 비교하는 부동소수점 코드
- CTF 문제에서 "정확히 이 부동소수점 값과 같아야 통과"라는 조건이 부동소수점 오차 때문에 절대 도달 불가능해 보이는 경우

## 가장 먼저 할 것
문제의 비교가 정수 비교(`cmp` + `jl`/`jb` 계열)인지 부동소수점 비교(`ucomiss`/`ucomisd`/`comiss`/`comisd` + `jp`/`je` 계열)인지부터 구분한다. `xmm` 레지스터가 관여하면 부동소수점 비교다.

## 단계별 절차

**1) 비교 명령어의 종류부터 확인**
`ucomiss`(단정밀도, float)와 `ucomisd`(배정밀도, double)를 구분한다. 뒤에 `s`가 붙으면 4바이트 float, `d`가 붙으면 8바이트 double이다. `comiss`/`comisd`(u가 없는 버전)는 NaN이 있으면 예외를 발생시킬 수 있는 변형이고, `ucomiss`/`ucomisd`는 예외 없이 조용히 unordered 결과만 남긴다.

**2) 뒤따르는 조건 점프의 의미를 정수 비교와 다르게 해석**
`jp`(또는 `jpe`)가 보이면 "피연산자 중 하나가 NaN이라 비교가 불가능한 경우"를 처리하는 분기다. 정수 비교에는 이 개념 자체가 없으므로, 부동소수점 코드에서만 나타나는 패턴임을 기억한다.

**3) 값을 직접 헥스로 확인해서 NaN 여부 판별**
IEEE 754 단정밀도에서 지수부(exponent) 비트가 전부 1이고 가수부(mantissa)가 0이 아니면 NaN이다. 예: `0x7FC00000`은 대표적인 (quiet) NaN 비트 패턴이다.
```python
>>> import struct
>>> struct.unpack('<f', bytes.fromhex('0000c07f'))[0]
nan
```

**4) epsilon 비교 패턴인지 정확한 일치 비교인지 구분**
뺄셈 후 절댓값을 구하고 작은 상수와 비교하는 코드라면, 목표값을 정확히 맞추지 않아도 그 오차 범위 안이면 통과한다는 뜻이므로 익스플로잇/입력 생성 시 오차 허용 범위를 계산해서 활용할 수 있다.

## 명령어/단축키
```asm
ucomiss xmm0, xmm1     ; 단정밀도 비교, ZF/PF/CF 세팅 (예외 없음)
ucomisd xmm0, xmm1     ; 배정밀도 비교, ZF/PF/CF 세팅 (예외 없음)
jp  label               ; PF=1이면 점프 (unordered, NaN 관여)
jnp label               ; PF=0이면 점프 (정상 비교 가능)
```
```python
import struct
struct.unpack('<f', b'...')[0]   # 4바이트를 float로 해석
struct.unpack('<d', b'...')[0]   # 8바이트를 double로 해석
math.isnan(x)                    # 파이썬에서 NaN 여부 확인
```

## 출력 해석
- `PF=1`(parity flag set) 상태에서 나온 비교 결과는 "크다/작다/같다" 그 어느 것도 신뢰할 수 없는 unordered 상태다 — 반드시 `jp`로 먼저 걸러내야 하는 이유다.
- `struct.unpack`으로 뽑은 값이 `nan`으로 나온다면 그 비트 패턴은 정상적인 수치가 아니라 "정의되지 않은 연산의 결과"라는 뜻이다.

## 흔한 실수
- 부동소수점 비교 어셈블리를 정수 비교처럼 `je`/`jne`만 보고 넘어가서 앞에 붙은 `jp` 분기의 의미(NaN 처리)를 놓치는 것.
- CTF 문제에서 목표 float 값을 "정확히" 만들려고 시도하다가, 실제로는 epsilon 비교라 근사값으로도 충분하다는 것을 못 알아채는 것.
- `float`와 `double`을 구분하지 않고 4바이트/8바이트 파싱을 섞어 써서 값 자체를 잘못 복원하는 것.
- NaN 체크 관용구(`x != x`)를 오타나 의미 없는 코드로 오해하고 그냥 지나치는 것.

## 막혔을 때 다음 체크
- XMM 레지스터를 이용한 부동소수점 비교가 실제로 어떤 명령어 조합으로 컴파일되는지 더 자세히 보고 싶으면 assembly 카테고리의 부동소수점 비교(XMM) 패턴 글로 이동.
- 부동소수점 레지스터 값 자체가 이상하게 보일 때(잘못된 타입으로 읽는 경우 등)는 assembly 카테고리의 부동소수점 레지스터 관련 글로 이동.
- 정수 비교의 signed/unsigned 조건 점프 차이가 궁금하면 REV-0025 문서로 이동.

## 미니 예제
다음 C 코드와 어셈블리를 비교해보자.
```c
int is_valid(float x) {
    return x == x;   // NaN이면 false, 정상 수치면 true
}
```
```asm
movss   xmm0, [rdi]
ucomiss xmm0, xmm0
jp      not_valid      ; PF=1(unordered) → 자기 자신과도 비교 불가 → NaN
mov     eax, 1
ret
not_valid:
xor     eax, eax
ret
```
`x`가 정상적인 수치라면 `ucomiss xmm0, xmm0`는 항상 "같음"(ordered, equal)이라 `jp`가 점프하지 않고 `eax=1`을 반환한다. 그러나 `x`가 NaN이라면 자기 자신과 비교해도 PF가 세팅되어 `jp`가 `not_valid`로 점프해 `eax=0`을 반환한다 — 이게 바로 `x == x`가 "NaN 검사용 관용구"로 쓰이는 이유를 어셈블리 수준에서 보여준다.

## 관련 글
- REV-0451 — 부동소수점 비교가 XMM 명령으로 컴파일되는 패턴
- REV-0492 — 부동소수점 레지스터 값이 이상하게 보일 때
- REV-0025 — Signed와 Unsigned 해석

## 출처/검증
- NaN 비교 규칙과 IEEE 754 unordered 개념: IEEE Std 754-2019, "Floating-Point Arithmetic" 비교 연산 관련 조항 기준 (2026-09-09 검증).
- `UCOMISS`/`UCOMISD` 명령어와 ZF/PF/CF 플래그 세팅 규칙: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.2, "UCOMISS", "UCOMISD" 명령어 레퍼런스 기준.
