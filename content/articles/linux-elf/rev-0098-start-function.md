---
id: REV-0098
title: "_start 함수 읽는 법"
slug: "rev-0098-start-function"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, "objdump", "readelf", "binutils"]
keywords: ["_start", "crt1.o", "start.S", "__libc_start_main 인자", "entry point 어셈블리"]
aliases: ["_start 함수란", "_start 분석", "start 함수 읽기", "entry point 어셈블리 읽기"]
symptom_keywords: ["_start 코드가 뭘 하는지 모름", "entry point 어셈블리 해석이 안됨"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`_start`는 우리가 작성한 코드가 아니라 glibc의 `crt1.o`에 들어있는 짧은 어셈블리 스텁으로, 하는 일은 딱 하나 — 커널이 스택에 얹어놓은 `argc`/`argv`와 몇 가지 함수 포인터를 레지스터에 정리해서 `__libc_start_main`을 호출하는 것뿐이다.

## 언제 검색해야 하나
- entry point로 이동했더니 `_start`라는 짧은 함수가 나왔는데 각 명령어가 왜 있는지 궁금할 때
- `xor ebp, ebp`, `pop rsi`, `and rsp, 0xfffffffffffffff0` 같은 명령어들의 의도가 궁금할 때
- `_start`가 `main`을 직접 호출하지 않고 `__libc_start_main`을 호출하는 이유가 궁금할 때
- 정적 분석 중 `_start`를 몇 초 만에 훑고 다음 단계로 넘어가고 싶을 때

## 핵심 개념

### _start의 출처
동적 링킹된 일반적인 x86-64 Linux 바이너리에서 `_start`는 glibc 빌드에 포함된 `sysdeps/x86_64/start.S`를 어셈블한 오브젝트(`crt1.o` 또는 `Scrt1.o` — PIE용)에서 온다. gcc/clang으로 평범하게 컴파일하면 링커가 이 오브젝트를 자동으로 링크에 포함시키므로, 우리가 이 코드를 작성하거나 신경 쓸 일은 원래 없다. 하지만 리버싱할 때는 남이 컴파일한 바이너리를 보는 것이므로 이 코드가 그대로 나타난다.

### 명령어 한 줄씩 의미

x86-64, 일반적인 glibc 빌드 기준(버전에 따라 세부 명령어 순서는 조금씩 다를 수 있다):

```asm
_start:
    endbr64                          ; CET(Control-flow Enforcement) 지원용, 간접 점프/콜의 합법적 목적지 표시 (보안 기능, 로직과 무관)
    xor    ebp, ebp                  ; rbp를 0으로 초기화 — "여기가 콜스택의 최상위(맨 밑바닥)"라는 관례적 표시. 디버거/언와인더가 이 값을 보고 스택 추적을 여기서 멈춘다.
    mov    r9, rdx                   ; rdx에 커널이 넣어둔 값(rtld_fini, 동적 로더의 정리 함수 포인터)을 r9로 옮김 — __libc_start_main의 인자로 쓰임
    pop    rsi                       ; 스택 맨 위에 있던 argc를 rsi로 꺼냄 (커널이 프로세스 시작 시 스택에 argc, argv[], NULL, envp[], NULL, auxv 순으로 얹어놓았음)
    mov    rdx, rsp                  ; 이제 rsp가 가리키는 곳이 argv[0]의 시작 — rdx = argv
    and    rsp, 0xfffffffffffffff0   ; 스택을 16바이트 정렬(SysV x64 ABI 요구사항)
    push   rax                       ; 정렬을 맞추기 위한 패딩(또는 리턴 주소 자리 대체용)
    push   rsp                       ; 현재 rsp 값을 스택에 푸시 (stack_end 인자)
    lea    r8,  [rip+...]            ; r8 = __libc_csu_fini 주소 (fini 콜백)
    lea    rcx, [rip+...]            ; rcx = __libc_csu_init 주소 (init 콜백)
    lea    rdi, [rip+...]            ; rdi = main 함수 주소  ← 이게 핵심
    call   __libc_start_main          ; 위에서 세팅한 인자들로 __libc_start_main 호출, 여기서 리턴하지 않음(정상 흐름이면)
```

이 명령어들이 하는 일을 요약하면: **커널이 스택에 던져준 원시 값들(argc, argv 등)을 SysV x64 호출 규약(RDI, RSI, RDX, RCX, R8, R9 순서)에 맞게 레지스터로 옮겨 담아서, `__libc_start_main`이라는 훨씬 복잡한 함수 하나를 호출하는 것**뿐이다.

### 왜 xor ebp, ebp인가
`rbp`를 0으로 만드는 것은 디버거나 스택 언와인더(backtrace 생성기)에게 "콜스택이 여기서 끝난다"는 신호를 준다. GDB에서 `bt`(backtrace)를 실행했을 때 `_start`보다 위로 스택 프레임이 안 나오는 이유가 이것이다.

### 왜 스택을 16바이트로 정렬하는가
SysV AMD64 ABI는 `call` 명령어가 실행되는 시점에 `rsp % 16 == 0`이어야 한다고 규정한다(SSE 명령어 등 16바이트 정렬 메모리 접근을 안전하게 하기 위함). 커널이 프로세스를 시작할 때 스택 정렬 상태가 이 요구사항과 정확히 맞지 않을 수 있어 `_start`가 명시적으로 정렬해준다.

### 정적 링킹이면 뭐가 다른가
코드 자체(`_start`의 명령어)는 거의 동일하다. 차이는 `__libc_start_main`이 GOT를 거친 동적 심볼 호출이 아니라 바이너리 안에 이미 포함된 코드로 direct call된다는 점뿐이다.

## 화면/코드에서 보이는 징후
- IDA/Ghidra/objdump에서 함수 크기가 매우 작음(20~40바이트 내외)
- CALL 명령어가 딱 하나(`__libc_start_main` 또는 그 GOT 스텁)만 있고 그 외에는 전부 레지스터 세팅용 `mov`/`lea`/`pop`/`push`
- 함수 이름이 strip 여부와 무관하게 `_start`로 남아있는 경우가 많음(동적 심볼에도 포함되는 경우가 있으나, 완전히 strip되면 이름도 사라지고 ELF 헤더의 `e_entry` 주소로만 식별 가능)

## 가장 먼저 할 것
`_start`를 명령어 단위로 전부 분석하려 하지 말고, **`call __libc_start_main` 직전에 `rdi`에 로드되는 값**만 확인한다. 그게 `main`이다. 나머지 명령어는 "레지스터 세팅용 배관"이라는 것만 인지하고 넘어간다.

## 단계별 절차

**1) _start 디스어셈블리 확보**
```bash
objdump -d -M intel ./chall | grep -A18 '<_start>:'
```

