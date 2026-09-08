---
id: REV-0534
title: "NtSetInformationThread ThreadHideFromDebugger 기법"
slug: "rev-0534-ntsetinformationthread-threadhidefromdebugger"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["NtSetInformationThread", "ThreadHideFromDebugger", "0x11", "스레드 안티디버깅", "ntdll 스레드 은닉"]
aliases: ["ThreadHideFromDebugger 기법", "NtSetInformationThread 안티디버깅", "스레드 디버거 숨기기", "쓰레드 하이드 프롬 디버거"]
symptom_keywords: ["NtSetInformationThread 호출 뒤 디버거가 이벤트를 못 받음", "특정 스레드부터 브레이크포인트가 안 걸림", "ThreadHideFromDebugger가 뭔지 모르겠음", "스레드 생성 후 갑자기 디버거 로그가 끊김"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`NtSetInformationThread`를 `ThreadInformationClass = ThreadHideFromDebugger`(값 `0x11`, 10진수 17)로 호출하면 현재 스레드가 커널 레벨에서 디버거의 디버그 이벤트 통지 대상에서 완전히 제외되어, 그 이후로 이 스레드에서 발생하는 예외나 종료 이벤트가 디버거에 전혀 보고되지 않게 되는 은밀하고 강력한 안티디버깅 기법이다.

## 언제 검색해야 하나
- `ntdll.dll`의 `NtSetInformationThread`를 호출하는 코드를 발견했고, 두 번째 인자가 `0x11`(17)인 것을 확인했을 때
- x64dbg로 디버깅하다가 어느 시점 이후 특정 스레드에서 건 브레이크포인트가 전혀 반응하지 않거나, 그 스레드가 크래시해도 디버거가 아무 알림 없이 그냥 지나칠 때
- 멀티스레드 프로그램에서 새로 생성된 스레드 하나만 디버거가 추적하지 못하는 이상한 현상을 마주쳤을 때
- 이 기법의 원리를 이해해서 왜 특정 스레드만 디버깅이 안 되는지 설명하고 싶을 때

## 핵심 개념

### 함수 시그니처
```c
NTSTATUS NtSetInformationThread(
  HANDLE          ThreadHandle,
  THREADINFOCLASS ThreadInformationClass,
  PVOID           ThreadInformation,
  ULONG           ThreadInformationLength
);
```
`NtQueryInformationProcess`(REV-0533)와 이름/구조가 비슷하지만, 이 함수는 "정보를 조회(Query)"하는 게 아니라 "정보를 설정(Set)"한다는 점이 다르다. `ThreadHandle`에는 대개 `GetCurrentThread()`(의사 핸들, `-2`)가 넘어가 자기 자신의 스레드를 대상으로 한다.

### ThreadHideFromDebugger의 동작
`ThreadInformationClass`에 `ThreadHideFromDebugger`(`0x11`)를 지정하면, 세 번째/네 번째 인자(`ThreadInformation`, `ThreadInformationLength`)는 무시되고(둘 다 `0`/`NULL`을 넘겨도 됨) 커널이 해당 스레드 오브젝트 내부에 "이 스레드는 디버거에게 이벤트를 보고하지 않는다"는 플래그를 세팅한다. 이후 이 스레드에서:
- 예외가 발생해도 디버거의 예외 핸들러(`WaitForDebugEvent`)에 통지되지 않고, 마치 디버거가 아예 없는 것처럼 프로그램 자체의 예외 처리(SEH)로만 넘어간다.
- 소프트웨어 브레이크포인트(`int3`)를 심어도 디버거가 그 이벤트를 받지 못하므로, 사실상 그 스레드에는 브레이크포인트를 걸 수 없는 것과 같은 효과가 난다.
- 스레드가 종료돼도 `EXIT_THREAD_DEBUG_EVENT`가 디버거에 전달되지 않는다.

### 왜 이 기법이 특히 강력한가
`IsDebuggerPresent`나 `CheckRemoteDebuggerPresent`는 "지금 디버거가 있는가"를 확인만 하고 그 결과를 코드가 스스로 판단해야 하는 수동적 방식이지만, `ThreadHideFromDebugger`는 커널에게 "이 스레드에 대해서는 디버거 통지 자체를 끄라"고 지시하는 능동적 방식이다. 판단 로직을 우회당할 여지 자체가 없고, 오직 이 API 호출을 사전에 막거나 그 효과를 되돌리는 방법으로만 대응할 수 있다.

### 흔한 활용 패턴 — 새 스레드에서 실제 로직 실행
많은 실전 사례에서, 프로그램은 시작하자마자 `CreateThread`로 새 스레드를 만들고, 그 스레드의 시작 함수 첫 줄에서 곧바로 `NtSetInformationThread(GetCurrentThread(), ThreadHideFromDebugger, ...)`를 호출한다. 이렇게 하면 프로그램의 핵심 로직(시리얼 검증, 복호화 등)을 이 "숨겨진" 스레드 안에서 실행시켜, 디버거가 메인 스레드는 볼 수 있어도 실제 중요한 코드가 도는 스레드는 완전히 놓치게 만든다.

### 우회 개념(간략)
이 기법 자체를 무력화하려면 다음 중 하나가 필요하다.
- `NtSetInformationThread` 호출을 후킹해, `ThreadInformationClass`가 `0x11`이면 아무 일도 하지 않고 바로 `STATUS_SUCCESS`만 반환하도록 가로채기(ScyllaHide 같은 플러그인이 이 항목을 지원하는 경우가 많다).
- 이 호출에 브레이크포인트를 걸어두고, 호출될 때마다 `ThreadInformationClass` 값을 다른 값(예: 무해한 `ThreadQuerySetWin32StartAddress` 같은 값)으로 바꿔치기해 실제 효과가 발생하지 않도록 패치.
- TitanHide처럼 커널 드라이버 레벨에서 이 플래그의 효과 자체를 무시하도록 만드는 도구를 사용.

수동 패치든 플러그인이든, 핵심은 "이 API 호출이 실제 커널 상태를 바꾸기 전에 가로채야 한다"는 점이며, 이미 플래그가 세팅된 이후에는 그 스레드에 대한 디버깅 관찰이 정상적으로 복구되지 않는 경우가 많으므로 사전 차단이 중요하다.

### 스레드 목록에서 사라지지는 않음
이 기법은 어디까지나 "디버그 이벤트 통지"를 차단하는 것이며, 스레드 자체가 프로세스에서 사라지거나 숨겨지는 것은 아니다. x64dbg의 Threads 창에는 여전히 해당 스레드가 목록에 나타나므로, 스레드 목록과 실제 디버그 이벤트 수신 여부는 별개로 판단해야 한다.

## 화면/코드에서 보이는 징후
- `ntdll.dll`에서 `NtSetInformationThread`를 동적으로 `GetProcAddress`로 얻어오는 코드가 있음.
- 호출 직전 두 번째 인자에 `11h`(17)가 채워짐.
- 대개 `CreateThread`로 만든 새 스레드의 시작 루틴 맨 앞부분에서 이 호출이 등장한다.
- x64dbg에서 특정 스레드가 생성된 직후부터 그 스레드에 건 브레이크포인트가 전혀 히트하지 않거나, Threads 창에서 그 스레드의 상태를 추적하는 로그가 갑자기 끊김.

## 가장 먼저 할 것
`CreateThread` 호출 이후 새로 생성된 스레드의 시작 함수 코드를 먼저 살펴보고, 맨 앞부분에 `NtSetInformationThread` 호출과 상수 `0x11`이 있는지 확인한다. 있다면 이 스레드 안의 코드는 정상적인 방법으로는 디버깅 관찰이 어렵다는 것을 미리 인지하고 대응 전략(사전 후킹, ScyllaHide 등)을 준비한다.

## 단계별 절차

**1) CreateThread 호출 지점 확인**

