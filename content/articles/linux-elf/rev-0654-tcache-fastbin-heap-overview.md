---
id: REV-0654
title: "tcache와 fastbin 등 glibc 힙 구조 개요(리버싱 관점)"
slug: "rev-0654-tcache-fastbin-heap-overview"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["tcache", "fastbin", "smallbin", "largebin", "unsorted bin", "glibc heap", "힙 구조"]
aliases: ["tcache란", "fastbin이란", "glibc bin 종류", "힙 청크가 어느 bin에 들어가는지"]
symptom_keywords: ["free된 청크가 tcache로 들어갔다는 게 무슨 뜻인지 모르겠음", "pwndbg heap 출력에 tcachebins fastbins가 나옴", "malloc 크기별로 청크가 다른 리스트에 들어간다는데 기준을 모르겠음", "double free가 tcache에서 왜 문제가 되는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
glibc의 `malloc`/`free`는 해제된 메모리 조각(청크)을 크기별로 여러 개의 연결 리스트(bin)에 나눠 보관해두었다가 다음 `malloc` 요청 때 재활용하는데, 이 리스트들이 tcache, fastbin, unsorted bin, smallbin, largebin이며, 리버싱/pwn 관점에서는 "이 청크가 지금 어느 bin에 있고, 그 bin이 어떤 연결 방식(단일/이중 연결)을 쓰는지"를 아는 것이 힙 취약점을 읽는 출발점이다.

## 언제 검색해야 하나
- pwndbg의 `bins`, `heap`, `tcache` 명령 출력에 나오는 `tcachebins`, `fastbins`, `unsortedbin`, `smallbins`, `largebins` 항목들이 각각 뭘 뜻하는지 모를 때
- CTF pwn 문제 writeup에서 "tcache poisoning", "fastbin dup", "unlink" 같은 용어가 나오는데 그 전에 기본 힙 구조 자체가 헷갈릴 때
- `free()`를 호출한 뒤 청크가 어느 리스트로 들어가는지 크기 기준으로 예측하고 싶을 때
- 힙 취약점 문제를 처음 접해서 "청크(chunk)"와 "bin"이라는 용어부터 정리하고 싶을 때

## 핵심 개념

### 청크(chunk) — 힙 메모리의 기본 단위
glibc `malloc`이 관리하는 힙 메모리는 "청크"라는 단위로 쪼개진다. 사용자가 `malloc(24)`를 호출하면 실제로는 요청 크기에 8~16바이트 정도의 헤더(그리고 정렬을 위한 패딩)를 더한 크기의 청크가 하나 만들어진다. 각 청크는 대략 다음 구조를 가진다(64비트 기준, 필드 크기는 8바이트씩).

```
청크 헤더:
  prev_size (또는 이전 청크가 free일 때만 유효)
  size      | 하위 3비트는 플래그(PREV_INUSE 등), 나머지가 실제 크기
사용자 데이터 영역 (malloc이 리턴하는 포인터가 가리키는 곳)
```

`malloc(24)`가 리턴하는 포인터는 청크 시작 주소가 아니라 헤더 다음(데이터 영역 시작) 주소다. 즉 GDB에서 `p (void*)$rax`로 받은 포인터에서 16바이트(64비트 기준 헤더 크기)를 빼면 청크 헤더 시작 주소가 나온다. 청크가 **해제(free)되면** 사용자 데이터 영역의 앞부분이 리스트 연결을 위한 포인터로 재활용된다 — 이게 바로 tcache/fastbin 등의 "다음 청크" 포인터가 저장되는 자리다. glibc 버전별 정확한 구조체 필드는 REV-0644에서 표로 정리되어 있다.

### tcache — 스레드별 캐시, 가장 먼저 확인되는 곳
tcache(thread-local cache)는 glibc 2.26부터 도입된 가장 최근/가장 빠른 재활용 경로다. 스레드마다 독립적으로 존재하며, 크기별로 최대 64개(기본값)까지 최근 해제된 청크를 **단일 연결 리스트(singly linked list, LIFO)** 로 보관한다. `free(ptr)`가 호출되면 glibc는 먼저 "이 크기의 tcache 슬롯이 아직 꽉 안 찼는가"를 확인하고, 여유가 있으면 그냥 tcache에 넣고 끝낸다 — fastbin이나 다른 bin 로직까지 갈 필요가 없다. 반대로 `malloc`이 호출되면 요청 크기에 맞는 tcache 슬롯에 청크가 있는지부터 확인하고, 있으면 그 청크를 즉시 재사용한다. tcache는 검사(무결성 체크)가 상대적으로 느슨했던 시절이 있어서(이후 버전에서 double-free 감지가 추가됨) CTF에서 가장 많이 등장하는 공격 대상이다.

### fastbin — 작은 크기 전용 단일 연결 리스트
tcache가 도입되기 전부터 있던 구조로, 아주 작은 크기(64비트 기준 보통 32~128바이트대) 청크를 위한 단일 연결 리스트다. tcache가 꽉 찼거나(64개 초과) tcache 자체가 없는 오래된 glibc 환경에서는 이 fastbin이 1차 재활용 경로가 된다. fastbin에 들어간 청크는 인접 청크와 병합(coalescing)되지 않는다 — 이는 성능을 위한 설계이며, 그 대신 "fastbin에 들어간 채로도 헤더의 PREV_INUSE 플래그는 계속 켜진 것처럼 남는다"는 특징이 있다.

### unsorted bin — 정리되기 전 임시 대기소
fastbin/tcache 크기가 아닌 청크가 `free`되면 일단 unsorted bin이라는 **이중 연결 리스트(doubly linked list)** 에 들어간다. 이후 `malloc`이 호출될 때 unsorted bin을 훑으면서 "요청 크기와 정확히 맞으면 바로 재사용, 안 맞으면 크기에 맞는 smallbin/largebin으로 재분류(sorting)"하는 작업이 일어난다. 즉 unsorted bin은 영구적인 저장소가 아니라 "분류 대기 중" 상태에 가깝다.

### smallbin / largebin — 크기별로 정리된 이중 연결 리스트
- smallbin: 특정 고정 크기 구간(작은 크기)마다 하나씩 존재하는 이중 연결 리스트. 같은 smallbin 안의 청크는 모두 같은 크기다.
- largebin: 더 큰 크기 구간을 담당하며, 하나의 largebin 안에도 서로 다른 크기의 청크가 섞여 들어갈 수 있어 크기 내림차순으로 정렬되어 관리된다.

이 두 bin은 fastbin/tcache와 달리 인접한 free 청크와 자동으로 병합(coalescing)되어 단편화(fragmentation)를 줄인다.

### 어느 bin에 들어가는지 결정하는 기준 — 오직 크기
사용자가 어떤 데이터를 넣었는지는 전혀 상관없고, 오직 **청크의 크기**만으로 어느 bin에 들어갈지 결정된다. 대략적인 감(정확한 임계값은 glibc 버전에 따라 미세하게 다를 수 있으므로 실제 분석 시에는 pwndbg의 `bins`/`tcache` 명령으로 실제 값을 확인해야 한다):
- tcache 대상 크기이면서 아직 슬롯 여유가 있으면 → tcache
- tcache 슬롯이 가득 찼거나 tcache 대상이 아니고, 아주 작은 크기이면 → fastbin
- fastbin 대상보다 크면 → 일단 unsorted bin에 들어갔다가 다음 malloc 때 재분류되어 → smallbin 또는 largebin

### 왜 리버서가 이걸 알아야 하는가
힙 문제(use-after-free, double free, heap overflow)를 분석할 때 "지금 이 포인터가 가리키는 청크가 어느 bin에 연결되어 있는가"를 알아야 다음에 벌어질 일을 예측할 수 있다. 예를 들어 tcache에 들어간 청크는 다음 `malloc(같은 크기)` 호출 때 바로 튀어나오므로, 공격자가 free된 청크의 "다음 포인터" 필드를 조작해두면(tcache poisoning) 다음 `malloc`이 임의 주소를 리턴하게 만드는 것이 가능해진다. 이런 공격 기법 자체를 깊게 다루는 것은 이 글의 범위가 아니지만, 최소한 "지금 어느 bin에 있고 그 bin의 연결 방식이 무엇인지"를 pwndbg로 읽어낼 수 있어야 그 다음 단계(익스플로잇 writeup 이해, 취약점 재현)로 넘어갈 수 있다.

## 화면/코드에서 보이는 징후
- pwndbg에서 `bins` 또는 `tcache`, `fastbins` 명령을 쳤을 때 크기별로 청크 주소가 화살표(`->`)로 이어진 리스트가 출력됨
- 소스 코드나 디스어셈블에서 `malloc`/`free` 호출이 반복되는 루프, 특히 같은 크기로 여러 번 `malloc` 후 `free`하는 패턴이 보임
- GDB에서 힙 메모리를 덤프했을 때 `free`된 청크의 데이터 영역 앞부분에 다른 힙 주소처럼 보이는 8바이트 값이 들어있음(이것이 bin의 연결 포인터)

## 가장 먼저 할 것
분석 중인 바이너리의 정확한 glibc 버전을 `strings ./libc.so.6 | grep "GLIBC_2\."` 또는 `strings ./chall | grep "GNU C Library"`로 먼저 확인한다. tcache 유무(2.26 기준), 안전 링크(safe-linking, 2.32+)와 double-free 검사 강화 등은 버전에 따라 동작이 달라지므로, "지금 내가 보는 이 glibc가 어떤 방어를 갖고 있는지"부터 확정해야 이후 bin 동작을 정확히 예측할 수 있다.

## 단계별 절차
1. `checksec --file=./chall`로 이 바이너리가 어떤 libc를 링크하는지, PIE/RELRO 여부 확인
2. glibc 버전 확인: `strings ./libc.so.6 | grep "GNU C Library"`
3. GDB + pwndbg로 프로세스 실행 후 `malloc`/`free`가 호출되는 지점에 브레이크포인트
4. `free` 호출 직후 `bins` 명령으로 방금 해제된 청크가 tcache에 들어갔는지 fastbin에 들어갔는지 확인
5. `malloc` 호출 직전에 다시 `bins`로 어느 bin에서 청크가 튀어나올지 예측하고, `finish`로 실제 리턴값과 비교해 검증
6. 힙 전체 레이아웃을 한눈에 보고 싶으면 `heap` 명령으로 청크 목록을 순서대로 출력

## 명령어/단축키
```gdb
heap                 # 전체 힙 청크 목록(주소, 크기, 상태)
bins                 # tcache/fastbin/unsorted/small/large bin 전체 요약
tcache               # tcache 슬롯만 상세 출력
fastbins             # fastbin 슬롯만 상세 출력
smallbins            # smallbin 슬롯만 상세 출력
largebins            # largebin 슬롯만 상세 출력
chunk ADDR           # 특정 주소를 청크 헤더로 해석해서 필드 출력
```

## 출력 해석
pwndbg `bins` 출력 예시:
```
tcachebins
0x20 [  2]: 0x55d1234 —▸ 0x55d1256 ◂— 0x0
fastbins
0x20: 0x0
0x30: 0x0
unsortedbin
all: 0x55d12a0 —▸ 0x7f8a1c2b3ce0 (main_arena+96) ◂— 0x55d12a0
smallbins
empty
largebins
empty
```
- `tcachebins` 아래 `0x20 [ 2]`는 "크기 0x20짜리 tcache 슬롯에 청크 2개가 들어있다"는 뜻이고, 그 뒤 `0x55d1234 —▸ 0x55d1256 ◂— 0x0`은 단일 연결 리스트로 첫 번째 청크가 두 번째 청크를 가리키고, 두 번째는 `0x0`(리스트 끝)을 가리킨다는 뜻이다.
- `fastbins`가 전부 `0x0`이면 현재 fastbin에는 아무 청크도 없다는 뜻 — 아직 tcache가 다 못 받은 상황이 아니면 정상이다.
- `unsortedbin`의 `all: 0x55d12a0 —▸ main_arena+96`은 청크 하나가 unsorted bin에 있고, 그 청크의 다음/이전 포인터가 결국 `main_arena`(전역 힙 관리 구조체) 안의 리스트 헤드를 가리켜 리스트가 끝난다는 뜻이다. `main_arena` 주소가 보인다는 것 자체가 "여기서 리스트가 끝난다"는 표시로 해석하면 된다.

## 흔한 실수
- tcache와 fastbin을 같은 것으로 착각해서, glibc 2.26 이후 환경에서 fastbin 관련 writeup을 그대로 적용하려다 안 맞는 것 — 최신 glibc는 작은 크기 청크가 tcache로 먼저 빠지므로 fastbin이 거의 비어 있는 경우가 많다.
- 청크의 "다음 포인터"가 저장되는 위치를 사용자 데이터 영역 맨 앞이라는 것을 모르고, `malloc`이 리턴한 포인터에 바로 값을 쓰면 다음 재사용 시 리스트가 깨진다는 사실을 놓치는 것.
- unsorted bin에 청크가 있다는 것을 "메모리 누수(leak)"라고 착각하는 것 — 이는 정상적인 재활용 대기 상태다.
- smallbin/largebin이 인접 청크와 병합(coalescing)된다는 것을 모르고, free 순서만 보고 청크 개수를 잘못 세는 것.
- glibc 버전 확인 없이 인터넷에서 본 오래된(또는 너무 최신) writeup의 bin 임계값을 그대로 적용하는 것 — 정확한 값은 항상 pwndbg로 그 자리에서 확인해야 한다.

## 막혔을 때 다음 체크
- 청크 헤더 필드 하나하나(size, prev_size, PREV_INUSE 비트)를 자세히 알고 싶으면 → REV-0655 glibc malloc 내부 흐름 개요(청크 헤더 수준)
- 정확한 구조체 오프셋이 glibc 버전마다 어떻게 다른지 표로 보고 싶으면 → REV-0644 glibc 버전별 malloc 구조 요약표
- 힙 상태를 pwndbg로 시각적으로 더 편하게 보는 팁이 필요하면 → REV-0659 Pwndbg에서 힙 상태를 시각화해서 보는 법
- Pwndbg 자체의 heap/got/plt 관련 심화 명령이 궁금하면 → REV-0643 Pwndbg 명령어 심화 치트시트(heap/got/plt)
- 정적 링킹 바이너리라 내장된 malloc을 찾아야 하는 상황이면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법

## 미니 예제
```c
// chall.c
#include <stdlib.h>
int main() {
    char *a = malloc(0x18);   // 요청 0x18 -> 실제 청크 크기 0x20 (헤더 포함, 정렬)
    char *b = malloc(0x18);
    free(a);
    free(b);
    char *c = malloc(0x18);   // b가 tcache에서 재사용될 가능성이 높음
    return 0;
}
```
```gdb
(gdb) break *(main+40)   # free(b) 직후 지점 예시
(gdb) run
(gdb) bins
tcachebins
0x20 [  2]: 0x55...a10 —▸ 0x55...a30 ◂— 0x0
(gdb) next   # malloc(0x18) 호출 지나감
(gdb) p/x $rax
$1 = 0x55...a30   # 방금 tcache 리스트의 첫 번째(가장 최근에 free된 b)가 그대로 재사용됨
```
tcache는 LIFO(마지막에 넣은 것을 먼저 꺼냄)이므로, 나중에 `free`한 `b`가 다음 `malloc`에서 먼저 재사용되는 것을 확인할 수 있다.

## 관련 글
- REV-0655 — glibc malloc 내부 흐름 개요(청크 헤더 수준)
- REV-0644 — glibc 버전별 malloc 구조 요약표
- REV-0659 — Pwndbg에서 힙 상태를 시각화해서 보는 법
- REV-0643 — Pwndbg 명령어 심화 치트시트(heap/got/plt)
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0626 — libc 함수 사전: malloc free 계열

## 출처/검증
- tcache/fastbin/unsorted bin/smallbin/largebin 구조와 재활용 순서: glibc 소스코드(`malloc/malloc.c`) 주석 및 공식 glibc 문서 기준.
- tcache가 glibc 2.26부터 도입되었고 safe-linking이 2.32부터 추가된 시점: glibc NEWS 파일(릴리스 노트) 기준.
- pwndbg `bins`/`heap`/`tcache`/`fastbins` 명령 출력 형식: pwndbg 공식 문서 및 실제 사용 예시 기준 (2026-09-09 검증).
