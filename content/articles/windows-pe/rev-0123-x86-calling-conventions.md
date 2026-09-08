---
id: REV-0123
title: "Windows x86 stdcall cdecl fastcall thiscall"
slug: "rev-0123-x86-calling-conventions"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86]
format: [PE]
tools: [IDA, x64dbg, "x32dbg"]
keywords: ["cdecl", "stdcall", "fastcall", "thiscall", "x86 calling convention", "ECX this 포인터", "스택 정리 caller callee", "@함수이름@숫자"]
aliases: ["x86 호출규약 종류", "stdcall cdecl 차이", "thiscall이란", "fastcall이란", "함수 이름 뒤에 @16 붙는 이유"]
symptom_keywords: ["cdecl stdcall 차이를 모름", "스택을 누가 정리하는지 모름", "thiscall에서 this가 어디 있는지 모름", "함수 이름에 @숫자가 붙는 이유를 모름", "가변인자 함수는 왜 cdecl만 쓰는지 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
32비트 Windows(x86)에는 인자를 어디에 놓고 스택을 누가 정리하는지가 서로 다른 네 가지 호출 규약(`cdecl`, `stdcall`, `fastcall`, `thiscall`)이 공존하며, x64 하나로 통일된 Windows x64(REV-0122)나 Linux SysV(REV-0106)와 달리 x86 디스어셈블리에서는 함수마다 이 네 가지 중 무엇을 쓰는지 스택 정리 코드와 인자 위치로 직접 구분해야 한다.

## 언제 검색해야 하나
- 32비트 Windows 바이너리에서 함수 호출 후 `add esp, N`이 있는 경우와 없는 경우가 섞여 있어서 왜 다른지 궁금할 때
- IDA가 함수 이름 뒤에 `@16`, `@8` 같은 숫자를 붙여서 보여주는데(`_함수이름@16`) 이게 뭘 뜻하는지 모를 때
- C++ 멤버 함수를 디스어셈블리에서 보는데 `ECX`에 뭔가가 항상 들어 있어서 이게 뭔지 궁금할 때
- `printf`처럼 인자 개수가 가변인 함수는 왜 항상 특정 호출 규약(`cdecl`)만 쓰는지 궁금할 때
- 오래된 32비트 CTF/wargame 바이너리를 분석하면서 x64와 다른 인자 전달 방식에 적응해야 할 때

## 핵심 개념

### 왜 x86에는 호출 규약이 여러 개인가
x86(32비트)은 범용 레지스터가 8개(`EAX`~`EDI`)뿐이라 x64처럼 여유 있게 레지스터로 인자를 넘기기 어렵다. 그래서 전통적으로 **인자를 스택에 쌓아서 전달하는 방식**이 기본이었고, 그 위에 "누가 스택을 정리하는지", "일부 인자를 레지스터로 최적화할지", "C++ 멤버 함수의 `this` 포인터를 어떻게 넘길지"에 따라 여러 변종 규약이 컴파일러/언어별로 생겨났다. x64로 넘어오면서 Microsoft는 이 모든 걸 하나의 통일된 규약(REV-0122)으로 정리했지만, 32비트 코드(오래된 프로그램, 일부 레거시 CTF 바이너리)를 분석할 때는 여전히 이 네 가지를 구분할 수 있어야 한다.

### 1) cdecl (`__cdecl`) — C의 기본, 가변 인자의 표준
```
인자 전달: 모두 스택에, 오른쪽 인자부터 push(마지막 인자가 가장 먼저 push됨)
스택 정리: 호출자(caller)가 call 이후 add esp, N 으로 직접 정리
이름 장식(decoration): 보통 없음 (또는 밑줄 하나: _함수이름)
```
```asm
push 3          ; c (오른쪽부터)
push 2           ; b
push 1            ; a
call _add3
add  esp, 0xC       ; 호출자가 직접 정리 (인자 3개 * 4바이트)
```
**가변 인자 함수(`printf` 등)는 반드시 cdecl이어야 한다** — 호출된 함수 입장에서는 인자가 몇 개 들어왔는지 컴파일 시점에 알 수 없으므로, 스택 정리를 호출자가 맡는 것이 유일하게 안전한 방법이기 때문이다(피호출자가 정리하는 규약이라면 인자 개수를 함수 자신이 알아야 하는데, 가변 인자 함수는 그걸 모른다).

### 2) stdcall (`__stdcall`) — 대부분의 Win32 API
```
인자 전달: cdecl과 동일하게 모두 스택에, 오른쪽부터 push
스택 정리: 피호출자(callee)가 ret N 명령으로 자기 자신이 정리
이름 장식: _함수이름@N  (N = 인자 총 바이트 수)
```
```asm
push 3
push 2
push 1
call _add3@12    ; 이름 뒤에 @12가 붙음 (인자 3개 * 4바이트)
; add esp 가 없다! 호출자는 정리 안 함

; add3@12 내부:
add3@12:
    ...
    ret  0xC      ; 피호출자가 ret N으로 스택을 직접 정리하고 리턴
```
`user32.dll`, `kernel32.dll` 등 거의 모든 표준 Win32 API가 이 규약을 쓴다. 함수 이름 뒤에 붙는 `@N`이라는 숫자(예: `_CreateFileA@28`)는 이 함수가 스택에서 정리해야 할 바이트 수를 정확히 알려주는 표식이며, IDA에서 이 장식된 이름을 그대로 보여주는 경우가 많다.

### 3) fastcall (`__fastcall`) — 처음 두 인자를 레지스터로
```
인자 전달: 처음 2개 정수 인자는 ECX, EDX에, 나머지는 스택에(오른쪽부터 push)
스택 정리: 피호출자(callee)가 ret N으로 정리 (stdcall과 동일)
이름 장식: @함수이름@N
```
```asm
push 3         ; 3번째 인자만 스택으로
mov  edx, 2     ; 2번째 인자
mov  ecx, 1      ; 1번째 인자
call @add3@12
```
Windows의 `__fastcall`은 딱 2개의 정수 인자만 레지스터(`ECX`, `EDX`)로 넘긴다는 점에서, x64 Microsoft calling convention(4개 레지스터)이나 SysV(6개 레지스터)보다 훨씬 제한적이다. 이름 장식이 `_`가 아니라 `@`로 시작하는 것도 stdcall과 구분되는 특징이다.

### 4) thiscall (`__thiscall`) — C++ 멤버 함수 전용
```
인자 전달: this 포인터는 ECX에, 나머지 일반 인자는 스택에(오른쪽부터 push)
스택 정리: 피호출자(callee)가 정리 (MSVC 기준. 인자 개수가 가변이면 caller가 정리하는 예외도 있음)
이름 장식: C++ 네임 맹글링을 따름 (예: ?Method@ClassName@@QAEXH@Z 같은 형태)
```
```c
class Foo {
public:
    int Add(int x) { return this->value + x; }
};
```
```asm
mov  ecx, [this포인터가_있는_변수]  ; this를 ECX에
push 5                                ; Add(5)의 인자 x
call Foo::Add
```
C++ 멤버 함수를 MSVC로 컴파일하면 기본적으로 `thiscall`이 적용되며, **암묵적인 `this` 포인터가 항상 `ECX`에 담긴다.** 디스어셈블리에서 함수 진입 직후 `ECX` 값을 어딘가(예: `[ebp-4]`)에 저장하고 그 뒤로 그 저장된 값을 통해 멤버 변수(`[eax+오프셋]` 형태)에 접근하는 패턴이 보이면, 이건 거의 확실히 C++ 멤버 함수이고 `ECX`가 `this`라는 강력한 신호다. 이 특징은 x64 Microsoft calling convention에서 `this`가 그냥 첫 번째 인자로 취급되어 `RCX`에 들어가는 것(REV-0122)과 원리는 비슷하지만, x86에서는 `thiscall`이라는 이름이 붙은 별도 규약으로 명시적으로 구분된다는 점이 다르다.

### 네 규약 비교표
| 규약 | 정수 인자 레지스터 | 나머지 인자 | 스택 정리 | 대표 사용처 |
|---|---|---|---|---|
| `cdecl` | 없음(전부 스택) | 스택, 오른쪽부터 push | 호출자(`add esp, N`) | C 기본, 가변 인자 함수 |
| `stdcall` | 없음(전부 스택) | 스택, 오른쪽부터 push | 피호출자(`ret N`) | 대부분의 Win32 API |
| `fastcall` | `ECX`, `EDX` (처음 2개) | 스택, 오른쪽부터 push | 피호출자(`ret N`) | 컴파일러 최적화 선택 |
| `thiscall` | `ECX` (this 포인터) | 스택, 오른쪽부터 push | 피호출자(대개) | C++ 비정적 멤버 함수 |

### SysV x64 / Microsoft x64와의 근본적 차이
REV-0106, REV-0122에서 다룬 x64 규약들은 시스템마다 **딱 하나의 통일된 규약**만 존재하고 레지스터 개수도 훨씬 많다(SysV 6개, MS x64 4개). 반면 x86은 위 네 가지가 **컴파일러 지시자(`__cdecl`, `__stdcall` 등)나 함수의 성격(멤버 함수 여부, 가변 인자 여부)에 따라 함수마다 다르게 선택된다.** 그래서 x86 디스어셈블리를 읽을 때는 "이 아키텍처는 이 규약 하나"라고 단정할 수 없고, **함수 하나하나마다 스택 정리 코드(`ret N`인지, 호출 측 `add esp`인지)와 이름 장식(`@N` 유무)을 직접 확인**해야 한다. 이 점이 x86 리버싱을 x64보다 오히려 더 까다롭게 만드는 요인 중 하나다.

## 화면/코드에서 보이는 징후
- `call` 직후 `add esp, N`이 있으면 cdecl(호출자가 정리)
- `call` 직후 아무 정리 코드가 없고, 대신 함수 끝부분에 `ret N`(`N`이 0이 아닌 값)이 있으면 stdcall/fastcall/thiscall(피호출자가 정리)
- 함수 이름이 `_CreateFileA@28`처럼 `@숫자`로 끝나면 stdcall, `@함수이름@숫자`처럼 앞뒤로 `@`가 붙으면 fastcall
- 함수 진입 직후 `ECX`를 즉시 스택 변수에 저장하고 그 값을 통해 `[값+오프셋]` 형태로 멤버 변수처럼 접근하면 thiscall(C++ 멤버 함수)
- IDA가 함수 프로토타입을 `__stdcall`, `__fastcall`, `__thiscall`로 자동 표시(디컴파일러가 스택 정리 패턴을 분석해서 추론한 결과)

## 가장 먼저 할 것
분석 중인 함수의 `call` 명령 직후에 `add esp, N`이 있는지부터 확인한다. 있으면 cdecl, 없으면 함수 자체의 `ret` 명령이 `ret`(정리 없음, 드묾)인지 `ret N`(정리함)인지 확인해서 stdcall류로 판단한다. 그다음 `ECX`가 인자로 쓰이고 있는지, 그리고 그 함수가 C++ 클래스의 멤버로 보이는지(같은 `this` 값으로 여러 함수가 호출되는 패턴)를 확인해서 thiscall인지 fastcall인지 구분한다.

## 단계별 절차

**1) 스택 정리 위치로 caller-cleanup vs callee-cleanup 구분**
```text
call 직후 add esp, N 있음      → cdecl
call 직후 아무것도 없음         → stdcall / fastcall / thiscall 중 하나 (함수 내부의 ret N 확인)
```

