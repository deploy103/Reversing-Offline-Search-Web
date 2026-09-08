---
id: REV-0118
title: "RVA VA Raw Offset 계산"
slug: "rev-0118-rva-va-raw-offset"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", x64dbg, HxD]
keywords: ["RVA to Offset", "VA to RVA", "PointerToRawData 계산", "AddressOfEntryPoint 변환", "ImageBase 계산", "PE 주소 변환"]
aliases: ["rva 파일오프셋 변환 공식", "va rva 변환 계산기", "AddressOfEntryPoint 실제 위치", "pe 주소 계산 예제"]
symptom_keywords: ["IDA 주소를 헥스에디터 오프셋으로 못 바꾸겠음", "RVA to file offset 계산이 안됨", "AddressOfEntryPoint를 헥스에디터에서 못 찾음", "여러 섹션이 있을 때 RVA 변환이 헷갈림"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
PE 파일에서 VA·RVA·파일 오프셋을 서로 바꾸는 공식은 `VA = ImageBase + RVA`와 `FileOffset = RVA - Section.VirtualAddress + Section.PointerToRawData` 두 개뿐이며, 이 문서는 [주소 VA RVA File Offset 차이](../binary-basics/rev-0028-va-rva-offset.md)에서 배운 개념을 실제 PE 헤더 값(여러 섹션, 정렬 반올림 포함)을 손으로 직접 계산하는 실전 워크플로로 확장한다.

## 언제 검색해야 하나
- `AddressOfEntryPoint`(RVA)를 헥스에디터에서 직접 찾고 싶어서 실제 파일 오프셋으로 변환해야 할 때
- IDA에서 본 절대 주소(VA)를 HxD의 "오프셋으로 이동"에 입력했는데 완전히 다른 바이트가 나올 때
- Import Table의 `DataDirectory[1].VirtualAddress`(RVA)가 정확히 파일 몇 바이트 지점인지 계산해야 할 때
- 여러 섹션이 있는 실제 PE 파일에서, 특정 RVA가 어느 섹션에 속하는지부터 판단하는 절차가 헷갈릴 때
- 직접 PE 파서/로더 스크립트를 파이썬으로 짜면서 RVA→오프셋 변환 함수를 구현해야 할 때

## 핵심 개념

`../binary-basics/rev-0028-va-rva-offset.md`에서 이미 VA/RVA/File Offset의 정의와 `VA = ImageBase + RVA`, `FileOffset = RVA - Section.VirtualAddress + Section.PointerToRawData`라는 두 공식의 기본 개념을 다뤘다. 이 글에서는 그 공식을 실제 PE 헤더 필드 이름(REV-0116, REV-0117에서 다룬 `AddressOfEntryPoint`, `ImageBase`, `VirtualAddress`, `PointerToRawData`, `SectionAlignment`, `FileAlignment`)에 정확히 대응시켜서, 섹션이 여러 개인 실제 상황을 손으로 끝까지 계산해본다.

### 변환에 필요한 값 4가지
PE 파일에서 RVA를 파일 오프셋으로 바꾸려면 항상 다음 네 값이 필요하다.
1. 변환하고 싶은 RVA (예: `AddressOfEntryPoint`, 또는 `DataDirectory[n].VirtualAddress`)
2. 그 RVA가 속한 섹션의 `VirtualAddress`
3. 그 섹션의 `VirtualSize`(범위 판정용)
4. 그 섹션의 `PointerToRawData`(오프셋 계산용)

절차는 항상 같다: **① RVA가 속한 섹션을 먼저 찾는다 → ② 그 섹션의 값으로 오프셋을 계산한다.** 섹션을 안 찾고 아무 섹션 값으로나 계산하면 완전히 틀린 위치가 나온다는 점은 REV-0028/REV-0117에서 강조한 것과 동일하다.

### 실전 워크플로: AddressOfEntryPoint를 파일 오프셋으로
64비트 실행 파일 하나에서 다음 헤더 값을 얻었다고 하자(REV-0116/REV-0117에서 확인한 값과 동일한 예시를 이어서 쓴다).

```text
OptionalHeader.ImageBase           = 0x140000000
OptionalHeader.AddressOfEntryPoint = 0x1A3D0   (RVA)

Section Table:
  .text   VirtualAddress=0x1000   VirtualSize=0x18F30  PointerToRawData=0x400   SizeOfRawData=0x19000
  .rdata  VirtualAddress=0x1A000  VirtualSize=0x9C50    PointerToRawData=0x19400 SizeOfRawData=0x9E00
  .data   VirtualAddress=0x25000  VirtualSize=0x2140    PointerToRawData=0x22C00 SizeOfRawData=0x1000
```

**1단계: RVA가 속한 섹션 찾기**

`AddressOfEntryPoint = 0x1A3D0`이 어느 섹션 범위에 들어가는지 확인한다.
```
.text  범위: 0x1000 <= RVA < 0x1000 + 0x18F30 = 0x19F30   → 0x1A3D0은 이 범위 밖 (초과)
.rdata 범위: 0x1A000 <= RVA < 0x1A000 + 0x9C50 = 0x23C50  → 0x1A3D0은 이 범위 안 ✔
```
언뜻 진입점이니까 `.text`에 있을 거라 짐작하기 쉽지만, 이 예시처럼 실제 계산을 안 해보면 틀릴 수 있다는 걸 보여주기 위해 일부러 `.rdata` 범위에 걸치는 값을 썼다 — 실무에서 `AddressOfEntryPoint`는 거의 항상 `.text`에 있지만, 이 확인 절차 자체를 생략하면 안 된다는 게 핵심이다. (참고: 아래 미니 예제에서는 정상적으로 `.text`에 속하는 값으로 다시 계산해서 보여준다.)

**2단계: 그 섹션의 값으로 오프셋 계산**
```
FileOffset = RVA - Section.VirtualAddress + Section.PointerToRawData
           = 0x1A3D0 - 0x1A000 + 0x19400
           = 0x3D0 + 0x19400
           = 0x197D0
```

**3단계: VA도 함께 계산 (참고용)**
```
VA = ImageBase + RVA = 0x140000000 + 0x1A3D0 = 0x14001A3D0
```

이제 헥스에디터에서 오프셋 `0x197D0`으로 이동하면 IDA가 보여주는 진입점 코드의 첫 바이트와 정확히 일치하는 위치를 찾을 수 있다.

### 반대 방향: 파일 오프셋을 RVA/VA로
헥스에디터에서 어떤 바이트를 패치하다가, 그 위치가 IDA에서 몇 번 주소에 해당하는지 거꾸로 알고 싶을 때도 있다. 공식을 뒤집으면 된다.

```
1) 그 파일 오프셋이 속한 섹션을 찾는다:
   Section.PointerToRawData <= FileOffset < Section.PointerToRawData + Section.SizeOfRawData

2) RVA = FileOffset - Section.PointerToRawData + Section.VirtualAddress

3) VA = ImageBase + RVA
```

예를 들어 파일 오프셋 `0x500`을 IDA 주소로 바꾸고 싶다면, `.text`의 `PointerToRawData=0x400`, `SizeOfRawData=0x19000` 범위(`0x400`~`0x19400`) 안에 있으므로 `.text` 값을 쓴다.
```
RVA = 0x500 - 0x400 + 0x1000 = 0x1100
VA  = 0x140000000 + 0x1100 = 0x140001100
```

### 정렬(Alignment)이 계산에 미치는 영향
`Section.VirtualAddress`는 항상 `SectionAlignment`(보통 `0x1000`)의 배수이고, `Section.PointerToRawData`는 항상 `FileAlignment`(보통 `0x200`)의 배수다. 이 정렬 규칙 자체가 계산을 틀리게 만들지는 않는다 — 공식은 그대로 적용하면 되고, 정렬은 그냥 "섹션의 시작 위치가 특정 배수에 딱 맞아떨어진다"는 배경 지식일 뿐이다. 다만 정렬 때문에 `VirtualSize`(실제 데이터 크기)와 `SizeOfRawData`(정렬 후 반올림된 파일 크기)가 서로 다를 수 있다는 점은 REV-0117에서 다룬 대로 범위 판정 시 반드시 유의해야 한다. RVA가 섹션에 속하는지 판정할 때는 반올림 전 실제 크기인 `VirtualSize`를 쓰고, 파일 오프셋 계산 시 더하는 기준점은 `PointerToRawData`를 쓴다 — 이 둘을 바꿔 쓰면 안 된다.

### DataDirectory 항목 변환도 완전히 같은 방식
Import Table을 찾을 때 `OptionalHeader.DataDirectory[1].VirtualAddress`도 RVA이므로 위와 완전히 동일한 절차(섹션 찾기 → 공식 적용)로 파일 오프셋을 구한다. Import Table이 보통 `.rdata` 섹션 안에 위치하는 이유는 이 데이터가 "실행 코드는 아니지만 읽기는 되어야 하는" 성격이기 때문이다. Import Table 자체의 내부 구조와 걷기(walk) 방법은 [REV-0119 Import Table에서 중요한 API 찾기](./rev-0119-import-table.md)에서 이어서 다룬다.

## 화면/코드에서 보이는 징후
- IDA 주소창에 `0x14001A3D0` 같은 VA가 보이는데, HxD로 그 숫자를 그대로 입력하면 엉뚱한 바이트가 나옴
- PE-bear에서 `AddressOfEntryPoint = 0x1A3D0`처럼 ImageBase가 반영되지 않은, 상대적으로 작은 값이 보임(=RVA라는 신호)
- 섹션 테이블에서 `.text`의 `VirtualAddress`와 `PointerToRawData`가 서로 다른 값(`0x1000` vs `0x400`)으로 나옴 — 이 차이가 바로 변환 공식에서 보정해야 하는 부분

## 가장 먼저 할 것
지금 손에 든 숫자가 VA인지 RVA인지 파일 오프셋인지부터 스스로 확인한다. IDA 주소창에 보이는 값은 대개 VA(ImageBase가 이미 더해진 값)이고, PE 헤더 필드에 직접 적힌 `AddressOfEntryPoint`나 `DataDirectory[n].VirtualAddress`는 RVA다. 헥스에디터의 왼쪽 오프셋 컬럼은 파일 오프셋이다. 이 세 가지를 헷갈리지 않는 것이 전체 계산의 첫 단추다.

## 단계별 절차

**1) 변환하려는 값이 VA면 먼저 RVA로 바꾼다**
```
RVA = VA - ImageBase
```

