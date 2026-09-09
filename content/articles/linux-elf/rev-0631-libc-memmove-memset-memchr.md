---
id: REV-0631
title: "libc 함수 사전: memmove memset memchr"
slug: "rev-0631-libc-memmove-memset-memchr"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, ltrace, objdump]
keywords: ["memmove", "memset", "memchr", "memcpy 차이", "겹치는 메모리", "버퍼 초기화"]
aliases: ["memmove memset memchr 함수 사전", "memmove 시그니처", "memset 시그니처", "memchr 시그니처", "memmove memcpy 차이"]
symptom_keywords: ["memmove와 memcpy 차이가 궁금하다", "memset으로 스택 변수 초기화", "memchr로 특정 바이트 찾기", "memset 두번째 인자가 int인 이유", "메모리 겹칠 때 memcpy 쓰면 안되는 이유"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`memmove`는 `memcpy`와 달리 **출발지와 목적지 메모리 영역이 겹쳐도 안전하게** 복사하고, `memset`은 지정한 바이트 값으로 메모리 블록 전체를 채우며, `memchr`은 문자열이 아니라 **임의의 바이트 배열**에서 특정 바이트를 찾는다 — 셋 다 문자열의 널 종료(`\0`)를 신경 쓰지 않고 정확히 `n`바이트만큼만 동작한다는 공통점이 있다.

## 언제 검색해야 하나
- `call memmove@plt`가 보이는데 `memcpy`와 뭐가 다른지, 왜 이 자리에서 `memcpy` 대신 쓰였는지 궁금할 때
- `call memset@plt`로 스택 버퍼나 구조체를 0으로 초기화하는 코드를 확인하고 싶을 때 (카나리 우회/버퍼 클리어 패턴 분석)
- `call memchr@plt`로 바이너리 데이터(널 바이트 포함 가능) 안에서 특정 값을 찾는 로직을 분석할 때

## 핵심 개념
```c
void *memmove(void *dest, const void *src, size_t n);
void *memset(void *s, int c, size_t n);
void *memchr(const void *s, int c, size_t n);
```

**memmove**: `dest`와 `src` 영역이 겹쳐도 항상 올바른 결과를 보장한다. 내부적으로 두 영역이 겹치는지 확인해, 겹치면 뒤에서 앞으로(또는 임시 버퍼를 거쳐) 복사하는 방식으로 원본 데이터가 복사 도중 훼손되지 않게 한다. `memcpy`는 이 겹침 여부를 확인하지 않으므로 겹치는 영역에 쓰면 결과가 정의되지 않는다(Undefined Behavior) — 그래서 **배열 내부에서 요소를 앞/뒤로 밀 때**(`memmove(arr, arr+1, ...)` 같은 패턴, 예: 배열에서 원소 삭제)는 반드시 `memmove`를 써야 한다. SysV x64: `rdi=dest`, `rsi=src`, `rdx=n`.

**memset**: `s`가 가리키는 메모리 `n`바이트를 전부 `c`값(하위 1바이트만 사용, `int`로 전달되지만 실제로는 `unsigned char`로 캐스팅됨)으로 채운다. `rdi=s`, `esi=c`, `rdx=n`. 흔히 `memset(buf, 0, sizeof(buf))`처럼 버퍼를 0으로 초기화(제로화)하는 데 쓰이며, 비밀번호/키 버퍼를 다 쓰고 나서 메모리에 남지 않도록 지우는 보안 코드에서도 자주 보인다(단, 컴파일러 최적화로 이 `memset`이 "죽은 코드"로 제거될 수 있어 실제 보안 코드에서는 `explicit_bzero`/`memset_s` 등을 쓰기도 한다).

**memchr**: `s`가 가리키는 `n`바이트 범위 안에서 값 `c`(1바이트)가 처음 나타나는 위치를 반환한다. `strchr`과 달리 **널 종료 문자열을 가정하지 않는다** — `n` 범위 안에 `\0`이 섞여 있어도 무시하고 정확히 `n`바이트까지만 탐색하므로, 바이너리 데이터(이미지, 암호화된 블록 등)에서 특정 바이트를 찾을 때 쓰인다. 못 찾으면 `NULL`.

## 화면/코드에서 보이는 징후
- `call memmove@plt` 인자 중 `rdi`와 `rsi`의 차이가 작은 상수(예: 배열 원소 크기)일 때 — 같은 버퍼 내에서 데이터를 밀어내는(shift) 패턴
- `xor esi, esi` 후 `call memset@plt` — 흔한 "0으로 초기화" 패턴 (`esi=0`)
- 함수 진입부(prologue) 직후 스택 버퍼 전체에 대해 `call memset@plt` — 지역 변수를 매번 0으로 리셋하는 방어적 코드이거나 컴파일러가 삽입한 스택 클리어
- `call memchr@plt` 반환값을 `NULL` 비교로 검증 — 특정 바이트(예: 개행 `\n`, 구분자 `0xFF`) 존재 여부 확인

## 가장 먼저 할 것
`memmove`인지 `memcpy`인지부터 구분한다(둘 다 `@plt`로 보이므로 이름을 정확히 읽어야 함). `memmove`가 쓰였다면 "출발지/목적지가 겹칠 수 있는 상황"임을 전제로 로직을 해석한다.

## 단계별 절차
1. `objdump -d ./chall | grep 'memmove@plt\|memset@plt\|memchr@plt'`로 사용 여부와 개수 확인.
2. GDB에서 `break memmove` 후 `print/x $rdi`(dest), `print/x $rsi`(src), `print/x $rdx`(n)로 두 주소 차이를 직접 계산해 겹치는지 확인.
3. `break memset` 후 `print/x $rdi`, `print (char)$esi`(채우는 값), `print/x $rdx`(길이)로 어떤 영역을 무슨 값으로 채우는지 확인.
4. `break memchr` 후 `x/Nxb $rdi`(n)로 탐색 대상 바이트 배열을 직접 확인, `print (char)$esi`로 찾는 값 확인.
5. `finish` 후 반환값(`$rax`)이 `NULL`인지, 아니면 유효한 포인터인지 확인.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'memmove@plt\|memset@plt\|memchr@plt'
ltrace -e 'memmove+memset+memchr' ./chall
```
GDB/Pwndbg: `break memmove`, `break memset`, `break memchr`, `print/x $rdi`, `print/x $rsi`, `print/x $rdx`, `x/Nxb <addr>`

## 출력 해석
- `memmove` 호출 시 `dest - src`(또는 `src - dest`)의 절대값이 `n`보다 작으면 두 영역이 실제로 겹친다는 뜻 — 왜 `memcpy` 대신 `memmove`를 썼는지 설명된다.
- `memset` 호출 직후 `x/Nxb $rdi`로 찍었을 때 지정한 값(예: `0x00`)으로 전부 채워져 있으면 정상 동작.
- `memchr`이 `NULL`을 반환하면 해당 바이트가 지정된 `n`바이트 범위 안에 없다는 뜻이며, 그 이후 분기 로직(예: "구분자를 못 찾음 → 에러 처리")을 확인한다.

## 흔한 실수
- `memmove`와 `memcpy`를 같은 함수로 취급해 겹침 여부 분석을 생략하는 것 — 이름이 다르면 반드시 겹침 가능성을 열어두고 분석해야 한다.
- `memset(ptr, value, n)`의 두 번째 인자를 "바이트 개수"로 착각하는 것 — 두 번째 인자는 **채울 값**이고, 세 번째 인자가 개수다. 순서를 거꾸로 읽으면 완전히 다른 해석이 나온다.
- `memchr`이 문자열 함수라서 널 종료에서 멈춘다고 가정하는 것 — `memchr`은 오직 `n` 값으로만 범위를 제한하며 중간에 `\0`이 있어도 계속 탐색한다.

## 막혔을 때 다음 체크
- 비교 계열(memcmp 포함)이 궁금하면 → REV-0110.
- 문자열 탐색(strchr 등, 널 종료 기준)과 헷갈리면 → REV-0630.
- calloc이 이미 0으로 채워주는 것과 memset의 관계가 궁금하면 → REV-0627.

## 미니 예제
```c
char arr[10] = "0123456789";
memmove(arr, arr + 2, 5);   // "01234"->자리를 "23456"으로 덮음, 겹치지만 안전
memset(arr + 5, 'X', 5);    // 뒤 5바이트를 'X'로 채움 -> "23456XXXXX"
```
```gdb
(gdb) break memmove
(gdb) run
(gdb) print/x $rdi
$1 = 0x7fffffffe410
(gdb) print/x $rsi
$2 = 0x7fffffffe412
(gdb) print/x $rdx
$3 = 0x5
```
`$rsi - $rdi = 2`가 `n`(5)보다 작으므로 두 영역이 겹친다 — 이런 경우 `memcpy`를 썼다면 결과가 깨질 수 있었던 자리다.

## 관련 글
- REV-0627 — libc 함수 사전: calloc realloc 계열
- REV-0630 — libc 함수 사전: strchr strstr strtok
- REV-0110 — strcmp strncmp memcmp 비교 추적
- REV-0629 — libc 함수 사전: strcpy strncpy strcat strncat

## 출처/검증
- `memmove`/`memset`/`memchr` 시그니처와 겹침 안전성 규칙: ISO C 표준(C11 7.24.2.2, 7.24.6.1, 7.24.5.1) 및 Linux man-pages `memmove(3)`, `memset(3)`, `memchr(3)` 기준.
- `memcpy` 겹침 시 Undefined Behavior라는 점은 C 표준 7.24.2.1(memcpy) 명세 "the objects overlap" 조항 기준.
