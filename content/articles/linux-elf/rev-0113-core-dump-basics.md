---
id: REV-0113
title: "Core dump와 크래시 지점 분석 기초"
slug: "rev-0113-core-dump-basics"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, "readelf", "binutils"]
keywords: ["core dump", "core file", "ET_CORE", "ulimit -c", "core_pattern", "coredumpctl", "segfault 분석"]
aliases: ["코어덤프란", "core dump 분석", "코어파일 분석", "segfault 크래시 분석", "core 파일 열기"]
symptom_keywords: ["segmentation fault 발생 후 원인 파악 안됨", "core dump가 안 생김", "core 파일을 어떻게 여는지 모름", "크래시 지점을 못 찾겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
core dump(코어 덤프)는 프로그램이 세그폴트 등으로 비정상 종료되는 순간의 **메모리 전체 스냅샷을 담은 ELF 파일**(`e_type == ET_CORE`)이며, GDB로 원본 실행 파일과 함께 열면 크래시 당시의 레지스터, 스택, 힙 상태를 그대로 재현해서 "정확히 어느 명령어에서 왜 죽었는지"를 사후에도 분석할 수 있다.

## 언제 검색해야 하나
- 프로그램이 `Segmentation fault (core dumped)`를 출력하고 죽었는데, 그 순간을 재현하지 않고도 원인을 분석하고 싶을 때
- `core_pattern` 설정이나 `ulimit -c` 때문에 core 파일이 생성되지 않아서 당황할 때
- CTF/실전에서 크래시를 유발하는 입력을 찾았고, 이제 그 크래시가 정확히 어느 함수·어느 명령어·어느 오프셋에서 발생했는지 알아내야 할 때
- pwn 문제에서 익스플로잇 스크립트가 왜 세그폴트를 내는지 디버깅해야 할 때

## 핵심 개념

### core dump는 그 자체로 ELF 파일이다
core dump는 별도의 특수 포맷이 아니라 **ELF 포맷을 그대로 재사용**한다. ELF 헤더(REV-0089 참고)의 `e_type` 필드가 `ET_CORE`(4)로 설정되어 있을 뿐, 나머지 구조(Program Header 등)는 일반 실행 파일과 같은 방식으로 해석된다. 다만 core 파일에는 Section Header가 없고(분석 시점에 링킹할 필요가 없으므로), Program Header의 각 `PT_LOAD` 세그먼트가 "크래시 당시 프로세스의 각 메모리 매핑(코드, 스택, 힙, 매핑된 라이브러리 등)을 그대로 복사한 것"이 된다. 추가로 `PT_NOTE` 세그먼트에 레지스터 값(`NT_PRSTATUS`), 프로세스 정보, 시그널 정보 같은 메타데이터가 들어있다.

즉 core 파일 하나에는: 크래시 시점의 **모든 레지스터 값**, **스택 전체 내용**, **힙 전체 내용**, **로드되어 있던 모든 공유 라이브러리의 메모리 이미지**가 고스란히 들어있다. 원본 실행 파일과 함께 GDB에 올리면, 마치 그 순간에 프로그램이 멈춰있는 것처럼 완전히 재구성해서 볼 수 있다.

### core dump가 왜 안 생기는가 (실전에서 가장 먼저 부딪히는 문제)
Linux 배포판 대부분은 기본적으로 core dump 생성을 제한하거나 다른 방식으로 가로챈다:
1. **`ulimit -c` (리소스 제한)**: 셸의 core dump 크기 제한이 기본값 `0`인 경우가 많다. `0`이면 아무리 크래시가 나도 core 파일이 생성되지 않는다.
2. **`/proc/sys/kernel/core_pattern`**: 커널이 core dump를 어디에 어떤 이름으로 쓸지(또는 어떤 프로그램에 파이프로 넘길지) 결정하는 설정. Ubuntu 등 데스크톱 배포판은 기본적으로 `apport`(오류 보고 도구)나 `systemd-coredump`로 파이프하도록 설정되어 있어, 단순히 `./chall.core`처럼 파일이 뚝 떨어지지 않는다.
3. **SUID 바이너리**: 보안상 SUID 비트가 설정된 프로그램은 기본적으로 core dump가 생성되지 않는다(`prctl(PR_SET_DUMPABLE)` 관련 커널 정책).

### 왜 core dump 분석이 유용한가
크래시를 "재현"하지 않고도(예: 서버가 이미 죽어서 로그만 남은 상황, 랜덤성 때문에 재현이 어려운 경우) 사후 분석이 가능하다는 게 가장 큰 장점이다. 또한 라이브 디버깅과 달리 프로세스가 실제로 멈춰있는 게 아니라 파일이므로, 얼마든지 시간을 들여 반복해서 같은 상태를 재검사할 수 있다.

## 화면/코드에서 보이는 징후
- 셸에서 프로그램 실행 후 `Segmentation fault (core dumped)` 메시지 출력
- `ls core*` 또는 `ls core.<PID>`로 현재 디렉터리에 core 파일이 보임(설정에 따라 다른 경로일 수 있음)
- `file core` 실행 시 `ELF 64-bit LSB core file` 같은 결과

## 가장 먼저 할 것
크래시가 재현 가능하다면 굳이 core dump 설정을 건드리지 않고 바로 GDB로 실행하며 크래시를 잡는 것(`gdb -q ./chall`, `run`, 크래시 시 자동으로 멈춤)이 더 빠르다. core dump는 **크래시를 재현하기 어렵거나, 재현할 수 없는 상황**(이미 발생한 로그만 있음, 랜덤 요소가 있음, 서버 프로세스가 죽고 남은 core만 있음)에서 진가를 발휘한다.

## 단계별 절차

**1) core dump가 생성되도록 설정 확인/변경**
```bash
ulimit -c unlimited          # 현재 셸 세션에서 core 크기 제한 해제
cat /proc/sys/kernel/core_pattern
```
`core_pattern`이 `core`나 `core.%p`처럼 단순 파일명이면 현재 작업 디렉터리(또는 지정된 경로)에 바로 생성된다. `|/usr/share/apport/apport ...`처럼 파이프(`|`)로 시작하면 다른 프로그램이 가로채고 있다는 뜻이다.

