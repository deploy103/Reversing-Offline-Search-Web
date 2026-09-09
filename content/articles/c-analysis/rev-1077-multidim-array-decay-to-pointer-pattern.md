---
id: REV-1077
title: "다차원 배열을 함수로 넘길 때 포인터로 decay되는 패턴"
slug: "rev-1077-multidim-array-decay-to-pointer-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["다차원 배열 decay", "multidim array pointer decay", "int arr 10 함수 매개변수", "행 포인터 stride 계산"]
aliases: ["2차원 배열 함수 인자 어셈블리", "배열이 포인터로 변하는 이유", "다차원 배열 stride 어셈블리"]
symptom_keywords: ["행렬 함수 인자가 포인터 하나뿐임", "arr[3][10]인데 함수 인자는 int(*)[10]", "다차원 배열 넘겼는데 크기 정보가 하나만 남음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`int mat[3][10]`처럼 선언된 다차원 배열을 함수 매개변수로 넘기면 가장 바깥쪽 차원(`3`)의 크기 정보는 사라지고 `int (*)[10]`(10개짜리 배열을 가리키는 포인터) 하나로 decay되며, 어셈블리에서는 이것이 "함수는 포인터 레지스터 하나만 받고, 행(row) 하나를 건너뛸 때마다 안쪽 차원 크기(`10 * sizeof(int)` = 40바이트)를 고정 상수로 곱해 더하는" 형태로 나타난다.

## 언제 검색해야 하나
- `void f(int mat[3][10])`처럼 선언한 함수인데 어셈블리를 보면 인자로 받는 게 그냥 포인터 레지스터 하나뿐이라 "3이라는 정보는 어디 갔지?" 싶을 때
- 행렬의 특정 행 주소를 계산하는 코드에서 `add rax, 40`, `imul rax, rdx, 40` 처럼 고정된 배수(40, 80 등)가 반복해서 나올 때
- 함수 시그니처만 보고 "이 배열이 몇 행짜리인지" 알아내려다 실패하고, 대신 호출하는 쪽 코드에서 몇 번 반복하는지를 봐야 하는 상황일 때
- 2차원 배열 인덱싱 `mat[i][j]`가 함수 안/밖에서 서로 다른 방식(곱셈 유무)으로 계산되는 것을 비교해야 할 때

## 핵심 개념
C에서 배열이 함수 매개변수로 선언되면 항상 포인터로 decay(퇴화)된다. 1차원 배열 `int arr[10]`은 `int *arr`로, 다차원 배열 `int mat[3][10]`은 `int (*mat)[10]`(10개 int로 된 배열 하나를 가리키는 포인터)로 바뀐다. 이때 사라지는 것은 가장 바깥쪽 차원(행의 개수, `3`)뿐이고, 안쪽 차원(열의 개수, `10`)은 포인터 타입 자체(`int (*)[10]`)에 남아 있어서 컴파일러가 "한 행을 건너뛸 때 몇 바이트를 이동해야 하는지"(stride)를 계산하는 데 계속 쓰인다.

```c
void fill_row(int arr[10], int row) {   /* int arr[10]은 실제로 int *arr로 decay */
    for (int i = 0; i < 10; i++) {
        arr[i] = row;
    }
}

void use_matrix(int mat[3][10]) {       /* 실제 매개변수 타입은 int (*mat)[10] */
    fill_row(mat[1], 7);                /* mat[1] = 두 번째 행의 시작 주소 */
}
```

x86-64 SysV, `-O0`, Intel 문법:

```asm
use_matrix:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 16
    mov     [rbp-8], rdi        ; mat 저장 -- 실제로는 int(*)[10] 포인터 하나, [3][10] 중 3은 이미 사라짐
    mov     rax, [rbp-8]        ; rax = mat
    add     rax, 40             ; rax = mat + 40바이트 = &mat[1][0]  (1행 * 10칸 * 4바이트 = 40, 안쪽 차원 10이 stride로 남아있음)
    mov     rdi, rax            ; fill_row의 1번째 인자: &mat[1][0]
    mov     esi, 7              ; fill_row의 2번째 인자: row = 7
    call    fill_row
    leave
    ret

fill_row:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-24], rdi       ; arr 저장 (int *arr로 decay됨, 안쪽 차원 정보도 없음)
    mov     [rbp-28], esi       ; row 저장
    mov     DWORD [rbp-4], 0    ; i = 0
.L_loop:
    cmp     DWORD [rbp-4], 9
    jg      .L_end
    mov     eax, [rbp-4]        ; eax = i
    cdqe                        ; eax를 rax로 부호 확장
    lea     rdx, [rax*4]        ; rdx = i * 4바이트 (int 하나 크기)
    mov     rax, [rbp-24]       ; rax = arr
    add     rax, rdx            ; rax = &arr[i]
    mov     ecx, [rbp-28]       ; ecx = row
    mov     [rax], ecx          ; arr[i] = row
    add     DWORD [rbp-4], 1
    jmp     .L_loop
.L_end:
    pop     rbp
    ret
```

`use_matrix`에서 `mat[1]`을 계산할 때 `add rax, 40`이라는 고정 상수가 쓰인 것을 주목하자. 이 `40`은 `10(안쪽 차원, 열 개수) * 4바이트(int 크기)`로, 컴파일러가 `mat`의 타입이 `int (*)[10]`이라는 걸 알고 있기 때문에 나올 수 있는 값이다. 반면 `fill_row` 안에서는 매개변수가 이미 단순 `int *`로 decay되어 있어서 `arr[i]`를 계산할 때는 그냥 `i * 4`만 곱하며, 더 이상 "몇 번째 행인지" 같은 개념이 없다.

## 화면/코드에서 보이는 징후
- 함수 매개변수로 배열을 받는 함수인데 실제로는 포인터 레지스터(`rdi`, `rcx` 등) 하나만 전달됨
- 행렬 관련 코드에서 `imul`이나 `add`에 `10*4=40`, `10*8=80` 같은, 선언된 열 개수와 원소 크기를 곱한 고정 상수가 반복됨
- `sizeof(mat)`을 함수 안에서 호출했다고 가정할 코드가 실제로는 배열 전체 크기가 아니라 포인터 크기(8바이트)로 계산됨(그래서 `sizeof`를 함수 매개변수 배열에 쓰면 안 된다는 규칙의 어셈블리적 증거)

## 가장 먼저 할 것
함수가 다차원 배열을 매개변수로 받는 것처럼 선언되어 있다면, 실제로 레지스터/스택에 전달되는 것이 포인터 하나뿐인지부터 확인한다. 그 다음 함수 안에서 인덱싱 시 곱해지는 고정 상수를 찾아 "안쪽 차원 크기 × 원소 크기"로 역산하면 원래 선언의 안쪽 차원을 알 수 있다.

## 단계별 절차
1. 함수 프롤로그에서 배열로 선언된 매개변수가 실제로 포인터 레지스터 하나로만 전달되는지 확인한다.
2. 그 포인터에 인덱싱이 일어날 때 곱해지는 상수를 찾는다(`imul`, 또는 `lea reg, [reg*N]` 형태).
3. 그 상수를 원소 크기(대개 4바이트 `int`, 8바이트 `double`/포인터 등)로 나누어 안쪽 차원의 크기를 역산한다.
4. 바깥쪽 차원(행 개수)은 함수 시그니처만 봐서는 알 수 없으므로, 호출하는 쪽 코드에서 반복 횟수나 배열 전체 크기 상수를 찾아 확인한다.

## 명령어/단축키
- IDA: 함수 인자 타입을 `int (*)[10]`처럼 직접 지정(Edit Function 또는 로컬 타입 편집)하면 pseudocode가 `mat[i][j]` 형태로 자연스럽게 복원됨
- Ghidra: Function Signature 편집에서 매개변수 타입을 배열 포인터로 지정
- GDB: `ptype mat`으로 실제 컴파일된 타입 확인, `p sizeof(mat)`으로 배열 전체가 아니라 포인터 크기(8)가 나오는 것을 직접 확인
- x64dbg: 레지스터 창에서 포인터 값 하나만 전달되는지 직접 확인, 메모리 덤프에서 40바이트 간격으로 값이 반복되는지 확인

## 출력 해석
`add rax, 40`이 반복적으로 나타나고 그 값이 항상 `40`으로 고정되어 있다면, 이는 배열의 안쪽 차원이 `10`(10 * 4바이트 = 40)으로 컴파일 시점에 이미 고정되어 있다는 뜻이다. 만약 이 값이 실행 중 레지스터 곱셈으로 매번 다시 계산된다면(`imul rax, rcx, N`처럼 변수 곱셈이라면), 안쪽 차원 크기가 컴파일 시점 상수가 아니라 가변 길이 배열(VLA)일 가능성도 검토해야 한다.

## 흔한 실수
- 함수 매개변수로 선언된 `int mat[3][10]`을 보고 실제로 3행 전체 정보가 함수 안에 전달된다고 생각하는 것 — 실제로는 행 개수(3)는 완전히 사라진다.
- 함수 안에서 `sizeof(mat)`을 호출해 전체 배열 크기를 구하려는 것 — 매개변수화된 배열은 포인터이므로 `sizeof`는 8(포인터 크기)만 반환한다.
- 안쪽 차원 크기를 곱하는 상수(`40`)를 원소 개수(`10`)로 착각하는 것 — 반드시 원소 크기로 나누어야 진짜 차원 크기가 나온다.
- 1차원 배열 decay(`int arr[10]` → `int *arr`)와 다차원 배열 decay(`int mat[3][10]` → `int (*mat)[10]`)를 같은 것으로 취급해 안쪽 차원 정보까지 사라진다고 착각하는 것 — 안쪽 차원은 포인터 타입에 남아 유지된다.

## 막혔을 때 다음 체크
- 함수 밖(호출하는 쪽)에서 2차원 배열을 직접 인덱싱하는 코드가 어떻게 다른지 비교하려면 → REV-1059 2차원 배열 인덱싱이 어셈블리에서 보이는 패턴(예정)
- 이 포인터에 대한 포인터 산술(더하기/빼기) 전반이 궁금하면 → REV-1063 포인터 산술이 어셈블리에서 보이는 패턴(예정)
- 배경 지식으로 다차원 배열 자체가 메모리에 어떻게 배치되는지 먼저 보고 싶다면 → REV-0350 다차원 배열이 어셈블리로 어떻게 변하는지

## 미니 예제
3x3 단위 행렬의 대각선 원소만 채우는 함수로, 안쪽 차원 상수가 곱해지는 모습을 더 명확히 보여준다.

```c
void set_diagonal(int mat[3][3], int value) {   /* 실제 매개변수 타입: int (*mat)[3] */
    for (int i = 0; i < 3; i++) {
        mat[i][i] = value;
    }
}
```

```asm
set_diagonal:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-24], rdi        ; mat 저장 (int(*)[3] 하나의 포인터)
    mov     [rbp-28], esi        ; value 저장
    mov     DWORD [rbp-4], 0     ; i = 0
.L_loop:
    cmp     DWORD [rbp-4], 2
    jg      .L_end
    mov     eax, [rbp-4]         ; eax = i
    cdqe
    imul    rdx, rax, 12         ; rdx = i * 12  (안쪽 차원 3 * 4바이트 = 12, 행 오프셋)
    mov     rax, [rbp-24]        ; rax = mat
    add     rax, rdx             ; rax = &mat[i][0]
    mov     edx, [rbp-4]         ; edx = i (열 인덱스로 재사용)
    movsxd  rdx, edx
    lea     rcx, [rdx*4]         ; rcx = i * 4  (열 오프셋)
    add     rax, rcx             ; rax = &mat[i][i]
    mov     ecx, [rbp-28]        ; ecx = value
    mov     [rax], ecx           ; mat[i][i] = value
    add     DWORD [rbp-4], 1
    jmp     .L_loop
.L_end:
    pop     rbp
    ret
```

`imul rdx, rax, 12`에서 `12`는 `3(안쪽 차원, 열 개수) * 4바이트`이고, 이 상수 하나만으로도 원래 선언이 `int mat[N][3]` 형태(안쪽 차원이 3)였다는 것을 바깥쪽 N값 없이도 알아낼 수 있다.

## 관련 글
- REV-0350 — 다차원 배열이 어셈블리로 어떻게 변하는지
- REV-1059 — 2차원 배열 인덱싱이 어셈블리에서 보이는 패턴
- REV-1063 — 포인터 산술이 어셈블리에서 보이는 패턴

## 출처/검증
- 배열이 함수 매개변수로 선언될 때 포인터로 decay되는 규칙과, 다차원 배열은 가장 바깥쪽 차원만 사라진다는 규칙: C 표준(ISO/IEC 9899) 배열/포인터 변환 섹션 기준.
- 안쪽 차원 크기가 stride 상수로 컴파일 시점에 고정되어 `add`/`imul` 명령으로 나타나는 패턴: 실제 gcc/clang `-O0` x86-64 출력 비교로 반복 확인 (2026-09-10 검증).
