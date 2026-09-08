---
id: REV-0426
title: "JC와 JNC: 캐리 플래그 기반 분기 별칭"
slug: "rev-0426-jc-jnc"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - JC
  - JNC
  - jump if carry
  - jump if not carry
  - 캐리 플래그 분기
  - CF 분기
  - carry flag jump
  - JB alias
  - JAE alias
  - JNAE
  - JNB
  - 캐리 점프
  - 자리올림 분기
aliases:
  - jc가 뭔가요
  - jnc가 뭔가요
  - jc jnc 차이
  - jc랑 jb 차이
  - 캐리 플래그로 점프
  - carry jump 명령어
symptom_keywords:
  - jc jnc가 뭔지 모르겠음
  - cmp 없이 갑자기 jc가 나옴
  - adc 다음에 jc가 나옴
  - 시프트 다음에 jc가 나옴
  - jc랑 jb가 같은 명령인지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`JC`(Jump if Carry)와 `JNC`(Jump if Not Carry)는 CF(캐리 플래그)가 1인지 0인지만 보고 분기하는 명령으로, 사실은 `JB`/`JNAE`(JC)와 `JAE`/`JNB`(JNC)와 **완전히 같은 기계어 opcode**를 갖는 "이름만 다른" 별칭이다.

## 언제 검색해야 하나
- 디스어셈블리에 `cmp`가 아니라 `add`, `shl`, `adc` 바로 뒤에 `jc`나 `jnc`가 나와서 무엇을 비교하는 건지 헷갈릴 때
- `jc`와 `jb`가 같은 명령인지, 왜 도구마다 다른 이름으로 표시되는지 궁금할 때
- 시프트/로테이트 명령(`SHL`, `SHR`, `ROL`, `ROR`) 뒤에 `jc`가 오는 코드를 만나서 "밀려난 비트"를 검사하는 패턴을 이해하고 싶을 때
- 128비트 이상의 큰 정수 덧셈/뺄셈(bignum) 코드를 리버싱하다가 자리올림을 추적해야 할 때

## 핵심 개념

### JC/JNC가 하는 일
`JC target`은 "CF(Carry Flag)가 1이면 target으로 점프"하고, `JNC target`은 "CF가 0이면 target으로 점프"한다. 그게 전부다 — 다른 플래그(ZF, SF, OF, PF)는 전혀 보지 않는다.

Intel SDM 기준으로 `JC`의 opcode는 `72 cb`(rel8) 또는 `0F 82 cd`(rel32)이고, `JNC`는 `73 cb`(rel8) 또는 `0F 83 cd`(rel32)다. 그런데 [REV-0070 — JA JAE JB JBE](./rev-0070-ja-jae-jb-jbe.md)에서 다룬 `JB`/`JNAE`도 정확히 `72/0F 82`이고, `JAE`/`JNB`도 정확히 `73/0F 83`이다. 즉 CPU 입장에서는 `JC`와 `JB`가 **완전히 동일한 명령**이며, 어셈블러/디스어셈블러가 문맥에 따라 어느 이름을 표시할지 고를 뿐이다. IDA와 objdump는 대개 `unsigned` 비교 문맥(직전에 `cmp`가 있을 때)에서는 `jb`/`jae`로, 순수하게 캐리 플래그만 다루는 문맥(직전에 `add`, `adc`, `shl` 등)에서는 `jc`/`jnc`로 표시하는 경향이 있지만 이는 관례일 뿐 강제 규칙은 아니다.

### 왜 CMP 없이 JC가 나오나
`JA`/`JB` 계열은 보통 `CMP` 직후에 나오는 것으로 배우기 쉽지만, CF는 `CMP`뿐 아니라 다음 명령들도 세팅한다.
- `ADD`, `ADC`: 부호 없는 덧셈에서 결과가 레지스터 폭을 넘으면(자리올림 발생) CF=1
- `SUB`, `SBB`: 부호 없는 뺄셈에서 빌림(borrow)이 필요하면 CF=1
- `SHL`/`SAL`, `SHR`, `SAR`, `ROL`, `ROR`, `RCL`, `RCR`: 시프트/로테이트로 **밀려나간 마지막 비트**가 그대로 CF에 저장됨

