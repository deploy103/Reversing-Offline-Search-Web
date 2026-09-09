---
id: REV-0987
title: "angr 심볼릭 실행 심화(상태 탐색 전략)"
slug: "rev-0987-angr-advanced-state-exploration"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [angr, Python]
keywords: ["angr exploration technique", "LoopSeer", "Veritesting", "step_func", "simgr.stashes", "angr 상태 관리", "angr 탐색 전략"]
aliases: ["angr 고급 사용법", "angr 상태 탐색", "angr exploration techniques", "angr 실전 활용"]
symptom_keywords: ["angr 탐색이 너무 오래 걸림", "angr 상태가 너무 많아짐", "angr에서 특정 경로만 우선 탐색하고 싶음", "angr stash 관리 어떻게 함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
REV-0271에서 다룬 `simgr.explore(find=..., avoid=...)` 기본 패턴만으로는 반복문이 많거나 상태가 급격히 늘어나는 실제 CTF 바이너리를 감당하기 어려운 경우가 많은데, angr의 **exploration technique**(`LoopSeer`, `Veritesting`, `DFS` 등)과 상태 그룹(`stash`) 직접 조작, `step_func` 콜백을 조합하면 탐색 순서와 자원 사용을 세밀하게 통제할 수 있다.

## 언제 검색해야 하나
- REV-0271의 기본 `explore(find=..., avoid=...)`가 몇 분이 지나도 끝나지 않을 때
- 상태가 너무 많이 갈라져서(`simgr.active`가 수백 개 이상) 메모리/시간이 감당 안 될 때
- 반복문이 많은 함수에서 루프를 몇 바퀴까지만 허용하고 그 이상은 자르고 싶을 때
- 어떤 경로를 먼저 탐색할지(깊이 우선/너비 우선) 직접 제어하고 싶을 때
- `simgr.deadended`, `simgr.errored`에 상태가 쌓이는데 왜 그런지 확인하고 싶을 때

## 핵심 개념
angr의 `SimulationManager`는 상태들을 여러 **스태시(stash)**라는 이름의 리스트로 분류해서 관리한다. 기본적으로 `active`(아직 탐색 중), `found`(목표 도달), `avoid`(회피 대상 도달), `deadended`(더 이상 진행할 명령어가 없음), `errored`(내부 오류 발생) 스태시가 있다. `simgr.explore()`는 이 스태시 관리를 자동으로 해주는 편의 함수일 뿐이고, 그 내부는 결국 `simgr.step()`을 반복 호출하며 각 상태를 한 단계씩 전진시키는 루프다.

### 왜 상태가 폭발하는가
프로그램에 조건 분기(`if`)가 많을수록, 그리고 그 조건에 심볼릭 값이 얽혀 있을수록 하나의 상태가 두 개, 그 두 개가 다시 각각 두 개로 갈라지는 일이 반복된다. 특히 **반복문 안에 심볼릭 조건이 있는 경우** 이론적으로 무한히 갈라질 수 있다. 이를 "상태 공간 폭발(state explosion)"이라 부르며, angr 탐색이 끝나지 않는 가장 흔한 원인이다.

### Exploration Technique — 탐색 전략을 플러그인처럼 교체하기
angr는 `simgr.use_technique(technique)`으로 탐색 알고리즘 자체를 바꿔 끼울 수 있게 설계되어 있다.

- **`angr.exploration_techniques.DFS()`** — 깊이 우선 탐색으로 전환한다. 기본 `explore()`는 사실상 너비 우선에 가깝게 모든 활성 상태를 매 스텝마다 같이 전진시키는데, 목표가 명확히 한쪽 방향에 있다고 예상되면 DFS가 더 빨리 답을 찾을 수 있다.
- **`angr.exploration_techniques.LoopSeer(bound=N)`** — 특정 루프를 N번 넘게 반복하는 상태를 자동으로 스핀(spin) 스태시로 격리해서, 무한/과도 반복으로 인한 상태 폭발을 억제한다.
- **`angr.exploration_techniques.Veritesting()`** — 여러 갈래로 나뉜 상태를 다시 하나로 합치는(state merging) 최적화 기법을 자동 적용해서, 분기가 많은 코드에서 상태 수 자체를 줄여준다.
- **`angr.exploration_techniques.Explorer(find=..., avoid=...)`** — `simgr.explore()`가 내부적으로 쓰는 바로 그 기법이며, 직접 등록해서 다른 기법과 조합할 수 있다.

### step_func — 매 스텝마다 개입하기
`simgr.explore(step_func=콜백함수)`를 쓰면, 매 스텝이 끝날 때마다 지정한 콜백이 호출되어 현재 `simgr` 상태를 관찰하거나 스태시를 직접 조작할 수 있다. 예를 들어 `active` 상태 수가 임계치를 넘으면 오래된 상태를 강제로 버리는 식의 커스텀 전략을 여기서 구현한다.

## 화면/코드에서 보이는 징후
- `from angr.exploration_techniques import DFS, LoopSeer, Veritesting`처럼 기법 클래스를 개별 import한다.
- `simgr.use_technique(LoopSeer(bound=5))`처럼 기법 객체를 만들어 등록하는 코드가 있다.
- `simgr.explore(find=addr, step_func=my_callback)`처럼 `step_func` 인자가 추가로 전달된다.
- 콜백 함수 안에서 `simgr.active`, `simgr.stashes['spinning']`, `len(simgr.active)` 같은 표현이 등장한다.

## 가장 먼저 할 것
탐색이 끝나지 않을 때 가장 먼저 `step_func`로 매 스텝마다 `len(simgr.active)`를 출력해서, 상태 수가 실제로 계속 늘어나는지(폭발 중인지) 아니면 특정 지점에서 멈춰 있는지(무한루프에 갇혔는지)부터 구분한다. 이 진단 없이 바로 여러 기법을 조합하면 무엇이 효과가 있었는지 알 수 없다.

## 단계별 절차

**1) 상태 수 모니터링으로 진단**

