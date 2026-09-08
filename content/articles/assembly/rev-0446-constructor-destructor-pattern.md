---
id: REV-0446
title: "C++ 생성자/소멸자 호출 패턴 읽기"
slug: "rev-0446-constructor-destructor-pattern"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - constructor
  - destructor
  - 생성자
  - 소멸자
  - ctor
  - dtor
  - this pointer
  - this 포인터
  - name mangling
  - 이름 맹글링
  - operator new
  - operator delete
  - vtable pointer 초기화
  - Foo::Foo
  - Foo::~Foo
aliases:
  - 생성자 어디서 불림
  - 소멸자가 언제 실행되는지 모르겠음
  - C++ 객체 생성 어셈블리
  - this 포인터가 뭔지 모르겠음
  - ctor dtor 구분
symptom_keywords:
  - 함수 이름이 Foo::Foo로 나옴
  - call operator new 다음에 바로 call Foo::Foo
  - 스코프 끝나는 지점에서 이상한 call들이 연달아 나옴
  - RCX에 방금 할당한 주소가 들어감
  - 생성자인지 일반 함수인지 구분이 안 됨
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
C++ 생성자/소멸자는 겉보기엔 평범한 `CALL`이지만, 호출 직전에 "이 객체를 가리키는 포인터"(`this`)가 항상 첫 번째 인자 레지스터(`RCX` 또는 `RDI`)에 실려 있고, 함수 내부에서 멤버를 순서대로 초기화하거나 vtable 포인터를 써넣는다는 특징으로 알아볼 수 있다.

## 언제 검색해야 하나
- IDA/Ghidra 함수 이름이 `Foo::Foo`, `Foo::~Foo`, `CFoo::CFoo` 처럼 클래스 이름과 똑같은(또는 `~`가 붙은) 형태로 나올 때
- `call operator new` 직후에 곧바로 어떤 함수가 호출되고, 그 함수 안에서 방금 할당받은 포인터에 값을 채워 넣는 코드를 볼 때
- 함수 스코프(중괄호 `{}`)가 끝나는 지점에서 이유를 알 수 없는 `CALL`들이 연달아 나올 때 (소멸자 체인일 가능성)
- 어떤 함수의 첫 줄이 `mov [rax], offset vtable_for_Foo` 형태로 시작할 때
- Name mangling(`?Foo@Bar@@QEAA@XZ`, `_ZN3FooC1Ev` 등)이 뭘 뜻하는지 몰라서 함수 이름 해석이 막혔을 때

## 핵심 개념

### 생성자/소멸자도 결국 "함수"다
C++ 컴파일러는 `Foo obj(1, 2);` 같은 코드를 만나면, 내부적으로 `Foo::Foo(Foo* this, int, int)` 형태의 평범한 함수를 호출하는 코드로 바꾼다. 즉 생성자/소멸자는 문법적으로는 특별하지만, 어셈블리 레벨에서는 REV-0071(CALL)에서 다룬 일반적인 함수 호출과 완전히 동일하게 동작한다 — 차이는 **항상 객체 자신을 가리키는 포인터가 암묵적인 첫 번째 인자로 전달된다**는 점뿐이다. 이 포인터를 `this`라고 부른다.

- Windows x64(Microsoft ABI): `this`는 **RCX**에 들어간다 (REV-0122 참고). 나머지 명시적 인자는 RDX, R8, R9 순으로 밀린다.
- Linux x64(SysV ABI): `this`는 **RDI**에 들어간다 (REV-0106 참고). 나머지 인자는 RSI, RDX, RCX, R8, R9 순.
- x86(32비트)에서는 컴파일러에 따라 `thiscall`(MSVC, `this`는 ECX)이나 스택 전달 방식을 쓴다.

### 객체 생성의 전형적인 3단계
스택이 아니라 힙에 객체를 만드는 `new Foo(...)` 코드는 보통 다음 순서로 컴파일된다.
1. **메모리 할당**: `call operator new` (또는 `call malloc`) — 반환값(RAX)이 아직 초기화되지 않은 원시 메모리 주소.
2. **생성자 호출**: 방금 받은 포인터를 `this`용 레지스터(RCX/RDI)에 넣고 `call Foo::Foo`. 생성자 내부에서 멤버 변수들을 선언 순서대로(코드 순서가 아니라 **클래스 정의에 선언된 순서**) 초기화한다.
3. **vtable 포인터 세팅**(가상 함수가 있는 클래스라면): 생성자의 가장 처음 부분에서 `mov qword ptr [rax], offset Foo::`vftable'` 같은 코드로 객체의 첫 8바이트에 vtable 주소를 써넣는다. 자세한 내용은 REV-0444(vtable과 가상함수 호출 패턴) 참고.

