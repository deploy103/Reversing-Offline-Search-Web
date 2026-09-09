---
id: REV-1087
title: "Python 2 vs 3 바이트코드 차이가 리버싱에 미치는 영향"
slug: "rev-1087-python2-vs-python3-bytecode"
category: "other-targets"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [python, dis, uncompyle6]
keywords: ["python2 python3 bytecode 차이", "PRINT_ITEM", "STORE_MAP", "python2 pyc", "python2 리버싱"]
aliases: ["python2 바이트코드가 이상하게 보임", "print문 opcode", "python2 vs 3 디컴파일 차이"]
symptom_keywords: ["dis 결과에 PRINT_ITEM이라는 낯선 opcode가 보임", "python2 pyc인데 최신 도구로 안 열림", "매직 넘버가 62211로 나옴"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
매직 넘버(REV-1083)가 `62211`(Python 2.7)처럼 6만대 값이면 이 `.pyc`는 Python 2 계열이라는 뜻이고, 이 경우 `print`문 전용 opcode·정수 나눗셈 방식·문자열이 바이트 시퀀스로 취급되는 점 등 Python 3과 근본적으로 다른 바이트코드 구조를 갖고 있으므로 디컴파일 도구와 해석 방식을 그에 맞게 바꿔야 한다.

## 언제 검색해야 하나
- REV-1083에서 확인한 매직 넘버가 `62211`처럼 Python 3 계열의 3000번대와 확연히 다른 값일 때
- `dis.dis()` 결과에 `PRINT_ITEM`, `PRINT_NEWLINE`, `STORE_MAP` 같은 Python 3에서는 볼 수 없는 opcode가 나올 때
- uncompyle6로 Python 2용 `.pyc`를 디컴파일했는데 결과 코드에 `print "text"`처럼 함수 호출이 아닌 `print`문 형태가 나와서 당황스러울 때

## 핵심 개념

### 매직 넘버부터 다르다
REV-1083의 표에서 봤듯 Python 2.7의 매직 넘버는 `62211`로, Python 3.x 계열의 3000번대 값과는 자릿수부터 다르다. 즉 매직 넘버 확인 단계에서 이미 "이건 Python 2다"라는 것을 알 수 있고, 이후 모든 도구 선택(uncompyle6는 2.x도 지원, decompyle3는 3.7+ 전용이라 Python 2에는 아예 못 씀)이 여기서 갈린다.

### print문 vs print() 함수 — 가장 눈에 띄는 차이
Python 2에서 `print "hello"`는 문법 자체가 문(statement)이라 전용 바이트코드가 따로 있었다. `dis` 출력에 `PRINT_ITEM`(출력할 값을 스택에서 꺼내 출력), `PRINT_NEWLINE`(줄바꿈 출력) 같은 opcode가 그대로 나타난다. Python 3부터는 `print()`가 평범한 내장 함수 호출이 되었기 때문에, 바이트코드 상으로는 `LOAD_GLOBAL (print)` 뒤에 `CALL`(또는 구버전 3.x의 `CALL_FUNCTION`)이 오는, 다른 일반 함수 호출과 구분되지 않는 형태로 나온다. 이 차이 하나만으로도 `dis` 결과를 보고 Python 2/3을 즉시 구분할 수 있다.

### 나눗셈 연산자의 의미 차이
Python 2는 `/` 연산자가 기본적으로 정수 나눗셈(피연산자가 둘 다 int면 몫만 반환)이었고, 이는 바이트코드 상 `BINARY_DIVIDE` opcode로 나타난다. Python 3은 `/`가 항상 실수(참) 나눗셈이 되었고(`BINARY_TRUE_DIVIDE`), 몫만 구하는 `//` 연산자를 위한 별도의 `BINARY_FLOOR_DIVIDE` opcode가 생겼다. 같은 소스처럼 보여도 어느 버전에서 컴파일됐는지에 따라 `/`가 실제로 하는 연산이 다르므로, 바이트코드만 보고 소스를 재구성할 때 이 opcode 이름을 반드시 확인해야 한다.

### 예외 처리 문법과 opcode 변화
Python 2는 `except Exception, e:`라는, 지금 보면 낯선 문법을 허용했고 내부적으로 `SETUP_EXCEPT`라는 전용 opcode를 썼다. Python 3은 `except Exception as e:`로 문법이 통일되었고, 예외 처리 관련 opcode 구성도 여러 차례 바뀌었다(3.11에서는 예외 처리 시 스택에 쌓이던 항목 수 자체가 3개에서 1개로 줄어드는 등 표현 방식이 재설계됨). 오래된 Python 2 코드를 다루다 `SETUP_EXCEPT`, `END_FINALLY` 같은 이름을 보면 "Python 2/3 초기의 예외 구조구나"라고 인식하면 된다.

### 문자열 리터럴의 근본적 차이
Python 2는 기본 문자열 리터럴(`"abc"`)이 바이트 문자열이고, 유니코드를 쓰려면 `u"abc"`처럼 명시해야 했다. Python 3은 반대로 기본 문자열이 전부 유니코드(`str`)이고, 바이트 시퀀스를 쓰려면 `b"abc"`로 명시해야 한다. 이 차이는 opcode 이름 자체보다는 `LOAD_CONST`로 로드되는 상수 객체의 실제 타입(`str` vs `bytes`/`unicode`)에서 드러나므로, `dis` 결과에서 상수 타입을 확인할 때 항상 어느 파이썬 버전 기준인지 염두에 둬야 한다.

### 디컴파일 도구 선택에 미치는 실전 영향
- **uncompyle6**는 Python 1.5, 2.1~3.8 근방까지 폭넓게 지원한다고 공식적으로 밝히고 있어 Python 2 `.pyc`를 다룰 수 있는 사실상 유일한 주력 도구다.
- **decompyle3**는 "Python 3.7 이상"만 대상으로 하므로 Python 2 파일에는 애초에 쓸 수 없다.
- 따라서 REV-1083에서 매직 넘버가 6만대(Python 2)로 나왔다면 REV-1084의 선택지 중 decompyle3는 제외하고 곧바로 uncompyle6를 쓴다.

## 화면/코드에서 보이는 징후
- `dis.dis()` 결과에 `PRINT_ITEM`, `PRINT_NEWLINE`, `STORE_MAP`(Python 2 dict literal 생성 시 쓰이던 opcode), `SETUP_EXCEPT` 같은 이름이 보인다.
- 디컴파일 결과 소스에 `print "값"` (괄호 없는 print문)이나 `except Exception, e:` 문법이 그대로 나온다.
- 매직 넘버가 REV-1083 표의 3.x 계열(3000번대)이 아니라 62211(2.7) 근방의 값이다.

## 가장 먼저 할 것
REV-1083 방식으로 매직 넘버부터 확인한다. 62211이면 Python 2.7로 확정, 이후 절차는 전부 "Python 2 전용 경로"(uncompyle6, 2.x 문법 이해)로 진행한다.

## 단계별 절차
1. 매직 넘버로 Python 2/3 여부를 먼저 확정한다(REV-1083).
2. Python 2로 확인되면 decompyle3는 후보에서 제외하고 uncompyle6만 시도한다.
3. `dis` 결과에 `PRINT_ITEM`/`SETUP_EXCEPT` 등이 보이면 "이건 2.x 문법이 반영된 것"이라 인식하고 3.x 기준 opcode 이름(`CALL`, `SETUP_FINALLY`)과 혼동하지 않는다.
4. 나눗셈 연산이 나오면 opcode가 `BINARY_DIVIDE`인지 `BINARY_TRUE_DIVIDE`/`BINARY_FLOOR_DIVIDE`인지로 실제 연산 의미를 확정한다.
5. 문자열 상수를 다룰 때 Python 2라면 기본이 바이트 문자열이라는 점을 감안해 값 비교 로직을 해석한다.

## 명령어/단축키
```python
import dis, marshal
with open("legacy.pyc", "rb") as f:
    f.read(8)   # Python 2는 8바이트 헤더(매직 4 + 타임스탬프 4)
    code = marshal.load(f)
dis.dis(code)
```
```bash
pip install uncompyle6   # Python 2 pyc는 uncompyle6로
uncompyle6 legacy.pyc
```

## 출력 해석
- `PRINT_ITEM` + `PRINT_NEWLINE` 조합이 보이면 원본 소스는 `print "문자열"` 형태의 Python 2 print문이다.
- `BINARY_DIVIDE`가 보이면 해당 나눗셈은 Python 2 기본 규칙(정수/정수는 정수 몫)으로 실행됐다는 뜻이다 — 같은 자리에 `BINARY_TRUE_DIVIDE`가 있다면 Python 3 규칙(실수 결과)이다.
- `STORE_MAP`은 Python 2에서 `{}` 딕셔너리 리터럴을 만들 때 각 키-값 쌍을 개별적으로 저장하던 opcode로, Python 3에서는 `BUILD_MAP`류로 통합되어 다르게 나타난다.

## 흔한 실수
- Python 2 `.pyc`에 decompyle3를 시도하며 시간을 낭비하는 것 — 애초에 지원 대상이 아니다(3.7 이상 전용).
- `dis` 출력의 opcode 이름을 보고 최신 Python 3 문서 기준으로 해석해 `PRINT_ITEM` 같은 것을 모르는 opcode로 취급하는 것 — Python 2 전용 opcode임을 인지해야 한다.
- Python 2 문자열을 무조건 유니코드로 가정하고 비교 로직을 해석해, 실제로는 바이트 단위 비교였던 부분을 놓치는 것.
- 매직 넘버 확인을 생략하고 바로 dis 결과의 opcode 이름만 보고 버전을 추측하다가, 실제로는 특정 3.x 버전에서만 존재했다가 사라진 opcode(예: 3.12 이전의 `PRINT_EXPR` 등 REPL 전용 opcode)와 Python 2 opcode를 혼동하는 것.

## 막혔을 때 다음 체크
- 매직 넘버를 아직 확인하지 않았다면 → REV-1083 .pyc 파일에서 Python 버전(매직 넘버) 확인하기
- Python 2 pyc를 uncompyle6로 돌리는 구체적 방법 → REV-1084 uncompyle6/decompyle3로 .pyc 디컴파일하기
- opcode를 직접 하나씩 읽는 기본기가 필요하면 → REV-1085 Python 바이트코드(dis 모듈)를 직접 읽는 법

## 미니 예제
```text
>>> dis.dis(code)
  1           0 LOAD_CONST               0 ('flag check: ')
              3 PRINT_ITEM
              4 LOAD_FAST                0 (result)
              7 PRINT_ITEM
              8 PRINT_NEWLINE
```
`PRINT_ITEM`이 두 번, 그 뒤에 `PRINT_NEWLINE`이 오는 패턴은 Python 2의 `print "flag check: ", result` (쉼표로 여러 값을 이어 출력하는 print문) 형태를 그대로 보여준다. Python 3였다면 이 자리에 `LOAD_GLOBAL (print)`과 `CALL` opcode가 나왔을 것이다.

## 관련 글
- REV-1083 — .pyc 파일에서 Python 버전(매직 넘버) 확인하기
- REV-1084 — uncompyle6/decompyle3로 .pyc 디컴파일하기
- REV-1085 — Python 바이트코드(dis 모듈)를 직접 읽는 법

## 출처/검증
- Python 2.7 매직 넘버(62211)와 Python 3 계열 매직 넘버 체계의 근본적 차이: CPython 공식 저장소 `Include/internal/pycore_magic_number.h` 이력 기준 (2026-09-10 WebFetch 검증, REV-1083과 동일 출처).
- uncompyle6가 Python 1.5, 2.1~3.8 근방을 지원하고 decompyle3는 3.7 이상만 지원한다는 점(Python 2는 decompyle3 대상 밖): GitHub `rocky/python-uncompyle6`, `rocky/python-decompile3` 공식 README 기준 (2026-09-10 WebSearch 검증).
- `print`문 전용 opcode(`PRINT_ITEM`/`PRINT_NEWLINE`), 정수/실수 나눗셈 opcode 차이(`BINARY_DIVIDE` vs `BINARY_TRUE_DIVIDE`/`BINARY_FLOOR_DIVIDE`), `except E, e:` 문법과 `SETUP_EXCEPT`, Python 2/3의 기본 문자열 타입 차이(bytes vs unicode)는 Python 언어 자체의 공식 변경 이력(PEP 3105 print 함수화, PEP 238 나눗셈 연산자 변경, PEP 3110 예외 처리 구문 변경, PEP 3112 바이트 리터럴)에 기반한 잘 알려진 사실이며, 이번 세션에서 opcode 이름 자체를 CPython 2.7 소스로 재확인하지는 못했으므로 정확한 opcode 스펠링이 중요한 경우 실제 Python 2.7 환경의 `dis` 출력으로 재검증할 것을 권장한다.
