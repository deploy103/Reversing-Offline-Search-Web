---
id: REV-0436
title: "x87 FPU 스택 레지스터 개념 기초"
slug: "rev-0436-x87-fpu-stack"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - x87
  - FPU
  - x87 FPU
  - ST0
  - "ST(0)"
  - "st(0)"
  - FPU 스택
  - 부동소수점 스택
  - TOP
  - tag word
  - control word
  - status word
  - extended precision
  - long double
  - 80비트 실수
  - C0 C1 C2 C3
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - x87이 뭐임
  - FPU 스택이 뭐임
  - ST0 레지스터
  - 부동소수점 스택 레지스터
  - x87 fpu 기초
symptom_keywords:
  - fld fstp 명령이 자꾸 나옴
  - ST(0) 레지스터를 모르겠음
  - fpu 스택이 이해가 안 됨
  - long double 어셈블리
  - x87 명령어가 뭔지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
x87 FPU는 일반 레지스터(RAX, RBX...)와 달리 **8개의 레지스터가 스택처럼 동작하는** 독립적인 부동소수점 연산 장치이며, `ST(0)`은 "0번 레지스터"가 아니라 "현재 스택 맨 위"를 가리키는 상대적인 이름이다.

## 언제 검색해야 하나
- 32비트 바이너리나 `long double`을 쓰는 코드에서 `fld`, `fstp`, `fadd`, `st(0)`, `st(1)` 같은 낯선 명령/레지스터가 나올 때
- IDA/Ghidra 디스어셈블리에 `EAX`, `RAX` 같은 익숙한 레지스터 대신 `ST(0)` ~ `ST(7)`가 보여서 당황스러울 때
- x64 SSE/SSE2(XMM 레지스터)만 알고 있었는데 갑자기 다른 방식의 부동소수점 코드를 만났을 때
- "왜 이 코드는 float 계산인데 XMM이 아니라 이상한 스택 명령을 쓰지?"라는 의문이 들 때

## 핵심 개념

### x87은 무엇이고 왜 아직도 보이는가
x87은 인텔 8087 코프로세서에서 시작된 **레거시 부동소수점 연산 유닛**이다. 오늘날 x64 코드에서 float/double 연산은 대부분 SSE/SSE2(XMM0~XMM15, REV-0396 SIMD 개요 참고)가 담당하기 때문에, x87 명령을 보게 되는 상황은 다음 중 하나일 가능성이 높다.
- **32비트(x86) 바이너리** — 32비트 ABI에서는 SSE2를 항상 쓸 수 있다고 가정하지 않으므로 컴파일러가 여전히 x87을 기본으로 쓰는 경우가 있다(대상 CPU/컴파일 옵션에 따라 다름).
- **`long double`(80비트 확장 정밀도) 연산** — x64에서도 `long double`은 XMM(64비트 double까지만 지원)으로 표현할 수 없어서, x87의 80비트 확장 정밀도 레지스터를 그대로 쓴다.
- **오래된 컴파일러/레거시 코드, 손으로 쓴 어셈블리, 특정 난독화 기법** — 굳이 x87을 쓰는 것 자체가 "이 코드는 오래됐거나 특수 목적"이라는 신호가 되기도 한다.

### 스택 구조: ST(0) ~ ST(7)
x87은 8개의 80비트 레지스터를 갖지만, 이를 `R0~R7`처럼 절대 번호로 부르지 않고 **원형 스택(circular stack)** 으로 취급한다.
- 내부적으로 **TOP**이라는 3비트 포인터(상태 워드의 일부)가 "지금 스택 맨 위가 물리적으로 몇 번 레지스터인지"를 가리킨다.
- `ST(0)`은 항상 "현재 스택 맨 위"를 뜻하고, `ST(1)`은 "그 바로 아래"를 뜻한다 — 즉 **TOP이 바뀌면 ST(0)이 가리키는 물리 레지스터도 같이 바뀐다.**
- 값을 스택에 넣는 동작(`FLD` 등)은 TOP을 하나 감소시키고 그 자리에 값을 쓴다("push"). 값을 꺼내는 동작(`FSTP` 등)은 값을 읽은 뒤 TOP을 하나 증가시킨다("pop").

이 구조 때문에 x87 코드를 읽을 때는 "지금 ST(0)에 뭐가 들어있는가"를 명령어 순서대로 손으로 따라가야 한다. REV-0044(PUSH)/REV-0045(POP)의 일반 스택 개념과 원리는 같지만, 대상이 메모리 스택이 아니라 **레지스터 스택**이라는 점이 다르다.

