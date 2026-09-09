---
id: REV-0671
title: "Linux 시그널(SIGSEGV 등)과 리버싱에서의 의미"
slug: "rev-0671-linux-signals-reversing"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, strace]
keywords: ["SIGSEGV", "SIGABRT", "SIGTRAP", "SIGILL", "시그널", "signal", "리눅스 시그널"]
aliases: ["세그폴트 시그널", "SIGSEGV 뜻", "시그널 번호 표", "Segmentation fault 원인"]
symptom_keywords: ["Segmentation fault core dumped", "Aborted core dumped", "종료코드 139", "gdb Program terminated with signal SIGSEGV"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
리눅스 프로세스가 잘못된 메모리 접근이나 오류로 죽을 때 터미널에 뜨는 `Segmentation fault (core dumped)`, `Aborted (core dumped)` 같은 메시지는 커널이 프로세스에 SIGSEGV(11), SIGABRT(6) 같은 시그널을 보낸 결과이며, 이 시그널 번호와 종류를 알면 GDB가 왜 멈췄는지, 셸의 종료 코드가 왜 그 숫자인지, 프로그램이 크래시한 원인이 무엇인지를 빠르게 좁힐 수 있다.

## 언제 검색해야 하나
- 프로그램을 실행했더니 `Segmentation fault (core dumped)`만 뜨고 아무 정보도 없을 때
- GDB `run` 중 `Program received signal SIGSEGV, Segmentation fault.` 메시지가 뜨는데 이게 뭘 의미하는지 모를 때
- 셸에서 `echo $?`로 확인한 종료 코드가 `139`, `134` 같은 이상한 숫자로 나오는 이유가 궁금할 때
- 안티 디버깅 코드가 일부러 시그널을 발생시켜서 디버거를 감지하거나 흐름을 제어하는 패턴을 분석해야 할 때

## 핵심 개념

### 시그널이란
시그널은 커널이 프로세스에게 "이벤트가 발생했다"고 비동기적으로 알리는 메커니즘이다. 하드웨어 예외(잘못된 메모리 접근, 0으로 나누기)나 다른 프로세스의 요청(`kill`), 또는 프로그램 자신이 `raise()`/`abort()`를 호출한 결과로 발생한다. 각 시그널은 번호와 이름을 갖고, 기본 동작(default disposition)이 정해져 있다 — 대부분은 프로세스 종료(그리고 일부는 core dump 생성)다.

### 리버싱에서 자주 만나는 시그널
| 번호 | 이름 | 기본 동작 | 흔한 발생 원인 |
|---|---|---|---|
| 4 | SIGILL | 종료+core | 잘못된/알 수 없는 명령어 실행 (opcode 손상, 잘못된 점프) |
| 5 | SIGTRAP | 종료+core | `int3`(0xCC) 실행, 싱글스텝 완료 — 디버거/브레이크포인트의 핵심 시그널 |
| 6 | SIGABRT | 종료+core | `abort()` 호출 — 스택 카나리 감지(`__stack_chk_fail`), glibc `malloc`/`free` 무결성 검사 실패, `assert()` 실패 |
| 7 | SIGBUS | 종료+core | 정렬 안 된 메모리 접근, `mmap`한 파일의 범위를 벗어난 접근 |
| 8 | SIGFPE | 종료+core | 정수 나눗셈 0 또는 `INT_MIN / -1` 오버플로우(부동소수점과 무관하게도 발생) |
| 9 | SIGKILL | 즉시 종료(차단 불가) | 강제 종료, 커널이 프로세스를 즉시 죽일 때 |
| 11 | SIGSEGV | 종료+core | 잘못된 포인터 역참조, 매핑 안 된 주소 접근, 쓰기 금지 영역에 쓰기 |
| 31 | SIGSYS | 종료+core | seccomp(REV-0673)가 허용하지 않은 시스템 콜을 호출했을 때 |

### 시그널과 셸 종료 코드의 관계
시그널로 죽은 프로세스의 셸 종료 코드는 `128 + 시그널번호`다. 즉 `echo $?`가 `139`면 `139 - 128 = 11`이라 SIGSEGV, `134`면 `134 - 128 = 6`이라 SIGABRT다. 이 계산만으로도 core dump 없이 대략적인 크래시 원인을 알 수 있다.

### 프로그램 자신이 시그널을 걸어서 안티 디버깅/제어 흐름으로 쓰는 경우
- `sigaction()`/`signal()`로 SIGSEGV, SIGTRAP 핸들러를 등록해두고 일부러 잘못된 접근이나 `int3`를 실행시켜, 정상 실행에서는 핸들러가 흐름을 이어가지만 디버거가 붙어 있으면 디버거가 시그널을 먼저 가로채서 프로그램이 예상과 다르게 동작하게 만드는 패턴(시그널 기반 안티 디버깅/난독화)
- `PTRACE_TRACEME`(REV-0234)로 자기 자신을 트레이싱해서, 이미 다른 디버거가 붙어있으면 실패하는지 확인하는 패턴
- GDB는 기본적으로 `SIGSEGV`, `SIGABRT` 등에서 멈추지만 `SIGTRAP`은 자체적으로 브레이크포인트 구현에 쓰기 때문에 특별 취급한다 — 프로그램이 스스로 `SIGTRAP`을 발생시키면 GDB가 이를 자신의 브레이크포인트로 착각해 흐름이 꼬일 수 있다.

## 화면/코드에서 보이는 징후
```bash
$ ./chall
Segmentation fault (core dumped)
$ echo $?
139
```
```
(gdb) run
Starting program: /home/user/chall

Program received signal SIGSEGV, Segmentation fault.
0x0000000000401234 in vuln_func ()
```

## 가장 먼저 할 것
GDB로 다시 실행해서 정확히 어느 명령어에서 어떤 시그널로 죽는지 확인한다.
```bash
gdb ./chall
(gdb) run
```
크래시가 나면 GDB가 자동으로 멈추고 시그널 이름과 크래시 주소를 보여준다. 그 직후 바로 레지스터/스택을 확인한다.
```bash
(gdb) info registers
(gdb) x/5i $pc
(gdb) bt
```

## 단계별 절차

**1) 종료 코드로 1차 추정**
```bash
./chall; echo "exit=$?"
```
`128+N` 규칙으로 시그널 번호를 역산한다.

