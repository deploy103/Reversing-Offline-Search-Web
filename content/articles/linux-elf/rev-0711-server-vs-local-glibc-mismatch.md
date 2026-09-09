---
id: REV-0711
title: "서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때"
slug: "rev-0711-server-vs-local-glibc-mismatch"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, "patchelf", "pwninit"]
keywords:
  - glibc 버전 불일치
  - libc offset
  - one_gadget
  - patchelf
  - pwninit
  - LD_LIBRARY_PATH
  - ld-linux
  - symbol versioning
symptom_keywords:
  - 로컬에서는 익스플로잇이 되는데 서버에서는 안 됨
  - system 함수 오프셋이 서버와 다름
  - one_gadget 주소가 서버에서 안 맞음
  - libc 버전이 달라서 힙 구조가 다르게 보임
  - 로컬 분석 결과가 원격 서버와 다름
aliases:
  - 서버 로컬 glibc 다름
  - 원격 환경 libc 버전 차이
  - 익스플로잇이 서버에서만 실패
  - libc 오프셋 안 맞음
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
로컬에서 분석/익스플로잇이 잘 되는데 원격 서버에서만 실패한다면 가장 먼저 의심할 것은 **로컬 시스템 glibc와 서버(또는 문제 배포 Docker 이미지)의 glibc 버전이 다르다는 것**이며, CTF pwn 문제는 거의 항상 정확한 `libc.so.6`(그리고 필요하면 `ld-linux.so`)을 함께 배포하므로 반드시 그 파일을 `LD_LIBRARY_PATH`나 `patchelf`로 강제 지정해서 로컬 재현 환경을 서버와 동일하게 맞춰야 한다.

## 언제 검색해야 하나
- 로컬 `./chall`에서는 `system("/bin/sh")`가 잘 떨어지는데 원격(`nc host port`)에서는 크래시만 나거나 아무 반응이 없을 때
- `one_gadget`로 뽑은 주소를 썼는데 서버에서는 `execve` 조건(레지스터 값)이 안 맞아 실패할 때
- pwntools `libc.symbols['system']` 오프셋을 로컬 `/lib/x86_64-linux-gnu/libc.so.6` 기준으로 계산했는데 서버에서 안 맞을 때
- 힙 익스플로잇에서 tcache/fastbin 동작이 로컬과 서버에서 다르게 나타날 때(glibc 버전에 따라 malloc 내부 구조/보호 기법이 다름)

## 핵심 개념

### 왜 로컬과 서버 glibc가 다를 수 있는가
CTF 문제 서버는 특정 Docker 이미지(예: `ubuntu:20.04`, glibc 2.31)로 배포되는 경우가 많은데, 참가자의 로컬 시스템은 그보다 최신이거나 다른 배포판(예: Ubuntu 24.04, glibc 2.39)일 가능성이 높다. glibc는 배포판/버전마다 다음이 달라진다.
- libc 함수들의 **정확한 메모리 오프셋**(`system`, `execve`, `/bin/sh` 문자열, `one_gadget` 후보 주소)
- malloc 내부 구조(tcache 도입 여부, tcache `key` 필드의 안전성 검사, safe-linking 포인터 난독화 등)
- 일부 함수의 시그니처/동작 자체(예: `printf` 계열의 포맷 문자열 처리 방식 변화)

즉 로컬 시스템 libc로 오프셋을 계산해서 만든 익스플로잇 페이로드는, 서버가 다른 버전의 libc를 쓰는 순간 전혀 다른 코드 주소를 가리키게 되어 크래시하거나 아예 반응이 없어진다.

### 문제 배포 파일이 곧 "정답 환경"이다
정상적으로 출제된 pwn 문제는 서버와 **완전히 동일한** `libc.so.6`(그리고 종종 `ld-2.xx.so` 또는 `ld-linux-x86-64.so.2`)을 첨부 파일로 함께 제공한다. 이 파일이 서버 환경의 100% 정확한 사본이라고 가정하고, 로컬 분석/익스플로잇 개발은 반드시 이 libc를 강제로 사용하도록 맞춰야 한다.

## 화면/코드에서 보이는 징후
- 로컬 `python3 exploit.py LOCAL`은 성공, `python3 exploit.py REMOTE`는 실패
- GDB로 로컬에서 본 `system` 주소와 pwntools가 원격 연결에서 계산한 `system` 주소가 다름
- `checksec`이나 `file` 결과에서 로컬 시스템 libc와 배포된 `libc.so.6`의 버전 문자열이 다름

