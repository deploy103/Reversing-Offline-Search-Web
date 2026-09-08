---
id: REV-0034
title: "배열 접근이 어셈블리로 변하는 방식"
slug: "rev-0034-array-access-in-asm"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["배열 접근", "array indexing", "scale index base", "SIB", "rax+rsi*4", "배열 어셈블리"]
aliases: ["배열이 어셈블리에서 어떻게 보이나요", "인덱스 4를 왜 곱하나요", "rax rsi 4가 뭔가요", "배열 원소 크기 곱셈"]
symptom_keywords: ["rdi+rsi*4 가 왜 나오는지 모르겠음", "인덱스에 4를 곱하는 이유를 모르겠음", "배열 접근이 어셈블리에서 어떻게 나오는지 모르겠음", "2차원 배열 접근을 어떻게 읽는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
배열 인덱싱 `arr[i]`는 어셈블리에서 "배열의 시작 주소에, 인덱스에 원소 크기를 곱한 값을 더해서 주소를 만들고, 그 주소를 역참조"하는 형태(`mov eax, [rdi+rsi*4]`)로 컴파일되며, x64는 이 계산을 명령어 하나로 처리할 수 있는 전용 문법(SIB, Scale-Index-Base)을 제공한다.

## 언제 검색해야 하나
- `mov eax, [rdi+rsi*4]`, `movzx eax, byte [rax+rcx]`처럼 대괄호 안에 곱셈이 들어간 코드를 만났을 때
- 반복문 안에서 인덱스 변수가 4씩, 8씩 곱해지는 이유가 궁금할 때
- 2차원 배열(`arr[i][j]`)이나 배열의 배열이 어셈블리에서 어떻게 표현되는지 알고 싶을 때
- `lea rax, [rax*4]`처럼 곱셈만 있는 `lea`를 만났을 때

## 핵심 개념
C에서 `arr[i]`는 사실 포인터 연산의 문법 설탕(syntactic sugar)이다. `arr[i]`는 정의상 `*(arr + i)`와 완전히 같다. 다만 여기서 `arr + i`는 "바이트 i개를 더한다"가 아니라 **"arr의 원소 타입 크기 × i 바이트를 더한다"** 는 뜻이다. 이것이 배열 인덱싱과 어셈블리의 연결고리다.

예를 들어 `int arr[10]`이고 `arr[i]`에 접근한다면, `int`가 4바이트이므로 실제 주소 계산은 `주소 = arr시작주소 + i*4`가 된다. x64 어셈블리는 이 "베이스 주소 + 인덱스×배율" 계산을 명령어 하나의 오퍼랜드 안에서 표현할 수 있는 주소 지정 방식을 갖고 있다. 이를 **SIB(Scale-Index-Base)** 방식이라 부른다.

```asm
mov     eax, [rdi + rsi*4]
```
이 한 줄이 정확히 다음을 의미한다:
- `rdi` = Base(배열의 시작 주소)
- `rsi` = Index(인덱스 변수 i)
- `4` = Scale(원소 하나의 크기, 배율은 1/2/4/8만 가능)
- 전체 계산: `주소 = rdi + rsi*4`, 그 주소에서 4바이트를 읽어 `eax`에 저장

즉 `mov eax, [rdi+rsi*4]`는 정확히 C의 `eax = arr[i]` (arr가 `int*`, arr가 rdi, i가 rsi)와 대응한다.

**배율(Scale)은 원소 타입 크기에 따라 결정된다:**

| 원소 타입 | 크기 | 어셈블리 배율 | 예시 |
|---|---|---|---|
| `char` / `uint8_t` | 1바이트 | `*1` (보통 생략) | `movzx eax, byte [rdi+rsi]` |
| `short` / `uint16_t` | 2바이트 | `*2` | `movzx eax, word [rdi+rsi*2]` |
| `int` / `float` | 4바이트 | `*4` | `mov eax, [rdi+rsi*4]` |
| `long` / `double` / 포인터 | 8바이트 | `*8` | `mov rax, [rdi+rsi*8]` |

**x64의 SIB 배율은 하드웨어적으로 1, 2, 4, 8만 지원한다.** 만약 배열 원소 크기가 그 외의 값(예: 구조체 배열에서 원소가 12바이트, 24바이트 등)이라면, 컴파일러는 곱셈을 별도의 `imul` 명령어로 처리한 뒤 그 결과를 더한다.

```asm
imul    rax, rsi, 12     ; rax = i * 12  (원소 크기가 12바이트인 구조체 배열)
add     rax, rdi          ; rax = arr + i*12
mov     eax, [rax]        ; arr[i]의 첫 4바이트 필드 읽기
```

**배열 원소에 값을 쓰는 경우(`arr[i] = x`)** 도 방향만 반대다.
```asm
mov     [rdi+rsi*4], eax   ; arr[i] = x
```

**상수 인덱스**(`arr[3]`처럼 컴파일 시점에 인덱스가 고정된 경우)는 곱셈이 아예 사라지고 고정 오프셋으로 최적화되기도 한다.
```asm
mov     eax, [rdi+0xC]     ; arr[3] (3*4=12=0xC), 인덱스 레지스터 없이 바로 오프셋
```
이런 코드를 만나면 인덱스를 역산하려면 오프셋을 원소 크기로 나눠보면 된다(0xC = 12, 12/4 = 3).

**2차원 배열**(`int arr[ROWS][COLS]`)의 `arr[i][j]` 접근은 "1차원 배열 인덱싱을 두 번 겹친" 형태로 컴파일된다: 전체 주소는 `arr + (i*COLS + j)*4`로 계산된다(행 우선 저장, row-major order). 어셈블리에서는 대략 다음과 같이 나타난다.
```asm
imul    eax, edi, COLS    ; eax = i * COLS
add     eax, esi          ; eax = i*COLS + j
mov     eax, [rbx+rax*4]  ; arr[i][j] = *(arr + (i*COLS+j)*4)
```

## 화면/코드에서 보이는 징후
- `[reg1+reg2*N]` 형태(N=1,2,4,8)로 대괄호 안에 레지스터 두 개와 곱셈이 함께 나타난다.
- 반복문 안에서 인덱스 레지스터가 `add esi, 1`(i++)로 증가하고, 그 레지스터가 배열 접근의 인덱스로 재사용되는 패턴이 반복된다.
- `imul reg, reg, N` 뒤에 `add`가 이어지는 패턴(원소 크기가 1/2/4/8이 아닌 배열, 주로 구조체 배열).
- IDA/Ghidra 디컴파일 결과에서 `a1[i]`, `*(a1 + i)`, `*(int *)(a1 + i * 4)` 같은 표현이 등장한다 — 타입 정보가 좋으면 `[]`로, 나쁘면 포인터 산술+캐스팅으로 보여준다.

## 가장 먼저 할 것
`[reg+reg*N]` 형태를 보면 먼저 **N 값을 확인**한다. N이 1/2/4/8이면 그것이 원소 크기이고, 곧 원소 타입(`char`/`short`/`int·float`/`long·double·포인터`)을 짐작할 수 있는 가장 빠른 단서다.

## 단계별 절차

**1) SIB 표기에서 베이스/인덱스/배율 분리**
```asm
mov     eax, [rdi+rsi*4]
```
- Base = `rdi` (배열 시작 주소)
- Index = `rsi` (인덱스 변수)
- Scale = `4` (원소 크기 4바이트 → `int`/`float` 배열로 추정)

