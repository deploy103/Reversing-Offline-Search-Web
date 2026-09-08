---
id: REV-0608
title: "RIP가 예상 못한 예외 핸들러로 튈 때"
slug: "rev-0608-rip-jumps-to-exception-handler"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, IDA]
keywords: ["SEH", "VEH", "KiUserExceptionDispatcher", "RtlDispatchException", "AddVectoredExceptionHandler", "EXCEPTION_BREAKPOINT", "EXCEPTION_SINGLE_STEP"]
aliases: ["예외 핸들러로 점프", "SEH 안티디버깅", "VEH 안티디버깅", "예외 기반 제어흐름 난독화"]
symptom_keywords: ["디버거로 스텝하다가 갑자기 모르는 주소로 튄다", "RIP가 ntdll 안으로 들어간다", "예외가 발생하고 나서 코드가 이상한 곳으로 간다", "SEH 체인이 이상하다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
디버거가 예외(대개 `INT3`, `EXCEPTION_SINGLE_STEP`, 접근 위반 등)를 대상 프로그램에 전달하지 않고 자신이 가로채 버렸거나, 반대로 대상 프로그램이 SEH/VEH 핸들러를 의도적으로 등록해 예외를 트리거로 삼아 제어 흐름을 옮기는 것이므로, x64dbg의 예외 전달(Pass to application) 설정을 확인하고 SEH 체인을 직접 들여다보면 원인을 알 수 있다.

## 언제 검색해야 하나
- `F7`/`F8`로 한 줄씩 스텝하다가 갑자기 `RIP`가 자신이 분석하던 모듈이 아니라 `ntdll.dll`이나 전혀 모르는 주소로 튀었을 때
- 예외가 발생한 직후 코드가 원래 흐름과 무관해 보이는 곳으로 이동해서 실행을 이어갈 때
- `AddVectoredExceptionHandler`나 SEH 체인 설정 코드(`fs:[0]`/`gs:[0]` 접근, x64는 `.pdata`/`.xdata` 기반 예외 디렉터리)가 Import/코드에서 보일 때

## 핵심 개념
Windows에서 예외(0으로 나누기, 접근 위반, `INT3` 브레이크포인트, 싱글스텝 등)가 발생하면 커널이 이를 감지하고 유저 모드의 `ntdll.dll!KiUserExceptionDispatcher`로 제어를 넘긴다. 이 함수는 내부적으로 `RtlDispatchException`을 호출해 등록된 예외 핸들러를 순서대로 찾아 실행시킨다. 이때 두 가지 핸들러 체계가 함께 동작한다.

- **VEH(Vectored Exception Handler)**: `PVOID AddVectoredExceptionHandler(ULONG First, PVECTORED_EXCEPTION_HANDLER Handler);`로 등록한다. 함수가 어느 스택 프레임에 속하는지와 무관하게 프로세스 전역에 걸리며, **SEH보다 먼저** 호출된다.
- **SEH(Structured Exception Handling)**: x86에서는 스레드 스택에 체인 형태(`fs:[0]`이 가리키는 연결 리스트)로 등록되고, x64에서는 이런 런타임 체인 대신 PE의 예외 디렉터리(`.pdata`)에 컴파일 시점에 정적으로 기록된 언와인드 정보를 사용한다.

디버거가 대상 프로세스에 붙어 있을 때, 프로세스 안에서 발생한 예외는 **디버거에게 먼저 통지**된다(디버그 이벤트). 이 시점에 디버거가 "이 예외를 대상 프로그램에게 넘길지(pass), 아니면 디버거가 처리하고 끝낼지"를 선택할 수 있다. 여기서 다음과 같은 두 가지 혼란이 자주 생긴다.

1. **디버거가 예외를 삼켜버림**: 대상 프로그램이 SEH/VEH 핸들러 안에 진짜 복호화/실행 로직을 숨겨놓았는데(예외 지향 프로그래밍, Exception-Oriented Programming), 디버거가 기본 설정상 이 예외를 애플리케이션에 전달하지 않고 그냥 멈춰버리면 핸들러가 실행되지 않아 "코드가 어디로도 안 간다"고 느껴진다.
2. **예외가 전달되어 핸들러로 튐**: 반대로 예외가 정상적으로 전달되면 `RIP`가 등록된 핸들러 주소로 이동하는데, 이 핸들러가 원래 분석 중이던 함수와 전혀 상관없어 보이는 위치(다른 모듈, 또는 실행 중 메모리에 새로 풀린 코드)에 있어서 "예상 못한 곳으로 튀었다"고 느껴진다. 이는 실제로는 정상적인 예외 디스패치 과정이며, 프로텍터가 일부러 예외를 일으켜 분석을 어렵게 만드는 전형적인 기법이다.

## 화면/코드에서 보이는 징후
- x64dbg 하단 로그에 `EXCEPTION_BREAKPOINT`, `EXCEPTION_SINGLE_STEP`, `EXCEPTION_ACCESS_VIOLATION` 같은 예외 이름이 first chance/second chance와 함께 출력됨
- 스텝 실행 중 `RIP`가 갑자기 `ntdll.dll` 내부 주소(`KiUserExceptionDispatcher` 부근)로 이동
- IDA Imports에 `AddVectoredExceptionHandler`, `SetUnhandledExceptionFilter`가 존재
- 코드에 고의로 `0`으로 나누거나 잘못된 포인터를 역참조하는 등, 명백히 비정상적인 연산이 있는데 프로그램이 크래시 없이 계속 실행됨(핸들러가 이를 잡아서 복구하고 있다는 뜻)

## 가장 먼저 할 것
1. x64dbg의 예외 처리 설정을 확인한다(`Options → Preferences → Exceptions`, 또는 명령창에서 `SetExceptionBPX`). 기본적으로 first-chance 예외를 디버거가 가로채고 있는지 확인한다.
2. 예외가 발생한 순간 `Shift+F9`(예외를 애플리케이션에 전달하며 실행)로 진행해, 등록된 SEH/VEH 핸들러가 실제로 실행되는지 관찰한다.
3. x64dbg의 SEH 체인 보기(스택 창 우클릭 → "SEH 체인" 또는 `dseh` 유사 커맨드, x64는 `.pdata` 기반이라 IDA의 `Exceptions` 뷰나 함수 속성에서 확인)로 등록된 핸들러 주소 목록을 확보한다.

## 단계별 절차
**1) 예외를 애플리케이션에 전달하도록 설정**
- x64dbg에서 일반 실행(`F9`)은 예외를 디버거가 처리하고 애플리케이션에는 넘기지 않는 경우가 있다. 반대로 `Shift+F9`(Pass exception to application and run에 해당하는 기능)를 사용하면 예외가 실제로 SEH/VEH 핸들러로 전달된다. 어떤 단축키가 "전달"이고 어떤 것이 "무시"인지는 `Options → Preferences → Exceptions`에서 개별 예외 코드별로 "add to ignore list" 여부를 확인해 명확히 한다.

