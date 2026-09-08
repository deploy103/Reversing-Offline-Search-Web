---
id: REV-0235
title: "IsDebuggerPresent 우회 개념"
slug: "rev-0235-isdebuggerpresent-bypass-concept"
category: "packing"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, IDA]
keywords:
  - IsDebuggerPresent
  - CheckRemoteDebuggerPresent
  - windows anti-debug
  - 윈도우 안티디버깅
  - PEB BeingDebugged
  - kernel32 디버거 탐지
  - x64dbg TitanHide
  - ScyllaHide
  - 디버거 탐지 API
aliases:
  - IsDebuggerPresent가 뭐임
  - 디버거 탐지 API 우회
  - x64dbg 걸리는 이유
  - 윈도우 크랙미 디버거 탐지
symptom_keywords:
  - x64dbg로 실행하면 프로그램이 다르게 동작함
  - IsDebuggerPresent 함수 호출이 보임
  - 디버거 없이는 되는데 디버거 붙이면 안됨
  - kernel32 IsDebuggerPresent import가 있음
  - 브레이크포인트 걸면 바로 종료됨
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
**이해를 위한 개념 설명**: `IsDebuggerPresent()`는 Windows API 함수로, 현재 프로세스의 PEB(Process Environment Block)에 있는 `BeingDebugged` 플래그 한 바이트를 읽어서 그대로 반환하는 아주 단순한 함수이며, 크랙미/악성코드는 이 값을 확인해 "디버거가 붙어 있으면" 실행을 중단하거나 오동작하도록 분기한다 — 이 글은 자신이 직접 만들거나 CTF로 받은 연습용 크랙미에서 이 체크를 이해하고 인식하는 법을 다룬다.

## 언제 검색해야 하나
- IDA/x64dbg의 import 목록에서 `kernel32.dll`의 `IsDebuggerPresent`가 보일 때
- x64dbg로 프로그램을 실행하면 콘솔 없이 그냥 실행할 때와 다르게 동작하거나 조용히 종료될 때
- 디컴파일된 코드에서 인자 없이 호출되는 함수 뒤에 `test eax, eax` / `jnz`가 바로 이어지는데 그 함수가 뭔지 모를 때
- `CheckRemoteDebuggerPresent`라는 비슷한 이름의 함수를 봤을 때 `IsDebuggerPresent`와 차이가 궁금할 때

## 핵심 개념

### PEB와 BeingDebugged 플래그
Windows에서 모든 프로세스는 커널이 유지하는 **PEB(Process Environment Block)**라는 구조체를 가지고 있고, 이 구조체는 유저 모드 코드에서도 접근 가능한 주소에 매핑되어 있다(x64에서는 `GS:[0x60]`, x86에서는 `FS:[0x30]`로 접근). PEB 구조체의 오프셋 `+2` 위치에는 `BeingDebugged`라는 딱 1바이트짜리 필드가 있는데, **운영체제가 이 프로세스를 디버거가 실행시켰다면(또는 디버거가 attach했다면) 이 값을 1로 세팅**한다.

### IsDebuggerPresent가 하는 일
`IsDebuggerPresent()`는 사실상 다음과 같은 아주 짧은 코드와 동등하다.
```c
BOOL IsDebuggerPresent(void) {
    return NtCurrentTeb()->ProcessEnvironmentBlock->BeingDebugged;
}
```
어셈블리로 인라인되면 대략 이런 모습이다.
```asm
mov     rax, gs:[60h]     ; PEB 주소
movzx   eax, byte ptr [rax+2]  ; BeingDebugged 필드
ret
```
인자가 없고, 반환값이 `BOOL`(0 또는 0이 아닌 값)이며, 순수하게 메모리 한 바이트를 읽어오는 것뿐이라는 점이 핵심이다. **이 API 자체는 아무런 "탐지 로직"을 갖고 있지 않다 — 그냥 OS가 이미 세팅해둔 플래그를 읽어서 전달할 뿐이다.**

### 크랙미에서의 사용 패턴
```c
if (IsDebuggerPresent()) {
    MessageBoxA(NULL, "No debugging!", "Error", MB_OK);
    ExitProcess(1);
}
```
디컴파일에서는 `call IsDebuggerPresent` 직후 `test eax, eax`와 `jnz`/`jne` 조합으로 자주 나타난다. 함수 이름 자체가 그대로 import 심볼로 남기 때문에, 정적 분석 단계에서 IDA의 Imports 탭이나 Ghidra의 Symbol Tree에서 이름만 봐도 바로 알아볼 수 있다는 것이 이 체크의 특징이자 약점이다.

