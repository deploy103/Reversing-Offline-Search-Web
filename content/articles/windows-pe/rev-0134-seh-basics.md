---
id: REV-0134
title: "SEH와 예외 기반 제어 흐름 기초"
slug: "rev-0134-seh-basics"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["SEH", "Structured Exception Handling", "try except", "fs:[0]", "예외 처리", "RUNTIME_FUNCTION", "안티디버깅"]
aliases: ["구조적 예외 처리", "SEH 체인", "fs 0 트릭", "예외 기반 제어 흐름"]
symptom_keywords: ["예외가 발생했는데 프로그램이 안 죽는다", "fs:[0]을 조작하는 코드가 보인다", "디버거로 실행하면 흐름이 달라진다", "except 블록으로 갑자기 점프한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
SEH(Structured Exception Handling)는 Windows가 제공하는 예외 처리 메커니즘으로, C의 `__try`/`__except` 문법이 실제로는 스택(x86)이나 별도 테이블(x64)에 "예외가 나면 여기로 가라"는 정보를 등록해두는 코드로 컴파일되며, 이를 알아두지 않으면 디스어셈블리에서 예외를 일부러 일으켜 정상적인 분기처럼 보이지 않게 제어 흐름을 숨기는 안티디버깅/난독화 트릭을 이해할 수 없다.

## 언제 검색해야 하나
- 디스어셈블리에서 `push`로 어떤 함수 주소를 넣고 `mov dword ptr fs:[0], esp` 같은 코드를 봤을 때
- `__except`, `EXCEPTION_POINTERS`, `GetExceptionCode()` 같은 키워드가 디컴파일 결과에 보일 때
- 일부러 0으로 나누거나 잘못된 메모리에 접근한 뒤 프로그램이 죽지 않고 계속 실행되는 것을 봤을 때
- x64 바이너리인데 `.pdata`/`.xdata` 섹션과 `RUNTIME_FUNCTION` 관련 자료를 찾아야 할 때
- "예외를 이용한 안티디버깅"이라는 표현을 CTF 라이트업에서 보고 원리를 찾아볼 때

## 핵심 개념
C/C++에서 `__try { ... } __except(필터식) { ... }` 블록을 쓰면, 컴파일러는 이 블록 안에서 예외(0으로 나누기, 잘못된 메모리 접근, `RaiseException` 호출 등)가 발생했을 때 운영체제가 실행 중인 스레드를 되감아 등록된 핸들러로 제어를 넘기도록 정보를 미리 등록해둔다. 이 등록 방식은 아키텍처마다 완전히 다르다.

**x86(32비트)**: 스레드 정보 블록(TIB, Thread Information Block)의 맨 앞(`fs:[0]`)에는 현재 스레드에 등록된 SEH 핸들러들의 **연결 리스트(체인)**의 머리 주소가 들어있다. 함수가 `__try` 블록에 들어갈 때 컴파일러는 스택에 "다음 레코드 포인터 + 이 블록의 핸들러 함수 주소"로 이루어진 `EXCEPTION_REGISTRATION_RECORD`를 만들고, `fs:[0]`이 이 새 레코드를 가리키도록 갱신한다(즉 체인의 맨 앞에 새로 끼워 넣는다). 함수 프롤로그에서 흔히 보이는 다음 패턴이 바로 이것이다.

```asm
push    offset SEH_handler   ; 이 블록을 보호할 핸들러 함수 주소
push    dword ptr fs:[0]     ; 기존 체인의 head를 다음 레코드로 저장
mov     dword ptr fs:[0], esp  ; 새 레코드를 체인의 head로 등록
```

예외가 발생하면 OS는 `fs:[0]`부터 체인을 따라가며 각 핸들러 함수를 호출해 "이 예외를 처리할 것인가"를 묻고, 처리하겠다는 핸들러를 찾으면 그 핸들러(즉 `__except` 블록)로 실행을 옮긴다.

**x64(64비트)**: x64는 스택 기반 체인을 쓰지 않는다. 대신 PE 파일의 `.pdata` 섹션에 함수별 `RUNTIME_FUNCTION` 항목(함수 시작 RVA, 끝 RVA, 언와인드 정보 RVA)이 정적으로 저장되어 있고, `.xdata` 섹션에 실제 언와인드/예외 처리기 정보가 담겨 있다. 예외가 발생하면 OS가 예외 발생 주소(RIP)를 갖고 `.pdata` 테이블을 검색해 해당 함수의 언와인드 정보를 찾아 핸들러를 실행한다. `fs:[0]` 같은 런타임 조작이 없기 때문에 x64는 x86보다 SEH 체인을 스택에서 직접 조작하는 공격/트릭이 통하지 않는다.

이 메커니즘이 리버싱에서 중요한 이유는, 예외를 **일부러** 일으켜서(예: 0으로 나누기, `int 0x2d`, `int3`, 잘못된 포인터 역참조) 정상적인 `jmp`/`call` 흐름이 아니라 OS 예외 디스패처를 거쳐 원하는 곳으로 점프하도록 만드는 난독화/안티디버깅 기법이 실제로 쓰이기 때문이다. 정적 디스어셈블러는 이런 흐름을 자동으로 연결해서 보여주지 못하므로, "함수가 여기서 갑자기 끊기고 다음 코드가 안 이어지는 것 같다"는 인상을 받게 된다. 또한 디버거가 붙어 있으면 OS는 예외를 프로그램에 전달하기 전에 디버거에게 먼저 알리는데(1차 기회, first-chance exception), 이 타이밍 차이를 이용해 "디버거가 붙어 있으면 예외 처리 흐름이 달라진다"는 점을 감지하는 것도 흔한 안티디버깅 수법이다.

## 화면/코드에서 보이는 징후
- x86 함수 초입에서 `push`로 핸들러 주소를 넣고 `fs:[0]`을 갱신하는 3~4줄짜리 정형화된 패턴
- 디컴파일러(IDA/Ghidra)가 `__except`, `_SEH_prolog`, `_except_handler3/4`, `__C_specific_handler` 같은 이름을 자동으로 붙여주는 경우
- 코드 흐름이 정상적인 조건 분기(`cmp`+`jxx`) 없이 특정 지점에서 뚝 끊기고, 전혀 다른 곳에서 실행이 재개되는 것처럼 보일 때(디버거로 실제 실행해보면 예외 핸들러로 튀는 것을 확인 가능)
- x64 바이너리를 IDA로 열었을 때 `.pdata`/`.xdata` 섹션이 별도로 존재
- x64dbg에서 실행 중 `EXCEPTION_ACCESS_VIOLATION`, `EXCEPTION_INT_DIVIDE_BY_ZERO` 등의 창이 뜨는데, "Pass exception to program"을 하지 않으면 프로그램 동작이 완전히 달라지는 경우

## 가장 먼저 할 것
1. 대상이 x86인지 x64인지부터 확인한다(PE-bear의 Machine 필드 또는 IDA의 아키텍처 표시). 접근 방법이 완전히 다르기 때문이다.
2. x86이라면 문제의 함수 프롤로그에서 `fs:[0]` 조작 코드가 있는지 찾고, 등록되는 핸들러 함수 주소로 바로 이동해서 그 코드를 확인한다.
3. x64라면 `.pdata` 섹션을 훑어 문제의 함수에 대응하는 `RUNTIME_FUNCTION` 항목을 찾고, 거기서 가리키는 언와인드 정보/핸들러 함수를 확인한다. IDA는 대개 이 정보를 자동으로 반영해 함수 옆에 예외 처리기 이름을 붙여준다.

## 단계별 절차
**1) 정적으로 SEH 핸들러 찾기(x86)**
- `push offset handler` 패턴을 찾으면 그 `handler` 주소로 이동한다.
- 핸들러 함수는 보통 `EXCEPTION_RECORD*`, `EstablisherFrame`, `CONTEXT*`, `DispatcherContext` 네 개의 인자를 받는 형태(`EXCEPTION_DISPOSITION` 반환)를 갖는다. IDA가 이 시그니처를 자동 인식하면 편하지만, 안 되면 수동으로 함수 프로토타입을 지정(`Y` 단축키)해서 인자 이름을 붙여준다.

