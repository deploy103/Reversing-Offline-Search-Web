---
id: REV-0690
title: "Pwndbg가 설치는 됐는데 명령어가 안 먹을 때"
slug: "rev-0690-pwndbg-commands-not-working"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pwndbg 명령어 안됨", "Undefined command vmmap", "pwndbg setup.sh", "pwndbg gdbinit 안불러짐", "pwndbg virtualenv 충돌"]
aliases: ["pwndbg vmmap 안됨", "pwndbg context 명령어 없음", "gdb pwndbg 안불러짐"]
symptom_keywords: ["pwndbg 설치했는데 vmmap 쳤더니 Undefined command", "gdb에서 context 명령어가 없다고 함", "pwndbg setup.sh 돌렸는데 명령어 안먹힘", "sudo gdb에서 pwndbg 명령어 안됨"]
source_ids: ["SRC-PWNDBG-DOCS", "SRC-GDB-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg를 설치했는데도 `vmmap`, `context`, `telescope` 같은 명령어를 치면 GDB가 `Undefined command: "vmmap".  Try "help".`처럼 순정 GDB 오류를 낸다면, 이는 **지금 실행된 GDB 세션에 Pwndbg가 실제로 로드되지 않았다**는 뜻이며, 원인은 대부분 `~/.gdbinit`에 Pwndbg가 안 걸려있거나, `setup.sh`를 가상환경(venv/conda) 안에서 돌려서 GDB가 쓰는 Python과 다른 곳에 설치됐거나, `sudo gdb`처럼 다른 `HOME`으로 실행해서 `.gdbinit`을 못 찾는 경우다.

## 언제 검색해야 하나
- `./setup.sh`를 분명히 실행했는데 `gdb`를 켜고 `vmmap`을 치면 `Undefined command: "vmmap".  Try "help".`가 뜰 때
- GDB 시작 배너에 Pwndbg 관련 문구가 전혀 안 뜨고 그냥 순정 GDB처럼 보일 때
- `sudo gdb -p PID`로는 명령어가 안 먹는데 `gdb ./chall`로는 될 때(또는 그 반대)
- 파이썬 가상환경(virtualenv, conda)을 쓰는 프로젝트 폴더에서 GDB를 켰을 때만 유독 Pwndbg가 안 먹을 때

## 가장 먼저 할 것
GDB를 켜자마자(아무 것도 안 치고) 화면에 Python 트레이스백이나 에러 메시지가 스크롤되어 지나가지 않았는지부터 다시 확인한다. `gdb -q -ex 'python import pwndbg' -ex quit`을 실행해서 import 자체가 성공하는지 직접 테스트하는 것이 가장 빠른 진단이다.

## 핵심 개념

### Pwndbg는 "GDB의 Python 확장"이며, `.gdbinit`을 통해 매번 새로 로드된다
Pwndbg는 별도 프로그램이 아니라 GDB의 내장 Python 인터프리터 위에서 동작하는 스크립트 모음이다. `./setup.sh`를 실행하면 보통 `~/.gdbinit`에 `source /경로/pwndbg/gdbinit.py` 같은 줄을 추가해서, **GDB가 켜질 때마다 이 줄을 읽어 Pwndbg를 import**하도록 설정한다. 즉 "설치"란 사실 이 한 줄이 `~/.gdbinit`에 잘 들어가 있고, 그 경로의 Python 코드가 정상적으로 import되는 것 전부다. 이 사슬의 어느 한 곳이 끊기면 GDB는 아무 오류 표시 없이(또는 스크롤되어 지나가는 트레이스백만 남기고) 그냥 순정 GDB로 켜진다.

### 원인 ① — 가상환경(virtualenv/conda) 충돌
GDB는 시스템에 설치된 `libpython`에 동적 링킹되어 있어서, **GDB의 Python 인터프리터는 항상 시스템 기본 Python(그리고 그 `site-packages`)을 본다** — 셸에서 `conda activate`나 `source venv/bin/activate`로 가상환경을 켠 상태에서 `./setup.sh`를 돌리면, Pwndbg가 필요로 하는 의존성 패키지들이 가상환경의 `site-packages`에 설치된다. 하지만 정작 GDB를 실행하면 GDB의 Python은 그 가상환경을 전혀 모르기 때문에 `import pwndbg`가 조용히 실패하고, 결과적으로 Pwndbg의 명령어가 하나도 등록되지 않는다.

### 원인 ② — 여러 개의 GDB, 또는 sudo로 인한 HOME 변경
시스템에 GDB가 여러 버전 설치돼 있을 수 있다(apt로 설치된 것, 소스 빌드한 것, `gdb-multiarch` 등). `setup.sh`는 실행 당시 `PATH`에서 찾은 특정 `gdb`를 기준으로 연결되므로, 이후 다른 `gdb` 바이너리를 실행하면 Pwndbg가 안 걸려있을 수 있다. 또한 `sudo gdb -p PID`처럼 attach에 root 권한이 필요해 `sudo`를 쓰면, 기본적으로 `HOME`이 `/root`로 바뀌어 GDB가 `/root/.gdbinit`을 찾는데 거기엔 Pwndbg 설정이 없을 수 있다.

### 원인 ③ — GDB/Pwndbg 버전 요구사항 불일치
Pwndbg는 특정 GDB/Python 최소 버전을 요구한다(예: Python 3.8+, GDB 9.2 이상 계열). 오래된 배포판의 구버전 GDB에서는 아예 로드가 안 되거나 로드는 되어도 일부 명령이 깨질 수 있다.

## 화면/코드에서 보이는 징후
```gdb
$ gdb ./chall
GNU gdb (Ubuntu 12.1-0ubuntu1~22.04) 12.1
(gdb) vmmap
Undefined command: "vmmap".  Try "help".
(gdb) context
Undefined command: "context".  Try "help".
```

## 단계별 절차

**1) Pwndbg의 Python import가 실제로 되는지 직접 테스트**
```bash
gdb -q -ex 'python import pwndbg' -ex quit
```
아무 출력 없이 종료되면 정상, `ModuleNotFoundError` 등 트레이스백이 뜨면 import 자체가 실패하는 것이다.

