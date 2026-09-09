---
id: REV-0672
title: "ptrace 기반 자체 디버거 구현 개념 소개"
slug: "rev-0672-ptrace-custom-debugger-concept"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["ptrace", "PTRACE_TRACEME", "PTRACE_PEEKTEXT", "PTRACE_POKETEXT", "PTRACE_GETREGS", "자체 디버거"]
aliases: ["ptrace 디버거 만들기", "ptrace 시스템콜 개념", "int3 브레이크포인트 구현", "ptrace 기반 디버거 원리"]
symptom_keywords: ["gdb가 어떻게 브레이크포인트를 거는지 궁금함", "ptrace가 뭔지 모르겠음", "int3로 브레이크포인트를 직접 걸고 싶음", "PTRACE_TRACEME가 왜 안티디버깅에 쓰이는지 모름"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB를 포함한 리눅스의 모든 네이티브 디버거는 결국 `ptrace(2)` 시스템 콜 하나로 대상 프로세스를 정지시키고, 레지스터와 메모리를 읽고 쓰고, `0xCC`(`int3`) 바이트를 심어 브레이크포인트를 구현하는 방식으로 동작하며, 이 원리를 이해하면 GDB가 멈추지 않거나 안티 디버깅에 막힐 때 왜 그런지, 그리고 최소한의 디버거를 직접 짜서 우회할 수 있는지 판단할 수 있다.

## 언제 검색해야 하나
- "GDB가 대체 어떻게 프로세스를 멈추고 레지스터를 읽는 걸까"가 궁금할 때
- 안티 디버깅 코드에서 `ptrace(PTRACE_TRACEME, ...)`를 호출하는 걸 보고 이게 왜 디버거를 막는지 원리를 이해하고 싶을 때
- GDB/기존 도구가 안티 디버깅에 막혀서, 최소한의 커스텀 트레이서를 직접 짜서 우회해야 하는 상황일 때
- `int3` 브레이크포인트가 내부적으로 어떻게 원본 바이트를 저장하고 복원하는지 알고 싶을 때

## 핵심 개념

### ptrace(2) — 리눅스 디버깅의 유일한 표준 인터페이스
```c
long ptrace(enum __ptrace_request request, pid_t pid, void *addr, void *data);
```
`request`에 따라 동작이 완전히 달라지는 다목적 시스템 콜이다. 주요 요청 값들:
- `PTRACE_TRACEME`: "내 부모 프로세스가 나를 트레이싱하겠다"고 커널에 선언. 자식 프로세스가 `fork()` 직후, `execve()` 직전에 호출하는 것이 표준 패턴.
- `PTRACE_ATTACH` / `PTRACE_SEIZE`: 이미 실행 중인 프로세스에 트레이서로 붙기(GDB `attach <pid>`가 내부적으로 이걸 사용)
- `PTRACE_PEEKTEXT` / `PTRACE_PEEKDATA`: 대상 프로세스 메모리에서 워드(8바이트) 단위로 읽기
- `PTRACE_POKETEXT` / `PTRACE_POKEDATA`: 대상 프로세스 메모리에 워드 단위로 쓰기
- `PTRACE_GETREGS` / `PTRACE_SETREGS`: `struct user_regs_struct`(rax, rbx, rip, rsp 등 전체 레지스터 세트)를 읽고 쓰기
- `PTRACE_CONT`: 정지된 대상 프로세스를 계속 실행
- `PTRACE_SINGLESTEP`: 명령어 하나만 실행하고 다시 SIGTRAP으로 정지(RFLAGS의 트랩 플래그를 이용)
- `PTRACE_SYSCALL`: 다음 시스템 콜 진입/탈출 시점에 정지 (strace의 핵심 메커니즘)
- `PTRACE_DETACH`: 트레이싱 관계 해제

### 최소 디버거의 뼈대 — fork + execve + waitpid
```c
pid_t child = fork();
if (child == 0) {
    ptrace(PTRACE_TRACEME, 0, NULL, NULL);
    execve("./target", argv, envp);
} else {
    int status;
    waitpid(child, &status, 0);   // execve 직후 자동으로 SIGTRAP 발생, 여기서 멈춤
    // 이제 child는 정지 상태 — PEEKTEXT/POKETEXT/GETREGS 등을 자유롭게 사용 가능
    ptrace(PTRACE_CONT, child, NULL, NULL);
    waitpid(child, &status, 0);
}
```
자식이 `PTRACE_TRACEME`를 호출한 뒤 `execve`를 실행하면, 커널은 새 이미지로 교체되는 시점에 자동으로 `SIGTRAP`을 발생시켜 자식을 정지시킨다. 부모는 `waitpid()`로 이 정지를 감지하고, 그 순간부터 자식의 메모리/레지스터를 자유롭게 조작할 수 있다. GDB의 `run` 명령이 내부적으로 정확히 이 순서를 따른다.

### int3(0xCC) 소프트웨어 브레이크포인트의 원리
1. 브레이크포인트를 걸 주소의 원본 바이트 1개를 `PTRACE_PEEKTEXT`로 읽어서 백업해둔다.
2. 그 주소의 첫 바이트를 `0xCC`(`INT3` 명령어의 인코딩)로 `PTRACE_POKETEXT`를 이용해 덮어쓴다.
3. `PTRACE_CONT`로 실행을 재개한다.
4. CPU가 그 주소에 도달하면 `int3`를 실행하며 `SIGTRAP`을 발생시키고 프로세스가 커널에 의해 정지된다.
5. 트레이서는 `waitpid()`로 이를 감지하고, `PTRACE_GETREGS`로 레지스터를 읽는다. 이때 `rip`는 `int3` 명령어(1바이트) 실행 직후 위치, 즉 **원래 걸었던 주소보다 1 크다**.
6. 트레이서는 `rip`를 원래 주소로 되돌리고(`rip -= 1`), 백업해둔 원본 바이트를 `PTRACE_POKETEXT`로 복원해야 이후 정상 실행이 가능하다.
7. 다시 실행을 이어가려면 원본 바이트를 임시로 복원 → 한 스텝(`PTRACE_SINGLESTEP`) 실행 → 다시 `0xCC`로 덮어쓰는 절차가 필요하다(같은 지점에 브레이크포인트를 유지하려면).

GDB의 소프트웨어 브레이크포인트(`break *0x401234`)가 바로 이 절차를 자동으로 해준다. Pwndbg/GDB에서 `x/1xb 0x401234`로 브레이크포인트를 건 주소를 보면 `0xcc` 바이트가 실제로 박혀있는 걸 확인할 수 있다.

### 왜 PTRACE_TRACEME가 안티 디버깅에 쓰이나
`ptrace`는 한 프로세스에 트레이서가 **하나만** 붙을 수 있다는 제약이 있다. 만약 GDB가 이미 `PTRACE_ATTACH`로 대상 프로세스에 붙어있는 상태라면, 대상 프로세스 자신이 `ptrace(PTRACE_TRACEME, ...)`를 호출했을 때 이미 트레이서가 있으므로 이 호출이 실패(`-1` 반환, `errno = EPERM`)한다. 크래크미/안티 디버깅 코드는 이 실패 여부를 검사해서 "이미 디버거가 붙어있다"를 감지한다(자세한 내용은 REV-0234 참고).

## 화면/코드에서 보이는 징후
Ghidra/IDA 디컴파일 결과에서 다음과 같은 패턴이 보이면 자체적으로 ptrace를 안티 디버깅에 쓰는 코드다.
```c
long ret = ptrace(PTRACE_TRACEME, 0, NULL, NULL);
if (ret == -1) {
    puts("Debugger detected!");
    exit(1);
}
```

## 가장 먼저 할 것
크래크미가 `ptrace`를 호출하는지 먼저 정적으로 확인한다.
```bash
nm ./chall | grep -w ptrace     # 동적 링킹 + 심볼 있으면
objdump -d ./chall | grep -A2 "call.*ptrace@plt"
```
또는 동적으로 바로 확인한다.
```bash
strace -e trace=ptrace ./chall
```

## 단계별 절차 (최소 디버거 직접 짜보기 개념 흐름)

**1) 자식 프로세스 생성 및 트레이싱 선언**
`fork()` → 자식에서 `ptrace(PTRACE_TRACEME, ...)` → `execve()`