## 가장 먼저 할 것
1. 문제 zip/tar 안에 `libc.so.6`(또는 `libc-2.xx.so`)이 포함되어 있는지 확인한다. 없다면 `strings ./chall | grep -i "GLIBC_"`나 바이너리에 링크된 버전 문자열, 또는 서버 배너/Dockerfile에서 배포판 버전을 확인한다.
2. `strings libc.so.6 | grep "GNU C Library"`로 정확한 버전 문자열을 확인한다.
3. 로컬 실행/디버깅을 반드시 이 `libc.so.6`로 강제한 뒤 오프셋을 뽑는다 — 시스템 기본 libc로 계산한 오프셋은 서버에서 의미가 없다.

## 단계별 절차

**1) 배포된 libc 버전 정확히 확인**
```bash
$ strings libc.so.6 | grep "GNU C Library"
GNU C Library (Ubuntu GLIBC 2.31-0ubuntu9.16) stable release version 2.31.
```

**2) 인터프리터(ld)도 같이 배포됐는지 확인**
```bash
$ ls
chall  libc.so.6  ld-2.31.so
```
`ld-2.31.so`(인터프리터)까지 있다면 glibc 버전 자체가 시스템과 크게 달라 `LD_LIBRARY_PATH`만으로는 안 맞는 경우다(예: 시스템은 이미 glibc 2.39라 예전 `ld.so`와 심볼 버전 요구사항이 안 맞을 수 있음).

**3) pwninit / patchelf로 로컬 실행 환경을 서버와 동일하게 패치 (실전에서 가장 흔한 방법)**
```bash
$ pwninit
```
`pwninit`은 `chall`, `libc.so.6`, `ld-*.so`를 자동으로 인식해서 `patchelf --set-interpreter`와 `--set-rpath`를 적용한 `chall_patched`를 만들어준다. 수동으로 하면:
```bash
$ patchelf --set-interpreter ./ld-2.31.so ./chall
$ patchelf --set-rpath . ./chall
```

**4) pwntools에서 정확한 libc로 오프셋 계산**
```python
from pwn import *

elf = context.binary = ELF('./chall_patched')
libc = ELF('./libc.so.6')

# 로컬 테스트
p = process([elf.path])
# 원격 테스트
# p = remote('host', 1337)

leak = ...  # leak된 libc 주소
libc.address = leak - libc.symbols['puts']
system = libc.symbols['system']
binsh = next(libc.search(b'/bin/sh\x00'))
```
`ELF('./libc.so.6')` 객체를 **배포된 파일 그대로** 사용해야 한다. 시스템 `/lib/x86_64-linux-gnu/libc.so.6`를 실수로 참조하면 오프셋이 전부 어긋난다.

**5) GDB로 로컬 재현할 때도 동일한 libc 강제**
```bash
$ LD_PRELOAD=./libc.so.6 gdb ./chall_patched
```
또는 patchelf로 이미 인터프리터/rpath를 패치했다면 그냥 `gdb ./chall_patched`만으로도 올바른 libc가 로드된다. `info sharedlibrary`로 실제 로드된 libc 경로가 배포 파일과 일치하는지 항상 재확인한다.

**6) one_gadget도 반드시 그 libc 버전 기준으로 다시 계산**
```bash
$ one_gadget ./libc.so.6
0xe3afe execve("/bin/sh", r15, r12)
constraints:
  [r15] == NULL || r15 == NULL
  [r12] == NULL || r12 == NULL
```
버전이 다르면 gadget 오프셋뿐 아니라 제약 조건(어떤 레지스터가 NULL이어야 하는지)도 달라진다.

## 명령어/단축키
```bash
strings libc.so.6 | grep "GNU C Library"   # 정확한 버전 확인
pwninit                                     # 자동 패치 도구
patchelf --set-interpreter <ld경로> <바이너리>
patchelf --set-rpath <디렉터리> <바이너리>
one_gadget ./libc.so.6                      # 해당 libc 기준 gadget 재계산
```
```python
libc = ELF('./libc.so.6')          # 반드시 배포 파일 경로
libc.symbols['system']             # 정확한 오프셋
```

