---
id: REV-0231
title: "Control Flow Flattening 기초"
slug: "rev-0231-control-flow-flattening"
category: "packing"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, "x64dbg", "Detect It Easy"]
keywords: ["control flow flattening", "CFF", "제어 흐름 평탄화", "dispatcher switch", "state machine obfuscation", "flattened control flow", "IDA graph view 복잡함", "코드 난독화"]
aliases: ["cff란", "제어흐름 평탄화", "control flow flattening 뜻", "switch dispatcher 난독화", "복잡한 CFG"]
symptom_keywords: ["IDA graph view가 스파게티", "함수 하나에 basic block이 수백개", "switch문이 이상하게 많음", "state 변수가 루프를 돈다", "디컴파일 결과가 while switch로만 됨", "CFG가 방사형으로 퍼짐"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Control Flow Flattening(제어 흐름 평탄화, CFF)은 원래 if/else와 반복문으로 이루어진 자연스러운 코드 흐름을, "상태 변수 하나 + 그 값에 따라 분기하는 거대한 switch문을 감싼 while 루프" 하나로 통째로 뒤바꿔서, IDA의 그래프 뷰를 보기만 해도 어지러운 방사형(spaghetti) 모양으로 만들어 분석을 방해하는 코드 난독화 기법이다.

## 언제 검색해야 하나
- IDA에서 함수 하나를 그래프 뷰(Graph view, Space 키)로 봤는데 노드(basic block)가 수십~수백 개이고, 중앙의 한 블록에서 사방으로 화살표가 뻗어나가는 별 모양/방사형 구조로 보일 때
- 디컴파일(F5) 결과가 원래 프로그램 로직과 무관하게 `while(1) { switch(state) { case 1: ... state = 5; break; case 5: ... } }` 형태로만 나올 때
- 간단해 보이는 함수인데 basic block 개수가 비정상적으로 많아서 뭘 하는 함수인지 감이 안 잡힐 때
- "코드 난독화(obfuscation)"라는 단어를 보고 정확히 어떤 기법인지 궁금할 때

## 핵심 개념
컴파일러가 만드는 일반적인 코드는 **직관적인 그래프 구조**를 가진다. `if`문은 두 갈래로 갈라졌다가 다시 합쳐지고, `for`/`while` 반복문은 루프 안에서 위로 되돌아가는 화살표 하나만 가진다. 그래서 IDA 그래프 뷰로 보면 코드의 논리 구조가 그림만 봐도 대략 짐작이 간다(예: 다이아몬드 모양이면 if/else, 위로 감기는 화살표가 있으면 루프).

**Control Flow Flattening**은 컴파일 이후(또는 컴파일 과정에 통합된 난독화 패스로) 이 자연스러운 구조를 인위적으로 파괴한다. 변환 방식은 다음과 같다.

1. 원본 함수의 모든 코드 블록(원래 if/else의 각 분기, 루프의 각 반복 등)을 잘게 쪼갠다.
2. 각 블록에 고유한 번호(상태 값, state)를 부여한다.
3. 함수 전체를 **하나의 큰 `while(true)` 루프**로 감싸고, 그 안에 **하나의 거대한 `switch(state)` 문**을 둔다. `switch`의 각 `case`가 원래 블록 하나에 해당한다.
4. 각 블록(case)의 마지막에서는 다음에 실행할 블록의 번호를 `state` 변수에 대입하고 `break`(즉 `switch` 밖으로 나가 `while` 루프 맨 위로 되돌아감)한다. 원래는 `JMP 다음_블록`이었던 것이, 이제는 `state = 다음_블록_번호; break;`로 바뀐다.
5. 원래 if/else였던 분기도 마찬가지로, "조건이 참이면 state = A, 거짓이면 state = B"로 바뀐다.

이렇게 되면 원래 코드가 어떤 순서로 실행되었는지는 **오직 `state` 변수의 값 변화를 실제로 추적해야만** 알 수 있다. 정적으로 그래프만 봐서는 `case 1` 다음에 어떤 `case`가 실행될지 알 수 없다(모든 `case`가 dispatcher 루프를 거쳐 이론적으로는 서로 연결될 수 있는 것처럼 보이기 때문). 이것이 바로 "평탄화(flattening)"라는 이름의 의미다 — 원래 있던 깊이 있는 트리/그래프 구조가 하나의 평평한 switch-case 목록으로 눌린다.

## 화면/코드에서 보이는 징후
- IDA 그래프 뷰(Space 키로 전환)에서 함수 하나가 **중앙의 큰 블록(dispatcher)에서 사방으로 화살표가 뻗어나가는 방사형/별 모양**으로 보임. 정상적인 함수의 다이아몬드/직선 구조와 확연히 다름.
- 디컴파일(F5) 결과에 원래 프로그램 로직과 무관해 보이는 정수형 변수(흔히 `v4`, `state`, `dispatcher` 같은 이름)가 함수 전체에 걸쳐 계속 갱신되고, 그 변수를 기준으로 하는 거대한 `switch` 문이 나타남
- `switch`의 `case` 개수가 함수의 원래 복잡도에 비해 과도하게 많음(단순한 함수인데 case가 30개 이상)
- 각 `case` 블록의 코드 자체는 짧고(원래 basic block 하나 분량), 끝부분에서 항상 다음 state 값을 정하는 대입문으로 끝남
- basic block 개수가 원본 소스 코드의 논리적 분기 개수보다 훨씬 많음(원래 if 3개짜리 함수인데 실제 block은 20개 이상)

## 가장 먼저 할 것
그래프 뷰의 복잡한 모양에 압도되지 말고, 먼저 **dispatcher 블록**(모든 화살표가 모이고 다시 흩어지는 중앙 블록)을 찾는다. 그 블록에서 `state` 변수를 비교하는 코드(`cmp state, N` / `jz caseN`의 연쇄, 또는 컴파일러가 최적화한 jump table)를 확인하면, 이 함수가 CFF로 변환되었다는 것을 확신할 수 있다.

## 단계별 절차

**1) 그래프 뷰로 전체 모양 확인**

