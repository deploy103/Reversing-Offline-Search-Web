---
id: REV-0923
title: "Base64로 추정했는데 디코드가 실패할 때"
slug: "rev-0923-base64-decode-fails"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["Base64 디코드 실패", "Incorrect padding", "URL-safe Base64", "커스텀 알파벳", "Base64 변형"]
aliases: ["Base64 디코드 에러", "Incorrect padding 에러", "Base64인데 안 풀림", "커스텀 Base64 알파벳"]
symptom_keywords: ["binascii.Error Incorrect padding", "base64 디코드하면 에러남", "문자셋이 이상한 base64", "디코드는 되는데 결과가 이상함"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
문자열이 `A-Z`, `a-z`, `0-9`, 그리고 `+`/`/` 또는 `=`처럼 생겨서 Base64라고 확신하고 `base64.b64decode()`를 돌렸는데 에러가 나거나 결과가 깨진다면, 원인은 거의 항상 **패딩(`=`) 누락**, **URL-safe 변형(`-`, `_`)**, 또는 **알파벳 순서 자체가 표준과 다른 커스텀 Base64**이며, 세 가지를 순서대로 의심하면 대부분 해결된다.

## 언제 검색해야 하나
- `base64.b64decode(s)`가 `binascii.Error: Incorrect padding`을 던질 때
- 디코드는 에러 없이 되는데 결과가 사람이 읽을 수 없는 바이트로 나올 때
- 문자열에 `-`나 `_`가 섞여 있어서 표준 Base64와 조금 다르게 생겼을 때
- 디스어셈블리에서 Base64 인코딩 테이블을 발견했는데 표준 순서(`ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/`)와 다르게 배열돼 있을 때

## 핵심 개념
Base64는 3바이트(24비트)를 4개의 6비트 그룹으로 나누고, 각 6비트 값(0~63)을 정해진 64개 문자 알파벳에 매핑하는 인코딩이다. 이 매핑에는 표준이 있지만, 실제로 마주치는 문자열이 그 표준을 정확히 따르지 않는 경우가 많다.

**원인 1 — 패딩 누락/손상**: 표준 Base64는 입력 길이가 3의 배수가 아니면 마지막에 `=`를 채워 4의 배수 길이로 맞춘다. 이 패딩이 전송/저장 과정에서 잘렸거나, 애초에 프로그램이 패딩 없이 인코딩했다면 파이썬 표준 라이브러리는 `Incorrect padding` 에러를 던진다. 길이를 4의 배수로 맞추는 `=`의 개수는 `(-len(s)) % 4`로 계산할 수 있다.

**원인 2 — URL-safe 변형**: 표준 알파벳의 `+`와 `/`는 URL이나 파일 경로에서 특수한 의미를 가지므로, 이를 피하려고 `+`→`-`, `/`→`_`로 바꾼 "URL-safe Base64"(RFC 4648 §5)가 널리 쓰인다. 표준 디코더로 이런 문자열을 그대로 디코드하면 `-`, `_` 문자를 이해하지 못해 실패한다.

**원인 3 — 커스텀(치환된) 알파벳**: CTF에서는 표준 64개 문자를 그대로 쓰되 **순서를 섞은** 커스텀 알파벳을 쓰는 경우가 흔하다. 이 경우 문자 종류는 표준 Base64와 똑같이 생겼지만(그래서 처음엔 표준으로 착각하기 쉽다), 실제 6비트 값 매핑이 달라서 표준 디코더로는 에러 없이 디코드되더라도 완전히 다른(의미 없는) 바이트가 나온다.

## 화면/코드에서 보이는 징후
- `binascii.Error: Incorrect padding` 예외 메시지
- 디코드된 결과가 UTF-8/ASCII로 해석되지 않는 바이트 나열
- 문자열 안에 `-`, `_`가 섞여 있음
- 디스어셈블리에서 인코딩 테이블 문자열이 `ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/`와 다른 순서로 하드코딩돼 있음

## 가장 먼저 할 것
문자열의 문자 종류부터 확인한다. `-`나 `_`가 있으면 URL-safe로 먼저 시도하고, `+`나 `/`가 있으면 표준으로 시도한다. 그다음 길이가 4의 배수인지 확인하고 아니라면 패딩부터 보충한다. 이 두 가지를 해도 결과가 깨진다면 마지막으로 커스텀 알파벳을 의심한다.

## 단계별 절차

**1) 패딩 보충 후 표준 디코드 시도**
```python
import base64

def fix_padding(s: str) -> str:
    return s + "=" * ((-len(s)) % 4)

s = "aGVsbG8gd29ybGQ"   # 패딩이 잘린 상태
print(base64.b64decode(fix_padding(s)))   # b'hello world'
```

**2) URL-safe 변형 시도**
```python
s2 = "aGVsbG8t_29ybGQ"   # '-', '_' 포함
decoded = base64.urlsafe_b64decode(fix_padding(s2))
```

**3) 둘 다 실패하면 알파벳 자체를 디스어셈블리에서 추출**

바이너리의 인코딩 테이블(전역 변수로 선언된 64바이트 문자열)을 IDA/Ghidra의 Hex View나 문자열 창에서 그대로 복사한다.

