---
id: REV-0607
title: "하드웨어 브레이크포인트가 갑자기 사라질 때"
slug: "rev-0607-hardware-breakpoint-disappears"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, IDA, "ScyllaHide"]
keywords: ["DR0", "DR1", "DR2", "DR3", "DR7", "GetThreadContext", "SetThreadContext", "CONTEXT", "하드웨어 브레이크포인트"]
aliases: ["HW BP가 안 걸림", "디버그 레지스터 초기화", "브레이크포인트 무력화 우회", "DR7 초기화 탐지"]
symptom_keywords: ["방금 건 하드웨어 브레이크포인트가 없어졌다", "HW BP가 걸리다가 어느 순간부터 안 걸린다", "DR7이 0으로 리셋된다", "GetThreadContext SetThreadContext를 호출한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
대상 프로그램이 `GetThreadContext`/`SetThreadContext`로 자기 자신의 디버그 레지스터(`Dr0`~`Dr7`)를 직접 읽고 지우는 안티디버깅 코드를 실행했기 때문에 벌어지는 일이므로, 이 두 API의 호출 지점을 찾아 무력화하거나 x64dbg의 ScyllaHide 플러그인으로 컨텍스트 조작을 가로채면 하드웨어 브레이크포인트가 다시 유지된다.

## 언제 검색해야 하나
- x64dbg에서 하드웨어 브레이크포인트(`Set Hardware Breakpoint`)를 걸었는데, 특정 지점을 지나고 나면 어느 순간 브레이크포인트 목록(`Breakpoints` 탭)에서 체크 표시가 사라지거나 걸리지 않을 때
- 소프트웨어 브레이크포인트(`INT3`)는 잘 걸리는데 유독 하드웨어 브레이크포인트만 무력화되는 것처럼 보일 때
- Import 목록에 `GetThreadContext`, `SetThreadContext`가 있고, 이 둘이 함께 호출되는 패턴이 보일 때

## 핵심 개념
x86/x64 CPU는 실행 중 특정 메모리 주소에 접근하거나 실행할 때 하드웨어적으로 예외를 발생시키는 **디버그 레지스터** `DR0`~`DR7`을 제공한다.

- `DR0`~`DR3`: 감시할 최대 4개 주소를 저장한다.
- `DR6`: 어떤 조건이 실제로 걸렸는지(상태) 표시한다.
- `DR7`: 각 `DRn`을 활성화할지, 어떤 조건(실행/쓰기/읽기-쓰기)과 크기로 감시할지를 제어한다.

x64dbg 같은 디버거가 "하드웨어 브레이크포인트"를 설정한다는 것은, 대상 스레드의 `CONTEXT` 구조체 안의 `Dr0`~`Dr7` 필드를 원하는 값으로 채운 뒤 `SetThreadContext(HANDLE hThread, const CONTEXT *lpContext);`를 호출해 실제 CPU 레지스터에 반영하는 것이다.

문제는 **대상 프로그램 스스로도 자신의 스레드 컨텍스트를 조작할 수 있다**는 점이다. 다음 두 API가 이 용도로 쓰인다.

- `BOOL GetThreadContext(HANDLE hThread, LPCONTEXT lpContext);` — 지정한 스레드(대개 `GetCurrentThread()`)의 레지스터 상태를 읽어온다. `CONTEXT` 구조체에는 `Dr0`~`Dr7` 필드가 그대로 포함되어 있다.
- `BOOL SetThreadContext(HANDLE hThread, const CONTEXT *lpContext);` — 읽어온 `CONTEXT`를 수정해서 다시 써넣는다.

안티디버깅 코드는 다음 두 가지 방식 중 하나로 이 기능을 악용한다.

1. **탐지형**: `GetThreadContext`로 `Dr0`~`Dr3`를 읽어서 값이 0이 아니면(=누군가 하드웨어 브레이크포인트를 걸어놓았다는 뜻) 디버거가 있다고 판단한다.
2. **무력화형**: `GetThreadContext`로 읽은 뒤 `Dr0`~`Dr7`을 강제로 전부 0으로 만들고 `SetThreadContext`로 다시 써넣어, 디버거가 걸어놓은 하드웨어 브레이크포인트를 실행 중간에 지워버린다.

디버거가 이 API 호출을 별도로 가로채지 않으면, 대상 프로세스가 자신의 컨텍스트를 직접 덮어쓰는 것을 막을 방법이 없어서 "분명히 걸어놨는데 사라졌다"는 현상이 발생한다.

## 화면/코드에서 보이는 징후
- x64dbg의 `Breakpoints` 탭에서 방금 건 하드웨어 브레이크포인트 항목이 실행 후 사라지거나 비활성 표시로 바뀜
- IDA Imports 탭에 `GetThreadContext`와 `SetThreadContext`가 함께 존재
- 두 함수 xref를 따라가 보면 `CONTEXT` 구조체를 스택에 할당(`sizeof(CONTEXT)`만큼, x64 기준 약 1232바이트)하고, `ContextFlags`에 `CONTEXT_DEBUG_REGISTERS`(0x00010010, x64는 값이 다를 수 있음)를 설정하는 코드가 보임
- 해당 구조체에서 `Dr0`, `Dr1`, `Dr2`, `Dr3`, `Dr7`에 해당하는 오프셋에 `0`을 쓰는 코드가 있음

## 가장 먼저 할 것
1. IDA에서 Imports 탭을 열어 `GetThreadContext`/`SetThreadContext`가 있는지 확인한다.
2. 있으면 `SetThreadContext` 호출부에 x64dbg로 소프트웨어(`INT3`) 브레이크포인트를 건다. 하드웨어 브레이크포인트는 이 코드에 의해 지워지지만, 소프트웨어 브레이크포인트는 코드 바이트 자체를 바꾸는 방식이라 이 공격의 영향을 받지 않는다.
3. 이 API가 호출되기 전에 미리 실행을 멈춰서, 어떤 스레드/어떤 시점에 컨텍스트를 조작하는지 확인한다.

## 단계별 절차
**1) 소프트웨어 브레이크포인트로 먼저 잡기**
- 하드웨어 브레이크포인트 대신 우선 `SetThreadContext` 함수 시작 주소에 일반 `INT3` 브레이크포인트(`F2`)를 건다. 이 브레이크는 코드 자체를 `0xCC`로 패치하는 방식이라 대상이 컨텍스트를 조작해도 사라지지 않는다.
- 브레이크가 걸리면 인자로 전달된 `CONTEXT` 포인터(x64는 `RDX`)를 덤프 창에서 확인해, `Dr7` 필드 값이 실제로 0으로 설정되려는 참인지 확인한다.

