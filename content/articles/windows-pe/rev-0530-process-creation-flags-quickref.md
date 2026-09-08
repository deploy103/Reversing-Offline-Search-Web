---
id: REV-0530
title: "Windows 프로세스 생성 플래그 빠른 참조표"
slug: "rev-0530-process-creation-flags-quickref"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CreateProcess", "dwCreationFlags", "CREATE_SUSPENDED", "DEBUG_PROCESS", "CREATE_NO_WINDOW", "프로세스 생성 플래그"]
aliases: ["CreateProcess 플래그 표", "dwCreationFlags 사전", "프로세스 생성 옵션 표", "CREATE_SUSPENDED 뜻"]
symptom_keywords: ["CreateProcess의 dwCreationFlags 값이 뭔지 모르겠음", "CREATE_SUSPENDED가 뭔지 모르겠음", "프로세스 할로잉 관련 플래그가 궁금함", "DEBUG_PROCESS 플래그가 뭔지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CreateProcess` 계열 API의 `dwCreationFlags` 인자는 새 프로세스를 어떤 상태로 만들지(일시 정지 상태로 시작할지, 새 콘솔을 열지, 디버깅 대상으로 만들지 등)를 비트 플래그로 지정하는 값으로, 특히 `CREATE_SUSPENDED`와 `DEBUG_PROCESS`는 프로세스 할로잉이나 디버거/런처 구현 코드를 분석할 때 반드시 알아둬야 하는 핵심 플래그다.

## 언제 검색해야 하나
- 디스어셈블리에서 `call CreateProcessW`(또는 A) 직전에 여러 상수가 OR로 조합된 값이 `dwCreationFlags` 인자로 들어가는 것을 보고 그 값의 의미를 확인하고 싶을 때
- 악성코드 분석 중 프로세스 할로잉(process hollowing) 패턴을 의심할 때, `CREATE_SUSPENDED`가 쓰였는지 먼저 확인하고 싶을 때
- 어떤 도구가 다른 프로세스를 자식 프로세스로서 디버깅 모드로 실행시키는 코드를 만났을 때 `DEBUG_PROCESS`/`DEBUG_ONLY_THIS_PROCESS`의 차이가 궁금할 때
- 콘솔 창이 안 뜨는 이유가 `CREATE_NO_WINDOW` 플래그 때문인지 확인하고 싶을 때

## 핵심 개념

### 함수 시그니처에서의 위치
```c
BOOL CreateProcessW(
  LPCWSTR               lpApplicationName,
  LPWSTR                lpCommandLine,
  LPSECURITY_ATTRIBUTES lpProcessAttributes,
  LPSECURITY_ATTRIBUTES lpThreadAttributes,
  BOOL                  bInheritHandles,
  DWORD                 dwCreationFlags,   // 이 문서가 다루는 인자
  LPVOID                lpEnvironment,
  LPCWSTR               lpCurrentDirectory,
  LPSTARTUPINFOW        lpStartupInfo,
  LPPROCESS_INFORMATION lpProcessInformation
);
```
x64 호출 규약(REV-0527)상 6번째 인자이므로, 처음 4개 레지스터(`RCX, RDX, R8, R9`)를 넘어 스택(Shadow Space 이후 첫 번째 슬롯, `[RSP+0x20]`)에 위치한다.

### 자주 보는 플래그 값 표
| 플래그 이름 | 값 | 의미 |
|---|---|---|
| `DEBUG_PROCESS` | `0x00000001` | 새 프로세스와 그 프로세스가 만드는 모든 자식 프로세스까지 디버깅 대상으로 삼음 |
| `DEBUG_ONLY_THIS_PROCESS` | `0x00000002` | 새 프로세스만 디버깅 대상, 자식 프로세스는 제외 |
| `CREATE_SUSPENDED` | `0x00000004` | 메인 스레드를 일시 정지 상태로 생성(프로세스 할로잉의 핵심 플래그) |
| `DETACHED_PROCESS` | `0x00000008` | 부모의 콘솔을 상속하지 않음(콘솔 없는 프로세스 생성) |
| `CREATE_NEW_CONSOLE` | `0x00000010` | 새 콘솔 창을 생성 |
| `CREATE_NEW_PROCESS_GROUP` | `0x00000200` | 새 프로세스 그룹 생성(Ctrl+C 신호 전파 제어와 관련) |
| `CREATE_UNICODE_ENVIRONMENT` | `0x00000400` | 환경 블록이 유니코드 형식임을 지정 |
| `CREATE_SEPARATE_WOW_VDM` | `0x00000800` | 16비트 앱을 별도 VDM에서 실행(구식) |
| `CREATE_SUSPENDED` 등과 함께 자주 보이는 `NORMAL_PRIORITY_CLASS` | `0x00000020` | 우선순위 클래스 지정(생성 플래그와 같은 DWORD에 OR로 합쳐짐) |
| `CREATE_NO_WINDOW` | `0x08000000` | 콘솔 창을 아예 만들지 않음(백그라운드 실행) |
| `EXTENDED_STARTUPINFO_PRESENT` | `0x00080000` | `STARTUPINFOEXW` 구조체 사용을 지정(프로세스 완화 정책 등 확장 속성 설정 시 필요) |
| `CREATE_PROTECTED_PROCESS` | `0x00040000` | 보호된 프로세스로 생성(DRM 등 특수 목적, 일반 프로그램에서는 드묾) |

우선순위 클래스(`IDLE_PRIORITY_CLASS`, `NORMAL_PRIORITY_CLASS`, `HIGH_PRIORITY_CLASS`, `REALTIME_PRIORITY_CLASS` 등)도 같은 `dwCreationFlags` DWORD에 OR로 함께 들어가므로, 이 필드 값을 분해할 때 생성 옵션과 우선순위 값이 섞여 있을 수 있다는 점을 염두에 둔다.

### 프로세스 할로잉과 CREATE_SUSPENDED
악성코드 분석에서 특히 중요한 패턴은 다음과 같다: `CreateProcessW`를 `CREATE_SUSPENDED` 플래그로 호출해 정상 프로세스(예: `svchost.exe`, `explorer.exe`)를 "실행은 됐지만 메인 스레드는 멈춘" 상태로 띄운 뒤, 그 메모리 공간의 이미지를 지우고(`NtUnmapViewOfSection` 등) 악성 코드를 대신 써넣은 다음, `ResumeThread`로 재개시키는 기법(프로세스 할로잉)이다. `CREATE_SUSPENDED`가 보이면 이후 코드에서 `WriteProcessMemory`, `SetThreadContext`, `ResumeThread`로 이어지는 흐름이 있는지 반드시 확인해야 한다.

### DEBUG_PROCESS와 안티디버깅 우회 도구의 관계
일부 안티디버깅 우회 도구나 언패커는 대상 프로그램을 직접 `DEBUG_PROCESS`/`DEBUG_ONLY_THIS_PROCESS` 플래그로 실행시켜 스스로 디버거 역할을 하면서, 디버그 이벤트 루프(`WaitForDebugEvent`/`ContinueDebugEvent`)를 통해 프로세스를 제어한다. 이런 도구의 소스나 바이너리를 분석할 때 이 플래그가 그 신호가 된다.

## 화면/코드에서 보이는 징후
- 디스어셈블리에서 `CreateProcessW`/`CreateProcessA` 호출 직전 6번째 인자 위치(`mov dword ptr [rsp+0x20], 4` 등)에 `4`(`CREATE_SUSPENDED`) 같은 값이 채워짐.
- 뒤이어 `WriteProcessMemory`, `GetThreadContext`/`SetThreadContext`, `ResumeThread` 호출이 연달아 나오면 프로세스 할로잉 패턴을 강하게 의심해야 한다.
- `CREATE_NO_WINDOW`(`0x08000000`)가 쓰인 경우 실행해도 콘솔 창이 뜨지 않아, 실제로 자식 프로세스가 실행되고 있는지 Process Explorer/작업 관리자로 별도 확인해야 한다.

## 가장 먼저 할 것
`CreateProcess` 호출을 발견하면 6번째 인자(`dwCreationFlags`) 값을 먼저 확인한다. `CREATE_SUSPENDED`(`4`) 비트가 켜져 있는지가 가장 중요한 첫 신호이며, 켜져 있다면 즉시 그 뒤를 따라가며 할로잉 관련 API가 이어지는지 확인한다.

## 단계별 절차

**1) CreateProcess 호출부 찾기**

