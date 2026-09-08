---
id: REV-0547
title: ".reloc 섹션과 재배치 정보 읽는 법"
slug: "rev-0547-reloc-base-relocation"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", HxD]
keywords: ["IMAGE_BASE_RELOCATION", "IMAGE_DIRECTORY_ENTRY_BASERELOC", "IMAGE_REL_BASED_DIR64", "IMAGE_REL_BASED_HIGHLOW", "ASLR", "ImageBase", "IMAGE_FILE_RELOCS_STRIPPED"]
aliases: ["reloc 섹션이란", "베이스 재배치 테이블", "ASLR과 재배치의 관계", "이미지베이스 변경 시 주소 보정"]
symptom_keywords: ["reloc 섹션이 뭔지 모름", "ASLR이 켜진 파일을 정적 분석할 때 주소가 안 맞음", "덤프한 메모리 이미지 주소를 고정 오프셋으로 못 바꿈", ".reloc 섹션이 파일에 없는 이유를 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`.reloc` 섹션은 PE가 링커가 가정한 `ImageBase`가 아닌 다른 주소에 로드됐을 때(ASLR이 대표적인 경우), 코드/데이터 안에 하드코딩된 절대 주소들을 실제 로드 주소에 맞게 고쳐 쓸 수 있도록 "이 RVA에 있는 값을 얼마만큼 보정해야 한다"는 위치 목록을 담은 베이스 재배치(Base Relocation) 테이블이며, 이 구조를 이해하면 ASLR이 켜진 바이너리를 정적으로 분석하거나 메모리 덤프를 파일로 되돌릴 때 왜 주소가 어긋나는지, 그리고 어떻게 고쳐야 하는지를 알 수 있다.

## 언제 검색해야 하나
- ASLR이 켜진 x64 바이너리를 정적 분석 도구에 로드했는데, 실제 실행 중 디버거에서 본 주소와 IDA 정적 분석 주소가 계속 다르게 나올 때
- 언패킹 과정에서 프로세스 메모리를 덤프해서 파일로 저장했더니, 덤프 파일 내부의 절대 주소 참조들이 원래 파일 오프셋 기준으로 깨져 보일 때
- `IMAGE_FILE_RELOCS_STRIPPED` 플래그나 `.reloc` 섹션이 아예 없는 파일을 만났을 때 이게 무슨 의미인지 궁금할 때
- PE-bear의 `Base Relocations` 탭에 나오는 `IMAGE_REL_BASED_DIR64`, `IMAGE_REL_BASED_HIGHLOW` 같은 타입 값이 헷갈릴 때
- 수동으로 언패킹한 이미지를 다시 로드 가능한 PE로 재구성(dump & fix)할 때 재배치 테이블을 어떻게 다뤄야 하는지 알고 싶을 때

## 핵심 개념

### 왜 재배치가 필요한가
컴파일러/링커는 `OptionalHeader.ImageBase`(예: EXE는 관례적으로 `0x140000000`, DLL은 다양)에 로드된다고 가정하고 일부 절대 주소(예: 전역 변수의 VA를 직접 레지스터에 로드하는 명령, 함수 포인터 테이블의 절대 주소 항목 등)를 코드/데이터에 그대로 박아 넣는다. 만약 실제 로드 주소가 `ImageBase`와 정확히 같다면 이 값들은 그대로 유효하다. 하지만 ASLR(주소 공간 배치 난수화)이 켜져 있거나, 이미 그 주소에 다른 모듈이 로드되어 있어 충돌이 나면, 로더는 이미지를 다른 주소에 올리고(rebase) 이 하드코딩된 절대 주소들을 "실제 로드 주소 - ImageBase" 만큼 전부 보정해야 한다. `.reloc` 섹션은 바로 이 "보정이 필요한 위치 목록"을 담고 있다.

### IMAGE_BASE_RELOCATION 블록 구조
데이터 디렉터리 인덱스 5(`IMAGE_DIRECTORY_ENTRY_BASERELOC`)가 이 테이블의 시작 RVA와 전체 크기를 가리킨다. 테이블은 4KB 페이지 단위로 나뉜 여러 "블록"의 연속이다.
```c
typedef struct _IMAGE_BASE_RELOCATION {
    DWORD VirtualAddress;  // 이 블록이 담당하는 4KB 페이지의 시작 RVA
    DWORD SizeOfBlock;     // 이 블록 전체 크기(헤더 8바이트 포함)
    // 이어서 (SizeOfBlock - 8) / 2 개의 WORD 엔트리
} IMAGE_BASE_RELOCATION;
```
각 블록 뒤에는 2바이트짜리 엔트리가 여러 개 이어지며, 각 엔트리는 상위 4비트(Type)와 하위 12비트(Offset)로 나뉜다.
```text
엔트리(WORD) = (Type << 12) | Offset
Type   : 이 재배치의 종류(아래 표)
Offset : VirtualAddress(블록 시작 RVA)로부터의 바이트 오프셋(0~4095)
```
자주 보는 `Type` 값:
```text
IMAGE_REL_BASED_ABSOLUTE  0   // 패딩용, 아무 동작 안 함(정렬 맞추기용)
IMAGE_REL_BASED_HIGHLOW   3   // x86: 해당 위치의 32비트 값에 델타를 더함
IMAGE_REL_BASED_DIR64     10  // x64: 해당 위치의 64비트 값에 델타를 더함
```
로더는 각 엔트리마다 "블록 시작 RVA + Offset" 위치의 값을 읽어서, `실제로드주소 - OptionalHeader.ImageBase`(이를 델타라고 부른다)를 더한 뒤 다시 그 위치에 써넣는다. `IMAGE_REL_BASED_ABSOLUTE`(타입 0)는 실제 재배치가 아니라 블록을 짝수 개(4바이트/8바이트 정렬)로 맞추기 위한 채움용이므로 무시하면 된다.

### ASLR과의 관계
`OptionalHeader.DllCharacteristics`에 `IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE`(`0x0040`)가 켜져 있으면 이 이미지는 ASLR 대상이며, 로더가 매번 다른 주소에 올릴 수 있다는 뜻이다. 이때 `.reloc`이 없으면(즉 `IMAGE_FILE_RELOCS_STRIPPED`가 `FileHeader.Characteristics`에 켜져 있으면, `0x0001`) 로더는 재배치를 수행할 수 없으므로 **반드시 `ImageBase`에 정확히 로드해야 하며, ASLR을 사실상 적용할 수 없다**(고정 베이스로만 로드됨). 과거 일부 시스템 DLL이나 특수한 목적의 실행 파일이 의도적으로 재배치 정보를 제거해 로드 주소를 고정시키는 경우가 있었는데, 이는 성능(재배치 계산 생략)을 위한 것이었지만 ASLR 시대에는 보안상 바람직하지 않은 설정으로 취급된다.

## 화면/코드에서 보이는 징후
- PE-bear의 `Base Relocations` 탭에서 각 블록의 `VirtualAddress`, `SizeOfBlock`과 그 안의 엔트리 리스트(타입/오프셋)를 표 형태로 확인 가능
- 헤더 뷰에서 `FileHeader.Characteristics`에 `IMAGE_FILE_RELOCS_STRIPPED`(`0x0001`)가 켜져 있으면 `.reloc` 섹션 자체가 없거나 비어있음
- IDA로 파일을 열었을 때 기본적으로 `ImageBase`(예: `0x140000000`) 기준으로 주소가 표시되는데, 실제 실행 중인 프로세스를 x64dbg로 붙였을 때 모듈 베이스가 다르면(ASLR로 다른 주소에 로드) 두 도구의 주소가 일정한 델타만큼 차이 남
- 덤프한 메모리 이미지를 그대로 파일로 저장해서 다시 분석하면, 코드 안의 절대 주소 참조들이 덤프 당시의 실제 로드 주소를 기준으로 이미 패치되어 있어 원래 `ImageBase` 기준 정적 분석 결과와 어긋남

## 가장 먼저 할 것
ASLR이 관련된 주소 불일치 문제를 만나면, 먼저 IDA/도구가 사용 중인 베이스 주소(정적 분석 시 `ImageBase`)와 실제 실행 중 모듈 베이스(디버거에서 확인)를 각각 적어두고 그 차이(델타)를 계산한다. 그 다음 `.reloc`이 실제로 존재하는지, `IMAGE_FILE_RELOCS_STRIPPED`가 꺼져 있는지 확인해 이 파일이 애초에 재배치 가능한 파일인지부터 판단한다.

## 단계별 절차
**1) Base Relocation Directory 위치 확인**
`OptionalHeader.DataDirectory[5].VirtualAddress`/`.Size`를 읽는다. `Size`가 `0`이면 재배치 정보가 없는 파일이다.

