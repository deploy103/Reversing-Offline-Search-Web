---
id: REV-0116
title: "PE Header COFF Optional Header 읽기"
slug: "rev-0116-pe-coff-optional-header"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", x64dbg]
keywords: ["IMAGE_NT_HEADERS", "FileHeader", "OptionalHeader", "COFF Header", "Machine", "NumberOfSections", "AddressOfEntryPoint", "ImageBase", "SectionAlignment", "FileAlignment", "DataDirectory"]
aliases: ["pe header 구조", "coff header란", "optional header란", "nt header 필드", "이미지베이스란"]
symptom_keywords: ["FileHeader와 OptionalHeader 차이를 모름", "AddressOfEntryPoint가 뭔지 모름", "ImageBase가 왜 필요한지 모름", "DataDirectory가 뭔지 모름", "SectionAlignment FileAlignment 차이를 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`IMAGE_NT_HEADERS`는 `PE\0\0` 시그니처, 아키텍처·섹션 개수를 담은 **COFF `FileHeader`**, 그리고 진입점 주소·ImageBase·정렬 값·DataDirectory 등 로더가 실제로 파일을 메모리에 매핑하는 데 필요한 거의 모든 정보를 담은 **`OptionalHeader`**로 구성되며, 이 두 헤더의 필드를 읽을 줄 알면 PE 파일의 아키텍처, 진입점, 로드 방식을 코드 한 줄 안 보고도 파악할 수 있다.

## 언제 검색해야 하나
- `FileHeader`와 `OptionalHeader`가 어떻게 다른지, 왜 굳이 나뉘어 있는지 궁금할 때
- `AddressOfEntryPoint`가 정확히 어떤 값(RVA인지 VA인지)을 담고 있는지 헷갈릴 때
- `ImageBase`, `SectionAlignment`, `FileAlignment` 같은 필드 이름은 봤는데 실제로 뭘 의미하는지 모를 때
- `DataDirectory` 배열이 Import/Export/Resource 테이블과 어떻게 연결되는지 궁금할 때
- IDA/PE-bear에서 본 헤더 필드 값을 근거로 "이 파일이 x86인지 x64인지, DLL인지 EXE인지"를 스스로 판단하고 싶을 때

## 핵심 개념

### IMAGE_NT_HEADERS의 3단 구조
`e_lfanew`(REV-0115 참고)가 가리키는 위치에 있는 `IMAGE_NT_HEADERS`(64비트 실행 파일이라면 실제로는 `IMAGE_NT_HEADERS64`)는 다음 세 부분으로 이뤄진다.

```c
typedef struct _IMAGE_NT_HEADERS64 {
    DWORD                   Signature;       // "PE\0\0" (0x00004550)
    IMAGE_FILE_HEADER       FileHeader;       // COFF Header, 20바이트
    IMAGE_OPTIONAL_HEADER64 OptionalHeader;   // PE32+에서 240바이트
} IMAGE_NT_HEADERS64;
```

`Signature`는 항상 4바이트 `50 45 00 00`("PE\0\0")이어야 하며, 이 값이 아니면 `e_lfanew`가 잘못된 위치를 가리키고 있거나 파일이 손상된 것이다.

### FileHeader (COFF Header) — "이 파일의 기본 스펙"
```c
typedef struct _IMAGE_FILE_HEADER {
    WORD  Machine;              // 대상 CPU 아키텍처
    WORD  NumberOfSections;     // 섹션 개수
    DWORD TimeDateStamp;        // 링크된 시각 (Unix epoch)
    DWORD PointerToSymbolTable; // 디버그 심볼 테이블 오프셋 (대개 0)
    DWORD NumberOfSymbols;      // 심볼 개수 (대개 0)
    WORD  SizeOfOptionalHeader; // 뒤에 오는 OptionalHeader의 크기
    WORD  Characteristics;      // 파일 특성 플래그
} IMAGE_FILE_HEADER;            // 총 20바이트
```

`FileHeader`는 원래 COFF(Common Object File Format)라는, PE 이전부터 있던 오브젝트 파일 포맷에서 그대로 가져온 구조체다. 실무에서 자주 보는 필드:

- **`Machine`** — 대상 아키텍처. `0x8664`는 x64(AMD64), `0x14C`는 x86(I386), `0x1C0`/`0xAA64`는 각각 ARM/ARM64다. IDA나 도구가 자동으로 32/64비트를 인식하는 근거가 바로 이 필드다.
- **`NumberOfSections`** — 뒤에 오는 Section Table(REV-0117)의 항목 개수. 이 값을 알아야 Section Table을 몇 번 반복해서 읽을지 알 수 있다.
- **`TimeDateStamp`** — 링커가 파일을 만든 시각. 리버싱에서는 이 값으로 "이 샘플이 언제 컴파일됐는지" 추정하는 용도로 자주 쓰인다(단, 재현 빌드나 의도적 조작으로 신뢰할 수 없는 경우도 있다).
- **`Characteristics`** — 이 파일의 성격을 나타내는 비트 플래그 모음. 대표적으로 `IMAGE_FILE_EXECUTABLE_IMAGE`(`0x0002`, 실행 가능한 이미지), `IMAGE_FILE_DLL`(`0x2000`, DLL 파일), `IMAGE_FILE_32BIT_MACHINE`(`0x0100`) 등이 있다. 이 플래그로 EXE와 DLL을 구분할 수 있다.

### OptionalHeader — 이름과 달리 사실상 필수
"Optional"이라는 이름은 COFF 오브젝트 파일(`.obj`)에서는 이 헤더가 없어도 되기 때문에 붙은 역사적인 이름일 뿐, 실행 가능한 PE(EXE/DLL)에서는 항상 존재하고 로더가 실제로 참조하는 가장 중요한 정보 대부분이 여기 담겨 있다. PE32+(64비트) 기준 주요 필드는 다음과 같다.

```c
typedef struct _IMAGE_OPTIONAL_HEADER64 {
    WORD    Magic;                    // 0x20B (PE32+) / 0x10B (PE32)
    BYTE    MajorLinkerVersion;
    BYTE    MinorLinkerVersion;
    DWORD   SizeOfCode;
    DWORD   SizeOfInitializedData;
    DWORD   SizeOfUninitializedData;
    DWORD   AddressOfEntryPoint;      // ★ 진입점의 RVA
    DWORD   BaseOfCode;
    ULONGLONG ImageBase;              // ★ 선호 로드 베이스 주소 (PE32+는 8바이트)
    DWORD   SectionAlignment;         // ★ 메모리상 섹션 정렬 단위 (보통 0x1000)
    DWORD   FileAlignment;            // ★ 파일상 섹션 정렬 단위 (보통 0x200)
    WORD    MajorOperatingSystemVersion;
    WORD    MinorOperatingSystemVersion;
    WORD    MajorImageVersion;
    WORD    MinorImageVersion;
    WORD    MajorSubsystemVersion;
    WORD    MinorSubsystemVersion;
    DWORD   Win32VersionValue;
    DWORD   SizeOfImage;              // 메모리에 로드됐을 때 전체 이미지 크기
    DWORD   SizeOfHeaders;            // 헤더 전체(DOS+NT+Section Table) 크기
    DWORD   CheckSum;
    WORD    Subsystem;                // GUI(2) / CUI(3) / 드라이버 등
    WORD    DllCharacteristics;       // ASLR/DEP 등 보안 관련 플래그
    ULONGLONG SizeOfStackReserve;
    ULONGLONG SizeOfStackCommit;
    ULONGLONG SizeOfHeapReserve;
    ULONGLONG SizeOfHeapCommit;
    DWORD   LoaderFlags;
    DWORD   NumberOfRvaAndSizes;      // DataDirectory 배열 항목 개수 (보통 16)
    IMAGE_DATA_DIRECTORY DataDirectory[16]; // ★ Import/Export/Resource 등 위치 테이블
} IMAGE_OPTIONAL_HEADER64;
```

핵심 필드를 하나씩 짚어보면 다음과 같다.

**`AddressOfEntryPoint`** — 프로그램 실행이 시작되는 지점의 주소를, **RVA(Relative Virtual Address)**로 저장한다. 절대 VA가 아니다. 이 값에 `ImageBase`를 더해야 실제 로드 시점의 절대 가상 주소가 나온다(`VA = ImageBase + RVA`, 자세한 계산은 REV-0118). 이 주소는 `main`이나 `WinMain`이 아니라 C 런타임 초기화 코드(`CRT startup`)의 시작 지점이다(REV-0121에서 자세히 다룸).

**`ImageBase`** — 로더가 이 이미지를 메모리에 올릴 때 "선호하는" 시작 주소. EXE는 관례적으로 `0x140000000`(64비트) 또는 `0x00400000`(32비트), DLL은 `0x180000000`(64비트) 또는 `0x10000000`(32비트) 근처 값을 흔히 쓴다. 다만 ASLR(Address Space Layout Randomization)이 켜져 있으면 실제 로드 주소는 매 실행마다 이 값과 다르게 랜덤화된다 — `ImageBase`는 어디까지나 "재배치가 필요 없다면 이 주소에 올리고 싶다"는 희망값이다.

**`SectionAlignment` / `FileAlignment`** — 각 섹션이 메모리에서는 `SectionAlignment`(보통 `0x1000`, 즉 한 페이지 크기) 단위로, 파일에서는 `FileAlignment`(보통 `0x200`) 단위로 정렬되어 배치된다는 규칙이다. 이 둘이 다르기 때문에 같은 섹션이라도 메모리상 크기(`VirtualSize`)와 파일상 크기(`SizeOfRawData`)가 다를 수 있다 — 이 차이가 바로 RVA↔파일오프셋 변환이 단순 뺄셈 하나로 끝나지 않고 섹션별 정렬을 고려해야 하는 이유다.

**`Subsystem`** — 이 실행 파일이 어떤 서브시스템을 대상으로 하는지. `IMAGE_SUBSYSTEM_WINDOWS_GUI`(2)면 GUI 프로그램(`WinMain` 진입), `IMAGE_SUBSYSTEM_WINDOWS_CUI`(3)면 콘솔 프로그램(`main` 진입)이다. 이 값으로 링커가 `WinMainCRTStartup`을 쓸지 `mainCRTStartup`을 쓸지가 정해진다(REV-0121 참고).

**`DataDirectory[16]`** — 이 필드가 사실상 PE 리버싱에서 가장 실용적인 배열이다. 각 항목은 `IMAGE_DATA_DIRECTORY { DWORD VirtualAddress; DWORD Size; }` 구조로, "어떤 종류의 부가 정보(Import Table, Export Table, Resource, Relocation, TLS, Debug 등)가 RVA 몇 번지에 몇 바이트 크기로 있는지"를 알려준다. 주요 인덱스:

```
DataDirectory[0]  IMAGE_DIRECTORY_ENTRY_EXPORT     — Export Table
DataDirectory[1]  IMAGE_DIRECTORY_ENTRY_IMPORT     — Import Table
DataDirectory[2]  IMAGE_DIRECTORY_ENTRY_RESOURCE   — 리소스(.rsrc)
DataDirectory[5]  IMAGE_DIRECTORY_ENTRY_BASERELOC  — 재배치 테이블
DataDirectory[9]  IMAGE_DIRECTORY_ENTRY_TLS        — Thread Local Storage
DataDirectory[12] IMAGE_DIRECTORY_ENTRY_IAT        — Import Address Table
```

예를 들어 Import Table을 직접 찾고 싶다면 `DataDirectory[1].VirtualAddress`를 RVA→파일오프셋으로 변환한 위치로 가면 된다(REV-0119에서 실습).

## 화면/코드에서 보이는 징후
- PE-bear에서 `NT Headers` → `File Header` 탭에 `Machine`, `NumberOfSections`, `Characteristics`가 표로 보임
- 같은 화면 `Optional Header` 탭에 `AddressOfEntryPoint`, `ImageBase`, `SectionAlignment`, `FileAlignment`, `Subsystem`이 나열됨
- PE-bear 좌측 트리의 `Data Directories` 항목을 클릭하면 16개 항목이 `Import Table`, `Export Table` 등 이름과 함께 RVA/Size로 표시됨
- IDA가 파일을 로드하면서 대화상자에 "PE\0\0", 프로세서 종류(metapc), 진입점 주소를 자동으로 표시

## 가장 먼저 할 것
`FileHeader.Machine`으로 아키텍처(x86/x64)를 먼저 확정하고, `OptionalHeader.Magic`으로 PE32/PE32+를 재확인한다(둘이 서로 모순되면 파일이 이상한 것이다). 그다음 `AddressOfEntryPoint`와 `ImageBase`를 적어두고, `DataDirectory` 배열에서 Import Table(`[1]`) 항목의 `VirtualAddress`가 `0`이 아닌지 확인한다 — `0`이면 이 파일이 외부 DLL에 전혀 의존하지 않는 특이한 파일(혹은 정적 링크되었거나 헤더가 조작된 파일)이라는 뜻이므로 주의 깊게 봐야 한다.

## 단계별 절차

**1) FileHeader 읽기 (PE-bear)**
```text
좌측 트리 → NT Headers → File Header 클릭
Machine, NumberOfSections, TimeDateStamp, Characteristics 확인
```

