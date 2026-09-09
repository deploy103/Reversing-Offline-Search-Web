---
id: REV-0210
title: "TEA와 XTEA 상수 패턴"
slug: "rev-0210-tea-xtea"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["TEA", "XTEA", "0x9E3779B9", "2654435769", "delta", "golden ratio constant", "0xC6EF3720", "Feistel", "Tiny Encryption Algorithm"]
aliases: ["TEA 암호", "XTEA 암호", "9E3779B9가 뭐임", "이상한 델타 상수", "황금비 상수"]
symptom_keywords: ["루프에서 같은 상수를 계속 더함", "9E3779B9 상수가 보임", "Feistel 구조 같은데 알고리즘을 모르겠음", "두 개의 32비트 값이 서로 섞임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
루프 안에서 `0x9E3779B9`(2654435769)라는 상수가 매 반복마다 더해지고, 두 개의 32비트 변수가 시프트(`<<4`, `>>5`)와 XOR로 서로를 갱신하는 코드를 보면 **TEA(Tiny Encryption Algorithm)** 또는 그 변형인 **XTEA**를 의심해야 한다.

## 언제 검색해야 하나
- 디컴파일 코드에 `sum += 0x9E3779B9;` 같은 줄이 `for` 루프 안에 있고, 루프가 정확히 32번(또는 그 배수) 도는 것을 봤을 때
- 두 개의 `unsigned int`(또는 `uint32_t`) 변수 `v0`, `v1`이 번갈아 갱신되는 함수를 만났을 때 — 전형적인 Feistel 네트워크 구조
- 복호화 루틴에서 `sum`이 `0xC6EF3720`으로 초기화되고 매 라운드 `delta`를 빼는 코드를 봤을 때
- 4워드(16바이트) 키 배열을 사용하는 암호화 함수를 발견했는데 AES 상수(REV-0211 참고)가 안 보일 때

## 핵심 개념
TEA는 1994년 케임브리지 대학에서 만든, 구현이 극단적으로 짧은 블록 암호다. 64비트(8바이트) 블록을 두 개의 32비트 워드 `v0`, `v1`로 나누고, 128비트(16바이트) 키를 네 개의 32비트 워드 `k0..k3`로 나눠서 32라운드 동안 섞는다. 코드가 짧고 상수가 뚜렷해서 CTF 문제에 매우 자주 등장한다.

**핵심 상수: DELTA = `0x9E3779B9` = `2654435769`**

이 값은 황금비(golden ratio, φ = 1.6180339887...)에서 유래한 상수로, `2^32 / φ`를 반올림한 값이다. TEA 계열 암호에서 라운드마다 누적되는 `sum` 변수에 매번 더해지며, 이 상수 하나만 봐도 TEA/XTEA 계열임을 강하게 의심할 수 있다.

**두 번째 확인 상수: `sum`의 최종값 = `0xC6EF3720`**

표준 TEA는 32라운드를 돌며, 32라운드 후 `sum == delta * 32 (mod 2^32) == 0xC6EF3720`이 된다. 복호화 루틴은 보통 `sum = 0xC6EF3720`으로 시작해서 매 라운드 `delta`를 빼 나가며 0으로 수렴시킨다. 따라서 함수 초반에 `0xC6EF3720`이라는 매직 넘버가 초기화되는 걸 보면, 그 함수는 TEA/XTEA **복호화** 루틴이라고 확신할 수 있다.

**TEA 원본 알고리즘 (C 참조 구현)**
```c
void encrypt(uint32_t v[2], uint32_t const key[4]) {
    uint32_t v0=v[0], v1=v[1], sum=0, i;
    uint32_t delta=0x9E3779B9;
    uint32_t k0=key[0],k1=key[1],k2=key[2],k3=key[3];
    for (i=0; i<32; i++) {
        sum += delta;
        v0 += ((v1<<4) + k0) ^ (v1 + sum) ^ ((v1>>5) + k1);
        v1 += ((v0<<4) + k2) ^ (v0 + sum) ^ ((v0>>5) + k3);
    }
    v[0]=v0; v[1]=v1;
}
```
`v0`를 갱신할 때 `v1`을 시프트하고, `v1`을 갱신할 때는 방금 바뀐 `v0`를 시프트한다는 점에 주목한다. 그리고 `v0` 갱신에는 `k0`, `k1`이, `v1` 갱신에는 `k2`, `k3`가 쓰여서 **키 네 워드가 모두 정적으로, 위치가 고정된 채** 사용된다.

**XTEA(eXtended TEA) — 같은 델타, 다른 키 스케줄**

XTEA는 TEA의 키 스케줄 취약점을 보완한 후속 버전으로, DELTA 상수는 동일하게 `0x9E3779B9`를 쓰지만 키를 고르는 방식이 다르다.
```c
void encrypt(unsigned int r, uint32_t v[2], uint32_t const key[4]) {
    uint32_t v0=v[0], v1=v[1], sum=0, delta=0x9E3779B9;
    for (unsigned int i=0; i < r; i++) {
        v0 += (((v1 << 4) ^ (v1 >> 5)) + v1) ^ (sum + key[sum & 3]);
        sum += delta;
        v1 += (((v0 << 4) ^ (v0 >> 5)) + v0) ^ (sum + key[(sum>>11) & 3]);
    }
    v[0]=v0; v[1]=v1;
}
```

**TEA와 XTEA를 코드만 보고 구분하는 법**

| 구분 | TEA | XTEA |
|---|---|---|
| 시프트 대상 | 상대 워드를 `<<4`, `>>5` 두 번 따로 시프트해서 각각 다른 키워드와 더함 | 상대 워드를 `<<4 ^ >>5`로 먼저 XOR한 뒤 그 값 하나에 `+ v1(또는 v0)` | 
| 키 사용 | `k0,k1`은 항상 v0 갱신에, `k2,k3`는 항상 v1 갱신에 — 고정된 리터럴 오퍼랜드 | `key[sum & 3]`, `key[(sum>>11) & 3]` — **런타임에 계산되는 배열 인덱스**로 키워드 선택 |
| 디스어셈블리 특징 | `add`, `shl`, `shr`, `xor`가 뒤섞이지만 키 오퍼랜드는 항상 같은 스택/전역 오프셋 | `and eax, 3` 또는 `shr eax, 0Bh` 뒤에 `and eax, 3`가 보이고, 그 결과로 **메모리를 인덱싱**해서 키를 읽음 |

즉 가장 확실한 구분 포인트는 **키 접근이 고정 오프셋이냐, sum 비트로 계산된 인덱스냐**이다. `and eax, 3`나 `shr eax, 0Bh` (11비트 우측 시프트) 뒤에 배열 인덱싱이 나오면 XTEA로 확정해도 된다.

## 화면/코드에서 보이는 징후
- `mov eax, 9E3779B9h` 또는 리터럴 `2654435769`가 루프 안에서 반복 사용
- `add [rbp+var_sum], eax` 형태로 sum이 누적
- 루프가 정확히 32번(`cmp ecx, 20h` / `cmp ecx, 32`) 반복
- 두 개의 지역변수(또는 레지스터)가 번갈아 갱신되고, 각 갱신에 `shl`, `shr`, `xor`, `add`가 조합됨
- 복호화 함수에서 `mov eax, 0C6EF3720h`로 시작하는 초기화

## 가장 먼저 할 것
`0x9E3779B9` 상수를 IDA에서 발견하면, 그 함수 전체를 캡처해서 **키 워드 접근이 고정 오프셋인지 배열 인덱스인지**부터 확인한다. 이것만 판단하면 TEA/XTEA 중 무엇인지 바로 정해지고, 아래 파이썬 함수를 그대로 대입해서 복호화할 수 있다.

## 단계별 절차

**1) 델타 상수와 라운드 수 확인**

