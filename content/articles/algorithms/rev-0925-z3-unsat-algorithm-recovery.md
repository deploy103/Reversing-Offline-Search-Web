---
id: REV-0925
title: "Z3에게 조건을 걸었는데 unsat이 뜰 때"
slug: "rev-0925-z3-unsat-algorithm-recovery"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python, Z3]
keywords: ["Z3 unsat", "unsat core", "제약조건 모순", "BitVec 부호 비교", "Z3 디버깅"]
aliases: ["Z3가 unsat이라고 함", "Z3 solver 답이 없음", "z3 조건이 모순됨", "z3 unsat_core 사용법"]
symptom_keywords: ["z3.check()가 unsat을 반환함", "제약조건을 걸었는데 답이 없다고 나옴", "분명 정답이 있는데 z3가 unsat이라고 함", "z3 모델을 못 찾음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
분명히 정답이 존재하는 문제인데 Z3가 `unsat`(만족하는 해 없음)을 반환한다면, 이는 문제 자체가 정말 풀 수 없어서가 아니라 **거의 항상 제약조건 작성 과정에서 원본과 다른(더 엄격하거나 잘못된) 조건을 걸어서 스스로 답을 봉쇄한 것**이며, `unsat_core`나 제약조건을 하나씩 제거해보는 방법으로 어느 조건이 범인인지 찾을 수 있다.

## 언제 검색해야 하나
- 체크 로직을 Z3 제약조건으로 옮겨서 `solver.check()`를 호출했는데 `unsat`이 나올 때
- 같은 문제를 브루트포스나 손 계산으로는 답이 존재한다고 확인했는데 Z3만 `unsat`을 반환할 때
- 제약조건을 여러 개 이어 붙였는데 어느 조건이 문제인지 감이 안 잡힐 때
- 부호 있는/없는 비교, 비트폭 확장을 섞어 쓰다가 갑자기 풀리지 않게 됐을 때

## 핵심 개념
Z3의 `unsat`은 "이 제약조건들을 동시에 만족하는 값이 수학적으로 존재하지 않는다"는 뜻이지, "이 문제에 답이 없다"는 뜻이 아니다. CTF 문제는 설계상 답이 존재하므로, `unsat`이 나온다면 **작성한 제약조건이 원본 로직과 다르게 더 좁거나 모순된 조건을 표현하고 있다**고 봐야 한다. 흔한 원인은 다음과 같다.

**1) 부호 있는/없는 비교 연산자 혼동**: Z3의 `BitVec`에서 기본 비교 연산자(`<`, `>`, `<=`, `>=`)는 실제로 **부호 있는(signed) 비교**로 해석된다(unsigned로 착각하기 쉬운 지점이다). 원본 C 코드가 `unsigned int` 비교인데 Z3에서 `<`를 그대로 썼다면, 상위 비트가 1인(큰 unsigned 값이지만 signed로는 음수인) 영역에서 정반대의 조건이 걸려 실제로는 존재하는 해를 배제해버릴 수 있다. unsigned 비교가 필요하면 `ULT`, `UGT`, `ULE`, `UGE`를 명시적으로 써야 한다.

**2) 목표 상수를 잘못 옮김**: 목표 값 하나를 엔디안이나 signed/unsigned 표시 문제로 잘못 옮기면, 애초에 그 어떤 입력도 만족할 수 없는 상수와 비교하게 되어 `unsat`이 나온다.

**3) 서로 다른 반복(라운드)에서 같은 변수를 재사용**: 루프를 제약조건으로 풀어 쓸 때, 각 반복마다 새로운 중간 변수를 만들지 않고 같은 Z3 변수 이름을 덮어써서 실제로는 서로 다른 시점의 값이어야 할 것을 "항상 같은 값"이라고 제약해버리는 실수. 이 경우 서로 양립할 수 없는 등식들이 동시에 걸려 모순이 생긴다.

**4) 비트폭 불일치로 인한 과도한 범위 제한**: `BitVec` 폭을 원본보다 좁게 잡아서 실제로는 오버플로우를 이용해야 나오는 해를 폭 자체가 표현할 수 없게 만드는 경우.

## 화면/코드에서 보이는 징후
```python
>>> s.check()
unsat
```
- 제약조건을 하나씩 주석 처리하며 다시 `check()`를 돌리면 특정 조건을 빼는 순간 `sat`으로 바뀜
- 루프를 `for i in range(n)`으로 풀면서 `x = BitVec('x', 32)`처럼 매 반복 같은 변수명을 재사용

## 가장 먼저 할 것
제약조건을 전부 걸기 전에, **하나씩 순서대로 추가하면서 매번 `check()`를 호출**해 어느 조건을 추가하는 순간 `unsat`으로 바뀌는지 찾는다. 이게 가장 빠르고 확실한 이분 탐색이다.

