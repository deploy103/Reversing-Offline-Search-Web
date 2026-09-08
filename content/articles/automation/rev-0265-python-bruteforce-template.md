---
id: REV-0265
title: "Python Brute Force 기본 템플릿"
slug: "rev-0265-python-bruteforce-template"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["python 브루트포스 템플릿", "itertools.product 브루트포스", "python 전수조사 코드", "brute force charset python"]
aliases: ["파이썬 브루트포스 코드", "전수조사 템플릿", "itertools product 예제"]
symptom_keywords: ["키 몇 자리인지 모름", "전수조사 코드 어떻게 짜지", "brute force 스크립트 필요"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
문자 집합과 길이가 작은 값(패스워드, PIN, 짧은 키)은 `itertools.product`로 모든 조합을 생성하며 검증 함수를 호출하다가 맞으면 즉시 멈추는 제너릭 브루트포스 템플릿 하나로 대부분 해결되지만, 시도하기 전에 반드시 키스페이스 크기부터 계산해 현실적으로 가능한지 확인해야 한다.

## 언제 검색해야 하나
- 리버싱 중 발견한 검증 로직이 XOR/회전 등으로 깔끔하게 역산되지 않고, 입력을 하나씩 넣어 결과를 비교하는 수밖에 없을 때(예: 해시 비교, 단방향 함수)
- PIN 번호나 짧은 영숫자 키처럼 키스페이스가 충분히 작아서 전수조사가 현실적인 시간 안에 끝날 것으로 예상될 때
- 이미 앞부분(prefix)이나 일부 문자를 알고 있어서 나머지만 좁혀서 찾으면 되는 상황일 때

## 핵심 개념
브루트포스는 "가능한 모든 입력을 하나씩 시도해서 조건을 만족하는 것을 찾는" 가장 단순하지만 가장 무식한 방법이다. Python 표준 라이브러리의 `itertools.product`는 여러 개의 반복 가능한 객체(iterable)의 **데카르트 곱**을 생성한다 — 즉 문자 집합(charset)과 자릿수(length)를 주면 가능한 모든 조합을 순서대로 만들어준다.

브루트포스를 쓰기 전에 반드시 확인해야 할 것은 **키스페이스 크기**다.
```
키스페이스 크기 = (문자 집합 크기) ^ (길이)
```
예를 들어 소문자+숫자(36자) 4자리면 `36^4 = 1,679,616`으로 노트북에서도 몇 초 안에 끝나지만, 대소문자+숫자+기호(약 94자) 10자리라면 `94^10 ≈ 5.3 × 10^19`로 슈퍼컴퓨터로도 현실적이지 않다. 이 계산을 먼저 하지 않고 무작정 스크립트를 돌리면 며칠~평생이 걸려도 안 끝날 수 있다. 키스페이스가 언제 "현실적"인지에 대한 판단 기준은 REV-0219(브루트포스 타당성 검토)에서 자세히 다룬다.

## 화면/코드에서 보이는 징후
- 디컴파일된 검증 함수가 해시 계산(MD5/SHA/CRC) 후 상수와 비교하는 형태 — 역산이 불가능하고 앞에서 뒤로만 계산 가능한 단방향 함수라면 전수조사 외에 다른 선택지가 별로 없다.
- 입력 길이가 짧게(4~8자) 고정되어 있고, 사용 가능한 문자 종류가 코드 안에 명시적으로 나열되어 있는 경우(`"0123456789"`, `"ABCDEF"` 등).
- 프로그램이 "몇 번째 문자가 틀렸는지"를 알려주는 부실한 검증 로직(문자 하나씩 비교하며 조기 종료) — 이 경우는 전체 브루트포스보다 문자 단위로 좁혀나가는 것이 훨씬 빠르다(뒤의 "문자 단위 브루트포스" 참고).

## 가장 먼저 할 것
검증 함수를 파이썬으로 **정확히 재현**한 뒤(REV-0264의 32비트 마스킹 규칙 등을 지켜서), 그 함수에 후보 입력을 넣어 참/거짓을 판별하는 `check(candidate) -> bool` 형태로 정리한다. 브루트포스 루프는 이 `check` 함수만 있으면 재사용 가능한 뼈대로 바로 붙일 수 있다.

## 단계별 절차
**1) 키스페이스 크기부터 계산 (반드시 먼저)**
```python
charset = "0123456789abcdef"
length = 6
keyspace = len(charset) ** length
print(f"키스페이스: {keyspace:,}개")
# 초당 100만회 검증 가정 시 예상 소요 시간(최악의 경우)
print(f"예상 최대 소요 시간(1M/s 가정): {keyspace / 1_000_000:.1f}초")
```
이 값이 수천만을 넘어가면 순수 Python 반복문은 느릴 수 있으니, 검증 로직을 더 빠르게 만들거나(예: numpy, 병렬화) 다른 접근(부분 정보 활용, Z3 같은 SMT 솔버)을 REV-0219 기준으로 검토한다.

