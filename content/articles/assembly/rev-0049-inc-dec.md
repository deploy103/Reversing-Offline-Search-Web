---
id: REV-0049
title: "INC와 DEC: 1 증가 감소와 CF 주의"
slug: "rev-0049-inc-dec"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - inc
  - INC
  - Inc
  - dec
  - DEC
  - Dec
  - inc 명령어
  - dec 명령어
  - inc instruction
  - dec instruction
  - "inc eax"
  - "dec ecx"
  - "inc rax"
  - "dec rcx"
  - 1 증가
  - 1 감소
  - 증가 감소
  - 루프 카운터
  - loop counter
  - CF 안 바뀜
  - CF 보존
  - CF not affected
  - INC DEC 차이 ADD SUB
  - 부분 플래그 업데이트
  - partial flag update
  - for 루프 어셈블리
  - 카운터 증가
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - inc가 뭐임
  - dec가 뭐임
  - inc dec 명령이 뭐죠
  - 1씩 증가시키는 명령어
  - 1씩 감소시키는 명령어
  - inc가 왜 CF 안 바꿈
  - dec는 캐리플래그 영향 없나요
  - inc랑 add 1 차이
  - 루프에서 dec ecx 뜻
symptom_keywords:
  - inc했는데 CF가 안 바뀜
  - dec 다음에 jnz 뭔 뜻
  - inc eax cmp eax 패턴이 뭔지 모르겠음
  - dec ecx jnz loop 뭔 뜻
  - inc dec가 add sub랑 뭐가 다른지 모르겠음
  - 캐리 플래그가 루프 돌리는데 안 바뀜
last_verified: "2026-09-08"
---

## 한 줄 요약
`INC dest`는 `dest = dest + 1`, `DEC dest`는 `dest = dest - 1`을 계산하는 단항(오퍼랜드 1개) 명령어이며, **OF·SF·ZF·AF·PF는 갱신하지만 CF(Carry Flag)는 절대 건드리지 않는다** — 이게 이 명령어의 가장 중요하고 가장 자주 헷갈리는 특징이다.

## 언제 검색해야 하나
- `inc eax`, `dec ecx` 같은 코드가 루프 안에서 반복적으로 나오는데 정확히 무슨 역할인지 확인하고 싶을 때
- `dec ecx` 다음에 `jnz`(또는 `loop`)로 반복문이 만들어지는 전형적인 for/while 루프 패턴을 해석하고 싶을 때
- 왜 `add eax, 1`이 아니라 `inc eax`가 쓰였는지, 혹은 반대로 최신 코드에서 `add reg, 1`만 보이고 `inc`가 안 보이는 이유가 궁금할 때
- "INC/DEC가 CF를 안 바꾼다"는 게 왜 중요한지, 실제로 어떤 상황에서 문제가 되는지 알고 싶을 때

## 핵심 개념

### INC/DEC가 실제로 하는 일
`INC`와 `DEC`는 오퍼랜드를 **하나만** 받는다. `ADD`/`SUB`처럼 두 값을 더하거나 빼는 게 아니라, 그 오퍼랜드 자체를 1만큼 증가/감소시킨다.

```asm
inc eax           ; EAX = EAX + 1
dec ecx           ; ECX = ECX - 1
inc dword [rbp-4] ; 메모리 값 += 1
```

dest는 레지스터 또는 메모리이고, `ADD eax, 1` / `SUB ecx, 1`과 계산 결과 자체는 동일하다. 다른 건 딱 하나, **플래그 처리 방식**이다.

### 결정적 차이 — INC/DEC는 CF를 건드리지 않는다
`ADD`([REV-0047](./rev-0047-add.md))와 `SUB`([REV-0048](./rev-0048-sub.md))는 CF를 포함한 6개 플래그를 전부 갱신한다. 하지만 `INC`/`DEC`는:
- **갱신함**: OF, SF, ZF, AF, PF
- **절대 갱신 안 함**: **CF (Carry Flag)** — 실행 전 CF 값이 실행 후에도 그대로 유지된다.

이건 Intel이 의도적으로 설계한 예외다. 이유를 실제 코드로 보면 이해가 빠르다.

