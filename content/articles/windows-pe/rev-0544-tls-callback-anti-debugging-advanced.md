---
id: REV-0544
title: "TLS 콜백을 이용한 안티디버깅 심화"
slug: "rev-0544-tls-callback-anti-debugging-advanced"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["TLS Callback", "IMAGE_TLS_DIRECTORY", "AddressOfCallBacks", "DLL_PROCESS_ATTACH", "OEP 이전 실행", "TLS 안티디버깅"]
aliases: ["TLS 콜백 안티디버깅", "OEP 우회 안티디버깅", "TLS 디렉토리 안티디버깅", "엔트리포인트 이전 코드 실행", "TLS 콜백 트릭"]
symptom_keywords: ["IDA 엔트리포인트에 브레이크포인트를 걸었는데 그 전에 이미 뭔가 실행된 것 같다", "TlsCallback_0 같은 함수가 있다", "IMAGE_TLS_DIRECTORY가 PE 헤더에 있다", "x64dbg 시스템 브레이크포인트에서 멈췄는데 이상한 값이 이미 계산되어 있다", "엔트리포인트에서 디버거로 열면 프로그램이 이미 종료된 것처럼 보인다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
TLS(Thread Local Storage) 콜백은 프로그램의 진짜 시작 지점(Entry Point, OEP)보다도 먼저 로더에 의해 자동으로 실행되는 코드이기 때문에, 많은 리버서/디버거가 기본적으로 EP에 브레이크포인트를 거는 습관을 역이용해 TLS 콜백 안에 안티디버깅 검사나 핵심 로직을 심어두면 "디버거를 EP까지만 따라간 사람"은 그 이전에 이미 실행된 검사를 놓치게 된다 — REV-0133의 TLS Callback 기본 개념을 실제 안티디버깅 공격 표면으로 확장한 것이 이 문서다.

## 언제 검색해야 하나
- REV-0133으로 TLS 콜백이 `main`보다 먼저 실행된다는 것은 알고 있는데, "이게 왜 안티디버깅에 유리한지" 구체적으로 알고 싶을 때
- IDA에서 Entry Point를 찾아 브레이크포인트를 걸고 실행했는데, 이미 전역 변수 값이 계산되어 있거나 프로그램이 예상과 다르게 종료된 것을 발견했을 때
- PE 헤더의 `IMAGE_DATA_DIRECTORY[IMAGE_DIRECTORY_ENTRY_TLS]`가 0이 아닌 값을 가리키고 있는데, 이 안에 어떤 코드가 들어있는지 궁금할 때
- x64dbg의 `Options → Preferences → Events`에 있는 `TLS Callbacks` 체크박스가 왜 있는지 궁금할 때

## 핵심 개념

### TLS 콜백이 언제, 왜 먼저 실행되는가
Windows 로더는 PE의 `IMAGE_TLS_DIRECTORY` 구조체(REV-0133에서 기본 구조를 다룸)에 있는 `AddressOfCallBacks` 배열을 순회하며, 각 콜백 함수를 **프로세스의 Entry Point가 호출되기 전에**, 그리고 새 스레드가 생성될 때마다(`DLL_THREAD_ATTACH`) 자동으로 호출한다. 원래 이 메커니즘은 스레드별 전역 변수를 스레드가 시작될 때마다 초기화하기 위한 것이지만, EXE의 경우에도 프로세스 시작 시 `DLL_PROCESS_ATTACH` 이유로 최소 한 번은 반드시 호출된다는 점이 안티디버깅에 악용된다.

```c
VOID NTAPI TlsCallback(PVOID DllHandle, DWORD Reason, PVOID Reserved) {
    if (Reason == DLL_PROCESS_ATTACH) {
        if (IsDebuggerPresent()) {
            ExitProcess(1);
        }
    }
}
```

### 왜 "EP에 브레이크포인트"만으로는 못 막나
분석자가 흔히 하는 습관은 IDA/x64dbg에서 프로그램을 열고 곧바로 Entry Point(OEP)에 브레이크포인트를 건 뒤 실행하는 것이다. 하지만 TLS 콜백은 로더에 의해 **EP보다 먼저** 호출되므로, 이 시점에는 아직 디버거가 "EP 브레이크포인트"에 도달하지 못한 채 TLS 콜백 코드가 이미 다 실행되어 버린 뒤다. 그 안에 안티디버깅 검사나 핵심 복호화 로직이 있다면, 분석자는 그 결과만 보게 되고 실제 검사/복호화 과정 자체는 놓치게 된다.

### x64dbg/IDA의 대응 옵션
이 문제 때문에 x64dbg는 `Options → Preferences → Events` 탭에 `System Breakpoint`, `TLS Callbacks`, `Entry Breakpoint` 등의 체크박스를 제공한다. `TLS Callbacks`를 켜두면 x64dbg는 각 TLS 콜백 함수의 시작 지점에서 자동으로 실행을 멈춰주므로, 분석자가 EP보다 먼저 실행되는 이 코드를 놓치지 않고 확인할 수 있다. 기본 설정에서 이 옵션이 꺼져 있거나 분석자가 존재를 모르면, TLS 콜백 기반 검사는 매우 효과적인 함정이 된다.

### TLS 콜백은 몇 개까지 있을 수 있나
`AddressOfCallBacks`가 가리키는 배열은 함수 포인터들의 나열이고 `NULL`로 끝난다. 즉 콜백은 0개, 1개, 또는 여러 개가 연속으로 존재할 수 있으며, IDA는 이를 자동으로 인식해 `TlsCallback_0`, `TlsCallback_1`처럼 이름을 붙여준다(정확한 개수는 컴파일러/링커가 몇 개를 만들었는지에 달려 있다). 컴파일러가 기본적으로 넣는 것 외에 개발자가 `#pragma comment(linker, "/INCLUDE:_tls_used")`와 커스텀 섹션(`.CRT$XLx`)을 이용해 추가 콜백을 직접 등록할 수도 있다.

### 복호화/자기 변조와의 결합
TLS 콜백은 안티디버깅뿐 아니라, EP에 도달하기 전에 `.text` 섹션을 복호화하거나 재배치하는 언패킹 방지용 트릭에도 자주 쓰인다. 이 경우 EP에서 정적으로 보이는 코드는 아직 복호화되지 않은 쓰레기 바이트일 수 있고, TLS 콜백이 실행된 이후에야 실제 코드가 메모리에 올라온다는 점도 함께 기억해야 한다.

## 화면/코드에서 보이는 징후
- IDA의 Imports/Exports 근처 또는 함수 목록에 `TlsCallback_0`(자동 명명) 함수가 있음.
- PE 헤더의 Optional Header Data Directory 중 `TLS Table`(REV-0524 참고) 엔트리가 0이 아닌 RVA/크기를 가짐.
- x64dbg 시스템 브레이크포인트(모듈 로드 완료 시점)에서 멈췄을 때 이미 특정 전역 변수 값이 초기화되어 있거나, `IsDebuggerPresent` 등이 이미 호출된 흔적(스택/레지스터 상태)이 보임.

## 가장 먼저 할 것
IDA에서 `Ctrl+E`(Entry points 목록)를 열어 TLS 콜백 함수가 별도로 나열되는지 먼저 확인한다. PE-bear나 DIE로 열었을 때 TLS Directory가 존재하는지부터 확인하는 것도 빠른 방법이다.

## 단계별 절차
**1) TLS Directory 존재 확인**

