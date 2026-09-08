---
id: REV-0417
title: "WAIT/FWAIT: FPU 동기화 명령 기초"
slug: "rev-0417-wait-fwait"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - wait
  - fwait
  - WAIT
  - FWAIT
  - Fwait
  - wait 명령어
  - fwait 명령어
  - x87 FPU
  - x87 동기화
  - FPU 예외 확인
  - pending FPU exception
  - floating point synchronization
  - 부동소수점 동기화
  - 0x9B opcode
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - wait 뭐임
  - fwait가 뭐죠
  - fwait 명령
  - x87 wait
  - fpu wait 명령어
symptom_keywords:
  - fwait가 왜 있는지 모르겠음
  - wait 명령어를 delay로 착각함
  - x87 코드에서 fwait이 계속 나옴
  - fstp 다음에 fwait이 붙어있음
  - long double 코드에서 이상한 명령어가 보임
---

## 한 줄 요약
`WAIT`(어셈블러 표기로는 `FWAIT`)는 CPU를 시간 동안 재우는 명령이 아니라, x87 FPU에 아직 처리되지 않은(마스크 해제된) 부동소수점 예외가 있는지 확인하고 동기화하는 명령어다.

## 언제 검색해야 하나
- 오래된 32비트 바이너리나 `long double` 관련 코드를 리버싱하는데 `fwait`가 반복해서 보일 때
- `WAIT`라는 이름 때문에 "일정 시간 대기(sleep)"하는 명령으로 오해하고 있을 때
- `fstp`, `fld`, `finit` 같은 x87 명령 사이에 `fwait`가 왜 끼어 있는지 궁금할 때

## 핵심 개념

### WAIT와 FWAIT는 같은 명령
opcode `0x9B` 하나뿐이며, `WAIT`와 `FWAIT`는 완전히 동일한 명령어에 대한 두 가지 어셈블리 표기다. 관례적으로 x87 부동소수점 명령들 사이에 단독으로 쓸 때는 `FWAIT`라고 쓰는 경우가 많다(다른 x87 명령들이 대개 `F`로 시작하는 것과 통일하기 위함일 뿐, 동작 차이는 없다).

### 실제로 하는 일
x87 FPU는 역사적으로(8087 시절) CPU와 분리된 코프로세서였다. `WAIT`는:
1. FPU의 상태 워드(status word)에 처리되지 않은, **마스크 해제된** 부동소수점 예외(무효 연산, 0으로 나누기, 오버플로/언더플로 등)가 있는지 확인한다.
2. 있다면 `#MF`(x87 부동소수점 예외, 인터럽트 벡터 16)를 발생시켜 예외 처리기로 넘어간다.
3. 없다면 그냥 다음 명령으로 넘어간다(사실상 no-op처럼 보인다).

즉 이름과 달리 "시간"과는 아무 관련이 없다. 정밀한 예외 지점(precise exception)을 보장하기 위한 동기화 지점일 뿐이다.

### F 접두사 없는 명령 vs 있는 명령
많은 x87 명령어는 "wait 포함" 버전과 "wait 없는(N, No-wait)" 버전이 짝을 이룬다. 예를 들어 `FSTSW`(상태 워드 저장, 암묵적 wait 포함)와 `FNSTSW`(wait 없이 즉시 저장)가 그렇다. `FNSTSW` 뒤에 `WAIT`/`FWAIT`가 별도로 붙어 있다면 결국 wait 포함 버전과 같은 효과를 명시적으로 만든 것이다.

### 플래그/레지스터 영향
- `WAIT`/`FWAIT`는 EFLAGS의 어떤 비트도 바꾸지 않는다.
- 범용 레지스터(RAX 등)나 메모리도 직접 건드리지 않는다.
- 오직 x87 FPU 내부 상태(예외 플래그 확인)에만 관여하며, 예외가 나면 예외 처리기로 제어가 넘어간다는 점에서 간접적으로 실행 흐름에 영향을 줄 수 있다.
- 스택(RSP)이나 RIP에는 정상 실행 시(예외 없을 때) 다음 명령으로 넘어가는 것 외의 변화가 없다.

### 역사적 배경
`WAIT`라는 이름은 8086/8087 시절 CPU와 FPU가 물리적으로 분리된 두 개의 칩이었던 데서 유래한다. 당시 8087 코프로세서는 8086과 독립적으로 명령을 실행했기 때문에, 8086이 FPU 연산 결과를 메모리에서 읽으려 할 때 FPU가 아직 계산을 끝내지 못했을 수 있었다. `WAIT`는 이런 상황에서 "FPU가 준비될 때까지, 그리고 예외가 없는지 확인될 때까지" 동기화 지점 역할을 했다. 이후 FPU가 CPU 다이 안으로 통합된 이후에도(80486부터) 이 명령은 예외 동기화 목적으로 계속 남아 있다.

### 리버싱 관점에서의 의미
`FWAIT`가 자주 등장하는 함수는 거의 항상 x87 스택 기반 부동소수점 연산을 사용한다는 뜻이다. 최신 x86-64 코드에서 `double`/`float` 연산은 대부분 SSE2 명령(`movsd`, `addsd`, `mulss` 등)으로 컴파일되므로, `fwait`가 눈에 띈다면 다음 중 하나를 의심해볼 수 있다: (1) 32비트 타깃으로 컴파일된 오래된 바이너리, (2) `long double`(x86 확장 정밀도, 80비트)을 사용하는 함수, (3) 컴파일러가 특정 옵션(`-mfpmath=387` 등)으로 x87을 강제한 경우. 이 신호만으로도 해당 함수가 정밀도에 민감한 수치 계산(과학 연산, 금융 계산 등)일 가능성을 짐작할 수 있다.

