---
id: REV-0508
title: "WinAPI 메모리 함수 사전: VirtualAlloc VirtualProtect"
slug: "rev-0508-virtualalloc-virtualprotect"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["VirtualAlloc", "VirtualProtect", "PAGE_EXECUTE_READWRITE", "MEM_COMMIT", "언패킹", "self-modifying code", "메모리 보호 속성"]
aliases: ["버추얼알록", "버추얼프로텍트", "RWX 메모리 할당", "메모리 실행 권한 변경 함수"]
symptom_keywords: ["VirtualAlloc으로 뭘 하는지 모르겠다", "PAGE_EXECUTE_READWRITE가 뭔지 모르겠다", "언패킹 스텁을 찾고 있다", "VirtualProtect로 보호 속성을 바꾸는 코드를 발견했다", "새로 할당한 메모리로 점프하는 코드가 있다", "OEP를 못 찾겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`VirtualAlloc`은 새 메모리 페이지를 할당하고 `VirtualProtect`는 기존 페이지의 읽기/쓰기/실행 권한을 바꾸는 함수로, 언패커가 원본 코드를 복호화해 담을 공간을 만들거나(`VirtualAlloc` + `PAGE_EXECUTE_READWRITE`) 이미 로드된 `.text` 섹션을 쓰기 가능하게 바꿔 코드를 패치하는(`VirtualProtect`) 지점을 찾을 때 반드시 알아야 하는 API 쌍이다.

## 언제 검색해야 하나
- 패킹된 실행 파일을 분석하며 "언패킹된 코드가 어디에 풀리는가"를 찾아야 할 때
- `VirtualAlloc`으로 새로 할당된 메모리 영역에 데이터가 복사된 뒤 그쪽으로 `jmp`/`call`이 이어지는 흐름(OEP 진입점 후보)을 추적해야 할 때
- 읽기 전용이어야 할 `.text` 섹션에 값을 쓰는 self-modifying code를 발견해 그 직전에 `VirtualProtect` 호출이 있는지 확인해야 할 때
- 셸코드나 인젝션 페이로드가 `PAGE_EXECUTE_READWRITE`(RWX) 권한의 메모리를 만드는지 확인하고 싶을 때

## 핵심 개념

### 함수 시그니처
```c
LPVOID VirtualAlloc(
    LPVOID lpAddress,        // 1. 원하는 시작 주소(NULL이면 시스템이 알아서 선택)
    SIZE_T dwSize,           // 2. 할당할 바이트 수
    DWORD  flAllocationType, // 3. MEM_COMMIT / MEM_RESERVE / MEM_RESET 등의 조합
    DWORD  flProtect         // 4. 페이지 보호 속성(PAGE_* 상수)
);

BOOL VirtualProtect(
    LPVOID lpAddress,      // 1. 대상 메모리 시작 주소
    SIZE_T dwSize,         // 2. 바꿀 영역의 바이트 수
    DWORD  flNewProtect,   // 3. 새로 적용할 보호 속성(PAGE_* 상수)
    PDWORD lpflOldProtect  // 4. 이전 보호 속성이 저장될 DWORD 주소(반드시 유효한 주소여야 함)
);
```
둘 다 `kernel32.dll`이 제공하며, 대상 페이지가 존재해야 하는(`VirtualAlloc`으로 이미 커밋된) `VirtualProtect`와 달리 `VirtualAlloc`은 새 영역을 확보한다는 점이 근본적인 차이다.

### flAllocationType 주요 값
```text
MEM_COMMIT   0x1000  // 실제 물리 메모리(페이지 파일)를 배정
MEM_RESERVE  0x2000  // 주소 공간만 예약, 아직 메모리는 배정 안 함
MEM_RESET    0x80000 // 페이지 내용을 더 이상 신경 쓰지 않는다고 표시
```
`MEM_COMMIT | MEM_RESERVE`(0x3000)를 함께 쓰는 것이 가장 흔한 패턴이다.

### flProtect / flNewProtect 주요 값
```text
PAGE_NOACCESS          0x01
PAGE_READONLY           0x02
PAGE_READWRITE          0x04
PAGE_EXECUTE            0x10
PAGE_EXECUTE_READ       0x20
PAGE_EXECUTE_READWRITE  0x40  // 읽기/쓰기/실행 모두 가능(RWX) — 언패커/셸코드에서 매우 흔함
PAGE_GUARD              0x100 (조합 플래그)
```
정상적인 컴파일러가 생성한 `.text` 섹션은 보통 `PAGE_EXECUTE_READ`로 매핑되며, 코드 영역이 `PAGE_READWRITE`나 `PAGE_EXECUTE_READWRITE`로 바뀌는 순간은 "이 프로그램이 자기 코드를 스스로 수정하려 한다"는 강한 신호다.

### 왜 리버싱/언패킹에서 핵심 API인가
UPX 같은 단순 패커부터 상용 프로텍터까지, 압축/암호화된 원본 코드를 실행 전에 복원해야 하므로 다음 3단계 패턴이 거의 항상 등장한다.
1. `VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)`로 쓰기+실행이 모두 가능한 새 영역을 만든다.
2. 그 영역에 압축 해제/복호화된 원본 코드를 채운다(루프로 바이트 단위 복사, 또는 `memcpy`류 호출).
3. 채운 뒤 그 주소로 `jmp`하거나(직접 실행), 필요하면 `VirtualProtect`로 `PAGE_EXECUTE_READ`처럼 실행 전용에 가깝게 권한을 낮춘다.

디버거에서 "RWX로 새로 할당된 메모리에 값을 쓴 뒤 그쪽으로 제어가 넘어가는 지점"을 찾는 것이 언패킹의 핵심 기법 중 하나이며, x64dbg의 "Memory Map" 탭에서 실행 도중 새로 생기는 RWX 영역을 관찰하는 방식으로 이를 실전에서 활용한다.

## 화면/코드에서 보이는 징후
```asm
push 40h            ; PAGE_EXECUTE_READWRITE
push 1000h          ; MEM_COMMIT
push [size]
push 0               ; lpAddress = NULL
call VirtualAlloc
mov  [newbuf], eax
...
; newbuf에 데이터를 채우는 루프
...
jmp  eax             ; 또는 call eax — 새로 할당한 영역으로 제어 이전
```
- Import 목록에 `VirtualAlloc`/`VirtualAllocEx`가 있고, 반환값(할당된 주소)이 이후 메모리 쓰기 루프의 목적지로 쓰이는 패턴.
- `VirtualProtect` 호출 직전 `lpAddress`가 자기 자신의 `.text` 섹션 범위 안의 주소인 경우.

## 가장 먼저 할 것
`VirtualAlloc` 호출에 브레이크포인트를 걸고 `flProtect` 인자가 `0x40`(PAGE_EXECUTE_READWRITE)인지부터 확인한다. RWX 할당이면 거의 확실히 언패킹/코드 생성 목적이므로, 반환값(할당된 주소)을 메모리에 기록해두고 그 주소에 대한 쓰기/실행 접근을 계속 추적한다.

## 단계별 절차
**1) VirtualAlloc 반환값 기록**
```text
bp VirtualAlloc
run
; 인자 확인(x64: RCX=lpAddress, RDX=dwSize, R8=flAllocationType, R9=flProtect)
Ctrl+F9   ; 실행till return
; RAX = 새로 할당된 주소
```
**2) 그 주소에 하드웨어 브레이크포인트 설정**
x64dbg에서 해당 주소를 Dump 창에 띄운 뒤 우클릭 → `Breakpoint > Hardware, Access`(쓰기 감시) 또는 `Hardware, Execute`(실행 감시)를 걸어, 언제 그 영역에 값이 채워지고 언제 실행되는지 추적한다.

