---
id: REV-0390
title: "ADDPS와 ADDSS: SIMD 병렬/단일 덧셈"
slug: "rev-0390-addps-addss"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - addps
  - ADDPS
  - addss
  - ADDSS
  - addps instruction
  - addss instruction
  - addps 명령어
  - addss 명령어
  - packed add
  - scalar add
  - float 덧셈
  - xmm
  - XMM
  - SSE
  - "addps xmm0"
  - "addss xmm0"
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - addps 뭐임
  - addss 뭐임
  - addps addss 차이
  - ps ss 접미사 차이
  - float 덧셈 어셈블리
symptom_keywords:
  - addps addss 차이를 모르겠음
  - float 덧셈이 add 대신 addss로 되어있음
  - scalar와 packed 차이를 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`ADDPS`는 두 XMM 레지스터에 담긴 **4개의 single-precision float를 각각 병렬로 더하고**, `ADDSS`는 그중 **맨 아래 float 하나만 더하는(scalar)** SSE 명령이다.

## 언제 검색해야 하나
- `float a + b;`처럼 단순해 보이는 C 코드가 정수 `ADD`가 아니라 `addss`로 컴파일된 이유를 알고 싶을 때
- 배열 전체를 더하는 반복문이 `addps`를 쓰는 벡터화된 형태로 컴파일된 것을 볼 때
- `PS`(packed)와 `SS`(scalar) 접미사가 실제 연산에서 어떤 차이를 만드는지 정리하고 싶을 때

## 핵심 개념

### 정수 ADD와 무엇이 다른가
정수 `ADD`(REV-0047)는 범용 레지스터(EAX 등)에 대한 정수 덧셈이며 부호/오버플로 플래그를 세팅한다. `ADDPS`/`ADDSS`는 완전히 별개의 명령 집합(SSE)으로, **XMM 레지스터 안의 부동소수점 값을 IEEE 754 규칙에 따라 더한다.** x86/x64에서 `float`/`double` 연산은 정수 ALU가 아니라 이 SSE(또는 구식 x87 FPU) 유닛을 거친다는 점이 리버싱 초심자가 처음 헷갈리는 부분이다.

### Intel 문법과 PS/SS 차이
```
ADDPS xmm_dest, xmm/m128_src   ; dest의 4개 float 각각에 src의 대응 float를 더함 (병렬)
ADDSS xmm_dest, xmm/m32_src    ; dest의 맨 아래(0번째) float 하나에만 src의 0번째 float를 더함
```
- `ADDPS`: `dest[0..3] = dest[0..3] + src[0..3]` — 4개의 덧셈이 동시에 일어난다.
- `ADDSS`: `dest[0] = dest[0] + src[0]` — dest의 1,2,3번째 값(비트)은 **그대로 유지**된다(변경 없음). src가 메모리면 32비트(float 1개)만 읽는다.

즉 **일반 스칼라 `float` 변수 하나를 더하는 C 코드도 XMM 레지스터를 쓰는 `ADDSS`로 컴파일된다** — x64에서는 부동소수점 계산에 XMM 레지스터를 표준으로 쓰기 때문이다(x87 FPU 스택은 레거시 32비트 코드에서만 흔하다).

### 레지스터/메모리 효과와 방향
목적지(첫 번째 오퍼랜드)가 곧 누산기 역할을 한다: 결과가 dest에 그대로 덮어써진다. `dest = dest + src` 형태로 XOR/ADD 같은 정수 산술 명령과 방향 규칙은 동일하다(첫 오퍼랜드가 dest).

### 플래그 변화
`ADDPS`/`ADDSS`는 **범용 EFLAGS(ZF/SF/CF/OF 등)를 전혀 건드리지 않는다.** 대신 부동소수점 예외 상태를 담는 별도의 레지스터인 **MXCSR**(부동소수점 제어/상태 레지스터)의 비트가 갱신된다(예: Overflow, Underflow, Invalid Operation, Precision 플래그). 일반적인 정수 조건 분기(`jz`, `jg` 등)는 이 MXCSR을 직접 참조하지 않으므로, 부동소수점 비교 결과로 분기하려면 별도의 비교 명령(`COMISS`/`UCOMISS` 등, 본 배치 범위 밖)이 필요하다.

### 신호 있음/없음 관점
부동소수점 덧셈에는 애초에 signed/unsigned 구분이 없다(IEEE 754는 부호 비트를 값의 일부로 포함). 다만 NaN, 무한대, 반올림 오차 같은 부동소수점 특유의 문제는 정수 연산과 다르게 발생할 수 있다는 점만 인지하면 된다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴
- **스칼라 float 덧셈** (`float c = a + b;`): `movss xmm0, a` → `addss xmm0, b` → 결과를 저장 또는 반환값 레지스터(XMM0)에 유지.
- **배열 합산 벡터화**: 컴파일러가 반복문을 자동 벡터화하면 4개씩 묶어 `addps`로 처리하고, 배열 크기가 4의 배수가 아니면 남는 부분을 스칼라 루프로 마무리한다.

### IDA/Ghidra 디컴파일
`addss`는 대부분 `fVar1 = fVar2 + fVar3;` 형태의 평범한 float 덧셈으로 정리된다. `addps`는 배열 루프 안에 있으면 그대로 루프로 남거나, 짧은 고정 크기(4개)라면 `v[0]+=a[0]; v[1]+=a[1]; ...` 식으로 풀어서 보여주기도 한다.