스택에 만드는 지역 객체(`Foo obj;`)는 1단계(할당)가 없다 — 그냥 스택 프레임 안의 고정된 오프셋(`[rbp-0x20]` 등)을 `this`로 써서 바로 생성자를 호출한다.

### 소멸자 호출 시점
소멸자는 객체의 "수명이 끝나는" 시점에 컴파일러가 **자동으로** 삽입한다. 사람이 직접 `delete`를 쓴 게 아니어도, 스코프(`{}`)를 벗어나는 모든 지점에 소멸자 호출이 끼워진다.
- 지역 객체가 정상적으로 스코프를 벗어날 때 (함수 끝, 블록 끝)
- `delete ptr;` — `call Foo::~Foo` 다음에 `call operator delete`가 이어진다 (소멸 후 메모리 해제라는 순서에 주의)
- 함수가 `return`으로 여러 지점에서 빠져나갈 수 있다면, 각 `return` 지점마다 소멸자 호출이 각각 복제되어 삽입되는 경우가 많다 — 그래서 같은 소멸자를 호출하는 `CALL`이 함수 안에 여러 번 나타날 수 있다.
- 컴파일러 최적화가 예외 처리(스택 언와인딩)까지 고려하면 별도의 "unwind" 경로용 소멸자 호출도 존재하지만, 이는 일반적인 정적 디스어셈블리에서는 별도 테이블(`.pdata`/`.xdata`, `.eh_frame`)로 빠져 있어 눈에 잘 안 띈다.

**소멸 순서는 생성의 역순**이다. 멤버 변수가 A, B, C 순으로 생성자에서 초기화됐다면, 소멸자는 C, B, A 순으로 파괴한다. 배열이라면 마지막 원소부터 첫 원소 순으로 소멸자를 반복 호출한다.

### Name Mangling으로 생성자/소멸자 알아보기
컴파일러는 오버로딩을 지원하기 위해 함수 이름에 타입 정보를 인코딩(맹글링)한다. IDA/Ghidra는 이를 자동으로 사람이 읽기 쉬운 형태로 "디맹글링(demangle)"해서 보여주지만, 원본 심볼 문자열도 알아두면 도움이 된다.
- **MSVC (Windows)**: 생성자는 `??0`, 소멸자는 `??1`로 시작한다. 예: `??0Foo@@QEAA@XZ` → `Foo::Foo(void)`. 소멸자는 `??1Foo@@QEAA@XZ` → `Foo::~Foo(void)`.
- **Itanium ABI (Linux/GCC/Clang)**: 생성자는 `C1`(complete object constructor) 또는 `C2`(base object constructor), 소멸자는 `D1`/`D2`/`D0`으로 표시된다. 예: `_ZN3FooC1Ev` → `Foo::Foo()`, `_ZN3FooD1Ev` → `Foo::~Foo()`.

IDA는 View → Open subviews → Names 또는 함수 목록에서 이미 디맹글링된 이름을 보여주므로, 굳이 맹글링 규칙을 직접 해독할 일은 드물지만, 스트립된 바이너리나 심볼이 부분적으로만 남은 경우 원본 문자열 패턴(`??0`, `??1`, `C1Ev`, `D1Ev`)만 보고도 생성자/소멸자를 구분할 수 있다.

### 플래그와 레지스터 관점에서 보는 CALL 자체
생성자/소멸자 호출 자체는 그냥 `CALL`이므로 플래그를 바꾸지 않는다(REV-0071 참고). 다만 **생성자 내부**에서 멤버 초기화를 위해 실행되는 `MOV`, `LEA`, `ADD` 등의 명령은 각각 자신의 규칙대로 플래그에 영향을 줄 수 있다 — 그러나 이 플래그 변화는 생성자 로직상 보통 다음 조건 분기에 쓰이지 않으므로 무시해도 되는 경우가 대부분이다.

## 화면/코드에서 보이는 징후
```asm
; 힙 객체 생성 패턴 (Windows x64, MSVC)
mov     ecx, 18h            ; sizeof(Foo) = 24바이트
call    operator new         ; RAX = 새 메모리 주소
mov     rcx, rax             ; this = RAX (방금 할당받은 주소)
call    Foo::Foo             ; 생성자 호출, RCX 그대로 this로 전달
```
```asm
; 생성자 내부 첫 부분 (vtable 세팅)
Foo::Foo proc near
    mov     [rsp+8], rcx      ; this를 홈 스페이스에 저장 (REV-0450 참고)
    mov     rax, [rsp+8]
    mov     qword ptr [rax], offset Foo::`vftable'   ; vtable 포인터 세팅
    mov     rax, [rsp+8]
    mov     dword ptr [rax+8], 0   ; 멤버 변수 초기화 (예: int count = 0;)
    mov     rax, [rsp+8]
    ret
