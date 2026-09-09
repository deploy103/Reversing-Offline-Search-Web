---
id: REV-0269
title: "Z3로 문자 조건 풀기"
slug: "rev-0269-z3-solving-char-constraints"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python, Z3]
keywords: ["Z3 문자열", "Z3 char", "BitVec 8비트", "flag 복원", "출력가능문자 제약", "printable ascii z3", "z3 배열 변수"]
aliases: ["z3로 flag 구하기", "z3 문자열 조건", "z3 아스키 범위 제약", "z3 패스워드 복원"]
symptom_keywords: ["flag 각 글자 조건 z3로 풀고 싶음", "z3 문자 배열 어떻게 씀", "출력가능한 문자로 제한하려면", "z3로 문자열 복원", "패스워드 문자별 조건"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
CTF 바이너리가 입력 문자열을 한 글자씩 순회하며 검사하는 구조라면, 문자열 길이만큼 8비트 `BitVec` 변수를 만들어 배열처럼 다루고 각 글자의 검증식을 `s.add()`로 그대로 옮긴 뒤, 결과값을 `chr()`로 변환하면 원본 문자열(플래그)을 통째로 복원할 수 있다.

## 언제 검색해야 하나
- 리버싱한 `check_flag()` 함수가 `for (i = 0; i < len; i++)`처럼 문자열을 한 글자씩 순회하며 각 위치마다 다른 조건을 검사할 때
- 각 문자가 이전 문자, 다음 문자, 또는 고정된 키 배열과 XOR/덧셈 관계로 얽혀 있어서 손으로 역산하기 번거로울 때
- Z3로 정수 하나는 풀어봤는데(REV-0268), 문자열 전체를 어떻게 변수 여러 개로 다뤄야 할지 모를 때
- 찾은 해가 출력 불가능한 제어문자라서 실제로는 말이 안 되는 "플래그"가 나올 때, 어떻게 조건을 더 추가해야 할지 모를 때

## 핵심 개념
C 문자열은 결국 `char` 배열, 즉 8비트 정수들의 나열이다. 따라서 문자열 조건을 Z3로 풀 때 가장 자연스러운 방법은 문자열 길이만큼 **8비트 `BitVec` 변수를 리스트로 만들어** 각각을 한 글자에 대응시키는 것이다.

```python
from z3 import *
flag = [BitVec(f'c{i}', 8) for i in range(10)]  # 10글자짜리 문자열
```

이렇게 만든 `flag[0]`, `flag[1]`, ... 각각은 C 코드에서 `input[0]`, `input[1]`, ...에 대응하는 심볼릭 변수다. 리버싱한 검증 함수가 하는 연산(비교, XOR, 덧셈, 룩업 테이블 참조 등)을 인덱스별로 그대로 `s.add()`에 옮기면 된다.

여기에 리버싱에서 거의 항상 추가해야 하는 조건이 하나 있다: **출력 가능 문자 범위 제약**이다. Z3는 수학적으로 조건을 만족하기만 하면 어떤 8비트 값(0~255)이든 답으로 내놓을 수 있다. 하지만 실제 플래그는 보통 사람이 읽을 수 있는 ASCII 문자(영문자, 숫자, 기호)로 이루어져 있다. 이 제약을 걸어주지 않으면 Z3가 수학적으로는 맞지만 화면에 이상한 제어문자로 나오는 "쓸모없는 해"를 줄 수도 있고, 반대로 검증 로직 자체가 출력 가능 문자를 전제로 설계되어 있다면 이 제약이 오히려 탐색 공간을 크게 줄여 더 빨리 풀리게 도와준다.

```python
for c in flag:
    s.add(c >= 0x20, c <= 0x7e)   # 스페이스(0x20)~물결표(0x7e) 사이의 출력 가능 문자
```

또는 더 좁혀서 영문/숫자만 허용하고 싶다면 `Or()`로 여러 구간을 합칠 수 있다.

```python
def is_alnum(c):
    return Or(
        And(c >= ord('0'), c <= ord('9')),
        And(c >= ord('A'), c <= ord('Z')),
        And(c >= ord('a'), c <= ord('z')),
    )

for c in flag:
    s.add(is_alnum(c))
```

모델을 얻은 뒤에는 각 `BitVec`의 정수값을 `chr()`로 바꿔서 이어붙이면 최종 문자열이 완성된다.

## 화면/코드에서 보이는 징후
- `[BitVec(f'c{i}', 8) for i in range(n)]`처럼 리스트 컴프리헨션으로 문자 변수 배열을 한 번에 만드는 코드가 보인다.
- `for i in range(len(flag)): s.add(...)`처럼 반복문 안에서 인덱스별 조건을 추가하는 패턴이 있다.
- `s.add(c >= 0x20, c <= 0x7e)`처럼 아스키 범위를 제한하는 조건이 별도로 붙어 있다.
- 결과를 출력하는 부분에서 `''.join(chr(m[c].as_long()) for c in flag)`처럼 모델 값을 문자로 변환해 이어붙이는 코드가 있다.
- 리버싱 대상 코드에 `key[i]`, `table[i]` 같은 상수 배열이 있고, 이 값들이 Z3 스크립트에 파이썬 리스트로 그대로 옮겨져 있다.

## 가장 먼저 할 것
검증 함수에서 플래그의 **길이가 고정인지**부터 확인한다(예: `if (strlen(input) != 20) return 0;` 같은 코드). 길이를 모르는 채로 시작하면 `BitVec` 배열의 크기를 몇 개로 잡아야 할지 알 수 없다. 길이가 코드에 명시적으로 없다면, 배열 크기(버퍼 크기)나 반복문의 상한값을 단서로 추정한다.

## 단계별 절차

**1) 대상 검증 로직 예시(리버싱 결과라고 가정)**

