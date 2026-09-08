---
id: REV-0132
title: "PEB BeingDebugged 검사 이해"
slug: "rev-0132-peb-beingdebugged"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["PEB", "Process Environment Block", "BeingDebugged", "fs:[0x30]", "gs:[0x60]", "PEB 직접 검사", "안티디버깅", "anti-debugging"]
aliases: ["PEB 안티디버깅", "BeingDebugged 플래그", "fs 0x30 gs 0x60", "PEB 구조체 검사"]
symptom_keywords: ["mov eax fs 0x30이 뭔지 모르겠음", "mov rax gs 0x60이 뭔지 모르겠음", "IsDebuggerPresent 없는데 안티디버깅이 있는 것 같음", "PEB가 뭔지 모르겠음", "byte ptr eax+2 검사하는 코드가 있음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`IsDebuggerPresent`는 내부적으로 **PEB(Process Environment Block)** 구조체의 `BeingDebugged` 바이트를 읽어서 반환할 뿐이므로, API 호출 없이 어셈블리 코드가 `fs:[0x30]`(x86) 또는 `gs:[0x60]`(x64)로 PEB 주소를 직접 얻은 뒤 그 안의 `+0x2` 오프셋을 읽는 패턴이 보이면, 이는 Import Table에 아무 흔적도 안 남기는 "이름 없는" 버전의 `IsDebuggerPresent`라고 이해하면 된다.

## 언제 검색해야 하나
- Import Table에 `IsDebuggerPresent`나 `CheckRemoteDebuggerPresent`가 전혀 없는데도 안티디버깅이 의심될 때
- 디스어셈블리에서 `mov eax, fs:[0x30]` 또는 `mov rax, gs:[0x60]` 같은 세그먼트 레지스터 접두사가 붙은 명령을 봤을 때
- 그 뒤에 `movzx eax, byte ptr [eax+2]` 같은 오프셋 접근이 이어져서 이게 무슨 구조체를 읽는 건지 궁금할 때
- IDA 디컴파일러(F5)가 이런 코드를 `*(_BYTE *)(__readfsdword(0x30) + 2)` 또는 `NtCurrentPeb()->BeingDebugged` 형태로 보여줄 때 이게 뭘 의미하는지 알고 싶을 때

## 핵심 개념

### PEB(Process Environment Block)란
PEB는 Windows가 각 프로세스마다 유지하는 사용자 모드(user-mode)에서 접근 가능한 구조체로, 로드된 모듈 목록, 힙 정보, 명령줄 인자, 그리고 지금 다루는 `BeingDebugged` 플래그 등 프로세스에 대한 다양한 메타데이터를 담고 있다. 공식적으로 문서화되지 않은 필드가 많지만(비공식 구조체), `BeingDebugged`처럼 안정적으로 알려진 필드는 리버싱/보안 커뮤니티에서 오래전부터 널리 활용해왔다.

### PEB에 접근하는 방법
Windows는 현재 스레드의 TEB(Thread Environment Block)를 가리키는 포인터를 특수한 세그먼트 레지스터를 통해 항상 접근 가능하게 해준다.
- **x86(32비트)**: `FS` 세그먼트 레지스터가 TEB를 가리킨다. TEB 구조체의 오프셋 `0x30`에 PEB의 포인터가 저장되어 있다. 그래서 `mov eax, fs:[0x30]`은 "현재 프로세스의 PEB 주소를 EAX에 담아라"는 뜻이다.
- **x64(64비트)**: 같은 역할을 `GS` 세그먼트 레지스터가 담당하며, TEB 안에서 PEB 포인터의 오프셋은 `0x60`이다. 그래서 `mov rax, gs:[0x60]`이 PEB 주소를 얻는 x64 버전이다.

PEB 주소를 얻은 뒤에는 그 구조체 안의 `BeingDebugged` 필드까지 오프셋만큼 더해서 읽으면 된다. `BeingDebugged`는 PEB 구조체 맨 앞부분에 있는 1바이트(`BOOLEAN`) 필드로, **오프셋이 x86과 x64에서 동일하게 `0x02`**다(앞의 두 필드 `InheritedAddressSpace`, `ReadImageFileExecOptions`가 각각 1바이트씩이기 때문).

### 왜 API 호출 없이 이렇게 하나
- **Import Table에 흔적이 안 남는다.** `IsDebuggerPresent`라는 이름 자체가 아예 코드 어디에도 등장하지 않으므로, Import Table이나 문자열 검색으로 안티디버깅을 찾으려는 분석(REV-0130의 방식)을 그대로 우회한다.
- **API 후킹에도 안 걸린다.** 많은 안티-안티디버깅 도구(예: x64dbg 플러그인 ScyllaHide)는 `IsDebuggerPresent` 같은 API 함수 자체를 후킹해서 항상 `FALSE`를 반환하도록 속인다. 하지만 코드가 API를 거치지 않고 메모리를 직접 읽으면, 이런 API 레벨 후킹은 전혀 효과가 없다.
- **컴파일러가 자동으로 이렇게 최적화하기도 한다.** 일부 컴파일러/런타임은 `IsDebuggerPresent` 호출을 인라인화하면서 실제로 이 PEB 직접 읽기 코드로 펼쳐버리는 경우도 있어서, 개발자가 의도적으로 안티디버깅을 넣지 않았는데도 이런 패턴이 보일 수 있다(다만 CTF/의도된 안티디버깅 문제에서는 대개 의도적으로 넣은 것).

### IDA 디컴파일러(F5)에서 보이는 형태
IDA의 Hex-Rays 디컴파일러는 이 패턴을 자동으로 인식해서 `NtCurrentPeb()->BeingDebugged`처럼 사람이 읽기 쉬운 형태로 보여주거나, 완전히 인식하지 못하면 `*(_BYTE *)(__readfsdword(0x30) + 2)`(x86) / `*(_BYTE *)(__readgsqword(0x60) + 2)`(x64) 같은 컴파일러 내장 함수(intrinsic) 형태로 보여준다. 둘 다 의미는 같다 — PEB의 `BeingDebugged` 바이트를 읽는 코드다.

## 화면/코드에서 보이는 징후
- x86: `mov eax, large fs:30h` 또는 `mov eax, fs:[0x30]` 형태의 명령.
- x64: `mov rax, gs:60h` 또는 `mov rax, gs:[0x60]` 형태의 명령.
- 그 직후 `movzx eax, byte ptr [eax+2]` 또는 `movzx eax, byte ptr [rax+2]`처럼 `+2` 오프셋으로 1바이트를 읽는 코드.
- IDA F5 디컴파일 결과에 `NtCurrentPeb()`, `__readfsdword`, `__readgsqword`, `PEB`, `BeingDebugged` 같은 이름이 등장.
- Import Table에는 안티디버깅 관련 API가 전혀 없는데도 `test`/`cmp` + 조건 분기로 흐름이 갈라지는 코드가 프로그램 초반부에 존재.

## 가장 먼저 할 것
`fs:[0x30]`(x86) 또는 `gs:[0x60]`(x64) 접근 코드를 발견하면, 곧바로 이어지는 오프셋이 `+2`인지 확인한다. `+2`가 맞으면 `BeingDebugged` 검사가 거의 확실하다. 다른 오프셋(`+0x68` 등)이면 PEB의 다른 필드(예: `NtGlobalFlag`, 힙 플래그 등 다른 안티디버깅 기법)를 읽는 것일 수 있으므로 오프셋 값을 정확히 확인하는 것이 핵심이다.

## 단계별 절차

**1) 세그먼트 레지스터 접근 코드 찾기**

