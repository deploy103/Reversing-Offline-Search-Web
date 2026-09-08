---
id: REV-0234
title: "ptrace PTRACE_TRACEME 안티디버깅"
slug: "rev-0234-ptrace-traceme"
category: "packing"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, strace]
keywords:
  - ptrace
  - PTRACE_TRACEME
  - anti-debug linux
  - 리눅스 안티디버깅
  - 디버거 탐지 리눅스
  - self-trace
  - catch syscall ptrace
  - ptrace 반환값 -1
  - fork ptrace anti-debug
  - GDB 우회
aliases:
  - ptrace가 뭐임
  - ptrace 안티디버깅
  - 리눅스에서 디버거 탐지 어떻게함
  - gdb 붙이면 죽는 프로그램
symptom_keywords:
  - gdb로 attach하면 프로그램이 바로 종료됨
  - gdb run 하면 정상인데 attach하면 이상함
  - strace에서 ptrace 호출이 보임
  - ptrace 반환값이 -1임
  - 이미 트레이스 중이라는 에러가 남
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Linux에서는 **한 프로세스를 동시에 두 개의 트레이서(tracer)가 `ptrace`할 수 없다**는 커널 규칙을 이용해, 크랙미/악성코드가 시작하자마자 스스로 `ptrace(PTRACE_TRACEME, 0, 0, 0)`을 호출해서 "이미 나를 추적 중인 프로세스가 있다"는 상태를 만들어 놓고, 나중에 GDB 같은 진짜 디버거가 붙으려 하면 그 호출이 실패하는 것을 이용해 디버거의 존재를 간접적으로 탐지하는 기법이다.

## 언제 검색해야 하나
- GDB로 `attach <pid>`를 시도했는데 `Operation not permitted` 에러가 뜨거나, 붙긴 붙었는데 프로그램이 곧바로 이상하게 종료될 때
- `strace ./chall`로 실행해봤더니 초반에 `ptrace(PTRACE_TRACEME, ...)` 호출이 보이는데 이게 뭔지 궁금할 때
- CTF pwnable/reversing 문제 설명에 "디버거로 못 붙게 막아뒀다"는 힌트가 있을 때
- `ltrace`/`strace` 로그에서 `ptrace` 호출의 리턴값이 `-1`이고 곧이어 프로그램이 `exit()`을 호출하는 패턴을 볼 때

## 핵심 개념

### ptrace란 무엇인가
`ptrace(2)`는 Linux 커널이 제공하는 시스템 콜로, 한 프로세스(트레이서)가 다른 프로세스(트레이시, tracee)의 메모리·레지스터를 읽고 쓰고, 시스템 콜/시그널을 가로채고, 실행을 한 단계씩 멈출 수 있게 해주는 기반 기능이다. GDB, strace, ltrace 모두 내부적으로 이 `ptrace` 시스템 콜을 사용해서 동작한다 — 즉 **GDB가 프로그램을 디버깅한다는 것 자체가 커널 관점에서는 "GDB가 그 프로세스에 대해 ptrace 트레이서가 된다"는 뜻**이다.

### 핵심 규칙: 트레이서는 하나만
Linux 커널은 **한 프로세스당 하나의 ptrace 트레이서만 허용**한다. 이미 어떤 프로세스가 특정 대상을 트레이싱하고 있으면, 다른 프로세스가 같은 대상에 `ptrace(PTRACE_ATTACH, ...)`나 `PTRACE_TRACEME`를 시도하면 실패한다(`errno`가 `EPERM`으로 설정되고 반환값 `-1`).

### PTRACE_TRACEME를 이용한 자가 방어
크랙미나 악성코드는 이 규칙을 거꾸로 이용한다. 프로그램이 시작하자마자(보통 `main` 진입 직후, 또는 그보다 더 이른 시점) 스스로에게 다음을 호출한다.
```c
#include <sys/ptrace.h>
long ret = ptrace(PTRACE_TRACEME, 0, 0, 0);
```
`PTRACE_TRACEME`는 "지금부터 내 부모 프로세스를 내 트레이서로 등록해달라"는 요청이다. 이 호출 자체는 정상적인 프로그램에서도 쓰이는 기능이지만(예: 디버거가 자식 프로세스를 실행할 때 내부적으로 사용), 안티디버깅 목적의 프로그램은 이걸 **아무도 자신을 추적하지 않는 상태에서 미리 스스로 호출**해 트레이서 슬롯을 선점해버린다.