```c
// 각 글자를 key 배열과 XOR한 뒤 target 배열과 비교
unsigned char key[]    = {0x13, 0x37, 0x42, 0x99, 0x01};
unsigned char target[] = {0x56, 0x5a, 0x2e, 0xf5, 0x60};

int check(char *input) {
    for (int i = 0; i < 5; i++) {
        if ((input[i] ^ key[i]) != target[i]) return 0;
    }
    return 1;
}
```

**2) 이를 그대로 Z3로 옮기기**

```python
from z3 import *

key    = [0x13, 0x37, 0x42, 0x99, 0x01]
target = [0x56, 0x5a, 0x2e, 0xf5, 0x60]
n = len(key)

flag = [BitVec(f'c{i}', 8) for i in range(n)]
s = Solver()

for i in range(n):
    s.add((flag[i] ^ key[i]) == target[i])
    s.add(flag[i] >= 0x20, flag[i] <= 0x7e)  # 출력 가능 문자로 제한

if s.check() == sat:
    m = s.model()
    result = ''.join(chr(m[flag[i]].as_long()) for i in range(n))
    print('recovered:', result)
else:
    print('unsat')
```

**3) 문자 사이에 관계가 있는 경우(이전 글자에 의존)**

일부 검증 로직은 `input[i]`가 `input[i-1]`에 의존한다(예: 롤링 체크섬). 이런 관계도 그대로 조건으로 추가하면 된다.

```python
from z3 import *

n = 6
flag = [BitVec(f'c{i}', 8) for i in range(n)]
s = Solver()

target_sum_pairs = [0xaa, 0x91, 0x88, 0x7f, 0x76, 0x6d]  # 예시 목표값

s.add(flag[0] == ord('C'))  # 첫 글자는 보통 알려진 접두사(예: 'C'TF{...})
for i in range(1, n):
    s.add((flag[i] + flag[i-1]) & 0xff == target_sum_pairs[i])

for c in flag:
    s.add(c >= 0x20, c <= 0x7e)

if s.check() == sat:
    m = s.model()
    print(''.join(chr(m[flag[i]].as_long()) for i in range(n)))
```

**4) 여러 해가 나올 수 있을 때 다른 해도 찾아보기**

조건이 느슨해서 여러 개의 문자열이 답이 될 수 있다면, 찾은 해를 배제하는 조건을 추가하고 다시 풀어서 다른 해가 있는지 확인할 수 있다.

```python
if s.check() == sat:
    m = s.model()
    print(''.join(chr(m[flag[i]].as_long()) for i in range(n)))
    # 방금 찾은 해를 제외하는 조건 추가
    s.add(Or([flag[i] != m[flag[i]] for i in range(n)]))
    print(s.check())  # 다른 해가 있으면 sat, 유일한 해면 unsat
```

## 명령어/단축키
- `[BitVec(f'c{i}', 8) for i in range(n)]` : n개의 8비트 문자 변수 배열 생성
- `s.add(c >= 0x20, c <= 0x7e)` : 출력 가능 아스키 범위 제약
- `Or(cond1, cond2, ...)` / `And(cond1, cond2, ...)` : 논리합/논리곱 명시적 결합
- `ord('A')` / `chr(65)` : 파이썬 표준 문자↔코드 변환(제약조건 작성/결과 해석에 사용)
- `''.join(chr(m[c].as_long()) for c in flag)` : 모델의 문자 배열을 최종 문자열로 조립
- `s.add(Or([flag[i] != m[flag[i]] for i in range(n)]))` : 방금 찾은 해를 제외하고 재탐색(다른 해 존재 확인)

