---
id: REV-0524
title: "PE Optional Header 필드 전체 사전"
slug: "rev-0524-pe-optional-header-fields"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, PE-bear]
keywords: ["IMAGE_OPTIONAL_HEADER", "AddressOfEntryPoint", "ImageBase", "SectionAlignment", "FileAlignment", "DataDirectory", "Subsystem", "DllCharacteristics"]
aliases: ["옵셔널 헤더 필드", "PE32 PE32+ 헤더 필드", "데이터 디렉터리 목록"]
symptom_keywords: ["옵셔널 헤더 필드가 뭔지 모르겠다", "AddressOfEntryPoint 위치를 모르겠다", "DataDirectory 배열이 뭔지 모르겠다", "Subsystem 값 의미를 모르겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`IMAGE_OPTIONAL_HEADER`(PE32는 32비트, PE32+는 64비트 변형)는 이름과 달리 실제로는 로더가 이미지를 메모리에 올리는 데 필요한 필수 정보(진입점, 이미지 베이스, 섹션/파일 정렬, 서브시스템, 16개 데이터 디렉터리)를 담은 핵심 구조체이며, PE-bear나 IDA의 헤더 뷰에서 이 필드들의 이름과 의미를 바로 찾을 수 있어야 정적 분석 초반 단계를 빠르게 지나갈 수 있다.

## 언제 검색해야 하나
- PE-bear나 IDA에서 옵셔널 헤더 필드를 하나씩 보다가 이름은 아는데 정확히 무슨 뜻인지 헷갈릴 때
- `AddressOfEntryPoint`, `ImageBase`, `SectionAlignment`, `FileAlignment` 등 특정 필드 하나의 의미와 계산법이 궁금할 때
- `DataDirectory` 배열의 16개 항목이 각각 무엇을 가리키는지(Export, Import, Resource, TLS 등) 확인해야 할 때
- PE32(32비트)와 PE32+(64비트) 옵셔널 헤더의 필드 차이(어떤 필드가 4바이트에서 8바이트로 바뀌는지)를 확인해야 할 때

## 핵심 개념
`IMAGE_OPTIONAL_HEADER`는 COFF 파일 헤더(`IMAGE_FILE_HEADER`) 바로 뒤, 섹션 테이블(REV-0117) 바로 앞에 위치한다. `Magic` 필드 값(`0x10B`=PE32, `0x20B`=PE32+)으로 32/64비트 여부를 판별하며(REV-0116에서 이미 다룬 COFF/옵셔널 헤더 기본 개념 참고), 이 문서는 그 필드들을 표로 정리한다.

**표준 필드(Standard Fields, COFF 계열)**

| 필드 | 크기 | 의미 |
|---|---|---|
| `Magic` | 2 | `0x10B`=PE32, `0x20B`=PE32+, `0x107`=ROM |
| `MajorLinkerVersion`/`MinorLinkerVersion` | 1+1 | 링커 버전 |
| `SizeOfCode` | 4 | 코드 섹션 총 크기(파일 정렬 기준 합) |
| `SizeOfInitializedData` | 4 | 초기화된 데이터 섹션 총 크기 |
| `SizeOfUninitializedData` | 4 | `.bss` 등 초기화 안 된 데이터 총 크기 |
| `AddressOfEntryPoint` | 4 | 진입점의 RVA(REV-0121에서 다룬 EP) — EXE는 CRT 시작 함수, DLL은 `DllMain` |
| `BaseOfCode` | 4 | 코드 섹션 시작 RVA |
| `BaseOfData` | 4(PE32만) | 데이터 섹션 시작 RVA — PE32+에는 이 필드가 없음(제거됨) |

**Windows 전용 필드(Windows-Specific Fields)**

| 필드 | 크기(PE32/PE32+) | 의미 |
|---|---|---|
| `ImageBase` | 4/8 | 로더가 선호하는 이미지 로드 시작 VA(EXE 기본값 `0x00400000`, DLL 기본값 `0x10000000`) |
| `SectionAlignment` | 4 | 메모리에 로드될 때 섹션의 정렬 단위(기본 `0x1000`, 페이지 크기) |
| `FileAlignment` | 4 | 디스크 파일에서 섹션 raw 데이터의 정렬 단위(기본 `0x200`) — `SectionAlignment`보다 항상 작거나 같다 |
| `MajorOperatingSystemVersion`/`Minor...` | 2+2 | 요구 OS 버전 |
| `MajorImageVersion`/`Minor...` | 2+2 | 이미지 자체 버전(개발자 지정) |
| `MajorSubsystemVersion`/`Minor...` | 2+2 | 요구 서브시스템 버전 |
| `Win32VersionValue` | 4 | 예약, 반드시 0 |
| `SizeOfImage` | 4 | 메모리에 로드된 전체 이미지 크기(`SectionAlignment` 배수) |
| `SizeOfHeaders` | 4 | DOS/PE/섹션 헤더 전체 크기(`FileAlignment` 배수로 올림) |
| `CheckSum` | 4 | 이미지 체크섬(드라이버/일부 시스템 DLL만 검증, 보통 EXE는 0이어도 무방) |
| `Subsystem` | 2 | `2`=GUI, `3`=CUI(콘솔), `1`=네이티브 드라이버 등 |
| `DllCharacteristics` | 2 | ASLR/DEP/CFG 등 보안 플래그 조합(REV-0526에서 상세) |
| `SizeOfStackReserve`/`Commit` | 4/8, 4/8 | 스레드 스택 예약/커밋 크기(기본 1MB/4KB) |
| `SizeOfHeapReserve`/`Commit` | 4/8, 4/8 | 프로세스 기본 힙 예약/커밋 크기 |
| `LoaderFlags` | 4 | 예약, 반드시 0 |
| `NumberOfRvaAndSizes` | 4 | 뒤에 오는 `DataDirectory` 배열의 원소 개수(보통 16) |

**DataDirectory 배열(16개, 각 원소는 `{VirtualAddress, Size}` 8바이트)**

| 인덱스 | 이름 | 의미 |
|---|---|---|
| 0 | Export Table | `.edata`, REV-0120 참고 |
| 1 | Import Table | `.idata`, REV-0119 참고 |
| 2 | Resource Table | `.rsrc`, REV-0141 참고 |
| 3 | Exception Table | x64 SEH/함수 테이블(`.pdata`) |
| 4 | Certificate Table | 디지털 서명(파일 오프셋 기준, RVA 아님에 주의) |
| 5 | Base Relocation Table | `.reloc`, ASLR용 재배치 정보 |
| 6 | Debug | 디버그 정보(PDB 경로 등) |
| 7 | Architecture | 예약, 사용 안 함 |
| 8 | Global Ptr | IA64 전역 포인터(x86/x64에서 사용 안 함) |
| 9 | TLS Table | `.tls`, REV-0133(TLS 콜백) 참고 |
| 10 | Load Config Table | 보안 쿠키, CFG 관련 정보 |
| 11 | Bound Import | 바인드된 임포트(고정 주소 최적화, 요즘 거의 안 씀) |
| 12 | IAT | Import Address Table 위치(임포트 테이블과 별개 항목) |
| 13 | Delay Import Descriptor | 지연 로드 임포트 |
| 14 | CLR Runtime Header | .NET 이미지 여부 판별(REV-0136 참고) — 여기 값이 있으면 .NET 어셈블리 |
| 15 | Reserved | 항상 0 |

## 화면/코드에서 보이는 징후
- PE-bear의 "Optional Header" 탭에 위 필드들이 그대로 나열되고, 각 값 옆에 16진수로 표시됨
- IDA의 헤더 뷰(`View > Open subviews > Segments` 또는 초기 로드 로그)에서 `AddressOfEntryPoint`, `ImageBase` 값이 표시됨
- `DataDirectory[14]`(CLR Runtime Header)의 `VirtualAddress`가 0이 아니면 .NET 바이너리라는 뜻(REV-0136)

## 가장 먼저 할 것
1. `Magic` 값으로 PE32/PE32+ 여부를 먼저 확인한다(필드 크기가 달라지므로).
2. `AddressOfEntryPoint`와 `ImageBase`를 더해 실제 진입점 VA(`ImageBase + AddressOfEntryPoint`)를 계산해서 IDA/x64dbg에서 시작 지점을 바로 찾는다.
3. `DataDirectory[1]`(Import), `DataDirectory[14]`(CLR)를 먼저 확인해 이 파일이 일반 네이티브 PE인지 .NET 어셈블리인지부터 구분한다.

## 단계별 절차
**1) PE-bear로 확인**
- 파일을 열고 "Optional Header" 탭을 클릭하면 위 표의 필드가 값과 함께 그대로 나열된다.
- "Data Directories" 탭에서 16개 항목의 RVA/Size를 개별적으로 확인할 수 있다.

