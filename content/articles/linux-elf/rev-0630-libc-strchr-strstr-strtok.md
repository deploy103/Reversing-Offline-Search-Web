---
id: REV-0630
title: "libc 함수 사전: strchr strstr strtok"
slug: "rev-0630-libc-strchr-strstr-strtok"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, ltrace, objdump]
keywords: ["strchr", "strstr", "strtok", "strtok_r", "문자열 탐색", "delimiter", "정적 내부 상태"]
aliases: ["strchr strstr strtok 함수 사전", "strchr 시그니처", "strstr 시그니처", "strtok 시그니처", "strtok 스레드 안전성"]
symptom_keywords: ["strchr이 NULL을 반환한다", "strstr로 문자열 안 문자열 찾기", "strtok로 문자열이 쪼개지는 이유", "strtok가 원본 문자열을 변형한다", "strtok NULL 인자 의미"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`strchr`은 문자열에서 특정 **문자** 하나를 찾고, `strstr`은 문자열 안에서 다른 **부분 문자열**을 찾으며, `strtok`은 구분자(delimiter)를 기준으로 문자열을 조각내는데 **원본 문자열을 직접 변형**하고 호출 사이에 내부 정적 상태를 공유한다는 점이 리버싱에서 자주 헷갈리는 포인트다.

## 언제 검색해야 하나
- `call strchr@plt` 반환값이 `NULL`인지 아닌지에 따라 분기하는 코드를 만나 어떤 문자를 찾는지 확인하고 싶을 때
- `strstr`로 특정 부분 문자열(플래그 접두사, 명령어 등)을 찾는 검증 로직을 분석할 때
- `strtok`을 여러 번 연속 호출하는데 첫 번째 인자가 `NULL`인 이유를 모를 때
- 입력을 여러 토큰으로 나누는 파서 코드를 분석할 때

## 핵심 개념
```c
char *strchr(const char *s, int c);
char *strstr(const char *haystack, const char *needle);
char *strtok(char *str, const char *delim);
```

**strchr**: `s`에서 문자 `c`(1바이트로 취급, `int`로 전달되지만 실제로는 `unsigned char`로 비교)가 처음 나오는 위치의 포인터를 반환한다. 못 찾으면 `NULL`. `c`로 `'\0'`(0)을 넘기면 문자열의 널 종료 위치 자체를 찾아준다(항상 성공). SysV x64에서는 `rdi=s`, `esi=c`.

**strstr**: `haystack` 안에서 `needle` 전체가 연속으로 나타나는 첫 위치를 반환한다. `needle`이 빈 문자열("")이면 `haystack` 자체(시작 위치)를 반환한다. 못 찾으면 `NULL`. `rdi=haystack`, `rsi=needle`.

**strtok**: 가장 주의가 필요한 함수다.
- 첫 호출에서는 `str`에 실제 대상 문자열을 넘긴다. 함수는 `str` 내부의 첫 번째 delimiter 문자를 **직접 `'\0'`으로 덮어써서** 그 자리에서 문자열을 끊고, 토큰의 시작 포인터를 반환한다. 즉 **원본 버퍼가 변형된다**(읽기 전용 문자열 리터럴을 넘기면 세그폴트).
- 두 번째 호출부터는 `str` 자리에 **`NULL`**을 넘긴다. `strtok`은 함수 내부에 `static` 포인터(스레드 로컬이 아님)로 "마지막으로 끊은 위치"를 기억하고 있다가 그 다음부터 이어서 파싱한다.
- `delim`은 "구분자로 취급할 문자들의 집합"이며 하나의 문자열이 아니라 문자 하나하나가 개별 구분자다(예: `strtok(s, " ,")`는 공백과 콤마 둘 다 구분자).
- 내부 상태가 전역(정적) 변수이므로 **멀티스레드 환경이나 재귀/중첩 호출에서 안전하지 않다.** 재진입이 필요하면 `char *strtok_r(char *str, const char *delim, char **saveptr)`를 쓴다 — 상태를 호출자가 직접 관리하는 `saveptr` 인자로 넘기므로 스레드마다 독립적으로 쓸 수 있다.

## 화면/코드에서 보이는 징후
- `mov esi, 0x2f` (문자 리터럴, 예: `/`) 후 `call strchr@plt` — 특정 문자(경로 구분자 등)를 찾는 패턴
- `call strstr@plt` 이후 반환값을 `NULL` 비교로 분기 — "특정 부분 문자열 포함 여부" 검증 로직
- 반복문 안에서 `mov rdi, 0` (또는 `xor edi, edi`) 후 `call strtok@plt` — 두 번째 호출부터 첫 인자가 0이 되는 전형적인 strtok 루프
- `strtok_r@plt` 호출 시 세 번째 인자로 스택 변수 주소(`lea rdx, [rbp-0x8]`)가 매번 전달됨

## 가장 먼저 할 것
`strtok`이 보이면 루프 안에서 첫 호출과 이후 호출의 첫 인자가 다른지(원본 → `NULL`)부터 확인해 "이게 토큰화 루프구나"라고 파악한다. `strchr`/`strstr`은 반환값이 `NULL`이냐 아니냐로 분기하는 지점을 먼저 찾는다.

## 단계별 절차
1. `objdump -d ./chall | grep 'strchr@plt\|strstr@plt\|strtok@plt\|strtok_r@plt'`로 어떤 함수가 쓰였는지 목록화.
2. GDB에서 `break strchr` 후 `x/s $rdi`(대상 문자열), `print (char)$esi`(찾는 문자)로 확인.
3. `break strstr` 후 `x/s $rdi`, `x/s $rsi`로 haystack/needle 둘 다 확인.
4. `break strtok`을 반복 히트할 때마다 `print $rdi`가 0인지 아닌지, `x/s $rsi`(delim)를 매번 확인해 루프 구조 파악.
5. `finish` 후 `x/s $rax`로 매 호출이 반환하는 토큰 문자열을 순서대로 기록.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'strchr@plt\|strstr@plt\|strtok@plt'
ltrace -s 200 ./chall
```
GDB/Pwndbg: `break strchr`, `break strstr`, `break strtok`, `x/s $rdi`, `x/s $rsi`, `print (char)$esi`, `x/s $rax`

## 출력 해석
- `strchr` 반환값이 `NULL`(0)이면 그 문자가 문자열에 없다는 뜻이므로, 반환값을 실패 처리로 쓰는 분기(`je`)가 뒤따르는 게 정상이다.
- `strstr` 반환값이 `haystack`의 시작 주소와 같다면 needle이 문자열 맨 앞에서 매치된 것이다(오프셋 0).
- `strtok` 호출을 계속 반복하다 반환값이 `NULL`이 되면 더 이상 남은 토큰이 없다는 뜻 — 대부분 파싱 루프의 종료 조건이다.

## 흔한 실수
- `strtok`이 원본 문자열을 바꾸지 않는다고 착각하는 것 — 원본 버퍼에 `'\0'`을 직접 써넣으므로, 이후 원본 전체 문자열을 다시 쓰려는 코드가 있으면 이미 조각나 있어 예상과 다른 결과가 나온다.
- 문자열 리터럴(`"a,b,c"`처럼 `.rodata`에 있는 읽기 전용 문자열)을 `strtok`의 첫 인자로 바로 넘겼다고 가정하는 것 — 실제로 그렇게 하면 쓰기 시도 시 세그폴트가 나므로, 반드시 스택/힙에 복사된 버퍼여야 한다.
- `strchr(s, c)`에서 `c`를 문자열로 착각하는 것 — `c`는 단일 문자(정수)이지 문자열 포인터가 아니다. `strstr`과 헷갈리기 쉽다.

## 막혔을 때 다음 체크
- 비교 함수(strcmp/strncmp/memcmp)로 확장해서 보고 싶으면 → REV-0110.
- 복사/연결 함수(strcpy/strcat 계열)가 궁금하면 → REV-0629.
- 메모리 단위 탐색(memchr)이 궁금하면 → REV-0631.

## 미니 예제
```c
char buf[] = "flag=CTF{example}";
char *p = strtok(buf, "=");   // "flag" 반환, buf는 "flag\0CTF{example}"로 변형됨
char *q = strtok(NULL, "=");  // 이어서 "CTF{example}" 반환
```
```gdb
(gdb) break strtok
(gdb) run
(gdb) x/s $rdi
0x7fffffffe400: "flag=CTF{example}"
(gdb) x/s $rsi
0x402004: "="
(gdb) finish
Value returned is $1 = (char *) 0x7fffffffe400 "flag"
(gdb) x/24xb 0x7fffffffe400
0x7fffffffe400: 0x66 0x6c 0x61 0x67 0x00 0x43 0x54 0x46 ...
```
5번째 바이트(원래 `=`가 있던 자리)가 `0x00`으로 바뀐 것이 `strtok`이 원본을 변형했다는 직접적인 증거다.

## 관련 글
- REV-0629 — libc 함수 사전: strcpy strncpy strcat strncat
- REV-0631 — libc 함수 사전: memmove memset memchr
- REV-0110 — strcmp strncmp memcmp 비교 추적
- REV-0109 — scanf fgets read 입력 추적

## 출처/검증
- `strchr`/`strstr`/`strtok`/`strtok_r` 시그니처와 내부 정적 상태 규칙: ISO C 표준(C11 7.24.5) 및 Linux man-pages `strchr(3)`, `strstr(3)`, `strtok(3)` 기준.
- `strtok`이 스레드 안전하지 않다는 점과 `strtok_r`의 재진입 설계는 POSIX.1 `strtok_r(3)` 명세 기준.