### CheckRemoteDebuggerPresent와의 차이
`CheckRemoteDebuggerPresent(HANDLE hProcess, PBOOL pbDebuggerPresent)`는 이름은 비슷하지만 프로세스 핸들을 인자로 받아서(자기 자신의 핸들을 넘기는 경우가 많다) 결과를 `pbDebuggerPresent`가 가리키는 위치에 채워 넣는 방식이다. 내부적으로는 `NtQueryInformationProcess`를 통해 커널에 "이 프로세스에 디버그 포트가 연결되어 있는지" 물어보는 방식이라 PEB만 보는 `IsDebuggerPresent`보다 조금 더 신뢰도가 높지만, 원리(운영체제가 유지하는 디버그 관련 상태를 조회)는 같은 계열이다.

### 더 깊이 들어가는 변형: NtQueryInformationProcess 기반 체크
`IsDebuggerPresent`가 너무 흔하고 이름부터 눈에 띈다는 걸 아는 크랙미 제작자는, 같은 정보를 더 낮은 레벨의 네이티브 API `NtQueryInformationProcess`(`ntdll.dll`)로 직접 조회하기도 한다. 대표적으로 쓰이는 정보 클래스는 다음과 같다.
- `ProcessDebugPort`(0x07): 디버거가 붙어 있으면 0이 아닌 값이 반환된다. `CheckRemoteDebuggerPresent`가 내부적으로 이 클래스를 사용한다.
- `ProcessDebugFlags`(0x1F): 디버거가 없을 때 1, 있을 때 0이 반환되는(다른 값들과 반대 방향인) 필드라 코드를 읽을 때 부호를 헷갈리기 쉽다.
- `ProcessDebugObjectHandle`(0x1E): 디버거가 있으면 유효한 커널 핸들 값이, 없으면 실패 코드(`STATUS_PORT_NOT_SET`)가 반환된다.

이 API들은 `IsDebuggerPresent`처럼 import 목록에서 이름 하나로 딱 드러나지 않고 `ntdll.dll`의 `NtQueryInformationProcess` 하나를 통해 여러 종류의 질의를 처리하기 때문에, 어떤 정보를 요청하는지는 호출 시 넘기는 두 번째 인자(정보 클래스 상수)를 직접 확인해야만 알 수 있다는 점이 `IsDebuggerPresent`와의 큰 차이다. 분석 난이도가 한 단계 더 올라가는 이유이기도 하다.

## 화면/코드에서 보이는 징후
- IDA Imports 탭 또는 x64dbg의 Symbols 창에 `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`라는 이름이 그대로 보인다(이름 난독화가 없다면).
- 디컴파일 코드에서 `if (IsDebuggerPresent())`처럼 함수명이 그대로 노출된 조건문이 보인다.
- x86 어셈블리에서 `fs:[30h]` 접근, x64에서 `gs:[60h]` 접근 뒤 오프셋 `+2` 바이트를 읽는 코드가 있다면, API 호출 없이 PEB를 직접 읽는 "인라인 버전"일 수 있다(REV-0236 참고).
- 프로그램을 더블클릭으로 실행하면 정상, x64dbg로 열어서 실행(`F9`)하면 다른 동작을 보이는 대조가 관찰된다.

## 가장 먼저 할 것
1. IDA Imports 탭에서 `IsDebuggerPresent` / `CheckRemoteDebuggerPresent`가 있는지 검색한다(`Ctrl+F`).
2. 있다면 xref(`X`)로 호출 위치를 찾는다.
3. 호출 직후 반환값을 검사하는 분기와, 그 분기가 향하는 "탐지됨" 블록의 내용을 확인한다.

## 단계별 절차 (자신의 연습용 크랙미에서 이해/패치하는 법)
1. IDA에서 `IsDebuggerPresent` 호출 지점을 xref로 찾아 디컴파일 화면에서 확인한다.
2. `call IsDebuggerPresent` 다음에 오는 `test eax, eax` + `jnz`(또는 `jne`) 명령의 주소를 기록한다.
3. x64dbg에서 그 주소로 이동해(`Ctrl+G`) 분기 명령에 브레이크포인트(`F2`)를 건다.
4. `F9`로 실행해서 멈추면, 레지스터 창에서 `EAX`(또는 `RAX`) 값을 확인한다 — 디버거가 붙어 있으니 정상적으로 `1`(참)이 나오는 것을 직접 확인할 수 있다.
5. **개념 이해를 위한 패치 실습**: 그 분기 명령을 우클릭 → Assemble로 무조건 "정상" 경로로 가도록 바꾸거나(예: `jnz`를 `jmp`로, 또는 조건을 반전), 아예 `test eax, eax` 앞에서 `EAX`를 직접 `0`으로 세팅한다.
6. 더 범용적인 학습 방법으로, x64dbg의 플러그인 **ScyllaHide** 또는 **TitanHide**가 `IsDebuggerPresent`가 항상 `FALSE`를 반환하도록 API 후킹을 자동으로 해주는 원리를 살펴보면, "개별 분기 패치" 대신 "API 자체의 반환값을 가로채는" 접근 방식도 있다는 것을 이해할 수 있다.

