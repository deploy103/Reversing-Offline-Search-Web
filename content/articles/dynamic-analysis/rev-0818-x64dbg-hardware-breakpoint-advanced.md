---
id: REV-0818
title: "x64dbg에서 하드웨어 브레이크포인트 활용하기"
slug: "rev-0818-x64dbg-hardware-breakpoint-advanced"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["x64dbg 하드웨어 브레이크포인트", "x64dbg ba 명령어", "x64dbg bph", "x64dbg SetHardwareBreakpoint", "x64dbg DR7", "x64dbg 디버그 레지스터", "x64dbg CSP 레지스터"]
aliases: ["x64dbg 하드웨어 중단점", "x64dbg ba 명령", "x64dbg DR0 DR1 DR2 DR3", "x64dbg 데이터 브레이크포인트"]
symptom_keywords: ["x64dbg 하드웨어 브레이크포인트 4개 제한", "x64dbg ba 명령어 문법 모름", "x64dbg 리턴 주소 감시하고 싶음", "x64dbg 안티디버깅에 하드웨어 브레이크포인트가 걸림", "x64dbg CSP 레지스터가 뭔지 모름"]
source_ids: ["SRC-X64DBG-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
x64dbg의 하드웨어 브레이크포인트(`ba`/`bph` 명령, `SetHardwareBreakpoint`)는 CPU 디버그 레지스터(`DR0`~`DR3`)를 직접 사용해 특정 주소의 실행(Execute)/쓰기(Write)/읽기+쓰기(ReadWrite)를 감시하는 방식으로, 최대 4개까지만 걸 수 있지만 메모리 브레이크포인트보다 훨씬 빠르고 정확한 바이트 단위 감시가 가능하다.

## 언제 검색해야 하나
- 스택의 리턴 주소나 특정 지역 변수 하나(1/2/4/8바이트)가 정확히 언제 바뀌는지 빠르게 잡고 싶을 때
- 반복 접근이 매우 잦은 위치를 감시해야 해서 메모리 브레이크포인트(REV-0817)의 속도 저하가 부담될 때
- `ba`, `bph`, `DR7` 같은 용어를 보긴 했는데 정확한 명령 문법과 크기/타입 지정 방법이 헷갈릴 때
- 안티디버깅 루틴이 하드웨어 브레이크포인트를 탐지해서(`GetThreadContext`로 `DR7` 검사) 왜 프로그램이 이상하게 종료되는지 이해하고 싶을 때
- 스택 포인터 기준 상대 주소(`CSP`, `SS:[ESP]` 등)에 브레이크포인트를 걸어야 할 때

## 핵심 개념

### 디버그 레지스터와 4개 슬롯 한계
x86/x64 CPU는 `DR0`, `DR1`, `DR2`, `DR3`라는 4개의 주소 레지스터와, 각 슬롯의 활성화 여부·타입·크기를 담는 `DR7` 제어 레지스터를 갖고 있다. x64dbg의 하드웨어 브레이크포인트는 이 레지스터를 직접 설정하므로, **동시에 최대 4개**까지만 걸 수 있다. 이미 4개를 다 썼다면 다섯 번째를 걸기 전에 기존 것 중 하나를 지우거나 비활성화해야 한다.

CPU가 직접 감시하기 때문에 매 명령어 실행마다 디버거가 개입할 필요가 없어, 메모리 브레이크포인트(예외 기반, REV-0817)보다 오버헤드가 훨씬 작다.

### 명령어 문법 — ba(SetHardwareBreakpoint)
```text
ba arg1[, arg2[, arg3]]
```
- `arg1` — 브레이크포인트를 걸 주소.
- `arg2`(선택) — 타입: `r`(read+write, 읽기/쓰기 모두 감시), `w`(write, 쓰기만), `x`(execute, 실행). **지정하지 않으면 `x`(실행)가 기본값**이다.
- `arg3`(선택) — 감시 크기: `1`, `2`, `4`, 또는 `8`(x64 전용). **지정하지 않으면 `1`바이트**가 기본값이다. 주소는 지정한 크기에 맞춰 정렬되어 있어야 한다(예: 4바이트 감시라면 주소가 4의 배수여야 함).

```text
ba 00404060, w, 4     ; 00404060부터 4바이트 쓰기 감시
ba csp, r, 8           ; 현재 스택 포인터(x64에서는 8바이트) 위치 읽기+쓰기 감시 — 리턴 주소 변조 탐지에 자주 씀
```

`x`(실행) 타입일 때는 소프트웨어 브레이크포인트(`bp`)와 결과적으로 비슷해 보이지만, 메모리에 `INT3`(0xCC) 바이트를 실제로 심지 않는다는 차이가 있다. 그래서 코드 자체를 체크섬 검사하는 안티디버깅/안티치트 코드에도 걸리지 않는 경우가 많다(다만 `DR7` 검사로는 여전히 탐지될 수 있다).

### CSP — 스택 포인터를 가리키는 가상 레지스터
`CSP`는 x64dbg가 제공하는 가상 레지스터로, x86에서는 `ESP`, x64에서는 `RSP`를 자동으로 가리킨다. 아키텍처에 상관없이 같은 스크립트/명령을 쓸 수 있어, 함수 진입 직후 `ba csp, r`를 걸어두면 그 함수의 **리턴 주소가 읽히거나(반환 시) 덮어써지는(스택 버퍼 오버플로우 등) 순간**을 아키텍처 구분 없이 잡을 수 있다.

### 관련 명령들
- `bphc`(`DeleteHardwareBreakpoint`/`bphwc`) — 하드웨어 브레이크포인트 삭제. 인자 생략 시 전체 삭제.
- `bphe`/`bphd`(`EnableHardwareBreakpoint`/`DisableHardwareBreakpoint`) — 활성화/비활성화. 슬롯은 그대로 두고 잠깐 꺼두고 싶을 때 유용하다(4개 한계 안에서 회전시켜 쓸 때 편리).
- `bphwcond`(`SetHardwareBreakpointCondition`) — 조건부 브레이크포인트(REV-0183)와 동일한 표현식 문법으로 하드웨어 브레이크포인트에도 조건을 걸 수 있다. 조건이 참(0이 아님)일 때만 실제로 멈춘다.
- `SetHardwareBreakpointCommand` — 하드웨어 브레이크포인트가 걸릴 때 자동 실행할 명령을 지정한다(명령 조건이 없으면 항상, 있으면 조건 만족 시).
- `bphwname`(`SetHardwareBreakpointName`) — 브레이크포인트에 이름을 붙여 Breakpoints 뷰와 로그에 표시되게 한다. 4개뿐이라 서로 헷갈리기 쉬우므로 이름을 붙여두면 관리가 편해진다.

### GUI로 걸기
CPU 탭 디스어셈블리 줄 우클릭 → `Breakpoint → Set Hardware on Execution`, 또는 레지스터/Dump 창에서 주소 우클릭 → `Breakpoint → Hardware, Access/Write/Execute`로 대화상자 없이 바로 걸 수 있다.

### 안티디버깅과의 관계
하드웨어 브레이크포인트는 `DR0`~`DR7` 레지스터 값 자체에 흔적이 남으므로, 프로그램이 `GetThreadContext`로 자기 자신의 컨텍스트를 읽어 `DR7`이 0이 아닌지 검사하면 탐지될 수 있다(REV-0536 참고). 이런 검사를 우회하려면 ScyllaHide 같은 안티안티디버깅 플러그인으로 `GetThreadContext` 반환값을 조작하는 방법이 흔히 쓰인다.

## 화면/코드에서 보이는 징후
- 하드웨어 브레이크포인트가 걸린 실행 지점은 소프트웨어 브레이크포인트와 똑같이 빨간 원으로 보이지만, Breakpoints 탭에서 타입이 `HW`(하드웨어)로 구분 표시된다.
- 4개를 초과해서 걸려고 하면 Log 탭에 실패 메시지가 남고 브레이크포인트가 설정되지 않는다.
- 데이터(코드가 아닌 변수/스택 위치)에 건 하드웨어 브레이크포인트는 CPU 탭이 아니라 그 값을 실제로 건드리는 명령어 실행 시점에 자동으로 멈춘다.
- 레지스터 탭에서 `DR0`~`DR7` 값을 직접 확인할 수 있는 x64dbg 뷰(또는 `dr0`~`dr7` 표현식)로 현재 어떤 슬롯이 어떤 주소를 감시 중인지 볼 수 있다.

## 가장 먼저 할 것
감시하려는 대상이 정확히 몇 바이트인지, 실행/쓰기/읽기 중 어떤 접근을 잡아야 하는지부터 정한다. 이미 4개 슬롯을 다 쓰고 있는지 Breakpoints 탭에서 미리 확인해, 필요하면 덜 중요한 기존 하드웨어 브레이크포인트를 `bphd`로 비활성화하거나 `bphc`로 정리한 뒤 새로 건다.

## 단계별 절차

**1) 감시 슬롯 여유 확인**

