---
id: REV-0532
title: "CheckRemoteDebuggerPresent 우회 실습 개념"
slug: "rev-0532-checkremotedebuggerpresent-bypass-concept"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CheckRemoteDebuggerPresent 우회", "pbDebuggerPresent 패치", "출력 인자 조작", "x64dbg 메모리 수정", "안티디버깅 우회"]
aliases: ["CheckRemoteDebuggerPresent 패치", "CheckRemoteDebuggerPresent bypass", "pbDebuggerPresent 조작", "원격 디버거 확인 우회"]
symptom_keywords: ["CheckRemoteDebuggerPresent를 우회하고 싶은데 EAX만 바꿔서는 안 됨", "pbDebuggerPresent가 가리키는 값을 어떻게 바꾸는지 모르겠음", "IsDebuggerPresent는 우회했는데 여전히 감지됨", "출력 인자로 결과를 받는 함수는 어떻게 후킹하는지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CheckRemoteDebuggerPresent`는 결과를 함수 반환값이 아니라 **두 번째 인자가 가리키는 메모리**에 채우기 때문에, `IsDebuggerPresent`처럼 `EAX`만 0으로 바꾸는 방식으로는 우회되지 않으며 반드시 그 출력 인자(`pbDebuggerPresent`)가 가리키는 스택 주소의 값을 직접 0으로 덮어써야 한다는 점이 이 API 우회의 핵심 차이다.

## 언제 검색해야 하나
- REV-0131에서 `CheckRemoteDebuggerPresent` 호출과 두 번째 인자(출력 포인터)까지는 확인했는데, 실제로 그 결과를 속여서 분석을 계속 진행하고 싶을 때
- `IsDebuggerPresent`를 우회하는 방식(REV-0531, 반환값 EAX 조작)을 그대로 적용했는데 왜 안 통하는지 이해가 안 될 때
- x64dbg에서 함수 호출 이후 스택 변수 값을 직접 수정하는 절차가 낯설 때
- 출력 인자(포인터로 결과를 반환하는 형태)를 갖는 다른 Win32 API를 우회할 때도 적용할 수 있는 일반적인 접근법을 배우고 싶을 때

## 핵심 개념

### 왜 EAX 조작이 통하지 않는가
`CheckRemoteDebuggerPresent`의 함수 시그니처를 다시 보면 다음과 같다.
```c
BOOL CheckRemoteDebuggerPresent(
    HANDLE hProcess,
    PBOOL  pbDebuggerPresent
);
```
이 함수 자체의 반환값(`BOOL`, `EAX`에 담김)은 **API 호출 자체가 성공했는지**를 나타낼 뿐이다. 실제 "디버거가 있는가/없는가"라는 진짜 결과는 두 번째 인자 `pbDebuggerPresent`가 가리키는 메모리 주소에 별도로 기록된다. 따라서 `Ctrl+F9`(Execute till return) 이후 `EAX`를 0으로 바꿔봐야, 이후 코드가 실제로 검사하는 것은 `EAX`가 아니라 그 스택 변수의 값이므로 아무 효과가 없다.

### 우회의 두 가지 접근
1. **호출 이후 출력 값을 직접 덮어쓰기** — 함수가 정상적으로 실행되어 스택 변수에 `1`을 써넣게 놔둔 뒤, `ret` 직후(또는 그 값을 다시 읽는 `movzx eax, byte ptr [...]` 명령 직전) 그 스택 주소의 값을 `0`으로 바꾼다.
2. **함수 진입 시점에 인자 자체를 가로채 무력화** — 함수가 시작하기 전에 두 번째 인자(`RDX`가 가리키는 주소)를 미리 확인해두고, 함수가 끝난 뒤 그 주소의 값을 0으로 강제하는 조건부 브레이크포인트를 설정해 자동화한다.

두 방법 모두 결국 "출력 인자가 가리키는 메모리"를 대상으로 삼는다는 점이 `IsDebuggerPresent` 우회와 근본적으로 다른 부분이다.

### 이 패턴이 왜 중요한가 — 일반화
Win32 API 중에는 반환값이 아니라 포인터 인자를 통해 실제 결과를 돌려주는 함수가 매우 많다(`GetExitCodeProcess`, `PeekMessage`, 각종 `Get*Info` 계열 등). `CheckRemoteDebuggerPresent`를 통해 "이 함수의 진짜 결과가 어디에 저장되는지 파라미터 목록에서 먼저 파악한 뒤, 그 위치를 직접 조작한다"는 접근법을 익혀두면, 다른 출력 인자 기반 API를 우회하거나 후킹할 때도 동일한 사고방식을 적용할 수 있다.

### PEB와의 관계는 약함
`IsDebuggerPresent`는 PEB `BeingDebugged`를 그대로 반환하므로 PEB 패치만으로 함께 무력화되지만, `CheckRemoteDebuggerPresent`는 문서화되지 않은 내부 구현에서 커널에 질의하는 방식으로 알려져 있어(정확한 내부 시스템 콜은 마이크로소프트가 공식적으로 문서화하지 않음), PEB의 `BeingDebugged`만 0으로 패치해도 이 API의 결과에는 영향이 없을 수 있다. 즉 REV-0531에서 다룬 PEB 패치와 이 문서의 우회는 서로 별개로 적용해야 하는 경우가 많다.

### ScyllaHide가 처리하는 범위
ScyllaHide 같은 플러그인은 `CheckRemoteDebuggerPresent`도 알려진 우회 대상 목록에 포함하는 경우가 많아, 옵션에서 이 항목을 켜두면 수동으로 스택 값을 조작하지 않아도 자동으로 처리된다. 다만 플러그인이 어떤 버전의 API/OS를 기준으로 후킹을 구현했는지에 따라 최신 Windows에서는 동작하지 않을 수도 있으므로, 수동 방법을 함께 알아두는 것이 안전하다.

## 화면/코드에서 보이는 징후
- x64dbg에서 `CheckRemoteDebuggerPresent`를 브레이크포인트로 잡고 `EAX`를 0으로 바꿨는데도 프로그램이 여전히 감지 분기로 빠짐.
- 디스어셈블리에서 `call CheckRemoteDebuggerPresent` 직후 `movzx eax, byte ptr [rbp-0x4]`(또는 유사한 스택 오프셋) 형태로 별도의 메모리 읽기가 이어짐 — 바로 이 줄이 진짜 검사 지점이다.
- 두 번째 인자가 `lea rdx, [rbp-0x4]`처럼 스택 변수 주소를 만드는 코드로 준비됨.

## 가장 먼저 할 것
REV-0131에서 확인한 두 번째 인자(`pbDebuggerPresent`)의 스택 오프셋을 다시 확인한다. 이 주소가 이번 우회 작업의 목표 지점이며, `EAX`가 아니라 이 주소의 1바이트 값을 조작해야 한다.

## 단계별 절차

**1) 호출 지점과 인자 주소 확인**

