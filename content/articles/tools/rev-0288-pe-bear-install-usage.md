---
id: REV-0288
title: "PE-bear 설치와 사용법"
slug: "rev-0288-pe-bear-install-usage"
category: "tools"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [PE-bear]
keywords: ["pe-bear 설치", "pe-bear 사용법", "PE 헤더 분석", "hasherezade", "pe-bear import table", "pe-bear section table"]
aliases: ["PE Bear", "피이베어", "PE 헤더 뷰어"]
symptom_keywords: ["PE 헤더가 뭔지 눈으로 보고싶음", "import table 확인하는법", "섹션 테이블 확인하는법", "pe-bear 설치 방법 모름", "pe-bear 실행 안됨"]
source_ids: ["SRC-PEBEAR-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
PE-bear는 Windows PE 실행 파일의 헤더, 섹션 테이블, Import/Export 테이블, 리소스를 시각적으로 파싱해서 보여주는 무료 오픈소스 GUI 도구로, IDA/Ghidra로 들어가기 전에 파일 구조를 빠르게 훑어보는 "PE 전용 X-ray" 역할을 한다.

## 언제 검색해야 하나
- PE 헤더(DOS 헤더, NT 헤더, 섹션 테이블)를 직접 파싱해서 눈으로 확인하고 싶을 때
- 어떤 DLL의 어떤 함수를 import하는지(Import Table) 빠르게 보고 싶을 때
- 손상되거나 비정상적으로 조작된(malformed) PE 파일이 IDA에서 제대로 안 열릴 때
- 섹션의 RVA/파일 오프셋 변환을 손으로 계산하지 않고 도구로 확인하고 싶을 때
- 리소스 섹션에 숨겨진 데이터(아이콘, 문자열 테이블, 커스텀 리소스)를 훑어보고 싶을 때

## 핵심 개념

### PE-bear는 무엇을 위한 도구인가
PE-bear는 "PE 파일을 빠르게 첫눈에(first view) 파악하는 것"을 목표로 만들어진 도구다. IDA/Ghidra처럼 코드를 디스어셈블하지는 않지만, PE 포맷 자체(DOS 헤더 → NT 헤더 → 섹션 테이블 → 각 디렉터리)를 매우 안정적으로 파싱해서 시각적으로 보여준다. 특히 악성코드 분석에서 자주 만나는 **일부러 망가뜨린(malformed) PE 파일**도 잘 견디도록 설계되어 있어서, IDA가 파싱 에러로 열리지 않는 파일도 PE-bear에서는 구조를 확인할 수 있는 경우가 많다.

### 개발 히스토리와 배포 형태
PE-bear는 개발자 `hasherezade`가 만들었으며, 2022년 9월부터 완전한 오픈소스로 전환되어 코드와 빌드가 공식 GitHub 저장소(`hasherezade/pe-bear`)에서 함께 관리된다. 이전에는 별도의 릴리스 저장소(`hasherezade/pe-bear-releases`)에 컴파일된 파일만 올라왔지만, 지금은 메인 저장소의 Releases 탭에서 최신 빌드를 받는 것이 표준이다. Windows용 빌드는 컴파일에 사용된 Visual Studio 버전에 따라 접미사가 붙는다(`vs17`, `vs19` 등은 별도 재배포 패키지 필요, `vs13` 빌드는 외부 의존성 없이 바로 실행 가능).

### 정적 뷰어이지 디스어셈블러가 아니다
PE-bear는 코드 섹션의 바이트를 헥스와 기초적인 디스어셈블리로 보여주긴 하지만, 함수 경계 인식이나 xref, 디컴파일 같은 깊은 정적 분석 기능은 없다. "구조를 빠르게 파악하고 다음 도구(IDA/Ghidra)로 넘어가기 전 사전 점검"이 이 도구의 역할이다.

## 화면/코드에서 보이는 징후
- IDA/Ghidra에서 PE 파일을 열었는데 "corrupted file" 또는 헤더 파싱 오류로 정상적으로 안 열릴 때
- 어떤 함수가 어느 DLL에서 온 것인지(예: `kernel32.dll!CreateFileA`) 빠르게 목록으로 보고 싶을 때
- 섹션 개수, 각 섹션의 가상 크기(Virtual Size)와 파일상 크기(Raw Size)가 다른 것이 패킹/난독화 흔적인지 의심될 때
- Entry Point RVA가 `.text` 섹션이 아니라 이상한 섹션(예: 마지막에 추가된 섹션)을 가리킬 때(패킹 흔적)

## 가장 먼저 할 것
PE 파일을 PE-bear 창에 드래그&드롭한다. 왼쪽 트리에서 `DOS Header` → `NT Headers` → `Section Headers` 순서로 클릭해보며 전체 구조를 훑는다. 그다음 `Imports` 탭에서 이 프로그램이 어떤 API를 쓰는지 확인해서 대략적인 기능을 추측한다.

## 단계별 절차

**1) 공식 다운로드 (인터넷 되는 곳에서, 한 번만)**
- `https://github.com/hasherezade/pe-bear/releases`에서 Windows용 최신 빌드(zip)를 받는다
- 접미사(vs13/vs17/vs19)를 확인 — 외부 의존성 없이 바로 쓰고 싶다면 vs13 계열, 최신 빌드가 필요하면 해당 Visual C++ 재배포 패키지도 함께 준비
- WinGet을 쓸 수 있는 환경이면 `winget install pe-bear`로도 설치 가능(단, 이 역시 인터넷 필요)

