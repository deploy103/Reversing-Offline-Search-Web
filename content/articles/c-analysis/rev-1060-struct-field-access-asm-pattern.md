---
id: REV-1060
title: "구조체 필드 접근이 어셈블리에서 보이는 패턴"
slug: "rev-1060-struct-field-access-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["구조체 필드 접근 어셈블리", "struct field access asm pattern", "구조체 패딩 오프셋 C 코드"]
aliases: ["s->field 어셈블리에서 어떻게 보임", "구조체 접근 C ASM 대조", "구조체 오프셋 계산 디스어셈블"]
symptom_keywords: ["구조체 필드 오프셋이 필드 순서와 안 맞는 이유를 모르겠음", "s->field가 어셈블리에서 어떻게 변하는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`s->field`는 어셈블리에서 "구조체 시작 주소 + 그 필드의 **컴파일 시점에 고정된** 바이트 오프셋"으로 컴파일되며(`mov eax, [rax+8]`), 배열 인덱싱(REV-1058)과 달리 오프셋에 레지스터 곱셈이 전혀 없고, 그 오프셋 값이 필드 선언 순서를 그대로 누적한 값이 아니라 **정렬(alignment) 규칙 때문에 패딩이 끼어든 값**일 수 있다는 게 핵심이다.

## 언제 검색해야 하나
- `[rax+8]`, `[rdi+0xc]`처럼 대괄호 안에 레지스터와 고정 상수 하나만 있는 코드를 만났을 때, 이게 배열 인덱싱(REV-1058)인지 구조체 필드 접근인지 구분하고 싶을 때
- 구조체에 필드를 하나 추가했더니 필드 오프셋 순서(0, 4, 8, ...)가 예상과 다르게 튀는 걸 보고 이유를 알고 싶을 때
- IDA/Ghidra가 구조체 타입을 인식 못 해서 `*(int *)(a1 + 8)`처럼 캐스팅으로만 보여줄 때 원래 필드 접근이었다는 걸 알아채고 싶을 때

## 핵심 개념

### 원본 C 코드
```c
typedef struct {
    int  id;      // offset 0
    char grade;   // offset 4
    int  score;   // offset 8  (grade 뒤 3바이트는 패딩)
} Student;

int get_score(Student *s) {
    return s->score;
}
```
`grade`는 1바이트지만 다음 필드 `score`(`int`, 4바이트 정렬 필요)가 4의 배수 오프셋에 와야 하므로, `grade`(offset 4) 뒤에 3바이트 패딩이 끼어들고 `score`는 offset 5가 아니라 **offset 8**에 위치한다.

### -O0 x86-64 어셈블리
```asm
get_score:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-8], rdi   ; s
    mov     rax, [rbp-8]    ; rax = s
    mov     eax, [rax+8]    ; eax = s->score   (offset 8, 5가 아님!)
    leave
    ret
```

### 줄 단위 대응 — 배열 인덱싱과의 결정적 차이
- `mov eax, [rax+8]` — `+8`은 **상수**다. 배열 인덱싱(REV-1058)의 `[rdx+rax*4]`처럼 레지스터×스케일 곱셈이 전혀 없다. **대괄호 안에 곱셈이 있으면 배열, 상수만 있으면 구조체 필드**라는 게 가장 확실한 1차 구분법이다.
- `+8`이라는 값 자체가 `id`(4바이트) + `grade`(1바이트) + 패딩(3바이트) = 8을 그대로 반영한다. 필드 선언 순서(`id`, `grade`, `score`)만 보고 "score는 5번째 바이트겠지"라고 손으로 계산하면 틀린다 — 반드시 각 필드의 정렬 요구사항(보통 자기 타입 크기만큼 정렬)을 고려해야 한다.
- `s`가 함수 인자로 들어온 포인터이므로, 먼저 그 포인터 값을 레지스터로 로드(`mov rax, [rbp-8]`)한 뒤 오프셋을 더해 역참조하는 두 단계가 나타난다. 구조체가 스택의 지역 변수 자체라면 `lea`로 구조체의 시작 주소를 구한 뒤 같은 방식으로 오프셋을 더한다(REV-0035 참고).

### 값을 쓰는 방향
```c
void set_id(Student *s, int id) {
    s->id = id;
}
```
```asm
set_id:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-8], rdi    ; s
    mov     [rbp-0xc], esi   ; id
    mov     rax, [rbp-8]     ; rax = s
    mov     edx, [rbp-0xc]   ; edx = id
    mov     [rax], edx        ; s->id = id   (offset 0, 그래서 +0이 생략됨)
    leave
    ret
```
`id`는 구조체의 첫 번째 필드(offset 0)라서 `[rax+0]`이 아니라 그냥 `[rax]`로 오프셋 표시가 생략된다. 오프셋이 0인 필드는 어셈블리에 상수가 안 보이므로, "이 필드가 구조체의 맨 앞이다"라는 신호로 읽어야 한다.

### 디컴파일러가 복원한 pseudocode
```c
int get_score(Student *s)
{
  return s->score;
}
```
IDA/Ghidra가 `Student` 구조체 타입을 인식(또는 사용자가 직접 정의)했다면 필드 이름 그대로 복원해준다. 인식하지 못하면 `return *(int *)((char *)s + 8);`처럼 오프셋 숫자가 그대로 노출된 캐스팅 코드로 보여준다. 이 경우 오프셋 8, 그 앞뒤로 등장하는 다른 오프셋들(0, 4)을 모두 모아 정렬하면 구조체 레이아웃을 역으로 재구성할 수 있다 — IDA의 Structures 창(`Shift+F9`)에 이 오프셋들로 새 구조체 타입을 만들어 붙이면 이후 모든 참조가 자동으로 필드 이름으로 바뀐다.

## 화면/코드에서 보이는 징후
- `[reg+N]`(N이 작고 고정된 상수, 곱셈 없음)이 반복문 없이 여러 곳에서 서로 다른 N 값으로 등장한다 — 같은 구조체의 여러 필드에 접근하는 코드일 가능성이 높다.
- 오프셋 간격이 등간격(0, 4, 8, 12)이 아니라 불규칙(0, 4, 8, **16**)하게 튄다 — 그 사이에 패딩이 있다는 신호다.
- IDA/Ghidra가 구조체 타입을 인식하면 `s->field`, 인식 못 하면 `*(TYPE *)(s + N)` 캐스팅 형태로 보여준다.

## 가장 먼저 할 것
같은 베이스 레지스터에 대해 서로 다른 상수 오프셋으로 접근하는 코드들을 모두 찾아 오프셋을 오름차순으로 나열한다. 이 목록이 곧 그 구조체의 필드 레이아웃 추정치다. 오프셋 사이에 간격이 예상보다 크면 패딩을 의심한다.

## 단계별 절차
1. `[reg+N]`(N은 상수, 곱셈 없음) 형태의 접근을 찾고, 같은 `reg`에 대한 다른 오프셋들을 함께 수집한다.
2. 각 오프셋에서 읽는 크기(`mov eax,`는 4바이트, `mov al,`은 1바이트, `mov rax,`는 8바이트)로 필드 타입을 추정한다.
3. 오프셋 간격이 필드 크기와 정확히 일치하지 않으면 패딩이 있다고 판단하고, 그 구간을 "unknown/padding"으로 표시해둔다.
4. IDA Structures 창이나 Ghidra의 Data Type Manager에서 이 오프셋들로 구조체를 직접 정의해 붙인다.

## 명령어/단축키
```
(gdb) disas get_score
(gdb) print $rdi                    ; s 포인터 값
(gdb) x/4xw $rdi                    ; id, grade+패딩, score를 4바이트씩 덤프해서 오프셋 확인
(gdb) print *(int*)((char*)$rdi+8)  ; s->score를 직접 계산해서 검증
```
IDA: Structures 창(`Shift+F9`)에서 새 구조체 정의 → 함수 인자/변수에 그 구조체 포인터 타입 지정 → `[rax+8]`이 자동으로 `s->score`로 표시됨.

## 출력 해석
- 오프셋 0은 항상 구조체의 첫 필드다(어셈블리에 `+0`이 안 보이고 그냥 `[reg]`로만 나타남에 주의).
- 오프셋 간격이 필드 크기 합과 안 맞으면 그 차이만큼이 패딩이다. 예: `grade`(1바이트, offset 4) 다음 필드가 offset 8이면 3바이트 패딩이 있다는 뜻이다.
- 구조체 전체 크기(`sizeof`)가 예상보다 크면, 마지막 필드 뒤에도 "꼬리 패딩(tail padding)"이 붙어 구조체 배열을 만들 때 전체 정렬을 맞춘다는 걸 의미한다.

## 흔한 실수
- 구조체 필드 오프셋(상수만 있는 `[reg+N]`)과 배열 인덱스(레지스터 곱셈이 있는 `[reg+reg*N]`)를 혼동하는 것 — 곱셈의 유무로 명확히 구분해야 한다.
- 필드 선언 순서만 보고 오프셋을 손으로 누적 계산해서 패딩을 놓치는 것 — `char` 다음에 `int`가 오면 반드시 패딩을 의심해야 한다.
- `p->field`와 `(*p).field`가 완전히 동일한 어셈블리로 컴파일된다는 걸 모르고 소스 문법 차이에 의미를 두는 것 — C 표준에서도 두 표현은 정의상 동일하다.
- 중첩 구조체(`outer->inner.field`)의 경우, 내부 구조체의 오프셋과 필드 오프셋이 **한 번에 더해진 단일 상수**로 나타난다는 것을 놓치는 것 — 이 경우는 REV-1061(중첩 구조체 접근)에서 더 자세히 다룬다.
- `-O2`에서 구조체 필드가 레지스터에 캐시되어 재사용되면(같은 필드를 여러 번 읽는 대신 한 번 읽어서 레지스터에 계속 들고 있는 경우) 오프셋이 있는 `[reg+N]` 접근 자체가 함수 전체에서 딱 한 번만 나타날 수 있다는 것을 놓치는 것.

## 막혔을 때 다음 체크
- 패딩과 정렬 규칙의 더 깊은 원리가 궁금하면 → REV-0344(정렬(Alignment)과 패딩이 구조체에 미치는 영향), REV-0035(구조체 접근이 어셈블리로 변하는 방식).
- 구조체 안에 또 다른 구조체가 들어있는 경우가 궁금하면 → REV-1061(중첩 구조체 접근이 어셈블리에서 보이는 패턴).
- 구조체로 이루어진 배열을 순회하는 경우가 궁금하면 → REV-1064(구조체 배열 순회가 어셈블리에서 보이는 패턴).
- 배열 인덱싱과의 구분이 계속 헷갈리면 → REV-1058(1차원 배열 인덱싱이 어셈블리에서 보이는 패턴).
- 오프셋이 이상하게 나올 때의 트러블슈팅은 → REV-0377(구조체 오프셋이 생각한 것과 다를 때).

## 미니 예제
구조체의 여러 필드를 한 함수 안에서 동시에 다루면 오프셋들이 한눈에 모여 비교하기 좋다.
```c
typedef struct {
    int  hp;      // offset 0
    int  mp;      // offset 4
    char level;   // offset 8
} Player;

void heal_full(Player *p) {
    p->hp = 100;
    p->mp = 50;
    p->level = 1;
}
```
```asm
heal_full:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-8], rdi     ; p
    mov     rax, [rbp-8]
    mov     dword [rax], 100     ; p->hp = 100      (offset 0)
    mov     rax, [rbp-8]
    mov     dword [rax+4], 50    ; p->mp = 50       (offset 4)
    mov     rax, [rbp-8]
    mov     byte [rax+8], 1       ; p->level = 1     (offset 8)
    leave
    ret
```
이 구조체는 `hp`(4)+`mp`(4)+`level`(1)로 필드 크기 합이 9바이트지만, 마지막에 꼬리 패딩이 붙어 전체 `sizeof(Player)`는 12바이트가 된다(가장 큰 정렬 요구사항인 4바이트의 배수로 맞춤). 오프셋 0, 4, 8이 등간격으로 나온 것은 이 구조체에 필드 사이 패딩이 없었기 때문이며, `grade`처럼 1바이트 필드가 중간에 끼면 앞의 `Student` 예제처럼 오프셋이 튈 수 있다.

## 관련 글
- REV-0035 — 구조체 접근이 어셈블리로 변하는 방식
- REV-0344 — 정렬(Alignment)과 패딩이 구조체에 미치는 영향
- REV-0377 — 구조체 오프셋이 생각한 것과 다를 때
- REV-1058 — 1차원 배열 인덱싱이 어셈블리에서 보이는 패턴
- REV-1061 — 중첩 구조체 접근이 어셈블리에서 보이는 패턴
- REV-1064 — 구조체 배열 순회가 어셈블리에서 보이는 패턴

## 출처/검증
- 구조체 멤버 정렬(alignment)과 패딩 규칙: System V AMD64 ABI 공식 스펙의 "Aggregates and Unions" 섹션 및 C11 표준 6.7.2.1 Structure and union specifiers 기준.
- 고정 오프셋 메모리 오퍼랜드(`[reg+disp]`)와 SIB 기반 배열 접근의 인코딩 차이: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.2 기준 (2026-09-10 검증).
