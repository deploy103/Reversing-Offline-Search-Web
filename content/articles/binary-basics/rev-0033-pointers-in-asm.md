---
id: REV-0033
title: "포인터와 역참조를 어셈블리에서 읽는 법"
slug: "rev-0033-pointers-in-asm"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["포인터", "pointer", "역참조", "dereference", "lea", "mov rax rax", "이중 포인터"]
aliases: ["포인터가 어셈블리에서 어떻게 보이나요", "역참조가 뭔가요", "lea랑 mov 차이", "대괄호가 뭔가요"]
symptom_keywords: ["대괄호 안 레지스터가 뭔지 모르겠음", "lea가 왜 나오는지 모르겠음", "mov rax rax 두번 나오는 이유를 모르겠음", "포인터의 포인터를 어떻게 읽는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
어셈블리에서 대괄호 `[ ]`는 "이 안의 값을 주소로 취급해서 메모리에서 읽어와라"는 뜻이며, 이것이 바로 C 언어의 포인터 **역참조(dereference, `*p`)** 에 해당한다 — 반면 `lea`는 메모리를 읽지 않고 **주소값 자체**를 계산해서 레지스터에 담는다.

## 언제 검색해야 하나
- 어셈블리에서 `mov rax, [rdi]`, `mov eax, [rax]`처럼 대괄호가 붙은 피연산자를 만났는데 이게 정확히 뭘 하는 건지 모를 때
- `lea rax, [rbp-0x10]`처럼 `lea`가 대괄호를 쓰는데 `mov`와 뭐가 다른지 헷갈릴 때
- C 코드의 `*p`, `p->field`, `**pp` 같은 포인터 표현이 어셈블리로 어떻게 컴파일되는지 알고 싶을 때
- IDA 디컴파일 결과에 `*(int *)(a1 + 8)`처럼 낯선 캐스팅과 역참조가 섞인 표현이 나올 때

## 핵심 개념
포인터는 그냥 "메모리 주소를 담고 있는 정수"다. C에서 `int *p`는 "p라는 변수 안에는 int가 있는 곳의 주소가 들어있다"는 뜻이고, `*p`(역참조)는 "p가 가리키는 주소로 가서 그 안의 int 값을 읽어와라"는 뜻이다.

어셈블리에서 이 두 단계는 명확히 구분된다.

**1) 주소값 자체를 다루는 것 — 그냥 레지스터/즉시값**
```asm
mov     rax, rdi        ; rax에 rdi의 "값"을 그대로 복사 (rdi가 포인터라면 주소값 자체를 복사)
```

**2) 주소가 가리키는 메모리의 내용을 읽는 것 — 대괄호(역참조)**
```asm
mov     eax, [rdi]      ; rdi가 가리키는 주소에서 4바이트를 읽어 eax에 저장 (= *p, p의 타입이 int일 때)
mov     rax, [rdi]      ; rdi가 가리키는 주소에서 8바이트를 읽음 (= *p, p의 타입이 8바이트 포인터/long일 때)
```

대괄호 안에 있는 것은 "주소를 계산하는 수식"이고, 그 수식으로 계산된 주소에 있는 **메모리의 실제 내용**을 가져오는 것이 `mov reg, [주소식]`이다. 이 동작이 바로 포인터 역참조와 정확히 대응한다.

**`lea`(Load Effective Address)는 다르다.** `lea`는 대괄호 수식을 계산만 하고, **메모리를 읽지 않고** 그 계산 결과(주소값)를 그대로 레지스터에 넣는다.

```asm
lea     rax, [rbp-0x10]   ; rax = rbp - 0x10  (메모리 읽기 없음, 그냥 주소 계산)
```
이는 C에서 `int *p = &local_var;`처럼 **주소를 얻는 연산자(`&`)** 와 대응한다. `lea`와 `mov [ ]`를 구분하는 것이 포인터 코드를 읽는 첫걸음이다: **`lea`는 `&`(주소 얻기), `mov reg, [ ]`는 `*`(역참조)**.

**포인터의 포인터(이중 포인터, `int **pp`)** 도 대괄호를 두 번 씀으로써 그대로 표현된다.
```asm
mov     rax, [rdi]       ; rax = *pp  (첫 번째 역참조: pp가 가리키는 곳에서 "포인터 값"을 읽음)
mov     eax, [rax]       ; eax = **pp (두 번째 역참조: 방금 읽은 포인터가 가리키는 곳에서 int를 읽음)
```
이 "레지스터로 값을 읽어온 다음, 그 레지스터를 다시 대괄호에 넣어 또 읽는" 두 줄 패턴이 이중 포인터의 전형적인 시그니처다.

**값을 메모리에 쓰는 것(포인터를 통한 대입, `*p = x`)** 도 마찬가지로 대괄호를 쓰지만 방향이 반대다.
```asm
mov     [rdi], eax        ; *p = x  (rdi가 가리키는 주소에 eax 값을 씀)
```
`mov`는 항상 "오른쪽(source)에서 왼쪽(destination)으로" 값이 이동한다는 원칙을 기억하면, 대괄호가 왼쪽에 있는지 오른쪽에 있는지로 "쓰기"인지 "읽기"인지를 바로 구분할 수 있다.