**2) __libc_start_main 호출 직전 rdi 로드 위치 찾기**
```bash
objdump -d -M intel ./chall | grep -A18 '<_start>:' | grep -B1 'call.*libc_start_main\|call.*<[0-9a-f]* <__libc_start_main'
```
`lea rdi, [rip+0x...]` 줄 뒤에 `# <main>`처럼 objdump가 대상 심볼 이름을 주석으로 붙여준다(strip 안 된 경우).

**3) GDB로 실제 레지스터 값 확인**
```gdb
(gdb) break *_start
(gdb) run
(gdb) x/8i $pc
(gdb) break *(_start+0x28)   ; call 직전 주소로 조정
(gdb) continue
(gdb) info registers rdi
```
`info registers rdi`로 나온 주소가 `main`이다. `x/3i $rdi`로 그 주소를 디스어셈블해서 `push rbp` / `endbr64` 같은 함수 프롤로그가 나오는지 확인하면 진짜 함수 시작점이 맞는지 재검증할 수 있다.

**4) strip된 바이너리에서 __libc_start_main 자체도 이름이 없을 때**
정적 링킹 + strip 조합이면 `__libc_start_main`도 이름 없이 `sub_XXXX`로 보인다. 이때는 `_start` 패턴(레지스터 세팅 후 CALL 하나) 자체를 지문(fingerprint)으로 삼는다 — `_start`는 함수 하나만 호출하고 리턴하지 않는(그 뒤에 `ud2`나 패딩만 있는) 아주 독특한 모양이라 다른 함수와 헷갈리기 어렵다.

## 명령어/단축키
```bash
objdump -d -M intel ./chall | grep -A18 '<_start>:'
readelf -h ./chall | grep Entry
```
GDB: `break *_start`, `x/8i $pc`, `info registers rdi`, `stepi`

