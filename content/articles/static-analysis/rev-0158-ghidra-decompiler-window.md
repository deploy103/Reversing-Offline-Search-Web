---
id: REV-0158
title: "Ghidra Decompiler 창 읽기"
slug: "rev-0158-ghidra-decompiler-window"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Decompile window", "Ghidra 디컴파일러", "Ghidra pseudo C", "Ghidra local_", "Ghidra param_", "Ghidra DAT_"]
aliases: ["Ghidra 디컴파일 창", "Ghidra C 코드 보기", "Ghidra 의사코드"]
symptom_keywords: ["Ghidra 디컴파일 결과 읽는 법", "local_28이 뭔지 모름", "Ghidra DAT_ 주소가 뭔지 모름", "Ghidra 디컴파일러 창이 비어있음"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Ghidra CodeBrowser 오른쪽의 **Decompile 창**은 현재 Listing에서 커서가 위치한 함수를 C와 비슷한 의사코드(pseudo C)로 실시간 변환해 보여주는 패널이며, `local_XX`/`param_X`/`DAT_XXXXXXXX`/`FUN_XXXXXXXX` 같은 기본 이름의 의미만 정확히 알아도 초기 분석 속도가 크게 빨라진다.

## 언제 검색해야 하나
- CodeBrowser를 처음 열었을 때 오른쪽 패널에 나오는 C 비슷한 코드가 뭔지 모를 때
- `local_28`, `param_1`, `DAT_00402010`, `FUN_00401500` 같은 이름의 의미가 궁금할 때
- Listing(왼쪽 어셈블리 창)과 Decompile(오른쪽 C 코드 창)이 서로 어떻게 연결되어 있는지 모를 때
- 디컴파일 결과가 실제 로직과 다르게 보여서 신뢰할 수 있는지 검증하고 싶을 때

## 핵심 개념
Ghidra CodeBrowser는 기본적으로 화면을 세로로 나눠, 왼쪽에 **Listing**(주소별 어셈블리 + 데이터), 오른쪽에 **Decompile**(현재 커서가 있는 함수의 C 유사 의사코드)을 동시에 보여준다. 두 창은 **커서 동기화**되어 있어서, Listing에서 특정 주소로 이동하면 Decompile 창도 그 주소가 속한 문장(statement)을 자동으로 하이라이트한다. 반대로 Decompile 창에서 특정 줄을 클릭해도 Listing의 해당 주소로 커서가 이동한다.

Ghidra 디컴파일러가 자동으로 붙이는 기본 이름 규칙:
- **`param_1`, `param_2`, ...**: 함수의 인자(파라미터). IDA의 `a1`, `a2`와 같은 역할이다. Windows x64는 `RCX, RDX, R8, R9` 순서, x86 stdcall/cdecl은 스택을 통해 전달되며, Ghidra가 호출 규약(Compiler Spec)에 따라 자동으로 매핑해서 `param_N` 순서를 정한다.
- **`local_XX`**: 함수 내부의 지역 변수. `XX`는 대개 그 변수가 스택 프레임에서 차지하는 오프셋(16진수)에서 유래한 이름이라, `local_28`과 `local_2c`처럼 오프셋이 다르면 서로 다른 변수다. 이름만으로 오프셋 크기를 짐작할 수 있어, 배열/버퍼처럼 여러 바이트를 쓰는 변수는 오프셋 간격이 넓게 벌어져 있는 것으로 어림할 수 있다.
- **`DAT_XXXXXXXX`**: 코드가 아닌 전역 데이터 영역(예: `.data`, `.rodata`)의 특정 주소를 가리키는데, 아직 사람이 의미 있는 이름을 붙이지 않은 상태. 고정 문자열, 전역 변수, 참조 테이블 등이 여기 해당한다.
- **`FUN_XXXXXXXX`**: 아직 이름이 붙지 않은 사용자 정의 함수. 이 함수를 호출하는 코드를 볼 때 이 이름이 나오면 "Ghidra가 라이브러리로 식별하지 못한, 이 바이너리 고유의 함수"라는 뜻이다.
- **`uVar1`, `iVar1`, `cVar1`, `sVar1`** 등: 스택에 자리를 갖지 않고 레지스터에만 존재하는 임시 변수. 접두사는 타입을 암시한다(`u`=unsigned int, `i`=int, `c`=char, `s`=short 등).
- **`unaff_`, `in_`, `extraout_`** 접두사: 각각 "이 레지스터가 함수 진입 전부터 어떤 값을 갖고 있었는데 그 출처를 못 찾음", "이 레지스터 값이 함수 호출 규약 상 인자가 아닌데 실제로는 쓰이고 있음", "함수가 리턴한 것으로 보이는 추가 레지스터 값" 등을 의미하며, 디컴파일러의 분석이 완벽하지 않을 때 나타나는 신호이므로 이런 이름이 보이면 그 주변 코드는 어셈블리로 직접 대조하는 것이 안전하다.

## 화면/코드에서 보이는 징후
- 오른쪽 Decompile 패널 상단에 함수 시그니처(`undefined4 FUN_00401230(int param_1, char *param_2)` 형태)가 보이고, 그 아래 중괄호로 감싼 C 유사 코드 본문이 이어진다.
- 코드 중간중간 `/* WARNING: ... */` 같은 주석이 자동으로 삽입되어 있으면, 디컴파일러가 스스로 확신하지 못하는 부분(예: 스택 정리가 애매함, 알 수 없는 계산 등)을 표시한 것이다.
- Listing에서 커서를 옮기면 Decompile 창의 해당 줄이 옅은 색으로 하이라이트된다.

## 가장 먼저 할 것
분석하려는 함수로 이동한 뒤(Symbol Tree에서 더블클릭하거나 Listing에서 커서 이동), Decompile 창에 그 함수의 pseudo C가 자동으로 뜨는지 확인한다. 함수 시그니처의 인자 개수/타입이 말이 되는지부터 훑어본다.

## 단계별 절차

**1) 함수로 이동**

