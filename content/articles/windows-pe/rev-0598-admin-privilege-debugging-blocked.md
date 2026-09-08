---
id: REV-0598
title: "관리자 권한이 없어서 디버깅이 막힐 때"
slug: "rev-0598-admin-privilege-debugging-blocked"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords:
  - SeDebugPrivilege
  - OpenProcess ERROR_ACCESS_DENIED
  - 관리자 권한 디버깅
  - x64dbg 관리자 권한 실행
  - Protected Process Light
aliases:
  - Cannot open process error code 5
  - x64dbg attach 실패 권한
  - 디버거 attach 안됨
  - 관리자 권한으로 실행 필요
symptom_keywords:
  - Cannot open process error code 5
  - attach 목록에 프로세스가 안 보임
  - access denied 디버거
  - x64dbg 관리자 권한 요청
  - OpenProcess 실패
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x64dbg나 IDA의 디버거 모듈이 대상 프로세스를 열지 못하고 "Cannot open process, error code 5"(`ERROR_ACCESS_DENIED`)를 내거나 attach 목록에 프로세스 자체가 안 보인다면, 대부분 디버거를 관리자 권한으로 실행하지 않아서 생기는 문제이므로 디버거 실행 파일을 우클릭 → "관리자 권한으로 실행"으로 다시 열면 해결된다.

## 언제 검색해야 하나
- x64dbg로 실행 중인 프로세스에 attach를 시도했는데 "Cannot open process, error code 5" 또는 유사한 접근 거부 메시지가 뜰 때
- Attach 대화상자의 프로세스 목록에 분명히 실행 중인 대상이 표시되지 않을 때
- IDA의 "Attach to process" 메뉴에서 대상이 회색으로 비활성화되어 선택할 수 없을 때
- 관리자 권한으로 실행했는데도 여전히 특정 프로세스(SYSTEM 권한 서비스 등)에는 붙을 수 없을 때

## 가장 먼저 할 것
디버거 실행 파일(`x64dbg.exe`/`x32dbg.exe`/`ida64.exe`)을 우클릭해서 "관리자 권한으로 실행"을 선택해 다시 켠다. 이미 관리자 권한으로 켰다고 착각하고 있는 경우가 많으므로, 창 제목 표시줄이나 작업 관리자의 "관리자" 컬럼으로 실제로 권한이 상승되었는지 다시 확인한다.

## 핵심 개념
Windows에서 한 프로세스가 다른 프로세스를 디버깅(메모리 읽기/쓰기, 스레드 컨텍스트 조작, 브레이크포인트 설정)하려면 `OpenProcess` API로 대상 프로세스 핸들을 충분한 접근 권한(`PROCESS_ALL_ACCESS` 등)으로 얻어야 한다. 이 요청이 거부되면 `GetLastError()`가 `5`(`ERROR_ACCESS_DENIED`)를 반환한다.

이 접근 권한 검사를 통과하려면 디버거 프로세스의 토큰에 `SeDebugPrivilege`("프로그램 디버그" 권한)가 활성화되어 있어야 한다. 기본적으로 로컬 관리자(Administrators) 그룹 구성원은 이 권한을 가질 자격이 있지만, Windows의 UAC(사용자 계정 컨트롤) 구조상 "관리자 권한이 있는 계정으로 로그인했다"는 것과 "지금 실행 중인 이 프로세스가 실제로 상승된 권한 토큰을 갖고 있다"는 것은 별개다. 프로그램을 그냥 더블클릭해서 실행하면 기본적으로 표준 사용자 권한 토큰으로 시작되며, 이 상태에서는 `SeDebugPrivilege`가 잠재적으로 부여 가능하더라도 실제로 활성화되어 있지 않다.

x64dbg 같은 디버거는 시작 시 자기 프로세스 토큰에서 `SeDebugPrivilege`를 켜는 코드(`AdjustTokenPrivileges`)를 실행하는데, 애초에 관리자 권한으로 상승되지 않은 프로세스는 이 권한을 가지고 있지 않으므로 이 시도 자체가 실패한다. 결과적으로 디버거는 "권한이 없어서 이 프로세스를 열 수 없다"는 오류를 낸다.

또한 일부 프로세스는 관리자 권한만으로도 디버깅이 불가능하다. Windows의 PPL(Protected Process Light) 메커니즘이 적용된 프로세스(일부 안티치트, DRM, 시스템 핵심 프로세스)는 커널 드라이버 수준의 서명된 컴포넌트 없이는 일반 디버거로 attach할 수 없다. 이런 경우는 권한 문제가 아니라 설계상의 보호이므로 별도의 우회 기법이 필요하며 이 글의 범위를 벗어난다.

## 화면/코드에서 보이는 징후
- x64dbg 상태 표시줄이나 로그 창에 `Cannot open process, error code 5.` 라는 문구가 그대로 출력된다.
- IDA에서 "Could not attach to the process to debug" 계열 메시지가 뜬다.
- Attach 대화상자에 프로세스 자체가 목록에서 아예 빠져 있다(일부 도구는 열 수 없는 프로세스를 목록에서 숨긴다).
- 디버거 실행 아이콘에 방패 아이콘이 없거나, 작업 관리자 "세부 정보" 탭의 "권한 수준" 컬럼이 "표준"으로 표시된다.

