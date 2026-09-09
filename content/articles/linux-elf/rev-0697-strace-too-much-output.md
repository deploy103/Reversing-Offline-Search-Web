---
id: REV-0697
title: "strace 결과가 너무 많아서 원하는 부분을 못 찾을 때"
slug: "rev-0697-strace-too-much-output"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [strace, GDB]
keywords: ["strace -e trace", "strace 필터링", "strace -c", "strace -f", "시스템 콜 필터"]
aliases: ["strace 출력 너무 많음", "strace 필요한 부분만 보기", "strace 로그 걸러내기", "strace 결과 정리"]
symptom_keywords: ["strace 결과가 수천 줄 나옴", "strace 출력에서 원하는 syscall을 못 찾음", "strace 결과가 스크롤을 못 따라감", "fork/thread마다 strace 로그가 섞여서 헷갈림"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`strace ./chall`을 그냥 실행하면 프로그램 시작부터 끝까지의 **모든 시스템 콜**(라이브러리 초기화, 동적 링커 준비 과정 포함)이 다 찍히므로, `-e trace=`로 관심 있는 syscall 종류만 걸러내고, `-o 파일`로 저장한 뒤 `grep`으로 검색하고, 필요하면 `-c`로 요약 통계부터 보는 식으로 접근해야 원하는 부분을 빠르게 찾을 수 있다.

## 언제 검색해야 하나
- `strace ./chall`을 실행했더니 화면이 수천 줄로 도배되어서 정작 프로그램이 입력을 받는 시점(`read`)이나 파일을 여는 시점(`openat`)을 못 찾을 때
- 어떤 syscall이 문제인지는 모르겠고 일단 "뭘 하는지 감"만 잡고 싶을 때
- `fork()`나 `pthread_create()`를 쓰는 프로그램이라 여러 프로세스/스레드의 로그가 뒤섞여서 어느 줄이 어느 흐름인지 헷갈릴 때

## 핵심 개념
`strace`는 `ptrace(2)` 시스템 콜을 이용해 대상 프로세스가 커널에 요청하는 **모든** 시스템 콜을 가로채서 보여준다(REV-0112 strace 기초 참고). 문제는 프로그램이 `main()`에 도달하기도 전에 동적 링커(`ld.so`)가 `openat`, `mmap`, `mprotect`, `fstat` 같은 syscall을 수십~수백 번 호출해서 공유 라이브러리를 로드한다는 점이다. 여기에 `libc`의 스택 카나리 초기화, `malloc` 내부의 `brk`/`mmap` 호출까지 더해지면, 정작 우리가 보고 싶은 "이 프로그램이 어떤 파일을 열고 어떤 입력을 읽는가" 같은 한두 줄이 수백 줄 노이즈 속에 묻혀버린다.

`strace`는 이런 상황을 위해 **syscall 종류별 필터**, **문자열 그룹 필터**(`trace=file`, `trace=network` 등 미리 정의된 그룹), **요약 통계 모드**(`-c`), **출력 분리**(`-o`, `-ff`) 옵션을 제공한다. 이 옵션들을 조합하면 노이즈를 크게 줄일 수 있다.

## 화면/코드에서 보이는 징후
```text
$ strace ./chall
execve("./chall", ["./chall"], 0x7ffd... /* 60 vars */) = 0
brk(NULL)                              = 0x55d2a3f9c000
arch_prctl(0x3001, 0x7ffe...)          = -1 EINVAL (Invalid argument)
access("/etc/ld.so.preload", R_OK)     = -1 ENOENT (No such file or directory)
openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3
... (수백 줄 생략) ...
```
정작 찾고 싶은 `read(0, "flag{...", 100)` 같은 줄은 이 아래 어딘가에 파묻혀 있다.

## 가장 먼저 할 것
관심사에 따라 다음 세 갈래 중 하나로 바로 시작한다.
1. **"이 프로그램이 뭘 하는지 개요만 알고 싶다"** → `-c`로 요약 통계부터 본다.
2. **"파일 입출력/입력값만 보고 싶다"** → `-e trace=file` 또는 `-e trace=read,write`로 좁힌다.
3. **"자식 프로세스/스레드까지 다 보고 싶은데 섞이는 게 문제다"** → `-f -ff -o 접두사`로 프로세스별 파일을 분리한다.

## 단계별 절차

**1) 요약 통계로 전체 그림 먼저 파악**
```bash
strace -c ./chall
```
프로그램 종료 후 syscall별 호출 횟수, 소요 시간, 에러 횟수를 표로 보여준다. 어떤 syscall이 특이하게 많이 호출되는지(예: `read`가 반복문에서 계속 불림) 여기서 먼저 감을 잡는다.

**2) 관심 있는 syscall 종류로 필터링**
```bash
strace -e trace=open,openat,read,write ./chall
strace -e trace=file ./chall        # 파일 관련 syscall 그룹(open, stat, access, unlink 등)
strace -e trace=network ./chall     # socket, connect, send, recv 등
strace -e trace=memory ./chall      # brk, mmap, mprotect 등
strace -e trace=signal ./chall      # 시그널 관련
```
`trace=` 뒤에는 개별 syscall 이름을 콤마로 나열하거나, strace가 미리 정의한 그룹 이름(`file`, `network`, `process`, `signal`, `memory`, `ipc` 등)을 쓸 수 있다.

**3) 특정 syscall만 제외하기(반대 방향 필터)**
```bash
strace -e trace=!rt_sigprocmask,mprotect ./chall
```
동적 링킹 초반 노이즈만 골라서 빼고 싶을 때 유용하다.

