---
id: REV-0688
title: "GDB에서 No such file or directory 오류가 뜰 때"
slug: "rev-0688-gdb-no-such-file-or-directory"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["No such file or directory gdb", "PT_INTERP 없음", "ld-linux.so.2 없음", "32비트 바이너리 실행 안됨", "ENOENT exec"]
aliases: ["gdb no such file or directory", "파일 있는데 no such file", "32비트 바이너리 no such file"]
symptom_keywords: ["gdb chall 했더니 No such file or directory가 뜸", "파일이 분명히 있는데 no such file or directory", "32비트 바이너리 실행했더니 No such file or directory", "run 했더니 No such file or directory"]
source_ids: ["SRC-GDB-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`ls`로 분명히 존재하는 파일인데도 `gdb ./chall`이나 `./chall` 실행 시 `No such file or directory`가 뜬다면, 십중팔구 파일 자체가 없는 게 아니라 **그 ELF의 `PT_INTERP`(동적 링커/로더)가 가리키는 경로(예: 32비트용 `/lib/ld-linux.so.2`)가 지금 시스템에 없는 것**이며, 해결책은 `file`/`ldd`로 원인을 확인한 뒤 필요한 멀티아키텍처 라이브러리를 설치하거나 문제에서 제공된 `ld.so`를 `patchelf`로 지정해주는 것이다.

## 언제 검색해야 하나
- `ls -l chall`로는 파일이 멀쩡히 보이는데 `./chall`이나 `gdb ./chall`을 실행하면 `bash: ./chall: No such file or directory`가 뜰 때
- 64비트 시스템에서 32비트 CTF 바이너리를 처음 실행해보는데 이 오류가 뜰 때
- gdb 안에서 `run`을 쳤을 때, 또는 `core-file`/`file` 명령에서 지정한 경로에 대해 같은 오류가 뜰 때
- CTF 문제에서 별도로 제공된 `libc.so.6`, `ld-linux-x86-64.so.2`를 어떻게 써야 하는지 몰라서 헤맬 때

## 핵심 개념

### 파일이 있어도 "No such file or directory"가 뜨는 이유: PT_INTERP가 진짜 원인
동적 링킹된 ELF 실행 파일은 프로그램 헤더에 `PT_INTERP` 세그먼트를 갖고 있고, 그 안에는 커널이 프로세스를 시작하기 전에 먼저 실행해야 할 **동적 링커(인터프리터) 경로**가 문자열로 박혀 있다(보통 64비트는 `/lib64/ld-linux-x86-64.so.2`, 32비트는 `/lib/ld-linux.so.2`). 커널의 `execve()`는 대상 ELF의 `PT_INTERP` 경로를 먼저 찾아서 실행하려고 시도하는데, **이 경로가 시스템에 존재하지 않으면 커널은 `ENOENT`(No such file or directory)를 반환**한다. bash는 이 오류를 그대로 사용자에게 `bash: ./chall: No such file or directory`로 보여주기 때문에, 마치 `chall` 파일 자체가 없는 것처럼 착각하게 만든다. 이 문제는 특히 64비트 배포판에 32비트 멀티아키텍처 라이브러리가 설치되어 있지 않은 상태에서 32비트 CTF 바이너리를 실행할 때 가장 흔하게 발생한다.

### 진짜로 경로/이름이 틀린 경우와 구분하기
반대로 정말 `chall`이라는 이름의 파일이 그 디렉터리에 없거나, `gdb Chall`처럼 대소문자를 틀리거나, 상대 경로 `chall`(맨 앞에 `./` 없음)을 셸의 `PATH`에서 찾으려다 실패하는 흔한 케이스도 있다. 이 경우는 `PT_INTERP` 문제와 증상이 똑같이 보이므로, `ls -l`로 파일 존재/이름/실행 권한부터 먼저 확인해야 한다.

### GDB 안에서 발생하는 경우들
- `run`/`start`: 위의 `PT_INTERP` 문제 또는 `run`에 넘긴 인자 파일(예: `run < input.txt`)이 GDB를 실행한 셸의 현재 디렉터리 기준으로 없는 경우.
- `file ./chall`, `core-file ./core`: 경로 오타이거나, 상대 경로가 GDB 실행 당시의 작업 디렉터리 기준이라 실제 바이너리 위치와 다른 경우.

## 화면/코드에서 보이는 징후
```bash
$ ls -l chall
-rwxr-xr-x 1 user user 16728 Sep  8 10:00 chall
$ ./chall
bash: ./chall: No such file or directory
$ gdb ./chall
"/home/user/chall": No such file or directory.
```

## 가장 먼저 할 것
`file ./chall`로 ELF 클래스(32/64비트)를 확인하고, `ldd ./chall`을 실행해본다. `ldd`가 `No such file or directory`나 `not found`를 출력하면 인터프리터/라이브러리 경로 문제가 원인임이 바로 확인된다.

## 단계별 절차

**1) 파일 자체가 진짜 있는지, 실행 권한이 있는지 확인**
```bash
ls -l ./chall
file ./chall
```
`file` 출력에 `ELF 32-bit LSB pie executable` 등이 보이면 파일 자체는 정상이다.

**2) 인터프리터/라이브러리 문제인지 확인**
```bash
ldd ./chall
```
```text
./chall: /lib/ld-linux.so.2: bad ELF interpreter: No such file or directory
```
또는 그냥
```text
not a dynamic executable
```
`bad ELF interpreter: No such file or directory`가 뜨면 확정이다. `readelf -l ./chall | grep interpreter`로 어떤 경로를 요구하는지도 직접 확인할 수 있다.

