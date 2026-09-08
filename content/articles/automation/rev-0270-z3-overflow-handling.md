---
id: REV-0270
title: "Z3에서 8비트 32비트 Overflow 다루기"
slug: "rev-0270-z3-overflow-handling"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python, Z3]
keywords: ["Z3 오버플로우", "unsigned char wraparound", "uint32_t overflow", "BitVec 비트폭", "Z3 Int vs BitVec", "ZeroExt", "SignExt", "부호 확장"]
aliases: ["z3 정수 오버플로우 모델링", "z3 랩어라운드", "z3 8비트 32비트 차이", "z3 초보자 실수"]
symptom_keywords: ["z3 답이 실제 바이너리랑 다름", "z3 Int 썼는데 안 맞음", "오버플로우 모델링 어떻게 함", "부호 확장 z3", "z3 unsigned char 처리"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Z3로 구한 답이 실제 바이너리에서는 틀리다고 나오는 가장 흔한 원인은 파이썬의 무한 정밀도 정수 감각으로 `Int`를 쓰거나 비트폭을 잘못 잡아서, C의 `unsigned char`/`uint32_t`가 실제로 겪는 8비트/32비트 랩어라운드(오버플로우)를 재현하지 못했기 때문이며, 해결책은 항상 원본 변수와 정확히 같은 폭의 `BitVec`을 쓰고 연산 도중의 임시값 폭까지 신경 쓰는 것이다.

## 언제 검색해야 하나
- Z3가 찾아준 답을 실제 바이너리에 넣었더니 "Wrong"이 나오는데 왜 틀렸는지 이해가 안 될 때
- 검증 로직에 `unsigned char`, `uint8_t`, `uint32_t`처럼 크기가 명시된 타입이 섞여 있고, 중간에 곱셈/덧셈으로 자연스럽게 오버플로우가 나는 것 같은데 Z3 코드에 그걸 어떻게 반영해야 할지 모를 때
- Z3의 `Int` 타입과 `BitVec` 타입의 차이를 정확히 모를 때
- 8비트 변수와 32비트 변수가 한 식에서 섞여 있어서(`(uint32_t)(unsigned char)x`) 어떻게 다뤄야 할지 막막할 때

## 핵심 개념
C 프로그램의 정수 타입은 항상 **유한한 비트 폭**을 가진다. `unsigned char`는 8비트라서 0~255 범위를 벗어나면 256으로 나눈 나머지로 자동으로 "랩어라운드"되고, `uint32_t`는 32비트라서 `0xFFFFFFFF`를 넘으면 다시 0부터 시작한다. 이건 버그가 아니라 C 표준이 정의한 정상 동작이다(부호 없는 정수 타입의 오버플로우는 undefined behavior가 아니라 well-defined다).

문제는 Z3의 `Int` 타입이 이 동작을 전혀 흉내 내지 않는다는 점이다. Z3의 `Int`는 수학의 정수처럼 무한히 크거나 작을 수 있는 값을 표현한다. 그래서 `Int` 변수로 `x * x == 300`같은 조건을 풀면 진짜 수학적인 정수해를 찾아주지만, 원래 C 코드가 `unsigned char x`였다면 `x * x`는 8비트로 잘린 결과와 비교되었을 것이므로 Z3가 찾은 "수학적으로 옳은" 해가 실제 바이너리에서는 전혀 다른 값으로 계산되어 검증에 실패한다.

해결책은 처음부터 **`BitVec`을 쓰고, 원본 C 타입과 정확히 같은 비트 폭을 지정하는 것**이다. `BitVec` 연산은 기본적으로 모듈러 연산(폭을 넘어서면 자동으로 랩어라운드)을 하도록 정의되어 있어서, C의 오버플로우 동작을 정확히 재현한다.

```python
from z3 import *

# 틀린 방법: Int는 오버플로우를 흉내내지 못한다
x_wrong = Int('x')

# 맞는 방법: unsigned char와 같은 8비트 BitVec
x_right = BitVec('x', 8)
```

`BitVec(8)` 두 변수를 곱하면 결과도 자동으로 8비트로 잘린다. 예를 들어 `x = BitVecVal(200, 8)`이고 `y = BitVecVal(100, 8)`이면, `x + y`는 수학적으로 300이지만 8비트 BitVec 덧셈에서는 `300 % 256 = 44`가 된다. 이게 바로 `unsigned char`에서 `200 + 100`을 계산했을 때 실제로 일어나는 일과 동일하다.

**서로 다른 비트폭이 섞이는 경우**도 흔하다. 예를 들어 `unsigned char`를 `uint32_t`로 대입하는 코드(`uint32_t y = x;`, x는 `unsigned char`)가 있다면, 이는 상위 비트를 0으로 채우는 **제로 확장(zero extension)**이다. Z3에서는 `ZeroExt(n, bv)` 함수로 표현한다(n은 추가할 비트 수). 반대로 `signed char`를 더 큰 부호 있는 타입으로 확장할 때는 부호 비트를 복제하는 **부호 확장(sign extension)**이 일어나며, Z3에서는 `SignExt(n, bv)`를 쓴다.

```python
x8 = BitVec('x8', 8)          # unsigned char
x32 = ZeroExt(24, x8)          # 8비트 -> 32비트, 상위 24비트는 0으로 채움 (unsigned 확장)
x32_signed = SignExt(24, x8)   # 8비트 -> 32비트, 부호 비트 복제 (signed 확장)
```

폭이 다른 `BitVec`끼리는 직접 연산할 수 없고(`x8 + x32`처럼 쓰면 에러), 반드시 먼저 같은 폭으로 맞춰야 한다는 점도 기억해야 한다. 반대로 32비트를 8비트로 좁힐 때(대입으로 잘리는 경우)는 `Extract(7, 0, bv32)`로 하위 8비트만 뽑아낸다.

## 화면/코드에서 보이는 징후
- 리버싱 대상 소스/디컴파일 결과에 `unsigned char`, `uint8_t`, `BYTE`, `uint32_t`, `DWORD`처럼 크기가 명시된 타입이 자주 등장한다.
- 디스어셈블리에서 `movzx`(제로 확장 이동) 또는 `movsx`(부호 확장 이동) 명령어가 좁은 레지스터(`al`, `cl` 등)에서 넓은 레지스터(`eax`, `ecx`)로 값을 옮길 때 등장한다 — 이게 바로 `ZeroExt`/`SignExt`가 필요한 지점이라는 신호다.
- Z3 스크립트에서 `Int`를 쓰다가 답이 안 맞아서 뒤늦게 `BitVec`으로 바꾼 흔적(주석, 커밋 히스토리 등)이 라이트업에 종종 보인다.
- `& 0xff`, `% 256`처럼 명시적으로 마스킹하는 코드가 원본에 있다면, 이는 곧 8비트 오버플로우를 프로그래머가 의도적으로 다루고 있다는 신호다.

## 가장 먼저 할 것
검증 로직에 등장하는 **모든 변수의 원래 C 타입과 정확한 비트 폭**을 다시 한번 확인한다. `char`/`unsigned char`(8비트), `short`/`unsigned short`(16비트), `int`/`unsigned int`/`uint32_t`(32비트), `long long`/`uint64_t`(64비트)를 표로 적어두고, Z3 변수를 선언할 때 이 표를 그대로 따라간다. 특히 중간 계산 결과를 저장하는 임시 변수의 타입도 놓치지 않아야 한다 — 대입되는 순간 타입이 바뀌면서 암묵적으로 잘리거나 확장될 수 있다.

## 단계별 절차

**1) `Int`로 틀리는 예시부터 확인**

