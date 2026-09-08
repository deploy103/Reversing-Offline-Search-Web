---
id: REV-0625
title: "x64dbg Step Over가 CALL 내부로 계속 들어갈 때"
slug: "rev-0625-step-over-enters-call"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["Step Over", "F8", "F7", "CALL 내부 진입", "브레이크포인트 충돌", "예외 처리 설정"]
aliases: ["Step Over가 안 먹힘", "F8인데 함수 안으로 들어감", "step over 오작동"]
symptom_keywords: ["Step Over를 눌렀는데 함수 내부로 들어간다", "F8 눌렀는데 F7처럼 동작한다", "CALL을 건너뛰지 못한다", "step over 도중 갑자기 멈춘다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x64dbg의 Step Over(F8)는 `CALL` 명령을 "실행은 하되 함수 내부에서 멈추지 않고 리턴 지점까지 한 번에 진행"하는 기능인데, 그 함수 **내부에 브레이크포인트가 걸려 있거나 예외가 발생하면 Step Over도 그 지점에서 멈춘다.** 이건 오작동이 아니라 정상 동작이다. 원인은 대부분 (1) 콜백 안에 남아있는 브레이크포인트, (2) 안티디버깅/보호 코드가 발생시키는 예외, (3) F7과 F8을 착각해서 누른 것, 셋 중 하나다.

## 언제 검색해야 하나
- F8(Step Over)을 눌렀는데 CPU 창이 `CALL` 대상 함수 내부의 첫 명령어로 이동했을 때
- 반복적으로 F8을 누르는데 어느 순간부터 함수 안으로 들어가서 다시 나오는 게 번거로울 때
- Step Over 도중 상태 표시줄에 예외 관련 메시지가 뜨면서 멈출 때
- Options에서 예외 처리 설정을 건드린 적이 있는데 그 이후로 Step Over 동작이 달라진 것 같을 때

## 핵심 개념
Step Over(F8)의 내부 동작은 "그 `CALL` 명령의 바로 다음 주소(리턴 지점)에 임시 브레이크포인트를 걸고 Run 한다"는 것과 사실상 같다. 즉 Step Over도 결국 "실행 → 멈춤"의 반복이며, 다음 세 가지 중 하나라도 해당하면 리턴 지점에 도달하기 전에 먼저 멈춘다.

1. **콜백/헬퍼 함수 내부에 이미 걸려 있는 브레이크포인트**: 예를 들어 이전에 `bp GetProcAddress`를 걸어뒀는데, 지금 Step Over 하려는 `CALL`이 내부적으로 `GetProcAddress`를 호출한다면, Step Over는 리턴 지점까지 못 가고 그 브레이크포인트에서 먼저 멈춘다. 이는 정상이며, x64dbg가 "브레이크포인트 우선"으로 동작하기 때문이다.
2. **호출된 함수 내부에서 예외가 발생**: 안티디버깅 루틴이 의도적으로 예외(예: `0xC0000005` 액세스 위반, `0x80000003` `INT3`)를 발생시켜 SEH로 흐름을 바꾸는 경우, x64dbg의 예외 처리 설정("이 예외를 프로그램에 전달할지 여부")에 따라 첫 발생(first-chance) 시점에 디버거가 멈추도록 설정되어 있으면 Step Over 도중에도 그 예외 지점에서 멈춘다.
3. **F7과 F8 단축키 혼동**: x64dbg 기본 단축키는 F7이 Step Into(함수 내부로 들어감), F8이 Step Over(함수를 통째로 건너뜀)다. 습관적으로 다른 디버거(GDB 등)의 단축키를 쓰다가 실수로 F7을 누르고 "Step Over가 이상하다"고 착각하는 경우가 실제로 꽤 많다.
4. **자체 수정 코드(self-modifying code)**: 호출된 함수가 자기 자신의 코드를 실행 중에 변경하는 경우, 디스어셈블리 캐시가 갱신되면서 예기치 않은 곳에서 멈추는 것처럼 보일 수 있다.

## 화면/코드에서 보이는 징후
- Step Over를 눌렀는데 CPU 창 주소가 `CALL` 대상 함수의 시작 주소와 정확히 일치함(진짜로 함수 안으로 들어간 것)
- 상태 표시줄이나 Log 창에 "Breakpoint at ..." 또는 "Access violation" 같은 메시지가 함께 뜸
- Breakpoints 탭을 열어보면 지금 멈춘 그 주소(또는 그 함수 어딘가)에 이미 활성화된 브레이크포인트가 있음
- Options → Preferences → Exceptions 목록에 특정 예외 코드가 "Break on first chance"로 체크되어 있음

## 가장 먼저 할 것
지금 멈춘 위치가 정확히 어디인지 확인한다. `CALL` 대상 함수의 **첫 번째 명령어**에 정확히 멈췄다면 브레이크포인트나 F7 오조작을, 함수 **중간의 특정 지점**에 멈췄다면 그 지점에 걸린 브레이크포인트나 예외 발생을 의심한다.

## 단계별 절차
1. **단축키부터 확인**: Options → Preferences → Shortcuts(또는 하단 툴바 아이콘에 마우스 오버)에서 F7과 F8이 각각 Step Into/Step Over에 정확히 매핑되어 있는지 확인한다. 헷갈린다면 툴바의 "Step Over" 아이콘을 직접 클릭해서 확인해본다.
2. **Breakpoints 탭 확인**: 멈춘 주소 혹은 그 함수 범위 안에 활성 브레이크포인트가 있는지 확인한다. 있다면 일시적으로 Disable하고 다시 Step Over를 시도한다.
3. **Log 창/상태 표시줄로 원인 메시지 확인**: 멈춘 직후 Log 창에 어떤 이벤트로 멈췄는지 메시지가 남는 경우가 많다("Breakpoint", "Exception" 등의 키워드를 확인한다).
4. **예외 설정 확인**: Options → Preferences → Exceptions 탭에서 특정 예외 코드가 체크되어 있으면, 그 예외가 발생할 때마다 first-chance에서 멈추도록 설정된 것이다. 안티디버깅 우회를 위해 일부러 이렇게 설정해둔 게 아니라면, 필요 없는 예외 항목은 체크 해제하거나 "Ignore custom exceptions" 옵션을 활용해 예외를 프로그램에 그냥 전달하고 넘어가게 한다.
5. **의도적으로 브레이크포인트를 유지해야 한다면**: 콜백 내부 브레이크포인트를 지우고 싶지 않다면, Step Over 대신 **"Execute till return"**(Ctrl+F9, 현재 함수가 리턴할 때까지 실행)을 사용해 원하는 지점까지 강제로 진행시킨 뒤 다시 브레이크포인트를 활성화한다.
6. **자체 수정 코드 의심 시**: CPU 창을 우클릭 → "Analyse code" 또는 캐시를 새로고침하는 옵션으로 디스어셈블리를 재분석해보고, 실제 실행되는 바이트가 정적 분석 때와 다른지 Hex 덤프로 대조한다.

## 명령어/단축키
- x64dbg: F8(Step Over), F7(Step Into), Ctrl+F9(Execute till return), F9(Run)
- x64dbg: Options → Preferences → Shortcuts(단축키 확인/변경), Options → Preferences → Exceptions(예외 처리 설정)
- Breakpoints 탭: 개별 브레이크포인트 Enable/Disable

## 출력 해석
- 정확히 `CALL` 대상의 첫 명령어에서 멈췄고 Log에 별다른 메시지가 없다면, 십중팔구 F7을 누른 것이다.
- Log에 "Breakpoint reached"류의 메시지가 있다면 콜백 내부의 기존 브레이크포인트 때문이다.
- Log에 예외 코드(`0xC0000005` 등)가 찍혔다면 안티디버깅이나 SEH 기반 로직이 원인일 수 있으며, 이 경우 REV-0240(디버거에서 갑자기 종료될 때 체크리스트)의 안티디버깅 패턴도 함께 의심해봐야 한다.

## 흔한 실수
- 단축키를 확인하지 않고 "x64dbg 버그"라고 단정하는 것. 대부분 F7/F8 혼동이거나 기존 브레이크포인트 때문이다.
- 콜백 내부에 걸어둔 브레이크포인트의 존재를 잊어버리고, 왜 Step Over가 거기서 멈추는지 몰라 헤매는 것.
- 예외 처리 설정을 건드려놓고 원래 상태로 되돌리지 않아, 이후 다른 분석에서도 계속 예상치 못한 지점에서 멈추는 것.
- Step Over가 멈춘 이유를 확인하지 않고 무작정 F8을 계속 눌러 다음 예외/브레이크포인트까지 반복적으로 통과시키다가, 정작 중요한 멈춤 지점을 놓치는 것.

## 막혔을 때 다음 체크
- 그 브레이크포인트 자체가 아예 걸리지 않는 문제라면 → REV-0622(브레이크포인트를 걸었는데 한 번도 안 걸릴 때)를 확인한다.
- 예외 이후 프로그램이 아예 응답이 없어진다면 → REV-0618(특정 API 호출 이후 x64dbg가 응답이 없을 때)을 확인한다.
- Step Into와 Step Over의 기본 차이 자체가 헷갈린다면 → REV-0170(Step Into와 Step Over 차이)을 먼저 읽는다.

## 미니 예제
`CALL sub_402000`을 Step Over(F8)하려 했는데 CPU 창이 `sub_402000`의 첫 명령어로 이동했다. Breakpoints 탭을 확인하니 이전 세션에서 `bp sub_402050`(그 함수 중간 지점)을 걸어놓고 잊고 있었던 것이 아니라, 실제로는 상태 표시줄에 "Access violation reading location 0x00000000" 메시지가 남아 있었다. 이 함수는 `IsDebuggerPresent`를 우회하기 위해 일부러 널 포인터 역참조 예외를 발생시켜 디버거의 존재를 감지하는 안티디버깅 루틴이었다. Options → Preferences → Exceptions에서 `0xC0000005`를 "프로그램에 전달(pass to program)"하도록 설정을 확인하고, Ctrl+F9(Execute till return)로 함수를 완전히 빠져나온 뒤 분석을 이어갔다.

## 관련 글
- REV-0622 — 브레이크포인트를 걸었는데 한 번도 안 걸릴 때(x64dbg)
- REV-0618 — 특정 API 호출 이후 x64dbg가 응답이 없을 때
- REV-0170 — Step Into와 Step Over 차이

## 출처/검증
- x64dbg의 Step Over/Step Into 동작 방식(임시 브레이크포인트를 통한 리턴 지점 실행), 예외 처리 설정(Preferences → Exceptions)은 x64dbg 공식 문서 및 GitHub 위키 기준이다.
- 예외 코드 `0xC0000005`(`STATUS_ACCESS_VIOLATION`)의 의미는 Microsoft NTSTATUS 공식 문서 기준이다.
- 미니 예제의 구체적 시나리오는 설명을 위해 구성한 예시다(2026-09-08 기준 서술).