```
```asm
; 소멸자 호출 후 해제 패턴
mov     rcx, [rbp-0x18]      ; this
call    Foo::~Foo             ; 소멸자
mov     rcx, [rbp-0x18]
call    operator delete       ; 메모리 해제 (소멸자 다음 순서)
```

## 가장 먼저 할 것
1. 함수 이름이 클래스 이름과 같은지(`Foo::Foo`) 또는 `~`가 붙었는지(`Foo::~Foo`) 확인한다.
2. 이 함수 진입 직후 첫 번째 인자 레지스터(RCX 또는 RDI)가 어디서 왔는지 위쪽 코드를 거슬러 올라간다 — `call operator new`의 반환값(RAX)을 그대로 옮긴 것이라면 힙 객체 생성이 확실하다.
3. 함수 본문에서 `[this + offset]`에 값을 순서대로 쓰는 코드가 반복되면, 그 offset들이 클래스 멤버 변수의 레이아웃이다. offset 0에 포인터 크기(8바이트)를 쓰면 그건 대부분 vtable이다.

## 단계별 절차

**1) 생성자 식별**

IDA에서 함수 이름이 디맹글링되어 `Foo::Foo(int)`처럼 보이면 바로 생성자다. 스트립된 바이너리라면 `call` 대상 함수 안에서 `mov [rax], offset ...vftable...` 패턴이 있는지, 또는 `call operator new` 바로 다음에 오는 함수인지를 확인한다.

**2) this 포인터 추적**

생성자/소멸자 함수 내부에서 첫 줄 근처의 `mov [rsp+8], rcx`(Windows, 홈 스페이스 저장) 또는 그냥 `rdi`를 계속 사용하는 흐름(Linux)을 보면, 이후 `[rcx+N]` 또는 `[rdi+N]` 형태로 나오는 모든 접근이 "이 객체의 N번째 오프셋에 있는 멤버"라는 뜻이다. IDA에서 구조체(Structure)를 만들어 이 오프셋들에 이름을 붙이면(Local Types 또는 Structures 서브뷰) 이후 디컴파일 결과가 `this->count = 0;` 처럼 훨씬 읽기 쉬워진다.

**3) 소멸자 체인 추적**

함수가 끝나는 지점(에필로그 직전)에서 여러 `CALL`이 연달아 나오면, 각 CALL이 어떤 멤버 객체의 소멸자인지 하나씩 확인한다. 이때 this 값이 서로 다른 오프셋(`[rbp-0x18+8]`, `[rbp-0x18+0x10]` 등)이면 멤버 객체들이 순서대로 소멸되고 있는 것이다.

**4) new/delete 쌍 확인**

`operator new` 뒤에 생성자, `operator delete` 앞에 소멸자가 오는지 순서를 확인한다. 순서가 반대(delete가 소멸자보다 먼저)라면 해석을 잘못한 것이니 다시 확인한다.

## 명령어/단축키
- IDA: `Shift+F12`(문자열에서 클래스 이름 힌트 찾기), Local Types(`Shift+F1`)에서 구조체 정의, 함수 이름 위에서 `X`(Xrefs to)로 이 생성자가 어디서 호출되는지 확인, `N`으로 함수/멤버 오프셋 이름 붙이기
- Ghidra: Data Type Manager에서 구조체(Structure) 생성 후 함수 시그니처에 적용, Symbol Tree에서 디맹글링된 이름 확인
- x64dbg/GDB: 생성자 진입 지점에 브레이크포인트를 걸고 `this`(RCX/RDI) 값을 확인 → 이후 멤버 오프셋에 쓰이는 값을 하나씩 덤프해서 실제 초기값 확인

## 출력 해석
- `Foo::Foo(Foo *this)` 형태로 디컴파일되면 IDA/Ghidra가 이미 이걸 생성자로 인식했다는 뜻이다.
- `this->vfptr = &Foo::vftable;`(또는 비슷한 표현)이 생성자 첫 줄에 보이면 이 클래스가 최소 하나의 가상 함수를 가진다는 뜻 — REV-0444로 이동해서 vtable 구조를 마저 분석한다.
- 소멸자 안에서 `if (this->ptr) operator delete(this->ptr);` 같은 코드가 보이면, 이 클래스가 힙에 할당한 멤버(예: 내부 버퍼)를 직접 관리하고 있다는 뜻 — 이런 클래스는 리소스 해제 로직(더블 프리 취약점 등)을 살펴볼 가치가 있다.

## 흔한 실수
- `Foo::Foo`라는 이름만 보고 "특별한 명령어"가 있을 거라 생각하는 것 — 실제로는 그냥 `CALL`이고, 특별함은 오직 "this가 항상 첫 인자"라는 호출 규약 수준의 관례일 뿐이다.
- 생성자 내부의 `mov [rsp+8], rcx`(홈 스페이스에 this 저장, REV-0450 참고)를 의미 있는 로직으로 착각하는 것 — 이건 그냥 ABI가 요구하는 인자 스필이다.
- 소멸자가 여러 번 호출되는 것을 보고 "버그"라고 오해하는 것 — 함수에 `return`이 여러 개면 각 반환 경로마다 컴파일러가 소멸자 호출을 복제해서 삽입하는 게 정상이다.
- 생성/소멸 순서를 코드에 적힌 멤버 선언 순서가 아니라 생성자 초기화 리스트(initializer list)에 적힌 순서로 착각하는 것 — C++ 표준상 실제 초기화 순서는 **클래스에 멤버가 선언된 순서**이지 초기화 리스트에 쓴 순서가 아니다. 이는 소스가 있을 때 헷갈리기 쉬운 함정이며, 어셈블리 레벨에서는 이미 확정된 순서로 코드가 나온다.

## 막혔을 때 다음 체크
- 함수가 생성자인지 일반 멤버 함수인지 애매하면 → 첫 인자(this) 오프셋 0에 vtable 포인터를 쓰는지 확인한다. 쓴다면 생성자일 확률이 매우 높다(파괴자는 오히려 vtable을 "부모 클래스의" vtable로 되돌려 쓰기도 한다).
- 클래스 레이아웃(멤버 오프셋)을 전체적으로 파악하고 싶다면 → REV-0444(vtable과 가상함수 호출 패턴), REV-0445(RTTI 흔적 분석)로 이동해서 클래스 계층 구조까지 함께 재구성한다.
- this가 어느 레지스터로 전달되는지 헷갈리면 → REV-0106(SysV) 또는 REV-0122(Microsoft x64) 호출 규약을 다시 확인한다.

## 미니 예제

**예제 1 — 스택 지역 객체 (Linux x64)**
```c
// 원본 C++
void run() {
    Logger log("session.txt");
    log.write("start");
}
```
```asm
lea     rdi, [rbp-0x30]      ; this = 지역 객체 주소
lea     rsi, [rip+str_session] ; "session.txt"
call    Logger::Logger        ; 생성자
...
lea     rdi, [rbp-0x30]
call    Logger::write
lea     rdi, [rbp-0x30]
call    Logger::~Logger       ; 스코프(함수) 끝나기 직전 자동 소멸
```

**예제 2 — 힙 객체 (Windows x64)**
```c
Foo* p = new Foo(5);
delete p;
```
```asm
mov     ecx, 18h
call    operator new
mov     rcx, rax
mov     edx, 5
call    Foo::Foo             ; 생성자(int)
mov     [rbp+p], rax
...
mov     rcx, [rbp+p]
call    Foo::~Foo
mov     rcx, [rbp+p]
call    operator delete
```

**예제 3 — 멤버 객체 소멸 체인**
```c
class Container {
    A a; B b; C c;
};
```
```asm
Container::~Container proc near
    lea     rcx, [this+offset_c]
    call    C::~C
    lea     rcx, [this+offset_b]
    call    B::~B
    lea     rcx, [this+offset_a]
    call    A::~A
    ret
```
선언 순서가 `a, b, c`였다면 소멸은 `c, b, a` 역순으로 일어난다는 것을 CALL 순서로 확인할 수 있다.

## 관련 글
- REV-0444 — vtable과 가상함수 호출 패턴 분석
- REV-0445 — RTTI(런타임 타입 정보) 흔적 분석
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0106 — SysV AMD64 Calling Convention
- REV-0122 — Microsoft x64 Calling Convention
- REV-0450 — 함수 인자가 레지스터에서 스택으로 스필되는 패턴

## 출처/검증
- MSVC 이름 맹글링 규칙(`??0`/`??1` 생성자/소멸자 접두사): Microsoft C++ 데코레이션 이름 문서 기준.
- Itanium C++ ABI 이름 맹글링 규칙(`C1`/`C2`/`D1`/`D2`/`D0`): Itanium C++ ABI 공식 명세(mangling 섹션) 기준.
- 멤버 초기화 순서(선언 순서 기준, 초기화 리스트 순서 무관)는 ISO C++ 표준(class.base.init) 규칙 기준.
- 호출 규약(RCX/RDI가 this로 쓰임)은 각 플랫폼 ABI 문서(Microsoft x64 calling convention, System V AMD64 ABI) 기준.
