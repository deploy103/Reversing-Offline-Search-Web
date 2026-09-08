---
id: REV-0565
title: "WinMain wWinMain DllMain 진입점 차이"
slug: "rev-0565-winmain-wwinmain-dllmain"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["WinMain", "wWinMain", "DllMain", "DLL_PROCESS_ATTACH", "mainCRTStartup", "로더 락"]
aliases: ["winmain wwinmain 차이", "dllmain 인자 의미", "dll_process_attach란", "실제 진입점과 winmain 차이"]
symptom_keywords: ["ida 진입점이 winmain이 아니라 다른 함수로 나옴", "dllmain에서 4개 리즌 값이 뭔지 모름", "wwinmain 유니코드 버전", "로더 락 데드락"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`WinMain`/`wWinMain`/`DllMain`은 PE의 `AddressOfEntryPoint`가 실제로 가리키는 진짜 OS 진입점이 아니라, CRT 시작 함수(`WinMainCRTStartup` 등)나 Windows 로더가 준비를 마친 뒤 **호출해주는** 함수일 뿐이며, 셋의 시그니처와 호출 시점, 특히 `DllMain`이 로더 락(loader lock) 아래에서 실행된다는 제약을 구분해서 알아두면 IDA에서 진입점을 헤맬 일이 크게 줄어든다.

## 언제 검색해야 하나
- IDA가 잡아준 진입점(Entry Point)이 `WinMain`이 아니라 알 수 없는 함수로 보여서 당황할 때
- `WinMain`과 `wWinMain`의 차이가 단순히 "유니코드냐 아니냐"인지 궁금할 때
- `DllMain`의 네 번째 인자, `fdwReason` 값(`DLL_PROCESS_ATTACH` 등)이 각각 언제 호출되는지 궁금할 때
- DLL 안에서 `DllMain`이 다른 스레드를 만들거나 다른 DLL을 로드하려다가 멈추는(데드락) 이유를 이해하고 싶을 때
- 실제 EXE 진입점 코드에서 `GetCommandLine`, `GetStartupInfo` 호출이 왜 있는지 궁금할 때

## 핵심 개념

### 진짜 진입점은 WinMain이 아니다
REV-0121에서 다룬 것처럼, PE의 `AddressOfEntryPoint`가 가리키는 실제 OS 진입점은 개발자가 작성하는 `WinMain`/`main`이 아니라, 컴파일러/CRT가 자동으로 붙이는 시작 함수다.

| 개발자가 작성하는 함수 | 실제 OS 진입점(링커가 자동 지정) |
|---|---|
| `main` | `mainCRTStartup` |
| `wmain` | `wmainCRTStartup` |
| `WinMain` | `WinMainCRTStartup` |
| `wWinMain` | `wWinMainCRTStartup` |

이 CRT 시작 함수가 먼저 실행되면서 C 런타임 초기화(전역 변수 생성자 호출, 힙 초기화, 예외 처리기 등록 등)를 마친 뒤, `GetStartupInfoW`로 창 표시 방식 등의 정보를 얻고 `GetCommandLineW`로 명령줄 문자열을 가져와서 인자를 조립한 다음, 비로소 개발자가 작성한 `WinMain`을 호출한다. IDA에서 진입점으로 이동했는데 `main`/`WinMain`처럼 안 보이고 짧고 정형화된 코드가 보인다면 바로 이 CRT 시작 함수를 보고 있는 것이다 — 여기서 `call`되는 함수를 한 단계 더 따라가면 실제 `WinMain`이 나온다.

### WinMain vs wWinMain: ANSI와 유니코드
```c
int WINAPI WinMain(
    HINSTANCE hInstance,      // 현재 모듈(자기 자신)의 인스턴스 핸들
    HINSTANCE hPrevInstance,  // 항상 NULL (Win16 시절의 잔재, 무시해도 됨)
    LPSTR     lpCmdLine,      // ANSI(단일 바이트) 명령줄 문자열, 실행 파일명 제외
    int       nCmdShow        // ShowWindow에 넘길 창 표시 방식(SW_SHOW 등)
);

int WINAPI wWinMain(
    HINSTANCE hInstance,
    HINSTANCE hPrevInstance,
    PWSTR     pCmdLine,       // 유니코드(UTF-16) 명령줄 문자열
    int       nCmdShow
);
```
차이는 오직 `lpCmdLine`/`pCmdLine`의 문자 인코딩뿐이다. `hInstance`는 REV-0135에서 다루는 것처럼 `GetModuleHandle(NULL)`로도 얻을 수 있는 값과 같은 개념 — 자기 자신의 모듈 베이스 주소다. `hPrevInstance`는 항상 `NULL`이므로 리버싱 시 이 인자에 의미를 두지 않아도 된다.

### DllMain: 로더가 호출하는 콜백
```c
BOOL WINAPI DllMain(
    HINSTANCE hinstDLL,   // 이 DLL 자신의 모듈 핸들
    DWORD     fdwReason,  // 왜 호출됐는지
    LPVOID    lpvReserved // 동적/정적 로드 여부에 따라 의미가 다름
);
```
`fdwReason`은 다음 값 중 하나이며, DLL의 생명주기에서 여러 번 다른 시점에 호출된다.

| 값 | 상수 | 호출 시점 |
|---|---|---|
| 1 | `DLL_PROCESS_ATTACH` | DLL이 프로세스에 처음 매핑될 때(로드 시) — 가장 중요, 초기화 코드가 여기 들어감 |
| 2 | `DLL_THREAD_ATTACH` | 프로세스 내에서 새 스레드가 생성될 때(단, 이미 로드된 후에 생성된 스레드에 한함) |
| 3 | `DLL_THREAD_DETACH` | 스레드가 정상 종료될 때 |
| 0 | `DLL_PROCESS_DETACH` | DLL이 프로세스에서 언로드될 때(`FreeLibrary` 또는 프로세스 종료) |

### DllMain과 로더 락(Loader Lock): 초보자가 가장 자주 걸리는 함정
`DllMain`은 **로더 락**이라는 전역 락을 쥔 상태에서 Windows 로더에 의해 호출된다. 이 락이 걸려 있는 동안 `DllMain` 안에서 다음과 같은 행동을 하면 데드락이나 정의되지 않은 동작이 발생할 수 있다.
- 다른 DLL을 새로 `LoadLibrary`하는 것(이미 로드된 DLL에 대한 `GetModuleHandle`은 대체로 안전)
- 새 스레드를 만들고 그 스레드가 끝나기를 `WaitForSingleObject` 등으로 기다리는 것
- 다른 스레드와 동기화 프리미티브로 통신하려는 것

이 제약 때문에 실무에서는 `DllMain`은 최소한의 초기화(전역 변수 세팅, 크리티컬 섹션 초기화 등)만 하고, 무거운 초기화는 별도의 명시적 초기화 함수나 `DLL_THREAD_ATTACH` 이후 시점으로 미루도록 권장된다. 리버싱 관점에서는, 악성코드의 `DllMain`이 유난히 복잡한 로직(네트워크 통신, 복호화 루프 등)을 직접 담고 있다면 "로더 락 문제를 감수하고서라도 여기서 바로 실행되게 만든 이유가 뭘까"를 생각해볼 가치가 있다 — 프로세스 인젝션(REV-0568) 시나리오에서 `DllMain`이 페이로드 실행 지점으로 쓰이는 경우가 흔하기 때문이다.

## 화면/코드에서 보이는 징후
- IDA에서 진입점으로 이동했을 때 `WinMain`이 아니라 `GetStartupInfoW`, `GetCommandLineW`를 호출하는 짧은 함수가 보임 — CRT 시작 함수
- DLL을 IDA로 열었을 때, Export 여부와 무관하게 진입점 함수가 4개 인자(`hinstDLL`, `fdwReason`, `lpvReserved`, 그리고 반환형 `BOOL`)를 가진 형태로 보이면 `DllMain`
- `fdwReason` 값에 따라 분기하는 `switch`/`cmp` 코드가 `DllMain` 초반에 있음 — 각 분기가 `DLL_PROCESS_ATTACH`(1) 등에 대응
- x64dbg로 DLL 로드 순간에 브레이크포인트를 걸면, `DLL_PROCESS_ATTACH`로 호출되는 순간을 실제로 관찰할 수 있음

## 가장 먼저 할 것
IDA에서 EXE 진입점으로 이동했는데 익숙한 코드가 아니라면, 당황하지 말고 그 함수 안에서 호출되는 다른 함수들을 하나씩 따라간다. 보통 `GetStartupInfoW` 호출 직후, 준비된 인자들을 들고 실제 `WinMain`/`main`을 호출하는 지점이 나온다. DLL이라면 Export 함수 목록과 별개로, 진입점 자체가 `DllMain`이라는 것을 먼저 확인하고 `fdwReason` 분기부터 읽는다.

## 단계별 절차

**1) 실제 OS 진입점과 개발자 함수 구분**
`AddressOfEntryPoint`가 가리키는 함수가 CRT 시작 함수인지 확인한다(`GetStartupInfo`/`GetCommandLine` 호출 패턴).

