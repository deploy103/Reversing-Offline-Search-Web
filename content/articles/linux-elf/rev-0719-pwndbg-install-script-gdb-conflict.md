---
id: REV-0719
title: "Pwndbg 설치 스크립트가 최신 GDB와 충돌할 때"
slug: "rev-0719-pwndbg-install-script-gdb-conflict"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [Pwndbg, GDB]
keywords: ["pwndbg setup.sh", "ModuleNotFoundError pwndbg", "GDB Python 버전 불일치", "pwndbg portable release"]
aliases: ["pwndbg 설치 실패", "pwndbg import 오류", "pwndbg gdb python mismatch", "pwndbg no module named pwndbg"]
symptom_keywords: ["ModuleNotFoundError No module named pwndbg", "setup.sh 실행하면 python 버전 다르다고 경고", "pwndbg 설치 후 gdb 실행하면 오류", "gdb 업데이트 후 pwndbg 깨짐"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg의 구식 설치 방식(`git clone` + `./setup.sh`)은 시스템에 설치된 GDB가 링크한 Python 버전과 `setup.sh`가 패키지를 까는 Python 버전이 어긋나면 `ModuleNotFoundError: No module named 'pwndbg'` 같은 오류로 깨지기 쉬우며, 최근에는 이 문제 자체를 피하도록 공식 설치 스크립트(`curl -qsL 'https://install.pwndbg.re' | sh`)나 portable 릴리스를 쓰는 것이 가장 안전한 해결책이다.

## 언제 검색해야 하나
- `./setup.sh`를 실행했더니 "GDB is using a different Python version than the one installed via the package manager" 같은 경고가 뜰 때
- GDB를 열면 `pwndbg` 프롬프트 대신 `ModuleNotFoundError: No module named 'pwndbg'` 오류가 뜨거나, Pwndbg 명령어(`context`, `vmmap` 등)가 아예 안 먹을 때
- 배포판(Ubuntu/Debian/Arch)의 GDB를 업데이트했더니 멀쩡히 쓰던 Pwndbg가 갑자기 깨질 때

## 핵심 개념

### 원인 — GDB가 내장한 Python과 시스템 Python이 서로 다른 버전
GDB는 자체적으로 Python 인터프리터를 임베드해서 스크립팅 기능(`gdb.execute`, `gdb.Breakpoint` 등, REV-0656 계열 주제)을 제공한다. Pwndbg는 이 GDB 내장 Python 위에서 동작하는 순수 Python 패키지이므로, **GDB가 링크한 Python 버전**과 **Pwndbg가 의존성을 설치한 Python 버전**이 반드시 일치해야 한다. 구식 `setup.sh`는 설치 시점에 `gdb -batch -q --nx -ex 'pi import sysconfig; print(sysconfig.get_config_vars()...)'` 같은 명령으로 GDB가 쓰는 Python을 탐지해서 그 버전에 맞춰 의존성을 설치하려 시도하지만, 다음과 같은 상황에서 어긋난다:
- 배포판 GDB 업데이트로 GDB가 갑자기 더 최신 시스템 Python(예: 3.12)에 링크되었는데, Pwndbg는 예전 Python(예: 3.10) 기준으로 설치돼 있던 경우
- `pyenv`, `conda`, 수동 빌드한 Python 등 여러 Python이 시스템에 공존해서 `setup.sh`가 엉뚱한 Python을 잡은 경우
- GDB를 소스 빌드하면서 Python 지원 없이(`--without-python`) 빌드했거나, 다른 Python으로 링크되게 빌드한 경우

### 흔한 오류 메시지들
- `ModuleNotFoundError: No module named 'pwndbg'`: `gdbinit.py`가 `sys.path`에 Pwndbg 설치 경로를 못 찾을 때. GDB를 Pwndbg 클론 디렉터리 밖에서 실행했거나, 가상환경(venv) 경로가 어긋난 경우 흔히 발생한다.
- `ModuleNotFoundError: No module named 'distutils.sysconfig'` 또는 `No module named 'pkg_resources'`: Python 3.12+에서 `distutils`가 표준 라이브러리에서 제거되면서, Capstone 등 Pwndbg 의존 패키지의 구식 빌드 스크립트가 깨지는 경우. `python3-distutils`(또는 `setuptools`) 패키지를 별도로 설치해야 하는 경우가 있다.
- "It looks like GDB is using a different Python version than the one installed via the package manager": `setup.sh`가 자체적으로 띄우는 사전 경고로, 이 시점에서 이미 계속 진행해도 실패할 가능성이 높다는 신호다.

## 화면/코드에서 보이는 징후
```bash
$ ./setup.sh
[!] It looks like GDB is using a different Python version than the one installed via the package manager.
    GDB Python: 3.10
    System Python: 3.12
```
```
$ gdb ./chall
Traceback (most recent call last):
  File "/home/user/pwndbg/gdbinit.py", line 74, in <module>
    import pwndbg  # noqa: F401
ModuleNotFoundError: No module named 'pwndbg'
```

## 가장 먼저 할 것
가능하면 문제의 근본 원인(구식 `git clone` + `setup.sh` 방식)을 우회한다. Pwndbg 공식 문서(pwndbg.re)는 현재 아래와 같은 설치 방법을 권장한다:
```bash
curl -qsL 'https://install.pwndbg.re' | sh -s -- -t pwndbg-gdb
```
이 스크립트는 Python 의존성을 시스템과 분리된 형태로 번들링하므로, 시스템 GDB/Python 버전과의 충돌 가능성이 크게 줄어든다. 이미 구식 방식으로 설치해서 문제가 난 상태라면 이 공식 스크립트로 재설치하는 것이 디버깅보다 빠른 경우가 많다.

## 단계별 절차

**1) GDB가 쓰는 Python 버전 확인**
```bash
gdb -batch -q -ex "python import sys; print(sys.version)"
```

