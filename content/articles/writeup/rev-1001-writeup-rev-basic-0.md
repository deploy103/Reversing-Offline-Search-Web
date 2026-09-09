---
id: REV-1001
title: "[Write-up] rev-basic-0"
slug: "rev-1001-writeup-rev-basic-0"
category: "writeup"
difficulty: "basic"
platform: [windows]
architecture: [x64]
format: [PE]
tools: [IDA, "Detect It Easy"]
keywords: ["dreamhack rev-basic-0", "드림핵 rev-basic-0", "rev-basic-0 풀이", "rev-basic-0 write-up", "rev-basic-0 strcmp"]
aliases: ["드림핵 rev basic 0", "rev-basic-0 못풀겠음", "dreamhack rev basic 0 flag"]
symptom_keywords: ["드림핵 rev-basic-0 어떻게 풀어야 할지 모르겠음", "Correct Wrong만 나오고 로직을 못찾음", "sub_140001000 안에서 뭘 봐야 할지 모르겠음"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
rev-basic-0은 입력 문자열을 정답 문자열과 `strcmp`로 그대로 직접 비교하는 가장 단순한 유형이며, IDA로 검증 함수 하나만 디컴파일하면 비교 대상 문자열이 코드에 그대로 노출된다.

## 언제 검색해야 하나
- 드림핵 워게임 rev-basic 시리즈 중 가장 처음(rev-basic-0) 문제를 열었는데 어디부터 봐야 할지 감이 안 잡힐 때
- 프로그램을 실행해서 아무 문자열이나 넣어봤는데 계속 `Wrong`만 나오고, `Correct`가 나오는 조건을 코드에서 못 찾을 때
- IDA에서 `sub_140001000` 같은 이름 없는 함수 안에 들어갔는데 배열도 없고 루프도 없어서 오히려 더 헷갈릴 때

## 핵심 개념
이 문제는 실행하면 `Input : `을 출력하고 사용자로부터 문자열을 하나 입력받은 뒤, 내부 검증 함수의 반환값에 따라 `Correct` 또는 `Wrong`을 출력하는 64비트 Windows PE 실행 파일이다. 목표는 `Correct`가 뜨는 정답 문자열을 알아내 드림핵에 `DH{정답}` 형식으로 제출하는 것이다.

검증 로직의 종류를 미리 분류해두면 분석이 빨라진다. 이 문제의 검증 함수는 XOR 연산이나 배열 인덱스 순회 같은 복잡한 변환 없이, 입력 버퍼 전체를 정답 문자열과 `strcmp`(문자열이 완전히 같은지 비교하는 C 표준 함수)로 한 번에 비교하고 그 결과가 0(같음)인지만 검사한다. 즉 "암호화된 값을 복호화"하는 문제가 아니라 "정답이 코드/데이터 어딘가에 평문으로 박혀 있는" 문제다. 이런 유형은 REV-0196에서 다루는 `strcmp` 기반 검증 패턴의 가장 전형적인 예시다.

## 화면/코드에서 보이는 징후
- PowerShell(또는 cmd)에서 실행하면 `Input : `이 출력되고 커서가 입력을 기다린다.
- 아무 문자열이나 입력하면 `Wrong`이 출력된다.
- IDA에서 `main`을 F5로 디컴파일하면 입력을 받는 함수 호출, 그리고 결과 문자열을 비교해 분기하는 `if` 문이 보인다.
- `main`이 호출하는 이름 없는 함수(`sub_140001000` 형태의 주소 기반 이름) 안에 `strcmp` 호출과 함께 문자열 리터럴이 인자로 들어가 있다.

## 가장 먼저 할 것
Detect It Easy(DIE)로 파일을 열어 64비트 PE, 컴파일러(보통 MSVC), 패킹 여부를 먼저 확인한다. 패킹이 없는 일반 PE라면 곧바로 IDA로 넘어가도 된다. 그다음 실제로 한 번 실행해서 입출력 문구(`Input : `, `Correct`, `Wrong`)를 정확히 기억해 둔다. 이 문구들은 뒤에서 IDA Strings 창(REV-0144, Shift+F12)으로 검증 함수 위치를 찾는 이정표가 된다.

## 단계별 절차
1. DIE로 아키텍처/컴파일러/패킹 여부 확인.
2. 파일을 실행해 임의 문자열 입력 시 `Wrong`이 나오는지 확인.
3. IDA로 파일을 열고 자동 분석이 끝나면 `main` 함수로 이동(Imports나 Strings 창에서 `Input :` 문자열을 더블클릭해 참조 위치로 진입).
4. `main`을 F5로 디컴파일. 입력 함수 호출, 검증 함수 호출, 그리고 반환값에 따른 `Correct`/`Wrong` 분기 구조를 확인한다.
5. 검증 함수(예: `sub_140001000`) 위에서 더블클릭해 진입, F5로 디컴파일한다.
6. 디컴파일된 코드 안에서 `strcmp(입력버퍼, "문자열리터럴")` 형태의 호출을 찾는다. 이 문자열 리터럴이 곧 정답이다.
7. 찾은 문자열을 그대로 실행 파일에 입력해 `Correct`가 나오는지 검증한다.

## 명령어/단축키
- IDA: 파일 열기 후 자동 분석 대기, `main` 진입 → `F5`(디컴파일), 함수 이름 더블클릭(하위 함수 진입), `Shift+F12`(Strings 창, REV-0144).
- DIE: 실행 파일을 창에 드래그 앤 드롭만 하면 헤더/컴파일러/엔트로피 정보가 표시된다.
- PowerShell: `.\rev-basic-0.exe` 실행 후 임의 문자열 입력.

## 출력 해석
디컴파일된 검증 함수에서 `return strcmp(a1, "Compar3_the_str1ng") == 0;` 같은 코드가 보이면, 이는 "입력값(a1)과 문자열 리터럴이 완전히 같을 때만 1(true)을 반환한다"는 뜻이다. `strcmp`는 두 문자열이 같으면 0을 반환하므로 `== 0` 비교가 붙어 있는 것이 정상이며, `!= 0`으로 되어 있다면 반대로 "다를 때 true"라는 의미이니 분기 방향을 착각하지 않도록 주의한다.

## 흔한 실수
- `strcmp`의 반환값 의미를 헷갈려서(0이 아니라 1이 "같음"이라고 착각) 반대로 해석하는 것.
- 문자열 리터럴을 IDA 디컴파일 화면에서 못 보고 넘어가는 것 — 디컴파일러가 문자열을 `a2` 같은 변수로만 표시하면 변수를 더블클릭해 실제 참조를 따라가야 한다.
- 정답 문자열을 찾았는데 대소문자나 특수문자를 하나 빼먹고 입력해서 여전히 `Wrong`이 나오는 것.
- `Input :` 문자열이 여러 곳에서 참조될 수 있다는 것을 모르고 첫 번째로 찾은 참조만 보고 잘못된 함수를 검증 함수로 오인하는 것.

## 막혔을 때 다음 체크
- `strcmp` 비교가 아니라 배열을 순회하며 한 바이트씩 상수와 비교하는 형태라면 다음 문제인 REV-1002(rev-basic-1)의 패턴에 더 가깝다.
- 문자열이 코드에 안 보이고 배열 인덱스 접근만 보인다면 REV-1003(rev-basic-2)의 배열 stride 문제를 먼저 참고한다.
- `strcmp` 자체의 일반적인 검증 패턴이 더 궁금하면 REV-0196을 참고한다.

## 미니 예제
검증 함수를 단순화하면 다음과 같은 형태다.

```c
int check(char *a1) {
    return strcmp(a1, "Compar3_the_str1ng") == 0;
}
```

이 경우 정답은 문자열 리터럴 그 자체이므로, `main` 쪽에서 반환값이 1일 때 `Correct`를 출력하는 흐름만 확인하면 추가 연산 없이 곧바로 답이 나온다.

## 관련 글
- REV-0196 — strcmp 기반 Flag 검증 패턴
- REV-0146 — IDA F5 디컴파일과 Pseudocode 읽기
- REV-0144 — IDA Strings 창과 Shift+F12
- REV-0126 — Detect It Easy로 컴파일러 패커 확인
- REV-0001 — 리버싱 문제 파일을 받았을 때 30초 트리아지
- REV-1002 — [Write-up] rev-basic-1
- REV-1003 — [Write-up] rev-basic-2
- REV-1004 — [Write-up] rev-basic-3

## 출처/검증
- 드림핵 워게임 rev-basic-0 챌린지 페이지(dreamhack.io/wargame/challenges, reversing 태그, Bronze 4 티어, 풀이자 8126명, 2026-09-09 조회 기준).
- 참고 블로그: `velog.io/@helenason/dreamhack-wargame-rev-basic-0` — IDA로 `main`과 `sub_140001000`을 디컴파일해 `strcmp(a1, "Compar3_the_str1ng") == 0` 형태의 직접 비교 로직을 확인한 것으로 조사됨.
- 위 원문 문장을 그대로 인용하지 않고, 검증 로직의 종류(strcmp 직접 비교)와 분석 절차만 재구성해 한국어로 새로 서술했다.
