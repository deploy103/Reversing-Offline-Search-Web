---
id: REV-0212
title: "Base64 인코딩 검증 패턴"
slug: "rev-0212-base64-pattern"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["Base64", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", "0x3F", "6bit", "base64 table", "URL-safe base64", "패딩 문자 =="]
aliases: ["base64 상수", "이상한 64글자 문자열", "base64 테이블", "3바이트 4글자 인코딩"]
symptom_keywords: ["64글자짜리 문자열이 rodata에 있음", "3바이트씩 4바이트로 늘어남", "shr 2 and 3f 패턴이 보임", "= 패딩 문자가 붙음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
바이너리 안에 64글자짜리 문자열 상수(전형적으로 `ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/`)가 있고, 입력을 3바이트씩 묶어 4글자로 늘리면서 `>>2`, `&0x3F`, `<<4`, `<<6` 같은 6비트 단위 시프트가 보이면 Base64 인코딩/디코딩 루틴이다.

## 언제 검색해야 하나
- 출력 문자열 길이가 입력 길이의 약 4/3배(3바이트→4글자)로 늘어나는 함수를 봤을 때
- 결과 문자열 끝에 `=` 패딩이 0~2개 붙는 걸 봤을 때
- rodata에 64글자 정도의 알파벳+숫자+기호 문자열이 있는데 순서가 어딘가 익숙해 보일 때
- 디컴파일 코드에 `& 0x3F`(63)이라는 마스크가 반복적으로 등장할 때 — 6비트를 다루는 것의 강력한 힌트

## 핵심 개념
Base64는 이진 데이터를 인쇄 가능한 ASCII 문자로 표현하기 위한 인코딩이다. 원리는 단순하다: **입력 3바이트(24비트)를 6비트씩 4조각으로 잘라서**, 각 6비트 값(0~63)을 64글자 알파벳 테이블에 대응시킨다.

**표준 Base64 알파벳**
```
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
```
인덱스 0은 `A`, 25는 `Z`, 26은 `a`, 51은 `z`, 52는 `0`, 61은 `9`, 62는 `+`, 63은 `/`이다. URL-safe 변형은 마지막 두 글자만 `-`와 `_`로 바뀐다. 이 64바이트 문자열이 `.rodata`에 그대로 있으면 Base64로 거의 확정이다.

**패딩(`=`)**: 입력 길이가 3의 배수가 아니면 마지막 그룹을 0으로 채우고, 부족한 출력 글자 수만큼 `=`를 붙인다. 1바이트 남으면 `==`, 2바이트 남으면 `=`가 붙는다.

**비트 연산 패턴 (인코딩)**

3바이트를 4개의 6비트 인덱스로 쪼개는 공식은 다음과 같다:
```
idx0 = (byte0 >> 2) & 0x3F
idx1 = ((byte0 & 0x03) << 4) | ((byte1 >> 4) & 0x0F)
idx2 = ((byte1 & 0x0F) << 2) | ((byte2 >> 6) & 0x03)
idx3 = byte2 & 0x3F
```
디컴파일 결과에서 `>> 2`, `<< 4`, `<< 2`, `& 0x3F`, `& 0x0F`, `& 0x03`이 한 함수 안에 몰려 있으면 이 공식을 그대로 구현한 것이다. 반대로 디코딩은 4글자(각 6비트)를 3바이트(각 8비트)로 다시 합치는 역연산이며, 공식은 다음과 같다:
```
byte0 = (idx0 << 2) | (idx1 >> 4)
byte1 = ((idx1 & 0x0F) << 4) | (idx2 >> 2)
byte2 = ((idx2 & 0x03) << 6) | idx3
```
디코딩 구현은 유효하지 않은 문자를 걸러내기 위한 256바이트짜리 역방향 룩업 테이블(문자→0~63, 잘못된 문자는 -1이나 0x80 같은 특수값)을 쓰는 경우가 흔하다. 이 테이블은 인코딩용 64바이트 알파벳 테이블과는 별개의 상수이므로, `.rodata`에 64바이트 테이블과 256바이트 테이블이 함께 있다면 인코딩/디코딩 양쪽 로직이 모두 구현되어 있다는 뜻이다.

**Intel x64 인코딩 스니펫 예시**
```asm
movzx   eax, byte [rsi]        ; eax = byte0
mov     ecx, eax
shr     cl, 2                   ; cl = byte0 >> 2  (idx0)
movzx   ecx, byte [rcx+b64_table]
mov     [rdi], cl               ; out[0] = table[idx0]
and     eax, 3                  ; eax = byte0 & 0x03
shl     eax, 4
movzx   edx, byte [rsi+1]       ; byte1
mov     r8d, edx
shr     r8b, 4
or      eax, r8d                ; idx1
movzx   eax, byte [rax+b64_table]
mov     [rdi+1], al             ; out[1] = table[idx1]
```
`shr cl, 2` 뒤에 곧바로 테이블 인덱싱(`movzx ecx, byte [rcx+b64_table]`)이 이어지는 패턴이 반복적으로 나오면, 이게 바로 Base64 인코딩의 6비트 슬라이싱을 어셈블리 레벨에서 확인하는 방법이다.

## 화면/코드에서 보이는 징후
- `.rodata`에 있는 64바이트 문자열: `41 42 43 ... 5A 61 62 ... 7A 30 31 ... 39 2B 2F` (아스키로 `A-Za-z0-9+/`)
- `movzx eax, byte [rsi]` 뒤에 `shr al, 2`, 그다음 같은 테이블을 가리키는 `movzx eax, byte [rax+table_addr]`
- 디코딩 쪽에서는 `and eax, 3Fh` 직후 시프트-OR 조합으로 바이트 재조립
- 루프 stride가 인코딩은 입력 3 / 출력 4, 디코딩은 입력 4 / 출력 3

## 가장 먼저 할 것
`.rodata`/`.rdata`를 문자열 뷰(IDA `Shift+F12`)로 열어서 64자 내외의 문자열을 찾는다. 표준 알파벳 순서(`A-Z`, `a-z`, `0-9`, `+/`)와 정확히 일치하면 표준 Base64, 순서가 다르면 커스텀 알파벳(REV-0214)일 가능성을 함께 열어둔다.

## 단계별 절차

**1) 알파벳 테이블 확인**

문자열 창에서 64자 문자열을 찾아 실제로 `A`부터 순서대로 나열되어 있는지 육안으로 확인한다.

**2) 인코드/디코드 방향 판별**

