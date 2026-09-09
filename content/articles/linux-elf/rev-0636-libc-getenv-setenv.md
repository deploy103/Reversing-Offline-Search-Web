---
id: REV-0636
title: "libc 함수 사전: getenv setenv 환경변수 함수"
slug: "rev-0636-libc-getenv-setenv"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, strace]
keywords: ["getenv", "setenv", "unsetenv", "putenv", "environ", "환경변수", "environment variable"]
aliases: ["getenv 함수", "setenv 함수", "environ 전역변수", "환경변수 리버싱", "LD_PRELOAD 확인"]
symptom_keywords: ["getenv 호출 이유를 모르겠음", "환경변수로 flag를 주는 문제", "environ 심볼이 GOT에 있음", "ret2libc에서 environ 필요"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`getenv(const char *name)`은 `PATH`, `LD_PRELOAD`, 혹은 CTF 문제가 심어놓은 임의의 환경변수 값을 프로세스 내부에서 읽어오는 함수이고, `setenv`/`putenv`/`unsetenv`는 그 값을 바꾸며, 이 함수들이 참조하는 실제 데이터는 `char **environ`이라는 전역 포인터 배열이다.

## 언제 검색해야 하나
- 코드에 `getenv("...")` 호출이 보이는데 어떤 환경변수를 왜 읽는지 모를 때
- CTF 문제가 "환경변수에 값을 넣고 실행하라"는 힌트를 줄 때
- ret2libc/GOT 관련 write-up에서 `environ` 심볼이 스택 주소 leak에 쓰이는 이유가 궁금할 때

## 핵심 개념

### 함수 시그니처
```c
char *getenv(const char *name);
int setenv(const char *name, const char *value, int overwrite);
int unsetenv(const char *name);
int putenv(char *string);          // "NAME=value" 형태 문자열 하나를 통째로 받음
extern char **environ;             // envp 배열의 시작 주소를 담은 전역 변수
```
`getenv`는 찾는 변수가 없으면 `NULL`을 반환한다. `setenv`의 세 번째 인자 `overwrite`가 0이면 이미 존재하는 변수는 덮어쓰지 않는다.

### environ과 스택의 관계
프로세스가 시작될 때 커널은 스택 최상단에 `argv` 배열, 그 뒤에 `envp` 배열(각 원소는 `"KEY=VALUE"` 문자열의 포인터)을 올려놓는다. libc의 `__libc_start_main`이 이 `envp` 포인터를 받아 전역 변수 `environ`에 저장한다(REV-0099, REV-0108 참고). 즉 `environ`은 **libc 안의 데이터 심볼이지만 그 값은 스택 주소**다.

이 사실이 pwn/리버싱에서 중요한 이유: PIE가 꺼져 있거나 libc 베이스를 이미 알고 있는 상황에서 `environ`의 값을 leak하면 스택 주소를 바로 알아낼 수 있다. `environ` - (고정 오프셋) 으로 `argv[0]`이나 스택 상의 특정 프레임 주소를 계산하는 것이 ret2libc/스택 피벗 공격의 흔한 전처리 단계다.

### 설계 의도 — 실행 시점 설정
`getenv`류 함수는 프로그램을 재컴파일하지 않고도 동작을 바꿀 수 있게 해준다. CTF에서는 이 성질을 문제 설계에 그대로 이용해서 "특정 환경변수가 설정되어 있어야 디버그 메뉴가 열린다"거나 "환경변수 값 자체가 flag의 일부"인 문제가 흔하다.

## 화면/코드에서 보이는 징후
- 디컴파일 코드에 `v1 = getenv("DEBUG");` 후 `if (v1) { ... }` 형태의 분기
- `strings` 결과에 `LD_PRELOAD`, `LD_LIBRARY_PATH`, `PATH` 같은 익숙한 이름이 아니라 문제 고유의 커스텀 변수 이름(`FLAG`, `SECRET_KEY` 등)이 보임
- GOT에 `getenv`, `environ` 심볼이 동적 재배치 대상으로 존재

## 가장 먼저 할 것
`getenv("이름")` 호출을 보면 그 문자열 인자(변수 이름)를 확인하고, 실제로 그 환경변수를 설정한 채로 프로그램을 실행해서 분기가 어떻게 바뀌는지 관찰한다.
```bash
FLAG=test123 ./chall
```

## 단계별 절차

**1) 어떤 환경변수를 읽는지 정적으로 확인**
```bash
objdump -d ./chall | grep -B5 'call.*getenv@plt'
strings ./chall | grep -iE 'flag|debug|secret|key'
```

