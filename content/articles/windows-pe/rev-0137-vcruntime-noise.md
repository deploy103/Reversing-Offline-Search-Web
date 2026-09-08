---
id: REV-0137
title: "Visual C++ Runtime 함수가 많은 바이너리 정리법"
slug: "rev-0137-vcruntime-noise"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", "Detect It Easy"]
keywords: ["Visual C++ Runtime", "CRT", "FLIRT", "정적 링크", "vcruntime140.dll", "__scrt_common_main", "라이브러리 함수 인식"]
aliases: ["CRT 함수 노이즈", "vcruntime 정리", "라이브러리 함수 걸러내기", "main 못 찾겠다"]
symptom_keywords: ["함수가 너무 많아서 뭐가 진짜 로직인지 모르겠다", "이상한 이름의 함수들이 잔뜩 있다", "main을 못 찾겠다", "실행 파일 크기가 이상하게 크다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Visual C++로 컴파일된 바이너리를 정적 링크(static link)로 빌드하면 `malloc`, `memcpy`, 예외 처리 헬퍼, C++ 런타임 초기화 코드 등 수백 개의 CRT(C Runtime) 함수가 통째로 바이너리 안에 박혀 들어와 함수 목록을 가득 채워버리므로, IDA의 FLIRT 시그니처로 이런 "라이브러리 함수"를 미리 걸러내고 진입점에서부터 실제 `main`으로 이어지는 경로를 따라가는 법을 알아야 진짜 로직에 빠르게 도달할 수 있다.

## 언제 검색해야 하나
- IDA에서 함수 목록(`Functions` 창)을 열었더니 이름이 `_initterm`, `_RTC_CheckStackVars`, `__scrt_common_main_seh`, `operator new` 같은 낯선 함수 수백 개로 가득할 때
- 파일 크기는 몇백 KB~몇 MB인데 실제 사용자 로직은 몇 줄 안 될 것 같은 느낌이 들 때
- `main`이나 `WinMain`을 찾으려고 진입점부터 따라갔는데 여러 겹의 래퍼 함수(`__scrt_*`)를 거치느라 길을 잃을 때
- Detect It Easy로 열었을 때 "Statically linked"라는 표시나 컴파일러 정보가 나올 때

## 핵심 개념
Visual C++로 빌드된 실행 파일은 링크 방식에 따라 크게 두 가지로 나뉜다.

**동적 링크(Dynamic/DLL 런타임, `/MD` 옵션)**: 프로그램이 `msvcrt.dll` 또는 `vcruntime140.dll`, `ucrtbase.dll` 같은 별도의 CRT DLL을 임포트해서 그 안의 함수를 그때그때 호출한다. 이 경우 바이너리 자체의 함수 개수는 적고, 임포트 테이블에 CRT 함수 이름이 그대로 나열되어 있어서 오히려 분석이 쉽다.

**정적 링크(Static 런타임, `/MT` 옵션)**: CRT 코드 전체가 컴파일 시점에 실행 파일 안으로 그대로 복사되어 들어간다. 이러면 실행 파일 하나로 배포가 간편해지지만(대상 PC에 CRT DLL이 없어도 동작), 그 대가로 바이너리 안에 `malloc`/`free`/`memcpy`/`sprintf`/예외 처리 헬퍼/부동소수점 헬퍼 같은 수백 개의 함수가 몽땅 딸려 들어와 함수 목록이 폭발적으로 늘어난다. CTF 문제 바이너리는 배포 편의성 때문에 정적 링크로 빌드되는 경우가 흔하다.

이 "노이즈"를 다루는 표준적인 방법이 IDA의 **FLIRT(Fast Library Identification and Recognition Technology)** 시그니처다. IDA는 수많은 컴파일러/버전별 표준 라이브러리의 바이트 패턴을 미리 데이터베이스로 갖고 있어서, 파일을 열자마자 자동으로 "이 함수는 CRT의 `malloc`이다"라는 식으로 인식하고 이름을 붙여준다. 이렇게 인식된 함수는 함수 목록에서 다른 색(보통 연보라/핑크 계열)으로 표시되고, 함수 이름 앞에 "라이브러리 함수"라는 표시가 붙는다.

또 하나 알아야 할 것은 Visual C++ 실행 파일의 **시작 경로**다. 사용자가 작성한 `main`/`WinMain`은 프로그램의 진짜 진입점(`AddressOfEntryPoint`)이 아니다. 실제 진입점은 CRT 초기화 코드(`__scrt_common_main_seh` 등)이며, 이 코드가 C 런타임을 초기화(힙, 표준 입출력, 예외 처리 테이블, 전역 생성자 등)한 다음에야 비로소 사용자의 `main`을 호출한다. 대략적인 호출 체인은 다음과 같다.

```text
entry point (예: mainCRTStartup)
  -> __scrt_common_main_seh
    -> __scrt_common_main
      -> invoke_main   (여기서 실제 main/WinMain 호출)
```

이 체인 이름은 Visual Studio 버전에 따라 다소 다를 수 있지만, 개념은 동일하다. FLIRT가 이 함수들도 대부분 인식해서 이름을 붙여주므로, "라이브러리 함수가 아닌 것 중 진입점에서 몇 단계 안 거치고 도달하는 첫 번째 함수"를 찾으면 그게 대개 `main`이다.

## 화면/코드에서 보이는 징후
- IDA `Functions` 창에서 함수 이름 왼쪽에 도서관 모양 아이콘이 붙거나, 함수 이름이 밑줄(`_`)로 시작하는 CRT 스타일 이름(`_initterm`, `_amsg_exit`, `_RTC_InitBase`)으로 가득함
- 함수를 정렬(이름/주소 컬럼 클릭)했을 때 사용자 코드 함수(짧고 개성 있는 이름 또는 `sub_401xxx` 형태)가 CRT 함수들 사이에 몇 개 안 섞여 있음
- Detect It Easy로 열었을 때 컴파일러 섹션에 "Microsoft Visual C/C++"와 함께 정적 링크를 암시하는 정보가 나옴(임포트가 적고 파일 크기가 상대적으로 큼)
- IDA 초기 로딩 시 "FLIRT" 관련 메시지 창(예: "라이브러리 함수 몇 개를 인식했습니다")이 잠깐 나타남

## 가장 먼저 할 것
1. IDA로 파일을 열 때 뜨는 FLIRT 관련 대화상자를 무시하지 말고, 시그니처 적용을 허용한다(기본적으로 자동 적용되는 경우가 많다).
2. `Functions` 창에서 "Function name" 컬럼을 클릭해 이름순 정렬한 뒤, 라이브러리 함수로 표시되지 않은(회색/기본색) 함수만 눈으로 훑어본다.
3. 그래도 함수가 많다면 진입점(`Entry point`, `Ctrl+E`)에서 시작해 `__scrt_common_main_seh` 계열 함수를 따라 `main`/`WinMain`까지 직접 걸어 들어간다.

## 단계별 절차
**1) FLIRT로 걸러내기**
- IDA 상단 메뉴 `View → Open subviews → Functions`로 함수 목록을 연다.
- 라이브러리 함수는 보통 별도 색으로 구분되어 표시되며, 함수 이름 위에서 우클릭 → "라이브러리 함수인지" 여부를 토글하는 메뉴도 있다.
- 시그니처가 정확히 안 맞아서 인식이 덜 된 것 같으면 `File → Load file → FLIRT signature file`로 해당 컴파일러/버전에 맞는 추가 시그니처를 로드할 수 있다.

