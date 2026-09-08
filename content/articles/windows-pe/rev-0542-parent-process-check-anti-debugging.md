---
id: REV-0542
title: "부모 프로세스 확인 안티디버깅(explorer.exe 체크)"
slug: "rev-0542-parent-process-check-anti-debugging"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["부모 프로세스 확인", "explorer.exe", "CreateToolhelp32Snapshot", "Process32First", "ProcessBasicInformation", "InheritedFromUniqueProcessId", "th32ParentProcessID"]
aliases: ["부모 프로세스 검사", "explorer 체크 안티디버깅", "Parent Process Check", "PPID 검사 안티디버깅", "부모 이름 확인 트릭"]
symptom_keywords: ["CreateToolhelp32Snapshot과 Process32First로 부모를 찾는 코드가 있다", "explorer.exe 문자열이 코드에 하드코딩되어 있다", "NtQueryInformationProcess로 InheritedFromUniqueProcessId를 읽는다", "cmd.exe나 x64dbg.exe에서 실행하면 프로그램이 종료된다", "탐색기에서 더블클릭할 때만 정상 동작한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
평범한 사용자가 `.exe`를 더블클릭하면 그 프로세스의 부모는 항상 `explorer.exe`가 되는 반면, 리버서가 x64dbg나 IDA, 또는 `cmd.exe`에서 프로그램을 실행하면 부모 프로세스 이름이 `x64dbg.exe`, `ida64.exe`, `cmd.exe` 등으로 달라지므로, 실행 중에 자신의 부모 프로세스 이름을 확인해서 `explorer.exe`가 아니면 "정상적인 실행 방식이 아니다"라고 판단하는 것이 이 기법의 핵심이다.

## 언제 검색해야 하나
- 코드 문자열에 `"explorer.exe"`가 하드코딩되어 있는 것을 발견했을 때
- `CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)` + `Process32First`/`Process32Next` 조합으로 프로세스 목록을 순회하며 `th32ParentProcessID`를 확인하는 코드를 발견했을 때
- 탐색기에서 더블클릭하면 정상 실행되는데, x64dbg에서 열거나 `cmd.exe`에서 실행하면 프로그램이 조용히 종료되는 것을 발견했을 때
- `NtQueryInformationProcess`로 `ProcessBasicInformation`을 조회하는 코드가 있고, 반환된 구조체의 특정 필드(부모 PID)를 쓰는 것을 발견했을 때

## 핵심 개념

### 부모 프로세스 정보는 어디서 오나
Windows에서 새 프로세스를 만들면 커널은 "누가 이 프로세스를 만들었는가(부모 PID)"를 기록해둔다. 이 정보를 얻는 방법은 크게 두 가지다.

**방법 1: Toolhelp 스냅샷**
```c
HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
PROCESSENTRY32 pe = { sizeof(pe) };
DWORD myPid = GetCurrentProcessId();
DWORD parentPid = 0;
if (Process32First(snap, &pe)) {
    do {
        if (pe.th32ProcessID == myPid) {
            parentPid = pe.th32ParentProcessID;
            break;
        }
    } while (Process32Next(snap, &pe));
}
// parentPid로 다시 한 번 순회해서 이름(szExeFile) 확인
```
프로세스 목록 전체를 순회하며 자기 자신의 `PROCESSENTRY32` 항목을 찾고, 그 안의 `th32ParentProcessID` 필드로 부모 PID를 얻은 뒤, 다시 그 PID를 가진 항목의 `szExeFile`(실행 파일 이름)을 확인한다.

**방법 2: NtQueryInformationProcess**
```c
PROCESS_BASIC_INFORMATION pbi;
ULONG retLen;
NtQueryInformationProcess(GetCurrentProcess(), ProcessBasicInformation,
                           &pbi, sizeof(pbi), &retLen);
// pbi.InheritedFromUniqueProcessId 가 부모 PID
```
`ntdll.dll`의 비공식(정확히는 공식 문서화가 제한적인) API인 `NtQueryInformationProcess`를 `ProcessBasicInformation`(값 0) 클래스로 호출하면 `PROCESS_BASIC_INFORMATION` 구조체의 `InheritedFromUniqueProcessId` 필드에서 부모 PID를 바로 얻을 수 있다. Toolhelp 방식보다 API 호출이 하나로 끝나 더 빠르고 은밀하다.

### 왜 explorer.exe와 비교하나
사용자가 탐색기(Windows Explorer, `explorer.exe`)에서 `.exe` 파일을 더블클릭하면, 새 프로세스��� `explorer.exe`의 자식으로 생성된다. 이것이 "일반 사용자의 정상적인 실행 경로"의 표준 패턴이다. 반면:
- x64dbg에서 `File → Open`으로 실행하면 부모가 `x64dbg.exe`가 된다.
- `cmd.exe`나 PowerShell에서 실행하면 부모가 `cmd.exe`/`powershell.exe`가 된다.
- IDA의 디버거로 실행하면 부모가 `ida64.exe`/`ida.exe`가 된다.

이 차이를 이용해 부모 이름이 `explorer.exe`가 아니면 "리버서/디버거 환경에서 실행 중"이라고 의심하는 것이다.

### 이 기법의 근본적인 한계
이 검사는 **오탐(false positive)이 매우 흔하다**는 치명적인 약점이 있다. 배치 스크립트, 설치 프로그램, 다른 정상 프로그램이 자식 프로세스로 실행하는 경우, 원격 데스크톱/자동화 도구로 실행하는 경우 등 정상적인 사용 시나리오에서도 부모가 `explorer.exe`가 아닌 경우가 매우 많다. 그래서 실전 상용 소프트웨어에서는 이 검사를 단독으로 쓰기보다 다른 안티디버깅 기법과 조합해서 보조적으로만 사용하는 경우가 많다.

### PID 재사용 문제
부모 프로세스가 이미 종료된 뒤 그 PID가 다른(전혀 무관한) 프로세스에 재사용될 수 있다는 점도 이 검사를 신뢰도 낮게 만드는 요인이다. 정교한 구현은 PID뿐 아니라 프로세스 생성 시각까지 비교해서 이런 오판을 줄이려 하지만, CTF/실전 리버싱 문제 수준에서는 대개 단순 PID+이름 비교 정도로 구현되어 있다.

### 조부모(grandparent)까지 검사하는 변형
일부 구현은 부모 하나만 보는 것으로 만족하지 않고, 부모의 부모(조부모)까지 거슬러 올라가며 실행 체인 전체를 검사한다. 예를 들어 사용자가 `cmd.exe`를 먼저 열고 그 안에서 탐색기 아이콘을 더블클릭하는 대신 파일 경로를 직접 입력해 실행하면 부모는 `cmd.exe`가 되고, `cmd.exe`의 부모는 다시 `explorer.exe`인 경우가 많다. 조부모까지 확인하는 검사는 이런 "간접 실행" 경로까지 걸러내려는 의도이며, 반대로 리버서 입장에서는 이런 조부모 검사 로직을 놓치면 "분명 부모를 explorer.exe로 위장했는데도 왜 걸리지?"라는 혼란을 겪을 수 있다.

### 형제 프로세스 개수 검사와의 결합
일부 프로그램은 부모 이름 검사와 더불어, 같은 부모를 가진 다른 자식 프로세스(형제 프로세스) 개수까지 함께 확인한다. 정상적인 탐색기 실행 환경에서는 `explorer.exe`의 자식이 매우 많은 반면(트레이 아이콘, 백그라운드 서비스 등), x64dbg 하나만 띄워놓고 그 안에서 실행한 환경은 부모의 자식 수가 비정상적으로 적을 수 있다는 통계적 특징을 이용하는 것인데, 실무에서는 오탐 위험이 커서 흔히 쓰이지는 않는다.

## 화면/코드에서 보이는 징후
- 코드나 문자열 창에 `"explorer.exe"`가 하드코딩되어 있고, 대소문자 비교(`_stricmp`, `lstrcmpiA` 등) 함수와 함께 쓰임.
- `CreateToolhelp32Snapshot`, `Process32First`, `Process32Next`가 Import Table에 함께 있음.
- `ntdll.dll`에서 `NtQueryInformationProcess`를 직접 `GetProcAddress`로 얻어 호출하는 패턴(정적 Import에 안 보이고 문자열로만 `"NtQueryInformationProcess"`가 보일 수 있음).

## 가장 먼저 할 것
비교 대상 문자열이 정확히 `"explorer.exe"`인지, 대소문자를 구분하는지, 전체 경로(`C:\Windows\explorer.exe`)까지 비교하는지 파일 이름만 비교하는지부터 확인한다. 이 비교 방식에 따라 x64dbg에서 프로세스 이름을 위장하는 우회 난이도가 달라진다.

## 단계별 절차
**1) 부모 PID 획득 방식 확인**

