---
id: REV-0392
title: "PXOR: XMM 레지스터 초기화와 XOR"
slug: "rev-0392-pxor"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - pxor
  - PXOR
  - pxor instruction
  - pxor 명령어
  - xorps
  - XORPS
  - xmm zeroing
  - xmm 제로화
  - "pxor xmm0, xmm0"
  - simd zeroing idiom
  - 제로화 관용구
  - xmm
  - XMM
  - SSE2
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - pxor 뭐임
  - pxor가 뭐죠
  - pxor 명령
  - PXOR 명령어
  - pxor xmm0 xmm0 왜함
  - xor eax eax pxor 차이
symptom_keywords:
  - pxor xmm0 xmm0가 왜 나오는지 모르겠음
  - 함수 시작에 pxor가 있음
  - xmm 레지스터를 왜 xor로 초기화하는지 모르겠음
  - simd 제로화 관용구가 뭔지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`PXOR`는 두 XMM 레지스터를 128비트 전체에 대해 비트 단위 XOR하는 정수 SIMD 명령이며, 특히 `pxor xmm0, xmm0`는 [`xor eax, eax`](rev-0057-xor.md)의 SIMD 버전에 해당하는 "XMM 레지스터를 통째로 0으로 만드는" 표준 관용구다.

## 언제 검색해야 하나
- 함수 시작부나 루프 진입 직전에 `pxor xmm0, xmm0` 같은 코드가 나와서 이게 뭘 계산하는 건지 헷갈릴 때
- `xorps xmm0, xmm0`와 `pxor xmm0, xmm0`가 둘 다 나와서 차이가 있는지 궁금할 때
- SIMD 코드에서 "값을 0으로 초기화하는 지점"을 빠르게 찾아야 할 때(float/double 배열의 합계 누산기 초기화 등)

## 핵심 개념

### Intel 문법과 오퍼랜드
```
PXOR xmm_dest, xmm/m128_src
```
- `dest = dest XOR src`, 128비트 전체에 대해 비트 단위로 계산.
- 정수 SIMD 계열(`P`=Packed integer)이므로 실수 해석 없이 순수 비트 연산으로 취급한다. 부동소수점 버전인 `XORPS`(single-precision 취급)/`XORPD`(double-precision 취급)도 존재하며, 셋 다 결과 비트는 동일하다 — 옮기는 것과 마찬가지로 접미사는 "이 데이터를 무엇으로 해석할 것인가"의 표시일 뿐 XOR 자체의 비트 결과는 같다.

### `pxor xmm0, xmm0` — SIMD 제로화 관용구 (가장 중요)
정수 레지스터에서 `xor eax, eax`가 "EAX를 0으로 만드는" 표준 관용구인 것처럼, XMM 레지스터에서는 **`pxor xmm0, xmm0`(또는 `xorps`/`xorpd` 버전)가 완전히 동일한 역할**을 한다. 같은 레지스터를 자기 자신과 XOR하면 원래 값이 무엇이었든 결과는 항상 128비트 전부 0이다.

**왜 `MOVAPS xmm0, [상수 0.0f]`처럼 메모리에서 0을 로드하지 않고 `PXOR`를 쓰는가:**
1. **메모리 접근이 필요 없다** — 상수 0을 담은 메모리 위치를 따로 두고 로드할 필요 없이 레지스터만으로 즉시 0을 만든다(캐시/메모리 지연 없음).
2. **인코딩이 짧다** — 레지스터-레지스터 연산이라 즉시값/메모리 오�リ랜드 인코딩이 필요 없다.
3. **제로화 관용구로 특별 인식** — 많은 x86 CPU가 `xor reg, reg`와 마찬가지로 `pxor xmm, 같은xmm`도 실행 유닛 의존성을 끊는 제로화 관용구로 인식해 빠르게 처리한다.

이 관용구는 **함수 시작부에서 부동소수점 누산기(합계, 카운터)를 0.0으로 초기화**하거나, **memset(buf, 0, n)의 SIMD 전개에서 채울 값(0)을 준비**할 때 압도적으로 자주 등장한다. `xor eax, eax`를 볼 때와 완전히 같은 사고방식으로 "레지스터 초기화"라고 즉시 인식하면 된다.

### 플래그 변화
`PXOR`는 정수 SIMD 명령이므로 **EFLAGS를 전혀 건드리지 않는다**(정수 `XOR`가 ZF/CF/OF 등을 세팅하는 것과 다르다 — XMM 명령은 범용 플래그 레지스터 체계와 분리되어 있다).

### 레지스터/메모리 효과
소스가 메모리일 수도 있지만(`pxor xmm0, [rax]`), 제로화 목적이라면 거의 항상 `dest`와 `src`가 같은 레지스터다. 자기 자신이 아닌 다른 값과 XOR하면 진짜 비트 연산(마스킹, 토글) 목적일 수 있다 — 이 경우는 [XOR](rev-0057-xor.md) 문서의 "XOR 기반 인코딩" 논리가 그대로 적용된다(다만 SIMD 버전으로 16바이트를 한 번에 처리한다는 차이).

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴
- 함수가 `float`/`double`을 반환하거나 지역 누산기를 쓸 때, 프롤로그 근처에서 `pxor xmm0, xmm0`(또는 `xorps`)로 XMM0을 미리 0으로 만들어 둔다.
- `memset(buf, 0, n)`의 SIMD 전개에서 채울 값을 준비하는 첫 단계로 등장한다([REV-0389](rev-0389-movdqa-movdqu.md) 참고).
- 벡터/구조체를 0으로 초기화하는 C 코드(`Vec4 v = {0,0,0,0};`)가 `pxor` 한 줄로 컴파일되는 경우가 흔하다.

