---
id: REV-0579
title: "Windows 클립보드를 이용한 데이터 전달 패턴 분석"
slug: "rev-0579-clipboard-data-transfer-pattern"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["OpenClipboard", "SetClipboardData", "GetClipboardData", "GlobalAlloc", "CF_UNICODETEXT", "클립보드 하이재킹"]
aliases: ["클립보드 API 분석", "클립보드 데이터 가로채기", "클립보드 하이재킹 패턴"]
symptom_keywords: ["OpenClipboard가 임포트에 있다", "SetClipboardData 호출을 찾았다", "클립보드로 데이터가 나가는 것 같다", "클립보드 주소가 바뀌는 악성코드"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows 클립보드는 `OpenClipboard`/`GetClipboardData`/`SetClipboardData`/`CloseClipboard` 네 함수와 `GlobalAlloc`/`GlobalLock`으로 관리되는 공유 메모리 핸들을 통해 동작하며, 이 흐름을 알면 크랙미가 클립보드로 플래그를 빼돌리는 패턴이나 악성코드가 암호화폐 주소를 바꿔치기하는 클립보드 하이재킹(clipboard hijacking) 패턴을 모두 같은 방식으로 추적할 수 있다.

## 언제 검색해야 하나
- IDA Imports 탭에 `OpenClipboard`, `SetClipboardData`, `GetClipboardData`, `EmptyClipboard` 중 하나라도 보일 때
- 프로그램 실행 후 클립보드 내용이 의도치 않게 바뀌어 있을 때(예: 복사한 비트코인 주소가 다른 주소로 바뀜)
- CTF 문제에서 "클립보드를 확인하라"는 힌트가 있거나, 화면에는 안 보이는데 `Ctrl+V`로 붙여넣으면 플래그가 나오는 유형일 때
- `AddClipboardFormatListener`나 `WM_CLIPBOARDUPDATE` 메시지를 처리하는 코드가 보여서 클립보드 변화를 실시간 감시하는 프로그램인지 확인해야 할 때

## 핵심 개념
클립보드는 시스템 전역 자원이므로, 접근하려면 반드시 "열고(Open) → 조작 → 닫기(Close)" 순서를 지켜야 하며, 데이터는 프로세스 힙이 아니라 `GlobalAlloc`으로 할당한 이동 가능(moveable) 핸들 형태로 주고받는다.

```c
BOOL OpenClipboard(HWND hWndNewOwner);       // 클립보드 사용 시작(소유권 획득), hWndNewOwner는 NULL 가능
BOOL EmptyClipboard(void);                   // 기존 클립보드 내용을 비우고 소유권을 현재 프로세스로 설정
HANDLE SetClipboardData(UINT uFormat, HANDLE hMem); // 지정 형식으로 데이터 등록(성공 시 시스템이 hMem 소유권을 가져감)
HANDLE GetClipboardData(UINT uFormat);       // 지정 형식의 데이터 핸들을 가져옴(읽기 전용으로 취급해야 함)
BOOL CloseClipboard(void);                   // 클립보드 사용 종료
```

주요 형식(`uFormat`) 상수: `CF_TEXT`(1, ANSI 텍스트), `CF_UNICODETEXT`(13, UTF-16 텍스트), `CF_BITMAP`(2), `CF_HDROP`(15, 파일 드래그앤드롭 목록).

클립보드는 하나의 데이터를 여러 형식으로 동시에 등록할 수 있다는 점도 중요하다. 예를 들어 워드프로세서에서 텍스트를 복사하면 `CF_TEXT`, `CF_UNICODETEXT`, 서식 정보를 담은 커스텀 형식(예: `RegisterClipboardFormatW`로 등록한 `"Rich Text Format"`)이 동시에 클립보드에 올라간다. 리버싱 관점에서는 `GetClipboardData`를 호출할 때 어떤 형식을 요청하는지가 "이 프로그램이 클립보드에서 어떤 종류의 데이터를 기대하는가"를 알려주는 단서가 된다 — 예를 들어 `CF_HDROP`을 요청한다면 사용자가 파일 탐색기에서 파일을 복사한 뒤 붙여넣기하는 시나리오(파일 경로 목록 전달)를 염두에 둔 코드라는 뜻이다.

**쓰기(클립보드에 데이터 넣기) 흐름**
1. `OpenClipboard(NULL)` → `EmptyClipboard()`
2. `GlobalAlloc(GMEM_MOVEABLE, size)`로 이동 가능한 메모리 핸들을 할당
3. `GlobalLock(hMem)`으로 실제 포인터를 얻어 데이터를 복사(`memcpy`/`wcscpy`)
4. `GlobalUnlock(hMem)`으로 잠금 해제
5. `SetClipboardData(CF_UNICODETEXT, hMem)` 호출 — **성공하면 시스템이 이 핸들의 소유권을 가져가므로, 이후 `GlobalFree`를 호출하면 안 된다**
6. `CloseClipboard()`

**읽기(클립보드에서 데이터 가져오기) 흐름**
1. `OpenClipboard(NULL)`
2. `GetClipboardData(CF_UNICODETEXT)`로 핸들을 얻음
3. `GlobalLock(hData)`로 실제 포인터를 얻어 내용을 읽음(복사해서 쓰는 것이 안전, 원본을 直接 수정하면 안 됨)
4. `GlobalUnlock(hData)`
5. `CloseClipboard()`

## 화면/코드에서 보이는 징후
- `OpenClipboard` → `EmptyClipboard` → `GlobalAlloc(0x0002 /* GMEM_MOVEABLE */, size)` → `GlobalLock` → 메모리 복사 루틴 → `GlobalUnlock` → `SetClipboardData` → `CloseClipboard` 순서로 이어지는 연속 호출
- 반대로 `OpenClipboard` → `GetClipboardData(13 /* CF_UNICODETEXT */)` → `GlobalLock` → 문자열 비교/치환 루틴 → `GlobalUnlock` → `CloseClipboard` 흐름
- 클립보드 하이재킹형 악성코드는 `GetClipboardData`로 읽은 문자열을 정규식과 유사한 패턴 매칭(예: `1`이나 `3`, `bc1`로 시작하는 비트코인 주소, `0x`로 시작하는 이더리움 주소 형태)으로 검사한 뒤, 일치하면 공격자의 주소 문자열로 다시 `SetClipboardData`를 호출해 바꿔치기함
- `AddClipboardFormatListener(hWnd)` 등록 후 윈도우 프로시저에서 `WM_CLIPBOARDUPDATE` 메시지를 처리하는 코드가 있다면, 클립보드가 바뀔 때마다 자동으로 반응하는 상시 감시형 구조

## 가장 먼저 할 것
`SetClipboardData`와 `GetClipboardData` 중 어느 것이(혹은 둘 다) 임포트에 있는지 먼저 구분한다. `SetClipboardData`만 있으면 "클립보드로 데이터를 내보내는" 유형(플래그를 클립보드에 심어두는 크랙미 등)이고, `GetClipboardData`가 있으면 "클립보드 내용을 읽어서 검사/변조하는" 유형(하이재킹, 또는 사용자가 복사-붙여넣기한 값을 검증에 쓰는 크랙미)이다.

## 단계별 절차
**1) 정적 분석(IDA)**
- Imports에서 `SetClipboardData`/`GetClipboardData`를 찾아 `X`로 호출부를 확인한다.
- `SetClipboardData`라면 그 직전의 `GlobalLock` 반환값(버퍼 포인터)에 어떤 데이터가 복사되는지, 즉 그 데이터의 출처(상수 문자열, 복호화 결과 등)를 추적한다.
- `GetClipboardData`라면 그 이후 `GlobalLock` 결과가 어떤 비교/치환 로직에 쓰이는지 추적한다.

