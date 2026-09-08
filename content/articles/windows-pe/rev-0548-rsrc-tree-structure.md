---
id: REV-0548
title: ".rsrc 섹션 트리 구조 자세히 읽는 법"
slug: "rev-0548-rsrc-tree-structure"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", "Resource Hacker", HxD]
keywords: ["IMAGE_RESOURCE_DIRECTORY", "IMAGE_RESOURCE_DIRECTORY_ENTRY", "IMAGE_RESOURCE_DATA_ENTRY", "IMAGE_RESOURCE_DIR_STRING_U", ".rsrc", "리소스 디렉터리 트리"]
aliases: ["rsrc 섹션 구조체", "리소스 디렉터리 파싱", "IMAGE_RESOURCE_DIRECTORY_ENTRY 하이비트", "리소스 트리 3단계"]
symptom_keywords: ["rsrc 섹션 내부 구조체를 모름", "리소스 디렉터리 엔트리의 하이비트 의미를 모름", "리소스 이름 문자열이 어떻게 저장되는지 모름", "직접 rsrc 파서를 짜야 함"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`.rsrc` 섹션은 `IMAGE_RESOURCE_DIRECTORY`와 `IMAGE_RESOURCE_DIRECTORY_ENTRY`로 이루어진 Type→Name/ID→Language 3단계 트리이며, 각 엔트리의 최상위 비트가 "이게 이름 문자열인지 숫자 ID인지", "이게 하위 디렉터리로 더 내려가는지 아니면 실제 데이터인지"를 구분하는 스위치 역할을 하기 때문에, 이 하이비트 규칙을 알아야 Resource Hacker 같은 GUI 도구 없이도 직접 리소스를 파싱하거나 도구가 못 읽는 손상된/변조된 리소스를 손으로 분석할 수 있다.

## 언제 검색해야 하나
- Resource Hacker 같은 GUI 도구가 특정 리소스를 파싱하지 못하고 깨져 보일 때, 원인을 직접 헥스로 확인하고 싶을 때
- 직접 `.rsrc` 파서 스크립트를 짜야 하는데 `IMAGE_RESOURCE_DIRECTORY_ENTRY`의 `Name`/`OffsetToData` 필드의 하이비트 의미를 모를 때
- 리소스 이름이 숫자 ID가 아니라 문자열로 되어 있는 경우(예: 커스텀 리소스 타입 이름) 그 문자열이 실제로 어디에, 어떤 형식으로 저장되는지 궁금할 때
- IDA의 리소스 뷰나 PE-bear의 `Resources` 트리에서 보이는 계층이 실제 파일 바이트 구조와 어떻게 대응되는지 확인하고 싶을 때
- 안티 리버싱 목적으로 리소스 디렉터리 구조 자체가 변조된 파일을 만났을 때

## 핵심 개념

### 세 단계 트리: Type → Name/ID → Language
`.rsrc`는 `OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_RESOURCE]`(인덱스 2)가 가리키는 위치부터 시작하는 트리 구조다. 트리는 정확히 3단계로 구성된다.
```text
Level 1 (Type)      : RT_ICON, RT_VERSION, RT_MANIFEST, RT_RCDATA 등 리소스 종류
  Level 2 (Name/ID)  : 같은 Type 안에서 개별 리소스를 구분하는 이름 또는 숫자 ID
    Level 3 (Language): 언어별 버전(예: 0x0409=영어(미국), 0x0412=한국어)
      → 실제 데이터(IMAGE_RESOURCE_DATA_ENTRY)
```
각 레벨은 동일한 형식의 `IMAGE_RESOURCE_DIRECTORY` 헤더로 시작하고, 그 뒤에 여러 개의 `IMAGE_RESOURCE_DIRECTORY_ENTRY`가 이어지는 동일한 패턴이 재귀적으로 반복된다.

### IMAGE_RESOURCE_DIRECTORY
```c
typedef struct _IMAGE_RESOURCE_DIRECTORY {
    DWORD Characteristics;       // 사용 안 함, 항상 0
    DWORD TimeDateStamp;
    WORD  MajorVersion;
    WORD  MinorVersion;
    WORD  NumberOfNamedEntries;  // 이름(문자열)으로 된 엔트리 개수
    WORD  NumberOfIdEntries;     // 숫자 ID로 된 엔트리 개수
    // 이어서 (NumberOfNamedEntries + NumberOfIdEntries)개의
    // IMAGE_RESOURCE_DIRECTORY_ENTRY 배열
} IMAGE_RESOURCE_DIRECTORY;      // 16바이트 헤더
```
이름 엔트리가 항상 ID 엔트리보다 먼저 오도록 정렬되어 있다는 점이 중요하다. 즉 배열의 앞쪽 `NumberOfNamedEntries`개는 이름 기반, 나머지 `NumberOfIdEntries`개는 숫자 ID 기반이다.

### IMAGE_RESOURCE_DIRECTORY_ENTRY와 하이비트 규칙
```c
typedef struct _IMAGE_RESOURCE_DIRECTORY_ENTRY {
    union {
        struct {
            DWORD NameOffset : 31;  // 이름 문자열의 오프셋(하이비트=1일 때)
            DWORD NameIsString : 1; // 1이면 이름, 0이면 숫자 ID
        };
        DWORD Id;                  // NameIsString=0일 때 그냥 숫자 ID로 사용
        DWORD Name;                // 원시 32비트 값(하이비트 포함)
    };
    union {
        DWORD OffsetToData;          // 하이비트=0: 실제 데이터(IMAGE_RESOURCE_DATA_ENTRY)로의 오프셋
        struct {
            DWORD OffsetToDirectory : 31; // 하이비트=1: 하위 디렉터리로의 오프셋
            DWORD DataIsDirectory : 1;
        };
    };
} IMAGE_RESOURCE_DIRECTORY_ENTRY;  // 8바이트
```
핵심은 **두 필드 모두 최상위 비트(`0x80000000`)가 스위치라는 것**이다.
- `Name` 필드의 최상위 비트가 1이면, 나머지 31비트는 리소스 디렉터리 시작 위치(`.rsrc`의 base RVA)로부터의 오프셋이며, 그 위치에는 `IMAGE_RESOURCE_DIR_STRING_U`(WORD 길이 + UTF-16LE 문자열, 널 종료 없음)가 있다. 최상위 비트가 0이면 나머지 값은 그냥 숫자 ID(예: `RT_VERSION`=16, `RT_ICON`=3)다.
- `OffsetToData` 필드의 최상위 비트가 1이면, 나머지 31비트는 **하위 `IMAGE_RESOURCE_DIRECTORY`**(다음 레벨)로의 오프셋이다. 최상위 비트가 0이면, 나머지 값은 실제 데이터를 가리키는 `IMAGE_RESOURCE_DATA_ENTRY`로의 오프셋이며, 이는 트리의 리프(맨 아래 Language 레벨)에서만 나타난다.

이 두 하이비트 규칙 덕분에 파서는 별도의 "이게 몇 단계인지" 메타데이터 없이도 트리를 재귀적으로 순회할 수 있다.

### IMAGE_RESOURCE_DATA_ENTRY
트리의 리프에 도달하면 최종적으로 다음 구조체를 가리킨다.
```c
typedef struct _IMAGE_RESOURCE_DATA_ENTRY {
    DWORD OffsetToData;  // 실제 리소스 바이트의 RVA(★ 이 필드만 예외적으로 RVA, 오프셋이 아님)
    DWORD Size;           // 실제 리소스 바이트 크기
    DWORD CodePage;
    DWORD Reserved;
} IMAGE_RESOURCE_DATA_ENTRY;
```
주의할 점은 `IMAGE_RESOURCE_DIRECTORY_ENTRY`의 오프셋들은 모두 "리소스 디렉터리 시작 위치로부터의 상대 오프셋"인데, `IMAGE_RESOURCE_DATA_ENTRY.OffsetToData`만 **이미지 전체 기준 RVA**라는 점이다. 이걸 혼동해서 리소스 디렉터리 base를 더해버리면 완전히 엉뚱한 위치를 읽게 된다.

## 화면/코드에서 보이는 징후
- IDA 리소스 뷰나 PE-bear `Resources` 탭에서 Type/Name/Language 3단 트리가 폴더처럼 펼쳐져 보임
- Resource Hacker의 좌측 트리도 동일하게 `RT_ICON → 101 → 1033(영어)` 같은 3단 경로로 표시됨
- 커스텀 리소스 타입(숫자가 아니라 `"MYDATA"`처럼 문자열 타입)을 쓰는 파일은 Type 레벨 엔트리의 `Name` 필드가 하이비트=1이고, 이는 표준 `RT_*` 상수를 쓰는 대다수 리소스와 다르게 도구에서 문자열 이름으로 표시됨
- 헥스 에디터로 `.rsrc` 시작 부분을 보면 16바이트 헤더 뒤에 8바이트 엔트리들이 촘촘히 이어지는 규칙적인 패턴이 보임

## 가장 먼저 할 것
`.rsrc`를 직접 파싱해야 한다면, 먼저 `IMAGE_DIRECTORY_ENTRY_RESOURCE`의 RVA를 "리소스 디렉터리 base"로 고정해두고, 이후 모든 `IMAGE_RESOURCE_DIRECTORY_ENTRY`의 오프셋 필드는 이 base에 대한 상대값이라는 점을 코드/메모 어디에나 명시해둔다. `IMAGE_RESOURCE_DATA_ENTRY.OffsetToData`만 예외적으로 이미지 전체 RVA라는 점을 반드시 별도로 처리한다.

## 단계별 절차
**1) 리소스 디렉터리 base 구하기**
`OptionalHeader.DataDirectory[2].VirtualAddress`가 Type 레벨 `IMAGE_RESOURCE_DIRECTORY`의 시작 RVA다. 이 값을 base로 저장해둔다.

