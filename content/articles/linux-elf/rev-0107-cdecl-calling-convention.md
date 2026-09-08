---
id: REV-0107
title: "Linux x86 cdecl Calling Convention"
slug: "rev-0107-cdecl-calling-convention"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86]
format: [ELF]
tools: [IDA, GDB, objdump]
keywords: ["cdecl", "x86 calling convention", "32비트 함수 호출 규약", "스택 인자 전달", "caller cleanup", "add esp"]
aliases: ["cdecl이란", "32비트 함수 호출 규약", "x86 인자 전달 순서", "add esp 0xc 이유"]
symptom_keywords: ["인자가 전부 스택에 push되는 이유", "call 다음 줄에 add esp가 있는 이유", "32비트 코드에서 rdi rsi가 안 보이는 이유"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
32비트 리눅스(x86) ELF에서 함수 인자는 레지스터가 아니라 전부 **스택에 오른쪽 인자부터 순서대로 push**되어 전달되고, 반환값은 `EAX`에 담기며, 스택 정리는 **호출한 쪽(caller)** 이 `call` 직후 `add esp, N`으로 직접 처리하는 것이 cdecl 규약의 핵심이다.

## 언제 검색해야 하나
- 32비트 바이너리 디스어셈블리에서 `call` 직전에 `push` 명령어가 여러 번 연달아 나오는데 왜 x64처럼 레지스터에 안 담고 스택에 쌓는지 궁금할 때
- `call func` 바로 다음 줄에 `add esp, 0xc` 같은 코드가 항상 붙어있는 이유가 궁금할 때
- 같은 C 코드인데 32비트로 컴파일하면 64비트(SysV AMD64, REV-0106)와 완전히 다른 어셈블리가 나오는 이유를 알고 싶을 때
- Windows `stdcall`/`fastcall`과 리눅스 `cdecl`이 뭐가 다른지 궁금할 때(참고용으로만 다룸, 본문은 리눅스 cdecl에 집중)

## 핵심 개념

### cdecl이란
cdecl(C declaration)은 C 컴파일러의 기본 함수 호출 규약으로, 32비트 x86에서 가장 널리 쓰인다. 리눅스 32비트 ELF(`gcc -m32`로 컴파일한 바이너리 등)의 일반 함수 호출은 특별한 지정이 없는 한 기본적으로 이 규약을 따른다. 핵심 규칙은 세 가지다.
1. 모든 인자는 **스택**을 통해 전달한다(정수든 포인터든 레지스터를 쓰지 않는다).
2. 인자는 **오른쪽에서 왼쪽 순서로 push**한다 — 즉 마지막 인자가 가장 먼저 스택에 올라간다.
3. 함수가 끝난 뒤 스택에 쌓인 인자를 치우는 책임은 **호출한 쪽(caller)** 에 있다.

### 인자를 오른쪽부터 push하는 이유
`f(a, b, c)`를 호출한다면 어셈블리는 다음과 같은 순서로 나온다:
```asm
push c
push b
push a
call f
add  esp, 0xc     ; 인자 3개 * 4바이트 = 0xc만큼 스택 되돌리기
```
가장 마지막에 push된 `a`가 스택의 맨 위(가장 낮은 주소)에 오게 되므로, 함수 안에서는 `[esp+4]`(또는 프레임 포인터를 쓴다면 `[ebp+8]`)가 첫 번째 인자 `a`, 그다음이 `b`, `c` 순서로 접근된다. 오른쪽부터 push하는 이유 중 하나는 가변 인자 함수(`printf(fmt, ...)`) 때문이다 — 포맷 문자열 `fmt`가 항상 스택에서 가장 먼저(가장 낮은 주소에 가깝게) 접근 가능해야, `printf` 내부 구현이 인자 개수를 몰라도 `fmt`부터 안정적으로 찾아 읽을 수 있다.

### 왜 호출자가 스택을 정리하나(Caller Cleanup)
`call` 명령어가 끝나고 함수가 리턴해도, `push`로 쌓아올린 인자들은 스택에 그대로 남아있다. 누군가는 `ESP`를 원래 위치로 되돌려야 하는데, cdecl은 이 책임을 **호출한 쪽**에 맡긴다. 그래서 `call f` 바로 다음에는 거의 항상 `add esp, N`(N = push한 바이트 수의 합) 코드가 따라붙는다.

이 방식의 장점은 **가변 인자 함수를 지원할 수 있다**는 것이다 — 호출된 함수(`printf`)는 자기가 몇 개의 인자를 받았는지 스택만 봐서는 정확히 알 수 없지만(포맷 문자열을 파싱해서 알아내야 함), 스택 정리는 애초에 몇 개를 push했는지 아는 호출자가 하므로 문제가 없다. 반대로 Windows의 `stdcall`처럼 **호출된 함수가 스스로 스택을 정리(`ret N`)** 하는 규약은 코드 크기는 조금 줄지만 가변 인자 함수를 지원할 수 없다.

### 여러 번 호출되는 함수에서 add esp가 합쳐지는 경우
컴파일러가 최적화를 하거나, 같은 함수를 연달아 여러 번 호출하는 코드에서는 매번 `add esp`를 하지 않고, 여러 호출의 인자를 한꺼번에 정리하도록 코드를 재배치하는 경우도 있다. 이때는 `call` 뒤에 바로 `add esp`가 안 보일 수 있으니, 조금 더 아래쪽 코드까지 같이 살펴봐야 한다.

### 반환값과 스택 프레임
반환값은 `EAX`에 담긴다(64비트 값이 필요하면 `EDX:EAX`). 스택 프레임 구성은 x64와 개념적으로 동일하다:
```asm
push ebp
mov  ebp, esp
sub  esp, N        ; 로컬 변수 공간
; ...
leave              ; mov esp, ebp ; pop ebp
ret
```
프레임 포인터(`EBP`) 기준으로 `[ebp+8]`부터가 인자, `[ebp-4]`, `[ebp-8]`처럼 음수 오프셋이 로컬 변수라는 배치는 32비트에서도 그대로 성립한다.

### SysV AMD64(REV-0106)와의 결정적 차이
| 항목 | x86 cdecl (32비트) | SysV AMD64 (64비트, REV-0106) |
|---|---|---|
| 인자 전달 | 전부 스택 | 처음 6개는 레지스터(`RDI`~`R9`), 이후 스택 |
| 스택 정리 | 호출자(caller)가 `add esp, N` | 애초에 스택에 안 쌓았으므로 대개 필요 없음(7개 이상일 때만 정리) |
| 반환값 | `EAX`(64비트 값은 `EDX:EAX`) | `RAX`(128비트 값은 `RDX:RAX`) |
| 레지스터 개수 | 8개(`EAX`~`EDI`) | 16개(`RAX`~`R15`) |

같은 소스 코드라도 32비트로 컴파일된 바이너리와 64비트로 컴파일된 바이너리는 인자 전달 부분의 어셈블리가 완전히 다르게 생긴다. 32비트 코드에서 `RDI`, `RSI` 같은 인자 레지스터를 찾으려 하면 안 되고, 반대로 64비트 코드에서 `push` 인자 나열을 찾으려 해도 안 된다(7번째 인자 이상이 아닌 이상).

### 참고: Windows의 다른 규약들
Windows 32비트에는 cdecl 외에도 `stdcall`(callee cleanup, Win32 API 대부분), `fastcall`(처음 두 인자를 `ECX`/`EDX`로), `thiscall`(C++ 멤버 함수, `this`를 `ECX`로) 등이 섞여 쓰인다. 이 문서는 리눅스 ELF 32비트를 기준으로 cdecl만 다루며, 어떤 규약인지는 반환 후 스택 정리 위치(`call` 직후 vs 함수 자체의 `ret N`)로 구분할 수 있다는 정도만 참고로 알아두면 된다.

## 화면/코드에서 보이는 징후
- `call func` 이전에 `push` 명령어가 인자 개수만큼 연달아 나옴
- `call func` 직후에 `add esp, 0x4`, `add esp, 0xc` 같은 코드가 바로 따라붙음
- 함수 내부에서 인자에 접근할 때 `[ebp+8]`, `[ebp+0xc]`처럼 `EBP`에 양수 오프셋을 더한 형태로 접근
- 반환값을 쓰는 코드가 `EAX`(또는 `AL`, `AX`)를 그대로 다음 연산에 사용

## 가장 먼저 할 것
32비트 바이너리인지부터 확인한다(`file ./chall` 결과에 `ELF 32-bit`). 맞다면 `call` 직전의 `push` 나열을 아래→위(스택에 나중에 올라가는 것이 먼저 실행되는 순서, 즉 코드 순서 그대로)로 읽되, **실제 함수 인자 순서는 반대로 해석**해야 한다는 점을 기억한다 — 코드에서 가장 마지막에 `push`된 값이 함수의 첫 번째 인자다.

## 단계별 절차

**1) push 나열을 함수 인자 순서로 재정렬**
```asm
push c    ; 3번째 인자
push b    ; 2번째 인자
push a    ; 1번째 인자
call f
```
코드에 쓰인 순서와 실제 인자 순서가 반대임을 유의한다.

