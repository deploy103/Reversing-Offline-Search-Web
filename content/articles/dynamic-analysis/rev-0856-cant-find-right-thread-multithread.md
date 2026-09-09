---
id: REV-0856
title: "멀티스레드 프로그램에서 원하는 스레드를 못 찾을 때"
slug: "rev-0856-cant-find-right-thread-multithread"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg]
keywords: ["멀티스레드 디버깅", "info threads", "thread 전환", "스레드별 브레이크포인트"]
aliases: ["스레드 선택 방법", "원하는 스레드 찾기", "여러 스레드 중 하나만 추적"]
symptom_keywords: ["스레드가 너무 많아서 어느게 원하는건지 모르겠다", "브레이크포인트가 다른 스레드에서 걸린다", "스레드마다 스택이 달라서 헷갈린다", "몇 번 스레드인지 특정할 수가 없다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
스레드가 여러 개인 프로그램에서 "원하는" 스레드를 찾으려면, 그 스레드를 유일하게 특정할 수 있는 단서(스레드가 실행 중인 함수, 브레이크포인트가 걸린 콜스택, 또는 생성 시점)를 기준으로 골라야 한다 — 무작정 번호를 훑는 대신 `thread apply all bt`로 전체 스레드의 콜스택을 한 번에 뽑아 비교하는 것이 가장 빠르다.

## 언제 검색해야 하나
- 브레이크포인트를 걸었는데 예상과 다른 스레드에서 멈춰서, 원래 원했던 스레드가 어느 것인지 헷갈릴 때
- `info threads`로 목록은 보이는데 번호(TID)만으로는 어느 스레드가 어떤 작업을 하는지 알 수 없을 때
- 특정 작업을 처리하는 워커 스레드 하나만 골라서 추적하고 싶은데 스레드 수가 너무 많아 하나씩 확인하기 번거로울 때
- 스레드가 실행 중 계속 생성/종료되어 이전에 확인한 번호가 다음번엔 다른 스레드를 가리킬 때

## 핵심 개념

### 스레드 번호(TID)는 재사용된다
운영체제는 스레드가 종료되면 그 TID를 다른 새 스레드에 재사용할 수 있다. 즉 "3번 스레드가 이 함수를 처리했다"는 관찰은 그 순간에만 유효하며, 나중에 다시 3번 스레드를 보면 완전히 다른 작업을 하는 스레드일 수 있다. 번호만으로 스레드를 계속 추적하는 것은 위험하다.

### 콜스택이 가장 신뢰할 수 있는 식별자
스레드가 지금 어떤 함수 안에 있는지(콜스택)를 보면, "네트워크 처리 스레드"인지 "타이머 스레드"인지 "메인 스레드"인지 바로 구분된다. `thread apply all bt`(GDB) 또는 x64dbg Threads 창에서 각 스레드를 클릭해 Call Stack을 확인하는 방법으로, 전체 스레드를 한 번에 훑어 원하는 역할을 하는 스레드를 골라낸다.

### 스레드 생성 시점에 브레이크포인트를 걸어 새 TID를 확보
워커 스레드가 어떤 함수(`pthread_create`, `CreateThread`)로 생성되는지 안다면, 그 생성 함수에 브레이크포인트를 걸어 새로 만들어지는 스레드의 시작 함수 인자(스레드 함수 포인터, 인자 데이터)를 확인하면, 그 직후 생성된 스레드가 바로 원하는 것임을 확신할 수 있다.

### 스레드별 브레이크포인트로 특정 스레드에서만 멈추기
GDB는 브레이크포인트에 스레드 조건을 붙일 수 있어, 다른 스레드가 같은 코드를 지나가도 무시하고 지정한 스레드에서만 멈추게 할 수 있다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) info threads
  Id   Target Id                       Frame
* 1    Thread 0x7ffff7d... (LWP 1001)  main () at server.c:20
  2    Thread 0x7ffff6a... (LWP 1002)  0x00007ffff7ac... in recv ()
  3    Thread 0x7ffff5f... (LWP 1003)  0x00007ffff7ac... in recv ()
  4    Thread 0x7ffff54... (LWP 1004)  handle_timer () at server.c:80
