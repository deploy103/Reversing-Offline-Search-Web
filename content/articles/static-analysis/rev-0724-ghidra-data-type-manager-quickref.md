---
id: REV-0724
title: "Ghidra Data Type Manager 빠른 참조"
slug: "rev-0724-ghidra-data-type-manager-quickref"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Data Type Manager", "Ghidra 구조체 만들기", "Ghidra gdt 파일", "Ghidra archive", "Ghidra struct editor"]
aliases: ["Ghidra 데이터 타입 매니저", "Ghidra 구조체 창", "Ghidra 타입 아카이브", "Ghidra 헤더 불러오기"]
symptom_keywords: ["Ghidra에서 구조체 만드는 법 모름", "local_38 같은 변수를 구조체로 묶고 싶음", "Ghidra gdt 파일이 뭔지 모름", "Ghidra Data Type Manager 창을 못 찾음"]
source_ids: ["SRC-GHIDRA-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra의 **Data Type Manager** 창(`Window → Data Type Manager`)은 IDA의 Structures/Enums/Local Types에 해당하는 기능을 한 창에서 모두 제공하는 곳으로, 여기서 구조체·enum·typedef를 직접 만들거나 `.gdt`(Ghidra Data Type Archive) 파일 또는 C 헤더를 불러와 바이너리에 적용할 수 있다.

## 언제 검색해야 하나
- Decompile 창에 `undefined4 field0x8`처럼 구조체가 될 법한 필드가 반복해서 보일 때
- 변수를 구조체로 묶어서 `->` 표기로 읽고 싶을 때
- 이미 알려진 라이브러리 헤더(`.h`)나 다른 프로젝트에서 만든 타입 아카이브를 재사용하고 싶을 때
- Data Type Manager 창이 화면에 안 보여서 어디서 여는지 찾고 있을 때

## 핵심 개념

### Data Type Manager 창 구조
`Window → Data Type Manager`로 열면 좌측에 트리 형태로 여러 **Archive**(타입 저장소)가 나열된다. 기본적으로 다음이 함께 보인다.
- **Built In Types** — Ghidra가 기본 제공하는 원시 타입(`int`, `char`, `undefined4` 등)
- **현재 프로그램 이름의 Archive** — 지금 분석 중인 바이너리 전용으로 새로 만든 구조체/enum이 저장되는 곳
- 추가로 불러온 **.gdt 아카이브**들(예: 표준 라이브러리용 아카이브)

### 새 구조체 만들기
현재 프로그램 Archive를 우클릭하고 `New → Structure`를 선택하면 구조체 편집기가 열린다. 이 편집기에서 오프셋별로 필드를 추가/삭제하고 각 필드의 이름과 타입을 지정할 수 있다. 편집기 안에서 필드 크기를 조절하면 이후 필드들의 오프셋이 자동으로 밀리거나 당겨진다.

### Enum과 typedef도 같은 창에서
`New → Enum`으로 열거형을, `New → Typedef`로 typedef를 같은 방식으로 만들 수 있다. IDA처럼 구조체/enum이 별도 창으로 나뉘어 있지 않고 Data Type Manager 하나에 모두 모여 있는 것이 Ghidra의 특징이다.

### 변수에 구조체 적용하기
Decompile 창에서 포인터 변수를 우클릭 후 `Retype Variable`(`Ctrl+L`)을 선택하고, 방금 만든 구조체 이름에 `*`를 붙여 입력하면 그 포인터가 구조체 타입으로 재해석되어 `local_10->field1_0x8`처럼 표시된다. Ghidra는 구조체를 적용한 뒤에도 오프셋 기반 필드 이름(`field1_0x8` 등)을 자동으로 붙여주므로, 그 필드를 다시 편집기에서 원하는 이름으로 바꿔주면 된다.

### .gdt 아카이브 불러오기/만들기
`File → Open File Archive` 또는 Data Type Manager 창 상단 아이콘으로 기존 `.gdt` 파일을 불러올 수 있다. 반대로 지금 프로젝트에서 만든 타입들을 다른 프로젝트에서도 재사용하려면, Archive를 우클릭해 `Save As`로 별도 `.gdt` 파일로 내보낼 수 있다. C 헤더 파일을 직접 파싱해서 아카이브로 만드는 기능(`Parse C Source`)도 제공된다.

## 화면/코드에서 보이는 징후
Decompile 창에서 `*(undefined4 *)(param_1 + 8)`처럼 포인터에 오프셋을 더해 접근하는 코드가 반복되거나, 함수 인자가 `undefined4`, `undefined8` 같은 미확정 타입으로만 표시되어 실제 의미를 알 수 없을 때 Data Type Manager를 열어볼 때다.

## 가장 먼저 할 것
`Window → Data Type Manager`로 창을 열고, 현재 프로그램 Archive 아래에 이미 만들어진 타입이 있는지부터 확인한다.

## 단계별 절차

**1) 창 열기**

`Window → Data Type Manager`.

**2) 새 구조체 생성**

현재 프로그램 Archive 우클릭 → `New → Structure` → 이름 입력(예: `player_t`) → 구조체 편집기에서 필드 추가.

