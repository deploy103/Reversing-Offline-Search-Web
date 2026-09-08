---
id: REV-0505
title: "WinAPI 스레드 함수 사전: CreateThread ExitThread"
slug: "rev-0505-createthread-exitthread"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CreateThread", "ExitThread", "LPTHREAD_START_ROUTINE", "lpStartAddress", "lpParameter", "CreateRemoteThread"]
aliases: ["CreateThread 함수 사전", "ExitThread 함수 사전", "스레드 생성 API", "스레드 시작 루틴"]
symptom_keywords: ["CreateThread 세 번째 인자가 뭔지 모르겠다", "lpStartAddress가 어디를 가리키는지 확인해야 한다", "CreateThread와 CreateRemoteThread 차이를 모르겠다", "새 스레드가 갑자기 실행되는 코드를 만났다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CreateThread`는 같은 프로세스 안에 새 실행 흐름(스레드)을 만드는 함수로, 3번째 인자(`lpStartAddress`)가 곧 새 스레드가 실행을 시작할 함수 주소이므로 이 함수를 만나면 가장 먼저 그 주소로 이동해 "새 스레드가 정확히 무엇을 하는지" 별도로 분석해야 하며, 이는 멀티스레드 안티디버깅이나 코드 인젝션(`CreateRemoteThread`)의 시작점이 되는 경우가 많다.

## 언제 검색해야 하나
- 메인 흐름과 별개로 갑자기 다른 코드가 실행되는 것을 발견해 "새 스레드가 만들어졌나?"를 의심할 때
- `CreateThread`의 `lpStartAddress`가 가리키는 함수를 IDA에서 별도로 분석해야 할 때
- `CreateThread`와 `CreateRemoteThread`(다른 프로세스에 스레드를 심는 함수)의 차이를 확인하고 싶을 때
- 스레드가 어떻게 종료되는지(`ExitThread` vs 그냥 함수 리턴) 헷갈릴 때

## 핵심 개념
```c
HANDLE CreateThread(
    LPSECURITY_ATTRIBUTES  lpThreadAttributes,
    SIZE_T                  dwStackSize,
    LPTHREAD_START_ROUTINE  lpStartAddress,
    __drv_aliasesMem LPVOID lpParameter,
    DWORD                   dwCreationFlags,
    LPDWORD                 lpThreadId
);
```

**인자별 요약**
1. `lpThreadAttributes` — 대개 `NULL`(기본 보안 속성, 핸들 상속 불가).
2. `dwStackSize` — 새 스레드의 초기 스택 크기(바이트). `0`이면 실행 파일의 PE 헤더에 지정된 기본값(대개 1MB)을 사용한다.
3. `lpStartAddress` — **가장 중요한 인자.** 새 스레드가 실행을 시작할 함수의 주소(`LPTHREAD_START_ROUTINE`, 즉 `DWORD WINAPI ThreadProc(LPVOID param)` 형태의 함수 포인터). IDA에서 이 주소로 이동(`G` 또는 주소 더블클릭)해서 별도 함수로 분석해야 한다.
4. `lpParameter` — `lpStartAddress`가 가리키는 함수에 전달될 단일 인자(포인터). 구조체를 통째로 넘겨 여러 값을 전달하는 경우가 흔하다.
5. `dwCreationFlags` — `0`이면 생성 즉시 실행 시작. `CREATE_SUSPENDED`(0x4)이면 일시정지 상태로 생성되고, 이후 `ResumeThread`가 호출되어야 실제로 실행이 시작된다(REV-0503의 `CREATE_SUSPENDED`와 같은 의미, 대상이 프로세스가 아니라 스레드라는 점만 다름).
6. `lpThreadId` — 새로 생성된 스레드의 ID가 저장될 주소. `NULL`을 넘겨도 되지만(Windows 2000 이후), 있으면 스레드 목록에서 이 값으로 스레드를 특정할 수 있다.

반환값은 성공 시 새 스레드의 `HANDLE`, 실패 시 `NULL`.

**`ExitThread`** — 현재 실행 중인 스레드를 즉시 종료한다.
```c
VOID ExitThread(DWORD dwExitCode);
```
`ThreadProc`가 끝까지 실행되어 `return`으로 리턴해도 결과적으로 `ExitThread`가 자동 호출된 것과 동일하게 처리되지만(C 런타임이 진입점에서 감싸서 처리), 코드 안에서 명시적으로 `ExitThread`를 호출하면 그 지점에서 **즉시** 스레드가 끝나고 그 이후의 코드(스택 해제, 지역 객체 소멸자 등 C++ 관례)가 건너뛰어질 수 있다는 차이가 있다.

**`CreateThread` vs `CreateRemoteThread`** — `CreateThread`는 **자기 프로세스 안**에 스레드를 만들고, `CreateRemoteThread(HANDLE hProcess, ...)`는 인자에 대상 프로세스 핸들이 추가되어 **다른 프로세스 안**에 스레드를 심는다. `CreateRemoteThread`는 코드/DLL 인젝션의 핵심 API이며, `lpStartAddress`가 대상 프로세스의 주소 공간을 가리켜야 하므로 그 앞에 `VirtualAllocEx`+`WriteProcessMemory`로 코드를 미리 심어두는 3단계 패턴(할당 → 쓰기 → 원격 스레드 생성)이 항상 함께 나타난다.

## 화면/코드에서 보이는 징후
- `lea rcx, sub_140012340` / `call CreateThread` 형태로 3번째 인자(x64 기준 R8이지만 x86 stdcall push 순서 기준으로는 다를 수 있음)에 함수 주소가 그대로 들어감. IDA는 이 주소를 자동으로 함수로 인식해 이름(`sub_XXXXXX`)을 붙여준다.
- 메인 함수에서 `CreateThread` 호출 이후 별다른 로직 없이 곧바로 `WaitForSingleObject`로 넘어가는 패턴(스레드 작업이 끝나길 기다림) — REV-0506에서 다룸.
- 여러 개의 `CreateThread` 호출이 반복문 안에서 이루어지면 워커 스레드 풀을 만드는 코드일 수 있다.
- `VirtualAllocEx` → `WriteProcessMemory` → `CreateRemoteThread` 3단계가 연속으로 나타나면 프로세스 인젝션이 거의 확실하다.

## 가장 먼저 할 것
`lpStartAddress`(3번째 인자) 주소로 먼저 이동해서 그 함수가 무엇을 하는지 별도로 분석한다. `CreateThread` 호출 지점만 봐서는 실제로 무슨 일이 일어나는지 알 수 없다 — 반드시 대상 함수 본문을 봐야 한다.

## 단계별 절차
1. IDA에서 `CreateThread` 호출을 `X`(xref)로 찾는다.
2. `F5`로 디컴파일해 3번째 인자(함수 포인터)의 실제 주소를 확인한다.
3. 그 주소를 더블클릭(또는 `G`로 이동)해서 스레드 시작 함수 본문으로 이동해 별도로 분석한다.
4. x64dbg에서 `bp CreateThread` 후 `R8`(lpStartAddress, x64 기준)을 확인하고, 해당 주소에 브레이크포인트(`bp <주소>`)를 추가로 걸어 스레드가 실제로 그 코드에 진입하는 순간을 관찰한다.
5. `dwCreationFlags`가 `CREATE_SUSPENDED`라면 `ResumeThread` 호출까지 찾아 실행이 언제 실제로 시작되는지 확인한다.

## 명령어/단축키
- x64dbg: `bp CreateThread`, `bp <lpStartAddress 주소>`(스레드 진입점에 직접 브레이크포인트), `Ctrl+F9`(리턴까지 실행)
- x64dbg: Threads 창(`Alt+7` 또는 View 메뉴)에서 현재 실행 중인 모든 스레드와 각 스레드의 시작 주소를 한눈에 확인 가능
- IDA: `X`(xref), `F5`(디컴파일), `G`(주소로 이동)

## 출력 해석
- 반환값(`HANDLE`)이 `NULL`이면 스레드 생성 실패.
- `lpThreadId`가 가리키는 값이 채워졌다면 그 TID로 x64dbg Threads 창에서 해당 스레드를 바로 찾아 전환할 수 있다.
- 스레드 시작 함수의 반환값(`DWORD`)은 `GetExitCodeThread`로 나중에 조회 가능하며, 스레드가 어떤 결과(성공/실패/계산값)를 냈는지 나타내는 경우가 많다.

## 흔한 실수
- `CreateThread` 호출 지점만 보고 분석을 끝내는 것 — 실제 로직은 `lpStartAddress`가 가리키는 별도 함수에 있으므로 반드시 그 함수까지 따라가야 한다.
- `CreateThread`와 `CreateRemoteThread`를 같은 것으로 취급하는 것 — 전자는 자기 프로세스, 후자는 인자에 `hProcess`가 추가된 타 프로세스 대상이며 인젝션 여부 판단에 결정적 차이다.
- 메인 스레드가 종료(`ExitProcess`)되면 다른 모든 스레드도 함께 강제 종료된다는 점을 놓치고 "이 워커 스레드가 끝까지 실행될 것"이라 가정하는 것 — `WaitForSingleObject`(REV-0506) 등으로 명시적으로 기다리지 않으면 메인 스레드가 먼저 끝나 워커 스레드 작업이 중간에 잘릴 수 있다.

## 막혔을 때 다음 체크
- 생성한 스레드/프로세스가 끝나길 기다리는 API가 궁금하면 → REV-0506(WaitForSingleObject WaitForMultipleObjects, 추후 작성) 확인.
- 스레드가 아니라 프로세스 자체를 만드는 API가 궁금하면 → REV-0503 확인.
- 다른 프로세스에 스레드를 심는 인젝션 패턴이 의심되면 → REV-0511(ReadProcessMemory WriteProcessMemory, 추후 작성)과 REV-0508(VirtualAlloc VirtualProtect, 추후 작성)을 함께 확인.

## 미니 예제
```c
DWORD WINAPI WorkerProc(LPVOID param) {
    // 별도 스레드에서 실행되는 실제 로직
    return 0;
}

DWORD tid;
HANDLE h = CreateThread(NULL, 0, WorkerProc, NULL, 0, &tid);
```
디스어셈블리에서는 `WorkerProc`의 주소가 `lea rcx/r9, WorkerProc` 형태로 `CreateThread` 호출 인자에 그대로 나타나며, IDA는 이 주소를 자동으로 별도 함수 경계로 인식해 `sub_XXXXXX` 이름을 붙인다.

## 관련 글
- REV-0503 — WinAPI 프로세스 함수 사전: CreateProcess 계열
- REV-0504 — WinAPI 프로세스 함수 사전: OpenProcess TerminateProcess
- REV-0122 — Microsoft x64 Calling Convention

## 출처/검증
- `CreateThread`/`ExitThread`/`CreateRemoteThread` 시그니처, `LPTHREAD_START_ROUTINE` 타입, `CREATE_SUSPENDED` 플래그 동작은 Microsoft Win32 API 공식 문서 기준(2026-09-08 확인 서술).
