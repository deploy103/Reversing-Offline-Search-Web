---
id: REV-0526
title: "PE Characteristics 플래그 사전"
slug: "rev-0526-pe-characteristics-flags"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["IMAGE_FILE_HEADER", "Characteristics", "IMAGE_FILE_EXECUTABLE_IMAGE", "IMAGE_FILE_DLL", "IMAGE_FILE_LARGE_ADDRESS_AWARE", "PE 헤더 플래그"]
aliases: ["PE Characteristics 필드", "IMAGE_FILE_HEADER Characteristics", "파일 헤더 플래그 사전", "PE 특성 플래그"]
symptom_keywords: ["Characteristics 값이 0x102라는데 무슨 뜻인지 모르겠음", "이 파일이 EXE인지 DLL인지 헤더로 구분하고 싶음", "PE-bear에서 Characteristics 열이 이상한 16진수로 나옴", "32비트인지 64비트인지 헤더에서 확인하고 싶음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`IMAGE_FILE_HEADER`의 `Characteristics` 필드는 16비트 안에 "이 파일이 실행 가능한가", "DLL인가", "32비트 전용인가" 같은 여러 개의 참/거짓 정보를 비트마다 하나씩 압축해 넣은 값으로, PE-bear나 IDA에서 `0x0102` 같은 16진수만 보고도 각 비트를 분해하면 파일의 기본 성격을 바로 읽어낼 수 있다.

## 언제 검색해야 하나
- PE-bear/IDA의 File Header(또는 COFF Header) 창에서 `Characteristics: 0x...` 값을 보고 이게 정확히 무슨 뜻인지 찾아보고 싶을 때
- 분석 중인 파일이 EXE인지 DLL인지, 또는 시스템 파일인지 헤더 값만으로 빠르게 구분하고 싶을 때
- `IMAGE_FILE_LARGE_ADDRESS_AWARE` 같은 특정 플래그 이름을 코드나 도구 출력에서 보고 뜻을 확인하고 싶을 때
- CTF 문제 파일이 스트립되어 있거나(디버그 정보 없음) 특이한 헤더 플래그를 갖고 있어서 그 의미를 알아야 할 때

## 핵심 개념

### 필드 위치와 크기
`Characteristics`는 `IMAGE_FILE_HEADER`(REV-0116에서 다룬 File/COFF 헤더) 안에 있는 `WORD`(2바이트, 16비트) 필드다. DOS 헤더의 `e_lfanew`가 가리키는 PE 시그니처(`"PE\0\0"`) 바로 다음, `IMAGE_FILE_HEADER` 구조체의 마지막 멤버로 위치한다.

```c
typedef struct _IMAGE_FILE_HEADER {
  WORD  Machine;
  WORD  NumberOfSections;
  DWORD TimeDateStamp;
  DWORD PointerToSymbolTable;
  DWORD NumberOfSymbols;
  WORD  SizeOfOptionalHeader;
  WORD  Characteristics;      // 이 문서가 다루는 필드
} IMAGE_FILE_HEADER, *PIMAGE_FILE_HEADER;
```

16비트이므로 최대 16개의 개별 플래그를 비트 OR로 조합해 표현한다. 도구에 표시되는 `0x0102` 같은 값은 여러 플래그가 동시에 켜져 있다는 뜻이며, 그 값을 이진수로 펼쳐서 각 비트를 확인해야 정확히 해석할 수 있다.

### 자주 보는 플래그 값 표
| 플래그 이름 | 값 | 의미 |
|---|---|---|
| `IMAGE_FILE_RELOCS_STRIPPED` | `0x0001` | 재배치 정보가 없음(고정 주소 로드 전제) |
| `IMAGE_FILE_EXECUTABLE_IMAGE` | `0x0002` | 실행 가능한 이미지(링크 성공, 유효한 EXE/DLL) |
| `IMAGE_FILE_LINE_NUMS_STRIPPED` | `0x0004` | (구식) 줄 번호 정보 제거됨, 현재는 미사용 취급 |
| `IMAGE_FILE_LOCAL_SYMS_STRIPPED` | `0x0008` | (구식) 로컬 심볼 제거됨, 현재는 미사용 취급 |
| `IMAGE_FILE_AGGRESSIVE_WS_TRIM` | `0x0010` | (구식, Windows 2000 이후 미사용) |
| `IMAGE_FILE_LARGE_ADDRESS_AWARE` | `0x0020` | 2GB 이상 주소 공간 지원(x86에서 `/LARGEADDRESSAWARE` 링크 옵션) |
| `IMAGE_FILE_BYTES_REVERSED_LO` | `0x0080` | (구식, 사용 안 함) |
| `IMAGE_FILE_32BIT_MACHINE` | `0x0100` | 32비트 워드 머신 기반(주로 x86 EXE/DLL에서 켜짐) |
| `IMAGE_FILE_DEBUG_STRIPPED` | `0x0200` | 디버그 정보가 별도 파일(.dbg/.pdb)로 분리됨 |
| `IMAGE_FILE_REMOVABLE_RUN_FROM_SWAP` | `0x0400` | 이동식 미디어에 있으면 스왑에 복사 후 실행 |
| `IMAGE_FILE_NET_RUN_FROM_SWAP` | `0x0800` | 네트워크 드라이브에 있으면 스왑에 복사 후 실행 |
| `IMAGE_FILE_SYSTEM` | `0x1000` | 시스템 파일(사용자 프로그램 아님, 드라이버 등) |
| `IMAGE_FILE_DLL` | `0x2000` | 이미지가 DLL(EXE가 아님) |
| `IMAGE_FILE_UP_SYSTEM_ONLY` | `0x4000` | 단일 프로세서 시스템에서만 실행 가능(사실상 미사용) |
| `IMAGE_FILE_BYTES_REVERSED_HI` | `0x8000` | (구식, 사용 안 함) |

### 대표적인 조합 해석
- 일반적인 64비트 EXE: `IMAGE_FILE_EXECUTABLE_IMAGE`(`0x0002`) + `IMAGE_FILE_LARGE_ADDRESS_AWARE`(`0x0020`) → `0x0022`
- 일반적인 32비트 DLL: `IMAGE_FILE_EXECUTABLE_IMAGE`(`0x0002`) + `IMAGE_FILE_32BIT_MACHINE`(`0x0100`) + `IMAGE_FILE_DLL`(`0x2000`) → `0x2102`
- 재배치 정보를 제거한 32비트 EXE: `0x0001 | 0x0002 | 0x0100` = `0x0103`

### 32비트/64비트 구분은 이 필드만으로 안 됨
`IMAGE_FILE_32BIT_MACHINE` 플래그가 켜져 있다고 곧바로 "32비트 실행 파일"이라고 단정하면 안 된다. 실제 아키텍처(x86 vs x64 vs ARM)는 `IMAGE_FILE_HEADER.Machine` 필드(`0x014c`=x86, `0x8664`=x64, `0xAA64`=ARM64)로 판단해야 하며, `Characteristics`의 이 비트는 어디까지나 보조 정보다. `Machine` 필드 확인은 REV-0116을 함께 참고한다.

## 화면/코드에서 보이는 징후
- PE-bear의 File Header 탭에서 `Characteristics` 값이 16진수로 표시되고, 옆에 각 플래그를 체크리스트 형태로 펼쳐 보여주는 UI가 있다.
- IDA의 `File > Produce file > ...` 또는 로드 시 콘솔 로그에 `Characteristics: EXECUTABLE_IMAGE, ...` 같은 텍스트로 이미 해석되어 나오는 경우가 많다.
- `IMAGE_FILE_DLL` 비트가 켜진 파일을 IDA로 열면 확장자가 `.exe`여도 IDA가 DLL로 인식하고 그에 맞는 분석(Export 우선 등)을 시도한다.

## 가장 먼저 할 것
PE-bear 또는 IDA에서 `Characteristics` 16진수 값을 확인한 뒤, 위 표를 이용해 어떤 비트들이 켜져 있는지 하나씩 AND 연산으로 분해한다. 특히 `IMAGE_FILE_DLL`(`0x2000`)과 `IMAGE_FILE_EXECUTABLE_IMAGE`(`0x0002`) 두 비트만 먼저 확인해도 이 파일의 기본 성격(EXE vs DLL, 유효한 이미지인지)을 바로 알 수 있다.

## 단계별 절차

**1) 값 확보**