```python
from z3 import *

# unsigned char 두 개를 더해서 특정 값과 같은지 확인하는 로직이라고 가정
x = Int('x')
s = Solver()
s.add(x >= 0, x <= 255)   # char 범위라고 "흉내"만 냄
s.add(x + 200 == 44)       # 실제 8비트 덧셈에서는 200+200=400->144가 아니라 여기선 예시
print(s.check())  # unsat: Int는 랩어라운드를 모르므로 200을 넘는 조건을 못 맞춤
```

**2) `BitVec(8)`로 정확히 재현**

```python
from z3 import *

x = BitVec('x', 8)  # unsigned char x
s = Solver()
s.add(x + 200 == 44)  # 8비트 세계에서는 x=100일 때 100+200=300 -> 300%256=44
print(s.check())       # sat
print(s.model())        # [x = 100]
```

**3) 8비트 -> 32비트 확장이 섞인 실제 유사 사례**

```c
// 원본 C 로직 예시
unsigned char input;      // 8비트
uint32_t acc = 0;          // 32비트 누산기

acc = (uint32_t)input * (uint32_t)input;  // 8비트 값을 32비트로 확장 후 곱셈
if (acc == 40000) { /* correct */ }
```

```python
from z3 import *

inp = BitVec('inp', 8)               # unsigned char
inp32 = ZeroExt(24, inp)              # uint32_t로 제로 확장
acc = inp32 * inp32                    # 32비트 곱셈(32비트 폭에서 랩어라운드)

s = Solver()
s.add(acc == 40000)
s.add(inp >= 0, inp <= 255)  # 사실 BitVec(8)은 이미 이 범위로 제한됨(참고용 명시)

if s.check() == sat:
    print(s.model()[inp].as_long())  # 200 (200*200 = 40000, 32비트 안에서 오버플로우 없음)
```

