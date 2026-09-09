---
id: REV-0882
title: "AES S-Box/Rcon 상수 빠른 참조"
slug: "rev-0882-aes-sbox-rcon-reference"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["AES S-box", "AES Rcon", "63 7c 77 7b", "역S-box", "inverse s-box", "key expansion constant", "0x1B"]
aliases: ["aes sbox 표", "aes rcon 표", "aes 상수 전체", "역s박스 값"]
symptom_keywords: ["s박스 앞부분만 봤는데 나머지가 궁금함", "rcon 표가 필요함", "역s박스 값이 필요함", "키 확장 상수를 확인하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
REV-0211에서 AES 흔적을 처음 16바이트(`63 7C 77 7B ...`)로 식별했다면, 이 문서는 그 뒤를 잇는 **S-box 전체 256바이트, 역S-box, Rcon 테이블의 실제 값**을 바로 복사해서 쓸 수 있도록 정리한 빠른 참조표다.

## 언제 검색해야 하나
- AES S-box를 앞부분만 확인했고, 이제 직접 파이썬 구현체를 만들기 위해 256바이트 전체 값이 필요할 때
- 키 확장(key expansion) 루틴에서 Rcon 값을 몇 라운드까지 준비해야 하는지 헷갈릴 때
- 복호화 루틴을 만났는데 역S-box(Inverse S-box) 값을 몰라서 손으로 계산해야 하나 고민될 때
- IDA에서 뽑은 테이블이 표준 AES S-box와 정확히 일치하는지 바이트 단위로 대조해야 할 때

## 핵심 개념
AES S-box와 Rcon은 모두 표준(FIPS 197)에 고정된 값이며, 수학적으로는 GF(2^8) 유한체에서의 곱셈 역원(multiplicative inverse)과 아핀 변환(affine transformation)으로 유도되지만, 리버싱 실무에서는 **유도 공식을 몰라도 표만 그대로 베껴 쓰면 충분**하다.

**AES S-box 전체 256바이트 (16×16 표, 행=상위 니블, 열=하위 니블)**
```
    0   1   2   3   4   5   6   7   8   9   A   B   C   D   E   F
0  63  7C  77  7B  F2  6B  6F  C5  30  01  67  2B  FE  D7  AB  76
1  CA  82  C9  7D  FA  59  47  F0  AD  D4  A2  AF  9C  A4  72  C0
2  B7  FD  93  26  36  3F  F7  CC  34  A5  E5  F1  71  D8  31  15
3  04  C7  23  C3  18  96  05  9A  07  12  80  E2  EB  27  B2  75
4  09  83  2C  1A  1B  6E  5A  A0  52  3B  D6  B3  29  E3  2F  84
5  53  D1  00  ED  20  FC  B1  5B  6A  CB  BE  39  4A  4C  58  CF
6  D0  EF  AA  FB  43  4D  33  85  45  F9  02  7F  50  3C  9F  A8
7  51  A3  40  8F  92  9D  38  F5  BC  B6  DA  21  10  FF  F3  D2
8  CD  0C  13  EC  5F  97  44  17  C4  A7  7E  3D  64  5D  19  73
9  60  81  4F  DC  22  2A  90  88  46  EE  B8  14  DE  5E  0B  DB
A  E0  32  3A  0A  49  06  24  5C  C2  D3  AC  62  91  95  E4  79
B  E7  C8  37  6D  8D  D5  4E  A9  6C  56  F4  EA  65  7A  AE  08
C  BA  78  25  2E  1C  A6  B4  C6  E8  DD  74  1F  4B  BD  8B  8A
D  70  3E  B5  66  48  03  F6  0E  61  35  57  B9  86  C1  1D  9E
E  E1  F8  98  11  69  D9  8E  94  9B  1E  87  E9  CE  55  28  DF
F  8C  A1  89  0D  BF  E6  42  68  41  99  2D  0F  B0  54  BB  16
```
찾는 법: 입력 바이트가 `0x2C`라면 행 `2`, 열 `C`의 값 `71`이 치환 결과다.

**AES 역S-box(Inverse S-box) 전체 256바이트 — 복호화 전용**
```
    0   1   2   3   4   5   6   7   8   9   A   B   C   D   E   F
0  52  09  6A  D5  30  36  A5  38  BF  40  A3  9E  81  F3  D7  FB
1  7C  E3  39  82  9B  2F  FF  87  34  8E  43  44  C4  DE  E9  CB
2  54  7B  94  32  A6  C2  23  3D  EE  4C  95  0B  42  FA  C3  4E
3  08  2E  A1  66  28  D9  24  B2  76  5B  A2  49  6D  8B  D1  25
4  72  F8  F6  64  86  68  98  16  D4  A4  5C  CC  5D  65  B6  92
5  6C  70  48  50  FD  ED  B9  DA  5E  15  46  57  A7  8D  9D  84
6  90  D8  AB  00  8C  BC  D3  0A  F7  E4  58  05  B8  B3  45  06
7  D0  2C  1E  8F  CA  3F  0F  02  C1  AF  BD  03  01  13  8A  6B
8  3A  91  11  41  4F  67  DC  EA  97  F2  CF  CE  F0  B4  E6  73
9  96  AC  74  22  E7  AD  35  85  E2  F9  37  E8  1C  75  DF  6E
A  47  F1  1A  71  1D  29  C5  89  6F  B7  62  0E  AA  18  BE  1B
B  FC  56  3E  4B  C6  D2  79  20  9A  DB  C0  FE  78  CD  5A  F4
C  1F  DD  A8  33  88  07  C7  31  B1  12  10  59  27  80  EC  5F
D  60  51  7F  A9  19  B5  4A  0D  2D  E5  7A  9F  93  C9  9C  EF
E  A0  E0  3B  4D  AE  2A  F5  B0  C8  EB  BB  3C  83  53  99  61
F  17  2B  04  7E  BA  77  D6  26  E1  69  14  63  55  21  0C  7D
```

**Rcon(Round Constant) 테이블 — 키 확장 전용, AES-256 기준 14라운드까지**
| 라운드 | 값 (hex) |
|---|---|
| 1 | `01` |
| 2 | `02` |
| 3 | `04` |
| 4 | `08` |
| 5 | `10` |
| 6 | `20` |
| 7 | `40` |
| 8 | `80` |
| 9 | `1B` |
| 10 | `36` |
| 11 | `6C` |
| 12 | `D8` |
| 13 | `AB` |
| 14 | `4D` |

앞 8개는 단순히 2배씩 증가하지만, 9번째에서 `0x1B`로 값이 뚝 떨어지는 게 특징이다(2^8=256이 GF(2^8)의 기약다항식 `x^8+x^4+x^3+x+1`(`0x11B`)으로 축소된 결과). AES-128은 라운드 10까지, AES-192는 12까지, AES-256은 14까지만 Rcon이 필요하다.

## 화면/코드에서 보이는 징후
```c
static const uint8_t sbox[256] = {
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, /* ... */
};
static const uint8_t rcon[11] = {
    0x8d, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36
};
```
(일부 구현은 `rcon[0]`에 사용하지 않는 더미 값 `0x8d`를 넣어 인덱스를 1부터 시작하기도 한다 — 배열 크기가 10이 아니라 11이면 이 관례를 의심한다.)

## 가장 먼저 할 것
IDA에서 뽑은 256바이트 테이블을 위 S-box 표와 첫 32바이트만 먼저 바이트 단위로 대조한다. 정확히 일치하면 나머지도 표준이라고 신뢰하고 전체 표를 그대로 파이썬 코드에 붙여넣으면 된다.

## 단계별 절차
**1) 첫 16~32바이트 대조** — REV-0211에서 이미 확인한 `63 7C 77 7B ...`와 일치하는지 재확인.

