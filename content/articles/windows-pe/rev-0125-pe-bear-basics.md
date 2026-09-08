---
id: REV-0125
title: "PE-bear로 헤더 분석하는 방법"
slug: "rev-0125-pe-bear-basics"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: ["PE-bear"]
keywords: ["PE-bear", "PE 헤더 분석", "DOS Header", "NT Header", "Optional Header", "Section Table", "Import Table", "Export Table", "PE-bear 사용법", "PE 구조 뷰어"]
aliases: ["PE bear", "PEbear", "PE-bear 툴", "PE 헤더 뷰어"]
symptom_keywords: ["PE-bear 처음 켰는데 뭐부터 봐야 할지 모르겠음", "exe 헤더 구조가 궁금함", "PE-bear로 섹션 확인하는 법", "PE-bear import table 안 보임", "PE-bear entry point 못 찾겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
PE-bear는 PE(Portable Executable) 파일의 DOS Header, NT Header, Section Table, Import/Export Table 등을 트리 형태 GUI로 빠르게 훑어볼 수 있는 무료 헤더 분석 툴로, 디스어셈블 없이도 "이 파일이 32비트인지 64비트인지, 어떤 섹션이 있는지, 엔트리 포인트가 어디인지, 무슨 API를 쓰는지"를 몇 초 안에 파악하는 데 쓴다.

## 언제 검색해야 하나
- IDA나 x64dbg로 들어가기 전에, PE 구조 자체(섹션, 헤더 값, import/export)를 먼저 빠르게 훑어보고 싶을 때
- exe/dll 파일이 32비트인지 64비트인지, 어떤 서브시스템(콘솔/GUI)인지 헤더 값으로 바로 확인하고 싶을 때
- 섹션 이름이 이상하거나(`.text`가 아닌 이름), 섹션 개수가 비정상적으로 적거나 많아서 패킹이 의심될 때
- Entry Point(엔트리 포인트) RVA 값을 헥스 값 그대로 확인하고, 그 주소가 어느 섹션에 속하는지 알고 싶을 때
- Import Table에 어떤 DLL/함수가 링크되어 있는지 디스어셈블러 없이 목록으로만 빠르게 보고 싶을 때

## 핵심 개념

### PE 파일 구조 한눈에
PE 파일은 크게 다음 순서로 구성된다.

1. **DOS Header** — 파일 맨 앞의 `MZ` 매직 바이트로 시작하는 레거시 헤더. 대부분 필드는 현대 Windows에서 의미가 없고, 중요한 건 파일 끝에 있는 실제 헤더(`e_lfanew`)의 오프셋을 가리키는 값 하나뿐이다.
2. **NT Headers** — `PE\0\0` 시그니처로 시작하며, 다시 **File Header**(머신 종류, 섹션 개수, 타임스탬프 등)와 **Optional Header**(엔트리 포인트, 이미지 베이스, 서브시스템, 데이터 디렉토리 등 실제로 중요한 정보 대부분)로 나뉜다. "Optional"이라는 이름과 달리 실행 파일에서는 사실상 필수다.
3. **Section Table** — `.text`(코드), `.data`(초기화된 전역 변수), `.rdata`(읽기 전용 데이터, import table 포함), `.rsrc`(리소스, 아이콘 등), `.reloc`(재배치 정보) 같은 섹션들의 이름, 크기, 파일/메모리상 위치, 권한(읽기/쓰기/실행)이 나열된 테이블.
4. **Data Directories** — Optional Header 안에 있는 16개의 항목으로, Import Table, Export Table, Resource, Relocation, TLS 등 각 데이터가 어디(RVA)에 얼마나(Size) 있는지를 가리키는 포인터 모음.

PE-bear는 이 구조 전체를 왼쪽 트리 패널로 보여주고, 항목을 클릭하면 오른쪽에 필드별 값을 표로 보여준다.

### RVA(Relative Virtual Address)와 파일 오프셋
PE를 볼 때 계속 나오는 개념이 RVA다. RVA는 "파일이 메모리에 로드된 이후, 이미지 베이스로부터의 상대 주소"다. 파일 상태에서의 오프셋(Raw Offset)과 메모리에 로드된 뒤의 RVA는 섹션 정렬 방식 때문에 값이 다르다. PE-bear는 이 둘을 자동으로 계산해서 함께 보여주므로, 수동 변환 공식을 몰라도 특정 RVA가 파일의 어느 바이트에 대응하는지 바로 확인할 수 있다.

### 왜 IDA보다 먼저(혹은 같이) 쓰는가
IDA는 디스어셈블/디컴파일에 최적화된 툴이라 헤더 구조 자체를 훑어보기엔 클릭이 많고 느리다. PE-bear는 무겁게 분석하지 않고 헤더/섹션/디렉토리 값만 즉시 파싱해서 보여주므로, "이 파일 뭐부터 봐야 하지"를 몇 초 안에 정리하는 1차 트리아지(triage) 툴로 적합하다.

## 화면/코드에서 보이는 징후
- PE-bear로 파일을 열면 왼쪽에 트리 구조(DOS Header, NT Header → File Header/Optional Header, Section Headers, Import Table, Export Table 등)가 나타난다.
- 상단 탭 중 하나로 "General info"(또는 "Basic Info") 화면이 있어서 파일 형식, 머신(x86/x64), 엔트리 포인트, 서브시스템 등을 요약해서 보여준다.
- 특정 섹션 헤더를 클릭하면 `VirtualSize`, `VirtualAddress`, `SizeOfRawData`, `PointerToRawData`, `Characteristics`(읽기/쓰기/실행 플래그) 값이 표로 나타난다.
- Import Table 항목을 클릭하면 어떤 DLL(`kernel32.dll`, `user32.dll` 등)에서 어떤 함수 이름을 가져오는지 리스트로 나열된다.
- 헤더 값이 깨져 있거나(예: 섹션 개수와 실제 섹션 헤더 수가 안 맞음, 엔트리 포인트가 어느 섹션에도 속하지 않음) 있으면 PE-bear가 경고 아이콘이나 빨간 표시로 이상 징후를 알려준다.

## 가장 먼저 할 것
파일을 열자마자 상단의 "General/Basic info" 요약 화면에서 **Machine(x86/x64), Entry Point, Subsystem, 섹션 개수**를 먼저 확인한다. 여기서 섹션 개수가 지나치게 적거나(2~3개), 섹션 이름이 `.text`/`.data`/`.rdata` 같은 표준 이름이 아니라 `UPX0`, `UPX1`처럼 낯설다면 패커가 의심되므로 다음 단계로 Detect It Easy(REV-0126)를 먼저 돌리는 것이 순서상 낫다.

## 단계별 절차

**1) 파일 열기**

