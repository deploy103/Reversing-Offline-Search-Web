---
id: REV-0421
title: "LAHF와 SAHF: 플래그를 AH로 옮기기"
slug: "rev-0421-lahf-sahf"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - lahf
  - sahf
  - LAHF
  - SAHF
  - lahf 명령어
  - sahf 명령어
  - AH 레지스터
  - flags to AH
  - AH to flags
  - fnstsw sahf
  - x87 비교
  - x87 comparison
  - fcom fnstsw sahf
  - 플래그 저장 복원
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - lahf 뭐임
  - sahf가 뭐죠
  - AH로 플래그 옮기기
  - fnstsw 다음 sahf
  - x87 플래그 비교
symptom_keywords:
  - fnstsw ax 다음에 sahf가 나옴
  - lahf sahf가 왜 있는지 모르겠음
  - x87 비교 코드에서 이상한 AH 조작이 보임
  - sahf가 pushf popf랑 뭐가 다른지 모르겠음
  - of 플래그가 sahf 이후에도 안 바뀜
---

## 한 줄 요약
`LAHF`는 EFLAGS 하위 바이트(SF, ZF, AF, PF, CF)를 `AH` 레지스터로 읽어오고, `SAHF`는 반대로 `AH`의 값을 EFLAGS 하위 바이트에 써넣는 명령어로, 주로 오래된 x87 부동소수점 비교 결과를 일반 조건 분기(Jcc)로 연결할 때 쓰인다.

## 언제 검색해야 하나
- `fcom`/`fucomip` 같은 x87 비교 명령 뒤에 `fnstsw ax`와 `sahf`가 붙어 있는 패턴을 봤을 때
- `lahf`/`sahf`가 `PUSHF`/`POPF`와 어떻게 다른지 궁금할 때
- `sahf` 다음에 `jo`(오버플로 분기)를 썼는데 왜 항상 의도대로 동작하지 않는지 이해가 안 될 때

## 핵심 개념

### 정확한 동작과 비트 매핑
`LAHF`(Load Status Flags into AH)는 EFLAGS의 하위 8비트를 다음과 같이 `AH`에 복사한다(비트 7이 MSB):
```
AH = SF ZF 0 AF 0 PF 1 CF
     bit7 6 5 4  3 2  1 0
```
`SAHF`(Store AH into Flags)는 정확히 반대 방향으로, `AH`의 해당 비트들을 읽어 `SF`, `ZF`, `AF`, `PF`, `CF`에 다시 써넣는다(비트 1, 3, 5의 예약된 값은 무시/고정).

**핵심: `OF`(오버플로 플래그)는 이 둘 어디에도 포함되지 않는다.** `LAHF`는 OF를 읽지 않고, `SAHF`는 OF를 건드리지 않는다. `DF`, `IF` 같은 다른 상위 플래그들도 마찬가지로 대상이 아니다.

### PUSHF/POPF와의 차이
`PUSHF`/`POPF`(REV-0046)는 전체 EFLAGS(16/32/64비트 전부)를 스택에 저장/복원하지만, `LAHF`/`SAHF`는 오직 5개 플래그(SF, ZF, AF, PF, CF)만, 그것도 스택이 아니라 `AH` 레지스터 하나로 다룬다. 그만큼 가볍고 빠르지만 다룰 수 있는 플래그 범위가 좁다.

### 64비트 모드에서의 가용성
초기 x86-64 설계에서는 `LAHF`/`SAHF`가 제거될 뻔했으나, 이후 대부분의 64비트 CPU에서 다시 사용 가능하도록 복원되었다(CPUID로 지원 여부 확인 가능). 오늘날 상용 x64 CPU에서는 사실상 항상 사용 가능하다고 봐도 된다.

