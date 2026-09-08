---
id: REV-0561
title: "서비스(Windows Service) 실행 파일 분석 기초"
slug: "rev-0561-windows-service-exe"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg, sc.exe, "Process Explorer"]
keywords: ["Windows Service", "StartServiceCtrlDispatcher", "ServiceMain", "SERVICE_TABLE_ENTRY", "RegisterServiceCtrlHandlerEx", "SCM"]
aliases: ["윈도우 서비스 분석", "서비스 exe 리버싱", "servicemain 찾기", "svchost 서비스 dll"]
symptom_keywords: ["exe를 그냥 실행했더니 바로 종료됨", "서비스로만 실행되는 프로그램", "sc.exe start 후 분석하고 싶음", "svchost.exe 안에서 실행되는 dll 서비스"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows 서비스 실행 파일은 콘솔에서 그냥 더블클릭해서 실행하면 곧바로 종료돼 버리는 것이 정상이며, 실제 로직은 SCM(Service Control Manager)이 `StartServiceCtrlDispatcher`를 통해 호출해주는 `ServiceMain` 함수 안에 있으므로, 이 진입 구조(`SERVICE_TABLE_ENTRY` 배열, `RegisterServiceCtrlHandlerEx`)를 이해하고 IDA에서 이 함수들을 기준으로 xref를 따라가는 것이 분석의 출발점이다.

## 언제 검색해야 하나
- 실행 파일을 더블클릭했는데 콘솔 창이 잠깐 떴다가 즉시 사라지고, 아무 동작도 안 하는 것처럼 보일 때
- Import Table에서 `advapi32.dll`의 `StartServiceCtrlDispatcherW`, `RegisterServiceCtrlHandlerExW`, `SetServiceStatus` 같은 함수들이 보일 때
- `services.msc`나 `sc.exe query`에 특정 서비스 이름이 등록돼 있는 실행 파일을 분석해야 할 때
- `svchost.exe` 프로세스 안에서 실행되는 DLL 형태의 서비스를 어떻게 찾아 분석할지 궁금할 때
- 서비스로 동작하는 악성코드/드로퍼를 디버거로 붙여서 분석하고 싶은데 방법을 모를 때

## 핵심 개념

### 서비스 프로세스의 진입 구조
일반 콘솔/GUI 프로그램의 `main`/`WinMain`과 달리, 서비스 실행 파일의 실제 진입점(REV-0121에서 다룬 `WinMain`)은 보통 다음과 같은 아주 짧은 코드로 이루어져 있다.

```c
SERVICE_TABLE_ENTRYW ServiceTable[] = {
    { L"MyServiceName", (LPSERVICE_MAIN_FUNCTIONW)ServiceMain },
    { NULL, NULL }   // 배열 끝 표시
};

int wmain(int argc, wchar_t* argv[]) {
    StartServiceCtrlDispatcherW(ServiceTable);
    return 0;
}
```

`StartServiceCtrlDispatcherW`는 이 함수가 호출된 스레드를 SCM과 통신하는 디스패처 루프로 바꿔버린다. 이 호출은 **SCM이 실제로 이 프로세스를 서비스로 시작시킨 경우에만 정상적으로 동작**하며, 그냥 콘솔에서 더블클릭해서 실행하면 SCM과 연결할 방법이 없으므로 즉시 실패하고 함수가 리턴한다. 그래서 초보자가 "서비스 exe를 그냥 실행했더니 아무것도 안 하고 꺼진다"고 느끼는 것이 정상 동작이다.

### ServiceMain: 진짜 로직이 시작되는 곳
```c
VOID WINAPI ServiceMain(DWORD argc, LPWSTR* argv) {
    g_StatusHandle = RegisterServiceCtrlHandlerExW(L"MyServiceName", ServiceCtrlHandler, NULL);
    // 상태를 SERVICE_START_PENDING → SERVICE_RUNNING으로 갱신
    SetServiceStatus(g_StatusHandle, &status);
    // 여기서부터 실제 서비스 로직 시작 (별도 워커 스레드를 만드는 경우가 많음)
}
```
`ServiceMain`은 `SERVICE_TABLE_ENTRY` 배열에 함수 포인터로 등록되기 때문에, 정적 분석에서 xref로 바로 찾아지지 않고 이 배열의 데이터를 통해서만 연결되는 경우가 있다. IDA는 대부분 이 배열을 인식해서 함수 이름을 자동으로 붙여주지만, 난독화되거나 포인터가 런타임에 계산되는 경우 수동으로 배열을 찾아야 한다.

### 서비스 제어 핸들러: 정지/일시정지 요청을 받는 콜백
`RegisterServiceCtrlHandlerExW`로 등록한 콜백(`ServiceCtrlHandler`)은 SCM이 `SERVICE_CONTROL_STOP`, `SERVICE_CONTROL_PAUSE` 같은 제어 코드를 보낼 때 호출된다. 이 함수를 찾으면 "이 서비스가 정지 요청을 받았을 때 무엇을 정리하는가"(예: 로그 파일 flush, 네트워크 연결 종료, 특정 안티포렌식 동작)를 파악할 수 있다.

### EXE 서비스 vs DLL 서비스(svchost 호스팅)
서비스는 두 가지 방식으로 존재할 수 있다.
- **독립 EXE 서비스**: 위에서 설명한 구조 그대로, 해당 EXE 프로세스 자체가 서비스로 실행된다.
- **공유 프로세스(svchost) DLL 서비스**: 실제 코드는 DLL에 있고, `svchost.exe`가 이 DLL을 로드해서 서비스를 대신 호스팅한다. 레지스트리의 `HKLM\SYSTEM\CurrentControlSet\Services\서비스이름\Parameters\ServiceDll` 값이 실제 DLL 경로를 가리킨다. 이 경우 DLL은 `ServiceMain`이 아니라 `svchost`가 기대하는 특정 export(구현 방식에 따라 다르지만 흔히 `ServiceMain`류 이름의 export 또는 COM 기반 등록)를 제공한다.

## 화면/코드에서 보이는 징후
- Import Table에 `advapi32.dll!StartServiceCtrlDispatcherW`(또는 A 버전), `RegisterServiceCtrlHandlerExW`, `SetServiceStatus`가 함께 보임
- 실제 진입점(WinMain) 코드가 매우 짧고, `SERVICE_TABLE_ENTRY` 배열처럼 보이는 데이터(문자열 포인터 + 함수 포인터 쌍, NULL로 끝나는 배열)가 `.rdata`에 존재함
- `sc.exe query 서비스이름` 또는 `services.msc`에서 해당 실행 파일 경로가 등록된 서비스로 나타남
- Process Explorer로 `svchost.exe`를 열었을 때 "Services" 탭에 여러 서비스 이름이 나열되고, 그중 하나를 선택하면 대응하는 DLL 경로가 표시됨

## 가장 먼저 할 것
파일을 그냥 실행해서 동작을 보려 하지 말고, 먼저 IDA로 열어 `StartServiceCtrlDispatcherW`를 xref로 찾는다. 이 함수를 호출하는 지점 바로 위/근처에서 `SERVICE_TABLE_ENTRY` 배열을 찾으면 그 배열의 두 번째 필드가 바로 `ServiceMain`이다. 그 함수부터 분석을 시작하면 된다. 실제로 동작을 관찰하고 싶다면 `sc.exe create`로 임시 서비스를 등록하고 `sc.exe start`로 시작한 뒤, x64dbg를 프로세스에 Attach(REV-0127 참고)하는 방식이 안전하다.

## 단계별 절차

**1) StartServiceCtrlDispatcher 호출 지점 찾기**
IDA의 Imports 창에서 `StartServiceCtrlDispatcherW`(또는 `A`)를 찾아 xref(Ctrl+X 또는 우클릭 → Jump to xref)로 호출부로 이동한다.

