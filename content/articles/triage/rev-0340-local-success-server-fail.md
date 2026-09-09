---
id: REV-0340
title: "로컬에서는 성공하는데 서버에서는 실패할 때"
slug: "rev-0340-local-success-server-fail"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [pwntools, GDB, patchelf]
keywords: ["로컬 성공 서버 실패", "process 대 remote", "환경 차이", "ASLR", "glibc 버전 차이", "환경변수 차이"]
aliases: ["로컬은 되는데 원격은 안 됨", "process()는 되는데 remote()는 안 됨", "익스플로잇이 서버에서만 실패", "로컬 테스트만 성공"]
symptom_keywords: ["local로 실행하면 성공하는데 remote로 붙이면 실패함", "로컬 익스플로잇은 되는데 서버 제출하면 안 됨", "환경 차이 때문에 결과가 다른 것 같음", "로컬과 서버에서 다른 주소나 다른 동작이 나옴"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
로컬(`process()`, 직접 실행)에서는 성공하는데 원격 서버(`remote()`, `nc`)에서만 실패한다면, 원인은 거의 항상 **로컬과 서버 사이의 환경 차이**(glibc 버전, ASLR, 작업 디렉터리/파일, 환경변수, 스택 레이아웃, 리소스 제한, 네트워크 타이밍) 중 하나이며, "익스플로잇 로직 자체가 틀렸다"보다 "가정한 환경이 서버와 다르다"를 먼저 의심해야 한다.

## 언제 검색해야 하나
- pwntools 스크립트에서 `p = process(['./chall'])`로는 원하는 동작(쉘 획득, 특정 값 leak 등)이 성공하는데 `p = remote('host', port)`로 바꾸면 크래시하거나 응답이 없을 때
- 로컬에서 GDB로 디버깅하며 확인한 주소/오프셋을 그대로 썼는데 서버에서는 다른 결과가 나올 때
- 로컬 우분투/데비안 개발 환경과 문제 서버가 서로 다른 Docker 이미지/배포판일 가능성이 있을 때
- 여러 번 재시도해도 서버에서만 재현이 안 되는 미묘한 차이가 있을 때

## 핵심 개념
"로컬 성공, 서버 실패"는 하나의 원인이 아니라 여러 후보의 묶음이다. 아래 순서대로 하나씩 배제해나가는 것이 가장 효율적이다.

### 1) glibc/libc 버전 차이
문제 서버가 특정 Docker 이미지(예: Ubuntu 20.04, glibc 2.31)로 배포되는데 로컬 시스템은 더 최신이거나 다른 배포판(glibc 2.38+)일 수 있다. `system`, `execve`, `/bin/sh` 문자열, `one_gadget` 후보 주소가 버전마다 다르고, malloc 내부 구조(tcache 등)도 버전마다 다르다. 문제 zip에 `libc.so.6`이 첨부되어 있다면 그게 정답 환경이므로 로컬 재현도 반드시 그 libc로 강제해야 한다. → 자세한 절차는 REV-0711 참고.

### 2) ASLR과 하드코딩된 주소
로컬 GDB 디버깅 중에는 `set disable-aslr on`(GDB 기본값이기도 함)이나 습관적으로 ASLR을 꺼두고 테스트하는 경우가 많다. 이 상태에서 확인한 절대 주소를 그대로 익스플로잇에 박아넣으면, ASLR이 켜진 서버 환경에서는 매번 다른 주소가 나오므로 실패한다. leak 없이 하드코딩된 주소를 쓰고 있다면 이게 원인일 가능성이 매우 높다.

### 3) 파일 시스템/작업 디렉터리 차이
바이너리가 특정 경로의 파일(`flag.txt`, 설정 파일, 추가 라이브러리)을 상대 경로로 읽는다면, 로컬 테스트 디렉터리 구조와 서버의 작업 디렉터리 구조가 다를 수 있다. 로컬에서는 우연히 그 파일이 존재해서 성공한 것처럼 보이지만, 서버에서는 파일이 없거나 다른 위치에 있어서 다른 분기를 타는 경우가 있다.

### 4) 환경변수 차이
`process()`는 기본적으로 현재 셸의 전체 환경변수를 그대로 물려주지만, 서버는 서비스 실행 스크립트(`xinetd`, `systemd`, Docker `ENTRYPOINT`)가 설정한 최소한의 환경변수만 가진 채로 실행되는 경우가 많다. 환경변수의 **개수와 내용 자체가 초기 스택 레이아웃(스택에 먼저 올라가는 `envp` 배열과 각 문자열)에 영향을 준다** — 즉 스택 기반 버프오버플로우에서 정확한 오프셋을 로컬 환경 기준으로 계산했다면, 서버의 환경변수 개수가 달라 스택 주소/오프셋이 몇 바이트 밀려서 실패할 수 있다. pwntools에서는 `process(['./chall'], env={})`처럼 환경변수를 명시적으로 제한/고정해서 서버와 최대한 비슷한 조건을 만들 수 있다.

### 5) 리소스 제한(ulimit) 차이
로컬 셸의 `ulimit -s`(스택 크기), `ulimit -c`(core dump), 파일 디스크립터 제한 등이 서버 서비스 실행 환경과 다를 수 있다. 특히 스택 크기 제한이 다르면 큰 지역 배열/재귀 관련 동작이나 특정 오버플로우 성공 여부가 달라질 수 있다.

### 6) 여러 접속을 동시에 처리하는 서버 구조
로컬에서는 항상 새 프로세스를 하나씩 깨끗하게 실행하지만, 서버는 `fork()`한 자식 프로세스로 여러 접속을 동시에 처리하거나, 요청마다 컨테이너를 새로 띄우는 구조일 수 있다. 이 과정에서 표준입출력 버퍼링 방식(REV-0337), 소켓 지연(REV-0338), 또는 동시 접속으로 인한 자원 경쟁이 로컬 단일 실행과 다른 타이밍을 만들 수 있다.

### 7) 커널/시스템 레벨 차이
로컬 개발 머신과 서버가 다른 리눅스 커널 버전, 다른 CPU 아키텍처 세부사항(예: mitigation 패치), 또는 컨테이너 격리 방식을 쓰면 일부 시스템콜 동작이나 타이밍 관련 익스플로잇(레이스 컨디션 등)이 미묘하게 다르게 동작할 수 있다.

## 화면/코드에서 보이는 징후
- `process()`로는 쉘을 획득하는데 `remote()`로는 세그폴트(비정상 종료)만 발생.
- leak한 주소를 빼서 계산한 libc base의 하위 12비트가 로컬에서는 항상 0이었는데 서버에서는 다른 패턴을 보임(라이브러리 자체가 다를 가능성).
- 로컬에서 계산한 스택 오버플로우 페이로드 길이가 서버에서는 정확히 몇 바이트씩 어긋나서 크래시.
- 로컬 GDB 세션에서 확인한 주소가 실행할 때마다 동일(ASLR 꺼짐)한데, 서버는 접속마다 다른 주소를 사용하는 것으로 추정됨.

## 가장 먼저 할 것
문제 zip/tar에 `libc.so.6`, `ld-*.so` 같은 파일이 포함되어 있는지 가장 먼저 확인한다. 포함되어 있다면 그 파일이 서버의 "정답 환경"이므로, 로컬 재현을 그 libc로 강제(`patchelf`/`pwninit`)하는 것이 가장 흔하고 중요한 첫 조치다. 포함되어 있지 않다면 ASLR/leak 여부, 환경변수, 파일 경로 순서로 점검한다.

## 단계별 절차

**1) libc 버전 강제 일치**
```bash
strings libc.so.6 | grep "GNU C Library"
pwninit
```
자세한 절차는 REV-0711 참고.