### 가장 흔한 실전 등장 장소: x87 부동소수점 비교
SSE2 이전(또는 `long double`을 다루는 코드)에서는 부동소수점 비교가 EFLAGS를 직접 설정하지 않는다. 대신 x87 FPU 자체의 "상태 워드(status word)"에 비교 결과(C0, C2, C3 비트)를 기록한다. 이 결과를 일반 `Jcc`로 분기하려면 다음과 같은 3단계 변환이 필요하다:
```asm
fcom    qword ptr [rbp-8]  ; ST(0)과 메모리 값을 x87 방식으로 비교 -> C0,C2,C3에 결과 기록
fnstsw  ax                  ; FPU 상태 워드를 AX로 복사 (AH에 C0,C2,C3가 특정 비트로 매핑됨)
sahf                         ; AH의 내용을 CPU 플래그(ZF, PF, CF)로 반영
jbe     less_or_equal        ; 이제 일반 Jcc로 분기 가능
```
x87 상태 워드의 C0/C2/C3 비트는 `SAHF` 이후 CF/PF/ZF 위치에 맞춰지도록 설계되어 있어서, 이 시퀀스만으로 `<`, `<=`, `==` 같은 비교를 정수 비교처럼 `JB`/`JBE`/`JE` 등으로 분기할 수 있게 된다.

### 플래그/레지스터/스택 영향 요약
- `LAHF`: 플래그는 전혀 바꾸지 않는다(읽기만). `AH` 레지스터를 덮어쓴다(하위 8비트, `AL`/나머지 `RAX`는 그대로).
- `SAHF`: `AH`는 바꾸지 않는다(읽기만). `CF`, `PF`, `AF`, `ZF`, `SF`를 `AH`의 값으로 덮어쓴다. `OF`는 변하지 않는다.
- 둘 다 스택/RSP 변화 없음. RIP는 명령어 길이만큼 증가.

## 화면/코드에서 보이는 징후
```asm
fcom    qword ptr [rbp-8]
fnstsw  ax
sahf
jbe     less_or_equal
```
```asm
lahf
; ... AH 값을 보존한 채 다른 연산 수행 ...
sahf
```
`fnstsw ax` 바로 뒤에 `sahf`가 오는 조합은 x87 부동소수점 비교의 사실상 표준 패턴이므로, 이 조합을 보면 바로 "부동소수점 대소 비교구나"라고 인식할 수 있어야 한다.

## 가장 먼저 할 것
1. `sahf` 앞에 `fnstsw ax`(또는 `fstsw ax`)가 있는지 확인한다 — 있다면 x87 부동소수점 비교의 일부다.
2. `sahf` 직후의 `Jcc`가 `JB`/`JBE`/`JE`/`JA`/`JAE` 계열(CF/ZF 기반)인지 확인한다 — `JL`/`JG` 같은 부호(signed) 비교 계열이나 `JO`/`JNO`가 뒤따르면 이상하다는 신호다. OF는 SAHF로 복원되지 않기 때문이다.
3. 이 부동소수점 비교가 소스에서 `if (a < b)`, `if (a == b)` 같은 어떤 조건이었을지 매핑해본다.

## 단계별 절차
1. `fcom`/`fcomp`/`fucomi` 등 x87 비교 명령의 오퍼랜드(비교 대상 두 값)를 확인한다.
2. `fnstsw ax` → `sahf` → `Jcc` 3단계를 하나의 논리적 비교 블록으로 묶어 읽는다.
3. `Jcc`의 종류(JB=미만, JBE=이하, JE=같음, JA=초과, JAE=이상)를 원래 소스의 비교 연산자로 되짚는다.
4. 함수 전체에서 SSE2 명령(`movss`, `comiss`, `ucomiss`)이 하나도 안 보이고 이런 x87 패턴만 있다면, 오래된 32비트 코드거나 `long double` 연산일 가능성이 크다.

