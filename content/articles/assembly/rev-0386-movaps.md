---
id: REV-0386
title: "MOVAPS: 정렬된 XMM 레지스터 이동"
slug: "rev-0386-movaps"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - movaps
  - MOVAPS
  - movaps instruction
  - movaps 명령어
  - xmm
  - XMM
  - xmm register
  - xmm 레지스터
  - SSE
  - aligned move
  - 정렬 이동
  - 16바이트 정렬
  - 16-byte alignment
  - "movaps xmm0"
  - packed single precision
  - GPF alignment fault
  - 정렬 예외
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - movaps 뭐임
  - movaps가 뭐죠
  - movaps 명령
  - MOVAPS 명령어
  - xmm 레지스터가 뭐임
  - movaps 크래시
symptom_keywords:
  - movaps에서 크래시가 남
  - movaps 실행 중 예외 발생
  - xmm 레지스터가 뭔지 모르겠음
  - simd 코드가 갑자기 나옴
  - float 배열 복사가 movaps로 되어있음
last_verified: "2026-09-08"
---

## 한 줄 요약
`MOVAPS`는 128비트 XMM 레지스터와 **16바이트 정렬된** 메모리(또는 다른 XMM 레지스터) 사이에서 4개의 single-precision(32비트) float를 한 번에 통째로 옮기는 SIMD 명령이며, 메모리 오퍼랜드가 16바이트 경계에 있지 않으면 예외(#GP)를 낸다.

## 언제 검색해야 하나
- 디스어셈블리에 `movaps xmm0, [rax]` 같은 코드가 처음 나와서 XMM이 뭔지부터 막힐 때
- 함수 시작부에 `movaps` 여러 줄이 몰려 있어서(레지스터 저장/복원) 이게 SIMD 계산인지 단순 데이터 이동인지 헷갈릴 때
- `movaps`가 실행되다가 크래시(예외)가 나서 "정렬이 안 맞은 것 같다"는 실마리를 확인하고 싶을 때
- `float`/`double` 배열을 다루는 C 코드가 왜 스칼라 연산 대신 SIMD 명령으로 컴파일됐는지 궁금할 때

## 핵심 개념

### XMM 레지스터란
x86/x64 CPU는 SSE(Streaming SIMD Extensions) 확장으로 **128비트 XMM 레지스터**를 갖는다. x64에서는 `xmm0`~`xmm15`(x86에서는 `xmm0`~`xmm7`)가 존재하며, 각 XMM 레지스터는 다음 중 하나로 해석될 수 있다:
- 4개의 32비트 single-precision float (packed single, `PS`)
- 2개의 64비트 double-precision float (packed double, `PD`)
- 16/8/4개의 8/16/32비트 정수 (packed integer)
- 맨 앞 하나의 값만 쓰는 scalar 형태(`SS`=scalar single, `SD`=scalar double)

즉 `PS`/`PD`는 "레지스터 하나에 여러 값을 나란히 담아 한 번에 처리(packed)"한다는 뜻이고, `SS`/`SD`는 "레지스터의 맨 아래 한 칸만 쓴다(scalar)"는 뜻이다. 이 접미사 규칙(P=packed, S=scalar, S=single, D=double)은 다른 SIMD 명령에도 그대로 적용된다.

### Intel 문법과 오퍼랜드
```
MOVAPS xmm_dest, xmm/m128_src
MOVAPS xmm/m128_dest, xmm_src
```
- 오퍼랜드는 XMM 레지스터 또는 128비트(16바이트) 메모리이며, 둘 중 하나는 반드시 XMM 레지스터여야 한다(메모리-메모리 이동 불가는 일반 MOV와 동일).
- `A`는 **Aligned**, `PS`는 **Packed Single-precision**의 약자다. 즉 이름 자체가 "정렬된 상태로 4개의 float를 통째로 옮긴다"는 뜻을 담고 있다.

### 정렬 요구사항 — 리버싱에서 가장 중요한 특징
`MOVAPS`의 메모리 오퍼랜드는 **반드시 16바이트 경계(주소가 0x10의 배수)** 에 있어야 한다. 정렬이 맞지 않으면 CPU가 **#GP(General Protection Fault)** 예외를 발생시켜 프로그램이 즉시 크래시한다. 이는 스칼라 `MOV`에는 없는, SIMD 정렬 명령만의 엄격한 제약이다. 반대로 정렬 여부와 무관하게 항상 동작하는 버전이 [MOVUPS](rev-0387-movups.md)(Unaligned)다.

### 레지스터/메모리 효과
- 데이터 방향은 일반 `MOV`와 동일하게 첫 번째 오퍼랜드가 목적지, 두 번째가 소스다.
- 이동 크기는 항상 128비트(16바이트) 전체이며, 값의 의미(그게 float 4개인지 그냥 임의의 바이트 뭉치인지)는 해석하지 않고 비트 그대로 복사한다.

### 플래그 변화
`MOVAPS`는 **EFLAGS를 전혀 건드리지 않는다.** 데이터 이동일 뿐 산술/논리 연산이 아니기 때문이다.

### 스택/RSP/RIP 변화
없음. 단, 함수 프롤로그에서 콜리-세이브(callee-saved) XMM 레지스터를 스택에 저장할 때 `movaps [rsp+N], xmm6` 형태로 등장하기도 한다(Windows x64 ABI에서는 `xmm6`~`xmm15`가 non-volatile).

### 컴파일러가 MOVAPS를 쓰는 이유
C 소스에 명시적인 SIMD 코드가 전혀 없어도, 컴파일러(GCC/Clang/MSVC)는 최적화 단계에서 다음과 같은 상황을 자동으로 벡터화(auto-vectorization)해서 `MOVAPS` 계열 명령을 생성한다:
- `float buf[4]` 같은 구조체/배열을 통째로 복사하거나 초기화할 때
- 반복문에서 4개씩 묶어 float 연산을 처리할 수 있을 때(루프 벡터화)
- `memcpy`/구조체 대입에서 크기가 16의 배수인 블록을 옮길 때

즉 **스칼라처럼 보이는 C 코드가 `MOVAPS`로 컴파일되는 것은 매우 흔한 일**이며, 이것이 "SIMD를 쓴다는 것 자체가 특별한 알고리즘을 의미하지 않는다"는 점을 아는 것이 중요하다.

### IDA/Ghidra 디컴파일에서 보이는 방식
IDA F5와 Ghidra 모두 `movaps`를 대부분 구조체 대입(`*(_QWORD *)(dst) = ...`, `local_var = src_var;`) 또는 float 배열 복사 형태로 정리한다. 벡터화된 루프는 종종 `undefined1 auVarN [16];` 같은 임시 128비트 변수나 SIMD 인트린식(`_mm_load_ps` 등)으로 표현되기도 한다.

## 화면/코드에서 보이는 징후
- 함수 프롤로그/에필로그에서 `movaps [rsp+0x20], xmm6` 같은 저장/복원 — non-volatile XMM 레지스터 보존
- 구조체/배열 복사 코드에서 `movaps xmm0, [rax]` 뒤 `movaps [rdx], xmm0` — 16바이트 블록 통째 복사
- 루프 안에서 `movaps` + `addps`/`mulps` 조합 — 벡터화된 산술 루프
- 크래시 덤프에서 `movaps` 명령 주소에서 예외 발생 — 정렬 안 된 포인터를 SIMD 코드에 넘겼을 가능성

## 가장 먼저 할 것
1. 오퍼랜드가 XMM-XMM인지 XMM-메모리인지 확인한다.
2. 메모리 오퍼랜드라면 그 주소가 16바이트 정렬되어 있을 것으로 기대되는 상황인지(스택 정렬, `malloc`/`_aligned_malloc` 결과 등) 확인한다.
3. 앞뒤로 `addps`/`mulps`/`pxor` 등 다른 SIMD 명령이 있는지 봐서 단순 데이터 이동인지 실제 벡터 연산인지 구분한다.

## 단계별 절차
**1) 레지스터 저장/복원 인식**
```asm
sub  rsp, 0x30
movaps [rsp+0x20], xmm6
...
movaps xmm6, [rsp+0x20]
add  rsp, 0x30
ret
```
→ `xmm6`을 함수 시작에서 스택에 백업했다가 끝에서 복원(콜리-세이브 관례).

