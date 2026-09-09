---
id: REV-0750
title: "Ghidra에서 구조체를 역으로 추론해서 만드는 법"
slug: "rev-0750-ghidra-reverse-engineer-structures"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Auto Create Structure", "Ghidra 구조체 추론", "Ghidra Create Structure From Selection", "구조체 오프셋 패턴", "Ghidra Structure Editor"]
aliases: ["Ghidra 구조체 역공학", "Ghidra 오프셋으로 구조체 만들기", "정의 없는 구조체 재구성"]
symptom_keywords: ["Ghidra에서 구조체를 모르는데 어떻게 만드나", "Ghidra 포인터 오프셋 반복 패턴", "Ghidra Auto Create Structure 안 될 때", "malloc 크기로 구조체 크기 추정"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
헤더나 문서가 없는 커스텀 구조체는 코드가 그 포인터를 어떻게 쓰는지(반복되는 오프셋 접근 패턴)를 관찰해서 거꾸로 재구성해야 하며, Ghidra의 Auto Create Structure와 Create Structure From Selection이 이 과정의 초안을 자동으로 만들어준다.

## 언제 검색해야 하나
- `undefined4 field_0x4`, `field_0x8` 같은 자동 이름이 여러 함수에 반복해서 나오는데 아직 struct로 묶지 않았을 때
- CTF 문제의 자체 자료구조처럼 헤더/공개 문서가 전혀 없는 구조체를 다뤄야 할 때
- `malloc` 호출의 크기 인자가 특정 상수(예: 24, 32)로 고정되어 있어 구조체 냄새가 날 때
- Auto Create Structure를 실행했는데 필드가 일부만 잡혀서 더 다듬어야 할 때

## 핵심 개념

### 언제 구조체를 "역으로" 추론해야 하는가
헤더 파일이나 공개 문서가 없는 커스텀 구조체(CTF 문제의 자체 자료구조, 알려지지 않은 내부 오브젝트 등)를 다룰 때는, 코드가 그 포인터를 어떻게 쓰는지 관찰해서 거꾸로 구조체 정의를 재구성해야 한다. REV-0742는 이미 정의가 있는(헤더/`.gdt`) 구조체를 가져오는 법이었다면, 이 글은 정의가 아예 없을 때 만들어내는 법이다.

### 신호 포착 - 반복되는 오프셋 접근
Decompile 창에서 같은 포인터 변수가 `*(int *)(param_1 + 0)`, `*(int *)(param_1 + 4)`, `*(char **)(param_1 + 8)`처럼 여러 고정 오프셋으로 반복 접근되면, 그 포인터가 가리키는 것은 십중팔구 구조체다. 오프셋 값과 그때 쓰인 타입(4바이트 int로 읽었는지, 8바이트 포인터로 읽었는지)을 하나씩 메모해두는 것이 첫 단계다.

### Auto Create Structure 활용
포인터 변수 위에서 우클릭했을 때 나타나는 Auto Create Structure를 실행하면, Ghidra가 현재 함수(또는 선택 범위) 안에서 그 포인터에 대한 모든 오프셋 접근을 스스로 스캔해 구조체 초안을 만들어준다. 이 초안은 필드 이름이 `field_0x0`, `field_0x4`처럼 자동 명명되어 있으므로, 이후 Data Type Manager(REV-0742)에서 열어 실제 의미에 맞는 이름으로 다듬는다.

### 한 함수만으로는 부족할 때 - Create Structure From Selection
구조체를 쓰는 코드가 여러 함수에 흩어져 있으면 한 함수의 Auto Create Structure만으로는 필드가 다 안 잡힌다. 이럴 때는 각 함수를 돌면서 반복하거나, 관련된 여러 줄을 Listing에서 선택한 뒤 Create Structure From Selection으로 선택 범위 안의 접근 패턴만 모아 구조체를 만드는 방법도 있다. 이후 Data Type Manager에서 여러 초안을 하나의 구조체로 병합(필드를 손으로 추가)한다.

### 크기와 정렬 확정하기
구조체의 전체 크기는 `sizeof` 호출, `malloc(N)` 호출의 인자, 배열 선언(구조체 배열이면 전체 크기를 원소 개수로 나눠 원소 크기 추정) 등에서 단서를 얻는다. 마지막 필드의 오프셋 + 그 필드의 크기가 전체 구조체 크기와 맞아떨어지는지 항상 검산한다. 안 맞으면 중간에 아직 못 찾은 필드(패딩이거나 코드에서 안 쓰이는 필드)가 있다는 뜻이다.

### 포인터/배열 필드 구분하기
오프셋에서 읽은 값을 다시 포인터처럼 역참조(`*(int *)(*(long *)(param_1 + 8) + 4)`)하는 패턴이 보이면, 그 필드는 다른 구조체를 가리키는 포인터다. 이런 경우 필드 타입을 `void *`로 우선 잡아두고, 가리키는 대상 구조체가 파악되면 나중에 그 구조체의 포인터 타입으로 교체(`Ctrl+L`)한다. 반대로 같은 오프셋 간격이 고정폭으로 반복되면(예: `+0x10`, `+0x14`, `+0x18`이 각각 4바이트씩) 배열 필드일 가능성을 의심한다.

### 검증 - Hex View와 실제 실행으로 대조
구조체 초안이 완성되면 REV-0162(Hex View로 디컴파일 결과 검증하기)에서 다룬 방식대로, 실제 메모리에서 그 오프셋들에 값이 있는지 GDB/x64dbg로 런타임에 값을 찍어 검산한다. 정적 추론만으로는 오프셋 사이의 패딩, 컴파일러가 넣은 정렬 바이트를 놓치기 쉽다.

## 화면/코드에서 보이는 징후
`undefined4 field_0x4`, `field_0x8` 같은 자동 이름이 여러 함수에 반복해서 나오는데 아직 struct로 묶지 않았거나, `malloc` 호출의 크기 인자가 특정 상수로 고정되어 있어 구조체 냄새가 날 때.

## 가장 먼저 할 것
의심되는 포인터 변수 하나를 정해서 그 변수가 쓰이는 모든 XREF(REV-0160)를 먼저 따라가며 오프셋 접근 목록부터 손으로 정리한다.

## 단계별 절차
1. 대상 포인터 변수 확정, XREF로 모든 사용처 나열
2. 각 사용처에서 오프셋과 그때 쓰인 타입(크기) 기록
3. 포인터 위 우클릭 → Auto Create Structure로 초안 생성
4. Data Type Manager에서 초안을 열어 필드 이름을 의미에 맞게 정리(REV-0161의 Rename 습관 적용)
5. `malloc` 크기 인자/`sizeof` 등에서 전체 크기 단서 확보, 필드 합계와 대조
6. 다른 함수에서 같은 포인터 타입이 더 쓰이면 그 함수도 돌며 누락된 필드 보완
7. GDB/x64dbg로 실제 실행 중 해당 메모리 오프셋 값 확인해 최종 검증(REV-0162)

## 명령어/단축키
- 포인터 변수 우클릭 → Auto Create Structure
- Listing에서 범위 선택 후 우클릭 → Create Structure From Selection
- Data Type Manager에서 구조체 편집
- `Ctrl+L`: 포인터에 구조체 타입 적용

## 출력 해석
Auto Create Structure 직후 Decompile 코드가 `param_1->field_0x0`, `param_1->field_0x4` 형태로 바뀌면 성공적으로 구조체 포인터로 인식된 것이다. 필드 이름이 아직 `field_0x`로 남아있는 건 정상이며, 다음 단계(이름 정리)로 넘어가면 된다.

## 흔한 실수
- 한 함수만 보고 구조체를 완성했다고 확신하는 것 — 다른 함수에서 다른 오프셋이 더 쓰일 수 있다.
- `malloc` 크기와 필드 합계를 검산하지 않아 마지막 패딩/필드를 놓치는 것.
- 포인터 필드를 int로 잘못 잡아 역참조 표현식이 이상하게 렌더링되는 것을 방치하는 것.

## 막혔을 때 다음 체크
- 이미 헤더/`.gdt`로 정의가 있는 구조체를 가져오는 법이 궁금하면 → REV-0742 Ghidra Data Type Manager로 구조체 임포트/정의하기
- 만든 구조체 필드의 실제 값을 메모리에서 확인하고 싶으면 → REV-0162 Hex View로 디컴파일 결과 검증하기
- 이 포인터가 어디서 만들어지는지(XREF) 다시 보고 싶으면 → REV-0160 Ghidra XREF 따라가기

## 미니 예제
```c
// 정리 전 (여러 함수에서 반복 관찰됨)
undefined4 FUN_00401700(long param_1)
{
  int local_c;
  local_c = *(int *)(param_1 + 4);
  if (*(int *)param_1 == 0x1337) {
    local_c = local_c + 1;
  }
  return local_c;
}
```
1. `param_1 + 0`은 4바이트 비교값, `param_1 + 4`는 4바이트 카운터로 추정
2. 다른 함수에서 `param_1 + 8`이 `char *`로 쓰이는 것도 추가 확인
3. `param_1` 위 우클릭 → Auto Create Structure → `field_0x0`, `field_0x4`, `field_0x8` 초안 생성
4. Data Type Manager에서 각각 `magic`, `counter`, `label`로 이름 정리, 구조체 이름을 `GameObject`로 지정
5. `malloc(0x10)` 호출(총 16바이트)과 필드 합계(4+4+8=16)가 일치함을 확인해 구조체 완성 확정

## 관련 글
- REV-0742 — Ghidra Data Type Manager로 구조체 임포트/정의하기
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0162 — Hex View로 디컴파일 결과 검증하기
- REV-0160 — Ghidra XREF 따라가기

## 출처/검증
Ghidra 공식 Help 문서(Auto Create Structure, Structure Editor, Create Structure From Selection) 기준. 실제 실행 화면을 캡처해 재검증하지는 않았으며, 공식 문서와 널리 통용되는 메뉴 경로를 기준으로 작성했다(2026-09-09).