PE-bear(REV-0125)에서 Optional Header의 Data Directories 중 TLS Table을 확인하거나, IDA의 `Ctrl+E`(엔트리 포인트 목록)에서 TLS 콜백이 별도 항목으로 나열되는지 본다.

**2) x64dbg에서 TLS 콜백 이벤트 활성화**

`Options → Preferences → Events` 탭에서 `TLS Callbacks` 체크박스를 켠다. 이렇게 하면 프로그램 실행 시 로더가 TLS 콜백을 호출하는 시점에 x64dbg가 자동으로 멈춘다.

**3) TLS 콜백 함수 분석**

멈춘 지점에서 코드를 스텝 실행하며 이 콜백이 무엇을 하는지 확인한다. 안티디버깅 검사(`IsDebuggerPresent` 등)인지, 복호화 루틴인지 구분한다.

**4) IDA에서도 함께 정적 분석**

TLS 콜백 함수 시작 주소를 IDA에서 열어(`G`로 주소 이동), 함수 시그니처가 `void NTAPI TlsCallback(PVOID DllHandle, DWORD Reason, PVOID Reserved)` 형태와 일치하는지 확인하고 함수 이름을 명확하게 리네임해둔다.

**5) 우회 방법 이해**

가장 실전적인 방법은 x64dbg의 TLS Callbacks 이벤트를 항상 켜두고 분석을 시작하는 습관을 들이는 것이다. 검사 로직 자체를 무력화하려면 콜백 안의 감지 분기를 패치하거나, 콜백 함수 시작에서 곧바로 `ret`으로 빠지도록 패치해 콜백 자체를 무력화하는 방법도 있다(단, 그 안에 필수적인 초기화 로직이 있다면 프로그램이 깨질 수 있으니 주의).

