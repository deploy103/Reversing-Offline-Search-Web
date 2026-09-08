---
id: REV-0557
title: "PE 체크섬(Checksum) 검증과 리버싱 의미"
slug: "rev-0557-pe-checksum"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", "CFF Explorer"]
keywords: ["CheckSum", "IMAGE_OPTIONAL_HEADER", "MapFileAndCheckSumW", "CheckSumMappedFile", "imagehlp.dll", "드라이버 서명"]
aliases: ["pe 체크섬이란", "옵셔널 헤더 체크섬", "체크섬 필드가 0인 이유", "checksum 필드 안 맞음"]
symptom_keywords: ["파일을 패치했더니 실행이 안 됨", "체크섬 필드가 0으로 되어 있음", "드라이버가 로드되지 않고 오류남", "PE-bear에서 checksum invalid라고 표시됨"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`IMAGE_OPTIONAL_HEADER.CheckSum` 필드는 파일 전체 바이트로부터 계산되는 16비트 워드 합 기반 체크섬 값으로, 일반 사용자 EXE는 로더가 이 값을 거의 검사하지 않지만 **커널 드라이버(.sys), 일부 시스템 DLL, 그리고 서명 검증 과정**에서는 이 값이 틀리면 로드 자체가 실패하거나 서명이 무효로 처리될 수 있어서, 바이너리를 패치한 뒤에는 이 필드를 재계산해서 넣어주는 습관이 필요하다.

## 언제 검색해야 하나
- 패치한 EXE/DLL/드라이버를 저장했더니 실행이 안 되거나 "손상된 이미지"류의 오류가 뜰 때
- PE-bear나 CFF Explorer가 `CheckSum` 필드 옆에 `[invalid]` 또는 계산된 값과 실제 값이 다르다고 표시할 때
- 드라이버(.sys) 파일을 로드하려는데 `STATUS_IMAGE_CHECKSUM_MISMATCH` 계열 오류가 나거나 `sc.exe start`가 실패할 때
- Authenticode 서명 검증(REV-0559)이 왜 체크섬 필드를 서명 해시 계산에서 제외하는지 궁금할 때
- 바이너리 패치 도구를 직접 만들면서 "체크섬을 다시 계산해야 하나?"를 판단해야 할 때

## 핵심 개념

### CheckSum 필드의 위치와 계산 방식
`CheckSum`은 `IMAGE_OPTIONAL_HEADER`(32비트/64비트 공통 레이아웃상 위치는 같음, PE32는 오프셋 0x40, PE32+도 오프셋 0x40) 안에 있는 4바이트 `DWORD` 필드다. 계산 알고리즘은 대략 다음과 같이 동작한다.

1. 파일 전체를 16비트(WORD) 단위로 읽으면서 합산한다. 이때 자기 자신인 `CheckSum` 필드 위치의 4바이트는 0으로 취급해서 합산에서 제외한다.
2. 합산 중 32비트 캐리가 발생하면 하위 16비트에 다시 더해주는(end-around carry) 방식으로 접어준다.
3. 마지막에 파일 크기(바이트 수)를 더해 최종 체크섬 값을 만든다.

리버서가 이 알고리즘을 직접 손으로 구현할 일은 드물다 — Windows가 공식으로 제공하는 `imagehlp.dll`의 `MapFileAndCheckSumW` API나 `CheckSumMappedFile` API가 정확히 이 로직을 구현하고 있고, 대부분의 PE 편집 도구(CFF Explorer, PE-bear, Detect It Easy)가 "체크섬 재계산" 버튼을 제공한다.

```c
DWORD MapFileAndCheckSumW(
  PCWSTR Filename,
  PDWORD HeaderSum,     // 파일에 원래 저장돼 있던 값
  PDWORD CheckSum       // 실제로 계산된 값
);
```
두 값이 다르면 체크섬이 깨져 있다는 뜻이다.

### 로더가 언제 이 값을 실제로 검사하는가
많은 초보자가 오해하는 부분이 "체크섬이 틀리면 EXE가 아예 안 열린다"는 것인데, 실제로는 그렇지 않다. Windows 로더는 **일반 사용자 모드 EXE**에 대해서는 기본적으로 체크섬을 검사하지 않는다(패치 후 바로 실행돼서 "왜 체크섬은 안 맞는데 잘 실행되지?"라고 느끼는 이유가 이것이다). 다만 다음과 같은 상황에서는 실제로 검사된다.

- **커널 모드 드라이버(.sys)**: 드라이버 로더는 체크섬이 올바른지 검사하며, 틀리면 로드를 거부할 수 있다.
- **DLL이 특정 시스템 시나리오로 로드될 때**: 일부 시스템 컴포넌트나 강제 무결성 검사 경로에서 체크섬을 확인한다.
- **`/FORCE` 링커 옵션 없이 빌드된 결과물**에 대해 링커/빌드 도구가 자체적으로 체크섬을 검증하는 경우.
- **Authenticode 서명 검증 관점**: 서명 자체는 체크섬 필드를 서명 대상 해시 계산에서 제외하도록 정의돼 있다(REV-0559 참고). 즉 체크섬이 서명 유효성에 직접 영향을 주지는 않지만, 체크섬이 깨진 파일은 "정상적으로 빌드되지 않은 파일"이라는 정황 증거로 쓰일 수 있다.

### 왜 리버서에게 중요한가
1. **패치 후 재계산 습관**: 바이트를 몇 개 패치하고 저장했을 때, 대부분의 헥스 에디터는 체크섬을 자동으로 갱신해주지 않는다. 드라이버나 특정 서명 검증 경로를 다루는 게 아니라면 실행에는 지장이 없지만, "이 파일이 원본에서 수정됐는가"를 정황으로 판단할 때 체크섬 불일치가 좋은 단서가 된다.
2. **정황 증거로서의 체크섬**: 악성코드 분석 시 체크섬 필드가 아예 `0`으로 채워진 경우(일부 컴파일러/패커가 기본값을 안 채우는 경우)나, 계산값과 저장값이 다른 경우는 "빌드 후 바이너리가 조작됐다"는 강한 신호다.
3. **드라이버 리버싱에서 필수**: REV-0562에서 다루는 것처럼 `.sys` 파일을 패치해서 테스트하려면 체크섬을 반드시 재계산해야 로드가 성공한다.

## 화면/코드에서 보이는 징후
- CFF Explorer의 "NT Headers → File Header" 탭에서 `CheckSum` 필드 옆에 "Calculate Checksum" 버튼과 실제 계산값이 나란히 표시되고, 서로 다르면 붉은색 등으로 강조됨
- PE-bear에서 Optional Header를 열면 `CheckSum` 필드 값이 보이고, `File → Recalculate PE Checksum` 같은 메뉴로 재계산 가능
- 드라이버 로드 시 이벤트 뷰어(Event Viewer)나 `sc.exe start` 결과에 이미지 손상/체크섬 관련 오류 코드가 나타남
- `MapFileAndCheckSumW`를 스크립트로 호출했을 때 `HeaderSum != CheckSum`으로 반환됨

## 가장 먼저 할 것
바이너리를 패치했는데 드라이버이거나, "혹시 체크섬 때문에 문제가 생기지 않을까" 의심될 때는 CFF Explorer나 PE-bear 같은 GUI 도구를 열어서 체크섬을 재계산하는 버튼을 누르는 것이 가장 빠르다. 직접 파싱/계산 코드를 짤 필요 없이 도구가 알고리즘을 이미 구현해두었다.

## 단계별 절차

**1) 체크섬 필드 위치 확인**
`IMAGE_OPTIONAL_HEADER.CheckSum`(REV-0116 참고)을 찾는다. PE32/PE32+ 모두 Optional Header 시작으로부터 0x40 오프셋에 위치한다.