함수가 바이트 배열을 문자열로 바꾸면(3→4 stride) 인코딩, 문자열을 바이트 배열로 바꾸면(4→3 stride) 디코딩이다.

**3) 비트 마스크 확인**

`& 0x3F`(63)가 있으면 6비트 단위 처리가 확실하다. IDA에서 상수 위에 커서를 놓고 `H`로 10진 표시하면 `63`으로 바로 확인된다.

**4) 파이썬으로 직접 구현해서 검증**

`base64` 표준 라이브러리를 쓰지 않고 직접 짜보면 비트 연산 이해가 바이너리 로직과 정확히 맞아떨어지는지 검증할 수 있다.
```python
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def b64_decode(s: str) -> bytes:
    s = s.rstrip("=")
    bits = "".join(f"{B64.index(c):06b}" for c in s)
    bits = bits[:len(bits) - (len(bits) % 8)]
    return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))

def b64_encode(data: bytes) -> str:
    bits = "".join(f"{b:08b}" for b in data)
    while len(bits) % 6:
        bits += "0"
    out = "".join(B64[int(bits[i:i+6], 2)] for i in range(0, len(bits), 6))
    while len(out) % 4:
        out += "="
    return out
```

**5) 실제 값으로 검증**
```python
assert b64_decode("aGVsbG8=") == b"hello"
assert b64_encode(b"hello") == "aGVsbG8="
```
`"aGVsbG8="`를 표준 `base64.b64decode`로도 확인해보면 정확히 `b"hello"`가 나오는 걸 알 수 있다.

## 명령어/단축키
- IDA: `Shift+F12`(문자열 창)에서 길이 60~64 정도로 필터링
- 파이썬 대조 검증: `import base64; base64.b64decode("aGVsbG8=")` → `b'hello'`
- IDA 상수 확인: `& 3Fh` 위에서 `H`로 10진 토글 → 63 확인

## 출력 해석
- 직접 구현한 `b64_decode` 결과가 파이썬 표준 `base64.b64decode`와 다르면, 테이블 순서가 표준과 다르거나(커스텀 알파벳) 패딩 처리 로직이 다를 수 있다.
- 결과 바이트가 사람이 읽을 수 없는 쓰레기 값이면, 애초에 Base64가 아니라 겉모습만 비슷한 다른 인코딩(Base32, Base85 등)일 수 있으니 알파벳 길이(정확히 64자인지)를 다시 확인한다.

