---
id: REV-0606
title: "디버거 창 제목/클래스명 때문에 탐지당할 때 대응"
slug: "rev-0606-debugger-window-title-class-detection"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg, "TitanHide", "ScyllaHide"]
keywords: ["FindWindowA", "FindWindowW", "EnumWindows", "GetClassName", "GetWindowText", "OLLYDBG", "WinDbgFrameClass"]
aliases: ["FindWindow 안티디버깅", "창 클래스명 탐지 우회", "디버거 창 숨기기", "OLLYDBG 탐지 우회"]
symptom_keywords: ["디버거로 열면 프로그램이 바로 종료된다", "FindWindowA를 호출하는 것 같다", "OLLYDBG 문자열이 바이너리에 보인다", "x64dbg로 열었더니 동작이 달라진다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
프로그램이 `FindWindowA`/`FindWindowW`나 `EnumWindows`+`GetClassName`/`GetWindowText` 조합으로 "OLLYDBG", "WinDbgFrameClass", "x64dbg" 같은 알려진 디버거 창 클래스명·제목을 찾아서 탐지하는 것이므로, 해당 API 호출 직후의 조건 분기를 IDA로 찾아 패치하거나 TitanHide/ScyllaHide로 디버거 창 자체를 창 목록 열거 결과에서 숨기면 우회된다.

## 언제 검색해야 하나
- 정상 실행하면 잘 되던 프로그램이 x64dbg/OllyDbg/IDA로 열어서 실행하면 조용히 종료되거나 다르게 동작할 때
- Import 목록에 `FindWindowA`, `FindWindowExA`, `EnumWindows`, `GetClassNameA`, `GetWindowTextA` 같은 창 관련 API가 보일 때
- 문자열 창(Strings)에 `OLLYDBG`, `WinDbgFrameClass`, `Zeta Debugger`, `x64dbg`, `ID`(Immunity Debugger) 같은 디버거 이름 문자열이 보일 때

## 핵심 개념
Windows의 모든 GUI 프로그램은 창을 만들 때 "창 클래스"를 등록한다. 디버거도 예외가 아니어서, 예를 들어 OllyDbg는 메인 창의 클래스명이 항상 `"OLLYDBG"`로 고정되어 있다. 악성코드나 상용 프로텍터는 이 사실을 이용해 다음 두 API 중 하나로 실행 중인 디버거를 찾는다.

- `HWND FindWindowA(LPCSTR lpClassName, LPCSTR lpWindowName);` — 클래스명 또는 창 제목이 일치하는 최상위 창의 핸들을 찾는다. 찾으면 0이 아닌 핸들을, 없으면 `NULL`을 반환한다. `hnd = FindWindowA("OLLYDBG", NULL);`처럼 클래스명만 주고 제목은 `NULL`로 넘기는 패턴이 흔하다.
- `BOOL EnumWindows(WNDENUMPROC lpEnumFunc, LPARAM lParam);` — 현재 떠 있는 모든 최상위 창을 순회하며 콜백 함수를 호출한다. 콜백 안에서 `GetClassNameA`/`GetWindowTextA`로 각 창의 클래스명과 제목을 읽어와 블랙리스트 문자열과 비교하는 방식이다.

실제로 자주 검사되는 클래스명 블랙리스트는 대략 다음과 같다.

```text
OLLYDBG, WinDbgFrameClass, Zeta Debugger, Rock Debugger,
ObsidianGUI, Qt5QWindowIcon, ID, ntdll.dll, SunAwtFrame
```

여기서 `Qt5QWindowIcon`은 x64dbg 같은 Qt 기반 프로그램이 공통으로 쓰는 매우 범용적인 클래스명이라, 이 값 하나만으로 판단하면 다른 정상 Qt 프로그램까지 오탐될 수 있다. 그래서 정교한 검사는 클래스명과 함께 창 제목("x64dbg", "x32dbg", "IDA - " 등)까지 같이 대조한다.

## 화면/코드에서 보이는 징후
- IDA의 Imports 탭에 `FindWindowA`/`FindWindowW`/`FindWindowExA`, 또는 `EnumWindows`와 `GetClassNameA`/`GetWindowTextA`가 한 세트로 존재
- Strings 창(`Shift+F12`)에 `OLLYDBG`, `WinDbgFrameClass`, `x64dbg` 같은 문자열이 있고, 그 문자열에 대한 xref를 따라가면 위 API 호출 근처로 연결됨
- `FindWindowA` 호출 직후 반환값(`EAX`/`RAX`)을 `TEST`/`CMP`로 검사한 뒤 `JNZ`(0이 아니면 = 발견됨)로 종료 루틴이나 다른 코드 경로로 분기

## 가장 먼저 할 것
1. IDA에서 Imports 탭을 열어 `FindWindowA`/`FindWindowW`/`EnumWindows`가 있는지 확인한다.
2. 있다면 해당 함수 이름을 더블클릭해서 이동한 뒤 `X`(교차 참조 보기)로 실제로 이 함수를 호출하는 코드 위치를 모두 찾는다.
3. 각 호출 지점 바로 뒤의 조건 분기(`TEST EAX, EAX` / `JNZ`, `CMP EAX, 0` / `JE` 등)를 확인해, "발견 시 어디로 튀는지"를 파악한다.

## 단계별 절차
**1) 정적으로 검사 지점 찾기**
- IDA Imports 탭에서 `FindWindowA`를 찾아 더블클릭 → `X` 키로 xref 목록을 연다.
- 호출 직전에 클래스명 문자열을 스택/레지스터로 넘기는 부분(`push offset aOllydbg` 또는 `lea rcx, aOllydbg`)을 확인하면 어떤 문자열을 찾는지 바로 알 수 있다.

