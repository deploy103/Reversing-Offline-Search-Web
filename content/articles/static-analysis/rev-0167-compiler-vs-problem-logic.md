---
id: REV-0167
title: "Compiler Generated Code와 실제 문제 로직 구분"
slug: "rev-0167-compiler-vs-problem-logic"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra, IDA]
keywords: ["CRT startup 코드", "__scrt_common_main_seh", "__libc_csu_init", "frame_dummy", "stack canary 체크", "컴파일러 생성 코드 구분", "라이브러리 함수 식별"]
aliases: ["부트스트랩 코드 무시하기", "런타임 초기화 코드 구분", "진짜 로직만 보기"]
symptom_keywords: ["main 찾기 전에 이상한 함수들이 너무 많음", "__scrt로 시작하는 함수가 뭔지 모름", "frame_dummy가 뭔지 모름", "이 함수가 문제 로직인지 컴파일러 코드인지 모르겠음"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
실행 파일 안의 함수 중 상당수는 **문제를 낸 사람이 작성한 코드가 아니라 컴파일러/런타임 라이브러리가 자동으로 붙인 부트스트랩·보안·초기화 코드**이며, `mainCRTStartup`/`__scrt_common_main_seh`/`__libc_csu_init`/`frame_dummy`/스택 카나리 체크처럼 이름과 형태가 정형화된 패턴을 알아두면 이런 코드를 곧바로 건너뛰고 실제 문제 로직에만 집중할 수 있다.

## 언제 검색해야 하나
- `entry`나 `_start`부터 `main`까지 따라가는데 낯선 함수가 여러 겹으로 계속 나와서 어디까지가 "그냥 부트스트랩"인지 헷갈릴 때
- 함수 이름에 `__scrt`, `__libc`, `csu`, `security_check_cookie`, `frame_dummy`, `register_tm_clones` 같은 접두사/단어가 보일 때
- 디컴파일 결과에 갑자기 스택 오버플로 방지용으로 보이는 이상한 비교 코드(`if (canary != value) __fastfail(...)` 류)가 섞여 있어서 이게 문제의 일부인지 헷갈릴 때
- 함수가 너무 많아서 REV-0166(Call Graph)으로 좁혀봐도 여전히 컴파일러 생성 코드가 후보에 섞여 나올 때

## 핵심 개념
현대 컴파일러(MSVC, GCC/Clang)는 사용자가 작성한 `main` 함수 하나만 달랑 실행 파일에 넣지 않는다. 실제 실행 파일에는 다음과 같은 "사용자가 작성하지 않은" 코드가 함께 포함된다.

**Windows PE (MSVC 계열)**
- **`entry` (진입점)**: PE 헤더의 AddressOfEntryPoint가 가리키는 곳으로, 보통 `mainCRTStartup` 또는 `WinMainCRTStartup`이라는 이름이 붙는다. 이는 사용자의 `main`이 아니라 C 런타임 초기화 루틴이다.
- **`__scrt_common_main_seh`**: 최신 MSVC 런타임에서 CRT 초기화(힙, 로케일, 예외 처리 등록, 스택 체크 쿠키 설정)를 담당한 뒤 마지막에 사용자의 `main`/`wmain`을 호출하는 함수.
- **`__security_init_cookie` / `__security_check_cookie`**: 스택 버퍼 오버플로 보호(`/GS` 옵션)를 위한 스택 카나리(canary) 값을 초기화/검증하는 함수. 함수 프롤로그에서 카나리 값을 스택에 심고, 에필로그 직전에 이 값이 변조되지 않았는지 확인하는 코드가 자동으로 삽입된다.
- **`atexit`/TLS(Thread Local Storage) 콜백 등록 코드**: 프로그램 종료 시 실행할 정리 함수를 등록하는 배열/함수.

**Linux ELF (GCC/Clang 계열)**
- **`_start`**: 실제 진입점으로, glibc가 제공하는 코드이며 내부적으로 `__libc_start_main`을 호출해 최종적으로 사용자의 `main`을 실행한다.
- **`__libc_csu_init` / `__libc_csu_fini`**: `.init_array`/`.fini_array`에 등록된 생성자/소멸자 함수들을 순회하며 호출하는 초기화/정리 루틴.
- **`frame_dummy`**: 예외 처리 프레임 정보 등록을 위한 작은 함수로, 거의 항상 내용이 비슷하고 사용자가 손댈 일이 없다.
- **`register_tm_clones` / `deregister_tm_clones`**: 트랜잭셔널 메모리(transactional memory) 관련 초기화로, 최신 GCC가 자동 삽입하는 짧은 함수. 내용은 거의 항상 정형화되어 있다.
- **스택 프로텍터(`__stack_chk_fail`, `__stack_chk_guard`)**: MSVC의 `/GS`와 동일한 목적의 GCC `-fstack-protector` 관련 코드.

이런 함수들의 공통적인 특징은 **(1) 함수 이름이 정형화된 규칙을 따르고, (2) 내부 로직이 어느 프로그램에서든 거의 동일하며, (3) 문제 출제자가 임의로 수정하지 않는다**는 것이다. 즉, 이 패턴을 한 번 익혀두면 다음부터는 이름만 보고도 "이건 CTF 문제와 무관한 컴파일러 코드"라고 즉시 판단해서 시간을 아낄 수 있다.

반대로, **스택 카나리 체크 자체를 우회하거나 조작해야 하는 문제**(예: 스택 오버플로우 취약점을 익스플로잇하는 pwnable 문제)에서는 이 코드가 오히려 분석 대상이 될 수 있다. 이 문서는 어디까지나 "일반적인 정적 분석에서 검증 로직을 찾을 때" 이런 코드를 건너뛰는 기준을 설명하는 것이며, 문제 유형에 따라 예외가 있을 수 있다는 점은 염두에 둬야 한다.

## 화면/코드에서 보이는 징후
- Symbol Tree/Imports/Functions 목록에 `__scrt_`, `__libc_`, `_CRT_`, `csu`, `frame_dummy`, `register_tm_clones` 같은 이름이 다수 보인다.
- 함수 프롤로그 근처에서 `mov eax, [special stack cookie]`처럼 스택에 특정 값을 저장하고, 함수 끝부분에서 그 값을 다시 비교하는 패턴이 여러 함수에 걸쳐 똑같이 반복된다.
- IDA는 이런 라이브러리/부트스트랩 함수를 Functions window에서 다른 색으로 표시하거나 "Library function" 플래그를 붙이는 경우가 많고(FLIRT 시그니처로 인식된 경우), Ghidra는 Function ID Analyzer가 인식에 성공하면 실제 함수 이름을 그대로 붙여준다(REV-0157 참고).

## 가장 먼저 할 것
`entry`/`_start`에서 `main`까지 이어지는 호출 체인을 REV-0166(Call Graph)으로 한 번 훑어보고, 그 경로에 있는 함수 이름이 위에서 설명한 정형화된 이름과 일치하면 내부를 깊이 읽지 않고 그대로 통과시킨다.

## 단계별 절차

**1) 진입점 확인**

