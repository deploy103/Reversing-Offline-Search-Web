---
id: REV-0032
title: "함수 인자와 반환값이 어디에 있는지"
slug: "rev-0032-args-and-return-location"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["calling convention", "호출 규약", "함수 인자", "반환값", "rdi rsi rdx rcx r8 r9", "rcx rdx r8 r9", "rax 반환값"]
aliases: ["함수 인자 어디에 있나요", "리턴값이 왜 eax에 있나요", "sysv 호출규약", "windows x64 호출규약"]
symptom_keywords: ["함수 호출 전에 인자가 어느 레지스터에 들어가는지 모르겠음", "rdi rsi가 왜 나오는지 모르겠음", "rcx rdx r8 r9가 왜 나오는지 모르겠음", "반환값이 왜 eax rax에 있는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
함수를 호출하기 직전에 인자는 정해진 규칙(**호출 규약, calling convention**)에 따라 특정 레지스터(그리고 넘치면 스택)에 실리고, 반환값은 거의 항상 **RAX(정수/포인터)** 에 담겨 돌아온다 — 이 규칙은 Linux(SysV)와 Windows에서 서로 다르다.

## 언제 검색해야 하나
- `call` 직전에 `mov edi, ...`, `mov esi, ...` 같은 코드가 왜 나오는지, 이게 인자를 준비하는 코드라는 걸 확인하고 싶을 때
- Windows 바이너리에서는 `rcx`, `rdx`가, Linux 바이너리에서는 `rdi`, `rsi`가 인자로 쓰이는 이유가 헷갈릴 때
- 함수가 끝난 직후 `eax`/`rax` 값을 봐야 하는 이유, 반환값이 어디 담기는지 궁금할 때
- IDA/Ghidra 디컴파일에서 `func(a1, a2, a3)`처럼 인자 개수와 순서가 자동으로 추론된 걸 보고 원리가 궁금할 때

## 핵심 개념
함수를 호출하는 쪽(caller)과 호출당하는 쪽(callee)이 "인자를 어디에 놓고, 반환값을 어디서 받을지" 미리 약속해두지 않으면 서로 다른 컴파일러/코드가 만든 함수끼리 호출이 불가능하다. 이 약속을 **호출 규약(calling convention)** 이라 한다. x64에서 가장 중요한 두 가지는 다음과 같다.

### SysV x64 (Linux, macOS 등)
정수/포인터 인자는 순서대로 다음 레지스터에 담긴다:

```
1번째 인자: RDI
2번째 인자: RSI
3번째 인자: RDX
4번째 인자: RCX
5번째 인자: R8
6번째 인자: R9
7번째 이후: 스택에 push (오른쪽에서 왼쪽 순서로)
```
반환값은 **RAX**에 담긴다(64비트를 넘는 큰 구조체는 RAX:RDX 조합이나 숨은 포인터 인자를 쓰기도 한다). 부동소수점 인자는 정수 레지스터가 아니라 `XMM0`~`XMM7`을 사용한다.

### Windows x64 (Microsoft x64 calling convention)
정수/포인터 인자는 순서대로 다음 레지스터에 담긴다:

```
1번째 인자: RCX
2번째 인자: RDX
3번째 인자: R8
4번째 인자: R9
5번째 이후: 스택에 push
```
반환값은 마찬가지로 **RAX**에 담긴다. 부동소수점 인자는 `XMM0`~`XMM3`을 사용한다. Windows x64에서는 함수를 호출하기 전에 레지스터 인자 4개분(32바이트)의 **섀도 스페이스(shadow space)** 를 스택에 미리 확보해야 한다는 규칙도 있다(호출받은 함수가 필요하면 레지스터 값을 그 공간에 저장할 수 있도록 caller가 비워두는 공간).

두 규약을 비교하면 이렇게 정리된다:

| 순번 | SysV x64 (Linux) | Windows x64 |
|---|---|---|
| 1 | RDI | RCX |
| 2 | RSI | RDX |
| 3 | RDX | R8 |
| 4 | RCX | R9 |
| 5 | R8 | 스택 |
| 6 | R9 | 스택 |
| 7~ | 스택 | 스택 |
| 반환값 | RAX | RAX |

레지스터 이름 뒤에 붙는 크기 접두사는 REV-0026(비트 마스크)에서 다룬 것과 비슷한 원리로, 인자 타입 크기에 따라 `RDI`(64비트) 대신 `EDI`(32비트), `DI`(16비트), `DIL`(8비트)처럼 하위 레지스터가 쓰인다. 예를 들어 `int` 타입 인자는 `EDI`/`ECX`처럼 32비트 폭 레지스터 이름으로 나타난다.

**32비트(x86) 환경은 다르다.** 레지스터가 부족했던 32비트 시절에는 대부분의 호출 규약(`cdecl`, `stdcall` 등)이 인자를 전부 스택에 push해서 넘겼다. 이 글은 x64를 기준으로 설명하지만, 32비트 바이너리를 만나면 `push` 연속과 `call`이 함께 나오는 패턴을 찾아야 한다는 점만 기억해두면 된다.

이 글은 어디까지나 **개요 수준**이다. 여섯 개를 넘는 인자, 구조체를 값으로 전달하는 경우, 부동소수점과 정수가 섞인 경우, 가변 인자 함수(`printf`류)의 세부 규칙처럼 더 복잡한 케이스는 별도의 심화 문서에서 다룰 예정이다.

## 화면/코드에서 보이는 징후
- `call` 직전에 `mov edi, X` / `mov esi, Y` (Linux) 또는 `mov ecx, X` / `mov edx, Y` (Windows)처럼 레지스터에 값을 채우는 코드가 연속으로 나온다.
- 함수 진입 직후에 `mov [rbp-N], edi`처럼 레지스터 인자를 지역 변수 슬롯으로 복사(spill)하는 코드가 보인다(REV-0031 스택 프레임 참고).
- `call` 직후에 `mov [rbp-M], eax` 또는 바로 `test eax, eax` / `cmp eax, 0`처럼 RAX(반환값)를 검사하는 코드가 이어진다.
- IDA/Ghidra 디컴파일 결과에서 `func(a1, a2)`처럼 인자가 자동으로 채워져 있는데, 이는 디스어셈블러가 호출 규약을 알고 있어서 `call` 직전 레지스터 세팅을 인자로 자동 매핑해준 것이다.

## 가장 먼저 할 것
`call` 명령어를 만나면, 먼저 그 직전 몇 줄에서 **어느 레지스터들이 세팅되는지**를 확인한다. 대상 바이너리가 Linux ELF면 RDI/RSI/RDX/RCX/R8/R9 순서로, Windows PE면 RCX/RDX/R8/R9 순서로 해석한다. 그 다음 `call` 직후 RAX를 어떻게 쓰는지 보면 그 함수의 반환값이 어떻게 활용되는지 알 수 있다.

## 단계별 절차

**1) 플랫폼 판단**

