---
id: REV-0555
title: "Ordinal Import(이름 없는 Import) 분석법"
slug: "rev-0555-ordinal-import"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", "Detect It Easy"]
keywords: ["IMAGE_ORDINAL_FLAG32", "IMAGE_ORDINAL_FLAG64", "IMAGE_IMPORT_BY_NAME", "GetProcAddress 오디널", "MAKEINTRESOURCE", "ws2_32 오디널 임포트"]
aliases: ["오디널 임포트란", "이름 없는 임포트 함수", "오디널로 GetProcAddress 호출", "IDA ordinal_123 미해석"]
symptom_keywords: ["IDA에 ordinal_123 같은 이름만 보임", "임포트 함수 이름이 안 보이고 숫자만 보임", "오디널을 실제 함수 이름으로 바꾸는 법을 모름", "ws2_32 dll 임포트가 이름이 아니라 번호로 되어 있음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Ordinal Import는 Import Thunk가 함수 이름 대신 대상 DLL의 Export Table 안에서의 순번(오디널)만으로 함수를 지목하는 방식으로, 이름 문자열이 파일 어디에도 남지 않기 때문에 IDA 같은 도구가 잘 알려진 DLL의 오디널-이름 매핑을 미리 알고 있지 않으면 `ordinal_123`처럼 의미 없는 표시로만 보이게 되어, 대상 DLL의 실제 Export Table을 오디널 기준으로 대조해야 진짜 함수 이름을 알아낼 수 있다.

## 언제 검색해야 하나
- IDA 임포트 목록이나 디스어셈블리에 `ws2_32_1`, `ordinal_17`처럼 함수 이름 대신 번호가 붙은 임포트가 보일 때
- `GetProcAddress`를 호출하는 코드에서 두 번째 인자가 문자열 포인터가 아니라 정수 상수로만 되어 있어서 어떤 함수인지 알 수 없을 때
- `ws2_32.dll`, `wsock32.dll`, MFC/VB 런타임 DLL을 임포트하는 바이너리를 분석하는데 함수 이름이 유독 안 보일 때
- 오디널로만 임포트하는 것이 은닉/난독화 기법인지, 아니면 그냥 오래된 관례인지 판단하고 싶을 때
- 오디널을 실제 함수 이름으로 수동 복원하는 절차가 필요할 때

## 핵심 개념

### IMAGE_THUNK_DATA의 두 가지 형태
Import Name Table(INT)/Import Address Table(IAT)의 각 항목은 `IMAGE_THUNK_DATA`(union)이며, 최상위 비트로 두 가지 형태 중 하나를 나타낸다.
```c
// 32비트
#define IMAGE_ORDINAL_FLAG32 0x80000000
// 64비트
#define IMAGE_ORDINAL_FLAG64 0x8000000000000000ULL

typedef union _IMAGE_THUNK_DATA32 {
    DWORD ForwarderString;
    DWORD Function;
    DWORD Ordinal;            // 최상위 비트=1이면 하위 16비트가 오디널 번호
    DWORD AddressOfData;      // 최상위 비트=0이면 IMAGE_IMPORT_BY_NAME으로의 RVA
} IMAGE_THUNK_DATA32;
```
최상위 비트가 1이면, 이 항목은 이름을 전혀 담지 않고 하위 16비트에 있는 **오디널 번호만으로** 대상 DLL의 Export Table에서 함수를 찾으라는 뜻이다. 최상위 비트가 0이면 나머지 비트는 `IMAGE_IMPORT_BY_NAME`(`Hint`(WORD) + 널 종료 함수 이름 문자열)으로의 RVA다. 즉 **일반적인 이름 기반 임포트라면 파일 안에 `"CreateFileW"` 같은 문자열이 그대로 남아있지만, 오디널 임포트는 그 문자열이 원천적으로 존재하지 않는다.**

### API 레벨에서의 대응: GetProcAddress
런타임에 동적으로 함수를 가져올 때도 동일한 개념이 적용된다. `GetProcAddress(hModule, lpProcName)`의 `lpProcName`이 일반 문자열 포인터가 아니라 `MAKEINTRESOURCE(ordinal)`(내부적으로 하위 16비트만 유효한 정수를 문자열 포인터처럼 캐스팅한 특수 값, 상위 16비트는 0)로 넘어오면, 이는 이름이 아니라 오디널로 함수를 찾으라는 신호다. 디스어셈블리에서 `GetProcAddress` 호출 직전 두 번째 인자를 준비하는 코드가 문자열 주소를 로드하는 대신 작은 정수 상수를 그대로 레지스터에 넣고 있다면 오디널 호출로 의심해야 한다.

### Export Table의 Hint와 오디널 임포트의 관계
이름 기반 임포트에서도 `IMAGE_IMPORT_BY_NAME` 구조에는 이름 문자열 앞에 `Hint`라는 WORD 필드가 있다. 이는 "이 함수가 대상 DLL의 Export Name Pointer Table에서 대략 이 인덱스 근처에 있을 것"이라는 힌트로, 로더가 이진 탐색 전에 먼저 확인해보는 최적화용 값일 뿐 틀려도 로더는 정상적으로 이름 기반 이진 탐색으로 폴백한다. 오디널 임포트는 이 힌트 단계조차 건너뛰고 곧바로 `AddressOfFunctions[Ordinal - Base]`로 함수 주소를 얻으므로, 이름 기반 방식보다 검색 비용이 원천적으로 적다는 점에서 `Hint` 필드의 존재 자체가 "이름 기반 조회도 결국 오디널 기반 배열 인덱싱으로 귀결된다"는 것을 보여주는 좋은 대조군이다.

### 왜 오디널 임포트가 쓰이는가
역사적으로 몇 가지 이유가 있다.
- **성능** — 이름 문자열 비교 없이 곧바로 Export Address Table의 인덱스로 접근할 수 있어 이론상 더 빠르다(현대 시스템에서는 체감 차이가 거의 없다).
- **관례/레거시** — MFC, 일부 VB 런타임, 그리고 `ws2_32.dll`/`wsock32.dll`의 Winsock 1.1 호환 함수 일부(오디널 1~19 부근)처럼, 이름 export를 아예 제공하지 않고 오디널로만 export하는 전통적인 DLL들이 있다.
- **은닉/난독화 목적** — 이름이 파일에 전혀 남지 않으므로, 문자열 기반 정적 시그니처 스캐너나 사람이 임포트 목록을 훑어보는 초기 트리아지를 어렵게 만들 수 있다. 다만 대상이 이름 export도 정상적으로 제공하는 일반 DLL(예: `kernel32.dll`)인데 굳이 오디널로만 임포트한다면, 이는 흔치 않은 선택이라 의심스러운 신호로 볼 수 있다.

## 화면/코드에서 보이는 징후
- IDA 임포트 목록에 `ws2_32_1`, `ordinal_247`처럼 DLL 이름 뒤에 숫자만 붙은 함수 이름이 보임(IDA가 알려진 DLL의 오디널 데이터베이스를 갖고 있으면 일부는 자동으로 실제 이름으로 표시되기도 함, 예: `ws2_32.dll` 오디널 111은 `WSAStartup`으로 자동 인식되는 경우가 많음)
- `GetProcAddress` 호출부에서 두 번째 인자가 스택/레지스터에 작은 정수 상수로만 준비됨(`mov edx, 17` 형태)
- Detect It Easy나 PE-bear의 Import 뷰에서 함수 이름 컬럼이 비어있고 `Ordinal` 컬럼에만 숫자가 채워짐
- Export Table(REV-0120)을 가진 대상 DLL 자체를 열어보면, 그 DLL도 `AddressOfNames`가 비어있거나 일부 함수만 이름 export를 갖고 나머지는 오디널로만 export하는 경우가 있음(오디널 임포트가 강제되는 근본 원인)

## 가장 먼저 할 것
오디널로만 표시되는 임포트를 만나면, 먼저 대상 DLL이 무엇인지 확인한다(파일명으로 바로 알 수 있음). 그 다음 그 DLL의 실제 사본(분석 환경의 `System32` 등)을 PE-bear나 IDA로 열어 Export Table을 확인하고, 같은 오디널 번호를 가진 export 항목의 이름을 찾는다.

## 단계별 절차
**1) 오디널 값 확인**
`IMAGE_THUNK_DATA`의 최상위 비트가 켜진 항목에서 하위 16비트를 추출해 오디널 번호를 얻는다(IDA는 보통 이 값을 임포트 이름 뒤에 자동으로 붙여 표시한다).