**4) 진짜 오버플로우가 일어나는 케이스**

곱셈 결과가 32비트를 넘는 경우도 확인해본다.

```python
from z3 import *

inp = BitVec('inp', 8)
inp32 = ZeroExt(24, inp)
acc = inp32 * inp32 * inp32   # 세제곱, 32비트 안에서 랩어라운드 발생 가능

s = Solver()
s.add(acc == 0)   # 0이 되는 자명한 해(0) 말고 다른 해가 있는지도 확인 가능
s.add(inp != 0)
print(s.check())
if s.check() == sat:
    print(s.model()[inp].as_long())
```

이 경우 `inp`가 크면 `inp**3`이 32비트를 넘어 랩어라운드되면서 우연히 0이 되는 값이 존재할 수 있다 — 이런 "오버플로우를 이용한 우회"가 실제 CTF 문제의 트릭으로 종종 등장하며, `BitVec`을 정확히 쓰지 않으면 이런 해를 아예 놓치게 된다.

**5) 부호 있는 타입 비교**

`signed char`나 `int` 같은 부호 있는 타입을 비교할 때는 Z3의 부호 있는 비교 연산이 필요하다. 기본 `<`, `>` 연산자는 부호 없는 비교이므로, 부호 있는 비교가 필요하면 명시적으로 표시해야 한다.

```python
from z3 import *
x = BitVec('x', 8)  # signed char로 취급하고 싶다고 가정
s = Solver()
# 부호 없는 비교(기본): 0~255 범위로 취급됨
s.add(x > 100)
# 부호 있는 비교가 필요한 경우 별도 처리가 필요하므로,
# 애초에 signed 값인지 unsigned 값인지 원본 타입을 먼저 정확히 파악하는 것이 중요하다.
```

## 명령어/단축키
- `BitVec('x', n)` : n비트 폭 변수 선언(원본 C 타입 폭과 반드시 일치시킬 것)
- `ZeroExt(n, bv)` : bv를 상위 n비트를 0으로 채워 확장(부호 없는 확장, unsigned 대입)
- `SignExt(n, bv)` : bv를 부호 비트로 채워 확장(부호 있는 확장, signed 대입)
- `Extract(hi, lo, bv)` : bv에서 hi~lo 비트 구간만 잘라내기(좁은 타입으로 대입될 때)
- `BitVecVal(v, n)` : 구체적인 상수값을 n비트 폭으로 생성(테스트/디버깅에 유용)
- 산술 연산자(`+`, `-`, `*`) : `BitVec` 폭 안에서 자동으로 모듈러(랩어라운드) 연산

## 출력 해석
- Z3가 찾은 해를 바이너리에 넣었는데 검증 실패 — 거의 항상 비트폭 불일치(`Int` 사용, 또는 `BitVec` 폭이 원본 타입과 다름)가 원인이다. 모든 변수 선언을 다시 원본 타입과 대조한다.
- `BitVec` 폭이 다른 두 변수를 직접 연산하려 하면 `Z3Exception: sort mismatch` 같은 에러가 뜬다 — `ZeroExt`/`SignExt`/`Extract`로 폭을 먼저 맞춰야 한다.
- `unsat`이 나왔는데 실제로는 오버플로우를 이용하면 해가 존재하는 경우 — `Int`를 쓰고 있었다면 `BitVec`으로 바꿔서 다시 확인한다. `Int`는 오버플로우로만 성립하는 해를 아예 찾아낼 수 없다.
- 모델에서 나온 값이 음수처럼 보이는데(`as_long()`이 음수를 반환) 원본이 unsigned 타입이라면, `as_long()` 대신 필요 시 `2**n`을 더해 부호 없는 값으로 재해석해야 할 수 있다(부호 있는 BitVecVal로 해석되는 경우).

