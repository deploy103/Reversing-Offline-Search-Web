---
id: REV-0748
title: "Ghidra Comments와 IDA Comments 비교"
slug: "rev-0748-ghidra-vs-ida-comments"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["Ghidra Comments", "IDA Comments", "Ghidra Plate Comment", "IDA repeatable comment", "EOL comment", "Ghidra Pre Post Comment"]
aliases: ["Ghidra 주석 종류", "IDA 주석 종류", "디스어셈블러 코멘트 비교", "Ghidra IDA 주석 대응표"]
symptom_keywords: ["Ghidra 주석 단축키가 뭔가", "IDA 반복 주석이 뭔가", "Ghidra Plate Comment와 EOL Comment 차이", "함수 전체 요약 주석 다는 법"]
source_ids: ["SRC-GHIDRA-DOCS", "SRC-IDA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra와 IDA 모두 "한 줄 메모"부터 "함수 전체 요약", "여러 곳에 동시에 나타나는 반복 주석"까지 여러 종류의 주석을 구분해 제공하며, Ghidra의 EOL/Pre/Post/Plate/Repeatable Comment와 IDA의 Comment/Repeatable Comment/Anterior·Posterior Lines/함수 주석을 서로 대응시켜 외워두면 도구를 오가도 헷갈리지 않는다.

## 언제 검색해야 하나
- 다른 사람(또는 과거의 자신)이 분석해 둔 파일을 열었는데 주석 종류가 헷갈릴 때
- IDA 경험자가 Ghidra에서 반복 주석(Repeatable Comment)을 어디서 찾는지 모를 때
- 함수 전체 요약과 한 줄 메모를 구분해서 남기고 싶을 때
- 주석 단축키가 도구마다 달라서 계속 헷갈릴 때

## 핵심 개념

### 공통적으로 필요한 이유
분석 중 알아낸 사실(이 함수는 flag 검증, 이 상수는 XOR key 등)을 코드에 직접 남겨두지 않으면 나중에 같은 함수를 다시 열었을 때 처음부터 다시 분석해야 한다. 두 도구 모두 "어디에", "얼마나 넓은 범위에" 주석을 붙일지에 따라 여러 종류의 주석 타입을 제공한다.

### Ghidra의 주석 종류
- EOL(End of Line) Comment: 명령어 한 줄 끝에 붙는 가장 흔한 주석. 단축키 `;`.
- Pre Comment: 명령어 앞(위)에 붙는 주석. 단축키 `Ctrl+;`. 함수 안 특정 블록 시작 전에 설명을 붙일 때 쓴다.
- Post Comment: 명령어 뒤(아래)에 붙는 주석. 단축키 `Ctrl+Shift+;`.
- Plate Comment: 함수 맨 위에 박스 형태로 크게 표시되는 주석. 함수 전체 요약 설명에 적합하며, Decompile 창에도 함수 시그니처 위에 그대로 나타난다.
- Repeatable Comment: 같은 주소를 참조하는 다른 위치에도 동일하게 나타나는 주석(예: 전역 변수 하나에 붙이면 그 변수를 쓰는 모든 곳에 같이 보인다).

(정확한 단축키는 Ghidra 버전/키 설정에 따라 다를 수 있으니 Edit → Tool Options → Key Bindings 또는 메뉴 위에서 `F4`로 재확인 권장)

### IDA의 주석 종류
- 일반 주석(Comment): 명령어 줄 끝에 붙는 기본 주석. 단축키 `:`(콜론).
- 반복 주석(Repeatable Comment): 같은 주소/피연산자를 참조하는 다른 위치에도 자동으로 나타나는 주석. 단축키 `;`(세미콜론). Ghidra의 Repeatable Comment와 개념이 유사하다.
- Anterior/Posterior Lines: 명령어 위/아래에 여러 줄로 붙이는 주석(Ghidra의 Pre/Post Comment와 유사). 버전에 따라 메뉴 경로가 다를 수 있다.
- 함수 주석: 함수 시작 부분에 붙이는 주석으로 Ghidra의 Plate Comment와 유사한 역할을 한다.

### 대응 관계로 외우기
| 목적 | Ghidra | IDA |
|---|---|---|
| 한 줄 끝 간단 메모 | EOL Comment(`;`) | Comment(`:`) |
| 여러 곳에 같이 뜨는 주석 | Repeatable Comment | Repeatable Comment(`;`) |
| 명령어 앞/뒤 여러 줄 | Pre/Post Comment | Anterior/Posterior Lines |
| 함수 전체 요약 | Plate Comment | 함수 주석 |

이렇게 표로 대응시켜 외워두면 한 도구에 익숙한 사람이 다른 도구로 옮겨갈 때 헷갈림을 크게 줄일 수 있다.

### Decompile/Pseudocode 창에서의 표시
Ghidra Plate Comment는 Decompile 창의 함수 선언부 바로 위에 박스로 나타나고, EOL Comment는 해당 줄 끝에 회색으로 나타난다. IDA F5 디컴파일 창에서도 붙인 주석이 유사한 형태로 pseudocode에 반영된다(정확한 표시 여부는 주석 타입과 IDA 버전에 따라 다를 수 있다).

## 화면/코드에서 보이는 징후
이미 분석해 둔 파일에서 어떤 주석이 "함수 전체 요약"이고 어떤 것이 "한 줄 메모"인지 구분이 안 되거나, IDA 경험자가 Ghidra에서 반복 주석이 어디 있는지 못 찾을 때.

## 가장 먼저 할 것
함수 전체에 대한 결론은 Plate Comment(Ghidra)/함수 주석(IDA)에, 특정 줄에 대한 메모는 EOL Comment/Comment에 구분해서 남기는 습관부터 들인다.

## 단계별 절차
1. 함수를 다 분석했으면 함수 맨 위에서 Plate Comment(Ghidra: 함수 이름 줄 우클릭 → Comments → Set Plate Comment / IDA: 함수 시작에서 주석 추가)로 한 줄 요약을 남긴다
2. 핵심 로직 줄에는 EOL Comment(`;`)/Comment(`:`)로 짧은 메모
3. 같은 상수/전역변수가 여러 곳에서 쓰이면 Repeatable Comment로 한 번만 달아도 모든 참조 위치에 반영되게 한다
4. 블록 단위 설명이 필요하면 Pre/Post Comment(Ghidra) 또는 Anterior/Posterior Lines(IDA)를 사용한다

## 명령어/단축키
- Ghidra: `;`(EOL) / `Ctrl+;`(Pre) / `Ctrl+Shift+;`(Post) / 함수 우클릭 → Comments → Set Plate Comment
- IDA: `:`(일반 주석) / `;`(반복 주석) / Anterior/Posterior 관련 메뉴(버전에 따라 다름)

## 출력 해석
Ghidra Bookmarks 창(REV-0747)의 Note와 실제 코드에 남긴 Comment는 다른 개념이다 — Bookmark는 "표시", Comment는 "설명 텍스트"이며 둘을 함께 쓰면(중요 지점 Bookmark + 그 위치에 EOL Comment로 이유 설명) 가장 효과적이다.

## 흔한 실수
- Plate Comment와 EOL Comment를 구분 없이 아무 데나 길게 써서 나중에 요약과 세부 메모를 구분 못 하게 되는 것.
- IDA의 반복 주석(`;`)과 일반 주석(`:`)을 헷갈려 의도치 않게 여러 곳에 같은 텍스트가 나타나 당황하는 것.
- 도구를 바꿀 때(IDA→Ghidra) 단축키가 그대로일 거라 착각하는 것.

## 막혔을 때 다음 체크
- 주석 대신 위치 표시만 하고 싶으면 → REV-0747 Ghidra Bookmarks로 분석 진행상황 표시하기
- 이름 자체를 바꾸는 것과 주석을 헷갈린다면 → REV-0161 Ghidra Rename과 Data Type 수정, REV-0147 IDA 함수 변수 이름 N으로 바꾸기

## 미니 예제
```text
Ghidra:
  함수 check_password 시작 줄 우클릭 -> Comments -> Set Plate Comment
  입력: "사용자 입력을 s_correct_password와 strcmp로 비교, 0이면 통과"
  strcmp 호출 줄에서 ; 입력 -> "여기서 실제 비교 발생"

IDA:
  함수 시작에서 함수 주석 추가: "패스워드 검증 함수"
  strcmp 호출 줄에서 : 입력 -> "비교 결과가 성공 여부"
```

## 관련 글
- REV-0747 — Ghidra Bookmarks로 분석 진행상황 표시하기
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0147 — IDA 함수 변수 이름 N으로 바꾸기
- REV-0278 — Ghidra 핵심 단축키 치트시트

## 출처/검증
Ghidra 공식 Help 문서(Comments) 및 Hex-Rays IDA 공식 문서(Comments) 기준. 실제 실행 화면을 캡처해 재검증하지는 않았으며, 공식 문서 기준 키바인딩으로 작성했다. 로컬 환경에서 키바인딩이 커스터마이즈되어 있다면 다를 수 있다(2026-09-09).
