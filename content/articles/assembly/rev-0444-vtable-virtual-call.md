---
id: REV-0444
title: "vtable과 가상함수 호출 패턴 분석"
slug: "rev-0444-vtable-virtual-call"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - vtable
  - virtual table
  - 가상함수 테이블
  - virtual function
  - 가상함수 호출
  - vptr
  - "??_7"
  - thiscall
  - this pointer
  - C++ 다형성
  - 이중 역참조
  - double dereference call
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - vtable이 뭐임
  - 가상함수가 어떻게 호출됨
  - vptr이 뭐임
  - "this가 어느 레지스터임"
  - 가상함수 호출 어셈블리
symptom_keywords:
  - call 대상이 이중으로 역참조됨
  - "mov rax [rcx] 다음에 call [rax+xx]가 나옴"
  - xref로 가상함수를 못 찾음
  - "(**(void (**)(void))this)() 이상한 디컴파일"
last_verified: "2026-09-08"
---

## 한 줄 요약
C++의 가상함수 호출은 객체 맨 앞에 숨어있는 vptr(가상 테이블 포인터)을 읽고, 그 vtable 배열에서 함수 슬롯을 다시 읽어 `call`하는 **이중 역참조(double dereference)** 패턴으로 컴파일되며, 이 때문에 정적 xref만으로는 호출 대상을 바로 찾을 수 없다.

## 언제 검색해야 하나
- `mov rax, [rcx]` 다음에 `call [rax+0x10]`처럼 레지스터를 두 번 거쳐 `call`하는 코드를 만났을 때
- Hex-Rays 디컴파일이 `(**(void (__fastcall ***)(void *, ...))this)(this, ...)`처럼 알아보기 힘든 함수 포인터 캐스팅 덩어리로 나올 때
- C++ 바이너리에서 `obj->method()` 호출부가 REV-0071(CALL) 방식의 일반 direct call로는 안 보일 때
- 객체 생성자에서 `mov qword ptr [rcx], offset ??_7ClassName@@6B@` 같은 심볼이 보일 때
- `X`(Xrefs to)를 눌러도 어떤 함수를 호출하는지 찾을 수 없어서 답답할 때(REV-0794 참고)

## 핵심 개념

### vtable과 vptr의 역할
클래스에 `virtual` 함수가 하나라도 있으면, 컴파일러는 그 클래스(정확히는 클래스 계층 전체)마다 **하나의 vtable(가상 함수 테이블)** 을 만든다. vtable은 함수 포인터들의 배열로, 보통 읽기 전용 데이터 영역(.rodata/.rdata)에 위치하며, 슬롯 순서는 클래스 선언에서 virtual 함수가 등장한 순서와 일치한다.

이 클래스의 객체 하나하나는 자기 메모리 맨 앞(대부분 오프셋 0)에 **vptr**이라는 숨은 포인터 멤버를 갖는다. 생성자가 실행될 때 이 vptr에 자기 클래스의 vtable 주소가 채워진다. 가상함수를 호출할 때는:
1. 객체(`this`)에서 vptr을 읽는다 (`mov rax, [rcx]` — 객체 시작 8바이트).
2. vtable에서 원하는 슬롯을 읽는다 (`mov rax, [rax+slot*8]` — slot은 virtual 함수 선언 순서에 따른 인덱스).
3. 그 주소로 간접 호출한다 (`call rax`).

이 "포인터를 두 번 따라가는" 구조 때문에 vtable 기반 호출을 **이중 역참조**라고 부른다.

### `this` 포인터 전달
가상함수도 결국 평범한 함수이므로 일반 호출 규약(REV-0071 참고)을 그대로 따른다. 다만 첫 번째 인자 자리에 항상 **객체 자기 자신의 주소(`this`)** 가 암묵적으로 들어간다.
- **Itanium C++ ABI (GCC/Clang, Linux)**: SysV 규약대로 `RDI = this`, 두 번째 인자부터 `RSI, RDX, ...`.
- **MSVC (Windows x64)**: `RCX = this`, 두 번째 인자부터 `RDX, R8, R9, ...`.

