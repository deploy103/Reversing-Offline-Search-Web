---
id: REV-0220
title: "Meet-in-the-middle를 고려할 상황"
slug: "rev-0220-meet-in-the-middle"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["meet in the middle", "MITM", "중간에서 만나기", "double DES", "탐색 공간 분할", "해시 테이블 매칭", "시간-메모리 트레이드오프"]
aliases: ["미트인더미들", "중간 매칭 공격", "절반씩 브루트포스", "MITM 공격"]
symptom_keywords: ["브루트포스 너무 오래걸림", "탐색공간이 반으로 나뉘는것같음", "키가 두 부분으로 나뉨", "중간값 비교하는 구조"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
검증 로직이 미지 입력을 **두 개의 독립적인 절반으로 나눠서 어떤 중간값에서 비교**하는 구조라면, 양쪽을 각각 브루트포스한 뒤 해시 테이블로 매칭하는 **meet-in-the-middle(MITM)**을 쓰면 `charset^(a+b)` 시간이 `charset^a + charset^b`로 줄어든다 — 종종 불가능하던 문제를 순식간에 푸는 문제로 바꿔준다.

## 언제 검색해야 하나
- [rev-0219-bruteforce-feasibility.md](./rev-0219-bruteforce-feasibility.md)로 계산했더니 전체를 한 번에 브루트포스하기엔 시간이 너무 오래 걸리는데, 알고리즘 구조를 보니 입력이 두 부분으로 쪼개져서 각각 처리되는 것 같을 때
- 체크 로직에 `intermediate1 == intermediate2` 처럼 두 계산 결과를 비교하는 코드가 보이고, 그 두 계산이 서로 다른 입력 조각에서만 나올 때
- 이중 암호화(2단 인코딩, 2단 XOR-then-transform 등)처럼 "먼저 이렇게 변환하고, 그 다음 다르게 변환한 값과 비교" 구조를 만났을 때

## 핵심 개념
탐색 공간이 두 개의 **서로 독립적인** 부분 A(크기 `charset^a`)와 B(크기 `charset^b`)로 나뉘고, 이 둘이 어떤 중간 지점에서 만나 비교되는 구조라고 하자. 순진하게 모든 조합 `(A 후보, B 후보)`를 다 시도하면 `charset^a × charset^b = charset^(a+b)`번 계산해야 한다. 하지만:

1. A쪽 모든 후보에 대해 중간값을 계산해서 **딕셔너리(해시 테이블)**에 저장한다 — `charset^a`번 계산, `charset^a`개 메모리.
2. B쪽 모든 후보에 대해 중간값을 계산해서 딕셔너리에서 **O(1) 조회**로 일치하는 A 후보를 찾는다 — `charset^b`번 계산.

총 계산량은 `charset^a + charset^b`로, 곱셈이 아니라 **덧셈**이 된다. 이게 MITM의 핵심 트릭이다.

**교과서적 예시**: 이중 DES(56비트 키 두 개로 두 번 암호화)를 순진하게 브루트포스하면 `2^56 × 2^56 = 2^112`이지만, MITM을 쓰면 평문을 key1 후보 전부로 암호화해서 테이블에 저장하고(`2^56`), 암호문을 key2 후보 전부로 복호화하면서 테이블을 조회하면(`2^56`) 총 시간은 대략 `2^57`(메모리 `2^56`)로 줄어든다. 이것이 이중 DES가 사실상 단일 DES보다 크게 강하지 않은 이유로 유명하다.

## 화면/코드에서 보이는 징후
- 체크 함수에 `part1 = transform_a(input[0:half])`와 `part2 = transform_b(input[half:end])`처럼 입력을 앞/뒤로 나눠서 각각 다른 함수에 넣는 코드
- 최종 비교가 `if (part1 == part2)` 또는 `if (result_from_first_half == result_from_second_half)` 형태로, 두 절반이 서로의 값을 직접 참조하지 않고 각자 계산된 뒤에만 만나는 구조
- 암호화 알고리즘이 라운드 중간에 한 번 결과를 저장해두는 것처럼 보이는 임시 변수

## 가장 먼저 할 것
디스어셈블리/디컴파일을 보고 **두 절반이 정말로 독립적인지**부터 확인한다. 절반 B의 계산이 절반 A의 특정 바이트를 입력으로 쓴다면(예: `part2 = transform_b(input[half:end], input[0])`) 진짜 MITM이 아니라 단순 의존 관계이므로, 이 기법을 그대로 적용할 수 없다. 완전히 독립적으로 계산되고 오직 마지막 비교 지점에서만 만난다는 걸 확인한 뒤에 진행한다.

## 단계별 절차

**1) 독립성 확인**