## 출력 해석
- `patchelf` 적용 후 `ldd ./chall_patched` 결과에서 `libc.so.6 => ./libc.so.6`처럼 로컬 상대 경로로 뜨면 성공적으로 강제된 것이다.
- pwntools `libc.address` 계산 후 `libc.symbols['system']`으로 나온 절대 주소가 GDB `p system`으로 확인한 값과 정확히 일치해야 한다. 다르면 아직 다른 libc가 로드되고 있다는 뜻이다.
- 원격 서버 응답에서 leak한 주소로 역산한 libc 베이스의 하위 12비트(페이지 정렬, `& 0xfff`)가 항상 `0`이어야 한다. `0`이 아니면 오프셋 계산 자체가 잘못됐다는 강한 신호다.

## 흔한 실수
- 로컬 디버깅에서만 시스템 libc를 쓰고 실제 exploit 페이로드는 배포된 libc 오프셋으로 만들어서, "로컬 디버깅은 이상한데 익스플로잇은 서버에서 될 것"이라고 착각하는 것 — 디버깅과 오프셋 계산에 쓰는 libc는 항상 하나로 통일해야 한다.
- `patchelf`로 원본 파일을 직접 수정해서 원본 바이너리를 잃어버리는 것 — 항상 복사본에 적용한다.
- 심볼 버전(`GLIBC_2.34`처럼 symbol versioning, REV-0653 참고) 요구사항이 다른 `ld.so`와 `libc.so.6`을 섞어 써서 `version GLIBC_2.xx not found` 에러가 나는 것 — `ld`와 `libc`는 반드시 같은 배포 세트로 맞춰야 한다.
- 서버가 ASLR을 쓰는데 leak 없이 바로 하드코딩한 로컬 주소를 원격에 쏘는 것 — 이는 glibc 버전 문제와 별개로 ASLR 문제이므로 REV-0714를 함께 참고한다.

## 막혔을 때 다음 체크
- 애초에 `.so`를 못 찾아 실행 자체가 안 된다면 → REV-0706(공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때)
- glibc 버전 차이로 실행 자체가 거부된다면 → REV-0705(glibc 버전이 안 맞아서 바이너리가 실행이 안 될 때, CONTENT_PLAN 예정 항목)
- Pwndbg 힙 명령이 이 libc 버전을 인식 못 한다면 → REV-0709(Pwndbg에서 heap 명령이 이 glibc 버전에서 지원 안 된다고 할 때)
- ASLR로 인해 매번 주소가 달라지는 것까지 겹쳐 있다면 → REV-0714(동적분석 중 ASLR 때문에 라이브러리 베이스 주소가 계속 바뀔 때)

## 미니 예제
```bash
$ ls
chall  libc.so.6  ld-2.31.so
$ pwninit
libc: ./libc.so.6
ld: ./ld-2.31.so
bin: ./chall
Executable set to executable.
Patching bin...
Removing existing patched file... skipping
Setting rpath...
Set rpath: ./
Patching interpreter: ./ld-2.31.so
$ ./chall_patched
Welcome!
```
`pwninit`으로 인터프리터와 rpath를 한 번에 맞춰 로컬 환경이 서버와 동일한 glibc를 쓰도록 강제했다.

## 관련 글
- REV-0706 — 공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때
- REV-0709 — Pwndbg에서 heap 명령이 이 glibc 버전에서 지원 안 된다고 할 때
- REV-0714 — 동적분석 중 ASLR 때문에 라이브러리 베이스 주소가 계속 바뀔 때
- REV-0712 — musl 바이너리를 glibc 전제로 분석해서 헷갈릴 때

## 출처/검증
- glibc 버전별 malloc/tcache 구조 및 심볼 오프셋 차이: glibc 공식 NEWS 파일 및 소스 변경 이력 기준.
- `patchelf`를 이용한 인터프리터/rpath 강제 지정: patchelf 공식 저장소(NixOS/patchelf) 사용법 기준.
- `pwninit` 도구의 동작(인터프리터/rpath 자동 패치): pwninit 공식 GitHub 저장소(io12/pwninit) README 기준.
- `one_gadget`을 특정 libc 파일 기준으로 재계산해야 하는 이유: one_gadget 공식 GitHub 저장소(david942j/one_gadget) 사용법 기준 (2026-09-08 확인).
