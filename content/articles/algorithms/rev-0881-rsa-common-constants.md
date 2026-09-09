---
id: REV-0881
title: "RSA 관련 흔한 상수(e=65537 등) 빠른 참조"
slug: "rev-0881-rsa-common-constants"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["RSA", "65537", "0x10001", "public exponent", "e=3", "F4", "modpow", "RSA_public_encrypt", "BCryptEncrypt RSA"]
aliases: ["rsa 상수", "rsa e값", "65537이 뭐임", "0x10001이 뭐임", "rsa 공개지수"]
symptom_keywords: ["65537이라는 숫자가 보임", "0x10001이 보임", "modpow 함수가 있음", "n e d 변수가 보임", "RSA 함수가 임포트됨"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
코드나 데이터에서 `65537`(hex `0x10001`)이 보이면 이는 거의 항상 **RSA의 공개 지수(public exponent) e**이며, 이 값과 함께 `modpow`/거듭제곱-모듈러 연산, 큰 정수(n, 보통 256바이트 이상) 상수가 나타나면 RSA 암호화/서명 로직으로 확정할 수 있다.

## 언제 검색해야 하나
- 상수 `65537` 또는 `0x10001`이 변수 초기화나 함수 인자로 등장할 때
- `n`, `e`, `d`, `p`, `q`처럼 이름 붙은(또는 그렇게 추정되는) 매우 큰 정수 변수들이 있을 때
- Import 목록에 `RSA_public_encrypt`, `RSA_private_decrypt`, `BCryptEncrypt`(BCRYPT_RSA_ALGORITHM), `mbedtls_rsa_*`, `CryptEncrypt`(PROV_RSA_FULL) 같은 함수가 있을 때
- 큰 정수(수백 비트) 거듭제곱 후 모듈러 연산(`modpow`, `powmod`, 몽고메리 곱셈 루프)을 반복하는 코드를 만났을 때

## 핵심 개념
RSA는 공개키(n, e)와 개인키(n, d)로 구성되며, 공개 지수 `e`는 실무에서 놀라울 정도로 몇 가지 값으로 고정되어 나타난다.

**흔히 보이는 공개 지수 e 값**
| 값 (10진) | 값 (hex) | 별칭 | 비고 |
|---|---|---|---|
| `65537` | `0x10001` | F4 (페르마 수 2^16+1) | 사실상 업계 표준. TLS 인증서의 99% 이상이 이 값을 사용 |
| `3` | `0x3` | F0 (페르마 수 2^1+1) | 매우 오래된 구현/저사양 임베디드에서 간혹 사용, Bleichenbacher류 서명 위조 취약점과 자주 엮임 |
| `17` | `0x11` | F2 | 드물게 사용 |
| `257`, `1` 등 작은 값 | - | - | CTF에서 의도적으로 매우 작은 e를 써서 "Low public exponent 공격"을 유도하는 문제 설정 |

`65537`이 선호되는 이유는 **이진수로 `10000000000000001`(1비트가 딱 2개)**이라서, 거듭제곱-제곱(square-and-multiply) 알고리즘으로 암호화할 때 곱셈 연산이 최소화되기 때문이다(속도상의 이유이지 보안과는 무관).

**RSA 핵심 수식**
```
암호화: c = m^e mod n
복호화: m = c^d mod n
n = p * q  (두 개의 큰 소수의 곱)
d = e^-1 mod φ(n)   (φ(n) = (p-1)(q-1))
```

**CTF/리버싱에서 자주 나오는 취약 상황들 (상수 확인 후 다음 단계로 이어지는 신호)**
- **e가 매우 작고(3 등) 메시지가 짧으면** — 패딩 없이 `c = m^3`이면 세제곱근만 계산해도 복원 가능(Low exponent attack).
- **n이 소인수분해 가능할 만큼 작으면(수백 비트 이하)** — `factordb`나 Pollard's rho 등으로 `p`, `q`를 직접 구해 `d`를 역산.
- **여러 공개키가 n을 공유하면(Common modulus)** — 서로 다른 e로 같은 메시지를 암호화한 두 암호문이 있으면 개인키 없이 평문 복원 가능.
- **p와 q가 너무 가까우면(Fermat factorization)** — `n`이 두 인접한 제곱수의 차로 빠르게 인수분해됨.

## 화면/코드에서 보이는 징후
```c
BIGNUM *e = BN_new();
BN_set_word(e, 65537);           // 공개 지수 초기화
RSA_generate_key_ex(rsa, 2048, e, NULL);
```
```asm
mov     dword ptr [e], 10001h     ; 0x10001 = 65537
```
디스어셈블리에서 큰 정수(256/384/512바이트) 배열 여러 개가 함께 초기화되고, 그중 하나의 값이 `65537`이면 공개키 구조체(n, e)가 초기화되는 지점이다.

## 가장 먼저 할 것
`65537`(`0x10001`) 상수를 찾으면, 그 근처에서 훨씬 더 큰 정수(모듈러스 `n`)를 함께 찾는다. `n`의 비트 길이(256바이트=2048비트, 128바이트=1024비트 등)를 확인하면 이후 소인수분해 시도 여부를 판단할 근거가 된다 — 1024비트 이하의 작은 키는 CTF에서 온라인 도구나 Python `sympy.factorint`로 직접 깨질 수 있다.

## 단계별 절차
**1) e 값 확인** — `65537`인지 `3`인지, 혹은 훨씬 작은 값인지 확인.

**2) n, c(암호문) 추출** — 바이너리나 통신 데이터에서 모듈러스와 암호문 전체 바이트를 정확히 덤프.

