---
id: REV-0510
title: "WinAPI 메모리 함수 사전: HeapAlloc HeapFree"
slug: "rev-0510-heapalloc-heapfree"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["HeapAlloc", "HeapFree", "GetProcessHeap", "HEAP_ZERO_MEMORY", "힙 할당", "malloc 내부 구현"]
aliases: ["힙알록", "힙프리", "겟프로세스힙", "힙 버퍼 할당 함수"]
symptom_keywords: ["HeapAlloc이 malloc과 뭐가 다른지 모르겠다", "GetProcessHeap이 뭔지 모르겠다", "힙 오버플로우 버그를 찾고 있다", "HeapFree 이후 use-after-free를 의심하고 있다", "동적으로 만들어지는 문자열 버퍼를 추적하고 싶다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`HeapAlloc`/`HeapFree`는 지정한 힙(대개 `GetProcessHeap()`이 반환하는 프로세스 기본 힙)에서 메모리 블록을 직접 할당/해제하는 저수준 Win32 API로, CRT의 `malloc`/`free`가 내부적으로 감싸고 있는 실체이며, 할당 크기 인자(`dwBytes`)와 실제 쓰기 크기를 대조하면 힙 오버플로우 취약점을, 해제 이후에도 포인터가 계속 쓰이는지 확인하면 use-after-free를 찾을 수 있다.

## 언제 검색해야 하나
- Import 목록에 `malloc`/`free`가 안 보이는데(정적 링크되었거나 CRT를 우회한 경우) `HeapAlloc`/`HeapFree`가 직접 보여서 이것이 동적 메모리 할당의 실체임을 확인해야 할 때
- `HeapAlloc`의 `dwBytes` 인자 크기와 그 버퍼에 이후 쓰여지는 데이터 크기가 일치하는지 대조해 힙 오버플로우 여부를 판단해야 할 때
- `HeapFree`로 해제된 포인터가 이후 코드에서 다시 참조되는지(use-after-free) 확인해야 할 때
- 문자열/설정 데이터를 정적 데이터 섹션이 아니라 런타임에 힙에서 조립하는 코드(문자열 스캔 회피 목적)를 만났을 때

## 핵심 개념

### 함수 시그니처
```c
LPVOID HeapAlloc(
    HANDLE hHeap,   // 1. 대상 힙 핸들, 대개 GetProcessHeap()의 반환값
    DWORD  dwFlags, // 2. HEAP_ZERO_MEMORY(0x8) 등
    SIZE_T dwBytes  // 3. 할당할 바이트 수
);

BOOL HeapFree(
    HANDLE hHeap, // 1. 대상 힙 핸들
    DWORD  dwFlags,
    LPVOID lpMem  // 3. 해제할 블록의 시작 주소(HeapAlloc이 반환한 값)
);
```
`hHeap`은 보통 `GetProcessHeap()`(인자 없이 프로세스 기본 힙 핸들을 반환)의 결과를 그대로 쓰지만, `HeapCreate`로 별도의 전용 힙을 만들어 쓰는 프로그램도 있다.

### dwFlags 주요 값
```text
HEAP_ZERO_MEMORY        0x00000008  // 할당된 메모리를 0으로 초기화(calloc과 유사)
HEAP_GENERATE_EXCEPTION 0x00000004  // 실패 시 NULL 대신 예외 발생
HEAP_NO_SERIALIZE       0x00000001  // 스레드 동기화 생략(위험, 잘 안 씀)
```

### malloc/free와의 관계
Visual C++ CRT의 `malloc`은 대부분의 경우 내부적으로 `HeapAlloc(GetProcessHeap(), 0, size)` 또는 CRT 전용 힙에 대한 `HeapAlloc` 호출을 감싸고 있으며, 여기에 CRT 자체의 디버그 헤더/가드 바이트(디버그 빌드의 경우) 관리가 추가된다. 즉 `malloc`을 리버싱할 때 디스어셈블리 안쪽 깊숙이 `HeapAlloc` 호출이 보인다면 그것이 바로 실제 할당이 일어나는 지점이다. 최적화/정적 링크된 릴리즈 빌드에서는 `malloc`이라는 이름이 안 보이고 `HeapAlloc`만 직접 보이는 경우도 흔하다.

### 왜 리버싱에서 중요한가
- 힙 오버플로우(CTF pwn 스타일 문제)를 찾을 때: `HeapAlloc(h, 0, 0x20)`으로 32바이트를 할당했는데 이후 `memcpy`나 수동 복사 루프가 32바이트보다 많이 쓴다면 힙 버퍼 오버플로우다.
- Use-after-free를 찾을 때: `HeapFree` 호출 이후에도 같은 포인터 변수가 재초기화 없이 다시 역참조되는지 데이터 흐름을 추적한다.
- 악성코드가 문자열/설정값을 정적 문자열이 아니라 런타임에 힙 버퍼를 만들어 바이트 단위로 채워 넣는 경우, Strings 창만으로는 값을 볼 수 없으므로 `HeapAlloc` 반환 주소를 추적해 동적으로 확인해야 한다.

## 화면/코드에서 보이는 징후
```asm
call GetProcessHeap
push 20h            ; dwBytes = 32
push 0                ; dwFlags
push eax              ; hHeap
call HeapAlloc
mov  [buf], eax
```
- `GetProcessHeap` 반환값이 곧바로 `HeapAlloc`의 첫 인자로 쓰이는 패턴이 반복해서 등장.
- `HeapAlloc` 반환 포인터에 대해 이후 `HeapFree`가 호출된 뒤, 코드 뒷부분에서 같은 포인터를 다시 `mov`/`cmp`하는 흐름이 있으면 UAF 후보.

## 가장 먼저 할 것
`HeapAlloc` 호출을 발견하면 `dwBytes`(세 번째 인자) 값을 먼저 확인한다. 이 값이 상수인지, 아니면 사용자 입력(예: 파일 크기, 네트워크 패킷 길이)에서 그대로 온 변수인지가 취약점 여부를 가르는 첫 단서다.

## 단계별 절차
**1) 할당 크기와 실제 쓰기 크기 대조(IDA)**
`HeapAlloc` 반환 포인터가 이후 어떤 루프/`memcpy` 호출의 목적지로 쓰이는지 `X`(xref)로 추적하고, 그 복사 크기를 `dwBytes`와 비교한다.

