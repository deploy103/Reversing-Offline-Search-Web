---
id: REV-0289
title: "ImHex 설치와 기본 사용법"
slug: "rev-0289-imhex-install-usage"
category: "tools"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [ImHex]
keywords: ["imhex 설치", "imhex 사용법", "hexpat", "pattern language", "imhex pattern editor", "werwolv", "imhex offline"]
aliases: ["ImHex 헥스 에디터", "imhex 패턴 에디터", "아임헥스"]
symptom_keywords: ["구조체를 헥스에서 자동으로 파싱하고 싶음", "imhex 설치 방법 모름", "imhex 패턴 파일 사용법", "hexpat이 뭔지 모름", "imhex 오프라인 설치"]
source_ids: ["SRC-IMHEX-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
ImHex는 헥스 뷰, 디스어셈블러, 데이터 인스펙터, 그리고 자체 패턴 언어(Pattern Language, `.hexpat` 파일)로 바이너리 구조를 자동 파싱해주는 최신 무료 오픈소스 헥스 에디터로, 단순히 바이트를 보는 것을 넘어 "이 바이트가 어떤 구조체 필드인지"까지 자동으로 이름 붙여준다.

## 언제 검색해야 하나
- HxD 같은 단순 헥스 에디터로는 부족하고, 구조체 단위로 파일을 파싱해서 보고 싶을 때
- 알려진 파일 포맷(PE, ELF, PNG, ZIP 등)의 필드를 자동으로 색칠해서 보여주는 도구가 필요할 때
- 특정 오프셋의 바이트를 정수/실수/문자열 등 여러 타입으로 동시에 해석해보고 싶을 때(Data Inspector)
- 커스텀 파일 포맷을 분석하면서 직접 구조체 정의를 스크립트로 작성하고 반복 재사용하고 싶을 때
- 대회 PC에 인터넷 없이 ImHex를 설치해서 쓰고 싶을 때

## 핵심 개념

### ImHex는 "똑똑한" 헥스 에디터다
전통적인 헥스 에디터(HxD 등)는 바이트를 있는 그대로 보여주고 검색/수정만 지원한다. ImHex는 여기에 더해 **패턴 언어**라는 C와 비슷한 문법의 자체 언어로 파일 구조(구조체, 배열, 비트필드, 열거형)를 정의하면, 해당 구조에 맞춰 바이트에 자동으로 이름과 색을 입혀서 보여준다. 예를 들어 PE 파일의 `.hexpat` 패턴을 로드하면 `IMAGE_DOS_HEADER`, `IMAGE_NT_HEADERS` 필드가 헥스 뷰에서 자동으로 구간별로 표시된다.

### `.hexpat` 패턴 파일과 커뮤니티 저장소
패턴 언어로 작성한 정의는 `.hexpat` 확장자 파일로 저장된다. 공식 커뮤니티 저장소(`WerWolv/ImHex-Patterns`)에는 PE, ELF, PNG, ZIP 등 수백 개의 유명 포맷에 대한 `.hexpat` 파일이 이미 만들어져 있으며, 새 릴리스마다 ImHex의 "Content Store"라는 내장 다운로드 기능을 통해 함께 배포된다. 오프라인 대회 환경에서는 이 Content Store 자체가 인터넷을 필요로 하므로, 자주 쓰는 패턴 파일은 **미리 받아서 로컬 패턴 폴더에 넣어두는 것**이 핵심이다.

### 헥스 뷰 + 디스어셈블러 + 데이터 인스펙터가 한 화면에
ImHex는 헥스 덤프뿐 아니라 선택한 영역을 즉시 여러 진법/타입(부호있는/없는 정수, float, ASCII, UTF-8, 시간 값 등)으로 동시에 보여주는 Data Inspector, 그리고 코드 영역을 대략적으로 디스어셈블해주는 기능도 내장하고 있어, 간단한 바이너리 구조 파악은 별도 도구 없이 ImHex 안에서 상당 부분 끝낼 수 있다.

## 화면/코드에서 보이는 징후
- 헥스 뷰에서 특정 구간이 색깔별로 구획이 나뉘어 표시되면 패턴이 로드되어 자동 파싱 중이라는 뜻
- 우측 패널에 "Pattern Data"라는 트리가 있고 구조체 필드명이 나열되어 있으면 패턴 언어 기반 파싱이 적용된 상태
- 오프라인 환경에서 "Content Store"를 열었는데 목록이 비어 있거나 로딩이 멈춰 있으면 인터넷 연결이 필요한 기능이라는 뜻(정상 동작)

## 가장 먼저 할 것
분석할 파일을 열고, 먼저 알려진 포맷(PE라면 pe.hexpat 등)의 패턴을 로드해본다. 패턴이 없다면 순수 헥스 뷰와 Data Inspector만으로도 특정 오프셋의 값을 여러 타입으로 즉시 확인할 수 있으므로 바로 활용 가능하다.

## 단계별 절차

**1) 공식 다운로드 (인터넷 되는 곳에서, 한 번만)**
- `https://github.com/WerWolv/ImHex/releases`에서 운영체제에 맞는 설치 파일을 받는다
- Windows: `.msi` 설치 파일 또는 포터블 zip
- Linux: `.AppImage`(포터블, 배포판 무관) 또는 `.deb`/`.rpm`

