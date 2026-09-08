---
id: REV-0163
title: "문자열에서 검증 함수로 이동하는 정적 분석"
slug: "rev-0163-strings-to-check-function"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra, IDA]
keywords: ["문자열에서 함수 찾기", "Strings 창 활용", "정답 출력 문자열", "Correct Wrong 문자열 xref", "IDA Shift+F12", "Ghidra Defined Strings"]
aliases: ["문자열로 크랙미 풀기", "성공 문자열 역추적", "문자열 XREF로 함수 찾기"]
symptom_keywords: ["crackme에서 함수를 어디서부터 봐야 할지 모름", "정답 문자열은 찾았는데 그다음이 막힘", "Correct 문자열 어디서 쓰이는지 모름", "strings 결과에서 뭘 봐야 할지 모름"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
"성공했습니다", "Wrong password" 같은 **출력 문자열은 검증 로직으로 가는 가장 확실한 지름길**이며, 문자열을 찾아 그 문자열의 XREF(참조)를 따라 올라가면 대부분 몇 단계 안에 실제 비교/검증이 일어나는 함수에 도달한다 — 이것이 정적 분석에서 가장 먼저 시도해야 할 표준 절차다.

## 언제 검색해야 하나
- crackme/CTF 바이너리를 열었는데 함수가 너무 많아서 어디서부터 봐야 할지 막막할 때
- "Wrong Password", "Access Denied", "Correct!" 같은 메시지가 실행 결과로 나오는 것을 이미 확인했을 때
- IDA의 Strings 창이나 Ghidra의 Defined Strings 창을 열긴 했는데, 그다음에 뭘 해야 할지 모를 때
- 검증 함수 후보를 문자열 단서 없이 무작정 코드를 훑으며 찾고 있어서 시간이 오래 걸릴 때

## 핵심 개념
CTF crackme나 라이선스 체크 로직은 거의 예외 없이 **결과를 사용자에게 보여주기 위한 문자열**을 갖고 있다. `printf("Correct!\n")`, `MessageBox(NULL, "Wrong password", ...)` 같은 코드가 바이너리 안에 그대로 포함되어 있고, 이 문자열 리터럴은 컴파일 시 `.rodata`(ELF) 또는 `.rdata`(PE) 섹션에 고정 데이터로 저장된다.

이 방법이 강력한 이유는 **문자열은 은닉하기 어렵고(문자열 난독화가 없다면 평문 그대로 남는다), 그 문자열을 쓰는 코드는 반드시 검증 로직의 "결과가 나오는 지점"과 직접 연결되어 있기 때문**이다. 즉 문자열 → (그 문자열을 참조하는 코드) → (그 코드를 포함한 함수) → (그 함수 안에서 분기를 결정한 비교 연산)의 역순으로 따라가면, 굳이 `main`부터 순서대로 모든 함수를 읽지 않아도 핵심 로직에 최단 경로로 도달할 수 있다.

이 절차는 도구에 상관없이 다음 3단계로 요약된다:

1. **문자열 목록에서 결과 메시지를 찾는다.**
2. **그 문자열의 XREF(누가 참조하는가)를 확인한다.**
3. **참조하는 코드가 속한 함수로 이동해서, 그 문자열이 출력되기 직전의 조건 분기(`cmp`/`test` + `jz`/`jnz` 계열)를 찾는다.**

3단계에서 찾은 조건 분기가 바로 "무엇을 비교해서 성공/실패를 가르는가"의 답이며, 이것이 검증 로직의 핵심이다.

## 화면/코드에서 보이는 징후
- 바이너리를 실행하면(동적으로 한 번 돌려봤다면) "Wrong", "Incorrect", "Access Denied", "Correct", "Success" 같은 텍스트가 화면에 출력된다.
- `strings` 명령이나 도구의 문자열 목록에 이런 메시지들이 그대로 나열되어 있다.
- 함수 안에서 `call printf` 또는 `call MessageBoxA` 직전/직후에 문자열 주소를 로드하는 명령(`lea`, `push offset`, `mov edx, offset`)이 보인다.

## 가장 먼저 할 것
IDA는 **Shift+F12**(Strings 창), Ghidra는 **Window → Defined Strings**를 열어서 전체 문자열 목록을 훑는다. "Wrong", "Correct", "Success", "Fail", "Invalid", "denied" 같은 키워드가 포함된 항목을 먼저 찾는다.

## 단계별 절차

**1) 문자열 목록 열기**

