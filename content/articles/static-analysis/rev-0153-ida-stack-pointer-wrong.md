---
id: REV-0153
title: "IDA Stack Pointer 분석이 틀렸을 때"
slug: "rev-0153-ida-stack-pointer-wrong"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["stack pointer analysis", "SP-analysis failed", "fuzzy sp", "change stack pointer", "esp 이상함", "rsp 이상함", "stack frame size wrong"]
aliases: ["스택 포인터 분석 오류", "SP 추적 실패", "스택 프레임 크기 이상함", "esp rsp 꼬임"]
symptom_keywords: ["스택 다 깨짐", "지역변수 오프셋이 이상함", "함수 Locals 크기가 말이 안 됨", "esp 계산이 안 맞음", "스택 정렬 명령어 때문에 꼬임", "변수가 겹쳐 보임"]
source_ids: ["SRC-HEXRAYS-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
경고 문구가 없더라도 지역 변수 오프셋이 뒤죽박죽이거나 Functions 창의 함수 크기(Locals)가 비정상적으로 크거나 작게 보인다면 **IDA의 SP(스택 포인터) 추적이 어딘가에서 실패한 것**이며, 대부분 `and esp, -16` 같은 수동 스택 정렬·비표준 프롤로그·꼬리 호출(tail call)처럼 IDA가 자동으로 이해하지 못하는 스택 조작이 원인이므로 Alt+K(Change stack pointer)로 해당 지점의 SP 델타를 직접 알려주는 것이 핵심 해결책이다.

## 언제 검색해야 하나
- "positive sp value has been detected/found" 라는 정확한 문구가 뜬 게 아니라, 그냥 디컴파일 결과의 지역 변수 위치가 이상하거나 겹쳐 보일 때 (정확히 그 경고 문구를 검색해서 왔다면 REV-0151을 먼저 볼 것)
- IDA Functions 창(Ctrl+P)에서 어떤 함수의 "Locals"(지역 변수용 스택 크기) 열 값이 말도 안 되게 크거나(수만 바이트) 음수처럼 보일 때
- `and esp, 0FFFFFFF0h` 같은 스택 정렬 명령어가 있는 함수에서 디컴파일/스택 변수 뷰가 깨질 때
- 최적화된 릴리스 빌드, FPO(Frame Pointer Omission) 함수, 꼬리 호출(tail call)이 있는 함수를 분석할 때

## 핵심 개념
IDA는 함수를 분석하면서 각 명령어가 SP(x86의 ESP, x64의 RSP)를 얼마나 바꾸는지 명령어 단위로 시뮬레이션한다. `push`/`pop`/`sub esp, N`/`add esp, N`/`call`처럼 IDA가 이미 알고 있는 패턴은 정확히 추적하지만, IDA의 사전 지식 밖에 있는 방식으로 스택이 바뀌면 추적이 어긋난다. IDA는 이렇게 추적을 계속할 수 없는 상태를 내부적으로 **"fuzzy-sp"**(스택 값이 불확실함)로 표시하고, 그 이후 오프셋 계산은 신뢰할 수 없게 된다.

REV-0151에서 다룬 "positive sp value has been detected/found" 경고는 이 문제의 **한 가지 구체적인 증상**(SP 델타가 시작점보다 커짐)일 뿐이다. 이번 글은 그 경고 문구가 뜨지 않아도 스택 추적이 깨지는 **더 넓은 범위의 상황들**을 다룬다.

**IDA가 스택 추적에 실패하는 흔한 원인들**:
1. **수동 스택 정렬(stack alignment)** — `and esp, 0FFFFFFF0h`처럼 AND 연산으로 스택을 16바이트 경계에 맞추는 코드. 이 연산은 esp의 정확한 값을 뺄셈/덧셈이 아니라 비트 마스킹으로 바꾸므로, IDA 입장에서는 "esp가 정확히 얼마나 줄었는지" 계산할 수 없다. 이런 함수는 IDA가 자동으로 fuzzy-sp로 표시하고 추적을 포기한다.
2. **비표준 함수 프롤로그** — 컴파일러 최적화로 `push ebp; mov ebp, esp` 같은 표준 프롤로그가 생략된 경우(FPO, Frame Pointer Omission). 프레임 포인터가 없으면 IDA가 오직 SP 추적에만 의존해서 지역 변수 위치를 계산하는데, 최적화된 코드는 SP를 예측하기 어려운 방식으로 다루는 경우가 많다.
3. **꼬리 호출(tail call) 최적화** — 함수 끝에서 `call` 대신 `jmp target`으로 다른 함수로 점프하며 실제로는 반환하는 패턴. IDA가 이걸 별개의 두 함수로 인식하지 못하거나, 반대로 하나의 함수 안에 있어야 할 코드로 착각해서 SP 계산이 꼬일 수 있다.
4. **손으로 짠 인라인 어셈블리** — 컴파일러가 생성하지 않는 임의의 스택 조작(예: 직접 `push`/`pop` 균형을 맞추지 않는 셸코드, 트램폴린 코드).
5. **인터럽트/예외 핸들러, SEH 관련 스텁** — 일반적인 호출 규약을 따르지 않는 특수 코드.

## 화면/코드에서 보이는 징후
- Pseudocode에서 지역 변수가 `v4`, `v18` 같은 이름으로 나오는데, 실제 로직상 말이 안 되게 겹치거나 크기가 이상해 보임(예: 4바이트 정수인데 오프셋 간격이 200바이트씩 벌어짐)
- Functions 창(Ctrl+P)에서 해당 함수의 "Locals"/"Frame" 관련 열이 비정상적으로 큰 값(수만~수십만)이거나 이상하게 작음
- 디스어셈블리 왼쪽 여백에 SP 델타 표시를 켰을 때(Options → General → Disassembly → "Line prefixes"), 특정 명령어 이후로 델타가 `?`나 이상한 값으로 표시되거나 더 이상 갱신되지 않음
- Output window에 `positive sp value` 외에도 `SP-analysis failed`, 또는 아무 메시지 없이 그냥 스택 변수 뷰가 비정상인 경우

## 가장 먼저 할 것
문제 함수의 디스어셈블리를 처음부터 훑으며 `and esp`, `esp`/`rsp`에 직접 대입하는 명령어, 또는 표준 `push ebp; mov ebp, esp` 프롤로그가 없는지부터 눈으로 확인한다. SP 델타 표시(Line prefixes)를 켜두면 어느 명령어부터 추적이 깨지는지 시각적으로 바로 보인다.

## 단계별 절차

**1) SP 델타 표시 켜기**

