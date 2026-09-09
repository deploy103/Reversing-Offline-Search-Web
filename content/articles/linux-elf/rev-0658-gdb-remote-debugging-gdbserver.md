---
id: REV-0658
title: "GDB 원격 디버깅(gdbserver) 기초"
slug: "rev-0658-gdb-remote-debugging-gdbserver"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdbserver", "target remote", "gdb 원격 디버깅", "qemu-user gdb", "크로스 디버깅"]
aliases: ["gdbserver 사용법", "gdb remote target", "원격 gdb 연결", "gdbserver attach"]
symptom_keywords: ["Remote connection closed", "Remote g packet reply is too long", "Connection timed out gdb", "도커 컨테이너 안 프로세스 디버깅하고 싶음", "다른 아키텍처 바이너리 디버깅"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`gdbserver`는 대상 머신(원격 서버, 도커 컨테이너, 다른 아키텍처 기기)에서 프로그램을 실행/제어만 하는 얇은 에이전트이고, 실제 GDB(심볼·소스·명령 해석 전부)는 로컬 머신에서 `target remote HOST:PORT`로 붙어서 마치 로컬 프로세스처럼 디버깅하는 방식 — 대상 환경에 GDB 전체를 설치할 필요 없이 원격/이기종 바이너리를 분석할 때 쓴다.

## 언제 검색해야 하나
- CTF 문제가 원격 서버에서만 재현되는데, 그 서버에 GDB를 설치할 권한이나 여유가 없을 때
- 도커 컨테이너나 별도 VM 안에서 실행 중인 프로세스를 호스트에서 붙어서 디버깅하고 싶을 때
- ARM/MIPS 등 다른 아키텍처 바이너리를 `qemu-user`로 실행하면서 동시에 디버깅하고 싶을 때
- `target remote` 시도 중 `Remote connection closed`, `Connection timed out` 같은 에러를 만났을 때

## 핵심 개념

### gdbserver와 gdb의 역할 분담
`gdbserver`는 대상 프로세스를 `ptrace`로 제어하고, 레지스터/메모리 읽기·쓰기·싱글스텝 같은 저수준 동작만 수행하는 경량 프로그램이다. 심볼 이름 해석, 소스 코드 매핑, 표현식 평가, 사용자 명령 파싱 같은 "무거운" 작업은 전혀 하지 않는다. 반대로 로컬에서 실행하는 일반 `gdb`는 이 모든 무거운 작업을 담당하고, `gdbserver`와는 **GDB Remote Serial Protocol**이라는 텍스트 기반 프로토콜로 TCP(또는 시리얼)를 통해 통신한다. 그래서 대상 머신에는 `gdbserver`(수 MB 수준의 작은 바이너리)만 있으면 되고, 무거운 심볼 파일과 소스 코드는 로컬 머신에만 있어도 된다.

### 기본 흐름
1. 대상 머신에서: `gdbserver :PORT ./chall` (새로 실행) 또는 `gdbserver :PORT --attach PID` (이미 떠 있는 프로세스에 붙기)
2. 로컬 머신에서: `gdb ./chall` 로 심볼이 있는 로컬 바이너리를 로드
3. `(gdb) target remote HOST:PORT` 로 원격 gdbserver에 연결
4. 이후는 `break`, `continue`, `finish`, `x`, `info registers` 등 로컬 디버깅과 완전히 동일한 명령을 그대로 사용한다.

### 크로스 아키텍처 디버깅 — qemu-user와 조합
로컬 머신이 x86-64인데 ARM 바이너리를 분석해야 하는 경우, `qemu-arm` 같은 사용자 모드 에뮬레이터 자체가 `-g PORT` 옵션으로 내장 gdbserver 역할을 할 수 있다:
```bash
qemu-arm -g 1234 ./chall_arm
```
그러면 로컬에서는 ARM용 GDB(또는 멀티 아키텍처를 지원하는 GDB)로 `target remote :1234`에 붙어서, x86-64 머신에 있으면서도 ARM 바이너리를 한 명령씩 실행/추적할 수 있다. 이 경우 레지스터 이름과 명령어 세트가 대상 아키텍처(ARM) 기준으로 표시된다.

### multi 모드 — 여러 프로세스를 순차적으로
```bash
gdbserver --multi :1234
```
`--multi`로 띄우면 하나의 `gdbserver`가 여러 번의 `run`/`attach` 요청을 계속 받을 수 있다. 매번 `gdbserver`를 새로 실행하지 않고 GDB 쪽에서 `target extended-remote :1234` 후 `run`으로 새 프로세스를 반복해서 띄울 때 사용한다.

## 화면/코드에서 보이는 징후
CTF 문제 설명에 "nc <host> <port>로 서비스에 접속하되, 별도 포트에서 gdbserver도 열려 있다"거나, 도커 `docker-compose.yml`에 `gdbserver :1234 ./chall`이 엔트리포인트로 들어가 있는 경우, 또는 원격 분석 환경을 요구하는 임베디드/펌웨어 문제에서 이 기법이 필요하다.

## 가장 먼저 할 것
대상 머신에서 gdbserver가 실제로 리스닝 중인지 확인한다:
```bash
# 대상 머신에서
ss -tlnp | grep 1234
```
포트가 열려 있는 것을 확인했다면 로컬에서 `gdb ./chall` 후 `target remote HOST:1234`를 시도한다.

## 단계별 절차

**1) 대상 머신: gdbserver로 새 프로세스 실행**
```bash
gdbserver :1234 ./chall
```
출력 예:
```
Process ./chall created; pid = 5821
Listening on port 1234
```
이 시점에서 프로세스는 **진입점 직전 상태로 멈춰서 로컬 GDB 연결을 기다린다.**

