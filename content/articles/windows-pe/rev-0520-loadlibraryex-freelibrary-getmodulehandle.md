---
id: REV-0520
title: "WinAPI 모듈 함수 사전: LoadLibraryEx FreeLibrary GetModuleHandle"
slug: "rev-0520-loadlibraryex-freelibrary-getmodulehandle"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["LoadLibraryExW", "FreeLibrary", "GetModuleHandleW", "DLL 로드", "동적 링크"]
aliases: ["DLL 동적 로드 함수", "모듈 핸들 조회", "런타임 DLL 로딩"]
symptom_keywords: ["LoadLibrary와 LoadLibraryEx 차이를 모르겠다", "GetModuleHandle이 뭔지 모르겠다", "DLL을 언제 로드하는지 찾고 싶다", "FreeLibrary를 왜 호출하는지 모르겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LoadLibraryExW`는 실행 중에 DLL을 프로세스 주소 공간에 새로 로드하고, `GetModuleHandleW`는 이미 로드된 모듈의 베이스 주소를 이름으로 조회하며, `FreeLibrary`는 로드된 DLL의 참조 카운트를 줄여 필요 없으면 언로드하는 함수로, 이 세 함수는 임포트 테이블에 없는 DLL/함수를 런타임에 동적으로 가져오는 "수동 임포트" 패턴을 분석할 때 반드시 확인해야 한다.

## 언제 검색해야 하나
- 임포트 테이블에는 몇 개 함수만 보이는데 실제로는 훨씬 많은 기능이 있어서, 런타임에 DLL을 동적으로 로드하는 것으로 의심될 때
- 패킹/난독화된 바이너리가 `kernel32.dll`, `advapi32.dll` 등을 문자열로 만들어 `LoadLibraryExW`로 로드하는 패턴을 찾을 때
- 특정 DLL이 이미 프로세스에 로드되어 있는지(가상 머신 탐지, 특정 보안 툴 탐지 등) `GetModuleHandleW`로 검사하는 코드를 분석할 때
- 플러그인/애드온 구조처럼 실행 중 필요한 시점에만 모듈을 붙였다 떼는 로직을 볼 때

## 핵심 개념
```c
HMODULE LoadLibraryExW(
    LPCWSTR lpLibFileName, // 1. 로드할 DLL 경로 또는 이름
    HANDLE  hFile,         // 2. 예약, 항상 NULL
    DWORD   dwFlags        // 3. LOAD_LIBRARY_AS_DATAFILE 등 로드 방식 플래그
);

HMODULE GetModuleHandleW(LPCWSTR lpModuleName); // NULL이면 현재 실행 파일(EXE) 자신의 핸들 반환

BOOL FreeLibrary(HMODULE hLibModule);
```

`LoadLibraryExW`(기본형 `LoadLibraryW`도 동일 계열)는 DLL을 디스크에서 찾아 프로세스 주소 공간에 매핑하고, 아직 로드되지 않았다면 그 DLL의 `DllMain`을 `DLL_PROCESS_ATTACH`로 호출한 뒤 모듈 베이스 주소(`HMODULE`)를 반환한다. 이미 로드되어 있다면 다시 매핑하지 않고 참조 카운트만 증가시켜 같은 핸들을 반환한다. `dwFlags`에 `LOAD_LIBRARY_AS_DATAFILE`(0x2)을 주면 코드를 실행하지 않고 리소스만 읽을 목적으로 매핑할 수 있다(안전하게 문자열/아이콘만 추출할 때 사용).

`GetModuleHandleW`는 새로 로드하지 않고 "이미 로드되어 있는가"만 확인한다. 인자로 `NULL`을 넘기면 현재 프로세스의 EXE 자신의 베이스 주소를 반환하는데, 이는 셸코드나 자가 수정 코드에서 자기 자신의 이미지 베이스를 얻는 전형적인 방법이다.

`FreeLibrary`는 `LoadLibraryExW`로 늘어난 참조 카운트를 하나 줄이며, 카운트가 0이 되면 실제로 언로드되고 `DllMain`이 `DLL_PROCESS_DETACH`로 호출된다. `GetModuleHandleW`로 얻은 핸들은 참조 카운트를 늘리지 않았으므로 `FreeLibrary`로 짝을 맞추면 안 된다.

`LoadLibraryExW`로 로드한 뒤 그 안의 함수 포인터를 얻으려면 REV-0129에서 다룬 `GetProcAddress`가 바로 이어서 등장하는 것이 정석 패턴이다.

## 화면/코드에서 보이는 징후
- 문자열 참조 목록에서 `"kernel32.dll"`, `"user32.dll"`, `"advapi32.dll"` 같은 DLL 이름 문자열이 있고, 바로 아래에서 `LoadLibraryExW` 또는 `LoadLibraryW`로 이어지는 코드
- `LoadLibraryExW` 반환값(`EAX`/`RAX`)이 곧이어 `GetProcAddress`의 첫 번째 인자로 들어가는 패턴(수동 API 해석)
- `GetModuleHandleW(NULL)` 호출 뒤 반환값을 이용해 자기 자신의 PE 헤더(DOS 헤더, `MZ` 시그니처)를 파싱하는 코드
- 함수 종료 직전 `FreeLibrary` 호출이 `LoadLibraryExW`와 짝을 이루는 패턴

## 가장 먼저 할 것
1. `LoadLibraryExW`의 첫 번째 인자(DLL 이름/경로 문자열)부터 확인해 어떤 모듈을 로드하는지 파악한다.
2. 반환값이 바로 이어서 `GetProcAddress`에 쓰이는지 확인해서, 수동으로 어떤 API를 가져오는지 추적한다(REV-0129와 연계).
3. `GetModuleHandleW(NULL)`이면 자기 자신의 베이스를 얻는 것이므로, 이후 PE 헤더 파싱이나 셸코드/인젝션 관련 코드가 이어질 가능성을 염두에 둔다.

## 단계별 절차
**1) 정적 분석(IDA)**
- 임포트 목록에서 `LoadLibraryExW`/`GetModuleHandleW`를 찾아 `X`로 교차 참조한다.
- 첫 번째 인자로 들어가는 문자열이 직접 리터럴이 아니라 런타임에 조합(XOR 디코딩 등)되는 경우, 문자열이 만들어지는 지점까지 거슬러 올라가야 한다(패킹/난독화 바이너리에서 흔함).

