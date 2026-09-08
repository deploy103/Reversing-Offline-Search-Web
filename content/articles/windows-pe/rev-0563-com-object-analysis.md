---
id: REV-0563
title: "COM 객체(IUnknown, CLSID)가 보일 때 분석 접근"
slug: "rev-0563-com-object-analysis"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg, OleView]
keywords: ["COM", "IUnknown", "CLSID", "IID", "vtable", "CoCreateInstance", "DllGetClassObject", "QueryInterface"]
aliases: ["com 객체 리버싱", "vtable 호출 분석", "iunknown 인터페이스란", "clsid 레지스트리 확인"]
symptom_keywords: ["call [eax]처럼 구조체를 통한 간접 호출이 반복됨", "guid 상수가 코드에 보임", "cocreateinstance가 뭘 하는지 모름", "vtable 첫 세 함수가 뭔지 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
COM(Component Object Model) 객체는 겉보기엔 그냥 "구조체를 가리키는 포인터"지만 실제로는 함수 포인터 배열(vtable)의 첫 주소를 가리키는 포인터이며, 모든 COM 인터페이스는 `IUnknown`의 세 함수(`QueryInterface`, `AddRef`, `Release`)를 vtable 맨 앞 3슬롯에 반드시 가지고 있으므로, IDA에서 `mov ecx, [obj]; call [ecx+8]`(64비트라면 `+0x10`) 같은 패턴을 보면 십중팔구 `Release` 호출이라는 것부터 알아두면 COM 기반 코드를 훨씬 빠르게 읽을 수 있다.

## 언제 검색해야 하나
- 디스어셈블리에서 `mov rax, [rcx]; call [rax+X]` 같은, "포인터를 읽어서 그 안의 함수 포인터를 다시 읽어 호출"하는 이중 간접 호출 패턴이 반복해서 보일 때
- 코드나 데이터 섹션에 16바이트짜리 GUID처럼 보이는 상수(예: `{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}` 형태)가 있을 때
- `CoCreateInstance`, `CoGetClassObject`, `DllGetClassObject` 같은 함수가 Import Table에 보일 때
- 레지스트리의 `HKEY_CLASSES_ROOT\CLSID\{GUID}` 경로와 실행 파일의 관계를 파악해야 할 때
- ActiveX 컨트롤이나 셸 확장(Shell Extension) 같은 COM 기반 컴포넌트를 분석해야 할 때

## 핵심 개념

### COM 객체의 실체: vtable을 가리키는 포인터의 포인터
C++로 가상 함수를 가진 클래스의 인스턴스를 만들면, 컴파일러는 그 인스턴스 메모리의 맨 앞에 **vtable 포인터**(vptr)를 몰래 넣는다. COM 인터페이스 포인터도 정확히 이 구조를 그대로 활용한다.

```text
COM 인터페이스 포인터(예: IFoo* pFoo)
        │
        ▼
[vtable 포인터] ──────► vtable(함수 포인터 배열)
[멤버 데이터...]              [0] QueryInterface
                               [1] AddRef
                               [2] Release
                               [3] (IFoo 고유 메서드 1)
                               [4] (IFoo 고유 메서드 2)
                               ...
```
즉 `pFoo->Method()`를 C++에서 호출하면, 실제 기계어 수준에서는 "`pFoo`가 가리키는 곳에서 vtable 포인터를 읽고, 그 vtable에서 N번째 함수 포인터를 읽어서 그 주소로 `call`한다"는 두 단계 역참조가 일어난다. x64에서는 대략 다음과 같은 패턴으로 나타난다.
```asm
mov rax, [rcx]        ; rcx = COM 객체 포인터, [rcx] = vtable 시작 주소
call qword ptr [rax+18h]  ; vtable의 4번째 슬롯(인덱스 3) 호출 — IUnknown 이후 첫 고유 메서드
```

### IUnknown: 모든 COM 인터페이스의 공통 기반
```c
interface IUnknown {
    virtual HRESULT QueryInterface(REFIID riid, void** ppvObject) = 0; // vtable[0]
    virtual ULONG   AddRef(void) = 0;                                  // vtable[1]
    virtual ULONG   Release(void) = 0;                                 // vtable[2]
};
```
**어떤 COM 인터페이스든 이 세 함수가 항상 vtable의 0, 1, 2번 슬롯에 이 순서 그대로 있다.** 그래서 `call [vtable+0]`은 항상 `QueryInterface`, `call [vtable+8]`(x64 기준, 포인터 크기 8바이트)은 `AddRef`, `call [vtable+0x10]`은 `Release`라고 곧바로 판단할 수 있다. 이 규칙 하나만 알아도 COM 코드에서 참조 카운트 관리(`AddRef`/`Release`) 호출과 실제 기능 호출을 구분할 수 있다.

### CLSID와 IID: 클래스와 인터페이스를 식별하는 GUID
- **CLSID(Class ID)**: 특정 COM 클래스(구현체)를 식별하는 128비트 GUID. 레지스트리 `HKEY_CLASSES_ROOT\CLSID\{GUID}\InprocServer32`에 이 클래스를 구현한 DLL 경로가 등록돼 있다.
- **IID(Interface ID)**: 특정 인터페이스(메서드 집합)를 식별하는 GUID. `QueryInterface(riid, ...)`를 호출할 때 "이 객체에서 이 IID에 해당하는 인터페이스를 달라"고 요청하는 데 쓰인다.

코드나 `.rdata`에서 16바이트 단위의 GUID 형태 상수를 발견하면, 이것이 CLSID인지 IID인지 판단해야 하는데, 잘 알려진 GUID(예: `IID_IUnknown = {00000000-0000-0000-C000-000000000046}`)는 IDA가 자동으로 `guids.lib`/타입 라이브러리 기반 이름을 붙여주는 경우가 많다.

### 객체를 만드는 두 가지 경로
```c
// 1) 표준 API로 생성 (COM 라이브러리가 초기화된 상태에서)
HRESULT CoCreateInstance(REFCLSID rclsid, LPUNKNOWN pUnkOuter,
                          DWORD dwClsContext, REFIID riid, LPVOID* ppv);

// 2) DLL을 직접 로드해서 팩토리 함수 호출 (더 저수준)
HRESULT DllGetClassObject(REFCLSID rclsid, REFIID riid, LPVOID* ppv);
```
`CoCreateInstance`는 내부적으로 레지스트리를 조회해 해당 CLSID를 구현하는 DLL을 찾고, 그 DLL을 로드한 뒤 DLL이 export하는 `DllGetClassObject`를 호출해서 클래스 팩토리를 얻고, 최종적으로 원하는 인터페이스 포인터를 반환한다. 리버싱 관점에서는 `CoCreateInstance` 호출부의 CLSID/IID 인자만 읽어도 "이 프로그램이 어떤 COM 컴포넌트를 쓰는지" 바로 알 수 있다.

## 화면/코드에서 보이는 징후
- `mov reg, [reg]` 다음에 곧바로 `call [reg+오프셋]`이 오는 이중 역참조 호출 패턴이 반복됨
- 코드/데이터에 `{XXXXXXXX-XXXX-...}` 형태로 표시되는 GUID 상수, 또는 IDA가 `IID_IFoo`, `CLSID_Bar` 같은 이름을 자동으로 붙여준 상수
- Import Table에 `ole32.dll`의 `CoCreateInstance`, `CoInitialize`/`CoInitializeEx`, `CoGetClassObject`가 있음
- Export Table에 `DllGetClassObject`, `DllCanUnloadNow`, `DllRegisterServer` 같은 이름이 있음(COM 서버 DLL의 표준 export)

## 가장 먼저 할 것
IDA에서 반복되는 `call [reg+오프셋]` 패턴을 보면, 먼저 오프셋이 `0`, 포인터크기, `2*포인터크기`(x64면 0, 8, 0x10) 중 하나인지 확인한다. 맞다면 각각 `QueryInterface`/`AddRef`/`Release`이므로 실제 로직과 무관한 COM 배관(plumbing) 코드로 넘겨도 된다. 그보다 큰 오프셋이면 그 COM 인터페이스의 고유 메서드이므로, 어떤 인터페이스인지부터 알아내야 한다 — 근처에서 `QueryInterface`에 전달된 IID 상수를 찾으면 실마리가 된다.

## 단계별 절차

**1) vtable 호출 패턴 식별**
`mov reg, [obj_ptr]; call [reg+N]` 패턴을 찾고, N이 3개 이하 슬롯이면 IUnknown 메서드로 분류한다.

