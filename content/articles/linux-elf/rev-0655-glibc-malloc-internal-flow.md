---
id: REV-0655
title: "glibc malloc 내부 흐름 개요(청크 헤더 수준)"
slug: "rev-0655-glibc-malloc-internal-flow"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["malloc 내부 구현", "malloc_chunk", "PREV_INUSE", "top chunk", "arena", "청크 헤더"]
aliases: ["malloc_chunk 구조체", "top chunk란", "malloc이 실제로 하는 일", "청크 size 필드 하위 비트"]
symptom_keywords: ["malloc이 정확히 몇 바이트를 할당하는지 모르겠음", "청크 size 필드에 이상한 홀수 값이 보임", "top chunk가 뭔지 모르겠음", "malloc 호출 하나를 어셈블리로 끝까지 따라가고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`malloc(n)` 한 번의 호출은 단순히 "n바이트짜리 메모리를 반환"하는 게 아니라, 요청 크기를 정렬된 청크 크기로 반올림하고, tcache/fastbin/unsorted bin/smallbin/largebin 순으로 재사용 가능한 청크를 뒤진 뒤, 아무것도 못 찾으면 top chunk를 잘라 쓰거나 `brk`/`mmap`으로 커널에서 새 메모리를 받아오는 여러 단계로 이루어진 흐름이며, 이 흐름을 청크 헤더 수준까지 알면 힙 덤프의 숫자들이 왜 그런 값인지 설명할 수 있다.

## 언제 검색해야 하나
- `malloc(24)`를 호출했는데 GDB로 확인한 실제 청크 크기가 24가 아니라 32(0x20)로 나와서 왜 그런지 궁금할 때
- 힙 메모리를 덤프했을 때 `size` 필드처럼 보이는 값이 짝수가 아니라 `0x21`, `0x31`처럼 항상 홀수로 끝나는 이유가 궁금할 때
- "top chunk"라는 용어가 pwndbg `heap` 출력에 나오는데 이게 뭔지 모를 때
- 힙 오버플로우 문제에서 "다음 청크의 size 필드를 덮어썼다"는 설명을 읽었는데 그 size 필드가 정확히 어디 있는지 스스로 계산하고 싶을 때

## 핵심 개념

### malloc_chunk 구조체 — 헤더 두 필드가 핵심
glibc 내부적으로 청크는 대략 다음과 같은 구조체(단순화, 64비트 기준)로 다뤄진다.

```c
struct malloc_chunk {
    size_t prev_size;   /* 이전 청크가 free 상태일 때만 유효(그 청크의 크기) */
    size_t size;        /* 이 청크의 크기 + 하위 3비트 플래그 */
    /* 청크가 in-use일 때: 여기부터 사용자 데이터
       청크가 free일 때:   fd(다음), bk(이전) 포인터가 이 자리에 들어감 */
};
```
`prev_size`와 `size` 각각 8바이트(64비트 기준)이므로 헤더는 총 16바이트다. 다만 실제로 청크가 "사용 중(in-use)"일 때는 `prev_size` 자리를 이전 청크의 데이터 영역으로 재활용할 수 있어, 실질적인 오버헤드는 8바이트(size 필드)만 있는 것처럼 보일 때가 많다. 이것이 "헤더는 16바이트인데 실제 오버헤드는 8바이트"라는 말이 나오는 이유다.

### size 필드의 하위 3비트 — 플래그
`size` 필드는 실제 크기를 담지만, 크기 자체가 항상 16의 배수(정렬 단위)로 관리되기 때문에 하위 몇 비트가 항상 0으로 비어 있다. glibc는 이 여유 비트를 아래 세 가지 플래그로 활용한다.
- `PREV_INUSE` (비트 0, 값 1): 바로 이전 청크가 현재 사용 중(in-use)인지 여부. 이 비트가 1이면 이전 청크는 free 상태가 아니므로 `prev_size` 필드는 무의미하다.
- `IS_MMAPPED` (비트 1, 값 2): 이 청크가 `mmap`으로 별도 할당된 큰 덩어리인지 여부.
- `NON_MAIN_ARENA` (비트 2, 값 4): 이 청크가 메인 arena가 아닌 다른(스레드별) arena에 속하는지 여부.

그래서 힙 덤프에서 `size` 필드가 `0x21`, `0x31`처럼 항상 홀수로 보이는 것은 버그가 아니라 실제 크기(`0x20`, `0x30`)에 `PREV_INUSE` 비트(1)가 항상 켜져 있기 때문이다. 실제 청크 크기를 구하려면 `size & ~0x7` (하위 3비트를 지움) 연산을 해야 한다.

### malloc(n) 호출 시 크기가 반올림되는 이유
사용자가 요청한 `n`바이트에 헤더 오버헤드(보통 8바이트)를 더한 뒤, 최소 청크 크기(64비트 기준 보통 32바이트, `0x20`)보다 작으면 그 최소값으로, 그렇지 않으면 16바이트 단위로 올림한다. 예를 들어 `malloc(24)`를 호출하면 24 + 8(오버헤드) = 32이고 이미 16의 배수이므로 실제 청크 크기는 `0x20`(32바이트)이 된다. `malloc(1)`처럼 아주 작은 요청도 최소 청크 크기인 `0x20`으로 반올림된다. 이 반올림 규칙 때문에 "요청한 크기"와 "실제로 확보되는 청크 크기"가 다를 수 있고, 힙 오버플로우 문제에서 여유 공간(정렬로 남는 패딩)을 이용한 공격이 가능해지는 이유이기도 하다.

### malloc 내부 탐색 순서
`malloc(n)`이 호출되면 대략 다음 순서로 재사용 가능한 청크를 찾는다.
1. 요청 크기가 tcache 대상 범위이고 해당 슬롯에 청크가 있으면 → 즉시 반환 (가장 빠른 경로)
2. tcache에 없고 fastbin 대상 크기이며 해당 fastbin에 청크가 있으면 → fastbin에서 꺼내 반환(이때 남는 여유가 있으면 tcache도 채워 넣는 최적화가 있음)
3. unsorted bin을 순회하며 정확히 맞는 크기가 있으면 즉시 반환, 아니면 순회하면서 smallbin/largebin으로 재분류(sorting)
4. 재분류 후에도 못 찾았고 largebin에서 요청보다 큰 청크를 찾으면 그 청크를 잘라(split) 필요한 만큼만 반환하고 나머지는 다시 bin에 넣음
5. 그래도 못 찾으면 top chunk(힙의 맨 끝, 아직 아무도 안 쓴 영역)를 잘라서 사용
6. top chunk 크기도 부족하면 `sbrk`/`brk` 시스템 콜로 힙을 확장하거나, 요청이 아주 크면(기본 임계값 128KB 이상) `mmap`으로 별도 페이지를 새로 받아옴

### top chunk — 힙의 맨 끝, 아직 나눠주지 않은 영역
top chunk는 현재 힙에서 "아직 어떤 `malloc` 요청에도 할당되지 않은, 맨 끝에 남아있는 하나의 큰 청크"를 가리키는 개념이다. 모든 bin을 다 뒤져도 맞는 크기가 없을 때 최후의 수단으로 이 top chunk를 잘라서 쓴다. top chunk 자체도 크기가 부족해지면 glibc가 커널에 `brk`로 힙을 더 늘려달라고 요청한 뒤 top chunk를 그만큼 키운다. pwndbg `heap` 명령 출력의 마지막 줄에 보통 `top chunk`라는 표시가 함께 나온다.

### arena — 힙 전체를 관리하는 구조체
`main_arena`는 메인 스레드가 사용하는 힙 전체를 관리하는 전역 구조체로, 각 bin(fastbin 배열, unsorted/small/large bin의 이중 연결 리스트 헤드)에 대한 포인터, top chunk 포인터 등을 담고 있다. 멀티스레드 프로그램은 스레드마다 별도의 arena를 가질 수 있어 락 경합 없이 동시에 `malloc`을 호출할 수 있게 되어 있다. pwndbg `bins` 명령이 참조하는 리스트 헤드가 바로 이 arena 구조체 안에 있는 것이다.

## 화면/코드에서 보이는 징후
- GDB에서 힙 메모리를 `x/4gx` 등으로 덤프했을 때 8바이트씩 끊어지는 값들 중 하나가 `0x21`, `0x31`, `0x91`처럼 항상 홀수
- pwndbg `heap` 명령 출력 마지막에 `Top chunk` 항목이 별도로 표시됨
- `malloc` 호출 후 리턴된 포인터에서 정확히 16바이트를 뺀 위치에서 `size` 필드로 보이는 값이 발견됨
- 힙 오버플로우로 다음 청크의 `size` 필드를 조작하는 익스플로잇 코드에서 `PREV_INUSE` 비트를 유지한 채로 값을 계산하는 부분(예: `next_size | 1`)

## 가장 먼저 할 것
분석 중인 청크의 실제 헤더 시작 주소를 먼저 계산한다. `malloc`이 리턴한 포인터(사용자 데이터 시작)에서 64비트 기준 16바이트를 빼면 그 청크의 `prev_size` 필드 위치, 즉 헤더 시작 주소가 나온다. pwndbg에서는 `chunk ADDR` 명령이 이 계산과 필드 해석을 자동으로 해준다.

## 단계별 절차
1. `malloc` 호출 지점에 브레이크포인트를 걸고 `finish`로 리턴값(사용자 포인터) 확보 (REV-0657 참고)
2. 리턴된 포인터에서 16을 뺀 주소를 청크 헤더 시작으로 계산
3. pwndbg `chunk ADDR`로 `size`, `prev_size`, 플래그 비트를 한 번에 확인
4. `size & ~0x7` 계산으로 플래그를 제거한 순수 청크 크기 확인
5. 힙 전체 구조를 보고 싶으면 `heap` 명령으로 모든 청크를 순서대로(주소 오름차순) 나열, 마지막의 top chunk까지 확인
6. 특정 청크가 free된 뒤 어느 bin으로 갔는지 REV-0654 절차대로 `bins` 명령으로 추적

## 명령어/단축키
```gdb
chunk ADDR         # 지정 주소를 malloc_chunk으로 해석해서 필드별 출력
heap                # 힙 전체 청크 목록(top chunk 포함) 순서대로 출력
p/x *(size_t*)(ADDR-8)   # size 필드를 직접 읽는 raw 방법(플래그 포함)
x/4gx ADDR-16       # 헤더 2필드 + 데이터 앞부분을 8바이트씩 4개 원시 덤프
```

## 출력 해석
pwndbg `chunk` 출력 예시:
```
Allocated chunk | PREV_INUSE
Addr: 0x55d1234000
Size: 0x21

fd: 0x0000000000000000
bk: 0x0000000000000000
```
- `Size: 0x21`은 실제 청크 크기 `0x20`(32바이트)에 `PREV_INUSE` 플래그(1)가 켜져 있다는 뜻이다. `Allocated chunk | PREV_INUSE`라는 표시 자체가 "이 청크는 지금 사용 중이고, 이전 청크도 사용 중"이라는 두 정보를 동시에 알려준다.
- 청크가 free 상태라면 같은 명령에서 `fd`/`bk` 필드에 실제 다음/이전 청크 주소(또는 tcache의 경우 `fd`만 사용, 안전 링크가 적용된 glibc 2.32+에서는 이 값이 XOR 인코딩되어 있어 그대로 주소로 읽으면 안 됨)가 채워진다.

`heap` 명령 마지막 줄 예시:
```
Top chunk
Addr: 0x55d1236020
Size: 0x1cfe0
```
힙에서 아직 아무 `malloc`에도 배정되지 않은 나머지 영역이 `0x1cfe0`바이트(약 118KB) 남아있다는 뜻이며, 이후 `malloc` 호출이 bin에서 아무것도 못 찾으면 이 영역에서 잘라 쓰게 된다.

## 흔한 실수
- `size` 필드 값을 그대로 청크 크기라고 착각해서 `PREV_INUSE` 플래그를 안 지우고 계산해 오프셋이 8바이트씩 어긋나는 것.
- `malloc(n)`의 `n`과 실제 청크 크기가 항상 같다고 가정하고 힙 레이아웃을 손으로 계산하다가 정렬 반올림을 놓쳐 오프셋 계산이 틀리는 것.
- glibc 2.32 이상에서 tcache의 `fd` 포인터가 안전 링크(safe-linking)로 인코딩되어 있다는 것을 모르고 그냥 원시 주소로 읽어버리는 것 — 이 경우 `fd XOR (해당 청크 주소 >> 12)` 식의 디코딩이 필요하다.
- top chunk를 "그냥 빈 메모리"로 여기고 무시하는 것 — 실제로는 여전히 유효한 청크 헤더(size 필드 포함)를 갖고 있어 이 헤더를 덮어쓰는 것도 유효한 공격 표면(House of Force 계열 등)이 된다.
- 멀티스레드 프로그램에서 `main_arena`만 보고 분석하다가, 실제로 문제의 `malloc`/`free`가 다른 스레드의 별도 arena에서 일어나고 있다는 것을 놓치는 것.

## 막혔을 때 다음 체크
- 청크가 어느 bin(tcache/fastbin/unsorted/small/large)에 들어가는지 리스트 구조 자체가 헷갈리면 → REV-0654 tcache와 fastbin 등 glibc 힙 구조 개요(리버싱 관점)
- glibc 버전별로 정확한 구조체 필드 오프셋을 표로 확인하고 싶으면 → REV-0644 glibc 버전별 malloc 구조 요약표
- `malloc`/`free` 호출 자체의 인자/반환값을 GDB로 보는 기본기가 부족하면 → REV-0626 libc 함수 사전: malloc free 계열, REV-0657 GDB에서 함수 반환값을 finish로 확인하는 법
- 힙 상태를 명령 하나로 시각적으로 보고 싶으면 → REV-0659 Pwndbg에서 힙 상태를 시각화해서 보는 법
- 메모리 안의 특정 패턴(예: 특정 힙 주소가 박혀있는 곳)을 찾고 싶으면 → REV-0660 Pwndbg search로 메모리에서 패턴 찾기

## 미니 예제
```c
// chall.c
#include <stdlib.h>
int main() {
    char *p = malloc(24);   // 요청 24바이트
    return 0;
}
```
```gdb
(gdb) break *(main+20)   # malloc 호출 리턴 직후 지점(예시)
(gdb) run
(gdb) p/x $rax
$1 = 0x555555559010      # malloc이 리턴한 사용자 데이터 포인터

(gdb) p/x *(size_t*)($rax - 8)
$2 = 0x21                 # size 필드: 실제 크기 0x20 + PREV_INUSE(1)

(gdb) chunk 0x555555559010-16
Allocated chunk | PREV_INUSE
Addr: 0x555555559000
Size: 0x21
```
요청은 24바이트였지만 실제 청크 크기는 `0x20`(32바이트)이고, 그 위에 `PREV_INUSE` 플래그가 얹혀 `size` 필드는 `0x21`로 보인다는 것을 직접 확인했다.

## 관련 글
- REV-0654 — tcache와 fastbin 등 glibc 힙 구조 개요(리버싱 관점)
- REV-0644 — glibc 버전별 malloc 구조 요약표
- REV-0626 — libc 함수 사전: malloc free 계열
- REV-0657 — GDB에서 함수 반환값을 finish로 확인하는 법
- REV-0659 — Pwndbg에서 힙 상태를 시각화해서 보는 법
- REV-0660 — Pwndbg search로 메모리에서 패턴 찾기

## 출처/검증
- `malloc_chunk` 구조체 필드(`prev_size`, `size`, `fd`, `bk`)와 `PREV_INUSE`/`IS_MMAPPED`/`NON_MAIN_ARENA` 플래그 비트: glibc 소스코드(`malloc/malloc.c`) 정의 기준.
- top chunk 개념과 `brk`/`mmap` 확장 임계값(기본 128KB, `mmap_threshold`): glibc 공식 문서 및 소스코드 주석 기준.
- safe-linking(tcache `fd` XOR 인코딩)이 glibc 2.32부터 적용된 사실: glibc NEWS 릴리스 노트 기준.
- pwndbg `chunk`/`heap` 명령 출력 형식: pwndbg 공식 문서 및 실사용 예시 기준 (2026-09-09 검증).