```
스레드 2, 3이 똑같이 `recv` 안에서 멈춰 있어 번호만으로는 어느 것이 원하는 클라이언트 연결인지 구분이 안 되는 상황.

## 가장 먼저 할 것
`thread apply all bt`(GDB) 또는 Threads 창에서 각 스레드를 순서대로 클릭(x64dbg)해 전체 콜스택을 한 번에 확인한다. 여기서 함수 이름이나 인자 값으로 원하는 스레드를 구분할 단서를 찾는다.

## 단계별 절차

**1) 전체 스레드 콜스택 한 번에 확인**
```gdb
(gdb) thread apply all bt
```
각 스레드가 지금 어느 함수 체인 안에 있는지 한 화면에서 비교한다.

**2) 콜스택으로 구분이 안 되면 인자/지역변수까지 비교**
```gdb
(gdb) thread 2
(gdb) frame 1
(gdb) info args
(gdb) print client_fd
```
같은 함수(`recv`)라도 처리 중인 소켓 fd, 클라이언트 주소 등 인자 값이 다르면 그것으로 구분한다.

**3) 특정 스레드로 전환해서 계속 그 스레드만 스텝**
```gdb
(gdb) thread 3
(gdb) next
```
GDB는 `thread N` 이후 `step`/`next`/`continue`가 기본적으로 해당 스레드 관점에서 실행되도록 지원한다(`set scheduler-locking on`을 걸면 다른 스레드는 그동안 멈춰 있게 만들 수도 있다).

**4) 스레드 생성 시점부터 추적**
```gdb
(gdb) break pthread_create
(gdb) run
(gdb) finish
(gdb) info threads
```
새로 생긴 스레드의 TID를 그 자리에서 바로 확인해두면, 이후 그 스레드가 어떤 역할인지 헷갈릴 일이 없다.

**5) 특정 스레드에서만 멈추는 조건부 브레이크포인트**
```gdb
(gdb) break handle_connection thread 3
```
스레드 3에서 `handle_connection`을 호출할 때만 멈추고, 다른 스레드는 이 브레이크포인트를 무시하고 지나간다.

**6) x64dbg에서 스레드 전환**
Threads 창에서 원하는 스레드 행을 더블클릭하면 그 스레드가 "활성" 스레드로 전환되어 CPU 창이 그 스레드의 현재 위치를 보여준다. 각 스레드 행에서 우클릭 → "Freeze"로 특정 스레드만 멈춰두고 나머지만 진행시킬 수도 있다.

## 명령어/단축키
```gdb
(gdb) info threads
(gdb) thread N
(gdb) thread apply all bt
(gdb) break FUNC thread N
(gdb) set scheduler-locking on|off|step
```
```
x64dbg: Threads 창 더블클릭(스레드 전환), 우클릭 → Freeze/Resume
```

## 출력 해석
- `info threads`의 `*` 표시는 현재 GDB가 "활성"으로 보고 있는 스레드다. 명령을 그 스레드 기준으로 실행 중이라는 뜻.
- `thread apply all bt`에서 여러 스레드가 똑같은 함수 이름으로 멈춰 있으면, 그 아래 프레임의 인자 값이나 지역 변수로 더 좁혀야 한다.
- `set scheduler-locking on` 이후에는 `step`/`next`를 눌러도 다른 스레드는 전혀 진행되지 않는다 — 특정 스레드만 순수하게 추적하고 싶을 때 유용하지만, 락 경합이 있는 코드에서는 오히려 교착 상태처럼 보일 수 있으니 필요할 때만 켠다.

## 흔한 실수
- 이전 실행에서 확인한 TID 번호를 다음 실행에서도 같은 역할의 스레드라고 가정하는 것 — 스레드 생성 순서가 매번 달라질 수 있다.
- 콜스택이 같다고 바로 같은 스레드로 단정하는 것 — 같은 함수(`recv`)를 여러 워커 스레드가 동시에 실행 중일 수 있으므로 인자 값까지 봐야 한다.
- `scheduler-locking`을 켜둔 채로 잊어버리고, 다른 스레드가 전혀 안 움직이는 것을 이상한 버그로 착각하는 것.
- x64dbg에서 스레드를 Freeze해놓고 다시 Resume하는 것을 잊어 이후 분석에서 그 스레드만 계속 안 움직이는 것.

## 막혔을 때 다음 체크
- 스레드 생성 자체의 기본 개념(`pthread_create` 인자, 반환값)이 궁금하다면 → REV-0638 libc 함수 사전: pthread_create 기초.
- 멀티스레드 때문에 API 호출 순서가 실행마다 달라 보이는 문제라면 → REV-0617 실행마다 API 호출 순서가 달라 보일 때(멀티스레드).
- 스레드 하나가 멈춰서 다른 스레드까지 멈춘 것처럼 보이는 상황이라면 → REV-0848 디버거에서 특정 API 호출 시 프로세스가 멈출 때.

## 미니 예제
```gdb
(gdb) thread apply all bt

Thread 4 (Thread 0x7ffff54006c0):
#0  handle_timer () at server.c:80

Thread 3 (Thread 0x7ffff5fff6c0):
#0  recv () from libc.so.6
#1  0x0000000000401a20 in handle_connection (fd=7) at server.c:55

Thread 2 (Thread 0x7ffff6aff6c0):
#0  recv () from libc.so.6
#1  0x0000000000401a20 in handle_connection (fd=5) at server.c:55

Thread 1 (Thread 0x7ffff7d... (LWP 1001)):
#0  main () at server.c:20
```
스레드 2와 3이 똑같이 `recv`에 멈춰 있었지만, `fd=5`와 `fd=7`이라는 인자 값 차이로 어느 스레드가 어느 클라이언트 연결을 처리하는지 정확히 구분할 수 있었다.

## 관련 글
- REV-0638 — libc 함수 사전: pthread_create 기초
- REV-0617 — 실행마다 API 호출 순서가 달라 보일 때(멀티스레드)
- REV-0848 — 디버거에서 특정 API 호출 시 프로세스가 멈출 때

## 출처/검증
- GDB의 멀티스레드 디버깅 명령(`info threads`, `thread`, `thread apply`, `scheduler-locking`): GDB 공식 매뉴얼 "Debugging Programs with Multiple Threads" 챕터 기준.
- x64dbg Threads 창의 Freeze/Resume 및 스레드 전환 동작: x64dbg 공식 문서(Threads) 기준 (2026-09-09 검증).
