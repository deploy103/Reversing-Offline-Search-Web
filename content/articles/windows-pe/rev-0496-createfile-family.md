---
id: REV-0496
title: "WinAPI 파일 입출력 함수 사전: CreateFile 계열"
slug: "rev-0496-createfile-family"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CreateFileA", "CreateFileW", "CreateFile2", "dwDesiredAccess", "dwShareMode", "dwCreationDisposition", "INVALID_HANDLE_VALUE"]
aliases: ["CreateFile 함수 사전", "CreateFileA CreateFileW 차이", "파일 열기 API", "CreateFile2"]
symptom_keywords: ["CreateFile 인자 값이 뭔지 모르겠다", "dwCreationDisposition 상수 의미를 모르겠다", "CreateFile이 INVALID_HANDLE_VALUE를 반환한다", "GENERIC_READ GENERIC_WRITE 값이 헷갈린다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CreateFileA`/`CreateFileW`(및 `CreateFile2`)는 파일·파이프·장치를 열거나 새로 만들어 `HANDLE`을 돌려주는 Win32 진입점이며, 7개 인자 중 `dwDesiredAccess`(2번), `dwCreationDisposition`(5번)만 정확히 읽어도 "이 코드가 뭘 하려는 파일 작업인지" 즉시 판단할 수 있다.

## 언제 검색해야 하나
- Import Table에서 `CreateFileA`/`CreateFileW`를 보고 정확한 인자 순서와 각 상수값이 기억나지 않을 때
- `CreateFile2`(Windows 8+ 전용 API)가 보여서 기존 `CreateFileW`와 뭐가 다른지 궁금할 때
- 반환값이 `INVALID_HANDLE_VALUE`(`-1`)인데 왜 실패했는지 `dwCreationDisposition`/`dwDesiredAccess` 조합으로 원인을 추정하고 싶을 때
- x64dbg에서 `bp CreateFileW` 후 레지스터에 찍힌 숫자 상수(`0x80000000`, `0x3` 등)가 무슨 뜻인지 바로 찾고 싶을 때

## 핵심 개념
`CreateFileA`/`CreateFileW`는 `kernel32.dll`(실제 구현은 `KernelBase.dll`)이 제공하며, ANSI(`A`)와 유니코드(`W`) 버전은 첫 인자 문자열 인코딩만 다르고 나머지 동작은 동일하다.

```c
HANDLE CreateFileW(
    LPCWSTR               lpFileName,
    DWORD                  dwDesiredAccess,
    DWORD                  dwShareMode,
    LPSECURITY_ATTRIBUTES  lpSecurityAttributes,
    DWORD                  dwCreationDisposition,
    DWORD                  dwFlagsAndAttributes,
    HANDLE                 hTemplateFile
);
```

**인자별 요약**
1. `lpFileName` — 경로 문자열. `\\.\PhysicalDrive0`처럼 `\\.\`로 시작하면 물리 디스크/장치를 직접 여는 것이므로 단순 파일 조작이 아닐 가능성이 크다.
2. `dwDesiredAccess` — 흔한 값: `GENERIC_READ`(0x80000000), `GENERIC_WRITE`(0x40000000), 둘 다 OR하면 읽기/쓰기 겸용. `0`을 주면 메타데이터(속성)만 조회하고 실제 데이터 접근은 하지 않겠다는 뜻이다.
3. `dwShareMode` — `0`이면 다른 프로세스와 공유 안 함(독점), `FILE_SHARE_READ`(1)/`FILE_SHARE_WRITE`(2)/`FILE_SHARE_DELETE`(4)를 OR해서 공유 허용.
4. `lpSecurityAttributes` — 대부분 `NULL`. 상속 가능한 핸들을 만들 때만 값이 채워진다.
5. `dwCreationDisposition` — **정확히 하나만** 선택해야 하는 값. 뒤 표 참고.
6. `dwFlagsAndAttributes` — `FILE_ATTRIBUTE_NORMAL`(0x80)이 가장 흔함. `FILE_FLAG_OVERLAPPED`(0x40000000)면 비동기 I/O, `FILE_FLAG_DELETE_ON_CLOSE`(0x04000000)면 핸들이 닫히자마자 파일 자동 삭제(임시 파일/안티포렌식 패턴에서 자주 보임).
7. `hTemplateFile` — 거의 항상 `NULL`.

**`dwCreationDisposition` 값표**

| 값 | 이름 | 의미 |
|---|---|---|
| 1 | `CREATE_NEW` | 파일이 없을 때만 새로 생성, 있으면 실패 |
| 2 | `CREATE_ALWAYS` | 항상 새로 생성(기존 파일 있으면 덮어씀) |
| 3 | `OPEN_EXISTING` | 파일이 있어야만 열림(없으면 실패) — 가장 흔한 "읽기용 열기" 패턴 |
| 4 | `OPEN_ALWAYS` | 있으면 열고 없으면 새로 생성 |
| 5 | `TRUNCATE_EXISTING` | 파일을 열면서 크기를 0으로 초기화(쓰기 권한 필수) |

반환값은 성공 시 유효한 `HANDLE`, 실패 시 `INVALID_HANDLE_VALUE`(모든 비트가 1, 즉 x86에서 `0xFFFFFFFF`, x64 포인터 크기에서도 상위 비트까지 전부 1)다. `NULL`(0)이 아니라는 점이 다른 많은 Win32 함수의 실패값(`NULL`)과 다르므로 실패 체크 코드에서 `cmp eax, -1` / `cmp rax, -1` 형태를 찾아야 한다.

**`CreateFile2`** (Windows 8 이상)는 인자 3개(`dwShareMode`, `dwCreationDisposition`, `dwFlagsAndAttributes`)를 `CREATEFILE2_EXTENDED_PARAMETERS` 구조체 하나로 묶은 최신 버전이다. UWP/최신 데스크톱 앱에서 보이며 등장 빈도는 낮지만, 구조체 포인터를 4번째 인자로 넘긴다는 점만 알면 나머지는 동일하다.

## 화면/코드에서 보이는 징후
- x86: `call`부터 역순으로 `push`가 7번 쌓임(마지막 인자 `hTemplateFile`이 먼저 push됨).
- x64: `mov r9d, ...`(hTemplateFile 생략 시 0), `mov [rsp+28h], ...`(6번째 인자는 스택), `mov r8d, ...`(dwShareMode), `mov edx, ...`(dwDesiredAccess), `lea rcx, [filename]` 순서로 역순 세팅되는 경우가 흔함.
- 반환값을 곧바로 `cmp eax/rax, -1` 또는 `cmp eax/rax, 0FFFFFFFFh`로 검사.

## 가장 먼저 할 것
`dwDesiredAccess`(2번 인자)와 `dwCreationDisposition`(5번 인자) 두 값만 먼저 확인한다. 이 둘의 조합만으로 "새 파일을 만드는가/기존 파일을 읽는가/덮어쓰는가"가 결정된다.

## 단계별 절차
1. IDA에서 `CreateFileW` 호출부를 `X`(xref)로 모두 나열한다.
2. `F5`(Hex-Rays)로 디컴파일하면 `CreateFileW(L"save.dat", 0xC0000000, 0, 0, 2, 0x80, 0)` 형태로 상수가 그대로 보인다. `0xC0000000`은 `GENERIC_READ|GENERIC_WRITE`, `2`는 `CREATE_ALWAYS`다.
3. x64dbg에서는 `bp CreateFileW` 후 멈추면 `RCX`(경로), `RDX`(access), `R8`(share), `R9`(security), `[rsp+28h]`(disposition)를 순서대로 확인한다.
4. 반환값(`RAX`)을 `Ctrl+F9`(Execute till return)로 확인하고, `-1`이 아니면 성공한 것이므로 이후 `ReadFile`/`WriteFile` 흐름(REV-0497)으로 이어간다.

## 명령어/단축키
- x64dbg: `bp CreateFileW`, `bp CreateFileA`, `Ctrl+F9`(리턴까지 실행)
- IDA: `X`(xref), `F5`(디컴파일), 상수 우클릭 → `Use standard symbolic constant`로 `0x80000000` 같은 숫자를 `GENERIC_READ`로 자동 치환 가능

## 출력 해석
- `dwDesiredAccess = 0x80000000` → 읽기 전용. `0x40000000` → 쓰기 전용. `0xC0000000` → 읽기/쓰기.
- `dwCreationDisposition = 3`(OPEN_EXISTING)인데 반환값이 `-1`이면 "그 경로에 파일이 없다"는 뜻 — 프로그램이 어떤 파일을 찾는지 역으로 알 수 있는 좋은 단서다.
- `dwFlagsAndAttributes`에 `FILE_FLAG_DELETE_ON_CLOSE`(0x04000000) 비트가 있으면 이 핸들이 닫히는 순간 파일이 자동 삭제되므로, 파일 내용을 보려면 핸들이 열려 있는 동안(즉 `CloseHandle` 전)에 덤프해야 한다.

## 흔한 실수
- `dwCreationDisposition` 값을 `dwDesiredAccess`와 혼동해서 "값이 3이니까 읽기+쓰기+실행이겠지"처럼 잘못 추측하는 것. 두 필드는 완전히 다른 상수 세트를 쓴다.
- 실패값을 `NULL`(0)로 착각해서 `test eax, eax` 로 검사하는 코드를 찾다가 못 찾는 것 — `CreateFile` 계열은 `INVALID_HANDLE_VALUE`(`-1`)를 쓴다.
- `CreateFileA`와 `CreateFileW`가 같은 함수라고 생각해서 문자열 인코딩을 착각하는 것. `A`는 1바이트(현재 코드페이지), `W`는 2바이트(UTF-16LE)다.

## 막혔을 때 다음 체크
- 열린 핸들로 실제 데이터를 읽고 쓰는 흐름이 궁금하면 → REV-0497 확인.
- 파일 포인터 이동/삭제/이동(rename) 계열 API가 궁금하면 → REV-0498 확인.
- 파일 크기나 속성만 조회하는 API가 궁금하면 → REV-0499 확인.
- 함수 이름 자체가 낯설다면 → REV-0138에서 API 이름으로 기능을 추측하는 법을 먼저 본다.

## 미니 예제
```c
HANDLE h = CreateFileW(L"C:\\temp\\out.dat", GENERIC_WRITE, 0, NULL,
                        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
if (h == INVALID_HANDLE_VALUE) { /* 실패 처리 */ }
```
디스어셈블리(x64)에서는 상수가 `0x40000000`(GENERIC_WRITE), `2`(CREATE_ALWAYS), `0x80`(FILE_ATTRIBUTE_NORMAL)로 그대로 보이며, 반환값을 `cmp rax, -1` / `je fail_branch`로 검사하는 패턴이 뒤따른다.

## 관련 글
- REV-0497 — WinAPI 파일 입출력 함수 사전: ReadFile WriteFile 상세
- REV-0498 — WinAPI 파일 입출력 함수 사전: SetFilePointer DeleteFile MoveFile
- REV-0499 — WinAPI 파일 입출력 함수 사전: GetFileSize GetFileAttributes
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- `CreateFileW`/`CreateFile2` 시그니처, 인자 상수값(`GENERIC_READ`, `CREATE_ALWAYS` 등)은 Microsoft Win32 API 공식 문서(learn.microsoft.com) 기준.
- `INVALID_HANDLE_VALUE`가 실패값이라는 점, 반환값 규칙도 동일 공식 문서 기준(2026-09-08 확인 서술).
