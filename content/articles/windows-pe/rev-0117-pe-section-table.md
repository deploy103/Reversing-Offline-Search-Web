---
id: REV-0117
title: "PE Section Table 읽기"
slug: "rev-0117-pe-section-table"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", x64dbg]
keywords: ["IMAGE_SECTION_HEADER", "Section Table", "VirtualAddress", "VirtualSize", "SizeOfRawData", "PointerToRawData", "Characteristics", "IMAGE_SCN_MEM_EXECUTE", "IMAGE_SCN_MEM_WRITE", "IMAGE_SCN_MEM_READ"]
aliases: ["섹션 테이블이란", "pe 섹션 헤더 구조", "virtualsize sizeofrawdata 차이", "섹션 권한 플래그"]
symptom_keywords: ["섹션이 몇 개인지 어떻게 아는지 모름", "VirtualSize와 SizeOfRawData가 왜 다른지 모름", "섹션이 실행가능한지 어떻게 확인하는지 모름", "이상한 섹션 이름을 봤는데 뭔지 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Section Table은 `IMAGE_NT_HEADERS` 바로 뒤에 `FileHeader.NumberOfSections`개만큼 이어지는 40바이트짜리 `IMAGE_SECTION_HEADER` 배열로, 각 섹션이 "메모리 어디에(`VirtualAddress`/`VirtualSize`), 파일 어디에(`PointerToRawData`/`SizeOfRawData`), 어떤 권한(`Characteristics`)으로" 존재하는지를 알려주는 PE 파일의 진짜 지도다.

## 언제 검색해야 하나
- IDA의 Segments 창에 나오는 `.text`, `.rdata`, `.data` 같은 섹션이 실제로 헤더 어디에서 파싱된 정보인지 궁금할 때
- 어떤 섹션이 실행 가능한지, 쓰기 가능한지를 코드가 아니라 헤더 값만으로 판단하고 싶을 때
- `VirtualSize`와 `SizeOfRawData`가 서로 다른 값으로 나와서 당황했을 때
- 패킹된 파일에서 `UPX0`, `UPX1`처럼 낯선 섹션 이름을 봤을 때 이게 정상인지 판단하고 싶을 때
- RVA를 파일 오프셋으로 변환하기 전에, 그 RVA가 어느 섹션에 속하는지부터 찾아야 할 때

## 핵심 개념

### IMAGE_SECTION_HEADER 구조체
Section Table은 `IMAGE_NT_HEADERS`(정확히는 `OptionalHeader`) 바로 다음, 파일 오프셋으로 `e_lfanew + 4(Signature) + 20(FileHeader) + FileHeader.SizeOfOptionalHeader` 위치에서 시작한다. 이 위치부터 `NumberOfSections`개의 `IMAGE_SECTION_HEADER`가 각각 40바이트씩 연속으로 나열된다.

```c
typedef struct _IMAGE_SECTION_HEADER {
    BYTE  Name[8];                  // 섹션 이름 (널 종료 안 될 수도 있음, 최대 8글자)
    union {
        DWORD PhysicalAddress;
        DWORD VirtualSize;           // ★ 메모리에 로드됐을 때 실제 크기
    } Misc;
    DWORD VirtualAddress;            // ★ 메모리 로드 시 RVA (SectionAlignment 배수)
    DWORD SizeOfRawData;             // ★ 파일에 저장된 크기 (FileAlignment 배수로 반올림)
    DWORD PointerToRawData;          // ★ 파일에서 이 섹션 데이터가 시작하는 오프셋
    DWORD PointerToRelocations;      // 오브젝트 파일(.obj)용, 실행 파일에서는 보통 0
    DWORD PointerToLinenumbers;      // 사용 안 함(레거시)
    WORD  NumberOfRelocations;       // 오브젝트 파일용, 실행 파일에서는 보통 0
    WORD  NumberOfLinenumbers;       // 사용 안 함(레거시)
    DWORD Characteristics;           // ★ 권한/속성 플래그
} IMAGE_SECTION_HEADER;              // 총 40바이트
```

### 핵심 필드 4종 세트
**`Name[8]`** — 섹션 이름. 최대 8바이트이고, 8글자를 꽉 채우면 널 종료 바이트가 없을 수 있다. `.text`, `.data`, `.rdata`, `.rsrc`, `.reloc`, `.pdata`(64비트 예외 처리 테이블) 등이 컴파일러/링커가 관례적으로 붙이는 이름이지만, **이 이름 자체는 로더 동작에 아무 영향도 주지 않는 단순 라벨**이다. 로더가 실제로 참조하는 건 이름이 아니라 아래 `Characteristics` 플래그다. 그래서 패커들은 종종 원래 섹션 이름을 지우거나 `UPX0`, `UPX1`, `.aspack` 같은 자체 이름으로 바꾼다 — 이것만으로 패킹 여부를 짐작할 수 있는 단서가 된다.

**`VirtualAddress` / `Misc.VirtualSize`** — 이 섹션이 프로세스 메모리에 로드됐을 때, 이미지 시작(ImageBase)으로부터 상대적인 시작 위치(RVA)와 그 크기. `VirtualAddress`는 항상 `OptionalHeader.SectionAlignment`(보통 `0x1000`)의 배수로 정렬된다.

**`SizeOfRawData` / `PointerToRawData`** — 이 섹션의 실제 바이트가 **디스크 파일 안에** 저장된 크기와 시작 오프셋. `PointerToRawData`는 `OptionalHeader.FileAlignment`(보통 `0x200`)의 배수로 정렬된다.

**`Characteristics`** — 이 섹션이 실행 가능한지, 쓰기 가능한지, 읽기 가능한지를 나타내는 비트 플래그의 조합. 자주 보는 값:

```
IMAGE_SCN_CNT_CODE               0x00000020  // 실행 코드를 담고 있음
IMAGE_SCN_CNT_INITIALIZED_DATA   0x00000040  // 초기화된 데이터를 담고 있음
IMAGE_SCN_CNT_UNINITIALIZED_DATA 0x00000080  // 미초기화 데이터(.bss 유사)
IMAGE_SCN_MEM_EXECUTE            0x20000000  // 실행 가능
IMAGE_SCN_MEM_READ               0x40000000  // 읽기 가능
IMAGE_SCN_MEM_WRITE              0x80000000  // 쓰기 가능
```

예를 들어 `.text` 섹션의 전형적인 `Characteristics` 값은 `0x60000020`(`CNT_CODE | MEM_EXECUTE | MEM_READ`)이고, `.data` 섹션은 흔히 `0xC0000040`(`CNT_INITIALIZED_DATA | MEM_READ | MEM_WRITE`)이다. **읽기+쓰기+실행이 모두 켜진 섹션(`0xE0000020`류)은 정상적인 컴파일러 출력에서는 드물고, 자가 수정 코드(self-modifying code)나 언패킹 스텁을 쓰는 패커/프로텍터에서 흔히 보인다** — 이런 섹션을 발견하면 언패킹이 필요한 파일일 가능성을 의심해야 한다.

### VirtualSize와 SizeOfRawData가 다른 이유
이 둘은 종종 다른 값을 갖는데, 크게 두 가지 이유가 있다.

1. **정렬 배수가 다르다.** `VirtualAddress`/`VirtualSize`는 `SectionAlignment`(예: `0x1000`) 기준, `PointerToRawData`/`SizeOfRawData`는 `FileAlignment`(예: `0x200`) 기준으로 반올림되므로, 같은 실제 데이터량이라도 두 값이 다른 배수로 반올림되어 서로 다르게 나온다.
2. **미초기화 데이터(`.bss` 유사 영역)가 있다.** 예를 들어 전역 배열을 `0`으로만 초기화하는 코드가 많으면, 컴파일러는 그 배열을 파일에 실제 바이트로 저장하지 않고 "메모리에 로드할 때 이만큼 공간을 확보하고 0으로 채워라"라는 크기 정보만 남긴다. 이 경우 `VirtualSize`가 `SizeOfRawData`보다 훨씬 클 수 있다.

이 때문에 어떤 RVA가 특정 섹션에 속하는지 판단할 때는 `VirtualSize`(메모리 기준 범위)를 써야 하고, 그 RVA를 파일 오프셋으로 변환할 때는 `PointerToRawData`(파일 기준 시작점)를 써야 한다 — 이 두 값을 섞어 쓰면 계산이 틀어진다. 구체적인 변환 공식과 예제는 [REV-0118 RVA VA Raw Offset 계산](./rev-0118-rva-va-raw-offset.md)에서 다룬다.

### 섹션이 겹치거나 파일 크기를 넘어서면
정상적인 PE라면 섹션들은 RVA 기준으로 서로 겹치지 않고 순서대로 배치된다. 하지만 의도적으로 조작된 파일(안티 리버싱, 특정 도구의 자동 파싱을 방해하려는 목적)에서는 `PointerToRawData`가 파일 실제 크기를 넘어서거나, `SizeOfRawData`가 비정상적으로 큰 값으로 설정되어 순진한 파서를 오작동시키는 경우가 있다. IDA나 PE-bear 같은 성숙한 도구는 이런 경우를 보정해서 보여주지만, 직접 파서를 짤 때는 이런 예외 상황을 방어적으로 처리해야 한다.

## 화면/코드에서 보이는 징후
- PE-bear 좌측 트리의 `Section Headers`를 클릭하면 각 섹션이 한 행씩, `Name/VirtualAddress/VirtualSize/PointerToRawData/SizeOfRawData/Characteristics` 컬럼을 가진 표로 나옴
- IDA의 Segments 창(`Shift+F7` 대응 뷰)에 `.text`, `.rdata` 등이 나열되고, 각 세그먼트의 시작/끝 주소, 권한(R/W/X)이 함께 표시됨
- 섹션 이름이 표준(`.text`, `.data`, `.rdata`, `.rsrc`, `.reloc`)이 아니라 `UPX0`, `UPX1`, `.aspack`, `.vmp0` 등으로 나오면 패킹/프로텍션 도구 사용 정황

## 가장 먼저 할 것
Section Table을 확인할 때는 반드시 `Characteristics` 플래그부터 본다. `.text`처럼 보이는 이름이라도 실제로 `IMAGE_SCN_MEM_EXECUTE`가 꺼져 있으면 그 섹션은 실행되지 않는다(이름만 관례일 뿐 강제성이 없다는 걸 다시 상기하자). 그리고 RWX(읽기+쓰기+실행)가 모두 켜진 섹션이 있는지 훑어본다 — 있다면 패킹/자가수정코드 가능성을 염두에 두고 분석 전략을 조정한다.

## 단계별 절차

**1) 섹션 개수 확인**
`FileHeader.NumberOfSections` 값을 REV-0116에서 이미 확인했다면 그 값만큼 섹션이 나열되어 있는지 확인한다.