Breakpoints 탭에서 현재 하드웨어 브레이크포인트가 몇 개 걸려 있는지 확인한다.

**2) 명령어로 걸기**

```text
ba 00404060, w, 4
```

**3) GUI로 걸기(대안)**

Dump 창에서 주소 우클릭 → `Breakpoint → Hardware, Write`.

**4) 이름 붙이기(선택, 여러 개 관리할 때 유용)**

```text
bphwname 00404060, "score_write_guard"
```

**5) 실행 후 결과 확인**

`F9`로 실행하고, 멈추면 CPU 탭에서 어떤 명령어가 그 값을 건드렸는지 확인한다.

**6) 조건으로 좁히기(필요 시)**

```text
bphwcond 00404060, "eax > .1000"
```

**7) 정리**

```text
bphc 00404060
```

## 명령어/단축키
```text
ba 주소[, r/w/x][, 1/2/4/8]     ; 하드웨어 브레이크포인트 설정 (SetHardwareBreakpoint), 타입 기본값 x, 크기 기본값 1
bphc [주소]                      ; 삭제, 인자 없으면 전체 삭제
bphe [주소] / bphd [주소]        ; 활성화 / 비활성화
bphwcond 주소, "조건식"           ; 조건부로 만들기
bphwname 주소, "이름"             ; 브레이크포인트에 이름 붙이기
csp                               ; 현재 아키텍처의 스택 포인터를 가리키는 가상 레지스터(x86: ESP, x64: RSP)
```
우클릭 → `Breakpoint → Set Hardware on Execution` / `Hardware, Access/Write/Execute` : GUI로 동일하게 설정.

