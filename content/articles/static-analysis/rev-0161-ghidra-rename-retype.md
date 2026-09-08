---
id: REV-0161
title: "Ghidra Rename과 Data Type 수정"
slug: "rev-0161-ghidra-rename-retype"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Rename", "Ghidra Retype Variable", "Ghidra L 단축키", "Ghidra Data Type Manager", "Ghidra Edit Function Signature", "Ghidra Create Structure"]
aliases: ["Ghidra 이름 바꾸기", "Ghidra 변수 이름 변경", "Ghidra 타입 지정", "Ghidra 구조체 만들기"]
symptom_keywords: ["Ghidra에서 변수 이름 바꾸는 법", "Ghidra local_28을 다른 이름으로", "Ghidra 함수 인자 타입 바꾸는 법", "Ghidra 구조체 정의하는 법"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Ghidra에서 함수/변수/데이터의 기본 이름(`FUN_`, `local_`, `param_`, `DAT_`)을 의미 있는 이름으로 바꾸는 것은 단축키 **`L`(Rename)**, 자료형을 바로잡는 것은 **`Ctrl+L`(Retype Variable)**로 하며, 이 두 작업을 꾸준히 반복하는 것이 Ghidra 디컴파일 결과를 실제 소스코드처럼 읽히게 만드는 가장 중요한 습관이다.

## 언제 검색해야 하나
- Decompile 창의 `local_28`, `param_1`, `FUN_00401230` 같은 이름을 의미 있는 이름으로 바꾸고 싶을 때
- 변수 타입이 `undefined4`로 나와서 실제로 `int`인지 포인터인지 구조체인지 확인/지정하고 싶을 때
- 함수 시그니처(인자 개수, 리턴 타입) 자체가 잘못 추정된 것 같아서 고치고 싶을 때
- 반복되는 필드 구조(예: 여러 개의 4바이트 필드가 이어진 구조체)를 발견해서 struct로 묶고 싶을 때

## 핵심 개념
Ghidra 디컴파일러가 붙이는 기본 이름은 어디까지나 "아직 분석자가 확인하지 않았다"는 placeholder다. 이름과 타입을 바로잡는 작업은 단순히 보기 좋게 꾸미는 게 아니라, **Ghidra가 이후 표현식을 어떻게 렌더링할지에 실제로 영향을 준다.** 예를 들어 `undefined4`로 되어 있던 변수를 포인터 타입으로 Retype하면, 그 변수를 사용하는 코드가 `*(int *)(param_1 + 4)` 형태의 포인터 연산으로 자동으로 다시 표현되어 훨씬 읽기 쉬워진다.

- **Rename(이름 바꾸기, 단축키 `L`)**: 함수, 지역 변수, 파라미터, 전역 데이터(`DAT_`), 라벨 등 거의 모든 심볼에 적용된다. 대상 위에 커서를 놓거나 클릭한 뒤 `L`을 누르면 이름 편집 대화상자(또는 인라인 편집)가 뜬다.
- **Retype Variable(타입 바꾸기, 단축키 `Ctrl+L`)**: 지역 변수나 파라미터의 자료형을 바꾼다. `int`, `char *`, `DWORD`, 사용자 정의 구조체 포인터 등으로 지정할 수 있다.
- **Edit Function Signature**: 함수 이름 자체가 아니라 함수 전체의 시그니처(리턴 타입, 파라미터 개수/순서/타입, 호출 규약)를 편집한다. Decompile 창에서 함수 이름 줄 우클릭 → **Edit Function Signature**로 연다. 파라미터 개수가 실제와 다르게 추정된 경우 여기서 직접 추가/삭제할 수 있다.
- **Data Type Manager**: CodeBrowser 왼쪽(Symbol Tree 옆 탭)에 있는 패널로, 기본 제공 타입(`int`, `DWORD`, `char *` 등)과 이 프로그램에서 사용자가 만든 구조체/열거형이 트리로 정리되어 있다. 여기서 새 구조체를 만들거나(우클릭 → New → Structure), 기존 구조체에 필드를 추가할 수 있다.
- **구조체(Structure) 자동 인식 확장**: 어떤 포인터 변수가 여러 오프셋(`+0`, `+4`, `+8`)으로 반복해서 접근되는 패턴이 보이면, 이는 구조체일 가능성이 높다는 신호다. Data Type Manager에서 구조체를 정의하고 그 포인터를 구조체 포인터로 Retype하면, 이후 `*(int *)(param_1 + 4)` 같은 코드가 `param_1->field_0x4`처럼 훨씬 읽기 쉬운 형태로 바뀐다.

## 화면/코드에서 보이는 징후
- Decompile 창 곳곳에 `local_XX`, `param_X`, `DAT_XXXXXXXX`, `FUN_XXXXXXXX`, `undefined4` 같은 기본값 이름/타입이 반복해서 보인다.
- 변수 위에서 우클릭하면 컨텍스트 메뉴에 **Rename Variable**, **Retype Variable**, **Auto Create Structure** 같은 항목이 보인다.

## 가장 먼저 할 것
지금 읽고 있는 함수에서 가장 자주 등장하거나 로직상 중요해 보이는 변수(예: 사용자 입력을 담는 버퍼, 비교 결과를 담는 플래그)부터 이름을 바꾼다. 이름만 바꿔도 코드 전체의 가독성이 즉시 좋아진다.

## 단계별 절차

**1) 이름 바꾸기 (Rename, `L`)**

