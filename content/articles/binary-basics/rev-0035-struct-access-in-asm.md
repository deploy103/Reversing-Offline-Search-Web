---
id: REV-0035
title: "구조체 접근이 어셈블리로 변하는 방식"
slug: "rev-0035-struct-access-in-asm"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["구조체 접근", "struct access", "필드 오프셋", "field offset", "패딩", "padding", "mov eax rdi+8"]
aliases: ["구조체가 어셈블리에서 어떻게 보이나요", "rdi+8이 뭔가요", "구조체 패딩이 뭔가요", "필드 오프셋 역산"]
symptom_keywords: ["rdi+8 rdi+0xc 처럼 고정 오프셋이 왜 나오는지 모르겠음", "구조체 필드가 어셈블리에서 어떻게 보이는지 모르겠음", "구조체 패딩 때문에 오프셋이 안 맞는 이유를 모르겠음", "화살표 연산자가 어셈블리로 어떻게 변하는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
구조체 필드 접근(`s.field`, `p->field`)은 어셈블리에서 "구조체 시작 주소 + 그 필드의 고정 바이트 오프셋"으로 컴파일되며(`mov eax, [rdi+8]`), 배열 인덱싱과 달리 이 오프셋은 **런타임에 계산되지 않고 컴파일 시점에 이미 확정된 상수**라는 점이 가장 큰 차이다.

## 언제 검색해야 하나
- `mov eax, [rdi+8]`, `mov [rax+0x10], ecx`처럼 대괄호 안에 레지스터와 고정 상수만 더해진 코드를 봤을 때
- IDA/Ghidra가 구조체를 인식하지 못해서 `*(int *)(a1 + 0xC)`처럼 캐스팅 범벅으로 보여줄 때, 이것이 원래 `p->field`였다는 걸 알아채고 싶을 때
- 구조체에 필드를 하나 추가했더니 다른 필드들의 오프셋이 왜 갑자기 밀리는지(패딩) 이해하고 싶을 때
- `p->field`(화살표)와 `s.field`(점)이 어셈블리 레벨에서 어떻게 다른지/같은지 궁금할 때

## 핵심 개념
구조체(struct)는 서로 다른 타입의 값들을 하나의 메모리 블록 안에 순서대로 배치한 것이다. 컴파일러는 구조체를 정의하는 시점에 각 필드가 구조체 시작점으로부터 몇 바이트 떨어져 있는지를 전부 계산해서 고정시켜 버린다. 그래서 필드 접근은 배열 인덱싱(REV-0034)과 달리 **런타임에 곱셈을 할 필요가 없다** — 오프셋이 이미 상수로 정해져 있으므로 그냥 `주소+상수`만 계산하면 된다.

```c
struct Point {
    int x;       // offset 0
    int y;       // offset 4
};
```
```asm
mov     eax, [rdi]        ; p->x   (offset 0이므로 +0은 생략)
mov     eax, [rdi+4]      ; p->y   (offset 4)
```

`p->field`(포인터를 통한 접근)와 `s.field`(구조체 변수 직접 접근)는 **어셈블리 레벨에서는 거의 같은 패턴**이다. 차이는 "베이스 레지스터에 이미 들어있는 것이 포인터냐, 아니면 지역 변수인 구조체 자체의 시작 주소(스택 프레임 안)냐"뿐이다.

```c
struct Point pt;
pt.y = 10;              // 스택 위 구조체, 베이스는 lea로 계산한 지역 주소
```
```asm
lea     rax, [rbp-8]      ; &pt  (구조체가 스택에 있다면 그 시작 주소)
mov     dword [rax+4], 10 ; pt.y = 10
```

구조체가 지역 변수라면 컴파일러가 종종 `lea`로 주소를 구하는 단계 자체를 생략하고 `[rbp-8+4]` = `[rbp-4]`처럼 바로 오프셋을 rbp에 합산해버리기도 한다. 반면 포인터로 받은 구조체는 반드시 그 포인터 레지스터를 거쳐서 접근한다.

**구조체 필드 오프셋과 패딩(padding).** 각 필드는 자신의 타입에 맞는 정렬(alignment) 규칙을 따른다 — 예를 들어 `int`는 4바이트 경계에, `double`/포인터는 8바이트 경계에 놓이는 것이 일반적이다. 그래서 다음과 같은 구조체는 필드 순서만으로 크기를 짐작하면 틀리기 쉽다.

```c
struct Mixed {
    char  a;   // offset 0        (1바이트)
    // 패딩 3바이트 (offset 1~3)  — int b가 4바이트 경계에 오도록
    int   b;   // offset 4        (4바이트)
    char  c;   // offset 8        (1바이트)
    // 패딩 7바이트 (offset 9~15) — double d가 8바이트 경계에 오도록
    double d;  // offset 16       (8바이트)
};              // 전체 크기 24바이트 (8의 배수로 정렬)
```
어셈블리에서 이 구조체를 접근하는 코드를 보면 `[rdi]`(a), `[rdi+4]`(b), `[rdi+8]`(c), `[rdi+16]`(d)처럼 오프셋 사이에 "구멍"이 보이는데, 그 구멍이 바로 패딩이다. 오프셋이 1씩 딱딱 붙어있지 않고 4/8의 배수로 튀는 걸 보면 "이 사이에 패딩이 있구나"라고 짐작할 수 있다.

**구조체 배열의 필드 접근**(REV-0034와 결합되는 경우)은 인덱스 곱셈과 필드 오프셋 덧셈이 함께 나타난다.
```c
struct Point pts[10];
pts[i].y = 5;
```
```asm
imul    rax, rsi, 8        ; i * sizeof(struct Point)  (Point가 8바이트이므로 배율 8)
add     rax, rdi            ; &pts[i]
mov     dword [rax+4], 5    ; pts[i].y = 5   (필드 y의 오프셋 4를 더함)
```
`sizeof(struct Point)`가 1/2/4/8이 아니면 SIB 배율을 못 쓰고 `imul`로 계산한다는 점은 REV-0034에서 다룬 것과 동일하다.

## 화면/코드에서 보이는 징후
- `[reg+N]` 형태(N이 0, 4, 8, 0xC, 0x10 등 작고 고정된 상수)가 반복문 없이 여러 번 나타나되, 매번 N만 다르다 — 서로 다른 필드에 접근하는 코드일 가능성이 높다.
- 같은 베이스 레지스터에 대해 여러 개의 서로 다른 오프셋으로 접근하는 코드가 한 함수 안에 몰려 있다(구조체 초기화 함수나 getter/setter류).
- IDA/Ghidra가 구조체 타입을 인식하면 `p->x`, `p->y`처럼 필드 이름으로 보여주고, 인식하지 못하면 `*(int *)(a1 + 4)`처럼 원시 캐스팅으로 보여준다.
- 오프셋 사이 간격이 불규칙(0, 4, 8, 16처럼 8을 건너뛰는 등)하면 패딩이 존재하는 구조체다.

## 가장 먼저 할 것
같은 베이스 레지스터에 여러 오프셋으로 접근하는 코드를 발견하면, 그 오프셋들을 **모두 모아서 오름차순으로 정렬**해본다. 이 목록이 사실상 그 구조체의 필드 레이아웃이다. IDA에서는 이 정보를 바탕으로 Structures 창(`Shift+F9`)에서 새 구조체 타입을 만들어 각 오프셋에 이름을 붙이면, 이후 모든 참조가 자동으로 `struct명.필드명`으로 바뀌어 훨씬 읽기 쉬워진다.

## 단계별 절차

**1) 같은 베이스에 대한 오프셋 목록 수집**
```asm
mov     eax, [rdi]         ; offset 0
mov     [rdi+4], ecx        ; offset 4
mov     dl, [rdi+8]         ; offset 8
mov     rax, [rdi+0x10]     ; offset 0x10 (16)
```
오프셋 목록: 0, 4, 8, 0x10 → 필드 4개, 세 번째와 네 번째 사이(8→16)에 4바이트 정도 간격이 있음(8바이트 필드이거나 패딩+4바이트 필드).