**2) 동적 분석(x64dbg)**
- `bp SetClipboardData`로 브레이크포인트를 걸고 실행한다. 걸리면 x64 기준 `RDX`(2번째 인자, `hMem`)를 확인하고, 이 값으로 `GlobalLock`을 호출한 결과 포인터를 별도로 추적하거나, `SetClipboardData` 호출 직전에 있었을 `GlobalLock` 반환값(보통 `RAX`가 이전에 저장된 지역 변수)을 역추적해 실제 데이터 내용을 덤프에서 확인한다.
- `bp GetClipboardData`로도 동일하게 접근할 수 있으며, 함수가 리턴한 직후(`RAX`) 값을 다시 `GlobalLock`에 넘기는 지점까지 따라가면 실제 문자열을 볼 수 있다.
- 클립보드 자체 내용을 빠르게 확인하려면 디버거를 쓰지 않고 그냥 메모장을 열어 `Ctrl+V`로 붙여넣어 보는 것도 유효한 1차 확인 방법이다.

## 명령어/단축키
- x64dbg: `bp SetClipboardData`, `bp GetClipboardData`, `bp GlobalLock`, 인자/반환값 우클릭 → "Follow in Dump"
- IDA: `X`(교차 참조), `F5`(디컴파일)
- 수동 확인: 클립보드 뷰어 대용으로 메모장에 `Ctrl+V`

## 출력 해석
- `OpenClipboard`가 0(실패)을 반환하면 다른 프로세스가 이미 클립보드를 열고 있는 상태이며, 이 경우 재시도 로직이 있는지 확인한다.
- `SetClipboardData`가 성공(0이 아닌 핸들 반환)하면 시스템이 데이터 소유권을 가져간 것이므로, 이후 코드에서 원본 `hMem`을 다시 `GlobalLock`하거나 `GlobalFree`하면 안 된다(잘못된 코드이거나 버그).
- `GetClipboardData`가 NULL을 반환하면 요청한 형식(`uFormat`)의 데이터가 클립보드에 없다는 뜻이다 — 예를 들어 이미지만 복사되어 있는데 `CF_UNICODETEXT`를 요청하면 NULL이 반환된다.

