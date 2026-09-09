---
id: REV-0847
title: "원격 디버깅(gdbserver) 연결이 안 될 때"
slug: "rev-0847-gdbserver-remote-connection-fail"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB]
keywords: ["gdbserver 연결 실패", "target remote 안됨", "Connection timed out gdb", "Connection refused gdb", "Remote connection closed"]
aliases: ["gdbserver 접속 안됨", "target remote 실패", "gdb 원격 디버깅 연결 오류", "gdbserver 포트 안열림"]
symptom_keywords: ["Connection timed out", "Connection refused", "Remote connection closed", "target remote 명령이 멈춘다", "gdbserver는 떠 있는데 gdb가 못 붙는다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`target remote HOST:PORT`가 실패하는 원인은 거의 항상 "네트워크 경로가 막혀 있음", "포트/주소를 잘못 지정함", "gdbserver가 이미 죽어 있거나 다른 세션이 점유 중임", "GDB와 gdbserver 버전/아키텍처가 안 맞음" 네 가지 중 하나이며, 에러 메시지 문구만 봐도 어느 쪽인지 대부분 구분된다.

## 언제 검색해야 하나
- `(gdb) target remote HOST:PORT`를 쳤는데 몇 초~몇십 초 그대로 멈춰 있다가 `Connection timed out`이 뜰 때
- 즉시 `Connection refused`가 뜰 때
- 연결은 됐다가 바로 `Remote connection closed`로 끊길 때
- 도커 컨테이너나 원격 서버 안의 `gdbserver`에 붙으려는 상황에서 위 증상 중 하나라도 겪을 때

## 핵심 개념
`gdbserver` 연결은 TCP 3-way handshake(네트워크 경로) → GDB Remote Serial Protocol 핸드셰이크(프로토콜 호환성) 두 단계를 순서대로 통과해야 완성된다. 두 단계 중 어디서 실패하느냐에 따라 에러 메시지가 다르게 나오므로, 메시지를 원인 분류표처럼 활용할 수 있다.

- **`Connection timed out`**: TCP 패킷 자체가 목적지에 도달하지 못하고 있다는 뜻이다. 방화벽이 SYN 패킷을 그냥 드롭(응답 없이 버림)하고 있거나, 라우팅이 안 되는 네트워크(다른 서브넷, 도커 브릿지 네트워크 미개방)이거나, 대상 머신에서 `gdbserver`가 아예 그 포트로 리스닝하고 있지 않은 경우다.
- **`Connection refused`**: TCP 패킷은 도달했지만 그 포트에서 리스닝하는 프로세스가 없다는 뜻이다. `gdbserver`가 실행되지 않았거나, 다른 포트 번호로 떴거나, 이미 죽어서 포트가 닫힌 경우다.
- **`Remote connection closed`**: TCP 연결과 초기 핸드셰이크까지는 됐지만 이후 프로토콜 교환 중 상대가 연결을 끊은 것. `gdbserver` 프로세스가 중간에 죽었거나(대상 프로그램 자체가 크래시), 이미 다른 GDB 세션이 붙어 있어서 두 번째 연결을 거부한 경우다.
- **아키텍처/버전 불일치**: 연결 자체는 되는데 `Remote 'g' packet reply is too long` 같은 프로토콜 레벨 에러가 나거나 레지스터 값이 전부 깨져 보이는 경우로, GDB가 대상 아키텍처를 모르거나 GDB와 gdbserver 버전 차이가 너무 큰 것이다.

## 화면/코드에서 보이는 징후
```
(gdb) target remote 192.168.1.50:1234
192.168.1.50:1234: Connection timed out.
```
```
(gdb) target remote 192.168.1.50:1234
192.168.1.50:1234: Connection refused.
```
```
(gdb) target remote 192.168.1.50:1234
Remote debugging using 192.168.1.50:1234
Remote connection closed
```

## 가장 먼저 할 것
대상 머신(원격/컨테이너)에 직접 접속해 `gdbserver`가 실제로 그 포트에 살아서 리스닝 중인지부터 확인한다.
```bash
# 대상 머신에서
ps aux | grep gdbserver
ss -tlnp | grep 1234
```
프로세스가 없거나 포트가 안 보이면 네트워크 문제가 아니라 "애초에 떠 있지 않은 것"이므로 먼저 `gdbserver :1234 ./chall`부터 다시 실행한다.

## 단계별 절차

**1) 대상에서 리스닝 상태 확인**
```bash
ss -tlnp | grep 1234
# 또는
netstat -tlnp | grep 1234
```
`LISTEN` 상태로 안 보이면 gdbserver를 아직 안 띄웠거나 다른 포트를 썼다는 뜻이다.

**2) 로컬에서 대상까지 경로가 열려 있는지 확인**
```bash
# 로컬 머신에서
nc -zv 192.168.1.50 1234
telnet 192.168.1.50 1234
```
`nc: connect timed out` → 방화벽/라우팅 차단. `Connection refused` → 포트 자체가 안 열림(1번으로 돌아가서 확인).

**3) 도커/컨테이너 환경이면 포트 매핑 확인**
```bash
docker ps
# PORTS 컬럼에 0.0.0.0:1234->1234/tcp 형태로 노출돼 있는지 확인
```
`-p 1234:1234` 없이 컨테이너를 띄웠다면 호스트에서 절대 접근할 수 없다. 컨테이너를 재시작하며 포트를 명시적으로 열어야 한다.

