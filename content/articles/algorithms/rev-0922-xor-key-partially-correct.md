---
id: REV-0922
title: "XOR 키를 구했는데 일부만 맞을 때"
slug: "rev-0922-xor-key-partially-correct"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["XOR 키 복구", "known plaintext", "반복 키 길이", "key length mismatch", "부분적으로만 맞는 키"]
aliases: ["XOR 키가 반만 맞음", "복호화가 일부만 됨", "키 길이를 잘못 추정함", "크립 공격 부분 실패"]
symptom_keywords: ["복호화했더니 일부 글자만 맞음", "특정 자리마다 계속 틀림", "키 일부만 알아냄", "반복 주기로 틀린 자리가 보임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
반복 XOR 키를 known-plaintext(크립)로 복구했는데 복호화 결과가 "군데군데만" 맞는다면, 거의 항상 **크립으로 확보한 구간이 실제 키 길이보다 짧아서 키의 일부 바이트만 복구됐거나, 키 길이 자체를 잘못 추정한 것**이다 — 틀린 자리가 무작위가 아니라 일정한 간격(주기)으로 반복된다는 게 이 문제의 핵심 증거다.

## 언제 검색해야 하나
- known-plaintext(예: 알고 있는 파일 헤더, `"flag{"` 접두사)로 XOR 키를 역산했는데, 복호화 결과의 앞부분만 맞고 뒷부분은 깨질 때
- 복호화 결과에서 몇 글자마다 한 번씩 규칙적으로 이상한 문자가 나올 때
- 키 길이를 추정해서 썼는데 그 길이가 맞는지 확신이 안 설 때
- Vigenère류 반복 키 암호(단순 반복 XOR도 본질적으로 동일)를 다룰 때

## 핵심 개념
반복 XOR 암호화는 `ciphertext[i] = plaintext[i] ^ key[i % keylen]`으로 동작한다. 이를 역산할 때는 `key[i % keylen] = ciphertext[i] ^ plaintext[i]`를 쓰는데, 문제는 **평문을 아는 구간(크립)이 키 전체 길이보다 짧을 때**다. 예를 들어 키 길이가 8인데 크립으로 앞 5바이트의 평문만 안다면, `key[0]`부터 `key[4]`까지는 정확히 복구되지만 `key[5]`, `key[6]`, `key[7]`은 전혀 알 수 없다. 이 상태에서 그 미지의 3바이트를 0이나 임의값으로 채워 전체를 복호화하면, 암호문 전체에서 인덱스가 `i % 8 == 5, 6, 7`인 위치들만 계속 틀리고 나머지(`i % 8 == 0..4`)는 정확히 맞는, 정확히 8바이트 주기로 반복되는 오류 패턴이 나타난다.

또 다른 흔한 원인은 **키 길이 추정 자체가 틀린 경우**다. 실제 키 길이가 8인데 4로 잘못 추정하고 크립 8바이트로 "키"를 복구하면, 사실은 `key[0..3]`과 `key[4..7]`이 다른데도 이를 길이 4인 하나의 키로 착각해서 반복시키게 된다. 이 경우 복호화 결과는 4바이트 주기로 "맞았다 틀렸다"가 아니라, 크립 구간 밖에서는 두 개의 서로 다른 4바이트 조각이 번갈아 섞이는 형태로 나타나 패턴이 좀 더 복잡해 보일 수 있다.

**키 길이를 모를 때 추정하는 법**: 암호문을 자기 자신과 여러 오프셋만큼 XOR해서(`ciphertext[i] ^ ciphertext[i+n]`), 이는 `plaintext[i] ^ plaintext[i+n] ^ key[i%n] ^ key[(i+n)%n]`이 되는데 `n`이 실제 키 길이의 배수이면 뒤의 두 키 항이 상쇄되어 `plaintext[i] ^ plaintext[i+n]`만 남는다. 평문이 사람이 읽는 텍스트라면 이 결과에 아스키 출력 가능 문자 비율이 높아지는 `n`을 후보 키 길이로 고른다(고전적인 Kasiski/반복도 검사와 같은 원리).

## 화면/코드에서 보이는 징후
- 복호화 결과 문자열에서 몇 글자는 정상 텍스트인데 일정 간격으로 깨진 바이트(`0x00`, 제어문자, 비ASCII)가 섞여 나옴
- 복호화 결과를 8/16/32 등 후보 길이로 줄 바꿔서 세로로 늘어놓아 보면, 특정 "열(column)"만 전부 깨져 있고 나머지 열은 멀쩡함

## 가장 먼저 할 것
복호화 결과에서 틀린 바이트의 인덱스를 전부 나열하고, 그 인덱스들 사이의 간격이 일정한지부터 확인한다. 일정한 주기가 보인다면 그 주기가 곧 실제 키 길이이고, 크립 구간이 그 길이를 다 덮지 못했다는 뜻이다.

## 단계별 절차

**1) 크립으로 부분 키 복구**
```python
cipher = bytes.fromhex("1f2e3d4c5b6a79880011223344556677")
crib   = b"flag{"          # 알고 있는 평문 5바이트

partial_key = bytes(c ^ p for c, p in zip(cipher, crib))
print(partial_key.hex())   # 앞 5바이트만 신뢰 가능
```

