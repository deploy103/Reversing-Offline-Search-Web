---
id: REV-0425
title: "JCXZ JECXZ JRCXZ: 카운터가 0일 때 분기"
slug: "rev-0425-jcxz-jecxz-jrcxz"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - jcxz
  - jecxz
  - jrcxz
  - JCXZ
  - JECXZ
  - JRCXZ
  - jcxz 명령어
  - 카운터 0 분기
  - zero counter jump
  - loop guard
  - zero-trip loop
  - ECX 0 검사
  - RCX 0 검사
  - loop 명령어
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - jcxz 뭐임
  - jecxz가 뭐죠
  - jrcxz가 뭐죠
  - 카운터가 0이면 분기
  - loop 0 가드
symptom_keywords:
  - loop 앞에 jecxz가 왜 있는지 모르겠음
  - jecxz가 플래그를 안 보는 이유를 모르겠음
  - jecxz 다음 목표가 멀어서 어셈블 오류가 남
  - ecx가 0일 때 루프를 건너뛰는 코드가 이해 안됨
  - jrcxz가 64비트인데 32비트만 검사하는 것 같음
---

## 한 줄 요약
`JCXZ`/`JECXZ`/`JRCXZ`는 다른 모든 `Jcc`와 달리 **EFLAGS를 전혀 읽지 않고**, 오직 `CX`/`ECX`/`RCX` 레지스터 값이 0인지만 직접 검사해 분기하는 특수한 조건 분기 명령이다.

## 언제 검색해야 하나
- `LOOP` 명령 바로 앞에 `jecxz`/`jcxz`가 붙어 있는 이유가 궁금할 때
- 이 명령이 `CMP`/`TEST` 없이 왜 바로 조건 분기를 하는지 이해가 안 될 때
- 어셈블러가 `jecxz`에 대해 "목표가 너무 멀다(operand out of range)" 같은 에러를 낼 때
- 오래된 16/32비트 코드나 손으로 최적화된 어셈블리에서 이 명령을 처음 봤을 때

## 핵심 개념

### 다른 Jcc와의 근본적 차이: 플래그를 안 본다
`JE`, `JS`, `JO` 등 대부분의 조건 분기는 EFLAGS의 특정 비트(들)를 검사한다. 하지만 `JCXZ`/`JECXZ`/`JRCXZ`는 **플래그를 전혀 읽지 않고**, 카운터 레지스터 자체의 값을 직접 검사한다:
- `JCXZ`: 16비트 `CX` 레지스터가 0이면 분기.
- `JECXZ`: 32비트 `ECX` 레지스터가 0이면 분기.
- `JRCXZ`: 64비트(롱 모드 전용) `RCX` 레지스터가 0이면 분기.

어떤 크기를 검사할지는 니모닉 자체로 명시적으로 고정된다(어드레스 크기에 따라 어셈블러가 자동으로 선택하기도 하지만, 니모닉을 명시적으로 쓰면 그 크기가 확정된다).

### 오퍼랜드: rel8 전용이라는 제약
`JCXZ`/`JECXZ`/`JRCXZ`는 **짧은 점프(rel8, -128~+127바이트)만 지원**하며 rel32 인코딩이 존재하지 않는다. 목표가 이 범위를 벗어나면 어셈블러가 에러를 내거나, 이 명령 하나만으로 먼 곳까지 점프할 수 없어 별도의 `JMP`와 조합해야 한다. 리버싱 중 "왜 하필 여기 짧은 조건 분기 하나와 그 바로 뒤에 무조건 JMP가 같이 있지?"라는 패턴을 보면 이 제약 때문일 수 있다.

### 왜 필요한가: LOOP의 함정
x86의 `LOOP` 명령은 "`ECX`를 1 감소시키고, 0이 아니면 분기"하는 동작을 한다. 즉 **먼저 몸체를 최소 한 번 실행한 뒤에야** 카운터를 검사한다. 그래서 `ECX`가 처음부터 0인 상태로 `LOOP` 기반 루프에 들어가면, 몸체가 1번 실행된 뒤 `ECX`가 0에서 1 감소해 매우 큰 값(0xFFFFFFFF)이 되어버려 루프가 사실상 끝나지 않는 심각한 버그가 생긴다.

이를 막기 위해 루프 진입 **전에** `JECXZ`로 카운터가 0인지 먼저 확인하고, 0이면 루프 몸체 자체를 건너뛰는 "0회 실행(zero-trip) 가드"를 흔히 사용한다:
```asm
jecxz   skip_loop        ; ECX가 0이면 루프에 아예 들어가지 않음
loop_start:
    ...
    loop    loop_start
skip_loop:
```

### 플래그/레지스터/스택 영향
- 플래그: 전혀 바꾸지 않는다(애초에 읽지도 않는다).
- 레지스터/메모리: `CX`/`ECX`/`RCX`를 읽기만 하고 수정하지 않는다.
- 스택 변화 없음. RIP는 분기 성립 시 목표로, 아니면 다음 명령으로.

### 현대 컴파일러에서는 왜 잘 안 보이는가
`LOOP`/`JECXZ`는 최신 x86 CPU에서 상대적으로 느린 명령으로 취급되어, GCC/Clang/MSVC 같은 현대 컴파일러는 일반 `for`/`while` 루프를 `CMP`+`JNE`류 조합으로 컴파일하고 `LOOP`/`JECXZ`는 사실상 쓰지 않는다. 따라서 이 명령들을 보면 다음 중 하나를 강하게 의심할 수 있다:
- 손으로 직접 짠(hand-written) 어셈블리.
- 매우 오래된 컴파일러가 만든 16/32비트 코드.
- REP 계열 문자열 명령을 직접 흉내내려는 코드.
- 안티디스어셈블/난독화 트릭 — 플래그를 전혀 건드리지 않는 조건 분기라는 특성을 이용해, 주변 코드가 의존하는 플래그 상태를 흐트러뜨리지 않으면서 은밀하게 분기하는 용도로 악용될 수 있다.