**2) 대상 DLL의 Export Table 열기**
같은 이름의 실제 DLL 파일(가급적 분석 대상 프로그램이 실행되는 것과 같은 Windows 버전의 것)을 확보해 Export Directory Table을 확인한다.

**3) 오디널로 함수 이름 찾기**
Export Table에는 `Base`(오디널 시작값), `AddressOfFunctions`(오디널 순 함수 주소 배열), `AddressOfNames`/`AddressOfNameOrdinals`(이름이 있는 함수만 이름↔오디널 매핑)가 있다(REV-0120 참고). 찾는 오디널이 `AddressOfNameOrdinals` 배열 어딘가에 있으면 대응하는 `AddressOfNames` 항목이 실제 함수 이름이다. 만약 그 DLL이 애초에 이 함수에 이름 export를 전혀 제공하지 않는다면(진짜 오디널 전용 export), 함수 이름은 공식 문서나 커뮤니티 데이터베이스에서 찾아야 한다.

**4) IDA에 수동 주석/이름 부여**
찾은 실제 함수 이름을 IDA에서 해당 임포트 항목에 이름을 바꿔주면(`N` 단축키) 이후 xref, 디스어셈블리 표시가 모두 그 이름으로 정리되어 분석이 훨씬 편해진다.

## 명령어/단축키
```text
IDA: 임포트 항목 위에서 N (Rename) — 오디널 → 실제 이름으로 수동 지정
PE-bear: 대상 DLL을 열어 Export Directory 탭에서 오디널/이름 매핑 확인
dumpbin (Windows SDK): dumpbin /exports 대상.dll   — 오디널과 이름을 나란히 출력
```

