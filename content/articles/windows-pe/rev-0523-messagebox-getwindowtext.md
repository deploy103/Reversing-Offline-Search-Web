---
id: REV-0523
title: "WinAPI 클립보드/UI 함수 사전: MessageBox GetWindowText"
slug: "rev-0523-messagebox-getwindowtext"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["MessageBoxW", "GetWindowTextW", "SetWindowTextW", "GetDlgItemText", "UI 텍스트 추출"]
aliases: ["메시지박스 함수", "윈도우 텍스트 얻기", "다이얼로그 입력값 읽기"]
symptom_keywords: ["MessageBox 인자를 모르겠다", "GetWindowText가 뭔지 모르겠다", "입력창 텍스트를 어디서 읽는지 모르겠다", "정답/오답 메시지가 어디서 뜨는지 찾고 싶다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`MessageBoxW`는 화면에 안내창(정답/오답, 경고, 에러 메시지)을 띄우는 함수이고 `GetWindowTextW`(및 다이얼로그 컨트롤 전용 `GetDlgItemTextW`)는 에디트 박스 같은 컨트롤에 사용자가 입력한 텍스트를 코드로 가져오는 함수로, GUI 기반 crackme에서는 이 두 함수의 호출 지점을 찾는 것만으로도 "입력을 어디서 읽고 결과를 어디서 알리는지"가 거의 바로 드러난다.

## 언제 검색해야 하나
- GUI crackme에서 사용자가 입력한 값(에디트 박스 텍스트)을 코드 흐름 어디서 읽어들이는지 찾아야 할 때
- "정답입니다"/"틀렸습니다" 같은 메시지 문자열이 코드의 어느 분기에서 나오는지 찾아 그 분기 조건(비교 로직)을 역추적해야 할 때
- 임포트 목록에서 `MessageBoxW`, `GetWindowTextW`, `GetDlgItemTextW`, `SetWindowTextW`를 발견했을 때
- 콘솔이 아니라 다이얼로그 기반(리소스에 `DIALOGEX` 정의)으로 만들어진 프로그램을 분석할 때

## 핵심 개념
```c
int MessageBoxW(
    HWND    hWnd,      // 1. 부모 윈도우 핸들(NULL이면 소유 윈도우 없음)
    LPCWSTR lpText,    // 2. 메시지 본문 텍스트
    LPCWSTR lpCaption, // 3. 제목 표시줄 텍스트
    UINT    uType      // 4. MB_OK, MB_ICONERROR 등 버튼/아이콘 조합
);

int GetWindowTextW(
    HWND    hWnd,      // 1. 텍스트를 읽을 대상 윈도우(컨트롤)의 핸들
    LPWSTR  lpString,  // 2. 텍스트가 채워질 버퍼
    int     nMaxCount  // 3. 버퍼 크기(문자 수)
);

UINT GetDlgItemTextW(
    HWND    hDlg,      // 1. 다이얼로그 윈도우 핸들
    int     nIDDlgItem,// 2. 컨트롤 ID(리소스에서 정의된 정수)
    LPWSTR  lpString,  // 3. 텍스트가 채워질 버퍼
    int     cchMax     // 4. 버퍼 크기(문자 수)
);
```

`MessageBoxW`의 두 번째 인자(`lpText`)가 실제 화면에 뜨는 본문 메시지이므로, "정답입니다", "Wrong password", "Access denied" 같은 문자열을 문자열 검색으로 먼저 찾고 그 문자열의 교차 참조(`X`)를 타고 올라가면 바로 검증 로직의 호출부에 도달한다 — GUI crackme 분석에서 가장 빠른 진입점이다.

`GetWindowTextW`는 임의의 윈도우/컨트롤 핸들에서 텍스트를 읽으며, 에디트 박스의 핸들은 보통 `GetDlgItem(hDlg, nIDDlgItem)`으로 먼저 얻은 뒤 `GetWindowTextW`에 넘긴다. `GetDlgItemTextW`는 이 두 단계(`GetDlgItem` + `GetWindowTextW`)를 한 번에 처리하는 축약형이며, 다이얼로그 기반 프로그램(리소스에서 컨트롤 ID로 정의된 UI)에서 더 흔히 쓰인다. 반대 방향으로 텍스트를 설정하는 함수는 `SetWindowTextW`/`SetDlgItemTextW`다.

버튼 클릭 이벤트는 대개 `WM_COMMAND` 메시지를 처리하는 `DialogProc`/`WndProc` 콜백 함수 안에서 컨트롤 ID(`LOWORD(wParam)`)로 분기하며, "확인" 버튼 클릭 시 이 분기 안에서 `GetWindowTextW`(또는 `GetDlgItemTextW`)로 입력값을 읽고 검증한 뒤 `MessageBoxW`로 결과를 알리는 흐름이 정형적이다.

## 화면/코드에서 보이는 징후
- 문자열 검색(`Alt+T` in IDA)에서 `"Correct"`, `"정답"`, `"Wrong"`, `"틀렸습니다"` 같은 문자열을 발견 → 교차 참조(`X`)하면 `MessageBoxW` 호출 지점으로 바로 연결
- `WM_COMMAND`(0x111) 처리 분기 안에서 `GetDlgItemTextW` 또는 `GetWindowTextW` 호출 뒤 곧바로 비교/해시 함수(`strcmp`, `CryptHashData` 등)로 이어지는 코드
- 버튼 ID 상수(예: `IDOK`=1, 또는 리소스 정의 `IDC_EDIT1` 등)가 `GetDlgItemTextW`의 두 번째 인자로 들어가는 패턴

## 가장 먼저 할 것
1. IDA 문자열 창(`Shift+F12`)에서 "정답"/"Correct"/"Wrong"/"Fail" 등 결과 메시지로 보이는 문자열을 먼저 찾는다.
2. 그 문자열의 교차 참조를 따라가 `MessageBoxW` 호출 지점, 그리고 그 지점을 감싼 조건 분기(`if`)를 찾는다.
3. 그 조건 분기 바로 위에서 사용된 비교 대상 변수가 어디서 왔는지(`GetWindowTextW`/`GetDlgItemTextW` 호출까지) 거슬러 올라간다.

## 단계별 절차
**1) 정적 분석(IDA)**
- 문자열 창에서 결과 메시지 문자열을 찾아 `X`로 참조 위치를 확인한다.
- 그 위치를 포함한 함수를 `F5`로 디컴파일해서 입력 → 검증 → 결과 출력까지 전체 흐름을 한 번에 파악한다.

