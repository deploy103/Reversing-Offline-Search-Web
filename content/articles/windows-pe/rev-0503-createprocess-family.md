---
id: REV-0503
title: "WinAPI 프로세스 함수 사전: CreateProcess 계열"
slug: "rev-0503-createprocess-family"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CreateProcessW", "CreateProcessA", "STARTUPINFO", "PROCESS_INFORMATION", "CREATE_SUSPENDED", "lpCommandLine"]
aliases: ["CreateProcess 함수 사전", "STARTUPINFO 구조체", "PROCESS_INFORMATION 구조체", "프로세스 생성 API"]
symptom_keywords: ["CreateProcess 인자가 10개나 돼서 뭐가 뭔지 모르겠다", "CREATE_SUSPENDED 플래그가 뭔지 모르겠다", "새 프로세스를 실행하는 코드를 분석해야 한다", "lpCommandLine과 lpApplicationName 차이를 모르겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CreateProcessW`는 새 프로세스를 만들어 실행하는 Win32의 핵심 API로, 인자가 10개나 되어 복잡해 보이지만 실제 분석에서는 2번 인자(`lpCommandLine`, 실행되는 명령줄)와 6번 인자(`dwCreationFlags`, 특히 `CREATE_SUSPENDED`)만 확인해도 "무엇을 실행하는지"와 "프로세스 인젝션을 의도했는지"를 대부분 판단할 수 있다.

## 언제 검색해야 하나
- 프로그램이 다른 실행 파일을 자식 프로세스로 띄우는 코드(드로퍼, 셀프 스폰 패턴)를 분석할 때
- `CREATE_SUSPENDED` 플래그가 보여서 프로세스 할로잉(Process Hollowing) 같은 인젝션 기법을 의심할 때
- `STARTUPINFO`/`PROCESS_INFORMATION` 구조체 필드가 뭔지 헷갈릴 때
- `lpApplicationName`과 `lpCommandLine` 중 어느 쪽에 실제 실행 파일 경로가 들어가는지 헷갈릴 때

## 핵심 개념
```c
BOOL CreateProcessW(
    LPCWSTR               lpApplicationName,
    LPWSTR                lpCommandLine,
    LPSECURITY_ATTRIBUTES lpProcessAttributes,
    LPSECURITY_ATTRIBUTES lpThreadAttributes,
    BOOL                  bInheritHandles,
    DWORD                 dwCreationFlags,
    LPVOID                lpEnvironment,
    LPCWSTR               lpCurrentDirectory,
    LPSTARTUPINFOW        lpStartupInfo,
    LPPROCESS_INFORMATION lpProcessInformation
);
```

**인자별 요약**
1. `lpApplicationName` — 실행 파일 전체 경로. `NULL`이면 `lpCommandLine`의 첫 토큰에서 경로를 유추한다. 실무에서는 이 인자를 `NULL`로 두고 2번 인자에 전체 명령줄을 몰아 넣는 경우가 훨씬 흔하다.
2. `lpCommandLine` — 실제 실행되는 전체 명령줄 문자열(`"cmd.exe /c whoami"` 형태). **분석에서 가장 먼저 봐야 할 인자**다. 주의: 이 문자열은 쓰기 가능한 메모리여야 한다(함수 내부에서 파싱을 위해 이 버퍼를 수정할 수 있음) — 문자열 리터럴을 그대로 넘기면 크래시가 날 수 있어 실제 코드는 스택/힙 버퍼에 복사해서 넘기는 경우가 많다.
3. `lpProcessAttributes`, 4. `lpThreadAttributes` — 대개 `NULL`(기본 보안 속성, 상속 불가).
5. `bInheritHandles` — `TRUE`면 부모의 상속 가능한 핸들(예: 리다이렉션용 파이프)이 자식에게 전달된다. 자식 프로세스의 출력을 파이프로 가로채는 코드에서 `TRUE`로 설정된다.
6. `dwCreationFlags` — 흔한 값들:

| 값 | 이름 | 의미 |
|---|---|---|
| 0x00000004 | `CREATE_SUSPENDED` | 프로세스를 만들되 주 스레드를 즉시 실행하지 않고 일시정지 상태로 생성 — **프로세스 할로잉의 핵심 신호** |
| 0x00000008 | `DETACHED_PROCESS` | 콘솔 없이 생성 |
| 0x00000010 | `CREATE_NEW_CONSOLE` | 새 콘솔 창과 함께 생성 |
| 0x08000000 | `CREATE_NO_WINDOW` | 창을 아예 띄우지 않음(백그라운드 실행, 악성코드에서 흔함) |
| 0x00000200 | `CREATE_NEW_PROCESS_GROUP` | 새 프로세스 그룹으로 생성(Ctrl+C 시그널 격리) |

7. `lpEnvironment` — `NULL`이면 부모 환경변수를 그대로 상속.
8. `lpCurrentDirectory` — `NULL`이면 부모의 현재 디렉터리 유지.
9. `lpStartupInfo` — `STARTUPINFOW` 구조체 포인터(**필수**, 최소한 `cb` 필드에 `sizeof(STARTUPINFOW)`를 채워야 함). `dwFlags`에 `STARTF_USESTDHANDLES`가 있으면 `hStdInput`/`hStdOutput`/`hStdError` 필드로 표준 입출력을 리다이렉션한 것이다.
10. `lpProcessInformation` — `PROCESS_INFORMATION` 구조체 포인터(출력). 성공하면 이 구조체에 `hProcess`(새 프로세스 핸들), `hThread`(새 스레드 핸들), `dwProcessId`, `dwThreadId`가 채워진다.

반환값은 `BOOL`(0이면 실패, `GetLastError()`로 원인 확인).

`CreateProcessA`는 ANSI 버전으로 동작은 동일하다. `dwCreationFlags`에 `CREATE_SUSPENDED`가 있으면 이후 코드가 `GetThreadContext`/`SetThreadContext`, `WriteProcessMemory`, `ResumeThread`로 이어지는지 반드시 확인해야 한다 — 이 조합이 바로 프로세스 할로잉/인젝션의 전형적인 시퀀스다.

## 화면/코드에서 보이는 징후
- `call CreateProcessW` 직전 `lpCommandLine`으로 넘어가는 문자열이 `cmd.exe`, `powershell.exe`, 또는 자기 자신의 경로(`GetModuleFileNameW` 결과)인 패턴.
- `dwCreationFlags` 인자 값이 `4`(`CREATE_SUSPENDED`)로 세팅된 직후, 함수 뒤쪽에서 `WriteProcessMemory`와 `ResumeThread`가 이어지는 코드 — 프로세스 할로잉 의심.
- `STARTUPINFOW` 구조체의 `cb` 필드를 `sizeof`로 세팅하는 초기화 코드(`mov [rbp+cb], 68h` 등, x64에서 구조체 크기는 0x68).

## 가장 먼저 할 것
`lpCommandLine`(2번 인자) 문자열부터 확인한다. 이것이 "이 프로그램이 정확히 무엇을 실행하려는가"에 대한 직접적인 답이다.

## 단계별 절차
1. IDA에서 `CreateProcessW` 호출을 `X`(xref)로 찾는다.
2. `F5`로 디컴파일해 `lpCommandLine` 문자열과 `dwCreationFlags` 값을 확인한다.
3. `dwCreationFlags`에 `CREATE_SUSPENDED`(4)가 보이면, 같은 함수 내에서 `WriteProcessMemory`/`SetThreadContext`/`ResumeThread` 호출이 뒤따르는지 확인한다.
4. x64dbg에서 `bp CreateProcessW` 후 `RDX`(lpCommandLine)를 Follow in Dump로 문자열 확인, `[rsp+28h]`(6번째 인자, dwCreationFlags)를 확인한다.
5. `Ctrl+F9`로 리턴까지 실행해 `lpProcessInformation`이 가리키는 `PROCESS_INFORMATION` 구조체에서 `hProcess`/`dwProcessId`를 확인한다 — 이후 이 핸들/PID로 자식 프로세스를 추적할 수 있다.

## 명령어/단축키
- x64dbg: `bp CreateProcessW`, `Ctrl+F9`(리턴까지 실행)
- IDA: `X`(xref), `F5`(디컴파일)
- x64dbg에서 자식 프로세스까지 같이 디버깅하려면 옵션에서 "Enable child process debugging" 계열 설정 확인

## 출력 해석
- 반환값 `0`이면 실패 — `lpApplicationName`/`lpCommandLine`이 가리키는 실행 파일이 없거나 권한 문제일 가능성이 크다.
- `PROCESS_INFORMATION.dwProcessId`는 작업 관리자/Process Explorer에서 그대로 확인 가능한 실제 PID다.
- `dwCreationFlags`에 `CREATE_SUSPENDED`가 있는데 `ResumeThread` 호출이 안 보인다면, 프로세스가 영원히 멈춘 상태로 남아있거나(버그) 다른 스레드/외부 도구가 나중에 재개하는 구조일 수 있다.

## 흔한 실수
- `lpApplicationName`에 실행 파일 경로가 항상 있을 거라 가정하는 것 — 실제로는 `NULL`이고 `lpCommandLine`에만 경로가 들어있는 경우가 더 흔하다.
- `CREATE_SUSPENDED` 플래그를 보고도 그냥 "일시정지 옵션이구나" 하고 넘어가는 것 — 이 플래그는 프로세스 할로잉의 강력한 신호이므로 반드시 이후 `WriteProcessMemory`/`ResumeThread` 흐름까지 추적해야 한다.
- `lpStartupInfo`의 `cb` 필드 초기화를 놓치고 구조체를 잘못된 크기로 해석하는 것.

## 막혔을 때 다음 체크
- 생성된 프로세스를 다루는 후속 API(`OpenProcess`/`TerminateProcess`)가 궁금하면 → REV-0504 확인.
- 프로세스 내부의 스레드를 직접 다루는 API가 궁금하면 → REV-0505 확인.
- `CREATE_SUSPENDED` 이후 메모리 조작 흐름이 궁금하면 → REV-0511(WinAPI 메모리 함수 사전: ReadProcessMemory WriteProcessMemory, 추후 작성)을 확인.

## 미니 예제
```c
STARTUPINFOW si = { sizeof(si) };
PROCESS_INFORMATION pi;
WCHAR cmd[] = L"C:\\Windows\\System32\\cmd.exe /c whoami";
CreateProcessW(NULL, cmd, NULL, NULL, FALSE, CREATE_NO_WINDOW,
               NULL, NULL, &si, &pi);
```
`dwCreationFlags = CREATE_NO_WINDOW`(0x08000000)이므로 콘솔 창 없이 백그라운드에서 `whoami`가 실행된다. `pi.hProcess`/`pi.dwProcessId`로 생성된 프로세스를 이후 추적할 수 있다.

## 관련 글
- REV-0504 — WinAPI 프로세스 함수 사전: OpenProcess TerminateProcess
- REV-0505 — WinAPI 스레드 함수 사전: CreateThread ExitThread
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- `CreateProcessW` 시그니처, `STARTUPINFOW`/`PROCESS_INFORMATION` 구조체, `dwCreationFlags` 상수(`CREATE_SUSPENDED` 등)는 Microsoft Win32 API 공식 문서 기준.
- 프로세스 할로잉에서 `CREATE_SUSPENDED` + `WriteProcessMemory` + `ResumeThread` 조합이 쓰인다는 점은 일반적인 악성코드 분석/리버싱 레퍼런스 기준(2026-09-08 확인 서술).
