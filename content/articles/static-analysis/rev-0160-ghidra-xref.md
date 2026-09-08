---
id: REV-0160
title: "Ghidra XREF 따라가기"
slug: "rev-0160-ghidra-xref"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra XREF", "Ghidra Show References To", "Ghidra Incoming References", "Ghidra Outgoing References", "Ghidra Function Call Graph"]
aliases: ["Ghidra 참조 추적", "Ghidra 크로스레퍼런스", "Ghidra 누가 호출하는지"]
symptom_keywords: ["Ghidra에서 이 함수를 누가 부르는지 모름", "Ghidra XREF 창 여는 법", "Ghidra 이 문자열을 누가 쓰는지 찾기", "Ghidra References to Address"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Ghidra에서 XREF(cross-reference)는 **어떤 주소/심볼을 누가 참조하는지(Incoming), 그 함수가 무엇을 참조하는지(Outgoing)**를 보여주는 기능으로, Listing에 표시되는 `XREF[n]:` 태그를 읽거나 우클릭 메뉴의 **References → Show References To**를 사용해 핵심 로직까지 거슬러 올라가는 것이 정적 분석에서 가장 많이 쓰는 이동 방법이다.

## 언제 검색해야 하나
- Import된 함수(`strcmp` 등)나 특정 문자열을 찾았는데, 그것을 실제로 사용하는 코드로 어떻게 이동해야 할지 모를 때
- Listing에서 `XREF[2,0]:` 같은 표기를 봤는데 숫자가 무슨 뜻인지 모를 때
- 특정 함수가 프로그램 전체에서 몇 번, 어디서 호출되는지 한눈에 보고 싶을 때
- IDA의 `X` 단축키(xrefs to)에 대응하는 Ghidra 기능이 뭔지 궁금할 때

## 핵심 개념
XREF는 "이 주소를 참조하는 다른 위치가 어디인가"를 알려주는 정적 분석의 핵심 도구다. 참조에는 두 방향이 있다.

- **Incoming Reference(들어오는 참조)**: "누가 이 주소를 가리키는가." 예를 들어 함수 A 안에서 함수 B를 호출(`call`)하면, B 입장에서는 A로부터 들어오는 참조가 생긴다. 데이터도 마찬가지다 — 어떤 문자열 주소를 참조하는 명령어가 있다면, 그 문자열 입장에서 Incoming Reference가 생긴다.
- **Outgoing Reference(나가는 참조)**: "이 위치가 누구를 가리키는가." 함수 A의 관점에서 A가 호출하는 B, C, D는 A의 Outgoing Reference다.

Ghidra Listing에서는 **어떤 함수/데이터가 다른 곳에서 참조되고 있으면, 그 정의 위치 바로 위에 `XREF[n]:` 형태의 주석 줄이 자동으로 표시된다.** `n`은 참조하는 곳의 개수다. 예를 들어 `XREF[1]: 00401520(c)`처럼 표시되면, 주소 `00401520`에서 `(c)` 즉 code(코드) 형태로 이 위치를 참조한다는 뜻이다. 괄호 안 문자는 참조 유형을 나타내는데 대표적으로:
- `(c)` : 코드에서의 참조 (예: call, jump)
- `(R)` / `(r)` : 읽기(Read) 참조
- `(W)` / `(w)` : 쓰기(Write) 참조
- `(*)` : 간접 참조(포인터를 통한 참조 등)

참조 개수가 많으면 Listing에 전부 나열하지 않고 요약된 형태로 보여주며, 이때는 우클릭 메뉴를 통해 전체 목록을 담은 별도 창을 띄워야 한다.

## 화면/코드에서 보이는 징후
- Listing에서 함수나 데이터 정의 바로 위 줄에 회색 글씨로 `XREF[1,0]: 00401520(c)` 같은 텍스트가 보인다.
- 우클릭 메뉴에 **References** 하위 메뉴가 있고, 그 안에 **Show References To**, **Show References From** 같은 항목이 있다.
- Decompile 창에서 함수를 클릭하고 우클릭하면 **Show Function Call Trees** 같은 항목도 나온다.

## 가장 먼저 할 것
관심 있는 주소(함수, 문자열, 전역 변수)에 커서를 놓고, Listing에 보이는 `XREF[...]:` 줄을 먼저 읽는다. 참조가 하나뿐이면 그 주소를 더블클릭해서 바로 이동하고, 여러 개면 우클릭 → **References → Show References To**로 전체 목록 창을 연다.

## 단계별 절차

**1) 대상 주소로 이동**