**2) 시스템 기본 python3 버전과 비교**
```bash
python3 --version
```
두 버전(주.부 버전, 예: 3.10 vs 3.12)이 다르면 이것이 원인일 가능성이 매우 높다.

**3) 공식 설치 스크립트로 재설치(권장)**
```bash
curl -qsL 'https://install.pwndbg.re' | sh -s -- -t pwndbg-gdb
```
이 방식은 자체 런타임을 포함한 배포 형태라 시스템 Python 버전 변화의 영향을 덜 받는다. macOS는 `brew install pwndbg/tap/pwndbg-gdb`도 지원된다.

**4) portable 릴리스로 대체(오프라인/권한 제약 환경)**
GitHub 릴리스 페이지에서 portable 아카이브를 받아 압축만 풀면 별도 설치 없이 실행할 수 있다:
```bash
tar -xf pwndbg-portable.tar.gz
./pwndbg/bin/pwndbg ./chall
```
외부 네트워크가 막힌 CTF 환경이나 오프라인 실습 환경에서는 미리 이 portable 패키지를 받아둔 로컬 킷을 쓰는 것이 가장 안정적이다.

**5) 그래도 구식 setup.sh를 써야 한다면 — Python 버전을 맞춰서 재시도**
```bash
sudo apt install python3.12-venv  # GDB가 링크한 버전과 맞춤
./setup.sh
```
또는 GDB 자체를 시스템 Python과 맞는 버전으로 재빌드/재설치한다. 배포판 패키지 관리자(`pacman`, `apt` 등)로 GDB와 Pwndbg를 함께 설치하는 방법은 Pwndbg 프로젝트가 "공식 지원 대상 아님(dependency 버전을 통제할 수 없음)"이라고 명시하고 있으므로, 이 조합에서 자꾸 깨진다면 공식 설치 스크립트/portable로 갈아타는 편이 낫다.

**6) 시스템에 GDB가 이미 깔려 있는 상태에서 재설치가 꼬였다면**
Pwndbg의 Python 모듈이 순정 GDB의 다른 Python 모듈과 경로 충돌을 일으키는 경우가 보고되어 있다. 순정 GDB 패키지를 완전히 제거한 뒤 Pwndbg 번들(자체 GDB 포함 버전)만 남기거나, `.gdbinit`에서 `source` 라인이 중복되지 않았는지 확인한다.

## 명령어/단축키
```bash
curl -qsL 'https://install.pwndbg.re' | sh -s -- -t pwndbg-gdb
gdb -batch -q -ex "python import sys; print(sys.version)"
python3 --version
brew install pwndbg/tap/pwndbg-gdb   # macOS
```

