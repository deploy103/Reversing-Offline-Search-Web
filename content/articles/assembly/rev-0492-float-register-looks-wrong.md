---
id: REV-0492
title: "부동소수점 레지스터 값이 이상하게 보일 때"
slug: "rev-0492-float-register-looks-wrong"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - xmm register value
  - float 레지스터
  - double 레지스터
  - IEEE 754
  - movss
  - movsd
  - cvtsi2sd
  - cvttsd2si
  - addsd
  - mulsd
  - 부동소수점 정수 해석
  - hex to float
  - x87 스택
  - st0 레지스터
aliases:
  - xmm 레지스터 값이 이상해요
  - float 값이 정수처럼 보임
  - double 레지스터 해석하는 법
  - 부동소수점 16진수 변환
  - st0 레지스터가 뭔지 모르겠음
symptom_keywords:
  - xmm0에 이상한 16진수가 들어있음
  - 디버거에서 float 값이 정수로 보임
  - 부동소수점 계산 결과가 이해가 안 됨
  - movss movsd 차이를 모르겠음
  - st0 st1 레지스터 스택이 헷갈림
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
디버거의 레지스터 창에서 `XMM0`이나 `ST0` 값이 `0x4014000000000000`처럼 "말이 안 되는 정수"로 보이는 것은 레지스터가 잘못된 게 아니라, 그 비트 패턴이 **IEEE 754 부동소수점 인코딩**이기 때문이며(이 예시는 `5.0`), 정수 레지스터처럼 10진수로 그냥 읽으면 안 되고 반드시 "부동소수점으로 해석"해서 봐야 한다.

## 언제 검색해야 하나
- x64dbg/GDB에서 `XMM0` 레지스터 값을 봤는데 `0x4024000000000000` 같은 16진수만 나와서 실제 값을 모를 때
- 디컴파일 결과에 `double`/`float` 변수인데 이상하게 큰 정수처럼 표시될 때
- `movss`, `movsd`, `addsd`, `mulsd`, `cvtsi2sd`, `cvttsd2si` 같은 명령이 나와서 정수 연산과 뭐가 다른지 헷갈릴 때
- 오래된 32비트 바이너리에서 `ST0`, `ST1` 같은 x87 FPU 스택 레지스터를 만났을 때

## 핵심 개념

### IEEE 754: 부동소수점은 정수와 완전히 다른 방식으로 비트를 쓴다
`float`(32비트)와 `double`(64비트)은 정수처럼 "값 그대로"를 이진수로 담는 게 아니라, **부호(sign) + 지수(exponent) + 가수(mantissa/fraction)** 세 부분으로 나눠서 비트를 배치하는 IEEE 754 표준을 따른다.

```
double (64비트):  [부호 1비트][지수 11비트][가수 52비트]
float  (32비트):  [부호 1비트][지수  8비트][가수 23비트]
```

그래서 `XMM0`에 `0x4014000000000000`이 들어있는 걸 정수로 읽으면 "약 4.6 x 10^18"이라는 터무니없이 큰 수처럼 보이지만, 이 비트 패턴을 IEEE 754 double로 해석하면 정확히 `5.0`이다. **레지스터 값이 이상한 게 아니라, 보는 방식이 잘못된 것**이라는 점이 이 문제의 핵심이다.

### 어디에 저장되는가: XMM(SSE) vs x87 FPU 스택
- **x64와 최신 x86 코드(SSE/SSE2 사용)**: `float`/`double` 값은 `XMM0`~`XMM15` 레지스터에 저장된다. 함수의 부동소수점 반환값은 **`XMM0`**(정수 반환값이 `RAX`인 것과 대응)에 담긴다.
- **오래된 32비트 코드(x87 FPU 사용)**: `ST0`~`ST7`이라는 8단짜리 **스택 구조**의 레지스터에 저장된다. 일반 레지스터처럼 이름으로 직접 접근하는 게 아니라 `FLD`(push), `FSTP`(pop)처럼 스택 연산으로 값을 밀어넣고 빼낸다(REV-0436~0438 참고). 컴파일러 옵션(`/arch:SSE2` 등)이나 타겟 아키텍처에 따라 x87 대신 SSE를 쓰도록 강제할 수 있어서, 최신 컴파일러가 만든 32비트 코드도 SSE를 쓰는 경우가 많다.

