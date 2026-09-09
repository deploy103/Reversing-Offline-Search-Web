---
id: REV-0659
title: "Pwndbg에서 힙 상태를 시각화해서 보는 법"
slug: "rev-0659-pwndbg-heap-visualization"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pwndbg heap", "pwndbg bins", "vis_heap_chunks", "tcache 확인", "malloc_chunk", "chunk 헤더"]
aliases: ["pwndbg heap 명령어", "pwndbg vis", "힙 청크 확인", "pwndbg tcachebins"]
symptom_keywords: ["힙 청크 구조가 헷갈림", "tcache 리스트가 어떻게 생겼는지 보고 싶음", "malloc free 이후 청크 상태 확인", "heap 명령이 안 됨"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg는 `heap`, `bins`, `vis_heap_chunks`(별칭 `vis`) 같은 명령으로 glibc 힙 안의 청크(chunk) 목록, 각 청크의 크기·플래그, tcache/fastbin/unsortedbin/smallbin/largebin에 연결된 프리 리스트를 사람이 읽기 좋은 색상/표 형태로 즉시 보여줘서, `x/20gx` 같은 raw 메모리 덤프를 손으로 계산하며 읽지 않고도 힙 상태를 한눈에 파악할 수 있게 해준다.

## 언제 검색해야 하나
- heap 문제(UAF, double free, heap overflow 등)를 분석하면서 지금 malloc된 청크들과 free된 청크들이 메모리에 어떻게 배치돼 있는지 보고 싶을 때
- `free()` 이후 그 청크가 tcache/fastbin 중 어디로 들어갔는지, 다음에 `malloc()`하면 어떤 청크가 재사용될지 예측하고 싶을 때
- `malloc_chunk`, `chunk`, `heap`, `bins` 명령을 쳤는데 출력이 이해가 안 되거나 에러가 날 때

## 핵심 개념

### glibc 청크(chunk) 구조 복습
glibc malloc이 관리하는 힙 메모리 블록은 `malloc_chunk` 구조로 나뉘어 있다. 핵심 필드:
```c
struct malloc_chunk {
  size_t prev_size;   // 이전 청크가 free 상태일 때만 유효 (그 청크의 크기)
  size_t size;         // 이 청크의 크기 + 하위 3비트 플래그
  struct malloc_chunk *fd;   // free 상태일 때만: 다음 free 청크
  struct malloc_chunk *bk;   // free 상태일 때만: 이전 free 청크
};
```
`size` 필드의 하위 3비트는 각각 `PREV_INUSE`(직전 청크가 사용 중인지), `IS_MMAPPED`(mmap으로 확보된 청크인지), `NON_MAIN_ARENA`(메인 아레나가 아닌 스레드 아레나 소속인지) 플래그다. 실제 청크 크기는 이 값에서 하위 3비트를 마스킹해서(`size & ~0x7`) 구해야 한다.

### 프리 리스트 종류
- **tcache**: glibc 2.26+ 기본. 스레드-로컬 캐시로, 크기별 최대 7개(기본값)까지 최근 free된 청크를 단일 연결 리스트로 보관한다. glibc 2.29부터 `fd` 포인터에 safe-linking(`PROTECT_PTR`, 힙 주소 기반 XOR 마스킹)이 적용된다.
- **fastbin**: 작은 크기(기본 x64에서 32~176바이트) 청크용 단일 연결 리스트. tcache가 가득 찼을 때 넘치는 청크가 여기로 간다.
- **unsortedbin**: free된 청크가 처음 들어가는 임시 대기소. 다음 malloc 요청 때 크기가 맞으면 재사용되거나 알맞은 bin으로 정렬된다.
- **smallbin / largebin**: 크기별로 정렬된 이중 연결 리스트. 재사용 우선순위가 tcache/fastbin보다 낮다.

### Pwndbg가 이걸 사람이 읽기 좋게 바꿔준다
GDB 기본 기능만으로 이 구조들을 확인하려면 `x/4gx <chunk주소>`를 청크마다 반복하며 `size` 필드를 손으로 마스킹하고, `fd`/`bk`를 따라가며 리스트를 추적해야 한다. Pwndbg는 이 전체 과정을 `heap`, `bins`, `vis_heap_chunks` 같은 명령 하나로 자동화해서, 색상(사용 중=한 색, free=다른 색)과 함께 정리된 표로 보여준다.

## 화면/코드에서 보이는 징후
소스 코드보다는 GDB+Pwndbg 세션에서 직접 확인하는 상황이다. 문제 바이너리가 `malloc`, `free`, `calloc`, `realloc`을 반복 호출하는 메뉴 구조(1. Add, 2. Delete, 3. Edit, 4. Show 같은 힙 문제 전형적 UI)를 갖고 있다면 이 명령들이 필요한 신호다.

## 가장 먼저 할 것
프로그램을 malloc이 최소 한 번 이상 호출된 지점까지 실행시킨 뒤(예: 메뉴에서 "1. Add" 한 번 선택 후) 곧바로 힙 전체를 훑어본다:
```
pwndbg> heap
```

## 단계별 절차

**1) 힙 전체 청크 목록 보기**
```
pwndbg> heap
```
현재 아레나에 있는 모든 청크를 주소 순서대로, 크기와 상태(할당됨/free됨)와 함께 나열한다.

