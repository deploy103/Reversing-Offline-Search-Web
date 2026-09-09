---
id: REV-0677
title: "ELF Auxiliary Vector(auxv) 개요"
slug: "rev-0677-auxiliary-vector-auxv"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["auxv", "Auxiliary Vector", "AT_PHDR", "AT_ENTRY", "AT_BASE", "AT_RANDOM", "AT_SYSINFO_EHDR", "Elf64_auxv_t", "getauxval"]
aliases: ["auxv가 뭔가요", "auxiliary vector 구조", "at_phdr at_entry 차이", "procfs auxv 읽는 법"]
symptom_keywords: ["gdb info auxv 항목 뜻을 모르겠음", "proc pid auxv 파일이 뭔지 모르겠음", "getauxval 함수가 뭘 리턴하는지 모르겠음", "at_sysinfo_ehdr가 vdso랑 무슨 관계인지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Auxiliary Vector(auxv)는 커널이 `execve` 직후 스택 맨 위(환경변수 배열 다음)에 심어주는 `(타입, 값)` 쌍의 배열로, 동적 로더와 glibc가 프로그램 헤더 위치·페이지 크기·랜덤값·vDSO 주소 같은 저수준 정보를 재계산 없이 바로 알 수 있게 해준다.

## 언제 검색해야 하나
- GDB에서 `info auxv`를 쳤는데 `AT_PHDR`, `AT_BASE`, `AT_SYSINFO_EHDR` 같은 줄이 무슨 뜻인지 모를 때
- `/proc/<pid>/auxv`라는 파일을 우연히 발견했는데 이게 뭔지 궁금할 때
- glibc 소스나 CTF 익스플로잇 코드에서 `getauxval(AT_RANDOM)` 같은 함수 호출을 봤을 때
- REV-0676(AT_RANDOM과 스택 카나리)을 읽다가 auxv 자체의 전체 구조가 궁금해졌을 때
- 스택 최상단 레이아웃(`argc` → `argv[]` → NULL → `envp[]` → NULL → auxv → 문자열 데이터)을 정확히 이해하고 싶을 때

## 핵심 개념

### auxv가 존재하는 이유
전통적으로 유닉스 프로그램은 `main(int argc, char **argv, char **envp)` 형태로 인자와 환경변수만 전달받았다. 하지만 동적 로더(`ld.so`)와 glibc 초기화 코드는 그보다 훨씬 많은 정보가 필요하다 — 예를 들어 자기 자신(실행 파일)의 ELF 프로그램 헤더가 메모리 어디에 매핑됐는지, 시스템 페이지 크기가 몇 바이트인지, CPU가 어떤 기능(HWCAP)을 지원하는지, vDSO(virtual dynamic shared object)가 어디에 매핑됐는지 등이다. 이런 정보를 매번 `/proc`을 파싱하거나 시스템 콜로 재계산하면 느리고 번거롭기 때문에, 커널이 프로세스를 처음 띄우는 시점에 이미 알고 있는 값들을 스택에 미리 박아두고 넘겨준다. 이 배열이 auxv다.

### 메모리 레이아웃
프로세스가 막 시작될 때 스택 최상단은 대략 다음 순서로 배치된다(주소가 높은 곳에서 낮은 곳 방향).
```
[문자열 데이터: argv/envp가 가리키는 실제 문자열들]
[auxv[] : Elf64_auxv_t 배열, AT_NULL로 끝남]
[envp[] : char* 배열, NULL로 끝남]
[argv[] : char* 배열, NULL로 끝남]
[argc]        <- 스택 포인터가 처음 가리키는 위치 (_start 진입 시점)
```
각 auxv 엔트리는 다음과 같은 구조체다(64비트 기준).
```c
typedef struct {
    long a_type;      // AT_* 상수
    union {
        long a_val;    // 정수 값
        void *a_ptr;   // 포인터 값
        void (*a_fcn)(void); // 함수 포인터 (거의 안 씀)
    } a_un;
} Elf64_auxv_t;
```
배열의 끝은 `a_type == AT_NULL`(0)인 엔트리로 표시된다.

### 자주 보이는 AT_* 타입들
| 타입 값 | 이름 | 의미 |
|---|---|---|
| 3 | `AT_PHDR` | 실행 파일 프로그램 헤더 테이블의 메모리 주소 |
| 4 | `AT_PHENT` | 프로그램 헤더 엔트리 하나의 크기(바이트) |
| 5 | `AT_PHNUM` | 프로그램 헤더 엔트리 개수 |
| 6 | `AT_PAGESZ` | 시스템 페이지 크기(보통 4096) |
| 7 | `AT_BASE` | 동적 로더(`ld.so`) 자신이 로드된 베이스 주소 |
| 8 | `AT_FLAGS` | 예약된 플래그(현재 거의 0) |
| 9 | `AT_ENTRY` | 실행 파일의 엔트리 포인트 주소 |
| 11 | `AT_UID` / 12 `AT_EUID` | 실제/유효 사용자 ID |
| 13 | `AT_GID` / 14 `AT_EGID` | 실제/유효 그룹 ID |
| 15 | `AT_PLATFORM` | CPU 플랫폼 문자열 포인터(예: `"x86_64"`) |
| 16 | `AT_HWCAP` | CPU 기능 비트마스크(SSE, AVX 등 감지에 사용) |
| 17 | `AT_CLKTCK` | `times()` 시스템 콜의 클럭 틱 주파수 |
| 23 | `AT_SECURE` | setuid/setgid로 실행됐는지 여부(1이면 "보안 모드") |
| 25 | `AT_RANDOM` | 커널이 제공한 16바이트 난수의 주소(REV-0676 참고) |
| 31 | `AT_EXECFN` | 실행에 사용된 파일 경로 문자열의 주소 |
| 33 | `AT_SYSINFO_EHDR` | vDSO(가짜 공유 라이브러리로 매핑된 커널 코드)의 ELF 헤더 주소 |

이 중 리버싱에서 특히 자주 쓰이는 것은 `AT_PHDR`(정적 바이너리에서 프로그램 헤더를 찾을 때), `AT_BASE`(PIE/ASLR 환경에서 ld.so의 실제 로드 주소를 알아내야 할 때), `AT_RANDOM`(카나리 leak), `AT_SYSINFO_EHDR`(vDSO 안의 `__kernel_vsyscall` 등을 찾을 때)이다.

### 누가 auxv를 읽는가
- 동적 로더(`ld.so`)는 초기화 극초반에 auxv를 스캔해서 `_dl_phdr`, `_dl_phnum`, `_dl_platform`, `_dl_random` 등 내부 전역 변수를 채운다.
- glibc는 `getauxval(unsigned long type)` 함수(`<sys/auxv.h>`)를 통해 사용자 코드에서도 auxv 값을 조회할 수 있게 해준다. 예를 들어 `getauxval(AT_RANDOM)`으로 카나리 재료로 쓰인 그 16바이트 주소를 직접 얻을 수 있다.
- 정적으로 링크된 실행 파일도 `_start` 진입 시점에 스택에서 직접 auxv를 읽어 자체 초기화를 수행한다(로더가 없으므로 스스로 해야 함).

## 화면/코드에서 보이는 징후
- GDB `info auxv` 출력에 `AT_PHDR`, `AT_BASE`, `AT_RANDOM`, `AT_SYSINFO_EHDR` 등의 줄이 보인다.
- `/proc/<pid>/auxv`라는 바이너리 파일이 존재하며, `xxd`로 열면 8바이트씩(타입, 값) 쌍이 반복되다가 8개의 0(AT_NULL)으로 끝난다.
- 정적 바이너리의 `_start` 디스어셈블리 초반부에서 `[rsp]`(argc), `[rsp+8]`(argv[0])에 이어 envp와 auxv 영역을 순회하는 루프 코드가 보일 수 있다.
- 소스코드에 `getauxval(AT_...)` 또는 `__libc_csu_irel`, `_dl_aux_init` 같은 심볼이 등장하면 auxv를 다루는 코드다.

## 가장 먼저 할 것
분석 중인 바이너리가 정적 링크(static)인지, ASLR/PIE가 걸려 있는지 궁금하면 GDB에서 `break main` 후 `info auxv`를 가장 먼저 찍어본다. `AT_BASE`가 0이면 정적 바이너리(로더가 없음)이고, 0이 아니면 그 값이 `ld.so`의 실제 로드 주소다. `AT_RANDOM`을 확인해두면 이후 카나리/포인터 가드 분석에도 바로 활용할 수 있다.

## 단계별 절차

**1) GDB에서 auxv 전체 덤프**
```gdb
gdb ./chall
break main
run
info auxv
```
출력 예:
```
33   AT_SYSINFO_EHDR      System-supplied DSO's ELF header  0x7ffff7fc9000
16   AT_HWCAP              Machine-dependent CPU capability hints  0x1f8bfbff
6    AT_PAGESZ              System page size                       4096
9    AT_ENTRY               Entry point of program                 0x555555555110
11   AT_UID                  Real user ID                          1000
25   AT_RANDOM               Address of 16 random bytes             0x7fffffffe1c9
31   AT_EXECFN                File name of executable                0x7fffffffefe4
15   AT_PLATFORM               String identifying platform             0x7fffffffe1d9
```