IDA/x64dbg 디스어셈블리에서 `fs:` 또는 `gs:` 접두사가 붙은 명령을 찾는다. IDA Search(`Alt+T`, 텍스트 검색)로 `fs:` 또는 `gs:`를 검색하면 빠르게 찾을 수 있다.

**2) 오프셋 확인: PEB를 가리키는지 확인**

`fs:[0x30]`(x86) 또는 `gs:[0x60]`(x64)이면 PEB 주소를 얻는 코드다. 다른 오프셋(예: x86의 `fs:[0]`은 SEH 체인 헤드)이면 안티디버깅과 무관한 다른 목적일 수 있다.

**3) 그 다음 오프셋 확인: BeingDebugged인지 확인**

PEB 주소를 얻은 레지스터에 이어지는 접근이 `+2`(1바이트, `movzx`/`byte ptr`)라면 `BeingDebugged`다. 이 코드가 이후 어디서 조건 분기로 이어지는지 xref/흐름을 따라간다.

**4) IDA 디컴파일러로 이름 붙이기(선택)**

IDA F5로 디컴파일했을 때 이 패턴이 `NtCurrentPeb()->BeingDebugged`로 인식되지 않고 raw intrinsic으로만 보인다면, 해당 변수에 직접 주석을 달아 "PEB.BeingDebugged 검사"라고 표시해두면 이후 분석이 편해진다.

**5) x64dbg로 PEB 주소 직접 확인**

x64dbg는 Registers 패널이나 커맨드바에서 현재 프로세스의 PEB 주소를 바로 알려주는 기능이 있다. PEB 주소를 알아낸 뒤 Dump 창에서 `PEB주소+2` 위치의 바이트 값을 직접 확인할 수 있다.
```text
; x64dbg 커맨드바
dq gs:[0x60]           ; 또는 Registers 패널의 PEB 링크 클릭
; Dump 창에서 PEB주소+2 바이트 확인 (디버깅 중이면 보통 1)
```

**6) API 후킹 우회 여부 판단**