**2) SERVICE_TABLE_ENTRY 배열 식별**
호출 직전에 스택/레지스터에 로드되는 배열의 주소를 따라가서, `{ 문자열 포인터, 함수 포인터 }` 쌍이 NULL 항목으로 끝나는 구조를 확인한다. 각 함수 포인터가 `ServiceMain` 역할을 하는 함수다.

**3) ServiceMain부터 분석**
찾은 함수에서 `RegisterServiceCtrlHandlerExW` 호출, `SetServiceStatus` 호출, 그리고 실제 워커 스레드 생성(`CreateThread` 등)을 순서대로 확인한다.

**4) 제어 핸들러 콜백 확인**
`RegisterServiceCtrlHandlerExW`의 두 번째 인자로 넘어가는 콜백 함수를 찾아, 정지/일시정지 요청 처리 로직을 분석한다.

**5) 동적 분석이 필요하면 서비스로 등록해서 실행**
```text
sc.exe create TestSvc binPath= "C:\path\sample.exe" type= own start= demand
sc.exe start TestSvc
```
서비스가 시작된 후 x64dbg → File → Attach로 해당 프로세스에 붙는다.

**6) DLL 서비스라면 svchost 호스팅 확인**
레지스트리 `HKLM\SYSTEM\CurrentControlSet\Services\서비스이름\Parameters\ServiceDll`을 확인해 실제 DLL 경로를 찾고, 그 DLL을 별도로 IDA에 로드해서 분석한다.

## 명령어/단축키
```text
sc.exe query 서비스이름          서비스 상태 확인
sc.exe qc 서비스이름             서비스 설정(실행 파일 경로 등) 확인
sc.exe create / start / stop / delete   테스트용 서비스 등록/제어/삭제
services.msc                     GUI 서비스 관리 콘솔
IDA: Imports 창에서 StartServiceCtrlDispatcherW 검색 → xref로 호출부 이동
x64dbg: File → Attach 로 이미 실행 중인 서비스 프로세스에 붙기
```

