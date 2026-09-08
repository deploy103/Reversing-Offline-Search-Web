---
id: REV-0213
title: "Hex 인코딩 검증 패턴"
slug: "rev-0213-hex-encoding-pattern"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["hex encoding", "%02x", "0123456789abcdef", "nibble", "hex decode", "ASCII hex", "니블 분리"]
aliases: ["hex 상수", "%02x가 뭐임", "니블 분리 패턴", "16진수 문자열 변환"]
symptom_keywords: ["문자열 길이가 정확히 2배로 늘어남", "0123456789abcdef 테이블이 보임", "shr 4 and f 패턴이 보임", "02x 포맷 문자열이 보임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
입력 길이가 정확히 2배로 늘어나는 변환이 있고, `.rodata`에 `"0123456789abcdef"`(16바이트) 테이블이나 문자열 `"%02x"`가 보이면 Hex(16진수 ASCII) 인코딩/디코딩이다 — 인코딩 계열 중 가장 단순하고 항상 역산 가능하다.

## 언제 검색해야 하나
- 검증 함수가 `strlen(input) == 2 * N` 같은 정확히 2배 길이 조건을 체크할 때
- 문자열 창에서 `%02x` 또는 `%02X` 포맷 문자열을 발견했을 때
- rodata에 16바이트짜리 `"0123456789abcdef"` 또는 `"0123456789ABCDEF"` 테이블이 있을 때
- 디컴파일 코드에서 `>> 4`와 `& 0xF`가 짝지어 나오는데 곱셈이나 복잡한 시프트 조합은 없을 때(Base64처럼 6비트가 아니라 4비트/니블 단위)

## 핵심 개념
Hex 인코딩은 1바이트를 2개의 ASCII 문자로 표현하는 가장 단순한 인코딩이다. 한 바이트를 상위 4비트(하이 니블)와 하위 4비트(로우 니블)로 나누고, 각각을 `0-9, a-f`(또는 대문자 `A-F`) 중 하나의 문자로 매핑한다. Base64(REV-0212)가 3바이트를 6비트씩 4조각으로 나누는 것과 대비되게, Hex 인코딩은 **1바이트를 4비트씩 2조각**으로 나눈다는 점이 구조적 차이다.

**구현 방식 1 — `sprintf` 계열 (가장 흔함)**

```c
sprintf(dst + i*2, "%02x", src[i]);
```
`%02x`(또는 `%02X`) 포맷 문자열이 바이너리에 그대로 남아있는 경우가 많아서, 문자열 검색만으로 바로 알고리즘을 특정할 수 있는 가장 쉬운 케이스다.

**구현 방식 2 — 수동 니블 분리 + 테이블 조회**

```c
const char *hexchars = "0123456789abcdef";
dst[i*2]   = hexchars[(src[i] >> 4) & 0xF];
dst[i*2+1] = hexchars[src[i] & 0xF];
```
상위 니블은 `>> 4` 후 `& 0xF`(사실 `>>4`만으로 이미 0~15 범위지만 안전하게 마스킹하는 구현도 많다), 하위 니블은 시프트 없이 `& 0xF`만 적용한다. 이 두 값을 16바이트 테이블에 인덱싱한다.

**디코딩(문자열 → 바이트) 판별 로직**

디코딩은 반대로 각 문자를 0~15 값으로 되돌려야 한다. 숫자(`'0'-'9'`)는 아스키 코드에서 `'0'`(0x30)을 빼면 되지만, 문자(`'a'-'f'`/`'A'-'F'`)는 `'a'-10`(0x57) 또는 `'A'-10`(0x37)을 빼야 한다. 이 두 경로를 나누려면 반드시 **분기(비교+점프)** 가 필요하다:
```c
int hex_val(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1; // invalid
}
```
어셈블리에서 `cmp al, 39h`(`'9'`) 뒤에 `jle`/`ja`로 갈라지는 분기가 있으면 이 수동 판별 로직이고, 반대로 분기 없이 곧장 인덱싱 테이블을 참조한다면 인코딩(디코딩이 아니라) 쪽 코드다 — **분기의 유무가 인코딩과 디코딩을 구분하는 좋은 단서**다.

**API 흔적 — Windows `CryptBinaryToStringA`/`CryptStringToBinaryA`**

직접 니블 분리 코드를 짜지 않고 Windows API를 그대로 호출하는 바이너리도 있다. `CryptBinaryToStringA(data, len, CRYPT_STRING_HEXASCII, ...)` 같은 임포트가 보이면 API가 대신 hex 인코딩을 해주는 것이고, 반대로 `CryptStringToBinaryA(..., CRYPT_STRING_HEX, ...)`는 hex 디코딩을 해준다. IDA의 Imports 창(`Ctrl+Alt+I` 또는 View → Open subviews → Imports)에서 이 함수 이름이 보이면, 직접 니블 연산을 찾을 필요 없이 바로 이 API 호출부의 인자(데이터 포인터, 길이, 플래그)만 읽으면 된다 — REV-0211에서 다룬 AES API 흔적 찾기와 동일한 접근 방식이다.

**컴파일러가 `strlen` 호출을 인라인하는 경우**

REV-0218에서 다루듯 길이 검증은 보통 `call strlen` 형태지만, 최적화가 걸린 바이너리에서는 컴파일러가 `strlen`을 별도 함수 호출 없이 직접 루프(널 바이트를 만날 때까지 `cmp byte [rax], 0` / `jne`로 순회)로 풀어써버리는 경우가 있다. Hex 인코딩/디코딩 함수 앞에서 `call strlen`이 안 보이더라도, 짧은 바이트 스캔 루프가 먼저 나온다면 그게 인라인된 길이 계산일 수 있으니 놓치지 않아야 한다.

## 화면/코드에서 보이는 징후
- 문자열 창에 `%02x` 또는 `%02X`
- `.rodata`에 16바이트 `"0123456789abcdef"`
- `shr al, 4` 바로 뒤에 `and al, 0Fh`, 그리고 별도로 `and cl, 0Fh`(시프트 없음)가 나란히 있음
- 디코딩 쪽에서는 `cmp al, 39h`, `jle`/`ja` 같은 범위 분기가 반복
- 출력 버퍼 길이가 입력의 정확히 2배

## 가장 먼저 할 것
문자열 창(`Shift+F12`)에서 `%02x`를 검색한다. 있으면 바로 그 문자열의 Xref를 따라가 `sprintf`/`snprintf` 호출부를 찾으면 끝이다. 없으면 16바이트짜리 `0123456789abcdef` 테이블을 rodata에서 찾는다.

## 단계별 절차

**1) 포맷 문자열 검색**

