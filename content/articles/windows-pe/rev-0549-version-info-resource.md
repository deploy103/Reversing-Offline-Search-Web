---
id: REV-0549
title: "버전 정보(Version Info) 리소스에서 단서 찾기"
slug: "rev-0549-version-info-resource"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "Resource Hacker", "PE-bear"]
keywords: ["RT_VERSION", "VS_VERSIONINFO", "VS_FIXEDFILEINFO", "StringFileInfo", "OriginalFilename", "GetFileVersionInfo", "VerQueryValue"]
aliases: ["버전 정보 리소스", "파일 속성 상세 정보", "OriginalFilename 위조 탐지", "VS_VERSIONINFO 구조"]
symptom_keywords: ["파일 속성 창의 정보가 이상함", "원래 파일 이름과 실제 파일 이름이 다름", "회사명 제품명이 유명 소프트웨어를 사칭함", "버전 정보 리소스 구조를 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`RT_VERSION` 리소스는 탐색기의 "속성 → 자세히" 탭에 표시되는 회사명·제품명·파일 버전·원본 파일 이름 등을 담은 `VS_VERSIONINFO` 구조체이며, 정상 프로그램에서는 신뢰 판단에 도움이 되지만 악성코드는 이 값들을 정상 소프트웨어처럼 위장하거나 아예 비워두는 경우가 많아서, `OriginalFilename`이 실제 파일명과 다르거나 유명 회사명을 사칭하는지를 확인하는 것만으로도 강력한 1차 트리아지 단서가 된다.

## 언제 검색해야 하나
- 의심스러운 파일의 속성 창에서 회사명/제품명이 표시되는데 이게 진짜인지 위조인지 판단하고 싶을 때
- 파일 이름은 `svchost.exe`인데 실제로 시스템 `svchost.exe`가 맞는지 `OriginalFilename` 필드로 교차 검증하고 싶을 때
- Resource Hacker로 `Version Info`를 열었는데 필드가 비어있거나 파싱이 깨져 보일 때
- `VS_VERSIONINFO` 구조체를 직접 파싱하는 스크립트를 짜야 할 때
- `sigcheck`나 다른 도구의 버전 정보 출력이 파일 자체의 리소스와 일치하는지 검증하고 싶을 때

## 핵심 개념

### VS_VERSIONINFO의 위치와 구조
버전 정보는 `.rsrc` 트리에서 `Type=RT_VERSION`(16) 아래, 보통 `Name=1`, 그 아래 언어별 리프에 저장된 원시 바이트다. 이 원시 바이트는 `VS_VERSIONINFO`라는 가변 길이 구조로 되어 있다.
```c
// 개념적 구조(실제로는 WORD 길이 접두 + 가변 길이 문자열/데이터가 반복됨)
struct VS_VERSIONINFO {
    WORD  wLength;          // 전체 구조 크기
    WORD  wValueLength;     // 뒤따르는 VS_FIXEDFILEINFO 크기(보통 sizeof(VS_FIXEDFILEINFO)=52)
    WORD  wType;            // 1=텍스트, 0=바이너리
    WCHAR szKey[];          // L"VS_VERSION_INFO" (고정 문자열)
    // 4바이트 정렬 패딩
    VS_FIXEDFILEINFO Value; // 고정 크기 필드(아래)
    // 4바이트 정렬 패딩
    // 이어서 StringFileInfo, VarFileInfo 자식 블록들(가변 개수)
};
```

### VS_FIXEDFILEINFO — 숫자로 된 버전 정보
```c
typedef struct tagVS_FIXEDFILEINFO {
    DWORD dwSignature;        // 항상 0xFEEF04BD
    DWORD dwStrucVersion;
    DWORD dwFileVersionMS;    // 상위 16비트=Major, 하위 16비트=Minor
    DWORD dwFileVersionLS;    // 상위 16비트=Build, 하위 16비트=Revision
    DWORD dwProductVersionMS;
    DWORD dwProductVersionLS;
    DWORD dwFileFlagsMask;
    DWORD dwFileFlags;        // VS_FF_DEBUG, VS_FF_PRERELEASE 등
    DWORD dwFileOS;           // VOS_NT_WINDOWS32 등
    DWORD dwFileType;         // VFT_APP, VFT_DLL, VFT_DRV 등
    DWORD dwFileSubtype;
    DWORD dwFileDateMS;
    DWORD dwFileDateLS;
} VS_FIXEDFILEINFO;  // 52바이트
```
`dwSignature`가 `0xFEEF04BD`가 아니면 이 데이터가 손상됐거나 애초에 버전 정보 형식을 흉내만 낸 위장 데이터일 가능성이 크다. `dwFileVersionMS`/`LS`를 조합하면 탐색기 속성 창에 보이는 "1.2.3.4" 형식의 파일 버전 숫자가 나온다.

### StringFileInfo — 사람이 읽는 문자열 정보
`VS_FIXEDFILEINFO` 뒤에는 `StringFileInfo`와 `VarFileInfo`라는 이름의 자식 블록들이 이어진다. `StringFileInfo` 안에는 언어/코드페이지별 `StringTable`이 있고, 그 안에 키-값 쌍이 들어있다. 자주 보는 표준 키:
```text
CompanyName        FileDescription    FileVersion
InternalName        LegalCopyright     OriginalFilename
ProductName          ProductVersion    Comments
```
이 중 **`OriginalFilename`**이 리버싱에서 특히 중요하다. 이 필드는 "이 파일이 빌드될 당시 원래 이름이 무엇이었는지"를 컴파일 시점에 개발자가 리소스(.rc) 파일에 적어 넣은 값이며, 실행 파일이 이후에 다른 이름으로 복사/배포되어도 이 값은 바뀌지 않는다. 그래서 실제 파일명과 `OriginalFilename`이 크게 다르면(예: 파일명은 `update.exe`인데 `OriginalFilename`은 `payload.exe`나 전혀 다른 임의 문자열) 강한 의심 신호가 된다. 반대로 진짜 시스템 파일을 사칭하려는 악성코드는 `CompanyName`에 `"Microsoft Corporation"`, `OriginalFilename`에 진짜와 동일한 값을 넣어 이 검사를 통과하려 시도하기도 하므로, 이 필드는 **강력하지만 절대적이지 않은** 단서로 취급해야 한다.

### VarFileInfo와 언어/코드페이지 매핑
`StringFileInfo`와 나란히 존재하는 `VarFileInfo` 블록에는 `Translation`이라는 이름의 배열이 들어있으며, 각 항목은 `(언어ID, 코드페이지)` 쌍의 `DWORD`다. 예를 들어 `(0x0409, 0x04B0)`은 "영어(미국), 유니코드"를 뜻하고, 이를 8자리 16진수로 이어붙인 `"040904B0"`이 바로 `StringFileInfo` 아래 `StringTable`의 키로 쓰인다. 즉 `VarFileInfo`가 "이 파일에 어떤 언어/코드페이지 조합의 문자열 테이블이 존재하는지"를 알려주는 색인 역할을 하고, `StringFileInfo`가 실제 값을 담는 구조다. 다국어 지원 프로그램은 `StringTable`이 여러 개 존재할 수 있으므로, `OriginalFilename` 같은 필드를 확인할 때 특정 언어 블록 하나만 보고 판단하지 말고 존재하는 모든 `StringTable`을 함께 확인하는 것이 안전하다.

### API 레벨에서 버전 정보 읽기
코드에서 직접 이 리소스를 읽고 싶다면 `GetFileVersionInfoSizeW`로 필요한 버퍼 크기를 얻은 뒤 `GetFileVersionInfoW`로 원시 데이터를 통째로 로드하고, `VerQueryValueW`에 `L"\\StringFileInfo\\040904B0\\OriginalFilename"` 같은 경로 문자열을 넘겨 개별 값을 꺼낸다. 리버싱 중에는 반대로, 임포트 목록에서 `GetFileVersionInfoW`/`VerQueryValueW`를 호출하는 코드를 발견하면 "이 프로그램이 자기 자신이나 다른 파일의 버전 정보를 런타임에 검사한다"는 뜻이며, 이는 종종 라이선스 체크, 자가 무결성 검사, 혹은 특정 대상 프로세스를 찾는 로직(버전 문자열로 타깃 식별)과 연결되므로 xref를 따라가 볼 가치가 있다.

## 화면/코드에서 보이는 징후
- 탐색기에서 파일 우클릭 → 속성 → 자세히 탭에 회사명/제품명/파일 버전/저작권 등이 표시됨(이 값들이 바로 `.rsrc`의 `RT_VERSION`에서 온 것)
- Resource Hacker로 `Version Info`를 열면 좌측에 파싱된 트리, 우측에 리소스 스크립트(.rc) 형태의 텍스트로 각 키-값 쌍이 그대로 보임
- `dwFileType`이 `VFT_APP`(`0x1`)인데 실제로는 DLL 확장자인 경우, 또는 그 반대인 경우처럼 선언된 타입과 실제 파일 형식이 불일치
- `CompanyName`이 `"Microsoft Corporation"`인데 디지털 서명(Authenticode)이 없거나 서명 검증이 실패하면 강한 사칭 의심 신호

## 가장 먼저 할 것
의심 파일을 만나면 먼저 탐색기 속성 창이나 Resource Hacker로 버전 정보를 열어 `OriginalFilename`과 실제 파일명을 비교하고, `CompanyName`/`ProductName`이 유명 소프트웨어를 사칭하는지 육안으로 확인한다. 그 다음 해당 파일에 유효한 디지털 서명(Authenticode)이 있는지 함께 확인해, "이름만 사칭하고 서명은 없는" 전형적인 패턴인지 판단한다.

## 단계별 절차
**1) 리소스 트리에서 RT_VERSION 찾기**
`.rsrc` 트리(REV-0548 참고)에서 `Type=16`(`RT_VERSION`) 아래로 내려가 원시 바이트를 확보한다.

