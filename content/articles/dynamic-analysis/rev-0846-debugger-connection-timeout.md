---
id: REV-0846
title: "디버거 연결 중 타임아웃/응답없음이 뜰 때"
slug: "rev-0846-debugger-connection-timeout"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords: ["attach 응답없음", "디버거 타임아웃", "Waiting for debuggee", "ptrace 좀비 프로세스", "gdbserver 연결 실패"]
aliases: ["디버거가 멈춰서 안 붙음", "attach 창이 계속 도는 중", "gdb가 응답이 없음"]
symptom_keywords: ["attach 버튼을 눌렀는데 창이 계속 로딩중임", "gdb -p PID 했는데 그대로 멈춰 있음", "attach 다이얼로그가 응답없음 상태가 됨", "gdbserver 연결이 몇 초째 그대로임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
"연결 자체"가 멈춰서 응답이 없는 증상은 원격(gdbserver 네트워크) 문제와 로컬(attach/ptrace 자체가 안 끝남) 문제를 먼저 구분해야 하며, 로컬이라면 백신/EDR의 디버거 실시간 검사, 대상 프로세스가 이미 정지(suspend/그룹스톱) 상태라 디버그 이벤트 자체가 안 오는 경우, 좀비(defunct) 프로세스에 attach를 시도한 경우가 가장 흔한 원인이다.

## 언제 검색해야 하나
- x64dbg의 Attach 대화상자가 "Waiting..." 상태로 몇 초~몇십 초째 응답이 없을 때
- `gdb -p PID`를 쳤는데 프롬프트가 안 돌아오고 그대로 멈춰 있을 때
- 원격/컨테이너의 `gdbserver`에 `target remote`로 붙으려는데 타임아웃이 날 때
- 로컬 프로세스인데도 attach 자체가 몇 분째 완료되지 않을 때

## 핵심 개념

### 먼저 나눠야 할 것 — 네트워크 연결 vs 로컬 attach
`target remote HOST:PORT`처럼 네트워크를 거치는 원격 디버깅의 `Connection timed out`/`Connection refused`/`Remote connection closed`는 TCP 경로, 방화벽, 포트 매핑, gdbserver 생존 여부의 문제이며, 이 시나리오의 원인 분류와 해결 절차는 REV-0847에서 자세히 다룬다. 이 글은 그와 달리 **로컬 프로세스에 대한 attach/ptrace 자체가 완료되지 않고 멈추는** 경우에 집중한다.

### Windows — 보안 소프트웨어의 실시간 검사
일부 백신/EDR은 디버거가 다른 프로세스에 attach하려는 시도(`OpenProcess` + `DebugActiveProcess`)를 의심스러운 행위로 간주해 실시간 검사를 걸며, 이 검사가 몇 초에서 몇십 초까지 attach 자체를 지연시켜 "응답없음"처럼 보이게 만든다. 방화벽/백신이 분석 도구를 차단하거나 지연시키는 일반적인 패턴은 REV-0599에서 다룬다.

### Windows — 대상 프로세스가 이미 정지 상태
Process Explorer 등으로 이미 Suspend된 프로세스, 또는 모든 스레드가 대기 중인 프로세스는 디버거가 attach를 완료하기 위한 디버그 이벤트 자체를 아직 못 받았을 수 있다. 이 경우 attach 자체는 결국 끝나지만 체감상 매우 오래 걸린다.

### Linux — 그룹스톱/좀비 프로세스
대상 프로세스가 이미 `SIGSTOP`으로 그룹스톱된 상태이거나, 부모가 아직 `wait()`하지 않은 좀비(defunct, `Z` 상태) 프로세스라면 `ptrace(PTRACE_ATTACH, ...)`가 정상적으로 끝나지 않거나 attach 후 아무 이벤트도 오지 않아 GDB 프롬프트가 계속 멈춘 것처럼 보인다. `ps aux`에서 상태 컬럼(`STAT`)이 `T`(stopped) 또는 `Z`(zombie)인지 먼저 확인해야 한다.

### Linux — 이미 다른 tracer가 소켓/PID를 붙잡고 있음
비정상 종료한 이전 GDB 세션이 여전히 tracer로 남아 있으면, 새 GDB의 attach 요청은 명확한 에러 없이 대기 상태로 오래 걸리는 경우가 있다. `ps`로 기존 tracer 프로세스를 찾아 정리해야 한다.

## 화면/코드에서 보이는 징후
```
$ gdb -p 4821
Attaching to process 4821
```
위 상태에서 프롬프트가 몇십 초째 안 돌아옴. Windows에서는 x64dbg Attach 대화상자의 진행바/스피너가 멈춘 것처럼 보이거나, 작업 관리자에서 x64dbg의 CPU 사용률이 순간적으로 튀며 백신 프로세스(`MsMpEng.exe` 등)의 CPU 사용률도 함께 올라간다.

## 가장 먼저 할 것
로컬인지 원격인지부터 구분한다. `target remote`/네트워크 주소가 개입되어 있다면 REV-0847로 넘어간다. 로컬이라면 `ps aux`(Linux)로 대상 프로세스의 `STAT` 컬럼, 또는 작업 관리자(Windows)에서 대상/백신 프로세스의 CPU·응답 상태부터 확인한다.

## 단계별 절차
1. Linux: `ps aux | grep 대상`으로 `STAT`이 `T`/`Z`가 아닌지 확인한다. `T`라면 `kill -CONT PID`로 재개시킨 뒤 다시 attach한다. `Z`라면 그 부모 프로세스를 찾아 종료/정리한다.
2. Linux: `ps aux | grep gdb`로 좀비 tracer가 남아 있는지 확인하고 있으면 정리한다.
3. Windows: 작업 관리자에서 백신/EDR 프로세스의 CPU 사용률이 attach 시도와 함께 튀는지 관찰한다. 튄다면 분석 대상 폴더를 백신 예외 목록에 추가한 뒤 재시도한다(REV-0599).
4. Windows: Process Explorer로 대상 프로세스의 스레드가 이미 Suspend 상태인지 확인한다.
5. 충분히 기다려도 끝나지 않으면(수 분 이상) attach를 취소하고 대상 프로세스를 재시작한 뒤, 시작 시점부터 디버거로 직접 실행(attach 대신 처음부터 F9/`run`)하는 방식으로 바꿔본다.

## 명령어/단축키
```bash
ps aux | grep 대상
ps aux | grep gdb
kill -CONT PID
```
```text
Windows: 작업 관리자 → 세부 정보 → CPU 컬럼으로 백신 프로세스 확인
Process Explorer: 프로세스 트리에서 Suspend 상태 확인
```

## 출력 해석
`ps aux`의 `STAT` 컬럼이 `T`면 그룹스톱, `Z`면 좀비다. 둘 다 정상적인 attach 완료를 막는 상태다. 백신 프로세스의 CPU 사용률이 attach 타이밍과 정확히 맞물려 튄다면 실시간 검사가 지연의 원인이라는 강한 신호다.

## 흔한 실수
- 원격 gdbserver 연결 문제와 로컬 attach 지연 문제를 구분하지 않고 같은 해결책(방화벽 확인 등)만 반복하는 것.
- 대상 프로세스의 `STAT`(Linux)이나 Suspend 상태(Windows)를 확인하지 않고 무작정 디버거를 재시작하는 것.
- 좀비 tracer 프로세스가 남아 있는 것을 모르고 계속 새 GDB 세션으로 재시도하는 것.
- 백신 예외 목록에 추가하지 않고 매번 실시간 검사 지연을 그대로 감수하는 것.

## 막혔을 때 다음 체크
- 원격/gdbserver 네트워크 연결 자체가 문제라면 → REV-0847 원격 디버깅(gdbserver) 연결이 안 될 때
- 방화벽/백신이 분석 도구를 아예 차단한다면 → REV-0599 방화벽/백신이 분석 도구를 차단할 때
- attach 자체가 권한 문제로 실패한다면(타임아웃이 아니라 즉시 거부) → REV-0838 디버거가 프로세스에 attach가 안 될 때

## 미니 예제
`gdb -p 4821`을 실행했는데 5분째 프롬프트가 안 돌아왔다. 다른 터미널에서 `ps aux | grep 4821`을 확인하니 `STAT` 컬럼이 `T`였다. `kill -CONT 4821`로 재개시킨 뒤 GDB를 다시 attach하자 즉시 완료됐다.

## 관련 글
- REV-0847 — 원격 디버깅(gdbserver) 연결이 안 될 때
- REV-0599 — 방화벽/백신이 분석 도구를 차단할 때
- REV-0838 — 디버거가 프로세스에 attach가 안 될 때

## 출처/검증
- Linux 프로세스 상태(`STAT` 컬럼: `T` 정지, `Z` 좀비)와 `ptrace` attach 동작: `ps(1)`, `ptrace(2)` man page 기준.
- Windows 보안 소프트웨어의 프로세스 attach 관련 실시간 검사 지연은 일반적으로 알려진 EDR/백신 동작 패턴 기준(2026-09-09 검증).