IDA에서 함수를 열고 `Space`로 그래프 뷰로 전환한다. 방사형 구조가 보이면 CFF를 의심한다.

**2) dispatcher 블록과 state 변수 식별**

중앙 블록의 코드를 본다. 보통 지역 변수 하나(스택 슬롯 또는 레지스터)를 비교하는 일련의 `cmp`/`je`/`jz` 체인이거나, 컴파일러가 만든 jump table(`jmp [table + state*4]`)이 보인다. 이 변수가 바로 state 변수다.

**3) 각 case 블록을 원래 코드 조각으로 매핑**

각 `case`를 하나씩 읽으면서, 그 블록이 실제로 어떤 계산을 하는지, 그리고 끝에서 state를 어떤 값으로 바꾸는지를 기록한다. 이 매핑을 종이나 메모장에 "state 3 → 조건 검사 → 참이면 state=7, 거짓이면 state=12" 식으로 정리하면 원래 흐름이 보이기 시작한다.

**4) 동적 분석으로 실제 실행 순서 확인**

정적으로 손으로 다 따라가기 번거롭다면, 디버거(x64dbg)로 state 변수가 위치한 메모리/레지스터에 조건부 로깅 브레이크포인트를 걸어, 실제 실행 중 state 값이 어떤 순서로 바뀌는지 기록한다. 이렇게 얻은 실제 순서가 원래 함수의 논리 흐름이다.

**5) 필요하면 디컴파일러 결과를 손으로 재구성**

F5 디컴파일 결과를 그대로 믿기보다, 3)/4)에서 얻은 state 전이표를 바탕으로 "이건 사실 `if (x > 10) { ... } else { ... }`였겠구나" 식으로 원래 로직을 손으로 재구성해서 주석을 남긴다.

## 명령어/단축키
- IDA `Space` : 텍스트 뷰 ↔ 그래프 뷰 전환
- IDA `F5` : 디컴파일 (Hex-Rays)
- IDA 그래프 뷰에서 마우스 휠/드래그 : 전체 구조를 축소해서 방사형 모양인지 한눈에 확인
- x64dbg 조건부 브레이크포인트: state 변수 주소에 브레이크포인트를 걸고 "Log" 조건으로 값 변화를 기록

## 출력 해석
- dispatcher 블록의 비교 체인이 `cmp eax, 1 / je case_1`, `cmp eax, 2 / je case_2` ... 식으로 수십 개 이어진다면 → 컴파일러 최적화 없이 순차 비교로 구현된 CFF.
- `jmp dword ptr [eax*4 + jump_table]` 형태의 간접 점프가 보인다면 → 컴파일러/난독화 도구가 switch를 jump table로 최적화한 CFF. IDA가 이 테이블을 자동으로 인식하면 그래프 뷰에 각 case로의 화살표가 자동으로 그려진다.
- 특정 case 블록이 유난히 다른 case로 가는 경로가 하나뿐(항상 같은 다음 state로 고정)이라면 → 원래 순차 실행 코드(분기 없는 직선 코드)였을 가능성이 높다.
- 특정 case 블록에서 state가 조건에 따라 두 가지 값 중 하나로 갈린다면 → 원래 if/else 분기였던 지점이다.
- 특정 case에서 이전에 나온 state 번호로 다시 돌아가는 경로가 있다면 → 원래 반복문(loop)이었던 지점이다.

