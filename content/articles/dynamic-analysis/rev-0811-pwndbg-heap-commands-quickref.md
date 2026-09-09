---
id: REV-0811
title: "Pwndbg 힙 명령 빠른 참조(bins, chunk 등)"
slug: "rev-0811-pwndbg-heap-commands-quickref"
category: "dynamic-analysis"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pwndbg heap", "pwndbg bins", "pwndbg malloc_chunk", "pwndbg vis_heap_chunks", "pwndbg tcachebins", "pwndbg find_fake_fast"]
aliases: ["pwndbg 힙 명령어 모음", "pwndbg bins 명령", "pwndbg heap 시각화 명령", "pwndbg tcache 확인"]
symptom_keywords: ["pwndbg 힙 명령어가 뭐가 있는지 모름", "pwndbg에서 tcache 상태 확인하고싶음", "pwndbg 청크 하나만 자세히 보고싶음", "pwndbg top chunk가 뭔지 모름", "pwndbg free 시뮬레이션 하고싶음"]
source_ids: ["SRC-PWNDBG-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Pwndbg는 glibc의 tcache/fastbin/smallbin/largebin/unsortedbin 구조를 직접 파싱해서 사람이 읽기 좋은 형태로 보여주는 전용 힙 명령어 세트(`bins`, `heap`, `malloc_chunk`, `vis_heap_chunks` 등)를 제공하며, 이 명령들만으로 힙 익스플로잇에 필요한 상태 파악의 대부분을 끝낼 수 있다.

## 언제 검색해야 하나
- 힙 익스플로잇 문제를 풀다가 지금 어떤 청크가 어느 bin에 들어있는지 한눈에 보고 싶을 때
- 특정 주소가 청크의 시작인지, 그 청크의 크기/플래그가 뭔지 확인하고 싶을 때
- 힙 전체 레이아웃을 그림처럼 보고 싶을 때
- `free()`를 호출하면 어떤 일이 벌어질지 실제로 실행하지 않고 미리 확인하고 싶을 때
- Use-After-Free/Double-Free 공격에서 가짜 청크(fake chunk)를 만들 위치를 찾고 싶을 때

## 핵심 개념

### 힙 명령어 표
| 명령 | 하는 일 |
|---|---|
| `bins` | 현재 arena의 모든 bin(tcache 포함)을 한 번에 요약해서 보여줌 — 가장 먼저 쳐볼 명령 |
| `heap` | 현재 힙의 청크들을 처음부터 끝까지 순서대로 나열 |
| `malloc_chunk ADDR` (`mc`) | 지정한 주소를 하나의 청크로 해석해서 상세 정보(size, flags, fd/bk 등) 출력 |
| `hi ADDR` | ADDR이 어떤 청크에 속하는지 힙 전체를 검색해서 알려줌(청크 시작 주소를 모를 때) |
| `fastbins` | fastbin만 따로 출력 |
| `tcachebins` | tcache만 따로 출력 |
| `smallbins` | smallbin만 따로 출력 |
| `largebins` | largebin만 따로 출력 |
| `unsortedbin` | unsorted bin만 따로 출력 |
| `tcache` | 현재 스레드의 tcache 구조체 내용 출력 |
| `top_chunk` | 현재 arena의 top chunk(아직 할당되지 않은 힙 끝부분) 정보 출력 |
| `vis_heap_chunks` (`vis`) | 힙 전체를 청크 단위로 시각화해서 한 화면에 그려줌 |
| `find_fake_fast ADDR` | ADDR을 헤더로 갖는 위조 가능한 fastbin/tcache 청크 후보를 탐색(fastbin dup류 공격용) |
| `try_free ADDR` | ADDR에 대해 실제로 `free()`를 호출하지 않고 그 결과(에러 여부 등)만 시뮬레이션 |
| `mp` | glibc `mp_`(malloc parameters) 구조체 내용 출력 |

### 이 명령들이 참조하는 arena/스레드
`bins`, `fastbins`, `tcache` 등은 기본적으로 **현재 스레드가 사용 중인 arena**를 기준으로 출력한다. 멀티스레드 프로그램에서 다른 스레드의 힙 상태를 보려면 먼저 그 스레드로 컨텍스트를 전환(`thread N`)한 뒤 같은 명령을 다시 실행해야 한다.

### 실전 워크플로
전형적인 흐름은: `bins`로 전체 상태 스냅샷 확인 → 의심스러운 청크가 있으면 `malloc_chunk ADDR`로 그 청크만 자세히 확인 → 힙 전체 구조가 헷갈리면 `vis_heap_chunks`로 그림처럼 확인 → 공격을 준비 중이면 `find_fake_fast`나 `try_free`로 사전 검증.

## 화면/코드에서 보이는 징후
GDB 프롬프트에서 Pwndbg가 로드된 상태에서 직접 입력하는 명령들이며, 힙 관련 버그(UAF, Double Free, 힙 오버플로우)를 다루는 CTF pwn 문제나 glibc 내부 구조를 학습할 때 자주 쓰인다.

## 가장 먼저 할 것
힙 상태가 궁금하면 아무 인자 없이 `bins`부터 쳐본다. 이 한 명령이 tcache/fastbin/unsorted/small/large bin을 모두 요약해서 보여주므로 대부분의 상황에서 출발점이 된다.

## 단계별 절차

**1) 전체 bin 상태 한 번에 보기**
```
pwndbg> bins
```