**2) Type 레벨 순회**
base 위치의 16바이트 헤더에서 `NumberOfNamedEntries + NumberOfIdEntries`개의 엔트리를 읽는다. 각 엔트리의 `Name`으로 리소스 종류(예: `RT_VERSION`=16)를 판별한다.

**3) Name/ID 레벨로 내려가기**
`OffsetToData`의 하이비트가 1이면 `base + (OffsetToData & 0x7FFFFFFF)` 위치에 있는 다음 `IMAGE_RESOURCE_DIRECTORY`로 이동해 2단계와 같은 방식으로 순회한다.

**4) Language 레벨로 내려가서 데이터 획득**
같은 방식으로 한 번 더 내려가면 리프에 도달한다. 이번엔 `OffsetToData`의 하이비트가 0이어야 하며, `base + OffsetToData` 위치의 `IMAGE_RESOURCE_DATA_ENTRY`를 읽는다. 그 안의 `OffsetToData`(이번엔 이미지 전체 RVA)와 `Size`로 실제 리소스 바이트를 읽는다.

## 명령어/단축키
```text
IDA: 리소스 뷰(Resources) — Type/Name/Language 트리 클릭하며 탐색
PE-bear: Resources 탭 — 트리 노드를 클릭하면 우측에 오프셋/크기/헥스 표시
Resource Hacker: 좌측 트리 탐색, 우클릭 → Save Resource As Binary File로 원시 바이트 추출
```

