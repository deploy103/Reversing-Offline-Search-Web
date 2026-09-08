---
id: REV-0566
title: "DllMain에서 실행되는 코드가 있을 때 주의점"
slug: "rev-0566-dllmain-caution"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["DllMain", "DLL_PROCESS_ATTACH", "DLL_THREAD_ATTACH", "loader lock", "로더 락", "DllMain deadlock"]
aliases: ["DllMain 진입점", "DLL 로드 시 실행되는 코드", "DllMain 데드락", "로더 락 문제"]
symptom_keywords: ["DLL을 로드했는데 프로세스가 멈춘다", "LoadLibrary 호출이 끝나지 않는다", "DllMain 안에서 CreateThread 하면 데드락", "DllMain에서 뭘 하길래 이렇게 오래 걸리지"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
DllMain은 DLL이 프로세스에 붙거나(attach) 스레드가 생성/종료될 때, 그리고 DLL이 언로드될 때마다 호출되는 특수한 진입점이며, 이 함수가 실행되는 동안에는 Windows 로더가 잡고 있는 전역 락(로더 락, loader lock)이 걸려 있기 때문에 여기서 무거운 작업이나 다른 DLL 로드, 새 스레드 대기 같은 일을 하면 프로세스 전체가 멈추거나 데드락에 빠질 수 있어, DllMain 안에서 실제 로직이 실행되는 DLL을 분석할 때는 이 제약을 반드시 이해하고 봐야 한다.

## 언제 검색해야 하나
- DLL을 IDA/x64dbg로 열었더니 `DllMain` 함수 안에 `DLL_PROCESS_ATTACH` 분기에서 복잡한 코드(암호화 해제, 안티디버깅, 네트워크 연결 시도 등)가 실행되는 것을 봤을 때
- `LoadLibrary` 호출이 끝나지 않고 멈춰있는 프로세스를 분석하다가 원인이 DllMain 내부 코드인지 의심될 때
- 악성코드 DLL이 프로세스에 인젝션된 뒤 DllMain에서 바로 페이로드를 실행하는 패턴을 만났을 때
- "DllMain에서 CreateThread하면 왜 문제가 되나요"라는 질문에 답이 필요할 때

## 핵심 개념
`DllMain`은 사용자가 직접 호출하는 함수가 아니라, Windows 로더가 특정 시점마다 자동으로 호출하는 콜백이다. 시그니처는 다음과 같다.

```c
BOOL WINAPI DllMain(
    HINSTANCE hinstDLL,  // DLL의 모듈 핸들 (베이스 주소)
    DWORD     fdwReason,  // 호출 이유
    LPVOID    lpvReserved // 정적/동적 로드 여부 등
);
```

`fdwReason`은 다음 네 가지 값 중 하나로, `DLL_PROCESS_ATTACH`(1), `DLL_THREAD_ATTACH`(2), `DLL_THREAD_DETACH`(3), `DLL_PROCESS_DETACH`(0)이다. IDA 디컴파일 결과에서 `switch(fdwReason)` 형태로 보이는 경우가 많다.

가장 중요한 사실은 **DllMain이 실행되는 동안 로더 락(loader lock, 내부적으로 `ntdll!LdrpLoaderLock`이라는 임계 구역/critical section)이 걸려 있다**는 것이다. 이 락은 Windows 로더가 모듈 리스트(PEB의 `Ldr` 구조체)를 안전하게 조작하기 위해 사용하는데, 문제는 다음과 같은 동작들이 **같은 락을 기다리기 때문에** DllMain 안에서 실행되면 데드락이 발생할 수 있다는 점이다.

- DllMain 안에서 `LoadLibrary`로 다른 DLL을 새로 로드하는 것 (로더 락을 재획득하려다 자기 자신과 충돌할 수 있음)
- DllMain 안에서 `CreateThread`로 새 스레드를 만들고, 그 스레드가 끝나기를 `WaitForSingleObject` 등으로 대기하는 것 (새 스레드가 시작할 때 자신도 DLL_THREAD_ATTACH 처리를 위해 로더 락을 기다려야 하는데, 원본 스레드가 락을 쥔 채 대기 중이라 서로 멈춤)
- DllMain 안에서 콘솔 I/O(`printf`, `AllocConsole`)나 `OleInitialize`, `CoCreateInstance` 등 내부적으로 다른 DLL을 지연 로드하는 API를 호출하는 것
- 이런 문제를 Microsoft 공식 문서(Dynamic-Link Library Best Practices)도 명시적으로 경고하고 있으며, DllMain에서는 "간단한 초기화(전역 변수 설정, 임계 구역 생성 등)만 하라"고 권장한다.

리버싱 관점에서 이 지식이 중요한 이유는, 악성 DLL이나 패커가 일부러 DllMain의 `DLL_PROCESS_ATTACH` 분기에 실제 페이로드 실행 로직(복호화, 인젝션, C2 연결)을 넣는 경우가 흔하기 때문이다. 이는 `rundll32.exe`로 실행되거나 다른 프로세스에 인젝션(REV-0568 프로세스 할로잉 참고)될 때 자동으로 코드가 실행되게 만드는 손쉬운 방법이다. 반대로 분석 관점에서는, 로더 락 제약 때문에 DllMain 안에서는 새 스레드를 만들고 그 안에서 무거운 작업(네트워크, 파일 I/O 등)을 수행한 뒤 즉시 리턴하는 패턴이 "정상적으로 잘 만들어진" 코드에서도, "탐지를 피하려는" 악성코드에서도 공통적으로 나타난다는 점을 알아두면 코드 구조를 읽을 때 도움이 된다.

## 화면/코드에서 보이는 징후
- IDA Imports 뷰에서 `DllMain`이 Export되어 있고, 함수 시작부에서 `fdwReason`(두 번째 인자, x64에서는 `edx`)을 비교하는 `cmp`/`switch` 패턴이 보임
- `DLL_PROCESS_ATTACH`(값 1) 분기 안에 문자열 복호화 루프, `VirtualAlloc`, `CreateThread`, 네트워크 API(`WSAStartup`, `connect`) 등이 보임 — 페이로드가 DllMain에 직접 박혀 있는 신호
- x64dbg로 DLL을 붙여서 실행했을 때, `LoadLibrary` 호출이 리턴하지 않고 프로세스가 멈춘 상태로 유지됨
- DllMain 안에서 `CreateThread` 호출 직후 `WaitForSingleObject`나 `Sleep` 루프로 새 스레드 완료를 기다리는 코드 — 데드락 후보 패턴

## 가장 먼저 할 것
1. IDA에서 DLL을 열고 Exports 탭(`Shift+F11`)에서 `DllMain`을 찾아 더블클릭해 진입한다.
2. 디컴파일(`F5`)해서 `fdwReason`에 따른 분기를 확인하고, `DLL_PROCESS_ATTACH`(1) 분기에 실제 로직이 있는지부터 본다. 로직이 있다면 이 DLL은 "로드되는 순간 자동 실행"을 노린 DLL일 가능성이 높다.

## 단계별 절차
**1) DllMain 분기 구조 파악**
- `F5`로 디컴파일된 코드에서 `if ( a2 == 1 )`(`DLL_PROCESS_ATTACH`), `if ( a2 == 2 )`(`DLL_THREAD_ATTACH`) 같은 비교문을 찾는다.
- 각 분기가 호출하는 함수들을 하나씩 따라가며 어떤 이유(reason)에서 무슨 일이 일어나는지 표로 정리한다. 대부분의 악성 페이로드는 `DLL_PROCESS_ATTACH`에 몰려 있다.

