---
id: REV-0815
title: "x64dbg Trace 기능으로 실행 흐름 기록하기"
slug: "rev-0815-x64dbg-trace-execution-flow"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["x64dbg Trace 탭", "x64dbg Trace Into", "x64dbg Trace Over", "x64dbg Conditional Tracing", "x64dbg trace coverage", "x64dbg TraceSetLogFile", "x64dbg 실행 흐름 기록"]
aliases: ["x64dbg 트레이스", "x64dbg 실행 기록", "x64dbg 조건부 트레이싱", "x64dbg trace log"]
symptom_keywords: ["x64dbg에서 어디를 실행했는지 나중에 다시 보고 싶음", "x64dbg 조건이 언제 처음 참이 되는지 모르겠음", "x64dbg F8을 수천 번 눌러야 하는 반복문", "x64dbg 코드 커버리지 확인하고 싶음", "x64dbg trace into until condition이 뭔지 모름"]
source_ids: ["SRC-X64DBG-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
x64dbg의 **Trace 탭**은 `Trace Into`/`Trace Over`(조건부 실행: `... until condition`)로 프로그램을 자동으로 여러 스텝 진행시키면서 지나간 명령어들을 기록해두는 기능으로, "정확히 어디서 멈춰야 할지 모르지만 넓은 구간을 훑으며 특정 조건이 참이 되는 순간이나 실행 경로 전체를 확인하고 싶을 때" 쓴다.

## 언제 검색해야 하나
- 반복문이 몇 번 도는지, 그 안에서 특정 값이 언제 원하는 상태가 되는지 코드를 눈으로 다 읽지 않고 알고 싶을 때
- "이 조건이 참이 될 때까지 자동으로 스텝 실행하고, 참이 되는 순간 멈춰라"는 동작이 필요할 때
- 실행된 명령어 전체 목록(어떤 주소를 몇 번 지나갔는지)을 남겨서 나중에 다시 살펴보고 싶을 때
- 언패킹된 코드가 실제로 실행되는 범위(코드 커버리지)를 눈으로 확인하고 싶을 때
- 조건부 브레이크포인트(REV-0816, REV-0183)만으로는 "그 조건이 어디서 처음 참이 되는지"조차 감이 안 잡힐 때

## 핵심 개념

### Trace Into vs Trace Over
x64dbg는 `Trace` 메뉴(또는 단축키)에서 두 가지 트레이스 실행을 제공한다.
- **Trace Into**(`Ctrl+Alt+F7`) — CALL을 만나면 그 안으로 들어가면서 한 스텝씩 계속 진행한다. 내부적으로 Step Into를 반복 실행하는 것과 같다.
- **Trace Over**(`Ctrl+Alt+F8`) — CALL을 만나면 안으로 들어가지 않고 넘어가면서 진행한다. Step Over를 반복 실행하는 것과 같다.

둘 다 "한 번 시작하면 조건이 만족되거나 최대 스텝 수에 도달할 때까지 자동으로 계속 진행"하는 것이 핵심이다. 사람이 F7/F8을 수백 번 누르는 대신, x64dbg가 내부적으로 그만큼 스텝을 반복해준다.

### 조건부 트레이싱 — 언제 멈출지 지정하기
`Trace into until condition` / `Trace over until condition`을 선택하면 대화상자가 뜨고 여기에 **Break condition**(조건부 브레이크포인트와 같은 표현식 문법, REV-0183 참고)을 입력할 수 있다. 이 조건이 참이 되는 순간 트레이스가 멈춘다. 조건을 비워두면 기본값(항상 거짓에 가까운 형태)이라 최대 스텝 수까지 계속 진행한다.

트레이스가 한 스텝 진행할 때마다 x64dbg는 다음을 순서대로 수행한다.
1. 로그 텍스트가 설정되어 있고 로그 조건이 참이면 → 로그를 기록한다.
2. 명령(커맨드) 텍스트가 설정되어 있고 명령 조건이 참이면 → 그 명령을 실행한다.
3. 위 처리 후 `$tracecondition`(중단 조건), `$tracelogcondition`(로그 조건) 같은 내부 변수를 스크립트에서 직접 조작해 중단 여부를 제어할 수도 있다.

Trace Over 중에는 CALL 안쪽으로 들어가지 않으므로, 그 안에서 조건이 참이 되어도 트레이스가 멈추지 않고 로그/기록도 남지 않는다는 점에 주의해야 한다 — 호출된 함수 내부까지 감시하려면 Trace Into를 써야 한다.

### 트레이스 기록(Trace Record)과 커버리지
트레이스가 진행되는 동안 x64dbg는 지나간 명령어를 **Trace 탭**(트레이스 뷰)에 기록하고, 동시에 디스어셈블리 창에 **커버리지 표시**(실행된 적 있는 줄을 색으로 구분)를 남긴다. 이는 수동으로 한 스텝씩 실행할 때도 동일하게 누적되며, "이 함수의 이 부분은 이번 실행에서 한 번도 안 지나갔다"는 것을 한눈에 파악하는 데 유용하다.

### 로그 포맷팅
로그 텍스트에는 x64dbg의 문자열 포매팅 문법을 쓸 수 있다. 예를 들어 지나간 모든 명령어의 주소와 디스어셈블리를 그대로 남기고 싶다면 다음 포맷을 로그 텍스트에 지정한다.

```text
{p:cip} {i:cip}
```

`{p:cip}`는 현재 명령어 주소를, `{i:cip}`는 그 주소의 디스어셈블리 텍스트를 의미한다. 이렇게 남긴 로그는 화면의 Log 탭에서 볼 수 있고, `TraceSetLogFile` 명령(또는 GUI의 로그 파일 지정 옵션)으로 파일에 그대로 저장해 나중에 텍스트 편집기나 스크립트로 분석할 수도 있다.

### Script 자동화, 조건부 브레이크포인트와의 역할 구분
- **조건부 브레이크포인트**(REV-0183, REV-0816): "정확히 이 주소에서, 이 조건일 때 멈춰라" — 멈출 위치를 이미 알고 있을 때.
- **Trace(조건부 트레이싱)**: "이 구간 전체를 훑으면서 조건이 언제 처음 참이 되는지 찾아라" — 멈출 위치를 모를 때, 혹은 지나간 경로 자체가 궁금할 때.
- **Script 탭**(REV-0814): "여러 단계에 걸친 임의의 절차(분기, 반복, 서브루틴 호출)를 프로그래밍하듯 자동화" — 트레이스보다 훨씬 자유도 높은 로직이 필요할 때.

셋은 서로 대체 관계가 아니라 상황에 맞게 골라 쓰는 도구다.

## 화면/코드에서 보이는 징후
- Trace를 시작하면 디버거가 멈추지 않고 짧은 시간 동안 빠르게 여러 스텝을 처리한 뒤, 조건 만족 또는 최대 스텝 도달 시 자동으로 멈춘다.
- Trace 탭에 실행된 명령어들이 순서대로 나열되어, 스크롤하며 지나온 경로를 되짚어볼 수 있다.
- 디스어셈블리 창에서 한 번이라도 실행된 줄은 다른 색(커버리지 표시)으로 구분된다.
- 조건 표현식에 문법 오류가 있으면 트레이스가 예상보다 훨씬 빨리(또는 즉시) 멈추거나, 반대로 조건이 절대 만족되지 않아 최대 스텝 수까지 다 채우고 멈춘다.

## 가장 먼저 할 것
Trace를 걸기 전에 "내가 멈추고 싶은 조건"을 표현식으로 먼저 적어본다(레지스터 값, 메모리 값, 몇 번째 히트인지 등). 그 다음 CALL 안쪽까지 봐야 하는지(Trace Into) 아니면 함수 내부는 무시해도 되는지(Trace Over)를 정해서 어느 쪽을 실행할지 고른다.

## 단계별 절차

**1) 시작 위치 확보**