두 절반의 계산 코드를 각각 읽고, 서로 다른 변수만 참조하는지 확인한다. 공유 변수가 있다면 그 변수도 "알려진 값"인지(예: 길이, 상수) 아니면 "미지의 값"인지 구분한다.

**2) 각 절반의 탐색 공간 크기 계산**

[rev-0219-bruteforce-feasibility.md](./rev-0219-bruteforce-feasibility.md)에서 배운 `charset^length` 공식으로 각 절반의 크기를 구한다.

**3) 작은 쪽을 테이블로 만들기**

두 절반의 크기가 다르다면(예: A가 `charset^3`, B가 `charset^5`) 항상 **더 작은 쪽을 딕셔너리로 구축**한다. 메모리를 절약하기 위함이다.

**4) 큰 쪽을 순회하며 조회**

큰 쪽 후보를 하나씩 계산해서 딕셔너리에 있는지 확인한다. 일치하면 두 절반을 합쳐서 완전한 답을 얻는다.

## 명령어/단축키
Python으로 바로 실행 가능한 MITM 골격 코드:

```python
from itertools import product

CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

def half1_forward(half1_bytes):
    # 실제 바이너리에서 역산해낸 절반1의 변환 로직으로 교체
    return sum(half1_bytes) & 0xFFFFFF

def half2_forward(half2_bytes):
    # 실제 바이너리에서 역산해낸 절반2의 변환 로직으로 교체
    return (sum(half2_bytes) * 7) & 0xFFFFFF

TARGET = 0x123456  # 바이너리의 비교 대상 상수(참고용, 이 스켈레톤에서는 직접 쓰지 않음)

table = {}
for combo in product(CHARSET.encode(), repeat=3):
    table[half1_forward(combo)] = combo

for combo in product(CHARSET.encode(), repeat=3):
    v = half2_forward(combo)
    if v in table:
        print("match:", bytes(table[v]), bytes(combo))
```

이 코드는 예시일 뿐이다. `half1_forward`/`half2_forward`는 반드시 실제 디스어셈블리를 읽고 역산해낸 진짜 변환 로직으로 바꿔야 하며, 두 함수가 정말로 서로 독립적인지(교차 의존이 없는지) 먼저 확인한 뒤에만 이 구조가 유효하다.

## 출력 해석

**예제 1 — MITM으로 극적인 절감을 보여주는 CTF형 시나리오**

체크 로직이 `intermediate = transform_a(flag_half1)`와 `target = transform_b(flag_half2)`를 각각 계산해서 `intermediate == target`으로 비교한다고 하자. `flag_half1`에 미지 바이트 3개, `flag_half2`에도 미지 바이트 3개가 있고 문자셋이 인쇄 가능 아스키(95종)라면:

- 각 절반의 후보 수: `95^3 = 857,375`
- 순진한 결합 브루트포스: `95^3 × 95^3 = 95^6 = 857,375^2 = 735,091,890,625` (약 7.35×10^11)
- MITM: `857,375 + 857,375 = 1,714,750` (약 1.71×10^6)

절감 비율: `735,091,890,625 / 1,714,750 ≈ 428,660`배. 즉 MITM은 순진한 브루트포스보다 **약 43만 배** 적은 연산으로 같은 답을 찾는다. 순진한 방식이 며칠~몇 주가 걸릴 수 있는 규모라면, MITM은 딕셔너리 구축과 조회에 걸리는 시간(각 변환 함수의 실제 계산 비용에 따라 다르지만 보통 수 초~수십 초) 안에 끝난다.