**2) SEH 체인을 직접 확인**
- x86 바이너리라면 스택 상단(`fs:[0]`이 가리키는 위치)부터 시작해 `EXCEPTION_REGISTRATION_RECORD` 연결 리스트를 따라가며 각 핸들러 함수 주소를 확인한다. x64dbg는 스택 창에서 SEH 체인을 표시해주는 기능을 제공한다.
- x64 바이너리라면 런타임 체인 대신 PE의 예외 디렉터리(`IMAGE_DIRECTORY_ENTRY_EXCEPTION`)에 있는 `RUNTIME_FUNCTION` 배열을 IDA가 자동으로 인식해 각 함수의 언와인드 정보와 연결된 예외 핸들러를 보여준다.

**3) 핸들러 주소에 미리 브레이크포인트 걸기**
- 1)~2)에서 확인한 핸들러 함수 주소에 `INT3` 브레이크포인트를 미리 걸어두면, 예외가 실제로 전달되는 순간 그 핸들러 내부에서 바로 멈출 수 있어 "왜 튀었는지"를 코드 레벨에서 확인할 수 있다.
- 이후 `RIP`가 이동한 근거(예외 코드, `ExceptionAddress`, `CONTEXT.Eip`/`Rip` 수정 여부)를 `EXCEPTION_POINTERS` 구조체를 통해 하나씩 확인한다.

**4) 커스텀 VEH가 진짜 로직을 숨기고 있는지 확인**
- 핸들러 내부에서 `ExceptionInfo->ContextRecord->Rip`를 수정하고 있다면, 이는 예외를 트리거로 삼아 원래 실행 흐름과 다른 곳으로 점프시키는 전형적인 난독화 기법이다. 이 경우 핸들러 코드 자체가 진짜 로직이므로, 여기서부터 다시 분석을 시작해야 한다.

