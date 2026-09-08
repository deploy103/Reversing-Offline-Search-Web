---
id: REV-0130
title: "IsDebuggerPresent 안티디버깅 식별"
slug: "rev-0130-isdebuggerpresent"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["IsDebuggerPresent", "안티디버깅", "anti-debugging", "PEB BeingDebugged", "디버거 탐지", "kernel32 IsDebuggerPresent"]
aliases: ["IsDebuggerPresent 함수", "디버거 감지 API", "안티디버그 식별", "이즈디버거프레즌트"]
symptom_keywords: ["import table에 IsDebuggerPresent 있음", "디버거로 열면 프로그램이 다르게 동작함", "call IsDebuggerPresent 다음에 뭘 하는지 모르겠음", "x64dbg로 열면 강제 종료됨", "test eax eax 뒤에 종료 분기가 있음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`IsDebuggerPresent`는 프로세스가 현재 사용자 모드 디버거에 의해 실행되고 있는지를 단 한 줄로 확인할 수 있는 가장 기본적인 Win32 안티디버깅 API로, Import Table이나 문자열에서 이 이름이 보이면 그 직후의 `test eax, eax` 분기가 "디버거가 붙어 있으면 다르게 동작하도록" 만드는 지점이라는 것을 바로 알아챌 수 있어야 한다.

## 언제 검색해야 하나
- PE-bear/IDA의 Import Table에서 `IsDebuggerPresent`라는 이름을 발견했을 때
- 같은 프로그램인데 그냥 실행했을 때와 x64dbg/IDA로 디버깅하며 실행했을 때 동작이 달라지는(예: 조용히 종료되거나, 다른 메시지가 뜨는) 상황을 마주쳤을 때
- Strings 창에 안티디버깅 관련 문자열은 없는데 프로그램이 디버거를 감지하는 것 같은 낌새가 있을 때, 우선 가장 흔한 API부터 의심하고 싶을 때
- CTF 문제에서 "디버거로 열면 풀이가 막힌다"는 힌트가 있을 때 가장 먼저 확인해야 할 함수가 뭔지 알고 싶을 때

## 핵심 개념

### 함수 시그니처와 동작
```c
BOOL IsDebuggerPresent(void);
```
인자가 전혀 없고, 현재 프로세스가 사용자 모드 디버거(x64dbg, WinDbg, IDA의 디버거 등)에 의해 디버깅되고 있으면 0이 아닌 값(TRUE), 아니면 0(FALSE)을 반환한다. 커널 디버거(예: 특수한 커널 레벨 디버깅 환경)는 이 API로 감지되지 않는다 — 어디까지나 "사용자 모드 디버거가 이 프로세스에 붙어 있는가"만 확인한다.

### 내부적으로 무엇을 확인하나
`IsDebuggerPresent`는 내부적으로 현재 프로세스의 **PEB(Process Environment Block)** 구조체 안에 있는 `BeingDebugged`라는 1바이트 플래그를 읽어서 그대로 반환한다. 이 플래그는 프로세스가 디버거에 의해 생성되거나(디버거로 직접 실행) 나중에 `DebugActiveProcess`로 디버거가 붙었을 때 Windows 커널이 자동으로 1로 세팅한다. 즉 `IsDebuggerPresent`는 사실상 이 플래그를 확인하는 것의 "공식 API 버전"이며, 같은 정보를 코드가 API 호출 없이 PEB를 직접 읽어서 확인하는 변형도 있다(REV-0132에서 다룬다).

### 왜 이렇게 흔하게 쓰이나
- 구현이 API 호출 한 줄로 끝나서 넣기 쉽다.
- 상용 프로텍터부터 간단한 CTF 문제까지 폭넓게 쓰이는 "1차 방어선"이다.
- 이름 자체가 워낙 잘 알려져 있어서, Import Table에 이 이름이 그냥 보인다는 것 자체가 "이 파일은 최소한의 안티디버깅을 갖추고 있다"는 신호로 통용된다.

### 이 문서의 범위
이 문서는 **식별(identification)**까지만 다룬다. `IsDebuggerPresent`를 우회(bypass)하는 구체적인 기법(반환값 패치, PEB 플래그 직접 수정, 후킹 등)은 이후 패킹/안티분석 카테고리의 별도 문서에서 더 깊게 다룰 예정이다. 여기서는 "이 함수가 코드 어디서 호출되고, 그 결과가 어떻게 쓰이는지 알아보는 법"까지만 확인한다.

### x86과 x64에서의 호출 형태 차이
`IsDebuggerPresent`는 인자가 없으므로 x86/x64 모두 `call IsDebuggerPresent` 이후 반환값이 `EAX`에 담긴다는 점은 동일하다. 다만 x86(32비트) 코드에서는 함수 호출 규약이 stdcall이라 `call` 이후 스택 정리(`add esp, N`)가 필요 없고(인자가 없으므로 정리할 것도 없다), x64 코드에서는 REV-0124에서 다룬 Shadow Space 확보(`sub rsp, 0x20` 이상)가 이 `call` 앞에 붙어 있는 경우가 많다는 점이 시각적인 차이다. 즉 x64에서 `IsDebuggerPresent` 호출부를 볼 때 그 위에 있는 `sub rsp, 0x28` 같은 코드를 "이 함수를 위한 특별한 준비"로 오해하지 말고, 그냥 일반적인 x64 함수 호출 관례로 이해하면 된다.

### WOW64 환경에서의 주의점
32비트로 컴파일된 프로그램이 64비트 Windows에서 WOW64(에뮬레이션 레이어) 위에서 실행되는 경우에도 `IsDebuggerPresent`는 동일하게 동작한다 — 다만 이때 실제로 참조되는 PEB는 WOW64용으로 별도 유지되는 32비트 PEB이며, 디버거(x32dbg 등)도 이에 맞춰 32비트 PEB를 봐야 정확한 값을 확인할 수 있다. 64비트 x64dbg로 32비트 프로세스를 직접 디버깅하려 하면 애초에 프로세스가 제대로 붙지 않으므로, 32비트 exe는 반드시 x32dbg로 열어야 한다는 점(REV-0127 참고)이 여기서도 다시 중요해진다.

## 화면/코드에서 보이는 징후
- IDA/PE-bear의 Imports 목록에 `kernel32.dll`의 `IsDebuggerPresent`가 있음.
- Strings 창이나 Import 목록에서 이 이름 자체가 그대로 문자열로 보이는 경우가 많다(동적 로딩으로 숨기지 않는 한).
- 디스어셈블리에서 다음과 같은 전형적인 패턴이 반복된다.
```asm
call IsDebuggerPresent
test eax, eax
jne  detected_branch   ; 또는 jnz
```
- `test eax, eax` 직후 분기(`jne`/`jnz`이면 "0이 아니면", 즉 디버거가 있으면 점프)가 종료 함수(`ExitProcess`, `TerminateProcess`), 이상한 값 리턴, 혹은 전혀 다른 코드 경로로 이어짐.
- x64dbg로 디버깅 중일 때만 특정 분기로 빠지고, 그냥 실행했을 때는 정상 동작하는 것을 관찰할 수 있음.

## 가장 먼저 할 것
`IsDebuggerPresent`를 Import 목록에서 발견하면, IDA에서 `X`(xref)로 호출 지점을 모두 찾는다. 호출이 한 곳뿐이면 그 직후 분기만 확인하면 되고, 여러 곳에서 호출된다면 프로그램 전반에 안티디버깅 체크가 흩어져 있다는 뜻이므로 각 호출 지점을 모두 표시해두고 분석 우선순위를 조정한다.

## 단계별 절차

**1) Import Table에서 확인**