**2) 값을 설정하고 실행하며 분기 관찰**
```bash
MY_VAR=1 ./chall
```

**3) 실행 중 environ 배열 직접 덤프 (GDB)**
```gdb
break main
run
print environ
print *environ@10
```
`print environ`은 스택 상의 envp 배열 시작 주소를, `print *environ@10`은 그 배열의 앞 10개 문자열 포인터를 보여준다.

**4) GDB에서 환경변수 직접 조작**
```gdb
show environment MY_VAR
set environment MY_VAR = injected_value
run
```
`set environment`는 GDB가 대상을 `run` 하기 전에 적용되므로, 소스 없이도 바이너리에 임의의 환경변수를 주입해 분기를 테스트할 수 있다.

**5) /proc에서 실제 프로세스 환경 확인 (동적, PID 필요)**
```bash
tr '\0' '\n' < /proc/<PID>/environ
```

## 명령어/단축키
```bash
FLAG=xxx ./chall
strace -e trace=none ./chall     # (execve 인자로 envp 확인용, REV-0112 참고)
```
GDB: `show environment [이름]`, `set environment 이름=값`, `unset environment 이름`, `print environ`, `print *environ@N`

## 출력 해석
- `print environ`이 `0x7ffd...` 같은 스택 주소를 가리키면 정상 — 이 값이 곧 스택 leak의 재료다.
- `getenv` 반환값이 `$0`(NULL)이면 그 이름의 환경변수가 설정되지 않은 것 — 프로그램이 어떻게 처리하는지(기본값 사용? 종료?) 다음 코드에서 확인한다.

## 흔한 실수
- `getenv`가 대소문자를 구분한다는 것을 잊고 `flag=1`로 설정했는데 코드가 `FLAG`를 찾는 경우 — 이름을 정확히 일치시켜야 한다.
- `setenv`로 값을 바꿔도 **이미 fork/exec된 자식 프로세스**나 **이미 캐싱해둔 로컬 변수**에는 반영되지 않는다는 점을 놓치는 것.
- `environ`을 함수로 착각하는 것 — `environ`은 함수가 아니라 `char **` 타입 전역 변수(데이터 심볼)다.

## 막혔을 때 다음 체크
- 프로그램이 환경변수 대신 `argv`/`argc`를 읽는다면 → REV-0108 argc argv envp 참고.
- `fork`/`execve`로 환경을 물려주는 방식이 궁금하면 → REV-0637 libc 함수 사전: fork exec 계열.
- 스택 leak 이후 실제 공격에 어떻게 쓰이는지는 이 사전 범위를 넘어서므로 pwn 카테고리 ret2libc 관련 글을 참고.

## 미니 예제
```c
char *dbg = getenv("CTF_DEBUG");
if (dbg && strcmp(dbg, "1") == 0) {
    puts("Debug menu unlocked");
}
```
```bash
$ CTF_DEBUG=1 ./chall
Debug menu unlocked
```
환경변수 이름과 기대값(`"1"`)만 알면 코드를 패치하지 않고도 숨겨진 분기를 그대로 통과시킬 수 있다.

## 관련 글
- REV-0108 — argc argv envp를 어셈블리에서 찾는 법
- REV-0099 — __libc_start_main이 무엇이고 main을 찾는 법
- REV-0637 — libc 함수 사전: fork exec 계열
- REV-0112 — strace로 시스템 콜에서 힌트 찾기

## 출처/검증
- `getenv`/`setenv`/`putenv`/`unsetenv` 시그니처: POSIX/glibc 표준 라이브러리 함수 정의 기준.
- `environ` 전역 변수와 envp/스택 관계: glibc `csu/libc-start.c`(`__libc_start_main`)의 envp 처리 및 System V AMD64 ABI 스택 초기 레이아웃 기준 (2026-09-08 검증).
- GDB `show environment`/`set environment` 명령: GDB 공식 매뉴얼 "Your Program's Environment" 섹션 기준.
