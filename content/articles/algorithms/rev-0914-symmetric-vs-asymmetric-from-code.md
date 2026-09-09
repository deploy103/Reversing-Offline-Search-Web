---
id: REV-0914
title: "대칭 vs 비대칭 여부를 코드만 보고 판단하는 법"
slug: "rev-0914-symmetric-vs-asymmetric-from-code"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["대칭키 비대칭키 구분", "symmetric asymmetric 판단", "RSA 흔적", "빅넘버 연산", "모듈러 거듭제곱", "big integer 코드", "공개키 개인키 리버싱"]
aliases: ["RSA인지 AES인지 구분하기", "공개키 암호 알아보는 법", "빅넘버 연산 흔적", "modpow 패턴 알아보기"]
symptom_keywords: ["코드에 아주 큰 정수 배열이 여러개 있음", "곱셈과 나머지 연산이 반복되는 루프", "e, n, d 같은 변수명이 보임", "GMP나 bignum 라이브러리를 링크함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
대칭키(symmetric) 암호는 바이트/워드 단위(8~64비트) 연산이 빠르게 반복되는 반면, 비대칭키(asymmetric, 공개키) 암호는 수백~수천 비트짜리 큰 정수(bignum)를 모듈러 거듭제곱하는 연산이 특징이므로, 코드에서 다루는 정수의 비트 폭과 연산 종류(고정폭 XOR/치환 vs 임의정밀도 곱셈/모듈러 연산)만 확인해도 둘을 구분할 수 있다.

## 언제 검색해야 하나
- 크랙미나 바이너리에 "암호화" 로직이 있는 건 확실한데, 이게 AES 같은 대칭 암호인지 RSA 같은 공개키 암호인지 감이 안 잡힐 때
- 변수명이나 상수에 `e`, `n`, `d`, `p`, `q`처럼 RSA를 연상시키는 이름이 보이는데 확신이 없을 때
- 코드에서 32비트/64비트 레지스터로는 도저히 표현 안 되는 큰 배열 기반 정수 연산(수백 바이트짜리 배열을 통째로 곱하고 나누는 루프)이 보일 때
- `import`나 `strings` 결과에 `libgmp`, `openssl`, `bignum`, `mpz_` 같은 이름이 보여서 큰 정수 라이브러리를 쓰고 있다는 심증이 들 때

## 핵심 개념

### 대칭키와 비대칭키의 근본적인 차이
대칭키 암호(AES, DES, ChaCha20, 그리고 CTF의 커스텀 XOR/치환 기반 알고리즘 대부분)는 암호화와 복호화에 **같은 키**를 쓴다. 반면 비대칭키(공개키) 암호(RSA, ECC, ElGamal 등)는 암호화에 쓰는 키(공개키)와 복호화에 쓰는 키(개인키)가 **서로 다르며**, 개인키 없이 공개키만으로 복호화하는 것이 계산적으로 불가능하도록 설계된다. 이 차이는 코드의 겉모습에도 뚜렷하게 드러난다.

| 특징 | 대칭키 (AES, XOR류) | 비대칭키 (RSA류) |
|---|---|---|
| 다루는 정수 크기 | 8/16/32/64비트 고정폭 | 512~4096비트 임의정밀도(bignum) |
| 핵심 연산 | XOR, 치환(S-box), 시프트, 덧셈 | 모듈러 거듭제곱(modular exponentiation), 큰 수 곱셈/나눗셈 |
| 코드 구조 | 짧고 빠른 루프가 여러 라운드 반복 | 곱셈-제곱(square-and-multiply) 알고리즘 형태의 반복 |
| 대표 라이브러리 흔적 | 없거나 자체 구현 | `libgmp`, `OpenSSL BIGNUM`, `mbedtls bignum`, 또는 자체 bignum 구현 |
| 변수명 힌트 | `key`, `iv`, `block`, `state` | `n`, `e`, `d`, `p`, `q`, `modulus`, `exponent`, `pubkey`, `privkey` |

### 비대칭키의 가장 확실한 지문 — 모듈러 거듭제곱
RSA의 핵심 연산은 다음 한 줄로 요약된다.

```
ciphertext = plaintext^e mod n     (암호화, e와 n은 공개키)
plaintext  = ciphertext^d mod n    (복호화, d는 개인키)
```

이 연산을 그대로 반복 곱셈으로 구현하면 지수 `e`가 클 때 극도로 느리므로, 실제 구현(그리고 리버싱 대상 코드)은 거의 항상 **square-and-multiply**(제곱-곱셈) 알고리즘을 쓴다.

```c
// 전형적인 modpow 구현 골격 (bignum 타입 가정)
bignum modpow(bignum base, bignum exp, bignum mod) {
    bignum result = 1;
    base = base % mod;
    while (exp > 0) {
        if (exp & 1) {
            result = (result * base) % mod;
        }
        exp >>= 1;
        base = (base * base) % mod;
    }
    return result;
}
```

이 루프 구조(지수를 비트 단위로 오른쪽 시프트하면서 조건부 곱셈 + 매 단계 제곱)는 RSA/ECC/Diffie-Hellman 등 모든 모듈러 거듭제곱 기반 암호에서 거의 동일한 형태로 반복된다. 이 패턴을 발견하면 비대칭키 암호를 보고 있다고 거의 확신할 수 있다.

### 큰 정수 표현 방식 확인하기
비대칭키 암호는 정수 하나를 32비트/64비트 레지스터에 담을 수 없으므로, 반드시 다음 중 하나의 방식으로 큰 정수를 표현한다.

1. **배열 기반 bignum**: `uint32_t limbs[64]`처럼 여러 워드를 이어붙여 하나의 큰 정수를 표현. 자체 구현 RSA에서 흔하다.
2. **외부 라이브러리 호출**: `libgmp`(`mpz_powm`, `mpz_mul` 등), OpenSSL의 `BN_mod_exp`, `BN_mul` 같은 함수를 import해서 사용. `nm`/`objdump`로 import 심볼을 확인하면 바로 드러난다.

어느 쪽이든 "정수 하나가 여러 워드/여러 함수 호출에 걸쳐 표현된다"는 공통점이 있으며, 이는 대칭키 암호에서는 절대 나타나지 않는 패턴이다.

### 판단이 왜 중요한가 — 이후 전략이 완전히 달라진다
대칭키로 판단되면 REV-0199~0223 계열의 기법(XOR 역산, 룩업 테이블 역산, known-plaintext)이 적용 대상이 된다. 비대칭키(특히 RSA)로 판단되면 전략이 완전히 바뀐다 — 대수적 역산 대신 다음과 같은 **RSA 특유의 취약점 패턴**을 찾아야 한다.

- `n`이 작다(예: 256비트 이하) → 소인수분해로 개인키 복구 가능 (`n = p*q`)
- `e`가 매우 작다(예: `e=3`)이고 메시지가 짧다 → Low Public Exponent Attack
- 같은 메시지를 서로 다른 공개키로 여러 번 암호화 → Common Modulus Attack, Håstad's Broadcast Attack
- `p`, `q`가 너무 가까운 값 → Fermat Factorization

이런 취약점은 XOR 역산과는 완전히 다른 종류의 지식(정수론, RSA 구조적 약점)을 요구하므로, "이게 RSA구나"라고 확정하는 순간 탐색 방향을 완전히 전환해야 한다.

## 화면/코드에서 보이는 징후
- 지수를 비트 단위로 우측 시프트(`exp >>= 1` 또는 `exp /= 2`)하면서 조건부로 곱셈을 수행하는 루프(square-and-multiply)
- 정수 하나가 여러 워드 배열(`uint32_t limbs[N]`)로 표현되거나, `mpz_t`/`BIGNUM` 타입을 다루는 함수 호출이 보임
- `strings`/`nm` 결과에 `gmp`, `openssl`, `BN_`, `mpz_`, `RSA_` 문자열/심볼
- 변수명이나 주석에 `modulus`, `exponent`, `pubkey`, `privkey`, `n`, `e`, `d` 등이 등장
- 키 크기가 128비트를 훨씬 넘는(256, 512, 1024, 2048비트) 값들이 상수로 박혀 있음

## 가장 먼저 할 것
`file`/`checksec`/`strings`로 `libgmp`, `openssl`, `BN_`, `mpz_` 관련 심볼이 링크되어 있는지 가장 먼저 확인한다. 없다면 코드에서 다루는 정수의 최대 비트 폭을 확인한다 — 64비트를 넘는 정수를 배열로 표현하고 있다면 자체 구현 bignum이므로 비대칭키를 의심한다.

## 단계별 절차
1. `nm ./chall | grep -iE "gmp|bn_|mpz|rsa"` 또는 `strings ./chall | grep -iE "gmp|openssl|rsa"`로 라이브러리 흔적을 확인한다.
2. 라이브러리 흔적이 없다면 코드에서 정수 변수의 비트 폭(레지스터 크기, 배열 크기)을 확인한다. 64비트 이하로 끝나면 대칭키, 그 이상이면 비대칭키 가능성이 높다.
3. 곱셈/나눗셈/모듈러 연산이 반복되는 루프가 있는지 찾고, 있다면 square-and-multiply 골격(지수 우측 시프트 + 조건부 곱셈 + 매 단계 제곱)과 일치하는지 대조한다.
4. 비대칭키(RSA)로 확정되면 공개키 값(`n`, `e`)을 정확히 추출한다.
5. `n`의 비트 크기를 확인해 소인수분해가 현실적인지 판단한다(작은 `n`은 `sympy.factorint()`나 `msieve`, `yafu` 같은 도구로 직접 분해 시도).
6. `e`가 작고 메시지가 짧다면 Low Exponent Attack을, 여러 암호문/공개키가 주어졌다면 Common Modulus/Broadcast Attack을 검토한다.

## 명령어/단축키
```bash
nm ./chall | grep -iE "gmp|bn_|mpz|rsa"
strings ./chall | grep -iE "gmp|openssl|rsa|modulus|exponent"
```
```python
# square-and-multiply 여부 확인용 재구현 (파이썬은 내장 pow()가 이미 이 알고리즘을 씀)
def modpow(base, exp, mod):
    result = 1
    base = base % mod
    while exp > 0:
        if exp & 1:
            result = (result * base) % mod
        exp >>= 1
        base = (base * base) % mod
    return result

print(modpow(5, 117, 19) == pow(5, 117, 19))  # True
```
```python
# n이 작을 때 소인수분해 시도
from sympy import factorint
n = 0x9F3A21B4C1D2E3F4  # 예시
print(factorint(n))
```

## 출력 해석
- `nm`/`strings`에서 `gmp`, `BN_`, `mpz_`, `RSA_` 같은 심볼이 나오면 비대칭키(대개 RSA) 확정이다 — 대수적 XOR 역산 시도를 즉시 중단하고 RSA 취약점 탐색으로 전환한다.
- `factorint(n)`이 몇 초 안에 두 개의 소인수로 분해되면 `n`이 안전하지 않게 작다는 뜻이며, `p`, `q`를 얻으면 오일러 파이 함수로 개인키 `d`를 직접 계산할 수 있다.
- square-and-multiply 루프가 확인되었지만 `n`이 커서(2048비트 이상) 소인수분해가 비현실적이면, `e`가 작은지·같은 메시지가 여러 공개키로 암호화됐는지 등 다른 구조적 약점을 찾아야 한다.

## 흔한 실수
- 큰 정수 상수를 보고도 "그냥 큰 XOR 키인가보다"라고 대칭키로 오판하는 것 — 상수 비트 폭이 64비트를 크게 넘고 모듈러 거듭제곱 루프가 있다면 비대칭키를 의심해야 한다.
- RSA라고 확정한 뒤에도 XOR 역산이나 known-plaintext(REV-0223) 같은 대칭키 기법을 계속 시도하며 시간을 낭비하는 것 — RSA는 구조적으로 완전히 다른 취약점(소인수분해, 작은 지수 등)을 찾아야 한다.
- `n`의 실제 비트 크기를 확인하지 않고 무작정 `factorint()`를 몇 시간 동안 돌리는 것 — 2048비트급 안전한 RSA 모듈러스는 현재 알려진 방법으로 현실적 시간 안에 소인수분해가 불가능하다. 먼저 비트 크기를 확인해 시도할 가치가 있는지 판단해야 한다.
- ECC(타원곡선 암호)도 비대칭키라는 걸 놓치고 "bignum이 없으니 대칭키"라고 오판하는 것 — ECC는 RSA보다 훨씬 작은 비트 폭(256비트 등)으로도 강력한 보안을 제공하므로, 점 덧셈/스칼라 곱셈 연산(타원곡선 특유의 좌표 연산)이 보이면 ECC도 함께 의심해야 한다.

## 막혔을 때 다음 체크
- 대칭키로 확정되었다면 → REV-0199 XOR 반복 변환 역산, REV-0223 Known plaintext와 Flag 형식으로 조건 줄이기
- 라이브러리 호출 없이 손으로 구현된 부분이 섞여 있다면 → REV-0915 라이브러리 호출 없이 손으로 구현된 암호를 알아채는 단서
- Z3로 RSA의 특정 조건(작은 차이의 p, q 등)을 자동으로 풀고 싶다면 → REV-0268 Z3 BitVec 기초, REV-0917 Z3로 풀기 전에 손으로 먼저 검증 로직 축소하기
- 이 알고리즘이 대칭/비대칭을 넘어서 애초에 역산 가능한 구조인지 다시 판단하고 싶다면 → REV-0221 역연산 가능한 알고리즘 판단법

## 미니 예제
어떤 바이너리에서 다음과 같은 함수와 상수를 발견했다고 하자.

```c
// n, e는 .rodata의 큰 정수 배열(각 256바이트, 즉 2048비트)에서 로드됨
bignum encrypt(bignum msg, bignum e, bignum n) {
    return modpow(msg, e, n);   // 위에서 본 square-and-multiply 골격
}
```

정수 크기가 256바이트(2048비트)이고 square-and-multiply 골격이 정확히 일치하므로 RSA로 확정할 수 있다. 다음으로 공개키 `e`를 확인해보니 `e=3`이었고, 평문 메시지 길이가 `n`보다 훨씬 짧다는 게 확인됐다고 하자.

```python
# Low Public Exponent Attack: c = m^3 mod n 이지만 m^3 < n이면 mod 연산이 사실상 무의미
from sympy import integer_nthroot

c = 0x1234...   # 암호문 (실제로는 훨씬 긴 정수)
m_cubed = c     # m^3 mod n == m^3 (모듈러 연산이 적용 안 된 경우)
m, exact = integer_nthroot(m_cubed, 3)
if exact:
    print("복원된 평문:", m)
```
이처럼 "RSA로 확정"하는 순간 다음 행동이 XOR 역산이 아니라 "e가 작은지, 세제곱근이 정확히 떨어지는지" 확인하는 쪽으로 완전히 바뀐다는 것이 이 판단의 실질적 가치다.

## 관련 글
- REV-0199 — XOR 반복 변환 역산
- REV-0223 — Known plaintext와 Flag 형식으로 조건 줄이기
- REV-0221 — 역연산 가능한 알고리즘 판단법
- REV-0268 — Z3 BitVec 기초
- REV-0915 — 라이브러리 호출 없이 손으로 구현된 암호를 알아채는 단서
- REV-0917 — Z3로 풀기 전에 손으로 먼저 검증 로직 축소하기

## 출처/검증
- RSA의 암호화/복호화 정의(`c=m^e mod n`, `m=c^d mod n`)와 square-and-multiply 모듈러 거듭제곱 알고리즘: RSA 원 논문(Rivest, Shamir, Adleman, 1978) 및 표준 암호학 교재(모듈러 거듭제곱 알고리즘) 기준.
- Low Public Exponent Attack, Common Modulus Attack, Fermat Factorization 등 RSA 구조적 취약점: 응용 암호학 표준 문헌(Boneh의 "Twenty Years of Attacks on the RSA Cryptosystem" 등에서 정리된 공개된 공격 기법) 기준 (2026-09-09 검증).
