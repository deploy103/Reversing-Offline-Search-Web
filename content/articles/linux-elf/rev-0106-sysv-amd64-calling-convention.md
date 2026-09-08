---
id: REV-0106
title: "SysV AMD64 Calling Convention"
slug: "rev-0106-sysv-amd64-calling-convention"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x64]
format: [ELF]
tools: [IDA, GDB, Pwndbg, objdump]
keywords: ["SysV AMD64", "System V ABI", "x64 calling convention", "RDI RSI RDX RCX R8 R9", "caller-saved", "callee-saved", "red zone", "레드존", "스택 정렬", "syscall calling convention"]
aliases: ["sysv abi", "리눅스 x64 함수 호출 규약", "x64 인자 전달 순서", "amd64 calling convention"]
symptom_keywords: ["함수 인자가 rdi rsi에 들어가는 이유", "레지스터로 인자를 전달하는 이유", "call 하기 전에 rsp가 16의 배수여야 하는 이유"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
리눅스 x86-64(AMD64) 바이너리에서 함수 인자는 순서대로 `RDI, RSI, RDX, RCX, R8, R9` 레지스터에 담기고, 반환값은 `RAX`(필요하면 `RDX:RAX`)에 담기며, 이 규칙(System V AMD64 ABI Calling Convention)만 외우면 디스어셈블리에서 어떤 함수가 몇 개의 인자로 무엇을 넘기는지 바로 읽어낼 수 있다.

## 언제 검색해야 하나
- 디스어셈블리에서 `call printf` 직전에 `mov edi, ...`, `mov rsi, ...` 같은 코드가 반복적으로 나오는데 이게 왜 이 순서인지 궁금할 때
- `RDI`가 왜 항상 "첫 번째 인자" 취급을 받는지, `RCX`는 왜 네 번째인지 근거가 궁금할 때
- 함수 호출 직전에 `and rsp, 0xfffffffffffffff0` 같은 스택 정렬 코드가 왜 있는지 이해하고 싶을 때
- syscall(시스템 콜) 호출과 일반 함수 호출의 인자 전달 방식이 왜 미묘하게 다른지 궁금할 때
- 32비트 리눅스(cdecl)와 64비트 리눅스(SysV AMD64)의 인자 전달 방식 차이가 궁금할 때 (32비트는 `./rev-0107-cdecl-calling-convention.md` 참고)

이 문서는 x64 함수 호출 규약의 **심화/정리판**이다. 처음 스택과 리턴 주소 개념부터 배우고 싶다면 이 저장소의 초급 문서(예: 인자와 리턴 위치를 다루는 기초 문서, 아직 작성 전이라면 추후 링크 예정)를 먼저 보는 것이 좋다.

## 핵심 개념

### 왜 레지스터로 인자를 전달하나
32비트 x86(cdecl, REV-0107 참고)에서는 함수 인자를 전부 스택에 쌓아서 전달했다. 그런데 스택에 쓰고 읽는 것은 레지스터를 쓰는 것보다 메모리 접근이 필요해 상대적으로 느리다. x86-64로 오면서 레지스터 개수가 8개(`RAX`~`RDI`)에서 16개(`RAX`~`R15`)로 늘어났고, System V AMD64 ABI는 이 여유를 이용해 **처음 몇 개의 인자는 레지스터로, 그 이상만 스택으로** 넘기도록 정했다. 이 편이 훨씬 빠르고, 디스어셈블리를 읽을 때도 함수 프롤로그의 스택 조작을 훨씬 적게 보게 된다.

### 정수/포인터 인자 전달 순서
왼쪽부터 순서대로 다음 레지스터를 채운다:
```
1번째 인자: RDI
2번째 인자: RSI
3번째 인자: RDX
4번째 인자: RCX
5번째 인자: R8
6번째 인자: R9
7번째 인자부터: 스택 (오른쪽 인자부터 push, 즉 마지막 인자가 가장 먼저 push됨)
```
32비트 레지스터로만 쓰이는 인자(`int`)라면 `EDI`, `ESI`, `EDX`, `ECX`, `R8D`, `R9D`처럼 하위 32비트 이름이 쓰인다. `char`/`short`처럼 더 작은 타입도 대개 32비트로 확장되어 같은 레지스터에 담긴다.

예시: `int add(int a, int b, int c)`를 호출하는 코드는
```asm
mov edx, 3      ; c = 3
mov esi, 2      ; b = 2
mov edi, 1      ; a = 1
call add
```
처럼 나타난다(컴파일러 최적화에 따라 대입 순서는 바뀔 수 있지만 최종적으로 `edi=a, esi=b, edx=c`가 되는 것은 동일하다).

### 부동소수점 인자: XMM0~XMM7
`double`, `float` 인자는 정수 레지스터가 아니라 **SSE 레지스터** `XMM0`부터 `XMM7`까지 순서대로 채워진다. 정수 인자와 부동소수점 인자는 **별개의 카운터**로 채워지므로, `void f(int a, double b, int c)`라면 `a`는 `RDI`, `b`는 `XMM0`, `c`는 `RSI`에 들어간다(정수 두 번째 인자이므로).

가변 인자 함수(`printf`처럼 `...`를 받는 함수)를 호출할 때는 추가로 `AL` 레지스터에 "사용한 벡터(XMM) 레지스터의 개수"를 넣어줘야 한다는 규칙이 있다. `printf`처럼 포맷 문자열에 부동소수점이 하나도 없다면 관례적으로 `AL`을 `0`으로 세팅하는 `xor eax, eax` 코드가 `call printf` 직전에 자주 보이는데, 이게 바로 이 규칙 때문이다.

### 반환값
정수/포인터 반환값은 `RAX`(또는 32비트라면 `EAX`)에 담긴다. 128비트 정수(`__int128`) 등 더 큰 값은 `RDX:RAX` 두 레지스터를 함께 쓴다. 구조체를 값으로 반환하는 경우, 구조체가 작으면(16바이트 이하) 레지스터 조합(`RAX`/`RDX` 또는 `XMM0`/`XMM1`)에 나눠 담기고, 크면 호출자가 미리 준비한 숨은 버퍼 주소를 첫 인자(`RDI`)로 암묵적으로 추가 전달하고 그 버퍼에 결과를 채우는 방식(hidden pointer)을 쓴다. 부동소수점 반환값은 `XMM0`(필요하면 `XMM0`/`XMM1`)에 담긴다.

### Caller-saved vs Callee-saved 레지스터
함수를 호출하고 나면 어떤 레지스터는 값이 유지된다는 보장이 있고, 어떤 레지스터는 호출된 함수가 마음대로 덮어써도 되는지가 정해져 있다.
- **Caller-saved(volatile, 호출자가 저장)**: `RAX`, `RCX`, `RDX`, `RSI`, `RDI`, `R8`~`R11`. 함수를 호출한 뒤에도 이 값들이 필요하다면 **호출하는 쪽**이 호출 전에 스택 등에 미리 저장해둬야 한다. 인자로 쓰이는 레지스터가 대부분 여기 속하는 것은 우연이 아니다 — 인자는 호출된 함수가 다 쓰고 나면 필요 없어지는 경우가 많기 때문이다.
- **Callee-saved(non-volatile, 호출된 함수가 저장)**: `RBX`, `RBP`, `RSP`, `R12`~`R15`. 함수 안에서 이 레지스터들을 쓰려면, 함수는 시작할 때 원래 값을 저장(보통 `push`)해두고 끝나기 전에 반드시 복원(`pop`)해야 한다. 디스어셈블리에서 함수 시작부에 `push rbx`, `push r12` 같은 코드가 보이고 끝부분에 대칭적으로 `pop r12`, `pop rbx`가 보이면 이 레지스터들을 함수 내부에서 실제로 사용했다는 뜻이다.

`RSP`(스택 포인터)는 당연히 항상 보존돼야 하고, `RBP`는 프레임 포인터로 관례적으로 callee-saved로 취급된다.

### 스택 정렬(Stack Alignment) 규칙
`call` 명령어가 실행되는 순간(즉 호출된 함수의 첫 명령어가 실행되기 직전) `RSP`는 반드시 **16의 배수에서 8을 뺀 값**, 다시 말해 `call`이 리턴 주소를 push한 뒤 함수 진입 시점에는 `(RSP % 16) == 8`이어야 한다는 것이 ABI 규칙이다. 다르게 표현하면, `call` 실행 직전에는 `RSP % 16 == 0`이어야 한다. 이는 SSE 명령어(`movaps` 등)가 16바이트 정렬된 메모리만 다루도록 최적화되어 있어서, 정렬이 깨지면 크래시가 나기 때문이다.

이 규칙 때문에 함수 프롤로그에서 `sub rsp, N`으로 로컬 변수 공간을 확보할 때 컴파일러가 `N`을 16의 배수(혹은 그 근처로 맞춰떨어지는 값)로 잡는 경우가 많고, 가끔 스택을 강제로 정렬시키는 `and rsp, 0xfffffffffffffff0` 같은 코드가 함수 진입부에 보이기도 한다(정렬이 보장되지 않는 상황, 예: 가변 길이 배열을 쓰는 함수 등). 리버싱 중 이런 코드를 보면 "인자 개수와 무관한 스택 정렬 보정 코드"로 이해하면 된다.

### Red Zone(레드존)
System V AMD64 ABI는 **leaf 함수**(다른 함수를 호출하지 않는 함수)에 한해, `RSP` 아래쪽 128바이트를 "함수를 더 호출하지 않고도 안전하게 임시로 쓸 수 있는 영역"으로 인정한다. 이 영역을 레드존이라고 부른다. 레드존 안에서는 `sub rsp, N`으로 스택을 미리 줄이지 않고도 `[rsp-8]`, `[rsp-16]` 같은 식으로 바로 값을 저장할 수 있다. 디스어셈블리에서 아주 짧은 함수가 `sub rsp`를 전혀 안 하는데도 `rsp` 아래 음수 오프셋으로 메모리에 값을 쓰는 게 보인다면 레드존을 활용하고 있는 것이다. 다른 함수를 호출하는 함수(leaf가 아닌 함수)에서는 그 `call`이 레드존을 덮어써버릴 수 있으므로 이 최적화를 쓰지 않는다.

### 함수 프롤로그/에필로그의 전형적인 모습
```asm
; 프롤로그
push rbp
mov  rbp, rsp
sub  rsp, 0x20        ; 로컬 변수용 공간 확보

; ... 함수 본문 ...

; 에필로그
leave                  ; mov rsp, rbp ; pop rbp 와 동일
ret
```
`leave`는 `mov rsp, rbp`로 스택을 프레임 시작 지점으로 되돌리고 `pop rbp`로 호출자의 `RBP`를 복원하는 두 동작을 한 번에 수행하는 명령이다. 최적화가 켜진 코드에서는 `RBP`를 프레임 포인터로 아예 안 쓰고(`-fomit-frame-pointer`), `RSP`를 직접 계산해서 접근하는 경우도 많다.

### 시스템 콜(syscall)은 다른 규칙을 쓴다
일반 함수 호출과 커널에 직접 요청하는 시스템 콜은 **호출 규약이 다르다.** 시스템 콜 번호는 `RAX`에 넣고, 인자는:
```
1번째 인자: RDI
2번째 인자: RSI
3번째 인자: RDX
4번째 인자: R10   (RCX가 아님!)
5번째 인자: R8
6번째 인자: R9
```
`syscall` 명령어 자체가 리턴 주소를 `RCX`에, 플래그를 `R11`에 저장하는 x86-64 하드웨어 규약 때문에, 커널은 네 번째 인자 자리에 `RCX` 대신 `R10`을 쓰도록 정했다. `ltrace`/`strace`(REV-0111, REV-0112)로 관찰되는 인자 순서를 코드와 대조할 때 이 차이를 꼭 기억해야 한다 — `strace`로 보는 것은 이 syscall 규약이고, 코드에서 `libc` 래퍼 함수(예: `read()`)를 호출하는 부분은 위에서 설명한 일반 함수 호출 규약(`RCX` 사용)이다. `libc`의 `read()` 래퍼 함수 내부에서 인자를 `R10`으로 옮겨 담은 뒤에야 실제 `syscall` 명령을 실행한다.

## 화면/코드에서 보이는 징후
- `call` 직전에 `mov edi, ...` / `mov esi, ...` / `mov edx, ...` 순서로 값이 채워지는 코드가 반복됨
- 부동소수점을 다루는 함수 호출 전에 `movsd xmm0, ...` 같은 코드가 보임
- 함수 진입부에 `push rbx`, `push r12` 등 callee-saved 레지스터를 저장하는 코드, 종료부에 대칭적인 `pop`이 있음
- `call` 직전에 `and rsp, 0xfffffffffffffff0`처럼 스택을 16으로 정렬하는 코드가 보임
- IDA 디컴파일러가 함수 프로토타입을 `int func(a1, a2, a3, ...)` 형태로 자동 추론해 보여줌 — 이 추론이 바로 레지스터 사용 패턴을 근거로 한다

## 가장 먼저 할 것
분석 중인 함수 호출부에서 `call` 직전 몇 줄을 보고, `RDI`부터 순서대로 어떤 값이 채워지는지 나열해본다. 그 값들이 상수인지, 스택 변수 주소(`lea rax, [rbp-0x20]; mov rdi, rax`)인지, 다른 함수의 반환값(`RAX`를 그대로 옮긴 것)인지 파악하면 그 함수 호출의 의미(어떤 데이터를 어디로 넘기는지)를 코드 몇 줄만 보고도 재구성할 수 있다.

## 단계별 절차

**1) call 직전 레지스터 세팅 코드 역순으로 읽기**
IDA/objdump에서 `call` 명령어를 찾고, 그 바로 위 몇 줄을 보며 `RDI, RSI, RDX, RCX, R8, R9` 각각에 무슨 값이 들어가는지 표시해본다(컴파일러가 항상 이 순서로 코드를 쓰는 것은 아니므로 레지스터 이름 기준으로 대응시킨다).