**2) 블록 순회**
`VirtualAddress` 위치에서 시작해서 `IMAGE_BASE_RELOCATION` 헤더(8바이트)를 읽고, `SizeOfBlock`만큼 처리한 뒤 다음 블록으로 넘어가는 식으로 Directory 전체 크기(`Size`)를 다 소진할 때까지 반복한다.

**3) 각 블록 안의 엔트리 처리**
각 2바이트 엔트리에서 상위 4비트로 `Type`을, 하위 12비트로 `Offset`을 뽑는다. `Type`이 `IMAGE_REL_BASED_ABSOLUTE`(0)면 건너뛰고, `IMAGE_REL_BASED_HIGHLOW`(x86, 3) 또는 `IMAGE_REL_BASED_DIR64`(x64, 10)면 `블록의 VirtualAddress + Offset` 위치가 재배치 대상이다.

**4) 델타 계산 및 적용(수동 재구성 시)**
언패킹한 메모리 이미지를 파일로 정리하는 경우: `델타 = 덤프 당시 실제 로드 주소 - OptionalHeader.ImageBase`를 계산하고, 3단계에서 찾은 각 위치의 값에서 이 델타를 빼면(반대로 역보정) 원래 `ImageBase` 기준 정적 파일처럼 되돌릴 수 있다.

