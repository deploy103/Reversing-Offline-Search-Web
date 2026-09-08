---
id: REV-0550
title: "매니페스트(Manifest)에서 실행 요구사항 확인하기"
slug: "rev-0550-manifest-execution-requirements"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "Resource Hacker", "PE-bear"]
keywords: ["RT_MANIFEST", "requestedExecutionLevel", "asInvoker", "requireAdmin", "UAC", "trustInfo", "dpiAware", "mt.exe"]
aliases: ["애플리케이션 매니페스트", "UAC 권한 상승 요구 확인", "requireAdmin 확인 방법", "supportedOS 호환성 GUID"]
symptom_keywords: ["실행하면 UAC 창이 뜨는 이유를 모름", "관리자 권한이 필요한지 미리 알고 싶음", "매니페스트가 뭔지 모름", "requireAdmin과 asInvoker 차이를 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`RT_MANIFEST` 리소스는 이 실행 파일이 관리자 권한을 요구하는지(`requireAdmin`), 자동으로 권한을 상승시키려 하는지, 어떤 Windows 버전과 호환된다고 선언하는지를 담은 XML이며, 실행하기도 전에 이 XML만 읽어보면 "실행하면 UAC 창이 뜰지", "DPI 인식을 하는지" 같은 실행 전 행동을 정적으로 예측할 수 있어 동적 분석 전 위험도 파악에 유용하다.

## 언제 검색해야 하나
- 파일을 실행하면 UAC(사용자 계정 컨트롤) 상승 창이 뜨는데, 이걸 실행 전에 정적으로 미리 알고 싶을 때
- 리소스 트리에서 `RT_MANIFEST`를 발견했는데 이게 무슨 내용을 담고 있는지 모를 때
- 샌드박스나 자동화 분석에서 관리자 권한 없이 실행되면 악성코드가 정상 동작하지 않는 이유를 확인하고 싶을 때
- 특정 프로그램이 comctl32 v6(테마 적용 UI 컨트롤) 같은 특정 side-by-side 어셈블리에 의존하는지 확인하고 싶을 때
- `mt.exe`로 매니페스트를 직접 다뤄야 할 때

## 핵심 개념

### 매니페스트가 저장되는 위치
매니페스트는 `.rsrc` 트리에서 `Type=RT_MANIFEST`(24) 아래에 저장되는 순수 텍스트(UTF-8 또는 UTF-16) XML이다. `Name`(ID)은 보통 다음 상수 중 하나를 쓴다.
```text
CREATEPROCESS_MANIFEST_RESOURCE_ID           1   // 일반 EXE의 기본 매니페스트
ISOLATIONAWARE_MANIFEST_RESOURCE_ID           2   // 격리 인식(DLL 등)
ISOLATIONAWARE_NOSTATICIMPORT_MANIFEST_RESOURCE_ID  3
```
대부분의 일반 EXE는 ID `1`에 매니페스트가 내장(embedded)되어 있으며, 드물게 실행 파일과 같은 폴더에 `프로그램이름.exe.manifest`라는 외부 파일로 존재하기도 한다(임베디드가 있으면 외부 파일보다 우선한다).

### requestedExecutionLevel — 권한 상승 요구
가장 중요하게 봐야 할 부분은 `trustInfo/security/requestedPrivileges/requestedExecutionLevel`이다.
```xml
<trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
  <security>
    <requestedPrivileges>
      <requestedExecutionLevel level="asInvoker" uiAccess="false" />
    </requestedPrivileges>
  </security>
</trustInfo>
```
`level` 속성 값에 따라 실행 시 동작이 완전히 달라진다.
```text
asInvoker           부모 프로세스(보통 탐색기)와 동일한 권한으로 실행, UAC 프롬프트 없음(기본값)
highestAvailable     현재 사용자가 가진 최고 권한으로 실행 시도, 관리자 그룹 소속이면 UAC 프롬프트 뜸
requireAdmin          반드시 관리자 권한 필요, 무조건 UAC 상승 프롬프트를 띄우고 사용자가 승인해야 실행됨
```
`requireAdmin`이 있는 파일은 더블클릭만으로 UAC 창이 뜨며, 사용자가 거부하면 프로세스 자체가 시작조차 되지 않는다. 반대로 매니페스트가 아예 없는 구형 프로그램은 Windows가 파일명이나 설치 관련 API 호출 패턴을 보고 관리자 권한이 필요한지 추정하는 **UAC 가상화(설치 관리자 감지 휴리스틱)**를 적용하기도 하는데, 이는 매니페스트가 명시적으로 있는 경우보다 훨씬 불확실하다. `uiAccess="true"`는 접근성 애플리케이션처럼 다른 창을 넘어 UI 자동화를 할 수 있는 특수 권한을 요구한다는 뜻으로, 서명된 실행 파일이 특정 안전한 디렉터리에 있을 때만 유효하게 동작하며 매우 드물게 쓰인다.

### 파일/레지스트리 가상화와의 관계
매니페스트가 아예 없는(따라서 UAC 관점에서 "레거시 애플리케이션"으로 취급되는) 32비트 프로그램이 `asInvoker` 권한으로 실행되면서 `C:\Program Files` 같은 보호된 경로나 `HKEY_LOCAL_MACHINE` 레지스트리에 쓰기를 시도하면, Windows는 오류를 내는 대신 그 쓰기 작업을 사용자별 가상 저장소(`%LOCALAPPDATA%\VirtualStore\...` 및 레지스트리의 유사한 가상화 영역)로 조용히 리다이렉션하는 **파일/레지스트리 가상화**를 적용한다. 이는 명시적으로 `requestedExecutionLevel`을 선언한 매니페스트가 있는 애플리케이션에는 적용되지 않는다(매니페스트가 있다는 것 자체가 "이 앱은 UAC를 인지하고 만들어졌다"는 뜻이기 때문). 그래서 분석 중인 프로그램이 실제로 쓴 파일이 안 보인다면, 매니페스트 유무를 먼저 확인하고 `VirtualStore` 경로도 함께 뒤져봐야 한다.

### DPI 인식과 호환성 선언
매니페스트에는 실행 요구사항 외에 화면/호환성 관련 선언도 흔히 들어있다.
```xml
<application xmlns="urn:schemas-microsoft-com:asm.v3">
  <windowsSettings>
    <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true</dpiAware>
  </windowsSettings>
</application>
```
`<supportedOS Id="{GUID}"/>` 요소는 이 프로그램이 어떤 Windows 버전에서 호환성 모드 없이 정상 동작한다고 선언하는지를 GUID로 나열한다(Vista/7/8/8.1/10 각각 고유 GUID). 이 GUID 목록으로 최소한 어떤 시대의 프로그램을 대상으로 빌드됐는지 짐작할 수 있다. `supportedOS` 목록에 최신 버전 GUID가 빠져있으면, `GetVersionEx` 같은 구버전 API가 실제 OS 버전 대신 호환성 셰임(compatibility shim)이 적용된 값을 돌려줄 수 있다는 점도 함께 기억해두면 버전 분기 로직을 분석할 때 도움이 된다.

### 의존 어셈블리(dependency)
```xml
<dependency>
  <dependentAssembly>
    <assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls"
                       version="6.0.0.0" processorArchitecture="*"
                       publicKeyToken="6595b64144ccf1df" language="*" />
  </dependentAssembly>
</dependency>
```
이런 블록은 이 프로그램이 특정 side-by-side(SxS) 어셈블리(가장 흔한 예가 테마 적용된 v6 공용 컨트롤)에 의존한다는 뜻이며, 해당 어셈블리가 시스템에 없으면 실행 시 컨트롤이 구식 스타일로 표시되거나 특정 API가 실패할 수 있다. 이런 `dependency` 선언이 전혀 없는 프로그램은 대체로 기본 GDI 스타일의 밋밋한 UI를 쓰거나, 아예 콘솔/커맨드라인 도구이거나, UI 프레임워크를 정적으로 링크한 경우일 가능성이 높다는 점도 참고할 만하다.

## 화면/코드에서 보이는 징후
- 파일을 더블클릭했을 때 실행 전에 UAC 방패 아이콘이 있는 상승 프롬프트가 뜨면 `requireAdmin`(또는 `highestAvailable`+관리자 계정) 매니페스트일 가능성이 매우 높음
- 탐색기에서 파일 아이콘 우하단에 UAC 방패 오버레이가 표시되면(Windows가 아이콘에 미리 표시) 매니페스트를 읽어 관리자 권한이 필요하다고 판단했다는 뜻
- Resource Hacker로 `Manifest` 항목을 열면 XML 텍스트가 그대로 보임(바이너리 파싱 불필요, 사람이 바로 읽을 수 있음)
- `.NET` 기반 실행 파일도 네이티브 PE와 동일하게 `RT_MANIFEST`를 가질 수 있음(닷넷 런타임 자체 요구사항과는 별개)

## 가장 먼저 할 것
의심스러운 실행 파일을 분석 전 트리아지할 때, Resource Hacker나 PE-bear로 `RT_MANIFEST`를 열어 `requestedExecutionLevel`부터 확인한다. `requireAdmin`이면 샌드박스/VM에서 관리자 권한으로 실행해야 정상 동작을 관찰할 수 있다는 뜻이므로 분석 환경 준비 단계에서 미리 반영한다.

## 단계별 절차
**1) RT_MANIFEST 리소스 찾기**
`.rsrc` 트리(REV-0548 참고)에서 `Type=24`를 찾는다. 없다면 이 파일은 매니페스트가 없는 구형 스타일이거나, 외부 `.manifest` 파일에 의존할 수 있으니 같은 폴더를 확인한다.

