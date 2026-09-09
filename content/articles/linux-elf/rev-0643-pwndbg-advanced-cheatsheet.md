---
id: REV-0643
title: "Pwndbg 명령어 심화 치트시트(heap/got/plt)"
slug: "rev-0643-pwndbg-advanced-cheatsheet"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [Pwndbg, GDB]
keywords: ["pwndbg heap", "pwndbg bins", "pwndbg got", "pwndbg vis_heap_chunks", "pwndbg telescope", "pwndbg checksec"]
aliases: ["pwndbg 명령어 모음", "pwndbg heap 명령어", "pwndbg got 확인", "pwndbg 힙 시각화", "pwndbg cheatsheet"]
symptom_keywords: ["힙 청크 구조가 안 보임", "GOT 상태를 빠르게 확인하고 싶음", "bins 명령 결과 해석", "카나리/PIE 베이스를 빠르게 알고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg는 순정 GDB 위에 힙/GOT/보호기법 상태를 사람이 읽기 좋은 색상과 표로 즉시 보여주는 확장 명령들(`heap`, `bins`, `got`, `vis_heap_chunks`, `telescope`, `checksec` 등)을 추가한 GDB 플러그인으로, CTF 힙/pwn 문제뿐 아니라 순수 리버싱에서도 메모리 상태를 빠르게 파악하는 데 필수적이다.

## 언제 검색해야 하나
- `malloc`/`free`로 만들어진 힙 청크들의 실제 구조(크기, `fd`/`bk` 포인터)를 순정 GDB의 `x` 명령으로 일일이 계산하기 귀찮을 때
- GOT 엔트리들이 현재 실제 함수 주소로 해석됐는지(resolved) 아직 안 됐는지(lazy) 한눈에 보고 싶을 때
- 스택/힙의 특정 주소부터 연속된 메모리를 포인터 체인처럼 따라가며 보고 싶을 때
- PIE 베이스, 카나리 값, RELRO/NX/PIE 상태를 매번 `readelf`로 따로 찾지 않고 GDB 세션 안에서 바로 보고 싶을 때

## 핵심 개념

### 설치와 기본 정보
Pwndbg는 GDB의 `.gdbinit`에 로드되는 파이썬 확장으로, 설치 후 GDB를 실행하면 프롬프트가 `pwndbg>`로 바뀌고 브레이크포인트가 걸릴 때마다 레지스터/디스어셈블리/스택을 한 화면(`context`)에 자동으로 보여준다.

### 힙 상태 조회 명령
```gdb
heap                 # 현재 arena의 모든 청크를 순서대로 요약 나열
bins                 # fastbin/unsortedbin/smallbin/largbin/tcache 전부 요약
fastbins             # fastbin만
tcachebins           # tcache만 (glibc 2.26+)
unsortedbin
smallbins
largebins
arena                # 현재(main) arena 구조체 상세
arenas               # 멀티스레드 환경의 모든 arena 목록
top_chunk            # 현재 top chunk(힙의 미할당 끝부분) 주소/크기
malloc_chunk <addr>  # 특정 주소를 malloc_chunk 구조체로 해석해서 필드별로 출력
mp                    # malloc_par(전역 malloc 파라미터) 구조체 출력
```
`bins` 계열 명령은 각 빈(bin)에 현재 몇 개의 청크가 체인으로 연결되어 있는지, 그 청크들의 주소와 크기를 fd 포인터를 따라가며 보여준다 — 이걸 손으로 하려면 `x/gx`를 수십 번 쳐야 한다.

### 힙 시각화
```gdb
vis_heap_chunks    # 별칭: vis
```
힙 전체를 청크 단위로 줄바꿈해서 시각적으로(각 청크의 `size`/`prev_size`/`fd`/`bk` 필드에 색을 입혀) 보여준다. 어떤 청크가 `free` 상태인지, 어떤 청크가 `top chunk`인지 등을 색으로 구분해준다.

### GOT / 보호기법 확인
```gdb
got                # 모든 GOT 엔트리와 resolved 여부를 나열
checksec           # 현재 로드된 바이너리의 Canary/NX/PIE/RELRO/RUNPATH 상태 요약
piebase            # PIE 베이스 주소(로드된 실제 시작 주소) 출력
canary             # 스택 카나리 현재 값 출력
```
`got` 명령은 각 함수의 GOT 슬롯 값이 아직 PLT resolver를 가리키면 노란색/lazy로, 실제 libc 주소로 이미 채워졌으면 초록색/resolved로 구분해 보여준다(REV-0100 참고).

### 메모리 탐색
```gdb
telescope <addr> [count]   # addr부터 count개의 워드를 연속으로 보여주며, 각 값이 포인터면 그 대상까지 재귀적으로 따라가 보여줌
stack <n>                  # 현재 스택 상위 n개 워드
search -t string "찾을문자열"
search -p "0xdeadbeef"     # 패턴 검색
xinfo <addr>                # 그 주소가 어느 세그먼트/구조체에 속하는지 상세 정보
```
`telescope`는 순정 GDB의 `x/10gx $rsp`보다 훨씬 읽기 좋다 — 각 워드가 스택 주소인지, 힙 주소인지, 코드 주소인지, 문자열인지 자동으로 라벨을 붙여준다.

## 화면/코드에서 보이는 징후
Pwndbg가 로드된 GDB 세션에서 브레이크포인트가 걸릴 때마다 자동으로 `LEGEND: STACK | HEAP | CODE | DATA | ...` 색상 범례와 함께 레지스터/디스어셈블리/스택 컨텍스트가 출력된다. 명령을 안 쳐도 이 컨텍스트 화면만으로도 순정 GDB보다 훨씬 많은 정보가 보인다.

## 가장 먼저 할 것
힙 문제를 처음 마주치면 `heap` → `bins` 순서로 쳐서 전체 그림을 먼저 파악하고, GOT/PLT가 관련된 문제라면 `got`부터, 보호기법 확인이 필요하면 `checksec`부터 친다.

## 단계별 절차

**1) 바이너리 보호기법 먼저 확인**
```gdb
pwndbg> checksec
```

