---
id: REV-0626
title: "libc 함수 사전: malloc free 계열"
slug: "rev-0626-libc-malloc-free"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, ltrace, objdump]
keywords: ["malloc", "free", "heap chunk", "tcache", "size_t", "PREV_INUSE", "double free", "use-after-free"]
aliases: ["malloc free 함수 사전", "malloc 시그니처", "free 시그니처", "힙 청크 구조", "malloc 반환값"]
symptom_keywords: ["malloc이 뭘 반환하는지 모르겠다", "free 이후 크래시", "double free 에러", "heap chunk 크기가 요청한 크기와 다르다", "malloc(0) 반환값이 궁금하다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`malloc(size_t size)`은 힙에서 최소 `size` 바이트를 확보해 그 시작 주소를 반환하고, `free(void *ptr)`은 그 메모리를 다시 할당자(glibc ptmalloc2)에 반납하는 함수로, 리버싱 시에는 인자(`rdi`)와 반환값(`rax`)만 봐도 "이 시점에 몇 바이트짜리 버퍼가 생기는지/사라지는지"를 바로 알 수 있다.

## 언제 검색해야 하나
- 디스어셈블리에서 `call malloc@plt` 직전 `mov edi, 0x40` 같은 코드를 보고 몇 바이트가 할당되는지 확인하고 싶을 때
- `free`가 두 번 호출되는 것 같아서(double free) 힙 취약점 여부를 의심할 때
- GDB에서 malloc이 반환한 포인터로 실제 청크 헤더(크기, 플래그)를 읽고 싶을 때
- pwntools/CTF 문제에서 "heap" 관련 문제인지 아닌지부터 판단하고 싶을 때

## 핵심 개념
```c
void *malloc(size_t size);
void  free(void *ptr);
```
`malloc`은 SysV x64 호출 규약에 따라 `size`를 `rdi`로 받고, 성공 시 확보한 메모리의 시작 주소를 `rax`로 반환한다. 실패(메모리 부족)하면 `NULL`(0)을 반환한다 — `test rax, rax` / `je fail`로 실패 체크하는 코드가 뒤따르면 malloc 실패 처리로 볼 수 있다.

**요청 크기와 실제 청크 크기는 다르다.** glibc(ptmalloc2)는 사용자가 요청한 `size`에 청크 헤더(8바이트, `size` 필드) 오버헤드를 더하고 최소 청크 크기(x64에서 32바이트) 및 16바이트 정렬 단위로 반올림한다. 예를 들어 `malloc(24)`을 호출해도 실제 청크는 32바이트로 할당되는 경우가 흔하다. `malloc(0)`을 호출하면 크래시 없이 최소 크기 청크에 대한 유효한(그러나 0바이트 사용 가능한) 포인터를 반환한다(glibc 구현 기준, 표준(C11)은 구현 정의로 남겨둠).

**청크 구조 (64비트, 사용 중인 상태)**
```
mem 포인터가 가리키는 곳 = chunk + 0x10
[chunk - 0x10] prev_size (또는 이전 청크의 payload로 재사용)
[chunk - 0x8 ]  size      (하위 3비트는 플래그: PREV_INUSE=1, IS_MMAPPED=2, NON_MAIN_ARENA=4)
[chunk +  0x0]  payload... (malloc이 반환하는 실제 포인터, 여기서부터 시작)
```
즉 `malloc`이 리턴한 포인터에서 **8바이트 앞**을 읽으면 그 청크의 `size` 필드(요청 크기가 아니라 실제 확보된 크기 + 플래그)를 볼 수 있다.

**`free`의 동작**은 glibc 버전에 따라 다르지만, 최신(2.26+) glibc는 작은 청크를 우선 **tcache**(스레드별 캐시, bin당 기본 최대 7개)에 넣는다. tcache가 가득 차면 fastbin(작은 크기) 또는 unsorted bin으로 들어간다. `free(NULL)`은 아무 일도 하지 않고 조용히 반환한다(표준에 명시된 안전한 동작). 이미 해제된 포인터를 다시 `free`하면(double free) glibc 2.29 이상은 tcache 엔트리의 `key` 필드로 같은 청크가 같은 tcache에 이미 있는지 검사해 `free(): double free detected in tcache 2` 같은 에러로 즉시 abort시킨다.

## 화면/코드에서 보이는 징후
- `call malloc@plt` 직전 `mov edi, <상수>`(x64) 또는 `push <상수>`(x86)로 크기 지정
- 반환값(`rax`/`eax`)을 곧바로 다른 포인터 변수에 저장하거나 `test rax, rax` 로 NULL 체크
- `call free@plt` 직전 `mov rdi, [저장해둔 포인터]`
- IDA/Ghidra 디컴파일에서 `v1 = (char *)malloc(0x40);`, `free(v1);` 형태로 그대로 보임

## 가장 먼저 할 것
`malloc` 호출 직전 `rdi`(또는 x86의 스택 최상단 인자)에 들어가는 상수를 확인해 "이 버퍼가 몇 바이트짜리인가"부터 적어둔다. 이후 이 포인터가 어디에 저장되고, 언제 `free`되는지 xref로 추적하면 힙 관련 로직(연결 리스트, 구조체 배열 등)을 빠르게 파악할 수 있다.

## 단계별 절차
1. `objdump -d ./chall | grep -B5 'call.*malloc@plt'` 로 malloc 호출 직전 크기 세팅 코드를 찾는다.
2. GDB에서 `break malloc` 후 `run`, 멈추면 `print/x $rdi`(x64)로 요청 크기 확인.
3. `finish`로 malloc 리턴까지 실행한 뒤 `print/x $rax`로 반환된 포인터 확인.
4. Pwndbg가 있다면 `chunk $rax`로 해당 포인터가 속한 청크의 `size`, `flags`(PREV_INUSE 등)를 사람이 읽기 쉬운 형태로 확인.
5. `break free`, `print/x $rdi`로 어떤 포인터가 해제되는지 확인하고, 같은 포인터가 다시 `free`되는지 반복 실행하며 관찰.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'malloc@plt\|free@plt'
ltrace -e malloc+free ./chall
```
GDB/Pwndbg: `break malloc`, `break free`, `print/x $rdi`, `print/x $rax`, `chunk <addr>`, `heap`, `bins`, `vis`

## 출력 해석
- `chunk` 명령 출력의 `size`는 malloc에 넘긴 값이 아니라 **정렬/오버헤드 반영 후 실제 청크 크기**다. 요청값과 다르다고 당황할 필요 없다.
- `PREV_INUSE` 플래그가 꺼져 있으면 바로 앞 청크가 free 상태라는 뜻이고, 그 경우 `prev_size` 필드가 실제로 유효한 값(병합용)이다.
- `free(): invalid pointer` 에러는 `free`에 넘긴 주소가 malloc이 실제로 반환한 청크 시작 주소가 아닐 때(오프셋이 틀렸거나 스택/전역 주소를 넘겼을 때) 발생한다.

## 흔한 실수
- malloc 반환값을 NULL 체크 없이 바로 역참조하는 코드라고 착각하는 것 — 대부분의 CTF 문제는 malloc 실패를 가정하지 않고 짜여 있어 NULL 체크가 아예 없는 경우가 많다.
- 요청 크기와 실제 청크 크기를 같다고 가정하고 오프셋을 계산하는 것 — 최소 청크 크기(32바이트)와 16바이트 정렬 때문에 어긋난다.
- `free` 이후 포인터를 그대로 다시 쓰는 코드를 발견했는데도 use-after-free가 아니라고 넘기는 것 — free된 포인터(dangling pointer)를 다시 쓰면 그 메모리가 이미 다른 malloc에 재사용됐을 수 있다.

## 막혔을 때 다음 체크
- 크기를 다시 조정하는 `realloc`/`calloc`이 궁금하면 → REV-0627.
- malloc이 실제로 `call printf`처럼 PLT를 거쳐 호출되는 구조가 궁금하면 → REV-0100.
- 힙 관련 함수 호출을 한눈에 로그로 보고 싶으면 → REV-0111(ltrace).

## 미니 예제
```c
char *buf = malloc(0x40);   // rdi=0x40, call malloc@plt, rax=buf
strcpy(buf, "hello");
free(buf);                  // rdi=buf, call free@plt
```
```gdb
(gdb) break malloc
(gdb) run
(gdb) print/x $rdi
$1 = 0x40
(gdb) finish
Value returned is $2 = (void *) 0x5555555592a0
(gdb) chunk 0x5555555592a0
Allocated chunk | PREV_INUSE
Addr: 0x555555559290
Size: 0x50
```
청크 헤더가 `mem` 포인터보다 0x10 앞에 있으므로 `chunk` 명령이 계산해서 보여주는 실제 청크 시작 주소(`0x555555559290`)는 malloc이 반환한 포인터(`0x5555555592a0`)보다 정확히 16바이트 작다.

## 관련 글
- REV-0627 — libc 함수 사전: calloc realloc 계열
- REV-0100 — PLT와 GOT 기초
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0106 — SysV AMD64 Calling Convention

## 출처/검증
- `malloc`/`free` 함수 시그니처와 반환값 규칙: POSIX/ISO C 표준(C11 7.22.3) 및 Linux man-pages `malloc(3)` 기준.
- glibc ptmalloc2 청크 구조(`prev_size`, `size`, PREV_INUSE 비트), tcache double-free 검사(`key` 필드): glibc 소스(`malloc/malloc.c`)의 공개된 구조체 정의 및 다수의 공개 힙 익스플로잇 문서(예: how2heap 프로젝트) 기준 서술.
- Pwndbg `chunk`/`heap`/`bins` 명령: Pwndbg 공식 GitHub 문서 기준.