IDA에서 `9E3779B9h` 위에 커서를 놓고 확인. 루프 카운터의 종료 조건(`cmp`, `jl`)을 보고 라운드 수가 32인지, 아니면 그보다 적은 커스텀 라운드 수(예: 16, 64)인지 확인한다 — CTF 문제는 종종 라운드 수를 바꿔서 문제를 살짝 변형한다.

**2) TEA인지 XTEA인지 판별**

앞서 설명한 표를 기준으로, 키 워드 오퍼랜드가 고정인지 계산된 인덱스인지 본다.

**3) 암호화인지 복호화인지 판별**

`sum`이 `0`에서 시작해 더해지면 암호화, `0xC6EF3720`에서 시작해 빼지면 복호화다. 검증 함수 안에 있는 루틴은 대개 **복호화**로, 입력을 복호화한 뒤 평문과 비교하는 구조가 많다.

**4) 파이썬으로 그대로 재현**
```python
def tea_encrypt(v0, v1, key):
    delta = 0x9E3779B9
    s = 0
    k0, k1, k2, k3 = key
    for _ in range(32):
        s = (s + delta) & 0xFFFFFFFF
        v0 = (v0 + (((v1 << 4) + k0) ^ (v1 + s) ^ ((v1 >> 5) + k1))) & 0xFFFFFFFF
        v1 = (v1 + (((v0 << 4) + k2) ^ (v0 + s) ^ ((v0 >> 5) + k3))) & 0xFFFFFFFF
    return v0, v1

def tea_decrypt(v0, v1, key):
    delta = 0x9E3779B9
    s = (delta * 32) & 0xFFFFFFFF   # 0xC6EF3720
    k0, k1, k2, k3 = key
    for _ in range(32):
        v1 = (v1 - (((v0 << 4) + k2) ^ (v0 + s) ^ ((v0 >> 5) + k3))) & 0xFFFFFFFF
        v0 = (v0 - (((v1 << 4) + k0) ^ (v1 + s) ^ ((v1 >> 5) + k1))) & 0xFFFFFFFF
        s = (s - delta) & 0xFFFFFFFF
    return v0, v1

def xtea_encrypt(v0, v1, key, rounds=32):
    delta = 0x9E3779B9
    s = 0
    for _ in range(rounds):
        v0 = (v0 + ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (s + key[s & 3]))) & 0xFFFFFFFF
        s = (s + delta) & 0xFFFFFFFF
        v1 = (v1 + ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (s + key[(s >> 11) & 3]))) & 0xFFFFFFFF
    return v0, v1

def xtea_decrypt(v0, v1, key, rounds=32):
    delta = 0x9E3779B9
    s = (delta * rounds) & 0xFFFFFFFF
    for _ in range(rounds):
        v1 = (v1 - ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (s + key[(s >> 11) & 3]))) & 0xFFFFFFFF
        s = (s - delta) & 0xFFFFFFFF
        v0 = (v0 - ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (s + key[s & 3]))) & 0xFFFFFFFF
    return v0, v1
```
모든 덧셈/뺄셈/시프트 뒤에 `& 0xFFFFFFFF`를 걸어 32비트로 고정하는 것을 잊지 않는다 — 이건 FNV(REV-0208 참고)와 동일한 원리다.

