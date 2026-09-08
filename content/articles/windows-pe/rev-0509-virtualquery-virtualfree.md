---
id: REV-0509
title: "WinAPI 메모리 함수 사전: VirtualQuery VirtualFree"
slug: "rev-0509-virtualquery-virtualfree"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["VirtualQuery", "VirtualFree", "MEMORY_BASIC_INFORMATION", "MEM_RELEASE", "MEM_DECOMMIT", "메모리 영역 조회"]
aliases: ["버추얼쿼리", "버추얼프리", "메모리 베이직 인포메이션", "메모리 영역 정보 조회 함수"]
symptom_keywords: ["VirtualQuery가 뭘 확인하는지 모르겠다", "MEMORY_BASIC_INFORMATION 구조체가 뭔지 모르겠다", "VirtualFree로 메모리를 해제하는 코드를 발견했다", "메모리 보호 속성을 검사하는 안티덤프 코드 같다", "MEM_RELEASE MEM_DECOMMIT 차이를 모르겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`VirtualQuery`는 특정 주소가 속한 메모리 영역의 크기·상태·보호 속성을 `MEMORY_BASIC_INFORMATION` 구조체로 조회하는 함수이고 `VirtualFree`는 `VirtualAlloc`으로 확보한 메모리를 반환하는 함수로, 전자는 안티덤프/안티디버깅 코드가 자기 메모리 속성을 스스로 검사할 때, 후자는 언패킹이 끝난 뒤 임시로 쓴 압축 버퍼를 정리할 때 자주 등장한다.

## 언제 검색해야 하나
- `VirtualQuery`가 반환한 구조체의 `State`나 `Protect` 필드를 검사해서 무언가를 판단하는 코드를 발견했을 때, 그것이 무엇을 검사하는지 알아내야 할 때
- 자기 자신의 `.text` 섹션 보호 속성이 `PAGE_EXECUTE_READ`가 아니면 이상 동작하는(디버거가 소프트웨어 브레이크포인트를 심느라 페이지 속성을 바꿔둔 흔적을 검사하는) 안티디버깅 코드를 만났을 때
- `VirtualFree` 호출을 보고 이 메모리가 완전히 해제(`MEM_RELEASE`)되는지, 아니면 커밋만 취소(`MEM_DECOMMIT`)되는지 구분해야 할 때
- 메모리 덤프 도구를 만들거나 디버거로 메모리 맵을 조사할 때 내부적으로 어떤 API가 쓰이는지 이해하고 싶을 때

## 핵심 개념

### 함수 시그니처
```c
SIZE_T VirtualQuery(
    LPCVOID                   lpAddress, // 1. 조회할 주소
    PMEMORY_BASIC_INFORMATION lpBuffer,  // 2. 결과가 채워질 구조체 주소
    SIZE_T                    dwLength   // 3. lpBuffer의 크기(보통 sizeof(MEMORY_BASIC_INFORMATION))
);

BOOL VirtualFree(
    LPVOID lpAddress, // 1. 해제할 메모리 시작 주소(VirtualAlloc이 반환한 값)
    SIZE_T dwSize,    // 2. 해제할 크기 — MEM_RELEASE 시 반드시 0이어야 함
    DWORD  dwFreeType // 3. MEM_DECOMMIT(0x4000) 또는 MEM_RELEASE(0x8000)
);
```

### MEMORY_BASIC_INFORMATION 구조체
```c
typedef struct _MEMORY_BASIC_INFORMATION {
    PVOID  BaseAddress;       // 이 영역의 시작 주소
    PVOID  AllocationBase;    // VirtualAlloc으로 처음 할당됐을 때의 시작 주소
    DWORD  AllocationProtect; // 처음 할당 시 지정된 보호 속성
    SIZE_T RegionSize;        // 같은 상태/속성을 공유하는 연속 영역의 크기
    DWORD  State;             // MEM_COMMIT(0x1000) / MEM_RESERVE(0x2000) / MEM_FREE(0x10000)
    DWORD  Protect;           // 현재 보호 속성(PAGE_* 상수, REV-0508 참고)
    DWORD  Type;              // MEM_IMAGE(0x1000000, PE 이미지) / MEM_MAPPED / MEM_PRIVATE
} MEMORY_BASIC_INFORMATION;
```
`lpAddress`로 넘긴 주소가 정확히 페이지 경계가 아니어도, 그 주소가 속한 "같은 속성을 가진 연속 영역 전체"의 정보를 한 번에 돌려준다는 점이 핵심이다.

### VirtualFree의 dwFreeType
```text
MEM_DECOMMIT  0x4000  // 물리 메모리(페이지 파일) 배정만 취소, 주소 공간 예약은 유지 — dwSize 지정 가능
MEM_RELEASE   0x8000  // 주소 공간 예약 자체를 완전히 해제 — 이 경우 dwSize는 반드시 0, lpAddress는 반드시 VirtualAlloc이 반환한 원래 주소여야 함
```

### 왜 리버싱에서 중요한가
- `Type`이 `MEM_IMAGE`이면 PE 파일이 그대로 매핑된 영역(원본 EXE/DLL)이라는 뜻이고, `MEM_PRIVATE`이면 `VirtualAlloc`/`HeapAlloc` 등으로 프로세스가 직접 만든 영역(언패킹된 코드가 있을 가능성이 높은 곳)이라는 뜻이다. 메모리 덤프 도구(Scylla, PE-sieve 등)는 내부적으로 `VirtualQuery`를 반복 호출해 전체 주소 공간을 훑으며 `MEM_IMAGE`가 아닌 실행 가능 영역을 찾아 언패킹된 코드를 찾아낸다.
- 일부 안티디버깅/안티덤프 코드는 `VirtualQuery`로 자기 `.text` 섹션의 `Protect` 값을 스스로 확인해, 디버거가 소프트웨어 브레이크포인트(`0xCC`)를 심으려고 페이지 속성을 바꾼 흔적이 있는지 검사한다.
- `VirtualFree(ptr, 0, MEM_RELEASE)` 호출은 언패킹이 끝난 뒤 압축된 원본 데이터를 담았던 임시 버퍼를 정리하는 마무리 단계에서 자주 나타난다.

## 화면/코드에서 보이는 징후
```asm
lea  eax, [mbi]
push 1Ch                 ; sizeof(MEMORY_BASIC_INFORMATION)
push eax
push [addr]
call VirtualQuery
mov  eax, [mbi.Protect]
cmp  eax, 20h             ; PAGE_EXECUTE_READ
jne  tamper_detected
```
- `MEMORY_BASIC_INFORMATION` 구조체의 특정 오프셋(`Protect`는 x86에서 +0x14, x64에서 +0x20 부근)만 골라 읽어 비교하는 코드.
- `VirtualFree` 호출 시 세 번째 인자가 `0x8000`(MEM_RELEASE)이면서 두 번째 인자(`dwSize`)가 항상 `0`으로 고정된 패턴.

## 가장 먼저 할 것
`VirtualQuery` 호출을 발견하면 결과 구조체에서 실제로 어느 필드(`State`, `Protect`, `Type` 중 무엇)를 읽어 비교하는지부터 확인한다. 어느 필드를 보는지에 따라 "메모리 존재 여부 확인"인지 "보호 속성 위변조 탐지"인지 "이미지/사설 메모리 구분"인지 목적이 갈린다.

## 단계별 절차
**1) x64dbg로 결과 구조체 확인**
```text
bp VirtualQuery
run
Ctrl+F9              ; 실행 till return
; 두 번째 인자(lpBuffer)로 넘긴 주소를 Dump 창에서 Follow
; State/Protect/Type 필드를 오프셋 계산해서 직접 확인
```
**2) 비교 대상 값 기록**
반환 후 코드가 `mbi.Protect`를 어떤 상수와 비교하는지(`0x20`=PAGE_EXECUTE_READ, `0x40`=PAGE_EXECUTE_READWRITE 등, REV-0508 참고) IDA에서 확인한다.

