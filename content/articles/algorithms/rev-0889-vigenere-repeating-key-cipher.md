---
id: REV-0889
title: "Vigenere류 반복 키 암호 알아보기"
slug: "rev-0889-vigenere-repeating-key-cipher"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["Vigenere cipher", "비제네르 암호", "반복 키 암호", "repeating key", "polyalphabetic cipher", "Kasiski examination", "Index of Coincidence", "key[i % keylen]"]
aliases: ["비제네르", "반복키 XOR과 차이", "key modulo length 패턴", "다중 치환 암호"]
symptom_keywords: ["key[i % keylen] 패턴이 보임", "키가 입력보다 짧아서 반복 사용됨", "XOR인데 매번 다른 값과 연산함", "키 길이를 모르는데 반복 주기가 있는 것 같음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
암호화 루프에서 평문 인덱스 `i`에 대해 키를 `key[i % keylen]`처럼 **키 길이로 나눈 나머지**로 순환 참조하고 있다면, 이건 고정된 하나의 치환(REV-0888)이 아니라 여러 개의 치환을 키 길이 주기로 번갈아 적용하는 Vigenere류 반복 키 암호(polyalphabetic cipher)다.

## 언제 검색해야 하나
- XOR이나 덧셈 루프(REV-0199, REV-0200)인데 키가 한 바이트가 아니라 **여러 바이트로 구성된 배열**이고, 인덱스 계산에 `% keylen`이나 이와 동등한 순환 로직(`if (k >= keylen) k = 0;`)이 있을 때
- 평문과 같은 위치의 문자가 항상 같은 암호문 문자로 바뀌지 않고, 위치에 따라 다른 결과가 나오는 걸 발견했을 때(치환 암호와 구분되는 핵심 특징)
- 암호문에서 특정 간격(키 길이의 배수)마다 같은 부분 문자열이 반복되는 패턴을 발견했을 때
- "키가 입력보다 짧은데 어떻게 전체를 암호화하지?"라는 질문이 생겼을 때 — 답은 키를 반복 사용하기 때문

## 핵심 개념

### 반복 키 암호의 원리
Vigenere 암호는 16세기에 고안된 고전 암호로, 평문의 각 문자를 시저 암호(REV-0890)처럼 이동시키되 **이동량을 매번 다른 값으로 바꾼다**. 이동량은 키 문자열에서 순서대로 가져오고, 키가 평문보다 짧으면 처음으로 돌아가 반복한다.

```c
// 고전 Vigenere: 알파벳 A-Z 범위에서 순환 이동
void vigenere_encrypt(char *plain, const char *key, int keylen) {
    int i, k = 0;
    for (i = 0; plain[i]; i++) {
        if (isalpha(plain[i])) {
            int shift = key[k % keylen] - 'A';
            plain[i] = 'A' + ((plain[i] - 'A') + shift) % 26;
            k++;   // 알파벳 문자에서만 키 인덱스 증가 (구현에 따라 다름)
        }
    }
}
```
CTF/실전 바이너리에서는 알파벳 범위(mod 26) 대신 **바이트 전체 범위(mod 256, 또는 XOR)**로 확장한 변형이 훨씬 흔하다. 이게 흔히 "반복 키 XOR(repeating-key XOR)"이라 불리는 것이다.

```c
// 실전에서 훨씬 흔한 변형: 바이트 단위 XOR + 순환 키
void repeating_xor(unsigned char *buf, int len, const unsigned char *key, int keylen) {
    for (int i = 0; i < len; i++) {
        buf[i] ^= key[i % keylen];   // 핵심: 인덱스가 키 길이로 순환
    }
}
```
XOR 반복 변환 자체는 REV-0199에서 다루지만, 그 글은 **키 길이가 1바이트인 단순한 경우**를 전제로 한다. 여기서 다루는 반복 키 암호의 핵심 차별점은 **키가 여러 바이트로 이루어져 있고, 인덱스가 `i % keylen`으로 순환**한다는 점이다. 이 차이 하나 때문에 공략 방법이 완전히 달라진다 — 단일 바이트 XOR은 256가지 경우의 수를 다 시도하면 끝나지만(REV-0219), 반복 키는 먼저 **키 길이 자체를 알아내야** 하고, 그 다음에야 각 위치의 키 바이트를 하나씩 복구할 수 있다.

### 키 길이를 모를 때 — Kasiski 시험과 Index of Coincidence
키 길이를 모르는 상태에서 반복 키 암호를 깨는 두 가지 고전적 방법이 있다.

**1) 카시스키 시험(Kasiski examination)**: 암호문에서 3글자 이상의 동일한 부분 문자열이 여러 번 등장하는 지점을 찾는다. 평문에 자주 등장하는 패턴(`the`, `and` 등)이 우연히 키 주기와 같은 위치에서 반복되면 암호문에도 같은 결과가 반복되어 나타난다. 이 반복 지점들 사이의 거리를 모두 구해 최대공약수를 취하면 키 길이의 유력한 후보를 얻을 수 있다.

