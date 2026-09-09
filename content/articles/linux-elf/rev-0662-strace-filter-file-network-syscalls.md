---
id: REV-0662
title: "strace 결과를 파일/네트워크 시스템콜로 필터링해서 노이즈 줄이기"
slug: "rev-0662-strace-filter-file-network-syscalls"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [strace, GDB]
keywords: ["strace -e trace=file", "strace -e trace=network", "strace 필터링", "strace 그룹 매크로", "strace -y"]
aliases: ["strace 트레이스 필터", "strace 특정 시스템콜만 보기", "strace trace=open", "strace 네트워크 확인"]
symptom_keywords: ["strace 출력이 너무 많아서 못 읽겠음", "strace로 파일 경로만 보고 싶음", "strace로 소켓 연결만 보고 싶음", "strace 노이즈 줄이기"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`strace -e trace=file ./chall`, `strace -e trace=network ./chall`처럼 `-e trace=` 뒤에 시스템콜 이름이나 `%file`/`%network`/`%process`/`%signal`/`%desc` 같은 그룹 매크로를 지정하면, 수백 줄씩 쏟아지는 `mmap`/`brk`/`mprotect` 같은 초기화 노이즈를 걷어내고 "이 프로그램이 어떤 파일을 열고 어떤 소켓에 연결하는지"만 정확히 볼 수 있다.

## 언제 검색해야 하나
- `strace ./chall`을 그냥 돌렸는데 동적 링커 초기화 관련 시스템콜이 수백 줄 쏟아져서 정작 보고 싶은 부분을 찾기 힘들 때
- 바이너리가 어떤 설정 파일이나 flag 파일을 여는지, 어떤 IP/포트에 연결하는지만 빠르게 확인하고 싶을 때
- 네트워크 문제(서버 바이너리)에서 `bind`/`listen`/`accept`가 어떤 포트로 이뤄지는지 확인하고 싶을 때

## 핵심 개념

### -e trace= 필터 문법
`-e trace=` 뒤에는 쉼표로 구분된 시스템콜 이름 목록, 또는 `%`로 시작하는 그룹 매크로를 쓸 수 있다.
```bash
strace -e trace=open,openat,read ./chall     # 이름 나열
strace -e trace=%file ./chall                # 그룹 매크로
strace -e trace=%file,%network ./chall       # 그룹 여러 개 조합
```
앞에 `!`를 붙이면 반대로 "이것만 빼고" 필터가 된다:
```bash
strace -e trace=!brk,mmap,mprotect ./chall   # 초기화성 콜 제외
```

### 자주 쓰는 그룹 매크로
- `%file` — 파일 경로를 인자로 받는 시스템콜(`open`, `openat`, `stat`, `access`, `unlink`, `execve` 등)
- `%network` (별칭 `%net`) — 소켓 관련(`socket`, `connect`, `bind`, `listen`, `accept`, `send*`, `recv*`)
- `%process` — 프로세스 생성/제어(`fork`, `execve`, `exit`, `wait4` 등)
- `%signal` — 시그널 관련(`kill`, `rt_sigaction`, `rt_sigreturn` 등)
- `%desc` — 파일 디스크립터 조작(`read`, `write`, `close`, `dup2`, `fcntl` 등)
- `%memory` — 메모리 매핑 관련(`mmap`, `munmap`, `brk`, `mprotect`) — 이걸 제외하면 노이즈가 크게 줄어든다

### 왜 기본 strace가 시끄러운가
동적 링킹된 바이너리는 실행 시작 시 `ld.so`가 라이브러리들을 매핑하기 위해 `openat`, `mmap`, `mprotect`, `close` 등을 라이브러리 개수만큼 반복 호출한다. 이건 대부분 우리가 분석하려는 "프로그램 로직"과 무관한 부팅 단계 노이즈이므로, `-e trace=`로 관심 있는 콜만 골라내는 것이 실전에서 거의 필수다.

## 화면/코드에서 보이는 징후
`strace ./chall` 그냥 실행했을 때 화면이 `mmap(NULL, ...)`, `mprotect(...)`, `openat(AT_FDCWD, "/lib/x86_64-linux-gnu/libc.so.6", ...)` 같은 줄로 수십~수백 줄이 스크롤되어 정작 원하는 `open("flag.txt", ...)` 같은 줄을 찾기 어려운 상황이 전형적인 신호다.

## 가장 먼저 할 것
파일 관련 동작만 먼저 걸러서 본다:
```bash
strace -e trace=%file ./chall
```
서버/네트워크 바이너리라면:
```bash
strace -e trace=%network -f ./server
```

## 단계별 절차

**1) 관심사에 맞는 그룹부터 시도**
```bash
strace -e trace=%file ./chall
```