## 출력 해석
- Type 레벨 엔트리의 `Name` 하이비트가 0이고 값이 익숙한 `RT_*` 상수(3=아이콘, 16=버전 정보, 24=매니페스트 등)와 일치하면 표준 리소스
- Type 레벨 엔트리의 `Name` 하이비트가 1이면 커스텀(문자열) 타입 — 그 이름 문자열이 무엇인지 확인해서 개발자가 임의로 정의한 리소스일 가능성을 염두에 두어야 함
- `NumberOfNamedEntries`가 비정상적으로 크거나(수천 개) `OffsetToData`가 `.rsrc` 섹션 크기를 넘어서는 값이면 리소스 디렉터리 자체가 변조/손상된 것으로 의심
- 트리가 3단계보다 깊거나 얕게 보이는 도구 출력이 있다면, 그 도구가 편의상 재구성한 표시 방식일 뿐이며 파일 실제 구조는 항상 정확히 3단계임을 기억해야 함(Type/Name/Language 셋 중 하나가 항상 단일 값이라 생략된 것처럼 보일 수 있음)

## 흔한 실수
- `IMAGE_RESOURCE_DIRECTORY_ENTRY`의 오프셋 필드들을 이미지 전체 기준 RVA로 착각해서 리소스 디렉터리 base를 더하지 않고 읽는 것 — `IMAGE_RESOURCE_DATA_ENTRY.OffsetToData`만 예외적으로 RVA이고 나머지는 전부 base 상대 오프셋이다.
- 하이비트를 마스킹하지 않고 `OffsetToData`나 `Name` 값을 그대로 오프셋/ID로 써서 엉뚱한 위치를 읽는 것 — 반드시 `& 0x7FFFFFFF`로 하위 31비트만 취해야 한다.
- `NumberOfNamedEntries`와 `NumberOfIdEntries`의 순서(이름이 항상 먼저)를 무시하고 배열을 순서 없이 순회하다가 이름/ID 판별을 잘못하는 것.
- `IMAGE_RESOURCE_DIR_STRING_U`가 널 종료 문자열이 아니라 **길이 접두 UTF-16LE 문자열**이라는 걸 모르고 널 바이트를 찾다가 파싱이 깨지는 것.
- 3단계 트리 깊이를 임의로 가정하고 재귀 없이 하드코딩된 3중 for문만 짜는 것 — 실제로는 항상 정확히 3단계이므로 이 자체는 맞지만, 코드에서 "하위 디렉터리인지 데이터인지"를 매번 하이비트로 재확인하지 않고 레벨 번호만으로 판단하면 변형된 파일에서 깨질 수 있다.

