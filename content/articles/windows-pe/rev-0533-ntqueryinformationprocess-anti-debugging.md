---
id: REV-0533
title: "NtQueryInformationProcess로 하는 안티디버깅"
slug: "rev-0533-ntqueryinformationprocess-anti-debugging"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["NtQueryInformationProcess", "ProcessDebugPort", "ProcessDebugObjectHandle", "ProcessDebugFlags", "ntdll 안티디버깅", "PROCESSINFOCLASS"]
aliases: ["NtQueryInformationProcess 안티디버깅", "ProcessDebugPort 검사", "ntdll 디버거 탐지", "NtQueryInformationProcess 우회"]
symptom_keywords: ["ntdll.dll의 NtQueryInformationProcess가 안티디버깅에 쓰이는지 모르겠음", "ProcessDebugPort가 뭔지 모르겠음", "ProcessInformationClass 7이 뭔지 모르겠음", "IsDebuggerPresent는 없는데 여전히 디버거를 감지하는 것 같음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`NtQueryInformationProcess`는 `ntdll.dll`이 제공하는 범용 프로세스 정보 조회 함수로, 세 번째 인자로 넘기는 `PROCESSINFOCLASS` 열거값에 따라 완전히 다른 정보를 반환하는데, 그중 `ProcessDebugPort`(7), `ProcessDebugObjectHandle`(30), `ProcessDebugFlags`(31) 세 가지는 커널 레벨에서 디버거 연결 여부를 직접 확인하는 값이라 `IsDebuggerPresent`보다 훨씬 후킹하기 까다로운 안티디버깅 수단으로 쓰인다.

## 언제 검색해야 하나
- Import Table에 `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`는 안 보이는데 여전히 디버거로 열면 동작이 달라지는 바이너리를 만났을 때
- `ntdll.dll`에서 `NtQueryInformationProcess`를 동적으로 로드(`GetProcAddress`)하는 코드를 발견했을 때
- 함수 호출 시 세 번째 인자로 `7`, `30`, `31` 같은 낯선 상수가 들어가는 것을 보고 그 의미를 확인하고 싶을 때
- ScyllaHide로 `IsDebuggerPresent`류를 우회했는데도 여전히 감지되는 이유를 찾고 싶을 때

## 핵심 개념

### 함수 시그니처
```c
NTSTATUS NtQueryInformationProcess(
  HANDLE           ProcessHandle,
  PROCESSINFOCLASS ProcessInformationClass,
  PVOID            ProcessInformation,
  ULONG            ProcessInformationLength,
  PULONG           ReturnLength
);
```
이 함수는 마이크로소프트가 공식적으로 "완전히 문서화하지 않은(partially documented)" Native API에 속한다 — `ntdll.dll`이 내보내지만, 모든 `PROCESSINFOCLASS` 값이 공개 문서에 정리되어 있지는 않다. `winternl.h` 헤더에 함수 원형과 일부 상수가 선언되어 있어 개발자가 직접 가져다 쓸 수는 있지만, 향후 버전에서 동작이 바뀔 수 있다는 점을 마이크로소프트가 명시하고 있다.

### 안티디버깅에 쓰이는 세 가지 ProcessInformationClass
| 값(10진수) | 이름 | 반환되는 정보와 의미 |
|---|---|---|
| `7` | `ProcessDebugPort` | 디버거가 프로세스에 연결될 때 커널이 만드는 디버그 포트 핸들 값. 디버거가 없으면 `0`, 있으면 `-1`(모든 비트 1, 즉 `0xFFFFFFFFFFFFFFFF`)이 반환됨 |
| `30` | `ProcessDebugObjectHandle` | 프로세스와 연결된 디버그 객체(Debug Object)의 핸들. 디버거가 없으면 `STATUS_PORT_NOT_SET`(`0xC0000353`) 오류와 함께 핸들 값이 `0`으로 나옴 |
| `31` | `ProcessDebugFlags` | 디버거 없이 실행 중이면 `1`(`PROCESS_DEBUG_INHERIT`가 아닌 상태), 디버거가 붙어 있으면 `0`이 반환됨(다른 두 값과 반대로 "0이면 디버거 있음"이라는 점에 주의) |

세 값 모두 커널 오브젝트 관리자 수준에서 디버그 연결 상태를 추적하는 정보이므로, `IsDebuggerPresent`처럼 단순히 PEB의 1바이트를 읽는 것보다 근본적으로 조작하기 어렵다. PEB만 패치해서는 이 값들이 바뀌지 않는다.

### ProcessDebugPort(7) 값의 특이점
`ProcessDebugPort`가 반환하는 값은 `BOOL`이 아니라 `DWORD_PTR` 크기의 값이며, 디버거가 붙어 있으면 관례적으로 `0xFFFFFFFF`(32비트에서는 이 값, 64비트에서도 확장된 형태)가 반환된다는 점이 특징이다. 단순히 "0이 아니면 참"으로 처리하는 코드가 많아, 검사 자체는 `test`/`cmp` 이후 분기로 이어지는 익숙한 패턴을 따른다.

### ProcessDebugObjectHandle(30)의 반환값 해석
이 클래스는 `NTSTATUS` 반환값 자체도 함께 확인해야 한다. 디버거가 없을 때는 함수가 `STATUS_PORT_NOT_SET`을 반환하면서 출력 버퍼에 핸들 값 `0`을 채운다. 디버거가 있을 때는 `STATUS_SUCCESS`(`0`)와 함께 유효한 핸들 값이 채워진다. 즉 이 검사는 출력 버퍼 값뿐 아니라 함수 자체의 리턴 코드(`EAX`/`RAX`)도 함께 봐야 정확히 판단할 수 있는, 세 가지 중 가장 정교한 방식이다.

### ProcessDebugFlags(31)의 반대 방향 논리
이 값은 "디버거가 없으면 1(`EPROCESS_DEBUG_INHERIT` 관련 플래그가 세팅되지 않은 정상 상태), 디버거가 있으면 0"으로, 앞선 두 값과 논리가 반대(0이 "디버거 있음")라는 점에서 코드를 읽을 때 특히 헷갈리기 쉽다. 분기 방향을 반드시 직접 따라가서 확인해야 한다.

### 왜 이 API가 골치 아픈가
`NtQueryInformationProcess`는 단일 함수 이름 아래 수십 가지 `PROCESSINFOCLASS`를 처리하므로, Import Table이나 xref만으로는 "이게 안티디버깅용 호출인지 아니면 그냥 프로세스 기본 정보(`ProcessBasicInformation`, 값 `0`) 조회인지" 바로 구분되지 않는다. 반드시 각 호출부에서 두 번째 인자 값을 직접 확인해야 한다.

## 화면/코드에서 보이는 징후
- `ntdll.dll`을 `GetModuleHandle`/`LoadLibrary`로 로드한 뒤 `GetProcAddress(hNtdll, "NtQueryInformationProcess")`로 함수 포인터를 얻는 코드가 있음(정적 임포트 없이 동적 로딩되는 경우가 흔함).
- 호출 직전 두 번째 인자(`RDX`)에 `7`, `1Eh`(30), `1Fh`(31) 같은 상수가 채워짐.
- 세 번째 인자로 `lea`를 이용해 스택 변수 주소를 만들어 넘기는 패턴이 `CheckRemoteDebuggerPresent`(REV-0131/REV-0532)와 유사하게 나타남.
- 호출 이후 `NTSTATUS` 반환값(`EAX`)과 출력 버퍼 값 두 가지를 모두 검사하는 코드가 이어짐.

## 가장 먼저 할 것
`NtQueryInformationProcess` 호출을 발견하면 가장 먼저 두 번째 인자(`ProcessInformationClass`) 값을 확인한다. `7`, `30`, `31` 중 하나라면 안티디버깅 목적일 가능성이 매우 높고, 그 외의 값(예: `0` = `ProcessBasicInformation`)이라면 단순 정보 조회일 가능성이 크다.

## 단계별 절차

**1) 동적 로딩 여부 확인**

