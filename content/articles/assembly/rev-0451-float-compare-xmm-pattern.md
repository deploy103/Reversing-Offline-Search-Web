---
id: REV-0451
title: "부동소수점 비교가 XMM 명령으로 컴파일되는 패턴"
slug: "rev-0451-float-compare-xmm-pattern"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - UCOMISS
  - UCOMISD
  - COMISS
  - COMISD
  - float 비교
  - double 비교
  - XMM 비교
  - NaN 비교
  - JP JNP
  - unordered compare
aliases:
  - float 비교가 cmp로 안 보임
  - 실수 비교 어셈블리
  - ucomiss가 뭔지 모르겠음
  - float인데 왜 ja jb를 씀
symptom_keywords:
  - ucomiss 다음에 ja나 jb가 나옴
  - xmm 레지스터끼리 비교하는데 cmp가 안 보임
  - jp나 jnp가 비교 코드에 있음
  - float 비교인데 signed 점프가 아니라 unsigned 점프가 쓰임
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`float`/`double` 값끼리 `>`, `<`, `==` 등을 비교하는 C 코드는 정수처럼 `CMP`+`Jcc`가 아니라 `UCOMISS`(float) 또는 `UCOMISD`(double)로 XMM 레지스터를 직접 비교한 뒤, 그 결과로 만들어진 플래그를 놓고 **부호 있는(Signed) 점프가 아니라 부호 없는(Unsigned) 계열의 점프(`JA`/`JB`/`JBE`/`JAE`)** 로 분기하는 것이 정상이다 — 이는 실수가 아니라 IEEE 754 부동소수점 비교의 플래그 규칙 때문이다.

## 언제 검색해야 하나
- `xmm0`, `xmm1` 레지스터끼리 비교하는데 `CMP` 대신 `UCOMISS`/`UCOMISD`/`COMISS`/`COMISD`가 쓰였을 때
- 분명 `float a > b` 같은 "부호 있는" 비교인데, 어셈블리에는 `JG`/`JL`이 아니라 `JA`/`JB`(부호 없는 계열 점프)가 쓰여서 왜 그런지 헷갈릴 때
- `JP`(Jump if Parity)나 `JNP` 명령이 비교 코드 근처에 나와서 낯설 때
- `NaN`(Not a Number)을 포함한 비교가 코드에서 어떻게 처리되는지 확인하고 싶을 때

## 핵심 개념