## 출력 해석
- 하드웨어 브레이크포인트에 멈추면 소프트웨어 브레이크포인트와 마찬가지로 CPU 탭이 열리고 정확히 그 명령어 실행 시점(실행 타입) 또는 접근 시점(읽기/쓰기 타입)에서 멈춘 상태를 보여준다.
- Log 탭에 "hardware breakpoint could not be set" 같은 메시지가 나오면 이미 4개 슬롯이 다 찬 상태이거나, 지정한 크기에 맞게 주소가 정렬되지 않은 경우다(예: 4바이트 감시인데 주소가 4의 배수가 아님).
- 조건부(`bphwcond`)를 걸었는데도 매번 멈춘다면 조건식 문법 오류로 "항상 참"처럼 취급되고 있을 가능성이 크므로 REV-0183의 표현식 문법을 다시 점검한다.

## 흔한 실수
- 4개 슬롯을 넘겨서 걸려다 실패하고도 왜 안 걸렸는지 모른 채 넘어가는 것 — Log 탭 메시지를 항상 확인하는 습관이 필요하다.
- 감시 크기를 지정하지 않아 기본값 1바이트로 걸려서, 정작 4/8바이트짜리 값의 상위 바이트가 바뀌는 걸 놓치는 것 — 값 크기에 맞는 `arg3`를 명시적으로 지정해야 한다.
- 타입을 지정하지 않아 기본값인 `x`(실행)로 걸려버려서, 데이터 감시를 의도했는데 엉뚱하게 코드 실행 감시가 되는 것 — 데이터 감시는 반드시 `r` 또는 `w`를 명시한다.
- 정렬되지 않은 주소에 큰 크기의 하드웨어 브레이크포인트를 걸려다 실패하는 것 — 4바이트 감시는 4의 배수 주소, 8바이트 감시는 8의 배수 주소에만 걸 수 있다.
- 32비트 프로세스인데 8바이트 크기를 지정하려는 것 — 8바이트는 x64 전용이다.
- 안티디버깅이 `DR7`을 검사하는 상황에서 하드웨어 브레이크포인트만 계속 시도하다가 매번 탐지당하는 것 — 이런 경우 메모리 브레이크포인트(REV-0817)나 ScyllaHide 같은 우회 도구 사용을 검토해야 한다.