**2) PE-bear로 Section Headers 표 보기**
```text
좌측 트리 → Section Headers 클릭
각 행의 Name, VirtualAddress, VirtualSize, PointerToRawData, SizeOfRawData, Characteristics 확인
```

**3) 각 섹션의 권한을 Characteristics로 직접 판단**
```text
0x60000020 = CNT_CODE | MEM_EXECUTE | MEM_READ           → 코드 섹션(.text 전형)
0xC0000040 = CNT_INITIALIZED_DATA | MEM_READ | MEM_WRITE   → 쓰기 가능 데이터 섹션(.data 전형)
0x40000040 = CNT_INITIALIZED_DATA | MEM_READ               → 읽기 전용 데이터 섹션(.rdata 전형)
0xE0000020 = CNT_CODE | MEM_EXECUTE | MEM_READ | MEM_WRITE → 이례적, 패커/자가수정코드 의심
```

**4) 특정 RVA가 속한 섹션 찾기**
```text
조건: Section.VirtualAddress <= RVA < Section.VirtualAddress + Section.VirtualSize
```
이 조건을 만족하는 섹션을 순서대로 찾아서 확인한다. 자세한 변환은 REV-0118 참고.

## 명령어/단축키
```text
PE-bear: 좌측 트리 → Section Headers
IDA: Segments 창에서 각 세그먼트 우클릭 → Edit Segment로 권한(R/W/X) 확인/수정
x64dbg: Memory Map 창(Alt+M)에서 로드된 이미지의 각 섹션 권한을 실시간으로 확인
```

