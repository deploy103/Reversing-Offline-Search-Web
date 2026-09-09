---
id: REV-1054
title: "if-else가 어셈블리에서 보이는 패턴"
slug: "rev-1054-if-else-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["if else 어셈블리", "if else assembly pattern", "조건 분기 어셈블리"]
aliases: ["if else문 어셈블리에서 어떻게 보임", "if else 디스어셈블", "조건문 분기 패턴"]
symptom_keywords: ["if else를 어셈블리에서 못 알아봄", "cmp 다음 분기가 두 갈래인 이유를 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`if-else`는 조건을 검사해 참이면 곧바로 본문(then)을 실행하고 거짓이면 반대로 뛰어넘는 **반대 조건(inverted condition)으로 else 블록으로 분기**한 뒤, then 블록 끝에서 else 블록을 건너뛰는 무조건 점프(`jmp`) 하나가 붙는 "두 블록 + 합류 지점" 모양으로 컴파일된다.

## 언제 검색해야 하나
- `cmp` 뒤에 조건부 분기 하나, 그 아래 코드 블록, 그리고 무조건 `jmp`가 있고, 그 뒤에 또 다른 코드 블록이 이어지는 모양을 발견해서 이게 if-else인지 확인하고 싶을 때
- 소스의 `if (x < 0)` 조건이 어셈블리에서는 반대로 `jge`(크거나 같으면 점프)로 나오는 걸 보고 왜 뒤집혔는지 궁금할 때
- IDA 그래프 뷰에서 한 블록이 두 개의 자식 블록으로 갈라졌다가 다시 하나로 합쳐지는 다이아몬드(diamond) 모양을 봤을 때

## 핵심 개념

### 원본 C 코드
```c
int abs_val(int x) {
    int result;
    if (x < 0) {
        result = -x;
    } else {
        result = x;
    }
    return result;
}
```

### -O0 x86-64 어셈블리
```asm
abs_val:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-0x14], edi   ; x
    cmp     dword [rbp-0x14], 0
    jge     .L_else            ; x >= 0 이면 else로 (조건이 반대로 뒤집힘)
    mov     eax, [rbp-0x14]
    neg     eax
    mov     [rbp-4], eax        ; result = -x   (then 블록)
    jmp     .L_end               ; else 블록을 건너뛰는 무조건 점프
.L_else:
    mov     eax, [rbp-0x14]
    mov     [rbp-4], eax        ; result = x    (else 블록)
.L_end:
    mov     eax, [rbp-4]
    leave
    ret
```

### 줄 단위 대응
- `cmp dword [rbp-0x14], 0` / `jge .L_else` — 소스는 `if (x < 0)`이지만 어셈블리는 정반대 조건인 `x >= 0`을 검사해서 참이면 else로 뛴다. 컴파일러는 항상 **"조건이 거짓일 때 어디로 갈지"**를 조건부 분기로 표현하고, "조건이 참일 때"는 그냥 다음 줄로 자연스럽게 흘러가게(fall-through) 만든다. 그래서 소스의 `<` 조건이 어셈블리에서는 `jge`(반대 조건)로 항상 뒤집혀 보인다.
- then 블록(`neg eax`) 끝의 `jmp .L_end` — else 블록을 건너뛰기 위한 무조건 점프. **이 jmp가 if-else의 확정적 증거**다. 만약 이 jmp가 없다면 else가 없는 단순 if문일 가능성이 크다(REV-1055 참고).
- `.L_else` 레이블과 그 블록 — else 본문.
- `.L_end` 레이블 — then과 else가 다시 합류하는 지점. 두 경로 모두 결국 여기로 모인다.

### 디컴파일러가 복원한 pseudocode
```c
int abs_val(int x)
{
  int result;
  if (x < 0) {
    result = -x;
  } else {
    result = x;
  }
  return result;
}
```
IDA/Ghidra는 조건부 분기의 반대 조건(`jge`)을 다시 뒤집어서(`x >= 0`이 아니라 `x < 0`으로) 사람이 읽기 편한 원래 방향의 조건으로 복원해준다. `neg eax` 같은 단항 연산도 `-x`로 정확히 복원되는 경우가 많아, if-else는 디컴파일러 결과가 원본 소스와 거의 1:1로 대응되는 편에 속한다. 다만 then/else 블록의 코드가 복잡해지면 컴파일러가 두 블록에서 공통되는 코드를 미리 앞으로 끌어올리는(code hoisting) 최적화를 적용해 원본과 다른 모양이 될 수 있다.

## 화면/코드에서 보이는 징후
- `cmp`(또는 `test`) 하나, 그 다음 조건부 분기 하나(목적지가 뒤쪽의 else 레이블).
- 조건부 분기 다음 블록(then) 끝에 무조건 `jmp`가 있고, 그 목적지가 else 블록보다 더 뒤에 있는 합류 레이블.
- IDA 그래프 뷰에서 하나의 블록이 두 갈래로 갈라졌다가(다이아몬드 모양) 바로 다시 하나로 합쳐진다 — 루프처럼 위로 되돌아가는 화살표는 없다.

## 가장 먼저 할 것
조건부 분기를 찾으면 그 조건을 소스 관점으로 뒤집어서 읽는다(`jge`가 보이면 원본은 `<` 조건이었을 가능성이 크다). then 블록 끝에 `jmp`가 있는지부터 확인해서 else 블록의 존재 여부를 판단한다.

## 단계별 절차
1. `cmp`/`test` 다음의 조건부 분기 명령과 그 목적지 주소를 확인한다.
2. 조건부 분기 목적지 이전 코드(then 블록)를 읽고, 그 끝에 무조건 `jmp`가 있는지 확인한다.
3. `jmp`가 있으면 그 목적지가 최종 합류 지점(`.L_end`)이고, 조건부 분기 목적지가 else 블록의 시작이다.
4. then과 else 두 블록이 각각 같은 변수(`result` 등)에 값을 쓰고 합류 지점에서 그 변수를 읽는지 확인해서 두 블록이 진짜 "양자택일" 관계인지 검증한다.

## 명령어/단축키
```
(gdb) disas abs_val
(gdb) break *0x<addr_of_cmp>
(gdb) info registers eax
```
IDA: 그래프 뷰에서 조건부 분기 노드를 클릭하면 두 자식 블록이 색으로 구분되어 표시된다. x64dbg: 조건부 분기에서 `F8`(step over) 대신 분기 예측 표시(초록/빨강 화살표)로 어느 쪽이 실제로 타는지 바로 확인 가능.

## 출력 해석
- 조건부 분기의 방향(taken/not-taken)에 따라 then/else 중 어느 쪽이 실행됐는지는 디버거로 실제 값을 넣어봐야 확실히 알 수 있다. 정적 분석만으로는 두 경로 모두 도달 가능하다고 가정해야 한다.
- then 블록 끝의 `jmp` 목적지와 else 블록 바로 다음 주소가 같다면, else 블록이 곧 합류 지점 바로 앞이라는 뜻이고 코드가 짧게 최적화된 것이다.

## 흔한 실수
- 조건부 분기의 조건을 뒤집지 않고 그대로 읽어서 then/else를 반대로 해석하는 것 — `jge`가 있으면 "크거나 같으면 else"라는 뜻이지 "then"이 아니다.
- then 블록 끝의 `jmp`를 놓치고 else 블록까지 같은 조건 아래 실행되는 코드로 착각하는 것.
- `-O2`에서 then/else 두 블록의 결과가 단순 대입 하나뿐이면 컴파일러가 분기 자체를 없애고 `cmovcc`(조건부 이동, REV-0075)로 대체할 수 있다는 점을 놓치는 것 — 이 경우 `jmp`/레이블 구조 없이 한 줄의 `cmovge`/`cmovl`만 남아 if-else 구조 자체가 사라진 것처럼 보인다.
- else가 없는 단순 if문(REV-1055의 앞부분)과 if-else를 혼동하는 것 — else가 없으면 then 블록 끝에 else를 건너뛸 `jmp`가 필요 없으므로 아예 없거나, 있어도 목적지가 조건부 분기의 목적지와 같아진다.

## 막혔을 때 다음 체크
- 조건이 세 개 이상 이어지는 경우가 궁금하면 → REV-1055(if-elseif-else 체인이 어셈블리에서 보이는 패턴).
- 분기 대신 `cmovcc`로 대체된 경우가 궁금하면 → REV-0075(CMOVcc: 분기 없는 조건부 이동), REV-1073(삼항 연산자가 CMOV 또는 분기로 컴파일되는 패턴).
- `cmp`/`test`의 정확한 동작이 헷갈리면 → REV-0060(CMP), REV-0059(TEST).
- 조건부 분기 명령어 자체(`jge`, `jl` 등)의 의미가 헷갈리면 → REV-0069(JG JGE JL JLE: Signed 비교 분기).

## 미니 예제
두 값 중 더 큰 값을 고르는 함수도 같은 뼈대를 따른다.
```c
int max2(int a, int b) {
    int result;
    if (a > b) {
        result = a;
    } else {
        result = b;
    }
    return result;
}
```
```asm
max2:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-4], edi     ; a
    mov     [rbp-8], esi     ; b
    mov     eax, [rbp-4]
    cmp     eax, [rbp-8]
    jle     .L_else            ; a > b가 거짓(a <= b)이면 else
    mov     eax, [rbp-4]
    mov     [rbp-0xc], eax     ; result = a
    jmp     .L_end
.L_else:
    mov     eax, [rbp-8]
    mov     [rbp-0xc], eax     ; result = b
.L_end:
    mov     eax, [rbp-0xc]
    leave
    ret
```
`a > b`의 반대 조건인 `jle`(작거나 같으면 else)로 뒤집혀 있는 것, then 블록 끝의 `jmp .L_end`, 그리고 두 블록이 합류하는 구조가 앞의 `abs_val`과 동일하다.

## 관련 글
- REV-1055 — if-elseif-else 체인이 어셈블리에서 보이는 패턴
- REV-1073 — 삼항 연산자(?:)가 CMOV 또는 분기로 컴파일되는 패턴
- REV-0075 — CMOVcc: 분기 없는 조건부 이동
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0069 — JG JGE JL JLE: Signed 비교 분기

## 출처/검증
- 컴파일러가 조건을 반전시켜 "거짓일 때 분기"로 코드를 생성하고 참일 때는 fall-through로 처리하는 방식은 x86-64 gcc/clang `-O0` 실제 출력에서 반복 확인되는 표준 패턴이다.
- 단순 대입 결과의 조건부 이동(`cmovcc`) 대체 최적화: GCC/LLVM 공식 최적화 문서 및 x86-64 명령어 세트 설명 기준 (2026-09-10 검증).
