---
id: REV-1062
title: "포인터 역참조가 어셈블리에서 보이는 패턴"
slug: "rev-1062-pointer-dereference-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["포인터 역참조 어셈블리", "pointer dereference assembly pattern", "이중 포인터", "double pointer asm"]
aliases: ["별표 역참조 어셈블리", "포인터 읽기 쓰기 패턴", "asterisk dereference in asm"]
symptom_keywords: ["포인터 역참조를 어셈블리에서 못 알아봄", "이중 포인터가 어셈블리에서 뭘 하는지 모름"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`*p`처럼 포인터를 역참조하는 코드는 항상 "레지스터에 주소를 담고, 그 레지스터를 대괄호로 감싸서 메모리를 읽거나 쓴다"는 두 단계로 쪼개지며, `**pp`(이중 포인터)는 이 과정이 한 번 더 반복되어 `mov`가 연쇄적으로 늘어난다.

## 언제 검색해야 하나
- 소스에 `*p`, `*p = 값`, `**pp` 같은 코드가 있는데 실제 어셈블리에서 어느 줄이 그에 대응하는지 못 찾을 때
- `mov rax, [rax]`처럼 같은 레지스터가 반복되는 줄을 보고 무한루프인지 착각할 때
- IDA/Ghidra pseudocode에 `*(int *)a1`처럼 캐스트가 붙은 역참조가 나올 때 원래 C 타입이 뭐였는지 감을 못 잡을 때

## 핵심 개념
C에서 포인터 역참조는 "이 주소에 있는 값을 읽어와라(`*p`)" 또는 "이 주소에 이 값을 써라(`*p = v`)"라는 뜻이다. 어셈블리에서는 레지스터 자체가 주소를 담을 수도 있고 값을 담을 수도 있는데, **대괄호(`[]`)로 감싸느냐 아니냐**가 그 경계선이다.

- `mov rax, [rbp-8]` — `rbp-8`은 지역변수가 저장된 스택 슬롯의 **주소**이고, 여기서 값을 읽어 `rax`에 넣는다. 이 시점 `rax`는 포인터 변수 `p`의 **값**(즉 p가 가리키는 주소)이다.
- `mov edx, [rax]` — 이제 `rax`(포인터 값)를 다시 대괄호로 감싸서, `rax`가 가리키는 메모리에서 값을 읽는다. 이것이 바로 `*p`다.

즉 `*p`는 최소 두 번의 `mov`(포인터 변수 자체 로드 + 그 값으로 실제 메모리 접근)로 나타나며, `**pp`는 세 번(포인터 변수 로드 + 1차 역참조 + 2차 역참조)이 필요하다.

쓰기(`*p = 5`)는 방향이 반대다. 주소를 레지스터에 담은 뒤, 그 레지스터를 대괄호로 감싼 곳에 값을 쓴다: `mov rax, [rbp-8]` (p 로드) 다음 `mov dword [rax], 5` (그 주소에 5 저장).

## 화면/코드에서 보이는 징후
- `mov reg, [reg]` 형태로 **같은 레지스터가 좌변·우변에 걸쳐 재사용**되는 줄이 역참조다
- 이중 포인터는 이 패턴이 연속 두 번 나온다: `mov rax,[rax]` → `mov rax,[rax]` (혹은 `mov eax,[rax]`로 마무리)
- Ghidra pseudocode의 `*param_1`, `**param_1`, `*(int *)*param_1` 표현이 바로 이 역참조 횟수를 그대로 반영한다
- 쓰기 방향은 `mov [rax], edx`처럼 **대괄호가 목적지(왼쪽)**에 오는 형태로 구분된다

## 가장 먼저 할 것
문제가 되는 `mov` 줄에서 대괄호가 어느 쪽(좌변/우변)에 있는지부터 확인한다. 우변에 대괄호가 있으면 "읽기"(역참조해서 값을 가져옴), 좌변에 대괄호가 있으면 "쓰기"(역참조한 곳에 값을 저장)다. 그다음 같은 레지스터가 몇 번 연쇄적으로 재사용되는지 세면 포인터가 몇 단계인지(단일 포인터 vs 이중 포인터) 바로 알 수 있다.

## 단계별 절차
1. 함수 인자가 스택에 저장되는 첫 줄(`mov [rbp-8], rdi`)에서 이 슬롯이 포인터 타입 인자임을 확인한다.
2. 그 슬롯을 레지스터로 로드하는 줄(`mov rax, [rbp-8]`)을 찾는다 — 이건 포인터 "변수" 자체를 가져오는 것이지 아직 역참조가 아니다.
3. 바로 이어서 그 레지스터를 다시 대괄호로 감싸는 줄이 있는지 본다. 있다면 그게 1차 역참조(`*p`)다.
4. 그 결과를 또 대괄호로 감싸면 2차 역참조(`**pp`)다. 이 단계가 몇 번 반복되는지가 포인터의 "깊이"다.
5. GDB에서 `x/gx $rax`(64비트) 또는 `x/wx $rax`(32비트)로 각 단계의 실제 메모리 내용을 찍어보며 값이 유효한 주소인지 실제 데이터인지 구분하면 확실하다.

## 명령어/단축키
- GDB: `x/gx $rax` (역참조 전 rax가 가리키는 8바이트 확인), `p *(int*)$rax` (역참조 결과를 int로 해석)
- x64dbg: 레지스터 값 우클릭 → `Follow in Dump` → 그 주소의 실제 바이트 확인
- IDA: 변수에 `int *`, `int **` 타입을 지정하면 pseudocode가 `*p`, `**pp` 형태로 정리되어 훨씬 읽기 쉬워짐
- Ghidra: `Retype Variable`로 포인터 깊이를 지정하면 동일하게 정리됨

## 출력 해석
```c
int deref_read(int *p) {
    return *p;
}

void deref_write(int *p) {
    *p = 5;
}

int deref_double(int **pp) {
    return **pp;
}
```

```asm
; deref_read, rdi = p
deref_read:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-8], rdi
    mov     rax, [rbp-8]     ; rax = p (포인터 값 로드)
    mov     eax, [rax]       ; eax = *p (역참조: rax가 가리키는 곳에서 읽기)
    pop     rbp
    ret

; deref_write, rdi = p
deref_write:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-8], rdi
    mov     rax, [rbp-8]     ; rax = p
    mov     dword [rax], 5   ; *p = 5 (역참조: rax가 가리키는 곳에 쓰기)
    pop     rbp
    ret

; deref_double, rdi = pp
deref_double:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-8], rdi
    mov     rax, [rbp-8]     ; rax = pp (포인터의 포인터 값 로드)
    mov     rax, [rax]       ; rax = *pp (1차 역참조: int* 값을 얻음)
    mov     eax, [rax]       ; eax = **pp (2차 역참조: 실제 int 값을 얻음)
    pop     rbp
    ret
```

`deref_read`와 `deref_write`는 대괄호 위치만 반대다. `deref_double`은 `mov rax, [rax]`가 반복되는데, 첫 번째는 아직 포인터 값(`int *`)을 얻는 것이고 두 번째(`mov eax, [rax]`)에서 크기가 `eax`(32비트)로 바뀌는 순간 비로소 실제 `int` 데이터를 얻은 것이다. 레지스터 크기(`rax` vs `eax`)가 바뀌는 지점을 보면 "포인터를 얻었는지" "실제 값을 얻었는지" 구분할 수 있다.

## 흔한 실수
- `mov rax, [rax]`를 보고 무조건 무한 루프나 이상한 코드라고 의심하는 것 — 이중 포인터 역참조의 정상 패턴이다.
- 대괄호가 좌변에 있는 쓰기 연산(`mov [rax], edx`)을 읽기로 착각해 데이터 흐름을 반대로 추적하는 것.
- `eax`(32비트)와 `rax`(64비트) 크기 차이를 무시하고 "포인터를 읽은 것"과 "포인터가 가리키는 int를 읽은 것"을 구분하지 못하는 것.
- NULL 포인터 역참조(`p`가 0일 때 `[rax]` 접근)로 크래시가 나는 지점을 디버거에서 못 찾고 엉뚱한 곳을 보는 것 — 크래시 시점의 레지스터 값이 0인지 먼저 확인해야 한다.

## 막혔을 때 다음 체크
- 포인터 산술(`p+1`, `p[i]`)과 역참조를 같이 쓰는 경우가 헷갈리면 → REV-1063 포인터 산술이 어셈블리에서 보이는 패턴
- 구조체 멤버를 포인터로 따라가는 경우(`->`)는 → REV-1061 중첩 구조체 접근이 어셈블리에서 보이는 패턴
- 배열 인덱싱과 포인터 역참조의 관계가 궁금하면 → REV-0034 배열 접근이 어셈블리로 변하는 방식
- 포인터 값을 숫자로 착각해서 헷갈리는 문제라면 → REV-0380 포인터 값인데 숫자로 착각해서 헷갈릴 때

## 미니 예제
디버거에서 `deref_double` 실행 중 두 단계를 직접 관찰하는 예:
```
(gdb) p $rdi
$1 = (int **) 0x7fffffffe020
(gdb) x/gx 0x7fffffffe020
0x7fffffffe020: 0x0000555555558010   ; 이것이 *pp (int* 값)
(gdb) x/wx 0x555555558010
0x555555558010: 0x0000002a           ; 이것이 **pp (실제 int 값, 42)
```
어셈블리의 `mov rax,[rax]` → `mov eax,[rax]` 두 줄이 정확히 이 두 단계에 대응한다.

## 관련 글
- REV-1061 — 중첩 구조체 접근이 어셈블리에서 보이는 패턴
- REV-1063 — 포인터 산술이 어셈블리에서 보이는 패턴
- REV-0033 — 포인터와 역참조를 어셈블리에서 읽는 법
- REV-0380 — 포인터 값인데 숫자로 착각해서 헷갈릴 때
- REV-0034 — 배열 접근이 어셈블리로 변하는 방식

## 출처/검증
- x86-64 메모리 오퍼랜드 문법(`[base]`, `[base+offset]`)과 레지스터 재사용 규칙: Intel 64 and IA-32 Architectures Software Developer's Manual 기준.
- gcc/clang `-O0`에서 포인터 역참조가 "로드 후 재역참조" 형태의 연쇄 `mov`로 컴파일되는 패턴은 x86-64 리눅스/윈도우 환경에서 반복 확인되는 표준 패턴이다(2026-09-10 검증).