**2) 기본 템플릿 — itertools.product**
```python
import itertools

def check(candidate: str) -> bool:
    # 실제로는 이 자리에 리버싱으로 파악한 검증 로직을 그대로 재현
    target = "e48e13207341b6bffb7fb1622282247b"   # md5("1337")
    import hashlib
    return hashlib.md5(candidate.encode()).hexdigest() == target

charset = "0123456789"
length = 4

for tup in itertools.product(charset, repeat=length):
    candidate = "".join(tup)
    if check(candidate):
        print("FOUND:", candidate)   # FOUND: 1337
        break
else:
    print("not found in this keyspace")
```
`for...else`의 `else`는 루프가 `break` 없이 끝났을 때만 실행되므로, "다 찾아봤지만 없었다"는 상황을 깔끔하게 처리할 수 있다.

**3) 가변 길이까지 함께 탐색**
```python
import itertools

def brute_force(charset: str, min_len: int, max_len: int, check):
    for length in range(min_len, max_len + 1):
        for tup in itertools.product(charset, repeat=length):
            candidate = "".join(tup)
            if check(candidate):
                return candidate
    return None

result = brute_force("abc123", 3, 5, check)
print(result)
```

**4) 문자 단위로 조기 종료가 가능한 경우 (훨씬 빠름)**
검증 로직이 앞에서부터 한 글자씩 비교하며 실패 지점을 (부채널로든, 타이밍으로든, 혹은 디버거로 직접) 알 수 있다면, 전체 조합 대신 자리별로 좁혀나간다. 키스페이스가 `N^L`에서 `N*L`로 줄어드는 극적인 효과가 있다.
```python
def check_prefix(prefix: str) -> bool:
    # 검증 함수가 "여기까지는 맞다"를 판별할 수 있는 형태로 만들어야 함
    # 예: 부분 해시 비교, 또는 디버거로 각 자리 통과 여부 관찰
    ...

charset = "0123456789abcdef"
found = ""
for pos in range(8):               # 8자리라고 가정
    for c in charset:
        if check_prefix(found + c):
            found += c
            break
    else:
        raise RuntimeError(f"{pos}번째 자리에서 막힘")
print(found)
```

**5) 바이트 값(0~255) 전수조사 — 단일 바이트 키 찾기 예시**
```python
def check_byte_key(key: int, expected: bytes, known_plain_prefix: bytes) -> bool:
    decrypted = bytes(b ^ key for b in expected[:len(known_plain_prefix)])
    return decrypted == known_plain_prefix

expected = bytes.fromhex("...")
for key in range(256):
    if check_byte_key(key, expected, b"flag{"):
        print("key =", hex(key))
        break
```

## 명령어/단축키
- `python3 -O script.py` : assert 문 제거 등 약간의 최적화(브루트포스 자체 속도에는 큰 영향 없음)
- 진행 상황을 보고 싶으면 `tqdm` 같은 서드파티 없이도 `if i % 100000 == 0: print(i)`처럼 카운터로 충분
- `itertools.product(charset, repeat=length)` 대신 `itertools.product(*[charset]*length)`도 동일하게 동작(가독성 차이만 있음)