**2) 대상 머신: 이미 실행 중인 프로세스에 attach**
```bash
gdbserver :1234 --attach 5821
```

**3) 로컬 머신: 심볼 있는 바이너리로 gdb 실행**
```bash
gdb ./chall
```

**4) 로컬 머신: 원격 연결**
```
(gdb) target remote 192.168.1.50:1234
```
같은 머신 안 다른 컨테이너/네임스페이스라면:
```
(gdb) target remote :1234
```

**5) 라이브러리 경로가 다르면 sysroot 지정**
대상 컨테이너와 로컬의 공유 라이브러리 경로/버전이 다르면 심볼 해석이 어긋날 수 있다:
```
(gdb) set sysroot /path/to/mounted/target/rootfs
(gdb) set solib-search-path /path/to/target/libs
```

**6) 이후 일반 디버깅과 동일하게 진행**
```
(gdb) break main
(gdb) continue
(gdb) info registers
(gdb) finish
```

**7) 종료**
```
(gdb) kill
(gdb) detach
```
`detach`는 대상 프로세스를 죽이지 않고 연결만 끊는다. `kill`은 대상 프로세스 자체를 종료시킨다.

## 명령어/단축키
```bash
gdbserver :1234 ./chall                  # 새 프로세스 실행 + 대기
gdbserver :1234 --attach <PID>           # 기존 프로세스에 attach
gdbserver --multi :1234                  # 여러 세션 지원 모드
qemu-arm -g 1234 ./chall_arm             # 크로스 아키텍처 + qemu 조합
```
```
(gdb) target remote HOST:PORT
(gdb) target extended-remote HOST:PORT   # multi 모드용
(gdb) set sysroot <path>
(gdb) set solib-search-path <path>
(gdb) detach
(gdb) kill
```

## 출력 해석
```
$ gdbserver :1234 ./chall
Process ./chall created; pid = 5821
Listening on port 1234
```
```
(gdb) target remote 192.168.1.50:1234
Remote debugging using 192.168.1.50:1234
Reading symbols from /lib64/ld-linux-x86-64.so.2...
0x00007ffff7fd0100 in ?? ()
```
- `Listening on port 1234`: 연결을 기다리는 상태. 이 시점부터 프로세스는 이미 로드는 됐지만 실질적으로 멈춰 있다.
- `0x00007ffff7fd0100 in ?? ()`: 로컬 GDB가 처음 붙었을 때 위치가 아직 동적 링커(`ld-linux`) 내부일 수 있다. 정상이며, `break main` 후 `continue`하면 원하는 지점까지 진행된다.
- `??`로 표시되는 것은 해당 주소에 대한 심볼 정보가 로컬에 없다는 뜻 — 대상과 로컬의 libc/ld 버전이 다르면 계속 이렇게 나올 수 있으니 `set sysroot`로 맞춰야 한다.

