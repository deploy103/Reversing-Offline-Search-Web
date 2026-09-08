---
id: REV-0437
title: "FLD와 FSTP: x87 스택 로드/저장"
slug: "rev-0437-fld-fstp"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - FLD
  - fld
  - FSTP
  - fstp
  - FST
  - fst
  - FILD
  - FISTP
  - x87 로드
  - x87 저장
  - FPU push pop
  - "fld dword ptr"
  - "fstp qword ptr"
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - fld가 뭐임
  - fstp가 뭐임
  - fld fstp 차이
  - fst와 fstp 차이
  - x87 로드 저장 명령
symptom_keywords:
  - fld 명령이 뭔지 모르겠음
  - fstp 명령이 뭔지 모르겠음
  - fst와 fstp를 헷갈림
  - fpu 스택에 값을 어떻게 넣는지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`FLD`는 메모리(또는 다른 `ST(i)`)의 실수 값을 x87 스택 맨 위(`ST(0)`)에 **push**하고, `FSTP`는 `ST(0)`의 값을 메모리(또는 `ST(i)`)에 저장한 뒤 스택에서 **pop**한다 — REV-0044(PUSH)/REV-0045(POP)의 FPU 버전이다.

## 언제 검색해야 하나
- `fld dword ptr [ebp-4]`, `fstp qword ptr [ebp-8]` 같은 코드를 처음 보고 무슨 뜻인지 모를 때
- `FST`와 `FSTP`의 차이(P가 붙고 안 붙고)가 헷갈릴 때
- `FILD`/`FISTP`처럼 뒤에 I가 붙은 변형이 왜 있는지 궁금할 때
- x87 스택 언더플로/오버플로 관련 경고나 이상 동작을 조사할 때

## 핵심 개념

### FLD: 스택에 값 push
`FLD src`는 다음을 수행한다.
1. `src`(메모리 32/64/80비트 실수, 또는 `ST(i)`)의 값을 읽어 내부적으로 80비트 확장 정밀도로 변환한다.
2. x87 스택 포인터(TOP)를 하나 감소시킨다.
3. 그 새 `ST(0)` 자리에 변환된 값을 쓴다. 이전에 `ST(0)`이었던 값은 이제 `ST(1)`이 된다.

메모리에서 읽는 `fld dword ptr [...]`(단정도), `fld qword ptr [...]`(배정도), `fld tbyte ptr [...]`(80비트 확장 정밀도) 외에, 상수를 바로 push하는 전용 명령도 있다: `FLD1`(1.0), `FLDZ`(0.0), `FLDPI`(π), `FLDL2E`, `FLDLN2` 등.

**왜 항상 80비트로 변환해서 저장하는가**: x87은 정밀도가 다른 값들을 섞어 계산해도 항상 스택 내부에서는 80비트 확장 정밀도로 다룬다. 그래서 `float`(32비트) 두 개를 더한 결과를 다시 `float`으로 저장하면(`FSTP dword ptr [...]`), 계산 중간에는 80비트 정밀도로 더했다가 마지막에 32비트로 반올림되는 셈이라 이론적으로 더 정확한 결과가 나올 수 있다. 반대로 이 때문에 "같은 수식인데 x87로 계산한 결과와 SSE2(XMM, 항상 지정된 정밀도만 사용)로 계산한 결과가 미세하게 다르다"는 현상이 생기기도 한다 — 디버거로 값을 비교할 때 이 차이를 반올림 오차로 오인하지 않도록 주의한다.

### FST와 FSTP: 저장, 그리고 pop 여부의 차이
- `FST dest` — `ST(0)`의 값을 `dest`(메모리 또는 다른 `ST(i)`)에 **복사만 하고 스택은 그대로 둔다.** `ST(0)`은 그대로 유지된다.
- `FSTP dest` — `FST`와 동일하게 저장하되, 저장 직후 **스택에서 pop한다(P = Pop).** TOP이 하나 증가하고, 이전 `ST(1)`이 새 `ST(0)`이 된다.

실무에서는 계산이 끝난 최종 결과를 메모리에 쓰고 스택도 비우고 싶은 경우가 많아서 `FSTP`가 `FST`보다 훨씬 자주 보인다. `FST`는 중간값을 "복사만 해두고 스택 값은 계속 쓰고 싶을 때" 쓰인다.