먼저 원하는 시작 지점에 브레이크포인트를 걸고 `F9`로 그 지점까지 실행한다.

**2) 트레이스 종류 선택**

`Debug`(또는 `Trace`) 메뉴에서 `Trace into until condition`(호출 내부까지 감시) 또는 `Trace over until condition`(호출 내부는 건너뜀)을 선택한다.

**3) 중단 조건 입력**

대화상자의 Break condition에 조건부 브레이크포인트와 동일한 문법으로 조건을 입력한다.

```text
eax==0 && [esp]==0x1337
```

**4) 로그 조건/텍스트 채우기(선택)**

지나가는 값들을 전부 기록해두고 싶다면 Log condition은 `1`(항상 참)로 두고, Log text에 다음처럼 포맷을 지정한다.

```text
{p:cip} {i:cip}
```

**5) 실행 및 결과 확인**

트레이스를 시작하면 조건이 만족되는 순간 자동으로 멈춘다. 멈춘 시점의 레지스터/스택은 CPU 탭에서, 지나온 경로는 Trace 탭에서 확인한다.

**6) 필요하면 로그를 파일로 저장**

대량의 로그를 나중에 다시 분석하고 싶다면 `TraceSetLogFile` 명령이나 GUI의 로그 파일 지정 기능으로 파일 경로를 지정해 저장한다.