```python
import angr

proj = angr.Project('./chall', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)

def report(simgr):
    print(f"active={len(simgr.active)} deadended={len(simgr.deadended)} errored={len(simgr.errored)}")
    return simgr

simgr.explore(find=0x401236, avoid=0x401250, step_func=report)
```

이 콜백이 반복 실행되며 `active` 숫자가 스텝마다 기하급수적으로 늘어난다면 상태 폭발이 진행 중이라는 뜻이다.

**2) LoopSeer로 반복문 폭발 억제**

```python
import angr
from angr.exploration_techniques import LoopSeer

proj = angr.Project('./chall', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)

# 같은 루프를 5바퀴 넘게 도는 상태는 'spinning' 스태시로 격리
simgr.use_technique(LoopSeer(bound=5))

simgr.explore(find=0x401236, avoid=0x401250)

if simgr.found:
    print(simgr.found[0].posix.dumps(0))
else:
    print('spinning states:', len(simgr.stashes.get('spinning', [])))
```

**3) Veritesting으로 상태 병합**

```python
import angr
from angr.exploration_techniques import Veritesting

proj = angr.Project('./chall', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)

simgr.use_technique(Veritesting())
simgr.explore(find=0x401236, avoid=0x401250)

if simgr.found:
    print(simgr.found[0].posix.dumps(0))
```

**4) DFS로 탐색 순서 변경**

```python
import angr
from angr.exploration_techniques import DFS

proj = angr.Project('./chall', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)

simgr.use_technique(DFS())
simgr.explore(find=0x401236, avoid=0x401250)
```

**5) 여러 기법 조합 + 커스텀 step_func로 강제 가지치기**

```python
import angr
from angr.exploration_techniques import LoopSeer

proj = angr.Project('./chall', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)
simgr.use_technique(LoopSeer(bound=8))

MAX_ACTIVE = 200

def prune_if_too_many(simgr):
    if len(simgr.active) > MAX_ACTIVE:
        # 오래되었거나 우선순위가 낮은 상태를 일부 버려서 폭발을 억제
        simgr.active = simgr.active[:MAX_ACTIVE]
    return simgr

simgr.explore(find=0x401236, avoid=0x401250, step_func=prune_if_too_many)

if simgr.found:
    print(simgr.found[0].posix.dumps(0))
```

