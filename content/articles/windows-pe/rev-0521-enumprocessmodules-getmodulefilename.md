---
id: REV-0521
title: "WinAPI 모듈 함수 사전: EnumProcessModules GetModuleFileName"
slug: "rev-0521-enumprocessmodules-getmodulefilename"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["EnumProcessModules", "GetModuleFileNameW", "Psapi", "모듈 열거", "DLL 목록"]
aliases: ["프로세스 모듈 열거 함수", "로드된 DLL 목록 얻기", "모듈 경로 조회"]
symptom_keywords: ["EnumProcessModules가 뭔지 모르겠다", "GetModuleFileName 인자를 모르겠다", "로드된 DLL 목록을 어떻게 얻는지 모르겠다", "특정 DLL 로드 여부를 검사하는 코드가 궁금하다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`EnumProcessModules`는 지정한 프로세스에 현재 로드되어 있는 모든 모듈(EXE 자신 + 로드된 DLL들)의 핸들 배열을 얻는 함수이고, `GetModuleFileNameW`는 그 핸들로부터 실제 파일 경로 문자열을 얻는 함수로, 두 함수는 짝을 이루어 "이 프로세스에 어떤 DLL들이 붙어 있는가"를 스캔하는 코드(디버거 탐지, 후킹 DLL 탐지, 자기 자신의 경로 확인)에서 함께 등장한다.

## 언제 검색해야 하나
- 프로그램이 자신에게 로드된 DLL 목록을 순회하며 특정 이름(예: 후킹 DLL, 백신 모듈, 가상화 툴 DLL)을 찾는 코드를 분석할 때
- 임포트 목록에서 `EnumProcessModules`, `EnumProcessModulesEx`, `GetModuleFileNameW`, `GetModuleFileNameExW`를 발견했을 때
- 프로그램이 자기 자신의 실행 경로(EXE 파일 경로)를 얻어서 검증/변조 탐지에 사용하는 코드를 볼 때
- 원격 프로세스(다른 PID)에 인젝션된 DLL 목록을 확인하는 도구 동작을 분석할 때

## 핵심 개념
```c
BOOL EnumProcessModules(
    HANDLE  hProcess,     // 1. 대상 프로세스 핸들(자기 자신이면 GetCurrentProcess())
    HMODULE *lphModule,   // 2. 모듈 핸들이 채워질 배열 주소
    DWORD   cb,           // 3. 배열의 바이트 크기
    LPDWORD lpcbNeeded    // 4. 실제로 필요한(또는 채워진) 바이트 크기
);

DWORD GetModuleFileNameW(
    HMODULE hModule,  // 1. 모듈 핸들(NULL이면 현재 EXE 자신)
    LPWSTR  lpFilename,// 2. 경로가 채워질 버퍼
    DWORD   nSize      // 3. 버퍼 크기(문자 수)
);

// 다른 프로세스의 모듈 경로를 얻을 때는 Psapi 버전을 사용:
DWORD GetModuleFileNameExW(HANDLE hProcess, HMODULE hModule, LPWSTR lpFilename, DWORD nSize);
```

`EnumProcessModules`(및 확장판 `EnumProcessModulesEx`)는 `Psapi.dll`(또는 `Kernel32.dll` 내부로 통합된 최신 버전)이 제공하며, 대상 프로세스에 로드된 모든 모듈의 `HMODULE`(=베이스 주소) 목록을 배열로 채워준다. 일반적인 사용 패턴은 먼저 `cb=0`으로 호출해 `lpcbNeeded`로 필요한 크기를 얻은 뒤, 그 크기만큼 버퍼를 할당해 다시 호출하는 2단계 방식이다.

얻은 `HMODULE` 배열의 각 원소를 `GetModuleFileNameW`(자기 프로세스) 또는 `GetModuleFileNameExW`(다른 프로세스, `hProcess` 인자 추가)에 넘기면 해당 모듈의 전체 경로 문자열을 얻을 수 있다. 배열의 첫 번째 원소(`lphModule[0]`)는 관례적으로 프로세스 자신의 EXE 모듈이다.

이 조합은 "현재 프로세스에 로드된 DLL을 하나씩 순회하며 이름을 비교"하는 루프 형태로 매우 자주 나타나며, CTF/멀웨어 분석에서는 디버거(`x64dbg.dll`, `x32dbg.dll` 등은 실제로 로드되지 않지만 특정 후킹/인젝션 DLL의 파일명, 예: `easyhook`, `cheatengine` 관련 모듈)를 탐지하는 안티치트/안티디버깅 로직에서 자주 목격된다.

## 화면/코드에서 보이는 징후
- `EnumProcessModules`가 두 번 호출되는 패턴(첫 번째는 크기 확인용 `cb=0`, 두 번째는 실제 채우기용)
- 반환된 `HMODULE` 배열을 `for` 루프로 순회하며 각 원소에 `GetModuleFileNameW`를 호출하는 코드
- 얻은 파일명 문자열을 `wcsstr`/`wcscmp`(REV-0516)로 특정 이름과 비교하는 코드 — 특정 DLL 존재 여부 검사의 전형적 형태
- 배열 첫 원소만 별도로 써서 자기 자신의 EXE 경로를 얻는 짧은 코드(모듈 열거 없이 `GetModuleFileNameW(NULL, ...)` 한 줄로 끝나는 경우도 많음 — 이 경우가 훨씬 흔하고 간단하다)

## 가장 먼저 할 것
1. `GetModuleFileNameW`의 첫 번째 인자가 `NULL`인지 확인한다. `NULL`이면 단순히 자기 자신의 EXE 경로를 얻는 것뿐이므로 열거 로직 전체를 볼 필요가 없다.
2. `EnumProcessModules`가 등장하면 루프 안에서 비교되는 문자열(원하는 DLL 이름)이 무엇인지부터 찾는다.
3. `hProcess` 인자가 `GetCurrentProcess()`(pseudo-handle, 값은 `-1`)인지 `OpenProcess`로 얻은 다른 프로세스 핸들인지 구분한다.

## 단계별 절차
**1) 정적 분석(IDA)**
- 임포트 목록에서 `EnumProcessModules`(또는 `K32EnumProcessModules`) 및 `GetModuleFileNameW`를 찾아 `X`로 교차 참조한다.
- `F5`로 디컴파일해 루프 구조와 비교 대상 문자열(주로 `L".dll"`로 끝나는 리터럴)을 확인한다.

