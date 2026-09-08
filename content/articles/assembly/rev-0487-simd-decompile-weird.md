---
id: REV-0487
title: "SIMD 명령이 나와서 디컴파일이 이상해 보일 때"
slug: "rev-0487-simd-decompile-weird"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - SIMD
  - XMM 레지스터
  - movaps
  - movups
  - movdqa
  - movdqu
  - pxor
  - paddd
  - vector instruction
  - 벡터 명령
  - SSE
  - AVX
  - packed data
  - __m128
  - undefined4 undefined8 배열
  - IDA XMM0
  - Ghidra auVar
aliases:
  - xmm 레지스터가 뭔지 모르겠음
  - movaps가 뭔지 모르겠음
  - 디컴파일에 undefined 배열이 나옴
  - SIMD 코드 읽는 법
  - 벡터 명령 리버싱
symptom_keywords:
  - 디컴파일 결과에 xmm0 xmm1이 계속 나옴
  - undefined1 auVar 배열이 나와서 이해가 안 됨
  - movaps movdqa 차이를 모르겠음
  - 단순 반복문인데 명령어가 16바이트씩 처리됨
  - SSE AVX 명령이 나오면 분석을 포기하게 됨
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
디컴파일 결과에 `xmm0`, `auVar1[16]`, `undefined1` 배열, `_mm_` 계열 함수가 잔뜩 보인다면 컴파일러가 반복문(주로 `memcpy`/`memset`/문자열 비교/배열 연산)을 SIMD(128/256비트 벡터) 명령으로 자동 최적화한 것이며, "이상한 코드"가 아니라 "한 번에 여러 바이트를 처리하는 빠른 버전의 평범한 코드"일 뿐이다.

## 언제 검색해야 하나
- Ghidra 디컴파일 결과에 `undefined1 auVar1 [16];`, `auVar1 = ZEXT816(...)` 같은 이상한 타입/배열이 잔뜩 보일 때
- IDA 디컴파일이나 디스어셈블리에 `movaps`, `movups`, `movdqa`, `movdqu`, `pxor`, `paddd`, `pcmpeqb` 같은 처음 보는 니모닉이 나올 때
- 단순해 보이는 `for` 루프 하나가 디스어셈블리에서는 이해할 수 없이 복잡한 XMM/YMM 명령 블록으로 바뀌어 있을 때
- `-O2`/`-O3` 최적화가 걸린 바이너리에서 반복문/배열 연산/문자열 함수가 유난히 알아보기 어려울 때

## 핵심 개념

### SIMD가 뭐고 왜 생겼는가
SIMD(Single Instruction, Multiple Data)는 "명령어 하나로 여러 데이터를 동시에 처리"하는 CPU 기능이다. 일반 정수 레지스터(`RAX` 등)는 한 번에 최대 8바이트(64비트)만 다루지만, SIMD 전용 레지스터인 `XMM0`~`XMM15`(128비트, SSE)나 `YMM0`~`YMM15`(256비트, AVX)는 한 번에 16바이트, 32바이트를 동시에 로드/연산/저장할 수 있다. 그래서 `memcpy(dst, src, 64)`처럼 큰 블록을 복사하거나, 배열 전체에 같은 연산을 반복하는 코드에서 컴파일러가 SIMD 명령을 즉시 활용한다.

이건 알고리즘이 바뀐 게 아니라 **같은 일을 하드웨어 차원에서 병렬로 처리**하는 것뿐이다. 즉 "SIMD가 나왔으니 뭔가 특별한 암호화/난독화겠지"라고 지레짐작할 필요가 없다 — 대부분은 그냥 최적화된 `memcpy`/`memset`/`strlen`/배열 합계 같은 흔한 연산이다.

