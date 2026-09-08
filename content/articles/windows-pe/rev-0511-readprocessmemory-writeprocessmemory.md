---
id: REV-0511
title: "WinAPI 메모리 함수 사전: ReadProcessMemory WriteProcessMemory"
slug: "rev-0511-readprocessmemory-writeprocessmemory"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["ReadProcessMemory", "WriteProcessMemory", "프로세스 인젝션", "PROCESS_VM_READ", "PROCESS_VM_WRITE", "원격 메모리 접근"]
aliases: ["리드프로세스메모리", "라이트프로세스메모리", "RPM WPM", "원격 프로세스 메모리 읽기 쓰기 함수"]
symptom_keywords: ["ReadProcessMemory가 뭘 읽는지 모르겠다", "WriteProcessMemory로 다른 프로세스에 뭘 쓰는지 모르겠다", "프로세스 인젝션 패턴을 찾고 있다", "OpenProcess 이후 메모리를 조작하는 코드를 발견했다", "디버거가 소프트웨어 브레이크포인트를 어떻게 심는지 궁금하다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`ReadProcessMemory`/`WriteProcessMemory`는 `OpenProcess`로 얻은 핸들을 이용해 **다른 프로세스**의 가상 메모리를 직접 읽고 쓰는 API로, 디버거가 대상 프로세스에 소프트웨어 브레이크포인트(`0xCC`)를 심거나 변수 값을 확인하는 데도 쓰이지만 `VirtualAllocEx`/`CreateRemoteThread`와 함께 쓰이면 대표적인 프로세스 인젝션(코드 주입) 패턴이 된다.

## 언제 검색해야 하나
- Import 목록에서 `ReadProcessMemory`/`WriteProcessMemory`를 발견하고, 이 프로그램이 다른 프로세스의 메모리를 건드리는지(자기 자신이 아니라) 확인해야 할 때
- `OpenProcess` → `VirtualAllocEx` → `WriteProcessMemory` → `CreateRemoteThread`로 이어지는 전형적인 DLL/셸코드 인젝션 흐름을 진단해야 할 때
- x64dbg/WinDbg 같은 디버거 자체가 내부적으로 어떻게 브레이크포인트를 심고 메모리 값을 조회하는지 원리 수준에서 이해하고 싶을 때
- 프로세스 할로잉(hollowing) 같은 고급 인젝션 기법의 첫 신호를 찾아야 할 때

## 핵심 개념

### 함수 시그니처
```c
BOOL ReadProcessMemory(
    HANDLE  hProcess,             // 1. 읽을 대상 프로세스 핸들(PROCESS_VM_READ 권한 필요)
    LPCVOID lpBaseAddress,        // 2. 대상 프로세스 안에서 읽을 시작 주소
    LPVOID  lpBuffer,             // 3. 결과를 저장할 내 프로세스 쪽 버퍼 주소
    SIZE_T  nSize,                // 4. 읽을 바이트 수
    SIZE_T  *lpNumberOfBytesRead  // 5. 실제로 읽은 바이트 수(NULL 가능)
);

BOOL WriteProcessMemory(
    HANDLE  hProcess,                // 1. 쓸 대상 프로세스 핸들(PROCESS_VM_WRITE + PROCESS_VM_OPERATION 권한 필요)
    LPVOID  lpBaseAddress,           // 2. 대상 프로세스 안에서 쓸 시작 주소
    LPCVOID lpBuffer,                // 3. 써넣을 데이터가 있는 내 프로세스 쪽 버퍼 주소
    SIZE_T  nSize,                   // 4. 쓸 바이트 수
    SIZE_T  *lpNumberOfBytesWritten  // 5. 실제로 쓴 바이트 수(NULL 가능)
);
```
두 함수 모두 `kernel32.dll`(내부적으로 `KernelBase.dll` → `ntdll.dll`의 `NtReadVirtualMemory`/`NtWriteVirtualMemory`)이 제공하며, `hProcess`가 **자기 자신**(`GetCurrentProcess()`가 반환하는 의사 핸들 `-1`)일 수도 있지만, 대개 `OpenProcess`(REV-0504)로 얻은 **다른 프로세스**의 핸들과 함께 쓰일 때 리버싱 관점에서 의미가 커진다.

### 필요한 접근 권한
`OpenProcess` 호출 시 요청한 `dwDesiredAccess`에 최소한 `PROCESS_VM_READ`(0x0010, 읽기용), `PROCESS_VM_WRITE`(0x0020)와 `PROCESS_VM_OPERATION`(0x0008, 쓰기용)이 포함되어 있어야 성공한다. 인젝션 목적 코드는 대개 `PROCESS_ALL_ACCESS`(0x1FFFFF)처럼 넓은 권한을 한 번에 요청하는 경우가 많아, `OpenProcess` 인자만 봐도 의도를 짐작할 수 있다.

### 왜 리버싱에서 핵심 API인가
- **프로세스 인젝션 탐지**: `OpenProcess` → `VirtualAllocEx`(대상 프로세스에 메모리 확보) → `WriteProcessMemory`(셸코드/DLL 경로 문자열 기입) → `CreateRemoteThread`(대상 프로세스 안에서 새 스레드로 실행 시작)로 이어지는 4단계는 클래식 인젝션 패턴이며, 이 중 세 번째가 `WriteProcessMemory`다.
- **디버거의 브레이크포인트 구현 원리**: x64dbg 같은 디버거가 "여기 브레이크포인트"를 걸면, 내부적으로 해당 주소의 원래 1바이트를 `ReadProcessMemory`로 백업해두고 `WriteProcessMemory`로 그 자리에 `0xCC`(INT3)를 써넣는다. 실행이 멈춘 뒤 다시 실행을 재개할 때는 원래 바이트를 되돌려 쓴다. 즉 REV-0537(소프트웨어 브레이크포인트 탐지)의 원리를 이해하려면 이 두 함수가 정확히 어떻게 협력하는지 알아야 한다.
- **메모리 패치 도구/치트 엔진류**: 실행 중인 다른 프로세스의 값을 실시간으로 바꾸는 도구들도 결국 이 두 API 위에서 동작한다.

## 화면/코드에서 보이는 징후
```asm
push PROCESS_ALL_ACCESS
push [pid]
call OpenProcess
mov  [hProc], eax
...
push 0
push 3000h          ; MEM_COMMIT|MEM_RESERVE
push [size]
push 0
push [hProc]
call VirtualAllocEx
mov  [remoteBuf], eax
...
push 0
push [size]
push [localBuf]     ; 셸코드/DLL 경로
push [remoteBuf]
push [hProc]
call WriteProcessMemory
...
call CreateRemoteThread
```
- `OpenProcess` → `VirtualAllocEx` → `WriteProcessMemory` → `CreateRemoteThread` 네 API가 연달아 등장하면 사실상 인젝션 코드로 확신할 수 있다.
- `hProcess` 인자가 `GetCurrentProcess()`(-1)가 아니라 `OpenProcess`에서 얻은 값이면 대상이 "남의 프로세스"임을 뜻한다.

## 가장 먼저 할 것
`ReadProcessMemory`/`WriteProcessMemory` 호출을 발견하면 첫 번째 인자(`hProcess`)가 어디서 왔는지부터 추적한다. `GetCurrentProcess()`의 결과라면 자기 자신에 대한 조작(디버깅 우회, 자기 코드 패치 등)이고, `OpenProcess`의 결과라면 다른 프로세스에 대한 조작(인젝션 가능성)이다.

## 단계별 절차
**1) hProcess 출처 확인(IDA)**
`X`(xref)로 `hProcess` 변수가 초기화된 지점을 찾아 `OpenProcess`인지 `GetCurrentProcess`인지 구분한다.

