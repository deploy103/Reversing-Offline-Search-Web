---
id: REV-0577
title: "Windows 콘솔 입출력 함수(ReadConsole/WriteConsole) 추적하기"
slug: "rev-0577-console-io-readconsole-writeconsole"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["ReadConsoleW", "WriteConsoleW", "GetStdHandle", "콘솔 입출력", "STD_INPUT_HANDLE", "conhost.exe"]
aliases: ["콘솔 입출력 함수 추적", "ReadConsole WriteConsole 분석", "콘솔 프로그램 입력값 가로채기"]
symptom_keywords: ["콘솔 프로그램에서 입력값을 어디서 받는지 모르겠다", "ReadConsoleW가 임포트에 있다", "scanf 대신 ReadConsole이 보인다", "콘솔 출력 메시지를 만드는 지점을 찾고 싶다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
콘솔(cmd/터미널) 기반 크랙미는 CRT의 `scanf`/`printf` 대신, 또는 그 내부 구현으로 `ReadConsoleW`/`WriteConsoleW`를 직접 호출하는 경우가 많으므로 이 두 함수의 인자 순서를 알아두면 사용자가 입력한 값이 처음 어디에 저장되는지, 그리고 "Correct"/"Wrong" 같은 결과 메시지가 어디서 만들어지는지를 임포트 하나로 바로 찾아낼 수 있다.

## 언제 검색해야 하나
- IDA Imports 탭에 `ReadConsoleW`/`ReadConsoleA` 또는 `WriteConsoleW`/`WriteConsoleA`가 보일 때
- 콘솔 창에 입력한 플래그/비밀번호 문자열이 메모리 어디에 저장되는지 x64dbg로 가로채고 싶을 때
- "Correct!"나 "Wrong password" 같은 결과 문자열이 출력되는 지점(=검증 로직이 끝나는 지점)을 거꾸로 추적해서 검증 함수 시작점을 찾고 싶을 때
- `scanf`/`printf`로 검색했는데 임포트에 없어서 당황했을 때(정적 링크된 CRT가 내부적으로 이 함수들을 호출하는 경우가 많다)

## 핵심 개념
콘솔 입출력은 파일 입출력과 다른 전용 API를 쓴다. Windows는 콘솔 창을 일반 파일과 다른 특수 장치 객체로 취급하기 때문에, 콘솔 핸들에 대해서는 `ReadFile`/`WriteFile` 대신 `ReadConsole`/`WriteConsole`을 쓰는 것이 원칙이다(실제로는 `ReadFile`을 콘솔 핸들에 써도 내부적으로 유사하게 동작하지만, 콘솔 전용 기능—커서 위치, 라인 편집, 컨트롤 문자 처리 등—을 쓰려면 `ReadConsole`/`WriteConsole`이 필요하다).

**`GetStdHandle`** — 표준 입출력 핸들을 얻는다. 콘솔 입출력을 하려면 먼저 이 핸들이 필요하다.
```c
HANDLE GetStdHandle(DWORD nStdHandle);
// nStdHandle: STD_INPUT_HANDLE(-10), STD_OUTPUT_HANDLE(-11), STD_ERROR_HANDLE(-12)
```

**`ReadConsoleW`** — 콘솔 입력 버퍼에서 키보드 입력을 읽어온다.
```c
BOOL WINAPI ReadConsoleW(
    HANDLE  hConsoleInput,        // 1. GetStdHandle(STD_INPUT_HANDLE)로 얻은 핸들, GENERIC_READ 권한 필요
    LPVOID  lpBuffer,             // 2. 읽은 문자를 저장할 버퍼(UTF-16)
    DWORD   nNumberOfCharsToRead, // 3. 읽을 문자 개수(바이트가 아니라 문자 단위, 버퍼는 최소 이 값*sizeof(WCHAR) 이상이어야 함)
    LPDWORD lpNumberOfCharsRead,  // 4. 실제로 읽은 문자 개수가 저장될 주소
    LPVOID  pInputControl         // 5. CONSOLE_READCONSOLE_CONTROL 구조체 포인터(대개 NULL)
);
```

**`WriteConsoleW`** — 콘솔 화면 버퍼(현재 커서 위치)에 문자를 출력한다.
```c
BOOL WINAPI WriteConsoleW(
    HANDLE      hConsoleOutput,        // 1. GetStdHandle(STD_OUTPUT_HANDLE)로 얻은 핸들
    const VOID  *lpBuffer,             // 2. 출력할 문자열이 담긴 버퍼(UTF-16)
    DWORD       nNumberOfCharsToWrite, // 3. 출력할 문자 개수
    LPDWORD     lpNumberOfCharsWritten,// 4. 실제로 출력된 문자 개수(NULL 가능)
    LPVOID      lpReserved             // 5. 예약됨, 반드시 NULL
);
```

두 함수 모두 `BOOL`을 반환하며(성공 시 0이 아님), `ReadConsole`/`WriteConsole`은 내부적으로 `conhost.exe`(또는 Windows Terminal의 호스트 프로세스)와 ALPC(비동기 로컬 프로시저 호출)로 통신해 실제 화면을 그리지만, 이 통신은 사용자 프로세스 내부의 API 호출(`ReadConsoleW`/`WriteConsoleW` 진입점)을 거친 뒤에 일어나므로 x64dbg에서 이 API에 브레이크포인트를 걸면 문제없이 데이터를 가로챌 수 있다.

## 화면/코드에서 보이는 징후
- `GetStdHandle(-10)` 또는 `GetStdHandle(-11)` 호출 뒤 반환값(콘솔 핸들)이 `ReadConsoleW`/`WriteConsoleW`의 첫 인자로 그대로 쓰임
- 프로그램 시작 직후 여러 차례 `WriteConsoleW` 호출(메뉴/안내 문구 출력)이 나온 뒤 `ReadConsoleW` 한 번(사용자 입력 대기), 그다음 검증 로직, 마지막에 결과에 따라 다른 `WriteConsoleW`(성공/실패 메시지)로 분기하는 전형적인 크랙미 흐름
- `ReadConsoleW`로 읽은 버퍼가 이후 `wcslen`, 문자별 비교 루프, 또는 해시 함수의 입력으로 쓰임
- 최적화되지 않은 디버그 빌드에서는 CRT의 `scanf`/`gets` 대신 컴파일러가 자동으로 `ReadFile`/`ReadConsole` 계열을 감싸는 내부 함수(`_read_console` 등 언더스코어 접두 CRT 내부 함수)를 거치는 경우도 있어, 임포트에 `ReadConsoleW`만 보이고 `scanf`가 안 보이는 이유가 된다

## 가장 먼저 할 것
IDA Imports 탭에서 `ReadConsoleW`(또는 `A`)를 찾아 교차 참조(`X`)로 호출 위치를 확인하고, 그 호출 지점 바로 위에서 두 번째 인자(`lpBuffer`)로 쓰인 변수/버퍼 주소를 먼저 적어둔다. 이 버퍼가 이후 검증 로직 전체의 입력값이 된다.

## 단계별 절차
**1) 정적 분석(IDA)**
- `ReadConsoleW` 교차 참조를 따라가 호출부를 연다. `F5` 디컴파일로 보면 `ReadConsoleW(hStdin, buf, 0x100, &charsRead, 0)` 형태로 나온다.
- `buf` 변수의 이후 사용처를 데이터 흐름으로 추적(변수 더블클릭 후 `X`)해서 검증 함수로 이어지는지 확인한다.
- 결과 출력 쪽은 `WriteConsoleW`를 검색해 성공/실패 각각의 호출 지점을 찾고, 그 직전의 조건 분기(`jz`/`jnz`)를 확인해 검증 함수의 반환값이 어떻게 갈리는지 파악한다.

