---
id: REV-0899
title: "DES/3DES 상수와 S-Box 흔적 알아보기"
slug: "rev-0899-des-3des-sbox-fingerprint"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["DES", "3DES", "Triple DES", "S-box", "Feistel", "Initial Permutation", "IP", "EDE", "56비트 키", "8바이트 블록"]
aliases: ["des 상수", "3des 상수", "des s박스", "feistel 구조", "des 흔적 찾기"]
symptom_keywords: ["8바이트 단위로 암호화함", "16라운드 반복문이 있음", "S1 S2 ... S8 테이블 8개가 보임", "58 50 42 34 순서의 테이블이 있음", "48비트 서브키를 생성함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
8바이트(64비트) 블록을 16라운드짜리 좌우 교환(Feistel) 구조로 반복 처리하면서, 정확히 8개의 S-box 테이블(각 4×16 = 64엔트리, 6비트 입력→4비트 출력)과 `58, 50, 42, 34, ...`로 시작하는 초기 순열(Initial Permutation) 테이블이 보이면 DES(Data Encryption Standard)이며, 이 DES 루틴이 세 번(암호화-복호화-암호화, EDE) 반복되면 3DES(Triple DES)다.

## 언제 검색해야 하나
- 입력을 정확히 8바이트씩 나눠서 처리하는 암호화/복호화 함수를 발견했을 때 (AES는 16바이트 블록, DES는 8바이트 블록이라는 점으로 우선 구분 가능)
- 함수 안에 정확히 16번(3DES면 48번, 16×3) 반복되는 라운드 루프가 있고, 매 라운드마다 좌우 절반을 맞바꾸는(swap) 코드가 있을 때
- `.rodata`에 4×16 크기(64개 값)의 작은 테이블이 8개 나란히 있을 때 — 이것이 DES의 S-box(S1~S8)
- Import 목록에 `CryptImportKey`+`CALG_DES`/`CALG_3DES`, 또는 OpenSSL `DES_set_key`/`DES_ecb_encrypt`/`EVP_des_ede3_cbc` 같은 함수가 있을 때

## 핵심 개념

### DES의 기본 구조 — Feistel 네트워크
DES는 1977년 미국 연방 표준으로 채택된 블록 암호로, 64비트(8바이트) 평문 블록을 56비트 키(실제로는 8바이트지만 각 바이트의 최하위 비트는 패리티 체크용이라 유효 키 길이는 56비트)로 암호화한다. 핵심은 **Feistel 네트워크**라는 구조인데, 블록을 좌(L)/우(R) 32비트씩 둘로 나눈 뒤 16라운드에 걸쳐 다음을 반복한다:
```
L[i] = R[i-1]
R[i] = L[i-1] XOR f(R[i-1], K[i])
```
여기서 `f`는 확장(Expansion)→서브키 XOR→S-box 치환→P-박스 순열로 이어지는 라운드 함수이고, `K[i]`는 원본 키에서 유도된 48비트 라운드별 서브키다. Feistel 구조의 특징은 **암호화와 복호화가 라운드 함수는 그대로 두고 서브키 적용 순서만 거꾸로 하면 된다**는 점이다 — 그래서 DES 코드는 암호화용과 복호화용이 거의 동일한 형태로 나타난다.

### Initial Permutation(IP) — 가장 눈에 띄는 첫 지문
DES는 라운드 처리 전에 64비트 블록의 비트 순서를 고정된 규칙으로 뒤섞는 초기 순열(IP)을 적용한다. 이 테이블은 8×8 = 64개의 항목으로, 표준 정의는 다음과 같이 시작한다:
```
58 50 42 34 26 18 10 2
60 52 44 36 28 20 12 4
62 54 46 38 30 22 14 6
64 56 48 40 32 24 16 8
...
```
이 순서(`58, 50, 42, 34, 26, 18, 10, 2`)가 정수 배열 상수로 코드나 데이터 영역에 그대로 있으면 DES로 사실상 확정이다. 라운드가 모두 끝난 뒤에는 이 IP의 역순열(Final Permutation, FP)을 적용해 원래 비트 순서로 되돌린다.

### S-box 8개 — DES의 유일한 비선형 요소
DES에서 유일하게 비선형 연산을 담당하는 부분이 8개의 S-box(S1~S8)다. 각 S-box는 6비트 입력을 받아 4비트 출력을 내는 4행×16열 테이블이며, 입력의 첫 비트와 마지막 비트로 행(0~3)을, 가운데 4비트로 열(0~15)을 선택한다. S1의 표준값은 다음과 같다(FIPS 46 정의):
```
Row0: 14  4 13  1  2 15 11  8  3 10  6 12  5  9  0  7
Row1:  0 15  7  4 14  2 13  1 10  6 12 11  9  5  3  8
Row2:  4  1 14  8 13  6  2 11 15 12  9  7  3 10  5  0
Row3: 15 12  8  2  4  9  1  7  5 11  3 14 10  0  6 13
```
이런 형태의 작은(4×16, 값 범위 0~15) 테이블이 정확히 8개 나란히 있으면 DES의 S-box로 확정할 수 있다. AES의 S-box(REV-0211, 256개 원소 1개 테이블)나 CRC 테이블(REV-0209, 256개 원소, 32비트 값)과는 테이블 크기와 값의 범위가 뚜렷이 다르므로 혼동할 일이 적다.

### 키 스케줄 — PC-1/PC-2와 좌측 순환 시프트
56비트 키에서 16개의 48비트 라운드 서브키를 뽑아내는 과정에서, 키를 두 개의 28비트 절반으로 나눠 라운드마다 1비트 또는 2비트씩 왼쪽으로 순환 시프트(rotate left)하고, PC-2라는 순열로 48비트를 골라낸다. 이 "28비트씩 나눈 두 값이 라운드마다 조금씩 회전한다"는 패턴도 DES 키 스케줄의 특징적인 동작이다.

### 3DES(Triple DES) — DES를 세 번, EDE 구조
3DES는 새로운 알고리즘이 아니라 **DES를 세 번 연달아 적용**하는 방식이다. 가장 흔한 구성은 EDE(Encrypt-Decrypt-Encrypt)로, 서로 다른 키 K1, K2, K3을 사용해:
```
암호화: C = DES_encrypt(K3, DES_decrypt(K2, DES_encrypt(K1, P)))
복호화: P = DES_decrypt(K1, DES_encrypt(K2, DES_decrypt(K3, C)))
```
K1과 K3이 같은 경우(2-key 3DES, 실질 키 길이 112비트)와 K1·K2·K3이 모두 다른 경우(3-key 3DES, 168비트)가 있다. 코드에서는 동일한 DES 라운드 함수가 **암호화→복호화→암호화 순서로 세 번** 호출되는 패턴, 또는 16라운드 루프가 **48회** 반복되는 형태로 나타난다. 중간 단계가 복호화라는 게 핵심이라 단순히 "DES를 3번 암호화"하는 게 아니라는 점을 반드시 확인해야 한다.

### 블록/키 크기 요약과 AES와의 구분
| 항목 | DES | 3DES | AES(REV-0211) |
|---|---|---|---|
| 블록 크기 | 8바이트(64비트) | 8바이트(64비트) | 16바이트(128비트) |
| 키 길이 | 56비트(실질) | 112 또는 168비트 | 128/192/256비트 |
| 라운드 수 | 16 | 16×3=48 | 10/12/14 |
| S-box 개수/크기 | 8개, 4×16 | (DES와 동일 반복) | 1개, 256엔트리 |

블록 크기 8바이트라는 사실 하나만으로도 AES(16바이트)와 즉시 구분되므로, 처음 마주쳤을 때 "8바이트씩 처리하나 16바이트씩 처리하나"부터 확인하는 것이 가장 빠른 1차 분류법이다.

### API/문자열 지문
- **Windows CryptoAPI**: `CryptImportKey`+`CALG_DES`(`0x00006601`) 또는 `CALG_3DES`(`0x00006603`)
- **OpenSSL**: `DES_set_key_checked`, `DES_ecb_encrypt`, `DES_ede3_cbc_encrypt`, 고수준 `EVP_des_cbc`/`EVP_des_ede3_cbc`
- **문자열 지문**: `"DES"`, `"3DES"`, `"TripleDES"`, `"DESede"`(자바 계열에서 흔한 표기)

## 화면/코드에서 보이는 징후
- 8바이트 단위 입력을 좌/우 4바이트씩 나눠 처리하고, 매 라운드 끝에 좌우를 swap
- 정수 상수 `58, 50, 42, 34, 26, 18, 10, 2, ...`로 시작하는 64개짜리 순열 테이블
- 4행×16열 크기(값 범위 0~15)의 작은 테이블이 8개 나란히 배치
- 16회(또는 48회) 반복되는 라운드 루프
- Import에 `CryptImportKey`+`CALG_DES`/`CALG_3DES`, 문자열 `"3DES"`/`"DESede"`

## 가장 먼저 할 것
블록 크기부터 확인한다 — 8바이트씩 처리하면 DES/3DES 계열, 16바이트면 AES(REV-0211) 계열이다. 8바이트가 맞으면 IP 테이블의 시작값 `58, 50, 42, 34`를 정수 배열로 검색해 DES를 확정하고, 같은 라운드 함수가 세 번(E-D-E) 호출되는지 확인해 DES와 3DES를 구분한다.

## 단계별 절차
1. 처리 단위가 8바이트인지 확인(16바이트면 REV-0211 AES로 이동)
2. IDA/Ghidra에서 정수 배열 `58, 50, 42, 34, 26, 18, 10, 2`를 검색(바이트가 아니라 int/byte 배열 형태로 저장되어 있을 수 있음에 유의)
3. `.rodata`에서 4×16 크기 테이블 8개(S1~S8) 존재 확인
4. 라운드 루프가 16회인지(DES), 48회 또는 동일 함수가 세 번 호출되는지(3DES) 확인
5. 3DES라면 두 번째 DES 호출이 암호화가 아니라 복호화 방향인지(EDE 구조) 확인 — 세 번 모두 같은 방향이면 표준 3DES가 아닐 수 있음
6. Import/문자열에서 `CALG_DES`, `CALG_3DES`, OpenSSL 함수명으로 교차 확인
7. Python `pycryptodome`의 `DES`/`DES3` 모듈로 확보한 키/평문/암호문을 대입해 최종 검증

## 명령어/단축키
```bash
strings ./binary | grep -iE "des|3des|desede|tripledes"
objdump -d ./binary | grep -B2 -A2 "0x3a\|58,\s*50,\s*42"
python3 -c "
from Crypto.Cipher import DES
key = b'12345678'
c = DES.new(key, DES.MODE_ECB)
print(c.encrypt(b'ABCDEFGH').hex())
"
```
IDA: `Alt+B`(바이너리 검색)으로 IP 테이블 값(`3A 32 2A 22`, 즉 `58,50,42,34`의 16진수)을 바이트 배열로 검색.

## 출력 해석
- pycryptodome 등 표준 라이브러리로 재현한 결과가 바이너리의 목표 암호문과 일치하면 DES/3DES 사용이 최종 확정된다.
- S-box는 찾았는데 IP 테이블이 안 보이면, IP/FP를 생략한 단순화 구현(일부 임베디드 최적화)이거나 다른 Feistel 암호(예: Blowfish 등)일 수 있으니 S-box 테이블 크기(4×16, 값 0~15)를 다시 확인한다.
- 3DES인데 중간 단계가 암호화 방향으로 보인다면(EDE가 아니라 EEE 등) 표준과 다른 커스텀 변형이므로 재현 코드의 방향을 실제 바이너리 흐름에 맞춰 조정해야 한다.

## 흔한 실수
- DES를 8바이트 블록이라는 이유만으로 무조건 3DES라고 단정하는 것 — 라운드 함수 호출 횟수(16 vs 48, 또는 3회 반복)를 반드시 확인해야 한다.
- 3DES를 "DES를 세 번 암호화"로 잘못 이해하고 E-E-E로 재현해 결과가 안 맞는 것 — 표준 EDE(암호화-복호화-암호화) 순서를 지켜야 한다.
- 56비트 키를 8바이트(64비트)로 착각해 브루트포스 키공간을 잘못 계산하는 것 — 각 바이트의 최하위 비트는 패리티용이라 유효 키공간은 2^56이지 2^64가 아니다.
- DES의 S-box(4×16, 8개)를 AES의 S-box(256개, 1개)나 CRC 테이블(256개, 32비트값)과 혼동하는 것 — 테이블 개수와 크기, 값의 범위(0~15 vs 0~255)로 명확히 구분해야 한다.

## 막혔을 때 다음 체크
- 8바이트가 아니라 16바이트 블록이면 → [rev-0211-aes-fingerprints.md](./rev-0211-aes-fingerprints.md)
- 이 암호가 CBC 모드처럼 이전 블록과 XOR되는 구조인지 확인이 필요하면, IV 위치를 함수 인자에서 먼저 찾아본다(REV-0211의 AES-CBC 절차와 동일한 접근)
- 56비트 키공간 브루트포스가 실제로 가능한지 판단하려면 → [rev-0219-bruteforce-feasibility.md](./rev-0219-bruteforce-feasibility.md)
- 검증 로직을 파이썬으로 재현하려면 → [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md)

## 미니 예제
IDA Hex View에서 `.rodata`를 보다가 다음 정수 배열을 발견했다:
```
3A 32 2A 22 1A 12 0A 02 ...
```
16진수를 10진수로 바꾸면 `58, 50, 42, 34, 26, 18, 10, 2, ...`로, DES의 표준 Initial Permutation과 정확히 일치한다. 근처에 4×16 크기 테이블 8개가 더 있는 것도 확인했다면 DES 확정이다. 함수 호출 그래프를 보니 같은 DES 루틴이 세 번(두 번째는 반대 방향 플래그로) 호출되고 있어 3DES(EDE)임을 알 수 있었다. Python으로 검증:
```python
from Crypto.Cipher import DES3
key = bytes.fromhex("0123456789abcdef" "fedcba9876543210" "0011223344556677")  # 24바이트 3-key
c = DES3.new(key, DES3.MODE_ECB)
ct = c.encrypt(b"ABCDEFGH")
print(ct.hex())
```
바이너리가 요구하는 목표 암호문과 이 결과가 일치하면 3DES-EDE 사용이 확정된다.

### 심화 예제 — 외부 암호 라이브러리 없이 IP 테이블을 직접 적용해보기
`pycryptodome` 같은 외부 라이브러리가 없는 환경(오프라인 대회 PC 등)에서도, DES의 Initial Permutation(IP)이 실제로 비트를 어떻게 재배열하는지 순수 파이썬으로 직접 확인할 수 있다. 아래 스크립트는 표준 DES 예제 평문에 IP를 적용한 뒤, 잘 알려진 참고서(Grabbe, "The DES Algorithm Illustrated")의 검증값과 대조한다.
```python
# DES의 Initial Permutation(IP) 테이블을 순수 파이썬으로 직접 구현해서
# 8바이트 평문 블록의 비트를 실제로 재배열해본다 (외부 암호 라이브러리 불필요)

IP_TABLE = [   # FIPS 46-3에 정의된 표준 IP 테이블(1-base 비트 위치)
    58, 50, 42, 34, 26, 18, 10, 2,
    60, 52, 44, 36, 28, 20, 12, 4,
    62, 54, 46, 38, 30, 22, 14, 6,
    64, 56, 48, 40, 32, 24, 16, 8,
    57, 49, 41, 33, 25, 17, 9,  1,
    59, 51, 43, 35, 27, 19, 11, 3,
    61, 53, 45, 37, 29, 21, 13, 5,
    63, 55, 47, 39, 31, 23, 15, 7,
]

def bytes_to_bitlist(data: bytes) -> list:
    """8바이트(64비트)를 MSB부터 순서대로 담은 비트 리스트(길이 64)로 변환."""
    bits = []
    for byte in data:
        for shift in range(7, -1, -1):     # 상위 비트부터 하나씩 뽑는다
            bits.append((byte >> shift) & 1)
    return bits

def bitlist_to_bytes(bits: list) -> bytes:
    """비트 리스트(길이 64)를 다시 8바이트로 조립."""
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for b in bits[i:i+8]:
            byte = (byte << 1) | b
        out.append(byte)
    return bytes(out)

def apply_ip(block: bytes) -> bytes:
    """IP 테이블 순서대로 비트를 재배열한다. 테이블 값 n은 '원본의 n번째(1-base) 비트'를 뜻한다."""
    bits = bytes_to_bitlist(block)
    permuted = [bits[pos - 1] for pos in IP_TABLE]   # 1-base이므로 pos-1로 인덱싱
    return bitlist_to_bytes(permuted)

sample_block = bytes.fromhex("0123456789ABCDEF")  # 표준 DES 예제에서 자주 쓰이는 평문 블록
permuted = apply_ip(sample_block)

print("원본 블록  :", sample_block.hex())
print("IP 적용 후 :", permuted.hex())
# 이 값을 L0/R0로 나누면 L0=CC00CCFF, R0=F0AAF0AA로, DES 교재의 표준 예제와 정확히 일치한다.
assert permuted.hex().upper() == "CC00CCFFF0AAF0AA", "IP 구현이 표준과 다름!"
print("IP 재현 결과가 표준 예제와 일치 - DES의 첫 단계(IP)를 직접 재현함")
```
실행하면 다음과 같이 나온다(실행 확인함):
```text
원본 블록  : 0123456789abcdef
IP 적용 후 : cc00ccfff0aaf0aa
IP 재현 결과가 표준 예제와 일치 - DES의 첫 단계(IP)를 직접 재현함
```
같은 방식으로 S-box 8개도 파이썬 리스트로 옮겨두면, 라운드 함수 `f(R, K)`까지 이어서 순수 파이썬으로 완전한 DES를 재구현할 수 있다.

## 관련 글
- [rev-0211-aes-fingerprints.md](./rev-0211-aes-fingerprints.md) — 16바이트 블록 암호(AES)와의 대비
- [rev-0209-crc-fingerprints.md](./rev-0209-crc-fingerprints.md) — 256개짜리 큰 테이블(CRC)과 DES S-box(8개, 4×16)의 크기 차이
- [rev-0219-bruteforce-feasibility.md](./rev-0219-bruteforce-feasibility.md) — 56비트 키공간 브루트포스 가능성 판단
- REV-0900 — RC4 알고리즘 흔적(KSA/PRGA) 알아보기
- [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md) — 검증 로직을 파이썬으로 재현하는 법

## 출처/검증
- DES Initial Permutation 테이블, S-box(S1~S8) 값, Feistel 구조, 키 스케줄: FIPS 46-3, "Data Encryption Standard (DES)" 원표준 정의 기준 (2026-09-09 검증).
- 3DES EDE(Encrypt-Decrypt-Encrypt) 구성 방식과 2-key/3-key 변형: NIST SP 800-67("Recommendation for the Triple Data Encryption Algorithm (TDEA) Block Cipher") 기준 (2026-09-09 확인).
- pycryptodome `DES`/`DES3` 모듈 동작: PyCryptodome 공식 문서 기준 (2026-09-09).
