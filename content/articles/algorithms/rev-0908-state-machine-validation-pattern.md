---
id: REV-0908
title: "State Machine(상태 기계) 기반 검증 로직 알아보기"
slug: "rev-0908-state-machine-validation-pattern"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["state machine", "상태 기계", "DFA", "유한 오토마톤", "state transition table", "상태 전이 테이블", "switch case 상태 변수"]
aliases: ["상태 기계 크랙미", "DFA 기반 검증", "상태 전이 테이블 알아보기", "switch state 패턴"]
symptom_keywords: ["변수 하나가 계속 상태값으로 갱신됨", "switch case 안에 case가 여러 개고 각 case가 다음 state를 정함", "문자마다 상태가 바뀌면서 검증함", "2차원 테이블에서 현재상태 다음문자로 다음상태를 찾음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
State Machine(유한 상태 기계, DFA) 기반 검증은 "현재 상태(state)"라는 정수 변수 하나를 갖고 입력 문자를 하나씩 읽을 때마다 `state = transition[state][char]` 형태로 상태를 갱신하다가 마지막 상태가 특정 "accept 상태"인지로 합/불합을 가르는 패턴이며, 상태 전이 테이블(전이표)만 정확히 덤프하면 어떤 문자열이 accept 상태에 도달하는지 그래프 탐색으로 거꾸로 찾아낼 수 있다.

## 언제 검색해야 하나
- 디컴파일에서 정수 변수 하나(흔히 `state`, `st`, `cur`)가 루프 내내 계속 갱신되고, 루프가 끝난 뒤 이 변수가 특정 값(예: `state == 5`)인지로 최종 판정을 내릴 때
- `switch(state) { case 0: ... case 1: ... }` 형태로 상태별 분기가 있고, 각 case 안에서 입력 문자에 따라 또 분기해서 다음 state를 정할 때
- 2차원 배열(`transition[state][c]`)이 있고 각 셀 값이 "다음 state 번호"로 보일 때
- 정규표현식 매칭처럼 "특정 패턴의 문자열만 통과시키는" 크랙미인데 XOR/해시 같은 산술 변환이 전혀 안 보일 때

## 핵심 개념

### 상태 기계란 무엇인가
유한 상태 기계(Finite State Machine, FSM)는 다음 세 가지로 정의된다.

1. **상태 집합**: 가능한 `state` 값들의 유한한 목록 (예: 0, 1, 2, ..., N-1)
2. **전이 함수**: `next_state = transition(state, input_char)` — 현재 상태와 입력 한 글자를 받아 다음 상태를 결정
3. **시작 상태와 accept 상태**: 루프 시작 시 `state = start`이고, 입력을 모두 처리한 뒤 `state`가 accept 상태 집합에 속하면 검증 통과

이 구조는 정규표현식 엔진, 어휘 분석기(lexer), 그리고 CTF의 "패턴 검증" 크랙미에서 흔히 재발명된다. 문자열 전체를 한 번에 검사하는 대신 문자를 하나씩 읽으며 상태를 옮겨 다니는 방식이라, `strcmp`나 XOR 루프(REV-0196, REV-0199)와는 완전히 다른 형태로 보인다.

### 왜 State Machine이 크랙미에 쓰이는가
State Machine은 "특정 정규표현식에 맞는 문자열만 통과"시키는 로직을 구현하기에 자연스러운 방법이다. 예를 들어 "숫자로 시작하고 중간에 알파벳이 최소 1개 있고 `!`로 끝나야 한다" 같은 조건은 XOR/해시로는 표현하기 어렵지만 State Machine으로는 상태 몇 개만으로 깔끔하게 표현된다. 또한 각 상태 전이가 정수 배열 인덱싱으로만 이루어지기 때문에 디스어셈블리에서 눈에 잘 안 띄게 숨기기도 쉬워서, 난독화 목적으로도 종종 쓰인다.

### 전이표(Transition Table) 형태로 정리하기
State Machine 코드는 보통 다음 두 형태 중 하나로 구현되어 있다.

**형태 1 — 명시적 2차원 배열**
```c
int transition[NUM_STATES][256] = { ... };  // .rodata에 그대로 존재
int state = 0;
for (int i = 0; input[i]; i++) {
    state = transition[state][(unsigned char)input[i]];
    if (state == -1) return 0;  // 실패 상태(trap state)로 즉시 이탈
}
return (state == ACCEPT_STATE);
```
이 경우는 배열을 그대로 덤프하면 끝이다. 배열 크기가 `NUM_STATES * 256`이므로 IDA/Ghidra에서 주소와 크기만 정확히 확인하면 된다.

**형태 2 — switch/if 사슬로 흩어진 암묵적 전이**
```c
int state = 0;
for (int i = 0; input[i]; i++) {
    char c = input[i];
    switch (state) {
        case 0: state = (c >= '0' && c <= '9') ? 1 : -1; break;
        case 1: state = (c == '!') ? 2 : (isalpha(c) ? 1 : -1); break;
        case 2: state = -1; break;  // accept 이후 입력이 더 있으면 실패
    }
}
return state == 2;
```
이 경우는 명시적 테이블이 없으므로, 각 `case`를 직접 읽고 "이 state에서 이 조건의 문자가 오면 다음 state는 무엇"이라는 규칙을 손으로 표로 옮겨 적어야 한다. 사실상 사람이 직접 전이표를 재구성하는 것과 같다.

### 전이표를 그래프로 보고 accept 경로 역추적하기
전이표가 확보되면 이는 그래프 탐색 문제로 바뀐다. `state`를 노드로, `transition[state][c] = next`를 "문자 `c`를 소비하며 `state`에서 `next`로 가는 간선"으로 보면, "시작 상태에서 accept 상태로 가는 모든 경로"를 BFS/DFS로 열거할 수 있다. 이렇게 하면 조건을 만족하는 입력 문자열을 브루트포스 없이 그래프 탐색만으로 직접 생성할 수 있다.

## 화면/코드에서 보이는 징후
- 루프 밖에서 초기화된 정수 변수 하나가 루프 안에서 반복적으로 재할당되고, 그 변수 자체가 다음 루프 반복의 조건에 다시 쓰임
- `switch(state)` 또는 다단계 `if (state == 0) ... else if (state == 1) ...` 구조
- 실패를 나타내는 특별한 상태값(-1, 0xFF 등)이 있고, 이 값이 되면 즉시 함수가 리턴됨(trap state)
- 최종 판정이 `return state == N;`처럼 상태값 하나와의 비교로 끝남

## 가장 먼저 할 것
`state` 역할을 하는 변수를 특정하고, 그 변수가 가질 수 있는 모든 값(상태 개수)을 먼저 센다. 그다음 전이표가 배열로 명시되어 있는지, 아니면 switch/if로 흩어져 있는지부터 구분한다.

## 단계별 절차
1. 루프 안에서 반복 갱신되는 상태 변수를 찾고, 초기값(시작 상태)과 최종 비교값(accept 상태)을 확정한다.
2. 명시적 배열이면 IDA/Ghidra Hex View로 `NUM_STATES * 256`(또는 실제 알파벳 크기)만큼 통째로 덤프한다.
3. switch/if 사슬이면 각 `case`를 읽고 `(state, char_condition) -> next_state` 규칙을 파이썬 딕셔너리나 표로 손으로 옮긴다. 문자 조건이 범위(`isalpha`, `isdigit`)라면 범위 전체를 하나의 전이로 취급한다.
4. 파이썬으로 전이 함수를 재구현하고, `networkx` 같은 라이브러리 없이도 BFS로 시작 상태에서 accept 상태까지의 경로를 모두 탐색하는 짧은 코드를 작성한다.
5. BFS로 나온 경로를 문자열로 변환해 실제 통과하는 예시 입력 여러 개를 얻고, 그중 하나로 실제 바이너리를 실행해 정말 통과하는지 검증한다(REV-0919).
6. 상태 기계 뒤에 추가로 해시/XOR 검증이 이어진다면(REV-0911, 여러 알고리즘 합성), 상태 기계 통과는 필요조건일 뿐임을 기억하고 다음 단계 검증도 이어서 분석한다.

## 명령어/단축키
```python
from collections import deque

def find_accepting_strings(transition: dict, start: int, accept: set,
                            alphabet: bytes, max_len: int = 12):
    # BFS: (state, path) 큐. 경로 하나라도 찾으면 바로 반환(가장 짧은 예시)
    queue = deque([(start, b"")])
    seen = {(start, 0)}
    while queue:
        state, path = queue.popleft()
        if state in accept and len(path) > 0:
            return path
        if len(path) >= max_len:
            continue
        for c in alphabet:
            nxt = transition.get((state, c), None)
            if nxt is not None and nxt != -1 and (nxt, len(path) + 1) not in seen:
                seen.add((nxt, len(path) + 1))
                queue.append((nxt, path + bytes([c])))
    return None
```
IDA: 상태 변수에 이름을 붙일 때 `N`(rename)으로 `state`처럼 의미 있는 이름으로 바꿔두면 이후 xref 추적이 훨씬 수월하다.

## 출력 해석
- BFS가 경로를 찾아 반환하면 그 바이트열이 이 State Machine을 accept 상태로 통과시키는 최단 예시 입력이다.
- `None`이 반환되면 전이표를 잘못 옮겼거나(오타), 실제로 도달 불가능한 accept 상태를 지정했다는 뜻이므로 전이표를 재확인해야 한다.
- 경로가 여러 개 있을 수 있다는 점을 기억한다 — State Machine은 보통 유일한 정답이 아니라 "패턴에 맞는 모든 문자열"을 통과시키므로, 이후 단계(해시 비교 등)에서 추가로 좁혀야 최종 정답이 나올 수 있다.

## 흔한 실수
- switch 안의 조건이 단순 `==` 비교가 아니라 범위 조건(`isalpha`, `c >= 'a' && c <= 'z'`)인데 이를 개별 문자 256개로 일일이 나열하려는 것 — 범위 조건은 범위 그대로 파이썬 조건식으로 옮기는 게 훨씬 빠르고 실수가 적다.
- trap state(-1)로 가는 전이를 "이 조합은 존재하지 않는다"로 착각해서 표에서 빼먹는 것 — trap state도 명시적인 전이이며, BFS에서 이 전이를 만나면 그 가지를 접어야 한다는 걸 정확히 반영해야 한다.
- 상태 변수를 XOR 누적 변수(REV-0199)나 해시 누적 변수(REV-0906)와 혼동하는 것 — State Machine의 상태값은 보통 작은 정수(0~수십)이고 산술 연산 없이 순수 인덱싱/분기로만 갱신되는 반면, 해시/XOR 누적값은 훨씬 큰 정수 범위를 가지며 산술 연산(곱셈, XOR)으로 갱신된다는 차이로 구분한다.
- 상태 기계 통과가 최종 정답이라고 착각하는 것 — 많은 문제에서 State Machine은 입력 "형식"만 검증하고, 그 뒤에 별도의 해시/암호 비교가 이어져 실제 값까지 검증한다.

## 막혔을 때 다음 체크
- 상태 갱신에 산술 연산(곱셈, XOR)이 섞여 있어 순수 상태 기계가 아닌 것 같다면 → REV-0906 Polynomial Hash 패턴, REV-0199 XOR 반복 변환 역산
- 상태 기계 뒤에 또 다른 검증 단계가 이어진다면 → REV-0911 여러 알고리즘이 순차적으로 합성된 문제 풀어내기
- 이 구조가 사실 바이트코드를 해석하는 더 큰 구조의 일부라면 → REV-0909 가상머신(bytecode VM) 기반 검증 로직 초급 알아보기
- BFS로 찾은 예시 입력이 실제 바이너리에서 통과하는지 확실히 검증하고 싶다면 → REV-0919

## 미니 예제
"숫자 1개 이상 뒤에 알파벳 1개 이상, 그리고 `!`로 끝나야 함" 조건을 검증하는 간단한 State Machine을 재구성해보자.

```python
# state 0: 시작(숫자 대기), state 1: 숫자 받음(숫자 계속 또는 알파벳 전환),
# state 2: 알파벳 받음(알파벳 계속 또는 ! 로 종료), state 3: accept(끝)
transition = {}
for c in range(256):
    ch = chr(c) if 32 <= c < 127 else ''
    if ch.isdigit():
        transition[(0, c)] = 1
        transition[(1, c)] = 1
    if ch.isalpha():
        transition[(1, c)] = 2
        transition[(2, c)] = 2
    if ch == '!':
        transition[(2, c)] = 3

start, accept = 0, {3}
alphabet = bytes(range(32, 127))

result = find_accepting_strings(transition, start, accept, alphabet)
print(result)  # 예: b'0a!' 같은 최단 통과 문자열
```
실제 바이너리에서는 상태 개수가 5~20개, 전이 조건도 더 복잡하지만, 원리는 이 예제와 동일하다 — 전이 규칙을 정확히 표로 옮기고 BFS 한 번이면 통과하는 입력을 기계적으로 찾아낼 수 있다.

## 관련 글
- REV-0196 — strcmp 기반 Flag 검증 패턴
- REV-0199 — XOR 반복 변환 역산
- REV-0906 — Polynomial Hash(다항식 해시) 패턴 알아보기
- REV-0909 — 가상머신(bytecode VM) 기반 검증 로직 초급 알아보기
- REV-0911 — 여러 알고리즘이 순차적으로 합성된 문제 풀어내기
- REV-0919 — 알고리즘 복원 결과를 원본과 바이트 단위로 비교 검증하기

## 출처/검증
- 유한 상태 기계(FSM/DFA)의 표준 정의(상태 집합, 전이 함수, 시작/accept 상태): 형식 언어 및 오토마타 이론(Automata Theory) 표준 교재 수준의 정의 기준.
- 정규표현식 엔진이 내부적으로 DFA/NFA로 컴파일되어 문자 단위 상태 전이로 매칭을 수행하는 구조: 정규표현식 구현의 일반적인 이론적 배경(Thompson's construction 등) 기준 (2026-09-09 검증).
