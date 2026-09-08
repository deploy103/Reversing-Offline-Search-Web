---
id: REV-0046
title: "PUSHF와 POPF: 플래그 저장과 복원"
slug: "rev-0046-pushf-popf"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - pushf
  - PUSHF
  - Pushf
  - pushfd
  - PUSHFD
  - pushfq
  - PUSHFQ
  - popf
  - POPF
  - Popf
  - popfd
  - POPFD
  - popfq
  - POPFQ
  - pushf 명령어
  - popf 명령어
  - flags 저장
  - flags 복원
  - eflags 스택
  - rflags 스택
  - 플래그 레지스터 저장
  - 플래그 레지스터 복원
  - 플래그 백업
aliases:
  - pushf 뭐임
  - popf 뭐임
  - pushfq 뭐임
  - popfq 뭐임
  - 플래그 저장 명령어
  - 플래그 복원 명령어
  - eflags 백업
symptom_keywords:
  - 플래그가 왜 스택에 저장되는지 모르겠음
  - 안티디버깅에서 pushfd가 왜 나오는지 모르겠음
  - trap flag 확인 코드
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`PUSHF`(x64에서는 `PUSHFQ`)는 플래그 레지스터(`RFLAGS`) 전체를 스택에 저장하고, `POPF`(x64에서는 `POPFQ`)는 스택에서 값을 꺼내 플래그 레지스터 전체를 복원한다. 개별 플래그 비트를 직접 읽고 쓸 수 있는 몇 안 되는 방법이라, 안티 디버깅 트릭에서 자주 등장한다.

## 언제 검색해야 하나
- `pushfq`, `popfq`(x64) 또는 `pushfd`, `popfd`(x86) 명령어를 만났는데 왜 필요한지 궁금할 때
- 안티 디버깅 코드에서 TF(Trap Flag)를 확인/조작하는 패턴을 분석하고 싶을 때
- 플래그 레지스터 값 전체를 한 번에 백업했다가 나중에 그대로 되돌리는 코드를 이해하고 싶을 때
- `CPUID` 지원 여부를 확인하는 코드(EFLAGS의 ID 비트 토글)를 분석할 때

## 핵심 개념

### 왜 플래그를 "직접" 레지스터처럼 다룰 수 없는가
`CMP`, 산술 명령어 등은 플래그(ZF, CF, SF, OF 등)를 결과로 세팅하지만, 일반 명령어로는 **플래그 레지스터 전체를 하나의 값으로 읽거나 쓸 수 없다** — `mov eax, eflags` 같은 명령어는 존재하지 않는다. 플래그를 "값 하나"로 다루고 싶을 때(예: 백업했다가 나중에 정확히 그대로 복원하고 싶을 때, 혹은 보통은 접근 못 하는 특정 비트를 조작하고 싶을 때) 쓰는 방법이 바로 PUSHF/POPF다 — 스택을 경유해서 플래그 레지스터 전체를 일반 메모리 값처럼 다루는 것이다.

### 동작
```
PUSHF(Q):
  1. RSP = RSP - 8 (x64) / ESP -= 2 or 4 (x86, 모드에 따라)
  2. [RSP] = RFLAGS 전체 값

POPF(Q):
  1. RFLAGS = [RSP] 전체 값
  2. RSP = RSP + 8 (x64)
```
[PUSH](./rev-0044-push.md)/[POP](./rev-0045-pop.md)과 동일한 스택 규칙을 따르되, 오퍼랜드가 항상 "플래그 레지스터 전체"로 고정되어 있다는 점만 다르다. x64에서는 `PUSHFQ`/`POPFQ`가 8바이트 단위로 동작하며(상위 32비트는 예약되어 있어 실질적으로 하위 32비트 EFLAGS와 동일한 정보), 32비트 모드에서는 `PUSHFD`/`POPFD`(4바이트, EFLAGS 전체) 또는 레거시 `PUSHF`/`POPF`(2바이트, FLAGS)가 있다.

### 플래그: 명령어 자신이 플래그를 "바꾸는" 특이 케이스
- `PUSHF`는 플래그를 스택에 쓰기만 할 뿐, 플래그 자체의 값을 바꾸지는 않는다.
- `POPF`는 스택에서 읽은 값으로 **플래그 레지스터 전체를 덮어쓴다** — 즉 ZF, CF, SF, OF, TF, IF 등 거의 모든 플래그가 스택에 있던 값으로 강제로 바뀐다. 이건 다른 대부분의 명령어("자기 계산 결과에 따라 일부 플래그만 세팅")와 근본적으로 다른 동작이므로 주의해야 한다.

