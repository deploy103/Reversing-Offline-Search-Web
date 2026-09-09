---
id: REV-0641
title: "ELF Dynamic Section 태그(DT_*) 빠른 참조"
slug: "rev-0641-elf-dynamic-section-tags"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [readelf, GDB, Pwndbg]
keywords: ["DT_NEEDED", "DT_SYMTAB", "DT_STRTAB", "DT_PLTGOT", "DT_INIT", "DT_FLAGS_1", "dynamic section", ".dynamic"]
aliases: ["DT_ 태그", "dynamic section 태그", "readelf -d 해석", "동적 섹션 태그 목록"]
symptom_keywords: ["readelf -d 출력 태그가 낯섬", "DT_NEEDED가 뭔지 모름", "BIND_NOW가 뭔지 모름", "RELRO와 DT_FLAGS_1 관계"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`.dynamic` 섹션은 `(태그, 값)` 쌍의 배열(`Elf64_Dyn` 구조체 리스트)이며, 각 태그(`DT_NEEDED`, `DT_SYMTAB`, `DT_PLTGOT` 등)는 동적 링커(`ld-linux.so`)가 라이브러리를 찾고 심볼을 해석하고 재배치를 수행하는 데 필요한 정보를 하나씩 알려주는 "설정값 목록"이다.

## 언제 검색해야 하나
- `readelf -d ./chall` 출력에 나오는 태그 이름이 낯설어서 뜻을 찾아볼 때
- `checksec`이 어떻게 `RELRO`/`BIND_NOW` 상태를 판단하는지 그 근거(`DT_FLAGS`, `DT_FLAGS_1`)가 궁금할 때
- GDB가 라이브러리 베이스 주소를 어떻게 알아내는지(`DT_DEBUG`) 궁금할 때

## 핵심 개념

### Elf64_Dyn 구조체
```c
typedef struct {
    Elf64_Sxword d_tag;
    union {
        Elf64_Xword d_val;   // 정수 값 해석(크기, 플래그, 카운트 등)
        Elf64_Addr  d_ptr;   // 가상 주소 해석(테이블 시작 주소 등)
    } d_un;
} Elf64_Dyn;
```
어떤 필드로 해석할지는 태그 종류에 따라 정해져 있다. 배열은 `DT_NULL`(0) 태그로 끝난다.

### 자주 보이는 태그 목록

| 태그 | 값 | 의미 |
|---|---|---|
| `DT_NULL` | 0 | 배열의 끝 표시 |
| `DT_NEEDED` | 1 | 이 오브젝트가 필요로 하는 공유 라이브러리 이름(`.dynstr` 오프셋). 여러 개 있을 수 있음 — `readelf -d`에 `Shared library: [libc.so.6]` 형태로 나옴 |
| `DT_PLTRELSZ` | 2 | PLT 관련 재배치 테이블의 총 바이트 크기 |
| `DT_PLTGOT` | 3 | GOT(정확히는 `.got.plt`) 시작 주소 |
| `DT_HASH` | 4 | SysV 스타일 심볼 해시 테이블 주소 |
| `DT_STRTAB` | 5 | 동적 문자열 테이블(`.dynstr`) 주소 |
| `DT_SYMTAB` | 6 | 동적 심볼 테이블(`.dynsym`) 주소 |
| `DT_RELA` / `DT_REL` | 7 / 17 | 재배치 엔트리 테이블 주소(Addend 있는 버전/없는 버전) |
| `DT_STRSZ` | 10 | `.dynstr` 전체 크기 |
| `DT_SYMENT` | 11 | 심볼 테이블 엔트리 하나의 크기 |
| `DT_INIT` / `DT_FINI` | 12 / 13 | 초기화/종료 함수 주소(레거시 단일 함수 방식) |
| `DT_SONAME` | 14 | 이 오브젝트 자신의 공유 라이브러리 이름(예: `libc.so.6`) |
| `DT_RPATH` / `DT_RUNPATH` | 15 / 29 | 라이브러리 검색 경로 하드코딩(구식/신식) |
| `DT_SYMBOLIC` | 16 | 심볼 해석 시 자기 자신을 먼저 찾도록 지시 |
| `DT_PLTREL` | 20 | PLT 재배치가 `DT_REL`/`DT_RELA` 중 어떤 형식인지 |
| `DT_DEBUG` | 21 | 실행 중 동적 링커가 채우는 디버그 정보 주소. 여기를 따라가면 `r_debug`/`link_map` 연결 리스트가 나오고, **이것이 GDB/Pwndbg가 로드된 공유 라이브러리들의 베이스 주소를 알아내는 표준 경로**다 |
| `DT_JMPREL` | 23 | PLT용 재배치 테이블(`.rela.plt`) 시작 주소 |
| `DT_BIND_NOW` | 24 | 존재하면 지연 바인딩(lazy binding) 없이 시작 시 즉시 전부 바인딩 |
| `DT_INIT_ARRAY` / `DT_FINI_ARRAY` | 25 / 26 | 초기화/종료 함수 포인터 배열 주소(`.init_array`/`.fini_array`, 현대 표준 방식) |
| `DT_INIT_ARRAYSZ` / `DT_FINI_ARRAYSZ` | 27 / 28 | 위 배열들의 바이트 크기 |
| `DT_FLAGS` | 30 | `DF_ORIGIN`, `DF_SYMBOLIC`, `DF_TEXTREL`, `DF_BIND_NOW`, `DF_STATIC_TLS` 등 플래그 비트 |
| `DT_GNU_HASH` | 0x6ffffef5 | GNU 확장 해시 테이블(SysV `DT_HASH`보다 빠름, 최신 바이너리 대부분 이걸 씀) |
| `DT_VERSYM` / `DT_VERNEED` / `DT_VERDEF` | 0x6ffffff0대 | 심볼 버전 관리(`GLIBC_2.2.5` 같은 버전 문자열) 관련 |
| `DT_FLAGS_1` | 0x6ffffffb | GNU 확장 플래그. **`DF_1_NOW`가 켜져 있으면 Full RELRO의 핵심 조건 중 하나**(checksec이 이 비트를 확인) |
| `DT_RELACOUNT` | 0x6ffffff9 | `R_*_RELATIVE` 타입 재배치 개수(주로 PIE ASLR 재배치 최적화용) |

### RELRO와의 관계
`checksec`이 `Full RELRO`라고 판정하는 조건은 두 가지가 겹칠 때다: ① 프로그램 헤더에 `GNU_RELRO` 세그먼트가 있고(GOT를 매핑 후 읽기 전용으로 재설정할 범위 지정), ② `.dynamic`에 `DT_FLAGS_1`의 `DF_1_NOW` 비트(또는 `DT_BIND_NOW`)가 설정되어 있어 시작 시 모든 GOT 엔트리가 즉시 채워짐(eager binding). 둘 중 `GNU_RELRO`만 있고 즉시 바인딩이 없으면 `Partial RELRO`다(REV-0102 참고).

## 화면/코드에서 보이는 징후
- `readelf -d ./chall` 실행 시 `Tag Type Name/Value` 표 형태로 위 태그들이 나열됨
- GDB에서 `info sharedlibrary` 또는 Pwndbg `piebase`가 라이브러리 베이스를 보여줄 때, 내부적으로 `DT_DEBUG` → `r_debug` → `link_map` 체인을 따라간 결과

## 가장 먼저 할 것
`readelf -d ./chall`을 한 번 실행해서 `NEEDED`(필요 라이브러리 목록), `BIND_NOW`/`FLAGS_1` 유무(RELRO 판단), `SONAME`(자기 자신이 라이브러리인 경우)을 먼저 확인한다.

## 단계별 절차

**1) 전체 동적 섹션 덤프**
```bash
readelf -d ./chall
```

