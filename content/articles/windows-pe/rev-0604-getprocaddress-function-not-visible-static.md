---
id: REV-0604
title: "GetProcAddress로 얻은 함수가 정적분석에서 안 보일 때"
slug: "rev-0604-getprocaddress-function-not-visible-static"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords:
  - GetProcAddress 동적 해석
  - call eax 함수명 추적
  - IAT에 없는 API
  - Execute till return
  - API Hashing 대응
  - IDA 수동 이름 붙이기
aliases:
  - call 대상이 레지스터라 함수명을 모름
  - GetProcAddress 반환값 추적
  - 동적으로 로드된 API 이름 확인
  - Import에 없는데 실제로 호출되는 API
symptom_keywords:
  - Imports 탭에 함수가 없음
  - call eax 밖에 안 보임
  - GetProcAddress 두 번째 인자가 계산됨
  - IDA에서 함수 이름이 sub_로만 나옴
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
IDA의 Imports 탭에는 없는데 실제로는 어떤 Win32 API가 쓰이고 있다면, 그 함수는 `LoadLibrary` + `GetProcAddress`로 런타임에 동적으로 찾아진 뒤 `call eax`/`call rax`처럼 레지스터 간접 호출로 실행되고 있을 가능성이 높으므로, 정적 분석만으로는 함수 이름을 알 수 없고 `GetProcAddress` 호출 지점에서 두 번째 인자(함수 이름 문자열)와 반환값(함수 포인터)을 동적으로 확인해 IDA에 수동으로 이름을 붙여야 한다.

## 언제 검색해야 하나
- IDA Imports 탭을 아무리 뒤져도 없는데, 프로그램 동작상 분명히 특정 Win32 API(파일 입출력, 암호화, 네트워크 등)를 쓰는 것 같을 때
- 디스어셈블리에 `call eax`, `call rax`, `call [ebp-4]`처럼 대상이 상수 주소가 아니라 레지스터/메모리 간접 호출로만 나올 때
- `LoadLibraryA`/`GetProcAddress` 임포트는 있는데 `GetProcAddress`의 두 번째 인자(함수 이름)가 상수 문자열이 아니라 런타임에 조립/복호화되는 것처럼 보일 때

## 가장 먼저 할 것
IDA Imports 탭에서 `GetProcAddress`를 찾아 크로스 레퍼런스(`X`)를 건다. 각 호출 지점에서 두 번째 인자(`lpProcName`)가 바로 옆에 상수 문자열로 있는지부터 확인한다 — 상수 문자열이라면 정적으로 바로 답이 나오는 가장 쉬운 경우다.

## 핵심 개념
`GetProcAddress`는 다음 시그니처를 가진다.

```c
FARPROC GetProcAddress(
    HMODULE hModule,     // LoadLibrary(Ex)로 얻은 모듈 핸들
    LPCSTR  lpProcName    // 찾으려는 함수의 이름(ANSI 문자열) 또는 서수(MAKEINTRESOURCE로 만든 값)
);
```

반환값은 찾은 함수의 실제 시작 주소(`FARPROC`, 함수 포인터)이며, 실패 시 `NULL`이다. 이렇게 얻은 함수 포인터는 대개 지역/전역 변수에 저장되었다가 이후 `call` 명령의 대상으로 쓰인다.

이 패턴이 정적 분석을 어렵게 만드는 이유는, PE의 Import Address Table(IAT)에는 처음부터 알려진(빌드 시점에 링커가 기록해둔) 함수만 이름과 함께 채워지기 때문이다. `LoadLibrary`+`GetProcAddress`로 런타임에 찾은 함수는 IAT에 등록되지 않으므로, IDA는 그 `call` 명령의 대상이 무엇인지 정적으로 전혀 알 수 없다 — 그냥 "레지스터에 담긴 어떤 주소로 점프한다"는 것만 보인다.

난이도는 다음 순서로 올라간다.
1. **가장 쉬운 경우**: `GetProcAddress(hKernel32, "CreateFileW")`처럼 함수 이름이 그 호출 지점 바로 근처에 상수 문자열로 있다. IDA Strings 창(`Shift+F12`)에서 바로 찾을 수 있다.
2. **중간 경우**: 함수 이름 문자열이 XOR 등으로 간단히 인코딩되어 있거나, 여러 조각으로 나뉘어 런타임에 `strcat`처럼 이어붙여진다.
3. **가장 어려운 경우**: 함수 이름 문자열 자체가 아예 없고, 대신 함수 이름의 해시값(체크섬)만 상수로 박혀 있어서, PE의 Export Table을 직접 순회하며 각 export 이름의 해시를 계산해 비교하는 방식(API Hashing)을 쓴다. 이 경우 임포트 목록에 `GetProcAddress`조차 없을 수 있다.

## 화면/코드에서 보이는 징후
- `call eax`, `call rax`, `call [ebp-0xC]`처럼 호출 대상이 상수 주소가 아니다.
- 그 레지스터/변수에 값을 채우는 코드를 거슬러 올라가면 `GetProcAddress`(또는 그 반환값을 저장하는 전역 함수 포인터 변수) 호출로 이어진다.
- IDA의 Hex-Rays 디컴파일(`F5`) 결과에 `(*(void (__stdcall **)(...))v3)(...)` 같은 함수 포인터 간접 호출 형태로 나타난다.

