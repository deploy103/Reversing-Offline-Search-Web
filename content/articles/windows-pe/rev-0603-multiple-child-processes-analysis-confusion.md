---
id: REV-0603
title: "프로세스가 여러 개 자식 프로세스를 만들어 분석이 꼬일 때"
slug: "rev-0603-multiple-child-processes-analysis-confusion"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords:
  - CreateProcess 자식 프로세스
  - Image File Execution Options
  - IFEO Debugger 키
  - Process Monitor Process Tree
  - 자기 자신 재실행 패턴
  - UAC 재실행 분석
aliases:
  - 자식 프로세스에 브레이크포인트가 안 걸림
  - CreateProcess로 자기 자신을 다시 실행함
  - 진짜 로직이 다른 프로세스에 있음
  - IFEO 디버거 자동 attach
symptom_keywords:
  - 디버거로 붙였는데 아무것도 안 걸림
  - 프로세스가 계속 자식을 만들고 사라짐
  - 플래그 체크가 다른 프로세스에서 일어남
  - Process Monitor에 CreateProcess 여러 번 보임
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
디버거로 붙인 프로세스에는 정작 아무 의미 있는 로직이 없고, 실제 검증/처리는 그 프로세스가 만드는 자식 프로세스(때로는 자기 자신을 다른 인자로 재실행)에서 일어난다면, 일반 디버거는 기본적으로 자식 프로세스를 자동으로 따라가지 않으므로 Process Monitor로 프로세스 트리를 먼저 파악하고 Image File Execution Options(IFEO) 레지스트리 키로 자식이 생성되는 순간 자동으로 디버거가 붙도록 만들어야 한다.

## 언제 검색해야 하나
- x64dbg로 처음 실행 파일을 열고 여러 브레이크포인트를 걸었는데 하나도 안 걸리고 프로그램이 그냥 끝나버릴 때
- Process Explorer나 작업 관리자에 순간적으로 여러 개의 프로세스가 나타났다 사라지는 것이 보일 때
- 대상 프로그램이 `cmd.exe`나 자기 자신을 다른 인자로 다시 실행하는 것 같은데, 그 자식 프로세스 안에서 무슨 일이 일어나는지 확인해야 할 때
- UAC 상승이나 권한 재실행 때문에 분석 중이던 프로세스가 다른 프로세스로 바뀌어 버릴 때

## 가장 먼저 할 것
디버거를 걸기 전에 Sysinternals Process Monitor(procmon)를 먼저 켜고 `Operation is Process Create`로 필터를 걸어 대상을 실행한다. 이렇게 하면 부모-자식 프로세스 트리 전체와 각 자식의 정확한 커맨드라인 인자를 디버거 없이도 먼저 파악할 수 있다.

## 핵심 개념
많은 크랙미/실전 바이너리는 단일 프로세스로 끝나지 않고 다음과 같은 이유로 자식 프로세스를 만든다.

- **워커/감시자 분리**: 부모 프로세스는 UI만 담당하고, 실제 검증 로직은 별도로 `CreateProcess`한 자식(혹은 자기 자신을 다른 커맨드라인 인자로 재실행)에서 수행한다.
- **자기 자신 재실행**: 프로그램이 시작 시 특정 조건(예: 관리자 권한 여부, 특정 환경변수 유무)을 판단해 `CreateProcessW(NULL, "self.exe --stage2 ...", ...)`처럼 자기 자신을 다른 인자로 다시 실행하고 원래 프로세스는 종료한다. 이 경우 디버거가 붙어 있던 최초 프로세스는 진짜 로직을 실행하지 못한 채 사라져 버린다.
- **셸 명령 위임**: `cmd.exe /c`나 `powershell.exe -Command`로 실제 작업을 셸에 위임하는 패턴.
- **UAC 재실행**: 관리자 권한이 필요한 동작을 하려고 자기 자신을 상승된 권한으로 다시 실행(`ShellExecuteEx`에 `runas` verb)하는 패턴.