### 전형적인 어셈블리 (x64 SysV)
```cpp
class Shape {
public:
    virtual int area();     // slot 0
    virtual void draw();    // slot 1
};
Shape* s = ...;
int a = s->area();
```
```asm
mov     rdi, [rbp-8]     ; rdi = s (this 포인터, 1번째 인자)
mov     rax, [rdi]        ; rax = *this = vptr (vtable 주소)
mov     rax, [rax]        ; rax = vtable[0] = Shape::area의 실제 주소 (slot 0)
call    rax                ; area(this) 호출 — this는 이미 rdi에 있음
```
`draw()`(slot 1)를 부른다면 두 번째 로드가 `mov rax, [rax+8]`이 된다 — 슬롯 인덱스 × 8(64비트 포인터 크기)만큼 오프셋이 붙는다.

### 생성자에서 vptr을 세팅하는 코드
```asm
; Shape::Shape(this) 생성자 안
mov     qword ptr [rdi], offset ??_7Shape@@6B@   ; MSVC 심볼 예시: 이 클래스의 vtable 주소를 vptr에 대입
```
Itanium ABI(GCC/Clang)에서는 `_ZTV5Shape`(vtable for Shape)처럼 이름 붙는다. 이 대입문이 생성자 맨 앞부분에 나온다는 것은, "이 함수가 이 클래스의 생성자"라는 강력한 단서가 된다 — REV-0446(C++ 생성자/소멸자 호출 패턴)에서 더 자세히 다룬다.

### 점프 테이블과의 구분
REV-0441에서 다룬 switch 점프 테이블과 vtable은 겉보기엔 둘 다 "메모리 배열에서 주소를 읽어 간접 분기"라는 점에서 비슷하지만, 결정적인 차이가 있다.

| 구분 | 점프 테이블 | vtable |
|---|---|---|
| 원소가 가리키는 곳 | 같은 함수 내부의 기본 블록 | 서로 다른, 완전히 독립된 함수 |
| 사용하는 명령 | `jmp` (반환 주소 안 남김) | `call` (반환 주소 남김) |
| 역참조 횟수 | 1회 (`jmp [table+idx*4]`) | 보통 2회 (`this→vptr→vtable[slot]`) |

`call [rax+offset]` 형태에서 그 직전에 `mov rax, [rcx]`처럼 **객체로부터 먼저 포인터를 읽어오는 단계**가 있다면 vtable일 가능성이 매우 높다.

### 다중 상속과 thunk 함수
클래스가 여러 부모를 다중 상속하면, 객체 하나가 **부모별로 여러 개의 vptr**을 가질 수 있다(각 부모 서브객체마다 하나씩). 이 경우 특정 부모 인터페이스를 통해 가상함수를 호출하면, `this` 포인터가 실제 객체 시작 주소가 아니라 그 부모 서브객체의 오프셋 위치를 가리켜야 한다. 컴파일러는 이를 위해 **thunk**라는 작은 도우미 함수를 생성한다.
```asm
; thunk 예시: this를 원래 객체 주소로 보정한 뒤 실제 구현으로 점프
thunk_func:
    sub     rcx, 0x10        ; this 포인터를 실제 객체 시작으로 보정
    jmp     real_impl         ; CALL이 아니라 JMP로 위임 (tail call과 유사)
```
vtable 슬롯 하나가 실제 함수가 아니라 이런 thunk를 가리키는 경우가 있으므로, 함수 진입부에 `this` 보정처럼 보이는 `add`/`sub`가 있으면 다중 상속 관련 코드임을 의심해볼 수 있다.

