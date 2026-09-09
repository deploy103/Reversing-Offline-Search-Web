---
id: REV-0991
title: "angr에서 RecursionError가 발생할 때"
slug: "rev-0991-angr-recursionerror"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [angr, Python]
keywords: ["angr RecursionError", "maximum recursion depth exceeded", "sys.setrecursionlimit", "angr claripy 재귀 오류", "angr 깊은 제약조건"]
aliases: ["angr 재귀 오류", "RecursionError angr", "angr maximum recursion depth", "angr claripy 오류"]
symptom_keywords: ["RecursionError: maximum recursion depth exceeded", "angr 실행 중 재귀 오류로 죽음", "claripy 관련 재귀 오류", "탐색 중간에 파이썬 재귀 에러가 남"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
angr 탐색 도중 파이썬의 `RecursionError: maximum recursion depth exceeded`가 발생하는 것은 대부분 심볼릭 제약조건 트리(claripy 표현식)가 반복문/재귀 실행으로 인해 매우 깊게 중첩되어, 이를 내부적으로 재귀 순회하는 파이썬 함수(제약조건 단순화, 직렬화 등)의 호출 스택 한도를 초과했기 때문이며, angr 버그라기보다 탐색 범위가 지나치게 넓어졌다는 신호로 봐야 한다.

## 언제 검색해야 하나
- `simgr.explore()` 실행 중 갑자기 `RecursionError: maximum recursion depth exceeded`로 스크립트가 죽을 때
- 이 오류가 특정 상태에서만, 특히 긴 반복문을 통과한 뒤에 발생할 때
- `sys.setrecursionlimit()`을 늘려서 임시로 해결했는데 다시 다른 지점에서 같은 오류가 날 때
- claripy 관련 스택트레이스와 함께 오류가 뜰 때

## 핵심 개념
Z3에 넘길 제약조건(claripy 표현식)은 내부적으로 트리 구조로 표현된다. `x + 1 + 1 + 1 + ...`처럼 같은 연산이 반복문 안에서 계속 누적되면, 이 표현식 트리의 깊이가 반복 횟수만큼 계속 깊어진다. 파이썬의 여러 내부 함수(표현식 단순화, 재귀적 해시 계산, 문자열 변환 등)는 이런 트리를 재귀 함수로 순회하는데, 파이썬은 기본적으로 재귀 호출 깊이를 약 1000단계 정도로 제한한다(`sys.getrecursionlimit()`). 반복문이 수백~수천 번 도는 로직을 심볼릭하게 실행하면 이 한계를 쉽게 넘어선다.

즉 이 오류는 대개 **탐색 범위 자체가 반복 횟수 대비 너무 넓다**는 신호이며, 단순히 재귀 한도를 늘리는 것은 임시방편일 뿐 근본 해결책이 아닌 경우가 많다. 진짜 해결책은 반복 횟수를 제한하거나(REV-0987의 `LoopSeer`), 함수 단위로 탐색 범위를 좁히거나, 제약조건이 커지기 전에 주기적으로 단순화하는 것이다.

## 화면/코드에서 보이는 징후
- 스크립트 출력 마지막에 `RecursionError: maximum recursion depth exceeded`와 함께 길게 이어지는 스택트레이스가 뜬다.
- 스택트레이스 안에 `claripy`, `ast`, `simplify` 같은 이름이 반복적으로 등장한다.
- 특정 반복 횟수(예: 1000번 이상 도는 루프) 이후에만 이 오류가 재현된다.
- `sys.setrecursionlimit(10000)`처럼 임시로 늘린 코드가 있는데도 결국 다시 발생한다.

## 가장 먼저 할 것
오류가 나기 직전까지 `step_func`로 상태를 관찰해서, 어떤 반복문/함수에서 이 문제가 생기는지부터 특정한다. 무작정 재귀 한도부터 늘리지 말고, 그 반복 구조 자체를 `LoopSeer`로 제한할 수 있는지 먼저 살펴본다.

## 단계별 절차
1. 오류가 발생하는 시점을 `step_func`나 반복적인 `print`로 좁혀서, 어떤 반복문/함수 근처인지 확인한다.
2. `angr.exploration_techniques.LoopSeer(bound=N)`를 적용해서 해당 반복문의 실행 횟수를 제한한다(REV-0987 참고).
3. 함수 전체가 아니라 문제되는 검증 함수만 `call_state`로 좁혀서 실행 범위를 줄인다.
4. 그래도 필요하다면 `sys.setrecursionlimit()`을 임시로 늘리되, 이는 문제를 감추는 것이지 근본 해결이 아님을 인지하고 병행 대책(3번)을 함께 적용한다.
5. 표현식이 지나치게 커지는 게 확실하다면, 상태를 주기적으로 `state.solver.simplify()`(또는 유사한 단순화 호출)로 정리해서 트리 깊이를 관리한다.
6. 반복 자체가 문제의 핵심이 아니라 값 자체를 역산하는 문제라면, 애초에 angr 대신 Z3로 직접 제약조건을 세우는 것(REV-0268~REV-0270)이 이 문제를 원천적으로 피하는 방법일 수 있다.

## 명령어/단축키
```python
import sys
sys.setrecursionlimit(10000)   # 임시 완화(근본 해결 아님)

from angr.exploration_techniques import LoopSeer
simgr.use_technique(LoopSeer(bound=20))   # 반복 횟수 자체를 제한(더 근본적)
```

## 출력 해석
- 스택트레이스에 `claripy.ast` 관련 함수가 수백~수천 번 반복해서 찍혀 있다면, 제약조건 트리 깊이 문제라는 확실한 신호다.
- `LoopSeer` 적용 후 같은 오류가 사라졌다면, 반복 횟수가 실제 원인이었다는 뜻이다.
- `sys.setrecursionlimit()`을 크게 늘렸는데도 결국 인터프리터 자체가 크래시(세그먼트 폴트급 스택 오버플로우)한다면, 이는 파이썬 자체의 C 스택 한계에 부딪힌 것이므로 재귀 한도를 늘리는 방식으로는 해결할 수 없고 반드시 탐색 범위를 줄여야 한다.

## 흔한 실수
- `sys.setrecursionlimit()`만 계속 키우면서 근본 원인(반복 범위)을 들여다보지 않는 것 — 결국 더 큰 값에서 같은 문제가 재발한다.
- 재귀 한도를 지나치게 크게 설정해서 실제 스택 오버플로우로 파이썬 인터프리터 자체가 죽는(`Segmentation fault`) 상황을 만드는 것.
- 문제되는 반복문을 특정하지 않고 전체 프로그램에 `LoopSeer`를 걸어 정작 필요한 반복까지 과도하게 제한해버리는 것.
- 이 오류를 angr 버그로 오해해서 다른 angr 버전으로 계속 바꿔가며 시도하는 것 — 대부분 근본 원인은 탐색 범위 문제다.

## 막혔을 때 다음 체크
- 반복문으로 인한 상태 폭발/재귀 문제를 근본적으로 제어하는 방법이 궁금하면 → REV-0987 angr 심볼릭 실행 심화(상태 탐색 전략)
- 기본 개념 자체가 헷갈리면 → REV-0271 angr 심볼릭 실행 기초
- 상태가 아예 안 끝나고 계속 쌓이기만 한다면 → REV-0992 angr 탐색이 State Explosion으로 끝나지 않을 때

## 미니 예제
아래처럼 반복 횟수가 매우 많은 검증 로직을 심볼릭 실행하면 `RecursionError`가 재현되기 쉽다.

```c
// heavy_loop.c
int main() {
    int x;
    scanf("%d", &x);
    int acc = x;
    for (int i = 0; i < 5000; i++) {
        acc = acc + 1;   // 심볼릭 표현식이 반복마다 계속 깊어짐
    }
    if (acc == 12345) printf("Correct!\n");
    else printf("Wrong\n");
    return 0;
}
```

```python
import angr
from angr.exploration_techniques import LoopSeer

proj = angr.Project('./heavy_loop', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)

# LoopSeer 없이 그냥 explore()만 돌리면 RecursionError가 날 가능성이 큼
simgr.use_technique(LoopSeer(bound=50))

simgr.explore(find=0x401300, avoid=0x401320)  # 실제 주소는 대상에 맞게 확인
if simgr.found:
    print(simgr.found[0].posix.dumps(0))
```

이 경우처럼 반복 횟수 자체가 크고 매번 산술 연산이 누적되는 구조라면, `LoopSeer`로 반복을 적절히 제한하거나 아예 Z3로 `acc = x + 5000`이라는 최종 관계식을 직접 세워 푸는 것(REV-0268)이 훨씬 안전하고 빠르다.

## 관련 글
- REV-0987 — angr 심볼릭 실행 심화(상태 탐색 전략)
- REV-0271 — angr 심볼릭 실행 기초
- REV-0992 — angr 탐색이 State Explosion으로 끝나지 않을 때
- REV-0268 — Z3 BitVec 기초

## 출처/검증
- 파이썬의 재귀 호출 깊이 제한(`sys.getrecursionlimit`/`setrecursionlimit`) 동작은 CPython 공식 문서("sys — System-specific parameters and functions")를 기준으로 정리했다(2026-09-09 확인).
- claripy 표현식 트리 구조 및 `LoopSeer`를 통한 반복 제한은 angr 공식 문서(docs.angr.io)의 "Symbolic Expressions and Constraint Solving", "Exploration Techniques" 챕터 기준.
