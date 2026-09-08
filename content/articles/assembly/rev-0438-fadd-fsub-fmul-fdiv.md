---
id: REV-0438
title: "FADD FSUB FMUL FDIV: x87 산술 명령 개요"
slug: "rev-0438-fadd-fsub-fmul-fdiv"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - FADD
  - fadd
  - FSUB
  - fsub
  - FSUBR
  - fsubr
  - FMUL
  - fmul
  - FDIV
  - fdiv
  - FDIVR
  - fdivr
  - FADDP
  - FSUBP
  - FMULP
  - FDIVP
  - x87 산술
  - FPU 산술 명령
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - fadd가 뭐임
  - fsub fsubr 차이
  - fdiv fdivr 차이
  - x87 산술 명령어
  - fpu 덧셈 뺄셈 곱셈 나눗셈
symptom_keywords:
  - fadd fsub fmul fdiv 명령이 뭔지 모르겠음
  - fsubr 방향이 헷갈림
  - fdivr 순서가 이상함
  - x87 산술 결과가 예상과 다름
last_verified: "2026-09-08"
---

## 한 줄 요약
`FADD`/`FSUB`/`FMUL`/`FDIV`는 x87 스택의 `ST(0)`과 다른 피연산자(메모리 또는 `ST(i)`) 사이에서 사칙연산을 수행하는 명령으로, 특히 `FSUB`/`FDIV`는 **뺄셈/나눗셈 방향**을 뒤집는 `R`(Reverse) 접미사 변형이 있어 방향을 착각하기 쉽다.

## 언제 검색해야 하나
- `fadd`, `fsub`, `fmul`, `fdiv` 계열 명령이 x87 코드에 나오는데 피연산자 순서가 헷갈릴 때
- `FSUBR`, `FDIVR`처럼 `R`이 붙은 명령을 처음 보고 일반 `FSUB`/`FDIV`와 뭐가 다른지 모를 때
- `long double`/x87 코드의 계산 결과가 예상과 미묘하게 다를 때(정밀도/반올림 의심)
- `(a+b)*c` 같은 수식이 x87 스택 연산으로 어떻게 펼쳐지는지 확인하고 싶을 때

## 핵심 개념

### 기본 형태와 피연산자
x87 산술 명령은 항상 `ST(0)`을 한쪽 피연산자로 암묵적으로 사용한다. 오퍼랜드 형태는 크게 세 가지다.
```
FADD              ; ST(1) = ST(1) + ST(0), pop 없음(드물게 사용)
FADD  st(i)       ; ST(0) = ST(0) + ST(i)
FADDP st(i), st(0); ST(i) = ST(i) + ST(0), 이후 pop (가장 흔함 — 결과를 남기고 스택 정리)
FADD  m32fp/m64fp ; ST(0) = ST(0) + 메모리 값
FIADD m32int      ; ST(0) = ST(0) + 메모리의 정수(자동 변환)
```
`FMUL`도 동일한 패턴(`FMUL`, `FMULP`, `FIMUL`)을 따른다.

### FSUB/FSUBR, FDIV/FDIVR — 방향 주의
뺄셈과 나눗셈은 교환법칙이 성립하지 않기 때문에 인텔은 "어느 쪽에서 어느 쪽을 빼는가/나누는가"를 명시하는 두 버전을 제공한다.
- `FSUB st(0), st(i)` → `ST(0) = ST(0) - ST(i)` (일반)
- `FSUBR st(0), st(i)` → `ST(0) = ST(i) - ST(0)` (**R**everse — 순서가 뒤집힘)
- `FDIV st(0), st(i)` → `ST(0) = ST(0) / ST(i)`
- `FDIVR st(0), st(i)` → `ST(0) = ST(i) / ST(0)`

특히 `FSUBP`/`FDIVP` 형태(`FSUBP st(i), st(0)`)는 "`ST(i) = ST(i) - ST(0)`"이 되어, 얼핏 보면 `FSUBRP`와 헷갈릴 수 있다. 실제로 컴파일러가 어떤 변형을 골라 쓰는지는 스택에 피연산자가 어느 순서로 push됐는지에 달려 있으므로, **"이 명령이 정확히 뭘 누구에서 빼는가"를 매번 표에서 확인하는 습관**이 중요하다.

| 명령 | 의미 |
|---|---|
| `FSUB st(i), st(0)` | `ST(i) -= ST(0)` |
| `FSUBR st(i), st(0)` | `ST(i) = ST(0) - ST(i)` |
| `FSUBP st(i), st(0)` | `ST(i) -= ST(0)`, 이후 pop |
| `FSUBRP st(i), st(0)` | `ST(i) = ST(0) - ST(i)`, 이후 pop |
| `FDIVP` / `FDIVRP` | `FSUBP`/`FSUBRP`와 동일한 규칙을 나눗셈에 적용 |

