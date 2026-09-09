---
id: REV-0898
title: "HMAC 패턴 알아보기(이중 해시 구조)"
slug: "rev-0898-hmac-double-hash-pattern"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["HMAC", "0x36", "0x5c", "ipad", "opad", "이중 해시", "RFC 2104", "HMAC-SHA1", "HMAC-SHA256", "HMAC-MD5"]
aliases: ["hmac 패턴", "이중 해시 구조", "ipad opad 상수", "키 기반 해시 검증"]
symptom_keywords: ["같은 해시 함수를 두 번 호출함", "0x36 상수로 XOR함", "0x5c 상수로 XOR함", "블록 길이만큼 0으로 패딩된 키가 보임", "해시 결과를 다시 해시에 넣음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
같은 해시 함수(MD5/SHA-1/SHA-256 등)를 두 번 호출하되, 첫 번째 호출 전에는 키를 `0x36`(ipad)으로, 두 번째 호출 전에는 같은 키를 `0x5c`(opad)로 XOR한 블록을 붙이는 구조가 보이면 이는 HMAC(Hash-based Message Authentication Code)이며, "해시 함수 자체"가 아니라 "해시 함수를 감싸는 키 인증 껍데기"라는 점이 중요하다.

## 언제 검색해야 하나
- 디컴파일 코드에서 SHA-1/SHA-256/MD5(REV-0896, REV-0897, REV-0895) 같은 이미 식별된 해시 함수가 **정확히 두 번** 호출되고, 두 번째 호출의 입력이 첫 번째 호출의 출력을 포함할 때
- 코드 어딘가에 `0x36`이 64번(또는 128번, 블록 크기만큼) 반복되거나, 키 버퍼에 `0x36`/`0x5C`를 XOR하는 루프가 있을 때
- Import 목록에 `HMAC`, `CryptHashData`+`HMAC_INFO`, OpenSSL의 `HMAC()`/`HMAC_Init_ex()`, 또는 Python 코드/문자열에 `hmac.new(...)`가 보일 때
- 시크릿 키(비밀 값)와 메시지가 둘 다 입력으로 들어가는데 단순 `H(key || message)` 형태가 아니라 뭔가 더 복잡한 전처리가 있는 것 같을 때

## 핵심 개념

### HMAC이 해시와 다른 점
SHA-1, SHA-256, MD5 같은 해시 함수는 "메시지 하나"를 입력받아 고정 크기 출력을 만든다. 반면 HMAC은 **키(key)와 메시지(message) 두 개**를 입력받아, 그 키를 아는 사람만 만들 수 있는 인증 코드(MAC)를 생성하는 **구성 방식(construction)**이다. HMAC 자체는 새로운 해시 알고리즘이 아니라, 기존 해시 함수(H)를 감싸는 표준화된 절차이며 RFC 2104로 정의되어 있다. 그래서 "HMAC-SHA256"처럼 내부에 어떤 해시를 쓰는지 항상 이름에 붙는다.

### 왜 단순히 H(key||message)로 안 하는가
`H(key || message)`처럼 키와 메시지를 단순히 이어붙여 한 번만 해싱하면, MD5/SHA-1/SHA-256 같은 Merkle-Damgård 구조의 해시 함수에서 **길이 확장 공격(length extension attack)**이 가능해진다. 즉 원래 키를 몰라도 `H(key||message)`의 결과값만 알면 공격자가 `H(key||message||추가데이터)`를 계산할 수 있는 취약점이 생긴다. HMAC은 이 문제를 안쪽/바깥쪽 두 번의 해싱과 서로 다른 패딩 상수로 원천 차단한다.

### 핵심 구조 — 이중 해시와 ipad/opad
RFC 2104가 정의하는 HMAC의 계산 공식은 다음과 같다:
```
HMAC(K, m) = H( (K' XOR opad) || H( (K' XOR ipad) || m ) )
```
여기서 `K'`는 키를 해시 함수의 블록 크기(B, 대부분의 해시에서 64바이트)만큼 0으로 채우거나(짧으면 패딩), 블록 크기보다 길면 먼저 한 번 해시해서 줄인 값이다. 그리고:
```
ipad = 0x36을 B바이트만큼 반복
opad = 0x5C를 B바이트만큼 반복
```
즉 **내부 해시(inner hash)**는 `H((K' XOR 0x36...0x36) || message)`를 계산하고, **외부 해시(outer hash)**는 그 결과를 다시 `H((K' XOR 0x5C...0x5C) || innerHash결과)`로 감싼다. 코드에서 이 구조는 "같은 해시 함수 호출이 두 번, 그 사이에 `0x36`과 `0x5C`로 키를 XOR하는 처리"로 나타난다.

`0x36`과 `0x5C`는 RFC 2104가 정의한 고정 상수이며, 두 값을 XOR하면 `0x6A`가 나오는 등 비트 패턴이 서로 크게 다르도록(좋은 비트 차이 특성) 선택된 nothing-up-my-sleeve 값이다. 이 두 상수가 정확히 이 값으로 코드에 등장하는 것이 HMAC을 식별하는 가장 확실한 방법이다.

### 블록 크기(B)와 내부 해시 알고리즘의 관계
| 내부 해시 | 블록 크기 B | 출력 크기 L |
|---|---|---|
| MD5 | 64바이트 | 16바이트 |
| SHA-1 | 64바이트 | 20바이트 |
| SHA-256 | 64바이트 | 32바이트 |
| SHA-512 | 128바이트 | 64바이트 |

`ipad`/`opad` 반복 길이가 64바이트인지 128바이트인지 보면 내부 해시가 SHA-512 계열인지(128바이트) 나머지(64바이트)인지 힌트를 얻을 수 있다. 키가 B바이트보다 길면 먼저 `H(key)`로 한 번 줄이고, 짧으면 나머지를 0x00으로 채운다는 점도 코드에서 확인할 포인트다.

### API/문자열 지문
- **OpenSSL**: `HMAC()` 원샷 함수, 또는 `HMAC_Init_ex`/`HMAC_Update`/`HMAC_Final` 저수준 API
- **Windows CNG**: `BCryptOpenAlgorithmProvider`에 `BCRYPT_ALG_HANDLE_HMAC_FLAG` 플래그와 함께 `L"SHA256"` 등 전달
- **Python**: `hmac.new(key, msg, hashlib.sha256).hexdigest()` — 재현 및 대조에 가장 빠른 방법
- **JWT(JSON Web Token)**: `alg: "HS256"` 헤더가 보이면 내부적으로 HMAC-SHA256을 쓴다는 뜻이므로, 토큰 위변조 문제에서 이 패턴이 자주 등장

## 화면/코드에서 보이는 징후
- 동일한 해시 함수(SHA-1/SHA-256/MD5)가 코드 안에서 정확히 두 번 호출됨
- 키 버퍼에 `xor byte ptr [rax], 36h` 또는 `xor byte ptr [rax], 5Ch`가 64회(또는 128회) 반복되는 루프
- 첫 번째 해시 호출의 출력(16/20/32바이트)이 두 번째 해시 호출의 입력 뒷부분으로 그대로 들어감
- Import에 `HMAC`, `HMAC_Init_ex`, 문자열 `"HS256"`/`"HS384"`/`"HS512"`(JWT 헤더)
- 키 길이가 블록 크기(64/128바이트)보다 짧으면 나머지가 0x00으로 채워지는 패턴

## 가장 먼저 할 것
먼저 이미 알고 있는 해시 함수(REV-0895~0897)의 호출 위치를 코드에서 두 곳 찾는다. 그 사이에서 `0x36`과 `0x5C`로 키를 XOR하는 루프를 찾으면 HMAC으로 확정. Import에 `HMAC`이 있으면 이 과정 없이 바로 확정.

## 단계별 절차
1. Import 목록과 문자열에서 `HMAC`, `HS256`, `HS384` 등을 먼저 검색
2. 없으면 코드에서 같은 해시 함수가 두 번 호출되는 지점을 찾음(REV-0896/0897에서 배운 초기값 상수로 각 호출을 식별)
3. 두 호출 사이 또는 직전에 `0x36`, `0x5C` 상수로 XOR하는 루프가 있는지 확인 — IDA `Alt+B`로 `36h`, `5Ch` 즉시값 검색
4. 첫 번째(내부) 해시의 출력이 두 번째(외부) 해시 입력에 그대로 이어붙는지 데이터 흐름 추적
5. 키 길이와 블록 크기(대부분 64바이트) 비교 로직 확인 — 길면 먼저 축약 해시, 짧으면 0 패딩
6. Python `hmac` 모듈로 알고 있는 키/메시지 조합을 넣어 바이너리의 목표값과 대조

## 명령어/단축키
```bash
strings ./binary | grep -iE "hmac|hs256|hs384|hs512"
objdump -d ./binary | grep -E "36h|5ch|0x36|0x5c"
python3 -c "import hmac, hashlib; print(hmac.new(b'key', b'msg', hashlib.sha256).hexdigest())"
```
IDA: `Alt+B`(바이너리 검색)에 `36` 반복 패턴 검색, 또는 즉시값 `36h`/`5Ch` 위에서 `Ctrl+X`(Xref)로 어디서 쓰이는지 추적.

## 출력 해석
- Python `hmac.new(b"key", b"The quick brown fox jumps over the lazy dog", hashlib.sha256).hexdigest()`는 `f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd`가 나온다 — 알려진 테스트 벡터로 재현 로직을 검증할 수 있다.
- 내부 해시 결과(20바이트 또는 32바이트)가 외부 해시 입력 뒷부분에 정확히 이어붙는지 바이트 단위로 확인해야 한다 — 순서나 길이가 하나라도 틀리면 완전히 다른 MAC이 나온다.
- 키가 블록 크기보다 긴 경우 축약 해시를 빠뜨리면 결과가 절대 일치하지 않으니, 키 길이 조건 분기를 놓치지 않았는지 재확인한다.

## 흔한 실수
- HMAC을 "해시를 두 번 하는 것"으로만 이해하고, `H(H(key||message))`처럼 단순 이중 해시로 잘못 재현하는 것 — 반드시 `ipad`/`opad`로 키를 다르게 XOR한 뒤 각각 해싱해야 한다.
- HMAC 내부에 어떤 해시가 쓰였는지 확인 안 하고 무조건 SHA-256으로 가정하는 것 — REV-0895~0897의 상수 지문으로 내부 해시 종류를 먼저 정확히 식별해야 한다.
- JWT의 `alg: "none"` 취약점과 혼동해서, HMAC 서명 검증 자체를 우회할 수 있다고 착각하는 것 — HMAC 검증 로직 자체는 키를 모르면 위조가 불가능하며, 문제의 취약점은 대개 검증 코드의 구현 실수(타이밍 공격, alg 파라미터 조작 허용 등)에 있다.
- 키 길이가 블록 크기(64바이트)보다 긴 경우를 놓치고 그대로 0 패딩만 적용해 결과가 안 맞는 것.

## 막혔을 때 다음 체크
- 내부 해시가 무엇인지 모르겠다면 → REV-0896 SHA-1 흔적을 상수로 알아보는 법, REV-0897 MD5 흔적을 상수로 알아보는 법, REV-0895 SHA-256 흔적을 상수로 알아보는 법 (예정)
- JWT 토큰 구조 자체가 낯설다면 서명 부분이 바로 이 HMAC 패턴이라는 점을 기억하고 헤더의 `alg` 필드부터 확인
- 검증 로직을 파이썬으로 그대로 재현하려면 → [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md)
- 이 구조가 역산 가능한지 헷갈리면 → [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) (HMAC은 키를 모르면 역산도 위조도 불가능)

## 미니 예제
디컴파일 코드에서 다음과 같은 흐름을 발견했다:
```c
memset(k_ipad, 0x36, 64);
memset(k_opad, 0x5C, 64);
for (i = 0; i < key_len; i++) {
    k_ipad[i] ^= key[i];
    k_opad[i] ^= key[i];
}
sha256(inner_buf, k_ipad, 64, message, msg_len);   // 내부 해시
sha256(outer_buf, k_opad, 64, inner_buf, 32);      // 외부 해시, 내부 결과(32바이트) 재사용
```
`0x36`/`0x5C` 상수로 키를 XOR한 뒤 SHA-256을 두 번 호출하고, 첫 호출 결과(32바이트)를 두 번째 호출 입력에 붙이는 구조이므로 이는 HMAC-SHA256이다. Python으로 검증:
```python
import hmac, hashlib
key = b"key"
msg = b"message"
print(hmac.new(key, msg, hashlib.sha256).hexdigest())
```
이 값이 바이너리가 요구하는 목표값과 일치하면 HMAC-SHA256, 키, 메시지 형식까지 모두 확정된 것이다.

## 관련 글
- REV-0896 — SHA-1 흔적을 상수로 알아보는 법
- REV-0897 — MD5 흔적을 상수로 알아보는 법
- REV-0895 — SHA-256 흔적을 상수로 알아보는 법 (예정)
- [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) — 키 기반 인증 코드가 역산 불가능한 이유
- [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md) — 검증 로직을 파이썬으로 재현하는 법

## 출처/검증
- HMAC 구성 공식과 ipad(`0x36`)/opad(`0x5C`) 상수: IETF RFC 2104, "HMAC: Keyed-Hashing for Message Authentication" 원문 기준 (2026-09-09 검증).
- HMAC-SHA256 표준 테스트 벡터: Python 공식 `hmac`/`hashlib` 모듈 실행 결과 기준 (2026-09-09 확인).
- 길이 확장 공격과 HMAC의 방어 메커니즘: RFC 2104 명세 및 일반적으로 알려진 Merkle-Damgård 구조의 취약점 설명 기준 (2026-09-09).