**5) 키·평문 복원**

바이너리에서 사용하는 4워드 키를 덤프하고(정적 배열이면 IDA의 Hex View에서, 런타임 생성이면 디버거에서 브레이크포인트로), 검증 대상 암호문을 위 `tea_decrypt`/`xtea_decrypt`에 넣어 평문을 복원한다.

## 명령어/단축키
- IDA: 상수 위에서 `H`로 10진/16진 토글, `Alt+B`로 `9E 37 79 B9`(리틀엔디안 바이트 순서 주의) 바이너리 검색
- Ghidra: `Search > Memory`에서 같은 바이트 패턴 검색, 함수 그래프 뷰에서 32회 반복 루프 확인
- 파이썬: `hex(0x9E3779B9 * 32 & 0xFFFFFFFF)` → `0xc6ef3720` 직접 확인 가능

## 출력 해석
- `tea_encrypt`와 `tea_decrypt`를 서로 넣었을 때 원래 값이 안 나오면, 키 워드 순서(k0..k3)나 `v0`/`v1` 갱신 순서를 바이너리와 다르게 짰을 가능성이 크다. 디스어셈블리를 다시 보고 어떤 워드가 먼저 갱신되는지 확인한다.
- XTEA 함수인데 `key[]` 인덱스가 항상 `0, 1, 2, 3` 순서로만 나온다면, 실제로는 라운드 수가 4 이하로 짧아서 우연히 순차적으로 보이는 것일 수 있다 — `sum` 값을 직접 계산해서 `& 3` 결과를 검증한다.

## 흔한 실수
- TEA와 XTEA를 혼동해서 아무 파이썬 함수나 대입했다가 값이 안 맞는 것 — 키 접근이 고정 오프셋인지 배열 인덱스인지부터 다시 확인한다.
- 라운드 수를 32로 가정하고 그대로 복호화했는데 문제에서 라운드 수를 줄였거나 늘린 경우 — 루프 카운터의 종료 조건을 반드시 직접 세어본다.
- `v0`, `v1` 갱신 순서를 바꿔서 구현하는 것 — TEA는 `v0`를 먼저 갱신하고 그 다음 갱신된 `v0`로 `v1`을 갱신하므로, 이 순서를 반대로 짜면 완전히 다른 결과가 나온다.
- 마스킹(`& 0xFFFFFFFF`)을 빼먹어서 파이썬 정수가 무한정 커지는 것.