**2) 특정 함수만 정확히 짚고 싶다면 이름을 직접 나열**
```bash
strace -e trace=openat,read,write ./chall
```

**3) 파일 디스크립터가 실제 어떤 경로/소켓인지 같이 보고 싶다면 -y/-yy 추가**
```bash
strace -y -e trace=%desc ./chall
```
`-y`는 파일 디스크립터 번호 옆에 실제 경로를, `-yy`는 소켓의 경우 `TCP:[ip:port]`까지 보여준다.

**4) 자식 프로세스까지 함께 추적**
```bash
strace -f -e trace=%network ./server
```
`fork`/`execve`로 자식이 생기는 서버형 프로그램은 `-f` 없이는 부모 프로세스만 보인다.

**5) 타임스탬프와 함께 저장해서 나중에 분석**
```bash
strace -tt -e trace=%file,%network -o trace.log ./chall
```

**6) 호출 횟수/오류 코드만 요약**
```bash
strace -c ./chall
```
어떤 시스템콜이 몇 번 호출됐고 얼마나 시간을 썼는지, 에러가 몇 번 났는지(`errors` 열) 요약 테이블을 보여준다 — 특정 시스템콜이 비정상적으로 많이 호출되는(예: 무한 루프성 `read` 재시도) 문제를 찾을 때 유용하다.

## 명령어/단축키
```bash
strace -e trace=%file ./chall
strace -e trace=%network -f ./server
strace -e trace=!%memory ./chall          # 메모리 관련 제외
strace -e trace=openat,read,write ./chall
strace -y -e trace=%desc ./chall          # fd → 경로/소켓 표시
strace -c ./chall                          # 호출 횟수/시간 요약
strace -tt -o trace.log ./chall           # 마이크로초 타임스탬프 + 파일 저장
```

## 출력 해석
```
$ strace -e trace=%file ./chall
openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3
openat(AT_FDCWD, "/lib/x86_64-linux-gnu/libc.so.6", O_RDONLY|O_CLOEXEC) = 3
openat(AT_FDCWD, "flag.txt", O_RDONLY)   = -1 ENOENT (No such file or directory)
+++ exited (status 1) +++
```
- 앞의 두 `openat`은 동적 링커가 라이브러리를 찾는 정상적인 초기화 과정 — `%file`로 걸러도 완전히 없어지진 않지만 `read`/`mmap` 같은 나머지 노이즈는 사라진 상태다.
- 세 번째 줄 `openat(AT_FDCWD, "flag.txt", O_RDONLY) = -1 ENOENT`: 프로그램이 현재 디렉터리에서 `flag.txt`를 열려다가 **실패**했다는 뜻. `ENOENT`는 파일이 없다는 에러 코드이며, 이 한 줄만으로 "이 프로그램은 실행 위치에 `flag.txt` 파일이 있어야 정상 동작한다"는 걸 바로 알 수 있다 — 코드를 읽지 않고도 실행 환경 문제를 진단한 것이다.

