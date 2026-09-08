---
id: REV-0420
title: "STI와 CLI: 인터럽트 플래그 개념 소개"
slug: "rev-0420-sti-cli"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - sti
  - cli
  - STI
  - CLI
  - sti 명령어
  - cli 명령어
  - interrupt flag
  - 인터럽트 플래그
  - IF 플래그
  - 인터럽트 비활성화
  - 인터럽트 활성화
  - critical section kernel
  - 커널 크리티컬 섹션
  - ring0 instruction
  - privileged instruction
  - 권한 명령어
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - sti 뭐임
  - cli가 뭐죠
  - 인터럽트 끄는 명령
  - 인터럽트 켜는 명령
  - IF 플래그 조작
symptom_keywords:
  - sti cli가 커널 코드에서만 보이는 이유를 모르겠음
  - 유저모드에서 cli 실행하면 왜 죽나요
  - INT3 브레이크포인트랑 IF 플래그 헷갈림
  - 드라이버 코드에서 cli sti가 계속 나옴
  - 인터럽트 플래그와 소프트웨어 인터럽트 차이를 모르겠음
---

## 한 줄 요약
`STI`/`CLI`는 CPU의 인터럽트 플래그(IF)를 각각 1/0으로 설정해 마스크 가능한 하드웨어 인터럽트를 켜고 끄는 특권(privileged) 명령어로, 커널/드라이버 코드가 짧은 임계 구간(critical section)을 만들 때 쓴다.

## 언제 검색해야 하나
- 커널 드라이버나 부트로더 코드에서 `cli`, `sti`가 나오는데 무슨 뜻인지 모를 때
- 유저 모드 프로그램에서 `cli`를 실행했더니 크래시가 났을 때
- 인터럽트 플래그(IF, 하드웨어 인터럽트)와 디버거의 소프트웨어 브레이크포인트(`INT3`)를 혼동하고 있을 때
- `sti; hlt` 조합이 커널 유휴 루프에서 왜 함께 쓰이는지 궁금할 때

## 핵심 개념

### IF가 제어하는 것
`IF`(Interrupt Flag)는 EFLAGS의 9번 비트로, **마스크 가능한(maskable) 하드웨어 인터럽트(INTR 핀을 통한 인터럽트)**를 CPU가 받아들일지 여부를 결정한다.
- `STI`: `IF = 1` — 하드웨어 인터럽트 허용.
- `CLI`: `IF = 0` — 하드웨어 인터럽트 차단(대기시킴).