## 출력 해석
- 루프가 `break` 없이 끝나 `for...else`의 `else`가 실행되면, 가정한 문자 집합이나 길이가 틀렸다는 뜻이다 — charset을 넓히거나 길이 범위를 다시 검토한다.
- 실행이 너무 오래 걸려서 끝나지 않는다면, 먼저 1단계의 키스페이스 계산으로 돌아가 애초에 현실적인 문제였는지부터 재확인한다. 현실적이지 않다면 순수 브루트포스가 아니라 검증 로직 자체를 역산하는 방법(REV-0262, REV-0263, REV-0264 등)을 다시 찾아야 한다.

## 흔한 실수
- 키스페이스 크기를 계산하지 않고 무작정 실행해서, 몇 시간을 기다려도 끝나지 않는 조합을 돌리는 것 — 항상 1단계를 먼저 한다.
- `check()` 함수 안의 검증 로직을 원본 C/어셈블리와 다르게(특히 32비트 마스킹이나 엔디안을 빼먹고) 재현해서, 정답이 존재하는데도 영원히 못 찾는 것 — REV-0264, REV-0260을 참고해 검증 함수부터 별도로 단위 테스트한다.
- 문자 단위 조기 종료가 가능한 상황인데 이를 못 알아채고 전체 조합을 다 도는 것 — 키 길이가 조금만 길어도 이 차이가 몇 초와 몇 년의 차이를 만든다.
- 대소문자를 구분해야 하는데 charset에 한쪽만 넣거나, 반대로 대소문자를 구분하지 않아도 되는데 둘 다 넣어 키스페이스를 불필요하게 키우는 것.

## 막혔을 때 다음 체크
- 지금 하려는 브루트포스가 현실적인 시간 안에 끝날지 판단 기준이 필요하면 → REV-0219 (브루트포스 타당성 검토)에서 계산 예시와 함께 확인.
- 검증 로직 안에 XOR이 있다면 → REV-0262 (XOR 역산 템플릿)로 역산이 가능한지 먼저 검토 — 역산이 되면 브루트포스보다 훨씬 빠르다.
- 검증 로직에 32비트 해시/체크섬 연산이 있다면 → REV-0264 (32비트 Overflow 재현)로 먼저 정확히 재현.
- 회전 연산이 섞여 있다면 → REV-0263 (Rotate 함수 템플릿) 참고.

## 미니 예제
4자리 숫자 PIN을 검증하는 함수가 있고, MD5 해시와 비교한다고 하자.
```python
import itertools
import hashlib

target_hash = "81dc9bdb52d04dc20036dbd8313ed055"  # md5("1234") -- 실전에선 이 자리에 실제로 확보한 해시를 넣는다

def check(pin: str) -> bool:
    return hashlib.md5(pin.encode()).hexdigest() == target_hash

charset = "0123456789"
length = 4
keyspace = len(charset) ** length
print(f"키스페이스: {keyspace:,}개 (충분히 작음 -> 브루트포스 타당)")

for tup in itertools.product(charset, repeat=length):
    candidate = "".join(tup)
    if check(candidate):
        print("PIN found:", candidate)
        break
```
이 예제처럼 실행 전에 키스페이스를 출력해 "이 문제는 브루트포스가 맞는 전략인가"를 항상 먼저 확인하는 습관이 시간 낭비를 막는 가장 확실한 방법이다.

## 관련 글
- REV-0262 — Python XOR 역산 템플릿
- REV-0263 — Python Rotate 함수 템플릿
- REV-0264 — Python 32비트 Overflow 재현
- ../algorithms/rev-0219-bruteforce-feasibility.md

## 출처/검증
- `itertools.product`의 데카르트 곱 생성 동작은 Python 공식 문서(itertools 모듈) 기준(2026-09-08 확인). 키스페이스 크기 계산과 브루트포스 타당성 판단 기준은 일반적인 CTF 리버싱/암호학 방법론을 정리한 것.