```
$ strace -e trace=%network -f ./server
socket(AF_INET, SOCK_STREAM, IPPROTO_TCP) = 3
bind(3, {sa_family=AF_INET, sin_port=htons(9999), sin_addr=inet_addr("0.0.0.0")}, 16) = 0
listen(3, 5)                              = 0
accept(3, ...
```
`bind`의 `sin_port=htons(9999)` 부분에서 서버가 **9999번 ��트**로 리슨한다는 것이 코드를 안 봐도 바로 드러난다.

## 흔한 실수
- `-e trace=file`처럼 `%` 없이 그룹 이름만 쓰고 안 되는 줄 아는 것 — 최신 strace는 `%` 없이 `trace=file`도 허용하는 버전이 많지만, 이름 충돌(실제 `file`이라는 시스템콜은 없으므로 보통은 되지만) 혼동을 피하려면 그룹은 `%` 접두어를 명시하는 습관을 들이는 게 안전하다.
- 그룹 필터만 걸고 `-f`(자식 프로세스 추적)를 안 줘서 `fork`/`accept`로 생긴 자식의 네트워크 활동을 놓치는 것 — 서버형 프로그램은 거의 항상 `-f`가 필요하다.
- `-e trace=` 필터를 너무 좁게 걸어서 정작 원인이 되는 시스템콜(`mmap`으로 실행 가능한 메모리를 만드는 셸코드 인젝션 같은 경우)을 놓치는 것 — 처음엔 넓게 보고, 노이즈가 확인되면 그때 좁혀나가는 순서가 안전하다.
- ENOENT 같은 에러 리턴값을 무시하고 지나치는 것 — 시스템콜의 리턴값이 음수/에러 코드인 줄마다 왜 실패했는지 확인하는 습관이 중요하다.

## 막혔을 때 다음 체크
- 시스템콜이 아니라 라이브러리 함수(strcmp, malloc 등) 레벨에서 보고 싶다면 → REV-0663 ltrace 결과에서 라이브러리 호출 인자 해석하기
- exit code로 시그널 종료 여부를 먼저 스크리닝하고 싶다면 → REV-0661 리눅스 프로세스 종료 코드(Exit Code)로 크래시 원인 좁히기
- strace 기본 사용법 자체가 처음이라면 → REV-0112 strace 기본 사용법
- 이미 GDB로 브레이크포인트를 걸고 있는데 시스템콜 인자까지 자동으로 보고 싶다면 → REV-0656 GDB Python 스크립팅 기초

## 미니 예제
```bash
$ strace -y -e trace=%network,%file -f ./server 2>&1 | head -20
socket(AF_INET, SOCK_STREAM, IPPROTO_TCP) = 3<TCP:[0.0.0.0:0]>
bind(3<TCP:[0.0.0.0:0]>, {sa_family=AF_INET, sin_port=htons(1337), sin_addr=inet_addr("0.0.0.0")}, 16) = 0
listen(3<TCP:[0.0.0.0:1337]>, 10)        = 0
openat(AT_FDCWD, "/etc/services", O_RDONLY) = 4</TCP:[0.0.0.0:1337]>
```
`-y` 옵션 덕분에 파일 디스크립터 `3` 옆에 `<TCP:[0.0.0.0:1337]>`가 자동으로 붙어서, 이 fd가 어떤 소켓인지 즉시 알 수 있다 — 별도로 `bind` 인자를 손으로 계산할 필요가 없다.

## 관련 글
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0663 — ltrace 결과에서 라이브러리 호출 인자 해석하기
- REV-0661 — 리눅스 프로세스 종료 코드(Exit Code)로 크래시 원인 좁히기
- REV-0656 — GDB Python 스크립팅 기초(gdb.Breakpoint 등)

## 출처/검증
- `-e trace=`, `%file`/`%network`/`%process`/`%signal`/`%desc`/`%memory` 그룹 매크로, `-y`/`-yy`, `-f`, `-c` 옵션: `strace(1)` 공식 man page 기준 (2026-09-08 검증).
