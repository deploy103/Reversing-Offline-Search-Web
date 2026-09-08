---
id: REV-0028
title: "주소 VA RVA File Offset 차이"
slug: "rev-0028-va-rva-offset"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, PE-bear, HxD, readelf, objdump]
keywords: ["VA", "RVA", "File Offset", "Virtual Address", "Relative Virtual Address", "ImageBase", "PointerToRawData", "AddressOfEntryPoint", "p_vaddr", "p_offset"]
aliases: ["가상주소", "상대가상주소", "파일오프셋", "VA RVA 차이", "IDA 주소가 파일이랑 다름"]
symptom_keywords: ["IDA 주소를 헥스에디터에서 못찾겠음", "RVA가 뭔지 모르겠음", "ImageBase 더해야하는지 모르겠음", "파일 오프셋이랑 가상주소가 다름", "PointerToRawData가 뭔지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
같은 바이트라도 **파일 오프셋(File Offset)**, **VA(Virtual Address)**, **RVA(Relative Virtual Address)**라는 서로 다른 세 가지 "주소"로 표현될 수 있고, 이 셋을 서로 변환하지 못하면 IDA에서 본 주소를 헥스에디터에서 못 찾는 사고가 난다.

## 언제 검색해야 하나
- IDA/Ghidra에서 본 주소(예: `0x00401150`)를 HxD 같은 헥스에디터에서 찾으려는데 그 위치에 전혀 다른 바이트가 있을 때
- PE의 `AddressOfEntryPoint`, `PointerToRawData`, `VirtualAddress` 같은 필드 이름이 헷갈릴 때
- ELF의 `readelf -l` 출력에서 `p_vaddr`와 `p_offset`이 다른 값으로 나와서 당황했을 때
- 직접 로더나 파서 스크립트를 짜야 하는데 RVA를 실제 파일 위치로 바꾸는 공식을 모를 때
- 메모리 덤프(라이브 프로세스가 아닌 덤프 파일)를 분석하는데 주소 체계가 헷갈릴 때

## 핵심 개념

리버싱을 하다 보면 "주소"라는 말이 최소 세 가지 다른 뜻으로 쓰인다. 이걸 구분하지 못하면 IDA에서 찾은 함수를 헥스에디터로 패치하려 할 때마다 엉뚱한 위치를 건드리게 된다.

**1) File Offset (파일 오프셋)**

디스크에 저장된 바이너리 파일 안에서, 그 바이트가 몇 번째 바이트인지를 나타내는 **순수한 파일 내 위치**다. HxD 같은 헥스에디터를 열었을 때 왼쪽에 보이는 오프셋 컬럼이 바로 이것이다. 파일을 처음부터 순서대로 읽었을 때의 위치이므로, 프로세스가 실행 중이든 아니든 상관없이 고정된 값이다.

**2) VA (Virtual Address, 가상 주소)**

OS 로더가 이 파일을 메모리에 매핑(로드)한 뒤, **실제로 실행 중인 프로세스의 가상 메모리 공간에서** 그 바이트가 위치하는 주소다. 예를 들어 `0x00401000`처럼 나타난다. IDA나 x64dbg에서 기본적으로 보여주는 주소가 대부분 이 VA(또는 뒤에서 설명할 RVA)다. 파일 오프셋과 달리, 프로세스가 로드되는 위치(ImageBase)에 따라 값이 달라질 수 있다.

**3) RVA (Relative Virtual Address, 상대 가상 주소)**

`RVA = VA - ImageBase`로 정의된다. PE 포맷은 `AddressOfEntryPoint`, 임포트/익스포트 테이블 주소 같은 내부 주소 대부분을 **절대 VA가 아니라 RVA로 저장**한다. 이유는 간단하다 — ImageBase는 재배치(relocation)나 ASLR 때문에 실행할 때마다 바뀔 수 있지만, RVA는 이미지가 어디에 로드되든 상관없이 "이미지 시작점으로부터 몇 바이트 떨어져 있는가"라는 상대적 값이므로 항상 고정이다. 즉 PE 파일 하나를 만들 때 로더가 어디에 올릴지 미리 알 수 없으므로, 절대 주소 대신 상대 주소를 저장해서 어디에 로드되든 재사용 가능하게 만든 것이다.

