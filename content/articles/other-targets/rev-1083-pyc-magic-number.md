---
id: REV-1083
title: ".pyc 파일에서 Python 버전(매직 넘버) 확인하기"
slug: "rev-1083-pyc-magic-number"
category: "other-targets"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [python, "HxD", ImHex]
keywords: ["pyc 매직 넘버", "python magic number", "MAGIC_NUMBER", "pyc 헤더 구조", "python 버전 확인"]
aliases: ["pyc 버전 확인법", "pyc 헤더 읽는 법", "Bad magic number 에러"]
symptom_keywords: ["pyc 파일을 어느 python 버전으로 만들었는지 모름", "uncompyle6 실행했더니 Bad magic number 에러가 남", "pyc 파일 첫 4바이트가 뭘 의미하는지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
모든 `.pyc` 파일은 맨 앞 4바이트에 "매직 넘버(magic number)"를 담고 있고, 이 값이 어느 CPython 버전에서 만들어졌는지를 정확히 알려주므로, 디컴파일러(uncompyle6/decompyle3)나 `dis` 모듈을 고르기 전에 이 4바이트부터 확인하는 것이 순서다.

## 언제 검색해야 하나
- pyinstxtractor로 뽑은 `.pyc`가 어느 파이썬 버전 것인지 콘솔 로그를 놓쳐서 모를 때
- uncompyle6/decompyle3를 돌렸는데 `Bad magic number` 또는 `RuntimeError: Bad magic number in .pyc file` 에러가 날 때
- `.pyc` 파일 하나만 달랑 주어졌고 실행 환경이나 출처 정보가 전혀 없을 때

## 핵심 개념

### pyc 헤더 16바이트 구조
Python 3.7 이후 `.pyc` 파일의 헤더는 총 16바이트로 고정되어 있다.

| 오프셋 | 길이 | 의미 |
|---|---|---|
| 0~3 | 4바이트 | 매직 넘버(리틀 엔디안 정수) + 고정 `0d 0a`(`\r\n`) |
| 4~7 | 4바이트 | 플래그 비트필드(0이면 타임스탬프 기반, 최하위 비트가 1이면 해시 기반 `.pyc`) |
| 8~15 | 8바이트 | 타임스탬프 기반이면 mtime(4바이트)+소스 크기(4바이트), 해시 기반이면 소스 해시값 |

이 16바이트 뒤에 곧바로 `marshal` 모듈로 직렬화된 code 객체가 이어진다. Python 3.7 미만(2.x, 3.0~3.6)은 헤더가 더 짧아서(예: 3.3~3.6은 8바이트: 매직넘버 4바이트+타임스탬프 4바이트) 버전별 차이를 감안해야 한다.

### 매직 넘버 값은 왜 계속 바뀌는가
CPython 공식 소스(`Lib/importlib/_bootstrap_external.py`, 내부적으로 `Include/internal/pycore_magic_number.h`에서 관리)에 따르면, 매직 넘버는 바이트코드 포맷이나 오프코드 집합이 바뀔 때마다(새 opcode 추가/제거, 인코딩 방식 변경 등) 값이 올라간다. 목적은 서로 다른 인터프리터 버전이 호환되지 않는 `.pyc`를 실수로 실행하지 못하게 막는 것이다. 같은 마이너 버전의 패치 릴리스끼리는(예: 3.11.0과 3.11.9) 보통 같은 매직 넘버를 공유하지만, 마이너 버전이 바뀌면(3.10 → 3.11) 거의 항상 값이 달라진다.

### 버전별 매직 넘버(정수값) 표
CPython 공식 헤더 파일의 버전 이력에 기록된, 각 마이너 버전의 최종 매직 넘버는 다음과 같다.

| Python 버전 | 매직 넘버(정수) |
|---|---|
| 2.7 | 62211 |
| 3.0 | 3131 |
| 3.1 | 3151 |
| 3.2 | 3180 |
| 3.3 | 3230 |
| 3.4 | 3310 |
| 3.5 | 3351 |
| 3.6 | 3379 |
| 3.7 | 3394 |
| 3.8 | 3413 |
| 3.9 | 3425 |
| 3.10 | 3439 |
| 3.11 | 3495 |
| 3.12 | 3531 |
| 3.13 | 3571 |

이 값은 파일의 첫 2바이트를 리틀 엔디안 16비트 정수로 읽은 값이다(예: 3.8의 3413을 16진수로 나타내면 `0x0D55`이며, 리틀 엔디안이므로 파일에는 `55 0D`로 저장되고, 그 뒤에 고정 트레일러 `0D 0A`가 따라와 파일 앞 4바이트는 `55 0D 0D 0A`가 된다). 정확한 매칭이 필요하다면 직접 계산하기보다 아래 "명령어" 섹션의 파이썬 코드로 실제 값을 재현해 비교하는 것이 안전하다.

### CTF에서 실전적으로 확인하는 법
가장 확실한 방법은 직접 계산이나 표 암기가 아니라, **같은 표를 가진 도구에게 물어보는 것**이다. 로컬에 여러 파이썬 버전이 있다면 각 버전의 `import importlib.util; importlib.util.MAGIC_NUMBER`를 실행해 비교하거나, `uncompyle6`/`decompyle3`가 내부적으로 쓰는 `xdis` 라이브러리의 `xdis.magics` 모듈(버전-매직넘버 매핑을 갖고 있음)을 이용해도 된다.

## 화면/코드에서 보이는 징후
- 헥스 에디터(HxD, ImHex)로 `.pyc`를 열었을 때 앞 2바이트가 특정 값이고 이어서 `0D 0A`가 보인다.
- uncompyle6/decompyle3 실행 시 `RuntimeError: Bad magic number in .pyc file`, 또는 파이썬 자체 실행 시 `ImportError: Bad magic number in .pyc file` 에러 메시지가 나온다.
- pyinstxtractor 로그에 `[+] Python version: 39` 처럼 이미 버전이 찍혀 있는 경우도 있다(이 경우 이 글의 수동 확인은 교차 검증용).

## 가장 먼저 할 것
파이썬 인터프리터가 있다면 아래 스니펫으로 `.pyc`의 앞 2바이트를 정수로 읽어 표와 대조한다. 파이썬이 없는 환경이라면 헥스 에디터로 앞 4바이트만 확인해도 된다.

## 단계별 절차
1. `.pyc` 파일을 바이너리 모드로 열어 앞 4바이트를 읽는다.
2. 앞 2바이트를 리틀 엔디안 정수로 변환한다.
3. 위 표(또는 `xdis.magics`)와 대조해 어느 CPython 버전인지 특정한다.
4. 버전을 알았으면 REV-1084(디컴파일러 선택)로 넘어간다 — 3.7~3.8이면 decompyle3/uncompyle6, 3.9는 decompyle3, 3.10 이상이면 pycdc 계열을 고려한다.
5. 만약 이 파일이 pyinstxtractor로 추출한 것이라 헤더가 잘려 있다면(순수 code 객체만 marshal되어 저장된 경우), 이미 알고 있는 pyinstxtractor 로그의 버전 정보를 그대로 쓴다.

## 명령어/단축키
```python
# 파이썬으로 pyc 헤더의 매직 넘버 직접 읽기
with open("mystery.pyc", "rb") as f:
    magic = f.read(4)

print(magic.hex())          # 예: 550d0d0a
print(int.from_bytes(magic[:2], "little"))  # 예: 3413 -> Python 3.8

# 현재 인터프리터의 매직 넘버 확인(버전 비교용)
python3 -c "import importlib.util; print(importlib.util.MAGIC_NUMBER)"
```

## 출력 해석
- 정수값이 표의 3413이면 Python 3.8, 3439면 3.10처럼 표에서 바로 버전을 찾을 수 있다.
- 값이 표에 없는 애매한 숫자라면 alpha/beta 릴리스에서 개발 중 여러 번 바뀐 값일 수 있다(예: 3.12 개발 중에는 3513~3527 사이 여러 값이 존재했다). 이 경우 "3.12 계열이다" 정도까지만 확신하고, 정확한 패치 버전은 디컴파일 시도 결과로 보정한다.
- 4바이트 중 뒤 2바이트가 `0D 0A`가 아니라면애초에 이 파일이 표준 `.pyc` 헤더 포맷이 아니거나(PyArmor 등으로 추가 난독화된 경우 REV-1086 참고), 헤더가 잘려 나간 상태일 수 있다.

## 흔한 실수
- 매직 넘버 값을 외워서 암산으로 판단하려다 alpha/beta 릴리스의 중간값과 헷갈리는 것 — 위 표는 각 마이너 버전의 "최종" 값이며, 개발 중 릴리스는 다를 수 있다.
- pyinstxtractor로 뽑은 `.pyc`가 항상 완전한 16바이트 헤더를 갖고 있다고 가정하는 것 — 일부 추출 경로에서는 헤더 없이 순수 code 객체만 저장되어 있어 이 글의 방법이 바로 적용되지 않을 수 있다.
- 3.7 이전 버전(헤더가 16바이트가 아닌 8바이트)에 3.7 이후 기준 오프셋을 그대로 적용해 플래그/타임스탬프 필드를 잘못 읽는 것.

## 막혔을 때 다음 체크
- 버전을 확인했으면 바로 디컴파일 도구를 고른다 → REV-1084 uncompyle6/decompyle3로 .pyc 디컴파일하기
- 디컴파일이 안 되거나 신뢰가 안 가면 바이트코드를 직접 읽는다 → REV-1085 Python 바이트코드(dis 모듈)를 직접 읽는 법
- 애초에 이 pyc를 어디서 뽑았는지 모르겠다면 → REV-1082 pyinstxtractor로 PyInstaller 실행파일 추출하기
- 파일 자체의 매직 바이트/시그니처 개념이 낯설면 → REV-0020 Magic Byte와 파일 시그니처

## 미니 예제
```python
>>> with open("chall.pyc", "rb") as f:
...     magic = f.read(4)
...
>>> magic.hex()
'610d0d0a'
>>> int.from_bytes(magic[:2], "little")
3425
```
`3425`는 위 표에서 정확히 Python 3.9에 해당하는 값이다. 즉 이 `.pyc`는 CPython 3.9로 컴파일된 것이 확정되므로, REV-1084 단계에서 decompyle3(3.7 이상 지원)를 우선 시도하면 된다. 만약 읽은 값이 표의 어떤 최종값과도 정확히 일치하지 않는다면, 해당 마이너 버전의 alpha/beta 개발 릴리스 중 하나일 가능성이 있으므로 CPython 공식 저장소 `Include/internal/pycore_magic_number.h`의 전체 이력을 직접 대조하는 것이 가장 정확하다.

## 관련 글
- REV-1082 — pyinstxtractor로 PyInstaller 실행파일 추출하기
- REV-1084 — uncompyle6/decompyle3로 .pyc 디컴파일하기
- REV-1085 — Python 바이트코드(dis 모듈)를 직접 읽는 법
- REV-0020 — Magic Byte와 파일 시그니처

## 출처/검증
- pyc 16바이트 헤더 구조(매직넘버 4바이트+플래그 4바이트+타임스탬프/해시 8바이트)와 매직 넘버의 목적(버전 불일치 시 실행 거부): CPython 공식 소스 `Lib/importlib/_bootstrap_external.py` 및 `Include/internal/pycore_magic_number.h` 기준 (2026-09-10 WebFetch로 원문 확인).
- 버전별 매직 넘버 표(2.7=62211, 3.8=3413, 3.9=3425, 3.10=3439, 3.11=3495, 3.12=3531, 3.13=3571 등): CPython 공식 저장소 `Include/internal/pycore_magic_number.h`의 버전 이력 주석에서 직접 확인 (2026-09-10 WebFetch 검증). alpha/beta 중간값까지의 완전한 목록은 이 글에서 다루지 않으므로, 정확한 패치 단위 확인이 필요하면 해당 파일의 전체 이력을 직접 참고할 것.