**2) 힙 전체 구조 훑기**
```gdb
pwndbg> heap
pwndbg> bins
```

**3) 의심되는 청크 상세 확인**
```gdb
pwndbg> malloc_chunk 0x5555555592a0
```

**4) 힙을 그림으로 보기**
```gdb
pwndbg> vis
```

**5) GOT 상태 확인 (동적 링킹 함수 후킹/변조 여부 확인 시)**
```gdb
pwndbg> got
```

**6) 임의 주소 이후 메모리를 포인터 체인으로 훑기**
```gdb
pwndbg> telescope $rsp 20
```

## 명령어/단축키
```gdb
heap / bins / fastbins / tcachebins / unsortedbin / smallbins / largebins
arena / arenas / top_chunk / malloc_chunk <addr> / mp
vis (=vis_heap_chunks)
got / checksec / piebase / canary
telescope <addr> [n] / stack <n> / search -t string "..." / xinfo <addr>
context   # 현재 컨텍스트 화면 강제로 다시 출력
```

## 출력 해석
`bins` 출력 예(축약):
```
tcachebins
0x20 [  1]: 0x5555555592a0 ◂— 0x0
fastbins
0x20: 0x0
unsortedbin
empty
```
`tcachebins`의 `0x20 [ 1]`은 크기 `0x20`짜리 tcache 빈에 청크 1개가 연결되어 있고, 그 청크 주소가 `0x5555555592a0`이며 다음 `fd`가 `0x0`(리스트 끝)이라는 뜻이다. `fastbins`가 전부 `0x0`이면 현재 fastbin은 비어있는 상태다.

`got` 출력 예(축약):
```
State   Symbol          GOT Address       Value
Lazy    puts@plt         0x404018          0x401030 (puts@plt+6)
Resolved  printf@plt      0x404020          0x7ffff7c5a760 (printf)
```
`Lazy`는 아직 실제 `printf`/`puts` 주소로 안 채워진 상태, `Resolved`는 이미 실제 libc 주소로 채워진 상태다.

## 흔한 실수
- `bins`/`heap` 명령이 힙이 아직 한 번도 안 쓰인(=`malloc` 호출 전) 시점에는 의미 있는 정보를 못 준다는 것을 모르고 프로그램 시작 직후에 바로 쳐서 "아무것도 없다"고 당황하는 것 — 최소한 한 번 `malloc`이 호출된 뒤에 확인해야 한다.
- glibc 버전에 따라 `tcachebins` 자체가 없을 수 있다는 것(2.26 미만)을 모르고 결과가 안 나온다고 도구가 고장났다고 오해하는 것 — REV-0644 참고.
- `telescope` 결과에 나온 주소를 곧이곧대로 "항상 이 값"이라고 기억하는 것 — ASLR이 켜져 있으면 실행할 때마다 스택/힙/라이브러리 베이스가 달라진다.
- `got` 명령이 정적 링킹 바이너리에서는 보여줄 GOT 엔트리 자체가 거의 없다는 점을 놓치는 것(REV-0100 정적 링킹 관련 설명 참고).

## 막혔을 때 다음 체크
- 힙 청크 구조체 필드 자체(`prev_size`, `size`, `fd`, `bk`)의 의미가 궁금하면 → REV-0644 glibc 버전별 malloc 구조 요약표.
- GOT/PLT의 기본 개념이 궁금하면 → REV-0100 PLT와 GOT 기초.
- 순정 GDB의 `watch`/`catch` 등 기본기가 필요하면 → REV-0642 GDB 명령어 심화 치트시트.

## 미니 예제
```gdb
pwndbg> heap
Allocated chunk | PREV_INUSE
Addr: 0x555555559290
Size: 0x21

Free chunk (tcachebins[0x20][0/1]) | PREV_INUSE
Addr: 0x5555555592b0
Size: 0x21
fd: 0x0
pwndbg> bins
tcachebins
0x20 [  1]: 0x5555555592b0 ◂— 0x0
```
`heap` 결과에서 두 번째 청크가 "Free chunk"이고 tcache의 `0x20` 크기 빈에 이미 연결되어 있다고 나오며, `bins` 결과가 이를 다시 확인시켜준다 — `free()` 이후 해당 청크가 tcache로 들어갔음을 두 명령으로 교차 확인한 것이다.

## 관련 글
- REV-0644 — glibc 버전별 malloc 구조 요약표
- REV-0100 — PLT와 GOT 기초
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)
- REV-0096 — checksec 결과 읽는 법

## 출처/검증
- `heap`/`bins`/`fastbins`/`tcachebins`/`vis_heap_chunks`/`got`/`telescope`/`checksec`/`piebase`/`canary` 명령 존재 및 기능: Pwndbg 공식 GitHub 저장소 문서 및 명령어 목록(`pwndbg/commands/`) 기준 (2026-09-08 검증).
- tcache 관련 빈 구조는 glibc 2.26 이상에서만 존재: glibc 2.26 릴리스 NEWS 및 malloc 구현 변경 사항 기준.
