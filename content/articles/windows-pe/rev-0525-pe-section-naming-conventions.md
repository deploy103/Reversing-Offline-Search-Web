---
id: REV-0525
title: "PE Section 이름 관례 사전(.text .rdata .data .rsrc 등)"
slug: "rev-0525-pe-section-naming-conventions"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, PE-bear]
keywords: [".text", ".rdata", ".data", ".rsrc", ".reloc", ".pdata", ".idata", ".tls", "섹션 이름"]
aliases: ["PE 섹션 이름 목록", "섹션 이름별 용도", ".text .data 차이"]
symptom_keywords: [".text가 뭔지 모르겠다", ".rdata와 .data 차이를 모르겠다", ".rsrc가 뭔지 모르겠다", "섹션 이름만 보고 용도를 짐작하고 싶다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`.text`, `.rdata`, `.data`, `.rsrc`, `.reloc` 등 PE 섹션 이름은 컴파일러/링커가 관례적으로 붙이는 이름일 뿐 PE 로더가 이름 자체를 강제로 해석하지는 않지만(실제 동작은 섹션 헤더의 `Characteristics` 플래그가 결정), 이 관례를 알아두면 섹션 이름만 보고도 "여기는 실행 코드, 여기는 읽기 전용 상수, 여기는 리소스"라고 즉시 감을 잡을 수 있어 분석 속도가 크게 빨라진다.

## 언제 검색해야 하나
- IDA나 PE-bear에서 섹션 목록을 보다가 `.text`, `.rdata`, `.data` 외에 낯선 이름(`.pdata`, `.tls`, `.idata`)이 나와서 용도를 확인해야 할 때
- 패킹된 바이너리에서 섹션 이름이 `UPX0`, `UPX1`처럼 표준 관례를 벗어나 있어 패커 흔적을 판단해야 할 때
- 어떤 섹션이 쓰기 가능(W)한지, 실행 가능(X)한지 이름만으로 1차 추정하고 싶을 때
- 특정 데이터(문자열, 상수, 전역 변수)가 어느 섹션에 위치해야 정상인지 확인할 때

## 핵심 개념
섹션 이름은 섹션 헤더(`IMAGE_SECTION_HEADER`)의 `Name` 필드(8바이트, NUL로 안 끝날 수도 있음)에 저장되며, Microsoft 링커(link.exe)와 다른 컴파일러 툴체인(MinGW/GCC 등)이 관례적으로 아래 이름을 사용한다.

| 섹션 이름 | 일반적 내용 | 전형적 Characteristics |
|---|---|---|
| `.text` | 실행 코드(함수 본문) | 읽기(R) + 실행(X), 쓰기 불가 |
| `.rdata` | 읽기 전용 데이터: 문자열 리터럴, `const` 전역 변수, 임포트 디렉터리 정보 일부, vtable | 읽기(R)만 |
| `.data` | 초기화된 쓰기 가능 전역/정적 변수 | 읽기(R) + 쓰기(W) |
| `.bss` | 초기화 안 된(0으로 채워질) 전역/정적 변수 — 파일에는 실제 데이터 없이 크기만 존재(VirtualSize > SizeOfRawData) | 읽기(R) + 쓰기(W) |
| `.rsrc` | 리소스(아이콘, 문자열 테이블, 다이얼로그, 버전 정보 등), 트리 구조(`IMAGE_RESOURCE_DIRECTORY`) | 읽기(R)만 |
| `.reloc` | 베이스 재배치(relocation) 테이블 — ASLR로 이미지가 선호 베이스가 아닌 곳에 로드될 때 주소를 고쳐주는 정보 | 읽기(R)만, 로드 후 종종 discardable |
| `.idata` | 임포트 테이블(구버전 링커나 별도 옵션 사용 시 별도 섹션; 최신 링커는 보통 `.rdata`에 병합) | 읽기(R) + 쓰기(W)(IAT 부분) |
| `.edata` | 익스포트 테이블(주로 DLL) | 읽기(R)만 |
| `.pdata` | x64/ARM64 예외 처리용 함수 테이블(`RUNTIME_FUNCTION` 배열) — x86에는 보통 없음(SEH 방식이 다름) | 읽기(R)만 |
| `.tls` | 스레드 지역 저장소(Thread Local Storage) 데이터 및 콜백 배열(REV-0133 참고) | 읽기(R) + 쓰기(W) |
| `.xdata` | 예외 처리 언와인드 정보(x64), `.pdata`가 가리키는 상세 데이터 | 읽기(R)만 |
| `.didat` | 지연 로드(Delay Load) 임포트 테이블 | 읽기(R) + 쓰기(W) |
| `.rsrc$01` 등 | 리소스 하위 세그먼트(링크 단계 임시, 최종 바이너리에는 `.rsrc`로 병합됨) | - |

섹션 이름이 표준 이름이 아니거나(예: `UPX0`, `UPX1`, `.aspack`, 임의의 5바이트 문자열), 표준 이름인데 `Characteristics`가 관례와 다르면(예: `.text`인데 쓰기 가능 플래그가 있음) 패킹/난독화/자가 수정 코드의 강력한 단서다. 실행 압축기(UPX 등)는 압축 해제 스텁이 원본 코드를 메모리에 풀어써야 하므로 실행 가능한 섹션에 쓰기 권한까지 부여하는 경우가 흔하다.

## 화면/코드에서 보이는 징후
- IDA의 세그먼트 목록(`Ctrl+S`)이나 PE-bear의 "Section Headers" 탭에 위 표의 이름들이 순서대로(`.text` → `.rdata` → `.data` → ... → `.rsrc` → `.reloc`) 나열됨(정확한 순서는 링커/버전마다 다를 수 있음)
- `.text` 섹션인데 `IMAGE_SCN_MEM_WRITE`(쓰기 가능) 플래그가 켜져 있으면 자가 수정 코드나 패킹 스텁 의심
- 섹션 이름이 `.text`가 아니라 임의 문자열(`.aaaa`, `UPX0`)이면 이름 자체를 링커가 아니라 패커/난독화 도구가 임의로 붙인 것

## 가장 먼저 할 것
1. PE-bear나 IDA에서 섹션 목록을 열어 이름, 크기(VirtualSize/SizeOfRawData), Characteristics 플래그를 한눈에 확인한다.
2. `.text`의 실행/쓰기 플래그, `.rsrc`/`.reloc`의 존재 여부부터 확인해 표준 컴파일 결과물인지 패킹된 것인지 1차 판단한다.
3. 분석하려는 데이터(문자열, 상수, 전역 변수)가 어느 섹션에 있는지 주소로 역산해서(REV-0118 RVA/VA 변환) 정상적인 위치인지 확인한다.

## 단계별 절차
**1) PE-bear로 확인**
- "Section Headers" 탭에서 각 섹션의 `Name`, `VirtualSize`, `VirtualAddress`, `SizeOfRawData`, `PointerToRawData`, `Characteristics`를 한 화면에서 비교한다.
- Characteristics 열의 R/W/X 표시로 권한 조합을 바로 확인한다.

