---
id: REV-0388
title: "MOVAPD와 MOVUPD: Double Precision SIMD 이동"
slug: "rev-0388-movapd-movupd"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - movapd
  - MOVAPD
  - movupd
  - MOVUPD
  - movapd instruction
  - movupd instruction
  - movapd 명령어
  - movupd 명령어
  - double precision
  - packed double
  - xmm
  - XMM
  - SSE2
  - "movapd xmm0"
  - "movupd xmm0"
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - movapd 뭐임
  - movupd 뭐임
  - movapd movupd 차이
  - movaps movapd 차이
  - double simd 이동
symptom_keywords:
  - movapd랑 movaps 차이를 모르겠음
  - double 배열 복사가 movapd로 되어있음
  - pd ps 접미사 차이를 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`MOVAPD`/`MOVUPD`는 [MOVAPS](rev-0386-movaps.md)/[MOVUPS](rev-0387-movups.md)와 동일한 128비트 이동 명령이지만, 데이터를 4개의 32비트 float가 아니라 **2개의 64비트 double-precision float**로 해석한다는 의미상의 표기 차이만 있다.

## 언제 검색해야 하나
- `double` 배열/구조체를 다루는 코드가 `movapd`/`movupd`로 컴파일된 것을 보고 `movaps`/`movups`와 뭐가 다른지 궁금할 때
- `PS`와 `PD` 접미사가 SIMD 명령어 이름에 계속 붙는데 그 규칙을 정리하고 싶을 때
- double 연산이 많은 함수(수치 계산, 그래픽, 물리 연산 등)를 분석할 때

## 핵심 개념

### PS와 PD의 차이 — 해석의 차이일 뿐, 비트는 동일
SSE/SSE2 명령 이름의 접미사는 "128비트를 몇 개, 몇 바이트짜리 값으로 나눠 해석할 것인가"를 나타낸다:
- `PS` (Packed Single-precision): 128비트 = 32비트 float × 4개
- `PD` (Packed Double-precision): 128비트 = 64비트 float × 2개
- `SS` (Scalar Single): 128비트 중 맨 아래 32비트 하나만 사용
- `SD` (Scalar Double): 128비트 중 맨 아래 64비트 하나만 사용

**중요한 사실**: `MOVAPS`와 `MOVAPD`는 CPU 내부적으로 옮기는 비트 자체는 완전히 동일한 128비트 통짜 복사다. 차이는 오직 어떤 명령 인코딩(opcode)을 쓰느냐인데, 이는 역사적으로 SSE(단정도, `PS` 계열이 먼저 도입)와 SSE2(배정도, `PD` 계열 추가) 확장이 분리되어 생긴 것이다. 즉 값을 실제로 계산(덧셈, 곱셈 등)하지 않고 그냥 옮기기만 하는 `MOV` 계열에서는 `PS`/`PD` 구분이 사실상 "이 데이터가 float 배열인지 double 배열인지"에 대한 컴파일러의 힌트일 뿐, 동작은 같다.

### Intel 문법
```
MOVAPD xmm_dest, xmm/m128_src   ; 정렬 필요 (16바이트), 안 맞으면 #GP
MOVUPD xmm_dest, xmm/m128_src   ; 정렬 불필요
```
오퍼랜드 규칙, 방향(첫 번째=목적지), 정렬 요구사항(`A`=Aligned/예외 발생, `U`=Unaligned/항상 동작)은 `PS` 계열과 완전히 동일하다.

### 플래그, 스택/RSP/RIP 변화
`MOVAPS`/`MOVUPS`와 동일하게 EFLAGS를 건드리지 않으며 스택/RIP에 직접 영향이 없다.

### 컴파일러 패턴
`double` 타입 배열이나 구조체를 다루는 코드가 자동 벡터화되면 `MOVAPD`(정렬 보장 시)나 `MOVUPD`(정렬 미보장 시)가 생성된다. 원리는 `MOVAPS`/`MOVUPS` 문서(REV-0386, REV-0387)와 동일하며, 값의 개수만 4개에서 2개로 줄어든다(64비트씩이므로).

### IDA/Ghidra 디컴파일
`double` 변수/배열 대입으로 정리되며, `float` 버전과 마찬가지로 구조체 복사나 벡터화 루프의 일부로 나타난다.

### 스칼라 double 이동과의 관계 — MOVSD
값 하나짜리 `double` 변수를 옮길 때는 `MOVAPD`/`MOVUPD`(128비트, double 2개) 대신 **`MOVSD`(Move Scalar Double, 64비트 하나만 이동)** 가 더 흔하게 쓰인다. 함수 인자/반환값으로 `double` 하나만 오가는 코드(`double f(double x)`)에서는 `movsd`가 표준이고, `MOVAPD`/`MOVUPD`는 배열이나 구조체처럼 **double이 2개 이상 나란히 있는 블록을 한 번에 옮길 때** 주로 등장한다. 두 명령을 같은 함수 안에서 같이 볼 수 있으므로, 오퍼랜드가 배열/구조체 포인터인지 단일 변수인지로 어느 쪽이 쓰였는지 짐작할 수 있다.

