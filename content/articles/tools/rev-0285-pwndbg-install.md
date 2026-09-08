---
id: REV-0285
title: "Pwndbg 설치와 오프라인 준비"
slug: "rev-0285-pwndbg-install"
category: "tools"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pwndbg 설치", "pwndbg install", "pwndbg setup.sh", "pwndbg offline", "pwndbg 오프라인 설치", "pwndbg deb rpm", "gdbinit pwndbg"]
aliases: ["pwndbg 세팅", "pwndbg 오프라인 준비", "GDB 확장 플러그인 설치"]
symptom_keywords: ["pwndbg 설치가 안됨", "setup.sh 실행 안됨", "대회장에서 pwndbg 못깔음", "gdb context가 안 보임", "pwndbg 인터넷 없이 설치"]
source_ids: ["SRC-PWNDBG-DOCS", "SRC-GDB-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg는 순정 GDB를 CTF/익스플로잇 개발에 최적화된 화면(레지스터·스택·디스어셈블리 자동 표시)과 편의 명령(`telescope`, `vmmap`, `search` 등)으로 강화해주는 GDB/LLDB 플러그인으로, 공식 설치 방법은 `git clone` 후 `./setup.sh`를 실행하는 것이며 이 과정은 인터넷이 되는 환경에서 한 번만 수행하면 이후에는 완전히 오프라인으로 동작한다.

## 언제 검색해야 하나
- GDB는 켜지는데 IDA/Ghidra 필기에서 자주 보던 "레지스터+스택+디스어셈블리가 한 화면에 동시에 뜨는" 그 화면이 안 나올 때
- `context`, `telescope`, `vmmap` 같은 명령이 "Undefined command"로 뜰 때(순정 GDB에는 없는 Pwndbg 전용 명령)
- 대회 PC가 오프라인이라 `git clone`이 안 되는 상황에서 Pwndbg를 미리 준비하고 싶을 때
- Pwndbg 설치 스크립트가 Python 버전 문제로 실패할 때 원인을 파악하고 싶을 때
- GDB와 Pwndbg의 차이, 그리고 어느 쪽 문서를 봐야 하는지 헷갈릴 때

## 핵심 개념

### Pwndbg는 GDB를 "대체"하는 게 아니라 "강화"하는 것이다
Pwndbg는 별도의 디버거가 아니라, GDB(또는 LLDB) 안에 로드되는 Python 확장이다. 즉 GDB가 먼저 정상적으로 설치·동작해야 하고(REV-0283 참고), 그 위에 Pwndbg를 얹는 구조다. 설치가 끝나면 평소처럼 `gdb ./chall`을 치는 것만으로 Pwndbg가 자동으로 함께 로드된다 — 명령어를 따로 외워서 켜는 게 아니다.

### 공식 설치 방법: `setup.sh`
Pwndbg 공식 GitHub 저장소(`pwndbg/pwndbg`)가 제공하는 표준 설치 절차는 다음과 같다.
```bash
git clone https://github.com/pwndbg/pwndbg
cd pwndbg
./setup.sh
```
`setup.sh`는 배포판을 자동 감지해서 필요한 시스템 패키지(`gdb`, `gdbserver`, `python3-dev`, `python3-venv` 등)를 설치하고, Python 가상환경을 만든 뒤 Pwndbg 자체를 설치하고, 마지막으로 `~/.gdbinit`에 `source <pwndbg경로>/gdbinit.py` 한 줄을 자동으로 추가한다. 이 한 줄 덕분에 이후 GDB를 켤 때마다 Pwndbg가 자동 로드된다.

### 지원 환경과 Python 버전 주의
공식 문서 기준 Pwndbg는 Ubuntu 22.04/24.04, GDB 12.1 이상을 기준으로 테스트된다. Python 3.10~3.99 범위가 아니면 `setup.sh`가 경고를 내며, 더 낮은 Python 버전(3.8/3.9, 3.6/3.7)만 있는 오래된 배포판이라면 최신 Pwndbg 대신 과거 릴리스 태그(`2024.08.29`, `2023.07.17` 등)로 체크아웃해서 설치하라고 안내한다. 대회 PC의 배포판이 오래됐다면 이 부분을 미리 확인해야 한다.

### 오프라인 대회를 위한 준비 — 인터넷은 "설치 시점에 한 번만"
대회 PC가 인터넷이 안 되는 것이 일반적이므로, Pwndbg는 반드시 **사전에(인터넷 되는 곳에서) 설치를 끝낸 노트북/USB 이미지**를 대회장에 그대로 들고 가야 한다. 방법은 크게 세 가지다.
1. **미리 설치된 VM/디스크 이미지 통째로 반입**: 가장 안전. `git clone` + `setup.sh`까지 끝낸 상태의 가상머신이나 라이브 USB를 그대로 사용
2. **포터블 사전 빌드 릴리스 사용**: Pwndbg 공식 릴리스 페이지에서 GDB용/LLDB용으로 이미 의존성이 다 포함된 포터블 빌드를 받아둘 수 있다. 이 경우 대회 PC에서는 압축만 풀면 되고 추가 네트워크 접근이 필요 없다
3. **배포판 패키지(.deb/.rpm/.apk/Arch 패키지) 사전 다운로드**: 공식 릴리스 페이지에서 `pwndbg_<버전>_amd64.deb` 같은 패키지를 미리 받아 USB에 담고, 대회 PC에서 `apt install ./pwndbg_*.deb`로 오프라인 설치. 다만 공식 문서는 이 방법이 "공식 지원(officially supported)이 아니며 Python 의존성 버전을 pwndbg 팀이 통제할 수 없다"고 명시하므로, 가능하면 1번(이미지 반입)을 우선한다

세 방법 모두 "인터넷은 사전 준비 단계에서만 필요하고 대회 당일에는 필요 없다"는 원칙은 동일하다.

## 화면/코드에서 보이는 징후
- 설치 전: `gdb ./chall` → `start` 후 화면이 그냥 순정 GDB 프롬프트(`(gdb)`)만 나옴
- 설치 후: `gdb ./chall` → `start` 하면 자동으로 상단에 `REGISTERS`, `DISASM`, `STACK`, `BACKTRACE` 구획이 나뉜 화면(컨텍스트 뷰)이 뜸
- 설치 실패 시 `setup.sh` 실행 중 `Unsupported python version` 또는 apt 패키지 설치 실패 메시지가 뜸
- `.gdbinit`을 열어보면 `source /home/user/pwndbg/gdbinit.py` 줄이 자동으로 추가돼 있는 것이 정상

## 가장 먼저 할 것
인터넷이 되는 환경에서 먼저 `git clone https://github.com/pwndbg/pwndbg && cd pwndbg && ./setup.sh`를 실행해 설치를 끝낸다. 그 다음 `gdb ./아무바이너리`를 쳐서 컨텍스트 화면이 자동으로 뜨는지 확인한다. 여기까지 되면 대회 PC로 이 환경(또는 설치된 디스크 이미지) 자체를 그대로 옮기는 계획을 세운다.

## 단계별 절차

**1) GDB가 먼저 정상 설치돼 있는지 확인**
```bash
gdb --version
```