**2) (Ubuntu 등 apport/systemd-coredump 환경) core_pattern을 일시적으로 단순화**
```bash
sudo sysctl -w kernel.core_pattern=core.%p
```
CTF 로컬 환경이나 개인 VM에서만 이렇게 바꾸고, 공용 서버에서는 함부로 바꾸지 않는다.

**3) 크래시 유발 및 core 파일 생성**
```bash
ulimit -c unlimited
./chall < crash_input.txt
ls -la core*
```

**4) systemd-coredump를 쓰는 배포판이면 coredumpctl로 조회**
```bash
coredumpctl list                 # 최근 크래시 목록
coredumpctl gdb                  # 가장 최근 core를 바로 GDB로 열기
coredumpctl dump <PID> -o out.core   # 파일로 추출
```

**5) GDB로 core 파일 열기 (핵심 단계)**
```bash
gdb ./chall core
```
또는 실행 중:
```gdb
(gdb) file ./chall
(gdb) core-file core
```

**6) 크래시 지점 확인**
```gdb
(gdb) bt              # 백트레이스: 크래시 시점 콜스택
(gdb) info registers   # 크래시 시점 레지스터 전체 값
(gdb) x/5i $pc         # 크래시 시점 명령어 (크래시 난 그 명령어 포함)
(gdb) print $rdi       # 특정 레지스터 값 확인
```
`bt`의 맨 위(#0)가 실제로 죽은 함수, 그 아래로 호출한 함수들이 순서대로 나온다.

**7) 크래시 원인이 된 메모리 주소 확인**
```gdb
(gdb) info signal        # 어떤 시그널로 죽었는지(SIGSEGV 등)
(gdb) print $_siginfo
```
SIGSEGV라면, 접근하려던 주소가 유효하지 않았거나 권한이 없었다는 뜻이다. `bt full`로 각 스택 프레임의 지역 변수 값까지 함께 확인하면 어떤 값이 잘못된 포인터/오프셋을 만들었는지 추적할 수 있다.

**8) Pwndbg를 쓴다면 더 편하게**
```gdb
(gdb) bt
(gdb) context
```
Pwndbg가 설치되어 있으면 core 파일을 열었을 때도 레지스터/스택/디스어셈블리를 한 화면에 색깔로 정리해서 보여준다.

## 명령어/단축키
```bash
ulimit -c unlimited
cat /proc/sys/kernel/core_pattern
coredumpctl list / coredumpctl gdb
gdb ./chall core
```
GDB: `bt`, `bt full`, `info registers`, `x/5i $pc`, `info signal`, `print $_siginfo`