**2) 암호화/복호화 구분** — S-box(`63 7C...`)면 암호화, 역S-box(`52 09 6A D5...`)면 복호화 루틴.

**3) Rcon 라운드 수로 키 길이 추정** — Rcon 배열이 10개까지만 있으면 AES-128, 12개면 AES-192, 14개면 AES-256일 가능성이 높다(REV-0211의 확장 키 버퍼 크기와 교차 검증).

**4) Python으로 표 전체를 상수화**
```python
SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    # ... 표 전체(256개)를 그대로 옮겨 담는다
]
RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36,0x6c,0xd8,0xab,0x4d]
```
직접 표를 새로 구현하기보다, 필요하면 `pycryptodome`의 `AES` 클래스를 그대로 사용하는 편이 실수를 줄인다(REV-0211 예제 참고). 이 표는 손으로 재구현하거나 IDA 덤프값을 검증할 때만 대조용으로 쓴다.

## 명령어/단축키
- IDA: `Alt+B`(바이너리 검색)로 `63 7C 77 7B` 검색 후, 이어지는 240바이트를 `Edit → Export data`로 한 번에 추출
- Python: `from Crypto.Cipher import AES` (표를 직접 구현할 필요 없이 라이브러리로 검증)

## 출력 해석
- IDA에서 덤프한 256바이트가 위 표와 한 바이트라도 다르면, 시작 주소를 잘못 잡았거나(오프셋 밀림) 표준이 아닌 커스텀 S-box(매우 드묾, 논커스텀 AES 변형)를 의심.
- Rcon 배열 길이가 10/12/14 중 하나와 맞지 않으면, 더미 값 포함 여부(인덱스 0부터 시작 vs 1부터 시작)를 다시 확인.