**2) /proc/pid/auxv 원본 확인**
```bash
cat /proc/$(pgrep -n chall)/auxv | xxd
```
8바이트(타입) + 8바이트(값)이 반복되는 걸 직접 확인할 수 있다.

**3) 프로그램 자체에서 값 얻기**
```c
#include <sys/auxv.h>
#include <stdio.h>
int main(void) {
    printf("AT_RANDOM = %p\n", (void*)getauxval(AT_RANDOM));
    printf("AT_PHDR   = %p\n", (void*)getauxval(AT_PHDR));
    return 0;
}
```

**4) ld.so 실제 베이스 확인(AT_BASE 활용)**
```gdb
p/x $auxv_at_base   # gdb 버전에 따라 직접 지원 안 하면 info auxv 출력값을 그대로 사용
```
`info auxv`의 `AT_BASE` 줄에 나온 주소가 곧 `readelf -d`로 확인한 `ld-linux-x86-64.so.2`가 실제로 매핑된 시작 주소다.

**5) Pwndbg로 더 보기 좋게**
```gdb
auxv
```
일부 Pwndbg 버전은 `auxv` 별칭으로 동일한 정보를 정리해서 보여준다(없으면 GDB 기본 `info auxv` 사용).

## 명령어/단축키
```gdb
info auxv
```
```bash
cat /proc/<pid>/auxv | xxd
LD_SHOW_AUXV=1 ./chall
```
```c
#include <sys/auxv.h>
unsigned long getauxval(unsigned long type);
```

