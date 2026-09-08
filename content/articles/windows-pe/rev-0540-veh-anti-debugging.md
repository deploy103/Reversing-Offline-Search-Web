---
id: REV-0540
title: "VEH(Vectored Exception Handler) 기반 안티디버깅"
slug: "rev-0540-veh-anti-debugging"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["VEH", "AddVectoredExceptionHandler", "RemoveVectoredExceptionHandler", "PVECTORED_EXCEPTION_HANDLER", "VEH 안티디버깅", "예외 기반 난독화"]
aliases: ["Vectored Exception Handler 안티디버깅", "VEH 트릭", "AddVectoredExceptionHandler 안티디버깅", "예외 벡터 후킹"]
symptom_keywords: ["AddVectoredExceptionHandler를 호출하는 코드가 있다", "함수 시작 부분이 일부러 예외를 던지는 명령어로 시작한다", "정상 로직이 예외 핸들러 콜백 안에 들어있다", "int3나 잘못된 명령어가 함수 여기저기 흩어져 있다", "디버거가 예외를 먼저 잡아채서 프로그램이 멈춘다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`AddVectoredExceptionHandler`로 등록한 VEH(Vectored Exception Handler)는 SEH보다 먼저, 그리고 함수 단위가 아니라 프로세스 전체에 걸쳐 예외를 가로챌 수 있기 때문에, 프로그램이 일부러 예외(잘못된 명령어, 0으로 나누기, `INT3` 등)를 발생시키고 그 처리 여부·타이밍·`CONTEXT` 값을 관찰해 디버거를 탐지하거나, 아예 정상 실행 흐름 자체를 VEH 콜백 안에 숨겨서 디버거로는 정상적으로 따라가기 어렵게 만드는 데 널리 쓰인다.

## 언제 검색해야 하나
- 코드에서 `AddVectoredExceptionHandler`를 호출하는 부분을 발견했는데 등록된 콜백 함수가 하는 일이 단순 에러 처리로 보이지 않을 때
- 함수 여러 곳에서 일부러 잘못된 명령어(`0xCC`, `0x0F0B`(`UD2`) 등)나 0으로 나누기 같은 코드가 나타나고, 이후 실행이 전혀 다른 곳으로 이어지는 것을 발견했을 때
- REV-0539에서 SEH 기반 안티디버깅을 이해했고, "함수 단위가 아니라 프로그램 전체에 적용되는 버전"이 궁금할 때
- x64dbg로 실행하면 예외가 프로그램 코드가 아니라 계속 디버거 메시지로만 뜨고 정상 흐름을 이어갈 수 없는 상황을 마주쳤을 때

## 핵심 개념

### VEH란 무엇인가
`AddVectoredExceptionHandler(ULONG First, PVECTORED_EXCEPTION_HANDLER Handler)`는 프로세스 전역에 예외 콜백을 등록하는 Win32 API다.
```c
LONG CALLBACK MyVeh(PEXCEPTION_POINTERS ExceptionInfo) {
    // ExceptionInfo->ExceptionRecord->ExceptionCode 로 어떤 예외인지 확인
    // ExceptionInfo->ContextRecord 로 레지스터 상태 확인/수정 가능
    return EXCEPTION_CONTINUE_EXECUTION; // 또는 EXCEPTION_CONTINUE_SEARCH
}
AddVectoredExceptionHandler(1, MyVeh); // First=1: 체인 맨 앞에 등록
```
SEH(REV-0134, REV-0539)가 특정 스택 프레임(함수 호출 범위)에 묶여 있는 반면, VEH는 등록되는 순간부터 프로세스 전체·모든 스레드에서 발생하는 예외를 함수 범위와 무관하게 가로챌 수 있다. `First` 인자가 1이면 이미 등록된 다른 VEH나 SEH보다도 먼저 호출되도록 체인 맨 앞에 삽입된다.

### 안티디버깅에 쓰이는 이유
1. **먼저 개입할 수 있다**: VEH는 SEH보다도 먼저 호출되므로, 디버거가 개입하기 전에 프로그램이 스스로 예외를 처리하고 흐름을 바꿀 여지가 생긴다. 다만 디버거가 붙어 있으면 커널 차원에서 디버거에게 먼저 통지되는 first-chance 순서(REV-0539) 자체는 VEH도 피해갈 수 없다 — 그래서 VEH 트릭은 "예외가 최종적으로 어떻게 처리되는가"를 이용하는 방식이 많다.
2. **정상 흐름을 예외 처리 안에 숨길 수 있다**: 프로그램이 코드 곳곳에 일부러 잘못된 명령어(`UD2`, 잘못된 opcode 등)를 심어두고, `EXCEPTION_ILLEGAL_INSTRUCTION` 예외가 발생하면 VEH 콜백이 `ExceptionInfo->ContextRecord->Rip`를 원하는 다음 주소로 직접 바꿔서 실행을 이어간다. 정적 디스어셈블리만 봐서는 "여기서 크래시가 나야 정상인데 실행이 계속된다"는 게 이해되지 않고, VEH 콜백이 `Rip`를 조작한다는 사실을 알아야만 실제 실행 흐름을 재구성할 수 있다. 이는 사실상 **VEH를 이용한 제어 흐름 난독화(control-flow obfuscation)** 기법으로, 순수 탐지보다 한 단계 더 나아간 응용이다.
3. **싱글스텝 트랩과 결합**: `CONTEXT`의 `EFlags`에서 트랩 플래그(TF, bit 8)를 세팅해 강제로 `EXCEPTION_SINGLE_STEP` 예외를 반복 발생시키고, VEH 콜백에서 이를 처리하며 매 명령어 실행 사이에 검사를 끼워 넣는 방식도 있다. 이 경우 디버거로 싱글 스텝하려 하면 VEH가 자기 자신의 싱글스텝 메커니즘과 충돌해 훨씬 이상하게 동작한다.

### VEH vs SEH vs UnhandledExceptionFilter 정리
| 구분 | 등록 범위 | 처리 순서 | 대표 API |
|---|---|---|---|
| SEH | 함수(스택 프레임) 단위 | VEH 다음 | `__try`/`__except` |
| VEH | 프로세스 전역 | SEH보다 먼저(단, first/last 순서에 따라 다름) | `AddVectoredExceptionHandler` |
| UnhandledExceptionFilter | 프로세스 전역, 최종 단계 | 아무도 처리 못 했을 때 마지막 | `SetUnhandledExceptionFilter` |

## 화면/코드에서 보이는 징후
- `AddVectoredExceptionHandler` 호출과 그 두 번째 인자(콜백 함수 포인터)가 Import/코드에서 확인됨.
- 콜백 함수 내부에서 `ExceptionInfo->ExceptionRecord->ExceptionCode`를 여러 `STATUS_*` 상수와 비교하는 분기.
- 콜백 함수가 `ExceptionInfo->ContextRecord->Rip`(x64) 또는 `Eip`(x86) 값을 직접 대입해서 반환하는 코드 — 이것이 있으면 VEH가 실행 흐름을 능동적으로 바꾸는 것.
- 코드 여러 곳에 정상적인 명령어 흐름과 안 맞는 잘못된 opcode(`0x0F 0x0B` = `UD2`)가 흩어져 있음.

## 가장 먼저 할 것
`AddVectoredExceptionHandler` 호출을 찾으면 곧바로 두 번째 인자(콜백 함수 포인터)로 이동해서, 그 함수가 `ExceptionCode`를 어떻게 분기 처리하는지, 그리고 `ContextRecord`를 수정하는지부터 확인한다. `ContextRecord`(특히 `Rip`/`Eip`)를 수정한다면 이건 단순 탐지가 아니라 흐름 제어에 VEH를 쓰고 있다는 뜻이므로 분석 전략을 바꿔야 한다.

## 단계별 절차
**1) 콜백 함수 진입**

