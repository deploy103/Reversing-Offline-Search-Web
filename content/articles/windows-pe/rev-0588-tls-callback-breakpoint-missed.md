---
id: REV-0588
title: "TLS 콜백 때문에 브레이크포인트가 먼저 안 걸릴 때"
slug: "rev-0588-tls-callback-breakpoint-missed"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["TLS callback", "IMAGE_TLS_DIRECTORY", "AddressOfCallBacks", "x64dbg TLS breakpoint", "System Breakpoint", "안티디버깅"]
aliases: ["엔트리포인트 bp가 안먹힘", "이미 코드가 실행된 것 같다", "TLS 콜백 브레이크 안걸림"]
symptom_keywords: ["entry point에 bp 걸었는데 이미 뭔가 실행된 흔적이 있다", "디버거로 열자마자 바로 종료된다", "OEP보다 먼저 실행되는 코드가 있는 것 같다", "IsDebuggerPresent 호출 지점을 못찾겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Entry Point에 브레이크포인트를 걸어도 이미 뭔가 실행된 것처럼 보이거나 프로세스가 곧바로 종료되는 이유는, PE가 `IMAGE_DIRECTORY_ENTRY_TLS`로 등록한 **TLS 콜백**이 Windows 로더에 의해 진입점보다 먼저 실행되기 때문이며, 해결책은 x64dbg의 `Options → Preferences → Events`에서 **TLS Callback** 브레이크 옵션을 켠 뒤 다시 실행하는 것이다.

## 언제 검색해야 하나
- IDA에서 `AddressOfEntryPoint`에 브레이크포인트를 걸고 x64dbg로 실행했는데, 그 지점에 도달하기도 전에 프로세스가 이미 종료되거나 안티디버깅이 발동한 것 같을 때
- x64dbg가 처음 멈추는 위치의 레지스터/메모리 상태가 "아직 아무것도 안 했는데" 라고 하기엔 이상하게 느껴질 때
- PE-bear나 IDA에서 `IMAGE_DIRECTORY_ENTRY_TLS`(데이터 디렉터리 인덱스 9)의 RVA/Size가 0이 아닌 것을 발견했을 때

## 핵심 개념
Windows 로더는 프로세스 이미지를 메모리에 매핑한 뒤 다음 순서로 코드를 실행한다.

1. **TLS 콜백들** — `IMAGE_TLS_DIRECTORY`(x86) / `IMAGE_TLS_DIRECTORY64`(x64) 구조체의 `AddressOfCallBacks` 필드가 가리키는, NULL로 끝나는 함수 포인터 배열에 등록된 함수들이 `DLL_PROCESS_ATTACH` 이유로 순서대로 먼저 호출된다.
2. 그다음에야 `OptionalHeader.AddressOfEntryPoint`가 가리키는 CRT startup 코드(REV-0121)가 실행되고, 최종적으로 `main`/`WinMain`으로 이어진다.

문제는 x64dbg를 포함한 대부분의 디버거가 **기본 설정에서는** 프로세스가 로드된 직후의 "System Breakpoint"에서 한 번 멈추고, 사용자가 지정한 Entry Point 브레이크포인트에서 또 한 번 멈추도록 되어 있는데, 이 두 지점 사이에 TLS 콜백이 이미 실행되고 지나가버린다는 점이다. 즉 사용자가 "진입점에서 멈췄으니 여기서부터 전부 봤다"고 생각해도, 실제로는 TLS 콜백 안에서 `IsDebuggerPresent`(REV-0130), `NtQueryInformationProcess`, `rdtsc` 타이밍 체크 같은 안티디버깅 코드가 먼저 실행되어 이미 디버거를 탐지했거나 메모리를 변조한 뒤일 수 있다. 이것이 패커/안티디버깅 코드가 TLS 콜백을 즐겨 남용하는 이유다.

## 화면/코드에서 보이는 징후
- x64dbg에서 F9(실행)를 눌렀을 때 사용자가 건 Entry Point 브레이크포인트에 도달하기 전에 프로세스가 이미 종료됨(안티디버깅 탐지 성공)
- IDA Imports/Exports 옆에 별도의 "TLS Callbacks" 서브뷰가 존재하거나, 진입점 함수보다 먼저 실행되는 이름 없는 함수가 보임
- PE-bear의 `Optional Header → Data Directories`에서 TLS 항목의 RVA/Size가 0이 아님
- 겉보기에 문자열/임포트가 거의 없어 보이는데도 실행하자마자 즉시 종료됨

## 가장 먼저 할 것
대상 파일에 TLS 디렉터리가 존재하는지부터 확인한다. PE-bear로 열어 `Optional Header → Data Directories`의 TLS 항목 RVA가 0이 아니면 콜백이 있다는 뜻이다. TLS 디렉터리가 있다면 Entry Point 브레이크포인트만 믿지 말고, 반드시 x64dbg의 TLS 콜백 브레이크 옵션을 먼저 켠다.

## 단계별 절차
**1) x64dbg에서 TLS 콜백 브레이크 옵션 켜기**
- 상단 메뉴 `Options → Preferences`를 연다.
- `Events` 탭에서 **"TLS Callback"** 체크박스를 켠다(System Breakpoint 관련 항목들과 함께 있는 경우가 많다).
- 대상 파일을 다시 열거나(`File → Open`) 재시작(`Ctrl+F2` 후 `F9`)하면, 사용자 Entry Point보다 먼저 TLS 콜백 함수의 시작 주소에서 디버거가 자동으로 멈춘다.

