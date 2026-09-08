---
id: REV-0551
title: "아이콘/커서 리소스에서 숨겨진 데이터 찾기"
slug: "rev-0551-icon-cursor-hidden-data"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "Resource Hacker", HxD, "PE-bear"]
keywords: ["RT_ICON", "RT_GROUP_ICON", "RT_CURSOR", "RT_GROUP_CURSOR", "GRPICONDIR", "ICONDIRENTRY", "아이콘 스테가노그래피"]
aliases: ["아이콘 리소스 구조", "그룹 아이콘 디렉터리", "아이콘에 데이터 숨기기", "커서 리소스 구조"]
symptom_keywords: ["아이콘 리소스 크기가 비정상적으로 큼", "아이콘 파일 안에 실행 파일이 숨어있는 것 같음", "GRPICONDIR가 뭔지 모름", "고아 아이콘 리소스가 있음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
아이콘은 `RT_ICON`(실제 이미지 데이터)과 `RT_GROUP_ICON`(어떤 해상도들의 `RT_ICON`을 묶어 하나의 아이콘 세트로 쓸지 정의하는 목록)이 서로 참조하는 2단 구조이기 때문에, `RT_GROUP_ICON`이 선언한 크기와 실제 `RT_ICON` 데이터 크기가 맞지 않거나, 어떤 `RT_GROUP_ICON`에서도 참조되지 않는 "고아" `RT_ICON`이 있다면 그 여분 바이트가 숨겨진 페이로드일 가능성을 의심해야 한다.

## 언제 검색해야 하나
- 아이콘 하나만 있는 단순한 프로그램인데 `.rsrc` 섹션이나 특정 아이콘 리소스 크기가 비정상적으로 클 때
- Resource Hacker에서 아이콘을 열었는데 렌더링은 정상인데 리소스 원본 바이트 크기가 이미지 해상도로 계산되는 이론적 크기보다 훨씬 클 때
- `RT_ICON` 리소스 ID들 중 일부가 `RT_GROUP_ICON`의 참조 목록에 나타나지 않는 경우를 발견했을 때
- 아이콘/커서 리소스를 이용한 스테가노그래피(steganography) 기법의 원리를 이해하고 싶을 때

## 핵심 개념

### RT_GROUP_ICON과 RT_ICON의 관계
윈도우 아이콘은 하나의 이미지가 아니라 여러 해상도(16x16, 32x32, 48x48, 256x256 등)와 색 심도를 담은 세트로 이루어진다. 이 세트를 관리하기 위해 두 종류의 리소스가 짝을 이룬다.
- **`RT_GROUP_ICON`**(타입 14) — "이 아이콘 세트는 어떤 해상도/색상 조합의 이미지들로 구성되며, 각각이 몇 번 `RT_ICON` 리소스 ID를 가리키는지"를 나열한 인덱스 역할의 작은 구조체(`GRPICONDIR`)
- **`RT_ICON`**(타입 3) — 실제 이미지 픽셀 데이터(BMP 형식의 `BITMAPINFOHEADER`+컬러 데이터, 또는 256x256 이상 큰 아이콘은 PNG로 압축되어 저장되기도 함)

```c
// GRPICONDIR (RT_GROUP_ICON 원시 데이터의 시작부)
typedef struct {
    WORD idReserved;   // 0
    WORD idType;        // 1 = 아이콘
    WORD idCount;        // 포함된 이미지 개수
    // 이어서 idCount개의 GRPICONDIRENTRY
} GRPICONDIR;

typedef struct {
    BYTE  bWidth;
    BYTE  bHeight;
    BYTE  bColorCount;
    BYTE  bReserved;
    WORD  wPlanes;
    WORD  wBitCount;
    DWORD dwBytesInRes;   // ★ 이 이미지의 실제 바이트 크기(선언값)
    WORD  nID;            // ★ 이 이미지가 저장된 RT_ICON의 리소스 ID
} GRPICONDIRENTRY;
```
분석 시 핵심은 `dwBytesInRes`(이 항목이 선언하는 크기)와, `nID`가 가리키는 실제 `RT_ICON` 리소스의 `IMAGE_RESOURCE_DATA_ENTRY.Size`(REV-0548 참고)가 정확히 일치해야 정상이라는 점이다.

### 아이콘에 데이터를 숨기는 두 가지 전형적인 방식
**1. 크기 불일치(트레일링 데이터) 방식** — `GRPICONDIRENTRY.dwBytesInRes`가 예를 들어 `1128`바이트(32x32, 32비트 정상 아이콘 크기)라고 선언되어 있는데, 실제로 `nID`가 가리키는 `RT_ICON`의 `Size`는 `1128 + 500000`바이트라고 하자. 아이콘 렌더러는 앞의 `1128`바이트만 읽어 정상적으로 아이콘을 표시하므로 겉보기에는 아무 문제가 없어 보이지만, 리소스 전체를 원시로 추출해보면 정상 아이콘 데이터 뒤에 50만 바이트짜리 여분 데이터가 그대로 붙어있다.

**2. 고아(orphan) 리소스 방식** — `RT_ICON` 아래에 리소스 ID가 여러 개 있는데, 그중 일부 ID가 **어떤 `RT_GROUP_ICON`의 `GRPICONDIRENTRY.nID`에서도 참조되지 않는** 경우다. 이런 ID는 실제로 화면에 그려지는 아이콘 세트에 포함되지 않으므로 렌더러도, 대부분의 자동화 분석 도구도 무시하고 지나치기 쉽다. 하지만 리소스 트리 자체에는 존재하므로, `RT_ICON` 타입 아래의 모든 ID 목록과 모든 `RT_GROUP_ICON`이 실제로 참조하는 ID 목록을 비교하면 이런 고아 항목을 찾아낼 수 있다.

큰 아이콘 세트(여러 해상도, 컬러 뎁스 조합)는 원래도 수십~수백 KB에 이를 수 있기 때문에 "아이콘치고 크다"는 인상만으로는 눈치채기 어렵고, 그래서 공격자들이 다른 `RT_RCDATA` 같은 리소스보다 오히려 아이콘을 은닉 장소로 선호하기도 한다.

### RT_CURSOR / RT_GROUP_CURSOR도 동일한 원리
커서 리소스는 아이콘과 형제 관계에 있는 리소스 타입으로, `RT_CURSOR`(1)와 `RT_GROUP_CURSOR`(12)가 각각 `RT_ICON`/`RT_GROUP_ICON`과 거의 동일한 역할을 한다. 차이는 `GRPICONDIRENTRY`에 해당하는 커서용 구조체가 `bWidth`/`bHeight` 대신 커서의 클릭 기준점을 나타내는 `wXHotspot`/`wYHotspot` 필드를 추가로 갖는다는 정도다. 원리가 동일하기 때문에 앞서 설명한 크기 불일치·고아 리소스 탐지 절차를 커서에도 그대로 적용할 수 있다. 다만 커서는 아이콘보다 훨씬 드물게 쓰이므로(대부분 프로그램은 커서를 커스터마이징하지 않고 시스템 기본 커서를 그대로 쓴다), 실행 파일 안에 `RT_CURSOR`/`RT_GROUP_CURSOR`가 존재하는 것 자체가 상대적으로 눈에 띄는 신호가 될 수 있다.

### 큰 아이콘의 PNG 압축과 크기 판단의 함정
Windows Vista 이후 256x256 같은 대형 아이콘은 비압축 BMP 대신 PNG 형식으로 저장되는 것이 허용된다(`GRPICONDIRENTRY`의 시작 4바이트가 PNG 시그니처 `89 50 4E 47`인지로 구분). PNG는 압축률이 이미지 내용에 따라 크게 달라지므로, "이 해상도 아이콘의 이론적 크기는 이 정도여야 한다"는 계산이 BMP만큼 정확하지 않다. 따라서 PNG 형식 아이콘을 검사할 때는 `dwBytesInRes`와 실제 리소스 `Size`의 일치 여부만으로 판단하고, 절대적인 예상 크기 계산에 지나치게 의존하지 않는 것이 좋다 — 이 경우에도 여전히 유효한 검증 기준은 "선언된 크기와 실제 데이터 크기가 정확히 같은가"이다.

## 화면/코드에서 보이는 징후
- Resource Hacker에서 아이콘은 정상적으로 렌더링되어 보이는데, 해당 리소스를 "Save Resource As Binary File"로 저장한 파일 크기가 그 해상도의 이론적 크기(예: 32x32 32비트 BMP 기준 약 4KB 이하)보다 훨씬 큼
- PE-bear의 `Resources` 트리에서 `RT_ICON` 아래 리소스 ID 개수가 같은 파일의 `RT_GROUP_ICON`이 나열하는 `idCount` 합계보다 많음
- 추출한 아이콘 원시 데이터를 HxD로 열어 `dwBytesInRes`만큼 건너뛴 위치부터 `MZ`(`4D 5A`)나 다른 파일 시그니처가 보임
- 아이콘 파일 크기 대비 전체 `.rsrc` 섹션 크기가 유난히 큰데, 문자열 창에는 별다른 이상이 안 보이는 조합

## 가장 먼저 할 것
의심스러운 아이콘을 발견하면, 먼저 `RT_GROUP_ICON`을 열어 각 `GRPICONDIRENTRY.dwBytesInRes`와 `nID`를 표로 정리한다. 그 다음 같은 파일의 `RT_ICON` 아래 모든 리소스 ID와 각각의 실제 `Size`(`IMAGE_RESOURCE_DATA_ENTRY.Size`)를 나열해, 두 목록을 대조한다.

## 단계별 절차
**1) RT_GROUP_ICON 원시 데이터 추출**
Resource Hacker나 직접 파싱으로 `GRPICONDIR`와 `GRPICONDIRENTRY` 배열을 읽어 각 항목의 `nID`, `dwBytesInRes`, `bWidth`, `bHeight`를 기록한다.

