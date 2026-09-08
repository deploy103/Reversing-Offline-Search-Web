---
id: REV-0109
title: "scanf fgets read 입력 추적"
slug: "rev-0109-input-functions"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [IDA, GDB, Pwndbg, ltrace]
keywords: ["scanf", "__isoc99_scanf", "fgets", "gets", "read", "getchar", "입력 함수", "버퍼", "stdin"]
aliases: ["scanf 추적", "fgets 버퍼 위치", "read 시스템콜 추적", "입력 버퍼 찾기"]
symptom_keywords: ["입력값이 어디에 저장되는지 모르겠음", "버퍼 주소를 못찾겠음", "scanf 포맷 문자열이 뭔지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
CTF 리버싱에서 사용자 입력이 프로그램 안 어디로 들어가는지 알고 싶다면 `scanf`/`fgets`/`read`/`gets` 같은 입력 함수의 **호출 직전 레지스터**(SysV AMD64 규약, REV-0106)를 보면 되고, 대개 "버퍼 주소"가 첫 번째나 두 번째 인자에 그대로 들어있어 그 자리에 브레이크포인트를 걸고 실행 후 버퍼를 들여다보면 입력값을 바로 확인할 수 있다.

## 언제 검색해야 하나
- 디스어셈블리에서 `call scanf`, `call __isoc99_scanf`, `call fgets`, `call read`가 보이는데 사용자가 입력한 값이 정확히 어느 변수(스택 오프셋)에 들어가는지 찾고 싶을 때
- 입력값을 받은 뒤 그 값을 어디서 검사하는지(비교 로직으로 이어지는지) 추적하고 싶을 때
- `gets`가 왜 위험한 함수로 취급되는지, `fgets`와 뭐가 다른지 궁금할 때

## 핵심 개념

### 각 함수의 시그니처와 인자 의미
CTF/리버싱에서 자주 보는 입력 함수들을 SysV AMD64 규약(`RDI, RSI, RDX, ...`, REV-0106) 기준으로 정리하면:

| 함수 | 시그니처 | RDI | RSI | RDX |
|---|---|---|---|---|
| `scanf` | `int scanf(const char *format, ...)` | 포맷 문자열 주소 | 첫 버퍼 주소(있다면) | (추가 버퍼) |
| `__isoc99_scanf` | glibc 내부에서 `scanf`가 실제로 링크되는 이름(C99 규격 반영) | 위와 동일 | 위와 동일 | |
| `fgets` | `char *fgets(char *s, int size, FILE *stream)` | 버퍼 주소 | 최대 읽을 크기 | 스트림(`stdin` 등) |
| `gets` | `char *gets(char *s)` (사실상 폐기된 위험 함수) | 버퍼 주소만 (크기 제한 없음!) | | |
| `read` | `ssize_t read(int fd, void *buf, size_t count)` | 파일 디스크립터(0=stdin) | 버퍼 주소 | 읽을 최대 바이트 수 |
| `getchar` | `int getchar(void)` | (인자 없음) | | |

`scanf`류는 인자 개수가 가변적이라(포맷 문자열의 `%` 지시자 개수만큼) 버퍼 인자가 두 번째(`RSI`)부터 순서대로 이어진다 — `scanf("%d %s", &num, buf)`라면 `RDI`=포맷 문자열, `RSI`=`&num`, `RDX`=`buf`가 된다.

### gets가 특히 위험한 이유
`gets`는 읽을 최대 길이를 아예 인자로 받지 않는다 — 개행문자가 나올 때까지 무한정 읽어서 버퍼에 채운다. 그래서 버퍼 크기를 넘는 입력을 주면 그대로 스택을 덮어써버리는(버퍼 오버플로우) 것이 사실상 확정적이다. 이 문제 때문에 glibc는 `gets`를 쓰면 링크 시점에 경고를 내고, 최신 표준(C11)에서는 아예 제거됐다. CTF 문제에서 `gets` 또는 `gets_s`가 아닌 그냥 `gets` import가 보이면, 그 자체로 "여기가 취약점이다"라는 강한 신호로 읽어도 좋다.

`fgets`는 두 번째 인자로 최대 크기를 받으므로 크기를 초과한 입력은 잘라서 받고(개행 또는 크기-1 바이트까지) 안전하다 — **단, 그 크기 인자를 프로그래머가 버퍼의 실제 크기보다 크게 잘못 넣었다면** `fgets`를 써도 오버플로우가 날 수 있다는 점은 주의해야 한다. 즉 함수 이름만 보고 안전하다고 단정하지 말고, 실제로 넘어온 크기 인자 값을 확인하는 습관이 중요하다.

### read()와 libc 버퍼링
`read`는 libc 함수가 아니라 시스템 콜 래퍼다(REV-0106의 syscall 규약 참고). `scanf`/`fgets`는 내부적으로 결국 `read` 시스템 콜을 호출하지만, libc가 중간에 버퍼링을 하기 때문에 실제 `read` 호출 횟수나 타이밍이 코드에서 보이는 `scanf` 호출과 1:1로 대응하지 않을 수 있다. 정적 링킹 바이너리이거나 `strace`로 커널 레벨에서 관찰하고 싶다면 REV-0112(strace)를 참고한다. 반대로 프로그램이 `scanf`/`fgets` 같은 libc 함수를 아예 안 쓰고 `read(0, buf, n)`을 직접 호출하는 경우(정적 링킹, 어셈블리로 직접 작성, 또는 단순히 그렇게 짜여진 코드)도 흔하니 import 목록에 `scanf`가 없다고 입력이 없는 프로그램이라 오해하면 안 된다 — `read`도 함께 확인해야 한다.

### 포맷 문자열로 입력 개수/타입 짐작하기
`scanf`를 만나면 가장 먼저 첫 번째 인자(포맷 문자열)를 읽어서 몇 개의, 어떤 타입의 값을 받는지 파악한다. `%d`는 `int*`, `%s`는 `char*`(공백까지 읽음, 길이 제한 없어 위험할 수 있음), `%c`는 `char*`, `%lf`는 `double*` 하나씩을 뒤이은 인자로 요구한다. `%s`는 `gets`와 마찬가지로 길이 제한이 없는 형태로 자주 쓰이므로(`scanf("%s", buf)`), CTF에서 `scanf("%s", ...)` 패턴은 버퍼 오버플로우 후보로 항상 의심해봐야 한다.

## 화면/코드에서 보이는 징후
- `call scanf` 또는 `call __isoc99_scanf` 직전에 `lea rax, [rbp-0x20]`처럼 스택 버퍼의 주소를 계산해 `RSI`(또는 그 이후)에 넣는 코드가 보임
- `call fgets` 직전에 세 개의 값(버퍼, 크기, `stdin`)이 순서대로 채워짐, 특히 `RDX`에 `stdin`(전역 변수 `_IO_2_1_stdin_`의 주소 또는 GOT를 거친 값)이 들어감
- Import 목록에 `gets`가 보임 — 그 자체로 취약점 후보
- `call read`(PLT 경유) 직전에 `EDI=0`(stdin 파일 디스크립터)이 세팅됨

## 가장 먼저 할 것
프로그램의 import 목록(REV-0101)에서 `scanf`, `__isoc99_scanf`, `fgets`, `gets`, `read`, `getchar` 등이 있는지부터 확인한다. 있다면 그 호출부로 바로 이동해서, 버퍼로 쓰이는 스택 주소(또는 힙 주소)가 어느 로컬 변수인지 특정하고, 그 변수의 크기(주변 `sub rsp, N`이나 다른 변수와의 오프셋 차이로 추정)를 함께 기록해둔다.

## 단계별 절차

**1) 입력 함수 호출부 찾기**
IDA에서 import 목록의 `scanf`/`fgets`/`read`를 더블클릭해 Xref(cross-reference)를 확인하거나, `objdump -d ./chall | grep -B10 'call.*scanf@plt'`로 직전 코드를 훑는다.

