---
id: REV-1058
title: "1차원 배열 인덱싱이 어셈블리에서 보이는 패턴"
slug: "rev-1058-1d-array-indexing-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["1차원 배열 인덱싱 어셈블리", "array indexing asm pattern", "SIB 배열 접근 C 코드"]
aliases: ["arr[idx] 어셈블리에서 어떻게 보임", "배열 인덱싱 C ASM 대조", "1차원 배열 디스어셈블"]
symptom_keywords: ["arr[idx]가 어셈블리에서 어떻게 변하는지 모르겠음", "cdqe가 왜 배열 인덱싱에 붙는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`arr[idx]`는 어셈블리에서 "인덱스를 64비트로 부호 확장 → 원소 크기만큼 스케일(SIB의 `*4`, `*8` 등) → 베이스 포인터에 더해서 역참조"하는 짧은 명령어 시퀀스로 컴파일되며, `int` 인덱스를 쓰는 순간 거의 항상 `cdqe`/`movsxd` 같은 부호 확장 명령이 먼저 끼어든다는 게 초보자가 자주 놓치는 부분이다.

## 언제 검색해야 하나
- `arr[idx]` 한 줄짜리 C 코드가 어셈블리에서 왜 `cdqe` 같은 낯선 명령어를 포함해 3~4줄로 늘어나는지 궁금할 때
- `mov eax, [rdx+rax*4]`처럼 대괄호 안에 곱셈이 있는 코드를 소스 레벨 배열 접근과 정확히 대응시키고 싶을 때
- 함수 인자로 받은 포인터(`int *arr`)와 인덱스(`int idx`)가 각각 어느 레지스터/스택 위치에 저장되고 어떻게 조합되는지 처음부터 끝까지 따라가고 싶을 때

## 핵심 개념

### 원본 C 코드
```c
int get_at(int *arr, int idx) {
    return arr[idx];
}
```

### -O0 x86-64 어셈블리 (SysV, Intel 문법)
```asm
get_at:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-8], rdi     ; arr  (rdi: 첫 번째 인자)
    mov     [rbp-0xc], esi    ; idx  (esi: 두 번째 인자)
    mov     eax, [rbp-0xc]    ; eax = idx
    cdqe                       ; rax = (int64_t)eax  (idx를 64비트로 부호 확장)
    mov     rdx, [rbp-8]       ; rdx = arr
    mov     eax, [rdx+rax*4]   ; eax = *(arr + idx*4) = arr[idx]
    leave
    ret
```

### 줄 단위 대응
- `mov [rbp-8], rdi` / `mov [rbp-0xc], esi` — 함수 인자 두 개를 각각의 지역 스택 슬롯으로 옮기는, `-O0`에서 거의 항상 보이는 인자 저장 코드다.
- `mov eax, [rbp-0xc]` / `cdqe` — `idx`(32비트 `int`)를 포인터 연산에 쓰기 위해 64비트로 부호 확장한다. `cdqe`는 `eax`의 값을 부호 확장해서 `rax`에 넣는 전용 명령어다(REV-0041). **인덱스가 `int`(부호 있는 32비트)이고 배열 접근에 쓰인다면 거의 항상 이 부호 확장 명령이 먼저 나온다** — 이걸 놓치면 왜 `mov`가 한 줄 더 끼어드는지 헷갈릴 수 있다. 인덱스가 `size_t`나 `unsigned long`처럼 이미 64비트라면 이 확장 명령 자체가 필요 없다.
- `mov rdx, [rbp-8]` — 배열 베이스 포인터(`arr`)를 다시 레지스터로 불러온다.
- `mov eax, [rdx+rax*4]` — SIB 주소 지정 방식으로 `arr + idx*4`를 계산해서 그 주소를 역참조한다. `4`는 `sizeof(int)`이며, 이 스케일 값이 곧 배열 원소 타입의 크기를 알려주는 가장 직접적인 단서다(REV-0034에서 원소 타입별 스케일 표를 참고).

### 디컴파일러가 복원한 pseudocode
```c
int get_at(int *arr, int idx)
{
  return arr[idx];
}
```
`cdqe`, SIB 주소 계산 같은 저수준 세부사항은 디컴파일러가 완전히 흡수해서 원본과 거의 동일한 `arr[idx]` 표현으로 되돌려준다. 배열 인덱싱은 if/for 같은 제어 흐름 구문과 달리 **소스 레벨 문법과 어셈블리 패턴이 거의 1:1로 대응**되는 편이라, 디컴파일러 결과의 신뢰도가 높은 대표적인 케이스다. 단, IDA/Ghidra가 `arr`의 타입을 `int *`로 정확히 추론하지 못하면 `*(int *)(arr + idx * 4)`처럼 포인터 캐스팅 형태로 더 원시적으로 보여줄 수 있다.

## 화면/코드에서 보이는 징후
- `cdqe` 또는 `movsxd reg64, reg32`가 배열 접근 코드 직전에 나타난다(인덱스가 부호 있는 32비트일 때).
- `[reg+reg*N]`(N=1,2,4,8) 형태로 대괄호 안에 곱셈이 들어간 SIB 주소 지정.
- 반복문 안에서 인덱스 레지스터가 매번 `add`/`inc`로 증가하고, 그 값이 계속 같은 배열 접근에 재사용된다.
- 원소 크기가 1/2/4/8이 아니면(구조체 배열 등) `imul`로 대체된다 — 이 경우는 REV-1064(구조체 배열 순회)와 함께 봐야 한다.

## 가장 먼저 할 것
`[reg+reg*N]` 형태를 찾으면 N 값부터 확인한다. N이 원소 타입 크기(1/2/4/8)와 일치하는지 보고, 그 앞에 `cdqe`/`movsxd`가 있는지 확인해서 인덱스 변수의 원래 타입이 부호 있는 32비트였는지 짐작한다.

## 단계별 절차
1. 배열 접근으로 의심되는 `[reg+reg*N]` 명령을 찾는다.
2. N 값으로 원소 크기(따라서 원소 타입)를 추정한다.
3. 인덱스 레지스터가 어디서 왔는지(함수 인자, 반복문 카운터 등) 역추적한다.
4. 베이스 레지스터가 어디서 왔는지(함수 인자로 받은 포인터, 지역 배열의 시작 주소 등) 확인한다.
5. `cdqe`/`movsxd`가 있다면 원본 인덱스 변수가 32비트 부호 있는 정수였다고 판단한다.

## 명령어/단축키
```
(gdb) disas get_at
(gdb) print $rdi          ; arr 포인터 값
(gdb) print $esi           ; idx 값
(gdb) x/1dw $rdi+$rsi*4   ; arr[idx]를 직접 메모리에서 읽어 대조
```
IDA: 배열로 쓰이는 포인터 변수에서 `Y`(Set item type)로 배열 타입을 지정하면 이후 `[rdx+rax*4]` 패턴이 자동으로 `arr[idx]` 형태로 디컴파일된다.

## 출력 해석
- `[reg+reg*4]`의 4는 `int`/`float` 배열임을 강하게 시사한다. 1이면 `char`/`byte` 배열, 8이면 `long`/`double`/포인터 배열이다.
- `cdqe`가 없다면 인덱스가 이미 64비트였거나(`size_t`, `long`), 혹은 `unsigned int`라서 부호 확장이 아니라 단순 상위 32비트 클리어(`mov eax, eax`처럼 보이거나 그냥 32비트 레지스터를 그대로 다음 명령의 하위 32비트로 재사용)로 처리된 경우다.

## 흔한 실수
- `cdqe` 한 줄을 실제 계산과 무관한 노이즈로 여기고 건너뛰는 것 — 이는 인덱스 타입의 부호 여부를 알려주는 중요한 단서다.
- SIB의 스케일 값(N)을 무시하고 "그냥 곱셈이네" 하고 넘어가는 것 — N이 곧 배열 원소 타입의 크기다.
- 상수 인덱스(`arr[3]`처럼 컴파일 시점에 고정된 인덱스)는 곱셈 없이 바로 고정 오프셋(`[rdx+0xc]`)으로 최적화된다는 것을 놓치고 이걸 구조체 필드 접근(REV-1060)으로 오인하는 것 — 반복문 안에서 인덱스가 변하는지, 상수인지로 구분해야 한다.
- `-O2` 이상에서는 배열 접근이 벡터화(SIMD, `movdqu` 등으로 여러 원소를 한 번에 로드)되거나, 인덱스 범위가 컴파일 시점에 확정되면 배열 접근 자체가 상수로 치환(constant folding)될 수 있다는 점을 놓치는 것 — 이 경우 `[reg+reg*4]` 패턴이 전혀 안 보일 수 있다.

## 막혔을 때 다음 체크
- 배열 원소 타입별 스케일 표, 구조체 배열의 비표준 스케일 처리 등 더 깊은 내용은 → REV-0034(배열 접근이 어셈블리로 변하는 방식).
- 2차원 배열로 확장된 경우가 궁금하면 → REV-1059(2차원 배열 인덱싱이 어셈블리에서 보이는 패턴).
- 배열 원소가 구조체인 경우가 궁금하면 → REV-1064(구조체 배열 순회가 어셈블리에서 보이는 패턴).
- 부호 확장 명령어(`cdqe`, `movsx`) 자체의 세부 동작이 헷갈리면 → REV-0041.
- 포인터와 역참조의 기본 원리가 헷갈리면 → REV-1062(포인터 역참조가 어셈블리에서 보이는 패턴), REV-0033.

## 미니 예제
배열에 값을 쓰는 방향(대입)도 같은 SIB 패턴을 그대로 쓰되 방향만 반대다.
```c
void set_at(int *arr, int idx, int value) {
    arr[idx] = value;
}
```
```asm
set_at:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x18
    mov     [rbp-8], rdi      ; arr
    mov     [rbp-0xc], esi     ; idx
    mov     [rbp-0x10], edx    ; value
    mov     eax, [rbp-0xc]     ; idx
    cdqe
    mov     rdx, [rbp-8]       ; arr
    mov     ecx, [rbp-0x10]    ; value
    mov     [rdx+rax*4], ecx    ; arr[idx] = value
    leave
    ret
```
읽기(`get_at`)와 쓰기(`set_at`)는 `mov`의 오퍼랜드 방향만 반대이고, 주소 계산 부분(`cdqe`, `[rdx+rax*4]`)은 완전히 동일하다.

## 관련 글
- REV-0034 — 배열 접근이 어셈블리로 변하는 방식
- REV-1059 — 2차원 배열 인덱싱이 어셈블리에서 보이는 패턴
- REV-1062 — 포인터 역참조가 어셈블리에서 보이는 패턴
- REV-1064 — 구조체 배열 순회가 어셈블리에서 보이는 패턴
- REV-0042 — LEA: 주소 계산인데 왜 산술 연산처럼 보이는가

## 출처/검증
- x86-64 SIB(Scale-Index-Base) 주소 지정 방식과 스케일 제약(1/2/4/8): Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.2 기준.
- C 배열 인덱싱과 포인터 산술의 동치성(`arr[idx] == *(arr+idx)`) 및 부호 확장 규칙: ISO C 표준(C11) 6.5.2.1, 6.3.1.3 기준 (2026-09-10 검증).
