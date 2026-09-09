---
id: REV-0644
title: "glibc 버전별 malloc 구조 요약표"
slug: "rev-0644-glibc-malloc-struct-by-version"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["malloc_chunk", "tcache", "tcache_entry", "fastbin", "safe-linking", "glibc malloc", "힙 청크 구조"]
aliases: ["malloc_chunk 구조체", "tcache_entry 구조체", "glibc malloc 버전 차이", "safe linking이란", "힙 청크 필드"]
symptom_keywords: ["glibc 버전마다 힙 구조가 다름", "tcache가 없는 바이너리", "fd 포인터 값이 이상하게 XOR된 것 같음", "malloc_chunk 필드 이름을 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
glibc의 힙 청크 기본 구조(`malloc_chunk`)는 오랫동안 거의 그대로지만, tcache 도입(2.26), tcache 이중 해제 탐지(2.29), 각종 무결성 검사 강화(2.30~), safe-linking(2.32) 등 버전별로 **보호 메커니즘**이 계속 추가되어 왔기 때문에 "이 glibc 버전에서 무엇이 가능하고 무엇이 막히는지"를 아는 것이 힙 관련 리버싱/pwn 문제 접근의 출발점이다.

## 언제 검색해야 하나
- `pwndbg`의 `bins`/`heap` 결과에서 `fd` 값이 예상과 다르게(포인터 같지 않은 이상한 값으로) 보일 때
- 대상 바이너리의 glibc 버전을 확인했는데, 그 버전에서 tcache가 있는지 없는지 헷갈릴 때
- write-up에서 "safe-linking 때문에 fd를 그냥 덮어쓸 수 없다"는 설명이 이해가 안 될 때

## 핵심 개념

### malloc_chunk 구조체 (공통 기본형)
```c
struct malloc_chunk {
    INTERNAL_SIZE_T mchunk_prev_size;  // 이전 청크가 free 상태일 때만 유효한, 이전 청크 크기
    INTERNAL_SIZE_T mchunk_size;       // 이 청크의 크기 + 하위 3비트 플래그
    struct malloc_chunk* fd;           // free 상태일 때: 다음 free 청크 (같은 bin 내)
    struct malloc_chunk* bk;           // free 상태일 때: 이전 free 청크 (같은 bin 내)
    struct malloc_chunk* fd_nextsize;  // largebin 전용: 다음으로 큰 크기의 청크
    struct malloc_chunk* bk_nextsize;  // largebin 전용: 다음으로 작은 크기의 청크
};
```
`mchunk_size`의 하위 3비트는 크기 정보가 아니라 플래그다: `PREV_INUSE`(bit0, 직전 청크가 사용 중인지), `IS_MMAPPED`(bit1, `mmap`으로 별도 할당됐는지), `NON_MAIN_ARENA`(bit2, 메인 arena가 아닌 스레드별 arena 소속인지). 실제 사용 가능 크기를 구하려면 `mchunk_size & ~0x7`로 하위 3비트를 마스킹해야 한다. `fd`/`bk`/`fd_nextsize`/`bk_nextsize`는 청크가 **할당된 상태에서는 사용자 데이터 영역**으로 쓰이고, **free된 상태에서만** 링크드리스트 포인터로 재사용된다(오버레이 구조).

### tcache_entry 구조체 (glibc 2.26+)
```c
typedef struct tcache_entry {
    struct tcache_entry *next;
    struct tcache_perthread_struct *key;   // 2.29+ : 이중 해제 탐지용
} tcache_entry;
```
`tcache_perthread_struct`는 스레드별로 하나씩 존재하며, 크기별로 최대 64개 bin(각 bin은 기본 최대 7개 청크까지 캐시)을 갖는다. tcache는 `malloc`/`free`의 가장 빠른 캐시 경로로, fastbin보다도 먼저 확인된다.

### 버전별 주요 변경점

| glibc 버전 | 연도 | 변경점 |
|---|---|---|
| 2.25 이하 | ~2017 | tcache 없음. fastbin/unsortedbin/smallbin/largebin만 존재. fastbin 이중 해제 탐지가 약해서 고전적인 fastbin dup 공격이 비교적 쉬움 |
| **2.26** | 2017 | **tcache 도입.** 스레드별 캐시로 `malloc`/`free` 성능 향상, 하지만 초기에는 이중 해제 검사가 없어 tcache dup 공격이 매우 쉬웠음 |
| **2.29** | 2019 | tcache에 `key` 필드 추가 — `free()` 시 해당 청크가 이미 tcache에 있는지 `key` 값으로 검사해 **"double free detected in tcache 2"** 에러로 이중 해제를 탐지 |
| 2.30 | 2019 | `malloc`/`free` 경로에 청크 크기 정합성 검사 등 각종 sanity check 강화(`free(): invalid size` 등 에러 메시지 다수 추가) |
| **2.32** | 2020 | **safe-linking 도입.** fastbin/tcache의 `fd` 포인터를 그냥 저장하지 않고, `PROTECT_PTR` 매크로로 `(청크 자신의 주소 >> 12) XOR 원래_fd값` 형태로 **난독화**해서 저장. 힙 주소 일부를 모르면 `fd`를 임의 값으로 덮어써도 유효한 포인터를 만들기 어려워짐 |
| **2.34** | 2021 | libpthread/libdl/libutil이 libc.so로 통합(malloc 자체 로직 변경은 아니지만 스레드 arena 관련 심볼 위치가 바뀜) |
| 2.35~ | 2022+ | 지속적인 하드닝 패치(추가 sanity check 등), 큰 구조 변화는 없음 |

### safe-linking 계산식
```c
#define PROTECT_PTR(pos, ptr) \
    ((__typeof(ptr))((((size_t)pos) >> 12) ^ ((size_t)ptr)))
```
저장된 `fd` 값을 실제 포인터로 복원하려면 `(청크_주소 >> 12) XOR 저장된_fd값`을 계산해야 한다. Pwndbg는 이 계산을 `bins`/`heap` 출력에서 자동으로 해서 보여준다.

## 화면/코드에서 보이는 징후
- Pwndbg `bins` 출력에서 tcache 항목 자체가 안 보이면 → glibc 2.26 미만일 가능성
- `free()` 중 프로그램이 `*** stack smashing detected ***`가 아니라 `double free or corruption`, `free(): invalid pointer`, `malloc(): unaligned tcache chunk detected` 같은 glibc 자체 abort 메시지로 죽으면 → 해당 버전의 sanity check에 걸린 것
- `fd` 값이 힙 주소치고 이상하게 큰/이해 안 되는 값이면 → safe-linking으로 XOR된 값일 가능성(2.32+)

## 가장 먼저 할 것
대상 바이너리와 함께 배포된 `libc.so.6`(또는 시스템 libc)의 버전을 먼저 확인한다.
```bash
./libc.so.6 --version
strings ./libc.so.6 | grep -i 'GNU C Library'
```

## 단계별 절차

**1) glibc 버전 확인**
```bash
strings ./libc.so.6 | grep 'GNU C Library) stable release version'
```