### IDA/Ghidra 디컴파일
`pxor xmm0, xmm0`는 거의 항상 `0` 또는 `0.0`으로의 대입(`fVar1 = 0.0;`, 구조체 필드 전체를 0으로)으로 단순화된다. 원본이 XOR였다는 사실은 디스어셈블리에서만 확인 가능하다 — 이는 정수 [`XOR`](rev-0057-xor.md) 문서에서 설명한 것과 동일한 현상이다.

## 화면/코드에서 보이는 징후
- 함수 시작부의 `pxor xmm0, xmm0` — float/double 반환값 또는 누산기 초기화
- `pxor xmm0, xmm0` 직후 `movdqu [buf], xmm0` 반복 — memset(0)의 SIMD 전개
- 루프 진입 전 `pxor xmm1, xmm1` — SIMD 합산 누산기 초기화
- `pxor` 뒤 오퍼랜드가 서로 다른 레지스터 — 제로화가 아니라 실제 비트 마스킹/토글 연산

## 가장 먼저 할 것
1. 두 오퍼랜드가 완전히 같은 레지스터인지 확인한다(같으면 100% 제로화).
2. 제로화라면 그 XMM 레지스터가 이후 반환값, 누산기, memset 값 중 어디에 쓰이는지 확인한다.
3. 오퍼랜드가 다르면 진짜 XOR 연산(암호화, 마스크 토글)일 가능성을 검토한다.

## 단계별 절차
**1) 반환값 0.0 초기화 인식**
```asm
pxor xmm0, xmm0   ; return 0.0;에 해당
ret
```
**2) memset(0) 준비 단계 인식**
```asm
pxor   xmm0, xmm0
movdqu [rdi], xmm0
movdqu [rdi+16], xmm0
```
**3) 벡터 누산기 초기화 인식**
```asm
pxor xmm1, xmm1        ; sum = 0
loop_top:
    addps xmm1, [rsi+rcx*4]
    add   rcx, 4
    cmp   rcx, n
    jl    loop_top
```

## 명령어/단축키
- x64dbg/GDB: `pxor` 실행 전후 XMM 레지스터 값이 전부 0으로 바뀌는지 확인 (GDB: `p/x $xmm0.uint64`가 `{0x0, 0x0}`이면 완전 제로화 확인).
- IDA: F5 디컴파일 결과에서 `pxor xmm0,xmm0`가 대체로 `0`으로만 보이므로, 정확한 명령을 확인하려면 디스어셈블리 뷰(Space로 전환)를 봐야 한다.

## 출력 해석
- 디컴파일러가 `pxor xmm0, xmm0`를 단순히 `0`으로 표기했다고 해서 "계산이 없다"고 오해하면 안 된다 — 원본 명령이 XOR인지 MOV인지는 리버싱 목적(예: 코드 시그니처/패턴 매칭)에 따라 중요할 수 있다.

## 흔한 실수
- `pxor xmm0, xmm0`를 정수 `xor eax, eax`와 무관한 별개 개념이라고 생각하는 것 — 원리(자기소거로 0 생성)와 목적(레지스터 제로화 관용구)이 완전히 동일하다. [REV-0057 XOR](rev-0057-xor.md) 문서의 제로화 논리를 그대로 적용하면 된다.
- `pxor`가 뭔가 복잡한 정수 XOR 연산이라고 오해해서 값을 억지로 추적하려는 것 — 오퍼랜드가 같으면 무조건 결과는 0이다.
- `PXOR`와 `XORPS`/`XORPD`가 서로 다른 결과를 낸다고 착각하는 것 — 순수 비트 XOR 결과는 셋 다 동일하고, 접미사는 CPU 파이프라인 상의 도메인 힌트(정수 vs 부동소수점 유닛)일 뿐 계산 결과에는 차이가 없다.

## 막혔을 때 다음 체크
- `pxor xmm0, xmm0` 뒤 값이 계속 헷갈리면 → 두 오퍼랜드가 정말 같은 레지스터인지(대소문자까지) 다시 확인.
- 함수가 왜 float 0.0을 반환하는지 모르겠으면 → 함수 원형(반환 타입이 float/double인지) 확인.
- memset처럼 보이는데 확신이 없으면 → 직후 몇 줄에 `movdqu`/`movups`가 같은 레지스터를 반복 저장하는지 확인.

## 미니 예제

**예제 1 — float 0.0 반환**
```c
float zero(void) { return 0.0f; }
```
```asm
pxor xmm0, xmm0
ret
```

**예제 2 — 구조체(Vec4) 0 초기화**
```c
Vec4 v = {0, 0, 0, 0};
```
```asm
pxor   xmm0, xmm0
movaps [rdi], xmm0
```

**예제 3 — memset(buf, 0, n)의 SIMD 전개**
```c
memset(buf, 0, 32);
```
```asm
pxor   xmm0, xmm0
movdqu [rdi], xmm0
movdqu [rdi+16], xmm0
```

**예제 4 — 벡터 합산 누산기 초기화**
```c
float sum4[4] = {0,0,0,0};
for (...) sum4[i] += a[i];  // 벡터화된 형태
```
```asm
pxor  xmm1, xmm1     ; 누산기 0으로 시작
addps xmm1, [rsi]     ; 누적
```

## 관련 글
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0389 — MOVDQA와 MOVDQU: 정수 XMM 이동
- REV-0393 — PADDB PADDW PADDD: SIMD 정수 덧셈

## 출처/검증
- `PXOR` 명령어 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "PXOR—Logical Exclusive OR" 섹션 기준 (2026-09-08 검증).
- `pxor reg, reg`/`xorps reg, reg` 제로화 관용구와 CPU 최적화 근거: Agner Fog, "Optimizing subroutines in assembly language" (레지스터 제로화 관용구 섹션) 기준.