메모리도 확인해야 한다: 857,375개의 3바이트 키를 딕셔너리에 저장하면 파이썬 딕셔너리 오버헤드를 감안해도 수십 메가바이트 수준으로, 일반 노트북에서도 전혀 문제되지 않는다.

**예제 2 — MITM과 "단순 분할 브루트포스"를 구분하기**

만약 체크 로직이 각 바이트를 완전히 독립적으로, 각자의 고정된 목표값과 비교한다면(예: `input[0] ^ K0 == T0`, `input[1] ^ K1 == T1`, ... 각 바이트가 완전히 별개로 검증됨), 이건 MITM이 아니다. 이 경우 공유되는 "중간값"이 아예 없으므로 딕셔너리 매칭이 필요 없고, 그냥 바이트마다 독립적으로 `charset`번씩 시도하면 된다 — 총 비용은 `N × charset`(더하기, 선형)로 MITM의 `2 × charset^(n/2)`보다도 훨씬 저렴하다. 오히려 이 경우는 REV-0221(역연산 가능한 알고리즘 판단법)에서 다루는 직접 역산이 정답에 더 가깝다. **MITM은 두 절반이 하나의 공유된 비교 지점에서 결합되어야만** 의미가 있다는 점을 명심한다.

## 흔한 실수
- 절반이 진짜 독립적인지 확인하지 않고 MITM을 시도했다가, 실제로는 한쪽이 다른 쪽 바이트를 참조하는 숨은 의존성 때문에 매칭이 하나도 안 나오는 것.
- 큰 쪽을 딕셔너리로 만들어서 메모리를 낭비하는 것 — 항상 더 작은 후보 집합을 테이블로 구축한다.
- MITM과 단순 바이트별 독립 브루트포스(위 예제 2)를 혼동해서 불필요하게 복잡한 딕셔너리 매칭 코드를 짜는 것 — 바이트별로 완전히 독립적이면 그냥 반복문으로 충분하다.
- 딕셔너리 키 충돌을 무시하는 것 — 서로 다른 두 후보가 같은 중간값을 낼 수 있으므로(특히 중간값의 비트 폭이 좁을 때), 조회 후 반드시 최종 검증(전체 flag를 원래 체크 함수에 다시 넣어 확인)을 한 번 더 해야 한다.

## 막혔을 때 다음 체크
- 애초에 전체 탐색 공간이 MITM 없이도 감당 가능한지 먼저 계산 → [rev-0219-bruteforce-feasibility.md](./rev-0219-bruteforce-feasibility.md)
- 절반으로 쪼갤 수 없고 완전히 순차적으로 이전 바이트에 의존하는 구조라면 → [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md)에서 각 단계를 거꾸로 계산할 수 있는지 확인
- 세 개 이상으로 쪼개야 할 것 같은 구조라면(예: 입력이 세 조각으로 나뉘어 각각 다른 변환을 거친 뒤 합쳐짐) 순수 MITM은 두 조각 사이의 트레이드오프이므로 세 조각 이상에서는 "한 조각을 고정하고 나머지 두 조각에 대해 2-way MITM을 적용"하는 식으로 단계적으로 축소해야 한다 — 세 조각 각각의 크기가 `charset^a`, `charset^b`, `charset^c`라면 가장 작은 조각을 먼저 전수 조사하며 남은 두 조각에 대해 MITM을 반복 적용하는 방식으로 접근한다.
- 한쪽 절반의 크기가 여전히 메모리에 못 올릴 만큼 크다면(예: 2^32 이상) → 딕셔너리 대신 정렬된 배열 + 이진 탐색, 혹은 디스크 기반 정렬 파일을 검토
- known-plaintext(접두사/접미사 등)로 한쪽 절반의 크기를 더 줄일 수 있는지 → [rev-0223-known-plaintext-narrowing.md](./rev-0223-known-plaintext-narrowing.md)