**2) 필요 라이브러리만 추출**
```bash
readelf -d ./chall | grep NEEDED
```

**3) RELRO/BIND_NOW 관련 플래그만 확인**
```bash
readelf -d ./chall | grep -E 'FLAGS|BIND_NOW'
checksec --file=./chall
```

**4) GDB에서 DT_DEBUG를 통해 로드된 라이브러리 베이스 확인**
```gdb
info sharedlibrary
```
Pwndbg에서는 더 간단히:
```gdb
piebase
vmmap
```

## 명령어/단축키
```bash
readelf -d ./chall
readelf -d ./chall | grep NEEDED
checksec --file=./chall
```
GDB/Pwndbg: `info sharedlibrary`, `piebase`, `vmmap`

## 출력 해석
`readelf -d` 예시:
```
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x000000000000000c (INIT)               0x1000
 0x0000000000000019 (INIT_ARRAY)         0x3db8
 0x000000000000001b (INIT_ARRAYSZ)       8 (bytes)
 0x000000006ffffffb (FLAGS_1)            Flags: NOW PIE
```
`FLAGS_1`에 `NOW`가 보이면 즉시 바인딩(Full RELRO의 필요조건 충족), `PIE`가 보이면 이 오브젝트가 Position-Independent Executable임을 나타낸다.

