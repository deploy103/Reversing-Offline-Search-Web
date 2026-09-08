---
id: REV-0445
title: "RTTI(런타임 타입 정보) 흔적 분석"
slug: "rev-0445-rtti-traces"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - RTTI
  - Run-Time Type Information
  - type_info
  - dynamic_cast
  - typeid
  - "_ZTI"
  - "_ZTS"
  - "RTTI Complete Object Locator"
  - "RTTI Type Descriptor"
  - "__dynamic_cast"
  - "__RTDynamicCast"
  - "fno-rtti"
  - "/GR-"
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - RTTI가 뭐임
  - dynamic_cast 어셈블리
  - type_info가 뭐임
  - "_ZTI가 뭐임"
  - 클래스 이름 문자열 복구
symptom_keywords:
  - 스트립된 바이너리에서 클래스 이름을 못 찾음
  - "_ZTI로 시작하는 심볼이 뭔지 모르겠음"
  - "?AV로 시작하는 이상한 문자열이 보임"
  - dynamic_cast 호출을 분석해야 함
  - ghidra rtti 분석이 뭔지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
RTTI는 `dynamic_cast`/`typeid`를 지원하기 위해 컴파일러가 각 클래스의 vtable 바로 앞에 심어두는 타입 메타데이터로, 클래스 이름이 사람이 읽을 수 있는 문자열 그대로 남아있는 경우가 많아서 **심볼이 스트립된 C++ 바이너리에서도 클래스 구조를 상당 부분 복구할 수 있는 단서**가 된다.

## 언제 검색해야 하나
- `.rodata`/`.rdata`에서 `.?AVClassName@@`(MSVC) 또는 클래스 이름처럼 보이는 짧은 문자열이 vtable 근처에 있을 때
- `_ZTI...`(typeinfo for), `_ZTS...`(typeinfo name for)로 시작하는 심볼을 Linux/GCC 바이너리에서 봤을 때
- `dynamic_cast<T*>(p)`가 어떻게 컴파일되는지, `__dynamic_cast`/`__RTDynamicCast` 호출을 분석하고 싶을 때
- Ghidra의 RTTI 자동 분석 기능이나 IDA의 RTTI 스크립트를 써서 스트립된 C++ 바이너리의 클래스 이름을 복구하고 싶을 때
- vtable(REV-0444)을 찾았는데 그 시작 주소 바로 앞(`vtable-8` 또는 `vtable-16`)에 또 다른 포인터가 있어서 이게 뭔지 궁금할 때

## 핵심 개념

### RTTI가 존재하는 이유
C++의 `dynamic_cast`(안전한 다운캐스팅, 실패 시 `nullptr`/예외)와 `typeid`(런타임에 실제 타입 조회)는 실행 시점에 "이 객체가 실제로 어떤 클래스인지, 어떤 클래스들을 상속했는지"를 알아야 동작할 수 있다. 이를 위해 컴파일러는 다형적인(virtual 함수가 있는) 클래스마다 타입 정보를 담은 데이터 구조를 만들어 바이너리에 심어둔다. 이게 **RTTI(Run-Time Type Information)** 다.

### Itanium C++ ABI (GCC/Clang, Linux/macOS)
- 각 다형적 클래스의 **vtable[-1]**(즉 vtable 함수 포인터 배열이 시작되기 바로 직전 슬롯)에 그 클래스의 `std::type_info` 객체를 가리키는 포인터가 저장된다.
- `type_info` 객체는 다시 클래스 이름 문자열을 가리키는 포인터를 갖는다. 이 이름은 맹글링된 형태(`5Shape`처럼 "길이+이름")로, 사람이 읽을 수 있게 하려면 `c++filt`나 IDA/Ghidra의 디맹글러를 거치면 된다.
- 심볼 이름 규칙: `_ZTV5Shape`(vtable for Shape), `_ZTI5Shape`(typeinfo for Shape), `_ZTS5Shape`(typeinfo name for Shape).
- 상속 관계 표현: 단일 상속은 `__si_class_type_info`, 다중/가상 상속은 `__vmi_class_type_info`가 부모 클래스들의 `type_info`를 배열로 연결해 계층 구조를 담는다.