**2) `.gdbinit`에 Pwndbg가 실제로 걸려있는지 확인**
```bash
cat ~/.gdbinit
```
`source /home/user/pwndbg/gdbinit.py` 같은 줄이 있는지 확인한다. 없다면 Pwndbg 클론 디렉터리에서 `./setup.sh`를 다시 실행한다.

**3) 가상환경을 비활성화하고 재설치**
```bash
conda deactivate      # 또는 deactivate (virtualenv)
cd ~/pwndbg
./setup.sh
```
이렇게 하면 의존성이 시스템 Python `site-packages`에 설치되어 GDB가 실제로 참조하는 경로와 일치하게 된다.

**4) sudo로 attach해야 한다면 환경 변수 보존**
```bash
sudo -E gdb -p 1234
```
`-E`는 현재 사용자의 환경 변수(`HOME` 포함)를 그대로 유지시켜 `~/.gdbinit`을 계속 찾게 해준다. 또는 root 계정용으로 별도로 `sudo ./setup.sh`를 한 번 더 실행해 `/root/.gdbinit`에도 등록해둔다.

**5) GDB/Python 버전 확인**
```bash
gdb --version
python3 --version
```
Pwndbg GitHub 저장소의 README에 명시된 최소 버전과 비교한다. 너무 오래된 배포판이면 GDB를 업그레이드하거나, 그 배포판을 지원하는 과거 릴리스 태그의 Pwndbg를 체크아웃한다.

## 명령어/단축키
```bash
gdb -q -ex 'python import pwndbg' -ex quit
cat ~/.gdbinit
conda deactivate
deactivate
cd ~/pwndbg && ./setup.sh
sudo -E gdb -p PID
gdb --version
```

