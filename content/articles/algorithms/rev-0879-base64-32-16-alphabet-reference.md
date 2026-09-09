---
id: REV-0879
title: "Base64/Base32/Base16 알파벳 빠른 참조"
slug: "rev-0879-base64-32-16-alphabet-reference"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["Base64 알파벳", "Base32 알파벳", "Base16 알파벳", "RFC 4648", "A-Z2-7", "URL-safe base64", "base32hex"]
aliases: ["base64 base32 base16 차이", "인코딩 알파벳 길이 표", "rfc4648 알파벳"]
symptom_keywords: ["64글자 문자열이 있음", "32글자 문자열이 있음", "16글자 hex 문자열이 있음", "어떤 base인지 헷갈림"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
RFC 4648이 정의하는 Base64/Base32/Base16 인코딩은 알파벳 길이(64/32/16자)와 한 글자가 표현하는 비트 수(6/5/4비트)만 다를 뿐 원리는 동일하며, `.rodata`에서 발견한 문자열 테이블의 **글자 수를 세는 것만으로** 어떤 Base-N인지 즉시 구분할 수 있다.

## 언제 검색해야 하나
- `.rodata`/`.rdata`에 알파벳+숫자로 이루어진 문자열 상수가 있는데 Base64인지 Base32인지 헷갈릴 때
- 출력 문자열이 전부 대문자와 숫자 `2~7`로만 이루어져 있어서(소문자·`+`·`/` 없음) Base64가 아닌 것 같다고 느낄 때
- 순수 16진수 문자(`0-9A-F`)로만 된 출력이 있는데 이게 그냥 hex 인코딩인지 확인하고 싶을 때
- URL-safe 변형(`-`, `_`)이 섞여 있어서 표준 Base64 테이블과 매칭이 안 될 때

## 핵심 개념
세 인코딩 모두 "이진 데이터를 N비트씩 잘라서 인쇄 가능한 문자로 매핑"하는 동일한 원리를 쓴다. 차이는 **몇 비트씩 자르는가**와 **알파벳이 몇 글자인가**뿐이다.

| 구분 | 알파벳 크기 | 비트/문자 | 입력:출력 비율 | 패딩 |
|---|---|---|---|---|
| Base64 | 64자 | 6비트 | 3바이트 → 4글자 | `=` (0~2개) |
| Base32 | 32자 | 5비트 | 5바이트 → 8글자 | `=` (0~6개) |
| Base16(Hex) | 16자 | 4비트 | 1바이트 → 2글자 | 없음 |

**Base64 표준 알파벳 (RFC 4648 §4)**
```
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
```
인덱스: `A`=0, `Z`=25, `a`=26, `z`=51, `0`=52, `9`=61, `+`=62, `/`=63.

**Base64 URL-safe 변형 (RFC 4648 §5)** — 마지막 두 글자만 교체:
```
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_
```
`+`→`-`, `/`→`_`로 바뀐다. URL이나 파일명에 안전하게 쓰기 위한 변형으로, 파일 경로/쿠키/JWT 토큰에서 자주 보인다.

**Base32 표준 알파벳 (RFC 4648 §6)**
```
ABCDEFGHIJKLMNOPQRSTUVWXYZ234567
```
대문자 A-Z(0~25) 다음에 숫자 2~7(26~31)이 온다. **숫자 0, 1은 알파벳 O, I와 헷갈리기 쉬워 의도적으로 제외**된 것이 특징이다. case-insensitive(대소문자 구분 없음) 사용을 전제로 설계되었다.

**Base32 Extended Hex 변형(base32hex, RFC 4648 §7)**
```
0123456789ABCDEFGHIJKLMNOPQRSTUV
```
숫자 0-9 다음 A-V가 이어지는 방식으로, 정렬 순서가 원본 바이트 순서와 일치하는 특수 목적 변형이다(파일시스템 인덱스 등에서 간혹 사용).

**Base16(Hex) 알파벳 (RFC 4648 §8)**
```
0123456789ABCDEF
```
사실상 표준 16진수 표기와 같으며, `printf("%02X", byte)`로 만드는 흔한 hex 문자열 출력이 바로 이것이다. 대소문자 구분 없이(`0-9a-f`도 허용) 디코딩하는 구현이 많다.

## 화면/코드에서 보이는 징후
- **Base64**: `.rodata`에 64글자, 마스크 `& 0x3F`(63), 3:4 stride
- **Base32**: `.rodata`에 32글자(`A-Z2-7`), 마스크 `& 0x1F`(31), 5:8 stride
- **Base16**: `.rodata`에 16글자(`0123456789ABCDEF`), 마스크 `& 0x0F`(15), 1:2 stride, 상위/하위 니블을 나누는 `shr 4`/`and 0Fh` 쌍

## 가장 먼저 할 것
발견한 알파벳 문자열의 **정확한 글자 수**부터 센다. 64자면 Base64, 32자면 Base32, 16자면 Base16(Hex) 계열이다. 그다음 알파벳 순서가 표준(A-Z, a-z, 0-9, +/)과 일치하는지 확인해서 표준인지 커스텀(REV-0880 참고)인지 가른다.

## 단계별 절차
**1) 알파벳 길이 세기** — IDA 문자열 창(`Shift+F12`)에서 후보 문자열의 길이를 확인.

