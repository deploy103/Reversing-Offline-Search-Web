---
id: REV-0587
title: "Ordinal 번호로 Import가 표시되어 함수명을 모를 때"
slug: "rev-0587-ordinal-import-unknown"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg, "PE-bear"]
keywords: ["import by ordinal", "IMAGE_ORDINAL_FLAG32", "IMAGE_ORDINAL_FLAG64", "AddressOfNameOrdinals", "dumpbin /exports", "hint/name table"]
aliases: ["import이 숫자로만 보임", "ordinal 123 함수명 찾기", "IDA에서 함수 이름 대신 숫자만 뜸"]
symptom_keywords: ["Import 목록에 함수명 대신 Ordinal#123 형태로만 보인다", "IDA에서 sub_ 이름 대신 숫자만 임포트된다", "PE-bear에서 import name이 비어있고 ordinal 값만 있다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Import Table에 함수 이름 대신 `Ordinal#123` 같은 숫자만 보이는 것은 그 DLL이 해당 함수를 **이름이 아니라 순번(ordinal)으로만 익스포트**했기 때문이며, 함수명을 알아내려면 그 DLL 자체를 `dumpbin /exports`나 x64dbg의 Symbols 탭으로 열어 같은 ordinal 번호에 매핑된 이름을 대조해야 한다.

## 언제 검색해야 하나
- IDA의 Imports 창이나 PE-bear의 Import Directory 탭에서 함수 이름 칸이 비어 있고 `Ordinal: 123` 같은 숫자만 보일 때
- x64dbg의 Symbols 탭에서 특정 임포트가 이름 없이 번호로만 표시될 때
- VB6, Delphi로 만들어진 오래된 바이너리나 특정 서드파티 DLL을 분석하다가 함수 이름이 하나도 안 보여서 무슨 API인지 감을 못 잡을 때

## 핵심 개념
PE Import Table(REV-0119)의 각 항목은 Import Address Table(IAT)/Import Lookup Table(ILT)의 `IMAGE_THUNK_DATA` 값으로 표현된다. 이 32/64비트 값의 **최상위 비트**가 켜져 있으면(`IMAGE_ORDINAL_FLAG32 = 0x80000000`, `IMAGE_ORDINAL_FLAG64 = 0x8000000000000000`), 나머지 하위 비트는 문자열 이름을 가리키는 포인터가 아니라 **그 DLL 안에서의 익스포트 순번(ordinal)** 그 자체다. 즉 이름 문자열(Hint/Name Table)을 전혀 거치지 않고 곧바로 번호로 함수를 지정하는 임포트 방식이다.

익스포트하는 쪽(DLL) 입장에서 보면, `IMAGE_EXPORT_DIRECTORY`는 `AddressOfFunctions`(함수 주소 배열), `AddressOfNames`(이름 문자열 배열), `AddressOfNameOrdinals`(이름-순번 매핑 배열) 세 개를 갖는다. 만약 어떤 함수가 **이름 없이 순번으로만** 익스포트되도록 `.def` 파일에 `NONAME` 속성을 주고 빌드했다면, 그 함수는 `AddressOfFunctions` 배열에는 존재하지만 `AddressOfNames`/`AddressOfNameOrdinals`에는 대응 항목이 없다. 이런 DLL을 임포트하는 쪽에서는 이름으로 찾을 방법이 아예 없으므로 반드시 ordinal로 임포트해야 하고, 그 결과가 지금 보고 있는 "이름 없는 임포트"다.

이 방식은 링크 시점 오버헤드를 줄이려는 오래된 관행(초기 Winsock의 `ws2_32.dll` 일부 함수, VB6 런타임, 일부 Delphi 패키지)이나, 리버스 엔지니어링을 어렵게 하려는 의도적 난독화 목적 둘 다로 쓰인다. 어느 쪽이든 정적 분석 도구는 이름을 알 방법이 없으므로 사람이 직접 대상 DLL의 익스포트 테이블을 확인해서 매핑해줘야 한다.

## 화면/코드에서 보이는 징후
- IDA Imports 창에서 `Ordinal` 칸에는 숫자가 있는데 `Name` 칸이 비어 있거나 `Ordinal123` 형태의 자동 생성 이름만 붙어 있음
- PE-bear의 Import Directory에서 특정 항목만 `Name RVA`가 0이고 `Ordinal` 값만 유효함
- x64dbg에서 해당 API를 호출하는 CALL 명령의 대상이 `<모듈명>.Ordinal#123` 같은 표기로 나타남

## 가장 먼저 할 것
어느 DLL의 몇 번 ordinal인지부터 정확히 적어둔다(예: `ws2_32.dll`의 ordinal `115`). 그다음 그 DLL 파일 자체를 구해서 익스포트 테이블을 열어야 하므로, 대상 DLL이 시스템 표준 DLL이면 같은 버전의 System32 파일을, 서드파티 DLL이면 배포 파일에 포함된 원본을 확보한다.

## 단계별 절차
**1) dumpbin으로 대상 DLL의 익스포트 테이블 덤프**
- Visual Studio의 "Developer Command Prompt"를 연다(오프라인 환경이면 Visual Studio 설치 시 포함된 `dumpbin.exe`를 미리 확보해둔다).
- `dumpbin /exports 대상.dll` 실행. 출력은 `ordinal hint RVA name` 네 컬럼으로 정렬되어 나온다.
- 찾고 있는 ordinal 번호와 같은 행의 `name` 컬럼을 읽으면 함수 이름을 알 수 있다.

