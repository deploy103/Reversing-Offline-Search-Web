---
id: REV-0156
title: "Ghidra 프로젝트 생성과 바이너리 Import"
slug: "rev-0156-ghidra-project-import"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra 프로젝트 생성", "Ghidra Import File", "Ghidra New Project", "Ghidra Non-Shared Project", "Ghidra Language Compiler ID"]
aliases: ["Ghidra 시작하기", "Ghidra 파일 불러오기", "Ghidra 임포트", "Ghidra 프로젝트 만들기"]
symptom_keywords: ["Ghidra 처음 켰는데 뭘 해야 할지 모르겠음", "Ghidra에 파일을 어떻게 넣나요", "Ghidra Import 대화상자가 뭔지 모름", "Ghidra Language 선택을 잘못한 것 같음"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Ghidra는 IDA처럼 실행 파일을 바로 여는 것이 아니라 **프로젝트(Project)를 먼저 만들고, 그 프로젝트 안에 바이너리를 Import해서 프로그램(Program)으로 등록한 뒤** CodeBrowser에서 여는 구조이며, Import 시 Format/Language/Compiler를 올바르게 선택하는 것이 이후 모든 분석 품질을 좌우한다.

## 언제 검색해야 하나
- Ghidra를 처음 실행했는데 화면에 프로젝트 창(Project window)만 뜨고 무엇을 눌러야 할지 모를 때
- "Import File" 대화상자에 Format, Language, Destination Folder 같은 항목이 나오는데 무슨 뜻인지 모를 때
- Import는 됐는데 디컴파일 결과가 이상해서 Language/Compiler를 잘못 골랐는지 의심될 때
- IDA는 써봤지만 Ghidra는 처음이라 "프로젝트"라는 개념 자체가 낯설 때

## 핵심 개념
IDA에서는 `.idb`/`.i64` 하나가 곧 "분석 세션"이다. 반면 Ghidra는 계층이 하나 더 있다.

- **Project(프로젝트)**: 여러 개의 분석 대상(프로그램)을 담는 폴더 같은 단위. 디스크에는 `<프로젝트이름>.gpr` 파일과 `<프로젝트이름>.rep` 폴더가 함께 생성된다. `.gpr`은 프로젝트 메타데이터, `.rep` 폴더 안에 실제 분석 데이터베이스(각 Program의 분석 결과)가 저장된다.
- **Program(프로그램)**: 프로젝트 안에 Import된 개별 바이너리 하나. 원본 실행 파일을 직접 수정하는 것이 아니라, Ghidra가 원본을 읽어서 자체 데이터베이스로 복사·변환해 저장한다. 즉 원본 `.exe`/`.elf` 파일은 건드리지 않는다.
- **Non-Shared Project vs Shared Project**: 개인이 로컬에서 혼자 분석할 때는 Non-Shared Project(로컬 전용)를 쓴다. Shared Project는 Ghidra Server를 통해 여러 명이 협업 분석할 때 쓰는 구조로, 오프라인 CTF 환경에서는 필요 없다.
- **Import 시 Format**: 바이너리의 컨테이너 형식. Windows 실행 파일은 `PE`, Linux 실행 파일은 `ELF`, 헤더 없는 순수 바이트 덤프는 `Raw Binary`를 선택한다. Ghidra는 파일 시그니처를 보고 자동으로 후보를 추천해 주지만, 최종 선택은 사용자가 확인해야 한다.
- **Language(프로세서 사양)**: `x86:LE:32:default`처럼 "프로세서 아키텍처:엔디안:비트수:세부모델" 형태로 표기된다. 32비트 x86 PE라면 `x86:LE:32:default`, 64비트라면 `x86:LE:64:default`를 골라야 한다. 여기서 32/64를 잘못 고르면 레지스터 폭과 스택 프레임 계산이 전부 틀어진다.
- **Compiler Spec(컴파일러 사양)**: 같은 프로세서라도 호출 규약과 스택 정리 방식이 컴파일러/OS마다 다르다. Windows PE는 보통 `windows` cspec, Linux ELF(gcc로 빌드)는 보통 `gcc` cspec을 사용한다. Ghidra는 PE/ELF 헤더 정보를 보고 대부분 자동으로 맞는 조합을 골라주지만, Raw Binary를 Import할 때는 사용자가 직접 지정해야 한다.

Language/Compiler를 잘못 고르면 겉보기에는 Import가 "성공"한 것처럼 보여도, 디스어셈블리 자체가 엉뚱한 명령어로 해석되거나(예: 64비트 코드를 32비트로 잘못 해석) 함수 인자 전달 규약이 틀려서 디컴파일 결과가 처음부터 신뢰할 수 없게 된다.

## 화면/코드에서 보이는 징후
- Ghidra를 처음 실행하면 "Ghidra Project" 창(메뉴가 File / Edit / Tools / Help뿐인 작은 창)만 뜨고, 그 안에 Active Project 트리 목록이 비어 있다.
- 파일을 Import하지 않고 CodeBrowser를 바로 열려고 하면 열 대상이 없다.
- Import File 대화상자를 열면 상단에 "Format", 그 아래 "Language", "Destination Folder" 항목이 보이고, Format을 바꾸면 Language 후보 목록도 바뀐다.

## 가장 먼저 할 것
아직 프로젝트가 없다면 File → New Project로 로컬(Non-Shared) 프로젝트를 하나 만든다. 이미 프로젝트가 있다면 그 프로젝트를 열고, File → Import File로 분석할 바이너리를 끌어오거나 대화상자에서 직접 선택한다.

## 단계별 절차

**1) Ghidra 실행**