## 막혔을 때 다음 체크
- 4개보다 많은 위치를, 또는 더 넓은 범위(페이지 단위)를 감시해야 한다면 → REV-0817 x64dbg에서 메모리 브레이크포인트(Access/Write) 활용하기를 참고한다.
- 조건식 문법 자체가 헷갈리면 → REV-0183 x64dbg 조건부 Breakpoint 기초를 먼저 본다.
- 하드웨어 브레이크포인트 탐지 원리(DR 레지스터 검사)가 궁금하면 → REV-0536 하드웨어 브레이크포인트(DR 레지스터) 탐지 기법을 참고한다.
- 기본적인 브레이크포인트 개념/소프트웨어 브레이크포인트가 먼저 궁금하다면 → REV-0178 x64dbg Breakpoint 설정과 삭제를 본다.

## 미니 예제
함수 진입 직후 리턴 주소가 스택 버퍼 오버플로우로 덮어써지는 순간을 잡는 상황이다.

```text
1. 취약 함수 진입 직전에 F2로 브레이크포인트, F9로 도달
2. F8(Step Over)로 프롤로그(push rbp 등)를 지나 스택 프레임이 만들어진 직후까지 진행
3. 커맨드 바에 ba csp, w, 8 입력 (현재 스택 포인터 위치의 리턴 주소, x64이므로 8바이트, 쓰기 감시)
4. F9로 계속 실행
5. 버퍼 오버플로우로 인해 리턴 주소가 실제로 덮어써지는 명령어에서 자동으로 멈춤
6. CPU 탭에서 그 명령어(예: rep movsb, mov [rsp+N], rax 등)를 확인해 오버플로우가 발생하는 정확한 지점을 특정
```

## 관련 글
- REV-0817 — x64dbg에서 메모리 브레이크포인트(Access/Write) 활용하기
- REV-0183 — x64dbg 조건부 Breakpoint 기초
- REV-0178 — x64dbg Breakpoint 설정과 삭제
- REV-0536 — 하드웨어 브레이크포인트(DR 레지스터) 탐지 기법

## 출처/검증
- `ba`/`bph`/`SetHardwareBreakpoint` 명령의 인자 구조(`arg1` 주소, `arg2` 타입 r/w/x 기본값 x, `arg3` 크기 1/2/4/8 기본값 1, x64 전용 8바이트, 주소 정렬 요구사항): 공식 문서 help.x64dbg.com의 `commands/breakpoint-control/SetHardwareBreakpoint.html` 기준(2026-09-09 조사).
- `bphc`(`DeleteHardwareBreakpoint`), `bphe`/`bphd`(`EnableHardwareBreakpoint`/`DisableHardwareBreakpoint`), `bphwcond`(`SetHardwareBreakpointCondition`), `bphwname`(`SetHardwareBreakpointName`), `SetHardwareBreakpointCommand` 명령과 각 설명: 같은 공식 문서 사이트의 `commands/breakpoint-control/` 및 `commands/conditional-breakpoint-control/` 섹션 기준.
- `CSP` 가상 레지스터(아키텍처별 ESP/RSP 자동 매핑)와 이를 활용한 리턴 주소 감시 예시: HackMag "Automating x64dbg" 튜토리얼의 스크립팅 예제에서 언급된 활용법을 참고해 정리.
- 하드웨어 브레이크포인트가 CPU 디버그 레지스터(DR0-DR7)를 사용하며 최대 4개 슬롯 제한이 있다는 점과 `GetThreadContext`를 통한 탐지 가능성: REV-0536 하드웨어 브레이크포인트(DR 레지스터) 탐지 기법 및 Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 3B(Debug Registers 챕터) 기준.
