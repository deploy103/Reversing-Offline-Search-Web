---
id: REV-0593
title: "Section 이름이 표준과 달라서 도구가 헷갈릴 때"
slug: "rev-0593-nonstandard-section-names"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", "Detect It Easy"]
keywords: ["IMAGE_SECTION_HEADER", "Characteristics", "IMAGE_SCN_MEM_EXECUTE", "IMAGE_SCN_CNT_CODE", "UPX0 UPX1", "섹션 이름 스푸핑"]
aliases: ["text 섹션이 안 보임", "섹션 이름이 이상함", "UPX0 UPX1 섹션이란"]
symptom_keywords: ["섹션 이름이 .text가 아니라 이상한 문자열이다", ".text 섹션을 검색해도 안 나온다", "PE-bear에서 섹션 이름이 UPX0 UPX1로 되어있다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
섹션 이름이 `.text`/`.data`가 아니라 `UPX0`, `UPX1` 또는 알아볼 수 없는 임의의 문자열로 되어 있어도 실행에는 아무 문제가 없는 이유는 **Windows 로더가 섹션 이름을 전혀 참조하지 않고, `IMAGE_SECTION_HEADER.Characteristics`의 비트 플래그(실행 가능/쓰기 가능/코드 여부)만으로 각 섹션을 처리하기 때문**이며, 분석 시에도 이름이 아니라 이 `Characteristics` 값과 `AddressOfEntryPoint`가 속한 섹션을 기준으로 코드/데이터 섹션을 구분해야 한다.

## 언제 검색해야 하나
- IDA나 PE-bear의 섹션 목록에 `.text`, `.data`, `.rdata` 같은 익숙한 이름이 하나도 안 보이고 `UPX0`, `UPX1`, `.aspack`, 혹은 의미 없는 문자열/빈 문자열만 있을 때
- 자동화 스크립트가 섹션 이름을 문자열로 매칭(`if section.Name == ".text"`)하도록 짜여 있어서 오탐이 날 때
- Detect It Easy가 섹션 이름만으로 특정 패커(UPX 등)를 자동 식별했다는 결과를 봤을 때 그 원리가 궁금할 때

## 핵심 개념
`IMAGE_SECTION_HEADER` 구조체의 `Name` 필드는 **정확히 8바이트**이며, 스펙상 널 종료 문자열이 아니다(8자를 꽉 채우면 널 종료 바이트가 없을 수도 있다). 더 중요한 것은 이 이름이 순전히 사람이 읽기 위한 레이블일 뿐, Windows 로더의 실행 동작에는 전혀 영향을 주지 않는다는 점이다. 로더는 각 섹션을 메모리에 매핑할 때 다음 필드들만 본다.

- `VirtualAddress`, `VirtualSize`: 이 섹션이 메모리 어디에, 얼마나 매핑되는지
- `PointerToRawData`, `SizeOfRawData`: 파일 어느 위치의 데이터를 그대로 복사할지
- `Characteristics`: 이 섹션에 부여할 메모리 보호 속성과 내용 종류를 나타내는 비트 플래그
  - `IMAGE_SCN_CNT_CODE`(0x00000020): 실행 코드를 담고 있음
  - `IMAGE_SCN_CNT_INITIALIZED_DATA`(0x00000040): 초기화된 데이터
  - `IMAGE_SCN_CNT_UNINITIALIZED_DATA`(0x00000080): 초기화 안 된 데이터(BSS류)
  - `IMAGE_SCN_MEM_EXECUTE`(0x20000000): 실행 가능 페이지
  - `IMAGE_SCN_MEM_READ`(0x40000000): 읽기 가능
  - `IMAGE_SCN_MEM_WRITE`(0x80000000): 쓰기 가능

즉 어떤 섹션이 "코드 섹션"으로 취급되는지는 이름이 `.text`인지가 아니라, `Characteristics`에 `IMAGE_SCN_CNT_CODE`와 `IMAGE_SCN_MEM_EXECUTE`가 켜져 있는지로 결정된다. 링커/컴파일러가 관례적으로 `.text`, `.data`, `.rdata`, `.rsrc` 같은 이름을 붙일 뿐이고, 이 관례를 어떤 도구도 강제하지 않는다.

UPX 같은 패커는 압축 해제용 섹션을 관례적으로 `UPX0`(대개 압축 해제된 코드가 풀릴 빈 공간), `UPX1`(압축된 원본 코드+압축 해제 스텁), `UPX2`(임포트 등 나머지 데이터) 이름으로 만든다. 이 이름 패턴 자체가 워낙 유명해서 Detect It Easy 같은 도구가 이를 시그니처로 활용해 "UPX로 패킹됨"을 빠르게 판별하는 데 쓰지만, 이것은 어디까지나 관례적 이름을 이용한 휴리스틱이지 스펙 요구사항이 아니다. 악의적인 목적으로 섹션 이름을 무작위 문자열이나 심지어 다른 정상 이름(`.text`가 아닌데 `.text`처럼 보이는 이름)으로 바꿔서 사람의 눈이나 이름 기반 자동화 도구를 혼란시키는 경우도 흔하다.

## 화면/코드에서 보이는 징후
- PE-bear/IDA의 섹션 목록에 `.text` 대신 `UPX0`, `UPX1` 또는 빈 문자열, 임의 문자열이 표시됨
- Detect It Easy가 섹션 이름 패턴만으로 특정 패커를 자동 인식한 결과를 보여줌
- 자동화 스크립트(Python `pefile` 등)에서 `.text` 이름으로 섹션을 찾는 코드가 `None`을 반환하며 실패함
- 섹션 이름은 `.text`인데 실제 `Characteristics`에는 실행 속성이 없는(반대로 데이터 섹션인데 실행 속성이 있는) 위장 사례

## 가장 먼저 할 것
섹션 이름은 참고용으로만 보고, PE-bear의 Section Headers 탭이나 IDA의 세그먼트 뷰(`Alt+7`)에서 각 섹션의 `Characteristics` 값과 `AddressOfEntryPoint`가 어느 섹션의 `VirtualAddress`~`VirtualAddress+VirtualSize` 범위에 속하는지부터 확인한다. 그 섹션이 사실상의 코드 섹션이다.

## 단계별 절차
**1) PE-bear로 Characteristics 직접 확인**
- `Section Headers` 탭을 연다. 각 행에 `Name`뿐 아니라 `Characteristics`(16진수 플래그 값)와 이를 사람이 읽기 쉽게 풀어주는 표시(Executable, Readable, Writable 등 체크 아이콘)가 함께 있다.
- `IMAGE_SCN_MEM_EXECUTE`가 켜진 섹션을 코드 섹션 후보로 표시해둔다.

