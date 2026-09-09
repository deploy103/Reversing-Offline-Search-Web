---
id: REV-0692
title: "GDB attach가 permission denied로 실패할 때(ptrace_scope)"
slug: "rev-0692-gdb-attach-permission-denied-ptrace-scope"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB]
keywords: ["ptrace_scope", "yama ptrace_scope", "GDB attach permission denied", "ptrace Operation not permitted", "kernel.yama.ptrace_scope"]
aliases: ["gdb attach 권한 오류", "ptrace Operation not permitted 해결", "yama 보안 모듈 ptrace 제한"]
symptom_keywords: ["gdb -p PID 했더니 Operation not permitted", "attach 명령이 permission denied로 실패", "루트도 아닌데 attach가 왜 안되는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`gdb -p PID`나 GDB 안에서 `attach PID`를 실행했을 때 `ptrace: Operation not permitted`가 뜬다면, 대부분 프로세스 소유권 문제가 아니라 리눅스 Yama 보안 모듈의 `kernel.yama.ptrace_scope` 설정이 "자기 자신이 낳은 자식 프로세스에만 attach 허용"으로 걸려 있는 것이 원인이며, 값을 `0`으로 바꾸거나 `sudo`로 실행하면 해결된다.

## 언제 검색해야 하나
- `gdb -p 12345` 또는 GDB 안에서 `attach 12345`를 실행했는데 `ptrace: Operation not permitted`가 뜰 때
- 분명 내가 소유한(같은 사용자로 실행한) 프로세스인데도 attach가 거부될 때
- root가 아닌 일반 사용자로 GDB를 쓰다가 이미 떠 있는 서버/데몬 프로세스에 붙으려 할 때
- CTF 문제를 로컬에서 먼저 실행해두고 나중에 GDB로 붙여서 분석하려는데 이 오류를 만났을 때

## 핵심 개념
리눅스 커널의 Yama LSM(Linux Security Module)은 `/proc/sys/kernel/yama/ptrace_scope` 값으로 `ptrace` 허용 범위를 제한한다.
```text
0 = classic — 같은 사용자 권한이면 임의 프로세스에 attach 가능
1 = restricted (기본값, 대부분의 데스크톱 배포판) — 오직 부모-자식 관계(직접 fork해서 만든 자식)만 attach 가능
2 = admin-only — CAP_SYS_PTRACE 권한(root)이 있어야만 가능
3 = no attach — 어떤 프로세스도 attach 불가(재부팅 전까지 되돌릴 수 없음)
```
Ubuntu 등 다수의 데스크톱/서버 배포판은 기본값이 `1`(restricted)이다. 이 값에서는 GDB로 **이미 실행 중인 임의의 프로세스**에 `attach`하는 것이 막힌다 — GDB가 그 프로세스를 직접 `fork`해서 낳은 자식이 아니기 때문이다. 반면 `gdb ./chall`로 GDB가 직접 프로세스를 새로 실행(`run`)하는 경우는 GDB 자신이 부모가 되므로 이 제한에 걸리지 않는다. 즉, "이미 떠 있는 프로세스에 나중에 붙는" 시나리오에서만 이 문제가 나타난다.

## 화면/코드에서 보이는 징후
```bash
$ gdb -p 12345
Attaching to process 12345
ptrace: Operation not permitted.
```
또는 GDB를 이미 실행한 상태에서:
```gdb
(gdb) attach 12345
Attaching to process 12345
ptrace: Operation not permitted.
```
자신이 소유한(같은 사용자로 실행한) 프로세스인데도 이 오류가 나서 당황하기 쉽다. 파일 권한(`chmod`)이나 sudo 여부와는 무관하게 이 메시지 그대로 발생한다.

## 가장 먼저 할 것
```bash
cat /proc/sys/kernel/yama/ptrace_scope
```
`1` 이상이 나오면 바로 이것이 원인이다.

## 단계별 절차
**1) 임시로 값을 0으로 낮추기(가장 흔한 해결책, 재부팅 시 원복됨)**
```bash
sudo sysctl -w kernel.yama.ptrace_scope=0
```
**2) 영구 적용하려면 sysctl 설정 파일에 기록**
```bash
echo "kernel.yama.ptrace_scope = 0" | sudo tee /etc/sysctl.d/10-ptrace.conf
sudo sysctl --system
```
**3) 설정을 바꾸고 싶지 않다면 root로 GDB 실행**
```bash
sudo gdb -p 12345
```
`admin-only`(`2`) 단계까지는 root 권한(`CAP_SYS_PTRACE`)이면 attach가 가능하다. 단, `3`(no attach)로 설정되어 있으면 root라도 재부팅 전까지는 불가능하다.