**2) 동적으로 예외 흐름 따라가기(x64dbg)**
- `Options → Preferences → Exceptions`(버전에 따라 `Debug options`)에서 어떤 예외를 디버거가 가로챌지, 프로그램에 전달할지(Pass to application) 설정을 확인한다.
- `F9`로 실행하다 예외가 발생하면 x64dbg가 멈추고 예외 코드와 발생 주소를 보여준다. 여기서 `Shift+F9`(예외를 프로그램에 전달하며 계속 실행)를 누르면 실제로 `__except` 블록으로 넘어가는 과정을 그대로 관찰할 수 있다.
- 예외가 발생한 직후 `RIP`(x64)/`EIP`(x86)가 어디로 이동하는지 계속 스텝하며 따라가면, 핸들러 함수가 실제로 실행되는 지점을 확인할 수 있다.

**3) 안티디버깅 여부 판단**
- 핸들러 안에서 `GetExceptionCode()`가 특정 값(디버거가 개입했을 때와 아닐 때 다른 값)을 비교해 분기하는 코드가 있다면, 이는 디버거 유무를 감지하는 안티디버깅 트릭일 가능성이 크다. 이 경우 x64dbg의 예외 전달 옵션을 정확히 프로그램이 기대하는 대로 맞춰줘야 정상 경로로 진행시킬 수 있다.

