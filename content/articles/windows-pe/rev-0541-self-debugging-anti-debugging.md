---
id: REV-0541
title: "자기 자신 디버깅(Self-Debugging) 안티디버깅 기법"
slug: "rev-0541-self-debugging-anti-debugging"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["Self-Debugging", "DebugActiveProcess", "DEBUG_PROCESS", "자식 프로세스 디버깅", "디버그 포트 선점", "anti-attach"]
aliases: ["셀프 디버깅 안티디버깅", "자식 프로세스로 디버깅", "DebugActiveProcess 트릭", "디버그 슬롯 선점 기법", "anti-attach 기법"]
symptom_keywords: ["CreateProcess를 DEBUG_PROCESS 플래그로 호출한다", "DebugActiveProcess를 자기 자신이나 자식에게 호출한다", "프로세스가 두 개 떠서 서로 감시한다", "부모와 자식이 동일한 실행파일이다", "디버거로 붙이려 하면 액세스가 거부된다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows는 프로세스 하나에 디버거를 딱 하나만 붙일 수 있다는 제약이 있는데, 프로그램이 이 제약을 역이용해 실행되자마자 자기 자신의 복사본(또는 자식 프로세스)을 미리 스스로의 디버거로 만들어 "디버거 슬롯"을 선점해버리면, 나중에 사용자가 x64dbg 같은 진짜 디버거를 붙이려 해도 이미 자리가 차 있어 실패하게 된다 — 이것이 셀프 디버깅(self-debugging) 기법의 핵심이다.

## 언제 검색해야 하나
- x64dbg로 프로그램에 `File → Attach`를 시도했는데 액세스 거부나 "이미 디버깅 중"과 유사한 오류가 뜰 때
- 프로그램을 실행하면 프로세스가 두 개(작업 관리자에서 동일한 이름으로 2개) 뜨는 것을 발견했을 때
- 코드에서 `CreateProcess` 호출에 `DEBUG_PROCESS`나 `DEBUG_ONLY_THIS_PROCESS` 플래그가 쓰이거나, `DebugActiveProcess`가 자기 자신의 실행 파일 경로로 호출되는 것을 발견했을 때
- "이 프로그램은 처음부터 attach가 안 된다"는 힌트가 있는 CTF 문제를 만났을 때

## 핵심 개념

### Windows 디버깅 모델의 전제: 프로세스당 디버거 1개
Windows 커널은 프로세스마다 "디버그 포트(디버그 오브젝트)"를 하나만 연결할 수 있도록 설계되어 있다. 즉 어떤 프로세스 P에 이미 디버거 A가 붙어 있는 상태에서, 다른 프로그램(x64dbg 등)이 `DebugActiveProcess(P의 PID)`를 호출해도 이미 자리가 차 있으므로 이 호출은 실패한다. 셀프 디버깅 기법은 이 사실을 이용해서, **악의적인(또는 방어하려는) 프로그램 스스로가 자기 프로세스에 먼저 디버거로 등록**해버리는 방식이다.

### 구현 패턴 1: 자식 프로세스를 디버깅
```c
STARTUPINFO si = { sizeof(si) };
PROCESS_INFORMATION pi;
CreateProcess(NULL, cmdline, NULL, NULL, FALSE,
              DEBUG_PROCESS, NULL, NULL, &si, &pi);
// 이제 부모 프로세스가 pi.dwProcessId(자식)의 디버거가 됨
```
프로그램이 자기 자신의 실행 파일 경로를 다시 `CreateProcess`로 실행하면서 `DEBUG_PROCESS` 플래그를 준다. 이렇게 만들어진 부모-자식 관계에서 **부모가 자식의 디버거**가 되고, 실제 로직(플래그 검증 등)은 자식 프로세스에서 실행된다. 자식 프로세스는 이미 부모가 디버거로 붙어 있으므로, 사용자가 자식 프로세스에 x64dbg로 attach하려고 하면 실패한다.

### 구현 패턴 2: 자기 자신을 디버깅(스레드 이용)
프로세스가 `CREATE_SUSPENDED`로 자기 자신의 새 인스턴스를 띄운 뒤, 새 인스턴스에 대해 `DebugActiveProcess`를 호출해 자신이 디버거가 되고, 그 다음 원래 로직을 새 인스턴스(피디버기)에서 실행하는 변형도 있다. 어느 쪽이든 목적은 같다 — **진짜 로직이 도는 프로세스의 "디버거 자리"를 미리 자기 자신으로 채워버려서 외부 디버거의 접근을 막는 것**이다.

### 부수 효과: 자식 입장에서 IsDebuggerPresent는 항상 TRUE
셀프 디버깅 구조에서 자식(실제 로직 실행 프로세스)은 항상 디버거(부모)가 붙어 있는 상태이므로, 자식 안에서 `IsDebuggerPresent()`를 호출하면 항상 `TRUE`가 나온다. 따라서 이 구조를 쓰는 프로그램은 `IsDebuggerPresent` 검사를 별도로 쓰지 않거나, 부모의 PID/이름이 "신뢰할 수 있는 자기 자신"인지 별도로 확인하는 로직을 추가로 둔다(REV-0542 부모 프로세스 확인과 결합되는 경우가 많다).

### 부모-자식 간 통신
부모(디버거 역할)는 `WaitForDebugEvent`/`ContinueDebugEvent` 루프를 돌며 자식에서 발생하는 디버그 이벤트를 처리해야 하는데, 이 루프 안에서 특정 예외나 브레이크포인트 이벤트를 감시해 "혹시 다른 진짜 디버거가 끼어들려는 시도가 있는지"까지 감시하는 더 정교한 구현도 가능하다.

### 디버그 이벤트 루프가 하는 일
부모 프로세스의 `WaitForDebugEvent` 루프는 단순히 이벤트를 흘려보내는 역할만 하는 게 아니라, 실제로는 자식에서 발생하는 모든 예외(`EXCEPTION_DEBUG_EVENT`), 스레드 생성/종료(`CREATE_THREAD_DEBUG_EVENT`, `EXIT_THREAD_DEBUG_EVENT`), 모듈 로드(`LOAD_DLL_DEBUG_EVENT`)까지 하나하나 통지받는다. 이 구조를 악용하면 자식 프로세스에서 `INT3`(REV-0537의 소프트웨어 브레이크포인트)가 발생했을 때 그 이벤트가 반드시 부모의 이 루프로 먼저 전달되므로, 부모가 이 이벤트를 직접 처리하며 "누가 이 브레이크포인트를 걸었는지" 자체를 감시하는 것도 이론적으로 가능하다. 즉 self-debugging 구조는 단순한 슬롯 선점을 넘어, 부모가 자식의 모든 예외를 1차로 검열하는 감시 레이어로도 쓰일 수 있다.

### 왜 CTF/실전에서 드물게 등장하는가
셀프 디버깅은 구현이 상대적으로 복잡하고(디버그 이벤트 루프를 직접 관리해야 함), 정상적인 프로그램 종료·크래시 처리와 충돌할 위험이 있어 일반적인 상용 소프트웨어보다는 강력한 방어가 필요한 상용 프로텍터나 고난도 CTF 문제에서 주로 등장한다. 그만큼 이 패턴을 발견했다면 해당 바이너리가 비교적 신경 써서 만들어진 방어 로직을 갖추고 있다는 신호로 받아들이고, 다른 안티디버깅 기법들과의 조합 가능성을 염두에 두고 분석 우선순위를 높이는 것이 좋다.

## 화면/코드에서 보이는 징후
- Import Table에 `DebugActiveProcess`, `CreateProcess`(with `DEBUG_PROCESS`/`DEBUG_ONLY_THIS_PROCESS` 플래그), `WaitForDebugEvent`, `ContinueDebugEvent`가 함께 있음.
- `CreateProcess` 호출의 첫 인자(`lpApplicationName`) 또는 커맨드라인이 `GetModuleFileName`으로 얻은 자기 자신의 경로와 같음.
- 작업 관리자에 동일한 이름의 프로세스가 2개(부모/자식) 떠 있음.
- x64dbg로 실행 중인 프로세스에 `Attach`를 시도하면 `Could not attach` 류의 오류가 발생.

## 가장 먼저 할 것
프로세스가 몇 개 뜨는지부터 확인한다. 작업 관리자나 Process Explorer(Sysinternals)에서 동일 이름 프로세스가 2개 이상이면, 부모-자식 관계(PID/PPID)를 확인해 어느 쪽이 디버거 역할이고 어느 쪽이 실제 로직을 실행하는 쪽인지 구분해야 한다.

## 단계별 절차
**1) 프로세스 개수와 관계 확인**

