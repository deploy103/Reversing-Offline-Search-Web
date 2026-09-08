---
id: REV-0097
title: "ELF Entry Point에서 main까지"
slug: "rev-0097-entry-to-main"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, "readelf", "objdump", "binutils"]
keywords: ["entry point", "_start", "__libc_start_main", "__libc_start_call_main", "main 진입 흐름", "e_entry"]
aliases: ["entry point에서 main까지", "실행 시작 흐름", "elf 실행 순서", "프로그램 시작 흐름"]
symptom_keywords: ["entry point부터 main까지 어떻게 이어지는지 모름", "_start와 main 사이에 뭐가 있는지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Linux ELF 실행 파일은 커널이 넘겨준 `e_entry` 주소(대부분 `_start`)에서 실행을 시작해, `__libc_start_main`(최신 glibc는 내부적으로 `__libc_start_call_main`까지)을 거쳐서야 비로소 우리가 작성한 `main`이 호출된다 — 이 전체 경로를 알면 어떤 바이너리를 봐도 "코드가 시작되자마자 낯선 함수들을 잔뜩 호출하는" 이유를 이해하고 무시할 수 있다.

## 언제 검색해야 하나
- IDA/Ghidra에서 entry point를 열었는데 `main`이 아니라 낯선 초기화 코드가 잔뜩 나와서 당황할 때
- `_start`, `__libc_start_main`, `main`이 정확히 어떤 순서와 관계로 호출되는지 전체 그림이 필요할 때
- GDB로 `run` 대신 entry point부터 한 줄씩 따라가며 프로그램 초기화 과정을 이해하고 싶을 때
- 왜 `main`의 리턴값이 프로세스의 exit code가 되는지 그 경로를 정확히 알고 싶을 때

## 핵심 개념

### 커널이 넘겨주는 것은 딱 하나, entry point 주소
`execve()` 시스템 콜로 ELF 파일을 실행하면, 커널은 Program Header(REV-0090)를 읽어 세그먼트들을 메모리에 매핑하고, 스택에 `argc`/`argv`/`envp`/auxiliary vector(AT_* 값들, 예: `AT_ENTRY`, `AT_PHDR`)를 세팅한 뒤, ELF 헤더의 `e_entry`(REV-0089) 주소로 점프한다. 동적 링킹된 바이너리라면 사실 커널이 직접 `e_entry`로 가는 게 아니라, 먼저 `PT_INTERP`에 지정된 동적 로더(`/lib64/ld-linux-x86-64.so.2`)를 실행해서 필요한 공유 라이브러리(`libc.so.6` 등)를 전부 매핑하고 심볼을 재배치한 다음, 그 로더가 최종적으로 실행 파일의 `e_entry`로 넘어간다.

이 `e_entry`가 가리키는 함수가 관례적으로 **`_start`**라는 이름을 갖는다(REV-0098에서 자세히 다룸). `_start`는 우리가 작성하는 코드가 아니라 glibc가 제공하는 시작 스텁(`crt1.o`에 들어있는 코드, 소스는 `sysdeps/x86_64/start.S`)이다.

### 전체 호출 체인 (glibc, 동적 링킹, x86-64 기준)

```
커널 execve()
  → (동적 링킹이면) ld.so가 라이브러리 로드 및 재배치
  → e_entry 주소로 점프 = _start (crt1.o, 어셈블리)
    → __libc_start_main(main, argc, argv, init, fini, rtld_fini, stack_end) 호출
      → 내부 초기화: TLS 설정, stack protector(카나리) 초기화, __libc_csu_init 등
      → (최신 glibc ≥ 2.34) __libc_start_call_main 이 실제 main 호출을 담당
      → main(argc, argv, envp) 호출   ← 드디어 우리 코드
      → main의 리턴값을 받아서
      → exit(리턴값) 호출
        → 등록된 atexit 핸들러들, 전역 소멸자 실행
        → _exit() / exit_group 시스템 콜로 프로세스 종료
```

핵심은: **`main`은 이 체인의 중간 지점일 뿐이고, 앞뒤로 상당한 양의 glibc 초기화/정리 코드가 자동으로 실행된다**는 것이다. 리버싱 초심자가 entry point부터 한 줄씩 분석하려다 지치는 이유가 바로 이 부분이 전부 "우리 로직과 무관한" 정형화된 코드이기 때문이다.

### 정적 링킹이라면?
정적 링킹된 바이너리는 `ld.so` 단계가 없다 — 커널이 바로 `e_entry`(`_start`)로 점프한다. `__libc_start_main`을 포함한 libc 전체가 이미 바이너리 안에 통째로 들어있으므로, 흐름 자체(`_start` → `__libc_start_main` → `main`)는 동일하지만 외부 라이브러리 로딩 단계가 없어 시작이 더 빠르고, 코드 크기는 훨씬 크다.

### init/fini, `.init_array`/`.fini_array`도 이 흐름에 낀다
`__libc_start_main`은 `main` 호출 전후로 `.init_array` 섹션에 등록된 함수 포인터들(전역 객체 생성자, `__attribute__((constructor))` 함수 등)을 순서대로 호출한다. C++의 전역 객체 생성자가 `main` 실행 전에 이미 실행되는 이유가 여기 있다. 마찬가지로 `.fini_array`는 `exit()` 시점에 실행된다.

## 화면/코드에서 보이는 징후
- IDA/Ghidra에서 entry point에 커서가 가 있고, 함수 이름이 `_start` 또는 `start`
- `_start` 안에 `xor ebp, ebp`, `pop rsi`, `mov rdx, rsp`처럼 스택에서 값을 빼내는 코드와 함께 `__libc_start_main` 호출이 보임
- `main` 함수 진입 전에 IDA Functions 창에 `_init`, `frame_dummy`, `__libc_csu_init`, `register_tm_clones` 같은 낯선 함수들이 잔뜩 나열됨 — 전부 glibc/컴파일러가 자동 삽입한 것이지 사용자 코드가 아니다.

## 가장 먼저 할 것
entry point에서 이 낯선 함수들을 전부 분석하려 하지 말고, `_start` 안에서 `__libc_start_main`(또는 최신 glibc에서 인라인된 형태)의 **첫 번째 인자**만 확인한다. 그게 바로 `main`이다. REV-0009/REV-0099에서 이 방법을 구체적으로 다룬다.

## 단계별 절차

**1) entry point 주소 확인**
```bash
readelf -h ./chall | grep Entry
```

