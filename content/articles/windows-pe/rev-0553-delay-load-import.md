---
id: REV-0553
title: "Delay-Load Import 이해하기"
slug: "rev-0553-delay-load-import"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", x64dbg]
keywords: ["IMAGE_DELAYLOAD_DESCRIPTOR", "IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT", "__delayLoadHelper2", "delayimp.lib", "DELAYLOAD 링커 옵션"]
aliases: ["지연 로드 임포트", "delay import란", "__delayLoadHelper2 후킹", "DLL 지연 로딩 탐지"]
symptom_keywords: ["임포트 테이블에 없는 DLL을 호출함", "delay import 디렉터리가 뭔지 모름", "IAT가 처음엔 채워져 있지 않음", "DLL이 나중에 로드되는 이유를 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Delay-Load Import는 프로세스 시작 시 로더가 곧바로 로드하는 일반 Import Table과 달리, 해당 DLL의 함수를 처음 호출하는 순간에야 `__delayLoadHelper2`라는 헬퍼가 `LoadLibrary`/`GetProcAddress`를 대신 호출해 그때 그때 로드/해석하는 지연 로딩 메커니즘이며, 정상적으로는 선택적 기능이나 로드 시간을 단축하기 위해 쓰이지만 악성코드가 정적 임포트 테이블에 의심스러운 API 이름이 드러나는 것을 피하려는 용도로도 쓰일 수 있다.

## 언제 검색해야 하나
- IDA 임포트 목록에는 없는데 실행 중 특정 DLL이 로드되고 그 DLL의 함수가 호출되는 것을 디버거에서 목격했을 때
- PE-bear에서 `Delay Import` 탭을 봤는데 일반 `Import` 탭과 뭐가 다른지 모를 때
- 정적 분석에서 함수 이름이 안 보이는데, 프로그램이 특정 조건에서만 특정 DLL을 쓰는 것 같을 때
- `/DELAYLOAD` 링커 옵션이나 `delayimp.lib`, `__delayLoadHelper2`라는 심벌을 코드에서 봤을 때
- 지연 로드된 DLL의 함수 호출을 후킹하거나 실패 시 동작을 분석하고 싶을 때

## 핵심 개념

### 왜 지연 로딩이 필요한가
일반 Import Table(REV-0119)에 있는 DLL은 프로세스가 시작되자마자 로더에 의해 전부 로드되고, 모든 임포트 함수의 주소가 IAT(Import Address Table)에 채워진다. 하지만 어떤 DLL은 프로그램 실행 시간의 극히 일부에서만, 혹은 선택적 기능에서만 필요할 수 있다(예: 특정 플러그인 DLL, 특수 하드웨어가 있을 때만 쓰는 API). 이런 DLL까지 매번 시작 시점에 전부 로드하면 시작 시간이 느려지고, 그 DLL이 시스템에 아예 없는 경우 프로세스 시작 자체가 실패해버린다. Delay-Load는 이 문제를 "실제로 그 함수를 처음 호출하는 순간까지 로딩을 미루는" 방식으로 해결한다.

### 데이터 디렉터리와 IMAGE_DELAYLOAD_DESCRIPTOR
`OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT]`(인덱스 13)가 Delay Import Descriptor 배열의 시작을 가리킨다. 각 항목은 지연 로드할 DLL 하나에 대응한다.
```c
typedef struct _IMAGE_DELAYLOAD_DESCRIPTOR {
    DWORD AllAttributes;                 // 보통 1 (RVA 기반임을 의미)
    DWORD DllNameRVA;                     // DLL 이름 문자열 RVA
    DWORD ModuleHandleRVA;                // 로드 후 HMODULE을 저장할 위치 RVA
    DWORD ImportAddressTableRVA;          // 지연 로드 IAT RVA
    DWORD ImportNameTableRVA;             // 함수 이름 테이블 RVA(일반 INT와 유사)
    DWORD BoundImportAddressTableRVA;     // 바인딩된 IAT(선택적)
    DWORD UnloadInformationTableRVA;      // 언로드 시 원복용 정보(선택적)
    DWORD TimeDateStamp;
} IMAGE_DELAYLOAD_DESCRIPTOR;
```
이 구조는 일반 Import Descriptor와 개념적으로 비슷하지만, IAT가 프로세스 시작 시점에는 실제 함수 주소가 아니라 **자기 자신을 지연 로드 헬퍼로 되돌리는 트램폴린 스텁의 주소**로 채워져 있다는 점이 다르다.

### 런타임 동작: __delayLoadHelper2
Visual C++ 링커에서 `/DELAYLOAD:some.dll` 옵션을 쓰면, 링커가 `delayimp.lib`의 `__delayLoadHelper2` 함수와 각 임포트 함수마다 작은 스텁 코드를 자동으로 삽입한다. 코드가 지연 로드 대상 함수를 처음 호출하면 실제로는 이 스텁으로 점프하고, 스텁은 `__delayLoadHelper2(pDelayDescriptor, ppfnIATEntry)`를 호출한다. 이 헬퍼가 내부적으로 `LoadLibrary`(또는 사용자 지정 `dliNotify`/`dliFailureHook` 후킹 콜백)로 DLL을 로드하고 `GetProcAddress`로 실제 함수 주소를 얻은 뒤, 그 주소로 IAT 엔트리를 덮어쓰고 원래 호출을 그 실제 함수로 이어준다. 두 번째 호출부터는 이미 IAT가 실제 주소로 채워져 있으므로 일반 함수 호출과 성능 차이가 거의 없다.

### 실패 처리와 커스텀 후킹
`delayimp.lib`는 로드나 함수 조회가 실패했을 때 기본적으로 예외(`VcppException(ERROR_SEVERITY_ERROR, ERROR_MOD_NOT_FOUND)` 계열의 구조적 예외)를 던지지만, 개발자가 전역 함수 포인터 `__pfnDliFailureHook2`(또는 구버전에서는 `__pfnDliFailureHook`)에 자신의 콜백 함수를 등록해두면 실패 시(그리고 선택적으로 성공 로드 시점에도 `__pfnDliNotifyHook2`를 통해) 원하는 로직을 끼워 넣을 수 있다. 예를 들어 특정 DLL이 없을 때 대체 경로에서 로드를 시도하거나, 로드에 실패해도 조용히 넘어가고 해당 기능만 비활성화하는 식이다. 이런 후킹 콜백이 코드에 있다면, 정상적으로는 로드되지 않을 DLL이 실행 환경에 따라 선택적으로만 로드된다는 뜻이므로 분석 시 "이 DLL이 없는 환경"과 "있는 환경" 양쪽에서의 동작 차이를 함께 살펴볼 가치가 있다.

### 리버싱에서의 의미
정적 분석 도구가 기본 Import Table만 보고 "이 프로그램은 어떤 DLL/API를 쓰는지"를 판단하면, Delay-Load로 임포트된 DLL/함수는 빠뜨릴 수 있다. 악성코드는 이 특성을 악용해 탐지에 민감한 API(예: 프로세스 인젝션 관련 API)를 일반 Import Table 대신 Delay-Load로 넣어, 자동화된 정적 시그니처 스캐너의 "임포트 목록 기반 탐지"를 우회하려 시도하기도 한다. 물론 Delay Import Descriptor 자체는 여전히 파일 안에 평문으로 DLL 이름과 함수 이름이 남아 있으므로(단순히 위치가 다른 테이블일 뿐), 이 테이블까지 함께 파싱하는 도구(PE-bear, 최신 IDA)에게는 숨겨지지 않는다 — 다만 초심자가 Import Table 탭만 보고 넘어가면 놓칠 수 있다는 것이 핵심 위험이다.

## 화면/코드에서 보이는 징후
- PE-bear에서 `Import`와 별도로 `Delay Import`라는 탭이 존재하고, 여기 나열된 DLL이 `Import` 탭에는 없음
- IDA에서 디스어셈블리 중 `call __imp_load_함수이름`처럼 일반 임포트와 다른 형태의 스텁 호출부, 또는 `__delayLoadHelper2`로 향하는 반복적인 짧은 트램폴린 함수들이 보임
- x64dbg로 실행 중 프로세스를 관찰하면, 시작 직후에는 로드되지 않았던 DLL이 특정 시점(특정 버튼 클릭, 특정 기능 사용 시)에 갑자기 모듈 목록에 나타남
- 문자열 창에서 DLL 이름과 함수 이름이 보이는데도 임포트 테이블에서는 해당 이름을 찾을 수 없는 경우

## 가장 먼저 할 것
임포트 테이블에서 기대한 API가 안 보인다면, 먼저 PE-bear나 동급 도구로 Delay Import Directory(`IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT`)를 확인한다. 여기에 있다면, 그 함수는 처음 호출되는 시점(실행 흐름 중 특정 조건 도달 시)까지 실제 로드가 미뤄진다는 점을 감안해 동적 분석 시나리오를 조정한다(그 기능을 실제로 트리거해야 DLL이 로드됨).

## 단계별 절차
**1) Delay Import Directory 위치 확인**
`OptionalHeader.DataDirectory[13].VirtualAddress`/`.Size`로 시작 위치를 찾는다.