## 출력 해석
- `info auxv`의 각 줄은 "타입 번호 → 이름 → 설명 → 값" 순서로 표시된다. 값 칸이 포인터인 항목(`AT_PHDR`, `AT_RANDOM`, `AT_EXECFN`, `AT_PLATFORM`)은 그 주소를 다시 메모리에서 읽어야 실제 데이터가 나온다는 점에 주의한다.
- `AT_BASE`가 `0x0`이면 동적 로더가 관여하지 않은 정적 바이너리라는 뜻이다. 0이 아닌 값이면 PIE 여부와 무관하게 `ld.so`가 그 주소에 매핑되어 있다는 뜻이다.
- `AT_SYSINFO_EHDR`은 vDSO의 시작 주소다. `readelf -h`를 이 주소에서 직접 읽을 수는 없지만(파일이 아니라 메모리 매핑이므로) GDB의 `info sharedlibrary`나 `vmmap`(Pwndbg)로 `[vdso]` 영역과 대조하면 같은 주소임을 확인할 수 있다.
- `/proc/<pid>/auxv`를 `xxd`로 봤을 때 마지막 16바이트(8+8)가 전부 `00`이면 그것이 `AT_NULL` 종료 마커다.

## 흔한 실수
- auxv를 환경변수(`envp`)의 일부라고 착각하는 것 — envp는 `NULL` 포인터로 끝나고 그 바로 다음부터 별도의 auxv 배열이 시작된다. 둘은 서로 다른 배열이다.
- `AT_RANDOM`의 값(주소)과 그 주소가 가리키는 16바이트 데이터를 혼동하는 것 — `info auxv`에 나오는 숫자는 항상 주소이며, 실제 난수 바이트를 보려면 그 주소를 다시 덤프해야 한다.
- 모든 리눅스 프로세스에 동일한 auxv 항목이 다 존재한다고 가정하는 것 — 커널 버전, 아키텍처, 정적/동적 여부에 따라 일부 항목(`AT_SYSINFO_EHDR`은 vDSO가 없는 아키텍처/커널 설정에서는 누락 가능)은 빠질 수 있다.
- `getauxval()`이 실패 시 0을 반환할 수 있다는 걸 잊고 반환값을 곧바로 역참조하는 것 — 존재하지 않는 타입을 요청하면 0이 반환된다.

