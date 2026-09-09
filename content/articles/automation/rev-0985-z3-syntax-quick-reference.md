---
id: REV-0985
title: "Z3 문법 빠른 참조(BitVec/제약조건)"
slug: "rev-0985-z3-syntax-quick-reference"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Z3, Python]
keywords: ["Z3 문법표", "BitVec 함수 정리", "Z3 비교 연산자", "Z3 논리 연산", "Z3 signed unsigned 비교", "Z3 배열"]
aliases: ["z3 치트시트", "z3 함수 목록", "z3 빠른 참조", "z3py 문법 정리"]
symptom_keywords: ["z3 함수 이름을 까먹음", "signed 비교 함수가 뭐였는지 모름", "BitVec 배열 어떻게 씀", "z3 논리 연산자 문법 헷갈림"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Z3(REV-0268~REV-0270)를 실전에서 쓸 때마다 매번 API 문서를 찾아보지 않도록, BitVec 선언/연산/부호 있는 비교/논리 결합/배열/모델 추출까지 자주 쓰는 문법을 표 형태로 정리한 빠른 참조 문서다.

## 언제 검색해야 하나
- Z3 코드를 짜다가 특정 함수(부호 있는 비교, 부호 확장 등) 이름이 기억 안 날 때
- `BVSGT`, `SignExt`, `Extract` 같은 함수 문법을 매번 검색하기 귀찮을 때
- 여러 조건을 AND/OR로 묶는 정확한 문법이 헷갈릴 때
- 문자 배열(패스워드 등)을 다루는 제약조건 문법을 빠르게 다시 확인하고 싶을 때

## 핵심 개념
Z3 파이썬 바인딩은 대부분 연산자 오버로딩(`+`, `-`, `^`, `&`, `==` 등)으로 자연스러운 파이썬 문법을 그대로 쓸 수 있지만, **부호 있는(signed) 비교**나 **비트 추출/확장**처럼 파이썬 연산자로 표현할 수 없는 연산은 별도 함수 이름을 알아야 한다. 이 문서는 REV-0268(BitVec 기초), REV-0269(문자 조건), REV-0270(오버플로우)에서 다룬 개념들의 실제 함수 시그니처만 빠르게 찾아볼 수 있도록 표로 압축했다.

## 화면/코드에서 보이는 징후
아래 표에 정리된 함수/연산자 이름이 그대로 Z3 파이썬 스크립트에 등장한다. `from z3 import *` 이후 이 문서의 표에 나온 이름들을 그대로 호출하면 된다.

## 가장 먼저 할 것
지금 풀어야 할 조건이 "부호 없는 비교(기본 연산자로 충분)"인지 "부호 있는 비교(별도 함수 필요)"인지부터 판단한다. C 원본 코드에서 변수 타입이 `unsigned int`/`unsigned char`면 기본 연산자, `int`/`char`(부호 있는 기본 타입)면 signed 전용 함수가 필요하다.

## 단계별 절차
1. 변수를 선언한다: `BitVec('name', bits)`.
2. 필요한 연산을 아래 표에서 찾아 그대로 적용한다.
3. `Solver()`에 `add()`로 제약조건을 쌓는다.
4. `check()` 결과가 `sat`이면 `model()`로 실제 값을 꺼낸다.

## 명령어/단축키

### 변수/상수 선언
```python
from z3 import *
x = BitVec('x', 32)          # 32비트 심볼릭 변수
c = BitVecVal(10, 32)         # 32비트 상수값
arr = [BitVec(f'c{i}', 8) for i in range(16)]   # 8비트 변수 16개(문자 배열)
```

### 산술/비트 연산 (파이썬 연산자 그대로)
```python
x + y, x - y, x * y            # 덧셈/뺄셈/곱셈
x ^ y, x & y, x | y, ~x         # XOR/AND/OR/NOT
x << y, LShR(x, y)              # 왼쪽 시프트 / 논리 오른쪽 시프트(부호 무시)
x >> y                          # 산술(부호 있는) 오른쪽 시프트
```

### 비교 연산자
```python
x == y, x != y                  # 동등/부등 (부호 무관)
x < y, x <= y, x > y, x >= y     # 부호 없는(unsigned) 비교 — 기본값
ULT(x, y), ULE(x, y), UGT(x, y), UGE(x, y)   # 명시적 unsigned 비교
x <s y                          # BitVec에서 <s/<=s/>s/>=s는 signed 비교 연산자 (일부 버전은 함수형: BVSLT 등)
```

### 부호/비트폭 관련
```python
SignExt(n, x)     # x를 부호 확장해서 (원래비트+n)비트로 늘림
ZeroExt(n, x)     # x를 0으로 채워서 확장(부호 없는 확장)
Extract(hi, lo, x) # x의 [hi:lo] 비트 구간을 잘라냄(예: Extract(7,0,x)는 최하위 바이트)
```

### 논리 결합
```python
s.add(And(cond1, cond2))     # 모든 조건 동시 만족
s.add(Or(cond1, cond2))       # 조건 중 하나 이상 만족
s.add(Not(cond1))             # 조건 부정
s.add(Implies(cond1, cond2))  # cond1이면 cond2도 성립
```

### 솔버/모델
```python
s = Solver()
s.add(expr)
result = s.check()            # sat / unsat / unknown
m = s.model()
val = m[x].as_long()           # 정수로 추출
```

## 출력 해석
- `<`, `<=`, `>`, `>=`는 Z3 BitVec에서 **기본적으로 부호 없는(unsigned) 비교**다. 원본 로직이 `int`(부호 있는) 타입이면 `<s` 계열이나 `BVSLT` 등 signed 전용 비교를 명시적으로 써야 한다. 이 구분을 놓치면 `sat`/`unsat` 결과가 원본 프로그램의 실제 동작과 어긋난다.
- `Extract(hi, lo, x)`의 결과 비트폭은 `hi-lo+1`이다. 예를 들어 32비트 `x`에서 최하위 바이트만 뽑으려면 `Extract(7, 0, x)`이고 결과는 8비트 값이다.
- `SignExt`/`ZeroExt`의 첫 인자는 "추가할 비트 수"이지 "최종 비트 수"가 아니다. 8비트를 32비트로 만들려면 `SignExt(24, x)`(24비트 추가)다.

## 흔한 실수
- 부호 있는 비교가 필요한데 기본 `<` 연산자를 그대로 써서 잘못된 해를 얻는 것.
- `SignExt`/`ZeroExt`의 인자를 "최종 비트 수"로 착각해서 엉뚱한 비트폭이 나오는 것.
- `Extract(lo, hi, x)`처럼 인자 순서를 거꾸로 넣는 것 — 반드시 `(hi, lo, x)` 순서다.
- `LShR`(논리 시프트)과 `>>`(산술 시프트)를 혼동해서 부호 비트가 잘못 유지/소실되는 것.

## 막혔을 때 다음 체크
- BitVec 기본 개념 자체가 헷갈리면 → REV-0268 Z3 BitVec 기초
- 문자열/문자 배열 조건을 실제로 세우는 예제가 필요하면 → REV-0269 Z3로 문자 조건 풀기
- 오버플로우/부호 확장이 섞인 복잡한 로직이라면 → REV-0270 Z3에서 8비트 32비트 Overflow 다루기
- 로직이 너무 복잡해서 손으로 옮기기 어렵다면 → REV-0271 angr 심볼릭 실행 기초

## 미니 예제
부호 있는 8비트 값 `x`가 `-10`보다 크고 `100`보다 작다는 조건을 정확히 표현하는 예제다.

```python
from z3 import *

x = BitVec('x', 8)
s = Solver()

# 부호 있는 비교(signed)를 명시적으로 사용 — 기본 <, > 연산자는 unsigned라 여기선 부적합
s.add(x >s -10)
s.add(x <s 100)

if s.check() == sat:
    m = s.model()
    print(m[x].as_long())
```

기본 unsigned 비교(`x > -10`처럼 파이썬에서 음수를 그대로 넣는 경우)를 썼다면 8비트 값 `-10`이 내부적으로 `246`(2의 보수 표현)으로 처리되어 전혀 다른 결과가 나왔을 것이다.

## 관련 글
- REV-0268 — Z3 BitVec 기초
- REV-0269 — Z3로 문자 조건 풀기
- REV-0270 — Z3에서 8비트 32비트 Overflow 다루기
- REV-0271 — angr 심볼릭 실행 기초

## 출처/검증
- Z3 파이썬 API(`BitVec`, `Extract`, `SignExt`, `ZeroExt`, `ULT`/`UGT`, signed 비교 연산자, `And`/`Or`/`Not`/`Implies`)는 Z3 공식 GitHub(Z3Prover/z3)의 Z3py API 문서 및 튜토리얼을 기준으로 정리했다(2026-09-09 검증).
- BitVec 기본 비교 연산자가 unsigned라는 사실은 Z3py 튜토리얼의 "Bit-Vectors" 섹션 설명과 일치한다.