중요한 점은 IF가 **NMI(Non-Maskable Interrupt), 소프트웨어 인터럽트(`INT n`), 예외(#GP, #PF 등), `INT3` 브레이크포인트에는 전혀 영향을 주지 않는다**는 것이다. IF는 오직 "마스크 가능한" 하드웨어 인터럽트(타이머, 키보드, 네트워크 카드 등의 IRQ)만 제어한다.

### 특권 명령어
`STI`/`CLI`는 CPL(Current Privilege Level)이 IOPL(I/O Privilege Level) 이하일 때만 실행 가능한 특권 명령어다. 실제로는 거의 항상 CPL=0(커널/ring0)에서만 실행된다. 유저 모드(ring3) 프로그램이 이를 실행하면 `#GP`(General Protection Fault) 예외가 발생해 프로세스가 즉시 종료된다(Windows: `STATUS_PRIVILEGED_INSTRUCTION`).

### 왜 커널에서 인터럽트를 끄는가
커널이 여러 CPU 코어나 인터럽트 핸들러와 공유하는 자료구조를 짧게 수정해야 할 때, 그 수정 도중 타이머 인터럽트나 다른 하드웨어 인터럽트가 끼어들어 같은 자료구조를 건드리면 데이터가 깨질 수 있다. `CLI`로 인터럽트를 잠시 막아 그 짧은 구간을 "원자적(atomic)"으로 만들고, 작업이 끝나면 `STI`로 즉시 되돌린다.
```asm
cli
mov  eax, [shared_counter]
inc  eax
mov  [shared_counter], eax
sti
```
이런 구간은 최대한 짧게 유지해야 한다 — 인터럽트를 오래 막아두면 타이머 틱을 놓치거나 응답성이 나빠질 수 있기 때문이다.

### STI의 "한 명령 지연" 특성
`STI`는 실행되자마자 바로 인터럽트를 받아들이는 게 아니라, **STI 다음 한 명령이 완전히 실행된 뒤부터** 인터럽트가 인식된다. 이 특성 덕분에 `STI` 바로 다음 줄에 `HLT`를 놓으면, "인터럽트를 켜는 동작"과 "그 인터럽트를 기다리며 정지하는 동작"이 사이에 인터럽트가 끼어들 틈 없이 원자적으로 이어진다.
```asm
sti
hlt         ; STI와 HLT 사이에는 인터럽트가 끼어들 수 없음(고전적인 유휴 루프 관용구)
```

### 플래그/레지스터/스택 영향
- `STI`/`CLI` 모두 **IF만** 바꾸고 다른 플래그(CF, ZF, SF, OF, PF)는 그대로 둔다.
- 범용 레지스터/메모리는 건드리지 않는다.
- 스택 변화 없음. RIP는 명령어 길이만큼 증가.

### IDA/Ghidra 디컴파일에서의 모습
`STI`/`CLI`는 일반적인 데이터 흐름에 영향을 주지 않는 명령이라, 디컴파일러가 자동으로 인식하는 고수준 표현이 따로 없다. IDA F5나 Ghidra 디컴파일 결과에서는 대개 원문 그대로 인라인 어셈블리 형태로 남거나, 아예 표시되지 않고 생략되는 경우도 있다. 실제 의미를 파악하려면 raw disassembly 창에서 직접 확인해야 한다.

### 왜 유저 모드 리버서에게 중요한가
CTF에서 커널 익스플로잇이나 드라이버 취약점 문제를 다룰 때, `cli`/`sti`가 감싸는 구간은 "동시성 버그가 있을 수도, 없을 수도 있는 경계"를 표시해준다. 이 구간이 지나치게 길면 다른 코어의 인터럽트 처리가 지연되어 DoS(서비스 거부) 문제가 될 수 있고, 반대로 이 구간이 있어야 할 자리에 빠져 있으면 레이스 컨디션 취약점의 단서가 될 수 있다. 커널 드라이버 코드를 분석할 때 `cli...sti` 쌍으로 둘러싸인 부분을 찾아 그 안의 공유 자원이 무엇인지 목록화해두면, 취약점 헌팅의 좋은 출발점이 된다.

## 화면/코드에서 보이는 징후
```asm
cli
mov  [shared_data], eax
sti
```
```asm
sti
hlt
```
정상적인 애플리케이션(EXE/ELF) 바이너리의 함수 안에서 `cli`/`sti`가 보인다면, 이는 커널 드라이버가 아니라 다음 중 하나일 가능성이 크다: 잘못 디스어셈블된 데이터, 의도적인 크래시 트랩, 또는 실제로는 커널 모드 코드(.sys 드라이버, 부트로더)를 분석하고 있는 것.

## 가장 먼저 할 것
1. 지금 보고 있는 바이너리가 정말 커널/드라이버/펌웨어 코드인지 확인한다(파일 확장자 `.sys`, 임포트하는 함수가 `Ntoskrnl.exe`/`Hal.dll` 계열인지 등).
2. 일반 유저 모드 EXE/ELF라면 이 `cli`/`sti`가 실제 실행 경로인지 Xref로 확인한다.
3. `sti`와 `hlt`가 붙어 있다면 커널 유휴 루프 패턴임을 인지한다.

## 단계별 절차
1. `cli`로 시작해서 `sti`로 끝나는 구간을 하나의 임계 구역으로 묶어서 읽는다.
2. 그 구간 안에서 어떤 공유 자원(전역 변수, 자료구조)이 수정되는지 확인한다 — 동시성 버그를 찾는 실마리가 된다.
3. 커널 디버거(WinDbg 커널 모드, KGDB, QEMU+GDB 등)로 실제 동작을 추적한다 — 일반 유저 모드 디버거(x64dbg, GDB ptrace 모드)로는 이 코드를 정상 실행할 수 없다.

## 명령어/단축키
- 유저 모드 디버거(x64dbg, GDB)에서는 `cli`/`sti`에 도달하면 특권 명령어 예외로 프로세스가 즉시 종료되므로, 도달 전에 멈춰야 한다.
- 커널 디버깅이 필요하다면 WinDbg를 커널 모드로 연결(`kd`)하거나, 에뮬레이터(QEMU) + GDB stub을 사용한다.

## 출력 해석
- Windows: `STATUS_PRIVILEGED_INSTRUCTION (0xC0000096)` 예외가 뜨면 유저 모드에서 `cli`/`sti` 같은 특권 명령이 실행된 것이다.
- 디버거 플래그 창에서 `IF` 비트(비트 9)를 보면 인터럽트 허용 여부를 바로 확인할 수 있다.

## 흔한 실수
- `IF`(인터럽트 플래그)를 디버거의 `INT3` 소프트웨어 브레이크포인트나 `INT n` 소프트웨어 인터럽트와 같은 것으로 착각하는 것 — IF는 오직 마스크 가능한 하드웨어 인터럽트만 제어하며, `INT3`/`INT n`/예외는 IF와 무관하게 항상 발생한다.
- 유저 모드 코드에서 `cli`를 보고 "인터럽트를 잠깐 끄는 정상적인 동작"이라 여기고 넘어가는 것 — 유저 모드에서는 이 명령 자체가 존재하면 안 되며, 발견되면 즉시 크래시 원인이나 잘못된 disassembly를 의심해야 한다.
- `cli` 이후 `sti`로 복원하지 않는 코드를 정상으로 오해하는 것 — 실제 커널 코드에서 인터럽트를 계속 막아두면 시스템 전체가 멈추거나 응답 불가 상태가 될 수 있다(버그 또는 의도적 DoS).

## 막혔을 때 다음 체크
- 이 코드가 진짜 커널/드라이버 코드인지 다시 확인했는가?
- `cli`와 짝을 이루는 `sti`가 어딘가에 있는지 찾아봤는가?
- 유저 모드 디버거로 무작정 실행하려다 특권 명령어 예외로 막힌 것은 아닌지 확인했는가?

## 미니 예제

**예제 1 — 커널 임계 구역**
```asm
cli
mov  eax, [shared_data]
inc  eax
mov  [shared_data], eax
sti
```
C로 개념화하면 `local_irq_disable(); shared_data++; local_irq_enable();` (리눅스 커널 스타일 매크로)에 해당한다.

**예제 2 — 유휴 루프**
```asm
idle_loop:
    sti
    hlt          ; STI 다음 명령까지는 인터럽트가 지연되어, hlt까지 원자적으로 처리됨
    jmp  idle_loop
```

**예제 3 — 유저 모드에서 만나면 크래시**
```asm
cli              ; 유저 모드(ring3)라면 여기서 #GP -> 프로세스 종료
mov  [x], eax
sti
```

## 관련 글
- REV-0416 — HLT: CPU 정지 명령
- REV-0079 — INT와 INT 0x80: 인터럽트 기반 시스템 콜
- REV-0046 — PUSHF와 POPF: 플래그 저장과 복원
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- STI/CLI 명령어 동작 및 IF 정의, STI의 명령 지연 특성: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "STI—Set Interrupt Flag" / "CLI—Clear Interrupt Flag" 섹션, Volume 3A 인터럽트/예외 챕터 기준 (2026-09-08 검증).
- Windows `STATUS_PRIVILEGED_INSTRUCTION` 예외 코드: Microsoft Learn NTSTATUS 값 문서 기준.