**2) RT_ICON 전체 목록 확보**
같은 파일의 `.rsrc` 트리에서 `RT_ICON`(타입 3) 아래에 있는 모든 리소스 ID와 각각의 실제 `Size`를 나열한다.

**3) 두 목록 대조**
`RT_GROUP_ICON`에서 참조하는 `nID` 집합과 `RT_ICON`에 실제로 존재하는 ID 집합을 비교해 고아 ID가 있는지 확인한다. 참조되는 ID들에 대해서는 `dwBytesInRes`(선언값)와 실제 `Size`(실측값)가 일치하는지 확인한다.

**4) 의심 항목 원시 추출 및 오프셋 이후 확인**
크기가 안 맞는 항목을 원시 바이너리로 저장한 뒤, `dwBytesInRes` 바이트만큼 건너뛴 지점부터 HxD로 확인한다. 그 지점의 첫 바이트가 `MZ`, `PK`, 또는 높은 엔트로피의 데이터라면 숨겨진 페이로드일 가능성이 크다.

## 명령어/단축키
```text
Resource Hacker: Icon Group / Icon 트리 노드 → 우클릭 → Save Resource As Binary File
HxD: 추출 파일 열기 → 지정 오프셋으로 이동(Ctrl+G)하여 해당 지점부터 확인
PE-bear: Resources 탭 → RT_ICON / RT_GROUP_ICON 각각의 Size 컬럼 비교
```