**2) Entry Point가 속한 섹션 찾기**
- `Optional Header`에서 `AddressOfEntryPoint` 값을 확인한다.
- 각 섹션의 `VirtualAddress`부터 `VirtualAddress + VirtualSize` 범위 중 이 값이 포함되는 섹션을 찾는다. 이름이 뭐든 이 섹션이 실제 진입점이 있는, 사실상의 코드 섹션이다.

**3) IDA에서도 동일하게 접근**
- IDA는 파일을 로드할 때 `Characteristics`를 읽어 자동으로 세그먼트 속성(R/W/X)을 부여하므로, 이름과 무관하게 `Segments` 창(단축키로 열리는 목록)에서 `R W X` 컬럼을 보고 실행 가능한 세그먼트를 바로 식별할 수 있다.

**4) 자동화 스크립트를 이름이 아닌 플래그 기준으로 수정**
- Python `pefile`을 쓴다면 `section.Name`으로 매칭하지 말고 `section.Characteristics & 0x20000000`(`IMAGE_SCN_MEM_EXECUTE`) 같은 비트 검사로 코드 섹션을 찾도록 로직을 바꾼다.

## 명령어/단축키
```text
PE-bear: Section Headers 탭에서 Characteristics 컬럼 확인
IDA: Alt+7(세그먼트 뷰)에서 R/W/X 컬럼 확인
Python pefile: section.Characteristics & 0x20000000  # IMAGE_SCN_MEM_EXECUTE 여부
```