**2) GDB로 재현하며 정확한 시그널/위치 확인**
```bash
gdb ./chall
(gdb) run
(gdb) bt
(gdb) info registers
```

**3) 코어 덤프가 남았다면 사후 분석**
```bash
ulimit -c unlimited
./chall
gdb ./chall core
(gdb) bt
```
(코어 덤프 분석의 자세한 절차는 REV-0113 참고)

**4) 특정 시그널에서만 멈추도록 GDB 설정**
```bash
(gdb) handle SIGSEGV stop print
(gdb) handle SIGTRAP nostop noprint pass
```
프로그램이 정상적으로 자주 발생시키는 시그널(예: 스레드 관련 `SIGRTMIN` 계열)은 `nostop`으로 무시하고, 진짜 크래시 시그널만 걸리도록 조정하면 노이즈를 줄일 수 있다.

**5) 시그널을 커널이 아니라 프로세스 자신이 발생시키는지 확인**
```bash
strace -e trace=signal,rt_sigaction ./chall
```
`rt_sigaction` 호출이 보이면 프로그램이 직접 시그널 핸들러를 등록하고 있다는 뜻이니, 안티 디버깅/난독화 패턴을 의심하고 해당 핸들러 함수를 정적으로도 확인한다.

## 명령어/단축키
```bash
./chall; echo $?
ulimit -c unlimited
gdb ./chall
  (gdb) run
  (gdb) bt
  (gdb) info registers
  (gdb) handle SIGSEGV stop print
  (gdb) handle SIGTRAP nostop noprint pass
  (gdb) catch signal SIGSEGV
strace -e trace=signal ./chall
```

## 출력 해석
```
Program received signal SIGSEGV, Segmentation fault.
0x0000000000401234 in vuln_func ()
(gdb) info registers rip rdi
rip            0x401234  0x401234 <vuln_func+20>
rdi            0x4242424242424242  0x4242424242424242
```
`rdi`에 `0x4242424242424242`("BBBBBBBB")처럼 입력값이 그대로 들어간 게 보이면, 사용자 입력이 검증 없이 포인터/오프셋으로 쓰이다가 잘못된 주소를 참조해서 SIGSEGV가 난 전형적인 패턴이다.

