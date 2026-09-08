---
id: REV-0395
title: "CVTSI2SD와 CVTTSD2SI: 정수-실수 변환"
slug: "rev-0395-cvtsi2sd-cvttsd2si"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - cvtsi2sd
  - CVTSI2SD
  - cvttsd2si
  - CVTTSD2SI
  - cvtsi2ss
  - cvttss2si
  - int to double
  - double to int
  - 정수 실수 변환
  - 형변환 어셈블리
  - type cast simd
  - xmm
  - XMM
  - SSE2
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - cvtsi2sd 뭐임
  - cvttsd2si 뭐임
  - int to double 어셈블리
  - double to int 어셈블리
  - 형변환이 simd로 되어있음
symptom_keywords:
  - int를 double로 바꾸는 코드가 cvtsi2sd로 되어있음
  - double을 int로 바꾸는 코드에 cvttsd2si가 나옴
  - t가 붙은 명령과 안붙은 명령 차이를 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`CVTSI2SD`는 정수(GPR)를 double-precision float(XMM)로, `CVTTSD2SI`는 반대로 double을 정수(GPR)로 변환하는 SSE2 명령으로, C의 `(double)i`/`(int)d` 같은 명시적 형변환이 컴파일된 결과다.

## 언제 검색해야 하나
- `int`를 `double`/`float`로, 또는 그 반대로 캐스팅하는 C 코드가 어셈블리로 어떻게 나타나는지 알고 싶을 때
- `cvtsi2sd`, `cvttsd2si` 같은 명령이 처음 나와서 이름이 무엇을 뜻하는지 헷갈릴 때
- `T`가 붙은 버전(`CVTT...`)과 안 붙은 버전(`CVT...`)의 반올림 방식 차이가 버그의 원인인지 확인해야 할 때

## 핵심 개념

### 이름 구조로 방향과 타입 읽기
SSE 변환 명령의 이름은 `CVT[T] <출발타입><도착타입>`구조를 따른다:
- `CVTSI2SD`: **C**on**v**er**t** **S**caler **I**nteger **2**(to) **S**caler **D**ouble → 정수 → double
- `CVTTSD2SI`: **C**on**v**er**t** **T**runcating **S**caler **D**ouble **2**(to) **S**caler **I**nteger → double → 정수 (버림)
- 같은 규칙으로 `CVTSI2SS`(정수→float), `CVTTSS2SI`(float→정수, 버림), `CVTSD2SI`(double→정수, 반올림) 등도 존재한다(본 문서는 double 계열을 중심으로 다룬다).

**핵심 암기법**: 이름 안의 `2`는 화살표(→)이고, 그 앞이 출발, 뒤가 도착 타입이다.

### CVTSI2SD — 정수를 double로
```
CVTSI2SD xmm_dest, r/m32_src   ; 32비트 정수를 double로 변환해 xmm_dest[0]에 저장
CVTSI2SD xmm_dest, r/m64_src   ; (REX.W 접두사 시) 64비트 정수를 double로 변환
```
- 목적지 XMM의 **하위 64비트(0번째 double)** 에만 결과가 쓰이고, 상위 64비트는 그대로 보존된다(scalar 명령의 공통 규칙, [REV-0390](rev-0390-addps-addss.md) 참고).
- 정수 → 부동소수점 변환은 IEEE 754 규칙에 따라 **반올림(가장 가까운 값으로, round-to-nearest가 기본)** 되지만, `int`/`long`이 표현할 수 있는 범위는 `double`의 53비트 가수부보다 작거나 비슷한 수준이라 실질적으로 대부분 정확히 표현된다.