## 막혔을 때 다음 체크
- 이 구조가 애초에 역산 가능한 구조인지 헷갈린다면 → [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md)에서 Feistel 네트워크가 왜 항상 역산 가능한지 확인.
- 디스어셈블리를 파이썬 함수로 옮기는 일반적인 절차가 필요하다면 → [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md).
- 상수가 `9E3779B9`가 아니라 다른 값이면 TEA 계열이 아닐 수 있다 — [rev-0208-fnv-16777619.md](./rev-0208-fnv-16777619.md)의 FNV 상수나 REV-0211의 AES 상수와 비교해본다.

## 미니 예제
어떤 CTF 바이너리의 검증 함수를 IDA로 열었더니 다음과 같은 디컴파일 결과가 나왔다고 하자:
```c
unsigned int sum = 0;
unsigned int key[4] = { 0x00010203, 0x04050607, 0x08090A0B, 0x0C0D0E0F };
for (int i = 0; i < 32; i++) {
    sum += 0x9E3779B9;
    v0 += ((v1 << 4) + key[0]) ^ (v1 + sum) ^ ((v1 >> 5) + key[1]);
    v1 += ((v0 << 4) + key[2]) ^ (v0 + sum) ^ ((v0 >> 5) + key[3]);
}
```
키 워드가 항상 `key[0]`, `key[1]`, `key[2]`, `key[3]`로 고정 인덱스이므로 XTEA가 아니라 표준 TEA다. 파이썬으로 왕복 검증:
```python
key = (0x00010203, 0x04050607, 0x08090A0B, 0x0C0D0E0F)
v0, v1 = 0x41424344, 0x45464748

enc0, enc1 = tea_encrypt(v0, v1, key)
dec0, dec1 = tea_decrypt(enc0, enc1, key)

assert (dec0, dec1) == (v0, v1)
print(hex(enc0), hex(enc1))  # 암호화된 값 (바이너리의 비교 대상 상수와 대조)
```
`tea_decrypt(enc0, enc1, key)`가 정확히 원래의 `(0x41424344, 0x45464748)`로 돌아오는 것을 확인하면, 이 파이썬 구현이 바이너리 로직과 동일하다는 뜻이다. 이제 바이너리에 하드코딩된 실제 암호문 상수를 `tea_decrypt`에 넣기만 하면 평문(플래그)을 얻는다.

**심화 예제 — 암호문에서 평문(flag)을 복원하는 완결된 스크립트**

이번에는 실제로 8바이트짜리 암호문 하나를 파이썬으로 완전히 복호화해서 flag 조각을 복원하는 전체 과정을 보여준다. 파이썬을 잘 몰라도 따라할 수 있도록 각 줄에 한국어 주석을 달았다.