## 흔한 실수
- 대상 머신 방화벽이나 도커 포트 매핑을 안 해서 `Connection timed out`이 나는 것 — 도커라면 `-p 1234:1234`로 포트를 명시적으로 열어야 한다.
- 로컬에서 심볼 없는 바이너리로 `gdb`를 실행해서 함수 이름이 하나도 안 보이는 것 — `target remote`에 연결하기 **전에** 반드시 `gdb ./chall`처럼 로컬에 있는 (가능하면 디버그 심볼 포함) 바이너리를 인자로 줘야 한다.
- 아키텍처가 다른데 로컬 GDB가 그 아키텍처를 지원하지 않아서 `Remote 'g' packet reply is too long` 같은 에러가 나는 것 — 대상 아키텍처용 GDB(예: `gdb-multiarch`, 또는 `set architecture arm`)가 필요하다.
- `gdbserver`가 이미 종료된 프로세스나 잘못된 PID에 `--attach`를 시도해서 조용히 실패하는 것 — `ps aux`로 PID를 다시 확인한다.
- 원격 세션을 `kill`로 끝내야 할 때 `detach`만 치고 프로세스가 계속 떠 있는 걸 잊어버리는 것 — 완전히 종료하려면 `kill`을 써야 한다.

## 막혔을 때 다음 체크
- 연결 후 자동으로 특정 함수 호출을 추적/기록하고 싶다면 → REV-0656 GDB Python 스크립팅 기초(gdb.Breakpoint 등)
- 리턴값을 확인하는 절차 자체가 로컬과 똑같은지 궁금하다면 → REV-0657 GDB에서 함수 반환값을 finish로 확인하는 법
- PIE 바이너리라 브레이크포인트 주소가 매번 바뀌는 문제까지 겹친다면 → REV-0194 PIE 바이너리 GDB 브레이크포인트 잡기
- 기본 GDB 명령/단축키 자체가 헷갈린다면 → REV-0284 GDB 명령어 치트시트

## 미니 예제
```bash
# 대상 컨테이너 (172.18.0.2)
$ gdbserver :1234 ./chall
Process ./chall created; pid = 42
Listening on port 1234
```
```bash
# 로컬 머신
$ gdb -q ./chall
Reading symbols from ./chall...
(gdb) target remote 172.18.0.2:1234
Remote debugging using 172.18.0.2:1234
0x00007f... in ?? ()
(gdb) break check_password
Breakpoint 1 at 0x401146
(gdb) continue
Continuing.

Breakpoint 1, check_password (input=0x7ffd... "test") at chall.c:15
15      int check_password(char *input) {
(gdb) finish
Value returned is $1 = 0
```
로컬 심볼과 소스 라인이 그대로 보이면서, 실제 실행은 원격 컨테이너 안에서 이뤄지고 있다는 것이 핵심이다.

## 관련 글
- REV-0656 — GDB Python 스크립팅 기초(gdb.Breakpoint 등)
- REV-0657 — GDB에서 함수 반환값을 finish로 확인하는 법
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기
- REV-0284 — GDB 명령어 치트시트
- REV-0283 — GDB 설치와 기본 설정

## 출처/검증
- `gdbserver` 명령 옵션(`--attach`, `--multi`)과 `target remote`/`target extended-remote` 동작: GDB 공식 매뉴얼 "Debugging Remote Programs" 챕터 및 `gdbserver(1)` man page 기준.
- `qemu-arm -g PORT` 사용자 모드 에뮬레이션 gdbserver 연동: QEMU 공식 문서(User Mode Emulation) 기준 (2026-09-08 검증).
