---
id: REV-0838
title: "디버거가 프로세스에 attach가 안 될 때"
slug: "rev-0838-debugger-attach-fails"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords: ["attach 실패", "ptrace_scope", "SeDebugPrivilege", "self-debugging", "Cannot open process", "ptrace Operation not permitted"]
aliases: ["디버거 attach 안됨", "프로세스에 못 붙음", "attach 목록에 안 보임", "gdb -p 실패"]
symptom_keywords: ["Cannot open process error code 5", "ptrace Operation not permitted", "attach 대화상자에 프로세스가 안 보임", "gdb -p PID 했는데 실패함", "이미 실행 중인 프로세스에 못 붙음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
디버거가 실행 중인 프로세스에 attach하지 못하는 원인은 Windows/Linux 모두 결국 "권한 부족", "이미 다른 디버거가 그 자리를 차지함(self-debugging 포함)", "커널/컨테이너 보안 정책이 막음" 세 가지로 좁혀지며, 운영체제별로 확인 순서만 다를 뿐 진단 흐름은 동일하다.

## 언제 검색해야 하나
- x64dbg로 File → Attach를 시도했는데 "Cannot open process, error code 5"가 뜨거나 대상이 목록에 아예 안 보일 때
- GDB에서 `gdb -p PID`를 실행했는데 `ptrace: Operation not permitted.`가 뜰 때
- attach는 됐다고 나오는데 대상 프로세스가 곧바로 종료돼버릴 때
- Docker 컨테이너 안에서만 유독 attach가 실패할 때

## 핵심 개념

### 공통 원리 — 디버깅은 항상 권한 검사를 거친다
Windows는 `OpenProcess`가 충분한 접근 권한(`SeDebugPrivilege`)을 요구하고, Linux는 `ptrace(PTRACE_ATTACH, ...)`가 커널의 YAMA `ptrace_scope`/capability 검사를 거친다. 둘 다 "디버거 프로세스가 대상보다 낮은 권한이거나 커널 정책에 막히면" 실패한다.

### Windows — SeDebugPrivilege 미상승
표준 사용자 권한으로 실행한 x64dbg/IDA는 `SeDebugPrivilege`를 활성화하지 못해 `OpenProcess`가 `ERROR_ACCESS_DENIED`(5)로 실패한다. 디버거를 "관리자 권한으로 실행"하면 대부분 해결되며, 자세한 진단은 REV-0598을 참고한다.

### Windows — self-debugging(anti-attach)
대상 프로그램이 시작하자마자 자기 자신에게 `DebugActiveProcess`로 붙는 자식 프로세스를 만들면, Windows는 프로세스당 디버그 포트를 하나만 허용하므로 사람이 나중에 x64dbg로 attach하려 해도 실패한다. attach 자체가 실패하는지, attach 후 프로세스가 스스로 종료되는지(NtQueryInformationProcess 기반 탐지)를 구분해야 하며 자세한 사례는 REV-0583에서 다룬다.

### Linux — YAMA ptrace_scope
`/proc/sys/kernel/yama/ptrace_scope`가 기본값 `1`이면, 부모-자식 관계가 아닌 프로세스 간 `ptrace` attach가 커널 레벨에서 막힌다. GDB로 직접 `run`한 자식 프로세스에는 영향이 없지만, 이미 떠 있는 임의 프로세스에 `gdb -p PID`로 붙으려는 상황에서는 이 설정이 원인이 되는 경우가 흔하다. 자세한 진단은 REV-0692에서 다룬다.

### Linux — Docker/컨테이너의 seccomp·capability 제한
컨테이너는 기본적으로 `SYS_PTRACE` capability와 `ptrace` 계열 syscall을 seccomp으로 차단하므로, 호스트에서는 되던 attach/run이 컨테이너 안에서는 항상 실패한다. `--cap-add=SYS_PTRACE`와 `--security-opt seccomp=unconfined`가 필요하며 자세한 절차는 REV-0715에서 다룬다.

### Linux — ptrace는 프로세스당 하나만 허용
Windows의 디버그 포트와 마찬가지로, 리눅스도 한 프로세스는 동시에 하나의 tracer만 가질 수 있다. 이미 다른 GDB 세션이나 `strace`가 붙어 있으면 두 번째 attach는 `ptrace: Operation not permitted.` 또는 `already traced`류 메시지로 실패한다.

## 화면/코드에서 보이는 징후
```text
Cannot open process, error code 5.
```
```
$ gdb -p 1234
Attaching to process 1234
ptrace: Operation not permitted.
```
Process Explorer/`ps`에서 대상 프로세스가 시작 직후 자식 프로세스를 만드는지, 또는 이미 다른 디버거/`strace`가 그 PID를 잡고 있는지 확인하면 원인 범주를 좁힐 수 있다.

## 가장 먼저 할 것
운영체제부터 나눈다. Windows라면 디버거를 관리자 권한으로 재실행한다. Linux라면 `cat /proc/sys/kernel/yama/ptrace_scope`와 컨테이너 여부(`cat /proc/1/cgroup`)부터 확인한다.

## 단계별 절차
**Windows**
1. 디버거를 종료하고 우클릭 → "관리자 권한으로 실행"으로 재시작.
2. Process Explorer로 대상 프로세스에 자식 프로세스가 생기는지 확인 → 있으면 self-debugging 의심(REV-0583).
3. x64dbg를 먼저 실행해 "File → Open File"로 처음부터 디버거 하위에서 실행해본다(자식이 디버그 포트를 선점하기 전에 x64dbg가 먼저 차지).

**Linux**
1. `cat /proc/sys/kernel/yama/ptrace_scope` 확인 → `1` 이상이고 attach 방식이면 REV-0692 절차대로 완화.
2. 컨테이너 안이라면 `docker inspect`로 `--cap-add=SYS_PTRACE`/seccomp 옵션 여부 확인(REV-0715).
3. `ps aux`로 이미 다른 tracer가 붙어 있는지 확인, 있으면 그 프로세스를 먼저 종료.

## 명령어/단축키
```bash
cat /proc/sys/kernel/yama/ptrace_scope
docker inspect <container> | grep -i cap
gdb -p PID
```
```powershell
Start-Process x64dbg.exe -Verb RunAs
```

## 출력 해석
`error code 5`(Windows)는 권한 부족, `ptrace: Operation not permitted.`(Linux)는 YAMA/seccomp/capability 중 하나가 원인이다. attach는 성공했는데 프로세스가 바로 사라지면 권한 문제가 아니라 안티디버깅 탐지(REV-0583, REV-0841, REV-0842)를 의심해야 한다.

## 흔한 실수
- Windows 관리자 계정으로 로그인했다는 이유만으로 지금 켜진 디버거 프로세스도 자동으로 상승된 권한일 거라 착각하는 것.
- Linux에서 `ptrace_scope`만 확인하고 컨테이너 seccomp 제한은 놓치는 것(또는 그 반대).
- attach 실패와 attach 후 자살(self-terminate)을 구분하지 않고 같은 해결책만 반복 시도하는 것.
- 이미 다른 디버거/`strace`가 대상을 잡고 있다는 사실을 확인하지 않는 것.

## 막혔을 때 다음 체크
- Windows 권한 문제 상세 진단이 필요하다면 → REV-0598 관리자 권한이 없어서 디버깅이 막힐 때
- Windows self-debugging/anti-attach가 의심된다면 → REV-0583 x64dbg로 붙였는데 바로 종료(anti-attach)될 때
- Linux ptrace_scope 문제라면 → REV-0692 GDB attach가 permission denied로 실패할 때(ptrace_scope)
- Docker 컨테이너 안이라면 → REV-0715 Docker 컨테이너 안에서 gdb가 ptrace 권한 오류를 낼 때

## 미니 예제
Linux에서 이미 실행 중인 서버 프로세스에 `gdb -p 1234`로 붙으려 했더니 `ptrace: Operation not permitted.`가 떴다. `cat /proc/sys/kernel/yama/ptrace_scope`가 `1`이었고, GDB는 그 프로세스의 부모가 아니었다. `echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope`로 임시 완화한 뒤 다시 시도하니 정상적으로 attach됐다.

## 관련 글
- REV-0598 — 관리자 권한이 없어서 디버깅이 막힐 때
- REV-0583 — x64dbg로 붙였는데 바로 종료(anti-attach)될 때
- REV-0692 — GDB attach가 permission denied로 실패할 때(ptrace_scope)
- REV-0715 — Docker 컨테이너 안에서 gdb가 ptrace 권한 오류를 낼 때

## 출처/검증
- Windows `OpenProcess`/`SeDebugPrivilege`와 디버그 포트 단일 소유 정책: Microsoft Win32 API 공식 문서 기준.
- Linux YAMA LSM의 `ptrace_scope`와 `ptrace` 단일 tracer 제한: Linux 커널 문서(`Documentation/admin-guide/LSM/Yama.rst`) 및 `ptrace(2)` man page 기준(2026-09-09 검증).
- Docker의 기본 seccomp 프로파일과 `SYS_PTRACE` capability 제한: Docker 공식 문서 기준.
