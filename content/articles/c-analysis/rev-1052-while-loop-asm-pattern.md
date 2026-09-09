---
id: REV-1052
title: "while 루프가 어셈블리에서 보이는 패턴"
slug: "rev-1052-while-loop-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["while 루프 어셈블리", "while loop assembly pattern", "조건 검사 루프 어셈블리"]
aliases: ["while문 어셈블리에서 어떻게 보임", "while 루프 디스어셈블", "while과 for 어셈블리 차이"]
symptom_keywords: ["while 루프인지 for 루프인지 어셈블리로 구분이 안됨", "조건이 왜 루프 맨 아래에 있는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`while` 루프는 -O0에서 `for` 루프와 **어셈블리 뼈대가 완전히 동일**하게 컴파일된다 — "조건 검사로 먼저 점프 → 본문 → 조건 검사(맨 아래)"라는 모양은 그대로이며, 차이는 오직 증감식이 본문 안에 문법적으로 따로 안 분리되어 있다는 소스 레벨 차이일 뿐 바이너리에는 흔적이 남지 않는다.

## 언제 검색해야 하나
- 루프를 찾았는데 REV-1051에서 배운 for 루프 모양과 구분이 안 될 때, "이게 진짜 while인지 for인지 확인할 방법이 있는지" 궁금할 때
- 소스 코드 없이 바이너리만 보고 리포트를 쓸 때 "for문입니다" vs "while문입니다"를 어떻게 판단해야 하는지 궁금할 때
- 디컴파일러가 `while(...)`로 보여줬는데 실제로는 `for`였을 수도 있다는 이야기를 듣고 확인하고 싶을 때

## 핵심 개념

### 원본 C 코드
```c
int count_digits(int n) {
    int count = 0;
    while (n != 0) {
        n = n / 10;
        count++;
    }
    return count;
}
```

### -O0 x86-64 어셈블리
```asm
count_digits:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-0x14], edi   ; n
    mov     dword [rbp-4], 0   ; count = 0
    jmp     .L_cond            ; 조건 검사로 먼저 점프
.L_body:
    mov     eax, [rbp-0x14]
    mov     ecx, 10
    cdq
    idiv    ecx
    mov     [rbp-0x14], eax    ; n = n / 10
    add     dword [rbp-4], 1   ; count++
.L_cond:
    cmp     dword [rbp-0x14], 0
    jne     .L_body            ; n != 0 이면 본문으로 되돌아감
    mov     eax, [rbp-4]
    leave
    ret
```

### REV-1051의 for 루프와 정면 비교
```asm
; for 루프 뼈대 (REV-1051)
    <초기화>
    jmp   .L_cond
.L_body:
    <본문>
    <증감>
.L_cond:
    <조건 검사>
    j<cc> .L_body

; while 루프 뼈대 (이 글)
    <초기화(있으면)>
    jmp   .L_cond
.L_body:
    <본문(증감 로직이 본문 안에 자연스럽게 섞여 있음)>
.L_cond:
    <조건 검사>
    j<cc> .L_body
```
두 뼈대는 **한 글자도 다르지 않다**. 유일한 "차이"는 `for`의 증감식(`i++`)이 소스에서 세미콜론으로 명시적으로 분리되어 있었다는 것뿐이고, 컴파일 결과에서는 증감 코드가 그냥 본문 블록의 마지막 명령어들로 합쳐져서 `for`의 증감이었는지 `while` 본문 안에 있던 일반 대입문이었는지 구분할 표시가 전혀 남지 않는다.

### 디컴파일러가 복원한 pseudocode
```c
int count_digits(int n)
{
  int count = 0;
  while (n != 0) {
    n = n / 10;
    count++;
  }
  return count;
}
```
IDA/Ghidra는 진입부 `jmp` + 맨 아래 조건부 백점프 패턴을 보고 `while`로 복원하는 경우가 많지만, 완전히 동일한 패턴을 REV-1051 예제에 적용하면 `for`로도 복원한다 — **디컴파일러의 선택은 힌트일 뿐 증거가 아니다.** 두 구문이 바이너리 레벨에서 구분 불가능하다는 사실 자체를 알고 있는 것이 중요하다. 실무에서는 "이게 for인지 while인지"를 굳이 구분하려 하지 말고, "초기화 몇 번, 조건 검사 위치, 증감이 있는지"라는 **동작(behavior)** 관점으로 리포트를 쓰는 게 정확하다.

## 화면/코드에서 보이는 징후
- REV-1051과 똑같이 진입부에 `jmp .L_cond`, 본문 블록, 맨 아래 `cmp`+조건부 백점프.
- `for`처럼 카운터 변수의 초기화-조건-증감이 소스에서 한곳에 몰려 있던 형태가 아니라, 조건 검사에 쓰이는 변수가 함수 인자 자체(`n`)이거나 이전에 이미 초기화된 변수인 경우가 많다.
- 조건식이 단순 카운터 비교(`i < n`)가 아니라 더 복잡한 연산 결과 비교(`n != 0`, 포인터 NULL 체크 등)인 경우 `while`일 가능성이 소스 스타일상 높지만, 이 역시 바이너리만으로 확정할 수는 없다.

## 가장 먼저 할 것
루프의 뼈대(진입부 jmp, 본문, 맨 아래 조건검사)를 REV-1051과 같은 방식으로 먼저 식별한다. 그다음 "이게 for인지 while인지"에 매달리지 말고, 조건 변수가 무엇이고 본문에서 어떻게 갱신되는지부터 정리한다 — 리포트에는 "n이 0이 될 때까지 10으로 나누는 루프"처럼 동작으로 서술하는 것이 for/while 이름표보다 훨씬 유용하다.

## 단계별 절차
1. 진입부 `jmp` 유무를 확인해 for/while류(있음)인지 do-while류(없음, REV-1053)인지 1차 분류한다.
2. 맨 아래 조건 검사 블록의 `cmp` 대상이 무엇인지 확인한다 — 단순 증가 카운터면 for로 작성됐을 가능성이 크고, 복잡한 계산 결과나 포인터면 while로 작성됐을 가능성이 크다(단, 이건 추정일 뿐 확정할 수 없다).
3. 본문 블록에서 조건 변수를 갱신하는 코드를 찾는다(`n = n / 10` 같은 연산).
4. 소스 복원 리포트를 쓸 때는 "for 루프" 대신 "n이 0이 될 때까지 반복" 식으로 동작 위주로 서술해 오판 리스크를 줄인다.

## 명령어/단축키
```
(gdb) disas count_digits
(gdb) watch *(int*)&n     # n 변경 추적(실제로는 스택 오프셋 지정)
(gdb) break .L_cond       # 조건 검사 시점마다 값 확인
```
IDA/Ghidra: 그래프 뷰에서 진입 화살표가 조건 검사 블록으로 바로 들어가는지, 본문 블록에서 위로 되돌아가는지 시각적으로 확인.

## 출력 해석
- `cdq`+`idiv ecx`는 `n / 10`의 signed 나눗셈이다(`cdq`가 `edx:eax`를 부호 확장해서 나눗셈 준비). 이 나눗셈 결과가 다시 `n`에 저장되는 걸 보고 "조건 변수가 매 반복마다 줄어드는 구조"임을 알 수 있다 — 종료를 보장하는 근거다.
- `cmp dword [rbp-0x14], 0` / `jne .L_body`는 "n != 0이면 계속"이라는 뜻이며, `n`이 0이 되는 순간 자연스럽게 다음 명령(함수 나머지)으로 흘러간다.

## 흔한 실수
- 디컴파일러가 `while`로 보여줬다고 원본 소스가 100% `while`이었다고 리포트에 확정적으로 쓰는 것 — for/while은 바이너리 레벨에서 구분 불가능하므로 "루프 형태(for 또는 while)" 정도로 유보적으로 서술해야 한다.
- `-O2` 이상에서는 나눗셈이 매직 넘버(magic number) 곱셈+시프트 조합(`imul`, `sar`, `add` 등)으로 강도 감소(strength reduction)될 수 있어 `idiv`가 안 보일 수 있다. `idiv`가 없다고 나눗셈이 없는 게 아니라 최적화된 형태로 바뀐 것일 수 있다는 점을 REV-0037과 함께 체크한다.
- 조건이 항상 참인 무한루프(`while(1)`)와 일반 while을 혼동하는 것 — `while(1){...}`은 조건 검사 자체가 생략되고 진입부 `jmp` 없이 바로 본문으로 진입하며 본문 끝에 `jmp .L_body`로 무조건 되돌아가는 경우가 많다. 이 경우 `cmp` 없이 `jmp`만 반복되는 게 특징이다.

## 막혔을 때 다음 체크
- for와의 어셈블리 뼈대가 왜 같은지 다시 확인하려면 → REV-1051(for 루프가 어셈블리에서 보이는 패턴).
- 조건 검사 위치가 맨 위가 아니라 진입 직후 본문이 무조건 실행되는 모양이라면 → REV-1053(do-while 루프가 어셈블리에서 보이는 패턴).
- 나눗셈이 `idiv` 없이 곱셈/시프트로 바뀐 모양이 헷갈리면 → REV-0037(컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유).
- 조건부 분기 명령어 종류가 헷갈리면 → REV-0068(JNE와 JNZ: ZF가 0일 때 분기).

## 미니 예제
포인터를 따라가며 끝(NULL)을 찾는 전형적인 while 패턴도 같은 뼈대를 따른다.
```c
int list_length(Node *head) {
    int len = 0;
    while (head != NULL) {
        head = head->next;
        len++;
    }
    return len;
}
```
```asm
list_length:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-8], rdi     ; head
    mov     dword [rbp-4], 0  ; len = 0
    jmp     .L_cond
.L_body:
    mov     rax, [rbp-8]
    mov     rax, [rax]        ; head->next (Node의 첫 필드로 가정)
    mov     [rbp-8], rax       ; head = head->next
    add     dword [rbp-4], 1   ; len++
.L_cond:
    cmp     qword [rbp-8], 0
    jne     .L_body            ; head != NULL 이면 계속
    mov     eax, [rbp-4]
    leave
    ret
```
포인터 NULL 체크(`cmp qword [rbp-8], 0`)가 조건식 자리에 온 것만 다르고, 진입부 `jmp`, 본문, 맨 아래 조건검사라는 뼈대는 앞의 `count_digits`와 동일하다. 구조체 포인터 역참조 세부는 REV-1062를 참고한다.

## 관련 글
- REV-1051 — for 루프가 어셈블리에서 보이는 패턴
- REV-1053 — do-while 루프가 어셈블리에서 보이는 패턴
- REV-1062 — 포인터 역참조가 어셈블리에서 보이는 패턴
- REV-0068 — JNE와 JNZ: ZF가 0일 때 분기
- REV-0037 — 컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유

## 출처/검증
- gcc/clang `-O0`에서 `for`와 `while`이 동일한 제어 흐름 그래프(진입부 조건 점프, 본문, 맨 아래 백엣지)로 컴파일되는 현상은 x86-64 System V ABI 환경에서 실제 컴파일 출력으로 반복 확인된다.
- 나눗셈의 강도 감소(strength reduction, 매직 넘버 곱셈으로 대체) 최적화: GCC/LLVM 최적화 패스 공식 문서 기준 (2026-09-10 검증).
