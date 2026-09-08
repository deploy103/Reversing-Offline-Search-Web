---
id: REV-0166
title: "함수 Call Graph로 핵심 로직 좁히기"
slug: "rev-0166-call-graph-narrowing"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra, IDA]
keywords: ["Call Graph 분석", "IDA Function calls 그래프", "Ghidra Function Call Graph", "Function Call Trees", "Proximity browser", "함수 호출 관계 시각화"]
aliases: ["함수 호출 그래프", "콜그래프로 핵심 함수 찾기", "누가 누구를 부르는지 시각화"]
symptom_keywords: ["함수가 너무 많아서 구조 파악이 안 됨", "어디가 핵심 로직인지 감이 안 옴", "함수 호출 관계를 한눈에 보고 싶음", "IDA Ghidra 콜그래프 보는 법"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
함수 하나하나를 순서대로 읽는 대신, **함수 호출 관계를 그래프(노드-엣지)로 시각화**해서 "어디서 시작해서 어디로 갈라지는지"를 먼저 파악하면, 함수가 수십~수백 개인 바이너리에서도 몇 초 안에 핵심 로직이 몰려 있는 영역을 짐작할 수 있다.

## 언제 검색해야 하나
- REV-0163(문자열), REV-0164(Imports), REV-0165(상수)로도 뚜렷한 단서를 못 찾았을 때
- 함수가 너무 많고 서로 복잡하게 얽혀 있어서 어디서부터 읽어야 할지 감이 안 잡힐 때
- `main`에서 시작해 몇 단계를 거쳐야 실제 검증 로직에 도달하는지 미리 지도를 그려두고 싶을 때
- 특정 함수가 프로그램 전체에서 얼마나 "중심적인" 역할을 하는지(다른 함수들이 얼마나 이 함수를 호출하는지) 감을 잡고 싶을 때

## 핵심 개념
Call Graph(호출 그래프)는 함수를 노드(점)로, "A가 B를 호출한다"는 관계를 화살표(엣지)로 표현한 그림이다. 텍스트로 된 코드를 한 줄씩 읽는 대신 그림으로 전체 구조를 보면, 다음과 같은 것들이 시각적으로 바로 드러난다:

- **진입점에서 몇 단계 만에 어디로 퍼지는가**: `entry` → C 런타임 초기화 → `main` → 몇 개의 하위 함수로 갈라지는 구조를 한눈에 볼 수 있다.
- **허브(hub) 함수**: 여러 함수로부터 호출되는 유틸리티성 함수(예: 로깅, 메모리 할당 래퍼)는 들어오는 화살표가 많다. 반대로 검증 로직처럼 특정 지점에서만 호출되는 함수는 들어오는 화살표가 적다.
- **말단(leaf) 함수**: 다른 함수를 거의 호출하지 않고 자기 안에서 계산만 하는 함수는 나가는 화살표가 적다. 해시/체크섬 계산 함수가 이런 형태인 경우가 많다.
- **고립된 큰 서브그래프**: 프로그램의 나머지 부분과 거의 연결이 적은, 자기들끼리만 촘촘히 얽힌 함수 무리가 있다면 그 자체로 하나의 독립된 기능 모듈(예: 암호화 루틴 전체)일 가능성이 있다.

**IDA에서는** 여러 그래프 기능이 나뉘어 있다:
- **View → Graphs → Flow chart**: 지금 커서가 있는 함수 하나의 내부 흐름(기본 블록 단위 CFG)을 보여준다. 조건 분기의 참/거짓 경로가 초록/빨강 선으로 구분된다.
- **View → Graphs → Function calls**: 프로그램 전체의 함수 호출 그래프를 보여준다. 노드가 함수, 엣지가 호출 관계다.
- **View → Graphs → Xrefs to / Xrefs from**: 현재 주소를 중심으로 들어오는/나가는 참조만 그래프로 보여준다.
- **View → Graphs → User xrefs chart**: 위 to/from을 결합한 형태로, 특정 부분만 골라 보이게 필터링할 수 있어 큰 그래프를 다룰 때 더 유용하다.
- **View → Open subviews → Proximity browser**: 현재 함수를 중심으로 한 호출 관계를 별도의 인터랙티브한 뷰로 보여주며, 마우스로 노드를 계속 확장/축소할 수 있다.

**Ghidra에서는**:
- 함수 위에서 우클릭 → **Function Call Graph**: 그 함수를 중심으로 호출하는 함수(Outgoing)와 호출받는 함수(Incoming)를 그래프로 보여준다. 노드를 더블클릭하면 그 노드를 중심으로 그래프가 다시 그려진다.
- **Window → Function Call Trees**(단축키 `Ctrl+Alt+T`): 그래프가 아니라 트리 형태로, 왼쪽에 "Incoming Calls"(이 함수를 부르는 함수들), 오른쪽에 "Outgoing Calls"(이 함수가 부르는 함수들)를 계층적으로 펼쳐볼 수 있는 상시 패널이다. 여러 함수를 옮겨 다니며 계속 확인해야 할 때는 그래프보다 이 트리 패널이 더 다루기 편할 때가 많다.

## 화면/코드에서 보이는 징후
- 함수 개수가 많아서(예: 100개 이상) Symbol Tree나 Functions 목록을 스크롤하는 것만으로는 구조가 안 잡힌다.
- 여러 함수를 오가며 REV-0160 방식으로 XREF를 하나씩 따라가다 보니, 지금까지 확인한 경로를 자꾸 잊어버리게 된다.

## 가장 먼저 할 것
`main`(또는 `entry`)이나 이미 REV-0163~0165에서 확인된 후보 함수 중 하나를 기준으로 Call Graph를 열어서, 그 함수의 위아래로 몇 단계나 연결되어 있는지 큰 그림부터 본다.

## 단계별 절차

**1) 기준 함수 정하기**