### 정수 ↔ 부동소수점 변환 명령
```
cvtsi2sd  xmm0, eax     ; 정수(eax)를 double로 변환해서 xmm0에 저장 (Convert Signed Integer to Scalar Double)
cvtsi2ss  xmm0, eax     ; 정수를 float로 변환
cvttsd2si eax, xmm0      ; double을 정수로 변환(잘라내기, Truncate), 이름의 두 번째 t가 "truncate"를 의미
cvtsd2si  eax, xmm0      ; double을 정수로 변환(반올림, 현재 반올림 모드 따름)
```
이름이 비슷해서 헷갈리기 쉬운데, **`cvtt`로 시작하면 소수점을 그냥 잘라버리는(truncate) 변환**이고, `cvtt`가 아니라 그냥 `cvt`면 반올림 모드를 따른다는 차이를 기억해두면 좋다. C의 `(int)someDouble` 캐스팅은 보통 truncate(0 방향 절삭)이므로 `cvttsd2si`에 대응된다.

### 스칼라(scalar) vs 패킹(packed) 연산, 그리고 ss/sd 접미사
XMM 레지스터는 128비트라서 `float` 4개 또는 `double` 2개를 동시에 담을 수 있다. 명령 이름의 접미사로 어떤 모드인지 구분한다.
```
ss = Scalar Single  (32비트 float 1개만 연산, 나머지 96비트는 그대로 둠)
sd = Scalar Double   (64비트 double 1개만 연산, 나머지 64비트는 그대로 둠)
ps = Packed Single    (32비트 float 4개를 동시에 연산)
pd = Packed Double     (64비트 double 2개를 동시에 연산)
```
```
movss   xmm0, [rax]     ; float 1개 로드
movsd   xmm0, [rax]     ; double 1개 로드 (참고: MOVS 문자열 명령의 movsd와 이름은 같지만 완전히 다른 명령이다! 오퍼랜드로 구분)
addss   xmm0, xmm1       ; float 덧셈 1개
addpd   xmm0, xmm1       ; double 2개를 동시에 덧셈
```
**주의**: `movsd`라는 이름이 REV-0081(MOVS 문자열 명령 계열)의 `MOVSD`(Move String Doubleword, 문자열 복사)와 **완전히 다른 명령**임에도 이름이 같다. 오퍼랜드를 보면 구분된다 — `xmm` 레지스터가 오퍼랜드면 부동소수점 이동, `REP` 프리픽스와 함께 나오거나 오퍼랜드가 없으면(암묵적 ESI/EDI 사용) 문자열 이동이다.

### 플래그: 부동소수점 비교는 정수 CMP와 다른 플래그를 쓴다
`comiss`/`comisd`(Compare Scalar, Ordered) 또는 `ucomiss`/`ucomisd`(Unordered 버전)는 두 부동소수점 값을 비교해서 결과를 `EFLAGS`의 `ZF`, `PF`, `CF`에 담는다(정수 `CMP`가 쓰는 `SF`/`OF`가 아니다!). `NaN`(Not a Number, 정의되지 않은 값)이 포함된 비교는 `PF=1`로 표시되며, 이런 특수 케이스 때문에 부동소수점 분기는 `ucomisd` + `jp`(패리티 분기, NaN 검사) 조합이 함께 나오는 경우가 있다.