이렇게 되면:
1. 정상 실행(디버거 없이): `PTRACE_TRACEME` 호출이 성공하고(부모 프로세스, 대개 쉘이 트레이서로 등록됨) 반환값이 `0`이다. 프로그램은 정상 경로로 진행한다.
2. GDB로 실행(`gdb ./chall`, `run`): GDB가 이미 그 프로세스를 `PTRACE_ATTACH`(또는 `fork` 후 자동으로) 트레이서로 등록한 상태이므로, 프로그램 자신이 호출하는 `PTRACE_TRACEME`가 **이미 트레이서가 있다는 이유로 실패**한다(`-1` 반환, `errno == EPERM`). 프로그램은 이 반환값을 확인해서 "나는 지금 디버깅당하고 있다"고 판단하고, 종료하거나 오동작을 유도한다.

```c
if (ptrace(PTRACE_TRACEME, 0, 0, 0) == -1) {
    // 이미 트레이서가 있음 -> 디버거로 실행 중
    puts("no debugging allowed");
    exit(1);
}
```

이 기법의 핵심은 "디버거를 직접 탐지"하는 게 아니라 **"내가 셀프 트레이서 등록에 실패했다 = 누군가 먼저 나를 붙잡고 있다"는 간접 신호를 이용**한다는 점이다. `IsDebuggerPresent`(Windows, REV-0235)와 원리는 다르지만 목적은 동일하다.

### 변형 기법: fork + 부모가 트레이서
좀 더 정교한 버전은 `fork()`로 자식 프로세스를 만들고, 부모 프로세스가 직접 `PTRACE_ATTACH`로 자식을 추적하며 실제 로직을 자식에서 실행한다. 이러면 GDB가 붙으려고 해도 이미 부모가 트레이서 자리를 차지하고 있어 실패하고, 게다가 실제 실행 흐름이 부모-자식 사이에 나뉘어 있어 분석이 한층 더 번거로워진다.

## 화면/코드에서 보이는 징후
- `strace ./chall` 초반 로그에 `ptrace(PTRACE_TRACEME, ...)` 호출이 보인다(단, `strace` 자체도 `ptrace`를 쓰므로 `strace`로 실행하면 이 호출이 실패로 나올 수 있다는 점도 함께 관찰된다 — 그 자체가 또 하나의 힌트다).
- 디컴파일 코드에서 `main` 초반부에 알 수 없는 시스템 콜 wrapper 호출 하나와 그 반환값을 `cmp`/`test`하는 분기가 있다.
- IDA/Ghidra에서 import 목록에 `ptrace`가 있고, xref를 따라가면 프로그램 아주 초반(entry 근처)에서 호출된다.
- 정상 실행(`./chall`)은 잘 되는데 `gdb ./chall` → `run`으로 실행하면 이상하게 조용히 죽거나 다른 메시지가 뜬다.

## 가장 먼저 할 것
1. `strace -f ./chall`로 프로그램 초반에 정말 `ptrace(PTRACE_TRACEME, ...)` 호출이 있는지 확인한다.
2. IDA/Ghidra에서 import된 `ptrace` 심볼의 xref를 찾아 호출 위치와, 반환값을 확인하는 분기 코드를 찾는다.
3. 분기 목표(실패 시 이동하는 블록)에 `exit`/`abort`/이상 동작 코드가 있는지 확인한다.

## 단계별 절차
1. 먼저 정적 분석으로 `ptrace` 호출 위치를 찾는다(`objdump -d ./chall | grep -A5 'call.*ptrace@plt'` 또는 IDA import xref).
2. 반환값(보통 `EAX`/`RAX`)을 검사하는 `cmp`/`test` + 조건 분기를 찾는다.
3. **가장 간단한 우회(교육/CTF 목적, 자신이 풀고 있는 크랙미에 한함)**: 그 조건 분기 명령을 GDB에서 NOP으로 패치하거나, `set $eflags` 등으로 분기 조건을 강제로 반전시켜 "트레이서 없음" 경로로 가도록 만든다.
4. **더 근본적인 우회**: `ptrace` 호출 자체를 패치해서 항상 성공(`0`)을 반환하도록 만든다 — 함수 진입부에 `mov rax, 0; ret`로 패치하거나, GDB의 `catch syscall ptrace` 기능으로 그 시스템 콜이 실행되는 순간을 잡아 결과 레지스터를 조작한다.
5. Pwndbg를 쓴다면 `set follow-fork-mode child`, `set detach-on-fork off` 등의 옵션과 함께 실제로 `ptrace` 콜이 어떻게 실패하는지 단계별로 관찰하면 이해가 빠르다.

