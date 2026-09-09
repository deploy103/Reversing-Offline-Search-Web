---
id: REV-0840
title: "브레이크포인트를 파일 오프셋으로 걸었는데 실제 메모리 주소랑 안 맞을 때"
slug: "rev-0840-file-offset-vs-memory-address-mismatch"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords: ["파일 오프셋 vs VA", "RVA ImageBase", "ELF p_offset p_vaddr", "SectionAlignment FileAlignment", "헥스에디터 오프셋 브레이크포인트"]
aliases: ["파일 오프셋으로 걸었는데 안 맞음", "hex editor 오프셋과 디버거 주소가 다름", "raw offset과 VA 혼동"]
symptom_keywords: ["헥스에디터에서 본 오프셋으로 브레이크포인트를 걸었는데 엉뚱한 곳", "파일에서 본 주소와 디버거 주소가 다름", "RVA를 그대로 걸었더니 안 맞음", "IDA 주소와 파일 오프셋이 헷갈림"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
헥스에디터/IDA의 "파일 오프셋"과 디버거가 실제로 멈추는 "메모리 주소(VA)"는 애초에 서로 다른 좌표계이며, PE는 `VA = ImageBase + RVA`(RVA는 섹션의 `FileAlignment` 기준 파일 오프셋과 `SectionAlignment` 기준 메모리 오프셋이 서로 다르게 매핑됨), ELF는 `VA = 로드베이스 + p_vaddr`(파일에서는 `p_offset`)로 계산되므로, 이 변환 없이 파일 오프셋 숫자를 그대로 디버거에 넣으면 전혀 다른 위치를 가리키게 된다.

## 언제 검색해야 하나
- HxD/ImHex 같은 헥스에디터에서 확인한 오프셋을 x64dbg나 GDB에 그대로 입력했는데 엉뚱한 곳에서 멈추거나 아예 안 멈출 때
- IDA의 정적 분석 주소(가상 주소로 표시됨)와 파일을 직접 열었을 때의 바이트 위치가 안 맞아 헷갈릴 때
- PE 섹션의 `FileAlignment`(보통 0x200)와 `SectionAlignment`(보통 0x1000)가 달라서 오프셋 계산이 어긋날 때
- ELF 프로그램 헤더의 `p_offset`과 `p_vaddr`가 왜 다른 값인지 궁금할 때

## 핵심 개념

### 파일 오프셋과 VA(Virtual Address)는 다른 좌표계다
디스크에 저장된 실행 파일은 섹션들이 촘촘하게(파일 정렬 단위로) 이어져 있지만, 메모리에 로드될 때는 각 섹션이 페이지 정렬 단위로 널찍하게 배치된다. 그래서 "파일에서 1000바이트 지점"과 "메모리에서 1000바이트 오프셋 지점"은 섹션 경계를 넘어가는 순간부터 서로 다른 값이 된다. 개념 자체와 계산 공식은 REV-0028(주소 VA RVA File Offset 차이), PE 한정 상세 계산은 REV-0118(RVA VA Raw Offset 계산)에서 다룬다.

### PE — FileAlignment vs SectionAlignment
PE Optional Header의 `FileAlignment`(디스크상 섹션 정렬 단위, 보통 0x200)와 `SectionAlignment`(메모리상 정렬 단위, 보통 0x1000)가 다르면, 같은 섹션 안에서도 "파일 오프셋 - 섹션의 PointerToRawData"와 "RVA - 섹션의 VirtualAddress"가 같은 값이 아니게 되는 구간이 생길 수 있다. 실행 중 주소(VA)는 `ImageBase + RVA`로 계산하며, 파일 오프셋에서 RVA로 가려면 반드시 그 오프셋이 속한 섹션의 `PointerToRawData`/`VirtualAddress`를 기준으로 변환해야 한다.

### ELF — p_offset vs p_vaddr, 그리고 PIE 베이스
ELF 프로그램 헤더(`Elf64_Phdr`)의 `p_offset`은 파일 안에서의 위치, `p_vaddr`는 그 세그먼트가 매핑될 가상 주소다. 고정 베이스 실행 파일(`ET_EXEC`)은 `p_vaddr`가 절대 주소지만, PIE(`ET_DYN`)는 `p_vaddr`조차 "베이스를 0으로 가정한 상대값"이라 실제 VA를 얻으려면 커널이 정한 런타임 로드 베이스를 더해야 한다. PIE/ASLR 베이스 계산의 상세 절차는 REV-0194에서 다룬다.

### 왜 "파일 오프셋 그대로" 걸면 안 걸리거나 엉뚱한 곳에서 걸리는가
디버거의 `break *0x주소`(GDB), `bp 0x주소`(x64dbg)는 항상 **VA**를 기대한다. 헥스에디터에서 본 파일 오프셋 숫자를 변환 없이 그대로 넣으면, 우연히 해당 섹션의 오프셋 차이가 0인 극히 일부 구간이 아닌 이상 다른 바이트를 가리키게 되어 브레이크포인트가 무의미한 위치에 걸린다.

## 화면/코드에서 보이는 징후
- 헥스에디터 오프셋을 그대로 `bp`/`break *`에 넣었는데 실행 중 전혀 다른(또는 무의미한) 명령어에서 멈춤
- IDA에서 같은 위치를 볼 때 "가상 주소"와 "파일 오프셋"이 서로 다른 두 개의 숫자로 표시됨(Options → General에서 어느 쪽을 보고 있는지 확인 가능)
- PE-bear/`readelf -l`으로 확인한 섹션/세그먼트의 오프셋과 가상 주소 값이 서로 다름

## 가장 먼저 할 것
지금 갖고 있는 숫자가 "파일 오프셋"인지 "가상 주소(VA/RVA)"인지부터 명확히 한다. IDA라면 상태 표시줄이나 Options에서 현재 보고 있는 좌표계를 확인하고, 헥스에디터에서 얻은 값이라면 반드시 변환을 거친다.

## 단계별 절차
1. PE: `PE-bear`나 `readelf`(ELF)로 섹션/세그먼트 테이블을 열어, 문제의 오프셋이 속한 섹션의 `PointerToRawData`/`VirtualAddress`(PE) 또는 `p_offset`/`p_vaddr`(ELF)를 확인한다.
2. RVA = 파일오프셋 - PointerToRawData + VirtualAddress (PE) 로 변환한다.
3. VA = ImageBase + RVA (PE, 고정 베이스라면 그대로, ASLR이면 실제 로드 베이스로 대체) 를 계산한다.
4. ELF: VA = 런타임 로드 베이스 + (p_vaddr + (파일오프셋 - p_offset)) 로 변환한다(비PIE는 로드 베이스가 0이라 p_vaddr가 곧 VA).
5. 변환한 VA로 다시 브레이크포인트를 건다.
6. IDA를 쓴다면 애초에 파일 오프셋 대신 IDA가 보여주는 가상 주소를 그대로 복사해서 쓰는 것이 계산 실수를 줄이는 가장 안전한 방법이다.

## 명령어/단축키
```bash
readelf -l ./chall        # ELF 프로그램 헤더: p_offset, p_vaddr
objdump -h ./chall         # 섹션별 오프셋/VMA
```
```text
PE-bear: Section Headers 탭에서 PointerToRawData / VirtualAddress 확인
```
```gdb
break *(BASE + RVA)
```

## 출력 해석
`readelf -l`/`objdump -h`에서 같은 세그먼트/섹션의 두 값(파일 오프셋 계열, 가상 주소 계열)이 다르면 그 차이가 곧 변환에 필요한 보정값이다. PE-bear에서 `PointerToRawData`와 `VirtualAddress`가 다르면 마찬가지로 그 차이만큼 보정해야 한다.

## 흔한 실수
- IDA 화면에 나온 숫자가 파일 오프셋인지 VA인지 확인하지 않고 그대로 디버거에 입력하는 것.
- 여러 섹션에 걸친 범위인데 하나의 변환 공식(하나의 섹션 기준 보정값)만 전체에 적용하는 것 — 섹션마다 보정값이 다를 수 있다.
- PIE/ASLR 바이너리인데 비PIE처럼 `p_vaddr`를 절대 주소로 착각하는 것.
- `FileAlignment`와 `SectionAlignment`가 같다고 가정하고 계산하는 것 — 대부분의 컴파일러 기본값은 다르다.

## 막혔을 때 다음 체크
- VA/RVA/파일 오프셋 개념 자체가 헷갈린다면 → REV-0028 주소 VA RVA File Offset 차이
- PE에서의 구체적 계산 공식이 필요하다면 → REV-0118 RVA VA Raw Offset 계산
- PIE 바이너리라서 베이스 자체가 실행마다 바뀐다면 → REV-0194 PIE 바이너리 GDB 브레이크포인트 잡기
- 브레이크포인트가 다른 이유로도 안 걸리는 것 같다면 → REV-0835 브레이크포인트가 안 걸릴 때 확인할 것들

## 미니 예제
HxD에서 파일 오프셋 `0x600`에 흥미로운 바이트를 발견했다. `readelf -l`로 확인하니 그 오프셋을 포함하는 세그먼트가 `p_offset=0x0`, `p_vaddr=0x400000`(비PIE)였다. VA = 0x400000 + (0x600 - 0x0) = 0x400600으로 계산해 GDB에 `break *0x400600`을 걸자 정확히 그 지점에서 멈췄다.

## 관련 글
- REV-0028 — 주소 VA RVA File Offset 차이
- REV-0118 — RVA VA Raw Offset 계산
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기
- REV-0835 — 브레이크포인트가 안 걸릴 때 확인할 것들

## 출처/검증
- PE `FileAlignment`/`SectionAlignment`, `PointerToRawData`/`VirtualAddress`와 RVA/VA 계산: Microsoft PE/COFF 공식 문서 기준.
- ELF 프로그램 헤더 `p_offset`/`p_vaddr`와 `ET_DYN`(PIE)의 런타임 재배치: System V ABI ELF 명세 기준(2026-09-09 검증).
