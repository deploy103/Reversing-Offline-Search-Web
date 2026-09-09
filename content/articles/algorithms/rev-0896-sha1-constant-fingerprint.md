---
id: REV-0896
title: "SHA-1 흔적을 상수로 알아보는 법"
slug: "rev-0896-sha1-constant-fingerprint"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["SHA-1", "SHA1", "0x67452301", "0xEFCDAB89", "0x98BADCFE", "0x10325476", "0xC3D2E1F0", "5A827999", "6ED9EBA1", "8F1BBCDC", "CA62C1D6", "160비트 해시"]
aliases: ["sha1 상수", "sha1 초기값", "160비트 해시 알고리즘", "sha1 흔적 찾기"]
symptom_keywords: ["67452301이라는 상수가 보임", "efcdab89 상수가 보임", "20바이트 해시 결과가 나옴", "5개의 32비트 변수를 초기화함", "5A827999 상수가 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
바이너리 안에서 32비트 정수 5개가 `0x67452301`, `0xEFCDAB89`, `0x98BADCFE`, `0x10325476`, `0xC3D2E1F0` 순서로 초기화되고 최종 결과가 20바이트(160비트)로 나온다면 이는 SHA-1 해시 알고리즘이며, 초기값이 8개(SHA-256)가 아니라 5개라는 개수 자체가 SHA-1을 특정하는 핵심 지문이다.

## 언제 검색해야 하나
- 디컴파일 코드나 어셈블리에서 지역 변수 5개가 특정 32비트 상수로 초기화되는 함수를 발견했을 때
- 검증 로직이 20바이트(40자리 hex 문자열) 결과를 비교 대상으로 삼고 있을 때
- Import 목록에 `CryptCreateHash`와 함께 `CALG_SHA1`, 또는 OpenSSL의 `SHA1_Init`/`SHA1`, `EVP_sha1` 같은 함수/문자열이 보일 때
- 64바이트(512비트) 블록 단위로 반복 처리하면서 내부에 80회 도는 루프가 있는 해시 유사 함수를 만났을 때

## 핵심 개념

### SHA-1이 무엇이고 왜 CTF에 자주 나오는가
SHA-1(Secure Hash Algorithm 1)은 NIST가 1995년 FIPS 180 시리즈로 표준화한 암호학적 해시 함수로, 임의 길이의 메시지를 160비트(20바이트) 다이제스트로 압축한다. 오늘날 충돌(collision) 공격이 실용화되어 보안 용도로는 사실상 폐기되었지만, CTF에서는 여전히 "체크섬 검증", "레거시 포맷 파싱", "Git 오브젝트 해시 재현" 같은 문제에 자주 등장한다. 구조상 SHA-256(REV-0895)과 형제뻘이지만, 내부 상태 크기와 초기값 개수가 다르므로 코드만 보고도 구분할 수 있다.

### 5개의 32비트 초기 해시값 — 가장 강력한 지문
SHA-1은 내부 상태로 5개의 32비트 변수(A, B, C, D, E)를 쓰고, 처리를 시작하기 전에 다음 고정값으로 초기화한다(FIPS 180-4, RFC 3174 기준):
```
H0 = 0x67452301
H1 = 0xEFCDAB89
H2 = 0x98BADCFE
H3 = 0x10325476
H4 = 0xC3D2E1F0
```
이 다섯 값은 모든 표준 SHA-1 구현에서 동일하게 나타나며, 심지어 앞의 네 개(`0x67452301`, `0xEFCDAB89`, `0x98BADCFE`, `0x10325476`)는 MD4와 MD5(REV-0897)에서도 그대로 재사용된다. 따라서 **이 네 개만 보고는 MD5인지 SHA-1인지 구분할 수 없고, 다섯 번째 값 `0xC3D2E1F0`가 있는지 없는지가 결정적 구분점**이다. 초기값이 4개뿐이고 다섯 번째가 없으면 MD5, 다섯 개가 다 있으면 SHA-1, 여덟 개(`0x6A09E667` 등)면 SHA-256이다.

### 라운드 상수 4개 — 보조 지문
SHA-1은 80단계를 20단계씩 4개 라운드로 나누고, 각 라운드마다 다른 상수를 덧셈에 사용한다(FIPS 180-4 §4.2.1):
```
K0 = 0x5A827999   (0 ≤ t ≤ 19)
K1 = 0x6ED9EBA1   (20 ≤ t ≤ 39)
K2 = 0x8F1BBCDC   (40 ≤ t ≤ 59)
K3 = 0xCA62C1D6   (60 ≤ t ≤ 79)
```
이 값들은 각각 2, 3, 5, 10의 제곱근의 소수부에서 유도된 nothing-up-my-sleeve 상수다. 코드에 초기값 5개가 안 보이더라도(레지스터에 바로 로드되어 상수 풀에서 찾기 어려운 경우) 이 네 개의 라운드 상수가 있으면 SHA-1로 확정할 수 있다.

### 처리 단위와 출력 크기
SHA-1은 메시지를 512비트(64바이트) 블록 단위로 처리하며, 각 블록마다 16개의 32비트 워드를 80개로 확장(message schedule)한 뒤 80회 압축 루프를 돈다. 최종 출력은 5개의 32비트 상태(A~E)를 이어붙인 160비트(20바이트, hex로는 40자리)다. 이 "20바이트/40자리 hex" 출력 크기는 SHA-256의 32바이트/64자리, MD5의 16바이트/32자리와 구분되는 또 하나의 단서다.

| 알고리즘 | 초기값 개수 | 출력 크기 | 라운드 수 |
|---|---|---|---|
| MD5 | 4개 (32비트) | 16바이트 | 64 |
| SHA-1 | 5개 (32비트) | 20바이트 | 80 |
| SHA-256 | 8개 (32비트) | 32바이트 | 64 |

### 압축 함수와 비선형 함수
각 20단계 라운드는 서로 다른 비선형 함수 f를 쓴다:
```c
if (0 <= t && t <= 19)  f = (B & C) | ((~B) & D);        // Ch, MD5와 유사한 형태
if (20 <= t && t <= 39) f = B ^ C ^ D;                     // Parity
if (40 <= t && t <= 59) f = (B & C) | (B & D) | (C & D);   // Maj
if (60 <= t && t <= 79) f = B ^ C ^ D;                     // Parity (다시)
```
디컴파일 결과에서 `(b & c) | (~b & d)` 형태의 선택 함수와 `b ^ c ^ d` 형태의 패리티 함수가 번갈아 나오는 것도 SHA 계열 특유의 패턴이다. 또한 각 단계마다 A를 5비트 왼쪽 순환(`ROL 5`), 처리 후 B를 30비트 왼쪽 순환(`ROL 30`)시키는데, 이 "5비트/30비트 회전"이라는 특정 회전량도 SHA-1을 다른 해시와 구분하는 세부 지문이다.

### 문자열/API 지문
소프트웨어 구현 없이 라이브러리를 그대로 쓰는 경우도 많다.
- **Windows CryptoAPI**: `CryptCreateHash`에 `CALG_SHA1` 상수(`0x00008004`) 전달, 또는 CNG의 `BCryptOpenAlgorithmProvider`에 `L"SHA1"` 문자열 전달
- **OpenSSL**: `SHA1_Init`/`SHA1_Update`/`SHA1_Final` 저수준 API, 또는 `EVP_sha1()` 고수준 API
- **Python 대조 표준**: `hashlib.sha1()` — 바이너리에서 뽑은 값과 즉시 대조 가능

## 화면/코드에서 보이는 징후
- 함수 진입부에서 5개의 지역 변수/레지스터가 `0x67452301`, `0xEFCDAB89`, `0x98BADCFE`, `0x10325476`, `0xC3D2E1F0` 순서로 초기화됨
- `.rodata`/코드 안에 `5A827999`, `6ED9EBA1`, `8F1BBCDC`, `CA62C1D6` 네 상수가 순서대로 등장
- 64바이트 단위 블록 루프 안에 다시 80회 도는 내부 루프
- 최종 결과 버퍼 크기가 정확히 20바이트
- Import에 `CryptCreateHash`+`CALG_SHA1`, 또는 문자열 `"SHA1"`/`"sha1"`

## 가장 먼저 할 것
`0x67452301`을 IDA `Alt+B`(바이너리 검색) 또는 `objdump -s`로 먼저 찾는다. 찾았다면 바로 뒤에 `0xC3D2E1F0`가 있는지 확인해서 SHA-1(있음)인지 MD5(없음, REV-0897)인지 즉시 구분한다. 초기값을 못 찾았다면 라운드 상수 `5A827999`를 대신 찾는다.

## 단계별 절차
1. `strings ./binary | grep -i sha1` 및 Import 목록에서 `CryptCreateHash`, `SHA1_Init`, `EVP_sha1` 검색으로 라이브러리 호출 여부 먼저 확인
2. 없으면 IDA/Ghidra에서 `67452301`을 16진수 상수로 검색(IDA: `Alt+B` 바이너리 검색, 또는 상수 위 커서 놓고 `Ctrl+F`로 즉시값 검색)
3. 찾은 위치 근처에 `EFCDAB89`, `98BADCFE`, `10325476`, `C3D2E1F0`가 연속으로 나오는지 확인 — 다섯 개가 다 있으면 SHA-1, 네 개뿐이면 MD5
4. 함수 본체에서 64바이트 블록 처리 루프와 그 안의 80회 내부 루프 존재 확인(64회면 MD5, 64회지만 8워드 초기값이면 SHA-256이므로 반드시 초기값 개수와 함께 교차 확인)
5. 라운드 상수 `5A827999`/`6ED9EBA1`/`8F1BBCDC`/`CA62C1D6`이 20단계씩 구간을 나눠 등장하는지 재확인
6. Python `hashlib.sha1()`로 알고 있는 입력을 넣어 바이너리가 기대하는 출력값과 일치하는지 대조

## 명령어/단축키
```bash
strings ./binary | grep -iE "sha1|sha-1"
objdump -s -j .rodata ./binary | grep -A1 "6745 2301"
python3 -c "import hashlib; print(hashlib.sha1(b'abc').hexdigest())"
```
IDA: `Alt+B`(바이너리 검색)에 `01 23 45 67`(리틀엔디안 `0x67452301`) 입력. Ghidra: `Search → Memory` 에서 Hex `01234567` 검색.

## 출력 해석
- Python `hashlib.sha1(b"abc").hexdigest()` 결과는 `a9993e364706816aba3e25717850c26c9cd0d89` — 이 표준 테스트 벡터로 자신이 구현/추출한 로직이 맞는지 항상 먼저 검증한다.
- 초기값 5개는 찾았는데 최종 출력이 20바이트가 아니라 16바이트로 잘려 나온다면, 해시값 중 일부(예: 앞 16바이트)만 잘라 쓰는 커스텀 검증 로직일 수 있으니 비교 루틴의 길이 상수를 다시 확인한다.
- 라운드 상수 4개는 있는데 초기값이 다섯 개가 아니라면, SHA-1이 아니라 SHA-1 변형 또는 다른 해시에 라운드 상수만 재사용한 커스텀 알고리즘일 가능성이 있다.

## 흔한 실수
- 초기값 앞 네 개(`67452301`, `efcdab89`, `98badcfe`, `10325476`)만 보고 SHA-1이라 단정하는 것 — 이 네 개는 MD5(REV-0897)와 완전히 동일하므로, 다섯 번째 값 `C3D2E1F0`의 존재 여부를 반드시 확인해야 한다.
- SHA-1을 SHA-256과 혼동해 초기값이 8개일 것으로 착각하고 검색하는 것 — SHA-1은 정확히 5개, SHA-256은 8개다.
- 요즘도 SHA-1이 안전하다고 가정해 "충돌을 못 찾으니 원문이 유일하다"고 단정하는 것 — SHA-1은 이미 실용적 충돌 공격(SHAttered 등)이 공개된 알고리즘이라, CTF 맥락에 따라선 의도적으로 충돌을 이용하는 문제일 수도 있다.
- 라운드 상수 검색 시 엔디안을 안 맞춰서(리틀엔디안 바이너리인데 빅엔디안 바이트 순서로 검색) 상수를 못 찾고 "SHA-1이 아니다"라고 오판하는 것.

## 막혔을 때 다음 체크
- 앞 네 개 초기값만 있고 다섯 번째가 없다면 → REV-0897 MD5 흔적을 상수로 알아보는 법
- 초기값이 8개면 SHA-256이므로 → REV-0895 SHA-256 흔적을 상수로 알아보는 법 (예정)
- SHA-1 결과를 그대로 쓰지 않고 두 번 감싸서 쓰는 구조라면 → REV-0898 HMAC 패턴 알아보기(이중 해시 구조) (예정)
- 해시 자체가 역산 가능한지 헷갈리면 → [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md)
- 찾은 로직을 파이썬으로 그대로 재현하는 일반적 방법이 필요하면 → [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md)

## 미니 예제
IDA Hex View에서 다음과 같은 dword 배열 초기화를 발견했다:
```c
v1 = 0x67452301;
v2 = 0xEFCDAB89;
v3 = 0x98BADCFE;
v4 = 0x10325476;
v5 = 0xC3D2E1F0;
```
다섯 번째 값 `0xC3D2E1F0`가 존재하므로 이 함수는 MD5가 아니라 SHA-1이다. 이어서 함수 아래쪽에서 다음 상수를 발견했다면 라운드 상수까지 일치해 확정할 수 있다:
```c
if (t <= 19)      k = 0x5A827999;
else if (t <= 39) k = 0x6ED9EBA1;
else if (t <= 59) k = 0x8F1BBCDC;
else              k = 0xCA62C1D6;
```
Python으로 실제 값 검증:
```python
import hashlib
print(hashlib.sha1(b"abc").hexdigest())
# a9993e364706816aba3e25717850c26c9cd0d89
```
바이너리가 요구하는 목표 해시값과 이 결과 형식(40자리 hex, 20바이트)이 맞는지 대조하면 SHA-1 사용 여부를 최종 확정할 수 있다.

### 실행 가능한 전체 스크립트 — 출력 크기로 해시 종류 자동 판별 + 4자리 PIN 사전 대입

이번 스크립트는 두 단계로 구성된다. 먼저 "출력 바이트 수만 보고 MD5/SHA-1/SHA-256 중 무엇인지" 자동으로 구분하는 헬퍼를 만들고, 그다음 SHA-1로 해시된 4자리 PIN을 실제로 사전 대입해 찾아낸다.

```python
# -*- coding: utf-8 -*-
import hashlib   # SHA-1을 포함한 여러 해시 알고리즘을 제공하는 파이썬 표준 라이브러리

# --- 1) 표준 테스트 벡터로 내 계산 도구가 올바른지 먼저 검증 ---
test_vector = hashlib.sha1(b"abc").hexdigest()
print("SHA-1('abc') =", test_vector)
print("길이(자리수):", len(test_vector))   # 40자리(=20바이트)여야 정상

# --- 2) 다이제스트 크기(바이트 수)만으로 어떤 해시 알고리즘인지 추측하는 헬퍼 ---
DIGEST_SIZE_TABLE = {
    16: "MD5",       # 16바이트 = 128비트
    20: "SHA-1",      # 20바이트 = 160비트  <- 이번 글의 주제
    32: "SHA-256",    # 32바이트 = 256비트
    64: "SHA-512",    # 64바이트 = 512비트
}

def guess_hash_algorithm(digest_bytes: bytes) -> str:
    """다이제스트의 바이트 길이만 보고 어떤 알고리즘인지 1차 추측."""
    return DIGEST_SIZE_TABLE.get(len(digest_bytes), "알 수 없음 (표에 없는 크기)")

sample_digest = hashlib.sha1(b"abc").digest()   # bytes 형태(문자열이 아닌 원본 20바이트)
print("이 다이제스트는:", guess_hash_algorithm(sample_digest), " (바이트 수:", len(sample_digest), ")")

# --- 3) "바이너리에 SHA-1(PIN)의 해시값만 하드코딩되어 있다"는 상황을 재현 ---
secret_pin = "1337"                                    # 실전에서는 이 값을 모른다고 가정
expected_hash = hashlib.sha1(secret_pin.encode()).hexdigest()
print("목표 해시(바이너리에서 뽑았다고 가정):", expected_hash)

# --- 4) secret_pin을 모른다고 가정하고 0000~9999까지 전부 시도 ---
found_pin = None
for pin in range(10_000):                        # 4자리 숫자이므로 만 가지뿐 — 순식간에 끝난다
    candidate = str(pin).zfill(4)                 # 예: 7 -> "0007"
    if hashlib.sha1(candidate.encode()).hexdigest() == expected_hash:
        found_pin = candidate
        break

print("사전 대입으로 찾은 PIN:", found_pin)
print("원래 정답과 같은가?", found_pin == secret_pin)
```

이 스크립트를 그대로 실행하면 다음과 같은 결과가 나온다.

```text
SHA-1('abc') = a9993e364706816aba3e25717850c26c9cd0d89
길이(자리수): 40
이 다이제스트는: SHA-1  (바이트 수: 20 )
목표 해시(바이너리에서 뽑았다고 가정): 77ba9cd915c8e359d9733edcfe9c61e5aca92afb
사전 대입으로 찾은 PIN: 1337
원래 정답과 같은가? True
```

`guess_hash_algorithm()`은 초기값 상수를 하나도 보지 않고 오직 "결과가 몇 바이트인가"만으로 SHA-1임을 정확히 맞혔다 — 리버싱 중 코드를 자세히 읽기 전에, 비교 대상 버퍼의 크기만 먼저 확인해도 후보를 좁힐 수 있다는 걸 보여준다. 그다음 4자리 PIN 전체(10,000가지)를 SHA-1로 해시해가며 목표값과 대조한 결과, `1337`이라는 원래 정답을 정확히 찾아냈다. 여기서도 SHA-1을 거꾸로 계산한 게 아니라, 좁은 입력 공간을 전부 정방향으로 해시해서 우연히 일치하는 값을 찾은 것뿐이라는 점을 다시 강조해둔다.

## 관련 글
- REV-0897 — MD5 흔적을 상수로 알아보는 법
- REV-0895 — SHA-256 흔적을 상수로 알아보는 법
- REV-0898 — HMAC 패턴 알아보기(이중 해시 구조)
- [rev-0209-crc-fingerprints.md](./rev-0209-crc-fingerprints.md) — 암호학적 해시가 아닌 체크섬(CRC)과의 대비
- [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) — 해시 함수가 역산 불가능한 이유
- [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md) — 검증 로직을 파이썬으로 재현하는 법

## 출처/검증
- SHA-1 초기 해시값(H0~H4) 및 라운드 상수(K0~K3): NIST FIPS 180-4, "Secure Hash Standard (SHS)" 및 RFC 3174("US Secure Hash Algorithm 1 (SHA1)") 원문 기준 (2026-09-09 검증).
- SHA-1 표준 테스트 벡터(`"abc"` → `a9993e364706816aba3e25717850c26c9cd0d89`): Python 공식 `hashlib` 모듈 및 FIPS 180-4 예제값 기준 (2026-09-09 확인).
- MD5와 SHA-1이 초기값 앞 네 개를 공유한다는 사실: FIPS 180-4와 RFC 1321(MD5)의 초기값 정의 비교를 통해 확인 (2026-09-09).