### CVTTSD2SI — double을 정수로 (버림, Truncate)
```
CVTTSD2SI r32_dest, xmm/m64_src   ; double을 32비트 정수로, 소수부를 0 방향으로 버림(truncate)
CVTTSD2SI r64_dest, xmm/m64_src   ; (REX.W) 64비트 정수로 버림 변환
```
이름 중간의 **`T`(Truncating)** 가 핵심이다: 이 명령은 소수부를 **항상 0을 향해 잘라낸다**(C의 `(int)d` 캐스팅과 동일한 동작 — `3.9`→`3`, `-3.9`→`-3`). 이는 C 언어의 `(int)` 캐스트가 "반올림이 아니라 버림"이라는 규칙과 정확히 일치하기 때문에, 컴파일러는 명시적 정수 캐스팅에 거의 항상 `T`가 붙은 버전을 쓴다.

**`T` 없는 버전(`CVTSD2SI`)과의 차이**: `T`가 없는 `CVTSD2SI`는 현재 MXCSR의 반올림 모드(기본은 round-to-nearest-even)를 따라 반올림한다. 즉 `3.5`가 `CVTTSD2SI`로는 `3`(버림), `CVTSD2SI`로는 `4`(가장 가까운 짝수로 반올림, banker's rounding)가 될 수 있다. **C의 `(int)` 캐스트를 흉내내려면 반드시 `T`가 붙은 버전이 필요**하며, 컴파일러가 생성하는 캐스팅 코드는 거의 전부 `CVTT...` 계열이다.

### 변환 실패(범위 초과) 처리
정수로 표현 불가능한 값(너무 크거나 NaN)을 변환하려 하면, 결과로 **정수 부호 있는 최솟값(예: 32비트라면 `0x80000000`, "integer indefinite" 값)** 이 채워지고 MXCSR의 Invalid Operation 플래그가 세팅된다. 이는 예외를 던지지 않고 조용히 잘못된 값을 반환할 수 있다는 뜻이므로, 큰 double을 int로 캐스팅하는 코드에서 원인 불명의 이상값(`0x80000000` 근방)이 보이면 이 변환 실패를 의심해야 한다.

### 플래그 변화
정수 EFLAGS는 변경하지 않는다. 변환 결과의 정밀도/오류 상태는 MXCSR에 반영된다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴
- `double d = (double)i;` → `cvtsi2sd xmm0, edi`(또는 지역 변수 로드 후 변환)
- `int i = (int)d;` → `cvttsd2si eax, xmm0`
- 정수 인덱스로 배열 접근 후 그 값을 실수 계산에 섞는 코드(`sum += (double)arr[i];`)에서 반복문 안에 이 변환이 반복적으로 나타나기도 한다.

### IDA/Ghidra 디컴파일
`(double)`, `(int)` 같은 C 스타일 캐스트 연산자로 정확히 복원되는 경우가 많다 — 디컴파일러가 이 명령들의 의미를 잘 이해하기 때문에 원본 캐스팅 의도가 비교적 잘 드러나는 편이다.

## 화면/코드에서 보이는 징후
- `cvtsi2sd xmm0, eax` — 정수(EAX)를 double로 변환
- `cvttsd2si eax, xmm0` — double(XMM0)을 정수로 버림 변환
- 변환 직후 `cmp eax, 80000000h` 유사 비교 — 변환 실패(범위 초과) 검사 코드일 가능성
- 반복문 안에서 매 반복마다 `cvtsi2sd` — 정수 카운터를 실수 계산에 매번 캐스팅하는 비효율적 패턴(최적화 여지)

## 가장 먼저 할 것
1. 이름에서 출발 타입과 도착 타입을 순서대로 읽는다(`SI2SD`= 정수→double).
2. `T`가 붙어 있는지 확인해 버림(truncate)인지 반올림인지 구분한다.
3. 변환 결과가 이후 어떻게 쓰이는지(배열 인덱스, 반환값 등) 추적한다.

## 단계별 절차
**1) int → double 변환 인식**
```asm
mov    eax, [count]
cvtsi2sd xmm0, eax     ; xmm0 = (double)count
```
**2) double → int 버림 변환 인식**
```asm
cvttsd2si eax, xmm0     ; eax = (int)xmm0, 소수부 버림
```
**3) 변환 실패 값 인지**
결과가 `0x80000000`(32비트) 또는 `0x8000000000000000`(64비트)이면 원본 double이 범위를 초과했거나 NaN이었을 가능성을 의심한다.