**3) VirtualFree 호출부 확인**
`dwFreeType`이 `MEM_RELEASE`(0x8000)인지 `MEM_DECOMMIT`(0x4000)인지 확인하고, 해제되는 주소가 앞서 `VirtualAlloc`으로 언패킹 버퍼를 만들었던 그 주소와 같은지 대조한다.

## 명령어/단축키
- x64dbg: `bp VirtualQuery`, `bp VirtualFree`, `Ctrl+F9`
- x64dbg: Dump 창에서 구조체 시작 주소로 이동 후 `Ctrl+G`로 오프셋 계산, 우클릭 → `Follow in Dump`
- IDA: 구조체 타입 적용(`Structures` 창에 `MEMORY_BASIC_INFORMATION` 추가 후 `Alt+Q`로 필드에 이름 부여)

## 출력 해석
- `VirtualQuery`의 반환값은 실제로 채워진 바이트 수이며, `0`이면 실패한 것이다(주소가 유효하지 않을 때 등).
- `State`가 `MEM_FREE`(0x10000)이면 그 주소는 아직 아무것도 할당되지 않은 영역이므로 접근 시 접근 위반(access violation)이 발생한다.
- `VirtualFree`가 `FALSE`(0)를 반환했다면 `dwSize`/`lpAddress` 조합이 `dwFreeType`과 맞지 않는 등의 인자 오류일 가능성이 크므로 `GetLastError()`를 함께 확인한다.