**변환 공식**은 다음 한 줄로 요약된다.

```
VA = ImageBase + RVA
```

이 공식이 VA·RVA·ImageBase 세 값 사이의 전부다. RVA를 알고 ImageBase를 알면 VA가 나오고, 반대로 VA에서 ImageBase를 빼면 RVA가 나온다.

그런데 이 VA/RVA는 어디까지나 "**메모리에 로드된 후**"의 이야기이고, 파일 오프셋은 "**디스크에 있을 때**"의 이야기다. 이 둘을 이어주는 다리가 섹션 헤더의 `VirtualAddress`(그 섹션의 RVA)와 `PointerToRawData`(그 섹션 데이터가 파일 어디서 시작하는지)다. 자세한 섹션 테이블 구조는 [`./rev-0029-section-vs-segment.md`](./rev-0029-section-vs-segment.md)에서 다룬다.

> 참고: ImageBase 필드 자체의 크기도 [`./rev-0021-x86-vs-x64.md`](./rev-0021-x86-vs-x64.md)에서 다루는 32/64비트 차이를 그대로 따른다. PE32(32비트)에서는 ImageBase가 4바이트, PE32+(64비트)에서는 8바이트로 저장된다. 그리고 이 모든 주소 필드는 [`./rev-0023-endianness.md`](./rev-0023-endianness.md)에서 설명하는 대로 파일 안에 리틀엔디안으로 저장되어 있으므로, 헥스에디터에서 바이트를 직접 읽을 때는 순서를 뒤집어야 한다.

**PIE와 ASLR에서 특히 중요해지는 이유**: 이 VA/RVA 구분은 평소에는 별로 신경 쓰지 않아도 되지만, PIE(Position Independent Executable) 바이너리를 분석하거나 ASLR(Address Space Layout Randomization)이 걸린 프로세스를 디버깅할 때는 결정적으로 중요해진다. ASLR이 켜져 있으면 프로세스를 실행할 때마다 실제 로드 베이스 주소가 랜덤하게 바뀌어서, 오늘 GDB에서 본 VA가 내일 다시 실행하면 완전히 다른 값이 된다. 반면 RVA와 파일 오프셋은 실행할 때마다 바뀌지 않고 고정이다. 그래서 ASLR 환경에서 브레이크포인트나 패치 위치를 재현 가능하게 기록하려면 VA가 아니라 RVA(또는 파일 오프셋) 기준으로 적어두어야 한다. PIE/ASLR 자체를 다루는 별도 글은 이 위키에서 따로 준비 중이다(가칭 "PIE와 ASLR" 항목, 아직 작성 전).

## 화면/코드에서 보이는 징후
- IDA의 주소창(또는 함수 목록)에 나온 주소를, 그대로 HxD의 "오프셋으로 이동"에 입력했더니 엉뚱한 바이트가 나옴
- PE-bear나 CFF Explorer로 PE를 열었을 때 `AddressOfEntryPoint`, `VirtualAddress`, `PointerToRawData`처럼 비슷해 보이지만 값이 다른 필드들이 나열됨
- `readelf -l` 출력에서 같은 세그먼트인데 `VirtAddr`와 `Offset` 컬럼 값이 서로 다름
- IDA 옵션에서 "Rebase program" 또는 Options → General의 주소 표시 방식에 따라 같은 함수의 주소가 다르게 보임(이미지가 리베이스됐는지 여부)

## 가장 먼저 할 것
지금 보고 있는 값이 정확히 어느 종류인지부터 확인한다. IDA 화면에 나오는 주소는 대부분 VA(ImageBase가 이미 더해진 값)다. 반면 헥스에디터의 오프셋 컬럼은 파일 오프셋이다. 둘을 그대로 같은 숫자로 취급하고 헥스에디터에서 찾으려 하면 반드시 어긋난다 — 먼저 "이 값이 VA인가, RVA인가, 파일 오프셋인가"를 스스로에게 물어야 한다.

## 단계별 절차

**1) PE에서 ImageBase 확인**

PE-bear나 IDA의 헤더 뷰에서 Optional Header의 `ImageBase`를 확인한다. 기본값은 32비트 실행 파일(EXE) 기준으로 흔히 `0x00400000`이다(DLL은 보통 `0x10000000`).

