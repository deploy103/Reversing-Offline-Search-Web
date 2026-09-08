---
id: REV-0424
title: "JP JPE JNP JPO: 패리티 플래그 기반 분기"
slug: "rev-0424-jp-jpe-jnp-jpo"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - jp
  - jpe
  - jnp
  - jpo
  - JP
  - JPE
  - JNP
  - JPO
  - jp 명령어
  - parity flag
  - 패리티 플래그
  - PF 플래그
  - NaN 검사
  - isnan
  - unordered comparison
  - ucomiss
  - ucomisd
  - fucomi
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - jp 뭐임
  - jpe가 뭐죠
  - jnp가 뭐죠
  - jpo가 뭐죠
  - 패리티 플래그 분기
  - NaN 판별 분기
symptom_keywords:
  - ucomiss 다음에 jp가 나오는데 뭔지 모르겠음
  - jp jnp가 뭔지 처음 봄
  - 패리티 플래그가 정수 짝수 홀수랑 관련있는줄 알았는데 아님
  - 부동소수점 비교 코드에 이상한 분기가 섞여있음
  - NaN 비교 코드가 이해 안 됨
---

## 한 줄 요약
`JP`(=`JPE`)/`JNP`(=`JPO`)는 패리티 플래그(PF)만 검사해서 분기하는 명령으로, 실전에서는 거의 항상 부동소수점 비교(`UCOMISS`/`COMISD`/`FUCOMI` 등) 뒤에 붙어 "비교 대상 중 하나가 NaN이라 순서를 정할 수 없다(unordered)"는 것을 감지하는 데 쓰인다.

## 언제 검색해야 하나
- `ucomiss`/`ucomisd`/`comiss`/`comisd` 같은 SSE 비교 명령 뒤에 `jp`나 `jnp`가 붙어 있는데 뭔지 모를 때
- `JP`가 "짝수(Parity Even)"라는 이름 때문에 정수의 짝/홀과 관련 있다고 오해하고 있을 때
- `isnan()`이나 `!=`/`==` 부동소수점 비교가 컴파일된 어셈블리를 분석할 때

## 핵심 개념

### 정확한 동작
- `JP`/`JPE` (Jump if Parity / Parity Even): `PF = 1`이면 분기.
- `JNP`/`JPO` (Jump if No Parity / Parity Odd): `PF = 0`이면 분기.

`JP`와 `JPE`는 완전히 동일한 명령의 서로 다른 이름(mnemonic alias)이고, `JNP`와 `JPO`도 마찬가지다 — opcode 레벨에서 차이가 없다.

`PF`(Parity Flag)는 직전 연산 결과의 **최하위 바이트(하위 8비트)**에 들어있는 1비트의 개수가 짝수면 1, 홀수면 0으로 설정된다. 32비트나 64비트 연산이어도 오직 하위 1바이트만 본다는 점이 중요한 함정이다.

### 이름 때문에 생기는 흔한 오해
"Parity(패리티)"라는 단어 때문에 "그 숫자가 짝수/홀수인가"를 판별하는 명령이라고 착각하기 쉽지만, 전혀 다르다. PF는 값 자체의 짝/홀이 아니라, **비트 표현에서 1의 개수**가 짝수/홀수인지를 본다. 예를 들어 `0000_0011`(십진수 3, 홀수)은 1비트가 2개(짝수)라서 PF=1이 된다. 값의 짝/홀과 비트 패리티는 서로 무관한 개념이다.

### 실전에서 진짜 중요한 용도: 부동소수점 NaN 검사
IEEE 754 부동소수점 비교에는 정수에 없는 특수 상태 **"unordered"**가 있다 — 비교 대상 중 하나 이상이 NaN(Not a Number)이면, `<`, `>`, `==` 어느 쪽으로도 순서를 매길 수 없다. SSE의 `UCOMISS`/`UCOMISD`/`COMISS`/`COMISD`, 그리고 x87의 `FUCOMI` 계열은 이 unordered 상태를 알리기 위해 `ZF:PF:CF = 1:1:1`로 설정한다(보통의 "같다"는 `ZF=1, PF=0, CF=0`이므로 PF의 유무로 구분 가능).