**왜 이렇게 설계했는가 — 다중 정밀도 연산과 루프 카운터가 공존하는 상황**
```asm
; 128비트(RDX:RAX) 값에 128비트(RBX:RCX) 값을 더하면서, 동시에 별도의 인덱스 레지스터 RSI로 루프를 도는 코드
loop_top:
    add  rax, rcx     ; 하위 64비트 덧셈 → CF 세팅됨 (자리올림 발생했다고 가정)
    adc  rdx, rbx     ; 상위 64비트 덧셈 + 방금 CF 반영 → 정확한 128비트 덧셈 완성
    inc  rsi           ; 루프 인덱스 증가 — 만약 INC가 CF를 건드린다면, 방금 ADC가 쓴 CF가 여기서 망가짐!
    cmp  rsi, count
    jl   loop_top
```
위 코드에서 `ADC`(Add with Carry)는 바로 앞의 `ADD`가 세팅한 CF를 반드시 참조해야 한다. 그런데 그 사이/뒤에 있는 "루프 카운터 증가용" `INC`가 만약 CF를 건드린다면, 다음 반복에서 `ADC`가 잘못된 CF를 읽어서 다중 정밀도 연산 전체가 틀어진다. **그래서 x86은 INC/DEC를 CF에 관해서는 "투명한" 명령으로 설계했다** — 루프 카운터나 배열 인덱스를 증감시키는 용도로 마음 놓고 쓸 수 있도록, 이미 계산 중인 CF 체인(ADC/SBB로 이어지는 다중 정밀도 연산)을 방해하지 않게 한 것이다.

### 컴파일러가 INC/DEC 대신 ADD/SUB를 쓰기도 한다
현대 x64 컴파일러(특히 최신 GCC/Clang/MSVC)는 단순 `i++`, `i--`를 `inc`/`dec`가 아니라 `add reg, 1` / `sub reg, 1`로 컴파일하는 경우가 흔하다. 이는 과거 일부 마이크로아키텍처(대표적으로 Pentium 4)에서 `INC`/`DEC`가 **부분 플래그 갱신(partial flag update)** 때문에 플래그 레지스터에 대한 거짓 의존성(false dependency)을 만들어 파이프라인 스톨을 유발했던 이력 때문이다. `ADD`/`SUB`는 모든 플래그를 갱신하므로 이런 거짓 의존성이 없다. 그래서 리버싱할 때는 **`inc eax`와 `add eax, 1`을 완전히 동일한 의미로 인식**해야 한다 — 어느 쪽이 쓰였는지는 컴파일러/최적화 옵션의 선택일 뿐, 로직상 차이는 없다(단, CF 보존 여부는 다르므로 플래그 체인이 있는 코드에서는 컴파일러가 반드시 의미에 맞게 골라 쓴다).

### 컴파일러 패턴 — 루프 카운터
가장 흔하게 보는 패턴은 for/while 루프의 카운터 증감이다.

**패턴 A — 감소 카운터 (`dec` + `jnz`)**
```asm
mov ecx, 10
loop_top:
    ; ... 루프 본문 ...
    dec ecx
    jnz loop_top      ; ECX가 0이 아니면 반복 (ZF 기반, CF와 무관)
```
C로는:
```c
for (int i = 10; i > 0; i--) { /* ... */ }
```

**패턴 B — 증가 카운터 (`inc` + `cmp`/`jl`)**
```asm
xor eax, eax
loop_top:
    ; ... 루프 본문 ...
    inc eax
    cmp eax, 10
    jl  loop_top       ; EAX < 10이면 반복 (signed 비교, SF/OF 기반)
```
C로는:
```c
for (int i = 0; i < 10; i++) { /* ... */ }
```

두 패턴 모두 `jnz`/`jl` 분기가 **ZF나 SF/OF**를 보지 CF를 보지 않기 때문에, `INC`/`DEC`가 CF를 안 건드려도 루프 제어에는 전혀 문제가 없다. 오히려 앞서 설명했듯 CF를 건드리지 않는 게 다른 연산과 섞였을 때 안전하다.

### IDA/Ghidra 디컴파일 렌더링
- `inc eax` → `v1++;` 또는 `++v1;`
- `dec ecx` → `v1--;` 또는 `--v1;`
- `dec ecx; jnz loop_top` → `for`/`while` 루프의 카운터 감소 부분으로 자동 정리되어 `while (--v1)` 형태로 보이는 경우가 많다.
- `inc dword [rbp-4]` → 메모리에 직접 있는 지역 변수의 `count++;`

### 리버싱에서의 의미
- 루프를 찾을 때 `inc`/`dec` (또는 `add reg,1`/`sub reg,1`) + 뒤따르는 `jnz`/`jl`/`jle`/`jg` 조합을 보면 바로 "이건 반복문의 카운터 갱신부"라고 인식하는 게 가장 빠른 루프 식별 방법이다.
- `INC`/`DEC`가 CF를 안 건드린다는 점을 알면, 그 앞뒤에 있는 `jc`/`jnc`(CF 기반 분기)가 실제로는 `INC`/`DEC`보다 더 앞선 명령(예: 이전의 `ADD`/`SUB`/`ADC`/`SBB`)의 결과를 보고 있다는 걸 즉시 알아챌 수 있다. 이걸 모르면 "방금 `inc`를 실행했는데 왜 CF가 그대로지?"라며 혼란스러워하게 된다.

