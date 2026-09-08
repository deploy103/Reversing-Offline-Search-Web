---
id: REV-0620
title: "Delay-Load Import가 처음엔 안 보여서 함수가 없다고 착각할 때"
slug: "rev-0620-delay-load-import-missing"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, PE-bear, x64dbg]
keywords: ["Delay-Load Import", "IMAGE_DELAY_LOAD_DESCRIPTOR", ".didat", "__delayLoadHelper2", "지연 로딩", "DelayImport"]
aliases: ["Delay Import 안 보임", "지연 로딩 함수 못 찾음", "Import Table에 함수가 없는데 실제론 호출됨"]
symptom_keywords: ["Import Table에는 없는데 실행하면 그 DLL 함수가 불린다", "IDA Imports 창에 함수가 안 보인다", "특정 DLL이 나중에 로드되는 것 같다", "off_ 이름으로만 보이고 함수명이 안 붙는다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
함수가 일반 Import Table(`IMAGE_DIRECTORY_ENTRY_IMPORT`, 인덱스 1)에는 없는데 실행하면 분명히 호출되고 있다면, **Delay-Load Import**(`IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT`, 인덱스 13)를 의심해야 한다. 이는 링커 옵션(`/DELAYLOAD`)으로 "이 DLL은 실제로 함수가 처음 호출되는 순간에 로드하라"고 지정한 것으로, 별도의 디렉터리와 헬퍼 코드(`.didat` 섹션, `__delayLoadHelper2`)를 통해 동작하기 때문에 일반 Import 뷰어에서 놓치기 쉽다.

## 언제 검색해야 하나
- IDA Imports 창이나 PE-bear의 Import 탭에 특정 DLL/함수가 안 보이는데, 동적 분석(x64dbg)에서는 그 DLL이 실제로 로드되고 함수가 호출되는 것을 확인했을 때
- 문자열 목록에서 DLL 이름(예: `"bcrypt.dll"`)이 하드코딩되어 있는데 Import Table에는 그 DLL이 없을 때
- 디컴파일 결과에 `off_xxxxx()`처럼 함수 이름이 아니라 오프셋 변수로 호출되는 것처럼 보이는 코드가 있을 때
- `.didat`라는 낯선 섹션 이름을 PE 섹션 목록에서 발견했을 때

## 핵심 개념
일반 Import는 PE가 로드되는 즉시 Windows 로더가 모든 임포트 DLL을 메모리에 매핑하고 IAT(Import Address Table)를 실제 함수 주소로 채워 넣는다. 반면 **Delay-Load Import**는 프로그램이 실제로 그 함수를 처음 호출하는 순간까지 DLL 로딩과 주소 해석을 미룬다. 선택적 의존성이 있는 DLL(예: 특정 기능에서만 필요한 라이브러리)이나 시작 시간을 줄이고 싶을 때 사용하는 기법이며, Visual C++ 링커의 `/DELAYLOAD:<dllname>` 옵션으로 지정한다.

내부 동작 방식:
1. PE Optional Header의 `DataDirectory[13]`(`IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT`)이 `IMAGE_DELAY_LOAD_DESCRIPTOR` 배열을 가리킨다. 이 구조체는 일반 `IMAGE_IMPORT_DESCRIPTOR`와 비슷하지만 별도의 필드 구성을 가진다(`DllNameRVA`, `ModuleHandleRVA`, `ImportAddressTableRVA`, `ImportNameTableRVA` 등).
2. 코드에서 지연 로드 함수를 처음 호출하면, 실제로는 `__delayLoadHelper2`(런타임 헬퍼)로 먼저 진입한다.
3. 이 헬퍼가 내부적으로 `LoadLibraryExW`(또는 사용자 정의 후크)로 DLL을 로드하고 `GetProcAddress`로 실제 함수 주소를 얻은 뒤, 지연 로드 IAT 슬롯을 그 주소로 덮어쓴다.
4. 이후부터는 그 슬롯을 통한 호출이 실제 함수로 바로 연결되어, 두 번째 호출부터는 일반 Import처럼 빠르게 동작한다.

이 과정 때문에 정적 분석 도구가 지연 로드 임포트를 "일반 임포트처럼" 자동으로 이름 붙여주지 않는 경우가 있고(도구/버전에 따라 다름), 함수가 처음 보일 때는 이름 없는 오프셋 변수나 `Ordinal#N` 형태로만 보이기도 한다.

## 화면/코드에서 보이는 징후
- PE 섹션 목록에 `.didat`라는 섹션이 별도로 존재(지연 로드 관련 데이터가 여기 저장되는 경우가 많음)
- IDA에서 함수 호출부가 `call __imp_load_FunctionName` 형태이거나, `call ds:off_140005000` 처럼 이름이 안 붙은 포인터를 통한 간접 호출로 보임
- 문자열 참조로 DLL 이름은 있는데 Import Table에는 해당 DLL 자체가 안 보임
- x64dbg로 `bp LoadLibraryExW` 걸어두면 프로그램 시작 후 한참 뒤(해당 기능을 실제로 쓸 때) 갑자기 특정 DLL 이름으로 브레이크포인트가 걸림

## 가장 먼저 할 것
PE-bear로 파일을 열어 Optional Header의 Data Directory 목록에서 **Delay Import Descriptor**(인덱스 13) 항목의 크기가 0이 아닌지 확인한다. 0이 아니면 지연 로드 임포트가 존재한다는 뜻이며, PE-bear는 보통 "Delay Import" 탭에서 이 목록을 일반 Import처럼 DLL/함수 이름으로 펼쳐서 보여준다.

## 단계별 절차
1. **PE-bear로 Delay Import 탭 확인**: PE-bear에서 파일을 열고 좌측 트리에서 "Delay Import" 항목을 클릭한다. 여기에 DLL별로 임포트되는 함수 목록이 일반 Import Table과 동일한 형태로 나열된다.
2. **IDA에서 수동으로 디렉터리 확인(자동 인식이 안 될 때)**: IDA가 지연 로드 임포트를 자동으로 이름 붙이지 못했다면, `.didat` 섹션이나 `IMAGE_DELAY_LOAD_DESCRIPTOR` 배열 위치(Optional Header DataDirectory[13].VirtualAddress)로 직접 이동해 구조체를 수동으로 해석한다. 각 디스크립터의 `DllNameRVA`가 가리키는 문자열로 DLL 이름을, `ImportNameTableRVA`가 가리키는 배열로 함수 이름(또는 서수)을 확인할 수 있다.
3. **호출부 재확인**: 함수 이름을 확인했으면, 그 IAT 슬롯 주소에 데이터 xref가 걸린 코드 위치(원래 함수를 호출하려던 지점)를 찾아 함수 이름을 수동으로 리네임(`N`)해준다.
4. **동적 분석으로 실제 로드 시점 확인**: x64dbg에서 `bp LoadLibraryExW`(지연 로드 헬퍼가 내부적으로 이 API를 씀)를 걸고 실행하면서, 어느 시점에 어떤 DLL이 로드되는지 관찰한다. 이 시점이 바로 지연 로드가 실제로 트리거되는 순간이다.
5. **후속 GetProcAddress 확인**: 이어서 `bp GetProcAddress`를 걸면 실제로 어떤 함수 이름(또는 서수)이 해석되는지 확인할 수 있다. Call Stack을 보면 `__delayLoadHelper2` 프레임이 보이는 경우가 많아 이것이 지연 로드 경로임을 재확인할 수 있다.

## 명령어/단축키
- PE-bear: 좌측 트리 "Delay Import" 클릭
- IDA: `G`(특정 주소로 이동, Data Directory RVA 확인 시), `N`(이름 바꾸기)
- x64dbg: `bp LoadLibraryExW`, `bp GetProcAddress`, Call Stack 창으로 `__delayLoadHelper2` 확인

## 출력 해석
- Delay Import Descriptor 크기가 0이면 이 바이너리는 지연 로드를 쓰지 않는다는 뜻이니 다른 원인(예: 동적 문자열 조합으로 `LoadLibrary`/`GetProcAddress`를 직접 호출하는 수동 방식, REV-0129 참고)을 확인해야 한다.
- `LoadLibraryExW`가 프로그램 시작 직후가 아니라 특정 사용자 동작(예: 버튼 클릭, 특정 입력) 이후에 호출된다면, 그 DLL의 기능이 조건부로만 필요하다는 설계 의도를 알 수 있다.
- 첫 호출에서만 헬퍼를 거치고 두 번째 호출부터는 바로 함수로 점프하므로, 브레이크포인트가 첫 호출 이후에는 더 이상 `__delayLoadHelper2`를 거치지 않고 곧장 함수로 진입하는 것이 정상이다.

## 흔한 실수
- Import Table에 없다고 "이 DLL은 이 프로그램과 무관하다"고 성급히 결론짓는 것. 문자열에 DLL 이름이 보인다면 지연 로드나 런타임 동적 로딩(REV-0129)을 반드시 함께 확인해야 한다.
- `.didat` 섹션을 그냥 일반 데이터 섹션으로 넘겨버리고 그 안의 구조체를 분석하지 않는 것.
- 지연 로드 함수 호출부를 일반 임포트 호출부와 똑같은 방식(단순 `call` 대상 이름 확인)으로만 찾으려다가, 헬퍼 함수를 거치는 간접 호출 패턴이라 못 찾는 것.
- `GetProcAddress`로 서수(ordinal)만으로 함수를 가져오는 경우, 이름 문자열이 아예 없으므로 이름표만 보고 함수를 찾으려 하면 실패한다. 서수를 DLL의 Export Table과 대조해서 실제 함수 이름을 찾아야 한다.

## 막혔을 때 다음 체크
- 일반 Import Table 자체를 읽는 법이 헷갈린다면 → REV-0119(Import Table에서 중요한 API 찾기)를 먼저 확인한다.
- 지연 로드가 아니라 완전히 수동으로 `LoadLibrary`/`GetProcAddress`를 호출하는 패턴이라면 → REV-0129(GetProcAddress LoadLibrary 동적 API 해석)를 확인한다.
- 함수 이름을 확보한 뒤 그 역할을 추측해야 한다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.

## 미니 예제
`target.exe`의 문자열 목록에서 `"bcrypt.dll"`이 발견됐는데, IDA Imports 창에는 `bcrypt.dll`이 전혀 없었다. PE-bear로 열어 "Delay Import" 탭을 확인하니 다음과 같이 나왔다.

```text
DLL: bcrypt.dll
  BCryptOpenAlgorithmProvider
  BCryptHashData
  BCryptCloseAlgorithmProvider
```

x64dbg에서 `bp LoadLibraryExW` 후 실행하니, 프로그램 시작 직후에는 걸리지 않다가 "암호화 검증" 버튼을 누른 순간 `bcrypt.dll` 이름으로 브레이크포인트가 걸렸다. 이는 이 DLL이 특정 기능(암호화 검증)에서만 필요해서 지연 로드로 지정되어 있었기 때문이다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- Delay-Load Import의 구조(`IMAGE_DELAY_LOAD_DESCRIPTOR`, `IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT` 인덱스 13)와 `/DELAYLOAD` 링커 옵션은 Microsoft PE/COFF 공식 문서 및 Visual C++ 공식 문서(Delay Loading DLLs) 기준이다.
- `__delayLoadHelper2`의 내부 동작(`LoadLibraryExW` + `GetProcAddress` 호출 후 IAT 슬롯 패치)은 Microsoft 공식 문서 및 Visual C++ 런타임 소스(delayimp.h/delayhlp.cpp) 공개 자료 기준이다.
- 미니 예제의 구체적 DLL/함수 이름과 시나리오는 설명을 위해 구성한 예시다(2026-09-08 기준 서술).
