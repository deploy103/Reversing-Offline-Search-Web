---
id: REV-1078
title: "printf 스타일 가변 인자 호출이 어셈블리에서 보이는 패턴"
slug: "rev-1078-printf-varargs-call-asm-pattern"
category: "c-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["printf 가변인자 어셈블리", "printf varargs assembly", "al 레지스터 xmm 개수", "가변 인자 호출 규약"]
aliases: ["printf 호출 어셈블리 패턴", "가변 인자 함수 호출 시 al이 왜 세팅되는지", "printf 인자 레지스터 순서"]
symptom_keywords: ["printf 호출 전에 al에 숫자를 넣는 이유를 모르겠음", "가변 인자 함수 호출 인자 순서가 헷갈림", "double 인자가 xmm에 있는데 정수 인자는 rdi에 있음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`printf` 같은 가변 인자(variadic) 함수를 SysV x64에서 호출할 때는 고정 인자(포맷 문자열)부터 시작해 정수/포인터 인자는 순서대로 `rdi, rsi, rdx, rcx, r8, r9`에, 부동소수 인자는 완전히 별도의 순서로 `xmm0, xmm1, ...`에 나눠 담고, 추가로 `al` 레지스터에 사용한 `xmm` 레지스터 개수를 넣어줘야 하는 특수한 호출 패턴이 나타난다(Windows x64는 이 규칙이 다르다).

## 언제 검색해야 하나
- `printf`나 다른 가변 인자 함수를 호출하는 코드 직전에 `mov al, N` 같은, 다른 함수 호출에서는 안 보이던 명령이 나와서 이게 뭔지 궁금할 때
- 정수 인자는 `esi`, `edx`, `ecx`에 있는데 `double`/`float` 인자는 그 순서와 무관하게 `xmm0`부터 채워지는 걸 보고 인자 순서가 왜 이렇게 나뉘는지 헷갈릴 때
- IDA/Ghidra가 `printf` 호출 인자 개수를 실제 포맷 문자열의 `%d`, `%s` 개수와 다르게 표시하거나 인자를 잘못 나열할 때 직접 손으로 검증해야 할 때
- Windows API의 가변 인자 함수(`wsprintf` 등)와 Linux `printf`의 인자 전달 방식이 왜 다른지 비교해야 할 때

## 핵심 개념
가변 인자 함수는 호출된 시점에는 몇 개의 인자가 왔는지, 그 타입이 뭔지 컴파일러가 함수 정의만 보고는 알 수 없다(정의에 `...`만 있음). 그래서 **호출하는 쪽(caller)**이 모든 정보를 정해진 규칙대로 레지스터/스택에 배치해야 하며, 함수 내부는 그 규칙(그리고 포맷 문자열 같은 힌트)에 의존해 인자를 해석한다. SysV x64 ABI에서는 정수/포인터형과 부동소수형이 완전히 독립적인 레지스터 순서를 가지며, 정수형 레지스터가 이미 여러 개 쓰였어도 부동소수형은 항상 `xmm0`부터 시작한다.

```c
void report(int id, const char *name, double score) {
    printf("id=%d name=%s score=%.1f\n", id, name, score);
}
```

x86-64 SysV, `-O0`, Intel 문법:

```asm
report:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 24
    mov     [rbp-20], edi        ; id 저장            (report 자신의 인자: id는 edi로 전달받음)
    mov     [rbp-32], rsi        ; name 저장          (report 자신의 인자: name은 rsi로 전달받음)
    movsd   [rbp-16], xmm0       ; score 저장         (report 자신의 인자: double은 xmm0로 전달받음)
    mov     edx, [rbp-20]        ; edx = id
    mov     rcx, [rbp-32]        ; rcx = name
    movsd   xmm1, [rbp-16]       ; xmm1 = score
    lea     rax, [rip+.LC0]      ; rax = "id=%d name=%s score=%.1f\n" 문자열 주소
    mov     rdi, rax             ; printf 1번째 인자(고정 인자): 포맷 문자열 -> rdi
    mov     esi, edx             ; printf 2번째 인자(가변 인자#1, int)   -> esi
    mov     rdx, rcx             ; printf 3번째 인자(가변 인자#2, pointer) -> rdx
    movapd  xmm0, xmm1           ; printf 4번째 인자(가변 인자#3, double) -> xmm0  (정수 레지스터 순서와 별개로 xmm0부터)
    mov     al, 1                ; xmm 레지스터를 1개 사용했다는 것을 al에 기록 (printf 내부의 va_start 처리가 참고)
    call    printf
    leave
    ret
```

핵심은 두 가지다. 첫째, `id`(정수)와 `name`(포인터)은 `esi`, `rdx` 순서로 채워지는데 이는 `rdi`(포맷 문자열) 다음 정수/포인터 슬롯을 순서대로 차지하는 것이다. 둘째, `score`(double)는 그 순서에 끼어들지 않고 별도로 `xmm0`에 채워진다 — 만약 인자 순서가 `id, score, name`이었어도 정수 인자는 여전히 `esi`부터, 부동소수 인자는 여전히 `xmm0`부터 채워진다. 마지막으로 `mov al, 1`은 SysV x64 ABI의 특수 규칙으로, 가변 인자 함수 내부가 저장해야 할 `xmm` 레지스터가 몇 개인지 몰라서 호출자가 힌트를 남겨주는 것이다(정수 레지스터 개수는 힌트가 필요 없음 — 이유는 아래 흔한 실수 참고).

## 화면/코드에서 보이는 징후
- `call printf`, `call sprintf`, `call fprintf` 등 가변 인자 함수 호출 직전에 `mov al, N`(N은 보통 0~8)이 있음
- 정수/포인터 인자는 `rdi → rsi → rdx → rcx → r8 → r9` 순서로, 부동소수 인자는 `xmm0 → xmm1 → ...` 순서로 서로 독립적으로 채워짐
- 포맷 문자열 리터럴의 주소가 항상 첫 번째 정수 레지스터(`rdi`)에 들어감(포맷 문자열 자체는 고정 인자이므로 가변 규칙과 무관하게 맨 앞)
- Windows x64에서는 `printf` 계열 대신 자체 CRT 함수(`printf`도 MSVC CRT에 있음)를 호출하며, 이 경우 인자가 그냥 `rcx, rdx, r8, r9` + 스택 순서로 나열되고 부동소수 인자도 정수 인자와 슬롯을 공유하는(같이 카운트되는) 차이가 있음

## 가장 먼저 할 것
`call printf` 계열 직전의 `mov al, N`을 찾아 N값(사용된 xmm 레지스터 개수)을 확인한 다음, 포맷 문자열을 `rdi`에서 읽어 `%d`/`%s`/`%f` 개수와 위치를 파악하고, 그 개수만큼 정수/포인터 레지스터와 부동소수 레지스터를 각각 순서대로 대응시킨다.

## 단계별 절차
1. `call printf`(또는 다른 가변 인자 함수) 직전 코드에서 `rdi`에 들어가는 값을 확인해 포맷 문자열을 특정한다.
2. 포맷 문자열의 `%` 지시자를 순서대로 나열해 몇 개의 정수/포인터 인자와 몇 개의 부동소수 인자가 필요한지 센다.
3. 정수/포인터 인자는 `rsi, rdx, rcx, r8, r9` 순서로(포맷 문자열이 이미 `rdi`를 차지했으므로 두 번째 슬롯부터), 부동소수 인자는 `xmm0, xmm1, ...` 순서로 각각 대응시킨다.
4. `mov al, N`의 N이 실제로 사용한 xmm 레지스터 개수와 일치하는지 검증해 분석이 맞는지 재확인한다.

## 명령어/단축키
- IDA: `call printf` 호출부에서 포맷 문자열 인자를 자동 인식하면 나머지 인자도 자동으로 나열해 주는 경우가 많음(Hex-Rays의 printf 시그니처 인식)
- Ghidra: Decompile 창에서 포맷 문자열 기반 인자 추론(자동은 아닐 수 있어 수동 확인 필요)
- GDB: `call` 직전에 브레이크포인트를 걸고 `p $rdi`, `p $rsi`, `p $xmm0.v2_double` 등으로 각 레지스터 값을 직접 확인
- x64dbg: 함수 호출 직전 레지스터 창과 FPU/XMM 레지스터 창을 동시에 열어 정수·부동소수 인자를 나란히 비교

## 출력 해석
`mov al, 1`은 "이 호출에서 부동소수 가변 인자를 1개(즉 `xmm0`만) 사용했다"는 뜻이다. glibc의 `printf` 내부 구현(`vfprintf`)은 이 값을 참고해서 나중에 `va_arg`로 꺼내 쓸 `xmm` 레지스터 값들을 스택의 레지스터 저장 영역(register save area)에 얼마나 저장해야 하는지 결정한다. 이 값이 실제 사용한 개수보다 작으면 뒤쪽 부동소수 인자를 잘못 읽어 엉뚱한 값이 나올 수 있다.

## 흔한 실수
- 모든 인자가 `rdi, rsi, rdx, rcx, r8, r9` 순서로만 채워진다고 생각하고 부동소수 인자가 그 순서 어딘가에 끼어 있다고 착각하는 것 — 부동소수는 완전히 별도의 `xmm` 순서를 쓴다.
- `mov al, N`을 정수 인자 개수라고 오해하는 것 — 이는 오직 부동소수(`xmm`) 인자 개수만을 나타내며, 정수 인자 개수에 대한 힌트는 SysV ABI에 따로 없다(정수 레지스터는 스택 프레임 구조상 몇 개를 썼는지 몰라도 안전하게 처리 가능하기 때문).
- Windows x64 가변 인자 호출을 SysV 규칙으로 해석하는 것 — Windows x64는 부동소수 인자도 정수 인자와 같은 위치 슬롯을 하나씩 차지하며(예: 두 번째 인자가 `double`이면 `xmm1`에도 들어가지만 그 자리의 정수 레지스터 `rdx`는 그냥 비워둠), `al` 같은 개수 힌트 레지스터도 쓰지 않는다.
- 고정 인자(포맷 문자열)까지 "가변 인자"로 잘못 묶어서 세는 것 — 포맷 문자열은 항상 고정된 첫 인자이며 `...` 이전에 선언된 부분이다.

## 막혔을 때 다음 체크
- 가변 인자 함수 내부가 스택/레지스터에서 인자를 어떻게 다시 꺼내는지(callee 관점)가 궁금하면 → REV-0356 가변 인자 함수(varargs)가 메모리에서 동작하는 방식
- `printf` 계열 함수 자체의 동작과 포맷 지시자 종류가 궁금하면 → REV-0635 libc 함수 사전: printf 계열 포맷 문자열 함수
- SysV 정수 인자 전달 규칙 자체가 헷갈리면 → REV-0106 SysV AMD64 Calling Convention
- Windows x64에서의 인자 전달 규칙과 비교하려면 → REV-0122 Microsoft x64 Calling Convention

## 미니 예제
부동소수 인자가 두 개인 경우로, `xmm0`과 `xmm1`이 모두 쓰이고 `al`이 2로 세팅되는 모습을 보여준다.

```c
void log_pair(const char *label, double x, double y) {
    printf("%s: (%.2f, %.2f)\n", label, x, y);
}
```

```asm
log_pair:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 24
    mov     [rbp-24], rdi        ; label
    movsd   [rbp-16], xmm0       ; x
    movsd   [rbp-8], xmm1        ; y
    mov     rax, [rbp-24]        ; rax = label
    lea     rdx, [rip+.LC1]      ; "%s: (%.2f, %.2f)\n" 주소
    mov     rsi, rax             ; printf 2번째 인자(가변#1, pointer): label -> rsi
    mov     rdi, rdx             ; printf 1번째 인자(고정): 포맷 문자열 -> rdi
    movsd   xmm0, [rbp-16]       ; printf 부동소수 가변#1: x -> xmm0
    movsd   xmm1, [rbp-8]        ; printf 부동소수 가변#2: y -> xmm1
    mov     al, 2                ; xmm 레지스터 2개(xmm0, xmm1) 사용했음을 기록
    call    printf
    leave
    ret
```

정수/포인터 인자는 `label` 하나뿐이라 `rsi` 한 자리만 쓰지만, 부동소수 인자는 `x`, `y` 두 개라 `xmm0`, `xmm1` 두 자리를 쓰고 그만큼 `al`도 `2`로 세팅된다 — 두 순서가 서로 완전히 독립적으로 카운트된다는 사실이 다시 확인된다.

## 관련 글
- REV-0356 — 가변 인자 함수(varargs)가 메모리에서 동작하는 방식
- REV-0635 — libc 함수 사전: printf 계열 포맷 문자열 함수
- REV-0106 — SysV AMD64 Calling Convention
- REV-0122 — Microsoft x64 Calling Convention

## 출처/검증
- 가변 인자 호출 시 정수/포인터와 부동소수 레지스터가 독립적인 순서를 가지며 `al`에 사용한 SSE 레지스터 개수를 기록해야 하는 규칙: System V Application Binary Interface AMD64 Architecture Processor Supplement, 3.5.7절(Variable Argument Lists) 기준.
- Windows x64 가변 인자 호출에서 부동소수 인자도 정수 인자와 같은 위치 슬롯을 공유한다는 차이: Microsoft x64 소프트웨어 규약(calling convention) 공식 문서 기준 (2026-09-10 검증).