## 흔한 실수
- `GlobalLock`으로 얻은 포인터를 `GlobalUnlock` 없이 계속 들고 있다가 `CloseClipboard`를 호출해서 이후 접근 시 오류가 나는 코드를 분석 관점에서 "버그"로만 보고 넘어가는 것 — 실제로는 의도적인 지연 접근(다른 스레드에서 나중에 읽음)일 수도 있으므로 전체 흐름을 봐야 한다.
- `SetClipboardData` 성공 후 `GlobalFree(hMem)`을 호출하는 코드를 발견했을 때 "정상"이라고 넘기는 것 — 이는 공식 문서상 금지된 패턴(이중 해제 위험)이므로, 실제로는 별도의 새 버퍼를 free하는 것이거나 프로그램 자체의 버그일 수 있어 변수를 재확인해야 한다.
- `CF_TEXT`(ANSI)와 `CF_UNICODETEXT`(UTF-16)를 혼동해서 덤프를 1바이트 단위로 읽어버리는 것.
- 클립보드 감시형 악성코드를 분석할 때 `SetClipboardData` 호출 한 번만 보고 끝내는 것 — 실제로는 `WM_CLIPBOARDUPDATE`에 반응해 반복적으로 감시/치환하는 루프 구조이므로 메시지 루프 전체를 봐야 완전한 그림이 나온다.

클립보드는 시스템 전역 자원이라는 특성 때문에, 동시에 여러 프로세스가 접근을 시도하면 경합(race)이 생길 수 있다는 점도 분석 시 염두에 둬야 한다. `OpenClipboard`가 실패하는 경우(다른 프로세스가 이미 열어둔 상태)를 대비해 실전 코드는 대개 짧은 재시도 루프(`Sleep`을 섞어 몇 차례 재시도)를 두는데, 이 재시도 루프 자체가 디버거로 한 줄씩 밟을 때는 타이밍이 달라져서 계속 실패하는 것처럼 보일 수 있다. 이런 경우 브레이크포인트 없이 통째로 실행(`F9`)한 뒤 결과만 확인하는 방식이 더 안정적이다.

## 막혔을 때 다음 체크
- 클립보드가 아니라 명명된 파이프로 데이터를 주고받는 것 같다면 → REV-0580(명명된 파이프를 이용한 IPC 분석 기초) 참고
- 클립보드에 담기는 데이터가 파일에서 온 것이라면 → REV-0139(CreateFile ReadFile WriteFile 입력 데이터 추적) 참고
- 리소스 섹션에 숨겨진 데이터가 클립보드로 옮겨지는 구조라면 → REV-0141(Resource Section과 숨겨진 데이터 확인) 참고

## 미니 예제
x64dbg에서 `bp SetClipboardData` 후 실행했더니 다음과 같이 멈췄다고 하자.

```text
RCX = 0x0000000D              (uFormat = CF_UNICODETEXT = 13)
RDX = 0x0000000000450000      (hMem, GlobalAlloc이 반환한 핸들)
```

`RDX` 값을 그대로 덤프 창에 이동(Follow in Dump)해서 보면 `GlobalLock`을 거치지 않은 핸들 자체 값이 보일 수도 있으므로, 실제 데이터를 보려면 이 값이 `GlobalLock`에 인자로 들어간 지점을 콜스택(`Alt+K`)에서 역추적해 `GlobalLock`의 반환값(실제 포인터)을 확인해야 한다. 그 포인터를 Follow in Dump하면 다음과 같은 UTF-16 문자열이 보인다.

```text
00450000  43 00 54 00 46 00 7B 00  63 00 6C 00 69 00 70 00   C.T.F.{.c.l.i.p.
00450010  62 00 30 00 61 00 72 00  64 00 7D 00 00 00 00 00   b.0.a.r.d.}.....
```

`CTF{clipb0ard}`가 클립보드에 심어지는 순간을 그대로 가로챈 것이다.

## 관련 글
- REV-0580 — 명명된 파이프(Named Pipe)를 이용한 IPC 분석 기초
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 출처/검증
- `OpenClipboard`/`EmptyClipboard`/`SetClipboardData`/`GetClipboardData`/`CloseClipboard`와 `GlobalAlloc`/`GlobalLock`/`GlobalUnlock`의 함수 시그니처, 소유권 이전 규칙(`SetClipboardData` 성공 후 `GlobalFree` 금지)은 Microsoft Win32 API 공식 문서(Clipboard, Global Memory) 기준이다.
- 클립보드 하이재킹(암호화폐 주소 치환) 패턴은 다수의 공개된 악성코드 분석 리포트에서 공통적으로 보고되는 일반적 기법 설명이다.
- 위 미니 예제의 메모리 값과 플래그 문자열은 설명을 위해 구성한 예시다(2026-09-08 기준 서술).
