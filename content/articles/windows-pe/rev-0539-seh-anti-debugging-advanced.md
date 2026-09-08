---
id: REV-0539
title: "SEH 기반 안티디버깅 심화"
slug: "rev-0539-seh-anti-debugging-advanced"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["SEH", "__try __except", "EXCEPTION_INVALID_HANDLE", "CloseHandle 안티디버깅", "first-chance exception", "예외 기반 제어 흐름", "SetUnhandledExceptionFilter"]
aliases: ["SEH 안티디버깅 심화", "예외 핸들러 안티디버깅", "CloseHandle 트릭", "구조적 예외 처리 안티디버깅", "first-chance 예외 트릭"]
symptom_keywords: ["CloseHandle을 이상한 값으로 호출한다", "__except 블록 안에서 종료 처리를 한다", "디버거로 실행하면 예외가 발생하고 그냥 실행하면 조용히 넘어간다", "first-chance exception 메시지가 x64dbg에 여러 번 뜬다", "정상 흐름에 필요한 코드가 예외 핸들러 안에만 있다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
디버거가 붙어 있으면 프로세스에서 발생한 예외를 프로그램의 SEH 핸들러보다 디버거가 먼저 가로채는(first-chance exception) Windows의 기본 동작을 역이용해서, 일부러 예외를 발생시킨 뒤 "내 핸들러가 정상적으로 실행됐는가" 또는 "특정 종류의 예외가 예상대로 처리됐는가"를 확인하면 디버거의 존재를 알아낼 수 있다 — REV-0134에서 다룬 SEH의 기본 동작을 실제 안티디버깅 무기로 응용한 것이 이 문서의 주제다.

## 언제 검색해야 하나
- REV-0134로 SEH의 기본 개념(`__try`/`__except`, 예외 체인)은 이해했는데, "이게 어떻게 안티디버깅에 쓰이는지" 궁금할 때
- `CloseHandle`을 존재하지 않는 핸들 값(예: `0xDEADBEEF`, `0x12345678`)으로 호출하는 코드를 발견했을 때
- x64dbg 로그 창에 `first-chance exception`이 여러 번 뜨는데, 그냥 `F9`로 계속 진행하면 프로그램이 이상하게 종료되는 상황을 마주쳤을 때
- `__except` 블록 안에 있는 코드가 실제로는 정상 실행 경로처럼 보이는(에러 처리가 아닌) CTF 문제를 만났을 때

## 핵심 개념

### first-chance vs second-chance exception
Windows에서 예외가 발생하면 커널은 우선 디버거가 붙어 있는지 확인한다. 디버거가 붙어 있으면 그 예외를 **먼저** 디버거에게 통지한다(first-chance exception). 디버거가 "이 예외는 내가 처리하지 않고 프로그램에게 넘긴다(pass to program)"고 결정해야만 비로소 프로그램의 SEH 체인이 예외를 받아 처리하게 된다. 디버거가 없으면 이 통지 과정 자체가 없고, 예외는 곧바로 프로그램의 SEH 체인으로 전달된다. 이 차이(디버거가 먼저 볼 기회를 갖는가 아닌가)가 SEH 기반 안티디버깅의 핵심 축이다.

### 대표 기법: CloseHandle 무효 핸들 트릭
```c
__try {
    CloseHandle((HANDLE)0xDEADBEEF);
} __except (GetExceptionCode() == STATUS_INVALID_HANDLE
            ? EXCEPTION_EXECUTE_HANDLER
            : EXCEPTION_CONTINUE_SEARCH) {
    // 여기 도달했다는 것 자체가 디버거가 붙어 있다는 뜻
    ExitProcess(1);
}
```
정상 실행(디버거 없음)에서는 `CloseHandle`에 존재하지 않는 핸들을 넘겨도 대부분 조용히 실패(`FALSE` 반환, `GetLastError()`로 `ERROR_INVALID_HANDLE`)만 하고 예외를 던지지 않는다. 하지만 **디버거가 붙어 있으면** 커널이 이 무효 핸들 사용을 `STATUS_INVALID_HANDLE`(`0xC0000008`) 예외로 승격시켜 던진다. 이 예외가 실제로 발생해서 `__except` 블록에 진입한다는 것 자체가 "디버거가 붙어 있다"는 결정적 신호가 된다. 다만 이 트릭은 x64dbg에서는 재현되지 않는 경우가 보고되어 있어(x64dbg가 이 특정 예외 승격 동작을 다르게 처리), 디버거 종류에 따라 결과가 다를 수 있다는 점을 감안해야 한다.

### 대표 기법 2: 예외 체인 무결성 검사
x86에서 SEH 체인은 `FS:[0]`이 가리키는 `EXCEPTION_REGISTRATION_RECORD` 연결 리스트로 구현된다. 일부 디버거 플러그인이나 사용자가 수동으로 이 체인을 조작하면 체인의 마지막이 `0xFFFFFFFF`로 끝나지 않거나 중간 포인터가 깨질 수 있다. 코드가 실행 중에 이 체인을 직접 순회하며 무결성을 검사하는 방식도 넓은 의미의 SEH 기반 안티디버깅에 포함된다.

### 대표 기법 3: 예외를 이용한 흐름 난독화
프로그램이 일부러 (0으로 나누기, 잘못된 메모리 접근 등) 예외를 발생시키고, `__except` 블록 안에 실제 정상 로직의 일부를 숨겨두는 방식이다. 디버거가 이 예외를 자동으로 "처리됨"으로 넘겨버리면(사용자가 `Ignore exception` 설정을 해두지 않으면 디버거가 멈춰버리므로) 정상 흐름이 깨지고, 반대로 디버거 없이 실행되면 예외가 즉시 SEH로 전달되어 `__except` 안의 로직까지 그대로 실행된다. 즉 이 기법은 단순 탐지를 넘어 **정상 실행 자체를 예외 처리 경로에 의존하게 만들어**, 디버거가 예외를 가로채는 순간 프로그램 로직이 아예 실행되지 않게 만드는 더 공격적인 변형이다.

### x86과 x64의 구현 차이
x86의 프레임 기반 SEH(`FS:[0]` 체인)는 x64에서는 테이블 기반 예외 처리(`.pdata`/`.xdata` 섹션, REV-0546 참고)로 완전히 대체되었다. 따라서 `FS:[0]`을 직접 조작하는 저수준 트릭은 x86 전용이며, x64에서는 `__try`/`__except` 컴파일러 매크로를 그대로 쓰거나 `AddVectoredExceptionHandler`(REV-0540) 기반 기법으로 대체되는 경우가 많다.

## 화면/코드에서 보이는 징후
- `CloseHandle`이 유효하지 않아 보이는 상수 값(`0xDEADBEEF` 같은 매직 넘버)과 함께 호출됨.
- `__try`/`__except` 블록(IDA에서는 컴파일러가 생성한 예외 처리 관련 함수 프롤로그/에필로그로 나타남)이 있고, `__except` 필터 표현식에서 `GetExceptionCode()`(또는 `_exception_code()`) 결과를 특정 `STATUS_*` 상수와 비교.
- x64dbg 로그에 `first-chance exception`이 반복적으로 표시되고, `Shift+F9`(pass exception to program)로 넘겨줘야 정상 진행되는 경우.

## 가장 먼저 할 것
`__except` 필터 조건을 먼저 확인한다. `EXCEPTION_EXECUTE_HANDLER`를 무조건 리턴하는 게 아니라 `GetExceptionCode()` 값을 조건부로 검사한다면, 그 비교 대상 예외 코드가 무엇인지부터 파악해야 이 검사가 무엇을 노리는지 알 수 있다.

## 단계별 절차
**1) __except 필터 표현식 찾기**

