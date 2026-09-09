---
id: REV-1065
title: "함수 포인터 호출이 어셈블리에서 보이는 패턴"
slug: "rev-1065-function-pointer-call-asm-pattern"
category: "c-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["함수 포인터 호출 어셈블리", "function pointer call assembly pattern", "indirect call", "call rax"]
aliases: ["콜백 함수 어셈블리", "call 레지스터 패턴", "간접 호출 패턴"]
symptom_keywords: ["call 대상이 함수 이름이 아니라 레지스터로 나옴", "indirect call 대상을 못 찾음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
함수 포인터를 통한 호출은 `CALL` 명령의 대상이 고정된 주소가 아니라 레지스터나 메모리 오퍼랜드(`call rax`, `call [rax]`, `call qword [rbp-8]`)가 되는 **간접 호출(indirect call)**로 나타나며, 실제 호출 대상은 정적 분석만으로는 알 수 없고 런타임에 그 레지스터/메모리에 어떤 값이 들어있는지 봐야 확정된다.

## 언제 검색해야 하나
- IDA/Ghidra에서 `CALL` 다음에 함수 이름이 아니라 `rax`, `[rax]`, `[rbp-8]` 같은 레지스터/메모리가 붙어 있어서 실제로 뭘 호출하는지 못 찾을 때
- Xref(cross-reference)를 봐도 그 함수로 들어오는 직접 호출이 하나도 없는데 실행은 되고 있어서 "어떻게 호출되는 거지" 헷갈릴 때
- 콜백(callback)이나 vtable, 함수 포인터 배열 기반 디스패치 코드를 분석해야 할 때
- 디버거로 한 단계씩(Step Into) 들어갔는데 그때마다 다른 함수로 들어가서 혼란스러울 때

## 핵심 개념
일반적인 함수 호출은 `call sub_401234`처럼 **대상 주소가 컴파일 시점에 고정**되어 있다(direct call, REV-0071). 반면 함수 포인터를 통한 호출은 "어떤 함수를 호출할지"가 변수(포인터)의 **런타임 값**에 따라 결정되므로, `CALL`의 오퍼랜드가 상수 주소가 아니라 레지스터나 메모리가 된다. 이것이 간접 호출(indirect call)이다.

```c
typedef int (*op_fn)(int, int);

int add(int a, int b) { return a + b; }
int mul(int a, int b) { return a * b; }

int apply(op_fn f, int a, int b) {
    return f(a, b);
}
```

`apply` 안에서 `f(a, b)`를 호출하는 순간, 컴파일러는 `f`가 가리키는 실제 함수 주소를 알 수 없다(런타임에 `add`가 될 수도, `mul`이 될 수도 있다). 그래서 `f`를 레지스터에 로드한 뒤 그 레지스터를 그대로 `CALL`의 대상으로 쓴다.

이 패턴은 C의 함수 포인터뿐 아니라 C++ 가상 함수(vtable 호출), 콜백 등록(`qsort`의 비교 함수, `signal` 핸들러), 플러그인 디스패치 테이블에서도 똑같이 나타난다. 정적으로는 "이 CALL이 무엇을 부르는지" 100% 확정할 수 없고, 그 포인터에 어떤 값이 대입되는 지점(대입 순간 REV-0349 콜백 패턴 참고)을 역추적하거나, 디버거로 실제 실행 시점의 레지스터 값을 봐야 한다.

## 화면/코드에서 보이는 징후
- `call rax`, `call rbx` — 레지스터에 담긴 주소로 바로 점프
- `call [rax]`, `call qword ptr [rax]` — 메모리에서 함수 포인터 값을 읽자마자 호출(구조체 필드나 vtable 슬롯에 저장된 함수 포인터를 바로 부르는 경우)
- `call [rbp-8]` — 스택에 저장된 지역 함수 포인터 변수를 통한 호출
- IDA에서 이런 CALL 줄에는 보통 노란색 경고나 "간접 호출" 표시가 없고, 대상 함수로의 화살표(Xref)도 안 그려짐 — Xref 창에서 "To"가 비어 있는 함수가 있다면 간접 호출로만 불릴 가능성을 의심
- Ghidra pseudocode에서는 `(*f)(a, b)` 또는 `f(a, b)` 형태로 함수 포인터 호출임을 그대로 보여줌

## 가장 먼저 할 것
`CALL`의 오퍼랜드가 레지스터/메모리인지(간접) 상수 주소인지(직접) 먼저 구분한다. 간접이면 그 레지스터 값이 어디서 왔는지 위로 거슬러 올라가며(`mov rax, [...]`, 함수 인자, 전역 변수 로드 등) 추적한다. 가장 확실한 방법은 디버거로 그 `CALL` 직전에 브레이크포인트를 걸고 레지스터 값을 직접 확인하는 것이다.

## 단계별 절차
1. `call reg` 또는 `call [mem]` 줄을 찾아 간접 호출임을 확인한다.
2. 그 레지스터/메모리 값이 바로 위 몇 줄에서 어떻게 채워졌는지 역추적한다(`mov rax, [rbp-8]`처럼 지역 변수에서 왔다면 그 변수가 어디서 초기화됐는지 더 위로 추적).
3. 초기화 지점이 함수 인자라면, 이 함수를 호출하는 쪽(caller)에서 어떤 함수 주소를 넘겼는지 다시 추적한다(예: `apply(add, 1, 2)`처럼 호출하는 코드에서 `lea rax, [add]` 같은 줄을 찾음).
4. IDA/Ghidra에서 그 함수 주소가 상수라면(`mov rax, offset add` 등) 바로 확정할 수 있다. 전역 함수 포인터 배열/구조체 필드라면 초기화 코드(전역 변수 초기값, `.data`/`.rodata` 덤프)를 확인한다.
5. 정적으로 확정이 안 되면 GDB/x64dbg로 그 `CALL` 직전에 브레이크포인트를 걸고 레지스터 값을 읽어(`p $rax`), 그 값이 어떤 함수의 시작 주소와 일치하는지 심볼 테이블에서 대조한다.

## 명령어/단축키
- GDB: `b *0x401234`(CALL 명령 주소에 브레이크) 후 `p/x $rax` → `info symbol $rax`로 그 주소가 어느 함수인지 이름 확인
- x64dbg: CALL 줄에 F2(브레이크포인트) → 실행 중지 시 레지스터 창에서 값 확인 → 우클릭 `Follow in Disassembler`로 실제 점프될 코드 확인
- IDA: 간접 호출 줄에서 `Alt+F7`(전체 Xref) 대신, 대상 레지스터를 채우는 대입 지점까지 `Ctrl+클릭`으로 데이터 흐름을 손으로 추적
- Ghidra: `Function Graph`에서 간접 호출 노드를 확인하고, `References`에서 관련 함수 포인터 변수의 다른 사용처 탐색

## 출력 해석
```c
typedef int (*op_fn)(int, int);
int apply(op_fn f, int a, int b) { return f(a, b); }
```

```asm
; apply, x86-64 SysV, rdi = f, esi = a, edx = b
apply:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 24
    mov     [rbp-8], rdi     ; f 저장 (함수 포인터)
    mov     [rbp-12], esi    ; a
    mov     [rbp-16], edx    ; b
    mov     edx, [rbp-16]    ; edx = b (4번째 인자로 전달)
    mov     eax, [rbp-12]    ; eax = a
    mov     esi, eax         ; esi = a (2번째 인자로 전달, System V 순서상 재배치)
    mov     rax, [rbp-8]     ; rax = f (호출할 함수 주소)
    call    rax              ; *** 간접 호출: 대상이 상수가 아니라 레지스터 ***
    leave
    ret
```

핵심은 마지막 두 줄이다. `mov rax, [rbp-8]`로 함수 포인터 값을 레지스터에 올리고, `call rax`로 그 값을 대상으로 호출한다. 직접 호출이었다면 `call add`처럼 함수 이름(고정 주소)이 바로 나왔을 것이다. 이 함수만 봐서는 `f`가 실제로 `add`인지 `mul`인지 전혀 알 수 없고, `apply`를 호출하는 코드(`apply(add, 1, 2)` 같은 caller)까지 봐야 한다.

## 흔한 실수
- 간접 호출을 보고 "이 CALL은 분석할 수 없다"고 포기하는 것 — caller 쪽 추적이나 런타임 관찰로 대부분 확정 가능하다.
- Xref 창에 화살표가 안 보인다고 해서 그 함수가 "죽은 코드(dead code)"라고 오판하는 것 — 간접 호출로만 불리는 함수는 정적 Xref 분석에 안 잡히는 게 정상이다.
- vtable(C++ 가상 함수) 호출을 만났을 때 `call [rax]`가 "임의의 함수 포인터"라고만 생각하고, 실제로는 클래스별로 정해진 함수 집합(vtable) 중 하나라는 구조적 맥락을 놓치는 것.
- Step Into(F7/F11)로 무작정 들어가면서 매번 다른 함수에 진입하는 것에 당황하는 것 — 이는 콜백/디스패치 구조가 정상적으로 여러 함수를 오가며 실행되고 있다는 뜻이다.

## 막혔을 때 다음 체크
- 함수 포인터가 메모리(전역 변수, 구조체 필드)에 어떻게 저장되는지가 궁금하면 → REV-0348 함수 포인터가 메모리에서 어떻게 보이는지
- 콜백 등록 패턴 전체 흐름이 궁금하면 → REV-0349 콜백 함수 패턴을 어셈블리에서 알아보는 법
- 직접 호출(CALL)의 기본 문법과 인자 전달 규칙이 헷갈리면 → REV-0071 CALL: 함수 호출, 반환 주소, 인자 추적
- Step Into와 Step Over의 차이, 디버거 조작법이 궁금하면 → REV-0071(CALL 문서 내 Step Into/Over 설명) 참고

## 미니 예제
caller 쪽까지 함께 보면 실제 대상이 확정된다:
```c
int main(void) {
    return apply(add, 3, 4);   /* f = add */
}
```
```asm
; main 내부 일부
lea     rax, [rip+add_offset]   ; rax = add 함수의 주소 (상수, 컴파일 시점에 결정)
mov     rdi, rax                ; apply의 1번째 인자(f)로 add 주소 전달
mov     esi, 3
mov     edx, 4
call    apply
```
`main`에서는 `lea rax, [rip+...]`로 `add`의 주소를 직접 계산해 `rdi`에 넣고 `apply`를 호출한다. `apply` 내부의 `call rax`는 바로 이 값을 받아 실행하는 것이므로, caller까지 함께 보면 "이번 실행에서는 `add`가 호출된다"를 확정할 수 있다.

## 관련 글
- REV-0348 — 함수 포인터가 메모리에서 어떻게 보이는지
- REV-0349 — 콜백 함수 패턴을 어셈블리에서 알아보는 법
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-1066 — 재귀 함수가 어셈블리/스택에서 보이는 패턴
- REV-1061 — 중첩 구조체 접근이 어셈블리에서 보이는 패턴

## 출처/검증
- 직접 호출(`call addr`)과 간접 호출(`call reg`/`call [mem]`)의 인코딩 차이: Intel 64 and IA-32 Architectures Software Developer's Manual, CALL 명령 설명 기준.
- x86-64 SysV 호출 규약에서 함수 포인터 인자가 정수 레지스터로 전달되고 그 값 그대로 CALL 오퍼랜드가 되는 패턴은 리눅스/윈도우 x86-64 환경에서 반복 확인되는 표준 패턴이다(2026-09-10 검증).