IDA 또는 x64dbg에서 `call CheckRemoteDebuggerPresent` 직전의 `lea rdx, [주소]` 명령을 찾아, `pbDebuggerPresent`가 가리키는 스택 오프셋을 기록해둔다.

**2) 함수 실행 전 브레이크포인트 설정**

x64dbg에서 `bp CheckRemoteDebuggerPresent`로 브레이크포인트를 건다.

**3) RDX 값을 별도로 메모**

브레이크포인트에 도달하면 Registers 창에서 `RDX`(두 번째 인자, 즉 결과를 쓸 실제 주소)를 확인하고 적어둔다.

**4) 함수 실행 완료까지 진행**

`Ctrl+F9`(Execute till return)로 함수가 끝날 때까지 실행한다. 이 시점에는 이미 스택 변수에 `1`(디버거 있음)이 쓰인 상태다.

**5) 해당 주소의 값을 직접 수정**

Dump 창에서 `Ctrl+G`(Go to)로 3단계에서 메모한 주소로 이동한 뒤, 그 1바이트 값을 `00`으로 수정한다(우클릭 → `Edit` 또는 직접 더블클릭 후 입력).

**6) 계속 실행하며 결과 확인**

`F9`로 계속 실행해, 이후 `movzx`/`test`로 이 값을 읽는 코드가 이제 "디버거 없음" 경로로 빠지는지 확인한다.

**7) 반복 호출 자동화**

호출이 여러 번 일어난다면, `ret` 직전에 걸어둔 브레이크포인트의 Command에 해당 스택 오프셋을 0으로 쓰는 명령(예: x64dbg 스크립트로 `mov [rsp+0x30], 0` 형태의 메모리 쓰기 명령을 조건부로 실행)을 등록해 자동화하거나, ScyllaHide의 해당 항목을 활성화한다.