Process Explorer 또는 `tasklist /v`로 부모-자식 관계를 확인한다. Process Explorer는 트리 뷰로 부모-자식이 한눈에 보여서 편하다.

**2) 어느 쪽이 실제 로직을 담당하는지 파악**

IDA에서 이진 파일을 정적으로 열어, `CreateProcess`+`DEBUG_PROCESS` 호출 이후 부모가 하는 일과 자식(재실행된 인스턴스)에서만 실행되는 분기(대개 커맨드라인 인자나 부모-자식 구분용 뮤텍스/이벤트로 나뉨)를 구분한다.

**3) x64dbg로 자식에 먼저 붙기**

`CREATE_SUSPENDED`로 자식이 생성되는 타이밍을 노려서, 자식이 실제 `DebugActiveProcess`로 부모에게 붙잡히기 전에 먼저 x64dbg로 attach를 시도하는 레이스 컨디션을 활용하는 방법이 실전에서 쓰이기도 한다(항상 성공하지는 않음).

**4) 부모 프로세스를 먼저 죽이는 방법**

부모(디버거 역할) 프로세스를 강제 종료하면, Windows는 디버거가 사라진 자식 프로세스를 기본적으로 함께 종료시킨다(`DebugSetProcessKillOnExit` 설정에 따라 다름). 이 동작 때문에 단순히 부모만 죽이는 접근은 대개 실패하며, 오히려 `DebugSetProcessKillOnExit(FALSE)`가 코드에 있는지 확인해서 이 값이 어떻게 설정됐는지부터 봐야 한다.