**2) entry point 디스어셈블리 확인**
```bash
objdump -d -M intel ./chall | grep -A20 '<_start>:'
```
출력 예:
```
0000000000001060 <_start>:
    1060:	f3 0f 1e fa          	endbr64
    1064:	31 ed                	xor    ebp,ebp
    1066:	49 89 d1             	mov    r9,rdx
    1069:	5e                   	pop    rsi
    106a:	48 89 e2             	mov    rdx,rsp
    106d:	48 83 e4 f0          	and    rsp,0xfffffffffffffff0
    1071:	50                   	push   rax
    1072:	54                   	push   rsp
    1073:	4c 8d 05 c6 01 00 00 	lea    r8,[rip+0x1c6]        # __libc_csu_fini
    107a:	48 8d 0d 4f 01 00 00 	lea    rcx,[rip+0x14f]        # __libc_csu_init
    1081:	48 8d 3d c1 00 00 00 	lea    rdi,[rip+0xc1]         # main
    1088:	ff 15 12 2f 00 00    	call   qword ptr [rip+0x2f12] # __libc_start_main@GOT
```
`lea rdi, [rip+0xc1]` 주석에 `# main`이라고 objdump가 친절하게 알려준다(strip 안 된 경우). 이 값이 `rdi`, 즉 `__libc_start_main`의 첫 번째 인자로 들어간다.

**3) GDB로 실제 호출 흐름을 스텝 실행으로 확인**
```gdb
gdb ./chall
(gdb) break _start
(gdb) run
(gdb) stepi        # 한 명령어씩 진행
(gdb) x/3i $pc
```
`call __libc_start_main` 직전에 `info registers rdi`로 `rdi`에 담긴 값이 `main`의 주소인지 확인할 수 있다.

**4) main에 브레이크포인트를 걸고 도달 여부 확인**
```gdb
(gdb) break main
(gdb) continue
```
`_start`에서 `continue`만 눌러도 GDB가 알아서 `__libc_start_main`을 거쳐 `main`까지 실행하고 멈춘다 — 중간 초기화 코드를 직접 스텝할 필요가 없다는 걸 실감할 수 있다.

