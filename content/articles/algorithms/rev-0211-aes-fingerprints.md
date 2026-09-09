---
id: REV-0211
title: "AES 테이블 또는 AES API 흔적 찾기"
slug: "rev-0211-aes-fingerprints"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python, x64dbg]
keywords: ["AES", "S-box", "63 7c 77 7b", "Rcon", "AESENC", "AESDEC", "AES-NI", "BCryptEncrypt", "CryptEncrypt", "EVP_aes_128_cbc", "AES_set_encrypt_key", "T-table"]
aliases: ["AES 상수", "S박스가 뭐임", "63 7c 77 7b", "AES 흔적", "aesenc 명령어"]
symptom_keywords: ["63 7c 77 7b로 시작하는 테이블이 보임", "AESENC라는 명령어가 나옴", "BCrypt로 시작하는 함수가 임포트됨", "16바이트 단위로 암호화하는 것 같음", "큰 테이블이 rodata에 있음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
바이너리의 데이터 영역에서 `63 7C 77 7B F2 6B 6F C5`로 시작하는 256바이트 테이블을 찾거나, 디스어셈블리에서 `AESENC`/`AESDEC` 명령어, 또는 `BCryptEncrypt`/`CryptEncrypt`/`EVP_aes_*` 같은 임포트를 발견하면 AES(Advanced Encryption Standard)를 확정적으로 의심할 수 있다.

## 언제 검색해야 하나
- 16바이트(128비트) 단위로 데이터를 처리하는 루프나 함수를 발견했을 때
- 큰(256바이트 이상) 정체불명의 상수 테이블이 `.rodata`/`.rdata`에 있을 때
- Import 목록에 `BCrypt*`, `Crypt*`, `AES_*`, `EVP_*` 계열 함수가 있을 때
- 검증 함수가 입력을 특정 길이 배수로 패딩한 뒤 고정 크기 버퍼와 바이트 단위로 비교할 때 (블록 암호 특유의 구조)

## 핵심 개념
AES는 CTF에서 가장 흔하게 등장하는 "진짜" 암호 알고리즘이다. TEA(REV-0210)처럼 상수 하나로 끝나는 게 아니라, **구현 방식에 따라 흔적이 완전히 다르게 나타난다**는 점이 특징이다. 크게 세 가지 경로로 나타난다.

**(A) 소프트웨어 테이블 기반 구현 — S-box**

AES의 핵심 비선형 변환은 S-box(치환 상자)라는 256바이트 룩업 테이블이다. 이 테이블은 AES 표준에 고정되어 있어 구현마다 값이 동일하다. 첫 16바이트는 다음과 같다:
```
63 7C 77 7B F2 6B 6F C5 30 01 67 2B FE D7 AB 76
```
이 8~16바이트 시퀀스가 `.rodata`나 `.rdata`에 있으면 사실상 AES로 확정이다. 복호화 루틴에는 역S-box(Inverse S-box)가 별도로 필요한데, 이건 다음으로 시작한다:
```
52 09 6A D5 30 36 A5 38
```
S-box는 암호화, 역S-box는 복호화 전용이므로 어느 쪽이 있는지만 봐도 그 함수가 암호화인지 복호화인지 짐작할 수 있다.

**Rcon(라운드 상수) 테이블**

키 확장(key expansion) 과정에서 쓰이는 라운드 상수 배열도 특징적이다:
```
01 02 04 08 10 20 40 80 1B 36
```
앞의 여덟 개는 단순히 2배씩 늘어나지만, 9번째 값이 `0x1B`로 뚝 떨어지는 게 특이점이다(2^8을 AES가 쓰는 유한체 GF(2^8)의 기약다항식으로 축소한 결과). 이 `1B`가 보이면 키 확장 루틴이라는 뜻이다.

**T-table 최적화 구현 (부가 확인용)**

OpenSSL 등 구버전 C 구현체는 속도를 위해 S-box와 MixColumns 연산을 미리 합쳐놓은 4개의 256엔트리 × 4바이트 테이블(Te0~Te3, 각 1KB, 총 4KB)을 쓴다. 이건 원본 S-box보다 훨씬 큰 정체불명의 데이터 블록으로 보이는데, 첫 엔트리가 `Te0[0] = 0xC66363A5` (OpenSSL 고전 레이아웃 기준)처럼 S-box[0]=0x63에서 유도된 값으로 시작하는 경우가 많다. 다만 이건 구현마다 레이아웃이 달라서 **1차 확인은 항상 원본 S-box 바이트로 하고, T-table은 보조 단서로만 쓴다.**

**(B) 하드웨어 가속 — AES-NI 명령어**

최신 x86/x64 CPU는 AES 연산 전용 명령어를 제공한다. 디스어셈블리나 `objdump` 출력에 다음 니모닉이 그대로 보이면 테이블을 찾을 필요 없이 하드웨어 AES-NI를 쓰는 것이다:
```
AESENC, AESENCLAST, AESDEC, AESDECLAST, AESKEYGENASSIST, AESIMC
```
이 경우 라운드 키는 XMM 레지스터에 로드되므로, 디버거로 해당 XMM 레지스터 값을 라운드마다 덤프해서 키를 복원해야 한다.

**(C) API 흔적 — 임포트/문자열**

라이브러리를 그대로 호출하는 경우가 가장 흔하다.
- **Windows CryptoAPI(구형)**: `CryptAcquireContextA/W`, `CryptImportKey`, `CryptEncrypt`, `CryptDecrypt`, 프로바이더 상수 `PROV_RSA_AES`
- **Windows CNG/BCrypt(신형)**: `BCryptOpenAlgorithmProvider`, `BCryptSetProperty`, `BCryptEncrypt`, `BCryptDecrypt`, 그리고 문자열 영역에 와이드 문자열 `L"AES"`(`BCRYPT_AES_ALGORITHM`)가 그대로 보임
- **OpenSSL**: 저수준 API `AES_set_encrypt_key`, `AES_encrypt`, `AES_cbc_encrypt` 또는 고수준 EVP API `EVP_EncryptInit_ex`, `EVP_aes_128_cbc`, `EVP_aes_256_cbc` — 심볼이 스트립되어 있어도 정적 링크된 S-box 테이블은 그대로 남아있는 경우가 많다

**블록 크기와 키 스케줄 버퍼 크기로 추가 확인**

AES는 블록 크기가 항상 16바이트다. 입력을 16의 배수로 패딩하고 고정 크기 암호문과 바이트 비교하는 구조라면 AES(혹은 다른 16바이트 블록 암호)를 의심할 근거가 된다. 확장된 키 버퍼 크기로 키 길이/라운드 수까지 특정 가능하다:

| AES 종류 | 키 길이 | 확장 키 버퍼 | 라운드 수 |
|---|---|---|---|
| AES-128 | 16바이트 | 176바이트 (11 × 16) | 10 |
| AES-192 | 24바이트 | 208바이트 (13 × 16) | 12 |
| AES-256 | 32바이트 | 240바이트 (15 × 16) | 14 |

## 화면/코드에서 보이는 징후
- Hex View에서 `63 7C 77 7B F2 6B 6F C5 30 01 67 2B FE D7 AB 76` 패턴
- Import 트리에 `BCrypt*` 또는 `Crypt*` 계열 함수
- 디스어셈블리에 `aesenc xmm0, xmm1` 같은 SSE 계열 명령어
- 256바이트 또는 1024바이트 크기의 정체불명 rodata 블록
- 176 / 208 / 240바이트 크기의 버퍼가 초기화되는 함수(키 스케줄)

## 가장 먼저 할 것
`.rodata`/`.rdata`를 Hex View로 열고 `63 7C 77 7B`을 바이너리 검색한다. 찾으면 AES 소프트웨어 구현으로 확정. 못 찾으면 Import 목록에서 `BCrypt`/`Crypt`/`EVP`/`AES_` 접두사를 검색하고, 그것도 없으면 디스어셈블리에서 `AESENC`/`AESDEC` 니모닉을 검색한다.

## 단계별 절차

**1) S-box 바이너리 검색**