## 막혔을 때 다음 체크
- 리소스 안에 숨겨진 페이로드를 찾는 실전 절차와 `RT_RCDATA` 위장 기법이 궁금하면 → [Resource Section과 숨겨진 데이터 확인](./rev-0141-resource-section.md)
- 버전 정보 리소스(`RT_VERSION`)의 내부 구조와 단서를 자세히 보고 싶으면 → [버전 정보(Version Info) 리소스에서 단서 찾기](./rev-0549-version-info-resource.md)
- 매니페스트(`RT_MANIFEST`) 리소스에서 실행 요구사항을 읽는 법이 궁금하면 → [매니페스트(Manifest)에서 실행 요구사항 확인하기](./rev-0550-manifest-execution-requirements.md)
- 리소스 디렉터리의 RVA를 파일 오프셋으로 바꾸는 계산이 헷갈리면 → [RVA VA Raw Offset 계산](./rev-0118-rva-va-raw-offset.md)

## 미니 예제
`.rsrc`가 RVA `0x2A000`에서 시작한다고 하자(base=`0x2A000`). Type 레벨 헤더를 읽으니 `NumberOfIdEntries=1`이고 엔트리 하나가 `Name=16`(`RT_VERSION`), `OffsetToData=0x80000028`이다. 하이비트가 1이므로 `0x2A000 + (0x28) = 0x2A028`에 Name/ID 레벨 디렉터리가 있다. 그곳의 엔트리는 `Name=1`(리소스 ID 1), `OffsetToData=0x80000040`이며, 다시 하이비트가 1이므로 `0x2A000+0x40=0x2A040`이 Language 레벨이다. 거기서 `Name=0x0412`(한국어), `OffsetToData=0x00000058`(하이비트 0)을 읽어 `0x2A000+0x58=0x2A058`의 `IMAGE_RESOURCE_DATA_ENTRY`를 확인하니 `OffsetToData=0x2A400`(이번엔 이미지 전체 RVA), `Size=0x2C0`이다. 최종적으로 RVA `0x2A400`부터 `0x2C0`바이트가 이 EXE의 한국어 버전 정보 원시 데이터다.

## 관련 글
- REV-0141 — Resource Section과 숨겨진 데이터 확인
- REV-0549 — 버전 정보(Version Info) 리소스에서 단서 찾기
- REV-0550 — 매니페스트(Manifest)에서 실행 요구사항 확인하기
- REV-0551 — 아이콘/커서 리소스에서 숨겨진 데이터 찾기
- REV-0118 — RVA VA Raw Offset 계산

## 출처/검증
- `IMAGE_RESOURCE_DIRECTORY`, `IMAGE_RESOURCE_DIRECTORY_ENTRY`, `IMAGE_RESOURCE_DATA_ENTRY`, `IMAGE_RESOURCE_DIR_STRING_U` 구조체 정의와 하이비트 규칙: Microsoft Learn "PE Format" 공식 문서의 ".rsrc Section" 항목 기준 (2026-09-08 검증).
- 표준 `RT_*` 리소스 타입 상수: Microsoft Win32 리소스 관련 공식 문서 기준.