**2) VS_FIXEDFILEINFO 파싱**
`wLength`, `wValueLength`, `wType`, `L"VS_VERSION_INFO"` 문자열을 지나 4바이트 정렬된 위치에서 `VS_FIXEDFILEINFO`를 읽는다. `dwSignature==0xFEEF04BD`를 먼저 검증한다.

**3) StringFileInfo 블록 탐색**
`VS_FIXEDFILEINFO` 뒤, 다시 4바이트 정렬 후 이어지는 자식 블록들의 `szKey`가 `L"StringFileInfo"`인 것을 찾는다. 그 안의 `StringTable`(키가 "언어ID+코드페이지" 8자리 16진수 문자열, 예: `"040904B0"`)로 내려가면 실제 `CompanyName`, `OriginalFilename` 등 키-값 쌍이 나온다.

**4) 실제 파일명과 대조**
`OriginalFilename` 값을 분석 대상 파일의 실제 이름과 비교한다. 다르면 왜 다른지(정상적인 리네이밍인지, 위장인지) 다른 단서(임포트, 문자열, 서명)와 함께 종합 판단한다.

## 명령어/단축키
```text
탐색기: 파일 우클릭 → 속성 → 자세히 탭
Resource Hacker: 좌측 트리 → Version Info → 더블클릭(파싱된 스크립트 뷰)
Sysinternals sigcheck: sigcheck -m <파일>  (버전 정보 + 서명 정보 함께 출력)
PowerShell: (Get-Item <파일>).VersionInfo | Format-List *
```