**2) Pwndbg 저장소 클론 및 설치 (인터넷 필요, 이 단계만)**
```bash
git clone https://github.com/pwndbg/pwndbg
cd pwndbg
./setup.sh
```

**3) 설치 확인**
```bash
gdb -q
(gdb) quit
```
GDB가 시작될 때 Pwndbg 배너/버전 정보가 함께 출력되면 성공.

**4) 오프라인 반입 준비 (대회 전 필수)**
- 방법 A: `setup.sh`까지 끝낸 VM 디스크 이미지를 통째로 백업해서 대회 PC에 복사
- 방법 B: 공식 릴리스 페이지에서 포터블 빌드(예: `pwndbg-gdb-<버전>-x86_64.tar.gz` 형태)를 받아 USB에 저장, 대회 PC에서 압축 해제 후 바로 실행 가능한지 리허설
- 방법 C: `.deb`/`.rpm` 패키지를 받아 USB에 저장, 대회 PC에서 `sudo apt install ./pwndbg_*.deb`

**5) 실제 CTF 바이너리로 동작 검증**
```bash
gdb ./chall
(gdb) start
```
레지스터/스택/디스어셈블리가 자동으로 화면에 정리돼 나오면 준비 완료.

## 명령어/단축키
| 목적 | 명령 |
|---|---|
| 공식 설치 | `git clone https://github.com/pwndbg/pwndbg && cd pwndbg && ./setup.sh` |
| 개발용 추가 설정 | `./setup-dev.sh` (기여자용, 일반 사용자는 불필요) |
| Nix 사용자 | `nix shell github:pwndbg/pwndbg` |
| 설치 확인 | `gdb -q` 실행 후 배너 확인 |
| 구버전 Python 대응 | `git checkout 2024.08.29` (python3.8/3.9), `git checkout 2023.07.17` (python3.6/3.7) 후 `./setup.sh` |
| deb 오프라인 설치 | `sudo apt install ./pwndbg_<버전>_amd64.deb` |