IDA `Shift+F12` → `%02x` 또는 `%02X` 검색. 발견하면 그 문자열을 참조하는 함수(Xref, `X` 단축키)로 이동해서 몇 바이트를 몇 번 반복 처리하는지 루프 카운터를 확인.

**2) 테이블 검색**

포맷 문자열이 없으면 Hex View에서 `30 31 32 33 34 35 36 37 38 39 61 62 63 64 65 66`(아스키로 `0123456789abcdef`) 검색.

**3) 인코딩/디코딩 방향 판별**

바이트 배열을 문자열로 만들면 인코딩(길이 2배 증가), 문자열을 바이트 배열로 만들면 디코딩(길이 절반 감소). 분기(cmp+jle/ja)의 존재 여부로도 디코딩 여부를 교차 확인한다.

**4) 파이썬으로 재현**
```python
def hex_encode(data: bytes) -> str:
    return "".join(f"{b:02x}" for b in data)

def hex_decode(s: str) -> bytes:
    return bytes(int(s[i:i+2], 16) for i in range(0, len(s), 2))
```

**5) 실제 값으로 검증**
```python
assert hex_encode(b"flag") == "666c6167"
assert hex_decode("666c6167") == b"flag"

assert hex_encode(b"CTF") == "435446"
assert hex_decode("435446") == b"CTF"
```
'C'=0x43, 'T'=0x54, 'F'=0x46이므로 `"435446"`이 맞다는 걸 아스키 테이블로 직접 검산할 수 있다.

## 명령어/단축키
- IDA: `Shift+F12`(문자열 검색), `Alt+B`(바이너리 검색으로 `30 31 32 33` 시작 패턴)
- Linux: `strings ./binary | grep "%02x"`
- 파이썬 대조: `bytes.fromhex("666c6167")` → `b'flag'`, `b"flag".hex()` → `'666c6167'`

## 출력 해석
- `hex_decode` 결과 길이가 홀수 입력에서 에러가 나면, 원본 바이너리도 홀수 길이 입력을 애초에 거부하는 길이 검증을 먼저 하고 있을 가능성이 크다 — 검증 함수 앞부분에서 `strlen % 2 == 0` 체크를 찾아본다.
- 디코딩 결과에 `0xFF`나 음수 값이 섞여 나오면, `hex_val` 같은 판별 함수가 잘못된 문자에 대해 `-1`을 리턴하는데 이걸 `unsigned char`로 잘못 캐스팅해서 생기는 문제일 수 있다 — 원본 로직의 에러 처리 분기를 다시 확인한다.