**2) 틀린 자리의 주기 확인**

키 길이를 8로 가정하고 나머지 3바이트를 0으로 채운 뒤 전체를 복호화하고, 아스키로 이상해 보이는 바이트의 인덱스를 모은다.
```python
guess_key = partial_key + b"\x00\x00\x00"   # 5바이트 + 미지 3바이트(임시로 0)
plain = bytes(c ^ guess_key[i % 8] for i, c in enumerate(cipher))
bad_idx = [i for i, b in enumerate(plain) if b < 0x20 or b > 0x7e]
print(bad_idx)   # 예: [5, 6, 7, 13, 14, 15, ...] -> 8 간격 반복
```
`bad_idx`가 `i % 8 in {5, 6, 7}`인 자리에서만 나온다면, 키 길이 8 자체는 맞고 단지 크립이 그 부분을 못 덮었을 뿐이라는 확증이다.

**3) 부족한 키 바이트를 다른 위치의 크립으로 보강**

암호문 뒷부분에도 추정 가능한 평문(예: 알려진 포맷의 구분자, 반복되는 구조)이 있다면 그 구간으로 `key[5]`, `key[6]`, `key[7]`을 추가로 복구한다. 크립이 더 없다면 그 3바이트는 남은 문자셋 안에서 브루트포스해야 한다.

**4) 완성된 키로 전체 재검증**

키 8바이트가 모두 채워지면 전체 암호문을 복호화해서 사람이 읽을 수 있는 텍스트가 끝까지 나오는지 확인한다.

## 명령어/단축키
```python
def xor_repeat(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

def guess_keylen(cipher: bytes, max_len=32):
    best = None
    for n in range(1, max_len + 1):
        shifted = bytes(a ^ b for a, b in zip(cipher, cipher[n:]))
        printable = sum(0x20 <= c <= 0x7e for c in shifted)
        score = printable / max(1, len(shifted))
        if best is None or score > best[1]:
            best = (n, score)
    return best
```

## 출력 해석
- 틀린 인덱스가 `키길이`의 배수 오프셋으로 정확히 반복되면 → 키 길이는 맞고 크립 구간 부족이 원인.
- 틀린 인덱스가 불규칙하거나 여러 주기가 섞여 보이면 → 키 길이 추정 자체가 틀렸을 가능성이 크므로 `guess_keylen`으로 다시 후보를 찾는다.
- `guess_keylen` 결과에서 점수가 특정 `n`과 그 배수(`2n`, `3n`...)에서 동시에 높게 나오면, 진짜 키 길이는 그중 가장 작은 `n`이다(배수는 항상 같이 높게 나오는 것이 정상).

## 흔한 실수
- 미지의 키 바이트를 0으로 채운 채로 "키를 다 구했다"고 착각하고 넘어가는 것 — 크립 길이와 키 길이가 같은지 반드시 확인해야 한다.
- 틀린 바이트가 몇 개 보인다고 해서 바로 "키가 통째로 틀렸다"고 결론짓고 처음부터 다시 크립 공격을 시도하는 것 — 먼저 틀린 인덱스의 주기부터 확인하면 이미 맞는 부분까지 버리지 않아도 된다.
- 키 길이를 추정할 때 실제 키 길이의 약수(예: 실제 8인데 4로 추정)에서도 그럴듯하게 맞아떨어져서 잘못된 길이로 확정하는 것 — 여러 후보 길이의 점수를 비교해서 가장 작은 진짜 주기를 찾아야 한다.
- 크립 자체가 틀린 경우(가정한 평문 접두사가 실제와 다름)를 의심하지 않는 것 — 크립을 바꿔가며 partial_key가 "그럴듯한 바이트 값"으로 나오는지도 함께 확인한다.

