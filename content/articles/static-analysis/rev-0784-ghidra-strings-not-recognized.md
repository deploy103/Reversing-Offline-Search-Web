---
id: REV-0784
title: "Ghidra에서 문자열이 인식되지 않을 때"
slug: "rev-0784-ghidra-strings-not-recognized"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Defined Strings 비어있음", "Ghidra ASCII Strings Analyzer", "Ghidra 문자열 인식 안 됨", "Ghidra 문자열 수동 정의", "Ghidra Data Type ASCII"]
aliases: ["Ghidra 문자열 창이 텅 빔", "Ghidra 문자열이 db로만 보임", "Ghidra 유니코드 문자열 안 잡힘"]
symptom_keywords: ["Ghidra Defined Strings 창에 문자열이 없음", "Ghidra에서 문자열이 회색 바이트로만 보임", "Ghidra가 문자열을 데이터로 인식 못함", "Ghidra 유니코드 문자열 인식 실패"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra의 `Window → Defined Strings` 창이 비어 있거나 실제로 존재하는 문자열이 목록에 안 보이는 것은 대부분 **ASCII Strings Analyzer가 아직 안 돌았거나, 최소 길이 설정보다 문자열이 짧거나, 그 영역이 Undefined 바이트/다른 데이터 타입으로 이미 잘못 정의되어 있기 때문**이며, 해당 주소를 직접 `String` 타입으로 재정의하면 대부분 해결된다.

## 언제 검색해야 하나
- Hex 뷰나 `strings` 결과에서는 분명히 텍스트가 보이는데 Ghidra `Defined Strings` 창에는 없을 때
- 특정 주소로 XREF를 따라갔더니 문자열이 `db 48h,65h,6ch...` 같은 원시 바이트로만 보일 때
- 짧은 문자열(1~3글자)이나 유니코드(UTF-16) 문자열이 목록에서 누락된 것 같을 때
- 문자열은 보이는데 그 문자열을 참조하는 XREF가 안 잡힐 때

## 핵심 개념
Ghidra에서 "문자열이 인식된다"는 것은 그 메모리 영역이 **String 계열 Data Type(예: `string`, `unicode`, `TerminatedCString`)으로 정의되어 있다**는 뜻이다. 이 정의는 자동으로 되는 게 아니라 Auto Analysis의 **ASCII Strings** Analyzer가 스캔해서 만들어주는 것이며, 다음과 같은 이유로 누락될 수 있다.

1. **최소 길이 미달**: ASCII Strings Analyzer는 기본적으로 일정 길이(기본값은 버전에 따라 다르며 보통 4~5바이트 이상) 이상인 시퀀스만 문자열로 인식한다. `"OK"`, `"A"`처럼 아주 짧은 문자열은 걸러진다.
2. **아직 분석이 실행되지 않음**: Auto Analysis를 건너뛰었거나 옵션에서 ASCII Strings를 꺼둔 채로 Analyze한 경우.
3. **이미 다른 타입으로 정의되어 있음**: 그 영역이 이미 `undefined4` 배열이나 다른 구조체로 정의되어 있으면, Analyzer가 기존 정의를 덮어쓰지 않고 건너뛴다.
4. **인코딩 불일치**: UTF-16(유니코드) 문자열인데 ASCII로만 스캔되었거나, 반대로 ASCII 문자열 영역이 유니코드로 오인된 경우.
5. **참조되지 않는 문자열**: 코드에서 직접 주소로 참조하지 않고 오프셋 계산이나 룩업 테이블을 거쳐 간접 참조하는 문자열은 애초에 코드 흐름 분석 단계에서 발견되지 못해 문자열 스캔 대상에서도 놓칠 수 있다.

## 화면/코드에서 보이는 징후
- `Window → Defined Strings` 창을 열었을 때 목록이 비어 있거나 기대한 문자열이 없다.
- Listing에서 해당 주소가 `??` (Undefined) 또는 `db` 계열 바이트로만 표시된다.
- Hex 뷰(REV-0162)에는 사람이 읽을 수 있는 ASCII/유니코드 텍스트가 분명히 보인다.

## 가장 먼저 할 것
문자열이 있어야 할 주소로 직접 이동(`G`)해서 그 영역이 실제로 어떤 상태(Undefined/다른 데이터 타입)로 정의되어 있는지부터 확인한다. 그다음 필요하면 수동으로 String 타입으로 재정의한다.

## 단계별 절차

**1) 대상 주소로 직접 이동**

`strings` 결과나 Hex 뷰에서 확인한 오프셋을 파일 기준 주소로 변환해 `G`(Go To)로 이동한다.

**2) 현재 정의 상태 확인**

Listing에서 그 위치가 Undefined(회색 `??`)인지, 이미 다른 데이터 타입으로 정의되어 있는지 본다.

**3) Undefined라면 재정의 안 된 상태로 되돌리기**

이미 잘못된 타입으로 정의되어 있다면 시작 주소에 커서를 놓고 `C`(Clear Code Bytes)로 Undefined 상태로 되돌린다.

**4) String 타입으로 수동 지정**

시작 주소에 커서를 놓고 우클릭 → **Data → Choose Data Type...**(또는 단축키 `T` 이후 타입 검색)에서 `string`(ASCII, null-terminated) 또는 `unicode`를 선택한다. 길이를 자동으로 잡지 못하면 원하는 범위를 먼저 드래그로 선택한 뒤 같은 메뉴를 실행한다.

