---
id: REV-0543
title: "윈도우 클래스명으로 디버거 탐지하는 기법(x64dbg 창 이름)"
slug: "rev-0543-window-class-name-debugger-detection"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["FindWindow", "FindWindowEx", "EnumWindows", "GetClassName", "Qt5QWindowIcon", "OLLYDBG 클래스", "윈도우 클래스명 탐지"]
aliases: ["창 클래스 탐지", "FindWindow 안티디버깅", "디버거 창 이름 검색", "GUI 기반 디버거 탐지", "x64dbg 윈도우 탐지"]
symptom_keywords: ["FindWindowA를 여러 클래스 이름으로 반복 호출한다", "OLLYDBG 문자열이 코드에 있다", "Qt5QWindowIcon 문자열이 코드에 있다", "EnumWindows로 모든 창을 순회하며 제목을 검사한다", "x64dbg 창을 최소화하면 프로그램이 다르게 동작한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x64dbg, OllyDbg, IDA 같은 디버거들은 결국 화면에 자기 이름을 담은 GUI 창을 띄우고 있기 때문에, `FindWindow`/`EnumWindows` 같은 일반적인 GUI API로 현재 데스크톱에 떠 있는 창들의 클래스명이나 제목을 훑어서 알려진 디버거 창이 있는지 확인하는 것만으로도 디버거 존재를 탐지할 수 있다 — 코드 내부(PEB, API 반환값 등)를 보는 다른 기법들과 달리 이 기법은 순전히 "화면에 뭐가 떠 있는가"만 본다는 점이 특징이다.

## 언제 검색해야 하나
- 코드에서 `FindWindowA`/`FindWindowExA`/`EnumWindows`를 반복적으로 호출하며 여러 문자열(`"OLLYDBG"`, `"Qt5QWindowIcon"`, `"WinDbgFrameClass"` 등)과 비교하는 패턴을 발견했을 때
- 문자열 창에 알려진 디버거 이름이나 클래스명이 여러 개 나열되어 있는 배열/테이블을 발견했을 때
- x64dbg 창을 최소화하거나 다른 이름으로 바꿔서 실행했을 때만 프로그램 동작이 달라지는 것을 관찰했을 때
- "GUI 기반 안티디버깅"이라는 표현이 CTF 문제 설명에 등장할 때

## 핵심 개념

### 왜 GUI 창으로 디버거를 알 수 있나
Windows에서 모든 창(윈도우)은 등록된 "윈도우 클래스"에 속하고, `GetClassName`으로 그 클래스 이름 문자열을 얻을 수 있다. 유명한 디버거들의 메인 창 클래스명은 공개적으로 잘 알려져 있다.
- OllyDbg: 클래스명 `"OLLYDBG"`
- WinDbg: 클래스명 `"WinDbgFrameClass"`
- Immunity Debugger: 클래스명 `"ID"`
- x64dbg/x32dbg/IDA(모두 Qt 프레임워크 기반): 여러 Qt 기반 도구가 공유하는 제네릭 클래스명 `"Qt5QWindowIcon"`이 뜬다. Qt 프레임워크는 자체 렌더링 방식 때문에 세부 위젯들이 표준 Win32 창 클래스로 등록되지 않고, 최상위 창만 이 제네릭 클래스로 보이는 경우가 많다.

정적으로 알려진 이 클래스명들을 `FindWindowA(className, NULL)`로 하나씩 조회해서, 하나라도 `NULL`이 아닌 핸들이 리턴되면 "해당 디버거가 실행 중"이라고 판단한다.

### 대표 코드 패턴
```c
const char* debuggerClasses[] = {
    "OLLYDBG", "WinDbgFrameClass", "ID",
    "Qt5QWindowIcon", "GBDYLLO", "pediy06"
};
for (int i = 0; i < ARRAYSIZE(debuggerClasses); i++) {
    if (FindWindowA(debuggerClasses[i], NULL) != NULL) {
        // 디버거 창 발견
    }
}
```

### Qt 기반 클래스명의 모호함과 제목 병행 검사
`"Qt5QWindowIcon"`은 x64dbg뿐 아니라 IDA, Detect It Easy 등 Qt로 만들어진 다른 여러 도구가 공유하는 클래스명이라, 이 클래스명 하나만으로는 "어떤 도구인지" 특정할 수 없다. 그래서 실전 구현은 클래스명 검사와 함께 **창 제목(window title)**을 `GetWindowText`로 읽어서 `"x64dbg"`, `"x32dbg"`, `".idb"`, `"_i64"` 같은 특정 문자열이 포함되는지 추가로 검사하는 경우가 많다. `EnumWindows`로 현재 떠 있는 모든 최상위 창을 순회하며 각 창의 제목/클래스를 검사하는 방식이 `FindWindow` 한 번보다 더 폭넓게(정확한 이름을 모르더라도) 탐지할 수 있어 함께 쓰인다.

### 이 기법의 한계
- 디버거 창을 최소화해도 창 자체는 여전히 존재하므로(`FindWindow`는 보이지 않는 창도 찾을 수 있음, `IsWindowVisible`을 추가로 확인하지 않는 한) 탐지된다.
- 반대로 디버거의 창 클래스나 제목을 바꿔치기하면(예: 소스 코드를 고쳐 재빌드하거나, 실행 중 `SetWindowText`/클래스 재등록으로 위장) 이 검사를 쉽게 피할 수 있어, 다른 저수준 기법(PEB, API 기반)보다 근본적으로 약한 방어로 취급된다.
- 여러 창을 이름으로 하드코딩해야 하므로 새 버전의 디버거가 클래스명을 바꾸면 탐지가 실패할 수 있다.

### EnumWindows 기반 전수 조사와의 차이
`FindWindowA`는 정확한 클래스명/제목을 알아야만 찾을 수 있는 반면, `EnumWindows`는 현재 데스크톱의 모든 최상위 창을 하나씩 콜백으로 넘겨주기 때문에 정확한 이름을 몰라도 "제목에 특정 부분 문자열이 포함되는가"(`strstr` 등)처럼 더 느슨한 매칭이 가능하다. 예를 들어 x64dbg의 창 제목은 로드된 파일 이름에 따라 매번 달라지지만(`파일명.exe - PID: 1234 - x64dbg`), 이 제목 안에 항상 `"x64dbg"`라는 부분 문자열이 포함된다는 점을 이용하면 `EnumWindows` + `strstr` 조합으로 훨씬 안정적으로 탐지할 수 있다. 이런 이유로 실전 구현에서는 `FindWindow`보다 `EnumWindows` 기반 전수 조사가 더 흔히 쓰인다.

### 프로세스 소유권까지 확인하는 심화 버전
단순히 클래스명/제목만 보는 데서 그치지 않고, `GetWindowThreadProcessId`로 그 창을 소유한 프로세스의 PID를 얻은 뒤, 그 PID의 실행 파일 이름을 다시 확인하는 이중 검사도 가능하다. 이렇게 하면 단순히 창 제목만 바꿔치기하는 우회로는 막을 수 없고, 실제로 그 창을 띄운 프로세스의 실행 파일 이름까지 위장해야 하므로 탐지 신뢰도가 한 단계 높아진다.

## 화면/코드에서 보이는 징후
- Import Table에 `FindWindowA`/`FindWindowExA`/`EnumWindows`/`GetWindowTextA`/`GetClassNameA`가 함께 있음.
- 문자열 창에 `"OLLYDBG"`, `"WinDbgFrameClass"`, `"Qt5QWindowIcon"`, `"x64dbg"`, `"x32dbg"` 같은 값들이 배열 형태로 나열됨.
- 여러 클래스명을 순회하며 매번 같은 함수(`FindWindowA`)를 반복 호출하는 루프.
- `EnumWindows`에 전달되는 콜백 함수 안에서 `GetClassName`/`GetWindowText` 결과를 `strstr`/`lstrcmpi` 등으로 비교.

## 가장 먼저 할 것
비교 대상 문자열 목록부터 전부 나열한다. IDA의 Strings 창(`Shift+F12`)에서 `"OLLYDBG"`, `"Qt5"`, `"WinDbg"`, `"x64dbg"`, `"x32dbg"`, `"IDA"` 등을 검색해 이 프로그램이 정확히 어떤 도구들을 노리고 있는지 목록을 확보하면 분석과 우회 모두 훨씬 수월해진다.

## 단계별 절차
**1) 비교 문자열 목록 확보**