## 명령어/단축키
- GDB: `catch syscall ptrace`로 `ptrace` 시스템 콜 진입 시점에 자동으로 멈추기, `finish`로 함수 리턴까지 실행 후 `p $rax`로 반환값 확인, `set $rax = 0`으로 반환값을 강제로 성공(0)으로 조작
- GDB: `b *0x<주소>` 후 `stepi`로 한 줄씩 실행하며 분기 조건 확인
- Pwndbg: `context` 명령으로 현재 레지스터/디스어셈블리를 한 화면에서 확인, `patch` 플러그인 명령으로 명령어 직접 패치
- Linux: `strace -f -e trace=ptrace ./chall`(ptrace 호출만 필터링해서 관찰)

## 출력 해석
- `strace` 출력에서 `ptrace(PTRACE_TRACEME, 0, 0, 0) = 0`이면 성공(트레이서 없음/등록 성공)이고, `= -1 EPERM (Operation not permitted)`이면 실패(이미 트레이서 존재)다.
- GDB에서 `catch syscall ptrace` 후 `finish`로 반환값을 봤을 때 `$rax`가 `0xffffffffffffffff`(즉 `-1`)이면 GDB 자신이 이미 트레이서라서 실패한 것 — 정상적인 현상이며, 프로그램이 이 값을 어떻게 처리하는지가 관건이다.

## 흔한 실수
- `ptrace(PTRACE_TRACEME, ...)` 실패를 GDB 설정 문제로 착각하고 GDB를 재설치하거나 권한을 만지는 것 — 이것은 프로그램이 의도적으로 넣은 탐지 로직이다.
- `strace`로 관찰하려다가 `strace` 자체가 트레이서 역할을 해서 프로그램의 `PTRACE_TRACEME`가 또 실패하는 것을 이상 현상으로 오해하는 것 — 오히려 이게 탐지 로직이 작동하고 있다는 증거다.
- 반환값 분기만 패치하고 이후 코드에서 또 다른 `ptrace` 호출(예: `PTRACE_PEEKTEXT`로 자기 코드에 브레이크포인트가 있는지 스캔)이 있다는 걸 놓치는 것 — 안티디버깅은 보통 한 곳에만 있지 않다.
- fork 기반 변형에서 자식 프로세스만 디버깅하려다 부모 프로세스의 트레이서 등록을 놓치는 것 — `set follow-fork-mode`, `set detach-on-fork` 옵션을 반드시 확인해야 한다.

## 막혔을 때 다음 체크
- GDB로 attach만 해도 바로 죽는다면 → `strace -f -p <pid>`로 먼저 어떤 시스템 콜이 실패하는지 살펴본다.
- 패치했는데도 여전히 이상하게 종료된다면 → `ptrace` 호출이 여러 번(다른 요청 타입으로) 있는지 xref를 다시 전수 조사한다.
- 정적 분석으로 로직을 다 이해했는데도 확신이 안 서면 → 일단 `ptrace` 관련 분기를 전부 무조건 "정상" 경로로 강제하고 실행해서 결과를 관찰한다.
- 리눅스 시스템 콜 자체가 낯설다면 → `../linux-elf/rev-0112-strace-basics.md`에서 strace 기본 사용법부터 확인한다.

## 미니 예제
**예제 1 — 전형적인 자가 트레이싱 체크**
```c
#include <sys/ptrace.h>
#include <stdio.h>
#include <stdlib.h>

int main() {
    if (ptrace(PTRACE_TRACEME, 0, 0, 0) < 0) {
        puts("debugger detected");
        exit(1);
    }
    puts("welcome");
    // ... 실제 로직 ...
}
```

**예제 2 — GDB에서 시스템 콜 가로채서 반환값 조작**
```text
(gdb) catch syscall ptrace
(gdb) run
Catchpoint 1 (call to syscall ptrace), 0x... in ptrace ()
(gdb) finish
Run till exit from #0 ptrace ()
Value returned is $1 = -1
(gdb) set $rax = 0
(gdb) continue
```
`catch syscall ptrace`로 호출 시점을 잡고, `finish`로 함수가 끝날 때까지 실행한 뒤, 반환값(`$rax`)이 담긴 레지스터를 직접 `0`으로 바꿔서 프로그램이 "성공"으로 착각하게 만드는 방식이다. 자신이 만들거나 CTF 문제로 받은 크랙미를 학습 목적으로 분석할 때만 사용해야 한다.

## 관련 글
- REV-0239 — Exception 기반 안티디버깅 기초
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트

## 출처/검증
- `ptrace(2)` 시스템 콜과 "한 프로세스당 하나의 트레이서" 제약: Linux man-pages 프로젝트의 `ptrace(2)` 매뉴얼 페이지 기준(2026-09-08 검증).
- `PTRACE_TRACEME`를 이용한 셀프 트레이싱 기반 안티디버깅 기법: 다수의 공개 리눅스 안티디버깅/CTF 리버싱 교육 자료에서 공통적으로 설명하는 표준 기법을 정리함.
