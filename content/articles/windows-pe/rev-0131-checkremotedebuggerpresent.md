---
id: REV-0131
title: "CheckRemoteDebuggerPresent 식별"
slug: "rev-0131-checkremotedebuggerpresent"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CheckRemoteDebuggerPresent", "안티디버깅", "anti-debugging", "GetCurrentProcess", "pbDebuggerPresent", "kernel32 CheckRemoteDebuggerPresent"]
aliases: ["체크리모트디버거프레즌트", "원격 디버거 확인 API", "CheckRemoteDebuggerPresent 함수"]
symptom_keywords: ["import table에 CheckRemoteDebuggerPresent 있음", "pbDebuggerPresent 인자가 뭔지 모르겠음", "GetCurrentProcess 반환값이 -1임", "IsDebuggerPresent 말고 다른 안티디버깅 API가 있음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CheckRemoteDebuggerPresent`는 이름과 달리 원격 컴퓨터가 아니라 **지정한 프로세스 핸들**(대개 `GetCurrentProcess()`로 얻은 자기 자신)에 디버거가 붙어 있는지 확인하는 API로, 결과를 반환값이 아니라 **포인터로 넘긴 BOOL 변수**에 채워준다는 점에서 `IsDebuggerPresent`와 호출부 코드 모양이 다르다.

## 언제 검색해야 하나
- Import Table에서 `CheckRemoteDebuggerPresent`라는 낯선 이름을 발견했을 때
- `IsDebuggerPresent`는 못 찾았는데 여전히 디버거 감지 동작이 의심될 때, 대체/보완용으로 흔히 같이 쓰이는 이 API를 확인하고 싶을 때
- 디스어셈블리에서 `call GetCurrentProcess` 직후 `call CheckRemoteDebuggerPresent`가 이어지는 패턴을 봤을 때
- 함수 호출부에서 두 번째 인자가 어떤 지역 변수의 **주소**(`lea` 명령으로 만들어짐)로 넘어가는데, 왜 값이 아니라 주소를 넘기는지 이해가 안 될 때

## 핵심 개념

### 함수 시그니처
```c
BOOL CheckRemoteDebuggerPresent(
    HANDLE hProcess,
    PBOOL  pbDebuggerPresent
);
```
- `hProcess`: 확인하고 싶은 프로세스의 핸들. 자기 자신을 검사하려면 `GetCurrentProcess()`가 반환하는 **의사 핸들(pseudo handle)**, 즉 항상 `-1`(모든 비트가 1, `(HANDLE)-1`)인 값을 그대로 넘긴다. 이 값은 실제 커널 객체를 가리키는 진짜 핸들이 아니라 "현재 프로세스"를 의미하는 특수 상수이며, `CloseHandle`로 닫을 필요도 없다.
- `pbDebuggerPresent`: 결과를 받을 `BOOL` 변수의 **주소**. 함수 자체의 반환값(`BOOL`)은 "이 API 호출 자체가 성공했는지"를 나타내고, 실제 "디버거가 있는지 없는지" 결과는 이 포인터가 가리키는 메모리에 채워진다.

이름이 "Remote"이지만, 인자로 다른 프로세스의 핸들을 넘기면 실제로 다른 프로세스를 원격에서 검사하는 용도로도 쓸 수 있다. 하지만 안티디버깅 목적으로는 거의 항상 **자기 자신의 핸들**을 넘겨서 자기 자신이 디버깅되고 있는지 확인하는 데 쓰인다.

### IsDebuggerPresent와의 차이
| 항목 | IsDebuggerPresent | CheckRemoteDebuggerPresent |
|---|---|---|
| 인자 | 없음 | 프로세스 핸들 + 결과를 담을 BOOL 포인터 |
| 결과 위치 | 함수 반환값(`EAX`) | 두 번째 인자가 가리키는 메모리 |
| 검사 방식(내부) | PEB `BeingDebugged` 플래그 직접 읽기 | 커널에 질의(`NtQueryInformationProcess`류 내부 호출을 거치는 것으로 알려짐) |
| 다른 프로세스 검사 가능 여부 | 불가(현재 프로세스만) | 가능(핸들만 있으면 임의 프로세스 검사 가능) |

`IsDebuggerPresent`가 PEB 값을 그대로 읽어오는 "가벼운" 검사라면, `CheckRemoteDebuggerPresent`는 커널에 실제로 질의하는 방식이라 알려져 있어 다른 경로로 탐지를 우회당했을 때도 별도로 걸릴 수 있는 보완적인 검사로 함께 쓰이는 경우가 많다.

### 왜 두 API를 같이 쓰는가
안티디버깅을 여러 겹으로 쌓아두는(레이어드 디펜스) 전형적인 방식이다. 한쪽 검사(`IsDebuggerPresent`)를 패치나 후킹으로 무력화해도, 서로 다른 내부 경로를 쓰는 다른 검사(`CheckRemoteDebuggerPresent`)가 여전히 살아있으면 탐지를 완전히 피하기 어렵다. 그래서 실전 바이너리에서는 이 두 API가 같은 함수 안에서 연달아, 혹은 프로그램 여러 곳에 흩어져 함께 등장하는 경우가 흔하다.

## 화면/코드에서 보이는 징후
- Import Table에 `kernel32.dll`의 `CheckRemoteDebuggerPresent`가 있음.
- 디스어셈블리에서 다음과 같은 패턴이 반복된다.
```asm
call GetCurrentProcess       ; 반환값 RAX = -1 (의사 핸들)
mov  rcx, rax                ; 첫 번째 인자: hProcess
lea  rdx, [local_bool]       ; 두 번째 인자: &pbDebuggerPresent (스택 변수 주소)
call CheckRemoteDebuggerPresent
movzx eax, byte ptr [local_bool]
test eax, eax
jne  detected_branch
```
- `lea` 명령으로 스택 지역 변수의 주소를 만든 뒤 두 번째 인자로 넘기는 모습이 `IsDebuggerPresent` 패턴과 뚜렷이 다른 시각적 특징이다.
- `CheckRemoteDebuggerPresent` 호출 자체의 반환값(`EAX`)이 아니라, 그 이후 스택 변수를 다시 읽어서(`movzx eax, byte ptr [...]`) 검사하는 코드가 이어짐.

## 가장 먼저 할 것
`CheckRemoteDebuggerPresent`를 발견하면 먼저 두 번째 인자로 넘어가는 지역 변수(스택 슬롯)의 주소를 특정한다. 그 주소가 함수 호출 이후 어디서 다시 읽히는지(`movzx`, `cmp` 등) 찾는 것이 이 API의 실제 결과를 확인하는 핵심이다 — `IsDebuggerPresent`처럼 `EAX`만 보면 안 된다.

## 단계별 절차

**1) Import Table 및 xref 확인**