**2) 진입점부터 main까지 추적**
- `Ctrl+E`로 Entry point 목록을 열고 첫 항목으로 이동한다(보통 `mainCRTStartup` 또는 `WinMainCRTStartup`).
- 함수 안에서 호출되는 다음 함수로 `Enter`(코드 따라 들어가기)를 눌러가며 `__scrt_common_main_seh` → `__scrt_common_main` → `invoke_main`(또는 유사 이름) 순서로 들어간다.
- `invoke_main` 안에서 실제로 호출되는 함수가 바로 사용자가 작성한 `main`/`WinMain`이다. 이 함수에 `N` 단축키로 이름을 `real_main` 등으로 바꿔두면 이후 탐색이 훨씬 수월해진다.

**3) 크기/복잡도로 보조 판단**
- FLIRT가 놓친 사용자 함수를 찾을 때는 함수 크기(바이트 수)나 참조하는 문자열 개수로 정렬해보는 것도 유용하다. CTF 문제의 핵심 로직 함수는 대개 크기가 크고, 여러 지역 문자열/상수를 참조하는 경우가 많다.
- Ghidra를 함께 쓴다면, Ghidra도 자체 함수 ID 데이터베이스(FID)로 유사한 라이브러리 함수 인식을 수행하므로 동일한 접근이 가능하다.

## 명령어/단축키
- IDA: `Ctrl+E`(Entry point 목록), `Enter`(함수 안으로 들어가기), `N`(함수/변수 이름 바꾸기), `View → Open subviews → Functions`(함수 목록), `File → Load file → FLIRT signature file`(추가 시그니처 로드)
- Detect It Easy: 파일을 드래그 앤 드롭 후 상단 "컴파일러" 정보와 "라이브러리" 정보 확인
- PE-bear: `Imports` 탭에서 `vcruntime140.dll`/`msvcrt.dll`/`ucrtbase.dll` 등 CRT DLL 임포트 여부 확인(있으면 최소한 완전 정적 링크는 아님)