Windows에서는 설치 폴더의 `ghidraRun.bat`, Linux에서는 `ghidraRun` 스크립트를 실행한다. 처음 실행 시 라이선스 동의 화면이 나올 수 있다.

**2) 새 프로젝트 만들기**

Project window에서 **File → New Project**를 선택한다. "Select Project Type" 화면에서 **Non-Shared Project**(로컬 전용, 협업 서버 불필요)를 선택하고 Next. 그다음 "Project Name"과 "Project Directory"(저장 위치)를 입력하고 **Finish**를 누른다. 이 순간 지정한 폴더에 `<이름>.gpr` 파일과 `<이름>.rep` 폴더가 생성된다.

**3) 바이너리 Import**

Project window 메뉴에서 **File → Import File...**을 선택하거나, 분석할 바이너리 파일을 탐색기/파일 관리자에서 Project window로 드래그 앤 드롭한다.

**4) Import 대화상자 확인**

"Import File" 대화상자가 뜨면 다음을 확인한다:
- **Format**: Ghidra가 파일 헤더를 보고 자동 추천한다(예: `Portable Executable (PE)`, `Executable and Linking Format (ELF)`). 헤더가 없는 순수 바이너리 덤프라면 `Raw Binary`를 직접 선택해야 한다.
- **Language**: 우측의 `...` 버튼을 눌러 "Language Provider" 창에서 정확한 프로세서/비트수/엔디안을 고른다. PE/ELF 파일은 헤더에 아키텍처 정보가 들어 있어 보통 자동으로 정확히 채워진다. Raw Binary는 사용자가 직접 골라야 하므로, 대상이 32비트인지 64비트인지, x86인지 ARM인지 미리 `file` 명령이나 헤더 바이트로 확인해 두는 것이 좋다.
- **Destination Folder**: 프로젝트 안에서 이 프로그램을 저장할 폴더(기본은 프로젝트 루트).

옵션을 더 세밀하게 조정하려면 **Options...** 버튼을 눌러 base address, block name 등을 지정할 수 있지만, 일반적인 PE/ELF 실행 파일이라면 기본값을 그대로 두어도 된다.

**5) Import 실행 및 결과 확인**

**OK**를 누르면 Import가 진행되고, 완료되면 "Import Results Summary" 창이 뜬다. 여기서 로드된 메모리 블록 수, 심볼 개수, entry point 주소 등을 간단히 확인할 수 있다. **OK**로 닫는다.

**6) CodeBrowser로 열기**

Project window에 방금 Import한 파일이 아이콘으로 나타난다. 이 아이콘을 더블클릭하면 **CodeBrowser** 툴(디스어셈블리/디컴파일을 보는 메인 창)이 열린다. 이때 "Would you like to analyze it now?"라는 Auto Analysis 여부를 묻는 대화상자가 뜨는데, 이 옵션들은 REV-0157(Ghidra Auto Analysis 옵션)에서 자세히 다룬다.

## 명령어/단축키
- 프로젝트 생성: **File → New Project**
- 파일 불러오기: **File → Import File...** 또는 드래그 앤 드롭
- 여러 파일 한 번에: **File → Batch Import...** (같은 폴더의 여러 바이너리를 한 번에 Import)
- 이미 Import한 프로그램 열기: Project window에서 아이콘 더블클릭
- 프로젝트 저장 위치 나중에 확인: 프로젝트 파일 = `<이름>.gpr` + `<이름>.rep` 폴더

## 출력 해석
- Import Results Summary에 표시되는 "Language"와 "Compiler Spec ID"는 실제로 이 바이너리가 어떤 사양으로 디스어셈블/디컴파일될지를 보여주는 최종 확인 값이다. PE 파일인데 여기에 `gcc`가 찍혀 있다면 뭔가 잘못 인식된 것이니 재Import를 고려해야 한다.
- Destination Folder 트리에서 파일 아이콘 색/모양은 포맷별로 다르게 표시되며(PE, ELF 등), 같은 폴더에 여러 파일을 정리해 두면 프로젝트가 커져도 찾기 쉽다.

