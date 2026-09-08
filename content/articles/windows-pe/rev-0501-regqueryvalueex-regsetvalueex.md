---
id: REV-0501
title: "WinAPI 레지스트리 함수 사전: RegQueryValueEx RegSetValueEx"
slug: "rev-0501-regqueryvalueex-regsetvalueex"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["RegQueryValueExW", "RegSetValueExW", "REG_SZ", "REG_DWORD", "REG_BINARY", "레지스트리 값 읽기 쓰기"]
aliases: ["RegQueryValueEx 함수 사전", "RegSetValueEx 함수 사전", "레지스트리 값 조회 API", "REG_DWORD REG_SZ"]
symptom_keywords: ["RegQueryValueEx 인자 순서를 모르겠다", "REG_SZ REG_DWORD 값이 헷갈린다", "레지스트리에서 어떤 값을 읽는지 확인하고 싶다", "RegSetValueEx로 자동실행을 등록하는 코드"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`RegQueryValueExW`는 이미 열린 `HKEY` 안의 명명된 값(value)을 읽고, `RegSetValueExW`는 그 값을 쓰는 대칭 함수로, 두 함수 모두 "값의 타입"(`REG_SZ`, `REG_DWORD`, `REG_BINARY` 등)을 나타내는 인자를 따로 갖고 있어 이 타입 코드를 알아야 버퍼에 담긴 바이트를 올바르게 해석할 수 있다.

## 언제 검색해야 하나
- `RegQueryValueExW` 호출에서 실제로 어떤 값(문자열/DWORD/바이너리)을 읽어오는지 데이터 타입을 판별해야 할 때
- `RegSetValueExW`로 레지스트리에 값을 쓰는 코드(자동실행 등록, 설정 저장, 라이선스 키 저장 등)를 분석할 때
- `REG_SZ`, `REG_DWORD`, `REG_BINARY`, `REG_MULTI_SZ` 같은 타입 상수값이 기억나지 않을 때
- 버퍼 크기 인자(`lpcbData`)를 in/out 어느 쪽으로 써야 하는지 헷갈릴 때

## 핵심 개념

**`RegQueryValueExW`** — 값을 읽는다.
```c
LSTATUS RegQueryValueExW(
    HKEY    hKey,
    LPCWSTR lpValueName,
    LPDWORD lpReserved,     // 항상 NULL
    LPDWORD lpType,         // 값의 타입이 저장될 주소(REG_SZ 등)
    LPBYTE  lpData,         // 실제 데이터가 채워질 버퍼
    LPDWORD lpcbData        // in: 버퍼 크기 / out: 실제 데이터 크기
);
```
`lpcbData`는 **입력이자 출력**이다 — 호출 전에는 `lpData` 버퍼의 크기를 알려주는 용도로 채워야 하고, 함수가 끝나면 실제로 복사된 바이트 수로 덮어써진다. `lpData`를 `NULL`로 넘기면 값을 실제로 복사하지 않고 타입과 필요한 크기만 얻을 수 있어, "버퍼를 미리 얼마나 할당해야 하는지 모를 때" 먼저 크기 조회용으로 한 번, 버퍼를 할당한 뒤 실제 조회용으로 한 번, 총 두 번 호출하는 패턴이 매우 흔하다.

**`RegSetValueExW`** — 값을 쓴다.
```c
LSTATUS RegSetValueExW(
    HKEY       hKey,
    LPCWSTR    lpValueName,
    DWORD      Reserved,   // 항상 0
    DWORD      dwType,     // 쓰려는 값의 타입
    const BYTE *lpData,    // 쓸 데이터
    DWORD      cbData      // 데이터 크기(바이트)
);
```
`RegQueryValueExW`와 인자가 거의 대칭이지만, `RegSetValueExW`의 `cbData`는 순수 입력값(쓸 크기)이라는 점이 `lpcbData`(in/out)와 다르다.

**주요 값 타입(`dwType`/`lpType`)**

| 값 | 이름 | 의미 |
|---|---|---|
| 1 | `REG_SZ` | NULL 종료 유니코드 문자열 |
| 2 | `REG_EXPAND_SZ` | 환경변수(`%windir%` 등)를 포함할 수 있는 문자열 |
| 3 | `REG_BINARY` | 임의의 바이너리 데이터 |
| 4 | `REG_DWORD` | 32비트 정수(리틀 엔디안) |
| 7 | `REG_MULTI_SZ` | NULL로 구분된 문자열 여러 개, 마지막은 이중 NULL |
| 11 | `REG_QWORD` | 64비트 정수 |

## 화면/코드에서 보이는 징후
- `RegQueryValueExW`가 같은 `lpValueName`으로 **두 번** 호출되는 패턴 — 첫 번째는 `lpData=NULL`로 크기만 얻고, 두 번째는 그 크기로 할당한 버퍼를 넘겨 실제 값을 읽는다.
- `lpType`이 가리키는 값을 `cmp`로 `4`(REG_DWORD)와 비교한 뒤 분기하는 코드 — 값의 타입에 따라 처리 로직이 달라짐을 의미.
- `RegSetValueExW` 호출 직전에 문자열 리터럴이나 계산된 버퍼가 `lpData`로 들어가는 패턴 — 이 시점 버퍼를 보면 레지스트리에 실제로 쓰이는 값을 그대로 가로챌 수 있다.

## 가장 먼저 할 것
`lpValueName`(값 이름 문자열)과 `lpType`/`dwType`(값 타입) 두 가지를 먼저 확인한다. 이름과 타입을 알면 `lpData` 버퍼를 어떻게 해석해야 할지(문자열인지, 4바이트 정수인지) 바로 정해진다.

## 단계별 절차
1. IDA에서 `RegQueryValueExW`/`RegSetValueExW` 호출을 `X`(xref)로 나열한다.
2. `F5`로 디컴파일해 `lpValueName` 문자열과 타입 인자를 확인한다.
3. x64dbg에서 `bp RegQueryValueExW` 후 `RDX`(lpValueName, Follow in Dump로 문자열 확인)를 본다.
4. `Ctrl+F9`로 리턴까지 실행한 뒤, 호출 전 `R8`/`R9`(또는 스택)로 넘겼던 `lpType`/`lpData` 주소를 다시 열어 실제로 채워진 타입과 값을 확인한다. `REG_SZ`면 UTF-16 문자열로, `REG_DWORD`면 4바이트 리틀 엔디안 정수로 해석한다.

## 명령어/단축키
- x64dbg: `bp RegQueryValueExW`, `bp RegSetValueExW`, `Ctrl+F9`(리턴까지 실행)
- IDA: `X`(xref), `F5`(디컴파일)

## 출력 해석
- 반환값 `0`(`ERROR_SUCCESS`)이 성공, 그 외는 실패(레지스트리 API 공통 규칙, REV-0500 참고).
- `lpType`에 채워진 값이 `4`(`REG_DWORD`)인데 코드가 `lpData`를 문자열처럼 취급한다면 분석이 잘못된 것이니 타입을 다시 확인해야 한다.
- `REG_BINARY` 타입인 경우 `lpData`의 바이트를 곧바로 해석할 수 없는 경우가 많다 — 별도의 커스텀 포맷(설정 구조체, 암호화된 블롭 등)일 가능성을 염두에 둔다.

## 흔한 실수
- `lpcbData`(`RegQueryValueExW`)가 in/out 겸용이라는 것을 모르고, 호출 전 버퍼 크기를 세팅하지 않아 `ERROR_MORE_DATA`(234)를 받는 것.
- `RegSetValueExW`의 `cbData`에 문자열 길이를 셀 때 NULL 종료 문자를 빼먹어서 레지스트리에 잘린 문자열이 저장되는 실수를 놓치는 것(문자열은 NULL 포함 바이트 수를 넣는 것이 정석).
- 타입을 확인하지 않고 `lpData`를 무조건 문자열로 가정해 덤프를 읽는 것 — `REG_DWORD`/`REG_BINARY`는 문자열이 아니다.

## 막혔을 때 다음 체크
- 값을 읽기 전에 키를 여는 단계가 궁금하면 → REV-0500 확인.
- 다 쓴 키를 닫거나 삭제하는 API가 궁금하면 → REV-0502 확인.
- 레지스트리에 저장된 값이 암호화되어 있는 것 같다면 → REV-0140(Crypt API BCrypt API 흔적 찾기)을 참고.

## 미니 예제
```c
DWORD type, size = 0;
RegQueryValueExW(hKey, L"InstallPath", NULL, &type, NULL, &size); // 1차: 크기만 조회
BYTE* buf = malloc(size);
RegQueryValueExW(hKey, L"InstallPath", NULL, &type, buf, &size);  // 2차: 실제 값 조회
// type == REG_SZ이면 buf를 UTF-16 문자열로 해석
```
이 "두 번 호출" 패턴은 레지스트리 값 크기를 미리 알 수 없을 때 매우 흔히 쓰이며, 디스어셈블리에서 같은 `lpValueName`으로 `RegQueryValueExW`가 연속 두 번 호출되는 것으로 쉽게 식별할 수 있다.

## 관련 글
- REV-0500 — WinAPI 레지스트리 함수 사전: RegOpenKeyEx RegCreateKeyEx
- REV-0502 — WinAPI 레지스트리 함수 사전: RegCloseKey RegDeleteKey
- REV-0140 — Crypt API BCrypt API 흔적 찾기

## 출처/검증
- `RegQueryValueExW`/`RegSetValueExW` 시그니처, `lpcbData`의 in/out 동작, `REG_SZ`/`REG_DWORD`/`REG_BINARY` 등 타입 상수값은 Microsoft Win32 API 공식 문서 기준(2026-09-08 확인 서술).