IDA Imports에서 `CheckRemoteDebuggerPresent`를 찾고 `X`로 호출 지점을 모두 나열한다.

**2) 첫 번째 인자(hProcess) 확인**

호출 직전 `RCX`(x64)에 들어가는 값을 역추적한다. 대개 바로 위에 `call GetCurrentProcess`가 있고 그 반환값을 그대로 옮기는 패턴이다. `GetCurrentProcess()`가 항상 `-1`을 반환하는 의사 핸들이라는 것을 알고 있으면 "이건 자기 자신을 검사하는구나"라고 바로 판단할 수 있다.

**3) 두 번째 인자(pbDebuggerPresent) 주소 특정**

`RDX`에 들어가는 값이 `lea rdx, [rbp-N]`(또는 `[rsp+N]`) 형태로 스택 변수 주소를 만드는 코드인지 확인하고, 그 스택 오프셋(`rbp-N` 등)을 기억해둔다.

**4) 호출 이후 결과를 읽는 코드 찾기**

같은 스택 오프셋(`[rbp-N]`)을 다시 읽는 코드(`movzx eax, byte ptr [rbp-N]` 등)를 찾는다. 이 값이 실제 "디버거가 있는지"를 나타내는 최종 결과다.

**5) 분기 방향 확인**

그 값을 검사하는 `test`/`cmp` 이후의 `je`/`jne` 분기가 각각 어디로 이어지는지 실제로 따라가서, 어느 쪽이 "감지됨" 경로인지 확정한다.

**6) x64dbg로 동적 확인**

```text
bp CheckRemoteDebuggerPresent
run
; 실행 후 리턴 직전(Ctrl+F9)까지 진행
; RDX에 저장해뒀던 스택 주소를 Dump 창에서 직접 확인 (1바이트, 0 또는 1)
```