## 출력 해석
- `recovered: CTF{...}` 형태의 정상적인 문자열이 나오면 성공이다. 실제 대회 플래그 포맷(`flag{`, `CTF{` 등)과 접두사가 일치하는지 확인하면 정답 여부를 빠르게 검증할 수 있다.
- 결과 문자열에 물음표나 깨진 문자가 섞여 있다면 출력 가능 문자 제약(`0x20~0x7e`)을 빠뜨렸을 가능성이 크다.
- `unsat`이 나오면 인덱스 매핑(`flag[i]`와 `key[i]`/`target[i]`가 정말 같은 i를 가리키는지), 길이, 또는 원본 로직에서 XOR을 덧셈으로 잘못 옮기는 등의 번역 실수를 의심한다.
- 답이 여러 개 나올 수 있는 구조에서 `s.check()`를 반복 호출했는데 계속 `sat`이 나온다면, 조건이 실제 검증 로직보다 느슨하게(예: 일부 검사 누락) 옮겨졌을 가능성이 있다 — 원본 코드의 조건을 다시 대조한다.

## 흔한 실수
- 각 문자에 출력 가능 문자 제약을 빼먹어서, 수학적으로는 맞지만 사람이 읽을 수 없는 이상한 바이트가 답으로 나오는 경우.
- 문자 변수를 8비트가 아니라 32비트로 선언해서, `char`가 원래 갖는 자연스러운 8비트 랩어라운드(wraparound)가 재현되지 않아 잘못된 해를 얻는 경우 — 이 주제는 REV-0270에서 더 자세히 다룬다.
- `input[i]`가 `signed char`인지 `unsigned char`인지 확인하지 않고 부호 비교를 잘못 써서, 실제로는 존재하는 해를 `unsat`으로 잘못 판단하는 경우.
- 인덱스 순서를 뒤바꿔서(`key[i]`와 `target[n-1-i]`를 짝지어야 하는데 `target[i]`와 짝지음) 검증 로직을 잘못 옮기는 경우 — 원본 반복문의 인덱스 진행 방향(정방향/역방향)을 반드시 재확인해야 한다.
- 리스트 컴프리헨션으로 만든 변수 이름이 전부 똑같아서(`BitVec('c', 8)`을 매번 이름 겹치게 생성) Z3가 서로 다른 변수를 같은 변수로 취급해버리는 경우 — 반드시 `f'c{i}'`처럼 인덱스를 이름에 포함시켜 유일하게 만들어야 한다.

## 막혔을 때 다음 체크
- `unsat`이 계속 나온다면 → 조건을 인덱스 몇 개만 남기고 나머지는 주석 처리해서, 어느 인덱스에서 모순이 생기는지 좁혀본다.
- 검증 로직에 8비트/32비트가 섞여 있어 오버플로우 처리가 애매하다면 → REV-0270 문서를 참고해서 비트폭을 정확히 맞춘다.
- 애초에 정수 하나만 다루는 단순한 경우로 돌아가서 개념을 다시 잡고 싶다면 → REV-0268 문서의 기본 `BitVec` 사용법을 다시 참고한다.
- 검증 로직이 반복문/분기가 너무 많아서 손으로 옮기는 것 자체가 비현실적이라면 → REV-0271 문서의 `angr`로 넘어가서 바이너리를 직접 심볼릭 실행시키는 방법을 고려한다. angr을 쓰면 로직을 손으로 Z3 코드로 번역하지 않아도 된다.

## 미니 예제
위 2단계 예제를 완성된 형태로 다시 정리하면 다음과 같다. 실행하면 `recovered: %7*!.`처럼 XOR로 얽힌 5글자 문자열을 즉시 복원한다(실제 출력 문자는 key/target 값에 따라 달라진다).

```python
from z3 import *

key    = [0x13, 0x37, 0x42, 0x99, 0x01]
target = [0x56, 0x5a, 0x2e, 0xf5, 0x60]

flag = [BitVec(f'c{i}', 8) for i in range(len(key))]
s = Solver()
for i in range(len(key)):
    s.add((flag[i] ^ key[i]) == target[i])
    s.add(flag[i] >= 0x20, flag[i] <= 0x7e)

assert s.check() == sat
m = s.model()
print(''.join(chr(m[flag[i]].as_long()) for i in range(len(key))))
```