만약 `IsDebuggerPresent`는 후킹해서 우회했는데도 여전히 감지된다면, 바로 이 PEB 직접 읽기 패턴이 코드 어딘가에 남아있는지 다시 검색해봐야 한다.

## 명령어/단축키
- IDA: `Alt+T`(텍스트 검색)로 `fs:` / `gs:` 검색, `X`(xref로 이 값을 쓰는 이후 코드 추적)
- x64dbg: Registers 패널에서 PEB 주소 확인(대부분 버전에서 오른쪽 하단이나 별도 표시 제공), Dump 창에서 `PEB주소+2` 바이트 확인
- x64dbg 커맨드바: `dq gs:[0x60]`(x64에서 PEB 포인터 직접 조회)

## 출력 해석
- `PEB+2` 바이트 값이 `0`이면 디버거 없음, `1`이면 디버거가 붙어 있다는 뜻 — `IsDebuggerPresent`의 반환값과 완전히 동일한 의미다.
- x64dbg로 디버깅 중이라면 이 값은 정상적으로 `1`이어야 한다.
- 디컴파일 결과에 `__readfsdword(0x30)`/`__readgsqword(0x60)`가 다른 오프셋(`+2`가 아닌 값)과 함께 쓰인다면, `BeingDebugged`가 아니라 PEB의 다른 안티디버깅 관련 필드(예: 힙 플래그 `ForceFlags`, `NtGlobalFlag`)를 확인하는 더 심화된 기법일 수 있다 — 이런 기법은 이 문서 범위를 넘어서므로, 발견 시 오프셋 값을 기록해두고 추가 조사가 필요하다.

## 흔한 실수
- `fs:`/`gs:` 접근을 보고 무조건 `BeingDebugged` 검사라고 단정하는 것 — 반드시 뒤따르는 오프셋(`+2`)까지 확인해야 한다.
- x86과 x64의 세그먼트 레지스터(`fs` vs `gs`)와 오프셋(`0x30` vs `0x60`)을 헷갈려서 잘못된 아키텍처 공식을 적용하는 것.
- API 후킹 기반 안티-안티디버깅 툴을 적용했는데도 여전히 감지되면 "우회가 실패했다"고만 생각하고, 코드에 이런 API-비경유 직접 읽기 패턴이 남아있을 가능성을 놓치는 것.
- PEB 구조체 전체를 다 외우려 하는 것 — 실전에서는 `BeingDebugged`(오프셋 0x2) 정도만 확실히 알아두고, 나머지 필드는 필요할 때 마이크로소프트 문서나 WinDbg의 `dt _PEB` 같은 도구로 그때그때 찾아보는 것이 현실적이다.

## 막혔을 때 다음 체크
- API 호출 버전의 기본형이 궁금하다면 → REV-0130 IsDebuggerPresent 안티디버깅 식별
- 프로세스 핸들 기반의 변형 API가 궁금하다면 → REV-0131 CheckRemoteDebuggerPresent 식별
- 이런 패턴을 x64dbg에서 직접 실행하며 확인하는 기본기가 필요하다면 → REV-0127 x64dbg로 EXE 첫 분석 시작
- 이 코드가 동적으로 로드된 API와 섞여 있어 헷갈린다면 → REV-0129 GetProcAddress LoadLibrary 동적 API 해석

## 미니 예제
```c
// 개념적으로 동일한 코드 (실제로는 인라인 어셈블리나 컴파일러 intrinsic으로 구현됨)
BOOL being_debugged = *(BYTE*)((BYTE*)NtCurrentPeb() + 2);
if (being_debugged) {
    ExitProcess(1);
}
```
x64 디스어셈블리로는 다음과 같이 나타난다.
```asm
mov  rax, gs:[0x60]        ; RAX = PEB 주소
movzx eax, byte ptr [rax+2] ; PEB.BeingDebugged
test eax, eax
je   continue_normally
mov  ecx, 1
call ExitProcess
continue_normally:
```
x86(32비트)이었다면 첫 줄만 `mov eax, fs:[0x30]`으로 바뀌고 나머지 로직은 동일하다.

## 관련 글
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0131 — CheckRemoteDebuggerPresent 식별
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- PEB/TEB 구조와 `BeingDebugged` 필드 오프셋(0x2), `fs:[0x30]`(x86)/`gs:[0x60]`(x64) 접근 방식은 Windows 내부 구조에 대한 공개된 리버싱/보안 레퍼런스(Microsoft가 일부 공식 문서화한 `PEB` 구조체 포함) 및 IDA Hex-Rays 디컴파일러의 `NtCurrentPeb()`/`__readfsdword`/`__readgsqword` intrinsic 인식 동작 기준(2026-09-08 확인).
- 이 필드는 공식적으로 완전히 문서화된 안정 ABI는 아니므로, Windows 버전에 따라 세부 오프셋이 달라질 가능성을 항상 염두에 두고 실제 바이너리에서 직접 재검증하는 것이 안전하다.