Strings 창과 IDA의 데이터 세그먼트에서 문자열 배열을 찾아 전체 목록을 정리한다.

**2) 호출 패턴 확인**

`FindWindowA` 단독 호출인지, `EnumWindows` 콜백 기반인지 구분한다. 콜백 기반이면 콜백 함수 안의 비교 로직까지 따라가야 한다.

**3) x64dbg에서 실제로 재현**

x64dbg로 대상 프로그램을 실행하며 이 검사에 걸리는지 관찰한다. 창을 최소화해도 여전히 걸리는지 실험해본다.

**4) 우회 방법 이해**

가장 간단한 우회는 검사 결과 분기(`FindWindowA` 반환값이 `NULL`이 아닐 때의 조건 분기)를 패치하는 것이다. 더 일반적인 방법은 x64dbg의 창 제목을 변경하거나(설정에서 변경 가능한 빌드/포크도 있음), ScyllaHide 플러그인으로 `FindWindowA`/`EnumWindows` 자체를 후킹해 항상 "못 찾음" 결과를 반환하도록 만드는 것이다.

## 명령어/단축키
- IDA: `Shift+F12`(Strings 창)에서 디버거 이름 검색
- x64dbg: `Alt+B`(브레이크포인트 창)에서 `FindWindowA`에 브레이크포인트를 걸고 어떤 인자로 호출되는지 확인
- x64dbg: `bp FindWindowA` 후 `run`, 인자 레지스터(`RCX` x64에서 클래스명 포인터) 확인

