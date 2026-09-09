---
id: REV-0848
title: "디버거에서 특정 API 호출 시 프로세스가 멈출 때"
slug: "rev-0848-debugger-hangs-on-specific-api-call"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg]
keywords: ["디버거 멈춤", "블로킹 호출", "recv 멈춤", "read 멈춤", "무한루프 안티디버깅"]
aliases: ["특정 함수에서 진행이 안됨", "디버거가 응답없음", "Run 눌러도 반응없음", "블로킹 API 디버깅"]
symptom_keywords: ["recv 이후 진행이 안된다", "read 호출 후 멈춘다", "Continue를 눌러도 아무 반응이 없다", "CPU 사용률이 100%로 고정된다", "디버거가 특정 지점에서 응답이 없다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-MS-PE-FORMAT"]
last_verified: "2026-09-09"
---

## 한 줄 요약
특정 API를 지나간 뒤 화면이 멈춘 것처럼 보이면 원인은 셋 중 하나다 — 그 API가 원래 무언가(입력, 이벤트, 락)를 **정상적으로 기다리는 중**이거나, **진짜 무한 루프**(안티디버깅 포함)에 들어갔거나, **다른 스레드**가 그 자리에서 락을 붙잡고 안 풀어주는 것이다. 디버거를 일시정지하고 "지금 정확히 어느 함수 안에 있는지"부터 확인하면 셋을 바로 구분할 수 있다.

## 언제 검색해야 하나
- `recv`, `read`, `WaitForSingleObject`, `pthread_mutex_lock`, `accept` 같은 API를 지나간 뒤 디버거 화면이 갱신되지 않을 때
- Continue/Run을 눌러도 다음 브레이크포인트나 프롬프트로 돌아오지 않을 때
- 작업 관리자/`top` 기준 CPU 사용률이 한 코어에서 계속 높게 유지되는데도 디버거는 멈춰 있을 때
- 이 증상이 매번 재현되는지, 특정 조건(네트워크 서버 미기동 등)에서만 재현되는지 구분이 안 될 때

## 핵심 개념
"멈췄다"는 하나의 증상이지만 원인은 완전히 다른 세 갈래로 나뉜다. 원인을 구분하지 않고 강제 종료부터 하면 매번 같은 문제를 반복해서 겪는다.

1. **정상적인 블로킹 대기**: 소켓 `recv`/`read`(블로킹 모드), `WaitForSingleObject(..., INFINITE)`, 뮤텍스/세마포어 대기, GUI 메시지 루프(`GetMessage`)처럼 설계상 그 자리에서 외부 이벤트를 기다리는 코드. 디버거도 대상 프로세스도 죽지 않았고, CPU 사용률은 낮게 유지된다(진짜로 아무 일도 안 하고 잠들어 있으므로).
2. **진짜 무한 루프**: 안티디버깅 루틴이 디버거를 감지하고 의도적으로 스핀 루프에 빠지게 만들거나, 원래 로직 버그로 CPU를 계속 소모하는 루프에 들어간 경우. CPU 사용률이 한 코어에서 계속 높게 유지된다.
3. **다른 스레드의 락 경합**: 멀티스레드 프로그램에서 한 스레드가 브레이크포인트에 걸려 멈춘 채로 뮤텍스를 들고 있으면, 그 뮤텍스를 기다리는 다른 스레드가 영원히 못 풀리고 전체 프로그램이 멈춘 것처럼 보인다. 이 경우 실제로는 디버거가 스레드 하나만 멈춘 것이 문제의 근원이다.

## 화면/코드에서 보이는 징후
- GDB: `continue` 이후 프롬프트가 돌아오지 않고, `Ctrl+C`를 눌러야만 다시 제어가 돌아옴
- x64dbg: 상태 표시줄이 "Running"에서 멈춘 채 CPU 창 하이라이트가 갱신되지 않음
- `top`/작업 관리자에서 대상 프로세스 CPU 사용률이 0%에 가깝게 유지되면 대기, 한 코어에서 계속 높으면 루프
- 멀티스레드 프로그램이라면 `info threads`(GDB) 또는 Threads 창(x64dbg)에서 여러 스레드가 동시에 "멈춘" 상태로 보임

## 가장 먼저 할 것
GDB는 `Ctrl+C`, x64dbg는 Pause 버튼을 눌러 지금 정확히 어느 함수 내부에 멈춰 있는지부터 확인한다. 강제로 프로세스를 죽이기 전에 이 확인이 반드시 먼저다.

## 단계별 절차

**1) 현재 위치 확인**
```gdb
(gdb) Ctrl+C
^C
Program received signal SIGINT, Interrupt.
0x00007ffff7... in __libc_recv () from /lib/x86_64-linux-gnu/libc.so.6
(gdb) bt
```
`bt`로 콜스택을 보면 어떤 함수가 이 대기/루프를 유발했는지 바로 드러난다.

**2) 대기 계열 함수 안이면 "정상 대기"로 판단**
`recv`, `read`, `poll`, `select`, `WaitForSingleObject`, `pthread_cond_wait` 근처라면 그 대기를 풀어줄 조건(서버 응답, 이벤트 시그널, 사용자 입력)을 채워준다. 예를 들어 클라이언트가 서버 응답을 기다리는 중이라면 서버 프로세스가 먼저 떠 있는지 확인한다.