## 출력 해석
- `dumpbin /exports`의 출력에서 `ordinal hint RVA name` 형식의 표를 보고, 찾는 오디널 번호와 일치하는 행의 `name` 컬럼이 실제 함수 이름
- 찾는 오디널에 대응하는 행에 `name`이 비어있고 `RVA`만 있으면, 이 함수는 그 DLL에서 정말로 이름 없이 오디널로만 export되는 함수라는 뜻이며, 이름을 알아내려면 해당 DLL/오디널 조합을 다루는 공개 레퍼런스나 SDK 헤더의 `.def` 파일을 찾아야 한다
- IDA가 자동으로 실제 이름을 표시해준 임포트(`ws2_32.dll`처럼 잘 알려진 DLL)는 IDA 내장 오디널 데이터베이스 덕분이며, 그렇지 않은 DLL은 수동으로 확인해야 한다

## 흔한 실수
- 오디널로 임포트됐다는 것 자체를 곧바로 "악성/난독화"로 단정하는 것 — `ws2_32.dll`, MFC 등 정상적인 프로그램에서도 오디널 임포트는 매우 흔하다. 대상 DLL이 원래 이름 export를 제공하는데도 굳이 오디널만 쓰는 경우에 한해 의심의 우선순위를 높여야 한다.
- 32비트와 64비트의 오디널 플래그 비트 크기(`IMAGE_ORDINAL_FLAG32`의 `0x80000000` vs `IMAGE_ORDINAL_FLAG64`의 `0x8000000000000000ULL`)를 혼동해서 잘못된 비트로 마스킹하는 것.
- 오디널 번호가 Windows 버전마다 달라질 수 있다는 걸 모르고, 분석 환경과 다른 버전의 DLL에서 얻은 오디널-이름 매핑을 그대로 신뢰하는 것 — 반드시 분석 대상과 동일하거나 최대한 가까운 버전의 DLL로 대조해야 한다.
- `GetProcAddress`에 오디널이 아니라 이름 문자열이 넘어가는 일반적인 경우와 오디널 케이스를 디스어셈블리에서 구분하지 못하고 무조건 문자열 xref만 찾다가 오디널 호출을 놓치는 것.

