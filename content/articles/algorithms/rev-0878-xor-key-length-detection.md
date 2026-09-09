---
id: REV-0878
title: "흔한 XOR 키 길이 탐지 팁 참조"
slug: "rev-0878-xor-key-length-detection"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["XOR 키 길이", "Hamming distance", "해밍 거리", "Index of Coincidence", "일치 지수", "Kasiski", "repeating key XOR", "반복 키 XOR"]
aliases: ["xor 키 길이 구하는 법", "반복 xor 키 찾기", "해밍거리로 키 길이", "다중바이트 xor 크랙"]
symptom_keywords: ["xor 반복 키인데 키 길이를 모르겠음", "단일 바이트 xor로는 안 풀림", "암호문에 반복되는 패턴이 보임", "키가 여러 바이트인 것 같음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
루프에서 키 인덱스가 `i % key_len`처럼 순환하는 **다중바이트(반복 키) XOR**을 만났는데 키 길이를 모를 때는, 암호문 자체의 통계적 성질(해밍 거리, 반복 패턴 간격, 일치 지수)만으로 원문이나 키를 몰라도 키 길이를 먼저 추정할 수 있다.

## 언제 검색해야 하나
- 디스어셈블리에서 `xor al, [key + edx]` 다음 `inc edx` / `cmp edx, key_len` / `xor edx, edx`(모듈러 순환) 패턴을 봤는데 `key_len`을 코드에서 바로 못 찾을 때
- 키가 하드코딩되어 있지 않고 사용자 입력이거나 별도로 전달되어서, 암호문만 갖고 키 길이부터 추정해야 할 때
- 단일 바이트 XOR 브루트포스(256가지)를 이미 시도했는데 결과가 사람이 읽을 수 있는 텍스트로 전혀 안 나올 때(=다중바이트 키를 의심해야 하는 신호)

## 핵심 개념
반복 키 XOR은 `ciphertext[i] = plaintext[i] XOR key[i % key_len]`로 동작한다. 키 길이를 모르면 무차별로 여러 길이를 시도해야 하는데, 아래 세 가지 방법으로 후보를 빠르게 좁힐 수 있다.

**1) 해밍 거리(Hamming distance) 방법 — 가장 널리 쓰임**

같은 키로 XOR된 두 블록은, 원문이 영어/구조화된 데이터처럼 예측 가능한 바이트 분포를 가질 경우 **정규화된 해밍 거리(비트 단위 차이 개수)가 다른 길이보다 작게** 나오는 경향이 있다. 절차:
1. 암호문을 후보 키 길이 `KEYSIZE`(보통 2~40)만큼씩 여러 블록으로 나눈다.
2. 인접한 블록 쌍(또는 여러 쌍의 평균)의 해밍 거리를 계산하고 `KEYSIZE`로 나눠 정규화한다.
3. 정규화된 값이 가장 작은 `KEYSIZE` 몇 개가 실제 키 길이의 강력한 후보다.

**2) 반복 패턴 간격(gcd) 방법 — 평문에 반복 구간이 있을 때**

평문에 같은 문자열이 반복되면(예: 공백이 연속되거나 포맷 문자열이 반복되는 구조화 데이터), 암호문에도 같은 위치 간격으로 동일한 바이트열이 나타난다. 이 반복 지점들 사이의 **간격(거리)들의 최대공약수(GCD)** 가 키 길이의 배수일 가능성이 높다(고전 암호학의 Kasiski 시험과 원리가 동일하다).

**3) 일치 지수(Index of Coincidence, IC) 방법**

후보 키 길이로 열(column)을 나눈 뒤, 각 열 내부에서 같은 바이트값이 반복될 확률(IC)을 계산한다. 열이 실제로 "같은 키 바이트로만 XOR된 그룹"이라면 원문 언어의 자연스러운 통계적 편향이 남아 있어 IC가 무작위 열보다 유의미하게 높게 나온다. 영어 텍스트의 IC는 약 0.065, 완전 무작위 바이트의 IC는 약 0.0039(1/256)에 가깝다.

## 화면/코드에서 보이는 징후
```asm
xor     dl, dl              ; key index = 0
loop_start:
movzx   eax, byte [rsi+rcx] ; ciphertext byte
xor     al, [key+edx]       ; XOR with key[edx]
mov     [rdi+rcx], al
inc     edx
cmp     edx, key_len        ; edx가 key_len에 도달하면
jl      no_wrap
xor     edx, edx            ; 0으로 순환
no_wrap:
inc     rcx
```
`key_len`으로 나눈 나머지 인덱싱(`edx`가 순환하는 카운터)이 다중바이트 XOR의 결정적 신호다.

## 가장 먼저 할 것
암호문(또는 검증 대상 바이트열)을 확보한 뒤, 단일 바이트 XOR 브루트포스(256가지)부터 시도한다. 안 되면 곧바로 해밍 거리 방법으로 키 길이 후보 2~40을 스캔한다.

## 단계별 절차

**1) 해밍 거리로 키 길이 스캔**
```python
def hamming_distance(a: bytes, b: bytes) -> int:
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))

def guess_keysize(ciphertext: bytes, max_len: int = 40) -> list:
    scores = []
    for keysize in range(2, max_len + 1):
        blocks = [ciphertext[i*keysize:(i+1)*keysize] for i in range(4)]
        if len(blocks[-1]) < keysize:
            continue
        pairs = [(blocks[i], blocks[j]) for i in range(4) for j in range(i+1, 4)]
        avg = sum(hamming_distance(a, b) for a, b in pairs) / len(pairs)
        normalized = avg / keysize
        scores.append((normalized, keysize))
    scores.sort()
    return scores[:5]   # 가장 작은 값 5개가 유력 후보
```

