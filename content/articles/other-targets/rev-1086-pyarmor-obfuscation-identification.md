---
id: REV-1086
title: "PyArmor로 난독화된 Python 스크립트 알아보기"
slug: "rev-1086-pyarmor-obfuscation-identification"
category: "other-targets"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [python, strings]
keywords: ["PyArmor 식별", "pyarmor_runtime", "__pyarmor__", "python 난독화", "pytransform"]
aliases: ["파이썬 난독화 확인법", "PyArmor 스크립트인지 확인", "pyarmor_runtime_000000이 뭔지"]
symptom_keywords: [".py 파일을 열었는데 알아볼 수 없는 바이트 문자열과 __pyarmor__ 호출만 있음", "pyarmor_runtime 폴더가 같이 있는데 뭔지 모름", "pyc를 디컴파일했더니 의미없는 바이트 배열만 나옴"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`.py` 파일을 열었는데 코드 대부분이 사라지고 `from pyarmor_runtime_000000 import __pyarmor__`로 시작해서 `__pyarmor__(__name__, __file__, b'...')`처럼 긴 바이트 리터럴을 통째로 넘기는 한두 줄만 있다면, 이는 **PyArmor**로 난독화(정확히는 바이트코드 암호화)된 스크립트이며 일반 디컴파일러(REV-1084)로는 뚫리지 않는다.

## 언제 검색해야 하나
- `.py` 소스를 받았는데 사람이 짠 코드가 전혀 안 보이고 `pyarmor_runtime`이라는 이름의 폴더나 모듈 임포트가 같이 딸려 있을 때
- pyinstxtractor로 뽑은 `.pyc`를 디컴파일했는데 정상적인 로직 대신 의미 없는 바이트 배열과 `__pyarmor__` 호출 하나만 나올 때
- 배포 폴더 안에 `pyarmor_runtime.so`/`pyarmor_runtime.pyd` 같은 확장자를 가진 바이너리 파일이 함께 있을 때

## 핵심 개념

### PyArmor가 하는 일
PyArmor는 파이썬 스크립트의 바이트코드를 암호화하고, 원본 `.py` 파일 자리에는 이 암호화된 데이터를 런타임에 복호화해서 실행해주는 아주 짧은 "로더" 코드만 남겨두는 상용 난독화 도구다. 실제 복호화/실행 로직은 C로 작성되어 컴파일된 별도의 확장 모듈(공유 라이브러리)이 담당하기 때문에, 파이썬 레벨에서 아무리 디스어셈블해도 진짜 로직은 보이지 않는다.

### 실제로 보이는 코드 형태(PyArmor 9.x 기준)
PyArmor 공식 문서에 따르면 난독화된 파일은 다음과 같은 형태를 그대로 갖는다.

```python
from pyarmor_runtime_000000 import __pyarmor__
__pyarmor__(__name__, __file__, b'\xa1\x2b...(긴 바이트 리터럴)...')
```

즉 `pyarmor_runtime_000000`이라는 이름의 패키지에서 `__pyarmor__`라는 함수를 가져와서, 모듈 이름/파일 경로/암호화된 바이트 블롭을 인자로 즉시 호출하는 두 줄이 전부다. 이 `pyarmor_runtime_000000` 패키지는 실행 파일과 같은 폴더에 함께 배포되며 내부 구성은 다음과 같다.

- `__init__.py`
- `pyarmor_runtime.so`(Linux) 또는 이에 대응하는 확장 모듈(Windows에서는 `.pyd`) — 실제 복호화/실행을 담당하는 컴파일된 확장 모듈. 라이선스나 만료 기간, 기기 바인딩 같은 제어 정보도 보통 이 안에 내장된다.

이 런타임 패키지는 폴더째로 다른 위치로 옮겨도 일반적인 파이썬 import 규칙만 지키면 계속 동작하도록 설계되어 있다.

### 왜 일반 디컴파일이 안 통하는가
uncompyle6/decompyle3(REV-1084)나 `dis` 모듈(REV-1085)은 표준 CPython 바이트코드를 대상으로 하는데, PyArmor로 암호화된 블롭은 애초에 표준 marshal 포맷의 code 객체가 아니라 PyArmor 자체 포맷으로 암호화된 바이너리 데이터다. 이 데이터는 `pyarmor_runtime` 확장 모듈이 실행 시점에 메모리 안에서만 복호화하고, 복호화된 실제 code 객체는 디스크에 다시 쓰이지 않는다. 그래서 정적으로 파일만 보고 있어서는 원본 로직에 도달할 수 없고, 실행 중 메모리를 덤프하거나(동적 분석) 확장 모듈 자체를 리버싱해서 복호화 로직을 재현하는 접근이 필요하다.

### 버전에 따라 세부 형태가 다를 수 있다는 점
위 형태는 최신 PyArmor(9.x)의 공식 문서에서 확인한 내용이다. 구버전(예: PyArmor 6.x/7.x)은 `pytransform`이라는 다른 이름의 런타임 모듈과 `__pyarmor__` 대신 다른 진입점 이름을 쓰는 등 세부 문자열이 다를 수 있다는 보고가 있으나, 이 글에서는 그 구버전 형식까지 실제 문서로 재확인하지는 못했다(아래 출처/검증 참고). 실전에서 마주친 파일의 정확한 임포트 문/함수 이름이 여기 설명과 다르더라도, "런타임 패키지를 import해서 바이트 블롭 하나를 통째로 넘기는 한두 줄짜리 로더" 패턴 자체는 PyArmor 계열의 공통 특징으로 봐도 무방하다.

## 화면/코드에서 보이는 징후
- `.py` 파일 전체가 단 2~3줄이고, 그중 하나가 `import`, 나머지가 매우 긴 `b'...'` 바이트 리터럴을 인자로 하는 함수 호출이다.
- 같은 폴더에 `pyarmor_runtime_000000` (또는 유사한 이름의) 폴더나 모듈이 함께 배포되어 있다.
- `strings`로 해당 확장 모듈(`.so`/`.pyd`)을 훑으면 `pyarmor`, `PyArmor`, `pytransform` 같은 문자열이 나온다.
- 실행하면 정상 동작하지만, 코드를 열어봐도 로직을 전혀 알 수 없는 "블랙박스" 상태다.

## 가장 먼저 할 것
`.py` 파일 맨 위 두 줄만 봐도 판별이 끝난다. `pyarmor_runtime`으로 시작하는 임포트와 `__pyarmor__(...)` 형태의 즉시 호출이 보이면 PyArmor로 확정하고, 일반 디컴파일 시도(REV-1084/1085)는 시간 낭비이므로 바로 동적 분석 전략으로 전환한다.

## 단계별 절차
1. `.py` 소스 파일을 열어 임포트 문에 `pyarmor_runtime`류 이름이 있는지 확인한다.
2. 같이 배포된 폴더에서 `pyarmor_runtime.so`/`.pyd` 같은 확장 모듈을 찾는다.
3. `strings pyarmor_runtime.so | grep -i pyarmor`로 이름을 재확인한다.
4. 정적 디컴파일(REV-1084/1085)은 통하지 않으므로, 실행 중 메모리에서 복호화된 code 객체를 가로채는 동적 접근(예: `sys.settrace`/`sys.setprofile` 후킹, 또는 실행 중 프로세스 메모리 덤프)이 필요하다는 점을 인지한다.
5. CTF 맥락이라면 "완전한 소스 복원"보다 "실행 중 값 관찰"(입력에 따라 어떻게 분기하는지 blackbox로 테스트)이 더 현실적인 경우가 많다.

## 명령어/단축키
```bash
# 임포트 줄만 빠르게 확인
head -n 3 obfuscated_script.py

# 동봉된 런타임 확장 모듈에서 문자열 확인
strings pyarmor_runtime_000000/pyarmor_runtime.so | grep -i "pyarmor\|pytransform"
```

## 출력 해석
- `from pyarmor_runtime_000000 import __pyarmor__` + `__pyarmor__(__name__, __file__, b'...')` 두 줄만 보이면 PyArmor 난독화가 100% 확정이다.
- `strings` 결과에 `pyarmor`/`PyArmor` 브랜드 문자열이 나오면 어떤 버전 계열인지까지는 몰라도 PyArmor 제품군이라는 것은 확실하다.
- 이 시점에서는 "코드가 안 보인다"는 사실 자체가 문제 풀이의 힌트일 수 있다 — CTF에서 굳이 완전한 정적 디컴파일을 요구하지 않고 동적 관찰만으로 풀리게 설계된 경우도 많다.

## 흔한 실수
- 일반 pyc 디컴파일러(uncompyle6 등)를 계속 돌리며 시간을 낭비하는 것 — 이 데이터는 애초에 표준 marshal 포맷이 아니다.
- `__pyarmor__` 호출에 넘어가는 바이트 블롭을 "그냥 base64나 XOR로 인코딩된 텍스트"라고 착각하고 수동 디코딩을 시도하는 것 — 이는 PyArmor 자체 바이너리 포맷이며 단순 인코딩이 아니다.
- 런타임 확장 모듈(`pyarmor_runtime.so` 등) 없이 `.py` 파일 하나만 갖고 실행/분석하려는 것 — 이 파일은 반드시 짝이 되는 확장 모듈과 함께 있어야 동작한다.
- 라이선스/만료 검증이 확장 모듈 안에 내장되어 있을 수 있다는 점을 간과하고, 원본 배포 환경과 다른 곳(다른 OS, 다른 파이썬 버전)에서 실행해보려다 실행 자체가 막히는 것.

## 막혔을 때 다음 체크
- 일반 pyc라고 착각해 디컴파일을 먼저 시도했다면 → REV-1084 uncompyle6/decompyle3로 .pyc 디컴파일하기
- pyc 자체를 다시 확인하고 싶다면 → REV-1083 .pyc 파일에서 Python 버전(매직 넘버) 확인하기
- 바이트코드를 직접 봐도 안 풀리는 이유가 이 암호화 때문인지 확인하려면 → REV-1085 Python 바이트코드(dis 모듈)를 직접 읽는 법

## 미니 예제
```python
# obfuscated_check.py 전체 내용
from pyarmor_runtime_000000 import __pyarmor__
__pyarmor__(__name__, __file__, b'\x50\x59\x41\x52\x4d\x4f\x52\x00...(중략, 수백 바이트)...')
```
같은 폴더에는 다음이 함께 있다.
```text
obfuscated_check.py
pyarmor_runtime_000000/
├── __init__.py
└── pyarmor_runtime.so
```
이 구조를 보는 순간 "이 스크립트는 PyArmor로 암호화됐고, 정적 디컴파일로는 원본 로직을 볼 수 없다"고 바로 결론짓고, 동적 분석(입력값을 바꿔가며 실행 결과 관찰, 혹은 프로세스 메모리 덤프)으로 전략을 전환하는 것이 실전적인 다음 행동이다.

## 관련 글
- REV-1084 — uncompyle6/decompyle3로 .pyc 디컴파일하기
- REV-1085 — Python 바이트코드(dis 모듈)를 직접 읽는 법
- REV-1081 — PyInstaller로 패키징된 실행파일 식별하는 법

## 출처/검증
- 최신 PyArmor(9.x)의 난독화 스크립트 형태(`from pyarmor_runtime_000000 import __pyarmor__`, `__pyarmor__(__name__, __file__, b'...')` 호출부), 런타임 패키지 구성(`__init__.py` + `pyarmor_runtime.so`/확장 모듈), 런타임 키가 확장 모듈에 내장된다는 점: PyArmor 공식 문서(pyarmor.readthedocs.io, "Understanding Obfuscated Script" 페이지) 기준 (2026-09-10 WebFetch로 원문 확인).
- 구버전(PyArmor 6.x/7.x대)에서 `pytransform` 등 다른 모듈명을 썼다는 정보는 이번 조사에서 공식 문서로 재확인하지 못했으므로, 정확한 구버전 문자열이 필요하다면 별도로 해당 버전 공식 문서나 실제 샘플을 확인할 것.