## 출력 해석
- `FindWindowA`가 `NULL`이 아닌 핸들을 반환하면 해당 클래스/제목을 가진 창이 실제로 열려 있다는 뜻이다. 이 핸들 값을 `GetWindowText`로 다시 조회하면 정확히 어떤 창이 걸렸는지 확인할 수 있다.
- `EnumWindows` 콜백이 특정 창에서 `TRUE`(또는 `FALSE`, 구현에 따라 다름)를 반환하고 순회를 멈춘다면, 그 시점의 창이 탐지된 대상이다.

## 흔한 실수
- 디버거 창을 최소화하면 이 검사를 피할 수 있다고 오해하는 것 — `FindWindow`는 기본적으로 숨겨진/최소화된 창도 찾아낸다.
- `Qt5QWindowIcon` 클래스명 하나만 보고 "이건 x64dbg 전용 탐지"라고 단정하는 것 — IDA, DIE 등 다른 Qt 기반 도구도 함께 걸릴 수 있다.
- 이 기법이 강력한 방어라고 과신하는 것 — 창 이름/클래스는 비교적 쉽게 위장 가능해서 실전에서는 보조적인 검사로만 쓰이는 경우가 많다.
- `FindWindow`의 두 인자(클래스명, 창 제목) 중 어느 쪽이 `NULL`이고 어느 쪽이 실제 비교 대상인지 헷갈리는 것 — 첫 인자가 클래스명, 두 번째가 창 제목이며 둘 다 지정하면 AND 조건으로 동작한다.

## 막혔을 때 다음 체크
- 부모 프로세스 이름 기반의 또 다른 "환경" 확인 기법이 궁금하다면 → REV-0542 부모 프로세스 확인 안티디버깅(explorer.exe 체크)
- 더 저수준의 API 기반 검사가 궁금하다면 → REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- ScyllaHide 같은 플러그인으로 이런 검사들을 자동 우회하는 개념이 궁금하다면 → REV-0531 — IsDebuggerPresent 우회 실습 개념과 한계
- 여러 안티디버깅 기법을 한눈에 정리한 표가 필요하다면 → REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 미니 예제
```c
#include <windows.h>

const char* debuggerClasses[] = {
    "OLLYDBG", "WinDbgFrameClass", "ID", "Qt5QWindowIcon"
};

BOOL DetectDebuggerWindow(void) {
    for (int i = 0; i < 4; i++) {
        if (FindWindowA(debuggerClasses[i], NULL) != NULL) {
            return TRUE;
        }
    }
    return FALSE;
}

int main(void) {
    if (DetectDebuggerWindow()) {
        ExitProcess(1);
    }
    printf("Enter flag: ");
    return 0;
}
```
x64dbg로 이 프로그램을 열어두면 `Qt5QWindowIcon` 클래스를 가진 창(x64dbg 자체)이 이미 떠 있으므로 `FindWindowA("Qt5QWindowIcon", NULL)`이 유효한 핸들을 반환해 곧바로 종료 분기를 탄다.

## 관련 글
- REV-0542 — 부모 프로세스 확인 안티디버깅(explorer.exe 체크)
- REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- REV-0531 — IsDebuggerPresent 우회 실습 개념과 한계
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 출처/검증
- `FindWindowA`/`FindWindowExA`/`EnumWindows`/`GetClassNameA`/`GetWindowTextA` API 시그니처는 Microsoft 공식 문서(learn.microsoft.com, "Window Features") 기준.
- OllyDbg 클래스명 `"OLLYDBG"`, WinDbg 클래스명 `"WinDbgFrameClass"`, x64dbg/IDA 등 Qt 기반 도구의 제네릭 클래스명 `"Qt5QWindowIcon"` 및 창 제목 병행 검사 관행은 Hexacorn 블로그("Anti- techniques refresh A.D. 2019")와 Check Point "Anti-Debug Tricks — Misc" 항목에서 확인되는 공개 리서치 내용을 기준으로 서술했다(2026-09-08 확인).
- Qt 프레임워크 기반 앱의 창 클래스명이 여러 도구 간에 공유되어 단독으로는 특정 도구를 확정하기 어렵다는 한계도 같은 출처에서 함께 지적된 내용이다.
