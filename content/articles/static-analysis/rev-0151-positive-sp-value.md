---
id: REV-0151
title: "IDA Positive SP Value Has Been Detected 경고"
slug: "rev-0151-positive-sp-value"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["positive sp value", "positive sp value has been detected", "SP-analysis failed", "stack pointer", "IDA 경고"]
aliases: ["sp value 경고", "포지티브 sp", "스택 언밸런스 경고", "IDA 스택 에러"]
symptom_keywords: ["IDA에서 이상한 경고가 뜸", "디컴파일이 이상하게 나옴", "함수가 이상하게 잘림", "sp 분석 실패"]
source_ids: []
last_verified: "2026-09-08"
---

## 한 줄 요약
"Positive SP value has been detected"는 IDA가 함수 안에서 **스택 포인터(SP/ESP/RSP) 변화량을 추적하다가 CALL 이후 스택이 원래보다 더 얕아진(양수 오프셋) 상태를 발견했다**는 경고이며, 대부분 호출 규약을 잘못 추론했거나 함수 원형(인자 개수/스택 정리 방식)을 잘못 인식한 것이 원인이다.

## 언제 검색해야 하나
- IDA 하단 Output window에 `sub_401230: positive sp value has been detected`가 출력될 때
- 이 경고가 뜬 함수의 디컴파일(F5) 결과가 이상하게 끊기거나, 지역 변수/인자가 뒤죽박죽으로 보일 때
- 특히 32비트(x86) `stdcall`/`cdecl` 바이너리에서 자주 발생

## 핵심 개념
IDA는 각 함수를 분석할 때 함수 시작부터 끝까지 **SP(스택 포인터)의 변화량을 명령어 단위로 계산**한다. `push`는 SP를 감소시키고, `pop`은 증가시키며, `call`은 리턴 시 호출자가 인자를 정리하는 방식(cdecl)인지 피호출자가 정리하는 방식(stdcall)인지에 따라 SP 변화가 달라진다. 함수가 끝나는 시점(RET)에서 SP는 함수가 시작될 때와 정확히 같아야 정상이다(스택 균형, stack balance).

**"positive"의 의미**: IDA 내부적으로 함수 시작 시점의 SP를 0(기준점)으로 놓고 추적한다. 정상이라면 함수 안에서 SP delta는 0 이하로만 움직이다가(스택에 뭔가를 push해서 임시로 내려갔다가) 다시 0으로 돌아와야 한다. 그런데 IDA가 계산한 delta가 **0보다 커지는(양수가 되는)** 순간이 있으면, 이는 "함수 시작 시점보다 스택이 더 위로(더 얕게) 올라갔다"는 뜻이고, 이는 논리적으로 이상한 상태이므로 경고를 낸다.

**가장 흔한 원인**:
1. **호출 규약(calling convention) 오판** — 예를 들어 실제로는 `cdecl`(호출자가 인자를 정리해야 함)인데 IDA가 `stdcall`(피호출자가 정리)로 추론해서, CALL 이후 IDA가 "이미 정리됐겠지"라고 예상한 만큼 SP를 되돌렸는데 실제 코드는 추가로 `add esp, N`을 한 번 더 실행하는 경우.
2. **함수 원형(인자 개수)을 잘못 지정** — 가변 인자 함수(`printf`류)나 사용자가 직접 함수 타입을 잘못 지정한 경우.
3. **인라인 어셈블리나 컴파일러가 생성한 비표준 스택 조작** — 최적화된 코드에서 스택을 예상 밖의 방식으로 다루는 경우.
4. **점프 테이블/예외 처리 코드로 인해 실제로는 실행되지 않는 경로를 IDA가 함수의 일부로 잘못 포함**시킨 경우.

이 경고가 뜨면 IDA는 해당 지점 이후의 SP 추적을 포기하거나 강제로 보정하기 때문에, 그 이후 코드의 지역 변수 오프셋 계산이 틀어져서 디컴파일 결과가 깨지거나 이상한 변수 이름/오프셋이 나오게 된다.

## 화면/코드에서 보이는 징후
- IDA Output window(화면 하단 로그 창)에 `함수이름: positive sp value has been detected` 메시지
- 해당 함수를 F5로 디컴파일했을 때 지역 변수가 `a1`, `a2` 대신 이상한 오프셋(`v45`, `unknown_libname_1` 등)으로 표시되거나 코드가 중간에 끊김
- 그래프 뷰(Graph view)에서 함수의 노드 배치가 이상하게 겹치거나 잘림

## 가장 먼저 할 것
경고가 뜬 함수 이름과 정확한 주소를 Output window에서 확인한다. 그다음 그 함수로 이동해서, 함수 원형(특히 인자 개수와 호출 규약)이 IDA 자동 추론과 실제 코드가 일치하는지부터 비교한다.

## 단계별 절차

**1) 경고 위치 특정**

Output window(단축키 없으면 View → Output window)에서 경고 메시지를 찾고, 함수 이름을 더블클릭하거나 직접 그 함수로 이동한다.

**2) 스택 포인터 델타 창으로 원인 지점 찾기**

디스어셈블리 뷰에서 왼쪽 여백에 SP 델타 값이 표시되도록 설정되어 있다면(Options → General → Disassembly → "Line prefixes" 활성화), 함수를 위에서 아래로 훑으며 delta가 예상과 다르게 튀는 지점을 찾는다. 보통 특정 `call` 직후에서 튄다.

**3) 문제의 CALL 확인**