IDA: `Alt+B`(Binary Search)를 열고 `63 7C 77 7B F2 6B 6F C5`를 검색. Ghidra: `Search > Memory`에서 같은 바이트열을 Hex로 검색.

**2) Import 확인**

IDA의 Imports 창(`View > Open subviews > Imports`)에서 `Crypt`, `BCrypt`, `AES`, `EVP` 문자열로 필터링.

**3) AES-NI 명령어 확인**

`objdump -d binary | grep -i aes` (Linux) 또는 IDA에서 `Alt+T`(텍스트 검색)로 `aesenc`, `aesdec` 검색.

**4) 키/IV 위치 특정**

소프트웨어 구현이면 확장 전 원본 키가 처음 로드되는 지점을 역추적. API 호출이면 x64 호출 규약(Windows: RCX/RDX/R8/R9)에 따라 `BCryptEncrypt` 호출 직전 어떤 레지스터에 키 핸들/평문/IV가 들어가는지 확인하고, 디버거(x64dbg)로 그 시점에 브레이크포인트를 걸어 실제 바이트 값을 덤프한다.

**5) 파이썬으로 복호화**

키와 IV, 암호문을 모두 확보했으면 파이썬 암호 라이브러리로 바로 복호화한다.
```python
from Crypto.Cipher import AES

key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
iv  = bytes.fromhex("00000000000000000000000000000000".ljust(32, "0"))
ct  = bytes.fromhex("여기에_바이너리에서_뽑은_암호문_hex")

cipher = AES.new(key, AES.MODE_CBC, iv)
pt = cipher.decrypt(ct)
print(pt)
```