PE-bear 실행 후 `File → Open` 또는 실행 파일을 창에 드래그&드롭한다.

**2) General/Basic info 확인**

상단 탭에서 요약 정보를 본다. `Machine`이 `0x8664`면 x64, `0x014c`면 x86(32비트)이다. `Subsystem`이 `IMAGE_SUBSYSTEM_WINDOWS_GUI`(2)면 GUI 프로그램, `IMAGE_SUBSYSTEM_WINDOWS_CUI`(3)면 콘솔 프로그램이다.

**3) DOS Header / NT Header 확인**

왼쪽 트리에서 `DOS Header`를 클릭해 `e_magic`(=`MZ`)과 `e_lfanew` 값을 본다. `NT Header → File Header`에서 `NumberOfSections`(섹션 개수), `TimeDateStamp`(컴파일 시각, 조작될 수 있으므로 참고용), `Characteristics`(exe인지 dll인지 등 플래그)를 확인한다.

**4) Optional Header 확인**

`AddressOfEntryPoint`(엔트리 포인트 RVA), `ImageBase`(선호 로드 주소), `SectionAlignment`/`FileAlignment`, `Subsystem`, `SizeOfImage` 등을 본다. `AddressOfEntryPoint` 값을 기억해두면 나중에 IDA/x64dbg에서 실제 코드가 시작하는 지점을 대조할 수 있다.

**5) Section Headers 확인**

왼쪽 트리의 `Section Headers`(또는 각 섹션 이름)를 하나씩 눌러 `VirtualAddress`, `VirtualSize`, `SizeOfRawData`, `Characteristics`(예: `IMAGE_SCN_MEM_EXECUTE`, `IMAGE_SCN_MEM_WRITE`)를 확인한다. 실행 가능(E)이면서 쓰기 가능(W)한 섹션이 있으면 자가 수정 코드(self-modifying code)나 언패킹 스텁을 의심할 수 있다.

**6) Import Table 확인**