Decompile 창이나 Listing에서 이름을 바꾸고 싶은 변수/함수 위에 커서를 놓고 `L`을 누른다. 인라인 편집 상자가 뜨면 새 이름을 입력하고 Enter. 예: `local_c` → `strcmp_result`, `FUN_00401550` → `check_password`.

**2) 함수 이름 바꾸기**

함수 자체의 이름은 Decompile 창 맨 위 시그니처 줄에서 함수 이름 부분에 커서를 놓고 `L`을 누르거나, Symbol Tree의 Functions 폴더에서 함수 항목을 우클릭 → **Rename**을 사용해도 된다.

**3) 변수 타입 바꾸기 (Retype Variable, `Ctrl+L`)**

타입을 바꾸고 싶은 변수 위에 커서를 놓고 `Ctrl+L`을 누른다. "Retype Variable" 대화상자가 뜨면 타입 이름을 입력한다(자동완성 지원). 예: `undefined4 param_1` → `char *param_1`로 바꾸면 이후 `param_1`을 다루는 모든 표현식이 포인터 연산으로 다시 렌더링된다.

**4) 함수 시그니처 전체 편집**

Decompile 창 상단 함수 이름 줄 우클릭 → **Edit Function Signature**를 선택하면 리턴 타입, 파라미터 목록(추가/삭제/타입 변경/이름 변경), 호출 규약을 한 번에 편집하는 대화상자가 뜬다. Ghidra가 파라미터 개수를 잘못 추정했다고 판단되면 여기서 직접 바로잡는다.

**5) 구조체 만들기**

Data Type Manager 탭에서 이 프로그램의 폴더(보통 프로그램 이름으로 된 카테고리) 위에 우클릭 → **New → Structure**를 선택하면 빈 구조체 편집기가 열린다. 필드를 오프셋/타입/이름 순으로 추가한다. 완료 후 이 구조체를 변수의 타입으로 지정(`Ctrl+L`에서 구조체 이름 입력 후 포인터 표시 `*` 추가)하면 적용된다.

**6) Auto Create Structure(자동 구조체 추론) 활용**

포인터 변수 위에서 우클릭했을 때 **Auto Create Structure** 항목이 보이면, Ghidra가 그 포인터에 대한 코드 상의 오프셋 접근 패턴을 스스로 분석해서 구조체 초안을 자동 생성해 준다. 이후 Data Type Manager에서 필드 이름만 다듬으면 되므로 수작업보다 빠르다.

**7) 전역 데이터 이름 바꾸기**

`DAT_XXXXXXXX`도 함수와 동일하게 `L`로 이름을 바꿀 수 있다. 예를 들어 정답 문자열을 가리키는 것으로 확인되면 `DAT_00403010` → `s_correct_password`처럼 바꿔서 이후 코드 어디서든 그 의미가 바로 드러나게 한다.

## 명령어/단축키
- 이름 바꾸기: **`L`** (함수, 변수, 파라미터, 라벨, 전역 데이터 공통)
- 타입 바꾸기: **`Ctrl+L`** (Retype Variable)
- 함수 시그니처 전체 편집: 함수 이름 우클릭 → **Edit Function Signature**
- 구조체 생성: Data Type Manager 우클릭 → **New → Structure**
- 자동 구조체 추론: 포인터 변수 우클릭 → **Auto Create Structure**
- 주석 달기: `;` (EOL 주석), `Ctrl+;` (Plate/블록 주석)

## 출력 해석
- 이름을 바꾼 뒤 Decompile 창의 코드가 즉시 새 이름으로 갱신되는지 확인한다. 갱신되지 않으면 다른 함수를 봤다가 다시 돌아와 새로고침되는 경우도 있다.
- 타입을 구조체 포인터로 바꿨는데 필드 접근이 `->field_0x4`처럼 오프셋 그대로 보인다면, 그 오프셋에 해당하는 필드를 아직 구조체 정의에 추가하지 않은 것이다. Data Type Manager에서 그 구조체를 다시 열어 해당 오프셋에 필드를 채운다.
- 함수 시그니처를 바꾼 뒤 그 함수를 호출하는 다른 코드의 인자 표현도 함께 바뀌어 보이면, 변경이 프로그램 전체에 일관되게 반영된 것이다.