IDA에서 `CreateThread`/`CreateRemoteThread`의 xref를 찾아, 새로 생성되는 스레드의 시작 주소(함수)를 파악한다.

**2) 시작 함수 앞부분 검사**

해당 함수 초입에서 `NtSetInformationThread` 호출과 두 번째 인자 값을 확인한다.

**3) 값이 0x11이면 사전 대응 준비**

`ThreadInformationClass`가 `0x11`(`ThreadHideFromDebugger`)이면, 이 호출이 실행되기 **전에** 미리 브레이크포인트를 걸어 대응해야 한다는 것을 기록해둔다.

**4) x64dbg에서 사전 브레이크포인트 설정**

```text
bp ntdll.NtSetInformationThread
run
; RDX(두 번째 인자) 값이 0x11인지 확인
```

**5) 값이 0x11이면 우회 적용**

호출 직전 `RDX`(x86은 두 번째 스택 인자) 값을 다른 무해한 값(예: 존재하지만 부작용이 없는 `ThreadInformationClass`)으로 바꾸거나, 함수 진입 직후 강제로 `ret`(레지스터에 `STATUS_SUCCESS` 설정 후 즉시 반환)시켜 실제 커널 호출이 일어나지 않도록 만든다.

**6) 플러그인 활용**

수동 패치가 번거롭다면 ScyllaHide의 `NtSetInformationThread` 관련 옵션을 활성화해 자동으로 처리되도록 한다.