## 명령어/단축키
- `simgr.use_technique(technique_instance)` : 탐색 기법 등록
- `angr.exploration_techniques.DFS()` : 깊이 우선 탐색
- `angr.exploration_techniques.LoopSeer(bound=N)` : 루프 반복 횟수 제한, 초과분은 `spinning` 스태시로 격리
- `angr.exploration_techniques.Veritesting()` : 상태 병합으로 폭발 억제
- `simgr.explore(..., step_func=callback)` : 매 스텝마다 콜백 호출, `simgr`을 받아서 관찰/수정 후 반환
- `simgr.stashes['spinning']`, `simgr.active`, `simgr.deadended`, `simgr.errored` : 상태 그룹 직접 접근
- `simgr.move(from_stash='active', to_stash='deprioritized', filter_func=...)` : 조건에 맞는 상태를 다른 스태시로 이동

## 출력 해석
- `step_func` 콜백에서 출력한 `active` 수가 스텝을 거듭할수록 계속 커지면(예: 10 → 40 → 160) 전형적인 상태 폭발 패턴이다 — `LoopSeer`나 `Veritesting`을 우선 적용해본다.
- `simgr.stashes['spinning']`에 상태가 쌓였다면 `LoopSeer`가 실제로 반복문을 감지해서 격리하고 있다는 뜻이며, 이 안의 상태들도 필요하면 나중에 다시 `active`로 되돌려 탐색을 이어갈 수 있다.
- `simgr.errored`에 상태가 쌓이면 각 항목의 `.error`로 어떤 예외(대개 지원되지 않는 syscall/명령어)가 발생했는지 확인할 수 있다.
- 탐색 후에도 `simgr.found`가 비어 있고 `active`도 0이 됐다면(전부 `deadended`/`errored`로 소진), 목표 주소 자체가 잘못됐거나 그 경로가 애초에 도달 불가능한 것이다.

## 흔한 실수
- 상태 폭발 진단(`step_func`로 active 수 확인) 없이 무작정 여러 기법을 한꺼번에 조합해서 어떤 기법이 실제로 효과가 있었는지 알 수 없게 되는 것.
- `LoopSeer(bound=N)`의 `N`을 너무 작게 잡아서, 실제 정답 경로에 필요한 반복 횟수보다 먼저 상태를 스핀 처리해버려 정답 경로 자체를 놓치는 것.
- `Veritesting`이 항상 빠르게 만들어줄 거라 기대하는 것 — 상태 병합 자체에도 비용이 들어서, 분기가 적은 단순한 바이너리에서는 오히려 오버헤드가 될 수 있다.
- `step_func`에서 `simgr.active`를 직접 잘라내는(pruning) 로직을 넣을 때, 그 안에 실제 정답 경로가 포함된 상태를 실수로 함께 버리는 것.

## 막혔을 때 다음 체크
- 애초에 `find`/`avoid` 기본 사용법이 헷갈리면 → REV-0271 angr 심볼릭 실행 기초
- 특정 주소 도달 조건을 더 정교하게 지정하는 방법이 필요하면 → REV-0988 angr로 특정 주소 도달 조건 찾기(find/avoid)
- 여러 기법을 시도해도 여전히 안 끝난다면, 함수 단위로 범위를 좁혀 `call_state`로 시작하는 것이 상태 폭발 자체를 근본적으로 줄이는 더 확실한 방법일 수 있다(REV-0271 참고).
- 로직이 단순한 산술/비트 문제로 판명되면 → Z3(REV-0268~REV-0270, REV-0985)로 직접 제약조건을 세우는 편이 훨씬 빠를 수 있다.

## 미니 예제
반복문 안에서 입력 문자를 한 글자씩 검증하는 다음과 같은 대상 프로그램을 가정한다.

```c
// loopcheck.c
#include <stdio.h>
#include <string.h>
int main() {
    char buf[9];
    scanf("%8s", buf);
    int ok = 1;
    for (int i = 0; i < 8; i++) {
        if (buf[i] != ("h4ck3rz!"[i])) ok = 0;
    }
    if (ok) printf("Correct!\n");   // 0x401300 (예시)
    else printf("Wrong\n");          // 0x401320 (예시)
    return 0;
}
```

반복문이 있어 기본 `explore()`만으로도 대부분 잘 풀리지만, 입력 길이가 길어지거나 조건이 더 복잡해질 경우를 대비해 `LoopSeer`와 진단용 `step_func`를 함께 적용한 스크립트다.