### 자주 보이는 SIMD 명령 요약
| 명령 | 의미 |
|---|---|
| `movaps xmm0, [rax]` | Aligned Packed Single(정렬된 128비트 로드/저장). 주소가 16바이트 정렬 안 되면 예외(#GP) 발생 가능 |
| `movups xmm0, [rax]` | Unaligned Packed Single(정렬 여부 무관 로드/저장). 안전하지만 정렬된 경우보다 살짝 느릴 수 있음 |
| `movdqa` / `movdqu` | 정수형 128비트 데이터의 정렬/비정렬 이동 (Move Double Quadword Aligned/Unaligned) |
| `pxor xmm0, xmm0` | 128비트 정수 XOR. `xor eax, eax`의 XMM 버전으로, `xmm0`을 0으로 초기화할 때 흔히 쓰임 |
| `paddd`, `psubd` | 128비트 레지스터 안에서 32비트 정수 4개를 각각 동시에 더하기/빼기 (Packed Add/Sub Doubleword) |
| `pcmpeqb`, `pcmpeqd` | 바이트/더블워드 단위로 동시에 비교해서 같으면 모든 비트 1, 다르면 0으로 채움 |
| `pmovmskb` | 위 비교 결과(각 바이트의 최상위 비트)를 모아 일반 정수 레지스터의 비트마스크로 변환 — 비교 결과를 `if`문으로 쓸 때 등장 |
| `cvtsi2sd`, `cvttsd2si` | 정수 ↔ double 변환 (SIMD 레지스터를 스칼라 부동소수점 용도로도 사용) |

`movaps`/`movups`는 이름의 "aps"가 붙어도 정수 데이터를 옮기는 데 그냥 쓰이는 경우가 매우 흔하다 — 컴파일러가 "그냥 16바이트를 복사"하는 용도로 아무 SIMD 이동 명령이나 재사용하기 때문에, 이름의 "Single(단정도 실수)"이라는 원래 의미에 얽매이지 않아도 된다. `rev-0386-movaps.md`(REV-0386)에 `MOVAPS` 단독 상세 설명이 있다.

### 왜 디컴파일 결과가 이상해 보이는가
IDA/Ghidra의 디컴파일러는 정수/포인터/구조체 연산은 매우 잘 재구성하지만, SIMD 벡터 연산은 원래 C 소스에 없던 "컴파일러가 만들어낸 병렬 처리"이기 때문에 대응되는 고수준 C 문법이 없다. 그래서 디컴파일러는 다음과 같은 방식으로 어떻게든 표현한다.

- **Ghidra**: `undefined1 auVar1 [16];` 같은 "16바이트 크기의 정체불명 배열"이나 `unkbyte16`, `unkbyte32` 타입, `ZEXT816(...)`(8바이트를 16바이트로 제로 확장), `SUB164(...)` 같은 헬퍼 함수 형태로 표현. 이런 이름을 보면 "SIMD 레지스터를 억지로 배열/헬퍼 함수로 흉내낸 것"이라고 이해하면 된다.
- **IDA**: 인식이 잘 되면 `memcpy`/`memset`/`__memcmp_sse2` 같은 라이브러리 함수 호출로 깔끔하게 보여주지만, 인식이 안 되면 `xmm0 = _mm_loadu_si128(...)`, `_mm_storeu_si128(...)` 같은 인트린식(intrinsic) 함수 형태나 그냥 원본 SIMD 명령어를 그대로 유사 인라인어셈블리처럼 남겨둔다.

**전략**: 디컴파일된 SIMD 코드를 한 줄 한 줄 이해하려 하지 말고, 먼저 어셈블리 원문을 보고 "이게 결국 memcpy/memset/strlen/배열 합계/문자열 비교 중 무엇의 벡터화된 버전인가"부터 특정하는 게 훨씬 빠르다.

### 플래그, 스택, RIP 관점
- SIMD 데이터 이동 명령(`movaps`, `movdqa`, `movdqu`, `movups`)은 **EFLAGS를 전혀 바꾸지 않는다** — 정수 `MOV`와 마찬가지로 순수 데이터 이동이다.
- `pcmpeqb`/`pcmpeqd` 등 비교류도 일반 `CMP`처럼 `EFLAGS`를 바꾸는 게 아니라, 결과를 XMM 레지스터 자체에 비트마스크로 채워 넣는다 — 이후 `pmovmskb`로 일반 레지스터의 비트마스크로 뽑아내고, 그 값을 `TEST`/`CMP`로 검사해야 비로소 `EFLAGS`가 바뀐다.
- 스택/`RIP`에는 특별한 영향이 없다(일반 명령과 동일하게 다음 명령으로 순차 진행).
- 부호(signed/unsigned) 구분은 명령 종류에 따라 다르다 — 예를 들어 `paddd`는 부호와 무관하게 그냥 32비트 덧셈을 4개 동시에 하는 것이고(오버플로우 시 자르는 동작은 signed/unsigned 정수 덧셈과 동일), `pmaxsw`/`pmaxuw`처럼 이름에 `s`/`u`가 붙은 명령들은 signed/unsigned를 구분해서 최대값을 계산한다.

## 화면/코드에서 보이는 징후
```asm
movdqu  xmm0, xmmword ptr [rsi]
movdqu  xmm1, xmmword ptr [rsi+10h]
movdqu  xmmword ptr [rdi], xmm0
movdqu  xmmword ptr [rdi+10h], xmm1
add     rsi, 20h
add     rdi, 20h
sub     rcx, 20h
ja      loop_start
```
이런 블록을 보면 "32바이트씩 복사하는 memcpy 루프를 SIMD로 언롤(unroll)한 것"이라고 바로 인식하면 된다.

Ghidra 디컴파일 예:
```c
undefined1 auVar1 [16];
auVar1 = *(undefined1 (*) [16])(param_1 + i);
*(undefined1 (*) [16])(param_2 + i) = auVar1;
```

## 가장 먼저 할 것
1. SIMD 명령이 나오면 먼저 **몇 바이트 단위로 처리하는지**(`xmm`=16바이트, `ymm`=32바이트) 확인한다.
2. 로드-저장 패턴인지(`movdqu`로 읽고 그대로 다른 곳에 씀 → memcpy류), 초기화 패턴인지(`pxor xmm0, xmm0` → 0으로 채움, memset류), 비교 패턴인지(`pcmpeqb` + `pmovmskb` → 문자열 비교/탐색)부터 분류한다.
3. 원본 함수 이름(`memcpy`, `memset`, `strlen`, `strcmp` 등)이 IDA/Ghidra 함수 목록이나 심볼에 남아있는지 확인한다 — 남아있으면 이 블록이 그 함수의 인라인 버전이라고 바로 확정할 수 있다.

## 단계별 절차
**1) 반복 여부 확인**