PE-bear의 DOS/File Header 탭 또는 IDA의 헤더 정보에서 `Characteristics` 필드의 16진수 값을 읽는다.

**2) 이진수로 펼치기**

예를 들어 `0x0122`라면 2진수로 `0000 0001 0010 0010`이다. 각 자리에서 1인 비트의 위치를 위 표와 대조한다.
```text
0x0122 = 0x0002 | 0x0020 | 0x0100
       = IMAGE_FILE_EXECUTABLE_IMAGE
       | IMAGE_FILE_LARGE_ADDRESS_AWARE
       | IMAGE_FILE_32BIT_MACHINE
```

**3) DLL 여부 우선 확인**

`값 & 0x2000`이 0이 아니면 DLL, 0이면 EXE(또는 다른 이미지 형태)로 우선 분류한다.

**4) 실행 가능 여부 확인**

`값 & 0x0002`가 0이면 링크가 실패했거나 손상된 이미지일 가능성이 있으므로, 파일 자체가 온전한지 다시 점검한다.

**5) 특이 플래그 별도 메모**

`IMAGE_FILE_SYSTEM`(드라이버/시스템 파일 가능성), `IMAGE_FILE_RELOCS_STRIPPED`(재배치 없음, ASLR과 연관) 같은 흔치 않은 비트가 켜져 있으면 분석 노트에 별도로 기록해둔다.

