---
id: REV-0415
title: "IRET와 IRETD: 인터럽트 반환"
slug: "rev-0415-iret-iretd"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - iret
  - IRET
  - Iret
  - iretd
  - IRETD
  - Iretd
  - iretq
  - IRETQ
  - iret 명령어
  - iretd 명령어
  - interrupt return
  - 인터럽트 반환
  - "iret"
  - "iretd"
  - "iretq"
  - 인터럽트 서비스 루틴
  - ISR 반환
  - trap flag 복원
aliases:
  - iret 뭐임
  - iretd 뭐임
  - iret가 뭐죠
  - iret 명령
  - IRET 명령어
  - IRETD 명령어
  - 인터럽트 리턴 명령어
symptom_keywords:
  - 인터럽트 핸들러 끝에서 iret이 왜 나오는지
  - iret과 retf 차이
  - 커널 드라이버 코드에서 iret이 보일 때
  - iret이 플래그까지 복원하는 이유
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`IRET`/`IRETD`(그리고 64비트의 `IRETQ`)는 인터럽트나 예외 처리 루틴의 마지막에 실행되어, 스택에서 명령어 포인터·코드 세그먼트·플래그 레지스터를 한꺼번에 복원함으로써 인터럽트 발생 직전의 실행 상태로 완전히 되돌아가는 명령어다.

## 언제 검색해야 하나
- 인터럽트 서비스 루틴(ISR), 예외 핸들러, OS 커널/드라이버 코드에서 `iret`, `iretd`를 만났을 때
- [`RETF`](rev-0414-retf.md)(REV-0414)와 `IRET`가 비슷해 보이는데 정확히 무엇이 다른지 궁금할 때
- 안티 디버깅 코드에서 TF(Trap Flag)를 다루는데 `iret`이 관련되어 있을 때
- 커널 익스플로잇/CTF 문제에서 "가짜 인터럽트 스택 프레임을 만들어 iret으로 유저 모드에 복귀"하는 기법을 분석할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
IRET     ; 16비트: IP, CS, FLAGS를 POP
IRETD    ; 32비트: EIP, CS, EFLAGS를 POP
IRETQ    ; 64비트: RIP, CS, RFLAGS를 POP (경우에 따라 RSP, SS까지)
```
셋 다 오퍼랜드가 없다 — 니모닉 자체가 오퍼랜드 크기를 나타낸다(어셈블러에 따라 그냥 `IRET`으로 쓰고 모드에 맞게 자동으로 크기가 결정되기도 한다).

### 실제로 하는 일 — RETF보다 한 단계 더 복원
[`RETF`](rev-0414-retf.md)가 CS와 IP(오프셋) 두 가지만 스택에서 복원하는 반면, `IRET`/`IRETD`는 **여기에 더해 FLAGS/EFLAGS까지 통째로 복원**한다:
```
IRET (16비트) 스택에서 POP하는 순서:
  1. IP
  2. CS
  3. FLAGS

IRETD (32비트):
  1. EIP
  2. CS
  3. EFLAGS

IRETQ (64비트, long mode):
  1. RIP
  2. CS
  3. RFLAGS
  (권한 레벨이 바뀌는 인터럽트라면 추가로) 4. RSP  5. SS
```
64비트 모드에서는 인터럽트/예외가 발생할 때 CPU가 항상 **SS:RSP까지 포함한 전체 프레임**을 스택에 저장하도록 설계되어 있어서(특권 레벨이 안 바뀌는 경우에도 마찬가지로 취급되는 구현이 많음), `IRETQ`는 상황에 따라 5개 항목 모두를 복원할 수 있다.

### 하드웨어 예외의 에러 코드 처리 — 잊기 쉬운 함정
일부 예외(`#GP`, `#PF`, `#DF` 등)는 CPU가 인터럽트 프레임을 만들 때 **에러 코드(error code)를 추가로 스택에 push**한다. 이 에러 코드는 `IRET`이 자동으로 처리해주지 않으므로, 핸들러는 `IRET`을 실행하기 **직전에 반드시 `add rsp, 8`(또는 해당 크기만큼) 같은 명령으로 에러 코드를 수동으로 버려야 한다.** 이걸 빠뜨리면 `IRET`이 엉뚱한 값을 RIP/CS/RFLAGS로 잘못 해석해서 곧바로 크래시(대개 `#GP` 또는 `#UD` 연쇄 발생)로 이어진다.

### 플래그 변화
`IRET`은 목적 자체가 "플래그를 포함해 실행 상태 전체를 복원"하는 것이므로, **거의 모든 플래그(CF, ZF, SF, OF, TF, IF, DF 등)가 스택에 있던 값으로 완전히 교체**된다. 이 점이 `RETF`(플래그를 전혀 안 건드림)와의 결정적 차이이며, `IRET` 자체는 "일부 플래그만 세팅하는" 일반 산술 명령어들과는 근본적으로 다른 특수 명령어다.

### signed/unsigned 관점
해당 없음 — 실행 컨텍스트 복원 명령어다.

