---
id: REV-0271
title: "angr 심볼릭 실행 기초"
slug: "rev-0271-angr-basics"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python, angr, Z3]
keywords: ["angr", "심볼릭 실행", "symbolic execution", "entry_state", "simgr.explore", "find avoid", "simgr.found", "바이너리 자동 풀이"]
aliases: ["angr 사용법", "angr 기초", "심볼릭 실행 파이썬", "angr find avoid 예제"]
symptom_keywords: ["angr 어떻게 씀", "심볼릭 실행이 뭔지 모르겠음", "find avoid 어떻게 지정함", "angr 결과 어떻게 꺼냄", "로직이 너무 복잡해서 z3로 못 옮기겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`angr`는 바이너리를 실제로 명령어 단위로 실행하면서 입력값 자체를 미지수(심볼릭 값)로 취급하는 **심볼릭 실행(symbolic execution)** 프레임워크로, 검증 로직을 사람이 손으로 Z3 코드로 옮길 필요 없이 "이 주소(성공 경로)에는 도달하고 저 주소(실패 경로)는 피하는 입력값이 뭔지" 자동으로 탐색해서 알아낼 수 있다.

## 언제 검색해야 하나
- 검증 로직이 반복문, 재귀, 여러 단계의 분기로 너무 복잡하게 얽혀 있어서 Z3 제약조건으로 손수 옮기는 게(REV-0268~REV-0270) 현실적으로 너무 오래 걸릴 때
- 로직 자체가 손으로 역연산하기 어려운, 즉 REV-0221에서 다루는 "역연산 불가능"에 가까운 구조(해시, 비가역 비트 연산 등)라서 아예 정방향으로 실행시켜 답을 찾아야 할 때
- "이 주소는 통과하고 저 주소(예: Wrong 출력 직전)는 피해야 한다"처럼 도달 가능성 자체를 조건으로 풀고 싶을 때
- 소스코드 없이 바이너리만 있는 상태에서, 함수 내부 로직을 하나하나 리버싱하지 않고 자동으로 입력을 찾고 싶을 때

## 핵심 개념
Z3(REV-0268)를 직접 쓰는 방식은 사람이 리버싱한 로직을 먼저 이해하고, 그 로직을 손으로 파이썬 제약조건 코드로 "번역"해야 한다. `angr`는 이 번역 과정 자체를 자동화한다. angr는 바이너리를 로드한 뒤, 실제 CPU가 명령어를 하나씩 실행하듯이 시뮬레이션하되, 특정 메모리 영역(보통 표준입력으로 들어온 사용자 입력)을 **구체적인 값이 아니라 "아직 정해지지 않은 심볼(symbol)"**로 취급한다. 프로그램이 이 심볼릭 값에 대해 `cmp`, `add`, `xor` 같은 연산을 수행할 때마다, angr는 내부적으로 그 연산을 제약조건으로 계속 누적한다. 이 제약조건 누적/해결 엔진은 사실 내부적으로 Z3를 백엔드 솔버로 사용한다 — 즉 angr는 "Z3에 넣을 제약조건을 바이너리 실행 자체로부터 자동으로 뽑아내는 도구"라고 이해하면 정확하다.

프로그램 실행 중 분기(`if`)를 만나면, 조건이 참인 경우와 거짓인 경우 둘 다로 상태(state)가 갈라질 수 있다(이를 상태 공간의 "분기(branching)"라 한다). angr는 이렇게 갈라진 여러 실행 경로(state)들을 동시에 관리하면서, 사용자가 지정한 조건에 맞는 경로를 찾을 때까지 계속 실행을 뻗어나간다.

핵심 객체 세 가지는 다음과 같다.

1. **`angr.Project(path)`** — 바이너리 파일을 로드해서 분석 대상으로 등록한다.
2. **`proj.factory.entry_state()`** — 프로그램의 진입점(entry point)에서 시작하는 초기 실행 상태를 만든다. 이때 표준입력 등을 심볼릭 값으로 채우도록 옵션을 줄 수 있다.
3. **`proj.factory.simgr(state)`** — "심볼릭 매니저(simulation manager)"를 만든다. 이 객체가 여러 갈래로 나뉜 실행 경로들을 관리하며, `simgr.explore(find=..., avoid=...)`를 호출하면 `find`로 지정한 주소에 도달하는 경로를 찾을 때까지(그리고 `avoid`로 지정한 주소로 가는 경로는 버리면서) 자동으로 계속 실행한다.

탐색이 끝나면 `simgr.found`라는 리스트에 목표 주소에 도달한 상태(state)들이 담긴다. 그 상태의 `state.posix.dumps(0)`(표준입력 0번 파일디스크립터에 실제로 어떤 바이트가 들어갔어야 했는지)를 확인하면, 프로그램이 "성공" 경로로 가기 위해 필요했던 구체적인 입력값을 역산해낼 수 있다.

`angr`가 특히 유용한 상황은 REV-0221(역연산 가능한 알고리즘 판단법)에서 다루는 것처럼 로직이 **역연산이 쉽지 않은 경우**다. AND 연산, 단방향 해시, 정보 손실이 있는 변환처럼 수학적으로 역함수를 구하기 어려운 로직은 Z3 제약조건을 손으로 세우기도 까다롭다. 이럴 때 angr는 실제 바이너리를 정방향으로 계속 실행시키면서 조건을 자동으로 수집하므로, 역함수를 몰라도 답을 찾을 수 있는 경우가 많다. 다만 angr의 탐색도 결국 내부적으로 Z3 SMT 솔버에 의존하므로, 탐색 공간이 지나치게 크거나(예: 긴 반복문, 암호학적 해시) 경로 폭발(state explosion)이 심하면 REV-0220(Meet-in-the-middle)처럼 탐색 공간을 절반으로 쪼개는 알고리즘적 접근이 더 빠를 수도 있다는 점을 함께 고려해야 한다.

## 화면/코드에서 보이는 징후
- `import angr`로 시작하는 스크립트에 `angr.Project('./chall', auto_load_libs=False)`처럼 바이너리를 로드하는 코드가 있다.
- `state = proj.factory.entry_state(stdin=angr.SimFileStream(...))` 또는 단순히 `entry_state()`만 호출하는 코드가 보인다.
- `simgr = proj.factory.simgr(state)` 다음에 `simgr.explore(find=0x401234, avoid=0x401256)`처럼 16진수 주소가 인자로 들어간다 — 이 주소는 보통 "Correct" 출력 직전 주소(find)와 "Wrong" 출력 직전 주소(avoid)다.
- 실행 중 터미널에 `WARNING | ... | Unsupported syscall` 같은 경고가 자주 뜬다 — angr가 모든 시스템 콜/라이브러리 함수를 완벽히 시뮬레이션하지는 못하기 때문에 흔히 나타나는 정상적인 잡음이다.
- `simgr.found[0]`를 꺼내서 `.posix.dumps(0)`을 출력하는 코드로 마무리된다.

## 가장 먼저 할 것
IDA/Ghidra 등으로 대상 바이너리를 먼저 열어서, "성공"을 출력하는 코드 블록의 주소와 "실패"를 출력하는 코드 블록의 주소를 정확히 찾아 적어둔다. angr의 `find`/`avoid`는 이 두 주소를 그대로 쓰는 경우가 가장 단순하고 확실하다. 이 사전 조사 없이 angr부터 돌리면 목표 주소를 몰라 탐색을 어디서 멈춰야 할지 지정할 수 없다.

## 단계별 절차

**1) 설치 확인**

