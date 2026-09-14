---
id: REV-0709
title: "Pwndbg에서 heap 명령이 이 glibc 버전에서 지원 안 된다고 할 때"
slug: "rev-0709-pwndbg-heap-not-supported"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [Pwndbg, GDB]
keywords:
  - pwndbg heap
  - glibc version detection
  - tcache
  - malloc_chunk
  - GLIBC_TUNABLES
  - symbol resolution
  - debug symbols
  - libc6-dbg
symptom_keywords:
  - pwndbg heap 명령을 쳤는데 지원 안 된다는 에러가 뜸
  - could not find glibc version
  - tcache bins 명령이 아무것도 안 보여줌
  - vis heap 명령이 깨져서 나옴
  - malloc_chunk 구조체를 못 읽음
aliases:
  - pwndbg heap 에러
  - pwndbg glibc 버전 인식 실패
  - tcache bins 안 나옴
  - pwndbg heap 명령 안 됨
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg의 `heap`, `bins`, `tcache`, `vis` 같은 힙 명령은 내부적으로 대상 프로세스가 사용 중인 **glibc 버전과 malloc 내부 구조체 레이아웃을 자동으로 인식**해야 동작하는데, 이 인식이 실패하면 "not supported"류 에러나 빈 출력이 나오며, 대부분 (1) libc 심볼/버전 정보를 못 읽거나 (2) pwndbg 자체가 오래되어 최신 glibc의 tcache/heap 구조 변경을 모르는 경우이므로 `pwndbg> heap` 대신 `pwndbg> libc_ver` 등으로 인식 상태를 먼저 확인하고 pwndbg를 최신화하는 것이 우선이다.

## 언제 검색해야 하나
- `pwndbg> bins`나 `pwndbg> heap`을 쳤는데 `Could not determine libc version` 같은 에러가 뜰 때
- `tcache bins`가 항상 빈 목록으로만 나오고 실제로 해제한 청크가 안 보일 때
- 최신 배포판(Ubuntu 24.04 등)의 glibc 2.39+ 바이너리를 분석하는데 pwndbg가 힙 레이아웃을 잘못 해석해서 이상한 값을 보여줄 때
- CTF 문제에서 준 특정 버전의 `libc.so.6`(예: 2.31, 2.35, 2.39)을 GDB에 로드했는데 pwndbg 힙 명령이 동작하지 않을 때

## 핵심 개념

### pwndbg가 힙 명령을 위해 필요로 하는 정보
pwndbg의 힙 관련 명령은 glibc 소스의 `malloc_chunk`, `malloc_state`(arena), `tcache_perthread_struct` 구조체 레이아웃을 그대로 재현해서 대상 프로세스의 메모리를 해석한다. 이 구조체들은 glibc 버전마다 필드가 달라졌기 때문에(예: tcache는 glibc 2.26부터 도입, tcache의 `key` 필드는 2.29에서 포인터 방식으로 변경, Safe-Linking은 2.32부터 도입), pwndbg는 실행 중인 프로세스가 **실제로 어떤 glibc를 로드했는지** 정확히 알아야 그에 맞는 구조체 정의를 골라 쓸 수 있다.

이 버전 인식은 보통 다음 정보로 이루어진다.
- libc 이미지 안의 문자열(`GNU C Library ... version 2.35`)이나 심볼 버전 정보
- 로드된 `libc.so.6`의 파일 경로/이름에 포함된 버전 힌트
- glibc 디버그 심볼(있다면 `malloc_state` 구조체 정의를 DWARF에서 직접 읽어옴)

### "not supported" 계열 문제가 생기는 대표적인 이유
1. **pwndbg 자체가 오래되어 최신 glibc를 모르는 경우.** pwndbg는 릴리스마다 지원하는 glibc 범위를 확장해왔다(예: 2024.02.14 릴리스에서 libc 2.12+ 힙 익스플로잇 지원을 정식으로 추가). 오래된 pwndbg로 아주 새 glibc(2.38, 2.39 등)나 아주 오래된 glibc를 분석하면 구조체 오프셋이 안 맞아 값이 깨지거나 명령 자체가 실패할 수 있다.
2. **libc 버전을 자동으로 못 찾는 경우.** strip된 커스텀 libc, 심볼 버전 문자열이 지워진 libc, 또는 정적 링킹이라 별도의 `libc.so.6` 매핑이 아예 없는 경우 pwndbg가 버전을 추정할 근거 자체가 없다.
3. **아직 힙이 초기화되지 않은 시점.** 프로그램 시작 직후(첫 `malloc` 호출 전)에는 `main_arena`가 아직 유효한 값으로 채워지지 않아 `bins`/`heap` 명령이 이상한 값을 보여주거나 실패할 수 있다.