IDA Imports에서 `CreateProcessW`/`CreateProcessA`를 검색하고 `X`로 호출 지점을 나열한다.

**2) 6번째 인자 값 추적**

x64 규약(REV-0527)에 따라 5번째 이상 인자는 스택에 쌓이므로, `[rsp+0x20]`에 쓰이는 값을 역추적한다.

**3) 값 분해**

읽은 값을 위 표와 대조해 어떤 플래그들이 OR로 조합됐는지 분해한다. 우선순위 클래스 비트와 생성 옵션 비트가 섞여 있을 수 있으므로 전부 나열해본다.

**4) CREATE_SUSPENDED가 있으면 후속 API 추적**

`GetThreadContext`, `VirtualAllocEx`, `WriteProcessMemory`, `SetThreadContext`, `ResumeThread`가 이어지는지 함수 전체를 스크롤하며 확인한다. 이 조합이 전부 나오면 사실상 프로세스 할로잉으로 확정할 수 있다.

**5) 대상 실행 파일 경로 확인**

첫 번째/두 번째 인자(`lpApplicationName`/`lpCommandLine`)로 넘어가는 문자열을 확인해 어떤 실행 파일을 대상으로 하는지(정상 시스템 파일을 가장하는 경우가 많음) 파악한다.

## 명령어/단축키
- IDA: Imports에서 `CreateProcess` 검색, `X`(xref), 스택 인자 값 확인을 위해 Hex-Rays 의사코드(`F5`) 활용 권장(인자가 이름 붙어 훨씬 읽기 쉬움)
- x64dbg: `bp CreateProcessW`, 브레이크 시 스택/레지스터 창에서 각 인자 값 직접 확인
- Sysinternals Process Explorer/Process Monitor: 실제 실행 시 생성되는 프로세스와 그 상태(Suspended 여부)를 동적으로 관찰 가능