`entry`(Ghidra) 또는 진입점 함수(IDA에서 자동으로 `start`라는 이름이 붙는 경우가 많음)로 이동한다.

**2) 이름 패턴으로 1차 필터링**

호출되는 함수들의 이름을 보고, 위 목록(`__scrt_`, `__libc_`, `csu`, `frame_dummy`, `register_tm_clones`, `security_check_cookie` 등)과 일치하면 "컴파일러 생성 코드"로 잠정 분류하고 넘어간다.

**3) 라이브러리 식별 플래그 확인**

- Ghidra: Function ID Analyzer(REV-0157)가 인식에 성공했다면 함수 이름이 이미 정확하게 붙어 있을 것이다. Symbol Tree에서 이런 함수들은 대개 표준 라이브러리 이름 그대로 나타난다.
- IDA: FLIRT 시그니처가 인식한 라이브러리 함수는 함수 이름 앞에 특정 표시가 붙거나 Functions window에서 "Library function" 컬럼/색상으로 구분된다.

**4) `main`(또는 실제 사용자 정의 진입 함수)을 찾을 때까지 반복**

`__scrt_common_main_seh` → 사용자 `main`으로 이어지는 것처럼, 부트스트랩 함수들은 결국 사용자 코드를 호출하는 지점에서 끝난다. 그 마지막 호출 대상이 바로 실제 분석을 시작해야 할 지점이다.