**2) ASLR 켠 상태로 로컬 재현**
```bash
echo 2 | sudo tee /proc/sys/kernel/randomize_va_space   # ASLR 켬(임시)
python3 exploit.py LOCAL
```
ASLR을 켠 상태에서도 로컬 익스플로잇이 안정적으로 성공하는지 먼저 확인한다. 이 단계에서 실패한다면 leak 로직 자체가 부족한 것이지 서버만의 문제가 아니다.

**3) 환경변수를 서버와 비슷하게 제한**
```python
p = process(['./chall'], env={})   # 환경변수 전부 비움 (또는 서버가 설정할 법한 최소값만 지정)
```
로컬 전체 환경변수를 물려받는 기본 동작과 비교해서, 최소 환경으로도 페이로드/오프셋이 그대로 동작하는지 확인한다.

**4) 상대 경로 의존성 확인**
```bash
strace -f -e trace=open,openat ./chall 2>&1 | grep -v ENOENT
```
바이너리가 실제로 어떤 파일을 여는지 확인해서, 서버 환경에 그 파일이 없을 가능성이 있는지 점검한다.

**5) 리소스 제한 비교**
```bash
ulimit -a
```
로컬 셸의 제한값들을 확인하고, 문제에 `Dockerfile`이 첨부되어 있다면 그 안에 설정된 `ulimit`/`--ulimit` 값과 비교한다.

**6) 로컬에서 소켓 서비스처럼 재현해 최종 확인**
```bash
socat tcp-listen:4444,reuseaddr,fork exec:./chall &
python3 exploit.py REMOTE   # host를 127.0.0.1:4444로
```
`process()` 직접 실행이 아니라 실제 소켓을 통한 접속으로 로컬 재현을 해봐서, 순수 프로세스 실행과 다른 점(버퍼링, 타이밍)이 있는지 최종 확인한다.