## 출력 해석
- `dwCreationFlags & 0x4`(CREATE_SUSPENDED)가 0이 아니면, 새 프로세스는 생성 직후 어떤 코드도 실행하지 않고 멈춰 있다 — `ResumeThread`가 호출되기 전까지는 정상적인 프로세스처럼 보여도 실제로는 아무 동작도 하지 않는다.
- `dwCreationFlags & 0x1`(DEBUG_PROCESS)이 켜져 있으면 호출자 프로세스가 이 새 프로세스의 디버거 역할을 자처한 것이므로, 이후 코드에서 `WaitForDebugEvent` 루프를 찾아야 전체 그림이 완성된다.
- `CREATE_NO_WINDOW`가 켜진 상태에서 프로그램이 아무 반응 없이 끝나는 것처럼 보인다면, 실제로는 백그라운드에서 자식 프로세스가 실행 중일 수 있으므로 작업 관리자의 "세부 정보" 탭에서 프로세스 목록을 확인해야 한다.

## 흔한 실수
- `dwCreationFlags` 값 하나에 여러 플래그가 섞여 있다는 것을 모르고 표에서 정확히 일치하는 값만 찾다가 못 찾는 것 — 반드시 비트 단위로 분해해야 한다.
- `CREATE_SUSPENDED`를 보고 무조건 악성코드로 단정하는 것 — 정상적인 인젝터, 디버거, 런처 프로그램에서도 합법적으로 쓰인다. 후속 API 흐름까지 함께 봐야 판단할 수 있다.
- `DEBUG_PROCESS`와 `DEBUG_ONLY_THIS_PROCESS`를 같은 것으로 혼동하는 것 — 자식 프로세스까지 디버깅 대상에 포함되는지 여부가 다르다.
- 우선순위 클래스 값(`NORMAL_PRIORITY_CLASS`=`0x20` 등)을 생성 옵션 플래그로 착각해 해석하는 것 — 같은 DWORD에 섞여 있지만 의미하는 범주가 다르다.

## 막혔을 때 다음 체크
- 이 인자가 몇 번째 인자로 어디에 위치하는지 다시 확인하고 싶다면 → REV-0527 x64 Calling Convention 레지스터 사용 빠른 참조표
- 프로세스가 크래시할 때 뜨는 예외 코드가 궁금하다면 → REV-0528 Windows 예외 코드(Exception Code) 빠른 참조표
- 이 프로세스 자체가 안티디버깅을 갖추고 있는지 확인하고 싶다면 → REV-0529 Windows 안티디버깅 기법 종류 빠른 참조표
- `NtQueryInformationProcess`로 디버깅 여부를 확인하는 방식이 궁금하다면 → REV-0533 NtQueryInformationProcess로 하는 안티디버깅

## 미니 예제
```asm
; CreateProcessW(NULL, cmdline, NULL, NULL, FALSE, CREATE_SUSPENDED, NULL, NULL, &si, &pi)
xor  rcx, rcx                      ; lpApplicationName = NULL
lea  rdx, [cmdline]                ; lpCommandLine
xor  r8, r8                        ; lpProcessAttributes = NULL
xor  r9, r9                        ; lpThreadAttributes = NULL
mov  dword ptr [rsp+0x20], 0        ; bInheritHandles = FALSE
mov  dword ptr [rsp+0x28], 4        ; dwCreationFlags = CREATE_SUSPENDED (0x4)
mov  qword ptr [rsp+0x30], 0        ; lpEnvironment = NULL
mov  qword ptr [rsp+0x38], 0        ; lpCurrentDirectory = NULL
lea  rax, [si]
mov  [rsp+0x40], rax                ; lpStartupInfo
lea  rax, [pi]
mov  [rsp+0x48], rax                ; lpProcessInformation
call CreateProcessW
; 이후 GetThreadContext / WriteProcessMemory / SetThreadContext / ResumeThread가
; 이어진다면 프로세스 할로잉 패턴으로 확정
```

## 관련 글
- REV-0527 — x64 Calling Convention 레지스터 사용 빠른 참조표
- REV-0528 — Windows 예외 코드(Exception Code) 빠른 참조표
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표
- REV-0533 — NtQueryInformationProcess로 하는 안티디버깅

## 출처/검증
- `CreateProcess` 함수 시그니처와 `dwCreationFlags` 상수 값은 Microsoft 공식 문서(learn.microsoft.com, "CreateProcessW function", "Process Creation Flags") 기준(2026-09-08 확인). 프로세스 할로잉 패턴 설명은 리버싱/악성코드 분석 커뮤니티에서 널리 통용되는 일반적 기법 서술이다.
