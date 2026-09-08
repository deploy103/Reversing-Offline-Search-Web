---
id: REV-0413
title: "원거리(Far) CALL과 JMP 기초"
slug: "rev-0413-far-call-jmp"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - far call
  - far jmp
  - "call far"
  - "jmp far"
  - far ptr
  - FAR CALL
  - FAR JMP
  - 원거리 호출
  - 원거리 점프
  - 세그먼트 전환
  - segment selector
  - CS 레지스터 변경
  - heaven's gate
  - heavens gate 기법
  - wow64 far jmp
  - call gate
  - "jmp 0x33"
  - "push 0x33"
aliases:
  - far call 뭐임
  - far jmp 뭐임
  - 원거리 콜 뭐죠
  - far call과 call 차이
  - far jmp와 jmp 차이
  - 헤븐즈 게이트
symptom_keywords:
  - jmp far ptr이 뭔지 모르겠음
  - push 0x33 다음에 retf가 나올 때
  - wow64 32비트 프로세스인데 64비트 코드가 실행될 때
  - cs 레지스터가 왜 바뀌는지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Far(원거리) `CALL`/`JMP`는 일반(near) `CALL`/`JMP`와 달리 명령어 포인터(EIP/RIP)뿐 아니라 **코드 세그먼트 레지스터(CS)까지 함께 바꿔서**, 실행 흐름을 완전히 다른 세그먼트(때로는 완전히 다른 실행 모드)로 옮기는 명령어다.

## 언제 검색해야 하나
- `jmp far ptr`, `call far ptr`, 또는 `jmp 0x33:주소` 같은 콜론(`:`)이 포함된 이상한 형태의 점프/호출을 만났을 때
- WOW64(64비트 Windows 위의 32비트 프로세스)에서 갑자기 64비트 코드처럼 보이는 바이트가 실행되는 "Heaven's Gate" 패턴을 만났을 때
- 부트로더, BIOS, 커널/드라이버 코드에서 세그먼트를 전환하는 코드를 분석할 때
- `CS` 레지스터 값이 왜 바뀌는지, 왜 일반 `CALL`/`JMP`로는 안 되는지 궁금할 때

## 핵심 개념

### Near vs Far — 근본적 차이
지금까지 다룬 [`CALL`](rev-0071-call.md), [`JMP`](rev-0066-jmp.md)은 전부 **near** 형태다 — 목적지가 **같은 코드 세그먼트 안**에 있다고 가정하고, `CS`는 그대로 둔 채 `EIP`/`RIP`(또는 `IP`)만 바꾼다. 반면 **far** `CALL`/`JMP`는 목적지가 세그먼트 선택자(selector) + 오프셋으로 지정되며, 실행하면 **`CS` 레지스터 자체가 새 값으로 교체**된다.

### Intel 문법
```
JMP  FAR PTR label
JMP  0x33:0x0000000140001000        ; 직접 지정: 셀렉터 0x33, 오프셋 0x140001000
JMP  FWORD PTR [mem]                 ; 메모리에서 셀렉터:오프셋을 읽어 간접 far jmp

CALL FAR PTR proc
CALL 0x33:target
CALL FWORD PTR [mem]
```
`FWORD PTR`은 6바이트(32비트 오프셋 + 16비트 셀렉터, 32비트 모드 기준) 또는 64비트 모드에서는 10바이트(64비트 오프셋 + 16비트 셀렉터) 크기의 메모리 오퍼랜드를 가리킨다는 뜻이다.

### 스택/레지스터 효과
- **Far JMP**: 스택을 전혀 건드리지 않는다. 그냥 `CS:IP`(또는 `CS:EIP`/`CS:RIP`)를 새 값으로 바꿀 뿐이다.
- **Far CALL**: **CS와 반환 오프셋(IP/EIP/RIP) 둘 다** 스택에 PUSH한다 — near call이 반환 오프셋 하나만 PUSH하는 것과 대비된다. 그래서 far call은 스택을 더 많이 소비하고, 짝을 이루는 반환 명령어도 [`RETF`](rev-0414-retf.md)(REV-0414)를 써야 한다(일반 `RET`는 CS를 복원하지 않는다).

### 플래그 변화
`CALL`/`JMP`(near, far 모두)는 플래그를 바꾸지 않는다. 단, far call/jmp가 **디스크립터 테이블(GDT/LDT)을 거쳐 권한 레벨(CPL)을 바꾸는 경우**(콜 게이트를 통한 링 전환 등)에는 간접적으로 실행 컨텍스트가 크게 달라질 수 있지만, 이는 플래그 레지스터 자체를 직접 바꾸는 것과는 다른 이야기다.

### signed/unsigned 관점
해당 없음 — 주소/셀렉터를 다루는 제어 흐름 명령어다.

### CS가 바뀐다는 것의 의미
보호 모드(protected mode)에서 CS에 새 셀렉터를 로드하면, CPU는 GDT(Global Descriptor Table) 또는 LDT(Local Descriptor Table)에서 그 셀렉터에 해당하는 세그먼트 디스크립터를 찾아 **코드 실행 모드(16/32/64비트), 권한 레벨(CPL), 베이스 주소, 접근 권한**을 전부 새로 적용한다. 이것이 near jmp/call과 완전히 다른 점이다 — near는 "같은 세그먼트 안에서 위치만 이동", far는 "실행 환경 자체를 바꿀 수 있음"이다.