**2) 각 IMAGE_DELAYLOAD_DESCRIPTOR 순회**
`DllNameRVA`로 DLL 이름을, `ImportNameTableRVA`로 함수 이름 목록을(일반 INT와 유사하게 `IMAGE_THUNK_DATA` 배열, 오디널 임포트일 경우 REV-0555 규칙 적용) 확인한다.

**3) IAT 초기 상태 확인**
`ImportAddressTableRVA`가 가리키는 값들이 프로세스 시작 직후에는 실제 함수 주소가 아니라 스텁 코드 주소로 채워져 있음을 디버거에서 확인한다.

**4) 트리거 조건 찾기**
IDA에서 해당 함수를 호출하는 코드 경로를 xref로 추적해, 어떤 조건(메뉴 클릭, 특정 인자 등)에서 이 지연 로드 함수가 처음 호출되는지 파악한다.

## 명령어/단축키
```text
PE-bear: Delay Import 탭 — DLL/함수 목록과 각 디스크립터 필드 확인
IDA: 임포트 목록 아래 별도로 표시되는 Delay-Load 항목, 또는 __delayLoadHelper2 xref(X) 확인
x64dbg: 모듈 목록(Alt+E)을 실행 중 지속 관찰해 새로 로드되는 DLL 포착, 브레이크포인트로 LoadLibraryExW 후킹
```