PE-bear(REV-0125) 또는 IDA Imports 창에서 `IsDebuggerPresent`가 있는지 확인한다.

**2) 모든 호출 지점(xref) 찾기**

IDA에서 `IsDebuggerPresent` 이름 위에 커서를 놓고 `X`를 눌러 xref 목록을 연다. 이 함수를 부르는 모든 위치가 나열된다.

**3) 각 호출 직후의 분기 조건 확인**

각 호출 지점에서 `call IsDebuggerPresent` 다음 줄부터 살펴본다. 대개 `test eax, eax` 뒤에 `jne`/`jnz`(0이 아니면, 즉 디버거 감지 시 점프) 또는 `je`/`jz`(반대로 정상 흐름일 때 점프하는 형태로 쓰였을 수도 있음)가 온다. 두 분기 중 어느 쪽이 "디버거 감지됨" 경로인지 반드시 직접 따라가서 확인한다 — 이름만 보고 짐작하면 반대로 읽을 수 있다.

**4) 감지됐을 때의 동작 파악**

감지 시 분기가 어디로 이어지는지 끝까지 따라간다. `ExitProcess`/`TerminateProcess`로 바로 종료되는 단순한 경우도 있고, 일부러 잘못된 결과를 계산하도록 흐름을 바꿔서 "디버거로 보면 다른 값이 나오게" 만드는 더 교묘한 경우도 있다.

**5) x64dbg로 동적 관찰**

x64dbg 자체가 디버거이므로, `IsDebuggerPresent`를 그대로 실행시키면 당연히 TRUE가 반환된다. 브레이크포인트를 걸어 실제로 그렇게 되는지, 그리고 `test eax, eax` 직후 어느 분기로 빠지는지 직접 관찰한다.
```text
bp IsDebuggerPresent
run
; call 이후 ret까지 실행해서 EAX 값 확인
Ctrl+F9 (execute till return)
; Registers 창에서 EAX = 1 확인
```

**6) 필요하면 문자열/Strings로 보조 확인**