**2) IDA로 확인**
- 파일 로드 시 상단 로그(Output window)에 `ImageBase`, `AddressOfEntryPoint` 값이 출력된다.
- `Ctrl+S`(세그먼트 뷰)에서 각 섹션의 시작 주소가 `ImageBase + VirtualAddress` 기준으로 표시된다.

## 명령어/단축키
- PE-bear: 파일 열기 → "Optional Header" / "Data Directories" 탭 클릭
- IDA: `Ctrl+S`(세그먼트 목록), 로드 시 Output window 확인

## 출력 해석
- `SectionAlignment`(메모리 정렬)와 `FileAlignment`(디스크 정렬)가 다르기 때문에, 파일에서의 오프셋(raw offset)과 메모리에서의 RVA는 섹션마다 서로 다른 배수로 정렬되어 계산이 필요하다(자세한 변환은 REV-0118 RVA VA Raw Offset 참고).
- `DataDirectory` 배열 원소의 `VirtualAddress`가 `0`이면 해당 디렉터리가 존재하지 않는다는 뜻(예: Export Table이 0이면 이 PE는 아무 함수도 export하지 않음).
- `Subsystem` 값이 `2`(GUI)인데 콘솔 창이 안 뜨는 이유, `3`(CUI)인데 콘솔이 뜨는 이유가 바로 이 필드 하나로 설명된다.