## 출력 해석
- `dwSignature != 0xFEEF04BD`면 이 리소스는 형식이 손상됐거나 버전 정보를 흉내 낸 가짜 데이터일 가능성이 큼 — 도구가 "버전 정보 없음"으로 표시하거나 파싱 오류를 낼 것
- `OriginalFilename`이 비어있으면(빈 문자열) 단서로 쓸 수 없을 뿐, 그 자체가 악성이라는 뜻은 아니다(일부 정상 빌드도 이 필드를 채우지 않음)
- `CompanyName`/`ProductName`이 유명 회사를 사칭하면서 `LegalCopyright`가 어색한 문법이거나 연도가 비정상적이면(예: 미래 연도) 위조 가능성이 높음
- PowerShell `VersionInfo`가 파일 자체를 열어보지 않고도 요약값을 주지만, 손상되거나 비표준 구조인 리소스는 일부 필드가 빈 값으로 나올 수 있으므로 Resource Hacker로 직접 원시 구조를 재확인하는 것이 안전

## 흔한 실수
- `CompanyName`이 유명 회사 이름이라는 것만으로 파일을 신뢰하는 것 — 이 문자열은 리소스 컴파일 시 개발자가 임의로 넣는 텍스트일 뿐이며 아무 검증 장치가 없다. 반드시 Authenticode 서명 같은 별도의 신뢰 메커니즘과 함께 봐야 한다.
- `OriginalFilename`이 실제 파일명과 같다는 이유만으로 안전하다고 판단하는 것 — 공격자가 원본 이름을 그대로 복사한 뒤 코드만 바꿔치기했을 수도 있다.
- `dwFileVersionMS`/`LS`의 상위/하위 16비트 배치를 반대로 해석해서 버전 번호를 잘못 읽는 것.
- `StringTable`의 언어/코드페이지 키를 무시하고 항상 첫 번째 블록만 읽어서, 다국어 파일에서 다른 언어의 값을 놓치는 것.
- 버전 정보가 아예 없는 파일을 "무조건 의심스럽다"고 단정하는 것 — 많은 정상적인 오픈소스/개인 프로젝트 빌드도 버전 정보를 채우지 않는다. 다른 단서와 함께 종합적으로 판단해야 한다.