**5) ASCII Strings Analyzer 다시 돌리기**

개별 수동 정의 대신 전체를 다시 스캔하고 싶다면 **Analysis → Auto Analyze '<파일명>'...**에서 **ASCII Strings**만 체크한 채로 재분석하거나, Analysis 메뉴의 One Shot 항목에서 ASCII Strings를 즉시 재실행한다.

**6) 최소 길이 설정 확인**

ASCII Strings Analyzer 옵션(Analysis Options 창에서 ASCII Strings 항목 클릭 시 우측에 나오는 세부 옵션)에서 최소 문자열 길이(minimum string length) 값을 확인하고, 짧은 문자열도 잡고 싶다면 값을 낮춘 뒤 재분석한다.

**7) 문자열 정의 후 XREF 재확인**

문자열을 정의한 뒤에는 `X`(Cross-references)로 그 문자열을 참조하는 코드가 있는지 확인한다. XREF가 여전히 없다면 참조 방식이 직접 주소 참조가 아니라 계산된 주소(간접 참조)일 수 있다(REV-0790 참고).

## 명령어/단축키
```text
G                              Go To — 주소로 이동
C                              Clear Code Bytes — 기존 정의 해제
T 또는 우클릭 → Data → Choose Data Type...   문자열/데이터 타입 수동 지정
Analysis → Auto Analyze ...    ASCII Strings 재실행(One Shot 포함)
X                              Cross-references — 문자열 참조 확인
Window → Defined Strings       전체 문자열 목록 창
```

## 출력 해석
- 수동으로 `string` 타입을 지정한 뒤 Listing에 `"S3cr3t_P4ss"`처럼 실제 텍스트가 보이면 정의에 성공한 것이다.
- 지정했는데도 이상한 글자가 섞여 나오면 인코딩(ASCII vs 유니코드)을 잘못 골랐을 가능성이 크므로 `unicode` 타입으로 다시 시도한다.
- Defined Strings 창에 새로 나타난 문자열의 XREF 컬럼이 0이면, 코드에서 이 문자열의 주소를 직접 쓰지 않는다는 뜻 — 오프셋 계산이나 테이블을 통해 간접적으로 쓰일 가능성을 염두에 둔다.

## 흔한 실수
- Defined Strings 창이 비어 있다고 해서 바이너리에 문자열이 없다고 단정하는 것 — Hex 뷰로 먼저 실제 존재 여부를 확인해야 한다.
- 이미 다른 타입(예: 배열)으로 정의된 영역 위에 바로 String 타입을 지정하려다 실패하는 것 — 먼저 `C`로 정의를 해제해야 한다.
- 유니코드(UTF-16) 문자열에 ASCII 타입을 지정해서 글자 사이에 널 바이트가 섞여 이상하게 보이는 것.
- 최소 길이 설정 때문에 짧은 문자열이 원래부터 안 잡힌다는 사실을 모르고 계속 재분석만 반복하는 것.

## 막혔을 때 다음 체크
- 문자열은 찾았는데 그 문자열을 쓰는 검증 함수로 어떻게 가는지 모르겠다면 → REV-0163.
- 문자열 XREF가 하나도 안 잡히는데 실제로는 간접 참조로 쓰이는 것 같다면 → REV-0790.
- 문자열 주변 바이트 자체가 이상하게 보이면 Hex 뷰로 먼저 원본을 확인 → REV-0162.
- 문자열뿐 아니라 함수/코드 인식 전반이 이상하면 → REV-0781(Auto Analysis).

## 미니 예제
`strings` 명령으로 바이너리에서 `"Login_Success_Key"`라는 문자열을 확인했지만, Ghidra `Defined Strings` 창에는 안 보이는 상황이다.

1. Hex 뷰나 파일 오프셋 계산으로 해당 텍스트의 가상 주소(예: `0x00403010`)를 구한다.
2. `G` → `0x00403010` 입력해 이동. Listing에 회색 `??` Undefined 바이트로 보인다.
3. 시작 주소에 커서를 놓고 우클릭 → Data → Choose Data Type... → `string` 선택.
4. Listing에 `"Login_Success_Key"`가 정의된 문자열로 표시된다.
5. `X`로 참조를 확인하니 `check_license` 함수에서 이 문자열을 비교에 사용하는 것을 발견한다.

## 관련 글
- REV-0163 — 문자열에서 검증 함수로 이동하는 정적 분석
- REV-0790 — 함수가 어디서 호출되는지 Xref로 안 잡힐 때(간접 호출)
- REV-0162 — Hex View로 디컴파일 결과 검증하기
- REV-0157 — Ghidra Auto Analysis 옵션

## 출처/검증
- ASCII Strings Analyzer의 동작(길이 임계값, 기존 정의 위 미실행), `Defined Strings` 창, 수동 `Choose Data Type`을 통한 string/unicode 지정: Ghidra 공식 Help 문서(ASCII Strings Analyzer, Defined String View 토픽) 기준.
- 라이브 환경에서 모든 인코딩 케이스를 직접 재현 검증하지는 않았으며, 공식 문서와 통상적인 사용 경험을 기준으로 정리했다. 최소 길이 기본값은 Ghidra 버전에 따라 다를 수 있다.