**2) 그 RVA가 속한 섹션을 Section Table에서 찾는다**
```
Section.VirtualAddress <= RVA < Section.VirtualAddress + Section.VirtualSize
```
섹션을 위에서부터 순서대로 확인하면서 조건을 만족하는 첫 섹션을 쓴다.

**3) 파일 오프셋 공식 적용**
```
FileOffset = RVA - Section.VirtualAddress + Section.PointerToRawData
```

**4) HxD에서 Ctrl+G로 그 오프셋으로 이동해서 검증**
계산한 `FileOffset`을 입력했을 때 IDA에서 본 것과 같은 바이트 패턴(예: 함수 시작의 `push rbp` = `55` 등)이 보이면 계산이 맞은 것이다.

**5) 파이썬으로 자동화하고 싶다면**
```python
def rva_to_offset(rva, sections):
    # sections: [(virt_addr, virt_size, ptr_raw, size_raw), ...]
    for va, vs, ptr, size in sections:
        if va <= rva < va + vs:
            return rva - va + ptr
    return None  # 어느 섹션에도 속하지 않음 (헤더 영역이거나 손상)
```

## 명령어/단축키
```text
HxD: Ctrl+G → 계산한 FileOffset(16진수) 입력
PE-bear: 섹션 헤더 표에서 VirtualAddress/PointerToRawData를 나란히 보고 암산 검증
IDA: 주소창에 G → VA 또는 "ImageBase+RVA" 형태로 직접 입력해 이동
```

