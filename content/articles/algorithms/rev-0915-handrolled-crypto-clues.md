---
id: REV-0915
title: "라이브러리 호출 없이 손으로 구현된 암호를 알아채는 단서"
slug: "rev-0915-handrolled-crypto-clues"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["handrolled crypto", "손으로 구현한 암호", "custom crypto 식별", "S-box 상수 매칭", "표준 암호 상수", "라운드 함수", "자체 구현 AES"]
aliases: ["직접 구현된 암호 알아보기", "라이브러리 없이 만든 crypto", "표준 암호 상수로 알고리즘 식별", "custom cipher 알아채는 법"]
symptom_keywords: ["OpenSSL이나 CryptoAPI import가 안보임", "그런데 암호처럼 보이는 라운드 구조가 있음", "S-box같은 256개짜리 테이블이 있음", "라운드 상수가 반복됨"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
CTF 바이너리가 `CryptAcquireContext`, `EVP_EncryptInit`, `AES_encrypt` 같은 암호 라이브러리 API를 전혀 import하지 않는데도 암호처럼 동작한다면, 이는 개발자가 표준 암호 알고리즘을 직접 재구현했거나(hand-rolled 표준 암호) 완전히 새로운 커스텀 암호를 설계한 것이며, import 목록이 비어 있다는 사실 자체가 "라이브러리 문서를 봐도 소용없고 코드 자체에서 알고리즘을 식별해야 한다"는 신호다.

## 언제 검색해야 하나
- `nm`/`objdump`/Import 창을 확인했는데 `openssl`, `bcrypt`, `crypt32`, `libgcrypt` 같은 암호 라이브러리 흔적이 전혀 없는데, 바이너리 동작은 명백히 "암호화/복호화"처럼 보일 때
- 코드에 라운드(round)를 도는 루프가 있고, 매 라운드마다 비슷한 연산(치환+순열+키 XOR)이 반복될 때
- 256엔트리 짜리 정체불명의 상수 테이블이 있는데 이게 표준 AES S-box인지 커스텀 S-box인지 구분이 안 될 때
- "이 문제는 자작 암호(custom cipher)를 쓴다"는 문제 설명이 있거나, 표준 암호라고 하기엔 어딘가 이상하게 단순하거나 변형된 구조가 보일 때

## 핵심 개념

### 왜 CTF에서 암호를 직접 구현하는가
CTF 문제 출제자는 두 가지 이유로 암호 라이브러리 호출 대신 직접 구현을 택한다.

1. **표준 암호를 그대로 구현**: AES, DES, RC4, TEA 같은 잘 알려진 알고리즘을 교육 목적 또는 난이도 조절을 위해 라이브러리 없이 순수 C/어셈블리로 재구현. 이 경우 알고리즘 자체는 이미 완전히 공개되어 있으므로, "이게 무슨 알고리즘인지"만 식별하면 나머지는 이미 알려진 지식으로 풀 수 있다.
2. **완전히 새로운 커스텀 암호 설계**: 표준 알고리즘을 변형하거나(예: AES인데 S-box를 바꿈, 라운드 수를 줄임) 아예 새로 설계. 이 경우 표준 지식을 그대로 쓸 수 없고, 코드 자체를 처음부터 분석해야 한다.

두 경우를 구분하는 것이 분석 전략을 결정한다 — 표준 암호의 변형이라면 "표준과 다른 부분이 무엇인지"에 집중하면 되고, 완전 커스텀이라면 REV-0916(순수 비트 연산 커스텀 알고리즘)과 같은 접근이 필요하다.

### import가 없다는 것 자체가 강한 신호
Windows PE에서 `CryptAcquireContext`, `CryptEncrypt`, `BCryptEncrypt` 같은 CryptoAPI/CNG 함수나, Linux ELF에서 `libcrypto.so`(OpenSSL) 관련 심볼이 Import 테이블에 전혀 없다면, 암호화 로직이 정적으로 바이너리 안에 직접 구현되어 있다는 뜻이다. 이는 REV-0101(Dynamic Linking과 Import 함수 추적)에서 배운 "import 목록으로 감 잡기" 전략이 이 경우엔 통하지 않는다는 뜻이기도 하다 — 라이브러리 문서를 찾아볼 게 아니라 바이너리 내부의 상수와 구조로 알고리즘을 식별해야 한다.

### 표준 암호 식별의 첫 단서 — 상수 매칭
직접 구현된 코드라도 표준 알고리즘을 그대로 옮긴 것이라면, 알고리즘 고유의 "지문 상수"가 코드에 그대로 남아 있다. 이미 이 위키에 정리된 지문들을 활용한다.

- AES: S-box 테이블의 첫 몇 바이트가 `63 7C 77 7B F2 6B 6F C5`로 시작(REV-0211)
- TEA/XTEA: 라운드 상수 `0x9E3779B9`(황금비 기반 delta)가 반복적으로 더해짐(REV-0210)
- FNV: 곱셈 상수 `16777619`(FNV prime) 또는 초기값 `2166136261`(FNV offset basis)이 보임(REV-0207, REV-0208)
- CRC: 다항식 상수(`0xEDB88320` 등 CRC-32 계열)나 256엔트리 CRC 테이블(REV-0209)
- DES: S-box 8개(각 4x16 크기)가 특유의 값으로 존재, 초기 순열(IP)/최종 순열(FP) 테이블이 고정된 상수 배열로 존재

이런 상수 중 하나라도 정확히 일치하면, 그 알고리즘의 공개된 표준 명세(FIPS, RFC)를 그대로 가져와 나머지 구조를 대조하면 된다 — 처음부터 새로 분석할 필요가 없다.

### 상수가 하나도 안 맞을 때 — 구조적 특징으로 계열 추정
상수 매칭이 실패하면(전혀 알려지지 않은 상수, 혹은 표준 상수를 일부러 바꾼 경우), 다음 구조적 특징으로 큰 계열(family)만이라도 좁힐 수 있다.

- **Feistel 구조**: 입력을 좌/우 절반으로 나누고, 매 라운드마다 한쪽 절반을 다른 쪽에 대한 함수로 변형한 뒤 서로 교환(swap)하는 구조. DES, TEA/XTEA, Blowfish 계열의 공통 골격이다. 좌우 반씩 나누는 코드와 라운드마다 교환(swap)이 보이면 Feistel 계열로 강하게 의심한다.
- **SPN(Substitution-Permutation Network) 구조**: 치환(S-box)과 순열(비트/바이트 재배열)을 번갈아 반복. AES가 대표적이다. S-box 테이블 참조와 바이트 재배열(shift row 유사 동작)이 각 라운드마다 반복되면 SPN 계열로 의심한다.
- **ARX(Add-Rotate-XOR) 구조**: 덧셈, 비트 회전(rotate), XOR만으로 이루어진 라운드 함수. ChaCha20, Salsa20, TEA/XTEA(덧셈과 시프트/XOR)가 여기 속한다. S-box 없이 순수 산술/비트 연산만 반복되면 ARX 계열이며, 이는 REV-0916에서 다루는 "상수 없는 순수 비트 연산" 커스텀 알고리즘과 경계가 맞닿아 있다.

계열만 알아도 대응 전략이 갈린다 — Feistel/SPN은 라운드 함수 하나만 정확히 재구현하면 전체가 그 반복이므로 분석량이 크게 줄고, ARX는 라운드 수와 회전 상수(rotation amount)만 확인하면 된다.

### 라운드 수 세기
표준 암호와 구별되는 흔한 변형 포인트는 라운드 수다. AES-128은 10라운드, DES는 16라운드가 표준이지만, CTF에서는 종종 라운드 수를 줄이거나(예: AES를 4라운드만) 늘려서 난이도를 조절한다. 루프 카운터의 상한값을 정확히 확인해 실제 라운드 수를 세는 것이 표준 구현과 정확히 일치하는지 판단하는 데 중요하다.

## 화면/코드에서 보이는 징후
- Import 테이블/`nm` 결과에 암호 라이브러리 심볼이 전혀 없음
- 코드에 `for (round = 0; round < N; round++)` 형태의 라운드 루프와 그 안에서 반복되는 서브함수 호출(치환, 순열, 키 XOR)
- 256엔트리 또는 16/64엔트리 짜리 정체불명의 상수 테이블
- 좌/우 절반을 나누고 교환하는 코드(Feistel 구조 힌트), 또는 회전(`rol`/`ror`)과 XOR/덧셈만 반복되는 코드(ARX 힌트)

## 가장 먼저 할 것
`nm`/Import 창으로 암호 라이브러리 흔적이 정말 없는지 재확인하고, 코드 안의 모든 상수 테이블과 매직 넘버를 나열한다. 그 상수들을 REV-0207~0211에 정리된 지문 상수와 하나씩 대조한다.

## 단계별 절차
1. `nm ./chall | grep -iE "aes|des|rc4|crypt|sha|md5"`와 Import 창으로 라이브러리 흔적 유무를 확정한다.
2. 코드 내 모든 상수 배열과 매직 넘버(`0x9E3779B9`, `63 7C 77 7B...` 등)를 나열하고 알려진 지문과 대조한다(REV-0207~0211).
3. 상수가 일치하면 해당 알고리즘의 공식 명세(FIPS 197, RFC 등)를 가져와 나머지 구조(라운드 수, 키 스케줄)를 대조하며 차이점(변형된 부분)만 찾는다.
4. 상수가 일치하지 않으면 구조(Feistel/SPN/ARX)를 관찰해 계열만 추정한다.
5. 라운드 함수 하나를 정확히 재구현하고, 전체 라운드 수만큼 파이썬에서 반복 적용해 전체 알고리즘을 완성한다.
6. 재구현 결과를 실제 바이너리의 알려진 입출력 쌍과 비교해 검증한다(REV-0912, REV-0919).

## 명령어/단축키
```bash
nm ./chall | grep -iE "aes|des|rc4|crypt|sha|md5|blowfish"
strings ./chall | grep -iE "openssl|libcrypto|bcrypt|cryptacquire"
```
```python
# 지문 상수 스캔 헬퍼 - 바이너리에서 뽑은 바이트열에 알려진 상수가 있는지 확인
known_constants = {
    "AES S-box 시작": bytes.fromhex("637c777bf26b6fc5"),
    "TEA/XTEA delta": (0x9E3779B9).to_bytes(4, "little"),
    "FNV prime": (16777619).to_bytes(4, "little"),
    "FNV offset basis": (2166136261).to_bytes(4, "little"),
}

def scan_constants(blob: bytes):
    for name, pattern in known_constants.items():
        if pattern in blob:
            print(f"MATCH: {name} at offset {blob.index(pattern)}")
```

## 출력 해석
- `scan_constants()`가 매치를 찾으면, 그 알고리즘의 공식 표준 문서를 그대로 참고해도 좋다는 뜻이다 — 이후 분석은 "표준과 다른 점"만 찾으면 된다.
- 매치가 하나도 없으면 완전 커스텀 암호이거나 상수가 의도적으로 변형된 것이다 — 구조적 특징(Feistel/SPN/ARX)으로 접근 방식만 좁히고, 라운드 함수를 처음부터 직접 재구현해야 한다.
- 라운드 수가 표준값(AES 10, DES 16)과 다르게 세어진다면 의도적인 변형이므로, 재구현 시 표준값이 아니라 실제로 센 값을 그대로 써야 한다.

## 흔한 실수
- 라이브러리 import가 없다고 "이건 암호가 아니라 그냥 잡다한 연산이다"라고 오판하는 것 — 직접 구현된 암호는 라이브러리 흔적이 전혀 없는 게 정상이다.
- 상수 몇 바이트만 비슷하다고 성급히 특정 알고리즘으로 단정하는 것 — 반드시 여러 바이트(최소 8바이트 이상) 연속 일치를 확인하고, 가능하면 두 번째 지문(예: AES라면 S-box뿐 아니라 라운드 상수 Rcon도)까지 교차 확인한다.
- Feistel 구조인데 SPN처럼 접근해서 좌우 절반을 나누는 로직을 놓치는 것 — 구조 식별을 먼저 정확히 하지 않으면 재구현 방향 자체가 틀어진다.
- 표준 암호의 변형(라운드 수 축소 등)을 원본 표준 그대로 재구현해서 결과가 안 맞는데, 원인을 못 찾고 헤매는 것 — 반드시 실제 루프 상한값(라운드 수)을 코드에서 직접 세어 확인해야 한다.

## 막혔을 때 다음 체크
- 상수도 없고 구조도 애매한 순수 비트 연산이라면 → REV-0916 상수 없이 순수 비트 연산만으로 된 커스텀 알고리즘 접근법
- 이게 대칭키가 아니라 비대칭키(RSA 등)일 가능성도 있다면 → REV-0914 대칭 vs 비대칭 여부를 코드만 보고 판단하는 법
- 재구현이 정확한지 확실히 검증하고 싶다면 → REV-0912 알고리즘 복원 결과를 유닛 테스트로 검증하는 법, REV-0919
- 개별 지문 상수 각각에 대해 더 자세히 알고 싶다면 → REV-0207 FNV-1과 FNV-1a 해시 패턴, REV-0209 CRC 계열 알고리즘 흔적 찾기, REV-0210 TEA와 XTEA 상수 패턴, REV-0211 AES 테이블 또는 AES API 흔적 찾기

## 미니 예제
어떤 바이너리에서 Import 목록이 텅 비어 있고, 다음과 같은 루프가 발견됐다고 하자.

```c
void round_func(uint32_t *v0, uint32_t *v1, uint32_t sum, uint32_t *key) {
    *v0 += (((*v1 << 4) ^ (*v1 >> 5)) + *v1) ^ (sum + key[sum & 3]);
}

void encrypt(uint32_t *v0, uint32_t *v1, uint32_t *key) {
    uint32_t sum = 0;
    uint32_t delta = 0x9E3779B9;
    for (int i = 0; i < 32; i++) {
        sum += delta;
        round_func(v0, v1, sum, key);
        // v1도 유사하게 갱신 (생략)
    }
}
```

`delta = 0x9E3779B9`라는 상수가 정확히 TEA 계열의 지문(REV-0210)과 일치하므로, 이 알고리즘이 TEA 또는 그 변형임을 즉시 알 수 있다. 이후에는 TEA의 공개된 표준 구현을 참고해 `v0`/`v1`이 어떻게 갱신되는지 나머지 절반을 대조하고, 라운드 수(여기서는 32)가 표준과 같은지만 확인하면 재구현이 끝난다.

### 완전한 예제 스크립트 — TEA 표준 명세를 그대로 재구현해서 암호화/복호화 왕복 검증하기
지문 상수(`0x9E3779B9`)를 확인했다면, TEA의 공개된 표준 알고리즘을 그대로 파이썬으로 옮겨서 암호화한 값이 다시 복호화했을 때 원래 값으로 돌아오는지(왕복 검증) 확인하는 것이 재구현 정확성을 검증하는 가장 확실한 방법이다.

```python
def tea_encrypt(v0: int, v1: int, key: tuple, rounds: int = 32):
    """
    TEA(Tiny Encryption Algorithm) 표준 암호화.
    v0, v1 : 암호화할 64비트 평문을 32비트씩 나눈 두 조각
    key    : 128비트 키를 32비트씩 4조각으로 나눈 튜플 (k[0], k[1], k[2], k[3])
    rounds : 라운드 수 (표준은 32라운드)
    """
    delta = 0x9E3779B9   # TEA 고유의 지문 상수 (황금비 기반)
    mask = 0xFFFFFFFF     # 32비트로 결과를 잘라내기 위한 마스크
    total = 0             # sum 역할을 하는 누산 변수, 매 라운드마다 delta씩 증가

    for _ in range(rounds):
        total = (total + delta) & mask
        # v1을 이용해 v0를 갱신 (좌측 시프트/우측 시프트로 v1을 흔들고, 키의 일부와 XOR)
        v0 = (v0 + (((v1 << 4) ^ (v1 >> 5)) + v1 ^ (total + key[total & 3]))) & mask
        # 이번엔 갱신된 v0를 이용해 v1을 갱신 (대칭적인 구조)
        v1 = (v1 + (((v0 << 4) ^ (v0 >> 5)) + v0 ^ (total + key[(total >> 11) & 3]))) & mask
    return v0, v1


def tea_decrypt(v0: int, v1: int, key: tuple, rounds: int = 32):
    """TEA 표준 복호화. 암호화의 모든 연산을 정확히 반대 순서로 되돌린다."""
    delta = 0x9E3779B9
    mask = 0xFFFFFFFF
    total = (delta * rounds) & mask   # 복호화는 total이 이미 최댓값에서 시작해서 거꾸로 줄어든다

    for _ in range(rounds):
        # 암호화의 마지막 라운드부터 거꾸로 v1, v0를 원래대로 되돌린다 (뺄셈으로 더하기를 상쇄)
        v1 = (v1 - (((v0 << 4) ^ (v0 >> 5)) + v0 ^ (total + key[(total >> 11) & 3]))) & mask
        v0 = (v0 - (((v1 << 4) ^ (v1 >> 5)) + v1 ^ (total + key[total & 3]))) & mask
        total = (total - delta) & mask
    return v0, v1


# 128비트 키를 32비트 4조각으로 나눈 예시 값
key = (0x11111111, 0x22222222, 0x33333333, 0x44444444)

# 암호화할 원래 평문 (64비트를 32비트 두 조각으로 나눈 값)
v0, v1 = 0x01020304, 0x05060708
print("원래 평문:", hex(v0), hex(v1))

encrypted_v0, encrypted_v1 = tea_encrypt(v0, v1, key)
print("암호화 결과:", hex(encrypted_v0), hex(encrypted_v1))

decrypted_v0, decrypted_v1 = tea_decrypt(encrypted_v0, encrypted_v1, key)
print("복호화 결과:", hex(decrypted_v0), hex(decrypted_v1))

print("왕복 검증 (원래 평문과 같아야 함):", (decrypted_v0, decrypted_v1) == (v0, v1))
```

실제로 실행한 결과:
```
원래 평문: 0x1020304 0x5060708
암호화 결과: 0xf1fa925f 0xa6627240
복호화 결과: 0x1020304 0x5060708
왕복 검증 (원래 평문과 같아야 함): True
```

암호화한 값을 복호화했더니 정확히 원래 평문으로 돌아왔다. 이렇게 "암호화 -> 복호화 왕복"이 항상 원본과 일치하는지 확인하는 것은, 표준 알고리즘을 재구현했을 때 로직이 정확한지 판단하는 가장 기본적이면서도 강력한 검증 방법이다(REV-0912의 유닛 테스트, REV-0919의 차분 테스트와도 같은 원리다). 만약 실전에서 만난 바이너리가 표준 TEA와 라운드 수나 델타 값이 다르다면, 위 스크립트의 `rounds` 인자와 `delta` 상수만 실제로 확인한 값으로 바꿔서 똑같이 왕복 검증을 해보면 된다.

## 관련 글
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- REV-0208 — 16777619 상수가 보일 때 FNV 의심하기
- REV-0209 — CRC 계열 알고리즘 흔적 찾기
- REV-0210 — TEA와 XTEA 상수 패턴
- REV-0211 — AES 테이블 또는 AES API 흔적 찾기
- REV-0916 — 상수 없이 순수 비트 연산만으로 된 커스텀 알고리즘 접근법
- REV-0914 — 대칭 vs 비대칭 여부를 코드만 보고 판단하는 법

## 출처/검증
- Feistel 구조, SPN 구조, ARX 구조의 표준 정의와 대표 알고리즘(DES/Feistel, AES/SPN, ChaCha20·Salsa20/ARX): 각 알고리즘의 공식 명세(FIPS 46-3, FIPS 197) 및 ChaCha 설계자 Daniel J. Bernstein의 공개 문서 기준.
- TEA/XTEA의 delta 상수(`0x9E3779B9`, 황금비 기반)와 알고리즘 구조: TEA 원 논문(Wheeler and Needham, "TEA, a Tiny Encryption Algorithm", 1994) 기준 (2026-09-09 검증).