**5) `main` 진입 이후부터 REV-0163/0164/0165/0166 적용**

이 지점부터는 이 시리즈의 다른 문서(문자열/Imports/상수/Call Graph)에서 설명한 방법을 그대로 적용해 검증 로직을 찾는다.

**6) 예외 상황 인지**

문제 자체가 스택 카나리 우회, TLS 콜백을 이용한 안티디버깅, 커스텀 CRT 초기화 조작 등을 다루는 pwnable/안티디버깅 문제라면, 이 컴파일러 생성 코드 자체가 분석 대상이 될 수 있다. 이 경우 "무시해도 되는 패턴"이 아니라 "정확히 이해해야 하는 패턴"으로 취급을 바꿔야 한다.

## 명령어/단축키
- Call Graph로 진입점부터 훑기: REV-0166 참고(IDA View → Graphs → Function calls, Ghidra Function Call Graph/Function Call Trees)
- 라이브러리 함수 재식별: Ghidra **Analysis → One Shot → Function ID**, IDA는 FLIRT 시그니처 적용(File → Load file → FLIRT signature file 또는 자동 적용)
- 이름으로 필터링: Symbol Tree/Functions 목록 상단 필터에 `scrt`, `libc`, `csu` 등 입력해 한 번에 훑어보기

## 출력 해석
- Function ID/FLIRT가 정확히 인식한 함수는 이름이 실제 라이브러리 함수명(`__scrt_common_main_seh` 등) 그대로 나타난다. 이런 이름이 나왔다면 그 자체가 "이 함수는 컴파일러가 넣은 것"이라는 확실한 신호다.
- 반대로 인식에 실패해서 `FUN_` 이름이 그대로 남아 있더라도, 함수 내부가 스택 카나리 설정/검사만 하고 있거나, 여러 함수 포인터를 배열로 순회하며 호출만 하는 매우 정형화된 짧은 코드라면 컴파일러 생성 코드일 가능성을 의심해야 한다.
- 반대로 이런 부트스트랩 함수들을 지나 마침내 도달한 함수가 입력을 받고, 조건 분기가 여러 개 있고, 반복문으로 데이터를 처리한다면 그때부터가 실제로 "문제를 낸 사람이 작성한 로직"일 가능성이 크다.

## 흔한 실수
- `entry`에서 `main`까지 가는 모든 함수를 하나하나 처음부터 끝까지 읽으려고 시도하는 것 — 대부분 시간 낭비다. 이름 패턴만 확인하고 빠르게 통과시켜야 한다.
- 스트립된(symbol이 제거된) 바이너리에서 이런 함수 이름이 안 보인다고 해서 "전부 문제 로직"이라고 오해하는 것 — 이름이 없어도 내부 구조(짧고 정형화된 반복 패턴)로 컴파일러 코드임을 추정할 수 있다.
- 스택 카나리 체크 코드를 발견하고 "이게 검증 로직인가?" 하고 오래 분석하는 것 — 일반적인 crackme/reversing 문제에서는 이 코드가 문제와 무관한 컴파일러 보안 기능일 뿐인 경우가 대부분이다(단, pwnable 문제는 예외).
- C++ 바이너리에서 전역 객체 생성자(`_GLOBAL__sub_I_...`, `__static_initialization_and_destruction_0` 등)를 사용자 코드로 착각하는 것 — 이것도 C++ 컴파일러가 전역/정적 객체를 초기화하기 위해 자동 생성하는 코드다.

