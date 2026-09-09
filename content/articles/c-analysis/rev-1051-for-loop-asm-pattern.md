---
id: REV-1051
title: "for 루프가 어셈블리에서 보이는 패턴"
slug: "rev-1051-for-loop-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["for 루프 어셈블리", "for loop assembly pattern", "루프 카운터 어셈블리"]
aliases: ["for문 어셈블리에서 어떻게 보임", "for 루프 디스어셈블", "루프 어셈블리 패턴"]
symptom_keywords: ["어셈블리에서 루프를 못 알아봄", "이게 for문인지 while문인지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`for` 루프는 -O0 기준으로 "초기화 → 조건 검사로 바로 점프 → 본문 → 증감 → 조건 검사(맨 아래)"라는 정형화된 모양으로 컴파일되며, 조건 검사가 루프 맨 아래에 있고 그 위로 조건부 분기 하나만 존재한다는 게 핵심 특징이다.

## 언제 검색해야 하나
- 디스어셈블리에서 `cmp`와 `jl`/`jle`/`jg` 같은 조건부 분기가 뒤로(위쪽 주소로) 되돌아가는 코드를 발견해서 이게 루프인지 확인하고 싶을 때
- IDA/Ghidra 그래프 뷰에서 화살표가 위로 되돌아가는 블록을 보고 "이게 for인지 while인지" 궁금할 때
- 카운터 변수(`i` 같은 것)가 어디서 초기화되고 어디서 증가하는지 스택 오프셋만 보고는 못 찾겠을 때

## 핵심 개념

### 원본 C 코드
```c
int sum_for(int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += i;
    }
    return total;
}
```

### -O0 x86-64 어셈블리 (gcc/clang 공통 패턴, Intel 문법)
```asm
sum_for:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-0x14], edi   ; n (인자)
    mov     dword [rbp-4], 0   ; total = 0
    mov     dword [rbp-8], 0   ; i = 0          (for 초기화)
    jmp     .L_cond            ; 조건 검사로 먼저 점프 (본문을 아직 안 돎)
.L_body:
    mov     eax, [rbp-8]
    add     [rbp-4], eax       ; total += i
    add     dword [rbp-8], 1   ; i++            (for 증감)
.L_cond:
    mov     eax, [rbp-8]
    cmp     eax, [rbp-0x14]
    jl      .L_body            ; i < n 이면 본문으로 되돌아감
    mov     eax, [rbp-4]       ; return total
    leave
    ret
```

### 줄 단위 대응
- `mov dword [rbp-8], 0` — `for(int i = 0; ...)`의 초기화 부분. 루프 진입 전 딱 한 번만 실행된다.
- `jmp .L_cond` — for/while 루프의 결정적 특징. 본문을 실행하기 전에 조건 검사부터 먼저 하러 간다(0번 실행 가능성을 보장).
- `.L_body` 블록 — `{ total += i; }` 본문과 `i++` 증감이 **같은 블록**에 붙어 있다. `for(;;i++)`의 증감식은 본문 코드 바로 뒤, 조건 검사 바로 앞에 위치한다.
- `.L_cond` 블록 — `i < n` 조건 검사가 **루프 맨 아래**에 있고, 조건이 참이면 `jl .L_body`로 위로 되돌아간다. 조건 검사가 한 번만 있고 위로 되돌아가는 분기가 있다는 게 자연 루프(natural loop)의 표준 모양이다.

### 디컴파일러가 복원한 pseudocode
IDA/Ghidra는 위 `jmp` + 뒤쪽 조건부 백점프 패턴을 인식해서 아래처럼 되돌려준다.
```c
int sum_for(int n)
{
  int total = 0;
  int i;
  for (i = 0; i < n; i++) {
    total += i;
  }
  return total;
}
```
초기화/조건/증감이 한 줄에 다 모여 있는 `for` 형태로 아주 깔끔하게 복원되는 경우가 많다. 이는 어셈블리의 "초기화 → jmp 조건 → 본문 → 증감 → 조건"이라는 모양이 `for` 구문과 1:1로 대응되기 때문이다. 다만 이 모양은 REV-1052에서 다룰 `while` 루프와 **어셈블리 레벨에서 완전히 동일**하므로, 디컴파일러도 원래 소스가 `for`였는지 `while`이었는지는 구분하지 못하고 둘 다 비슷한 `for`/`while` pseudocode로 보여준다 — 구분은 오직 원본 소스에만 존재했던 정보다.

## 화면/코드에서 보이는 징후
- 루프 시작 직후 `jmp` 한 줄이 조건 검사 블록으로 건너뛴다.
- 본문 블록 끝에 카운터를 1(또는 임의의 step) 증가시키는 `add`/`inc` 명령이 있다.
- 조건 검사 블록(루프 맨 아래)에 `cmp` 하나와 조건부 분기(`jl`, `jle`, `jg` 등) 하나가 있고, 그 목적지가 본문 블록의 시작 주소(더 낮은 주소)다.
- IDA 그래프 뷰에서 조건 검사 블록에서 본문 블록으로 올라가는 화살표 하나, 진입부에서 조건 검사로 바로 내려가는 화살표 하나가 보인다.

## 가장 먼저 할 것
루프로 의심되는 블록을 찾으면 먼저 **되돌아가는 조건부 분기**(`jl .L_body`처럼 더 낮은 주소로 점프)를 찾는다. 그 분기 바로 위의 `cmp`가 종료 조건이고, 진입부의 `jmp`가 있는지 확인해서 있으면 for/while류, 없으면 REV-1053의 do-while류로 1차 분류한다.

## 단계별 절차
1. 되돌아가는 조건부 분기(`jl`/`jle`/`jg` 등, 목적지가 자기보다 낮은 주소)를 찾는다.
2. 그 분기 바로 위 `cmp` 명령의 두 오퍼랜드를 확인해 종료 조건 변수를 특정한다.
3. 루프 진입부에 `jmp .L_cond` 형태의 무조건 점프가 있는지 확인한다 — 있으면 본문 실행 전에 조건을 먼저 검사하는 for/while 패턴이다.
4. `jmp` 목적지 바로 위, 본문 블록의 마지막 명령들에서 카운터 증감(`add`, `inc`, `sub`)을 찾는다 — 이게 `for`의 세 번째 절(증감식)이다.
5. 본문 블록 시작 전, 진입부에서의 초기화 대입문을 찾아 카운터 초기값을 확인한다.

## 명령어/단축키
```
(gdb) disas sum_for
(gdb) break *0x<addr_of_.L_cond>
(gdb) x/3i $rip
```
IDA: 그래프 뷰(`Space`)로 전환하면 루프 백엣지(back edge)가 화살표로 바로 보인다. Ghidra: `Graph View` 창에서 동일하게 확인.

## 출력 해석
- `cmp eax, [rbp-0x14]` 다음 `jl .L_body`는 "i(eax) < n이면 본문으로"라는 뜻이고, 반대로 조건이 거짓이면 그냥 다음 명령(루프 뒤 코드)으로 흘러간다 — 별도의 `jmp .L_end`가 없어도 자연스럽게 루프를 빠져나간다.
- 조건 검사가 맨 아래 있다는 것은 이 루프가 "본문을 0번 실행할 수 있다"(n이 0 이하면 `jmp .L_cond`로 바로 가서 조건이 거짓이 되어 본문을 한 번도 안 돎)는 의미다. 이 성질로 do-while(REV-1053, 최소 1회 실행 보장)과 확실히 구분할 수 있다.

## 흔한 실수
- 진입부의 `jmp .L_cond`를 못 보고 넘어가서 "조건 검사가 왜 두 번 나오지?"라고 헷갈리는 것 — 사실 조건 검사는 한 곳(맨 아래)에만 있고, 진입부의 `jmp`는 단순히 그 검사로 건너뛰는 역할일 뿐이다.
- `-O2` 이상 최적화가 켜지면 컴파일러가 루프 언롤링(loop unrolling, 본문을 2~4배 복제해서 반복 횟수를 줄임)이나 SIMD 벡터화(`movdqa`, `paddd` 등 XMM 레지스터 사용)를 적용해 이 글의 정형화된 모양이 완전히 사라질 수 있다. 최적화가 의심되면 컴파일러 플래그를 낮춰 재컴파일해서 비교하거나, REV-0037(컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유)을 먼저 참고한다.
- 카운터 변수가 레지스터에만 있고 스택에 안 보이는 경우(레지스터 할당 최적화)를 보고 "카운터가 없다"고 오판하는 것 — `-O0`이 아니면 지역 변수가 스택 대신 레지스터에 계속 상주할 수 있다.

## 막혔을 때 다음 체크
- 이 모양이 `while` 루프와 뭐가 다른지 헷갈리면 → REV-1052(while 루프가 어셈블리에서 보이는 패턴) — 결론적으로 어셈블리 레벨에서는 구분이 안 된다는 점을 확인.
- 조건 검사가 맨 아래 없고 본문이 무조건 먼저 실행되는 모양을 봤다면 → REV-1053(do-while 루프가 어셈블리에서 보이는 패턴).
- 루프 안에 `break`/`continue`가 있어서 분기가 더 복잡해 보이면 → REV-1067, REV-1068.
- 조건부 분기 명령어 자체(`jl`, `jle` 등)의 정확한 의미가 헷갈리면 → REV-0069(JG JGE JL JLE: Signed 비교 분기).

## 미니 예제
배열 합산처럼 조금 더 실전적인 for 루프도 같은 뼈대를 따른다.
```c
int sum_array(int *arr, int len) {
    int total = 0;
    for (int i = 0; i < len; i++) {
        total += arr[i];
    }
    return total;
}
```
```asm
sum_array:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x20
    mov     [rbp-0x18], rdi   ; arr
    mov     [rbp-0x1c], esi   ; len
    mov     dword [rbp-4], 0   ; total = 0
    mov     dword [rbp-8], 0   ; i = 0
    jmp     .L_cond
.L_body:
    mov     eax, [rbp-8]
    cdqe
    mov     rdx, [rbp-0x18]
    mov     eax, [rdx+rax*4]   ; arr[i]
    add     [rbp-4], eax       ; total += arr[i]
    add     dword [rbp-8], 1   ; i++
.L_cond:
    mov     eax, [rbp-8]
    cmp     eax, [rbp-0x1c]
    jl      .L_body
    mov     eax, [rbp-4]
    leave
    ret
```
`jmp .L_cond` 진입부, `.L_body` 안에 배열 인덱싱(`[rdx+rax*4]`)과 증감이 같이 있고, `.L_cond`가 맨 아래에 있는 뼈대는 앞의 `sum_for`와 완전히 동일하다. 배열 인덱싱 자체의 상세한 주소 계산은 REV-1058을 참고한다.

## 관련 글
- REV-1052 — while 루프가 어셈블리에서 보이는 패턴
- REV-1053 — do-while 루프가 어셈블리에서 보이는 패턴
- REV-1067 — break문이 있는 for 루프가 어셈블리에서 보이는 패턴
- REV-1068 — continue문이 있는 for 루프가 어셈블리에서 보이는 패턴
- REV-1058 — 1차원 배열 인덱싱이 어셈블리에서 보이는 패턴
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0037 — 컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유

## 출처/검증
- gcc/clang `-O0` 기준 for 루프 코드 생성 패턴(초기화 → 조건으로 점프 → 본문 → 증감 → 맨 아래 조건 검사)은 x86-64 System V ABI 환경에서 실제 gcc/clang 출력에서 반복적으로 확인되는 표준 패턴이다.
- IDA/Ghidra의 자연 루프(natural loop) 인식 및 pseudocode 복원 방식: Hex-Rays 및 Ghidra 공식 문서의 제어 흐름 분석(control flow analysis) 설명 기준 (2026-09-10 검증).
