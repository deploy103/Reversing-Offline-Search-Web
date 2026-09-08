---
id: REV-0580
title: "명명된 파이프(Named Pipe)를 이용한 IPC 분석 기초"
slug: "rev-0580-named-pipe-ipc-basics"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CreateNamedPipeW", "ConnectNamedPipe", "명명된 파이프", "IPC", "\\\\.\\pipe", "Process Monitor"]
aliases: ["Named Pipe 분석", "명명된 파이프 IPC", "파이프 기반 프로세스 간 통신 분석"]
symptom_keywords: ["CreateNamedPipeW가 임포트에 있다", "\\\\.\\pipe\\ 문자열이 보인다", "여러 프로세스가 통신하는 크랙미", "ConnectNamedPipe 호출을 찾았다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
명명된 파이프(Named Pipe)는 `\\.\pipe\<이름>` 형식의 고유한 이름으로 서버와 클라이언트 프로세스가 서로 다른 실행 파일이더라도 `ReadFile`/`WriteFile`과 동일한 방식으로 데이터를 주고받을 수 있게 해주는 IPC(프로세스 간 통신) 수단이므로, 문자열에서 파이프 이름을 먼저 찾고 Process Monitor로 실제 파이프 입출력을 관찰하면 검증 로직이 다른 프로세스(또는 서비스)에 나뉘어 있는 크랙미를 놓치지 않고 분석할 수 있다.

## 언제 검색해야 하나
- Strings나 IDA에서 `\\.\pipe\` 로 시작하는 문자열을 발견했을 때
- 임포트에 `CreateNamedPipeW`, `ConnectNamedPipe`, `CallNamedPipeW`, `WaitNamedPipeW` 중 하나라도 있을 때
- 실행 파일 하나만 분석했는데 플래그 검증 로직이 안 보이고, 프로그램이 다른 프로세스를 `CreateProcess`로 실행하는 코드가 보일 때(그 프로세스가 파이프 서버/클라이언트일 가능성)
- Process Monitor(ProcMon)로 관찰했을 때 `\Device\NamedPipe\...` 경로에 대한 `CreateFile`/`ReadFile`/`WriteFile` 이벤트가 보일 때

## 핵심 개념
명명된 파이프는 커널 객체로, 파일 시스템 이름공간의 특수한 위치(`\\.\pipe\`)에 만들어지는 가상의 "파일"이다. 서버가 파이프를 만들고 클라이언트가 그 이름으로 연결하면, 이후에는 일반 파일 핸들처럼 `ReadFile`/`WriteFile`로 데이터를 주고받을 수 있다.

**서버 측 — `CreateNamedPipeW`**
```c
HANDLE CreateNamedPipeW(
    LPCWSTR               lpName,               // 1. "\\.\pipe\이름" 형식(최대 256자)
    DWORD                  dwOpenMode,           // 2. PIPE_ACCESS_DUPLEX/INBOUND/OUTBOUND, FILE_FLAG_OVERLAPPED 등
    DWORD                  dwPipeMode,           // 3. PIPE_TYPE_BYTE|MESSAGE, PIPE_READMODE_BYTE|MESSAGE, PIPE_WAIT|NOWAIT
    DWORD                  nMaxInstances,        // 4. 동시에 만들 수 있는 파이프 인스턴스 최대 개수
    DWORD                  nOutBufferSize,       // 5. 출력 버퍼 힌트 크기(바이트)
    DWORD                  nInBufferSize,        // 6. 입력 버퍼 힌트 크기(바이트)
    DWORD                  nDefaultTimeOut,      // 7. WaitNamedPipe 기본 타임아웃(ms), 0이면 기본 50ms
    LPSECURITY_ATTRIBUTES  lpSecurityAttributes  // 8. 보안 속성(대개 NULL)
);
```
서버는 `CreateNamedPipeW`로 파이프를 만든 뒤 `ConnectNamedPipe(hPipe, lpOverlapped)`를 호출해 클라이언트의 연결을 기다린다.

**클라이언트 측**
클라이언트는 별도 API 없이 그냥 `CreateFileW(L"\\\\.\\pipe\\이름", GENERIC_READ|GENERIC_WRITE, ...)`로 연결한다(REV-0139의 `CreateFileW`와 동일한 함수, 경로만 파이프 이름공간). 연결 후에는 서버와 클라이언트 모두 `ReadFile`/`WriteFile`로 데이터를 주고받는다. 간단한 요청-응답 한 번만 필요하다면 `CallNamedPipeW` 하나로 연결-쓰기-읽기-종료를 한 번에 처리할 수도 있다.

**이름 규칙**: 로컬 파이프는 `\\.\pipe\PipeName`, 원격(같은 도메인의 다른 컴퓨터) 파이프는 `\\ServerName\pipe\PipeName` 형식을 쓴다. 이름은 백슬래시를 제외한 어떤 문자든 가능하고 대소문자를 구분하지 않는다.

**다른 IPC 수단과의 비교**: Windows에는 명명된 파이프 외에도 공유 메모리(`CreateFileMappingW`/`MapViewOfFile`), 소켓(로컬호스트 TCP), 메일슬롯(mailslot), 클립보드(REV-0579), COM/RPC 등 다양한 IPC 수단이 있다. 이 중 명명된 파이프가 크랙미/멀티 프로세스 챌린지에서 특히 자주 쓰이는 이유는 (1) `ReadFile`/`WriteFile`이라는 이미 익숙한 API로 그대로 다룰 수 있어 구현이 간단하고, (2) 양방향(duplex) 통신과 메시지 경계 유지(`PIPE_TYPE_MESSAGE`)를 기본으로 지원하며, (3) 소켓과 달리 방화벽이나 포트 충돌 문제 없이 동작하기 때문이다. 따라서 문자열에서 포트 번호(`127.0.0.1:####`)가 안 보이는데 프로세스 간 통신이 의심된다면 소켓보다 명명된 파이프를 먼저 의심해보는 것이 합리적이다.

## 화면/코드에서 보이는 징후
- `.rdata`나 `.data` 섹션 문자열 중 `\\.\pipe\...` 형태가 있고, 이 문자열이 `CreateNamedPipeW`(서버) 또는 `CreateFileW`(클라이언트)의 첫 인자로 쓰임
- `CreateNamedPipeW` 호출 뒤 `ConnectNamedPipe`가 이어지고, 그 뒤에 `ReadFile`/`WriteFile` 루프가 반복되는 서버 패턴
- 메인 실행 파일이 `CreateProcessW`로 두 번째 실행 파일이나 자기 자신을 다른 인자로 실행시킨 뒤, 두 프로세스가 같은 파이프 이름 문자열을 공유하는 구조 — 이 경우 플래그 검증의 "정답 비교" 부분이 두 번째 프로세스(또는 서비스 실행 파일)에 있을 수 있다
- 파이프 이름 문자열이 난독화되어 있거나(개별 문자로 조합) 실행 시점에 동적으로 생성되는 경우도 있으므로, 문자열 검색만으로 못 찾으면 임포트 기반 브레이크포인트가 더 확실하다

## 가장 먼저 할 것
Strings 검색으로 `\\.\pipe\`를 먼저 찾는다. 문자열이 바로 안 보이면 IDA Imports에서 `CreateNamedPipeW`를 찾아 `X`로 호출부를 확인하고 첫 인자를 역추적한다. 파이프 이름을 확보했다면, 이 이름으로 통신하는 다른 프로세스(별도 실행 파일, 서비스, 또는 같은 파일의 자식 프로세스)가 있는지부터 확인한다.

## 단계별 절차
**1) 정적 분석(IDA)**
- `CreateNamedPipeW`/`CreateFileW` 교차 참조로 파이프 이름 문자열을 확보한다.
- 같은 디렉터리나 리소스 섹션에 두 번째 실행 파일이 내장되어 있는지(REV-0141 참고) 확인한다 — 파이프 서버가 별도 바이너리로 존재하는 경우가 흔하다.
- `CreateProcessW`/`ShellExecuteW` 호출이 있다면 어떤 파일을 실행하는지 확인해 분석 대상을 넓힌다.

**2) 동적 분석 — Process Monitor로 전체 흐름 관찰**
- Sysinternals Process Monitor(ProcMon)를 실행하고, Filter에 `Path contains pipe`를 추가해 노이즈를 줄인다.
- 대상 프로그램을 실행하면 `\Device\NamedPipe\<이름>`에 대한 `CreateFile`(연결), `ReadFile`, `WriteFile`, `CloseFile` 이벤트가 시간 순서대로 나열되는 것을 볼 수 있다. 어느 프로세스(PID)가 어느 순서로 읽고 쓰는지 한눈에 파악할 수 있어, 여러 프로세스가 얽힌 구조를 분석할 때 x64dbg보다 먼저 시도할 가치가 있다.

**3) 동적 분석 — x64dbg로 실제 데이터 가로채기**
- 서버 프로세스에는 `bp ReadFile`, 클라이언트 프로세스에는 `bp WriteFile`(또는 그 반대)을 걸어 실제로 파이프를 통해 오가는 바이트를 확인한다. 인자 규칙은 REV-0139와 동일하다(x64: `RCX`=hFile, `RDX`=버퍼, `R8`=바이트 수).
- 두 프로세스를 동시에 디버깅해야 하므로, x64dbg 인스턴스를 두 개 띄우거나 한쪽은 ProcMon으로 개략적 흐름만 보고 다른 쪽만 정밀 디버깅하는 전략이 효율적이다.

## 명령어/단축키
- ProcMon: Filter 추가(`Path` `contains` `pipe`), `Ctrl+E`(캡처 시작/중지), `Ctrl+L`(필터 창)
- x64dbg: `bp CreateNamedPipeW`, `bp ConnectNamedPipe`, `bp ReadFile`, `bp WriteFile`
- IDA: `Shift+F12`(Strings), `X`(교차 참조)
- 수동 확인: WinObj(Sysinternals)로 `\Device\NamedPipe` 아래 활성 파이프 목록 조회 가능

## 출력 해석
- `CreateNamedPipeW`가 `INVALID_HANDLE_VALUE`를 반환하면 파이프 생성 실패(이름 중복, 권한 문제 등)이며 `GetLastError`로 원인을 추가 확인해야 한다.
- `ConnectNamedPipe`가 실패하고 `GetLastError()`가 `ERROR_PIPE_CONNECTED`(535)면 이미 클라이언트가 연결된 상태이므로 이는 정상 처리 경로다(에러가 아님).
- `dwPipeMode`에 `PIPE_TYPE_MESSAGE`가 설정되어 있으면 데이터가 메시지 단위로 전달되며, `ReadFile` 한 번에 메시지 하나가 정확히 대응된다. `PIPE_TYPE_BYTE`면 스트림처럼 이어져서 여러 번의 `WriteFile`이 한 번의 `ReadFile`로 합쳐져 읽힐 수 있다.

## 흔한 실수
- 눈에 보이는 실행 파일 하나만 계속 정적 분석하면서 "검증 로직이 없다"고 결론 내리는 것 — 실제 비교 로직이 파이프로 연결된 다른 프로세스(서비스, 자식 프로세스)에 있을 수 있으므로 `CreateProcessW` 호출과 파이프 이름을 반드시 함께 확인해야 한다.
- 서버가 `ConnectNamedPipe` 완료를 기다리지 않고 바로 `ReadFile`을 호출해서 타이밍 문제로 분석 중 프로그램이 멈춘 것을 버그로 오인하는 것 — 실제 프로그램 설계상 정상일 수 있으니 먼저 정상 실행(디버거 없이)에서의 동작을 기준으로 삼는다.
- 파이프 이름에 특수문자나 GUID가 포함되어 실행마다 이름이 바뀌는 경우, 이전 실행에서 확인한 이름으로 다시 연결을 시도해 실패하는 것 — 매 실행마다 ProcMon으로 이름을 새로 확인해야 한다.
- x64dbg로 서버/클라이언트 두 프로세스를 동시에 브레이크포인트 걸어두고 한쪽만 계속 실행(F9)해서 서로 데드락처럼 보이는 상황을 만드는 것 — 두 프로세스를 교대로 진행시켜야 한다.

## 막혔을 때 다음 체크
- 파이프 대신 클립보드로 데이터를 주고받는 것 같다면 → REV-0579(Windows 클립보드를 이용한 데이터 전달 패턴 분석) 참고
- 파이프 데이터가 파일 입출력과 같은 방식으로 다뤄지는 것을 더 자세히 보고 싶다면 → REV-0139(CreateFile ReadFile WriteFile 입력 데이터 추적) 참고
- 서비스 실행 파일이 파이프 서버로 동작하는 구조라면 → REV-0561(서비스(Windows Service) 실행 파일 분석 기초) 참고

## 미니 예제
ProcMon 필터를 `Path contains pipe`로 설정하고 `challenge.exe`를 실행했더니 다음 이벤트가 순서대로 기록되었다고 하자.

```text
1) challenge.exe   CreateFile   \Device\NamedPipe\ctf_check_pipe   SUCCESS
2) checker.exe      CreateFile   \Device\NamedPipe\ctf_check_pipe   SUCCESS   (파이프 서버 측 연결 수락)
3) challenge.exe   WriteFile    \Device\NamedPipe\ctf_check_pipe   Length: 32
4) checker.exe      ReadFile     \Device\NamedPipe\ctf_check_pipe   Length: 32
5) checker.exe      WriteFile    \Device\NamedPipe\ctf_check_pipe   Length: 1
6) challenge.exe   ReadFile     \Device\NamedPipe\ctf_check_pipe   Length: 1
```

이 로그만으로 `challenge.exe`가 입력한 32바이트를 `checker.exe`라는 별도 프로세스로 보내고, 그 결과(1바이트, 성공/실패 플래그로 추정)를 돌려받는 구조라는 것을 알 수 있다. 실제 비교 로직은 `checker.exe`에 있으므로, 이 파일을 IDA로 별도 로드해 분석을 이어가야 한다.

## 관련 글
- REV-0579 — Windows 클립보드를 이용한 데이터 전달 패턴 분석
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적
- REV-0561 — 서비스(Windows Service) 실행 파일 분석 기초

## 출처/검증
- `CreateNamedPipeW`, `ConnectNamedPipe`, `CallNamedPipeW`, 파이프 이름 규칙(`\\.\pipe\`), `dwPipeMode`/`dwOpenMode` 플래그 의미는 Microsoft Win32 API 공식 문서(namedpipeapi.h, Named Pipes) 기준이다.
- `ERROR_PIPE_CONNECTED`(535) 처리와 `ConnectNamedPipe` 관련 동작은 동일 공식 문서의 Remarks를 근거로 한다.
- Process Monitor의 파이프 이벤트 표시 방식(`\Device\NamedPipe\...` 경로)은 Sysinternals Process Monitor의 일반적인 사용 경험을 기준으로 서술했다.
- 위 미니 예제 로그는 설명을 위해 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
