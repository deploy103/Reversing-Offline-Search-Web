---
id: REV-0992
title: "angr 탐색이 State Explosion으로 끝나지 않을 때"
slug: "rev-0992-angr-state-explosion"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [angr, Python]
keywords: ["angr state explosion", "angr 탐색이 안 끝남", "simgr.active 급증", "angr 메모리 부족", "angr 무한 대기"]
aliases: ["angr 상태 폭발", "angr 탐색 무한대기", "angr 메모리 터짐", "angr explore 안끝남"]
symptom_keywords: ["angr가 몇 시간째 안 끝남", "메모리 사용량이 계속 늘어남", "simgr.active 개수가 계속 커짐", "angr 스크립트가 멈춘 것처럼 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`simgr.explore()`가 몇 분/몇 시간이 지나도 끝나지 않고 메모리 사용량만 계속 늘어난다면, 이는 대상 프로그램의 분기/반복 구조가 심볼릭 실행 상태를 기하급수적으로 갈라지게 만드는 **상태 공간 폭발(state explosion)**이 진행 중이라는 뜻이며, 무작정 오래 기다리는 대신 `find`/`avoid` 주소를 재확인하고 탐색 범위를 좁히거나 전용 기법을 적용해야 한다.

## 언제 검색해야 하나
- `simgr.explore()`를 실행했는데 몇 분이 지나도 끝나지 않을 때
- 작업관리자/`top`에서 파이썬 프로세스의 메모리 사용량이 계속 증가하는 게 보일 때
- `simgr.active`의 상태 개수를 출력해보니 스텝을 거듭할수록 계속 커질 때
- 단순해 보이는 바이너리인데도 angr가 유난히 오래 걸릴 때

## 핵심 개념
angr는 프로그램의 조건 분기를 만날 때마다 그 분기가 심볼릭 값에 의존하면 상태를 둘로 쪼갠다. 이 분기가 반복문 안에 있거나 여러 단계로 중첩되면, 상태 수가 이론적으로 지수적으로 늘어날 수 있다. 이것이 상태 공간 폭발이며, angr가 "느린 것"이 아니라 "탐색해야 할 경로 자체가 실제로 매우 많아진 것"이다.

가장 흔한 원인 세 가지는 다음과 같다.
- **`find`/`avoid` 주소가 틀렸거나 너무 늦은 지점(도달 자체가 매우 드문 경로)을 가리키는 경우** — 목표에 도달하는 경로 자체가 희박해서, 그 경로를 찾기 전에 무수히 많은 다른 경로들이 먼저 갈라진다.
- **전체 프로그램을 `entry_state()`로 시작해서 불필요한 초기화 코드/라이브러리 코드까지 심볼릭하게 실행하는 경우** — 검증 로직과 무관한 코드에서도 상태가 갈라진다.
- **반복문의 반복 횟수 자체에 제한이 없는 경우** — 매 반복마다 상태가 갈라지면 이론상 무한히 계속될 수 있다.

## 화면/코드에서 보이는 징후
- 터미널이 아무 출력 없이 멈춰 있는 것처럼 보인다(`explore()`가 끝나지 않아서).
- `htop`/작업관리자에서 파이썬 프로세스 메모리가 계속 늘어난다.
- `step_func`로 `len(simgr.active)`를 출력해보면 스텝마다 값이 크게 증가한다.
- `WARNING | ... | Unsupported syscall` 경고가 반복적으로 쏟아진다(핵심 원인은 아니지만 함께 관찰되는 경우가 많다).

## 가장 먼저 할 것
바로 몇 시간을 더 기다리지 말고, `step_func`로 `len(simgr.active)`를 스텝마다 출력해서 상태 수가 실제로 계속 커지는지부터 확인한다. 커지고 있다면 즉시 스크립트를 중단하고 아래 대응책을 적용한다.

## 단계별 절차
1. 스크립트를 중단하고, `step_func`로 상태 수 증가 추이를 먼저 확인한다(REV-0987의 진단 코드 참고).
2. `find`/`avoid` 주소가 정확한지 다시 확인한다 — 특히 PIE 바이너리라면 로드 베이스 보정을 빠뜨리지 않았는지 REV-0988을 참고해 재확인한다.
3. 전체 프로그램이 아니라 검증 함수만 `call_state`로 좁혀서 시작한다.
4. `angr.exploration_techniques.LoopSeer(bound=N)`으로 반복 횟수를 제한한다.
5. `Veritesting()`으로 상태 병합을 시도해본다.
6. 그래도 안 되면, 애초에 이 로직이 angr보다 Z3로 직접 제약조건을 세우는 편이 나은 단순한 산술/비트 문제는 아닌지 재검토한다.
7. 로직이 정말 복잡해서 심볼릭 실행이 불가피하다면, 입력 길이를 인위적으로 최대한 줄여서(예: 원래 32바이트 대신 4바이트로 축소한 테스트 바이너리) 먼저 기법이 통하는지 소규모로 검증한 뒤 범위를 늘려간다.

## 명령어/단축키
```python
def report(simgr):
    print(f"active={len(simgr.active)} deadended={len(simgr.deadended)}")
    return simgr

simgr.explore(find=addr, avoid=avoid_addr, step_func=report)
```
```python
from angr.exploration_techniques import LoopSeer, Veritesting
simgr.use_technique(LoopSeer(bound=10))
simgr.use_technique(Veritesting())
```
```python
# 함수 단위로 좁혀서 시작(전체 프로그램 대신)
state = proj.factory.call_state(CHECK_FUNC_ADDR, symbolic_arg)
```

## 출력 해석
- `active` 수가 스텝마다 뚜렷하게 커지는 패턴(예: 5 → 20 → 90)이 보이면 확실한 상태 폭발이다.
- `active`는 안 커지는데 `deadended`/`errored`만 계속 쌓이면서 안 끝난다면, 폭발이 아니라 그냥 탐색해야 할 경로 수 자체가 유한하지만 많은 것일 수 있다 — 이 경우는 `call_state`로 범위를 좁히는 것이 더 효과적이다.
- `LoopSeer` 적용 후 `simgr.stashes['spinning']`에 상태가 쌓이기 시작하면, 반복문이 실제 원인이었다는 것이 확인된 것이다.

## 흔한 실수
- 상태 수를 확인하지 않고 그냥 "느린가보다" 하며 몇 시간이고 계속 기다리는 것.
- `find`/`avoid` 주소가 틀린 걸 모르고, 진짜 원인(잘못된 목표 주소)을 상태 폭발 탓으로 돌려 엉뚱한 최적화만 시도하는 것.
- 전체 프로그램을 계속 `entry_state()`로 실행하면서, 정작 필요한 것은 검증 함수 하나뿐이라는 걸 뒤늦게 깨닫는 것.
- `LoopSeer`의 `bound`를 정답에 필요한 반복 횟수보다 작게 잡아서 정답 경로 자체를 스핀 처리해 놓치는 것.
- 다양한 기법을 순서 없이 한꺼번에 적용해서 어떤 조치가 실제로 효과가 있었는지 알 수 없게 만드는 것.

## 막혔을 때 다음 체크
- 상태 폭발 대응 기법들을 더 자세히 알고 싶으면 → REV-0987 angr 심볼릭 실행 심화(상태 탐색 전략)
- `find`/`avoid` 주소 계산 자체가 의심스럽다면 → REV-0988 angr로 특정 주소 도달 조건 찾기(find/avoid)
- 재귀 오류까지 함께 발생한다면 → REV-0991 angr에서 RecursionError가 발생할 때
- 결국 로직이 단순하다고 판단되면 → REV-0268 Z3 BitVec 기초로 직접 제약조건을 세우는 편이 나을 수 있다

## 미니 예제
전체 프로그램을 `entry_state()`로 실행하다 상태 폭발을 겪고, 함수 단위로 좁혀서 해결하는 전형적인 흐름이다.

```python
import angr

proj = angr.Project('./chall', auto_load_libs=False)

# 1차 시도: 전체 프로그램 (상태 폭발 발생 가능)
# state = proj.factory.entry_state()
# simgr = proj.factory.simgr(state)
# simgr.explore(find=0x401500, avoid=0x401520)  # 몇 분째 안 끝남

# 2차 시도: 검증 함수만 좁혀서 시작
import claripy

CHECK_ADDR = 0x401100  # 예: int check(int x) 함수 주소
arg = claripy.BVS('arg', 32)
state = proj.factory.call_state(CHECK_ADDR, arg)
simgr = proj.factory.simgr(state)

def report(simgr):
    print('active:', len(simgr.active))
    return simgr

simgr.explore(find=lambda s: s.solver.eval(s.regs.eax) == 1, step_func=report)

if simgr.found:
    print('answer:', simgr.found[0].solver.eval(arg))
```

전체 프로그램 대신 검증 함수 하나만 대상으로 좁히는 것만으로도 상태 폭발 문제가 사라지는 경우가 실전에서 매우 흔하다.

### 에러를 재현하는 잘못된 코드 vs 고쳐서 정상 동작하는 코드
실제 angr가 상태를 지수적으로 늘리는 과정을 그대로 재현하려면 몇 시간이 걸리거나 메모리를 다 써버릴 수 있으므로, 여기서는 "조건 분기를 만날 때마다 상태 수가 2배로 늘어난다"는 핵심 동작만 순수 파이썬으로 안전하게 흉내낸다. 외부 라이브러리 없이 파이썬 3만 있으면 그대로 실행되며, 실제 메모리를 많이 쓰지 않도록 상태는 리스트가 아니라 정수(개수)로만 다룬다.

**잘못된 코드 — 반복(분기) 횟수에 아무 제한이 없어 상태 수가 기하급수적으로 폭발**
```python
class StateExplosionError(Exception):
    """실제로는 angr가 메모리를 계속 늘리며 멈추지 않는 상황을, 예제에서는
    상태 수가 감당 못할 만큼 커진 시점에 일부러 예외를 던져서 확인하기 쉽게 만든 것이다."""
    pass

def explore_no_bound(steps, max_states=1_000_000):
    """angr가 조건 분기를 만날 때마다 상태를 둘로 쪼개는 것을 단순화해서 흉내낸 함수.
    LoopSeer 같은 반복 제한이 전혀 없으면 상태 수가 2**step으로 계속 커진다."""
    state_count = 1   # 처음에는 상태가 1개(entry_state 하나)뿐이다
    for step in range(steps):
        state_count *= 2   # 분기를 만날 때마다 상태가 2배로 늘어남(제한 없음)
        print(f'step {step}: 활성 상태 수 = {state_count}')
        if state_count > max_states:
            # 실제 angr였다면 이 시점부터 메모리 사용량이 계속 늘어나며 멈추지 않았을 것이다.
            raise StateExplosionError(f'상태 수가 {state_count}개로 폭발함 (step={step})')
    return state_count

try:
    explore_no_bound(steps=30)   # 2**20 = 약 105만 시점에서 max_states(100만)를 넘어 예외 발생
except StateExplosionError as e:
    print('에러 발생:', e)
```

**고친 코드 — LoopSeer(bound=N)처럼 일정 횟수 이후로는 상태를 더 쪼개지 않고 접어버림**
```python
def explore_with_loopseer(steps, bound):
    """angr의 LoopSeer(bound=N) 기법이 하는 일을 단순화해서 흉내낸 함수.
    bound번째 분기까지만 실제로 상태를 쪼개고, 그 이후로는 상태 수를 더 늘리지 않는다
    (LoopSeer는 실제로는 그 반복 상태를 'spinning' 스태시에 보류시킨다)."""
    state_count = 1
    for step in range(steps):
        if step < bound:
            state_count *= 2   # bound에 도달하기 전까지만 정상적으로 분기시킴
        # bound 이후에는 더 쪼개지 않고 그대로 유지 (LoopSeer가 반복을 접어버리는 것과 같은 효과)
        print(f'step {step}: 활성 상태 수 = {state_count}')
    return state_count

final_count = explore_with_loopseer(steps=30, bound=10)
print('최종 활성 상태 수:', final_count)   # 2**10 = 1024로 억제되어 예외 없이 끝까지 실행됨
```
`bound` 값을 10으로 제한한 두 번째 스크립트는 30단계를 전부 돌고도 상태 수가 1024개에서 멈추고, `StateExplosionError` 없이 끝까지 실행된다. 실제 angr 코드에서 이 역할을 하는 것이 바로 이 글의 "명령어/단축키" 절에 있는 `simgr.use_technique(LoopSeer(bound=10))`이며, 위 두 함수는 그 기법이 왜 상태 폭발을 억제하는지를 angr 없이도 직접 확인시켜주기 위한 것이다.

## 관련 글
- REV-0987 — angr 심볼릭 실행 심화(상태 탐색 전략)
- REV-0988 — angr로 특정 주소 도달 조건 찾기(find/avoid)
- REV-0991 — angr에서 RecursionError가 발생할 때
- REV-0271 — angr 심볼릭 실행 기초

## 출처/검증
- 상태 공간 폭발(state explosion) 개념과 `LoopSeer`/`Veritesting`을 통한 완화 기법은 angr 공식 문서(docs.angr.io)의 "Exploration Techniques" 챕터를 기준으로 정리했다(2026-09-09 검증).
- `call_state`로 함수 단위 분석 범위를 좁히는 방법은 angr 공식 문서의 "Working with States" 설명 기준.