## 단계별 절차
1. 디버거를 완전히 종료한다.
2. 디버거 실행 파일을 우클릭 → "관리자 권한으로 실행"을 선택한다. UAC 프롬프트가 뜨면 "예"를 눌러 승인한다.
3. 매번 이 과정을 반복하기 귀찮다면, 실행 파일 속성 → 호환성 탭 → "관리자 권한으로 이 프로그램 실행"에 체크해 기본값으로 만들어둔다.
4. 다시 attach를 시도한다. 이번에는 프로세스 목록에 대상이 정상적으로 나타나야 한다.
5. 그래도 실패하면 대상이 PPL 보호 프로세스이거나 다른 보안 소프트웨어(REV-0599)가 별도로 차단하고 있는지 확인한다.

## 명령어/단축키
- 우클릭 → "관리자 권한으로 실행" (또는 `Shift`+우클릭이 아니라 일반 우클릭 메뉴에서 선택)
- 작업 관리자에서 "세부 정보" 탭 → 열 추가 → "권한 수준"으로 현재 실행 중인 프로세스의 권한 확인
- PowerShell(관리자)에서 `Start-Process x64dbg.exe -Verb RunAs`로 관리자 권한 실행

## 출력 해석
- `error code 5` = `ERROR_ACCESS_DENIED` — 권한 부족. 관리자 권한 재실행으로 대부분 해결된다.
- 관리자 권한으로도 여전히 안 되고 대상이 서비스/SYSTEM 프로세스라면, `SeDebugPrivilege`는 있어도 대상 프로세스의 보안 설명자(DACL)나 PPL 보호가 별도로 막고 있을 수 있다.
- attach는 됐는데 특정 메모리 영역 읽기/쓰기만 실패한다면 그건 권한 문제가 아니라 페이지 보호 속성(REV-0182 Memory Map 참고) 문제일 가능성이 높다.

## 흔한 실수
- Windows 로그인 계정이 "관리자 계정"이라는 이유만으로 지금 켜진 디버거 프로세스도 자동으로 관리자 권한일 거라고 착각하는 것 — UAC 때문에 명시적으로 상승시키지 않으면 표준 권한으로 실행된다.
- 관리자 권한으로 이미 켜져 있는 다른 프로그램(예: 탐색기)에서 디버거를 실행하면 상속될 거라 기대하는 것 — 실제로는 각 실행마다 별도로 상승해야 한다.
- 대상 프로세스도 관리자 권한(또는 SYSTEM)으로 실행 중인데 디버거는 표준 권한으로 켜서 "낮은 권한 프로세스가 높은 권한 프로세스를 열 수 없다"는 기본 규칙에 걸리는 것.
- PPL 보호 프로세스를 관리자 권한만으로 뚫으려고 계속 시도하며 시간을 낭비하는 것 — 이 경우 일반적인 방법으로는 애초에 불가능하다.

## 막혔을 때 다음 체크
- 관리자 권한으로 실행했는데도 디버거 자체가 실행되지 않거나 사라진다면 → REV-0599(방화벽/백신이 분석 도구를 차단할 때)를 확인한다.
- attach는 성공했는데 곧바로 대상 프로세스가 종료된다면 → 권한 문제가 아니라 안티 디버깅 가능성이 높다. 패킹 카테고리의 안티디버깅 체크리스트를 참고한다.
- 대상이 여러 자식 프로세스를 만드는 구조라 어느 프로세스에 붙어야 할지 모르겠다면 → REV-0603을 확인한다.

## 미니 예제
표준 사용자 권한으로 실행한 `x64dbg.exe`에서 `target.exe` 프로세스에 attach를 시도했더니 로그 창에 다음이 출력되었다.

```text
Cannot open process, error code 5.
```

`x64dbg.exe`를 우클릭 → "관리자 권한으로 실행"으로 다시 켜고 동일한 attach를 시도하자, 이번에는 오류 없이 프로세스가 정상적으로 목록에 나타났고 attach도 성공했다.

## 관련 글
- REV-0599 — 방화벽/백신이 분석 도구를 차단할 때
- REV-0603 — 프로세스가 여러 개 자식 프로세스를 만들어 분석이 꼬일 때
- REV-0182 — x64dbg Memory Map과 Module View

## 출처/검증
- `OpenProcess` 실패 시 `GetLastError()` 값 `5`(`ERROR_ACCESS_DENIED`)의 의미와 `SeDebugPrivilege`의 역할은 Microsoft Win32 API 공식 문서 기준이다.
- 디버거가 관리자 권한으로 실행되어야 `SeDebugPrivilege`를 활성화할 수 있다는 동작은 x64dbg 공식 문서 및 일반적인 Windows 디버깅 관행 기준이다.
- Protected Process Light(PPL)로 보호된 프로세스는 일반 디버거로 attach할 수 없다는 점은 Microsoft의 프로세스 보호 수준 문서 기준이다.
- 2026-09-08 기준 서술.