**2) GDB에서 call 직전에 멈춰서 실제 값 확인**
```gdb
break *0x<call주소>
run
info registers rdi rsi rdx rcx r8 r9
```
Pwndbg라면 `break` 후 자동으로 레지스터 패널에 이 값들이 다 보인다.

**3) 문자열/포인터 인자는 역참조해서 실제 값 확인**
```gdb
x/s $rdi
x/s $rsi
```

**4) 스택으로 넘어가는 7번째 이후 인자 확인**
```gdb
x/2gx $rsp
```
`call` 실행 직전 기준으로 `[rsp]`에 7번째 인자, `[rsp+8]`에 8번째 인자가 있다(호출 규약상 `call`이 리턴 주소를 push하기 전 상태 기준).

**5) 반환값 확인**
```gdb
finish
print $rax
```
`finish`는 현재 함수가 리턴할 때까지 실행한 뒤 멈추고, 반환값을 `Value returned is $1 = ...` 형태로 바로 보여준다.

## 명령어/단축키
GDB/Pwndbg: `info registers`, `x/s $rdi`, `x/gx $rsp`, `finish`, `p $rax`

## 출력 해석
- `info registers`에서 `rdi`, `rsi`, `rdx` 값이 작은 정수라면 길이/개수/플래그 같은 값일 가능성이, 큰 16진수(스택이나 힙 범위)라면 포인터일 가능성이 높다.
- `x/s $rdi` 결과가 사람이 읽을 수 있는 문자열로 나오면 그 인자는 `char*`(문자열)이다.
- `finish` 이후 `Value returned is $1 = 0x0`이면 함수가 실패(NULL/0)를 반환했다는 뜻으로 흔히 해석된다(함수의 관례에 따라 다름).

