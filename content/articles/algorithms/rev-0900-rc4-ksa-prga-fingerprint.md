---
id: REV-0900
title: "RC4 알고리즘 흔적(KSA/PRGA) 알아보기"
slug: "rev-0900-rc4-ksa-prga-fingerprint"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["RC4", "ARC4", "ARCFOUR", "KSA", "PRGA", "256바이트 S박스", "스트림 암호", "키 스케줄링"]
aliases: ["rc4 상수", "rc4 흔적", "스트림 암호 흔적", "arcfour", "256개 순열 배열"]
symptom_keywords: ["0부터 255까지 채워진 배열이 있음", "swap S[i] S[j] 패턴이 보임", "j = j + S[i] + key 패턴이 보임", "출력이 키스트림과 XOR됨", "블록 크기 제약이 없는 암호화 함수"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
256개짜리 바이트 배열을 `0, 1, 2, ..., 255`로 초기화한 뒤 키를 이용해 뒤섞고(KSA), 이후 이 배열에서 인덱스를 두 개 굴려가며 한 바이트씩 키스트림을 뽑아 평문과 XOR하는(PRGA) 구조가 보이면 이는 RC4(ARC4/ARCFOUR)이며, DES/AES(REV-0899, REV-0211)처럼 고정 블록 크기가 없는 스트림 암호라는 점이 가장 큰 구조적 차이다.

## 언제 검색해야 하나
- 암호화/복호화 함수인데 입력 길이가 8바이트나 16바이트의 배수로 제약되지 않고 임의 길이를 그대로 처리할 때(블록 암호가 아니라는 신호)
- 256바이트 배열을 `for(i=0;i<256;i++) S[i]=i;`처럼 항등 순열로 초기화하는 코드를 봤을 때
- 그 직후 또 다른 256회 루프에서 `j = (j + S[i] + key[i % keylen]) % 256`과 `swap(S[i], S[j])`가 반복될 때
- 최종 출력 바이트가 `S[(S[i]+S[j]) % 256]`와 평문/암호문의 XOR로 계산될 때
- Import 목록에 `CryptImportKey`+`CALG_RC4`, OpenSSL `RC4()`/`RC4_set_key`, 또는 문자열 `"RC4"`/`"ARCFOUR"`가 있을 때

## 핵심 개념

### RC4가 다른 암호와 다른 점 — 스트림 암호
RC4(Rivest Cipher 4, 표준 명칭 논쟁으로 ARC4/ARCFOUR로도 불림)는 DES(REV-0899)나 AES(REV-0211) 같은 **블록 암호**가 아니라 **스트림 암호**다. 블록 암호는 8바이트, 16바이트처럼 고정된 크기 단위로만 데이터를 처리하지만, RC4는 키에서 유도한 의사난수 바이트 스트림(키스트림)을 평문과 같은 길이만큼 만들어서 그냥 XOR한다. 그래서 입력 길이에 아무 제약이 없고, 패딩 로직도 필요 없다는 게 코드상에서 가장 먼저 눈에 띄는 특징이다.

### 1단계 — KSA(Key Scheduling Algorithm)
RC4는 먼저 256바이트 크기의 상태 배열 S를 항등 순열(identity permutation)로 채운다:
```c
for (i = 0; i < 256; i++)
    S[i] = i;
```
그다음 키를 이용해 이 배열을 뒤섞는다:
```c
j = 0;
for (i = 0; i < 256; i++) {
    j = (j + S[i] + key[i % keylen]) % 256;
    swap(S[i], S[j]);
}
```
이 두 단계(항등 순열 초기화 → 키 기반 swap 뒤섞기)가 KSA다. 키가 짧으면 `i % keylen`으로 순환 재사용되며, 이 나머지 연산 패턴도 키 길이가 가변적임을 보여주는 힌트다. KSA가 끝나면 S 배열은 여전히 0~255의 순열이지만 순서가 키에 의존해 완전히 뒤바뀐 상태가 된다.

### 2단계 — PRGA(Pseudo-Random Generation Algorithm)
KSA로 만든 S 배열을 이용해 키스트림을 한 바이트씩 뽑아낸다:
```c
i = 0; j = 0;
for (n = 0; n < data_len; n++) {
    i = (i + 1) % 256;
    j = (j + S[i]) % 256;
    swap(S[i], S[j]);
    keystream_byte = S[(S[i] + S[j]) % 256];
    output[n] = input[n] ^ keystream_byte;
}
```
`i`를 1씩 증가시키고, `j`를 `S[i]`만큼 누적시키며, 매번 `S[i]`와 `S[j]`를 swap한 뒤 `S[(S[i]+S[j]) % 256]`를 키스트림 바이트로 뽑는 이 특정한 인덱스 조합(`S[(S[i]+S[j]) & 0xFF]`)이 RC4를 다른 스트림 암호(ChaCha20/Salsa20, REV-0901)와 구분하는 결정적 지문이다. 암호화와 복호화가 완전히 동일한 코드다 — XOR은 대칭 연산이므로 같은 키스트림을 다시 XOR하면 원래 값으로 돌아온다는 점도 눈여겨볼 부분이다.

### 왜 CTF에 자주 나오는가 — 그리고 왜 위험한가
RC4는 구현이 매우 짧고(수십 줄), 대칭적이라 암호화/복호화 함수를 하나로 재사용할 수 있어 임베디드/레거시/CTF 커스텀 암호 문제에 자주 쓰인다. 하지만 실제로는 여러 통계적 편향(키스트림 초반 바이트의 편향, 관련 키 공격 등)이 알려져 WEP, 초기 TLS 등에서 실제 공격으로 이어진 전례가 있다. CTF에서는 "키를 몰라도 평문의 일부를 알면(known plaintext) 그 부분의 키스트림을 복원해 나머지를 유추"하는 문제가 흔하다 — RC4는 키스트림만 알면 XOR 한 번으로 바로 복호화되기 때문이다.

### 블록 암호와의 구조적 대비
| 항목 | RC4(스트림 암호) | DES/AES(블록 암호) |
|---|---|---|
| 처리 단위 | 1바이트씩, 임의 길이 | 고정 블록(8/16바이트) |
| 패딩 필요 여부 | 불필요 | 필요(블록 정렬) |
| 암/복호화 코드 | 완전히 동일(XOR) | 대개 다르거나 역방향 라운드 |
| 내부 상태 | 256바이트 순열 배열 1개 | 라운드 키 배열, S-box |

### API/문자열 지문
- **Windows CryptoAPI**: `CryptImportKey`+`CALG_RC4`(`0x00006801`)
- **OpenSSL**: `RC4_set_key`, `RC4()` — 인자로 `RC4_KEY` 구조체(내부에 256바이트 배열 포함)
- **문자열**: `"RC4"`, `"ARCFOUR"`, `"ARC4"`

## 화면/코드에서 보이는 징후
- 256회 반복 루프로 배열을 `0..255` 순서로 채우는 초기화 코드
- 바로 이어지는 또 다른 256회 루프에서 `j += S[i] + key[i%len]`과 `swap`
- 메인 처리 루프에서 `i = (i+1) & 0xFF`, `j = (j+S[i]) & 0xFF`, `swap(S[i],S[j])`, `S[(S[i]+S[j]) & 0xFF]` 패턴
- 처리 대상 데이터 길이에 8/16 배수 같은 제약이 전혀 없음
- Import에 `CryptImportKey`+`CALG_RC4`, `RC4_set_key`, 문자열 `"RC4"`

## 가장 먼저 할 것
암호화 함수가 임의 길이 데이터를 처리하고 블록 정렬 코드가 전혀 없는지부터 확인한다. 맞다면 256바이트 배열 초기화 루프(`S[i]=i`)를 찾고, 그 아래 또 다른 256회 루프에서 `swap`이 나오는지 확인해 KSA를 확정한다.

## 단계별 절차
1. 처리 단위가 블록 크기 제약 없이 가변적인지 확인(블록 암호면 REV-0899/REV-0211로 이동)
2. IDA/Ghidra에서 256회 반복되는 `for` 루프 두 개가 연속으로 있는지 확인(첫 번째: 항등 초기화, 두 번째: 키 기반 swap)
3. 두 번째 루프에서 `% 256`(또는 `& 0xFF`) 연산과 `key[i % keylen]` 형태의 나머지 인덱싱이 있는지 확인
4. 메인 루프에서 `i`, `j` 두 인덱스가 각각 다르게 증가하고, `S[(S[i]+S[j]) & 0xFF]`로 출력 바이트를 뽑는지 확인
5. 출력이 입력과 단순 XOR로 결합되는지 확인(암호화/복호화 코드가 동일한지도 함께 확인)
6. Python으로 동일 키를 넣어 재현한 키스트림이 바이너리의 것과 일치하는지 검증

## 명령어/단축키
```bash
strings ./binary | grep -iE "rc4|arcfour|arc4"
objdump -d ./binary | grep -B3 -A3 "256\|0xff"
python3 -c "
def rc4(key, data):
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    i = j = 0
    out = bytearray()
    for byte in data:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(byte ^ S[(S[i] + S[j]) % 256])
    return bytes(out)

print(rc4(b'Key', b'Plaintext').hex())
"
```

## 출력 해석
- 위 예제 `rc4(b"Key", b"Plaintext")`는 잘 알려진 RC4 참조 예제로, 결과는 `bbf316e8d940af0ad3`가 나와야 한다 — 재현 코드가 맞는지 이 값으로 먼저 검증한다.
- 암호문을 복호화했는데 결과가 깨진 바이트라면 키 길이나 키 자체가 틀렸을 가능성이 크다 — RC4는 대칭이라 로직 자체를 잘못 구현했을 확률은 낮고, 대부분 키/오프셋 문제다.
- 일부 구현은 키스트림 앞부분(예: 첫 256바이트, "RC4-drop")을 버리고 쓰는 경우가 있으니, 재현 결과가 계속 안 맞으면 키스트림을 몇 바이트 건너뛰고 XOR해보는 것도 시도해볼 만하다.

## 흔한 실수
- RC4를 블록 암호처럼 취급해서 입력을 8/16바이트로 잘라 처리하려는 것 — RC4는 블록 개념이 없는 스트림 암호다.
- KSA와 PRGA를 헷갈려서, 키를 섞는 256회 루프(KSA)를 실제 암호화 루프(PRGA)로 착각해 잘못된 위치에서 키스트림을 추출하려는 것.
- 두 인덱스 `i`, `j`의 증가 방식을 혼동하는 것 — `i`는 항상 +1씩 단순 증가, `j`는 `S[i]` 값에 의존해 누적된다는 차이를 놓치면 재현 결과가 틀어진다.
- known-plaintext로 키스트림 일부를 복원했을 때, 그 키스트림이 "이 특정 오프셋에서만" 유효하다는 걸 잊고 다른 위치의 암호문에 그대로 재사용하는 것 — RC4 키스트림은 위치(오프셋)마다 다른 값이다.

## 막혔을 때 다음 체크
- 256바이트 순열 배열은 없고 4×4 워드 상태와 "expand" 계열 상수가 보인다면 → REV-0901 ChaCha20/Salsa20 상수(expand 32-byte k) 알아보기
- 처리 단위가 고정 블록(8/16바이트)이라면 → [rev-0211-aes-fingerprints.md](./rev-0211-aes-fingerprints.md) 또는 REV-0899 DES/3DES 상수와 S-Box 흔적 알아보기
- 평문 일부를 알고 있어서 키 없이 나머지를 복원하려면 → [rev-0223-known-plaintext-narrowing.md](./rev-0223-known-plaintext-narrowing.md)
- 검증 로직을 파이썬으로 재현하는 일반적 방법은 → [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md)

## 미니 예제
IDA 디컴파일 결과에서 다음 코드를 발견했다:
```c
for (i = 0; i < 256; i++) S[i] = i;
j = 0;
for (i = 0; i < 256; i++) {
    j = (j + S[i] + key[i % keylen]) & 0xFF;
    tmp = S[i]; S[i] = S[j]; S[j] = tmp;
}
i = 0; j = 0;
for (n = 0; n < len; n++) {
    i = (i + 1) & 0xFF;
    j = (j + S[i]) & 0xFF;
    tmp = S[i]; S[i] = S[j]; S[j] = tmp;
    out[n] = in[n] ^ S[(S[i] + S[j]) & 0xFF];
}
```
256회 초기화 루프, `key[i % keylen]` 나머지 인덱싱, 그리고 `S[(S[i]+S[j]) & 0xFF]` 출력 공식까지 정확히 일치하므로 RC4로 확정된다. Python 참조 구현으로 검증한 결과가 바이너리의 출력과 바이트 단위로 일치하면 키와 알고리즘이 모두 확정된 것이다.

## 관련 글
- REV-0901 — ChaCha20/Salsa20 상수(expand 32-byte k) 알아보기
- [rev-0211-aes-fingerprints.md](./rev-0211-aes-fingerprints.md) — 블록 암호(AES)와 스트림 암호(RC4)의 구조적 대비
- REV-0899 — DES/3DES 상수와 S-Box 흔적 알아보기
- [rev-0223-known-plaintext-narrowing.md](./rev-0223-known-plaintext-narrowing.md) — known plaintext로 키스트림 복원하기
- [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md) — 검증 로직을 파이썬으로 재현하는 법

## 출처/검증
- RC4 KSA/PRGA 알고리즘 정의와 인덱스 갱신 공식: 공개적으로 널리 검증된 RC4(ARCFOUR) 참조 구현 및 다수의 암호학 교재 기술 기준 (2026-09-09 검증).
- RC4 참조 테스트 벡터(`key="Key"`, `plaintext="Plaintext"` → `bbf316e8d940af0ad3`): 공개적으로 널리 알려진 RC4 표준 테스트 벡터 기준 (2026-09-09 확인).
- RC4의 통계적 편향 및 실제 공격 사례(WEP 등): 일반적으로 알려진 RC4 암호 분석 문헌 기준 (2026-09-09).
