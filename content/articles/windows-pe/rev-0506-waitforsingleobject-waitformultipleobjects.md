---
id: REV-0506
title: "WinAPI 스레드 함수 사전: WaitForSingleObject WaitForMultipleObjects"
slug: "rev-0506-waitforsingleobject-waitformultipleobjects"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["WaitForSingleObject", "WaitForMultipleObjects", "동기화 함수", "커널 오브젝트 대기", "INFINITE", "WAIT_TIMEOUT", "WAIT_OBJECT_0"]
aliases: ["웨이트포싱글오브젝트", "웨이트포멀티플오브젝트", "스레드 join 함수", "이벤트 뮤텍스 대기 API", "스레드 대기 함수"]
symptom_keywords: ["WaitForSingleObject가 언제 끝나는지 모르겠다", "INFINITE로 계속 멈춰 있는 것 같다", "WAIT_TIMEOUT 반환값이 뭔지 모르겠다", "여러 핸들을 동시에 기다리는 함수를 찾고 있다", "스레드가 끝날 때까지 기다리는 코드를 찾고 있다", "unpacking 스레드 종료를 기다리는 패턴인지 확인하고 싶다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`WaitForSingleObject`와 `WaitForMultipleObjects`는 프로세스/스레드/뮤텍스/이벤트 같은 "대기 가능한 커널 오브젝트"의 핸들이 신호(signaled) 상태가 될 때까지 현재 스레드를 멈추는 동기화 함수로, 언패킹 스텁이 별도 스레드의 작업 완료를 기다리는 지점이나 단일 인스턴스 뮤텍스 체크 지점을 찾을 때 자주 마주치게 된다.

## 언제 검색해야 하나
- Import 목록에서 `WaitForSingleObject`/`WaitForMultipleObjects`를 발견했을 때, 이 코드가 정확히 무엇이 끝나기를 기다리는지 알아내고 싶을 때
- `CreateThread` 직후 `WaitForSingleObject(hThread, INFINITE)` 패턴을 보고 "메인 스레드가 다른 스레드 작업을 기다린 뒤 무언가로 점프하는" 언패킹 구조인지 판단해야 할 때
- 반환값이 `WAIT_TIMEOUT`(0x102)인지 `WAIT_OBJECT_0`(0)인지에 따라 분기가 갈리는 코드를 만나 의미를 확인해야 할 때
- 여러 핸들 배열을 넘기는 `WaitForMultipleObjects` 호출에서 몇 번째 핸들이 신호됐는지 계산해야 할 때

## 핵심 개념

### 함수 시그니처
```c
DWORD WaitForSingleObject(
    HANDLE hHandle,        // 1. 대기할 커널 오브젝트 핸들
    DWORD  dwMilliseconds  // 2. 최대 대기 시간(ms), INFINITE(0xFFFFFFFF)면 무한 대기
);

DWORD WaitForMultipleObjects(
    DWORD        nCount,       // 1. lpHandles 배열의 핸들 개수(최대 MAXIMUM_WAIT_OBJECTS=64)
    const HANDLE *lpHandles,   // 2. HANDLE 배열의 시작 주소
    BOOL         bWaitAll,     // 3. TRUE면 모든 핸들이 신호될 때까지, FALSE면 하나라도 신호되면 반환
    DWORD        dwMilliseconds // 4. 최대 대기 시간(ms)
);
```
두 함수 모두 `kernel32.dll`(내부적으로 `KernelBase.dll`)에서 제공하며, `hHandle`은 프로세스(`CreateProcess`가 반환한 `hProcess`), 스레드(`CreateThread`가 반환한 `hThread`), 뮤텍스(`CreateMutex`), 이벤트(`CreateEvent`) 등 "신호/비신호 상태를 가지는" 모든 커널 오브젝트에 적용된다.

### 신호 상태의 의미는 오브젝트 종류마다 다르다
- 프로세스/스레드 핸들: 해당 프로세스/스레드가 **종료**하면 신호 상태가 된다. 즉 `WaitForSingleObject(hThread, INFINITE)`는 사실상 "그 스레드가 끝날 때까지 기다린다"(다른 언어의 `join()`과 동일한 효과)는 뜻이다.
- 이벤트(`CreateEvent`로 만든 핸들): `SetEvent`가 호출되면 신호 상태가 된다.
- 뮤텍스: 아무도 소유하고 있지 않으면 신호 상태이며, `WaitForSingleObject`가 성공하면 호출한 스레드가 소유권을 얻는다.

### 반환값
```text
WAIT_OBJECT_0    0x00000000  // 대기 성공(단일 핸들이거나, 배열의 첫 번째 핸들)
WAIT_ABANDONED   0x00000080  // 뮤텍스를 소유한 스레드가 해제 없이 종료됨
WAIT_TIMEOUT     0x00000102  // dwMilliseconds가 지나도록 신호가 오지 않음
WAIT_FAILED      0xFFFFFFFF  // 오류(GetLastError로 원인 확인)
```
`WaitForMultipleObjects`에서 `bWaitAll=FALSE`이고 여러 핸들 중 하나가 신호되면, 반환값은 `WAIT_OBJECT_0 + i`(`i`는 신호된 핸들의 배열 인덱스, 0부터 시작) 형태로 나온다. 즉 반환값에서 `WAIT_OBJECT_0`을 빼면 몇 번째 핸들이 신호됐는지 알 수 있다.

## 화면/코드에서 보이는 징후
```asm
push 0FFFFFFFFh   ; INFINITE
push [hThread]    ; hHandle
call WaitForSingleObject
```
- `dwMilliseconds` 자리에 `0xFFFFFFFF`(INFINITE)가 그대로 상수로 박혀 있는 경우가 매우 흔하다.
- `CreateThread` 반환값이 곧바로 지역 변수에 저장된 뒤, 몇 줄 뒤 `WaitForSingleObject`의 첫 인자로 다시 로드되는 패턴은 "메인 스레드가 작업 스레드를 기다린다"는 명확한 신호다.
- 반환값(`eax`)을 `cmp eax, 102h`로 비교하는 코드가 있으면 타임아웃 여부를 분기하는 로직이다.

## 가장 먼저 할 것
`WaitForSingleObject`/`WaitForMultipleObjects` 호출 지점을 찾으면, 가장 먼저 첫 번째 인자(핸들)가 어디서 만들어졌는지 위로 거슬러 올라가 확인한다. `CreateThread`, `CreateProcess`, `CreateMutex`, `CreateEvent` 중 어느 것에서 나온 핸들인지에 따라 "무엇을 기다리는 코드인가"의 의미가 완전히 달라진다.

## 단계별 절차
**1) 핸들 출처 추적(IDA)**
`X`(xref)로 `hHandle`에 해당하는 변수가 어디서 초기화되는지 위쪽 코드를 확인한다. Hex-Rays 디컴파일(`F5`)을 쓰면 `hThread = CreateThread(...)` 형태로 훨씬 빠르게 파악된다.