그래서 `add`/`shl` 바로 다음에 오는 `jc`/`jnc`는 "덧셈이 오버플로했는가" 또는 "밀려난 비트가 1이었는가"를 검사하는 것이지, 두 값의 대소를 비교하는 것이 아니다. `INC`/`DEC`는 예외적으로 CF를 건드리지 않으므로([REV-0049 — INC와 DEC](./rev-0049-inc-dec.md) 참고) 그 뒤에 `jc`가 온다면 그 CF는 더 이전 명령이 세팅한 값이라는 뜻이다.

### 플래그 영향
`JC`/`JNC` 자신은 **어떤 플래그도 바꾸지 않는다**. 그냥 CF를 읽기만 한다. 다른 모든 `Jcc` 계열과 동일하다.

### RIP/스택 변화
조건이 참이면 `RIP = RIP + rel8` (또는 rel32)로 갱신되어 target으로 점프한다. 조건이 거짓이면 다음 명령으로 그대로 진행한다(`RIP`는 이 명령의 길이만큼만 증가). 스택(RSP)에는 어떤 영향도 없다 — `CALL`과 달리 반환 주소를 남기지 않는다.

### 컴파일러가 만드는 전형적 패턴
1. **다중 정밀도(bignum) 덧셈**: `unsigned __int128`이나 자체 bignum 라이브러리의 128/256비트 덧셈에서 하위 절반을 `ADD`로 더하고, 상위 절반을 `ADC`로 더할 때 자리올림 전파 여부를 `JC`로 확인하는 경우가 있다.
2. **비트 검사 루프**: 데이터를 한 비트씩 시프트하며 밀려나간 비트를 `JC`/`JNC`로 분기해 처리하는 코드(CRC 계산, 압축 알고리즘의 비트 단위 파서 등)에서 자주 보인다.
3. **`unsigned int` 오버플로 검사**: C 코드에서 `if (a + b < a)` 같은 관용구(부호 없는 덧셈 오버플로 검사)를 작성하면 컴파일러가 `add`/`jc` 조합으로 최적화하는 경우가 있다.

## 화면/코드에서 보이는 징후
- `add eax, ebx` 다음 `jc overflow_handler` — unsigned 덧셈 오버플로 검사
- `shl eax, 1` 다음 `jc bit_was_set` — 최상위 비트가 1이었는지 검사
- `adc edx, ecx` 다음 `jnc no_carry_propagation` — 다중 정밀도 덧셈에서 자리올림 전파 여부 확인
- 디스어셈블러에 따라 같은 바이트열이 `jb`/`jnb`로 표시될 수도 있음 (opcode가 동일하기 때문)

## 가장 먼저 할 것
`jc`/`jnc`를 만나면 순서대로 확인한다.
1. 바로 위 명령이 `CMP`인가, 아니면 `ADD`/`ADC`/`SUB`/`SBB`/시프트/로테이트인가.
2. `CMP` 뒤라면 사실상 `JB`/`JAE`와 동일하게 unsigned 크기 비교로 해석한다 ([REV-0070](./rev-0070-ja-jae-jb-jbe.md) 참고).
3. 산술/시프트 명령 뒤라면 "오버플로/자리올림/밀려난 비트"를 검사하는 것으로 해석한다.

## 단계별 절차
**1) 다중 정밀도 덧셈 추적**
```asm
mov  eax, [rsi]        ; 하위 32비트
add  eax, [rdi]
mov  [rbx], eax
mov  eax, [rsi+4]      ; 상위 32비트
adc  eax, [rdi+4]      ; 이전 ADD의 CF를 반영
jnc  done
inc  dword ptr [rbx+8] ; 자리올림이 더 위 워드로 전파
done:
mov  [rbx+4], eax
```
`add` 다음 `adc`, 그 뒤 `jc`/`jnc`가 나오면 128비트 이상의 정수 연산 조각임을 바로 알 수 있다.

**2) 디버거로 CF 직접 확인**
x64dbg/IDA 디버거의 레지스터 창에서 `C` 표시(CF)를 보고, `jc`/`jnc` 직전에 F7/F8로 한 줄씩 실행하며 그 값이 바뀌는지 관찰한다. GDB/Pwndbg는 `info registers eflags`로 `[ CF ... ]` 목록에 CF가 포함되는지 확인한다.

