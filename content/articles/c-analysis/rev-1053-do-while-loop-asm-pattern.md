---
id: REV-1053
title: "do-while 루프가 어셈블리에서 보이는 패턴"
slug: "rev-1053-do-while-loop-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["do-while 루프 어셈블리", "do while assembly pattern", "최소 1회 실행 루프"]
aliases: ["do while문 어셈블리에서 어떻게 보임", "진입부 jmp 없는 루프", "do while 디스어셈블"]
symptom_keywords: ["루프 진입부에 jmp가 없어서 이상함", "본문이 조건 검사 없이 바로 실행됨"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`do-while` 루프는 진입부에 REV-1051/1052의 `jmp .L_cond` 같은 "조건 검사로 먼저 건너뛰는 점프"가 **없다** — 함수 흐름이 곧바로 본문으로 떨어지고, 조건 검사는 본문을 한 번 실행한 뒤 맨 아래에서만 이루어지므로 최소 1회 실행이 어셈블리 구조 자체로 보장된다.

## 언제 검색해야 하나
- 루프처럼 보이는 블록인데 함수 진입 직후 조건 검사 없이 바로 코드가 실행되는 걸 보고 "이게 루프 맞나" 헷갈릴 때
- REV-1051/1052에서 본 진입부 `jmp`가 안 보이는 루프를 발견해서 어떤 종류인지 구분하고 싶을 때
- `n=0`인데도 최소 한 번은 실행되는 것처럼 보이는 함수 동작을 이해하려 할 때

## 핵심 개념

### 원본 C 코드
```c
int factorial_do(int n) {
    int result = 1;
    int i = 1;
    do {
        result *= i;
        i++;
    } while (i <= n);
    return result;
}
```

### -O0 x86-64 어셈블리
```asm
factorial_do:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-0x14], edi   ; n
    mov     dword [rbp-4], 1   ; result = 1
    mov     dword [rbp-8], 1   ; i = 1
.L_body:
    mov     eax, [rbp-4]
    imul    eax, [rbp-8]
    mov     [rbp-4], eax        ; result *= i
    add     dword [rbp-8], 1    ; i++
    mov     eax, [rbp-8]
    cmp     eax, [rbp-0x14]
    jle     .L_body              ; i <= n 이면 되돌아감
    mov     eax, [rbp-4]
    leave
    ret
```

### for/while과의 결정적 차이
```asm
; for/while (REV-1051, REV-1052)          ; do-while (이 글)
    <초기화>                                    <초기화>
    jmp   .L_cond      <-- 이 줄이 핵심!         .L_body:      <-- 초기화 직후 바로 여기로 떨어짐
.L_body:                                        <본문>
    <본문>                                       <조건 검사>
.L_cond:                                        j<cc> .L_body
    <조건 검사>
    j<cc> .L_body
```
`for`/`while`은 초기화 뒤에 **조건 검사로 먼저 점프하는 `jmp` 한 줄**이 반드시 있다(0회 실행 가능성을 보장하기 위함). `do-while`은 이 `jmp`가 **없다** — 초기화가 끝나면 바로 다음 명령이 본문의 첫 줄이 된다. 그리고 조건 검사는 본문 실행 후 맨 아래에서 딱 한 번, 조건부 백점프(`jle .L_body`)로만 이루어진다. 즉 **do-while에는 무조건 점프가 없고, for/while에는 있다**는 것이 어셈블리 레벨에서 가장 확실한 구분법이다.

### 디컴파일러가 복원한 pseudocode
```c
int factorial_do(int n)
{
  int result = 1;
  int i = 1;
  do {
    result *= i;
    i++;
  } while (i <= n);
  return result;
}
```
do-while은 for/while과 달리 진입부 `jmp`가 없는 독특한 구조이기 때문에, IDA/Ghidra는 이 셋 중 do-while만큼은 비교적 정확하게 `do { ... } while(...)` 형태로 복원해준다. 반대로 만약 디컴파일러가 `while(...)` 앞에 `if(...)`로 감싸서 "조건이 처음부터 거짓이면 본문을 건너뛰는" pseudocode를 만들어냈다면, 그건 진입부에 실제로 `jmp .L_cond`가 있었다는 뜻이므로 do-while이 아니라 for/while이라는 확실한 신호다.

## 화면/코드에서 보이는 징후
- 함수(또는 이전 코드) 바로 뒤에 조건 검사 없이 곧바로 루프 본문 코드가 나온다.
- 루프 본문 맨 아래에 `cmp` + 조건부 분기(`jle`, `jl` 등) 하나만 있고, 그 목적지가 본문 시작 주소다.
- 루프 진입 전에 `jmp`가 전혀 없다 — 초기화 대입문 다음 줄이 곧바로 레이블(`.L_body`)이자 본문의 첫 실행 명령이다.

## 가장 먼저 할 것
루프 뼈대를 봤을 때 초기화 코드 바로 다음에 `jmp`가 있는지부터 확인한다. 없으면 do-while, 있으면 for/while(REV-1051, REV-1052)이다. 이 한 가지 체크만으로 세 종류의 대분류가 끝난다.

## 단계별 절차
1. 초기화 코드(대입문들) 바로 다음 줄이 `jmp`인지 아닌지 확인한다.
2. `jmp`가 없다면 do-while로 분류하고, 본문의 마지막 부분에서 `cmp`+조건부 백점프를 찾는다.
3. 그 조건이 참일 때 위로 되돌아가는지(`i <= n`이면 계속) 확인해서 종료 조건을 정확히 서술한다.
4. n이 애초에 조건을 만족하지 않는 값(예: n=0)이어도 본문이 최소 1회는 실행된다는 점을 리포트에 명시한다 — 이게 do-while만의 동작 특성이다.

## 명령어/단축키
```
(gdb) disas factorial_do
(gdb) break factorial_do
(gdb) stepi         # 진입 직후 jmp 여부를 명령어 단위로 직접 확인
```
IDA/Ghidra: 함수 진입 첫 블록의 자식 노드가 바로 루프 본문 블록인지(=do-while), 별도의 조건 검사 블록인지(=for/while)를 그래프 뷰에서 확인.

## 출력 해석
- `imul eax, [rbp-8]`은 `result *= i`의 signed 곱셈이며, 결과가 다시 `[rbp-4]`(`result`)에 저장된다.
- 맨 아래 `cmp eax, [rbp-0x14]` / `jle .L_body`는 "i(방금 증가된 값) <= n이면 계속"이라는 뜻이다. `i++`가 조건 검사 **이전**에 실행되므로, 조건 검사 시점의 `i` 값은 이미 증가된 다음 값이라는 점에 주의해야 한다 — 조건식 위치와 증감 위치의 순서를 헷갈리면 반복 횟수를 하나 잘못 셀 수 있다.

## 흔한 실수
- do-while을 for/while과 같은 뼈대로 착각해서 "0회 실행 가능"이라고 잘못 서술하는 것 — do-while은 조건과 무관하게 최소 1회 실행이 구조적으로 보장된다.
- `-O2`에서 컴파일러가 do-while 루프를 그대로 두는 경우가 많다는 점(do-while은 이미 "조건 검사가 뒤에 있는" 최적화된 형태이므로 for/while처럼 진입부 jmp를 제거하는 추가 변환이 필요 없음)과 달리, for/while 쪽은 최적화 시 이 do-while 모양으로 변환(loop rotation)되는 경우가 흔하다는 점을 놓치는 것. 즉 `-O2`로 컴파일된 for 루프의 어셈블리가 진입부 `jmp` 없이 이 글의 do-while 모양과 똑같이 나올 수 있다 — 이 경우 소스가 for였는지 do-while이었는지는 어셈블리만으로 절대 구분 불가능해진다(디컴파일러는 이때 종종 `if(cond) { do {...} while(cond); }` 형태의 가드(guard)를 붙여서 for/while의 0회 실행 가능성을 표현하기도 한다).
- 조건 검사에 쓰인 값이 증감 전 값인지 증감 후 값인지 확인 안 하고 반복 횟수를 셈하는 것.

## 막혔을 때 다음 체크
- for/while과의 어셈블리 차이를 다시 확인하려면 → REV-1051(for 루프가 어셈블리에서 보이는 패턴), REV-1052(while 루프가 어셈블리에서 보이는 패턴).
- `-O2`에서 for 루프가 do-while 모양(loop rotation)으로 바뀌는 현상이 더 궁금하면 → REV-0037(컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유).
- 조건부 분기 명령어(`jle`)의 정확한 signed 비교 의미가 헷갈리면 → REV-0069(JG JGE JL JLE: Signed 비교 분기).

## 미니 예제
사용자 입력을 최소 한 번은 받아야 하는 입력 검증 루프가 do-while의 전형적인 실전 사용 예다.
```c
int read_positive(void) {
    int x;
    do {
        x = get_input();
    } while (x <= 0);
    return x;
}
```
```asm
read_positive:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
.L_body:
    call    get_input
    mov     [rbp-4], eax       ; x = get_input()
    cmp     dword [rbp-4], 0
    jle     .L_body             ; x <= 0 이면 다시 입력받음
    mov     eax, [rbp-4]
    leave
    ret
```
함수 진입 직후 바로 `.L_body`로 떨어지는(별도의 `jmp`나 조건 검사 없음) 것이 do-while의 특징을 가장 단순하게 보여준다. `get_input()` 호출 자체에 대해서는 REV-0071을 참고한다.

## 관련 글
- REV-1051 — for 루프가 어셈블리에서 보이는 패턴
- REV-1052 — while 루프가 어셈블리에서 보이는 패턴
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0037 — 컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유

## 출처/검증
- do-while이 for/while과 달리 진입부 무조건 점프 없이 곧바로 본문으로 진입하는 컴파일 패턴은 x86-64 System V ABI 환경의 gcc/clang `-O0` 실제 출력에서 반복 확인된다.
- 루프 회전(loop rotation) 최적화(for/while을 do-while 형태로 변환해 조건 검사 횟수를 줄이는 기법): GCC/LLVM 루프 최적화 패스 공식 문서 기준 (2026-09-10 검증).
