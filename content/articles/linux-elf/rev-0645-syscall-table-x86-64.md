---
id: REV-0645
title: "시스템콜 번호(syscall number) 빠른 참조표(x86-64)"
slug: "rev-0645-syscall-table-x86-64"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [strace, GDB, Pwndbg]
keywords: ["syscall number", "syscall_64.tbl", "rax syscall", "int 0x80", "syscall 명령어", "시스템콜 번호"]
aliases: ["시스템콜 번호표", "syscall 번호 x64", "syscall 테이블", "리눅스 시스템콜 목록", "쉘코드 syscall 번호"]
symptom_keywords: ["rax에 이상한 숫자가 들어감", "syscall 명령어 인자 순서를 모르겠음", "쉘코드에서 syscall 번호가 필요함", "32비트 64비트 syscall 번호가 다름"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x86-64 리눅스에서 시스템 콜은 `rax`에 번호를 넣고 `syscall` 명령어로 커널에 진입하며, 인자는 `rdi, rsi, rdx, r10, r8, r9` 순서로 전달되고(함수 호출 규약과 달리 4번째 인자가 `rcx`가 아니라 `r10`), 이 번호 체계는 32비트(`int 0x80`) 시절과 완전히 다르므로 쉘코드/디스어셈블리에서 `rax` 값만 보고 바로 어떤 syscall인지 알아채려면 이 표를 참고해야 한다.

## 언제 검색해야 하나
- 디스어셈블리에서 `mov eax, N` 다음에 `syscall` 명령어가 나오는데 그 번호 `N`이 무슨 시스템 콜인지 모를 때
- 쉘코드를 직접 작성/분석하면서 `execve`, `read`, `write` 등의 syscall 번호가 필요할 때
- `strace` 없이 정적 분석만으로 바이너리가 어떤 시스템 콜을 쓰는지 추정해야 할 때

## 핵심 개념

### 호출 규약 — 함수 호출과 다르다
```
syscall 번호   : rax
인자 1~6      : rdi, rsi, rdx, r10, r8, r9
반환값        : rax  (음수면 -errno)
```
일반 SysV AMD64 함수 호출 규약(REV-0106)의 인자 순서(`rdi, rsi, rdx, rcx, r8, r9`)와 거의 같지만, **4번째 인자가 `rcx`가 아니라 `r10`**이라는 점이 유일하고 중요한 차이다. 이는 `syscall` 명령어 자체가 실행되면서 반환 주소를 `rcx`에, 플래그를 `r11`에 자동으로 저장(x86-64 `SYSCALL`/`SYSRET` 메커니즘)해 `rcx`/`r11`이 훼손되기 때문에, 커널 ABI에서 4번째 인자 자리로 `rcx` 대신 `r10`을 쓰도록 정했다.

### syscall vs int 0x80
64비트 모드에서는 `syscall` 명령어(빠른 시스템 콜 진입, `SYSCALL`/`SYSRET` 전용 명령)를 쓰는 것이 표준이다. `int 0x80`도 64비트 프로세스에서 여전히 동작하긴 하지만 **32비트 syscall 번호 체계**를 사용하게 되므로 완전히 다른 번호 매핑이 적용된다 — 예를 들어 32비트에서 `write`는 4번이지만 64비트 `syscall` 체계에서는 1번이다. 쉘코드를 작성/분석할 때 이 둘을 섞으면 엉뚱한 시스템 콜이 호출된다.

### 자주 쓰이는 x86-64 syscall 번호

| 번호 | 이름 | 인자(간략) |
|---|---|---|
| 0 | `read` | fd, buf, count |
| 1 | `write` | fd, buf, count |
| 2 | `open` | pathname, flags, mode |
| 3 | `close` | fd |
| 4 | `stat` | pathname, statbuf |
| 5 | `fstat` | fd, statbuf |
| 8 | `lseek` | fd, offset, whence |
| 9 | `mmap` | addr, length, prot, flags, fd, offset |
| 10 | `mprotect` | addr, len, prot |
| 11 | `munmap` | addr, length |
| 12 | `brk` | addr |
| 13 | `rt_sigaction` | signum, act, oldact |
| 21 | `access` | pathname, mode |
| 22 | `pipe` | pipefd[2] |
| 32 | `dup` | oldfd |
| 33 | `dup2` | oldfd, newfd |
| 39 | `getpid` | (없음) |
| 41 | `socket` | domain, type, protocol |
| 42 | `connect` | sockfd, addr, addrlen |
| 56 | `clone` | flags, stack, ... |
| 57 | `fork` | (없음) |
| 58 | `vfork` | (없음) |
| 59 | `execve` | pathname, argv, envp |
| 60 | `exit` | status |
| 61 | `wait4` | pid, wstatus, options, rusage |
| 62 | `kill` | pid, sig |
| 63 | `uname` | buf |
| 101 | `ptrace` | request, pid, addr, data |
| 231 | `exit_group` | status |
| 257 | `openat` | dirfd, pathname, flags, mode |

이 번호들은 커널 소스의 `arch/x86/entry/syscalls/syscall_64.tbl`에 정의되어 있으며, 커널 버전이 올라가도 기존 번호는 하위 호환을 위해 거의 바뀌지 않고 새 syscall이 뒤쪽 번호로 계속 추가되는 방식이다(예: `openat`=257은 2.6 커널 이후 추가분).

### exit vs exit_group
`exit`(60)은 **호출한 스레드만** 종료시키고, `exit_group`(231)은 **프로세스의 모든 스레드**를 한 번에 종료시킨다. libc의 `exit()`/`_exit()`은 실제로 `exit_group` syscall을 호출하도록 구현되어 있는 경우가 일반적이라, 쉘코드에서 단일 스레드 프로그램을 깔끔히 끝내고 싶을 때도 관례적으로 `exit_group`(231)을 많이 쓴다.

## 화면/코드에서 보이는 징후
- 디스어셈블리에 `mov eax, 0x3b`(59, execve) 직후 `syscall` 명령어
- 쉘코드 헥스덤프에 `48 c7 c0 3b 00 00 00`(mov rax, 0x3b) 같은 패턴
- `strace` 출력의 함수 이름은 이미 번호가 이름으로 변환되어 나오므로, 정적 분석에서 숫자만 보이는 상황과 대조해서 사용

## 가장 먼저 할 것
`syscall` 명령어 직전의 `rax` 설정 값을 확인하고, 위 표(또는 `ausyscall`, `/usr/include/asm-generic/unistd.h`)에서 번호를 이름으로 변환한다.

## 단계별 절차

**1) 디스어셈블리에서 syscall 직전 rax 값 확인**
```bash
objdump -d ./shellcode.bin -b binary -m i386:x86-64
```