IDA에서 `CreateToolhelp32Snapshot` 계열인지 `NtQueryInformationProcess` 계열인지 구분한다.

**2) 비교 로직 확인**

부모 이름과 `"explorer.exe"`를 비교하는 함수(문자열 비교 함수 이름과 대소문자 구분 여부)를 확인하고, 일치/불일치에 따른 분기 방향을 반드시 실제로 따라가서 확인한다.

**3) x64dbg에서 재현**

x64dbg로 프로그램을 직접 열어(`File → Open`) 실행하면 부모가 `x64dbg.exe`가 되므로 검사에 걸리는지 관찰한다. `Attach`로 붙였을 때와 `Open`으로 직접 실행했을 때 부모가 다를 수 있다는 점도 함께 비교해본다.

**4) 우회 방법 이해**

가장 흔한 우회는 `explorer.exe`에서 x64dbg를 자식으로 실행한 뒤(예: 탐색기에서 x64dbg 바로가기 실행), 그 x64dbg가 다시 대상 프로그램을 `explorer.exe`의 손자 프로세스로 만들어버리는 방법이 아니라, **대상 프로그램을 먼저 `explorer.exe`가 부모가 되도록 정상 실행시킨 뒤 x64dbg로 나중에 Attach**하는 방법이다(단, 이 경우 초기 몇 명령어는 이미 지나간 상태이므로 타이밍에 주의). 더 근본적인 방법은 검사 로직 자체(비교 후 분기)를 패치하거나, `CreateToolhelp32Snapshot`/`NtQueryInformationProcess` 호출을 후킹해 항상 `explorer.exe`의 PID를 반환하도록 만드는 것이다.