### 스택/RIP
XMM 관련 명령들은 스택이나 `RIP`에 직접적인 영향을 주지 않는다(일반 데이터 이동/연산 명령과 동일). 다만 함수 프롤로그에서 XMM 레지스터를 저장하기 위해 `SUB RSP`로 스택 공간을 확보하고 `movaps [rsp+x], xmm6` 식으로 콜리 세이브(callee-save) XMM 레지스터를 저장하는 패턴은 흔히 볼 수 있다.

## 화면/코드에서 보이는 징후
```asm
cvtsi2sd  xmm0, ecx        ; 정수 인자를 double로 변환
mulsd     xmm0, qword ptr [rip+ratio]  ; 상수와 곱하기
movsd     qword ptr [rbp-8], xmm0        ; 결과를 지역 변수에 저장
```
x64dbg/GDB 레지스터 창:
```text
XMM0 = 4014000000000000 00000000...   ; 이 16진수를 그대로 읽으면 안 됨 (IEEE754 double로 해석하면 5.0)
```

## 가장 먼저 할 것
XMM 레지스터의 16진수 값을 보면, 디버거에 "부동소수점으로 해석" 옵션이 있는지부터 확인한다. 대부분의 현대 디버거(x64dbg, GDB, Pwndbg)는 XMM 레지스터를 float/double로 자동 변환해서 함께 보여준다.

## 단계별 절차
**1) 디버거의 부동소수점 표시 확인**

x64dbg는 레지스터 패널에서 XMM 레지스터를 우클릭하면 "float"/"double"로 해석해서 보여주는 옵션이 있다. GDB는 기본적으로 `print $xmm0.v2_double` 같은 형태로 이미 해석된 값을 보여준다.

**2) 수동으로 16진수를 부동소수점으로 변환**

디버거가 자동 변환을 안 해줄 때는 온라인/오프라인 IEEE754 변환 도구나 Python을 사용한다:
```python
import struct
struct.unpack('<d', bytes.fromhex('0000000000001440'))  # 리틀엔디안 바이트 순서 주의
```

**3) SSE인지 x87인지 확인**

레지스터 창에 `XMM0`~`XMM15`가 있으면 SSE, `ST0`~`ST7`(또는 `FPU`라는 이름의 스택)이 있으면 x87이다. x87은 스택 방식이라 "지금 맨 위(ST0)에 뭐가 있는가"를 계속 추적해야 한다.

**4) 명령 접미사로 데이터 크기/모드 파악**

`ss`(float 1개), `sd`(double 1개), `ps`(float 4개), `pd`(double 2개) 접미사를 보고 해당 XMM 레지스터의 어느 부분이 유효한 데이터인지 판단한다.

## 명령어/단축키
- x64dbg: 레지스터 패널의 XMM 값 우클릭 → 표시 형식(float/double/hex) 전환
- GDB/Pwndbg: `p $xmm0.v2_double`(double 2개로 해석), `p $xmm0.v4_float`(float 4개로 해석), `info registers xmm0`
- IDA 디버거: 레지스터 뷰에서 FPU/XMM 섹션, 값 위에서 우클릭 → 표시 형식 변경
- Python(오프라인 수동 변환): `struct.unpack('<f', ...)` (float), `struct.unpack('<d', ...)` (double)

## 출력 해석
- `0x4014000000000000` → double로 해석 시 `5.0`
- `0x3FF0000000000000` → double로 해석 시 `1.0`
- `0x40490FDB` (32비트) → float로 해석 시 약 `3.14159` (π 근사값)
- `XMM0`의 상위/하위 절반이 서로 다른 값처럼 보이면 → Packed 모드(`ps`/`pd`)로 여러 값이 동시에 들어있는 것이니, 접미사에 맞춰 4등분(float×4) 또는 2등분(double×2)해서 각각 해석한다.

