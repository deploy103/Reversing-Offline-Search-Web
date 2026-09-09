---
id: REV-0669
title: "vDSO가 무엇이고 왜 보이는지"
slug: "rev-0669-vdso-explained"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, readelf]
keywords: ["vDSO", "linux-vdso.so.1", "virtual dynamic shared object", "AT_SYSINFO_EHDR", "vsyscall"]
aliases: ["vdso란", "linux-vdso.so.1 정체", "info sharedlibrary vdso", "vmmap vdso"]
symptom_keywords: ["gdb info sharedlibrary에 linux-vdso.so.1이 뜸", "vmmap에 vdso 영역이 있음", "ldd 결과에 linux-vdso.so.1 표시", "vdso가 악성코드인지 궁금함"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`linux-vdso.so.1`은 리눅스 커널이 모든 프로세스의 주소 공간에 자동으로 매핑해주는 아주 작은 "가짜 공유 라이브러리"로, `gettimeofday`, `clock_gettime`, `getcpu` 같은 자주 호출되는 몇몇 시스템 콜을 실제 커널 트랩 없이 유저 공간에서 빠르게 처리하기 위한 것이며, GDB나 `/proc/pid/maps`에서 이게 보인다고 해서 악성 코드나 후킹이 주입된 게 아니다.

## 언제 검색해야 하나
- GDB `info sharedlibrary` 목록에 내가 링크하지도 않은 `linux-vdso.so.1`이 나와서 "이게 왜 여기 있지?"라는 의문이 들 때
- `cat /proc/<pid>/maps`나 pwndbg `vmmap` 결과에 `[vdso]`, `[vvar]` 같은 이름의 특이한 영역이 보일 때
- `ltrace`/`strace`로 시스템 콜을 추적하다가 `gettimeofday`나 `clock_gettime` 같은 함수가 실제 `strace`에는 안 잡히는데 프로그램은 시간 값을 얻어오는 걸 보고 헷갈릴 때

## 핵심 개념

### vDSO(virtual Dynamic Shared Object)란
일반적인 시스템 콜은 `syscall`(REV-0077) 명령으로 유저 모드에서 커널 모드로 컨텍스트 스위치가 일어나는데, 이 전환에는 상당한 오버헤드가 있다. 그런데 `gettimeofday`, `clock_gettime`, `time`, `getcpu`처럼 아주 자주 호출되고 커널의 복잡한 권한 검사가 필요 없는 함수들은, 커널이 미리 계산해서 공유 메모리(`[vvar]`)에 채워둔 값을 유저 공간 코드가 그냥 읽기만 하면 끝나는 경우가 많다. 커널은 이런 함수들의 코드를 담은 작은 ELF 공유 객체를 만들어서 **모든 프로세스의 주소 공간에 자동으로 매핑**해주는데, 이것이 vDSO다. glibc는 이 함수들을 호출할 때 실제 `syscall` 명령 대신 이 vDSO 안의 코드를 직접 호출하도록 최적화되어 있다.

### vsyscall과의 차이 — 더 오래된 메커니즘
vDSO 이전에는 `vsyscall`이라는 더 단순한 메커니즘이 있었다. `vsyscall`은 고정된 커널 주소(`0xffffffffff600000` 근방)에 몇 개의 함수(`gettimeofday`, `time`, `getcpu`)를 항상 같은 위치에 매핑해두는 방식이었는데, ASLR(REV-0104)을 무력화하는 고정 주소라는 보안 문제 때문에 대부분 deprecated되었고, 최신 커널에서는 실행은 되지만 실제로는 진짜 시스템 콜로 트랩하도록 바뀌었거나 아예 비활성화되어 있다. 반면 vDSO는 매핑 위치가 ASLR의 영향을 받아 실행마다 바뀐다.

### 어떻게 프로세스에 알려지나 — AT_SYSINFO_EHDR
커널은 `execve` 시 프로세스에게 auxiliary vector(REV-0677 참고)라는 초기화 정보 배열을 넘겨주는데, 이 안의 `AT_SYSINFO_EHDR` 항목이 vDSO ELF 이미지가 매핑된 주소를 가리킨다. 동적 링커(`ld-linux.so.2`, REV-0649)는 부팅 초기에 이 값을 읽어 `linux-vdso.so.1`이라는 이름으로 마치 진짜 공유 라이브러리를 로드한 것처럼 심볼 테이블에 등록한다. 그래서 `ldd`나 GDB `info sharedlibrary`에 다른 `.so`들과 나란히 나열되는 것이다.

### 리버싱 관점에서의 의미
- 정상적인 커널 동작이므로, `linux-vdso.so.1`이 보인다고 인젝션이나 후킹을 의심할 필요는 없다.
- `strace`(REV-0112)로 `gettimeofday`/`clock_gettime` 호출을 추적했는데 실제 시스템 콜 로그에는 안 잡히는 경우가 있다 — vDSO 경로를 탄 호출은 커널 트랩 자체가 없으므로 `strace`가 볼 수 없기 때문이다(이때는 vDSO를 우회하도록 강제하는 별도 방법이나 `ltrace`가 필요할 수 있다).
- 타이밍 기반 안티 디버깅(예: `clock_gettime` 두 번 호출해서 그 사이 시간을 재는 방식)을 분석할 때, 실제로 호출되는 코드가 바이너리 안이 아니라 vDSO 영역 안에 있다는 걸 알아야 GDB에서 `step`으로 따라 들어갔을 때 헷갈리지 않는다.

## 화면/코드에서 보이는 징후
```
$ cat /proc/$(pgrep chall)/maps | tail -5
7ffe12345000-7ffe12346000 r--p 00000000 00:00 0                          [vvar]
7ffe12346000-7ffe12348000 r-xp 00000000 00:00 0                          [vdso]
7ffe12348000-7ffe1234a000 r--p 00000000 00:00 0                          [vvar_vclock]
7ffe1234a000-7ffe1234b000 r--p 00000000 08:01 1234567                    /lib/x86_64-linux-gnu/libc.so.6
7ffffXXXX000-7ffffXXXX000 rw-p 00000000 00:00 0                          [stack]
```
`[vdso]`, `[vvar]` 같은 이름의 영역이 파일 경로 없이 나타난다.

```
(gdb) info sharedlibrary
From                To                  Syms Read   Shared Object Library
0x00007ffff7fc7000  0x00007ffff7fc9... Yes         linux-vdso.so.1
0x00007ffff7d9c000  0x00007ffff7f2... Yes         /lib/x86_64-linux-gnu/libc.so.6
```

## 가장 먼저 할 것
낯선 `linux-vdso.so.1`을 발견했다면, 먼저 이것이 정상적인 커널 매핑인지만 확인하고 넘어간다.
```bash
cat /proc/$(pgrep -f chall)/maps | grep -E "vdso|vvar"
```
`[vdso]` 항목이 실행 파일 경로가 아니라 대괄호로 표시된 특수 영역으로 나온다면 정상이다.

## 단계별 절차

**1) 프로세스 메모리 맵에서 vDSO 위치 확인**
```bash
cat /proc/<pid>/maps | grep vdso
```