**2) IDA로 확인**
- `Ctrl+S`(세그먼트 목록)에서 각 섹션이 코드(`CODE`)인지 데이터(`DATA`)인지 IDA가 자동 분류한 타입도 함께 본다.
- 낯선 섹션 이름이 있으면 그 섹션의 시작 주소로 이동(`G`)해서 실제 데이터 패턴(코드처럼 보이는지, 압축된 것처럼 엔트로피가 높은지)을 직접 눈으로 확인한다.

## 명령어/단축키
- PE-bear: "Section Headers" 탭
- IDA: `Ctrl+S`(세그먼트 목록), `G`(주소 이동)

## 출력 해석
- `VirtualSize`가 `SizeOfRawData`보다 훨씬 크면 `.bss`처럼 파일에는 없고 메모리에서만 0으로 채워지는 영역이 있다는 뜻이다.
- Characteristics에 `IMAGE_SCN_MEM_EXECUTE`(0x20000000)와 `IMAGE_SCN_MEM_WRITE`(0x80000000)가 동시에 켜진 섹션이 있으면 패킹/자가 수정 코드 가능성이 높은 강한 신호다.
- `.reloc` 섹션이 통째로 없으면 이 바이너리는 ASLR을 지원하지 않을 가능성이 있다(단, `/DYNAMICBASE:NO`로 링크했거나 고정 베이스를 강제한 경우).