## 출력 해석
```
GDB Python: 3.10
System Python: 3.12
```
이 두 줄이 다르게 나오면, `setup.sh`가 pip으로 설치하는 Capstone/Unicorn 등 확장 모듈이 3.12용 바이너리인데 GDB는 3.10 인터프리터로 그 모듈을 import하려 시도하는 상황이 된다. Python은 서로 다른 마이너 버전 간 컴파일된 확장 모듈(.so)을 호환하지 않으므로 반드시 `ModuleNotFoundError`나 `ImportError`로 실패한다.

## 흔한 실수
- 오류 메시지만 보고 pip으로 `pwndbg` 모듈을 아무 Python 환경에나 설치하는 것 — 반드시 **GDB가 실제로 사용하는 그 Python**에 설치되어야 의미가 있다.
- 배포판 GDB를 업데이트할 때마다 Pwndbg가 깨지는 걸 매번 수작업으로 고치는 것 — 애초에 시스템 Python과 분리된 공식 설치 스크립트/portable 릴리스로 옮기면 이 반복을 피할 수 있다.
- GEF, PEDA, Pwndbg를 동시에 `.gdbinit`에 `source`시켜 놓고 어느 하나가 안 먹는다고 착각하는 것 — 여러 GDB 플러그인을 같은 `.gdbinit`에 함께 두면 서로 충돌하므로 하나만 활성화해야 한다.
- 오프라인 대회장에서 그제서야 인터넷이 필요한 `setup.sh`나 `curl` 설치를 시도하는 것 — 대회 전에 portable 릴리스나 검증된 오프라인 킷을 미리 준비해둔다(REV-0285 Pwndbg 설치와 오프라인 준비 참고).

## 막혔을 때 다음 체크
- Pwndbg 기본 설치/오프라인 준비 절차 전반이 궁금하다면 → REV-0285 Pwndbg 설치와 오프라인 준비
- Pwndbg 명령어를 빠르게 훑고 싶다면 → REV-0286 Pwndbg 명령어 치트시트
- GDB 자체 설치/설정이 궁금하다면 → REV-0283 GDB 설치와 기본 설정
- Docker 컨테이너 안에서 GDB가 별도로 권한 오류를 낸다면(ptrace_scope) → REV-0715 Docker 컨테이너 안에서 gdb가 ptrace 권한 오류를 낼 때

## 미니 예제
```bash
$ gdb -batch -q -ex "python import sys; print(sys.version)"
3.10.12 (main, ...) [GCC 11.4.0]
$ python3 --version
Python 3.12.3
```
GDB는 3.10, 시스템 기본 `python3`는 3.12로 버전이 갈라져 있다. 이 상태에서 `setup.sh`가 3.12용 패키지를 설치했다면 GDB(3.10)에서 import가 실패하는 것이 당연한 결과이며, 해결은 "GDB가 실제 사용하는 3.10 환경에 맞춰 설치"하거나 이런 버전 추적 자체가 필요 없는 공식 설치 스크립트/portable 릴리스로 옮기는 것이다.

## 관련 글
- REV-0285 — Pwndbg 설치와 오프라인 준비
- REV-0286 — Pwndbg 명령어 치트시트
- REV-0283 — GDB 설치와 기본 설정
- REV-0715 — Docker 컨테이너 안에서 gdb가 ptrace 권한 오류를 낼 때
- REV-0716 — statically linked 바이너리라 GDB가 함수 이름을 안 보여줄 때

## 출처/검증
- `setup.sh`가 GDB/시스템 Python 버전 불일치를 감지해 경고하는 동작 및 `ModuleNotFoundError: No module named 'pwndbg'`(gdbinit.py import 실패) 사례: Pwndbg 공식 GitHub 저장소 이슈(#1866) 및 `setup.sh` 소스 기준.
- 현재(2025 릴리스 기준) 공식 설치 방법(curl 설치 스크립트, Homebrew, Nix, portable 릴리스, distro 패키지 비공식 명시): Pwndbg 공식 문서 `pwndbg.re/2025.10.10/setup/` 기준 (2026-09-08 확인).
- Python 3.12+에서 `distutils` 제거로 인한 관련 빌드 오류: Python 공식 변경 로그(PEP 632) 및 커뮤니티 보고 사례 기준.