## 명령어/단축키
- Sysinternals Process Explorer: 프로세스 트리에서 부모-자식 관계를 시각적으로 확인
- x64dbg: `File → Open`(직접 실행, 부모가 x64dbg가 됨) vs `File → Attach`(이미 실행된 프로세스에 붙음, 부모는 원래 실행한 프로그램 그대로)
- IDA: `Shift+F12`(Strings 창)에서 `"explorer.exe"` 검색 후 xref로 사용처 추적

## 출력 해석
- 부모 PID로 찾은 프로세스 이름이 `explorer.exe`가 아니면 검사 로직상 "의심스러운 실행 환경"으로 분류된다.
- `InheritedFromUniqueProcessId`(NtQueryInformationProcess 방식)가 0이거나 이미 종료된 PID를 가리킨다면, 부모가 이미 사라졌거나 특수한 방식으로 생성된 프로세스라는 신호일 수 있다.

## 흔한 실수
- 이 검사 하나만 우회하면 안전하다고 생각하는 것 — 오탐이 흔한 기법이라 다른 강력한 기법(REV-0533 NtQueryInformationProcess, REV-0541 Self-Debugging)과 함께 조합되는 경우가 많다.
- x64dbg를 explorer.exe에서 직접 실행하지 않고 다른 방식(스크립트, 배치파일)으로 띄운 뒤 대상 프로그램을 열어서 "역시 부모가 explorer.exe가 아니네"라고 오판하는 것 — x64dbg 자체의 실행 경로도 함께 신경 써야 정확한 재현이 된다.
- 부모 프로세스 이름 비교가 대소문자를 구분하는지 확인하지 않고 우회 방법(프로세스 이름 위장)을 시도하는 것.
- PID 재사용 가능성을 고려하지 않고 "부모 PID가 있으니 확실한 부모다"라고 단정하는 것.

## 막혔을 때 다음 체크
- 셀프 디버깅과 결합되는 경우가 궁금하다면 → REV-0541 자기 자신 디버깅(Self-Debugging) 안티디버깅 기법
- `NtQueryInformationProcess`의 다른 정보 클래스(디버그 포트 등)가 궁금하다면 → REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- 윈도우 클래스명 기반의 또 다른 환경 확인 기법이 궁금하다면 → REV-0543 윈도우 클래스명으로 디버거 탐지하는 기법(x64dbg 창 이름)
- 여러 안티디버깅 기법을 한눈에 정리한 표가 필��하다면 → REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 미니 예제
```c
#include <windows.h>
#include <tlhelp32.h>

BOOL IsParentExplorer(void) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32 pe = { sizeof(pe) };
    DWORD myPid = GetCurrentProcessId();
    DWORD parentPid = 0;

    if (Process32First(snap, &pe)) {
        do {
            if (pe.th32ProcessID == myPid) {
                parentPid = pe.th32ParentProcessID;
                break;
            }
        } while (Process32Next(snap, &pe));
    }

    BOOL result = FALSE;
    if (Process32First(snap, &pe)) {
        do {
            if (pe.th32ProcessID == parentPid) {
                result = (lstrcmpiA(pe.szExeFile, "explorer.exe") == 0);
                break;
            }
        } while (Process32Next(snap, &pe));
    }
    CloseHandle(snap);
    return result;
}

int main(void) {
    if (!IsParentExplorer()) {
        ExitProcess(1);
    }
    printf("Enter flag: ");
    return 0;
}
```
x64dbg로 직접 실행하면 부모가 `x64dbg.exe`가 되어 `IsParentExplorer()`가 `FALSE`를 반환하고, 탐색기에서 더블클릭하면 부모가 `explorer.exe`라 `TRUE`가 반환되는 차이를 관찰할 수 있다.

## 관련 글
- REV-0541 — 자기 자신 디버깅(Self-Debugging) 안티디버깅 기법
- REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- REV-0543 — 윈도우 클래스명으로 디버거 탐지하는 기법(x64dbg 창 이름)
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 출처/검증
- `CreateToolhelp32Snapshot`, `Process32First`/`Process32Next`, `PROCESSENTRY32`(`th32ProcessID`, `th32ParentProcessID`, `szExeFile`)는 Microsoft 공식 문서(learn.microsoft.com, "Tool Help Library") 기준.
- `NtQueryInformationProcess`와 `PROCESS_BASIC_INFORMATION.InheritedFromUniqueProcessId`는 Microsoft가 부분적으로 문서화한 ntdll 네이티브 API(learn.microsoft.com "NtQueryInformationProcess function") 및 ReactOS/Process Hacker 등에서 공개된 구조체 정의를 기준으로 서술했다.
- 부모 프로세스 이름 비교 기반 안티디버깅 패턴과 그 오탐 한계는 다수의 공개 안티디버깅 리서치 자료에서 공통적으로 지적하는 내용이다(2026-09-08 확인).