```
Program terminated with signal SIGABRT, Aborted.
#0  0x00007ffff7... in __pthread_kill_implementation ()
#1  0x00007ffff7... in raise ()
#2  0x00007ffff7... in abort ()
#3  0x00007ffff7... in __libc_message ()
#4  0x00007ffff7... in __fortify_fail ()
#5  0x00007ffff7... in __stack_chk_fail ()
```
`__stack_chk_fail`이 백트레이스에 보이면 스택 카나리(REV-0442류 개념)가 깨져서 프로그램이 스스로 `abort()`를 호출한 것 — 스택 버퍼 오버플로우가 있었다는 강력한 증거다.

## 흔한 실수
- `Segmentation fault (core dumped)` 메시지만 보고 원인을 짐작만 하는 것 — 반드시 GDB `run`으로 재현해 정확한 크래시 주소와 레지스터 상태를 확인해야 한다.
- SIGABRT를 무조건 스택 카나리 문제로 단정하는 것 — glibc `malloc`/`free` 계열의 힙 무결성 검사 실패(`free(): invalid pointer` 등)도 SIGABRT로 이어지므로 백트레이스를 반드시 확인해야 한다.
- `handle SIGTRAP nostop`을 설정하지 않은 상태에서 자체적으로 `int3`를 실행하는 안티 디버깅 코드를 분석하다가, GDB가 매번 멈추는 걸 프로그램 크래시로 착각하는 것.
- 코어 덤프가 생성되지 않는 걸 보고 당황하는 것 — 기본적으로 `ulimit -c 0`(비활성)인 배포판이 많으므로 먼저 `ulimit -c unlimited`를 설정해야 한다(REV-0113 참고).

## 막혔을 때 다음 체크
- 코어 덤프 자체를 다루는 법이 더 궁금하다면 → REV-0113 Core dump와 크래시 지점 분석 기초
- 종료 코드로 크래시 원인을 더 체계적으로 좁히고 싶다면 → REV-0661 리눅스 프로세스 종료 코드(Exit Code)로 크래시 원인 좁히기
- `ptrace`와 시그널의 관계, 자체 디버거 구현이 궁금하다면 → REV-0672 ptrace 기반 자체 디버거 구현 개념 소개
- 이 크래시가 시그널 기반 안티 디버깅인지 의심된다면 → REV-0234 ptrace PTRACE_TRACEME 안티디버깅

## 미니 예제
```bash
$ ./chall
Segmentation fault (core dumped)
$ echo $?
139
$ python3 -c "print(139-128)"
11
```
`11`이 SIGSEGV이므로, 잘못된 메모리 접근으로 죽었다는 걸 코드를 열어보지 않고도 바로 알 수 있다. 이어서 GDB로 재현하면 정확한 크래시 위치까지 확인할 수 있다.

## 관련 글
- REV-0113 — Core dump와 크래시 지점 분석 기초
- REV-0661 — 리눅스 프로세스 종료 코드(Exit Code)로 크래시 원인 좁히기
- REV-0672 — ptrace 기반 자체 디버거 구현 개념 소개
- REV-0234 — ptrace PTRACE_TRACEME 안티디버깅
- REV-0186 — GDB break와 address breakpoint

## 출처/검증
- 시그널 번호/이름/기본 동작(SIGSEGV=11, SIGABRT=6, SIGTRAP=5, SIGFPE=8, SIGBUS=7, SIGILL=4, SIGSYS=31 등): Linux man-pages 프로젝트 `signal(7)` 문서 기준.
- 시그널로 종료된 프로세스의 셸 종료 코드가 `128+N`이 되는 규칙: POSIX 셸/Bash 공식 매뉴얼 종료 상태 설명 기준.
- `__stack_chk_fail` → `abort()` → SIGABRT로 이어지는 스택 카나리 실패 경로: glibc 소스(`stack_chk_fail.c`, `fortify_fail`) 동작 기준 (2026-09-08 검증).