**2) 객체가 생성되는 지점 역추적**
그 `obj_ptr`이 어디서 왔는지(`CoCreateInstance`의 `ppv` 출력 인자, 또는 `QueryInterface`의 출력 인자) 역추적한다.

**3) CLSID/IID 상수 확인**
`CoCreateInstance` 호출부의 `rclsid`, `riid` 인자에 쓰인 GUID 상수를 읽는다. IDA가 이름을 못 붙였다면 GUID 값을 그대로 검색 엔진이나 알려진 COM 인터페이스 데이터베이스에서 찾아본다.

**4) 레지스트리로 실제 구현 DLL 확인**
```text
레지스트리 편집기: HKEY_CLASSES_ROOT\CLSID\{알아낸GUID}\InprocServer32
                   → 기본값이 실제 구현 DLL 경로
```
또는 `OleView`/`OleViewDotNet` GUI 도구로 등록된 COM 클래스를 검색한다.

**5) vtable을 IDA 구조체로 정의**
고유 메서드가 많은 인터페이스라면, IDA에서 vtable 배열을 구조체(Struct)로 정의하고 각 슬롯에 이름을 붙여두면 이후 xref 추적이 훨씬 쉬워진다(`Edit → Struct`로 새 구조체 생성 후 각 오프셋에 이름 부여, 이후 데이터 위치에서 이 구조체 타입 적용).

