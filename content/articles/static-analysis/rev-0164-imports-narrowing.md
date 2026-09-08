---
id: REV-0164
title: "Imports에서 검증 함수 후보 좁히기"
slug: "rev-0164-imports-narrowing"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra, IDA]
keywords: ["Imports 탭 활용", "strcmp xref 분석", "라이브러리 함수 후보 좁히기", "IDA Imports 창", "Ghidra Imports 폴더", "가짜 strcmp 시나리오"]
aliases: ["임포트로 검증함수 찾기", "strcmp memcmp 어디서 쓰이나", "라이브러리 함수 필터링"]
symptom_keywords: ["strcmp가 여러 군데서 호출됨", "어떤 strcmp가 진짜 검증인지 모름", "Imports 탭에서 뭘 봐야 할지 모름", "라이브러리 함수 xref가 너무 많음"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
프로그램이 사용하는 외부 라이브러리 함수 목록(Imports)은 **"이 바이너리가 무엇을 할 수 있는가"에 대한 압축된 요약**이며, `strcmp`/`memcmp`/`MessageBoxA`처럼 비교·검증과 직결된 함수를 골라 그 XREF를 모두 나열한 뒤 호출 지점 각각을 짧게 검토하는 것이 문자열 단서가 없거나 부족할 때 가장 효율적인 대안 경로다.

## 언제 검색해야 하나
- REV-0163(문자열에서 검증 함수로 이동하기)을 시도했는데 쓸 만한 결과 문자열이 없거나(예: 리소스 문자열 테이블, 암호화된 문자열) XREF가 간접적이어서 막혔을 때
- `strcmp`, `memcmp`, `strncmp` 같은 비교 함수의 XREF가 여러 개 나와서 어느 것이 실제 검증 로직인지 판단이 안 될 때
- Import 목록 자체가 너무 길어서 어디부터 봐야 할지 모를 때
- 정적 링크(static linking)로 인해 `strcmp` 자체는 안 보이지만 비슷한 역할을 하는 함수를 찾아야 할 때

## 핵심 개념
Import는 프로그램이 직접 구현하지 않고 운영체제/런타임 라이브러리에서 빌려 쓰는 함수 목록이다. Windows PE는 Import Address Table(IAT), Linux ELF는 PLT/동적 심볼 테이블을 통해 이 정보가 바이너리에 명시적으로 남는다. 이 목록은 코드 전체를 읽지 않고도 "이 프로그램이 파일을 여는지, 네트워크 통신을 하는지, 문자열을 비교하는지"를 짐작하게 해주는 강력한 요약 정보다.

검증/비교 로직 탐색에 특히 유용한 함수군:
- **문자열 비교**: `strcmp`, `strncmp`, `_stricmp`(대소문자 무시), `wcscmp`(유니코드), `lstrcmpA/W`
- **메모리 비교**: `memcmp`
- **해시/암호 관련**: `CryptHashData`, `MD5_Update` 계열(정적 링크된 경우 이름이 안 보일 수 있음)
- **UI 메시지 출력**: `MessageBoxA/W`, `printf`, `puts`, `fprintf`
- **입력 처리**: `scanf`, `gets`, `fgets`, `GetDlgItemTextA`, `ReadFile`

전략은 REV-0163과 대칭적이다. REV-0163은 "출력 문자열"에서 거슬러 올라갔다면, 이 문서는 "라이브러리 함수 호출"에서 거슬러 올라간다. 두 방법을 병행하면 서로 교차검증이 되어, 같은 함수에 두 경로로 모두 도달했을 때 확신을 가질 수 있다.

**주의할 함정 — "가짜" 호출 지점**: 하나의 라이브러리 함수는 프로그램 전체에서 검증 목적이 아닌 곳에도 얼마든지 쓰인다. 예를 들어 `strcmp`가 명령줄 인자를 파싱하는 코드(`argv[1] == "-v"`인지 확인), 설정 파일 경로를 비교하는 코드, 다국어 문자열을 고르는 코드 등 **검증과 무관한 곳에서도 호출**될 수 있다. XREF 개수가 여러 개라면 이 함정을 염두에 두고 각 호출 지점을 실제로 열어봐야 한다.

## 화면/코드에서 보이는 징후
- IDA의 Imports 탭(또는 Ghidra Symbol Tree의 Imports 폴더)에 DLL/공유 라이브러리별로 함수 목록이 나열되어 있다.
- 비교 함수 하나를 골라 XREF를 열었더니 호출 지점이 5개, 10개씩 나와서 어디부터 봐야 할지 막막하다.

## 가장 먼저 할 것
Imports 목록을 훑어서 비교/검증과 관련 있어 보이는 함수(`strcmp` 계열, `memcmp`)를 고른 뒤, 그 함수의 XREF 개수부터 확인한다. 개수가 적으면(1~3개) 전부 확인하고, 많으면 우선순위를 정해서(아래 절차 참고) 순서대로 좁혀나간다.

## 단계별 절차

**1) Imports 목록 열기**