## 명령어/단축키
- x64dbg: `Options → Preferences → Events → TLS Callbacks` 체크
- IDA: `Ctrl+E`(Entry points 목록에서 TLS 콜백 확인)
- PE-bear: Optional Header → Data Directories → TLS Table 확인

## 출력 해석
- x64dbg가 TLS 콜백에서 멈췄다는 것은 아직 EP(OEP)에도 도달하지 않은 매우 이른 시점이라는 뜻이다. 이 시점의 레지스터/메모리 상태는 프로그램이 "본격적으로 시작하기 전"의 상태이므로, `main`에서 보던 것과는 다른 문맥(예: 아직 CRT 초기화도 안 됐을 수 있음)임을 감안해서 해석해야 한다.
- 콜백의 세 번째 인자(`Reason`)가 `DLL_PROCESS_ATTACH`(값 1)인지 `DLL_THREAD_ATTACH`(값 2)인지에 따라 이 호출이 "프로세스 최초 시작"인지 "새 스레드 생성"인지 구분된다.

## 흔한 실수
- EP에만 브레이크포인트를 걸고 "이 프로그램의 시작점을 다 봤다"고 안심하는 것 — TLS 콜백이 있다면 이미 그 전에 코드가 실행됐을 수 있다.
- x64dbg의 `TLS Callbacks` 이벤트 옵션을 모르고, 매번 수동으로 TLS Directory를 찾아 주소를 계산해 브레이크포인트를 거는 비효율적인 방식만 시도하는 것.
- TLS 콜백이 여러 개일 수 있다는 것을 모르고 첫 번째 콜백만 확인하고 넘어가는 것.
- 콜백 함수 시그니처의 세 번째 인자(`Reason`)를 무시해서, `DLL_THREAD_ATTACH`로 반복 호출되는 코드와 `DLL_PROCESS_ATTACH`로 한 번만 실행되는 코드를 구분하지 못하는 것.

## 막혔을 때 다음 체크
- TLS 콜백의 기본 구조와 `IMAGE_TLS_DIRECTORY` 필드가 궁금하다면 → REV-0133 TLS Callback과 main 이전 코드
- 이 콜백 안에서 `IsDebuggerPresent`를 쓰는 패턴이 궁금하다면 → REV-0130 IsDebuggerPresent 안티디버깅 식별
- PE Optional Header의 Data Directory 전체 목록이 궁금하다면 → REV-0524 — PE Optional Header 필드 전체 사전
- 여러 안티디버깅 기법을 한눈에 정리한 표가 필요하다면 → REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 미니 예제
```c
#include <windows.h>

#pragma comment(linker, "/INCLUDE:_tls_used")
#pragma data_seg(".CRT$XLB")
PIMAGE_TLS_CALLBACK p_tls_callback = TlsCallback;
#pragma data_seg()

VOID NTAPI TlsCallback(PVOID h, DWORD reason, PVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        if (IsDebuggerPresent()) {
            ExitProcess(1); // main에 도달하기도 전에 종료됨
        }
    }
}

int main(void) {
    printf("Enter flag: ");
    return 0;
}
```
IDA에서 `main`에만 브레이크포인트를 걸고 실행하면 `TlsCallback`이 이미 실행되어 디버거 감지 시 프로세스가 종료된 뒤이므로 `main`에 도달조차 하지 못한다 — x64dbg의 `TLS Callbacks` 이벤트를 켜야만 이 함수 안에서 멈춰 실제 동작을 관찰할 수 있다.

## 관련 글
- REV-0133 — TLS Callback과 main 이전 코드
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0524 — PE Optional Header 필드 전체 사전
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 출처/검증
- `IMAGE_TLS_DIRECTORY` 구조체와 `AddressOfCallBacks` 필드, TLS 콜백이 로더에 의해 Entry Point 이전에 호출된다는 사실은 Microsoft PE/COFF 공식 스펙(`SRC-MS-PE-FORMAT`) 기준.
- x64dbg의 `Options → Preferences → Events` 탭에 `TLS Callbacks` 항목이 존재하고 이를 통해 TLS 콜백 시점에 자동으로 멈출 수 있다는 것은 x64dbg 공식 문서 및 UI 구성에 기반한 서술이다(2026-09-08 확인, 버전에 따라 메뉴 명칭이 다를 수 있음).
- TLS 콜백을 이용한 안티디버깅/안티언패킹 활용 패턴은 다수의 공개 리버싱 레퍼런스(Unprotect Project, CTF 라이트업)에서 공통적으로 설명되는 기법이다.