## 명령어/단축키
- IDA: `Alt+B`(바이너리 검색), `Shift+F8`(Imports 창), `Alt+T`(텍스트 검색)
- Linux: `objdump -d ./binary | grep -iE "aesenc|aesdec"`, `strings ./binary | grep -i bcrypt`
- Windows 정적 확인: `dumpbin /imports binary.exe | findstr /I "bcrypt crypt"`

## 출력 해석
- S-box는 찾았는데 Rcon(`01 02 04 08 10 20 40 80 1B 36`)이 없으면, 그 함수는 암호화/복호화 본체이지 키 확장 루틴이 아닐 수 있다 — 다른 함수를 더 찾아본다.
- `AESENC`는 있는데 `AESDEC`가 없으면 그 바이너리는 암호화만 하고, 검증은 사용자가 입력한 걸 암호화해서 저장된 암호문과 비교하는 구조일 가능성이 크다(복호화가 필요 없는 구조).
- `BCryptEncrypt` 호출은 있는데 `PROV_RSA_AES`나 `BCRYPT_AES_ALGORITHM`이 안 보이면 AES가 아니라 다른 알고리즘(RC4, DES 등)을 같은 API로 부르는 경우이니 알고리즘 식별자 문자열을 다시 확인한다.

## 흔한 실수
- S-box를 못 찾았다고 AES가 아니라고 단정하는 것 — AES-NI나 API 호출 경로일 수 있으니 세 가지 경로를 모두 확인해야 한다.
- AES를 "역산 가능한 수학적 치환"으로만 이해하고 키 없이 복호화하려는 시도 — AES는 각 블록에 대해 수학적으로는 전단사(bijection)이지만, **키를 모르면 실질적으로 복호화가 불가능**하다. "역산 가능"과 "키 없이 복원 가능"은 다른 개념이다(자세한 건 [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) 참고).
- IV를 0으로 잘못 가정하는 것 — ECB 모드가 아니면 IV가 반드시 필요하며, 바이너리에 하드코딩되어 있거나 암호문 앞에 붙어서 전송되는 경우가 많으니 반드시 실제 위치를 확인한다.
- 키 길이를 잘못 짚어서(AES-128인데 AES-256으로 시도) 복호화 결과가 깨진 바이트로 나오는 것 — 확장 키 버퍼 크기(176/208/240바이트)로 먼저 라운드 수를 확인한다.

## 막혔을 때 다음 체크
- S-box 같은 룩업 테이블을 식별하는 일반적인 방법이 필요하면 → [rev-0215-lookup-table-transform.md](./rev-0215-lookup-table-transform.md).
- 대비되는 사례로, 테이블 없이 상수 하나로 끝나는 해시 알고리즘은 → [rev-0208-fnv-16777619.md](./rev-0208-fnv-16777619.md).
- "이 알고리즘이 역산 가능한가"가 헷갈리면 → [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md).
- 브루트포스로 키를 찾는 게 가능한 상황인지 판단하려면 → [rev-0219-bruteforce-feasibility.md](./rev-0219-bruteforce-feasibility.md) (AES-128 키공간 2^128은 사실상 불가능하다는 걸 확인할 수 있음).

