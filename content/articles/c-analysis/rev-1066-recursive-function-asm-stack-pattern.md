---
id: REV-1066
title: "재귀 함수가 어셈블리/스택에서 보이는 패턴"
slug: "rev-1066-recursive-function-asm-stack-pattern"
category: "c-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["재귀 함수 어셈블리", "recursive function assembly pattern", "재귀 스택 프레임", "call self"]
aliases: ["자기 자신 호출 어셈블리", "재귀 콜스택 쌓임", "recursion stack diagram"]
symptom_keywords: ["재귀 함수가 어셈블리에서 왜 자기 주소를 호출하는지 모름", "재귀 호출 중 스택이 계속 쌓여서 헷갈림"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
재귀 함수는 어셈블리에서 함수 자기 자신의 시작 주소로 향하는 `CALL`(자기 자신을 부르는 direct call)로 나타나며, 호출될 때마다 그 함수의 스택 프레임(지역변수 + 저장된 레지스터 + 반환 주소)이 스택 위에 새로 하나씩 쌓인다.

## 언제 검색해야 하나
- IDA/Ghidra에서 어떤 함수 안에 그 함수 자신의 주소로 향하는 `CALL`이 있어서 "이게 왜 자기를 부르지" 헷갈릴 때
- 디버거로 스택을 보는데 같은 함수의 스택 프레임이 여러 겹으로 반복해서 쌓여 있을 때
- 재귀 호출이 너무 깊어져서 스택 오버플로우(Stack Overflow)가 나는 이유를 코드로 확인하고 싶을 때
- Call Stack 창(IDA/GDB `bt`)에 같은 함수 이름이 수십~수백 번 반복해서 나열될 때

## 핵심 개념
재귀 함수는 특별한 명령어를 쓰지 않는다. 그냥 자기 자신의 시작 주소를 대상으로 하는 평범한 `CALL`이다(REV-0071). 컴파일러/CPU 입장에서는 "다른 함수를 부르는 것"과 "자기 자신을 부르는 것"이 코드상 전혀 다르지 않다 — 차이는 오직 `CALL`의 대상 주소가 현재 실행 중인 함수 자신의 시작 주소와 같다는 점뿐이다.

`CALL`은 실행될 때마다 반환 주소를 스택에 `PUSH`한다(REV-0071). 재귀 호출이 일어나면 그때마다:
1. 인자를 레지스터/스택에 준비
2. `CALL`로 반환 주소 `PUSH` + 함수 시작으로 점프
3. 함수 프롤로그(`push rbp`, `sub rsp, N`)가 그 함수의 지역변수 공간을 스택에 추가로 확보

이 세 단계가 재귀 깊이만큼 반복되므로, 스택은 "반환 주소 + 저장된 rbp + 지역변수"로 이루어진 프레임이 호출 횟수만큼 겹겹이 쌓인 모양이 된다. 함수가 끝나는 조건(base case)에 도달하기 전까지 이 쌓임은 계속되고, 각 프레임은 자신만의 인자 값과 지역변수 값을 독립적으로 갖는다 — 그래서 `n=5`일 때 호출된 프레임과 `n=4`일 때 호출된 프레임은 서로 다른 메모리 주소에 각자의 `n` 값을 갖고 공존한다.

## 화면/코드에서 보이는 징후
- `CALL`의 대상이 현재 함수 이름/주소와 동일 (`factorial` 함수 안에서 `call factorial`)
- GDB `bt`(backtrace) 또는 IDA Debugger의 Call Stack 창에 같은 함수 이름이 반복해서 여러 줄 나열됨
- 스택 포인터(`RSP`)가 호출이 깊어질수록 계속 낮은 주소 쪽으로 이동(스택은 아래로 자람)
- 재귀가 너무 깊으면 `Stack Overflow` 예외나 세그폴트(SIGSEGV)가 스택 영역 끝(가드 페이지)에서 발생

## 가장 먼저 할 것
`CALL` 대상이 현재 함수 자신인지 함수 시작 주소와 비교해 확인한다. 그다음 종료 조건(base case, 재귀를 멈추는 `if`/`cmp`+분기)이 어디 있는지 찾는다 — 이 조건이 없거나 잘못되면 무한 재귀(스택 오버플로우)로 이어지므로 리버싱에서도 가장 먼저 확인해야 할 지점이다.

## 단계별 절차
1. 함수 내부에서 자기 자신의 주소로 향하는 `CALL`을 찾는다.
2. 그 `CALL` 이전에 있는 비교/분기(`cmp`, `je`/`jle` 등)를 찾아 재귀를 멈추는 조건(base case)을 특정한다.
3. `CALL` 이후 반환값을 어떻게 가공하는지 본다(예: `imul eax, [반환값]`처럼 재귀 결과에 현재 값을 곱하는 후처리가 있으면 이것이 "재귀 후 연산"이다).
4. 디버거로 재귀 호출 중 브레이크포인트를 걸고 `bt`(GDB) 또는 Call Stack 창(x64dbg/IDA)으로 실제 몇 겹까지 쌓였는지 확인한다.
5. 각 프레임의 `RBP`/`RSP` 값과 그 프레임에 저장된 인자 값을 비교해, 프레임마다 독립적인 지역변수 공간을 갖는다는 것을 직접 확인한다.

## 명령어/단축키
- GDB: `bt`(전체 콜스택), `bt 5`(위 5개만), `frame 2`(2번째 프레임으로 이동해 그 시점 변수 확인), `info frame`
- x64dbg: Call Stack 탭에서 각 프레임 클릭 → 그 시점 스택/레지스터 확인
- IDA 디버거: `Debugger → Debugger windows → Call stack`
- Ghidra 디버거(또는 GDB 연동): 프레임별로 `Stack` 뷰에서 각 재귀 호출의 지역변수 영역 확인

## 출력 해석
```c
int factorial(int n) {
    if (n <= 1) {
        return 1;              /* base case */
    }
    return n * factorial(n - 1); /* 재귀 호출 + 후처리(곱셈) */
}
```

```asm
; factorial, x86-64 SysV, gcc -O0, Intel 문법
; rdi = n
factorial:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 24
    mov     [rbp-20], edi     ; n 저장 (이 프레임만의 n)
    cmp     dword [rbp-20], 1
    jg      .L_recurse        ; n > 1이면 재귀로
    mov     eax, 1            ; base case: return 1
    jmp     .L_return
.L_recurse:
    mov     eax, [rbp-20]
    sub     eax, 1
    mov     edi, eax          ; 인자 = n - 1
    call    factorial         ; *** 자기 자신 재귀 호출 ***
    imul    eax, [rbp-20]     ; 반환값(하위 재귀 결과) * n  (후처리)
.L_return:
    leave
    ret
```

`call factorial`이 바로 재귀 호출이다. 이 시점 스택에는 이미 호출한 쪽(caller, 이전 재귀 단계 또는 `main`)의 반환 주소가 있고, `CALL` 실행으로 이 함수의 반환 주소가 추가로 `PUSH`된다. 함수에 들어가자마자 `push rbp`, `sub rsp, 24`가 다시 실행되어 **이번 호출만의 새 스택 프레임**이 만들어진다. `imul eax, [rbp-20]`은 재귀 호출이 끝나고 돌아온 뒤 실행되는데, 이때 `[rbp-20]`은 **이 프레임의 `n`**(예: `n=3`일 때의 3)이고 `eax`는 **더 깊은 재귀(`n-1=2`)가 반환한 결과**다.

**스택 다이어그램 (factorial(3) 호출 예시)**
```
[초기 호출: factorial(3)]
높은 주소
+-----------------------------+
| main의 반환 주소             |
+-----------------------------+
| factorial(3) 프레임          |
|   saved rbp                 |
|   n = 3                     |
+-----------------------------+   <- 여기까지 쌓인 상태에서 call factorial(2) 실행
| factorial(3)이 만든 반환주소  |
+-----------------------------+
| factorial(2) 프레임          |
|   saved rbp                 |
|   n = 2                     |
+-----------------------------+   <- call factorial(1) 실행
| factorial(2)가 만든 반환주소  |
+-----------------------------+
| factorial(1) 프레임          |
|   saved rbp                 |
|   n = 1                     |   <- base case! 여기서 더 안 내려감
+-----------------------------+
낮은 주소 (RSP가 가장 낮은 지점)
```
`n=1`(base case)에서 `return 1`이 실행되면 스택은 반대로 풀리기 시작한다. `factorial(1)` 프레임이 `leave`/`ret`으로 제거되며 `factorial(2)`로 복귀 → `eax(=1) * n(=2) = 2` 계산 → `factorial(2)` 프레임 제거하며 `factorial(3)`으로 복귀 → `eax(=2) * n(=3) = 6` 반환. 이렇게 "내려갈 때는 프레임이 쌓이고, 올라올 때는 곱셈 결과를 들고 하나씩 프레임이 사라진다"는 것이 재귀의 스택 동작 전체 그림이다.

## 흔한 실수
- 재귀 호출을 "특별한 명령어가 있는 것"으로 오해하는 것 — 그냥 평범한 `CALL`이 자기 자신을 대상으로 할 뿐이다.
- `CALL` 이후의 후처리 코드(`imul eax, [rbp-20]`)를 재귀 호출 전에 실행되는 코드로 착각하는 것 — 이 줄은 재귀가 완전히 끝나고 **돌아온 뒤** 실행된다.
- 재귀 깊이가 깊어질 때 각 프레임의 `[rbp-20]`(n 값)이 전부 같은 메모리라고 오해하는 것 — 각 프레임은 서로 다른 `RBP`를 가지므로 실제로는 서로 다른 메모리 주소다.
- Base case(종료 조건) 분기를 놓쳐서 "이 함수가 왜 멈추는지 모르겠다"며 무한 루프로 오판하는 것.

## 막혔을 때 다음 체크
- 스택 프레임/프롤로그·에필로그의 기본 구조가 헷갈리면 → REV-0341 프롤로그/에필로그 상세 읽기, REV-0031 스택 프레임
- 재귀 함수의 스택 쌓임을 더 깊게 다룬 개념 설명은 → REV-0355 재귀 함수가 스택에서 어떻게 쌓이는지
- CALL/RET의 기본 동작(반환 주소 PUSH/POP)이 헷갈리면 → REV-0071 CALL: 함수 호출, 반환 주소, 인자 추적, REV-0072 RET: 함수 반환과 스택 변화
- 재귀 대신 반복문으로 최적화(tail call)된 경우를 구분하려면 → REV-0358 Tail Call이 CALL 대신 JMP로 보이는 이유

## 미니 예제
GDB로 `factorial(3)` 실행 중 재귀가 가장 깊은 지점에서 콜스택을 확인하면:
```
(gdb) bt
#0  factorial (n=1) at fact.c:2
#1  0x0000555555555160 in factorial (n=2) at fact.c:4
#2  0x0000555555555160 in factorial (n=3) at fact.c:4
#3  0x0000555555555185 in main () at fact.c:8
```
`#0`이 가장 깊은(가장 최근) 호출이고 아래로 갈수록 바깥쪽 호출이다. 같은 함수 이름(`factorial`)이 서로 다른 `n` 값으로 반복 등장하는 것이 재귀의 가장 직접적인 증거다.

## 관련 글
- REV-0355 — 재귀 함수가 스택에서 어떻게 쌓이는지
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0341 — 함수 프롤로그와 에필로그 자세히 읽기
- REV-0358 — Tail Call이 CALL 대신 JMP로 보이는 이유
- REV-1065 — 함수 포인터 호출이 어셈블리에서 보이는 패턴

## 출처/검증
- `CALL`이 반환 주소를 스택에 PUSH하고 대상으로 점프하는 동작, 재귀 호출이 동일한 메커니즘을 반복 사용한다는 점: Intel 64 and IA-32 Architectures Software Developer's Manual, CALL/RET 설명 기준.
- gcc/clang `-O0`에서 재귀 함수가 매 호출마다 독립적인 프롤로그(`push rbp`/`sub rsp`)를 실행해 새 스택 프레임을 만드는 패턴은 x86-64 리눅스/윈도우 환경에서 반복 확인되는 표준 패턴이다(2026-09-10 검증).