## 막혔을 때 다음 체크
- `AT_RANDOM`이 스택 카나리와 정확히 어떻게 연결되는지 더 깊이 보고 싶다면 → REV-0676 AT_RANDOM과 스택 카나리 초기화 관계
- `AT_PHDR`이 가리키는 프로그램 헤더 구조 자체가 궁금하다면 → REV-0090 ELF Program Header와 Section Header 차이
- `_start`부터 초기화가 어떻게 진행되는지 전체 흐름이 궁금하다면 → REV-0098 _start 함수 읽는 법, REV-0097 ELF Entry Point에서 main까지
- `argc`/`argv`/`envp`가 스택에서 정확히 어디에 있는지 어셈블리로 확인하고 싶다면 → REV-0108 argc argv envp를 어셈블리에서 찾는 법

## 미니 예제
```bash
$ LD_SHOW_AUXV=1 ./chall
AT_SYSINFO_EHDR: 0x7ffff7fc9000
AT_HWCAP:        1f8bfbff
AT_PAGESZ:        4096
AT_BASE:           0x7ffff7fc4000
AT_ENTRY:          0x555555555110
AT_RANDOM:          0x7fffffffe1c9
AT_EXECFN:           /home/user/chall
```
이 출력만으로도 이 바이너리가 동적 링크(`AT_BASE`가 0이 아님)이고, PIE(엔트리 주소가 `0x555...`처럼 낮은 고정 주소가 아니라 무작위 베이스 위에 얹힌 형태)임을 대략 짐작할 수 있다.

## 관련 글
- REV-0676 — AT_RANDOM과 스택 카나리 초기화 관계
- REV-0090 — ELF Program Header와 Section Header 차이
- REV-0098 — _start 함수 읽는 법
- REV-0099 — __libc_start_main이 무엇이고 main을 찾는 법
- REV-0108 — argc argv envp를 어셈블리에서 찾는 법

## 출처/검증
- `Elf64_auxv_t` 구조체 및 `AT_*` 상수 목록: `<elf.h>`/`<bits/auxv.h>` 리눅스 시스템 헤더 및 관련 문서(LWN "getauxval() and the auxiliary vector") 기준.
- auxv가 스택 최상단에 배치되는 레이아웃 및 커널이 채워 넣는 과정: Linux 커널 `fs/binfmt_elf.c`의 `create_elf_tables` 로직 기준.
- `getauxval()` API 및 `LD_SHOW_AUXV` 환경변수: glibc `man 3 getauxval`, `man 8 ld.so` 매뉴얼 기준 (2026-09-08 검증).
