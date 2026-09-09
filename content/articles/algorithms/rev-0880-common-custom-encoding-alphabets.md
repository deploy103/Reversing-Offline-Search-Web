---
id: REV-0880
title: "흔한 커스텀 인코딩 알파벳 예시 모음"
slug: "rev-0880-common-custom-encoding-alphabets"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["Base58", "Ascii85", "Base85", "Z85", "셔플된 Base64", "custom alphabet 예시", "비트코인 알파벳", "uuencode"]
aliases: ["base58 알파벳", "ascii85 알파벳", "커스텀 base64 예시", "이상한 인코딩 알파벳"]
symptom_keywords: ["58글자 알파벳이 보임", "85개 문자로 인코딩됨", "z로 시작하는 압축 문자가 있음", "표준 base64와 순서가 다름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
표준 Base64/32/16(REV-0879)에 정확히 안 맞는 인코딩을 만났을 때, 실무/CTF에서 실제로 자주 쓰이는 커스텀 알파벳(Base58, Ascii85/Base85, Z85, 셔플된 Base64)의 정확한 문자 구성과 특징을 미리 알아두면 알파벳 길이만 보고도 바로 후보를 좁힐 수 있다.

## 언제 검색해야 하나
- 알파벳 길이가 64/32/16이 아니라 58자, 85자처럼 애매한 숫자일 때
- 결과 문자열에 `z` 하나만 뜬금없이 섞여 있고 나머지는 특수문자+영숫자로 보일 때(Ascii85의 z 축약 신호)
- Base64처럼 보이는데 알파벳 순서가 표준(`A-Z a-z 0-9 +/`)과 다르게 섞여 있을 때
- 비트코인/블록체인 관련 문자열(지갑 주소처럼 보이는 값)을 다룰 때

## 핵심 개념

**1) Base58 — 비트코인 알파벳 (58자)**
```
123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz
```
표준 영숫자(62자: `0-9A-Za-z`)에서 **모양이 헷갈리는 4개 문자(`0`, `O`, `I`, `l`)를 의도적으로 제외**해서 58자가 됐다. 사람이 손으로 옮겨 적거나 눈으로 구분할 때 실수를 줄이기 위한 설계다. 인코딩 방식도 Base64/32처럼 고정 비트 슬라이싱이 아니라, 전체 바이트열을 **하나의 큰 정수로 보고 58로 나눈 나머지를 반복 추출**하는 방식(임의 정밀도 정수 나눗셈)이라는 점이 결정적으로 다르다. 선두의 `0x00` 바이트는 나눗셈으로는 사라지므로, 별도로 알파벳의 첫 글자(`1`)로 개수만큼 채워 넣어야 정확히 복원된다. 이 알파벳이 보이면 지갑 주소, 짧은 ID, 체크섬 포함 식별자(Base58Check)를 다루는 코드일 가능성이 높다.

**2) Ascii85 / Base85 (85자, ASCII 33~117)**
```
! " # $ % & ' ( ) * + , - . / 0 1 2 3 4 5 6 7 8 9 : ; < = > ? @
A B C D E F G H I J K L M N O P Q R S T U V W X Y Z [ \ ] ^ _ `
a b c d e f g h i j k l m n o p q r s t u v w x y z { | } ~ u
```
0~84의 값에 33을 더해서 아스키 `!`(33)부터 `u`(117)까지의 인쇄 가능 문자 범위에 매핑한다. **4바이트를 5글자로** 묶는 방식이라 Base64(3→4)보다 압축 효율이 좋다. 특이한 최적화로, 4바이트가 전부 0이면 다섯 글자(`!!!!!`) 대신 문자 하나(`z`)로 축약해서 표시한다 — 결과 문자열 중간에 `z`가 툭 튀어나온다면 이 최적화가 적용된 구간이다. Adobe PDF/PostScript에서 바이너리 데이터를 표현할 때 흔히 쓰이며, 전체를 `<~`와 `~>`로 감싸는 관례가 있다.

**3) Z85 (85자, ZeroMQ 변형)**
Ascii85와 원리(4바이트→5글자, 85진법)는 같지만, 프로그래밍 언어 문자열 리터럴이나 URL에서 문제가 될 수 있는 문자(따옴표, 백슬래시 등)를 피하도록 알파벳을 다시 골랐다. ZeroMQ 생태계(ZMQ 소켓 키 표현 등)에서 자주 보인다. Ascii85와 겉보기(85자, 유사한 특수문자 비율)가 비슷해서 혼동하기 쉬우니, 알파벳에 `!`나 `` ` `` 같은 특정 문자가 있는지 없는지로 구분해야 한다.