**2) 모든 bin 상태를 한 번에 보기**
```
pwndbg> bins
```
tcache, fastbins, unsortedbin, smallbins, largebins를 각 크기별로 어떤 청크가 연결되어 있는지 리스트로 보여준다. 빈 bin은 생략되거나 `empty`로 표시된다.

**3) tcache만 따로 보기**
```
pwndbg> tcachebins
```

**4) fastbin만 따로 보기**
```
pwndbg> fastbins
```

**5) 특정 청크 하나를 자세히 보기**
```
pwndbg> malloc_chunk <주소>
```
또는 줄여서:
```
pwndbg> chunk <주소>
```
해당 청크의 `prev_size`, `size`(플래그 해석 포함), free 상태면 `fd`/`bk`까지 필드별로 보여준다.

**6) 힙 전체를 그림으로 보기**
```
pwndbg> vis_heap_chunks
```
별칭:
```
pwndbg> vis
```
각 청크를 블록 단위로 나열하면서 헤더 바이트, ASCII 표현, 청크 경계를 색상으로 구분해서 그려준다. 청크 여러 개가 연속으로 붙어 있는 힙 오버플로우/UAF 문제에서 특히 유용하다.

**7) 아레나(malloc_state) 자체 정보 보기**
```
pwndbg> arena
```
top chunk 주소, 현재 아레나가 메인인지 스레드 아레나인지 등을 보여준다.

## 명령어/단축키
```
pwndbg> heap                 # 힙의 모든 청크 목록
pwndbg> bins                 # 모든 bin(tcache/fast/unsorted/small/large) 요약
pwndbg> tcachebins            # tcache만
pwndbg> fastbins              # fastbin만
pwndbg> unsortedbin            # unsortedbin만
pwndbg> smallbins              # smallbin만
pwndbg> largebins               # largebin만
pwndbg> malloc_chunk <addr>   # 청크 하나 상세 (= chunk)
pwndbg> vis_heap_chunks        # 힙 시각화 (= vis)
pwndbg> arena                 # malloc_state 정보
pwndbg> top_chunk              # top chunk 주소
```

## 출력 해석
```
pwndbg> bins
tcachebins
0x20 [  2]: 0x55d4a1b2c2a0 —▸ 0x55d4a1b2c260 ◂— 0x0
fastbins
0x20: 0x0
0x30: 0x0
unsortedbin
empty
smallbins
empty
largebins
empty
```
- `0x20 [  2]`: 크기 0x20(32바이트) 청크가 tcache에 **2개** 연결되어 있다는 뜻.
- `0x55d4a1b2c2a0 —▸ 0x55d4a1b2c260 ◂— 0x0`: tcache 연결 리스트를 화살표로 그려준 것 — 첫 번째 청크(`0x...c2a0`)의 `fd`(safe-linking 복호화 후)가 두 번째 청크(`0x...c260`)를 가리키고, 그 청크의 `fd`는 `0x0`(리스트 끝)이라는 뜻.
- `fastbins`의 `0x20: 0x0`, `0x30: 0x0`: 두 크기 클래스 모두 fastbin에는 청크가 없다(전부 `0x0` = NULL).
- `unsortedbin`, `smallbins`, `largebins`가 `empty`: 아직 이 bin들로 넘어간 청크가 없다는 뜻 — 지금까지 free된 청크가 전부 tcache 용량(기본 7개) 안에서 처리됐다는 신호.

```
pwndbg> chunk 0x55d4a1b2c260
Allocated chunk | PREV_INUSE
Addr: 0x55d4a1b2c260
Size: 0x21
```
- `Size: 0x21`: 실제 청크 크기는 `0x20`(32바이트)이고 하위 비트 `1`은 `PREV_INUSE` 플래그가 켜져 있다는 뜻(직전 청크가 사용 중).
- `Allocated chunk`: 이 청크가 현재 free되지 않고 할당된 상태로 표시(주의: free된 직후라도 tcache에 들어간 청크는 자체 헤더의 `PREV_INUSE` 비트가 그대로 남아있는 등 glibc 특유의 표기 방식이 있으니, `bins`/`heap` 출력과 함께 교차 확인하는 것이 안전하다).

