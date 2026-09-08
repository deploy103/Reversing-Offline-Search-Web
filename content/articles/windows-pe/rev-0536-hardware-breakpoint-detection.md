---
id: REV-0536
title: "하드웨어 브레이크포인트(DR 레지스터) 탐지 기법"
slug: "rev-0536-hardware-breakpoint-detection"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["DR0", "DR1", "DR2", "DR3", "DR6", "DR7", "GetThreadContext", "SetThreadContext", "CONTEXT_DEBUG_REGISTERS", "하드웨어 브레이크포인트", "디버그 레지스터", "ScyllaHide"]
aliases: ["디버그 레지스터 탐지", "DR 레지스터 체크", "Hardware Breakpoint Detection", "하드웨어 BP 탐지", "Dr7 검사"]
symptom_keywords: ["GetThreadContext 호출 뒤에 이상한 분기가 있다", "x64dbg에서 하드웨어 브레이크포인트를 걸면 프로그램이 조용히 종료된다", "CONTEXT_DEBUG_REGISTERS 상수가 코드에 보인다", "Dr7 값을 검사하는 루프가 있다", "b 명령으로 하드웨어 브레이크포인트를 걸었더니 감지당했다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
하드웨어 브레이크포인트는 CPU의 디버그 레지스터(DR0~DR3에 주소, DR7에 활성화 플래그)에 저장되기 때문에 코드 자체에는 아무 흔적도 남기지 않지만, `GetThreadContext`로 자기 자신의 `CONTEXT` 구조체를 읽어서 DR0~DR3나 DR7이 0이 아닌지 검사하는 것만으로 "누군가 나에게 하드웨어 브레이크포인트를 걸어뒀다"는 사실을 알아낼 수 있다.

## 언제 검색해야 하나
- x64dbg에서 `bp`(소프트웨어 BP) 대신 `ba`(Break on Access, 하드웨어 브레이크포인트)로 걸었을 때만 프로그램이 이상하게 종료되거나 다른 분기를 탈 때
- 코드에서 `GetThreadContext`를 호출하고 그 결과 버퍼에서 오프셋 `0x04`(x86) 또는 `0x30`(x64) 부근을 읽는 패턴을 발견했을 때 — 이 오프셋들이 각각 `CONTEXT.Dr0`, `CONTEXT.Dr7` 위치인지 확인하고 싶을 때
- Import Table에 `GetThreadContext`는 있는데 `SetContextThread`나 `IsDebuggerPresent`는 안 보여서 어떤 안티디버깅인지 헷갈릴 때
- ScyllaHide 같은 플러그인이 왜 "하드웨어 브레이크포인트 숨기기" 옵션을 제공하는지 원리를 알고 싶을 때

## 핵심 개념

### 하드웨어 브레이크포인트란
x86/x64 CPU는 소프트웨어 브레이크포인트(코드에 `0xCC` 바이트를 심는 방식, REV-0537 참고)와 별개로, **디버그 레지스터**라는 전용 레지스터 8개(DR0~DR7, DR4·DR5는 예약됨)를 이용한 하드웨어 브레이크포인트 기능을 제공한다.
- `DR0`~`DR3`: 감시할 메모리 주소 4개까지 저장.
- `DR6`: 상태 레지스터. 어느 브레이크포인트가 걸렸는지(B0~B3 비트), 싱글스텝인지(BS 비트, 14번째) 등을 기록.
- `DR7`: 제어 레지스터. `L0/G0`~`L3/G3` 비트로 DR0~DR3 각각을 활성화하는지, `RW0/LEN0` 등으로 실행/쓰기/읽기 감시 조건과 길이를 설정.

이 레지스터들은 메모리나 코드가 아니라 CPU 내부 상태이므로, 코드를 아무리 정적으로 뜯어봐도 하드웨어 브레이크포인트가 걸려 있는지 자체는 절대 알 수 없다 — 오직 실행 중에 이 레지스터 값을 직접 읽어야만 알 수 있다.

### 어떻게 읽는가: GetThreadContext
```c
CONTEXT ctx = { 0 };
ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
GetThreadContext(GetCurrentThread(), &ctx);
if (ctx.Dr0 || ctx.Dr1 || ctx.Dr2 || ctx.Dr3 || ctx.Dr7) {
    // 하드웨어 브레이크포인트가 걸려 있음 = 디버거가 붙어 있을 가능성 높음
}
```
`CONTEXT` 구조체는 `<winnt.h>`에 정의되어 있고, `ContextFlags`에 `CONTEXT_DEBUG_REGISTERS`(x86: `0x00010010`, x64: `0x00100010`)를 세팅해야만 커널이 `Dr0`~`Dr7` 필드를 채워준다. 이 플래그를 세팅하지 않으면 해당 필드는 채워지지 않으므로, 코드에서 이 상수가 등장하는지가 이 기법을 식별하는 첫 단서다.

### 왜 이 값이 디버거의 흔적인가
일반적으로 실행 중인 프로세스는 스스로 자기 자신에게 하드웨어 브레이크포인트를 걸 이유가 없다. `DR0`~`DR3`, `DR7`이 0이 아니라는 것은 외부의 디버거(x64dbg, WinDbg 등)가 `SetThreadContext`를 이용해 이 스레드의 디버그 레지스터에 감시 주소를 심어뒀다는 뜻이다. 즉 이 검사는 "디버거가 나를 감시하려고 남긴 흔적을 CPU 레지스터에서 직접 확인"하는 셈이다.

### 스레드마다 별도로 존재
디버그 레지스터는 스레드별 컨텍스트에 속한다. 멀티스레드 프로그램에서 어떤 스레드에는 하드웨어 브레이크포인트가 걸려 있고 다른 스레드에는 없을 수 있으므로, 정교한 안티디버깅 코드는 `CreateThread`로 만든 여러 스레드 각각에서 이 검사를 반복 수행하기도 한다.

### SetThreadContext로 직접 조작하는 변형
탐지뿐 아니라, 프로그램이 스스로 `SetThreadContext`를 호출해 자신의 `Dr7`을 강제로 0으로 초기화하는 방어적 코드를 넣는 경우도 있다. 이렇게 하면 디버거가 걸어둔 하드웨어 브레이크포인트가 프로그램 스스로에 의해 지워져버려서, 사용자가 분명히 브레이크포인트를 걸었는데도 실행이 멈추지 않는 현상이 발생한다. 이 경우 x64dbg에서 `ba`로 건 브레이크포인트가 어느 순간 `bl` 목록에서는 여전히 보이는데 실제로는 트리거되지 않는다면, 코드 어딘가에서 `SetThreadContext`로 `Dr7`을 초기화하고 있는지 의심해봐야 한다.

### NtGetContextThread / NtSetContextThread 우회
`GetThreadContext`/`SetThreadContext`는 내부적으로 `ntdll.dll`의 `NtGetContextThread`/`NtSetContextThread`를 호출하는 얇은 래퍼다. ScyllaHide 같은 안티안티디버깅 플러그인은 Win32 API 레벨이 아니라 이 ntdll 레벨 함수를 직접 후킹해서, 상위 계층에서 어떤 이름으로 호출하든(직접 `GetThreadContext`를 부르든, 동적으로 `GetProcAddress`로 얻어서 부르든) 일관되게 `Dr0`~`Dr7` 필드를 0으로 위장할 수 있다. 이런 방식이 왜 필요한지 이해해두면, 왜 Win32 API 레벨 후킹만으로는 우회가 불완전한지도 함께 이해할 수 있다.

## 화면/코드에서 보이는 징후
- Import Table에 `GetThreadContext`(때로는 `Wow64GetThreadContext`)가 있음.
- IDA 디스어셈블리에서 `CONTEXT_DEBUG_REGISTERS` 상수(`0x10010`)를 스택에 세팅한 뒤 `GetThreadContext` 호출.
```asm
mov  [rbp+ctx.ContextFlags], 100010h
lea  rdx, [rbp+ctx]
call GetCurrentThread
mov  rcx, rax
call GetThreadContext
cmp  qword ptr [rbp+ctx.Dr7], 0
jnz  detected
```
- x64dbg에서 `ba`(하드웨어 브레이크포인트)를 건 직후에만 프로그램이 다르게 동작하고, 같은 위치에 `bp`(소프트웨어 브레이크포인트)를 걸면 정상 동작하는 경우.

## 가장 먼저 할 것
`GetThreadContext` 호출 지점을 IDA에서 `X`(xref)로 모두 찾은 뒤, 각 호출 뒤 `ContextFlags`에 어떤 값이 들어가는지, 그리고 반환된 구조체의 어느 필드(Dr0~Dr7)를 비교하는지부터 확인한다. 이 값이 비교되는 방식(전부 0인지 검사 vs 특정 비트만 검사)에 따라 우회 방법이 달라진다.

## 단계별 절차
**1) 구조체 오프셋 확인**