관심 있는 함수(예: Import된 `strcmp`의 thunk)나 데이터(예: 문자열)로 이동한다.

**2) Listing에서 XREF 줄 확인**

정의 위치 위에 `XREF[n]: 주소1(유형) 주소2(유형) ...` 형태의 줄이 있는지 본다. 참조가 하나뿐이면 그 주소 텍스트를 더블클릭하면 바로 그 위치로 이동한다.

**3) 참조가 많으면 References 창 열기**

참조가 많거나 전체 목록을 표로 보고 싶으면, 대상 위에서 우클릭 → **References → Show References To**를 선택한다. "References to..." 라는 작은 창이 뜨며, 참조하는 모든 주소와 그 주소가 속한 함수 이름이 테이블로 나열된다. 이 테이블에서 행을 더블클릭하면 Listing이 그 위치로 이동한다.

**4) 반대 방향(이 함수가 무엇을 부르는지) 확인**

지금 있는 함수가 무엇을 호출/참조하는지 보려면 우클릭 → **References → Show References From**을 사용하거나, 더 시각적으로는 **Function Call Graph**(아래 6단계)를 이용한다.

**5) Decompile 창에서 XREF 활용**

Decompile 창에서도 변수나 함수 호출 위에 커서를 두고 우클릭하면 References 관련 메뉴가 동일하게 제공된다. pseudo C를 읽다가 낯선 이름이 나오면 그 자리에서 바로 References를 확인할 수 있다.

**6) Function Call Graph로 전체 그림 보기**

특정 함수 위에서 우클릭 → **Function Call Graph**(또는 상단 도구 아이콘)를 선택하면, 그 함수를 중심으로 호출하는 함수/호출받는 함수가 노드-엣지 그래프로 시각화된다. IDA의 Xrefs graph, Proximity Browser와 비슷한 역할이며, 자세한 활용법은 REV-0166(함수 Call Graph로 핵심 로직 좁히기)에서 다룬다.

**7) Function Call Trees 패널로 트리 보기**

**Window → Function Call Trees**를 열면 왼쪽에 "Incoming Calls", 오른쪽에 "Outgoing Calls" 트리가 상시 표시되는 패널을 고정해 둘 수 있다. 여러 함수를 옮겨 다니며 계속 호출 관계를 확인해야 할 때 유용하다(단축키 `Ctrl+Alt+T`로 토글).

## 명령어/단축키
- 들어오는 참조 보기: 우클릭 → **References → Show References To**
- 나가는 참조 보기: 우클릭 → **References → Show References From**
- Function Call Graph 열기: 함수 위 우클릭 → **Function Call Graph**
- Function Call Trees 패널 토글: `Ctrl+Alt+T`
- 뒤로/앞으로 이동(참조 따라간 뒤 원위치): `Alt+←` / `Alt+→`

## 출력 해석
- `XREF[3,1]:`처럼 콤마로 숫자가 두 개 나오는 경우가 있는데, 이는 각각 "일반 참조 개수"와 "다른 종류(예: 간접 점프 테이블 등)의 참조 개수"를 구분해서 보여주는 것이다. 정확한 개수 구분보다는 "이 위치를 참조하는 곳이 여러 군데 있다"는 사실 자체를 우선 확인하면 된다.
- References 창에서 "Ref Type" 컬럼에 `CALL`, `READ`, `WRITE`, `DATA` 같은 값이 보이면 각각 "함수 호출로 참조", "값을 읽음", "값을 씀", "단순 데이터 포인터로 참조"를 뜻한다. 검증 로직을 찾을 때는 `CALL` 타입 참조가 가장 중요하다.
- 참조가 0개(`XREF` 줄 자체가 없음)인 함수는 **아무도 직접 호출하지 않는 함수**라는 뜻이다. 이런 함수는 함수 포인터 테이블을 통해 간접 호출되거나, 죽은 코드(dead code)이거나, 익스포트된 콜백일 수 있다.