**레지스터 크기와 역참조 크기는 항상 같이 간다.** `mov eax, [rdi]`는 4바이트를 읽고(`int`, `float`), `mov rax, [rdi]`는 8바이트를 읽는다(`long`, 포인터 자체). `movzx`/`movsx`는 1~2바이트를 읽어서 부호 없는/부호 있는 방식으로 32/64비트로 확장한다 — `char`, `short` 타입 역참조에서 자주 보인다.

IDA/Ghidra 디컴파일러는 이 패턴들을 인식해서 `*p`, `p->field`, `**pp` 같은 C 스타일 표현으로 되돌려 보여주지만, 타입 정보가 불완전하면 `*(int *)(a1 + 8)`처럼 원시적인 캐스팅+역참조 형태로 표시하기도 한다. 이때도 원리는 동일하다: 괄호 안 수식이 주소, 바깥의 역참조가 그 주소의 내용을 읽는 것.

## 화면/코드에서 보이는 징후
- `mov reg, [reg]`, `mov reg, [reg+N]`처럼 대괄호 안에 레지스터(+오프셋)가 들어간 형태가 반복해서 나타난다.
- `lea reg, [reg+N]`처럼 `lea`가 나오는데 그 결과 레지스터가 곧바로 다른 `mov [reg], ...`의 대상 주소로 재사용된다.
- IDA 디컴파일 결과에 `*a1`, `a1[0]`, `*(int *)(a1 + 8)`, `(*pp)` 같은 표현이 등장한다.
- 두 번 연속으로 `mov rax, [rax]`가 나오는 패턴(이중 포인터 또는 연결 리스트/트리의 `next`/`child` 포인터 따라가기).

## 가장 먼저 할 것
대괄호가 있는 피연산자를 만나면 먼저 **읽기(mov dst, [src])인지 쓰기(mov [dst], src)인지**부터 구분한다. 그 다음 대괄호 안의 레지스터가 어디서 왔는지(REV-0032에서 다룬 함수 인자, 또는 `lea`로 계산된 지역 변수 주소, 또는 이전 역참조 결과) 거슬러 올라가면 이 포인터가 무엇을 가리키는지 짐작할 수 있다.

## 단계별 절차

**1) `lea`와 `mov [ ]`를 구분해서 표시**
```asm
lea     rax, [rbp-0x10]   ; rax = &local   (주소 계산만, 읽기 없음)
mov     rdi, rax           ; 그 주소를 다음 함수 호출의 인자로 전달 준비
```
이 패턴은 C의 `func(&local)`에 해당한다.

**2) 대괄호 안 레지스터의 출처 추적**

```asm
mov     rax, [rdi]        ; rdi = 함수의 1번째 인자(포인터), 이걸 역참조
```
REV-0032에서 배운 대로 `rdi`는 SysV x64에서 1번째 인자이므로, 이 함수는 포인터 하나를 받아서 그 값을 역참조하는 함수라고 짐작할 수 있다.

**3) 역참조 크기로 원래 타입 추정**
```asm
mov     al, [rdi]         ; 1바이트 읽기 → char 또는 uint8_t 역참조로 추정
mov     ax, [rdi]         ; 2바이트 읽기 → short 역참조로 추정
mov     eax, [rdi]        ; 4바이트 읽기 → int/float 역참조로 추정
mov     rax, [rdi]        ; 8바이트 읽기 → long/포인터/double 역참조로 추정
```

**4) 쓰기 패턴 구분**
```asm
mov     [rdi], eax         ; *p = value  (쓰기: 대괄호가 왼쪽/목적지)
```

**5) 디버거로 실제 주소와 값 확인**

x64dbg나 GDB에서 역참조가 일어나는 명령어에 브레이크포인트를 걸고, 레지스터 값(주소)과 그 주소의 메모리 내용을 함께 확인한다.
```
(gdb) break *0x0000555555555142
(gdb) run
(gdb) info registers rdi
(gdb) x/1xg $rdi          # rdi가 가리키는 주소의 8바이트 내용 확인
```

## 명령어/단축키
```
(gdb) x/xg $rax        # rax가 가리키는 주소의 8바이트를 헥스로 출력
(gdb) x/s $rax          # rax가 가리키는 주소를 문자열로 출력 (REV-0036 참고)
(gdb) print *(int*)$rax # rax를 int 포인터로 캐스팅해서 역참조 값 출력
```
IDA: 포인터로 추정되는 변수 위에서 `Y`(Set type)로 타입을 `int *`, `char *` 등으로 지정하면 디컴파일 결과에 `->`, `*`, `[]` 표현이 훨씬 자연스럽게 나타난다.