그 CALL이 호출하는 함수의 원형을 확인한다:
- 만약 그 함수가 IDA가 알아서 이름 붙인 라이브러리 함수(예: `_printf`)라면, 실제 호출 규약(cdecl vs stdcall)이 맞는지 확인.
- 사용자 정의 함수라면, 함수 위에서 Y(Set item type / Edit function)로 함수 원형과 호출 규약을 직접 확인/수정한다.

**4) 함수 원형을 수동으로 고정**

문제 함수 시작 부분에서 커서를 두고 **Y** (또는 Edit → Functions → Edit function)를 눌러 "Edit function" 대화상자를 연다. Calling convention 드롭다운에서 실제 맞는 규약(`__cdecl`, `__stdcall` 등)으로 바꾸고, 필요하면 "Number of purged bytes(스택 정리 바이트 수)"를 수동으로 입력한다.

**5) SP 델타 수동 보정**

특정 명령어 위치에서 우클릭 → **"Change stack pointer"** (또는 Edit → Functions → Define stack variables 근처 메뉴)를 선택해서, 그 지점 이후의 SP 델타를 수동으로 원하는 값으로 고정할 수 있다. 이는 IDA가 스스로 잘못 계산한 부분을 사람이 정정해주는 방법이다.

**6) 함수 재분석**

수정 후 함수 시작 주소에서 우클릭 → **"Reanalyze function"** (또는 함수를 삭제(U)했다가 다시 코드로 만들기(C))를 실행해서 IDA가 새 정보로 다시 분석하게 한다.

## 명령어/단축키
- IDA: Output window 확인, `Y` (함수/변수 타입 편집), 명령어 우클릭 → "Change stack pointer", 함수 시작 주소 우클릭 → "Reanalyze function"
- 함수를 통째로 재정의: `U`(Undefine) → 커서를 함수 시작에 놓고 `P`(Create function) 또는 `C`(Code)

## 출력 해석
- `positive sp value has been detected`만 뜨고 그 뒤에 구체적 오프셋이 없으면, Output window 위쪽 줄에 실제 얼마나 어긋났는지(`SP-analysis failed` 등 관련 메시지)가 함께 있는 경우가 많으니 로그를 위아래로 스크롤해서 확인한다.
- 이 경고 자체는 **오류가 아니라 경고**다. 즉 IDA는 계속 분석을 진행하지만, 그 이후 코드의 지역 변수 매핑 정확도가 떨어질 수 있다는 신호로 받아들이면 된다.

## 흔한 실수
- 경고를 무시하고 디컴파일 결과를 그대로 믿는 것 — 이 경고가 뜬 함수는 변수 이름/오프셋이 실제와 다를 수 있으므로, 중요한 함수라면 반드시 어셈블리 원문과 대조해야 한다.
- 호출 규약을 고치지 않고 계속 F5만 다시 누르는 것 — 근본 원인(함수 원형 오판)을 고치지 않으면 몇 번을 다시 디컴파일해도 동일하게 깨진다.
- 32비트 바이너리에서 이 경고가 유독 잦다는 걸 모르고 64비트와 똑같이 접근하는 것 — x86에서는 호출 규약(cdecl/stdcall/fastcall)이 스택 정리 방식 자체를 바꾸기 때문에 훨씬 민감하다. x64는 대부분 호출자가 정리하는 방식이 통일되어 있어 이 문제가 상대적으로 적다.

## 막혔을 때 다음 체크
- 여러 번 수동 보정해도 계속 깨진다면 → 함수 경계 자체가 잘못 잡혔을 가능성(REV-0154, 예정)을 의심.
- 디컴파일이 아예 실패(Decompilation failed)한다면 → REV-0152(IDA Decompiler Failed가 뜰 때, 예정) 참고.
- 이 함수가 예외 처리(SEH)나 최적화로 생성된 비표준 코드라면 → 어셈블리 레벨에서 직접 읽는 것으로 전환하고, 디컴파일 결과는 참고용으로만 사용.

## 미니 예제
32비트 cdecl 함수를 IDA가 stdcall로 착각한 상황을 단순화하면:
```asm
push    10h          ; 인자 push
push    offset aFmt  ; 인자 push
call    _printf       ; cdecl이므로 호출자가 정리해야 함
add     esp, 8        ; 호출자가 직접 스택 정리 (cdecl의 특징)
```
IDA가 만약 `_printf`를 잘못된 정보로 stdcall(피호출자가 정리)로 인식했다면, `call _printf` 시점에 이미 스택이 정리됐다고 가정하고 SP를 계산한다. 그런데 실제로는 그 다음 줄 `add esp, 8`이 스택을 한 번 더(추가로) 정리하므로, IDA 관점에서는 스택이 예상보다 더 많이 줄어든 것으로 보이고, 이후 델타 계산이 어긋나면서 결국 함수 어딘가에서 delta가 양수로 튀는 상황이 발생할 수 있다. 이 경우 `_printf`가 실제로는 가변인자 cdecl 함수임을 확인하고 원형을 바로잡으면 해결된다.

## 관련 글
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0152 — IDA Decompiler Failed가 뜰 때
- REV-0153 — IDA Stack Pointer 분석이 틀렸을 때
- REV-0123 — Windows x86 stdcall cdecl fastcall thiscall (예정)

## 출처/검증
- IDA SP-analysis 및 "positive sp value" 경고: Hex-Rays 공식 포럼/문서(SP-analysis failed 관련 troubleshooting 자료) 및 IDA 자체 Output window 실제 메시지 문구 기준 (2026-09-08 검증).
- cdecl/stdcall 스택 정리 책임 차이: Microsoft Learn "Argument Passing and Naming Conventions" 문서 기준.