### 정수 변환 변형: FILD / FIST / FISTP
FPU는 정수와 실수 간 변환도 스택 push/pop과 함께 처리한다.
- `FILD src` — 메모리의 **정수**(16/32/64비트)를 읽어 실수로 변환한 뒤 `ST(0)`에 push. `int`를 `double`/`long double`로 바꾸는 코드에서 흔하다.
- `FISTP dest` — `ST(0)`의 실수 값을 **정수**로 반올림/변환해서 메모리에 저장하고 pop. `(int)someDouble` 같은 캐스팅에서 흔하다.

`FISTP`가 정수로 변환할 때 어떤 반올림 규칙을 쓰는지는 Control Word의 반올림 모드 비트에 달려 있다(기본값은 "가장 가까운 짝수로 반올림", round-to-nearest-even). C의 `(int)x` 캐스팅은 "0 방향으로 자르기(truncate)"를 요구하므로, 컴파일러는 `FISTP` 앞에서 `FLDCW`로 반올림 모드를 잠깐 "0 방향 절삭"으로 바꿨다가 변환 후 다시 원래 모드로 되돌리는 코드를 넣거나, x87 대신 SSE2의 `CVTTSD2SI`(자르기 전용) 명령을 쓰기도 한다. 이런 `FLDCW` 쌍이 `FISTP` 앞뒤로 보이면 "정수 캐스팅을 위한 반올림 모드 임시 변경"이라고 이해하면 된다.

### 플래그와 부호/정밀도
- 이 명령들은 EFLAGS를 변경하지 않는다. 대신 x87 상태 워드(Status Word)의 예외 비트(스택 오버플로/언더플로, 부정확한 결과 등)에 영향을 줄 수 있다.
- `FLD`/`FSTP`는 부호 있는 실수를 그대로 다루므로 별도의 signed/unsigned 구분은 없다(부동소수점은 항상 부호 비트를 포함한다). 다만 `FILD`/`FISTP`로 정수를 오갈 때는 그 정수가 signed인지(대부분 x87 정수 명령은 signed 정수를 가정) 확인해야 한다 — unsigned 64비트처럼 x87이 직접 지원하지 않는 폭/부호는 컴파일러가 보정 코드를 추가로 넣기도 한다.

### 스택/레지스터 효과 요약
| 명령 | 방향 | 스택 효과 |
|---|---|---|
| `FLD src` | src → ST(0) | push (TOP -1) |
| `FST dest` | ST(0) → dest | 변화 없음 |
| `FSTP dest` | ST(0) → dest | pop (TOP +1) |
| `FILD src` | src(int) → ST(0) | push |
| `FISTP dest` | ST(0) → dest(int) | pop |

### 컴파일러 패턴과 디컴파일러 화면
전형적인 `float c = a + b;` 코드는 `fld a; fld b; faddp; fstp c` 형태로 컴파일된다(산술 명령 상세는 REV-0438 참고). IDA/Ghidra는 이런 로드/저장 시퀀스를 대부분 하나의 대입문으로 깔끔하게 합쳐서 보여주지만, 함수 경계나 인라인 어셈블리가 섞인 경우 `FLD`/`FSTP` 원문이 그대로 노출될 수 있다.

### 리버싱 관점에서의 의미
`FLD`/`FSTP` 개수가 함수 안에서 짝이 맞는지 세어보면, 그 함수가 x87 스택을 깨끗이 정리하고 끝나는지(정상) 아니면 스택에 값을 남긴 채 반환하는지(비정상적이거나 특이한 호출 규약)를 빠르게 판단할 수 있다. 또한 `FSTP st(0)`처럼 목적지가 `ST(0)` 자신인 코드는 "값은 필요 없고 그냥 스택만 비우고 싶다(pop만 하고 싶다)"는 관용구로 자주 쓰인다.

## 화면/코드에서 보이는 징후
- `fld dword/qword/tbyte ptr [...]` — 메모리에서 스택으로 로드
- `fstp dword/qword/tbyte ptr [...]` — 스택에서 메모리로 저장 후 pop
- `fild`/`fistp` — 정수 메모리 피연산자와 함께 등장(정수↔실수 변환)
- `fstp st(0)` — 값을 버리고 스택만 비우는 관용구