**2) 번호를 이름으로 변환 (시스템에 ausyscall이 있는 경우)**
```bash
ausyscall x86_64 59
# Result: execve
```

**3) GDB로 실행 중 확인**
```gdb
catch syscall
run
```
`syscall` 진입 시점에 자동으로 멈추고, GDB가 `rax` 값을 보고 이름까지 함께 알려준다(`Catchpoint 1 (call to syscall execve)`).

**4) strace로 동적 확인(비교용)**
```bash
strace ./chall
```

## 명령어/단축키
```bash
ausyscall x86_64 <번호>
ausyscall x86_64 --dump | less   # 전체 표
strace ./chall
```
GDB: `catch syscall`, `catch syscall <이름>`, `catch syscall <번호>`

## 출력 해석
```
mov    eax, 0x3b        ; rax = 59 = execve
lea    rdi, [rip+0x10]  ; "/bin/sh"
xor    esi, esi         ; argv = NULL
xor    edx, edx         ; envp = NULL
syscall
```
번호 `0x3b`(59)와 인자 레지스터(`rdi`=경로, `rsi`=argv, `rdx`=envp)를 대조하면 이 코드가 정확히 `execve("/bin/sh", NULL, NULL)`을 호출하는 전형적인 쉘코드 패턴임을 알 수 있다.

## 흔한 실수
- 32비트 syscall 번호(`int 0x80` 체계)와 64비트 syscall 번호(`syscall` 체계)를 그대로 섞어 쓰는 것 — 아키텍처와 진입 방식이 다르면 번호표 자체가 다르다.
- `syscall` 4번째 인자를 함수 호출 규약처럼 `rcx`에 넣는 것 — 커널 syscall ABI에서는 반드시 `r10`을 써야 한다(`rcx`는 `syscall` 명령어가 반환 주소 저장용으로 덮어씀).
- `exit`(60)과 `exit_group`(231)을 구분하지 않고 아무거나 써서, 멀티스레드 프로그램에서 의도치 않게 한 스레드만 종료되는 상황을 만드는 것.
- 커널 버전이 다르면 번호가 다를 거라 오해하는 것 — 리눅스는 ABI 안정성을 위해 기존 syscall 번호를 거의 재배치하지 않는다(새 syscall만 계속 뒤에 추가).

## 막혔을 때 다음 체크
- `syscall`이 실제로 무엇을 하는 명령어인지(모드 전환, SYSCALL/SYSRET 메커니즘)가 궁금하면 → Assembly Dictionary의 SYSCALL 항목 참고.
- 인자 전달 규약을 함수 호출과 정확히 비교하고 싶으면 → REV-0106 SysV AMD64 Calling Convention.
- `catch syscall`로 실행 중 잡아내는 방법이 더 궁금하면 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak).

## 미니 예제
```asm
; write(1, msg, 13); exit(0);
mov rax, 1        ; syscall number: write
mov rdi, 1        ; fd = stdout
lea rsi, [rip+msg]
mov rdx, 13
syscall
mov rax, 60       ; syscall number: exit
xor rdi, rdi
syscall
msg: db "Hello, CTF!\n"
```
첫 번째 `syscall` 전 `rax=1`이므로 `write(1, msg, 13)`, 두 번째 `syscall` 전 `rax=60`이므로 `exit(0)`이 실행된다.

## 관련 글
- REV-0106 — SysV AMD64 Calling Convention
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0637 — libc 함수 사전: fork exec 계열

## 출처/검증
- x86-64 syscall 번호 및 커널 소스 위치(`arch/x86/entry/syscalls/syscall_64.tbl`): Linux 커널 공식 소스 기준, 다수의 공개 syscall 레퍼런스(filippo.io/linux-syscall-table, x64.syscall.sh) 교차 확인 (2026-09-08 검증).
- `syscall` 명령어의 `rdi, rsi, rdx, r10, r8, r9` 인자 전달 규약 및 4번째 인자가 `r10`인 이유(`rcx`/`r11` 훼손): System V AMD64 ABI 및 리눅스 커널 syscall 진입 규약(`SYSCALL`/`SYSRET` 관련) 문서 기준.
- `exit`(60) vs `exit_group`(231) 차이: Linux man-pages `exit(2)`, `exit_group(2)` 기준.
