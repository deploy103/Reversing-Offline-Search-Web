---
id: REV-0535
title: "OutputDebugString을 이용한 안티디버깅 탐지"
slug: "rev-0535-outputdebugstring-anti-debugging"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["OutputDebugStringA", "OutputDebugStringW", "GetLastError 안티디버깅", "DBG_PRINTEXCEPTION_C", "SetLastError 트릭"]
aliases: ["OutputDebugString 안티디버깅", "OutputDebugStringA 우회", "GetLastError 트릭", "디버그 문자열 안티디버깅"]
symptom_keywords: ["OutputDebugStringA 호출 뒤 GetLastError를 확인함", "SetLastError로 특정 값을 미리 세팅해두고 뭔가 확인함", "디버거 없이 실행하면 크래시하는데 왜 그런지 모르겠음", "GetLastError 값이 왜 바뀌는지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`OutputDebugStringA`/`W`는 디버거가 붙어 있을 때와 없을 때 내부적으로 완전히 다른 경로로 동작하는데, 디버거가 없으면 이 API가 예외(`DBG_PRINTEXCEPTION_C`, `0x40010006`)를 일으켜 시스템 예외 핸들러가 `SetLastError`를 특정 값(`0xBADF00D`, 대략 "bad food"를 흉내낸 십진수 `195939181`에 가까운 관례적 상수)으로 세팅하는 특이한 부작용을 이용해, 이 함수를 부른 직후 `GetLastError()`를 확인하는 것만으로 디버거 유무를 판단할 수 있다는 잘 알려진 트릭이다.

## 언제 검색해야 하나
- 디스어셈블리에서 `SetLastError`로 어떤 임의의 값을 미리 세팅해두고, 곧바로 `OutputDebugStringA`(또는 `W`)를 호출한 뒤 다시 `GetLastError()`로 값을 확인하는 특이한 순서를 봤을 때
- 디버거 없이 실행하면 프로그램이 이상하게 동작하거나 크래시하는데, x64dbg로 열면 오히려 정상 작동하는(또는 반대인) 현상을 마주쳤을 때
- `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, `NtQueryInformationProcess` 어느 것도 안 보이는데 여전히 디버거를 감지하는 것 같은 바이너리를 만났을 때
- CTF 문제에서 안티디버깅 종류를 하나씩 소거해가다가 마지막까지 원인을 못 찾았을 때, 흔히 놓치는 이 기법을 확인하고 싶을 때

## 핵심 개념

### 왜 OutputDebugString이 안티디버깅에 쓰이는가
`OutputDebugStringA(LPCSTR lpOutputString)`는 원래 개발자가 디버거의 출력 창에 로그 메시지를 보내기 위한 평범한 API다. 그런데 이 함수의 구현 내부 동작이 디버거 유무에 따라 달라진다는 특성이 안티디버깅에 악용된다.

- **디버거가 붙어 있을 때**: 문자열이 정상적으로 디버거의 출력 창(x64dbg의 Log 창 등)에 전달되고, `GetLastError()`는 이 호출 전에 세팅해둔 값을 그대로 유지한다.
- **디버거가 없을 때**: 이 API는 시스템 예외 `DBG_PRINTEXCEPTION_C`(코드 `0x40010006`)를 발생시켜 커널/시스템에 문자열을 전달하려 시도하는데, 이를 처리할 디버거가 없으므로 예외가 처리되지 않은 채 시스템 기본 처리 경로로 넘어가고, 그 과정에서 `GetLastError()`가 반환하는 값이 특정한 관례적 값(흔히 `0xBADF00D`로 알려진 값)으로 바뀌어버린다.

즉 코드는 이 함수를 부르기 **전에** `SetLastError(0)`(또는 다른 임의 값)로 초기화해두고, 함수를 부른 **뒤** `GetLastError()`를 다시 읽어 그 값이 바뀌었는지(디버거 없음) 그대로인지(디버거 있음)로 판단한다.

### 코드 패턴
```c
SetLastError(0);
OutputDebugStringA("test");
if (GetLastError() == 0) {
    // 값이 그대로 -> 디버거가 있어서 정상 경로로 처리됨
} else {
    // 값이 바뀜(0xBADF00D 등) -> 디버거가 없어서 예외 경로를 탐
}
```
분기 방향은 구현마다 다르게 쓰일 수 있으므로, 반드시 실제 코드에서 어느 쪽이 "디버거 있음" 경로인지 직접 확인해야 한다.

### 신뢰성과 한계
이 기법은 Windows 버전과 빌드에 따라 동작이 다소 다르게 보고된 사례가 있어(특히 최신 Windows 10/11에서는 예외 발생 여부나 `GetLastError` 값의 정확한 세부 동작이 예전 문서와 미묘하게 다를 수 있음), 상용 프로텍터보다는 교육적 예제나 비교적 단순한 CTF 문제에서 더 흔하게 사용된다. 그럼에도 "잘 알려진 API 하나를 다른 목적으로 부작용까지 이용하는" 대표적인 예시로서, 안티디버깅 기법을 폭넓게 이해하는 데 중요한 사례다.

### OutputDebugStringW와의 차이
유니코드 버전인 `OutputDebugStringW`도 유사한 원리로 동작하지만, 내부적으로 `OutputDebugStringA`를 호출하는 방식으로 구현된 경우가 많아 결과적으로 같은 예외/`GetLastError` 패턴을 보인다.

### 이 기법과 DBG_PRINTEXCEPTION_C 예외 코드
REV-0528에서 다룬 예외 코드 표에 있는 `0x40010006`(`DBG_PRINTEXCEPTION_C`)이 바로 이 함수가 디버거 없이 호출됐을 때 발생시키는 예외다. 이 예외는 심각도가 `0x4`(Informational)로, 실제 프로그램을 중단시키는 치명적 오류가 아니라 정보성 이벤트로 분류된다는 점도 함께 기억해두면 예외 코드 표를 해석할 때 도움이 된다.

## 화면/코드에서 보이는 징후
- 디스어셈블리에서 `call SetLastError`(인자로 `0` 또는 임의 상수) 직후 `call OutputDebugStringA`(또는 `W`), 그 뒤 `call GetLastError`가 연달아 나오는 특이한 3연속 패턴.
- x64dbg의 Log 창(`Alt+L`)에 `OutputDebugStringA`로 보낸 문자열이 실제로 출력되는 것을 확인할 수 있다 — 이는 디버거가 이 예외/문자열 전달을 정상적으로 소비하고 있다는 증거다.
- `GetLastError()` 반환값을 검사하는 `cmp eax, ...` 다음 분기가, 다른 API 실패 처리 코드와 달리 유독 이 호출 바로 뒤에 위치해 있어 맥락상 어색하게 느껴진다.

## 가장 먼저 할 것
`SetLastError` → `OutputDebugStringA/W` → `GetLastError` 3단계 조합을 발견하면, 이것이 일반적인 에러 처리 코드가 아니라 안티디버깅 트릭임을 먼저 의심한다. 일반적인 에러 처리라면 `GetLastError`가 직전에 실패할 수 있는 API(파일 열기 등) 바로 뒤에 오는 것이 자연스러운데, `OutputDebugString`처럼 실패할 일이 거의 없는 로깅 함수 뒤에 붙어 있다는 점 자체가 단서다.

## 단계별 절차

**1) 패턴 매칭**

IDA에서 `OutputDebugStringA`/`W`의 xref를 확인하고, 그 호출 직전/직후에 `SetLastError`/`GetLastError`가 함께 있는지 확인한다.

**2) SetLastError 초기값 확인**

`SetLastError` 호출의 인자(첫 번째, `RCX`)로 어떤 값이 들어가는지 확인한다. 대개 `0`이다.

**3) GetLastError 이후 비교 대상 확인**

`GetLastError` 호출 이후 어떤 값과 비교(`cmp eax, 0` 등)하는지 확인해, "값이 그대로면"과 "값이 바뀌었으면" 중 어느 쪽이 감지 경로인지 코드를 직접 따라가 확정한다.

**4) x64dbg로 두 가지 상황 비교**

디버거 없이(예: 탐색기에서 더블클릭) 실행했을 때와, x64dbg로 붙여서 실행했을 때 프로그램 동작이 실제로 다른지 비교 관찰한다.

**5) 우회 방법 적용**

가장 간단한 우회는 `GetLastError` 호출 직후 브레이크포인트를 걸고 `EAX`(반환값)를 원하는 값(대개 `SetLastError`로 세팅했던 값, 보통 `0`)으로 강제로 맞춰 "디버거 있음" 경로가 나오도록 만드는 것이다. `IsDebuggerPresent` 우회(REV-0531)와 원리가 같다 — 반환값을 조작하는 방식이므로 절차를 그대로 재활용할 수 있다.

## 명령어/단축키
- x64dbg: `Alt+L`(Log 창)에서 `OutputDebugString`으로 전달된 문자열 확인
- x64dbg: `bp kernel32.GetLastError`, `Ctrl+F9`(Execute till return), Registers 창에서 `EAX` 수정
- IDA: `Alt+T`로 `SetLastError`/`GetLastError`/`OutputDebugString` 문자열 일괄 검색

## 출력 해석
- x64dbg의 Log 창에 `OutputDebugString`으로 보낸 문자열이 표시된다면, 디버거가 이 예외/메시지를 정상적으로 소비하고 있다는 뜻이며 프로그램 입장에서는 "디버거 있음" 상태로 판단될 조건이 충족된 것이다.
- `GetLastError()` 값이 세팅했던 초기값과 다르게 나온다면, 이는 예외가 처리되지 않고 시스템 기본 경로로 흘러갔다는 뜻이므로 디버거가 없는 상태로 판단된다.
- 이 트릭 하나만으로 판단이 애매하다면(Windows 버전별 동작 차이), 다른 안티디버깅 기법(REV-0529)과 함께 조합되어 있는지 추가로 확인한다.

## 흔한 실수
- `SetLastError`/`GetLastError` 조합을 보고 무조건 일반적인 에러 처리 코드로 넘겨버리는 것 — 사이에 `OutputDebugString` 호출이 끼어 있는지 반드시 확인해야 한다.
- 이 기법이 모든 Windows 버전에서 동일하게 동작한다고 가정하는 것 — 버전에 따라 미묘한 차이가 보고된 바 있으므로, 실제 실행 환경에서 직접 동적으로 확인하는 것이 가장 정확하다.
- `DBG_PRINTEXCEPTION_C`(`0x40010006`) 예외를 심각한 오류로 오해하고 크래시 원인으로 잘못 지목하는 것 — 심각도가 Informational인 정상적인 정보성 이벤트다.
- 이 기법만 우회하고 다른 안티디버깅 기법(REV-0529의 나머지 분류)을 확인하지 않아 여전히 감지되는 상황에서 헤매는 것.

## 막혔을 때 다음 체크
- 이 기법이 만드는 예외 코드(`0x40010006`)의 전체 맥락이 궁금하다면 → REV-0528 Windows 예외 코드(Exception Code) 빠른 참조표
- 반환값 조작 방식의 우회 절차 기본형을 다시 보고 싶다면 → REV-0531 IsDebuggerPresent 우회 실습 개념과 한계
- 이 기법 외에 어떤 다른 안티디버깅 분류가 있는지 전체 지형을 다시 보고 싶다면 → REV-0529 Windows 안티디버깅 기법 종류 빠른 참조표
- SEH가 예외를 어떻게 넘겨받는지 배경 지식이 필요하다면 → REV-0134 SEH와 예외 기반 제어 흐름 기초

## 미니 예제
```asm
; SetLastError(0)
xor  ecx, ecx
call SetLastError

; OutputDebugStringA("probe")
lea  rcx, [probe_str]
call OutputDebugStringA

; GetLastError() 확인
call GetLastError
test eax, eax
je   debugger_present_branch   ; 0 그대로면(값 안 바뀜) 디버거가 예외를 소비한 것 -> 있음
; 아니면(0이 아니면) 디버거 없음 -> 아래로 계속 진행(예: 오답 처리 강제)
```

## 관련 글
- REV-0528 — Windows 예외 코드(Exception Code) 빠른 참조표
- REV-0531 — IsDebuggerPresent 우회 실습 개념과 한계
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표
- REV-0134 — SEH와 예외 기반 제어 흐름 기초

## 출처/검증
- `OutputDebugStringA`/`W` 함수 시그니처는 Microsoft 공식 문서(learn.microsoft.com, "OutputDebugStringA function") 기준. 디버거 유무에 따른 예외 발생 및 `GetLastError` 부작용을 이용한 안티디버깅 트릭은 공식 문서에 명시된 내용이 아니라 리버싱/보안 커뮤니티에서 오랫동안 검증되고 인용되어 온 잘 알려진 기법(예: "Anti-Debug Tricks" 계열 문헌)을 기준으로 정리했으며, 정확한 상수 값과 최신 Windows 버전에서의 동작은 실습 환경에서 직접 동적으로 재확인하는 것을 권장한다(2026-09-08 확인).