## 명령어/단축키
```text
Ctrl+Alt+F7   ; Trace Into (조건 없이 자동 반복)
Ctrl+Alt+F8   ; Trace Over
```
- `Trace → Trace into until condition` / `Trace over until condition` : 조건부 트레이싱 대화상자
- Break condition / Log condition / Log text / Command condition / Command text : 스텝마다 평가되는 4가지 항목(조건부 브레이크포인트와 동일한 문법)
- `$tracecondition`, `$tracelogcondition` : 스크립트/커맨드에서 직접 조작해 중단·로그 여부를 제어하는 내부 변수
- `TraceSetLogFile 경로` : 트레이스 로그를 파일로 저장

## 출력 해석
- 트레이스가 예상보다 훨씬 이른 스텝에서 멈췄다면, 조건식이 의도한 것보다 더 자주 참이 되고 있다는 뜻이다 — 조건에 `&&`로 제약을 더 추가해 좁혀야 한다.
- 트레이스가 최대 스텝 수를 다 채우고도 멈추지 않았다면, 조건이 아예 참이 될 수 없거나(오타/잘못된 비교), 감시하려는 코드 경로에 실제로는 도달하지 않고 있다는 뜻이다.
- Trace Over로 진행했는데 CALL 내부에서 벌어지는 일을 놓치고 있다고 의심되면, 같은 조건으로 Trace Into를 다시 시도해 내부까지 들여다봐야 한다.
- 로그 파일에 `{p:cip} {i:cip}` 포맷으로 남긴 결과는 사실상 "이 구간의 전체 실행 트레이스"이므로, 텍스트 편집기에서 특정 명령어(예: 특정 API 호출, 특정 주소)가 몇 번 등장하는지 검색해 반복 횟수나 최초/최후 등장 위치를 빠르게 파악할 수 있다.

