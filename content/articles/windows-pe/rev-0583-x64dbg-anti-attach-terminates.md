---
id: REV-0583
title: "x64dbg로 붙였는데 바로 종료(anti-attach)될 때"
slug: "rev-0583-x64dbg-anti-attach-terminates"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, IDA]
keywords: ["anti-attach", "DebugActiveProcess", "NtQueryInformationProcess", "ProcessDebugPort", "ScyllaHide", "self-debugging"]
aliases: ["x64dbg attach 즉시 종료", "디버거 붙이면 프로세스 종료", "anti-attach 우회"]
symptom_keywords: ["attach만 해도 프로세스가 꺼진다", "x64dbg attach 직후 종료", "디버거 붙이자마자 죽는다", "이미 실행 중인 프로세스에 붙일 수 없다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x64dbg로 attach하자마자 프로세스가 종료되면 대부분 프로그램 자체의 안티디버깅 체크 때문이며, ScyllaHide 같은 플러그인으로 대표적인 탐지 API를 먼저 우회해봐야 한다.

## 진단 먼저: attach 실패인가, attach 후 자살(self-terminate)인가
"바로 종료된다"는 증상은 두 가지로 나뉘며 대응이 다르다.

1. **x64dbg 자체가 attach에 실패한다**(File → Attach에서 대상이 목록에서 사라지거나, attach 버튼을 눌러도 아무 반응이 없거나 에러가 뜸) → 대상 프로세스가 이미 다른 디버거(자기 자신이 만든 감시용 자식 프로세스 등)에 의해 "디버깅 중"으로 표시되어 있어서, 프로세스당 하나만 허용되는 디버거 객체 슬롯을 x64dbg가 차지하지 못하는 경우다(self-debugging 기법).
2. **attach는 성공했는데 대상 프로세스가 곧바로 종료된다**(x64dbg 창에는 붙었다고 나오는데 프로세스 목록에서 대상이 사라짐) → 대상이 `NtQueryInformationProcess`나 예외 트릭으로 디버거 존재를 감지하고 스스로 `TerminateProcess`/`ExitProcess`를 호출한 경우다.

둘 다 "anti-attach(안티 어태치)"로 통칭되지만, 1번은 attach 자체를 막는 기법이고 2번은 attach 후 감지해서 죽는 기법이라는 차이가 있다.

## 언제 검색해야 하나
- x64dbg로 이미 실행 중인 프로세스에 File → Attach를 시도했는데 목록에 안 보이거나 attach가 실패할 때
- attach는 성공했다고 나오는데 대상 프로세스가 작업 관리자에서 곧바로 사라질 때
- 처음부터 x64dbg로 실행(`F3`으로 파일 열기)했는데 디스어셈블리가 뜬 직후 프로세스가 종료될 때
- CTF 문제 설명에 "디버거를 감지하면 종료됩니다" 같은 힌트가 있을 때

## 핵심 개념
Windows는 프로세스마다 디버그 포트(디버거가 이벤트를 받는 커널 객체)를 최대 하나만 연결할 수 있다. 이 특성을 이용한 대표 기법이 **셀프 디버깅(self-debugging)**이다 — 프로그램이 시작하자마자 자기 자신의 자식 프로세스(또는 별도 스레드)를 만들어 `DebugActiveProcess`로 부모(또는 원본) 프로세스에 스스로 디버거처럼 붙어버린다. 이렇게 되면 디버그 포트 슬롯이 이미 차 있으므로, 나중에 사람이 x64dbg로 같은 프로세스에 attach하려 하면 `DebugActiveProcess` 호출이 실패하고 x64dbg도 attach할 수 없다.

또 다른 흔한 계열은 **`NtQueryInformationProcess` 기반 탐지**다.
- `ProcessDebugPort`(정보 클래스 7): 디버거가 붙어 있으면 0이 아닌 값을 반환한다.
- `ProcessDebugFlags`(0x1F): 디버거가 붙어 있으면 0을 반환한다(디버깅 중이 아니면 1).
- `ProcessDebugObjectHandle`(0x1E): 디버거가 붙어 있으면 유효한 핸들을 반환하고, `STATUS_PORT_NOT_SET`이면 안 붙어 있는 것이다.

이 외에 **`EXCEPTION_INVALID_HANDLE` 트릭**(존재하지 않는 핸들로 `CloseHandle`을 호출했을 때, 디버거가 붙어 있으면 이 예외가 디버거로 먼저 전달되어 프로그램이 자신의 예외 핸들러 대신 디버거 개입을 감지)도 널리 쓰인다. 이런 체크가 참으로 나오면 프로그램은 `TerminateProcess(GetCurrentProcess(), ...)`를 호출해 즉시 종료한다.

## 화면/코드에서 보이는 징후
- IDA에서 `NtQueryInformationProcess` 임포트를 찾았을 때, 두 번째 인자(ProcessInformationClass)로 `7`(ProcessDebugPort) 또는 `0x1F`(ProcessDebugFlags), `0x1E`(ProcessDebugObjectHandle)가 상수로 들어감
- 프로그램 시작 직후 `CreateProcessW`로 자기 자신을 다시 실행하거나 별도 감시 프로세스를 띄우는 코드
- `CloseHandle`을 의도적으로 잘못된 값(예: `0x1234`처럼 유효하지 않은 핸들)으로 호출하고 그 뒤에 `__try`/`__except`로 예외 발생 여부를 확인하는 코드
- `TerminateProcess`/`ExitProcess` 호출이 정상 종료 경로가 아닌, 위 체크들 직후의 조건 분기에 있음

## 가장 먼저 할 것
attach가 아예 실패하는지, attach 후 종료되는지부터 명확히 구분한다. Process Explorer/작업 관리자로 대상 프로세스를 실행한 직후 새로 생성되는 자식 프로세스가 있는지 먼저 확인한다 — 있다면 self-debugging 기법일 가능성이 매우 높다.

## 단계별 절차
**1) self-debugging(자식 프로세스가 먼저 붙는 경우)**
- Process Explorer(Sysinternals)로 대상 프로그램을 실행하고, 트리 뷰에서 자식 프로세스가 생성되는지 확인한다.
- 자식 프로세스가 보인다면, x64dbg를 **먼저** 실행해 대상 프로그램을 "File → Open File"(처음부터 디버거로 실행)로 열면, 자식이 `DebugActiveProcess`를 시도하기 전에 x64dbg가 먼저 디버그 포트를 차지하게 되어 자식의 attach 시도가 실패할 수 있다.
- 또는 자식 프로세스가 생성되자마자 일시 정지(Process Explorer에서 Suspend)시켜 `DebugActiveProcess` 호출 자체를 막는 방법도 있다.