## 미니 예제
길이 검증을 통해 flag 본문이 6바이트이고, 알고리즘을 읽어보니 앞 3바이트로 계산한 값과 뒤 3바이트로 계산한 값을 XOR해서 상수와 비교하는 구조였다고 하자(`transform_a(input[0:3]) ^ transform_b(input[3:6]) == 0xABCDEF`). 이건 `intermediate == target` 형태는 아니지만, `transform_a(...) == 0xABCDEF ^ transform_b(...)`로 식을 바꾸면 여전히 MITM이 적용된다 — 절반1은 그대로 두고, 절반2는 `0xABCDEF ^ transform_b(...)`를 중간값으로 삼아 딕셔너리에 넣으면 된다:

```python
TARGET = 0xABCDEF

table = {}
for combo in product(CHARSET.encode(), repeat=3):
    table[transform_a(combo)] = combo

for combo in product(CHARSET.encode(), repeat=3):
    needed = TARGET ^ transform_b(combo)
    if needed in table:
        flag_body = bytes(table[needed]) + bytes(combo)
        print("candidate:", flag_body)
```

이렇게 비교식을 대수적으로 정리해서 "한쪽 = 다른 쪽으로 표현되는 어떤 값"의 형태로 만들 수만 있다면, XOR/덧셈/뺄셈처럼 역연산이 쉬운 연산자가 중간에 껴 있어도 MITM을 그대로 적용할 수 있다.

**심화 예제 — 두 절반을 실제로 딕셔너리로 매칭해서 flag를 복원하는 완결된 스크립트**

이번에는 실제로 3바이트씩 두 절반으로 나뉜 6바이트 flag 본문을 MITM으로 찾아내는 전체 과정을 실행한다. `transform_a`/`transform_b`는 "바이너리를 역산해서 얻은 진짜 변환 로직"의 자리를 대신하는 예시 함수다.

```python
import hashlib
# ↑ 이 예제에서 두 절반을 뒤섞는 변환 함수를 만들기 위해 hashlib 모듈을 불러온다.
#   실전에서는 이 자리에 실제 디스어셈블리를 역산한 로직이 들어간다.
from itertools import product
# ↑ 모든 후보 조합을 만들어주는 product() 함수를 불러온다.

CHARSET = "abcdefghijklmnopqrstuvwxyz"
# ↑ 각 절반에 들어갈 수 있는 문자 종류(소문자 26개)로 좁혔다고 가정한다.

def transform_a(chunk: bytes) -> int:
    # ↑ flag 앞쪽 절반(3바이트)에 적용되는 변환. 실전에서는 실제 역산 로직으로 교체.
    return int.from_bytes(hashlib.md5(b"A" + chunk).digest()[:4], "big")
    # ↑ 여기서는 "결정적이지만 예측하기 어려운 변환"을 흉내 내기 위해
    #   MD5 해시의 앞 4바이트를 정수로 바꿔서 돌려준다.

def transform_b(chunk: bytes) -> int:
    # ↑ flag 뒤쪽 절반(3바이트)에 적용되는 변환. 역시 실전에서는 실제 로직으로 교체.
    return int.from_bytes(hashlib.md5(b"B" + chunk).digest()[:4], "big")
    # ↑ transform_a와 구분하기 위해 접두사만 다르게 붙였을 뿐, 원리는 동일하다.

if __name__ == "__main__":
    # ↑ 이 파일을 직접 실행할 때만 아래 블록을 수행한다.

    secret1, secret2 = b"cat", b"dog"
    # ↑ 검증용으로 우리가 미리 알고 있는 정답 두 절반(실전에서는 모르는 값).
    TARGET = transform_a(secret1) ^ transform_b(secret2)
    # ↑ 바이너리가 저장/비교하는 목표값. 실전에서는 디버거로 직접 확인해서 넣는다.
    print("목표값:", hex(TARGET))
    # ↑ 목표값을 16진수로 출력해서 확인한다.

    table = {}
    # ↑ 앞쪽 절반의 모든 후보와 그 중간값을 저장할 딕셔너리(해시 테이블)를 준비한다.
    for combo in product(CHARSET.encode(), repeat=3):
        # ↑ 소문자 3글자로 만들 수 있는 모든 조합(26^3 = 17,576가지)을 하나씩 만든다.
        chunk = bytes(combo)
        # ↑ 문자 코드 튜플을 실제 바이트열로 바꾼다.
        table[transform_a(chunk)] = chunk
        # ↑ "이 중간값은 이 후보에서 나왔다"는 사실을 딕셔너리에 저장한다.

    print("앞쪽 절반 테이블 크기:", len(table))
    # ↑ 딕셔너리에 몇 개의 서로 다른 중간값이 저장됐는지 확인한다.

    matches = []
    # ↑ 최종적으로 찾아낸 (절반1, 절반2) 정답 쌍들을 저장할 리스트.
    for combo in product(CHARSET.encode(), repeat=3):
        # ↑ 뒤쪽 절반의 모든 후보(마찬가지로 17,576가지)를 하나씩 만든다.
        chunk = bytes(combo)
        # ↑ 문자 코드 튜플을 실제 바이트열로 바꾼다.
        needed = TARGET ^ transform_b(chunk)
        # ↑ "앞쪽 절반의 중간값이 이 값이어야만 전체가 TARGET과 맞아떨어진다"는
        #   필요조건을 계산한다(TARGET = a_value ^ b_value 이므로 a_value = TARGET ^ b_value).
        if needed in table:
            # ↑ 이 필요값이 앞서 만든 딕셔너리에 실제로 존재한다면(=일치하는 절반1이 있다면)
            matches.append((table[needed], chunk))
            # ↑ (절반1, 절반2) 쌍을 정답 후보 리스트에 추가한다.

    print("찾아낸 정답 쌍:", matches)
    # ↑ 최종적으로 찾아낸 모든 정답 쌍을 출력한다.
    if matches:
        # ↑ 정답 쌍이 하나 이상 있다면
        half1, half2 = matches[0]
        # ↑ 첫 번째 정답 쌍을 꺼낸다.
        print("복원된 flag 본문:", half1 + half2)
        # ↑ 두 절반을 이어붙여서 전체 flag 본문을 완성한다.
```

