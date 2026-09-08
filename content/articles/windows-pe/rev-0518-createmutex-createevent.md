---
id: REV-0518
title: "WinAPI 동기화 함수 사전: CreateMutex CreateEvent"
slug: "rev-0518-createmutex-createevent"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CreateMutexW", "CreateEventW", "WaitForSingleObject", "동기화 객체", "이미 실행 중"]
aliases: ["뮤텍스 생성 함수", "이벤트 객체 생성", "단일 인스턴스 체크 함수"]
symptom_keywords: ["CreateMutex가 왜 있는지 모르겠다", "프로그램이 이미 실행 중이라고 뜨는 이유를 모르겠다", "CreateEvent 인자를 모르겠다", "WaitForSingleObject와 관계가 궁금하다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CreateMutexW`/`CreateEventW`는 여러 스레드(또는 여러 프로세스 인스턴스) 사이의 동기화를 위한 커널 객체를 만드는 함수로, 리버싱에서는 주로 "프로그램이 이미 실행 중인지 검사하는 단일 인스턴스(single instance) 체크"나 "특정 조건이 될 때까지 스레드를 대기시키는 이벤트 기반 트리거"를 찾는 단서로 쓰인다.

## 언제 검색해야 하나
- 프로그램을 두 번 실행하면 바로 종료되거나 "이미 실행 중입니다" 메시지가 뜨는 원인을 찾을 때
- 임포트 목록에서 `CreateMutexW`, `CreateEventW`, `WaitForSingleObject`, `SetEvent`를 발견했을 때
- 특정 이벤트가 발생(예: 디버거 감지, 특정 파일 생성)해야만 다음 로직이 실행되는 구조를 분석할 때
- 안티디버깅/안티멀티인스턴스 우회를 시도해야 할 때

## 핵심 개념
```c
HANDLE CreateMutexW(
    LPSECURITY_ATTRIBUTES lpMutexAttributes, // 1. 보안 속성(대개 NULL)
    BOOL                   bInitialOwner,     // 2. TRUE면 생성 즉시 호출 스레드가 소유
    LPCWSTR                lpName             // 3. 뮤텍스 이름(NULL이면 이름 없는 뮤텍스)
);

HANDLE CreateEventW(
    LPSECURITY_ATTRIBUTES lpEventAttributes, // 1. 보안 속성(대개 NULL)
    BOOL                   bManualReset,      // 2. TRUE=수동 리셋, FALSE=자동 리셋
    BOOL                   bInitialState,     // 3. TRUE=처음부터 signaled 상태
    LPCWSTR                lpName             // 4. 이벤트 이름(NULL이면 이름 없는 이벤트)
);
```

`CreateMutexW`는 이름(`lpName`)이 주어지면 이미 같은 이름의 뮤텍스가 존재하는지 확인하고, 존재하면 새로 만들지 않고 기존 핸들을 반환한다. 이 경우 `GetLastError()`가 `ERROR_ALREADY_EXISTS`(183)를 반환하므로, 프로그램은 이 값을 검사해서 "내가 이미 실행 중이구나"를 판단하고 즉시 종료하는 패턴을 자주 쓴다. 이것이 흔히 보는 "이미 실행 중입니다" 안내창의 정체다.

`CreateEventW`는 특정 시점에 "신호(signal)"를 보내는 용도의 객체를 만든다. `bManualReset`이 `FALSE`면 `WaitForSingleObject`로 대기하던 스레드가 깨어나는 즉시 자동으로 non-signaled 상태로 돌아가고(한 번에 한 스레드만 깨움), `TRUE`면 `ResetEvent`를 명시적으로 호출할 때까지 signaled 상태가 유지된다(여러 스레드가 동시에 깨어날 수 있음). 이벤트를 신호 상태로 만드는 함수는 `SetEvent`, 대기하는 함수는 `WaitForSingleObject`/`WaitForMultipleObjects`다.

## 화면/코드에서 보이는 징후
- 프로그램 시작 직후(`WinMain`/`main` 초반)에 `CreateMutexW` 호출이 있고, 바로 뒤에 `GetLastError` 호출 및 `cmp eax, 0B7h`(183, `ERROR_ALREADY_EXISTS`) 비교가 나오는 패턴
- 비교 결과가 참이면 `MessageBoxW`로 안내창을 띄우고 `ExitProcess`/`return`으로 종료하는 흐름
- 별도 스레드가 `WaitForSingleObject(hEvent, INFINITE)`로 멈춰 있다가, 특정 조건에서 다른 스레드가 `SetEvent(hEvent)`를 호출하면 진행되는 구조

## 가장 먼저 할 것
1. `CreateMutexW` 호출 직후 `GetLastError`가 호출되는지, 그 반환값이 `ERROR_ALREADY_EXISTS`(183)와 비교되는지부터 확인한다.
2. 뮤텍스/이벤트의 이름 문자열(4번째 또는 3번째 인자)을 확인해서 어떤 이름으로 단일 인스턴스를 체크하는지 파악한다(이 이름을 알면 x64dbg나 별도 도구로 미리 같은 이름의 뮤텍스를 만들어 우회 테스트를 할 수 있다).
3. 단일 인스턴스 체크가 목적이 아니라면, 이 동기화 객체가 어느 스레드와 어느 스레드 사이를 조율하는지부터 파악한다.

## 단계별 절차
**1) 정적 분석(IDA)**
- 임포트 목록에서 `CreateMutexW`(또는 A)를 찾아 `X`로 교차 참조한다.
- 호출 직후 코드 흐름을 따라가 `GetLastError` 비교 및 분기(`je`/`jne`)를 확인한다.