**3) VirtualProtect 호출 확인**
`.text` 섹션 주소 범위 안에서 `VirtualProtect`가 불리면 self-modifying code 가능성이 높으므로 `lpAddress`, `dwSize`, `flNewProtect`를 기록하고 `lpflOldProtect`가 가리키는 값(원래 보호 속성)도 함께 확인한다.

**4) 실행 이전 지점(OEP 후보) 확인**
새로 채워진 영역으로 `jmp`/`call eax`(또는 레지스터)가 발생하는 지점을 IDA에서 표시해두면, 이곳이 언패킹 후 원본 코드의 진입점(OEP)일 가능성이 크다.

## 명령어/단축키
- x64dbg: `bp VirtualAlloc`, `bp VirtualProtect`, `Ctrl+F9`(Execute till return)
- x64dbg: 메모리 주소 우클릭 → `Breakpoint > Hardware, Access/Execute`
- x64dbg: `Memory Map` 탭(Alt+M)에서 RWX(`ERWC` 등으로 표시) 영역 확인
- IDA: `X`(xref), `F5`(디컴파일)

## 출력 해석
- `VirtualAlloc`이 `NULL`(0)을 반환하면 할당 실패이며, `GetLastError()`로 원인을 확인해야 한다.
- `VirtualProtect`가 `TRUE`(0이 아닌 값)를 반환하고 `lpflOldProtect`에 이전 값이 채워졌다면 보호 속성 변경이 성공한 것이다.
- Memory Map에서 `Protect` 열이 `PAGE_EXECUTE_READWRITE`(RWX)로 표시된 영역은 정상 프로그램에서는 드물게 나타나므로 우선 조사 대상으로 표시해둔다.

