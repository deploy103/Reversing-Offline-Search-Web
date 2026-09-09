---
id: REV-0816
title: "x64dbg Conditional Log Breakpoint 활용하기"
slug: "rev-0816-x64dbg-conditional-log-breakpoint"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["x64dbg Log condition", "x64dbg Log text", "x64dbg 조건부 로그", "x64dbg 브레이크포인트 로깅", "x64dbg printf 브레이크포인트", "x64dbg 문자열 포매팅"]
aliases: ["x64dbg 로그 브레이크포인트", "x64dbg 조건부 로그 중단점", "x64dbg dprintf 대응 기능", "x64dbg 멈추지 않는 브레이크포인트"]
symptom_keywords: ["x64dbg에서 멈추지 않고 값만 찍고 싶음", "x64dbg Log condition이 뭔지 모름", "x64dbg 문자열 포매팅 문법 모름", "x64dbg Log 탭에 아무것도 안 남음", "x64dbg 반복문 안 값 변화를 계속 보고 싶음"]
source_ids: ["SRC-X64DBG-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Conditional Log Breakpoint는 `Edit breakpoint` 대화상자의 **Log condition**과 **Log text**만 채우고 Break condition은 `0`(절대 멈추지 않음)으로 둬서, 프로그램을 멈추지 않고도 특정 지점에 도달할 때마다 원하는 값을 문자열로 포매팅해 Log 탭에 계속 찍히게 만드는 활용법이다.

## 언제 검색해야 하나
- 반복문 안에서 특정 값이 매번 어떻게 바뀌는지 흐름을 보고 싶은데, 매번 멈춰서 F9를 누르는 건 너무 느릴 때
- GDB의 `dprintf`(REV-0820)처럼 "멈추지 않는 로그용 브레이크포인트"가 x64dbg에도 있는지 궁금할 때
- 여러 값(레지스터, 메모리, 문자열)을 한 줄의 로그 텍스트로 조합해서 남기고 싶을 때
- 특정 조건일 때만 골라서 로그를 남기고 싶을 때(예: 특정 인덱스, 특정 스레드에서만)
- Break condition과 Log condition을 헷갈려서 의도치 않게 매번 멈추고 있을 때

## 핵심 개념

### Break condition과 Log condition은 완전히 독립적이다
REV-0183에서 다뤘듯 x64dbg의 모든 브레이크포인트는 Break condition, Log condition, Command condition 세 가지를 독립적으로 가진다. 이 문서에서 다루는 활용법의 핵심은 다음 조합이다.

- **Break condition = `0`** → 이 브레이크포인트는 **절대로 프로그램을 멈추지 않는다.**
- **Log condition = `1`**(또는 원하는 조건) → 이 조건이 참일 때마다 **Log text를 평가해서 Log 탭에 출력만 한다.**

즉 이 브레이크포인트는 실행 흐름에는 전혀 개입하지 않고, 마치 소스 코드에 `printf` 디버그 출력을 미리 심어 놓은 것과 같은 효과를 낸다. GDB의 `dprintf`(REV-0820)와 목적이 동일하다.

### Log text의 문자열 포매팅 문법
Log text에는 x64dbg의 문자열 포매팅 문법으로 레지스터/메모리/문자열 값을 끼워 넣을 수 있다. 중괄호 안에 `타입:표현식` 형태로 적는다.

- `{r:eax}` — 레지스터 `EAX`의 값을 16진수로 표시
- `{d:eax}` — `EAX`를 10진수로 표시
- `{p:cip}` — 현재 명령어 주소(포인터 형태)
- `{s:edx}` — `EDX`가 가리키는 주소의 ANSI 문자열을 읽어서 출력
- `{u:edx}` — `EDX`가 가리키는 주소의 유니코드(UTF-16) 문자열을 읽어서 출력
- `{x:[rsp]}` — 메모리 역참조 값을 표시하는 식으로, 조건식 문법과 동일한 표현식을 타입 지정자와 함께 조합 가능

이 포맷 문자열은 조건부 브레이크포인트에서 쓰던 표현식 문법(REV-0183)을 그대로 활용하므로, `[rsp+8]`, `mem.valid(eax)` 같은 표현도 로그 텍스트 안에서 함께 쓸 수 있다.

### 조건을 좁혀서 로그 양 조절하기
`Log condition = 1`로 두면 그 지점을 지날 때마다 무조건 로그가 쌓여서 순식간에 수천 줄이 될 수 있다. 특정 상황에서만 로그를 보고 싶다면 Log condition 자체에 조건을 건다.

```text
ecx > .50 && ecx < .60
```

이렇게 하면 `ECX`가 50~59 사이일 때만 로그가 남아, 전체 반복 중 관심 있는 구간만 골라서 확인할 수 있다.

### Command condition과 조합해 카운터 자동 증가 등도 가능
Log 출력 외에 조건이 참일 때 자동으로 스크립트 명령을 실행하고 싶다면 Command condition/Command text도 함께 채울 수 있다. 다만 REV-0183에서 언급했듯 `run`처럼 실행 상태를 직접 바꾸는 명령은 이 자리에서 불안정할 수 있으므로 피하고, 값 기록이나 변수 갱신 같은 부수 효과 없는 명령 위주로 쓴다.

### Trace의 조건부 로깅과의 차이
REV-0815에서 다룬 Trace 탭의 조건부 트레이싱도 로그 조건/로그 텍스트를 지원하지만, 그건 "Trace Into/Over로 여러 스텝을 자동 진행하는 동안"의 로깅이다. 반면 이 문서의 Conditional Log Breakpoint는 **평소처럼 프로그램을 그냥 `F9`(Run)로 자유롭게 실행하는 동안**, 지정한 그 한 지점을 지날 때마다 로그만 조용히 쌓이는 방식이다. "특정 한두 지점을 계속 감시하고 싶다"면 이 방법이, "특정 구간 전체의 실행 경로를 훑어야 한다"면 Trace 쪽이 더 적합하다.

## 화면/코드에서 보이는 징후
- 이 방식으로 설정한 브레이크포인트가 걸린 줄도 화면에는 여전히 빨간 원으로 보이지만, `F9`로 실행해도 프로그램이 실제로는 멈추지 않고 계속 흘러간다.
- Log 탭에 지정한 포맷대로 값이 실행 순서대로 계속 쌓인다.
- Breakpoints 탭의 Hit count는 계속 올라가는데 화면은 멈추지 않는다 — 이게 정상 동작이다.
- Log text 안의 포맷 문법이 틀리면(예: 잘못된 타입 지정자) 로그 줄에 값 대신 오류나 빈 문자열이 찍힌다.

## 가장 먼저 할 것
로그로 남기고 싶은 값이 정확히 무엇인지(레지스터인지, 메모리 문자열인지, 몇 번째 인자인지) 먼저 정한다. 그 다음 일반 브레이크포인트로 한 번 멈춰서 실제로 그 표현식이 원하는 값을 제대로 가리키는지 Watch 창이나 커맨드 바에서 `? EXPR`로 미리 확인해보면 로그 문법 오류를 크게 줄일 수 있다.

## 단계별 절차

**1) 로그를 남기고 싶은 위치에 브레이크포인트 걸기**