**2) 함수 내부의 ret 명령 확인**
```text
ret       (피연산자 없음, 0바이트 정리) → 드묾, 인자 없는 함수이거나 특수 케이스
ret 0xC   (0xC바이트 정리)              → stdcall/fastcall/thiscall이 스택에 쌓인 인자를 정리
```

**3) ECX/EDX 사용 여부로 fastcall/thiscall 판정**
```text
ECX, EDX 둘 다 인자로 쓰임               → fastcall
ECX 하나만 쓰이고 그게 this처럼 보임(멤버 변수 접근 패턴) → thiscall
ECX/EDX 둘 다 인자로 안 쓰임             → cdecl 또는 stdcall
```

**4) 이름 장식으로 최종 확인 (심볼이 남아있는 경우)**
```text
_함수이름          → cdecl (장식 없거나 밑줄만)
_함수이름@N        → stdcall
@함수이름@N        → fastcall
C++ 맹글링된 이름   → thiscall (멤버 함수)
```

## 명령어/단축키
```text
IDA: 함수 우클릭 → Edit Function... 에서 호출 규약(Calling convention) 직접 확인/수정 가능
IDA: Options → Compiler에서 기본 이름 장식 스타일 확인
x32dbg: F2(브레이크포인트), F9(실행) 후 스택(Stack 창)에서 인자가 실제로 어디 쌓였는지 확인
```

