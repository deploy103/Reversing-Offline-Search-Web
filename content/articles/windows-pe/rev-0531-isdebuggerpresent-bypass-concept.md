---
id: REV-0531
title: "IsDebuggerPresent 우회 실습 개념과 한계"
slug: "rev-0531-isdebuggerpresent-bypass-concept"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["IsDebuggerPresent 우회", "PEB BeingDebugged 패치", "x64dbg TitanHide", "ScyllaHide", "안티디버깅 우회", "패치 바이트"]
aliases: ["IsDebuggerPresent 패치", "IsDebuggerPresent bypass", "안티디버깅 우회 실습", "BeingDebugged 패치 방법"]
symptom_keywords: ["IsDebuggerPresent를 우회하고 싶은데 방법을 모르겠음", "call 명령 결과를 강제로 0으로 만들고 싶음", "x64dbg가 IsDebuggerPresent 때문에 걸림", "ScyllaHide를 써야 하는지 직접 패치해야 하는지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`IsDebuggerPresent`를 우회하는 방법은 근본적으로 "PEB의 `BeingDebugged` 플래그를 0으로 되돌리기"와 "함수 호출 자체나 결과 검사 분기를 코드/디버거 레벨에서 조작하기" 두 갈래로 나뉘며, 어떤 방식을 쓰든 이 우회는 CTF·교육 목적의 정적/동적 분석을 계속 진행하기 위한 것으로 저작권이 있는 상용 소프트웨어의 라이선스 보호를 무력화하는 데 사용해서는 안 된다.

## 언제 검색해야 하나
- REV-0130에서 `IsDebuggerPresent` 호출 지점과 분기까지는 찾았는데, 실제로 디버거를 붙인 채 그 검사를 통과시키고 싶을 때
- x64dbg로 파일을 열고 실행했더니 `IsDebuggerPresent` 검사에 걸려 프로그램이 바로 종료되거나 다른 경로로 빠져서 분석을 더 진행할 수 없을 때
- ScyllaHide 같은 플러그인 이름은 들어봤지만 그게 정확히 무엇을 어떻게 바꿔주는지, 수동 패치와 어떤 차이가 있는지 궁금할 때
- CTF 문제에서 "이 안티디버깅을 우회해서 다음 단계로 진행하라"는 요구를 받았을 때 접근 방법 전체를 정리하고 싶을 때

## 핵심 개념

### 우회 대상은 세 지점 중 하나
`IsDebuggerPresent` 검사를 무력화하려면 다음 세 지점 중 어느 한 곳을 조작하면 된다.
1. **PEB의 `BeingDebugged` 플래그 자체** — 근원(root)을 고친다. 이 값을 0으로 만들면 `IsDebuggerPresent`뿐 아니라 이 플래그를 직접 읽는 다른 코드(REV-0132)까지 동시에 무력화된다.
2. **함수의 반환값(`EAX`)** — 함수가 실제로 실행되게 두되, 반환되는 순간 그 값을 강제로 0으로 바꾼다.
3. **반환값을 검사하는 분기(`test`/`jne` 등)** — 분기 명령 자체를 무조건 특정 방향으로만 가도록(NOP 처리 또는 조건 반전) 코드를 패치한다.

세 방법 모두 "디버거가 없는 것처럼 보이게 만든다"는 결과는 같지만, 적용 범위와 지속성이 다르다.

### 방법 A: PEB BeingDebugged 직접 패치(가장 근본적)
x64dbg의 메모리 덤프 창에서 현재 프로세스의 PEB 주소를 찾아(`dq fs:[30]`(x86) 또는 `dq gs:[60]`(x64) 명령, 혹은 `Debug > ... > PEB` 메뉴) `BeingDebugged` 오프셋(x86/x64 공통으로 PEB 시작에서 `+0x02`)의 바이트 값을 `1`에서 `0`으로 직접 덮어쓴다. 이 방법의 장점은 `IsDebuggerPresent` API를 거치지 않고 PEB를 직접 읽는 코드까지 함께 속인다는 점이다. 단점은 프로세스가 재시작되거나 새로 붙을 때마다(예: 디버거가 다시 attach) Windows 커널이 이 값을 다시 1로 세팅하므로 매번 다시 패치해야 한다는 점이다.

### 방법 B: 함수 후킹/EAX 강제 조작
x64dbg에서 `IsDebuggerPresent`에 브레이크포인트를 걸고, `ret` 직전(Execute till return, `Ctrl+F9`)에 멈춘 다음 Registers 창에서 `EAX`(또는 `RAX`) 값을 직접 `0`으로 수정한 뒤 계속 진행한다. 이 방법은 그 호출 한 번에만 적용되므로, 함수가 여러 번 호출되면 매번 반복해야 한다. 자동화하려면 x64dbg의 조건부 브레이크포인트(command on breakpoint hit)에 `eax=0` 명령을 등록해 매 호출마다 자동으로 값을 바꾸도록 설정할 수 있다.

### 방법 C: 분기 자체를 코드 패치
디스어셈블리에서 확인한 `test eax, eax` 다음의 `jne detected` 같은 분기 명령을 x64dbg의 CPU 창에서 우클릭 → `Binary > Fill with NOPs` 또는 어셈블 기능(`Space` 키로 해당 줄 선택 후 새 명령 입력)으로 아예 분기를 없애거나 항상 정상 경로로만 가도록 바꿔버리는 방식이다. 이 방법은 메모리상의 패치이므로 프로그램을 재시작하면 원래대로 돌아온다 — 영구 패치를 원한다면 x64dbg의 `Patches` 탭에서 `Save File`로 실제 EXE 파일에 반영해야 한다.

### 자동화 플러그인: ScyllaHide, TitanHide
매번 수동으로 패치하는 대신, x64dbg 플러그인인 ScyllaHide는 `IsDebuggerPresent`를 포함한 여러 잘 알려진 안티디버깅 API를 자동으로 후킹해 항상 "디버거 없음" 결과를 반환하도록 만들어준다. TitanHide는 커널 드라이버 레벨에서 더 깊은 은폐(PEB 조작, 프로세스 목록에서 디버거 자체를 숨기는 것 등)를 수행한다. `Plugins` 메뉴에서 설치된 플러그인을 활성화하고 어떤 기법을 우회할지 체크박스로 선택하는 방식이 일반적이다.

### 이 문서의 한계 — 무엇이 안 되는가
이 우회는 어디까지나 **이미 알려진, 표준적인 방식으로 구현된 `IsDebuggerPresent` 검사**를 대상으로 한다. 다음과 같은 경우는 이 문서의 범위를 넘어선다.
- 검사 결과가 즉시 분기로 이어지지 않고, 나중에 다른 계산(예: 복호화 키 생성)에 은밀히 섞여 들어가는 경우 — 단순히 EAX를 0으로 만드는 것만으로는 부족하고, 그 값이 어디에 쓰이는지 데이터 흐름을 끝까지 추적해야 한다.
- 여러 안티디버깅 기법이 동시에 걸려 있어 하나만 우회해도 다른 검사에 걸리는 경우(REV-0529의 레이어드 디펜스) — 각 기법을 개별적으로 찾아 모두 우회해야 한다.
- 자체적으로 무결성 검사(자기 자신의 코드 바이트를 체크섬으로 검증)를 수행하는 바이너리 — 코드 패치 자체가 감지되어 오히려 역효과를 낼 수 있다.
- 커널 레벨 안티디버깅(가상화 기반 보호, 드라이버 서명된 안티치트 등) — 이 문서가 다루는 사용자 모드 기법보다 훨씬 복잡하며 별도 학습이 필요하다.

## 화면/코드에서 보이는 징후
- x64dbg로 실행 시 `IsDebuggerPresent` 호출 이후 프로그램이 곧바로 `ExitProcess`로 종료되거나 메시지박스가 뜨고 멈춤.
- 디버거 없이 실행했을 때는 정상적으로 진행되던 프로그램이, 디버거로 열기만 하면 완전히 다른 문자열이 출력되거나 입력을 요구하지 않고 끝남.
- CPU 창에서 `test eax, eax` 직후 분기의 목적지 주소가 `ExitProcess`나 오류 메시지 출력 루틴으로 연결됨.

## 가장 먼저 할 것
REV-0130에서 확인한 호출 지점과 분기 방향을 다시 확인한 뒤, 가장 간단한 방법(방법 B: EAX를 0으로 강제)부터 시도한다. 이것으로 충분히 통과되면 더 복잡한 PEB 패치나 플러그인 설치 없이도 분석을 계속할 수 있다.

## 단계별 절차

**1) 호출 지점에 브레이크포인트 설정**