Imports 목록에 `NtQueryInformationProcess`가 정적으로 없다면, `GetProcAddress` 호출부(REV-0129)를 먼저 찾아 `"NtQueryInformationProcess"` 문자열이 넘어가는 지점을 확인한다.

**2) 호출 지점 나열**

IDA에서 함수 포인터를 통해 호출되는 간접 호출(`call rax` 형태)이라면 xref가 바로 안 잡힐 수 있으므로, 함수 포인터가 저장된 전역/지역 변수를 추적해 실제 호출 지점을 찾는다.

**3) 두 번째 인자 값 확인**

각 호출 직전 `RDX`(x64) 값을 역추적해 `7`/`30`/`31` 중 하나인지 확인한다.

**4) 세 번째 인자(출력 버퍼) 주소 기록**

`lea r8, [주소]` 형태로 준비되는 출력 버퍼 주소를 기록해둔다. 이 값이 실제 결과가 쓰이는 위치다.

**5) 호출 이후 검사 로직 파악**

`ProcessDebugPort`/`ProcessDebugObjectHandle`은 "0이 아니면 감지", `ProcessDebugFlags`는 "0이면 감지"라는 반대 논리를 가지므로, 실제 분기(`je`/`jne`)를 직접 따라가 어느 쪽이 감지 경로인지 확정한다.

**6) x64dbg로 동적 확인**

```text
bp ntdll.NtQueryInformationProcess
run
; RDX 값 확인하여 어떤 ProcessInformationClass인지 판단
Ctrl+F9
; 출력 버퍼(세 번째 인자가 가리키는 주소)의 값을 Dump 창에서 확인
```