**2) 로더 락 관련 위험 코드 식별**
- `DLL_PROCESS_ATTACH` 분기 안에서 `LoadLibraryA`/`LoadLibraryW`, `CreateThread` + `WaitForSingleObject` 조합, `CoInitialize` 계열 API가 있는지 확인한다.
- 이런 코드가 있다면 실제 실행 시 타이밍에 따라 멈추거나(데드락), 정상 실행되거나 하는 불안정한 동작을 보일 수 있으므로, 동적 분석 시 "이번엔 멈추지 않았다"고 안심하지 말고 여러 번 재현을 시도해야 한다.

**3) x64dbg로 로드 시점 추적**
- `rundll32.exe`나 테스트용 로더 EXE에 대상 DLL을 붙여서 x64dbg로 실행한다.
- `Options → Preferences → Events`에서 "DLL Load"(DLL 로드) 이벤트에 자동 정지가 걸리도록 설정하면, 대상 DLL이 매핑되는 시점에 멈춘다.
- DllMain 주소에 브레이크포인트(`F2`)를 걸고 `F9`로 실행을 재개해 실제로 `DLL_PROCESS_ATTACH`에서 어떤 코드가 실행되는지 스텝(`F7`/`F8`)으로 따라간다.

**4) 데드락 재현 시 대응**
- 분석 중 프로세스가 응답 없음 상태가 되면, 이는 버그가 아니라 DllMain 안에서 로더 락을 기다리는 데드락일 수 있다. x64dbg에서 각 스레드의 콜스택(`Threads` 창)을 확인해 `ntdll!LdrpAcquireLoaderLock` 근처에서 멈춘 스레드가 있는지 본다.
- 이 경우 분석용으로는 해당 분기를 패치(조건을 강제로 건너뛰게)하거나, 문제되는 API 호출 지점에 브레이크포인트를 걸고 강제로 리턴시켜 우회하는 방법을 쓴다.

