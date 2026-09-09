---
id: REV-0638
title: "libc 함수 사전: pthread_create 기초"
slug: "rev-0638-libc-pthread-create-basics"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, strace]
keywords: ["pthread_create", "pthread_join", "pthread_mutex_lock", "pthread_exit", "스레드", "멀티스레드 리버싱"]
aliases: ["pthread_create 함수", "스레드 생성 함수", "멀티스레드 바이너리 분석", "GDB 스레드 디버깅"]
symptom_keywords: ["바이너리에 여러 스레드가 보임", "info threads 결과가 여러 개", "race condition 문제", "pthread_create 호출이 있음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`pthread_create()`는 현재 프로세스 안에 **같은 주소 공간을 공유하는 새 실행 흐름(스레드)**을 하나 더 만들어 지정한 함수를 그 스레드에서 실행시키는 함수로, CTF에서는 레이스 컨디션 문제나 병렬 체크 로직을 만드는 데 자주 쓰인다.

## 언제 검색해야 하나
- 디컴파일 코드에서 `pthread_create` 호출과 함수 포인터 인자를 발견했을 때
- GDB로 `info threads`를 쳤더니 스레드가 여러 개 나와서 어느 스레드를 봐야 할지 모를 때
- 여러 스레드가 공유 변수에 동시에 접근해서 결과가 실행할 때마다 달라지는(race condition) 문제를 만났을 때

## 핵심 개념

### 함수 시그니처
```c
int pthread_create(pthread_t *restrict thread,
                    const pthread_attr_t *restrict attr,
                    void *(*start_routine)(void *),
                    void *restrict arg);
int pthread_join(pthread_t thread, void **retval);
void pthread_exit(void *retval);
int pthread_mutex_lock(pthread_mutex_t *mutex);
int pthread_mutex_unlock(pthread_mutex_t *mutex);
```
- `thread`: 생성된 스레드 ID를 저장할 출력 파라미터
- `attr`: 스택 크기, 분리(detach) 상태 등 속성. 보통 `NULL`(기본값)
- `start_routine`: 새 스레드가 진입해서 실행할 함수 — **이 함수 포인터가 리버싱 관점에서 가장 중요한 인자**다. `void *(*)(void *)` 타입이므로 인자 하나(`void*`)를 받고 `void*`를 반환한다.
- `arg`: `start_routine`에 전달될 인자

성공 시 `0`, 실패 시 에러 번호를 반환(errno와 달리 반환값 자체가 에러 코드)한다.

### 링킹 — glibc 2.34 전후 차이
glibc 2.34(2021) 이전에는 `pthread_create` 등 pthread 함수를 쓰려면 컴파일 시 `-lpthread`로 별도 라이브러리(`libpthread.so.0`)를 링크해야 했다. glibc 2.34부터는 pthread 관련 함수 전체가 `libc.so.6`에 통합되어 `-lpthread` 없이도 바로 쓸 수 있다. 그래서 오래된 바이너리에서는 `ldd` 결과에 `libpthread.so.0`이 별도로 보이지만, 최신 배포판(Ubuntu 22.04+ 등)에서 빌드된 바이너리는 `libc.so.6`만 보이는 경우가 많다 — 이는 glibc 버전 추정의 단서가 된다(REV-0648 참고).

### 스레드는 프로세스와 무엇을 공유하고 무엇을 안 하는가
- 공유: 코드(.text), 전역/정적 데이터(.data/.bss), 힙, 파일 디스크립터
- 공유 안 함: 각자의 스택, 레지스터 상태(따라서 각자의 PC/RSP), 스레드 로컬 저장소(TLS, `__thread` 변수)

이 때문에 전역 변수나 힙 데이터를 여러 스레드가 락(`pthread_mutex_t`) 없이 동시에 건드리면 값이 꼬이는 race condition이 발생하고, CTF에서는 이를 의도적으로 이용해 "정확한 타이밍에 값을 바꿔치기해야 통과하는" 문제를 만든다.

## 화면/코드에서 보이는 징후
- 디컴파일 코드에 `pthread_create(&tid, 0, sub_401234, arg);` 형태의 호출
- `nm`/`readelf -d`에 `libpthread.so.0`이 `NEEDED`로 보이거나(구버전), `pthread_*` 심볼이 `libc.so.6`에서 옴(2.34+)
- GDB `info threads`에서 `Thread 0x7f... (LWP 1234) "chall"` 같은 줄이 여러 개 출력됨
- 실행마다 출력 순서나 결과가 미묘하게 달라짐

## 가장 먼저 할 것
`pthread_create`의 세 번째 인자(시작 함수 포인터)를 확인해서 각 스레드가 실제로 어떤 함수를 실행하는지부터 파악한다. IDA/Ghidra에서 그 주소로 이동해 별도 함수로 분석하면 된다.

## 단계별 절차

**1) 스레드 시작 함수 확인 (정적)**
```bash
objdump -d ./chall | grep -B10 'call.*pthread_create@plt'
```
`call` 직전 `lea rdx, [rip+오프셋]` 형태로 시작 함수 주소를 레지스터에 로드하는 코드를 찾는다(x64 SysV에서 3번째 인자는 `rdx`).