IDA에서 `AddVectoredExceptionHandler` 호출부의 두 번째 인자(함수 포인터)를 따라가 콜백 함수 본체를 연다.

**2) 예외 코드 분기 확인**

`EXCEPTION_ACCESS_VIOLATION`(`0xC0000005`), `EXCEPTION_ILLEGAL_INSTRUCTION`(`0xC000001D`), `EXCEPTION_SINGLE_STEP`(`0x80000004`), `EXCEPTION_BREAKPOINT`(`0x80000003`) 등 어떤 코드를 기다리는지 확인한다.

**3) CONTEXT 조작 여부 확인**

콜백이 `ContextRecord->Rip`/`Eip`, `Dr7`, `EFlags` 등을 수정하는지 본다. 수정한다면 예외 발생 지점과 실제 다음 실행 지점이 다르다는 뜻이므로, 예외를 유발하는 명령어 바로 다음 줄이 아니라 VEH가 설정하는 실제 목적지를 별도로 추적해야 한다.

**4) x64dbg로 동적 확인**

VEH 콜백 시작에 브레이크포인트를 걸고, `ExceptionInfo` 구조체(첫 인자, x64에서는 `RCX`)를 따라가 실제 `ExceptionCode`와 `ContextRecord` 값을 관찰한다.
```text
bp <veh_callback_주소>
run
dump rcx        ; EXCEPTION_POINTERS 구조체 확인
```

**5) 우회 방법 이해**

가장 확실한 방법은 실제 예외 유발 지점과 VEH가 설정하는 목적지 주소를 모두 파악해서, IDA에서 그 목적지로 향하는 화살표(수동 xref, 코멘트)를 직접 그려주며 진짜 실행 흐름을 재구성하는 것이다. 탐지 목적으로만 쓰인 경우라면 콜백 내부의 감지 분기를 패치하거나, `RemoveVectoredExceptionHandler`를 강제로 호출해 아예 등록을 해제해버리는 방법도 있다.