**2) 각 오프셋에서 읽는 크기로 필드 타입 추정**
```asm
mov     eax, [rdi]         ; 4바이트 읽기 → offset 0은 int 계열
mov     dl, [rdi+8]         ; 1바이트 읽기 → offset 8은 char 계열
mov     rax, [rdi+0x10]     ; 8바이트 읽기 → offset 0x10은 long/포인터/double 계열
```

**3) IDA에서 구조체 타입 직접 정의**

IDA의 Structures 창(`Shift+F9`)에서 `Insert`로 새 구조체를 만들고, 위에서 수집한 오프셋마다 필드를 추가한다. 그 후 코드에서 베이스 레지스터를 우클릭 → "Convert to struct offset" 또는 변수 타입을 그 구조체 포인터로 지정하면, `[rdi+8]` 같은 표현이 `[rdi].field_8`처럼 이름 붙은 형태로 바뀐다.

**4) 디버거로 실제 필드 값 확인**
```
(gdb) break *0x0000555555555150
(gdb) run
(gdb) print $rdi
(gdb) x/4xg $rdi         # 구조체 시작 주소부터 32바이트(필드 4개 가정)를 헥스로 덤프
```

## 명령어/단축키
IDA: `Shift+F9` (Structures 창), 구조체 정의 후 오퍼랜드 위에서 `T`(Set struct offset 관련 단축키 계열)로 적용
```
(gdb) ptype struct Point   # 디버그 정보가 있을 때 구조체 정의 확인
(gdb) print *(struct Point *)$rdi   # 구조체 포인터로 캐스팅해서 전체 필드 한번에 출력
```