## 출력 해석
- `Characteristics`에 `0x60000020`(코드 + 실행 + 읽기) 같은 값이 있으면 전형적인 코드 섹션 조합이다.
- 이름이 `.text`인데 `Characteristics`에 실행 속성이 빠져 있다면, 이 섹션은 이름만 위장된 데이터 섹션일 수 있으므로 속지 않아야 한다.
- `AddressOfEntryPoint`가 특정 섹션 범위에 들어가면, 그 섹션 이름이 무엇이든 실제 실행이 시작되는 곳이라는 확실한 근거가 된다.

## 흔한 실수
- 섹션 이름이 `.text`가 아니라는 이유만으로 "이 파일에는 코드 섹션이 없다"고 오해하는 것.
- 자동화 스크립트나 YARA 룰을 섹션 이름 문자열에만 의존해서 작성했다가, 이름이 조작된 샘플에서 전부 놓치는 것.
- UPX 섹션 이름(`UPX0`/`UPX1`)만 보고 반드시 UPX라고 단정하는 것 — 이름은 자유롭게 바꿀 수 있으므로 실제로는 Characteristics나 코드 패턴, 헤더 구조로 재검증해야 확실하다.
- 섹션 이름의 8바이트 제한을 모르고 9바이트 이상의 이름을 넣으려다 뒷부분이 잘리는 것을 오류로 착각하는 것.

## 막혔을 때 다음 체크
- 섹션 이름뿐 아니라 헤더 자체의 다른 필드도 조작되어 도구가 파싱을 거부한다면 → REV-0592(PE 헤더가 조작되어 도구가 잘못 파싱할 때)를 함께 본다.
- 패커 여부 자체를 확실히 판별하고 싶다면 → REV-0126(Detect It Easy로 컴파일러 패커 확인)을 참고한다.
- 섹션 테이블의 각 필드 의미를 처음부터 다시 보고 싶다면 → REV-0117(PE Section Table 읽기)을 참고한다.

## 미니 예제
어떤 파일의 섹션 목록이 다음과 같이 보였다고 하자.

```text
Name      VirtualAddress  VirtualSize  Characteristics
UPX0      0x1000          0x00009000   0xE0000080
UPX1      0xA000          0x00003200   0xE0000060
UPX2      0xE000          0x00000800   0xC0000040
```

이름만 보면 셋 다 낯설지만, `UPX1`의 `Characteristics`(`0xE0000060`)에는 `IMAGE_SCN_CNT_CODE`(0x20)와 `IMAGE_SCN_MEM_EXECUTE`(0x20000000) 비트가 모두 켜져 있다. `Optional Header`의 `AddressOfEntryPoint`가 `0xA050`이라면 이는 `UPX1` 섹션(`0xA000`~`0xA000+0x3200`) 범위 안에 들어가므로, 이름이 무엇이든 `UPX1`이 실질적인 진입점 코드 섹션임을 확신할 수 있다.

## 관련 글
- REV-0117 — PE Section Table 읽기
- REV-0592 — PE 헤더가 조작되어 도구가 잘못 파싱할 때
- REV-0126 — Detect It Easy로 컴파일러 패커 확인
- REV-0121 — Entry Point와 WinMain 찾기

## 출처/검증
- `IMAGE_SECTION_HEADER.Name`이 8바이트 고정이며 널 종료가 보장되지 않는다는 점, `Characteristics` 비트 플래그(`IMAGE_SCN_CNT_CODE`, `IMAGE_SCN_MEM_EXECUTE` 등)의 의미는 Microsoft PE/COFF 형식 공식 문서 기준.
- UPX가 `UPX0`/`UPX1`/`UPX2` 섹션 이름 관례를 사용한다는 사실은 UPX 공식 프로젝트 및 다수의 언패킹 레퍼런스에서 공통적으로 확인된다.