**2) OptionalHeader 읽기**
```text
좌측 트리 → NT Headers → Optional Header 클릭
Magic, AddressOfEntryPoint, ImageBase, SectionAlignment, FileAlignment, Subsystem 확인
```

**3) DataDirectory에서 원하는 테이블 위치 찾기**
```text
좌측 트리 → Data Directories 클릭
"Import Table" 행의 VirtualAddress, Size 확인
"Export Table" 행의 VirtualAddress, Size 확인 (0이면 이 파일은 함수를 export하지 않음)
```

**4) 헥스에디터로 직접 오프셋 계산해서 검증(선택)**
`e_lfanew`가 가리키는 위치부터 4바이트(Signature) + 20바이트(FileHeader) 만큼 뒤로 이동하면 `OptionalHeader`가 시작한다. `AddressOfEntryPoint`는 `OptionalHeader` 시작 지점에서 오프셋 `0x10`에 있다(`Magic` 2바이트 + `MajorLinkerVersion` 1바이트 + `MinorLinkerVersion` 1바이트 + `SizeOfCode` 4바이트 + `SizeOfInitializedData` 4바이트 + `SizeOfUninitializedData` 4바이트 = 16바이트 뒤).

## 명령어/단축키
```text
PE-bear: 좌측 트리에서 NT Headers → File Header / Optional Header / Data Directories 클릭
IDA: View → Open subviews → Structures 에서 IMAGE_NT_HEADERS 정의 확인 가능
x64dbg: 우클릭 → Follow in Memory Map으로 ImageBase 확인
```

