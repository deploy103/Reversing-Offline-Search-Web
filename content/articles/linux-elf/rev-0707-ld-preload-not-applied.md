---
id: REV-0707
title: "LD_PRELOAD가 적용이 안 되는 것처럼 보일 때"
slug: "rev-0707-ld-preload-not-applied"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, "ltrace", "strace"]
keywords:
  - LD_PRELOAD
  - 함수 후킹
  - symbol interposition
  - static linking
  - RTLD_NOW
  - LD_BIND_NOW
  - setuid
  - secure-execution mode
  - dlopen
symptom_keywords:
  - LD_PRELOAD로 후킹 함수를 만들었는데 원본 함수가 계속 호출됨
  - 후킹한 malloc이 안 불림
  - LD_PRELOAD 지정했는데 아무 효과가 없음
  - setuid 바이너리에 LD_PRELOAD가 무시됨
  - 정적 바이너리에 LD_PRELOAD가 안 먹힘
aliases:
  - LD_PRELOAD 안 먹힘
  - LD_PRELOAD 후킹 실패
  - LD_PRELOAD 무시됨
  - 프리로드 후킹 안 됨
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LD_PRELOAD`로 지정한 `.so`의 함수가 호출되지 않는 원인은 거의 항상 (1) 대상 바이너리가 정적 링킹이라 애초에 동적 링커가 개입하지 않거나, (2) setuid/setgid 등 "보안 실행 모드"라서 커널/링커가 `LD_PRELOAD`를 무시하거나, (3) 후킹 함수 시그니처나 심볼 이름이 원본과 정확히 일치하지 않아 심볼 해석이 다른 곳으로 가는 것 중 하나이며, `ltrace`/`strace`로 실제 어떤 라이브러리의 함수가 불렸는지 먼저 확인하면 원인이 바로 드러난다.

## 언제 검색해야 하나
- `LD_PRELOAD=./hook.so ./chall`로 실행했는데 후킹 함수 안의 `printf`/로그가 전혀 안 찍힐 때
- `malloc`, `read` 같은 libc 함수를 가로채서 인자를 로그로 남기려 했는데 원본 동작만 그대로 일어날 때
- setuid가 걸린 바이너리를 대상으로 `LD_PRELOAD`를 걸었는데 아무 변화가 없을 때
- 후킹 `.so`를 만들었는데 컴파일은 되지만 실행 시 아무 효과가 없어서 "내가 뭘 잘못했지" 싶을 때

## 핵심 개념

### LD_PRELOAD가 동작하는 원리
`LD_PRELOAD`는 동적 링커(`ld-linux.so`)에게 "다른 모든 라이브러리보다 먼저 이 `.so`를 로드하고, 심볼 이름이 겹치면 이 `.so`의 정의를 우선 사용하라"고 지시하는 환경 변수다. 예를 들어 `hook.so` 안에 `malloc`이라는 이름의 함수를 정의해 두면, 프로그램이 `malloc`을 호출할 때 PLT/GOT(REV-0100)를 통해 실제로 연결되는 주소가 libc의 `malloc`이 아니라 `hook.so`의 `malloc`이 된다. 이 메커니즘을 **symbol interposition(심볼 가로채기)**이라 부른다.

### LD_PRELOAD가 아예 개입할 수 없는 경우 — 정적 링킹
`LD_PRELOAD`는 **동적 링커가 개입하는 과정**이다. 대상 바이너리가 `gcc -static`으로 빌드된 정적 링킹 바이너리(REV-0646 참고)라면, `malloc`이나 `read` 같은 함수의 코드가 이미 바이너리 자체에 통째로 복사되어 있고 런타임에 심볼을 다시 연결(relocation)하지 않는다. 즉 동적 링커 자체가 실행되지 않으므로 `LD_PRELOAD`가 개입할 지점이 원천적으로 없다.

```bash
$ file ./chall
./chall: ELF 64-bit LSB executable, x86-64, ... statically linked, ...
```
`file` 결과에 `statically linked`가 보이면 `LD_PRELOAD`는 애초에 통하지 않는다.

### 보안 실행 모드(secure-execution mode)에서 무시되는 경우
glibc 동적 링커는 프로세스가 "보안에 민감한" 상태로 판단되면 `LD_PRELOAD`, `LD_LIBRARY_PATH` 등 다수의 `LD_*` 환경 변수를 **의도적으로 무시**한다. 대표적으로:
- 실행 파일에 setuid/setgid 비트가 설정되어 실제 UID/GID와 유효 UID/GID(effective UID/GID)가 다른 경우
- `AT_SECURE` auxv 값이 1로 설정된 경우(예: 파일 능력(capabilities)이 설정된 바이너리)

이는 공격자가 setuid 루트 바이너리를 자신의 악성 `.so`로 후킹해서 권한 상승하는 것을 막기 위한 glibc의 보안 설계다. CTF에서 setuid 문제를 후킹으로 분석하려다 실패하는 가장 흔한 이유가 바로 이것이다.

### 심볼 이름/시그니처가 정확히 일치하지 않는 경우
`LD_PRELOAD`로 만든 함수의 **이름이 완전히 동일**해야 심볼 가로채기가 일어난다. 예를 들어 `read` 대신 실수로 `_read`나 `read2`라는 이름으로 만들었다면 아무 효과가 없다. 또한 가변인자(`printf` 계열)나 구조체를 인자로 받는 함수는 프로토타입이 미묘하게 다르면 크래시나 잘못된 값 전달로 이어질 수 있다.

## 화면/코드에서 보이는 징후
- 후킹 함수 안에 넣은 `fprintf(stderr, "hooked!\n")` 같은 디버그 출력이 전혀 안 나타남
- `strace -f -e trace=openat ./chall`로 봐도 `hook.so`가 아예 `openat`/`mmap`되지 않음
- `ltrace`로 봤을 때 여전히 libc 버전의 함수가 호출되는 것으로 보임

## 가장 먼저 할 것
1. `file ./chall`로 정적 링킹 여부부터 확인한다. `statically linked`면 `LD_PRELOAD`는 원천적으로 불가능하다.
2. `ls -l ./chall`로 setuid/setgid 비트(`rwsr-xr-x`처럼 `s`가 보이는지)가 있는지 확인한다.
3. `LD_DEBUG=libs LD_PRELOAD=./hook.so ./chall 2>&1 | grep hook.so`로 `hook.so`가 실제로 로드는 됐는지부터 확인한다.

## 단계별 절차

**1) 정적/동적 링킹 여부 확인**
```bash
$ file ./chall
./chall: ELF 64-bit LSB pie executable, x86-64, ..., dynamically linked, ...
```
`dynamically linked`가 나와야 `LD_PRELOAD`를 시도할 의미가 있다.

**2) setuid/보안 실행 모드 여부 확인**
```bash
$ ls -l ./chall
-rwsr-xr-x 1 root root 16384 ... ./chall
```
소유자 실행 권한 자리에 `s`가 보이면 setuid 바이너리다. 이 경우 `LD_PRELOAD`는 glibc 보안 정책상 무시된다. CTF 로컬 재현 목적이라면 setuid 비트를 뗀 복사본으로 먼저 분석하는 것이 현실적이다.
```bash
$ cp ./chall ./chall_nosuid
$ chmod -s ./chall_nosuid
```

**3) LD_DEBUG로 실제 로드 여부 확인 (가장 확실한 진단)**
```bash
$ LD_DEBUG=libs LD_PRELOAD=$(pwd)/hook.so ./chall 2>&1 | grep -i hook
     12345:     calling init: /home/user/hook.so