**2) 동적으로 확인하기**
- x64dbg로 대상을 로드하고, `FindWindowA`에 브레이크포인트를 건다(Imports 창에서 우클릭 → "Set Breakpoint" 또는 심볼 검색 후 `F2`).
- 프로그램을 실행(`F9`)해서 브레이크가 걸리면, 인자(x64는 `RCX`가 클래스명 포인터)를 덤프 창에서 문자열로 확인한다.
- `RET`까지 실행(`Ctrl+F9` 또는 함수 끝까지 `F8` 반복)해서 반환값(`EAX`)이 0인지 아닌지 본다. 실제 디버거로 실행 중이므로 대부분 0이 아닌 값(핸들)이 나와서 탐지 로직이 발동하는 것을 직접 확인할 수 있다.

**3) 즉시 우회(1회성 패치)**
- 반환값 검사 직후의 조건 분기 명령어(예: `JNZ`)를 IDA/x64dbg에서 반대 분기(`JMP`로 강제) 또는 `NOP`으로 패치해 탐지 로직이 항상 "디버거 없음" 경로를 타도록 만든다.
- 이 방법은 검사 지점이 하나뿐일 때만 유효하며, 같은 검사가 여러 곳에 흩어져 있으면 매번 반복해야 한다.

**4) 재사용 가능한 우회(창 자체를 숨기기)**
- x64dbg 플러그인인 **ScyllaHide**를 설치하면 `NtUserFindWindowEx`(`FindWindowA/W` 내부에서 사용)와 `NtUserBuildHwndList`(`EnumWindows` 내부에서 사용) 후킹 옵션이 있다. 이 옵션들을 켜면 대상 프로세스 입장에서는 디버거 창이 아예 목록에 나타나지 않아, 검사 지점을 하나하나 패치할 필요가 없다.
- 더 강력하게는 커널 드라이버 방식인 **TitanHide**를 사용한다. 서비스로 드라이버를 등록/시작한 뒤 `TitanHideGUI.exe`를 실행하고, 대상 PID를 입력한 다음 "창 클래스/캡션 숨김" 관련 항목을 체크하고 "Hide"를 누르면 커널 레벨에서 해당 프로세스에 한해 디버거 창을 숨겨준다.

## 명령어/단축키
- IDA: `Shift+F12`(Strings 창), `X`(교차 참조), 더블클릭(정의로 이동)
- x64dbg: Imports 창에서 함수 우클릭 → Set Breakpoint, `F9`(실행), `F8`(스텝 오버), `Ctrl+F9`(함수 반환까지 실행)
- TitanHide: 드라이버 서비스 등록 → `TitanHideGUI.exe` 실행 → PID 입력 → 항목 체크 → Hide
- ScyllaHide: x64dbg 플러그인 메뉴에서 옵션 설정 → 디버거 창 클래스/캡션 숨김 활성화