## 단계별 절차

**1) `unsat_core`로 원인 조건 추적**
```python
from z3 import *

s = Solver()
s.set(unsat_core=True)

a = Bool('a1'); b = Bool('a2'); c = Bool('a3')
x = BitVec('x', 32)

s.assert_and_track(x > 100, a)
s.assert_and_track(x < 50, b)          # a와 동시에 만족 불가능
s.assert_and_track(x % 7 == 0, c)

print(s.check())          # unsat
print(s.unsat_core())     # [a1, a2] -> 이 두 조건이 서로 모순임을 바로 알려줌
```
`assert_and_track`으로 각 조건에 이름표를 붙이면, `unsat_core()`가 서로 충돌하는 조건들만 정확히 짚어준다.

**2) 부호 비교 재점검**

원본이 `unsigned int` 비교인데 `<`/`>`를 그대로 썼다면 `ULT`/`UGT`로 바꿔서 다시 확인한다.
```python
x = BitVec('x', 32)
# 틀릴 수 있는 코드: 원본이 unsigned 비교인데 기본 비교 연산자만 사용
s.add(x > 0xF0000000)      # 부호 있는 비교로는 의도와 다르게 동작할 수 있음
# 올바른 코드
s.add(UGT(x, 0xF0000000))  # unsigned 비교로 명시
```

**3) 루프 변수 재사용 여부 확인**

루프의 각 반복마다 새 변수를 만들었는지 코드를 다시 읽는다.
```python
# 틀린 방식: 반복마다 같은 이름을 덮어써서 이전 제약과 충돌
h = BitVec('h', 32)
for i in range(len(data)):
    s.add(h == h * 31 + data[i])   # 매번 같은 h에 대해 등식을 걸어버림 (모순 유발)

# 올바른 방식: 반복마다 새 중간 변수 생성
hs = [BitVecVal(0, 32)]
for i, b in enumerate(data):
    hs.append(hs[-1] * 31 + b)
s.add(hs[-1] == target)
```

**4) 목표 상수와 비트폭 재대조**

목표 상수를 원본 디스어셈블리와 한 글자씩 재대조하고, 관련 변수의 `BitVec` 폭이 원본 C 타입과 정확히 일치하는지 재확인한다.

## 명령어/단축키
```python
s.set(unsat_core=True)
s.assert_and_track(cond, Bool('name'))
s.unsat_core()
ULT(a, b) / UGT(a, b) / ULE(a, b) / UGE(a, b)   # unsigned 비교
```

## 출력 해석
- `unsat_core()`가 두 개 이상의 태그를 반환하면, 그 태그에 해당하는 조건들이 서로 동시에 만족될 수 없다는 뜻이다 — 그중 하나가 원본과 다르게 옮겨진 조건이다.
- 부호 비교를 `ULT`/`UGT`로 바꾸자 `sat`으로 바뀌면, 원인은 signed/unsigned 혼동이었던 것이 확정된다.
- 루프 변수를 매 반복 새로 만들도록 고치자 `sat`으로 바뀌면, 변수 재사용이 원인이었던 것이다.

## 흔한 실수
- Z3의 기본 비교 연산자가 항상 부호 없는 비교라고 착각하는 것 — 실제로는 signed 비교이므로 unsigned가 필요하면 반드시 `U`로 시작하는 함수를 명시해야 한다.
- `unsat`이 나오자마자 "이 문제는 원래 못 푸는구나"라고 포기하는 것 — CTF 문제는 항상 답이 존재하도록 설계되므로, `unsat`은 100% 제약조건 작성 실수로 봐야 한다.
- 루프를 그대로 Z3 코드로 옮기면서 파이썬 변수처럼 같은 이름을 계속 덮어쓰는 것 — Z3의 제약조건은 "대입"이 아니라 "등식 선언"이므로 매 반복 새로운 기호 변수가 필요하다.
- `unsat_core`를 쓰지 않고 감으로 조건을 하나씩 지우면서 오래 헤매는 것 — `assert_and_track`을 처음부터 걸어두면 원인을 몇 초 안에 찾을 수 있다.

## 막혔을 때 다음 체크
- 비트폭/오버플로우 처리 자체가 헷갈린다면 → REV-0270 Z3에서 8비트 32비트 Overflow 다루기
- Z3 BitVec의 기초 문법이 헷갈린다면 → REV-0268 Z3 BitVec 기초
- 문자 배열 조건을 거는 일반적인 패턴이 필요하다면 → REV-0269 Z3로 문자 조건 풀기
- 목표 상수 자체가 의심된다면 → REV-0930 상수 하나를 잘못 읽어서 전체 알고리즘이 안 맞을 때