**2) 인덱스 레지스터가 반복문에서 어떻게 바뀌는지 추적**
```asm
xor     esi, esi          ; i = 0
loop_start:
cmp     esi, 10
jge     loop_end
mov     eax, [rdi+rsi*4]  ; arr[i]
; ... eax 사용 ...
inc     esi                ; i++
jmp     loop_start
loop_end:
```
이 구조는 전형적인 `for (i = 0; i < 10; i++) { ... arr[i] ... }` 패턴이다.

**3) 상수 인덱스는 오프셋 ÷ 원소크기로 역산**
```asm
mov     eax, [rdi+0x14]   ; 0x14 = 20, 20/4 = 5 → arr[5]
```

**4) 비표준 배율(구조체 배열)은 imul 뒤의 상수로 원소 크기 확인**
```asm
imul    rax, rsi, 0x18    ; 0x18 = 24바이트짜리 구조체 배열
add     rax, rdi
mov     eax, [rax+8]      ; arr[i].field_at_offset_8
```
이 경우 REV-0035(구조체 접근)의 필드 오프셋 해석과 함께 봐야 완전히 이해된다.

**5) 디버거로 인덱스와 실제 값 동시 확인**
```
(gdb) break *0x0000555555555160
(gdb) run
(gdb) print $rsi           # 현재 인덱스
(gdb) x/1dw $rdi+$rsi*4    # 해당 인덱스의 실제 int 값(10진수로)
```

## 명령어/단축키
```
(gdb) x/10dw arr_addr      # 배열 시작 주소부터 int 10개를 10진수로 덤프
(gdb) x/10xg arr_addr      # long/포인터 배열 10개를 헥스로 덤프
```
IDA: 배열로 추정되는 변수에서 `Y`(Set type)로 `int[10]` 같은 배열 타입을 지정하면 이후 `[rdi+rsi*4]` 패턴이 자동으로 `arr[i]` 형태로 디컴파일된다.