Options → General → Disassembly 탭에서 "Line prefixes"를 켜면 디스어셈블리 각 줄 왼쪽에 그 시점의 SP 델타 값이 표시된다. 이 값이 예상과 다르게 튀거나 멈추는 지점을 찾는다.

**2) 원인 명령어 확인**

찾은 지점의 명령어가 다음 중 하나인지 확인한다:
- `and esp, ...` (또는 `and rsp, ...`) 형태의 정렬 명령어
- 프롤로그가 표준적이지 않은 경우(예: `sub esp, N`만 있고 `push ebp`가 없음)
- 함수 끝의 `jmp` (call이 아니라 jmp로 다른 함수로 넘어가는 꼬리 호출)

**3) SP 값 수동 보정 (Alt+K)**

문제가 되는 명령어 위에 커서를 놓고 **Alt+K** (메뉴: Edit → Functions → Change stack pointer)를 누른다. 대화상자가 뜨면 "그 명령어 실행 직후 SP가 얼마나 변해야 하는지"를 직접 입력한다. 예를 들어 `and esp, 0FFFFFFF0h` 다음에 실제로 스택이 몇 바이트 내려갔는지 알고 있다면(디버거로 실제 값을 확인하거나, 그 뒤 `sub esp, N` 값으로 역산해서) 그 값을 입력해 IDA에게 알려준다.
- Alt+K는 커서가 어떤 함수에도 속하지 않은 위치에서는 사용할 수 없다.
- 값을 정확히 모르겠다면, 실제로 디버거(x64dbg, IDA 내장 디버거 등)로 그 함수를 한 번 실행시켜 레지스터 값을 직접 확인하는 것이 가장 확실하다.