## 흔한 실수
- 32비트 x86 cdecl 규약(모든 인자를 스택으로)과 헷갈려서 x64 코드에서도 스택 인자를 찾으려 헤매는 것 — x64는 처음 6개 정수 인자가 레지스터에 있다.
- 부동소수점 인자도 정수 레지스터(`RDI` 등)에서 찾으려 하는 것 — `XMM0`~`XMM7`을 따로 봐야 한다.
- syscall 인자 규약(`R10` 사용)과 일반 함수 호출 규약(`RCX` 사용)을 혼동하는 것 — `strace` 출력과 디스어셈블리를 같이 볼 때 이 차이 때문에 혼란이 생기기 쉽다.
- Caller-saved 레지스터의 값이 함수 호출 후에도 유지될 거라고 가정하는 것 — `call` 이후 `RCX`, `RDX`, `R8`~`R11` 등의 값은 보장되지 않는다.

## 막혔을 때 다음 체크
- 32비트 x86의 cdecl 규약과 비교하고 싶다면 → REV-0107 Linux x86 cdecl Calling Convention
- `main`의 `argc`/`argv`/`envp`가 이 규약으로 어떻게 전달되는지 → REV-0108 argc argv envp를 어셈블리에서 찾는 법
- CALL 명령어 자체(리턴 주소 push 등)를 더 알고 싶다면 → REV-0071 CALL: 함수 호출, 반환 주소, 인자 추적
- 인자와 리턴 위치에 대한 더 기초적인 개념은 `../binary-basics/rev-0032-args-and-return-location.md`(작성 예정, 아직 없다면 이 문서로 대체) 참고.

