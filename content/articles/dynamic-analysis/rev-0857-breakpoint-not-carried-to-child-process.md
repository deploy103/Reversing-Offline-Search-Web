---
id: REV-0857
title: "자식 프로세스로 브레이크포인트가 안 넘어갈 때"
slug: "rev-0857-breakpoint-not-carried-to-child-process"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg]
keywords: ["follow-fork-mode", "자식 프로세스 디버깅", "fork 이후 디버거", "CreateProcess 자식 attach"]
aliases: ["fork한 자식이 디버거에 안 잡힘", "자식 프로세스 브레이크포인트 안걸림", "child process 디버깅 안됨"]
symptom_keywords: ["fork 이후 자식 프로세스가 그냥 실행돼버린다", "자식 프로세스에 건 브레이크포인트가 안먹힌다", "CreateProcess로 만든 프로세스를 못따라간다", "부모만 멈추고 자식은 계속 간다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
디버거는 기본적으로 자신이 직접 실행/attach한 **하나의 프로세스만** 추적하므로, 대상 프로그램이 `fork`/`CreateProcess`로 새 프로세스를 만들면 그 자식 프로세스는 별도의 설정 없이는 디버거의 감시 범위 밖으로 그냥 실행돼 버린다 — GDB의 `follow-fork-mode`나 x64dbg의 자식 프로세스 옵션을 명시적으로 켜야 자식까지 따라간다.

## 언제 검색해야 하나
- `fork()`나 `CreateProcess`가 있는 걸 코드에서 확인했는데, 자식 프로세스 쪽에 걸어둔 브레이크포인트가 전혀 안 걸릴 때
- 부모 프로세스는 디버거에 잘 잡혀 있는데 자식 프로세스는 창이 뜨거나 로그를 남기며 자기 혼자 정상적으로 끝까지 실행돼 버릴 때
- 자식 프로세스 쪽에서만 발생하는 크래시/분기를 재현하고 싶은데 디버거가 부모만 붙잡고 있어 그 시점을 놓칠 때
- 멀티 프로세스 구조(부모-자식-손자)인 프로그램에서 몇 단계까지 디버거가 따라가야 할지 헷갈릴 때

## 핵심 개념

### 디버거와 대상 프로세스는 1:1이 기본값
GDB/x64dbg는 `ptrace`(Linux) 또는 Windows 디버그 API로 특정 PID 하나를 추적한다. `fork()`가 호출되면 커널이 새 프로세스(자식)를 만들지만, 이 자식은 기본적으로 디버거의 추적 대상이 아니다 — 디버거에게 "이 자식도 따라가라"고 명시적으로 지시해야 한다.

### GDB의 follow-fork-mode
GDB는 `set follow-fork-mode`로 `fork()` 발생 시 부모를 계속 따라갈지(`parent`, 기본값), 자식을 따라갈지(`child`)를 정할 수 있다. 기본값이 `parent`이기 때문에, 아무 설정 없이 자식 코드를 디버깅하려 하면 항상 실패한다.

### GDB의 detach-on-fork
`set detach-on-fork off`를 추가하면 부모/자식 둘 다 GDB가 붙잡아 둔 채로(하나는 멈춘 상태로) 관리할 수 있어, `inferior` 명령으로 두 프로세스를 오가며 디버깅할 수 있다.

### Windows의 CreateProcess와 디버그 이벤트
Windows에서 디버기가 `CreateProcess`로 자식을 만들 때, 디버거가 `DEBUG_ONLY_THIS_PROCESS` 플래그로 자식을 추적하고 있었다면 자식 프로세스에서 발생하는 디버그 이벤트(브레이크포인트 등)는 디버거에 전달되지 않는다. `DEBUG_PROCESS` 플래그(자식까지 포함)로 붙어 있어야 하며, x64dbg는 설정에서 이를 켜고 끌 수 있다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) break child_only_function
(gdb) run
# 부모 프로세스만 브레이크포인트에 걸리고, fork 이후 자식이 만든 새 창/출력은 그대로 진행됨
```
x64dbg에서는 자식 프로세스가 별도의 프로세스로 작업 관리자에 나타나지만 x64dbg 창에는 잡히지 않고, Attach 목록에서만 보임.

## 가장 먼저 할 것
GDB라면 `show follow-fork-mode`로 현재 설정을 확인한다. 기본값(`parent`)이면 `set follow-fork-mode child`(또는 `parent`+`detach-on-fork off`)로 바꾸고 다시 실행한다. x64dbg라면 Options → Settings → Events에서 자식 프로세스 관련 옵션(System Breakpoint/Attach 관련)을 확인한다.

## 단계별 절차

**1) GDB — 자식을 따라가도록 설정**
```gdb
(gdb) set follow-fork-mode child
(gdb) break child_only_function
(gdb) run
```
`fork()` 호출 시점부터 GDB가 자식 프로세스로 전환되어 계속 추적한다. 부모 쪽 코드를 마저 보고 싶다면 다시 `set follow-fork-mode parent`로 되돌린다.

**2) GDB — 부모/자식 둘 다 유지하고 오가기**
```gdb
(gdb) set detach-on-fork off
(gdb) run
(gdb) info inferiors
  Num  Description       Executable
  1    process 1001      /path/chall