**3) 필드 크기/타입 편집**

편집기 하단에서 필드를 선택해 크기를 바꾸거나, 타입 컬럼에 다른 데이터 타입(다른 구조체, 배열, 포인터 등)을 끌어다 놓을 수 있다.

**4) 변수에 적용**

Decompile 창에서 대상 변수를 우클릭 → `Retype Variable`(`Ctrl+L`) → 구조체 포인터 타입 입력.

**5) 결과 정리**

자동으로 붙은 `field1_0x8` 같은 이름을 편집기에서 실제 의미에 맞는 이름으로 바꾼다.

**6) 필요하면 아카이브로 저장**

다른 바이너리에서도 같은 구조체를 쓸 예정이면 Archive를 우클릭 → `Save As`로 `.gdt` 파일로 저장해둔다.

## 명령어/단축키
| 메뉴/단축키 | 동작 |
|---|---|
| `Window → Data Type Manager` | 창 열기 |
| 우클릭 → `New → Structure` | 새 구조체 생성 |
| 우클릭 → `New → Enum` | 새 열거형 생성 |
| 우클릭 → `New → Typedef` | 새 typedef 생성 |
| `Ctrl+L` (Decompile 창) | 변수 Retype(구조체 포인터 등 적용) |
| `File → Open File Archive` | 기존 `.gdt` 아카이브 불러오기 |
| 우클릭 Archive → `Save As` | 현재 타입들을 `.gdt`로 내보내기 |
| `File → Parse → Parse C Source` | C 헤더를 파싱해 아카이브로 생성 |

## 출력 해석
- 구조체를 적용하면 Decompile 코드의 `*(undefined4 *)(param_1 + 8)`이 `param_1->field1_0x8`처럼 바뀐다. `field1_0x8`은 오프셋 8을 뜻하는 Ghidra의 자동 이름 규칙이므로(REV-0640 참고 성격의 명명 규칙과 유사), 편집기에서 이름을 바꿔주면 된다.
- 구조체 크기가 실제 코드에서 관찰되는 최대 오프셋보다 작으면 Ghidra가 구조체를 자동으로 확장하거나, 접근이 구조체 밖으로 벗어난다는 경고성 표시를 보여줄 수 있다.
- `.gdt` 아카이브를 불러왔는데 원하는 타입이 안 보이면, 트리에서 해당 아카이브가 접혀 있거나 검색창(Filter)에 이전 검색어가 남아 있을 수 있다.

## 흔한 실수
- 구조체를 만들고도 Decompile 창의 변수에 `Ctrl+L`로 재적용하는 단계를 빼먹는 것.
- 필드 크기를 실제와 다르게 지정해서 이후 필드들의 오프셋이 전부 어긋나는 것.
- 프로그램 전용 Archive에 만든 임시 구조체를 그대로 두고, 재사용 가능한 구조체까지 `.gdt`로 저장해두지 않아 다음 바이너리에서 처음부터 다시 만드는 것.
- Data Type Manager와 Symbol Tree/Functions 목록을 혼동해서 구조체 정의를 함수 목록에서 찾으려 하는 것 — 구조체/타입은 항상 Data Type Manager에서 관리한다.

## 막혔을 때 다음 체크
- 구조체가 아니라 이름/타입 변경 자체(`L`/`Ctrl+L`)가 헷갈리면 → REV-0161 Ghidra Rename과 Data Type 수정.
- Decompile 창 자체의 읽는 법이 궁금하면 → REV-0158 Ghidra Decompiler 창 읽기.
- 이 필드가 어디서 참조되는지 추적하고 싶으면 → REV-0160 Ghidra XREF 따라가기.
- 자동화로 구조체를 스크립트로 만들고 싶으면 → REV-0725 Ghidra 스크립트 API 빠른 참조(기초).

## 미니 예제
```text
1. Window → Data Type Manager 열기
2. 프로그램 Archive 우클릭 → New → Structure → "player_t"
3. 구조체 편집기에서 offset 0(4바이트, hp), offset 4(4바이트, level) 추가
4. Decompile 창에서 param_1 우클릭 → Retype Variable → "player_t *"
5. *(undefined4 *)(param_1 + 4)가 param_1->level로 표시됨
```

## 관련 글
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0160 — Ghidra XREF 따라가기
- REV-0725 — Ghidra 스크립트 API 빠른 참조(기초)

## 출처/검증
- Data Type Manager 창 구조(Built In Types, 프로그램 Archive, 외부 `.gdt` 아카이브), 구조체/enum/typedef 생성 메뉴, `Ctrl+L` Retype Variable, `.gdt` 저장/불러오기 기능은 Ghidra 공식 문서(Ghidra Help, NationalSecurityAgency/ghidra 저장소의 공식 문서 페이지) 기준으로 정리했다(2026-09-09 검증).
- 정확한 메뉴 항목 이름과 위치는 Ghidra 버전에 따라 소폭 달라질 수 있으므로, 실제 설치본에서 우클릭 메뉴로 재확인할 것을 권장한다.