**2) x64dbg로 동적 확인**
```text
bp HeapAlloc
run
Ctrl+F9              ; 실행 till return
; RAX(x64) = 할당된 버퍼 주소, Dump 창에서 Follow
```
그 버퍼 주소에 `Hardware, Access`(쓰기 감시) 브레이크포인트를 걸면, 실제로 몇 바이트가 어디까지 쓰이는지 실행하며 직접 확인할 수 있다.

**3) HeapFree 이후 재참조 확인**
`HeapFree`가 호출된 주소를 기록해두고, 이후 코드에서 같은 포인터 변수가 새 값으로 초기화되지 않은 채 다시 읽히는지 데이터 흐름을 추적한다.

## 명령어/단축키
- x64dbg: `bp HeapAlloc`, `bp HeapFree`, `Ctrl+F9`(Execute till return)
- x64dbg: 버퍼 주소 우클릭 → `Breakpoint > Hardware, Access`로 쓰기 범위 감시
- IDA: `X`(xref), `F5`(디컴파일)로 `HeapAlloc(GetProcessHeap(), 0, n)` 형태를 한눈에 확인

## 출력 해석
- `HeapAlloc`이 `NULL`(0)을 반환하면 할당 실패다(`HEAP_GENERATE_EXCEPTION` 플래그가 없을 때).
- `HeapFree`가 `TRUE`(0이 아닌 값)를 반환하면 정상 해제된 것이며, 잘못된 포인터를 넘기면 `FALSE`를 반환하거나(경우에 따라) 힙 손상으로 프로그램이 그 자리에서 크래시할 수 있다.
- 디버그 빌드의 힙은 해제된 블록을 특정 패턴(`0xFEEEFEEE` 등, MSVC CRT 디버그 힙 관례)으로 채우는 경우가 있어, 덤프에서 이런 패턴이 보이면 이미 해제된 영역을 보고 있다는 신호다.

