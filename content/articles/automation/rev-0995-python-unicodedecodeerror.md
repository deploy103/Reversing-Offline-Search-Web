---
id: REV-0995
title: "Python 문자열/바이트 인코딩 오류(UnicodeDecodeError)가 날 때"
slug: "rev-0995-python-unicodedecodeerror"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["UnicodeDecodeError", "invalid start byte", "python bytes str 차이", "decode encode", "python3 인코딩 오류"]
aliases: ["파이썬 디코드 에러", "utf-8 codec can't decode byte", "python bytes to string 오류", "python 한글 깨짐"]
symptom_keywords: ["UnicodeDecodeError가 남", "invalid start byte 에러", "python에서 바이너리 읽다가 에러남", "codec can't decode byte 0x.. in position"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
파이썬 3에서 `str`(텍스트)과 `bytes`(원시 바이트열)는 서로 다른 타입이며, 바이너리 파일이나 네트워크에서 읽은 `bytes`를 `utf-8` 같은 텍스트 인코딩으로 강제로 `.decode()`하려다 그 바이트가 유효한 문자 시퀀스가 아니면 `UnicodeDecodeError`가 발생하는데, 리버싱 자동화에서는 애초에 디코드하지 말고 `bytes` 그대로 다루는 것이 정답인 경우가 대부분이다.

## 언제 검색해야 하나
- 바이너리 파일을 읽어서 문자열을 뽑으려다 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x.. in position ..`를 만났을 때
- pwntools로 받은 데이터(`p.recv()`)를 `print()`하거나 문자열 연산을 하려다 타입 에러나 디코드 에러가 날 때
- 바이너리 안의 문자열이 실제로 UTF-8이 아니라 다른 인코딩(EUC-KR, Latin-1 등)이거나 애초에 텍스트가 아닌 순수 데이터일 때
- 어떤 바이트를 `.decode()`해야 할지 말아야 할지 판단이 안 설 때

## 핵심 개념
파이썬 3에서 텍스트를 다루는 방식은 파이썬 2와 근본적으로 다르다.

- **`str`** — 유니코드 코드포인트의 시퀀스. 사람이 읽는 "문자"를 표현한다. 소스코드에서 `'abc'`, `"한글"`처럼 따옴표로만 감싸면 이 타입이다.
- **`bytes`** — 원시 바이트(0~255) 값의 시퀀스. 파일을 `'rb'` 모드로 읽거나, 소켓/파이프에서 받은 데이터, 실행 파일의 raw 내용은 전부 이 타입이다. 소스코드에서 `b'abc'`처럼 `b` 접두사를 붙이면 이 타입이다.

이 둘은 서로 다른 타입이라서 자동으로 변환되지 않는다. `bytes` → `str`로 바꾸려면 `.decode(인코딩)`을, `str` → `bytes`로 바꾸려면 `.encode(인코딩)`을 명시적으로 호출해야 한다. 문제는 **모든 바이트 시퀀스가 유효한 UTF-8 문자열은 아니라는 것**이다. UTF-8은 특정 비트 패턴 규칙을 따라야 하는 가변 길이 인코딩이라서, 실행 파일의 기계어 코드나 압축 데이터, 임의의 바이너리 조각을 그대로 `.decode('utf-8')`하면 그 규칙에 맞지 않는 바이트가 나오는 순간 예외가 발생한다.

리버싱/CTF 자동화에서 다루는 데이터(파일 바이트, 네트워크 페이로드, 메모리 덤프)는 대부분 애초에 사람이 읽는 텍스트가 아니다. 따라서 원칙은 "**가능하면 `bytes`로 계속 다루고, 사람이 읽을 화면 출력이 필요한 특정 부분만 골라서 디코드한다**"이다. 모든 것을 습관적으로 `str`로 바꾸려는 시도 자체가 이 오류의 근본 원인이다.

## 화면/코드에서 보이는 징후
```python
>>> data = open('chall', 'rb').read()
>>> text = data.decode('utf-8')
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
UnicodeDecodeError: 'utf-8' codec can't decode byte 0x90 in position 4: invalid start byte
```
또는 pwntools 사용 중:
```python
>>> response = p.recvline()
>>> print(response)
b'Correct!\n'
>>> if response == 'Correct!\n':   # str과 bytes를 == 비교
...     print('match')
... 
# 항상 False가 되어 print가 실행되지 않음 (예외는 안 나지만 로직 버그)
```

## 가장 먼저 할 것
지금 다루는 데이터가 정말 "사람이 읽는 텍스트"인지, 아니면 "임의의 바이트열"인지부터 구분한다. 실행 파일 전체, 네트워크 패킷, 메모리 덤프는 후자다. 이런 데이터는 애초에 `.decode()`할 필요가 없고, `bytes` 상태로 비교(`==`)하거나 `bytes` 리터럴(`b'...'`)과 대조하면 된다.

## 단계별 절차

**1) 정말 디코드가 필요한지 먼저 판단**
```python
data = open('chall', 'rb').read()
# 바이너리 전체를 문자열로 바꿀 필요는 거의 없다. 대신 bytes 그대로 검색한다.
if b'flag{' in data:
    print('found marker')
```

**2) 특정 구간만 안전하게 디코드하고 싶을 때 — errors 옵션 사용**
```python
data = open('chall', 'rb').read()
# 디코드 불가능한 바이트를 무시하거나 대체 문자로 바꿔서 예외 없이 진행
text_ignore = data.decode('utf-8', errors='ignore')
text_replace = data.decode('utf-8', errors='replace')  # 안 되는 바이트를 U+FFFD(?)로 치환
print(text_replace[:100])
```
`errors='ignore'`는 디코드 불가능한 바이트를 그냥 버리고, `errors='replace'`는 대체 문자로 바꾼다. 둘 다 예외 없이 끝까지 진행되지만, 원본 바이트 정보는 그 과정에서 손실된다는 점을 알아야 한다.

**3) 인코딩 자체가 UTF-8이 아닐 가능성 검토**
```python
# 바이너리 안 문자열이 EUC-KR(한글 윈도우 레거시 인코딩)일 수도 있다
try:
    text = data.decode('utf-8')
except UnicodeDecodeError:
    text = data.decode('cp949', errors='replace')  # 윈도우 한글 인코딩 시도
```

**4) pwntools 응답을 문자열과 비교할 때는 bytes로 통일**
```python
from pwn import *
p = process('./chall')
response = p.recvline()

# 올바른 비교: 양쪽 다 bytes
if b'Correct' in response:
    print('correct!')

# 화면에 사람이 읽기 좋게만 출력하고 싶다면 그때만 디코드
print(response.decode(errors='replace'))
```

**5) strings 스타일로 출력 가능한 문자열만 추출**
```python
import re

def extract_strings(data: bytes, minlen: int = 4):
    pattern = rb'[\x20-\x7e]{%d,}' % minlen  # 출력 가능한 ASCII 범위만
    return [m.decode('ascii') for m in re.findall(pattern, data)]

data = open('chall', 'rb').read()
for s in extract_strings(data)[:20]:
    print(s)
```
이 방식은 UTF-8 디코드를 아예 시도하지 않고 "출력 가능한 ASCII 바이트 구간"만 정규식으로 골라내므로, 바이너리 전체에서 `strings` 명령과 비슷한 결과를 예외 없이 얻을 수 있다.

## 명령어/단축키
- `b.decode('utf-8')` : bytes를 UTF-8 텍스트로 변환(실패 시 `UnicodeDecodeError`)
- `b.decode('utf-8', errors='ignore'|'replace'|'backslashreplace')` : 실패하는 바이트 처리 방식 지정
- `s.encode('utf-8')` : str을 bytes로 변환
- `b.decode('latin-1')` : 모든 256개 바이트값을 예외 없이 1:1로 매핑(디코드 실패가 절대 나지 않음, 원본 바이트 보존 목적으로 자주 씀)
- `re.findall(rb'[\x20-\x7e]{4,}', data)` : 바이너리에서 출력 가능한 ASCII 문자열 구간만 추출

## 출력 해석
- `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x90 in position 4: invalid start byte` — 4번째 바이트(`0x90`)가 UTF-8 문자 인코딩 규칙상 문자의 "시작 바이트"로 쓰일 수 없는 값이라는 뜻. 이는 그 데이터가 애초에 UTF-8 텍스트가 아니라는 강한 신호다.
- `invalid continuation byte` — 문자 시작 바이트는 맞는데 그 뒤에 이어져야 할 바이트가 UTF-8 규칙에 안 맞는다는 뜻. 역시 텍스트가 아닌 바이너리 데이터를 디코드하려 했을 가능성이 크다.
- `errors='replace'`로 디코드한 결과에 `�`(물음표 모양 대체 문자)가 여러 개 보이면, 그 위치의 원본 바이트는 이미 손실되었다는 뜻이므로 정확한 원본 바이트가 필요한 작업(오프셋 계산, 패치 등)에는 이 방식을 쓰면 안 된다.

## 흔한 실수
- 바이너리 파일 전체를 무조건 `.decode('utf-8')`부터 시도하는 것 — 대부분의 실행 파일 바이트는 애초에 텍스트가 아니다.
- `bytes`와 `str`을 `==`로 비교했는데 둘 다 다른 타입이라 조용히 항상 `False`가 나오는 것을 예외가 없다는 이유로 못 알아채는 것.
- `errors='ignore'`로 디코드 문제를 "해결"했다고 착각하지만, 실제로는 원본 바이트 일부가 사라진 채로 이후 로직(오프셋 계산 등)에 영향을 주는 것.
- 파일을 `'r'`(텍스트 모드)로 열어서 파이썬이 내부적으로 자동 디코드를 시도하다 예외가 나는 것 — 바이너리는 반드시 `'rb'` 모드로 열어야 한다.
- 소스 파일 자체의 인코딩(예: 한글 주석이 포함된 `.py` 파일)과 런타임에 다루는 데이터의 인코딩을 서로 다른 문제인데 혼동하는 것.

## 막혔을 때 다음 체크
- pwntools 통신 자체가 계속 끊기거나 멈춘다면(인코딩과는 별개 문제) → REV-0996 pwntools EOFError, REV-0997 pwntools TimeoutError.
- 바이트열을 정수로 조립/해체해야 한다면 → REV-0267 pwntools p32 p64 u32 u64.
- 정수 부호/비트 관련 변환이 헷갈리면 → REV-0259 파이썬 부호 있는/부호 없는 정수 변환.

## 미니 예제
```python
data = b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00\x00\x00\rIHDR'  # PNG 헤더 예시 (일부 바이트는 유효 UTF-8 아님)

try:
    text = data.decode('utf-8')
except UnicodeDecodeError as e:
    print('디코드 실패:', e)
    # 대신 안전하게 latin-1로 1:1 매핑하거나, 출력 가능한 부분만 추출
    safe = data.decode('latin-1')
    print(repr(safe))
```
출력 예:
```text
디코드 실패: 'utf-8' codec can't decode byte 0x89 in position 0: invalid start byte
'\x89PNG\r\n\x1a\x00\x00\x00\rIHDR'
```
PNG 시그니처처럼 첫 바이트부터 UTF-8 규칙에 맞지 않는 바이너리 매직 넘버는 애초에 디코드 대상이 아니라, `bytes` 그대로 `data[:8] == b'\x89PNG\r\n\x1a\n'` 같은 방식으로 비교해야 한다는 점을 보여준다.

### 에러를 재현하는 잘못된 코드 vs 고쳐서 정상 동작하는 코드 (기계어 바이트를 디코드하려다 실패하는 경우)
아래 두 스크립트는 별도 패키지 설치 없이 표준 파이썬 3만으로 그대로 실행된다. `b'\x55\x48\x89\xe5\x90\xc3'`는 x64 함수 프롤로그(`push rbp; mov rbp, rsp; nop; ret`)의 실제 기계어 바이트다.

**잘못된 코드 — 기계어 바이트를 그냥 utf-8로 디코드하려다 예외로 스크립트 전체가 중단됨**
```python
# push rbp; mov rbp, rsp; nop; ret 에 해당하는 실제 x64 기계어 바이트 (텍스트가 아님)
code_bytes = b'\x55\x48\x89\xe5\x90\xc3'

# *** 잘못된 부분: 이 바이트가 사람이 읽는 텍스트인지 확인하지 않고 무조건 디코드 시도 ***
text = code_bytes.decode('utf-8')   # 여기서 예외 발생 -> 아래 print는 실행되지 않음
print('디코드 결과:', text)
```
실행하면 다음과 같은 예외가 그대로 발생한다.
```text
UnicodeDecodeError: 'utf-8' codec can't decode byte 0x89 in position 2: invalid start byte
```
세 번째 바이트(`0x89`, 0-based 인덱스로는 2번 위치)가 UTF-8에서 "이어지는 바이트"에만 쓰이는 비트 패턴(`10xxxxxx`)이라서, 문자의 시작 바이트로는 쓰일 수 없기 때문에 나는 오류다.

**고친 코드 — 애초에 디코드가 필요 없는 데이터임을 인식하고 bytes 그대로 다룸**
```python
code_bytes = b'\x55\x48\x89\xe5\x90\xc3'

# 고친 방법 1: 텍스트가 아니므로 decode()를 아예 호출하지 않고 bytes 그대로 비교한다
if code_bytes[:1] == b'\x55':                 # 첫 바이트가 0x55(push)로 시작하는지 확인
    print('push 명령으로 시작하는 함수 프롤로그로 보임')

# 고친 방법 2: 화면에 16진수로 확인하고 싶을 뿐이라면 decode 대신 hex()를 쓴다
print(code_bytes.hex())   # '554889e590c3' -- 예외 없이 항상 성공

# 고친 방법 3: 그래도 문자(str) 형태가 꼭 필요하다면, 실패하지 않는 latin-1로 1:1 매핑한다
safe_text = code_bytes.decode('latin-1')   # 0~255 모든 바이트값을 그대로 유니코드 코드포인트로 매핑
print(repr(safe_text))   # 원본 바이트 정보가 손실 없이 그대로 보존됨
```
`latin-1`은 256개 바이트 값 전부를 예외 없이 1:1로 문자에 대응시키기 때문에, "어떤 값이 와도 절대 실패하지 않는 디코딩"이 필요할 때(원본 바이트를 보존해야 하는 경우) 자주 쓰인다.

### 에러를 재현하는 잘못된 코드 vs 고친 코드 (bytes와 str을 비교하는 조용한 로직 버그)
이번에는 예외가 아니라 **조용히 틀린 결과**가 나오는, 더 알아채기 어려운 형태의 버그를 재현한다.

**잘못된 코드 — bytes와 str을 `==`로 비교해서 항상 False가 됨(예외 없음)**
```python
response = b'Correct!\n'   # pwntools 등에서 실제로 받는 데이터는 항상 bytes 타입

# *** 잘못된 부분: 왼쪽은 bytes, 오른쪽은 str -- 타입이 달라 절대 같을 수 없다 ***
if response == 'Correct!\n':
    print('정답 처리됨')
else:
    print('오답으로 처리됨')   # 실제로는 정답인데도 타입 불일치 때문에 이 줄이 실행된다
```
이 코드는 예외를 전혀 던지지 않기 때문에, 실행 결과만 보고는 "정답인데 왜 오답으로 나오지?"라는 논리 버그를 눈치채기 매우 어렵다.

**고친 코드 — 비교하는 양쪽을 bytes로 통일**
```python
response = b'Correct!\n'

# 고친 부분: 오른쪽도 b'...' bytes 리터럴로 맞춰서 타입을 통일한다
if response == b'Correct!\n':
    print('정답 처리됨')   # 이제 정확히 True로 판정된다
else:
    print('오답으로 처리됨')
```

## 관련 글
- REV-0996 — pwntools 프로세스 연결이 EOFError로 끊길 때
- REV-0997 — pwntools 타임아웃(TimeoutError)이 반복될 때
- REV-0267 — pwntools p32 p64 u32 u64
- REV-0259 — Python으로 Signed Unsigned 변환

## 출처/검증
- `str`/`bytes` 분리와 `.decode()`/`.encode()`, `errors` 인자 동작은 Python 공식 문서("Text vs. Data Instead of Unicode vs. 8-bit", `codecs` 모듈 문서)를 기준으로 정리했다(2026-09-09 검증).
- UTF-8 인코딩 규칙(시작 바이트/연속 바이트) 설명은 UTF-8 표준(RFC 3629) 및 Python `codecs` 문서 기준이다.
- 코드 예제는 표준 CPython 3 환경에서 별도 패키지 설치 없이 그대로 재현 가능하다.