### 리버싱에서 가장 중요한 사례 — Heaven's Gate 기법
Windows x64에서 32비트(WOW64) 프로세스는 평소 `CS = 0x23`(32비트 코드 세그먼트)으로 실행된다. 그런데 x64 시스템에는 `CS = 0x33`인 **64비트 코드 세그먼트**도 항상 함께 존재한다. 일부 악성코드와 일부 WOW64 내부 전환 코드는 다음과 같은 패턴으로 **far jmp/call을 이용해 32비트 실행 중에 순간적으로 64비트 코드 세그먼트로 전환**한다:
```asm
push 33h                 ; 목적지 셀렉터 (0x33 = 64비트 코드 세그먼트)
call $+5                  ; 다음 명령 주소를 스택에 push (트릭)
add  dword ptr [esp], 5    ; 스택에 있는 복귀 주소를 보정
retf                        ; far return으로 CS:EIP를 동시 교체 -> 64비트 모드 진입
; 여기서부터는 64비트 명령어로 해석됨 (32비트 디스어셈블러는 이걸 알아채지 못함)
```
이 기법을 **"Heaven's Gate"**라 부르며, 32비트 전용 디버거/디스어셈블러가 세그먼트 전환을 인식하지 못해 이후 바이트를 잘못된 명령어 집합(32비트)으로 잘못 해석하게 만드는 안티 분석/안티 에뮬레이션 트릭으로 악용된다. 이 패턴을 만나면 `push 0x33` 뒤에 `retf` 또는 직접적인 `jmp far 0x33:target`가 있는지를 먼저 확인하고, 그 지점부터는 64비트 디스어셈블리 모드로 다시 분석해야 한다.

### 그 외의 정상적인 far call/jmp 사용처
- **부트로더/BIOS**: 컴퓨터가 켜지면 16비트 real mode로 시작하는데, 32비트 protected mode로 전환할 때 `jmp far 0x08:protected_mode_entry` 같은 코드로 CS를 32비트 코드 세그먼트로 갈아끼운다.
- **OS 커널/드라이버**: 옛 x86 설계의 콜 게이트(call gate)를 통한 링 전환(사용자 모드 → 커널 모드 시스템 콜)에 far call이 쓰였다(현대 x86-64에서는 [`SYSCALL`](rev-0077-syscall.md)/`SYSENTER`가 이를 대체).
- **DOS TSR/인터럽트 벡터 코드**: 인터럽트 벡터 테이블에 저장된 seg:offset 주소로 실행이 넘어가는 것도 개념적으로 far 전환에 해당한다.

### 컴파일러 패턴
일반적인 C 컴파일러가 사용자 모드 애플리케이션 코드에서 far call/jmp를 생성하는 일은 거의 없다 — 플랫(flat) 메모리 모델에서는 near call/jmp만으로 충분하기 때문이다. far call/jmp를 보면 부트로더/커널/드라이버 코드이거나, 손으로 작성된 어셈블리(특히 Heaven's Gate류 안티 분석 코드)라고 생각해야 한다.

### IDA/Ghidra에서 보이는 형태
`jmp far ptr sub_XXXX`, `call far ptr sub_XXXX`로 표시된다. Heaven's Gate 패턴은 IDA가 자동으로 인식하지 못하는 경우가 많아, 전환 이후의 바이트를 계속 32비트로 잘못 디스어셈블할 수 있다 — 이럴 때는 대상 주소에서 수동으로 "Edit → Segments" 또는 재분석 옵션을 이용해 64비트 코드로 다시 해석시켜야 정확한 디스어셈블리를 얻을 수 있다.

## 화면/코드에서 보이는 징후
- `jmp far ptr ...`, `call far ptr ...` — 명시적 far 전환
- `push 33h` 뒤에 `retf` 또는 직접적인 far jmp — Heaven's Gate 패턴 의심
- 부트로더 코드에서 `jmp far 08h:주소` — real mode에서 protected mode 진입
- `jmp fword ptr [mem]` — 메모리에 저장된 seg:offset을 통한 간접 far jmp

## 가장 먼저 할 것
1. 이게 near인지 far인지부터 구분한다 — 콜론(`:`)이 있는 오퍼랜드, 또는 `far ptr` 키워드가 있으면 far다.
2. 목적지 셀렉터 값(0x08, 0x23, 0x33 등)을 확인한다 — 특히 0x33이면 Heaven's Gate(64비트 세그먼트 전환) 가능성을 의심한다.
3. far call이면 짝이 되는 반환 명령어가 `RETF`(REV-0414)인지 확인한다.

## 단계별 절차

**1) 명시적 far jmp 인식**
```asm
jmp far ptr 0028h:00401000h   ; CS=0x28, EIP=0x00401000으로 즉시 전환
```

