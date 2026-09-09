---
id: REV-0858
title: "디버거가 붙자마자 프로그램이 종료될 때"
slug: "rev-0858-debugger-attach-immediate-exit"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg]
keywords: ["attach 즉시 종료", "디버거 붙이자마자 종료", "system breakpoint 이후 종료", "attach anti-debug"]
aliases: ["디버거 실행하자마자 꺼짐", "attach 하자마자 프로세스 종료", "브레이크포인트도 못 걸고 종료됨"]
symptom_keywords: ["아무것도 안했는데 붙이자마자 종료된다", "run 누르기도 전에 프로세스가 사라진다", "attach 버튼 누르자마자 죽는다", "system breakpoint에서 멈추지도 못하고 종료"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-MS-PE-FORMAT"]
last_verified: "2026-09-09"
---

## 한 줄 요약
브레이크포인트를 하나도 안 걸었고 아무 명령도 안 내렸는데 attach/실행하자마자 프로세스가 사라진다면, 원인은 크게 두 갈래다 — **프로그램 시작 코드(CRT/진입점 근처)에 있는 안티디버깅 체크가 즉시 작동**했거나, **디버거 실행 방식 자체가 정상 실행과 달라서**(인자 누락, 작업 디렉터리 차이, 콘솔 분리) 프로그램이 원래 로직대로 정상 종료한 것이다. 먼저 "이게 정말 안티디버깅인가"부터 5분 안에 가려내는 것이 핵심이다.

## 언제 검색해야 하나
- x64dbg로 열자마자(System Breakpoint에서 F9를 누르는 순간), 또는 attach 버튼을 누르자마자 대상 프로세스가 사라질 때
- GDB `run`을 치자마자, 브레이크포인트를 하나도 안 걸었는데도 바로 종료 메시지가 뜰 때
- 같은 바이너리를 그냥 더블클릭/셸에서 실행하면 멀쩡한데 디버거를 통해서만 실행하면 항상 이 증상이 재현될 때
- 원인이 안티디버깅인지, 단순히 디버거에서 실행할 때 인자/환경이 달라서인지 구분이 안 될 때

## 핵심 개념

### "즉시 종료"는 REV-0240 체크리스트의 특수 케이스
REV-0240(디버거에서 갑자기 종료될 때 체크리스트)은 실행 도중 임의 시점에 죽는 상황까지 폭넓게 다룬다. 이 글은 그중에서도 **attach/실행 직후, 사용자가 아직 아무 조작도 하기 전**이라는 좁은 상황만 다룬다. 이 경우 타이밍 체크(REV-0237)나 Step 실행 중 감지 같은 "시간이 걸려야 발동하는" 체크는 원인일 가능성이 낮고, **프로세스 시작과 동시에 한 번만 확인하는 정적인 체크**(PEB 플래그, `IsDebuggerPresent`, `ptrace(PTRACE_TRACEME)` 자가 트레이싱)가 유력한 후보로 좁혀진다.

### CRT/런타임 초기화 코드가 main() 이전에 이미 체크를 끝냄
많은 안티디버깅 체크는 `main()`이 시작되기도 전, CRT 초기화 루틴이나 TLS 콜백(Windows PE의 경우)에서 실행된다. 사용자가 `main`에 브레이크포인트를 걸어놨어도, 그 브레이크포인트에 도달하기 전에 이미 프로세스가 죽어버릴 수 있다 — 브레이크포인트가 "안 걸린 것"이 아니라 그 지점에 도달하기 전에 종료된 것이다.

### 안티디버깅이 아닐 수도 있다 — 디버거의 실행 방식 자체가 원인인 경우
디버거로 프로그램을 실행하면 명령줄 인자, 작업 디렉터리, 표준입출력 연결 방식이 셸에서 직접 실행할 때와 다를 수 있다. 프로그램이 인자가 없으면 사용법을 출력하고 바로 종료하도록 짜여 있는데, 디버거의 기본 실행 설정이 인자를 안 넘겨주고 있다면 "종료됐다"는 증상은 안티디버깅과 전혀 무관하게 그냥 정상적인 "인자 없음" 종료 경로일 수 있다.

### x64dbg의 System Breakpoint 자체를 종료로 착각
x64dbg는 기본적으로 프로세스 시작 시 "System Breakpoint"(ntdll 로더 초기화 시점)에서 한 번 멈추도록 설계되어 있다. 이 설정이 꺼져 있거나 "Pass exception"이 잘못 설정돼 있으면, 이 지점에서 멈추지 못하고 그대로 쭉 실행돼 버려서 마치 "붙이자마자 종료됐다"처럼 보일 수 있다 — 실제로는 안티디버깅이 아니라 그냥 아무 데도 안 멈추고 끝까지 실행된 것이다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) run
Starting program: /path/chall
[Inferior 1 (process 5821) exited with code 01]
```
```
x64dbg: System Breakpoint에서 F9를 누르자마자 프로세스가 목록에서 사라지고
Log 창에 "Process terminated"만 남음
```

## 가장 먼저 할 것
디버거를 거치지 않은 **정상 실행**과 **디버거 실행**을 나란히 비교한다. 종료 코드(exit code)와 콘솔 출력이 서로 다른지 먼저 확인한다.
```bash
# 터미널 1
./chall; echo "exit=$?"
# 터미널 2
gdb -q ./chall -ex run -ex quit
```
두 실행의 종료 코드가 다르면 안티디버깅 쪽으로 무게가 실리고, 같다면(예: 둘 다 인자 오류로 종료) 디버거 실행 설정(인자/환경) 쪽을 먼저 의심한다.

## 단계별 절차

**1) 디버거 실행 설정(인자/작업 디렉터리) 재확인**
- GDB: `run` 대신 실제 필요한 인자를 명시했는지 확인. `(gdb) run arg1 arg2`
- x64dbg: File → Change Command Line Arguments에서 인자가 비어 있지 않은지 확인.
- 작업 디렉터리 의존(상대 경로로 설정 파일을 읽는 프로그램 등)이 있다면 디버거의 시작 디렉터리도 셸 실행 때와 같게 맞춘다.

**2) strace로 자가 트레이싱(Linux) 확인**
```bash
strace -f gdb -q ./chall -ex run 2>&1 | grep ptrace
```
`ptrace(PTRACE_TRACEME, ...)` 호출이 보이고 반환값이 `-1 EPERM`이면, 이미 GDB가 `ptrace`로 이 프로세스를 잡고 있어서 프로그램 자신의 추가 `ptrace(PTRACE_TRACEME)` 시도가 실패한 것 — 이 실패를 감지해 즉시 종료하는 안티디버깅 패턴이다(REV-0234).

**3) Windows에서 PEB/IsDebuggerPresent 체크 확인**
IDA/Ghidra로 Import 목록에서 `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, `NtQueryInformationProcess`를 검색하거나, 진입점 근처 어셈블리에서 `fs:[30h]`(x86)/`gs:[60h]`(x64) 접근을 찾는다(REV-0235, REV-0236, REV-0533).

