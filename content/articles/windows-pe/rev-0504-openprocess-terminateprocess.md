---
id: REV-0504
title: "WinAPI 프로세스 함수 사전: OpenProcess TerminateProcess"
slug: "rev-0504-openprocess-terminateprocess"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["OpenProcess", "TerminateProcess", "PROCESS_ALL_ACCESS", "PROCESS_VM_WRITE", "PROCESS_TERMINATE", "ExitProcess"]
aliases: ["OpenProcess 함수 사전", "TerminateProcess 함수 사전", "프로세스 핸들 얻기 API", "프로세스 강제 종료 API"]
symptom_keywords: ["OpenProcess 두 번째 인자 권한 값이 뭔지 모르겠다", "PROCESS_ALL_ACCESS 값이 뭔지 모르겠다", "TerminateProcess와 ExitProcess 차이를 모르겠다", "다른 프로세스를 종료시키는 코드를 분석해야 한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`OpenProcess`는 이미 실행 중인 다른 프로세스에 대한 핸들을 PID로 얻는 함수이고, `TerminateProcess`는 그 핸들을 이용해 프로세스를 강제 종료하는 함수로, 두 함수를 연달아 쓰는 패턴은 백신/디버거 프로세스를 찾아 죽이는 안티분석 코드에서 매우 흔하게 등장한다.

## 언제 검색해야 하나
- `OpenProcess`가 어떤 권한(`dwDesiredAccess`)으로 다른 프로세스를 열려는지 확인해야 할 때
- `TerminateProcess` 호출을 보고 이 프로그램이 특정 프로세스(x64dbg, ProcessHacker 등 분석 도구)를 죽이려 하는지 의심될 때
- `PROCESS_ALL_ACCESS`, `PROCESS_VM_WRITE`, `PROCESS_TERMINATE` 같은 접근 권한 상수값이 헷갈릴 때
- `TerminateProcess`와 `ExitProcess`의 차이(자기 자신 종료 vs 남을 종료)가 헷갈릴 때

## 핵심 개념

**`OpenProcess`** — PID로 다른 프로세스의 핸들을 얻는다.
```c
HANDLE OpenProcess(
    DWORD dwDesiredAccess,
    BOOL  bInheritHandle,
    DWORD dwProcessId
);
```
1. `dwDesiredAccess` — 원하는 접근 권한. 코드가 이후 무엇을 하려는지 짐작할 수 있는 가장 중요한 인자다.

| 값 | 이름 | 의미 / 이후 예상되는 API |
|---|---|---|
| 0x0001 | `PROCESS_TERMINATE` | `TerminateProcess`용 |
| 0x0008 | `PROCESS_VM_OPERATION` | `VirtualAllocEx`/`VirtualProtectEx`용(메모리 조작) |
| 0x0010 | `PROCESS_VM_READ` | `ReadProcessMemory`용 |
| 0x0020 | `PROCESS_VM_WRITE` | `WriteProcessMemory`용 — `VM_OPERATION`과 함께 있으면 코드/DLL 인젝션 의심 |
| 0x0400 | `PROCESS_QUERY_INFORMATION` | `GetExitCodeProcess`, `GetPriorityClass` 등 정보 조회용 |
| 0x1000 | `PROCESS_QUERY_LIMITED_INFORMATION` | 더 제한된 정보 조회(낮은 권한으로도 가능) |
| 0x001F0FFF | `PROCESS_ALL_ACCESS` | 모든 권한 — 이 값이 보이면 이후 뭐든 할 수 있다는 뜻이므로 특히 주의 깊게 추적해야 함 |

`PROCESS_VM_OPERATION`+`PROCESS_VM_WRITE`+`PROCESS_VM_READ` 조합(또는 그냥 `PROCESS_ALL_ACCESS`)으로 연 핸들이 이후 `WriteProcessMemory`/`CreateRemoteThread`로 이어진다면 전형적인 DLL 인젝션/코드 인젝션 패턴이다.

2. `bInheritHandle` — 자식 프로세스가 이 핸들을 상속할지 여부. 대개 `FALSE`.
3. `dwProcessId` — 대상 프로세스의 PID. `CreateToolhelp32Snapshot`+`Process32First`/`Next`로 프로세스 이름을 순회하며 PID를 찾아 넘기는 코드가 앞에 붙는 경우가 매우 흔하다(예: `x64dbg.exe`, `ida64.exe`, `ollydbg.exe`, `procexp64.exe` 등 이름을 문자열 비교로 찾는 패턴).

반환값은 성공 시 유효한 `HANDLE`, 실패 시 `NULL`(`CreateFile`과 달리 여기서는 실패값이 `INVALID_HANDLE_VALUE`가 아니라 `NULL`이다).

**`TerminateProcess`** — 프로세스를 강제 종료한다.
```c
BOOL TerminateProcess(HANDLE hProcess, UINT uExitCode);
```
`hProcess`는 `PROCESS_TERMINATE` 권한을 포함해 연 핸들이어야 하며, `uExitCode`는 종료되는 프로세스의 종료 코드로 남는다. 이 함수는 대상 프로세스의 정리 코드(DLL의 `DLL_PROCESS_DETACH`, 소멸자 등)를 실행시키지 않고 **즉시 강제 종료**시킨다는 점이 일반적인 프로세스 종료와 다르다.

**`ExitProcess`와의 차이** — `ExitProcess(UINT uExitCode)`는 인자가 하나뿐이며 **자기 자신**을 정상 종료(DLL 언로드 등 정리 과정 포함)시키는 함수다. `TerminateProcess`는 **다른 프로세스**(또는 자기 자신도 가능)를 핸들 기준으로 강제 종료시키며 정리 과정을 건너뛴다. 코드에서 인자가 1개면 `ExitProcess`, 핸들+종료코드로 2개면 `TerminateProcess`라는 시그니처 차이로 즉시 구분 가능하다.

## 화면/코드에서 보이는 징후
- `CreateToolhelp32Snapshot` → `Process32FirstW`/`Process32NextW` 루프에서 `szExeFile` 문자열을 특정 프로세스 이름과 비교(`lstrcmpiW`, `wcscmp` 등)한 뒤, 일치하면 `OpenProcess`(권한 `PROCESS_TERMINATE` 또는 `PROCESS_ALL_ACCESS`) → `TerminateProcess` 순서로 이어지는 코드.
- `OpenProcess`의 `dwDesiredAccess` 인자가 `0x1F0FFF`(`PROCESS_ALL_ACCESS`)로 통째로 넘어가는 패턴 — 세밀한 권한 대신 전체 권한을 요청하는 것은 다소 거친(그리고 흔한) 구현 방식이다.
- `OpenProcess` 반환값을 `test eax, eax` / `je skip`(0이면 실패, 건너뜀)으로 검사하는 코드.

## 가장 먼저 할 것
`OpenProcess` 호출 직전에 대상 PID가 어떻게 결정되는지부터 역추적한다 — 대개 프로세스 이름 문자열 비교 코드가 근처에 있으며, 그 문자열이 곧 "이 프로그램이 무엇을 노리는가"에 대한 직접적인 답이다.

## 단계별 절차
1. IDA에서 `OpenProcess`를 `X`(xref)로 찾는다.
2. `F5`로 디컴파일해 `dwDesiredAccess` 상수와, `dwProcessId` 인자가 어떤 변수에서 왔는지(스냅샷 루프의 결과인지) 확인한다.
3. 스냅샷 루프가 있다면 비교 대상 문자열(프로세스 이름)을 확인해 어떤 프로세스를 찾는지 파악한다.
4. `TerminateProcess` 호출까지 이어지는지 확인하고, x64dbg에서 `bp TerminateProcess` 후 `RCX`(hProcess)가 어떤 프로세스인지 추적한다(핸들 값 자체로는 알 수 없으므로 `OpenProcess` 호출 시점의 PID를 먼저 확인해야 함).

## 명령어/단축키
- x64dbg: `bp OpenProcess`, `bp TerminateProcess`, `Ctrl+F9`(리턴까지 실행)
- IDA: `X`(xref), `F5`(디컴파일)

## 출력 해석
- `OpenProcess` 반환값 `NULL`이면 실패(권한 부족 또는 대상 PID가 존재하지 않음) — `CreateFile`류의 `INVALID_HANDLE_VALUE`(`-1`)와 실패값이 다르다는 점에 유의.
- `TerminateProcess` 반환값 `0`이면 종료 실패(대상이 이미 종료됐거나 권한 부족).
- 대상 PID가 자기 자신의 PID(`GetCurrentProcessId()` 결과)와 같다면 자기 자신을 종료하는 특수한 경우다.

## 흔한 실수
- `OpenProcess` 실패값을 `INVALID_HANDLE_VALUE`(-1)로 착각하는 것 — 실제로는 `NULL`(0)이다.
- `TerminateProcess`와 `ExitProcess`를 같은 함수로 착각하는 것 — 인자 개수(2개 vs 1개)와 대상(타 프로세스 vs 자기 자신)이 다르다.
- `PROCESS_ALL_ACCESS` 상수값을 32비트 기준(`0x1F0FFF`)으로만 기억해서 다른 버전/문서의 값과 헷갈리는 것 — Windows 버전에 따라 이 상수의 정확한 비트 구성이 문서에서 미묘하게 다르게 설명되는 경우가 있으므로, 정확한 판별은 상수값보다 "이후 어떤 API가 이어지는가"로 하는 것이 더 안전하다.

## 막혔을 때 다음 체크
- 대상 프로세스를 애초에 만드는 단계가 궁금하면 → REV-0503 확인.
- 프로세스 안의 스레드를 다루는 API가 궁금하면 → REV-0505 확인.
- 이 프로세스가 디버거를 감지하려는 것 같다면 → REV-0130(IsDebuggerPresent 안티디버깅 식별)도 함께 확인.

## 미니 예제
```c
HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
PROCESSENTRY32W pe = { sizeof(pe) };
Process32FirstW(snap, &pe);
do {
    if (!lstrcmpiW(pe.szExeFile, L"x64dbg.exe")) {
        HANDLE h = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
        TerminateProcess(h, 1);
    }
} while (Process32NextW(snap, &pe));
```
이 패턴은 실행 중인 모든 프로세스를 스냅샷으로 순회하며 이름이 `x64dbg.exe`인 프로세스를 찾아 강제 종료하는 전형적인 "분석 도구 킬러" 코드다.

## 관련 글
- REV-0503 — WinAPI 프로세스 함수 사전: CreateProcess 계열
- REV-0505 — WinAPI 스레드 함수 사전: CreateThread ExitThread
- REV-0130 — IsDebuggerPresent 안티디버깅 식별

## 출처/검증
- `OpenProcess`/`TerminateProcess`/`ExitProcess` 시그니처, `PROCESS_*` 접근 권한 상수, 실패값 규칙은 Microsoft Win32 API 공식 문서 기준(2026-09-08 확인 서술).