`F2`로 원하는 줄에 소프트웨어 브레이크포인트를 건다.

**2) Edit breakpoint 열기**

그 줄 우클릭 → `Breakpoint → Edit breakpoint`.

**3) Break condition을 0으로**

Break condition 입력란에 `0`을 입력한다. 이제 이 브레이크포인트는 절대 멈추지 않는다.

**4) Log condition과 Log text 채우기**

Log condition은 `1`(항상 로그) 또는 원하는 조건을 넣는다. Log text에는 포매팅 문법으로 원하는 값을 조합한다.

```text
[strcmp] rcx={p:rcx} str={s:rcx} rdx={p:rdx} str2={s:rdx}
```

**5) 확인 후 그냥 실행**

대화상자를 닫고 `F9`(Run)로 프로그램을 평소처럼 실행한다. 프로그램은 멈추지 않고 끝까지(또는 다음 진짜 브레이크포인트까지) 흘러가며, 그 사이 Log 탭에 값이 계속 쌓인다.

**6) Log 탭에서 결과 검토**

Log 탭을 스크롤하며 어떤 인자로 몇 번이나 그 지점을 지났는지, 각 시점의 값이 무엇이었는지 확인한다. Log 탭 내용은 우클릭으로 파일에 저장하거나 클립보드로 복사할 수 있다.

## 명령어/단축키
- 우클릭 → `Breakpoint → Edit breakpoint` : 조건/로그 편집 대화상자
- Break condition = `0` : 항상 멈추지 않음
- Log condition = `1` 또는 표현식 : 로그를 남길지 여부
- Log text : `{r:REG}`, `{d:REG}`, `{p:EXPR}`, `{s:EXPR}`, `{u:EXPR}` 등 포매팅 문법
- `bplog 주소, "텍스트"` 계열 커맨드로도 동일한 설정을 명령어로 지정 가능(대화상자 없이 스크립트에서 자동화할 때 유용)
- Log 탭 우클릭 → `Copy`/`Clear`/`저장` : 로그 내용 관리

## 출력 해석
- Log 탭에 한 줄도 안 쌓인다면 Log condition이 계속 거짓으로 평가되고 있거나, 애초에 그 지점에 실행이 도달하지 않고 있다는 뜻이다. 일반 브레이크포인트(Break condition을 다시 `1`로)로 잠깐 바꿔서 그 지점에 실제로 도달하는지부터 확인한다.
- `{s:...}`로 문자열을 찍었는데 이상한 문자가 나온다면, 실제로는 유니코드(UTF-16) 문자열인데 ANSI 타입 지정자를 썼을 가능성이 높다 — `{u:...}`로 바꿔본다.
- 로그가 너무 많이(수만 줄) 쌓여서 찾기 힘들다면 Log condition에 조건을 추가해 관심 구간만 남도록 좁힌다.

