---
id: REV-1082
title: "pyinstxtractor로 PyInstaller 실행파일 추출하기"
slug: "rev-1082-pyinstxtractor-extraction"
category: "other-targets"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [pyinstxtractor, python]
keywords: ["pyinstxtractor 사용법", "PyInstaller 추출", "CArchive 추출", "PYZ 아카이브", "pyc 추출"]
aliases: ["pyinstxtractor.py 사용법", "PyInstaller exe에서 pyc 뽑는 법", "PyInstaller 언패킹"]
symptom_keywords: ["PyInstaller인 건 확인했는데 pyc를 어떻게 꺼내는지 모름", "pyinstxtractor 실행했더니 unmarshal 에러가 남", "extracted 폴더에 pyc가 안 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
REV-1081에서 PyInstaller 실행파일임을 확인했다면, `python pyinstxtractor.py 파일명` 한 줄로 `파일명_extracted` 폴더를 만들어 그 안에 메인 스크립트의 `.pyc`, 부트스트랩 `.pyc`, 그리고 `PYZ-00.pyz_extracted` 하위 폴더에 번들된 모든 모듈의 `.pyc`를 꺼낼 수 있다.

## 언제 검색해야 하나
- `strings`로 `pyi-windows-manifest-filename`이나 `_MEIPASS`를 확인해 PyInstaller임을 이미 확정했고, 이제 실제 `.pyc` 바이트코드를 손에 넣어야 할 때
- pyinstxtractor를 실행했는데 `Unmarshalling FAILED` 같은 에러가 나서 원인을 모를 때
- 추출된 폴더 구조가 낯설어서 어떤 파일이 "진짜 내가 찾는 메인 스크립트"인지 헷갈릴 때

## 핵심 개념

### pyinstxtractor가 하는 일
`pyinstxtractor.py`(GitHub `extremecoders-re/pyinstxtractor`)는 PyInstaller가 실행파일 끝부분에 붙여놓은 자체 아카이브 포맷(CArchive)을 파싱해서 그 안에 들어있는 개별 파일들을 디스크에 풀어주는 순수 파이썬 스크립트다. CArchive 안에는 메인 스크립트의 `.pyc`, 파이썬 표준 라이브러리 중 필요한 모듈들을 압축해서 모아둔 PYZ 아카이브, 그리고 DLL/공유 라이브러리/데이터 파일들이 함께 들어있다. 이 도구는 단순히 "안의 파일들을 그대로 꺼내는" 역할만 하고, `.pyc`를 사람이 읽을 수 있는 `.py`로 바꿔주지는 않는다(그건 REV-1084의 몫이다).

### 명령행 사용법
사용법은 인자 하나뿐이다.

```text
python pyinstxtractor.py <파일명>
```

옵션이나 플래그가 없는 매우 단순한 CLI다. 성공하면 실행 파일과 같은 위치에 `<파일명>_extracted`라는 폴더가 새로 생긴다.

### 파이썬 버전 일치가 중요한 이유
pyinstxtractor는 내부적으로 파이썬 표준 `marshal` 모듈로 PYZ 안의 코드 객체를 언마샬링한다. `marshal` 포맷은 파이썬 버전마다 미묘하게 다르기 때문에, **실행파일을 빌드할 때 쓰인 파이썬 버전과 다른 버전으로 pyinstxtractor를 돌리면** "Unmarshalling FAILED" 같은 경고가 뜨며 PYZ 추출을 건너뛸 수 있다. pyinstxtractor는 이 경우 실행 시점에 경고 메시지로 알려준다. 이 문제를 피하려면 REV-1083에서 확인한 `.pyc` 매직 넘버로 원본 파이썬 버전을 먼저 파악하고, `pyenv`나 가상환경으로 그 버전에 맞는 파이썬으로 pyinstxtractor를 실행하는 것이 안전하다.

## 화면/코드에서 보이는 징후
- 실행 로그에 `[+] Pyinstaller version: 2.1+`, `[+] Python version: 39` 같은 자동 감지 결과가 출력된다.
- `[+] Found N files in CArchive`, `[+] Found M files in PYZ archive` 같은 개수 출력이 나온다.
- `[+] Possible entry point: xxx.pyc` 줄이 하나 이상 나오는데, 이것이 실제로 `python xxx.py`로 실행했을 때의 메인 스크립트에 해당하는 파일이다.
- 폴더 안에 `.pyc` 외에도 `.dll`/`.pyd`(Windows) 또는 `.so`(Linux), 그리고 `pyi-windows-manifest-filename`으로 시작하는 매니페스트 파일 같은 부산물이 같이 나온다.

## 가장 먼저 할 것
GitHub `extremecoders-re/pyinstxtractor` 저장소에서 `pyinstxtractor.py` 하나만 받는다(단일 스크립트라 설치가 따로 필요 없다). 쓰기 권한이 있는 폴더에 대상 실행파일과 함께 놓고 `python pyinstxtractor.py 파일명`을 실행한다.

## 단계별 절차
1. 대상 실행파일과 `pyinstxtractor.py`를 같은 폴더(쓰기 권한 있는 곳)에 둔다.
2. `python pyinstxtractor.py chall.exe` 실행.
3. 콘솔에 찍히는 `Python version: NN` 값을 기록해둔다(REV-1083의 매직 넘버와 교차 검증용).
4. `chall.exe_extracted` 폴더로 이동해 `Possible entry point:`로 표시된 `.pyc`를 찾는다 — 보통 실행파일 이름과 같은 이름의 `.pyc`가 메인 스크립트다.
5. `PYZ-00.pyz_extracted` 폴더 안에서 임포트된 모듈들의 `.pyc`도 필요하면 함께 확인한다.
6. "Unmarshalling FAILED" 경고가 떴다면, 해당 파이썬 버전(3번에서 기록한 버전)을 설치하고 그 버전의 인터프리터로 다시 실행한다.

## 명령어/단축키
```bash
python pyinstxtractor.py chall.exe
# 결과: ./chall.exe_extracted/ 폴더 생성

ls chall.exe_extracted/
ls chall.exe_extracted/PYZ-00.pyz_extracted/
```

## 출력 해석
```text
[+] Processing chall.exe
[+] Pyinstaller version: 2.1+
[+] Python version: 39
[+] Length of package: 9532110 bytes
[+] Found 61 files in CArchive
[+] Beginning extraction...please standby
[+] Possible entry point: pyiboot01_bootstrap.pyc
[+] Possible entry point: chall.pyc
[+] Found 210 files in PYZ archive
[+] Successfully extracted pyinstaller archive: chall.exe

You can now use a python decompiler on the pyc files within the extracted directory
```
`pyiboot01_bootstrap.pyc`는 PyInstaller가 자동으로 끼워 넣는 런타임 훅(runtime hook)이지 실제 CTF 문제 로직이 아니다. 실제로 봐야 할 것은 실행파일 이름과 일치하는 `chall.pyc` 쪽이다. "Python version: 39"는 Python 3.9로 빌드됐다는 뜻이며, REV-1083/REV-1084 단계에서 이 버전을 기준으로 도구를 골라야 한다.

## 흔한 실수
- 쓰기 권한이 없는 폴더(예: 관리자 권한이 필요한 시스템 폴더)에서 실행해 폴더 생성이 조용히 실패하는 것 — 항상 쓰기 가능한 작업 폴더에서 실행한다.
- `pyiboot01_bootstrap.pyc`를 메인 로직으로 착각해서 시간을 낭비하는 것 — 이건 PyInstaller의 내부 부트스트랩 코드다.
- Unmarshalling 경고를 무시하고 그냥 넘어가는 것 — PYZ 안의 모듈들이 통째로 빠진 채 진행하면 나중에 import 에러의 원인을 못 찾아 헤매게 된다.
- pyinstxtractor로 뽑은 `.pyc`를 바로 `python chall.pyc`처럼 실행하려는 것 — 헤더가 없는 순수 코드 객체만 들어있는 경우도 있어 그대로 실행되지 않을 수 있다. 목적은 실행이 아니라 REV-1084의 디컴파일이다.

## 막혔을 때 다음 체크
- 원본 파이썬 버전을 정확히 알아야 pyinstxtractor의 버전 불일치 경고를 해결할 수 있다 → REV-1083 .pyc 파일에서 Python 버전(매직 넘버) 확인하기
- `.pyc`를 실제로 읽을 수 있는 소스로 바꾸고 싶다 → REV-1084 uncompyle6/decompyle3로 .pyc 디컴파일하기
- 디컴파일이 실패하는 경우 바이트코드를 직접 읽어야 한다 → REV-1085 Python 바이트코드(dis 모듈)를 직접 읽는 법
- 애초에 PyInstaller인지 확신이 안 서면 → REV-1081 PyInstaller로 패키징된 실행파일 식별하는 법

## 미니 예제
Windows에서 받은 `crackme.exe`가 REV-1081 단계에서 PyInstaller로 확인됐다고 하자.
```text
> python pyinstxtractor.py crackme.exe
[+] Processing crackme.exe
[+] Pyinstaller version: 2.1+
[+] Python version: 38
[+] Found 45 files in CArchive
[+] Possible entry point: crackme.pyc
[+] Found 133 files in PYZ archive
[+] Successfully extracted pyinstaller archive: crackme.exe
```
`crackme.exe_extracted\crackme.pyc`가 바로 우리가 분석해야 할 메인 스크립트다. Python 버전이 38(=3.8)로 확인됐으므로, 다음 단계인 REV-1084에서는 decompyle3(3.7~3.8 지원)를 쓰면 된다.

## 관련 글
- REV-1081 — PyInstaller로 패키징된 실행파일 식별하는 법
- REV-1083 — .pyc 파일에서 Python 버전(매직 넘버) 확인하기
- REV-1084 — uncompyle6/decompyle3로 .pyc 디컴파일하기

## 출처/검증
- pyinstxtractor의 CLI 문법(`python pyinstxtractor.py <파일명>`, 인자 하나뿐), 추출 폴더 구조(`<파일명>_extracted`, `PYZ-00.pyz_extracted`), 실제 콘솔 출력 형식, 버전 불일치 시 "Unmarshalling FAILED"/버전 경고 동작: GitHub `extremecoders-re/pyinstxtractor` 공식 저장소 소스 및 README, DeepWiki CLI 문서 기준 (2026-09-10 WebSearch 검증).
- Linux ELF 바이너리도 pyinstxtractor로 직접 추출 가능하다는 점은 다수 write-up에서 확인됨.