**2) 동적 분석(x64dbg)**
- `bp CreateMutexW` 후 실행, `RDX`(x64, bInitialOwner)/`R8`(lpName 문자열 포인터, 정확히는 3번째 인자 위치) 등을 확인한다. x64에서 `CreateMutexW`는 `RCX`=lpMutexAttributes, `RDX`=bInitialOwner, `R8`=lpName 순서다.
- `R8`을 Follow in Dump 후 UTF-16으로 보면 뮤텍스 이름 문자열을 읽을 수 있다.
- 함수 리턴 직후(`ret` 다음 줄, 또는 F8로 스텝오버 후) `EAX`/`RAX`(반환된 핸들)와 `GetLastError` 결과를 확인한다.

## 명령어/단축키
- x64dbg: `bp CreateMutexW`, `bp CreateEventW`, `bp SetEvent`, `bp WaitForSingleObject`
- x64dbg: F8(스텝오버)로 `GetLastError` 호출 결과까지 진행 후 `EAX` 확인
- IDA: `X`(교차 참조), `F5`(디컴파일)

## 출력 해석
- `CreateMutexW` 반환값이 `NULL`이면 생성 자체가 실패한 것(권한 문제 등).
- 반환값이 유효한 핸들이지만 `GetLastError() == ERROR_ALREADY_EXISTS`(183)이면 "이미 같은 이름의 뮤텍스가 존재했다"는 뜻 — 단일 인스턴스 체크의 핵심 판단 지점이다.
- `CreateEventW`에서 `bInitialState`가 `TRUE`면 만들어지자마자 이미 signaled 상태이므로 첫 `WaitForSingleObject` 호출은 즉시 반환된다.

## 흔한 실수
- `CreateMutexW` 반환값이 `NULL`이 아니면 무조건 성공이라고 판단하는 것. `ERROR_ALREADY_EXISTS`여도 핸들 자체는 유효하게 반환되므로 반드시 `GetLastError`까지 함께 봐야 한다.
- 뮤텍스 이름이 없는(`lpName = NULL`) 경우인데도 단일 인스턴스 체크 대상으로 착각하는 것. 이름이 없으면 프로세스 간 공유가 안 되므로 단순 스레드 동기화 목적일 가능성이 높다.
- `CreateEvent`와 `CreateMutex`의 용도를 혼동하는 것. 뮤텍스는 "상호 배제(한 번에 하나만 소유)"가 목적이고, 이벤트는 "신호 전달(조건 알림)"이 목적으로 서로 다른 문제를 푼다.

## 막혔을 때 다음 체크
- 뮤텍스/이벤트 핸들을 다 쓴 뒤 정리하는 방식이 궁금하면 → REV-0519(CloseHandle DuplicateHandle GetLastError)를 본다.
- 동기화 이후 이어지는 흐름이 다른 모듈 로드와 관련 있다면 → REV-0520(LoadLibraryEx FreeLibrary GetModuleHandle)을 본다.
- 안티디버깅 목적의 다른 API 흔적이 궁금하면 → REV-0130(IsDebuggerPresent 안티디버깅 식별)을 본다.

## 미니 예제
x64dbg에서 `bp CreateMutexW` 후 실행하니 다음처럼 멈췄다.

```text
RCX = 0x0000000000000000   (lpMutexAttributes = NULL)
RDX = 0x0000000000000001   (bInitialOwner = TRUE)
R8  = 0x00000221A3B01000   (lpName)
```

`R8`을 Follow in Dump, UTF-16으로 전환하면 `L"Global\\MyAppSingleInstance123"`가 보인다. 함수 리턴 후 `GetLastError`를 호출한 결과가 `183`(`0xB7`)이라면, 이 프로그램은 이미 같은 이름의 뮤텍스가 있다는 뜻이므로 곧이어 "이미 실행 중" 메시지 박스와 종료 코드가 따라올 가능성이 높다.

추가로 `CreateSemaphoreW`나 `CreateWaitableTimerW` 같은 다른 동기화 객체 생성 함수도 이름/인자 구조가 비슷하며, 모두 `WaitForSingleObject`/`WaitForMultipleObjects`로 대기할 수 있는 커널 객체를 만든다는 공통점이 있다. 뮤텍스는 "한 번에 하나의 소유자"라는 상호 배제 규칙을 강제하지만 세마포어는 지정한 개수까지 동시 소유를 허용한다는 점에서 목적이 다르다. 리버싱 관점에서는 정확한 동기화 의미론까지 몰라도, "이 API가 등장하면 스레드 간 또는 프로세스 간 조율 지점"이라는 사실만 인지해도 분석 우선순위를 정하는 데 충분하다.

## 관련 글
- REV-0519 — WinAPI 핸들 함수 사전: CloseHandle DuplicateHandle GetLastError
- REV-0520 — WinAPI 모듈 함수 사전: LoadLibraryEx FreeLibrary GetModuleHandle
- REV-0130 — IsDebuggerPresent 안티디버깅 식별

## 출처/검증
- `CreateMutexW`/`CreateEventW`의 함수 시그니처, 인자 순서, `ERROR_ALREADY_EXISTS`(183) 동작은 Microsoft Win32 API(동기화 객체) 공식 문서 기준이다.
- x64 호출 규약(`RCX`/`RDX`/`R8`)은 Microsoft x64 소프트웨어 규약 공식 문서 기준이다.
- 위 미니 예제의 주소와 이름 문자열은 설명을 위해 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
