---
id: REV-0823
title: "여러 프로세스/스레드를 디버거로 동시에 다루는 법"
slug: "rev-0823-multi-process-thread-debugging"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg]
keywords: ["멀티프로세스 디버깅", "멀티스레드 디버깅", "GDB inferior", "GDB follow-fork-mode", "x64dbg DebugChildren", "info threads", "다중 프로세스 attach"]
aliases: ["여러 프로세스 동시 디버깅", "부모 자식 프로세스 디버깅", "멀티스레드 프로그램 분석법", "fork된 프로세스 디버깅"]
symptom_keywords: ["fork 이후 자식 프로세스를 놓침", "프로그램이 새 프로세스를 띄우는데 디버거가 안 따라감", "스레드가 여러 개라 어느 걸 봐야 할지 모름", "멀티스레드 프로그램에서 브레이크포인트가 이상하게 걸림"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
하나의 디버거 창은 기본적으로 프로세스 하나만 따라가므로, 대상 프로그램이 `fork`/`CreateProcess`로 자식 프로세스를 만들거나 `pthread_create`/`CreateThread`로 여러 스레드를 띄우면 GDB의 inferior/스레드 목록, x64dbg의 Threads 탭과 자식 프로세스 추적 옵션을 명시적으로 켜서 어느 프로세스·스레드를 보고 있는지 스스로 확인해야 한다.

## 언제 검색해야 하나
- 서버형 CTF 문제가 접속마다 `fork()`로 자식 프로세스를 만들어서, 디버거가 붙어 있던 프로세스가 아니라 새로 생긴 자식 프로세스에서 실제 로직이 실행될 때
- Windows 프로그램이 자기 자신을 다시 실행하거나(`CreateProcess`) 별도 워커 프로세스를 띄워서, x64dbg가 첫 프로세스만 잡고 있을 때
- 멀티스레드 프로그램에서 브레이크포인트가 걸렸는데 지금 멈춘 게 몇 번 스레드인지, 다른 스레드는 뭘 하고 있는지 감이 안 잡힐 때
- "분명 이 함수가 호출됐을 텐데 브레이크포인트가 안 걸린다"는 문제의 원인이 실제로는 다른 프로세스/스레드에서 실행됐기 때문일 때

## 핵심 개념

### 프로세스 하나 vs 여러 개
디버거는 기본적으로 하나의 "타겟"에 붙는다. 그런데 실행 파일이 `fork()`(Linux)나 `CreateProcess`(Windows)로 완전히 새로운 프로세스를 만들면, 그 새 프로세스는 원래 디버거가 알고 있던 대상이 아니다. 디버거가 자식 프로세스를 자동으로 따라가게 만들지, 부모만 보고 있을지를 명시적으로 설정해야 한다.

- **GDB**: `set follow-fork-mode` 옵션으로 `fork()` 이후 부모(`parent`)를 계속 따라갈지, 자식(`child`)으로 넘어갈지 정한다. `set detach-on-fork off`를 켜면 부모와 자식 둘 다 디버거의 "inferior" 목록에 남아서, `info inferiors`로 둘 다 확인하고 `inferior 2` 명령으로 다른 프로세스로 전환할 수 있다.
- **x64dbg**: 기본적으로 자식 프로세스를 자동으로 따라가지 않는다. Options → Preferences(또는 엔진 설정)에서 `DebugChildren`류 옵션을 켜거나, 자식 프로세스가 뜨면 별도의 x64dbg 창으로 직접 attach해야 한다. 실무적으로는 "부모 프로세스에 브레이크포인트를 걸어 `CreateProcess` 직후 자식 PID를 알아낸 뒤, 두 번째 x64dbg 인스턴스로 그 PID에 attach"하는 방식이 가장 확실하다.

### 스레드는 원래부터 같은 프로세스 안에 여러 개 존재
스레드는 프로세스와 달리 같은 주소 공간을 공유하므로, 디버거 하나가 한 프로세스 안의 모든 스레드를 동시에 볼 수 있다. 다만 "지금 어느 스레드가 멈췄는지", "다른 스레드는 여전히 돌고 있는지"를 구분해서 봐야 한다.

- **GDB**: `info threads`로 프로세스 안의 모든 스레드와 각 스레드의 현재 위치(주소, 함수)를 한 번에 나열한다. `thread N`으로 포커스를 옮기고, `thread apply all bt`로 모든 스레드의 콜스택을 한 번에 뽑을 수 있다.
- **x64dbg**: 하단 또는 별도 탭의 **Threads** 창에서 모든 스레드의 TID, 시작 주소, 우선순위, 현재 상태를 볼 수 있다. 특정 스레드를 더블클릭하면 그 스레드 컨텍스트(레지스터, 콜스택)로 CPU 뷰가 전환된다.

### 브레이크포인트가 걸렸을 때 프로그램 전체가 멈추는가
기본 동작이 도구마다 다르다. GDB는 기본적으로 "all-stop mode"라서 한 스레드가 브레이크포인트에 걸리면 프로세스의 모든 스레드가 같이 멈춘다(`set non-stop on`으로 바꾸면 스레드별 개별 제어가 가능하지만 CTF 수준에서는 잘 안 쓴다). x64dbg도 마찬가지로 브레이크포인트가 걸리면 프로세스 전체(모든 스레드)가 멈춘다. 이 "전체 정지"가 기본값이라는 걸 모르면, 다른 스레드가 계속 도는 줄 알고 헷갈리는 경우가 많다.

## 화면/코드에서 보이는 징후
- GDB에서 `Detaching after fork from child process 12345.` 메시지가 뜨고 그 이후 원하던 로직이 전혀 안 보임
- x64dbg에서 브레이크포인트를 건 함수가 로그에 안 찍히는데, 작업 관리자/`ps`에는 프로세스가 하나 더 떠 있음
- x64dbg Threads 탭에 TID가 여러 개 나열되어 있고, 지금 CPU 뷰가 보여주는 스레드가 어떤 건지 헷갈림
- GDB `info threads` 출력에 `* 2  Thread ...` 처럼 별표(`*`)가 붙은 줄이 현재 포커스된 스레드

## 가장 먼저 할 것
대상 프로그램이 새 프로세스를 만드는지부터 확인한다. Linux는 소스나 `strace ./chall` 결과에서 `clone`/`fork`/`execve` 계열 호출이 보이는지, Windows는 Process Monitor나 x64dbg 로그에서 `CreateProcessW` 호출이 보이는지 확인한다. 스레드만 여러 개인 경우라면 GDB `info threads` 또는 x64dbg Threads 탭부터 열어서 몇 개가 떠 있는지 파악한다.

## 단계별 절차
### 자식 프로세스 따라가기 (GDB, Linux)
1. `gdb ./chall` 후 `set follow-fork-mode child` (자식으로 넘어가서 계속 디버깅) 또는 `set follow-fork-mode parent` (부모에 남아 있기)
2. 둘 다 보고 싶으면 `set detach-on-fork off`로 부모/자식 모두 inferior로 유지
3. `run` 이후 `fork()` 지점에서 `info inferiors`로 부모/자식 PID 확인
4. `inferior 2`로 자식 프로세스로 전환, 필요하면 `inferior 1`로 다시 부모로 복귀

### 자식 프로세스 따라가기 (x64dbg, Windows)
1. 부모 프로세스를 x64dbg로 실행하고 `CreateProcessW`(또는 `CreateProcessA`) API에 브레이크포인트
2. 브레이크포인트에 걸리면 Step Over(F8)로 실제 프로세스 생성 완료까지 진행, 반환값(생성된 프로세스 핸들)과 `lpProcessInformation` 구조체에서 자식 PID 확인
3. 새 x64dbg 인스턴스를 열고 File → Attach로 그 자식 PID에 붙기(자식이 바로 종료되지 않도록, 필요하면 부모 코드에 `Sleep` 삽입 또는 자식 진입점에 미리 브레이크포인트를 걸 방법을 고려)

### 멀티스레드 상황 파악 (공통)
1. GDB: `info threads`로 전체 스레드 목록 확인 → `thread N`으로 이동 → `bt`로 콜스택 확인
2. x64dbg: Threads 탭 열기 → 의심 스레드 더블클릭 → CPU 뷰에서 그 스레드의 레지스터/스택 확인
3. 특정 스레드만 멈추고 나머지는 계속 돌게 하고 싶다면 REV-0824(스레드 지정 브레이크포인트)로 이동

## 명령어/단축키
GDB(Linux):
```
set follow-fork-mode child
set follow-fork-mode parent
set detach-on-fork off
info inferiors
inferior 2
info threads
thread 3
thread apply all bt
```
x64dbg(Windows):
```
bp CreateProcessW
Threads 탭 (하단 탭 또는 View → Threads)
File → Attach
```

## 출력 해석
- GDB `info inferiors`에서 `Num  Description       Connection ...  Executable` 형태로 나오는 각 줄이 하나의 독립된 프로세스다. `*`가 붙은 줄이 현재 명령이 적용될 프로세스다.
- x64dbg Threads 탭의 각 행은 TID, Start Address(스레드 시작 함수 주소), 마지막으로 멈춘 주소를 보여준다. Start Address가 `pthread_create`나 `CreateThread`에 넘긴 콜백 함수 주소와 같은지 대조하면 "이 스레드가 무슨 일을 하는 스레드인지" 짐작할 수 있다.
- GDB `thread apply all bt`는 각 스레드의 콜스택을 순서대로 출력하므로, 지금 어느 스레드가 어떤 함수 안에서 멈춰 있는지 한 번에 조망할 수 있다.

## 흔한 실수
- `follow-fork-mode`를 설정하지 않고 그냥 `run`을 눌러서, 자식 프로세스가 생성되자마자 디버거가 부모만 붙잡고 있다는 걸 뒤늦게 알아차리는 것
- x64dbg에서 새 프로세스가 뜬 걸 눈치채지 못하고 "브레이크포인트가 원래 안 걸리는 함수인가보다"라고 착각하는 것
- 멀티스레드 프로그램에서 브레이크포인트가 걸려 전체가 멈췄는데, 다른 스레드도 같이 멈췄다는 사실을 모르고 "왜 다른 스레드 로직이 진행이 안 되지"라고 헷갈리는 것
- 자식 프로세스에 attach하려는 순간 그 자식이 이미 빠르게 실행을 끝내고 종료해버려서 놓치는 것 — 부모 쪽에 `Sleep`을 강제로 넣거나 자식이 실행할 바이너리 자체에 `ptrace(PTRACE_TRACEME)`류 트릭, 혹은 `pause()`를 임시로 삽입하는 준비가 필요할 수 있음

## 막혔을 때 다음 체크
- 특정 스레드 하나만 골라 멈추고 싶다면 → REV-0824 멀티스레드 프로그램에서 특정 스레드만 멈추는 법
- pthread 관련 함수 시그니처가 헷갈리면 → REV-0638 libc 함수 사전: pthread_create 기초
- 자식 프로세스가 만들어지는 Windows API 자체가 궁금하면 → REV-0503 WinAPI 프로세스 함수 사전: CreateProcess 계열
- API 호출 순서가 실행마다 달라 보이는 멀티스레드 특유의 혼란은 → REV-0617 실행마다 API 호출 순서가 달라 보일 때(멀티스레드)

## 미니 예제
```
(gdb) set follow-fork-mode child
(gdb) set detach-on-fork off
(gdb) break main
(gdb) run
Breakpoint 1, main () at chall.c:10
(gdb) continue
[New process 12345]
(gdb) info inferiors
  Num  Description       Executable
  1    process 12300     /home/user/chall
* 2    process 12345     /home/user/chall
(gdb) inferior 2
(gdb) info threads
  Id   Target Id                    Frame
* 1    Thread 0x7ffff7d.. (LWP 12345) worker_func () at chall.c:42
```
`info inferiors`에서 `*`가 2번 프로세스로 옮겨진 것을 보고, 실제로 자식 프로세스 안으로 들어와 있다는 것을 확인할 수 있다.

## 관련 글
- REV-0824 — 멀티스레드 프로그램에서 특정 스레드만 멈추는 법
- REV-0638 — libc 함수 사전: pthread_create 기초
- REV-0503 — WinAPI 프로세스 함수 사전: CreateProcess 계열
- REV-0505 — WinAPI 스레드 함수 사전: CreateThread ExitThread
- REV-0617 — 실행마다 API 호출 순서가 달라 보일 때(멀티스레드)
- REV-0822 — Time Travel Debugging 개념 소개(WinDbg 참고) (예정)

## 출처/검증
- GDB `follow-fork-mode`, `detach-on-fork`, `info inferiors`, `info threads`, `thread apply` 명령: GNU GDB 공식 매뉴얼(Debugging with GDB) 문서 기준.
- x64dbg Threads 탭 및 프로세스 attach 절차: x64dbg 공식 GitHub Wiki 문서 기준.
- 자식 프로세스 추적 시 타이밍 문제는 실제 CTF pwn/rev 서버형 문제(fork 기반 서버)에서 반복 관찰되는 패턴 (2026-09-09 검증).
