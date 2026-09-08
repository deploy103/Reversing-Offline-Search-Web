---
id: REV-0414
title: "RETF: Far 반환"
slug: "rev-0414-retf"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - retf
  - RETF
  - Retf
  - retf 명령어
  - retf instruction
  - far return
  - 원거리 반환
  - far ret
  - "retf"
  - "retf 4"
  - retf와 ret 차이
  - heaven's gate retf
aliases:
  - retf 뭐임
  - retf가 뭐죠
  - retf 명령
  - RETF 명령어
  - far return 명령어
symptom_keywords:
  - retf가 스택에서 몇 바이트를 읽는지 모르겠음
  - push 0x33 다음에 retf가 나올 때
  - retf와 ret 차이가 뭔지 모르겠음
  - retf와 iret 차이
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`RETF`(Far Return)는 [`RET`](rev-0072-ret.md)와 달리 스택에서 반환 오프셋(IP/EIP/RIP)뿐 아니라 **CS(코드 세그먼트 셀렉터)까지 함께 POP**해서, [Far CALL](rev-0413-far-call-jmp.md)로 넘어왔던 원래 세그먼트로 정확히 되돌아가는 명령어다.

## 언제 검색해야 하나
- `retf` 명령어를 만났는데 일반 `ret`과 무엇이 다른지 궁금할 때
- `push 0x33` 뒤에 `retf`가 나오는 코드(Heaven's Gate 패턴, REV-0413 참고)를 분석할 때
- Far CALL로 호출된 함수의 끝에서 어떤 명령어로 복귀해야 하는지 궁금할 때
- `RETF`와 `IRET`(REV-0415)가 비슷해 보이는데 정확히 뭐가 다른지 궁금할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
RETF            ; 오퍼랜드 없음
RETF imm16      ; 복귀 후 스택에서 imm16 바이트를 추가로 버림 (호출자 스택 정리)
```
NASM/일부 어셈블러는 `RETF`로 표기하지만, Intel 매뉴얼 원문에서는 이것도 그냥 "RET"의 far 변형으로 다뤄진다 — 오피코드가 다르다: near RET는 `C3`(오퍼랜드 없음)/`C2`(imm16), far RET(`RETF`)는 `CB`(오퍼랜드 없음)/`CA`(imm16)이다.

### 실제로 하는 일 — Far CALL의 정확한 반대
[Far CALL](rev-0413-far-call-jmp.md)이 실행되면 스택에는 (아래에서부터) **반환 오프셋(IP/EIP/RIP), 그 위에 CS**가 순서대로 쌓인다. `RETF`는 이를 정확히 반대로 되돌린다:
1. 스택 맨 위에서 반환 오프셋을 POP해서 IP/EIP/RIP에 로드한다.
2. 그 다음 스택에서 CS 셀렉터를 POP해서 CS 레지스터에 로드한다.
3. `RETF imm16` 형태라면 추가로 imm16 바이트만큼 스택을 더 정리한다(스택 기반 인자를 넘기는 far 호출 규약에서 호출자가 넣은 인자를 정리하는 용도).

일반 `RET`가 스택에서 오프셋 하나만 꺼내는 것과 달리, `RETF`는 **오프셋과 셀렉터 두 개**를 꺼낸다는 점이 핵심 차이다.

### 플래그 변화
`RETF`는 플래그 레지스터를 건드리지 않는다. 이 점이 [`IRET`](rev-0415-iret-iretd.md)(REV-0415, 플래그까지 함께 복원)와의 결정적 차이다.

### signed/unsigned 관점
해당 없음.

### 스택/RSP/RIP 변화
```
RETF 실행 전:  스택 최상단 = [반환 오프셋][CS]  (오프셋이 더 낮은 주소)
RETF 실행:
  1. offset = pop()   ; RSP += (오퍼랜드 크기)
  2. CS = pop()         ; RSP += (오퍼랜드 크기, 보통 세그먼트 셀렉터는 스택에서 워드/더블워드 단위로 정렬되어 저장됨)
  3. RIP = offset
  4. (imm16 있으면) RSP += imm16
```

### 짝을 이루는 명령어
`RETF`는 반드시 [Far CALL](rev-0413-far-call-jmp.md)(또는 그와 동등하게 CS와 오프셋을 스택에 미리 세팅해둔 코드)과 짝을 이뤄야 의미가 있다. 만약 스택에 CS로 쓸 값과 오프셋 값을 **직접 push해서 세팅한 뒤 `retf`를 실행**하면, 이는 사실상 "far jmp를 흉내 내는" 용도로 쓰일 수 있다 — 바로 이것이 [Heaven's Gate](rev-0413-far-call-jmp.md) 기법에서 `retf`가 등장하는 이유다: far call 없이도 스택만 원하는 값으로 만들어두면 `retf` 한 줄로 CS와 IP를 동시에 원하는 값으로 바꿀 수 있다.

### 컴파일러 패턴
일반 C 컴파일러는 사용자 모드 애플리케이션에서 `RETF`를 생성하지 않는다 — near call/ret만으로 충분한 플랫 메모리 모델을 쓰기 때문이다. `RETF`가 보이면 부트로더/커널/드라이버의 far call 반환, 또는 Heaven's Gate류의 세그먼트 전환 트릭임을 의심해야 한다.

### IDA/Ghidra에서 보이는 형태
`retf` 그대로 표시된다. Hex-Rays 디컴파일러는 이를 일반적인 함수 반환으로 정리하지 못하는 경우가 많으며, Heaven's Gate 패턴의 일부라면 오히려 디스어셈블리가 그 지점에서 끊기거나 이상해 보일 수 있다 — 이럴 때는 `retf` 직전 스택에 어떤 값들이 push됐는지(특히 셀렉터 값) 손으로 추적하는 것이 정확하다.

### 리버싱 의미
`RETF`를 만나면 항상 다음 두 가지 중 하나를 의심해야 한다:
1. **정상적인 far call의 반환** — 부트로더/커널 코드에서 far call로 호출된 서브루틴이 끝나는 지점.
2. **의도적인 CS 전환 트릭** — `push 셀렉터; push 목적지오프셋; retf`처럼 far call 없이 스택을 직접 조작해서 `retf`를 "제어된 far jmp"처럼 쓰는 경우. 이 경우 Heaven's Gate 등 안티 분석 기법일 가능성이 높다.

## 화면/코드에서 보이는 징후
- `retf` — far call로 호출된 코드의 끝
- `retf 8` — 반환 후 스택에서 8바이트(예: far 호출 규약의 인자 2개)를 추가로 정리
- `push 셀렉터` → `push 오프셋`(또는 계산된 주소) → `retf` — Heaven's Gate류 세그먼트 전환 패턴 (REV-0413 참고)

## 가장 먼저 할 것
1. `retf` 직전에 스택에 무엇이 준비돼 있는지(정상적인 far call 프레임인지, 손으로 push한 셀렉터+오프셋인지) 확인한다.
2. `retf` 실행 후 CS 값이 무엇으로 바뀌는지 확인해서 실행 모드(16/32/64비트)가 달라지는지 판단한다.
3. `imm16` 오퍼랜드가 있다면 그 값만큼 스택이 추가로 줄어든다는 것을 감안해서 이후 스택 계산을 맞춘다.

## 단계별 절차

**1) 정상적인 far call 반환**
```asm
; 호출부
call far ptr 0028h:sub_far_proc

; sub_far_proc 내부
sub_far_proc:
    ; ... 처리 ...
    retf              ; 호출 지점으로 CS:IP를 함께 복원하며 복귀
```

**2) Heaven's Gate류 세그먼트 전환 트릭**
```asm
push  33h              ; 목적지 셀렉터 (64비트 코드 세그먼트)
push  target_offset      ; 목적지 오프셋
retf                     ; CS와 IP를 동시에 target_offset, 0x33으로 교체 -> 사실상 far jmp
```

**3) 스택 정리가 있는 far 반환**
```asm
sub_far_proc:
    ; ... 처리 ...
    retf 4              ; 복귀 후 추가로 4바이트(예: 스택 인자 하나) 정리
```

## 명령어/단축키
- IDA: `retf` 직전 몇 줄을 거슬러 올라가며 스택에 push된 값(특히 상수로 보이는 셀렉터 후보)을 확인
- x64dbg/GDB: `retf` 실행 직전 스택 덤프에서 두 값(오프셋, 셀렉터)을 직접 확인, 실행 후 CS 레지스터 값 변화 관찰

## 출력 해석
- `retf` 실행 후 CS 레지스터가 실행 전과 다르다면, 세그먼트(실행 모드/권한 레벨)가 실제로 바뀐 것이다.
- `retf` 직전 스택 최상단 두 값이 "합리적인 코드 주소"와 "알려진 셀렉터 값(0x08, 0x23, 0x33 등)"처럼 보이면, 이는 정상적인 far call 반환이거나 계획된 세그먼트 전환이다.

## 흔한 실수
- `RETF`를 그냥 `RET`와 같은 것으로 취급해서 스택에서 딱 하나(오프셋)만 꺼낸다고 착각하는 것 — CS도 함께 꺼내므로 소비하는 스택 바이트 수가 다르다.
- `RETF`와 `IRET`(REV-0415)를 혼동하는 것 — `RETF`는 CS와 IP만 복원하고, `IRET`는 여기에 더해 FLAGS/EFLAGS까지(그리고 권한 레벨이 바뀌는 경우 SS/ESP까지) 복원한다.
- `push 셀렉터; push 오프셋; retf` 패턴을 보고 단순히 "함수에서 리턴하는구나"라고 넘기는 것 — 실제로는 far call 없이 `retf`를 이용한 의도적 CS 전환(Heaven's Gate 등)일 수 있다.
- `RETF imm16`에서 imm16을 무시하고 스택 오프셋을 잘못 계산하는 것.

## 막혔을 때 다음 체크
- `retf` 실행 후 코드가 이상하게 해석되면 → CS가 바뀌어서 실행 모드(16/32/64비트)가 달라졌을 가능성을 의심하고 REV-0413의 Heaven's Gate 설명을 참고한다.
- `retf` 앞에 대응하는 far call이 안 보이면 → 스택을 직접 조작한 세그먼트 전환 트릭일 가능성이 높으니 push된 두 값을 그대로 "새 CS:IP"로 해석해본다.
- 스택 정리량이 이해 안 되면 → `retf` 뒤에 붙은 imm16 값을 확인해서 몇 바이트가 추가로 버려지는지 계산한다.

## 미니 예제

**예제 1 — 기본 far call/retf 쌍**
```asm
call far ptr 0028h:sub_1
; ...
sub_1:
    mov  eax, 1
    retf
```

**예제 2 — Heaven's Gate 스타일 세그먼트 전환**
```asm
push  33h
push  0000000140002000h
retf
```

**예제 3 — 스택 정리가 있는 far 반환**
```asm
sub_far_with_args:
    ; ... 인자 2개(8바이트)를 스택으로 받아 처리 ...
    retf 8
```

## 관련 글
- REV-0413 — 원거리(Far) CALL과 JMP 기초
- REV-0415 — IRET와 IRETD: 인터럽트 반환
- REV-0072 — RET: 함수 반환과 스택 변화
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- RETF(far RET) 오퍼랜드 형식, 스택에서 CS와 오프셋을 함께 POP하는 동작, imm16 스택 정리: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "RET—Return from Procedure" 섹션의 far 반환 서술 기준 (2026-09-08 검증).
- Heaven's Gate 기법에서 push 셀렉터 + push 오프셋 + retf 조합을 이용한 세그먼트 전환: 다수의 공개 악성코드 분석 보고서 및 리버싱 커뮤니티 기술 자료에서 공통적으로 설명하는 관찰된 기법.