**2) 호출 직전 인자 확인(정적)**
`RDI`, `RSI`, `RDX` 각각에 어떤 값이 들어가는지 코드로 읽는다.

**3) GDB로 실제 버퍼 주소와 크기 확인(동적)**
```gdb
break *0x<call주소>
run
info registers rdi rsi rdx
```

**4) 함수 실행 후 입력값 확인**
```gdb
finish
x/s $rsi        ; fgets라면 버퍼 주소가 rdi였으므로 x/s $rdi
```
`fgets`는 `finish` 이후 `RAX`에도 버퍼 시작 주소가 그대로 반환되므로 `x/s $rax`로도 확인 가능하다.

**5) 버퍼가 스택의 어느 위치인지, 카나리/리턴 주소와 얼마나 떨어져 있는지 확인**
```gdb
p $rbp - $rsi     ; fgets라면 rdi가 버퍼 주소
```
결과 값이 그 함수가 선언한 스택 버퍼 크기보다 작다면, 카나리나 리턴 주소를 덮어쓸 여지가 있는지 대략 가늠할 수 있다(순수 리버싱이라면 이 정보는 "버퍼 이름/크기 추정"에, pwn 관점이라면 오버플로우 가능성 판단에 쓰인다).

## 명령어/단축키
```bash
objdump -d ./chall | grep -B10 'call.*scanf@plt'
```
GDB: `break *0x<addr>`, `info registers rdi rsi rdx`, `finish`, `x/s $rax`