**5) 우회의 현실적인 방법**

가장 실전적인 우회는 이 셀프 디버깅 구조 자체를 만드는 초기 `CreateProcess`/`DebugActiveProcess` 호출을 패치해서 애초에 셀프 디버깅 구조가 성립하지 않게 만들거나, x64dbg로 부모 프로세스 자체를 처음부터 실행(`Attach`가 아니라 `File → Open`으로 직접 실행)해서 부모의 디버그 이벤트 루프 위에서 함께 분석하는 것이다.

## 명령어/단축키
- Sysinternals Process Explorer: 트리 뷰로 부모-자식 프로세스 관계 확인
- `tasklist /v`(cmd): 실행 중인 프로세스와 세션 정보 확인
- x64dbg: `File → Open`으로 실행 파일을 처음부터 직접 열어 디버깅 시작(Attach 대신)

## 출력 해석
- x64dbg로 Attach 시도 시 뜨는 오류가 "액세스가 거부되었습니다" 계열이면, 이미 다른 디버거(부모 프로세스)가 붙어 있다는 강한 신호다.
- Process Explorer에서 부모 프로세스의 핸들 목록에 `DebugObject`(디버그 오브젝트) 타입의 핸들이 보이면, 이 프로세스가 실제로 다른 프로세스의 디버거 역할을 하고 있다는 증거다.