### 정수 비교와 다른 전용 명령을 쓰는 이유
정수 비교는 `CMP`(내부적으로 `SUB`와 동일하게 플래그를 세팅, REV-0060)로 처리하지만, 부동소수점은 **뺄셈으로 비교할 수 없다**(부동소수점 뺄셈은 반올림 오차, 무한대, NaN 등 정수와 다른 특수 규칙이 있기 때문). 그래서 x86은 XMM 레지스터 두 개를 직접 비교해서 플래그를 세팅하는 전용 명령을 제공한다.
- **`UCOMISS xmm1, xmm2/m32`**: 단정밀도(float, 32비트) **비순서(Unordered) 비교**. NaN이 껴 있어도 예외를 던지지 않는다(조용히 "비교 불가"로 처리).
- **`UCOMISD xmm1, xmm2/m64`**: 배정밀도(double, 64비트) 버전.
- **`COMISS`/`COMISD`**: 위와 동작은 거의 같지만, **NaN이 하나라도 껴 있으면 부동소수점 예외(#IA, Invalid Arithmetic)를 발생시킬 수 있는 "signaling" 버전**이다. 일반적인 C `>`, `<`, `==` 비교는 예외를 던지지 않는 것이 표준 동작이므로, 컴파일러는 대부분 `UCOMISS`/`UCOMISD`를 사용한다.

### 비교 결과가 세팅하는 플래그 — 정수 CMP와 다르다
`UCOMISS`/`UCOMISD`는 비교 결과를 **ZF, PF, CF** 세 플래그로 인코딩한다(SF, OF는 항상 0으로 클리어). 이는 정수 `CMP`가 SF/OF/ZF/CF를 모두 쓰는 것과 다르다.

| 비교 결과 | ZF | PF | CF |
|---|---|---|---|
| xmm1 > xmm2 | 0 | 0 | 0 |
| xmm1 < xmm2 | 0 | 0 | 1 |
| xmm1 == xmm2 | 1 | 0 | 0 |
| Unordered (NaN 포함) | 1 | 1 | 1 |

이 표를 자세히 보면, "크다/작다/같다"의 플래그 조합이 **정수의 signed 비교(SF, OF 기반)가 아니라 정수의 unsigned 비교(CF, ZF 기반)와 완전히 동일한 패턴**임을 알 수 있다. 그래서 컴파일러는 float 비교 결과를 분기할 때 `JG`/`JL`(signed, REV-0069)이 아니라 **`JA`/`JB`/`JAE`/`JBE`(unsigned, REV-0070)** 를 사용한다 — 이것이 "float 비교인데 왜 unsigned 점프를 쓰지?"라는 의문의 답이다. REV-0088(플래그 레지스터 개요)에서 다룬 CF/ZF/SF/OF와 Jcc의 연결 규칙을 float 비교에도 그대로 적용할 수 있다는 뜻이다.

### NaN과 Unordered 결과 처리 — PF/JP
`float`나 `double` 값 중 하나라도 `NaN`이면, 모든 비교(`>`, `<`, `==`, `>=`, `<=`)가 **거짓**이어야 한다는 것이 IEEE 754 표준 규칙이다(단 `!=`는 NaN이 껴 있으면 항상 참). 이를 표현하기 위해 `PF`(Parity Flag)가 "비교 불가(Unordered)"를 나타내는 용도로 재사용된다. 엄격하게 NaN까지 고려한 코드는 `JP`(Jump if Parity, PF=1)를 추가로 검사해서 "이건 애초에 비교가 안 되는 상황"을 먼저 걸러내기도 한다.
```asm
ucomiss xmm0, xmm1
jp      unordered_case     ; 둘 중 하나라도 NaN이면 여기로
ja      greater_case        ; NaN이 아니고 xmm0 > xmm1
```
다만 실무에서는 컴파일러가 최적화를 통해 `JP` 체크를 생략하고 `JBE`(`<=` 조건의 반대) 하나로 "크다"와 "비교불가"를 한꺼번에 "거짓"으로 처리하는 압축된 분기를 만드는 경우도 많다 — 이런 경우 `>` 비교의 참/거짓 분기가 정수 비교보다 한두 개의 조건 반전이 더 들어간 것처럼 보일 수 있다.

### 레지스터/메모리 효과
- `UCOMISS`/`UCOMISD`/`COMISS`/`COMISD`는 **읽기 전용 비교**다 — 두 XMM 레지스터(또는 XMM과 메모리) 값을 비교만 하고, 오퍼랜드 자체는 전혀 변경하지 않는다. `CMP`가 `SUB`처럼 동작하되 결과를 버리는 것과 개념적으로 같다.
- 두 번째 오퍼랜드가 메모리일 수 있다(`ucomiss xmm0, [rbp-8]`) — 이때는 먼저 메모리에서 4바이트(float) 또는 8바이트(double)를 로드해서 비교한다. `MOVSS`/`MOVSD`로 미리 XMM에 로드한 뒤 비교하는 코드도 흔하다.
- **정수 레지스터(EAX 등)와 직접 비교할 수 없다** — 정수를 실수로 변환(`CVTSI2SS`/`CVTSI2SD`, REV-0395)하거나 실수를 정수로 변환한 뒤에만 비교가 가능하다.

### IDA/Ghidra 디컴파일에서 보이는 형태
Hex-Rays와 Ghidra는 이 패턴을 매우 잘 인식해서, 대개 원본 C 코드와 거의 동일하게 `if (a > b)` (a, b가 float/double) 형태로 깔끔하게 복원해준다. 다만 NaN 처리까지 완전하게 표현된 원본은 디컴파일러가 `if (a > b && !isnan_check)`처럼 풀어헤쳐 보여주기도 하므로, 조건문이 예상보다 복잡해 보이면 NaN 분기가 섞여 있는지 의심해본다.

## 화면/코드에서 보이는 징후
```asm
; float a > b
movss   xmm0, [rbp-4]      ; a
movss   xmm1, [rbp-8]       ; b
ucomiss xmm0, xmm1
jbe     false_branch         ; a <= b 이거나 unordered면 거짓
```
```asm
; double a == b
movsd   xmm0, [rbp-10h]
ucomisd xmm0, [rbp-18h]
jne     not_equal            ; ZF=0이면 다름 (JNE는 signed/unsigned 무관하게 ZF만 봄)
jp      not_equal             ; NaN 포함이면 같다고 볼 수 없음
```
```asm
; 정수를 double로 변환 후 비교
cvtsi2sd xmm0, eax
ucomisd  xmm0, xmm1
```

## 가장 먼저 할 것
1. `UCOMISS`/`UCOMISD`/`COMISS`/`COMISD`를 발견하면, 이건 무조건 부동소수점 비교라고 확정 짓는다.
2. 바로 뒤따르는 조건 분기가 `JA`/`JB`/`JAE`/`JBE`(unsigned 계열) 또는 `JE`/`JNE`(ZF만 보는 계열)인지 확인한다 — `JG`/`JL`이 나온다면 이건 float 비교의 결과가 아니라 별도의 정수 비교일 가능성이 높다.
3. `JP`/`JNP`가 섞여 있는지 확인해서 NaN까지 고려한 엄격한 비교인지 판단한다.

## 단계별 절차

**1) 오퍼랜드 타입 확정**

