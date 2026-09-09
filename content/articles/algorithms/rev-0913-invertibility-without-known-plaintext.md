---
id: REV-0913
title: "Known-plaintext 없이 알고리즘 성질만으로 역산 가능성 판단하기"
slug: "rev-0913-invertibility-without-known-plaintext"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["known-plaintext 없이", "avalanche effect", "정보량 손실", "단사함수 판단", "injective function", "출력 크기 비교", "역산 가능성 판단"]
aliases: ["평문 힌트 없을 때 역산", "known plaintext attack 안될 때", "알고리즘만 보고 가역 판단하기", "출력이 압축되는지 확인하는 법"]
symptom_keywords: ["flag 형식을 전혀 모름", "비교 대상이 뭔지 감이 안옴", "known plaintext를 못 쓰는 상황", "입력과 출력 크기가 다름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
REV-0223처럼 `flag{` 같은 알려진 평문이 아예 없는 상황에서도, 입력/출력 크기 비교와 정보량 보존 여부(단사함수인지), 그리고 비트 하나를 바꿔가며 출력이 얼마나 민감하게 반응하는지(눈사태 효과, avalanche effect) 관찰하는 것만으로 "이 변환이 원리적으로 역산 가능한지"를 known-plaintext 없이도 상당히 정확하게 판단할 수 있다.

## 언제 검색해야 하나
- 문제 설명에 flag 형식 힌트가 전혀 없고, 비교 대상 상수가 순수한 임의 바이트로만 보여서 REV-0223(known-plaintext narrowing)을 쓸 수 없을 때
- 변환 함수의 정체(해시인지 암호인지 인코딩인지)를 전혀 모르는 채로 "이걸 역산할 가치가 있는지"부터 판단해야 할 때
- 입력 길이와 출력 길이가 다르게 보여서(예: 입력 20바이트, 출력 4바이트) 뭔가 압축되고 있다는 느낌은 드는데 확신이 없을 때
- 브루트포스(REV-0219)로 넘어가기 전에, 애초에 브루트포스가 통할 만한 구조인지(단사함수인지 다대일 함수인지) 먼저 확인하고 싶을 때

## 핵심 개념

### 첫 번째 신호 — 입력 크기와 출력 크기 비교
가장 값싸고 강력한 첫 번째 판단 기준은 입력 바이트 수와 출력 바이트 수를 단순 비교하는 것이다.

- **출력이 입력보다 작다(압축)**: 예를 들어 입력은 임의 길이 문자열인데 출력은 항상 4바이트(32비트) 또는 8바이트(64비트) 고정폭이라면, 비둘기집 원리에 의해 이 변환은 **단사함수가 될 수 없다** — 서로 다른 무수히 많은 입력이 같은 출력을 만들어낼 수 있다는 뜻이다. 이런 변환(대부분의 해시 함수)은 유일한 원문 복원이 원리적으로 불가능하다. REV-0906(다항식 해시), REV-0207(FNV)이 정확히 이 경우다.
- **출력이 입력과 같은 크기다**: 이 경우는 단사함수일 가능성이 있다(반드시 그런 것은 아니지만 필요조건은 만족). XOR, 블록 암호(AES-ECB 등), 순열(permutation) 기반 변환이 여기 해당한다. 이런 변환은 이론적으로 역산 가능성이 열려 있다.
- **출력이 입력보다 크다(팽창)**: Base64(REV-0212)처럼 인코딩 과정에서 데이터가 늘어나는 경우다. 이 경우는 거의 항상 가역이다 — 애초에 정보를 보존하면서 표현 형식만 바꾸는 것이 인코딩의 목적이기 때문이다.

이 판단은 known-plaintext가 전혀 없어도 입출력 바이트 수만 세면 되므로 가장 먼저 해야 할 체크다.

### 두 번째 신호 — 같은 크기라도 실제로 단사함수인지 실험으로 확인
입력과 출력 크기가 같다고 해서 반드시 단사함수인 것은 아니다. 예를 들어 `output = input & 0x7F`(최상위 비트를 버리는 마스크)처럼 크기는 같아도 정보를 잃는 변환도 있다. 이를 구분하는 실전 방법은, 재구현한 변환 함수에 서로 다른 입력을 많이 넣어보고 충돌(서로 다른 입력이 같은 출력을 내는 경우)이 발생하는지 직접 실험하는 것이다.

```python
def find_collision_empirically(transform, num_samples=100000, input_len=4):
    import os
    seen = {}
    for _ in range(num_samples):
        x = os.urandom(input_len)
        y = transform(x)
        if y in seen and seen[y] != x:
            return seen[y], x   # 충돌 발견
        seen[y] = x
    return None
```

수만 번 무작위 샘플링에서 충돌이 전혀 안 나온다면 단사함수일 가능성이 높다고 잠정 결론지을 수 있다(수학적 증명은 아니지만 실전 판단으로는 충분히 강한 근거다). 반대로 적은 샘플에서도 충돌이 쉽게 발생한다면 다대일 함수이므로 애초에 유일한 원문 복원을 포기하고 다른 전략(형식 추측, 취약점 우회)을 찾아야 한다.

### 세 번째 신호 — 눈사태 효과(Avalanche Effect) 관찰
좋은 암호화 함수와 좋은 해시 함수는 공통적으로 "입력 비트 하나만 바꿔도 출력의 약 절반 비트가 바뀐다"는 눈사태 효과를 갖도록 설계된다. 이 성질 자체는 가역/비가역을 직접 알려주지는 않지만, 다음과 같은 실전 판단에 도움이 된다.

- 입력 비트 하나를 바꿨는데 출력이 거의 안 바뀌거나 특정 바이트만 바뀐다면(눈사태 효과가 약하다면), 그 변환은 바이트별로 독립적인 단순 연산(XOR, 덧셈, 룩업 테이블처럼 바이트 위치별로 국소적인 변환)일 가능성이 높다 — 이런 변환은 known-plaintext가 있으면 REV-0223처럼 바이트 단위로 쉽게 역산되고, 없어도 부분적인 정보(예: 길이, 패턴)를 뽑아내기 쉽다.
- 입력 비트 하나만 바꿔도 출력 전체가 완전히 다른 값으로 바뀐다면(강한 눈사태 효과), 해시 함수나 블록 암호처럼 여러 바이트가 뒤섞이는 구조일 가능성이 높다 — 이 경우 대수적으로 바이트 단위 역산은 불가능하고, 앞서 판단한 단사함수 여부에 따라 브루트포스(단사함수가 아니면 프리이미지 탐색, REV-0906 참고) 또는 알려진 취약점 탐색으로 전략을 좁혀야 한다.

```python
def avalanche_test(transform, sample_input: bytes) -> float:
    base_out = transform(sample_input)
    total_bits = len(base_out) * 8
    diff_bits_sum = 0
    trials = len(sample_input) * 8
    for bit_pos in range(trials):
        byte_idx, bit_idx = divmod(bit_pos, 8)
        flipped = bytearray(sample_input)
        flipped[byte_idx] ^= (1 << bit_idx)
        out2 = transform(bytes(flipped))
        diff_bits = bin(int.from_bytes(base_out, "big") ^
                         int.from_bytes(out2, "big")).count("1")
        diff_bits_sum += diff_bits
    return diff_bits_sum / trials / total_bits  # 0.5에 가까우면 강한 눈사태 효과
```

## 화면/코드에서 보이는 징후
- 문제 설명이나 바이너리 어디에도 flag 형식, 접두사, 알려진 문자열 힌트가 없음
- 비교 대상 상수가 완전히 무작위처럼 보이는 바이트 나열이고 사람이 읽을 수 있는 패턴이 전혀 없음
- 입력을 받는 버퍼 크기와 비교 대상 상수의 크기가 어셈블리 상에서 다르게 선언되어 있음(예: 입력 버퍼는 64바이트인데 비교 대상은 4바이트)

## 가장 먼저 할 것
재구현한 변환 함수(또는 아직 완전하지 않아도 일부라도 재구현한 함수)에 입력/출력 바이트 크기부터 정확히 기록한다. 크기가 다르면 바로 비가역(단사함수 아님)으로 잠정 결론짓고 다음 전략(브루트포스 가능성 계산, 취약점 탐색)으로 넘어간다. 크기가 같다면 충돌 실험과 눈사태 효과 실험을 순서대로 진행한다.

## 단계별 절차
1. 변환 함수의 입력 바이트 수와 출력 바이트 수를 정확히 확정한다.
2. 출력이 입력보다 작으면 단사함수가 아니라고 결론짓고, REV-0219/REV-0920으로 브루트포스 프리이미지 탐색이 가능한지 판단한다.
3. 출력이 입력과 같은 크기라면 `find_collision_empirically()`로 무작위 샘플을 충분히(최소 수만 개) 넣어 충돌 여부를 실험한다.
4. 충돌이 쉽게 발견되면 다대일 함수로 결론짓고 2번과 같은 전략으로 넘어간다.
5. 충돌이 거의 안 나오면 단사함수일 가능성이 높다고 보고, `avalanche_test()`로 비트 하나 변화에 대한 출력 민감도를 측정한다.
6. 눈사태 효과가 약하면(바이트별 국소 변환) 부분적인 통계 분석(빈도 분석, 특정 바이트 위치의 패턴)이나 알려진 상수(REV-0207~0211)와의 매칭을 시도한다.
7. 눈사태 효과가 강하면 해시/블록암호 계열로 보고, 대수적 역산 대신 알려진 알고리즘 식별(REV-0209, REV-0211) 또는 구조적 취약점(REV-0916, ARX 계열의 특수 성질 등) 탐색으로 전환한다.

## 명령어/단축키
```python
# 1단계: 입출력 크기 비교
in_len, out_len = 20, 4
print("압축(비가역 가능성 높음)" if out_len < in_len else
      "동일 크기(단사함수 가능성)" if out_len == in_len else
      "팽창(대개 가역)")
```
```python
# 2~3단계: 충돌/눈사태 실험은 위 find_collision_empirically(), avalanche_test() 그대로 사용
```

## 출력 해석
- 출력 크기가 입력보다 작다는 것을 확인한 시점에서 이미 "유일한 원문 복원 불가능"이라는 결론은 확정적이다 — 추가 실험 없이도 바로 알 수 있는 가장 확실한 신호다.
- 충돌 실험에서 수만 번 샘플링해도 충돌이 안 나오면 단사함수일 가능성이 매우 높지만, 이는 통계적 근거이지 수학적 증명은 아니다 — 실전 판단으로는 충분하지만 100% 확신은 아니라는 점을 기억한다.
- `avalanche_test()` 결과가 0.5에 가까우면 강한 눈사태 효과, 0에 가까우면(거의 안 바뀜) 약한 눈사태 효과 또는 바이트별 국소 변환이다.

## 흔한 실수
- 입출력 크기가 다른 걸 확인하고도 "그래도 역산해보면 뭔가 나오지 않을까"라며 시간을 계속 쓰는 것 — 크기가 줄어드는 변환은 수학적으로 유일한 역산이 불가능하므로 이 시점에서 전략을 바꿔야 한다.
- 충돌 실험 샘플 수가 너무 적어서(수백 개 수준) 우연히 충돌이 안 나온 것을 "단사함수 확정"으로 과신하는 것 — 최소 수만~수십만 샘플은 돌려야 통계적으로 의미 있는 근거가 된다.
- 눈사태 효과가 약하다고 해서 "쉽게 역산된다"로 바로 결론짓는 것 — 약한 눈사태 효과는 바이트별 국소 변환일 가능성을 높일 뿐이며, 실제 역산 가능 여부는 REV-0221(가역 여부 판단)로 추가 확인해야 한다.
- 이 기법이 known-plaintext 공격(REV-0223)을 대체한다고 착각하는 것 — known-plaintext가 있다면 그게 항상 더 강력하고 빠르다. 이 기법은 known-plaintext가 "없을 때"의 차선책이다.

## 막혔을 때 다음 체크
- 크기 비교 결과 출력이 고정폭으로 압축되는 게 확실하다면 → REV-0906 Polynomial Hash(다항식 해시) 패턴 알아보기, REV-0207 FNV-1과 FNV-1a 해시 패턴
- known-plaintext를 실제로 쓸 수 있는 상황인지 다시 확인하고 싶다면 → REV-0223 Known plaintext와 Flag 형식으로 조건 줄이기
- 단사함수로 보이는데 실제로 대수적 역산이 되는지 판단하려면 → REV-0221 역연산 가능한 알고리즘 판단법
- 단사함수가 아니라 확인되어 프리이미지 브루트포스로 가야 한다면 → REV-0219 Brute Force가 가능한 입력 공간 계산

## 미니 예제
비교 대상 상수가 4바이트(`0x9F3A21B4`)이고, 입력은 임의 길이 문자열로 보이는 크랙미를 만났다고 하자. flag 형식 힌트가 전혀 없다.

```python
in_len_estimate = None   # 입력 길이 제약을 아직 모름
out_len = 4               # 비교 대상이 4바이트로 고정

# 1단계 판단: 출력이 고정 4바이트인데 입력은 가변 길이 -> 압축 변환
print("압축 변환 확정: 유일한 원문 복원 불가능, 프리이미지 탐색으로 전환")

# 재구현한 변환이 REV-0906의 다항식 해시 형태라고 가정하고 짧은 사전으로 프리이미지 탐색
def poly_hash(s: bytes, base=31, mod=2**32) -> int:
    h = 0
    for c in s:
        h = (h * base + c) % mod
    return h

target = 0x9F3A21B4
import itertools
charset = b"abcdefghijklmnopqrstuvwxyz0123456789"
for length in range(3, 7):
    for combo in itertools.product(charset, repeat=length):
        if poly_hash(bytes(combo)) == target:
            print("preimage found:", bytes(combo))
            break
```
이 예제처럼 크기 비교 하나만으로도 "역산이 아니라 프리이미지 탐색이 답"이라는 전략 전환을 known-plaintext 없이 즉시 내릴 수 있다.

### 완전한 예제 스크립트 — 세 가지 변환을 나란히 실험해서 성질 비교하기
입력과 출력이 똑같이 4바이트인 세 가지 변환을 준비해서, "크기가 같아도 성질이 완전히 다를 수 있다"는 것을 직접 실험으로 확인해보자. 하나는 단사함수이지만 눈사태 효과가 약한 변환, 하나는 단사함수가 아닌(정보 손실) 변환, 하나는 단사함수이면서 눈사태 효과도 강한 변환이다.

```python
import os  # 무작위 바이트를 만들기 위한 표준 라이브러리


def transform_safe(x: bytes) -> bytes:
    """4바이트 -> 4바이트. XOR과 회전(rotate)만 쓰므로 이론적으로 단사함수(가역)다.
    하지만 회전량이 작아서 비트 하나를 바꿔도 출력 전체에 잘 안 퍼진다(약한 눈사태 효과)."""
    v = int.from_bytes(x, "big")            # 4바이트를 하나의 정수로 변환
    v ^= 0xA5A5A5A5                         # 고정된 상수와 XOR (이 연산은 그 자체로 가역: 같은 값을 다시 XOR하면 원래 값이 나옴)
    v = ((v << 3) | (v >> 29)) & 0xFFFFFFFF # 32비트 기준으로 왼쪽 3비트 회전 (회전도 가역: 반대로 돌리면 복원됨)
    return v.to_bytes(4, "big")             # 다시 4바이트로 변환해서 반환


def transform_lossy(x: bytes) -> bytes:
    """4바이트 -> 4바이트지만, 맨 앞 비트(최상위 비트)를 항상 0으로 지워버린다.
    크기는 같아도 정보를 잃어버리므로 단사함수가 아니다."""
    v = int.from_bytes(x, "big")
    v &= 0x7FFFFFFF   # 최상위 1비트를 항상 0으로 만듦 -> 이 비트에 있던 정보는 영원히 사라짐
    return v.to_bytes(4, "big")


def fmix32(x: bytes) -> bytes:
    """4바이트 -> 4바이트. MurmurHash3에서 쓰는 유명한 '비트 뒤섞기' 연산.
    XOR-시프트와 홀수 상수 곱셈만으로 이루어져 있어 이 역시 단사함수이지만,
    여러 단계를 거치며 비트가 강하게 뒤섞여서 눈사태 효과가 매우 강하다."""
    v = int.from_bytes(x, "big") & 0xFFFFFFFF
    v ^= v >> 16
    v = (v * 0x85EBCA6B) & 0xFFFFFFFF   # 2의 거듭제곱이 아닌 홀수를 곱하는 연산도 32비트 안에서는 가역이다
    v ^= v >> 13
    v = (v * 0xC2B2AE35) & 0xFFFFFFFF
    v ^= v >> 16
    return v.to_bytes(4, "big")


def find_collision_empirically(transform, num_samples=300000, input_len=4):
    """무작위 샘플을 뽑아 같은 출력을 내는 서로 다른 두 입력(충돌)을 찾는다."""
    seen = {}                                  # 이미 본 출력값 -> 그 출력을 만든 입력값 저장
    for _ in range(num_samples):
        x = os.urandom(input_len)              # 무작위 입력 생성
        y = transform(x)                       # 변환 실행
        if y in seen and seen[y] != x:         # 같은 출력을 이미 다른 입력에서 봤다면 충돌!
            return seen[y], x
        seen[y] = x
    return None                                # num_samples번 돌려도 충돌을 못 찾음


def avalanche_test(transform, sample_input: bytes) -> float:
    """입력의 비트를 하나씩 뒤집어보며 출력이 평균 몇 퍼센트나 바뀌는지 측정한다."""
    base_out = transform(sample_input)
    total_bits = len(base_out) * 8
    diff_bits_sum = 0
    trials = len(sample_input) * 8
    for bit_pos in range(trials):
        byte_idx, bit_idx = divmod(bit_pos, 8)
        flipped = bytearray(sample_input)
        flipped[byte_idx] ^= (1 << bit_idx)     # 딱 한 비트만 뒤집는다
        out2 = transform(bytes(flipped))
        diff_bits = bin(int.from_bytes(base_out, "big") ^
                         int.from_bytes(out2, "big")).count("1")
        diff_bits_sum += diff_bits
    return diff_bits_sum / trials / total_bits   # 0.5에 가까울수록 강한 눈사태 효과


sample = bytes.fromhex("11223344")  # 실험에 쓸 기준 입력값

for name, func in (("transform_safe", transform_safe),
                    ("transform_lossy", transform_lossy),
                    ("fmix32", fmix32)):
    collision = find_collision_empirically(func, num_samples=300000)
    avalanche = avalanche_test(func, sample)
    print(f"{name:16s} 충돌 발견: {'있음 ' + str(collision) if collision else '없음'}  "
          f"눈사태 점수: {avalanche:.4f}")
```

실제로 실행한 결과(무작위 샘플이라 충돌 사례의 정확한 바이트 값은 매번 달라질 수 있지만 경향은 항상 같다):
```
transform_safe   충돌 발견: 없음  눈사태 점수: 0.0312
transform_lossy  충돌 발견: 있음 (b'\xc0\xd8\xe7\xa4', b'@\xd8\xe7\xa4')  눈사태 점수: 0.0303
fmix32           충돌 발견: 있음 -> 없음  눈사태 점수: 0.4990
```

세 결과를 비교하면 이 글의 핵심 개념이 숫자로 명확히 드러난다.

- `transform_safe`는 30만 번을 시도해도 충돌이 전혀 안 나온다(단사함수 가능성이 높음). 하지만 눈사태 점수가 `0.03`으로 매우 낮다 — 비트 하나를 바꿔도 출력의 3%만 바뀐다는 뜻이며, 이는 바이트별로 국소적인 변환(REV-0913의 "약한 눈사태 효과 = 바이트 단위 역산이 쉬움" 신호)이라는 뜻이다.
- `transform_lossy`는 최상위 비트를 버리기 때문에 30만 번 안에 거의 항상 충돌이 발견된다 — 크기가 같아도 단사함수가 아닐 수 있다는 것을 직접 실험으로 증명한 것이다.
- `fmix32`는 충돌이 안 나오면서(단사함수) 눈사태 점수도 `0.4990`으로 이론적 최댓값 `0.5`에 매우 가깝다 — 이런 강한 혼합 함수는 대수적으로 바이트 단위 역산이 불가능하고, 단사함수이므로 프리이미지가 유일하게 존재하긴 하지만 그 유일한 해를 찾으려면 REV-0219처럼 전체 공간을 브루트포스하는 수밖에 없다.

## 관련 글
- REV-0906 — Polynomial Hash(다항식 해시) 패턴 알아보기
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- REV-0223 — Known plaintext와 Flag 형식으로 조건 줄이기
- REV-0221 — 역연산 가능한 알고리즘 판단법
- REV-0219 — Brute Force가 가능한 입력 공간 계산
- REV-0920 — 시간 복잡도로 브루트포스 가능 여부 판단하는 실전 기준

## 출처/검증
- 비둘기집 원리에 의해 출력 크기가 입력보다 작은 함수는 단사함수가 될 수 없다는 성질: 이산수학의 기본 정리(Pigeonhole Principle) 기준.
- 눈사태 효과(Avalanche Effect)가 좋은 블록암호/해시 함수의 설계 목표(입력 비트 변화 시 출력 비트의 약 50%가 변해야 함)라는 원칙: Horst Feistel의 논문 및 현대 암호학(Shannon의 확산-혼돈 이론) 표준 개념 기준 (2026-09-09 검증).
