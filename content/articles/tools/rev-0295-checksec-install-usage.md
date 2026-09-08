---
id: REV-0295
title: "checksec 설치와 사용법"
slug: "rev-0295-checksec-install-usage"
category: "tools"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["checksec", "pwntools"]
keywords: ["checksec 설치", "checksec 사용법", "pwn checksec", "checksec.sh"]
aliases: ["checksec 설치법", "checksec 실행 방법", "checksec 셋업"]
symptom_keywords: ["checksec 명령이 없다고 뜸", "checksec command not found", "checksec 설치가 안됨"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`checksec`은 별도 컴파일 없이 셸 스크립트 하나 또는 `pwntools` 패키지에 딸려오는 파이썬 구현으로 바로 쓸 수 있으며, 오프라인 대회 전에는 반드시 둘 중 하나를 미리 준비해 두어야 당일 인터넷 없이 바로 실행할 수 있다.

## 언제 검색해야 하나
- `checksec` 명령을 쳤는데 "command not found"가 뜰 때
- 오프라인 대회를 준비하며 `checksec`을 어떤 방식으로 미리 설치해 둘지 결정해야 할 때
- `checksec.sh` 스크립트와 `pwntools`에 포함된 `checksec` 중 어느 쪽을 쓸지 고민될 때

RELRO/Canary/NX/PIE/Fortify 각 항목이 의미하는 바와 결과 해석, 공격 전략 연결은 이 문서에서 다루지 않는다. → [REV-0096 checksec 결과 읽는 법](../linux-elf/rev-0096-checksec.md) 참고.

## 핵심 개념
"checksec"이라는 이름으로 실전에서 마주치는 것은 크게 두 가지 서로 다른 구현체다.

1. **`checksec.sh`(원조 셸 스크립트)** — Trail of Bits 등 여러 곳에서 관리해온 독립 실행형 bash 스크립트. `readelf`, `file` 같은 표준 binutils 명령만으로 판정을 계산하므로 의존성이 거의 없다.
2. **`pwntools`에 내장된 `checksec`** — `pwntools`(REV-0300 참고)를 설치하면 `pwn checksec` 서브커맨드, 그리고 파이썬 스크립트 안에서 `pwnlib.elf.ELF(...).checksec()`로도 같은 정보를 얻을 수 있다. CTF 참가자 대부분이 이미 `pwntools`를 설치해 두므로 별도 설치 없이 바로 쓸 수 있다는 장점이 있다.

두 구현의 판정 항목(RELRO/Canary/NX/PIE/Fortify)은 동일한 개념을 다루지만 출력 형식이 조금 다를 수 있다.

## 화면/코드에서 보이는 징후
`checksec` 명령을 쳤을 때 셸이 "command not found"를 출력하거나, `pwn checksec`이 "No such command" 류의 오류를 낼 때가 이 문서를 찾아야 할 신호다.

## 가장 먼저 할 것
설치된 파이썬 환경에 `pwntools`가 이미 있는지 먼저 확인한다.
```bash
python3 -c "import pwn; print(pwn.__version__)"
```
있다면 별도 설치 없이 바로 `pwn checksec ./chall`을 쓸 수 있다. 없다면 아래 셸 스크립트 설치로 넘어간다.

## 단계별 절차

### 1) 방법 A — 독립 checksec.sh 스크립트 (권장, 의존성 최소)
```bash
# 온라인 상태에서 미리 받아 실행 권한 부여
curl -o checksec https://raw.githubusercontent.com/slimm609/checksec.sh/master/checksec
chmod +x checksec
./checksec --file=./chall
```
오프라인 대회를 준비한다면 위 스크립트 파일 하나(순수 텍스트 bash 스크립트)를 대회용 USB/외장 SSD에 미리 복사해 두면 된다. 내부적으로 `readelf`, `file`, `grep` 등 표준 리눅스 유틸리티만 사용하므로 대상 서버/PC에 `readelf`만 있으면 추가 설치 없이 그대로 동작한다.

### 2) 방법 B — 배포판 패키지 (있는 경우)
일부 배포판은 저장소에 `checksec` 패키지를 제공한다.
```bash
sudo apt install checksec   # Debian/Ubuntu 계열, 저장소에 있는 경우
```
패키지 유무와 버전은 배포판마다 다르므로, 오프라인 대회 전 사용할 배포판에서 미리 확인해 두어야 한다.

### 3) 방법 C — pwntools에 포함된 checksec (이미 pwntools를 쓴다면 가장 간단)
```bash
pip install pwntools   # 온라인 상태에서 미리 설치, 오프라인 준비는 REV-0300 참고
pwn checksec ./chall
```
파이썬 스크립트 안에서 직접 호출할 수도 있다.
```python
from pwn import *
e = ELF('./chall')
print(e.checksec())
```

### 4) 동작 확인
어떤 방법을 택했든 다음 명령으로 5개 항목(RELRO/Canary/NX/PIE/Symbols)이 표로 출력되면 정상 설치된 것이다.
```bash
checksec --file=./chall
# 또는
pwn checksec ./chall
```

## 명령어/단축키
```bash
checksec --file=./chall            # checksec.sh 방식
pwn checksec ./chall               # pwntools 방식
checksec --file=./libc.so.6        # 제공된 libc 자체도 검사 가능
```

## 흔한 실수
- 온라인 상태에서 미리 스크립트/패키지를 받아두지 않고 대회 당일 인터넷 없는 환경에서 `curl`/`pip install`이 실패하는 것 — 오프라인 대회 전 반드시 사전 준비 단계에서 설치와 실행까지 검증해야 한다.
- `checksec.sh`와 `pwn checksec`의 출력 형식이 약간 달라서 "결과가 이상하다"고 착각하는 것 — 두 구현 모두 같은 ELF 정보를 다른 스타일로 보여줄 뿐이며, 항목이 5개(RELRO/Canary/NX/PIE/Symbols) 안팎으로 일치하는지만 확인하면 된다.
- 실행 권한을 안 주고 `./checksec`을 실행해 "Permission denied"를 만나는 것 — `chmod +x checksec`을 먼저 해야 한다.

## 막혔을 때 다음 체크
- 결과 표의 각 항목이 무슨 뜻인지, 공격 전략에 어떻게 연결되는지 → [REV-0096 checksec 결과 읽는 법](../linux-elf/rev-0096-checksec.md)
- `checksec` 자체를 못 쓰는 극단적인 환경이라면 `readelf`로 수동 판정 가능 → REV-0096의 "checksec 없이 readelf만으로 직접 확인" 절 참고
- `pwntools` 오프라인 설치 전반 → [REV-0300 Z3 angr pwntools Python 오프라인 패키지 준비](./rev-0300-offline-python-packages.md)

## 미니 예제
```bash
$ checksec --file=./chall
[*] '/home/user/chall'
    Arch:     amd64-64-little
    RELRO:    Full RELRO
    Stack:    Canary found
    NX:       NX enabled
    PIE:      PIE enabled
```
한 줄로 "카나리·NX·PIE·Full RELRO가 전부 켜진 바이너리"임을 파악했다 — 스택 오버플로를 노린다면 카나리부터 우회해야 하고, 주소는 매 실행마다 바뀐다는 뜻이다.

## 관련 글
- REV-0096 — checksec 결과 읽는 법
- REV-0300 — Z3 angr pwntools Python 오프라인 패키지 준비
- REV-0294 — readelf objdump nm strings 치트시트

## 출처/검증
- `checksec.sh` 배포 방식과 URL: `slimm609/checksec.sh` 공식 GitHub 저장소 기준.
- `pwn checksec` 서브커맨드 및 `pwnlib.elf.ELF.checksec()`: pwntools 공식 문서(https://docs.pwntools.com) 기준.
- 이 문서의 설치 명령은 실제 환경에서 재현 실행하지 못했으며, `curl` URL·패키지명은 리포지토리 구조 변경 시 달라질 수 있으므로 오프라인 키트 준비 단계에서 반드시 접속 확인 후 캐싱할 것을 권장한다.