**2) GDB에서 call 직전 스택 값 확인**
```gdb
break *0x<call주소>
run
x/3xw $esp
```
`call` 실행 직전이므로 `[esp]`가 가장 최근에 push된 값(=함수의 첫 번째 인자), 그다음이 두 번째, 세 번째 인자 순서로 보인다.

**3) 함수 진입 후 인자 확인**
```gdb
break f
run
x/3xw $esp+4
```
`call`이 리턴 주소를 push했으므로, 함수 진입 직후에는 `[esp]`가 리턴 주소, `[esp+4]`부터가 첫 번째 인자다. `EBP` 기반 프레임을 쓰는 함수라면 프롤로그(`push ebp; mov ebp, esp`) 이후에는 `[ebp+8]`부터가 첫 번째 인자가 된다.

**4) 반환값 확인**
```gdb
finish
print $eax
```

## 명령어/단축키
```bash
file ./chall     # ELF 32-bit 확인
```
GDB: `x/Nxw $esp`, `info registers eax`, `finish`, `p $eax`

## 출력 해석
- `x/3xw $esp`는 `ESP`부터 4바이트(word) 단위로 3개 값을 16진수로 보여준다 — 함수 호출 직전이라면 이 값들이 push된 인자들이다.
- `add esp, 0xc`에서 `0xc`(12바이트)는 인자 3개 × 4바이트를 의미하므로, 이 값을 4로 나누면 push된 인자 개수를 역산할 수 있다.