**2) 해당 버전에서 tcache 유무 판단**
2.26 미만이면 tcache 없음(fastbin/unsortedbin 위주 분석), 2.26 이상이면 tcache부터 확인.

**3) Pwndbg로 실제 구조 확인**
```gdb
heap
bins
malloc_chunk <청크주소>
```

**4) safe-linking 여부 확인(2.32+ 의심 시)**
`fd` 원본 값을 XOR로 복원해야 하는지 Pwndbg `bins` 출력의 자동 복원값과 raw 메모리 값을 비교해본다.
```gdb
x/2gx <청크주소>
bins
```

## 명령어/단축키
```bash
strings ./libc.so.6 | grep 'GNU C Library'
./libc.so.6 --version
```
GDB/Pwndbg: `heap`, `bins`, `tcachebins`, `fastbins`, `malloc_chunk <addr>`, `p/x *(struct malloc_chunk*)<addr>`

## 출력 해석
```
$ ./libc.so.6 --version
GNU C Library (Ubuntu GLIBC 2.35-0ubuntu3.8) stable release version 2.35.
```
`2.35`이므로 tcache 있음(2.26+), tcache 이중 해제 탐지 있음(2.29+), safe-linking 적용됨(2.32+)임을 바로 유추할 수 있다.

## 흔한 실수
- 대상 바이너리가 어떤 glibc와 함께 배포됐는지 확인하지 않고, 자기 로컬 시스템의 glibc 버전 지식으로 공격 기법을 그대로 적용하려는 것 — CTF에서는 문제 배포 파일에 포함된 `libc.so.6`을 반드시 따로 확인해야 한다.
- safe-linking을 모르고 `fd`를 그냥 원하는 주소로 덮어써서 왜 안 되는지 헤매는 것 — 2.32+에서는 반드시 XOR 마스킹 계산이 필요하다.
- fastbin/tcache 이중 해제가 예전 write-up처럼 항상 조용히 성공할 거라 기대하는 것 — 최신 glibc는 `free()` 시점에 여러 검사를 추가해서 예전 기법이 그대로 안 통하는 경우가 많다.

## 막혔을 때 다음 체크
- Pwndbg로 힙 상태를 실제로 확인하는 명령이 궁금하면 → REV-0643 Pwndbg 명령어 심화 치트시트(heap/got/plt).
- glibc 버전에 따른 함수 시그니처/심볼 차이 자체가 궁금하면 → REV-0648 glibc 버전별 함수 시그니처 차이 확인법(예정).
- musl libc처럼 아예 다른 malloc 구현과의 차이가 궁금하면 → REV-0647 musl libc와 glibc 차이가 리버싱에 미치는 영향(예정).

## 미니 예제
```gdb
pwndbg> malloc_chunk 0x555555559290
Allocated chunk | PREV_INUSE
Addr: 0x555555559290
Size: 0x21 (0x20 usable, PREV_INUSE 플래그 켜짐)
```
`Size: 0x21`에서 최하위 비트 `1`이 `PREV_INUSE` 플래그이고, 실제 사용 가능 크기는 `0x21 & ~0x7 = 0x20`이다.

## 관련 글
- REV-0643 — Pwndbg 명령어 심화 치트시트(heap/got/plt)
- REV-0638 — libc 함수 사전: pthread_create 기초
- REV-0096 — checksec 결과 읽는 법

## 출처/검증
- `malloc_chunk`/`tcache_entry`/`tcache_perthread_struct` 필드 구성 및 `PREV_INUSE`/`IS_MMAPPED`/`NON_MAIN_ARENA` 플래그: glibc 소스 `malloc/malloc.c` 구조체 정의 기준.
- tcache 도입(2.26), tcache key 이중 해제 탐지(2.29), safe-linking `PROTECT_PTR` 매크로 도입(2.32), libpthread 통합(2.34): 각 해당 glibc 버전의 공식 NEWS 파일 및 릴리스 노트 기준 (2026-09-08 검증).