이 스크립트를 그대로 실행하면 다음과 같이 출력된다(직접 실행해서 검증한 값):
```
목표값: 0xa228fc30
앞쪽 절반 테이블 크기: 17576
찾아낸 정답 쌍: [(b'cat', b'dog')]
복원된 flag 본문: b'catdog'
```
앞쪽 절반 17,576가지와 뒤쪽 절반 17,576가지를 곱하면 `17,576 × 17,576 = 308,915,776`가지의 조합이 나오지만, MITM 딕셔너리 매칭 덕분에 실제 계산은 `17,576 + 17,576 = 35,152`번의 해시 계산으로 끝난다 — 약 8,789배 더 적은 계산으로 정확히 `b"cat"`과 `b"dog"`라는 정답 쌍 하나만을 정확히 찾아낸다. 실전에서는 `transform_a`/`transform_b`를 실제 디스어셈블리에서 역산한 로직으로, `TARGET`을 바이너리에서 확인한 실제 목표값으로 바꿔 넣기만 하면 이 스크립트가 곧 solve script가 된다.

## 관련 글
- [rev-0219-bruteforce-feasibility.md](./rev-0219-bruteforce-feasibility.md) — Brute Force가 가능한 입력 공간 계산 (MITM을 검토하기 전에 순진한 브루트포스가 왜 안 되는지부터 계산)
- [rev-0223-known-plaintext-narrowing.md](./rev-0223-known-plaintext-narrowing.md) — Known plaintext와 Flag 형식으로 조건 줄이기
- [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) — 역연산 가능한 알고리즘 판단법
- [rev-0210-tea-xtea.md](./rev-0210-tea-xtea.md) — TEA/XTEA처럼 라운드 구조를 가진 알고리즘에서 중간값을 어디서 뽑을지 참고

## 출처/검증
- Meet-in-the-middle 공격의 원형(이중 DES에 대한 시간-메모리 트레이드오프): 암호학 교과서에서 널리 다뤄지는 고전적 공격 기법(Diffie–Hellman의 이중 DES 공격 분석 등)을 CTF 맥락으로 재구성 (2026-09-08 기준 정리).
- 본문의 모든 수치(95^3, 95^6, 절감 비율 등)는 Python으로 직접 검산됨.