## 출력 해석
- `_start` 안에서 CALL 대상이 `__libc_start_main`이 아니라 다른 이름(예: musl libc의 `__libc_start_main` 구현은 다르게 생겼음)이면, glibc가 아닌 다른 C 라이브러리(musl 등)로 빌드된 것일 수 있다 — 임베디드/Alpine Linux 바이너리에서 흔하다.
- `_start`에서 `call` 이후 코드가 없거나 `hlt`/`ud2`만 있다면 정상이다 — `__libc_start_main`은 내부에서 `exit()`까지 호출하고 절대 리턴하지 않으므로, 컴파일러가 그 뒤에 도달 불가능한 코드로 취급해 최소한의 패딩만 남긴다.

## 흔한 실수
- `_start`가 `main`을 직접 호출한다고 착각하는 것 — 실제로는 `__libc_start_main`(또는 정적 바이너리의 동일 역할 함수)이라는 중간 단계를 항상 거친다.
- `xor ebp, ebp` 같은 명령어를 보고 "여기서 뭔가 중요한 계산을 하나?"라고 의심하며 시간을 쓰는 것 — 이건 그냥 스택 프레임 종료 표시일 뿐 프로그램 로직과 무관하다.
- `_start`의 인자 순서를 아무 호출 규약이나 대입해서 착각하는 것 — x86-64 SysV ABI 기준으로 정수/포인터 인자는 RDI, RSI, RDX, RCX, R8, R9 순서로 전달된다는 걸 정확히 적용해야 몇 번째 인자가 `main`인지 헷갈리지 않는다(첫 번째 인자, 즉 RDI).

## 막혔을 때 다음 체크
- entry point부터 main까지 전체 그림을 다시 보고 싶으면 → [REV-0097 ELF Entry Point에서 main까지](./rev-0097-entry-to-main.md)
- `__libc_start_main`의 정확한 시그니처와 glibc 버전별 차이가 궁금하면 → [REV-0099 __libc_start_main이 무엇이고 main을 찾는 법](./rev-0099-libc-start-main.md)
- CALL 명령어의 인자 전달 규약 자체가 궁금하면 → REV-0071(CALL 명령어) 참고
- stripped 바이너리에서 이 과정을 어떻게 진행하는지 → [REV-0010 stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)

## 미니 예제
```bash
$ objdump -d -M intel chall | grep -A14 '<_start>:'
0000000000001060 <_start>:
    1060:	f3 0f 1e fa          	endbr64
    1064:	31 ed                	xor    ebp,ebp
    1066:	49 89 d1             	mov    r9,rdx
    1069:	5e                   	pop    rsi
    106a:	48 89 e2             	mov    rdx,rsp
    106d:	48 83 e4 f0          	and    rsp,0xfffffffffffffff0
    1071:	50                   	push   rax
    1072:	54                   	push   rsp
    1073:	4c 8d 05 c6 01 00 00 	lea    r8,[rip+0x1c6]        # 1240 <__libc_csu_fini>
    107a:	48 8d 0d 4f 01 00 00 	lea    rcx,[rip+0x14f]        # 11d0 <__libc_csu_init>
    1081:	48 8d 3d c1 00 00 00 	lea    rdi,[rip+0xc1]         # 1149 <main>
    1088:	ff 15 12 2f 00 00    	call   QWORD PTR [rip+0x2f12] # 3fa0 <__libc_start_main@GLIBC_2.34>
```
마지막 세 줄만 보면 된다: `rdi`에 `main`(0x1149) 주소를 넣고 `__libc_start_main`을 호출한다. 나머지는 배관 코드다.

## 관련 글
- [REV-0097 — ELF Entry Point에서 main까지](./rev-0097-entry-to-main.md)
- [REV-0099 — __libc_start_main이 무엇이고 main을 찾는 법](./rev-0099-libc-start-main.md)
- [REV-0092 — objdump 기본 사용법](./rev-0092-objdump-basics.md)
- [REV-0010 — stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)

## 출처/검증
- `_start` 어셈블리 구현: glibc 소스 `sysdeps/x86_64/start.S` 기준 (2026-09-08 검증).
- SysV AMD64 ABI 레지스터 인자 전달 규약 및 16바이트 스택 정렬 요구사항: System V Application Binary Interface AMD64 Architecture Processor Supplement 기준.
- `endbr64`/CET: Intel 소프트웨어 개발자 매뉴얼 "Control-flow Enforcement Technology" 챕터 기준.
