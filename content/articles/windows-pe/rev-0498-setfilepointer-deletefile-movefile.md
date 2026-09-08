---
id: REV-0498
title: "WinAPI 파일 입출력 함수 사전: SetFilePointer DeleteFile MoveFile"
slug: "rev-0498-setfilepointer-deletefile-movefile"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["SetFilePointer", "SetFilePointerEx", "DeleteFileW", "MoveFileW", "MoveFileEx", "FILE_BEGIN", "FILE_CURRENT", "FILE_END"]
aliases: ["SetFilePointer 함수 사전", "DeleteFile 함수 사전", "MoveFile 함수 사전", "파일 포인터 이동 API"]
symptom_keywords: ["SetFilePointer 세 번째 인자가 뭔지 모르겠다", "MoveFileEx와 MoveFile 차이를 모르겠다", "DeleteFile 호출 후 파일이 사라진다", "FILE_BEGIN FILE_CURRENT FILE_END 값이 헷갈린다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`SetFilePointer`(위치 이동), `DeleteFile`(삭제), `MoveFile`(이름 변경/이동)은 각각 파일 내부 커서 조작, 파일 자체 삭제, 파일 경로 변경이라는 서로 다른 목적을 갖지만 셋 다 인자 1개(경로 또는 핸들)만 확인하면 코드가 어떤 파일을 대상으로 하는지 바로 알 수 있는 짧은 API라는 공통점이 있다.

## 언제 검색해야 하나
- `SetFilePointer`의 `dwMoveMethod` 상수(`FILE_BEGIN`/`FILE_CURRENT`/`FILE_END`)가 헷갈릴 때
- 파일을 다 읽지 않고 특정 오프셋부터 읽으려고 파일 포인터를 옮기는 코드를 분석할 때
- `DeleteFile`/`MoveFile` 호출을 보고 이 프로그램이 자기 자신을 지우거나(자기 삭제 패턴) 다른 파일을 옮기는지 확인하고 싶을 때
- `MoveFileEx`에만 있는 특수 플래그(`MOVEFILE_DELAY_UNTIL_REBOOT` 등)의 의미가 궁금할 때

## 핵심 개념

**`SetFilePointer`** — 파일 핸들 내부의 읽기/쓰기 위치(커서)를 이동한다.
```c
DWORD SetFilePointer(
    HANDLE hFile,
    LONG   lDistanceToMove,
    PLONG  lpDistanceToMoveHigh,
    DWORD  dwMoveMethod
);
```
- `lDistanceToMove`: 이동할 바이트 수(부호 있음, 음수면 역방향).
- `lpDistanceToMoveHigh`: 64비트 오프셋이 필요할 때 상위 32비트를 담는 포인터. 32비트 범위면 `NULL`.
- `dwMoveMethod`: `FILE_BEGIN`(0, 파일 처음부터), `FILE_CURRENT`(1, 현재 위치부터), `FILE_END`(2, 파일 끝부터 — 이 경우 `lDistanceToMove`에 음수를 주는 것이 일반적).
- 반환값은 이동 후의 새 위치(하위 32비트)이며, 실패 시 `INVALID_SET_FILE_POINTER`(0xFFFFFFFF)이고 이때는 반드시 `GetLastError()`로 실제 에러 여부를 재확인해야 한다(정상적으로 위치가 0xFFFFFFFF가 되는 경우와 구분하기 위함).
- 최신 코드에서는 64비트 오프셋을 한 번에 다루는 `SetFilePointerEx(HANDLE, LARGE_INTEGER, PLARGE_INTEGER, DWORD)`가 더 흔히 쓰인다. 동작은 동일하되 `LARGE_INTEGER`로 상/하위를 한 번에 넘긴다는 점만 다르다.

**`DeleteFileW`** — 파일을 디스크에서 삭제한다.
```c
BOOL DeleteFileW(LPCWSTR lpFileName);
```
인자가 경로 문자열 하나뿐이다. 반환값 `BOOL`(0이면 실패, 대개 파일이 열려 있거나 읽기 전용 속성일 때 실패). 리버싱에서는 프로그램이 실행 중 자기 자신의 실행 파일을 지우려 시도하는 "자기 삭제(self-delete)" 패턴이나, 임시로 만든 드롭 파일을 흔적 없이 지우는 패턴에서 자주 등장한다. 다만 실행 중인 파일은 Windows에서 바로 삭제되지 않고 마지막 핸들이 닫힐 때 실제로 제거되므로, `MoveFileEx`로 파일명을 먼저 바꾸거나 배치 스크립트를 띄워 지연 삭제하는 우회 패턴도 함께 살펴야 한다.

**`MoveFileW`** — 파일(또는 디렉터리)의 이름을 바꾸거나 다른 경로로 이동한다.
```c
BOOL MoveFileW(LPCWSTR lpExistingFileName, LPCWSTR lpNewFileName);
```
같은 드라이브 안에서는 단순 이름 변경(rename)으로 처리되어 매우 빠르고, 다른 드라이브로는 실제 복사 후 원본 삭제로 처리된다. 대상 경로에 이미 파일이 있으면 기본적으로 **실패**한다(덮어쓰지 않음).

**`MoveFileExW`** — `MoveFileW`에 동작을 세밀하게 제어하는 플래그를 추가한 버전.
```c
BOOL MoveFileExW(LPCWSTR lpExistingFileName, LPCWSTR lpNewFileName, DWORD dwFlags);
```
- `MOVEFILE_REPLACE_EXISTING`(0x1): 대상에 파일이 있어도 덮어씀.
- `MOVEFILE_DELAY_UNTIL_REBOOT`(0x4): 지금 옮기지 않고 다음 재부팅 시 이동(레지스트리 `PendingFileRenameOperations`에 기록됨). `lpNewFileName`을 `NULL`로 주면 재부팅 시 삭제가 된다 — 실행 중이라 못 지우는 파일을 재부팅 후 지우는 전형적인 우회 기법이다.

## 화면/코드에서 보이는 징후
- `SetFilePointer` 호출 직후 곧바로 `ReadFile`이 이어지는 패턴 — 파일 앞부분을 건너뛰고 특정 오프셋(예: 헤더 뒤 데이터 영역)부터 읽으려는 의도.
- `GetModuleFileNameW`로 자기 자신의 경로를 얻은 뒤 그 문자열이 `MoveFileExW`(`MOVEFILE_DELAY_UNTIL_REBOOT`)나 `DeleteFileW`의 인자로 쓰이는 패턴 — 자기 삭제/흔적 제거 코드.
- `MoveFileExW`의 3번째 인자가 `4`(0x4)로 보이면 재부팅 후 삭제/이동을 의도한 것이다.

## 가장 먼저 할 것
`DeleteFile`/`MoveFile` 계열이 보이면 대상 경로 문자열부터 확인해서 "자기 자신을 지우는가, 다른 파일(로그, 임시 파일, 원본 드롭 파일)을 지우는가"를 구분한다.

## 단계별 절차
1. IDA에서 `SetFilePointer`/`DeleteFileW`/`MoveFileExW` 호출을 `X`(xref)로 나열한다.
2. `F5`로 디컴파일해 `dwMoveMethod` 값(0/1/2)과 이동 거리, 경로 문자열 인자를 바로 확인한다.
3. x64dbg에서 `bp SetFilePointer`(또는 `SetFilePointerEx`) 후 `RDX`(이동 거리)와 `R9`(dwMoveMethod)를 확인한다.
4. `DeleteFileW`/`MoveFileExW`는 `RCX`(경로1), `MoveFileExW`라면 추가로 `RDX`(경로2), `R8`(flags)까지 확인한다.

## 명령어/단축키
- x64dbg: `bp SetFilePointer`, `bp SetFilePointerEx`, `bp DeleteFileW`, `bp MoveFileExW`
- IDA: `X`(xref), `F5`(디컴파일)

## 출력 해석
- `SetFilePointer` 반환값이 `0xFFFFFFFF`(`INVALID_SET_FILE_POINTER`)이면 `GetLastError()`를 함께 확인해야 진짜 실패인지 판단할 수 있다.
- `MoveFileExW`의 `dwFlags`에 `0x4` 비트가 있으면 즉시 이동/삭제가 아니라 재부팅 이후로 예약된 것이므로, 지금 파일시스템을 봐도 아직 변화가 없을 수 있다.
- `DeleteFileW`가 `FALSE`를 반환했다면 파일이 이미 열려 있거나(다른 핸들이 점유), 읽기 전용 속성이거나, 경로가 틀렸을 가능성이 크다.

## 흔한 실수
- `FILE_END`(2)로 이동할 때 `lDistanceToMove`에 양수를 넣어서 파일 범위를 벗어나는 위치를 만드는 실수 — 파일 끝 기준 역방향이므로 보통 음수를 써야 한다.
- `MoveFile`이 대상 파일을 덮어쓸 것이라 착각하는 것 — 기본 `MoveFileW`는 대상이 이미 존재하면 실패한다. 덮어쓰려면 `MoveFileExW` + `MOVEFILE_REPLACE_EXISTING`이 필요하다.
- `DeleteFileW` 호출 직후 파일이 파일시스템에서 안 보인다고 바로 "삭제 완료"로 단정하는 것 — 실행 중인 파일은 마지막 핸들이 닫혀야 실제로 제거된다.

## 막혔을 때 다음 체크
- 파일을 여는 단계(`CreateFile`)가 궁금하면 → REV-0496 확인.
- 옮겨진 파일 포인터로 실제 읽기/쓰기를 하는 흐름이 궁금하면 → REV-0497 확인.
- 파일 크기/속성만 조회하려면 → REV-0499 확인.

## 미니 예제
```c
HANDLE h = CreateFileW(L"data.bin", GENERIC_READ, FILE_SHARE_READ, NULL,
                        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
SetFilePointer(h, 0x100, NULL, FILE_BEGIN);   // 0x100 오프셋으로 이동
ReadFile(h, buf, 0x20, &read, NULL);          // 헤더를 건너뛰고 데이터 읽기
```
이 패턴은 파일 앞부분(헤더/시그니처)을 건너뛰고 특정 오프셋의 데이터(예: 암호화된 페이로드)만 골라 읽는 전형적인 코드다.

## 관련 글
- REV-0496 — WinAPI 파일 입출력 함수 사전: CreateFile 계열
- REV-0497 — WinAPI 파일 입출력 함수 사전: ReadFile WriteFile 상세
- REV-0499 — WinAPI 파일 입출력 함수 사전: GetFileSize GetFileAttributes

## 출처/검증
- `SetFilePointer`/`SetFilePointerEx`/`DeleteFileW`/`MoveFileW`/`MoveFileExW` 시그니처와 상수(`FILE_BEGIN` 등, `MOVEFILE_*` 플래그)는 Microsoft Win32 API 공식 문서 기준.
- `PendingFileRenameOperations`를 통한 재부팅 후 삭제 메커니즘은 Windows 내부 동작에 대한 일반 레퍼런스 기준(2026-09-08 확인 서술).
