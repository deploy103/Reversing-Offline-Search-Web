---
id: REV-0499
title: "WinAPI 파일 입출력 함수 사전: GetFileSize GetFileAttributes"
slug: "rev-0499-getfilesize-getfileattributes"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["GetFileSize", "GetFileSizeEx", "GetFileAttributesW", "GetFileAttributesExW", "INVALID_FILE_SIZE", "INVALID_FILE_ATTRIBUTES", "FILE_ATTRIBUTE_HIDDEN"]
aliases: ["GetFileSize 함수 사전", "GetFileAttributes 함수 사전", "파일 크기 조회 API", "파일 속성 조회 API"]
symptom_keywords: ["GetFileSize 반환값이 이상하다", "GetFileAttributes로 파일 존재 여부를 확인하는 코드", "INVALID_FILE_ATTRIBUTES 값이 뭔지 모르겠다", "FILE_ATTRIBUTE 상수가 헷갈린다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`GetFileSize`/`GetFileSizeEx`는 이미 열린 파일 핸들의 크기를, `GetFileAttributesW`/`GetFileAttributesExW`는 핸들을 열지도 않고 경로만으로 속성(존재 여부 포함)을 알아내는 API로, 후자는 "이 파일이 존재하는가"를 확인하는 가장 가벼운 방법이라 안티디버깅/환경 탐지 코드에서도 자주 재활용된다.

## 언제 검색해야 하나
- `GetFileSize` 반환값이 예상과 달라서 실패값(`INVALID_FILE_SIZE`)인지 정상 크기인지 헷갈릴 때
- `GetFileAttributesW`가 `CreateFile` 없이 갑자기 등장해서 왜 쓰였는지 궁금할 때(파일 존재 확인 패턴)
- `GetFileAttributesExW`의 출력 구조체(`WIN32_FILE_ATTRIBUTE_DATA`) 필드가 뭔지 확인하고 싶을 때
- 속성 비트(`FILE_ATTRIBUTE_HIDDEN`, `FILE_ATTRIBUTE_READONLY` 등) 값이 기억나지 않을 때

## 핵심 개념

**`GetFileSize`** — 열린 핸들 기준 파일 크기(바이트)를 얻는다.
```c
DWORD GetFileSize(HANDLE hFile, LPDWORD lpFileSizeHigh);
```
반환값이 크기의 하위 32비트, `lpFileSizeHigh`가 가리키는 곳에 상위 32비트가 채워진다(4GB 이상 파일 대비). 실패 시 반환값은 `INVALID_FILE_SIZE`(0xFFFFFFFF)인데, 공교롭게도 정상적으로 파일 크기 하위 32비트가 딱 0xFFFFFFFF일 수도 있으므로 실패 여부는 반드시 `GetLastError()`가 `NO_ERROR`(0)인지 함께 확인해야 정확하다. 이런 모호함 때문에 최신 코드는 대부분 아래 `GetFileSizeEx`를 쓴다.

**`GetFileSizeEx`** — 64비트 크기를 한 번에, 모호함 없이 얻는다.
```c
BOOL GetFileSizeEx(HANDLE hFile, PLARGE_INTEGER lpFileSize);
```
`LARGE_INTEGER`(내부적으로 `QuadPart`라는 64비트 정수 필드를 가진 공용체) 포인터에 전체 크기가 그대로 채워진다. 반환값 `BOOL`이 성공/실패를 명확히 알려주므로 `GetFileSize`보다 안전하다.

**`GetFileAttributesW`** — 경로만으로 속성 비트를 얻는다. 핸들을 열 필요가 없다.
```c
DWORD GetFileAttributesW(LPCWSTR lpFileName);
```
실패(경로가 없거나 접근 불가) 시 `INVALID_FILE_ATTRIBUTES`(0xFFFFFFFF)를 반환한다. **가장 흔한 활용법은 파일 존재 여부 확인**이다 — 반환값이 `INVALID_FILE_ATTRIBUTES`가 아니면 그 경로에 뭔가 존재한다는 뜻이다.

주요 속성 비트:

| 값 | 이름 | 의미 |
|---|---|---|
| 0x1 | `FILE_ATTRIBUTE_READONLY` | 읽기 전용 |
| 0x2 | `FILE_ATTRIBUTE_HIDDEN` | 숨김 |
| 0x4 | `FILE_ATTRIBUTE_SYSTEM` | 시스템 파일 |
| 0x10 | `FILE_ATTRIBUTE_DIRECTORY` | 디렉터리(반환값에 이 비트가 있으면 파일이 아니라 폴더) |
| 0x20 | `FILE_ATTRIBUTE_ARCHIVE` | 보관 속성(백업 관련) |
| 0x80 | `FILE_ATTRIBUTE_NORMAL` | 다른 속성이 없을 때만 단독으로 쓰임 |
| 0x800 | `FILE_ATTRIBUTE_COMPRESSED` | 압축됨 |
| 0x400 | `FILE_ATTRIBUTE_REPARSE_POINT` | 심볼릭 링크/정션 등 |

**`GetFileAttributesExW`** — 속성뿐 아니라 크기, 생성/수정/접근 시각까지 한 번에 얻는다.
```c
BOOL GetFileAttributesExW(
    LPCWSTR                lpFileName,
    GET_FILEEX_INFO_LEVELS fInfoLevelId,   // 보통 GetFileExInfoStandard
    LPVOID                 lpFileInformation
);
```
`lpFileInformation`은 `WIN32_FILE_ATTRIBUTE_DATA` 구조체를 가리키며, 이 구조체 안에 `dwFileAttributes`, `ftCreationTime`, `ftLastAccessTime`, `ftLastWriteTime`, `nFileSizeHigh`, `nFileSizeLow`가 들어 있다. `CreateFile`로 핸들을 열지 않고도 파일 크기까지 알 수 있어, 단순히 크기만 확인하고 싶을 때 `CreateFile`+`GetFileSize`+`CloseHandle` 3단계보다 더 가볍게 쓰인다.

## 화면/코드에서 보이는 징후
- `GetFileAttributesW` 호출 직후 `cmp eax, 0FFFFFFFFh` / `je not_exist` 형태 — 전형적인 파일 존재 확인 패턴.
- `CreateFile` 없이 `GetFileAttributesW`만 반복 호출되면 특정 파일/디렉터리(예: 분석 도구 설치 경로, 가상머신 관련 파일)의 존재 여부를 탐지하는 안티분석/환경 체크 코드일 가능성.
- `GetFileSize`/`GetFileSizeEx` 호출 결과가 `malloc`/`HeapAlloc` 크기 인자로 바로 이어지는 패턴 — 파일 전체를 메모리에 읽어들이기 위한 준비 단계.

## 가장 먼저 할 것
`GetFileAttributesW`가 보이면 인자로 넘어가는 경로 문자열부터 확인한다. 특정 프로세스/도구 이름이 포함된 경로(예: `x64dbg.exe`, `\\.\pipe\...`)라면 안티분석 탐지일 가능성이 크다.

## 단계별 절차
1. IDA에서 `GetFileAttributesW`/`GetFileSizeEx` 호출을 `X`(xref)로 확인한다.
2. `F5`로 디컴파일해 반환값이 어떤 조건(`== -1`, `& FILE_ATTRIBUTE_DIRECTORY` 등)으로 쓰이는지 본다.
3. x64dbg에서 `bp GetFileAttributesW` 후 `RCX`(경로 문자열 주소)를 Follow in Dump로 확인한다.
4. `Ctrl+F9`로 리턴까지 실행해 `EAX` 값을 확인하고, `0xFFFFFFFF`인지 실제 속성 비트 조합인지 판단한다.

## 명령어/단축키
- x64dbg: `bp GetFileAttributesW`, `bp GetFileSizeEx`, `Ctrl+F9`(리턴까지 실행)
- IDA: `X`(xref), `F5`(디컴파일)

## 출력 해석
- `GetFileAttributesW` 반환값이 `0xFFFFFFFF`면 파일/경로가 없거나 접근할 수 없는 것이다.
- 반환값에 `0x10`(`FILE_ATTRIBUTE_DIRECTORY`) 비트가 있으면 그 경로는 파일이 아니라 디렉터리다 — 이후 코드가 파일로 취급해 여는지 확인하면 버그/우회 지점을 찾을 수도 있다.
- `GetFileSizeEx`가 채운 `LARGE_INTEGER.QuadPart` 값이 곧 힙 할당 크기와 같다면, 프로그램이 파일 전체를 메모리에 올려 처리하는 구조라는 뜻이다.

## 흔한 실수
- `GetFileSize`(구버전 API)의 반환값 `0xFFFFFFFF`를 무조건 실패로 단정하는 것 — 실제로 파일 크기 하위 32비트가 그 값일 수도 있으므로 `GetLastError()`를 함께 봐야 한다.
- `GetFileAttributesW`가 `BOOL`을 반환한다고 착각하는 것 — 실제로는 `DWORD`(속성 비트 조합)를 반환하며, 실패 판정은 `INVALID_FILE_ATTRIBUTES`와 비교로 해야 한다.
- 속성 비트를 하나의 값처럼 `==`로 비교하는 것 — 여러 속성이 OR로 조합되므로 반드시 `&`(AND)로 특정 비트만 검사해야 한다.

## 막혔을 때 다음 체크
- 파일을 실제로 여는 단계가 궁금하면 → REV-0496 확인.
- 파일 포인터 이동/삭제/이동 API가 궁금하면 → REV-0498 확인.
- 이 API가 안티분석 탐지처럼 보인다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)에서 의심스러운 API 판별 기준을 참고.

## 미니 예제
```c
if (GetFileAttributesW(L"C:\\Program Files\\x64dbg\\x64dbg.exe") != INVALID_FILE_ATTRIBUTES) {
    // 분석 도구가 설치되어 있다고 판단 -> 다르게 동작
}
```
`CreateFile`을 전혀 호출하지 않고도 특정 파일의 존재만으로 분기하는 이런 패턴은 디버거/분석 도구 탐지에서 매우 흔하다.

## 관련 글
- REV-0496 — WinAPI 파일 입출력 함수 사전: CreateFile 계열
- REV-0498 — WinAPI 파일 입출력 함수 사전: SetFilePointer DeleteFile MoveFile
- REV-0497 — WinAPI 파일 입출력 함수 사전: ReadFile WriteFile 상세
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- `GetFileSize`/`GetFileSizeEx`/`GetFileAttributesW`/`GetFileAttributesExW` 시그니처, `WIN32_FILE_ATTRIBUTE_DATA` 구조체, `FILE_ATTRIBUTE_*` 상수는 Microsoft Win32 API 공식 문서 기준(2026-09-08 확인 서술).