**7) 우회가 필요하면 출력 버퍼/반환값 조작**

REV-0532에서 다룬 것과 같은 방식으로, 함수 실행 후 출력 버퍼 값을 직접 덮어쓰거나(`ProcessDebugPort`는 0으로, `ProcessDebugFlags`는 1로), `ProcessDebugObjectHandle`의 경우 `NTSTATUS` 반환값(`EAX`)까지 함께 `STATUS_PORT_NOT_SET`으로 맞춰야 한다.

## 명령어/단축키
- IDA: `Alt+T`로 `"NtQueryInformationProcess"` 문자열 검색, 함수 포인터 변수에 `X`(xref)로 사용처 추적
- x64dbg: `bp ntdll.NtQueryInformationProcess`, `Ctrl+F9`(Execute till return), Dump 창에서 출력 버퍼 값 확인
- x64dbg: Registers 창에서 `RDX`(ProcessInformationClass), `R8`(출력 버퍼 주소) 확인

## 출력 해석
- `ProcessDebugPort` 값이 `0`이 아니면(대개 `-1`) 디버거가 연결된 상태다.
- `ProcessDebugObjectHandle` 호출의 반환값(`NTSTATUS`)이 `STATUS_SUCCESS`(`0`)이면 디버거가 있다는 뜻이고, `STATUS_PORT_NOT_SET`(`0xC0000353`)이면 없다는 뜻이다 — 출력 버퍼 값만 보지 말고 반환값도 함께 확인해야 한다.
- `ProcessDebugFlags`가 `0`이면 디버거가 있다는 뜻(다른 두 값과 반대 논리)이다.

## 흔한 실수
- `ProcessDebugFlags`(31)를 다른 두 값과 같은 논리(0=없음, 1=있음)로 착각해서 분기를 반대로 해석하는 것.
- `ProcessDebugObjectHandle`을 확인할 때 출력 버퍼 값만 보고, `NTSTATUS` 반환값을 놓쳐서 잘못된 결론을 내리는 것.
- PEB `BeingDebugged`만 패치하면 이 API도 함께 속을 것이라고 가정하는 것 — 이 값들은 커널이 직접 관리하는 별도 정보이므로 PEB 패치와 무관하게 정확한 값을 반환한다.
- `NtQueryInformationProcess`가 다른 `PROCESSINFOCLASS`(예: `ProcessBasicInformation`, 단순 PEB 주소나 PID 조회용)로 호출된 경우까지 전부 안티디버깅으로 오해하는 것 — 반드시 두 번째 인자 값을 확인해야 한다.

## 막혔을 때 다음 체크
- 이 API로도 여전히 안 막히는 다른 검사가 있는지 전체 목록을 다시 보고 싶다면 → REV-0529 Windows 안티디버깅 기법 종류 빠른 참조표
- 더 기본적인 `IsDebuggerPresent`/`CheckRemoteDebuggerPresent`부터 순서대로 복습하고 싶다면 → REV-0130, REV-0131
- 출력 인자를 직접 조작하는 우회 절차의 기본형이 궁금하다면 → REV-0532 CheckRemoteDebuggerPresent 우회 실습 개념
- 스레드 단위로 디버거 이벤트를 회피하는 관련 기법이 궁금하다면 → REV-0534 NtSetInformationThread ThreadHideFromDebugger 기법

## 미니 예제
```asm
; NtQueryInformationProcess(GetCurrentProcess(), ProcessDebugPort(7), &debugPort, sizeof(debugPort), NULL)
call GetCurrentProcess
mov  rcx, rax
mov  edx, 7                    ; ProcessDebugPort
lea  r8,  [rbp-0x8]             ; &debugPort (출력 버퍼)
mov  r9d, 8                     ; ProcessInformationLength
call NtQueryInformationProcess
mov  rax, [rbp-0x8]
test rax, rax
jne  detected_branch            ; 0이 아니면(대개 -1) 디버거 있음으로 판단
```

## 관련 글
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0131 — CheckRemoteDebuggerPresent 식별
- REV-0532 — CheckRemoteDebuggerPresent 우회 실습 개념
- REV-0534 — NtSetInformationThread ThreadHideFromDebugger 기법
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 출처/검증
- `NtQueryInformationProcess` 함수 시그니처는 Microsoft 공식 문서(learn.microsoft.com, "NtQueryInformationProcess function")에 부분 문서화되어 있음(2026-09-08 확인). `ProcessDebugPort`(7), `ProcessDebugObjectHandle`(30), `ProcessDebugFlags`(31) 값과 안티디버깅 활용 방식은 공식 문서에 전부 명시되지는 않으며, 리버싱/보안 커뮤니티에서 널리 검증되고 통용되는 값을 기준으로 정리했다. 마이크로소프트는 이 API가 향후 변경될 수 있는 미문서화 영역을 포함한다고 명시하고 있다.
