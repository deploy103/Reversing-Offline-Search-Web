---
id: REV-0619
title: "매니페스트 요구 권한 때문에 프로그램이 안 켜질 때"
slug: "rev-0619-manifest-privilege-wont-launch"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [Resource Hacker, PE-bear]
keywords: ["Application Manifest", "requestedExecutionLevel", "requireAdministrator", "UAC", "RT_MANIFEST", "관리자 권한"]
aliases: ["exe 실행이 안 됨", "관리자 권한 요구", "UAC 프롬프트 안 뜸", "매니페스트 권한 문제"]
symptom_keywords: ["더블클릭해도 프로그램이 안 켜진다", "관리자 권한이 필요하다는데 없다", "ERROR_ELEVATION_REQUIRED", "실행이 조용히 실패한다", "UAC 없이 관리자 권한을 요구한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
PE 파일 내부에 임베드된 **애플리케이션 매니페스트**(`RT_MANIFEST` 리소스)의 `requestedExecutionLevel`이 `requireAdministrator`로 설정되어 있으면, Windows는 관리자 권한 없이 그 프로그램을 실행시켜주지 않는다. 대회용 PC처럼 관리자 권한이 제한된 환경에서는 이것 때문에 더블클릭해도 조용히 실패하거나 오류만 뜨고 프로그램이 안 켜지는 것처럼 보인다. 먼저 매니페스트를 확인해 원인을 확정하고, "관리자 권한으로 실행"을 시도하거나 매니페스트 자체를 패치해서 우회한다.

## 언제 검색해야 하나
- 파일을 더블클릭했는데 아무 반응이 없거나, 잠깐 깜빡이고 사라질 때
- "이 앱이 디바이스에 변경 내용을 적용하도록 허용하시겠습니까?" UAC 프롬프트가 계속 뜨는데 계정에 관리자 권한이 없어 승인할 수 없을 때
- `CreateProcess`가 `ERROR_ELEVATION_REQUIRED`(오류 코드 740)를 반환하는 것을 API 후킹/로그에서 확인했을 때
- 디버거로 붙여서 실행했더니 프로세스가 시작되자마자 종료되는데 이유를 모를 때(일반 실행은 안 되지만 디버거로는 다른 권한 컨텍스트에서 뜨는 경우도 있어 증상이 헷갈릴 수 있다)

## 핵심 개념
PE 실행 파일은 `.rsrc` 섹션에 다양한 리소스를 담을 수 있는데, 그중 `RT_MANIFEST`(리소스 타입 24) 리소스는 XML 형식의 "애플리케이션 매니페스트"를 담는다. 이 XML은 Windows 로더/UAC(사용자 계정 컨트롤)에게 이 프로그램을 어떤 권한으로, 어떤 호환성 설정으로 실행할지 알려준다. 핵심 필드는 `<requestedExecutionLevel>`이며 값은 세 가지 중 하나다.

- `asInvoker`: 프로그램을 실행시킨 프로세스(대개 탐색기)와 같은 권한으로 실행. 기본값이며 대부분의 프로그램이 이것을 쓴다.
- `highestAvailable`: 현재 로그인한 사용자가 가진 권한 중 가장 높은 것으로 실행(관리자 그룹 소속이면 UAC 프롬프트가 뜬다).
- `requireAdministrator`: 무조건 관리자 권한으로만 실행 가능. UAC 프롬프트가 뜨고, 사용자가 관리자 계정이 아니거나 프롬프트를 거부하면 실행 자체가 취소된다.

CTF/워게임에서 배포되는 바이너리가 원래 서버/관리 도구였거나, 빌드 시 Visual Studio가 기본 템플릿 매니페스트를 그대로 포함시킨 경우 `requireAdministrator`가 딸려오는 일이 종종 있다. 참가자 PC 계정이 표준 사용자이거나, 조직 정책으로 UAC 프롬프트가 비활성화되어 있으면 이 요구 권한 때문에 실행 자체가 막힌다.

## 화면/코드에서 보이는 징후
- 탐색기에서 더블클릭 시 아이콘이 잠깐 반짝이고 아무 창도 뜨지 않음
- 아이콘에 방패 모양(UAC 방패 아이콘)이 표시되어 있음 — 이는 Windows가 매니페스트를 미리 읽고 관리자 권한이 필요하다고 판단했을 때 탐색기가 보여주는 시각적 힌트다
- `cmd.exe`에서 직접 실행하면 "이 작업을 수행하려면 관리자 권한이 필요합니다" 또는 "액세스가 거부되었습니다" 메시지가 뜸
- `CreateProcess` 계열 API를 사용하는 실행기(런처, 배치 스크립트)에서 반환값 실패와 `GetLastError() == 740`

## 가장 먼저 할 것
"관리자 권한으로 실행"(우클릭 → 관리자 권한으로 실행)을 먼저 시도해본다. 이것만으로 정상 실행되면 매니페스트 문제로 확정된다. 만약 관리자 권한 자체가 계정에 없다면(대회 PC 등), 아래 절차로 매니페스트를 직접 확인하고 필요하면 패치한다.

## 단계별 절차
1. **매니페스트 존재 확인**: PE-bear나 Resource Hacker로 파일을 열어 리소스 트리에서 `Manifest`(또는 `RT_MANIFEST`, 리소스 ID 24) 항목이 있는지 확인한다. 있다면 대개 리소스 ID `1`(EXE, `CREATEPROCESS_MANIFEST_RESOURCE_ID`) 또는 `2`(DLL, `ISOLATIONAWARE_MANIFEST_RESOURCE_ID`)로 들어있다.
2. **XML 내용 추출**: Resource Hacker에서 해당 리소스를 더블클릭하면 XML 텍스트가 그대로 보인다. 명령줄로는 Windows SDK의 `mt.exe`를 사용할 수도 있다.
   ```text
   mt.exe -inputresource:target.exe;#1 -out:extracted_manifest.xml
   ```
3. **`requestedExecutionLevel` 값 확인**: XML 안에서 `<requestedExecutionLevel level="requireAdministrator" uiAccess="false" />` 같은 줄을 찾는다. 이 값이 원인이다.
4. **우회 방법 선택**:
   - 관리자 계정을 쓸 수 있다면 그냥 "관리자 권한으로 실행"한다. 분석/디버깅 목적이면 이 방법이 가장 간단하고 파일을 변형하지 않는다.
   - 관리자 권한이 아예 없는 환경이라면, 매니페스트 리소스를 `asInvoker`로 수정한 사본을 만들어 실행한다. Resource Hacker에서 XML을 직접 편집 후 "Compile Script" → 저장하면 리소스가 교체된 새 실행 파일이 만들어진다. `mt.exe`로도 재삽입 가능하다.
   ```text
   mt.exe -manifest patched_manifest.xml -outputresource:target.exe;#1
   ```
5. **서명 파일 주의**: 원본 파일이 디지털 서명(Authenticode)되어 있었다면, 리소스를 수정하는 순간 서명이 깨진다(REV-0614 서명 검증 관련 참고). CTF 바이너리는 대부분 서명이 없으므로 큰 문제는 아니지만, 서명 검증 로직이 자체적으로 있는 바이너리라면 이 패치가 다른 오류를 유발할 수 있다.
6. **디버거로 직접 실행하는 경우**: IDA나 x64dbg로 "파일 열기(Open)"해서 실행할 때는 디버거 프로세스 자체의 권한 컨텍스트를 그대로 물려받는 경우가 많아, 관리자 권한으로 IDA/x64dbg를 실행하면 대상 프로그램도 관리자 권한으로 뜨는 경우가 있다. 다만 매니페스트가 명시적으로 `requireAdministrator`라면 디버거를 거치더라도 여전히 UAC 승인이 필요할 수 있다.

## 명령어/단축키
- Resource Hacker: File → Open, 좌측 트리에서 `Manifest` 더블클릭, "Compile Script" 후 저장
- `mt.exe -inputresource:파일;#1 -out:파일.xml`(매니페스트 추출)
- `mt.exe -manifest 파일.xml -outputresource:파일;#1`(매니페스트 삽입/교체)
- 우클릭 → "관리자 권한으로 실행"(빠른 확인용)

## 출력 해석
- `<requestedExecutionLevel level="asInvoker">`로 바뀐 뒤 정상 실행되면 원인이 매니페스트였음이 확정된다.
- `mt.exe` 실행 시 "성공적으로 완료했습니다" 메시지가 나오면 리소스 교체가 완료된 것이다. 오류가 나면 리소스 ID(`#1` vs `#2`)를 EXE/DLL에 맞게 바꿔본다.
- `GetLastError()`가 740(`ERROR_ELEVATION_REQUIRED`)이면 명확히 이 문제이고, 다른 코드(예: 5, `ERROR_ACCESS_DENIED`)라면 매니페스트가 아니라 파일 시스템 권한 등 다른 문제일 수 있다.

## 흔한 실수
- 매니페스트를 확인하지 않고 "파일이 손상됐다"거나 "안티바이러스가 차단했다"고 성급히 결론짓는 것. 방패 아이콘이 있는지부터 육안으로 확인하면 빠르게 구분된다.
- 매니페스트를 수정한 뒤 원본 파일을 덮어써서, 나중에 원본과 비교 분석이 필요할 때 원본을 잃어버리는 것. 항상 사본을 만들어 패치한다.
- 서명된 파일의 매니페스트를 수정해놓고 왜 "서명이 유효하지 않다"는 별개의 오류가 새로 뜨는지 헷갈리는 것(REV-0614 참고).
- DLL의 격리 인식(isolation-aware) 매니페스트 리소스 ID(`#2`)를 EXE 리소스 ID(`#1`)로 잘못 지정해 `mt.exe`가 실패하는 것.

## 막혔을 때 다음 체크
- 매니페스트 수정 후에도 실행이 안 되고 서명 오류가 새로 뜬다면 → REV-0614(서명 검증 때문에 수정한 파일이 실행이 안 될 때)를 확인한다.
- 리소스 섹션 자체를 다루는 다른 항목이 궁금하다면 → REV-0141(Resource Section과 숨겨진 데이터 확인)을 참고한다.
- 컴파일러/링커가 기본으로 어떤 매니페스트를 붙이는지 궁금하다면 → REV-0126(Detect It Easy로 컴파일러 패커 확인)에서 컴파일러 식별 방법을 먼저 확인한다.

## 미니 예제
Resource Hacker로 `target.exe`를 열어 Manifest 리소스를 확인했더니 다음과 같았다.

```xml
<requestedExecutionLevel level="requireAdministrator" uiAccess="false" />
```

표준 사용자 계정으로 로그인된 대회 PC에서는 이 프로그램이 더블클릭해도 전혀 반응이 없었다. Resource Hacker에서 이 줄을 `level="asInvoker"`로 수정하고 "Compile Script" 후 다른 이름(`target_patched.exe`)으로 저장하니, 관리자 권한 없이도 정상적으로 창이 뜨며 실행됐다.

## 관련 글
- REV-0614 — 서명 검증 때문에 수정한 파일이 실행이 안 될 때
- REV-0141 — Resource Section과 숨겨진 데이터 확인
- REV-0126 — Detect It Easy로 컴파일러 패커 확인

## 출처/검증
- 애플리케이션 매니페스트의 `requestedExecutionLevel`(`asInvoker`/`highestAvailable`/`requireAdministrator`)과 UAC 동작은 Microsoft 공식 문서(Application Manifests, User Account Control) 기준이다.
- `RT_MANIFEST` 리소스 타입과 `CREATEPROCESS_MANIFEST_RESOURCE_ID`(1) / `ISOLATIONAWARE_MANIFEST_RESOURCE_ID`(2) 상수는 Windows SDK(`winuser.h`) 및 Microsoft 공식 문서 기준이다.
- `mt.exe` 사용법은 Visual Studio/Windows SDK 공식 문서 기준이며, 미니 예제는 설명을 위해 구성했다(2026-09-08 기준 서술).