**2) 호출 자체를 무력화**
- `SetThreadContext` 함수 진입 직후 `RET`으로 바로 반환하도록 패치하거나, 호출 이전의 `CALL SetThreadContext` 명령어를 `NOP`으로 채워서 아예 호출되지 않게 만든다. 반환값이 필요한 코드라면 `MOV EAX, 1`(성공으로 위장) 후 `RET`으로 바꾼다.

**3) ScyllaHide로 재사용 가능하게 처리**
- x64dbg에 ScyllaHide 플러그인을 설치하면 `GetThreadContext`/`SetThreadContext` 후킹 옵션이 있어, 대상이 디버그 레지스터를 읽거나 쓰려고 할 때 디버거가 실제 값 대신 "깨끗한" 값을 보여주거나 디버거의 하드웨어 브레이크포인트 설정을 보존해준다. 매번 수동 패치할 필요 없이 옵션만 켜면 된다.

**4) 대안: 소프트웨어 브레이크포인트/메모리 브레이크포인트로 대체**
- 특정 지점에서 계속 하드웨어 브레이크포인트가 지워진다면, 굳이 하드웨어 방식을 고집하지 말고 해당 주소에 일반 `INT3` 브레이크포인트를 걸거나, 데이터 접근을 감시해야 하는 상황이면 메모리 브레이크포인트(페이지 속성을 이용한 감시)로 대체하는 것도 실용적인 방법이다.

## 명령어/단축키
- x64dbg: `F2`(소프트웨어 브레이크포인트 토글), 우클릭 → `Breakpoint > Hardware, Access/Write/Execute`(하드웨어 브레이크포인트), `Breakpoints` 탭에서 상태 확인
- IDA: `X`(교차 참조), Imports 탭에서 함수 검색
- ScyllaHide: x64dbg 플러그인 메뉴 → 옵션에서 컨텍스트 관련 후킹 활성화

