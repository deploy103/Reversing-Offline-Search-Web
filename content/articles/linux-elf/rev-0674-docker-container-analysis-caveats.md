---
id: REV-0674
title: "컨테이너(Docker) 안에서 배포된 문제 바이너리 분석 시 주의점"
slug: "rev-0674-docker-container-analysis-caveats"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, strace, readelf]
keywords: ["docker pwn 문제", "컨테이너 리버싱", "Dockerfile 분석", "docker cp", "gdbserver 컨테이너", "libc 버전 불일치"]
aliases: ["docker로 배포된 pwn 문제 분석법", "컨테이너 안 바이너리 로컬 분석", "docker exploit 환경 재현"]
symptom_keywords: ["로컬에서 실행하면 세그폴트가 나는데 서버에서는 됨", "컨테이너 안에 gdb가 없음", "libc 버전이 로컬과 달라서 익스플로잇이 안 먹힘", "Dockerfile만 주어지고 바이너리 실행 환경을 재현해야 함"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
CTF pwn 문제가 Docker 컨테이너로 배포될 때는 로컬 배포판과 컨테이너 안의 배포판/libc 버전이 다를 수 있고, 컨테이너 안에는 GDB 같은 분석 도구가 아예 없는 경우가 많으며, non-root로 실행되어 권한/코어덤프 설정이 로컬과 다르므로, `Dockerfile`을 먼저 읽고 컨테이너 안의 정확한 libc/바이너리를 로컬로 꺼내와 같은 환경을 재현하는 것이 분석의 첫걸음이다.

## 언제 검색해야 하나
- CTF 문제가 `Dockerfile`, `docker-compose.yml`과 함께 배포되어 있고 실행 파일만 로컬에서 돌려보면 서버와 다르게 동작할 때
- 로컬 Ubuntu에서 익스플로잇이 세그폴트가 나는데, 원격 서버(컨테이너)에서는 정상 동작할 것으로 예상될 때
- 컨테이너 이미지 안에 `gdb`, `strace`가 설치되어 있지 않아 직접 그 안에서 디버깅할 수 없을 때
- `docker exec`로 들어가봤는데 non-root 사용자라서 `ptrace`, core dump 관련 동작이 로컬과 다르게 막혀 있을 때
- Alpine 기반 이미지라서 libc가 `glibc`가 아니라 `musl`이라는 걸 뒤늦게 알았을 때

## 핵심 개념

### Dockerfile을 가장 먼저 읽어야 하는 이유
Dockerfile의 `FROM` 줄이 배포판과 libc 계열을 결정한다. `FROM ubuntu:20.04`라면 glibc 2.31 계열, `FROM alpine:3.18`이라면 musl libc(REV-0647 참고)다. `RUN apt-get install` 또는 `apk add`로 무엇이 추가로 설치됐는지, `COPY`로 어떤 바이너리/라이브러리가 이미지에 들어갔는지, `USER` 지시어로 어떤 권한(root 여부)으로 최종 프로세스가 도는지까지 Dockerfile 한 파일에 분석에 필요한 정보 대부분이 들어있다.

### 로컬 환경과의 libc/커널 차이
로컬 데스크톱의 `glibc` 버전과 챌린지 컨테이너 안의 `glibc` 버전이 다르면, 힙 관련 익스플로잇(tcache 구조, safe-linking 등, REV-0654/0655 참고)이 로컬에서는 실패하거나 다르게 동작할 수 있다(REV-0711 서버-로컬 glibc 불일치 참고). 반드시 컨테이너 안에 실제로 들어있는 `libc.so.6`과 동적 링커(`ld-linux-x86-64.so.2`)를 꺼내와 로컬 익스플로잇도 그 버전으로 강제 실행해야 한다.
```bash
docker cp <container_id>:/lib/x86_64-linux-gnu/libc.so.6 ./libc.so.6
docker cp <container_id>:/lib64/ld-linux-x86-64.so.2 ./ld.so
patchelf --set-interpreter ./ld.so --replace-needed libc.so.6 ./libc.so.6 ./chall
```
`patchelf`로 인터프리터와 필요한 라이브러리를 강제 지정하면, 로컬 시스템의 libc 대신 컨테이너와 동일한 libc로 로컬에서 실행할 수 있다.

### 컨테이너 안에 분석 도구가 없다
문제풀이용 컨테이너 이미지는 보통 실행에 필요한 최소한만 담아 용량을 줄이므로 `gdb`, `strace`, `vim` 같은 도구가 없는 경우가 흔하다. 이 경우 선택지는 두 가지다.
1. 컨테이너 밖(로컬)에서 같은 libc로 재현해서 분석 — 위의 `patchelf` 방식.
2. 컨테이너 안에 `gdbserver`(REV-0658 참고)만 최소로 넣어 원격 디버깅 — 이미지를 직접 만들 수 있는 로컬 재현 환경(같은 `Dockerfile`로 `docker build`)이라면 `RUN apt-get install -y gdbserver`를 임시로 추가한 이미지를 따로 빌드해서 그 안에서 `gdbserver :1234 ./chall`을 실행하고, 로컬 GDB에서 `target remote :1234`로 붙는다.

### non-root 실행이 만드는 차이
챌린지 컨테이너는 보안상 non-root 사용자로 프로세스를 띄우는 경우가 많다(`USER nobody` 등). 이 경우:
- `PTRACE_ATTACH` 권한이 로컬 root 환경과 다르게 동작할 수 있다.
- core dump 생성 여부/경로가 `ulimit -c`, `/proc/sys/kernel/core_pattern` 설정에 따라 컨테이너 안에서는 아예 꺼져 있는 경우가 많다.
- 파일 시스템 권한(`/flag` 읽기 권한 등)이 익스플로잇 성공 여부에 직접 영향을 준다 — 로컬에서 root로 테스트하면 성공하는데 실제 서버(non-root)에서는 권한 때문에 실패하는 상황이 생길 수 있다.

### 네트워크로 배포되는 경우의 소켓 vs 로컬 파이프 차이
`docker-compose.yml`에 `ports: - "1337:1337"` 같은 설정이 있으면 실제 채점은 TCP 소켓으로 stdin/stdout을 리다이렉트하는 방식(흔히 `socat`이나 `xinetd` 스타일)으로 이뤄진다. 로컬에서 파일을 직접 실행(`./chall`)하는 것과 `nc`/`pwntools`의 `remote()`로 접속하는 것은 표준 입출력이 파이프냐 소켓이냐의 차이가 있어, 버퍼링 동작(`stdout`이 터미널이 아니면 완전 버퍼링되는 것 등)이 달라질 수 있다.

## 화면/코드에서 보이는 징후
- `Dockerfile`에 `FROM alpine`, `FROM ubuntu:20.04` 같은 베이스 이미지 지정
- `docker-compose.yml`에 포트 매핑과 `command: ["socat", ...]` 또는 `xinetd` 관련 설정
- 로컬 실행은 세그폴트인데 원격 접속(`nc host port`)은 정상 동작
- 컨테이너 안에서 `which gdb`, `which strace`가 `command not found`

## 가장 먼저 할 것
`Dockerfile`을 열어 베이스 이미지, 설치 패키지, 실행 사용자(`USER`), 진입점(`ENTRYPOINT`/`CMD`)을 먼저 확인한다. 그다음 `docker cp` 또는 `docker build` + 임시 컨테이너 실행으로 실제 사용되는 `libc.so.6`/동적 링커를 로컬로 확보한다.

## 단계별 절차
1. `Dockerfile`, `docker-compose.yml`을 정독하며 베이스 이미지, 설치 패키지, 실행 사용자, 포트를 파악
2. 로컬에서 같은 이미지를 빌드하거나 pull: `docker build -t chall .` 또는 `docker run -it <image> /bin/sh`로 진입해서 실제 배포 환경 확인
3. 컨테이너 실행 중인 상태에서 `docker cp`로 실제 바이너리와 libc, 동적 링커를 로컬로 추출
   ```bash
   docker cp <container_id>:/challenge/chall ./chall
   docker cp <container_id>:/lib/x86_64-linux-gnu/libc.so.6 ./libc.so.6
   ```
4. `patchelf`로 로컬 환경에서도 정확히 같은 libc/링커로 실행되게 강제
5. 분석 도구가 컨테이너 안에 없다면, 로컬로 꺼내온 사본에 로컬 GDB/Ghidra를 사용하거나, 분석용 도구를 추가한 임시 이미지를 별도로 빌드해서 `gdbserver`로 원격 디버깅
6. 최종 익스플로잇은 로컬 파일 실행이 아니라 실제 배포 방식(TCP 소켓 등)과 동일한 경로로 검증 — `pwntools`의 `process()`가 아니라 `remote()`로 마지막 테스트를 반드시 해본다

## 명령어/단축키
```bash
docker ps
docker cp <container_id>:<path_in_container> <local_path>
docker exec -it <container_id> /bin/sh
docker build -t chall .
docker run --rm -it -p 1337:1337 chall
patchelf --set-interpreter ./ld.so ./chall
patchelf --replace-needed libc.so.6 ./libc.so.6 ./chall
```

## 출력 해석
`docker cp` 실행 후 로컬에 생긴 `libc.so.6`을 `file libc.so.6`로 확인하면 실제 컨테이너 안에서 쓰이는 아키텍처와 빌드 정보(예: `GNU/Linux 3.2.0`)가 나오고, `strings libc.so.6 | grep "GNU C Library"`로 정확한 버전 문자열을 뽑아 로컬 libc와 대조할 수 있다. 버전 문자열이 로컬 시스템 libc와 다르면, 그 차이가 바로 "로컬에서는 실패, 서버에서는 성공(또는 반대)"의 원인이었을 가능성이 크다.

## 흔한 실수
- 로컬 데스크톱의 `glibc`로만 익스플로잇을 개발하고 검증도 없이 원격 서버에 그대로 제출하는 것 — 힙 오프셋, 함수 오프셋이 버전마다 달라 실패할 수 있다.
- `docker cp`로 바이너리만 꺼내고 동적 링커/libc는 그대로 로컬 시스템 것을 쓰는 것 — `ldd`가 로컬 libc를 가리키면 `patchelf`로 강제 지정해야 한다.
- 컨테이너가 non-root로 도는데 로컬에서는 root로 테스트해서 권한 관련 실패를 못 잡아내는 것.
- Alpine 기반인 걸 모르고 glibc 전제로 힙 구조나 함수 시그니처를 분석하는 것 — musl은 tcache 등 glibc 힙 구조를 아예 안 쓴다(REV-0647 참고).
- `process()`로 로컬 테스트만 반복하고, 실제 배포 방식인 소켓 연결(`remote()`)로는 한 번도 테스트하지 않은 채 제출하는 것.

## 막혔을 때 다음 체크
- 컨테이너 안 바이너리에 seccomp 필터까지 걸려 있다면 → REV-0673 seccomp가 걸린 바이너리를 만났을 때 알아채는 법
- musl과 glibc 차이가 구체적으로 궁금하면 → REV-0647 musl libc와 glibc 차이가 리버싱에 미치는 영향
- 서버와 로컬의 glibc 버전이 달라 생기는 문제를 더 자세히 보려면 → REV-0711 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때
- 컨테이너 안에서 원격 디버깅이 필요하면 → REV-0658 GDB 원격 디버깅(gdbserver) 기초
- `LD_LIBRARY_PATH`로 특정 libc를 강제 지정하는 방법이 헷갈리면 → REV-0651 LD_LIBRARY_PATH와 라이브러리 탐색 순서

## 미니 예제
```bash
$ cat Dockerfile
FROM ubuntu:20.04
RUN apt-get update && apt-get install -y socat
COPY chall /challenge/chall
COPY libc-2.31.so /lib/x86_64-linux-gnu/libc.so.6
USER nobody
CMD ["socat", "TCP-LISTEN:1337,reuseaddr,fork", "EXEC:/challenge/chall"]

$ docker run --rm -d -p 1337:1337 --name chall_test chall
$ docker cp chall_test:/lib/x86_64-linux-gnu/libc.so.6 ./libc.so.6
$ patchelf --replace-needed libc.so.6 ./libc.so.6 ./chall
$ python3 -c "from pwn import *; io = process('./chall'); io.interactive()"
```
Dockerfile만 봐도 `USER nobody`(non-root), `libc-2.31.so`가 강제 교체됨, `socat` 기반 소켓 서비스라는 사실을 전부 미리 알 수 있었고, 이를 바탕으로 로컬 재현 환경을 정확히 맞췄다.

## 관련 글
- REV-0673 — seccomp가 걸린 바이너리를 만났을 때 알아채는 법
- REV-0647 — musl libc와 glibc 차이가 리버싱에 미치는 영향
- REV-0658 — GDB 원격 디버깅(gdbserver) 기초
- REV-0651 — LD_LIBRARY_PATH와 라이브러리 탐색 순서

## 출처/검증
- Docker 컨테이너의 이미지 레이어, `docker cp`, `USER`/`ENTRYPOINT`/`CMD` Dockerfile 지시어 동작: Docker 공식 문서(docs.docker.com, Dockerfile reference) 기준.
- `patchelf`로 ELF의 `PT_INTERP`(인터프리터 경로) 및 `DT_NEEDED` 항목을 재작성하는 방식: patchelf 공식 저장소(NixOS/patchelf) 문서 기준.
- CTF pwn 문제에서 컨테이너/소켓 기반 배포 시 libc 버전 일치가 익스플로잇 성공에 미치는 영향: 일반적인 CTF pwn 방법론 및 커뮤니티 라이트업에서 반복 확인되는 관행 (2026-09-09 검증).