## 출력 해석
- `ImportAddressTableRVA`가 가리키는 초기값이 이미지 내부(자기 자신 모듈)의 주소를 가리키면 이는 아직 해석되지 않은 스텁이며, 실제 로딩 전이라는 뜻
- `BoundImportAddressTableRVA`/`TimeDateStamp`가 유효하게 채워져 있으면 빌드 시점에 바인딩(REV-0554 참고)까지 시도된 지연 로드 — 로드된 DLL의 실제 타임스탬프가 일치하면 로더가 조회를 생략하는 추가 최적화가 적용될 수 있음
- 동적 분석 중 특정 기능을 눌러도 기대한 DLL이 로드되지 않으면, 코드에 `dliFailureHook` 같은 사용자 정의 실패 처리 콜백이 있어 로드 실패를 조용히 삼키고 있을 가능성을 고려

## 흔한 실수
- 임포트 테이블에 없다는 이유만으로 그 DLL/함수를 전혀 쓰지 않는다고 단정하는 것 — Delay Import Directory를 놓치는 가장 흔한 실수다.
- Delay-Load된 함수가 절대 호출되지 않을 거라 생각하고 동적 분석에서 해당 기능을 트리거하지 않아 관련 동작을 놓치는 것.
- 일반 Import Table의 IAT 패칭 방식(REV-0129)과 동일하게 취급해서, 시작 시점에 이미 실제 주소가 채워져 있을 거라 착각하고 초기 메모리 덤프에서 잘못된 결론을 내리는 것.
- `__delayLoadHelper2` 호출부를 일반 함수 호출로 착각해서 디버깅 시 그냥 Step Over 해버려, 실제 어떤 DLL/함수가 로드되는지 확인할 기회를 놓치는 것.

## 막혔을 때 다음 체크
- 일반 Import Table의 구조와 기본 개념이 헷갈리면 → [Import Table에서 중요한 API 찾기](./rev-0119-import-table.md)
- `LoadLibrary`/`GetProcAddress`의 수동 호출 패턴과 비교하고 싶으면 → [GetProcAddress LoadLibrary 동적 API 해석](./rev-0129-getprocaddress-loadlibrary.md)
- 빌드 시점에 주소를 미리 채워두는 또 다른 최적화 기법이 궁금하면 → [Bound Import와 Import 최적화 이해하기](./rev-0554-bound-import.md)
- 이름 대신 오디널로 임포트된 함수를 분석하는 법은 → [Ordinal Import(이름 없는 Import) 분석법](./rev-0555-ordinal-import.md)

## 미니 예제
`viewer.exe`를 IDA로 열었더니 일반 Import Table에는 `gdiplus.dll`이 없었다. PE-bear의 `Delay Import` 탭을 확인하니 `gdiplus.dll`이 `DllNameRVA`로 나열되어 있고, `GdiplusStartup`, `GdipCreateBitmapFromFile` 같은 함수 이름이 `ImportNameTableRVA` 아래 목록에 있었다. x64dbg로 프로그램을 실행해 모듈 목록을 확인하니 시작 직후에는 `gdiplus.dll`이 로드되어 있지 않다가, 사용자가 이미지 파일을 여는 메뉴를 클릭한 순간 모듈 목록에 `gdiplus.dll`이 나타났다. 이는 이미지 뷰어 기능이 선택적으로만 필요한 GDI+ 관련 API를 지연 로드로 구현해, 이미지를 한 번도 열지 않는 사용자는 이 DLL을 아예 로드하지 않도록 최적화한 전형적인 정상 사례다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0554 — Bound Import와 Import 최적화 이해하기
- REV-0555 — Ordinal Import(이름 없는 Import) 분석법

## 출처/검증
- `IMAGE_DELAYLOAD_DESCRIPTOR` 구조체와 Delay Import Directory(`IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT`, 인덱스 13) 정의: Microsoft Learn "PE Format" 공식 문서 기준 (2026-09-08 검증).
- `__delayLoadHelper2`, `/DELAYLOAD` 링커 옵션, `delayimp.lib` 동작 방식: Microsoft Learn Visual C++ "Linker Support for Delay-Loaded DLLs" 공식 문서 기준.
- 지연 로드를 이용한 정적 임포트 목록 회피 기법: 다수 리버싱/악성코드 분석 레퍼런스에서 공통적으로 언급되는 일반 패턴(2026-09-08 기준 서술).