**2) 특정 청크 자세히 보기**
```
pwndbg> malloc_chunk 0x555555559290
```

**3) 주소가 어느 청크에 속하는지 모를 때**
```
pwndbg> hi 0x5555555592a8
```

**4) 힙 전체를 그림으로 보기**
```
pwndbg> vis_heap_chunks
```

**5) free 전에 안전한지 미리 확인**
```
pwndbg> try_free 0x555555559290
```

**6) fastbin dup 공격용 위조 청크 위치 탐색**
```
pwndbg> find_fake_fast 0x5555555592a0
```

## 명령어/단축키
```
bins
heap
malloc_chunk ADDR   (mc)
hi ADDR
fastbins
tcachebins
smallbins
largebins
unsortedbin
tcache
top_chunk
vis_heap_chunks     (vis)
find_fake_fast ADDR
try_free ADDR
mp
```

## 출력 해석
- `bins` 출력에서 각 bin 이름(`tcachebins`, `fastbins`, `unsortedbin` 등) 아래에 나열된 주소들이 그 bin의 연결 리스트에 들어있는 청크들이며, 크기(size)별로 그룹핑되어 보인다.
- `malloc_chunk`의 출력에는 청크의 `size` 필드(하위 3비트는 PREV_INUSE 등 플래그), `fd`/`bk`(free 상태일 때의 연결 리스트 포인터) 등이 표시된다. size 값과 실제 사용 가능한 데이터 크기는 다르다는 점(헤더 크기, 정렬 규칙)을 감안해서 읽어야 한다.
- `vis_heap_chunks`는 각 청크를 블록 형태로 나열하며, 할당된 청크(allocated)와 각 bin에 들어있는 free 청크를 서로 다른 색으로 구분해 보여준다.
- `try_free`는 실제로 메모리 상태를 바꾸지 않고 glibc가 그 주소에 대해 `free()`를 호출했을 때 어떤 검증(예: 이중 해제 감지)에 걸리는지만 미리 알려준다.

## 흔한 실수
- 멀티스레드 프로그램에서 `thread N`으로 스레드를 옮기지 않고 계속 같은 arena만 보다가 "다른 스레드가 만든 청크가 안 보인다"고 헷갈리는 것.
- `malloc_chunk`에 청크 헤더 주소가 아니라 사용자 데이터 시작 주소(헤더+0x10)를 잘못 넣어서 엉뚱한 값이 나오는 것 — 헷갈리면 `hi ADDR`로 먼저 정확한 청크 시작 위치를 찾는 것이 안전하다.
- `find_fake_fast`가 만능이라고 생각하고 결과로 나온 모든 후보 주소를 그대로 신뢰하는 것 — 실제로 유효한 fastbin dup 후보인지는 크기 필드(0x7f 등 특수 케이스 포함) 정합성을 직접 재확인해야 하며, 이 명령 자체에 알려진 버그가 있었던 이력도 있다.
- glibc 버전에 따라 tcache 존재 여부나 구조가 달라진다는 걸 모르고 다른 버전 기준 설명과 결과를 그대로 비교하는 것 — REV-0644 glibc 버전별 malloc 구조 요약표를 함께 참고해야 한다.

## 막혔을 때 다음 체크
- 힙 상태를 그림으로 보는 방법을 더 자세히 익히고 싶다면 → REV-0659 Pwndbg에서 힙 상태를 시각화해서 보는 법.
- tcache/fastbin 등 glibc 힙 구조 자체의 개념이 헷갈리면 → REV-0654 tcache와 fastbin 등 glibc 힙 구조 개요(리버싱 관점).
- glibc 버전마다 malloc 관련 구조체가 어떻게 다른지 궁금하면 → REV-0644 glibc 버전별 malloc 구조 요약표.
- `context`/`telescope`/`vmmap` 같은 힙 외의 기본 Pwndbg 명령이 궁금하면 → REV-0193 Pwndbg context telescope vmmap.

## 미니 예제
```
pwndbg> bins
tcachebins
0x20 [  2]: 0x555555559290 —▸ 0x555555559260 ◂— 0x0
fastbins
0x20: 0x0
unsortedbin
empty
smallbins
empty
largebins
empty
pwndbg> malloc_chunk 0x555555559290
Allocated chunk | PREV_INUSE
Addr: 0x555555559290
Size: 0x20
```
`bins` 한 번으로 tcache 0x20 크기 bin에 청크 2개가 걸려있는 것을 확인하고, 그중 하나를 `malloc_chunk`로 자세히 들여다본 예시다.

## 관련 글
- REV-0659 — Pwndbg에서 힙 상태를 시각화해서 보는 법
- REV-0654 — tcache와 fastbin 등 glibc 힙 구조 개요(리버싱 관점)
- REV-0644 — glibc 버전별 malloc 구조 요약표
- REV-0193 — Pwndbg context telescope vmmap

## 출처/검증
- `bins`, `fastbins`, `smallbins`, `largebins`, `unsortedbin`, `tcache`, `tcachebins`, `heap`, `hi`, `malloc_chunk`, `top_chunk`, `try_free`, `find_fake_fast`, `mp`, `vis_heap_chunks` 명령의 기능 설명: Pwndbg 공식 문서(pwndbg.re) Commands 및 Heap 설정 페이지 기준.
- `find_fake_fast` 관련 알려진 이슈(특정 크기 필드에서의 크래시)는 Pwndbg 공식 GitHub 저장소 이슈 트래커 기준 (2026-09-09 조사).
