---
id: REV-1085
title: "Python 바이트코드(dis 모듈)를 직접 읽는 법"
slug: "rev-1085-dis-module-bytecode-reading"
category: "other-targets"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [python, dis, marshal]
keywords: ["dis 모듈", "python bytecode 읽기", "dis.dis", "marshal.load", "opcode 직접 분석"]
aliases: ["python 바이트코드 직접 분석", "디컴파일 실패했을 때 대안", "pyc 직접 파싱"]
symptom_keywords: ["디컴파일러가 다 실패해서 pyc를 직접 봐야 함", "dis.dis 결과를 어떻게 읽는지 모름", "LOAD_FAST STORE_FAST가 뭔지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
uncompyle6/decompyle3/pycdc가 전부 실패하거나 결과를 못 믿겠을 때는 파이썬 표준 라이브러리 `dis` 모듈로 바이트코드 명령어를 한 줄씩 직접 읽으면 되는데, `marshal.load()`로 `.pyc`의 code 객체를 불러온 뒤 `dis.dis(code)`에 넘기기만 하면 된다.

## 언제 검색해야 하나
- REV-1084의 모든 디컴파일러가 에러를 내거나 이상한 코드를 출력해서 원본 로직을 신뢰할 수 없을 때
- 최신 Python(3.10 이상)이라 디컴파일러 지원이 아직 부실한 `.pyc`를 다뤄야 할 때
- 디컴파일된 결과의 특정 함수 하나가 의심스러워서 실제 바이트코드로 교차 검증하고 싶을 때

## 핵심 개념

### `.pyc`는 결국 marshal된 code 객체
`.pyc` 파일은 16바이트 헤더(REV-1083) 뒤에 파이썬 `marshal` 모듈로 직렬화된 **code 객체** 하나가 통째로 저장되어 있다. `marshal.load()`는 이 직렬화 포맷을 역직렬화해서 실제 파이썬 `code` 객체(함수의 `__code__` 속성과 동일한 타입)로 복원해준다. 일단 이 code 객체만 손에 넣으면, `dis` 모듈의 모든 기능을 그대로 쓸 수 있다.

### dis.dis()가 보여주는 것
`dis.dis(code)`는 코드 객체 안의 모든 명령어를 사람이 읽기 좋은 표 형태로 출력한다. 각 줄은 대략 다음 정보를 담는다.
- **줄 번호**: 원본 소스에서 이 명령어에 대응하는 줄(디버그 정보가 남아있는 경우).
- **점프 대상 표시(`>>`)**: 다른 명령어가 여기로 점프해온다는 표시.
- **opcode 이름**(예: `LOAD_FAST`, `CALL`, `COMPARE_OP`, `POP_JUMP_IF_FALSE`).
- **정수 인자(oparg)**: 예를 들어 지역 변수 슬롯 번호, 상수 테이블 인덱스.
- **해석된 값(argval/argrepr)**: 괄호 안에 실제 변수 이름, 상수 값, 점프 대상 오프셋 등이 사람이 읽을 수 있게 표시된다.

프로그래밍적으로 각 명령어에 접근하려면 `dis.get_instructions(code)`나 `dis.Bytecode(code)`를 쓰면 `Instruction` 객체(namedtuple 유사)의 나열을 얻을 수 있고, 각 객체에서 `.opname`, `.arg`, `.argval`, `.argrepr`, `.offset` 등을 개별적으로 꺼낼 수 있다.

### 자주 보게 될 opcode를 읽는 요령
- `LOAD_FAST n (변수명)` / `STORE_FAST n (변수명)`: 지역 변수를 스택에 올리거나 스택 값을 지역 변수에 저장.
- `LOAD_CONST n (값)`: 상수 테이블에서 값을 스택에 올림 — 문자열 비교/플래그 값이 여기 자주 등장한다.
- `LOAD_GLOBAL` / `LOAD_ATTR` / `CALL`(3.11 이전은 `CALL_FUNCTION`): 전역 이름 참조, 속성 접근, 함수 호출.
- `COMPARE_OP n (==)`처럼 비교 연산자가 괄호 안에 그대로 표시된다.
- `POP_JUMP_IF_FALSE`/`POP_JUMP_IF_TRUE`: 조건 분기 — CTF 검증 로직의 `if` 문이 거의 항상 이 형태로 나타난다.

### 왜 이 방법이 "최후의 보루"인가
디컴파일러는 바이트코드를 다시 고급 언어 문법(if/for/컴프리헨션 등)으로 재구성하는 복잡한 패턴 매칭을 하기 때문에 버전이 하나만 안 맞아도 실패하거나 틀린 코드를 낼 수 있다. 반면 `dis`는 재구성을 전혀 하지 않고 **인터프리터가 실제로 실행하는 명령어를 있는 그대로** 보여주므로 항상 정확하다(단, 표준 라이브러리 공식 문서가 명시하듯 opcode 집합과 인코딩 자체는 버전마다 달라 "안정된 인터페이스가 아니다"). 읽기는 번거롭지만 절대 거짓말을 하지 않는다는 점이 핵심 가치다.

## 화면/코드에서 보이는 징후
- 디컴파일 결과에 `# WARNING: Decompyle incomplete` 나 이상한 임시 변수명이 섞여 있어 신뢰할 수 없을 때.
- `.pyc` 버전이 uncompyle6/decompyle3/pycdc 어느 것도 지원 범위에 없다고 나올 때.
- 함수 하나만 콕 집어 검증하고 싶은데 전체 디컴파일은 필요 없을 때.

## 가장 먼저 할 것
`marshal.load()`로 code 객체를 얻은 뒤 `dis.dis(code)`를 바로 호출해본다. 파일 헤더가 16바이트(3.7+ 기준)라는 것만 REV-1083에서 확인해두면 된다.

## 단계별 절차
1. REV-1083으로 `.pyc`의 정확한 헤더 길이(3.7+ 기준 16바이트)를 확인한다.
2. 파일을 열어 헤더만큼 `read()`로 건너뛴다.
3. 남은 바이트를 `marshal.load()`로 역직렬화해 code 객체를 얻는다.
4. `dis.dis(code)`로 최상위 코드(모듈 레벨)를 먼저 살펴본다.
5. 관심 있는 함수는 `code.co_consts` 안에 중첩된 code 객체로 들어있으므로, 그 안에서 찾아 `dis.dis(nested_code)`로 다시 들여다본다.
6. `POP_JUMP_IF_FALSE` 주변의 `COMPARE_OP`, 그 앞의 `LOAD_CONST`를 따라가며 비교 대상 상수(플래그 후보)를 찾는다.
7. **주의**: `marshal.load()`는 반드시 `.pyc`를 만든 파이썬과 같은 마이너 버전으로 실행해야 한다. 버전이 다르면 역직렬화 자체가 깨지거나 예외가 난다.

## 명령어/단축키
```python
import marshal, dis

with open("chall.pyc", "rb") as f:
    f.read(16)              # 3.7+ 기준 헤더 16바이트 스킵
    code = marshal.load(f)

dis.dis(code)                # 모듈 최상위 코드 디스어셈블

# 중첩된 함수의 code 객체 찾기
for const in code.co_consts:
    if hasattr(const, "co_name"):
        print(const.co_name)
        dis.dis(const)

# 명령어를 프로그램적으로 순회
for instr in dis.get_instructions(code):
    print(instr.offset, instr.opname, instr.argrepr)
```

## 출력 해석
```text
  3           0 LOAD_FAST                0 (flag)
              2 LOAD_CONST               1 ('CTF{sample_flag}')
              4 COMPARE_OP               2 (==)
              6 POP_JUMP_IF_FALSE        6 (to 12)
              8 LOAD_GLOBAL              0 (print + NULL)
             10 ...
        >>   12 LOAD_GLOBAL              1 (print + NULL)
```
`LOAD_CONST`에서 바로 옆 괄호에 `'CTF{sample_flag}'`처럼 실제 비교 상수가 그대로 보이면, 디컴파일 없이 이 opcode 나열만 읽고도 정답 문자열을 바로 찾을 수 있다. `COMPARE_OP`의 괄호 안 연산자(`==`, `!=`, `<` 등)로 비교 방향도 정확히 알 수 있다.

## 흔한 실수
- `marshal.load()`를 실행 중인 파이썬 버전과 다른 버전의 `.pyc`에 그냥 돌려서 예외를 만나고 "파일이 깨졌다"고 오해하는 것 — 버전을 맞추거나(`pyenv`로 해당 버전 설치), 최소한 REV-1083에서 확인한 매직 넘버와 실행 중인 인터프리터의 `importlib.util.MAGIC_NUMBER`가 일치하는지 먼저 확인한다.
- 헤더 길이를 3.7+ 기준 16바이트로 고정해서 그보다 오래된 `.pyc`(8바이트 헤더)에 잘못 적용하는 것.
- opcode 이름과 인자만 보고 제어 흐름(반복문 구조 등)을 완벽히 손으로 복원하려다 시간을 낭비하는 것 — 필요한 부분(비교 상수, 분기 조건)만 빠르게 짚어내는 용도로 쓰는 게 효율적이다.
- 파이썬 버전 간 opcode 이름이 다르다는 걸 모르고(예: 3.11부터 `CALL_FUNCTION`이 `CALL`로 바뀜) 예전 글의 opcode 이름을 최신 버전에 그대로 대입해 헷갈리는 것.

## 막혔을 때 다음 체크
- 먼저 파이썬 버전/매직 넘버부터 확인하지 않았다면 → REV-1083 .pyc 파일에서 Python 버전(매직 넘버) 확인하기
- 디컴파일러를 아직 안 써봤다면 먼저 시도해볼 가치가 있다 → REV-1084 uncompyle6/decompyle3로 .pyc 디컴파일하기
- Python 2 바이트코드라 opcode 자체가 낯설다면 → REV-1087 Python 2 vs 3 바이트코드 차이가 리버싱에 미치는 영향
- PyArmor 등으로 코드 자체가 암호화/난독화되어 있어 marshal.load조차 정상 code 객체를 안 준다면 → REV-1086 PyArmor로 난독화된 Python 스크립트 알아보기

## 미니 예제
```python
>>> import marshal, dis
>>> with open("check.pyc", "rb") as f:
...     f.read(16)
...     code = marshal.load(f)
...
>>> for c in code.co_consts:
...     if hasattr(c, "co_name") and c.co_name == "check_flag":
...         dis.dis(c)
...
  2           0 RESUME                   0
  3           2 LOAD_FAST                0 (user_input)
              4 LOAD_CONST               1 ('CTF{h1dd3n_1n_byt3c0d3}')
              6 COMPARE_OP              40 (==)
             10 POP_JUMP_IF_FALSE        4 (to 20)
```
디컴파일러 없이도 `LOAD_CONST` 한 줄에서 정답 플래그 문자열이 그대로 드러난다. 이런 식으로 "비교 상수 찾기" 목적이라면 굳이 완전한 소스 재구성 없이 `dis` 출력만으로 CTF 문제를 풀 수 있는 경우가 많다.

## 관련 글
- REV-1083 — .pyc 파일에서 Python 버전(매직 넘버) 확인하기
- REV-1084 — uncompyle6/decompyle3로 .pyc 디컴파일하기
- REV-1087 — Python 2 vs 3 바이트코드 차이가 리버싱에 미치는 영향
- REV-1086 — PyArmor로 난독화된 Python 스크립트 알아보기

## 출처/검증
- `dis` 모듈 API(`dis.dis`, `dis.get_instructions`, `dis.Bytecode`, `Instruction` 필드), 출력 컬럼 구성, marshal 기반 pyc 역직렬화 방법, 버전별 바이트코드 포맷 변화(3.6 고정 2바이트 명령어, 3.10 점프 오프셋 변경, 3.11 CACHE/적응형 바이트코드 도입 등), "bytecode는 안정된 인터페이스가 아니다"라는 공식 경고: Python 공식 문서 `dis — Disassembler for Python bytecode` 기준 (2026-09-10 WebFetch로 원문 확인).