`main`을 찾았다면 `main`에서 시작한다. 아직 못 찾았다면 `entry`에서 시작하거나, REV-0163/0164에서 이미 확보한 후보 함수(예: 문자열/Import로 찾은 함수)를 기준으로 삼는다.

**2) 전체 구조 조망 (IDA: Function calls / Ghidra: Function Call Graph)**

- IDA: **View → Graphs → Function calls**를 열어 프로그램 전체 호출 그래프를 본다. 노드가 너무 많으면 확대/축소로 큰 덩어리(클러스터) 단위로만 먼저 훑는다.
- Ghidra: 기준 함수 위에서 우클릭 → **Function Call Graph**를 연다. 기본적으로 그 함수를 중심으로 한 단계씩만 보여주므로, 필요하면 인접 노드를 더블클릭해 점점 넓혀간다.

**3) 특정 함수의 호출 관계만 좁혀 보기**

- IDA: 함수 위에서 **View → Graphs → Xrefs from**(이 함수가 부르는 것들), **Xrefs to**(이 함수를 부르는 것들)를 선택하거나, 더 유연한 필터링이 필요하면 **User xrefs chart**를 사용한다.
- Ghidra: **Window → Function Call Trees**(`Ctrl+Alt+T`)를 열어두고, 관심 함수로 이동할 때마다 왼쪽(Incoming)/오른쪽(Outgoing) 트리가 자동 갱신되는 것을 활용한다.

**4) 허브/말단 함수 구분**

그래프에서 들어오는 화살표가 유난히 많은 노드는 범용 유틸리티일 가능성이, 특정 한두 곳에서만 들어오고 나가는 화살표가 적은(계산만 하는) 노드는 검증/알고리즘 로직일 가능성이 높다는 관점으로 훑어본다.

**5) 후보 서브그래프를 찾으면 세부 읽기로 전환**

그래프로 후보 영역을 좁혔다면, 그 안의 함수들을 REV-0158(Decompiler 창 읽기)과 REV-0161(Rename/Retype)로 하나씩 정리하며 실제 로직을 확정한다.

**6) 큰 그래프 다루는 팁**

노드/엣지가 너무 많아 한눈에 안 들어오면, 그래프 전체를 한 번에 이해하려 하지 말고 "기준 함수 1~2단계 이내"로 범위를 좁혀서 반복적으로 살펴보는 것이 실전적이다. IDA의 User xrefs chart나 Ghidra의 Function Call Graph 모두 특정 노드를 다시 중심으로 재구성하는 기능을 지원하므로, 이를 반복하며 점진적으로 탐색 범위를 옮겨간다.

## 명령어/단축키
- IDA: 함수 내부 흐름 **View → Graphs → Flow chart**, 전체 호출 그래프 **View → Graphs → Function calls**, 참조 그래프 **Xrefs to/from**, 결합형 **User xrefs chart**, 대화형 뷰 **View → Open subviews → Proximity browser**
- Ghidra: 함수 우클릭 → **Function Call Graph**, 트리 패널 **Window → Function Call Trees**(`Ctrl+Alt+T`)
- 공통: 그래프에서 더블클릭하면 해당 함수의 코드/디컴파일 화면으로 바로 이동