**2) 저장된 값과 실제 계산값 비교**
`MapFileAndCheckSumW`를 직접 호출하거나, CFF Explorer의 계산 버튼, `pefile` 파이썬 라이브러리의 `pe.generate_checksum()` 같은 기능을 이용해 실제 값을 구한다.

**3) 두 값이 다르면 원인 파악**
- 패치 도구가 체크섬을 갱신하지 않고 저장했는가?
- 원본부터 체크섬이 0이거나 잘못 채워진 파일(일부 오래된 컴파일러/패커 출력)인가?

**4) 필요하면 재계산 후 저장**
드라이버, 서명이 필요한 파일, 혹은 정확성을 검증해야 하는 상황이라면 도구의 "Update/Recalculate Checksum" 기능으로 값을 갱신한다.

**5) 드라이버라면 반드시 재계산 후 테스트**
REV-0562에서 다루는 것처럼 `.sys` 파일은 체크섬이 맞지 않으면 로드 자체가 거부될 수 있으므로, 패치 후 항상 이 단계를 거친다.

## 명령어/단축키
```text
CFF Explorer: NT Headers → File Header 탭 → "Calculate Checksum" 버튼
PE-bear: 메뉴에서 체크섬 재계산 기능(버전에 따라 상단 툴바 또는 Optional Header 우클릭)
imagehlp.dll: MapFileAndCheckSumW(파일경로, &원본값, &계산값) — C/C++ 또는 ctypes로 직접 호출 가능
Python: pefile 모듈의 pe.generate_checksum() 및 pe.OPTIONAL_HEADER.CheckSum 비교
```