**4) 셔플된 Base64 (64자, 순서만 다름)**
알파벳 구성 문자(`A-Za-z0-9+/`)는 표준과 동일하지만 **순서만 재배열**된 경우다. 비트 슬라이싱 로직(3→4, `>>2`/`&0x3F` 등)은 표준 Base64와 완전히 동일하고, 인덱스→문자 매핑 테이블 하나만 바뀐 것이므로 REV-0212의 `b64_decode_custom` 방식으로 테이블만 교체하면 그대로 풀린다. CTF에서 "이거 Base64인데 플래그가 안 나와요"라는 흔한 함정이 대부분 이 패턴이다.

**5) uuencode (64자, 공백 기반 오프셋)**
유닉스 전통의 `uuencode`는 6비트 값에 32(스페이스 문자 코드)를 더해 문자로 표현한다(값 0은 공백 대신 관례적으로 `` ` ``로 표시). 각 줄 맨 앞에 원본 바이트 길이를 인코딩한 문자가 하나씩 온다는 점이 Base64와 구분되는 특징이다. 현대 바이너리에서는 드물지만 레거시 유닉스 유틸리티나 메일 첨부 포맷 리버싱에서 여전히 등장한다.

## 화면/코드에서 보이는 징후
- 58자 알파벳 + 나눗셈(`div`/`idiv`) 반복 루프(시프트가 아니라 나눗셈이라는 점이 Base64/32와 다름) → Base58
- 85자 알파벳 + `z` 특수 처리 분기 + 4:5 stride → Ascii85/Base85
- 64자인데 `A-Za-z0-9+/` 순서가 표준과 다름 → 셔플된 Base64
- 결과 문자열이 공백 문자로 시작하거나 라인마다 특이한 접두 문자 → uuencode

## 가장 먼저 할 것
알파벳 길이부터 정확히 센다. 58이면 Base58(나눗셈 기반), 85면 Ascii85/Z85(85진법), 64인데 표준 순서와 다르면 셔플된 Base64다. 그다음 코드에서 시프트/마스크 연산(`>>`, `&`)을 쓰는지 나눗셈(`div`)을 쓰는지 확인하면 Base64 계열과 Base58을 확실히 구분할 수 있다.

## 단계별 절차
**1) 알파벳 길이/구성 확인** — 문자열 창에서 후보 문자열을 정확히 옮겨 적는다.

**2) 연산 방식 확인** — 시프트/마스크(고정 비트 슬라이싱)인지 나눗셈(임의 정밀도 big-integer)인지 디스어셈블리에서 확인.

**3) Python으로 표준 라이브러리 우선 시도**
```python
import base64
print(base64.a85encode(b"hello"))    # b'BOu!rDZ'  (Ascii85)
print(base64.b85encode(b"hello"))    # Base85(RFC 1924 계열, Ascii85와 알파벳이 다름)
```

**4) Base58은 직접 구현 (표준 라이브러리에 없는 경우가 많음)**
```python
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58decode(s: str) -> bytes:
    num = 0
    for ch in s:
        num = num * 58 + ALPHABET.index(ch)
    combined = num.to_bytes((num.bit_length() + 7) // 8, "big")
    n_pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * n_pad + combined
```

**5) 셔플된 Base64면 알파벳만 교체** — REV-0212의 `b64_decode_custom(s, table)` 함수에 추출한 알파벳을 그대로 대입.

## 명령어/단축키
- IDA: `Shift+F12`(문자열 창)로 58/85자 후보 확인, `Alt+T`로 `div`/`idiv` 명령어 검색
- Python: `base64.a85decode/a85encode`, `base64.b85decode/b85encode`, `base64.b58...`는 표준 라이브러리에 없으므로 위 스니펫처럼 직접 구현하거나 `base58` 서드파티 패키지 사용

## 출력 해석
- Base58 디코딩 결과가 20바이트(RIPEMD-160 해시 길이)나 32바이트(공개키/개인키 길이) 근처로 나오면 블록체인 관련 식별자일 가능성이 높다.
- Ascii85 디코딩 중 `z` 문자가 그룹 중간에 있어서 에러가 나면, `z`는 그룹 맨 앞에서만 유효한 축약임을 놓친 것이다.
- 셔플된 Base64 디코딩 결과가 깨진다면 알파벳 순서를 정확히 옮겨 적지 못했을 가능성이 크므로 원본 문자열을 다시 대조.

## 흔한 실수
- Base58과 Base64를 "둘 다 Base-something이니 비슷하겠지"라고 생각해서 시프트/마스크 방식으로 풀려다 실패하는 것 — Base58은 나눗셈 기반 big-integer 인코딩이라 근본적으로 다른 알고리즘이다.
- Ascii85의 `z` 축약 규칙을 모르고 `z`를 그냥 리터럴 데이터로 취급해서 디코딩이 틀어지는 것.
- Z85와 Ascii85를 같은 것으로 착각해서 표준 `base64.a85decode`로 Z85 문자열을 디코딩 시도하는 것 — 알파벳 구성 문자가 다르므로 실패한다.
- 셔플된 Base64에서 알파벳 순서만 바뀐 걸 못 알아채고 완전히 새로운 알고리즘이라고 오판해서 시간을 낭비하는 것 — 비트 연산 패턴이 표준 Base64와 동일한지부터 먼저 확인해야 한다.

## 막혔을 때 다음 체크
- 표준 Base64/32/16 알파벳부터 다시 확인하려면 → REV-0879 — Base64/Base32/Base16 알파벳 빠른 참조.
- 알파벳이 셔플된 걸 확인했다면 실제 치환 처리 방법은 → REV-0214 — Custom alphabet 치환 패턴.
- Base64의 비트 슬라이싱 공식 자체가 헷갈리면 → REV-0212 — Base64 인코딩 검증 패턴.

## 미니 예제
`.rodata`에서 다음 58글자 문자열을 발견했다:
```
123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz
```
정확히 58자이고 `0`, `O`, `I`, `l`이 빠져 있으므로 Base58 알파벳이다. 코드에서 반복적으로 `div`/`idiv` 58 연산을 쓰고 있다면 이 알파벳으로 big-integer 나눗셈 디코딩을 구현해야 한다.
```python
assert b58decode("Cn8eVZg") == b"hello"
assert b58decode("StV1DL6CwTryKyV") == b"hello world"
```
이렇게 `b"hello"`가 `"Cn8eVZg"`로, `b"hello world"`가 `"StV1DL6CwTryKyV"`로 인코딩되는 것을 직접 재현해보면 나눗셈 기반 디코더가 올바르게 동작하는지 확인할 수 있다. 실전에서는 바이너리에서 추출한 문자열을 그대로 대입한다.

## 관련 글
- REV-0879 — Base64/Base32/Base16 알파벳 빠른 참조
- REV-0212 — Base64 인코딩 검증 패턴
- REV-0214 — Custom alphabet 치환 패턴
- REV-0213 — Hex 인코딩 검증 패턴

## 출처/검증
- Base58(비트코인 알파벳, 제외 문자 0/O/I/l, big-integer 나눗셈 방식): Bitcoin Wiki, "Base58Check encoding" 공식 문서 기준 (2026-09-09 검증).
- Ascii85/Base85(ASCII 33~117 범위, z 축약, 4:5 stride): Adobe PostScript Language Reference의 ASCII85Encode 필터 명세 및 공개 기술 자료 기준 (2026-09-09 검증).
- Z85: ZeroMQ 공식 명세(ZMTP RFC "Z85 - ZeroMQ Base-85 Encoding") 기준.
- Python 표준 라이브러리 `base64.a85encode`/`b85encode` 동작: Python 공식 문서 기준 (2026-09-09 검증).