## 막혔을 때 다음 체크
- Import Table/IAT/INT의 기본 구조가 헷갈리면 → [Import Table에서 중요한 API 찾기](./rev-0119-import-table.md)
- 대상 DLL의 Export Table 구조(`AddressOfFunctions`/`AddressOfNames`/`AddressOfNameOrdinals`)를 자세히 보고 싶으면 → [Export Table과 DLL 함수](./rev-0120-export-table.md)
- 런타임에 이름/오디널로 `GetProcAddress`를 호출하는 동적 해석 패턴이 궁금하면 → [GetProcAddress LoadLibrary 동적 API 해석](./rev-0129-getprocaddress-loadlibrary.md)
- 로딩 시점 자체를 늦추는 Delay-Load, 미리 주소를 계산해두는 Bound Import와 비교하고 싶으면 → [Delay-Load Import 이해하기](./rev-0553-delay-load-import.md), [Bound Import와 Import 최적화 이해하기](./rev-0554-bound-import.md)

## 미니 예제
`chat_client.exe`(32비트)를 IDA로 열었더니 임포트 목록에 `ws2_32.dll`의 함수들이 `ws2_32_1`, `ws2_32_2`, `ws2_32_111` 같은 이름으로만 표시되어 있었다. IDA가 이미 잘 알려진 `ws2_32.dll` 오디널 데이터베이스를 갖고 있어 `ws2_32_111`은 자동으로 `WSAStartup`으로 표시되었지만, `ws2_32_1`과 `ws2_32_2`는 그대로 번호만 남아있었다. 분석 환경의 실제 `ws2_32.dll`을 PE-bear로 열어 Export Table을 확인하니 오디널 `1`은 `accept`, 오디널 `2`는 `bind`였다. 이는 Winsock 1.1 호환성을 위해 `ws2_32.dll`이 낮은 번호대 오디널을 레거시 소켓 API에 그대로 유지하고 있는 잘 알려진 관례이며, 은닉 목적이 아니라 단순한 관행적 오디널 임포트의 전형적인 예다. IDA에서 두 임포트에 각각 `N`으로 `accept`, `bind` 이름을 수동으로 붙여주니 이후 디스어셈블리가 훨씬 읽기 쉬워졌다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0120 — Export Table과 DLL 함수
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0553 — Delay-Load Import 이해하기
- REV-0554 — Bound Import와 Import 최적화 이해하기

## 출처/검증
- `IMAGE_THUNK_DATA`, `IMAGE_ORDINAL_FLAG32`/`64`, `IMAGE_IMPORT_BY_NAME` 구조/상수 정의: Microsoft Learn "PE Format" 공식 문서 기준 (2026-09-08 검증).
- `GetProcAddress`와 `MAKEINTRESOURCE`를 이용한 오디널 기반 조회: Microsoft Learn Win32 API 공식 문서 기준.
- `ws2_32.dll`의 Winsock 1.1 호환 오디널 관례: Microsoft Learn Winsock 관련 공식 문서 및 다수 리버싱 참고자료 공통 설명 기준.
