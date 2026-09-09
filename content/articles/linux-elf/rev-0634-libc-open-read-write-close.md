---
id: REV-0634
title: "libc 함수 사전: open read write close(시스템콜 래퍼)"
slug: "rev-0634-libc-open-read-write-close"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, strace, objdump]
keywords: ["open", "read", "write", "close", "시스템콜", "syscall", "파일 디스크립터", "errno"]
aliases: ["open read write close 함수 사전", "open 시스템콜 래퍼", "read write 시스템콜", "파일 디스크립터 fd", "syscall 번호 read write open close"]
symptom_keywords: ["open이 -1을 반환한다", "read 반환값이 0이다", "write가 요청한 바이트보다 적게 썼다", "fd가 뭔지 모르겠다", "strace에서 read write open 시스템콜이 안 보인다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`open`/`read`/`write`/`close`는 glibc가 커널 시스템콜을 거의 그대로 감싼 얇은 래퍼 함수로, `fopen`/`fread`/`fwrite`/`fclose`(REV-0633)와 달리 **애플리케이션 레벨 버퍼링이 전혀 없어** 호출 즉시 커널로 요청이 전달되며, `strace`로 관찰했을 때 코드상의 호출 횟수와 실제 시스템콜 횟수가 거의 1:1로 대응한다.

## 언제 검색해야 하나
- `call open@plt`/`call read@plt`/`call write@plt`/`call close@plt`가 보이는데 `fopen` 계열과 뭐가 다른지, 왜 저수준 함수를 직접 썼는지 궁금할 때
- `strace ./chall`로 시스템콜 로그를 뜬 뒤, 그 로그의 `open`/`read`/`write` 호출과 디스어셈블리의 함수 호출을 1:1로 대응시키고 싶을 때
- 파일 디스크립터 번호(`0`, `1`, `2`, 또는 `open`이 반환한 값)가 무엇을 가리키는지 헷갈릴 때

## 핵심 개념
```c
int     open(const char *pathname, int flags, mode_t mode);
ssize_t read(int fd, void *buf, size_t count);
ssize_t write(int fd, const void *buf, size_t count);
int     close(int fd);
```
이 네 함수는 각각 x86-64 리눅스 syscall 번호 `2`(open), `0`(read), `1`(write), `3`(close)에 대응하는 `syscall(2)` 명령어 호출을 감싼 얇은 wrapper다. glibc 내부에서 인자를 레지스터(`rax`=syscall 번호, `rdi, rsi, rdx, ...`=인자)에 넣고 `syscall` 명령어를 실행하는 몇 줄짜리 코드로 구현되어 있다.

**open**: `pathname`을 `flags`(`O_RDONLY`=0, `O_WRONLY`=1, `O_RDWR`=2, `O_CREAT`=0x40, `O_TRUNC`=0x200, `O_APPEND`=0x400 등 OR 조합)에 따라 열고, 성공하면 **파일 디스크립터(fd, 0 이상의 정수)**를 반환한다. 실패하면 `-1`을 반환하고 `errno`를 설정한다. `O_CREAT`가 있을 때만 세 번째 인자 `mode`(예: `0644`)가 실제로 쓰인다. `rdi=pathname`, `esi=flags`, `edx=mode`.

**read/write**: `fd`가 가리키는 대상(파일, 파이프, 소켓, 표준입출력 등)과 `buf` 사이에서 정확히 `count`바이트를 옮기려 **시도**한다. **반환값이 요청한 `count`보다 작을 수 있다** — 이는 버그가 아니라 정상 동작이다(파일 끝 도달, 파이프에 데이터가 일부만 준비됨, 시그널에 의한 중단 등). 그래서 견고한 코드는 `read`/`write`를 반환값만큼 반복 호출하는 루프(short read/write 처리)를 둔다. `read`가 `0`을 반환하면 파일 끝(EOF)을 의미하고, `-1`은 에러다. `rdi=fd`, `rsi=buf`, `rdx=count`.

**close**: `fd`를 닫아 커널의 파일 테이블 엔트리를 해제한다. 성공 시 `0`, 실패 시 `-1`.

**표준 파일 디스크립터**: `0`=stdin, `1`=stdout, `2`=stderr는 프로세스 시작 시 이미 열려 있다. `open`이 새로 반환하는 fd는 보통 사용 중이 아닌 가장 작은 정수(예: 첫 `open` 호출이면 `3`)부터 할당된다.

## 화면/코드에서 보이는 징후
- `mov edx, 0x1B6` (0644, mode) 후 `mov esi, 0x241`(O_CREAT|O_TRUNC|O_WRONLY 조합) 후 `call open@plt`
- `call read@plt`/`call write@plt` 인자가 3개(`rdi, rsi, rdx`)로 `fread`/`fwrite`(인자 4개)보다 하나 적음
- 반환값을 `cmp eax, -1` / `je fail`로 체크하는 코드가 `open`/`read`/`write` 공통 패턴
- `strace`에서 `openat(AT_FDCWD, "flag.txt", O_RDONLY) = 3` 처럼 실제 fd 번호와 플래그 심볼이 그대로 보임(최신 glibc는 `open`을 내부적으로 `openat` 시스템콜로 구현하는 경우가 많음)

## 가장 먼저 할 것
`open`의 `flags` 값을 8진수/16진수 상수 조합으로 해석해 읽기 전용인지 쓰기(생성) 모드인지 먼저 파악한다. 이후 `read`/`write`의 `fd` 인자가 `open`이 반환한 값인지, 아니면 `0`/`1`(표준 입출력)인지 확인한다.

## 단계별 절차
1. `objdump -d ./chall | grep 'open@plt\|read@plt\|write@plt\|close@plt'`로 호출 지점 나열.
2. `strace ./chall`로 실제 실행 중 시스템콜 로그를 떠서 `openat`/`read`/`write`/`close`의 실제 인자와 반환값을 확인.
3. GDB에서 `break open` 후 `x/s $rdi`(경로), `print/x $rsi`(flags)로 8진수/16진수 상수를 실제 매크로로 환산(`O_RDONLY=0`, `O_WRONLY=1`, `O_RDWR=2`, `O_CREAT=0x40`, `O_TRUNC=0x200`).
4. `break read`(또는 write) 후 `print $rdi`(fd), `print/x $rsi`(buf), `print $rdx`(count) 확인, `finish` 후 `print $rax`(실제 처리된 바이트 수)와 비교.
5. 반환값이 요청보다 작으면 이후 코드가 루프를 도는지(short read 처리) 확인.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'open@plt\|read@plt\|write@plt\|close@plt'
strace -e trace=openat,read,write,close ./chall
```
GDB/Pwndbg: `break open`, `break read`, `break write`, `x/s $rdi`, `print/x $rsi`, `print $rdx`, `print $rax`

## 출력 해석
- `open` 반환값이 `-1`이면 실패 — `strace` 로그의 같은 줄 끝에 `ENOENT`(파일 없음), `EACCES`(권한 없음) 같은 에러 이름이 함께 출력되어 원인을 바로 알 수 있다.
- `read` 반환값이 `0`이면 EOF(더 읽을 데이터 없음), 양수면 실제로 읽은 바이트 수, `-1`이면 에러다. **요청한 `count`와 다르다고 무조건 에러는 아니다.**
- `strace` 로그의 시스템콜 호출 순서(`open` → `read`(들) → `close`)를 그대로 프로그램의 파일 처리 흐름으로 읽을 수 있다.

## 흔한 실수
- `read`/`write`가 항상 요청한 바이트 수만큼 정확히 처리한다고 가정하는 것 — 특히 파이프나 소켓, 큰 파일에서는 short read/write가 흔하고, 이를 무시하면 데이터 일부가 누락된 채로 처리되는 버그가 생긴다.
- `open`의 `flags` 상수를 10진수 그대로 읽어서 어떤 플래그 조합인지 헷갈리는 것 — 반드시 16진수/8진수로 변환해 `O_CREAT`(0x40), `O_TRUNC`(0x200) 등의 비트가 켜져 있는지 OR 분해해서 봐야 한다.
- fd `0`/`1`/`2`를 일반 파일로 착각하는 것 — 이 세 값은 표준 입력/출력/에러이지 `open`으로 새로 연 파일이 아니다.

## 막혔을 때 다음 체크
- 버퍼링이 있는 상위 레벨 stdio 함수(fopen/fread/fwrite)와 비교하려면 → REV-0633.
- 시스템콜을 전체적으로 추적하는 방법이 궁금하면 → REV-0112(strace).
- 라이브러리 호출까지 함께 보고 싶으면 → REV-0111(ltrace).

## 미니 예제
```c
int fd = open("flag.txt", O_RDONLY);   // flags=0
if (fd < 0) { /* 실패 */ }
char buf[32];
ssize_t n = read(fd, buf, sizeof(buf));
write(1, buf, n);                       // fd=1(stdout)로 그대로 출력
close(fd);
```
```
$ strace -e trace=openat,read,write,close ./chall
openat(AT_FDCWD, "flag.txt", O_RDONLY) = 3
read(3, "CTF{...}\n", 32)              = 9
write(1, "CTF{...}\n", 9)              = 9
close(3)                                = 0
```
`open`이 반환한 fd `3`이 이후 `read`의 첫 인자로 그대로 쓰이고, `write`는 fd `1`(stdout)로 화면에 출력하는 흐름을 로그만으로 그대로 재구성할 수 있다.

## 관련 글
- REV-0633 — libc 함수 사전: fopen fread fwrite fclose
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0106 — SysV AMD64 Calling Convention

## 출처/검증
- `open`/`read`/`write`/`close` 시그니처, 반환값, `errno` 규칙: POSIX.1 및 Linux man-pages `open(2)`, `read(2)`, `write(2)`, `close(2)` 기준.
- x86-64 Linux syscall 번호(read=0, write=1, open=2, close=3)와 레지스터 전달 방식: Linux 커널 `arch/x86/entry/syscalls/syscall_64.tbl` 및 x86-64 syscall calling convention(공개 syscall table 문서) 기준.
- glibc가 `open`을 내부적으로 `openat` 시스템콜로 구현하는 경향: glibc 릴리스 노트 및 `strace` 실측 관찰 기준.