## 흔한 실수
- 이름만 바꾸고 타입은 그대로 두는 것 — 이름이 바뀌어도 타입이 `undefined4`인 채로 있으면 포인터 연산이나 구조체 접근이 여전히 원시적인 형태(`*(int *)(x + 4)`)로 남아 가독성 개선 효과가 절반에 그친다.
- 확신 없이 타입을 바꿨다가 코드가 오히려 이상하게 렌더링되는 것을 보고 당황하는 것 — 잘못된 타입 지정이면 언제든 다시 `Ctrl+L`로 되돌리거나 다른 타입으로 바꿀 수 있으니, 시행착오를 두려워하지 않아도 된다.
- 함수 시그니처를 편집할 때 실제 호출 규약(예: x64에서 `__fastcall`처럼 레지스터로 인자를 받는지)을 무시하고 파라미터만 추가하는 것 — 개수만 맞추는 게 아니라 호출 규약 자체가 맞는지도 함께 확인해야 한다.
- 구조체를 만들 때 필드 오프셋을 잘못 계산해서 실제 데이터와 어긋나게 정의하는 것 — 필드를 추가할 때마다 REV-0162(Hex View로 디컴파일 결과 검증하기)로 실제 메모리 값과 대조하는 습관이 필요하다.

## 막혔을 때 다음 체크
- 이름/타입을 바꿔도 여전히 로직이 이해가 안 된다면 → REV-0158(Ghidra Decompiler 창 읽기)로 돌아가 pseudo C 연산자 의미부터 재확인.
- 이 변수/데이터가 실제로 어떤 값을 담고 있는지 직접 눈으로 확인하고 싶다면 → REV-0162(Hex View로 디컴파일 결과 검증하기).
- 이름을 바꾼 함수가 프로그램 전체 흐름에서 어디에 위치하는지 다시 보고 싶다면 → REV-0166(함수 Call Graph로 핵심 로직 좁히기).
- 여러 개의 비슷한 필드 접근 패턴이 반복되는데 구조체로 묶어야 할지 판단이 안 서면 → 우선 필드별로 이름만 붙여두고, 패턴이 명확해지면(같은 오프셋 조합이 여러 함수에서 반복) 그때 구조체로 승격하는 점진적 접근이 안전하다.

## 미니 예제
REV-0159~0160 예제에서 찾은 `FUN_00401550`을 정리하는 과정:

```c
// 정리 전
undefined4 FUN_00401550(char *param_1)
{
  int local_c;
  local_c = strcmp(param_1, DAT_00403010);
  if (local_c == 0) {
    return 1;
  }
  return 0;
}
```

1. `FUN_00401550` 위에서 `L` → `check_password`로 변경.
2. `param_1` 위에서 `L` → `user_input`으로 변경.
3. `local_c` 위에서 `L` → `cmp_result`로 변경.
4. `DAT_00403010` 위에서 `L` → `s_correct_password`로 변경.
5. 함수 리턴 타입이 실제로는 bool 의미이므로, 함수 이름 줄 우클릭 → Edit Function Signature에서 리턴 타입을 `undefined4`에서 `int`(또는 지원 환경이면 `bool`)로 바꾼다.

정리 후:
```c
int check_password(char *user_input)
{
  int cmp_result;
  cmp_result = strcmp(user_input, s_correct_password);
  if (cmp_result == 0) {
    return 1;
  }
  return 0;
}
```
이 상태가 되면 이 함수가 하는 일이 코드를 처음 보는 사람에게도 즉시 전달된다.

## 관련 글
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0159 — Ghidra Function 목록과 Symbol Tree
- REV-0160 — Ghidra XREF 따라가기
- REV-0162 — Hex View로 디컴파일 결과 검증하기
- REV-0168 — 정적 분석 결과를 Python 의사코드로 옮기기

## 출처/검증
- Rename(`L`)/Retype Variable(`Ctrl+L`) 단축키, Edit Function Signature, Data Type Manager, Auto Create Structure: Ghidra 공식 Help 문서(Decompiler, Data Type Manager 관련 topic) 및 널리 인용되는 Ghidra 단축키 정리 자료 기준.
- 라이브 Ghidra 실행 화면을 직접 캡처해 재검증하지는 않았으며, 공식 문서와 커뮤니티에서 통용되는 기본 키바인딩을 기준으로 작성되었다. 로컬 환경에서 키바인딩이 커스터마이즈되어 있다면 다를 수 있다(Edit → Tool Options → Key Bindings 또는 메뉴 항목에 마우스를 올린 채 `F4`로 확인 가능).
