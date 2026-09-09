---
id: REV-0648
title: "glibc 버전별 함수 시그니처 차이 확인법"
slug: "rev-0648-glibc-version-function-signature-diff"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, readelf, objdump]
keywords: ["glibc 버전", "__isoc99_scanf", "tcache key", "safe-linking", "glibc 2.34", "malloc_printerr", "libc 버전 확인"]
aliases: ["glibc 버전 차이", "libc 버전마다 다른 함수", "glibc 몇 버전인지 확인하는 법"]
symptom_keywords: ["scanf인데 __isoc99_scanf로 보임", "free할 때 double free detected in tcache 2 메시지", "GLIBC_2.34 not found 에러", "libc 버전 안맞아서 익스플로잇이 안 먹힘"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
glibc는 버전이 올라가면서 함수 내부 구현, 심볼 이름, 힙 방어 로직, 에러 메시지가 계속 바뀌기 때문에, CTF 문제를 풀 때는 반드시 대상 바이너리가 어떤 glibc 버전으로 빌드/링크됐는지 먼저 확인하고 그 버전 기준으로 함수 동작을 해석해야 한다.

## 언제 검색해야 하나
- IDA/Ghidra에서 `scanf`를 호출한 줄 같은데 실제 심볼 이름은 `__isoc99_scanf`로 나와서 왜 다른 이름인지 궁금할 때
- `free()` 도중 `free(): double free detected in tcache 2` 같은 메시지가 나오는데 이게 어느 glibc부터 생긴 검사인지 알고 싶을 때
- 로컬에서 익스플로잇을 짰는데 원격 서버에서 `version GLIBC_2.34 not found`류 에러가 나서 버전 불일치를 의심할 때
- `pwninit`이나 `patchelf`로 특정 libc를 맞춰 써야 하는데 정확히 몇 버전을 구해야 하는지 판단이 안 설 때

## 핵심 개념

### 왜 버전을 알아야 하는가
glibc는 하나의 코드베이스가 계속 진화하는 라이브러리라서, 같은 함수 이름이라도 버전에 따라 내부 동작·보안 검사·심지어 심볼 이름 자체가 다르다. 익스플로잇 오프셋(`system` 주소와 `"/bin/sh"` 문자열 사이 거리, `one_gadget` 조건 등)은 물론이고 정적 분석 중 "이 코드가 왜 이런 검사를 하지?"를 이해하는 데도 버전 지식이 필요하다. CTF에서 흔한 실수 1위가 로컬 libc와 문제 배포 libc 버전이 달라 오프셋이 안 맞는 것이다.

### 함수 이름 자체가 바뀌는 경우 — __isoc99_ 접두사
glibc 2.7부터 C99 표준을 엄격히 준수하는 `scanf` 계열 함수가 `__isoc99_scanf`, `__isoc99_sscanf`, `__isoc99_fscanf` 라는 별도 심볼로 제공된다. 소스 코드에서 `scanf(...)`를 호출해도 컴파일 시 헤더의 매크로/별칭 처리로 실제로는 `__isoc99_scanf`가 링크된다. 그래서 `readelf --dyn-syms ./chall`이나 IDA Imports에는 `scanf`가 아니라 `__isoc99_scanf`로 보인다. 이 함수는 `%d`, `%c` 같은 포맷의 폭(width)/부호 해석을 C99 규격에 맞게 처리한다는 점만 다르고, CTF 리버싱 관점에서는 그냥 `scanf`로 취급해도 무방하다.

### 힙 방어 로직의 버전별 변화
- **2.26**: tcache(thread-local cache) 도입. `malloc`/`free`가 크기별 최대 7개(기본값)까지 스레드 로컬 단일 연결 리스트에 청크를 캐싱해 속도를 높였지만, 초기 구현에는 double-free 검사가 없어 tcache dup 공격이 매우 쉬웠다.
- **2.29**: `tcache_entry` 구조체에 `key` 필드 추가. `free()` 시 해제하려는 청크가 이미 같은 tcache bin에 들어있는지 순회 검사하고, 일치하면 `free(): double free detected in tcache 2`를 출력하며 중단한다. `struct tcache_entry { struct tcache_entry *next; struct tcache_perthread_struct *key; };` 형태다.
- **2.31~2.32**: 여러 sanity check 강화(`malloc(): invalid size (unsorted)`, `free(): invalid pointer` 등 메시지 세분화). 2.32에서 **safe-linking**이 fastbin과 tcache에 도입되어, 리스트의 `fd`(next) 포인터가 `PROTECT_PTR(pos, ptr) = ((size_t)pos >> 12) ^ (size_t)ptr` 공식으로 마스킹된다. 여기서 `pos`는 포인터가 저장된 위치(청크 자신의 주소)다. 힙 주소 leak 없이 `fd`를 조작하는 tcache poisoning이 이 시점부터 훨씬 어려워졌다.
- **2.34**: 이전까지 `libpthread.so.0`, `libdl.so.2`, `libutil.so.1`, `libanl.so.1`로 나뉘어 있던 기능이 `libc.so.6` 하나로 통합됐다. `pthread_create` 등에 `-lpthread` 없이 바로 접근 가능해졌고, `__libc_start_main`에 새 `GLIBC_2.34` 심볼 버전이 추가돼 이 버전 이상으로 빌드된 바이너리는 구버전 시스템에서 실행되지 않는다(`version GLIBC_2.34 not found` 에러의 원인).
- **2.34 전후**: `__malloc_hook`, `__free_hook`, `__realloc_hook` 같은 훅 포인터가 2.34에서 완전히 제거됐다. 이 훅을 GOT처럼 덮어써서 `system`을 호출시키는 고전 기법(House of Force 계열의 훅 오버라이트)은 2.34 이상에서 더 이상 통하지 않는다.

### 버전을 확인하는 실전 방법
가장 정확한 방법은 대상 `libc.so.6` 자체에서 얻는 것이다.

```bash
strings ./libc.so.6 | grep "GNU C Library"
./libc.so.6   # 실행 파일처럼 직접 실행하면 버전 정보를 출력한다
```

`libc.so.6`을 인자 없이 직접 실행하면 `GNU C Library (Ubuntu GLIBC 2.31-0ubuntu9.9) stable release version 2.31.` 같은 배너와 컴파일러 버전, 컴파일 옵션까지 출력해준다. 대상 실행 파일만 있고 `libc.so.6`이 없다면, `readelf --dyn-syms ./chall`에서 각 심볼 뒤에 붙은 `@GLIBC_x.y` 중 가장 높은 버전이 "이 바이너리가 최소한 요구하는 glibc 버전"이다(정확한 빌드 버전은 아닐 수 있음, REV-0653 참고).

## 화면/코드에서 보이는 징후
- IDA Imports에 `scanf` 대신 `__isoc99_scanf`, `__isoc99_sscanf`
- `free()` 크래시 메시지에 `double free detected in tcache 2`(2.29+ 신호)
- pwndbg에서 tcache의 `fd` 값이 힙 주소로 안 보이고 이상한 큰 정수로 보임(safe-linking, 2.32+ 신호)
- `objdump -T ./chall | grep GLIBC` 결과 최고 버전이 `GLIBC_2.34`(libpthread/libdl 통합 이후)
- 원격 실행 시 `/lib/x86_64-linux-gnu/libc.so.6: version 'GLIBC_2.34' not found` 에러

## 가장 먼저 할 것
CTF 배포 파일에 `libc.so.6`이 동봉되어 있다면 그 파일을 직접 실행(`./libc.so.6`)해서 버전 배너부터 확인한다. 동봉되지 않았다면 `readelf --dyn-syms ./chall`로 요구 버전을 추정하고, `libc-database` 같은 도구로 정확한 버전을 찾아 로컬에 받아둔다.

## 단계별 절차
1. 배포 파일에 `libc.so.6`이 있는지 확인
2. 있다면 `./libc.so.6` 직접 실행 또는 `strings libc.so.6 | grep "GNU C Library"`로 버전 확인
3. 없다면 `readelf --dyn-syms ./chall`로 요구되는 `GLIBC_x.y` 최댓값 확인(REV-0653)
4. `patchelf --set-interpreter ./ld-2.31.so --set-rpath . ./chall` 등으로 정확한 버전의 loader/libc를 강제 로드해서 로컬 재현 환경을 맞춘다(REV-0649 참고)
5. 힙 관련 문제라면 해당 버전에 어떤 방어(tcache key, safe-linking)가 들어있는지부터 확인하고 익스플로잇 전략을 정한다
6. 훅 기반 기법을 시도하기 전에 2.34 이상인지 확인 — 이상이면 `__free_hook` 등이 없으므로 다른 접근(FSOP, ROP 등)이 필요하다

## 명령어/단축키
```bash
./libc.so.6
strings ./libc.so.6 | grep "GNU C Library"
readelf --dyn-syms ./chall | grep GLIBC
objdump -T ./chall | grep GLIBC
patchelf --set-interpreter ./ld-2.31.so --set-rpath . ./chall
```

## 출력 해석
- `./libc.so.6` 실행 결과의 `stable release version X.Y`가 가장 신뢰할 수 있는 정확한 버전 정보다.
- `readelf --dyn-syms`에서 얻는 버전은 "최소 요구 버전"일 뿐, 실제 빌드에 쓰인 버전과 100% 일치한다는 보장은 없다(더 최신 libc에서도 오래된 버전 심볼을 그대로 쓰는 함수가 있을 수 있음, REV-0653 참고).
- `double free detected in tcache 2`처럼 메시지에 구체적 숫자/단어가 붙은 경우, 그 문구 자체가 특정 glibc 커밋에서 도입된 것이므로 검색만 해도 최소 버전을 역추적할 수 있다.

## 흔한 실수
- 로컬 Ubuntu 시스템의 libc 버전과 문제 배포 libc 버전이 다른데 그냥 로컬 걸로 디버깅해서 오프셋이 안 맞는 것.
- `__malloc_hook`/`__free_hook` 기반 익스플로잇을 2.34 이상 libc에 시도하고 왜 안 되는지 못 찾는 것 — 애초에 그 심볼이 없다.
- `__isoc99_scanf`를 보고 "이건 scanf가 아니라 다른 함수"라고 오해해서 인자 해석을 다르게 하는 것 — 사실상 scanf와 동일하게 다루면 된다.
- safe-linking이 적용된 버전에서 leak 없이 곧바로 `fd` 값을 원하는 주소로 덮어쓰려다 실패하는 것 — 힙 주소 leak이 선행되어야 한다.

## 막혔을 때 다음 체크
- `.gnu.version_r`/`.gnu.version` 구조 자체를 더 깊이 이해하고 싶다면 → REV-0653 ELF Symbol Versioning(GLIBC_2.x) 이해하기
- 특정 libc/interpreter로 강제 실행하는 구체적 방법이 필요하면 → REV-0649 ELF Interpreter(ld-linux.so)가 하는 일
- tcache 구조체와 key 필드, safe-linking을 힙 구조 관점에서 더 자세히 보려면 → REV-0654 tcache와 fastbin 등 glibc 힙 구조 개요
- 정적 링킹 바이너리에 내장된 libc 버전을 찾는 법이 필요하면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법

## 미니 예제
```bash
$ ./libc.so.6
GNU C Library (Ubuntu GLIBC 2.31-0ubuntu9.9) stable release version 2.31.
Copyright (C) 2020 Free Software Foundation, Inc.
...

$ readelf --dyn-syms ./chall | grep GLIBC | sort -t_ -k2 -V | tail -3
    12: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND __isoc99_scanf@GLIBC_2.7
    15: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND __stack_chk_fail@GLIBC_2.4
    20: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND puts@GLIBC_2.2.5
```
이 예시는 최고 요구 버전이 `GLIBC_2.7`(`__isoc99_scanf`)뿐이라 실제 빌드 버전을 정확히 특정하기엔 부족하지만, "2.7 미만 시스템에서는 절대 못 돌아간다"는 하한선은 알려준다. 정확한 버전은 동봉된 `libc.so.6`을 직접 실행해 확인해야 한다.

## 관련 글
- REV-0653 — ELF Symbol Versioning(GLIBC_2.x) 이해하기
- REV-0649 — ELF Interpreter(ld-linux.so)가 하는 일
- REV-0654 — tcache와 fastbin 등 glibc 힙 구조 개요(리버싱 관점)
- REV-0655 — glibc malloc 내부 흐름 개요(청크 헤더 수준)
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0109 — scanf fgets read 입력 추적

## 출처/검증
- `__isoc99_scanf` 계열 심볼 도입(glibc 2.7, C99 준수): glibc NEWS 및 매뉴얼 기준.
- tcache `key` 필드와 `double free detected in tcache 2` 검사(glibc 2.29): glibc 공식 저장소 커밋 로그(`malloc/malloc.c`, tcache_entry에 key 필드 추가) 기준.
- Safe-linking `PROTECT_PTR` 공식(glibc 2.32): glibc 소스 `malloc/malloc.c` 및 공개된 보안 분석 자료 기준.
- glibc 2.34의 libpthread/libdl/libutil/libanl 통합 및 `__malloc_hook` 계열 제거: Red Hat Developer 공식 블로그("Why glibc 2.34 removed libpthread") 및 glibc 2.34 NEWS 기준 (2026-09-08 검증).