## 흔한 실수
- 대문자/소문자 테이블을 헷갈리는 것 — `"0123456789abcdef"`와 `"0123456789ABCDEF"`는 인코딩 결과 대소문자만 다를 뿐 디코딩 로직에는 지장이 없지만(디코딩은 보통 대소문자 모두 받아들이게 짜여 있음), 정확한 비교 대상 상수와 대조할 때는 대소문자까지 정확히 맞춰야 한다.
- Base64(REV-0212)와 혼동해서 6비트 마스크(`0x3F`)를 기대하는 것 — Hex 인코딩은 4비트(`0xF`) 단위이므로 마스크 값부터 다르다.
- 상위 니블 계산에서 `>> 4`만 하고 `& 0xF`를 빠뜨려 상위 비트가 섞여 들어가는 것(부호 확장된 값을 시프트할 때 특히 주의) — `movzx`로 부호 없는 확장을 하는지, 시프트 후 마스킹을 하는지 반드시 확인한다.
- `CryptBinaryToStringA` 같은 API를 호출하면서 플래그 인자를 잘못 읽어 `CRYPT_STRING_HEXASCII`(줄바꿈 포함 hex+ASCII 덤프 형식)와 `CRYPT_STRING_HEX`(순수 hex만) 같은 비슷한 이름의 플래그를 혼동하는 것 — 실제로 출력 버퍼에 개행 문자가 섞여 나오는지 직접 확인해서 어떤 플래그인지 교차 검증한다.

## 막혔을 때 다음 체크
- 이 변환이 항상 역산 가능한 이유가 궁금하면 → [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md)에서 "정보 손실 없는 순수 재표현"이 왜 가장 쉬운 역산 케이스인지 확인.
- 3바이트↔4글자 구조의 좀 더 복잡한 인코딩이 궁금하면 → [rev-0212-base64-pattern.md](./rev-0212-base64-pattern.md).
- 테이블 자체를 식별하는 일반 기법이 필요하면 → [rev-0215-lookup-table-transform.md](./rev-0215-lookup-table-transform.md).

## 미니 예제
**예제 1 — 포맷 문자열로 즉시 식별**

문자열 창에서 다음을 발견했다:
```
"%02x"
```
Xref를 따라가니 다음과 같은 디컴파일 결과가 나왔다:
```c
for (int i = 0; i < len; i++) {
    sprintf(out + i * 2, "%02x", (unsigned char)input[i]);
}
```
루프 stride가 출력 쪽으로 2씩 증가하므로 인코딩이며, 5초 안에 알고리즘 전체를 특정할 수 있는 가장 쉬운 케이스다.

**예제 2 — 수동 니블 분리 코드**

포맷 문자열이 없는 다른 함수에서는 다음 디컴파일 결과를 봤다:
```c
const char *tbl = "0123456789abcdef";
for (int i = 0; i < len; i++) {
    out[i*2]   = tbl[(input[i] >> 4) & 0xF];
    out[i*2+1] = tbl[input[i] & 0xF];
}
```
`hex_encode(b"CTF")`을 파이썬으로 계산하면:
```python
>>> hex_encode(b"CTF")
'435446'
```
'C'(0x43)의 상위 니블 4, 하위 니블 3 → `tbl[4]='4'`, `tbl[3]='3'` → `"43"`. 'T'(0x54)는 상위 5, 하위 4 → `"54"`. 'F'(0x46)는 상위 4, 하위 6 → `"46"`. 합쳐서 `"435446"`, 파이썬 결과와 정확히 일치한다.

**예제 3 — 디코딩 분기 판별**

또 다른 함수에서는 분기가 많이 섞인 다음 코드를 봤다:
```c
int hex_val(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
```
`cmp al, 39h`(`'9'`=0x39), `jg`로 숫자 범위를 벗어나면 다음 분기로 넘어가는 패턴이 바로 이 코드가 컴파일된 형태다. `hex_decode("666c6167")`을 실행하면 `b"flag"`가 정확히 나오는지 검증해서 이 판별 로직의 이해가 맞았는지 확인한다.

## 관련 글
- [rev-0212-base64-pattern.md](./rev-0212-base64-pattern.md) — 6비트 단위로 확장한 인코딩
- [rev-0215-lookup-table-transform.md](./rev-0215-lookup-table-transform.md) — 룩업 테이블 일반 식별법
- [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) — 정보 손실 없는 재표현은 항상 역산 가능

## 출처/검증
- Hex(Base16) 인코딩 명세: IETF RFC 4648, "The Base16, Base32, and Base64 Data Encodings" — Base16 알파벳과 인코딩 규칙의 원출처 (2026-09-08 검증).
- `printf` 포맷 스펙 `%02x`: C 표준 라이브러리(ISO C11) `printf` 포맷 지정자 정의 (2026-09-08 검증).