## 명령어/단축키
```text
PE-bear: Base Relocations 탭 — 블록/엔트리 목록 확인
IDA: Options → General → 로드 시 베이스 주소 지정 가능(Manual load 체크)
x64dbg: 모듈 목록(Alt+E)에서 실제 로드된 모듈 베이스 확인, 정적 분석 베이스와 비교
```

## 출력 해석
- 엔트리 타입이 대부분 `IMAGE_REL_BASED_DIR64`면 x64 PE, `IMAGE_REL_BASED_HIGHLOW`면 x86 PE의 전형적인 패턴
- 한 블록의 `SizeOfBlock`이 `8`(헤더만 있고 엔트리가 0개)이면 사실상 빈 블록 — 정상적인 링커 출력에서는 드물지만 오류는 아님
- `IMAGE_FILE_RELOCS_STRIPPED`가 켜져 있는데 `DllCharacteristics`에 `IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE`도 켜져 있다면 모순된 설정 — 실제로는 재배치할 수 없으므로 로더가 고정 베이스로만 로드하며, 이런 조합은 도구가 임의로 변조했거나 비표준 빌드일 가능성을 시사
- 재배치 엔트리 개수가 코드/데이터 크기 대비 지나치게 적으면(예: 큰 `.text`인데 엔트리가 몇 개뿐) 위치 독립 코드(PIC) 생성 옵션이 적용됐을 가능성이 있음(주소를 절대값이 아니라 RIP 상대 참조로 만들어 재배치 자체가 덜 필요해짐)