## 출력 해석
- `setup.sh` 마지막에 `Pwndbg was installed successfully`류의 메시지가 나오면 정상 완료
- GDB 시작 배너에 `pwndbg: loaded X commands`처럼 로드된 명령 개수가 표시되면 정상 로드
- `Unsupported python version` 메시지는 시스템 Python이 3.10 미만이거나 3.99를 초과한다는 뜻 — 배포판 업그레이드 또는 구버전 태그 사용

## 흔한 실수
- 대회 당일 처음으로 `git clone`을 시도했다가 인터넷이 막혀 있어서 그대로 시간을 날리는 경우 — 반드시 며칠 전에 오프라인 리허설
- GDB 자체가 안 깔린 최소 이미지에서 `setup.sh`만 실행하고 실패 원인을 GDB 문제인지 Pwndbg 문제인지 구분 못 하는 경우
- `.gdbinit`을 손으로 직접 수정해서 Pwndbg의 `source` 줄을 실수로 지우는 경우 — 이후 GDB를 켜도 Pwndbg가 로드되지 않음
- 회사/개인 방화벽 때문에 `git clone`이 https는 되는데 특정 포트만 막혀서 설치 스크립트 중간의 pip 패키지 설치가 실패하는 것을 못 알아채는 경우

## 막혔을 때 다음 체크
1. `gdb --version`으로 GDB 자체가 정상인지 먼저 분리해서 확인
2. `cat ~/.gdbinit`으로 Pwndbg의 `source` 줄이 실제로 있는지 확인
3. `python3 --version`으로 지원 범위(3.10~3.99)인지 확인
4. 오프라인 환경이면 `setup.sh`가 인터넷을 요구하는 지점(pip install, apt install)에서 멈추는지 로그로 확인
5. 그래도 안 되면 포터블 사전 빌드(압축 해제만 하면 되는 버전)로 전환

## 미니 예제
```bash
$ git clone https://github.com/pwndbg/pwndbg
$ cd pwndbg
$ ./setup.sh
...
$ gdb ./chall
pwndbg: loaded 150 commands. Type pwndbg [--shell | --python] for a list.
pwndbg> start
```

## 관련 글
- REV-0283 — GDB 설치와 기본 설정
- REV-0286 — Pwndbg 명령어 치트시트
- REV-0192 — Pwndbg 설치와 실행
- REV-0185 — GDB 실행 run start args 사용법

## 출처/검증
- Pwndbg 공식 문서(pwndbg.re) 및 공식 GitHub 저장소(github.com/pwndbg/pwndbg)의 `setup.sh`, 릴리스 페이지 안내를 기준으로 작성했다.
- 최종 확인일: 2026-09-08