## 흔한 실수
- 부모 프로세스만 보고 "이건 그냥 정상적인 재실행 로직"이라고 오판하는 것 — `DEBUG_PROCESS` 플래그 유무를 반드시 확인해야 한다.
- 부모를 강제 종료하면 자식이 그대로 남아서 분석할 수 있을 거라 가정하는 것 — 기본 설정에서는 부모가 죽으면 자식도 함께 종료된다.
- `IsDebuggerPresent`가 자식에서 항상 `TRUE`로 나오는 것을 보고 "이 프로그램은 그냥 디버거 탐지가 안 되는 구조"라고 착각하는 것 — 실제로는 자식이 부모에게 디버깅당하는 게 정상 상태이므로 별도의 "신뢰 확인" 로직이 있는지 찾아야 한다.
- 부모-자식 통신에 쓰이는 뮤텍스/이벤트/파이프 이름을 무시하는 것 — 이 이름들은 IDA의 문자열 창에서 쉽게 찾을 수 있고, 두 프로세스가 서로를 구분하는 핵심 단서가 되는 경우가 많다.

## 막혔을 때 다음 체크
- 부모 프로세스 이름 자체를 확인하는 별도 기법이 궁금하다면 → REV-0542 부모 프로세스 확인 안티디버깅(explorer.exe 체크)
- `NtSetInformationThread`로 디버거로부터 스레드를 숨기는 기법과 결합된 경우가 궁금하다면 → REV-0534 — NtSetInformationThread ThreadHideFromDebugger 기법
- 이 구조가 `NtQueryInformationProcess`의 `ProcessDebugPort` 확인과 함께 쓰이는지 궁금하다면 → REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- 여러 안티디버깅 기법을 한눈에 정리한 표가 필요하다면 → REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 미니 예제
```c
#include <windows.h>

int main(int argc, char** argv) {
    if (argc < 2) {
        // 부모: 자식을 디버깅 모드로 재실행
        char path[MAX_PATH];
        GetModuleFileName(NULL, path, MAX_PATH);
        char cmd[MAX_PATH + 16];
        wsprintfA(cmd, "\"%s\" child", path);

        STARTUPINFOA si = { sizeof(si) };
        PROCESS_INFORMATION pi;
        CreateProcessA(NULL, cmd, NULL, NULL, FALSE,
                        DEBUG_PROCESS, NULL, NULL, &si, &pi);

        DEBUG_EVENT dbgEvent;
        while (WaitForDebugEvent(&dbgEvent, INFINITE)) {
            ContinueDebugEvent(dbgEvent.dwProcessId, dbgEvent.dwThreadId, DBG_CONTINUE);
        }
    } else {
        // 자식: 실제 로직 실행 (이미 부모가 디버거로 붙어 있음)
        printf("Enter flag: ");
    }
    return 0;
}
```
부모는 `WaitForDebugEvent`/`ContinueDebugEvent` 루프로 자식의 디버거 슬롯을 계속 점유하고, 이 상태에서 사용자가 자식 프로세스에 x64dbg로 Attach를 시도하면 실패한다.

## 관련 글
- REV-0542 — 부모 프로세스 확인 안티디버깅(explorer.exe 체크)
- REV-0534 — NtSetInformationThread ThreadHideFromDebugger 기법
- REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 출처/검증
- `CreateProcess`의 `DEBUG_PROCESS`/`DEBUG_ONLY_THIS_PROCESS` 플래그, `DebugActiveProcess`, `WaitForDebugEvent`, `ContinueDebugEvent`, `DebugSetProcessKillOnExit` API는 Microsoft 공식 문서(learn.microsoft.com, "Debugging Functions") 기준.
- "프로세스당 디버거는 하나만 붙을 수 있다"는 제약과 이를 이용한 self-debugging/anti-attach 패턴은 다수의 공개 안티디버깅 리서치(예: GitHub `Anti-Debug` 계열 저장소, 상용 프로텍터 분석 리포트)에서 공통적으로 설명되는 기법을 정리한 것이다(2026-09-08 확인).