### 안티 디버깅에서의 활용 — TF(Trap Flag) 검사
EFLAGS의 비트 8은 **TF(Trap Flag)**다. TF가 1이면 CPU는 명령어를 하나 실행할 때마다 디버그 예외(싱글 스텝)를 발생시킨다 — 디버거가 "한 줄씩 실행(step)"할 때 내부적으로 이 비트를 이용한다. 악성코드나 안티 디버깅 루틴은 다음과 같은 방식으로 "내가 지금 디버거에 의해 싱글 스텝 중인가?"를 스스로 확인하기도 한다:
```asm
pushfd
or  dword ptr [esp], 100h   ; TF 비트(0x100)를 강제로 세팅
popfd                        ; 이 popfd 실행 직후 CPU가 TF=1 상태가 됨
                              ; -> 다음 명령어 실행 후 디버그 예외 발생 예상
```
디버거가 이미 싱글 스텝 중이라면 이 트릭이 예상과 다르게 동작해서 차이를 감지당할 수 있다. 리버싱 중 `pushfd`/`popfd`와 `0x100`(TF 비트 마스크) 조합을 보면 안티 디버깅 코드일 가능성을 의심해야 한다.

### CPUID 지원 여부 확인 — ID 비트 토글
EFLAGS의 비트 21은 **ID 비트**로, 이 비트를 토글할 수 있는지(써서 실제로 바뀌는지) 확인하는 것이 오래된 CPU에서 `CPUID` 명령어 지원 여부를 검사하는 표준 방법이었다:
```asm
pushfd
pop   eax
mov   ecx, eax
xor   eax, 200000h     ; ID 비트(0x200000) 토글
push  eax
popfd
pushfd
pop   eax
xor   eax, ecx           ; 토글이 실제로 반영됐는지 비교
```
요즘 x86-64 CPU는 전부 CPUID를 지원하므로 이 검사 자체는 레거시지만, 디스어셈블리에서 이 패턴을 보면 "CPUID 지원 검사"라고 바로 알아볼 수 있으면 좋다.

### 함수 호출 전후 플래그 보존이 필요할 때
어떤 코드가 플래그 값에 의존하는 로직 사이에 다른 계산을 끼워 넣어야 하는데, 그 계산이 플래그를 건드리면 안 되는 상황이라면 `pushfd`로 백업해두고 계산 후 `popfd`로 복원하는 패턴이 쓰이기도 한다. 다만 일반적인 컴파일러 출력에서는 드물고, 손으로 쓴 어셈블리나 인터럽트 핸들러, 컨텍스트 스위칭 코드에서 더 자주 보인다.

## 화면/코드에서 보이는 징후
- `pushfq` / `popfq` — x64에서 플래그 전체 백업/복원
- `pushfd` / `popfd` — x86(32비트)에서 플래그 전체 백업/복원
- `pushfd` 직후 `or dword ptr [esp], 100h` — TF 비트 세팅 시도, 안티 디버깅 의심
- `pushfd` 직후 `xor ... 200000h` — CPUID 지원 여부 검사(레거시)
- 인터럽트 핸들러/컨텍스트 스위칭 코드(커널/드라이버 리버싱)에서 레지스터 전체 저장 루틴과 함께 등장

## 가장 먼저 할 것
1. PUSHF인지 POPF인지 먼저 구분한다(저장인지 복원인지).
2. 이 명령어 주변에 특정 비트를 조작하는 `or`/`and`/`xor`가 있는지 확인한다 — 있다면 특정 플래그 비트(TF, ID 등)를 노리는 코드다.
3. 이후 실행 흐름에서 예외(디버그 예외 등)가 발생하는지, CPUID가 뒤따르는지 확인해서 목적을 좁힌다.

## 단계별 절차
**1) 단순 백업/복원 패턴**
```asm
pushfd
...              ; 플래그를 바꿀 수 있는 코드
popfd             ; 원래 플래그로 복원
```
→ 그냥 "이 사이의 코드가 플래그를 망가뜨리면 안 된다"는 의도.

**2) TF 비트 조작 (안티 디버깅 의심)**
```asm
pushfd
or  dword ptr [esp], 100h
popfd
```
→ `100h` = TF 비트. 싱글 스텝 트리거 목적일 가능성이 높다.

**3) 스택에서 직접 플래그 값 확인**
`pushfd` 직후 스택 최상단(`[esp]`)을 디버거로 열어보면 32비트(또는 64비트) 값이 보이는데, 이걸 2진수로 펼쳐서 각 비트가 어떤 플래그인지 대조한다(비트 0=CF, 비트 2=PF, 비트 6=ZF, 비트 7=SF, 비트 8=TF, 비트 11=OF 등).