## 출력 해석
- `x/s $rax`(fgets 리턴 후)에 사람이 입력한 문자열이 그대로 보이면 그 값이 프로그램 안에서 어떻게 쓰이는지 다음 코드를 계속 따라가면 된다.
- `scanf`의 리턴값(`RAX`)은 "성공적으로 채운 변수 개수"다 — 포맷에 지시자가 3개인데 리턴값이 2라면 마지막 하나는 입력에 실패했다는 뜻이고, 코드에서 이 리턴값을 검사하는 분기가 있는지 확인하면 입력 검증 로직을 파악할 수 있다.

## 흔한 실수
- `scanf("%s", buf)`와 `scanf("%9s", buf)`를 구분하지 않는 것 — 폭 지정자(`%9s`처럼 숫자)가 있으면 그만큼 길이 제한이 걸린 것이라 오버플로우 후보에서 제외해야 한다.
- `fgets`가 항상 안전하다고 가정하는 것 — 두 번째 인자(크기)가 버퍼의 실제 크기보다 크게 잘못 지정된 코드도 실제로 존재한다.
- `read` 호출을 시스템 콜 레벨로 착각해 `scanf`/`fgets`와 무관하다고 생각하는 것 — libc 함수 내부에서도 결국 `read` 시스템 콜로 귀결되므로 개념적으로 연결돼 있다(REV-0112 참고).
- 입력 함수 호출 후 버퍼 값을 바로 확인하지 않고 한참 뒤 코드까지 실행시켜버려 원본 입력값을 놓치는 것 — `finish` 직후 바로 `x/s`로 확인하는 습관을 들인다.

## 막혔을 때 다음 체크
- 입력값이 이후 `strcmp`/`memcmp`로 비교되는 부분을 추적하고 싶다면 → REV-0110 strcmp strncmp memcmp 비교 추적
- 호출 규약 자체를 더 알고 싶다면 → REV-0106 SysV AMD64 Calling Convention
- 라이브러리 호출을 코드 수정 없이 빠르게 다 보고 싶다면 → REV-0111 ltrace로 라이브러리 호출 빠르게 보기
- 시스템 콜 레벨(`read`)에서 관찰하고 싶다면 → REV-0112 strace로 시스템 콜에서 힌트 찾기

## 미니 예제
```bash
$ objdump -d ./chall | grep -B6 'call.*fgets@plt' | head -8
  40116a: 48 8d 45 e0    lea    rax,[rbp-0x20]
  40116e: ba 20 00 00 00 mov    edx,0x20        ; size = 32
  401173: 48 89 c6       mov    rsi,rax          ; 잘못 배치 예시(실제로는 rdi=buf, rsi=size, rdx=stream 순)
```
```gdb
(gdb) break *0x401178
(gdb) run
(gdb) info registers rdi rsi rdx
rdi   0x7fffffffe4c0   ; 버퍼 주소
rsi   0x20             ; 최대 32바이트
rdx   0x7ffff7dd1980    ; stdin
(gdb) finish
Run till exit ...
(gdb) x/s $rax
0x7fffffffe4c0: "hello_input\n"
```
버퍼 주소(`RDI`), 크기(`RSI`), 스트림(`RDX`)이 정확히 확인되고, `finish` 후 실제 입력값도 그대로 보인다.

## 관련 글
- REV-0110 — strcmp strncmp memcmp 비교 추적
- REV-0106 — SysV AMD64 Calling Convention
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0101 — Dynamic Linking과 Import 함수 추적

## 출처/검증
- `scanf`/`fgets`/`gets`/`read` 함수 시그니처: POSIX.1-2017 / ISO C 표준 라이브러리 명세 및 Linux man-pages(`scanf(3)`, `fgets(3)`, `gets(3)`, `read(2)`) 기준.
- `gets` 폐기(C11에서 제거) 배경: ISO/IEC 9899:2011(C11) 및 glibc 링크 경고 문서 기준 (2026-09-08 검증).