## 흔한 실수
- `heap`/`bins` 명령이 "no valid heap" 류의 에러를 낸다고 당황하는 것 — 프로그램이 아직 `malloc`을 한 번도 안 불러서 힙 세그먼트 자체가 아직 매핑 안 됐을 수 있다. 최소 한 번 malloc 이후에 다시 시도한다.
- `fd`/`bk` 값을 그대로 다음 청크 주소라고 믿는 것 — glibc 2.29부터 tcache의 `fd`(`next`)에는 safe-linking으로 XOR 마스킹이 걸려 있어서, raw 메모리 값과 Pwndbg가 보여주는 "복호화된" 화살표 값이 다르다. Pwndbg의 `bins`/`tcachebins` 출력은 이미 복호화된 값을 보여주므로 이걸 기준으로 봐야 한다.
- 정적으로 힙 크기/레이아웃을 예측하려다 ASLR 때문에 매 실행마다 힙 베이스 주소가 바뀌는 걸 놓치는 것 — 절대 주소보다 `heap`/`vis`가 보여주는 상대적 배치(어떤 청크가 어떤 청크 다음에 있는지)에 집중한다.
- `vis_heap_chunks` 출력이 너무 길어서 스크롤에 잘려 앞부분을 놓치는 것 — `set pagination off`로 페이지네이션을 끄거나, 필요하면 `pwndbg> heap > heap.log` 식으로 리다이렉트해서 확인한다.

## 막혔을 때 다음 체크
- bins 안의 특정 값이 다른 곳에서도 쓰이는지 메모리 전체에서 찾고 싶다면 → REV-0660 Pwndbg search로 메모리에서 패턴 찾기
- tcache/fastbin 자체의 이론적 구조(더블프리 취약점, safe-linking 등)를 더 깊게 알고 싶다면 → REV-0654 tcache와 fastbin 등 glibc 힙 구조 개요
- malloc 내부 전체 흐름(어떤 조건에서 어떤 bin을 먼저 확인하는지)이 궁금하다면 → REV-0655 glibc malloc 내부 흐름 개요
- Pwndbg 자체 설치나 기본 명령이 헷갈린다면 → REV-0192 Pwndbg 설치와 실행, REV-0286 Pwndbg 명령어 치트시트

## 미니 예제
```
pwndbg> heap
Allocated chunk | PREV_INUSE
Addr: 0x55d4a1b2c250
Size: 0x251

Free chunk (tcache) | PREV_INUSE
Addr: 0x55d4a1b2c4a0
Size: 0x21
fd: 0x0
bk: 0x0

Top chunk | PREV_INUSE
Addr: 0x55d4a1b2c4c0
Size: 0x20b41
```
- 첫 번째 청크(`0x...c250`)는 아직 할당 중(top-level 관리 구조체 등).
- 두 번째 청크(`0x...c4a0`)는 `free()` 후 tcache로 들어간 상태 — `bins` 명령으로 같은 주소가 tcache 0x20 리스트에도 나타나는지 교차 확인할 수 있다.
- `Top chunk`는 힙에서 아직 한 번도 분할되지 않은 나머지 큰 영역으로, 다음 malloc 요청이 기존 free 청크로 해결 안 되면 여기서 잘라 쓴다.

## 관련 글
- REV-0660 — Pwndbg search로 메모리에서 패턴 찾기
- REV-0654 — tcache와 fastbin 등 glibc 힙 구조 개요(리버싱 관점)
- REV-0655 — glibc malloc 내부 흐름 개요(청크 헤더 수준)
- REV-0192 — Pwndbg 설치와 실행
- REV-0286 — Pwndbg 명령어 치트시트

## 출처/검증
- `heap`, `bins`, `tcachebins`, `fastbins`, `malloc_chunk`, `vis_heap_chunks`, `arena` 명령: Pwndbg 공식 GitHub 저장소 문서/명령 목록 기준.
- `malloc_chunk` 필드(`prev_size`, `size`, `fd`, `bk`)와 하위 3비트 플래그(`PREV_INUSE`, `IS_MMAPPED`, `NON_MAIN_ARENA`), tcache safe-linking: glibc 소스(`malloc/malloc.c`) 및 glibc 2.29 changelog 기준 (2026-09-08 검증).