x64dbg에서 `bp IsDebuggerPresent` 명령을 입력하거나, Imports 창에서 우클릭 → `Follow in Disassembler` 후 함수 시작 주소에 `F2`로 브레이크포인트를 건다.

**2) 실행 후 함수 끝까지 진행**

`F9`(Run)로 실행해 브레이크포인트에 도달하면, `Ctrl+F9`(Execute till return)로 함수가 `ret` 직전까지 실행되도록 한다.

**3) EAX 값을 0으로 수정**

Registers 창에서 `EAX`(x86) 또는 `RAX`의 하위 32비트를 우클릭 → `Modify Value`로 `0`으로 바꾼다.

**4) 계속 실행하며 분기 확인**

`F9`로 계속 실행해, 이전에 종료로 이어지던 분기가 이제 정상 경로로 빠지는지 확인한다.

**5) 반복 호출 시 자동화**

같은 브레이크포인트가 여러 번 걸린다면, 브레이크포인트 속성(`Edit Breakpoint`)에서 `Command`란에 `eax=0` 을 입력하고 `Pass`를 체크해, 멈추지 않고 자동으로 값을 바꾼 뒤 계속 진행하도록 설정한다.

**6) 필요하면 PEB를 직접 패치**

여러 지점에서 각각 우회하기 번거롭거나, `IsDebuggerPresent`를 거치지 않는 다른 검사(REV-0132)까지 함께 막고 싶다면, `dq gs:[60]`(x64) 명령으로 PEB 주소를 확인한 뒤 Dump 창에서 그 주소로 이동해 `+0x02` 오프셋 바이트를 `0`으로 수정한다.