### 세 가지 제어 워드(word)
x87은 EFLAGS와 별개로 자신만의 상태 레지스터를 갖는다.
- **Control Word(제어 워드)**: 반올림 모드(round-to-nearest 등), 정밀도(단정도/배정도/확장정도), 예외 마스크 설정. `FLDCW`/`FSTCW`로 읽고 쓴다.
- **Status Word(상태 워드)**: 현재 TOP 값, 조건 코드 `C0`~`C3`(비교 결과, EFLAGS의 ZF/CF/PF와 비슷한 역할이지만 FPU 전용), 예외 플래그(스택 오버플로/언더플로 등). `FSTSW`/`FNSTSW`로 AX 레지스터에 복사한 뒤 `SAHF`로 EFLAGS에 옮겨서 일반 `Jcc`로 분기하는 트릭이 자주 쓰인다.
- **Tag Word**: 각 물리 레지스터가 "유효한 값 / 0 / 특수값(NaN 등) / 비어있음(empty)" 중 어떤 상태인지 2비트씩 기록. 스택 오버플로(이미 다 찬 스택에 또 push)나 언더플로(빈 스택에서 pop)를 감지하는 데 쓰인다.

### MMX와의 레지스터 공유(aliasing) — EMMS를 잊으면 생기는 문제
x87의 8개 물리 레지스터는 하드웨어적으로 MMX 레지스터(`MM0`~`MM7`)와 **같은 물리 저장공간을 공유**한다. 즉 MMX 명령을 쓰면 x87의 태그 워드가 "전부 유효한 값(값 0)"으로 강제 설정되어, 이후 곧바로 x87 명령을 쓰면 스택이 오염된 것처럼 동작한다. 그래서 MMX 코드는 x87로 되돌아가기 전에 반드시 `EMMS`(Empty MMX State) 명령으로 이 공유 상태를 정리해야 한다. 오래된 멀티미디어 코덱이나 일부 언패킹 루틴, 안티 디버깅 트릭에서 `EMMS` 호출 누락으로 인한 부동소수점 계산 오류가 실제 버그의 원인이 되기도 했으므로, MMX(`movq mm0, ...`)와 x87(`fld`, `fadd` 등) 명령이 한 함수 안에 섞여 있는데 그 사이에 `EMMS`가 없다면 의심해볼 만한 지점이다.

### 컴파일러 패턴과 디컴파일러 화면
컴파일러는 `long double` 수식을 스택 기반(후위 표기, RPN)으로 펼친다. 예를 들어 `(a + b) * c`는 대략 `fld a; fld b; faddp; fld c; fmulp` 순서로 나온다(자세한 산술 명령은 REV-0438 참고).

IDA/Ghidra는 이런 x87 코드도 대부분 잘 디컴파일해서 `long double result = (a + b) * c;` 형태로 보여주지만, 최적화가 복잡하거나 스택 균형이 애매한 경우 `in_ST0`, `ST0` 같은 의사변수가 그대로 노출되기도 한다. 이럴 땐 어셈블리 원문을 직접 따라가며 TOP이 어떻게 이동하는지 손으로 추적해야 한다.

### 리버싱 관점에서의 의미
x87 명령이 보이면 "이 함수는 float/double이 아니라 long double(80비트)을 다루거나, 32비트 타겟이다"라는 힌트를 얻을 수 있다. 또한 스택 기반이라는 특성상, `FLD`/`FSTP` 개수가 짝이 맞지 않으면 프로그램이 "FPU stack overflow" 같은 예외를 낼 수 있으므로, 함수 하나를 다 읽었을 때 push/pop 횟수가 균형을 이루는지 확인하는 습관이 버그(혹은 난독화 트릭) 탐지에 도움이 된다.

## 화면/코드에서 보이는 징후
- `ST(0)`, `ST(1)`, ... `st(i)` 형태의 레지스터 이름이 오퍼랜드로 등장
- `fld`, `fstp`, `fadd`, `fmul` 등 F로 시작하는 명령 다수
- `fnstsw ax` 뒤에 `sahf`가 이어지는, EFLAGS로 결과를 옮기는 패턴
- IDA 디컴파일에서 변수 타입이 `long double`로 표시됨

## 가장 먼저 할 것
1. 함수 시그니처나 지역 변수 타입에 `long double`이 있는지 먼저 확인한다(있으면 x87이 자연스럽다).
2. 32비트 바이너리인지 x64인지 확인한다 — 32비트라면 float/double도 x87로 계산됐을 수 있다.
3. 코드 블록 하나를 골라 `FLD`/`FSTP`(또는 `FADDP` 등 P가 붙은 pop 명령) 개수를 세어 스택이 균형 잡혀 있는지 확인한다.