## 화면/코드에서 보이는 징후
```asm
jecxz   skip_loop
mov     ecx, [count]
loop_start:
    ...
    loop    loop_start
skip_loop:
```
```asm
xor     rcx, rcx
jrcxz   handle_zero_count
```
`cmp ecx, 0` 뒤에 다시 `jecxz`가 나오는 것처럼 보이면(플래그와 무관하니 중복이지만) 비최적화 코드이거나 방어적으로 작성된 코드일 수 있다.

## 가장 먼저 할 것
1. 이 분기가 `CX`/`ECX`/`RCX` 중 정확히 어떤 크기를 검사하는지 니모닉으로 확인한다.
2. 근처에 `LOOP`/`LOOPE`/`LOOPNE`가 있는지 확인한다 — 있다면 zero-trip 가드일 가능성이 크다.
3. 목표 레이블까지의 거리가 짧은지(rel8 제약) 확인해, 왜 이 자리에 있는지 이해한다.

## 단계별 절차
```asm
mov     ecx, [count]
jecxz   skip_loop        ; count == 0 이면 루프 진입 자체를 건너뜀
loop_start:
    ; ... 루프 몸체 ...
    loop    loop_start     ; ecx 감소 후 0이 아니면 loop_start로
skip_loop:
```
1. `ECX`에 반복 횟수를 로드.
2. `JECXZ`로 0인지 먼저 검사 — 0이면 아예 `skip_loop`로.
3. 0이 아니면 정상적으로 루프 몸체를 실행하고, 끝에서 `LOOP`가 `ECX`를 감소시키며 반복.

## 명령어/단축키
- IDA/Ghidra: 대개 `if (count == 0) goto skip;`으로 루프 앞에 붙은 0-트립 가드로 재구성되거나, `LOOP`와 함께 일반적인 `for` 루프 형태로 정리되기도 한다.
- GDB/x64dbg: 이 명령은 플래그가 아닌 레지스터 값을 직접 보므로, 레지스터 창에서 `ECX`/`RCX` 값을 확인하는 것이 분기 예측의 전부다.

## 출력 해석
- `ECX`(또는 검사 대상 레지스터)가 0이면 분기, 아니면 다음 명령으로 진행 — EFLAGS 창은 이 명령의 분기 여부를 판단하는 데 아무 도움이 안 된다는 점에 유의한다.

## 흔한 실수
- 다른 `Jcc`처럼 이 명령도 직전 `CMP`/`TEST`의 플래그에 의존한다고 착각하는 것 — `JCXZ`류는 플래그를 전혀 보지 않으므로, 직전에 `CMP ECX, 0`이 있어도 그건 순전히 군더더기(혹은 다른 목적)다.
- `JECXZ`가 32비트든 64비트든 항상 프로그램의 "전체" 카운터를 검사한다고 착각하는 것 — 64비트 롱 모드에서 `JECXZ`를 쓰면 `RCX`의 하위 32비트인 `ECX`만 검사하며, `RCX` 상위 32비트에 값이 남아 있어도 무시된다. 진짜 64비트 전체를 보려면 `JRCXZ`를 써야 한다.
- rel8 제약을 모르고 "왜 이 조건 분기 바로 뒤에 또 JMP가 있지?"라며 당황하는 것 — 목표가 멀면 `JECXZ`로 가까운 스텁까지만 뛰고, 그 스텁에서 다시 `JMP`로 먼 목표까지 가는 2단 점프 패턴이 흔하다.

## 막혔을 때 다음 체크
- 검사 대상이 `CX`/`ECX`/`RCX` 중 정확히 무엇인지 다시 확인했는가?
- 근처에 `LOOP` 계열 명령이 있는지, 이게 zero-trip 가드 패턴인지 확인했는가?
- 64비트 코드인데 `JECXZ`가 쓰였다면, 상위 32비트가 무시되고 있다는 점을 인지했는가?

## 미니 예제

**예제 1 — LOOP 앞의 zero-trip 가드**
```c
for (int i = 0; i < count; i++) { body(); }
```
```asm
mov     ecx, count
jecxz   skip_loop         ; count가 0이면 body()를 한 번도 안 돌게 함
loop_start:
    call    body
    loop    loop_start
skip_loop:
```

**예제 2 — 64비트 카운터 검사**
```asm
xor     rcx, rcx
mov     rcx, [item_count]
jrcxz   handle_zero_count   ; RCX 전체(64비트)가 0인지 검사, rel8이라 가까운 곳만 가능
```

**예제 3 — 먼 목표로 가기 위한 2단 점프**
```asm
jecxz   near_stub
jmp     main_path
near_stub:
    jmp     far_skip_label   ; jecxz의 rel8 한계를 우회
```

## 관련 글
- REV-0066 — JMP: 무조건 분기
- REV-0067 — JE와 JZ: ZF가 1일 때 분기
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- JCXZ/JECXZ/JRCXZ 명령어 동작, rel8 전용 인코딩, 검사 대상 레지스터 폭: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "JCXZ/JECXZ/JRCXZ—Jump if CX/ECX/RCX Is Zero" 섹션 기준 (2026-09-08 검증).
- LOOP 명령의 감소 후 검사 동작과 zero-trip 문제: Intel SDM Volume 2A, "LOOP/LOOPcc—Loop According to ECX Counter" 섹션 기준.