파일이 ELF(Linux)인지 PE(Windows)인지 먼저 확인한다(`file`, IDA/Ghidra가 열 때 자동 인식). ELF면 SysV 규약, PE면 Windows x64 규약을 적용한다.

**2) call 직전 레지스터 세팅 순서로 인자 개수 추정**

```asm
mov     edi, 5          ; 1st arg = 5
mov     esi, 10         ; 2nd arg = 10
call    add_numbers
```
이 경우 `add_numbers`는 최소 2개의 정수 인자를 받는 함수로 추정된다(SysV 기준).

```asm
mov     ecx, 5          ; 1st arg = 5
mov     edx, 10         ; 2nd arg = 10
call    AddNumbers
```
동일한 로직의 Windows x64 버전이다.

**3) 스택으로 전달되는 인자(7번째 이후) 확인**

```asm
mov     [rsp+0x20], rax  ; 7th arg (SysV, 스택에 직접 저장)
mov     edi, 1
mov     esi, 2
...
call    many_args_func
```
레지스터 6개를 다 채운 뒤에도 인자가 남으면 `mov [rsp+N], ...` 형태로 스택에 쌓인다. Windows는 4개를 채운 뒤부터 스택을 쓴다.

**4) call 직후 RAX(반환값) 사용처 확인**

```asm
call    compute_value
mov     [rbp-8], eax     ; 반환값을 지역 변수에 저장
cmp     eax, 0
je      fail_label        ; 반환값이 0이면 분기
```
반환값이 0/음수/특정 값인지에 따라 분기하는 패턴은 실패 코드를 반환하는 함수에서 아주 흔하다(REV-0024 2의 보수 참고 — 반환값이 음수인지 판단할 때).

**5) 디버거로 실제 값 확인**

x64dbg나 GDB에서 `call` 명령어 위치에 브레이크포인트를 걸고, 그 직전에 레지스터 값을 확인하면 실제로 어떤 인자가 넘어가는지 런타임에 검증할 수 있다.
```
(gdb) break *0x0000555555555160   # call 명령어 주소
(gdb) run
(gdb) info registers rdi rsi rdx
(gdb) finish                       # 함수 실행 완료까지 진행 후 반환값 확인
Run till exit from #0  ...
0x... in main ()
Value returned is $1 = 15
```

## 명령어/단축키
IDA/Ghidra: 함수 시그니처를 더블클릭하거나 `Y`(Set type)로 인자 타입/개수를 직접 지정하면 디컴파일 결과의 인자 표시가 갱신된다.
```
(gdb) info registers rdi rsi rdx rcx r8 r9    # SysV 인자 레지스터 한 번에 확인
(gdb) info registers rcx rdx r8 r9            # Windows 인자 레지스터(WinDbg/gdb-multiarch 등)
(gdb) finish                                   # 현재 함수 리턴까지 실행하고 반환값(RAX) 출력
```
x64dbg: `call` 명령어 위에서 `F8`(Step Over)로 넘기면 실행 후 RAX 레지스터에 반환값이 바로 표시된다.

