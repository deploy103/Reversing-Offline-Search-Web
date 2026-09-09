---
id: REV-1081
title: "PyInstaller로 패키징된 실행파일 식별하는 법"
slug: "rev-1081-pyinstaller-identification"
category: "other-targets"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["Detect It Easy", pyinstxtractor, strings]
keywords: ["PyInstaller 식별", "PyInstaller CTF", "python 패킹 실행파일", "_MEIPASS", "pyi-windows-manifest-filename"]
aliases: ["PyInstaller 확인법", "exe가 python으로 만들어졌는지 확인", "이 exe가 파이썬인지 확인하는 법"]
symptom_keywords: ["exe 파일이 파이썬으로 만들어진 것 같은데 확인이 안 됨", "IDA로 열었더니 함수가 거의 없고 python3X.dll만 임포트됨", "파일 크기가 유난히 크고 실행하면 잠깐 멈췄다 뜸"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
CTF에서 받은 `.exe`나 리눅스 실행파일이 IDA/Ghidra로 열었을 때 함수가 거의 없고 `python3X.dll`(또는 `libpython`) 임포트만 보이면서 파일 크기가 수 MB로 크다면, 이는 파이썬 스크립트를 통째로 실행파일로 묶어주는 **PyInstaller**로 패키징된 것일 가능성이 매우 높고, `strings`로 `pyi-windows-manifest-filename`이나 `_MEIPASS` 같은 고유 문자열을 찾으면 확정할 수 있다.

## 언제 검색해야 하나
- 어셈블리 분석을 시작했는데 `main`다운 함수는 안 보이고 `Py_Initialize`, `PyRun_SimpleString` 같은 이름이나 `python310.dll`, `python3.dll` 임포트만 잔뜩 보일 때
- 파일이 실행되자마자 콘솔 창이 잠깐 깜빡이거나, 실행 초반에 임시 폴더에 파일들이 풀렸다가 사라지는 것처럼 느려질 때(onefile 모드 특유의 압축 해제 지연)
- Detect It Easy(DIE)로 열었을 때 컴파일러 항목에 명확한 MSVC/MinGW 표시 없이 정체불명의 큰 바이너리로만 나올 때
- 문제 설명이나 첨부파일 이름에 `.spec`, `dist/`, `build/` 같은 PyInstaller 특유의 산출물 흔적이 있을 때

## 핵심 개념

### PyInstaller가 실행파일을 만드는 방식
PyInstaller는 파이썬 인터프리터(`python3X.dll`/`libpythonX.Y.so`)와 필요한 모듈들의 `.pyc` 바이트코드, 그리고 이를 실행시켜주는 작은 C로 작성된 "부트로더(bootloader)"를 하나로 묶는다. `--onefile` 옵션을 쓰면 이 모든 것이 실행파일 하나에 CArchive라는 자체 포맷으로 압축되어 붙고, 실행 시점에 부트로더가 이를 임시 폴더에 풀어서 그 안의 실제 인터프리터를 구동한다. 이 임시 폴더 경로가 바로 `sys._MEIPASS`이며, 구버전 부트로더에서는 부모-자식 프로세스 간 이 경로를 전달하는 데 `_MEIPASS2`라는 환경변수를 썼다.

### 왜 이런 특징이 남는가
- 파이썬 인터프리터 전체와 표준 라이브러리 일부, 그리고 프로젝트가 쓰는 서드파티 패키지까지 통째로 들어가기 때문에 파일 크기가 수 MB~수십 MB로 커진다.
- 실제 로직은 전부 `.pyc` 바이트코드로 들어있어서 네이티브 디스어셈블러에는 파이썬 C API 호출(`Py_Initialize`, `PyImport_ExecCodeModule` 등)만 보이고 사람이 짠 로직은 전혀 보이지 않는다.
- 부트로더 소스코드(공식 오픈소스, `PyInstaller/bootloader`)에 하드코딩된 여러 상수 문자열이 최종 바이너리에 그대로 남는다.

## 화면/코드에서 보이는 징후
- `strings` 결과에 `pyi-windows-manifest-filename`, `_MEIPASS`, `_MEIPASS2`, `PYINSTALLER`, `PYI_ARCHIVE`, `pyi_rth_...`(runtime hook) 형태의 문자열이 하나 이상 보인다.
- IDA Imports 창에 `python310.dll`, `python38.dll` 같은 버전 번호가 붙은 파이썬 DLL, 또는 리눅스라면 `libpython3.x.so.1.0`이 보인다.
- Windows용 onefile 실행파일 실행 시 콘솔 창이 잠깐 깜빡이거나(부트로더가 콘솔을 잠깐 띄웠다가 자식 프로세스로 넘김), 백신/샌드박스 로그에 `%TEMP%\_MEIxxxxxx` 형태의 임시 디렉터리 생성 흔적이 남는다.
- 파일 뒷부분에 ZIP과 유사한 구조(PYZ 아카이브)가 보이는데 일반 ZIP 도구로는 안 열린다(PyInstaller 자체 포맷이라서).

## 가장 먼저 할 것
`strings` 한 번으로 끝낼 수 있다. Windows PE라면 `strings mainv2.exe | findstr /i pyinstaller` 또는 Linux ELF라면 `strings ./chall | grep -i "pyinstaller\|MEIPASS"`부터 실행한다. 이 문자열이 하나라도 걸리면 REV-1082(pyinstxtractor로 추출)로 바로 넘어가면 된다.

## 단계별 절차
1. `file ./chall`로 PE/ELF 여부와 대략적인 크기(수 MB 이상이면 의심)를 확인한다.
2. `strings ./chall | grep -iE "pyinstaller|_MEIPASS|pyi-windows-manifest-filename"`로 고유 문자열을 찾는다.
3. Windows PE라면 Import 목록에서 `pythonXY.dll`을 찾는다(예: `python39.dll`).
4. Detect It Easy로 열어 시그니처 데이터베이스가 PyInstaller를 잡아내는지 참고용으로 확인한다(버전에 따라 자동 인식되지 않을 수 있으므로 strings 결과를 우선 신뢰한다).
5. 확정되면 REV-1082(pyinstxtractor로 추출)로 넘어가 실제 `.pyc`를 꺼낸다.

## 명령어/단축키
```bash
# Linux / WSL에서
file ./chall
strings ./chall | grep -i "pyinstaller"
strings ./chall | grep -i "meipass"
```
```text
:: Windows cmd에서
findstr /i "PyInstaller" mainv2.exe >nul && echo PyInstaller DETECTED || echo Not PyInstaller
```

## 출력 해석
- `pyi-windows-manifest-filename` 문자열이 나오면 Windows용 PyInstaller 부트로더가 확실하다(이 문자열은 실행 매니페스트 파일 이름을 부트로더가 참조할 때 쓰는 내부 식별자다).
- `_MEIPASS`만 나오고 `_MEIPASS2`는 없다면 최신 버전 부트로더, 반대로 `_MEIPASS2`가 보이면 onefile 모드의 부모 프로세스가 자식에게 임시 폴더 경로를 전달하는 구버전 방식을 쓴 것이다.
- `python3X.dll` 임포트에서 버전 번호(`38`, `39`, `310`, `311` 등)를 읽어두면 이후 REV-1082/REV-1084 단계에서 어떤 파이썬 버전 환경으로 맞춰야 하는지 미리 알 수 있다.

## 흔한 실수
- DIE의 자동 시그니처만 믿고 넘어가는 것 — 버전이나 빌드 옵션에 따라 자동 인식이 안 될 수 있으므로 `strings` 확인을 항상 병행해야 한다.
- 파일 크기가 크다는 이유만으로 "패킹(UPX 등)됐다"고 오해하고 REV-0287 계열의 패커 언패킹부터 시도하는 것 — PyInstaller는 UPX 압축과는 전혀 다른 문제다.
- onefile이 아니라 onedir(`--onedir`) 모드로 배포된 경우, 실행파일 옆에 `_internal` 폴더나 여러 DLL이 함께 있는 것을 못 보고 실행파일 하나만 갖고 분석하려는 것 — 이 경우 폴더 전체가 분석 대상이다.

## 막혔을 때 다음 체크
- 확정했다면 실제 내용물을 꺼내야 한다 → REV-1082 pyinstxtractor로 PyInstaller 실행파일 추출하기
- 꺼낸 `.pyc`가 어느 파이썬 버전인지부터 알아야 한다 → REV-1083 .pyc 파일에서 Python 버전(매직 넘버) 확인하기
- 처음부터 첨부파일 이름/문제 설명에서 힌트를 더 찾고 싶다면 → REV-0012 문제 설명과 첨부파일에서 힌트 뽑는 방법

## 미니 예제
```text
$ file chall.exe
chall.exe: PE32+ executable (console) x86-64, for MS Windows

$ strings chall.exe | grep -i pyinstaller
pyi-windows-manifest-filename
PyInstallerImportError: Failed to load dynlib/dll ...

$ strings chall.exe | grep -i meipass
_MEIPASS2
sys._MEIPASS
```
이 세 줄만 나와도 이 파일이 PyInstaller로 만들어진 파이썬 프로그램임이 사실상 확정된다. 다음 단계는 pyinstxtractor로 넘어가는 것뿐이다.

## 관련 글
- REV-1082 — pyinstxtractor로 PyInstaller 실행파일 추출하기
- REV-1083 — .pyc 파일에서 Python 버전(매직 넘버) 확인하기
- REV-0012 — 문제 설명과 첨부파일에서 힌트 뽑는 방법

## 출처/검증
- `pyi-windows-manifest-filename`, `_MEIPASS`/`_MEIPASS2` 등 식별 문자열과 onefile 부트로더 동작 방식: 실전 CTF/리버싱 write-up 다수(Medium "Extract password from exe", cristiansandu.ro "Reverse Engineering a PyInstaller Executable on Linux", netscylla.com "Reversing Python Exes") 및 PyInstaller 공식 문서(Advanced Topics)의 `sys._MEIPASS` 설명 기준으로 확인 (2026-09-10 WebSearch 검증).
- Linux ELF에서도 pyinstxtractor로 직접 추출 가능하다는 점은 위 write-up들에서 반복 확인됨.
