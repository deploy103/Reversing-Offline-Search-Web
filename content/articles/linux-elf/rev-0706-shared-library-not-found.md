---
id: REV-0706
title: "공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때"
slug: "rev-0706-shared-library-not-found"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, "readelf", "ldd"]
keywords:
  - error while loading shared libraries
  - cannot open shared object file
  - ldd
  - LD_LIBRARY_PATH
  - ld.so.cache
  - ldconfig
  - rpath
  - runpath
  - patchelf
  - DT_NEEDED
symptom_keywords:
  - 바이너리를 실행하면 error while loading shared libraries가 뜸
  - cannot open shared object file No such file or directory
  - ldd 결과에 not found로 표시됨
  - CTF 문제 바이너리가 자기 libc를 못 찾음
  - libc.so.6 버전이 안 맞아서 실행이 안 됨
aliases:
  - 공유 라이브러리 못 찾음
  - shared object 못 찾음
  - .so 파일 못 찾음
  - cannot open shared object file 해결
  - libc.so.6 not found
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`error while loading shared libraries: libXXX.so.N: cannot open shared object file: No such file or directory`는 동적 링커(`ld-linux.so`)가 프로그램 실행 전에 `DT_NEEDED`에 적힌 공유 라이브러리를 못 찾았다는 뜻이며, 대부분 `LD_LIBRARY_PATH=<라이브러리가_있는_디렉터리> ./프로그램` 한 줄로 즉시 해결되고, CTF에서는 문제에서 제공한 전용 `libc.so.6`을 지정해서 실행해야 하는 경우가 많다.

## 언제 검색해야 하나
- 바이너리를 그냥 `./chall`로 실행했더니 바로 `error while loading shared libraries: ...`가 뜨고 종료될 때
- `ldd ./chall`을 돌렸는데 특정 `.so` 옆에 `not found`라고 나올 때
- CTF pwn 문제에서 배포된 `libc.so.6`, `ld-2.31.so` 같은 파일을 받았는데 그냥 실행하면 시스템 libc를 써서 오프셋이 안 맞을 때
- GDB로 `run`을 눌렀는데 같은 메시지가 뜨면서 프로그램이 아예 시작도 못 할 때

## 핵심 개념

### 동적 링커가 하는 일 (REV-0101, REV-0649 참고)
ELF 실행 파일이 동적 링킹되어 있으면, 커널이 프로그램을 실행하기 전에 ELF 헤더의 `e_type`/Program Header `PT_INTERP` 세그먼트에 적힌 인터프리터(보통 `/lib64/ld-linux-x86-64.so.2`)를 먼저 실행한다. 이 인터프리터(동적 링커)가 `.dynamic` 섹션의 `DT_NEEDED` 엔트리 목록을 읽어서 필요한 모든 `.so` 파일을 순서대로 찾아 메모리에 매핑하고, 심볼을 연결(relocation)한 뒤 비로소 프로그램의 `main`을 실행한다.

이 과정에서 `.so` 파일 하나라도 못 찾으면, 프로그램이 시작조차 못 하고 다음과 같은 메시지를 표준 에러로 출력하며 즉시 종료한다.

```
./chall: error while loading shared libraries: libc.so.6: cannot open shared object file: No such file or directory
```

### 동적 링커의 검색 순서
동적 링커가 `.so`를 찾는 순서는 대략 다음과 같다(자세한 우선순위는 `man ld.so` 참고).

1. `DT_RPATH`/`DT_RUNPATH` (바이너리에 내장된 검색 경로, REV-0641 DT_* 참고)
2. `LD_LIBRARY_PATH` 환경 변수 (콜론으로 구분된 디렉터리 목록)
3. `/etc/ld.so.cache` (`ldconfig`가 미리 만들어 둔 캐시)
4. 기본 경로(`/lib`, `/usr/lib` 등)

CTF pwn 문제처럼 특정 디렉터리에 놓인 `libc.so.6`를 강제로 쓰고 싶다면 `LD_LIBRARY_PATH`나 `PT_INTERP`/`RPATH` 조작이 필요하다.

## 화면/코드에서 보이는 징후
- `./chall` 실행 시 바로 `error while loading shared libraries: <이름>: cannot open shared object file: No such file or directory` 출력 후 종료 코드 127
- `ldd ./chall` 출력에서 특정 줄이 `libc.so.6 => not found`처럼 나옴
- GDB에서 `run` 실행 시 `[Inferior 1 (process 1234) exited with code 01]`과 함께 같은 에러 메시지가 stderr로 찍힘

