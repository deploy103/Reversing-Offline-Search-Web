---
id: REV-0715
title: "Docker 컨테이너 안에서 gdb가 ptrace 권한 오류를 낼 때"
slug: "rev-0715-docker-gdb-ptrace-permission-denied"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Docker, ptrace]
keywords: ["ptrace Operation not permitted", "docker gdb 권한 오류", "SYS_PTRACE", "seccomp unconfined", "ptrace_scope"]
aliases: ["docker gdb attach 안 됨", "컨테이너에서 gdb 실행 오류", "ptrace: Operation not permitted", "docker cap-add SYS_PTRACE"]
symptom_keywords: ["docker 컨테이너 안에서 gdb로 run 하면 ptrace Operation not permitted가 뜸", "docker attach로 붙으려는데 권한 오류가 남", "컨테이너 안인데 호스트에서는 gdb가 잘 됨", "warning could not trace the inferior process 메시지가 뜸"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Docker 컨테이너는 기본적으로 `ptrace` 시스템 콜을 seccomp 프로파일로 차단하고 `SYS_PTRACE` capability도 빼놓기 때문에, 컨테이너 안에서 GDB로 프로세스를 실행/attach하려 하면 호스트에서는 잘 되던 것과 달리 `ptrace: Operation not permitted` 오류가 나는데, 컨테이너를 실행할 때 `--cap-add=SYS_PTRACE`와 `--security-opt seccomp=unconfined`(또는 그에 준하는 프로파일)를 추가해야 해결된다.

## 언제 검색해야 하나
- 호스트에서는 `gdb ./chall` + `run`이 잘 되는데, 같은 바이너리를 Docker 컨테이너 안에서 실행하면 GDB가 `ptrace: Operation not permitted`를 낼 때
- 컨테이너 안에서 이미 실행 중인 프로세스에 `gdb -p PID`로 attach하려는데 권한 오류가 날 때
- CI 파이프라인이나 CTF 문제 배포용 Docker 이미지 안에서 디버깅을 시도하는데 GDB가 아예 실행을 못 시킬 때
- `strace`도 같은 컨테이너 안에서 비슷한 권한 오류를 낼 때

## 핵심 개념

### Docker 기본 보안 정책이 ptrace를 막는 이유
`ptrace` 시스템 콜은 다른 프로세스의 메모리를 읽고 쓰고 실행을 제어할 수 있게 해주는 강력한 기능이라, 컨테이너 격리를 우회해 호스트나 다른 컨테이너를 공격하는 데 악용될 소지가 있다. 그래서 Docker는 기본 seccomp 프로파일에서 `ptrace` 계열 시스템 콜을 차단하고, 기본 capability 목록에서도 `SYS_PTRACE`를 빼놓는다. GDB, `strace`, `ltrace` 모두 내부적으로 `ptrace`를 사용하므로 이 기본 정책 아래에서는 아예 동작하지 못한다.

### 해결 — capability와 seccomp 프로파일 완화
컨테이너를 실행할 때 다음 두 가지를 추가하면 컨테이너 안에서도 GDB가 정상 동작한다.
- `--cap-add=SYS_PTRACE`: `ptrace` 시스템 콜을 실행할 수 있는 Linux capability를 부여한다.
- `--security-opt seccomp=unconfined`: 기본 seccomp 필터를 완전히 해제한다(더 좁게 제한하고 싶다면 `ptrace`를 허용하는 커스텀 seccomp 프로파일을 만들어 지정할 수도 있다).

두 옵션을 함께 줘야 한다 — capability만 주고 seccomp이 그대로면 여전히 시스템 콜 자체가 필터에 걸려 막힌다. `--privileged`로 컨테이너를 완전 권한으로 띄우면 이 문제가 한 번에 사라지지만, 이건 훨씬 더 넓은 권한을 부여하는 것이라 신뢰할 수 있는 로컬 실습 환경이 아니면 권장되지 않는다.

### 컨테이너 안이 아니라 호스트의 YAMA ptrace_scope가 원인인 경우도 있다
컨테이너 옵션을 다 맞게 줬는데도 여전히 안 된다면, 호스트 커널의 YAMA 모듈이 "부모-자식 관계가 아닌 프로세스 간의 ptrace"를 막고 있을 수 있다(`/proc/sys/kernel/yama/ptrace_scope` 기본값 `1`). GDB로 직접 `run`(자신이 자식으로 실행)한 경우는 보통 문제가 없지만, 이미 떠 있는 다른 프로세스에 `gdb -p PID`로 attach하려는 경우는 이 설정에 영향을 받을 수 있다.

## 화면/코드에서 보이는 징후
```
$ gdb ./chall
(gdb) run
Starting program: /app/chall
ptrace: Operation not permitted.
```
또는
```
$ gdb -p 1234
Attaching to process 1234
ptrace: Operation not permitted.
```

## 가장 먼저 할 것
컨테이너를 어떤 `docker run` 명령으로 띄웠는지 확인하고, `--cap-add=SYS_PTRACE`와 `--security-opt seccomp=unconfined`가 빠져 있는지부터 확인한다.

## 단계별 절차
1. 현재 컨테이너를 종료하고, 다음 옵션을 추가해 다시 실행
   ```bash
   docker run --cap-add=SYS_PTRACE --security-opt seccomp=unconfined -it <이미지> bash
   ```
2. 컨테이너 안에서 다시 `gdb ./chall` + `run`으로 재시도
3. 그래도 안 되면 호스트에서 `cat /proc/sys/kernel/yama/ptrace_scope` 확인
4. 값이 `1` 이상이고 attach 방식이 문제라면(호스트 관리자 권한이 있는 실습 환경 한정) 임시로 `echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope`로 완화 후 재시도, 작업 후 원복
5. docker-compose를 쓴다면 서비스 정의에 `cap_add: [SYS_PTRACE]`와 `security_opt: ["seccomp:unconfined"]`를 추가
6. 그래도 안 되면 최후 수단으로 `--privileged`(신뢰 가능한 로컬 실습 환경에서만) 테스트해 문제 범위를 좁힌다

## 명령어/단축키
```bash
docker run --cap-add=SYS_PTRACE --security-opt seccomp=unconfined -it <이미지> bash
cat /proc/sys/kernel/yama/ptrace_scope
echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope
```
docker-compose.yml:
```yaml
services:
  chall:
    cap_add:
      - SYS_PTRACE
    security_opt:
      - "seccomp:unconfined"
```

## 출력 해석
`ptrace: Operation not permitted.`는 GDB가 `ptrace(PTRACE_TRACEME 또는 PTRACE_ATTACH, ...)` 호출 자체가 커널/seccomp에 의해 거부됐다는 뜻이다. `--cap-add=SYS_PTRACE` + `--security-opt seccomp=unconfined`를 준 컨테이너에서 같은 명령이 정상적으로 `Starting program:` 이후 실행을 이어간다면 컨테이너 정책이 원인이었음이 확인된 것이다.

## 흔한 실수
- `--cap-add=SYS_PTRACE`만 주고 `--security-opt seccomp=unconfined`는 빼먹어서 여전히 막히는 것 — 두 조건 모두 필요하다.
- 이미 떠 있는 컨테이너에 `docker exec`로 들어가서 옵션을 나중에 추가하려 하는 것 — capability/seccomp 옵션은 컨테이너를 처음 `run`할 때만 지정할 수 있고, 이미 실행 중인 컨테이너에는 나중에 추가할 수 없다(컨테이너를 다시 만들어야 한다).
- 문제 원인을 무조건 컨테이너 설정으로 단정하고, 실제로는 호스트의 YAMA `ptrace_scope`가 원인인 경우를 놓치는 것.
- `--privileged`를 습관적으로 아무 환경에나 쓰는 것 — 신뢰할 수 없는 이미지/공용 서버에서는 보안 위험이 크다.

## 막혔을 때 다음 체크
- 컨테이너 실행 옵션은 맞는데 GDB가 파일 경로 문제로 다른 오류를 낸다면 → REV-0688 GDB에서 No such file or directory 오류가 뜰 때.
- pwndbg 자체가 컨테이너 안에서 명령을 못 알아듣는 것이라면 → REV-0690 Pwndbg가 설치는 됐는데 명령어가 안 먹을 때.
- 원격 서버/다른 머신에서 GDB로 붙어야 하는 상황이라면 attach 대신 원격 디버깅도 고려 → REV-0658 GDB 원격 디버깅(gdbserver) 기초.

## 미니 예제
```bash
$ docker run -it alpine-gdb-test bash
# (컨테이너 안)
$ gdb ./chall
(gdb) run
ptrace: Operation not permitted.

# 컨테이너를 다시 띄움
$ docker run --cap-add=SYS_PTRACE --security-opt seccomp=unconfined -it alpine-gdb-test bash
# (컨테이너 안)
$ gdb ./chall
(gdb) run
Starting program: /chall
Hello from inside the container!
```
동일한 이미지, 동일한 GDB 명령인데 컨테이너 실행 옵션만 바꿔서 `ptrace` 문제가 해결된 것을 볼 수 있다.

## 관련 글
- REV-0688 — GDB에서 No such file or directory 오류가 뜰 때
- REV-0690 — Pwndbg가 설치는 됐는데 명령어가 안 먹을 때
- REV-0658 — GDB 원격 디버깅(gdbserver) 기초
- REV-0702 — Permission denied로 바이너리 실행이 안 될 때

## 출처/검증
- Docker의 기본 seccomp 프로파일이 `ptrace` 계열 시스템 콜을 차단하는 동작과 `--security-opt seccomp=unconfined` 옵션: Docker 공식 문서("Seccomp security profiles for Docker") 기준.
- `--cap-add=SYS_PTRACE`로 ptrace capability를 부여하는 방법: Docker 공식 문서("Runtime privilege and Linux capabilities") 기준.
- YAMA LSM의 `ptrace_scope` 설정과 non-parent ptrace 제한: Linux 커널 문서(`Documentation/admin-guide/LSM/Yama.rst`) 기준 (2026-09-09 검증).