## 명령어/단축키
- x64dbg: `Shift+F9`(예외 전달하며 실행), `F9`(일반 실행), `Options → Preferences → Exceptions`(예외별 처리 정책), 스택 창 우클릭 → SEH 체인 보기
- x64dbg 명령창: `SetExceptionBPX <예외코드/이름> <first|second|all>`(특정 예외 발생 시 강제로 브레이크)
- IDA: `Exceptions` 뷰(`IMAGE_DIRECTORY_ENTRY_EXCEPTION` 기반), 함수 속성에서 언와인드 정보 확인

## 출력 해석
- `dwFirstChance`가 1(첫 통지)인 상태에서 계속 무시하고 진행하면 결국 프로그램의 자체 핸들러(SEH/VEH)로 넘어가고, 그래도 처리되지 않으면 `second chance`로 다시 디버거에게 통지된다. second chance까지 갔는데도 처리가 안 되면 프로세스가 크래시된다.
- 핸들러 진입 시 첫 인자로 들어오는 `EXCEPTION_POINTERS*`의 `ContextRecord`를 확인하면, 그 핸들러가 실행을 재개할 때 사용할 실제 `Rip`/`Eip` 값을 미리 알 수 있다.

## 흔한 실수
- 예외가 발생하면 무조건 "버그"나 "디버거 문제"로 여기고 계속 `F9`만 눌러서 지나쳐 버리는 것. 예외 자체가 프로그램의 정상적인 제어 흐름의 일부일 수 있다.
- SEH 체인과 VEH 체인을 혼동해서 하나만 확인하고 다른 하나를 놓치는 것. x64에서는 VEH가 흔히 쓰이므로 `AddVectoredExceptionHandler` xref를 별도로 확인해야 한다.
- 예외를 전달했는데도 핸들러가 실행되지 않는다면, 디버거가 여전히 해당 예외 코드를 자신의 "ignore list"에 넣고 처리해버리고 있을 가능성을 놓치는 것.

## 막혔을 때 다음 체크
- 하드웨어 브레이크포인트가 이 과정에서 같이 사라진다면 → REV-0607을 확인한다.
- SEH의 기본 구조 자체가 낯설다면 → REV-0134(SEH와 예외 기반 제어 흐름 기초)를 먼저 읽는다.
- 예외 처리 이후 스택이 깨졌다는 크래시가 뒤따른다면 → REV-0609를 확인한다.

## 미니 예제
x64dbg로 스텝 실행 중 다음과 같은 로그가 하단에 출력되었다고 하자.

```text
EXCEPTION_ACCESS_VIOLATION at 0x00401234 (first chance)
```

여기서 그냥 `F9`를 눌러 넘겨버리면, 프로그램이 등록해 둔 VEH 핸들러(예: `0x00405000`)로 실행이 넘어가면서 `RIP`가 갑자기 `0x00405000`으로 바뀐 것처럼 보인다. 사전에 `0x00405000`에 브레이크포인트를 걸어두었다면, 예외가 전달되는 즉시 그 자리에서 멈춰 "이 주소가 바로 VEH 핸들러이며, 여기서부터가 진짜 복호화/분기 로직"이라는 것을 확인할 수 있다.

## 관련 글
- REV-0134 — SEH와 예외 기반 제어 흐름 기초
- REV-0607 — 하드웨어 브레이크포인트가 갑자기 사라질 때
- REV-0609 — 스택이 깨졌다는 예외가 발생할 때(Stack Corruption)

## 출처/검증
- `KiUserExceptionDispatcher`/`RtlDispatchException`을 통한 예외 디스패치 흐름, VEH가 SEH보다 먼저 호출된다는 점, x64는 정적 예외 디렉터리(`.pdata`) 기반이라는 점은 Windows 예외 처리 관련 공개 기술 자료(SEH/VEH 비교 자료, Windows 드라이버 문서의 예외 제어 관련 페이지) 기준이다.
- 예외를 트리거로 삼아 제어 흐름을 옮기는 SEH/VEH 기반 안티디버깅·난독화 기법은 다수의 악성코드 분석 및 프로텍터 분석 라이트업에서 반복적으로 확인되는 패턴이다(2026-09-08 기준 서술).
- x64dbg의 예외 브레이크포인트 명령(`SetExceptionBPX`)과 first/second chance 개념은 x64dbg 공식 문서 기준이다.
