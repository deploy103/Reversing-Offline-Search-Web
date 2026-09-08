---
id: REV-0300
title: "Z3 angr pwntools Python 오프라인 패키지 준비"
slug: "rev-0300-offline-python-packages"
category: "tools"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["Python", "pwntools", "Z3", "angr", "Capstone", "Unicorn"]
keywords: ["pip download", "pip install --no-index", "오프라인 pip 설치", "pwntools 오프라인", "z3-solver 오프라인", "angr 오프라인 설치", "offline wheels"]
aliases: ["파이썬 패키지 오프라인 설치", "pip 오프라인 캐시", "인터넷 없이 pip install", "오프라인 wheel 준비"]
symptom_keywords: ["대회장에 인터넷이 없는데 pip install이 안됨", "pip install 인터넷 필요", "오프라인에서 z3 angr pwntools 설치하는 법을 모름"]
source_ids: ["SRC-PYTHON-PIP-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`pip download -d ./offline-wheels <패키지>`로 인터넷이 되는 동안 필요한 wheel 파일을 폴더 하나에 전부 모아두면, 대회 당일 인터넷이 전혀 없는 PC에서도 `pip install --no-index --find-links=./offline-wheels <패키지>`만으로 `z3-solver`, `angr`, `pwntools`, `capstone`, `unicorn`을 그대로 설치할 수 있다.

## 언제 검색해야 하나
- 오프라인 CTF 대회를 앞두고 Python 자동화/솔버 환경을 미리 준비해야 할 때
- 대회 당일 `pip install pwntools`를 쳤는데 인터넷이 없어서 실패했을 때
- 팀원마다 다른 PC에 같은 패키지 세트를 반복해서 설치해야 할 때
- Python 버전이 대회 PC와 달라서 설치한 wheel이 안 맞는 이유를 모를 때

## 핵심 개념

### 왜 그냥 `pip install`이 오프라인에서 안 되는가
`pip install <패키지>`는 기본적으로 PyPI(Python Package Index, `pypi.org`)라는 온라인 저장소에 접속해서 패키지 파일(wheel 또는 소스 배포판)을 내려받은 뒤 설치한다. 인터넷이 없으면 이 다운로드 단계 자체가 실패하므로 설치가 진행되지 않는다. 해결책은 "다운로드"와 "설치"를 분리하는 것이다 — 인터넷이 되는 시점에 파일만 미리 받아두고(`pip download`), 나중에 그 로컬 파일로부터 설치(`pip install --no-index --find-links=...`)하면 된다.

### wheel이란
`.whl` 확장자를 가진 파일로, 이미 빌드가 끝난 상태의 파이썬 패키지 배포 형식이다. 순수 파이썬 코드만 있는 패키지는 플랫폼에 상관없이 동작하는 wheel(`py3-none-any.whl`)로 배포되지만, `z3-solver`나 `capstone`, `unicorn`처럼 C/C++로 구현된 네이티브 확장을 포함한 패키지는 **운영체제(Windows/Linux)와 아키텍처(x86/x64), 그리고 Python 버전마다 다른 wheel 파일**이 필요하다. 이 점이 오프라인 준비에서 가장 자주 발목을 잡는 부분이다.

### Python 버전 호환성 — 가장 흔한 함정
wheel 파일 이름에는 `cp311`, `cp312`처럼 대상 CPython 버전이 명시되어 있다(예: `z3_solver-4.13.0-py2.py3-none-manylinux...whl`처럼 순수 파이썬은 버전 무관, 반면 네이티브 확장 포함 패키지는 `-cp311-cp311-win_amd64.whl`처럼 특정 버전 전용인 경우가 많다). **`pip download`를 실행하는 PC의 Python 버전과, 실제로 오프라인에서 설치할 대회 PC의 Python 버전이 다르면 wheel이 안 맞아 설치가 실패**한다. 따라서 반드시 대회 당일 사용할 Python 버전과 최대한 동일한 버전으로 `pip download`를 실행해야 한다. 필요하다면 `--python-version`, `--platform`, `--only-binary=:all:` 옵션으로 목표 환경을 명시해서 다운로드할 수 있다(단, 이 옵션들은 대상 환경이 다운로드 환경과 다를 때 완벽히 재현되지 않을 수 있으므로, 가능하면 아예 동일한 OS/Python 버전 PC에서 다운로드하는 것이 가장 안전하다).

## 화면/코드에서 보이는 징후
오프라인 상태에서 `pip install <패키지>`를 시도하면 다음과 비슷한 오류가 뜬다.
```
WARNING: Retrying ... Failed to establish a new connection
ERROR: Could not find a version that satisfies the requirement pwntools
ERROR: No matching distribution found for pwntools
```
이 메시지가 보이면 네트워크 연결 문제이지 패키지 이름이나 오타 문제가 아니다.

## 가장 먼저 할 것
인터넷이 되는 동안(대회 며칠 전), 대회 당일과 동일한 Python 버전이 설치된 PC에서 다음을 실행해 wheel을 한 폴더에 모은다.
```bash
python3 -m venv build-env
build-env\Scripts\activate    # Windows
# 또는
source build-env/bin/activate # Linux

pip download -d ./offline-wheels z3-solver angr pwntools capstone unicorn
```

## 단계별 절차

### 1) 온라인 상태에서 wheel 모으기
```bash
mkdir offline-wheels
pip download -d ./offline-wheels z3-solver angr pwntools capstone unicorn keystone-engine
```
`pip download`는 지정한 패키지뿐 아니라 **의존성 패키지까지 전부** 같은 폴더에 받아준다(`angr`은 의존성이 특히 많으므로 다운로드에 시간이 좀 걸릴 수 있다). 이 폴더를 통째로 오프라인 대회용 USB/외장 SSD에 복사해 둔다.

### 2) 다운로드 결과 확인
```bash
ls offline-wheels | wc -l   # 파일 개수 확인(수십~백여 개가 정상)
```
`angr` 하나만 해도 `claripy`, `cle`, `pyvex`, `archinfo`, `capstone`, `unicorn` 등 여러 하위 패키지에 의존하므로, 폴더 안에 예상보다 훨씬 많은 wheel 파일이 쌓이는 것이 정상이다.

### 3) requirements.txt로 관리(팀 단위 준비에 권장)
필요한 패키지 목록을 파일로 관리하면 팀원 전체가 같은 세트를 재현하기 쉽다.
```text
# requirements.txt
pwntools
z3-solver
angr
capstone
unicorn
keystone-engine
```
```bash
pip download -d ./offline-wheels -r requirements.txt
```

### 4) 오프라인 PC에서 설치
대회 당일, 인터넷이 없는 PC에서 USB/외장 SSD에 담아온 `offline-wheels` 폴더를 이용해 설치한다.
```bash
pip install --no-index --find-links=./offline-wheels pwntools z3-solver angr capstone unicorn
```
- `--no-index`: PyPI 등 온라인 인덱스에 접속하지 않겠다는 뜻.
- `--find-links=./offline-wheels`: 대신 이 로컬 폴더에서 패키지 파일을 찾으라는 뜻.

`requirements.txt`를 함께 준비했다면 한 줄로 전체 설치가 가능하다.
```bash
pip install --no-index --find-links=./offline-wheels -r requirements.txt
```

### 5) 설치 검증
```bash
python3 -c "import pwn, z3, angr, capstone, unicorn; print('OK')"
```
오류 없이 `OK`가 출력되면 오프라인 설치가 완전히 끝난 것이다.

## 명령어/단축키
```bash
pip download -d ./offline-wheels <패키지 목록>              # 온라인 상태에서 wheel 모으기
pip download -d ./offline-wheels -r requirements.txt         # requirements.txt 기반 다운로드
pip install --no-index --find-links=./offline-wheels <패키지>  # 오프라인 설치
pip install --no-index --find-links=./offline-wheels -r requirements.txt  # 오프라인 일괄 설치
python -m venv build-env                                     # 격리된 다운로드/테스트 환경 준비
pip --version                                                 # pip 자체 버전 확인
python --version                                               # Python 버전 확인(대회 PC와 일치해야 함)
```

## 출력 해석
- `pip download` 중 `Saved ./offline-wheels/xxx.whl`가 반복해서 뜨는 것은 정상 진행 상황이다.
- `ERROR: No matching distribution found for angr`가 오프라인 설치 단계에서 뜨면, 다운로드 시점의 Python 버전/OS와 설치 대상 PC의 Python 버전/OS가 다를 가능성이 가장 크다 — wheel 파일 이름의 `cp3XX`, `win_amd64`/`manylinux` 표기를 직접 확인해서 대상 환경과 일치하는지 대조한다.
- `angr` 설치 후 `import angr`가 매우 느리게(수 초) 처음 로드되는 것은 정상이다(내부적으로 여러 하위 모듈을 초기화하기 때문) — 오류가 아니다.

## 흔한 실수
- 다운로드용 PC와 대회 당일 PC의 Python 버전이 다른 것을 확인하지 않고 진행해서, 당일 설치가 실패하는 것 — 반드시 동일한 `python --version`을 사용하는 PC에서 `pip download`를 실행해야 한다.
- Windows용 wheel만 받아두고 대회 PC가 Linux(또는 그 반대)인 것을 뒤늦게 발견하는 것 — OS가 다르면 네이티브 확장 포함 패키지(특히 `unicorn`, `capstone`, `z3-solver`)는 100% 재다운로드해야 한다.
- `pip download`로 의존성까지 다 받았다고 착각하고 `--no-deps` 옵션을 실수로 넣어 정작 필요한 하위 패키지가 빠지는 것.
- 오프라인 설치 시 `--no-index`를 빼먹어서, 대회장에 인터넷이 살짝이라도 있으면 로컬 폴더 대신 다시 온라인에서 받으려다 실패하는 것 — 로컬 폴더만 쓰도록 명시하는 습관이 안전하다.
- venv(가상환경) 없이 시스템 전역 Python에 계속 설치/삭제를 반복해서 팀원 PC마다 패키지 버전이 미묘하게 달라지는 것 — `python -m venv`로 격리된 환경을 만들어 관리하면 재현성이 훨씬 좋아진다.

## 막혔을 때 다음 체크
- `pwntools`로 실제 익스플로잇 스크립트를 어떻게 짜는지 → [pwntools로 프로세스 실행하고 입력 보내기](../automation/rev-0266-pwntools-process-basics.md), [pwntools p32 p64 u32 u64](../automation/rev-0267-pwntools-packing.md)
- `z3-solver`로 제약 조건을 실제로 어떻게 푸는지 → [Z3 BitVec 기초](../automation/rev-0268-z3-bitvec-basics.md), [Z3로 문자 조건 풀기](../automation/rev-0269-z3-solving-char-constraints.md)
- `angr`로 심볼릭 실행을 시작하는 방법 → [angr 심볼릭 실행 기초](../automation/rev-0271-angr-basics.md)
- `checksec`도 `pwntools`에 딸려오므로 함께 준비하면 좋다 → [checksec 설치와 사용법](./rev-0295-checksec-install-usage.md)

## 미니 예제
대회 3일 전, 발표된 대회 환경이 "Ubuntu 22.04, Python 3.10"이라고 공지되었다고 하자. 같은 조건의 로컬 VM에서:
```bash
python3 --version
# Python 3.10.12

python3 -m venv build-env
source build-env/bin/activate
pip install --upgrade pip
pip download -d ./offline-wheels pwntools z3-solver angr capstone unicorn keystone-engine
```
받은 `offline-wheels` 폴더(보통 수백 MB)를 외장 SSD로 대회장에 가져간 뒤, 인터넷이 차단된 대회 PC(동일하게 Ubuntu 22.04, Python 3.10)에서:
```bash
pip install --no-index --find-links=./offline-wheels pwntools z3-solver angr capstone unicorn keystone-engine
python3 -c "import pwn, z3, angr; print('ready')"
```
`ready`가 출력되면 인터넷 없이도 pwntools 익스플로잇, Z3 제약 조건 풀이, angr 심볼릭 실행을 모두 바로 시작할 수 있는 상태다.

## 관련 글
- REV-0295 — checksec 설치와 사용법
- REV-0298 — dnSpyEx ILSpy 설치와 사용법
- REV-0299 — JADX apktool adb 설치와 사용법

## 출처/검증
- `pip download`, `--no-index`, `--find-links` 옵션 동작: pip 공식 문서(pip.pypa.io, "pip download", "pip install") 기준.
- wheel 파일명 규칙(`cpXY`, 플랫폼 태그)과 순수 파이썬 vs 네이티브 확장 wheel의 차이: Python Packaging User Guide(packaging.python.org) 기준.
- `z3-solver`, `angr`, `pwntools`, `capstone`, `unicorn`이 PyPI에 배포되는 패키지라는 사실은 각 프로젝트의 공식 PyPI 페이지 기준이며, 최신 배포 상세(지원 Python 버전 범위 등)는 대회 준비 시점에 각 패키지의 PyPI 페이지에서 다시 확인해야 한다.
- 이 문서의 명령어는 실제 오프라인 환경 재현으로 검증하지 못했다. 특히 `angr`은 의존성 트리가 크고 자주 갱신되므로, 사전 준비 단계에서 반드시 `pip download` → 별도 오프라인(네트워크 차단) 환경에서 `pip install --no-index`까지 실제로 리허설할 것을 권장한다.
