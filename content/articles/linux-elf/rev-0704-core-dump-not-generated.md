---
id: REV-0704
title: "Core dump가 생성되지 않을 때 설정 확인하기"
slug: "rev-0704-core-dump-not-generated"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["ulimit", "coredumpctl", "sysctl"]
keywords: ["core dump 안 생김", "ulimit -c", "core_pattern", "coredumpctl", "systemd-coredump"]
aliases: ["core dump 파일이 안 만들어짐", "core 파일 어디 있음", "core dump 설정", "ulimit -c unlimited"]
symptom_keywords: ["Segmentation fault (core dumped)라고 뜨는데 core 파일이 없음", "현재 디렉터리에 core 파일이 안 보임", "core dump가 비활성화되어 있음", "Docker 컨테이너에서 core dump가 안 남음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
셸이 `Segmentation fault (core dumped)`라고 출력해도 실제로 `core` 파일이 생성되지 않는 경우가 흔한데, 원인은 대부분 `ulimit -c 0`(core 크기 제한 0)이거나 `/proc/sys/kernel/core_pattern`이 `apport`나 `systemd-coredump` 같은 다른 프로그램으로 파이프되어 있어서 현재 디렉터리가 아닌 다른 곳에 저장되기 때문이다.

## 언제 검색해야 하나
- 콘솔에는 `(core dumped)`라고 나오는데 `ls`로 봐도 현재 디렉터리에 `core` 파일이 없을 때
- REV-0703 절차대로 GDB에서 크래시를 사후 분석(`gdb ./chall core`)하려는데 core 파일 자체가 없어서 시작을 못 할 때
- Docker 컨테이너나 CI 환경에서 core dump가 전혀 안 남을 때
- setuid 바이너리를 실행했을 때만 유독 core dump가 안 생길 때

## 핵심 개념

### ulimit -c — 셸 세션 단위의 core 크기 제한
`ulimit -c`는 현재 셸 세션에서 생성 가능한 core dump 파일의 최대 크기(KB 단위)를 정한다. 많은 배포판이 기본값을 `0`으로 설정해두는데, 이 경우 커널은 크래시가 나도 "만들 수 있는 최대 크기가 0이니 아예 안 만든다"고 처리해 core 파일이 생성되지 않는다. **이 값은 셸(터미널) 단위로 적용**되므로, 다른 터미널에서 `ulimit -c unlimited`를 설정해도 정작 프로그램을 실행하는 그 셸에서 다시 설정하지 않으면 적용되지 않는다는 점이 자주 헷갈리는 부분이다.

### core_pattern — core dump가 실제로 저장되는 위치/방식을 결정
`/proc/sys/kernel/core_pattern`은 커널이 core dump를 어떤 이름으로, 어디에 쓸지(또는 다른 프로그램으로 넘길지) 정하는 설정이다. 기본값이 `core`처럼 단순 파일명이면 현재 작업 디렉터리에 `core`라는 이름으로 생긴다. 하지만 Ubuntu 계열은 기본적으로 `|/usr/share/apport/apport %p %s %c %d %P %E`처럼 **파이프(`|`)로 시작해서 apport라는 별도 프로그램에 core dump를 넘기도록** 설정되어 있고, systemd 기반 배포판은 `systemd-coredump`로 넘기는 경우가 많다. 이 경우 현재 디렉터리에는 아무 파일도 안 남고, 대신 `coredumpctl list` 같은 별도 명령으로 조회해야 한다.

### suid_dumpable — setuid 바이너리의 core dump 제한
setuid 비트가 설정된 바이너리는 보안상 기본적으로 core dump가 생성되지 않는다(`/proc/sys/kernel/suid_dumpable` 기본값 `0`). CTF에서 setuid 바이너리를 다루는데 core dump가 안 남는다면 이 설정도 원인 후보다.

### 컨테이너 환경의 추가 제약
Docker 컨테이너는 기본적으로 `ulimit -c 0`으로 시작하는 경우가 많고, 호스트의 `core_pattern`이 파이프 방식(`|...`)이면 그 파이프 대상 프로그램이 컨테이너 네임스페이스 밖에 있어 컨테이너 안에서 core dump가 아예 만들어지지 않을 수 있다. 이 경우 컨테이너 실행 시 `--ulimit core=unlimited`를 주고, 호스트의 `core_pattern`을 컨테이너 내부에서도 접근 가능한 단순 경로로 바꾸는 것이 필요할 수 있다.

## 화면/코드에서 보이는 징후
```
$ ./chall
Segmentation fault (core dumped)
$ ls
chall
$ ulimit -c
0
```
`(core dumped)`라는 메시지와 실제 파일 부재가 동시에 나타나는 것이 핵심 증상이다.

## 가장 먼저 할 것
`ulimit -c` 값부터 확인한다. `0`이면 `ulimit -c unlimited`로 바꾸고 같은 셸에서 다시 실행해본다. 그래도 안 나오면 `cat /proc/sys/kernel/core_pattern`을 확인한다.

## 단계별 절차
1. `ulimit -c`로 현재 셸의 core 크기 제한 확인
2. `0`이면 `ulimit -c unlimited` 실행 후 같은 셸에서 프로그램 재실행
3. `cat /proc/sys/kernel/core_pattern` 확인 — 값이 `|`로 시작하면 apport/systemd-coredump로 위임된 것
4. systemd-coredump 환경이면 `coredumpctl list`로 목록 확인, `coredumpctl dump <PID> -o core.dump`로 실제 파일 추출
5. apport라면 `/var/crash/` 아래에 리포트가 쌓였는지 확인, 필요하면 apport 대신 단순 `core` 파일로 남기도록 root 권한으로 `core_pattern`을 `core`로 임시 변경(`echo core | sudo tee /proc/sys/kernel/core_pattern`)
6. setuid 바이너리라면 `cat /proc/sys/kernel/suid_dumpable` 확인, 필요시 값 변경(테스트 환경 한정)
7. Docker 컨테이너라면 `docker run --ulimit core=unlimited ...`로 재시도

## 명령어/단축키
```bash
ulimit -c
ulimit -c unlimited
cat /proc/sys/kernel/core_pattern
echo core | sudo tee /proc/sys/kernel/core_pattern
coredumpctl list
coredumpctl dump <PID> -o core.dump
cat /proc/sys/kernel/suid_dumpable
docker run --ulimit core=unlimited ...
```

## 출력 해석
`core_pattern` 값이 `core`나 `core.%p`처럼 평범한 문자열이면 현재 디렉터리(또는 지정 경로)에 그 이름으로 파일이 남아야 정상이다. `|/usr/share/apport/apport ...`처럼 파이프로 시작하면 파일이 안 남는 게 정상 동작이며, `coredumpctl`이나 `/var/crash/`를 대신 봐야 한다. `ulimit -c` 값이 `0`이면 그 어떤 `core_pattern` 설정과도 무관하게 core dump 자체가 생성되지 않는다.

## 흔한 실수
- `ulimit -c unlimited`를 다른 터미널 탭이나 이전 세션에서만 설정하고, 정작 프로그램을 실행하는 셸에서는 적용 안 된 상태로 착각하는 것.
- `core_pattern`이 apport/systemd-coredump로 위임된 걸 모르고 계속 현재 디렉터리에서만 `core` 파일을 찾는 것.
- setuid 바이너리인 걸 눈치채지 못하고 일반 바이너리와 같은 방식으로 core dump가 생길 거라 기대하는 것.
- GDB 안에서 `run`으로 직접 크래시를 재현하면 core dump 파일 없이도 바로 분석할 수 있다는 사실(REV-0703)을 모르고, core dump 설정만 붙잡고 시간을 쓰는 것.

## 막혔을 때 다음 체크
- core dump 없이도 GDB로 바로 크래시 지점을 잡는 방법이 필요하면 → REV-0703 Segmentation fault가 나는데 원인 위치를 못 찾을 때.
- 만들어진 core 파일을 실제로 GDB에서 여는 기본 개념이 궁금하면 → REV-0113 Core dump와 크래시 지점 분석 기초.
- 종료 코드만으로 시그널 종류를 먼저 좁히고 싶으면 → REV-0661 리눅스 프로세스 종료 코드(Exit Code)로 크래시 원인 좁히기.

## 미니 예제
```bash
$ ulimit -c
0
$ ulimit -c unlimited
$ ./chall
Segmentation fault (core dumped)
$ ls
chall  core
$ gdb ./chall core
```
`ulimit -c unlimited`를 적용한 뒤에야 `core` 파일이 실제로 생성되어 `gdb ./chall core`로 사후 분석을 시작할 수 있었다.

## 관련 글
- REV-0703 — Segmentation fault가 나는데 원인 위치를 못 찾을 때
- REV-0113 — Core dump와 크래시 지점 분석 기초
- REV-0661 — 리눅스 프로세스 종료 코드(Exit Code)로 크래시 원인 좁히기

## 출처/검증
- `ulimit -c`가 셸 세션 단위로 core dump 최대 크기를 제한하는 동작: `bash(1)` 및 `setrlimit(2)` 공식 매뉴얼 기준.
- `/proc/sys/kernel/core_pattern`의 파이프(`|`) 문법과 apport/systemd-coredump 위임 동작: `core(5)` 공식 매뉴얼 및 systemd `systemd-coredump(8)` 공식 문서 기준 (2026-09-09 검증).
- `suid_dumpable`이 setuid 바이너리의 core dump 생성 여부를 제어하는 점: Linux 커널 문서(`Documentation/admin-guide/sysctl/kernel.rst`) 기준.