## 명령어/단축키
- x64dbg: 콜백 함수 시작에 `bp`, `dump rcx`(x64 첫 인자인 `EXCEPTION_POINTERS*` 확인)
- x64dbg: `Options → Preferences → Exceptions`에서 특정 예외를 자동으로 프로그램에 전달하도록 설정
- IDA: 콜백 함수 안에서 `ContextRecord->Rip`에 해당하는 오프셹(x64 `CONTEXT.Rip`는 오프셋 `0xF8`)에 대입하는 코드를 찾아 실제 점프 목적지 역산

## 출력 해석
- VEH 콜백이 `EXCEPTION_CONTINUE_EXECUTION`(`-1`)을 반환하면 예외가 여기서 완전히 처리되어 프로그램이 (수정된 `CONTEXT` 기준으로) 계속 실행된다는 뜻이다.
- `EXCEPTION_CONTINUE_SEARCH`(`0`)를 반환하면 이 예외가 처리되지 않았으니 다음 핸들러(다른 VEH, SEH, 결국 디버거)에게 넘어간다는 뜻이다.
- 콜백 안에서 `Rip`/`Eip`를 원래 예외 발생 지점보다 훨씬 뒤(또는 전혀 다른 함수)로 세팅한다면, 그 목적지가 바로 "이 예외를 트리거로 삼아 진짜 실행하고 싶었던 코드"다.

## 흔한 실수
- VEH가 SEH를 완전히 대체한다고 생각하는 것 — 둘은 별개의 메커니즘이며 한 프로그램에 둘 다 쓰일 수 있다.
- 예외를 유발하는 명령어 바로 다음 줄을 "다음 실행 지점"이라고 가정하는 것 — VEH가 `Rip`를 조작하면 실제 다음 실행 지점은 전혀 다른 곳일 수 있다.
- `AddVectoredExceptionHandler`의 `First` 인자(체인 순서)를 무시하는 것 — 여러 VEH가 등록되어 있으면 어느 것이 먼저 실행되는지가 분석 순서에 영향을 준다.
- 콜백 함수를 찾고 나서 정적 분석만으로 끝내는 것 — `ContextRecord` 조작 여부는 동적으로 실제 값을 찍어봐야 확실히 알 수 있는 경우가 많다.

## 막혔을 때 다음 체크
- SEH 기반 기법과 first-chance/second-chance 원리를 먼저 확인하고 싶다면 → REV-0539 SEH 기반 안티디버깅 심화
- 싱글스텝 트랩 플래그 관련 세부 사항이 궁금하다면 → REV-0536 하드웨어 브레이크포인트(DR 레지스터) 탐지 기법
- 예외 정보 테이블(.pdata)의 구조가 궁금하다면 → REV-0546 — .pdata 섹션과 x64 예외 처리 정보 읽는 법
- SEH의 가장 기초 개념부터 다시 보고 싶다면 → REV-0134 SEH와 예외 기반 제어 흐름 기초

## 미니 예제
```c
#include <windows.h>

LONG CALLBACK VehHandler(PEXCEPTION_POINTERS info) {
    if (info->ExceptionRecord->ExceptionCode == EXCEPTION_ILLEGAL_INSTRUCTION) {
        // 진짜 로직으로 실행 흐름을 이어감 (UD2 다음 2바이트 스킵)
        info->ContextRecord->Rip += 2;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

int main(void) {
    AddVectoredExceptionHandler(1, VehHandler);
    __asm { ud2 }              // 일부러 잘못된 명령어 실행 → VEH가 가로챔
    printf("Enter flag: ");    // VEH가 Rip를 옮겨줘야 여기까지 도달
    return 0;
}
```
디버거 없이 실행하면 `ud2`에서 예외가 발생하고 VEH가 즉시 `Rip`를 2바이트 뒤로 옮겨 실행을 이어가지만, 디버거로 실행하면 이 예외가 먼저 디버거에 통지되어 "Illegal Instruction" 상태로 멈추므로, 사용자가 `Shift+F9`로 넘겨주지 않는 한 정상 흐름을 볼 수 없다는 차이가 관찰의 핵심이다.

## 관련 글
- REV-0539 — SEH 기반 안티디버깅 심화
- REV-0134 — SEH와 예외 기반 제어 흐름 기초
- REV-0536 — 하드웨어 브레이크포인트(DR 레지스터) 탐지 기법
- REV-0546 — .pdata 섹션과 x64 예외 처리 정보 읽는 법
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 출처/검증
- `AddVectoredExceptionHandler`, `RemoveVectoredExceptionHandler`, `PVECTORED_EXCEPTION_HANDLER` 시그니처와 VEH/SEH 처리 순서는 Microsoft 공식 문서(learn.microsoft.com, "Vectored Exception Handling") 기준.
- `EXCEPTION_POINTERS`/`CONTEXT` 구조체 필드(`ExceptionRecord`, `ContextRecord`, `Rip`)는 `winnt.h` 공식 헤더 정의 기준.
- VEH를 이용한 제어 흐름 난독화 및 안티디버깅 응용 패턴은 공개된 안티디버깅/언패킹 리서치 자료(Check Point Anti-Debug Tricks, 다수의 CTF 리버싱 라이트업)에서 반복적으로 확인되는 일반적 구현 방식을 정리한 것이다(2026-09-08 확인).