**7) 영구 패치가 필요하면 파일에 반영**

메모리 패치가 아니라 실행 파일 자체를 고치고 싶다면, `Patches` 탭에서 적용한 패치 목록을 확인하고 `File > Patch file` 또는 `Save File`로 디스크에 저장한다. 단, 파일 무결성 검사가 있는 바이너리는 이 방식이 오히려 새로운 문제를 일으킬 수 있음을 유의한다.

## 명령어/단축키
- x64dbg: `bp IsDebuggerPresent`, `Ctrl+F9`(Execute till return), `F2`(브레이크포인트 토글), `F9`(Run)
- x64dbg: `dq gs:[60]`(x64 PEB 주소 확인), `dq fs:[30]`(x86 PEB 주소 확인)
- x64dbg: CPU 창 우클릭 → `Binary > Fill with NOPs`(NOP 패치), `Binary > Assemble`(명령어 직접 수정)
- x64dbg: `Plugins` 메뉴에서 ScyllaHide 활성화 및 옵션 설정

## 출력 해석
- `EAX`를 0으로 바꾼 뒤에도 여전히 종료 경로로 빠진다면, 이 검사가 `IsDebuggerPresent`만 쓰는 게 아니라 다른 안티디버깅 기법(REV-0529 참고)과 조합되어 있다는 뜻이다.
- PEB의 `BeingDebugged`를 0으로 패치했는데도 프로그램이 여전히 감지한다면, `NtQueryInformationProcess`(REV-0533) 같은 커널 질의 기반 검사가 별도로 있는지 확인해야 한다.
- ScyllaHide를 켰는데도 감지된다면, 해당 플러그인이 지원하는 우회 항목 목록(옵션 창에서 체크박스로 표시됨)에 이 바이너리가 쓰는 기법이 포함되어 있는지 먼저 확인한다.

## 흔한 실수
- PEB를 패치한 뒤 프로그램을 재시작(또는 디버거를 다시 attach)하면 `BeingDebugged`가 다시 1로 세팅된다는 것을 잊고, "패치가 풀렸다"며 당황하는 것 — 매 세션마다 다시 패치해야 한다.
- 분기를 NOP으로 밀어버렸는데 그 코드가 사실은 다른 목적(정상적인 스택 정리 등)까지 함께 담당하고 있어서 프로그램이 오히려 크래시하는 것 — 패치 전후 명령어 바이트 수와 스택 균형을 반드시 확인해야 한다.
- 우회 자체를 목적으로 착각해서, 정작 원래 분석하려던 로직(예: 시리얼 검증 알고리즘)을 살펴보지 않고 우회 작업에만 시간을 쓰는 것 — 우회는 분석을 계속하기 위한 수단이지 목적이 아니다.
- 라이선스가 있는 상용 소프트웨어의 보호 기능을 무력화하는 데 이 기법을 적용하는 것 — 이 저장소의 범위는 CTF/워게임/교육용 방어적 리버싱이며, 상용 라이선스 크랙은 다루지 않는다.

## 막혔을 때 다음 체크
- 애초에 `IsDebuggerPresent` 호출과 분기를 어떻게 찾는지 다시 확인하려면 → REV-0130 IsDebuggerPresent 안티디버깅 식별
- PEB의 `BeingDebugged` 필드 구조와 위치를 더 자세히 알고 싶다면 → REV-0132 PEB BeingDebugged 검사 이해
- 여전히 감지된다면 다른 API 기반 검사가 있는지 전체 목록을 다시 훑고 싶다면 → REV-0529 Windows 안티디버깅 기법 종류 빠른 참조표
- `CheckRemoteDebuggerPresent`도 함께 쓰이고 있다면 → REV-0532 CheckRemoteDebuggerPresent 우회 실습 개념

## 미니 예제
```text
원본 코드 (x64):
call IsDebuggerPresent
test eax, eax
jne  detected_branch

x64dbg 조작 순서:
1) bp IsDebuggerPresent
2) F9 (Run) -> 브레이크포인트 도달
3) Ctrl+F9 (Execute till return) -> ret 직전
4) Registers 창에서 EAX를 0으로 수정
5) F9 (계속 실행) -> test eax, eax 결과가 ZF=1이 되어 jne가 발생하지 않음
   -> detected_branch로 가지 않고 정상 경로로 진행됨
```

## 관련 글
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0132 — PEB BeingDebugged 검사 이해
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표
- REV-0532 — CheckRemoteDebuggerPresent 우회 실습 개념

## 출처/검증
- `IsDebuggerPresent`/PEB `BeingDebugged` 동작은 Microsoft 공식 문서(learn.microsoft.com) 기준. x64dbg의 브레이크포인트 명령 실행(Command on hit), 패치/NOP 채우기, ScyllaHide/TitanHide 플러그인 개념은 x64dbg 공식 문서 및 해당 오픈소스 프로젝트 저장소 설명(2026-09-08 확인) 기준으로 정리했으며, 실제 최신 UI 메뉴 문구는 x64dbg 버전에 따라 다를 수 있다.