**2) 패턴 파일 사전 확보 (매우 중요, 오프라인 대비)**
- `https://github.com/WerWolv/ImHex-Patterns`에서 저장소 전체를 zip으로 다운로드(`Code → Download ZIP`)
- 자주 쓸 `.hexpat` 파일(예: `pe.hexpat`, `elf.hexpat`, `png.hexpat`)을 로컬 패턴 폴더로 복사해둔다
- ImHex의 Content Store는 온라인 기능이므로, 오프라인 대회에서는 이 사전 복사가 유일한 방법이다

**3) 오프라인 반입**
- 설치 파일과 함께 위에서 받은 패턴 파일 폴더를 USB에 담아 대회 PC로 옮긴다
- Windows는 `.msi` 실행 후 설치, 또는 포터블 zip 압축 해제 후 바로 실행
- Linux AppImage는 `chmod +x ImHex-*.AppImage && ./ImHex-*.AppImage`

**4) 첫 실행 및 패턴 폴더 설정**
- 실행 후 `File → Open File`로 파일을 연다
- 좌측 하단 또는 `View → Pattern Editor`에서 패턴 언어 에디터를 열 수 있다
- `File → Import → Pattern File...` 또는 패턴 에디터에서 미리 받아둔 `.hexpat` 파일을 직접 `Load`

**5) 구조 파싱 확인**
- 패턴 실행 후 헥스 뷰의 색깔 구획과 우측 Pattern Data 트리에서 필드별 값을 확인

## 명령어/단축키
| 목적 | 조작 |
|---|---|
| 파일 열기 | `File → Open File` 또는 드래그&드롭 |
| 패턴 에디터 열기 | `View → Pattern Editor` |
| 패턴 파일 불러오기 | 패턴 에디터에서 `Load Pattern` 또는 `File → Import → Pattern File...` |
| 패턴 실행 | 패턴 에디터 상단 실행(▶) 버튼 |
| Data Inspector 열기 | `View → Data Inspector` (선택 영역을 여러 타입으로 동시 해석) |
| 검색 | `Ctrl+F` (바이트/문자열/정규식) |
| 오프셋으로 이동 | `Ctrl+G` |
| 즐겨찾기(Bookmark) 추가 | 선택 영역 우클릭 → Bookmark |
| 여러 파일 동시 비교 | `View → Diffing` |

## 출력 해석
- 패턴 에디터 하단에 컴파일 에러가 빨간 글씨로 나오면 `.hexpat` 문법 오류 — 라인 번호를 보고 해당 줄 확인
- Pattern Data 트리에서 필드를 클릭하면 헥스 뷰에서 해당 바이트 범위가 자동으로 하이라이트됨
- Data Inspector에서 같은 4바이트를 signed int32, unsigned int32, float, hex 각각으로 동시에 보여주므로, 값의 실제 의미(음수인지, 실수인지)를 바로 비교 가능

## 흔한 실수
- Content Store가 오프라인에서 안 열리는 것을 "ImHex가 고장났다"고 오해 — 온라인 전용 기능이며 패턴은 미리 로컬에 받아둬야 함
- `.hexpat` 패턴 파일을 아무 폴더에나 두고 ImHex가 못 찾는다고 헷갈리는 경우 — 패턴 폴더 경로(설정에서 확인 가능)에 넣거나 직접 `Load`로 지정
- 패턴 없이 열었을 때 색깔 구획이 안 보이는 것을 오류로 착각 — 패턴을 안 불러오면 원래 일반 헥스 뷰와 동일
- 큰 파일(수 GB)을 열 때 전체 로딩을 기다리지 않고 멈췄다고 오해하는 경우 — ImHex는 메모리 매핑 방식이라 대용량도 열리지만 초기 스캔에 시간이 걸릴 수 있음

## 막혔을 때 다음 체크
1. 패턴이 안 먹히면 패턴 에디터 하단 에러 로그부터 확인
2. 패턴 파일 경로가 맞는지, 오프라인 환경에서 Content Store 대신 로컬 파일로 직접 Load했는지 확인
3. 파일이 아예 안 열리면 파일 권한(읽기 전용 등) 확인
4. 구조가 예상과 다르게 파싱되면 대상 파일의 실제 엔디안(리틀/빅)이 패턴 정의와 일치하는지 확인

## 미니 예제
```text
1. chall.exe를 ImHex에 드래그&드롭
2. Pattern Editor 열기 → 미리 받아둔 pe.hexpat Load → 실행(▶)
3. 헥스 뷰에 e_magic("MZ"), e_lfanew 등 DOS 헤더 필드가 색깔별로 표시됨
4. 우측 Pattern Data 트리에서 IMAGE_NT_HEADERS.FileHeader.NumberOfSections 클릭
   → 헥스 뷰에서 해당 2바이트가 자동 하이라이트
```

## 관련 글
- REV-0290 — HxD 설치와 기본 사용법
- REV-0288 — PE-bear 설치와 사용법
- REV-0287 — Detect It Easy 설치와 사용법

## 출처/검증
- 공식 GitHub 저장소 `WerWolv/ImHex`(릴리스, 기능), `WerWolv/ImHex-Patterns`(패턴 저장소), 공식 문서(docs.werwolv.net/imhex)를 기준으로 작성했다.
- 최종 확인일: 2026-09-08
