---
id: REV-0673
title: "seccomp가 걸린 바이너리를 만났을 때 알아채는 법"
slug: "rev-0673-seccomp-detection"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, strace, readelf]
keywords: ["seccomp", "seccomp-bpf", "prctl PR_SET_SECCOMP", "SECCOMP_MODE_FILTER", "libseccomp", "SIGSYS", "seccomp-tools"]
aliases: ["seccomp 탐지", "seccomp 샌드박스 확인법", "syscall 필터링 확인", "왜 갑자기 프로세스가 죽는지(syscall 관련)"]
symptom_keywords: ["특정 syscall만 호출하면 프로세스가 즉시 죽음", "strace 도중 killed by SIGSYS가 뜸", "execve나 open이 막힌 것 같음", "orw 문제인데 open이 안 먹힘"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
seccomp(secure computing mode)는 프로세스가 호출할 수 있는 시스템 콜 종류를 커널 레벨에서 제한하는 샌드박스 기능이며, CTF pwn 문제에서 `open`/`execve` 같은 특정 syscall만 쓰게 하거나 아예 쉘 실행을 막으려고 자주 걸어두므로, 특정 syscall 근처에서만 프로세스가 죽거나 `strace` 로그가 `+++ killed by SIGSYS +++`로 끝나면 seccomp부터 의심해야 한다.

## 언제 검색해야 하나
- pwn 문제를 풀다가 셸을 땄다고 생각했는데 `execve`만 호출하면 프로세스가 바로 죽을 때
- `strace ./chall` 로그 끝부분이 정상 종료가 아니라 `+++ killed by SIGSYS (Bad system call) +++`로 끝날 때
- 문제 이름이나 설명에 "orw"(open-read-write), "sandbox", "filter" 같은 단어가 있을 때
- 바이너리에 `prctl`이나 `seccomp` 심볼, `libseccomp.so` 의존성이 보일 때
- gdb로 `attach`했는데 seccomp 자체가 `ptrace`를 막아서 이상하게 동작할 때

## 핵심 개념

### seccomp란 무엇인가
seccomp는 리눅스 커널 기능으로, 프로세스가 실행할 수 있는 시스템 콜의 화이트리스트/블랙리스트를 BPF(Berkeley Packet Filter) 프로그램 형태로 커널에 등록한다. 등록된 필터를 벗어난 syscall을 호출하면 커널은 그 시점에 즉시 프로세스를 죽이거나(`SECCOMP_RET_KILL`), `errno`만 채워서 리턴시키거나(`SECCOMP_RET_ERRNO`), 트레이서에게 알리는(`SECCOMP_RET_TRACE`) 등 미리 정한 동작을 취한다. 리눅스 컨테이너(Docker), 브라우저 샌드박스, 그리고 CTF pwn 문제의 익스플로잇 난이도를 조절하는 용도로 널리 쓰인다.

### 두 가지 활성화 경로
1. **`prctl(PR_SET_SECCOMP, SECCOMP_MODE_STRICT, ...)`**: `read`/`write`/`exit`/`sigreturn` 4개 syscall만 허용하는 가장 엄격한 모드. 요즘 CTF에서는 거의 안 쓴다.
2. **`prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog)`** 또는 `seccomp(SECCOMP_SET_MODE_FILTER, ...)`: BPF 필터로 세밀하게 허용/차단 syscall을 지정하는 방식. CTF pwn 문제 대부분이 이 방식이며, 보통 `libseccomp`(`seccomp_init`, `seccomp_rule_add`, `seccomp_load` 함수들)를 이용해 필터를 빌드한다.

### 왜 CTF pwn 문제에 seccomp를 거는가
셸 코드를 획득한 공격자가 `execve("/bin/sh", ...)`로 바로 쉘을 따는 것을 막기 위해서다. `open`, `read`, `write`는 허용하고 `execve`, `execveat`, `fork` 등은 차단하는 필터를 걸면, 공격자는 어쩔 수 없이 열려있는 syscall만으로 플래그 파일을 직접 `open`+`read`+`write`(orw) 하는 셸코드를 짜야 한다. 이런 문제를 흔히 "orw 문제"라고 부른다.

### seccomp가 ptrace/디버깅에 미치는 영향
seccomp 필터가 `ptrace` syscall 자체를 차단하거나, `PR_SET_NO_NEW_PRIVS`와 함께 설정된 경우 GDB의 `attach`나 `PTRACE_TRACEME`(REV-0672 참고)가 실패할 수 있다. 또한 필터가 걸린 상태에서 GDB로 이미 attach해서 실행 중이면, 대상 프로세스가 차단된 syscall을 호출하는 순간 `SIGSYS`를 받아 그 지점에서 바로 멈추므로, 이 자체가 "여기서 막힌 syscall이 있다"는 훌륭한 단서가 된다.

## 화면/코드에서 보이는 징후
- `strace ./chall` 로그가 특정 syscall 호출 직후 `+++ killed by SIGSYS +++`로 끝남
- `/proc/<pid>/status`에서 `Seccomp:` 필드가 `0`이 아님(`1`=strict, `2`=filter)
- IDA/Ghidra 디컴파일에 `prctl(38, 1, ...)` 또는 `seccomp_init`, `seccomp_rule_add`, `seccomp_load` 호출이 보임
- `ldd ./chall`에 `libseccomp.so.2`가 의존성으로 나열됨
- GDB로 실행 중 특정 syscall 호출 지점에서 갑자기 `Program terminated with signal SIGSYS`가 뜸

## 가장 먼저 할 것
바이너리에 `seccomp`나 `prctl` 심볼이 있는지 정적으로 먼저 확인한다.
```bash
nm ./chall 2>/dev/null | grep -i seccomp
strings ./chall | grep -i seccomp
ldd ./chall | grep -i seccomp
```
아무것도 안 나오면 실행 중 syscall 로그로 SIGSYS 여부를 확인한다.

## 단계별 절차
1. `nm`/`strings`/`ldd`로 seccomp 관련 심볼·라이브러리 유무 확인
2. `strace -f ./chall`로 실행하며 어느 syscall 직후 죽는지, `+++ killed by SIGSYS +++`가 나오는지 확인
3. 심볼이 스트립됐거나 확실하지 않으면 `seccomp-tools`(Ruby gem, CTF 커뮤니티 표준 도구)로 필터 자체를 덤프
   ```bash
   seccomp-tools dump ./chall
   ```
   이 명령은 실제로 프로그램을 한 번 실행시켜 등록된 BPF 필터를 디스어셈블해서 허용/차단되는 syscall 목록을 사람이 읽을 수 있게 보여준다.
4. 덤프 결과에서 `ALLOW`로 표시된 syscall 목록을 확인 — 익스플로잇에서 쓸 수 있는 syscall이 이것으로 제한된다
5. `execve` 계열이 막혀 있다면 orw 셸코드(open→read→write로 플래그 파일 직접 읽기) 방향으로 전략을 바꾼다
6. GDB로 분석해야 한다면 `catch syscall`로 실제 호출 시점을 관찰하되, ptrace 자체가 막혀 있는지도 `strace -e trace=ptrace ./chall`로 먼저 확인

## 명령어/단축키
```bash
nm ./chall | grep -i seccomp
strings ./chall | grep -i seccomp
ldd ./chall
strace -f ./chall
seccomp-tools dump ./chall
cat /proc/<pid>/status | grep Seccomp
```
```gdb
catch syscall
catch signal SIGSYS
```

## 출력 해석
`seccomp-tools dump` 출력 예:
```
 line  CODE  JT   JF      K
=================================
 0000: 0x20 0x00 0x00 0x00000004  A = arch
 0001: 0x15 0x00 0x0c 0xc000003e  if (A != ARCH_X86_64) goto 0014
 0002: 0x20 0x00 0x00 0x00000000  A = sys_number
 0003: 0x35 0x00 0x01 0x40000000  if (A < 0x40000000) goto 0005
 ...
 0009: 0x15 0x08 0x00 0x0000003b  if (A == execve) goto 0018
 0018: 0x06 0x00 0x00 0x00000000  return KILL
```
`if (A == execve) goto 0018`처럼 특정 syscall 번호를 비교한 뒤 `return KILL`로 이어지면 그 syscall이 차단된 것이다. `return ALLOW`로 이어지는 syscall만 익스플로잇에서 사용 가능하다.

`/proc/<pid>/status`의 `Seccomp:\t2`는 필터 모드가 활성화됐다는 뜻이고, `Seccomp:\t0`은 seccomp가 걸려 있지 않다는 뜻이다.

## 흔한 실수
- SIGSYS를 SIGSEGV(세그폴트)로 오해해서 스택/힙 손상 쪽만 파다가 시간을 낭비하는 것 — `strace` 마지막 줄의 시그널 이름을 꼭 확인해야 한다.
- seccomp 필터가 `open`은 허용하지만 특정 플래그(`O_RDWR` 등)나 파일 디스크립터 번호까지는 검사하지 못한다는 점을 이용하지 못하고, syscall 이름 차단만 보고 포기하는 것 — 필터는 보통 syscall 번호 단위로만 걸리므로 인자 조건까지 우회 여지가 있는지 덤프를 자세히 봐야 한다.
- `seccomp-tools` 없이 손으로 BPF 바이트코드를 해석하려다 시간을 다 쓰는 것 — 표준 도구를 먼저 설치해서 쓰는 편이 훨씬 빠르다.
- 필터가 `ptrace`도 막아놨는데 GDB `attach`가 실패하는 이유를 seccomp가 아니라 `ptrace_scope` 설정 문제로 착각하는 것(REV-0692 참고, 원인이 다를 수 있으니 둘 다 확인).

## 막혔을 때 다음 체크
- 컨테이너 환경에서 seccomp 프로파일이 별도로 적용된 경우가 궁금하면 → REV-0674 컨테이너(Docker) 안에서 배포된 문제 바이너리 분석 시 주의점
- ptrace 자체의 원리와 seccomp가 이를 어떻게 막는지 더 알고 싶다면 → REV-0672 ptrace 기반 자체 디버거 구현 개념 소개
- strace 결과를 syscall 종류별로 걸러서 보는 방법이 필요하면 → REV-0662 strace 결과를 파일/네트워크 시스템콜로 필터링해서 노이즈 줄이기
- syscall 번호와 이름을 빠르게 대조하고 싶다면 → REV-0645 시스템콜 번호(syscall number) 빠른 참조표(x86-64)

## 미니 예제
```bash
$ strace ./chall
...
open("/flag", O_RDONLY)                = -1 (Bad system call)
+++ killed by SIGSYS +++

$ seccomp-tools dump ./chall
 line  CODE  JT   JF      K
=================================
 ...
 0009: 0x15 0x00 0x01 0x00000002  if (A == open) goto 0011
 0010: 0x06 0x00 0x00 0x7fff0000  return ALLOW
 0011: 0x15 0x08 0x00 0x0000003b  if (A == execve) goto 0020
 0020: 0x06 0x00 0x00 0x00000000  return KILL
```
이 문제는 `open`은 허용하지만(오래된 32비트 `open` 번호가 아닌 실제 아키텍처의 `openat`을 안 넣어서 `open` 자체가 이미 실패하는 흔한 실수 사례) `execve`는 명시적으로 차단하고 있음을 덤프로 바로 확인할 수 있다. 이 경우 `openat`으로 파일을 열고 `read`/`write`로 내용을 출력하는 셸코드를 작성해야 한다.

## 관련 글
- REV-0672 — ptrace 기반 자체 디버거 구현 개념 소개
- REV-0674 — 컨테이너(Docker) 안에서 배포된 문제 바이너리 분석 시 주의점
- REV-0662 — strace 결과를 파일/네트워크 시스템콜로 필터링해서 노이즈 줄이기
- REV-0645 — 시스템콜 번호(syscall number) 빠른 참조표(x86-64)

## 출처/검증
- seccomp/seccomp-bpf 동작 방식(`prctl(PR_SET_SECCOMP)`, `SECCOMP_MODE_STRICT`/`SECCOMP_MODE_FILTER`, BPF 필터, `SECCOMP_RET_KILL`/`SECCOMP_RET_ERRNO`/`SECCOMP_RET_TRACE`): Linux 커널 공식 문서(Documentation/userspace-api/seccomp_filter.rst) 및 `seccomp(2)` man page 기준.
- `seccomp-tools`의 `dump` 서브커맨드와 BPF 디스어셈블 출력 형식: seccomp-tools 공식 저장소(문서/README) 기준 (2026-09-09 검증).