## 출력 해석
- IDA Flow chart(단일 함수 내부)에서 초록 선은 조건이 참일 때의 분기, 빨강 선은 거짓일 때의 분기를 뜻한다. 이를 이용해 "성공 경로"와 "실패 경로"가 코드 상에서 어떻게 갈라지는지 시각적으로 바로 볼 수 있다.
- 그래프에서 한 노드로 향하는 화살표가 하나뿐이면, 그 함수를 호출하는 지점이 프로그램 전체에서 유일하다는 뜻이다(REV-0160의 XREF 개념과 동일). 이런 노드는 특정 기능에 전용으로 쓰이는 함수일 가능성이 크다.
- 순환(cycle)이 보인다면(A→B→A) 재귀 호출이거나, 상호 보완적으로 동작하는 두 함수 쌍(예: 암호화/복호화 헬퍼)일 수 있다.

## 흔한 실수
- 그래프가 복잡해 보인다고 처음부터 전체 그래프를 다 이해하려 드는 것 — 기준 함수 근처 1~2단계만 먼저 보고, 필요할 때 점진적으로 넓혀가는 것이 훨씬 효율적이다.
- 그래프만 보고 실제 코드를 안 읽는 것 — Call Graph는 "어디를 읽어야 할지"를 정하는 지도일 뿐, 실제 로직 판단은 결국 Decompile 창(REV-0158)에서 이루어진다.
- 허브 함수(들어오는 화살표가 많은 함수)를 검증 로직으로 착각하는 것 — 오히려 이런 함수는 로깅, 메모리 할당, 문자열 유틸리티 같은 범용 기능일 확률이 높다.
- IDA에서 Function calls 그래프를 프로그램 전체 기준으로 열었다가 노드 수가 너무 많아 랙이 걸리는 것을 그대로 방치하는 것 — 이 경우 특정 함수를 기준으로 한 Xrefs to/from이나 User xrefs chart처럼 범위가 좁은 그래프로 전환하는 것이 낫다.

## 막혔을 때 다음 체크
- 후보 영역을 찾았는데 각 함수의 세부 로직이 안 읽힌다면 → REV-0158(Ghidra Decompiler 창 읽기).
- 그래프에서 찾은 함수 이름을 정리하고 싶다면 → REV-0161(Ghidra Rename과 Data Type 수정).
- 컴파일러가 자동 생성한 초기화/런타임 코드와 실제 문제 로직을 구분하기 어렵다면 → REV-0167(Compiler Generated Code와 실제 문제 로직 구분).
- 여전히 그래프만으로는 핵심 함수를 못 정했다면 → REV-0163/0164/0165의 단서 기반 접근으로 되돌아가 교차검증.

## 미니 예제
`main`을 기준으로 IDA에서 View → Graphs → Function calls를 열었더니, `main` 노드에서 화살표 3개가 뻗어나가 `read_input`, `check_password`, `print_result`로 향하는 것이 보인다고 하자. 이 중 `check_password`만 안쪽으로 다시 `strcmp`(라이브러리 함수)로 향하는 화살표가 있고, 다른 노드는 라이브러리 함수 호출이 거의 없다. 이 시점에서 굳이 `read_input`, `print_result` 내부를 자세히 읽지 않아도 "검증 로직은 `check_password`에 있다"는 결론을 그래프 모양만으로 상당히 신뢰성 있게 도출할 수 있다. 이후 `check_password`만 REV-0158/0161로 정밀하게 분석하면 된다.

## 관련 글
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0160 — Ghidra XREF 따라가기
- REV-0163 — 문자열에서 검증 함수로 이동하는 정적 분석
- REV-0164 — Imports에서 검증 함수 후보 좁히기
- REV-0167 — Compiler Generated Code와 실제 문제 로직 구분

## 출처/검증
- IDA View → Graphs(Flow chart, Function calls, Xrefs to/from, User xrefs chart)와 Proximity browser: Hex-Rays 공식 문서(User Guide, Menu Bar → View → Graphs 관련 topic) 기준.
- Ghidra Function Call Graph(우클릭 메뉴)와 Function Call Trees(`Window → Function Call Trees`, 기본 단축키 `Ctrl+Alt+T`): Ghidra 공식 Help 문서 및 널리 통용되는 Ghidra 단축키 정리 자료 기준.
- 이 문서는 라이브 IDA/Ghidra 화면을 직접 캡처해 재검증하지는 않았으며, 공식 문서와 일반적으로 통용되는 UI 동작을 기준으로 작성되었다.