**2) 오프라인 반입**
- 받은 zip을 그대로 USB로 옮겨 대회 PC에 압축 해제
- vs17/vs19 빌드를 쓴다면 Visual C++ 재배포 패키지(`vc_redist.x64.exe` 등)도 함께 오프라인 설치해둔다

**3) 첫 실행**
- 압축을 푼 폴더의 `PE-bear.exe`를 더블클릭하면 바로 실행된다(설치 프로그램 없이 포터블 형태)

**4) 바이너리 로드**
- `File → Open` 메뉴 또는 창에 파일을 드래그&드롭
- 여러 파일을 동시에 열어 좌측 탭으로 전환하며 비교 분석도 가능

**5) 구조 훑어보기**
- 좌측 트리에서 헤더/섹션/디렉터리를 순서대로 클릭
- `Imports`, `Exports`, `Resources` 탭에서 각각의 목록 확인
- 하단/우측 헥스 뷰에서 선택한 필드가 실제 파일의 어느 바이트에 해당하는지 하이라이트로 확인

## 명령어/단축키
| 목적 | 조작 |
|---|---|
| 파일 열기 | `File → Open` 또는 드래그&드롭 |
| 헤더 트리 이동 | 좌측 트리 클릭 (DOS Header / NT Headers / Section Headers) |
| Import 목록 | 좌측 트리 `Imports` 또는 상단 탭 |
| Export 목록 | 좌측 트리 `Exports` |
| 리소스 보기 | 좌측 트리 `Resources` |
| RVA ↔ 파일 오프셋 변환 | 필드를 클릭하면 하단 헥스 뷰에서 해당 오프셋이 자동 하이라이트 |
| 패턴/바이트 검색 | 우클릭 메뉴 또는 상단 검색 아이콘으로 시그니처 검색 |
| 헥스 값 직접 수정 | 헥스 뷰에서 클릭 후 바로 편집 가능(패치 실험용) |
| 수정 내용 저장 | `File → Save as...` |

## 출력 해석
- `NT Headers → File Header → NumberOfSections`: 실제 섹션 테이블 항목 개수와 이 값이 다르면 조작 의심
- `Section Headers`에서 `Virtual Size`가 `Raw Size`보다 훨씬 크면 실행 시 메모리에서 압축 해제/언패킹되는 영역일 가능성이 높음
- `Imports` 탭에 함수가 거의 없거나(정상 프로그램치고 너무 적음) `LoadLibrary`/`GetProcAddress`만 있으면 나머지 API를 런타임에 동적으로 resolve하는 패턴(패킹/난독화 흔적)
- `Entry Point`가 가리키는 섹션이 `.text`가 아니면 정상 컴파일러가 만든 배치가 아닐 가능성이 높음 (패커가 추가한 섹션일 수 있음)

## 흔한 실수
- PE-bear로 구조만 보고 실제 코드 로직까지 다 파악했다고 착각하는 경우 — 디스어셈블/디컴파일은 IDA/Ghidra의 역할
- vs17/vs19 빌드를 받았는데 재배포 패키지 없이 실행해서 "실행이 안 됨"으로 오인하는 경우
- 헥스 뷰에서 실수로 값을 수정한 뒤 저장(`Save as`)해서 원본 파일이 훼손되는 경우 — 항상 원본 사본을 따로 보관
- Import Table을 볼 때 Ordinal(이름 없이 번호로만 import)로 표시된 함수를 그냥 지나치는 경우 — 별도로 DLL 문서에서 번호-이름 매핑 확인 필요

## 막혔을 때 다음 체크
1. 파일이 아예 안 열리면 정말 PE 포맷이 맞는지 DIE(REV-0287)로 먼저 확인
2. vs17/vs19 빌드 실행 오류 시 Visual C++ 재배포 패키지 설치 여부 확인
3. Import 목록이 이상하게 적으면 DIE로 패커 여부부터 확인
4. 헥스 뷰 값과 트리에 표시된 필드 값이 안 맞으면 리틀 엔디안 해석을 다시 확인(PE 필드는 대부분 리틀 엔디안)

## 미니 예제
```text
1. chall.exe를 PE-bear 창에 드래그&드롭
2. 좌측 트리 → NT Headers → File Header 클릭
   → NumberOfSections: 5, TimeDateStamp: 확인
3. 좌측 트리 → Imports 클릭
   → KERNEL32.dll: CreateFileA, ReadFile, WriteFile
   → USER32.dll: MessageBoxA
4. 콘솔 입출력/메시지박스를 쓰는 일반적인 GUI 프로그램으로 추정
5. 이후 IDA/Ghidra로 넘어가 실제 로직 분석
```

## 관련 글
- REV-0287 — Detect It Easy 설치와 사용법
- REV-0289 — ImHex 설치와 기본 사용법
- REV-0125 — PE-bear로 헤더 분석하는 방법

## 출처/검증
- 공식 GitHub 저장소 `hasherezade/pe-bear`(릴리스, 빌드 변형 안내)를 기준으로 배포 방식과 기능을 확인했다.
- 최종 확인일: 2026-09-08