```bash
pip install angr
python3 -c "import angr; print(angr.__version__)"
```

angr는 내부적으로 여러 의존 패키지(z3-solver 포함)를 함께 설치하며, 다른 도구보다 설치 용량이 크고 시간이 오래 걸릴 수 있다.

**2) 대상 프로그램 구조 파악(예시)**

```c
// chall.c
#include <stdio.h>
int main() {
    char buf[16];
    gets(buf);  // 예시 목적의 단순화된 코드
    if (buf[0] == 'C' && buf[1] == 'T' && buf[2] == 'F') {
        printf("Correct!\n");   // 이 주소를 IDA에서 확인: 0x401236 (예시)
    } else {
        printf("Wrong\n");       // 이 주소를 IDA에서 확인: 0x401250 (예시)
    }
    return 0;
}
```

**3) angr 스크립트 작성**

```python
import angr

proj = angr.Project('./chall', auto_load_libs=False)

state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)

FOUND_ADDR = 0x401236   # "Correct!" 출력 직전 주소 (IDA로 확인한 값으로 교체)
AVOID_ADDR = 0x401250   # "Wrong" 출력 직전 주소

simgr.explore(find=FOUND_ADDR, avoid=AVOID_ADDR)

if simgr.found:
    found_state = simgr.found[0]
    solution = found_state.posix.dumps(0)  # 표준입력(fd 0)에 필요했던 실제 바이트
    print('input:', solution)
else:
    print('경로를 찾지 못함 (find/avoid 주소를 다시 확인)')
```