## 화면/코드에서 보이는 징후
- `movss xmm0, [rdi]` → `addss xmm0, [rsi]` — 스칼라 float 두 개를 더함
- 함수 반환 직전 `addss xmm0, xmm1` 뒤 `ret` — float 반환값(XMM0) 계산
- 루프 안의 `movaps`/`movups` + `addps` 조합 — float 배열의 원소별 벡터 합산

## 가장 먼저 할 것
1. 접미사가 `PS`(4개 병렬)인지 `SS`(1개만)인지 확인한다.
2. 목적지 XMM 레지스터가 이후 함수 반환값(XMM0)으로 쓰이는지 확인한다(float/double 반환 관례, REV-0071 CALL 참고).
3. `PS`라면 반복문 형태로 벡터화된 배열 연산인지 확인한다.

## 단계별 절차
**1) 스칼라 float 덧셈 인식**
```asm
movss  xmm0, [rbp-4]   ; a
addss  xmm0, [rbp-8]   ; xmm0 = a + b
movss  [rbp-12], xmm0  ; c = xmm0
```
**2) 벡터화된 배열 합산 인식**
```asm
loop_top:
    movaps xmm0, [rsi+rcx*4]
    addps  xmm0, [rdi+rcx*4]
    movaps [rsi+rcx*4], xmm0
    add    rcx, 4
    cmp    rcx, count
    jl     loop_top
```

## 명령어/단축키
- x64dbg/GDB: XMM 레지스터를 float(단일)/float×4(패킹) 형식으로 전환해 값 확인 (GDB: `p $xmm0.v4_float`).
- IDA F5: float 반환 함수는 `return (float)(...)` 형태로 정리되며, `addss`는 `+` 연산자로 단순화됨.

## 출력 해석
- `addss` 결과는 dest XMM의 0번째 float만 바뀌고 나머지 96비트는 원래 dest 값 그대로 유지된다 — 디버거로 확인 시 1,2,3번째 값이 그대로인지 보면 SS/PS를 헷갈리지 않았는지 검증할 수 있다.
- 함수의 반환 타입이 `float`/`double`이면 `RET` 직전 XMM0 값을 확인하는 것이 정수 함수의 EAX/RAX 확인과 동일한 역할을 한다.

## 흔한 실수
- `ADDSS`가 dest의 1~3번째 값을 0으로 지운다고 착각하는 것 — 실제로는 **원래 값 그대로 보존**된다(변경되는 건 0번째뿐).
- `addps`/`addss`가 EFLAGS(ZF 등)를 세팅한다고 가정하고 바로 뒤에 `jz`를 기대하는 것 — 부동소수점 연산은 MXCSR을 갱신할 뿐 일반 조건 분기에 쓰이는 EFLAGS는 바꾸지 않는다.
- 정수 `ADD`와 `ADDPS`/`ADDSS`를 완전히 같은 명령의 다른 이름이라고 오해하는 것 — 서로 다른 명령어 집합(GPR vs SIMD/FP)이며 인코딩과 동작 원리 자체가 다르다.

## 막혔을 때 다음 체크
- 덧셈 뒤에 조건 분기가 이어지면 → 그 사이에 `comiss`/`ucomiss` 같은 별도 비교 명령이 있는지 확인(직접 `addss` 결과로 분기하지 않는다).
- 반환값이 이상하면 → 함수가 `float`를 반환하는지 확인하고 `RET` 직전 XMM0(전체 128비트 중 하위 32비트)을 본다.

## 미니 예제

**예제 1 — 스칼라 float 덧셈과 반환**
```c
float add(float a, float b) { return a + b; }
```
```asm
addss xmm0, xmm1   ; Windows/SysV x64 모두 첫 float 인자는 xmm0, 두번째는 xmm1
ret                 ; 결과는 xmm0에 그대로 남아 반환값
```

**예제 2 — 배열 4원소 병렬 합산**
```c
float c[4];
for (int i = 0; i < 4; i++) c[i] = a[i] + b[i];
```
```asm
movaps xmm0, [rax]   ; a[0..3]
addps  xmm0, [rbx]    ; + b[0..3]
movaps [rcx], xmm0    ; c[0..3]
```

**예제 3 — 누적 합(스칼라)**
```c
float sum = 0;
for (int i = 0; i < n; i++) sum += arr[i];
```
```asm
xorps  xmm0, xmm0      ; sum = 0.0 (부동소수점 제로화, REV-0392 참고)
loop_top:
    addss xmm0, [rsi+rcx*4]
    inc   rcx
    cmp   rcx, n
    jl    loop_top
```

## 관련 글
- REV-0391 — SUBPS와 MULPS: SIMD 뺄셈과 곱셈
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0392 — PXOR: XMM 레지스터 초기화와 XOR

## 출처/검증
- `ADDPS`/`ADDSS` 명령어 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "ADDPS—Add Packed Single-Precision Floating-Point Values" / "ADDSS" 섹션 기준 (2026-09-08 검증).
- MXCSR 레지스터와 부동소수점 예외 플래그: Intel SDM Volume 1, "MXCSR Control and Status Register" 챕터 기준.
- x64 부동소수점 반환값 XMM0 관례: Microsoft Learn "x64 calling convention" 및 System V AMD64 ABI 공식 문서 기준.
