---
id: REV-0783
title: "Ghidra에서 함수 경계가 잘못 잡혔을 때"
slug: "rev-0783-ghidra-wrong-function-boundary"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra 함수 경계 오류", "Ghidra Edit Function", "Ghidra function chunk", "Ghidra 함수 크기 이상함", "Ghidra Non-Returning Function"]
aliases: ["Ghidra 함수가 이상하게 잘림", "Ghidra 함수 두 개가 합쳐짐", "Ghidra 함수 청크"]
symptom_keywords: ["Ghidra에서 함수가 중간에 끊김", "Ghidra Function 크기가 비정상적으로 큼", "Ghidra 함수 안에 관계없는 로직이 섞임", "Ghidra FUN 함수가 너무 작음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra Decompile 결과에서 로직이 뜬금없이 끊기거나 서로 다른 두 로직이 한 함수 안에 섞여 보인다면 대부분 **함수 경계(시작/끝)를 자동 분석이 잘못 추정한 것**이며, `Edit Function`으로 끝 주소를 직접 조정하거나 잘못된 함수를 삭제 후 재생성하면 대부분 해결되지만, 먼저 "정상적인 함수 청크(function chunk)"와 혼동하지 않도록 구분하는 것이 중요하다.

## 언제 검색해야 하나
- Decompile 결과가 논리적으로 앞뒤가 안 맞고, 마치 서로 다른 함수 두 개가 하나로 합쳐진 것처럼 보일 때
- Symbol Tree Functions 목록에서 어떤 함수의 크기(주소 범위)가 몇 바이트 수준으로 비정상적으로 작거나 반대로 수천 줄로 비정상적으로 클 때
- Listing에서 함수가 `RET` 없이 갑자기 다음 함수 시작과 맞물려 끝나 있을 때
- 함수 이름 뒤에 낯선 표기가 붙어 있어서 이게 오류인지 정상 구조인지 헷갈릴 때

## 핵심 개념
Ghidra의 Auto Analysis는 코드 패턴(표준 프롤로그, 호출 대상, 흐름 분석)으로 함수 시작/끝을 추정하며, 이 추정이 항상 정확하지는 않다. 대표적인 원인은 다음과 같다.

1. **Non-Returning Function 오판**: `exit`, `abort`, `_assert_fail`처럼 절대 반환하지 않는 함수를 Ghidra가 "반환할 수도 있다"고 잘못 판단하면, 그 CALL 뒤에 나오는(사실은 다른 함수의) 코드까지 현재 함수 안으로 억지로 편입시켜 함수가 비정상적으로 커진다. 반대의 오판이면 함수가 그 CALL 직후에서 뚝 잘린다.
2. **함수 청크(function chunk)**: 컴파일러 최적화로 하나의 논리적 함수가 메모리상 여러 조각(메인 청크 + 꼬리 청크)으로 나뉘어 배치된 경우다. 이는 버그가 아니라 정상 구조이며, Ghidra의 Function Call Graph/Listing에서 별도 표기로 구분된다.
3. **꼬리 호출(tail call)**: 함수 끝에서 다른 함수로 `call` 없이 `jmp`로 넘어가는 패턴을 Ghidra가 별도 함수 진입으로 인식하지 못하면 경계가 어긋난다.
4. **함수 사이 정렬 패딩/점프 테이블 데이터**: `nop`/`int3` 정렬 바이트나 switch 점프 테이블이 코드로 잘못 인식되어 다음 함수 시작 위치가 밀리는 경우.
5. **수동 편집 후 미반영**: 사용자가 코드 일부를 Undefine했다가 다시 정의하지 않아 함수 중간이 끊긴 채로 남는 경우.

## 화면/코드에서 보이는 징후
- Decompile 결과 앞부분과 뒷부분의 로직이 전혀 관계없어 보인다(사실은 서로 다른 두 함수가 합쳐짐).
- Symbol Tree의 Functions 목록에서 함수 크기가 극단적으로 작거나(2~3바이트) 극단적으로 크다.
- Listing에서 함수가 자연스러운 종료(RET/JMP) 없이 다음 함수의 시작과 그대로 이어져 있다.
- 함수를 두 번 클릭했는데 같은 이름의 다른 조각(청크)으로 보이는 항목이 여러 개 있다.

## 가장 먼저 할 것
문제로 의심되는 함수의 끝부분으로 이동해서, 코드가 실제로 실행 불가능한 쓰레기 바이트 위에서 끝나는지(진짜 오류), 아니면 정상적으로 이어지는 다른 코드 블록(정상 청크)으로 연결되는지부터 눈으로 확인한다.

## 단계별 절차

**1) 함수 끝부분 직접 확인**

Listing에서 문제 함수의 마지막 명령어로 이동한다. `RET`, `JMP` 등 자연스러운 종료 없이 바로 다음 함수의 프롤로그(`push rbp` 등)로 이어진다면 실제 경계 오류일 가능성이 높다.

**2) 간단 재생성 먼저 시도**

함수 시작 주소에서 우클릭 → **Delete Function**으로 기존 정의를 지운 뒤, 다시 그 시작 주소에서 우클릭 → **Create Function**으로 새로 만든다. 대부분의 단순 경계 오류는 이 재생성만으로 자동 분석이 새 정보를 반영해 고쳐진다.

**3) Non-Returning 표시 확인**

함수가 특정 CALL 직후에서 이상하게 잘려 있다면, 그 CALL이 부르는 함수 위에서 우클릭 → **Function → Non-Returning Function** 관련 항목을 확인하고 잘못 표시되어 있으면 해제한 뒤 원래 함수를 다시 생성한다.