### 스택/RSP 변화
인터럽트 진입 시 CPU가 자동으로 쌓아둔 프레임을 그대로 되돌리는 것이므로, `IRET` 실행 후 RSP는 인터럽트가 발생하기 직전 값으로 정확히 복귀한다(에러 코드를 미리 정리했다는 전제하에).

### 사용 위치 — 커널 모드 전용
`IRET`은 사실상 **인터럽트 서비스 루틴(ISR), CPU 예외 핸들러, 하이퍼바이저, 부트로더의 저수준 코드**에서만 나타난다. 일반 사용자 모드 애플리케이션 코드에는 절대 등장하지 않는다 — 애초에 유저 모드 코드는 인터럽트를 직접 다루지 않으며, 부적절한 상황에서 `IRET`을 실행하면 권한 검사에 걸려 `#GP` 예외가 발생한다.

### 컴파일러 패턴
C 컴파일러가 일반 애플리케이션 코드에서 `IRET`을 생성하는 일은 없다. OS 커널/드라이버 소스에서 `__declspec(naked)` 인터럽트 핸들러나 어셈블리로 직접 작성된 ISR의 맨 끝에서만 나타난다.

### IDA/Ghidra에서 보이는 형태
`iretd`/`iretq` 그대로 표시된다. 이 명령어가 있는 함수는 Hex-Rays가 일반 함수처럼 디컴파일하지 못하는 경우가 많다(반환 방식 자체가 표준 호출 규약과 다르기 때문) — 어셈블리 원문으로 스택 프레임을 직접 추적하는 것이 정확하다.

### 리버싱 의미
- **커널/드라이버 리버싱**: `iret`은 IDT(Interrupt Descriptor Table)에 등록된 핸들러의 끝을 표시하는 강한 신호다. 핸들러 시작부터 `iret`까지의 코드가 하나의 완결된 인터럽트 처리 로직이다.
- **커널 익스플로잇/CTF**: 커널 취약점을 이용해 임의 코드 실행에 성공한 뒤, 다시 안전하게 유저 모드로 복귀하기 위해 **가짜 인터럽트 스택 프레임(SS, RSP, RFLAGS, CS, RIP를 원하는 값으로 손수 구성)을 만들고 `iretq`를 실행**해서 유저 모드 셸로 복귀하는 것이 커널 익스플로잇의 정석적인 마무리 기법("iret to user mode")이다.
- **안티 디버깅/플래그 조작**: `IRET`이 TF(Trap Flag)까지 복원한다는 점을 이용해, 인터럽트 핸들러가 의도적으로 조작된 FLAGS 값을 스택에 심어두고 `IRET`으로 복귀시켜 싱글 스텝 상태를 강제로 켜거나 끄는 저수준 트릭도 존재한다.

## 화면/코드에서 보이는 징후
- ISR/예외 핸들러의 맨 끝에 위치한 `iretd`/`iretq`
- `iret` 직전의 `add rsp, 8` — 하드웨어가 push한 에러 코드를 수동으로 버리는 코드(#GP, #PF 등 처리기에서 흔함)
- 커널 익스플로잇 코드에서 `push ss; push rsp; pushfq; push cs; push 목적지; iretq` 형태로 유저 모드 복귀 프레임을 손수 구성하는 패턴

## 가장 먼저 할 것
1. 이 함수가 IDT에 등록된 인터럽트/예외 핸들러인지(진입점 이름, 주변 참조) 확인한다.
2. `iret` 직전에 에러 코드를 정리하는 `add rsp, N`이 있는지 확인한다 — 있다면 이 예외가 하드웨어 에러 코드를 동반하는 종류(#GP, #PF, #DF 등)임을 알 수 있다.
3. 스택에 최종적으로 남는 값들이 IP/CS/FLAGS(그리고 필요시 RSP/SS) 순서로 올바르게 구성되어 있는지 확인한다.

## 단계별 절차

**1) 기본 ISR 패턴**
```asm
my_isr:
    pushad                  ; 레지스터 보존 (REV-0412 참고)
    ; ... 인터럽트 처리 ...
    popad                    ; 레지스터 복원
    iretd                     ; EIP, CS, EFLAGS 복원 후 원래 실행 지점으로 복귀
```

**2) 에러 코드가 있는 예외 핸들러 (예: #GP)**
```asm
gp_fault_handler:
    ; 스택: [에러코드][EIP][CS][EFLAGS] (하드웨어가 자동으로 push)
    ; ... 에러코드를 이용한 처리 ...
    add   esp, 4              ; 에러 코드 버리기 (필수!)
    iretd                      ; 이제 스택 최상단이 EIP이므로 정상 복귀
```

**3) 커널 익스플로잇의 "iret to user mode" 패턴**
```asm
; 커널 컨텍스트에서 유저 모드로 안전하게 복귀
push  user_ss
push  user_rsp
pushfq
push  user_cs
push  user_rip
iretq                          ; 5개 값을 한 번에 로드하며 유저 모드로 전환
```