IDA에서 예외 처리 관련 코드는 함수 앞뒤에 특수한 처리(`.pdata`/SEH3 지원 코드, `_except_handler4` 등)가 붙어 다소 낯설게 보일 수 있다. `GetExceptionCode` 호출 직후의 비교문을 찾는다.

**2) 어떤 예외 코드를 기다리는지 확인**

`STATUS_INVALID_HANDLE`(`0xC0000008`), `STATUS_ACCESS_VIOLATION`(`0xC0000005`), `STATUS_BREAKPOINT`(`0x80000003`) 등 어떤 값과 비교하는지에 따라 어떤 트릭인지(CloseHandle 트릭, 접근 위반 유발, 소프트웨어 BP 관련 등) 구분한다.

**3) x64dbg 예외 처리 옵션 확인**

x64dbg의 `Options` → `Preferences` → `Exceptions` 탭에서 특정 예외를 자동으로 프로그램에 전달(pass)하도록 설정할 수 있다. 기본값이 "예외 발생 시 디버거가 멈춤"이므로, 이 트릭을 재현하려면 `Shift+F9`로 예외를 프로그램에 넘겨야 정상 흐름을 관찰할 수 있다.

**4) 우회 방법 이해**

가장 확실한 우회는 `__except` 필터 비교 분기(예: `jz detected` 또는 조건 자체)를 패치해서 그 경로로 절대 못 들어가게 만드는 것이다. 또는 x64dbg의 예외 옵션에서 해당 예외를 "디버거가 처리하지 않고 조용히 프로그램에 전달"하도록 미리 설정해두면, 애초에 first-chance 통지 차이 자체가 관찰되지 않게 만들 수 있다(ScyllaHide가 이런 예외 관련 처리를 자동화해준다).