- IDA: **View → Open subviews → Imports**(또는 기본 탭에 이미 있음).
- Ghidra: Symbol Tree(왼쪽 패널)의 **Imports** 폴더를 펼친다(REV-0159 참고).

**2) 비교/검증 관련 함수 선별**

목록을 훑으며 `strcmp`, `strncmp`, `_stricmp`, `memcmp`, `wcscmp` 등을 찾는다. 없다면 `MessageBoxA/W`, `printf` 계열처럼 "결과를 알려주는" 함수로 눈을 돌린다.

**3) 함수 하나를 선택해 XREF 확인**

- IDA: Import 목록에서 함수를 더블클릭해 그 위치로 이동한 뒤 **X**(xrefs to)로 호출 지점 목록을 연다.
- Ghidra: Imports 폴더에서 함수를 더블클릭해 이동한 뒤 우클릭 → **References → Show References To**(REV-0160 참고).

**4) XREF 개수에 따라 전략 분기**

- **1~3개**: 전부 하나씩 열어서 확인한다.
- **4개 이상**: 아래 5~6단계의 우선순위 규칙을 적용해 순서를 정한다.

**5) 우선순위 규칙 — 호출을 감싼 함수의 "무게" 보기**

각 XREF가 속한 함수로 이동해서, 그 함수가 단순히 몇 줄짜리 얇은 래퍼인지, 아니면 반복문/여러 조건 분기가 있는 좀 더 "무거운" 함수인지 훑어본다(REV-0159의 Functions window에서 Function Size 정렬과 함께 쓰면 좋다). 검증 로직은 보통 입력값을 반복적으로 처리하거나 여러 단계를 거치는 함수 안에 있는 경우가 많다.

**6) 우선순위 규칙 — 비교 대상이 상수/고정 데이터인지 보기**

비교 함수의 두 번째 인자(비교 대상)가 **프로그램 시작 시 사용자로부터 받은 값이 아니라 코드에 박혀 있는 상수 문자열/데이터**를 가리키는 호출 지점을 우선한다. 예를 들어 `strcmp(argv[1], "-v")`는 명령줄 옵션 파싱이지 검증 로직이 아닐 가능성이 크고, `strcmp(user_input_buffer, "S3cr3t")`처럼 사용자 입력과 고정 문자열을 비교하는 형태가 검증 로직일 가능성이 크다.

**7) 후보를 좁힌 뒤 디컴파일로 확정**

후보 함수로 이동해 F5(IDA)/Decompile(Ghidra)로 실제 로직을 읽고, REV-0163에서 설명한 것처럼 그 비교 결과가 성공/실패 메시지 출력으로 이어지는지 확인해 최종 확정한다.

## 명령어/단축키
- IDA: Imports 탭, `X`(xrefs to), `F5`(디컴파일), `Ctrl+↓`/`Ctrl+↑`(함수 간 이동)
- Ghidra: Symbol Tree → Imports, 우클릭 → References → Show References To, Window → Functions(Function Size 정렬)
- 공통: 후보 함수를 찾자마자 `L`(Ghidra)/`N`(IDA, Rename)로 즉시 이름을 정리해두면 나중에 헷갈리지 않는다.

## 출력 해석
- XREF 목록에서 같은 함수(예: `strcmp`)를 호출하는 지점이 프로그램 초반(인자 파싱 부근)과 중반(입력 처리 이후)에 나뉘어 있다면, 전자는 옵션 파싱, 후자가 검증 로직일 가능성이 높다는 정황 증거가 된다.
- Import 자체가 안 보이는 함수(예: 정적 링크된 바이너리)는 Function ID Analyzer(Ghidra)나 FLIRT 시그니처(IDA)가 라이브러리 함수임을 알아서 식별해 실제 이름을 붙여줄 수도 있다. 이 경우 Imports 폴더가 아니라 Functions 목록에서 같은 이름으로 검색해야 한다.
- 아무 비교 함수도 Import되어 있지 않다면, 검증 로직이 라이브러리 함수 없이 직접 반복문으로 바이트 단위 비교를 구현했을 가능성이 크다. 이 경우 REV-0165(상수 검색)로 전략을 바꾼다.