## 출력 해석
- `Characteristics`에 `IMAGE_SCN_MEM_EXECUTE`(`0x20000000`)가 없는데 IDA가 그 섹션을 코드로 잘못 디스어셈블한다면 실제로는 데이터일 가능성이 높으므로 주의
- `VirtualSize > SizeOfRawData`가 크게 차이 나면 그 섹션 뒷부분은 파일에 실제 데이터 없이 로드 시 0으로 채워지는 영역(미초기화 데이터)일 가능성이 높음
- `PointerToRawData`가 `0`이면서 `Characteristics`에 `IMAGE_SCN_CNT_UNINITIALIZED_DATA`가 있으면 이 섹션은 파일에 실제 바이트를 전혀 갖지 않는 순수 `.bss` 유사 섹션
- 섹션 이름이 비표준이거나(`UPX0` 등), 섹션 개수가 비정상적으로 적으면(예: 2~3개) 패킹된 파일일 가능성이 매우 높음

## 흔한 실수
- 섹션 이름만 보고 그 섹션의 실제 권한/용도를 판단하는 것 — 반드시 `Characteristics` 플래그로 재확인해야 한다. 패커는 이름을 자유롭게 바꿀 수 있다.
- `VirtualSize`와 `SizeOfRawData`를 같은 의미로 혼용하는 것 — RVA 범위 판정에는 `VirtualSize`, 파일 오프셋 계산에는 `SizeOfRawData`/`PointerToRawData`를 써야 한다.
- 특정 RVA가 속한 섹션을 찾을 때 아무 섹션이나 골라서 계산하는 것 — 반드시 `VirtualAddress <= RVA < VirtualAddress + VirtualSize` 조건을 만족하는 섹션을 먼저 찾아야 한다.
- `Name` 필드가 8바이트를 꽉 채운 경우 널 종료가 없을 수 있다는 걸 모르고 문자열 파싱 코드에서 버퍼 오버런을 내는 것(직접 파서를 짤 때 흔한 버그).
- `PointerToRelocations`, `NumberOfRelocations` 같은 필드를 실행 파일에서도 의미 있는 값으로 기대하는 것 — 이 필드들은 링크되지 않은 오브젝트 파일(`.obj`)용이며 최종 실행 파일에서는 보통 `0`이다.