**2) EXE라면 WinMain/wWinMain 구분**
호출되는 함수의 인자 타입에서 세 번째 인자가 단일 바이트 문자열 포인터로 쓰이면 `WinMain`, 유니코드(2바이트 단위) 문자열로 쓰이면 `wWinMain`이다.

**3) DLL이라면 DllMain의 fdwReason 분기부터 확인**
`DLL_PROCESS_ATTACH`(1) 분기가 보통 가장 중요한 초기화 로직을 담고 있다.

**4) DllMain 안에서 위험한 호출이 있는지 점검**
`LoadLibrary`, `CreateThread`+대기, 동기화 API 호출이 있다면 로더 락 관련 제약을 어기고 있을 가능성을 염두에 두고 분석한다.

**5) 동적으로 각 시점 관찰**
x64dbg의 옵션에서 "Break on DLL load/unload"를 켜거나, `DllMain` 시작 지점에 직접 브레이크포인트를 걸어 `fdwReason` 레지스터/스택 값을 실시간으로 확인한다.

## 명령어/단축키
```text
IDA: Jump → Jump to address(G) → AddressOfEntryPoint 값으로 이동
IDA: 진입점 함수 더블클릭으로 호출되는 하위 함수들을 순차 확인
x64dbg: Options → Preferences → Events → "DLL Load"/"DLL Unload" 체크 후
        실행하면 DllMain 호출 시점 근처에서 자동 정지
x64dbg: DllMain 주소에 직접 브레이크포인트(F2) 설정 후 fdwReason(두 번째 인자) 값 확인
```