**2) PE-bear로 같은 정보 확인(GUI 방식)**
- 대상 DLL을 PE-bear로 열고 `Export Directory` 탭으로 이동한다.
- 목록을 Ordinal 기준으로 정렬하거나 검색해서 원하는 번호를 찾는다. `NONAME`으로 익스포트된 함수는 여기서도 이름 칸이 비어 있을 수 있는데, 이 경우 이름 자체가 바이너리에 없는 것이므로 온라인 문서(예: Winsock 함수 문서, 해당 라이브러리의 공개 헤더/`.def` 파일)에서 "이 DLL의 ordinal N이 어떤 함수인지" 알려주는 참고 자료를 찾아야 한다.

**3) x64dbg에서 직접 확인(동적 분석 중이라면)**
- x64dbg의 `Symbols` 탭(하단 탭)에서 대상 모듈을 선택하면 그 모듈이 익스포트하는 심볼 목록이 `Ordinal` 열과 함께 뜬다.
- 여기서 원하는 ordinal 번호를 찾아 대조하거나, 아예 그 주소로 이동해 실제 코드를 보고 함수 시그니처를 추측할 수도 있다(REV-0138 참고).

**4) IDA에 이름 수동으로 붙이기**
- ordinal에 대응하는 실제 함수명을 알아냈다면, IDA의 Imports 창에서 해당 항목을 우클릭 → `Rename`(단축키 `N`)으로 실제 이름을 붙여준다. 이후 그 함수를 호출하는 모든 지점에 자동으로 이름이 반영된다.

## 명령어/단축키
```text
dumpbin /exports 대상.dll        # ordinal, hint, RVA, name 표로 출력
x64dbg: 하단 Symbols 탭에서 모듈 선택 후 Ordinal 열 확인
IDA: Imports 창에서 항목 우클릭 → Rename(N)
```

## 출력 해석
- `dumpbin /exports` 출력에서 `hint` 컬럼이 비어 있거나 `name` 컬럼이 없는 행은 `NONAME`으로 익스포트된, 이름 자체가 바이너리에 없는 함수다. 이런 경우 문서나 헤더 파일 등 외부 자료가 없으면 함수 이름을 알아낼 방법이 없고, 실제 동작(인자 개수, 호출하는 다른 API 등)을 분석해서 기능을 추측하는 수밖에 없다.
- 같은 ordinal이라도 DLL 버전이 다르면 다른 함수를 가리킬 수 있으므로, 반드시 대상 프로그램이 실제로 로드하는 것과 **같은 버전**의 DLL에서 익스포트 테이블을 확인해야 한다.

## 흔한 실수
- 다른 버전의 시스템에서 뽑은 DLL로 ordinal을 대조하는 것. Windows 버전이나 DLL 버전이 다르면 같은 ordinal 번호가 다른 함수를 가리킬 수 있어 완전히 엉뚱한 이름을 붙이게 된다.
- ordinal만 보고 "함수명을 지운 난독화"라고 단정하는 것. 실제로는 원래부터 이름으로 익스포트되지 않는 정상적인 DLL(예: 일부 레거시 런타임)일 수 있다.
- `AddressOfNameOrdinals` 배열과 `AddressOfFunctions` 배열의 인덱스 관계를 헷갈려서 수동으로 파싱할 때 엉뚱한 주소를 함수 주소로 착각하는 것. 가능하면 직접 파싱하지 말고 `dumpbin`/PE-bear 같은 검증된 도구의 출력을 신뢰한다.

## 막혔을 때 다음 체크
- ordinal로 찾은 함수가 무슨 일을 하는지 이름만으로 감이 안 잡히면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.
- 애초에 이 DLL 자체가 로드되지 않는 문제라면 → REV-0586(Missing DLL)을 먼저 해결한다.
- Import Table 구조 자체가 헷갈리면 → REV-0119(Import Table에서 중요한 API 찾기)를 다시 읽는다.

## 미니 예제
`dumpbin /exports ws2_32.dll`을 실행했더니 다음과 같은 줄이 나왔다고 하자.

```text
    ordinal hint RVA      name
        115    5 00006A10 WSAStartup
        116    6 00006B30 WSACleanup
        151   70 00007A00 accept
```

만약 IDA Imports 창에서 `ws2_32.dll`의 `Ordinal 115`로만 표시된 임포트가 있었다면, 위 표를 통해 이것이 `WSAStartup`이라는 것을 바로 알 수 있다. 이제 IDA에서 그 임포트 항목을 우클릭 → Rename으로 `WSAStartup`이라고 이름을 붙이면, 이 함수를 호출하는 모든 CALL 지점에 자동으로 `call ds:WSAStartup` 같은 읽기 쉬운 이름이 반영된다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0586 — DLL이 로드되지 않아 실행이 안 될 때(Missing DLL)
- REV-0120 — Export Table과 DLL 함수

## 출처/검증
- Import by ordinal의 비트 구조(`IMAGE_ORDINAL_FLAG32`/`64`)와 Export Directory의 `AddressOfFunctions`/`AddressOfNames`/`AddressOfNameOrdinals` 관계는 Microsoft PE/COFF 형식 공식 문서 기준.
- `dumpbin /exports` 사용법은 Microsoft Learn Visual Studio 도구 문서 기준.
- x64dbg Symbols 탭의 Ordinal 표시 동작은 실제 도구 사용 관찰 기준이며 버전에 따라 UI 배치가 다를 수 있다(2026-09-08 기준 서술).