**2) 스레드 생성 시점에 멈추기 (GDB)**
```gdb
break pthread_create
run
```

**3) 스레드 목록/전환**
```gdb
info threads
thread 2
bt
```
`info threads`는 현재 존재하는 모든 스레드와 각각의 현재 PC를 보여주고, `thread N`으로 원하는 스레드로 전환한 뒤 `bt`로 그 스레드의 콜스택을 본다.

**4) 모든 스레드에 동일 명령 적용**
```gdb
thread apply all bt
thread apply all print $rip
```

**5) 특정 스레드에만 브레이크포인트 걸기**
```gdb
break sub_401234 thread 2
```

## 명령어/단축키
```bash
ldd ./chall | grep pthread
```
GDB: `info threads`, `thread N`, `thread apply all CMD`, `break LOCATION thread N`, `set scheduler-locking on|off|step`

## 출력 해석
- `info threads` 출력에서 `*` 표시가 붙은 줄이 현재 GDB가 포커스를 두고 있는 스레드다.
- `set scheduler-locking on`을 켜면 `step`/`next` 실행 시 현재 스레드만 진행되고 다른 스레드는 멈춰있다 — race condition을 재현하지 않고 한 스레드만 조용히 분석하고 싶을 때 유용하다. 반대로 race condition 자체를 재현하려면 `off`(기본값) 상태로 둬야 한다.

## 흔한 실수
- `pthread_create`가 스레드를 **즉시** 실행 순서까지 보장한다고 착각하는 것 — 실제 스케줄링 순서는 OS 스케줄러가 결정하며 실행마다 달라질 수 있다.
- `pthread_join` 없이 메인 스레드가 먼저 끝나면, 데몬 스레드가 아닌 이상 프로세스 전체가 종료되어 다른 스레드 작업이 중간에 끊길 수 있다는 점을 간과하는 것.
- 여러 스레드를 동시에 디버깅할 때 `scheduler-locking` 설정을 잊고, 한 스레드에서 `step` 했는데 다른 스레드가 먼저 실행되어 "왜 코드가 순서대로 안 가지"라고 혼란스러워하는 것.

## 막혔을 때 다음 체크
- 스레드가 공유하는 함수 호출 규약이 궁금하면 → REV-0106 SysV AMD64 Calling Convention.
- glibc 버전에 따라 pthread 심볼 위치가 다른 이유가 궁금하면 → REV-0648 glibc 버전별 함수 시그니처 차이 확인법(예정).
- 스레드 내부에서 `malloc`/`free`를 쓸 때의 힙 구조(스레드별 arena)가 궁금하면 → REV-0644 glibc 버전별 malloc 구조 요약표.

## 미니 예제
```c
void *worker(void *arg) {
    int id = *(int *)arg;
    printf("thread %d running\n", id);
    return NULL;
}

int main(void) {
    pthread_t t1, t2;
    int a = 1, b = 2;
    pthread_create(&t1, NULL, worker, &a);
    pthread_create(&t2, NULL, worker, &b);
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
}
```
```gdb
(gdb) break worker
(gdb) run
Thread 2 "chall" hit Breakpoint 1, worker (arg=0x...) at chall.c:2
(gdb) info threads
  Id   Target Id                Frame
* 2    Thread 0x7f... (LWP 1235) worker (arg=0x...) at chall.c:2
  1    Thread 0x7f... (LWP 1234) main () at chall.c:10
  3    Thread 0x7f... (LWP 1236) 0x... in start_thread ()
```
두 워커 스레드 중 하나가 먼저 브레이크포인트에 걸렸고, 나머지 하나(스레드 3)는 아직 `start_thread`(pthread 내부 진입 코드) 단계에 있음을 알 수 있다.

## 관련 글
- REV-0106 — SysV AMD64 Calling Convention
- REV-0644 — glibc 버전별 malloc 구조 요약표
- REV-0637 — libc 함수 사전: fork exec 계열

## 출처/검증
- `pthread_create`/`pthread_join`/`pthread_mutex_lock` 시그니처: POSIX Threads(pthreads) 표준 및 glibc 매뉴얼 기준.
- glibc 2.34에서 libpthread가 libc로 통합된 변경: glibc 2.34 공식 NEWS 파일 기준 (2026-09-08 검증).
- GDB 멀티스레드 명령(`info threads`, `thread apply`, `scheduler-locking`): GDB 공식 매뉴얼 "Debugging Programs with Multiple Threads" 섹션 기준.
