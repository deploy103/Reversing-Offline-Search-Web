---
id: REV-0650
title: "LD_PRELOAD로 함수 후킹해서 관찰하기"
slug: "rev-0650-ld-preload-function-hooking"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, GCC, ltrace, strace]
keywords: ["LD_PRELOAD", "함수 후킹", "dlsym RTLD_NEXT", "malloc 후킹", "공유 라이브러리 후킹"]
aliases: ["LD_PRELOAD란", "함수 후킹하는 법", "malloc free 후킹", "RTLD_NEXT란"]
symptom_keywords: ["malloc free 호출을 로그로 남기고 싶음", "바이너리 수정 없이 함수 동작을 바꾸고 싶음", "LD_PRELOAD가 안 먹힘", "setuid 바이너리에서 LD_PRELOAD 무시됨"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LD_PRELOAD` 환경변수에 공유 라이브러리(`.so`) 경로를 지정하면 동적 로더가 그 라이브러리를 다른 모든 라이브러리보다 먼저 로드해서 같은 이름의 함수를 덮어쓰게 만들 수 있으며, 이를 이용해 바이너리를 한 바이트도 수정하지 않고 `malloc`, `free`, `strcmp` 같은 함수 호출을 가로채 인자와 반환값을 관찰할 수 있다.

## 언제 검색해야 하나
- `malloc`/`free`가 정확히 어떤 크기로, 어떤 순서로 호출되는지 매번 GDB로 브레이크포인트 잡지 않고 빠르게 로그로 보고 싶을 때
- 바이너리를 패치하지 않고 특정 함수(예: 난수 생성 함수, 시간 함수)의 반환값을 고정값으로 바꿔서 재현 가능한 실행 환경을 만들고 싶을 때
- `LD_PRELOAD=./hook.so ./chall`을 실행했는데 후킹이 전혀 먹히지 않아서 원인을 찾고 싶을 때
- ltrace/strace만으로는 부족한, 함수 내부 인자 구조체까지 파싱해서 보고 싶을 때

## 핵심 개념

### 심볼 탐색 순서와 LD_PRELOAD
REV-0651에서 다루는 라이브러리 탐색 순서와 별개로, 동적 로더는 각 심볼(함수 이름)을 해석할 때 로드된 라이브러리들을 특정 순서로 뒤져서 가장 먼저 찾은 정의를 사용한다. `LD_PRELOAD`에 나열된 라이브러리는 실행 파일이 명시적으로 요구하는 `DT_NEEDED` 라이브러리들(예: `libc.so.6`)보다 먼저 로드되므로, 같은 이름의 함수가 있으면 그 라이브러리의 것이 우선 선택된다. 즉 `malloc`이라는 심볼을 요청받았을 때 로더는 preload 라이브러리에 `malloc`이 있는지부터 확인하고, 있으면 그것을 쓴다.

### 후킹 라이브러리 작성법
가로챈 함수 안에서 "진짜" 원본 함수를 호출하려면 `dlsym(RTLD_NEXT, "malloc")`을 쓴다. `RTLD_NEXT`는 "현재 라이브러리 다음 순서에 있는 정의를 달라"는 의미의 특수 핸들로, `<dlfcn.h>`에 정의되어 있다.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <dlfcn.h>
#include <stddef.h>

static void *(*real_malloc)(size_t) = NULL;

void *malloc(size_t size) {
    if (!real_malloc)
        real_malloc = dlsym(RTLD_NEXT, "malloc");
    void *ptr = real_malloc(size);
    fprintf(stderr, "[hook] malloc(%zu) = %p\n", size, ptr);
    return ptr;
}
```

컴파일과 실행은 다음과 같다.

```bash
gcc -shared -fPIC -o hook.so hook.c -ldl
LD_PRELOAD=./hook.so ./chall
```

`fprintf(stderr, ...)`를 쓰는 이유는, 만약 `stdout`에 쓰면 원래 프로그램의 출력과 뒤섞여 어느 줄이 후킹 로그인지 구분이 어려워지기 때문이다. `free`, `strcmp`, `read` 등 원하는 모든 함수에 같은 패턴을 적용할 수 있다.

### 언제 통하지 않는가
- **정적 링킹 바이너리**: `LD_PRELOAD`는 동적 로더가 심볼을 해석하는 과정에 개입하는 메커니즘이므로, 애초에 동적 링킹을 하지 않는 정적 바이너리(REV-0646)에는 효과가 없다.
- **setuid/setgid 바이너리**: 커널이 `AT_SECURE`(보조 벡터, REV-0677)를 1로 설정해 "안전 실행 모드"에 들어간 프로세스에서는 `ld.so`가 `LD_PRELOAD`, `LD_LIBRARY_PATH` 등 보안에 민감한 환경변수를 무시한다. 권한 상승에 악용되는 것을 막기 위한 장치다. glibc 내부적으로는 `__libc_enable_secure` 플래그로 이 상태를 판단한다.
- **정적 심볼로 직접 참조된 호출**: 컴파일러가 함수를 인라인하거나 내부 별칭(`GLIBC_PRIVATE` 심볼 등)으로 직접 호출한 경우 PLT를 거치지 않을 수 있어 후킹이 안 먹힐 수 있다.

### 시스템 전역 후킹 — /etc/ld.so.preload
`LD_PRELOAD` 환경변수는 프로세스 단위지만, `/etc/ld.so.preload` 파일에 라이브러리 경로를 한 줄씩 적어두면 시스템의 거의 모든 동적 링킹 프로세스에 전역으로 적용된다. 이 방식은 공격자가 루트킷을 심을 때도 악용되는 고전적인 기법이라, 침해사고 분석에서 `/etc/ld.so.preload`의 존재 여부를 점검하는 것이 표준 체크리스트에 들어간다. 리버싱/CTF 목적으로는 보통 환경변수 방식이면 충분하다.

## 화면/코드에서 보이는 징후
- `strace ./chall` 결과 초반에 `LD_PRELOAD`로 지정한 `.so`가 다른 라이브러리들보다 먼저 `openat`/`mmap`되는 것이 보임
- 후킹이 성공하면 `stderr`에 로그가 프로그램 실행과 인터리브되어 출력됨
- 후킹이 실패하면(setuid 등) 로그가 전혀 안 찍히고 원래 동작만 일어남
- `ldd ./chall` 결과에 `LD_PRELOAD`로 지정한 `.so`가 목록 맨 앞에 추가되어 보임

## 가장 먼저 할 것
간단한 후킹 라이브러리부터 만들어서 `LD_PRELOAD=./hook.so ./chall`로 테스트한다. 로그가 전혀 안 찍히면 먼저 `file ./chall`로 정적 링킹 여부를, 그다음 `ls -l ./chall`로 setuid 비트(`s` 권한)가 있는지 확인한다.

## 단계별 절차
1. 관찰하고 싶은 함수(예: `malloc`)를 감싸는 `hook.c` 작성
2. `void *(*real_func)(...)` 함수 포인터를 전역으로 선언하고, 첫 호출 시 `dlsym(RTLD_NEXT, "함수이름")`으로 초기화
3. `gcc -shared -fPIC -o hook.so hook.c -ldl`로 컴파일
4. `LD_PRELOAD=./hook.so ./chall`로 실행하며 `stderr` 로그 관찰
5. 여러 함수를 동시에 후킹하려면 같은 `.so` 안에 여러 함수를 정의하면 된다(하나의 `.so`가 여러 심볼을 오버라이드 가능)
6. 반환값이나 인자를 조작해서 프로그램 동작 자체를 바꿔보고 싶다면(예: 난수 함수 고정값 반환) `real_func` 호출 없이 바로 원하는 값을 리턴
7. 정적 바이너리나 setuid 바이너리라 안 먹히면 GDB 브레이크포인트나 `ptrace` 기반 접근(REV-0672)으로 전환

## 명령어/단축키
```bash
gcc -shared -fPIC -o hook.so hook.c -ldl
LD_PRELOAD=./hook.so ./chall
LD_PRELOAD=./hook.so gdb --args ./chall   # GDB와 결합
ls -l ./chall   # setuid 비트(s) 확인
```

## 출력 해석
- `[hook] malloc(32) = 0x55...` 같은 로그가 정상적으로 나오면 후킹이 성공한 것이고, 이 주소값을 그대로 GDB `break *주소`나 `watch` 조건에 활용할 수 있다.
- 로그가 하나도 안 나오는데 프로그램은 정상 실행된다면, 그 함수가 애초에 호출 안 됐거나(로직상 다른 경로), PLT를 거치지 않는 형태로 호출됐거나, `LD_PRELOAD`가 무시되는 상황(정적/setuid) 중 하나다.
- `strace`로 봤을 때 `hook.so`가 `openat`되지 않는다면 경로 문제(상대경로 대신 절대경로 필요)일 수 있다.

## 흔한 실수
- `hook.c`에서 `dlsym(RTLD_NEXT, ...)` 결과를 캐싱하지 않고 매번 새로 호출해서 불필요한 오버헤드를 만드는 것(치명적이진 않지만 비효율적).
- `LD_PRELOAD=hook.so`처럼 상대경로를 현재 디렉터리 기준 없이 그냥 파일명만 써서 로더가 못 찾는 것 — `./hook.so`처럼 명시적 경로를 쓰거나 절대경로를 쓰는 것이 안전하다.
- setuid 바이너리에 왜 후킹이 안 되는지 모르고 코드 문제로 착각하는 것 — `AT_SECURE`/`__libc_enable_secure`로 인한 의도된 보안 동작이다.
- 정적 링킹 바이너리(REV-0646)에 `LD_PRELOAD`를 시도하고 안 된다고 당황하는 것.

## 막혔을 때 다음 체크
- `LD_PRELOAD`가 왜 안 통하는지 라이브러리 탐색 순서 관점에서 더 알고 싶다면 → REV-0651 LD_LIBRARY_PATH와 라이브러리 탐색 순서
- 정적 바이너리라 후킹이 안 통한다면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- 후킹 대신 시스템 콜 레벨에서 관찰하고 싶다면 → REV-0662 strace 결과를 파일/네트워크 시스템콜로 필터링해서 노이즈 줄이기
- 후킹 대신 라이브러리 호출 인자를 자동으로 보고 싶다면 → REV-0111 ltrace로 라이브러리 호출 빠르게 보기, REV-0663 ltrace 결과에서 라이브러리 호출 인자 해석하기
- 커널이 언제 AT_SECURE를 켜는지 궁금하면 → REV-0677 ELF Auxiliary Vector(auxv) 개요

## 미니 예제
```bash
$ cat hook.c
#define _GNU_SOURCE
#include <stdio.h>
#include <dlfcn.h>

static int (*real_strcmp)(const char *, const char *) = NULL;

int strcmp(const char *a, const char *b) {
    if (!real_strcmp) real_strcmp = dlsym(RTLD_NEXT, "strcmp");
    int r = real_strcmp(a, b);
    fprintf(stderr, "[hook] strcmp(\"%s\", \"%s\") = %d\n", a, b, r);
    return r;
}

$ gcc -shared -fPIC -o hook.so hook.c -ldl
$ LD_PRELOAD=./hook.so ./chall
[hook] strcmp("guess", "flag{fake}") = 1
Wrong password!
```
비밀번호 비교 로직을 코드 한 줄 패치 없이 실시간으로 관찰한 예시다. 이 방식은 REV-0110에서 다룬 `strcmp` 추적을 코드 정적 분석 없이 실행만으로 빠르게 확인하는 보완 수단이 된다.

## 관련 글
- REV-0651 — LD_LIBRARY_PATH와 라이브러리 탐색 순서
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0663 — ltrace 결과에서 라이브러리 호출 인자 해석하기
- REV-0110 — strcmp strncmp memcmp 비교 추적
- REV-0677 — ELF Auxiliary Vector(auxv) 개요

## 출처/검증
- `LD_PRELOAD` 동작 원리와 `dlsym(RTLD_NEXT, ...)` 사용법: `man 8 ld.so`, `man 3 dlsym` 공식 매뉴얼 기준.
- setuid/setgid 프로세스에서 `LD_PRELOAD`가 무시되는 것(`AT_SECURE`, secure-execution mode): `man 8 ld.so` "Secure-execution mode" 항목 기준.
- `/etc/ld.so.preload` 전역 후킹 메커니즘: `man 8 ld.so` 기준 (2026-09-08 검증).