`XMM` 레지스터가 쓰였다는 것 자체가 부동소수점 데이터를 다룬다는 강한 신호다. `MOVSS`(4바이트, float)로 로드됐는지 `MOVSD`(8바이트, double)로 로드됐는지에 따라 float/double을 구분한다.

**2) 비교 명령과 분기 명령을 한 쌍으로 읽기**

`UCOMISS/UCOMISD` 다음에 오는 `Jcc`를 REV-0088의 플래그-분기 대응표(unsigned 계열)에 대입해서 원래 비교 연산자(`>`, `<`, `>=`, `<=`, `==`, `!=`)를 복원한다.

**3) NaN 분기 유무 확인**

`JP`/`JNP`가 있으면 NaN까지 엄밀하게 처리하는 코드다. 없다면 컴파일러가 이미 조건을 합쳐서 압축했거나, 원본 소스가 NaN을 신경 쓰지 않는 단순 비교(`if (a > b)`)였을 가능성이 크다.

**4) 반환값/후속 로직 확인**

비교 결과가 `SETcc`(REV-0453)로 0/1 값이 되어 저장되는지, 아니면 바로 `Jcc`로 분기하는지 확인해서 이 비교가 boolean 변수 저장인지 즉시 제어 흐름 분기인지 판단한다.

## 명령어/단축키
- IDA: `F5`(디컴파일), XMM 레지스터 위에서 `X`로 이 값이 어디서 왔는지(변환/로드) 역추적
- Ghidra: Decompile 창에서 float/double 타입 추론 결과 확인, Listing에서 `ucomiss`/`ucomisd` 검색(`Search → Text`)으로 전체 float 비교 지점 나열
- x64dbg/GDB: XMM 레지스터 뷰(x64dbg의 "FPU" 탭, GDB의 `info registers xmm0`)로 실제 비교되는 실수 값을 직접 확인, `p $xmm0.v4_float`(GDB)로 float 형태 출력

## 출력 해석
- `ucomiss` 뒤 `ja`/`jae`가 오답(else) 라벨로 가면 → 원래 조건은 `<=`(작거나 같다)에 가깝다. REV-0088의 대응표를 그대로 적용한다.
- `jp`가 별도 라벨로 분기하면 → 그 라벨은 "NaN이라서 비교 불가"인 경우의 처리 루틴이니, 정상 비교 로직과 구분해서 읽는다.
- IDA가 `if (a > b)`로 깔끔하게 복원했다면, NaN 처리가 이미 그 비교 연산자의 의미(부동소수점 `>`는 NaN에 대해 항상 거짓) 안에 자연스럽게 녹아 있는 것이니 별도로 걱정할 필요가 없다.