## 출력 해석
- `Machine == 0x8664` → x64, `Machine == 0x14C` → x86
- `Magic == 0x20B`(PE32+)인데 `Machine == 0x14C`(x86)처럼 서로 모순되면 파일이 손상됐거나 조작된 것
- `Characteristics`에 `IMAGE_FILE_DLL`(`0x2000`) 비트가 있으면 DLL, 없고 `IMAGE_FILE_EXECUTABLE_IMAGE`(`0x0002`)만 있으면 EXE
- `DataDirectory[1].VirtualAddress == 0`이면 이 파일은 Import Table이 없는 것 — 실행 파일치고는 드문 경우이므로 패킹/난독화 가능성을 의심
- `Subsystem == 2`면 GUI 프로그램(`WinMainCRTStartup`), `Subsystem == 3`이면 콘솔 프로그램(`mainCRTStartup`)

## 흔한 실수
- `AddressOfEntryPoint`를 절대 주소(VA)로 착각해서 그대로 IDA 주소창에 입력하는 것 — 이 값은 RVA이므로 `ImageBase`를 더해야 실제 VA가 나온다(REV-0118 참고).
- `FileAlignment`와 `SectionAlignment`가 항상 같은 값이라고 가정하는 것 — 대부분의 실행 파일에서 `FileAlignment`는 `0x200`, `SectionAlignment`는 `0x1000`으로 다르다. 이 차이 때문에 RVA→파일오프셋 변환이 단순히 같은 값을 빼고 더하는 것으로 끝나지 않는다.
- `NumberOfSections` 값을 무시하고 무작정 Section Table을 읽다가 실제 섹션 개수보다 많거나 적게 읽는 것.
- `DataDirectory` 배열의 인덱스 순서를 외우지 못해서 Export를 찾아야 하는데 Import(`[1]`) 항목을 잘못 읽는 것 — Export는 `[0]`, Import는 `[1]`이다.
- COFF `FileHeader`의 `TimeDateStamp`를 무조건 신뢰해서 "이 샘플은 이 날짜에 만들어졌다"고 단정하는 것 — 재현 가능 빌드(reproducible build)나 악성코드의 경우 이 값이 의도적으로 조작되거나 고정값(예: 0)으로 설정될 수 있다.