```python
import angr
from angr.exploration_techniques import LoopSeer

proj = angr.Project('./loopcheck', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)
simgr.use_technique(LoopSeer(bound=10))

def report(simgr):
    print(f"active={len(simgr.active)}")
    return simgr

simgr.explore(find=0x401300, avoid=0x401320, step_func=report)

if simgr.found:
    print('input:', simgr.found[0].posix.dumps(0))
else:
    print('not found; spinning:', len(simgr.stashes.get('spinning', [])))
```

이렇게 `LoopSeer`와 모니터링용 `step_func`를 기본 세트로 함께 써두면, 이후 더 복잡한 반복 구조를 가진 바이너리를 만나더라도 같은 뼈대를 재사용해 빠르게 진단하고 대응할 수 있다.

## 실전 예시: num_find로 정답이 여러 개인 경우 전부 찾기
검증 로직이 헐거워서 "정답으로 인정되는 입력"이 하나가 아니라 여러 개 존재하는 경우가 있다(예: 대소문자를 구분하지 않는 검사, 또는 특정 자리 값은 아예 검사하지 않는 경우). `simgr.explore()`는 기본적으로 `find` 조건을 만족하는 상태를 **딱 하나** 찾으면 멈추는데, `num_find` 인자에 더 큰 값을 주면 그만큼 여러 개의 서로 다른 해를 한 번의 탐색으로 모두 모을 수 있다.

```python
import angr

proj = angr.Project('./loosecheck', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)

FOUND_ADDR = 0x401300   # "Correct!" 출력 직전 주소
AVOID_ADDR = 0x401320    # "Wrong" 출력 직전 주소

# num_find=5: find 조건을 만족하는 상태를 최대 5개까지 모을 때까지 계속 탐색한다
# (활성 상태가 먼저 다 소진되면 5개를 못 채워도 그 시점에서 멈춘다)
simgr.explore(find=FOUND_ADDR, avoid=AVOID_ADDR, num_find=5)

print(f'찾은 해의 개수: {len(simgr.found)}')
for i, found_state in enumerate(simgr.found):
    solution = found_state.posix.dumps(0)
    print(f'  해 {i}: {solution}')
```

`simgr.found`는 리스트이므로, `num_find`를 1보다 크게 주면 `len(simgr.found)`가 1보다 커질 수 있다. 각 원소는 서로 다른 실행 경로에서 같은 목표 주소(`FOUND_ADDR`)에 도달한, 서로 다른 입력값에 대응하는 상태다. 이 값을 반복 출력해보면, 같은 목표 주소로 가는 길이 여러 개 있었다는 것을(즉 검증 로직에 허점이 여러 개 있었다는 것을) 코드 몇 줄로 한꺼번에 확인할 수 있다. 실제 CTF에서는 이 중 어느 것을 넣어도 "Correct!"가 나오므로, `posix.dumps(0)`으로 얻은 여러 후보 중 사람이 읽기 편한(예: 아스키 문자로만 이루어진) 것을 골라 제출하면 된다.

주의할 점은 `num_find`를 무작정 크게 주면, REV-0987 앞부분에서 다룬 상태 폭발 문제와 똑같은 이유로 탐색이 오래 걸릴 수 있다는 것이다. 정말 여러 해가 필요한 상황이 아니라면 기본값(1)을 그대로 쓰는 것이 가장 빠르다.

## 관련 글
- REV-0271 — angr 심볼릭 실행 기초
- REV-0988 — angr로 특정 주소 도달 조건 찾기(find/avoid)
- REV-0991 — angr에서 RecursionError가 발생할 때
- REV-0992 — angr 탐색이 State Explosion으로 끝나지 않을 때

## 출처/검증
- `simgr.use_technique`, `DFS`, `LoopSeer`, `Veritesting`, `step_func`, 스태시(`active`/`deadended`/`errored`/`spinning`) 개념은 angr 공식 문서(docs.angr.io)의 "Exploration Techniques" 및 "The Simulation Manager" 챕터를 기준으로 정리했다(2026-09-09 검증).
- `angr`는 서드파티 패키지이므로 `pip install angr`가 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
- 코드 예제는 `pip install angr` 환경의 표준 CPython 3에서 그대로 재현 가능하다(단, 목표 주소는 대상 바이너리에 맞게 실제로 확인해서 교체해야 한다).