## 명령어/단축키
- x64dbg: `bp CheckRemoteDebuggerPresent`, `Ctrl+F9`(Execute till return), `Ctrl+G`(Dump 창에서 주소로 이동)
- x64dbg: Dump 창에서 바이트 더블클릭 또는 우클릭 → `Edit`로 메모리 값 직접 수정
- x64dbg: `Plugins > ScyllaHide > Settings`에서 `CheckRemoteDebuggerPresent` 관련 옵션 확인

## 출력 해석
- 스택 주소의 값을 0으로 바꾼 뒤에도 여전히 감지된다면, 주소를 잘못 기록했거나(RDX가 아니라 다른 레지스터를 참조), 이 값을 읽는 코드가 한 곳이 아니라 여러 곳에 흩어져 있을 가능성을 의심한다.
- `GetCurrentProcess()`의 반환값이 아닌 다른 값이 첫 번째 인자로 들어간다면(실제 프로세스 핸들), 이 검사가 자기 자신이 아니라 자식/부모 프로세스를 대상으로 하고 있다는 뜻이므로 분석 대상 프로세스 관계를 다시 파악해야 한다.
- 프로그램이 패치 이후 크래시한다면, 스택 오프셋을 잘못 계산했거나 다른 지역 변수를 실수로 덮어썼을 가능성이 크므로 오프셋을 다시 확인한다.

## 흔한 실수
- `IsDebuggerPresent` 우회와 똑같이 `EAX`만 조작하고 끝내는 것 — 이 API에서는 아무 효과가 없다.
- `pbDebuggerPresent` 주소를 함수 진입 전(`RDX` 초기값)이 아니라 진입 후 임의의 다른 레지스터 값으로 착각해 잘못된 주소를 수정하는 것.
- 여러 호출 지점 중 하나만 패치하고 나머지를 놓쳐서 "우회했는데도 여전히 걸린다"고 혼란스러워하는 것 — `X`(xref)로 전체 호출 지점을 먼저 확인해야 한다.
- 이 우회를 라이선스가 있는 상용 소프트웨어에 적용하는 것 — 이 문서는 CTF/워게임/교육 목적의 방어적 리버싱 범위 내에서만 다룬다.

## 막혔을 때 다음 체크
- 이 API의 인자 구조와 정상 호출 패턴을 다시 확인하고 싶다면 → REV-0131 CheckRemoteDebuggerPresent 식별
- `IsDebuggerPresent`의 더 단순한 우회 절차와 비교하고 싶다면 → REV-0531 IsDebuggerPresent 우회 실습 개념과 한계
- 이 API를 우회했는데도 여전히 감지된다면 다른 기법 목록을 확인하고 싶을 때 → REV-0529 Windows 안티디버깅 기법 종류 빠른 참조표
- `NtQueryInformationProcess` 기반의 더 깊은 검사가 궁금하다면 → REV-0533 NtQueryInformationProcess로 하는 안티디버깅

## 미니 예제
```text
원본 코드 (x64):
call GetCurrentProcess          ; rax = -1
mov  rcx, rax
lea  rdx, [rbp-0x4]             ; pbDebuggerPresent 주소 = rbp-0x4
call CheckRemoteDebuggerPresent
movzx eax, byte ptr [rbp-0x4]
test eax, eax
jne  detected_branch

x64dbg 조작 순서:
1) bp CheckRemoteDebuggerPresent
2) F9 -> 브레이크포인트 도달, Registers에서 RDX 값(= rbp-0x4의 실제 주소) 확인
3) Ctrl+F9 -> 함수 종료 직후까지 진행 (이 시점 [rbp-0x4] = 1)
4) Dump 창에서 Ctrl+G로 해당 주소 이동, 값 00으로 수정
5) F9 -> movzx가 0을 읽음 -> test 결과 ZF=1 -> jne 발생 안 함 -> 정상 경로 진행
```

## 관련 글
- REV-0131 — CheckRemoteDebuggerPresent 식별
- REV-0531 — IsDebuggerPresent 우회 실습 개념과 한계
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표
- REV-0533 — NtQueryInformationProcess로 하는 안티디버깅

## 출처/검증
- `CheckRemoteDebuggerPresent` 함수 시그니처와 출력 인자 방식은 Microsoft 공식 문서(learn.microsoft.com, "CheckRemoteDebuggerPresent function") 기준. 내부적으로 커널 질의를 거친다는 점은 공식 문서에 명시되어 있지 않은 통용 리버싱 지식이며, x64dbg 메모리 편집/스크립팅 절차는 x64dbg 공식 문서 기준(2026-09-08 확인).