## 출력 해석
- `bt`(backtrace)의 `#0` 프레임 함수 이름이 strip 등으로 안 보이면 그냥 주소만 나온다 — 그 주소를 `objdump -d`(REV-0092)로 다시 찾아서 원본 실행 파일의 어느 함수인지 대조한다.
- `info registers`에서 `rip`(또는 `pc`) 값이 실행 가능한 코드 영역이 아닌 이상한 값(예: `0x4141414141414141` — `AAAAAAAA`)이라면, 스택 버퍼 오버플로우로 리턴 주소가 사용자 입력으로 덮여서 발생한 크래시라는 강력한 단서다.
- PIE 바이너리의 core dump라면 주소가 ASLR 베이스 기준 절대 주소로 찍혀 있으므로, `info proc mappings`(core 안에도 매핑 정보가 있다면)로 베이스를 확인하고 정적 분석 주소와 비교할 오프셋을 계산해야 한다.

## 흔한 실수
- 크래시 후 `ls`로 core 파일이 안 보이면 "core dump 기능 자체가 없다"고 포기하는 것 — 대부분 `ulimit -c 0`이거나 `core_pattern`이 다른 프로그램으로 파이프되어 있을 뿐이다. 두 가지를 먼저 확인해야 한다.
- `gdb ./chall`만 실행하고 core 파일을 같이 지정하지 않아서 그냥 빈 상태로 여는 것 — `gdb ./chall core` 형태로 두 인자를 함께 줘야 하며, 실행 파일과 core가 서로 대응하는 쌍이어야 한다(다른 빌드의 실행 파일에 core를 물리면 심볼/주소가 안 맞는다).
- core dump 안의 주소가 지금 이 컴퓨터에서 재실행했을 때의 주소와 같을 거라 가정하는 것 — PIE + ASLR이면 매번 로드 베이스가 다르므로, core 파일 안에 기록된 주소는 **그 크래시가 발생했던 그 순간에만 유효한 값**이다.
- SUID/보안 제약이 있는 바이너리에서 core dump가 왜 안 나오는지 원인을 못 찾는 것 — `cat /proc/sys/kernel/suid_dumpable` 값을 함께 확인한다.

## 막혔을 때 다음 체크
- ELF의 `e_type`이 `ET_CORE`로 어떻게 표시되는지 다시 보고 싶으면 → [REV-0089 ELF 헤더 읽는 법](./rev-0089-elf-header.md)
- 크래시 지점 코드를 정적으로도 대조하고 싶으면 → [REV-0092 objdump 기본 사용법](./rev-0092-objdump-basics.md)
- 크래시가 스택 오버플로우 계열인지 미리 가늠하려면 → [REV-0096 checksec 결과 읽는 법](./rev-0096-checksec.md)의 Canary/NX 항목
- 애초에 `main`이나 크래시가 발생한 함수 자체를 아직 못 찾았다면 → [REV-0009 main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)

## 미니 예제
```bash
$ ulimit -c unlimited
$ ./chall < bad_input.txt
Segmentation fault (core dumped)
$ ls core*
core

$ gdb -q ./chall core
Core was generated by `./chall'.
Program terminated with signal SIGSEGV, Segmentation fault.
#0  0x0000000000401196 in vuln_func ()
(gdb) bt
#0  0x0000000000401196 in vuln_func ()
#1  0x0000000000401220 in main ()
(gdb) info registers rip
rip            0x401196   0x401196 <vuln_func+45>
```
`bt` 결과로 크래시가 `vuln_func` 안에서, `main`이 그 함수를 호출한 직후 발생했다는 콜스택을 재현 없이 확보했다.

## 관련 글
- [REV-0089 — ELF 헤더 읽는 법](./rev-0089-elf-header.md)
- [REV-0092 — objdump 기본 사용법](./rev-0092-objdump-basics.md)
- [REV-0096 — checksec 결과 읽는 법](./rev-0096-checksec.md)
- [REV-0009 — main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)

## 출처/검증
- core dump ELF 구조(`ET_CORE`, `PT_NOTE`, `NT_PRSTATUS`): System V ABI 및 Linux 커널 `fs/binfmt_elf.c`의 core dump 생성 로직 개념 기준 (2026-09-08 검증).
- `core_pattern`, `ulimit -c` 동작: `core(5)` man page(`man 5 core`) 기준.
- GDB core 파일 분석 명령(`core-file`, `bt`, `info registers`): GDB 공식 문서, "Debugging an Already-running Process" 및 "Core Dumps" 섹션 기준.
- `coredumpctl`/systemd-coredump: systemd 공식 문서 `coredumpctl(1)` 기준.