**2) 부모에서 execve 직후 정지 감지**
`waitpid(child, &status, 0)` — 이 시점 자식은 새 이미지로 교체되었지만 아직 진입점 실행 전.

**3) 원하는 주소에 브레이크포인트 심기**
`PTRACE_PEEKTEXT`로 원본 워드 백업 → 최하위 바이트만 `0xCC`로 바꾼 워드를 `PTRACE_POKETEXT`로 쓰기.

**4) 실행 재개 및 정지 대기**
`PTRACE_CONT` → `waitpid()` → `SIGTRAP` 확인.

**5) 레지스터 확인/조작**
`PTRACE_GETREGS`로 `struct user_regs_struct` 읽기 → `rip` 보정 → 필요하면 `PTRACE_SETREGS`로 값 변경.

**6) 원본 바이트 복원 후 계속 실행**
`PTRACE_POKETEXT`로 원본 복원 → `PTRACE_CONT` 또는 필요하면 `PTRACE_SINGLESTEP` 한 번 후 다시 `0xCC` 재설치.

## 명령어/단축키
```bash
strace -e trace=ptrace ./chall
nm ./chall | grep -w ptrace
objdump -d ./chall | grep -B2 -A2 "ptrace"
gdb ./chall
  (gdb) catch syscall ptrace
```
GDB에서 `catch syscall ptrace`를 걸어두면, 대상 프로그램이 스스로 `ptrace`를 호출하는 순간마다 GDB가 멈춰서 안티 디버깅 로직을 그 자리에서 관찰할 수 있다.