## 막혔을 때 다음 체크
- 이 Section Table이 헤더 전체에서 어느 위치에 있는지 큰 그림이 헷갈리면 → [REV-0114 PE 파일 구조 한 번에 보기](./rev-0114-pe-overview.md)
- `NumberOfSections`, `SectionAlignment`, `FileAlignment`가 정의된 상위 헤더가 궁금하면 → [REV-0116 PE Header COFF Optional Header 읽기](./rev-0116-pe-coff-optional-header.md)
- 특정 RVA를 실제 파일 오프셋으로 변환하는 전체 계산 절차가 필요하면 → [REV-0118 RVA VA Raw Offset 계산](./rev-0118-rva-va-raw-offset.md)
- ELF의 대응 개념(Section Header, `sh_flags`)과 비교하고 싶으면 → [ELF Program Header와 Section Header 차이](../linux-elf/rev-0090-program-vs-section-header.md)
- VA/RVA/파일오프셋의 일반 개념 자체가 헷갈리면 → [주소 VA RVA File Offset 차이](../binary-basics/rev-0028-va-rva-offset.md)

## 미니 예제
64비트 EXE 하나의 Section Table을 PE-bear로 확인했더니 다음과 같았다.

```text
Name    VirtualAddress  VirtualSize  PointerToRawData  SizeOfRawData  Characteristics
.text   0x1000          0x18F30      0x400             0x19000        0x60000020
.rdata  0x1A000         0x9C50       0x19400           0x9E00         0x40000040
.data   0x25000         0x2140       0x22C00            0x1000         0xC0000040
.pdata  0x28000         0xA5C        0x23C00            0xC00          0x40000040
.rsrc   0x2A000         0x4A0        0x24800            0x600          0x40000040
.reloc  0x2B000         0x28         0x24E00            0x200          0x42000040
```

여기서 `.text`는 `VirtualAddress=0x1000`부터 `0x1000+0x18F30=0x19F30`까지의 RVA 범위를 차지하고, `Characteristics=0x60000020`이므로 `CNT_CODE | MEM_EXECUTE | MEM_READ` — 정상적인 실행 코드 섹션이다. `.data`는 `VirtualSize(0x2140)`가 `SizeOfRawData(0x1000)`보다 크다 — 이는 이 섹션 뒷부분(`0x1000`~`0x2140` 구간)이 파일에는 저장되지 않고 로드 시 0으로 채워지는 미초기화 영역을 포함한다는 뜻이다.

## 관련 글
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0114 — PE 파일 구조 한 번에 보기
- REV-0118 — RVA VA Raw Offset 계산
- REV-0090 — ELF Program Header와 Section Header 차이
- REV-0028 — 주소 VA RVA File Offset 차이

## 출처/검증
- `IMAGE_SECTION_HEADER` 구조체 필드 정의: Microsoft Learn "PE Format" 공식 문서 기준 (2026-09-08 검증).
- `IMAGE_SCN_*` `Characteristics` 플래그 값: Microsoft Learn "PE Format" 문서의 Section Flags 표 기준.
- 정렬(`SectionAlignment`/`FileAlignment`)과 `VirtualSize`/`SizeOfRawData` 차이의 실무적 의미: PE Format 공식 문서 및 다수 리버싱 참고자료 공통 설명 기준.