## 명령어/단축키
- PE-bear: DOS/File Header 탭에서 `Characteristics` 값과 해석된 플래그 목록 확인
- IDA: `File > Load file > PE ...` 또는 Output 창의 초기 로드 로그에서 헤더 요약 확인
- x64dbg: Memory Map/Symbols 창에서는 직접 노출되지 않으므로, 정적 분석 도구(PE-bear/IDA)로 먼저 확인하는 것을 권장

## 출력 해석
- `0x2000` 비트가 켜져 있으면 이 파일은 DLL이며, IDA/x64dbg가 진입점을 `DllMain`으로 취급하고 단독 실행이 되지 않는 것이 정상이다.
- `0x0020`(`LARGE_ADDRESS_AWARE`)이 켜진 32비트 파일은 2GB가 아니라 최대 4GB 가까이 주소 공간을 쓸 수 있으므로, 포인터/오프셋 계산에서 큰 값이 나와도 오버플로로 의심하기 전에 이 플래그를 먼저 확인한다.
- `0x0001`(`RELOCS_STRIPPED`)이 켜진 EXE는 재배치 테이블이 없어 ASLR을 적용할 수 없는 경우가 많아, 매번 같은 베이스 주소로 로드되는 경향이 있다 — 디버깅 중 주소가 재부팅해도 안 바뀌는 이유를 여기서 확인할 수 있다.

## 흔한 실수
- `IMAGE_FILE_32BIT_MACHINE` 비트만 보고 파일 아키텍처를 x86으로 단정하는 것 — 반드시 `Machine` 필드도 함께 확인해야 한다.
- 여러 플래그가 OR로 합쳐진 값을 표에서 그대로 찾으려다가 못 찾고 "알 수 없는 값"이라고 결론 내리는 것 — 반드시 비트 단위로 분해해야 한다.
- `Characteristics`와 `DllCharacteristics`(Optional Header에 있는 별도 필드, ASLR/DEP 등과 관련)를 같은 필드로 혼동하는 것 — 이름이 비슷하지만 완전히 다른 필드다.

## 막혔을 때 다음 체크
- `IMAGE_FILE_HEADER` 전체 구조와 다른 필드들이 궁금하다면 → REV-0116 PE Header COFF Optional Header 읽기
- `DllCharacteristics`(Optional Header의 ASLR/DEP 관련 필드)가 궁금하다면 → 관련 항목은 이후 windows-pe 카테고리 문서에서 별도로 다룬다
- 이 값을 실제 도구에서 확인하는 법이 낯설다면 → REV-0125(PE-bear 기초) 문서를 먼저 참고

## 미니 예제
```text
DOS/File Header 탭에서 확인한 값:
Machine           = 0x8664   (IMAGE_FILE_MACHINE_AMD64)
NumberOfSections  = 0x0006
Characteristics   = 0x0022

0x0022 = 0x0002 | 0x0020
       = IMAGE_FILE_EXECUTABLE_IMAGE | IMAGE_FILE_LARGE_ADDRESS_AWARE

해석: 이 파일은 x64용으로 컴파일된 정상 실행 이미지이며,
LARGE_ADDRESS_AWARE가 켜져 있다(64비트에서는 이 플래그가 사실상 항상 켜져 있는 것이 정상).
```

## 관련 글
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0527 — x64 Calling Convention 레지스터 사용 빠른 참조표
- REV-0530 — Windows 프로세스 생성 플래그 빠른 참조표

## 출처/검증
- `IMAGE_FILE_HEADER`와 `Characteristics` 플래그 값은 Microsoft 공식 PE/COFF 사양 문서(learn.microsoft.com, "PE Format", winnt.h의 `IMAGE_FILE_*` 상수) 기준(2026-09-08 확인).
