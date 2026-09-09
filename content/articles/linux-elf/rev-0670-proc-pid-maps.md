---
id: REV-0670
title: "프로세스 메모리 맵(/proc/pid/maps) 읽는 법"
slug: "rev-0670-proc-pid-maps"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["/proc/pid/maps", "메모리 맵", "process memory map", "vmmap", "info proc mappings"]
aliases: ["proc pid maps 읽는 법", "vmmap 해석", "메모리 매핑 확인", "info proc mappings 사용법"]
symptom_keywords: ["proc pid maps가 뭔지 모르겠음", "vmmap 결과 해석이 안됨", "힙 스택 라이브러리 주소를 못 찾겠음", "권한 rwxp가 무슨 뜻인지 모름"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`/proc/<pid>/maps`는 리눅스 커널이 실행 중인 프로세스의 가상 주소 공간을 구간(주소 범위)별로 나열해주는 가상 파일로, 어느 주소 범위가 바이너리 코드인지, 어디가 힙/스택/공유 라이브러리인지, 각 구간이 읽기/쓰기/실행 가능한지를 한눈에 보여주는 리버싱의 가장 기본적인 "지도"이며, GDB에서는 `info proc mappings`, Pwndbg에서는 `vmmap`으로 같은 정보를 더 보기 좋게 확인할 수 있다.

## 언제 검색해야 하나
- PIE 바이너리(REV-0103)에서 ASLR로 바뀐 실제 로드 베이스 주소를 알아내야 할 때
- ROP 체인을 짜기 위해 libc가 실제로 어느 주소에 로드됐는지, 그 안에서 실행 가능한 영역이 어디인지 확인해야 할 때
- 힙 오버플로우를 디버깅하면서 `[heap]` 영역이 실제로 어디서 시작해서 얼마나 커졌는지 봐야 할 때
- GDB `vmmap`/`info proc mappings` 출력에서 `rwxp`, `r-xp` 같은 권한 표기가 무슨 뜻인지 헷갈릴 때

## 핵심 개념

### /proc/pid/maps 한 줄의 구조
각 줄은 다음 형식이다.
```
address           perms offset  dev   inode      pathname
55c1a2a3b000-55c1a2a3c000 r--p 00000000 08:01 1234567  /home/user/chall
```
- `address`: `시작주소-끝주소` (양쪽 다 16진수, 페이지 단위로 정렬됨)
- `perms`: 4글자 권한 — `r`(읽기), `w`(쓰기), `x`(실행), 넷째 자리는 `p`(private, copy-on-write) 또는 `s`(shared)
- `offset`: 매핑된 파일 내에서 이 구간이 시작하는 오프셋
- `dev`: 파일이 있는 장치 번호(`major:minor`)
- `inode`: 파일의 inode 번호. 익명 매핑(힙, 스택 등)은 `0`
- `pathname`: 매핑된 파일 경로, 또는 `[heap]`, `[stack]`, `[vdso]`, `[vvar]` 같은 특수 이름, 또는 아예 비어있음(익명 매핑)

### 특수 영역 이름
- `[heap]`: `brk`/`sbrk`로 확장되는 프로그램 힙(glibc `malloc`이 관리하는 영역, REV-0654/0655)
- `[stack]`: 메인 스레드 스택
- `[vdso]`, `[vvar]`: 커널이 제공하는 vDSO 관련 매핑(REV-0669)
- `[vsyscall]`: 오래된 커널의 vsyscall 영역(요즘은 거의 안 보이거나 비활성 상태)
- 이름이 없는 익명 매핑(`rw-p ... 00:00 0` 뒤에 경로 없음): `mmap`으로 할당된 메모리, 스레드 스택, `malloc`이 큰 청크를 위해 별도로 `mmap`한 영역 등

### 같은 파일이 여러 줄로 쪼개져 보이는 이유
같은 `libc.so.6` 하나가 보통 `r--p`(읽기 전용, ELF 헤더/rodata), `r-xp`(실행 가능, `.text`), `r--p`/`rw-p`(데이터, GOT/RELRO 이후 쓰기 가능 영역) 여러 줄로 나뉘어 나타난다. 이는 ELF 로더가 세그먼트별로 권한이 다른 매핑을 따로따로 하기 때문이다(REV-0090 Program Header와 Section Header 차이 참고). 이 여러 줄 중 가장 앞의 주소가 보통 그 라이브러리의 "베이스 주소"로 쓰인다.

### PIE/ASLR과의 관계
바이너리 자신이 PIE(REV-0103)라면 실행 파일 자체도 `/proc/pid/maps`에서 무작위 베이스 주소부터 시작하는 여러 줄로 보인다. libc, 스택, 힙, mmap 영역의 베이스 주소는 ASLR(REV-0104)에 의해 실행할 때마다 바뀌므로, 익스플로잇을 짤 때는 반드시 실행 중인 프로세스에서 `/proc/pid/maps`를 읽어 실제 주소를 확인해야 한다.

## 화면/코드에서 보이는 징후
디버거 없이 실행 중인 프로세스가 있다면 셸에서 바로 볼 수 있다.
```bash
$ cat /proc/$(pgrep chall)/maps
```
GDB/Pwndbg를 쓰는 경우 `info proc mappings` 또는 `vmmap` 명령 출력이 곧 이 파일의 내용을 재구성한 것이다.

## 가장 먼저 할 것
GDB로 프로세스를 실행 중이거나 정지시킨 상태에서 바로 매핑을 확인한다.
```bash
gdb ./chall
(gdb) starti
(gdb) info proc mappings
```
Pwndbg가 설치되어 있다면 훨씬 읽기 좋은 형태로 나온다.
```bash
pwndbg> vmmap
```

## 단계별 절차

**1) 실행 중인 프로세스의 PID 찾기**
```bash
pgrep -a chall
```

