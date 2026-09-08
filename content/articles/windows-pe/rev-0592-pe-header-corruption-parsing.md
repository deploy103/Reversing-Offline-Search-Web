---
id: REV-0592
title: "PE 헤더가 조작되어 도구가 잘못 파싱할 때"
slug: "rev-0592-pe-header-corruption-parsing"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", "HxD"]
keywords: ["PE 헤더 조작", "e_lfanew", "SizeOfOptionalHeader", "NumberOfSections", "loader 관용성", "pefile fast_load", "안티리버싱"]
aliases: ["ida에서 파일이 안열림", "pe-bear가 파일을 못읽음", "unsupported file format 오류"]
symptom_keywords: ["IDA에서 unknown format 오류가 뜬다", "PE-bear가 파일을 열지 못한다고 한다", "파일은 정상 실행되는데 분석 도구는 파싱을 거부한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
파일은 Windows에서 멀쩡히 실행되는데 IDA나 PE-bear가 "지원하지 않는 형식"이라며 열기를 거부하거나 잘못 파싱한다면, 이는 Windows 로더가 PE 헤더를 매우 관대하게(느슨하게) 해석하는 반면 정적 분석 도구들은 스펙을 더 엄격하게 검사하기 때문이며, 해결책은 헥스 에디터로 헤더 필드를 스펙에 맞게 직접 정상화하거나 더 관대한 파서(HxD+수동 계산, Python `pefile`)로 교차 검증하는 것이다.

## 언제 검색해야 하나
- IDA로 파일을 열었더니 PE로 인식하지 못하고 "Unknown file format"이라며 바이너리 파일로만 열릴 때
- PE-bear가 파일을 열자마자 오류 메시지를 띄우거나, 열리긴 하는데 섹션/임포트 정보가 이상하게 표시될 때
- CTF 문제 설명에 "이 파일은 헤더가 조작되어 있다"는 힌트가 있을 때
- 같은 파일이 실제로는 정상 실행되는데 분석 도구에서만 문제가 생겨서 원인이 헷갈릴 때

## 핵심 개념
Windows 로더(`ntdll.dll`의 이미지 매핑 로직)는 실행 성능과 하위 호환성을 위해 PE 헤더의 일부 필드에 대해 상당히 관대하다. 예를 들어 `IMAGE_DOS_HEADER.e_lfanew`(PE 헤더 시작 오프셋), `IMAGE_FILE_HEADER.SizeOfOptionalHeader`, 체크섬(`OptionalHeader.CheckSum`), 일부 예약 필드 등은 로더가 크게 신경 쓰지 않거나 다른 경로로 검증하기 때문에, 이 필드들을 스펙과 다르게 조작해도 실행 자체는 멀쩡히 되는 경우가 많다.

반면 IDA, PE-bear 같은 정적 분석 도구는 파일 형식을 "정확히" 해석하려고 하기 때문에, 스펙 위반(예: `NumberOfSections`가 실제 섹션 테이블 데이터와 안 맞음, `Magic` 필드가 `0x10b`/`0x20b`(PE32/PE32+) 중 어느 쪽도 아님, `SizeOfHeaders`가 비정상적으로 크거나 작음, 섹션의 `VirtualSize`/`SizeOfRawData`가 음수로 해석되는 값)을 만나면 파싱을 거부하거나, 검증 로직에 걸려 오류를 내거나, 심한 경우 잘못된 값으로 무한 루프/크래시를 일으키기도 한다. 이런 "로더와 분석 도구의 파싱 차이"는 실제 악성코드와 CTF anti-reversing 챌린지 양쪽에서 자주 악용되는 기법이다.

## 화면/코드에서 보이는 징후
- IDA가 "Unknown file format" 대화상자를 띄우며 PE로 인식하지 못함
- PE-bear가 파일을 열 때 헤더 검증 오류 팝업을 띄우거나, 열려도 Sections/Imports 탭이 비어있거나 깨짐
- 헥스 에디터로 직접 봤을 때 `4D 5A`(MZ) 시그니처와 `50 45 00 00`(PE\0\0) 시그니처는 정상인데, 그 사이 필드 값들이 비정상적으로 크거나 0으로 되어 있음
- Windows에서 더블클릭하면 파일이 정상적으로 실행됨(로더는 이 조작을 신경 쓰지 않음을 의미)

## 가장 먼저 할 것
헥스 에디터(HxD 등)로 파일을 열어 `IMAGE_DOS_HEADER`의 `e_lfanew`(오프셋 `0x3C`, 4바이트)부터 확인한다. 이 값이 파일 크기를 넘어서거나 명백히 이상한 값이면, 그 지점부터 PE 시그니처와 COFF 헤더를 스펙에 맞춰 하나씩 수동으로 검증한다.

## 단계별 절차
**1) DOS 헤더의 e_lfanew 확인**
- 오프셋 `0x3C`(4바이트, 리틀엔디안)를 읽는다. 이 값이 실제로 파일 안에서 `PE\0\0`(`50 45 00 00`) 시그니처가 있는 위치와 일치하는지 확인한다. 조작된 파일은 이 값이 일부러 틀리게 되어 있거나, 반대로 로더가 무시하는 다른 필드가 틀려 있을 수 있다.