**2) 정렬 크래시 원인 진단**
디버거(x64dbg/GDB)로 예외 발생 주소를 확인하고, 소스 오퍼랜드 레지스터(예: `rax`)의 값을 확인해 `주소 % 16 != 0`이면 정렬 문제로 확정한다.

**3) 벡터화된 float 복사 구분**
`movaps` 뒤에 산술 명령 없이 바로 다른 `movaps`(저장)만 이어지면 순수 복사(`memcpy`류)로 판단한다.

## 명령어/단축키
- IDA: XMM 레지스터 값은 디버거 레지스터 창의 "SSE"/"XMM" 하위 탭에서 확인, F5로 디컴파일 시 구조체 대입으로 정리됨
- x64dbg: 레지스터 패널 하단 XMM 레지스터 표시 영역에서 `xmm0`~`xmm15` 각 16바이트 값을 16진수/float로 확인 가능
- GDB/Pwndbg: `info registers xmm0`, `p $xmm0.v4_float`로 4개의 float 값을 각각 확인

## 출력 해석
- x64dbg의 XMM 뷰는 16바이트를 4개의 float(또는 다른 포맷)로 나눠 보여준다 — `movaps` 실행 전후로 이 값이 통째로 바뀌는지 비교하면 이동 여부를 바로 확인할 수 있다.
- 예외 발생 시 x64dbg/WinDbg는 "Access violation"을, GDB는 `SIGSEGV`(정렬 문제는 실제로는 `SIGSEGV`가 아니라 `SIGSEGV`로 잡히는 #GP)로 보고한다 — 주소를 16으로 나눠 나머지를 확인하는 습관을 들인다.

## 흔한 실수
- `MOVAPS`와 `MOVUPS`를 아무 데나 바꿔 써도 된다고 착각하는 것 — `MOVAPS`는 정렬이 안 맞으면 반드시 크래시한다. 디스어셈블리에서 어떤 명령이 쓰였는지가 곧 "이 메모리가 정렬되어 있다고 컴파일러가 확신했다"는 증거다.
- XMM 레지스터를 정수 레지스터(EAX 등)와 같은 방식으로 값 하나만 있다고 생각하는 것 — 128비트 안에 최대 4개의 32비트 값이 동시에 들어 있을 수 있다.
- `movaps`를 보고 무조건 "복잡한 SIMD 알고리즘"이라 겁먹는 것 — 대부분은 컴파일러가 자동 생성한 단순 복사/초기화다.

## 막혔을 때 다음 체크
- 크래시 원인이 `movaps`라면 → 소스/목적지 메모리 주소가 16의 배수인지 계산기로 확인.
- 어떤 값이 옮겨지는지 모르겠다면 → 디버거의 XMM 레지스터 뷰에서 float 4개로 해석된 값을 직접 확인.
- 이 코드가 계산인지 이동인지 헷갈리면 → 주변에 `addps`/`subps`/`mulps` 같은 산술 SIMD 명령이 있는지 검색.

## 미니 예제

**예제 1 — 구조체 복사 (정렬된 16바이트 블록)**
```c
typedef struct { float x, y, z, w; } Vec4;
Vec4 a = b;   // 16바이트, 정렬됨
```
```asm
movaps xmm0, [rdx]   ; b 로드
movaps [rcx], xmm0    ; a에 저장
```

**예제 2 — 함수 프롤로그의 XMM 레지스터 백업**
```asm
sub    rsp, 0x28
movaps [rsp], xmm6
```

**예제 3 — 정렬 안 된 포인터로 인한 크래시 상황**
```c
char buf[20];
float *p = (float *)(buf + 1); // 1바이트 오프셋이라 16정렬 아님
__m128 v = _mm_load_ps(p);      // 컴파일러가 movaps로 내렸다면 크래시
```

**예제 4 — 벡터화된 루프 일부**
```asm
loop_top:
    movaps  xmm0, [rsi+rcx*4]
    addps   xmm0, xmm1
    movaps  [rdi+rcx*4], xmm0
    add     rcx, 4
    cmp     rcx, count
    jl      loop_top
```

## 관련 글
- REV-0387 — MOVUPS: 비정렬 XMM 레지스터 이동
- REV-0388 — MOVAPD와 MOVUPD: Double Precision SIMD 이동
- REV-0389 — MOVDQA와 MOVDQU: 정수 XMM 이동
- REV-0392 — PXOR: XMM 레지스터 초기화와 XOR

## 출처/검증
- `MOVAPS` 명령어 동작, 정렬 요구사항, 예외 조건: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A/2B, "MOVAPS—Move Aligned Packed Single-Precision Floating-Point Values" 섹션 기준 (2026-09-08 검증).
- XMM 레지스터 구조와 SSE 개요: Intel SDM Volume 1, "SSE Extensions" 챕터 기준.
- Windows x64 ABI에서 XMM6-XMM15 non-volatile 규칙: Microsoft Learn "x64 calling convention" 공식 문서 기준.