## 흔한 실수
- `MEM_RELEASE`를 쓰면서 `dwSize`에 0이 아닌 값을 넣어 호출 자체가 실패하는 코드를 놓치는 것 — `MEM_RELEASE`는 반드시 `dwSize=0`이어야 한다.
- `VirtualQuery`가 조회하는 필드를 확인하지 않고 "메모리 관련 API니까 안티덤프겠지"라고 성급히 단정하는 것 — 단순히 특정 주소가 유효한지(`State != MEM_FREE`)만 확인하는 안전성 체크일 수도 있다.
- `RegionSize`를 "그 주소 하나의 크기"로 오해하는 것 — 실제로는 "같은 속성을 공유하는 연속 영역 전체의 크기"이므로 필요한 특정 페이지만 딱 가리키지는 않는다.

## 막혔을 때 다음 체크
- 애초에 이 메모리가 어떻게 할당됐는지 궁금하면 → REV-0508 WinAPI 메모리 함수 사전: VirtualAlloc VirtualProtect
- 힙 기반 할당/해제와 비교하고 싶다면 → REV-0510 WinAPI 메모리 함수 사전: HeapAlloc HeapFree
- 다른 프로세스의 메모리를 조회/읽는 흐름이라면 → REV-0511 WinAPI 메모리 함수 사전: ReadProcessMemory WriteProcessMemory

## 미니 예제
```c
MEMORY_BASIC_INFORMATION mbi;
VirtualQuery((LPCVOID)0x00401000, &mbi, sizeof(mbi));
if (mbi.Protect != PAGE_EXECUTE_READ) {
    // .text 섹션 보호 속성이 원래와 다르다 — 디버거의 소프트웨어 브레이크포인트 삽입 흔적 의심
    ExitProcess(1);
}
// ... 이후 임시 버퍼 정리
VirtualFree(tempBuf, 0, MEM_RELEASE);
```

## 관련 글
- REV-0508 — WinAPI 메모리 함수 사전: VirtualAlloc VirtualProtect
- REV-0510 — WinAPI 메모리 함수 사전: HeapAlloc HeapFree
- REV-0511 — WinAPI 메모리 함수 사전: ReadProcessMemory WriteProcessMemory

## 출처/검증
- `VirtualQuery`/`VirtualFree`의 시그니처, `MEMORY_BASIC_INFORMATION` 구조체 필드, `MEM_DECOMMIT`/`MEM_RELEASE` 상수는 Microsoft 공식 문서(learn.microsoft.com, "VirtualQuery function" / "VirtualFree function" / "MEMORY_BASIC_INFORMATION structure") 기준이다(2026-09-08 확인).
- 메모리 덤프 도구가 `VirtualQuery`를 이용해 언패킹된 영역을 찾는 원리는 일반적인 언패킹 도구(Scylla, PE-sieve) 동작 방식 레퍼런스 기준이다.
