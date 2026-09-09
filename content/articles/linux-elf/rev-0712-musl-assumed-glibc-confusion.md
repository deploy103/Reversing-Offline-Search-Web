---
id: REV-0712
title: "musl 바이너리를 glibc 전제로 분석해서 헷갈릴 때"
slug: "rev-0712-musl-assumed-glibc-confusion"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, readelf, file]
keywords: ["musl 착각", "glibc 전제 분석 오류", "ld-musl", "pwndbg heap 안 됨", "musl malloc 구조 다름"]
aliases: ["musl인데 glibc로 분석함", "pwndbg heap 명령이 이상함", "tcache 명령이 안 먹힘 musl", "libc-database에 안 나옴"]
symptom_keywords: ["pwndbg heap/bins 명령을 쳤는데 값이 이상하거나 아예 안 나옴", "libc-database에서 아무리 검색해도 안 나옴", "malloc_chunk 구조체 오프셋이 문서랑 다름", "FLIRT 시그니처가 하나도 안 맞는데 정적 링킹된 작은 바이너리임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Alpine 기반 Docker 이미지 등에서 만든 바이너리는 musl로 링크되는데, 이걸 glibc라고 무의식적으로 전제한 채 pwndbg의 `heap`/`tcache`/`bins` 명령을 쓰거나 libc-database에서 오프셋을 찾으면 값이 이상하거나 아예 아무것도 안 나와서 "분석이 잘못됐나" 헷갈리게 된다 — 실제로는 애초에 glibc가 아니라서 glibc 전용 도구/지식이 적용되지 않는 것이다.

## 언제 검색해야 하나
- pwndbg에서 `heap`, `bins`, `tcache` 명령을 쳤는데 에러가 나거나 값이 말이 안 될 때
- `libc.so.6`을 찾으려고 libc-database에서 심볼 오프셋으로 검색했는데 아무리 찾아도 매칭이 안 될 때
- 정적 링킹된 바이너리인데 파일 크기가 유난히 작고(수백 KB대), glibc FLIRT 시그니처가 하나도 안 맞을 때
- 분석 도중에야 `file`/`readelf` 결과에서 인터프리터가 `ld-musl-x86_64.so.1`이라는 걸 뒤늦게 알아챘을 때

## 핵심 개념

### 증상이 먼저 보이고 원인은 나중에 발견되는 패턴
REV-0647에서 musl과 glibc의 근본적인 차이(경량 구현, 다른 malloc 알고리즘 등)를 다뤘다면, 이 글은 그 사실을 모른 채 "당연히 glibc겠지"라고 전제하고 분석을 진행하다가 마주치는 **구체적인 실패 증상들**을 다룬다. 실무에서는 바이너리를 받자마자 musl 여부를 확인하지 않고 바로 GDB/pwndbg 명령부터 치는 경우가 많아서, 원인 파악이 한참 늦어지곤 한다.

### pwndbg heap 계열 명령이 이상하게 동작하는 이유
pwndbg의 `heap`, `bins`, `tcache` 명령은 glibc의 `malloc_chunk`, `tcache_perthread_struct` 등 **glibc 전용 구조체 레이아웃**을 가정하고 메모리를 해석한다. musl은 자체 할당자(`mallocng`, 구버전은 다른 방식)를 쓰며 청크 헤더, 프리리스트 구조가 전혀 다르다. 그 결과 pwndbg가 glibc 구조체 오프셋으로 musl 힙 메모리를 읽으면 값이 랜덤하게 보이거나, 애초에 glibc 심볼(`main_arena` 등)을 못 찾아 명령 자체가 실패한다.

### libc-database에서 안 나오는 이유
libc-database, `one_gadget` 같은 도구/데이터베이스는 배포판별 **glibc** 바이너리를 수집해둔 것이다. musl은 별도의 프로젝트이고 애초에 이 데이터베이스의 수집 대상이 아니므로, 심볼 오프셋으로 아무리 검색해도 매칭되는 항목이 없는 것이 정상이다.

### FLIRT 시그니처가 하나도 안 맞는 이유
IDA FLIRT/Ghidra Function ID 시그니처는 특정 컴파일러+**glibc** 조합의 바이트 패턴을 학습한 것이다. musl로 정적 링크된 바이너리는 함수 구현 자체가 다르므로 바이트 패턴이 전혀 다르게 나오고, glibc 시그니처를 적용해도 매칭률이 0에 가깝다. "정적 링킹인데 시그니처가 하나도 안 맞는다"는 현상 자체가 musl을 의심할 강력한 단서다.

## 화면/코드에서 보이는 징후
```
pwndbg> heap
[!] Could not find the heap for the main arena
```
또는 libc-database 검색에서
```
$ ./find __libc_start_main 400 500 4a0
No match found
```
이런 결과가 나오면서도 정작 원인(musl)은 아직 확인하지 않은 상태가 전형적인 증상이다.

## 가장 먼저 할 것
GDB/pwndbg 명령을 붙잡고 헤매기 전에 `file ./chall`과 `readelf -l ./chall | grep interpreter`부터 확인해서 인터프리터가 `ld-musl-*`인지, 또는 정적 바이너리라면 크기와 심볼 이름 접두사(`__stdio_` 등 musl 특유의 이름)를 먼저 본다.

## 단계별 절차
1. `file ./chall`로 인터프리터/정적 여부 확인
2. 동적 링킹이면 `readelf -l ./chall | grep interpreter`로 `ld-musl-x86_64.so.1` 여부 직접 확인
3. 정적 링킹이면 `strings ./chall | grep -i musl`, 또는 `nm ./chall`에 `__stdio_write`, `__syscall` 같은 musl 특유 내부 심볼이 있는지 확인
4. musl로 확인되면 pwndbg의 glibc 전용 heap 명령 사용을 중단하고, 수동으로 `x/`, `info proc mappings`로 힙 영역을 직접 읽는 방식으로 전환
5. libc-database/one_gadget 사용을 중단하고, musl 소스 코드(공식 저장소)를 참고해 해당 버전의 malloc 구현을 직접 대조
6. FLIRT/Function ID는 포기하고 `_start`부터 수동으로 콜체인을 따라가며 함수 식별(REV-0646 방식) 적용

## 명령어/단축키
```bash
file ./chall
readelf -l ./chall | grep interpreter
strings ./chall | grep -i musl
nm ./chall | grep -E '__stdio_|__syscall'
info proc mappings   # gdb 안에서, 힙 영역 수동 확인용
```

## 출력 해석
`readelf -l` 결과의 `[Requesting program interpreter: /lib/ld-musl-x86_64.so.1]` 한 줄이 나오면 musl이 확정이다. 이 상태에서는 pwndbg heap 명령의 실패나 libc-database의 "No match found"가 버그가 아니라 애초에 대상이 아니라서 나오는 정상 결과임을 인지해야 한다.

## 흔한 실수
- pwndbg 명령이 실패하는 걸 pwndbg 자체의 버그나 설치 문제로 오해하고 재설치를 반복하는 것(REV-0690과는 다른 원인).
- libc-database에 안 나온다고 오프셋을 억지로 다른 glibc 버전에서 추정해서 대입하는 것 — musl은애초에 glibc 오프셋 체계와 무관하다.
- 정적 링킹 + FLIRT 매칭 실패를 보고 "strip이 너무 심하게 됐나보다"라고 잘못 결론짓는 것 — 실제로는 musl이라 시그니처 자체가 대상이 아니다.
- musl로 확인된 후에도 계속 glibc 문서의 구조체 오프셋을 참고하는 것.

## 막혔을 때 다음 체크
- musl과 glibc의 근본적인 차이(malloc 구현, 심볼 버전 유무 등)를 아직 안 읽었다면 → REV-0647 musl libc와 glibc 차이가 리버싱에 미치는 영향.
- pwndbg 명령 자체가 설치 문제로 안 먹는 것인지 구분이 안 되면 → REV-0690 Pwndbg가 설치는 됐는데 명령어가 안 먹을 때.
- 정적 링킹 바이너리에서 함수를 수동으로 찾는 절차가 기억 안 나면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법.

## 미니 예제
```bash
$ file ./chall
chall: ELF 64-bit LSB executable, x86-64, ... dynamically linked, interpreter /lib/ld-musl-x86_64.so.1, ...
$ pwndbg> heap
[!] Could not find the heap for the main arena
```
`file` 결과에서 인터프리터가 `ld-musl-x86_64.so.1`로 확인된 순간, `heap` 명령 실패가 pwndbg 문제가 아니라 애초에 glibc 힙 구조가 없는 musl 바이너리였기 때문이라는 게 명확해진다.

## 관련 글
- REV-0647 — musl libc와 glibc 차이가 리버싱에 미치는 영향
- REV-0690 — Pwndbg가 설치는 됐는데 명령어가 안 먹을 때
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0709 — Pwndbg에서 heap 명령이 이 glibc 버전에서 지원 안 된다고 할 때

## 출처/검증
- musl의 malloc 구현(mallocng 등)이 glibc의 malloc_chunk/tcache 구조와 근본적으로 다르다는 점: musl libc 공식 소스 저장소 및 프로젝트 문서 기준.
- pwndbg heap 관련 명령이 glibc 심볼(main_arena 등)과 구조체 레이아웃에 의존한다는 점: pwndbg 공식 저장소 문서 기준.
- IDA FLIRT/Ghidra Function ID가 특정 라이브러리 바이트 패턴 기반 매칭이라는 점: Hex-Rays IDA 및 Ghidra 공식 문서 기준 (2026-09-09 검증).
