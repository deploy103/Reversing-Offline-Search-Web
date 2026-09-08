---
id: REV-0108
title: "argc argv envp를 어셈블리에서 찾는 법"
slug: "rev-0108-argc-argv-envp"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [IDA, GDB, Pwndbg]
keywords: ["argc", "argv", "envp", "__libc_start_main", "_start", "main 함수 인자", "명령줄 인자", "환경변수"]
aliases: ["argc argv 위치", "main 함수 인자 찾기", "_start 분석", "__libc_start_main 인자"]
symptom_keywords: ["main 함수에 인자가 3개인데 어디서 오는지 모르겠음", "argv가 어디 저장되는지 모르겠음", "envp를 어셈블리에서 못찾겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`int main(int argc, char **argv, char **envp)`의 세 인자는 커널이 프로세스를 시작할 때 스택에 직접 얹어준 값들이 `_start` → `__libc_start_main` → `main`으로 순서대로 레지스터를 거쳐 전달된 것이며, `main` 진입 직후 `RDI=argc, RSI=argv, RDX=envp`(x64 SysV 규약) 형태로 도착한다.

## 언제 검색해야 하나
- IDA/Ghidra가 `main` 함수의 시그니처를 `int __cdecl main(int argc, char **argv, char **envp)`처럼 자동으로 추론해놨는데, 이 값들이 실제로 어디서 오는지 궁금할 때
- `_start`나 `__libc_start_main` 근처의 디스어셈블리를 보게 됐는데 알아보기 힘들 때
- 프로그램이 명령줄 인자(`argv[1]`)나 환경변수(`envp`)를 검사하는 로직을 갖고 있어서, 그 시작점을 어셈블리에서 찾아 GDB로 실제 값을 찍어보고 싶을 때

## 핵심 개념

### 커널이 스택에 준비해주는 것
`execve()`로 새 프로세스가 시작되면, 리눅스 커널은 프로세스의 초기 스택 맨 위에 다음과 같은 정보를 미리 배치해준다(스택은 아래로 자라므로, 실제로는 스택의 가장 높은 주소 쪽부터 이런 순서로 놓인다고 이해하면 된다):
```
[esp/rsp]      argc                (인자 개수, 정수)
[esp+8]        argv[0]             (프로그램 이름 문자열의 포인터)
[esp+16]       argv[1]
...
               NULL                (argv 배열의 끝 표시)
               envp[0]             (환경변수 문자열의 포인터, "KEY=VALUE" 형태)
               envp[1]
...
               NULL                (envp 배열의 끝 표시)
               auxv[]              (Auxiliary Vector — 커널이 넘겨주는 추가 정보, ELF 헤더 주소 등)
```
이건 컴파일러가 만든 게 아니라 **커널이 프로세스를 실행시키는 순간 스택에 직접 세팅**하는 값이다. `_start`의 첫 명령어가 실행되는 시점에는 이미 이 값들이 스택 맨 위에 준비되어 있다.

### _start: 진짜 진입점
`_start`는 링커가 지정한 ELF의 실제 진입점(entry point, `readelf -h`의 `Entry point address`)이다. 이 코드는 우리가 직접 작성한 것이 아니라 glibc(정확히는 `crt1.o`)가 제공한다. `_start`가 하는 일은 대략:
1. 커널이 스택에 준비해준 `argc`(맨 위)를 꺼내고, `argv` 배열의 시작 주소(`argc` 바로 다음 위치)를 계산한다.
2. `__libc_start_main`이라는 함수를 호출하면서, 우리가 작성한 `main` 함수의 주소와 함께 `argc`, `argv` 등을 인자로 넘긴다.

x64 리눅스(glibc)에서 전형적인 `_start` 디스어셈블리는 대략 이렇게 생겼다(버전에 따라 세부는 다를 수 있다):
```asm
_start:
    endbr64
    xor  ebp, ebp
    mov  r9, rdx           ; rtld_fini (동적 링커 정리 함수)
    pop  rsi                ; argc (스택 맨 위 값을 rsi로 꺼냄)
    mov  rdx, rsp           ; argv (rsi를 꺼낸 뒤 남은 스택 위치 = argv 시작)
    and  rsp, 0xfffffffffffffff0
    push rax
    push rsp
    lea  r8, [rip+...]      ; __libc_csu_fini
    lea  rcx, [rip+...]     ; __libc_csu_init
    lea  rdi, [rip+...]     ; main 함수 주소
    call __libc_start_main
```
`pop rsi`로 스택 맨 위의 `argc`를 그대로 `rsi`에 담고, 그 직후 `rsp`(이제 `argv[0]`을 가리키는 위치)를 `rdx`에 복사해서 `argv`로 쓴다.

### __libc_start_main: main을 실제로 호출하는 곳
`__libc_start_main`(glibc 내부 함수, `libc.so.6` 안에 있으므로 PLT를 거쳐 호출됨)의 전형적인 시그니처는 다음과 같다(glibc 버전에 따라 인자 구성이 조금씩 다르다):
```c
int __libc_start_main(
    int (*main)(int, char**, char**),
    int argc,
    char **argv,
    void (*init)(void),
    void (*fini)(void),
    void (*rtld_fini)(void),
    void *stack_end
);
```
SysV AMD64 규약(REV-0106)에 따라 `RDI=main주소, RSI=argc, RDX=argv, RCX=init, R8=fini, R9=rtld_fini`, 마지막 `stack_end`는 스택으로 전달된다. `__libc_start_main`은 내부에서 표준 스트림 초기화, TLS 설정, 스택 카나리 초기값 세팅 등 여러 준비를 마친 뒤, **환경변수 포인터(envp)를 별도 전역 변수(`__environ`)에서 계산**해서 최종적으로 우리가 작성한 `main(argc, argv, envp)`를 호출한다. `envp`는 `argv` 배열이 `NULL`로 끝나는 바로 다음 위치이므로, `argv`와 `argc`만 있으면 `envp` 주소도 계산 가능하다 — `__libc_start_main`이 이 계산을 대신 해주는 것이다.

### main 진입 시점의 레지스터 상태(x64)
결국 우리가 작성한 `main`이 실제로 실행되기 시작하는 순간에는:
```
RDI = argc
RSI = argv   (char** — 문자열 포인터 배열의 시작 주소)
RDX = envp   (char** — "KEY=VALUE" 문자열 포인터 배열의 시작 주소, NULL로 끝남)
```
`main`의 프롤로그에서 이 값들을 로컬 스택 변수에 옮겨 저장하는 코드가 흔히 보인다:
```asm
mov [rbp-0x14], edi   ; argc
mov [rbp-0x20], rsi   ; argv
mov [rbp-0x28], rdx   ; envp
```
`main`이 `int main(int argc, char *argv[])`처럼 두 개 인자만 쓰거나 `int main(void)`로 인자를 아예 안 받게 선언됐다면, 해당 레지스터 값은 그냥 무시되고 코드에 나타나지 않는다 — 그렇다고 해서 커널/`_start`가 그 값을 안 넘겨주는 것은 아니고, 단지 `main` 코드가 안 쓸 뿐이다.

### 32비트(cdecl)에서는 스택으로 전달
32비트 리눅스에서는 REV-0107에서 설명한 cdecl 규약대로 `argc`, `argv`, `envp`가 전부 스택에 push되어 `main`으로 전달된다. `main` 프롤로그에서 `[ebp+8]=argc, [ebp+0xc]=argv, [ebp+0x10]=envp` 형태로 접근하는 코드가 보인다.

## 화면/코드에서 보이는 징후
- IDA/Ghidra가 `main`의 프로토타입을 자동으로 `int main(int argc, char **argv, char **envp)`로 추론해서 붙여놓음(실제로 쓰이는 인자 개수에 따라 1개나 2개만 추론되기도 함)
- `_start` 근처에 `pop rsi`, `mov rdx, rsp`, `call __libc_start_main`(또는 `call __libc_start_main@plt`) 패턴이 보임
- `main` 프롤로그에 `mov [rbp-N], edi`처럼 `EDI`/`RDI`를 로컬 변수에 옮겨 담는 코드가 있으면 그 프로그램은 `argc`를 실제로 검사한다는 뜻(예: "사용법: ./chall <key>" 류의 CLI 인자 검사)

## 가장 먼저 할 것
`main` 함수를 찾았다면(REV-0100~0105에서 다룬 여러 단서로 위치를 좁힐 수 있다) 프롤로그의 처음 몇 줄만 보고 `RDI`, `RSI`, `RDX`가 로컬 변수 어디에 저장되는지 확인한다. 어디에도 저장되지 않고 바로 다른 계산에 쓰인다면 최적화된 코드이므로 GDB로 직접 실행하며 관찰하는 편이 빠르다.

## 단계별 절차

**1) main 시작 주소에 브레이크포인트**
```gdb
break main
run <arg1> <arg2>
```
GDB에서 프로그램 실행 시 명령줄 인자를 직접 넘길 수 있다.