**4) 함수 끝(End) 직접 조정**

재생성만으로 안 되면 함수 위에서 우클릭 → **Edit Function**을 열어 대화상자에서 함수의 끝 범위(Body)를 직접 지정한다. 새 범위가 다른 함수/청크와 겹치면 적용되지 않으므로, 먼저 겹치는 대상 함수를 축소하거나 삭제해야 한다.

**5) 두 함수가 하나로 합쳐졌다면 분리**

두 번째 함수가 실제로 시작하는 주소(표준 프롤로그, 또는 다른 곳에서 그 주소로의 CALL XREF)를 먼저 찾는다. 그 주소 앞까지만 첫 함수로 남기고(Edit Function으로 범위 축소), 새 시작 주소에서 Create Function으로 두 번째 함수를 새로 만든다.

**6) 정상적인 함수 청크라면 그대로 두거나 명시적으로 조정**

코드가 정말로 최적화 때문에 두 곳에 나뉜 것이 맞다면(예외 처리 cold path 등), 이는 오류가 아니다. 필요하다면 해당 범위를 선택 후 **Add-Remove Function Tail** 관련 메뉴로 소속 청크를 조정할 수 있지만, 자동 분석이 이미 올바르게 구성한 경우가 대부분이므로 Decompile 결과가 실제로 이상할 때만 손댄다.

**7) 재분석 및 재확인**

경계를 고친 뒤 Decompile 창을 다시 확인한다. 여전히 비어 있거나 이상하면 REV-0782, REV-0781을 함께 점검한다.

## 명령어/단축키
```text
우클릭 → Delete Function     함수 정의 삭제(재생성 전 단계)
우클릭 → Create Function     커서 위치부터 함수 새로 생성
우클릭 → Edit Function        시작/끝 범위, 이름, 시그니처 직접 편집
D / C                         Disassemble / Clear Code Bytes (코드 재해석)
X                             Cross-references(경계 판단용 호출 지점 확인)
```

## 출력 해석
- Edit Function 대화상자에서 범위를 늘려도 반영되지 않으면, 그 범위가 다른 함수/청크와 겹친다는 뜻이다 — 겹치는 함수를 먼저 정리해야 한다.
- 재생성 후에도 함수 크기가 여전히 이상하다면, 애초에 선택한 시작 주소가 진짜 함수 시작이 아니었을 가능성이 크다 — 다른 프롤로그 패턴이나 XREF로 진짜 시작점을 다시 찾는다.
- Functions 목록에 이름은 같은데 위치만 다른 항목이 보이면 대부분 정상적인 함수 청크(꼬리 청크) 표시이므로 오류로 오인하지 않는다.

## 흔한 실수
- 정상적인 함수 청크를 오류로 착각해 억지로 하나로 합치려다 더 꼬아버리는 것.
- Delete Function만 하고 Create Function으로 다시 만들지 않아 그 구간이 그냥 정의되지 않은 상태로 남는 것.
- Edit Function에서 범위를 다른 함수와 겹치게 지정해 계속 실패하는데 원인을 모르고 반복 시도하는 것.
- Non-Returning 오판이 근본 원인인데 매번 Edit Function으로 끝만 늘렸다가 재분석 때마다 다시 잘리는 것을 반복하는 것.

## 막혔을 때 다음 체크
- 경계는 맞는 것 같은데 Decompile 결과 자체가 비어 있다면 → REV-0782.
- 문제 구간에 정의되지 않은(Undefined) 바이트가 섞여 있다면 → REV-0784와 함께 Undefine/재정의 절차 확인.
- IDA에서 동일한 개념(함수 청크, non-return 오판)을 다루는 문서가 필요하면 → REV-0154.
- 함수 목록/Symbol Tree 자체의 열 구성이 헷갈리면 → REV-0159.

## 미니 예제
Symbol Tree에서 `FUN_00401500`이 5바이트짜리로 표시되고 바로 뒤에 이름 없는 `FUN_00401505`가 이어져 있다고 하자. `FUN_00401500`의 마지막 명령어가 `call _exit`이고 RET 없이 그대로 끝나 있다.

1. `_exit` 호출 직후 주소로 이동해, 그 뒤 코드가 실제로 도달 가능한 로직인지 확인한다.
2. 도달 가능한 로직이라면(예: 에러 메시지 출력 후 정리 코드) `FUN_00401500`을 Edit Function으로 열어 끝 범위를 그 로직이 끝나는 지점까지 늘린다.
3. 반대로 완전히 별개의 함수라면 그대로 두고 `L`로 적절한 이름만 붙인다.
4. Decompile 창을 다시 확인해 두 로직이 하나의 일관된 함수로 읽히는지 검증한다.

## 관련 글
- REV-0782 — Ghidra에서 Decompile 결과가 비어있을 때
- REV-0784 — Ghidra에서 문자열이 인식되지 않을 때
- REV-0159 — Ghidra Function 목록과 Symbol Tree
- REV-0154 — IDA에서 함수 경계가 잘못 잡혔을 때

## 출처/검증
- Non-Returning Function 오판, 함수 청크(메인/꼬리), Edit Function의 범위 겹침 제약, Delete Function 후 Create Function으로 재생성하는 절차: Ghidra 공식 Help 문서(FunctionPlugin, Non-Returning Functions Analyzer 토픽) 기준.
- 라이브 환경에서 모든 케이스를 직접 재현 검증하지는 않았으며, 공식 문서와 IDA 등 다른 도구에서 통용되는 동일 개념(REV-0154)을 기준으로 서술했다. 실제 메뉴 문구는 버전에 따라 다를 수 있다.