## 명령어/단축키
- IDA: 명령어 위에서 `Alt+G`(그래프 뷰의 True/False 색 분기), 레지스터 창의 EFLAGS 옆 `C` 항목
- x64dbg: 레지스터 패널의 `CF` 값, F7/F8로 스텝하며 관찰
- GDB/Pwndbg: `info registers eflags` (`i r eflags`)

## 출력 해석
- `CF=1` 상태에서 `jc`가 실행되면 분기가 성립(taken)된다.
- `add`/`adc` 직후 CF가 1이면 "unsigned 폭을 넘는 자리올림이 발생했다"는 뜻이지 "결과가 크다/작다"는 별개의 의미이므로 signed 관점과 섞어서 해석하지 않는다.

## 흔한 실수
- `JC`를 signed 비교로 착각하는 것 — CF는 항상 unsigned 관점의 신호다. signed 오버플로는 OF([REV-0088](./rev-0088-flags-overview.md) 참고)가 담당한다.
- `INC`/`DEC` 다음에 `jc`가 온 걸 보고 "이 INC가 CF를 세팅했다"고 착각하는 것 — `INC`/`DEC`는 CF를 절대 바꾸지 않으므로 그 CF는 더 이전 명령이 남긴 값이다.
- `jc`와 `jb`가 다른 명령이라고 생각해서 디스어셈블러마다 다르게 표시되면 당황하는 것 — opcode가 완전히 같은 별칭이다.
- 시프트 명령 뒤의 `jc`를 "덧셈 오버플로"로 오해하는 것 — 시프트 뒤 CF는 밀려난 비트를 의미하므로 문맥(직전 명령의 종류)을 항상 먼저 확인해야 한다.

## 막혔을 때 다음 체크
- CF가 왜 그 값인지 모르겠다면 → 바로 위 명령을 [REV-0088 — 플래그 레지스터 개요](./rev-0088-flags-overview.md)의 "어떤 명령어가 어떤 플래그를 바꾸는가" 표에서 찾아본다.
- `jc`/`jb` 어느 이름으로 표시되든 헷갈리면 → [REV-0070](./rev-0070-ja-jae-jb-jbe.md)의 unsigned 비교 매핑표와 대조한다.
- CF를 명시적으로 세팅/클리어하는 코드를 찾고 싶다면 → `CLC`/`STC`/`CMC`(REV-0418, 예정) 명령을 검색한다.

## 미니 예제
**예제 1 — 시프트로 최상위 비트 검사**
```asm
mov  al, [byte_val]
shl  al, 1        ; 최상위 비트(bit 7)가 CF로 밀려남
jc   was_negative_bit_set
```

**예제 2 — unsigned 덧셈 오버플로 검사 (C의 `if (a+b < a)` 관용구)**
```c
unsigned int a, b;
if (a + b < a) { overflow_handler(); }
```
```asm
add  eax, ebx
jc   overflow_handler
```

**예제 3 — JC와 JB가 같은 바이트임을 보여주는 예**
```asm
cmp  eax, ebx
jb   less_unsigned   ; 디스어셈블러가 이렇게 표시할 수도 있고
; jc less_unsigned   ; 완전히 동일한 opcode(72 cb)로 이렇게 표시될 수도 있음
```

## 관련 글
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기
- REV-0427 — ADC: 캐리 포함 덧셈
- REV-0428 — SBB: 캐리 포함 뺄셈
- REV-0049 — INC와 DEC: 1 증가 감소와 CF 주의
- REV-0418 — CLC STC CMC: 캐리 플래그 직접 조작

## 출처/검증
- `JC`/`JNC`의 opcode(`72`/`73`/`0F 82`/`0F 83`)와 `JB`/`JAE`와의 동일성: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "Jcc—Jump if Condition Is Met" 조건 코드(tttn) 표 기준 (2026-09-08 검증).
- CF에 영향을 주는 명령 목록(ADD, ADC, SUB, SBB, 시프트/로테이트 계열): Intel SDM Volume 2A/2B 각 명령어 "Flags Affected" 절 기준.