## 흔한 실수
- `DT_NEEDED`에 나열된 이름이 실제 파일 경로라고 착각하는 것 — 이건 단순 이름(`libc.so.6`)일 뿐이고, 실제 파일 위치는 런타임에 `ld.so`가 `LD_LIBRARY_PATH`, `/etc/ld.so.cache`, 기본 경로 등을 뒤져서 찾는다.
- `DT_BIND_NOW` 태그가 없으면 무조건 lazy binding이라고 단정하는 것 — `DT_FLAGS_1`의 `DF_1_NOW` 비트로도 동일한 효과를 낼 수 있어 두 곳을 모두 확인해야 한다.
- `.dynamic` 섹션이 스트립되면 아예 동적 링킹 정보가 없다고 착각하는 것 — `.dynamic`은 런타임에 반드시 필요한 정보라 일반적인 `strip` 명령으로는 제거되지 않는다(제거하면 바이너리가 실행 자체가 안 됨).

## 막혔을 때 다음 체크
- RELRO 자체의 의미와 pwn 관점 영향이 궁금하면 → REV-0102 RELRO가 리버싱에 의미하는 것.
- PLT/GOT와 `DT_PLTGOT`/`DT_JMPREL`의 관계가 궁금하면 → REV-0100 PLT와 GOT 기초.
- 섹션 이름 전반이 궁금하면 → REV-0640 ELF Section 이름 관례 사전.

## 미니 예제
```bash
$ readelf -d ./chall | head -8
Dynamic section at offset 0x2dd8 contains 24 entries:
  Tag        Type                         Name/Value
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x000000000000000c (INIT)               0x1000
 0x000000000000000d (FINI)               0x11f8
 0x0000000000000019 (INIT_ARRAY)         0x3db8
 0x000000006ffffef5 (GNU_HASH)           0x3b8
 0x0000000000000006 (SYMTAB)             0x3d8
```
`NEEDED`로 `libc.so.6` 하나만 링크되어 있고, `GNU_HASH`가 있으므로 최신 방식 해시 테이블을 사용하는 바이너리임을 알 수 있다.

## 관련 글
- REV-0100 — PLT와 GOT 기초
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0102 — RELRO가 리버싱에 의미하는 것
- REV-0640 — ELF Section 이름 관례 사전(.text .rodata .bss 등)

## 출처/검증
- `Elf64_Dyn` 구조체 및 `DT_*` 태그 정의: System V Application Binary Interface(generic ABI) "Dynamic Section" 챕터 및 Linux Foundation Referenced Specifications(refspecs.linuxbase.org, ELF gABI ch5.dynamic) 기준 (2026-09-08 검증).
- `DT_GNU_HASH`, `DT_FLAGS_1`(`DF_1_NOW`) 등 GNU 확장 태그: GNU Binutils/glibc 동적 로더 구현 및 RELRO 관련 배포판 문서 기준.
- `DT_DEBUG`와 `r_debug`/`link_map`을 통한 라이브러리 베이스 추적: glibc `elf/link.h`, `elf/rtld.c` 및 GDB `solib-svr4.c` 구현 개념 기준.