**2) 인젝션 체인 여부 확인**
같은 함수/근처 코드에 `VirtualAllocEx`, `CreateRemoteThread`, `NtCreateThreadEx` 같은 이름이 함께 있는지 Imports 목록에서 확인한다.

**3) x64dbg로 쓰는 데이터 확인**
```text
bp WriteProcessMemory
run
; x64: R8 = lpBuffer(내 쪽 데이터), R9 = nSize
; R8이 가리키는 내용을 Follow in Dump로 확인 — 셸코드/DLL 경로 문자열인지 바로 판단 가능
```

**4) 대상 주소(lpBaseAddress) 확인**
두 번째 인자가 대상 프로세스 안의 어떤 주소인지(랜덤처럼 보이면 `VirtualAllocEx`가 방금 돌려준 주소일 가능성) 확인한다.

## 명령어/단축키
- x64dbg: `bp ReadProcessMemory`, `bp WriteProcessMemory`, `Ctrl+F9`(Execute till return)
- x64dbg: 우클릭 → `Search for` → `All Modules` → `Intermodular calls`로 이 API를 호출하는 모든 지점을 한 번에 나열
- IDA: `X`(xref), Imports 창에서 `VirtualAllocEx`/`CreateRemoteThread` 동시 존재 여부 확인

## 출력 해석
- `ReadProcessMemory`/`WriteProcessMemory`가 `FALSE`(0)를 반환하면 실패이며, 흔한 원인은 권한 부족(`OpenProcess`에서 필요한 `PROCESS_VM_*` 권한을 요청하지 않음)이나 대상 주소가 유효하지 않은 경우다. `GetLastError()`로 `ERROR_ACCESS_DENIED`(5) 등을 확인한다.
- `lpNumberOfBytesRead`/`Written`이 요청한 `nSize`보다 작으면 부분적으로만 성공한 것이므로, 코드가 이를 제대로 검사하는지도 확인 대상이다.