**2) XML 텍스트 추출**
Resource Hacker로 열면 바로 텍스트로 보인다. 직접 추출하려면 원시 바이트를 그대로 `.xml`로 저장해서 텍스트 에디터로 열면 된다(별도 파싱 라이브러리 불필요).

**3) requestedExecutionLevel 확인**
`level` 속성이 `asInvoker`/`highestAvailable`/`requireAdmin` 중 무엇인지 확인해 UAC 동작을 예측한다.

**4) 나머지 선언 확인**
`dpiAware`, `supportedOS`, `dependency` 블록을 훑어 이 프로그램의 빌드 시대와 UI 프레임워크 의존성을 파악한다.

## 명령어/단축키
```text
Resource Hacker: 좌측 트리 → Manifest → 더블클릭(XML 텍스트 그대로 표시)
mt.exe (Windows SDK): mt.exe -inputresource:파일.exe;#1 -out:extracted.manifest
PE-bear: Resources 탭 → RT_MANIFEST 노드 클릭 → Hex/텍스트 뷰
```

## 출력 해석
- `level="requireAdmin"`이면 무조건 UAC 상승이 필요 — 자동화 샌드박스에서 이 프로세스가 "실행됐지만 아무 동작도 안 한 것처럼" 보인다면 UAC 거부/미승인 때문일 수 있음
- `level="asInvoker"`이면서도 코드 내부에서 관리자 권한이 필요한 API(레지스트리 `HKLM` 쓰기, 서비스 설치 등)를 호출한다면, 실행 시 해당 API가 조용히 실패하거나 접근 거부 에러가 날 가능성이 있으므로 코드와 매니페스트 선언의 불일치를 눈여겨봐야 함
- 매니페스트 자체가 없으면 Windows의 설치 관리자 감지 휴리스틱(파일명에 "setup", "install" 등이 포함되거나 특정 버전 정보 API를 호출하는 패턴)이 적용될 수 있어, 실행 전 UAC 여부를 100% 정적으로 예측하기 어려움
- `dependency` 블록의 어셈블리가 시스템에 없으면 실행 시 `The application has failed to start because its side-by-side configuration is incorrect` 류 오류가 날 수 있음