**2) COFF File Header 필드 검증**
- `Machine`(오프셋 +4, 2바이트: `0x14c`=x86, `0x8664`=x64), `NumberOfSections`(오프셋 +6, 2바이트), `SizeOfOptionalHeader`(오프셋 +16, 2바이트)를 스펙과 대조한다.
- `NumberOfSections`가 실제 섹션 테이블에 있는 항목 수와 다르면, 도구에 따라 뒷부분을 아예 무시하거나 잘못된 개수만큼 파싱을 시도하다 깨진다.

**3) Optional Header의 Magic과 크기 필드 검증**
- `Magic`(오프셋 PE 헤더+24, 2바이트)이 `0x10B`(PE32)인지 `0x20B`(PE32+)인지 확인하고, 이후 필드 오프셋들이 이 값에 맞춰 다른 레이아웃(PE32는 `BaseOfData` 필드가 있고 PE32+는 없음)을 따르는지 확인한다. 이 구분을 틀리게 만들면 이후 모든 필드가 밀려서 잘못 읽힌다.

**4) 여러 도구로 교차 검증**
- IDA/PE-bear가 실패하면 Python `pefile` 라이브러리를 `pefile.PE(path, fast_load=True)` 옵션으로 열어본다. `fast_load=True`는 일부 검증을 건너뛰고 필수 구조만 파싱하므로 더 관대하게 동작하는 경우가 많다. 이후 `pe.parse_data_directories()`를 수동으로 호출해 필요한 디렉터리만 추가로 파싱할 수 있다.
- CFF Explorer 계열 도구는 깨진 헤더도 최대한 열어서 필드별로 직접 수정할 수 있게 해주는 경우가 많으므로, 문제 필드를 찾아 스펙에 맞는 값으로 고친 뒤 저장해서 다시 IDA로 열어본다.

**5) 필드를 정상값으로 되돌려 저장**
- 위에서 찾은 잘못된 필드(예: 틀린 `NumberOfSections`, 틀린 `SizeOfOptionalHeader`)를 실제 섹션 테이블 데이터에 맞는 값으로 헥스 에디터에서 직접 수정하고 저장한 뒤, 그 사본으로 IDA/PE-bear를 다시 열어본다.

## 명령어/단축키
```text
HxD: Ctrl+G(오프셋 이동)로 0x3C, 0x3C+4 등 주요 오프셋 바로 확인
Python: pefile.PE(path, fast_load=True) → pe.parse_data_directories()
PE-bear: File → Open, 오류 시 하단 로그/상태바 메시지 확인
```

