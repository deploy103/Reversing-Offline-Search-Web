---
id: REV-0910
title: "재귀적으로 정의된 검증 함수 풀어내기"
slug: "rev-0910-recursive-validation-function"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["재귀 함수 리버싱", "recursive validation", "재귀 호출 스택", "call self", "재귀를 반복문으로", "recursion to iteration", "메모이제이션"]
aliases: ["재귀 크랙미 알아보기", "함수가 자기 자신을 호출함", "재귀 호출 스택 프레임 분석", "recursion 풀어내기"]
symptom_keywords: ["함수 안에서 자기 자신의 주소를 call함", "스택이 함수 깊이만큼 계속 쌓임", "재귀 종료 조건을 못 찾겠음", "재귀 호출 인자가 계속 바뀜"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
재귀적으로 정의된 검증 함수는 자기 자신의 주소를 다시 `call`하는 함수이며, 스택 프레임이 호출 깊이만큼 계속 쌓이는 구조를 이해하고 base case(종료 조건)와 recursive case(자기 호출 시 인자 변화)만 정확히 뽑아내면, x86 콜스택을 눈으로 따라가지 않고도 파이썬 재귀 함수 또는 반복문으로 그대로 옮겨 풀 수 있다.

## 언제 검색해야 하나
- 디스어셈블리에서 함수 안의 `call` 명령 대상 주소가 그 함수 자신의 시작 주소와 같을 때(자기 재귀, self-recursion)
- GDB로 `bt`(backtrace)를 찍었을 때 같은 함수 이름이 스택에 수십~수백 번 반복해서 쌓여 있을 때
- 디컴파일 결과에 `if (조건) return 기본값; else return f(변형된 인자);` 형태의 짧은 함수가 있을 때
- 입력 길이가 길어질수록 실행 시간이나 스택 사용량이 눈에 띄게 늘어나는 검증 로직을 만났을 때

## 핵심 개념

### 재귀 함수의 두 부분 — base case와 recursive case
모든 재귀 함수는 반드시 다음 두 부분으로 나뉜다.

1. **base case(종료 조건)**: 더 이상 자기 자신을 호출하지 않고 바로 값을 반환하는 조건. 이게 없으면 무한 재귀(스택 오버플로)로 프로그램이 죽는다.
2. **recursive case(재귀 단계)**: 문제를 더 작은 부분 문제로 줄인 다음 자기 자신을 호출하고, 그 결과를 이용해 현재 단계의 답을 만드는 부분.

디스어셈블리/디컴파일에서 재귀 함수를 만나면 가장 먼저 할 일은 이 두 부분을 분리해서 적는 것이다.

```c
// 전형적인 재귀 검증 함수 골격
int verify(const char *s, int idx, int acc) {
    if (s[idx] == '\0') {           // base case
        return acc == TARGET;
    }
    int new_acc = transform(acc, s[idx]);  // 이번 문자로 acc 갱신
    return verify(s, idx + 1, new_acc);    // recursive case: idx+1로 재귀
}
```

이 형태는 사실 REV-0198(문자별 for 루프 검증 패턴)의 재귀 버전에 불과하다 — `for` 루프 대신 재귀 호출로 반복을 표현했을 뿐, 매 단계 하는 일(`transform`)은 동일하다. 이런 "꼬리 재귀(tail recursion)" 형태는 컴파일러가 최적화 옵션에 따라 실제로는 루프(jmp)로 변환해버리기도 하므로, 어셈블리에서 `call`이 아니라 함수 시작 지점으로의 `jmp`만 보이는 경우도 있다 — 이 역시 재귀의 흔적이다.

### 재귀가 단순 루프보다 복잡해지는 경우 — 트리형 재귀
어떤 재귀는 한 번 호출에서 자기 자신을 두 번 이상 호출한다(예: `f(n) = f(n-1) + f(n-2)`처럼 피보나치형). 이런 트리형 재귀는 계산 그래프가 트리 모양으로 뻗어나가므로, 단순히 `for` 루프로 바꾸기 어렵고 실행 시간이 지수적으로 증가할 수 있다. 이 경우 다음 두 가지를 반드시 확인해야 한다.

1. **같은 부분 문제가 반복 계산되는가**: 그렇다면 메모이제이션(memoization, 이미 계산한 결과를 캐시)으로 지수 시간을 다항 시간으로 줄일 수 있다.
2. **재귀 깊이가 입력 크기에 비례하는가**: 그렇다면 실제 실행 시 스택 오버플로가 날 수 있으므로, 파이썬으로 재구현할 때 `sys.setrecursionlimit()`을 늘리거나 아예 반복문(명시적 스택 사용)으로 바꿔야 한다.

### 재귀를 반복문으로 바꾸는 법 — 꼬리 재귀의 경우
recursive case가 "재귀 호출 결과를 그대로 리턴"하는 형태(꼬리 재귀)라면, 다음처럼 기계적으로 `while` 루프로 바꿀 수 있다.

```python
# 재귀 버전
def verify(s, idx, acc):
    if idx == len(s):
        return acc == TARGET
    return verify(s, idx + 1, transform(acc, s[idx]))

# 반복문 버전 (재귀 인자가 곧 루프 변수가 됨)
def verify_iter(s):
    idx, acc = 0, INIT_ACC
    while idx < len(s):
        acc = transform(acc, s[idx])
        idx += 1
    return acc == TARGET
```

재귀 호출의 인자(`idx+1`, 갱신된 `acc`)가 그대로 다음 루프 반복의 변수 갱신이 된다는 점이 핵심이다. 이렇게 바꾸면 스택 깊이 걱정 없이 REV-0198처럼 익숙한 루프 형태로 분석할 수 있다.

### GDB로 재귀 깊이와 인자 변화를 직접 관찰하기
정적으로 base/recursive case를 구분하기 애매하면, 실제 실행 중 재귀가 어떻게 진행되는지 동적으로 관찰하는 게 빠르다. 함수 진입 지점에 브레이크포인트를 걸고 `continue`를 반복하면서 매번 인자 레지스터 값을 출력하면, 어떤 인자가 매 호출마다 어떻게 바뀌는지(감소하는지, 누적되는지) 눈으로 확인할 수 있다.

## 화면/코드에서 보이는 징후
- `call`의 대상 주소가 현재 함수 자신의 시작 주소와 동일
- 함수 프롤로그(`push rbp; mov rbp, rsp; sub rsp, N`)가 반복적으로 스택에 쌓이는 것을 GDB `bt`로 확인
- 짧은 함수인데 조건문 하나로 즉시 반환하는 경로와, 인자를 바꿔 자기 자신을 다시 호출하는 경로 두 개만 있음
- 함수가 두 번 이상 자기 자신을 호출(트리형 재귀)해서 실행 시간이 입력 길이에 따라 기하급수적으로 늘어남

## 가장 먼저 할 것
재귀 함수의 인자 목록(스택 또는 레지스터로 전달되는 값들)을 먼저 확정하고, base case 조건(어떤 인자 값일 때 재귀를 멈추는지)부터 찾는다. 그다음 recursive case에서 인자가 어떻게 변형되어 다음 호출로 넘어가는지 정확히 추적한다.

## 단계별 절차
1. IDA/Ghidra에서 함수 하나가 자기 자신을 `call`하는지 xref로 확인한다(함수 이름 위에서 `X`를 누르면 호출 지점 목록에 자기 자신도 포함되어 있다).
2. base case 조건문(즉시 `return`하는 분기)을 찾아 어떤 인자 값에서 종료되는지 적는다.
3. recursive case에서 각 인자가 다음 호출 시 어떤 값으로 바뀌는지(증가, 감소, 다른 배열 인덱스로 변환 등) 확인한다.
4. 한 호출에서 자기 자신을 몇 번 호출하는지 확인한다 — 한 번이면 단순 재귀(반복문으로 쉽게 변환), 두 번 이상이면 트리형 재귀(메모이제이션 고려).
5. 파이썬으로 먼저 재귀 그대로 옮겨 작성하고, `sys.setrecursionlimit()`로 깊이 제한을 넉넉히 늘린 뒤 알려진 입력으로 실행해 실제 바이너리와 결과가 같은지 확인한다.
6. 꼬리 재귀라면 반복문으로 바꿔 성능과 가독성을 개선하고, 트리형 재귀에서 반복 계산이 확인되면 `functools.lru_cache`로 메모이제이션을 추가한다.

## 명령어/단축키
```python
import sys
sys.setrecursionlimit(100000)

def verify(s: bytes, idx: int, acc: int, target: int) -> bool:
    if idx == len(s):
        return acc == target
    acc = (acc ^ s[idx]) & 0xFF   # 예: transform이 단순 XOR 누적인 경우
    return verify(s, idx + 1, acc, target)
```
GDB로 재귀 관찰:
```
break *0x<verify함수시작주소>
commands
  silent
  printf "idx=%d acc=%d\n", $rsi, $rdx
  continue
end
run
```
IDA: 함수 이름 위에서 `X`(Jump to xref) → 자기 자신의 주소가 호출자 목록에 있으면 재귀 확정.

## 출력 해석
- GDB에서 `idx`가 매번 정확히 1씩 증가하며 base case에서 멈춘다면 단순 선형 재귀 — 반복문으로 바로 변환 가능하다.
- 같은 `idx` 값으로 여러 번 호출되는 게 관찰되면 트리형 재귀에서 중복 계산이 실제로 일어나고 있다는 뜻이므로 메모이제이션이 필요하다.
- 파이썬 재귀 버전이 `RecursionError`를 낸다면 실제 입력 길이가 예상보다 길거나, base case를 잘못 찾아 무한 재귀에 빠졌다는 신호다 — 두 가능성을 모두 확인해야 한다.

## 흔한 실수
- base case를 못 찾고 재귀가 어떻게 끝나는지 이해하지 못한 채 recursive case만 보고 짐작으로 구현하는 것 — 반드시 실제 종료 조건 분기를 어셈블리에서 확인해야 한다.
- 트리형 재귀(한 호출에서 두 번 이상 자기 호출)를 단순 선형 재귀처럼 취급해 반복문으로 성급히 바꾸려는 것 — 이 경우 반복문 변환이 자명하지 않으므로 먼저 메모이제이션된 재귀로 정확성부터 확보해야 한다.
- 파이썬 기본 재귀 깊이 제한(보통 1000)을 넘기고 나서 "재귀가 아니다"라고 오판하는 것 — `sys.setrecursionlimit()`을 늘리거나 반복문으로 변환해서 확인해야 한다.
- 재귀 함수의 인자가 스택으로 전달되는지 레지스터(x64 호출 규약의 RDI/RSI/RDX/RCX 등)로 전달되는지 확인하지 않고 스택 프레임만 보다가 실제 인자를 놓치는 것.

## 막혔을 때 다음 체크
- 재귀 각 단계에서 하는 변환이 XOR/해시류라면 → REV-0199 XOR 반복 변환 역산, REV-0906 Polynomial Hash(다항식 해시) 패턴 알아보기
- 이 재귀가 단순 문자별 루프의 다른 표현일 뿐이라면 → REV-0198 문자별 for 루프 검증 패턴
- 재귀 로직 뒤에 또 다른 검증 단계가 이어진다면 → REV-0911 여러 알고리즘이 순차적으로 합성된 문제 풀어내기
- 파이썬 재구현이 실제 바이너리와 정확히 일치하는지 확인하는 절차가 궁금하면 → REV-0919, REV-0912

## 미니 예제
어떤 크랙미가 다음처럼 재귀로 문자열을 검증한다고 하자.

```c
int check(const char *s, int idx, unsigned int acc) {
    if (s[idx] == '\0') {
        return acc == 0xCAFEBABE;
    }
    acc = acc * 131 + (unsigned char)s[idx];
    return check(s, idx + 1, acc);
}
```

이 함수는 REV-0906의 다항식 해시를 재귀로 표현한 것뿐이다. 파이썬으로 그대로 옮기면:

```python
def check(s: bytes, idx: int = 0, acc: int = 0) -> bool:
    if idx == len(s):
        return acc == 0xCAFEBABE
    acc = (acc * 131 + s[idx]) & 0xFFFFFFFF
    return check(s, idx + 1, acc)

# 꼬리 재귀이므로 반복문으로도 동일하게 표현 가능
def check_iter(s: bytes) -> bool:
    acc = 0
    for c in s:
        acc = (acc * 131 + c) & 0xFFFFFFFF
    return acc == 0xCAFEBABE

print(check(b"testcase"), check_iter(b"testcase"))  # 둘 다 같은 결과
```

재귀 버전과 반복문 버전이 항상 같은 결과를 낸다는 걸 여러 입력으로 교차 검증해두면, 이후 분석에서는 더 다루기 쉬운 반복문 버전만 사용해도 안전하다.

### 완전한 예제 스크립트 1 — base case/recursive case를 확정하고 정답을 검증하기
파이썬을 잘 몰라도 따라할 수 있도록 한 줄씩 주석을 달았다. 이 스크립트를 그대로 파일로 저장해서 `python3 파일이름.py`로 실행하면 바로 결과를 볼 수 있다.

```python
import sys  # 재귀 깊이 제한을 늘리기 위해 sys 모듈을 가져온다

# 파이썬은 기본적으로 재귀를 1000번 정도까지만 허용한다.
# 입력 문자열이 길어질 경우를 대비해 한도를 넉넉하게 늘려둔다.
sys.setrecursionlimit(100000)


def check(s: bytes, idx: int = 0, acc: int = 0) -> bool:
    """
    재귀적으로 정의된 검증 함수.
    s   : 검사할 바이트 문자열(입력값)
    idx : 지금 보고 있는 문자의 위치(처음 호출할 때는 0)
    acc : 지금까지 누적된 해시 값(처음 호출할 때는 0)
    """
    # --- base case: 문자열의 끝에 도달하면 재귀를 멈추고 결과를 돌려준다 ---
    if idx == len(s):
        return acc == TARGET  # 누적값이 목표값과 같은지 비교해서 True/False 반환

    # --- recursive case: 현재 문자로 누적값을 갱신하고, 다음 문자로 넘어가며 자기 자신을 호출 ---
    acc = (acc * 131 + s[idx]) & 0xFFFFFFFF  # 다항식 해시 누적 (32비트로 마스킹)
    return check(s, idx + 1, acc)            # idx를 1 늘리고 acc를 갱신해서 재귀 호출


# 실제 바이너리를 GDB로 관찰해서 TARGET 값을 미리 알아냈다고 가정한다.
# (아래 값은 "HelloCTF"라는 비밀번호를 위 알고리즘으로 직접 계산해서 얻은 실제 값이다)
TARGET = 0x719F9B37

print(check(b"HelloCTF"))   # 정답을 넣으면 -> True
print(check(b"WrongPwd"))   # 오답을 넣으면 -> False

# 꼬리 재귀이므로 반복문(while)으로 바꿔도 완전히 같은 결과가 나와야 한다.
# 재귀 버전과 반복문 버전을 서로 대조해보면, 반복문으로 옮긴 것이 맞았는지 스스로 검증할 수 있다.
def check_iter(s: bytes) -> bool:
    acc = 0                         # 초기 누적값 (재귀 버전의 acc=0과 동일)
    for idx in range(len(s)):       # idx가 0부터 len(s)-1까지 1씩 증가 (재귀의 idx+1과 동일)
        acc = (acc * 131 + s[idx]) & 0xFFFFFFFF
    return acc == TARGET            # base case에서 하던 비교를 루프가 끝난 뒤 한 번만 수행

print(check_iter(b"HelloCTF") == check(b"HelloCTF"))  # 두 버전이 같은 결과인지 확인 -> True
```

실행하면 다음처럼 출력된다.
```
True
False
True
```
`check(b"HelloCTF")`가 `True`가 나오는 이유는 `TARGET = 0x719F9B37`이 정확히 `"HelloCTF"`를 이 알고리즘에 넣었을 때 나오는 값이기 때문이다. 다른 문자열(`b"WrongPwd"`)을 넣으면 당연히 다른 누적값이 나오므로 `False`가 된다.

### 완전한 예제 스크립트 2 — 트리형 재귀와 메모이제이션 비교
"한 호출에서 자기 자신을 두 번 이상 호출하는" 트리형 재귀가 실제로 얼마나 느려지는지, 그리고 메모이제이션으로 얼마나 빨라지는지 직접 시간을 측정해서 눈으로 확인해보자. (실전 크랙미의 트리형 재귀 검증 함수도 같은 원리로 느려지고, 같은 방법으로 빨라진다.)

```python
import time        # 실행 시간을 측정하기 위한 모듈
import functools    # 메모이제이션(캐싱)을 자동으로 붙여주는 lru_cache를 쓰기 위한 모듈


def tree_recursion(n: int) -> int:
    """
    한 번 호출될 때마다 자기 자신을 두 번 호출하는 전형적인 트리형 재귀.
    (실전에서는 이런 이중 호출이 검증 로직 안에 숨어 있는 경우가 있다)
    """
    if n < 2:              # base case: n이 0 또는 1이면 그대로 n을 반환
        return n
    return tree_recursion(n - 1) + tree_recursion(n - 2)  # recursive case: 자기 자신을 두 번 호출


@functools.lru_cache(maxsize=None)  # 이미 계산한 n에 대한 결과를 자동으로 저장해두는 데코레이터
def tree_recursion_memo(n: int) -> int:
    if n < 2:
        return n
    return tree_recursion_memo(n - 1) + tree_recursion_memo(n - 2)


N = 30  # 테스트할 입력 크기

start = time.perf_counter()          # 시작 시각 기록
result_naive = tree_recursion(N)     # 메모이제이션 없는 버전 실행
time_naive = time.perf_counter() - start  # 걸린 시간 계산

start = time.perf_counter()
result_memo = tree_recursion_memo(N)       # 메모이제이션 있는 버전 실행
time_memo = time.perf_counter() - start

print(f"결과값 (둘 다 같아야 함): naive={result_naive}, memo={result_memo}")
print(f"naive 걸린 시간: {time_naive:.4f}초")
print(f"memo  걸린 시간: {time_memo:.6f}초")
```

실제로 실행한 결과(환경에 따라 수치는 다를 수 있지만 비율은 비슷하게 나온다):
```
결과값 (둘 다 같아야 함): naive=832040, memo=832040
naive 걸린 시간: 0.1849초
memo  걸린 시간: 0.000036초
```
두 버전의 결과값(832040)은 완전히 같지만, 걸린 시간은 5000배 이상 차이가 난다. 이것이 바로 "같은 부분 문제를 반복 계산하고 있는지"가 트리형 재귀 분석에서 왜 그렇게 중요한지를 숫자로 보여주는 증거다 — 실전에서 검증 함수가 오래 걸리는 트리형 재귀라면, 로직을 통째로 바꾸지 않고 `@functools.lru_cache`만 붙여도 실행이 즉시 빨라지는 경우가 많다.

## 관련 글
- REV-0198 — 문자별 for 루프 검증 패턴
- REV-0199 — XOR 반복 변환 역산
- REV-0906 — Polynomial Hash(다항식 해시) 패턴 알아보기
- REV-0911 — 여러 알고리즘이 순차적으로 합성된 문제 풀어내기
- REV-0912 — 알고리즘 복원 결과를 유닛 테스트로 검증하는 법

## 출처/검증
- 재귀 함수의 base case/recursive case 구분, 꼬리 재귀의 반복문 변환, 메모이제이션 원리: 알고리즘 및 프로그래밍 언어 이론의 표준 개념(재귀와 반복의 등가성, Dynamic Programming의 memoization 기법) 기준.
- 컴파일러가 꼬리 재귀를 루프(jmp)로 최적화하는 TCO(Tail Call Optimization) 동작: 컴파일러 최적화 일반 이론 기준 (2026-09-09 검증).