## 막혔을 때 다음 체크
- 진입점부터 어디까지가 부트스트랩이고 어디부터 `main`인지 구조를 그림으로 보고 싶다면 → REV-0166(함수 Call Graph로 핵심 로직 좁히기).
- `main`을 찾았는데 그 안에서도 컴파일러가 삽입한 코드(카나리 체크 등)와 실제 로직이 뒤섞여 보인다면 → 함수 시작/끝부분의 카나리 관련 코드는 무시하고 중간의 실질적인 조건 분기/반복문에 집중.
- main 함수 자체를 원천적으로 못 찾겠다면 → ../triage/rev-0009-finding-main.md(main 함수 찾기, 트리아지 관점)와 함께 참고.
- 부트스트랩 코드를 지나 도달한 함수가 진짜 검증 로직인지 확신이 안 서면 → REV-0163/0164/0165의 단서(문자열/Import/상수)로 교차 확인.

## 미니 예제
64비트 Linux ELF crackme를 Ghidra에서 열었다고 하자. `_start`부터 Function Call Graph(REV-0166)로 따라가 보면 다음과 같은 체인이 보인다.

```
_start → __libc_start_main → main
```

`__libc_start_main`은 glibc가 제공하는 초기화 함수로, 내부적으로 `__libc_csu_init`을 통해 `.init_array`에 등록된 초기화 함수들(그중 하나가 `frame_dummy`)을 호출한 뒤 최종적으로 `main`을 호출한다. 이 경로에서:

- `_start`, `__libc_start_main`, `__libc_csu_init`, `frame_dummy`: 전부 이름 패턴만으로 컴파일러/런타임 생성 코드임을 즉시 알 수 있으므로 내부를 읽지 않고 통과.
- `main`: 여기서부터 실제 분석 대상. `main` 안에서 `scanf`로 입력을 받고 `check_password`를 호출하는 코드가 보이면, 그때부터 REV-0163~0166의 방법을 적용한다.

이처럼 "이름 패턴 인식"만으로 실제로 읽어야 할 코드량을 처음부터 크게 줄일 수 있다.

## 관련 글
- REV-0157 — Ghidra Auto Analysis 옵션
- REV-0163 — 문자열에서 검증 함수로 이동하는 정적 분석
- REV-0164 — Imports에서 검증 함수 후보 좁히기
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기
- ../triage/rev-0009-finding-main.md — main 함수 찾기

## 출처/검증
- MSVC CRT 초기화 체인(`mainCRTStartup`, `__scrt_common_main_seh`, `__security_init_cookie`/`__security_check_cookie`)은 Microsoft Learn의 CRT 초기화 및 `/GS`(Buffer Security Check) 관련 공식 문서에 기반해 정리했다.
- glibc 초기화 체인(`_start`, `__libc_start_main`, `__libc_csu_init`, `frame_dummy`, `register_tm_clones`/`deregister_tm_clones`)은 glibc 소스 및 GCC가 생성하는 표준 ELF 시작 코드에 대한 널리 알려진 리버스 엔지니어링 레퍼런스 자료에 기반했다.
- Ghidra Function ID Analyzer와 IDA FLIRT 시그니처를 통한 라이브러리 함수 자동 식별: 각 도구의 공식 Help/문서 기준.
- 이 문서는 라이브 IDA/Ghidra 화면을 직접 캡처해 재검증하지는 않았으며, 공식 문서와 컴파일러/런타임의 잘 알려진 표준 동작을 기준으로 작성되었다. 컴파일러 버전에 따라 함수 이름이 다소 다를 수 있다.