## 막혔을 때 다음 체크
- 나머지 키 바이트를 알아낼 크립이 전혀 없다면 → REV-0924 브루트포스를 돌렸는데 답이 안 나올 때(부족한 바이트만 좁혀서 브루트포스)
- 이 XOR이 사실은 반복 키가 아니라 인덱스에 따라 변하는 복잡한 변환이라면 → REV-0199 XOR 반복 변환 역산
- 애초에 이 연산이 역산 가능한 구조인지 다시 판단하고 싶다면 → REV-0221 역연산 가능한 알고리즘 판단법

## 미니 예제
암호문 16바이트, 실제 키 길이 8, 크립으로 앞 5바이트("Hello" 5글자)만 안다고 하자.
```python
cipher = bytes.fromhex("2c0a1d4a184e1a1a184e011a1a1a1a1a")
crib = b"Hello"
partial = bytes(c ^ p for c, p in zip(cipher, crib))
print(partial.hex())   # 앞 5바이트만 유효, 나머지 3바이트는 아직 모름

guess_key = partial + b"\x00" * 3
plain = xor_repeat(cipher, guess_key)
bad = [i for i, b in enumerate(plain) if not (0x20 <= b <= 0x7e)]
print(bad)   # 예: [5, 6, 7, 13, 14, 15] -> 8 간격 반복, 키 길이 8 확정
```
`bad` 리스트가 정확히 8 간격으로 반복되므로 키 길이 8은 확정이고, `key[5]`, `key[6]`, `key[7]` 세 바이트만 더 구하면 된다는 것이 명확해진다.

### 완전한 예제 스크립트 — 키를 직접 만들어서 암호화하고, 부분 크립으로 다시 복구해보기
이번에는 우리가 직접 키와 평문을 정해서 암호문을 만들고, 그 암호문을 마치 "처음 받은 문제"처럼 취급해서 크립 공격으로 다시 원래 키를 복구하는 전체 과정을 끝까지 실행해본다. 스스로 만든 예제라서 정답을 미리 알고 있으므로, 복구한 값이 정확히 맞는지 100% 확인할 수 있다.

```python
def xor_repeat(data: bytes, key: bytes) -> bytes:
    """반복 XOR: data의 각 바이트를 key[i % len(key)]와 XOR한다."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


# --- 문제를 만드는 단계 (실전에서는 이 부분을 우리가 볼 수 없다) ---
real_key = b"K3YB8YTE"                                   # 실제 키, 길이 8 (문제 출제자만 아는 값)
plaintext = b"Hello CTF player, welcome to rev wiki site!!"  # 원래 평문
cipher = xor_repeat(plaintext, real_key)                   # 암호문 생성
print("우리에게 주어진 암호문 (hex):", cipher.hex())

# --- 여기부터가 실전에서 우리가 실제로 하는 작업이다 ---

# 1) 크립(known-plaintext)으로 앞 5바이트만 안다고 가정: "Hello"
crib = b"Hello"
partial_key = bytes(c ^ p for c, p in zip(cipher, crib))
print("\n[1단계] 크립으로 복구한 부분 키 (앞 5바이트만 확실함):", partial_key)

# 2) 키 길이가 8이라고 이미 확인됐다고 가정하고(예: 버퍼 크기 등으로 REV-0218 방식 확인),
#    모르는 나머지 3바이트는 임시로 0x00으로 채워서 전체를 복호화해본다.
guess_key = partial_key + b"\x00" * 3
plain_partial = xor_repeat(cipher, guess_key)
print("[2단계] 부분 키로 복호화한 결과:", plain_partial)

# 3) 아스키 출력 가능 범위(0x20~0x7e)를 벗어나는 바이트의 인덱스를 모두 찾는다.
bad_idx = [i for i, b in enumerate(plain_partial) if not (0x20 <= b <= 0x7e)]
print("[3단계] 깨진 바이트의 인덱스:", bad_idx)
print("        8로 나눈 나머지(주기 확인):", sorted(set(i % 8 for i in bad_idx)))

# 4) 뒷부분에 " site!!"라는 문구가 있다는 걸 추가로 알아냈다고 가정하고(구조적 힌트),
#    그 구간으로 남은 키 바이트를 전부 채운다.
tail_crib = b" site!!"
tail_start = len(plaintext) - len(tail_crib)   # 이 크립이 시작하는 암호문 상의 위치
guess_key = bytearray(guess_key)                # 바이트를 하나씩 고칠 수 있도록 bytearray로 변환
for offset in range(tail_start, len(plaintext)):
    key_idx = offset % 8                         # 이 위치가 8바이트 키 중 몇 번째에 해당하는지 계산
    guess_key[key_idx] = cipher[offset] ^ tail_crib[offset - tail_start]  # 그 키 바이트를 확정
guess_key = bytes(guess_key)

print("\n[4단계] 완성된 전체 키:", guess_key)
print("        실제 키와 정확히 일치하는가?:", guess_key == real_key)

# 5) 완성된 키로 암호문 전체를 다시 복호화해서 처음부터 끝까지 정상적인 문장이 나오는지 확인
final_plain = xor_repeat(cipher, guess_key)
print("[5단계] 최종 복호화 결과:", final_plain)
print("        원래 평문과 정확히 일치하는가?:", final_plain == plaintext)
```