## 흔한 실수
- Break condition을 `0`으로 바꾸는 걸 깜빡하고 `1`(기본값)로 둔 채 Log만 설정해서, 로그도 남고 매번 멈추기까지 하는 경우 — 목적이 "멈추지 않고 로그만"이라면 반드시 Break condition을 `0`으로 명시해야 한다.
- Log text 안에서 타입 지정자를 빠뜨리고 그냥 `{eax}`처럼 쓰는 것 — 반드시 `{r:eax}`, `{d:eax}`처럼 타입을 지정해야 올바르게 해석된다.
- 문자열 인자를 감시할 때 그 시점에 레지스터가 아직 유효한 포인터를 가리키지 않는 경우(함수 진입 직후가 아니라 진입 전 등)를 확인 없이 로그를 걸어서 이상한 값이 찍히는 경우 — 인자가 세팅된 정확한 시점(보통 함수 시작 첫 줄)에 걸어야 한다.
- 로그 양을 조절하지 않고 장시간 실행해서 Log 탭이 감당 못 할 만큼 쌓여 x64dbg 자체가 느려지는 경우 — 조건으로 범위를 좁히거나, 필요하면 로그를 파일로 내보내고 Log 탭은 주기적으로 `Clear`한다.
- Command condition에 상태를 바꾸는 명령을 넣어서 Log 목적의 브레이크포인트가 부작용을 일으키는 경우 — 순수 로깅 목적이라면 Command condition/Command text는 비워둔다.

## 막혔을 때 다음 체크
- Break condition 표현식 문법 자체가 헷갈리면 → REV-0183 x64dbg 조건부 Breakpoint 기초를 먼저 본다.
- 이 지점 하나가 아니라 특정 구간 전체의 실행 경로를 훑어야 한다면 → REV-0815 x64dbg Trace 기능으로 실행 흐름 기록하기가 더 적합하다.
- 로그로 확인한 값을 기반으로 더 복잡한 자동 분기/반복 로직이 필요하다면 → REV-0814 x64dbg 스크립트(Script) 탭으로 자동화하기를 참고한다.
- GDB 환경에서 같은 개념을 쓰고 싶다면 → REV-0820 GDB dprintf로 로그만 찍고 계속 실행하기를 참고한다.

## 미니 예제
`strcmp` 계열 함수가 몇 번이나, 어떤 문자열로 호출되는지 멈추지 않고 전부 기록하는 상황이다.

```text
1. bp msvcrt.strcmp 로 브레이크포인트 설정 (또는 F2로 직접)
2. 우클릭 → Edit breakpoint
3. Break condition: 0
4. Log condition: 1
5. Log text: strcmp(a="{s:rcx}", b="{s:rdx}")
6. OK 후 F9로 프로그램을 평소처럼 실행 (한 번도 멈추지 않음)
7. Log 탭에 strcmp(a="admin", b="guest") 같은 줄이 호출될 때마다 계속 쌓임
8. 프로그램 종료 후 Log 탭을 스크롤하며 실제 비교된 모든 문자열 쌍을 한 번에 검토
```

## 관련 글
- REV-0183 — x64dbg 조건부 Breakpoint 기초
- REV-0815 — x64dbg Trace 기능으로 실행 흐름 기록하기
- REV-0814 — x64dbg 스크립트(Script) 탭으로 자동화하기
- REV-0820 — GDB dprintf로 로그만 찍고 계속 실행하기
- REV-0178 — x64dbg Breakpoint 설정과 삭제

## 출처/검증
- Break condition/Log condition/Command condition 3분 구조와 Break condition을 `0`으로 두면 절대 멈추지 않는다는 동작: 공식 문서 help.x64dbg.com의 Conditional Breakpoints 페이지(`introduction/ConditionalBreakpoint.html`) 기준(2026-09-09 조사).
- Log text 문자열 포매팅 문법(`{r:...}`, `{d:...}`, `{p:...}`, `{s:...}`, `{u:...}` 등 타입 지정자 기반 표현식 삽입): 공식 문서 Expressions/Formatting 페이지 기준.
- 이 문서의 "Break condition=0 + Log condition/Log text" 조합 자체는 공식 문서에 정확히 이 명칭("Conditional Log Breakpoint")으로 실려 있는 활용 패턴은 아니며, 공식 문서가 설명하는 세 가지 조건 필드의 독립적 동작을 조합한 실전 활용 예시이므로 실습 환경에서 직접 확인을 권장한다.
