---
id: REV-0938
title: "난독화 기법 종류 빠른 참조표(정리본)"
slug: "rev-0938-obfuscation-techniques-summary-quickref"
category: "packing"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["난독화 종류", "obfuscation summary", "control flow flattening", "opaque predicate", "self-modifying code", "문자열 난독화", "난독화 지도"]
aliases: ["난독화 기법 총정리", "난독화 종류 표", "코드 난독화 분류", "obfuscation techniques quickref"]
symptom_keywords: ["난독화 종류가 헷갈림", "이 코드가 무슨 난독화인지 모르겠음", "control flow flattening이 뭔가", "opaque predicate가 뭔가"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
바이너리 난독화는 압축(패킹)과 달리 파일 크기를 줄이는 것이 목적이 아니라 코드의 "논리적 흐름을 읽기 어렵게" 만드는 것이 목적이며, 대표적으로 제어 흐름 난독화(Control Flow Flattening), 불투명 조건식(Opaque Predicate), 자기 수정 코드(Self-modifying Code), 문자열 난독화 네 가지로 분류된다 — 이 문서는 packing 카테고리의 개별 난독화 문서(REV-0230~0233)를 한 표로 빠르게 잇는 색인이다.

## 언제 검색해야 하나
- IDA 디컴파일 결과가 이상하게 복잡한 `switch`/`goto` 덩어리로 나오거나, 절대 참/거짓이 안 바뀔 것 같은 `if` 조건이 반복될 때 이게 어떤 종류의 난독화인지 분류하고 싶을 때
- 여러 난독화 기법 이름을 한 번에 비교하며 각각 어떤 문서에서 더 자세히 다루는지 색인이 필요할 때
- 패킹은 아닌데(엔트로피 정상, import 정상) 디컴파일 결과가 이상하게 꼬여 있어서 "이건 패킹이 아니라 난독화구나"를 확인하고 싶을 때

## 핵심 개념
패킹(REV-0224~0227)이 "파일을 압축해서 숨기는 것"이라면, 난독화는 "코드는 그대로 실행되지만 사람이 읽었을 때 논리를 파악하기 어렵게 변형하는 것"이다. 그래서 난독화된 코드는 엔트로피(REV-0934)가 정상 범위인 경우가 많고, import 개수도 정상적이어서 패킹 체크리스트(REV-0224)만으로는 잘 안 걸릴 수 있다. 아래 표는 packing 카테고리에 이미 있는 네 가지 난독화 기법 문서를 한 번에 비교한 것이다.

| 기법 | 핵심 원리 | 디컴파일/디스어셈블리에서 보이는 특징 | 상세 문서 |
|---|---|---|---|
| Control Flow Flattening | 원래의 순차적/중첩된 제어 흐름을 하나의 거대한 `switch`와 상태 변수로 평탄화 | 함수 전체가 `while(1) { switch(state) { ... } }` 형태로 보임, 원래 구조 파악 어려움 | REV-0231 |
| Opaque Predicate | 실행 결과가 항상 참(또는 항상 거짓)인 조건식을 삽입해 가짜 분기를 만듦 | 절대 안 바뀌는 것처럼 보이는 `if` 조건, 도달 불가능한 코드 블록이 함께 존재 | REV-0232 |
| Self-modifying Code | 실행 중에 자기 자신의 코드 바이트를 직접 변경 | 정적 디스어셈블리 결과와 실제 실행 시 동작이 다름, 특정 메모리 영역에 쓰기 명령이 반복됨 | REV-0230 |
| 문자열 난독화 | 문자열 리터럴을 XOR/커스텀 인코딩으로 저장하고 사용 직전에 복호화 | `strings` 결과에 의미 있는 문자열이 거의 안 보임, 복호화 루프가 여러 곳에 반복 등장 | REV-0233 |

## 화면/코드에서 보이는 징후
- IDA 디컴파일 결과에 `case`가 수십~수백 개인 거대한 `switch` 문 하나가 함수 전체를 감싸고 있음 → Control Flow Flattening 의심.
- 조건식이 복잡한 수식(`(x*x + x) % 2 == 0` 등)인데 실제로는 항상 같은 결과가 나옴 → Opaque Predicate 의심.
- 코드 섹션에 쓰기 권한이 있거나, 실행 중 특정 주소에 반복적으로 값을 쓰는 명령이 보임 → Self-modifying Code 의심.
- `strings` 결과가 거의 비어 있는데 프로그램은 분명 메시지를 출력함 → 문자열 난독화 의심.

## 가장 먼저 할 것
`strings sample`부터 실행해서 의미 있는 문자열이 나오는지 확인한다. 문자열이 거의 안 보이면 REV-0233(문자열 난독화)부터 확인한다. 문자열은 정상인데 IDA 디컴파일 결과가 이상하게 복잡하면 REV-0231/0232로 이동한다.

## 단계별 절차
**1) 엔트로피/import 정상 여부 확인**: REV-0224/REV-0934 기준으로 패킹이 아님을 먼저 확인한다.
**2) 문자열 확인**: `strings`로 의미 있는 문자열이 나오는지 본다. 안 나오면 REV-0233으로 이동.
**3) 디컴파일 구조 확인**: IDA에서 함수 전체가 거대한 `switch`+`while`로 보이면 REV-0231(Control Flow Flattening)로 이동.
**4) 조건식 확인**: 절대 안 바뀌는 것 같은 조건식이 반복되면 REV-0232(Opaque Predicate)로 이동.
**5) 실행 중 코드 변경 확인**: 코드 섹션에 쓰기가 발생하거나 정적 디스어셈블리와 실행 결과가 다르면 REV-0230(Self-modifying Code)으로 이동.
**6) 조합 여부 확인**: 실전 난독화는 위 네 가지 중 2개 이상을 함께 쓰는 경우가 흔하므로, 하나를 해결했다고 끝내지 말고 나머지도 확인한다.