**2) 동적 분석(x64dbg) — 입력값 가로채기**
- `bp ReadConsoleW`로 브레이크포인트를 걸고 실행한다. 프로그램이 입력을 요구하는 시점에 브레이크포인트가 걸린다.
- x64에서는 `RDX`(2번째 인자, `lpBuffer`)를 우클릭 → "Follow in Dump"해서 버퍼 주소를 미리 확보해둔다.
- `F9`(계속 실행)를 눌러 함수가 리턴할 때까지 실행한 뒤(또는 `ReadConsoleW` 반환 지점에 임시 브레이크포인트), 아까 확보한 버퍼 주소를 다시 덤프 창에서 확인하면 사용자가 입력한 문자열이 UTF-16으로 채워져 있다.

**3) 동적 분석(x64dbg) — 검증 결과 지점 거꾸로 추적**
- `bp WriteConsoleW`로 브레이크포인트를 걸고 실행/입력한다.
- 여러 번 걸릴 수 있으므로(메뉴 출력 등) 매번 `RDX`(2번째 인자, 출력할 문자열 버퍼)를 확인해 "Correct"나 "Wrong" 관련 메시지가 나오는 순간을 찾는다.
- 그 순간의 콜스택(Call Stack 창, `Alt+K`)을 보면 어떤 함수가 이 메시지를 출력했는지, 즉 검증 함수의 정확한 위치를 알 수 있다.

## 명령어/단축키
- x64dbg: `bp ReadConsoleW`, `bp WriteConsoleW`, `Alt+K`(Call Stack 창), 레지스터/인자 우클릭 → "Follow in Dump"
- IDA: `X`(교차 참조), `F5`(디컴파일), `Shift+F12`(Strings 창으로 "Correct"/"Wrong" 같은 결과 문구 먼저 찾기)