### MSVC ABI (Windows)
- vtable 시작 직전(x64에서는 보통 `vtable-8`)에 **RTTI Complete Object Locator**를 가리키는 포인터가 있다.
- 이 구조체는 다시 **RTTI Type Descriptor**(맹글링된 클래스 이름, 예: `.?AVShape@@`를 담음)와 **RTTI Class Hierarchy Descriptor**, **RTTI Base Class Array**로 이어지는 체인을 갖는다.
- x64 MSVC는 이 체인의 포인터들을 절대 주소가 아니라 **이미지 베이스 기준 RVA(상대 가상 주소)** 로 저장한다 — PIE/ASLR 환경에서도 재배치 없이 동작하도록 하기 위함이다(REV-0439의 RIP 상대 주소와 목적이 비슷하다).
- 따라서 실제 주소를 구하려면 `이미지 베이스(모듈 시작 주소) + RVA`를 직접 계산해야 한다. IDA/Ghidra의 자동 로더는 이 계산을 대신 해주지만, 수동으로 덤프를 분석할 때는 PE 헤더에서 얻은 로드 베이스 주소를 반드시 더해야 한다는 점을 잊지 않아야 한다.

### 상속 관계까지 표현하는 확장 구조
단일 클래스 이름만 복구해도 유용하지만, RTTI 체인은 **상속 관계**까지 담고 있다. Itanium ABI는 부모가 하나면 `__si_class_type_info`, 여러 개(다중/가상 상속)면 `__vmi_class_type_info`를 써서 부모들의 `type_info`를 배열로 이어 붙인다. MSVC는 RTTI Class Hierarchy Descriptor와 Base Class Array가 같은 역할을 한다. 이 체인을 끝까지 따라가면 "이 클래스가 어떤 부모들을 상속했는지" 클래스 다이어그램을 손으로 그릴 수 있을 정도의 정보를 얻을 수 있다 — 자동화 도구가 실패했을 때도 시간을 들이면 수동으로 복구 가능한 정보라는 뜻이다.

### 클래스 이름 문자열은 스트립돼도 잘 남는다
심볼 테이블(함수/변수 이름 목록)은 릴리스 빌드에서 `strip` 등으로 제거되는 경우가 흔하지만, RTTI가 참조하는 **클래스 이름 문자열 자체는 `.rodata`/`.rdata`의 평범한 데이터**이기 때문에 스트립의 영향을 받지 않는다. 그래서 함수 이름은 전부 `sub_401230`처럼 익명화된 스트립 바이너리에서도, `.?AVCPlayerController@@`나 `9CGameLogic` 같은 문자열은 그대로 남아있는 경우가 많다. 이건 대형 C++ 바이너리(게임, 상용 소프트웨어, C++로 작성된 악성코드 등)를 리버싱할 때 **거의 공짜로 얻는 최고의 단서**다.

### 탐지 방법
1. **문자열 검색**: Strings 창(IDA `Shift+F12`)이나 `strings` 명령으로 `.?AV`(MSVC), 혹은 그냥 사람이 읽을 수 있는 클래스 이름 후보 문자열을 찾는다.
2. **vtable 역추적**: vtable(REV-0444)의 시작 주소를 알고 있다면, 그 바로 앞(Itanium: -8, MSVC x64: -8, 구조에 따라 다를 수 있음)의 포인터를 따라가서 type_info/Complete Object Locator까지 도달한다.
3. **자동 분석 도구 활용**: Ghidra는 내장 **RTTI 분석기**가 있어서(자동 분석 옵션에서 활성화), 클래스 계층을 스스로 재구성하고 vtable/클래스에 실제 이름을 붙여준다. IDA는 기본 RTTI 인식 기능과, 더 강력한 서드파티 플러그인(Class Informer 등)으로 유사한 작업을 할 수 있다.
4. **`__dynamic_cast`/`__RTDynamicCast` 호출 추적**: 이 헬퍼 함수들은 인자로 대상 객체, 소스 `type_info`, 목적지 `type_info`를 받으므로, 호출부를 보면 캐스팅에 관련된 두 클래스의 `type_info` 주소를 바로 알 수 있다.