**2) 후보 키 길이로 열 분리 후 단일 바이트 XOR 반복**

키 길이가 `N`으로 추정되면, 암호문을 `N`개의 그룹(같은 키 바이트로 XOR된 바이트끼리)으로 나누고 각 그룹에 대해 단일 바이트 XOR 브루트포스를 독립적으로 수행한다.
```python
def split_columns(ciphertext: bytes, keysize: int) -> list:
    return [ciphertext[i::keysize] for i in range(keysize)]
```

**3) 각 열에서 최적의 키 바이트 찾기** — 영어 빈도 분석(공백/모음 비율 등)이나 알려진 평문 조각(known plaintext, REV-0223)으로 각 열의 정답 키 바이트를 하나씩 결정한다.

**4) 전체 키 조립 후 복호화** — 열별로 구한 키 바이트를 순서대로 이어 붙이면 전체 반복 키가 완성된다.

## 명령어/단축키
```python
# 빠른 검증
key_candidates = guess_keysize(ct, 40)
print(key_candidates)
cols = split_columns(ct, key_candidates[0][1])
```
IDA: `key_len`으로 쓰이는 상수를 찾으면 위 통계적 방법 없이도 즉시 확정되므로, 통계 분석 전에 먼저 디스어셈블리에서 상수/전역변수를 한 번 더 찾아보는 것이 빠르다.

## 출력 해석
- 정규화된 해밍 거리가 특정 길이에서 뚜렷하게 낮게 나오면 그 길이(및 배수)가 유력 후보.
- 여러 길이의 점수가 비슷하게 낮으면, 진짜 키 길이의 배수(예: 진짜 3인데 6, 9도 낮게 나옴)일 수 있으니 가장 작은 값을 우선 시도.
- 열별 빈도 분석 결과가 아무 언어로도 읽히지 않으면 키 길이 추정이 틀렸을 가능성이 크므로 다음 후보로 재시도.

## 흔한 실수
- 암호문 길이가 키 길이의 몇 배 이상이 되도록 충분히 길지 않은데 해밍 거리 방법을 적용해서 신뢰할 수 없는 결과를 얻는 것 — 암호문이 너무 짧으면(키 길이의 4~5배 미만) 통계적 방법 자체가 불안정하다.
- 키 길이의 배수(진짜 4인데 8, 12로 추정)를 진짜 키 길이로 오인하는 것 — 가장 작은 후보부터 순서대로 검증해야 한다.
- 이 방법이 "반복 키 XOR"에만 통한다는 걸 잊고, 스트림 암호(키가 매번 바뀌는 진짜 랜덤 키스트림)에 적용해서 헛수고하는 것 — 진짜 OTP(One-Time Pad)라면 통계적 힌트가 전혀 남지 않는다.
- 열 분리(`ciphertext[i::keysize]`) 방향을 반대로(행 우선 대신 열 우선) 착각해서 각 그룹이 실제로는 서로 다른 키 바이트가 섞인 상태로 잘못 나누는 것.

## 막혔을 때 다음 체크
- 키 길이를 구한 뒤 실제 XOR 복호화 로직 자체가 헷갈리면 → REV-0199 — XOR 반복 변환 역산.
- 평문의 일부(플래그 포맷 등)를 이미 안다면 → REV-0223 — Known plaintext와 Flag 형식으로 조건 줄이기.
- 브루트포스로 전체 키 공간을 뒤지는 게 더 빠른 상황인지 판단하려면 → REV-0219 — Brute Force가 가능한 입력 공간 계산.

## 미니 예제
40바이트 암호문에 대해 `guess_keysize`를 실행했더니 다음과 같은 상위 후보가 나왔다고 하자:
```python
[(2.1, 5), (2.3, 10), (2.9, 3), (3.4, 15), (3.6, 7)]
```
가장 작은 값(2.1)의 키 길이 5가 가장 유력한 후보다. `split_columns(ct, 5)`로 5개 그룹으로 나눈 뒤, 각 그룹에 대해 256가지 단일 바이트 XOR을 시도해서 영어 빈도(공백 비율, 알파벳 비율)가 가장 자연스러운 바이트를 그 열의 키로 채택하면 5바이트 전체 키를 복원할 수 있다.

## 관련 글
- REV-0199 — XOR 반복 변환 역산
- REV-0223 — Known plaintext와 Flag 형식으로 조건 줄이기
- REV-0219 — Brute Force가 가능한 입력 공간 계산
- REV-0221 — 역연산 가능한 알고리즘 판단법

## 출처/검증
- 해밍 거리 기반 반복 키 XOR 키 길이 추정 기법: Cryptopals Crypto Challenges Set 1 Challenge 6("Break repeating-key XOR") 공개 문제 설명 기준 (2026-09-09 검증).
- 일치 지수(Index of Coincidence)의 영어 텍스트 기준값(약 0.065)과 무작위 바이트 기준값(1/256): 고전 암호분석(Kasiski 시험, Friedman의 일치 지수) 일반 이론 기준.