**4) 스택 프레임 구조 보기/편집**

**Ctrl+K** (View → Open subviews → Stack frame, 또는 함수 내부에서 단축키)를 누르면 그 함수의 스택 프레임 구조(지역 변수, 저장된 레지스터, 리턴 주소 등이 오프셋별로 나열된 표)를 볼 수 있다. 여기서 변수 크기/타입/이름을 직접 조정하면 SP 보정 이후 디컴파일 결과가 더 깔끔해지는 경우가 많다.

**5) 함수 원형/호출 규약 재확인**

호출하는/호출되는 함수의 원형이 잘못되어 있으면 SP 계산도 함께 틀어진다. 문제 함수 위에서 **Y**를 눌러 원형과 호출 규약(cdecl/stdcall/fastcall 등)이 실제 코드와 맞는지 확인한다(REV-0148 참고).

**6) 재분석**

수정 후 함수 시작 주소에서 우클릭 → **Reanalyze function**을 실행하거나, **U**(Undefine) 후 커서를 함수 시작에 놓고 **P**(Create function)로 다시 만든다. 그다음 F5로 디컴파일을 다시 확인한다.

## 명령어/단축키
- `Alt+K`: Change stack pointer — 현재 명령어 위치에서 SP 값 수동 지정 (Edit → Functions → Change stack pointer)
- `Ctrl+K`: Stack frame(스택 변수) 뷰 열기/편집
- `Y`: 함수/변수 타입, 호출 규약 지정
- Options → General → Disassembly → "Line prefixes": SP 델타를 디스어셈블리 여백에 표시
- `U` → `P`: 함수 삭제 후 재생성
- 함수 시작 우클릭 → `Reanalyze function`

## 출력 해석
- SP 델타가 `?` 로 표시되거나 더 이상 갱신되지 않는다면, 그 지점부터 IDA가 "fuzzy-sp"(추적 불가) 상태로 넘어간 것이다. 그 이후의 모든 지역 변수 오프셋은 신뢰할 수 없다.
- Functions 창의 "Locals" 값이 비정상적으로 크다면(예: 4바이트 변수 몇 개뿐인데 수만 바이트로 표시), SP 추적이 함수 끝까지 제대로 안 됐다는 강한 신호다.
- Alt+K로 값을 입력한 후 그 이후 코드의 델타가 정상적인 작은 값들로 다시 안정되면 보정이 맞았다는 뜻이다. 여전히 이상한 값이 나온다면 입력한 값 자체가 틀렸거나 추가로 다른 지점에서도 보정이 필요하다.

## 흔한 실수
- `and esp, N` 같은 정렬 명령어를 보고도 "IDA가 알아서 처리하겠지"라고 넘어가는 것 — IDA는 이런 비트마스킹 방식의 스택 조작을 스스로 계산하지 못하므로 반드시 수동 개입이 필요하다.
- REV-0151의 "positive sp value" 경고만 검색하고, 경고 문구가 안 뜨는 조용한 SP 오류(그냥 변수가 이상하게 겹치는 경우)는 다른 문제라고 착각하는 것 — 둘 다 근본적으로 같은 SP 추적 실패 계열이다.
- Alt+K에 아무 근거 없이 값을 대충 입력하는 것 — 틀린 값을 넣으면 오히려 더 꼬인다. 디버거로 실제 값을 확인하거나 주변 명령어의 스택 조작량을 역산해서 넣어야 한다.
- 최적화된 릴리스 빌드에서 디버그 빌드와 동일한 표준 프롤로그를 기대하는 것 — FPO 함수는 애초에 `ebp` 기반 프레임이 없으므로 접근 방식 자체를 바꿔야 한다.