**2) IDA에서 본 VA를 RVA로 변환**

```
RVA = VA - ImageBase
```
예를 들어 IDA에서 `0x00401150`을 봤고 ImageBase가 `0x00400000`이라면, `RVA = 0x00401150 - 0x00400000 = 0x1150`이다.

**3) 그 RVA가 속한 섹션을 찾는다**

PE-bear의 섹션 헤더 목록(또는 IDA의 Segments 창)에서, 각 섹션의 `VirtualAddress`(시작 RVA)와 `VirtualSize`(그 섹션의 메모리상 크기)를 보고, 다음 조건을 만족하는 섹션을 찾는다.

```
Section.VirtualAddress <= RVA < Section.VirtualAddress + Section.VirtualSize
```

**4) 그 섹션의 PointerToRawData로 파일 오프셋 계산**

```
FileOffset = RVA - Section.VirtualAddress + Section.PointerToRawData
```

**5) 헥스에디터로 정확한 위치 확인**

계산된 FileOffset을 HxD의 "Ctrl+G(오프셋으로 이동)"에 입력하면 IDA에서 본 바이트와 정확히 같은 바이트가 그 위치에 있는 것을 확인할 수 있다.

**6) ELF의 경우 readelf로 대응**

```bash
readelf -l ./binary
```
프로그램 헤더(세그먼트) 목록에서 `VirtAddr`(메모리 주소, PIE 바이너리라면 로드 베이스로부터의 상대값)와 `Offset`(파일 오프셋)을 나란히 확인한다. PE와 원리는 같다 — "이 VA가 속한 세그먼트를 먼저 찾고, 그 세그먼트의 offset을 기준으로 상대 위치를 계산한다."

## 명령어/단축키
```bash
# ELF: 세그먼트별 VirtAddr / Offset / FileSiz 확인
readelf -l ./binary

# ELF: 섹션별 sh_addr / sh_offset 확인 (PE의 VirtualAddress/PointerToRawData에 대응)
readelf -S ./binary

# ELF: 요약 뷰(더 간단히 보고 싶을 때)
objdump -h ./binary
```
- IDA: 주소창에 RVA를 입력하고 싶으면 `Jump to address`(단축키 `G`)에서 `ImageBase+RVA` 형태로 직접 계산해 입력하거나, IDA가 이미 rebase된 상태라면 그냥 VA를 입력.
- PE-bear: 좌측 트리에서 `Section Headers`를 클릭하면 각 섹션의 `VirtualAddress` / `PointerToRawData` / `VirtualSize` / `SizeOfRawData`를 표 형태로 한눈에 볼 수 있음.
- HxD: `Ctrl+G` → "오프셋으로 이동"에 파일 오프셋(16진수) 입력.

## 출력 해석
`ImageBase = 0x00400000`, `.text` 섹션의 `VirtualAddress = 0x1000`, `PointerToRawData = 0x400`, `AddressOfEntryPoint = 0x1150`이라는 전형적인 32비트 PE를 예로 전체 계산을 풀어보자.

`AddressOfEntryPoint`는 PE 헤더에 RVA로 저장되어 있으므로 그 값 자체가 `0x1150`이다. 이 RVA가 `.text` 섹션(`0x1000` ~ `0x1000 + VirtualSize`) 범위 안에 있으므로 `.text`의 `PointerToRawData`를 기준으로 파일 오프셋을 구한다.

```
FileOffset = RVA - Section.VirtualAddress + Section.PointerToRawData
           = 0x1150 - 0x1000 + 0x400
           = 0x550

VA (기본 로드 시) = ImageBase + RVA
                  = 0x00400000 + 0x1150
                  = 0x00401150
```

같은 진입점 바이트를 세 가지 관점으로 정리하면 다음과 같다.

| 구분 | 값 | 의미 |
|---|---|---|
| RVA | `0x1150` | 이미지 시작점으로부터 상대 위치 (PE 헤더에 저장된 그대로) |
| File Offset | `0x550` | HxD 등 헥스에디터에서 이 바이트를 찾을 실제 파일상 위치 |
| VA (기본 로드시) | `0x00401150` | 기본 ImageBase(`0x00400000`)로 로드됐을 때 프로세스 메모리상 주소, IDA가 기본으로 보여주는 값 |