* 2    process 1002      /path/chall
(gdb) inferior 2
```
`inferior N`으로 원하는 프로세스로 전환해서 각각 독립적으로 브레이크포인트/스텝을 진행할 수 있다.

**3) GDB — execve까지 자동으로 따라가기**
`fork` 후 곧바로 `execve`로 다른 바이너리를 실행하는 구조(전형적인 서버의 `fork`+`exec` 패턴)라면 `set follow-exec-mode`도 함께 확인한다.
```gdb
(gdb) set follow-exec-mode new
```

**4) x64dbg — 자식 프로세스 디버깅 옵션 확인**
Options → Preferences(Settings) → Events 탭에서 "Attach to child process" 또는 유사한 자식 프로세스 관련 항목을 켠다. 버전에 따라 명칭이 다를 수 있으므로 Events/Engine 관련 설정을 모두 훑어본다.

**5) 자식 PID를 미리 알아내서 별도로 attach**
자동 추적이 여의치 않다면, 부모에서 `fork`/`CreateProcess` 반환 직후(REV-0852 참고) 자식 PID를 확인한 뒤, 별도의 디버거 인스턴스로 그 PID에 직접 attach한다.
```gdb
# 부모 GDB 세션에서 fork() 반환 직후
(gdb) print $rax    # fork()의 자식 프로세스 리턴값(자식 PID, 0이면 자식 자신 내부)
```
```bash
# 별도 터미널에서
gdb -p <자식PID>
```

**6) Windows에서 별도 프로세스로 attach**
자식이 이미 실행 중이라면 작업 관리자/`tasklist`로 PID를 확인하고 x64dbg의 Attach 메뉴로 그 PID에 직접 붙는다. 단, 이 경우 자식 프로세스의 아주 초반 코드(진입점 근처)는 이미 지나가 버렸을 수 있다.

## 명령어/단축키
```gdb
(gdb) show follow-fork-mode
(gdb) set follow-fork-mode parent|child
(gdb) set detach-on-fork on|off
(gdb) info inferiors
(gdb) inferior N
(gdb) set follow-exec-mode new|same
```
```
x64dbg: Options → Preferences → Events(자식 프로세스 관련 옵션)
x64dbg: File → Attach(자식 PID 직접 attach)
```

## 출력 해석
- `info inferiors`에 프로세스가 하나만 나온다면 `detach-on-fork`가 켜져 있어(기본값) 다른 쪽은 이미 분리되어 실행 중이라는 뜻이다.
- `set follow-fork-mode child` 이후 `run`을 하면, `fork()` 호출 시점에 GDB 프롬프트에 `[Attaching after fork to child process ####]` 같은 메시지가 뜨며 자식으로 전환된 것을 알 수 있다.
- 자식 PID로 별도 attach했는데 이미 진입점을 지나 있다면, 부모 쪽에서 자식이 바로 실행되지 않고 대기하도록(예: 환경변수, `raise(SIGSTOP)` 삽입 등 코드 수정이 가능하다면) 조정하는 것도 방법이다.

## 흔한 실수
- `follow-fork-mode`를 매번 설정해야 한다는 것을 잊고 새 GDB 세션마다 자식이 안 잡힌다고 헷갈리는 것 — `.gdbinit`에 기본값으로 넣어두면 편하다.
- `follow-fork-mode child`로 바꾼 뒤 부모 쪽 코드를 더 이상 볼 수 없다는 걸 모르고 "부모가 사라졌다"고 착각하는 것 — `detach-on-fork off`를 함께 써야 둘 다 유지된다.
- `fork` 직후 `execve`로 완전히 다른 바이너리를 실행하는 경우 `follow-exec-mode`도 같이 확인하지 않아 자식은 따라갔는데 그 안에서 실행되는 새 바이너리는 못 따라가는 것.
- 이미 실행 중인 자식 프로세스에 뒤늦게 attach하면서 초반 코드(가장 중요한 부분일 수 있음)를 놓쳤다는 걸 인지 못하는 것.

## 막혔을 때 다음 체크
- 여러 자식 프로세스가 동시에 떠서 분석이 꼬이는 상황이라면 → REV-0603 프로세스가 여러 개 자식 프로세스를 만들어 분석이 꼬일 때.
- `fork`/`exec`/`CreateProcess` 함수 자체의 기본 동작이 궁금하다면 → REV-0637 libc 함수 사전: fork exec 계열, REV-0503 WinAPI 프로세스 함수 사전: CreateProcess 계열.
- 반환값(자식 PID)을 확인하는 절차 자체가 헷갈린다면 → REV-0852 함수 반환 직후로 브레이크포인트를 옮기고 싶은데 위치를 못 찾을 때.

## 미니 예제
```gdb
(gdb) show follow-fork-mode
Debugger response to a program call of fork or vfork is "parent".
(gdb) set follow-fork-mode child
(gdb) break handle_client
(gdb) run
[Attaching after fork to child process 5821]
[New inferior 2 (process 5821)]
Breakpoint 1, handle_client (fd=4) at server.c:60
```
기본값(`parent`)일 때는 자식 쪽 `handle_client`가 전혀 안 걸렸지만, `follow-fork-mode child`로 바꾸자 `fork()` 시점에 자동으로 자식 프로세스로 전환되어 원하던 브레이크포인트가 정상적으로 걸렸다.

## 관련 글
- REV-0603 — 프로세스가 여러 개 자식 프로세스를 만들어 분석이 꼬일 때
- REV-0637 — libc 함수 사전: fork exec 계열
- REV-0503 — WinAPI 프로세스 함수 사전: CreateProcess 계열

## 출처/검증
- GDB `follow-fork-mode`/`detach-on-fork`/`follow-exec-mode`/`info inferiors` 동작: GDB 공식 매뉴얼 "Debugging Forks" 챕터 기준.
- Windows 디버그 API의 `DEBUG_PROCESS`/`DEBUG_ONLY_THIS_PROCESS` 플래그와 자식 프로세스 디버그 이벤트 전달 방식: Microsoft 공식 문서(`CreateProcess`, Debugging) 기준 (2026-09-09 검증).