### 컴파일러 옵션에 따라 없을 수도 있다
RTTI는 필수가 아니다. GCC/Clang은 `-fno-rtti`, MSVC는 `/GR-`로 RTTI 생성을 끌 수 있으며, 성능/바이너리 크기에 민감한 프로젝트(게임 엔진, 임베디드, 일부 시스템 소프트웨어)에서 흔히 꺼둔다. RTTI가 꺼져 있으면 `dynamic_cast`/`typeid` 자체를 쓸 수 없으므로(컴파일 에러), 그런 바이너리에서는 애초에 이 메타데이터를 찾을 수 없다 — "C++ 바이너리는 항상 RTTI가 있다"고 가정하면 안 된다.

### 리버싱 관점에서의 의미
RTTI 복구는 스트립된 대형 C++ 바이너리를 다룰 때 가장 효율이 좋은 초기 작업 중 하나다. 클래스 이름 하나를 복구하면 그 클래스의 vtable에 이름이 붙고, vtable에 이름이 붙으면 그걸 참조하는 생성자 함수(REV-0446)에도 자동으로 문맥이 생기고, 그 결과 지금까지 `sub_401230`이었던 익명 함수가 `CPlayerController::CPlayerController`처럼 의미 있는 이름으로 바뀐다. 이 연쇄 효과 덕분에 RTTI 하나 찾는 것으로 함수 수십~수백 개에 자동으로 맥락이 생기는 경우도 흔하다.

## 화면/코드에서 보이는 징후
- `.rodata`/`.rdata`에 `.?AV`(MSVC) 또는 클래스 이름스러운 짧은 문자열이 여러 개 몰려 있음
- `_ZTI`, `_ZTS`, `_ZTV`로 시작하는 심볼(Linux/GCC, 스트립 안 됐을 때)
- vtable로 추정되는 함수 포인터 배열 바로 앞(-8 또는 -16 오프셋)에 또 다른 포인터가 있음
- `__dynamic_cast`, `__RTDynamicCast`, `__RTtypeid` 같은 헬퍼 함수 호출

## 가장 먼저 할 것
1. Strings 창(IDA `Shift+F12`)에서 `.?AV`나 사람이 읽을 수 있는 클래스 이름 후보를 먼저 검색한다.
2. vtable을 이미 찾았다면 그 시작 주소 바로 앞의 포인터를 따라가 type_info/Complete Object Locator에 도달해본다.
3. Ghidra를 쓴다면 자동 분석 옵션에서 RTTI 분석기가 켜져 있는지 확인하고 재실행해본다.

## 단계별 절차
1. vtable 바로 앞(음수 오프셋)에 타입 정보를 가리키는 포인터가 있는지 확인한다(컴파일러/ABI에 따라 위치가 다를 수 있다).
2. 그 포인터를 따라가 문자열(맹글링된 클래스 이름 등)이 있는지 Hex View로 확인한다.
3. `dynamic_cast`나 `typeid`가 쓰인 지점이라면, RTTI 비교 함수(`__dynamic_cast`, `__cxa_*`) 호출을 찾아 어떤 타입 검사를 하는지 역추적한다.
4. 이름이 C++ 이름 맹글링 형태(`_ZN...`, `?...@@`)라면 `c++filt` 또는 IDA의 demangle 기능으로 원래 클래스/함수 이름을 복원한다.

## 명령어/단축키
- IDA: `Shift+F12`(Strings), 서드파티 RTTI/Class Informer 플러그인 실행, `c++filt`로 맹글링된 이름 수동 디맹글.
- Ghidra: Analysis → Auto Analyze Options에서 RTTI 관련 분석기(Windows RTTI 등) 활성화 후 재분석.
- 커맨드라인: Linux `c++filt _ZTI5Shape`, Windows Visual Studio 동봉 `undname .?AVShape@@`로 각각 디맹글.