**4) x64dbg의 예외 전달/시스템 브레이크포인트 설정 확인**
Options → Preferences → Exceptions에서 예외를 자동으로 프로그램에 전달(pass)하도록 되어 있는지 확인한다. 또한 System Breakpoint에서 실제로 멈췄는지(Log 창의 "System breakpoint reached!" 메시지 유무)를 확인한다 — 이 메시지가 아예 없다면 애초에 멈추지 못하고 지나간 것이다(REV-0583 참고).

**5) TLS 콜백/진입점 이전 코드 확인**
PE 헤더의 TLS 디렉터리에 콜백 함수가 등록돼 있는지 확인한다(REV-0133). 등록돼 있다면 `main`보다 먼저 실행되므로, `main`에 건 브레이크포인트로는 그 이전에 일어나는 안티디버깅 체크를 절대 잡을 수 없다.

**6) 그래도 원인이 안 보이면 REV-0240 체크리스트로 전체 훑기**
attach 시점 특화 원인이 없다면, 실행 도중 다른 시점의 체크일 수도 있으니 REV-0240의 8단계 체크리스트를 순서대로 확인한다.

## 명령어/단축키
```gdb
(gdb) run [ARGS]
(gdb) catch syscall ptrace
(gdb) info proc status   # TracerPid 확인용 유사 정보
```
```bash
strace -f -e trace=ptrace ./chall
cat /proc/<PID>/status | grep TracerPid
```
```
x64dbg: File → Change Command Line Arguments
x64dbg: Options → Preferences → Exceptions
x64dbg: Log 창(System breakpoint 도달 여부 확인)
```