## 흔한 실수
- XMM 레지스터의 16진수 값을 그냥 정수로 읽고 "이 값이 왜 이렇게 크지"라고 오해하는 것 — IEEE754 인코딩 특성상 작은 소수도 정수로 읽으면 매우 큰 수처럼 보인다.
- `movsd`(부동소수점 이동)와 `movsd`(문자열 이동, REP 프리픽스와 함께 쓰이는 MOVS 계열)를 이름만 보고 혼동하는 것 — 오퍼랜드(XMM 레지스터인지 아닌지)로 반드시 구분해야 한다.
- `cvttsd2si`와 `cvtsd2si`를 같은 명령으로 착각하는 것 — 하나는 truncate(0 방향 절삭), 하나는 반올림이라 결과가 다를 수 있다(예: `2.9`를 변환할 때 truncate는 `2`, 반올림은 `3`).
- x87 `ST0`을 일반 레지스터처럼 "항상 고정된 자리"라고 생각하는 것 — `FLD`/`FSTP` 등으로 스택처럼 밀리고 당겨지므로, 현재 `ST0`이 무엇을 가리키는지는 그 이전 연산 순서를 봐야 알 수 있다.
- `ucomisd` 이후 정수 비교처럼 `SF`/`OF`를 확인하려 하는 것 — 부동소수점 비교는 `ZF`/`PF`/`CF` 조합으로 결과를 표현한다는 점이 다르다.

## 막혔을 때 다음 체크
- 값 변환이 계속 이상하면 → 바이트 순서(리틀엔디안)를 제대로 뒤집어서 해석했는지 확인.
- SIMD 관련 배경 지식이 더 필요하면 → REV-0487(SIMD 명령이 나와서 디컴파일이 이상해 보일 때)로 이동.
- x87 FPU 스택 자체가 헷갈리면 → REV-0436(x87 FPU 스택 레지스터 개념 기초) 참고.
- MOVAPS와의 관계가 궁금하면 → REV-0386(MOVAPS) 참고.

## 미니 예제

**예제 1 — 정수를 double로 변환 후 연산 (C 대응)**
```c
double half(int n) {
    return n / 2.0;
}
```
```asm
cvtsi2sd  xmm0, ecx        ; n(정수)을 double로 변환
divsd     xmm0, qword ptr [rip+two_point_zero]  ; 2.0으로 나눔
ret                          ; 반환값은 XMM0 (RAX가 아님!)
```

**예제 2 — double을 정수로 truncate (C 캐스팅)**
```c
int truncate_it(double d) {
    return (int)d;
}
```
```asm
cvttsd2si eax, xmm0    ; xmm0(인자, double)을 소수점 버리고 정수로, 결과는 EAX
ret
```

**예제 3 — 부동소수점 비교와 분기**
```c
if (x > y) { ... }
```
```asm
movsd     xmm0, qword ptr [x]
ucomisd   xmm0, qword ptr [y]
jbe       else_branch     ; Below-or-Equal 계열 분기 사용(부호 있는 정수의 jle가 아님에 주의)
```

**예제 4 — 16진수를 Python으로 직접 변환**
```python
>>> import struct
>>> struct.pack('<d', 5.0).hex()
'0000000000001440'
>>> struct.unpack('<d', bytes.fromhex('0000000000001440'))
(5.0,)
```

## 관련 글
- REV-0487 — SIMD 명령이 나와서 디컴파일이 이상해 보일 때
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0436 — x87 FPU 스택 레지스터 개념 기초
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- IEEE 754 이진 부동소수점 형식(부호/지수/가수 배치): IEEE 754-2008 표준 및 Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 1, "Floating-Point Data Types" 섹션 기준 (2026-09-08 검증).
- `MOVSS`/`MOVSD`/`CVTSI2SD`/`CVTTSD2SI`/`COMISD`/`UCOMISD` 명령 스펙과 플래그 영향: 동 매뉴얼 Volume 2 (Instruction Set Reference) 기준.
- x64 호출 규약에서 부동소수점 반환값이 XMM0에 담긴다는 규칙: System V AMD64 ABI 및 Microsoft x64 calling convention 공식 문서 기준.