## 출력 해석
- `SetThreadContext` 호출 시 인자로 넘어온 `CONTEXT` 구조체의 `Dr7` 필드가 `0x00000000`이면, 이 호출이 디버그 레지스터를 초기화하려는 시도임을 의미한다.
- `ContextFlags`에 `CONTEXT_DEBUG_REGISTERS` 플래그가 켜져 있지 않다면 이 호출은 디버그 레지스터와 무관한 다른 목적(예: 일반적인 예외 처리 후 컨텍스트 복원)일 수 있으므로 섣불리 패치하지 않는다.

## 흔한 실수
- 하드웨어 브레이크포인트가 사라지는 원인을 무조건 "디버거 버그"로 오해하고 재부팅/재설치를 반복하는 것. 실제로는 대상 코드가 의도적으로 지우는 경우가 많다.
- `SetThreadContext` 호출을 통째로 무력화했더니, 컨텍스트 조작이 안티디버깅이 아니라 정상적인 예외 처리 루틴(SEH 복구 등)의 일부여서 프로그램이 오작동하는 경우가 있다. 반드시 xref로 이 호출의 전체 맥락(어떤 함수 안에서 쓰이는지)을 먼저 확인해야 한다.
- 소프트웨어 브레이크포인트도 스캔당할 수 있다는 사실을 잊는 것. 코드 메모리를 읽어서 `0xCC` 바이트를 찾는 별도의 검사가 병행될 수 있으므로, 하나를 우회했다고 끝난 게 아니라 계속 확인이 필요하다.

## 막혔을 때 다음 체크
- 컨텍스트 조작이 아니라 예외 처리 중에 벌어지는 것 같다면 → REV-0608(RIP가 예상 못한 예외 핸들러로 튈 때)을 확인한다.
- SEH 체인 자체를 이용한 안티디버깅이 의심된다면 → REV-0134(SEH와 예외 기반 제어 흐름 기초)를 확인한다.
- 창 클래스명/`IsDebuggerPresent` 등 다른 탐지도 함께 걸린다면 → REV-0606, REV-0130을 확인한다.

## 미니 예제
IDA에서 다음과 같은 패턴을 확인했다고 하자.

```c
CONTEXT ctx;
ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
GetThreadContext(GetCurrentThread(), &ctx);
ctx.Dr0 = 0;
ctx.Dr1 = 0;
ctx.Dr2 = 0;
ctx.Dr3 = 0;
ctx.Dr7 = 0;
SetThreadContext(GetCurrentThread(), &ctx);
```

x64dbg로 `main` 함수 앞부분에 `INT3` 브레이크를 먼저 걸어 실행을 멈춘 뒤, `SetThreadContext`에도 `INT3` 브레이크를 걸고 원하는 실제 하드웨어 브레이크포인트는 이 코드 이후 지점에 다시 걸어주면 지워지지 않는다. 근본적으로는 이 함수 자체를 패치해서 항상 `RET`만 하도록 만드는 것이 가장 간단하다.

## 관련 글
- REV-0606 — 디버거 창 제목/클래스명 때문에 탐지당할 때 대응
- REV-0608 — RIP가 예상 못한 예외 핸들러로 튈 때
- REV-0134 — SEH와 예외 기반 제어 흐름 기초

## 출처/검증
- `Dr0`~`Dr7` 디버그 레지스터의 역할과 `CONTEXT` 구조체를 통한 `GetThreadContext`/`SetThreadContext` 접근 방식은 x86 디버그 레지스터 관련 공개 기술 문서 및 Windows 디버깅 관련 자료 기준이다.
- `GetThreadContext`/`SetThreadContext`를 악용해 대상 프로세스가 자신의 하드웨어 브레이크포인트를 스스로 읽거나 지우는 안티디버깅 기법은 다수의 공개 안티디버깅 기법 정리 자료(예: LingSec "Hardware breakpoints and exceptions on Windows")에서 확인되는 일반적인 패턴이다.
- ScyllaHide가 스레드 컨텍스트 관련 API를 후킹해 디버그 레지스터 은닉/보존 기능을 제공한다는 점은 ScyllaHide 공식 저장소(x64dbg/ScyllaHide) 문서 기준이다(2026-09-08 확인).