### 예외와 FWAIT 동기화
x87은 원래 별도의 코프로세서 칩이었던 역사 때문에, CPU 코어와 비동기적으로 동작할 수 있다는 전제가 남아있다. 그래서 x87 예외(0으로 나누기, 오버플로/언더플로 등)가 발생했는지 확인하려면 `FWAIT`(또는 `WAIT`) 명령으로 FPU 연산이 끝날 때까지 동기화를 기다려야 하는 경우가 있다. 요즘 컴파일러가 내는 코드에서는 잘 안 보이지만, 오래된 코드나 손으로 최적화한 코드에서 `fwait`이 산술 명령 사이에 끼어 있다면 "예외 확인을 위한 동기화 지점"이라고 이해하면 된다. 예외가 마스크(기본값)되어 있으면 이런 동기화 없이도 결과는 조용히 `±Inf`/`NaN`으로 계산되어 다음 연산으로 전파된다.

### 플래그와 부호
- EFLAGS는 변경되지 않는다. 대신 x87 상태 워드의 `C1` 비트가 스택 오버플로/언더플로나 반올림 방향을 나타내는 데 쓰이고, 부정확한 결과·0으로 나누기 등은 예외 플래그로 기록된다(마스크되어 있으면 조용히 무시되고 결과는 ±Inf/NaN 등이 된다).
- x87은 부호 있는 실수만 다루므로 signed/unsigned 구분 자체가 없다. 대신 **정밀도**(단정도 32비트 / 배정도 64비트 / 확장정도 80비트) 차이로 인해 같은 계산도 x87(80비트 중간 정밀도)과 SSE2(64비트로 고정)에서 결과가 미세하게 달라질 수 있다는 점이 리버싱에서 종종 "왜 디버거로 본 값이 소스 레벨 예상과 살짝 다르지?"의 원인이 된다.

### 컴파일러 패턴: 후위 표기(RPN)로 펼쳐지는 수식
`(a + b) * c` 같은 수식은 사람이 읽는 중위 표기가 아니라 스택 기반 후위 표기로 컴파일된다.
```asm
fld     dword ptr [a]     ; ST(0) = a
fld     dword ptr [b]     ; ST(0) = b, ST(1) = a
faddp   st(1), st(0)      ; ST(1) = a+b, pop → ST(0) = a+b
fld     dword ptr [c]     ; ST(0) = c, ST(1) = a+b
fmulp   st(1), st(0)      ; ST(1) = (a+b)*c, pop → ST(0) = (a+b)*c
fstp    dword ptr [result]
```
연산 순서를 헷갈리지 않으려면, 매 줄마다 스택 그림을 손으로 그려가며 TOP이 무엇을 가리키는지 갱신하는 것이 가장 확실하다.

### IDA/Ghidra 디컴파일과 리버싱 관점
Hex-Rays/Ghidra 모두 이런 push-연산-pop 시퀀스를 대부분 `result = (a + b) * c;` 형태의 자연스러운 C 수식으로 재구성해준다. 다만 최적화된 코드에서 `FADD`/`FSUB` 순서가 재배치되거나 `FXCH`(스택 위치 교환)이 섞이면 디컴파일러가 실패하고 `ST0`, `in_ST1` 같은 의사변수를 그대로 노출할 수 있는데, 이럴 때는 위 표를 기준으로 어셈블리를 직접 손으로 재구성해야 한다. `FSUBR`/`FDIVR`가 보이는데 이를 일반 `FSUB`/`FDIV`처럼 읽으면 부호/결과가 반대로 계산되므로, exploit/crackme의 수치 검증 로직을 분석할 때 특히 주의해야 한다.

## 화면/코드에서 보이는 징후
- `faddp`, `fsubp`, `fmulp`, `fdivp` — 결과를 남기고 pop까지 하는 가장 흔한 형태
- `fsubr`, `fdivr`(또는 `fsubrp`, `fdivrp`) — 방향이 뒤집힌 변형, 표를 다시 확인해야 하는 신호
- `fiadd`, `fisub`, `fimul`, `fidiv` — 메모리의 정수 피연산자와 바로 연산(자동 변환 포함)
- `fld`가 여러 번 연속된 뒤 `faddp`/`fmulp` 등이 이어지는 RPN 스타일 블록

## 가장 먼저 할 것
1. 명령에 `R`(Reverse) 접미사가 붙어 있는지 먼저 확인한다 — 있으면 위 표에서 정확한 방향을 다시 찾는다.
2. `P` 접미사가 있는지 확인해서 이 연산 후 스택이 pop되는지(TOP 이동) 판단한다.
3. 여러 산술 명령이 연속되면, `FLD`부터 시작해서 스택 그림을 한 줄씩 손으로 그리며 최종 수식을 복원한다.

