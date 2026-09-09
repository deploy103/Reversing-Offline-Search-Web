---
id: REV-0737
title: "IDA Local Types 창 활용하기"
slug: "rev-0737-ida-local-types-window"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["Local Types", "Shift+F1", "IDA 타입 텍스트 편집", "Parse C header file", "typedef 정의", "Local Types export"]
aliases: ["IDA Local Types 창", "타입 텍스트로 정의하기", "C 헤더 붙여넣기 IDA", "로컬 타입 관리"]
symptom_keywords: ["구조체를 하나씩 클릭하며 만들기 귀찮음", "C 코드 형태로 타입을 한 번에 붙여넣고 싶음", "Local Types랑 Structures 뭐가 다른지 모름", "구조체 정렬이 이상하게 적용됨"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
**Local Types** 창(`Shift+F1`)은 현재 IDA 데이터베이스에 등록된 모든 사용자 정의/가져온 타입(구조체, 공용체, enum, typedef, 함수 원형)을 **C 문법 텍스트**로 한 번에 보고 편집할 수 있는 창으로, Structures/Enumerations 창처럼 항목을 하나씩 클릭해서 만드는 대신 C 코드를 그대로 타이핑하거나 붙여넣어 여러 타입을 한꺼번에 정의할 수 있다는 점이 가장 큰 장점이다.

## 언제 검색해야 하나
- 이미 손에 있는 C 구조체 정의(문제 소스 일부, 공개된 SDK 헤더 등)를 IDA에 빠르게 그대로 옮기고 싶을 때
- REV-0734(Structures 창)에서 필드를 하나씩 클릭해 추가하는 게 번거로워서, 텍스트로 한 번에 여러 구조체/typedef를 정의하고 싶을 때
- 이미 정의해 둔 타입들을 한눈에 훑어보거나, 다른 IDA 데이터베이스로 옮기기 위해 내보내고(export) 싶을 때
- Local Types에서 구조체를 만들었는데 필드 오프셋이 예상과 다르게 계산되어서 원인을 찾아야 할 때

## 핵심 개념

### Local Types가 담고 있는 것
Local Types는 현재 데이터베이스(idb)에 실제로 존재하는 모든 타입 정의의 저장소다. 여기에는 다음이 모두 포함된다.

- 분석자가 Structures/Enumerations 창에서 만든 구조체·enum(REV-0734, REV-0735)
- `File → Load file → Parse C header file...`로 헤더에서 가져온 타입
- REV-0736에서 다룬 Type Libraries(til)에서 실제로 참조되어 복사된 타입
- 함수 원형(REV-0738)에 등장하는 이름 붙은 typedef

Structures/Enumerations 창이 각각 구조체 전용, enum 전용 뷰인 것과 달리, Local Types는 이 모든 종류의 타입을 텍스트 기반의 통합 목록으로 보여준다.

### 텍스트로 타입 정의하기
Local Types 창에서 `Ins`(또는 우클릭 → **Insert...**, 일부 버전에서는 **Add...**)를 누르면 C 선언 형태로 타입을 직접 입력하는 편집창이 뜬다. 예를 들어 다음처럼 여러 구조체와 typedef를 한 번에 붙여넣을 수 있다.

```c
typedef struct _PLAYER {
  int id;
  int hp;
  int mp;
  char name[16];
} PLAYER, *PPLAYER;
```

Structures 창에서 필드를 하나씩 `Ins`로 추가하는 것과 달리, 이미 문법이 맞는 C 코드가 있다면 이 방식이 압도적으로 빠르다.

### C 헤더 파일 통째로 가져오기
더 큰 규모라면 `File → Load file → Parse C header file...` 메뉴로 `.h` 파일 자체를 파싱해서 그 안의 모든 타입을 한 번에 Local Types에 채울 수 있다. 파싱 중 알 수 없는 매크로나 컴파일러 확장 문법을 만나면 오류가 나므로, 필요하면 헤더 상단에 IDA가 이해하도록 `#define` 몇 개를 추가하거나 문제되는 부분만 잘라내고 다시 시도한다.

### Structures 창과의 차이 — 정렬(alignment) 주의
Local Types에서 C 문법으로 구조체를 선언하면, IDA는 기본적으로 표준 C 컴파일러의 정렬 규칙을 적용해 필드 오프셋을 계산한다. 그런데 원본 바이너리가 `#pragma pack(1)`처럼 다른 정렬 규칙으로 컴파일되었다면, Local Types에서 그냥 선언한 구조체는 실제 오프셋과 어긋나게 계산될 수 있다. 이 경우 선언 앞에 `#pragma pack(1)` (또는 필요한 정렬 값)을 명시하거나, Structures 창(REV-0734)에서 필드를 하나씩 만들며 각 필드의 정렬을 직접 통제하는 방법으로 우회해야 한다. 반대로 Structures 창에서 만든 구조체는 필드를 추가한 순서와 크기 그대로 오프셋이 결정되므로 이런 자동 재정렬 문제가 없다.

### 내보내기/가져오기
Local Types 창에서 타입을 선택한 뒤 우클릭 → **Export...**(또는 유사한 메뉴)를 사용하면 선택한 타입 정의를 `.h` 형태의 텍스트로 내보낼 수 있다. 이렇게 만든 텍스트는 다른 바이너리를 분석할 때 다시 파싱해서 재사용하거나, 팀원과 타입 정의를 공유하는 데 쓸 수 있다.

## 화면/코드에서 보이는 징후
- 이미 여러 구조체가 뒤섞인 C 코드/헤더가 있는데 Structures 창에서 하나씩 만들기엔 양이 너무 많다.
- Local Types에서 만든 구조체를 적용했더니, 실제 오프셋과 필드 위치가 미묘하게 어긋난다(패딩 문제 의심).
- 다른 바이너리 분석에서 썼던 구조체 정의를 이번 데이터베이스에도 그대로 옮기고 싶다.

## 가장 먼저 할 것
정의하려는 타입이 이미 텍스트(C 코드, 헤더 파일)로 존재하는지 확인한다. 존재한다면 Local Types의 텍스트 편집/헤더 파싱 기능을 바로 활용하고, 존재하지 않고 오프셋만으로 새로 추정해야 한다면 REV-0734(Structures 창)에서 필드를 하나씩 통제하며 만드는 편이 정렬 문제를 피하기 쉽다.

## 단계별 절차
1. `Shift+F1`로 Local Types 창을 연다.
2. 텍스트로 직접 입력하려면 `Ins`(또는 우클릭 → Insert/Add)를 눌러 C 선언 편집창을 열고, 구조체/typedef/enum 선언을 붙여넣는다.
3. 원본 바이너리가 특수한 정렬(예: 1바이트 정렬)로 빌드된 것 같다면 선언 앞에 `#pragma pack(N)`을 추가한다.
4. 헤더 파일 전체를 가져오려면 `File → Load file → Parse C header file...`로 `.h` 파일을 지정한다. 오류가 나면 문제 되는 매크로/문법을 헤더에서 잘라내거나 대체 정의를 추가한 뒤 다시 시도한다.
5. 완성된 타입은 REV-0148(`Y`)로 전역/지역 변수에 적용하거나, REV-0738에서 다루는 함수 원형 지정에서 타입 이름으로 참조한다.
6. 나중에 재사용하려면 타입을 선택한 뒤 우클릭 → **Export...**로 텍스트 형태로 저장해둔다.
7. 오프셋이 이상하게 계산된 것 같으면 Structures 창(`Shift+F9`)에서 같은 이름으로 만든 구조체와 오프셋을 대조해서 정렬 문제인지 확인한다.

## 명령어/단축키
- `Shift+F1`: Local Types 서브뷰 열기
- Local Types 창에서 `Ins`: 새 타입 텍스트 입력(구조체/typedef/enum/함수 원형 등)
- `File → Load file → Parse C header file...`: `.h` 파일 전체를 파싱해서 Local Types에 일괄 등록
- 타입 선택 후 우클릭 → **Export...**: 선택한 타입을 텍스트(`.h` 유사 형식)로 내보내기
- `Shift+F9` / `Shift+F10`: 각각 Structures / Enumerations 창(정렬을 직접 통제하고 싶을 때 대조용)

## 출력 해석
- C 선언 편집창에서 문법 오류가 있으면 저장 시 오류 메시지와 함께 어느 줄/토큰이 문제인지 표시된다. 알 수 없는 타입 이름을 참조했다면 먼저 그 타입부터 정의해야 한다.
- Parse C header file 실행 후 Output window에 성공적으로 파싱된 타입 개수와, 실패했다면 실패한 매크로/선언의 목록이 로그로 남는다.
- Local Types에 등록은 됐지만 실제 코드 어디에도 적용되지 않은 타입은 목록에는 보이지만 Pseudocode에는 아무 영향을 주지 않는다 — 반드시 `Y`나 함수 원형 지정으로 실제 적용해야 효과가 나타난다.

## 흔한 실수
- Local Types에서 C 문법으로 구조체를 선언하면서 원본의 특수 정렬(pack)을 고려하지 않아 필드 오프셋이 실제와 어긋나는 것.
- 헤더 파일을 통째로 파싱하려다 컴파일러 전용 확장 문법(예: `__declspec`, 컴파일러별 attribute) 때문에 파싱이 실패하는데, 오류 로그를 안 읽고 무작정 재시도만 반복하는 것.
- Local Types에 타입만 잔뜩 등록해두고 실제 변수/함수에는 하나도 적용하지 않아 분석에 아무 도움이 안 되는 것.
- Structures 창과 Local Types 창이 서로 다른 저장소라고 착각하는 것 — 실제로는 같은 타입 정보를 다른 방식(폼 기반 vs 텍스트 기반)으로 보여주는 것뿐이다.

## 막혔을 때 다음 체크
- 정렬 문제 없이 필드를 하나씩 통제하며 만들고 싶다면 → REV-0734 IDA에서 구조체를 직접 정의해서 디컴파일에 적용하기
- enum도 텍스트로 함께 선언하고 싶다면 → REV-0735 IDA에서 Enum을 정의해서 매직넘버를 이름으로 바꾸기
- 표준 SDK 타입을 직접 타이핑하지 않고 가져오고 싶다면 → REV-0736 IDA 타입 라이브러리(til) 로드해서 시그니처 인식률 높이기
- 정의한 타입을 함수 인자에 반영하고 싶다면 → REV-0738 IDA에서 함수 프로토타입을 수동으로 수정하기

## 미니 예제
문제에서 다음과 같은 구조체 정의 일부가 주어졌다고 하자.

```c
struct Packet {
    unsigned short type;
    unsigned short length;
    char data[64];
};
```

`Shift+F1`로 Local Types 창을 열고 `Ins`를 눌러 편집창에 이 코드를 그대로 붙여넣고 확인하면, Structures 창에서 필드 세 개를 하나씩 클릭해 만드는 것보다 훨씬 빠르게 타입이 등록된다. 이후 네트워크 패킷을 파싱하는 함수의 인자 위에서 `Y`를 눌러 `Packet *`을 지정하면, `*(unsigned short *)(a1)` 같은 표현이 `a1->type`으로 바로 바뀐다.

## 관련 글
- REV-0734 — IDA에서 구조체를 직접 정의해서 디컴파일에 적용하기
- REV-0735 — IDA에서 Enum을 정의해서 매직넘버를 이름으로 바꾸기
- REV-0736 — IDA 타입 라이브러리(til) 로드해서 시그니처 인식률 높이기
- REV-0738 — IDA에서 함수 프로토타입을 수동으로 수정하기
- REV-0148 — IDA Y로 타입 지정하기

## 출처/검증
- Local Types 서브뷰(`Shift+F1`)의 역할(현재 idb에 저장된 모든 타입을 텍스트 기반으로 통합 관리)과 `Ins`를 통한 C 선언 직접 입력, `File → Load file → Parse C header file...`로 헤더 일괄 파싱: Hex-Rays 공식 문서(Types) 기준.
- Local Types의 C 선언 파싱이 Structures 창과 다르게 표준 정렬 규칙을 적용해 `#pragma pack` 명시가 필요할 수 있다는 실전 caveat: 리버싱 실무에서 반복적으로 보고되는 동작이며, 정확한 재현 조건은 IDA 버전에 따라 다를 수 있다.
- 이 문서는 2026-09-09 기준 공개된 공식 문서 검색 결과를 바탕으로 작성했으며, 정확한 메뉴 문구(Insert/Add, Export 등)는 IDA 버전에 따라 다를 수 있으므로 실제 환경에서 재확인할 것을 권장한다.