x64 `CONTEXT` 구조체에서 `Dr0`은 오프셋 `0x48`, `Dr1`은 `0x50`, `Dr2`는 `0x58`, `Dr3`은 `0x60`, `Dr6`은 `0x68`, `Dr7`은 `0x70`이다(x86은 각각 `0x04`, `0x08`, `0x0C`, `0x10`, `0x14`, `0x18`). IDA에서 지역 변수를 `CONTEXT` 구조체로 타입 지정(`Y` 단축키로 타입 캐스팅 후 구조체 지정)하면 오프셋 대신 필드 이름이 바로 보여서 훨씬 읽기 쉬워진다.

**2) 검사 로직 따라가기**

`GetThreadContext` 호출 직후 `Dr0`~`Dr7` 중 어느 필드를 `cmp`/`test`하는지 확인한다. 전부 검사하는 코드도 있고, 실무에서 자주 걸리는 `Dr7`(활성화 플래그)만 검사하는 코드도 있다.

**3) x64dbg로 실습**

일부러 특정 주소에 하드웨어 브레이크포인트를 걸어보고(`ba r 1 <주소>`), 프로그램이 이를 감지하는지 관찰한다.
```text
ba x 1 00401234    ; 실행 시 감지되는 하드웨어 브레이크포인트 설정
run
```