## 흔한 실수
- 습관적으로 `Int()`를 쓰다가 오버플로우가 있는 로직에서 틀린(또는 존재하지 않는) 해를 얻는 경우 — 리버싱 자동화에서는 특별한 이유가 없으면 항상 `BitVec`을 기본으로 써야 한다.
- 8비트 변수를 32비트 연산에 섞으면서 `ZeroExt`/`SignExt` 없이 그냥 파이썬 정수처럼 더해버려서 `Z3Exception`이 나거나(폭이 다르면 에러), 혹은 실수로 같은 폭으로 선언해서 에러는 안 나지만 값이 틀리는 경우.
- `unsigned char`를 `signed char`로 착각하거나 그 반대로 착각해서 `ZeroExt`를 써야 할 곳에 `SignExt`를 쓰는(또는 그 반대) 경우 — 원본 타입 선언을 반드시 다시 확인해야 한다.
- 중간 임시 변수(예: 반복문의 누산기)의 타입을 놓쳐서, 최종 변수만 올바른 폭으로 선언하고 중간 계산은 잘못된 폭으로 하는 경우 — 디스어셈블리에서 `movzx`/`movsx`가 나오는 지점, 그리고 레지스터 크기(`al` vs `eax`)가 바뀌는 지점을 전부 추적해야 한다.
- 곱셈/시프트처럼 결과 폭이 커질 수 있는 연산에서, 원본 컴파일러가 실제로 어떤 폭으로 계산했는지(중간 결과가 32비트로 승격되는지, 8비트에서 그대로 랩어라운드되는지) C의 정수 승격 규칙(integer promotion)을 무시하고 넘어가는 경우.

## 막혔을 때 다음 체크
- 답이 계속 안 맞는다면 → 원본 디스어셈블리에서 해당 변수가 쓰이는 모든 지점의 레지스터 크기(`al`/`ax`/`eax`/`rax`)를 다시 추적해서 Z3 변수 폭과 하나하나 대조한다.
- 여러 비트폭이 섞인 복잡한 수식이라 손으로 옮기기 어렵다면 → REV-0271 문서의 `angr`로 넘어가는 것을 고려한다. angr은 바이너리를 실제 명령어 단위로 심볼릭 실행하므로 비트폭 실수를 사람이 직접 관리할 필요가 줄어든다.
- 문자열/배열 전체에 이 오버플로우 처리를 적용해야 한다면 → REV-0269 문서의 문자 배열 패턴과 결합해서 각 `flag[i]`를 정확한 8비트 `BitVec`으로 유지한 채 확장 연산을 추가한다.
- 기본 `BitVec` 개념 자체가 아직 헷갈린다면 → REV-0268 문서로 돌아가 기초부터 다시 확인한다.

## 미니 예제
`unsigned char x`를 입력받아 `(uint32_t)x * (uint32_t)x + 7`이 `10007`과 같은지 검사하는 로직을 정확한 비트폭으로 풀어본다.

```python
from z3 import *

x = BitVec('x', 8)            # unsigned char
x32 = ZeroExt(24, x)            # uint32_t로 제로 확장
expr = x32 * x32 + 7             # 32비트 폭 안에서 계산(오버플로우 시 랩어라운드)

s = Solver()
s.add(expr == 10007)

if s.check() == sat:
    ans = s.model()[x].as_long()
    print('x =', ans)  # 100  (100*100+7 = 10007, 오버플로우 없이 정확히 맞음)
else:
    print('unsat')
```

여기서 만약 `x32 = ZeroExt(24, x)` 대신 실수로 `x`를 그대로 32비트인 것처럼 `Int`로 다뤘다면, 8비트 랩어라운드가 실제로 일어나는 다른 케이스에서는 전혀 다른(틀린) 답을 내놓았을 것이다. 비트폭을 원본 타입과 정확히 맞추는 습관이 Z3 기반 리버싱 자동화에서 가장 중요한 기본기다.

## 관련 글
- REV-0268 — Z3 BitVec 기초
- REV-0269 — Z3로 문자 조건 풀기
- REV-0267 — pwntools p32 p64 u32 u64

## 출처/검증
- Z3의 `BitVec` 모듈러 연산 의미론과 `ZeroExt`/`SignExt`/`Extract` API는 Z3 공식 GitHub(Z3Prover/z3)의 Z3py 참조 문서를 기준으로 정리했다(2026-09-08 검증).
- C 표준의 부호 없는 정수 오버플로우가 well-defined(모듈러 연산)라는 사실과 정수 승격 규칙은 C 언어의 일반적인 사양 서술과 일치한다.
- `z3-solver`는 서드파티 패키지이므로 `pip install z3-solver`가 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
- 코드 예제는 `pip install z3-solver` 환경의 표준 CPython 3에서 그대로 재현 가능하다.
