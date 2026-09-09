---
id: REV-0782
title: "Ghidra에서 Decompile 결과가 비어있을 때"
slug: "rev-0782-ghidra-decompile-empty"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Decompile 비어있음", "Ghidra Decompiler 창 아무것도 없음", "Ghidra bad instruction", "Ghidra 함수 미인식", "Ghidra Decompile empty"]
aliases: ["Ghidra 디컴파일 창이 빔", "Ghidra F5 대응 안 됨", "Ghidra 함수 클릭해도 코드 안 나옴"]
symptom_keywords: ["Ghidra Decompile 창에 아무것도 안 뜸", "Ghidra 함수를 클릭했는데 빈 화면", "Ghidra에서 코드가 안 생김", "Ghidra 회색 화면만 나옴"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra의 Decompile 창이 텅 비어 있는 것은 대부분 디컴파일러가 실패한 게 아니라 **커서가 함수 내부가 아닌 곳(정의되지 않은 바이트, 순수 데이터, 함수 밖 갭)에 있거나, 그 주소가 아직 함수(Function)로 정의되지 않았기 때문**이며, Listing에서 커서 위치와 함수 경계부터 확인하면 대부분 해결된다.

## 언제 검색해야 하나
- 함수처럼 보이는 코드를 클릭했는데 Decompile 창에 아무 내용도 없을 때
- Decompile 창에 회색 배경만 있고 `undefined FUN_xxx(void)` 같은 최소한의 시그니처조차 안 보일 때
- 특정 주소로 이동(`G`)했더니 Listing에는 명령어가 보이는데 Decompile 창만 비어 있을 때
- 함수 안에 있는 것 같은데 Decompile 패널이 갱신되지 않을 때

## 핵심 개념
Ghidra의 Decompile 창은 "현재 커서가 속한 함수"를 디컴파일해서 보여주는 구조다. 즉 커서가 **어떤 함수의 범위 안에도 속하지 않는 주소**에 있으면 디컴파일할 대상 자체가 없으므로 창이 비어 있는 것이 정상이다. 이 상태가 되는 대표적인 이유는 다음과 같다.

1. **커서가 함수로 정의되지 않은 코드 위에 있음**: Auto Analysis가 그 주소를 함수 시작으로 인식하지 못해서, Listing에는 명령어가 보이지만 Symbol Tree의 Functions 목록에는 없는 상태다.
2. **커서가 데이터(문자열, 구조체, 배열) 위에 있음**: 함수가 아니라 데이터로 정의된 영역이라 애초에 디컴파일 대상이 아니다.
3. **커서가 Undefined 바이트(회색 `??`) 위에 있음**: 아직 코드로도 데이터로도 정의되지 않은 영역이라 Listing 자체도 의미 있는 명령어를 보여주지 못한다.
4. **함수 본문이 실제로 0바이트에 가깝게 정의됨**: 함수 경계가 잘못 잡혀서 시작하자마자 바로 끝나 버린 극단적인 경우(REV-0783).
5. **Decompiler가 그 함수 처리 도중 내부적으로 실패**: 이 경우는 완전히 빈 화면이 아니라 대개 에러 메시지나 `// WARNING:` 주석이 남는 경우가 많아 1~4번과는 구분된다.

## 화면/코드에서 보이는 징후
- Decompile 창이 완전히 흰/회색 배경으로 비어 있고, 함수 시그니처 한 줄조차 없다.
- Listing 창에는 디스어셈블리 명령어가 보이는데도 Decompile 창만 비어 있다.
- Symbol Tree의 Functions 목록에서 해당 주소를 검색해도 항목이 없다.

## 가장 먼저 할 것
현재 커서 주소를 확인한 뒤, Symbol Tree의 Functions 목록에서 그 주소를 포함하는 함수가 실제로 정의되어 있는지부터 확인한다. 정의되어 있지 않다면 함수로 만드는 것이 먼저다.

## 단계별 절차

**1) 커서가 속한 영역의 종류 확인**

Listing에서 해당 줄의 왼쪽 여백(주소 옆)을 본다. 회색 `??` 바이트가 보이면 Undefined 상태이고, 데이터 타입(예: `ds "..."`, `dd`)이 보이면 데이터로 정의된 것이다. 어느 쪽도 아니고 명령어가 보이는데 Decompile만 비어 있다면 "코드로는 인식됐지만 함수로는 정의되지 않은" 상태다.

**2) Undefined 바이트라면 먼저 코드/데이터로 재정의**

회색 바이트라면 시작 주소로 커서를 옮기고 `D`(Disassemble)로 코드로 재해석을 시도한다. 결과가 정상적인 명령어처럼 보이면 함수 시작점으로 진행하고, 이상한 명령어가 잔뜩 나오면 시작 오프셋이 틀렸을 가능성이 크므로 `C`(Clear Code Bytes)로 되돌리고 다른 시작 위치를 찾는다.

**3) 함수로 정의**

코드로는 인식되지만 함수가 아니라면, 함수의 실제 시작 주소(보통 `push`/`endbr64`/`sub rsp` 같은 표준 프롤로그가 시작되는 지점)에 커서를 놓고 우클릭 → **Create Function**(또는 단축키 없으면 메뉴 Functions → Create Function)을 실행한다.