**4) 우회 방법 이해**

가장 직접적인 우회는 `GetThreadContext` 호출 직후 반환값을 조작하는 것이 아니라, x64dbg에 ScyllaHide 플러그인을 붙여 `GetThreadContext`를 후킹해서 `Dr0`~`Dr7` 필드를 항상 0으로 리턴하게 만드는 것이다. 또는 IDA/x64dbg에서 하드웨어 브레이크포인트 대신 소프트웨어 브레이크포인트나 메모리 브레이크포인트로 바꿔서 이 특정 검사 자체를 피해가는 방법도 있다.

## 명령어/단축키
- x64dbg: `ba x 1 <주소>`(실행 하드웨어 BP), `ba r 1 <주소>`(읽기), `ba w 1 <주소>`(쓰기), `bl`(현재 걸린 브레이크포인트 목록)
- IDA: 지역 변수 우클릭 → `Convert to struct` 또는 `Y`(타입 지정)로 `CONTEXT` 구조체 적용
- x64dbg + ScyllaHide: 플러그인 메뉴 → `Options` → `Anti-Debug` 탭에서 `GetThreadContext` 관련 후킹 옵션 활성화

## 출력 해석
- `Dr7`이 0이면 하드웨어 브레이크포인트가 전혀 걸려 있지 않은 상태다. 8비트 중 `L0`~`L3`(짝수 비트 0,2,4,6) 중 하나라도 1이면 해당 `DRn`이 활성화된 것이다.
- `Dr0`~`Dr3`에 실제 메모리 주소 값이 들어 있다면, 그 주소들이 바로 디버거가 감시 중인 위치다. 이 주소를 역으로 확인하면 "디버거가 어디를 보고 있었는지"까지 추정할 수 있다.
- `Dr6`의 `B0`~`B3` 비트는 "방금 어떤 브레이크포인트가 실제로 걸렸는가"를 나타내며, 예외 핸들러 안에서 이 값을 읽어 어떤 조건이 트리거됐는지 판단하는 데 쓰인다.