## 화면/코드에서 보이는 징후
- `pwndbg> heap` → `Could not find the version of glibc used, symbols may be missing` 류 경고
- `pwndbg> bins` → `Invalid address` 또는 빈 리스트만 출력
- `pwndbg> tcache` → tcache 구조체를 아예 못 찾음(2.26 미만 glibc인데 tcache 명령을 쓴 경우도 포함)
- `vis`(heap 시각화) 결과 청크 헤더 크기가 이상하게 커지거나 오프셋이 어긋나 보임

## 가장 먼저 할 것
1. `pwndbg> libc_ver` (또는 `heap --help` 후 버전 관련 하위 명령)로 pwndbg가 실제로 어떤 glibc 버전을 인식했는지 확인한다.
2. `pip3 install --upgrade pwndbg` 혹은 저장소를 `git pull`해서 pwndbg 자체를 최신화한다.
3. `info sharedlibrary`로 실제 로드된 `libc.so.6` 경로를 확인하고, 그 파일이 문제에서 배포한 libc와 정확히 일치하는지 대조한다.

## 단계별 절차

**1) 현재 pwndbg가 인식한 libc 버전 확인**
```gdb
pwndbg> libc_ver
GLIBC version: 2.35
```
버전이 아예 안 나오거나 `Could not determine`으로 나오면 자동 인식이 실패한 것이다.

**2) 실제 로드된 libc 경로/버전 직접 확인**
```gdb
pwndbg> info sharedlibrary
0x00007ffff7d9b090  0x00007ffff7f2c1a0  Yes         /home/user/ctf/libc.so.6
```
```bash
$ ./libc.so.6
GNU C Library (Ubuntu GLIBC 2.35-0ubuntu3.8) stable release version 2.35.
```
libc 파일을 직접 실행하면(실행 권한이 있는 `.so`는 버전 문자열을 출력하는 경우가 많다) 정확한 버전 문자열을 확인할 수 있다. `strings libc.so.6 | grep "GNU C Library"`로도 같은 정보를 얻을 수 있다.

**3) pwndbg를 최신 버전으로 업데이트**
```bash
$ cd ~/pwndbg
$ git pull
$ ./setup.sh
```
pip로 설치했다면:
```bash
$ pipx upgrade pwndbg   # 또는 pip3 install --upgrade pwndbg
```
pwndbg는 릴리스마다 새 glibc 버전의 malloc 구조체 변경(tcache key 방식, safe-linking, `size_t` 정렬 규칙 등)을 반영하므로, 최신화만으로 해결되는 경우가 가장 많다.

**4) 그래도 인식이 안 되면 힙이 아직 초기화 전인지 확인**
```gdb
pwndbg> break main
pwndbg> run
pwndbg> next   # malloc이 최소 한 번은 호출된 지점까지 진행
pwndbg> heap
```
프로그램 진입 직후 바로 `heap`을 치면 arena가 아직 lazy 초기화되지 않아 실패할 수 있다. 최소 한 번 `malloc`이 호출된 뒤 시도한다.

**5) 정적 링킹 바이너리라 별도 libc 매핑이 없는 경우**
```gdb
pwndbg> info sharedlibrary
No shared libraries loaded at this time.
```
이 경우 pwndbg가 malloc 심볼과 구조체를 정적 바이너리 자체에서 찾아야 하는데, strip되어 있으면 사실상 자동 인식이 불가능하다. `nm`으로 `malloc`, `main_arena` 심볼이 남아있는지 먼저 확인하고, 없다면 REV-0668(strip된 정적 바이너리에서 libc 함수 식별)의 시그니처 매칭 접근이 필요하다.

**6) 디버그 심볼을 설치해 정확도 높이기 (선택)**
```bash
$ sudo apt install libc6-dbg
```
Ubuntu/Debian 계열에서 `libc6-dbg` 패키지를 설치하면 pwndbg가 `malloc_state` 등 구조체 정의를 DWARF에서 직접 읽어와 버전 추정 없이도 정확하게 동작할 수 있다.