- IDA: **Shift+F12**로 Strings 창을 연다. 목록이 비어 있거나 부실하면 창 안에서 우클릭 → **Setup** → 최소 문자열 길이나 인코딩(C string, Unicode 등) 옵션을 조정한 뒤 다시 스캔한다.
- Ghidra: **Window → Defined Strings**를 연다. Auto Analysis의 ASCII Strings Analyzer가 이미 문자열을 찾아 등록해 두었을 것이다(REV-0157 참고). 이 창이 비어 보이면 아직 Auto Analysis가 안 끝났거나 문자열 Analyzer가 꺼져 있었을 수 있다.

**2) 키워드로 결과 메시지 찾기**

목록 상단의 검색/필터 기능으로 `wrong`, `correct`, `success`, `fail`, `invalid`, `denied`, `unlock`, `flag` 같은 키워드를 입력해 후보를 좁힌다. 영어 메시지가 없다면 한국어 문자열(예: `"틀렸습니다"`, `"정답입니다"`)도 확인한다.

**3) 문자열의 XREF 확인**

후보 문자열을 더블클릭해서 그 데이터의 정의 위치로 이동한 뒤:
- IDA: 그 자리에서 **X** 키(또는 Jump → Jump to xref)를 눌러 "xrefs to" 목록을 연다.
- Ghidra: Listing에 표시된 `XREF[n]:` 줄을 보거나, 우클릭 → **References → Show References To**를 연다(REV-0160 참고).

**4) 참조 지점으로 이동**

XREF 목록에 나온 주소(보통 `lea`/`push offset`/`mov` 명령)로 이동한다. 이 명령이 속한 함수가 바로 "이 문자열을 실제로 출력하는 함수"다.

**5) 그 함수 전체를 디컴파일해서 읽기**

IDA는 **F5**, Ghidra는 함수로 이동하면 자동으로 뜨는 **Decompile 창**으로 그 함수의 pseudo C를 읽는다. 문자열이 출력되는 줄 바로 위(또는 그 문자열이 속한 `if`/`else` 블록의 조건문)를 찾는다.

**6) 조건 분기의 원인이 되는 비교 찾기**

`if (result == 0) { printf("Wrong"); }`처럼, 문자열 출력을 결정하는 조건식에서 비교 대상이 무엇인지 확인한다. 그 비교 대상이 `strcmp` 결과, 특정 상수와의 비교, 체크섬 계산 결과 등 실제 검증 로직의 핵심이다.

**7) 필요하면 한 단계 더 위로**

문자열을 출력하는 함수가 단순히 결과를 표시만 하는 얇은 래퍼(wrapper)이고, 실제 비교는 그 함수를 호출한 상위 함수에서 이루어지는 구조도 흔하다. 이 경우 REV-0160(XREF 따라가기)의 방법으로 이 함수를 호출하는 곳을 한 단계 더 거슬러 올라간다.

## 명령어/단축키
- IDA: 문자열 창 `Shift+F12`, xref 보기 `X`, 디컴파일 `F5`, 뒤로가기 `Esc`
- Ghidra: 문자열 창 **Window → Defined Strings**, XREF는 Listing의 `XREF[n]:` 또는 우클릭 → References → Show References To, 디컴파일은 자동 표시
- 공통: 함수 이름 바꾸기(찾은 함수를 `check_password` 등으로 즉시 정리, REV-0161 참고)

## 출력 해석
- 문자열의 XREF가 여러 개면, 그 문자열이 여러 곳에서 재사용된다는 뜻이다(예: 여러 종류의 실패를 같은 메시지로 처리). 이 경우 각 참조 지점을 모두 확인해서 어떤 조건에서 어느 경로로 오는지 정리한다.
- 문자열의 XREF가 하나도 없다면, 그 문자열은 실제로 코드에서 사용되지 않는 죽은 데이터이거나, 포맷 문자열 테이블처럼 간접적으로(포인터 배열을 통해) 참조되고 있어 정적 XREF로 안 잡혔을 수 있다. 이 경우 REV-0165(상수 검색)나 REV-0166(Call Graph)로 접근 방식을 바꿔야 한다.
- 도달한 함수가 `FUN_` 같은 기본 이름이라도 걱정할 필요 없다 — 이름이 없다는 것과 그 함수가 중요한 함수라는 것은 무관하다. REV-0161로 이름을 정리하면 된다.