## 출력 해석
- `sc.exe qc`의 `BINARY_PATH_NAME`이 특정 EXE 경로를 직접 가리키면 독립 EXE 서비스, `%SystemRoot%\System32\svchost.exe -k 그룹이름`처럼 보이면 DLL 기반 공유 프로세스 서비스다
- `SERVICE_TABLE_ENTRY` 배열의 문자열 필드가 서비스 이름(레지스트리에 등록된 이름과 다를 수 있음에 주의)과 일치하는지 확인해서 분석 대상 함수를 교차 검증한다
- x64dbg로 attach 후 스레드 목록에 워커 스레드가 여러 개 보이면, `ServiceMain`이 별도 스레드를 만들어 실제 작업을 위임하는 구조라는 뜻이다

## 흔한 실수
- 서비스 exe를 그냥 더블클릭해서 실행해보고 "아무 일도 안 일어난다"며 분석을 포기하는 것 — 서비스는 SCM을 통해서만 정상 구동된다.
- `StartServiceCtrlDispatcherW` 호출 자체를 진짜 로직이라고 착각하고 그 안에서 시간을 쓰는 것 — 진짜 로직은 `ServiceMain` 안에 있다.
- DLL 기반 서비스를 EXE만 보고 분석해서 실제 코드를 못 찾는 것 — `ServiceDll` 레지스트리 값을 반드시 확인해야 한다.
- 테스트용 서비스를 만들고 지우지 않아 시스템에 불필요한 서비스 항목이 남는 것 — 분석이 끝나면 `sc.exe delete 서비스이름`으로 정리한다.
- 관리자 권한 없이 `sc.exe create/start`를 시도해서 권한 오류로 실패하는 것을 원인 파악 없이 지나치는 것.

## 막혔을 때 다음 체크
- 진입점/WinMain 구조 자체가 헷갈리면 → [REV-0121 Entry Point와 WinMain 찾기](./rev-0121-entry-point-winmain.md)
- DLL 형태로 로드되는 서비스 분석이 막히면 → [REV-0135 DLL 문제 분석 시작하기](./rev-0135-dll-analysis-start.md)
- x64dbg로 실행 중인 프로세스에 붙는 방법이 헷갈리면 → [REV-0127 x64dbg로 EXE 첫 분석 시작](./rev-0127-x64dbg-first-analysis.md)
- 드라이버(.sys)와 서비스가 어떻게 다른지 궁금하면 REV-0562(드라이버 파일을 만났을 때 최소 대응) 항목을 참고

## 미니 예제
`worker.exe`가 서비스로 등록돼 있다는 것을 알고 있다고 하자.

```text
1) sc.exe qc WorkerService
   BINARY_PATH_NAME  : C:\Program Files\App\worker.exe
   → 독립 EXE 서비스임을 확인.

2) IDA로 worker.exe 로드 → Imports에서 StartServiceCtrlDispatcherW 검색.
   xref로 이동하니 wmain 함수 안에서 다음과 같은 배열을 참조:
     SERVICE_TABLE_ENTRY[0] = { "WorkerService", sub_140012A00 }
     SERVICE_TABLE_ENTRY[1] = { NULL, NULL }

3) sub_140012A00을 ServiceMain으로 이름 변경(IDA에서 N 키) 후 분석 시작.
   내부에서 RegisterServiceCtrlHandlerExW 호출 → sub_140013100을 콜백으로 등록.
   이후 CreateThread로 sub_140014200(실제 워커 로직)을 새 스레드로 실행.

4) 동적 확인: sc.exe start WorkerService 후 x64dbg Attach,
   sub_140014200에 브레이크포인트를 걸어 실제 동작 관찰.
```

## 관련 글
- REV-0562 — 드라이버(.sys) 파일을 만났을 때 최소 대응
- REV-0121 — Entry Point와 WinMain 찾기
- REV-0135 — DLL 문제 분석 시작하기
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- `StartServiceCtrlDispatcher`, `SERVICE_TABLE_ENTRY`, `ServiceMain`, `RegisterServiceCtrlHandlerEx`, `SetServiceStatus` API 시그니처와 동작: Microsoft Learn "Service Programs" / "Service Control Manager" 공식 문서 기준 (2026-09-08 검증).
- `sc.exe` 명령어 사용법 및 서비스 등록/조회 방식: Microsoft Learn "sc.exe" 공식 문서 기준.
- svchost 기반 DLL 서비스의 `ServiceDll` 레지스트리 값 구조: Microsoft 공식 문서 및 다수 Windows 내부구조 참고자료 기준.