### IDA/Ghidra 디컴파일에서 보이는 형태
IDA가 vtable 구조를 정확히 인식하지 못하면, Hex-Rays는 이 이중 역참조 호출을 다음과 같이 매우 읽기 힘든 형태로 그대로 노출한다.
```c
(**(void (__fastcall ***)(void *, ...))this)(this, 5);
```
이건 "`this`가 가리키는 곳에서 함수 포인터 배열의 포인터를 읽고, 그 배열의 0번째 함수를 `this`와 인자 `5`로 호출한다"는 뜻을 억지로 C 캐스팅 문법으로 표현한 것이다. IDA에 **Class Informer** 같은 플러그인을 쓰거나, 수동으로 vtable 구조체를 정의(`Structs` 창)해 타입을 지정해주면 `this->vfptr->area(this)`처럼 훨씬 읽기 쉬운 형태로 바뀐다. Ghidra는 C++ 클래스 분석 기능(버전에 따라 다름)으로 유사한 개선을 제공한다.

### 리버싱 관점에서의 의미
가상함수 호출은 **정적 xref로 호출자를 추적할 수 없다는 점**이 가장 중요하다. 함수 `Shape::area`를 `X`(Xrefs to)로 찾아도, 실제로는 vtable 데이터 안의 함수 포인터 슬롯만 그 주소를 참조할 뿐, 호출부(`call rax`) 자체는 그 함수 이름을 전혀 언급하지 않기 때문에 "어디서 호출되는지" 정적 분석만으로는 바로 안 보인다(REV-0794). 대신:
1. vtable을 .rodata/.rdata에서 찾아 어떤 함수들이 몇 번째 슬롯에 들어있는지 먼저 파악하고,
2. 그 vtable 자체를 참조하는 곳(주로 생성자)을 xref로 찾아 클래스 경계를 알아내며,
3. 동적으로는 `call rax` 지점에 브레이크포인트를 걸고 실행 시 RAX 값을 확인해 실제 호출되는 함수를 특정한다.

## 화면/코드에서 보이는 징후
- `mov reg, [this_reg]` 다음에 `call [reg+offset]` 또는 `mov reg, [reg+offset]; call reg`처럼 두 단계 역참조 후 호출
- Hex-Rays에서 `(**(...)this)(this, ...)`처럼 함수 포인터 캐스팅이 여러 겹으로 중첩된 표현
- 생성자로 추정되는 함수 앞부분에 `mov [rcx], offset ??_7...@@6B@` 또는 `_ZTV...` 주소 대입
- `X`(Xrefs to)를 눌러도 호출자가 하나도 안 나오는 함수(간접 호출로만 불리는 경우)

## 가장 먼저 할 것
1. `call` 대상이 레지스터/메모리 계산식인지 확인하고, 그 직전에 객체 포인터에서 값을 읽어오는 `mov`가 있는지 본다.
2. 있다면 몇 단계를 거쳐 역참조되는지(1회=점프 테이블 가능성, 2회=vtable 가능성) 센다.
3. vtable로 판단되면 .rodata/.rdata에서 그 배열의 시작 주소를 찾아 슬롯별 함수 주소를 먼저 나열해둔다.

## 단계별 절차
1. 객체 포인터에서 첫 8바이트(x64)/4바이트(x86)를 읽는 코드(`mov rax, [rcx]`)를 찾는다 — vtable 포인터를 읽는 전형적인 패턴이다.
2. 그 vtable 포인터에 오프셋을 더해 함수 포인터를 읽는 코드(`mov rax, [rax+8]` 등)를 찾는다 — 오프셋/8이 몇 번째 가상함수인지 알려준다.
3. 읽어온 함수 포인터로 간접 호출(`call rax`)하는 지점을 확인한다.
4. vtable 자체의 실제 주소(보통 `.rodata`)를 Hex View로 열어 함수 포인터들을 나열하고, 각각이 실제로 어떤 함수인지 하나씩 이동해서 확인한다.