여기서 반드시 기억할 점: 위 공식은 **RVA가 속한 섹션을 먼저 찾은 뒤에만** 적용할 수 있다. `.text`, `.data`, `.rdata` 등 섹션마다 `VirtualAddress`와 `PointerToRawData`가 다르므로, RVA 하나를 임의의 섹션 값으로 계산하면 완전히 틀린 파일 위치가 나온다. 또한 섹션의 `VirtualSize`(메모리상 크기)와 `SizeOfRawData`(파일상 크기)가 서로 다를 수 있다는 점도 주의해야 한다 — 예를 들어 `.bss`처럼 초기화되지 않은 데이터 영역은 메모리에서는 공간을 차지하지만 파일에는 실제 바이트가 없거나 훨씬 작게 저장되는 경우가 흔하다(정렬 및 언이니셜라이즈드 영역 때문). 그러니 "RVA에서 그냥 어떤 섹션의 VirtualAddress를 빼고 PointerToRawData를 더하면 되겠지"라고 아무 섹션에나 공식을 적용하면 안 되고, 반드시 `Section.VirtualAddress <= RVA < Section.VirtualAddress + Section.VirtualSize` 조건을 만족하는 섹션을 먼저 찾아야 한다.

## 흔한 실수
- IDA에서 본 VA를 그대로 헥스에디터의 오프셋에 입력하는 것 — VA와 파일 오프셋은 다른 값이다. 반드시 ImageBase를 빼고(RVA로 변환), 해당 섹션의 PointerToRawData를 기준으로 다시 계산해야 한다.
- RVA를 계산할 때 아무 섹션이나 골라서 공식을 적용하는 것 — 반드시 그 RVA가 속한(범위 안에 있는) 섹션을 먼저 찾아야 한다. 섹션마다 `VirtualAddress`와 `PointerToRawData`가 다르기 때문에 잘못된 섹션 기준으로 계산하면 완전히 다른(때로는 파일 범위를 벗어난) 오프셋이 나온다.
- `VirtualSize`와 `SizeOfRawData`를 같은 값이라고 가정하는 것 — 섹션 정렬(Alignment)이나 `.bss` 같은 미초기화 영역 때문에 메모리상 크기와 파일상 크기가 다를 수 있다.
- ASLR이 걸린 프로세스에서 오늘 관찰한 VA를 "고정된 주소"로 착각하고 다음 실행에도 그대로 쓰는 것 — ASLR 환경에서는 매 실행마다 로드 베이스가 바뀌므로 VA도 바뀐다. RVA(또는 파일 오프셋)만이 실행마다 고정이다.
- PE의 `PointerToRawData`가 파일 정렬(FileAlignment, 보통 0x200) 단위로 반올림된다는 점을 무시하고 임의의 값을 그대로 파일 오프셋으로 쓰는 것.

## 막혔을 때 다음 체크
- 어느 섹션이 어떤 RVA 범위를 담당하는지, 그리고 섹션 테이블 자체의 구조가 헷갈리면 → [`./rev-0029-section-vs-segment.md`](./rev-0029-section-vs-segment.md)로 이동해서 섹션(PE)/세그먼트(ELF) 테이블 자체를 먼저 확인.
- 32비트/64비트에 따라 ImageBase나 주소 필드의 바이트 크기가 왜 다른지 궁금하면 → [`./rev-0021-x86-vs-x64.md`](./rev-0021-x86-vs-x64.md)로 이동.
- 헥스에디터에서 4바이트/8바이트 주소값을 읽었는데 순서가 이상해 보이면 → [`./rev-0023-endianness.md`](./rev-0023-endianness.md)로 이동해서 리틀엔디안 바이트 순서부터 확인.
- ASLR 때문에 매번 VA가 바뀌어서 디버깅 재현이 안 되면 → PIE/ASLR 전용 글(준비 중, 이 위키에 별도 항목으로 추가 예정)에서 다룰 예정이니 그때까지는 이 글의 "RVA/파일오프셋은 고정, VA만 바뀜" 원칙을 우선 적용.
- 아예 실행 중인 프로세스가 아니라 크래시 덤프나 메모리 덤프 파일을 분석 중이라면, 덤프 툴이 기록해 둔 로드 베이스 값을 먼저 확인하고 그 값을 이번 글의 ImageBase 자리에 대입해서 같은 공식을 적용.