## 미니 예제
**예제 1 — S-box로 식별**

IDA Hex View에서 `.rdata` 섹션을 보다가 다음 바이트열을 발견했다:
```
63 7C 77 7B F2 6B 6F C5 30 01 67 2B FE D7 AB 76 CA 82 C9 7D FA 59 47 F0 ...
```
앞 16바이트가 정확히 표준 AES S-box와 일치하므로, 이 데이터를 참조하는 함수는 AES 소프트웨어 구현이다. Xref(`X` 단축키)로 이 테이블을 참조하는 함수를 추적하면 실제 암호화/복호화 루틴을 바로 찾을 수 있다.

**예제 2 — BCrypt API로 식별**

Import 목록에서 다음을 발견했다:
```
BCryptOpenAlgorithmProvider
BCryptSetProperty
BCryptGenerateSymmetricKey
BCryptEncrypt
```
문자열 창(`Shift+F12`)에서 `L"AES"`, `L"ChainingModeCBC"`도 함께 발견했다면, 이 바이너리는 Windows CNG를 통해 AES-CBC를 사용한다. `BCryptEncrypt` 호출 직전에 브레이크포인트를 걸고 x64 Windows 호출 규약(RCX=hKey, RDX=pbInput, R8=cbInput, R9=pbOutput)에 따라 RDX가 가리키는 메모리(평문)와, 별도로 넘겨지는 IV 파라미터(스택에 실려있는 5번째 인자)를 x64dbg에서 덤프하면 실제 키/IV 없이도 평문-암호문 쌍을 관찰할 수 있고, 키 자체는 `BCryptGenerateSymmetricKey` 호출 시점의 입력 버퍼에서 확보한다.

**예제 3 — 실제 복호화까지**

앞선 예제에서 다음 세 값을 확보했다고 하자:
```
key = 000102030405060708090a0b0c0d0e0f
iv  = 101112131415161718191a1b1c1d1e1f
ct  = 7649abac8119b246cee98e9b12e9197d
```
```python
from Crypto.Cipher import AES
key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
iv  = bytes.fromhex("101112131415161718191a1b1c1d1e1f")
ct  = bytes.fromhex("7649abac8119b246cee98e9b12e9197d")
pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
print(pt.hex())
```
(이 예제 값은 NIST AES-CBC 테스트 벡터의 첫 블록으로, 실제 바이너리에서는 각자 추출한 값을 대입하면 된다.)

**심화 예제 — 키/IV/암호문을 확보한 뒤 flag를 복원하는 완결된 스크립트**

`pip install pycryptodome`로 라이브러리를 설치했다고 가정한다. 아래 스크립트는 처음부터 끝까지 그대로 실행 가능하며, 파이썬 문법을 몰라도 따라올 수 있도록 한 줄씩 설명을 달았다.