SIMD 블록이 루프 안에 있는지(주소 증가 + 카운터 감소 + 조건 분기가 반복) 아니면 한 번만 실행되는지 본다. 루프면 큰 버퍼 처리, 한 번뿐이면 고정 크기(예: 16바이트 구조체 복사) 처리다.

**2) 명령 종류로 원래 연산 추정**

- `movaps`/`movups`/`movdqa`/`movdqu` 로드 후 그대로 저장 → `memcpy`
- `pxor xmm, xmm` 후 저장 반복 → `memset(ptr, 0, n)`
- `pcmpeqb` + `pmovmskb` + 분기 → 문자열/바이트 비교(`strcmp`/`memcmp`/`strlen`의 벡터화 버전)
- `cvtsi2sd`, `addsd`, `mulsd`, `divsd` 등 스칼라 부동소수점 명령(이름에 `sd`=scalar double, `ss`=scalar single) → 그냥 `double`/`float` 산술 연산(REV-0492 참고)

**3) 컴파일러 인식 여부 확인**

IDA `F5`로 디컴파일했을 때 `memcpy(...)`/`memset(...)` 같은 함수 호출로 깔끔히 나오면 그대로 이해하고 넘어간다. 안 나오면 어셈블리 원문 레벨에서 위 패턴 분류만 해도 충분하다 — 벡터 명령 하나하나의 정확한 의미까지 다 외울 필요는 없다.

**4) 필요하면 Intel SDM 인덱스로 개별 명령 검색**

생소한 명령(`pshufb`, `psadbw` 등)이 나오면 Intel SDM의 명령어 세트 레퍼런스(Volume 2)에서 이름으로 검색해서 정확한 의미를 확인한다.

## 명령어/단축키
- IDA: `F5`(디컴파일 — memcpy/memset 인식 확인), 레지스터 창에서 `XMM0`~`XMM15` 값 확인(View → Open subviews → CPU registers에서 XMM 표시 옵션)
- x64dbg: 레지스터 패널 하단의 "XMM" 섹션에서 각 XMM 레지스터를 16바이트 hex로 직접 확인 가능
- GDB/Pwndbg: `info registers xmm0`, 또는 `p $xmm0.v16_int8`(요소별로 쪼개서 보기), pwndbg의 `context` 화면에도 SSE 레지스터가 표시됨

## 출력 해석
- Ghidra의 `undefined1 auVarN [16]`은 "타입을 특정할 수 없는 16바이트 값"이라는 뜻이지 오류가 아니다. 앞뒤 문맥(로드 후 그대로 저장되는지)을 보고 원래 어떤 데이터였는지(구조체, 버퍼 등) 추론한다.
- `ZEXT816(x)`는 "8바이트 값 x를 16바이트로 제로 확장"이라는 Ghidra 헬퍼 표기다. `SUB168(x, 0)`은 16바이트 값의 하위 8바이트만 취한다는 뜻이다. 이런 헬퍼들은 실제 CPU 명령이 아니라 Ghidra가 타입 변환을 표현하는 방식일 뿐이다.
- `pmovmskb eax, xmm0` 다음에 `test eax, eax` / `cmp eax, 0xffff`가 오면, 이는 "16바이트를 한 번에 비교한 결과(비트마스크)가 특정 패턴인지" 검사하는 것이다 — 전부 같으면 `0xFFFF`(16비트 모두 1), 전부 다르면 `0`이 된다.