## 출력 해석
- `mov eax, [rdi]`는 "rdi가 가리키는 곳의 4바이트를 읽어 eax에 저장" = `eax = *(int*)rdi`.
- `mov [rdi], eax`는 "eax의 값을 rdi가 가리키는 곳에 4바이트로 씀" = `*(int*)rdi = eax`.
- `lea rax, [rdi+8]`는 "rdi+8이라는 주소값 자체를 rax에 저장" = `rax = (char*)rdi + 8` — 메모리를 전혀 읽지 않는다는 점이 `mov rax, [rdi+8]`(그 주소의 내용을 읽음)과 결정적으로 다르다.
- 같은 대괄호 수식이라도 `lea`는 주소, `mov`는 그 주소의 내용이라는 차이만 정확히 구분하면 포인터 관련 코드의 절반은 해석이 끝난 것이다.

## 흔한 실수
- `lea`도 메모리를 읽는다고 착각하는 것 — `lea`는 절대 메모리에 접근하지 않는다. 순수하게 주소 계산(덧셈/곱셈)만 수행하는 명령어다.
- `mov rax, [rdi]`와 `mov rax, rdi`를 헷갈리는 것 — 대괄호 유무 하나로 "포인터가 가리키는 값을 읽는다"와 "포인터 값 자체를 복사한다"가 완전히 달라진다.
- NULL 포인터 역참조 크래시를 만났을 때, 크래시 주소가 왜 `0x0` 근처인지 이해하지 못하는 것 — `mov eax, [rax]`에서 `rax`가 0이면 주소 `0x0`을 읽으려는 시도이므로 곧바로 Access Violation/SIGSEGV가 발생한다.
- 이중 포인터의 두 번째 역참조를 첫 번째와 혼동해서, `**pp`의 결과를 `*pp`의 결과로 잘못 읽는 것 — `mov rax, [rdi]` 다음에 `mov eax, [rax]`가 있는지 반드시 줄 단위로 순서를 확인해야 한다.

## 막혔을 때 다음 체크
- 배열 인덱싱(`p[i]`)이 포인터 연산과 어떻게 다르게/비슷하게 컴파일되는지 궁금하면 → REV-0034(배열 접근이 어셈블리로 변하는 방식)로 이동.
- `p->field` 같은 구조체 필드 접근이 궁금하면 → REV-0035(구조체 접근이 어셈블리로 변하는 방식)로 이동.
- 포인터가 함수 인자로 어떻게 넘어오는지 궁금하면 → REV-0032(함수 인자와 반환값이 어디에 있는지)로 이동.
- 포인터가 가리키는 곳이 스택인지 힙인지 데이터 영역인지 헷갈리면 → REV-0030(Code Data BSS Stack Heap 기초)으로 이동.

## 미니 예제
다음 C 함수로 `lea`, 역참조, 이중 포인터 패턴을 한 번에 확인해보자.

```c
int add_via_pointer(int *p, int *q) {
    int local = 100;
    int *r = &local;      // lea 패턴
    *q = *p + *r;          // 두 번 역참조 후 한 번 쓰기
    return *q;
}
```

x64 SysV 어셈블리(개념 설명용, 최적화 없는 형태):
```asm
add_via_pointer:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-0x18], rdi   ; p
    mov     [rbp-0x20], rsi   ; q
    mov     dword [rbp-4], 100        ; local = 100
    lea     rax, [rbp-4]              ; r = &local  (주소 계산만)
    mov     [rbp-0x10], rax           ; r 저장

    mov     rax, [rbp-0x18]           ; rax = p
    mov     edx, [rax]                ; edx = *p   (역참조)
    mov     rax, [rbp-0x10]           ; rax = r
    mov     eax, [rax]                ; eax = *r   (역참조)
    add     eax, edx                  ; eax = *p + *r

    mov     rdx, [rbp-0x20]           ; rdx = q
    mov     [rdx], eax                ; *q = eax   (역참조를 통한 쓰기)

    mov     rax, [rbp-0x20]           ; rax = q
    mov     eax, [rax]                ; return *q  (다시 역참조)
    pop     rbp
    ret
```

IDA/Ghidra는 이 흐름을 다음과 같이 자연스러운 C로 되돌려준다.

```c
int add_via_pointer(int *p, int *q)
{
  int local;
  int *r;

  local = 100;
  r = &local;
  *q = *p + *r;
  return *q;
}
```

`lea rax, [rbp-4]`가 `r = &local`로, `mov edx, [rax]` 형태의 대괄호 읽기가 각각 `*p`, `*r`로, 마지막의 `mov [rdx], eax`가 `*q = ...`(쓰기)로 정확히 대응하는 것을 볼 수 있다.

## 관련 글
- REV-0030 — Code Data BSS Stack Heap 기초
- REV-0032 — 함수 인자와 반환값이 어디에 있는지
- REV-0034 — 배열 접근이 어셈블리로 변하는 방식
- REV-0035 — 구조체 접근이 어셈블리로 변하는 방식

## 출처/검증
- `MOV`의 레지스터-메모리 오퍼랜드 동작과 `LEA`(Load Effective Address)의 정의: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.2 명령어 레퍼런스 기준 (2026-09-08 검증).
- C 포인터 연산자(`*`, `&`)의 의미론: ISO C 표준(C11) 6.5.3 Unary operators 섹션 개념 기준.