## 명령어/단축키
- IDA: `Shift+F11`(Exports 뷰), `F5`(디컴파일), `X`(교차 참조)
- x64dbg: `Options → Preferences → Events → DLL Load` 체크, `F2`(브레이크포인트), `F7`/`F8`(스텝), `Threads` 창으로 각 스레드 콜스택 확인

## 출력 해석
- `fdwReason == 1`(`DLL_PROCESS_ATTACH`)에서 반환값이 `FALSE`면 로더가 이 DLL 로드를 실패로 처리하고 프로세스에서 언로드한다. 악성 DLL이 특정 환경(디버거 감지 등)에서 일부러 `FALSE`를 리턴해 조용히 사라지는 패턴도 있다.
- 스레드 목록에서 두 스레드가 서로 다른 락을 기다리는 상태(A는 로더 락을 쥐고 B의 종료를 기다리고, B는 로더 락을 기다림)로 멈춰 있으면 전형적인 데드락이다.

## 흔한 실수
- DllMain 안의 코드를 "그냥 초기화 코드겠지"라고 넘겨짚고 자세히 안 보는 것. 실제로는 여기가 페이로드의 진짜 시작점인 경우가 많다.
- 동적 분석에서 한 번 멈추지 않고 잘 실행됐다고 해서 로더 락 문제가 없다고 결론짓는 것. 타이밍에 따라 재현되는 경우가 있다.
- `DLL_THREAD_ATTACH`/`DLL_THREAD_DETACH` 분기를 무시하는 것. 일부 DLL은 매 스레드 생성마다 안티디버깅 체크나 카운터 증가를 여기서 수행한다.
- DllMain의 반환값을 확인하지 않고 넘어가는 것. `FALSE` 반환은 로드 실패를 의미하며 흐름 이해에 중요하다.

## 막혔을 때 다음 체크
- DLL 분석을 처음 시작하는 단계라면 → REV-0135(DLL 문제 분석 시작하기)를 먼저 읽는다.
- DllMain에서 자기 자신을 새 프로세스에 인젝션하거나 실행 흐름을 조작하는 것처럼 보이면 → REV-0568(프로세스 할로잉 개념 소개)을 참고한다.
- DllMain 안에서 API 이름 없이 함수 포인터만 계산해서 호출하는 것 같으면 → REV-0569(API Hashing 개념)를 확인한다.

## 미니 예제
```c
BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved)
{
    if ( fdwReason == DLL_PROCESS_ATTACH )
    {
        HANDLE hThread = CreateThread(NULL, 0, PayloadThread, NULL, 0, NULL);
        WaitForSingleObject(hThread, INFINITE);  // 위험: 로더 락을 쥔 채 대기
    }
    return TRUE;
}
```
이 코드는 `DLL_PROCESS_ATTACH` 안에서 새 스레드를 만든 뒤 그 스레드가 끝날 때까지 기다린다. 문제는 새로 생성된 스레드 자체도 시작할 때 `DLL_THREAD_ATTACH` 통지를 위해 로더 락을 요청해야 하는데, 원본 스레드가 이미 그 락을 쥐고 `WaitForSingleObject`로 블록되어 있으므로 두 스레드가 서로 영원히 기다리는 데드락이 발생한다. 실전에서 이런 코드를 만나면 리버서는 `PayloadThread`가 실제로 페이로드를 실행하는 함수라는 것과, 원작성자가 로더 락 규칙을 어겼거나(버그) 혹은 일부러 특정 조건에서만 데드락을 유도해 분석을 방해하려 한 것인지 구분해서 판단해야 한다.

## 관련 글
- REV-0135 — DLL 문제 분석 시작하기
- REV-0568 — 프로세스 할로잉(Process Hollowing) 개념 소개
- REV-0569 — Import 함수를 런타임에 해시로 찾는 API Hashing 개념
- REV-0567 — Reflective DLL Loading 개념 소개

## 출처/검증
- `DllMain` 시그니처와 `fdwReason` 값은 Microsoft Learn "DllMain entry point" 공식 문서 기준이다.
- 로더 락과 DllMain 제약사항(다른 DLL 로드 금지, 스레드 동기화 대기 금지 등)은 Microsoft "Dynamic-Link Library Best Practices" 문서에서 명시적으로 다루는 내용이다.
- 데드락 재현 조건은 타이밍에 의존적이므로 실습 시 여러 번 반복 실행하여 확인할 것을 권장한다(2026-09-08 기준 서술).