## 출력 해석
- `HeaderSum`(파일에 저장된 값)과 `CheckSum`(실제 계산값)이 같으면 정상 — 원본에서 변경되지 않았거나, 변경 후 올바르게 재계산됐다는 뜻
- 두 값이 다르면 파일이 최초 빌드 이후 바이트 수준으로 수정됐고, 체크섬이 갱신되지 않았다는 뜻 — 일반 EXE라면 실행에는 대부분 문제없지만 조작 여부의 증거가 됨
- 체크섬 필드가 `0x00000000`이면 애초에 링커가 채우지 않았거나(일부 빌드 설정), 도구가 의도적으로 지운 경우다

## 흔한 실수
- "체크섬이 틀리면 EXE가 무조건 안 열린다"고 오해하는 것 — 대부분의 사용자 모드 EXE는 로더가 체크섬을 검사하지 않는다.
- 드라이버를 패치하고 체크섬을 안 맞춰서 "패치가 안 먹힌다"고 착각하는 것 — 실제로는 로드 자체가 거부되고 있을 수 있다.
- 체크섬과 Authenticode 서명(REV-0559)을 같은 것으로 혼동하는 것 — 체크섬은 단순 무결성용 워드 합산이고, Authenticode는 별도의 암호학적 서명이다. 다만 서명 해시 계산 시 체크섬 필드는 제외하도록 정의돼 있다는 관계는 있다.
- 체크섬 계산 알고리즘을 직접 처음부터 구현하려다 캐리 처리, 자기 자신 필드 제외, 파일 크기 더하기 등의 세부 규칙을 놓쳐 값이 틀리는 것 — 가능하면 `imagehlp.dll`이나 검증된 라이브러리를 쓰는 것이 안전하다.

## 막혔을 때 다음 체크
- Optional Header에서 CheckSum 필드 위치 자체가 헷갈리면 → [REV-0116 PE Header COFF Optional Header 읽기](./rev-0116-pe-coff-optional-header.md)
- 드라이버(.sys) 패치/분석 전반이 궁금하면 REV-0562(드라이버 파일을 만났을 때 최소 대응) 항목을 참고
- Authenticode 서명과 체크섬의 관계가 궁금하면 → [REV-0559 Authenticode 서명이 있는 PE 기초 확인법](./rev-0559-authenticode-signature.md)
- 컴파일러/패커 흔적을 다른 각도로 확인하고 싶으면 → [REV-0558 Rich Header에서 컴파일러 정보 추출하기](./rev-0558-rich-header.md)

## 미니 예제
`sample.sys`라는 드라이버 파일의 IRP 처리 코드 한 줄을 x64dbg 등으로 미리 패치한 뒤 저장했다고 하자.

```text
1) CFF Explorer로 파일을 연다.
2) NT Headers → File Header 탭 이동.
3) CheckSum 필드: 0x0004A210 (원본에 저장된 값)
   Calculate Checksum 버튼 클릭 → 0x0004B77C (실제 계산값)
4) 두 값이 다르므로 "Update Checksum" 또는 계산값으로 필드를 직접 덮어써서 저장.
5) sc.exe create test type= kernel binPath= C:\path\sample.sys
   sc.exe start test
   → 체크섬을 맞추지 않았을 때는 로드 실패, 맞춘 뒤에는 정상 로드 확인.
```

## 관련 글
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0559 — Authenticode 서명이 있는 PE 기초 확인법
- REV-0558 — Rich Header에서 컴파일러 정보 추출하기
- REV-0556 — Forwarded Export 이해하기

## 출처/검증
- `IMAGE_OPTIONAL_HEADER.CheckSum` 필드 위치 및 정의: Microsoft Learn "PE Format" 공식 문서 기준 (2026-09-08 검증).
- `MapFileAndCheckSumW`/`CheckSumMappedFile` API 시그니처와 동작: Microsoft Learn "imagehlp.h" API 문서 기준.
- 사용자 모드 EXE는 로더가 체크섬을 일반적으로 검사하지 않고 커널 드라이버 로드 시 검사된다는 점: 다수 Windows 내부구조/드라이버 개발 참고자료 및 실무 관찰에 기반한 일반화 설명 — 정확한 버전별 예외 조건은 커널 로더 소스가 공개돼 있지 않아 완전한 검증은 어려움을 밝혀둔다.