## 화면/코드에서 보이는 징후
```asm
fstp    qword ptr [rbp-8]
fwait
```
```asm
finit
fwait
```
```asm
fnstsw  ax
sahf
```
x87 부동소수점 저장/초기화 명령 뒤에 `fwait`가 단독으로 한 줄 등장하는 패턴이 전형적이다.

## 가장 먼저 할 것
`fwait`를 만나면 "여기서 시간이 지연되나?"라고 생각하지 말고, 바로 위/아래에 있는 x87 명령(`fld`, `fstp`, `fadd`, `finit` 등)이 무엇을 하는지부터 확인한다. `fwait`는 그 x87 연산의 부수적 동기화 단계일 뿐이므로, 실제 로직은 옆의 x87 명령에 있다.

## 단계별 절차
1. `fwait`가 있는 함수 전체를 훑어 x87 스택 명령(`fld`, `fstp`, `fadd`, `fmul`, `fcom` 등)이 섞여 있는지 확인한다 — 있다면 이 함수는 x87 기반 부동소수점 코드다(SSE2 `movss`/`addss`가 아니라).
2. 32비트 바이너리이거나 Linux x86-64에서 `long double`을 다루는 함수라면 x87 코드가 등장하는 것이 정상이다.
3. `fwait`는 무시하고 넘어가도 로직 이해에는 지장이 없다 — 단, 예외 처리 경로(부동소수점 예외 핸들러)를 분석해야 하는 특수한 경우라면 이 지점이 예외 발생 지점이 될 수 있음을 기억한다.

## 명령어/단축키
- IDA/Ghidra: 별도 특수 처리 없이 그냥 disassembly에 원문 그대로 표시된다. F5 디컴파일 결과에서는 대개 생략되거나 흔적이 남지 않는다.
- GDB: `info registers` 대신 x87 상태 확인은 `info all-registers`로 FPU 상태 워드(`fctrl`, `fstat`)를 볼 수 있다.

## 출력 해석
- 디컴파일된 C 코드에는 `fwait` 자체가 거의 드러나지 않는다 — 이 명령이 만들어내는 유일한 "결과"는 예외가 있으면 예외를 던지는 것뿐이므로, 정상 실행에서는 아무 흔적도 안 남는다.
- GDB에서 `info float`를 치면 x87 스택(ST0~ST7)과 상태 워드를 볼 수 있어, `fwait` 직전 상태를 점검할 때 유용하다.

## 흔한 실수
- 이름만 보고 "sleep()"이나 "일정 시간 대기"라고 오해하는 것 — 실제로는 시간과 전혀 무관하다.
- `fwait`가 코드의 핵심 로직이라고 오판해 시간을 들여 분석하는 것 — 대부분의 경우 그냥 넘어가도 된다.
- x87 코드 자체를 낯설어해서 분석을 포기하는 것 — x87은 SSE2 이전(또는 `long double`)에서만 쓰이므로, 최신 64비트 `double`/`float` 코드라면 보통 `movss`/`addsd` 같은 SSE 명령을 봐야 정상이다. `fwait`가 계속 나온다면 이 함수가 예외적으로 x87 경로를 쓰고 있다는 신호로 받아들인다.

## 막혔을 때 다음 체크
- 이 바이너리가 32비트인지 64비트인지 다시 확인 — 32비트 x86이라면 x87/`fwait`가 흔하다.
- `long double`을 쓰는 함수인지 소스/심볼 이름으로 추정해본다.
- 예외 처리와 무관한 일반 흐름 분석이라면 `fwait`는 그냥 건너뛰어도 된다.

## 미니 예제

**예제 1 — 부동소수점 결과 저장 + 동기화**
```c
double d = compute();
```
```asm
call    compute
fstp    qword ptr [rbp-8]   ; x87 스택 top(ST0)을 메모리에 저장하고 pop
fwait                        ; 저장 중 발생했을 수 있는 FPU 예외 확인
```

**예제 2 — FPU 초기화 후 동기화**
```asm
finit                 ; x87 FPU 상태 초기화
fwait                  ; 초기화가 실제로 반영됐는지, 예외 없는지 동기화
```

C 근사치: `WAIT`/`FWAIT`에 정확히 대응하는 C 코드는 없다. 굳이 개념적으로 표현하면 `if (fetestexcept(FE_ALL_EXCEPT)) raise_fp_exception();` 정도지만, 이는 컴파일러가 내부적으로 삽입하는 동기화 지점이라 소스 레벨에는 보이지 않는다.

## 관련 글
- REV-0421 — LAHF와 SAHF: 플래그를 AH로 옮기기
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기
- REV-0046 — PUSHF와 POPF: 플래그 저장과 복원

## 출처/검증
- WAIT/FWAIT 명령어 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "WAIT/FWAIT—Wait" 섹션 기준 (2026-09-08 검증).
- x87 FPU 예외 및 상태 워드 개념: Intel SDM Volume 1, "x87 FPU" 챕터 기준.