## 흔한 실수
- `.reloc`을 그냥 "쓰레기 섹션"으로 여기고 무시하는 것 — ASLR 관련 주소 계산 문제를 겪을 때 가장 먼저 봐야 할 섹션이다.
- 엔트리의 `Offset`이 블록의 `VirtualAddress`로부터의 상대 오프셋이라는 걸 잊고, 파일 전체 기준 절대 RVA로 착각하는 것.
- `IMAGE_REL_BASED_ABSOLUTE`(타입 0) 엔트리도 실제 재배치 대상이라고 착각해서 잘못된 위치를 패치하는 것 — 이 타입은 패딩용으로 반드시 건너뛰어야 한다.
- 덤프한 메모리 이미지를 재배치 보정 없이 그대로 원본 파일과 바이트 단위로 비교해서 "코드가 다르다"고 잘못 결론 내리는 것 — 실제로는 재배치로 인한 주소 값 차이일 뿐일 수 있다.
- x86과 x64의 재배치 타입 상수(`HIGHLOW`=3 vs `DIR64`=10)를 혼동해서 잘못된 크기(4바이트 vs 8바이트)로 값을 읽고 쓰는 것.

## 막혔을 때 다음 체크
- 섹션 테이블 관점에서 `.reloc`이 다른 섹션과 어떻게 배치되는지 보고 싶으면 → [PE Section Table 읽기](./rev-0117-pe-section-table.md)
- RVA를 실제 파일 오프셋으로 바꾸는 계산식이 필요하면 → [RVA VA Raw Offset 계산](./rev-0118-rva-va-raw-offset.md)
- 같은 x64 전용 데이터 디렉터리인 예외 처리 테이블도 함께 보고 싶으면 → [.pdata 섹션과 x64 예외 처리 정보 읽는 법](./rev-0546-pdata-exception-handling.md)
- PE 헤더 전체 구조에서 Data Directory 배열의 위치가 헷갈리면 → [PE Header COFF Optional Header 읽기](./rev-0116-pe-coff-optional-header.md)
- PE 전체 구조를 다시 한 번 정리하고 싶으면 → [PE 파일 구조 한 번에 보기](./rev-0114-pe-overview.md)

## 미니 예제
64비트 DLL 하나의 Base Relocation Directory를 PE-bear로 열었더니 다음과 같은 블록이 보였다.

```text
Block VirtualAddress = 0x1000, SizeOfBlock = 0x20 (헤더 8 + 엔트리 12개 * 2바이트)
엔트리 예: (Type=DIR64, Offset=0x008), (Type=DIR64, Offset=0x120), (Type=ABSOLUTE, Offset=0x000) ...
```
이 DLL의 링크 시점 `ImageBase`는 `0x180000000`이었는데, 실제 프로세스에서는 ASLR로 `0x7FF6A0000000`에 로드됐다고 하자. 델타는 `0x7FF6A0000000 - 0x180000000 = 0x7FF520000000`이다. 로더는 `Type=DIR64`인 각 엔트리 위치(`0x1000+0x008`, `0x1000+0x120` 등)의 8바이트 값에 이 델타를 더해서 코드/데이터 안의 절대 주소 참조들을 실제 로드 주소 기준으로 고쳐 쓴다. `Type=ABSOLUTE`인 세 번째 엔트리는 실제 패치 대상이 아니라 블록을 짝수로 정렬하기 위한 채움값이므로 무시한다.

## 관련 글
- REV-0117 — PE Section Table 읽기
- REV-0118 — RVA VA Raw Offset 계산
- REV-0546 — .pdata 섹션과 x64 예외 처리 정보 읽는 법
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0114 — PE 파일 구조 한 번에 보기

## 출처/검증
- `IMAGE_BASE_RELOCATION` 구조체와 재배치 타입 상수(`IMAGE_REL_BASED_HIGHLOW`, `IMAGE_REL_BASED_DIR64` 등): Microsoft Learn "PE Format" 공식 문서의 ".reloc Section (Image Only)" 항목 기준 (2026-09-08 검증).
- `IMAGE_FILE_RELOCS_STRIPPED`, `IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE` 플래그 정의: Microsoft Learn "PE Format" 공식 문서 기준.
- ASLR과 베이스 재배치의 관계: Microsoft Learn ASLR 관련 공식 문서 및 다수 리버싱 참고자료 공통 설명 기준.
