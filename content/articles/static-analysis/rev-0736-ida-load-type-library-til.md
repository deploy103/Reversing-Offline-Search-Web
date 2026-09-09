---
id: REV-0736
title: "IDA 타입 라이브러리(til) 로드해서 시그니처 인식률 높이기"
slug: "rev-0736-ida-load-type-library-til"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["til 파일", "Type Libraries", "Shift+F11", "Load type library", "IDA 타입 라이브러리", "til 로드", "함수 원형 자동 인식"]
aliases: ["til 파일이란", "IDA 타입 라이브러리 로드", "Load type library 사용법", "til과 Local Types 차이"]
symptom_keywords: ["윈도우 API 함수 인자가 자꾸 int로만 보임", "표준 라이브러리 함수 원형이 자동으로 안 붙음", "til이 뭔지 모르겠음", "MFC나 SDK 타입이 인식이 안 됨"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`.til`(Type Information Library) 파일은 특정 SDK/런타임(Windows API, MSVC CRT, MFC 등)의 함수 원형과 구조체 타입을 미리 정리해 둔 IDA 전용 타입 데이터베이스이며, **Type Libraries** 서브뷰(`Shift+F11`)에서 알맞은 til을 추가로 로드해두면 알려진 함수의 인자 타입/구조체가 자동으로 정확하게 인식되어 디컴파일 결과가 훨씬 정확해진다.

## 언제 검색해야 하나
- Windows API 함수를 호출하는데 Pseudocode에서 인자가 전부 `int`나 `unsigned int`로만 보여서, 실제로 어떤 타입(핸들, 구조체 포인터, 플래그)인지 알아보기 어려울 때
- 특정 SDK(MFC, 특정 게임 엔진 SDK, 특정 임베디드 플랫폼 SDK)를 쓰는 바이너리인데 그 SDK의 구조체가 하나도 인식되지 않을 때
- REV-0731(FLIRT)로 함수 이름은 붙었는데, 그 함수의 인자 타입까지는 여전히 부정확하게 추론되어 있을 때
- 이미 갖고 있는 `.til` 파일(예: 특정 SDK 배포판에 포함된 til)을 IDA에 추가로 적용하고 싶은데 방법을 모를 때

## 핵심 개념

### til과 Local Types의 관계
IDA는 두 가지 타입 정보 저장소를 구분해서 관리한다.

- **Type Libraries(til)**: `View → Open subviews → Type Libraries`(`Shift+F11`)에서 관리하는, 특정 플랫폼/SDK에 대해 미리 만들어진 "타입 사전"이다. 여기에는 아직 현재 분석 중인 데이터베이스(idb)에 실제로 쓰이지 않은 타입도 전부 들어 있을 수 있다.
- **Local Types**: `Shift+F1`(REV-0737에서 자세히 다룸)에서 관리하는, 현재 데이터베이스에 실제로 저장된 타입 목록이다.

til에 있는 타입이 실제로 어떤 함수/변수에 적용되면, 그 순간 해당 타입이 Local Types에도 복사되어 이후에는 til을 다시 로드하지 않아도 데이터베이스 자체에 남는다. 즉 til은 "가져다 쓸 수 있는 재료 창고", Local Types는 "이미 쓰기로 확정한 재료 목록"에 가깝다.

### 왜 til을 추가로 로드해야 하는가
IDA는 바이너리를 열 때 기본적인 til(예: 컴파일러가 감지되면 그에 맞는 표준 라이브러리 til)을 자동으로 적용하는 경우가 많지만, 다음과 같은 상황에서는 자동 적용이 되지 않는다.

- 특정 SDK/미들웨어(MFC, DirectX 구버전, 특정 게임 엔진, 임베디드 벤더 SDK)의 til이 기본 목록에 없을 때
- 여러 버전의 SDK 중 IDA가 자동으로 고른 버전이 실제 빌드 환경과 다를 때
- 분석자가 직접 만든(또는 SDK 배포판에 포함된) `.til` 파일을 IDA가 아직 모를 때

이럴 때는 Type Libraries 창에서 수동으로 til을 추가해야, 그 SDK의 함수를 호출하는 코드에서 인자 타입/구조체가 정확하게 표시된다.

### til 로드 절차
`View → Open subviews → Type Libraries`(`Shift+F11`)를 열면 현재 적용된 til 목록이 보인다. 이 목록 위에서 우클릭 → **Load type library...**(또는 `Ins` 키)를 누르면 IDA가 알고 있는 til 후보 목록(설치 폴더 `til/` 아래 플랫폼별 하위 폴더에 있는 파일들)이 뜬다. 원하는 항목(예: Windows PE라면 `mssdk`, `vc` 계열 등)을 선택해 로드한다. 필요하다면 이 목록에 없는 외부 `.til` 파일 경로를 직접 지정해서 불러올 수도 있다.

### 적용 확인
til을 로드했다고 곧바로 기존에 분석된 함수들의 표시가 전부 바뀌는 것은 아니다. 이미 잘못 추론된 함수 원형이 남아있다면, 그 함수를 다시 분석하거나(`Reanalyze function`) 직접 `Y`(REV-0148)로 원형을 새로 지정해서 til에 있는 타입을 참조하도록 해줘야 실제로 반영된다. 새로 분석되는 함수(아직 방문하지 않은 함수)는 로드된 til을 바로 활용해서 원형을 추론한다.

## 화면/코드에서 보이는 징후
- Windows API 호출 부분에서 `CreateFileA(a1, a2, a3, a4, a5, a6, a7)`처럼 인자 이름이 전부 `a1`, `a2`...로만 보이고 실제 파라미터 이름(`lpFileName`, `dwDesiredAccess` 등)이 안 보인다.
- 구조체 포인터를 넘기는 API인데 그 구조체가 `void *`나 `int`로만 보인다.
- Type Libraries 창을 열어보면 지금 필요한 SDK의 til이 목록에 없다.

## 가장 먼저 할 것
Type Libraries 창(`Shift+F11`)을 열어 현재 어떤 til이 이미 적용되어 있는지 확인한다. 필요한 SDK의 til이 없다면, IDA 설치 폴더의 `til/` 하위에 해당 SDK/플랫폼용 파일이 있는지, 또는 SDK 자체 배포판에 `.til` 파일이 동봉되어 있는지부터 찾는다.

## 단계별 절차
1. `Shift+F11`로 Type Libraries 창을 연다.
2. 우클릭 → **Load type library...**(또는 `Ins`)를 눌러 후보 목록을 연다.
3. 분석 대상과 맞는 플랫폼/SDK의 til을 찾아 선택한다(목록에 없으면 외부 `.til` 파일 경로를 직접 지정).
4. 로드가 끝나면 Output window에 로드된 til 이름과 포함된 타입 개수 관련 로그가 뜨는지 확인한다.
5. API 호출부 함수 위에서 우클릭 → **Reanalyze function**을 실행하거나, `Y`로 함수 원형을 다시 지정해 새로 로드된 til의 타입을 명시적으로 참조시킨다.
6. F5로 Pseudocode를 다시 확인해 인자 이름/타입이 SDK 원형 기준으로 바뀌었는지 확인한다.
7. 여전히 인식이 안 되는 함수가 있다면, 그 SDK의 til 자체가 없거나 버전이 다른 것이므로 REV-0737(Local Types)에서 다루는 C 헤더 파싱으로 직접 원형을 등록하는 방법으로 넘어간다.

## 명령어/단축키
- `Shift+F11`: Type Libraries 서브뷰 열기
- Type Libraries 창에서 `Ins` 또는 우클릭 → **Load type library...**: 새 til 추가
- 함수 위 우클릭 → **Reanalyze function**: 새로 로드된 til 반영을 위한 재분석
- `Y`: 함수 원형을 수동으로 다시 지정(til의 타입 이름을 직접 입력해 참조, REV-0148)

## 출력 해석
- til을 로드하면 Output window에 로드된 라이브러리 이름과 그 안에 포함된 타입/함수 원형 개수 요약이 표시된다. 개수가 0이거나 로드 자체가 실패했다면 파일이 손상되었거나 IDA 버전과 호환되지 않는 til일 수 있다.
- Type Libraries 창의 목록에 이미 같은 이름의 til이 있는데 다시 로드하려 하면 중복 여부를 알려주는 메시지가 뜰 수 있다.
- 함수 원형이 바뀌지 않는다면 til 로드는 성공했지만 아직 그 함수에 적용(재분석 또는 수동 `Y`)이 안 된 것이다.

## 흔한 실수
- til만 로드하고 이미 분석된 함수를 재분석하지 않아 "로드했는데 왜 안 바뀌지"라고 헷갈리는 것.
- 플랫폼이 다른 til(예: 32비트용 til을 64비트 바이너리에)을 로드해서 오히려 잘못된 타입이 적용되는 것.
- til과 Local Types를 같은 것으로 착각해서, til만 로드하면 데이터베이스에 영구히 저장된다고 오해하는 것 — 실제로 타입이 쓰여야 Local Types로 복사되어 남는다.
- 필요한 SDK의 til이 없는데도 비슷한 이름의 다른 til을 억지로 적용해서 오히려 잘못된 함수 원형이 붙는 것.

## 막혔을 때 다음 체크
- til에도 없는 타입을 C 헤더에서 직접 가져오고 싶다면 → REV-0737 IDA Local Types 창 활용하기
- 함수 원형을 세부적으로 수동 편집하고 싶다면 → REV-0738 IDA에서 함수 프로토타입을 수동으로 수정하기
- 함수 이름 자체가 안 붙어 있다면(원형 이전에 식별부터 필요) → REV-0731 IDA FLIRT 시그니처 적용해서 라이브러리 함수 식별하기
- til 관련 요약 참조가 필요하다면 → REV-0723 IDA 타입 라이브러리(til) 빠른 참조

## 미니 예제
Windows PE 바이너리를 분석 중인데 다음처럼 API 인자가 전부 `int`로 나온다고 하자.

```c
int result = sub_401200(hFile, buf, 100, &v1, 0);
```

`Shift+F11`로 Type Libraries 창을 열고 `mssdk` 계열 til을 로드한 뒤, `sub_401200` 위에서 `Y`를 눌러 원형을 `ReadFile`로 직접 지정하거나 우클릭 → Reanalyze function을 실행하면, til에 등록된 `ReadFile`의 실제 원형(`BOOL ReadFile(HANDLE hFile, LPVOID lpBuffer, DWORD nNumberOfBytesToRead, LPDWORD lpNumberOfBytesRead, LPOVERLAPPED lpOverlapped)`)을 기준으로 다음처럼 바뀐다.

```c
BOOL result = ReadFile(hFile, buf, 100, &v1, 0);
```

인자 이름과 타입이 표준 원형과 일치하게 되어, 이 호출이 파일을 읽는 동작이라는 것이 코드만 보고도 바로 파악된다.

## 관련 글
- REV-0737 — IDA Local Types 창 활용하기
- REV-0731 — IDA FLIRT 시그니처 적용해서 라이브러리 함수 식별하기
- REV-0738 — IDA에서 함수 프로토타입을 수동으로 수정하기
- REV-0148 — IDA Y로 타입 지정하기
- REV-0723 — IDA 타입 라이브러리(til) 빠른 참조

## 출처/검증
- Type Libraries 서브뷰(`View → Open subviews → Type Libraries`, 단축키 `Shift+F11`)와 til/Local Types의 관계(til에서 실제 참조된 타입이 idb의 Local Types로 복사되는 동작), `Load type library...`(단축키 `Ins`) 조작: Hex-Rays 공식 문서(Types) 및 공식 블로그(Igor's tip of the week #60: Type libraries) 기준.
- 이 문서는 2026-09-09 기준 공개된 Hex-Rays 공식 문서/블로그 검색 결과를 바탕으로 작성했으며, 실제 til 파일 목록/경로 이름은 설치된 IDA 버전과 함께 제공되는 SDK 구성에 따라 달라질 수 있으므로 실제 환경에서 재확인할 것을 권장한다.