## 출력 해석
- `dwBytesInRes`와 실제 `Size`가 정확히 일치하면 정상 아이콘 — 대부분의 컴파일러/링커가 생성한 아이콘은 이 값이 항상 일치한다
- 실제 `Size`가 `dwBytesInRes`보다 크게 크면(수십~수백 배) 여분 바이트에 다른 데이터가 붙어있을 가능성이 높으므로 해당 오프셋부터 원시 확인 필요
- 고아 `RT_ICON` ID를 발견했는데 그 데이터가 정상적인 BMP/PNG 이미지 헤더로 시작한다면, 단순히 링커가 이전 빌드에서 남긴 미사용 리소스일 수도 있으니 곧바로 악성으로 단정하지 말고 내용을 확인
- 여분 데이터가 `MZ`로 시작하면 완전한 PE 파일이 숨겨진 것이 거의 확실 — REV-0141의 절차대로 2단계 분석 진행

## 흔한 실수
- 아이콘이 화면에 정상적으로 렌더링된다는 것만으로 그 리소스에 다른 데이터가 없다고 안심하는 것 — 렌더러는 선언된 크기만큼만 읽고 그 이후는 무시하기 때문에 여분 데이터가 있어도 렌더링에는 아무 영향이 없다.
- `RT_GROUP_ICON`을 확인하지 않고 `RT_ICON` 리소스 크기만 보고 "아이콘치고 크네" 정도로만 판단하는 것 — 반드시 `dwBytesInRes`(선언값)와 실제 크기를 정량적으로 비교해야 한다.
- 커서(`RT_CURSOR`/`RT_GROUP_CURSOR`)도 동일한 구조(단, `GRPICONDIRENTRY` 대신 hotspot 필드가 있는 유사 구조)를 쓴다는 걸 모르고 아이콘만 확인하고 넘어가는 것.
- 고아 리소스를 발견했을 때 무조건 악성으로 단정하는 것 — 개발 과정에서 남은 미사용 리소스일 수도 있으므로 내용을 직접 확인한 뒤 판단해야 한다.

