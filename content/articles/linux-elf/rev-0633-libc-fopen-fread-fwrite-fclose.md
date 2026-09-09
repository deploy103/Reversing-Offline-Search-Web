---
id: REV-0633
title: "libc 함수 사전: fopen fread fwrite fclose"
slug: "rev-0633-libc-fopen-fread-fwrite-fclose"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, ltrace, strace, objdump]
keywords: ["fopen", "fread", "fwrite", "fclose", "FILE 구조체", "버퍼링 I/O", "stdio"]
aliases: ["fopen fread fwrite fclose 함수 사전", "fopen 시그니처", "fread 시그니처", "FILE 포인터", "stdio 버퍼링 파일 함수"]
symptom_keywords: ["fopen이 NULL을 반환한다", "fread 반환값이 요청 개수보다 작다", "fwrite 이후 파일에 내용이 안 보인다(버퍼링)", "fclose를 안 해서 데이터 유실", "FILE* 구조체가 뭔지 모르겠다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`fopen`/`fread`/`fwrite`/`fclose`는 `open`/`read`/`write`/`close` 시스템콜(REV-0634)을 감싸 **애플리케이션 레벨 버퍼링**을 제공하는 C 표준 입출력(stdio) 함수로, `FILE *` 구조체를 통해 상태를 관리하며 `fwrite`로 쓴 데이터가 즉시 디스크에 반영되지 않을 수 있다는 점이 리버싱/디버깅에서 자주 혼란을 준다.

## 언제 검색해야 하나
- `call fopen@plt` 반환값(`FILE *`)이 `NULL`인지 확인하는 코드를 만나 파일 열기 실패 처리를 분석할 때
- `fwrite`로 데이터를 썼는데 `strace`로는 대응하는 `write` 시스템콜이 안 보여서 버퍼링 때문인지 확인하고 싶을 때
- `fread`의 반환값이 요청한 개수보다 작아서 파일 끝(EOF)인지 에러인지 구분하고 싶을 때

## 핵심 개념
```c
FILE *fopen(const char *pathname, const char *mode);
size_t fread(void *ptr, size_t size, size_t nmemb, FILE *stream);
size_t fwrite(const void *ptr, size_t size, size_t nmemb, FILE *stream);
int    fclose(FILE *stream);
```

**fopen**: `pathname`을 `mode`(`"r"`, `"w"`, `"a"`, `"rb"`, `"r+"` 등)에 따라 열고 `FILE *`(불투명 구조체 포인터)를 반환한다. 실패하면 `NULL`을 반환하고 `errno`를 설정한다. 내부적으로 `open(2)` 시스템콜을 호출해 실제 파일 디스크립터(fd)를 얻은 뒤, 그 fd를 감싸는 `FILE` 구조체(내부에 fd, 버퍼 포인터, 버퍼 크기, 현재 위치 등을 가짐)를 힙에 할당해 채운다. `rdi=pathname`, `rsi=mode`.

**fread/fwrite**: `size`바이트짜리 항목을 `nmemb`개 읽거나 쓴다. 반환값은 **성공적으로 처리한 항목(요소) 개수**이며, 요청한 `nmemb`보다 작으면 파일 끝에 도달했거나 에러가 발생한 것이다(`feof(stream)`/`ferror(stream)`으로 구분 가능). SysV x64 인자 순서는 `rdi=ptr`, `rsi=size`, `rdx=nmemb`, `rcx=stream`.

**버퍼링**: stdio 함수들은 기본적으로 데이터를 즉시 시스템콜로 내보내지 않고 `FILE` 구조체 안의 내부 버퍼(기본 완전 버퍼링, 터미널이면 라인 버퍼링)에 모아뒀다가 버퍼가 차거나, `fflush(stream)`이 호출되거나, `fclose`될 때 실제 `write(2)` 시스템콜로 내보낸다. 그래서 `fwrite` 호출 직후 `strace`로는 `write` 시스템콜이 안 보일 수 있고, 프로그램이 크래시로 비정상 종료되면 버퍼에 남아있던 데이터가 아예 디스크에 반영되지 않고 유실될 수 있다.

**fclose**: 버퍼에 남은 데이터를 `fflush`한 뒤 fd를 `close(2)`하고 `FILE` 구조체 메모리를 해제한다. 성공 시 `0`, 실패 시 `EOF`(-1)를 반환한다.

## 화면/코드에서 보이는 징후
- `call fopen@plt` 이후 반환값을 `test rax, rax` / `je fail`로 NULL 체크
- `call fread@plt`/`call fwrite@plt` 인자가 4개(`rdi, rsi, rdx, rcx`)로 세팅됨 — `read`/`write` 시스템콜 래퍼(REV-0634, 인자 3개)와 인자 개수로 구분 가능
- `strace`로 실행했을 때 프로그램 코드상 `fwrite` 호출 여러 번인데 실제 `write` 시스템콜은 한 번만(또는 몇 번만) 보임 — 버퍼링 증거
- `objdump -d`에서 `__fpending`, `__flbf` 같은 심볼이 함께 보이면 stdio 내부 버퍼 상태를 직접 조작/확인하는 코드

## 가장 먼저 할 것
`fopen`의 `mode` 문자열(`"r"`/`"w"`/`"rb"` 등)부터 확인해 읽기용인지 쓰기용인지 파악한다. 이후 `fread`/`fwrite`의 `size * nmemb`가 실제로 몇 바이트인지 계산한다.

## 단계별 절차
1. `objdump -d ./chall | grep 'fopen@plt\|fread@plt\|fwrite@plt\|fclose@plt'`로 사용 여부 확인.
2. GDB에서 `break fopen` 후 `x/s $rdi`(경로), `x/s $rsi`(모드) 확인, `finish` 후 `print/x $rax`(FILE 포인터, NULL이면 실패).
3. `break fread`(또는 fwrite) 후 `print $rsi`(size), `print $rdx`(nmemb)로 총 바이트 수(`size*nmemb`) 계산.
4. `finish` 후 `print $rax`(실제 처리된 항목 개수)가 요청한 `nmemb`와 같은지 비교.
5. `strace -e trace=open,openat,read,write,close ./chall`로 실제 시스템콜과 stdio 호출 횟수를 비교해 버퍼링 여부 확인.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'fopen@plt\|fread@plt\|fwrite@plt\|fclose@plt'
ltrace -e 'fopen+fread+fwrite+fclose' ./chall
strace -e trace=openat,read,write,close ./chall
```
GDB/Pwndbg: `break fopen`, `break fread`, `break fwrite`, `x/s $rdi`, `print/x $rax`, `print $rsi`, `print $rdx`

## 출력 해석
- `fopen` 반환값이 `0x0`(NULL)이면 파일 열기 실패 — 경로가 틀렸거나 권한 문제. `mode`에 `"r"`이 있는데 파일이 없으면 항상 이렇게 실패한다.
- `fread` 반환값이 `nmemb`보다 작으면 파일 끝에 도달(EOF)했거나 읽기 에러 — `ferror`/`feof` 호출이 뒤따르는지 확인하면 어느 쪽인지 알 수 있다.
- `strace`에서 예상보다 `write` 호출이 적게 보이면, 프로그램이 정상 종료(`fclose`나 `exit`를 거쳐 stdio가 자동 flush)했는지, 아니면 비정상 종료로 데이터가 유실됐는지 확인해야 한다.

## 흔한 실수
- `fwrite` 호출이 곧바로 디스크 반영을 의미한다고 생각하는 것 — 버퍼링 때문에 `fclose`나 `fflush` 전까지는 실제 파일에 안 보일 수 있다.
- `fread`/`fwrite`의 반환값을 "바이트 수"로 착각하는 것 — 반환값은 **항목(요소) 개수**다. 실제 바이트 수를 알려면 반환값에 `size`를 곱해야 한다.
- `fopen` 실패를 세그폴트로 이어지는 원인으로 못 찾는 것 — `NULL`이 된 `FILE *`을 그대로 `fread`/`fwrite`에 넘기면 그 안에서 크래시가 나므로, 크래시 지점이 아니라 그 이전 `fopen` 반환값부터 확인해야 한다.

## 막혔을 때 다음 체크
- 버퍼링 없는 저수준 시스템콜 래퍼(open/read/write/close)와 비교하려면 → REV-0634.
- 라이브러리 호출과 실제 시스템콜을 함께 비교하려면 → REV-0111(ltrace), REV-0112(strace).
- 사용자 표준 입력 함수(scanf/fgets)와의 차이가 궁금하면 → REV-0109.

## 미니 예제
```c
FILE *fp = fopen("data.bin", "rb");
if (!fp) { /* 실패 처리 */ }
char buf[64];
size_t n = fread(buf, 1, sizeof(buf), fp);  // 최대 64바이트 읽기, n=실제 읽은 바이트 수
fclose(fp);
```
```gdb
(gdb) break fread
(gdb) run
(gdb) print $rsi
$1 = 1
(gdb) print $rdx
$2 = 64
(gdb) finish
Value returned is $3 = 40
```
`size=1`, `nmemb=64`인데 반환값이 `40`이므로 요청한 64바이트 중 실제로는 40바이트만 읽혔다 — 파일 크기가 40바이트였거나 EOF에 먼저 도달했다는 뜻이다.

## 관련 글
- REV-0634 — libc 함수 사전: open read write close(시스템콜 래퍼)
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0109 — scanf fgets read 입력 추적

## 출처/검증
- `fopen`/`fread`/`fwrite`/`fclose` 시그니처와 버퍼링 규칙: ISO C 표준(C11 7.21.5, 7.21.8) 및 Linux man-pages `fopen(3)`, `fread(3)`, `fclose(3)` 기준.
- stdio 버퍼링 종류(완전/라인/버퍼링 없음)와 `fflush` 관계: `setvbuf(3)` man 페이지 및 glibc 매뉴얼(stdio 섹션) 기준.