**2) 표와 대조** — 64/32/16 중 어디에 해당하는지, 표준 순서와 일치하는지 확인.

**3) Python 표준 라이브러리로 즉시 검증**
```python
import base64

print(base64.b64encode(b"hello"))          # b'aGVsbG8='
print(base64.urlsafe_b64encode(b"hello"))  # b'aGVsbG8='  (이 예에서는 +/가 없어 동일)
print(base64.b32encode(b"hello"))          # b'NBSWY3DP'
print(bytes.fromhex("68656c6c6f"))         # b'hello'  (Base16/Hex)
```

**4) 표준이 아니면 커스텀 알파벳 문서로 이동** — 순서가 다르거나 완전히 다른 문자 집합이면 REV-0880(커스텀 인코딩 알파벳 예시 모음)과 REV-0214(치환 패턴)를 참고해 알파벳 자체를 바이너리에서 추출한다.

## 명령어/단축키
- IDA: `Shift+F12`(문자열 창), `H`(마스크 상수 진법 토글)
- Python: `base64.b64decode/b32decode`, `bytes.fromhex`, `base64.urlsafe_b64decode`

## 출력 해석
- `base64.b64decode`/`b32decode` 결과가 사람이 읽을 수 있는 문자열/올바른 구조(플래그 포맷 등)로 나오면 표준 인코딩으로 확정.
- 디코딩 결과가 깨진 바이트라면 알파벳 순서가 표준과 다른 커스텀 변형이거나, URL-safe/표준 버전을 서로 바꿔 시도했을 가능성이 있다.
- Base32 디코딩에서 대소문자를 구분해서 실패하는 경우, `.upper()`로 정규화 후 재시도.

## 흔한 실수
- Base32의 `A-Z2-7` 알파벳에서 왜 `0`과 `1`이 없는지 모르고 직접 알파벳을 만들다가 `O`/`I`와 혼동하는 것.
- 표준 Base64와 URL-safe Base64를 구분하지 않고 아무 디코더나 적용해서 `+`/`-`, `/`/`_` 위치에서 디코딩이 실패하는 것.
- Base16(Hex) 인코딩을 "그냥 문자열이라 의미 없다"고 넘기는 것 — 실제로는 표준 인코딩 계열의 가장 단순한 멤버이며 니블 단위 처리(REV-0213)로 바로 원문 바이트를 복원할 수 있다.
- 알파벳 길이가 64/32/16이 아닌데(예: 58자, 85자) 억지로 Base64/32/16 중 하나로 끼워 맞추려는 것 — 58자면 Base58(비트코인 주소 등), 85자면 Base85/Ascii85 같은 별도 인코딩이다.

## 막혔을 때 다음 체크
- Base64의 비트 슬라이싱(6비트 단위 연산) 자체를 더 자세히 확인하려면 → REV-0212 — Base64 인코딩 검증 패턴.
- 1바이트↔2글자의 단순 Hex 인코딩 로직이 궁금하면 → REV-0213 — Hex 인코딩 검증 패턴.
- 알파벳 순서가 셔플되어 있다면 → REV-0880 — 흔한 커스텀 인코딩 알파벳 예시 모음, REV-0214 — Custom alphabet 치환 패턴.

## 미니 예제
`.rodata`에서 다음 32글자 문자열을 발견했다:
```
ABCDEFGHIJKLMNOPQRSTUVWXYZ234567
```
정확히 32자, 표준 Base32 알파벳과 일치한다. Python으로 대조:
```python
import base64
assert base64.b32encode(b"hello") == b"NBSWY3DP"
```
이 함수가 5바이트를 8글자로 늘리는 구조(stride 5:8)라면 표준 Base32 인코딩으로 확정된다.

## 관련 글
- REV-0212 — Base64 인코딩 검증 패턴
- REV-0213 — Hex 인코딩 검증 패턴
- REV-0880 — 흔한 커스텀 인코딩 알파벳 예시 모음
- REV-0214 — Custom alphabet 치환 패턴

## 출처/검증
- Base64/Base32/Base16 알파벳, 패딩 규칙, URL-safe 및 base32hex 변형: IETF RFC 4648, "The Base16, Base32, and Base64 Data Encodings" 명세 기준 (2026-09-09 검증).
- Python 표준 라이브러리 `base64` 모듈의 인코딩 결과: Python 공식 문서 기준 (2026-09-09 검증).