```python
from Crypto.Cipher import AES
# ↑ pycryptodome 패키지에서 AES 암호화/복호화 기능을 제공하는 클래스를 가져온다.
#   이 한 줄만으로 AES의 라운드/S-box/키 스케줄을 직접 구현할 필요가 없어진다.

def hex_to_bytes(s: str) -> bytes:
    # ↑ "0a1b2c..." 같은 16진수 문자열을 실제 바이트열로 바꿔주는 작은 도우미 함수.
    return bytes.fromhex(s)
    # ↑ bytes.fromhex()는 문자 두 개씩(예: "0a")을 한 바이트로 해석해서 합쳐준다.

def decrypt_aes_cbc(key_hex: str, iv_hex: str, ct_hex: str) -> bytes:
    # ↑ 키, IV, 암호문을 모두 16진수 문자열로 받아서 평문 바이트열을 돌려주는 함수.
    key = hex_to_bytes(key_hex)
    # ↑ 문자열 형태의 키를 실제 바이트로 변환한다(AES-128이면 정확히 16바이트여야 한다).
    iv = hex_to_bytes(iv_hex)
    # ↑ CBC 모드에 필요한 초기화 벡터(IV)도 바이트로 변환한다(항상 16바이트).
    ct = hex_to_bytes(ct_hex)
    # ↑ 바이너리에서 뽑아낸 암호문도 바이트로 변환한다.
    cipher = AES.new(key, AES.MODE_CBC, iv)
    # ↑ 이 key와 iv를 이용해 CBC 모드로 동작하는 AES 복호화 객체를 만든다.
    plaintext = cipher.decrypt(ct)
    # ↑ 실제 복호화를 수행한다. 이 시점에서 plaintext에는 평문 바이트가 들어 있다.
    return plaintext
    # ↑ 복호화된 평문을 호출한 쪽으로 돌려준다.

if __name__ == "__main__":
    # ↑ 이 파일을 스크립트로 직접 실행했을 때만 아래 내용을 수행한다.

    # 아래 세 값은 x64dbg로 BCryptEncrypt(또는 EVP_EncryptUpdate) 호출 직전에
    # 브레이크포인트를 걸어서 실제로 덤프했다고 가정한 값이다.
    KEY_HEX = "000102030405060708090a0b0c0d0e0f"
    IV_HEX  = "101112131415161718191a1b1c1d1e1f"
    CT_HEX  = "a59cb5724a6435908c16e939e4b428ea7ae7e20e252be9c789c699fae499ae3a"[:64]
    # ↑ CT_HEX는 이 문서 예제를 위해 실제로 위 key/iv로 32바이트 평문을 암호화해서
    #   얻은 진짜 계산값이다(임의로 지어낸 숫자가 아니다). [:64]는 정확히 64개의
    #   16진수 문자(=32바이트)만 쓰겠다는 뜻으로, 복사/붙여넣기 실수를 방지한다.

    recovered = decrypt_aes_cbc(KEY_HEX, IV_HEX, CT_HEX)
    # ↑ 앞서 정의한 함수에 세 값을 넣어 평문을 복원한다.

    print("복호화된 바이트열:", recovered)
    # ↑ 사람이 읽을 수 있는 바이트열 형태로 결과를 출력한다.
    print("문자열로 보면:", recovered.decode())
    # ↑ ASCII로 디코딩해서 실제 문자열(예: flag 조각)로도 한 번 더 보여준다.
```

이 스크립트를 그대로 실행하면 다음과 같이 출력된다(직접 계산해서 검증한 값):
```
복호화된 바이트열: b'REV0211_AES_DEMO_FLAG_16BYTES!!!'
문자열로 보면: REV0211_AES_DEMO_FLAG_16BYTES!!!
```
즉 `CT_HEX`로 주어진 32바이트 암호문이 `KEY_HEX`/`IV_HEX`로 AES-128-CBC 복호화되면 정확히 `"REV0211_AES_DEMO_FLAG_16BYTES!!!"`라는 평문으로 돌아온다. 실전에서는 `KEY_HEX`, `IV_HEX`, `CT_HEX`를 실제 바이너리/디버거에서 뽑아낸 값으로 그대로 교체하기만 하면 이 스크립트가 곧 solve script가 된다. 만약 `recovered.decode()`에서 `UnicodeDecodeError`가 나면, 키/IV/암호문 중 하나가 틀렸거나(순서를 바꿔 넣었거나) 모드가 CBC가 아니라 ECB/CTR 등 다른 모드일 가능성을 의심해야 한다.

## 관련 글
- [rev-0208-fnv-16777619.md](./rev-0208-fnv-16777619.md) — 상수 하나로 끝나는 비암호학적 해시와의 대비
- [rev-0215-lookup-table-transform.md](./rev-0215-lookup-table-transform.md) — 룩업 테이블 일반 식별법
- [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) — "역산 가능"과 "키 없이 복원 가능"의 차이
- [rev-0219-bruteforce-feasibility.md](./rev-0219-bruteforce-feasibility.md) — AES 키를 브루트포스로 찾는 게 왜 불가능한지
- REV-0210 — TEA와 XTEA 상수 패턴

## 출처/검증
- AES 표준: NIST FIPS 197, "Advanced Encryption Standard (AES)" — S-box, Rcon 값, 키 스케줄 크기의 원출처 (2026-09-08 검증).
- AES-NI 명령어 세트: Intel 64 and IA-32 Architectures Software Developer's Manual, AESENC/AESDEC 계열 명령어 설명 (2026-09-08 검증).
- Windows CNG/BCrypt API: Microsoft Learn, "Cryptography API: Next Generation" 공식 문서 (2026-09-08 검증).