복원된 문자열은 이후 REV-0266의 `sendline()`으로 실제 바이너리에 넣어 최종 검증할 수 있다.

## 실전 예시: 치환 테이블(S-box) 참조를 조건으로 옮기기
XOR 키만 쓰는 검증 로직보다 조금 더 까다로운 실전 패턴은, 바이너리 안에 **256바이트짜리 치환 테이블(S-box)**을 두고 `output[i] = table[input[i]]` 형태로 각 글자를 변환하는 방식이다. 이런 테이블 조회는 산술식 하나로 표현할 수 없기 때문에, "입력 글자가 특정 값 k일 때만 출력이 `table[k]`와 같다"는 조건들을 `Or()`로 전부 나열해서 표현해야 한다.

리버싱한 바이너리에 다음과 같은(가상의) 256바이트 치환 테이블이 있고, 그 테이블로 4글자짜리 문자열을 변환한 뒤 결과를 상수 배열과 비교한다고 가정한다. 재현 가능하도록 `random.seed()`로 테이블을 고정해서 만든다.

```python
from z3 import *
import random

# 리버싱 대상 바이너리의 .rodata에 있다고 가정한 256바이트 치환 테이블.
# 실전에서는 이 테이블을 직접 손으로 옮겨 적거나 바이너리에서 읽어와야 하지만,
# 여기서는 누구나 동일하게 재현할 수 있도록 고정된 시드로 생성한다.
random.seed(1337)
sbox = list(range(256))
random.shuffle(sbox)

# 바이너리 안에 상수로 박혀 있다고 가정하는 목표값(4바이트) — sbox[ord('A')], sbox[ord('z')], sbox[ord('9')], sbox[ord('!')]
target = [0x00, 0x2d, 0xef, 0x39]

n = len(target)
flag = [BitVec(f'c{i}', 8) for i in range(n)]   # 8비트 문자 변수 4개
s = Solver()

for i in range(n):
    # "flag[i]가 k라면, target[i]는 반드시 sbox[k]와 같다"를 k=0..255 전부에 대해 나열하고 Or로 묶는다.
    # 즉 테이블 조회 table[input] == output을 "가능한 입력값 전부"에 대한 선택지로 풀어서 표현하는 방식이다.
    s.add(Or([And(flag[i] == k, target[i] == sbox[k]) for k in range(256)]))
    s.add(flag[i] >= 0x20, flag[i] <= 0x7e)   # 출력 가능 문자로 제한(항상 넣는 습관)

if s.check() == sat:
    m = s.model()
    recovered = ''.join(chr(m[flag[i]].as_long()) for i in range(n))
    print('recovered:', recovered)   # Az9!
else:
    print('unsat')
```

이 스크립트를 그대로 실행하면 `recovered: Az9!`가 나온다(`random.seed(1337)`로 만든 테이블 기준으로 직접 재현 검증됨). `Or([And(flag[i] == k, target[i] == sbox[k]) for k in range(256)])` 한 줄이 하는 일은 "flag[i]로 가능한 256가지 값 중, 그 값을 테이블에 넣었을 때 실제로 목표값이 나오는 것만 참으로 남긴다"는 뜻이며, 이 방식은 XOR/덧셈처럼 수식으로 바로 표현되지 않는 **임의의 룩업 테이블 기반 변환**에도 그대로 적용할 수 있는 일반적인 패턴이다. 테이블이 256바이트보다 작더라도(예: 16바이트 니블 치환 테이블) `range(256)` 대신 실제 테이블 크기만큼만 순회하도록 바꾸면 그대로 재사용 가능하다.

## 관련 글
- REV-0268 — Z3 BitVec 기초
- REV-0270 — Z3에서 8비트 32비트 Overflow 다루기
- REV-0266 — pwntools로 프로세스 실행하고 입력 보내기

## 출처/검증
- Z3 파이썬 API의 `BitVec` 리스트 패턴, `Or`/`And` 결합, 모델 추출 방식은 Z3 공식 GitHub(Z3Prover/z3) 및 Z3py 튜토리얼 문서를 기준으로 정리했다(2026-09-08 검증).
- `z3-solver`는 서드파티 패키지이므로 `pip install z3-solver`가 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
- 코드 예제는 `pip install z3-solver` 환경의 표준 CPython 3에서 그대로 재현 가능하다.
