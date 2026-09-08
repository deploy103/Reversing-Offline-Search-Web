---
id: REV-0497
title: "WinAPI 파일 입출력 함수 사전: ReadFile WriteFile 상세"
slug: "rev-0497-readfile-writefile"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["ReadFile", "WriteFile", "ReadFileEx", "WriteFileEx", "OVERLAPPED", "lpNumberOfBytesRead", "동기 비동기 파일 IO"]
aliases: ["ReadFile 함수 사전", "WriteFile 함수 사전", "OVERLAPPED 구조체", "비동기 파일 입출력"]
symptom_keywords: ["ReadFile 4번째 인자가 뭔지 모르겠다", "lpNumberOfBytesRead와 반환값 차이를 모르겠다", "OVERLAPPED가 왜 필요한지 모르겠다", "ReadFile이 FALSE를 반환한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`ReadFile`과 `WriteFile`은 인자 구조가 완전히 대칭인 5-인자 함수로, 반환값(`BOOL`)은 "호출 자체가 성공했는가"만 알려주고 실제로 처리된 바이트 수는 반드시 4번째 인자(`lpNumberOfBytesRead`/`Written`)가 가리키는 `DWORD`를 따로 읽어야 알 수 있다는 점이 이 두 함수를 분석할 때 가장 중요하다.

## 언제 검색해야 하나
- `ReadFile`/`WriteFile`의 정확한 인자 순서와 반환값 의미를 다시 확인하고 싶을 때
- `ReadFile`이 `TRUE`를 반환했는데 실제로 읽은 바이트가 몇 개인지 알아내야 할 때
- `ReadFileEx`/`WriteFileEx`나 `OVERLAPPED` 구조체가 왜 등장하는지 궁금할 때
- x64dbg에서 `WriteFile` 호출 직전 버퍼 내용을 가로채고 싶은데 어느 레지스터를 봐야 하는지 헷갈릴 때

## 핵심 개념
```c
BOOL ReadFile(
    HANDLE       hFile,
    LPVOID       lpBuffer,
    DWORD        nNumberOfBytesToRead,
    LPDWORD      lpNumberOfBytesRead,
    LPOVERLAPPED lpOverlapped
);

BOOL WriteFile(
    HANDLE       hFile,
    LPCVOID      lpBuffer,
    DWORD        nNumberOfBytesToWrite,
    LPDWORD      lpNumberOfBytesWritten,
    LPOVERLAPPED lpOverlapped
);
```

두 함수는 2번 인자(버퍼)의 방향만 반대다 — `ReadFile`은 버퍼가 "채워지는 곳", `WriteFile`은 버퍼가 "읽혀 나가는 곳"이다.

**반환값과 4번째 인자는 서로 다른 정보다.**
- 반환값(`BOOL`, `EAX`/`RAX`): 0이면 호출 자체 실패(`GetLastError()`로 원인 확인), 0이 아니면 성공.
- 4번째 인자가 가리키는 `DWORD`: 실제로 읽거나 쓴 바이트 수. 파일 끝(EOF)에 가까워서 요청한 `nNumberOfBytesToRead`보다 적게 읽혔어도 반환값은 여전히 `TRUE`일 수 있다. 즉 "성공 여부"와 "몇 바이트나 처리됐는가"는 반드시 따로 확인해야 한다.

**동기 vs 비동기(`OVERLAPPED`)**
- 동기 호출: 5번째 인자에 `NULL`을 넘긴다. 함수가 리턴할 때 이미 입출력이 끝나 있고, 4번째 인자에 실제 바이트 수가 들어 있다.
- 비동기 호출: `FILE_FLAG_OVERLAPPED`로 열린 핸들에 대해 `OVERLAPPED` 구조체 포인터를 5번째 인자로 넘기면, 함수가 즉시 리턴하고(반환값 `FALSE`, `GetLastError() == ERROR_IO_PENDING`) 입출력은 백그라운드에서 계속된다. `GetOverlappedResult`로 나중에 완료 여부와 바이트 수를 확인한다. `OVERLAPPED` 구조체는 파일 위치를 지정하는 `Offset`/`OffsetHigh` 필드도 겸한다.
- `ReadFileEx`/`WriteFileEx`는 완료 시 실행될 콜백 함수(`LPOVERLAPPED_COMPLETION_ROUTINE`)를 추가로 받는 비동기 전용 변형이며, 콜백이 등록된 스레드가 alertable 대기 상태(`SleepEx`, `WaitForSingleObjectEx` 등)일 때만 콜백이 실행된다는 점이 특징이다.

**호출 규약별 인자 위치**
- x86(stdcall): `[esp+4]`=hFile, `[esp+8]`=lpBuffer, `[esp+0Ch]`=바이트 수, `[esp+10h]`=바이트 수 저장 주소, `[esp+14h]`=lpOverlapped.
- x64: `RCX`=hFile, `RDX`=lpBuffer, `R8`=바이트 수, `R9`=바이트 수 저장 주소, 5번째 인자(lpOverlapped)는 섀도우 스페이스 뒤 `[rsp+28h]`(함수 진입 직후 기준).

## 화면/코드에서 보이는 징후
- `call WriteFile` 직후 `test eax, eax` / `je fail` 패턴.
- `lpNumberOfBytesRead`로 쓰인 지역 변수가 `ReadFile` 호출 이후 `cmp`로 요청 크기와 비교되는 코드(부분 읽기 감지).
- 5번째 인자가 `0`이 아니라 스택 변수 주소로 채워진 구조체를 가리키면 비동기 I/O를 의심해야 한다.

## 가장 먼저 할 것
`WriteFile`이라면 호출 직전(함수 진입 시점)에 `lpBuffer`가 가리키는 메모리를 먼저 본다. 이 시점이 곧 "이 프로그램이 파일에 쓰려는 데이터 원본"이다.

## 단계별 절차
1. x64dbg에서 `bp ReadFile` 또는 `bp WriteFile`을 건다.
2. 브레이크포인트가 걸리면 Registers 창에서 `RCX`(hFile), `RDX`(lpBuffer), `R8`(바이트 수)를 확인한다.
3. `RDX`를 우클릭 → `Follow in Dump`로 실제 버퍼 내용을 확인한다. `WriteFile`이면 지금 이 값이 그대로 파일에 써질 데이터다.
4. `Ctrl+F9`(Execute till return)로 함수가 끝날 때까지 실행한 뒤, `EAX`(반환값)와 4번째 인자가 가리키던 `DWORD` 메모리(주소는 3단계에서 `R9`로 미리 확인)를 함께 확인해 "성공 여부"와 "실제 바이트 수"를 분리해서 판단한다.

## 명령어/단축키
- x64dbg: `bp ReadFile`, `bp WriteFile`, `Ctrl+F9`(리턴까지 실행), 메모리 우클릭 → `Follow in Dump`
- IDA: `F5`(디컴파일), `X`(xref)

## 출력 해석
- 반환값 `0` = 호출 실패(`GetLastError()` 확인 필요). `0`이 아니면 성공.
- 4번째 인자 값 `< nNumberOfBytesToRead/Write`이면 요청보다 적게 처리된 것(EOF 근접, 파이프 버퍼 부족 등).
- 비동기 호출에서 반환값 `FALSE`이면서 `GetLastError() == ERROR_IO_PENDING`(997)이면 이것은 실패가 아니라 "아직 진행 중"이라는 정상 신호다.

## 흔한 실수
- 반환값만 보고 "성공했으니 요청한 바이트 수만큼 다 처리됐다"고 단정하는 것.
- 비동기 I/O의 `ERROR_IO_PENDING`을 실제 에러로 오인해서 흐름 추적을 멈추는 것.
- x64에서 5번째 인자를 찾을 때 섀도우 스페이스 0x20을 빠뜨리고 스택 오프셋을 잘못 계산하는 것 — 함수 진입 직후 기준 5번째 인자는 `[rsp+28h]`다.

## 막혔을 때 다음 체크
- 핸들을 여는 쪽(`CreateFile`)의 인자가 궁금하면 → REV-0496 확인.
- 파일 안에서 위치를 이동하거나 삭제/이동하는 API가 궁금하면 → REV-0498 확인.
- 데이터 흐름을 실제로 가로채는 실습형 절차가 궁금하면 → REV-0139(CreateFile ReadFile WriteFile 입력 데이터 추적)를 참고.

## 미니 예제
x64dbg에서 `bp WriteFile` 후 멈췄을 때 `RDX = 0x1F2A3C04010`, `R8 = 0x20`(32바이트)이라면, `RDX`를 Follow in Dump해서 나온 32바이트가 곧 파일에 그대로 기록될 원본 데이터다. 이는 파일이 디스크에 실제로 써지기를 기다리지 않고도 값을 가로챌 수 있는 가장 빠른 방법이다.

## 관련 글
- REV-0496 — WinAPI 파일 입출력 함수 사전: CreateFile 계열
- REV-0498 — WinAPI 파일 입출력 함수 사전: SetFilePointer DeleteFile MoveFile
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적
- REV-0124 — Shadow Space가 무엇인지

## 출처/검증
- `ReadFile`/`WriteFile`/`ReadFileEx`/`WriteFileEx` 시그니처와 `OVERLAPPED` 구조체 동작, `ERROR_IO_PENDING` 의미는 Microsoft Win32 API 공식 문서 기준.
- Microsoft x64 호출 규약(레지스터/섀도우 스페이스)은 Microsoft x64 소프트웨어 규약 공식 문서 기준(2026-09-08 확인 서술).