## 명령어/단축키
- x64dbg: `Options → Preferences → Exceptions`(예외 전달 설정), `Shift+F9`(예외를 프로그램에 전달하며 실행), `F9`(그냥 실행)
- IDA: `Y`(함수 프로토타입 지정), `X`(핸들러 함수 교차 참조 확인), `Alt+7`(세그먼트에서 `.pdata`/`.xdata` 확인)
- WinDbg(참고용): `!exchain`으로 x86 SEH 체인을 바로 덤프해서 볼 수 있음

## 출력 해석
- x86에서 `fs:[0]` 체인을 따라간 마지막 레코드가 `0xFFFFFFFF`이면 체인의 끝이라는 뜻이고, 그 앞의 각 레코드가 등록된 순서대로(가장 안쪽 `__try`가 체인의 맨 앞) 예외를 먼저 검사받는다.
- x64dbg에서 예외가 "First chance"로 표시되면 디버거가 먼저 통지받은 것이고, 여기서 계속 진행(`Shift+F9`)하면 프로그램의 자체 핸들러(`__except`)로 넘어간다. "Second chance"까지 갔다는 것은 아무도 처리하지 못해 결국 크래시로 이어진다는 뜻이다.
- 예외 필터식(`__except(필터)`)의 반환값이 `EXCEPTION_EXECUTE_HANDLER`(1)면 `__except` 블록 실행, `EXCEPTION_CONTINUE_SEARCH`(0)면 다음 체인으로 넘어감, `EXCEPTION_CONTINUE_EXECUTION`(-1)이면 예외가 발생한 지점으로 그대로 되돌아가 실행을 재개한다는 뜻이다. 이 세 번째 값이 바로 "예외를 이용해 원래 있던 코드가 아닌 다른 곳으로 실행을 재개시키는" 난독화 트릭에서 핵심적으로 쓰인다.