**4) 파일로 저장 후 grep으로 검색**
```bash
strace -o trace.log ./chall
grep -n "openat\|read(0" trace.log
less trace.log
```
화면이 흘러가서 놓친 부분도 파일에 다 남아있으므로, 나중에 `grep`, `less -N`(줄 번호 표시)으로 여유 있게 찾는다.

**5) 문자열이 잘려 보이면 `-s`로 길이 늘리기**
```bash
strace -s 200 -e trace=read,write ./chall
```
기본적으로 strace는 문자열 인자를 32바이트까지만 보여주고 `"..."`로 자른다(`-s <숫자>`로 조정). 입력값 전체를 보고 싶을 때 필수.

**6) fork/thread가 있는 프로그램은 `-f`(follow) + `-ff`(프로세스별 분리)**
```bash
strace -f -ff -o trace ./chall
ls trace.*        # trace.<PID> 형태로 프로세스별 파일 생성됨
```
`-f`만 쓰면 여러 프로세스의 로그가 한 화면에 `[pid 1234]`, `[pid 1235]` 접두사로 뒤섞여 나온다. `-ff`를 추가하면 프로세스마다 별도 파일로 분리되어 훨씬 읽기 편하다.

**7) 시간 정보까지 필요하면 타임스탬프 옵션 추가**
```bash
strace -tt -T -e trace=read,write ./chall
```
`-tt`는 마이크로초 단위 절대 시각, `-T`는 각 syscall이 걸린 시간을 보여준다. 타이밍 기반 사이드채널이나 타임아웃 문제를 볼 때 유용하다.

## 명령어/단축키
```bash
strace -c ./chall
strace -e trace=file ./chall
strace -e trace=!mprotect,rt_sigprocmask ./chall
strace -o trace.log ./chall
strace -s 200 ./chall
strace -f -ff -o trace ./chall
strace -tt -T ./chall
strace -p <PID>          # 이미 실행 중인 프로세스에 붙기
```

## 출력 해석
- `-c` 결과의 `% time`, `seconds`, `calls`, `errors`, `syscall` 열 중 `errors` 열에 숫자가 있으면 그 syscall이 실패했다는 뜻이다(예: `access` 실패는 대부분 정상 — 파일이 없는지 먼저 확인하는 절차일 뿐).
- `-e trace=file`로도 여전히 줄이 많다면, `ld.so`가 라이브러리를 찾느라 여러 경로를 순회하며 `access`/`openat`을 반복 호출하는 것이 원인인 경우가 많다 — 이 구간은 실제 프로그램 로직과 무관하므로 무시해도 된다.
- `read(0, "...", n)`처럼 fd `0`(stdin)을 읽는 줄이 우리가 넣은 입력이 실제로 프로그램에 도달했는지 확인하는 가장 확실한 지점이다.

## 흔한 실수
- 필터 없이 `strace ./chall > log.txt`만 해두고 `less`로 처음부터 끝까지 눈으로 스크롤하며 찾는 것 — `grep`을 먼저 쓰는 편이 훨씬 빠르다.
- `-e trace=`의 문법을 `-e open,read`처럼 `trace=`를 빼먹고 쓰는 것(구버전 strace 문법과 신버전 문법이 다를 수 있으므로 `man strace`로 버전별 문법 확인).
- `-f`만 걸고 `-ff`나 `-o`를 안 써서, 여러 프로세스 로그가 한 화면에 뒤섞인 채로 분석하려다 포기하는 것.
- 문자열이 `"AAAAAAAA"...`처럼 잘려 보이는데 `-s` 옵션을 몰라서 실제 값을 확인 못 하는 것.

## 막혔을 때 다음 체크
- strace 자체의 기본 사용법과 출력 형식이 처음이라면 → REV-0112 strace로 시스템 콜에서 힌트 찾기
- 라이브러리 함수 호출 수준에서(syscall보다 한 단계 위) 보고 싶다면 → REV-0111 ltrace로 라이브러리 호출 빠르게 보기
- 정적 링킹된 바이너리라서 ltrace가 안 먹힌다면 → REV-0698 ltrace가 정적 바이너리에서 아무것도 안 보여줄 때
- syscall 트레이싱보다 특정 함수에서 딱 멈춰서 보고 싶다면 → REV-0696 동적 링킹된 함수에 브레이크포인트가 심볼 없이는 안 걸릴 때

## 미니 예제
```bash
$ strace -e trace=read,write,openat -s 100 ./chall < input.txt
openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3
openat(AT_FDCWD, "/lib/x86_64-linux-gnu/libc.so.6", O_RDONLY|O_CLOEXEC) = 3
read(0, "test_password_123\n", 1024)   = 19
write(1, "Wrong password\n", 16)       = 16
+++ exited with 1 +++
```
`-e trace=read,write,openat`로 좁혔더니 라이브러리 로딩 잡음 두 줄 뒤에 바로 실제 입력(`read`)과 결과(`write`)가 보여서, 이 프로그램이 입력을 받자마자 패스워드를 검사하고 실패 메시지를 찍는다는 흐름을 몇 초 만에 파악할 수 있었다.

## 관련 글
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0698 — ltrace가 정적 바이너리에서 아무것도 안 보여줄 때
- REV-0696 — 동적 링킹된 함수에 브레이크포인트가 심볼 없이는 안 걸릴 때

## 출처/검증
- `strace`의 `-e trace=`, `-c`, `-f`/`-ff`, `-s`, `-tt`/`-T` 옵션 동작은 `strace(1)` man page(strace 공식 프로젝트, strace.io) 기준이다.
- syscall 그룹 이름(`file`, `network`, `memory`, `process`, `signal`, `ipc` 등)은 strace 소스의 `-e trace=` 그룹 정의를 따른다.
- `ptrace(2)` 기반 시스템 콜 가로채기 원리는 Linux man-pages `ptrace(2)` 문서에 기술되어 있다.