일반적인 디버거(x64dbg 포함)는 명시적으로 설정하지 않는 한 자신이 시작한 프로세스가 새로 만드는 자식 프로세스를 자동으로 따라 붙지 않는다. 따라서 부모 프로세스만 계속 들여다보면 "아무것도 안 걸린다"는 증상을 겪게 된다.

이 문제의 표준적인 해결책은 **Image File Execution Options(IFEO)** 레지스트리 메커니즘을 이용하는 것이다. Windows는 프로세스를 새로 생성할 때마다 다음 레지스트리 경로를 확인한다.

```text
HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\<실행파일이름>\
```

여기에 `Debugger`라는 `REG_SZ` 값을 등록해두면, Windows는 그 이름의 실행 파일이 새로 생성될 때마다 원래 실행 파일 대신 지정한 디버거를 먼저 실행하고, 원래 실행 파일 경로를 인자로 넘겨준다. 즉 자식 프로세스가 실제로 첫 명령어를 실행하기도 전에 디버거가 자동으로 붙어서 기다리고 있게 만들 수 있다. 이는 원래 개발자가 "직접 실행할 수 없는 자식 프로세스"(서비스, 다른 프로세스가 띄우는 하위 프로세스)를 디버깅하기 위해 마련된 정식 메커니즘이며, 동시에 악성코드가 지속성(persistence) 확보에 악용하기도 하는 잘 알려진 이중 용도 기법이다.

## 화면/코드에서 보이는 징후
- Process Monitor에서 `Operation = Process Create` 이벤트가 짧은 시간에 여러 번 기록되고, 각 이벤트의 커맨드라인이 조금씩 다르다.
- 디버거로 실행한 최초 프로세스가 몇 초 안에 정상 종료(exit code 0)되어 버리고, 그 직후 새로운 프로세스가 작업 관리자에 나타났다 사라진다.
- IDA에서 `CreateProcessW`/`CreateProcessA`/`ShellExecuteExW` 임포트와 자기 자신의 모듈 경로(`GetModuleFileNameW`)를 조합해 커맨드라인을 만드는 코드가 보인다.

## 단계별 절차
1. Process Monitor로 `Operation is Process Create` 필터를 걸고 대상을 한 번 실행해, 전체 프로세스 트리와 각 자식의 정확한 이미지 이름/커맨드라인을 기록한다.
2. 진짜 로직이 들어 있을 것으로 의심되는 자식 프로세스의 실행 파일 이름(예: `worker.exe`, 또는 자기 자신과 같은 `target.exe`)을 확인한다.
3. 레지스트리 편집기(`regedit`)에서 다음 경로에 그 이미지 이름으로 키를 만든다.
   ```text
   HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\worker.exe
   ```
4. 그 키 안에 `Debugger`(REG_SZ) 값을 만들고, x64dbg 실행 파일 경로를 넣는다. 예: `C:\tools\x64dbg\x64dbg.exe`.
5. 원래 부모 프로세스를 다시 실행한다. 자식 프로세스가 생성되려는 순간 x64dbg가 자동으로 열리며 그 자식 프로세스를 붙잡고 대기한다.
6. 이제부터는 자식 프로세스의 진입점부터 정상적으로 브레이크포인트를 걸고 분석할 수 있다.
7. 분석이 끝나면 반드시 4번에서 만든 레지스트리 키를 삭제해 원래 상태로 되돌린다(남겨두면 이후 해당 이름의 실행 파일이 항상 디버거를 거쳐 실행되므로 시스템 동작에 영향을 준다).

## 명령어/단축키
- Sysinternals Process Monitor: 필터 → `Operation` `is` `Process Create` → `Include`
- `regedit`: `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\<파일명>` → `Debugger`(REG_SZ)
- PowerShell(관리자)로 등록: `New-Item -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\worker.exe" -Force; Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\worker.exe" -Name Debugger -Value "C:\tools\x64dbg\x64dbg.exe"`
- 정리: 같은 경로의 `Debugger` 값과 키를 삭제(`Remove-Item`)