**2) 동적 분석(x64dbg)**
- `bp GetModuleFileNameW`로 브레이크포인트를 걸고 실행을 반복(F9)하면서 매 호출마다 `RCX`(hModule)와 리턴 후 채워진 버퍼(`RDX`가 가리키는 곳)를 확인해 어떤 모듈들이 순회되는지 기록한다.
- 비교 로직이 있는 지점에 조건부 브레이크포인트를 걸어 특정 DLL 이름이 감지되었을 때만 멈추게 할 수도 있다.

## 명령어/단축키
- x64dbg: `bp EnumProcessModules`, `bp GetModuleFileNameW`, `bp GetModuleFileNameExW`
- x64dbg: `Alt+M`(Memory Map)로 실제 로드된 모듈 목록을 직접 대조
- IDA: `X`(교차 참조), `F5`(디컴파일)

## 출력 해석
- `EnumProcessModules` 반환값이 `FALSE`면 실패(잘못된 프로세스 핸들, 권한 부족 등).
- `lpcbNeeded`가 `cb`보다 크면 버퍼가 부족했다는 뜻 — 정상적인 프로그램은 이 값을 보고 버퍼를 다시 할당해 재호출한다.
- `GetModuleFileNameW` 반환값은 실제로 복사된 문자 수(NUL 제외)이며, 버퍼가 부족하면 `nSize`와 같은 값을 반환하고 `GetLastError()`가 `ERROR_INSUFFICIENT_BUFFER`(122)를 나타낸다.

## 흔한 실수
- `EnumProcessModules`를 한 번만 호출하고 크기 확인 단계를 생략해서, 로드된 DLL이 많을 때 버퍼가 잘려 일부 모듈을 놓치는 것(분석 대상 프로그램의 버그일 수도 있고, 분석자가 이 흐름을 잘못 이해하는 경우도 있음).
- `GetModuleFileNameW`가 전체 경로를 반환한다는 점을 잊고 파일명만 있을 거라 가정해서 비교 로직(`wcsstr`)이 실패하는 이유를 못 찾는 것 — 실제로는 `C:\Windows\System32\kernel32.dll`처럼 전체 경로가 반환된다.
- 32비트 프로세스가 64비트 프로세스의 모듈을 열거하려 할 때 WOW64 제약으로 실패하는 경우를 놓치는 것.

## 막혔을 때 다음 체크
- 특정 DLL 하나만 로드되어 있는지 빠르게 확인하는 더 가벼운 방법이 궁금하면 → REV-0520(LoadLibraryEx FreeLibrary GetModuleHandle)의 `GetModuleHandleW`를 본다.
- 얻은 문자열이 와이드 문자열이라 비교 방식이 궁금하면 → REV-0516(wcscpy wcscat 계열)을 본다.
- 이런 열거 로직이 안티디버깅/안티후킹 목적이라면 → REV-0130(IsDebuggerPresent 안티디버깅 식별)을 함께 본다.

## 미니 예제
x64dbg에서 `bp GetModuleFileNameW`를 걸고 F9를 여러 번 눌러 호출을 반복하니 다음과 같은 값들이 순서대로 나타났다.

```text
1번째: RCX = 0x00007FF6A1230000  ->  "C:\Users\ctf\Desktop\target.exe"
2번째: RCX = 0x00007FFA12340000  ->  "C:\Windows\System32\ntdll.dll"
3번째: RCX = 0x00007FFA12010000  ->  "C:\Windows\System32\kernel32.dll"
4번째: RCX = 0x000000006A8B0000  ->  "C:\Tools\SomeHookDLL.dll"
```

4번째 항목처럼 시스템 경로(`System32`)가 아닌 낯선 위치의 DLL이 보이면, 프로그램이 바로 다음 코드에서 이 이름을 특정 문자열(`"Hook"`, `"Cheat"` 등)과 비교해 분석 도구를 탐지하려는 의도일 가능성이 높다.

## 관련 글
- REV-0520 — WinAPI 모듈 함수 사전: LoadLibraryEx FreeLibrary GetModuleHandle
- REV-0516 — Windows CRT 문자열 함수 사전: wcscpy wcscat 계열(와이드 문자)
- REV-0130 — IsDebuggerPresent 안티디버깅 식별

## 출처/검증
- `EnumProcessModules`/`GetModuleFileNameW`/`GetModuleFileNameExW`의 함수 시그니처와 2단계 호출 패턴(크기 확인 후 재호출)은 Microsoft Win32 API(Psapi, 프로세스 상태) 공식 문서 기준이다.
- `ERROR_INSUFFICIENT_BUFFER`(122) 등 에러 코드는 Microsoft 시스템 에러 코드 공식 문서 기준이다.
- 위 미니 예제의 경로와 값은 설명을 위해 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
