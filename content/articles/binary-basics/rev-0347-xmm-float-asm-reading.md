---
id: REV-0347
title: "부동소수점이 어셈블리(XMM)로 보일 때 읽는 법"
slug: "rev-0347-xmm-float-asm-reading"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["XMM", "movss", "movsd", "addss", "mulsd", "cvtsi2sd", "ucomiss", "SSE", "부동소수점 어셈블리"]
aliases: ["movss가 뭔가요", "xmm0이 뭔가요", "부동소수점 연산이 어셈블리에서 어떻게 보이나요", "cvtsi2sd가 뭔가요"]
symptom_keywords: ["xmm0 xmm1 레지스터가 왜 나오는지 모르겠음", "movss와 movsd 차이를 모르겠음", "부동소수점 함수인데 rax가 아니라 xmm0으로 반환되는 이유를 모르겠음", "ucomiss 다음 분기가 이상하게 뒤집혀 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
정수 연산은 `eax`, `rdi` 같은 범용 레지스터(GPR)와 `add`, `cmp`, `mov` 같은 익숙한 명령어를 쓰지만, `float`/`double` 연산은 **XMM 레지스터(xmm0~xmm15)** 와 `movss`/`movsd`, `addss`/`addsd`, `ucomiss`/`ucomisd` 같은 SSE 계열 전용 명령어를 쓰기 때문에, 이 패턴을 모르면 정수 코드와 완전히 다른 별개의 명령어 집합처럼 보여 당황하게 된다.

## 언제 검색해야 하나
- 어셈블리에 `movss xmm0, [rdi]`, `addsd xmm1, xmm2`처럼 `xmm`으로 시작하는 레지스터와 `ss`/`sd`로 끝나는 낯선 니모닉이 잔뜩 나올 때
- 함수의 반환값을 확인하려고 `eax`/`rax`를 봤는데 값이 없고, 대신 `xmm0`에 값이 들어있을 때
- `cvtsi2sd`, `cvttsd2si` 같은 "변환" 계열 명령어가 왜 필요한지 이해가 안 될 때
- 부동소수점 비교(`if (a > b)`)인데 `cmp`/`jg`가 아니라 `ucomiss`/`ja` 조합이 나와서 헷갈릴 때

## 핵심 개념

### 왜 부동소수점은 별도의 레지스터를 쓰는가
x86/x64 CPU는 정수 연산 회로(ALU)와 부동소수점 연산 회로(FPU/SSE 유닛)가 물리적으로 분리되어 있다. 초창기에는 x87 FPU라는 별도 스택 기반 레지스터(`st(0)`~`st(7)`)를 썼지만, 지금은 대부분의 컴파일러가 SSE/SSE2 명령어와 **XMM 레지스터(xmm0~xmm15, 각 128비트)** 를 기본으로 사용한다. XMM 레지스터는 128비트지만 스칼라 float/double 연산에서는 하위 32비트(float 1개) 또는 하위 64비트(double 1개)만 사용한다.

### 니모닉 접미사 읽는 법 — `ss`와 `sd`
SSE 명령어 이름 끝의 두 글자가 데이터 종류를 알려준다.
- **`ss`** = Scalar Single-precision → `float`(4바이트) 하나
- **`sd`** = Scalar Double-precision → `double`(8바이트) 하나
- (참고: `ps`/`pd`는 Packed, 즉 여러 개를 한 번에 처리하는 SIMD 벡터 연산이며 스칼라 코드에서는 잘 안 보인다.)

```asm
movss   xmm0, [rdi]     ; xmm0의 하위 32비트에 float 1개를 로드
movsd   xmm0, [rdi]     ; xmm0의 하위 64비트에 double 1개를 로드
addss   xmm0, xmm1      ; xmm0(float) += xmm1(float)
addsd   xmm0, xmm1      ; xmm0(double) += xmm1(double)
mulsd   xmm0, xmm1      ; xmm0(double) *= xmm1(double)
subss   xmm0, xmm1      ; xmm0(float) -= xmm1(float)
divsd   xmm0, xmm1      ; xmm0(double) /= xmm1(double)
```
정수의 `mov`/`add`/`sub`/`mul`/`div`와 정확히 대응하는 개념이지만, 레지스터가 XMM이고 니모닉 끝에 `ss`/`sd`가 붙는다는 점만 다르다.

### 정수 ↔ 부동소수점 변환 명령어
C에서 `int`와 `float`/`double`을 섞어 쓰면(`float f = i;`, `int n = (int)d;`) 컴파일러는 반드시 변환 명령어를 삽입한다. 이 명령어들이 보이면 타입 변환이 일어나고 있다는 확실한 신호다.

```asm
cvtsi2sd  xmm0, edi     ; 정수(edi) → double로 변환해서 xmm0에 저장   (int → double)
cvtsi2ss  xmm0, edi     ; 정수(edi) → float로 변환해서 xmm0에 저장    (int → float)
cvttsd2si eax, xmm0      ; double(xmm0) → 정수로 변환(truncate)해서 eax에 저장 (double → int, 소수점 버림)
cvtsd2ss  xmm1, xmm0      ; double → float 변환 (정밀도 낮춤)
cvtss2sd  xmm1, xmm0      ; float → double 변환 (정밀도 확장)
```
`cvtt`로 시작하는 명령어의 두 번째 `t`는 "truncate"(소수점 버림, C의 `(int)` 캐스팅과 동일한 반올림 방식)를 뜻한다. 반올림이 아니라 버림이라는 점이 중요하다 — `(int)3.9`는 `4`가 아니라 `3`이다.

### 함수 인자/반환값도 XMM으로 전달된다
정수/포인터 인자는 `rdi`, `rsi`, `rdx`...(SysV) 또는 `rcx`, `rdx`, `r8`, `r9`(Windows x64)로 전달되지만(REV-0032), **float/double 인자는 별도로 `xmm0`, `xmm1`, `xmm2`...** 순서로 전달된다. 반환값도 마찬가지로 정수는 `rax`/`eax`에, float/double은 **`xmm0`** 에 담겨 돌아온다.

```c
double add(double a, double b) { return a + b; }
```
```asm
add:
    addsd   xmm0, xmm1     ; a(xmm0) + b(xmm1)
    ret                     ; 결과는 xmm0에 남아있는 상태로 반환 (return 전용 mov 불필요)
```
`rdi`, `rsi`가 전혀 등장하지 않고 처음부터 `xmm0`, `xmm1`만 쓰이는 함수를 보면 "아, 인자가 전부 float/double이구나"라고 바로 짐작할 수 있다. 정수와 부동소수점 인자가 섞여 있으면 두 레지스터 세트가 독립적으로 병행 사용된다(예: `func(int a, double b)`이면 `a`는 `edi`, `b`는 `xmm0`).

### 부동소수점 비교 — `ucomiss`/`ucomisd`와 플래그
정수 비교는 `cmp` 다음 `SF`/`ZF`/`OF` 플래그를 조합해 `jg`, `jl` 등으로 분기한다(REV-0025 관련). 부동소수점 비교는 `ucomiss`(float)/`ucomisd`(double) 명령어가 `ZF`, `PF`, `CF` 플래그를 세팅하고, 그 뒤에 이어지는 조건 분기가 `ja`, `jb`, `jbe` 같은 **부호 없는(unsigned) 계열 조건 점프**를 사용한다는 점이 특징이다. 이는 부동소수점 비교 결과가 원래 부호 있는 정수 비교와 다른 플래그 조합 규칙을 쓰기 때문이며, 겉보기엔 "왜 float 비교인데 unsigned 점프를 쓰지?"라는 의문이 들 수 있지만 이는 정상적인 컴파일러 관례다.

```c
if (a > b) { ... }   // a, b는 double
```
```asm
ucomisd xmm0, xmm1     ; a(xmm0)와 b(xmm1) 비교, 플래그 세팅
jbe     else_branch     ; a <= b 이면(즉 a > b가 거짓이면) else로 분기
```
`ucomiss`/`ucomisd`는 NaN이 포함된 비교도 안전하게 처리하도록 설계되어 있다(NaN과의 비교는 항상 "정렬 안 됨"으로 처리되어 `>`, `<`, `==` 모두 거짓이 됨). `comiss`/`comisd`(u가 없는 버전)는 NaN이 있으면 예외를 발생시킬 수 있다는 차이가 있다.

### 부호만 뒤집기 — XOR 트릭
`-x`(단항 마이너스, 부동소수점 부호 반전)는 별도의 "부호 반전 명령어"가 없다. 대신 부호 비트만 뒤집는 비트마스크를 `xorps`/`xorpd`로 XOR하는 트릭을 쓴다.
```asm
xorps   xmm0, [부호비트마스크]   ; xmm0의 최상위 비트(부호)만 뒤집음 = -x
```
이런 코드를 보면 "이거 XOR인데 왜 정수 연산이 아니지?"라고 오해하지 말고, IEEE 754에서 부호 비트를 뒤집는 것만으로 음수/양수가 뒤바뀐다는 성질(REV-0346)을 이용한 최적화임을 기억한다.

## 화면/코드에서 보이는 징후
- `xmm0`~`xmm15` 레지스터가 등장하고 `movss`, `movsd`, `addss`, `mulsd`, `ucomisd` 등 접미사가 붙은 니모닉이 나온다.
- 함수 반환 직전에 `eax`/`rax`가 아니라 `xmm0`에 최종 값이 이미 들어있고 별도 `mov` 없이 바로 `ret`.
- `cvtsi2sd`, `cvttsd2si` 처럼 `cvt`로 시작하는 명령어가 정수 레지스터와 xmm 레지스터 사이를 오간다.
- 조건 분기 앞에 `cmp` 대신 `ucomiss`/`ucomisd`가 오고, 뒤따르는 점프가 `jg`/`jl`이 아니라 `ja`/`jb`/`jbe`/`jae` 계열이다.

## 가장 먼저 할 것
XMM 레지스터가 보이면 그 함수 또는 그 부분의 변수는 `float`나 `double`이라고 확정 짓는다. 그 다음 니모닉 끝의 `ss`(float)/`sd`(double)로 정밀도를, `cvt` 계열 명령어의 유무로 타입 변환이 일어나는지를 확인한다.

## 단계별 절차
1. `xmm` 레지스터 등장 여부로 부동소수점 코드 구간을 식별한다.
2. 니모닉 끝의 `ss`/`sd`로 float인지 double인지 구분한다.
3. `cvtsi2ss`/`cvtsi2sd`/`cvttsd2si` 등 변환 명령어가 있으면 정수↔실수 캐스팅 지점으로 표시해둔다.
4. `ucomiss`/`ucomisd` 다음에 오는 조건 점프(`ja`, `jb`, `jbe`, `jae`, `je`, `jp`)를 확인해 원래 C 조건식을 복원한다.
5. 함수 진입부에 `rdi`/`rsi` 없이 바로 `xmm0`/`xmm1`을 쓰면 인자가 float/double이라고 판단하고, `rax` 없이 `xmm0`으로 끝나면 반환형도 float/double로 판단한다.
6. 디버거에서 `xmm` 레지스터 값을 직접 확인해 계산이 맞는지 검증한다.

## 명령어/단축키
```
(gdb) info registers xmm0       # xmm0 레지스터 전체 128비트 raw 값 확인
(gdb) print $xmm0.v4_float      # xmm0을 float 4개 배열로 해석해서 출력
(gdb) print $xmm0.v2_double     # xmm0을 double 2개 배열로 해석해서 출력
(x64dbg) 레지스터 창에서 FPU/XMM 탭으로 전환하면 xmm0~xmm15 값을 float/double 형식으로 바로 확인 가능
```
IDA: 부동소수점 함수의 스택 변수/인자 타입을 `float`/`double`로 지정하면(`Y` 단축키) `xmm` 레지스터 조작 코드가 자연스러운 산술식으로 디컴파일된다.

## 출력 해석
- `xmm0`의 하위 32비트만 보면 float, 하위 64비트를 보면 double 값이다. 나머지 상위 비트는 스칼라 연산에서는 대개 의미 없는 값(0이거나 이전 데이터의 잔재)이다.
- `ucomisd xmm0, xmm1` 후 `jbe`가 오면 원래 C 조건은 `if (xmm0값 > xmm1값)`이었을 가능성이 높다(참이면 안 뛰고 통과, 거짓/같으면 분기).
- `movss`/`movsd`만 있고 산술 명령어가 없다면 단순히 값을 복사하거나 반환값을 준비하는 코드다.

## 흔한 실수
- `xmm0`를 정수 레지스터처럼 취급해서 그 안의 비트를 정수값으로 그대로 해석하는 것 — 반드시 float(4바이트)/double(8바이트) 관점으로 재해석해야 한다(REV-0346).
- `ucomiss`/`ucomisd` 뒤의 unsigned 계열 점프(`ja`, `jb`)를 보고 "부호 없는 정수 비교인가?"라고 착각하는 것 — 부동소수점 비교는 원래 이 조건 코드를 재사용하는 컴파일러 관례일 뿐, 실제 값 자체가 unsigned라는 뜻이 아니다.
- `cvttsd2si`(버림)와 반올림을 혼동하는 것 — `t`가 붙은 변환 명령어는 항상 소수점을 버리지, 가장 가까운 정수로 반올림하지 않는다.
- 함수 인자에 정수와 실수가 섞여 있을 때 각각 별도의 레지스터 세트(`rdi`/`rsi`... 와 `xmm0`/`xmm1`...)를 쓴다는 것을 모르고, 인자 순서를 레지스터 번호만으로 잘못 추정하는 것.

## 막혔을 때 다음 체크
- 부동소수점 자체의 비트 구조(부호/지수/가수)가 헷갈리면 → REV-0346 부동소수점 표현 IEEE 754 기초
- 함수 인자/반환값이 어느 레지스터에 오는지 기본 규칙이 헷갈리면 → REV-0032 함수 인자와 반환값이 어디에 있는지
- 정수 비교의 플래그와 조건 분기 규칙 자체가 헷갈리면 → REV-0025 Signed와 Unsigned 해석

## 미니 예제
```c
double average(double a, double b) {
    double sum = a + b;
    if (sum > 100.0)
        sum = 100.0;
    return sum / 2.0;
}
```

x64 SysV 어셈블리(개념 설명용):
```asm
average:
    addsd   xmm0, xmm1              ; sum = a + b   (xmm0 = a, xmm1 = b, 결과는 xmm0에 누적)
    movsd   xmm2, [rip+CONST_100]   ; 상수 100.0 로드
    ucomisd xmm0, xmm2               ; sum과 100.0 비교
    jbe     skip_clamp                ; sum <= 100.0 이면 클램프 건너뜀
    movsd   xmm0, xmm2               ; sum = 100.0
skip_clamp:
    movsd   xmm2, [rip+CONST_2]      ; 상수 2.0 로드
    divsd   xmm0, xmm2                ; sum / 2.0
    ret                                ; 결과는 xmm0에 담긴 채 반환
```

IDA/Ghidra는 이를 다음처럼 자연스럽게 복원한다.

```c
double average(double a, double b)
{
  double sum;

  sum = a + b;
  if ( sum > 100.0 )
    sum = 100.0;
  return sum / 2.0;
}
```

`rdi`/`rsi`가 전혀 등장하지 않고 처음부터 `xmm0`/`xmm1`만 쓰이는 것, `ucomisd` 다음 `jbe`가 `if (sum > 100.0)`의 반대 조건으로 대응하는 것, 상수 `100.0`/`2.0`이 `.rodata`의 특정 주소에서 `movsd`로 로드되는 것이 이 함수의 핵심 패턴이다.

## 관련 글
- REV-0346 — 부동소수점 표현 IEEE 754 기초
- REV-0032 — 함수 인자와 반환값이 어디에 있는지
- REV-0025 — Signed와 Unsigned 해석

## 출처/검증
- SSE/SSE2 스칼라 부동소수점 명령어(`movss`/`movsd`/`addss`/`ucomiss` 등)의 정의와 플래그 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.2 명령어 레퍼런스 기준.
- SysV x86-64 ABI 및 Microsoft x64 호출 규약에서 부동소수점 인자/반환값이 XMM 레지스터를 사용하는 규칙: System V AMD64 ABI 공식 스펙 및 Microsoft x64 calling convention 공식 문서 기준 (2026-09-09 확인).
