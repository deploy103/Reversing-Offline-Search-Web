---
id: REV-0842
title: "하드웨어 브레이크포인트도 탐지당할 때"
slug: "rev-0842-hardware-breakpoint-also-detected"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords: ["DR7 탐지", "GetThreadContext", "PTRACE_PEEKUSER", "u_debugreg", "디버그 레지스터 탐지", "self-ptrace"]
aliases: ["ba로 걸어도 감지됨", "하드웨어 브레이크포인트 우회 불가", "DR 레지스터 탐지 우회"]
symptom_keywords: ["ba로 걸었는데도 감지됨", "GetThreadContext 호출 뒤 이상한 분기", "하드웨어 브레이크포인트가 사라짐", "디버그 레지스터를 자식 프로세스가 읽음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-SYSV-ABI", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
하드웨어 브레이크포인트는 코드 바이트를 건드리지 않지만 CPU의 디버그 레지스터(DR0~DR7)에 흔적을 남기므로, Windows는 `GetThreadContext`로 직접, Linux는 자기 자신을 ptrace로 감시하는 자식 프로세스를 만들어(`PTRACE_PEEKUSER`) 간접적으로 이 레지스터 값을 읽어내면 "코드는 안 건드렸지만 디버거가 붙어 있다"는 사실을 알아낼 수 있다.

## 언제 검색해야 하나
- x64dbg에서 `ba`(하드웨어 브레이크포인트)로 걸었을 때만 프로그램이 다르게 동작하거나 종료될 때
- 코드에서 `GetThreadContext` 호출 뒤 `CONTEXT.Dr7` 오프셋 근처를 검사하는 패턴을 발견했을 때
- GDB `watch`(하드웨어 워치포인트)나 하드웨어 브레이크포인트를 걸었는데도 프로그램이 이상 동작하거나, 걸어둔 하드웨어 브레이크포인트가 어느 순간 사라질 때
- 프로그램이 시작하자마자 자식 프로세스를 하나 만들고, 그 자식이 부모를 `ptrace`로 감시하는 듯한 구조를 발견했을 때

## 핵심 개념

### 디버그 레지스터(DR0~DR7)는 코드가 아니라 CPU 상태다
x86/x64는 감시 주소 4개(DR0~DR3)와 제어/상태 레지스터(DR6, DR7)로 구성된 하드웨어 브레이크포인트 기능을 제공한다. 코드 메모리를 전혀 건드리지 않으므로 소프트웨어 브레이크포인트 탐지(REV-0841)에는 걸리지 않지만, 이 레지스터 값 자체를 읽을 수만 있다면 여전히 "누군가 나를 감시 중"임을 알아낼 수 있다.

### Windows — GetThreadContext로 직접 읽기
Windows는 유저 모드에서 합법적으로 자기 스레드의 디버그 레지스터를 읽을 수 있는 API(`GetThreadContext` + `CONTEXT_DEBUG_REGISTERS`)를 제공한다. `Dr0`~`Dr3`나 `Dr7`이 0이 아니면 디버거가 하드웨어 브레이크포인트를 걸어뒀다는 뜻이다. 상세 오프셋과 우회 방법은 REV-0536에서, 프로그램이 스스로 이 값을 초기화해 디버거의 하드웨어 브레이크포인트를 무력화하는 변형은 REV-0607에서 다룬다.

### Linux — 일반 프로세스는 자기 디버그 레지스터를 직접 못 읽는다
Linux는 Windows의 `GetThreadContext` 같은 유저모드 API가 없다. 디버그 레지스터는 `ptrace(PTRACE_PEEKUSER, ...)`로 **다른 프로세스의 tracer만** 읽을 수 있다. 그래서 리눅스 바이너리가 이 정보를 얻으려면 스스로 tracer가 되어야 하는데, 이미 GDB가 tracer 자리를 차지하고 있으면 `ptrace(PTRACE_ATTACH, ...)`가 실패한다(REV-0234의 self-attach 원리와 동일). 이를 우회하기 위해 프로그램은 자식 프로세스를 `fork`해서, 그 자식이 부모를 `PTRACE_ATTACH`로 붙으려 시도하거나(이미 GDB가 붙어 있으면 실패 자체가 신호가 됨), 또는 자식이 `PTRACE_TRACEME`로 스스로를 추적 대상으로 만들고 부모가 자식의 컨텍스트를 읽는 구조를 쓴다.
```c
long dr7 = ptrace(PTRACE_PEEKUSER, child_pid,
                   offsetof(struct user, u_debugreg[7]), NULL);
if (dr7 != 0) { /* 하드웨어 브레이크포인트 감지 */ }
```

### 스레드/프로세스마다 별도로 존재
디버그 레지스터는 스레드(Windows)/태스크(Linux) 단위로 별도이므로, 멀티스레드 프로그램은 여러 스레드 각각에서 이 검사를 반복할 수 있다.

## 화면/코드에서 보이는 징후
```asm
mov  [rbp+ctx.ContextFlags], 100010h
call GetThreadContext
cmp  qword ptr [rbp+ctx.Dr7], 0
jnz  detected
```
- `GetThreadContext`/`Wow64GetThreadContext` 임포트(Windows)
- 시작 직후 생성되는 자식 프로세스가 있고, 그 자식이 부모 PID로 `ptrace` 계열 syscall을 호출하는 패턴(Linux, `strace`로 확인 가능)
- x64dbg `ba`로 건 브레이크포인트가 실행 중 `bl` 목록에서는 보이는데 실제로는 트리거되지 않음(REV-0607의 무력화형)

## 가장 먼저 할 것
Windows라면 IDA에서 `GetThreadContext` 교차 참조를 모두 찾아 `ContextFlags`와 비교 대상 필드를 확인한다. Linux라면 `strace -f`로 자식 프로세스가 생성되는지, 그 자식이 `ptrace(PTRACE_ATTACH/PTRACE_PEEKUSER, ...)`를 호출하는지 확인한다.

## 단계별 절차
1. Windows: `GetThreadContext` 호출부에 소프트웨어 브레이크포인트를 걸어 반환된 `CONTEXT.Dr7` 값을 확인한다(REV-0536 참고).
2. Windows: ScyllaHide로 `GetThreadContext`/`SetThreadContext`를 후킹해 항상 0으로 위장한다.
3. Linux: `strace -f -e trace=ptrace ./chall`로 자식이 어떤 ptrace 요청을 하는지 확인한다.
4. Linux: 자식이 `PTRACE_ATTACH`로 부모에게 붙으려는 구조라면, GDB가 이미 부모를 tracer로 잡고 있으므로 자식의 attach 자체가 실패하는지(그 실패를 프로그램이 어떻게 해석하는지) 확인한다.
5. 두 플랫폼 모두, 이 검사 함수의 반환값을 강제로 "탐지 안 됨"으로 패치하는 것이 가장 직접적인 대응이다.

## 명령어/단축키
```text
x64dbg: bp GetThreadContext, ScyllaHide Options → Anti-Debug
```
```bash
strace -f -e trace=ptrace ./chall
```
```gdb
break GetThreadContext   # Wine/일부 환경, 일반적으로는 정적 분석 후 직접 주소 지정
```

## 출력 해석
`CONTEXT.Dr7`이 0이 아니면 하드웨어 브레이크포인트가 걸려 있다는 뜻이다(Windows). `strace`에서 자식의 `ptrace(PTRACE_ATTACH, 부모PID, ...)`가 `-1 EPERM`으로 실패한다면, 이미 다른 tracer(GDB)가 붙어 있어서 실패한 것이며 이 실패 자체를 프로그램이 "디버거 있음" 신호로 쓸 수 있다.

## 흔한 실수
- 하드웨어 브레이크포인트는 절대 탐지될 수 없다고 가정하는 것 — 코드는 안 건드리지만 CPU 레지스터에 흔적이 남는다는 점을 잊는 것.
- Linux는 Windows의 `GetThreadContext` 같은 API가 없어서 이런 탐지가 아예 불가능하다고 단정하는 것 — self-ptrace 기법으로 동일한 효과를 낼 수 있다.
- Windows와 Linux의 `CONTEXT`/`user` 구조체 오프셋이 아키텍처(x86/x64)마다 다르다는 것을 잊고 계산하는 것.
- 이 검사 하나만 우회하면 끝이라고 생각하는 것 — 소프트웨어 브레이크포인트 탐지(REV-0841)나 다른 안티디버깅과 함께 쓰이는 경우가 많다.

## 막혔을 때 다음 체크
- Windows GetThreadContext 탐지의 상세 오프셋/우회가 필요하다면 → REV-0536 하드웨어 브레이크포인트(DR 레지스터) 탐지 기법
- 하드웨어 브레이크포인트가 걸다가 갑자기 사라진다면 → REV-0607 하드웨어 브레이크포인트가 갑자기 사라질 때
- Linux self-ptrace 원리 자체가 궁금하다면 → REV-0234 ptrace PTRACE_TRACEME 안티디버깅
- 소프트웨어 브레이크포인트 탐지와 구분이 안 된다면 → REV-0841 소프트웨어 브레이크포인트가 안티디버깅에 걸릴 때

## 미니 예제
Linux 바이너리를 `strace -f`로 관찰하니 시작 직후 `fork` 후 자식이 `ptrace(PTRACE_ATTACH, 부모PID, ...)`를 호출했다가 `EPERM`으로 실패하는 것이 보였다. GDB가 이미 부모 프로세스의 tracer였기 때문이다. 이 실패 반환값을 검사해 종료하는 분기를 찾아 NOP 처리하니 정상적으로 진행됐다.

## 관련 글
- REV-0536 — 하드웨어 브레이크포인트(DR 레지스터) 탐지 기법
- REV-0607 — 하드웨어 브레이크포인트가 갑자기 사라질 때
- REV-0234 — ptrace PTRACE_TRACEME 안티디버깅
- REV-0841 — 소프트웨어 브레이크포인트가 안티디버깅에 걸릴 때

## 출처/검증
- Windows `GetThreadContext`/`CONTEXT_DEBUG_REGISTERS`와 `Dr0`~`Dr7` 필드: Microsoft 공식 문서(`winnt.h`) 기준.
- Linux에서 일반 프로세스가 자신의 디버그 레지스터를 직접 읽을 수 없고 `ptrace(PTRACE_PEEKUSER, ...)`로 tracer만 대상 태스크의 `struct user.u_debugreg`를 읽을 수 있다는 점: `ptrace(2)` man page 및 Linux 커널 소스(`arch/x86/include/asm/user_64.h`) 기준(2026-09-09 검증).
- x86 디버그 레지스터(DR0~DR7) 비트 구조: Intel SDM Volume 3B 기준.