## 흔한 실수
- Trace Over 중에 CALL 내부에서 조건이 참이 되기를 기대하는 것 — Trace Over는 호출된 함수 안에서는 조건 평가/로깅/중단을 하지 않는다. 내부까지 봐야 한다면 반드시 Trace Into를 써야 한다.
- Command condition/Command text 안에 `run`처럼 실행 상태 자체를 바꾸는 명령을 넣는 것 — 공식 문서에서도 이런 명령은 트레이싱 도중 불안정하게 동작할 수 있다고 명시하며, 대신 `$tracecondition` 변수 조작을 권장한다.
- 조건 없이(빈 조건으로) Trace Into를 큰 함수에서 시작해 사실상 프로그램 전체를 명령어 단위로 훑게 만들어 실행이 매우 느려지는 것 — 가능하면 브레이크포인트로 감시 범위를 먼저 좁힌 뒤 트레이스를 시작한다.
- 로그만 필요한데 Break condition에도 같은 조건을 넣어서 매 스텝마다 멈춰버려 트레이스의 자동 반복 이점을 잃는 것 — 로그만 원한다면 Break condition은 거짓에 가깝게, Log condition만 참이 되도록 분리해서 설정한다.
- Trace 탭에 쌓인 방대한 기록을 저장하지 않고 디버거를 재시작해서 기록을 날리는 것 — 중요한 트레이스는 미리 `TraceSetLogFile`로 파일에 남겨둔다.

## 막혔을 때 다음 체크
- 조건식 문법 자체가 헷갈리면 → REV-0183 x64dbg 조건부 Breakpoint 기초에서 표현식 문법을 먼저 확인한다.
- 트레이스보다 더 자유로운 절차(여러 단계의 분기/반복 로직)가 필요하다면 → REV-0814 x64dbg 스크립트(Script) 탭으로 자동화하기를 참고한다.
- 멈추지 않고 로그만 남기는 목적이라면 트레이스 대신 → REV-0816 x64dbg Conditional Log Breakpoint 활용하기가 더 간단할 수 있다.
- 기본적인 브레이크포인트 설정법이 헷갈린다면 → REV-0178 x64dbg Breakpoint 설정과 삭제를 먼저 본다.

## 미니 예제
반복문 안에서 카운터가 100이 되는 정확한 순간을 자동으로 찾는 상황이다.

```text
1. 반복문 진입 직전 주소에 F2로 브레이크포인트, F9로 실행해 도달
2. Trace 메뉴 → "Trace into until condition" 선택
3. Break condition에 ecx==.100 입력 (10진수 100, 앞에 . 필수)
4. Log condition은 1, Log text는 {p:cip} {i:cip} 로 설정해 지나간 경로도 함께 기록
5. 트레이스 시작 → ecx가 0부터 99까지 증가하는 동안 자동으로 스텝을 반복하며 로그를 남기다가, ecx==100이 되는 순간 자동으로 멈춤
6. Trace 탭에서 방금까지 지나온 명령어 목록을 스크롤하며 반복문 전체 흐름을 한 번에 검토
```

## 관련 글
- REV-0183 — x64dbg 조건부 Breakpoint 기초
- REV-0814 — x64dbg 스크립트(Script) 탭으로 자동화하기
- REV-0816 — x64dbg Conditional Log Breakpoint 활용하기
- REV-0178 — x64dbg Breakpoint 설정과 삭제
- REV-0182 — x64dbg Memory Map과 Module View

## 출처/검증
- `Trace Into`/`Trace Over` 단축키(`Ctrl+Alt+F7`/`Ctrl+Alt+F8`)와 CALL 내부 진입 여부 차이: 공식 문서 help.x64dbg.com 및 GitHub `x64dbg/docs`의 사용자 가이드 기준(2026-09-09 조사).
- 조건부 트레이싱의 동작 순서(로그 → 명령 → 중단 조건 평가), `$tracecondition`/`$tracelogcondition` 내부 변수, Trace Over 중 CALL 내부에서 로깅/중단이 발생하지 않는다는 점, Command condition에 `run` 계열 명령을 쓰지 말라는 경고: 공식 문서 help.x64dbg.com의 Conditional Tracing 페이지(`introduction/ConditionalTracing.html`) 및 GitHub `x64dbg/docs`의 `introduction/ConditionalTracing.md` 기준.
- 로그 포맷 `{p:cip} {i:cip}`(현재 명령어 주소/디스어셈블리 출력)와 `TraceSetLogFile` 명령: 같은 Conditional Tracing 공식 문서의 로깅 설명에 근거.