**4) 커스텀 알파벳으로 직접 디코드**
```python
import base64

STANDARD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
CUSTOM   = "ZYXWVUTSRQPONMLKJIHGFEDCBAzyxwvutsrqponmlkjihgfedcba9876543210-_"  # 예시: 바이너리에서 추출한 순서

def custom_b64decode(s: str, custom_alphabet: str) -> bytes:
    table = str.maketrans(custom_alphabet, STANDARD)
    return base64.b64decode(fix_padding(s.translate(table)))

print(custom_b64decode("blnu9wxi", CUSTOM))
```
핵심은 **커스텀 알파벳의 문자를 표준 알파벳의 같은 위치(같은 6비트 값)에 대응하는 문자로 치환**한 다음, 표준 디코더에 넘기는 것이다. `str.maketrans`로 이 치환표를 한 줄에 만들 수 있다.

## 명령어/단축키
```python
base64.b64decode(s, validate=True)     # 알파벳에 없는 문자가 섞이면 즉시 에러로 알려줌
base64.urlsafe_b64decode(s)            # '-', '_' 알파벳
(-len(s)) % 4                          # 부족한 '=' 개수 계산
str.maketrans(custom, standard)        # 커스텀 알파벳 -> 표준 알파벳 치환표
```

## 출력 해석
- `validate=True` 옵션을 켰을 때 에러가 난다면, 표준 알파벳에 없는 문자(`-`, `_`, 혹은 완전히 다른 문자)가 섞여 있다는 확실한 신호다 — 어떤 문자가 문제인지 정확히 알 수 있다.
- 패딩만 고쳤는데도 결과가 사람이 못 읽는 바이트라면, 패딩 문제가 아니라 알파벳 순서 문제다.
- 커스텀 알파벳으로 치환한 후 결과가 사람이 읽을 수 있는 텍스트로 나오면 알파벳 순서 추출이 정확했다는 뜻이다.

## 흔한 실수
- `-`, `_`가 보이는데도 표준 `b64decode`를 계속 고집하다가 시간을 낭비하는 것 — 문자 종류를 보자마자 URL-safe부터 시도해야 한다.
- 알파벳 순서를 바이너리에서 추출할 때 오프셋을 하나 밀려서 옮겨 적는 것 — 64바이트 전체를 정확히, 한 글자도 빠뜨리지 않고 복사해야 한다.
- 패딩을 무조건 3개 붙이는 식으로 대충 처리하는 것 — 반드시 `(-len(s)) % 4` 공식으로 정확한 개수만 붙여야 하며, 이미 4의 배수인 문자열에 패딩을 추가하면 오히려 에러가 난다.
- Base64로 디코드는 됐지만 그 결과가 사실은 또 다른 인코딩(Base32, Ascii85)이거나 압축/암호화된 바이너리라서 "왜 텍스트가 안 나오지"라고 헷갈리는 것 — 디코드 자체는 성공했다면 그다음 단계(Hex 인코딩, 혹은 암호 알고리즘 식별)로 넘어가야 한다.

## 막혔을 때 다음 체크
- 디스어셈블리에서 인코딩 테이블 자체를 아직 못 찾았다면 → REV-0212 Base64 인코딩 검증 패턴
- 알파벳이 표준 Base64가 아니라 완전히 다른 치환 규칙이라면 → REV-0214 Custom alphabet 치환 패턴
- Base64가 아니라 Hex 인코딩일 가능성이 있다면 → REV-0213 Hex 인코딩 검증 패턴
- 디코드된 바이트가 여전히 사람이 못 읽는 값이라면 그 뒤에 XOR/해시 등 추가 변환이 있을 수 있다 → REV-0921 알고리즘을 복원했는데 출력이 원본과 안 맞을 때

## 미니 예제
어떤 바이너리가 플래그를 인코딩해서 `"ZmxhZ3t0ZXN0fQ"`(패딩 없음, 표준 알파벳)로 저장했다고 하자.
```python
s = "ZmxhZ3t0ZXN0fQ"
print(len(s), len(s) % 4)          # 14, 2 -> 부족한 '=' 개수 = (-14) % 4 = 2
padded = s + "=" * ((-len(s)) % 4)  # "ZmxhZ3t0ZXN0fQ=="
print(base64.b64decode(padded))     # b'flag{test}'
```
길이 14를 4로 나눈 나머지가 2이므로 부족한 패딩은 정확히 2개(`==`)이고, 이를 채우면 곧바로 `b'flag{test}'`가 나온다.

## 관련 글
- REV-0212 — Base64 인코딩 검증 패턴
- REV-0213 — Hex 인코딩 검증 패턴
- REV-0214 — Custom alphabet 치환 패턴
- REV-0921 — 알고리즘을 복원했는데 출력이 원본과 안 맞을 때

## 출처/검증
- Base64 표준 알파벳, 패딩 규칙, URL-safe 변형(`+`/`/` → `-`/`_`)은 IETF RFC 4648("The Base16, Base32, and Base64 Data Encodings") §4, §5 기준 (2026-09-09 검증).
- Python `base64` 모듈의 `b64decode`/`urlsafe_b64decode`/`validate` 동작은 Python 공식 문서(`base64` 모듈) 기준.