## 막혔을 때 다음 체크
- `.rsrc` 트리 구조 자체(3단계, 하이비트 규칙)가 헷갈리면 → [.rsrc 섹션 트리 구조 자세히 읽는 법](./rev-0548-rsrc-tree-structure.md)
- 매니페스트 리소스와 함께 실행 요구사항까지 확인하고 싶으면 → [매니페스트(Manifest)에서 실행 요구사항 확인하기](./rev-0550-manifest-execution-requirements.md)
- 리소스 전반에서 숨겨진 페이로드를 찾는 절차가 궁금하면 → [Resource Section과 숨겨진 데이터 확인](./rev-0141-resource-section.md)

## 미니 예제
`fake_update.exe`라는 파일의 버전 정보를 Resource Hacker로 열었더니 다음과 같았다.
```text
CompanyName       : Microsoft Corporation
ProductName       : Microsoft Windows Operating System
FileDescription   : Windows Update Service
OriginalFilename  : svhost.exe
InternalName      : svhost
FileVersion       : 10.0.19041.1
```
`OriginalFilename`이 `svhost.exe`로, 진짜 시스템 파일명인 `svchost.exe`와 철자가 미묘하게 다르다(`c` 누락, 타이포스쿼팅). 진짜 `Microsoft Corporation` 서명 파일이라면 Authenticode 서명이 정상 검증되어야 하는데, 이 파일에는 서명이 아예 없거나 검증에 실패한다면 사칭이 거의 확실하다. 이처럼 `OriginalFilename`의 미묘한 오탈자는 사칭형 악성코드를 가려내는 대표적인 패턴이다.

## 관련 글
- REV-0548 — .rsrc 섹션 트리 구조 자세히 읽는 법
- REV-0550 — 매니페스트(Manifest)에서 실행 요구사항 확인하기
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 출처/검증
- `VS_VERSIONINFO`, `VS_FIXEDFILEINFO`, `StringFileInfo` 구조체와 표준 키 목록: Microsoft Learn Win32 "Version Information" 공식 문서 기준 (2026-09-08 검증).
- `GetFileVersionInfo`/`VerQueryValue` API 동작: Microsoft Learn Win32 API 문서 기준.
- `OriginalFilename` 불일치를 통한 사칭 탐지 관행: 다수 악성코드 분석 레퍼런스에서 공통적으로 언급되는 트리아지 기법(2026-09-08 기준 서술).