## 명령어/단축키
- IDA/Ghidra: 이 3~4줄 시퀀스를 통째로 인식해 디컴파일 결과에서는 그냥 `if (a <= b) { ... }` 같은 단순 비교로 보여주는 경우가 많다 — 실제 `sahf`/`fnstsw` 흔적은 원문 disassembly에서만 보인다.
- GDB: `info registers eflags`로 SAHF 실행 전후 플래그 변화를 확인할 수 있다.

## 출력 해석
- 디버거에서 `sahf` 실행 직후 `ZF`, `CF`, `PF`, `SF`, `AF`만 바뀌고 `OF`는 그대로인 것을 확인하면 정상 동작이다.
- `AH`에 담긴 값의 하위 비트를 이진수로 펼쳐보면(`CF`=비트0, `PF`=비트2, `AF`=비트4, `ZF`=비트6, `SF`=비트7) 어떤 플래그가 몇으로 설정될지 직접 계산해볼 수 있다.

## 흔한 실수
- `LAHF`/`SAHF`가 전체 EFLAGS(32/64비트 전부)를 다룬다고 착각하는 것 — 실제로는 하위 8비트, 그중에서도 5개 플래그(SF,ZF,AF,PF,CF)만 다룬다.
- `SAHF` 뒤에 `JO`/`JNO`(오버플로 분기)를 기대하는 것 — `OF`는 `SAHF`로 복원되지 않으므로 이런 분기는 `SAHF` 이전의 값을 그대로 쓰게 되어 의미가 없거나 버그가 된다.
- `PUSHF`/`POPF`와 완전히 같은 기능이라고 오해하는 것 — `LAHF`/`SAHF`는 더 가볍지만 다루는 플래그 범위가 좁고, 스택이 아니라 `AH` 레지스터를 매개로 한다.
- `fnstsw ax` 이후 `sahf` 없이 바로 `AH`/`AL` 값을 직접 비트마스크(`test ah, 0x41`)로 검사하는 대안 패턴을 보고 "SAHF가 없으니 이건 다른 거다"라고 오판하는 것 — 두 방식(SAHF 후 Jcc / AH 직접 비트 테스트)은 동일한 x87 비교 결과를 다르게 소비하는 것뿐이다.

## 막혔을 때 다음 체크
- `sahf` 앞에 `fnstsw`/`fstsw`가 있는지 다시 확인했는가? 없다면 순수하게 플래그를 임시 저장/복원하는 일반적인 용도일 수 있다.
- 뒤따르는 `Jcc`가 CF/ZF 기반(부호 없는 비교 계열)인지 확인했는가?
- 이 함수가 SSE2 대신 x87을 쓰는 이유(32비트 타깃, `long double`, 또는 구형 컴파일러 옵션)를 확인했는가?

## 미니 예제

**예제 1 — x87 부동소수점 비교 → 일반 분기**
```c
if (a <= b) { do_something(); }
```
```asm
fld     qword ptr [a]
fcom    qword ptr [b]
fnstsw  ax
sahf
ja      skip           ; a > b 이면 건너뜀 (즉 a <= b 일 때만 do_something 실행)
call    do_something
skip:
```

**예제 2 — LAHF로 가벼운 플래그 백업**
```asm
lahf                  ; 현재 SF ZF AF PF CF를 AH에 저장
mov     [saved_ah], ah
; ... 플래그를 바꾸는 다른 연산 수행 ...
mov     ah, [saved_ah]
sahf                   ; 저장해둔 플래그로 복원
```

## 관련 글
- REV-0046 — PUSHF와 POPF: 플래그 저장과 복원
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기
- REV-0417 — WAIT/FWAIT: FPU 동기화 명령 기초
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기

## 출처/검증
- LAHF/SAHF 명령어 동작과 AH 비트 매핑: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "LAHF—Load Status Flags into AH Register" / "SAHF—Store AH into Flags" 섹션 기준 (2026-09-08 검증).
- x87 FCOM/FNSTSW 기반 비교 후 SAHF/Jcc 변환 패턴: Intel SDM Volume 1, x87 FPU 비교 명령 챕터 기준.
