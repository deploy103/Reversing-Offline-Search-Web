---
id: REV-0627
title: "libc 함수 사전: calloc realloc 계열"
slug: "rev-0627-libc-calloc-realloc"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, ltrace, objdump]
keywords: ["calloc", "realloc", "size_t", "nmemb", "정수 오버플로우", "heap chunk", "malloc_usable_size"]
aliases: ["calloc realloc 함수 사전", "calloc 시그니처", "realloc 시그니처", "calloc malloc 차이", "realloc 동작 방식"]
symptom_keywords: ["calloc과 malloc의 차이가 궁금하다", "realloc이 포인터를 옮기는지 궁금하다", "calloc 곱셈 오버플로우", "realloc(ptr, 0) 동작이 궁금하다", "realloc 실패 시 원본 포인터"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`calloc(nmemb, size)`은 `nmemb * size` 바이트를 확보하면서 **0으로 초기화**까지 해주는 함수이고, `realloc(ptr, size)`은 기존 힙 블록의 크기를 늘리거나 줄이면서 필요하면 새 위치로 데이터를 복사해주는 함수다 — 둘 다 인자 두 개(`rdi`, `rsi`)를 받는다는 점에서 `malloc`과 호출 패턴이 확연히 다르다.

## 언제 검색해야 하나
- `call calloc@plt` 직전에 `rdi`, `rsi` 두 레지스터가 세팅되는 걸 보고 어느 게 개수고 어느 게 크기인지 헷갈릴 때
- `realloc` 호출 후 이전 포인터를 계속 쓰는 코드가 있어서 use-after-free 버그인지 판단하고 싶을 때
- `calloc(nmemb, size)`에서 `nmemb * size`가 정수 오버플로우를 일으켜 힙 취약점이 되는 패턴(CTF 단골)을 찾고 싶을 때

## 핵심 개념
```c
void *calloc(size_t nmemb, size_t size);
void *realloc(void *ptr, size_t size);
```

**calloc**: SysV x64에서 `nmemb`는 `rdi`, `size`는 `rsi`로 전달된다. glibc 내부적으로 `nmemb * size`를 계산하기 전에 **오버플로우 검사**를 수행한다(`__libc_calloc`이 곱셈 결과가 `size_t` 범위를 넘는지 확인). 오버플로우가 감지되면 malloc을 호출하지 않고 즉시 `NULL`을 반환한다 — 이 검사 덕분에 `calloc(0x100000000, 0x100000000)` 같은 극단적 값도 안전하게 실패 처리된다(단, `nmemb*size`가 오버플로우 없이 계산 가능한 값이라면 그대로 큰 할당 시도).  `malloc(nmemb*size)` 로 직접 계산해서 넘기는 코드는 이 자동 검사가 없으므로, 프로그램이 `calloc` 대신 `malloc(n * sz)`를 직접 쓴다면 정수 오버플로우로 작은 청크가 할당되고 이후 큰 크기만큼 쓰기가 일어나는 힙 오버플로우가 가능하다 — CTF에서 자주 나오는 취약 패턴이다.

`calloc`이 반환하는 메모리는 malloc과 달리 **반드시 전부 0으로 채워져 있다.** 디스어셈블리에서 `calloc` 리턴 직후 `memset`이 없어도 값이 0이라는 걸 신뢰할 수 있다는 뜻이다.

**realloc**: `ptr`은 `rdi`, `size`는 `rsi`로 전달된다. 동작 규칙(POSIX/ISO C 기준):
- `ptr == NULL`이면 `malloc(size)`와 완전히 동일하게 동작한다.
- `size == 0`이고 `ptr != NULL`이면 (glibc 기준) `free(ptr)`과 동등하게 동작하고 `NULL`을 반환한다(C23 이전 표준에서는 구현 정의 영역이었으나 glibc는 이렇게 동작).
- 새 크기가 기존 청크 크기 이하로 줄어드는 경우, 여유가 있으면 **같은 주소**를 그대로 반환하는 경우가 많다(항상 그런 것은 아니다).
- 새 크기가 커서 현재 위치에서 확장할 수 없으면 새 청크를 `malloc`으로 확보하고, `memcpy`로 기존 데이터를 복사한 뒤, 기존 청크를 `free`하고 새 주소를 반환한다.
- **실패 시(NULL 반환) 원본 `ptr`은 해제되지 않고 그대로 유효하다.** `ptr = realloc(ptr, n)`처럼 원본 포인터에 결과를 바로 덮어쓰면, 실패했을 때 원본 포인터를 잃어버려 메모리 누수가 생기는 흔한 버그 패턴이다.

## 화면/코드에서 보이는 징후
- `mov edi, N` / `mov esi, M` 두 레지스터 세팅 후 `call calloc@plt` — 인자가 두 개면 malloc이 아니라 calloc/realloc일 가능성이 크다.
- `call realloc@plt` 직전 `rdi`에 이전에 malloc/calloc이 반환했던 포인터 변수가 로드됨.
- 디컴파일러(IDA/Ghidra)에서 `v2 = calloc(count, 4);`처럼 두 인자가 그대로 보임 — 곱셈이 계산되는 지점을 xref로 따라가면 정수 오버플로우 취약점 여부를 판단할 수 있다.

## 가장 먼저 할 것
호출부의 인자 개수(1개면 malloc/free류, 2개면 calloc/realloc)부터 구분한다. 그다음 첫 인자가 이전에 malloc이 반환했던 포인터인지(realloc), 아니면 단순 개수(nmemb)인지(calloc) 확인한다.

## 단계별 절차
1. `objdump -d ./chall | grep -B6 'call.*calloc@plt\|call.*realloc@plt'`로 인자 세팅 코드 확인.
2. GDB에서 `break calloc`, `print/x $rdi`(nmemb), `print/x $rsi`(size)로 실제 곱셈 전 값 확인.
3. `break realloc`, `print/x $rdi`(원본 포인터), `print/x $rsi`(새 크기)로 확인.
4. `finish` 후 `print/x $rax`로 반환 주소가 원본과 같은지(같은 자리에서 확장) 다른지(새 위치로 이동) 비교.
5. calloc 오버플로우 의심 시 `nmemb`, `size` 두 값을 곱해 `0xFFFFFFFFFFFFFFFF`(64비트 `size_t` 최대값)를 넘는지 계산기로 직접 검산.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'calloc@plt\|realloc@plt'
ltrace -e calloc+realloc ./chall
```
GDB/Pwndbg: `break calloc`, `break realloc`, `print/x $rdi`, `print/x $rsi`, `finish`, `chunk $rax`

## 출력 해석
- calloc이 반환한 메모리를 `x/16xb <addr>`로 찍었을 때 전부 `0x00`이면 정상 — malloc과 구분하는 가장 확실한 방법이다.
- `realloc` 반환값이 원본과 같으면 "제자리 확장/축소", 다르면 "새 청크로 이동 후 기존 청크 free"라는 뜻이므로 이전 포인터를 계속 참조하는 코드가 있다면 use-after-free 가능성을 의심한다.
- `realloc(ptr, 0)` 호출 직후 반환값이 `NULL`이면 정상 동작(free와 동등)이지 실패가 아니다.

## 흔한 실수
- `calloc(a, b)`의 인자 순서를 `malloc(a*b)`와 동일하게 생각해 어느 게 개수고 어느 게 크기인지 신경 쓰지 않는 것 — 시그니처상 순서가 고정되어 있어 gdb에서 `rdi`/`rsi`를 각각 정확히 라벨링해야 한다.
- `realloc`이 실패하면 원본 포인터가 자동으로 해제된다고 착각하는 것 — 실패해도 원본은 살아있다.
- `realloc`이 항상 새 주소를 반환한다고 가정하고 이전 포인터를 즉시 못 쓰게 만드는 코드를 찾는 것 — 축소나 여유 공간이 있는 확장은 같은 주소를 반환할 수 있다.

## 막혔을 때 다음 체크
- malloc/free 기본 동작이 먼저 헷갈리면 → REV-0626.
- 힙 함수 호출 로그를 빠르게 보고 싶으면 → REV-0111(ltrace).
- SysV 호출 규약에서 두 번째 인자가 어느 레지스터인지 다시 확인하려면 → REV-0106.

## 미니 예제
```c
int *arr = calloc(10, sizeof(int));   // rdi=10, rsi=4, 전부 0으로 초기화됨
arr = realloc(arr, 20 * sizeof(int)); // rdi=이전 arr, rsi=80
```
```gdb
(gdb) break calloc
(gdb) run
(gdb) print/x $rdi
$1 = 0xa
(gdb) print/x $rsi
$2 = 0x4
(gdb) finish
Value returned is $3 = (void *) 0x5555555592a0
(gdb) x/10xw 0x5555555592a0
0x5555555592a0: 0x00000000 0x00000000 0x00000000 0x00000000
...
```
10개 워드 전부 `0x00000000`으로 초기화되어 있는 것이 `malloc`과의 핵심 차이임을 확인할 수 있다.

## 관련 글
- REV-0626 — libc 함수 사전: malloc free 계열
- REV-0631 — libc 함수 사전: memmove memset memchr
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0106 — SysV AMD64 Calling Convention

## 출처/검증
- `calloc`/`realloc` 함수 시그니처와 표준 동작 규칙(ptr=NULL, size=0 처리): ISO C 표준(C11 7.22.3) 및 Linux man-pages `malloc(3)` 기준.
- glibc calloc의 곱셈 오버플로우 자체 검사(`__libc_calloc`): glibc 소스코드(`malloc/malloc.c`)에 공개된 구현 로직 기준 서술.
- realloc의 제자리 확장/이동 동작: glibc `malloc.c`의 `_int_realloc` 구현 및 다수의 공개 힙 익스플로잇 자료(how2heap) 기준 서술.