**2) NtQueryInformationProcess/예외 기반 탐지(attach 후 종료되는 경우)**
- x64dbg 플러그인 **ScyllaHide**(Plugins → ScyllaHide → Options)를 설치/활성화한다. ScyllaHide는 `NtQueryInformationProcess`, `NtSetInformationThread`, `NtQuerySystemInformation`, `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, PEB `BeingDebugged`/`NtGlobalFlag` 등 유저모드에서 확인 가능한 디버거 흔적을 후킹해 "디버거 없음"으로 위장해준다.
- ScyllaHide로도 안 되면 프로그램이 후킹을 우회하는 방식(직접 syscall)으로 확인하는 것일 수 있으므로, 커널 모드 후킹 드라이버인 **TitanHide**를 함께 사용하는 것을 고려한다.
- `EXCEPTION_INVALID_HANDLE` 트릭이 의심되면 x64dbg의 Options → Preferences → Exceptions에서 해당 예외를 "프로그램에 전달하지 않고 무시" 하도록 설정을 조정해본다.

**3) 원인 함수를 직접 찾아 패치**
- IDA로 정적 분석해 `NtQueryInformationProcess` 교차 참조를 따라가 탐지 함수를 특정하고, 반환값을 검사하는 조건 분기(`jnz`/`jz`)를 x64dbg에서 NOP 처리하거나 항상 "디버거 없음" 경로를 타도록 패치하는 방법도 있다(교육/CTF 목적에 한함).

## 명령어/단축키
- x64dbg: Plugins → ScyllaHide → Options(후킹 항목 체크), Options → Preferences → Exceptions
- Process Explorer: 트리 뷰로 자식 프로세스 확인, 우클릭 → Suspend
- IDA: `X`(교차 참조로 `NtQueryInformationProcess` 사용처 찾기), `F5`(디컴파일)

## 출력 해석
- ScyllaHide 적용 후에도 프로세스가 죽는다면, 탐지 방식이 유저모드 API 후킹으로 막을 수 없는 방식(직접 syscall, 커널 드라이버 기반)일 가능성이 높으므로 TitanHide 같은 커널 레벨 대응이 필요하다.
- Process Explorer에서 자식 프로세스가 생성되자마자 사라진다면(짧게 실행되고 종료), self-debugging 목적의 감시 프로세스였을 가능성이 크다.

## 흔한 실수
- ScyllaHide를 설치만 하고 옵션 체크박스를 하나도 활성화하지 않은 채 "효과가 없다"고 결론짓는 것 — Options 창에서 필요한 후킹 항목을 직접 체크해야 한다.
- attach 방식만 반복 시도하고, "처음부터 디버거로 실행"(File → Open File)은 시도해보지 않는 것 — self-debugging은 attach 시점과 시작 시점의 방어 순서가 다르므로 두 방식을 모두 시도해야 한다.
- 하나의 탐지 기법을 우회했다고 끝났다고 착각하는 것 — 실전에서는 여러 탐지 기법이 동시에(중복으로) 걸려 있는 경우가 흔하다.
- 셀프 디버깅 자식 프로세스를 그냥 강제 종료(kill)해버려서, 그 자식이 원래 하던 다른 정상 기능(예: 라이선스 체크가 아닌 별도 작업)까지 함께 망가뜨리는 것 — 가능하면 attach 타이밍만 조정하는 방법을 먼저 시도한다.

## 막혔을 때 다음 체크
- 여러 안티디버깅 기법이 섞여 있어 뭐부터 봐야 할지 모르겠다면 → REV-0240(디버거에서 갑자기 종료될 때 체크리스트) 참고
- IsDebuggerPresent/PEB 기반의 더 기본적인 체크부터 확인하고 싶다면 → REV-0130(IsDebuggerPresent 안티디버깅 식별), REV-0132(PEB BeingDebugged 검사 이해) 참고
- attach 자체가 안 되는 게 아니라 파일 로드부터 안 된다면 → REV-0582(x64dbg가 실행 파일을 로드하지 못할 때) 참고

## 미니 예제
```
1) x64dbg attach 직후 프로세스가 즉시 종료됨
2) Plugins → ScyllaHide → 활성화 (IsDebuggerPresent, NtQueryInformationProcess 등 후킹)
3) 다시 attach → 정상적으로 유지됨
→ 표준 API 기반 안티디버깅이었다고 결론
```

## 관련 글
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0132 — PEB BeingDebugged 검사 이해
- REV-0582 — x64dbg가 실행 파일을 로드하지 못할 때
- REV-0584 — 디버거에서 실행하면 다른 분기를 타는 것처럼 보일 때

## 출처/검증
- `NtQueryInformationProcess`의 `ProcessDebugPort`(7), `ProcessDebugFlags`(0x1F), `ProcessDebugObjectHandle`(0x1E) 정보 클래스와 그 반환 의미는 공개된 Windows 내부 구조 문서 및 다수의 안티디버깅 리버싱 레퍼런스에서 공통적으로 확인되는 내용이다.
- `EXCEPTION_INVALID_HANDLE` 기반 탐지와 self-debugging(자식 프로세스의 `DebugActiveProcess`) 기법은 공개된 안티디버깅 기법 정리 자료(예: 다수의 리버싱 교육 자료 및 오픈소스 anti-attach 예제 프로젝트)에서 공통적으로 다뤄지는 잘 알려진 패턴이다.
- ScyllaHide/TitanHide는 x64dbg 생태계에서 널리 쓰이는 오픈소스 안티안티디버깅 플러그인/드라이버로, 각 프로젝트의 공개 문서를 기준으로 기능을 서술했다(2026-09-08 기준).