Symbol Tree(왼쪽 패널) → Functions 폴더에서 원하는 함수를 더블클릭하거나, Listing에서 `G`(Go To)로 주소를 입력해 이동한다.

**2) Decompile 창 자동 갱신 확인**

오른쪽 Decompile 창이 해당 함수의 pseudo C로 바뀌는지 확인한다. 만약 Decompile 창이 안 보인다면 **Window → Decompile**에서 다시 켤 수 있다.

**3) 함수 시그니처부터 읽기**

맨 위 줄(리턴 타입, 함수 이름, 파라미터 목록)을 먼저 읽는다. 파라미터 개수와 순서가 이 함수를 호출하는 다른 코드의 인자 전달과 일치하는지 나중에 대조할 기준이 된다.

**4) 지역 변수 선언부 확인**

함수 본문 초반에 `int local_28;`, `char local_38[16];`처럼 지역 변수가 선언된 목록이 나온다. 배열처럼 크기가 있는 변수는 버퍼일 가능성이 높고, CTF에서는 이런 버퍼가 입력값을 저장하는 곳인 경우가 많다.

**5) 본문 로직을 어셈블리와 교차 확인**

의심스러운 줄(예: 이상한 `unaff_`, `extraout_` 변수, WARNING 주석)이 있으면 그 줄을 클릭해서 Listing의 대응 주소로 이동한 뒤 실제 어셈블리 명령어를 직접 읽어 확인한다.

**6) 필요하면 이름/타입 정리**

`local_28`, `param_1`, `DAT_00402010` 같은 기본 이름은 REV-0161(Ghidra Rename과 Data Type 수정)에서 다루는 방법으로 의미 있는 이름으로 바꿔가며 읽으면 훨씬 빨라진다.

## 명령어/단축키
- Decompile 창 열기/닫기: **Window → Decompile**
- Listing ↔ Decompile 커서 동기화: 자동(별도 단축키 불필요), 클릭만으로 이동
- 함수 시그니처 편집: Decompile 창에서 함수 이름 위 우클릭 → **Edit Function Signature**
- 변수 이름 변경: 변수 위에서 `L`
- 변수 타입 변경: 변수 위에서 `Ctrl+L`

## 출력 해석
- `undefined4`, `undefined8` 같은 타입은 "크기는 알지만(4바이트/8바이트) 부호나 정확한 의미는 아직 특정되지 않은 값"이라는 뜻이다. 실제로는 `int`, `DWORD`, 포인터 등일 수 있으므로 문맥으로 판단해서 REV-0161 방식으로 재지정하면 가독성이 좋아진다.
- `CONCAT44(a, b)`, `SUB84(a, b)`처럼 생긴 함수 형태의 표현은 Ghidra 디컴파일러 고유의 **의사 연산자(pseudo-operator)**로, 레지스터 조각을 이어붙이거나(CONCAT) 잘라내는(SUB) 연산을 표현한 것이다. 예를 들어 `CONCAT44(extraout_EDX, eax)`는 "64비트 결과값 중 상위 32비트는 EDX, 하위 32비트는 EAX에서 온 것을 이어붙였다"는 뜻으로, x64 리턴값이나 64비트 나눗셈 결과 등에서 자주 보인다.
- `/* WARNING: Could not reconcile some variable overlaps */` 같은 주석은 디컴파일러가 스택 변수 경계를 확신하지 못했다는 뜻이므로, 그 함수는 어셈블리 원문 대조가 특히 필요하다.