## 명령어/단축키
- `strings sample`: 문자열 노출 여부 확인
- IDA: `View → Graph view`로 `switch` 구조를 시각적으로 확인(Control Flow Flattening 판별에 유용)
- IDA: 코드 섹션 속성에서 쓰기 권한(W) 여부 확인(Self-modifying Code 판별 단서)

## 출력 해석
- Graph view에서 하나의 거대한 블록에서 수십 개의 화살표가 각기 다른 작은 블록으로 갈라졌다가 다시 중앙 블록으로 모이는 "허브-스포크" 모양이 보이면 Control Flow Flattening이 강하게 의심된다.
- 디컴파일 결과에 `if (a * a >= 0)`처럼 항상 참인 수학적 항등식이 조건으로 쓰였다면 Opaque Predicate다.
- 문자열 복호화 루프를 찾았다면(단순 XOR 키 하나로 반복되는 경우가 많음) 그 루프를 디버거에서 한 번 실행시켜 복호화된 값을 레지스터/메모리에서 직접 읽으면 원래 문자열을 알아낼 수 있다.

## 흔한 실수
- 난독화된 코드를 보고 무조건 "패킹되었다"고 오해하는 것 — 난독화는 패킹과 달리 엔트로피가 정상일 수 있다.
- 네 가지 기법 중 하나만 확인하고 나머지를 확인하지 않아 분석이 막히는 것 — 실전에서는 조합이 흔하다.
- Opaque Predicate를 진짜 의미 있는 조건 분기로 착각해서 두 분기 모두를 똑같이 공들여 분석하는 것 — 항상 같은 결과가 나오는지 먼저 값을 대입해 확인하면 시간을 아낄 수 있다.

## 막혔을 때 다음 체크
- 특정 기법의 상세 분석/우회 방법이 필요하면 → REV-0230(Self-modifying Code), REV-0231(Control Flow Flattening), REV-0232(Opaque Predicate), REV-0233(문자열 난독화) 각 문서로 이동한다.
- 난독화가 아니라 패킹인지부터 재확인하고 싶으면 → REV-0224 패킹된 바이너리인지 의심하는 기준.
- 정적 분석으로 도저히 안 풀리면 → REV-0241 패커와 난독화 때문에 디컴파일이 틀릴 때 정적/동적 전환.

## 미니 예제
```c
// Control Flow Flattening 예시 (디컴파일 결과 형태)
int state = 0;
while (1) {
    switch (state) {
        case 0: x = a + b; state = 3; break;
        case 3: if (x > 10) state = 1; else state = 2; break;
        case 1: y = x * 2; state = 4; break;
        case 2: y = x - 1; state = 4; break;
        case 4: return y;
    }
}
```
원래는 단순한 `if (a+b > 10) y = (a+b)*2; else y = (a+b)-1;` 수준의 로직이지만, 상태 변수(`state`)와 `switch`로 평탄화되어 원래 흐름이 한눈에 안 들어온다. `state` 값의 변화를 따라가며 순서를 손으로 재구성하는 것이 이 유형의 기본 분석법이다.

## 관련 글
- REV-0230 — Self-modifying Code 기초
- REV-0231 — Control Flow Flattening 기초
- REV-0232 — Opaque Predicate 기초
- REV-0233 — 문자열 난독화가 보일 때
- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0241 — 패커와 난독화 때문에 디컴파일이 틀릴 때 정적/동적 전환

## 출처/검증
- Control Flow Flattening, Opaque Predicate, Self-modifying Code, 문자열 난독화의 분류와 특징은 다수의 공개 리버싱/컴파일러 난독화 연구 자료(예: Collberg et al., "A Taxonomy of Obfuscating Transformations")와 CTF 리버싱 교육 자료에서 공통적으로 다루는 표준적인 분류 방식을 종합한 것이다(2026-09-09 검증).
- 개별 기법의 세부 탐지/분석 방법은 각 하위 문서(REV-0230~0233)에서 별도로 검증되어 있다.
