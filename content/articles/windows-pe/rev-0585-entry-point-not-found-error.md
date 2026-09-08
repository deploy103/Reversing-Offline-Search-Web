---
id: REV-0585
title: "Entry Point를 찾을 수 없다는 오류가 뜰 때"
slug: "rev-0585-entry-point-not-found-error"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [PE-bear, IDA, x64dbg, DIE]
keywords: ["procedure entry point could not be located", "프로시저 진입점을 찾을 수 없습니다", "AddressOfEntryPoint", "DLL 검색 순서", "IAT 패치 오류"]
aliases: ["entry point not found 오류", "프로시저 진입점 오류", "DLL 진입점 못 찾음"]
symptom_keywords: ["프로시저 진입점을 찾을 수 없습니다", "The procedure entry point could not be located", "패치한 파일이 실행이 안 된다", "DLL 교체 후 실행 오류"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
"Entry Point Not Found" 오류는 대부분 실행 파일이 요구하는 DLL의 특정 함수(주로 export 이름/서수)를 찾지 못한 것이며, 어떤 DLL·함수 이름이 메시지에 적혀 있는지가 원인 진단의 핵심 단서다.

## 진단 먼저: 어떤 "Entry Point" 오류인지부터 구분한다
"Entry Point를 찾을 수 없다"는 말은 실제로 두 가지 서로 다른 상황을 가리킬 수 있으므로 화면에 뜨는 메시지를 정확히 읽는 것이 첫 단계다.

1. **Windows 실행 시 대화상자**: `%s 프로시저 진입점을 %s 동적 연결 라이브러리에서 찾을 수 없습니다.` / 영문: `The procedure entry point <FunctionName> could not be located in the dynamic link library <DLLName>.` — 이것이 압도적으로 가장 흔한 경우이며, DLL의 **함수(export) 진입점**을 못 찾았다는 뜻이다. 프로그램의 진입점(WinMain)과는 무관하다.
2. **PE 헤더의 `AddressOfEntryPoint`가 유효하지 않음**: 파일을 수동으로 패치하다가 Optional Header의 `AddressOfEntryPoint` 값이 손상되어, Windows 로더나 IDA가 프로그램 시작 지점 자체를 찾지 못하는 경우다. 이 경우 보통 `%1은(는) 올바른 Win32 응용 프로그램이 아닙니다`류의 오류가 뜨거나, IDA에서 엔트리 포인트가 이상한 곳(섹션 밖, 데이터 영역)을 가리킨다.

실무에서 "Entry Point를 찾을 수 없다"는 표현으로 가장 자주 마주치는 것은 1번(프로시저 진입점 오류)이므로, 아래 절차도 1번을 중심으로 다루고 2번은 별도 섹션에서 다룬다.

## 언제 검색해야 하나
- DLL을 교체(패치, 다른 버전으로 대체, IAT 수동 편집)한 뒤 원본 프로그램을 실행했더니 `The procedure entry point ... could not be located in the dynamic link library ...` 오류가 뜰 때
- Scylla 등으로 IAT를 재구성한 실행 파일을 실행했더니 비슷한 오류가 뜰 때
- 리버스 엔지니어링 실습으로 함수를 패치/후킹한 뒤 실행 파일이 갑자기 실행이 안 될 때
- 오래된 DLL이나 다른 시스템에서 복사해온 DLL을 같은 폴더에 넣었더니 원래 잘 되던 프로그램이 이 오류를 낼 때

## 핵심 개념
이 오류는 Windows 로더가 실행 파일을 메모리에 매핑하고 Import Table을 순회하며 각 DLL에서 필요한 함수를 **이름(또는 서수)** 기준으로 찾는 과정(바인딩, binding)에서, 지정된 DLL을 열긴 열었는데 그 DLL의 Export Table 안에 요청한 이름의 함수가 없을 때 발생한다. 즉 "실행 파일이 기대하는 함수"와 "실제로 로드된 DLL이 제공하는 함수"가 서로 다르다는 뜻이다. 주요 원인은 다음과 같다.

- **DLL 버전 불일치**: 실행 파일이 최신 API(예: 새 SDK에서 추가된 함수)를 쓰도록 빌드되었는데, 실행 환경에 더 오래된 버전의 DLL이 있어 그 함수가 없는 경우.
- **DLL 검색 순서(search order) 문제**: 애플리케이션 폴더에 무관한(이름만 같은) DLL이 놓여 있어서, 시스템 DLL 대신 그 DLL이 먼저 로드되고 정작 필요한 함수는 그 DLL에 없는 경우(DLL 검색 순서 하이재킹과 유사한 상황이지만 의도치 않게 발생하기도 함).
- **수동 IAT 편집 실수**: 리버싱 실습 중 Import Table의 함수 이름 문자열(Hint/Name 항목)을 직접 수정했는데, 오타가 있거나 실제로 그 DLL에 존재하지 않는 이름으로 잘못 써넣은 경우.
- **Import 재구성(Scylla 등) 오류**: 언패킹 후 IAT를 재구성할 때 실제로는 서수(ordinal)로만 export된 함수를 이름 기준으로 잘못 매칭해 저장한 경우.

## 화면/코드에서 보이는 징후
- 대화상자에 표시되는 정확한 함수 이름(예: `GetTickCount64`, `InitializeConditionVariable`)이 비교적 최신 API라면 "오래된 시스템 DLL 때문일 가능성"의 강한 단서다.
- PE-bear로 대상 EXE의 Import Table을 열어봤을 때, 오류 메시지에 나온 함수 이름이 특정 DLL 밑에 리스트되어 있는데, 실제 시스템(`C:\Windows\System32\`)에 있는 그 DLL을 Export Table 기준으로 열어보면 해당 이름이 없음
- 같은 폴더에 애플리케이션과 무관해 보이는 오래된 `.dll` 파일이 함께 놓여 있음(DLL 검색 순서상 시스템 DLL보다 먼저 로드됨)
- IAT를 수동 편집한 직후라면, 편집한 함수 이름 문자열의 철자나 널 종료 여부를 의심해볼 수 있음

## 가장 먼저 할 것
오류 대화상자에 나온 **정확한 함수 이름과 DLL 이름**을 그대로 기록한다. 이 두 정보만으로 원인 후보가 크게 좁혀진다.

## 단계별 절차
**1) 함수가 실제로 어느 DLL에 있는지 확인**
- PE-bear나 DIE로 `C:\Windows\System32\<DLL이름>`을 직접 열어 Export Table에서 해당 함수 이름을 검색한다. 없다면 시스템에 설치된 DLL 버전이 실행 파일이 기대하는 것보다 오래된 것이다.
- 없는 게 확인되면, 프로그램이 요구하는 최소 Windows 버전을 다시 확인하거나(매니페스트, REV-0550 참고), 올바른 버전의 시스템을 준비한다.

**2) DLL 검색 순서 문제 확인**
- 실행 파일과 같은 폴더에 시스템 DLL과 이름이 같은 파일이 있는지 확인한다. 있다면 Windows는 기본적으로(SafeDllSearchMode 등 보안 설정에 따라 다르지만) 애플리케이션 폴더의 DLL을 시스템 폴더보다 먼저 찾는 경우가 많으므로, 그 파일이 진짜 필요한 DLL이 맞는지 검증한다.
- 무관한 DLL이라면 삭제하거나 이름을 바꿔 시스템 DLL이 정상적으로 로드되도록 한다.

**3) 직접 편집/재구성한 IAT가 원인일 때**
- HxD나 PE-bear로 Import Table의 Hint/Name 항목을 다시 열어, 오류에 나온 함수 이름과 정확히 일치하는지(대소문자, 철자, 널 종료) 바이트 단위로 재확인한다.
- Scylla로 IAT를 재구성했다면, "Get Imports" 결과 목록에서 해당 함수 항목이 `???`나 이상한 이름으로 표시되지 않았는지 다시 확인하고, 필요하면 OEP를 다시 잡아 재시도한다.

**4) PE 헤더의 AddressOfEntryPoint 자체가 문제일 때(2번 상황)**
- PE-bear로 Optional Header의 `AddressOfEntryPoint` 값을 확인하고, 이 RVA가 실제 섹션(`.text` 등) 범위 안에 있는지 확인한다.
- 범위를 벗어났다면 수동 편집 과정에서 값이 손상된 것이므로, 백업해둔 원본과 비교하거나 올바른 값으로 복구한다.

## 명령어/단축키
- PE-bear: Import Table 트리에서 DLL/함수 목록 확인, Export Table 탭으로 전환해 실제 시스템 DLL의 export 목록 확인
- IDA: `Ctrl+F`(Imports 검색), Exports 탭에서 대상 DLL을 별도로 열어 비교
- DIE: DLL/EXE 각각 드래그해 버전/컴파일러 정보 비교

## 출력 해석
- Export Table 검색 결과 함수 이름이 아예 없으면 버전 문제, 이름은 비슷한데 철자가 다르면(예: `CreateFileW` vs `CreateFilesW`) 수동 편집 오타 문제다.
- 함수가 서수(ordinal)로만 export되어 있고 이름이 없는 DLL이라면(흔치 않지만 존재), 이름 기준 임포트 자체가 애초에 성립하지 않으므로 서수 기준으로 다시 임포트를 구성해야 한다(REV-0555 참고).

## 흔한 실수
- 오류 메시지의 함수 이름만 보고 바로 "이 DLL이 문제"라고 단정한 뒤, 실제로는 검색 순서상 다른 위치의 DLL이 먼저 로드되고 있다는 걸 놓치는 것 — 반드시 "지금 실제로 로드되는 DLL이 어느 경로의 파일인지" 확인해야 한다.
- IAT를 수동으로 편집하면서 문자열 길이(바이트 수)를 맞추지 않고 이름을 바꿔서, 뒤에 이어지는 다른 구조체 데이터까지 밀려나 깨지는 것.
- Scylla로 IAT 재구성할 때 "Invalid"로 표시된 항목을 무시하고 그냥 저장해버리는 것 — 이런 항목이 결국 이 오류의 원인이 된다.
- 시스템 DLL을 임의로 다른 버전으로 교체해서 문제를 "해결"하려다가 시스템의 다른 프로그램까지 망가뜨리는 것 — 시스템 DLL 교체는 신중해야 하며, 가능하면 격리된 분석 환경(VM)에서만 시도한다.

## 막혔을 때 다음 체크
- IAT 재구성 자체가 처음이라면 → REV-0581(IDA에서 PE를 열었는데 Import Table이 비어있을 때)의 Scylla 사용법 부분을 먼저 참고한다.
- 서수 기반 임포트가 원인이라면 → REV-0555(Ordinal Import(이름 없는 Import) 분석법) 참고
- 실행 요구사항(최소 OS 버전 등)이 명시된 매니페스트를 확인하고 싶다면 → REV-0550(매니페스트에서 실행 요구사항 확인하기) 참고

## 미니 예제
```
오류 메시지: "The procedure entry point ??1?$basic... could not be
located in the dynamic link library VCRUNTIME140.dll"
→ 함수 이름이 C++ 이름 맹글링 형태 → VC++ 런타임 버전 불일치로 판단
→ 올바른 버전의 vcredist를 설치하거나 정적 링크된 빌드로 교체
```

## 관련 글
- REV-0581 — IDA에서 PE를 열었는데 Import Table이 비어있을 때
- REV-0582 — x64dbg가 실행 파일을 로드하지 못할 때
- REV-0555 — Ordinal Import(이름 없는 Import) 분석법
- REV-0550 — 매니페스트(Manifest)에서 실행 요구사항 확인하기
- REV-0119 — Import Table에서 중요한 API 찾기

## 출처/검증
- `The procedure entry point ... could not be located in the dynamic link library ...` 오류는 Windows PE 로더가 Import Table의 함수 이름을 대상 DLL의 Export Table에서 찾지 못했을 때 발생하는 잘 알려진 표준 Windows 오류이며, 다수의 Microsoft 지원 문서와 일반 Windows 문제 해결 자료에서 공통적으로 다루는 내용이다.
- Import/Export Table 구조(`IMAGE_IMPORT_DESCRIPTOR`, `IMAGE_EXPORT_DIRECTORY`)와 이름/서수 기반 바인딩 방식은 Microsoft PE Format 공식 문서 기준이다.
- DLL 검색 순서(애플리케이션 폴더 vs 시스템 폴더)에 대한 일반적 설명은 Microsoft의 Dynamic-Link Library Search Order 공식 문서를 근거로 한다(2026-09-08 기준).