왼쪽 트리에서 `Import Table`(또는 `Imports`)을 클릭한다. DLL별로 트리가 펼쳐지며 각 DLL 아래 함수 이름 목록이 보인다. `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, `VirtualProtect`, `CreateRemoteThread` 같은 이름이 있으면 안티디버깅/인젝션 관련 코드가 있을 가능성을 미리 점찍어둔다.

**7) Export Table 확인(있는 경우)**

DLL 파일이거나 익스포트를 제공하는 exe라면 `Export Table`에서 외부에 공개된 함수 이름과 순번(ordinal)을 확인한다.

**8) Hex Viewer로 원본 바이트 대조**

특정 필드 값이 실제 파일의 어느 바이트에 대응하는지 궁금하면, PE-bear 내장 Hex Viewer(대부분 하단이나 별도 탭)로 전환해 해당 오프셋의 raw byte를 직접 확인한다.

## 명령어/단축키
- `File → Open` : 파일 열기(드래그&드롭도 동일)
- 왼쪽 트리 클릭 : 각 헤더/섹션/디렉토리 상세 필드로 이동
- 상단 탭 전환 : General info / Hex Viewer / Disasm(간단 미리보기) 등 뷰 전환
- 특정 필드 더블클릭(버전에 따라) : 해당 값의 파일 오프셋으로 Hex Viewer가 자동 스크롤

## 출력 해석
- `NumberOfSections`가 파일 크기에 비해 지나치게 적다(2개뿐 등)면 패킹/난독화 의심.
- `AddressOfEntryPoint`가 `.text`가 아니라 이름 없는 섹션이나 쓰기 가능(W) 섹션 안에 있으면 언패킹 스텁일 가능성이 높다.
- Import Table에 함수가 거의 없거나(`kernel32.dll`의 `LoadLibraryA`/`GetProcAddress` 딱 2개뿐 등) 텅 비어 있으면, 실제 API는 실행 중에 `GetProcAddress`로 동적으로 찾아 쓰는 방식(REV-0129 참고)이거나 패킹되어 원래 import table이 감춰진 것이다.
- 섹션의 `SizeOfRawData`가 `VirtualSize`보다 훨씬 작으면(파일에는 조금만 있는데 메모리에서는 훨씬 크게 확보) 나머지는 실행 중 압축 해제되거나 0으로 채워지는 영역(예: `.bss` 역할)일 수 있다.

## 흔한 실수
- RVA와 파일 오프셋(Raw Offset)을 같은 값으로 착각해서 Hex Viewer에서 엉뚱한 위치를 보는 것 — 섹션 정렬(SectionAlignment)과 파일 정렬(FileAlignment)이 다르면 둘은 달라진다.
- Import Table이 비어 있는 것만 보고 "이 프로그램은 아무 API도 안 쓴다"고 단정하는 것 — 실제로는 동적 로딩(LoadLibrary/GetProcAddress)이나 패킹 때문일 수 있다.
- `TimeDateStamp`(컴파일 타임스탬프)를 무조건 신뢰하는 것 — 이 값은 링커가 자동으로 넣지만 쉽게 조작 가능하므로 참고 정보 정도로만 취급해야 한다.
- 섹션 이름만 보고 내용을 단정하는 것 — 섹션 이름은 관례일 뿐 강제 규칙이 아니어서, 악의적으로 `.text`처럼 보이게 이름 붙인 데이터 섹션이 있을 수도 있다.

## 막혔을 때 다음 체크
- 섹션 개수가 너무 적거나 이름이 낯설어 패킹이 의심되면 → REV-0126 Detect It Easy로 컴파일러/패커 확인
- 헤더 확인이 끝나고 실제 코드를 동적으로 따라가고 싶다면 → REV-0127 x64dbg로 EXE 첫 분석 시작
- Import Table에서 안티디버깅 관련 함수(`IsDebuggerPresent` 등)를 발견했다면 → REV-0130 IsDebuggerPresent 안티디버깅 식별
- 정적 분석을 더 깊게 이어가고 싶다면 → ../static-analysis/rev-0142-ida-first-open.md

## 미니 예제
64비트 콘솔 프로그램 `sample.exe`를 PE-bear로 여는 순서:

```text
1. File → Open → sample.exe 선택
2. General info 탭: Machine=0x8664(x64), Subsystem=CUI(콘솔), EntryPoint RVA=0x1450
3. NT Header → File Header: NumberOfSections=6
4. Section Headers: .text(실행), .rdata(읽기전용), .data(읽기/쓰기), .pdata, .rsrc, .reloc 확인
5. Import Table: KERNEL32.dll(CreateFileW, ReadFile, WriteFile...), USER32.dll(MessageBoxW) 등 확인
6. EntryPoint RVA 0x1450이 .text 섹션 범위(VirtualAddress~VirtualAddress+VirtualSize) 안에 있음을 확인 → 정상적인 컴파일 결과로 판단
```

## 관련 글
- REV-0126 — Detect It Easy로 컴파일러 패커 확인
- REV-0127 — x64dbg로 EXE 첫 분석 시작
- REV-0122 — Microsoft x64 Calling Convention
- REV-0142 — IDA에 바이너리 처음 열었을 때 해야 할 것

## 출처/검증
- PE 파일 구조(DOS Header, NT Headers, Section Table, Data Directories)는 Microsoft 공식 "PE Format" 문서(learn.microsoft.com, Windows PE and COFF Specification) 기준.
- PE-bear의 화면 구성과 트리 탐색 방식은 PE-bear 공식 GitHub 저장소(hasherezade/pe-bear) 및 배포된 GUI 동작을 기준으로 정리했다(2026-09-08 확인). 정확한 메뉴 위치/명칭은 버전에 따라 약간 다를 수 있다.
