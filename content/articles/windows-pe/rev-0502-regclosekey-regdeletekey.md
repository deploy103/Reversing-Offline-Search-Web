---
id: REV-0502
title: "WinAPI 레지스트리 함수 사전: RegCloseKey RegDeleteKey"
slug: "rev-0502-regclosekey-regdeletekey"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["RegCloseKey", "RegDeleteKeyW", "RegDeleteKeyExW", "RegDeleteValueW", "레지스트리 핸들 닫기", "레지스트리 키 삭제"]
aliases: ["RegCloseKey 함수 사전", "RegDeleteKey 함수 사전", "레지스트리 핸들 정리 API", "RegDeleteValue"]
symptom_keywords: ["RegCloseKey를 언제 호출해야 하는지 모르겠다", "RegDeleteKey와 RegDeleteValue 차이를 모르겠다", "레지스트리 키를 삭제하는 코드를 분석해야 한다", "레지스트리 핸들 누수가 의심된다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`RegCloseKey`는 `RegOpenKeyExW`/`RegCreateKeyExW`로 얻은 `HKEY` 핸들을 정리하는 짝 함수이고, `RegDeleteKeyW`/`RegDeleteKeyExW`는 키 자체(그 안의 모든 값 포함)를 삭제하며, `RegDeleteValueW`는 키는 남기고 특정 값 하나만 지우는 함수라는 세 가지의 "닫기 vs 삭제 범위" 차이를 구분하는 것이 핵심이다.

## 언제 검색해야 하나
- `RegOpenKeyExW`/`RegCreateKeyExW`와 짝을 이루는 `RegCloseKey` 호출 위치를 찾아 핸들 생명주기를 파악해야 할 때
- 레지스트리 키 전체를 지우는 코드(`RegDeleteKeyW`)와 값 하나만 지우는 코드(`RegDeleteValueW`)를 구분해야 할 때
- 악성코드/설치 프로그램이 흔적을 지우는(자동실행 등록 삭제 등) 패턴을 분석할 때
- `RegDeleteKeyExW`에만 있는 `samDesired`(WOW64 관련) 인자가 왜 필요한지 궁금할 때

## 핵심 개념

**`RegCloseKey`** — 열려 있는 `HKEY` 핸들을 닫는다.
```c
LSTATUS RegCloseKey(HKEY hKey);
```
인자가 핸들 하나뿐인 가장 단순한 레지스트리 API다. `CloseHandle`과 비슷한 역할이지만, 레지스트리 핸들 전용으로 별도 함수가 존재한다는 점에 유의한다(일반 `CloseHandle`로 `HKEY`를 닫으면 안 된다). 미리 정의된 루트 키(`HKEY_LOCAL_MACHINE` 등)는 애초에 닫을 필요가 없다 — `RegOpenKeyExW`/`RegCreateKeyExW`로 새로 얻은 핸들만 닫으면 된다.

**`RegDeleteKeyW`** — 하위 키 하나를 통째로 삭제한다.
```c
LSTATUS RegDeleteKeyW(HKEY hKey, LPCWSTR lpSubKey);
```
`lpSubKey`가 가리키는 키와 그 **안에 있는 모든 값**이 함께 삭제된다. 32비트 Windows나 64비트 Windows에서 이 함수는 하위 키가 더 있으면(즉 비어있지 않으면) 실패한다는 제약이 있다 — 하위 트리 전체를 지우려면 `RegDeleteTree`(별도 함수, Vista 이상)가 필요하다.

**`RegDeleteKeyExW`** — WOW64 리다이렉션을 제어할 수 있는 확장판.
```c
LSTATUS RegDeleteKeyExW(HKEY hKey, LPCWSTR lpSubKey, REGSAM samDesired, DWORD Reserved);
```
`samDesired`에 `KEY_WOW64_32KEY`(0x0200) 또는 `KEY_WOW64_64KEY`(0x0100)를 지정해서, 64비트 프로세스가 32비트 전용 레지스트리 뷰(`SOFTWARE\WOW6432Node` 등)를 명시적으로 대상 지정할 수 있다. 32비트 프로그램을 64비트 Windows에서 분석할 때 "코드는 `SOFTWARE\Vendor`를 지웠다는데 실제로는 `SOFTWARE\WOW6432Node\Vendor`가 지워졌다"는 혼란이 이 리다이렉션 때문에 생긴다.

**`RegDeleteValueW`** — 키는 남기고 값 하나만 삭제한다.
```c
LSTATUS RegDeleteValueW(HKEY hKey, LPCWSTR lpValueName);
```
`lpValueName`이 `NULL`이거나 빈 문자열이면 "기본값(default value)"을 삭제한다.

## 화면/코드에서 보이는 징후
- `RegOpenKeyExW`(또는 `RegCreateKeyExW`) 호출 이후 함수 마지막 부분에서 `RegCloseKey`가 짝을 이뤄 호출됨. 짝이 안 보이면 핸들 누수이거나, 다른 분기(에러 경로)에서 닫는 구조일 수 있다.
- `RegDeleteKeyW`/`RegDeleteValueW` 호출 인자로 `Run`/`RunOnce` 하위의 특정 값 이름이 들어가면, 자동실행 등록을 스스로 지우는(흔적 제거) 코드일 가능성.
- 설치 제거(uninstall) 루틴에서 `RegDeleteKeyW`가 여러 번 연속 호출되는 패턴 — 설정 트리를 하나씩 정리하는 것.

## 가장 먼저 할 것
`RegDeleteKeyW`와 `RegDeleteValueW`를 먼저 구분한다 — 전자는 인자가 `(hKey, lpSubKey)`로 키 경로를 받고, 후자는 `(hKey, lpValueName)`으로 이미 열린 키 안의 값 이름을 받는다는 인자 이름의 차이로 즉시 구분할 수 있다.

## 단계별 절차
1. IDA에서 `RegCloseKey`를 `X`(xref)로 찾고, 어떤 `RegOpenKeyExW`/`RegCreateKeyExW` 호출과 데이터 흐름상 짝을 이루는지(같은 `HKEY` 지역변수를 공유하는지) 확인한다.
2. `RegDeleteKeyW`/`RegDeleteValueW` 호출을 찾아 `F5` 디컴파일로 인자(경로 또는 값 이름)를 확인한다.
3. x64dbg에서 `bp RegDeleteKeyW` 후 `RDX`(lpSubKey)를 Follow in Dump해 정확히 어떤 키가 삭제 대상인지 확인한다.
4. `Ctrl+F9`로 리턴까지 실행해 반환값이 `0`(성공)인지, 실패라면 어떤 코드인지(예: `ERROR_ACCESS_DENIED`) 확인한다.

## 명령어/단축키
- x64dbg: `bp RegCloseKey`, `bp RegDeleteKeyW`, `bp RegDeleteValueW`, `Ctrl+F9`(리턴까지 실행)
- IDA: `X`(xref), `F5`(디컴파일)

## 출력 해석
- 반환값 `0`(`ERROR_SUCCESS`)이 성공(레지스트리 API 공통 규칙, REV-0500 참고).
- `RegDeleteKeyW`가 실패하면서 코드가 `ERROR_ACCESS_DENIED`(5)를 반환한다면 권한 부족(관리자 권한 필요한 `HKEY_LOCAL_MACHINE` 하위를 일반 권한으로 시도했을 가능성)이다.
- `RegCloseKey`가 호출 안 되는 함수라도 프로세스가 곧 종료된다면 OS가 알아서 핸들을 정리하므로 실질적 문제는 없다 — 다만 리버싱 관점에서는 "짝이 안 맞는 지점"이 프로그램 흐름을 이해하는 단서가 될 수 있다.

## 흔한 실수
- 레지스트리 핸들(`HKEY`)을 일반 `CloseHandle`로 닫으려는 코드로 착각하는 것 — 반드시 `RegCloseKey`를 써야 하며 코드에서도 그렇게 나타난다.
- `RegDeleteKeyW`가 하위 키가 있는 트리도 통째로 지운다고 오해하는 것 — 실제로는 하위 키가 있으면 실패하며, 트리 전체 삭제는 별도의 `RegDeleteTree` API가 담당한다.
- 32비트 바이너리를 64비트 OS에서 분석하면서 WOW64 리다이렉션을 고려하지 않고 "코드가 지운 경로"와 "실제로 지워진 레지스트리 경로"가 같다고 가정하는 것.

## 막혔을 때 다음 체크
- 이 핸들을 처음 여는 단계가 궁금하면 → REV-0500 확인.
- 삭제 전에 값을 읽거나 쓰는 흐름이 궁금하면 → REV-0501 확인.
- 자동실행 등록/삭제와 관련된 전체 흐름을 다시 정리하고 싶다면 REV-0500부터 순서대로 다시 본다.

## 미니 예제
```c
HKEY hKey;
if (RegOpenKeyExW(HKEY_CURRENT_USER,
        L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
        0, KEY_WRITE, &hKey) == ERROR_SUCCESS) {
    RegDeleteValueW(hKey, L"MyAutorun");  // 값 하나만 삭제, 키 자체는 유지
    RegCloseKey(hKey);
}
```
`RegDeleteValueW`는 `Run` 키 자체를 지우지 않고 그 안의 `MyAutorun` 항목만 제거하므로, 다른 프로그램이 같은 `Run` 키에 등록한 값들은 영향받지 않는다.

## 관련 글
- REV-0500 — WinAPI 레지스트리 함수 사전: RegOpenKeyEx RegCreateKeyEx
- REV-0501 — WinAPI 레지스트리 함수 사전: RegQueryValueEx RegSetValueEx

## 출처/검증
- `RegCloseKey`/`RegDeleteKeyW`/`RegDeleteKeyExW`/`RegDeleteValueW` 시그니처와 동작(하위 키 존재 시 삭제 실패, WOW64 리다이렉션)은 Microsoft Win32 API 공식 문서 기준(2026-09-08 확인 서술).