## 출력 해석
- 정상 실행과 디버거 실행의 종료 코드가 다르다(`echo $?`로 비교) → 코드 경로 자체가 달라졌다는 확실한 증거. 안티디버깅 가능성이 높다.
- `ptrace(PTRACE_TRACEME, ...)` = `-1 EPERM` → 자가 트레이싱 실패를 감지하는 패턴. GDB로 실행 중일 때만 나타나며, 직접 실행하면 이 호출은 성공(`0`)한다.
- x64dbg Log 창에 "System breakpoint reached!"가 없다 → 애초에 멈추지 못하고 지나간 것이므로, 예외 전달 설정이나 브레이크포인트 방식(하드웨어 vs 소프트웨어)부터 점검한다.
- 정상 실행과 디버거 실행의 종료 코드가 **같다**(예: 둘 다 사용법 출력 후 종료) → 안티디버깅이 아니라 인자/환경 설정 문제일 가능성이 크다.

## 흔한 실수
- 디버거 실행 시 인자를 빠뜨린 것을 안티디버깅으로 오인해서 엉뚱하게 우회 코드를 찾아 헤매는 것 — 항상 정상 실행과 종료 코드부터 비교해야 한다.
- `main`에만 브레이크포인트를 걸어두고, TLS 콜백이나 CRT 초기화 코드에서 이미 종료됐다는 것을 모른 채 "브레이크포인트가 안 걸린다"고 헷갈리는 것(이 경우는 REV-0852/REV-0857과는 다른 문제이며, 애초에 그 지점에 도달하지 못하는 것이다).
- x64dbg의 System Breakpoint 메시지 유무를 확인하지 않고 바로 "안티디버깅이다"라고 단정하는 것.
- 하나의 체크(예: PTRACE_TRACEME)를 우회했다고 바로 안심하는 것 — 여러 겹의 체크가 동시에 걸려 있는 경우가 흔하다.

## 막혔을 때 다음 체크
- attach-time 좁은 상황이 아니라 실행 도중 임의 시점에 죽는 폭넓은 상황까지 전체 체크리스트가 필요하다면 → REV-0240 디버거에서 갑자기 종료될 때 체크리스트.
- x64dbg에서 구체적으로 anti-attach 패턴과 대응법이 궁금하다면 → REV-0583 x64dbg로 붙였는데 바로 종료(anti-attach)될 때.
- Linux에서 attach 자체가 permission denied로 막힌다면(이건 "종료"가 아니라 "attach 실패") → REV-0692 GDB attach가 permission denied로 실패할 때(ptrace_scope).
- `ptrace(PTRACE_TRACEME)` 안티디버깅의 구체적인 우회 절차가 필요하다면 → REV-0234 ptrace PTRACE_TRACEME 안티디버깅.

## 미니 예제
```bash
$ ./chall
Usage: ./chall <password>
$ echo $?
1
```
```gdb
$ gdb -q ./chall
(gdb) run
Starting program: /path/chall
Usage: ./chall <password>
[Inferior 1 (process 5821) exited with code 01]
```
두 실행의 종료 코드가 똑같이 `1`이었다. 안티디버깅이 아니라 단순히 인자를 안 넘겨서 프로그램이 사용법만 출력하고 종료된 것이었다. `(gdb) run testpass123`으로 인자를 넘기자 정상적으로 `check_password`까지 진입했다.

## 관련 글
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트
- REV-0583 — x64dbg로 붙였는데 바로 종료(anti-attach)될 때
- REV-0692 — GDB attach가 permission denied로 실패할 때(ptrace_scope)
- REV-0234 — ptrace PTRACE_TRACEME 안티디버깅

## 출처/검증
- CRT 초기화 코드 및 TLS 콜백이 `main()`보다 먼저 실행되는 순서: Microsoft 공식 문서(C Run-Time, TLS Callback) 및 System V ABI 프로그램 시작 순서 기준.
- `ptrace(PTRACE_TRACEME)` 자가 트레이싱과 이미 트레이싱 중인 프로세스에서의 실패(EPERM) 동작: Linux `ptrace(2)` man page 기준.
- x64dbg System Breakpoint 및 예외 전달(Pass exception) 설정: x64dbg 공식 문서(Exceptions, Options) 기준 (2026-09-09 검증).
