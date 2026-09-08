---
id: REV-0043
title: "XCHG: 두 값 교환"
slug: "rev-0043-xchg"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - xchg
  - XCHG
  - Xchg
  - xchg instruction
  - xchg 명령어
  - "xchg eax ebx"
  - "xchg eax, ebx"
  - "xchg ax ax"
  - "xchg ax, ax"
  - swap 명령어
  - 두 값 교환
  - 값 스왑
  - atomic exchange
  - lock xchg
  - nop 인코딩
  - xchg eax eax
aliases:
  - xchg 뭐임
  - xchg가 뭐죠
  - xchg 명령
  - XCHG 명령어
  - 교환 명령어
  - 스왑 명령어
symptom_keywords:
  - xchg ax ax가 왜 nop인지 모르겠음
  - lock xchg가 왜 쓰이는지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`XCHG dst, src`는 두 오퍼랜드의 값을 **서로 맞바꾸는** 명령어다. 임시 변수 없이 `a, b = b, a`를 한 명령으로 수행하며, 메모리 오퍼랜드가 있으면 자동으로 원자적(atomic)으로 동작한다.

## 언제 검색해야 하나
- `xchg eax, ebx` 같은 코드를 만나서 두 레지스터 값이 어떻게 뒤바뀌는지 궁금할 때
- `xchg ax, ax`가 왜 있는지 궁금할 때(사실 이건 NOP의 기계어 인코딩과 같다)
- 멀티스레드 코드에서 `xchg`가 락(lock)이나 스핀락, 원자적 연산 구현에 쓰인 걸 발견했을 때
- 함수 프롤로그에서 낯선 `xchg`가 나와서 당황했을 때(디버거 안티 트릭이나 패킹된 코드에서 종종 보임)

## 핵심 개념

### 동작
```
XCHG dst, src
```
실행 후: `dst`는 원래 `src` 값을, `src`는 원래 `dst` 값을 갖게 된다. 임시 변수 없이 스왑하는 것과 동일하다.
```asm
mov  eax, 1
mov  ebx, 2
xchg eax, ebx    ; 실행 후: eax = 2, ebx = 1
```
C로 쓰면 `int tmp = a; a = b; b = tmp;`와 완전히 같은 결과지만, XCHG는 이걸 **한 명령어**로 해낸다(내부적으로 CPU가 임시 저장을 처리).

### 오퍼랜드 조합
- 레지스터 ↔ 레지스터: `xchg eax, ebx`
- 레지스터 ↔ 메모리: `xchg eax, [rbx]` (메모리 값과 레지스터 값을 교환)
- 메모리 ↔ 메모리는 불가능(MOV와 동일한 제약).

### 메모리가 포함되면 자동으로 원자적(atomic)이다
이게 XCHG의 특별한 성질이다. `xchg eax, [rbx]`처럼 오퍼랜드 중 하나가 메모리라면, 이 명령어는 **`LOCK` 접두사를 명시하지 않아도 자동으로 원자적으로 실행**된다(다른 CPU 코어가 그 사이에 끼어들어 값을 읽거나 쓸 수 없다). 이 특성 때문에 멀티스레드 프로그래밍에서 **뮤텍스/스핀락 구현, 원자적 플래그 교체(test-and-set)** 에 전통적으로 많이 쓰였다. 요즘 컴파일러는 `std::atomic::exchange()` 같은 고수준 원자적 연산을 이 XCHG(또는 CMPXCHG)로 컴파일한다.

### 플래그
`XCHG`는 **플래그를 전혀 바꾸지 않는다.** 두 값을 그냥 맞바꿀 뿐이다.

### `xchg ax, ax` = NOP의 정체
1바이트 NOP 명령어(`0x90`)의 기계어 인코딩은 사실 `xchg ax, ax`(자기 자신과 자기 자신을 교환 = 아무 일도 안 일어남)와 완전히 동일한 바이트다. 그래서 디스어셈블러가 `0x90` 바이트를 만나면 문맥에 따라 `nop`으로 표시하기도 하고 `xchg ax, ax`로 표시하기도 한다 — 둘은 같은 것이다. `xchg eax, eax`(32비트 버전)도 실질적으로 아무 효과가 없다(단, x64 규칙상 32비트 레지스터 쓰기는 상위 64비트를 클리어하므로 완전히 무효과는 아닐 수 있음에 유의).

### 왜 컴파일러가 XCHG를 직접 쓰는 일은 드문가
일반적인(원자성이 필요 없는) 값 교환은 컴파일러가 그냥 `mov`+임시 레지스터 조합으로 처리하는 경우가 더 많다. XCHG가 직접 등장하는 경우는 대개: (1) 멀티스레드 원자적 연산, (2) 손으로 쓴 어셈블리/셸코드(레지스터를 아끼려는 최적화), (3) 패커/난독화 코드(디버거 스텝 트릭이나 코드 크기 축소), (4) `xchg ax, ax`/`xchg eax, eax` 형태의 패딩/정렬용 NOP 대체다.

## 화면/코드에서 보이는 징후
- `xchg eax, ebx` — 두 레지스터 값 스왑
- `xchg eax, [rbx]` — 메모리와 레지스터를 원자적으로 스왑 (락 없이도 원자적)
- `lock xchg [rdi], eax` — `LOCK` 접두사가 명시적으로 붙은 형태(사실 XCHG+메모리 조합은 이미 원자적이라 LOCK이 없어도 동일하지만, 컴파일러/어셈블러가 명시적으로 붙이기도 함)
- `xchg ax, ax` 또는 `90` 바이트 나열 — NOP 패딩(함수 정렬, 코드 채우기)
- IDA 디컴파일에서 원자적 연산이면 `InterlockedExchange(...)`나 `std::atomic<T>::exchange(...)` 형태로 나타나기도 함