## 화면/코드에서 보이는 징후
- `inc eax`, `inc [rbp-4]`, `dec ecx`, `dec rsi` — 단순 증감
- `dec reg` 바로 뒤에 `jnz`/`jne` — 감소 카운터 루프
- `inc reg` 바로 뒤에 `cmp reg, N` 그리고 `jl`/`jle`/`jb`/`jbe` — 증가 카운터 루프
- `inc`/`dec` 앞뒤에 `adc`/`sbb`가 있는 코드 — 다중 정밀도 연산 중간에 안전하게 끼워 넣은 인덱스 증감
- 최신 x64 바이너리에서 `inc`/`dec` 대신 `add reg, 1` / `sub reg, 1`이 보이는 경우 — 의미는 동일

## 가장 먼저 할 것
1. 오퍼랜드가 레지스터인지 메모리인지 확인
2. 이 INC/DEC 바로 다음에 오는 분기가 어떤 플래그를 보는지 확인 (ZF 기반 `jnz`/`je`인지, SF/OF 기반 signed 비교인지 — CF 기반이면 이 INC/DEC보다 더 앞의 명령을 봐야 함을 기억)
3. 루프 카운터/배열 인덱스 용도인지, 아니면 일반적인 값 계산인지 구분
4. `add reg, 1` / `sub reg, 1`이 똑같은 의미로 쓰였을 수 있다는 점을 염두에 두고 패턴 인식

## 단계별 절차

**1) 감소 루프 카운터 확인**
```asm
mov ecx, 5
loop_top:
    ; 본문
    dec ecx
    jnz loop_top
```
→ `for (i = 5; i != 0; i--)` 형태로 해석. `dec`가 ZF만 세팅하고 CF는 안 건드리므로, `jnz`가 정확히 "ECX가 0이 됐는가"만 본다.

**2) 증가 루프 카운터 확인**
```asm
xor eax, eax
loop_top:
    ; 본문
    inc eax
    cmp eax, count
    jl  loop_top
```
→ `for (i = 0; i < count; i++)` 형태.

**3) CF 보존이 실제로 쓰이는 코드 확인**
```asm
add  rax, rcx      ; CF 세팅 (자리올림 발생 가능)
inc  rbx            ; 별개의 카운터 증가 — CF에 영향 없음!
adc  rdx, rbp       ; 여전히 위 add의 CF를 정확히 반영
```
→ `inc rbx`가 중간에 끼어 있어도 `adc`가 올바른 CF를 참조한다는 걸 확인. 만약 `inc rbx` 자리에 `add rbx, 0`처럼 CF를 건드리는 명령이 있었다면 `adc`가 틀린 값을 낸다.

**4) `add reg, 1`을 INC와 동일하게 인식**
```asm
add eax, 1
cmp eax, 10
jl  loop_top
```
→ 이건 `inc eax`와 로직상 완전히 동일하다(단, `add eax, 1`은 CF도 갱신한다는 차이가 있지만 이 루프는 CF를 안 쓰므로 무관).

## 명령어/단축키
- x64dbg: F7/F8로 `inc`/`dec` 실행 전후 플래그 패널을 보면 C(CF) 비트만 안 바뀌고 Z/S/O 등은 바뀌는 걸 직접 확인 가능.
- GDB/Pwndbg: `info registers eflags`로 실행 전후 CF 값을 비교.
- IDA: 루프를 찾을 때 그래프 뷰(스페이스바로 전환)에서 뒤로 돌아가는 화살표(back edge)를 찾으면 그 근처에 `inc`/`dec` 카운터가 있을 확률이 높다.

## 출력 해석
- `inc`/`dec` 실행 직후 CF가 실행 전과 똑같다면 정상 — INC/DEC의 명세대로 동작한 것.
- `ZF=1`이 `dec` 직후 나오면 그 레지스터가 정확히 0이 됐다는 뜻이며, 바로 뒤 `jz`/`jnz`가 이를 이용해 루프 종료를 판단한다.
- IDA 디컴파일에서 `while (i--)`나 `for (...; i < n; i++)` 형태로 자동 정리된 코드는 원본이 `dec`+`jnz` 또는 `inc`+`cmp`+`jl` 조합이었을 가능성이 높다.