## 흔한 실수
- Import된 함수 이름 하나만 보고 "이 함수가 곧 검증 로직"이라고 오해하는 것 — `strcmp`는 어디까지나 라이브러리 함수이고, 실제 검증 로직은 그 함수를 호출하는 이 바이너리의 코드에 있다.
- XREF가 여러 개인데 첫 번째로 나온 것만 확인하고 결론짓는 것 — 위에서 설명한 "가짜 호출 지점" 함정에 그대로 걸리는 경우다. 최소한 각 호출 지점이 속한 함수 이름/주변 코드를 훑어보고 판단해야 한다.
- 대소문자 구분 없는 비교(`_stricmp`, `lstrcmpiA`)를 놓치고 `strcmp`만 검색하는 것 — 검증 로직이 대소문자를 구분하지 않도록 구현되어 있으면 다른 함수 이름을 쓴다.
- 정적 링크 바이너리에서 Imports 목록이 짧다고 "비교 함수를 아예 안 쓴다"고 단정하는 것 — 라이브러리 함수가 바이너리 내부에 통째로 포함(정적 링크)되어 있으면 Imports에는 안 뜨고 Functions 목록에 일반 함수처럼 섞여 있다.

## 막혔을 때 다음 체크
- 문자열 단서로 접근하는 편이 나을 것 같다면 → REV-0163(문자열에서 검증 함수로 이동하는 정적 분석).
- 비교 함수 자체가 안 보이거나 정적 링크로 숨어 있다면 → REV-0165(상수 검색으로 알고리즘 찾기).
- 후보가 여러 개라 전체 호출 구조를 시각적으로 보고 싶다면 → REV-0166(함수 Call Graph로 핵심 로직 좁히기).
- 후보 함수를 찾았는데 그 안의 비교 대상 값을 직접 확인하고 싶다면 → REV-0162(Hex View로 디컴파일 결과 검증하기).

## 미니 예제
`login_check.exe`의 Imports 목록에 `strcmp`가 있고, XREF를 확인하니 호출 지점이 3곳(`0x00401050`, `0x004013A0`, `0x00401820`)이라고 하자.

1. `0x00401050`이 속한 함수를 열어보니:
```c
if (argc >= 2 && strcmp(argv[1], "--debug") == 0) {
  debug_mode = 1;
}
```
   → 명령줄 옵션 파싱용. 검증 로직과 무관한 "가짜" 후보.

2. `0x004013A0`이 속한 함수를 열어보니:
```c
if (strcmp(config_path, "config.ini") == 0) {
  load_default_config();
}
```
   → 설정 파일 경로 비교. 이것도 검증 로직이 아니다.

3. `0x00401820`이 속한 함수를 열어보니:
```c
char input[32];
scanf("%31s", input);
if (strcmp(input, "L3tM3In_2024") == 0) {
  puts("Correct!");
} else {
  puts("Wrong password!");
}
```
   → `scanf`로 사용자 입력을 받은 직후, 그 입력을 고정 문자열과 비교하고 결과 메시지를 출력한다. 이것이 진짜 검증 로직이다.

이처럼 같은 `strcmp` import라도 XREF가 여러 개면 반드시 각각을 열어 "사용자 입력과 고정 값을 비교하는가"라는 기준으로 골라내야 한다. 이 예제는 REV-0163의 "Wrong password" 문자열 예제와 동일한 함수(`0x00401820`)에, 문자열 단서 없이 Import 단서만으로도 도달할 수 있음을 보여준다.

## 관련 글
- REV-0159 — Ghidra Function 목록과 Symbol Tree
- REV-0160 — Ghidra XREF 따라가기
- REV-0163 — 문자열에서 검증 함수로 이동하는 정적 분석
- REV-0165 — 상수 검색으로 알고리즘 찾기
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기

## 출처/검증
- IDA Imports 탭과 xref 보기(`X`): Hex-Rays 공식 IDA User Guide 및 단축키 레퍼런스 기준.
- Ghidra Symbol Tree의 Imports 폴더와 References → Show References To: Ghidra 공식 Help 문서 기준.
- "Import 함수에서 거슬러 올라가는" 분석 전략과 가짜 호출 지점(디코이) 판별 기준은 도구 자체의 기능이 아니라 CTF/리버싱 실무에서 통용되는 분석 방법론에 근거해 정리했다.
- 이 문서는 라이브 IDA/Ghidra 화면을 직접 캡처해 재검증하지는 않았으며, 공식 문서와 일반적으로 통용되는 UI 동작을 기준으로 작성되었다.