즉, 비교 직후 `PF=1`이라는 것은 "이 비교는 NaN이 껴서 무효(unordered)"라는 뜻이다. 그래서 `jp`/`jnp`는 부동소수점 비교의 **NaN 여부**를 확인하는 표준적인 방법이다.
```asm
ucomiss xmm0, xmm1
jp      unordered_nan   ; xmm0 또는 xmm1이 NaN이면 여기로 분기
jne     not_equal
; 여기 도달하면: NaN 아니고, 같음(==)
```

### 레지스터/메모리/플래그 영향
- 레지스터/메모리 영향 없음.
- 플래그를 전혀 바꾸지 않는다(PF 포함 읽기 전용).
- RIP: 분기 성립 시 목표 주소, 아니면 다음 명령. 스택 변화 없음.

### 정수 코드에서는 왜 거의 안 보이는가
일반 C 컴파일러는 `int`끼리의 `==`, `!=`, `<` 비교에서 PF를 검사하는 분기를 생성하지 않는다(ZF, SF, OF, CF만으로 충분하기 때문). `JP`/`JNP`가 정수 코드에서 나오는 경우는 사실상 없다고 봐도 되며, 나온다면 수작업으로 짠 비트 트릭이거나 난독화/안티디스어셈블 트릭일 가능성이 있다.

### IDA/Ghidra 디컴파일에서의 모습
`ucomiss`/`ucomisd` 다음에 붙는 `jp`/`jnp`는 디컴파일러가 float 비교 연산자(`==`, `!=`, `<`, `<=` 등)를 재구성할 때 함께 소비되어, 최종 C 유사 코드에는 `jp` 자체가 따로 드러나지 않고 그냥 `a < b`, `a != b` 같은 익숙한 조건식으로만 보이는 경우가 대부분이다. 다만 컴파일러 최적화 수준이 낮거나 디컴파일러가 패턴을 완전히 인식하지 못하면, `isnan(a) || isnan(b) || ...` 형태로 NaN 검사가 명시적으로 풀려서 나오기도 한다. 원문 disassembly에서 `jp`를 직접 봤을 때 "이건 그냥 부동소수점 비교의 NaN 처리 부분이구나"라고 즉시 인식할 수 있으면, 디컴파일 결과가 이상하게 복잡해 보여도 당황하지 않을 수 있다.

### 왜 이걸 알아두면 좋은가
CTF 문제에서 부동소수점 값을 비교하는 검증 로직(예: 어떤 부동소수점 계산 결과가 특정 값과 같아야 통과)을 분석할 때, `jp` 분기의 존재는 "NaN을 입력하면 이 비교를 어떻게 우회할 수 있는가"를 생각해볼 단서가 된다. 예를 들어 `!=` 비교에서 NaN은 항상 참(true)으로 취급되므로, 입력값을 NaN으로 만들 수 있다면 의도치 않게 검증을 통과시키는 경우가 있을 수 있다 — 다만 이는 어디까지나 부동소수점 IEEE 754 시맨틱을 이해하는 데 도움이 되는 참고 지식이다.

## 화면/코드에서 보이는 징후
```asm
ucomiss xmm0, xmm1
jp      unordered_nan
jne     not_equal
```
```asm
fucomip st, st(1)
jp      is_nan
```
정수 `CMP`/`TEST` 뒤에는 절대 안 붙는 것이 정상이며, 부동소수점 비교(`UCOMISS`류 또는 x87 `FUCOMI`류) 바로 뒤에 붙어 있는 것이 전형적인 패턴이다.

## 가장 먼저 할 것
1. `JP`/`JNP` 바로 앞의 명령이 정수 연산인지 부동소수점 비교(`UCOMISS`/`COMISD`/`FUCOMI` 등)인지 확인한다.
2. 부동소수점 비교라면 이 분기가 NaN(unordered) 케이스를 처리하는 로직임을 인지한다.
3. 만약 정수 연산 뒤에 있다면, 일반적인 컴파일러 산출물이 아니라 수작업/난독화 코드일 가능성을 의심한다.