**2) 동적 분석(x64dbg)**
- `bp LoadLibraryExW`로 브레이크포인트를 걸고 실행한다.
- x64에서 `RCX`=lpLibFileName. Follow in Dump, UTF-16으로 전환해 로드하려는 DLL 이름을 확인한다.
- 함수 리턴 후(F8) `RAX`가 로드된 모듈의 베이스 주소다. Memory Map 창(`Alt+M`)에서 이 주소가 새로운 모듈로 나타나는지 확인한다.

## 명령어/단축키
- x64dbg: `bp LoadLibraryExW`, `bp LoadLibraryW`, `bp GetModuleHandleW`, `bp FreeLibrary`, `bp GetProcAddress`
- x64dbg: `Alt+M`(Memory Map, 로드된 모듈 목록 확인)
- IDA: `X`(교차 참조), `F5`(디컴파일)

## 출력 해석
- `LoadLibraryExW` 반환값이 `NULL`이면 로드 실패(파일 없음, 권한 부족, 잘못된 형식 등). `GetLastError()`로 원인 확인 가능.
- `GetModuleHandleW`가 `NULL`을 반환하면 해당 이름의 모듈이 현재 로드되어 있지 않다는 뜻 — 이 값을 조건으로 특정 보안 툴/후킹 DLL의 존재 여부를 검사하는 안티분석 코드가 흔하다.
- `FreeLibrary` 반환값이 0이면 실패(잘못된 핸들 등), 0이 아니면 성공(단, 실제 언로드는 참조 카운트가 0이 될 때만 일어남).

## 흔한 실수
- `GetModuleHandleW`로 얻은 핸들을 `FreeLibrary`로 해제하는 것 — 참조 카운트를 증가시키지 않았으므로 짝이 맞지 않아 다른 코드가 기대하는 모듈이 예기치 않게 언로드될 수 있다.
- `LoadLibraryExW`의 `dwFlags`를 무시하고 항상 코드가 실행된다고 가정하는 것 — `LOAD_LIBRARY_AS_DATAFILE` 플래그가 있으면 `DllMain`이 실행되지 않는다.
- DLL 이름 문자열이 하드코딩되어 있다고만 생각하고, 런타임에 문자열이 디코딩/조합되는 안티분석 패턴을 놓치는 것.
- x86/x64에서 서로 다른 이름의 DLL(`SysWOW64` vs `System32`)이 로드될 수 있다는 점을 간과하는 것.

## 막혔을 때 다음 체크
- 로드된 모듈에서 함수 주소를 얻는 방법이 궁금하면 → REV-0129(GetProcAddress LoadLibrary 동적 API 해석)를 본다.
- 로드된 모듈 목록을 프로세스 관점에서 열거하는 방법이 궁금하면 → REV-0521(EnumProcessModules GetModuleFileName)을 본다.
- 문자열 자체가 암호화/난독화되어 안 보인다면 → REV-0128(Windows 문자열 ASCII와 UTF-16 찾기)을 함께 본다.

## 미니 예제
x64dbg에서 `bp LoadLibraryExW` 후 실행하니 다음처럼 멈췄다.

```text
RCX = 0x00000221A3B02000   (lpLibFileName)
RDX = 0x0000000000000000   (hFile = NULL)
R8  = 0x0000000000000000   (dwFlags = 0)
```

`RCX`를 Follow in Dump, UTF-16으로 보면 `L"advapi32.dll"`이 보인다. 함수 리턴 후 `RAX = 0x00007FFA12340000` 같은 값이 나오면, 이것이 `advapi32.dll`이 매핑된 베이스 주소다. 바로 다음 줄에서 `GetProcAddress(0x00007FFA12340000, "CryptAcquireContextW")`처럼 호출된다면, 이 프로그램이 암호화 관련 API를 임포트 테이블 없이 수동으로 가져와 사용한다는 뜻이다.

참고로 `LoadLibraryExW`의 `lpLibFileName`에 전체 경로가 아니라 파일명만 주어지면(예: `L"advapi32.dll"`), Windows는 정해진 검색 순서(애플리케이션 디렉터리 → 시스템 디렉터리 → 현재 디렉터리 → PATH 환경 변수 등)를 따라 DLL을 찾는다. 이 검색 순서를 악용해 정상 시스템 DLL과 같은 이름의 악성 DLL을 프로그램 실행 파일과 같은 폴더에 놓아 먼저 로드되게 만드는 기법을 "DLL 사이드로딩(DLL side-loading)" 또는 "DLL 하이재킹"이라 부르며, 멀웨어 분석과 CTF의 지속성(persistence) 문제에서 종종 등장하는 주제다.

## 관련 글
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0521 — WinAPI 모듈 함수 사전: EnumProcessModules GetModuleFileName
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기

## 출처/검증
- `LoadLibraryExW`/`GetModuleHandleW`/`FreeLibrary`의 함수 시그니처, 참조 카운트 동작, `LOAD_LIBRARY_AS_DATAFILE` 플래그는 Microsoft Win32 API(동적 연결 라이브러리) 공식 문서 기준이다.
- 위 미니 예제의 주소와 DLL 이름은 설명을 위해 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