**3) 대상 바이너리 자체 코드 안이면 "루프" 의심**
같은 좁은 주소 범위를 여러 번 반복해서 멈춰 보게 되면(GDB는 `Ctrl+C` 후 `x/5i $pc`를 몇 번 반복, x64dbg는 Pause를 몇 번 반복) 무한 루프다. `RDTSC`/`GetTickCount` 같은 타이밍 체크나 `IsDebuggerPresent` 근처인지 확인한다.

**4) 멀티스레드라면 스레드별 상태 확인**
```gdb
(gdb) info threads
(gdb) thread apply all bt
```
브레이크포인트에 걸려 멈춘 스레드가 락을 쥐고 있고, 다른 스레드가 그 락을 기다리는 구조인지 콜스택으로 확인한다. 이 경우 멈춘 스레드를 `continue`시켜 락을 풀어줘야 나머지가 진행된다.

**5) strace/ltrace로 사전에 어느 syscall/라이브러리 호출에서 막혔는지 좁히기(Linux)**
```bash
strace -f -p <PID>
```
마지막 줄에 찍힌 syscall이 그대로 멈춰 있으면(`recv(...` 다음에 아무 것도 안 찍힘) 그 syscall이 블로킹 원인이다.

## 명령어/단축키
```gdb
Ctrl+C                      # 실행 중 강제 중단, 현재 위치 확인
(gdb) bt
(gdb) info threads
(gdb) thread apply all bt
(gdb) x/5i $pc
```
```
x64dbg: Pause 버튼(F12), Threads 창, Call Stack 창
```
```bash
strace -f -p <PID>          # 어느 syscall에서 멈췄는지 실시간 확인
top / 작업 관리자            # CPU 사용률로 대기 vs 루프 구분
```

## 출력 해석
- `bt` 최상단이 `recv`/`read`/`__libc_read` 같은 syscall 래퍼이고 CPU 사용률이 낮다 → 정상 대기. 강제 종료하지 말고 원인 조건을 채운다.
- 같은 주소 범위를 반복해서 멈춰 있고 CPU 사용률이 높다 → 무한 루프. 그 루프 직전 분기 코드가 조작 대상이다.
- `thread apply all bt`에서 한 스레드는 `pthread_mutex_lock` 안에, 다른 스레드는 브레이크포인트로 멈춰 있다 → 락 경합. 멈춘 스레드를 진행시켜야 한다.
- `strace`가 `recv(3, ` 찍고 그대로 멈춰 있다 → 그 파일 디스크립터(fd 3)에 데이터가 안 오고 있다는 뜻. 상대편(서버/파이프 반대쪽)을 확인한다.

## 흔한 실수
- Pause/Ctrl+C를 눌러 현재 위치를 확인하지 않고 곧바로 프로세스를 강제 종료해서 원인 파악 기회를 날리는 것.
- 네트워크 문제(서버 미응답)인데 클라이언트 코드에서만 원인을 찾으려는 것.
- 멀티스레드 프로그램에서 하나의 스레드만 보고 "멈췄다"고 판단하고, 그 스레드가 다른 스레드의 락을 쥐고 있다는 사실을 놓치는 것.
- 무한 루프를 발견하자마자 원인 분석 없이 바로 패치부터 하는 것 — 안티디버깅 루프인지 원래 로직(폴링)인지 콜스택으로 먼저 구분해야 한다.

## 막혔을 때 다음 체크
- Windows/x64dbg 환경에서 숨겨진 다이얼로그, `MessageBoxW` 관련 정지까지 포함한 더 자세한 절차가 필요하면 → REV-0618 특정 API 호출 이후 x64dbg가 응답이 없을 때.
- 멈춘 게 아니라 디버거가 붙자마자 프로세스가 아예 종료돼 버린다면 → REV-0858 디버거가 붙자마자 프로그램이 종료될 때.
- 멀티스레드에서 원하는 스레드 자체를 못 찾겠다면 → REV-0856 멀티스레드 프로그램에서 원하는 스레드를 못 찾을 때.

## 미니 예제
```bash
$ gdb -q ./client
(gdb) break main
(gdb) run
(gdb) continue
# 몇 초 뒤에도 프롬프트가 안 돌아옴
Ctrl+C
Program received signal SIGINT, Interrupt.
0x00007ffff7ac1a4d in __libc_recv () from /lib/x86_64-linux-gnu/libc.so.6
(gdb) bt
#0  0x00007ffff7ac1a4d in recv () from /lib/x86_64-linux-gnu/libc.so.6
#1  0x0000000000401412 in wait_for_server_reply () at client.c:40
#2  0x0000000000401530 in main () at client.c:75
```
콜스택을 보니 `recv`에서 서버 응답을 기다리고 있었다. 서버 프로세스를 먼저 실행한 뒤 다시 시도하니 `recv`가 정상적으로 반환됐다.

## 관련 글
- REV-0618 — 특정 API 호출 이후 x64dbg가 응답이 없을 때
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트
- REV-0617 — 실행마다 API 호출 순서가 달라 보일 때(멀티스레드)

## 출처/검증
- `recv`/`read`/`WaitForSingleObject`/`pthread_mutex_lock`의 블로킹 동작: POSIX(`man 2 recv`, `man 3 pthread_mutex_lock`) 및 Microsoft Win32 API 공식 문서 기준.
- GDB `Ctrl+C`, `info threads`, `thread apply all bt` 동작: GDB 공식 매뉴얼 "Debugging Programs with Multiple Threads" 챕터 기준.
- `strace -f -p PID`로 실행 중 프로세스에 attach해 syscall을 추적하는 방법: `strace(1)` man page 기준 (2026-09-09 검증).