**2) 대기 시간 확인**
`dwMilliseconds`가 `INFINITE`(0xFFFFFFFF)인지, 아니면 특정 ms 값인지 확인한다. 타이밍 기반 안티디버깅에서는 아주 짧은 시간(수백 ms)을 준 뒤 `WAIT_TIMEOUT`이 나오면 정상, `WAIT_OBJECT_0`이 바로 나오면(디버거가 브레이크포인트로 다른 스레드를 멈춰서 원래보다 빨리 신호가 왔다는 등) 이상 상황으로 판단하는 변형도 있으므로 값 자체를 기록해둔다.

**3) x64dbg로 동적 확인**
```text
bp WaitForSingleObject
run
; 진입 시 RCX=hHandle, RDX=dwMilliseconds(x64) 확인
; x86은 [esp+4]=hHandle, [esp+8]=dwMilliseconds
```
핸들 값 자체는 그냥 숫자이므로, Handles 창(x64dbg의 `View > Handles`)에서 같은 값의 핸들이 어떤 종류(Process/Thread/Mutant/Event)인지 확인하면 빠르다.

**4) 반환 후 분기 확인**
`Ctrl+F9`(Execute till return)로 함수를 빠져나온 뒤 `EAX`/`RAX` 값을 확인하고, 그 값을 기준으로 어느 코드 경로로 이어지는지 따라간다.

## 명령어/단축키
- x64dbg: `bp WaitForSingleObject`, `bp WaitForMultipleObjects`, `Ctrl+F9`(Execute till return)
- x64dbg: `View > Handles`로 현재 프로세스가 가진 핸들 목록과 종류 확인
- IDA: `X`(xref), `F5`(Hex-Rays 디컴파일)