## 출력 해석
- `[reg]`(오프셋 0)은 구조체의 첫 번째 필드다.
- `[reg+N]`에서 N이 작고 고정된 상수라면 필드 오프셋이다. N이 레지스터×배율 형태라면(REV-0034) 배열 인덱싱이지 구조체 필드가 아니다 — 이 둘을 구분하는 게 핵심이다.
- 오프셋 간격이 필드 크기와 딱 맞아떨어지지 않고 더 크게 튄다면 그 사이에 패딩이 있다는 뜻이다. 구조체 전체 크기가 가장 큰 필드의 정렬 단위(보통 8바이트)의 배수로 맞춰지는 것도 패딩 때문이다(구조체 끝 패딩, tail padding).

## 흔한 실수
- 구조체 필드 오프셋(`[rdi+8]`)과 배열 인덱스(`[rdi+rsi*4]`)를 같은 것으로 보는 것 — 전자는 상수, 후자는 레지스터×배율이라는 형태 차이로 구분해야 한다.
- 패딩을 고려하지 않고 "필드가 4개면 오프셋도 0, 4, 8, 12로 딱 떨어지겠지"라고 가정하는 것 — `char` 다음에 `int`가 오면 패딩이 끼어들어 예상과 다른 오프셋이 나온다.
- `p->field`와 `(*p).field`가 어셈블리 레벨에서 동일한 코드로 컴파일된다는 것을 모르고 소스 레벨 문법 차이에 집착하는 것 — 둘은 C 표준에서도 완전히 동일한 의미이며 어셈블리에서 구분할 방법이 없다.
- 구조체 안에 다른 구조체가 중첩된 경우(`struct Outer { struct Inner in; int x; }`), 내부 구조체 필드에 접근할 때 오프셋이 두 단계로 누적된다는 것을 놓치는 것 — `outer->in.field`는 `[rdi + Inner내오프셋]`처럼 그냥 한 번에 더해진 상수로 나타난다(중첩 구조체도 결국 한 메모리 블록이므로).

## 막혔을 때 다음 체크
- 대괄호와 역참조의 기본 원리 자체가 헷갈리면 → REV-0033(포인터와 역참조를 어셈블리에서 읽는 법)으로 이동.
- 구조체 배열(`pts[i].field`)처럼 배열 인덱싱과 필드 접근이 함께 나오는 경우가 궁금하면 → REV-0034(배열 접근이 어셈블리로 변하는 방식)로 이동.
- 이 구조체가 스택/힙/전역 중 어디에 있는지 헷갈리면 → REV-0030(Code Data BSS Stack Heap 기초)으로 이동.

## 미니 예제
다음 구조체와 함수로 필드 오프셋이 실제 코드에서 어떻게 나타나는지 확인해보자.

```c
struct Player {
    int   hp;     // offset 0
    int   mp;     // offset 4
    char  name[8]; // offset 8
};

void heal(struct Player *p, int amount) {
    p->hp += amount;
    if (p->hp > 100)
        p->hp = 100;
}
```

x64 SysV 어셈블리(개념 설명용):
```asm
heal:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-8], rdi     ; p
    mov     [rbp-0xC], esi   ; amount

    mov     rax, [rbp-8]     ; rax = p
    mov     edx, [rax]       ; edx = p->hp    (offset 0)
    mov     eax, [rbp-0xC]   ; eax = amount
    add     edx, eax          ; p->hp + amount
    mov     rax, [rbp-8]
    mov     [rax], edx        ; p->hp = p->hp + amount   (쓰기, offset 0)

    mov     rax, [rbp-8]
    mov     eax, [rax]        ; p->hp 다시 읽기
    cmp     eax, 100
    jle     skip
    mov     rax, [rbp-8]
    mov     dword [rax], 100  ; p->hp = 100
skip:
    pop     rbp
    ret
```

IDA/Ghidra가 `struct Player`를 인식했다면 다음처럼 필드 이름 그대로 보여준다.

```c
void heal(Player *p, int amount)
{
  p->hp += amount;
  if ( p->hp > 100 )
    p->hp = 100;
}
```

만약 IDA가 구조체 타입을 자동으로 못 잡았다면 `[rax]`가 `p->hp`(offset 0)라는 것, 그리고 뒤에서 `mp`(offset 4)나 `name`(offset 8)에 접근하는 코드가 나온다면 `[rax+4]`, `[rax+8]`로 나타난다는 것을 직접 손으로 대응시켜야 한다. 이때 필드 순서를 몰라도, 코드에 등장하는 오프셋들을 모아 정렬하면 구조체 레이아웃을 역으로 복원할 수 있다.

## 관련 글
- REV-0030 — Code Data BSS Stack Heap 기초
- REV-0033 — 포인터와 역참조를 어셈블리에서 읽는 법
- REV-0034 — 배열 접근이 어셈블리로 변하는 방식

## 출처/검증
- 구조체 멤버 정렬(alignment)과 패딩 규칙: System V AMD64 ABI 공식 스펙의 "Aggregates and Unions" 섹션 및 C11 표준 6.7.2.1 Structure and union specifiers 기준 (2026-09-08 검증).
- x86/x64 고정 오프셋 메모리 오퍼랜드(`[reg+disp]`) 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.2 기준.