## 출력 해석
- `[base+index*4]`에서 4는 곧 "이 배열 원소는 4바이트"라는 강력한 힌트다. 8이면 8바이트, 1이면 1바이트(대개 문자열/바이트 배열).
- 배율이 없고 상수 오프셋만 있다면(`[rdi+0xC]`) 인덱스가 컴파일 시점에 이미 확정된 경우다. 오프셋을 원소 크기로 나누면 원래 인덱스를 복원할 수 있다.
- `imul`로 시작하는 주소 계산은 원소 크기가 1/2/4/8이 아닌, 대개 구조체 배열임을 시사한다.

## 흔한 실수
- SIB의 배율(N)을 무시하고 그냥 "레지스터 두 개를 더하는구나"로 넘기는 것 — N 값이 원소 타입 크기를 알려주는 핵심 단서인데 이를 놓치면 배열 원소 타입을 추정할 기회를 잃는다.
- 상수 인덱스로 최적화된 `[rdi+0x14]`를 보고 "이건 배열이 아니라 그냥 구조체 필드다"라고 단정하는 것 — 배열과 구조체 모두 고정 오프셋 접근으로 컴파일될 수 있어서, 반복문 존재 여부나 인접한 다른 오프셋들의 간격(등간격이면 배열, 불규칙하면 구조체일 가능성)까지 함께 봐야 한다.
- 2차원 배열 인덱싱에서 `i*COLS+j` 계산을 놓치고 `arr[i][j]`를 단순히 `arr[i+j]`로 착각하는 것.
- x86(32비트) 코드에서는 SIB에 `esi`, `edi` 대신 32비트 레지스터가 쓰이고 오프셋 계산 방식은 동일하지만 레지스터 폭만 다르다는 점을 놓치는 것.

## 막혔을 때 다음 체크
- 대괄호 자체의 기본 의미(역참조, `lea`와의 차이)가 헷갈리면 → REV-0033(포인터와 역참조를 어셈블리에서 읽는 법)으로 이동.
- 배열 원소가 구조체이고 그 안의 특정 필드에 접근하는 코드(`arr[i].field`)를 봐야 한다면 → REV-0035(구조체 접근이 어셈블리로 변하는 방식)로 이동.
- 배열이 스택/힙/전역 중 어디에 있는지 헷갈리면 → REV-0030(Code Data BSS Stack Heap 기초)으로 이동.

## 미니 예제
다음 C 함수로 배열 인덱싱의 전형적인 컴파일 패턴을 확인해보자.

```c
int sum_array(int *arr, int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += arr[i];
    }
    return total;
}
```

x64 SysV 어셈블리(개념 설명용):
```asm
sum_array:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-0x18], rdi   ; arr
    mov     [rbp-0x1C], esi   ; n
    mov     dword [rbp-4], 0  ; total = 0
    mov     dword [rbp-8], 0  ; i = 0
loop_cond:
    mov     eax, [rbp-8]      ; i
    cmp     eax, [rbp-0x1C]   ; i < n ?
    jge     loop_end
    mov     rax, [rbp-0x18]   ; arr
    mov     ecx, [rbp-8]      ; i
    mov     edx, [rax+rcx*4]  ; arr[i]   <- SIB 패턴, 배율 4 = int
    mov     eax, [rbp-4]      ; total
    add     eax, edx           ; total += arr[i]
    mov     [rbp-4], eax
    mov     eax, [rbp-8]
    add     eax, 1             ; i++
    mov     [rbp-8], eax
    jmp     loop_cond
loop_end:
    mov     eax, [rbp-4]       ; return total
    pop     rbp
    ret
```

IDA/Ghidra는 `[rax+rcx*4]` 패턴과 반복문 구조를 인식해서 다음과 같이 되돌려준다.

```c
int sum_array(int *arr, int n)
{
  int total;
  int i;

  total = 0;
  for (i = 0; i < n; i++)
    total += arr[i];
  return total;
}
```

핵심은 `mov edx, [rax+rcx*4]` 한 줄이 곧 `arr[i]`라는 것이다 — 베이스(`rax`=arr), 인덱스(`rcx`=i), 배율(4=sizeof(int))이 SIB 표기 안에 그대로 드러나 있다.

## 관련 글
- REV-0030 — Code Data BSS Stack Heap 기초
- REV-0033 — 포인터와 역참조를 어셈블리에서 읽는 법
- REV-0035 — 구조체 접근이 어셈블리로 변하는 방식

## 출처/검증
- x86/x64 ModRM/SIB 바이트와 Scale-Index-Base 주소 지정 방식: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.2, "ModRM and SIB Bytes" 섹션 기준 (2026-09-08 검증).
- C 배열 인덱싱과 포인터 산술의 동치성(`arr[i] == *(arr+i)`): ISO C 표준(C11) 6.5.2.1 Array subscripting 섹션 기준.
