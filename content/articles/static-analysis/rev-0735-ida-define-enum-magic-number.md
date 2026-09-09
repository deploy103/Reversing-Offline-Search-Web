---
id: REV-0735
title: "IDA에서 Enum을 정의해서 매직넘버를 이름으로 바꾸기"
slug: "rev-0735-ida-define-enum-magic-number"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["IDA Enumerations", "Shift+F10", "Add enum", "매직넘버", "symbolic constant", "enum 적용", "M 키 오퍼랜드 변환"]
aliases: ["IDA enum 만들기", "매직넘버 이름 붙이기", "IDA 상수 이름 지정", "operand to symbolic constant"]
symptom_keywords: ["0x1, 0x2, 0x3 같은 숫자가 switch 안에서 반복됨", "매직넘버가 뭘 뜻하는지 모르겠음", "상태값 숫자를 이름으로 바꾸고 싶음", "enum이 뭔지 모르겠는데 IDA에서 어떻게 쓰는지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
IDA의 **Enumerations** 서브뷰(`Shift+F10`)에서 상태값·플래그·에러 코드 같은 매직넘버 집합을 이름 있는 상수 목록(enum)으로 정의해두고, 디스어셈블리나 Pseudocode의 즉시값(immediate) 위에서 `M` 키로 그 enum을 적용하면 `if ( v3 == 2 )` 같은 의미 불명의 숫자 비교가 `if ( v3 == STATE_RUNNING )`처럼 바로 읽히게 바뀐다.

## 언제 검색해야 하나
- `switch` 문이나 연속된 `if`/`else if`에서 `0`, `1`, `2`, `3` 같은 작은 정수가 반복적으로 비교되는데 그 숫자들이 각각 무엇을 뜻하는지 매번 헷갈릴 때
- 플래그 비트(`0x1`, `0x2`, `0x4`, `0x8` 같은 2의 거듭제곱 값들의 OR 조합)로 상태를 표현하는 코드를 보고 있는데 어떤 조합이 어떤 의미인지 정리하고 싶을 때
- 에러 코드나 API 상수(`GetLastError` 반환값 등)가 숫자 그대로 보여서, 알려진 상수 이름으로 바꾸고 싶을 때
- REV-0165(상수 검색)로 어떤 상수의 정체는 알아냈는데, 그 값을 코드 전체에서 이름으로 통일해서 보고 싶을 때

## 핵심 개념

### Enum이란 무엇인가 (IDA 관점)
IDA에서 enum은 C/C++의 `enum`뿐 아니라 매크로 상수(`#define`)까지 포괄하는, "이름 붙은 숫자 상수들의 묶음"이다. 예를 들어 `STATE_IDLE = 0`, `STATE_RUNNING = 1`, `STATE_STOPPED = 2`처럼 관련 있는 숫자 집합을 하나의 enum 타입으로 묶어두면, 디스어셈블리나 Pseudocode의 어떤 자리에 있는 숫자 `2`든 그 enum을 적용해 `STATE_STOPPED`로 표시할 수 있다. 이는 단순 주석과 달리 **같은 값이 나오는 모든 위치에 일괄 적용 가능**하고, 값이 비트 플래그(bitmask) 형태면 IDA가 `FLAG_A | FLAG_B`처럼 OR 조합으로도 표현해준다는 장점이 있다.

### Enum 만들기
`View → Open subviews → Enumerations`(단축키 `Shift+F10`)를 열고 `Ins`(또는 우클릭 → **Add enum...**)를 누르면 이름, 폭(1/2/4/8바이트), 진법(10진수/16진수 등 기본 표시 방식)을 지정하는 대화상자가 뜬다. enum을 만든 뒤 그 안에서 다시 `Ins`(또는 우클릭 → **Add enum member...**, 단축키 `N`으로 이름 지정)로 각 상수 멤버의 이름과 값을 하나씩 추가한다.

### 비트 플래그로 만들기
값들이 `0x1`, `0x2`, `0x4`처럼 서로 겹치지 않는 비트를 나타낸다면, enum 생성 대화상자에서 **Bitmask(비트마스크)** 옵션을 켠다. 이렇게 만들면 나중에 `0x5`(=`0x1 | 0x4`) 같은 조합 값을 만났을 때도 IDA가 자동으로 `FLAG_A | FLAG_C`처럼 OR 표현으로 풀어서 보여줄 수 있다. 다만 같은 값에 여러 상수가 겹치는 경우 모든 조합을 표현하지 못할 수 있다는 한계도 있다.

### 코드에 적용하기 — M 키
enum을 만드는 것만으로는 아무 코드도 바뀌지 않는다. 실제로 적용하려면, 디스어셈블리(또는 Pseudocode)에서 바꾸고 싶은 즉시값 오퍼랜드 위에 커서를 놓고 `M`을 누른다. 그러면 현재 데이터베이스에 정의된 enum 목록이 뜨고, 값이 일치하는 enum 멤버를 골라 적용하면 그 자리의 숫자가 이름으로 바뀐다. 커서가 명령어의 첫 번째 오퍼랜드(콤마 앞)에 있으면 첫 오퍼랜드가, 그렇지 않으면 나머지 오퍼랜드가 대상이 된다.

### 여러 곳에 한꺼번에 적용하기 (en masse 변환)
디스어셈블리에서 특정 범위를 선택(앵커 설정 후 커서 이동으로 범위 지정)한 상태로 `M`을 누르면, 그 범위 안의 모든 명령어에서 지정한 값 범위에 해당하는 즉시값 오퍼랜드를 한꺼번에 같은 enum 상수로 변환하는 "일괄 변환" 대화상자가 뜬다. 이 기능을 쓰면 같은 상태값 비교가 함수 전체에 흩어져 있어도 한 번에 정리할 수 있다.

## 화면/코드에서 보이는 징후
- `if ( v3 == 1 )`, `if ( v3 == 2 )`, `if ( v3 == 3 )`처럼 같은 변수와 작은 정수의 비교가 반복된다.
- `switch ( v2 ) { case 0: ... case 1: ... case 2: ... }`처럼 정수 리터럴만으로 분기되는 switch 문이 보인다.
- 플래그 검사 코드에서 `v1 & 4`, `v1 | 8`처럼 2의 거듭제곱 상수와의 비트 연산이 반복된다.
- 문자열/상수 검색(REV-0165)으로 어떤 숫자가 특정 API의 에러 코드나 상태값이라는 걸 알아냈는데, 코드 여러 곳에 그 숫자가 흩어져 있다.

## 가장 먼저 할 것
매직넘버가 나타내는 "값의 집합"이 무엇인지부터 정리한다(상태 머신의 상태들인지, 플래그 조합인지, 에러 코드인지). 이 집합 전체를 먼저 목록으로 만든 다음 enum을 설계하는 것이, 값을 하나씩 보면서 즉흥적으로 이름 붙이는 것보다 훨씬 일관성 있다.

## 단계별 절차
1. `Shift+F10`으로 Enumerations 창을 연다.
2. `Ins`(또는 우클릭 → **Add enum...**)로 새 enum 이름(예: `GameState`)을 만들고, 폭과 표시 진법(보통 10진수 상태값은 10진수, 플래그는 16진수)을 지정한다. 비트 플래그라면 **Bitmask** 옵션을 켠다.
3. 만든 enum 안에서 `Ins`(또는 `N`으로 이름 지정)를 반복해 각 상수 멤버(`STATE_IDLE = 0`, `STATE_RUNNING = 1`, ...)를 추가한다.
4. 코드로 돌아가 바꾸고 싶은 즉시값 위에 커서를 놓고 `M`을 누른다.
5. enum 목록에서 값이 일치하는 항목을 선택해 적용한다.
6. 같은 값이 여러 곳에 흩어져 있다면, 범위를 선택한 뒤 `M`을 눌러 일괄 변환 대화상자에서 값 범위를 지정해 한 번에 처리한다.
7. Pseudocode(F5)를 다시 열어 비교문/switch가 이름 있는 상수로 바뀌었는지 확인한다.

## 명령어/단축키
- `Shift+F10`: Enumerations 서브뷰 열기
- Enumerations 창에서 `Ins`: 새 enum 추가(목록에서) 또는 새 멤버 추가(enum 안에서)
- Enumerations 창에서 `N`: 선택한 enum 또는 멤버 이름 바꾸기
- 디스어셈블리/Pseudocode에서 즉시값 위 `M`: 그 값을 enum 심볼릭 상수로 변환("Convert operand to symbolic constant")
- 범위 선택 후 `M`: 선택 범위 안의 즉시값들을 조건에 맞춰 일괄 변환

## 출력 해석
- `M`을 눌렀는데 목록에 원하는 enum이 안 보이면, 그 값과 정확히 일치하는 멤버가 아직 정의되어 있지 않은 것이다 — Enumerations 창으로 돌아가 멤버를 추가한다.
- 비트마스크 enum을 적용했는데 일부 값이 여전히 숫자로 남아 있다면, 그 값이 정의된 플래그들의 조합만으로 완전히 표현되지 않는 값(정의되지 않은 비트가 섞여 있음)이라는 뜻이다 — 원본 값과 정의한 플래그 목록을 다시 대조한다.
- 일괄 변환 대화상자에서 범위를 너무 넓게 잡으면 관계없는 상수(스택 오프셋 등)까지 잘못 바뀔 수 있으므로, 변환 후 반드시 Pseudocode를 다시 확인해야 한다.

## 흔한 실수
- enum 폭(1/2/4/8바이트)을 실제 변수 크기와 다르게 지정해서 비교/대입 문맥에서 값이 어색하게 표시되는 것.
- 플래그 성격의 값인데 Bitmask 옵션을 켜지 않아서 조합된 값이 항상 알 수 없는 숫자로만 보이는 것.
- enum만 만들어두고 `M`으로 실제 코드에 적용하는 단계를 빼먹어서 "만들었는데 왜 안 바뀌지"라고 헷갈리는 것.
- 서로 다른 의미의 상수 집합(예: 게임 상태값과 네트워크 에러 코드)을 하나의 enum에 뒤섞어 넣어서 나중에 다시 봤을 때 혼란스러운 것 — 의미 단위별로 enum을 분리해서 만드는 것이 좋다.

## 막혔을 때 다음 체크
- 이 숫자가 애초에 무슨 알고리즘/표준 상수인지부터 모른다면 → REV-0165 상수 검색으로 알고리즘 찾기
- enum이 아니라 구조체 필드를 정리해야 하는 상황이라면 → REV-0734 IDA에서 구조체를 직접 정의해서 디컴파일에 적용하기
- enum 값을 텍스트로 더 빠르게 대량 등록하고 싶다면 → REV-0737 IDA Local Types 창 활용하기(C 헤더의 `enum` 선언 일괄 가져오기)
- enum 관련 빠른 참조표가 필요하다면 → REV-0722 IDA Enum 정의 빠른 참조

## 미니 예제
다음과 같은 Pseudocode가 있다고 하자.

```c
int __cdecl update_state(int a1)
{
  if ( a1 == 0 )
    return 10;
  if ( a1 == 1 )
    return 20;
  if ( a1 == 2 )
    return 30;
  return -1;
}
```

`Shift+F10`으로 Enumerations 창을 열고 `Ins`로 `GameState`라는 enum을 만든 뒤, 그 안에서 `STATE_IDLE = 0`, `STATE_RUNNING = 1`, `STATE_STOPPED = 2`를 추가한다. 각 비교문의 `0`, `1`, `2` 위에 커서를 놓고 `M`을 눌러 각각 해당 멤버로 바꾸면 다음처럼 표시된다.

```c
int __cdecl update_state(int a1)
{
  if ( a1 == STATE_IDLE )
    return 10;
  if ( a1 == STATE_RUNNING )
    return 20;
  if ( a1 == STATE_STOPPED )
    return 30;
  return -1;
}
```

숫자만 보고 매번 "이게 무슨 상태였지"를 다시 떠올릴 필요 없이, 이름만으로 바로 의미가 파악된다.

## 관련 글
- REV-0165 — 상수 검색으로 알고리즘 찾기
- REV-0734 — IDA에서 구조체를 직접 정의해서 디컴파일에 적용하기
- REV-0737 — IDA Local Types 창 활용하기
- REV-0148 — IDA Y로 타입 지정하기
- REV-0722 — IDA Enum 정의 빠른 참조

## 출처/검증
- Enumerations 서브뷰(`Shift+F10`)와 `Add enum...`/`Add enum member...`(단축키 `Ins`, 이름 변경 `N`) 조작: Hex-Rays 공식 사용자 가이드(Subviews, Enums) 및 공식 블로그(Igor's tip of the week, Enums) 기준.
- 즉시값 오퍼랜드를 심볼릭 상수(enum)로 변환하는 명령("Convert operand to symbolic constant", 단축키 `M`)과 비트마스크 enum의 OR 조합 표현, 범위 선택 시 일괄("en masse") 변환 동작: Hex-Rays 공식 문서(Convert operand to symbolic constant) 기준.
- 이 문서는 2026-09-09 기준 공개된 Hex-Rays 공식 문서/블로그 검색 결과를 바탕으로 작성했으며, 정확한 메뉴 문구는 IDA 버전에 따라 다를 수 있으므로 실제 설치 환경에서 재확인할 것을 권장한다.