## 출력 해석
```
$ strace -e trace=ptrace ./chall
ptrace(PTRACE_TRACEME)                 = 0
+++ exited with 0 +++
```
반환값 `0`이면 트레이서가 없어 `PTRACE_TRACEME`가 성공한 것 — 정상 실행 상태다. 만약 GDB로 이미 attach된 상태에서 프로그램 자신이 `PTRACE_TRACEME`를 호출하면 `-1 EPERM (Operation not permitted)`가 찍히고, 이 값을 검사해 디버거 존재를 감지한다.

## 흔한 실수
- `ptrace` 요청 상수(`PTRACE_PEEKTEXT` 등)를 절대적인 것으로 착각하고 다른 아키텍처/OS에도 그대로 적용되리라 가정하는 것 — `ptrace`는 리눅스(및 BSD 계열) 고유 인터페이스이며 값과 의미가 플랫폼마다 다르다.
- 브레이크포인트를 걸고 원본 바이트 복원을 잊어버려서, `PTRACE_CONT` 이후 대상 프로세스가 `0xCC`(정의되지 않은 목적의 명령어가 아니라 항상 트랩을 발생시키는 명령)를 반복 실행하며 무한히 SIGTRAP만 반복하는 상황을 만드는 것.
- 트레이서가 이미 하나 붙어있는 프로세스에 GDB로 또 attach하려다 `ptrace: Operation not permitted` 에러를 보고 원인을 못 찾는 것 — 프로세스당 트레이서는 하나뿐이라는 제약을 기억해야 한다.
- `PTRACE_GETREGS`로 얻은 `rip`가 브레이크포인트를 건 주소보다 1 크다는 걸 깜빡하고 그대로 분석해서 엉뚱한 명령어를 보고 있다고 착각하는 것.

## 막혔을 때 다음 체크
- `ptrace` 기반 안티 디버깅 자체를 우회하는 구체적 방법이 궁금하다면 → REV-0234 ptrace PTRACE_TRACEME 안티디버깅
- 시그널(특히 SIGTRAP)의 의미를 더 정확히 이해하고 싶다면 → REV-0671 Linux 시그널(SIGSEGV 등)과 리버싱에서의 의미
- GDB의 표준 브레이크포인트 명령을 다시 짚고 싶다면 → REV-0186 GDB break와 address breakpoint
- seccomp가 `ptrace` 자체를 막는 경우도 있으니 → REV-0673 seccomp가 걸린 바이너리를 만났을 때 알아채는 법

## 미니 예제
```c
// 개념 스켈레톤 - 실제 프로덕션 코드 아님
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <sys/user.h>
#include <unistd.h>

int main(void) {
    pid_t child = fork();
    if (child == 0) {
        ptrace(PTRACE_TRACEME, 0, NULL, NULL);
        execl("./target", "target", NULL);
    } else {
        int status;
        waitpid(child, &status, 0);          // execve 직후 SIGTRAP
        struct user_regs_struct regs;
        ptrace(PTRACE_GETREGS, child, NULL, &regs);
        // regs.rip == 진입점 주소
        ptrace(PTRACE_CONT, child, NULL, NULL);
        waitpid(child, &status, 0);
    }
    return 0;
}
```
이 20줄 남짓한 코드가 GDB `run` 명령의 핵심 골격과 동일한 원리로 동작한다 — `fork` → `PTRACE_TRACEME` → `execve` → 부모의 `waitpid`.

## 관련 글
- REV-0234 — ptrace PTRACE_TRACEME 안티디버깅
- REV-0671 — Linux 시그널(SIGSEGV 등)과 리버싱에서의 의미
- REV-0186 — GDB break와 address breakpoint
- REV-0673 — seccomp가 걸린 바이너리를 만났을 때 알아채는 법
- REV-0112 — strace로 시스템 콜에서 힌트 찾기

## 출처/검증
- `ptrace(2)` 시스템 콜 시그니처, 요청 상수(`PTRACE_TRACEME`, `PTRACE_PEEKTEXT`, `PTRACE_POKETEXT`, `PTRACE_GETREGS`, `PTRACE_CONT`, `PTRACE_SINGLESTEP`, `PTRACE_SYSCALL` 등)와 동작: Linux man-pages 프로젝트 `ptrace(2)` 문서 기준.
- `int3`(0xCC) 소프트웨어 브레이크포인트의 SIGTRAP 발생 및 rip 보정(+1) 필요성: x86/x86-64 아키텍처 매뉴얼(인터럽트 3, INT3) 및 GDB/디버거 구현 표준 관행 기준 (2026-09-08 검증).