## 막혔을 때 다음 체크
- `e_lfanew`가 가리키는 위치 자체가 헷갈리면 → [REV-0115 DOS Header와 MZ 시그니처](./rev-0115-dos-header.md)
- `NumberOfSections` 뒤에 오는 실제 섹션 테이블 구조가 궁금하면 → [REV-0117 PE Section Table 읽기](./rev-0117-pe-section-table.md)
- `AddressOfEntryPoint`를 실제 파일 오프셋으로 변환하는 계산이 필요하면 → [REV-0118 RVA VA Raw Offset 계산](./rev-0118-rva-va-raw-offset.md)
- `DataDirectory[1]`이 가리키는 Import Table을 실제로 파싱하고 싶으면 → [REV-0119 Import Table에서 중요한 API 찾기](./rev-0119-import-table.md)
- 진입점에서 `main`/`WinMain`까지 코드 흐름이 궁금하면 → [REV-0121 Entry Point와 WinMain 찾기](./rev-0121-entry-point-winmain.md)
- ELF의 대응 구조(Program Header/Section Header)와 비교하고 싶으면 → [ELF Program Header와 Section Header 차이](../linux-elf/rev-0090-program-vs-section-header.md)

## 미니 예제
64비트 EXE 하나를 PE-bear로 열었더니 다음과 같이 나왔다고 하자.