## 단계별 절차
1. IDA에서 `GetProcAddress` 임포트에 `X`로 크로스 레퍼런스를 걸어 모든 호출 지점을 나열한다.
2. 각 호출 지점 직전에서 두 번째 인자(`lpProcName`)를 확인한다. 상수 문자열이면 바로 함수 이름을 알 수 있으므로 3~6번을 건너뛴다.
3. 문자열이 상수가 아니라면(조립/복호화됨), x64dbg에서 `bp GetProcAddress`를 걸고 실행한다.
4. 브레이크포인트가 걸리면 x64는 `RDX`, x86은 `[esp+8]`에서 `lpProcName` 문자열 포인터를 확인하고 "Follow in Dump"로 실제 함수 이름을 읽는다.
5. `Ctrl+F9`(Execute till return) 또는 함수 리턴 위치에 임시 브레이크포인트를 걸어 반환 직후 상태로 이동한다. 반환값(x64는 `RAX`, x86은 `EAX`)이 바로 그 함수의 실제 주소다.
6. 이 주소를 기억해두고(또는 그 주소가 저장되는 전역 변수를 IDA에서 찾아), IDA로 돌아가 그 전역 변수에 `N`(Rename)으로 `pCreateFileW`처럼 의미 있는 이름을 붙인다. 이렇게 하면 이후 그 변수를 참조하는 모든 `call` 지점에 자동으로 의미가 부여되어 교차 참조가 훨씬 읽기 쉬워진다.
7. 함수 이름 문자열조차 안 보이고 해시값만 있다면 API Hashing 패턴을 의심하고, 해시 알고리즘과 대조 대상(Export Table 순회)을 별도로 분석해야 한다.

## 명령어/단축키
- IDA: `X`(크로스 레퍼런스), `Shift+F12`(Strings 창), `N`(Rename)
- x64dbg: `bp GetProcAddress`, `Ctrl+F9`(Execute till return), 레지스터/스택 값 우클릭 → "Follow in Dump"

## 출력 해석
- `GetProcAddress` 반환값(`EAX`/`RAX`)이 `0`이면 해당 이름의 함수를 찾지 못한 것이다 — 오타이거나, DLL이 로드되지 않았거나, 이름이 잘못 복호화된 것일 수 있다.
- 반환값이 어떤 DLL의 모듈 베이스 근처(가까운 주소 범위) 안에 있다면 정상적으로 그 DLL 안의 함수 주소를 얻은 것이다. x64dbg Memory Map(`Alt+M`)에서 그 주소가 어느 모듈 범위에 속하는지 확인할 수 있다.
- 이후 `call` 지점에서 이 주소로 정확히 점프하는지 확인되면, 그 함수가 실제로 실행되고 있다는 것이 검증된 것이다.

## 흔한 실수
- IDA Imports 탭에 없다는 이유만으로 "이 프로그램은 이 API를 쓰지 않는다"고 성급하게 결론짓는 것 — 동적 해석 가능성을 항상 염두에 둬야 한다.
- `GetProcAddress` 반환값을 저장하는 전역 변수에 이름을 붙이지 않고 매번 주소로만 추적해서, 나중에 같은 작업을 반복하는 것.
- API 이름 문자열이 암호화되어 있는데 정적으로만 찾으려다 시간을 낭비하는 것 — 이런 경우는 동적으로 반환값을 확인하는 것이 훨씬 빠르다.
- API Hashing 패턴(해시 비교, Export Table 수동 순회)을 일반적인 `GetProcAddress` 사용과 혼동해서 같은 방법으로 접근하려다 막히는 것 — 이 경우는 해시 알고리즘 자체를 별도로 분석해야 한다.

## 막혔을 때 다음 체크
- 함수 이름 문자열조차 안 보이고 해시 상수만 있다면 API Hashing 패턴을 의심해야 한다(관련 개념은 windows-pe 카테고리의 API Hashing 관련 글을 참고).
- 이렇게 찾은 함수가 파일/암호화 관련이라면 → REV-0140(Crypt API BCrypt API 흔적 찾기)과 REV-0139(CreateFile ReadFile WriteFile)를 참고한다.
- API 이름 자체를 보고도 기능이 낯설다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.

## 미니 예제
IDA에서 `call eax` 명령을 발견했지만 `eax`가 어디서 오는지 바로 안 보였다. x64dbg에서 `bp GetProcAddress`를 걸고 실행하니 다음과 같이 멈췄다.

```text
RCX = 0x00007FFA12340000   (hModule, kernel32.dll 베이스)
RDX = 0x0000004F8A2B10A0   ("CreateFileW" 문자열 포인터)
```

`Ctrl+F9`로 함수 리턴까지 실행하자 `RAX = 0x00007FFA1235A210`이 반환되었다. 이 주소가 저장되는 전역 변수를 IDA에서 찾아 `g_pCreateFileW`로 이름을 바꾸자, 이후 `call [g_pCreateFileW]` 형태로 표시된 모든 지점이 `CreateFileW` 호출이라는 것이 한눈에 보이게 되었다.

## 관련 글
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0140 — Crypt API BCrypt API 흔적 찾기

## 출처/검증
- `GetProcAddress`의 함수 시그니처, 인자, 반환값 의미는 Microsoft Win32 API 공식 문서 기준이다.
- IAT에 등록되지 않은 동적 해석 함수가 정적 분석 도구에서 이름 없이 간접 호출로만 나타난다는 설명은 일반적인 PE Import 메커니즘과 리버스 엔지니어링 실무 관행 기준이다.
- x64dbg의 "Execute till return"(`Ctrl+F9`) 기능은 x64dbg 공식 문서 기준이다.
- 2026-09-08 기준 서술.