## 흔한 실수
- SIMD 명령을 보자마자 "이건 암호화/난독화 루틴"이라고 단정하고 분석을 포기하는 것 — 실제로는 대부분 `memcpy`/`memset`/`strlen` 같은 아주 평범한 연산의 최적화된 버전이다.
- `movaps`(Aligned)를 정렬 안 된 주소에 썼는데 왜 크래시가 나는지 모르는 것 — `movaps`/`movdqa`는 주소가 16바이트 경계에 정렬되지 않으면 `#GP`(General Protection) 예외를 낼 수 있다. 반면 `movups`/`movdqu`는 정렬과 무관하게 항상 안전하게 동작한다(약간 느릴 수 있지만).
- XMM 레지스터를 8바이트 정수 레지스터처럼 부분적으로만 보고 나머지 바이트를 놓치는 것 — XMM은 128비트 전체가 한 값이므로 하위 절반만 보면 데이터를 잘못 해석하게 된다.
- SIMD 명령이 `EFLAGS`를 바로 바꾼다고 착각하고 SIMD 명령 바로 다음에 오는 `Jcc`가 그 SIMD 명령 결과라고 오해하는 것 — 실제로는 `pmovmskb`나 별도의 `TEST`/`CMP`가 먼저 일반 레지스터로 결과를 옮긴 뒤에야 플래그가 바뀐다.

## 막혔을 때 다음 체크
- SIMD 블록이 문자열/배열 처리처럼 보이는데 정확한 원본 연산이 궁금하면 → 루프를 빠져나온 직후 어떤 값이 쓰이는지(길이? 비교 결과? 그냥 복사된 버퍼?) 확인해서 역으로 추론한다.
- `movaps`와 `movups`의 차이(정렬 요구사항)가 헷갈리면 → REV-0386(MOVAPS) 참고.
- `MOVAPS`가 아니라 정수 부동소수점 값 자체(`double`/`float` 연산)를 이해해야 한다면 → REV-0492(부동소수점 레지스터 값이 이상하게 보일 때)로 이동.
- 정확한 명령 스펙(오퍼랜드, 예외 조건 등)이 필요하면 → Intel SDM Volume 2의 해당 명령어 항목을 직접 찾아본다.

## 미니 예제

**예제 1 — SIMD로 벡터화된 memcpy**
```asm
loop_copy:
    movdqu  xmm0, xmmword ptr [rsi]
    movdqu  xmmword ptr [rdi], xmm0
    add     rsi, 10h
    add     rdi, 10h
    sub     rcx, 10h
    jnz     loop_copy
```
C로 표현하면: `memcpy(dst, src, n);` (16바이트씩 처리하는 벡터화 버전)

**예제 2 — pxor로 0 채우기 (memset(ptr, 0, n))**
```asm
pxor    xmm0, xmm0
loop_zero:
    movdqu  xmmword ptr [rdi], xmm0
    add     rdi, 10h
    sub     rcx, 10h
    jnz     loop_zero
```
C: `memset(ptr, 0, n);`

**예제 3 — 바이트 비교 후 비트마스크 검사 (memcmp류)**
```asm
movdqu  xmm0, xmmword ptr [rsi]
movdqu  xmm1, xmmword ptr [rdi]
pcmpeqb xmm0, xmm1        ; 바이트별로 같으면 0xFF, 다르면 0x00
pmovmskb eax, xmm0         ; 16바이트 비교 결과를 16비트 정수로
cmp     eax, 0xffff         ; 전부 같았는지 확인
jne     not_equal
```
C로 표현하면 대략: `if (memcmp(a, b, 16) == 0) { ... }`

**예제 4 — 정렬 예외를 일으키는 잘못된 movaps 사용**
```asm
lea     rax, [rbp-0x15]   ; 16의 배수가 아닌 주소 (정렬 안 됨)
movaps  xmm0, [rax]        ; #GP(General Protection) 예외 가능성
```
디버거로 여기서 크래시가 난다면, `movaps`를 `movups`로 바꾸면 해결되는지(정렬 문제였는지) 확인하는 것이 원인 진단의 첫걸음이다.

## 관련 글
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0492 — 부동소수점 레지스터 값이 이상하게 보일 때
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0447 — memset이 SIMD 명령으로 인라인되는 패턴
- REV-0448 — memcpy가 SIMD 명령으로 인라인되는 패턴

## 출처/검증
- SSE/SSE2 명령어(`MOVAPS`, `MOVDQA`, `MOVDQU`, `PXOR`, `PCMPEQB`, `PMOVMSKB` 등) 스펙: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2 (Instruction Set Reference) 기준 (2026-09-08 검증).
- `movaps`/`movdqa`의 정렬 요구사항과 `#GP` 예외 조건: 동 매뉴얼의 각 명령어 "Exceptions" 섹션 기준.
- Ghidra 디컴파일러의 `undefined1`, `unkbyte16`, `ZEXT`/`SUB` 표기 규칙: Ghidra 공식 문서(Decompiler) 및 소스 저장소 기준.