```text
FileHeader:
  Machine = 0x8664 (x64)
  NumberOfSections = 6
  Characteristics = 0x0022 (EXECUTABLE_IMAGE | LARGE_ADDRESS_AWARE)

OptionalHeader:
  Magic = 0x20B (PE32+)
  AddressOfEntryPoint = 0x1A3D0
  ImageBase = 0x140000000
  SectionAlignment = 0x1000
  FileAlignment = 0x200
  Subsystem = 3 (WINDOWS_CUI, 콘솔 프로그램)

DataDirectory[1] (Import Table): VirtualAddress = 0x2C000, Size = 0x140
DataDirectory[0] (Export Table): VirtualAddress = 0x0,     Size = 0x0
```

이 정보만으로 다음을 즉시 알 수 있다: (1) 64비트 콘솔 프로그램이다(`Subsystem == 3`), (2) 진입점의 실제 VA는 `0x140000000 + 0x1A3D0 = 0x14001A3D0`, (3) Import Table이 RVA `0x2C000`에 `0x140`바이트 크기로 존재하므로 이 파일은 외부 DLL 함수를 가져다 쓰는 평범한 실행 파일이다, (4) Export Table이 없으므로(`VirtualAddress == 0`) 이 파일은 다른 프로그램에 함수를 제공하지 않는다 — 즉 DLL이 아니라 일반 EXE라는 정황과도 일치한다.

## 관련 글
- REV-0115 — DOS Header와 MZ 시그니처
- REV-0114 — PE 파일 구조 한 번에 보기
- REV-0117 — PE Section Table 읽기
- REV-0118 — RVA VA Raw Offset 계산
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0121 — Entry Point와 WinMain 찾기
- REV-0090 — ELF Program Header와 Section Header 차이

## 출처/검증
- `IMAGE_NT_HEADERS`, `IMAGE_FILE_HEADER`, `IMAGE_OPTIONAL_HEADER64` 구조체 필드 정의: Microsoft Learn "PE Format" 공식 문서 기준 (2026-09-08 검증).
- `DataDirectory` 인덱스별 의미(`IMAGE_DIRECTORY_ENTRY_*` 상수): Microsoft Learn "PE Format" 문서 및 `winnt.h` 정의 기준.
- `Machine`, `Characteristics`, `Subsystem` 상수 값: Microsoft Learn "PE Format" 문서의 해당 열거값 목록 기준.