**4) 표준입력을 명시적으로 심볼릭하게 만들기(더 정밀한 제어)**

기본 `entry_state()`도 표준입력을 자동으로 심볼릭하게 다루지만, 입력 길이를 명시적으로 제한하고 싶다면 `SimFileStream` 등을 이용해 더 세밀하게 제어할 수 있다.

```python
import angr

proj = angr.Project('./chall', auto_load_libs=False)
state = proj.factory.entry_state(
    stdin=angr.SimFileStream(name='stdin', content=b'', has_end=False)
)
simgr = proj.factory.simgr(state)
simgr.explore(find=0x401236, avoid=0x401250)

if simgr.found:
    print(simgr.found[0].posix.dumps(0))
```

**5) 함수 하나만 대상으로 시작하기(entry_state 대신 call_state)**

프로그램 전체가 아니라 특정 검증 함수만 테스트하고 싶다면 `call_state()`로 특정 함수 주소에서 바로 시작할 수 있다.

```python
import angr, claripy

proj = angr.Project('./chall', auto_load_libs=False)
arg = claripy.BVS('arg', 32)  # 32비트 심볼릭 인자
state = proj.factory.call_state(0x401100, arg)  # check() 함수 주소로 가정
simgr = proj.factory.simgr(state)
simgr.explore(find=lambda s: s.regs.eax == 1)  # 반환값 eax==1이면 성공

if simgr.found:
    print(simgr.found[0].solver.eval(arg))
```

## 명령어/단축키
- `angr.Project(path, auto_load_libs=False)` : 바이너리 로드(공유 라이브러리 자동 로드는 대부분 꺼두는 것이 빠르고 안정적)
- `proj.factory.entry_state()` : 진입점에서 시작하는 초기 상태
- `proj.factory.call_state(addr, *args)` : 특정 함수 주소에서 인자와 함께 시작하는 상태
- `proj.factory.simgr(state)` : 시뮬레이션 매니저 생성
- `simgr.explore(find=addr, avoid=addr)` : find 도달 시까지 탐색, avoid는 가지치기
- `simgr.found[0]` : 목표에 도달한 첫 번째 상태
- `state.posix.dumps(0)` : 표준입력(fd 0)에 필요했던 구체적 바이트열
- `state.solver.eval(symbolic_var)` : 임의의 심볼릭 값(레지스터, 변수 등)을 구체값으로 평가

## 출력 해석
- `simgr.found`가 비어 있지 않고 리스트에 상태가 있으면 목표 주소에 도달하는 입력을 찾은 것이다.
- `simgr.found`가 계속 비어 있으면(deadended, errored 상태만 쌓임) `find`/`avoid` 주소가 틀렸거나, 프로그램 구조가 예상과 달라 그 경로에 도달하지 못했다는 뜻이다 — `simgr.deadended`, `simgr.errored`를 출력해서 상태가 어디서 멈췄는지 확인한다.
- `WARNING | ... | Unsupported syscall or unsupported library function` 로그는 angr가 해당 함수를 완벽히 모델링하지 못했다는 경고로, 대부분 무시해도 되지만 검증 로직에 핵심적으로 쓰이는 함수(예: 커스텀 암호화 함수를 부르는 외부 라이브러리)라면 결과가 부정확해질 수 있으므로 주의 깊게 봐야 한다.
- 탐색이 몇 분 넘게 끝나지 않는다면 상태 공간이 너무 넓게 갈라지는 "state explosion"이 발생하고 있다는 신호다.

## 흔한 실수
- `find`/`avoid` 주소를 IDA에서 잘못 읽어와서(오프셋과 실제 로드 주소를 혼동, 혹은 PIE 바이너리에서 베이스 주소를 고려하지 않아서) 엉뚱한 곳을 목표로 삼는 경우 — PIE 바이너리는 로드 시 주소가 바뀌므로 IDA에서 본 주소를 그대로 쓰려면 `auto_load_libs=False`와 함께 angr가 계산하는 실제 로드 베이스를 확인해야 한다.
- `auto_load_libs=True`(기본값에 가까운 옵션)로 모든 공유 라이브러리를 실제로 로드하게 둬서 분석이 극도로 느려지거나 불필요한 복잡도가 늘어나는 경우 — 대부분의 CTF 문제에서는 `auto_load_libs=False`로 충분하다.
- 입력 길이 제한이 없는 채로 탐색시켜서 상태 공간이 지수적으로 폭발하는 경우 — 가능하면 `call_state`로 검증 함수만 좁혀서 테스트하거나, 입력 길이를 명시적으로 제한한다.
- 목표 주소를 "Correct 출력 함수 호출 지점"이 아니라 "그 이후의 return 지점"처럼 애매하게 잡아서 탐색이 필요 이상으로 오래 걸리는 경우 — 가능한 한 분기가 갈리는 지점 바로 다음, 가장 좁은 지점을 목표로 잡는 것이 빠르다.
- angr가 Z3보다 무조건 좋다고 생각하고 모든 문제에 angr부터 쓰는 경우 — 로직이 이미 명확히 파악됐고 역연산도 쉬운 단순한 산술/비트 문제라면 REV-0268~REV-0270의 Z3 직접 사용이 훨씬 빠르고 예측 가능하다. angr는 로직 파악 자체가 어렵거나 매우 복잡할 때 쓰는 무거운 도구라는 걸 기억한다.

