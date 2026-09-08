---
id: REV-0236
title: "PEB BeingDebugged 검사 우회 개념"
slug: "rev-0236-peb-beingdebugged-bypass-concept"
category: "packing"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, IDA]
keywords:
  - PEB BeingDebugged
  - fs 0x30
  - gs 0x60
  - Process Environment Block
  - NtGlobalFlag
  - Heap flags anti-debug
  - PEB 직접 접근
  - manual PEB check
  - 인라인 안티디버깅
aliases:
  - PEB가 뭐임
  - fs:[30h]가 뭐임
  - gs:[60h]가 뭐임
  - PEB 직접 읽는 안티디버깅
symptom_keywords:
  - fs 0x30 접근하는 코드가 있음
  - gs 0x60 접근하는 코드가 있음
  - IsDebuggerPresent가 없는데도 디버거를 감지함
  - NtGlobalFlag 값을 비교하는 코드가 있음
  - 힙 플래그를 검사하는 코드가 있음
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
**이해를 위한 개념 설명**: `IsDebuggerPresent()`를 호출하지 않고도, 어셈블리 수준에서 `fs:[0x30]`(x86) 또는 `gs:[0x60]`(x64)로 PEB 주소를 직접 읽어와 `BeingDebugged` 필드(및 `NtGlobalFlag`, 힙 플래그 같은 다른 PEB 정보)를 검사하면 API 호출 자체가 없어서 import 목록만 봐서는 안티디버깅 여부를 알 수 없다 — 이 글은 자신이 만든 연습용 크랙미에서 이런 "인라인 PEB 체크"를 어셈블리에서 알아보고 이해하는 법을 다룬다.

## 언제 검색해야 하나
- IDA Imports 탭에는 `IsDebuggerPresent`가 없는데도 x64dbg로 실행하면 프로그램이 다르게 동작할 때
- 어셈블리 코드에 `mov rax, gs:[60h]` 또는 `mov eax, fs:[30h]` 같은 세그먼트 레지스터 접근이 보일 때
- 그 뒤에 `movzx`로 특정 오프셋의 1바이트를 읽어서 `test`/`cmp`하는 코드가 이어질 때
- `NtGlobalFlag`, 힙(Heap)의 `Flags`/`ForceFlags` 값을 비교하는 코드를 봤을 때

## 핵심 개념

### 왜 API 호출 없이 PEB를 직접 읽는가
`IsDebuggerPresent()`는 이름 자체가 그대로 남기 때문에 정적 분석에서 너무 쉽게 발견된다(REV-0235). 좀 더 신경 쓴 크랙미나 실제 악성코드는 그 API가 내부적으로 하는 일(`gs:[0x60]`로 PEB를 찾고 오프셋 `+2`를 읽는 것)을 **코드에 직접 인라인**해서, import 목록에 흔적을 남기지 않는다. 이렇게 하면 "이 프로그램은 IsDebuggerPresent를 안 쓰니까 안티디버깅이 없다"고 성급하게 결론 내리는 분석가를 속일 수 있다.

### PEB 접근 방법 (x64 / x86)
Windows는 스레드마다 TEB(Thread Environment Block)를 유지하고, x64에서는 `GS` 세그먼트 레지스터가, x86에서는 `FS` 세그먼트 레지스터가 현재 스레드의 TEB를 가리키도록 되어 있다. TEB 구조체 안의 특정 오프셋에 현재 프로세스의 PEB 주소가 들어있다.
```
x64: PEB 주소 = gs:[0x60]
x86: PEB 주소 = fs:[0x30]
```
PEB 구조체 안에서 관심 있는 필드들의 오프셋(x64/x86 공통, PEB 시작 기준):
| 오프셋 | 필드 | 의미 |
|---|---|---|
| `+0x02` | `BeingDebugged` | 1바이트. 디버거가 이 프로세스를 시작했거나 attach하면 1 |
| `+0x68`(x86) / `+0xBC`(x64) | `NtGlobalFlag` | 디버거 하에서 실행되면 특정 비트(`FLG_HEAP_ENABLE_TAIL_CHECK`, `FLG_HEAP_ENABLE_FREE_CHECK`, `FLG_HEAP_VALIDATE_PARAMETERS`)가 세팅됨 |

어셈블리로는 대략 다음과 같은 모습이다(x64):
```asm
mov     rax, gs:[60h]        ; PEB 주소
movzx   eax, byte ptr [rax+2] ; BeingDebugged
test    eax, eax
jnz     debugger_detected
```