## 흔한 실수
- XREF가 1개뿐이라고 해서 그 호출 지점이 유일한 실행 경로라고 단정하는 것 — 정적 분석의 XREF는 "코드상에 그렇게 쓰여 있다"는 사실만 보여줄 뿐, 실제 실행 시 그 경로가 몇 번 실행되는지는 알려주지 않는다. 반복문 안에 있으면 여러 번 실행될 수 있다.
- Import 함수의 XREF만 보고 검증 로직 전체를 파악했다고 착각하는 것 — `strcmp` 호출 지점을 찾은 뒤에도, 그 비교 결과를 어떻게 쓰는지(성공/실패 분기)는 그 함수 내부 로직을 마저 읽어야 안다.
- Function Call Graph를 열어놓고 노드가 너무 많다고 바로 포기하는 것 — 특정 노드를 더블클릭해 그 노드를 중심으로 다시 그래프를 좁히거나, REV-0166에서 설명하는 필터링 전략을 쓰면 훨씬 다루기 쉬워진다.
- 데이터(문자열, 전역 변수)에 대한 XREF와 함수에 대한 XREF를 같은 방식으로 해석하는 것 — 데이터의 XREF는 "누가 이 데이터를 읽거나 쓰는가"이고, 함수의 XREF는 "누가 이 함수를 호출하는가"로 의미가 다르다는 점을 구분해야 한다.

## 막혔을 때 다음 체크
- XREF를 따라갔는데 도착한 함수가 여전히 `FUN_` 이름이라 뭘 하는지 모르겠다면 → REV-0158(Ghidra Decompiler 창 읽기)로 로직부터 읽는다.
- 문자열에서 XREF로 검증 함수까지 가는 전체 흐름이 궁금하다면 → REV-0163(문자열에서 검증 함수로 이동하는 정적 분석).
- Import 함수 XREF로 후보를 좁히는 전략 자체가 궁금하다면 → REV-0164(Imports에서 검증 함수 후보 좁히기).
- XREF가 아예 없어서 함수 진입 경로를 못 찾겠다면 → 간접 호출(함수 포인터, 가상 함수 테이블)일 수 있으니 REV-0166의 Call Graph 활용법과 상수 검색(REV-0165)을 함께 고려.

## 미니 예제
Symbol Tree의 `Imports`에서 `strcmp`를 찾은 상황을 이어서 보자(REV-0159의 예제와 연결).

1. `strcmp` thunk 위치로 이동하면 Listing에 `XREF[1]: 00401550(c)`가 보인다.
2. 참조가 1개뿐이므로 `00401550`을 더블클릭해서 바로 이동.
3. 도착한 곳은 `FUN_00401550` 함수 내부의 `call strcmp` 명령어 줄이다.
4. 이 함수 전체를 Decompile 창으로 보면(REV-0158), `strcmp(param_1, "S3cr3t_P4ss")` 형태의 비교 로직이 보인다.
5. 이번엔 반대로 `FUN_00401550` 자체의 XREF를 확인(우클릭 → Show References To)하면, `main` 함수(또는 `entry`에서 몇 단계 아래)에서 이 함수를 호출하는 지점을 찾을 수 있고, 이로써 "입력 받기 → 이 함수로 검증 → 결과 출력"이라는 전체 흐름을 정적으로 재구성할 수 있다.

## 관련 글
- REV-0159 — Ghidra Function 목록과 Symbol Tree
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0163 — 문자열에서 검증 함수로 이동하는 정적 분석
- REV-0164 — Imports에서 검증 함수 후보 좁히기
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기
- ../assembly/rev-0071-call.md — CALL 명령어와 XREF의 관계

## 출처/검증
- Listing의 `XREF[n]:` 표기, References → Show References To/From 메뉴, Function Call Graph/Function Call Trees 패널(`Ctrl+Alt+T`): Ghidra 공식 Help 문서(References, Function Call Graph/Call Trees 관련 topic) 기준.
- 라이브 Ghidra 실행 화면을 직접 캡처해 재검증하지는 않았으며, 공식 문서와 널리 알려진 버전 동작을 기준으로 작성되었다. 참조 유형 표기 문자(`c`, `R`, `W` 등)는 버전에 따라 표시 형식이 다를 수 있다.