**2) 매핑 원본 확인**
```bash
cat /proc/<pid>/maps
```

**3) GDB에서 확인(디버깅 중이라면 더 편함)**
```bash
gdb -p <pid>
(gdb) info proc mappings
```

**4) Pwndbg로 색깔/가독성 있게 확인**
```bash
pwndbg> vmmap
pwndbg> vmmap heap
pwndbg> vmmap libc
```
Pwndbg의 `vmmap`은 필터 키워드를 받아 특정 이름이 포함된 매핑만 골라 보여준다.

**5) 특정 라이브러리의 베이스 주소만 뽑기**
```bash
grep libc.so /proc/<pid>/maps | head -1
```
첫 줄의 시작 주소가 그 라이브러리의 로드 베이스이며, 여기에 `readelf`/`nm`으로 얻은 함수의 파일 오프셋을 더하면 실제 실행 중 주소가 나온다(단, 라이브러리 자체가 공유 객체이므로 오프셋 계산 방식은 REV-0103의 PIE 주소 계산과 같은 원리를 따른다).

## 명령어/단축키
```bash
pgrep -a chall
cat /proc/<pid>/maps
grep heap /proc/<pid>/maps
grep libc /proc/<pid>/maps
gdb -p <pid>
  (gdb) info proc mappings
pwndbg> vmmap
pwndbg> vmmap heap
pwndbg> vmmap libc
```

## 출력 해석
```
555555554000-555555555000 r--p 00000000 08:01 1234567 /home/user/chall
555555555000-555555556000 r-xp 00001000 08:01 1234567 /home/user/chall
555555556000-555555557000 r--p 00002000 08:01 1234567 /home/user/chall
555555557000-555555558000 rw-p 00002000 08:01 1234567 /home/user/chall
555555558000-555555579000 rw-p 00000000 00:00 0       [heap]
7ffff7dab000-7ffff7dd0000 r--p 00000000 08:01 2345678 /lib/x86_64-linux-gnu/libc.so.6
7ffff7dd0000-7ffff7f45000 r-xp 00025000 08:01 2345678 /lib/x86_64-linux-gnu/libc.so.6
7ffff7f45000-7ffff7f93000 r--p 0019a000 08:01 2345678 /lib/x86_64-linux-gnu/libc.so.6
7ffff7f93000-7ffff7f97000 r--p 001e7000 08:01 2345678 /lib/x86_64-linux-gnu/libc.so.6
7ffff7f97000-7ffff7f99000 rw-p 001eb000 08:01 2345678 /lib/x86_64-linux-gnu/libc.so.6
7ffffffde000-7ffffffff000 rw-p 00000000 00:00 0       [stack]
```
- 첫 4줄이 `chall` 실행 파일 자신의 매핑으로, `555555554000`이 이 PIE 바이너리의 실제 로드 베이스다. IDA/objdump에서 본 정적 주소가 예를 들어 `0x1216`이었다면, 실행 중 실제 주소는 `0x555555554000 + 0x1216`이다.
- `r-xp` 줄이 실제로 명령어가 실행되는 `.text` 영역 — ROP 가젯을 찾을 때 이 범위 안에서만 찾아야 한다.
- `[heap]`은 `malloc` 힙이 시작하는 지점이며, 프로그램이 `malloc`을 계속 호출하면 이 영역의 끝 주소가 늘어난다.
- `libc.so.6`도 같은 패턴(r-- / r-x / r-- / rw-)으로 4~5줄로 쪼개져 있고, 가장 앞줄 주소가 libc 베이스 — 여기에 `one_gadget`이나 `system` 함수의 libc 내부 오프셋을 더해서 실제 주소를 계산한다.
- `[stack]`은 이 프로세스의 메인 스택 — 스택 버퍼 오버플로우 익스플로잇에서 리턴 주소나 카나리 위치를 계산할 기준이 된다.

