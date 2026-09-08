---
id: REV-0418
title: "CLC STC CMC: 캐리 플래그 직접 조작"
slug: "rev-0418-clc-stc-cmc"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - clc
  - stc
  - cmc
  - CLC
  - STC
  - CMC
  - clc 명령어
  - stc 명령어
  - cmc 명령어
  - carry flag
  - 캐리 플래그
  - CF 플래그
  - CF 초기화
  - CF 설정
  - CF 토글
  - adc sbb
  - bignum arithmetic
  - 빅넘 연산
  - multi-precision arithmetic
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - clc 뭐임
  - stc가 뭐죠
  - cmc 명령
  - 캐리 플래그 지우기
  - 캐리 플래그 세우기
  - 캐리 플래그 반전
symptom_keywords:
  - clc stc cmc 차이를 모르겠음
  - adc 앞에 clc가 왜 있는지 모르겠음
  - 캐리 플래그를 직접 건드리는 코드가 나옴
  - 빅넘 덧셈 코드에서 clc가 보임
  - sbb eax eax 트릭이 뭔지 모르겠음
---

## 한 줄 요약
`CLC`/`STC`/`CMC`는 각각 캐리 플래그(CF)를 0으로 지우고(Clear), 1로 세우고(Set), 반전(Complement)시키는 명령어로, 오직 CF 하나만 바꾸고 다른 플래그는 전혀 건드리지 않는다.

## 언제 검색해야 하나
- `ADC`/`SBB` 같은 자리올림(carry) 기반 덧셈/뺄셈 앞에 `clc`나 `stc`가 붙어 있는 이유가 궁금할 때
- 여러 워드짜리(64비트를 넘는) 큰 정수 연산, 즉 bignum/RSA/암호 라이브러리 코드를 리버싱할 때
- `sbb eax, eax` 같은 캐리 트릭 코드가 이해되지 않을 때
- "CF 플래그를 임의로 바꿨는데 CMP 결과가 왜 안 바뀌지?" 같은 혼란이 있을 때

## 핵심 개념

### 세 명령어의 정확한 동작
- `CLC` (Clear Carry): `CF = 0`.
- `STC` (Set Carry): `CF = 1`.
- `CMC` (Complement Carry): `CF = NOT CF` (현재 값을 반전).

셋 다 오퍼랜드가 없고, 오직 **CF 하나만** 바꾼다. `OF`, `SF`, `ZF`, `AF`, `PF` 등 다른 플래그는 전혀 건드리지 않는다 — 이 점이 `CMP`/`TEST`처럼 여러 플래그를 한 번에 바꾸는 명령들과의 결정적 차이다.

### 왜 필요한가: ADC/SBB와의 관계
CPU 레지스터는 보통 32/64비트지만, 그보다 훨씬 큰 정수(예: 2048비트 RSA 키)를 다루려면 여러 개의 32/64비트 "덩어리(limb)"를 이어 붙여 계산해야 한다. 이때 `ADD`/`SUB` 대신 `ADC`(Add with Carry)/`SBB`(Subtract with Borrow)를 체인으로 연결해서, 이전 덩어리에서 넘어온(또는 빌려온) 자리올림을 다음 덩어리 계산에 반영한다.

체인의 **맨 첫 덩어리**를 계산할 때는 "이전 자리올림"이 존재하지 않으므로, CF를 깨끗한 0 상태에서 시작해야 한다 — 이때 `CLC`를 먼저 실행해 CF를 확실히 0으로 만든다.
```asm
clc                  ; 체인 시작 - 이전 캐리 없음을 보장
mov  eax, [a0]
adc  eax, [b0]        ; limb 0: eax = a0 + b0 + 0
mov  [r0], eax
mov  eax, [a1]
adc  eax, [b1]        ; limb 1: eax = a1 + b1 + CF(limb 0의 자리올림)
mov  [r1], eax
```

### CMC와 STC의 용도
`STC`는 명시적으로 캐리가 "있는 것"으로 시작해야 하는 경우(예: 뺄셈 체인에서 빌림이 미리 발생한 상태를 흉내내거나, 특정 비트 트릭)에 쓰인다. `CMC`는 CF를 반전시키는데, 조건부 분기(`JC`/`JNC`)의 의미를 그 자리에서 뒤집고 싶을 때, 혹은 일부 오래된 비트 연산 트릭에서 등장한다.

### 유명한 트릭: `sbb eax, eax`
```asm
stc
sbb eax, eax      ; eax = eax - eax - CF = 0 - 1 = 0xFFFFFFFF (모든 비트 1)
```
```asm
clc
sbb eax, eax      ; eax = eax - eax - CF = 0 - 0 = 0x00000000
```
CF 값에 따라 레지스터를 "전부 1(-1)" 또는 "전부 0"으로 만드는 분기 없는(branchless) 트릭으로, 마스크를 만들거나 조건부 값을 branchless하게 만들 때 쓰인다.

### 플래그/레지스터/스택 영향 요약
- 바꾸는 것: CF만.
- 안 바꾸는 것: OF, SF, ZF, AF, PF, 그리고 모든 범용 레지스터/메모리.
- 스택(RSP)/RIP: 스택 변화 없음. RIP는 명령어 길이(1바이트)만큼 증가.