### 크래시 진단 시 PS와 PD를 구분해야 하는 이유
`MOVAPD`도 `MOVAPS`와 마찬가지로 정렬이 안 맞으면 #GP 예외를 낸다. 크래시 덤프를 볼 때 명령어가 `movapd`인지 `movaps`인지는 예외 원인 진단에는 차이가 없지만(둘 다 16바이트 정렬 요구), **그 메모리가 원래 어떤 타입의 배열이었는지(float[4]인지 double[2]인지)를 파악하는 데는 이 접미사가 유일한 단서**가 되는 경우가 많다. 스택 덤프에서 값을 재해석할 때 이 점을 놓치면 완전히 엉뚱한 숫자로 잘못 읽게 된다.

## 화면/코드에서 보이는 징후
- `movapd xmm0, [rax]` — double 2개짜리 정렬된 블록 이동
- `movupd xmm1, [rdx+8]` — 정렬 미보장 double 블록 이동
- `movapd`/`movupd` 뒤에 `addpd`/`mulpd`가 이어지면 double 배열 벡터 연산

## 가장 먼저 할 것
1. 접미사가 `PD`임을 확인해 대상 데이터가 (float가 아니라) double 2개짜리임을 인지한다.
2. `A`(Aligned)인지 `U`(Unaligned)인지로 정렬 보장 여부를 판단한다([REV-0386](rev-0386-movaps.md)/[REV-0387](rev-0387-movups.md)와 같은 논리).
3. 뒤따르는 산술 SIMD 명령(`addpd`, `mulpd`, `subpd`) 유무로 순수 이동인지 계산인지 구분한다.

## 단계별 절차
**1) double 배열 복사 인식**
```asm
movapd xmm0, [rsi]     ; double[2] 로드
movapd [rdi], xmm0      ; double[2] 저장
```
**2) 정렬 여부 확인**
소스/목적지 주소가 스택 지역 변수(정렬 보장)인지 임의 포인터(정렬 미보장)인지 확인해 왜 `A`/`U` 중 하나가 선택됐는지 판단한다.

## 명령어/단축키
- x64dbg/GDB의 XMM 레지스터 뷰에서 double 2개로 해석된 값을 직접 확인 (GDB: `p $xmm0.v2_double`).
- IDA F5 디컴파일에서 `double` 배열/구조체 대입 형태로 확인.

## 출력 해석
- x64dbg XMM 패널에서 값 표시 형식을 "double"로 바꾸면 2개의 64비트 실수 값을 바로 읽을 수 있다.
- GDB `p/x $xmm0.uint64`로 원시 64비트 두 덩어리를 16진수로 볼 수도 있다.

## 흔한 실수
- `PS`와 `PD`가 서로 다른 하드웨어 이동 경로를 쓴다고 착각하는 것 — `MOV` 계열에서는 옮기는 비트 자체는 동일하고, 접미사는 값 해석에 대한 표기일 뿐이다(단, 계산 명령인 `ADDPS`/`ADDPD`는 실제로 다르게 계산한다는 점은 주의).
- double 배열인데 `PS` 명령으로 착각해서 값을 4개의 float로 잘못 해석하는 것 — `PD`는 반드시 2개의 64비트 값으로 나눠 읽어야 한다.

## 막혔을 때 다음 체크
- 값이 이상한 float로 보인다면 → `PS`가 아니라 `PD` 명령인지 다시 확인하고 64비트 단위로 재해석.
- 정렬 크래시가 의심되면 → [REV-0386](rev-0386-movaps.md)의 정렬 확인 절차를 그대로 적용(주소 % 16 == 0 여부).

## 미니 예제

**예제 1 — double 2개 구조체 복사**
```c
typedef struct { double x, y; } Point2D;
Point2D a = b;
```
```asm
movapd xmm0, [rdx]
movapd [rcx], xmm0
```

**예제 2 — 정렬 미보장 double 배열 복사**
```c
double *src = get_unaligned_ptr();
memcpy(dst, src, 16);
```
```asm
movupd xmm0, [rax]
movupd [rdi], xmm0
```

**예제 3 — double 벡터 연산의 일부**
```asm
movapd xmm0, [rsi+rcx*8]
addpd  xmm0, xmm1
movapd [rdi+rcx*8], xmm0
```

**예제 4 — 단일 double 변수는 MOVSD로, 배열은 MOVAPD로**
```c
double scale(double x, double factor) { return x * factor; } // 인자 1개: movsd
Point2D pts[2];  // double 4개: movapd/movupd로 블록 이동 가능
```
```asm
; 단일 값 인자 전달은 보통 movsd로 처리됨 (본 문서 범위 밖, 참고용)
movsd  xmm0, xmm0
```

## 관련 글
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0387 — MOVUPS: 비정렬 XMM 레지스터 이동
- REV-0389 — MOVDQA와 MOVDQU: 정수 XMM 이동
- REV-0390 — ADDPS와 ADDSS: SIMD 병렬/단일 덧셈

## 출처/검증
- `MOVAPD`/`MOVUPD` 명령어 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A/2B, "MOVAPD—Move Aligned Packed Double-Precision Floating-Point Values" / "MOVUPD" 섹션 기준 (2026-09-08 검증).
- SSE/SSE2 접미사 규칙(PS/PD/SS/SD): Intel SDM Volume 1, "SSE2 Extensions" 챕터 기준.