## 흔한 실수
- 알파벳 테이블 문자열은 봤지만 순서를 확인하지 않고 표준 Base64로 단정하는 것 — CTF에서는 알파벳을 섞은 커스텀 Base64가 매우 흔하다(아래 참고).
- 패딩(`=`) 처리를 빼먹고 디코딩해서 길이가 안 맞는 것 — `rstrip("=")`을 반드시 먼저 하거나, 패딩 문자를 6비트 0으로 취급해서 마지막 그룹 처리를 정확히 한다.
- URL-safe 변형(`+/` 대신 `-_`)을 놓치고 표준 알파벳으로 디코딩을 시도해 실패하는 것 — 테이블의 마지막 두 글자를 반드시 확인한다.
- Base64를 다른 Base-N 인코딩과 혼동하는 것 — 알파벳 길이를 세어보면 쉽게 구분된다. **Base32**는 알파벳이 32자(`A-Z2-7`)이고 5바이트를 8글자로 늘리며 5비트 단위로 자른다(`& 0x1F` 마스크가 보이면 Base32 후보). **Base85/Ascii85**는 알파벳이 85자로 4바이트를 5글자로 압축한다(3바이트→4글자보다 압축률이 높음, 나눗셈/거듭제곱 85 연산이 특징). 정확히 64자 테이블 + `& 0x3F` 마스크 + 3:4 stride 세 가지가 함께 있어야 Base64로 확정할 수 있다.

## 막혔을 때 다음 체크
- 알파벳 순서가 표준과 다르면(예: `0123456789ABCDEF...`처럼 숫자가 앞에 오는 등) → [rev-0214-custom-alphabet-substitution.md](./rev-0214-custom-alphabet-substitution.md)에서 셔플된 알파벳 처리법 확인. 아래 미니 예제 2도 참고.
- 훨씬 단순한 1:2 비율 인코딩이면 → [rev-0213-hex-encoding-pattern.md](./rev-0213-hex-encoding-pattern.md).
- 이 인코딩 자체가 역산 가능한지 확신이 안 서면 → [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) (Base64는 정보 손실이 없는 순수 재표현이라 항상 역산 가능).

## 미니 예제
**예제 1 — 표준 Base64 확인**

`.rodata`에서 다음 문자열을 발견했다:
```
"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
```
정확히 표준 순서이므로 표준 Base64 테이블이다. `b64_decode("aGVsbG8=")`를 실행하면 `b"hello"`가 나온다 — 'h'=0x68='01101000', 'e'=0x65='01100101', ... 이 비트열을 6비트씩 자르면 `011010 000110 010101 101100 011011 000110 1111`(패딩 전)이 되고, 각 6비트 값이 알파벳 인덱스 26('a'), 22('W')... 등으로 대응하는 걸 직접 손으로 따라가 봐도 일치한다.

**예제 2 — 셔플된 커스텀 알파벳**

다른 문제에서는 `.rodata`에 다음과 같은 64자 문자열이 있었다:
```
"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz+/"
```
표준 알파벳과 글자 구성은 같지만 **숫자가 맨 앞으로 온** 순서다. 이건 여전히 Base64의 3→4 비트 패킹 구조를 그대로 쓰되, 알파벳 테이블만 바꾼 경우다. 앞의 `b64_decode` 함수에서 `B64` 변수만 이 문자열로 교체하면 그대로 동작한다:
```python
B64_SHUFFLED = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz+/"

def b64_decode_custom(s: str, table: str) -> bytes:
    s = s.rstrip("=")
    bits = "".join(f"{table.index(c):06b}" for c in s)
    bits = bits[:len(bits) - (len(bits) % 8)]
    return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))

print(b64_decode_custom("wMFVy2E=", B64_SHUFFLED))
```
즉 비트 패킹 로직(3바이트↔4글자, 6비트 마스크)은 절대 바뀌지 않고, 바뀌는 건 알파벳 매핑 테이블 하나뿐이라는 걸 기억하면 어떤 변형이 나와도 당황하지 않는다.

## 관련 글
- [rev-0213-hex-encoding-pattern.md](./rev-0213-hex-encoding-pattern.md) — 더 단순한 1바이트↔2글자 인코딩
- [rev-0214-custom-alphabet-substitution.md](./rev-0214-custom-alphabet-substitution.md) — 알파벳이 섞인 경우의 일반적 대응법
- [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) — 정보 손실 없는 재표현은 항상 역산 가능
- [rev-0208-fnv-16777619.md](./rev-0208-fnv-16777619.md) — 반대로 역산 불가능한 해시의 예

## 출처/검증
- Base64 인코딩 명세: IETF RFC 4648, "The Base16, Base32, and Base64 Data Encodings" — 알파벳 테이블, 패딩 규칙, URL-safe 변형의 원출처 (2026-09-08 검증).
- 표준 라이브러리 대조: Python 공식 문서 `base64` 모듈 (2026-09-08 검증).