## 가장 먼저 할 것
1. 오퍼랜드가 레지스터-레지스터인지, 레지스터-메모리인지 확인한다.
2. 메모리가 포함되어 있다면 "이건 원자적 연산이다 — 멀티스레드/동기화 코드일 가능성이 있다"고 의심한다.
3. `xchg ax, ax`/`xchg eax, eax`라면 그냥 NOP으로 취급하고 넘어간다.

## 단계별 절차
**1) 레지스터 스왑 확인**
```asm
mov  eax, [rbp-0x4]   ; eax = a
mov  ebx, [rbp-0x8]   ; ebx = b
xchg eax, ebx           ; eax<->ebx: 이제 eax=b, ebx=a
```

**2) 원자적 메모리 교환 확인**
```asm
mov  eax, 1
xchg [rdi], eax        ; *rdi 와 eax를 원자적으로 교환 (test-and-set 패턴)
test eax, eax           ; 교환 전 *rdi 값이 0이었는지 확인 (락 획득 성공 여부)
jnz  spin_wait
```
→ 스핀락 획득 코드의 전형적 패턴. `*rdi`가 원래 0이었으면(락이 안 걸려있었으면) 락 획득 성공.

**3) NOP 패딩 인식**
```asm
xchg ax, ax
xchg ax, ax
```
→ 그냥 정렬용 패딩, 실행 흐름 분석 시 무시해도 된다.

## 명령어/단축키
- IDA: XCHG가 있는 함수를 보면 우클릭 → "Convert to..."는 필요 없고, `Ctrl+X`(Xrefs)로 이 원자적 연산이 락/동기화 객체와 관련 있는지 주변 코드 확인
- x64dbg: 실행 전/후 레지스터 값 두 개가 서로 뒤바뀌는지 레지스터 창에서 직접 확인
- GDB/Pwndbg: `stepi`로 한 줄 실행 후 `info registers`로 두 레지스터 값이 교환됐는지 확인

## 출력 해석
- XCHG 실행 전후로 두 오퍼랜드 값이 정확히 뒤바뀌어 있으면 정상 동작.
- `lock xchg`나 메모리가 포함된 XCHG 다음에 `test`+조건분기가 있으면, 이는 락 획득/해제 로직일 가능성이 높다 — "교환 전 값이 무엇이었는가"로 성공/실패를 판단하는 패턴.

## 흔한 실수
- XCHG가 플래그를 바꾼다고 착각하는 것 — 바꾸지 않는다.
- `xchg ax, ax`를 의미 있는 연산으로 착각해서 분석 시간을 낭비하는 것 — 이건 그냥 NOP이다.
- 메모리가 포함된 XCHG를 그냥 평범한 대입으로 오해해서 "왜 원자적이라는 거지?"를 놓치는 것 — 이 특성이 동기화 코드를 식별하는 중요한 단서다.
- XCHG를 CMPXCHG(compare-and-exchange, 조건부 교환)와 혼동하는 것 — CMPXCHG는 비교 결과에 따라 교환 여부가 갈리는 별개의 명령어다(이 사전에서 별도로 다루지 않음, 필요시 Intel SDM 참고).

## 막혔을 때 다음 체크
- 스레드/동기화 관련 코드로 보이는데 XCHG의 역할이 애매하면 → 주변에 `InterlockedXxx`(Windows API) 또는 `pthread_mutex` 관련 심볼/문자열이 있는지 확인해서 문맥을 좁힌다.
- XCHG가 왜 갑자기 나왔는지 이해가 안 되면 → 함수 정렬을 위한 패딩(`xchg ax, ax`)인지부터 배제한다.

## 미니 예제

**예제 1 — 단순 스왑**
```c
int tmp = a;
a = b;
b = tmp;
```
```asm
mov  eax, [rbp-0x4]   ; eax = a
mov  ecx, [rbp-0x8]   ; ecx = b
xchg eax, ecx           ; eax<->ecx 교환
mov  [rbp-0x4], eax    ; a = 원래 b
mov  [rbp-0x8], ecx    ; b = 원래 a
```

**예제 2 — 원자적 test-and-set 스핀락 획득**
```c
while (atomic_exchange(&lock, 1) != 0) { /* spin */ }
```
```asm
spin:
    mov  eax, 1
    xchg [rdi], eax    ; lock과 eax 교환 (원자적)
    test eax, eax        ; 교환 전 lock 값이 0이었나?
    jnz  spin             ; 0이 아니었으면(이미 잠겨있었으면) 재시도
```

**예제 3 — NOP 대체 패딩**
```asm
sub_401000:
    push rbp
    mov  rbp, rsp
    xchg ax, ax     ; 정렬용 패딩, 실질적으로 아무 일도 안 함
    ...
```

## 관련 글
- [MOV: 값 복사와 레지스터 메모리 이동](./rev-0039-mov.md)
- [PUSH: 스택에 값 넣기](./rev-0044-push.md)
- [POP: 스택에서 값 꺼내기](./rev-0045-pop.md)

## 출처/검증
- XCHG 명령어 동작 및 메모리 오퍼랜드 시 자동 원자성: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "XCHG—Exchange Register/Memory with Register" 섹션 기준 (2026-09-08 검증).
- `xchg ax, ax`와 1바이트 NOP(`0x90`) 인코딩의 관계: 같은 매뉴얼의 NOP 관련 설명 및 x86 명령어 인코딩 표 기준.