## 출력 해석
- `EAX`(x64에서는 `RAX`의 하위 32비트)가 `0`이면 정상적으로 신호를 받아 대기가 풀린 것이다.
- `0x102`(258)이면 시간이 다 되도록 신호가 오지 않은 것이며, 이후 코드가 타임아웃을 "정상"으로 처리하는지 "오류"로 처리하는지가 로직 이해의 핵심이다.
- `0xFFFFFFFF`이면 대기 자체가 실패한 것이므로 `GetLastError`(REV-0519에서 다룸) 결과를 함께 확인해야 원인을 알 수 있다.

## 흔한 실수
- `WaitForSingleObject(hThread, INFINITE)`를 보고 무조건 "언패킹 대기"라고 단정하는 것 — 뮤텍스 대기(단일 인스턴스 체크), 이벤트 대기(스레드 간 신호 전달) 등 목적이 다양하므로 핸들 출처를 반드시 먼저 확인해야 한다.
- `WaitForMultipleObjects`의 반환값에서 `WAIT_OBJECT_0`을 빼는 것을 잊고 인덱스를 잘못 계산하는 것.
- `bWaitAll` 값을 확인하지 않고 "핸들 중 아무거나 하나면 되겠지"라고 넘겨짚는 것 — `TRUE`면 전부 신호될 때까지 실제로 오래 걸릴 수 있다.
- 디버거로 실행 중에는 다른 스레드가 브레이크포인트에 멈춰 있어서 실제 배포 환경보다 대기 시간이 훨씬 길어지거나 아예 타임아웃이 발생할 수 있다는 점을 감안하지 않고 "디버거에서는 왜 다르게 동작하지"라며 헷갈려하는 것 — 멀티스레드 프로그램을 디버깅할 때는 이 차이를 항상 염두에 둬야 한다.
- 짧은 타임아웃(수백 ms)을 준 뒤 `WAIT_TIMEOUT`이 나오는지 여부로 디버거 유무를 판별하는 타이밍 기반 안티디버깅 변형을 놓치고, 단순한 동기화 코드로만 해석하는 것 — 대기 시간이 비정상적으로 짧고 그 결과값으로 분기가 갈린다면 REV-0538(타이밍 기반 안티디버깅)과 함께 살펴봐야 한다.

## 막혔을 때 다음 체크
- 대기 대상 스레드가 어떻게 만들어졌는지 궁금하면 → REV-0505 WinAPI 스레드 함수 사전: CreateThread ExitThread
- 대기 대상이 프로세스라면 → REV-0503 WinAPI 프로세스 함수 사전: CreateProcess 계열
- 핸들을 닫거나 복제하는 후속 처리를 확인하고 싶다면 → REV-0519 WinAPI 핸들 함수 사전: CloseHandle DuplicateHandle GetLastError

## 미니 예제
```c
HANDLE hThread = CreateThread(NULL, 0, UnpackRoutine, NULL, 0, NULL);
WaitForSingleObject(hThread, INFINITE);
// 여기부터는 UnpackRoutine이 완전히 끝난 뒤에만 실행됨 → 원본 OEP로 점프하는 코드가 뒤이어 나오는 경우가 많다
JumpToOEP();
```
x64dbg에서 `bp WaitForSingleObject` 후 멈추면 `RCX`가 방금 `CreateThread`가 반환한 값과 동일함을 Handles 창에서 바로 대조할 수 있다.

## 관련 글
- REV-0505 — WinAPI 스레드 함수 사전: CreateThread ExitThread
- REV-0503 — WinAPI 프로세스 함수 사전: CreateProcess 계열
- REV-0519 — WinAPI 핸들 함수 사전: CloseHandle DuplicateHandle GetLastError

## 출처/검증
- `WaitForSingleObject`/`WaitForMultipleObjects`의 시그니처, 반환값 상수(`WAIT_OBJECT_0`, `WAIT_TIMEOUT`, `WAIT_ABANDONED`, `WAIT_FAILED`)는 Microsoft 공식 문서(learn.microsoft.com, "WaitForSingleObject function" / "WaitForMultipleObjects function") 기준이다(2026-09-08 확인).
- 언패킹 스텁에서의 스레드 대기 패턴은 일반적인 리버싱 관례 레퍼런스 기준이다.