## 명령어/단축키
```bash
strings libc.so.6 | grep "GNU C Library"
pwninit
echo 2 | sudo tee /proc/sys/kernel/randomize_va_space
strace -f -e trace=open,openat ./chall
ulimit -a
socat tcp-listen:4444,reuseaddr,fork exec:./chall &
```
```python
p = process(['./chall'], env={})
libc = ELF('./libc.so.6')  # 배포된 파일 그대로
```

## 출력 해석
- ASLR을 켠 로컬 테스트에서 실패율이 올라간다면(0/10 성공 등) leak 로직 자체가 불완전하다는 뜻 — 서버 문제가 아니라 익스플로잇 자체를 더 다듬어야 한다.
- `env={}`로 실행했을 때 오프셋이 달라져서 크래시한다면, 원래 오프셋 계산이 로컬 환경변수 개수에 암묵적으로 의존하고 있었다는 강한 신호다.
- `strace`에서 `openat(..., "flag.txt", ...) = -1 ENOENT`처럼 뜬다면 그 파일이 로컬에는 있어서 성공했지만 서버에는 없어서 다른 분기를 탈 수 있다는 뜻이다.

## 흔한 실수
- glibc 버전 차이(REV-0711)를 확인하지 않고 로컬 시스템 기본 libc로 오프셋을 계산해 그대로 서버에 쏘는 것.
- ASLR을 끈 상태로만 로컬 검증하고 "잘 되니까 서버에서도 되겠지"라고 넘어가는 것.
- 환경변수/작업 디렉터리 차이 같은 미묘한 원인은 생각하지 않고 익스플로잇 로직 자체를 계속 고쳐 쓰는 것 — 로직은 이미 맞을 수 있다.
- REV-0338(타임아웃)이나 REV-0337(버퍼링)로 인한 증상을 "익스플로잇이 실패했다"고 오판하는 것 — 실제로는 정상 동작 중인데 응답을 못 받아서 실패로 보이는 경우가 섞여 있을 수 있다.

## 막혔을 때 다음 체크
- glibc 버전 차이가 원인으로 확정되면 → REV-0711(서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때)
- 애초에 서버 응답 자체를 못 받고 있는 것 같다면 → REV-0338(서버 문제에서 타임아웃이 계속 발생할 때), REV-0337(nc로 접속은 되는데 프롬프트가 안 보일 때)
- 결과값(flag)은 나왔는데 서버가 계속 오답 처리한다면 → REV-0339(Flag 형식은 맞는데 서버가 계속 오답 처리할 때)
- 공유 라이브러리 자체를 못 찾는 에러가 뜬다면 → REV-0706(공유 라이브러리를 못 찾아서 error가 뜰 때)

## 미니 예제
```bash
$ ls
chall  libc.so.6  ld-2.31.so
$ file /lib/x86_64-linux-gnu/libc.so.6
/lib/x86_64-linux-gnu/libc.so.6: ... for GNU/Linux 3.2.0, ... stripped   # 로컬 시스템 libc, 버전 표기 없음
$ strings libc.so.6 | grep "GNU C Library"
GNU C Library (Ubuntu GLIBC 2.31-0ubuntu9.16) stable release version 2.31.   # 배포된 libc는 2.31
```
로컬 시스템은 이미 더 최신 glibc를 쓰고 있어서, 배포된 `libc.so.6`(2.31) 기준으로 계산한 `system` 오프셋이 로컬 기본 실행 시 완전히 다른 위치를 가리켰던 것이 원인이었다. `pwninit`으로 인터프리터/rpath를 패치한 뒤 로컬 재현과 서버 결과가 일치했다.

## 관련 글
- REV-0711 — 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때
- REV-0337 — nc로 접속은 되는데 프롬프트가 안 보일 때
- REV-0338 — 서버 문제에서 타임아웃이 계속 발생할 때
- REV-0339 — Flag 형식은 맞는데 서버가 계속 오답 처리할 때
- REV-0706 — 공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때

## 출처/검증
- glibc 버전별 심볼 오프셋/malloc 구조 차이 및 `patchelf`/`pwninit` 사용: glibc 공식 NEWS, patchelf(NixOS/patchelf) 및 pwninit(io12/pwninit) 공식 저장소 기준.
- ASLR(`/proc/sys/kernel/randomize_va_space`) 및 프로세스 초기 스택에 `envp`가 실리는 방식: Linux 커널 문서(`Documentation/admin-guide/sysctl/kernel.rst`) 및 System V AMD64 ABI의 "Initial Stack and Register State" 섹션 기준.
- pwntools `process(env=...)` 옵션 동작: pwntools 공식 문서(docs.pwntools.com) 기준 (2026-09-09 확인).