## 명령어/단축키
- IDA: Imports 검색, `X`(xref), 스택 변수 클릭 시 함수 전체에서 같은 변수를 쓰는 다른 위치를 하이라이트로 확인 가능
- x64dbg: `bp CheckRemoteDebuggerPresent`, `Ctrl+F9`(Execute till return), Dump 창에서 두 번째 인자 주소의 바이트 값 확인
- x64dbg: 우클릭 → `Search for` → `Intermodular calls`로 이 API의 모든 호출부 한 번에 나열

## 출력 해석
- 두 번째 인자가 가리키는 메모리 값이 `0`이면 디버거 없음, `1`(또는 0이 아닌 값)이면 디버거 있음이다. 함수 자체의 반환값(`EAX`)은 API 호출 성공 여부일 뿐, 디버거 유무와는 별개다 — 이 둘을 혼동하면 안 된다.
- x64dbg로 디버깅 중이라면 이 값은 정상적으로 `1`이 나와야 한다. `0`이 나온다면 이미 안티-안티디버깅 우회가 적용된 상태일 수 있다.
- `GetCurrentProcess()`의 반환값이 `-1`(즉 `0xFFFFFFFFFFFFFFFF`)이 아니라 다른 값이라면, 코드가 자기 자신이 아니라 실제로 다른 프로세스 핸들을 대상으로 검사하고 있다는 뜻이므로 그 핸들이 어디서 열렸는지 추가로 추적해야 한다.

## 흔한 실수
- `CheckRemoteDebuggerPresent`의 반환값(`EAX`)을 `IsDebuggerPresent`처럼 곧바로 디버거 유무 판단에 쓰는 것 — 실제 결과는 두 번째 인자가 가리키는 메모리에 있다.
- `lea rdx, [...]`로 만들어지는 두 번째 인자 주소를 놓치고 그냥 상수라고 오해하는 것.
- "Remote"라는 이름 때문에 이 API가 네트워크 너머 다른 컴퓨터를 검사한다고 착각하는 것 — 실제로는 로컬 프로세스 핸들을 대상으로 하며, 안티디버깅 용도로는 거의 항상 자기 자신을 가리킨다.
- `IsDebuggerPresent` 하나만 우회하고 이 API는 놓쳐서, 여전히 감지되는 상황을 "왜 아직도 걸리지" 하며 헤매는 것.

## 막혔을 때 다음 체크
- 더 기본적인 형태의 디버거 감지 API가 궁금하다면 → REV-0130 IsDebuggerPresent 안티디버깅 식별
- PEB를 API 호출 없이 직접 읽는 방식이 궁금하다면 → REV-0132 PEB BeingDebugged 검사 이해
- 이 API 자체가 Import Table에 없고 동적으로 로드되는 것 같다면 → REV-0129 GetProcAddress LoadLibrary 동적 API 해석
- 스택 변수 주소가 인자로 넘어가는 패턴(포인터로 결과 받기) 자체가 낯설다면 → REV-0122 Microsoft x64 호출 규약

## 미니 예제
```c
BOOL debugged = FALSE;
CheckRemoteDebuggerPresent(GetCurrentProcess(), &debugged);
if (debugged) {
    ExitProcess(1);
}
```
디스어셈블리(x64)로는 다음과 같이 나타난다.
```asm
call GetCurrentProcess         ; rax = -1
mov  rcx, rax                  ; hProcess
lea  rdx, [rbp-0x4]            ; &debugged
call CheckRemoteDebuggerPresent
movzx eax, byte ptr [rbp-0x4]  ; debugged 값 읽기
test eax, eax
je   continue_normally
mov  ecx, 1
call ExitProcess
continue_normally:
```

## 관련 글
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0132 — PEB BeingDebugged 검사 이해
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0122 — Microsoft x64 Calling Convention

## 출처/검증
- `CheckRemoteDebuggerPresent`, `GetCurrentProcess` 함수 시그니처와 의사 핸들(`-1`) 동작은 Microsoft 공식 문서(learn.microsoft.com, "CheckRemoteDebuggerPresent function", "GetCurrentProcess function") 기준(2026-09-08 확인).