## 명령어/단축키
- WinDbg/GDB(커널 디버깅): 인터럽트 핸들러 진입/종료 지점에 브레이크포인트를 걸어 `iret` 실행 전 스택 프레임(IP/CS/FLAGS 등)을 직접 덤프해서 확인
- IDA: IDT 관련 심볼(`KiInterruptDispatch` 계열 등, 커널 이미지 분석 시)을 통해 ISR 경계를 먼저 파악한 뒤 `iret` 위치를 추적

## 출력 해석
- `iret` 실행 직전 스택 최상단이 항상 IP/EIP/RIP여야 한다 — 만약 그 위치에 엉뚱한 값(정리 안 된 에러 코드 등)이 남아있다면 실행이 잘못된 주소로 튀며 크래시로 이어진다.
- `iret` 실행 후 FLAGS/EFLAGS/RFLAGS가 인터럽트 발생 직전 값과 동일해야 정상이다.

## 흔한 실수
- `IRET`을 `RETF`와 같은 것으로 착각하는 것 — `IRET`은 CS/IP에 더해 FLAGS까지(그리고 상황에 따라 RSP/SS까지) 복원하므로 스택에서 꺼내는 항목 수가 다르다.
- 에러 코드를 동반하는 예외 핸들러에서 `iret` 전에 에러 코드를 정리하는 `add rsp, N`을 빠뜨리는 것 — 이는 실제 커널 프로그래밍에서도 매우 흔한 치명적 버그다.
- `IRET`을 유저 모드 애플리케이션 코드에서도 볼 수 있다고 가정하는 것 — 정상적인 유저 모드 코드에는 절대 나타나지 않으며, 나타난다면 커널/드라이버 코드이거나 특수한(익스플로잇 등) 상황이다.
- `IRET`이 복원하는 FLAGS 값에 따라 TF(싱글 스텝)나 IF(인터럽트 허용)가 바뀔 수 있다는 것을 간과해서, `iret` 직후 디버거의 동작(예상치 못한 싱글 스텝 예외 발생 등)이 이상해 보이는 것을 이해하지 못하는 것.

## 막혔을 때 다음 체크
- `iret` 실행 직후 크래시가 난다면 → 직전에 에러 코드를 정리하는 `add rsp, N`이 빠졌는지, 스택에 남은 값들의 순서가 IP/CS/FLAGS(순)로 맞는지 확인한다.
- 이 코드가 왜 유저 모드가 아닌 곳에 있는지 궁금하면 → IDT 등록 여부, 함수가 커널 이미지(ntoskrnl.exe, vmlinux 등) 소속인지 확인한다.
- 커널 익스플로잇 코드를 분석 중인데 `iretq` 앞에 5개의 `push`가 있다면 → 이는 "가짜 인터럽트 프레임을 만들어 유저 모드로 복귀"하는 표준 마무리 기법이므로, 각 push 값(SS, RSP, RFLAGS, CS, RIP)이 무엇을 가리키는지 하나씩 확인한다.

## 미니 예제

**예제 1 — 기본 ISR**
```asm
timer_isr:
    pushad
    call  handle_timer_tick
    popad
    iretd
```

**예제 2 — 에러 코드가 있는 예외 핸들러**
```asm
page_fault_handler:
    ; 스택: [error_code][eip][cs][eflags]
    push  eax
    mov   eax, [esp+4]      ; error_code 읽기
    call  log_page_fault
    pop   eax
    add   esp, 4              ; error_code 정리 (필수)
    iretd
```

**예제 3 — 커널 익스플로잇의 iret to user mode**
```asm
; RIP=shellcode_addr, CS=user_cs, RFLAGS=원하는 플래그,
; RSP=user_stack, SS=user_ss로 유저 모드 복귀
push  user_ss
push  user_stack
push  0202h              ; 원하는 RFLAGS (IF 세팅 등)
push  user_cs
push  shellcode_addr
iretq
```

## 관련 글
- REV-0414 — RETF: Far 반환
- REV-0413 — 원거리(Far) CALL과 JMP 기초
- REV-0411 — PUSHA와 POPA: 레거시 32비트 일괄 저장/복원
- REV-0412 — PUSHAD와 POPAD 차이
- REV-0046 — PUSHF와 POPF: 플래그 저장과 복원
- REV-0079 — INT와 INT 0x80: 인터럽트 기반 시스템 콜

## 출처/검증
- IRET/IRETD/IRETQ 명령어의 스택 복원 순서(IP/EIP/RIP, CS, FLAGS/EFLAGS/RFLAGS, 권한 전환 시 RSP/SS 포함), 하드웨어 예외의 에러 코드 처리: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "IRET/IRETD—Interrupt Return" 섹션 및 Volume 3A "Interrupt and Exception Handling" 챕터 기준 (2026-09-08 검증).
- 커널 익스플로잇의 "iret to user mode" 복귀 기법: 다수의 공개 커널 익스플로잇/CTF 문서 및 리버싱 교육 자료에서 공통적으로 설명하는 관찰된 실무 기법.