**2) main 진입 직후 레지스터 확인**
```gdb
info registers rdi rsi rdx
```
`RDI`=argc, `RSI`=argv, `RDX`=envp가 보인다.

**3) argv 배열 내용 확인**
```gdb
p argc
p argv[0]
x/s argv[0]
p argv[1]
x/s argv[1]
```
Pwndbg가 있다면 `main`에서 디버그 정보가 있는 경우 `p argc`, `p argv`처럼 변수 이름으로 바로 접근 가능하다. 디버그 정보가 없다면 레지스터/스택 오프셋으로 직접 접근한다:
```gdb
x/s *(char**)($rsi)
x/s *(char**)($rsi+8)
```

**4) envp(환경변수 배열) 훑어보기**
```gdb
x/8gx $rdx
x/s *(char**)($rdx)
```
`envp[0]`부터 `NULL`이 나올 때까지 각 포인터가 `"KEY=VALUE"` 형태의 문자열을 가리킨다.

**5) _start ~ __libc_start_main 흐름을 직접 따라가 보고 싶다면**
```gdb
break _start
run
stepi   ; 한 명령어씩 실행하며 pop/mov 순서로 argc, argv가 만들어지는 과정 관찰
```

## 명령어/단축키
GDB: `break main`, `run <args>`, `info registers rdi rsi rdx`, `x/s argv[0]`, `p argc`, `break _start`, `stepi`