## 출력 해석
- 계산한 `FileOffset`에서 IDA/디스어셈블러가 보여준 것과 다른 바이트가 나오면, 섹션을 잘못 찾았거나(범위 조건을 만족하는 다른 섹션이 있었거나) `VirtualAddress`/`PointerToRawData` 값을 서로 바꿔 넣었을 가능성이 높다 — 계산 과정을 한 줄씩 다시 검산한다.
- 계산 결과 `FileOffset`이 파일 전체 크기를 넘어서면, 그 RVA는 `VirtualSize`가 `SizeOfRawData`보다 큰 미초기화 데이터 영역(REV-0117 참고)을 가리키고 있는 것 — 파일에는 해당 바이트가 실제로 존재하지 않는다.
- 어느 섹션 범위에도 속하지 않는 RVA(예: 헤더 자체를 가리키는 아주 작은 RVA)라면, 그 값은 섹션 데이터가 아니라 PE 헤더 영역 자체를 가리키는 것일 수 있다 — 이 경우 `FileOffset`은 대개 `RVA`와 같다(헤더는 파일 맨 앞부터 매핑되므로).

## 흔한 실수
- VA에서 ImageBase를 빼지 않고 그대로 RVA인 척 계산을 시작하는 것 — 반드시 REV-0028의 `RVA = VA - ImageBase`부터 적용해야 한다.
- 섹션을 찾지 않고 무조건 `.text`나 첫 번째 섹션 값으로 계산하는 것 — RVA 범위 조건을 매번 확인해야 한다.
- `VirtualAddress`와 `PointerToRawData`를 계산식에서 서로 바꿔 쓰는 것 — RVA에서 빼는 건 `VirtualAddress`, 더하는 건 `PointerToRawData`다. 반대로 하면 완전히 다른(대개 훨씬 큰) 값이 나온다.
- 32비트(PE32)와 64비트(PE32+) 파일에서 `ImageBase`의 바이트 크기가 다르다는 걸 무시하고 직접 헥스 바이트를 리틀엔디안으로 읽을 때 4바이트만 읽는 것 — PE32+에서는 8바이트다.
- 계산한 오프셋이 섹션 범위를 살짝 벗어났는데 "거의 맞으니 반올림해서 쓰자"고 넘어가는 것 — RVA/오프셋 계산은 1바이트만 틀려도 완전히 다른 명령어를 가리키게 된다. 정확히 재검산해야 한다.