## 흔한 실수
- push된 순서를 그대로 "1번째, 2번째 인자"로 읽는 것 — 코드에 먼저 나오는 `push`가 오히려 **마지막** 인자다.
- 32비트 코드에서 `RDI`, `ESI` 같은 것을 찾으려는 것 — cdecl은 레지스터로 인자를 넘기지 않는다(단, 컴파일러가 최적화 과정에서 레지스터를 임시로 쓰는 것과 "호출 규약상 인자 레지스터"는 다른 이야기다).
- `add esp, N`이 안 보인다고 당황하는 것 — 최적화나 여러 호출을 묶어 처리하는 경우 스택 정리 코드가 뒤로 밀리거나 합쳐질 수 있다. 조금 더 아래쪽까지 살펴봐야 한다.
- 반환값이 `EAX`가 아니라 스택에 있을 거라 생각하는 것 — 정수/포인터 반환값은 cdecl에서도 항상 `EAX`(또는 `EDX:EAX`)다.

## 막혔을 때 다음 체크
- 같은 개념의 64비트 버전이 궁금하다면 → REV-0106 SysV AMD64 Calling Convention
- `main`의 `argc`/`argv`가 이 규약으로 어떻게 전달되는지 → REV-0108 argc argv envp를 어셈블리에서 찾는 법
- CALL 명령어 자체의 동작 → REV-0071 CALL: 함수 호출, 반환 주소, 인자 추적

## 미니 예제
```c
int add3(int a, int b, int c) { return a + b + c; }
int main(void) { return add3(1, 2, 3); }
```
```asm
; add3(1, 2, 3) 호출부
push 3
push 2
push 1
call add3
add  esp, 0xc

; add3 본문
push ebp
mov  ebp, esp
mov  eax, [ebp+8]    ; a (1)
add  eax, [ebp+0xc]  ; b (2)
add  eax, [ebp+0x10] ; c (3)
pop  ebp
ret
```
`push 3; push 2; push 1` 순서로 스택에 올라가지만, 함수 안에서는 `[ebp+8]=a=1`, `[ebp+0xc]=b=2`, `[ebp+0x10]=c=3`으로 정확히 원래 순서대로 접근된다.

## 관련 글
- REV-0106 — SysV AMD64 Calling Convention
- REV-0108 — argc argv envp를 어셈블리에서 찾는 법
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- cdecl 인자 전달 순서 및 caller cleanup 규칙: Intel/AT&T 어셈블리 관례 및 System V ABI Intel386 Architecture Processor Supplement 기준.
- 스택 프레임(`push ebp; mov ebp, esp` 관례) 및 `leave` 명령: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2 기준 (2026-09-08 검증).