## 흔한 실수
- 그래프 뷰의 복잡한 모양만 보고 지레 겁먹어 아예 분석을 포기하는 것. dispatcher와 state 변수만 찾으면 각 case는 개별적으로는 짧고 단순한 경우가 많다.
- 모든 case를 처음부터 순서대로 읽으려는 것. 실제 실행 순서는 코드에 나열된 순서와 무관하므로, state 전이를 따라가며 읽어야 한다.
- 디컴파일러가 보여주는 `switch(state)` 구조 자체를 원래 프로그램의 진짜 로직이라고 착각하는 것. 이는 어디까지나 난독화로 인해 생긴 인위적인 구조이며, 실제 분석 목표는 그 뒤에 숨은 원래 로직을 재구성하는 것이다.
- state 변수가 하나가 아니라 여러 개로 쪼개져 있거나, 매 반복마다 값이 암호화/변형되는 더 강한 버전의 CFF를 만났을 때, 기본형과 똑같은 방식으로만 접근하다가 막히는 것 — 이런 경우 동적 분석(4단계) 비중을 크게 늘려야 한다.

## 막혔을 때 다음 체크
- state 변수를 찾았는데 값이 단순 정수가 아니라 매번 다른 방식으로 계산된다면 → Opaque Predicate(REV-0232)가 함께 섞여 있을 가능성이 높다.
- 각 case 블록 안에서 코드가 자기 자신을 수정하는 것처럼 보인다면 → REV-0230(Self-modifying Code)과 결합된 형태다.
- 손으로 따라가기엔 case가 너무 많다면(100개 이상) → 정적으로 전부 재구성하려 하지 말고, 동적 분석으로 관심 있는 입력값(예: 특정 비밀번호 입력)에 대해 실제로 어떤 state 경로를 타는지만 추적하는 것이 훨씬 효율적이다.
- IDA의 디컴파일 결과가 너무 지저분해서 못 읽겠다면 → 그래프 뷰에서 각 case 블록에 직접 주석을 달아가며 손으로 흐름을 표시하는 것이 오히려 더 빠를 수 있다.

## 미니 예제
원래 다음과 같은 간단한 C 함수가 있었다고 하자.

```c
int check(int x) {
    if (x > 10) {
        x = x * 2;
    } else {
        x = x + 5;
    }
    return x;
}
```

CFF가 적용되면 디컴파일 결과는 대략 다음처럼 보인다.

```c
int check(int x) {
    int state = 0;
    int result;
    while (1) {
        switch (state) {
            case 0:
                if (x > 10)
                    state = 1;
                else
                    state = 2;
                break;
            case 1:
                result = x * 2;
                state = 3;
                break;
            case 2:
                result = x + 5;
                state = 3;
                break;
            case 3:
                return result;
        }
    }
}
```

원래는 if/else 하나뿐인 아주 단순한 함수였지만, `state` 값을 손으로 따라가지 않으면 IDA 그래프 뷰만으로는 `case 1`과 `case 2`가 서로 배타적(mutually exclusive)인 분기라는 것을 한눈에 알기 어렵다. `case 0`이 dispatcher 진입점, `case 3`이 합류 지점이라는 것을 파악하면, 원래 로직이 단순한 if/else였음을 재구성할 수 있다.

## 관련 글
- REV-0230 — Self-modifying Code 기초
- REV-0232 — Opaque Predicate 기초

## 출처/검증
- Control Flow Flattening의 개념(state 변수 + dispatcher switch로 원본 CFG를 평탄화)은 원래 Cristina Cifuentes와 이후 난독화 연구(예: Tigress obfuscator, LLVM 기반 오픈소스 난독화 패스인 obfuscator-llvm/OLLVM 프로젝트 문서)에서 공통적으로 설명하는 표준적인 코드 난독화 기법을 기준으로 정리했다(2026-09-08 검증).
- IDA 그래프 뷰에서 CFF가 방사형/별 모양으로 보이는 특징은 실무 리버싱 커뮤니티에서 널리 공유되는 관찰이다.
- 실제 구현은 난독화 도구(OLLVM, Tigress, 커스텀 컴파일러 패스 등)마다 세부 방식이 다를 수 있으므로, 예제는 개념 이해를 위한 단순화된 형태다.