## 출력 해석
- `ReadConsoleW`의 4번째 인자(`lpNumberOfCharsRead`)가 가리키는 값은 줄바꿈 문자(엔터, `\r\n`으로 처리됨)까지 포함한 실제 입력 문자 개수다. 사용자가 입력한 문자열의 진짜 길이를 구하려면 이 값에서 개행 문자 수를 빼야 하는 경우가 많다.
- `WriteConsoleW`가 여러 번 호출된다면 각 호출은 화면에 그려지는 "한 줄" 단위가 아니라 프로그램이 원하는 임의의 문자열 단위이므로, 여러 조각이 이어져 하나의 메시지를 이룰 수 있다(예: `"Result: "` 출력 후 별도 호출로 `"Correct"` 출력).
- `GetStdHandle`이 `INVALID_HANDLE_VALUE`를 반환하면 콘솔이 없는 환경(예: GUI 서브시스템으로 실행되었거나 표준 입출력이 리다이렉트된 상태)이라는 뜻이며, 이 경우 `ReadConsole`/`WriteConsole`은 실패한다(리다이렉트된 파일/파이프 핸들에는 `ReadFile`/`WriteFile`을 써야 한다).

## 흔한 실수
- `ReadConsoleW`가 읽어온 버퍼를 UTF-16(2바이트 단위)이 아니라 ASCII(1바이트 단위)로 착각해서 덤프를 잘못 해석하는 것 — x64dbg 덤프 창에서 "UTF-16" 표시 옵션을 켜야 문자열이 제대로 보인다.
- `WriteConsoleW`가 여러 번 호출되는 것을 보고 첫 호출만 확인한 뒤 "출력 메시지가 없다"고 오판하는 것 — 실제 결과 메시지는 몇 번째 호출인지 순서대로 다 확인해야 한다.
- `ReadFile`을 표준 입력 핸들에 대해 검색해서 못 찾고, `ReadConsole` 계열이 있다는 걸 몰라 CRT 함수만 찾다가 시간을 낭비하는 것.
- 리다이렉션(`prog.exe < input.txt`)으로 실행하면 `ReadConsoleW`가 아예 실패하거나 다르게 동작할 수 있다는 점을 모르고, 자동화 스크립트에서 입력 파이프만 걸어놓고 왜 안 되는지 헤매는 것 — 이 경우 파이프/리다이렉트된 핸들은 `ReadFile` 경로로 처리되므로 애초에 `ReadConsole` 브레이크포인트가 걸리지 않는다.

## 막혔을 때 다음 체크
- 입력값이 파일에서 오는 것 같다면 → REV-0139(CreateFile ReadFile WriteFile 입력 데이터 추적) 참고
- 입력값 검증에 키 입력 폴링(엔터를 누르지 않는 실시간 입력 검사)이 섞여 있다면 → REV-0578(GetAsyncKeyState로 키 입력을 검증에 쓰는 패턴) 참고
- 콘솔이 아니라 GUI 서브시스템인데 콘솔 함수가 안 보인다면 → REV-0564(콘솔 프로그램과 GUI 프로그램 서브시스템 차이) 참고

## 미니 예제
x64dbg에서 `bp ReadConsoleW` 후 실행하고 `flag_test`라고 입력했다고 하자. 브레이크포인트가 걸린 시점에 `RDX`(lpBuffer)를 Follow in Dump하면:

```text
0000027A1B2A5010  66 00 6C 00 61 00 67 00  5F 00 74 00 65 00 73 00   f.l.a.g._.t.e.s.
0000027A1B2A5020  74 00 0D 00 0A 00 00 00  ...                        t.......
```

각 문자가 2바이트(UTF-16LE)로 저장되어 있고, 끝에 `0D 00 0A 00`(`\r\n`)이 붙은 것을 볼 수 있다. `lpNumberOfCharsRead`가 가리키는 값은 11(`flag_test` 9글자 + `\r\n` 2글자)이 된다. 이후 검증 함수가 이 개행 문자를 제대로 잘라내지 않고 비교한다면 항상 실패하는 버그가 될 수도 있으므로, 검증 로직에서 길이를 어떻게 계산하는지도 함께 확인해야 한다.

## 관련 글
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적
- REV-0578 — GetAsyncKeyState로 키 입력을 검증에 쓰는 패턴
- REV-0564 — 콘솔 프로그램과 GUI 프로그램 서브시스템 차이
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기

## 출처/검증
- `ReadConsoleW`/`WriteConsoleW`/`GetStdHandle`의 함수 시그니처, 인자 의미, 반환값은 Microsoft Windows Console API 공식 문서(learn.microsoft.com/windows/console/readconsole, /writeconsole) 기준이다.
- `conhost.exe`를 통한 콘솔 I/O의 ALPC 기반 동작 방식은 일반적으로 알려진 Windows 콘솔 서브시스템 구조에 대한 서술이며, 개별 브레이크포인트 동작에는 영향을 주지 않는다.
- 위 미니 예제의 메모리 덤프 값은 설명을 위해 구성한 예시다(2026-09-08 기준 서술).
