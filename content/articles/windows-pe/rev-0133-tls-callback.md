---
id: REV-0133
title: "TLS Callback과 main 이전 코드"
slug: "rev-0133-tls-callback"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg, "PE-bear"]
keywords: ["TLS callback", "IMAGE_TLS_DIRECTORY", "AddressOfCallBacks", "entry point", "안티디버깅", "System Breakpoint", "TLS directory"]
aliases: ["TLS 콜백", "TLS 디렉터리", "main 이전에 실행되는 코드", "브레이크포인트가 안 걸리는 이유"]
symptom_keywords: ["entry point에 bp 걸었는데 이미 코드가 실행됨", "OEP 이전에 뭔가 실행되는 것 같다", "IsDebuggerPresent가 어디서 호출되는지 모르겠다", "x64dbg 처음 멈추는 위치가 예상과 다르다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
TLS(Thread Local Storage) 콜백은 실행 파일의 진입점(Entry Point, `main`/`WinMain`으로 이어지는 코드)보다 먼저, 심지어 디버거가 보통 자동으로 멈추는 지점보다도 먼저 실행되는 코드이기 때문에, 이를 모르면 "내가 아직 아무 브레이크포인트도 안 걸었는데 왜 벌써 무언가 실행된 흔적이 있지?"라는 상황에 빠지기 쉽고, 실제로 패커와 안티디버깅 코드가 즐겨 쓰는 자리다.

## 언제 검색해야 하나
- x64dbg로 파일을 열었는데 첫 정지 지점에서 레지스터나 메모리 상태가 이미 뭔가 변경되어 있는 것 같을 때
- IDA에서 Entry Point(진입점)에 브레이크포인트를 걸고 실행했는데, 안티디버깅 탐지(예: 프로세스가 바로 종료됨)가 그보다 먼저 일어난 것 같을 때
- PE 헤더를 보다가 `IMAGE_DIRECTORY_ENTRY_TLS`라는 이름을 봤는데 이게 뭔지 모를 때
- "TLS 콜백을 이용한 안티디버깅"이라는 CTF 라이트업 문구를 보고 원리를 찾아볼 때

## 핵심 개념
Windows 실행 파일(PE)은 스레드마다 독립적으로 갖는 저장공간인 TLS(Thread Local Storage)를 지원한다. 이 TLS 영역이 초기화될 때 실행되도록 등록해둘 수 있는 콜백 함수들이 있는데, 이것이 **TLS 콜백**이다.

중요한 점은 실행 순서다. Windows 로더는 프로세스를 만들고 메모리에 이미지를 매핑한 뒤, 다음 순서로 코드를 실행한다.

1. TLS 콜백들 (등록된 순서대로, 프로세스 시작 시 `DLL_PROCESS_ATTACH` 이유로 호출)
2. PE 헤더의 `AddressOfEntryPoint`가 가리키는 진입점 코드 (컴파일러가 생성한 C 런타임 초기화 코드, 결국 `main`/`WinMain` 호출로 이어짐)

즉 TLS 콜백은 우리가 보통 "프로그램이 시작하는 곳"이라고 생각하는 진입점보다 먼저 실행된다. 그런데 초심자용 디버거 사용법에서 "F9로 실행하면 진입점에서 멈춘다"거나 "IDA로 열면 entry point에서 멈춘다"는 설명만 알고 있으면, TLS 콜백 안에서 이미 `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, `rdtsc` 타이밍 체크, 또는 자기 자신을 복호화하는 로직이 먼저 실행돼버린 뒤에야 디버거가 멈추는 상황을 만나게 된다. 이것이 흔히 "패커/안티디버깅 트릭"으로 불리는 TLS 콜백 남용이다.

PE 구조상 TLS 콜백은 `IMAGE_TLS_DIRECTORY`(x86) / `IMAGE_TLS_DIRECTORY64`(x64) 구조체가 가진 `AddressOfCallBacks` 필드가 가리키는, 함수 포인터들의 배열(마지막은 NULL로 끝남)에 등록되어 있다. 이 디렉터리 자체는 PE 옵셔널 헤더의 데이터 디렉터리 배열 중 `IMAGE_DIRECTORY_ENTRY_TLS`(인덱스 9) 항목이 가리킨다. 즉 TLS 콜백은 임포트 테이블(REV-0119 참고)이나 익스포트 테이블처럼 PE 헤더에 명시적으로 등록된 별도의 실행 경로이며, 디스어셈블러가 자동으로 "이것도 코드 시작점이다"라고 표시해주지 않으면 존재 자체를 놓치기 쉽다.

## 화면/코드에서 보이는 징후
- IDA에서 Imports/Exports 옆에 "TLS Callbacks" 서브뷰가 별도로 보이거나, PE 헤더 파싱(Alt+7 등으로 세그먼트 확인) 시 `.tls` 섹션 또는 TLS 디렉터리가 존재
- x64dbg에서 실행을 시작했는데 System Breakpoint(시스템 브레이크포인트) 이후, 사용자가 지정한 Entry Point보다 훨씬 이전에 알 수 없는 코드 블록에서 한 번 더 멈추거나 스텝이 튐
- PE-bear의 "Directories" 탭에서 TLS 항목의 RVA/Size가 0이 아님
- 문자열/임포트가 거의 없어 보이는데도 프로세스가 실행 직후 즉시 종료되거나 디버거를 감지한 것처럼 동작

## 가장 먼저 할 것
1. PE-bear 또는 IDA로 대상 파일을 열어 **TLS 디렉터리가 존재하는지**부터 확인한다. PE-bear는 "Optional Header" → "Data Directories"에서 TLS 항목의 RVA가 0이 아니면 콜백이 있다는 뜻이다.
2. TLS 디렉터리가 있다면, x64dbg에서 진입점 브레이크포인트를 걸기 전에 **TLS 콜백 브레이크포인트 옵션을 먼저 켠다**(아래 절차 참고). 이걸 안 하면 콜백 안의 코드를 그냥 지나쳐버린다.

## 단계별 절차
**1) IDA에서 TLS 콜백 찾기**
- 파일을 열면 IDA가 자동으로 TLS 디렉터리를 파싱해서 콜백 함수 시작 주소에 `TlsCallback_0` 같은 이름을 붙여주는 경우가 많다.
- 안 붙어 있다면 PE 헤더를 직접 확인한다. `Alt+7`(세그먼트 뷰) 또는 `View → Open subviews → Segments`로 `.tls` 섹션을 찾고, 시작 오프셋에서 `IMAGE_TLS_DIRECTORY` 구조체를 수동으로 매핑(`Alt+T` 구조체 적용)해 `AddressOfCallBacks` 필드 값을 읽는다.
- 그 주소로 이동(`Ctrl+G`)하면 함수 포인터 배열이 보이고, 배열의 각 항목이 실제 콜백 함수 주소다. 그 함수로 점프해서 코드를 확인한다.

**2) x64dbg에서 TLS 콜백에 브레이크포인트 걸기**
- 상단 메뉴 `Options → Preferences`(환경설정)를 연다.
- `Events`(이벤트) 탭에서 **"TLS Callback"**(또는 버전에 따라 "System Breakpoint"와 함께 있는 TLS 콜백 관련 항목) 체크박스를 켠다. 이 옵션을 켜두면 x64dbg가 프로세스를 로드할 때 TLS 콜백 진입 시점에서 자동으로 실행을 멈춰준다.
- 파일을 다시 열거나(`File → Open`) 재시작(`Ctrl+F2` 후 `F9`)하면, 사용자 진입점보다 먼저 TLS 콜백 함수 시작 주소에서 디버거가 멈추는 것을 확인할 수 있다.
- 이 시점부터 `F7`(Step Into)/`F8`(Step Over)로 콜백 내부를 따라가며 무슨 검사를 하는지 확인한다.

**3) 콜백 내용 분석**
- 콜백 안에서 `IsDebuggerPresent`, `NtQueryInformationProcess`, `OutputDebugString`, `rdtsc` 등이 호출되는지 확인한다. 이런 API가 보이면 안티디버깅 목적일 가능성이 매우 높다(자세한 API 이름 해석법은 REV-0138 참고).
- 콜백이 아무 것도 안 하고 바로 리턴한다면(정상적인 C++ 전역 객체의 스레드 로컬 초기화용일 수 있음) 굳이 더 파고들 필요는 없다.

## 명령어/단축키
- x64dbg: `Options → Preferences → Events → TLS Callback` 체크, `Ctrl+F2`(재시작), `F9`(실행), `F7`/`F8`(스텝)
- IDA: `Alt+7`(세그먼트 뷰), `Ctrl+G`(주소 이동), `Alt+T`(구조체 적용), `X`(교차 참조로 콜백 호출 지점 확인)
- PE-bear: `Optional Header → Data Directories`에서 TLS 항목 RVA/Size 확인

## 출력 해석
- TLS 디렉터리의 RVA/Size가 모두 0이면 이 바이너리에는 TLS 콜백이 없다는 뜻이므로 이 글의 시나리오와 무관하다.
- `AddressOfCallBacks`가 가리키는 배열에 함수 포인터가 하나 이상 있고 마지막이 0으로 끝나면, 그 개수만큼 콜백이 프로세스/스레드 생성 시 순서대로 호출된다.
- x64dbg가 TLS 콜백에서 멈췄을 때 `Reason`(멈춘 이유)이 진입점이 아니라 TLS 콜백으로 표시되면 정상적으로 옵션이 적용된 것이다.

## 흔한 실수
- TLS 콜백 브레이크포인트 옵션을 켜지 않은 채로 "진입점부터 스텝했으니 전부 봤다"고 착각하는 것. 콜백은 그보다 먼저 실행되므로 이미 지나간 뒤다.
- IDA 정적 분석만 보고 "콜백이 아무 것도 안 한다"고 판단했지만, 실제로는 콜백 안에서 간접 호출(레지스터를 통한 `call`)로 실제 로직이 숨겨진 경우를 놓치는 것. 이럴 땐 반드시 동적 분석(x64dbg)으로 실제 실행 경로를 따라가야 한다.
- DLL에도 TLS 콜백이 있을 수 있다는 것을 잊고 EXE에서만 확인하는 것. DLL을 분석할 때도(REV-0135 참고) TLS 디렉터리를 반드시 함께 확인해야 한다.
- 콜백이 여러 개 등록된 경우 첫 번째 콜백만 보고 끝내는 것. 배열 끝(NULL)까지 전부 확인해야 한다.

## 막혔을 때 다음 체크
- TLS 콜백 안에서 예외가 발생해 흐름이 바뀌는 것 같다면 → REV-0134(SEH와 예외 기반 제어 흐름)를 먼저 읽는다.
- 콜백이 하는 일이 API 이름만 보고 감이 안 잡히면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.
- TLS 콜백을 우회해도 여전히 실행이 이상하면 리소스 섹션에 추가 페이로드가 숨어 있을 수 있으니 → REV-0141(Resource Section과 숨겨진 데이터 확인)을 확인한다.

## 미니 예제
IDA 디컴파일 결과로 다음과 같은 TLS 콜백 함수를 봤다고 가정하자.

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

이 코드는 프로세스가 처음 붙을 때(`DLL_PROCESS_ATTACH`) `IsDebuggerPresent`를 호출해서 참이면 즉시 종료한다. x64dbg에서 TLS 콜백 브레이크포인트 옵션 없이 그냥 F9를 눌러 실행했다면, 사용자가 아무 브레이크포인트도 걸지 않았어도 프로세스가 바로 죽어버려서 "왜 아무것도 안 했는데 프로그램이 꺼지지?"라는 혼란을 겪게 된다. 반대로 TLS 콜백 옵션을 켜두면 이 함수의 시작 부분에서 정확히 멈추고, `IsDebuggerPresent` 호출 직후 반환값(EAX)을 강제로 0으로 바꾸는 식으로 우회할 수 있다.

## 관련 글
- REV-0134 — SEH와 예외 기반 제어 흐름 기초
- REV-0135 — DLL 문제 분석 시작하기
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 출처/검증
- TLS 디렉터리 구조(`IMAGE_TLS_DIRECTORY`, `AddressOfCallBacks`)는 Microsoft PE/COFF 형식 공식 문서 기준이다.
- Windows 로더가 진입점보다 TLS 콜백을 먼저 실행한다는 순서는 다수의 리버싱 레퍼런스와 실제 x64dbg/IDA 동작으로 재확인 가능한 사실이다.
- x64dbg의 TLS 콜백 브레이크포인트 옵션 위치는 도구 버전에 따라 메뉴 문구가 다소 다를 수 있으므로, 실습 시 `Options → Preferences → Events` 탭을 직접 확인할 것(2026-09-08 기준 서술).