**4) 로컬 방화벽 확인**
```bash
# Linux 로컬 머신
sudo iptables -L -n | grep 1234
# Windows 로컬 머신에서 원격에 붙는 경우
netsh advfirewall firewall show rule name=all | findstr 1234
```

**5) 이미 다른 GDB 세션이 붙어 있는지 확인**
`gdbserver`는 기본적으로 한 번에 하나의 GDB 연결만 받는다. 이전에 비정상 종료한 GDB 세션이 소켓을 붙잡고 있을 수 있으니, 대상 머신에서 `gdbserver` 프로세스를 완전히 죽이고 새로 띄운다.
```bash
pkill gdbserver
gdbserver :1234 ./chall
```

**6) 아키텍처/버전 문제 확인**
```bash
gdb --version
gdbserver --version
file ./chall   # 대상 아키텍처 확인
```
로컬 GDB가 대상 아키텍처를 모른다면(예: 로컬은 x86-64 전용 GDB인데 대상은 ARM) `gdb-multiarch`를 설치하거나 `(gdb) set architecture <arch>`로 명시한다.

## 명령어/단축키
```bash
ss -tlnp | grep <PORT>            # 대상: 리스닝 확인
nc -zv HOST PORT                  # 로컬: 포트 도달 여부 확인
docker ps                         # 컨테이너 포트 매핑 확인
pkill gdbserver                   # 좀비 gdbserver 정리
gdb-multiarch ./chall             # 크로스 아키텍처 GDB
```
```
(gdb) target remote HOST:PORT
(gdb) set architecture ARCH
(gdb) show remote-timeout
```

## 출력 해석
- `Connection timed out` → 응답 자체가 없음. 네트워크 경로(방화벽/라우팅/포트 매핑) 문제. 대상에 리스닝 프로세스가 있는지부터 확인.
- `Connection refused` → 상대가 "그 포트엔 아무도 없다"고 즉시 답한 것. gdbserver를 안 띄웠거나 죽었을 가능성이 가장 크다.
- `Remote connection closed` → 초반 연결은 됐지만 곧바로 끊김. gdbserver가 이미 다른 GDB에 물려 있거나, 대상 프로그램이 실행 중 죽어서 gdbserver 자체가 종료된 경우다. 대상 머신 콘솔에 `gdbserver`가 남긴 마지막 로그를 확인한다.
- `Remote 'g' packet reply is too long` → 레지스터 셋 크기가 다르다는 뜻으로, 아키텍처 불일치가 원인이다.

## 흔한 실수
- IP 대신 컨테이너 내부 이름(`localhost`)을 호스트에서 그대로 써서 접속하는 것 — 컨테이너 네트워크 네임스페이스가 다르면 호스트의 `localhost`는 컨테이너를 가리키지 않는다.
- 방화벽 규칙을 원격 서버에만 확인하고 자기 로컬 머신의 아웃바운드 방화벽/보안 프로그램은 확인하지 않는 것.
- `gdbserver`가 크래시로 죽었는데 GDB 쪽 에러 메시지만 보고 "연결 설정이 잘못됐다"고 오판하는 것 — 대상 머신 터미널에 남은 gdbserver 자체 로그를 먼저 봐야 한다.
- 이전 세션의 `gdbserver`가 좀비로 남아 포트를 계속 붙잡고 있는데 모르고 새 `gdbserver`를 다른 포트 없이 재실행해서 계속 실패하는 것.

## 막혔을 때 다음 체크
- 연결 자체는 됐고 이제 실제 디버깅 흐름을 알고 싶다면 → REV-0658 GDB 원격 디버깅(gdbserver) 기초.
- 로컬 프로세스인데도 `attach`가 permission denied로 막힌다면 → REV-0692 GDB attach가 permission denied로 실패할 때(ptrace_scope).
- PIE 바이너리라 원격에서도 브레이크포인트 주소가 안 맞는다면 → REV-0194 PIE 바이너리 GDB 브레이크포인트 잡기.

## 미니 예제
```bash
# 로컬에서 첫 시도
$ gdb -q ./chall
(gdb) target remote 172.18.0.2:1234
172.18.0.2:1234: Connection timed out.
```
```bash
# 대상 컨테이너 확인
$ docker ps
CONTAINER ID   PORTS
a1b2c3d4e5f6   1234/tcp
```
`PORTS`에 `0.0.0.0:1234->1234/tcp`가 아니라 `1234/tcp`만 있다는 것은 호스트로 노출되지 않았다는 뜻이다. 컨테이너를 `-p 1234:1234`로 재시작한 뒤 다시 연결하니 정상적으로 붙었다.
```
(gdb) target remote 127.0.0.1:1234
Remote debugging using 127.0.0.1:1234
0x00007f... in ?? ()
```

## 관련 글
- REV-0658 — GDB 원격 디버깅(gdbserver) 기초
- REV-0692 — GDB attach가 permission denied로 실패할 때(ptrace_scope)
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기

## 출처/검증
- `target remote`/`gdbserver` 연결 실패 메시지(`Connection timed out`, `Connection refused`, `Remote connection closed`)의 의미: GDB 공식 매뉴얼 "Debugging Remote Programs" 챕터 및 `gdbserver(1)` man page 기준.
- 도커 포트 매핑(`-p`)과 컨테이너 네트워크 네임스페이스 동작: Docker 공식 문서(Networking overview) 기준 (2026-09-09 검증).