## 출력 해석
- `e_lfanew`가 가리키는 위치에 실제로 `50 45 00 00`이 있으면 PE 시그니처 자체는 정상이므로 문제는 그 이후 필드에 있다.
- `pefile`로 열었을 때 `pe.OPTIONAL_HEADER.Magic`이 `0x10b`도 `0x20b`도 아니면 이후 모든 필드 오프셋 계산이 어긋난 것이므로, 이 값부터 바로잡아야 한다.
- 섹션 테이블을 수동으로 읽었을 때 `VirtualSize`나 `SizeOfRawData`가 파일 크기보다 훨씬 크면(예: 0xFFFFFFFF에 가까운 값) 의도적으로 파서를 헷갈리게 하려는 조작일 가능성이 크다.

## 흔한 실수
- IDA가 못 연다고 해서 파일이 손상됐다고 단정하고 분석을 포기하는 것 — Windows에서 정상 실행된다면 로더가 신경 쓰지 않는 필드만 조작됐을 뿐, 파일 자체는 유효한 경우가 많다.
- 헥스 에디터로 필드를 고칠 때 엔디안을 착각해서(리틀엔디안인데 빅엔디안으로 입력) 오히려 값을 더 망가뜨리는 것.
- `NumberOfSections`만 고치고 실제 섹션 테이블의 항목 개수는 그대로 둬서 여전히 불일치가 남는 것.
- 원본 파일을 직접 수정해버려서 나중에 "원래 조작된 상태"를 비교할 수 없게 되는 것 — 반드시 사본을 만들어 그 사본만 수정한다.

## 막혔을 때 다음 체크
- 섹션 이름/특성 자체가 표준과 달라 헷갈리는 문제라면 → REV-0593(Section 이름이 표준과 달라서 도구가 헷갈릴 때)을 함께 본다.
- PE 헤더 각 필드의 정확한 오프셋과 의미를 다시 확인하고 싶으면 → REV-0116(PE Header COFF Optional Header 읽기)을 참고한다.
- 헤더는 정상화됐는데 여전히 Import Table이 비어 보이면 → REV-0581(IDA에서 PE를 열었는데 Import Table이 비어있을 때)을 참고한다.

## 미니 예제
헥스 에디터로 파일을 열어보니 `IMAGE_FILE_HEADER.NumberOfSections`(오프셋 `e_lfanew + 4 + 6`) 값이 `0x0009`(9개)로 되어 있는데, 실제로 섹션 테이블 영역에는 `.text`, `.rdata`, `.data`, `.rsrc` 단 4개의 유효한 섹션 헤더만 있고 그다음은 전부 0으로 채워진 더미 데이터였다고 하자. PE-bear는 이 불일치 때문에 나머지 5개를 이상한 섹션으로 잘못 해석해 오류를 냈다. `NumberOfSections`를 `0x0004`로 수정해서 저장한 뒤 다시 열자 PE-bear가 정상적으로 4개 섹션만 파싱해 보여줬다.

## 관련 글
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0117 — PE Section Table 읽기
- REV-0593 — Section 이름이 표준과 달라서 도구가 헷갈릴 때
- REV-0581 — IDA에서 PE를 열었는데 Import Table이 비어있을 때

## 출처/검증
- PE 헤더 필드(`e_lfanew`, `NumberOfSections`, `SizeOfOptionalHeader`, `Magic` 등)의 오프셋과 의미는 Microsoft PE/COFF 형식 공식 문서 기준.
- Windows 로더가 일부 헤더 필드에 대해 정적 분석 도구보다 관대하게 동작한다는 점은 다수의 악성코드 분석/anti-reversing 관련 보안 리서치에서 공통적으로 다뤄지는 내용이다.
- Python `pefile` 라이브러리의 `fast_load` 옵션 동작은 `pefile` 공식 문서/소스 기준.