**2) 반복도 지수(Index of Coincidence, IC)**: 암호문을 후보 키 길이 `n`으로 나눠 `n`개의 부분열로 쪼갠 뒤, 각 부분열이 "한 가지 시저 이동만 적용된 단일 치환 결과"처럼 보이는지 통계적으로 검사한다. 진짜 키 길이로 나눴을 때 각 부분열의 IC 값이 자연어(영어 기준 약 0.067) 근처로 튀어 오르고, 틀린 키 길이로 나누면 무작위 분포에 가까운 값(약 1/26 ≈ 0.0385)이 나온다.

```python
from collections import Counter

def index_of_coincidence(text):
    n = len(text)
    counts = Counter(text)
    return sum(c * (c - 1) for c in counts.values()) / (n * (n - 1))

def guess_key_length(ciphertext, max_len=20):
    scores = {}
    for klen in range(1, max_len + 1):
        cols = [ciphertext[i::klen] for i in range(klen)]
        avg_ic = sum(index_of_coincidence(col) for col in cols) / klen
        scores[klen] = avg_ic
    return sorted(scores.items(), key=lambda kv: -kv[1])
```
키 길이 후보를 찾은 다음에는, 각 부분열을 **단일 바이트 XOR/시저 암호**로 취급해 REV-0199나 REV-0890의 방법을 그대로 적용하면 키의 각 바이트를 하나씩 복구할 수 있다. 즉 반복 키 암호는 결국 **"키 길이만큼의 독립적인 단일 치환 문제"로 분해**된다는 것이 핵심 통찰이다.

### CTF에서는 키 길이를 몰라도 되는 경우가 많다
실전 CTF 바이너리를 리버싱하는 상황이라면, 애초에 디스어셈블리에서 키 배열의 크기(`keylen`)를 직접 읽을 수 있는 경우가 대부분이다. 이 경우 Kasiski/IC 분석 없이 바로 키를 덤프해서 XOR/시저 연산을 되돌리면 끝난다. 통계적 공격은 **키 자체를 바이너리에서 찾을 수 없을 때**(예: 키가 런타임에 사용자 입력으로 들어오거나, 키를 알아내는 것 자체가 문제의 목표일 때)만 필요하다.

## 화면/코드에서 보이는 징후
- 인덱스 계산에 `i % keylen`, `i & (keylen - 1)`(keylen이 2의 거듭제곱일 때), 또는 `if (k == keylen) k = 0;` 형태의 순환 로직이 있음
- 키를 담는 배열의 크기가 처리 대상 데이터보다 눈에 띄게 짧음
- `buf[i] ^= key[i % keylen]` 또는 그와 동등한 XOR/덧셈 연산이 루프 안에 있음
- 같은 위치의 평문 문자가 다른 결과로 암호화되는 것을 디버거로 확인했을 때(치환 암호였다면 항상 같은 결과가 나와야 함)

## 가장 먼저 할 것
루프 안에서 키 인덱스가 **위치(`i`)에 따라 순환한다는 증거**(`% keylen`, 순환 카운터 리셋)부터 확인한다. 그 다음 키 배열이 바이너리 안에 정적으로 존재하는지, 아니면 런타임 입력인지 확인한다. 정적으로 존재하면 바로 덤프해서 XOR/뺄셈으로 되돌리면 끝난다.

## 단계별 절차
1. 반복 연산(XOR/ADD/커스텀 치환)과 순환 인덱스 로직을 확인해 반복 키 암호임을 확정
2. 키 배열이 바이너리에 하드코딩되어 있는지 Hex View/Import로 확인
3. 하드코딩되어 있으면 키와 길이를 그대로 덤프하고 파이썬으로 역연산 재현(REV-0222)
4. 키가 바이너리에 없고 암호문만 있다면, Kasiski 시험 또는 Index of Coincidence로 키 길이 후보를 추출
5. 키 길이 후보로 암호문을 나눠 각 부분열을 단일 바이트 XOR/시저 문제로 분해
6. 각 부분열에 대해 REV-0199(XOR 역산) 또는 REV-0890(시저류) 방법으로 키 바이트를 하나씩 복구
7. 복구한 키 전체로 암호문 전체를 복호화해 사람이 읽을 수 있는 평문(플래그 형식 등)이 나오는지 확인

## 명령어/단축키
```python
# 반복 키 XOR 복호화 (키를 이미 알고 있는 경우)
def repeating_xor_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    return bytes(c ^ key[i % len(key)] for i, c in enumerate(ciphertext))

# 키 길이를 모를 때 Index of Coincidence로 후보 탐색은 본문의
# guess_key_length() 함수 참고
```
IDA: 키 배열 위에서 `A`로 문자열 재해석, `Alt+B`로 짧은 반복 바이트열 검색. Ghidra: Data Type Manager에서 `byte[keylen]`으로 캐스팅.