**3) n의 크기로 공격 가능성 판단**
```python
n = 0x00c1...  # 바이너리에서 추출
print(n.bit_length())   # 2048이면 사실상 소인수분해 불가능, 512 이하면 가능성 있음
```

**4) 작은 n이면 소인수분해 시도**
```python
from sympy import factorint
factors = factorint(n)   # 작은 n에서만 현실적인 시간 안에 끝남
```

**5) p, q를 구했으면 개인키 복원 후 복호화**
```python
from sympy import mod_inverse

p, q = factors_found
phi = (p - 1) * (q - 1)
d = mod_inverse(e, phi)
m = pow(c, d, n)
print(m.to_bytes((m.bit_length() + 7) // 8, "big"))
```

**6) e가 매우 작고 패딩이 없으면 세제곱근 시도**
```python
import gmpy2
m, exact = gmpy2.iroot(c, 3)   # e=3, 패딩 없는 짧은 메시지에 한해 성립
```

## 명령어/단축키
- IDA/Ghidra: `Alt+T`(텍스트 검색)로 `65537` 또는 `10001h` 검색
- Python: `sympy.factorint(n)`, `sympy.mod_inverse(e, phi)`, `pow(c, d, n)`, `gmpy2.iroot(c, e)`
- 온라인 참고 도구: `factordb.com`(작은 n을 이미 누군가 인수분해해뒀는지 확인, 인터넷이 되는 환경에서만)

## 출력 해석
- `factorint`가 몇 초~몇 분 안에 끝나면 n이 충분히 작다는 뜻이므로 계속 진행.
- 오래 걸리거나 끝나지 않으면 n이 실전 크기(2048비트 이상)이므로 소인수분해 경로를 포기하고 다른 취약점(common modulus, 낮은 e, 약한 난수로 생성된 p/q 등)을 찾아야 한다.
- 복호화 결과 `m`이 사람이 읽을 수 있는 바이트(ASCII 플래그 등)로 나오면 성공, 아니면 패딩(PKCS#1 v1.5의 `00 02 ... 00` 헤더)을 제거하지 않았을 가능성을 확인.

## 흔한 실수
- `e=65537`이 무조건 안전하다고 착각하고 다른 취약점(작은 n, common modulus, 약한 소수 생성)을 아예 검토하지 않는 것 — e값 자체는 안전해도 다른 부분이 취약할 수 있다.
- n의 비트 길이를 확인하지 않고 무작정 `factorint`를 실행해서 무한정 기다리는 것 — 먼저 `n.bit_length()`로 현실적인 시간 안에 끝날지 가늠해야 한다.
- 패딩(PKCS#1 v1.5/OAEP)을 무시하고 `pow(c, d, n)` 결과를 그대로 평문이라고 착각하는 것 — 패딩 스킴에 따라 앞의 여러 바이트를 제거해야 실제 메시지가 나온다.
- Low exponent attack을 시도할 때 메시지에 패딩이 있는데도 세제곱근 공식을 그대로 적용해서 실패하는 것 — 패딩이 있으면 정수 세제곱근만으로는 못 풀고 Coppersmith류의 별도 기법이 필요하다.

## 막혔을 때 다음 체크
- n을 소인수분해할 수 없을 만큼 크다면 → REV-0219 — Brute Force가 가능한 입력 공간 계산(RSA 키공간이 왜 브루트포스 불가능한 규모인지 확인).
- AES 등 대칭키와 RSA가 함께 쓰이는 하이브리드 암호 구조라면 → REV-0211 — AES 테이블 또는 AES API 흔적 찾기.
- 이 변환이 역산 가능한지(개인키 없이도) 헷갈리면 → REV-0221 — 역연산 가능한 알고리즘 판단법.

## 미니 예제
바이너리에서 다음 세 값을 추출했다고 하자(설명을 위해 매우 작은 예시 소수 사용):
```python
p, q = 61, 53
n = p * q                  # 3233
e = 17
phi = (p - 1) * (q - 1)    # 3120
d = pow(e, -1, phi)        # 2753, 개인키 지수

m = 65
c = pow(m, e, n)           # 2790, 암호문
print(c)                   # 2790
print(pow(c, d, n))        # 65 (원문 정수로 되돌아옴)
```
실제 CTF 문제에서는 `p`, `q`를 직접 알 수 없으므로, `n`을 인수분해하는 단계가 핵심 난이도가 된다. `e=65537`이면서 `n`이 2048비트라면 이 예제처럼 손으로 풀 수 없고, 위 4)번 절차의 `factorint`가 사실상 끝나지 않는다는 걸 확인하는 것 자체가 "이 문제는 다른 취약점을 찾아야 한다"는 중요한 판단 근거가 된다.

## 관련 글
- REV-0219 — Brute Force가 가능한 입력 공간 계산
- REV-0211 — AES 테이블 또는 AES API 흔적 찾기
- REV-0221 — 역연산 가능한 알고리즘 판단법
- REV-0885 — 알고리즘 유형별 판별 체크리스트

## 출처/검증
- RSA 공개 지수 관례(e=65537이 TLS 인증서의 99.5% 이상에서 사용됨, F0=3/F4=65537 페르마 수 명칭): UCSD TLS 인증서 조사 자료 및 Java Cryptography API의 `RSAKeyGenParameterSpec.F0`/`F4` 상수 정의 기준 (2026-09-09 검증).
- RSA 기본 수식(n=p*q, φ(n), 암복호화 공식): RSA 원논문(Rivest, Shamir, Adleman, 1978) 및 PKCS#1 표준 명세 기준.
- Low exponent attack, Common modulus attack, Fermat factorization: 공개된 응용암호학 교재(RSA 공격 기법) 및 CTF 리버싱/크립토 writeup에서 반복적으로 관찰되는 패턴 기준.
