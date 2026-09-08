---
id: REV-0519
title: "WinAPI 핸들 함수 사전: CloseHandle DuplicateHandle GetLastError"
slug: "rev-0519-closehandle-duplicatehandle-getlasterror"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CloseHandle", "DuplicateHandle", "GetLastError", "핸들", "커널 객체", "핸들 누수"]
aliases: ["핸들 정리 함수", "에러 코드 확인 함수", "핸들 복제"]
symptom_keywords: ["CloseHandle을 왜 호출하는지 모르겠다", "GetLastError 값을 어디서 확인하는지 모르겠다", "DuplicateHandle이 뭔지 모르겠다", "핸들이 뭔지 모르겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CloseHandle`은 파일/뮤텍스/이벤트/프로세스/스레드 등 모든 종류의 커널 객체 핸들을 정리하는 공용 함수이고, `DuplicateHandle`은 한 프로세스의 핸들을 다른 프로세스에서도 쓸 수 있게 복제하는 함수이며, `GetLastError`는 직전에 실패한 Win32 API 호출의 원인을 나타내는 에러 코드를 반환하므로, 이 세 함수는 거의 모든 WinAPI 호출 뒤에 따라붙는 "뒷정리/에러 확인" 3종 세트로 이해하면 된다.

## 언제 검색해야 하나
- `CreateFile`, `CreateMutex`, `OpenProcess` 등으로 얻은 핸들이 언제 닫히는지(또는 안 닫히는지) 추적할 때
- API 호출 실패 원인을 알아내기 위해 `GetLastError` 반환값의 의미를 찾아야 할 때
- `DuplicateHandle`이 등장해서 왜 다른 프로세스에 핸들을 넘기는지 분석해야 할 때(프로세스 인젝션, IPC 등)
- 핸들 누수(leak)로 인한 이상 동작을 진단할 때

## 핵심 개념
```c
BOOL CloseHandle(HANDLE hObject);
// hObject: 닫을 커널 객체 핸들(파일, 뮤텍스, 이벤트, 프로세스, 스레드, 레지스트리 키 등 공통)

BOOL DuplicateHandle(
    HANDLE hSourceProcessHandle, // 1. 원본 핸들이 속한 프로세스 핸들
    HANDLE hSourceHandle,        // 2. 복제할 원본 핸들
    HANDLE hTargetProcessHandle, // 3. 복제본을 받을 대상 프로세스 핸들
    LPHANDLE lpTargetHandle,     // 4. 새 핸들이 저장될 주소
    DWORD dwDesiredAccess,       // 5. 새 핸들의 접근 권한
    BOOL bInheritHandle,         // 6. 자식 프로세스 상속 여부
    DWORD dwOptions              // 7. DUPLICATE_SAME_ACCESS, DUPLICATE_CLOSE_SOURCE 등
);

DWORD GetLastError(void); // 인자 없음, 스레드별 마지막 에러 코드 반환
```

`CloseHandle`은 파일, 뮤텍스, 이벤트, 프로세스, 스레드, 스레드풀, 맵핑된 파일 등 커널이 관리하는 거의 모든 객체 핸들에 공통으로 쓰인다(단, 레지스트리 키는 `RegCloseKey`처럼 전용 함수를 쓴다는 예외가 있다). `DuplicateHandle`은 핸들 값 자체가 프로세스마다 독립적인 테이블을 가리키기 때문에, 한 프로세스의 핸들 숫자를 그대로 다른 프로세스에 넘겨줘 봤자 의미가 없다는 문제를 해결한다 — 프로세스 인젝션이나 디버거 구현, IPC에서 자주 쓰인다.

`GetLastError`는 스레드마다 독립적인 값을 가지며, 성공한 API 호출이라도 반드시 이전 값을 덮어쓰는 것은 아니므로(문서에 "이 함수는 성공 시 GetLastError를 설정하지 않는다"고 명시된 API도 있음) 반드시 "실패를 나타내는 반환값(NULL, FALSE, INVALID_HANDLE_VALUE 등)을 먼저 확인한 직후"에 호출해야 의미가 있다. 자주 보는 코드 값은 `2`(`ERROR_FILE_NOT_FOUND`), `5`(`ERROR_ACCESS_DENIED`), `87`(`ERROR_INVALID_PARAMETER`), `183`(`ERROR_ALREADY_EXISTS`) 등이다.

## 화면/코드에서 보이는 징후
- `CreateFileW`/`CreateMutexW`/`OpenProcess` 등의 반환 핸들을 지역 변수에 저장한 뒤, 함수 끝부분(또는 에러 처리 분기)에서 `CloseHandle(hFile)`이 호출되는 패턴
- API 호출 직후 `call GetLastError`가 바로 이어지고, 반환값(`EAX`)을 특정 상수와 비교하는 코드
- `OpenProcess`로 얻은 핸들이 `DuplicateHandle`을 거쳐 다른 핸들 변수에 저장되는 패턴(원격 프로세스 조작/인젝션 코드에서 흔함)

## 가장 먼저 할 것
1. 분석 중인 함수에서 획득한 핸들이 모든 리턴 경로(성공/실패/예외)에서 `CloseHandle`로 닫히는지 확인한다.
2. API 실패 시 곧바로 `GetLastError`를 호출하는지, 그 값이 어떤 상수와 비교되는지 확인한다.
3. `DuplicateHandle`이 보이면 `hSourceProcessHandle`과 `hTargetProcessHandle`이 같은 프로세스(현재 프로세스, `GetCurrentProcess()` 반환값인 `-1`/`0xFFFFFFFFFFFFFFFF`인 pseudo-handle)인지 아니면 서로 다른 프로세스인지부터 구분한다.

## 단계별 절차
**1) 정적 분석(IDA)**
- 핸들을 반환하는 함수(`CreateFileW` 등) 호출 지점부터 시작해 해당 지역 변수가 쓰이는 모든 위치를 `X`로 추적한다.
- 함수의 모든 리턴 경로에서 `CloseHandle` 호출 여부를 확인해 누락된 경로(핸들 누수)가 있는지 점검한다.

