---
id: REV-0529
title: "Windows 안티디버깅 기법 종류 빠른 참조표"
slug: "rev-0529-windows-anti-debugging-techniques-quickref"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["안티디버깅", "anti-debugging", "IsDebuggerPresent", "NtQueryInformationProcess", "타이밍 체크", "PEB BeingDebugged", "안티디버깅 기법 목록"]
aliases: ["안티디버깅 기법 사전", "안티디버깅 종류표", "안티디버깅 체크리스트", "디버거 탐지 기법 목록"]
symptom_keywords: ["안티디버깅이 몇 종류나 있는지 모르겠음", "이 바이너리가 어떤 안티디버깅을 쓰는지 모르겠음", "IsDebuggerPresent 말고 다른 안티디버깅 방법이 궁금함", "타이밍 기반 안티디버깅이 뭔지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows 바이너리의 안티디버깅 기법은 크게 "API 호출로 물어보기", "플래그/구조체 직접 읽기", "타이밍 측정하기", "예외/하드웨어 이용하기" 네 갈래로 나뉘며, 어떤 바이너리를 처음 열었을 때 이 표를 훑어 어떤 유형에 해당하는 코드가 있는지 먼저 분류하면 개별 기법을 하나씩 새로 찾아 헤매지 않고 효율적으로 분석을 시작할 수 있다.

## 언제 검색해야 하나
- 처음 보는 바이너리에서 디버거로 열면 동작이 달라지는 것 같은데, 정확히 어떤 방식의 안티디버깅인지 감이 안 잡힐 때
- Import Table에 익숙한 `IsDebuggerPresent` 외에 낯선 함수 이름들이 여러 개 보여서 이들이 안티디버깅과 관련 있는지 빠르게 판단하고 싶을 때
- CTF 문제 설명에 "안티디버깅이 걸려있다"고만 적혀 있고 구체적인 기법은 스스로 찾아야 할 때, 어디부터 확인해야 할지 체크리스트가 필요할 때
- 특정 안티디버깅 기법(예: 타이밍 체크)에 대한 더 깊은 문서로 넘어가기 전에 전체 지형을 먼저 파악하고 싶을 때

## 핵심 개념

### 분류 1: API 호출 기반(가장 흔함, 탐지 쉬움)
Win32/Native API를 호출해서 결과를 확인하는 방식. Import Table에 함수 이름이 그대로 남아있는 경우가 많아 정적 분석만으로도 발견하기 쉽다.

| 함수 | 확인 방식 | 관련 문서 |
|---|---|---|
| `IsDebuggerPresent` | PEB `BeingDebugged` 플래그를 반환값으로 | REV-0130 |
| `CheckRemoteDebuggerPresent` | 포인터 인자에 결과를 채움 | REV-0131 |
| `NtQueryInformationProcess` | `ProcessDebugPort`, `ProcessDebugFlags`, `ProcessDebugObjectHandle` 등 다양한 정보 클래스로 질의 | REV-0533 |
| `NtSetInformationThread` | `ThreadHideFromDebugger`로 현재 스레드를 디버거의 이벤트 알림 대상에서 제외 | REV-0534 |
| `OutputDebugStringA/W` | 디버거 유무에 따라 다른 동작(예외 발생 여부, `GetLastError` 값)을 이용 | REV-0535 |

### 분류 2: 플래그/구조체 직접 읽기(은밀함)
API를 전혀 호출하지 않고 메모리(PEB, TEB 등)를 직접 읽어 API 후킹으로는 막기 어려운 방식.

| 대상 | 확인 위치 | 비고 |
|---|---|---|
| `PEB.BeingDebugged` | `PEB+0x02`(x64 기준, 오프셋은 아키텍처별로 다름) | `IsDebuggerPresent`가 내부적으로 읽는 것과 동일한 값을 코드가 직접 읽음 (REV-0132) |
| `PEB.NtGlobalFlag` | 디버거로 실행된 프로세스는 힙 관련 특정 플래그가 세팅됨 | `FLG_HEAP_ENABLE_TAIL_CHECK` 등과 조합해 힙 헤더 패턴으로 간접 탐지 |
| 힙 청크 헤더 | 디버거 하에서 실행된 힙은 특수 채움 바이트(`0xABABABAB` 등) 패턴이 다르게 나타남 | 상대적으로 드물게 쓰임 |

### 분류 3: 타이밍 측정(디버깅으로 인한 지연 감지)
정상 실행과 디버깅 중 실행의 속도 차이(브레이크포인트, 싱글스텝으로 인한 지연)를 이용.

| 방법 | 원리 |
|---|---|
| `RDTSC` 명령어 두 번 호출 후 사이클 차이 비교 | 디버깅 중에는 명령어 사이 지연이 비정상적으로 커짐 |
| `GetTickCount`/`QueryPerformanceCounter` 두 지점 시간차 측정 | 같은 원리를 API 레벨에서 구현 |
| `Sleep` 호출 전후 실제 경과 시간 비교 | 디버거로 일시정지된 시간까지 포함되면 예상보다 훨씬 길게 측정됨 |

타이밍 기반 기법은 오탐(false positive) 가능성이 있어(느린 컴퓨터, 백그라운드 부하 등) 단독보다는 보조 수단으로 자주 쓰인다.

### 분류 4: 예외/하드웨어 이용
CPU 예외나 하드웨어 브레이크포인트 자체를 검사 도구로 활용.

| 방법 | 원리 |
|---|---|
| `int3`(`0xCC`) 트랩 심어두기 | 디버거가 없으면 처리되지 않고 그냥 크래시하거나, 디버거가 있으면 이 예외를 소비해 정상 흐름을 이어가도록 설계 |
| 하드웨어 브레이크포인트(디버그 레지스터 `DR0`~`DR7`) 검사 | `GetThreadContext`로 자신의 디버그 레지스터 값을 읽어 0이 아니면(브레이크포인트 설정됨) 디버거 존재로 판단 |
| SEH(구조적 예외 처리)를 이용한 트릭 | 의도적으로 예외를 일으키고, 그 예외가 디버거에 의해 먼저 가로채지는지 프로그램의 핸들러로 바로 넘어가는지로 판단 |

### 왜 여러 기법을 조합해서 쓰는가
단일 기법은 후킹이나 패치로 비교적 쉽게 무력화되므로, 실전 상용 프로텍터나 정교한 CTF 문제는 위 네 분류 중 서로 다른 원리를 최소 2~3개 조합해서 배치하는 경우가 많다. 한 가지를 우회했다고 안심하지 말고 나머지 분류도 확인하는 습관이 필요하다.

## 화면/코드에서 보이는 징후
- Import Table에서 `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, `NtQueryInformationProcess`, `NtSetInformationThread`, `OutputDebugStringA/W` 중 하나 이상이 보임.
- `rdtsc` 명령어(디스어셈블리에서 `0F 31` 바이트)가 반복적으로 등장.
- `PEB`를 가리키는 세그먼트 레지스터 접근(`mov rax, gs:[0x60]`(x64) 또는 `mov eax, fs:[0x30]`(x86))이 API 호출 없이 나타남.
- 코드 흐름 어딘가에 이유 없어 보이는 `int3` 바이트나, `GetThreadContext` 호출 후 `Dr0`~`Dr7` 필드를 검사하는 코드가 있음.

## 가장 먼저 할 것
Import Table을 먼저 훑어 분류 1(API 기반)에 해당하는 함수 이름이 있는지 확인한다. 이것이 가장 흔하고 발견하기 쉬우므로 우선순위가 높다. 없다면 문자열/디스어셈블리에서 `rdtsc`나 PEB 직접 접근 패턴(분류 2, 3)을 찾는다.

## 단계별 절차

**1) Import Table 스캔**

PE-bear/IDA Imports 창에서 위 표에 나온 함수 이름들을 하나씩 검색한다.

**2) 발견된 함수마다 xref로 호출 지점 확인**

각 함수를 `X`(xref)로 호출 지점을 모두 찾아 표시해둔다.

**3) 문자열/디스어셈블리에서 API 없는 패턴 찾기**

`rdtsc`, `gs:[0x60]`/`fs:[0x30]`(PEB 직접 접근) 같은 패턴을 IDA의 텍스트 검색(`Alt+T`)이나 디스어셈블리 스크롤로 찾는다.

**4) 발견된 기법을 분류표에 매핑**

각 발견 지점을 4개 분류 중 어디에 속하는지 표시해두면, 이후 우회 전략을 세울 때(예: API 기반은 후킹으로, 타이밍 기반은 API 패치로) 접근 방식을 구분해서 계획할 수 있다.

**5) 조합 여부 확인**

한 가지만 찾고 끝내지 말고, 나머지 세 분류도 훑어서 다중 방어가 걸려 있는지 확인한다.

## 명령어/단축키
- IDA: `Alt+T`(텍스트 검색)로 `rdtsc`, `NtQueryInformationProcess` 등 검색, Imports 창에서 이름별 검색
- x64dbg: 우클릭 → `Search for` → `All Modules` → `Intermodular calls`로 안티디버깅 관련 API 호출부 한 번에 나열
- x64dbg 플러그인 ScyllaHide: 알려진 다수의 안티디버깅 기법을 자동으로 우회해주는 플러그인(설치 시 `Plugins` 메뉴에서 설정)

## 출력 해석
- 여러 함수가 동시에 Import Table에 있다면 레이어드 디펜스일 가능성이 높으므로, 하나를 우회해도 프로그램이 여전히 이상하게 동작하면 다른 분류를 의심한다.
- `rdtsc`가 반복되지만 그 사이 연산이 아주 단순하다면(단순 산술 몇 개), 그 자체로 타이밍 체크임을 강하게 시사한다.
- API 함수가 하나도 안 보이는데 여전히 디버거 감지가 의심된다면, 분류 2(PEB 직접 읽기)나 분류 4(하드웨어 브레이크포인트 검사)일 가능성을 우선 조사한다.

## 흔한 실수
- `IsDebuggerPresent` 하나만 찾고 다른 기법이 없다고 단정하는 것 — 조합 사용이 흔하다.
- 타이밍 기반 기법을 발견하고 바로 "이건 오탐일 것"이라며 무시하는 것 — 실제 CTF 문제에서 의도적으로 사용되는 경우도 많다.
- `rdtsc`가 보이면 무조건 안티디버깅이라고 단정하는 것 — 성능 측정, 난수 시드 생성 등 다른 목적으로도 쓰인다. 주변 코드(측정 후 비교/분기 여부)를 함께 봐야 한다.
- 각 기법의 우회 방법을 이 문서에서 바로 찾으려 하는 것 — 이 문서는 분류와 식별까지만 다루며, 개별 우회 개념은 REV-0531~REV-0535 등 각 문서에서 별도로 다룬다.

## 막혔을 때 다음 체크
- API 기반 기법 중 가장 기본적인 것부터 자세히 보고 싶다면 → REV-0130 IsDebuggerPresent 안티디버깅 식별
- PEB를 직접 읽는 방식이 궁금하다면 → REV-0132 PEB BeingDebugged 검사 이해
- `NtQueryInformationProcess` 기반 기법이 궁금하다면 → REV-0533 NtQueryInformationProcess로 하는 안티디버깅
- 스레드 단위로 디버거를 회피하는 기법이 궁금하다면 → REV-0534 NtSetInformationThread ThreadHideFromDebugger 기법

## 미니 예제
```asm
; 타이밍 기반(분류 3) 예시
rdtsc                 ; EDX:EAX = 시작 타임스탬프
mov  [start_lo], eax
mov  [start_hi], edx
call some_function     ; 실제로는 별 의미 없는 짧은 코드
rdtsc                  ; 다시 측정
sub  eax, [start_lo]
cmp  eax, 0x10000       ; 임계값 비교 - 디버거 중이면 이 값을 훌쩍 넘김
ja   debugger_detected
```

## 관련 글
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0131 — CheckRemoteDebuggerPresent 식별
- REV-0132 — PEB BeingDebugged 검사 이해
- REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- REV-0534 — NtSetInformationThread ThreadHideFromDebugger 기법
- REV-0535 — OutputDebugString을 이용한 안티디버깅 탐지

## 출처/검증
- 안티디버깅 기법 분류(API/구조체/타이밍/예외-하드웨어)는 Microsoft 공식 API 문서 및 CTF/리버싱 커뮤니티에서 널리 통용되는 안티디버깅 레퍼런스(예: "Anti-Debug Tricks" 계열 문헌) 기준으로 정리(2026-09-08 확인). 개별 API 시그니처는 각 하위 문서(REV-0130~REV-0135)에서 별도 검증.
