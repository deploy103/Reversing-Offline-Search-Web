---
id: REV-0763
title: "C++ 이름 맹글링(Name Mangling) 해석하기"
slug: "rev-0763-cpp-name-mangling-decoding"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["Name Mangling", "Itanium ABI 맹글링", "MSVC 맹글링", "c++filt", "undname", "_Z3fooii", "demangle"]
aliases: ["C++ 함수 이름 해석", "맹글된 함수 이름 읽는 법", "데맹글링(Demangling)"]
symptom_keywords: ["함수 이름이 _Z로 시작해서 못 읽겠음", "함수 이름이 ?로 시작함", "함수 이름에 @@YAH 같은 게 붙어있음", "C++ 바이너리 함수 이름이 이상함"]
source_ids: ["SRC-ITANIUM-CXX-ABI", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
C++는 함수 오버로딩과 네임스페이스/클래스를 지원하기 위해 컴파일러가 함수 이름에 매개변수 타입·소속 클래스·네임스페이스 정보를 인코딩한 "맹글된 이름"을 만들며, GCC/Clang은 `_Z`로 시작하는 Itanium C++ ABI 규칙을, MSVC는 `?`로 시작하는 자체 규칙을 쓰므로 두 규칙의 기본 문법만 익히면 스트립되지 않은 C++ 바이너리에서 함수 이름만 보고도 시그니처를 복원할 수 있다.

## 언제 검색해야 하나
- IDA/Ghidra Functions 목록에 `_Z3fooii`, `_ZN7MyClass6methodEi` 같은 이름이 잔뜩 보일 때
- Windows C++ 바이너리에서 `?foo@@YAHHH@Z`, `?method@MyClass@@QEAAXH@Z` 같은 `?`로 시작하는 이름이 보일 때
- IDA/Ghidra가 자동으로 데맹글해서 보여주는 이름(`MyClass::method(int)`)이 원래 맹글된 이름과 어떻게 대응되는지 직접 확인하고 싶을 때
- 오프라인 환경이라 온라인 데맹글러를 쓸 수 없어서 직접 손으로 맹글링 규칙을 해석해야 할 때

## 핵심 개념

### 왜 맹글링이 필요한가
C++는 `int foo(int)`와 `double foo(double)`처럼 이름은 같고 매개변수 타입이 다른 함수(오버로딩)를 허용한다. 하지만 링커(linker)는 심볼 이름 하나에 주소 하나만 대응시킬 수 있으므로, 컴파일러는 매개변수 타입과 소속 정보를 이름에 인코딩해서 서로 다른 고유 심볼을 만든다. 이 인코딩 규칙이 "이름 맹글링(Name Mangling)"이다. 컴파일러마다 규칙이 다르기 때문에 GCC로 컴파일한 오브젝트와 MSVC로 컴파일한 오브젝트는 서로 링크할 수 없다(ABI 비호환의 한 원인).

### Itanium C++ ABI (GCC/Clang, Linux/macOS 기본)
모든 맹글된 이름은 `_Z`로 시작한다. 기본 함수는 `_Z` + 이름 길이 + 이름 + 매개변수 타입 코드 순서로 인코딩된다.

```
_Z3fooii
  _Z      : 맹글링 시작 표시
  3foo    : 길이 3의 이름 "foo"
  i       : 첫 번째 매개변수 타입 int
  i       : 두 번째 매개변수 타입 int
```

즉 `_Z3fooii`는 `foo(int, int)`를 뜻한다. 주요 타입 코드는 다음과 같다.

| 코드 | 타입 | 코드 | 타입 |
|---|---|---|---|
| `v` | void | `b` | bool |
| `c` | char | `a` | signed char |
| `h` | unsigned char | `s` | short |
| `t` | unsigned short | `i` | int |
| `j` | unsigned int | `l` | long |
| `m` | unsigned long | `x` | long long |
| `y` | unsigned long long | `f` | float |
| `d` | double | `Pc` | char* (P=포인터 접두) |
| `PKc` | const char* (K=const 접두) | `Ss` | std::string (표준 축약형) |

네임스페이스나 클래스에 속한 함수는 `N`...`E`로 감싸고, 각 구성 요소마다 길이를 붙인다. 예를 들어 `_ZN7MyClass6methodEi`는 다음과 같이 해석된다.

```
_Z N 7MyClass 6method E i
  N ... E : 중첩된 이름(namespace/class::member) 시작/끝
  7MyClass : 길이 7의 클래스 이름 "MyClass"
  6method  : 길이 6의 메서드 이름 "method"
  i        : 매개변수 int 하나
```

→ `MyClass::method(int)`. 생성자는 `C1`/`C2`(complete/base object constructor), 소멸자는 `D1`/`D2`로 인코딩된다(`_ZN7MyClassC1Ev`는 `MyClass::MyClass()`).

### MSVC 맹글링 (Visual C++)
MSVC는 `?`로 시작하고 `@@`로 구간을 구분하며, 이름은 **뒤에서부터 읽는** 역순 표기를 쓰는 것이 특징이다.

```
?foo@@YAHHH@Z
  ?foo@@  : 함수 이름 "foo" (전역 함수, 소속 없음)
  YA      : 호출 규약 __cdecl
  H       : 반환 타입 int
  HH      : 매개변수 int, int
  @Z      : 매개변수 목록 종료
```

→ `int __cdecl foo(int, int)`. 클래스 멤버 함수는 `?method@MyClass@@QEAAXH@Z` 형태로, 클래스 이름이 함수 이름 뒤에(`@MyClass@@`) 붙는다. 주요 코드는 다음과 같다.

| 코드 | 의미 | 코드 | 의미 |
|---|---|---|---|
| `H` | int | `X` | void |
| `N` | double | `M` | float |
| `D` | char | `E` | unsigned char |
| `_N` | bool | `PEAH` | int* (64비트, E=64비트 포인터) |
| `PEBD` | const char* | `YA` | __cdecl |
| `QEAA` | public 비-const 멤버 함수(64비트 this) | `QEBA` | public const 멤버 함수 |

### extern "C"는 맹글링을 하지 않는다
`extern "C"`로 선언된 함수는 C 방식 그대로 이름이 유지되어 맹글링되지 않는다. 그래서 C++ 바이너리에서도 `main`, `printf` 같은 이름은 그대로 보이는 반면, C++로 작성된 사용자 클래스 메서드만 맹글링된 형태로 나타난다.

## 화면/코드에서 보이는 징후
- IDA/Ghidra Functions 목록에 `_Z`로 시작하는 긴 이름, 또는 `?`로 시작하고 `@@`가 여러 번 들어간 이름이 보인다.
- IDA는 기본적으로 데맹글된 이름을 "Demangled name" 필드에 별도로 보여주고(Options → Demangled names), Ghidra는 Listing/Decompile 창에 자동으로 데맹글된 이름을 표시한다.
- 오버로딩된 함수(`foo(int)`와 `foo(double)`)가 서로 다른 맹글된 이름(`_Z3fooi`, `_Z3food`)으로 별개 심볼이 되어 있다.

## 가장 먼저 할 것
이름이 `_Z`로 시작하면 Itanium ABI(GCC/Clang), `?`로 시작하면 MSVC 규칙임을 먼저 확인한다. 그다음 도구의 자동 데맹글 기능(IDA Demangled name, Ghidra 자동 표시)을 켜서 정답을 먼저 확인하고, 필요하면 이 문서의 표로 직접 검산한다.

## 단계별 절차
1. 맹글된 이름의 첫 글자(`_Z` vs `?`)로 컴파일러 계열을 판별한다.
2. `c++filt` (GNU binutils, Linux 오프라인 환경에도 대개 포함) 또는 Windows SDK의 `undname.exe`로 자동 데맹글해 정답을 확인한다.
3. IDA는 `Options → Demangled names → Name definitions`에서 표시 형식(짧게/전체)을 조정할 수 있고, Ghidra는 Listing에서 함수 이름이 자동으로 데맹글된 형태로 나타난다(원본 맹글 이름은 Symbol Table에서 확인 가능).
4. 자동 도구 없이 손으로 읽어야 한다면, 위 표를 참고해 길이 접두 숫자로 이름 구간을 하나씩 잘라내며 안쪽에서 바깥쪽으로(Itanium) 또는 지정된 순서대로(MSVC) 해석한다.
5. 데맹글된 시그니처를 확인했으면 IDA는 `Y`(REV-0148), Ghidra는 함수 시그니처 편집으로 반환 타입과 매개변수 타입을 정확히 지정해 이후 디컴파일 가독성을 높인다.
6. 같은 이름이 여러 개(오버로딩) 있다면 매개변수 타입 코드로 서로 구분해서 혼동하지 않도록 REV-0147/REV-0161 방식으로 별도 주석을 남긴다.

## 명령어/단축키
```bash
echo _Z3fooii | c++filt
# 출력: foo(int, int)

echo _ZN7MyClass6methodEi | c++filt
# 출력: MyClass::method(int)
```
Windows: `undname.exe ?foo@@YAHHH@Z` (Visual Studio Developer Command Prompt에 포함). IDA: `Options → Demangled names`. Ghidra: Listing 창에서 함수 이름 더블클릭 시 원본/데맹글 이름 모두 확인 가능.

## 출력 해석
- `c++filt`/`undname` 결과가 비정상적으로 잘리거나 실패하면, 이름이 완전히 복사되지 않았거나(중간에 공백/개행 포함) 두 컴파일러 규칙이 섞여 있는(드물지만 혼합 빌드) 경우일 수 있다.
- Itanium 이름에서 `C1`/`C2`/`C3`, `D0`/`D1`/`D2`는 모두 생성자/소멸자의 변형(complete object, base object, deleting destructor 등)이며 기능적으로는 거의 같은 생성자/소멸자로 취급해도 무방하다.
- MSVC 이름에서 `QEAA`(public, 64비트 this)와 `AEAA`(private)의 차이는 접근 제어자 정보이므로, 클래스 구조를 추정할 때 REV-0765에서 상속/캡슐화 단서로 활용할 수 있다.

## 흔한 실수
- `_Z`와 `?` 규칙을 섞어서 해석하려는 것 — 두 체계는 완전히 다른 별개의 인코딩이므로 절대 서로 대입해서 읽으면 안 된다.
- 길이 접두 숫자를 잘못 세어서 이름 구간을 엉뚱하게 잘라내는 것 — 반드시 숫자만큼 정확히 문자를 세어 잘라야 한다.
- 데맹글된 이름을 확인하고 나서 그 함수의 클래스 구조나 상속 관계까지 이 문서만으로 다 알아냈다고 착각하는 것 — 이름 해석은 시작일 뿐이고, 실제 클래스 구조 추정은 REV-0764/REV-0765에서 이어서 다룬다.
- IDA/Ghidra가 자동으로 데맹글해 준 이름만 보고 원본 맹글 이름을 확인하지 않는 것 — 자동 데맹글이 실패하거나 축약 표시될 때는 원본 이름을 직접 봐야 정확하다.

## 막혔을 때 다음 체크
- 데맹글된 이름으로 클래스의 멤버/필드 구조를 추정하고 싶다면 → REV-0764(데맹글된 이름으로 클래스 구조 추정하기)
- 여러 클래스 이름이 보이는데 상속 관계까지 알고 싶다면 → REV-0765(IDA/Ghidra에서 클래스 계층(상속) 추정하기)
- 맹글된 이름에 `vtable for`, `RTTI` 관련 접두사가 보인다면 → REV-0444(vtable과 가상함수 호출 패턴 분석), REV-0445(RTTI 흔적 분석)
- 이름 자체가 `_Z`도 `?`도 아니고 이상한 형태라면 → REV-0766(익명 함수/람다가 바이너리에서 보이는 방식)에서 람다/컴파일러 합성 이름 패턴 확인

## 미니 예제
스트립되지 않은 Linux ELF C++ 바이너리에서 다음 심볼을 발견했다고 하자.

```
_ZN6VaultC1Ev
_ZN6Vault8unlockedEv
_ZN6Vault6verifyEPKc
```

`c++filt`로 각각 데맹글하면:

```
Vault::Vault()
Vault::unlocked() const   (또는 non-const, 시그니처 세부는 실제 맹글에 따라 다름)
Vault::verify(char const*)
```

이로써 `Vault`라는 클래스가 존재하고, 생성자(`Vault()`), 잠금 상태 확인 메서드(`unlocked`), 그리고 `char const*` 하나를 받는 `verify` 메서드(사용자 입력 문자열을 검증하는 함수일 가능성이 매우 높음)를 갖는다는 것을 함수 내부를 하나도 읽지 않고 이름만으로 파악할 수 있다. 다음 단계는 `verify` 함수를 REV-0163~0165 방식으로 직접 열어보는 것이다.

## 관련 글
- REV-0764 — 데맹글된 이름으로 클래스 구조 추정하기
- REV-0765 — IDA/Ghidra에서 클래스 계층(상속) 추정하기
- REV-0444 — vtable과 가상함수 호출 패턴 분석
- REV-0445 — RTTI(런타임 타입 정보) 흔적 분석
- REV-0446 — C++ 생성자/소멸자 호출 패턴 읽기
- REV-0766 — 익명 함수/람다가 바이너리에서 보이는 방식

## 출처/검증
- Itanium C++ ABI 이름 맹글링 규칙(`_Z` 접두사, 타입 인코딩, `N`...`E` 중첩 이름, `C1`/`C2`/`D0`/`D1`/`D2`)은 Itanium C++ ABI 공식 명세(Name Mangling 섹션) 기준.
- MSVC 이름 데코레이션(`?`, `@@`, 호출 규약/타입 코드, `undname.exe`) 관련 내용은 Microsoft Learn의 Decorated Names 공식 문서 기준.
- `c++filt`(GNU binutils) 사용법은 binutils 공식 매뉴얼 기준으로 검증했다.