## 흔한 실수
- float 비교에 `JG`/`JL`(signed 정수 점프)이 나올 거라 기대하는 것 — 실제로는 `JA`/`JB` 계열(unsigned 점프)이 나오는 것이 정상이다. IEEE 754 비교 결과의 플래그 인코딩이 정수의 signed가 아니라 unsigned 규칙과 일치하기 때문이다.
- `UCOMISS`/`COMISS`의 차이(비순서 vs 신호 발생)를 몰라서 둘을 완전히 같은 명령으로 취급하는 것 — 대부분의 컴파일러 출력에는 `UCOMISS`/`UCOMISD`만 나오므로 실무에서 큰 문제는 안 되지만, `COMISS`/`COMISD`가 보이면 예외(#IA)를 명시적으로 신경 쓴 코드라는 걸 알아채야 한다.
- `PF`(Parity Flag)를 정수 코드에서처럼 "패리티 비트 체크"라는 옛 의미로만 알고 있어서, float 비교에서 "비교 불가(NaN)"를 뜻한다는 걸 못 알아채는 것.
- `float`와 `double`을 구분하지 않고 `UCOMISS`(float)와 `UCOMISD`(double)를 같은 것으로 뭉뚱그려 읽는 것 — 오퍼랜드 크기가 다르므로 값 해석(4바이트 vs 8바이트)도 달라진다.

## 막혔을 때 다음 체크
- Jcc가 왜 unsigned 계열인지 근본 원리가 헷갈리면 → REV-0088(플래그 레지스터와 Jcc 연결), REV-0070(JA JAE JB JBE)을 다시 읽는다.
- XMM 레지스터에 실제로 어떤 값이 들어있는지 궁금하면 → 디버거의 FPU/XMM 레지스터 뷰를 직접 확인한다(정수 뷰로 보면 비트 패턴만 보이므로 float로 해석해서 봐야 한다).
- 비교 대상이 정수에서 변환된 값인지 확인하려면 → 바로 위에서 `CVTSI2SS`/`CVTSI2SD`(REV-0395)가 있는지 찾는다.
- 비교 결과가 boolean 값으로 저장되는 패턴이 궁금하면 → REV-0453(짧은 if문이 SETcc로 컴파일되는 패턴)으로 이동한다.

## 미니 예제

**예제 1 — float 비교, 단순 분기**
```c
if (score > 90.0f) grade = 'A';
```
```asm
movss   xmm0, [rbp-4]      ; score
ucomiss xmm0, cs:flt_90    ; 90.0f
jbe     not_a               ; score <= 90.0f 또는 unordered면 A 아님
mov     byte ptr [rbp-1], 'A'
```

**예제 2 — double 동등 비교, NaN 고려**
```c
if (x == y) puts("equal");
```
```asm
movsd   xmm0, [rbp-10h]
ucomisd xmm0, [rbp-18h]
jp      not_equal            ; NaN 포함이면 같다고 볼 수 없음
jne     not_equal
call    puts
```

**예제 3 — 정수와 실수 비교(변환 후)**
```c
double d = 3.5;
int n = 4;
if (d < (double)n) { ... }
```
```asm
cvtsi2sd xmm1, [rbp-4]     ; n -> double
movsd    xmm0, [rbp-10h]     ; d
ucomisd  xmm0, xmm1
jae      skip                 ; d >= (double)n이면 건너뜀
```

**예제 4 — SETcc와 결합해 boolean 저장**
```c
bool cond = (a >= b);   // float
```
```asm
movss   xmm0, [rbp-4]
ucomiss xmm0, [rbp-8]
setae   al                  ; CF=0이면 1 (a >= b), unordered(CF=1)면 0
movzx   eax, al
```

## 관련 글
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0453 — 짧은 if문이 SETcc로 컴파일되는 패턴

## 출처/검증
- `UCOMISS`/`UCOMISD`/`COMISS`/`COMISD` 동작과 ZF/PF/CF 플래그 인코딩 표: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2, "(U)COMISS"/"(U)COMISD" 명령어 항목 기준.
- IEEE 754 부동소수점 비교 시 NaN에 대한 규칙(NaN이 껴 있으면 `>`,`<`,`==`,`>=`,`<=`는 거짓, `!=`는 참): IEEE 754-2019 표준의 비교 연산(comparison predicates) 규정 기준.
- CVTSI2SS/CVTSI2SD 등 정수-실수 변환: Intel SDM Volume 2 해당 명령어 항목 기준.