**4) 함수 생성 후 재확인**

함수가 생성되면 Decompile 창이 즉시 갱신되어 최소한 `undefined FUN_00401230(void) { ... }` 형태의 결과가 나타나야 한다. 여전히 비어 있으면 강제로 함수 자체가 다시 갱신되도록 다른 함수를 한 번 클릭했다가 되돌아온다.

**5) 데이터로 정의된 코드라면 되돌리기**

Auto Analysis가 실제 코드를 문자열/데이터로 잘못 정의한 경우, 그 영역에서 `C`(Clear Code Bytes)로 정의를 해제한 뒤 `D`로 다시 코드로 잡고 3번 절차를 반복한다.

**6) 그래도 비어 있으면 Analyzer 로그 확인**

위 방법으로도 안 되면 단순 미정의 문제가 아니라 디컴파일러 내부 실패일 수 있다. Decompile 창 우클릭 → **Show C Preprocessor output** 같은 진단 메뉴나, 함수를 다시 **Clear Code Bytes 후 재분석**해 근본 원인이 사라지는지 확인한다.

## 명령어/단축키
```text
G          Go To — 특정 주소로 커서 이동
D          Disassemble — Undefined 바이트를 코드로 재해석
C          Clear Code Bytes — 코드/데이터 정의 해제
우클릭 → Create Function   함수로 새로 정의
Ctrl+E     Decompile 패널 토글(안 보일 때 다시 켜기)
```

## 출력 해석
- 함수를 만들자마자 Decompile 창에 `undefined4 FUN_00401230(void)`처럼 최소 시그니처만 뜨고 본문이 부실하면, 함수는 인식됐지만 내부 코드 인식이 아직 불완전한 상태다 — REV-0783(함수 경계) 절차로 이어서 확인한다.
- Decompile 창에 `// WARNING: ...` 주석과 함께 일부 코드만 보이면 완전히 빈 것과는 다른 문제(디컴파일러가 일부 명령어 해석에 실패)이므로 원인이 다르다.
- 함수를 만든 직후에도 계속 비어 있다면, 그 함수가 실제로는 크기 0에 가깝게 다른 함수와 겹쳐 정의되어 있을 가능성이 있다 — Functions 목록에서 함수 크기를 확인한다.

## 흔한 실수
- 커서가 데이터 영역에 있다는 걸 모르고 "디컴파일러가 고장났다"고 오해하는 것 — Listing의 바이트 종류부터 먼저 확인해야 한다.
- Undefined 바이트 위에서 바로 Create Function을 시도해 실패하는 것 — 먼저 `D`로 코드로 만든 뒤에 함수로 정의해야 한다.
- 함수를 만들었는데도 안 보이는 게 캐시 문제라고 착각해서 Ghidra를 재시작하는 것 — 대부분은 다른 함수를 한 번 클릭했다 돌아오면 갱신된다.
- 실제로는 함수 경계 자체가 잘못 잡힌 문제(REV-0783)인데 계속 같은 자리에서 재정의만 반복하는 것.

## 막혔을 때 다음 체크
- 함수는 생성됐는데 로직이 중간에 끊기거나 이상하게 커 보이면 → REV-0783.
- 코드/데이터 재해석 자체가 처음이라 헷갈리면 → REV-0784(문자열 인식 문제)와 함께 Undefined 바이트 개념을 확인.
- 이 문제가 특정 함수 하나가 아니라 파일 전체에서 반복되면 → REV-0781(Auto Analysis가 끝나지 않을 때)이나 REV-0157(Analyzer 옵션)부터 재점검.
- IDA에서 겪는 비슷한 증상(Decompiler Failed)의 원인 분류가 궁금하면 → REV-0152.

## 미니 예제
`chall` 바이너리에서 문자열 XREF를 따라 `0x00401450`으로 이동했다고 하자.

1. Listing에 `push rbp` 등 정상적인 명령어가 보이지만 Decompile 창은 비어 있다.
2. Symbol Tree → Functions에서 `00401450`을 검색해도 없다 → 함수로 정의되지 않은 상태.
3. `0x00401450`에 커서를 놓고 우클릭 → Create Function.
4. Decompile 창에 즉시 `undefined8 FUN_00401450(void) { ... }` 형태의 코드가 나타난다.
5. `L`로 함수 이름을 `check_password`로 바꾸고 분석을 이어간다.

## 관련 글
- REV-0783 — Ghidra에서 함수 경계가 잘못 잡혔을 때
- REV-0784 — Ghidra에서 문자열이 인식되지 않을 때
- REV-0781 — Ghidra Auto Analysis가 끝나지 않을 때
- REV-0158 — Ghidra Decompiler 창 읽기

## 출처/검증
- Decompile 창이 "현재 커서가 속한 함수"만 표시하는 구조라는 점과 Create Function/Clear Code Bytes/Disassemble의 동작: Ghidra 공식 Help 문서(CodeBrowser, DecompilerPlugin 토픽) 기준.
- Undefined 바이트, 코드/데이터 재정의 흐름: Ghidra 공식 Help 문서의 Listing 편집 관련 토픽 기준.
- 라이브 환경에서 모든 실패 케이스를 재현 검증하지는 않았으며, 공식 문서와 통상적인 사용 경험을 바탕으로 정리했다.