## 출력 해석
- IFEO를 등록한 뒤 자식 프로세스 이름의 프로그램을 실행했을 때 x64dbg가 자동으로 뜨고 커맨드라인 인자란에 원래 인자가 그대로 채워져 있다면 정상적으로 걸린 것이다.
- 자식 프로세스가 콘솔/GUI가 없는 백그라운드 프로세스라면, x64dbg 창은 뜨지만 원래 프로그램의 UI는 아직 나타나지 않은 채(진입점 직전에 멈춘 채) 대기 상태여야 정상이다.

## 흔한 실수
- 부모 프로세스에만 온갖 브레이크포인트를 걸어놓고 왜 하나도 안 걸리는지 계속 원인을 못 찾는 것 — 애초에 그 로직이 자식 프로세스에 있다는 가능성을 먼저 확인해야 한다.
- IFEO의 이미지 이름을 잘못 적는 것(경로 전체가 아니라 파일 이름만 키로 써야 한다. 예: `C:\dir\worker.exe`가 아니라 `worker.exe`).
- 분석이 끝난 뒤 IFEO 레지스트리 키를 지우지 않고 방치해서, 이후 그 이름의 프로그램을 실행할 때마다 의도치 않게 디버거가 뜨는 것.
- 자식 프로세스가 GUI 없이 실행되는 경우, x64dbg가 자동으로 붙었다는 사실 자체를 눈치채지 못하고 "그냥 멈췄다"고 오해하는 것 — 이 경우 작업 관리자에서 x64dbg 프로세스가 새로 떠 있는지 확인해야 한다.

## 막혔을 때 다음 체크
- 자식 프로세스가 애초에 `CreateRemoteThread`로 다른 프로세스에 코드를 심는 방식이라면 → REV-0602를 확인한다.
- IFEO로 붙였는데도 attach 권한 오류가 난다면 → REV-0598(관리자 권한이 없어서 디버깅이 막힐 때)을 확인한다.
- 자식 프로세스가 attach하자마자 바로 종료된다면 안티 디버깅(anti-attach)일 수 있으므로 패킹 카테고리의 디버거 종료 체크리스트를 참고한다.

## 미니 예제
`launcher.exe`를 Process Monitor로 관찰했더니 실행 직후 `worker.exe --check`라는 커맨드라인으로 자식 프로세스를 만들고 곧바로 자신은 종료되는 것이 기록되었다. `HKLM\...\Image File Execution Options\worker.exe`에 `Debugger` = `C:\tools\x64dbg\x64dbg.exe`를 등록한 뒤 `launcher.exe`를 다시 실행하자, `worker.exe`가 생성되려는 순간 x64dbg가 자동으로 열리며 진입점 이전 상태에서 대기했다. 이 시점에 원하는 위치에 브레이크포인트를 걸고 `F9`로 실행을 재개해 실제 검증 로직을 분석할 수 있었다.

## 관련 글
- REV-0602 — CreateRemoteThread로 생성된 코드가 안 보일 때
- REV-0598 — 관리자 권한이 없어서 디버깅이 막힐 때
- REV-0599 — 방화벽/백신이 분석 도구를 차단할 때

## 출처/검증
- Image File Execution Options(IFEO)의 `Debugger` 값을 이용해 프로세스 생성 시점에 자동으로 디버거를 붙이는 메커니즘은 Microsoft 공식 문서(Image File Execution Options) 및 MITRE ATT&CK T1546.012(Event Triggered Execution: Image File Execution Options Injection) 기준이다.
- Sysinternals Process Monitor의 Process Create 필터링 기능은 Microsoft Sysinternals 공식 문서 기준이다.
- 일반 디버거가 자식 프로세스를 기본적으로 자동 추적하지 않는다는 동작은 Windows 디버깅 API(`DebugActiveProcess`, `DEBUG_ONLY_THIS_PROCESS` 플래그) 및 x64dbg의 기본 동작 기준이다.
- 2026-09-08 기준 서술.