## 흔한 실수
- `asInvoker`가 "권한이 낮다"는 뜻으로 오해하는 것 — 이는 그냥 "부모 프로세스와 동일한 권한"이라는 뜻이며, 만약 이미 관리자 권한 셸에서 실행됐다면 `asInvoker`라도 관리자 권한으로 동작한다.
- 매니페스트가 없다고 해서 "이 프로그램은 절대 관리자 권한을 요구하지 않는다"고 단정하는 것 — Windows의 휴리스틱 UAC 가상화 때문에 예측이 어긋날 수 있다.
- `RT_MANIFEST` XML을 코드로 잘못 실행되는 스크립트로 착각하는 것 — 이건 단지 선언적 메타데이터이며 그 자체로는 아무 코드도 실행하지 않는다.
- 매니페스트에 `requireAdmin`이 있다고 해서 이 파일이 곧 악성이라고 단정하는 것 — 정상적인 설치 프로그램, 시스템 관리 도구 등도 흔히 `requireAdmin`을 쓴다. 다른 단서와 함께 종합 판단해야 한다.

## 막혔을 때 다음 체크
- `.rsrc` 트리에서 `RT_MANIFEST`를 정확히 찾는 절차가 헷갈리면 → [.rsrc 섹션 트리 구조 자세히 읽는 법](./rev-0548-rsrc-tree-structure.md)
- 매니페스트와 함께 버전 정보로 사칭 여부를 교차 검증하고 싶으면 → [버전 정보(Version Info) 리소스에서 단서 찾기](./rev-0549-version-info-resource.md)
- 리소스 전반의 숨겨진 데이터 확인 절차가 궁금하면 → [Resource Section과 숨겨진 데이터 확인](./rev-0141-resource-section.md)

## 미니 예제
`installer_helper.exe`의 `RT_MANIFEST`를 Resource Hacker로 열었더니 다음과 같은 내용이 있었다.
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdmin" uiAccess="false" />
      </requestedPrivileges>
    </security>
  </trustInfo>
</assembly>
```
`requireAdmin`이 명시되어 있으므로 이 파일은 더블클릭 즉시 UAC 상승 프롬프트가 뜨고, 사용자가 승인해야만 프로세스가 시작된다. 만약 자동화 샌드박스에서 이 파일을 관리자 권한 없이 실행하려 했다면, 프로세스 생성 자체가 실패하거나(사용자 승인 대기 중 타임아웃) 아무 동작도 관찰되지 않았을 텐데, 매니페스트를 먼저 확인했다면 이 문제를 미리 예상하고 관리자 권한 환경을 준비할 수 있었을 것이다.

## 관련 글
- REV-0548 — .rsrc 섹션 트리 구조 자세히 읽는 법
- REV-0549 — 버전 정보(Version Info) 리소스에서 단서 찾기
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 출처/검증
- `RT_MANIFEST` 리소스 ID 상수(`CREATEPROCESS_MANIFEST_RESOURCE_ID` 등)와 매니페스트 XML 스키마: Microsoft Learn "Application Manifests" 공식 문서 기준 (2026-09-08 검증).
- `requestedExecutionLevel`의 `asInvoker`/`highestAvailable`/`requireAdmin` 동작: Microsoft Learn UAC 관련 공식 문서 기준.
- UAC 설치 관리자 감지 휴리스틱: Microsoft Learn UAC 공식 문서의 관련 설명 기준.