## 흔한 실수
- `AddressOfEntryPoint`를 VA로 착각해서 그대로 IDA에 입력하는 것 — 이 값은 RVA이므로 반드시 `ImageBase`를 더해야 실제 가상 주소가 된다.
- PE32와 PE32+에서 `BaseOfData` 필드가 있다 없다를 헷갈려 구조체 크기를 잘못 계산하는 것(PE32+는 `BaseOfData`가 없고 대신 `ImageBase`가 8바이트로 확장됨).
- `DataDirectory`의 인덱스 순서를 외우지 못해 Import(1번)와 IAT(12번)를 혼동하는 것 — 이 둘은 서로 다른 목적의 별개 항목이다.
- `SizeOfImage`가 파일 크기라고 착각하는 것 — 이는 메모리에 로드됐을 때의 크기이며 디스크 파일 크기와는 다르다(패딩/정렬 차이).

## 막혔을 때 다음 체크
- COFF 헤더와 옵셔널 헤더의 기본 구조 자체가 헷갈리면 → REV-0116(PE Header COFF Optional Header 읽기)을 먼저 본다.
- RVA/VA/Raw Offset 변환 계산이 필요하면 → REV-0118(RVA VA Raw Offset)을 본다.
- 섹션 이름과 그 안의 데이터 구조가 궁금하면 → REV-0525(PE Section 이름 관례 사전)를 본다.
- Export/Import/Resource/TLS 등 개별 디렉터리를 실제로 파싱하는 방법이 궁금하면 → REV-0119(Import Table), REV-0120(Export Table), REV-0141(Resource Section)을 본다.

## 미니 예제
PE-bear로 `notepad.exe`(x64)를 열어 Optional Header 탭을 보면 대략 다음과 같은 값이 나온다(실제 값은 Windows 버전마다 다를 수 있음).

```text
Magic                 : 0x20B  (PE32+)
AddressOfEntryPoint    : 0x00012340
ImageBase              : 0x0000000140000000
SectionAlignment       : 0x1000
FileAlignment          : 0x200
Subsystem              : 0x0002 (IMAGE_SUBSYSTEM_WINDOWS_GUI)
NumberOfRvaAndSizes    : 16
```

실제 진입점 VA는 `0x0000000140000000 + 0x00012340 = 0x0000000140012340`이며, 이 주소를 IDA에서 `G`(Go to address) 단축키로 바로 이동해 시작 코드를 확인할 수 있다.

## 관련 글
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0118 — RVA VA Raw Offset 계산
- REV-0525 — PE Section 이름 관례 사전(.text .rdata .data .rsrc 등)

## 출처/검증
- `IMAGE_OPTIONAL_HEADER32`/`IMAGE_OPTIONAL_HEADER64` 구조체의 필드명, 크기, 기본값, `DataDirectory` 16개 인덱스의 의미는 Microsoft PE/COFF 파일 형식 공식 사양(PE Format 문서) 기준이다.
- 위 미니 예제의 수치는 설명을 위해 구성한 근사값이며 실제 특정 Windows 버전의 `notepad.exe` 바이너리를 직접 덤프한 값이 아니다(2026-09-08 기준 서술).