**4) 애초에 GDB로 직접 실행해서 부모-자식 관계를 만들기**
가능한 상황이라면 이미 떠 있는 프로세스에 나중에 붙는 대신, 처음부터 `gdb ./chall` 후 `run`으로 실행하면 이 제한 자체를 우회할 수 있다.

**5) CTF 문제풀이용 개인 VM/컨테이너라면 값을 0으로 낮추는 것이 가장 실용적이다.** 프로덕션 서버라면 보안상 `ptrace_scope`를 함부로 낮추지 말고, 필요한 순간에만 `sudo gdb`로 접근하는 편이 안전하다.

## 명령어/단축키
```bash
cat /proc/sys/kernel/yama/ptrace_scope
sudo sysctl -w kernel.yama.ptrace_scope=0
sudo gdb -p PID
```

## 출력 해석
`cat /proc/sys/kernel/yama/ptrace_scope`가 `0`이면 attach 제한이 없는 상태, `1`이면 부모-자식 관계만 허용(현재 이 오류의 전형적 원인), `2`는 root만 가능, `3`은 재부팅 전까지 완전 차단이다. `sudo sysctl -w kernel.yama.ptrace_scope=0` 실행 후 같은 파일을 다시 `cat`했을 때 `0`으로 바뀌어 있으면 설정이 즉시 반영된 것이며, 이후 `gdb -p PID`가 곧바로 성공해야 정상이다.

## 흔한 실수
- 오류 메시지만 보고 파일 권한(`chmod`) 문제로 오해해서 바이너리 실행 권한을 만지작거리는 것 — 이 오류는 파일 권한이 아니라 커널의 ptrace 정책 문제다.
- `ptrace_scope`를 `0`으로 낮춘 뒤 실수로 `3`(no attach)으로 잘못 설정해버려서 재부팅 전까지 root로도 attach가 안 되는 상황을 만드는 것.
- Docker 컨테이너 안에서 이 오류가 나는데, 호스트의 sysctl 값이 아니라 컨테이너 자체의 `--cap-add=SYS_PTRACE`/`--privileged` 옵션이 필요한 경우와 혼동하는 것(컨테이너 안에서는 sysctl 값보다 컨테이너 실행 시 부여된 capability가 먼저 문제인 경우가 많다).
- 매번 이 문제를 겪으면서도 `/etc/sysctl.d/`에 영구 설정을 남기지 않아, 재부팅할 때마다 같은 오류를 반복해서 만나는 것.

## 막혔을 때 다음 체크
- 값을 0으로 낮췄는데도 attach가 안 되면 seccomp 필터가 `ptrace` syscall 자체를 막고 있는지 확인 → REV-0673 seccomp가 걸린 바이너리를 만났을 때 알아채는 법
- ptrace의 근본 동작 원리(TRACEME, PEEKTEXT 등)가 궁금하면 → REV-0672 ptrace 기반 자체 디버거 구현 개념 소개
- Docker 컨테이너 안에서의 권한/ptrace 제약이 궁금하면 → REV-0674 컨테이너(Docker) 안에서 배포된 문제 바이너리 분석 시 주의점

## 미니 예제
```bash
$ gdb -p $(pgrep chall)
Attaching to process 4821
ptrace: Operation not permitted.

$ cat /proc/sys/kernel/yama/ptrace_scope
1

$ sudo sysctl -w kernel.yama.ptrace_scope=0
kernel.yama.ptrace_scope = 0

$ gdb -p $(pgrep chall)
Attaching to process 4821
Reading symbols from /home/user/chall...
0x00007f2b3a1b7d2e in read () from /lib/x86_64-linux-gnu/libc.so.6
```
값을 `0`으로 낮춘 뒤에는 같은 명령이 정상적으로 attach에 성공했다.

## 관련 글
- REV-0673 — seccomp가 걸린 바이너리를 만났을 때 알아채는 법
- REV-0672 — ptrace 기반 자체 디버거 구현 개념 소개
- REV-0674 — 컨테이너(Docker) 안에서 배포된 문제 바이너리 분석 시 주의점

## 출처/검증
- Yama LSM `ptrace_scope`의 4단계 값(`0`~`3`)과 각 단계의 의미: Linux 커널 공식 문서(Documentation/admin-guide/LSM/Yama.rst) 기준.
- `sysctl`을 통한 커널 파라미터 임시/영구 변경 절차: Linux `sysctl(8)`/`sysctl.d(5)` man page 기준 (2026-09-09 검증).
