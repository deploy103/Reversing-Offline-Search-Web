---
id: REV-0808
title: "x64dbg 조건부 브레이크포인트 문법 참조"
slug: "rev-0808-x64dbg-conditional-breakpoint-syntax-quickref"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["x64dbg break condition", "x64dbg breakpointcounter", "x64dbg 조건부 브레이크포인트 레시피", "x64dbg 히트카운트 조건", "x64dbg 스레드 조건"]
aliases: ["x64dbg 조건부 브레이크포인트 표", "x64dbg break condition 패턴", "x64dbg 조건식 예시 모음"]
symptom_keywords: ["x64dbg 조건부 브레이크포인트 예시가 필요함", "x64dbg 몇 번째 히트에서만 멈추고 싶음", "x64dbg 특정 스레드에서만 멈추고 싶음", "x64dbg 문자열 조건 어떻게 쓰는지 모름", "x64dbg 조건이 계속 참으로 나옴"]
source_ids: ["SRC-X64DBG-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
x64dbg 브레이크포인트의 Break condition 입력란에는 REV-0806에서 다루는 표현식 문법을 그대로 쓸 수 있으며, 실전에서 자주 필요한 조건(값 비교/히트 횟수/스레드/메모리/문자열)은 몇 가지 정해진 패턴으로 거의 다 해결된다.

## 언제 검색해야 하나
- Break condition 칸에 뭘 써야 할지 몰라서 예시부터 베껴 쓰고 싶을 때
- "N번째 히트에서만 멈추기", "특정 스레드에서만 멈추기" 같은 자주 쓰는 패턴의 정확한 문법이 기억 안 날 때
- 조건을 걸었는데 매번 멈추거나, 반대로 전혀 안 멈춰서 정답 패턴과 비교하고 싶을 때

## 핵심 개념
Break condition은 결과가 **0이 아니면 멈추고, 0이면 계속 실행**되는 표현식이다. 아래 표는 실전에서 반복적으로 쓰이는 조건 패턴을 정리한 것이다.

| 목적 | Break condition 예시 | 설명 |
|---|---|---|
| 특정 값 비교 | `EAX == .1337` | EAX가 10진수 1337일 때만 멈춤(`.` 필수) |
| 두 조건 모두 참 | `EAX==.1 && ECX==.1` | AND 조합 |
| 둘 중 하나라도 참 | `EAX==0 \|\| EBX==0` | OR 조합 |
| 특정 값이 아닐 때 | `EAX != 0` | 부정 조건 |
| 스택 값 비교 | `[rsp]==0xDEADBEEF` | RSP가 가리키는 기본 크기 메모리 값 비교 |
| 스택 값 비교(크기 명시) | `dword(rsp+8)==.100` | 4바이트로 명시해서 비교(안전) |
| N번째 히트에서만 | `$breakpointcounter==.3` | 이 브레이크포인트가 3번째로 실행될 때만 |
| 매 N번째마다 | `($breakpointcounter % .3)==0` | 나머지 연산으로 주기적으로 멈춤 |
| 특정 스레드에서만 | `tid()==0x1a04` | 멀티스레드 프로그램에서 스레드 필터링 |
| 유효한 포인터일 때만 | `mem.valid(eax)` | 잘못된 주소에서 평가 에러 방지 |
| 안전한 메모리+값 조합 | `mem.valid(rax) && dword(rax)==.0` | 유효성 확인 후에만 값 비교(단축 평가) |
| 유니코드 부분 문자열 포함 | `strstr(utf16(ecx), "admin")` | ECX가 가리키는 UTF-16 문자열에 "admin" 포함 여부 |
| 절대 멈추지 않음(로그 전용) | `0` | Break condition은 항상 거짓, Log condition/Log text만 활용 |
| 항상 멈춤(기본값) | `1` | 조건 없는 일반 브레이크포인트와 동일 |

## 화면/코드에서 보이는 징후
브레이크포인트를 우클릭 → `Breakpoint` → `Edit breakpoint`를 열면 Break condition / Log condition / Command condition 세 칸이 있는 대화상자가 뜬다. 조건이 걸린 브레이크포인트도 화면의 빨간 원 표시 자체는 일반 브레이크포인트와 동일하므로, 조건이 걸려 있는지는 `Breakpoints` 탭의 조건식 열에서만 확인할 수 있다.

## 가장 먼저 할 것
원하는 조건을 "값 비교 / 히트 횟수 / 스레드 / 메모리 안전성 / 문자열" 중 어느 범주인지부터 분류한 뒤, 위 표에서 가장 가까운 패턴을 골라 값만 바꿔 넣는다.

## 단계별 절차

**1) 일반 브레이크포인트 걸기**
F2로 원하는 줄에 브레이크포인트를 건다.