## 가장 먼저 할 것
1. `ldd ./chall`을 실행해서 정확히 어떤 라이브러리가 `not found`인지 먼저 확인한다.
2. 그 라이브러리 파일이 어디에 있는지(문제 배포 디렉터리 안, 또는 시스템에 설치되어 있는지) `find` / `locate`로 찾는다.
3. 있는 위치를 찾았다면 `LD_LIBRARY_PATH`로 그 디렉터리를 지정해서 다시 실행해본다.

## 단계별 절차

**1) ldd로 정확한 원인 파악**
```bash
$ ldd ./chall
        linux-vdso.so.1 (0x00007ffee6bfd000)
        libc.so.6 => not found
        /lib64/ld-linux-x86-64.so.2 (0x00007f2a3c001000)
```
`not found`가 뜬 줄이 원인이다. 이름과 버전(`libc.so.6`)을 정확히 메모한다.

**2) 필요한 파일이 어디 있는지 확인**
```bash
$ find . -maxdepth 1 -iname "libc*"
./libc.so.6
$ find . -maxdepth 1 -iname "ld-*"
./ld-2.31.so
```
CTF에서는 문제 압축파일 안에 `libc.so.6`, 때로는 `ld-linux-x86-64.so.2`(또는 `ld-2.31.so`)까지 같이 배포하는 경우가 많다. 서버가 사용하는 실제 libc와 로컬 시스템 libc가 다르면 익스플로잇 오프셋이 안 맞기 때문에, 반드시 배포된 libc를 강제로 쓰도록 해야 한다.

**3) LD_LIBRARY_PATH로 임시 실행 (가장 빠른 방법)**
```bash
$ LD_LIBRARY_PATH=. ./chall
```
현재 디렉터리(`.`)에 있는 `libc.so.6`을 우선 사용하게 만든다. 세션 한정으로만 적용되고 원본 파일은 건드리지 않아 가장 안전하다.

**4) 인터프리터까지 다른 버전을 강제하고 싶다면 (glibc 버전 자체가 다를 때)**
```bash
$ ./ld-2.31.so --library-path . ./chall
```
동적 링커 자체를 직접 실행하며 `--library-path`로 검색 경로를 지정하는 방법이다. 배포된 `libc`와 `ld`의 버전이 시스템 것과 크게 다를 때(REV-0705, REV-0711 참고) 이 방법이 더 확실하다.

**5) GDB/Pwndbg에서 디버깅할 때도 동일하게 적용**
```bash
$ LD_LIBRARY_PATH=. gdb ./chall
```
또는 GDB 안에서:
```gdb
(gdb) set environment LD_LIBRARY_PATH=.
(gdb) run
```
pwntools를 쓴다면 `process(['./ld-2.31.so', '--library-path', '.', './chall'])`처럼 실행 커맨드 자체를 인터프리터 경유로 바꾸거나, `pwninit` 같은 도구로 자동으로 rpath를 패치해서 쓰는 경우가 많다.

**6) 영구적으로 바이너리 자체를 패치하고 싶다면 (선택)**
```bash
$ patchelf --set-interpreter ./ld-2.31.so ./chall
$ patchelf --set-rpath . ./chall
```
`patchelf`로 `PT_INTERP`와 `RPATH`를 바이너리에 직접 새겨 넣으면 이후에는 환경 변수 없이 `./chall`만으로 항상 지정한 libc를 쓴다. 원본을 보존하고 싶다면 복사본에 적용한다.

## 명령어/단축키
```bash
ldd ./chall                              # 어떤 .so가 not found인지 확인
LD_LIBRARY_PATH=. ./chall                # 현재 디렉터리 라이브러리 우선 사용
./ld-2.31.so --library-path . ./chall    # 인터프리터까지 직접 지정
patchelf --set-interpreter <ld경로> <바이너리>
patchelf --set-rpath <디렉터리> <바이너리>
readelf -d ./chall | grep NEEDED         # 바이너리가 요구하는 라이브러리 목록
```

