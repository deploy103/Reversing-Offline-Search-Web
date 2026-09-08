---
id: REV-0112
title: "strace로 시스템 콜에서 힌트 찾기"
slug: "rev-0112-strace-basics"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [strace, GDB]
keywords: ["strace", "system call trace", "시스템 콜 추적", "ptrace", "동적 분석 도구"]
aliases: ["strace 사용법", "strace 명령어", "strace 출력 해석", "ptrace 기반 추적"]
symptom_keywords: ["어떤 파일을 여는지 모르겠음", "strace가 프로그램을 멈추게 함", "ptrace 안티디버깅 의심", "strace 아무것도 안찍힘"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`strace ./chall`은 프로그램이 커널에 요청하는 모든 **시스템 콜**(`open`, `read`, `write`, `mmap`, `execve` 등)을 그대로 화면에 출력해주는 도구로, 라이브러리 함수 이름과 무관하게 "실제로 이 프로그램이 파일/네트워크/프로세스에 어떤 요청을 하는지"를 가장 낮은 레벨에서 확인할 때 쓴다.

## 언제 검색해야 하나
- 프로그램이 어떤 파일을 열려고 시도하는지(`flag.txt` 같은 힌트 파일 경로) 확인하고 싶을 때
- `ltrace`(REV-0111)가 정적 링킹 바이너리에서 아무것도 안 잡아줄 때, 대체 수단이 필요할 때
- 실제로 몇 바이트가 `read`/`write`되는지, `stdin`/`stdout`이 어떻게 쓰이는지 커널 레벨에서 확인하고 싶을 때
- 바이너리가 `ptrace(PTRACE_TRACEME, ...)`를 호출해서 자기 자신을 디버거로부터 보호하려는(안티디버깅) 낌새가 있는지 확인하고 싶을 때

## 핵심 개념

### strace가 하는 일 — ptrace로 커널 요청을 가로챔
`strace`는 리눅스 커널이 제공하는 `ptrace(2)` 시스템 콜을 이용해 대상 프로세스에 붙어(attach), 그 프로세스가 커널에 시스템 콜을 요청할 때마다(진입/종료 시점) 멈춰서 인자와 반환값을 가로채 출력한다. `ltrace`가 사용자 공간의 라이브러리 함수 호출을 보는 것과 달리, `strace`는 훨씬 더 낮은 레벨인 **커널 경계**를 관찰한다. 이 때문에 정적/동적 링킹 여부와 무관하게, 어떤 프로그램이든 결국 파일을 읽거나 네트워크를 쓰려면 시스템 콜을 거칠 수밖에 없으므로 `strace`는 항상 유효하다.

### 설치
```bash
sudo apt install strace
```

### ltrace와의 역할 분담
| | ltrace | strace |
|---|---|---|
| 관찰 대상 | 라이브러리 함수 호출(`strcmp`, `printf` 등) | 커널 시스템 콜(`read`, `open`, `mmap` 등) |
| 정적 링킹 바이너리 | 거의 무용지물 | 항상 동작 |
| 활용 예 | 비교 함수 인자로 정답 노출 | 여는 파일 경로, 네트워크 주소, 프로세스 실행 확인 |

두 도구는 겹치지 않는 정보를 주므로 함께 쓰는 것이 정석이다.

### ptrace 기반이라는 것의 함정 — 안티디버깅과의 충돌
`strace`도 `gdb`와 마찬가지로 `ptrace`를 사용한다. 그런데 리눅스에서 **한 프로세스에는 동시에 하나의 `ptrace` tracer만 붙을 수 있다.** 만약 대상 프로그램이 시작하자마자 스스로 `ptrace(PTRACE_TRACEME, 0, NULL, NULL)`를 호출해 자기 자신을 이미 "추적 중" 상태로 만들어버리는 안티디버깅 트릭을 쓰고 있다면, `strace`(또는 GDB)가 붙으려는 시도 자체가 `ptrace` 시스템 콜 실패로 이어져 프로그램이 비정상 종료되거나 이상하게 동작할 수 있다. 반대로 이 성질을 이용하면 "`strace`/GDB 아래에서 프로그램이 유독 다르게 행동하거나 바로 죽는다"는 관찰 자체가 "이 바이너리는 `ptrace` 기반 안티디버깅을 쓰고 있다"는 강력한 단서가 된다. `strace` 출력 맨 앞부분에서 `ptrace(PTRACE_TRACEME, ...)` 호출이 직접 보이는 경우도 있다.

### -f 옵션이 특히 중요한 이유
많은 CTF 챌린지 바이너리가 시작하자마자 `fork()`로 자식 프로세스를 만들고 실제 로직은 자식에서 처리한다(부모는 감시자 역할). `-f`(follow forks) 옵션 없이 `strace`를 돌리면 부모 프로세스의 시스템 콜만 보이고 정작 궁금한 자식 프로세스의 동작은 놓치게 된다.

## 화면/코드에서 보이는 징후
이 도구도 코드가 아니라 터미널 실행 결과로 확인한다. `strace` 실행 시 `시스템콜이름(인자들) = 반환값` 형태의 줄이 계속 출력된다.

## 가장 먼저 할 것
```bash
strace ./chall
```
아무 옵션 없이 한 번 돌려보고, 출력이 너무 많다면(특히 동적 링킹 프로그램은 시작 시점에 `mmap`, `openat`, `mprotect` 등 라이브러리 로딩 관련 시스템 콜이 수십 줄 쏟아진다) `-e trace=`로 관심 있는 종류만 필터링한다.

## 단계별 절차

**1) 기본 실행**
```bash
strace ./chall
```