### NtGlobalFlag / 힙 플래그 체크
디버거 하에서 프로세스가 생성되면, 프로세스 힙(Heap)이 디버깅을 돕기 위해 평소와 다른 방식(tail 체크, free 체크 등)으로 초기화되고, 이 상태가 `PEB->NtGlobalFlag`와 프로세스 힙 구조체의 `Flags`/`ForceFlags` 필드에 반영된다. 이를 이용한 체크는 대략 이런 식이다.
```c
DWORD ntGlobalFlag = *(DWORD*)((BYTE*)peb + 0xBC); // x64 오프셋
if (ntGlobalFlag & 0x70) { // FLG_HEAP_* 비트들
    // 디버거 의심
}
```
`BeingDebugged`보다 조금 더 우회하기 까다로운 편인데, 값을 하나만 패치하면 되는 게 아니라 힙이 실제로 생성되는 시점의 커널 동작 자체가 다르기 때문이다. 다만 학습 목적에서는 "이 값도 결국 프로세스 메모리에 있는 데이터이므로, 디버거로 그 값을 찾아 원하는 값으로 덮어쓸 수 있다"는 원리만 이해하면 충분하다.

## 화면/코드에서 보이는 징후
- IDA Imports 탭에 `IsDebuggerPresent`가 없는데도 디버거로 실행 시 동작이 달라진다.
- 어셈블리에 `fs:[30h]`, `gs:[60h]` 같은 세그먼트 레지스터 접근이 보인다.
- 그 접근 이후 코드에서 작은 오프셋(`+2`, `+0xBC` 등)으로 필드를 읽는다.
- 디컴파일러(IDA F5)가 이런 패턴을 인식하면 `NtCurrentTeb()->ProcessEnvironmentBlock->BeingDebugged`처럼 구조체 접근으로 깔끔하게 보여주기도 하지만, 인식하지 못하면 raw 포인터 연산으로 남는다.

## 가장 먼저 할 것
1. 어셈블리 뷰(IDA `Space`로 그래프/텍스트 전환)에서 `fs:` 또는 `gs:` 접두사가 붙은 명령을 검색한다(`Alt+T` 텍스트 검색 → `gs:` 또는 `fs:`).
2. 찾으면 그 뒤에 이어지는 오프셋과 비교 연산을 확인해 `BeingDebugged`(오프셋 `+2`)인지 `NtGlobalFlag`인지 구분한다.
3. 그 결과를 사용하는 분기의 목적지를 확인한다.

## 단계별 절차 (자신의 연습용 크랙미에서 이해/패치하는 법)
1. IDA에서 `Alt+T`(텍스트 검색)로 `gs:` 또는 `fs:`를 검색해 PEB 접근 지점을 모두 찾는다.
2. 각 지점에서 오프셋을 확인해 어떤 필드를 읽는지 표와 대조한다.
3. x64dbg에서 그 명령 주소로 이동(`Ctrl+G`)해 브레이크포인트를 건다.
4. 실행해서 멈추면, 명령어가 가리키는 메모리 주소를 Dump 창에서 직접 확인한다 — `BeingDebugged` 바이트가 실제로 `1`인지 확인할 수 있다.
5. **개념 이해를 위한 패치 실습**: Dump 창에서 그 바이트를 직접 `0`으로 덮어쓰거나(우클릭 → Edit), 그 값을 읽어 분기하는 `test`/`jnz` 명령을 패치한다.
6. x64dbg는 옵션에서 "PEB 내 BeingDebugged 자동 패치" 같은 기능을 제공하는 플러그인(ScyllaHide 등)이 있는데, 이런 플러그인이 실행 중에 PEB의 해당 바이트 자체를 계속 0으로 유지시켜주는 원리임을 이해하면 개별 분기를 일일이 찾아 패치할 필요가 줄어든다.

## 명령어/단축키
- IDA: `Alt+T`(텍스트 검색으로 `gs:`/`fs:` 찾기), `F5`(디컴파일해서 구조체 접근으로 인식되는지 확인)
- x64dbg: `Ctrl+G`(주소 이동), `F2`(브레이크포인트), Dump 창에서 PEB 주소로 이동 후 오프셋 확인, 바이트 우클릭 → Edit로 직접 수정
- x64dbg: 커맨드 바에 `dump fs:[30]` 또는 `dump gs:[60]`을 입력하면 Dump 창이 바로 PEB 시작 주소로 이동한다(버전에 따라 표기가 다를 수 있음)