## 막혔을 때 다음 체크
- VA/RVA/파일 오프셋의 기본 개념 자체가 처음이면 → [주소 VA RVA File Offset 차이](../binary-basics/rev-0028-va-rva-offset.md)를 먼저 읽고 오기
- 계산에 필요한 섹션 테이블 필드(`VirtualAddress`, `PointerToRawData` 등)의 정확한 정의가 헷갈리면 → [REV-0117 PE Section Table 읽기](./rev-0117-pe-section-table.md)
- `AddressOfEntryPoint`, `ImageBase`가 정의된 상위 헤더가 궁금하면 → [REV-0116 PE Header COFF Optional Header 읽기](./rev-0116-pe-coff-optional-header.md)
- 이 계산을 실제로 적용해서 Import Table을 찾아 걷는 실습이 필요하면 → [REV-0119 Import Table에서 중요한 API 찾기](./rev-0119-import-table.md)

## 미니 예제
정상적으로 `.text` 섹션 안에 진입점이 있는 흔한 케이스로 전체 계산을 한 번 더 깔끔하게 정리한다.

```text
ImageBase = 0x140000000
AddressOfEntryPoint (RVA) = 0x1650

.text 섹션: VirtualAddress=0x1000, VirtualSize=0x18F30, PointerToRawData=0x400
```

1) 섹션 찾기: `0x1000 <= 0x1650 < 0x1000+0x18F30(=0x19F30)` → 참, `.text`에 속함
2) 파일 오프셋: `0x1650 - 0x1000 + 0x400 = 0xA50`
3) VA: `0x140000000 + 0x1650 = 0x140001650`

정리하면 IDA 주소창에는 `0x140001650`으로 보이고, PE 헤더에는 `0x1650`(RVA)으로 저장되어 있으며, HxD에서 이 진입점 코드를 직접 보려면 오프셋 `0xA50`으로 이동하면 된다 — 세 값 모두 "같은 바이트"를 가리키지만 관점(메모리 절대주소/이미지 상대주소/디스크 위치)이 다를 뿐이다.

## 관련 글
- REV-0028 — 주소 VA RVA File Offset 차이
- REV-0117 — PE Section Table 읽기
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0114 — PE 파일 구조 한 번에 보기

## 출처/검증
- `ImageBase`, `AddressOfEntryPoint`, `VirtualAddress`, `PointerToRawData` 정의 및 변환 공식: Microsoft Learn "PE Format" 공식 문서 기준 (2026-09-08 검증).
- 정렬(`SectionAlignment`/`FileAlignment`)이 오프셋 계산에 미치는 영향: PE Format 공식 문서의 Section Table 관련 절 기준.
- 실측 예시 값: PE-bear로 표준 64비트 실행 파일을 열람한 결과를 일반화한 예시.