**2) 동적 분석(x64dbg)**
- `bp GetWindowTextW`(또는 `bp GetDlgItemTextW`)로 브레이크포인트를 걸고, "확인" 버튼을 눌러본다.
- 브레이크포인트가 걸리면 x64 기준 두 번째(또는 세 번째) 인자(버퍼 주소)를 Follow in Dump, UTF-16으로 확인해 실제 입력한 텍스트가 맞게 읽히는지 확인한다.
- 이어서 `bp MessageBoxW`도 걸어두면, 검증 로직을 다 통과한 뒤 어떤 문자열이 두 번째 인자로 들어가는지 보고 성공/실패 분기가 어디였는지 역산할 수 있다.

## 명령어/단축키
- x64dbg: `bp GetWindowTextW`, `bp GetDlgItemTextW`, `bp MessageBoxW`
- IDA: `Shift+F12`(문자열 목록), `X`(교차 참조), `F5`(디컴파일)

## 출력 해석
- `GetWindowTextW`/`GetDlgItemTextW`의 반환값은 실제로 복사된 문자 수(NUL 제외)다. `0`이면 컨트롤에 텍스트가 없거나 실패한 것.
- `MessageBoxW`의 반환값은 사용자가 누른 버튼(예: `IDOK`=1, `IDCANCEL`=2)이며, 이후 코드가 이 값을 보고 추가 분기를 할 수도 있다(드문 경우).
- `uType`(네 번째 인자)의 아이콘 플래그(`MB_ICONERROR`=0x10, `MB_ICONINFORMATION`=0x40 등)로 이 메시지가 성공 알림인지 에러 알림인지 코드만 보고도 짐작할 수 있다.

## 흔한 실수
- 문자열 창에서 원하는 메시지를 찾았는데 참조가 여러 곳(성공/실패 각각 다른 문자열)이라는 것을 놓치고 한 곳만 보고 결론 내리는 것.
- `GetWindowTextW`가 항상 에디트 박스에서만 쓰인다고 생각하는 것 — 버튼, 스태틱 텍스트 등 모든 윈도우/컨트롤에서 텍스트를 읽을 수 있다.
- 콘솔 기반 crackme(`scanf` 사용)와 GUI 기반 crackme(`GetWindowTextW` 사용)를 혼동해서 엉뚱한 함수를 브레이크포인트로 거는 것.
- `MessageBoxW`의 `lpText`가 리터럴이 아니라 `sprintf`/`wsprintf`로 동적으로 조합된 경우, 조합되기 전 원본 포맷 문자열만 보고 실제 출력 내용을 오판하는 것.

## 막혔을 때 다음 체크
- 읽어들인 입력값이 해시로 검증된다면 → REV-0522(CryptAcquireContext CryptHashData)를 본다.
- 입력값이 CRT 문자열 함수로 비교/가공된다면 → REV-0515(strcpy_s sprintf_s)나 REV-0516(wcscpy wcscat 계열)을 본다.
- 애초에 GUI 창의 구조(다이얼로그 리소스, 컨트롤 ID)를 더 알아야 한다면 → REV-0141(Resource Section과 숨겨진 데이터 확인)을 함께 본다.

## 미니 예제
x64dbg에서 `bp GetDlgItemTextW` 후 "확인" 버튼을 누르니 다음처럼 멈췄다.

```text
RCX = 0x00000000000A044C   (hDlg)
RDX = 0x00000000000003E9   (nIDDlgItem = 1001, 에디트 박스 ID)
R8  = 0x000000000021FB40   (버퍼)
R9  = 0x0000000000000040   (cchMax = 64)
```

함수 리턴 후(F8) `R8`이 가리키던 버퍼(`0x21FB40`)를 Follow in Dump, UTF-16으로 보면 방금 입력창에 타이핑한 `L"test1234"`가 그대로 보인다. 이후 코드를 따라가면 이 값이 곧바로 `CryptCreateHash`/`CryptHashData`로 넘어가 SHA1 해시를 계산하고, 그 결과를 하드코딩된 값과 비교한 뒤 `MessageBoxW(hDlg, L"틀렸습니다", L"결과", MB_ICONERROR)`가 호출되는 흐름을 확인할 수 있다.

## 관련 글
- REV-0522 — WinAPI 암호 관련 함수 사전: CryptAcquireContext CryptHashData
- REV-0515 — Windows CRT 문자열 함수 사전: strcpy_s sprintf_s
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 출처/검증
- `MessageBoxW`/`GetWindowTextW`/`GetDlgItemTextW`의 함수 시그니처, 반환값, `uType` 아이콘 플래그는 Microsoft Win32 API(사용자 인터페이스, 윈도우 및 메시지) 공식 문서 기준이다.
- `WM_COMMAND` 메시지와 다이얼로그 프로시저의 일반적인 처리 방식은 Microsoft Win32 윈도우 메시지 공식 문서 기준이다.
- 위 미니 예제의 주소와 값은 설명을 위해 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