## 명령어/단축키
- x64dbg/GDB: 변환 전후로 GPR(정수)과 XMM(실수) 값을 각각 확인해 캐스팅 결과를 검증 (GDB: `p $eax`, `p $xmm0.v2_double`).
- IDA F5: 대부분 `(double)`/`(int)` 캐스트로 정확히 복원되므로 디컴파일 결과를 우선 신뢰해도 무방하다.

## 출력 해석
- `cvtsi2sd` 결과 XMM의 하위 64비트만 바뀌고 상위 64비트는 그대로 유지된다 — 전체 128비트를 봤을 때 상위가 이전 값 그대로면 정상이다.
- `cvttsd2si`가 예상보다 항상 작은 정수를 낸다면(음수 방향 반올림처럼 보인다면) 실제로는 버림(0 방향)이 정상 동작임을 상기한다 — 버그가 아니라 명령의 기본 동작이다.

## 흔한 실수
- `CVTSI2SD`와 `CVTSI2SS`를 혼동하는 것 — 마지막 글자가 `D`(double)냐 `S`(single/float)냐로 목적지 정밀도가 갈린다.
- `T`가 붙은 버전과 안 붙은 버전을 같은 것으로 취급하는 것 — `CVTTSD2SI`(버림)와 `CVTSD2SI`(반올림)는 `3.5` 같은 값에서 결과가 다르게 나올 수 있다.
- 변환 결과가 `0x80000000` 근처로 나오는 걸 "정상적인 계산 결과"로 오해하는 것 — 이는 변환 실패(범위 초과/NaN)를 나타내는 특수값일 가능성이 높다.
- 이 명령들이 EFLAGS를 세팅한다고 가정하는 것 — 실제로는 정수 플래그에 영향이 없다.

## 막혔을 때 다음 체크
- 변환 결과가 이상하면 → 원본 값이 정수/실수 표현 범위를 초과하지 않았는지 확인.
- 반올림/버림 차이로 결과가 하나 어긋나면 → `T` 접미사 유무를 다시 확인.
- 어느 레지스터가 정수이고 어느 게 실수인지 헷갈리면 → GPR(EAX 등)은 항상 정수, XMM은 항상 실수 오퍼랜드임을 기억.

## 미니 예제

**예제 1 — int를 double로 캐스팅**
```c
int count = 10;
double avg = sum / (double)count;
```
```asm
mov      eax, [count]
cvtsi2sd xmm1, eax      ; (double)count
divsd    xmm0, xmm1      ; sum / (double)count
```

**예제 2 — double을 int로 버림 캐스팅**
```c
double d = 3.99;
int i = (int)d;   // i = 3 (버림)
```
```asm
cvttsd2si eax, xmm0
```

**예제 3 — 배열 인덱스 계산에 쓰이는 실수→정수 변환**
```c
int idx = (int)(t * (double)(n - 1));
```
```asm
cvtsi2sd xmm1, ecx        ; (double)(n-1)
mulsd    xmm0, xmm1        ; t * (double)(n-1)
cvttsd2si eax, xmm0         ; (int) 캐스트로 idx 확정
```

## 관련 글
- REV-0390 — ADDPS와 ADDSS: SIMD 병렬/단일 덧셈
- REV-0391 — SUBPS와 MULPS: SIMD 뺄셈과 곱셈
- REV-0388 — MOVAPD와 MOVUPD: Double Precision SIMD 이동

## 출처/검증
- `CVTSI2SD`/`CVTTSD2SI` 명령어 동작과 반올림/버림 규칙: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CVTSI2SD—Convert Doubleword Integer to Scalar Double-Precision Floating-Point Value" / "CVTTSD2SI—Convert with Truncation Scalar Double-Precision Floating-Point Value to Signed Integer" 섹션 기준 (2026-09-08 검증).
- 변환 실패 시 "integer indefinite" 값과 MXCSR Invalid Operation 플래그: Intel SDM Volume 1, "Floating-Point Exceptions" 챕터 기준.