## 출력 해석
- `ret 0xC`처럼 정리 바이트 수가 `4의 배수`이면 그 값을 4로 나눈 것이 대략 스택으로 전달된 인자 개수(포인터/정수 기준)와 일치한다(fastcall/thiscall이면 레지스터로 넘어간 인자는 제외하고 계산해야 함에 유의)
- 함수 이름에 `@28`이 붙어 있으면 이 함수는 스택에서 28바이트(정수 인자 7개어치)를 정리하는 stdcall 함수라는 뜻
- 같은 클래스의 여러 멤버 함수가 호출될 때마다 `ECX`에 매번 같은 변수(예: 힙에 할당된 객체 포인터)가 들어간다면 이는 명백한 thiscall 패턴이고, 그 `ECX` 값이 곧 C++ 객체의 `this`

## 흔한 실수
- x86 바이너리 전체가 하나의 통일된 규약만 쓸 거라고 가정하는 것 — 같은 파일 안에서도 함수마다(특히 사용자 코드 vs 가져온 Win32 API) 다른 규약이 섞여 있는 게 정상이다.
- `call` 뒤에 `add esp`가 없다고 해서 무조건 인자가 없는 함수라고 착각하는 것 — stdcall/fastcall/thiscall은 피호출자가 정리하므로 호출자 쪽에는 정리 코드가 안 보이는 게 정상이다.
- fastcall의 `ECX`, `EDX`를 thiscall의 `ECX`(this)와 혼동하는 것 — thiscall은 `ECX` **하나만** this로 쓰고 나머지는 전부 스택이며, fastcall은 `ECX`/`EDX` **둘 다** 일반 인자로 쓴다.
- 가변 인자 함수가 stdcall일 수 있다고 착각하는 것 — 가변 인자 함수는 반드시 cdecl이어야 한다(피호출자가 자신이 정리해야 할 바이트 수를 알 수 없기 때문).
- x64 Microsoft calling convention(REV-0122)의 `RCX`(1번째 인자)와 x86 thiscall의 `ECX`(this 포인터)를 같은 개념으로 혼동하는 것 — 이름이 겹치는 레지스터 계열이라 헷갈리기 쉽지만 아키텍처(32비트 vs 64비트)와 규약 자체가 다르다.

