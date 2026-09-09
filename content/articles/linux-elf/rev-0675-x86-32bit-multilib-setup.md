---
id: REV-0675
title: "Linux에서 x86 32비트 바이너리 실행 환경 준비(multilib)"
slug: "rev-0675-x86-32bit-multilib-setup"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, readelf]
keywords: ["multilib", "libc6-i386", "gcc-multilib", "dpkg --add-architecture i386", "32비트 실행 환경", "ELF32 실행 안 됨"]
aliases: ["32비트 바이너리 실행 안 됨", "No such file or directory ELF 32bit", "64비트 리눅스에서 32비트 실행", "i386 라이브러리 설치"]
symptom_keywords: ["32비트 바이너리인데 실행이 안 됨", "bash: ./chall: No such file or directory 인데 파일은 있음", "gdb에서 32비트 바이너리 레지스터가 이상하게 보임", "file 결과가 ELF 32-bit인데 로컬에서 안 돌아감"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
64비트 리눅스 배포판은 기본적으로 32비트(`ELF 32-bit`) 실행 파일이 필요로 하는 32비트용 동적 링커와 `libc`를 설치해두지 않으므로, `file`로 확인한 아키텍처가 `Intel 80386`인 바이너리를 실행하려면 `dpkg --add-architecture i386`(Debian/Ubuntu) 또는 `gcc-multilib`/32비트 호환 패키지군(multilib)을 별도로 설치해야 한다.

## 언제 검색해야 하나
- `file ./chall` 결과가 `ELF 32-bit LSB executable, Intel 80386`인데 `./chall`을 실행하면 `bash: ./chall: No such file or directory`가 뜨고, 파일이 분명히 그 자리에 있는데도 이런 오류가 날 때
- `ldd ./chall`이 `libc.so.6 => not found`를 출력할 때(32비트용 `libc.so.6`이 시스템에 없는 경우)
- GDB로 32비트 바이너리를 디버깅하려는데 레지스터가 64비트 이름(`$rax` 등)으로만 보이고 이상하게 동작할 때
- CTF pwn 문제가 32비트(x86)로 나왔는데 최근 설치한 64비트 전용 Ubuntu/Kali에서 바로 실행이 안 될 때

## 핵심 개념

### "No such file or directory"인데 파일은 있다 — 진짜 원인은 인터프리터
32비트 ELF 실행 파일도 64비트 ELF와 마찬가지로 `PT_INTERP` 세그먼트에 자신을 로드할 동적 링커 경로(보통 `/lib/ld-linux.so.2`)가 박혀 있다. 커널은 실행 요청을 받으면 이 인터프리터 경로가 실제로 존재하는지 확인하는데, 64비트 전용으로 설치된 시스템에는 이 32비트 전용 링커 파일 자체가 없다. 이때 셸이 내는 오류 메시지가 "커널이 실행 파일 자체를 못 찾음"과 똑같은 `No such file or directory`라서, 처음 보면 마치 파일이 없는 것처럼 착각하기 쉽다. `readelf -l ./chall | grep interpreter`로 요구되는 인터프리터 경로를 확인하고, `ls -l /lib/ld-linux.so.2`로 실제로 그 파일이 있는지 대조해보면 원인이 명확해진다.

### multilib이란
64비트(x86-64) 리눅스 배포판이 32비트(i386/x86) 바이너리도 실행할 수 있도록, 커널의 32비트 호환 실행 지원(대부분의 x86-64 CPU와 리눅스 커널은 기본적으로 32비트 유저랜드 코드 실행을 지원)과 함께 32비트용 `libc`, `libm`, 동적 링커 등을 나란히 설치해두는 구성을 **multilib**이라 부른다. 커널 자체는 대부분 이미 32비트 실행을 지원하므로, 실제로 부족한 건 유저 공간의 32비트 라이브러리/링커 파일들이다.

### 배포판별 설치 패키지
- **Debian/Ubuntu**: 먼저 32비트 아키텍처를 활성화한 뒤 패키지를 설치해야 한다.
  ```bash
  sudo dpkg --add-architecture i386
  sudo apt update
  sudo apt install libc6:i386 libncurses5:i386 libstdc++6:i386
  ```
  컴파일까지 32비트로 하고 싶다면 `gcc-multilib`, `g++-multilib`도 추가로 설치한다.
- **Kali Linux**: 위와 동일한 `dpkg --add-architecture i386` 절차를 따르되, 최신 Kali는 배포 저장소 설정이 조금씩 바뀌므로 공식 문서의 최신 안내를 따르는 것이 안전하다.
- **CTF/pwn용으로 특히 자주 필요한 패키지**: `libc6-dbg:i386`(32비트 libc 디버그 심볼, GDB에서 libc 내부 함수를 스텝 실행할 때 필요), `libssl-dev:i386` 등 문제에서 요구하는 개별 라이브러리.

### GDB/Pwndbg에서 32비트 바이너리를 다룰 때
32비트 프로세스를 디버깅할 때는 GDB가 자동으로 32비트 레지스터 세트(`$eax`, `$ebx`, `$esp`, `$ebp`, `$eip` 등)를 사용하도록 전환한다. 다만 32비트용 GDB 자체 또는 GDB의 32비트 지원 라이브러리가 없으면 `attach`/`run`이 실패할 수 있으므로, `libc6-dbg:i386`과 함께 시스템의 GDB가 멀티아키텍처를 지원하는 빌드인지도 확인 대상이다(대부분의 리눅스 배포판 기본 GDB 패키지는 x86/x86-64를 함께 지원한다).

### pwntools/Python에서의 아키텍처 지정
익스플로잇 스크립트를 짤 때는 `pwntools`의 `context.arch = 'i386'`(또는 `context(arch='i386', os='linux')`)로 명시적으로 32비트를 지정해야 레지스터/ROP 가젯 검색/`shellcraft` 출력이 올바르게 32비트 기준으로 동작한다.

## 화면/코드에서 보이는 징후
- `file ./chall` → `ELF 32-bit LSB executable, Intel 80386, ...`
- `./chall` 실행 시 `bash: ./chall: No such file or directory` (파일은 실재)
- `ldd ./chall` → `./lib/ld-linux.so.2: No such file or directory` 또는 `libc.so.6 => not found`
- `readelf -l ./chall | grep interpreter` 결과 경로가 실제로 시스템에 없음

## 가장 먼저 할 것
`file ./chall`로 32비트임을 확인한 뒤, `readelf -l ./chall | grep -A1 INTERP`로 요구되는 인터프리터 경로를, `ls -l <그 경로>`로 실제 존재 여부를 확인한다. 없으면 바로 multilib 패키지 설치로 넘어간다.

## 단계별 절차
1. `file ./chall`로 `Intel 80386`(32비트) 여부 확인
2. `readelf -l ./chall | grep interpreter`로 필요한 동적 링커 경로 확인 (보통 `/lib/ld-linux.so.2`)
3. `ls -l /lib/ld-linux.so.2` 또는 `ls -l /lib/i386-linux-gnu/`로 32비트 링커/라이브러리 유무 확인
4. 없으면 Debian/Ubuntu 계열에서 아키텍처 추가 및 설치
   ```bash
   sudo dpkg --add-architecture i386
   sudo apt update
   sudo apt install libc6:i386 libncurses5:i386
   ```
5. 다시 `./chall` 실행해서 정상 동작 확인
6. GDB로 디버깅해야 한다면 그대로 `gdb ./chall` 실행 — 최신 GDB는 대상 ELF의 클래스(`ELFCLASS32`)를 보고 자동으로 32비트 모드로 전환한다
7. 컴파일까지 필요하면 `gcc-multilib` 설치 후 `gcc -m32 -o test test.c`로 검증

## 명령어/단축키
```bash
file ./chall
readelf -l ./chall | grep -A1 interpreter
ldd ./chall
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install libc6:i386 libncurses5:i386 gcc-multilib
gdb ./chall
```
pwntools:
```python
context.arch = 'i386'
context.os = 'linux'
```

## 출력 해석
`readelf -l ./chall`에서:
```
INTERP         0x000154 0x08049154 0x08049154 0x00013 0x00013 R   0x1
      [Requesting program interpreter: /lib/ld-linux.so.2]
```
`[Requesting program interpreter: /lib/ld-linux.so.2]`가 바로 커널이 실행 시 찾는 경로다. 이 경로가 로컬 시스템에 없으면 셸이 "파일을 못 찾는다"는 오류를 내는 진짜 이유가 여기 있다는 것이 확정된다. `libc6:i386` 설치 후에는 `/lib/i386-linux-gnu/libc.so.6`, `/lib/ld-linux.so.2` 경로에 실제 파일이 생긴다.

## 흔한 실수
- `No such file or directory`를 보고 파일 경로나 실행 권한(`chmod +x`) 문제로 오해해서 엉뚱한 곳을 고치는 것 — 32비트 바이너리라면 항상 인터프리터 존재 여부부터 확인해야 한다.
- `apt install libc6-i386`처럼 아키텍처 접미사(`:i386`) 없이 옛날 패키지명을 그대로 시도해서 최신 배포판에서 패키지를 못 찾는 것 — `dpkg --add-architecture i386` 방식이 현재 Debian/Ubuntu 표준이다.
- `dpkg --add-architecture i386` 후 `apt update`를 빼먹고 바로 `apt install`을 시도해서 "Unable to locate package" 오류를 만나는 것.
- 32비트 바이너리인 걸 눈치채지 못하고 GDB에서 계속 64비트 레지스터(`$rax`)로 값을 확인하려다 이상한 값만 보는 것 — 32비트 프로세스에서는 `$eax`, `$ebx` 등 32비트 이름을 써야 한다.
- CPU가 실제로 32비트 실행을 지원하지 않는 특수 환경(일부 클라우드 인스턴스, ARM 기반 서버 등)에서 multilib을 설치해도 커널/CPU 자체가 32비트 유저랜드를 지원하지 않아 여전히 실행이 안 되는 경우를 구분하지 못하는 것 — 이 경우 x86 호환 VM/컨테이너를 별도로 준비해야 한다.

## 막혔을 때 다음 체크
- 32비트 ELF의 헤더/인터프리터 구조 자체가 헷갈리면 → REV-0649 ELF Interpreter(ld-linux.so)가 하는 일
- `LD_LIBRARY_PATH`로 특정 라이브러리 경로를 지정하는 방법이 필요하면 → REV-0651 LD_LIBRARY_PATH와 라이브러리 탐색 순서
- 공유 라이브러리 자체를 분석해야 한다면 → REV-0652 공유 라이브러리(.so) 자체를 분석 대상으로 다루기

## 미니 예제
```bash
$ file ./chall
chall: ELF 32-bit LSB executable, Intel 80386, version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux.so.2, ...

$ ./chall
bash: ./chall: No such file or directory

$ readelf -l ./chall | grep interpreter
      [Requesting program interpreter: /lib/ld-linux.so.2]

$ ls -l /lib/ld-linux.so.2
ls: cannot access '/lib/ld-linux.so.2': No such file or directory

$ sudo dpkg --add-architecture i386
$ sudo apt update
$ sudo apt install -y libc6:i386
$ ./chall
사용법: ./chall <input>
```
32비트 링커가 없어서 나던 "No such file or directory"가 `libc6:i386` 설치 이후 정상적으로 프로그램 자체의 사용법 메시지로 바뀐 것을 확인할 수 있다.

## 관련 글
- REV-0649 — ELF Interpreter(ld-linux.so)가 하는 일
- REV-0651 — LD_LIBRARY_PATH와 라이브러리 탐색 순서
- REV-0652 — 공유 라이브러리(.so) 자체를 분석 대상으로 다루기

## 출처/검증
- ELF `PT_INTERP` 세그먼트와 커널의 인터프리터 경로 해석 방식: System V ABI 및 ELF Specification 기준.
- Debian/Ubuntu의 `dpkg --add-architecture`를 이용한 multiarch(멀티아키텍처) 패키지 설치 절차: Debian 공식 위키(Multiarch/HOWTO) 및 Ubuntu 공식 문서 기준 (2026-09-09 검증).