**5) `main` 리턴 후 exit까지 관찰(선택)**
```gdb
(gdb) finish
```
`main`에서 `finish`를 실행하면 `__libc_start_call_main`(또는 구버전은 `__libc_start_main`) 안으로 돌아가고, 곧이어 `exit()`가 호출되는 걸 확인할 수 있다.

## 명령어/단축키
```bash
readelf -h ./chall | grep Entry
objdump -d -M intel ./chall | grep -A20 '<_start>:'
```
GDB: `break _start`, `break main`, `stepi`, `finish`, `info registers rdi`

## 출력 해석
- `_start`에서 `__libc_start_main` 호출 직전 `rdi`에 로드되는 주소 = **진짜 `main`의 주소**. objdump/IDA가 이미 이름을 붙여줬다면 바로 확인 가능, strip됐다면 REV-0099에서 다루는 시그니처 기반 추정이 필요.
- GDB에서 `_start`부터 `continue`만으로 `main`까지 자동으로 도달한다는 것은, 이 사이의 코드가 조건 분기 없이(입력값과 무관하게) 거의 항상 같은 순서로 실행되는 "고정 배관"이라는 뜻이다 — 분석 우선순위가 낮다.

## 흔한 실수
- entry point의 초기화 코드(`__libc_csu_init`, `frame_dummy` 등)를 사용자 로직으로 착각하고 시간을 들여 분석하는 것 — 거의 항상 컴파일러/glibc가 자동 삽입한 정형화된 코드다.
- `main`의 리턴값과 프로세스의 종료 코드(`echo $?`)가 무관하다고 생각하는 것 — `main`의 리턴값이 그대로 `exit()`의 인자로 전달되어 종료 코드가 된다.
- 정적 링킹된 바이너리에서 `ld.so` 단계가 없다는 걸 모르고 "라이브러리가 언제 로드되는지" 헷갈리는 것 — 정적 링킹이면 별도 로딩 단계 자체가 없다(코드가 이미 파일 안에 있음).

## 막혔을 때 다음 체크
- `_start`의 코드를 명령어 단위로 더 자세히 알고 싶으면 → [REV-0098 _start 함수 읽는 법](./rev-0098-start-function.md)
- `__libc_start_main`의 정확한 시그니처와 glibc 버전별 차이가 궁금하면 → [REV-0099 __libc_start_main이 무엇이고 main을 찾는 법](./rev-0099-libc-start-main.md)
- stripped 바이너리에서 이 흐름을 어떻게 따라가는지 → [REV-0010 stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)
- 라이브러리 함수 호출이 PLT/GOT를 거치는 이유가 궁금하면 → [REV-0100 PLT와 GOT 기초](./rev-0100-plt-got.md)

## 미니 예제
```gdb
$ gdb -q ./chall
(gdb) break _start
Breakpoint 1 at 0x1060
(gdb) run
Breakpoint 1, 0x0000555555555060 in _start ()
(gdb) break main
Breakpoint 2 at 0x555555555149
(gdb) continue
Breakpoint 2, 0x0000555555555149 in main ()
```
`_start`에서 딱 두 개의 브레이크포인트와 `continue` 한 번으로 `main`까지 도달했다 — 중간의 `__libc_start_main` 초기화 과정은 신경 쓸 필요가 없었다는 것을 직접 확인한 것이다.

## 관련 글
- [REV-0098 — _start 함수 읽는 법](./rev-0098-start-function.md)
- [REV-0099 — __libc_start_main이 무엇이고 main을 찾는 법](./rev-0099-libc-start-main.md)
- [REV-0089 — ELF 헤더 읽는 법](./rev-0089-elf-header.md)
- [REV-0009 — main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)
- [REV-0010 — stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)
- [REV-0100 — PLT와 GOT 기초](./rev-0100-plt-got.md)

## 출처/검증
- 실행 시작 흐름(`execve` → `ld.so` → `_start` → `__libc_start_main` → `main` → `exit`): glibc 소스 `sysdeps/x86_64/start.S`, `csu/libc-start.c` 기준 (2026-09-08 검증).
- auxiliary vector, ELF 로딩 절차: Linux 커널 문서 및 System V ABI "Process Initialization" 챕터 기준.
- `.init_array`/`.fini_array` 처리: glibc `csu/libc-start.c`의 `__libc_csu_init` 및 GCC `__attribute__((constructor))` 문서 기준.