## 흔한 실수
- ASLR이 켜진 상태에서 한 번 확인한 주소를 재실행 후에도 그대로 재사용하는 것 — 매 실행마다 베이스 주소가 바뀌므로, 익스플로잇 스크립트는 반드시 그때그때 leak한 주소를 기준으로 계산해야 한다.
- 같은 라이브러리의 여러 줄 중 아무 줄이나 베이스로 잡는 것 — 반드시 가장 작은(첫) 주소 줄을 베이스로 써야 하며, 이후 오프셋 계산도 그 기준으로 해야 한다.
- `r--p`(읽기 전용) 영역에 쓰기를 시도하는 익스플로잇을 짜고 왜 세그폴트가 나는지 못 찾는 것 — `perms` 컬럼에서 `w`가 없는 영역은 절대 쓸 수 없다(RELRO로 인해 읽기 전용이 된 GOT 등, REV-0102).
- 정적 링킹 바이너리인데도 `libc.so`가 매핑 목록에 있을 거라 기대하고 찾는 것 — 정적 링킹(REV-0101)이면 별도의 `libc.so.6` 매핑 자체가 없다.

## 막혔을 때 다음 체크
- vDSO/vvar 특수 매핑이 왜 있는지 궁금하다면 → REV-0669 vDSO가 무엇이고 왜 보이는지
- ASLR/PIE로 주소가 바뀌는 원리를 더 정확히 이해하고 싶다면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유, REV-0103 PIE와 주소 계산
- 힙 내부 구조(청크 헤더 등)까지 자세히 봐야 한다면 → REV-0654 tcache와 fastbin 등 glibc 힙 구조 개요
- 특정 메모리 패턴을 이 범위 안에서 검색하고 싶다면 → REV-0660 Pwndbg search로 메모리에서 패턴 찾기

## 미니 예제
```bash
$ gdb -q ./chall
(gdb) starti
(gdb) info proc mappings
process 12345
Mapped address spaces:

          Start Addr           End Addr       Size     Offset  Perms  objfile
      0x555555554000     0x555555555000     0x1000        0x0  r--p   /home/user/chall
      0x555555555000     0x555555556000     0x1000     0x1000  r-xp   /home/user/chall
      0x7ffff7dab000     0x7ffff7dd0000    0x25000        0x0  r--p   /lib/x86_64-linux-gnu/libc.so.6
(gdb) p/x 0x555555555000 - 0x555555554000
$1 = 0x1000
```
바이너리 베이스(`0x555555554000`)와 코드 실행 영역(`0x555555555000`)의 차이가 딱 `0x1000`(한 페이지)임을 확인하며 세그먼트 배치를 감을 잡는 예다.

## 관련 글
- REV-0669 — vDSO가 무엇이고 왜 보이는지
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0103 — PIE와 주소 계산
- REV-0654 — tcache와 fastbin 등 glibc 힙 구조 개요(리버싱 관점)
- REV-0660 — Pwndbg search로 메모리에서 패턴 찾기
- REV-0090 — ELF Program Header와 Section Header 차이

## 출처/검증
- `/proc/pid/maps` 필드 형식(address, perms, offset, dev, inode, pathname) 및 특수 영역 이름(`[heap]`, `[stack]`, `[vdso]` 등): Linux man-pages 프로젝트 `proc(5)` 문서 기준.
- GDB `info proc mappings`, Pwndbg `vmmap` 동작: GDB 공식 매뉴얼 및 Pwndbg 공식 문서 기준 (2026-09-08 검증).