## 흔한 실수
- S-box와 역S-box를 헷갈려서 복호화 코드에 암호화용 표를 대입하는 것 — 두 표는 서로 다른 256바이트이며 절대 같지 않다(단, `inv_sbox[sbox[x]] == x` 관계는 성립).
- 이 표를 통째로 손으로 타이핑하다가 오탈자를 내는 것 — 가능하면 IDA/Ghidra에서 바이트 그대로 복사하거나, 표준 라이브러리(`pycryptodome`)를 사용해 표 자체를 아예 다룰 필요를 없애는 것이 안전하다.
- Rcon의 9번째 값이 `0x1B`로 "떨어진다"는 걸 모르고 계속 2배씩 증가한다고 잘못 계산해서 10라운드 이후 키 확장이 틀어지는 것.

## 막혔을 때 다음 체크
- AES 흔적을 처음 식별하는 단계라면 → REV-0211 — AES 테이블 또는 AES API 흔적 찾기.
- 이 표가 왜 필요한지, 어떤 구조의 치환 테이블 전반을 이해하려면 → REV-0215 — Lookup Table 기반 변환.
- AES 자체를 브루트포스로 깰 수 있는지 궁금하면 → REV-0219 — Brute Force가 가능한 입력 공간 계산.

## 미니 예제
표에서 `sbox[0x53] = 0xED`인지 확인해보자(행 `5`, 열 `3`). 위 표의 5행 `53 D1 00 ED 20 FC B1 5B 6A CB BE 39 4A 4C 58 CF`에서 인덱스 3(0부터 세어 네 번째)이 정확히 `ED`이므로 일치한다. 역방향도 성립해야 하므로 역S-box 표에서 `inv_sbox[0xED]`를 찾으면 다시 `0x53`이 나와야 한다 — 역S-box 표의 행 `E` `A0 E0 3B 4D AE 2A F5 B0 C8 EB BB 3C 83 53 99 61`에서 인덱스 `D`(0부터 세어 열네 번째)가 정확히 `53`이므로 `inv_sbox[0xED] = 0x53`이 성립함을 확인할 수 있다. 이런 식으로 두 표를 서로 교차 검증하면 덤프한 테이블이 정확한지 스스로 확인할 수 있다.

## 관련 글
- REV-0211 — AES 테이블 또는 AES API 흔적 찾기
- REV-0215 — Lookup Table 기반 변환
- REV-0219 — Brute Force가 가능한 입력 공간 계산
- REV-0221 — 역연산 가능한 알고리즘 판단법

## 출처/검증
- AES S-box, 역S-box, Rcon 전체 값: NIST FIPS 197, "Advanced Encryption Standard (AES)" 부록의 S-box/Rcon 표 기준 (2026-09-09 검증). 표 값은 GF(2^8) 곱셈 역원과 아핀 변환으로 직접 재계산하여 FIPS 197 공개 표와 일치함을 재확인.
- Rcon의 9번째 값이 `0x1B`인 이유(기약다항식 `x^8+x^4+x^3+x+1`에 의한 GF(2^8) 축소): FIPS 197 4.2절(유한체 곱셈) 기준.
