---
id: REV-0500
title: "WinAPI 레지스트리 함수 사전: RegOpenKeyEx RegCreateKeyEx"
slug: "rev-0500-regopenkeyex-regcreatekeyex"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["RegOpenKeyExW", "RegCreateKeyExW", "HKEY_LOCAL_MACHINE", "HKEY_CURRENT_USER", "KEY_READ", "KEY_WRITE", "레지스트리 API"]
aliases: ["RegOpenKeyEx 함수 사전", "RegCreateKeyEx 함수 사전", "레지스트리 키 열기 API", "HKEY 핸들"]
symptom_keywords: ["RegOpenKeyEx 인자가 몇 개인지 모르겠다", "HKEY_LOCAL_MACHINE 상수값이 뭔지 모르겠다", "RegCreateKeyEx와 RegOpenKeyEx 차이를 모르겠다", "레지스트리에서 값을 읽는 코드를 분석해야 한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`RegOpenKeyExW`는 이미 존재하는 레지스트리 키를 열어 `HKEY` 핸들을 얻고, `RegCreateKeyExW`는 없으면 새로 만들면서 여는 함수로, 두 API 모두 반환값이 다른 Win32 함수처럼 `BOOL`이 아니라 `LSTATUS`(`ERROR_SUCCESS`=0이 성공)라는 점이 리버싱에서 가장 헷갈리기 쉬운 포인트다.

## 언제 검색해야 하나
- 임포트 목록에서 `RegOpenKeyExW`/`RegCreateKeyExW`(또는 `advapi32.dll` 계열)를 발견해 이 프로그램이 어떤 레지스트리 키를 다루는지 알아내야 할 때
- `HKEY_LOCAL_MACHINE`, `HKEY_CURRENT_USER` 같은 루트 키 상수값이 코드에 어떻게 나타나는지 확인하고 싶을 때
- 반환값이 `0`인데 왜 성공인지 헷갈릴 때(다른 API들의 `TRUE`=성공 관례와 반대)
- 악성코드/CTF에서 흔한 "레지스트리에 자동실행 키 등록" 패턴을 분석할 때

## 핵심 개념

**`RegOpenKeyExW`** — 기존 키를 연다.
```c
LSTATUS RegOpenKeyExW(
    HKEY    hKey,
    LPCWSTR lpSubKey,
    DWORD   ulOptions,
    REGSAM  samDesired,
    PHKEY   phkResult
);
```
1. `hKey` — 시작 지점이 되는 루트/부모 키 핸들. 실제 값은 특별한 미리 정의된 상수다.

| 상수 | 값 | 의미 |
|---|---|---|
| `HKEY_CLASSES_ROOT` | 0x80000000 | 파일 연결/COM 등록 정보 |
| `HKEY_CURRENT_USER` | 0x80000001 | 현재 로그인한 사용자 설정 |
| `HKEY_LOCAL_MACHINE` | 0x80000002 | 시스템 전역 설정(관리자 권한 필요할 수 있음) |
| `HKEY_USERS` | 0x80000003 | 모든 사용자 프로필 |
| `HKEY_CURRENT_CONFIG` | 0x80000005 | 현재 하드웨어 구성 |

2. `lpSubKey` — 열고 싶은 하위 키 경로 문자열(예: `L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"`).
3. `ulOptions` — 대개 `0`.
4. `samDesired` — 원하는 접근 권한. `KEY_READ`(0x20019), `KEY_WRITE`(0x20006), `KEY_ALL_ACCESS`(0xF003F)가 가장 흔하다.
5. `phkResult` — 성공 시 새로 얻은 `HKEY` 핸들이 저장될 포인터.

**`RegCreateKeyExW`** — 키가 없으면 새로 만들고, 있으면 그냥 연다.
```c
LSTATUS RegCreateKeyExW(
    HKEY                  hKey,
    LPCWSTR                lpSubKey,
    DWORD                  Reserved,          // 항상 0
    LPWSTR                 lpClass,           // 대개 NULL
    DWORD                  dwOptions,         // 대개 REG_OPTION_NON_VOLATILE(0)
    REGSAM                 samDesired,
    LPSECURITY_ATTRIBUTES  lpSecurityAttributes, // 대개 NULL
    PHKEY                  phkResult,
    LPDWORD                lpdwDisposition    // REG_CREATED_NEW_KEY(1) 또는 REG_OPENED_EXISTING_KEY(2)
);
```
`RegOpenKeyExW`보다 인자가 4개 더 많지만, 앞의 `hKey`/`lpSubKey`와 뒤쪽의 `samDesired`/`phkResult`는 의미가 같다. 마지막 인자 `lpdwDisposition`으로 "새로 만들어졌는지, 원래 있던 걸 열었는지"까지 구분할 수 있다는 점이 `RegOpenKeyExW`와의 핵심 차이다.

**반환값 규칙 — 가장 중요한 함정**
두 함수 모두 반환 타입이 `LSTATUS`(사실상 `LONG`)이며, **`ERROR_SUCCESS`(0)가 성공**이다. 다른 값(대개 `ERROR_FILE_NOT_FOUND`=2 등)이 에러 코드다. `CreateFile`류가 실패값 `-1`, 대부분의 `BOOL` 반환 API가 `0`=실패인 것과 정반대이므로, 디스어셈블리에서 `test eax, eax` 뒤 `jnz`(0이 아니면 점프)가 나오면 이것이 "에러 처리 분기"라는 것을 헷갈리지 않아야 한다.

## 화면/코드에서 보이는 징후
- `push 80000002h`(x86) 또는 `mov ecx, 80000002h`(x64)처럼 `HKEY_LOCAL_MACHINE` 상수가 그대로 인자로 들어감.
- `call RegOpenKeyExW` 직후 `test eax, eax` / `jnz fail_branch`(0이 아니면 실패로 분기) 패턴.
- `RegCreateKeyExW` 호출 뒤 `lpdwDisposition`이 가리키는 값을 `cmp`로 `1`(새로 생성)과 비교하는 코드.

## 가장 먼저 할 것
`hKey`(루트) + `lpSubKey`(경로 문자열) 두 값만 먼저 확인해서 "이 프로그램이 어떤 레지스트리 경로를 건드리는가"부터 파악한다. `Run`/`RunOnce` 키가 보이면 자동 실행 등록을 의심한다.

## 단계별 절차
1. IDA에서 `RegOpenKeyExW`/`RegCreateKeyExW` 호출을 `X`(xref)로 나열한다.
2. `F5`로 디컴파일해 `hKey` 상수(`0x80000002` 등)와 `lpSubKey` 문자열을 확인한다. IDA는 이 상수를 자동으로 `HKEY_LOCAL_MACHINE` 심볼로 표시해주는 경우가 많다(안 되어 있으면 우클릭 → `Use standard symbolic constant`).
3. x64dbg에서 `bp RegOpenKeyExW` 후 `RCX`(hKey), `RDX`(lpSubKey 주소, Follow in Dump로 문자열 확인)를 본다.
4. `Ctrl+F9`로 리턴까지 실행해 `EAX`가 `0`인지 확인하고, `0`이면 5번째(RegOpenKeyEx) 또는 8번째(RegCreateKeyEx) 인자로 넘긴 주소에서 `HKEY` 값을 확인한다 — 이 핸들이 이후 `RegQueryValueEx`/`RegSetValueEx`(REV-0501)의 첫 인자로 이어진다.

## 명령어/단축키
- x64dbg: `bp RegOpenKeyExW`, `bp RegCreateKeyExW`, `Ctrl+F9`(리턴까지 실행)
- IDA: `X`(xref), `F5`(디컴파일), 숫자 우클릭 → `Use standard symbolic constant`

## 출력 해석
- 반환값 `0`(`ERROR_SUCCESS`) = 성공. `2`(`ERROR_FILE_NOT_FOUND`) = 키가 없음. 그 외 값은 `WinError.h` 기준 에러 코드.
- `RegCreateKeyExW`의 `lpdwDisposition` = `1`(`REG_CREATED_NEW_KEY`)이면 이전에 없던 키를 새로 만든 것 — 최초 설치/드롭 시점을 특정하는 단서가 될 수 있다.
- 열린 `HKEY` 핸들 값 자체는 의미 있는 숫자가 아니라 내부 관리용 값이므로, 어떤 키를 열었는지는 반드시 호출 시점의 `lpSubKey` 문자열로 판단해야 한다.

## 흔한 실수
- 반환값을 `BOOL`처럼 취급해서 `0`을 실패로 착각하는 것 — 레지스트리 API는 `0`이 성공이다.
- `HKEY_LOCAL_MACHINE`(0x80000002)과 `HKEY_CURRENT_USER`(0x80000001)를 혼동해서 "시스템 전역 설정"과 "현재 사용자만의 설정"을 반대로 해석하는 것.
- `RegCreateKeyExW`가 항상 새로 만든다고 오해하는 것 — 이미 있으면 그냥 열기만 하며, 이 구분은 `lpdwDisposition`으로만 알 수 있다.

## 막혔을 때 다음 체크
- 열린 키에서 실제 값을 읽고 쓰는 흐름이 궁금하면 → REV-0501 확인.
- 다 쓴 키 핸들을 닫거나 키를 삭제하는 API가 궁금하면 → REV-0502 확인.
- 함수 이름 자체가 낯설다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고.

## 미니 예제
```c
HKEY hKey;
LSTATUS st = RegOpenKeyExW(HKEY_CURRENT_USER,
    L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
    0, KEY_READ, &hKey);
if (st == ERROR_SUCCESS) {
    // hKey를 RegQueryValueEx에 넘겨 자동실행 항목을 읽음
}
```
디스어셈블리에서는 `HKEY_CURRENT_USER`가 `0x80000001` 상수로, `KEY_READ`가 `0x20019`로 그대로 보이며, 반환값 검사는 `test eax, eax` / `jnz fail`(0이 아니면 실패) 형태로 나타난다.

## 관련 글
- REV-0501 — WinAPI 레지스트리 함수 사전: RegQueryValueEx RegSetValueEx
- REV-0502 — WinAPI 레지스트리 함수 사전: RegCloseKey RegDeleteKey
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- `RegOpenKeyExW`/`RegCreateKeyExW` 시그니처, `HKEY_*` 루트 키 상수값, `LSTATUS`/`ERROR_SUCCESS` 반환 규칙은 Microsoft Win32 API 공식 문서(learn.microsoft.com, Windows Registry 관련 문서) 기준(2026-09-08 확인 서술).