## 명령어/단축키
```gdb
libc_ver                  # pwndbg가 인식한 glibc 버전 확인
info sharedlibrary        # 로드된 libc 실제 경로 확인
heap                       # 힙 청크 목록
bins                       # fastbin/tcache/smallbin/largbin 상태
tcache                     # tcache 구조 상세
vis                        # 힙 시각화
```
```bash
strings libc.so.6 | grep "GNU C Library"   # 정확한 glibc 버전 문자열 확인
```

## 출력 해석
- `libc_ver`가 버전을 정확히 출력하면 이후 `heap`/`bins` 명령의 결과도 신뢰할 수 있다.
- `bins`에서 tcache가 존재해야 할 glibc 2.26 이상인데 `tcachebins empty`만 계속 나온다면, 실제로 해제된 청크가 없거나(정상) tcache 자체가 비활성화된 빌드(`--disable-tunables`)일 수 있다.
- 청크 크기가 비정상적으로 크거나 음수처럼 보이면 구조체 오프셋 자체가 잘못 해석된 것이므로, 버전 인식 실패를 다시 의심해야 한다.

## 흔한 실수
- pwndbg가 오래됐다는 것을 모른 채 "이 glibc 버전은 pwndbg가 지원 안 하는구나"라고 단정하고 포기하는 것 — 대부분 `git pull` 한 번으로 해결된다.
- 문제에서 배포한 `libc.so.6`을 로드하지 않고 시스템 libc로 디버깅하면서 힙 구조가 이상하다고 착각하는 것 — `LD_PRELOAD`/`LD_LIBRARY_PATH`(REV-0706, REV-0711 참고)로 반드시 정확한 libc를 강제해야 한다.
- 프로그램 시작 직후, 첫 `malloc` 호출 전에 `heap`을 실행해서 "안 된다"고 오해하는 것.
- 정적 링킹 바이너리에서 힙 명령이 안 되는 걸 pwndbg 버그로 착각하는 것 — 정적 바이너리는 애초에 별도 `libc.so.6` 매핑이 없어 자동 인식 대상이 아니다.

## 막혔을 때 다음 체크
- 애초에 서버/문제 환경과 로컬 glibc 버전이 다른 게 원인일 수 있다면 → REV-0711(서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때)
- 정적 링킹 바이너리라 심볼 자체가 안 보인다면 → REV-0646(정적 링킹된 ELF 분석 접근법)
- glibc 버전 차이로 함수 시그니처/구조가 달라지는 것을 더 체계적으로 확인하고 싶다면 → REV-0648(glibc 버전별 함수 시그니처 차이 확인법)
- Pwndbg 설치/명령 자체가 안 먹힐 때는 → REV-0690(Pwndbg가 설치는 됐는데 명령어가 안 먹을 때)

## 미니 예제
```gdb
pwndbg> heap
Could not find the version of glibc used, symbols may be missing
pwndbg> libc_ver
GLIBC version: could not determine
pwndbg> info sharedlibrary
0x7ffff7d9b090  0x7ffff7f2c1a0  Yes  /home/user/ctf/libc.so.6
```
```bash
$ strings /home/user/ctf/libc.so.6 | grep "GNU C Library"
GNU C Library (Ubuntu GLIBC 2.39-0ubuntu8.3) stable release version 2.39.
$ cd ~/pwndbg && git pull && ./setup.sh
```
```gdb
pwndbg> heap
Allocated chunk | PREV_INUSE
Addr: 0x555555559290
Size: 0x250 (with flag bits: 0x251)
```
오래된 pwndbg가 glibc 2.39를 인식 못 하던 문제가 최신화 후 정상적으로 해석됐다.

## 관련 글
- REV-0711 — 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때
- REV-0706 — 공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0648 — glibc 버전별 함수 시그니처 차이 확인법

## 출처/검증
- Pwndbg의 glibc 힙 지원 범위 확장(libc 2.12+ 힙 익스플로잇 지원 추가 등): pwndbg 공식 GitHub 저장소 릴리스 노트(2024.02.14 등) 기준.
- glibc malloc/tcache 구조체가 버전마다 변경된 사실(tcache 도입 2.26, tcache key 포인터화 2.29, safe-linking 2.32 등): glibc 공식 NEWS 파일 및 소스(`malloc/malloc.c`) 변경 이력 기준.
- `libc6-dbg` 패키지를 통한 디버그 심볼 활용: Ubuntu/Debian 패키지 문서 기준 (2026-09-08 확인).