## 미니 예제
`unsigned char` 입력 배열의 합이 특정 값을 넘으면서도 각 원소가 100 미만이어야 하는 조건을 걸었다고 하자.
```python
from z3 import *

x = BitVec('x', 8)   # unsigned char
s = Solver()
s.add(x < 100)         # 8비트 범위 안에서의 비교
s.add(x > 250)          # 250은 8비트 unsigned 범위(0~255) 안의 값
print(s.check())        # unsat: 100보다 작으면서 250보다 큰 값은 없음 (이 예시는 진짜 모순)
```
이 경우는 실제로 모순인 조건(100보다 작으면서 250보다 큼)이라 `unsat`이 정답이다. 하지만 실무에서는 이런 명백한 모순이 아니라, 부호 비교/루프 변수 재사용처럼 **겉보기에는 멀쩡해 보이는 코드가 몰래 이런 모순을 만들어낸다**는 점이 진짜 함정이다. `unsat_core`로 어떤 `add()` 호출이 문제인지 태그를 붙여 추적하면, 사람 눈으로는 안 보이던 이런 숨은 모순도 바로 드러난다.

### 추가 예제 — signed 비교가 진짜로 unsat을 만드는 실행 가능한 사례
"겉보기엔 멀쩡한데 몰래 모순을 만드는" 상황을 실제로 재현해보자. 원본 로직은 "8비트 unsigned char `x`가 126보다 크고 130보다 작다"(`0x7E < x < 0x82`, 즉 실제로 만족하는 값은 127, 128, 129)이다.

```python
from z3 import *   # Solver, BitVec, UGT, ULT 등을 사용하기 위해 z3 모듈 전체를 가져온다

x = BitVec('x', 8)   # 8비트 unsigned char 하나를 표현하는 심볼릭 변수

# [틀린 코드] Z3 기본 비교 연산자(>, <)를 그대로 사용 -> 사실은 signed(부호 있는) 비교로 해석됨
s_buggy = Solver()
s_buggy.add(x > 0x7E)   # signed로는 0x7E == 126(양수 그대로) -> "x > 126"
s_buggy.add(x < 0x82)   # signed로는 0x82 == -126(8비트에서 최상위 비트가 1이라 음수) -> "x < -126"
print("[틀린 코드] check():", s_buggy.check())
# 출력: [틀린 코드] check(): unsat
# 이유: signed로 x>126이면 x==127(8비트 signed 최댓값)만 가능하고,
#      x<-126이면 x<=-127(즉 x==-127 또는 -128)만 가능해서 두 조건을 동시에 만족하는 x가 없다.

# [고친 코드] 부호 없는 비교 함수 UGT/ULT를 명시적으로 사용
s_fixed = Solver()
s_fixed.add(UGT(x, 0x7E))   # unsigned로 "x > 126"
s_fixed.add(ULT(x, 0x82))   # unsigned로 "x < 130"
result = s_fixed.check()
print("[고친 코드] check():", result)          # sat
print("[고친 코드] model():", s_fixed.model())  # 예: [x = 128]
```
`x`를 선언한 코드, 부등호 기호, 상수값까지 전부 원본과 똑같이 보이지만, **비교 연산자 하나(`>`/`<` vs `UGT`/`ULT`)만 다르다는 이유로 결과가 `unsat`에서 `sat`으로 완전히 뒤바뀐다.** 실제 원본 알고리즘이 unsigned 8비트 값을 다룬다면, 정답은 언제나 `UGT`/`ULT` 버전이 알려주는 `127`, `128`, `129` 중 하나이며, 기본 연산자를 그대로 쓴 `unsat` 결과는 "답이 없다"가 아니라 "제약조건을 잘못 걸었다"는 신호였을 뿐이다.

## 관련 글
- REV-0268 — Z3 BitVec 기초
- REV-0269 — Z3로 문자 조건 풀기
- REV-0270 — Z3에서 8비트 32비트 Overflow 다루기
- REV-0930 — 상수 하나를 잘못 읽어서 전체 알고리즘이 안 맞을 때

## 출처/검증
- Z3py의 기본 비교 연산자가 부호 있는(signed) 비교이며 unsigned 비교를 위해서는 `ULT`/`ULE`/`UGT`/`UGE` 함수가 필요하다는 사양: Z3Prover/z3 공식 GitHub 저장소의 Z3py API 참조 문서 기준 (2026-09-09 검증).
- `assert_and_track`/`unsat_core`를 이용한 제약조건 충돌 추적 기능: 동일 Z3py API 문서의 Solver 클래스 설명 기준.
