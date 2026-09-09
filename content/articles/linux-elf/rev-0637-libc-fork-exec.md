---
id: REV-0637
title: "libc 함수 사전: fork exec 계열"
slug: "rev-0637-libc-fork-exec"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, strace, ltrace]
keywords: ["fork", "execve", "execv", "execl", "execlp", "vfork", "system", "wait", "waitpid", "프로세스 생성"]
aliases: ["fork exec 패턴", "execve 함수", "system 함수", "프로세스 복제", "자식 프로세스 리버싱"]
symptom_keywords: ["프로그램이 갑자기 다른 프로세스로 실행됨", "fork 이후 디버거가 부모만 따라감", "system 호출이 보임", "쉘이 튀어나옴"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`fork()`는 현재 프로세스를 그대로 복제해 부모/자식 두 개로 나누고, `execve()` 계열은 현재 프로세스의 메모리 이미지를 통째로 다른 프로그램으로 갈아치우며, 이 둘을 합친 `fork()+execve()` 패턴(또는 이를 감싼 `system()`)이 Linux에서 새 프로그램을 실행하는 표준 방법이다.

## 언제 검색해야 하나
- 코드에서 `fork()`, `execve()`, `system()`, `popen()` 호출을 발견해서 프로세스가 왜 갈라지거나 다른 프로그램으로 바뀌는지 이해해야 할 때
- GDB로 디버깅 중인데 `fork()` 이후 디버거가 자식/부모 중 어느 쪽을 계속 추적할지 헷갈릴 때
- `strace`/`ltrace` 출력에 `clone`, `execve`가 찍히는 이유를 알고 싶을 때

## 핵심 개념

### 함수 시그니처
```c
pid_t fork(void);
pid_t vfork(void);
int execve(const char *pathname, char *const argv[], char *const envp[]);
int execv(const char *path, char *const argv[]);
int execl(const char *path, const char *arg, ... /* NULL로 끝나야 함 */);
int execvp(const char *file, char *const argv[]);   // PATH 환경변수에서 file 탐색
int execlp(const char *file, const char *arg, ...);
int system(const char *command);
pid_t wait(int *wstatus);
pid_t waitpid(pid_t pid, int *wstatus, int options);
```

### fork — 프로세스 복제
`fork()`는 호출 시점의 메모리(코드/데이터/스택/힙)를 거의 그대로 복사한 자식 프로세스를 만든다. **반환값이 부모와 자식에서 다르다**는 점이 핵심이다:
- 부모 프로세스에서는 자식의 PID(양수)를 반환
- 자식 프로세스에서는 `0`을 반환
- 실패 시 부모에서만 `-1` 반환

즉 소스 코드에서는 `fork()` 호출이 한 줄이지만 실행 후에는 반환 지점 이후 코드가 **두 프로세스에서 각각 실행**된다. 흔한 패턴:
```c
pid_t pid = fork();
if (pid == 0) {
    // 자식: 여기서 exec 계열 호출
} else if (pid > 0) {
    // 부모: wait() 등으로 자식을 기다림
}
```
실제 리눅스 커널에서 `fork`는 내부적으로 `clone` 시스템 콜(플래그 조합)로 구현되어 있어, `strace`에서는 `clone(...)`으로 찍히는 경우가 많다.

### exec 계열 — 프로세스 이미지 교체
`exec*` 함수들은 **성공하면 절대 반환하지 않는다.** 현재 프로세스의 코드/데이터/스택을 새 실행 파일 것으로 완전히 덮어쓰고 그 프로그램의 `_start`부터 실행을 시작하기 때문이다(PID는 그대로 유지됨). 실패했을 때만 `-1`을 반환하며 `errno`가 설정된다. 접미사 규칙:
- `l`(list): 인자를 가변 인자로 나열, `NULL`로 종료 — `execl("/bin/ls", "ls", "-l", NULL)`
- `v`(vector): 인자를 `argv[]` 배열로 전달
- `p`(path): 파일 이름만 주면 `PATH` 환경변수에서 탐색
- `e`(environ): 별도의 `envp[]`를 명시적으로 지정 (`execve`, `execle`)

### system() — fork+exec를 감싼 래퍼
```c
int system(const char *command);
```
`system()`은 내부적으로 `fork()`한 뒤 자식에서 `execve("/bin/sh", ["sh", "-c", command, NULL], environ)`를 호출하고, 부모는 자식이 끝날 때까지 기다린다. 이 때문에 **`system` 함수 주소만 알아도 인자로 `"/bin/sh"`를 넘겨 셸을 얻는 것**이 pwn 문제의 대표적인 목표(ret2libc)다. 리버싱 관점에서는 바이너리에 `system@plt` 호출이 있으면 그 인자 문자열이 무엇인지가 가장 먼저 확인할 지점이다.

### wait / waitpid — 자식 종료 대기
부모가 자식의 종료를 기다리지 않으면 자식이 좀비(zombie) 프로세스로 남는다. `waitpid(pid, &status, 0)`로 특정 자식을, `wait(&status)`로 아무 자식이나 기다릴 수 있다. `WIFEXITED(status)`, `WEXITSTATUS(status)` 매크로로 종료 상태를 해석한다.

## 화면/코드에서 보이는 징후
- 디컴파일 코드에 `pid = fork();` 후 `if (pid == 0)` 분기
- `system("/bin/sh")` 또는 `system(sprintf로 만든 커맨드 문자열)` 호출
- `strace` 출력에 `clone(...)`, 이어서 `execve("/bin/sh", ...)`가 찍힘
- 실행 중 갑자기 셸 프롬프트가 나타남 (system이나 execve("/bin/sh") 성공)

## 가장 먼저 할 것
`fork`/`exec`/`system` 호출이 보이면, 그 직전/직후에 어떤 문자열(`argv[0]`, `command`)이 전달되는지부터 확인한다. GDB로는 해당 `call` 직전에 브레이크포인트를 걸고 인자 레지스터(x64는 `rdi`)를 읽으면 된다.

## 단계별 절차

**1) fork 이후 디버거 추적 대상 설정**
```gdb
set follow-fork-mode child   # 또는 parent (기본값)
set detach-on-fork off       # 부모/자식 둘 다 붙잡아두고 싶을 때
```