## 명령어/단축키
```text
IDA: 상수 위에서 우클릭 → "Convert to struct/array" 또는 GUID로 인식되면
     자동으로 IID_/CLSID_ 이름이 붙는지 확인
IDA: Edit → Struct(구조체 편집기)로 vtable 레이아웃 정의
OleView / OleViewDotNet: 레지스트리에 등록된 COM 클래스, 타입 라이브러리 탐색
regedit: HKEY_CLASSES_ROOT\CLSID\{GUID} 경로에서 InprocServer32 확인
```

## 출력 해석
- `call [vtable+0]`, `+8`, `+0x10`(x64 기준) — 각각 `QueryInterface`, `AddRef`, `Release`. 실제 기능과 무관한 참조 카운트 관리 코드
- `call [vtable+0x18]` 이상 — `IUnknown`을 상속한 구체적 인터페이스의 고유 메서드. 어떤 인터페이스인지 알아야 의미를 알 수 있다
- `CoCreateInstance`가 `S_OK`(0)를 반환하면 객체 생성 성공, 실패 시 `REGDB_E_CLASSNOTREG`(해당 CLSID가 레지스트리에 없음) 같은 HRESULT 코드가 반환됨 — 이 값으로 왜 실패했는지 짐작 가능

## 흔한 실수
- 이중 역참조 `call [[ptr]+N]` 패턴을 일반 함수 포인터 호출과 구분하지 못하고 그냥 "이상한 간접 호출"로 넘겨버리는 것.
- vtable 슬롯 0~2를 실제 기능 호출로 착각해서 분석 시간을 낭비하는 것 — 거의 항상 `IUnknown`의 세 함수다.
- x86과 x64에서 vtable 슬롯 간격(포인터 크기)이 4바이트/8바이트로 다르다는 것을 무시하고 오프셋 계산을 잘못하는 것.
- CLSID와 IID를 같은 개념으로 혼동하는 것 — CLSID는 "어떤 구현을 쓸지" 고르는 값이고, IID는 "그 구현에서 어떤 인터페이스를 달라고 할지" 고르는 값이다.
- `DllGetClassObject`가 export된 DLL을 일반 라이브러리처럼 함수 이름으로만 분석하려는 것 — 실제로는 클래스 팩토리(`IClassFactory`) 객체를 거쳐 최종 인터페이스가 나오므로 한 단계 더 따라가야 한다.