## 흔한 실수
- 섹션 이름이 PE 로더의 동작을 직접 결정한다고 착각하는 것 — 실제로 로더가 참조하는 것은 이름이 아니라 `Characteristics` 플래그와 `DataDirectory`의 RVA다. 이름은 순전히 사람이 읽기 위한 관례다.
- `.rdata`와 `.data`를 혼동해서 상수(`const`)와 일반 전역 변수를 같은 곳에서 찾으려는 것.
- UPX 등으로 패킹된 파일에서 `.text`가 비어 보이는(엔트로피가 낮거나 코드가 거의 없는) 것을 보고 "코드가 없다"고 결론짓는 것 — 실제 코드는 언패킹 스텁이 실행될 때 다른 섹션에서 풀려 나온다.
- `.pdata`가 x86 바이너리에도 항상 있다고 가정하는 것 — 이는 x64/ARM64의 테이블 기반 예외 처리에 필요한 섹션이며 x86은 다른 SEH 메커니즘(REV-0134)을 쓴다.

## 막혔을 때 다음 체크
- 섹션 헤더 구조체 자체의 필드(VirtualAddress, PointerToRawData 등)가 궁금하면 → REV-0117(PE Section Table 읽기)을 먼저 본다.
- 옵셔널 헤더의 DataDirectory가 각 섹션과 어떻게 연결되는지 궁금하면 → REV-0524(PE Optional Header 필드 전체 사전)를 본다.
- RVA와 파일 오프셋 변환 계산이 필요하면 → REV-0118(RVA VA Raw Offset)을 본다.

## 미니 예제
PE-bear로 일반적인 Release 빌드 x64 EXE를 열면 대략 다음과 같은 섹션 목록이 나온다.

```text
Name     VirtualSize   Characteristics
.text    0x00015000    CODE, EXECUTE, READ
.rdata   0x0000A200    INITIALIZED_DATA, READ
.data    0x00001800    INITIALIZED_DATA, READ, WRITE
.pdata   0x00000C00    INITIALIZED_DATA, READ
.rsrc    0x00002000    INITIALIZED_DATA, READ
.reloc   0x00000600    INITIALIZED_DATA, READ, DISCARDABLE
```

이 목록만 보고도 "실행 코드는 `.text`에 있고, 상수 문자열은 `.rdata`, 전역 변수는 `.data`, 아이콘/버전 정보는 `.rsrc`에 있으며, ASLR 재배치 정보(`.reloc`)도 정상적으로 존재하는 표준적인 컴파일 결과물"이라는 것을 바로 알 수 있다. 만약 여기서 섹션 이름이 `UPX0`/`UPX1`로 바뀌어 있었다면 UPX로 패킹된 파일임을 즉시 의심할 수 있다.

## 관련 글
- REV-0117 — PE Section Table 읽기
- REV-0524 — PE Optional Header 필드 전체 사전
- REV-0118 — RVA VA Raw Offset 계산

## 출처/검증
- 각 섹션 이름의 관례적 용도(`.text`/`.rdata`/`.data`/`.bss`/`.rsrc`/`.reloc`/`.pdata`/`.tls`/`.idata`/`.edata`)와 `IMAGE_SCN_MEM_EXECUTE`/`IMAGE_SCN_MEM_WRITE` 등 Characteristics 플래그는 Microsoft PE/COFF 파일 형식 공식 사양 및 Microsoft 링커 문서 기준이다.
- UPX 등 실행 압축기가 실행+쓰기 권한을 가진 섹션을 만드는 경향은 일반적인 리버싱/패커 분석 레퍼런스 기준이며, 모든 패커에 동일하게 해당하지는 않는다.
- 위 미니 예제의 수치는 설명을 위해 구성한 근사값이며 특정 실제 바이너리를 덤프한 값이 아니다(2026-09-08 기준 서술).