## 미니 예제
```c
int add3(int a, int b, int c) { return a + b + c; }
int main(void) { return add3(1, 2, 3); }
```
```asm
; add3(1, 2, 3) 호출부
mov edx, 3
mov esi, 2
mov edi, 1
call add3

; add3 본문
push rbp
mov  rbp, rsp
mov  [rbp-4], edi   ; a
mov  [rbp-8], esi   ; b
mov  [rbp-0xc], edx ; c
mov  eax, [rbp-4]
add  eax, [rbp-8]
add  eax, [rbp-0xc]
pop  rbp
ret
```
`edi=1, esi=2, edx=3`이 채워진 뒤 `call add3`가 실행되고, `add3`은 그 값들을 다시 로컬 스택 변수에 옮겨 저장한 뒤 계산해 `eax`에 결과를 담아 반환한다.

## 관련 글
- REV-0107 — Linux x86 cdecl Calling Convention
- REV-0108 — argc argv envp를 어셈블리에서 찾는 법
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0100 — PLT와 GOT 기초

## 출처/검증
- 레지스터 인자 순서, caller/callee-saved 구분, 스택 정렬, 레드존: System V Application Binary Interface, AMD64 Architecture Processor Supplement (x86-64 psABI), "Register Usage" 및 "The Stack Frame" 절 기준.
- syscall 인자 규약(`R10` 사용): Linux 커널 `x86-64 syscall(2)` 관례 및 `man 2 syscall` "Architecture calling conventions" 절 기준.
- 가변 인자 함수 `AL` 레지스터 규칙: x86-64 psABI "Parameter Passing" 절 기준 (2026-09-08 검증).