## 명령어/단축키
- x64dbg: `Shift+F9`(예외를 프로그램에 전달하고 계속 실행), `Options → Preferences → Exceptions`(특정 예외 자동 전달 설정)
- x64dbg: `Alt+B`(브레이크포인트 창)에서 예외 관련 조건 확인
- IDA: `Debugger → Exceptions`에서 특정 예외 코드 발생 시 자동 처리 방식 설정

## 출력 해석
- `GetExceptionCode()`가 `STATUS_INVALID_HANDLE`을 반환했다는 것은 `CloseHandle` 트릭이 실제로 걸렸다는 뜻이다.
- x64dbg 하단 상태바나 로그 창에 `Access violation`, `Breakpoint`, `Invalid handle` 같은 문구와 함께 예외 코드가 표시되면, 그 코드가 바로 이 검사가 기다리는 값인지 대조해봐야 한다.
- 예외가 발생했는데도 `__except` 블록에 진입하지 않고 프로그램이 그대로 종료된다면, 디버거가 이 예외를 프로그램에 전달하지 않고 자체적으로 먹어버렸을 가능성이 높다 — 예외 전달 설정을 다시 확인해야 한다.

## 흔한 실수
- x64dbg에서 예외가 뜰 때마다 무작정 `F9`(그냥 Run)를 눌러 디버거가 예외를 삼켜버리게 만들고, "이 프로그램은 SEH 트릭이 없다"고 오판하는 것 — 반드시 `Shift+F9`로 예외를 프로그램에 전달해가며 관찰해야 한다.
- `CloseHandle` 무효 핸들 트릭이 모든 디버거에서 동일하게 재현된다고 가정하는 것 — 디버거 구현에 따라 동작이 다를 수 있다.
- SEH와 VEH(REV-0540)를 같은 것으로 혼동하는 것 — SEH는 스택 기반/함수 단위 예외 처리이고 VEH는 프로세스 전역 콜백이라는 점이 다르다.
- x86 전용 `FS:[0]` 조작 트릭을 x64 바이너리에서도 찾으려 하는 것 — x64는 테이블 기반 예외 처리를 쓴다.

## 막혔을 때 다음 체크
- 이 기법의 프로세스 전역 버전이 궁금하다면 → REV-0540 VEH(Vectored Exception Handler) 기반 안티디버깅
- SEH의 기본 개념부터 다시 보고 싶다면 → REV-0134 SEH와 예외 기반 제어 흐름 기초
- 소프트웨어 브레이크포인트가 예외로 나타나는 원리가 궁금하다면 → REV-0537 소프트웨어 브레이크포인트(0xCC) 탐지 기법
- 예외 정보 테이블의 구조가 궁금하다면 → REV-0546 — .pdata 섹션과 x64 예외 처리 정보 읽는 법

## 미니 예제
```c
#include <windows.h>

BOOL SehCloseHandleTrick(void) {
    __try {
        CloseHandle((HANDLE)0xDEADBEEF);
    } __except (GetExceptionCode() == (DWORD)STATUS_INVALID_HANDLE
                ? EXCEPTION_EXECUTE_HANDLER
                : EXCEPTION_CONTINUE_SEARCH) {
        return TRUE; // 디버거 감지
    }
    return FALSE;
}

int main(void) {
    if (SehCloseHandleTrick()) {
        ExitProcess(1);
    }
    printf("Enter flag: ");
    return 0;
}
```
x64dbg로 이 코드를 실행하면 `CloseHandle` 호출 시점에 `first-chance exception - Invalid Handle` 알림이 뜨고, `Shift+F9`로 넘겨야 `__except` 블록(감지 처리)에 도달하는 과정을 직접 관찰할 수 있다.

## 관련 글
- REV-0134 — SEH와 예외 기반 제어 흐름 기초
- REV-0540 — VEH(Vectored Exception Handler) 기반 안티디버깅
- REV-0537 — 소프트웨어 브레이크포인트(0xCC) 탐지 기법
- REV-0546 — .pdata 섹션과 x64 예외 처리 정보 읽는 법
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 출처/검증
- first-chance/second-chance 예외 처리 순서(디버거가 프로그램보다 먼저 예외를 통지받음)는 Microsoft 공식 디버깅 문서(learn.microsoft.com, "Introduction to Windows Debugging" 계열) 기준.
- `CloseHandle`/`NtClose` 무효 핸들 시 `STATUS_INVALID_HANDLE` 예외 승격 트릭은 Check Point "Anti-Debug Tricks — Object Handles" 및 Unprotect Project "CloseHandle, NtClose" 항목에서 확인되는 공개 리버싱 레퍼런스 기준이며, x64dbg에서는 이 트릭이 재현되지 않는다는 점도 해당 자료에서 함께 언급된다(2026-09-08 확인).
- SEH 구조체 및 x86/x64 예외 처리 방식 차이는 Microsoft 공식 문서 및 REV-0134 문서에서 다룬 배경 지식을 전제로 한다.