## 흔한 실수
- `VirtualAlloc`의 `flProtect` 인자만 보고 실제 최종 보호 속성이라 단정하는 것 — 뒤이어 `VirtualProtect`로 다시 바뀔 수 있으므로 이후 흐름까지 확인해야 한다.
- `lpflOldProtect`에 NULL을 넘겨 `VirtualProtect` 호출 자체가 실패하는 코드를 놓치는 것 — 이 인자는 반드시 유효한 `DWORD` 변수의 주소여야 한다.
- RWX 메모리 발견 즉시 "이건 무조건 패커"라고 단정하는 것 — JIT 컴파일러(.NET, 일부 스크립트 엔진)나 정상적인 동적 코드 생성 기능에서도 RWX를 쓸 수 있으므로 주변 문맥을 함께 봐야 한다.

## 막혔을 때 다음 체크
- 할당된 메모리 영역의 속성을 나중에 다시 조회하고 싶다면 → REV-0509 WinAPI 메모리 함수 사전: VirtualQuery VirtualFree
- 다른 프로세스에 메모리를 할당/주입하는 변형(`VirtualAllocEx`)이 궁금하다면 → REV-0511 WinAPI 메모리 함수 사전: ReadProcessMemory WriteProcessMemory
- x64dbg로 실행 파일을 처음 여는 법이 아직 낯설다면 → REV-0127 x64dbg로 EXE 첫 분석 시작

## 미니 예제
```c
LPVOID buf = VirtualAlloc(NULL, unpackedSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
DecompressInto(buf, packedData, packedSize);
((void(*)())buf)();  // 언패킹된 코드로 바로 점프해 실행
```
x64dbg에서 `bp VirtualAlloc` → `Ctrl+F9` → `RAX` 확인 → 그 주소에 `Hardware, Execute` 브레이크포인트를 걸어두면, `DecompressInto`가 끝난 직후 그 영역이 실행되는 순간(위 예제 마지막 줄)에 정확히 멈춰서 언패킹된 코드의 첫 명령어를 바로 볼 수 있다.

## 관련 글
- REV-0509 — WinAPI 메모리 함수 사전: VirtualQuery VirtualFree
- REV-0511 — WinAPI 메모리 함수 사전: ReadProcessMemory WriteProcessMemory
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- `VirtualAlloc`/`VirtualProtect`의 시그니처와 `MEM_*`/`PAGE_*` 상수 값은 Microsoft 공식 문서(learn.microsoft.com, "VirtualAlloc function" / "VirtualProtect function") 기준이다(2026-09-08 확인).
- 언패킹 시 RWX 할당 후 실행 전이 패턴은 일반적인 언패킹/리버싱 관례 레퍼런스 기준이다.