## 흔한 실수
- `ContextFlags`를 세팅하지 않고 `GetThreadContext`를 호출한 뒤 `Dr7`을 읽으면 항상 쓰레기 값이거나 0으로 보인다는 점을 모르고 헷갈리는 것 — 반드시 `CONTEXT_DEBUG_REGISTERS` 플래그가 세팅됐는지부터 확인해야 한다.
- 이 검사 하나만 우회하면 안전하다고 생각하는 것 — 실전에서는 소프트웨어 브레이크포인트 탐지(REV-0537), `IsDebuggerPresent`(REV-0130) 등과 함께 쓰이는 경우가 많다.
- x86과 x64의 `CONTEXT` 구조체 오프셋이 다르다는 것을 잊고 한쪽 아키텍처에서 본 오프셋을 다른 쪽에 그대로 적용하는 것.
- 멀티스레드 프로그램에서 메인 스레드만 확인하고 다른 스레드의 검사 코드를 놓치는 것.

## 막혔을 때 다음 체크
- 소프트웨어 브레이크포인트(0xCC) 탐지 원리가 궁금하다면 → REV-0537 소프트웨어 브레이크포인트(0xCC) 탐지 기법
- `NtQueryInformationProcess` 기반의 더 저수준 안티디버깅이 궁금하다면 → REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- 이 검사를 우회하려는 관점에서 접근하고 싶다면 → REV-0531 — IsDebuggerPresent 우회 실습 개념과 한계
- x64dbg 브레이크포인트 종류 자체가 낯설다면 → REV-0127 x64dbg로 EXE 첫 분석 시작

## 미니 예제
```c
#include <windows.h>

BOOL CheckHardwareBreakpoints(void) {
    CONTEXT ctx = { 0 };
    ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    if (!GetThreadContext(GetCurrentThread(), &ctx))
        return FALSE;
    return (ctx.Dr0 != 0 || ctx.Dr1 != 0 ||
            ctx.Dr2 != 0 || ctx.Dr3 != 0 || ctx.Dr7 != 0);
}

int main(void) {
    if (CheckHardwareBreakpoints()) {
        ExitProcess(1);
    }
    printf("Enter flag: ");
    return 0;
}
```
디스어셈블리(x64)에서는 `GetThreadContext` 호출 뒤 `[rbp+ctx.Dr7]`(오프셋 `+0x70`)을 `cmp qword ptr ..., 0` 형태로 검사하고, 0이 아니면 곧바로 종료 분기로 빠지는 패턴이 전형적이다.

## 관련 글
- REV-0537 — 소프트웨어 브레이크포인트(0xCC) 탐지 기법
- REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- REV-0531 — IsDebuggerPresent 우회 실습 개념과 한계
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- `GetThreadContext`/`SetThreadContext` 함수와 `CONTEXT` 구조체(`Dr0`~`Dr7` 필드), `CONTEXT_DEBUG_REGISTERS` 플래그는 Microsoft 공식 문서(learn.microsoft.com, `winnt.h` 헤더 정의) 기준.
- x86 디버그 레지스터(DR0~DR7) 비트 구조는 Intel SDM(Software Developer's Manual) Volume 3B, Chapter "Debug, Branch Profile, TSC, and Resource Monitoring Features" 및 Wikipedia "X86 debug register" 항목 기준(2026-09-08 확인).
- 하드웨어 브레이크포인트 기반 안티디버깅 탐지 패턴은 다수의 공개 안티디버깅 예제 저장소(예: GitHub `Anti-Debug` 계열 프로젝트) 및 Check Point "Anti-Debug Tricks" 레퍼런스에서 공통적으로 확인되는 구현 방식을 정리한 것이다.