## 흔한 실수
- `dwBytes`가 상수라서 안전하다고 단정하고 실제 쓰기 루프의 반복 횟수(별도 변수로 제어될 수 있음)를 확인하지 않는 것.
- `HeapFree` 호출 자체를 못 보고 지나쳐서 use-after-free 가능성을 놓치는 것 — `X`(xref)로 해당 포인터 변수의 모든 사용처를 반드시 나열해야 한다.
- `HeapAlloc`과 `VirtualAlloc`(REV-0508)을 같은 것으로 혼동하는 것 — 전자는 작은 단위의 범용 버퍼용 힙 관리자를 거치고, 후자는 페이지 단위의 저수준 가상 메모리 할당이라는 점에서 용도가 다르다.
- 같은 포인터에 대해 `HeapFree`를 두 번 호출하는 더블 프리(double free) 코드를 놓치는 것 — 두 번째 `HeapFree` 호출 시점에 힙 관리자 내부 구조가 이미 손상되어 있을 수 있으므로, 반환값이 `FALSE`이거나 이후 다른 `HeapAlloc`/`HeapFree` 호출이 예상과 다르게 동작한다면 더블 프리를 의심해야 한다.
- `hHeap` 인자가 항상 `GetProcessHeap()`일 것이라 가정하는 것 — 일부 프로그램은 `HeapCreate`로 별도 전용 힙을 만들어 특정 목적(예: 문자열 전용, 네트워크 버퍼 전용)에 쓰므로, `hHeap` 값이 여러 종류라면 그 힙들이 서로 다른 용도로 분리되어 있다는 뜻일 수 있다.

## 막혔을 때 다음 체크
- 페이지 단위의 저수준 메모리 할당과 비교하고 싶다면 → REV-0508 WinAPI 메모리 함수 사전: VirtualAlloc VirtualProtect
- 힙에 할당된 영역의 속성을 조회하고 싶다면 → REV-0509 WinAPI 메모리 함수 사전: VirtualQuery VirtualFree
- 문자열이 아니라 CRT 메모리 복사 함수(`memcpy_s` 등) 쪽 오버플로우가 궁금하다면 → REV-0517 Windows CRT 메모리 함수 사전: memcpy_s memmove_s

## 미니 예제
```c
HANDLE hHeap = GetProcessHeap();
char *buf = (char *)HeapAlloc(hHeap, HEAP_ZERO_MEMORY, 0x20); // 32바이트, 0으로 초기화
strcpy(buf, userInput);  // userInput이 32바이트보다 길면 힙 오버플로우
...
HeapFree(hHeap, 0, buf);
...
printf("%s", buf);       // HeapFree 이후 재사용 — use-after-free
```

## 관련 글
- REV-0508 — WinAPI 메모리 함수 사전: VirtualAlloc VirtualProtect
- REV-0509 — WinAPI 메모리 함수 사전: VirtualQuery VirtualFree
- REV-0517 — Windows CRT 메모리 함수 사전: memcpy_s memmove_s

## 출처/검증
- `HeapAlloc`/`HeapFree`/`GetProcessHeap`의 시그니처와 `HEAP_ZERO_MEMORY` 등 플래그는 Microsoft 공식 문서(learn.microsoft.com, "HeapAlloc function" / "HeapFree function") 기준이다(2026-09-08 확인).
- MSVC CRT `malloc`이 내부적으로 `HeapAlloc`을 사용한다는 점과 디버그 힙 채움 패턴은 일반적인 MSVC 런타임 리버싱 관례 레퍼런스 기준이다.