**2) Edit breakpoint 열기**
그 줄 우클릭 → `Breakpoint` → `Edit breakpoint`.

**3) Break condition에 패턴 대입**
```text
$breakpointcounter==.5
```
루프 안 함수의 5번째 진입에서만 멈추고 싶을 때.

**4) 필요하면 안전장치 추가**
포인터 조건이 있다면 앞에 `mem.valid()`를 `&&`로 붙여 무효 주소 평가 오류를 막는다.
```text
mem.valid(rcx) && dword(rcx)==0x1337
```

**5) OK 후 F9로 실행하며 Hit count로 검증**
`Breakpoints` 탭의 Hit count가 늘어나는데 실제로는 안 멈춘다면 조건이 계속 거짓이라는 뜻이고, 매번 멈춘다면 조건식 문법 오류로 "항상 참" 취급되고 있다는 뜻이다.

## 명령어/단축키
```text
Edit breakpoint 열기      : 브레이크포인트 우클릭 → Breakpoint → Edit breakpoint
Break condition           : 이 값이 0이 아니면 실제로 멈춤(기본값 1)
$breakpointcounter        : 현재까지 이 브레이크포인트의 히트 횟수
tid()                     : 현재 스레드 ID
mem.valid(EXPR)           : 유효한 메모리인지 확인(단축 평가용 안전장치)
```

## 출력 해석
`Breakpoints` 탭의 Hit count는 조건과 무관하게 "이 지점을 지나간 횟수"를 계속 세고, 실제로 멈춘 횟수와 다를 수 있다. Hit count는 계속 늘어나는데 한 번도 안 멈췄다면 조건이 한 번도 참이 된 적이 없다는 뜻이므로 조건식 자체를 의심해야 한다.

## 흔한 실수
- 10진수 히트 카운트를 `$breakpointcounter==3`처럼 `.` 없이 써서 16진수 3으로 해석되는 것 — 우연히 3은 16진수/10진수가 같아 문제가 안 보이지만, `$breakpointcounter==.100`처럼 큰 수에서는 반드시 `.`을 붙여야 한다.
- `[addr]`로 직접 역참조하는 조건만 걸고 `mem.valid()` 안전장치를 빼먹어서, 조건 평가 도중 무효 주소를 만나 예외가 나는 것.
- Break condition과 Log condition을 헷갈려서 로그만 남기고 싶었는데 Break condition에 조건을 넣어 매번 멈추게 만드는 것.
- `tid()` 조건을 걸어두고 스레드가 바뀌는 걸 모른 채 "왜 이번엔 안 멈추지"라고 헷갈리는 것 — 멀티스레드 프로그램은 실행마다 스레드 ID가 다를 수 있다.

## 막혔을 때 다음 체크
- Break condition/Log condition/Command condition 구조와 대화상자 여는 법 자체가 처음이면 → REV-0183 x64dbg 조건부 Breakpoint 기초.
- 표현식에 쓸 수 있는 함수/연산자 전체 목록이 필요하면 → REV-0806 x64dbg 표현식(Expression) 문법 빠른 참조.
- 조건을 걸 지점을 아직 못 찾았다면 → REV-0179 x64dbg String References 찾기 또는 REV-0180 x64dbg Find Assembly 사용법.

## 미니 예제
```text
목표: strcmp가 10번째로 호출될 때만, 그리고 두 번째 인자(rdx)가 유효한 문자열일 때만 멈추기

1. strcmp에 F2 브레이크포인트
2. Edit breakpoint 열기
3. Break condition:
   mem.valid(rdx) && $breakpointcounter==.10
4. OK 후 F9 실행
5. 9번째 호출까지는 Hit count만 늘고 통과, 10번째에서 rdx가 유효하면 그 순간 멈춤
```

## 관련 글
- REV-0183 — x64dbg 조건부 Breakpoint 기초
- REV-0806 — x64dbg 표현식(Expression) 문법 빠른 참조
- REV-0179 — x64dbg String References 찾기
- REV-0180 — x64dbg Find Assembly 사용법

## 출처/검증
- Break condition의 참/거짓 판정 방식, `$breakpointcounter`/`tid()`/`mem.valid()`/`strstr()`/`utf16()` 함수와 `EAX==.1337`, `$breakpointcounter==3`, `tid()==1C0`, `strstr(utf16(ECX), "foo")` 계열 예시: x64dbg 공식 문서(help.x64dbg.com) Conditional Breakpoints 및 Expression Functions 페이지 기준 (2026-09-09 조사, 원문 확인).
