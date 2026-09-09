---
id: REV-1068
title: "continue문이 있는 for 루프가 어셈블리에서 보이는 패턴"
slug: "rev-1068-for-loop-continue-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["continue 어셈블리 패턴", "for loop continue assembly pattern", "루프 갱신부로 점프", "continue문 컴파일"]
aliases: ["continue문 어셈블리", "루프 다음 반복으로 점프", "loop skip iteration asm"]
symptom_keywords: ["continue문이 어셈블리에서 어디로 점프하는지 못 찾음", "break와 continue 점프 목적지가 헷갈림"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`continue`문은 루프 몸통의 나머지를 건너뛰고 **루프의 갱신부(`i++` 등)로 점프**하는 `JMP`로 나타나며, `break`(루프 완전히 종료, REV-1067)와 목적지가 다르다는 점이 이 둘을 구분하는 핵심이다.

## 언제 검색해야 하나
- 루프 몸통 중간에 `jmp`가 있는데 그 목적지가 루프 종료 지점이 아니라 갱신부(`i++` 해당 코드) 쪽인 것을 발견했을 때
- `break`와 `continue`가 코드에서 어떻게 다르게 컴파일되는지 구분해서 읽어야 할 때
- `for` 루프의 갱신부 위치가 예상과 달라서 어디가 `i++`에 해당하는지 못 찾을 때
- `while`/`for` 루프인데 몸통 안에 조건부로 "일부 반복을 스킵"하는 로직이 있어서 그 흐름을 확인해야 할 때

## 핵심 개념
`for (초기화; 조건; 갱신) { 몸통 }` 구조에서 `continue`는 "몸통의 나머지를 실행하지 말고 곧바로 **갱신** 단계로 가라"는 뜻이다. `for` 루프의 경우 갱신부(`i++`)가 조건 재검사 **전에** 실행되므로, `continue`의 점프 목적지는 갱신부 레이블이다. (`while` 루프에는 별도의 갱신부가 없으므로 `continue`가 곧바로 조건 검사 레이블로 간다 — 구조가 살짝 다르다.)

```c
int sum_even(int *arr, int n) {
    int i, sum = 0;
    for (i = 0; i < n; i++) {
        if (arr[i] % 2 != 0) {
            continue;      /* 몸통 나머지(sum += arr[i])를 건너뛰고 i++로 */
        }
        sum += arr[i];
    }
    return sum;
}
```

`break`(REV-1067)는 "루프 전체를 끝내는 레이블"로 점프하지만, `continue`는 "이번 반복만 끝내고 다음 반복을 준비하는 레이블(갱신부)"로 점프한다. 목적지가 다르다는 것 외에는 둘 다 "몸통 중간에서 무조건 점프가 발생한다"는 점은 똑같으므로, **점프 목적지 레이블이 갱신부인지 루프 종료 지점인지**를 확인하는 것이 `break`와 `continue`를 구분하는 유일한 방법이다.

## 화면/코드에서 보이는 징후
- 몸통 중간에서 발생하는 `jmp`의 목적지가 **루프 갱신 코드(`add ..., 1` 등 바로 앞)** 레이블임
- 그 레이블은 루프 조건 검사 레이블과는 다른, 갱신부 전용 레이블(예: `.L_update`)
- Ghidra pseudocode에서는 `continue;`가 그대로 복원되거나, 몸통 나머지가 `else` 블록으로 재구성되어 보이기도 함
- 같은 루프 안에 `break`(→ 종료 레이블)와 `continue`(→ 갱신 레이블)가 함께 있으면 목적지가 서로 다른 두 종류의 점프가 섞여 나타남

## 가장 먼저 할 것
몸통 중간의 `jmp` 목적지 레이블을 확인한다. 그 레이블 바로 다음 코드가 `i++`처럼 루프 변수를 갱신하는 코드라면 `continue`, 함수의 나머지 리턴 코드나 루프 완전 종료 코드라면 `break`(REV-1067)다.

## 단계별 절차
1. 루프의 갱신부 레이블(`i++` 코드가 있는 곳)과 조건 검사 레이블을 먼저 찾아 정상 흐름을 표시한다.
2. 몸통 안에서 조건부로 발생하는 `jmp`를 찾는다.
3. 그 `jmp`의 목적지가 1번에서 찾은 갱신부 레이블과 같은지 확인한다 — 같으면 `continue`다.
4. `continue` 직전의 조건(`cmp`)이 원본 C의 `if (조건) continue;`에서 어떤 조건이었는지 역추적한다(조건이 반전되어 있을 수 있음: `if (조건이 아니면) 몸통 계속 실행`으로 컴파일되는 경우가 흔함).
5. 디버거로 그 조건을 만족하는 입력을 넣어 실행해, 몸통 나머지(`sum += arr[i]` 등)가 정말 스킵되고 `i++`로 바로 넘어가는지 확인한다.

## 명령어/단축키
- IDA/Ghidra: 그래프 뷰에서 몸통 블록에서 나가는 화살표가 갱신부 블록으로 곧바로 연결되는지 확인
- GDB: 갱신부 레이블 주소와 몸통 중간 `jmp` 주소 각각에 브레이크포인트를 걸어 어느 경로로 흐르는지 실행 순서로 확인
- x64dbg: 그래프 뷰에서 동일하게 화살표 목적지 확인, 조건부 실행(홀수/짝수 등)으로 스텝하며 검증

## 출력 해석
```c
int sum_even(int *arr, int n) {
    int i, sum = 0;
    for (i = 0; i < n; i++) {
        if (arr[i] % 2 != 0) {
            continue;
        }
        sum += arr[i];
    }
    return sum;
}
```

```asm
; sum_even, rdi=arr, esi=n
sum_even:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 32
    mov     [rbp-24], rdi
    mov     [rbp-28], esi
    mov     dword [rbp-4], 0      ; sum = 0
    mov     dword [rbp-8], 0      ; i = 0
.L_cond:
    mov     eax, [rbp-8]
    cmp     eax, [rbp-28]
    jge     .L_end                ; i < n 거짓 -> 루프 완전 종료
    mov     eax, [rbp-8]
    lea     rdx, [rax*4]
    mov     rax, [rbp-24]
    add     rax, rdx
    mov     eax, [rax]            ; eax = arr[i]
    mov     ecx, eax
    and     ecx, 1                ; arr[i] % 2 (2의 거듭제곱 나머지는 AND로 대체됨)
    test    ecx, ecx
    je      .L_add                ; 짝수(나머지 0)면 sum 더하는 코드로
    jmp     .L_update             ; *** continue: 몸통 나머지 건너뛰고 갱신부로 ***
.L_add:
    mov     eax, [rbp-8]
    lea     rdx, [rax*4]
    mov     rax, [rbp-24]
    add     rax, rdx
    mov     eax, [rax]
    add     [rbp-4], eax          ; sum += arr[i]
.L_update:
    add     dword [rbp-8], 1      ; i++
    jmp     .L_cond
.L_end:
    mov     eax, [rbp-4]
    leave
    ret
```

`jmp .L_update`가 바로 `continue`다. `.L_update`는 갱신부(`i++`)이지 루프 종료 지점(`.L_end`)이 아니다. 조건이 `arr[i] % 2 != 0`(홀수면 continue)이었지만 어셈블리에서는 `je .L_add`(나머지가 0, 즉 짝수면 더하는 코드로)로 **조건이 반전**되어 나타난다 — `if (조건) continue`가 `if (!조건) 몸통 실행 후 갱신`으로 뒤집혀 컴파일되는 것은 매우 흔한 패턴이다. `and ecx, 1`은 `% 2` 연산이 최하위 비트만 보는 것과 같으므로 `AND`로 대체된 것이다.

## 흔한 실수
- `continue`의 점프 목적지(갱신부)와 `break`의 점프 목적지(루프 종료)를 구분하지 않고 둘 다 "루프 관련 점프"로 뭉뚱그려 읽는 것.
- 조건이 반전되어 있는 것(`!= 0` 조건인데 `je`가 나오는 것)을 보고 원본 조건을 잘못 복원하는 것 — 분기 방향과 조건식은 항상 반대일 수 있음을 기억해야 한다.
- `% 2` 같은 나머지 연산이 `AND`로 최적화된 것을 보고 "나머지 연산이 아니다"라고 오판하는 것 — 2의 거듭제곱 나머지는 항상 `AND`로 대체될 수 있다.
- `continue`가 갱신부로 가는 것을, `while` 루프에서는 조건 검사부로 직접 간다는 차이를 무시하고 `for`와 `while`을 같은 패턴으로 취급하는 것.

## 막혔을 때 다음 체크
- `break`와의 목적지 차이를 다시 비교하려면 → REV-1067 break문이 있는 for 루프가 어셈블리에서 보이는 패턴
- 기본 for 루프 구조 자체가 헷갈리면 → REV-1051 for 루프가 어셈블리에서 보이는 패턴
- while 루프의 기본 구조가 궁금하면 → REV-1052 while 루프가 어셈블리에서 보이는 패턴
- 조건 분기의 반전 패턴이 헷갈리면 → REV-0067 JE와 JZ, REV-0068 JNE와 JNZ

## 미니 예제
`while` 루프에서 같은 로직을 쓰면 `continue`의 목적지가 갱신부가 아니라 조건 검사부 자체로 바뀐다:
```c
i = 0;
while (i < n) {
    if (arr[i] % 2 != 0) { i++; continue; }
    sum += arr[i];
    i++;
}
```
이 형태에서는 `i++`가 코드에 두 번(continue 경로용, 정상 경로용) 등장하거나, 컴파일러가 `i++`를 공통 지점으로 합쳐서 `continue`가 그 공통 지점으로 점프하도록 만들 수도 있다. `for`처럼 문법적으로 분리된 갱신부가 없기 때문에 `while`의 `continue`는 항상 개별 코드를 잘 살펴야 한다.

## 관련 글
- REV-1067 — break문이 있는 for 루프가 어셈블리에서 보이는 패턴
- REV-1051 — for 루프가 어셈블리에서 보이는 패턴
- REV-1052 — while 루프가 어셈블리에서 보이는 패턴
- REV-0067 — JE와 JZ: ZF가 1일 때 분기
- REV-0068 — JNE와 JNZ: ZF가 0일 때 분기

## 출처/검증
- C 표준상 `continue`문이 현재 반복의 나머지를 건너뛰고 루프 갱신/조건 검사로 이동하는 제어 흐름 규칙: ISO C 표준(반복문/continue 절) 기준.
- gcc/clang `-O0`에서 `continue`가 갱신부 레이블로의 `JMP`로 컴파일되고, 조건이 반전되어 분기 명령이 배치되는 패턴, 2의 거듭제곱 나머지 연산이 `AND`로 대체되는 최적화는 x86-64 리눅스/윈도우 환경에서 반복 확인되는 표준 패턴이다(2026-09-10 검증).