**2) IDA로 TLS 콜백 위치 정적 확인**
- IDA가 자동으로 콜백 함수에 `TlsCallback_0` 같은 이름을 붙여주는 경우가 많다. 안 붙어 있다면 `Alt+7`(세그먼트 뷰)에서 `.tls` 섹션을 찾고, `Alt+T`로 `IMAGE_TLS_DIRECTORY` 구조체를 적용해 `AddressOfCallBacks` 값을 읽는다.
- 그 주소로 이동(`Ctrl+G`)해 함수 포인터 배열을 확인하고, 각 함수로 이동해 코드를 미리 읽어둔다.

**3) 콜백 내부에서 다시 스텝**
- x64dbg가 콜백 시작에서 멈추면 `F7`(Step Into)/`F8`(Step Over)로 내부를 따라가며 `IsDebuggerPresent`, `NtQueryInformationProcess`, `OutputDebugString`, `rdtsc` 호출이 있는지 확인한다.
- 안티디버깅 체크가 보이면 반환값을 강제로 바꾸거나(레지스터 값 수정), 해당 분기를 NOP 패치하는 식으로 우회한다.

## 명령어/단축키
```text
x64dbg: Options → Preferences → Events → TLS Callback 체크
        Ctrl+F2(재시작), F9(실행), F7/F8(스텝)
IDA: Alt+7(세그먼트 뷰), Ctrl+G(주소 이동), Alt+T(구조체 적용)
```

## 출력 해석
- x64dbg가 멈췄을 때 상태 표시줄/Log의 "Reason"이 Entry Point가 아니라 TLS 콜백으로 표시되면 옵션이 정상 적용된 것이다.
- TLS 디렉터리의 RVA/Size가 둘 다 0이면 이 바이너리에는 TLS 콜백이 없으므로 이 글의 시나리오와 무관하고, 원인은 다른 곳(REV-0583 anti-attach 등)에 있다.

## 흔한 실수
- TLS 콜백 브레이크 옵션을 켜지 않은 채 "Entry Point부터 스텝했으니 전부 봤다"고 착각하는 것 — 콜백은 그보다 먼저 지나가버린 뒤다.
- IDA 정적 분석만으로 "콜백이 아무것도 안 한다"고 판단하는 것. 레지스터를 통한 간접 호출(`call rax` 등)로 실제 로직이 숨겨진 경우가 많아 반드시 동적으로 재확인해야 한다.
- 콜백이 여러 개 등록된 경우 첫 번째만 확인하고 끝내는 것 — 배열이 NULL로 끝날 때까지 전부 확인해야 한다.
- DLL을 분석할 때도 TLS 콜백이 있을 수 있다는 것을 잊고 EXE에서만 이 절차를 적용하는 것.

## 막혔을 때 다음 체크
- TLS 콜백을 우회했는데도 여전히 즉시 종료된다면 → REV-0583(x64dbg로 붙였는데 바로 종료(anti-attach)될 때)을 확인한다.
- 콜백 안의 API 이름만 보고 기능이 안 잡히면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.
- TLS 콜백 개념 자체를 처음 접한다면 → REV-0133(TLS Callback과 main 이전 코드)에서 구조체 필드까지 자세히 다룬다.

## 미니 예제
IDA 디컴파일 결과로 다음 TLS 콜백을 봤다고 하자.

```c
void __stdcall TlsCallback_0(PVOID DllHandle, DWORD Reason, PVOID Reserved)
{
    if ( Reason == DLL_PROCESS_ATTACH )
    {
        if ( IsDebuggerPresent() )
            ExitProcess(1);
    }
}
```

TLS 콜백 브레이크 옵션 없이 그냥 F9로 실행하면, Entry Point에 걸어둔 브레이크포인트에 도달하기도 전에 이 콜백이 먼저 실행되어 `IsDebuggerPresent()`가 참을 반환하고 프로세스가 종료된다. 반대로 옵션을 켜두면 이 함수의 시작에서 정확히 멈추고, `call IsDebuggerPresent` 직후 `EAX`를 0으로 강제로 바꾼 뒤 계속 실행하면 자연스럽게 진입점까지 도달할 수 있다.

## 관련 글
- REV-0133 — TLS Callback과 main 이전 코드
- REV-0583 — x64dbg로 붙였는데 바로 종료(anti-attach)될 때
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- TLS 콜백이 Entry Point보다 먼저 실행되는 로더 순서는 Microsoft PE/COFF 형식 공식 문서 및 다수의 리버싱 레퍼런스, 실제 x64dbg/IDA 동작으로 재확인 가능한 사실이다.
- x64dbg의 TLS 콜백 브레이크 옵션 메뉴 위치는 버전에 따라 문구가 다를 수 있으므로 실습 시 `Options → Preferences → Events` 탭을 직접 확인할 것(2026-09-08 기준 서술).