실제로 실행한 결과:
```
우리에게 주어진 암호문 (hex): 0356352e577917110d13292e5920313767132e27543a3b282e132d2d182b31336b4430295179272c3f567863

[1단계] 크립으로 복구한 부분 키 (앞 5바이트만 확실함): b'K3YB8'
[2단계] 부분 키로 복호화한 결과: b"Helloy\x17\x11F pla 17, wel:;(e to +13 wikiy',te!!"
[3단계] 깨진 바이트의 인덱스: [6, 7]
        8로 나눈 나머지(주기 확인): [6, 7]

[4단계] 완성된 전체 키: b'K3YB8YTE'
        실제 키와 정확히 일치하는가?: True
[5단계] 최종 복호화 결과: b'Hello CTF player, welcome to rev wiki site!!'
        원래 평문과 정확히 일치하는가?: True
```

이 실행에서는 깨진 바이트가 `i % 8 in {6, 7}`인 자리에서만 나타났다 — 이는 앞서 크립으로 확보한 5바이트(`key[0]`~`key[4]`)와 임시로 0으로 채운 3바이트(`key[5]`~`key[7]`) 중, 공교롭게도 `key[5]` 자리에 해당하는 바이트는 우연히 XOR 결과가 출력 가능한 문자 범위에 들어가서 "깨진 것처럼 보이지 않는" 경우였다(본문의 "흔한 실수"에서 경고한, 우연히 정상처럼 보이는 바이트가 실제로 존재할 수 있다는 사례를 그대로 보여준다). 그래서 `tail_crib`으로 `key[5]`, `key[6]`, `key[7]` 세 바이트를 한꺼번에 확정지었을 때 비로소 전체 키가 실제 키(`K3YB8YTE`)와 완벽하게 일치했다. 이처럼 "깨진 바이트만 보고 안전하다고 판단하지 말고, 가능한 모든 미지 바이트를 추가 크립으로 명시적으로 확정하는 것"이 실전에서 가장 안전한 절차다.

## 관련 글
- REV-0921 — 알고리즘을 복원했는데 출력이 원본과 안 맞을 때
- REV-0924 — 브루트포스를 돌렸는데 답이 안 나올 때
- REV-0199 — XOR 반복 변환 역산
- REV-0221 — 역연산 가능한 알고리즘 판단법
- REV-0223 — Known plaintext와 Flag 형식으로 조건 줄이기

## 출처/검증
- 반복 키 XOR의 known-plaintext 복구 및 키 길이 추정(자기 자신과의 오프셋 XOR 후 출력 가능 문자 비율 검사)은 고전 암호해독 기법인 Kasiski 검사와 동일한 원리를 다항 XOR 스트림 암호에 적용한 일반적인 CTF 관행을 정리한 것 (2026-09-09 확인).