## 명령어/단축키
- IDA: `Ctrl+F`(Imports 탭에서 함수명 검색), `X`(Xrefs to), `F5`(디컴파일)
- x64dbg: `Ctrl+G`(주소로 이동), `F2`(브레이크포인트 토글), `F9`(실행), 레지스터 패널에서 `EAX` 확인, 명령어 우클릭 → Assemble(직접 패치)
- x64dbg 플러그인: ScyllaHide/TitanHide 활성화 후 Options에서 `IsDebuggerPresent` 후킹 옵션 확인(플러그인이 이미 이 API들을 자동으로 스푸핑해주는 목록을 갖고 있다)

## 출력 해석
- 브레이크포인트에서 멈췄을 때 `EAX == 1`이면 현재 디버거가 붙어 있다는 것을 프로그램이 정확히 인지한 상태다.
- 패치 후 다시 실행했을 때 `EAX == 0`으로 바뀌었는데도 여전히 프로그램이 이상하게 동작한다면, 같은 종류의 체크가 다른 곳에 하나 더(또는 PEB 직접 읽기 방식으로) 존재할 가능성이 높다(REV-0236 참고).

## 흔한 실수
- `IsDebuggerPresent` 하나만 패치하고 안심하는 것 — 실제 크랙미는 보통 여러 겹의 체크(PEB 직접 읽기, 타이밍 체크, 예외 기반 체크 등)를 함께 쓴다.
- 이 API를 "디버거를 실제로 감지하는 마법"이라고 오해하는 것 — 실제로는 OS가 관리하는 플래그 한 바이트를 읽어오는 것뿐이며, 그 플래그 자체를 조작/후킹하면 무력화된다는 원리를 이해하는 것이 핵심이다.
- 상용 소프트웨어나 제3자 프로그램의 보호를 무력화하려는 목적으로 이 지식을 쓰는 것 — 이 글은 자신이 소유하거나 CTF로 배포된 연습용 바이너리를 이해하는 용도로만 사용해야 한다.
- `ProcessDebugFlags`처럼 "디버거가 없을 때 1을 반환"하는, 다른 체크들과 반대 방향의 값을 가진 정보 클래스를 다른 체크와 똑같은 방식(0이면 정상, 1이면 탐지)으로 해석해 분기 조건을 반대로 읽는 것.

## 막혔을 때 다음 체크
- 이름이 그대로 안 보인다면 → import 이름이 난독화되었거나 API를 직접 코드로 인라인했을 수 있다. `fs:[30h]`/`gs:[60h]` 패턴이 있는지 REV-0236을 참고해 확인한다.
- 패치했는데도 여전히 막힌다면 → RDTSC 기반 타이밍 체크(REV-0237)나 예외 기반 체크(REV-0239)가 같이 있는지 확인한다.
- 여러 체크가 뒤섞여 헷갈리면 → 정적 분석을 잠시 멈추고 동적으로 하나씩 브레이크포인트를 걸며 실제 실행 흐름을 관찰한다(REV-0241).

## 미니 예제
**예제 — 전형적인 사용 패턴**
```c
#include <windows.h>
int main() {
    if (IsDebuggerPresent()) {
        MessageBoxA(NULL, "Debugger detected!", "Error", MB_OK);
        return 1;
    }
    printf("Welcome!\n");
    return 0;
}
```
```asm
call    IsDebuggerPresent
test    eax, eax
jnz     debugger_detected
```

## 관련 글
- REV-0236 — PEB BeingDebugged 검사 우회 개념
- REV-0239 — Exception 기반 안티디버깅 기초
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트

## 출처/검증
- `IsDebuggerPresent`/`CheckRemoteDebuggerPresent` API 정의와 동작: Microsoft Learn(Win32 API 문서), `IsDebuggerPresent function (debugapi.h)` 및 `CheckRemoteDebuggerPresent function` 공식 문서 기준(2026-09-08 검증).
- PEB `BeingDebugged` 필드와의 관계: Microsoft Learn 문서 및 공개된 PEB 구조체 리버스엔지니어링 레퍼런스 기준.