## 명령어/단축키
- IDA: vtable 데이터가 있는 주소에서 우클릭 → "Create struct from selection" 또는 `Structs` 창(Shift+F9)에서 구조체를 정의해 슬롯에 타입을 지정.
- Ghidra: C++ 클래스 분석 기능(버전에 따라 Window → Class 관련 뷰)으로 vtable/클래스 자동 인식.
- x64dbg/GDB: `call rax` 직전에 브레이크포인트를 걸고 RAX(또는 대상 레지스터) 값을 확인해 실제 호출되는 함수 주소를 동적으로 특정.

## 흔한 실수
- 이중 역참조 `call` 패턴을 보고 무조건 switch 점프 테이블로 오인하는 것 — 대상이 여러 독립 함수인지(vtable), 한 함수 내부 블록인지(점프 테이블)로 구분해야 한다.
- Hex-Rays의 `(**(void (***)(void))this)()` 같은 표현을 "디컴파일 실패, 분석 불가능"으로 포기하는 것 — 실제로는 vtable 구조를 수동으로 지정하면 대부분 정리된다.
- 가상함수 호출의 인자 개수를 셀 때 `this`(암묵적 첫 번째 인자)를 빼먹고 세는 것.
- `X`(Xrefs to)로 가상함수 호출자를 못 찾았을 때 "이 함수는 아무데서도 안 불린다"고 결론짓는 것 — vtable을 통한 간접 호출이라 정적 xref에 안 잡히는 것뿐일 수 있다.

## 막혔을 때 다음 체크
- vtable 시작 주소 바로 앞의 데이터가 궁금하면 → REV-0445(RTTI)에서 타입 정보 구조를 확인한다.
- 이 클래스의 생성자/소멸자를 찾고 vptr 대입 위치를 활용하는 방법이 궁금하면 → REV-0446.
- 여전히 xref로 호출자를 못 찾겠다면 → 정적 분석 카테고리의 관련 트러블슈팅 문서(가상함수 호출로 인한 xref 실패)를 참고하고, 동적 분석으로 전환한다.

## 미니 예제

**예제 1 — 단일 상속, x64 SysV 가상함수 호출**
```cpp
class Base { public: virtual int foo(); };
Base* p = ...;
int r = p->foo();
```
```asm
mov     rdi, [rbp-8]   ; this
mov     rax, [rdi]      ; vptr
mov     rax, [rax]      ; vtable[0] = foo 주소
call    rax              ; foo(this)
```

**예제 2 — MSVC x64, slot 1 호출**
```asm
mov     rcx, [rbp+0x10]   ; this (MSVC는 RCX)
mov     rax, [rcx]         ; vptr
call    qword ptr [rax+8]  ; vtable[1](=두 번째 virtual 함수), this는 이미 rcx
```

**예제 3 — 생성자에서 vptr 세팅**
```asm
; Base::Base(this)
mov     qword ptr [rcx], offset ??_7Base@@6B@   ; vtable 주소를 객체 첫 8바이트에 기록
mov     rax, rcx
ret
```

**예제 4 — Hex-Rays 원시 디컴파일 vs 구조체 지정 후**
```c
// 구조체 미지정 상태
(**(int (__fastcall ***)(void *))this)(this);

// vtable 구조체를 지정한 뒤
this->vfptr->foo(this);
```

## 관련 글
- REV-0441 — Switch문 점프 테이블(Jump Table) 완전 분석
- REV-0445 — RTTI(런타임 타입 정보) 흔적 분석
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0446 — C++ 생성자/소멸자 호출 패턴 읽기

## 출처/검증
- vtable/vptr 구조와 가상함수 호출 시 이중 역참조 방식: Itanium C++ ABI("Run-time Type Identification" 및 가상 함수 호출 규약 절) 공식 스펙 기준 (2026-09-08 검증).
- MSVC 측 vtable 심볼 규칙(`??_7...@@6B@`)과 x64 thiscall(RCX=this) 관례: Microsoft C++ 이름 맹글링 및 x64 calling convention 공식 문서 기준.
- 다중 상속 thunk 함수의 `this` 보정 패턴: Itanium C++ ABI "Virtual Table Thunks" 절 기준.