**2) 동적 분석(x64dbg)**
- `bp GetLastError`로 브레이크포인트를 걸어두면, 프로그램이 API 실패를 자체적으로 확인하는 모든 지점에서 멈출 수 있다.
- 멈춘 시점에서 스택의 리턴 주소(x64는 `[RSP]`)를 확인해 `GetLastError`를 호출한 함수가 어디인지 역추적한다. 리턴 직후(F8) `EAX`가 반환된 에러 코드다.
- `bp DuplicateHandle` 후 `RCX`(hSourceProcessHandle), `RDX`(hSourceHandle), `R8`(hTargetProcessHandle)을 확인해 어느 프로세스 간 핸들 이동인지 파악한다.

## 명령어/단축키
- x64dbg: `bp CloseHandle`, `bp DuplicateHandle`, `bp GetLastError`
- x64dbg: 브레이크포인트에서 F8(스텝오버)로 반환값(`EAX`) 확인
- IDA: `X`(교차 참조), `F5`(디컴파일)

## 출력 해석
- `CloseHandle` 반환값이 `FALSE`(0)이면 이미 닫혔거나 잘못된 핸들을 닫으려 한 것 — `GetLastError()`가 `ERROR_INVALID_HANDLE`(6)을 반환한다.
- `DuplicateHandle` 반환값이 `FALSE`이면 복제 실패이며, 성공 시 `lpTargetHandle`이 가리키는 주소에 새 핸들 값이 채워진다.
- `GetLastError` 값을 사람이 읽을 수 있는 메시지로 보려면 x64dbg의 "Error codes" 창(또는 `err` 로그 플러그인)이나 IDA의 상수 라이브러리(WinAPI 상수 자동 주석)를 활용한다.

## 흔한 실수
- `CloseHandle`을 호출한 뒤에도 그 핸들 값을 계속 사용하는 것(use-after-close 버그) — 이후 같은 값이 다른 객체에 재할당되면 엉뚱한 객체를 조작하게 된다.
- `GetLastError`를 성공한 호출 뒤에 호출해서 이전 실패의 낡은 에러 코드를 마치 방금 실패의 원인인 것처럼 착각하는 것.
- `DuplicateHandle`의 `hSourceProcessHandle`이 항상 현재 프로세스라고 가정하는 것 — 실제로는 `OpenProcess`로 얻은 다른 프로세스 핸들일 수 있으며, 이 경우가 바로 프로세스 인젝션/디버깅 도구의 핵심 패턴이다.
- `CloseHandle`을 파일이나 뮤텍스가 아니라 레지스트리 키 핸들에 잘못 사용하는 것(레지스트리는 `RegCloseKey` 전용).

## 막혔을 때 다음 체크
- 애초에 어떤 핸들이 만들어졌는지(뮤텍스/이벤트)가 궁금하면 → REV-0518(CreateMutex CreateEvent)을 본다.
- 핸들이 모듈(DLL) 핸들이라면 → REV-0520(LoadLibraryEx FreeLibrary GetModuleHandle)을 본다.
- 파일 핸들의 생성/사용 흐름이 궁금하면 → REV-0139(CreateFile ReadFile WriteFile 입력 데이터 추적)을 본다.

## 미니 예제
x64dbg에서 `bp GetLastError`를 걸고 실행하니 다음 상황에서 멈췄다.

```text
[RSP]     = 0x00000000004013A2   (리턴 주소, 호출한 함수 위치)
```

리턴 주소 부근을 IDA에서 확인해보니 직전에 `CreateFileW` 호출과 `cmp eax, -1`(INVALID_HANDLE_VALUE 비교) 코드가 있었다. `GetLastError` 리턴 후 `EAX = 2`(`ERROR_FILE_NOT_FOUND`)라면, 이 프로그램이 열려던 파일이 디스크에 존재하지 않아 실패했다는 뜻이다.

Windows 핸들 값 자체는 실제 메모리 주소가 아니라 프로세스별 핸들 테이블의 인덱스에 가까운 불투명한(opaque) 값이며, 보통 4의 배수로 증가한다. 이 성질 때문에 핸들 숫자만 보고 "핸들 몇 개가 열려 있는가"를 대략 짐작할 수는 있지만, 정확한 열린 핸들 목록을 보려면 Process Explorer(Sysinternals) 같은 별도 도구로 실제 프로세스의 핸들 테이블을 조회해야 한다. 리버싱 중 특정 함수가 반복 호출되는데 그때마다 `CloseHandle`이 누락되어 있다면, 장시간 실행 시 핸들 테이블이 고갈되어 이후 API 호출이 실패하는 간접적인 버그로 이어질 수 있다는 점도 함께 기억해두면 좋다.

## 관련 글
- REV-0518 — WinAPI 동기화 함수 사전: CreateMutex CreateEvent
- REV-0520 — WinAPI 모듈 함수 사전: LoadLibraryEx FreeLibrary GetModuleHandle
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적

## 출처/검증
- `CloseHandle`/`DuplicateHandle`/`GetLastError`의 함수 시그니처와 동작, 대표 에러 코드(2, 5, 6, 87, 183)는 Microsoft Win32 API(핸들/에러 처리) 공식 문서 기준이다.
- 위 미니 예제의 주소와 값은 설명을 위해 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