## 막혔을 때 다음 체크
- 정확히 "positive sp value has been detected/found" 라는 문구가 떴다면 → REV-0151을 먼저 확인 (더 구체적인 사례와 절차 수록)
- Alt+K로 고쳐도 디컴파일 자체가 계속 실패한다면 → REV-0152(Decompiler Failed 전반)
- 함수 크기 자체가 이상하게 크거나(두 함수가 합쳐짐) 작다면(잘림) → REV-0154(함수 경계 문제)를 먼저 의심 — SP 문제가 아니라 함수 경계 문제가 원인인 경우도 많다
- 함수 원형이나 호출 규약이 의심스럽다면 → REV-0148(Y로 타입 지정)

## 미니 예제
다음과 같은 x86 함수가 있다고 하자.
```asm
push    ebp
mov     ebp, esp
and     esp, 0FFFFFFF0h   ; 스택을 16바이트 경계로 정렬 (SIMD 지역 변수용)
sub     esp, 40h
...
mov     esp, ebp
pop     ebp
retn
```
`and esp, 0FFFFFFF0h`는 esp를 정확히 몇 바이트 줄였는지 컴파일 시점 상수로 알 수 없다(런타임 esp 값에 따라 다름). IDA는 이 지점에서 fuzzy-sp로 표시하고, 이후 `sub esp, 40h`로 만들어지는 지역 변수 40h바이트 블록의 절대 위치 계산이 불안정해진다. 다행히 이 함수는 끝에서 `mov esp, ebp`로 esp를 ebp 기준으로 복원하므로(정렬 이전 상태로 되돌림) 실제 실행에는 문제가 없지만, IDA의 정적 추적은 중간 구간에서 깨질 수 있다. 이런 경우 `and esp` 명령어 다음 줄에 커서를 놓고 Alt+K로 "이 시점 이후 SP 델타는 0으로 취급"처럼 명시적으로 알려주면 그 이후 지역 변수 오프셋 계산이 안정된다.

## 관련 글
- REV-0151 — IDA Positive SP Value Has Been Detected 경고
- REV-0152 — IDA Decompiler Failed가 뜰 때
- REV-0154 — IDA에서 함수 경계가 잘못 잡혔을 때
- REV-0148 — IDA Y로 타입 지정하기
- REV-0146 — IDA F5 디컴파일과 Pseudocode 읽기

## 출처/검증
- `Alt+K`(Change stack pointer, Edit → Functions → Change stack pointer)와 "fuzzy-sp" 개념, `and esp, -16` 류의 수동 정렬이 fuzzy-sp를 유발한다는 내용은 Hex-Rays 공식 블로그 "Igor's tip of the week #27: Fixing the stack pointer"와 IDA Help 문서(Change Stack Pointer 항목) 기준이다.
- `positive sp value has been found` 오류에 대한 공식 권장 조치(Change stack pointer 사용)는 Hex-Rays 공식 문서 "Failures and troubleshooting"(IDA 8.4, docs.hex-rays.com) 기준이다.
- `Ctrl+K`(스택 프레임 뷰) 단축키는 다수의 IDA 단축키 레퍼런스 자료에서 일관되게 언급되나, 이 글 작성 시점에 실제 설치된 IDA에서 직접 재현 검증을 하지는 못했다. IDA 버전에 따라 스택 프레임 뷰 접근 방식(Subview 메뉴 경로 등)이 달라졌을 수 있으므로, 실제 사용 중인 버전에서 View → Open subviews 메뉴를 통해 재확인할 것을 권장한다.