## 흔한 실수
- 스트립된 바이너리는 클래스/타입 정보를 전혀 복구할 수 없다고 단정하는 것 — RTTI 문자열은 심볼 테이블과 무관하게 데이터 섹션에 남아있는 경우가 많다.
- vtable의 함수 포인터 배열과 그 바로 앞에 있는 RTTI 포인터 슬롯을 혼동해서, RTTI 포인터를 "0번째 가상함수"로 잘못 해석하는 것(오프셋 한 칸 밀림 실수).
- 모든 C++ 바이너리에 RTTI가 존재한다고 가정하는 것 — `-fno-rtti`/`/GR-`로 꺼져 있을 수 있다.
- MSVC의 RVA 기반 RTTI 체인을 절대 주소로 착각해서 그대로 더하거나 역참조하는 것 — 반드시 이미지 베이스를 더해야 실제 주소가 된다.
- `_ZTI`/`_ZTS` 접두사나 `.?AV` 패턴을 몰라서, 이런 심볼/문자열을 그냥 "이상한 쓰레기 데이터"로 지나치는 것.

## 막혔을 때 다음 체크
- RTTI로 가는 첫 단계인 vtable 자체를 아직 못 찾았다면 → REV-0444에서 vtable 구조부터 확인한다.
- 클래스 이름을 복구한 뒤 생성자/소멸자에 적용하는 방법이 궁금하면 → REV-0446.
- MSVC RVA 체인 계산이 헷갈리면 → REV-0439(RIP 상대 주소)의 "실효 주소는 기준점 + 오프셋" 개념을 다시 떠올린다.

## 미니 예제

**예제 1 — Itanium ABI: vtable에서 type_info로 역추적**
```text
_ZTV5Shape:       ; vtable for Shape
    dq  _ZTI5Shape   ; vtable[-1] = type_info 포인터  ← RTTI
    dq  Shape::area
    dq  Shape::draw

_ZTI5Shape:        ; typeinfo for Shape
    dq  vtable_for___class_type_info_plus_offset
    dq  _ZTS5Shape   ; 클래스 이름 문자열 포인터

_ZTS5Shape:  db "5Shape", 0   ; c++filt로 디맹글하면 "Shape"
```

**예제 2 — MSVC: 맹글링된 타입 디스크립터 문자열**
```text
.rdata:
    db ".?AVShape@@", 0    ; RTTI Type Descriptor의 이름 필드
```
`undname`(Visual Studio 동봉 도구) 등으로 디맹글하면 `class Shape` 형태로 복원된다.

**예제 3 — `__dynamic_cast` 호출 (Itanium ABI)**
```asm
lea     rdx, [rip+_ZTI4Base]    ; 소스 타입 type_info
lea     rcx, [rip+_ZTI7Derived] ; 목적지 타입 type_info
xor     r8d, r8d
mov     rdi, rax                 ; 캐스팅할 객체 포인터
call    __dynamic_cast
```
이 호출부만 봐도 "`Base*`를 `Derived*`로 다운캐스팅하는 지점"이라는 것을 바로 알 수 있다.

**예제 4 — Ghidra RTTI 분석 전/후 (개념 설명)**
분석 전: 클래스가 `PTR_LAB_00403010`, 생성자로 추정되는 함수가 `FUN_00401550`처럼 익명으로 표시됨.
분석 후(RTTI 분석기 실행): vtable이 `PTR_vtable_for_CPlayerController`, 생성자가 `CPlayerController::CPlayerController`로 자동 리네임됨 — RTTI 문자열에서 클래스 이름을 읽어와 자동으로 적용한 결과다.

## 관련 글
- REV-0444 — vtable과 가상함수 호출 패턴 분석
- REV-0439 — RIP 상대 주소 지정 방식(RIP-relative addressing)
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0446 — C++ 생성자/소멸자 호출 패턴 읽기

## 출처/검증
- Itanium C++ ABI의 RTTI 구조(`type_info`, `vtable[-1]` 배치, `__si_class_type_info`/`__vmi_class_type_info`, `_ZTI`/`_ZTS` 심볼 규칙): Itanium C++ ABI 공식 스펙 "Run-Time Type Identification (RTTI)" 절 기준 (2026-09-08 검증).
- MSVC RTTI 구조(Complete Object Locator, Type Descriptor, Class Hierarchy Descriptor, x64 RVA 기반 인코딩): Microsoft 공식 문서 및 MSVC ABI 리버싱 관련 다수 공개 자료 기준.
- `-fno-rtti`/`/GR-` 컴파일 옵션: GCC/Clang 및 MSVC 공식 컴파일러 옵션 문서 기준.