```
이 줄이 안 보이면 `.so` 파일 경로가 잘못됐거나(상대 경로 문제 — 반드시 절대 경로 또는 `$(pwd)/hook.so` 사용 권장), 애초에 보안 모드 때문에 무시된 것이다.

**4) 심볼이 올바르게 export됐는지 확인**
```bash
$ nm -D ./hook.so | grep " T malloc"
0000000000001139 T malloc
```
`T`(전역 함수, text 섹션)로 나와야 한다. `t`(로컬)나 아예 안 보이면 `static` 키워드가 붙었거나 `visibility("hidden")` 속성 때문에 export되지 않은 것이다. 컴파일 시 `-fvisibility=default`(기본값) 확인.

**5) 원본 함수를 호출해야 하는 경우 dlsym(RTLD_NEXT) 사용**
후킹 함수 내부에서 원래 동작도 수행하려면 `dlopen`/`dlsym`으로 원본 심볼을 얻어야 한다. 이 부분이 빠지면 링크 에러나 무한 재귀(자기 자신을 다시 호출)로 크래시가 난다.
```c
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>

void *malloc(size_t size) {
    static void *(*real_malloc)(size_t) = NULL;
    if (!real_malloc)
        real_malloc = dlsym(RTLD_NEXT, "malloc");
    fprintf(stderr, "[hook] malloc(%zu)\n", size);
    return real_malloc(size);
}
```

**6) ltrace/strace로 실제 어느 라이브러리의 함수가 불렸는지 교차 검증**
```bash
$ ltrace -e malloc ./chall
```
`ltrace` 출력에 함수 호출은 보이는데 후킹 로그가 안 찍히면, 심볼 자체는 연결됐지만 후킹 코드 안의 출력이 버퍼링되어 안 보이는 경우도 있다 — `stderr`는 기본적으로 버퍼링되지 않으므로 `stdout` 대신 `stderr`를 쓰거나 `fflush`를 명시한다.

## 명령어/단축키
```bash
file ./chall                                   # 정적/동적 링킹 확인
ls -l ./chall                                  # setuid/setgid 비트 확인
LD_DEBUG=libs LD_PRELOAD=$(pwd)/hook.so ./chall 2>&1 | grep hook
nm -D ./hook.so | grep " T "                   # export된 전역 심볼 확인
ltrace -e malloc+free ./chall                  # 실제 호출된 라이브러리 함수 추적
```

## 출력 해석
- `LD_DEBUG=libs` 출력에 `hook.so`가 아예 언급되지 않으면 로드 자체가 안 된 것 — 경로(상대 경로는 실행 시 작업 디렉터리 기준으로 해석되어 실패하기 쉬움) 또는 보안 모드를 의심한다.
- `nm -D`로 심볼이 `T`(전역, export)로 안 나오면 그 함수는 애초에 가로챌 대상이 될 수 없다.
- `ltrace`에서 여전히 원본 libc 주소로 호출이 잡히면, 심볼 이름이 미묘하게 다르거나(오타) 컴파일러가 해당 호출을 인라인/내장 함수로 최적화해 애초에 `call malloc` 같은 심볼 참조 자체가 코드에 없는 경우다(예: `__builtin_malloc` 최적화).

## 흔한 실수
- 상대 경로로 `LD_PRELOAD=hook.so`처럼 지정하는 것 — 셸의 현재 디렉터리가 아니라 프로그램이 내부적으로 디렉터리를 바꾸는 경우 못 찾을 수 있다. 항상 절대 경로(`$(pwd)/hook.so`)를 쓰는 게 안전하다.
- setuid 바이너리에 `LD_PRELOAD`가 안 먹히는 걸 "내 후킹 코드가 잘못됐다"고 오해하고 코드만 계속 고치는 것 — `ls -l`로 setuid 비트부터 확인해야 한다.
- 후킹 함수 안에서 `dlsym(RTLD_NEXT, ...)`를 캐싱하지 않고 매번 호출해서 성능이 심각하게 느려지거나, 반대로 캐싱 로직 버그로 무한 재귀에 빠져 스택 오버플로우가 나는 것.
- 정적 링킹 바이너리에 `LD_PRELOAD`를 계속 시도하는 것 — 이 경우는 `ptrace` 기반 후킹(GDB breakpoint commands, `frida`) 등 다른 접근이 필요하다.

## 막혔을 때 다음 체크
- 대상이 정적 링킹인지 헷갈린다면 → REV-0646(정적 링킹된 ELF 분석 접근법)
- setuid 문제와 별개로 `LD_LIBRARY_PATH` 자체가 안 먹히는 상황이라면 → REV-0706(공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때)
- 후킹 검증을 위해 시스템 콜 단위로 더 정밀하게 보고 싶다면 → REV-0112(strace로 시스템 콜에서 힌트 찾기)
- 라이브러리 호출 인자를 빠르게 보고 싶다면 → REV-0111(ltrace로 라이브러리 호출 빠르게 보기)

## 미니 예제
```bash
$ gcc -shared -fPIC -o hook.so hook.c -ldl
$ LD_DEBUG=libs LD_PRELOAD=$(pwd)/hook.so ./chall 2>&1 | grep hook.so
     40213:     calling init: /home/user/ctf/hook.so
$ LD_PRELOAD=$(pwd)/hook.so ./chall
[hook] malloc(32)
[hook] malloc(128)
Welcome to the challenge!
```
`LD_DEBUG=libs`로 `hook.so`가 실제로 로드되는 것을 먼저 확인한 뒤에는 정상적으로 `malloc` 호출이 가로채졌다.

## 관련 글
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0706 — 공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0100 — PLT와 GOT 기초

## 출처/검증
- `LD_PRELOAD` 동작 및 보안 실행 모드(setuid/`AT_SECURE`)에서 무시되는 조건: `man ld.so`(glibc 공식 문서), "Dynamic linker/loader" 섹션, "Secure-execution mode" 항목 기준.
- `dlsym(RTLD_NEXT, ...)`를 이용한 원본 함수 호출 패턴: `man dlsym`(glibc) 기준.
- `LD_DEBUG=libs` 진단 방법: `man ld.so`의 "Environment variables" `LD_DEBUG` 항목 기준 (2026-09-08 확인).