**2) 파일 관련 시스템 콜만 필터링**
```bash
strace -e trace=open,openat,read,write ./chall
```
어떤 파일을 열려고 시도하는지, 어떤 파일 디스크립터로 읽고 쓰는지 빠르게 파악할 수 있다.

**3) 프로세스 실행 관련 시스템 콜 확인**
```bash
strace -e trace=execve,fork,clone,ptrace ./chall
```
서브프로세스 실행이나 `ptrace` 안티디버깅 여부를 집중적으로 확인할 때 쓴다.

**4) 자식 프로세스까지 추적**
```bash
strace -f ./chall
```

**5) 타임스탬프와 함께 보기(타이밍 기반 로직 분석)**
```bash
strace -tt ./chall
```

**6) 문자열 인자 길이 늘리기**
```bash
strace -s 300 ./chall
```

**7) 파일로 저장 + 호출 요약 통계**
```bash
strace -o trace.log -c ./chall
```
`-c`는 프로그램 종료 후 시스템 콜별 호출 횟수와 소요 시간 요약 테이블을 보여준다.

## 명령어/단축키
```bash
strace ./chall
strace -e trace=open,openat,read,write ./chall
strace -e trace=execve,fork,clone,ptrace ./chall
strace -f ./chall
strace -tt ./chall
strace -s 300 ./chall
strace -o trace.log -c ./chall
```

## 출력 해석
실전 예시:
```
$ strace -e trace=openat,read,write ./chall
openat(AT_FDCWD, "/lib/x86_64-linux-gnu/libc.so.6", O_RDONLY|O_CLOEXEC) = 3
write(1, "Enter password: ", 17)       = 17
read(0, "test123\n", 1024)             = 8
write(1, "Wrong password.\n", 17)      = 17
+++ exited with 1 +++
```
- 첫 줄은 동적 링커가 `libc.so.6`을 여는 것으로, 프로그램 로직과 무관한 초기화 과정이다.
- `write(1, "Enter password: ", 17)`에서 `1`은 파일 디스크립터 `stdout`, `write(0, ...)`이 아니라 `write`의 첫 인자가 `1`이라는 뜻이다(REV-0106의 syscall 인자 규약 참고).
- `read(0, "test123\n", 1024)`에서 `0`은 `stdin`, `1024`는 요청한 최대 읽기 크기, 실제 반환값 `8`은 실제로 읽은 바이트 수(개행 포함 `"test123\n"` = 8바이트)다.
- 마지막 `write`로 "Wrong password."가 출력된 것으로 입력이 틀렸다는 결과까지 코드 없이 확인된다.

`flag.txt`를 여는 프로그램이라면 다음과 같이 보일 것이다:
```
openat(AT_FDCWD, "flag.txt", O_RDONLY) = 3
read(3, "flag{...}", 100) = 45
```
파일 디스크립터 `3`으로 열고 곧바로 그 fd에서 `read`하는 패턴이 전형적이다.

## 흔한 실수
- 초기 라이브러리 로딩(`mmap`, `openat .../libc.so.6` 등) 시스템 콜과 프로그램 자체 로직에서 발생하는 시스템 콜을 구분하지 못해 출력이 너무 많다고 포기하는 것 — `-e trace=`로 필터링하면 훨씬 깔끔해진다.
- `strace` 아래에서 프로그램이 이상하게 죽거나 멈추는 걸 그냥 버그로 치부하는 것 — `ptrace` 기반 안티디버깅일 가능성을 먼저 의심한다(REV-0105의 보호 기법 논의와도 연결된다).
- `fork`를 쓰는 프로그램에 `-f` 없이 `strace`를 돌려서 정작 중요한 자식 프로세스의 동작을 놓치는 것.
- `read`/`write`의 반환값(실제 처리된 바이트 수)과 요청한 크기(인자로 넘긴 값)를 혼동하는 것 — 항상 반환값이 "실제로 일어난 일"이다.

## 막혔을 때 다음 체크
- 라이브러리 함수 레벨에서 더 보고 싶다면(정답 문자열이 직접 보이는 경우가 많음) → REV-0111 ltrace로 라이브러리 호출 빠르게 보기
- 이 시스템 콜들이 코드에서 어떤 레지스터 규약으로 호출되는지 → REV-0106 SysV AMD64 Calling Convention
- 이 프로그램이 어떤 라이브러리를 쓰는지 정적으로 먼저 확인하고 싶다면 → REV-0101 Dynamic Linking과 Import 함수 추적

## 미니 예제
```bash
$ strace -e trace=read,write,openat -f ./chall < <(echo "test_input")
openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3
read(0, "test_input\n", 1024)          = 11
write(1, "Wrong flag!\n", 12)          = 12
+++ exited with 0 +++
```
`-e trace=`로 필터링하니 라이브러리 로딩 잡음 없이 "표준입력에서 11바이트를 읽고 표준출력에 실패 메시지를 썼다"는 흐름만 바로 보인다 — 다음은 그 사이에서 어떤 비교가 일어났는지 `ltrace`(REV-0111)나 디버거로 파고들 차례다.

## 관련 글
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0106 — SysV AMD64 Calling Convention
- REV-0109 — scanf fgets read 입력 추적
- REV-0101 — Dynamic Linking과 Import 함수 추적

## 출처/검증
- `strace` 옵션 및 동작(`-e trace=`, `-f`, `-tt`, `-s`, `-c`): `strace(1)` man page 기준.
- `ptrace(2)`를 이용한 추적 원리 및 단일 tracer 제약: Linux man-pages `ptrace(2)` 기준.
- `PTRACE_TRACEME` 기반 안티디버깅 기법: 리눅스 안티디버깅 관련 공개 보안 문서/CTF 자료 일반 관례 기준 (2026-09-08 검증).