## 흔한 실수
- `WriteProcessMemory`만 보고 바로 "인젝션"이라 단정하는 것 — 디버거의 정상적인 브레이크포인트 관리, 합법적인 자동화 도구(핫패치, 접근성 도구)에서도 쓰이므로 `hProcess` 출처와 주변 API 조합을 함께 봐야 한다.
- `lpBuffer`(내 쪽 데이터 버퍼)와 `lpBaseAddress`(대상 프로세스 쪽 주소)를 혼동해서 반대로 해석하는 것.
- 자기 자신에 대한 `ReadProcessMemory(GetCurrentProcess(), ...)` 호출을 "이상하다"고 여기는 것 — 일부 코드는 단순히 API 호출을 통일하려고 자기 자신을 대상으로도 이 API를 쓴다(정상적인 패턴).

## 막혔을 때 다음 체크
- 대상 프로세스 핸들을 얻는 과정이 궁금하다면 → REV-0504 WinAPI 프로세스 함수 사전: OpenProcess TerminateProcess
- 대상 프로세스에 메모리를 새로 할당하는 `VirtualAllocEx`와 짝을 이루는 로컬 버전이 궁금하다면 → REV-0508 WinAPI 메모리 함수 사전: VirtualAlloc VirtualProtect
- 소프트웨어 브레이크포인트(0xCC)가 어떻게 심어지고 탐지되는지 더 깊이 보고 싶다면 → REV-0537 소프트웨어 브레이크포인트(0xCC) 탐지 기법

## 미니 예제
```c
HANDLE hProc = OpenProcess(PROCESS_ALL_ACCESS, FALSE, targetPid);
LPVOID remote = VirtualAllocEx(hProc, NULL, shellcodeSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
WriteProcessMemory(hProc, remote, shellcode, shellcodeSize, NULL);
CreateRemoteThread(hProc, NULL, 0, (LPTHREAD_START_ROUTINE)remote, NULL, 0, NULL);
```
x64dbg에서 `bp WriteProcessMemory`로 멈춘 뒤 `R8`(lpBuffer)을 Follow in Dump하면 곧 대상 프로세스에 심어질 셸코드 바이트열을 실행 전에 그대로 확인할 수 있다.

## 관련 글
- REV-0504 — WinAPI 프로세스 함수 사전: OpenProcess TerminateProcess
- REV-0508 — WinAPI 메모리 함수 사전: VirtualAlloc VirtualProtect
- REV-0537 — 소프트웨어 브레이크포인트(0xCC) 탐지 기법

## 출처/검증
- `ReadProcessMemory`/`WriteProcessMemory`의 시그니처와 필요 접근 권한(`PROCESS_VM_READ`/`WRITE`/`OPERATION`)은 Microsoft 공식 문서(learn.microsoft.com, "ReadProcessMemory function" / "WriteProcessMemory function") 기준이다(2026-09-08 확인).
- 프로세스 인젝션 4단계 패턴과 디버거의 소프트웨어 브레이크포인트 구현 원리는 일반적인 윈도우 리버싱/악성코드 분석 관례 레퍼런스 기준이다.