## 막혔을 때 다음 체크
- 64비트 Windows의 통일된 규약(shadow space 등)이 궁금하면 → [REV-0122 Microsoft x64 Calling Convention](./rev-0122-ms-x64-calling-convention.md)
- Linux x64 SysV 규약과 비교하고 싶으면 → [SysV AMD64 Calling Convention](../linux-elf/rev-0106-sysv-amd64-calling-convention.md)
- 인자/반환값 위치의 가장 기초적인 개념부터 다시 보고 싶으면 → [함수 인자와 반환값이 어디에 있는지](../binary-basics/rev-0032-args-and-return-location.md)
- Import Table에서 가져온 Win32 API의 실제 이름(장식 포함/제외)을 확인하고 싶으면 → [REV-0119 Import Table에서 중요한 API 찾기](./rev-0119-import-table.md)

## 미니 예제
같은 `Add(int a, int b)` 함수를 규약별로 컴파일하면 어떻게 다르게 보이는지 비교한다.

```asm
; cdecl: _Add
push 2
push 1
call _Add
add  esp, 8        ; 호출자가 정리

; stdcall: _Add@8
push 2
push 1
call _Add@8         ; 호출자 쪽 정리 코드 없음
; Add@8 내부: ... ret 8   (피호출자가 정리)

; fastcall: @Add@8
mov  edx, 2
mov  ecx, 1
call @Add@8           ; 인자 둘 다 레지스터, 스택 정리는 피호출자
; Add@8 내부: ... ret 0  (스택에 쌓은 인자가 없으므로 ret 0 또는 그냥 ret)

; thiscall (C++ 멤버 함수, 예: obj->Add(2) 형태의 int Add(int b))
mov  ecx, [obj포인터]  ; this
push 2                   ; 나머지 인자 b
call Add
; Add 내부: ... ret 4      (스택에 쌓인 인자 b(4바이트)만 정리)
```

이 네 버전을 나란히 보면, **인자가 어디 있는지**(레지스터냐 스택이냐, 몇 개가 레지스터로 가느냐)와 **스택을 누가 치우는지**(`add esp` vs `ret N`)라는 두 축만 확인하면 규약을 정확히 구분할 수 있다는 걸 알 수 있다.

## 관련 글
- REV-0122 — Microsoft x64 Calling Convention
- REV-0106 — SysV AMD64 Calling Convention
- REV-0032 — 함수 인자와 반환값이 어디에 있는지
- REV-0119 — Import Table에서 중요한 API 찾기

## 출처/검증
- `cdecl`, `stdcall`, `fastcall`, `thiscall` 규약별 인자 전달 위치와 스택 정리 주체: Microsoft Learn "Argument Passing and Naming Conventions" 및 "x86 calling conventions" 공식 문서 기준 (2026-09-08 검증).
- 이름 장식(`@N`, `_함수이름@N`) 규칙: Microsoft Learn "Decorated Names" 공식 문서 기준.
- 가변 인자 함수가 cdecl을 요구하는 이유: Microsoft Learn calling convention 문서의 stdcall/cdecl 비교 설명 기준.