## 출력 해석
- `fdwReason == 1`(`DLL_PROCESS_ATTACH`) — DLL이 막 로드됨. `lpvReserved`가 `NULL`이 아니면 정적 로드(암시적 링크), `NULL`이면 `LoadLibrary`를 통한 동적 로드
- `fdwReason == 0`(`DLL_PROCESS_DETACH`) — DLL이 언로드되는 중. `lpvReserved`가 `NULL`이 아니면 프로세스 종료로 인한 언로드(정리 코드를 건너뛰어도 되는 경우가 많음), `NULL`이면 `FreeLibrary` 호출로 인한 명시적 언로드
- `WinMain`/`wWinMain`의 반환값(정수)은 프로세스 종료 코드로 이어지는 경우가 많다(`ExitProcess`에 전달)
- `DllMain`의 반환값이 `FALSE`이면(주로 `DLL_PROCESS_ATTACH` 시점) 로더가 로드 자체를 실패로 처리하고, 이 DLL을 사용하려던 프로세스/`LoadLibrary` 호출이 실패로 이어진다

## 흔한 실수
- IDA가 자동으로 잡아준 진입점이 `main`/`WinMain`이 아니라고 해서 "파일이 손상됐다"고 오해하는 것 — CRT 시작 함수가 정상이다.
- `WinMain`과 `wWinMain`을 완전히 다른 기능으로 착각하는 것 — 문자열 인코딩 차이일 뿐, 나머지 인자와 호출 관례는 동일하다.
- `DllMain`의 `fdwReason` 값 네 가지를 헷갈려서, 스레드가 생길 때마다 `DLL_PROCESS_ATTACH` 로직이 다시 실행된다고 착각하는 것 — 프로세스 최초 로드 시 딱 한 번만 `DLL_PROCESS_ATTACH`가 온다.
- `DllMain` 안에서 `LoadLibrary`나 스레드 대기를 발견했는데도 이것이 데드락을 유발할 수 있다는 위험성을 인식하지 못하고 그냥 "초기화 코드"로만 넘어가는 것.
- `hPrevInstance` 인자를 실제로 의미 있는 값으로 취급해서 분석 시간을 낭비하는 것 — 항상 `NULL`이다.