## 흔한 실수
- **INC/DEC가 CF도 바꾼다고 착각하는 것** — 이게 이 명령어에서 가장 흔하고 가장 치명적인 오해다. `inc`/`dec` 앞에 CF를 세팅하는 연산(`ADD`, `SUB`, `CMP` 등)이 있었다면, 그 CF는 `inc`/`dec`를 거쳐도 그대로 살아있다. 나중에 나오는 `jc`/`jnc`가 `inc`/`dec`가 아니라 더 앞의 연산 결과를 본다는 걸 놓치면 분기 조건을 완전히 잘못 해석하게 된다.
- `inc`/`dec`와 `add ..., 1`/`sub ..., 1`을 다른 명령이라고 생각해서 패턴 매칭을 놓치는 것 — 계산 로직은 동일하다.
- 루프 카운터가 항상 `ecx`일 거라 가정하는 것 — x86의 문자열 반복 프리픽스(`REP`)는 관례적으로 ECX/RCX를 카운터로 쓰지만, 일반 `INC`/`DEC` 기반 루프는 컴파일러가 아무 레지스터나 자유롭게 고른다.
- `dec` 다음의 `jnz`를 "CF가 0이 아니면 분기"로 착각하는 것 — 실제로는 ZF(0이 됐는지)를 보는 것이지 CF와 무관하다.

## 막혔을 때 다음 체크
- `inc`/`dec` 뒤 분기가 어떤 플래그를 보는지 헷갈린다면 → [REV-0088 — 플래그 레지스터와 Jcc 연결](./rev-0088-flags-overview.md) 참고.
- CF가 예상과 다르게 유지되는 것 같다면 → 바로 위의 `inc`/`dec`가 아니라 그보다 더 앞선 산술 명령(`ADD`/`SUB`/`ADC`/`SBB`/`CMP`)을 찾아봐야 한다.
- 루프 경계 조건이 signed인지 unsigned인지 헷갈린다면 → 카운터 변수의 실제 타입을 확인하고, 뒤따르는 비교 분기가 `JL`/`JG` 계열(signed, [REV-0069 예정])인지 `JB`/`JA` 계열(unsigned, [REV-0070 예정])인지 확인.

## 미니 예제

**예제 1 — 감소 카운터 루프**
```c
for (int i = 5; i > 0; i--) {
    total += arr[i - 1];
}
```
```asm
mov ecx, 5
loop_top:
    ; ... total += arr[ecx-1] 계산 ...
    dec ecx
    jnz loop_top
```

**예제 2 — 증가 카운터 루프**
```c
for (int i = 0; i < n; i++) {
    sum += arr[i];
}
```
```asm
xor eax, eax        ; i = 0
loop_top:
    ; ... sum += arr[eax] 계산 ...
    inc eax
    cmp eax, [n]
    jl  loop_top
```

**예제 3 — CF 보존이 실제로 중요한 경우 (다중 정밀도 덧셈 + 별도 카운터)**
```c
// 개념 예시: 128비트 누산기에 여러 번 더하면서 반복 횟수도 센다
```
```asm
loop_top:
    add  rax, [rsi]     ; 하위 64비트 누적, CF 세팅될 수 있음
    adc  rdx, [rsi+8]   ; 상위 64비트 누적 + 방금 CF 반영
    inc  rbx             ; 반복 횟수 카운터 증가 — CF에 전혀 영향 없음
    add  rsi, 16
    dec  rcx
    jnz  loop_top
```
→ `inc rbx`와 `dec rcx`가 중간에 있어도 `adc rdx, [rsi+8]`은 그보다 앞선 `add rax, [rsi]`의 CF를 정확히 반영한다.

**예제 4 — 최신 컴파일러의 `add`/`sub` 대체 표현**
```asm
; 아래는 inc eax와 완전히 동일한 의미
add eax, 1
cmp eax, 100
jl  loop_top
```

## 관련 글
- [REV-0047 — ADD: 덧셈과 플래그](./rev-0047-add.md)
- [REV-0048 — SUB: 뺄셈과 플래그](./rev-0048-sub.md)
- [REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기](./rev-0088-flags-overview.md)
- REV-0055 — AND: 마스크와 비트 제거 (예정)
- REV-0066 — JMP: 무조건 분기 (예정)
- REV-0069 — JG JGE JL JLE: Signed 비교 분기 (예정)
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기 (예정)

## 출처/검증
- INC/DEC 명령어 동작과 플래그 영향(CF 미변경 포함): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "INC—Increment by 1" / "DEC—Decrement by 1" 섹션 기준 (2026-09-08 검증).
- 부분 플래그 업데이트로 인한 파이프라인 영향과 컴파일러의 ADD/SUB 대체 경향: Agner Fog, "Optimizing subroutines in assembly language" (agner.org) 및 Intel 최적화 매뉴얼 기준.