**2) GDB에서 공유 라이브러리 목록 확인**
```bash
gdb ./chall
(gdb) starti
(gdb) info sharedlibrary
```

**3) vDSO 안의 함수 직접 살펴보기(선택)**
```bash
(gdb) info proc mappings
(gdb) x/20i <vdso 시작주소>
```
`__vdso_gettimeofday`, `__vdso_clock_gettime` 같은 심볼이 vDSO 안에 존재하며, GDB가 이 영역의 심볼을 읽어올 수 있으면 이름까지 보인다.

**4) 실제로 vDSO를 타는지 strace로 재확인**
```bash
strace -e trace=gettimeofday,clock_gettime ./chall
```
vDSO 경로로 처리되면 실제 커널 시스템 콜 로그가 안 찍히거나, glibc/커널 버전에 따라 일부만 찍힐 수 있다. 이 차이 자체가 vDSO가 실제로 동작 중이라는 증거다.

## 명령어/단축키
```bash
cat /proc/<pid>/maps | grep -E "vdso|vvar"
gdb ./chall
  (gdb) info sharedlibrary
  (gdb) info proc mappings
pwndbg> vmmap
strace -e trace=gettimeofday,clock_gettime ./chall
```

## 출력 해석
```
0x00007ffff7fc7000  0x00007ffff7fc9000  Yes  linux-vdso.so.1
```
- `From`/`To`는 vDSO가 매핑된 가상주소 범위 — ASLR이 켜져 있으면 실행마다 이 범위가 바뀐다.
- `Syms Read: Yes`는 GDB가 이 영역의 ELF 헤더/심볼 테이블을 성공적으로 파싱했다는 뜻으로, `info functions`에서 `__vdso_` 접두사가 붙은 함수들을 검색할 수 있다.