## 명령어/단축키
- IDA: PUSHF/POPF 근처의 비트 마스크 상수(`100h`, `200000h` 등)에 커서를 놓고 우클릭 → "Hex" 등으로 표시 전환, 필요하면 주석으로 어떤 플래그 비트인지 달아둔다
- x64dbg: 상단 플래그 표시줄에서 각 플래그(CF, ZF, SF, OF, TF 등)를 개별적으로 확인 가능, PUSHFQ/POPFQ 실행 전후 비교
- GDB/Pwndbg: `info registers eflags` 또는 `p $eflags`로 현재 플래그 상태 확인, `stepi`로 PUSHFQ/POPFQ 전후 비교

## 출력 해석
- `pushfq` 실행 직후 스택 최상단 값을 16진수로 보고, 이를 EFLAGS 비트 정의표와 대조하면 현재 어떤 플래그가 세팅되어 있는지 정확히 알 수 있다.
- `popfq` 실행 후 디버거의 플래그 표시가 스택에 있던 값과 정확히 일치해야 정상이다.
- TF 비트(0x100)가 세팅된 채로 `popfd`가 실행되면, 그 다음 명령어 실행 직후 디버그 예외가 발생해야 정상 — 디버거에서 이게 발생하지 않으면(혹은 예외 처리기가 있으면) 안티 디버깅 우회/탐지 지점이다.

## 흔한 실수
- PUSHF/POPF를 그냥 일반 PUSH/POP과 같은 취급으로 넘어가서, "플래그 전체가 통째로 저장/복원된다"는 특수성을 놓치는 것.
- POPF가 ZF/CF 같은 개별 플래그만 바꾸는 게 아니라 **거의 모든 플래그를 한 번에 덮어쓴다**는 것을 모르고, POPF 이후의 조건 분기를 그 이전 CMP 결과로 착각하는 것 — POPF 이후라면 스택에 있던 값이 새 플래그 상태다.
- 비트 마스크(`100h`, `200000h` 등)를 그냥 임의의 상수로 넘기고 안티 디버깅/CPUID 검사 패턴을 놓치는 것.
- x86의 `pushfd`/`popfd`(32비트)와 x64의 `pushfq`/`popfq`(64비트)를 같은 것으로 혼동하는 것 — 니모닉 접미사(`d` vs `q`)로 구분해야 한다.

## 막혔을 때 다음 체크
- PUSHF/POPF 주변에 낯선 비트 마스크가 있으면 → EFLAGS 비트 정의표(CF=bit0, PF=bit2, AF=bit4, ZF=bit6, SF=bit7, TF=bit8, IF=bit9, DF=bit10, OF=bit11)를 대조해서 어떤 플래그를 노리는지 확인한다.
- 안티 디버깅이 의심되면 → TF 관련 조작 다음에 예외 처리기(SEH, `try/except`, 시그널 핸들러) 설치 코드가 있는지 주변을 넓게 살핀다.
- 왜 이 자리에 PUSHF/POPF가 있는지 이해가 안 되면 → 이 사이의 코드가 실제로 플래그를 바꾸는 명령(산술/비교/시프트 등)을 포함하는지 확인해서 "보존이 필요한 이유"를 찾는다.

## 미니 예제

**예제 1 — 단순 플래그 백업/복원**
```asm
pushfq              ; 현재 RFLAGS를 스택에 저장
mov  eax, [rbx]
add  eax, 10         ; 이 연산이 플래그를 바꿈
popfq                ; 원래 플래그 상태로 복원 (add가 남긴 플래그는 사라짐)
jz   somewhere        ; 이 jz는 popfq로 복원된(즉 pushfq 시점의) 플래그를 본다
```

**예제 2 — TF 비트 세팅 (안티 디버깅 패턴)**
```asm
pushfd
or   dword ptr [esp], 100h  ; TF 세팅
popfd
nop                            ; 이 nop 실행 직후 디버그 예외 발생 예상
```

**예제 3 — CPUID 지원 검사 (레거시 x86)**
```asm
pushfd
pop  eax
mov  ecx, eax
xor  eax, 200000h    ; ID 비트 토글
push eax
popfd
pushfd
pop  eax
cmp  eax, ecx           ; 토글이 반영 안 됐으면(=이전과 같으면) CPUID 미지원
je   no_cpuid
```

## 관련 글
- [PUSH: 스택에 값 넣기](./rev-0044-push.md)
- [POP: 스택에서 값 꺼내기](./rev-0045-pop.md)
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)

## 출처/검증
- PUSHF/POPF, PUSHFD/POPFD, PUSHFQ/POPFQ 명령어 동작과 오퍼랜드 크기: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "PUSHF/PUSHFD/PUSHFQ—Push EFLAGS Register onto the Stack" / "POPF/POPFD/POPFQ—Pop Stack into EFLAGS Register" 섹션 기준 (2026-09-08 검증).
- EFLAGS 비트 정의(TF=비트8, ID=비트21 등): 같은 매뉴얼 Volume 1, "EFLAGS Register" 섹션 기준.