**2) Heaven's Gate 패턴 인식**
```asm
push  33h
call  $+5
add   dword ptr [esp], 5
retf                           ; CS:EIP를 동시에 교체 -> 64비트 모드 진입
; 이 지점부터 64비트 명령어로 재해석 필요
```
이 패턴을 발견하면 `retf` 이후 주소를 IDA/Ghidra에서 64비트 코드로 강제 재분석해야 정확한 디스어셈블리를 얻을 수 있다.

**3) 부트로더의 real mode → protected mode 전환**
```asm
; 16비트 real mode
lgdt  [gdt_descriptor]
mov   eax, cr0
or    eax, 1
mov   cr0, eax
jmp   far 08h:protected_mode_start   ; CS를 32비트 코드 세그먼트로 전환
```

## 명령어/단축키
- IDA: far call/jmp 주변에서 "Force 64-bit"/"Force 32-bit" 재분석 옵션(우클릭 → 코드로 변환, 또는 세그먼트 속성 편집)으로 실행 모드 전환 지점을 수동 보정
- x64dbg: 64비트 전환 이후 코드를 보려면 64비트 디버거(x64dbg)로 다시 붙이거나, "Heaven's Gate 탐지" 관련 플러그인 활용
- GDB: 세그먼트 레지스터(`$cs`) 값을 `info registers`로 확인해 실제 실행 모드 추정

## 출력 해석
- far jmp/call 직후 `CS` 레지스터 값이 목적지 셀렉터와 일치하는지 확인한다.
- Heaven's Gate가 의심되면 `retf`/`jmp far` 실행 직후부터의 바이트를 64비트 명령어 집합으로 다시 해석했을 때 자연스러운 코드(정상적인 함수 프롤로그 등)가 나오는지 확인한다.

## 흔한 실수
- far call/jmp를 그냥 near call/jmp에 "셀렉터가 하나 더 붙은 것뿐"이라고 가볍게 넘기는 것 — 실제로는 실행 모드 자체(16/32/64비트)와 권한 레벨이 바뀔 수 있는 훨씬 근본적인 전환이다.
- far call의 반환 주소 프레임을 near call과 같은 크기(오프셋만)로 착각해서 스택을 잘못 해석하는 것 — far call은 CS까지 추가로 push하므로 스택에 더 많은 바이트가 쌓인다.
- Heaven's Gate 패턴을 못 알아보고 32비트 디스어셈블러 결과를 그대로 믿는 것 — 전환 이후 바이트를 32비트로 계속 해석하면 완전히 엉뚱한(의미 없는) 명령어들이 나열된 것처럼 보인다.
- far jmp가 스택에 무언가를 남긴다고 착각하는 것 — far jmp는 far call과 달리 스택을 전혀 쓰지 않는다.

## 막혔을 때 다음 체크
- 디스어셈블리가 특정 지점부터 갑자기 말이 안 되는 명령어들의 나열로 보이면 → 그 직전에 `push 0x33` + `retf` 또는 `jmp far` 패턴이 있는지 확인하고, 있다면 그 지점부터 64비트로 재분석해본다.
- far call 이후의 스택 프레임이 이상하면 → CS가 함께 push된다는 점을 감안해서 오프셋을 다시 계산한다.
- 목적지 셀렉터 값의 의미를 모르겠다면 → Windows x64 표준 셀렉터(0x23=32비트 유저 코드, 0x33=64비트 유저 코드, 0x2B/0x1B 계열은 데이터 세그먼트 등)와 대조해본다.

## 미니 예제

**예제 1 — 직접 지정 far jmp**
```asm
jmp far ptr 0033h:0000000140001000h
```

**예제 2 — Heaven's Gate (WOW64 → 64비트 전환)**
```asm
push  33h
call  next
next:
add   dword ptr [esp], 5
retf
```

**예제 3 — 메모리 기반 간접 far call**
```asm
call fword ptr [rdi]   ; [rdi]에 저장된 셀렉터:오프셋으로 far call
```

**예제 4 — 부트로더 protected mode 진입**
```asm
jmp far 0008h:pm_start
pm_start:
    mov ax, 10h
    mov ds, ax
    ; 이제 32비트 protected mode
```

## 관련 글
- REV-0414 — RETF: Far 반환
- REV-0415 — IRET와 IRETD: 인터럽트 반환
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0066 — JMP: 무조건 분기
- REV-0077 — SYSCALL: x86-64 시스템 콜

## 출처/검증
- Far CALL/JMP 오퍼랜드 형식, 스택 동작(CS+오프셋 push), 세그먼트 디스크립터/권한 레벨 전환: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CALL—Call Procedure" 및 "JMP—Jump" 섹션의 far 형태 관련 서술, Volume 3A "Segment Descriptors" 및 "Control Transfers" 챕터 기준 (2026-09-08 검증).
- Heaven's Gate 기법(WOW64에서 far jmp/retf를 이용한 64비트 세그먼트 전환): 다수의 공개 악성코드 분석 보고서 및 리버싱 커뮤니티(예: Microsoft, 보안 벤더 기술 블로그)에서 공통적으로 설명하는 관찰된 기법.