## 출력 해석
- Dump 창에서 PEB 주소 `+0x02` 위치의 바이트가 `01`이면 디버거가 감지된 상태, `00`이면 감지되지 않은 상태다.
- 값을 `00`으로 패치한 뒤에도 프로그램이 계속 이상하게 동작한다면, `NtGlobalFlag`나 힙 플래그처럼 더 깊은 곳의 체크가 남아있는지 의심해야 한다.

## 흔한 실수
- `fs:`/`gs:` 접두사를 그냥 "이상한 레지스터 문법"이라고 넘기고 무슨 데이터를 읽는지 확인하지 않는 것.
- `BeingDebugged` 바이트만 패치하면 모든 PEB 기반 체크가 끝난다고 생각하는 것 — `NtGlobalFlag`, 힙 플래그처럼 다른 필드를 쓰는 체크가 별도로 존재할 수 있다.
- x86과 x64에서 오프셋이 다르다는 걸 헷갈리는 것 — 반드시 대상 바이너리의 아키텍처에 맞는 오프셋 표를 써야 한다.
- 이 기법을 상용 소프트웨어의 보호를 무력화하는 데 쓰는 것 — 이 글은 CTF/자체 제작 크랙미 학습 목적에 한정된다.

## 막혔을 때 다음 체크
- `gs:`/`fs:` 검색 결과가 하나도 없는데 여전히 디버거를 감지하는 것 같다면 → `IsDebuggerPresent`(REV-0235)나 예외 기반 체크(REV-0239)를 먼저 의심한다.
- 오프셋이 표와 안 맞는 것 같다면 → 컴파일러/링커 버전에 따라 구조체 레이아웃이 미세하게 다를 수 있으니, 디버거로 실제 PEB 메모리를 덤프해서 직접 대조한다.
- PEB 자체가 낯설다면 → Windows 내부 구조에 대한 배경지식이 필요하므로, 먼저 프로세스가 시작될 때 커널이 어떤 구조체들을 세팅하는지 개념적으로 훑어본 뒤 돌아온다.
- x86과 x64 두 버전이 섞여 있는 바이너리(WOW64)를 분석 중이라면 → x86 프로세스도 내부적으로는 x64 TEB/PEB를 함께 갖고 있어 오프셋 계산이 헷갈리기 쉬우니, 디버거의 아키텍처 모드(x32dbg/x64dbg 중 어느 것으로 열었는지)를 먼저 확인한다.

## 왜 이 체크가 완전히 숨겨지지 않는가
`BeingDebugged` 플래그는 결국 운영체제 커널이 프로세스 생성/attach 시점에 관리하는 값이기 때문에, 애플리케이션 코드가 아무리 이 값을 읽는 위치를 숨기거나 여러 겹으로 암호화해도 **그 값 자체는 항상 메모리 어딘가(PEB)에 존재**한다. 이 사실을 이해하면 "이름을 숨긴 안티디버깅 체크"를 만났을 때도 당황하지 않고, "결국 어딘가에서 이 한 바이트(혹은 이에 대응하는 커널 상태)를 읽어와야 한다"는 전제로 코드를 추적할 수 있다. 이것이 API 기반 체크(REV-0235)와 인라인 PEB 체크(REV-0236)를 같은 계열로 묶어서 이해해야 하는 이유다.

## 미니 예제
**예제 — x64 인라인 PEB 체크**
```asm
mov     rax, gs:[60h]         ; TEB->ProcessEnvironmentBlock
movzx   eax, byte ptr [rax+2] ; PEB->BeingDebugged
test    eax, eax
jnz     debugger_detected
```

**예제 — C로 표현한 동일 로직**
```c
typedef struct _PEB { BYTE Reserved[2]; BYTE BeingDebugged; } PEB;

BOOL manual_check(void) {
    PEB* peb = (PEB*)__readgsqword(0x60);
    return peb->BeingDebugged;
}
```

## 관련 글
- REV-0235 — IsDebuggerPresent 우회 개념
- REV-0239 — Exception 기반 안티디버깅 기초
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트

## 출처/검증
- PEB 구조체 및 `BeingDebugged`/`NtGlobalFlag` 필드, TEB를 통한 접근(`fs:[0x30]`/`gs:[0x60]`) 방식: Microsoft가 공개한 `winternl.h` PEB 정의 및 공개된 Windows 내부 구조 레퍼런스(예: Windows Internals 서적 계열 자료) 기준(2026-09-08 검증).
- 힙 플래그 기반 디버거 탐지 원리: 공개된 안티디버깅 기법 교육 자료에서 공통적으로 다루는 표준 내용을 정리함.