**7) 효과 검증**

우회 적용 후 해당 스레드 안에 새 브레이크포인트를 걸어 정상적으로 히트하는지 확인한다.

## 명령어/단축키
- IDA: `Alt+T`로 `"NtSetInformationThread"` 검색, `CreateThread` xref 확인
- x64dbg: `bp ntdll.NtSetInformationThread`, Registers 창에서 `RDX` 확인, `Ctrl+F9`로 실행 후 반환값 확인
- x64dbg: `Plugins > ScyllaHide > Settings`에서 스레드 은닉 관련 우회 옵션 확인

## 출력 해석
- 함수의 `NTSTATUS` 반환값이 `STATUS_SUCCESS`(`0`)이면 호출이 성공적으로 적용된 것이며, 이후 그 스레드는 디버그 이벤트 보고 대상에서 제외된다.
- 이 호출 이후 해당 스레드에서 건 브레이크포인트가 전혀 반응하지 않는다면, 정상적으로 이 기법이 적용됐다는 신호이며 코드 버그가 아니다.
- 우회를 적용한 뒤에도 여전히 브레이크포인트가 안 걸린다면, 이 호출이 여러 번(다른 스레드에서도 반복) 일어나고 있어 일부만 막혔을 가능성을 의심한다.

## 흔한 실수
- 이 기법이 적용된 스레드에서 디버거가 아무것도 못 보는 것을 "디버거가 고장났다"거나 "x64dbg 버그"로 오해하는 것 — 실제로는 의도된 안티디버깅 동작이다.
- 이미 `ThreadHideFromDebugger`가 적용된 **이후에** 우회를 시도하는 것 — 이 플래그는 세팅된 후에는 일반적인 방법으로 되돌리기 어려우므로, 반드시 호출이 일어나기 전에 가로채야 한다.
- `NtQueryInformationProcess`(REV-0533)와 이름이 비슷해서 같은 함수로 착각하는 것 — 하나는 프로세스 정보 조회(Query), 다른 하나는 스레드 정보 설정(Set)으로 완전히 다른 함수다.
- 스레드가 Threads 창 목록에서 사라진다고 착각하는 것 — 스레드 자체는 계속 보이며, 디버그 이벤트만 차단된다.

## 막혔을 때 다음 체크
- 비슷한 이름의 프로세스 레벨 정보 조회 API가 궁금하다면 → REV-0533 NtQueryInformationProcess로 하는 안티디버깅
- 이 기법과 함께 쓰이는 다른 안티디버깅 기법 전체 분류가 궁금하다면 → REV-0529 Windows 안티디버깅 기법 종류 빠른 참조표
- 출력 인자/호출 자체를 가로채는 우회의 기본형이 궁금하다면 → REV-0532 CheckRemoteDebuggerPresent 우회 실습 개념
- x64dbg의 스레드별 브레이크포인트/추적 개념이 낯설다면 → REV-0127 x64dbg로 EXE 첫 분석 시작

## 미니 예제
```asm
; 새 스레드 시작 함수의 첫 부분
ThreadProc:
  sub  rsp, 0x28
  call GetCurrentThread          ; rax = -2 (의사 핸들)
  mov  rcx, rax
  mov  edx, 0x11                 ; ThreadHideFromDebugger
  xor  r8, r8                    ; ThreadInformation = NULL
  xor  r9d, r9d                  ; ThreadInformationLength = 0
  call NtSetInformationThread
  ; 이 지점 이후부터 이 스레드는 디버거에게 보이지 않는 예외/종료 이벤트를 가짐
  add  rsp, 0x28
  ; ... 실제 핵심 로직 계속 ...
```

## 관련 글
- REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표
- REV-0532 — CheckRemoteDebuggerPresent 우회 실습 개념
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- `NtSetInformationThread`와 `ThreadHideFromDebugger`(`0x11`)의 동작은 마이크로소프트가 완전히 공개 문서화하지 않은 Native API 영역에 속하며, `winternl.h`/리버싱 커뮤니티에서 널리 검증되고 통용되는 값과 동작 설명을 기준으로 정리했다(2026-09-08 확인). ScyllaHide/TitanHide 등의 대응 도구 개념은 해당 오픈소스 프로젝트의 공개 설명을 참고했다.