## 출력 해석
- `FindWindowA` 반환값이 `0x00000000`이면 해당 클래스명/제목의 창을 찾지 못한 것이므로 탐지 로직은 "디버거 없음"으로 판단하고 정상 진행한다.
- 0이 아닌 값(예: `0x000A047C` 같은 핸들)이 나오면 해당 창이 실제로 열려 있다는 뜻이며, 이 값을 기준으로 종료 분기가 타게 된다.

## 흔한 실수
- `Qt5QWindowIcon`처럼 범용적인 클래스명 검사까지 다 무력화하려다가, 정작 진짜 탐지 지점(구체적인 창 제목 비교)을 놓치는 경우가 있다. 반드시 xref로 실제 비교되는 문자열 상수를 같이 확인해야 한다.
- 검사 지점을 패치했다고 안심했다가, 같은 검사가 다른 함수에도 중복으로 들어있어서(특히 상용 프로텍터는 여러 곳에 분산 삽입) 다시 걸리는 경우가 흔하다. 문자열 xref를 끝까지 다 확인해야 한다.
- ScyllaHide/TitanHide의 옵션을 무작정 전부 켜면 디버거 자체의 안정성이 떨어지거나 다른 정상 동작(예: 실제 예외 처리)까지 왜곡될 수 있다. 필요한 항목만 최소로 켜는 것이 좋다.

## 막혔을 때 다음 체크
- 창 검사와 별개로 `IsDebuggerPresent`도 같이 걸리는 것 같다면 → REV-0130을 확인한다.
- `CheckRemoteDebuggerPresent`나 PEB의 `BeingDebugged` 필드 검사가 섞여 있다면 → REV-0131, REV-0132를 확인한다.
- 창 검사는 통과했는데 하드웨어 브레이크포인트가 갑자기 사라진다면 → REV-0607을 확인한다.

## 미니 예제
IDA에서 다음과 같은 의사코드를 확인했다고 하자.

```c
if ( FindWindowA("OLLYDBG", 0) )
{
    ExitProcess(0);
}
```

x64dbg로 `FindWindowA`에 브레이크를 걸고 실행하면, `RCX`에 `"OLLYDBG"` 문자열 포인터가 들어있는 것을 확인할 수 있다(실제 이 프로그램을 OllyDbg로 열지 않았다면 반환값은 0이라 정상 통과한다). x64dbg 자체를 감지하려는 최신 검사라면 클래스명 대신 창 제목에 `"x64dbg"` 또는 `"x32dbg"` 문자열을 비교하는 형태로 바뀌어 있을 수 있으니, Strings 창에서 `"x64dbg"`도 함께 검색해보는 것이 좋다.

## 관련 글
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0131 — CheckRemoteDebuggerPresent 식별
- REV-0132 — PEB BeingDebugged 검사 이해
- REV-0607 — 하드웨어 브레이크포인트가 갑자기 사라질 때

## 출처/검증
- `FindWindow`/`EnumWindows`를 이용한 디버거 창 클래스명 탐지는 al-khaser 등 공개 안티디버깅 예제 프로젝트와 다수의 악성코드 분석 자료에서 반복적으로 확인되는 패턴이다.
- OllyDbg의 창 클래스명이 `"OLLYDBG"`로 고정되어 있다는 사실과 `FindWindow` 기반 탐지 코드 패턴은 공개된 안티디버깅 기법 정리 자료(al-khaser, Checkpoint Evasion Techniques 문서 등) 기준이다.
- ScyllaHide가 `NtUserFindWindowEx`/`NtUserBuildHwndList`를 후킹해 창 열거/검색 결과에서 디버거 창을 숨기는 기능을 제공한다는 점, TitanHide가 커널 드라이버로 유사한 은닉을 제공한다는 점은 ScyllaHide/TitanHide 공식 GitHub 저장소 및 문서(x64dbg/ScyllaHide, mrexodia/TitanHide) 기준이다(2026-09-08 확인).