## 단계별 절차
1. 함수 진입부터 `FLD` 계열이 나올 때마다 종이(또는 메모)에 스택을 한 칸씩 쌓아 올린다(TOP이 맨 위).
2. `FADD`/`FSUB`/`FMUL`/`FDIV`처럼 P가 안 붙은 연산은 스택을 그대로 두고, `FADDP` 등 P가 붙은 연산은 결과를 아래 칸에 남기고 TOP을 pop한다는 점을 반영해 그림을 갱신한다.
3. `FSTP`가 나오면 현재 TOP 값을 메모리에 쓰고 스택에서 지운다 — 그림에서 맨 위 칸을 지운다.
4. 함수가 끝나는 지점에서 스택 그림이 비어 있는지(또는 함수 시작 때와 같은 깊이인지) 확인한다 — 안 맞으면 어딘가 `FLD`/`FSTP` 짝을 놓친 것이다.

## 명령어/단축키
- IDA: F5(디컴파일)로 `long double` 수식 복원 여부 확인, 레지스터 창에서 FPU 탭을 열면 `ST0`~`ST7` 실제 값과 TOP을 볼 수 있다.
- x64dbg: FPU 레지스터 뷰(오른쪽 패널)에서 ST0~ST7과 태그 워드를 실시간으로 확인 가능.
- GDB/Pwndbg: `info registers` 뒤에 x87 레지스터 확장 명령인 `info all-registers` 또는 `p $st0`로 개별 값 확인.

## 흔한 실수
- `ST(0)`을 `EAX`처럼 "항상 같은 물리 레지스터"라고 착각하는 것 — `ST(0)`은 TOP이 바뀌면 가리키는 물리 레지스터도 바뀌는 **상대 주소**다.
- x87 스택이 LIFO(후입선출)라는 점을 잊고, `FLD` 순서와 `FSTP`로 꺼내는 순서를 뒤섞어 값이 뒤바뀐 것으로 착각하는 것.
- FPU의 `C0~C3` 조건 코드를 일반 EFLAGS의 `ZF`/`CF`와 혼동하는 것 — 둘은 저장 위치와 갱신 규칙이 다른 별개의 상태다.
- x64 바이너리인데 x87이 나온다고 "이상하다"며 무시하는 것 — `long double`이 쓰였을 가능성을 먼저 의심해야 한다.

## 막혔을 때 다음 체크
- `FLD`/`FSTP` 관련 개별 명령의 정확한 동작이 궁금하면 → REV-0437.
- 산술 명령(`FADD`/`FSUB`/`FMUL`/`FDIV`)의 방향이 헷갈리면 → REV-0438.
- 디컴파일러가 `in_ST0` 같은 의사변수를 그대로 노출하면 → 어셈블리를 직접 손으로 스택 그림을 그리며 추적한다.

## 미니 예제

**예제 1 — 단순 float 로컬 변수 push**
```asm
fld     dword ptr [ebp-4]   ; 지역 float 변수를 32비트로 읽어 80비트로 변환 후 ST(0)에 push
```

**예제 2 — 두 값을 더하고 저장 (RPN 스타일)**
```asm
fld     dword ptr [ebp-4]   ; ST(0) = a
fld     dword ptr [ebp-8]   ; ST(0) = b, ST(1) = a
faddp   st(1), st(0)        ; ST(1) += ST(0), pop → ST(0) = a+b
fstp    dword ptr [ebp-4]   ; 결과 저장 후 pop → 스택 비움
```

**예제 3 — 상태 워드를 EFLAGS로 옮겨 분기하는 패턴**
```asm
fcom    st(1)                ; ST(0)과 ST(1) 비교, C0~C3에 결과 기록
fnstsw  ax                   ; 상태 워드를 AX로 복사
sahf                          ; AH를 EFLAGS 하위 바이트로 반영 (ZF/CF 등)
jb      less_label            ; 이제 일반 Jcc로 분기 가능
```

**예제 4 — long double 지역 변수**
```c
long double x = a + b;   // x64에서도 XMM이 아닌 x87 명령으로 컴파일됨
```

## 관련 글
- REV-0437 — FLD와 FSTP: x87 스택 로드/저장
- REV-0438 — FADD FSUB FMUL FDIV: x87 산술 명령 개요
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기
- REV-0044 — PUSH: 스택에 값 넣기
- REV-0045 — POP: 스택에서 값 꺼내기

## 출처/검증
- x87 FPU 레지스터 스택, TOP, Control/Status/Tag Word 구조: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 1, Chapter 8 "Programming with the x87 FPU" 기준 (2026-09-08 검증).
- `long double`이 x64에서도 x87 80비트 확장 정밀도로 표현되는 점: System V AMD64 ABI 및 주요 컴파일러(GCC/Clang) x86-64 `long double` 구현 문서 기준.