## 출력 해석
- `call` 직전 RDI/RSI/RDX/RCX/R8/R9(Linux) 또는 RCX/RDX/R8/R9(Windows)에 들어있는 값이 곧 함수 인자다. 정수든 포인터든 상관없이 동일한 레지스터를 쓴다(부동소수점만 XMM 레지스터로 분리).
- `call` 직후 RAX/EAX 값이 그 함수의 반환값이다. 함수가 `void`를 반환하면 RAX 값은 정의되지 않은(의미 없는) 상태일 수 있으니 무시해야 한다.
- 인자가 포인터(주소)인지 정수값인지는 레지스터 값만 봐서는 알 수 없고, 그 값이 어떻게 쓰이는지(역참조되는지, 산술 연산에 쓰이는지)를 REV-0033(포인터와 역참조)의 패턴과 함께 봐야 판단할 수 있다.

## 흔한 실수
- Linux 바이너리를 보면서 Windows 규약(RCX/RDX/R8/R9)을 적용하거나 그 반대로 하는 것 — 파일 형식(ELF vs PE)을 먼저 확인하는 습관이 중요하다.
- 함수 하나가 6개보다 많은 인자를 받는데 레지스터만 확인하고 스택에 쌓인 나머지 인자를 놓치는 것.
- `void`를 반환하는 함수 호출 직후의 RAX 값을 의미 있는 반환값이라고 오해하는 것 — 이런 경우 RAX는 그냥 그 함수 내부에서 마지막으로 쓰였던 값이 우연히 남아있는 것뿐이다.
- 부동소수점 인자/반환값이 XMM 레지스터를 쓴다는 사실을 몰라서, `double`이나 `float`을 다루는 함수를 볼 때 RDI/RAX만 보다가 값을 못 찾는 것.
- 재귀 호출이나 콜백처럼 함수가 자기 자신을, 혹은 다른 함수를 호출하는 도중에 레지스터 인자 값이 덮어써질 수 있다는 것을 잊고, 이미 지나간 `call`의 인자를 나중 시점의 레지스터 값으로 착각하는 것 — 항상 해당 `call` **바로 직전**의 값을 봐야 한다.

## 막혔을 때 다음 체크
- 인자/반환값이 저장되는 스택 프레임의 구조 자체가 궁금하면 → REV-0031(스택 프레임이 무엇인지)로 이동.
- 인자로 넘어온 값이 포인터일 때 그것을 역참조하는 어셈블리 패턴이 궁금하면 → REV-0033(포인터와 역참조를 어셈블리에서 읽는 법)으로 이동.
- `call` 명령어 자체의 동작(리턴 주소 push, 직접/간접 호출 구분)이 궁금하면 → `../assembly/rev-0071-call.md`로 이동.
- 반환값이 음수처럼 보이는데 이게 정말 음수인지 큰 양수인지 헷갈리면 → REV-0024(2의 보수와 음수 표현)로 이동.

## 미니 예제
다음 C 코드를 두 플랫폼에서 컴파일했을 때 어떻게 다르게 보이는지 비교해보자.

```c
int add(int a, int b) {
    return a + b;
}

int main(void) {
    int r = add(3, 4);
    return r;
}
```

**Linux(SysV x64)** 어셈블리:
```asm
; main 함수 내부
mov     edi, 3          ; 1st arg
mov     esi, 4          ; 2nd arg
call    add
mov     [rbp-4], eax    ; 반환값(r) 저장

; add 함수 내부
add:
    mov     eax, edi     ; a
    add     eax, esi     ; a + b
    ret                   ; 결과는 eax에 담긴 채 반환
```

**Windows x64** 어셈블리:
```asm
; main 함수 내부
mov     ecx, 3          ; 1st arg
mov     edx, 4          ; 2nd arg
sub     rsp, 0x28        ; 섀도 스페이스 + 정렬용 스택 확보
call    add
add     rsp, 0x28
mov     [rbp-4], eax    ; 반환값(r) 저장

; add 함수 내부
add:
    mov     eax, ecx     ; a
    add     eax, edx     ; a + b
    ret
```

두 코드는 사용하는 레지스터 이름만 다를 뿐, "처음 두 인자를 각각 정해진 레지스터에 넣고 call하며, 결과는 eax로 돌려받는다"는 구조는 동일하다. IDA/Ghidra는 이 패턴을 인식해서 두 경우 모두 `add(3, 4)`처럼 자연스러운 C 함수 호출 형태로 디컴파일해준다.

## 관련 글
- REV-0024 — 2의 보수와 음수 표현
- REV-0031 — 스택 프레임이 무엇인지
- REV-0033 — 포인터와 역참조를 어셈블리에서 읽는 법
- `../assembly/rev-0071-call.md` — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- SysV x64 호출 규약(레지스터 순서, 섀도 스페이스 없음, 반환값 RAX): System V Application Binary Interface AMD64 Architecture Processor Supplement 공식 스펙 기준 (2026-09-08 검증).
- Windows x64 호출 규약(RCX/RDX/R8/R9, 섀도 스페이스 32바이트): Microsoft 공식 문서 "x64 calling convention" 기준.