## 출력 해석
- `python import pwndbg`가 조용히 성공하면 Pwndbg 모듈 자체는 정상 설치된 것 — 문제는 `.gdbinit`이 그 import를 실제로 트리거하지 않는 데 있다.
- `ModuleNotFoundError: No module named 'xxx'`가 뜨면 Pwndbg의 의존성 패키지가 GDB의 Python이 보는 `site-packages`에 없다는 뜻 — 가상환경 충돌을 의심한다.
- `cat ~/.gdbinit`에 아무 내용도 없거나 Pwndbg 관련 줄이 없으면 애초에 `setup.sh`가 이 계정의 `HOME`에 대해 실행된 적이 없다는 뜻이다.

## 흔한 실수
- `./setup.sh`를 conda/venv가 활성화된 상태에서 실행해놓고 이후 매번 헷갈려하는 것 — 반드시 비활성화 상태에서 재실행한다.
- `sudo gdb`로 attach할 때마다 Pwndbg가 없어서 당황하는 것 — `HOME`이 바뀌는 게 원인이라는 걸 모르면 매번 재설치를 시도하게 된다.
- GDB를 여러 개 설치해두고 어느 것에 `setup.sh`가 연결됐는지 확인 안 하는 것 — `which gdb`로 지금 쓰는 GDB 경로부터 확인한다.
- 오류 메시지(`Undefined command`)를 "Pwndbg가 이 명령어를 지원하지 않는다"로 오해하는 것 — 이건 순정 GDB가 "그런 명령어 자체를 모른다"는 뜻이지, Pwndbg가 로드는 됐는데 이 기능만 없다는 뜻이 아니다.

## 막혔을 때 다음 체크
- import는 되는데 `context` 화면이 깨져 보인다면(로드는 됨) → REV-0691 Pwndbg 버전 문제로 context가 깨져 보일 때
- Pwndbg 없이 순정 GDB로 메모리를 봐야 한다면 → REV-0189 GDB x 명령으로 메모리 보기
- attach 자체가 권한 문제로 막힌다면 → REV-0692 GDB attach가 permission denied로 실패할 때(ptrace_scope)
- GDB 자체 설치/설정이 궁금하면 → REV-0283 GDB 설치와 기본 설정

## 미니 예제
```bash
$ conda activate myenv
(myenv) $ cd ~/pwndbg && ./setup.sh   # 의존성이 myenv 안에 설치됨
(myenv) $ conda deactivate
$ gdb ./chall
(gdb) vmmap
Undefined command: "vmmap".  Try "help".
$ conda deactivate   # 이미 비활성화됨을 재확인
$ cd ~/pwndbg && ./setup.sh   # 시스템 Python 기준으로 재설치
$ gdb ./chall
(gdb) vmmap
LEGEND: STACK | HEAP | CODE | DATA | RWX | RODATA
0x555555554000     0x555555555000 r--p     1000 0      /home/user/chall
```
가상환경이 켜진 채로 설치했던 첫 시도는 실패했지만, 비활성화 후 재설치하자 `vmmap`이 정상 동작했다.

## 관련 글
- REV-0691 — Pwndbg 버전 문제로 context가 깨져 보일 때
- REV-0692 — GDB attach가 permission denied로 실패할 때(ptrace_scope)
- REV-0283 — GDB 설치와 기본 설정
- REV-0284 — GDB 명령어 치트시트

## 출처/검증
- Pwndbg 설치 절차(`setup.sh`, `~/.gdbinit` 등록)와 GDB 버전 요구사항: Pwndbg 공식 저장소(pwndbg/pwndbg) README 및 공식 문서(pwndbg.re) 기준.
- GDB가 시스템 `libpython`에 동적 링킹되어 가상환경의 Python을 인식하지 못하는 동작: GDB 공식 문서 "Python API" 섹션 및 일반적인 GDB Python 확장 개발 문서에서 공통적으로 설명하는 제약 사항 기준 (2026-09-08 검증).
- `sudo -E`로 환경 변수(`HOME`)를 보존하는 동작: `sudo(8)` man page 기준.