## 흔한 실수
- **Shared Project를 실수로 선택**하는 것 — 서버 주소를 요구하며 진행이 막힌다. 오프라인 CTF 환경에서는 항상 Non-Shared Project를 선택해야 한다.
- **원본 파일이 수정된다고 착각**하는 것 — Ghidra는 Import 시 원본을 프로젝트 데이터베이스로 복사해 저장하므로, CodeBrowser에서 Rename/Retype 등을 아무리 해도 원본 `.exe`/`.elf` 파일 자체는 바뀌지 않는다.
- **UPX 등으로 패킹된 바이너리를 그대로 Import**하고 왜 문자열이 안 보이는지 헤매는 것 — 패킹된 바이너리는 언패킹 전까지는 정적 분석으로 의미 있는 코드/문자열을 보기 어렵다. 이 경우 정적 분석에 앞서 UPX 언패킹(`upx -d`) 여부부터 확인해야 한다.
- **32비트 바이너리인데 Raw Binary로 잘못 Import하면서 64비트 Language를 고르는 것** — PE/ELF는 자동 인식이 잘 되지만, Raw Binary를 다룰 때는 이 실수가 흔하다. Import 전에 `file` 명령이나 PE-bear/헤더 확인으로 비트수를 미리 파악해 둔다.
- Import 대화상자를 열지도 않고 습관적으로 **Options를 건드리지 않은 채 Format 자동 추천만 믿는 것** — 대부분은 맞지만, 헤더가 손상되었거나 비표준 포맷인 경우 자동 추천이 틀릴 수 있으므로 Format/Language 값을 한 번은 눈으로 확인하는 습관이 필요하다.

## 막혔을 때 다음 체크
- Import 자체가 실패하거나 "Format" 후보에 아무것도 안 뜬다면 → 파일이 손상되었거나 지원하지 않는 포맷일 수 있다. `file` 명령으로 실제 파일 타입을 먼저 확인한다.
- Import는 됐는데 Auto Analysis 옵션이 궁금하다면 → REV-0157(Ghidra Auto Analysis 옵션)로 이동.
- CodeBrowser를 열었는데 화면 구성(패널 배치)이 낯설다면 → REV-0159(Ghidra Function 목록과 Symbol Tree)에서 각 패널을 설명한다.
- 디컴파일 결과 자체가 이상하다면 → REV-0158(Ghidra Decompiler 창 읽기) 참고.

## 미니 예제
32비트 Windows PE 파일 `crackme.exe`를 분석한다고 가정하자.

1. Ghidra 실행 → Project window에서 File → New Project → Non-Shared Project → 이름 `ctf-project`로 생성.
2. `crackme.exe`를 Project window로 드래그.
3. Import File 대화상자에서 Format이 자동으로 `Portable Executable (PE)`로 잡히고, Language가 `x86:LE:32:default`, Compiler Spec이 `windows`로 자동 설정된 것을 확인.
4. OK → Import Results Summary에서 entry point 주소와 로드된 섹션 수(`.text`, `.data`, `.rdata` 등)를 확인.
5. Project window에서 `crackme.exe` 아이콘을 더블클릭 → CodeBrowser가 열리고 Auto Analysis 여부를 묻는 대화상자가 뜬다.

이 시점부터가 REV-0157에서 다루는 Auto Analysis 단계다.

## 관련 글
- REV-0157 — Ghidra Auto Analysis 옵션
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0159 — Ghidra Function 목록과 Symbol Tree
- rev-0151-positive-sp-value.md — IDA의 스택 분석 경고(비교 참고용)
- ../assembly/rev-0071-call.md — CALL 명령어와 호출 규약

## 출처/검증
- Ghidra 프로젝트/Import 워크플로우: Ghidra 공식 Help(AutoAnalysisPlugin 및 Importer 관련 도움말 topic)와 다수의 공개 Ghidra 튜토리얼(Non-Shared/Shared Project, Import File 대화상자 구성)에 기반해 작성. 실제 최신 버전 화면과 100% 동일한지는 로컬에서 직접 실행해 재검증하는 것을 권장한다(이 문서는 라이브 Ghidra 환경에서의 직접 캡처 검증 없이, 공식 문서와 잘 알려진 관례를 기준으로 작성됨).
- Language/Compiler Spec 표기 형식(`x86:LE:32:default`): Ghidra SLEIGH 프로세서 사양 명명 규칙 기준.