## 출력 해석
- `ldd`에서 `libc.so.6 => not found`처럼 화살표 뒤가 없으면 검색 경로 어디에서도 못 찾은 것이고, `libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x...)`처럼 경로가 붙어 있으면 정상적으로 찾은 것이다.
- `readelf -d ./chall | grep NEEDED`로 나오는 `(NEEDED) Shared library: [libc.so.6]` 목록이 실제로 링커가 찾아야 하는 이름 목록이다. 버전 번호(예: `libc.so.6`)까지 정확히 일치해야 하며, `libc.so.6.1`처럼 임의로 이름을 바꾼 파일은 인식되지 않는다(심볼릭 링크나 `patchelf`로 정확한 이름을 맞춰야 한다).
- CTF에서 서버 원격 익스플로잇을 만들 때, 로컬에서 `LD_LIBRARY_PATH`로 지정한 libc와 실제 서버가 쓰는 libc 버전이 정확히 같아야 오프셋 계산이 맞는다. 다르면 `one_gadget`, `system` 등 함수 오프셋이 전부 어긋난다.

## 흔한 실수
- `ldd`가 `not found`라고 나온 라이브러리를 시스템에 새로 설치(`apt install`)해버리는 것 — CTF 문제는 대부분 특정 glibc 버전에 의존하는 익스플로잇이므로, 시스템 libc를 덮어쓰면 서버와 버전이 달라져서 오히려 익스플로잇이 안 맞게 된다. `LD_LIBRARY_PATH`로 로컬 지정만 하고 시스템은 건드리지 않는 게 안전하다.
- `sudo ldconfig`로 시스템 캐시에 문제 libc를 등록해버리는 것 — 시스템 전역에 영향을 주므로 다른 프로그램이 깨질 수 있다. 반드시 필요할 때만, 그리고 되돌릴 수 있게 진행한다.
- `chmod +x libc.so.6`만 해두고 실제로 `LD_LIBRARY_PATH`나 `--library-path`로 지정하지 않아서 여전히 시스템 libc가 로드되는 것을 눈치채지 못하는 것 — `ldd` 결과에서 어떤 경로의 libc가 실제로 매핑됐는지 반드시 재확인해야 한다.
- 32비트(x86) 바이너리인데 64비트 시스템에서 그냥 실행해서 나는 에러(REV-0675 multilib 참고)를 이 문제와 혼동하는 것 — 이 경우는 `error while loading shared libraries`가 아니라 `cannot execute binary file: Exec format error`가 뜬다는 점으로 구분한다.

## 막혔을 때 다음 체크
- glibc 버전이 시스템과 아예 안 맞아서 실행 자체가 안 되는 근본 원인을 더 깊이 알고 싶다면 → REV-0705(glibc 버전이 안 맞아서 바이너리가 실행이 안 될 때)
- 서버 환경과 로컬 glibc가 달라서 분석 결과가 안 맞는 상황이라면 → REV-0711(서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때)
- `LD_PRELOAD`를 같이 쓰는데 적용이 안 되는 것처럼 보인다면 → REV-0707(LD_PRELOAD가 적용이 안 되는 것처럼 보일 때)
- 동적 링커/PLT/GOT 구조 자체를 더 이해하고 싶다면 → REV-0100(PLT와 GOT 기초), REV-0101(Dynamic Linking과 Import 함수 추적)

## 미니 예제
```bash
$ ./chall
./chall: error while loading shared libraries: libc.so.6: cannot open shared object file: No such file or directory

$ ldd ./chall
        linux-vdso.so.1 (0x00007ffd1b3fe000)
        libc.so.6 => not found
        /lib64/ld-linux-x86-64.so.2 (0x00007f1234001000)

$ LD_LIBRARY_PATH=. ./chall
Welcome to the challenge!
>
```
`LD_LIBRARY_PATH=.` 한 번으로 현재 디렉터리의 `libc.so.6`를 우선 사용해 정상적으로 실행됐다.

## 관련 글
- REV-0705 — glibc 버전이 안 맞아서 바이너리가 실행이 안 될 때
- REV-0711 — 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때
- REV-0707 — LD_PRELOAD가 적용이 안 되는 것처럼 보일 때
- REV-0100 — PLT와 GOT 기초
- REV-0101 — Dynamic Linking과 Import 함수 추적

## 출처/검증
- 동적 링커 검색 순서(`RPATH`/`RUNPATH`/`LD_LIBRARY_PATH`/`ld.so.cache`): `man ld.so` (glibc 공식 man page) 기준.
- `error while loading shared libraries` 메시지와 원인: glibc 동적 링커(`ld-linux.so`) 동작 및 다수 리눅스 실전 문서 기준 (2026-09-08 확인).
- `patchelf`를 이용한 `PT_INTERP`/`RPATH` 패치: patchelf 공식 저장소(NixOS/patchelf) 사용법 기준.