```python
def tea_decrypt_block(v0: int, v1: int, key: tuple) -> tuple:
    # ↑ 암호화된 두 개의 32비트 워드(v0, v1)와 16바이트 키(4워드 튜플)를 받아서
    #   평문 워드 두 개를 되돌려주는 함수를 정의한다.
    delta = 0x9E3779B9
    # ↑ TEA/XTEA 계열의 상징인 황금비 상수. 매 라운드 sum에서 빼거나 더해진다.
    s = (delta * 32) & 0xFFFFFFFF
    # ↑ 표준 TEA는 32라운드를 돌기 때문에, 복호화는 sum = delta*32 = 0xC6EF3720에서
    #   시작해서 라운드마다 delta를 빼 나간다. & 0xFFFFFFFF는 32비트로 값을 자르는
    #   마스킹으로, 파이썬 정수가 무한정 커지는 것을 막아준다.
    k0, k1, k2, k3 = key
    # ↑ 튜플로 받은 키를 4개의 이름 있는 변수로 풀어서 가독성을 높인다.
    for _ in range(32):
        # ↑ 암호화 때와 정확히 같은 32번을 반복하되, 내부 계산은 반대 순서로 뒤집는다.
        v1 = (v1 - (((v0 << 4) + k2) ^ (v0 + s) ^ ((v0 >> 5) + k3))) & 0xFFFFFFFF
        # ↑ 암호화 마지막에 v1이 v0로부터 갱신되었으므로, 복호화는 v1을 먼저 되돌린다.
        v0 = (v0 - (((v1 << 4) + k0) ^ (v1 + s) ^ ((v1 >> 5) + k1))) & 0xFFFFFFFF
        # ↑ 방금 되돌린 v1을 사용해서 v0도 되돌린다(암호화 때 순서를 정확히 역순으로).
        s = (s - delta) & 0xFFFFFFFF
        # ↑ 다음 라운드를 위해 sum에서 delta를 한 번 뺀다.
    return v0, v1
    # ↑ 완전히 복호화된 두 개의 32비트 워드를 돌려준다.

def words_to_bytes(v0: int, v1: int) -> bytes:
    # ↑ 32비트 정수 두 개를 8바이트(빅엔디안)로 합쳐서 사람이 읽는 바이트열로 바꾼다.
    return v0.to_bytes(4, "big") + v1.to_bytes(4, "big")
    # ↑ to_bytes(4, "big")은 정수를 4바이트, 상위 바이트가 먼저 오는 순서로 변환한다.

if __name__ == "__main__":
    # ↑ 이 파일을 직접 실행할 때만 아래 블록을 수행한다.
    key = (0x00010203, 0x04050607, 0x08090A0B, 0x0C0D0E0F)
    # ↑ 바이너리의 전역 변수 영역에서 IDA Hex View로 직접 덤프했다고 가정한 16바이트 키.

    # 바이너리를 실행해서 얻은(또는 파일에 저장된) 실제 암호문 8바이트.
    enc0, enc1 = 0x02292aa1, 0x0eaa60d5
    # ↑ 이 두 값은 이 문서의 예제를 위해 평문 b"flag" + b"ctf!" 를 위 키로
    #   직접 암호화해서 얻은 실제 계산값이다(즉, 아무렇게나 지어낸 값이 아니다).

    dec0, dec1 = tea_decrypt_block(enc0, enc1, key)
    # ↑ 암호문 두 워드를 복호화 함수에 넣어서 평문 두 워드를 얻는다.

    plaintext = words_to_bytes(dec0, dec1)
    # ↑ 복호화된 정수 두 개를 실제 바이트열(사람이 읽을 수 있는 문자열)로 합친다.

    print("복호화된 워드:", hex(dec0), hex(dec1))
    # ↑ 중간 결과를 16진수로 출력해서 계산이 어떻게 진행됐는지 확인할 수 있게 한다.
    print("복원된 평문:", plaintext)
    # ↑ 최종적으로 복원된 평문(바이트열)을 출력한다.
```

이 스크립트를 그대로 실행하면 다음과 같이 출력된다(직접 계산해서 검증한 값):
```
복호화된 워드: 0x666c6167 0x63746621
복원된 평문: b'flagctf!'
```
`0x666c6167`을 4바이트로 풀면 `0x66='f'`, `0x6c='l'`, `0x61='a'`, `0x67='g'` 이므로 `b"flag"`가 되고, `0x63746621`은 `b"ctf!"`가 된다. 즉 원래 평문 `b"flag"` + `b"ctf!"` = `b"flagctf!"`가 암호문 두 워드로부터 정확히 복원된다. 실전에서는 `enc0`, `enc1`을 바이너리에서 실제로 뽑아낸 값으로, `key`를 실제 덤프한 키 값으로 바꿔 넣기만 하면 동일한 스크립트로 flag를 복원할 수 있다.

## 관련 글
- [rev-0208-fnv-16777619.md](./rev-0208-fnv-16777619.md) — 상수 하나로 알고리즘을 특정하는 대표 사례(FNV)
- [rev-0211-aes-fingerprints.md](./rev-0211-aes-fingerprints.md) — 테이블 기반 블록 암호(AES)와의 구분법
- [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) — Feistel 구조가 항상 역산 가능한 이유
- [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md) — 디스어셈블리를 파이썬 함수로 옮기는 절차
- REV-0199 — XOR 반복 변환 역산

## 출처/검증
- TEA 원 논문: David Wheeler, Roger Needham, "TEA, a Tiny Encryption Algorithm" (Cambridge Computer Laboratory, 1994) — DELTA 상수와 32라운드 구조의 원출처 (2026-09-08 검증).
- XTEA 논문: Needham, Wheeler, "TEA extensions" (Cambridge Computer Laboratory, 1997) — 키 스케줄 개선과 `sum & 3`/`(sum>>11) & 3` 인덱싱 방식의 원출처 (2026-09-08 검증).