## 흔한 실수
- Strings 창에서 원하는 문자열이 안 보인다고 바로 포기하는 것 — 최소 길이 필터(기본 5자 등)에 걸려 짧은 문자열이 숨어 있거나, 유니코드 인코딩 옵션이 꺼져 있어 못 보는 경우가 흔하다. 필터/옵션을 먼저 점검해야 한다.
- 문자열을 찾은 뒤 XREF를 확인하지 않고 그 주소 근처 코드를 위아래로 무작정 스크롤하며 찾는 것 — XREF 기능을 쓰면 즉시 정확한 참조 지점으로 이동할 수 있는데 이를 활용하지 않으면 시간이 오래 걸린다.
- "Correct" 문자열을 출력하는 함수만 보고 그 함수 자체가 검증 로직 전부라고 결론짓는 것 — 실제로는 그 함수를 호출하기 직전에 이미 검증이 끝나 있고, 이 함수는 결과만 출력하는 경우가 많다. 반드시 그 함수를 호출한 상위 함수(호출자)의 조건 분기까지 확인해야 한다.
- 여러 언어(영어/한국어)로 된 메시지 중 한쪽만 검색하는 것 — 한국 CTF 문제는 한국어 메시지를 쓰는 경우도 많으므로 양쪽 다 검색어에 포함해야 한다.

## 막혔을 때 다음 체크
- 문자열의 XREF가 없거나 간접 참조라 못 찾겠다면 → REV-0164(Imports에서 검증 함수 후보 좁히기)나 REV-0165(상수 검색으로 알고리즘 찾기)로 접근 방식 전환.
- 도달한 함수의 로직이 복잡해서 뭘 비교하는지 한눈에 안 들어오면 → REV-0158(Ghidra Decompiler 창 읽기), REV-0162(Hex View로 디컴파일 결과 검증하기)로 값부터 확정.
- 여러 함수가 얽혀서 어디가 진짜 핵심인지 헷갈리면 → REV-0166(함수 Call Graph로 핵심 로직 좁히기)로 전체 구조를 시각적으로 파악.
- 찾은 로직을 실제로 풀어서 정답을 계산하고 싶다면 → REV-0168(정적 분석 결과를 Python 의사코드로 옮기기).

## 미니 예제
가상의 crackme `guess.exe`를 분석한다고 하자. 실행하면 비밀번호를 입력받고 "Wrong password!\n" 또는 "Correct! Here is your flag.\n"을 출력한다.

**1단계 — 문자열 찾기**: Strings 창에서 `Wrong password!`를 발견. 주소 `0x00403050`.

**2단계 — XREF 확인**: 그 문자열 위에서 IDA는 `X`, Ghidra는 Show References To. 참조 지점이 `0x00401234` 단 하나로 나옴.

**3단계 — 함수로 이동, 디컴파일**: `0x00401234`가 속한 함수(`FUN_00401200` 또는 `sub_401200`)로 이동해 F5/Decompile 결과를 보니 다음과 유사한 코드가 보인다.

```c
int FUN_00401200(char *input) {
  int cmp;
  cmp = strcmp(input, "L3tM3In_2024");
  if (cmp != 0) {
    puts("Wrong password!");
    return 0;
  }
  puts("Correct! Here is your flag.");
  return 1;
}
```

**4단계 — 결론**: 이 시점에서 이미 정답은 `"L3tM3In_2024"`라는 사실이 명확히 드러난다. `strcmp`가 Import 목록에 있었다는 사실(REV-0164에서 다루는 "Imports에서 후보 좁히기")과 결합했다면 훨씬 더 빨리 이 함수에 도달할 수도 있었을 것이다 — 즉 "문자열에서 시작"과 "Imports에서 시작"은 같은 목적지로 가는 두 가지 다른 출발점이며, 상황에 따라 둘 중 더 단서가 뚜렷한 쪽부터 시작하면 된다.

## 관련 글
- REV-0159 — Ghidra Function 목록과 Symbol Tree
- REV-0160 — Ghidra XREF 따라가기
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0164 — Imports에서 검증 함수 후보 좁히기
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기
- ../triage/rev-0009-finding-main.md — main 함수를 찾는 또 다른 트리아지 접근

## 출처/검증
- IDA Strings 창(`Shift+F12`)과 xref 보기(`X`): Hex-Rays 공식 IDA User Guide 및 단축키 레퍼런스 기준.
- Ghidra Defined Strings 창(Window → Defined Strings)과 ASCII Strings Analyzer: Ghidra 공식 Help 문서 기준.
- "문자열 → XREF → 함수" 역추적 절차는 도구 문서상의 기능 설명이 아니라, CTF/리버싱 커뮤니티에서 널리 통용되는 표준 분석 방법론(문자열 기반 트리아지)에 근거해 정리했다.
- 이 문서는 라이브 IDA/Ghidra 화면을 직접 캡처해 재검증하지는 않았으며, 공식 문서와 일반적으로 통용되는 UI 동작을 기준으로 작성되었다.
