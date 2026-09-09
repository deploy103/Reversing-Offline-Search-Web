---
id: REV-0322
title: "문제에 주어진 Dockerfile에서 실행 환경 힌트 읽기"
slug: "rev-0322-dockerfile-environment-hints"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [file, checksec, "Docker"]
keywords: ["Dockerfile 리버싱 힌트", "실행 환경 확인", "glibc 버전 확인", "베이스 이미지 확인", "CTF Dockerfile 읽는 법"]
aliases: ["Dockerfile 어떻게 읽나", "docker-compose 힌트", "채점 서버 환경 확인", "Dockerfile로 libc 버전 알기"]
symptom_keywords: ["로컬에서는 되는데 서버에서 안 됨", "libc 버전을 모르겠음", "flag 파일 위치를 모르겠음", "Dockerfile이 첨부됐는데 뭘 봐야 할지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
CTF 문제에 `Dockerfile`이나 `docker-compose.yml`이 함께 첨부되어 있다면 이는 단순한 배포 설정 파일이 아니라 "이 문제가 실제로 어떤 OS/glibc/권한/실행 인자로 돌아가는지"를 알려주는 명세서이므로, 코드를 열기 전에 먼저 이 파일부터 읽으면 분석 방향을 크게 절약할 수 있다.

## 언제 검색해야 하나
- 첨부파일에 `Dockerfile`, `docker-compose.yml`, `run.sh` 같은 파일이 포함되어 있을 때
- 로컬에서 바이너리를 실행한 결과와 원격 서버(`nc`)에서 받는 결과가 미묘하게 다를 때
- 문제에서 flag 파일 경로나 실행 인자를 어떻게 넘겨야 하는지 감이 안 잡힐 때
- 리버싱한 로직은 맞는 것 같은데 검증에 필요한 glibc/라이브러리 버전을 모를 때

## 핵심 개념

### Dockerfile은 실행 환경의 설계도다
`Dockerfile`은 채점 서버가 실제로 어떤 이미지를 기반으로, 어떤 파일을 어디에 배치하고, 어떤 명령으로 바이너리를 실행하는지를 그대로 기술한다. 이 정보는 로컬에서 직접 실행하며 추측하는 것보다 훨씬 정확하고 빠르다.

### 확인해야 할 항목별 의미
- **`FROM` 줄**: 베이스 이미지와 태그. 예를 들어 `FROM ubuntu:20.04`라면 그 이미지에 포함된 glibc가 정확히 2.31 계열이라는 뜻이다(REV-0711, REV-0647). pwn 요소가 섞인 문제라면 이 버전에 맞는 `libc.so`를 구해야 하고, 순수 리버싱이라도 `printf`/`scanf` 같은 표준 함수의 미묘한 버전 차이(REV-0648)를 이 정보로 미리 짐작할 수 있다.
- **`COPY`/`ADD` 줄**: 어떤 파일이 컨테이너의 어느 경로에 배치되는지 보여준다. `COPY flag.txt /flag.txt`처럼 flag 파일 위치가 그대로 드러나는 경우도 흔하다.
- **`RUN apt-get install ...` / `RUN pip install ...`**: 추가로 설치되는 라이브러리나 도구가 있다는 뜻이며, 바이너리가 그 라이브러리에 동적으로 링크되어 있을 가능성을 알려준다.
- **`USER` 줄**: `USER nobody`처럼 비루트 권한으로 실행된다면, 원격 pwn 문제에서 특정 파일 접근이 제한된다는 뜻이다.
- **`ENTRYPOINT`/`CMD`**: 바이너리가 실제로 어떤 인자와 함께 실행되는지 보여준다. `socat`으로 포트를 여는 패턴이면 원격 접속 시 표준입출력이 그대로 소켓에 연결된다는 뜻이라, 로컬에서 인자 없이 실행한 것과 동작이 다를 수 있다.
- **`ENV` 줄**: 환경 변수가 미리 설정되어 있으면 그 값이 실행에 영향을 줄 수 있다(예: 특정 로케일, 디버그 플래그).
- **포트/`EXPOSE`**: 어떤 포트로 접속해야 하는지, 서비스가 몇 개 떠 있는지(예: 리버싱용 바이너리 하나 + 별도 검증 서버 하나) 알 수 있다.

### ASLR/리소스 제한 힌트
`docker-compose.yml`이나 `run.sh`에 `--security-opt seccomp=unconfined`, `ulimit`, `sysctl kernel.randomize_va_space` 같은 옵션이 있으면 ASLR이나 syscall 필터링 설정이 로컬 기본값과 다를 수 있다는 신호다. 순수 리버싱 문제에는 큰 영향이 없지만, pwn 요소가 섞였다면(REV-0319) 반드시 확인해야 하는 항목이다.

## 화면/코드에서 보이는 징후
- 첨부 zip 안에 `Dockerfile`, `docker-compose.yml`, `xinetd` 설정 파일이 함께 들어있음
- `Dockerfile` 안에 `FROM ubuntu:22.04` 같이 명확한 배포판/버전 태그가 있음
- `COPY chall /home/user/chall`처럼 실행 파일 배치 경로가 명시됨
- `CMD ["/home/user/chall"]` 또는 `ENTRYPOINT ["socat", "TCP-LISTEN:...", "EXEC:/home/user/chall"]` 같은 실행 명령

## 가장 먼저 할 것
`Dockerfile`을 텍스트 편집기로 열어 `FROM`, `COPY`, `CMD`/`ENTRYPOINT` 세 줄부터 확인한다. 이 세 줄만으로도 "어떤 OS/glibc에서, 어떤 파일 배치로, 어떻게 실행되는지"의 큰 그림이 잡힌다.

## 단계별 절차
1. `Dockerfile`의 `FROM` 줄에서 베이스 이미지와 태그를 기록 (예: `ubuntu:20.04`, `debian:bullseye-slim`, `alpine:3.18`)
2. `alpine` 계열이면 musl libc 기반임을 인지 (REV-0647) — 표준 함수 동작이 glibc와 다를 수 있음
3. `COPY`/`ADD` 줄을 모두 읽어 어떤 파일이 어디에 배치되는지, flag 파일 경로가 노출되는지 확인
4. `RUN apt-get install` 등에서 추가 설치되는 패키지 확인 — 바이너리가 의존하는 라이브러리 힌트
5. `USER` 줄로 실행 권한(root/nobody 등) 확인
6. `CMD`/`ENTRYPOINT` 줄로 바이너리가 실제로 어떤 인자/파이프라인으로 실행되는지 확인 (`socat` 경유 여부 포함)
7. `docker-compose.yml`이 있다면 `ports`, `environment`, `cap_drop`, `security_opt` 항목까지 확인
8. 확인한 glibc 버전에 맞춰 필요하면 해당 버전 `libc.so`를 별도로 준비해 로컬 검증 환경을 서버와 최대한 맞춤

## 명령어/단축키
```bash
cat Dockerfile
cat docker-compose.yml 2>/dev/null
grep -E "FROM|COPY|ADD|RUN|USER|CMD|ENTRYPOINT|ENV" Dockerfile
```

## 출력 해석
- `FROM` 태그에 버전이 없으면(`FROM ubuntu`) `latest` 태그를 쓴다는 뜻이라 정확한 glibc 버전을 Dockerfile만으로 확정할 수 없다 — 이때는 실제 바이너리의 `strings ... | grep "GNU C Library"` 결과를 더 신뢰한다.
- `ENTRYPOINT`가 `socat`을 경유하면 표준입출력이 그대로 소켓으로 연결되는 구조이므로, 로컬에서 인자 없이 실행했을 때와 개행 처리, 버퍼링 동작이 다를 수 있다는 점을 감안한다.
- `COPY flag /flag` 같은 줄이 보이면 flag 파일 자체의 정확한 절대 경로를 이미 알아낸 것이므로, 이후 익스플로잇/입력값에서 그 경로를 그대로 사용하면 된다.

## 흔한 실수
- Dockerfile을 아예 열어보지 않고 코드 분석부터 시작해서, glibc 버전 불일치로 나중에 다시 확인하러 돌아오는 것.
- `alpine` 베이스 이미지를 보고도 이를 무시한 채 glibc 기준으로 분석해서 함수 동작 차이(REV-0647)에 혼란을 겪는 것.
- `latest` 태그를 특정 버전으로 착각하고 그 버전 기준으로 완전히 확정해버리는 것 — 태그가 고정되어 있는지 항상 확인한다.
- Dockerfile에 명시된 실행 인자(`CMD`)를 무시하고 바이너리를 인자 없이 실행해서 다른 동작을 보고 잘못된 결론을 내리는 것.

## 막혔을 때 다음 체크
- glibc 버전 차이로 함수 동작이 헷갈린다 → REV-0648 glibc 버전별 함수 시그니처 차이 확인법, REV-0711 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때
- musl 기반 이미지라 낯설다 → REV-0647 musl libc와 glibc 차이가 리버싱에 미치는 영향
- 문제 설명 자체에서 다른 힌트도 더 뽑아야 한다 → REV-0012 문제 설명과 첨부파일에서 힌트 뽑는 방법
- pwn 요소까지 섞여서 환경 설정이 더 중요해졌다 → REV-0319 리버싱과 Pwnable이 섞인 문제 구분하는 법

## 미니 예제
```dockerfile
FROM ubuntu:20.04

RUN apt-get update && apt-get install -y socat

COPY chall /home/user/chall
COPY flag.txt /home/user/flag.txt
RUN chmod 400 /home/user/flag.txt

USER nobody
WORKDIR /home/user

CMD ["socat", "TCP-LISTEN:9999,reuseaddr,fork", "EXEC:/home/user/chall"]
```
이 Dockerfile 하나로 다음을 즉시 알 수 있다. ① `ubuntu:20.04` → glibc 2.31 계열, ② flag는 `/home/user/flag.txt`에 있고 `nobody` 권한으로는 읽기 권한이 400이라 소유자만 읽을 수 있음(권한 상승/파일 디스크립터 유출이 필요할 수도 있다는 신호), ③ `socat`으로 감싸져 있으니 원격 접속 시 표준입출력이 소켓과 그대로 연결된다는 것. 코드를 한 줄도 안 보고 이 정도 정보를 얻을 수 있다.

## 관련 글
- REV-0012 — 문제 설명과 첨부파일에서 힌트 뽑는 방법
- REV-0647 — musl libc와 glibc 차이가 리버싱에 미치는 영향
- REV-0648 — glibc 버전별 함수 시그니처 차이 확인법
- REV-0711 — 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때
- REV-0319 — 리버싱과 Pwnable이 섞인 문제 구분하는 법

## 출처/검증
- Dockerfile 지시어(`FROM`, `COPY`, `RUN`, `USER`, `CMD`, `ENTRYPOINT`)의 의미: Docker 공식 문서(docs.docker.com/reference/dockerfile) 기준.
- `ubuntu:20.04` 이미지의 기본 glibc 버전이 2.31 계열이라는 사실: Ubuntu 20.04 LTS(Focal Fossa) 공식 패키지 정보 및 본 위키 REV-0646/REV-0711 검증 내용과 동일 (2026-09-09 검증).