## 미니 예제
64비트 ELF 바이너리를 하나 받아서 `readelf -l ./binary`를 실행했더니 다음과 같이 나왔다고 하자(값은 예시).

```
Program Headers:
  Type           Offset             VirtAddr           PhysAddr
                 FileSiz            MemSiz              Flags  Align
  LOAD           0x0000000000000000 0x0000000000000000 0x0000000000000000
                 0x0000000000000710 0x0000000000000710  R      0x1000
  LOAD           0x0000000000001000 0x0000000000001000 0x0000000000001000
                 0x00000000000001a5 0x00000000000001a5  R E    0x1000
```

두 번째 `LOAD` 세그먼트(실행 가능, `R E`)를 보면 `Offset = 0x1000`, `VirtAddr = 0x1000`으로 값이 우연히 같다. 이 바이너리가 PIE라면 이 `VirtAddr`는 절대 VA가 아니라 "로드 베이스로부터의 상대 주소"로 해석해야 한다. 실제로 GDB로 이 프로세스를 실행 중에 붙여서 `info proc mappings`로 실제 로드 베이스(예: `0x5555_55554000`)를 확인하면, 실제 VA는 `로드베이스 + 0x1000`이 된다 — PE의 `ImageBase + RVA` 공식과 완전히 같은 구조다. 반면 정적으로 파일만 열어서 분석할 때(objdump, readelf, IDA를 정적 모드로 열었을 때)는 `Offset` 값을 그대로 헥스에디터 오프셋으로 써서 바이트를 찾으면 된다. 이 예제에서 눈여겨볼 점은, PE든 ELF든 "파일에 고정으로 박혀 있는 상대적 위치(RVA/VirtAddr, Offset)"와 "실행 중에만 확정되는 절대 위치(VA)"라는 같은 구조를 공유한다는 것이다.

실무 워크플로 관점에서 보면, IDA나 Ghidra 같은 디스어셈블러를 쓰는 동안에는 이 계산을 거의 의식하지 않아도 된다 — 둘 다 화면에 VA(또는 IDA가 리베이스하지 않은 상태라면 RVA 기준 주소)를 직접 보여주고, 그 주소로 바로 점프까지 시켜주기 때문이다. 이 변환이 실제로 필요해지는 순간은 세 가지다: (1) 헥스에디터로 바이트를 직접 패치해야 할 때 IDA에서 본 주소를 파일 위치로 옮겨야 하는 경우, (2) 직접 PE/ELF 파서나 로더 스크립트를 작성할 때, (3) 라이브 프로세스가 아니라 파일로 떨어진 메모리 덤프를 분석할 때. 이 세 상황에서는 오늘 다룬 공식(`VA = ImageBase + RVA`, `FileOffset = RVA - Section.VirtualAddress + Section.PointerToRawData`)을 직접 손으로 적용해야 한다.

## 관련 글
- [`./rev-0019-binary-basics.md`](./rev-0019-binary-basics.md) — 바이너리 기초 전반
- [`./rev-0021-x86-vs-x64.md`](./rev-0021-x86-vs-x64.md) — 32/64비트에 따른 주소 필드 크기 차이(PE32 vs PE32+)
- [`./rev-0023-endianness.md`](./rev-0023-endianness.md) — 주소 필드가 파일에 저장되는 바이트 순서(리틀엔디안)
- [`./rev-0029-section-vs-segment.md`](./rev-0029-section-vs-segment.md) — RVA-파일오프셋 변환에 쓰이는 섹션(PE)/세그먼트(ELF) 테이블 구조

## 출처/검증
- PE 포맷의 `ImageBase`, `AddressOfEntryPoint`, 섹션 헤더 `VirtualAddress`/`PointerToRawData` 정의: Microsoft PE Format 공식 문서(`docs.microsoft.com`, PE Format 스펙) 기준 개념 설명 (2026-09-08 검증).
- ELF 프로그램 헤더 `p_vaddr`/`p_offset`/`p_filesz`, 섹션 헤더 `sh_addr`/`sh_offset` 정의: System V Application Binary Interface / ELF 공식 스펙 문서 기준.
- `readelf`, `objdump` 사용법: GNU Binutils 공식 매뉴얼 기준.