## 막혔을 때 다음 체크
- 이 DLL이 어떤 함수를 export하는지부터 다시 보고 싶으면 → [REV-0120 Export Table과 DLL 함수](./rev-0120-export-table.md)
- 런타임에 함수 주소를 찾는 다른 방식(GetProcAddress)과 비교하고 싶으면 → [REV-0129 GetProcAddress LoadLibrary 동적 API 해석](./rev-0129-getprocaddress-loadlibrary.md)
- DLL 분석을 어디서부터 시작할지 감이 안 잡히면 → [REV-0135 DLL 문제 분석 시작하기](./rev-0135-dll-analysis-start.md)
- x64 호출 규약과 레지스터 사용이 헷갈리면 → [REV-0122 Microsoft x64 Calling Convention](./rev-0122-ms-x64-calling-convention.md)

## 미니 예제
디스어셈블리에서 다음과 같은 코드를 만났다고 하자.

```asm
; rcx = 어떤 COM 객체 포인터 (이전에 CoCreateInstance로 얻음)
mov rax, [rcx]          ; rax = vtable 시작 주소
call qword ptr [rax+20h] ; vtable[4번째 고유 메서드] 호출 (IUnknown 3개 이후 2번째)
```

```text
분석 순서:
1) 0x20 / 8 = 4번째 슬롯. IUnknown(0,1,2) 다음이므로 인덱스 3, 즉
   "IUnknown 세 개 이후 첫 번째 고유 메서드"에 해당.
2) rcx가 어디서 왔는지 역추적 →
   CoCreateInstance(rclsid=CLSID_ShellLink, ..., riid=IID_IShellLinkW, &rcx) 호출부를 발견.
3) CLSID_ShellLink + IID_IShellLinkW 조합으로,
   이 객체가 "바로가기(.lnk) 생성/조작"용 COM 인터페이스라는 것을 알아냄.
4) IShellLinkW 인터페이스 정의(공개 헤더 shobjidl.h)를 참고해
   vtable 인덱스 3이 SetPath 메서드임을 확인 → call 지점의 인자(rdx)를 보면
   어떤 경로 문자열을 바로가기 대상으로 설정하는지 바로 알 수 있다.
```

## 관련 글
- REV-0120 — Export Table과 DLL 함수
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0135 — DLL 문제 분석 시작하기
- REV-0122 — Microsoft x64 Calling Convention

## 출처/검증
- `IUnknown` 인터페이스 정의(`QueryInterface`/`AddRef`/`Release`가 vtable 0~2번 슬롯에 고정된다는 규칙): Microsoft Learn "COM: Component Object Model" 및 "IUnknown interface" 공식 문서 기준 (2026-09-08 검증).
- `CoCreateInstance`, `CoGetClassObject`, `DllGetClassObject` API 시그니처와 동작, CLSID/InprocServer32 레지스트리 구조: Microsoft Learn "COM" 공식 문서 기준.
- `IShellLinkW`와 관련 CLSID/IID 예시: Microsoft Learn "Shell Programming" 공식 문서(`shobjidl.h`) 기준이며, 미니 예제의 vtable 인덱스는 설명 목적의 단순화된 예시임을 밝혀둔다.