**2) fork/exec 시점에 자동으로 멈추기**
```gdb
catch fork
catch exec
run
```
`catch fork`는 `fork()`(또는 `clone`) 호출이 발생하는 순간, `catch exec`는 `execve`가 성공적으로 이미지 교체를 하기 직전 시점에 프로그램을 멈춘다.

**3) system/execve 인자 확인**
```gdb
break system
run
x/s $rdi
```
`x/s $rdi`는 x64 SysV 호출 규약(REV-0106)의 첫 번째 인자를 문자열로 출력한다.

**4) strace로 실제 커널 레벨 확인**
```bash
strace -f ./chall
```
`-f`는 `fork`로 생성된 자식 프로세스까지 함께 추적한다(REV-0112 참고).

## 명령어/단축키
```bash
strace -f ./chall
ltrace -f ./chall
```
GDB: `catch fork`, `catch exec`, `set follow-fork-mode child|parent`, `set detach-on-fork on|off`

## 출력 해석
- `strace`에서 `execve("/bin/sh", ["sh", "-c", "id"], 0x...)  = 0`이면 `/bin/sh -c id` 형태로 `system("id")`가 실제로 호출됐다는 뜻.
- `fork()` 반환값을 GDB에서 `finish` 후 `print $rax`로 보면, 부모 프로세스 컨텍스트에서는 자식 PID(양수), 자식 컨텍스트에서는 `0`이 보인다 — 어느 쪽을 보고 있는지 `info inferiors`로 항상 확인한다.

## 흔한 실수
- `fork()` 이후 `if (pid == 0)`을 부모/자식 어느 쪽이 실행하는지 반대로 착각하는 것 — **자식이 0, 부모가 양수**다.
- `exec*` 계열이 실패 시에만 반환한다는 것을 몰라서, 반환 이후 코드가 "성공했을 때의 다음 단계"라고 착각하는 것 — 성공하면 그 지점에 도달하지 않는다.
- GDB로 `fork`를 넘어 자식을 추적하고 싶은데 기본 설정(`follow-fork-mode parent`)을 그대로 둬서 자식이 그냥 실행되어 버리는 것.
- `execl`류 가변 인자 목록 끝에 `NULL`을 빠뜨리는 실수 — 소스 코드에서 이런 버그가 보이면 정의되지 않은 동작으로 크래시의 원인일 수 있다.

## 막혔을 때 다음 체크
- 인자 전달 규약 자체가 헷갈리면 → REV-0106 SysV AMD64 Calling Convention.
- 환경변수를 자식에게 어떻게 물려주는지 궁금하면 → REV-0636 libc 함수 사전: getenv setenv 환경변수 함수.
- 커널 시스템 콜 레벨에서 직접 보고 싶다면 → REV-0645 시스템콜 번호 빠른 참조표, REV-0112 strace.

## 미니 예제
```c
if (fork() == 0) {
    execl("/bin/sh", "sh", NULL);
    _exit(1);   // execl이 실패했을 때만 도달
}
wait(NULL);
```
```
$ strace -f ./chall
clone(child_stack=NULL, flags=...) = 1234
[pid  1234] execve("/bin/sh", ["sh"], 0x7ffd...) = 0
[pid  1234] ...
```
자식 프로세스(PID 1234)가 `/bin/sh`로 이미지를 교체한 것이 `execve` 반환값 `0`(성공)으로 확인된다.

## 관련 글
- REV-0106 — SysV AMD64 Calling Convention
- REV-0636 — libc 함수 사전: getenv setenv 환경변수 함수
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0645 — 시스템콜 번호(syscall number) 빠른 참조표(x86-64)

## 출처/검증
- `fork`/`vfork`/`exec*`/`system`/`wait`/`waitpid` 시그니처와 반환값 규약: POSIX.1 및 glibc 표준 라이브러리 함수 정의 기준.
- `system()`이 내부적으로 `/bin/sh -c command`를 실행한다는 동작: glibc `stdlib/system.c` 구현 기준 (2026-09-08 검증).
- GDB `catch fork`/`catch exec`/`set follow-fork-mode`: GDB 공식 매뉴얼 "Debugging Programs with Multiple Processes" 섹션 기준.