## 흔한 실수
- x86 코드에서 배운 `fs:[0]` 체인 개념을 x64 바이너리에도 그대로 적용하려는 것. x64는 테이블 기반이라 이 패턴 자체가 존재하지 않는다.
- 디버거의 예외 전달 옵션을 잘못 설정해서(예외를 프로그램에 전달하지 않고 디버거가 계속 가로채기만 함) 프로그램이 의도한 `__except` 경로를 절대 타지 못하고 계속 다른 동작을 보이는 것.
- `__except` 필터식이 `EXCEPTION_CONTINUE_EXECUTION`을 반환해서 예외 발생 지점으로 그대로 복귀하는 패턴을 놓치고, "이 코드는 죽었으니 볼 필요 없다"고 넘어가는 것. 이런 경우가 오히려 진짜 로직이 숨어있는 지점일 때가 많다.
- SEH 핸들러 함수를 일반 함수처럼 인자 없이 읽으려다가 프로토타입을 놓쳐서 `EXCEPTION_RECORD*` 등 인자 해석을 잘못하는 것.

## 막혔을 때 다음 체크
- 예외가 TLS 콜백 안에서 발생한다면 → REV-0133(TLS Callback과 main 이전 코드)을 먼저 확인한다. 콜백 자체가 예외 기반 트릭을 쓸 수도 있다.
- 예외 핸들러 안에서 호출되는 API 이름이 낯설다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.
- 예외 핸들러가 암호화/복호화를 수행하는 것 같다면 → REV-0140(Crypt API BCrypt API 흔적 찾기)에서 관련 API 흔적을 찾아본다.

## 미니 예제
x86 디스어셈블리로 다음과 같은 코드를 봤다고 하자.

```asm
sub_401000:
    push    offset filter_and_handler
    push    dword ptr fs:[0]
    mov     dword ptr fs:[0], esp
    xor     eax, eax
    mov     ecx, [eax]        ; 일부러 NULL 포인터 역참조 -> 예외 발생
    ...
filter_and_handler:
    ; EXCEPTION_RECORD*, EstablisherFrame, CONTEXT*, DispatcherContext
    mov     eax, 1            ; EXCEPTION_EXECUTE_HANDLER 반환
    ret
```

이 코드는 `mov ecx, [eax]`에서 일부러 접근 위반(access violation) 예외를 일으킨다. 예외가 발생하면 OS는 `fs:[0]`이 가리키는 체인을 따라 `filter_and_handler`를 찾아 실행하고, 이 함수가 1(`EXCEPTION_EXECUTE_HANDLER`)을 반환하면 `__except` 블록(여기서는 생략된 실제 로직)으로 실행이 넘어간다. 정적 디스어셈블리만 봐서는 `mov ecx, [eax]` 다음 줄이 실제로 실행되는 코드처럼 안 보이지만, 실제로는 이 한 줄이 트리거가 되어 전혀 다른 함수로 제어가 넘어가는 것이다. x64dbg로 `Shift+F9`를 누르며 따라가 보면 이 흐름을 눈으로 직접 확인할 수 있다.

## 관련 글
- REV-0133 — TLS Callback과 main 이전 코드
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0140 — Crypt API BCrypt API 흔적 찾기

## 출처/검증
- SEH 체인의 `fs:[0]` 기반 구조(x86)와 `RUNTIME_FUNCTION`/`.pdata`/`.xdata` 기반 구조(x64)는 Microsoft의 구조적 예외 처리(SEH) 및 PE/COFF 형식 공식 문서 기준이다.
- 예외 필터식 반환값 3종(`EXCEPTION_EXECUTE_HANDLER`, `EXCEPTION_CONTINUE_SEARCH`, `EXCEPTION_CONTINUE_EXECUTION`)의 의미는 Win32 `__except` 문법 공식 문서 기준이다.
- 예외를 이용한 제어 흐름 난독화/안티디버깅 활용 사례는 다수의 리버싱 레퍼런스 및 CTF 라이트업에서 반복적으로 다뤄지는 일반적인 기법이다(2026-09-08 기준 서술).