동적 로딩(REV-0129)으로 이 함수 이름 문자열만 숨겨둔 경우도 있으므로, Import Table에 안 보인다고 안심하지 말고 Strings 창에서 `"IsDebuggerPresent"` 문자열 자체가 있는지도 함께 확인한다.

## 명령어/단축키
- IDA: Imports 창에서 이름 검색, `X`(xref 목록), `Shift+F12`(Strings 창)
- x64dbg: `bp IsDebuggerPresent`, `Ctrl+F9`(Execute till return), Registers 창에서 `EAX` 확인
- x64dbg: 우클릭 → `Search for` → `All Modules` → `Intermodular calls`로 이 API를 부르는 모든 지점을 한 번에 나열 가능

## 출력 해석
- `EAX`(또는 `RAX`의 하위 32비트)가 `0`이면 디버거가 없다는 뜻, `1`(또는 0이 아닌 값)이면 디버거가 붙어 있다는 뜻이다.
- x64dbg로 실행 중이라면 이 값은 거의 항상 `1`이어야 정상이다. 만약 `IsDebuggerPresent` 호출 결과가 `0`으로 나온다면, 이미 어떤 안티-안티디버깅 패치나 플러그인(ScyllaHide 등)이 적용되어 있다는 뜻일 수 있다.
- 감지 분기 쪽 코드가 `ExitProcess`가 아니라 조용히 어떤 계산 결과만 바꾸는 형태라면, 겉보기엔 프로그램이 "정상적으로 끝까지 실행되는데 결과만 틀린" 상황이 되어 훨씬 알아채기 어렵다.

## 흔한 실수
- 분기 방향(`jne`/`je`)을 확인하지 않고 "당연히 이쪽이 감지 시 분기겠지"라고 추측만으로 결론 내리는 것 — 항상 실제로 따라가서 확인해야 한다.
- `IsDebuggerPresent` 호출이 하나뿐이라고 가정하고 나머지 호출 지점을 놓치는 것 — 반드시 `X`(xref)로 전체 목록을 확인해야 한다.
- 이 API 하나만 확인하고 "안티디버깅이 더는 없다"고 단정하는 것 — `CheckRemoteDebuggerPresent`(REV-0131), PEB `BeingDebugged` 직접 검사(REV-0132) 등 같은 목적의 다른 방법이 함께 쓰이는 경우가 흔하다.
- 우회(패치/후킹) 방법부터 먼저 찾으려 하는 것 — 이 문서 범위에서는 식별과 흐름 파악까지만 다루며, 실전 우회는 별도 패킹/안티분석 문서에서 다룬다.

## 막혔을 때 다음 체크
- 원격 프로세스 관점에서 확인하는 변형 API가 궁금하다면 → REV-0131 CheckRemoteDebuggerPresent 식별
- API 호출 없이 PEB를 직접 읽는 더 은밀한 방식이 궁금하다면 → REV-0132 PEB BeingDebugged 검사 이해
- 이 함수 이름이 Import Table에 없고 동적으로 로드되는 것 같다면 → REV-0129 GetProcAddress LoadLibrary 동적 API 해석
- x64dbg 자체 사용법이 아직 낯설다면 → REV-0127 x64dbg로 EXE 첫 분석 시작

## 미니 예제
```c
if (IsDebuggerPresent()) {
    MessageBoxA(NULL, "Debugger detected!", "Error", MB_OK);
    ExitProcess(1);
}
printf("Enter flag: ");
```
디스어셈블리(x64)로는 다음과 같이 나타난다.
```asm
call IsDebuggerPresent
test eax, eax
je   no_debugger        ; EAX == 0(디버거 없음)이면 정상 경로로 점프

; 여기부터는 디버거가 감지됐을 때(EAX != 0) 실행되는 경로
lea  rdx, [msg_str]      ; "Debugger detected!"
lea  rcx, [title_str]
call MessageBoxA
mov  ecx, 1
call ExitProcess

no_debugger:
; printf("Enter flag: ") 등 정상 로직 계속
```
이 예제에서는 `je`(EQ, 즉 EAX==0)일 때 정상 경로로 빠지고, 조건을 통과하지 못하면(디버거 감지) 그대로 아래로 흘러 종료된다 — 앞서 강조했듯 분기 방향은 반드시 코드를 직접 보고 확인해야 한다.

## 관련 글
- REV-0131 — CheckRemoteDebuggerPresent 식별
- REV-0132 — PEB BeingDebugged 검사 이해
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- `IsDebuggerPresent` 함수 시그니처와 PEB `BeingDebugged` 플래그 기반 동작은 Microsoft 공식 문서(learn.microsoft.com, "IsDebuggerPresent function") 및 Windows 안티디버깅 관례 레퍼런스 기준(2026-09-08 확인).
- 안티디버깅 식별과 우회는 별개 주제로 다루며, 우회 세부사항은 이 저장소의 패킹/안티분석 카테고리 문서(추후 작성)에서 확장한다.
