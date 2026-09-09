---
id: REV-0632
title: "libc 함수 사전: atoi atol strtol strtoul"
slug: "rev-0632-libc-atoi-atol-strtol-strtoul"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, ltrace, objdump]
keywords: ["atoi", "atol", "strtol", "strtoul", "문자열 정수 변환", "endptr", "진법 base"]
aliases: ["atoi atol strtol strtoul 함수 사전", "atoi 시그니처", "strtol 시그니처", "atoi strtol 차이", "문자열을 숫자로 바꾸는 함수"]
symptom_keywords: ["atoi 잘못된 입력 처리", "strtol 반환값이 이상하다", "strtol endptr이 뭔지 모르겠다", "atoi 오버플로우 시 동작", "16진수 문자열을 숫자로 변환"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`atoi`/`atol`은 문자열을 정수로 바꿔주지만 **잘못된 입력에 대한 오류 검사가 전혀 없어** 실패해도 `0`을 반환하는 반면, `strtol`/`strtoul`은 진법(`base`)을 지정할 수 있고 `endptr`을 통해 "어디까지 숫자로 해석했는지"와 파싱 실패 여부를 정확히 알려준다.

## 언제 검색해야 하나
- `call atoi@plt`가 보이는데 사용자 입력을 검증 없이 정수로 바꿔서 이후 배열 인덱스나 크기로 쓰는 코드(정수 오버플로우/인덱스 취약점 후보)를 분석할 때
- `call strtol@plt`에 인자가 3개 전달되는데 세 번째 인자(`base`)가 무엇을 뜻하는지 확인하고 싶을 때
- `strtol` 호출 뒤 `errno`를 확인하는 코드가 있어 정확히 어떤 실패 케이스를 검사하는지 알고 싶을 때

## 핵심 개념
```c
int   atoi(const char *nptr);
long  atol(const char *nptr);
long  strtol(const char *nptr, char **endptr, int base);
unsigned long strtoul(const char *nptr, char **endptr, int base);
```

**atoi/atol**: 문자열 앞의 공백을 건너뛰고, 선택적 부호(`+`/`-`) 다음에 오는 숫자를 읽어 정수로 변환한다. **오류 검사가 전혀 없다** — 숫자로 시작하지 않는 문자열(`"abc"`)을 넘기면 그냥 `0`을 반환하고, 변환 결과가 `int`/`long` 범위를 넘으면 동작이 정의되지 않는다(Undefined Behavior, 실무에서는 대개 잘려서 이상한 값이 나옴). 즉 반환값 `0`만으로는 "입력이 진짜 `\"0\"`이었는지" "파싱에 실패했는지" 구분할 수 없다. SysV x64: `rdi=nptr`, 반환값은 `eax`(atoi) 또는 `rax`(atol).

**strtol/strtoul**: 같은 방식으로 문자열을 파싱하되 두 가지가 추가된다.
1. `base` — 몇 진법으로 해석할지 지정. `10`이면 10진수, `16`이면 16진수(`0x` 접두사 있어도 없어도 인식), `8`이면 8진수. **`base`를 `0`으로 주면** 문자열 접두사를 보고 자동 판별한다: `0x`/`0X` 시작이면 16진수, `0` 시작(그 다음 숫자)이면 8진수, 그 외는 10진수.
2. `endptr` — `NULL`이 아닌 `char **`를 넘기면, 함수가 파싱을 멈춘 지점(더 이상 숫자로 해석할 수 없는 첫 문자)의 주소를 `*endptr`에 써준다. **`*endptr == nptr`이면 숫자를 하나도 못 읽었다는 뜻**(완전 실패), `*endptr`이 문자열 끝(`\0`)을 가리키면 문자열 전체가 숫자였다는 뜻이다.

변환 결과가 `long`/`unsigned long` 범위를 넘으면 `strtol`은 `LONG_MAX`/`LONG_MIN`, `strtoul`은 `ULONG_MAX`를 반환하고 전역 변수 `errno`를 `ERANGE`로 설정한다 — `atoi`와 달리 **오버플로우를 명확히 감지할 수 있다.**

## 화면/코드에서 보이는 징후
- `call atoi@plt` 반환값을 곧바로 `malloc` 크기나 배열 인덱스로 사용 — 검증 없는 사용자 제어 정수가 크기/인덱스에 흘러드는 취약점 후보
- `mov edx, 0x10` (또는 `0xa`) 후 `call strtol@plt` — 세 번째 인자로 진법(16 또는 10)을 명시
- `strtol` 호출 후 `call __errno_location@plt`가 뒤따르면 `ERANGE` 검사를 하는 방어적 코드
- `lea rsi, [rbp-0x8]` (스택 변수 주소) 후 `call strtol@plt` — `endptr`을 받아 파싱 성공 여부를 검증하는 패턴

## 가장 먼저 할 것
`atoi`가 쓰였다면 "이 프로그램은 잘못된 숫자 입력에 대한 검증이 약하다"고 가정하고 그 반환값이 이후 어디에 쓰이는지(배열 크기, 인덱스, 반복 횟수) 추적한다. `strtol`이 쓰였다면 `base` 인자와 `endptr` 사용 여부부터 확인한다.

## 단계별 절차
1. `objdump -d ./chall | grep 'atoi@plt\|atol@plt\|strtol@plt\|strtoul@plt'`로 어떤 변환 함수가 쓰였는지 확인.
2. GDB에서 `break atoi` 후 `x/s $rdi`로 변환 대상 문자열 확인, `finish` 후 `print $eax`로 결과 확인.
3. `break strtol` 후 `x/s $rdi`(문자열), `print $rdx`(base), `print/x $rsi`(endptr 저장 위치, 0이면 안 씀) 확인.
4. `finish` 후 `print $rax`(변환 결과)와, endptr을 넘겼다면 `x/s *(char**)$rsi_저장주소`로 파싱이 어디서 멈췄는지 확인.
5. 반환값이 이후 `malloc`, 배열 인덱싱, 반복 카운터로 쓰이는지 xref로 추적.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'atoi@plt\|strtol@plt\|strtoul@plt'
ltrace ./chall
```
GDB/Pwndbg: `break atoi`, `break strtol`, `x/s $rdi`, `print $rdx`, `print $rax`, `print $eax`

## 출력 해석
- `atoi` 반환값이 `0`이면 실제 `"0"` 입력인지 파싱 실패인지 코드만으로는 구분 불가 — 실패 처리 분기가 없다면 그냥 `0`으로 취급되어 다음 로직으로 넘어간다는 뜻.
- `strtol`에서 `endptr`이 가리키는 문자가 `\0`이 아니면(`x/c *endptr`로 확인) 문자열 뒤에 숫자가 아닌 문자가 남아있다는 뜻 — `"123abc"` 같은 입력에서 `123`까지만 변환되고 `abc` 위치를 가리킨다.
- `strtol` 반환값이 `LONG_MAX`(0x7fffffffffffffff)이고 직후 `errno`가 `ERANGE`(34)면 오버플로우로 값이 잘렸다는 뜻이다.

## 흔한 실수
- `atoi("abc")`가 에러를 일으킨다고 생각하는 것 — 크래시 없이 조용히 `0`을 반환한다. 오류 처리를 기대하고 분기를 찾다가 못 찾는 경우가 많다.
- `strtol`의 `base=0`을 "진법 지정 안 함(에러)"으로 착각하는 것 — 실제로는 "문자열 접두사로 자동 판별"이라는 유효한 의미다.
- `endptr`을 확인하지 않고 `strtol` 반환값만 보고 "파싱 성공"이라 단정하는 것 — 숫자를 하나도 못 읽어도 `strtol`은 크래시 없이 `0`을 반환하며, 이 경우도 `endptr == nptr`으로만 구분할 수 있다.

## 막혔을 때 다음 체크
- 변환된 정수가 이후 malloc 크기로 쓰이는 흐름이 궁금하면 → REV-0626, REV-0627.
- 사용자 입력을 받는 함수 자체(scanf/fgets)가 궁금하면 → REV-0109.
- 라이브러리 호출 인자를 로그로 빠르게 보고 싶으면 → REV-0111(ltrace).

## 미니 예제
```c
char *end;
long v = strtol("0x2A", &end, 16);   // v = 42, *end = '\0'
int  n = atoi("not_a_number");        // n = 0 (에러 구분 불가)
```
```gdb
(gdb) break strtol
(gdb) run
(gdb) x/s $rdi
0x7fffffffe420: "0x2A"
(gdb) print $rdx
$1 = 16
(gdb) finish
Value returned is $2 = 42
```
`base=16`이 명시되어 있고 `"0x2A"`의 `0x` 접두사까지 정상 인식되어 결과가 `42`(0x2A)로 나온 것을 확인할 수 있다.

## 관련 글
- REV-0626 — libc 함수 사전: malloc free 계열
- REV-0109 — scanf fgets read 입력 추적
- REV-0110 — strcmp strncmp memcmp 비교 추적
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기

## 출처/검증
- `atoi`/`atol`/`strtol`/`strtoul` 시그니처와 오버플로우 시 `ERANGE`/`LONG_MAX` 동작: ISO C 표준(C11 7.22.1) 및 Linux man-pages `atoi(3)`, `strtol(3)` 기준.
- `atoi`가 오류 검사를 제공하지 않는다는 점은 `atoi(3)` man 페이지 "NOTES" 섹션 및 CERT C 코딩 표준(문자열-정수 변환 권고, ERR34-C)에서 공통적으로 지적하는 내용.