## 출력 해석
- `x/s argv[0]`은 보통 실행한 바이너리의 경로 문자열(`/home/user/chall` 등)이 나온다 — `argv[0]`은 프로그램 이름이지 첫 번째 "사용자 인자"가 아니라는 점을 기억한다. 사용자가 넘긴 첫 인자는 `argv[1]`이다.
- `envp` 배열을 끝까지 훑으면 `PATH=...`, `HOME=...`, `LD_PRELOAD=...`(설정돼 있다면) 등이 보인다. `LD_PRELOAD`나 `LD_LIBRARY_PATH` 같은 값을 프로그램이 직접 검사하는 안티치트/안티디버깅 로직이 있는지 확인할 때 유용하다.

## 흔한 실수
- `argv[0]`을 사용자가 입력한 첫 번째 인자로 착각하는 것 — `argv[0]`은 항상 실행 파일 자기 자신의 경로/이름이다.
- `main`이 인자를 하나도 안 쓴다고 해서 `_start`/`__libc_start_main`이 값들을 안 넘겼다고 생각하는 것 — 값은 항상 레지스터에 도착해 있고, 단지 `main` 코드가 무시할 뿐이다.
- 32비트와 64비트에서 `main` 인자 접근 방식(레지스터 vs 스택)을 혼동하는 것 — REV-0106/REV-0107의 차이가 여기에도 그대로 적용된다.
- `envp`를 항상 `main`의 세 번째 인자로 명시적으로 받아야만 접근 가능하다고 생각하는 것 — glibc는 `main`이 몇 개 인자를 선언했든 상관없이 전역 변수 `environ`(또는 `__environ`)을 통해서도 항상 환경변수 배열에 접근할 수 있게 해준다.

## 막혔을 때 다음 체크
- 이 값들이 어떤 레지스터로 전달되는지 규약 자체를 더 알고 싶다면 → REV-0106 SysV AMD64 Calling Convention, REV-0107 Linux x86 cdecl Calling Convention
- `main`에 진입한 뒤 `scanf`/`fgets`로 추가 입력을 받는 부분을 추적하고 싶다면 → REV-0109 scanf fgets read 입력 추적
- CALL 명령어와 리턴 주소 개념 → REV-0071 CALL: 함수 호출, 반환 주소, 인자 추적

## 미니 예제
```bash
$ gdb ./chall
(gdb) break main
(gdb) run hello world
Breakpoint 1, 0x0000555555555185 in main ()
(gdb) info registers rdi rsi rdx
rdi            0x3                 3
rsi            0x7fffffffe4c8      ...
rdx            0x7fffffffe4f0      ...
(gdb) p (int)$rdi
$1 = 3
(gdb) x/s *(char**)$rsi
0x7fffffffe808: "/home/user/chall"
(gdb) x/s *(char**)($rsi+8)
0x7fffffffe81a: "hello"
(gdb) x/s *(char**)($rsi+16)
0x7fffffffe820: "world"
```
`argc=3`(프로그램 이름 + 인자 2개), `argv[0]`은 실행 경로, `argv[1]="hello"`, `argv[2]="world"`가 정확히 확인된다.

## 관련 글
- REV-0106 — SysV AMD64 Calling Convention
- REV-0107 — Linux x86 cdecl Calling Convention
- REV-0109 — scanf fgets read 입력 추적
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- 커널이 초기 스택에 배치하는 `argc/argv/envp/auxv` 레이아웃: Linux `execve(2)` man page 및 `System V Application Binary Interface, AMD64 Supplement`의 "Initial Stack and Register State" 절 기준.
- `__libc_start_main` 시그니처 및 `_start` 동작: glibc 소스(`sysdeps/x86_64/start.S`, `csu/libc-start.c`) 공개 구현 기준 (2026-09-08 검증).
