---
id: REV-0886
title: "RSA 개념과 간단한 모듈러 거듭제곱 인식하기"
slug: "rev-0886-rsa-modular-exponentiation-recognition"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["RSA", "modular exponentiation", "모듈러 거듭제곱", "65537", "square and multiply", "mpz_powm", "BN_mod_exp", "공개키 암호"]
aliases: ["RSA 알고리즘", "모듈러 거듭제곱이 뭐임", "square and multiply 패턴", "n e d 상수", "RSA 암호화 코드"]
symptom_keywords: ["엄청 큰 16진수 상수가 두 개 있음", "65537이라는 상수가 보임", "루프 안에서 계속 제곱하고 곱함", "mpz_powm 함수를 호출함", "GMP 라이브러리를 링크함"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
코드에 수백 비트짜리 거대한 정수 상수 두세 개(모듈러스 `n`, 지수 `e`, 그리고 흔히 `65537`)가 하드코딩되어 있고, 루프 안에서 "제곱한 뒤 필요하면 곱하고, 매번 나머지를 취하는" 패턴이 보이면 RSA의 모듈러 거듭제곱(modular exponentiation) 연산을 의심해야 한다.

## 언제 검색해야 하나
- 디스어셈블리나 문자열 영역에 128비트를 훨씬 넘는(보통 1024/2048비트급) 16진수 상수가 여러 개 보일 때
- Import 목록에 `GMP`, `libgmp`, `mpz_powm`, `mpz_powm_sec`, OpenSSL의 `BN_mod_exp`, `RSA_public_encrypt`, `RSA_private_decrypt` 같은 함수가 있을 때
- 정수 하나를 반복적으로 제곱(`곱하기 자기 자신`)하면서 지수의 비트를 하나씩 검사해 결과에 곱해 넣는, 겉보기에 단순한데 반복 횟수가 수백 회에 달하는 루프를 만났을 때
- `65537`(0x10001) 같은 특정 상수가 지수 자리에 등장할 때 — RSA 공개 지수의 사실상 표준값이기 때문
- Python 문제 파일에 `pow(m, e, n)` 호출이 그대로 있거나, 문제 설명에 "공개키", "암호화", "n, e, c" 같은 용어가 등장할 때

## 핵심 개념

### RSA가 CTF에 나오는 이유
RSA는 실전에서 가장 널리 쓰이는 공개키 암호 알고리즘이다. 두 개의 큰 소수 `p`, `q`를 곱해 모듈러스 `n = p*q`를 만들고, 오일러 파이 함수 `φ(n) = (p-1)(q-1)`를 기준으로 공개 지수 `e`와 개인 지수 `d`를 `e*d ≡ 1 (mod φ(n))` 관계로 정한다. 암호화는 `c = m^e mod n`, 복호화는 `m = c^d mod n`이다. CTF에서는 이 수학 자체를 구현하라고 요구하기보다, **약한 파라미터(작은 소수, 공유 모듈러스, 작은 `e`, 재사용된 키 등)를 찾아내 개인키 없이 복호화하는 문제**로 자주 나온다. 그래서 리버서 입장에서 가장 먼저 할 일은 "이 코드가 RSA구나"를 알아채고, `n`, `e`, `c`(암호문) 세 값을 뽑아내는 것이다.

### 왜 65537인가
공개 지수 `e`는 이론상 `1 < e < φ(n)`이고 `gcd(e, φ(n)) = 1`이면 어떤 값이든 가능하지만, 실무에서는 `65537(0x10001)`을 압도적으로 많이 쓴다. 이진수로 `10000000000000001`, 즉 비트가 2개뿐인 페르마 수(`2^16 + 1`)라서 모듈러 거듭제곱 연산 시 "제곱-곱하기(square-and-multiply)" 루프의 곱하기 단계가 딱 한 번만 실행되어 암호화 속도가 매우 빠르면서도, 지수가 작은 데서 오는 공격(저지수 공격)에는 어느 정도 안전하기 때문이다. OpenSSL, GMP 기반 코드 모두 기본값으로 `65537`을 쓰므로, 이 숫자 하나만 봐도 RSA를 강하게 의심할 수 있다. 반대로 `e = 3`처럼 극단적으로 작은 지수가 보이면 저지수 공격(Håstad's broadcast attack 등)이 가능한 취약한 구현일 가능성이 크다.

### 모듈러 거듭제곱의 코드 패턴 — Square-and-Multiply
`m^e mod n`을 계산할 때 `e`가 수백 비트인 경우, `m`을 `e`번 곱하는 건 현실적으로 불가능하다(지수가 2048비트짜리 수라고 생각해보라). 그래서 실제 구현은 예외 없이 **이진 거듭제곱(binary exponentiation)**, 흔히 "square-and-multiply"라 불리는 알고리즘을 쓴다. 지수 `e`를 비트 단위로 훑으면서, 매 비트마다 결과를 제곱하고, 그 비트가 1이면 추가로 밑을 한 번 더 곱한다.

```c
// square-and-multiply 의사코드 (디컴파일에서 흔히 보이는 형태)
BigInt mod_pow(BigInt base, BigInt exp, BigInt mod) {
    BigInt result = 1;
    base = base % mod;
    while (exp > 0) {
        if (exp & 1) {                  // 지수의 최하위 비트가 1이면
            result = (result * base) % mod;   // "곱하기" 단계
        }
        exp = exp >> 1;                 // 다음 비트로
        base = (base * base) % mod;     // "제곱" 단계 — 항상 실행
    }
    return result;
}
```
이 함수는 리버싱 관점에서 다음과 같은 뚜렷한 형태로 나타난다.

1. 두 개의 "큰 수"(단순 `int`가 아니라 여러 워드로 이루어진 배열, 또는 GMP의 `mpz_t` 구조체) 사이의 곱셈과 나머지 연산이 반복된다.
2. 루프 종료 조건이 지수의 비트 길이(예: 2048비트 RSA면 최대 2048회)와 일치한다.
3. 루프 안에 `if` 분기가 있고, 그 분기가 지수 값의 최하위 비트(`exp & 1`)를 검사한다.
4. 매 반복마다 `base = base * base % mod` (제곱)가 무조건 실행되고, 조건부로 `result = result * base % mod` (곱하기)가 추가 실행된다.

### 라이브러리 호출로 나타나는 경우
직접 구현하는 대신 라이브러리를 쓰는 경우가 훨씬 흔하다.
- **GMP**: `mpz_powm(rop, base, exp, mod)` 또는 사이드채널에 안전한 `mpz_powm_sec`. Import 목록에 `libgmp.so`나 `mpz_*` 계열 심볼이 보이면 바로 이 함수를 찾는다.
- **OpenSSL**: 저수준 `BN_mod_exp(r, a, p, m, ctx)`, 고수준 `RSA_public_encrypt`/`RSA_private_decrypt`. 구조체 `RSA`에 `n`, `e`, `d`, `p`, `q` 필드가 있다.
- **Python 문제 스크립트**: 바이너리가 아니라 `.py` 파일 자체가 문제로 주어지는 경우 `pow(m, e, n)` 세 줄짜리 코드로 거의 항상 끝난다. 이 경우는 리버싱이랄 것도 없이 `n`, `e`, `c` 값만 뽑아 파이썬으로 재현하면 된다.

### `n`, `e`, `c` 찾아내는 법
디스어셈블리에서 거대한 상수 배열이나 문자열로 인코딩된 16진수/10진수를 찾는다. IDA/Ghidra에서 큰 전역 배열(수십~수백 바이트)을 만나면 Hex View로 바이트를 확인하고, 리틀엔디안임을 감안해 워드 순서를 뒤집어 하나의 큰 정수로 재조합한다. 파이썬에서는 이렇게 처리한다.

```python
# 바이너리에서 뽑은 리틀엔디안 바이트 배열을 하나의 정수로 조립
raw_bytes = bytes.fromhex("...")  # IDA Hex View에서 복사한 바이트
n = int.from_bytes(raw_bytes, byteorder="little")
```

## 화면/코드에서 보이는 징후
- 수백 자리(16진수 기준 수십~수백 바이트)에 달하는 거대한 상수 배열이 `.rodata`/`.data`에 있음
- `65537` 또는 `0x10001`이 지수 변수 초기값으로 등장
- `mpz_powm`, `mpz_init`, `mpz_mul`, `mpz_mod`, `BN_mod_exp`, `BN_new` 등 큰 정수 연산 라이브러리 함수 임포트
- 루프 하나가 수백~수천 회 반복되며 그 안에서 곱셈과 나머지 연산만 반복
- 조건 분기가 지수의 최하위 비트를 검사하는 형태(`exp & 1`, `test eax, 1`)로 나타남

## 가장 먼저 할 것
Import 목록에서 `mpz_`, `BN_`, `RSA_` 접두사부터 검색한다. 있으면 라이브러리 기반 RSA로 확정하고 해당 호출 직전 인자(모듈러스 포인터, 지수 포인터, 평문/암호문 포인터)를 추적한다. 없으면 자체 구현한 modpow 루프를 찾아야 하는데, 이때는 "제곱은 항상, 곱하기는 조건부"라는 특징적인 비대칭 구조를 기준으로 루프를 식별한다.

## 단계별 절차
1. `strings`/Import 창에서 GMP·OpenSSL·BigInteger 계열 흔적 확인
2. 라이브러리 호출이 있다면 해당 함수 호출 직전 인자(레지스터/스택)에서 `n`, `e`(또는 `d`), 평문/암호문 포인터를 각각 특정
3. 라이브러리 호출이 없다면 IDA Functions 창에서 "곱셈+나머지 연산이 반복되는 긴 루프"를 찾고, 그 루프의 반복 횟수(비트 길이)를 확인
4. 루프 내부에서 지수 비트를 검사하는 분기(`if (exp & 1)`)와 무조건 실행되는 제곱 단계를 구분해 square-and-multiply 여부를 확정
5. 상수 영역에서 `n`(모듈러스), `e`(지수, 흔히 `65537`), 그리고 암호문으로 쓰이는 값을 바이트 단위로 덤프
6. 파이썬으로 동일 연산(`pow(m, e, n)`)을 재현해 값이 일치하는지 검증(REV-0222 참고)
7. `n`이 인수분해 가능할 정도로 작거나(수백 비트 미만), `e`가 비정상적으로 작거나, 여러 암호문이 같은 `n`을 공유하는 등 약점이 있는지 확인해 실제 공격 방향(RSA CTF 툴킷, `RsaCtfTool` 등) 결정

## 명령어/단축키
```bash
# 라이브러리 흔적 확인
strings ./chall | grep -iE "gmp|openssl|bignum"
objdump -T ./chall | grep -iE "mpz_|BN_|RSA_"

# 파이썬으로 modpow 직접 검증
python3 -c "print(pow(0x41, 65537, 0xFFFF))"
```
IDA: 큰 배열 위에서 `A`(ASCII/데이터 타입 전환), `Alt+B`로 알려진 바이트 시퀀스 검색. Ghidra: Hex View에서 리틀엔디안 워드 순서 확인 후 `Big Integer` 타입으로 재해석.

## 출력 해석
- `mpz_powm` 호출 인자를 추적했는데 지수 자리 값이 `d`(개인키)로 보이면 그 함수는 복호화 경로, `e`(보통 65537 근처의 작은 값)로 보이면 암호화 경로다.
- square-and-multiply 루프의 반복 횟수가 정확히 지수의 비트 길이와 같다면 구현이 맞다는 신호이고, 반복 횟수가 고정된 상수(예: 항상 2048)라면 사이드채널 방지를 위해 지수 값과 무관하게 항상 최대 비트 수만큼 도는 상수시간(constant-time) 구현일 수 있다.
- `n`을 인수분해했는데 실패한다면 실제 키 크기가 예상보다 크다는 뜻이므로, 문제 설명이나 다른 힌트(여러 암호문 공유, 작은 `e`)를 다시 확인해야 한다.

## 흔한 실수
- 거대한 상수를 보고 바로 "AES 키인가?"라고 생각하는 것 — AES 키는 16/24/32바이트로 짧고 고정 크기이지만, RSA 모듈러스는 그보다 훨씬 크고(128바이트 이상) 매 문제마다 크기가 들쭉날쭉하다.
- 리틀엔디안 바이트 순서를 무시하고 그대로 정수로 읽어서 완전히 다른 값을 얻는 것.
- `e`와 `d`를 혼동해서 암호화 함수에 개인 지수를 넣거나, 반대로 복호화하려는데 공개 지수를 쓰는 것.
- `n`이 실제로는 인수분해 가능한 크기(예: 512비트 이하)인데 시도조차 안 해보고 다른 취약점만 찾으려는 것 — RSA CTF 문제의 상당수는 결국 `n`을 인수분해하는 문제로 귀결된다.

## 막혔을 때 다음 체크
- `d`를 계산하는 과정에서 확장 유클리드 호제법 코드가 나온다면 → REV-0887 모듈러 역원(Modular Inverse)이 코드에 나타나는 패턴
- 이 연산이 왜 키 없이는 역산 불가능한지 궁금하면 → REV-0221 역연산 가능한 알고리즘 판단법
- 디스어셈블리에서 뽑은 값을 파이썬으로 옮기는 일반 절차가 기억 안 나면 → REV-0222 검증 루틴을 Python으로 그대로 재현하기
- RSA 관련 상수(e=65537 등)를 표로 빠르게 확인하고 싶다면 → REV-0881 RSA 관련 흔한 상수(e=65537 등) 빠른 참조
- 모듈러스나 지수가 작아서 무차별 대입이 통할지 판단하려면 → REV-0219 Brute Force가 가능한 입력 공간 계산

## 미니 예제
Ghidra로 디컴파일한 어떤 바이너리에서 다음과 같은 함수를 발견했다고 하자.

```c
undefined8 verify(uint64_t *cipher, uint64_t *n, uint64_t *e) {
    uint64_t result[32] = {1, 0, 0, ...};   // 초기값 1
    uint64_t base[32];
    memcpy(base, cipher, sizeof(base));
    for (int bit = 0; bit < 2048; bit++) {
        if (get_bit(e, bit)) {              // 지수의 bit번째 비트가 1이면
            bignum_mulmod(result, result, base, n);   // 곱하기
        }
        bignum_mulmod(base, base, base, n);           // 제곱 (항상 실행)
    }
    return bignum_cmp(result, KNOWN_PLAINTEXT) == 0;
}
```
`bignum_mulmod`가 항상 제곱 단계에서 실행되고, 곱하기 단계는 `get_bit(e, bit)` 조건에서만 실행되는 것이 square-and-multiply의 전형적인 형태다. 여기서 `n`, `e`, `cipher`를 덤프해 파이썬으로 옮기면:

```python
n = int.from_bytes(dumped_n, "little")
e = int.from_bytes(dumped_e, "little")
c = int.from_bytes(dumped_cipher, "little")

m = pow(c, e, n)   # 이 함수가 검증용이면 e가 아니라 실제로는 d일 수도 있으니 주의
print(m.to_bytes((m.bit_length() + 7) // 8, "big"))
```
`e`가 아니라 개인 지수 `d`로 검증하는 구조라면(즉, 이 함수가 서버 측 복호화 검증이라면), `d`를 알아내려면 `n`을 인수분해해서 `p`, `q`를 구하고 `φ(n) = (p-1)(q-1)`, `d = modinv(e, φ(n))`을 계산해야 한다(REV-0887 참고).

### 실행 가능한 전체 스크립트 — 작은 소수로 RSA 키 생성부터 암복호화까지 손으로 검증

실제 RSA는 소수가 수백 비트라 손으로 계산할 수 없지만, 원리를 이해하려면 아주 작은 소수 두 개로 전체 과정을 직접 돌려보는 것이 가장 빠르다. 아래 스크립트는 교과서에서 자주 쓰는 작은 소수 `p=61`, `q=53`으로 키를 만들고, 평문을 암호화한 뒤 다시 복호화해서 원래 값이 나오는지 검증한다.

```python
# -*- coding: utf-8 -*-

# --- 1) 작은 소수 두 개를 고른다 (실제 RSA는 이 자리에 수백 비트 소수가 들어간다) ---
p = 61
q = 53
n = p * q                 # 모듈러스 n = p * q. 리버싱 중 바이너리에서 뽑아낸 그 거대한 상수가 바로 이 n이다.
phi = (p - 1) * (q - 1)    # 오일러 파이 함수 φ(n) = (p-1)(q-1)
print("n =", n, " phi(n) =", phi)   # 실행 결과: n = 3233  phi(n) = 3120

# --- 2) 공개 지수 e를 고른다 (실전에서는 65537을 쓰지만, phi=3120보다 작아야 하므로
#         이 작은 예제에서는 학습용으로 흔히 쓰는 17을 사용한다) ---
e = 17

# --- 3) 확장 유클리드 호제법으로 개인 지수 d = e의 phi(n)에 대한 모듈러 역원을 구한다 ---
def ext_gcd(a, b):
    old_r, r = a, b
    old_s, s = 1, 0
    while r != 0:
        quotient = old_r // r
        old_r, r = r, old_r - quotient * r
        old_s, s = s, old_s - quotient * s
    return old_r, old_s   # (gcd, x) : a*x + b*y = gcd 를 만족하는 x

def modinv(a, m):
    g, x = ext_gcd(a, m)
    assert g == 1, "e와 phi(n)이 서로소가 아니라 역원이 존재하지 않음"
    return x % m

d = modinv(e, phi)         # d = e^-1 mod phi(n)
print("개인 지수 d =", d)   # 실행 결과: d = 2753

# --- 4) 평문을 하나 정해서 암호화(c = m^e mod n)한다 ---
m = 65                      # 평문(숫자로 인코딩된 메시지, 여기서는 그냥 예시 정수)
c = pow(m, e, n)             # 파이썬 내장 pow(밑, 지수, 모듈러스)가 square-and-multiply를 대신 해준다
print("평문 m =", m, " -> 암호문 c =", c)   # 실행 결과: c = 2790

# --- 5) 개인 지수 d로 복호화(m' = c^d mod n)해서 원래 값이 나오는지 확인 ---
m_recovered = pow(c, d, n)
print("복호화 결과 m' =", m_recovered)      # 실행 결과: m' = 65
print("원본과 일치하는가?", m_recovered == m)  # 실행 결과: True

# --- 6) CTF에서 훨씬 흔한 상황: n을 몰래 인수분해해서 개인키 없이 복호화하기 ---
# n이 3233처럼 작으면(현실의 RSA는 1024비트 이상이라 이 방법이 안 통하지만,
# 문제로 나오는 "취약한 RSA"는 종종 이렇게 작은 n을 쓴다) 그냥 순차 시도로도 인수분해된다.
def factor_small_n(n):
    i = 2
    while i * i <= n:
        if n % i == 0:
            return i, n // i
        i += 1
    return None, None

found_p, found_q = factor_small_n(n)
print("n을 인수분해해서 찾은 p, q =", found_p, found_q)  # 실행 결과: 53 61

# 인수분해에 성공했으니 개인키 없이도 d를 직접 재계산할 수 있다
recovered_phi = (found_p - 1) * (found_q - 1)
recovered_d = modinv(e, recovered_phi)
print("인수분해로 복구한 d =", recovered_d, " (원래 d와 같은가?", recovered_d == d, ")")
```

이 스크립트를 그대로 실행하면 다음과 같은 결과가 나온다.

```text
n = 3233  phi(n) = 3120
개인 지수 d = 2753
평문 m = 65  -> 암호문 c = 2790
복호화 결과 m' = 65
원본과 일치하는가? True
n을 인수분해해서 찾은 p, q = 53 61
인수분해로 복구한 d = 2753  (원래 d와 같은가? True )
```

여기서 가장 중요한 부분은 6번 단계다 — 개인키 `d=2753`을 전혀 모르는 상태에서 시작했어도, 공개된 모듈러스 `n=3233`이 인수분해 가능할 만큼 작다면 `p`, `q`를 직접 찾아내 `d`를 처음부터 다시 계산할 수 있다. 실제 CTF의 "취약한 RSA" 문제 대부분이 바로 이 구조를 노린다 — `n`이 크면(1024비트 이상) `factor_small_n` 같은 단순 시도는 몇 조 년이 걸려 불가능하지만, 문제 출제자가 일부러 작거나 특수한 구조의 `n`을 준다면 이 6번 단계 하나로 문제가 끝난다.

## 관련 글
- REV-0887 — 모듈러 역원(Modular Inverse)이 코드에 나타나는 패턴
- REV-0221 — 역연산 가능한 알고리즘 판단법
- REV-0222 — 검증 루틴을 Python으로 그대로 재현하기
- REV-0219 — Brute Force가 가능한 입력 공간 계산
- REV-0881 — RSA 관련 흔한 상수(e=65537 등) 빠른 참조

## 출처/검증
- RSA 알고리즘 정의(`n = p*q`, `c = m^e mod n`, `m = c^d mod n`)와 공개 지수 `65537`이 페르마 수 `2^16+1`로 널리 쓰이는 이유: RFC 8017 (PKCS #1 v2.2, RSA Cryptography Specifications) 및 실무 관행 기준 (2026-09-09 검증).
- GMP `mpz_powm`/`mpz_powm_sec` 함수 시그니처: GNU GMP 공식 매뉴얼(Number Theoretic Functions 챕터) 기준 (2026-09-09 검증).
- OpenSSL `BN_mod_exp` 함수 시그니처: OpenSSL 공식 `bn` 모듈 문서(`man BN_mod_exp`) 기준 (2026-09-09 검증).