## 흔한 실수
- `linux-vdso.so.1`을 링크되지 않은 미지의 라이브러리로 오인해 파일 시스템에서 찾으려는 것 — 이건 디스크상의 파일이 아니라 커널이 메모리에만 존재하도록 즉석에서 만들어 매핑하는 이미지라 `/lib`에서 아무리 찾아도 안 나온다.
- vDSO 매핑을 스택 오버플로우나 힙 오버플로우의 결과로 착각하는 것 — 이는 프로세스 시작 시 커널이 항상 만들어주는 정상 매핑이다.
- 타이밍 기반 안티 디버깅을 분석하면서 `clock_gettime` 호출을 `strace`로 못 잡았다고 "이 함수가 호출 안 됐다"고 결론 내리는 것 — vDSO를 탄 호출은 원래 `strace`에 안 보일 수 있으므로, GDB로 직접 `break clock_gettime` 또는 vDSO 진입 지점에 브레이크포인트를 거는 게 더 확실하다.

## 막혔을 때 다음 체크
- 프로세스 메모리 맵 전체 구조를 더 알고 싶다면 → REV-0670 프로세스 메모리 맵(/proc/pid/maps) 읽는 법
- vDSO 주소를 알려주는 auxv 구조 자체가 궁금하다면 → REV-0677 ELF Auxiliary Vector(auxv) 개요
- ASLR로 인해 vDSO/라이브러리 주소가 매번 바뀌는 원리가 궁금하다면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유
- 시스템 콜 자체를 더 깊이 추적하고 싶다면 → REV-0112 strace로 시스템 콜에서 힌트 찾기

## 미니 예제
```bash
$ gdb -q ./chall
(gdb) starti
(gdb) info sharedlibrary
From                To                  Syms Read   Shared Object Library
0x00007ffff7fc7000  0x00007ffff7fc9000  Yes         linux-vdso.so.1
0x00007ffff7d9c000  0x00007ffff7f9c000  Yes         /lib/x86_64-linux-gnu/libc.so.6
(gdb) info address __vdso_gettimeofday
Symbol "__vdso_gettimeofday" is at 0x7ffff7fc7900 in a file compiled without debugging.
```
`linux-vdso.so.1`이 다른 정상 라이브러리들과 나란히 나열되어 있고, 그 안의 `__vdso_gettimeofday` 심볼까지 GDB가 인식하고 있음을 확인할 수 있다 — 전형적인 정상 상태다.

## 관련 글
- REV-0670 — 프로세스 메모리 맵(/proc/pid/maps) 읽는 법
- REV-0677 — ELF Auxiliary Vector(auxv) 개요
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0649 — ELF Interpreter(ld-linux.so)가 하는 일

## 출처/검증
- vDSO의 목적과 동작(gettimeofday/clock_gettime 등 최적화, AT_SYSINFO_EHDR): Linux man-pages 프로젝트 `vdso(7)` 문서 기준.
- vsyscall과 vDSO의 차이, 고정 주소 deprecated 배경: Linux 커널 공식 문서(Documentation/x86) 및 `vdso(7)` 기준 (2026-09-08 검증).