## 막혔을 때 다음 체크
- 진입점과 CRT 시작 함수 전반이 헷갈리면 → [REV-0121 Entry Point와 WinMain 찾기](./rev-0121-entry-point-winmain.md)
- DLL 분석을 어디서부터 시작할지 감이 안 잡히면 → [REV-0135 DLL 문제 분석 시작하기](./rev-0135-dll-analysis-start.md)
- Subsystem과 진입점 함수 종류의 관계가 궁금하면 → [REV-0564 콘솔 프로그램과 GUI 프로그램 서브시스템 차이](./rev-0564-subsystem-console-gui.md)
- TLS 콜백처럼 `WinMain`보다도 더 먼저 실행되는 코드가 궁금하면 → [REV-0133 TLS Callback과 main 이전 코드](./rev-0133-tls-callback.md)

## 미니 예제
`payload.dll`을 IDA로 열어 진입점을 확인했다고 하자.

```asm
; 진입점 (DllMain)
BOOL WINAPI DllEntryPoint(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved)
{
  if (fdwReason == 1)   // DLL_PROCESS_ATTACH
  {
    sub_10004000();     // 실제 초기화 함수 호출
  }
  return TRUE;
}
```

```text
1) fdwReason 분기에서 값 1(DLL_PROCESS_ATTACH)일 때만 sub_10004000을 호출하는 것을 확인.
2) sub_10004000 내부를 보니 CreateThread로 새 스레드를 만들고
   WaitForSingleObject로 그 스레드가 끝나길 기다리는 코드가 있음.
3) 이것이 로더 락 데드락을 유발할 수 있는 전형적인 안티패턴임을 인지.
   → 실제로 이 DLL을 LoadLibrary로 로드하는 프로세스가
      간헐적으로 멈추는 증상이 있다면, 바로 이 지점이 원인일 가능성이 높다.
4) x64dbg로 DllMain 진입 시 fdwReason 값을 직접 확인해
   DLL_PROCESS_ATTACH(1) 타이밍에 정확히 이 로직이 실행되는지 검증.
```

## 관련 글
- REV-0121 — Entry Point와 WinMain 찾기
- REV-0135 — DLL 문제 분석 시작하기
- REV-0564 — 콘솔 프로그램과 GUI 프로그램 서브시스템 차이
- REV-0133 — TLS Callback과 main 이전 코드

## 출처/검증
- `WinMain`/`wWinMain`/`DllMain` 함수 시그니처와 `mainCRTStartup` 계열 CRT 시작 함수: Microsoft Learn "WinMain entry point" / "DllMain entry point" 공식 문서 기준 (2026-09-08 검증).
- `fdwReason`(`DLL_PROCESS_ATTACH` 등) 값과 각 호출 시점, `lpvReserved`의 정적/동적 로드 구분 의미: Microsoft Learn "DllMain entry point" 공식 문서 기준.
- 로더 락(Loader Lock)과 `DllMain` 안에서 피해야 할 동작(LoadLibrary, 스레드 동기화 대기 등): Microsoft Learn "Dynamic-Link Library Best Practices" 공식 문서 기준.