## 흔한 실수
- Decompile 창의 pseudo C를 실제 C 소스코드처럼 100% 신뢰하는 것 — 디컴파일러는 추정 결과이며, 특히 최적화된 코드나 인라인 어셈블리가 섞인 함수에서는 로직이 왜곡되어 보일 수 있다.
- `local_XX`의 `XX` 값이 실제 변수 크기라고 오해하는 것 — 이는 스택 오프셋에서 유래한 이름일 뿐, 항상 변수 크기와 정비례하지는 않는다.
- WARNING 주석을 그냥 지나치는 것 — 이 주석이 있는 함수는 디컴파일 신뢰도가 낮다는 명시적 신호다.
- 함수 시그니처의 파라미터 타입(`undefined4` 등)을 그대로 두고 로직을 판단하는 것 — 타입을 먼저 바로잡으면(REV-0161) 이후 표현식이 훨씬 자연스럽게(예: 포인터 연산, 부호 있는 비교 등) 바뀐다.

## 막혔을 때 다음 체크
- 이름이 너무 기본값(`local_`, `param_`, `DAT_`, `FUN_`)이라 읽기 힘들다면 → REV-0161(Ghidra Rename과 Data Type 수정).
- `DAT_XXXXXXXX`가 실제로 무슨 값을 담고 있는지 확인하고 싶다면 → REV-0162(Hex View로 디컴파일 결과 검증하기).
- 이 함수를 호출하는 곳/이 함수가 호출하는 곳을 보고 싶다면 → REV-0160(Ghidra XREF 따라가기).
- 디컴파일 결과가 특정 지점에서 완전히 깨져 있다면 → IDA의 유사 증상인 rev-0151-positive-sp-value.md(스택 분석 오류 개념)을 참고해 스택 프레임 재계산이 필요한지 의심.

## 미니 예제
간단한 비밀번호 검증 함수가 Ghidra에서 다음처럼 보인다고 하자.

```c
undefined4 FUN_00401500(char *param_1)
{
  int local_c;
  local_c = strcmp(param_1, DAT_00403010);
  if (local_c == 0) {
    return 1;
  }
  return 0;
}
```

- `param_1`: 이 함수의 첫 번째 인자, 아마도 사용자가 입력한 문자열 포인터.
- `local_c`: `strcmp` 결과를 담는 지역 변수.
- `DAT_00403010`: 아직 이름이 없는 전역 데이터 주소. `strcmp`의 두 번째 인자로 쓰이는 것으로 보아, 실제로는 정답 문자열의 주소일 가능성이 크다.
- `DAT_00403010`을 더블클릭해 Listing으로 이동하면 그 주소에 저장된 실제 바이트(문자열이라면 ASCII 텍스트)를 확인할 수 있다 — 이 확인 과정은 REV-0162에서 자세히 다룬다.

이처럼 함수 이름 하나만 봐도 "이건 입력값을 정답 문자열과 `strcmp`로 비교하는 검증 함수"라는 가설을 곧바로 세울 수 있다.

## 관련 글
- REV-0159 — Ghidra Function 목록과 Symbol Tree
- REV-0160 — Ghidra XREF 따라가기
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0162 — Hex View로 디컴파일 결과 검증하기
- rev-0151-positive-sp-value.md — 디컴파일 신뢰도가 떨어지는 근본 원인(스택 분석 오류) 참고

## 출처/검증
- Decompile 창의 Listing 동기화, `local_`/`param_`/`DAT_`/`FUN_` 명명 규칙, `CONCAT`/`SUB` 계열 pseudo-operator: Ghidra 공식 Decompiler 도움말 문서(Decompiler Concepts, C Output 관련 topic) 및 Ghidra 소스 코드 내 디컴파일러 출력 규칙 기준.
- 라이브 Ghidra 환경에서 직접 캡처해 재검증하지는 않았으며, 공식 문서와 널리 알려진 버전 동작을 기준으로 작성되었다.