## 출력 해석
- Index of Coincidence 그래프에서 특정 키 길이(및 그 배수)에서 값이 눈에 띄게 튀어 오르면 그게 실제 키 길이일 가능성이 크다 — 배수 중 가장 작은 값을 우선 시도한다.
- 복호화 결과가 부분적으로만 읽히면 키의 일부 바이트만 맞은 것 — 틀린 바이트가 있는 위치의 부분열만 다시 단일 치환 문제로 재분석한다.
- 키를 완전히 복구했는데도 결과가 깨진 바이트로 나온다면, 인덱스 순환이 `i % keylen`이 아니라 알파벳 문자에서만 카운트를 증가시키는 방식(공백/기호는 건너뜀)일 수 있으니 루프 조건을 다시 확인한다.

## 흔한 실수
- 반복 키 XOR을 단일 바이트 XOR(REV-0199 단순 버전)로 착각해서 256가지 경우의 수만 시도하다 실패하는 것 — 키 길이가 1보다 크면 이 방법은 통하지 않는다.
- Kasiski 시험에서 우연히 겹친 짧은 반복(2글자 이하)까지 신호로 오인해서 잘못된 키 길이를 확정하는 것 — 3글자 이상의 반복만 신뢰도가 있다.
- 알파벳 전용(mod 26) 구현과 바이트 전체(mod 256/XOR) 구현을 혼동해서 잘못된 연산으로 되돌리려는 것.
- 키의 배수 길이(예: 진짜 키 길이가 4인데 8로 착각)로 분석해 부분열은 맞게 나뉘지만 불필요하게 두 배로 많은 부분열을 분석하는 비효율.

## 막혔을 때 다음 체크
- 키 길이가 1이라 단일 바이트로 충분한 경우인지 먼저 확인하려면 → REV-0199 XOR 반복 변환 역산
- 키가 아예 없고 고정된 순열 하나로만 매핑되는 경우와 헷갈리면 → REV-0888 간단한 치환 암호(substitution cipher) 알아보기
- 알파벳 범위 시프트만 쓰는 단순한 변형인지 확인하려면 → REV-0890 시저 암호(Caesar Cipher) 변형 알아보기
- 이미 평문의 일부(플래그 형식 등)를 알고 있어서 키를 바로 역산할 수 있는 상황이면 → REV-0223 Known plaintext와 Flag 형식으로 조건 줄이기

## 미니 예제
어떤 바이너리에서 다음과 같은 함수를 발견했다고 하자.

```c
unsigned char key[] = { 0x13, 0x37, 0xAB, 0xCD };   // keylen = 4
void check(unsigned char *input, int len) {
    for (int i = 0; i < len; i++) {
        input[i] ^= key[i % 4];
    }
    // 이후 input을 정답 배열과 memcmp
}
```
키가 바이너리에 그대로 있으므로 통계적 공격 없이 바로 되돌릴 수 있다.

```python
key = bytes([0x13, 0x37, 0xAB, 0xCD])
expected = bytes.fromhex("...")   # 바이너리에서 뽑은 비교 대상(암호화된 플래그)

flag = bytes(c ^ key[i % len(key)] for i, c in enumerate(expected))
print(flag)
```
만약 키가 바이너리에 없고 암호문만 주어졌다면, 앞서 소개한 `guess_key_length()`로 키 길이 후보(여기서는 4)를 먼저 찾고, 각 위치(`i % 4 == 0, 1, 2, 3`)별로 분리한 부분열을 단일 바이트 XOR 문제로 풀어 키를 바이트 단위로 복구한 뒤 동일한 절차로 복호화하면 된다.

## 관련 글
- REV-0199 — XOR 반복 변환 역산
- REV-0888 — 간단한 치환 암호(substitution cipher) 알아보기
- REV-0890 — 시저 암호(Caesar Cipher) 변형 알아보기
- REV-0223 — Known plaintext와 Flag 형식으로 조건 줄이기
- REV-0222 — 검증 루틴을 Python으로 그대로 재현하기

## 출처/검증
- Vigenere 암호의 반복 키 구조와 카시스키 시험(Kasiski examination)의 원리: David Kahn, *The Codebreakers* 및 표준 고전 암호학 교재(다중 치환 암호 챕터) 기준 (2026-09-09 검증).
- Index of Coincidence를 이용한 키 길이 추정 기법: William F. Friedman의 반복도 지수(Index of Coincidence) 연구에 기반한 고전 암호분석 표준 기법 기준 (2026-09-09 검증).
- 영어 텍스트의 평균 Index of Coincidence 값(약 0.067)과 무작위 균등분포 기준값(1/26 ≈ 0.0385): 표준 암호분석 참고자료 기준 (2026-09-09 검증).
