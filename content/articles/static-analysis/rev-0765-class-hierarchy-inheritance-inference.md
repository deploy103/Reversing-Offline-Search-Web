---
id: REV-0765
title: "IDA/Ghidra에서 클래스 계층(상속) 추정하기"
slug: "rev-0765-class-hierarchy-inheritance-inference"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["C++ 상속 추정", "vtable 접두사 비교", "base class constructor 호출", "다중 상속 추정", "RTTI ClassHierarchyDescriptor", "가상 상속 vtordisp"]
aliases: ["클래스 상속 관계 복원", "vtable로 상속 트리 만들기", "다중 상속 식별"]
symptom_keywords: ["생성자 안에서 다른 클래스 생성자를 호출함", "vtable 앞부분이 서로 비슷함", "this가 두 개인 것처럼 보임", "다중 상속인지 합성인지 구분이 안 됨"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-HEXRAYS-DOCS", "SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
클래스 간 상속 관계는 소스 코드 없이도 (1) 파생 클래스 생성자 초입에서 같은 `this`로 기반 클래스 생성자를 호출하는 패턴, (2) 두 클래스의 vtable 앞부분이 그대로 겹치는 패턴, (3) RTTI가 살아있다면 `ClassHierarchyDescriptor`/`BaseClassArray`(MSVC)나 `__si_class_type_info`/`__vmi_class_type_info`(Itanium) 구조체를 직접 읽는 방법으로 정적 분석만으로 복원할 수 있다.

## 언제 검색해야 하나
- REV-0764로 여러 클래스의 필드 구조까지는 정리했는데, 클래스 A와 클래스 B가 서로 무관한지 상속 관계인지 판단이 안 될 때
- 어떤 클래스의 생성자 안에서 `this` 포인터(또는 `this`+고정 오프셋)를 그대로 넘겨 다른 클래스처럼 보이는 함수를 호출하는 코드가 보일 때
- 두 클래스의 vtable을 나란히 봤을 때 앞부분 함수 포인터들이 완전히 똑같이 겹칠 때
- RTTI 관련 문자열(`.?AVBase@@`, `St9type_info` 등)이나 구조체가 남아있어서 이를 직접 해석해 상속 트리를 확정하고 싶을 때

## 핵심 개념

### 단서 1 — 파생 클래스 생성자의 기반 클래스 생성자 호출
C++ 컴파일러는 파생 클래스 생성자 본문 맨 앞에 반드시 기반 클래스 생성자 호출 코드를 삽입한다(사용자가 이니셜라이저 리스트에 명시하지 않아도 기본 생성자가 자동 호출됨). 정적 분석에서는 이렇게 구분한다.

- **상속(is-a) 신호**: `Derived::Derived()` 안에서 `Base::Base(this)`처럼 **같은 `this` 값**을 그대로 넘겨 다른 클래스의 생성자를 호출하고, 그 직후 vtable 포인터를 `Derived`의 vtable로 덮어쓰는(overwrite) 코드가 이어진다.
- **합성(has-a, 멤버 객체) 신호**: `Outer::Outer()` 안에서 `Member::Member(this + N)`처럼 `this`에 **고정 오프셋을 더한 주소**를 넘겨 호출한다. 이 경우는 상속이 아니라 "멤버 변수로 다른 클래스의 객체를 갖고 있다"는 뜻이다.

이 둘을 구분하는 것이 상속 추정에서 가장 흔히 틀리는 지점이므로, 반드시 넘겨지는 주소가 `this` 그대로인지, `this+오프셋`인지부터 확인해야 한다.

### 단서 2 — vtable 앞부분 비교(단일 상속)
가상 함수가 있는 클래스는 객체 앞에 vtable 포인터를 갖는다(REV-0444). 클래스 `Derived`가 클래스 `Base`를 상속하면, `Derived`의 vtable은 **`Base`의 vtable과 앞부분 항목이 완전히 동일하고, 오버라이드한 가상 함수만 다른 주소로 교체되며, 새로 추가한 가상 함수는 뒤에 이어 붙는다.** 즉 두 vtable을 나란히 놓고 앞에서부터 비교했을 때 일치하는 구간이 길수록 상속 관계일 가능성이 크다.

### 단서 3 — 다중 상속과 여러 개의 vtable 포인터
클래스가 둘 이상의 기반 클래스를 다중 상속하면, 생성자 안에서 `this+0x0`뿐 아니라 `this+0x10`(다른 기반 클래스의 서브객체 시작 위치) 같은 **다른 오프셋에도 별도의 vtable 포인터**를 설정하는 코드가 나타난다. 이는 "이 클래스는 하나의 객체 안에 서로 다른 두 개의 vtable을 갖고 있다"는 뜻이며, 다중 상속의 명확한 정적 증거다.

### 단서 4 — RTTI가 살아있다면 구조체를 직접 해석
스트립되지 않고 RTTI(`/GR`, `-frtti`, 기본 활성화가 흔함)가 남아있다면 굳이 패턴 추론을 하지 않고 구조체를 직접 읽을 수 있다.

- **MSVC**: vtable 바로 앞(`vtable - 0x8`)에 `RTTICompleteObjectLocator` 포인터가 있고, 이 구조체가 `ClassHierarchyDescriptor`를 가리키며, 그 안의 `BaseClassArray`가 모든 기반 클래스 목록(다중/가상 상속 포함)을 순서대로 나열한다.
- **Itanium(GCC/Clang)**: `type_info` 계열 구조체가 상속 형태에 따라 `__class_type_info`(상속 없음), `__si_class_type_info`(단일 상속, 기반 클래스 `type_info`를 가리키는 필드 하나 추가), `__vmi_class_type_info`(다중/가상 상속, 기반 클래스 배열 포함)로 나뉜다. vtable에서 `-0x8`(64비트 기준, this 조정 값 다음) 위치에 이 `type_info` 포인터가 있다.

이 구조체들은 데맹글된 이름(`typeinfo for ClassName`, `.?AVClassName@@`)으로도 식별 가능하므로 REV-0763/0764와 함께 교차 확인한다.

### 단서 5 — 가상 상속(virtual inheritance)의 복잡성
가상 상속(`class C : public virtual Base`)은 vtable 앞부분 비교만으로는 잘 드러나지 않고, MSVC에서는 `vtordisp` 썽크(this 포인터 보정 코드가 앞에 붙은 함수)가, Itanium에서는 vtable에 가상 기반 클래스 오프셋(vbase offset) 항목이 추가된다. 이는 상당히 고급 패턴이므로, 일반 CTF crackme에서는 드물다는 점을 감안하고 우선순위를 낮게 둬도 된다.

## 화면/코드에서 보이는 징후
- 생성자로 추정되는 함수 안에서 첫 줄 근처에 다른 함수 호출이 있고, 그 인자가 자신의 `this`와 동일한 레지스터/값이다.
- 서로 다른 두 클래스의 vtable을 Hex View나 IDA의 데이터 창에서 나란히 봤을 때 앞쪽 몇 개 항목의 주소가 완전히 같다.
- 생성자 안에서 `this+0x0`과 `this+0x10`처럼 서로 다른 오프셋에 각각 다른 vtable 주소를 대입하는 코드가 두 번 이상 나온다.
- `.rodata`/`.rdata`에서 `RTTICompleteObjectLocator`, `_ZTI`(typeinfo), `_ZTV`(vtable) 접두사가 붙은 심볼이 남아있다.

## 가장 먼저 할 것
상속 관계를 의심하는 두 클래스의 생성자를 나란히 열어, 한쪽 생성자 초반에 다른 클래스 생성자로 보이는 호출이 있는지, 그리고 그 호출에 전달되는 주소가 `this` 그대로인지부터 확인한다.

## 단계별 절차
1. REV-0764로 정리한 클래스 목록 중 생성자 크기가 유난히 작고 다른 클래스 생성자 호출로 시작하는 것들을 후보로 고른다.
2. 그 호출에 전달되는 주소가 `this` 그대로면 상속(단일 상속) 후보, `this+오프셋`이면 멤버 객체(합성) 후보로 분류한다.
3. 상속 후보로 분류된 두 클래스의 vtable을 나란히 놓고 처음 N개 함수 포인터가 일치하는지 비교한다(IDA/Ghidra에서 vtable 데이터 배열을 Xref로 열어 주소를 나열).
4. 생성자 안에서 `this`에 서로 다른 오프셋으로 vtable을 두 번 이상 대입하면 다중 상속으로 결론짓고, 각 오프셋을 별도의 기반 클래스 서브객체로 기록한다.
5. RTTI 구조체가 남아있다면 `RTTICompleteObjectLocator`/`ClassHierarchyDescriptor`/`BaseClassArray`(MSVC) 또는 `__si_class_type_info`/`__vmi_class_type_info`(Itanium)를 직접 따라가 기반 클래스 이름을 확정한다.
6. 확정한 상속 관계를 화살표 표기(`Derived -> Base`)로 정리해 REV-0770 방식의 노트에 남긴다.

## 명령어/단축키
- IDA: vtable 데이터 배열은 Data 정의 후 Xref(`X`)로 각 슬롯이 어느 함수를 가리키는지 확인, RTTI 구조체는 `.rdata`에서 수동으로 구조체 오버레이(Local Types에 `RTTICompleteObjectLocator` 정의 후 적용)
- Ghidra: vtable은 Data Type Manager에서 포인터 배열로 정의, RTTI 관련 구조체도 Structure Editor로 직접 정의 가능(Ghidra 최신 버전은 일부 MSVC RTTI를 자동 인식)
- 공통: 클래스 간 비교는 두 vtable 주소를 각각 별도 창(IDA는 여러 Hex View, Ghidra는 여러 Listing 탭)에 열어 나란히 대조

## 출력 해석
- vtable 앞부분이 정확히 일치하고 뒤에 새 항목이 추가된 형태면 "단일 상속 + 신규 가상함수 추가"로 해석한다.
- vtable 앞부분 일부가 다른 주소로 교체됐다면 그 위치의 가상 함수를 파생 클래스가 오버라이드했다는 뜻이다.
- 생성자에서 두 개의 서로 다른 vtable 포인터 대입이 서로 다른 `this` 오프셋에 이뤄지면 다중 상속, 같은 오프셋에 순차적으로 다른 값이 두 번 대입되면(먼저 기반 클래스 vtable, 나중에 파생 클래스 vtable) 이는 단일 상속에서 흔히 보이는 "생성 중 임시 vtable" 패턴이다.

## 흔한 실수
- `this+오프셋`을 넘기는 멤버 객체 초기화 호출을 상속으로 오인하는 것 — 반드시 넘겨지는 주소가 `this` 그대로인지 확인해야 한다.
- vtable 앞부분이 우연히 몇 개 겹친다고 바로 상속으로 단정하는 것 — 최소 여러 개의 연속된 항목이 일치해야 신뢰도가 있으며, 함수 자체의 내용(단순 empty 함수 등)이 겹치는 우연의 일치일 수도 있으니 REV-0444로 각 슬롯이 실제로 다른 함수인지 재확인한다.
- 가상 상속의 `vtordisp` 썽크를 일반 가상 함수로 착각해 상속 구조를 잘못 해석하는 것 — 함수 프롤로그에서 `this` 값을 보정하는 코드(예: `sub rcx, N` 후 다른 함수로 점프)가 보이면 이는 가상 상속 관련 썽크일 가능성을 의심한다.
- RTTI 구조체를 발견하고도 굳이 패턴 추론만으로 상속을 재구성하려 애쓰는 것 — RTTI가 살아있으면 직접 읽는 것이 훨씬 빠르고 정확하다.

## 막혔을 때 다음 체크
- vtable 구조와 가상 함수 호출 코드 패턴 자체가 헷갈린다면 → REV-0444(vtable과 가상함수 호출 패턴 분석)
- RTTI 구조체 자체를 어떻게 찾고 읽는지 기초가 필요하다면 → REV-0445(RTTI 흔적 분석)
- 클래스 필드 오프셋을 먼저 정리하고 싶다면 → REV-0764(데맹글된 이름으로 클래스 구조 추정하기)
- 생성자/소멸자 호출 순서 자체가 헷갈린다면 → REV-0446(C++ 생성자/소멸자 호출 패턴 읽기)
- 추정한 상속 트리를 여러 클래스에 걸쳐 노트로 정리하고 싶다면 → REV-0770(여러 함수에 걸친 로직을 하나의 흐름으로 정리하는 노트 작성법)

## 미니 예제
`Derived::Derived()` 디컴파일 결과가 다음과 같다고 하자.

```c
void Derived::Derived(Derived *this) {
    Base::Base((Base *)this);          // this 그대로 전달 -> 상속 신호
    *(void **)this = &Derived::vtable; // vtable을 Derived 것으로 덮어씀
    *(int *)((char *)this + 0x10) = 0; // Derived가 추가한 필드 초기화
}
```

`Base::Base(this)`가 `this`를 그대로 넘겼으므로 이는 멤버 객체 합성이 아니라 상속이다. 이어서 vtable을 `Derived`의 것으로 즉시 덮어쓰는 패턴은 "먼저 기반 클래스로 초기화한 뒤 파생 클래스 정체성을 확립한다"는 C++ 표준 생성자 순서와 정확히 일치한다. `Base`의 vtable과 `Derived`의 vtable을 나란히 비교했을 때 앞부분 항목들이 겹친다면(REV-0444 방식으로 확인) `Derived : public Base` 관계가 확정된다.

## 관련 글
- REV-0764 — 데맹글된 이름으로 클래스 구조 추정하기
- REV-0444 — vtable과 가상함수 호출 패턴 분석
- REV-0445 — RTTI(런타임 타입 정보) 흔적 분석
- REV-0446 — C++ 생성자/소멸자 호출 패턴 읽기
- REV-0763 — C++ 이름 맹글링(Name Mangling) 해석하기
- REV-0770 — 여러 함수에 걸친 로직을 하나의 흐름으로 정리하는 노트 작성법

## 출처/검증
- MSVC RTTI 구조체(`RTTICompleteObjectLocator`, `ClassHierarchyDescriptor`, `BaseClassArray`)와 `vtordisp` 썽크는 Microsoft의 공개된 C++ ABI 관련 문서 및 널리 알려진 리버스 엔지니어링 레퍼런스(비공식이지만 다수의 보안 컨퍼런스 자료에서 일관되게 확인된 구조) 기준으로 정리했다.
- Itanium C++ ABI의 `__class_type_info`/`__si_class_type_info`/`__vmi_class_type_info` 계층과 다중 상속 시 vtable 레이아웃은 Itanium C++ ABI 공식 명세(RTTI, Object Layout 섹션) 기준.
- 단일 상속에서 파생 클래스 vtable이 기반 클래스 vtable의 접두사(prefix) 형태를 갖는다는 성질은 Itanium ABI 및 다수의 컴파일러 구현에서 공통적으로 관찰되는 표준 관행이다.