## 출력 해석
- 임포트 테이블에 `vcruntime140.dll`, `ucrtbase.dll`, `msvcrt.dll` 등이 보이면 CRT의 일부(또는 전부)가 동적 링크되어 있다는 뜻이므로, 바이너리 내부 함수 개수가 상대적으로 적을 것이다.
- 반대로 이런 CRT DLL 임포트가 전혀 없고 `KERNEL32.dll` 같은 기본 시스템 DLL만 임포트되어 있다면, CRT가 완전히 정적으로 포함된 것이므로 FLIRT를 적극 활용해야 한다.
- FLIRT가 함수 이름을 정확히 못 맞히고 `sub_` 접두사로 남겨둔 함수라도, 크기가 아주 작고(몇 바이트) 단순 점프/리턴만 있다면 여전히 CRT 헬퍼일 가능성이 높다.

## 흔한 실수
- FLIRT가 인식한 함수 이름을 무조건 신뢰해서, 실제로는 컴파일러 버전 차이로 오탐된 이름을 그대로 믿고 넘어가는 것. 이름이 이상하게 안 맞으면 함수 내부 코드를 한 번은 직접 확인한다.
- CRT 노이즈를 걸러내는 데만 집중하다가, 정작 그 사이에 숨어 있는 사용자 정의 헬퍼 함수(예: 복호화 함수가 CRT 함수 이름과 비슷하게 명명된 경우는 드물지만, 크기가 작아서 무시하고 지나치는 경우)를 놓치는 것.
- 정적 링크된 C++ 바이너리에서 `std::string`, `std::vector` 등 템플릿 코드까지 전부 "CRT 노이즈"로 착각하고 무시하는 것. 이런 템플릿 인스턴스화 코드는 라이브러리 코드이긴 하지만, 그 안에서 사용자 데이터가 어떻게 다뤄지는지(예: 문자열 조작)를 보여줄 수 있어 완전히 무시하면 안 된다.
- `main` 진입 전 전역 객체 생성자(정적 초기화)가 실행된다는 사실을 잊고, 전역 변수가 이미 특정 값으로 세팅된 상태에서 `main`이 시작된다는 점을 놓치는 것.

## 막혔을 때 다음 체크
- 이 바이너리가 네이티브가 아니라 .NET일 수도 있다는 의심이 들면 → REV-0136(.NET EXE인지 Native EXE인지 구분)을 먼저 확인한다.
- `main`을 찾은 뒤 그 안에서 호출하는 Windows API 이름이 낯설다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.
- CRT 초기화 과정에서 TLS 콜백이 함께 등록되어 있을 수 있으니 → REV-0133(TLS Callback과 main 이전 코드)도 함께 확인한다.

## 미니 예제
IDA로 어떤 CTF 바이너리를 열었더니 함수가 400개나 있었다. `Functions` 창에서 이름순 정렬해보니 대부분이 `_`로 시작하는 CRT 스타일 이름(`_initterm`, `_except_handler4_common`, `_RTC_Initialize` 등)이었고, FLIRT가 이들을 모두 라이브러리 함수로 표시해줬다. 이름순 정렬 결과 중간쯤에 `sub_401560`이라는, 라이브러리 표시가 안 된 함수가 하나 있었는데 크기가 800바이트나 됐다. `Ctrl+E`로 진입점을 확인해보니 `mainCRTStartup → __scrt_common_main_seh → invoke_main`을 거쳐 정확히 이 `sub_401560`을 호출하고 있었다. 이 함수를 `real_main`으로 이름을 바꾸고 여기서부터 본격적인 분석을 시작하면 된다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0133 — TLS Callback과 main 이전 코드
- REV-0136 — .NET EXE인지 Native EXE인지 구분
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- Visual C++의 `/MT`(정적)과 `/MD`(동적) 런타임 링크 옵션 차이는 Microsoft C++ 빌드 도구 공식 문서 기준이다.
- CRT 시작 함수 체인(`mainCRTStartup`, `__scrt_common_main_seh` 등)의 이름과 역할은 Microsoft Visual C++ 소스(공개된 CRT 소스 일부) 및 공식 문서 기준이며, Visual Studio 버전에 따라 세부 함수명이 다를 수 있다.
- IDA의 FLIRT 기술 개요는 Hex-Rays(IDA 개발사) 공식 문서 기준이다(2026-09-08 기준 서술).