## 화면/코드에서 보이는 징후
```asm
clc
adc  eax, ebx
```
```asm
stc
sbb  eax, eax
```
```asm
cmc
jc   was_clear_now_set
```
`ADC`/`SBB` 명령 근처에서만 의미가 있으므로, 이 셋을 보면 곧바로 근처의 `ADC`/`SBB`를 함께 확인해야 한다.

## 가장 먼저 할 것
1. `CLC`/`STC`/`CMC` 바로 뒤에 어떤 명령이 오는지 본다 — 대부분 `ADC`나 `SBB`가 뒤따른다.
2. `ADC`/`SBB`가 여러 번 연속으로 나오는지 확인한다 — bignum/암호 연산 루프일 가능성이 크다.
3. 이 함수가 RSA, AES, SHA 같은 암호 알고리즘의 일부인지 문자열/상수 참조를 통해 짐작해본다.

## 단계별 절차
1. `CLC`를 발견하면 "여기서부터 멀티 리밋 덧셈 체인이 시작된다"는 표시로 받아들인다.
2. 이후 반복되는 `ADC`/`SBB` 블록을 하나의 논리적 단위(더 큰 정수 하나의 덧셈/뺄셈)로 묶어서 읽는다.
3. `sbb reg, reg` 패턴이 보이면 branchless 마스크 생성 트릭임을 인지하고, 그 결과 레지스터가 이후 `AND`로 어떻게 쓰이는지 추적한다(조건부 선택 패턴).

## 명령어/단축키
- IDA/Ghidra: 원문 그대로 disassembly에 표시되며, 디컴파일러는 대개 이를 숨은 캐리 변수를 통한 큰 정수 덧셈으로 재구성하려 시도하지만 실패하면 raw 명령이 그대로 남는다.
- GDB/x64dbg: 레지스터 창에서 EFLAGS의 `CF` 비트만 확인하면 된다(다른 플래그는 변하지 않으므로 무시해도 된다).

## 출력 해석
- 디버거의 플래그 창에서 `CLC` 실행 직후 CF가 0, `STC` 직후 1이 되는 것만 확인하면 된다.
- `ADC`/`SBB` 결과값이 이전 CF에 의존한다는 점을 기억하고, 체인의 시작점에 `CLC`/`STC`가 있는지 항상 먼저 확인한다.

## 흔한 실수
- `CLC`/`STC`/`CMC`가 `ZF`나 `SF` 같은 다른 플래그도 바꾼다고 착각하는 것 — 오직 CF만 바뀐다.
- `CMP` 기반 분기와 무관하다는 것을 모르고, `CLC` 다음에 `JE`/`JNE` 같은 ZF 기반 분기가 있으면 그게 CLC의 영향이라고 오해하는 것 — CLC는 ZF를 건드리지 않으므로 그 분기는 이전 다른 명령의 결과다.
- bignum 체인의 시작에 `CLC`가 빠져 있다고 착각해 버그로 오판하는 것 — 컴파일러/작성자가 이미 CF가 0이라고 알고 있는 문맥(예: 방금 `XOR eax, eax`를 실행해 자연스럽게 CF=0이 된 경우)에서는 `CLC`를 생략하기도 한다.

## 막혔을 때 다음 체크
- `ADC`/`SBB`가 반복되는데 시작점에 `CLC`/`STC`가 안 보인다면, 몇 줄 더 위에서 CF를 0/1로 만드는 다른 연산(예: `SUB eax, eax`)이 있는지 찾아본다.
- `sbb reg, reg` 결과가 이후 어떻게 쓰이는지 못 찾겠다면, `AND`로 마스킹하는 다음 줄을 찾아본다.

## 미니 예제

**예제 1 — 128비트(두 개의 64비트 limb) 덧셈**
```c
// 개념적으로: unsigned __int128 r = a + b;
```
```asm
clc
mov  rax, [a_lo]
add  rax, [b_lo]     ; 참고: 첫 limb는 ADD로도 가능(캐리 없음 보장됨)
mov  [r_lo], rax
mov  rax, [a_hi]
adc  rax, [b_hi]      ; 두 번째 limb는 반드시 ADC로 이전 캐리를 반영
mov  [r_hi], rax
```

**예제 2 — 조건부 마스크 생성 (branchless)**
```asm
cmp  eax, ebx
setb al          ; al = (eax < ebx) ? 1 : 0  (참고용, CF 기반 SETcc)
```
```asm
; CF를 이용한 전형적 -1/0 마스크
stc
sbb  edx, edx     ; edx = 0xFFFFFFFF
```

**예제 3 — CMC로 캐리 반전**
```asm
clc
jc   never_taken   ; CF=0이라 분기 안 함
cmc                 ; CF를 1로 반전
jc   taken_now      ; 이제 분기함
```

## 관련 글
- REV-0047 — ADD: 덧셈과 플래그
- REV-0048 — SUB: 뺄셈과 플래그
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기
- REV-0046 — PUSHF와 POPF: 플래그 저장과 복원
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기

## 출처/검증
- CLC/STC/CMC 명령어 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CLC—Clear Carry Flag" / "STC—Set Carry Flag" / "CMC—Complement Carry Flag" 섹션 기준 (2026-09-08 검증).
- ADC/SBB를 이용한 다중정밀도 연산 패턴: Intel SDM Volume 1, 정수 산술 챕터 및 일반 컴파일러/암호 라이브러리 구현 관례 기준.