## 가장 먼저 할 것
1. 피연산자의 크기 접미사(`dword`=32비트, `qword`=64비트, `tbyte`=80비트)를 확인해서 원본 타입(`float`/`double`/`long double`)을 추정한다.
2. `FST`인지 `FSTP`인지(P 유무)를 확인해서 이 명령 이후 스택이 줄어드는지 아닌지 판단한다.
3. `FILD`/`FISTP`가 보이면 정수↔실수 변환이 일어난다는 것을 표시해두고 원본 변수 타입을 역추적한다.

## 단계별 절차
1. `FLD`(로드)인지 `FST`/`FSTP`(저장)인지 먼저 구분한다 — L은 스택에 넣기, ST는 꺼내 쓰기다.
2. 오퍼랜드 크기 접미사로 원본 타입을 적어둔다 (dword=float, qword=double, tbyte=long double).
3. `FSTP`처럼 P가 붙었으면 이 명령 이후 스택 깊이가 1 줄어든다는 것을 표시한다.
4. 여러 FLD/FSTP가 섞인 블록이면 순서대로 스택 그림을 그려서 최종적으로 무엇이 메모리에 저장되는지 추적한다.

## 명령어/단축키
- IDA: 레지스터 창의 FPU 탭에서 push/pop 직후 `ST0`~`ST7` 값 변화를 즉시 확인.
- x64dbg: FPU 패널에서 `dword`/`qword`/`tbyte` 형식으로 메모리 피연산자를 바로 보기(우클릭 → "Follow in Dump").
- GDB/Pwndbg: `x/gx $rbp-8` 등으로 메모리에 저장된 실수 값을 16진수로 확인 후 필요 시 `p (double)*(double*)($rbp-8)`처럼 캐스팅해서 값 확인.

## 흔한 실수
- `FST`가 `FSTP`처럼 항상 pop한다고 착각하는 것 — `FST`는 스택을 건드리지 않는다.
- `FLD`/`FSTP` 호출 횟수를 세지 않고 넘어가서, 함수 끝에서 스택이 비었는지 안 비었는지 놓치는 것.
- `FILD`/`FISTP`를 `FLD`/`FSTP`와 같은 것으로 착각해서 정수↔실수 변환이 일어난다는 사실을 놓치는 것.
- 메모리 피연산자 크기 접미사(`dword`/`qword`/`tbyte`)를 무시하고 모두 같은 정밀도라고 가정하는 것 — 32비트 float, 64비트 double, 80비트 확장 정밀도는 서로 다른 결과를 낼 수 있다.

## 막혔을 때 다음 체크
- 스택 자체의 원리(TOP, ST(i) 상대 개념)가 헷갈리면 → REV-0436.
- 로드/저장이 아니라 실제 사칙연산 방향이 궁금하면 → REV-0438.
- 반올림 모드 관련 `FLDCW` 쌍이 왜 있는지 더 알고 싶으면 → 위 "정수 변환 변형" 절의 반올림 모드 설명을 다시 확인.

## 미니 예제

**예제 1 — float 덧셈**
```c
float c = a + b;
```
```asm
fld     dword ptr [a]
fld     dword ptr [b]
faddp   st(1), st(0)
fstp    dword ptr [c]
```

**예제 2 — int를 double로 변환**
```c
double d = (double)n;
```
```asm
fild    dword ptr [n]     ; 정수를 읽어 실수로 변환, push
fstp    qword ptr [d]     ; 결과 저장, pop
```

**예제 3 — 값만 복사하고 스택은 유지 (FST)**
```asm
fld     dword ptr [x]
fst     dword ptr [tmp1]   ; ST(0)은 그대로 유지된 채 tmp1에 복사
fstp    dword ptr [tmp2]   ; 같은 값을 tmp2에 저장하고 이번엔 pop
```

**예제 4 — 스택만 비우는 관용구**
```asm
fstp    st(0)   ; ST(0) 값을 자기 자신에 "저장"하는 형태로, 사실상 값을 버리고 pop만 수행
```

## 관련 글
- REV-0436 — x87 FPU 스택 레지스터 개념 기초
- REV-0438 — FADD FSUB FMUL FDIV: x87 산술 명령 개요
- REV-0039 — MOV: 값 복사와 레지스터 메모리 이동
- REV-0044 — PUSH: 스택에 값 넣기
- REV-0045 — POP: 스택에서 값 꺼내기

## 출처/검증
- `FLD`/`FST`/`FSTP`/`FILD`/`FISTP` 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "FLD—Load Floating-Point Value" / "FST/FSTP" / "FILD" / "FIST/FISTP" 섹션 기준 (2026-09-08 검증).