## 막혔을 때 다음 체크
- 탐색이 끝나지 않는다면 → 목표 함수만 떼어내 `call_state`로 좁혀서 실행 범위를 줄인다.
- `find`/`avoid` 주소가 맞는지 의심스럽다면 → 다시 IDA/Ghidra로 돌아가 "Correct"/"Wrong" 문자열의 xref를 따라 정확한 분기 주소를 재확인한다.
- 로직이 사실 그렇게 복잡하지 않고 손으로 옮길 만하다면 → REV-0268(Z3 BitVec 기초)로 돌아가 직접 제약조건을 세우는 편이 더 빠를 수 있다.
- 로직이 AND 연산이나 해시처럼 애초에 역연산이 안 되는 구조인지 먼저 판단하고 싶다면 → `../algorithms/rev-0221-is-it-invertible.md` 문서에서 역연산 가능 여부 판단 기준을 확인한다.
- 입력 공간이 두 개의 독립적인 절반으로 쪼개지는 구조라 angr 탐색보다 알고리즘적으로 접근하는 게 더 빠를 것 같다면 → `../algorithms/rev-0220-meet-in-the-middle.md` 문서를 참고한다.
- 찾은 입력값을 실제 바이너리에 자동으로 넣어 재검증하고 싶다면 → REV-0266 문서의 `process()`/`sendline()`으로 이어서 자동화한다.

## 미니 예제
표준입력으로 4바이트를 받아 특정 값과 XOR 비교하는 아주 단순한 바이너리를 angr로 자동으로 푸는 전체 흐름이다(실제 주소는 IDA에서 확인한 값으로 바꿔야 한다).

```c
// tiny.c
#include <stdio.h>
int main() {
    unsigned int x;
    scanf("%u", &x);
    if ((x ^ 0x1337) == 0xdead) {
        printf("Correct!\n");   // IDA에서 확인: 0x4011a0
    } else {
        printf("Wrong\n");       // IDA에서 확인: 0x4011c0
    }
    return 0;
}
```

```python
import angr

proj = angr.Project('./tiny', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)

simgr.explore(find=0x4011a0, avoid=0x4011c0)

if simgr.found:
    print(simgr.found[0].posix.dumps(0))
else:
    print('not found')
```

이렇게 얻은 표준입력 바이트열을 그대로 REV-0266의 `p.sendline(...)`에 넣으면 실제 바이너리에서도 "Correct!"가 나오는지 바로 검증할 수 있다.

## 관련 글
- REV-0268 — Z3 BitVec 기초
- REV-0266 — pwntools로 프로세스 실행하고 입력 보내기
- REV-0272 — Capstone으로 디스어셈블 자동화
- ../algorithms/rev-0221-is-it-invertible.md — 역연산 가능한 알고리즘 판단법
- ../algorithms/rev-0220-meet-in-the-middle.md — Meet-in-the-middle를 고려할 상황

## 출처/검증
- `angr` 공식 문서(docs.angr.io)의 `Project`, `entry_state`, `simgr.explore`, `SimulationManager.found` API를 기준으로 정리했다(2026-09-08 검증).
- angr가 내부적으로 SMT 솔버(Z3)를 사용해 제약조건을 해결한다는 사실은 angr 공식 문서의 아키텍처 설명과 일치한다.
- `angr`는 서드파티 패키지이므로 `pip install angr`가 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다. angr는 설치 용량이 크고 의존성이 많으므로 오프라인 준비 시 특히 시간을 넉넉히 잡아야 한다.
- 코드 예제는 `pip install angr` 환경의 표준 CPython 3에서 그대로 재현 가능하다(단, `find`/`avoid` 주소는 대상 바이너리에 맞게 실제로 확인해서 교체해야 한다).
