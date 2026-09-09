---
id: REV-0903
title: "URL-safe Base64 변형 알아보기"
slug: "rev-0903-url-safe-base64-variant"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["URL-safe Base64", "base64url", "JWT", "RFC 4648", "-_", "패딩 생략", "unpadded base64"]
aliases: ["url safe base64", "base64url", "jwt 인코딩", "웹세이프 base64", "url 안전 인코딩"]
symptom_keywords: ["플러스 대신 하이픈이 보임", "슬래시 대신 언더스코어가 보임", "등호 패딩이 아예 없음", "점(.) 세 부분으로 나뉜 문자열이 보임", "jwt 헤더가 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
표준 Base64(REV-0212)와 똑같이 3바이트→4글자 비트 패킹을 쓰지만, 알파벳의 마지막 두 글자만 `+`/`/` 대신 `-`/`_`로 바뀌고 대부분 `=` 패딩까지 생략하는 인코딩이 보이면 이는 URL-safe Base64(base64url, RFC 4648 §5)이며, JWT(JSON Web Token)처럼 URL이나 HTTP 헤더에 안전하게 넣어야 하는 데이터에서 압도적으로 많이 쓰인다.

## 언제 검색해야 하나
- Base64로 보이는 문자열인데 `+`나 `/`가 전혀 없고 대신 `-`나 `_`가 섞여 있을 때
- 점(`.`)으로 구분된 세 부분의 문자열을 발견했을 때 — `헤더.페이로드.서명` 구조의 JWT일 가능성이 매우 높음
- 디코딩해야 할 문자열 끝에 `=` 패딩이 전혀 없는데도 Base64 계열 비트 패킹(`>>2`, `&0x3F` 등)이 보일 때
- HTTP 쿠키, URL 쿼리 파라미터, 파일명 등 특수문자가 문제를 일으킬 수 있는 위치에 인코딩된 데이터가 들어갈 때

## 핵심 개념

### 표준 Base64가 URL에서 문제가 되는 이유
표준 Base64(REV-0212) 알파벳의 마지막 두 문자는 `+`와 `/`다. 그런데 URL에서 `+`는 공백으로 해석되거나 쿼리 파라미터 구분에 관여할 수 있고, `/`는 경로 구분자로 해석된다. 또한 `=` 패딩 문자도 URL 쿼리 문자열의 키=값 구분자와 충돌할 수 있다. 이런 문제 때문에 Base64로 인코딩한 데이터를 URL, 쿠키, 파일명, HTTP 헤더 등에 그대로 넣으면 별도의 URL 인코딩(퍼센트 인코딩)이 추가로 필요해져 번거롭고 길이도 늘어난다.

### URL-safe 변형의 핵심 — 알파벳 두 글자 교체
RFC 4648 §5("Base 64 Encoding with URL and Filename Safe Alphabet")는 이 문제를 해결하기 위해 딱 두 글자만 바꾼 변형을 정의한다:
```
표준 Base64:  ... 62='+', 63='/'
URL-safe:     ... 62='-', 63='_'
```
즉 인덱스 0~61에 대응하는 62개 문자(`A-Z`, `a-z`, `0-9`)는 표준과 완전히 동일하고, **인덱스 62와 63만 각각 `+`→`-`, `/`→`_`로 바뀐다.** 6비트→문자 매핑 공식이나 3바이트→4글자 비트 패킹 로직(REV-0212에서 다룬 `>>2 & 0x3F` 등) 자체는 조금도 바뀌지 않는다. 즉 코드를 볼 때 "비트 연산 로직은 Base64와 완전히 동일한데 알파벳 테이블의 마지막 두 글자만 다르다"는 것이 URL-safe Base64의 핵심 지문이다.

### 패딩 생략 — 실무에서 거의 항상 함께 나타나는 관례
RFC 4648 자체는 패딩(`=`)을 URL-safe 변형에서도 여전히 정의하지만, 실무에서는 `=`도 URL 쿼리 구분자와 충돌 소지가 있어 **패딩 없는(unpadded) 형태**로 쓰는 경우가 압도적으로 많다. 이 경우 디코딩 시 원래 길이를 몰라도 남은 문자 수(4로 나눈 나머지가 0, 2, 3 중 하나)만으로 마지막 그룹의 유효 바이트 수를 계산할 수 있다. 패딩이 없는 문자열을 표준 `base64.b64decode`로 그대로 디코딩하려 하면 길이 오류가 나는 경우가 많으므로, "패딩이 없으면 부족한 만큼 `=`를 채워 넣고 디코딩한다"는 처리가 코드나 재현 스크립트에 필요하다.

### JWT(JSON Web Token) — URL-safe Base64의 가장 흔한 실전 용례
JWT는 `헤더.페이로드.서명` 세 부분을 마침표(`.`)로 이어붙인 문자열이며, 각 부분이 모두 URL-safe Base64(패딩 없음)로 인코딩되어 있다. 예를 들어 헤더 부분을 디코딩하면 `{"alg":"HS256","typ":"JWT"}` 같은 JSON이 나온다. CTF나 웹 리버싱에서 "이상한 점(.) 두 개로 나뉜 긴 문자열"을 보면 거의 항상 JWT이고, 그 서명 부분은 REV-0898에서 다룬 HMAC(또는 RSA 서명) 구조로 만들어진다.

### 다른 Base64 변형과의 비교
| 변형 | 62번 문자 | 63번 문자 | 패딩 | 대표 용례 |
|---|---|---|---|---|
| 표준 Base64(REV-0212) | `+` | `/` | `=` 사용 | 이메일(MIME), 일반 데이터 |
| URL-safe(RFC 4648 §5) | `-` | `_` | 보통 생략 | URL, 쿠키, JWT, 파일명 |
| YAML/일부 커스텀 | 다양 | 다양 | 다양 | 프로그램별로 다름(REV-0214 커스텀 알파벳 참고) |

## 화면/코드에서 보이는 징후
- Base64 스타일 문자열(길이가 4의 배수에 가까움)인데 `+`, `/`가 전혀 없고 대신 `-`, `_`가 섞여 있음
- 문자열이 `=` 없이 끝나거나, 길이가 4의 배수가 아님(패딩 생략)
- `.`으로 구분된 세 개의 그룹으로 이루어진 긴 문자열(JWT 구조)
- 디컴파일 코드에서 표준 Base64와 동일한 `>>2`, `&0x3F` 비트 연산인데 테이블의 마지막 두 값만 `2D`(`-`)와 `5F`(`_`)로 되어 있음

## 가장 먼저 할 것
문자열에 `+`/`/`가 있는지 먼저 확인한다. 없고 `-`/`_`가 보이면 URL-safe 변형이다. `.`으로 나뉜 세 부분 구조라면 JWT일 가능성이 매우 높으므로 각 부분을 점 기준으로 분리한 뒤 개별적으로 디코딩을 시도한다.

## 단계별 절차
1. 대상 문자열에 `.`이 정확히 2개 있는지 확인 — 있으면 JWT로 간주하고 3부분으로 분리
2. 각 부분(또는 단일 문자열)에 `+`/`/` 유무로 표준/URL-safe 여부 판별
3. 길이를 4로 나눈 나머지를 계산해 패딩이 몇 개 빠졌는지 계산(`나머지 2` → `==` 2개 필요, `나머지 3` → `=` 1개 필요, `나머지 0` → 패딩 불필요)
4. 부족한 `=`를 채운 뒤 표준 Base64 알파벳을 URL-safe로 바꿔서(또는 반대로) 디코딩
5. JWT라면 페이로드(두 번째 부분) 디코딩 결과가 JSON인지 확인하고, 서명(세 번째 부분)이 REV-0898의 HMAC 구조와 맞는지 확인
6. Python `base64.urlsafe_b64decode`로 표준 라이브러리와 대조 검증

## 명령어/단축키
```bash
python3 -c "
import base64

def decode_url_safe(s: str) -> bytes:
    s += '=' * (-len(s) % 4)   # 부족한 패딩 채우기
    return base64.urlsafe_b64decode(s)

print(decode_url_safe('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'))
"
```
IDA: `Shift+F12`(문자열 창)에서 `-`/`_` 포함 여부로 필터링, 점(`.`) 2개짜리 긴 문자열 검색은 `Alt+T` 텍스트 검색 활용.

## 출력 해석
- 위 예제를 디코딩하면 `b'{"alg":"HS256","typ":"JWT"}'`가 나온다 — JWT 헤더의 전형적인 JSON 형태로, 이걸 확인하면 URL-safe Base64 디코딩이 정확했다는 뜻이다.
- 표준 `base64.b64decode`로 시도했는데 `Invalid base64-encoded string` 오류가 나면 `-`/`_` 문자 때문일 가능성이 높으니 `urlsafe_b64decode`로 바꿔서 재시도한다.
- 패딩을 채웠는데도 디코딩 오류가 나면 문자열 자체가 URL 인코딩(퍼센트 인코딩)까지 한 번 더 씌워진 상태일 수 있으니 `%XX` 패턴이 남아있는지 먼저 확인한다.

## 흔한 실수
- URL-safe Base64를 표준 Base64와 다른 알고리즘으로 착각하는 것 — 비트 패킹 로직은 완전히 동일하고 알파벳 두 글자와 패딩 관례만 다르다.
- 패딩이 없다고 디코딩이 불가능하다고 단정하는 것 — 남은 문자 수의 나머지(mod 4)만으로 부족한 패딩 개수를 항상 계산할 수 있다.
- JWT를 "암호화되어 있다"고 착각하는 것 — 표준 JWT(JWS)는 헤더/페이로드가 그냥 Base64url로 인코딩만 되어 있을 뿐 암호화되지 않으므로 누구나 디코딩해서 내용을 읽을 수 있다. 보호되는 것은 무결성(서명)이지 기밀성이 아니다.
- `-`/`_` 치환을 빠뜨리고 표준 `+`/`/`로 그대로 치환 후 디코딩을 시도해 잘못된 바이트가 나오는 것.

## 막혔을 때 다음 체크
- 표준 Base64의 기본 비트 연산 원리가 기억나지 않으면 → [rev-0212-base64-pattern.md](./rev-0212-base64-pattern.md)
- 서명 부분이 어떻게 만들어지는지 궁금하면 → REV-0898 HMAC 패턴 알아보기(이중 해시 구조)
- 알파벳 순서 자체가 표준과 또 다르게 셔플되어 있다면 → [rev-0214-custom-alphabet-substitution.md](./rev-0214-custom-alphabet-substitution.md)
- 검증 로직을 파이썬으로 재현하려면 → [rev-0222-reimplement-in-python.md](./rev-0222-reimplement-in-python.md)

## 미니 예제
웹 요청의 쿠키 값에서 다음 문자열을 발견했다:
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiYWRtaW4ifQ.dGhpc2lzYXNpZ25hdHVyZQ
```
점(`.`)이 두 개 있어 JWT 구조로 판단하고 세 부분으로 나눴다:
```python
import base64

def decode_part(s: str) -> bytes:
    s += '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)

header, payload, sig = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "eyJ1c2VyIjoiYWRtaW4ifQ", "dGhpc2lzYXNpZ25hdHVyZQ"
print(decode_part(header))   # b'{"alg":"HS256","typ":"JWT"}'
print(decode_part(payload))  # b'{"user":"admin"}'
```
헤더와 페이로드가 모두 정상 JSON으로 디코딩되므로, 이 문자열은 URL-safe Base64(패딩 생략)로 인코딩된 JWT임이 확정된다. 서명 부분은 REV-0898의 HMAC-SHA256 절차로 검증해야 한다.

## 관련 글
- [rev-0212-base64-pattern.md](./rev-0212-base64-pattern.md) — 표준 Base64의 비트 패킹 원리
- REV-0898 — HMAC 패턴 알아보기(이중 해시 구조)
- [rev-0214-custom-alphabet-substitution.md](./rev-0214-custom-alphabet-substitution.md) — 알파벳이 셔플된 경우의 일반적 대응법
- REV-0902 — Base85/Ascii85 인코딩 알아보기
- [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) — 정보 손실 없는 재표현은 항상 역산 가능

## 출처/검증
- URL-safe Base64 알파벳(`-`, `_`)과 표준 Base64 알파벳의 차이: IETF RFC 4648 §5, "Base 64 Encoding with URL and Filename Safe Alphabet" 원문 기준 (2026-09-09 검증).
- JWT(JWS) 구조와 헤더/페이로드/서명이 각각 URL-safe Base64로 인코딩된다는 사실: IETF RFC 7515(JSON Web Signature), RFC 7519(JSON Web Token) 기준 (2026-09-09 확인).
- Python `base64.urlsafe_b64decode` 동작 및 패딩 계산 방식: Python 공식 `base64` 모듈 문서 기준 (2026-09-09).