## 단계별 절차
1. 블록의 첫 `FLD`부터 스택 그림을 그리기 시작한다.
2. `FADD`/`FSUB`/`FMUL`/`FDIV`(P 없음)는 ST(0)과 지정 레지스터를 연산해 ST(0)에 결과를 남기고 스택 깊이는 그대로다.
3. `FADDP`/`FSUBP`/`FMULP`/`FDIVP`(P 있음)는 연산 후 pop까지 하므로 스택 깊이가 1 줄어든다 — 그림에서 한 칸을 지운다.
4. 마지막 `FSTP`가 나올 때까지 반복하면 원래의 중위 표기 수식(`(a+b)*c` 등)을 그대로 복원할 수 있다.

## 명령어/단축키
- IDA: F5 디컴파일로 자동 복원된 수식을 먼저 확인하고, 이상하면 어셈블리 뷰(스페이스바로 전환)에서 원문을 직접 추적.
- x64dbg: FPU 패널에서 명령 하나씩 Step(F7)하며 ST0~ST7 값이 어떻게 바뀌는지 실시간 관찰.
- GDB/Pwndbg: `stepi`로 한 명령씩 진행하며 `info float`(또는 확장 레지스터 명령)로 스택 상태 확인.

## 흔한 실수
- `FSUBR`/`FDIVR`를 `FSUB`/`FDIV`와 같은 명령으로 착각해서 뺄셈/나눗셈 방향을 반대로 해석하는 것.
- `FADDP`류 명령이 "더하고 pop"이라는 두 동작을 동시에 한다는 것을 잊고, pop이 안 일어난다고 착각해서 스택 상태 추적이 틀어지는 것.
- x87(80비트 중간 정밀도)과 SSE2(64비트) 계산 결과가 다를 수 있다는 점을 모르고, "같은 수식인데 왜 값이 다르지"에서 막히는 것.
- 정수 변형(`FIADD`, `FIMUL` 등)을 실수 변형과 혼동해서 메모리 피연산자가 정수인지 실수인지 확인하지 않는 것.

## 막혔을 때 다음 체크
- 스택 push/pop 자체의 기본 규칙이 헷갈리면 → REV-0437.
- ST(i) 상대 개념이나 TOP 포인터가 헷갈리면 → REV-0436.
- 정수 연산의 부호/플래그 규칙과 비교하고 싶으면 → REV-0047(ADD), REV-0048(SUB), REV-0051(IMUL).

## 미니 예제

**예제 1 — 단순 덧셈**
```asm
fld     dword ptr [a]
fadd    dword ptr [b]     ; ST(0) = a + b (메모리 피연산자, pop 없음)
fstp    dword ptr [result]
```

**예제 2 — FSUBR로 방향이 뒤집힌 뺄셈**
```asm
fld1                       ; ST(0) = 1.0
fld     dword ptr [x]      ; ST(0) = x, ST(1) = 1.0
fsubrp  st(1), st(0)       ; ST(1) = ST(0) - ST(1) = x - 1.0, pop → ST(0) = x - 1.0
fstp    dword ptr [result] ; result = x - 1.0  (즉 "1.0 - x"가 아님에 주의)
```

**예제 3 — 수식 `(a+b)*c`**
```asm
fld     dword ptr [a]
fld     dword ptr [b]
faddp   st(1), st(0)
fld     dword ptr [c]
fmulp   st(1), st(0)
fstp    dword ptr [result]
```

**예제 4 — 나눗셈 방향 확인**
```asm
fld     dword ptr [b]      ; ST(0) = b
fld     dword ptr [a]      ; ST(0) = a, ST(1) = b
fdivrp  st(1), st(0)       ; ST(1) = ST(0)/ST(1) = a/b, pop → ST(0) = a/b
fstp    dword ptr [result] ; result = a / b
```

## 관련 글
- REV-0436 — x87 FPU 스택 레지스터 개념 기초
- REV-0437 — FLD와 FSTP: x87 스택 로드/저장
- REV-0047 — ADD: 덧셈과 플래그
- REV-0048 — SUB: 뺄셈과 플래그
- REV-0051 — IMUL: Signed 곱셈과 컴파일러 패턴

## 출처/검증
- `FADD`/`FSUB`/`FSUBR`/`FMUL`/`FDIV`/`FDIVR` 및 `P`/`R` 접미사 규칙: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "FADD/FADDP/FIADD", "FSUB/FSUBP/FISUB", "FDIV/FDIVP/FIDIV" 섹션 기준 (2026-09-08 검증).