**3) (32비트 바이너리인 경우) 멀티아키텍처 라이브러리 설치**
```bash
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install libc6:i386 libncurses5:i386 libstdc++6:i386
```

**4) 문제에서 제공된 전용 libc/ld.so를 써야 하는 경우**
CTF pwn 문제는 종종 특정 버전의 `libc.so.6`, `ld-*.so`를 함께 제공한다. 이때는 시스템의 인터프리터를 덮어쓰지 말고, `patchelf`로 이 바이너리 전용 인터프리터를 지정한다.
```bash
patchelf --set-interpreter ./ld-2.31.so --set-rpath . ./chall
```
또는 링커를 직접 호출하는 방식(원본 파일을 건드리지 않음):
```bash
./ld-2.31.so ./chall
```
GDB에서도 동일하게 실행 파일 대신 링커를 대상으로 넘길 수 있다:
```bash
gdb --args ./ld-2.31.so ./chall
```

**5) GDB 자체 명령에서 경로 문제라면**
```gdb
(gdb) file ./chall
```
GDB의 현재 디렉터리는 `pwd`(gdb 명령)로 확인하고, 필요하면 `cd`(gdb 명령)로 바이너리가 있는 디렉터리로 이동한다.

## 명령어/단축키
```bash
ls -l ./chall
file ./chall
ldd ./chall
readelf -l ./chall | grep interpreter
patchelf --set-interpreter ./ld-2.31.so ./chall
```
```gdb
pwd
cd /path/to/challenge
file ./chall
```

## 출력 해석
- `ldd`가 `bad ELF interpreter: No such file or directory`를 출력하면 `PT_INTERP` 경로가 시스템에 없다는 확정 증거다.
- `ldd`가 각 라이브러리 옆에 `=> not found`를 출력하면 인터프리터는 찾았지만 그 인터프리터가 요구하는 개별 공유 라이브러리(예: `libc.so.6`)가 없다는 뜻이며, 원인은 같은 계열이지만 해결책은 필요한 `.so`를 같은 디렉터리에 두고 `LD_LIBRARY_PATH=. ./chall`이나 `patchelf --set-rpath`를 쓰는 것이다.
- `readelf -l ./chall | grep interpreter`에서 나온 경로(`[Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]`)를 `ls`로 직접 확인하면 실제로 그 경로에 파일이 있는지 바로 알 수 있다.

## 흔한 실수
- "파일이 있는데 No such file or directory가 뜬다"는 모순을 이해하지 못하고 파일을 지웠다 다시 받는 등 엉뚱한 조치를 하는 것 — 원인은 거의 항상 인터프리터 경로다.
- 32비트 바이너리를 64비트 전용 배포판(멀티아키텍처 미설치)에서 그냥 실행하려는 것 — `dpkg --add-architecture i386` 없이는 애초에 안 된다.
- CTF에서 제공된 `libc.so.6`을 시스템의 `/lib/x86_64-linux-gnu/libc.so.6`에 덮어써서 시스템 전체를 망가뜨리는 것 — 반드시 `patchelf`나 `LD_LIBRARY_PATH`로 문제 디렉터리 안에서만 격리해서 써야 한다.
- `readelf -l` 출력에서 `Requesting program interpreter` 줄을 못 찾고 그냥 static 바이너리로 착각하는 것 — static 바이너리는 애초에 `PT_INTERP` 세그먼트 자체가 없다(`readelf -h`의 `Type`이 `EXEC`이고 `ldd`가 `not a dynamic executable`을 출력).

## 막혔을 때 다음 체크
- GDB에 아예 파일이 안 물려 있는 다른 오류(`No symbol table is loaded`)라면 → REV-0686 GDB에서 No symbol table is loaded 오류가 뜰 때
- 실행 자체는 됐는데 그 다음 attach 단계에서 막힌다면 → REV-0692 GDB attach가 permission denied로 실패할 때(ptrace_scope)
- ELF 헤더/프로그램 헤더 구조 자체가 궁금하면 → REV-0089 ELF 헤더 읽는 법, REV-0090 Program Header와 Section Header의 차이
- 동적 링킹 개념 자체가 헷갈리면 → REV-0101 동적 링킹 기초

## 미니 예제
```bash
$ ./chall
bash: ./chall: No such file or directory
$ file ./chall
chall: ELF 32-bit LSB pie executable, Intel 80386, ...
$ ldd ./chall
./chall: /lib/ld-linux.so.2: bad ELF interpreter: No such file or directory
$ sudo dpkg --add-architecture i386 && sudo apt update
$ sudo apt install libc6:i386
$ ./chall
Welcome to the challenge!
```
`ldd`가 `bad ELF interpreter`를 정확히 짚어준 덕분에, 파일이 없는 게 아니라 32비트용 동적 링커가 시스템에 없다는 진짜 원인을 바로 찾을 수 있었다.

## 관련 글
- REV-0686 — GDB에서 No symbol table is loaded 오류가 뜰 때
- REV-0692 — GDB attach가 permission denied로 실패할 때(ptrace_scope)
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0089 — ELF 헤더 읽는 법

## 출처/검증
- `PT_INTERP`와 커널의 `execve()` 로더 동작(인터프리터 경로 부재 시 ENOENT): System V ABI ELF 명세 및 Linux `execve(2)`/`ld.so(8)` man page 기준.
- `ldd`의 `bad ELF interpreter` 메시지: glibc 동적 링커(`ld.so`) 동작 및 다수의 CTF pwn 환경설정 가이드에서 공통적으로 보고되는 증상 기준 (2026-09-08 검증).
- `patchelf --set-interpreter`/`--set-rpath` 사용법: patchelf 공식 저장소(NixOS/patchelf) README 기준.