## 단계별 절차
```c
if (a != b) { do_something(); }   // a, b: float
```
```asm
ucomiss xmm0, xmm1
jp      do_something     ; unordered(NaN 포함)면 "!="로 취급되어 분기
jne     do_something      ; 순서 비교 가능하고 실제로 다르면 분기
jmp     skip
```
1. `ucomiss`로 두 float를 비교.
2. IEEE 754 규칙상 NaN이 하나라도 있으면 `!=` 비교는 참(true)으로 취급돼야 하므로, `jp`로 unordered를 먼저 걸러 `do_something`으로 보낸다.
3. `jne`로 일반적인 부등호 판정을 이어서 처리.

## 명령어/단축키
- IDA/Ghidra: `isnan(a) || isnan(b) || a != b` 또는 `isunordered(a, b)` 형태로 재구성되는 경우가 많고, Ghidra는 내부적으로 `NAN()` 헬퍼 함수 형태로 표시하기도 한다.
- GDB/x64dbg: EFLAGS 창에서 `PF` 비트를 직접 확인한다.

## 출력 해석
- `PF=1`이면 `JP`가 분기 — 부동소수점 비교 문맥이라면 이는 NaN이 개입했다는 뜻.
- `PF=0`이면 `JNP`가 분기 — 정상적으로 순서를 매길 수 있는 비교였다는 뜻.

## 흔한 실수
- "Parity"라는 이름만 보고 정수 값의 짝/홀 판별 명령이라고 착각하는 것 — 실제로는 결과의 하위 1바이트에 있는 1비트 개수의 짝/홀이다.
- 32/64비트 연산 결과 전체의 패리티라고 착각하는 것 — PF는 항상 **하위 8비트만** 본다.
- 부동소수점 비교 문맥이 아닌데도 `JP`/`JNP`를 보고 당황하는 것 — 이런 경우는 매우 드물며, 대부분 x87/SSE 비교 근처에서만 정상적으로 등장한다는 점을 기억해두면 코드를 훑을 때 빠르게 문맥을 파악할 수 있다.

## 막혔을 때 다음 체크
- `JP`/`JNP` 바로 앞이 `UCOMISS`/`COMISD`/`FUCOMI` 계열인지 다시 확인했는가?
- 이 비교가 C의 `==`/`!=` 연산자에서 왔다면, `isnan()`/`isunordered()` 시맨틱이 반영된 것인지 재구성해봤는가?
- 정수 코드에서 나왔다면 난독화나 수작업 어셈블리 여부를 의심해봤는가?

## 미니 예제

**예제 1 — float 부등호 비교(NaN 포함 처리)**
```c
if (a != b) { flag = 1; }
```
```asm
ucomiss xmm0, xmm1
jp      set_flag        ; NaN 포함 -> "다르다"로 취급
jne     set_flag
jmp     done
set_flag:
    mov  dword ptr [flag], 1
done:
```

**예제 2 — 단순 패리티 판별(정수, 드문 경우)**
```asm
mov     al, 03h        ; 0000_0011 -> 1비트 2개(짝수)
test    al, al
jp      even_parity      ; PF=1이라 분기함
```

## 관련 글
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교
- REV-0067 — JE와 JZ: ZF가 1일 때 분기
- REV-0068 — JNE와 JNZ: ZF가 0일 때 분기
- REV-0421 — LAHF와 SAHF: 플래그를 AH로 옮기기
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- JP/JPE/JNP/JPO 명령어 동작과 PF 정의: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "Jcc—Jump if Condition Is Met" 섹션 기준 (2026-09-08 검증).
- UCOMISS/COMISS 등이 unordered 결과를 ZF:PF:CF=1:1:1로 인코딩하는 규칙: Intel SDM Volume 1, SSE 비교 명령 챕터 기준.
