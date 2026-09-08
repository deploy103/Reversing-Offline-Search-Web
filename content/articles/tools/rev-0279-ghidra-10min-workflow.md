---
id: REV-0279
title: "Ghidra 10분 실전 워크플로"
slug: "rev-0279-ghidra-10min-workflow"
category: "tools"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra 실전 예제", "Ghidra 크랙미 풀이", "Ghidra 10분", "Ghidra speedrun", "Ghidra flag 찾기", "Ghidra 워크플로", "Ghidra Defined Strings"]
aliases: ["Ghidra 빠른 풀이", "Ghidra 실전 루틴", "Ghidra 10분 완성", "Ghidra 스피드런"]
symptom_keywords: ["Ghidra로 크랙미 빨리 푸는 법", "Ghidra 시간 없을 때 뭐부터", "Ghidra flag 검사 함수 못 찾음", "Ghidra 대회 중 빨리 풀어야 함"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
간단한 크랙미라면 Ghidra에서 **프로젝트 생성 및 Import → Auto Analysis 대기 → Defined Strings 창에서 힌트 문자열 찾기 → 참조(References) 추적으로 검사 함수 찾기 → Decompile 창에서 조건 읽기** 순서를 따르면 파일을 연 지 10분 안에 플래그 검사 로직에 도달할 수 있다.

## 언제 검색해야 하나
- 시간 제한이 있는 CTF에서 Ghidra로 빠르게 플래그 검사 로직을 찾고 싶을 때
- Ghidra 설치와 개별 창 사용법은 알지만 전체를 이어붙인 실전 흐름이 궁금할 때
- IDA의 10분 워크플로(REV-0276)와 Ghidra에서 뭐가 다른지 비교하고 싶을 때
- Ghidra Auto Analysis가 끝난 다음에 뭐부터 눌러야 할지 막막할 때

## 핵심 개념
이 문서는 Ghidra의 개별 기능(프로젝트 생성, Auto Analysis, Decompiler 창, xref 등은 REV-0156~REV-0161)을 이미 다룬 문서들이 있다는 전제 하에, **그 기능들을 실전에서 어떤 순서로 조합하는지**만 다룬다.

Ghidra는 IDA와 달리 파일을 열기 전에 **먼저 프로젝트(Project)를 만들어야** 하고, Import 이후 Auto Analysis를 명시적으로(또는 자동으로) 실행해야 한다는 점이 워크플로 상의 가장 큰 차이다. 일단 이 초기 단계만 지나면, 이후의 "힌트 문자열로 거꾸로 추적하기" 전략은 IDA와 근본적으로 동일하다.

## 화면/코드에서 보이는 징후
- Ghidra CodeBrowser 창의 `Window → Defined Strings`(또는 자동으로 뜨는 Defined Strings 창)에 `"Correct!"`, `"Access Denied"`, `"flag{"` 같은 문자열이 나열된다.
- 그 문자열을 더블클릭해 이동한 뒤 `X`(Cross-references)를 누르면 이 문자열을 쓰는 함수 목록이 뜬다.
- 해당 함수를 Symbol Tree나 Listing에서 클릭하면 오른쪽 Decompile 창에 `if (조건) { ... } else { ... }` 형태의 C 비슷한 코드가 자동으로 뜬다.

## 가장 먼저 할 것
Ghidra를 실행하고 새 프로젝트(비어 있는 폴더면 충분)를 만든 뒤, 분석할 바이너리를 `File → Import File`로 불러온다. Import 후 뜨는 "Analyze?" 대화상자에서 기본 옵션 그대로 **Yes/Analyze**를 눌러 Auto Analysis를 시작한다.

## 단계별 절차

**[0:00~1:30] 프로젝트 생성, Import, Auto Analysis 시작**

Ghidra 실행 → `File → New Project`(Non-Shared Project로 충분) → 프로젝트 이름/경로 지정 → `File → Import File`로 대상 바이너리 선택 → 포맷 인식 대화상자 기본값 확인 → OK. Import 후 CodeBrowser 창이 자동으로 뜨거나 더블클릭해서 연다. "Would you like to analyze it now?" 대화상자에서 기본 분석기 옵션 그대로 **Analyze** 버튼을 누른다. (프로젝트/Import 세부 사항은 REV-0156 참고.)

**[1:30~2:30] Auto Analysis 대기**

화면 하단 진행률 표시줄이 끝날 때까지 기다린다. 작은 바이너리는 수 초에서 수십 초면 끝난다. 진행 중에는 편집 작업(rename 등)을 하지 않는 것이 안전하다(REV-0157 참고).

**[2:30~3:30] Defined Strings로 힌트 찾기**

`Window → Defined Strings`를 열어(또는 이미 열려 있는 탭을 클릭) 목록에서 `"Correct"`, `"Wrong"`, `"Success"`, `"flag"`, `"password"` 같은 메시지를 찾는다. 목록 위에서 문자열 필터(검색창)에 "correct"나 "wrong"을 입력하면 더 빠르게 좁힐 수 있다.

**[3:30~4:30] xref로 사용처 추적**

찾은 문자열을 더블클릭해 Listing에서 그 위치로 이동한 뒤, `X`를 눌러 Cross-references 목록을 확인한다. 목록의 항목을 더블클릭하면 이 문자열을 실제로 참조하는 코드(대개 어떤 함수 안의 `printf`/`puts` 호출 직전)로 이동한다.

**[4:30~5:00] 함수 파악**

이동한 위치가 속한 함수 이름을 Listing 상단이나 Symbol Tree에서 확인한다. Ghidra는 함수 안 어디로 이동해도 오른쪽 Decompile 창이 그 함수 전체의 디컴파일 결과를 자동으로 보여주므로, 별도로 "F5를 누르는" 단계가 필요 없다.

**[5:00~6:30] Decompile 창에서 로직 읽기**

Decompile 창에서 다음을 확인한다.

- 입력을 받는 지점(`scanf`, `fgets`, `read` 등 호출)
- 검사 조건(`strcmp`, `memcmp`, 배열 순회 비교 등)
- 성공/실패 분기와 각각의 출력 메시지

**[6:30~8:00] 비교 대상 값 확인**

`strcmp(local_input, "S3cr3t_2026")`처럼 정답이 코드에 그대로 있으면 그 문자열이 답(또는 답의 일부)이다. 변수와 비교한다면 그 변수를 `X`로 추적해서 초기화 위치(전역 배열, 다른 함수의 리턴값 등)를 확인한다. 배열 순회 비교라면 비교 대상 배열을 더블클릭해 Listing에서 실제 바이트 값을 확인한다(필요하면 `T`로 데이터로 재해석해 보기 편하게 만든다).

**[8:00~9:00] 이름 정리(선택) 및 정답 조립**

시간이 있으면 `L`로 변수 이름을 정리해 가독성을 높인다. 확인한 비교값들을 조합해서 입력 후보(플래그)를 만든다. XOR/인코딩 등 추가 변환이 있으면 짧은 Python 스크립트로 역산한다.

**[9:00~10:00] 최종 확인**

실제 바이너리를 실행해 조립한 입력을 넣어보고 성공 메시지가 뜨는지 확인한다. 실행이 여의치 않으면 Decompile 결과의 조건식을 다시 한번 손으로 검산한다.

## 명령어/단축키
- `File → New Project` / `File → Import File` : 시작 진입점
- `Window → Defined Strings` : 힌트 문자열 찾기
- `X` : Cross-references 추적
- `L` : 변수/함수 이름 정리
- `Ctrl+L` : 타입 정리(필요시)
- `Alt+←` : 되돌아가기(추적하다 원래 위치로 복귀할 때)

## 출력 해석
- Defined Strings에 힌트가 없으면 → 문자열이 암호화되어 있거나 이 방식이 안 통하는 문제 유형이다. Imports 목록이나 함수 이름 패턴(REV-0164 계열 문서, static-analysis 카테고리)으로 접근을 바꾼다.
- Decompile 결과가 지나치게 뒤섞여 읽기 힘들면 → 컴파일러 최적화 가능성이 있다. Listing(디스어셈블리) 뷰를 같이 보면서 실제 분기 구조를 재확인한다.
- xref 목록이 텅 비어 있으면 → 그 문자열이 실제로 안 쓰이거나(디버그 잔재), 간접 참조(포인터 테이블)로만 연결된 경우다.

## 흔한 실수
- Import 직후 Auto Analysis 대화상자에서 실수로 "No"를 눌러 분석을 건너뛰고, 함수 목록이 텅 빈 채로 헤매는 경우 — Auto Analysis는 `Analysis → Auto Analyze 'filename'`에서 나중에라도 다시 실행할 수 있다.
- Defined Strings를 안 열어보고 Symbol Tree의 함수 목록을 위에서부터 다 읽으려다 시간을 낭비하는 경우.
- `X`(xref) 결과 중 첫 항목만 보고 잘못된 함수로 들어가는 경우 — 여러 후보가 있으면 호출 문맥을 보고 진짜 검사 함수를 골라야 한다.
- 비교 로직에 XOR/인코딩이 섞여 있는데 이를 무시하고 테이블 값 자체를 답이라고 제출하는 경우.

## 막혔을 때 다음 체크
- 프로젝트 생성/Import 자체가 헷갈리면 → REV-0156(Ghidra Project Import)을 참고한다.
- Auto Analysis 옵션이나 진행 상태가 궁금하면 → REV-0157(Ghidra Auto Analysis)을 참고한다.
- Decompile 창을 더 깊이 알고 싶으면 → REV-0158(Ghidra Decompiler 창)을 참고한다.
- 함수 목록 탐색이 필요하면 → REV-0159(Ghidra Function List)를 참고한다.
- xref를 더 깊이 활용하고 싶으면 → REV-0160(Ghidra xref)을 참고한다.
- 값 검산에 자신이 없으면 → x64dbg/GDB로 실제 실행하며 값을 찍어보는 동적 분석으로 전환하는 것이 더 빠를 수 있다.

## 미니 예제
가상의 Linux ELF 크랙미 `crackme`를 Ghidra로 여는 순간부터 답을 찾기까지의 타임라인 예시:

```text
0:00  New Project → Import File crackme → Analyze(Yes)
1:20  Auto Analysis 완료 대기
2:10  Window → Defined Strings → "Access Granted" 발견
3:00  더블클릭 후 X → check_serial 함수에서 1건 참조
4:20  check_serial 클릭 → Decompile 창 자동 갱신:
      if (memcmp(input, key_table, 16) == 0)
        puts("Access Granted");
      else
        puts("Access Denied");
6:00  key_table 더블클릭 → Listing에서 16바이트 실제 값 확인
8:30  16바이트를 문자열로 변환해 플래그 후보 조립
9:40  실제 crackme 실행 → 조립한 값 입력 → "Access Granted" 확인
```

## 관련 글
- REV-0156 — Ghidra 프로젝트 생성과 바이너리 Import
- REV-0157 — Ghidra Auto Analysis 옵션
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0277 — Ghidra 설치와 오프라인 준비
- REV-0278 — Ghidra 핵심 단축키 치트시트

## 출처/검증
- 프로젝트 생성 → Import → Auto Analysis → Defined Strings → xref → Decompile로 이어지는 흐름은 Ghidra 공식 문서(GhidraDocs)에 설명된 각 기능의 표준 동작을 조합한 것이며, 다수의 공개 Ghidra 입문 튜토리얼/CTF 라이트업에서 공통적으로 쓰이는 실전 순서와 일치한다(2026-09-08 검증).
- 실제 걸리는 시간은 바이너리 크기와 최적화 수준, JDK/Auto Analysis 속도(PC 사양)에 따라 달라질 수 있으므로 "10분"은 단순 비교형 크랙미를 기준으로 한 목표 시간이다.