## 막혔을 때 다음 체크
- `.rsrc` 트리 전체 구조와 하이비트 규칙이 헷갈리면 → [.rsrc 섹션 트리 구조 자세히 읽는 법](./rev-0548-rsrc-tree-structure.md)
- 아이콘 외 다른 리소스 타입에 데이터를 숨기는 일반적인 기법과 탐지법이 궁금하면 → [리소스에 커스텀 데이터 숨기는 기법과 찾는 법](./rev-0552-custom-data-in-resources.md)
- `RT_RCDATA` 위장 및 리소스 전반의 숨겨진 페이로드 확인 절차는 → [Resource Section과 숨겨진 데이터 확인](./rev-0141-resource-section.md)

## 미니 예제
`toolbox.exe`의 `RT_GROUP_ICON`(ID 1)을 파싱했더니 `idCount=1`이고 `GRPICONDIRENTRY`가 `bWidth=32, bHeight=32, dwBytesInRes=1128, nID=101`이었다. `RT_ICON` 아래 ID `101`의 실제 `Size`는 `1128`로 정확히 일치해 정상이었다. 그런데 같은 파일의 `RT_ICON` 아래에 ID `102`가 하나 더 있었고, 어떤 `RT_GROUP_ICON`도 이 ID를 참조하지 않았다(고아 리소스). ID `102`의 데이터를 추출해 HxD로 확인하니 시작 바이트가 `4D 5A 90 00`(`MZ`)이었다 — 아이콘으로 위장된 자리가 아니라 아예 아이콘 세트에 포함되지도 않은 채로 숨겨진 완전한 PE 파일이 리소스 트리에 존재했던 것이다. 이는 자동 렌더링 경로를 거치지 않으므로 화면에는 전혀 티가 나지 않는, 매우 은밀한 은닉 방식이다.

## 관련 글
- REV-0548 — .rsrc 섹션 트리 구조 자세히 읽는 법
- REV-0552 — 리소스에 커스텀 데이터 숨기는 기법과 찾는 법
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 출처/검증
- `RT_ICON`/`RT_GROUP_ICON`과 `GRPICONDIR`/`GRPICONDIRENTRY` 구조: Microsoft Learn Win32 "Icons" 및 ".ico File Format" 관련 공식 문서 기준 (2026-09-08 검증).
- 아이콘/커서 리소스를 이용한 데이터 은닉 기법: 다수 악성코드 분석 레퍼런스에서 공통적으로 설명되는 일반 패턴(2026-09-08 기준 서술).
