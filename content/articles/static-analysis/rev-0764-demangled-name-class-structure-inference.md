---
id: REV-0764
title: "데맹글된 이름으로 클래스 구조 추정하기"
slug: "rev-0764-demangled-name-class-structure-inference"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["클래스 구조 추정", "this 포인터 오프셋", "생성자 소멸자 식별", "operator overload 데맹글", "멤버 필드 추정", "구조체 생성 Ghidra IDA"]
aliases: ["데맹글된 이름으로 멤버 함수 그룹화", "클래스 필드 레이아웃 추정", "this+offset로 필드 찾기"]
symptom_keywords: ["ClassName:: 이름이 여러 개 보이는데 필드가 뭔지 모름", "생성자 소멸자 구분이 안 됨", "this 포인터가 뭘 가리키는지 모름", "operator== 이름을 처음 봄"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-HEXRAYS-DOCS", "SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
REV-0763으로 이름을 데맹글해서 `ClassName::method(...)` 형태를 얻었다면, 같은 `ClassName::`으로 시작하는 함수들을 모아 생성자/소멸자/연산자/일반 메서드로 분류하고 각 메서드가 `this+오프셋`으로 어떤 메모리를 읽고 쓰는지 교차 비교하면 소스 코드 없이도 그 클래스의 필드 레이아웃(구조체)을 상당히 정확하게 복원할 수 있다.

## 언제 검색해야 하나
- 데맹글된 함수 목록에 `Vault::Vault()`, `Vault::unlock(char const*)`, `Vault::~Vault()`처럼 같은 클래스 이름이 반복되는데, 그 클래스가 실제로 어떤 멤버 변수를 갖는지 알고 싶을 때
- 디컴파일된 메서드 안에서 `*(int *)(this + 0x8)`, `*(char **)(this + 0x10)` 같은 코드가 반복적으로 나오는데 이게 무슨 필드인지 정리가 안 될 때
- `operator==`, `operator[]`, `operator<<` 같은 연산자 오버로드 이름을 만나서 이게 일반 함수와 뭐가 다른지 헷갈릴 때
- 클래스 구조를 IDA Local Types나 Ghidra Structure Editor에 실제 구조체로 등록해서 이후 모든 메서드의 디컴파일 가독성을 한 번에 높이고 싶을 때

## 핵심 개념

### 데맹글된 이름을 클래스별로 그룹화한다
REV-0763에서 얻은 데맹글된 이름들을 `ClassName::` 접두사 기준으로 모으면, 그 클래스가 갖는 멤버 함수 전체 목록이 자연스럽게 만들어진다. 이 목록 안에서 함수는 다음과 같이 분류된다.

| 패턴 | 의미 |
|---|---|
| `ClassName::ClassName(...)` | 생성자(매개변수 유무로 기본/복사/변환 생성자 구분) |
| `ClassName::~ClassName()` | 소멸자 |
| `ClassName::operator=(...)` | 대입 연산자(복사/이동 대입) |
| `ClassName::operator==`, `operator<`, `operator[]`, `operator<<` 등 | 연산자 오버로드 — 이름은 특수하지만 첫 인자가 암묵적 `this`라는 점은 일반 메서드와 동일 |
| `ClassName::method(...) const` | const 메서드 — 멤버 변수를 읽기만 하고 수정하지 않는다는 설계 의도를 알려주는 단서 |
| `static` 표시 없이 나열되지만 첫 인자가 `this`가 아닌 경우 | 정적(static) 메서드 — 특정 인스턴스에 종속되지 않음 |

### `this` 포인터와 필드 오프셋
비-static 멤버 함수는 컴파일러가 내부적으로 첫 번째 매개변수로 `this` 포인터를 암묵적으로 전달한다(Itanium ABI와 MSVC 모두 x64에서 사실상 정수 레지스터로 전달, System V는 RDI, Windows x64는 RCX). 디컴파일러는 이를 `this` 또는 `param_1`으로 보여준다. 여러 메서드에서 `this + N` 형태로 접근하는 오프셋을 모으면 다음과 같이 필드 목록을 재구성할 수 있다.

```
Vault::Vault()          this+0x0 = 0 (bool/int, 초기화)     -> 아마 "locked" 플래그
Vault::unlock(char*)    this+0x0 = 1, this+0x8 = malloc 결과 -> this+0x8은 char* 포인터 필드
Vault::verify(char*)    this+0x0 읽기만, this+0x8 읽어서 strcmp
```

이 세 함수만 봐도 `Vault`는 최소한 `{ int locked; char *secret; }` 형태의 필드를 가진 클래스라는 결론을 낼 수 있다. **오프셋이 겹치지 않고 접근 방식(읽기/쓰기, 크기)이 일관되면** 해당 오프셋을 하나의 필드로 확정하고, 크기(1/4/8바이트)와 타입(정수/포인터/부동소수점 명령어 사용 여부)까지 함께 기록한다.

### vtable 포인터는 항상 this+0x0(단일 상속 기준)
가상 함수가 하나라도 있는 클래스는 객체 맨 앞(`this+0x0`)에 vtable 포인터가 숨어 있다(REV-0444 참고). 생성자 초반에 `*(void**)this = &vtable_for_ClassName` 같은 대입이 보이면, 그 클래스는 가상 함수를 가진 폴리모픽(polymorphic) 클래스이고, 실제 사용자 필드는 `this+0x8`(64비트 기준)부터 시작한다는 뜻이다. 이를 놓치면 필드 오프셋을 8바이트씩 밀려서 잘못 해석하게 된다.

## 화면/코드에서 보이는 징후
- 같은 클래스 이름 접두사(`ClassName::`)를 가진 함수가 5개 이상 모여 있다.
- 디컴파일 결과에 `this`, `param_1`(암묵적 this로 추정되는 첫 인자), `*(int *)(this + 8)` 같은 포인터 연산이 반복된다.
- 생성자로 추정되는 함수 초입에 `this+0x0`에 특정 주소(함수 포인터 배열의 시작 주소)를 대입하는 코드가 보인다(vtable 셋업, REV-0444).
- `operator` 키워드가 포함된 데맹글 이름이 보인다.

## 가장 먼저 할 것
REV-0763으로 전체 함수 이름을 데맹글한 뒤, 텍스트 편집기나 표(REV-0770 노트 방식)에 `클래스 이름 → 메서드 목록`으로 먼저 정리한다. 그다음 생성자부터 열어 `this+0x0`에 무엇이 들어가는지 확인하는 것이 가장 확실한 시작점이다.

## 단계별 절차
1. 데맹글된 함수 이름 전체를 클래스 이름 기준으로 그룹화한다(같은 접두사끼리 모음).
2. 생성자(`ClassName::ClassName`)를 가장 먼저 열어, `this+0x0`부터 대입되는 값들을 순서대로 기록한다.
3. vtable 셋업 코드(REV-0444의 패턴)가 보이면 첫 8바이트(64비트)는 vtable 포인터로 확정하고, 실제 필드는 그다음 오프셋부터 센다.
4. 나머지 메서드를 순서대로 열어 `this+오프셋` 접근을 모두 기록하고, 오프셋·크기·읽기/쓰기 여부·추정 타입을 표로 정리한다.
5. 소멸자(`~ClassName`)를 확인해 `free`/`delete` 호출 대상이 어떤 필드인지 보면, 그 필드가 포인터(동적 할당된 자원)라는 확증을 얻을 수 있다.
6. 정리된 필드 표를 바탕으로 IDA Local Types(`Structures` 서브뷰, 단축키 없이 Local Types 창에서 `Insert`) 또는 Ghidra Structure Editor로 실제 구조체(`struct Vault { ... }`)를 만든다.
7. 만든 구조체를 각 메서드의 `this` 매개변수 타입으로 지정(IDA `Y`/REV-0148, Ghidra `Edit Function Signature`)하면, 이후 모든 메서드의 디컴파일 결과가 `this->locked`, `this->secret`처럼 훨씬 읽기 쉬워진다.

## 명령어/단축키
- IDA: Local Types 창 열기(`Shift+F1`), 구조체 추가는 창 안에서 `Insert`, 함수 인자에 구조체 포인터 타입 지정은 변수 선택 후 `Y`
- Ghidra: `Data Type Manager` → 우클릭 `New → Structure`로 필드 추가, 함수 시그니처 편집은 함수 이름에서 우클릭 `Edit Function Signature`
- 공통: 클래스 필드 표는 텍스트 파일로 별도 보관(REV-0770 참고)해 두면 재분석 시 바로 재사용 가능

## 출력 해석
- 서로 다른 메서드에서 같은 오프셋에 크기가 다른 접근(한 곳은 4바이트 `int`, 다른 곳은 8바이트 `long`)이 보이면, 실제로는 그 근처에 필드가 두 개 이상 있는데 오프셋 계산을 잘못했거나 union처럼 겹쳐 쓰는 특수한 경우이니 Hex View(REV-0162)로 실제 크기를 재검증해야 한다.
- 생성자에서 `malloc`/`new`(연산자 `operator new`로 나타남) 호출 결과를 특정 오프셋에 저장하면, 그 필드는 포인터이고 소멸자에서 대응하는 `free`/`delete`(`operator delete`)가 있는지 짝을 맞춰 확인해야 자원 관리 패턴을 놓치지 않는다.
- const 메서드로 표시된 함수 안에서 `this+오프셋`에 값을 **쓰는** 코드가 있다면 `mutable` 필드이거나, 데맹글 결과를 잘못 읽었을 가능성이 있으므로 원본 맹글 이름을 재확인한다.

## 흔한 실수
- 오버로딩된 생성자(기본 생성자 vs 복사 생성자)를 같은 함수로 착각해서 필드 초기화 순서를 뒤섞어 기록하는 것 — 반드시 매개변수 타입까지 구분해서 별도로 취급해야 한다.
- vtable 포인터(this+0x0)를 사용자 정의 필드로 착각해서 전체 오프셋을 8바이트씩 밀려 해석하는 것.
- `this+오프셋` 접근이 하나만 발견됐다고 바로 필드로 확정하는 것 — 최소 2개 이상의 메서드에서 같은 오프셋·같은 크기로 일관되게 접근하는지 교차 확인해야 신뢰도가 높다.
- 정적 메서드(첫 인자가 `this`가 아님)를 인스턴스 메서드와 같은 방식으로 분석해 존재하지 않는 필드 접근을 억지로 찾으려 하는 것.

## 막혔을 때 다음 체크
- 맹글된 이름 자체를 아직 데맹글하지 못했다면 → REV-0763(C++ 이름 맹글링 해석하기)
- 클래스 여러 개 사이의 상속 관계까지 알아내고 싶다면 → REV-0765(IDA/Ghidra에서 클래스 계층(상속) 추정하기)
- vtable 포인터 셋업이나 가상 함수 호출 패턴 자체가 헷갈린다면 → REV-0444(vtable과 가상함수 호출 패턴 분석)
- 생성자/소멸자 호출 순서(멤버 객체 초기화 순서 등)가 헷갈린다면 → REV-0446(C++ 생성자/소멸자 호출 패턴 읽기)
- 필드 표를 실제 구조체로 등록하는 IDA/Ghidra 조작법을 더 자세히 알고 싶다면 → REV-0148(IDA Y로 타입 지정하기), REV-0161(Ghidra Rename과 Data Type 수정)

## 미니 예제
데맹글된 이름이 다음과 같이 나왔다고 하자.

```
Vault::Vault()
Vault::unlock(char const*)
Vault::verify(char const*) const
Vault::~Vault()
```

각 함수를 열어 `this+오프셋` 접근을 기록하면:

```
Vault::Vault()          this+0x0 = 0                (4바이트, int로 추정 -> locked)
Vault::unlock(char*)    this+0x0 = 1
                        this+0x8 = strdup(param_2)  (8바이트 포인터 -> secret)
Vault::verify(char*)    this+0x0 읽기
                        this+0x8 읽어서 strcmp(this+0x8, param_2)
Vault::~Vault()         free(this+0x8)
```

이로부터 다음 구조체를 확정할 수 있다.

```c
struct Vault {
    int   locked;   // +0x0
    char *secret;   // +0x8 (8바이트 정렬 패딩 포함)
};
```

이 구조체를 IDA/Ghidra에 등록하고 네 메서드 모두의 `this` 타입으로 지정하면, 이후 디컴파일 결과는 `this->locked`, `this->secret`으로 바로 표시되어 훨씬 읽기 쉬워진다.

## 관련 글
- REV-0763 — C++ 이름 맹글링(Name Mangling) 해석하기
- REV-0765 — IDA/Ghidra에서 클래스 계층(상속) 추정하기
- REV-0444 — vtable과 가상함수 호출 패턴 분석
- REV-0446 — C++ 생성자/소멸자 호출 패턴 읽기
- REV-0148 — IDA Y로 타입 지정하기
- REV-0161 — Ghidra Rename과 Data Type 수정

## 출처/검증
- Itanium C++ ABI의 객체 메모리 레이아웃(this 포인터, vtable 포인터 위치, 생성자/소멸자 변형)은 Itanium C++ ABI 공식 명세(Object Layout 섹션) 기준.
- MSVC의 this 전달 방식(x64에서 RCX 사용)과 멤버 함수 호출 규약은 Microsoft Learn의 x64 Calling Convention 및 C++ 클래스 레이아웃 관련 공식 문서 기준.
- IDA Local Types/구조체 생성, Ghidra Structure Editor/Data Type Manager 사용법은 각 도구의 공식 문서(Hex-Rays User Guide, Ghidra Help) 기준.
