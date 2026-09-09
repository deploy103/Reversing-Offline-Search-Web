---
id: REV-0849
title: "조건부 브레이크포인트 표현식이 항상 false로 평가될 때"
slug: "rev-0849-conditional-breakpoint-always-false"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg]
keywords: ["조건부 브레이크포인트 안걸림", "condition 명령어", "GDB condition", "x64dbg break condition"]
aliases: ["조건부 브레이크포인트가 안먹힘", "condition이 항상 거짓", "브레이크포인트 조건식 오류"]
symptom_keywords: ["condition을 걸었는데 한번도 안 걸린다", "eax==값인데 안멈춘다", "조건식이 맞는것 같은데 통과된다", "break if 조건이 안먹는다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
조건부 브레이크포인트가 "절대" 안 걸리는 경우, 조건식 자체의 논리 오류보다 **레지스터 크기 불일치, 부호 있음/없음 혼동, 값이 아직 그 시점에 만들어지지 않음, 문자열을 포인터 값으로 비교함** 같은 "평가 시점/표현 방식" 문제가 대부분이다.

## 언제 검색해야 하나
- `break FUNC if CONDITION` 또는 x64dbg의 조건부 브레이크포인트를 걸었는데 실제로 그 조건이 참일 게 분명한 상황에서도 멈추지 않을 때
- 무조건 브레이크포인트(`break FUNC`)는 걸리는데 조건을 추가하는 순간부터 전혀 안 걸릴 때
- 반복 호출되는 함수에서 "이번 값이 0x1337일 때만" 같은 조건을 걸고 싶은데 원하는 순간에 멈추지 않을 때

## 핵심 개념

### 레지스터 폭 불일치
`$eax == 0x1337`처럼 32비트 레지스터로 비교했는데 실제 값은 상위 32비트에 쓰레기 값이 섞인 64비트 레지스터(`$rax`)로 다뤄지는 경우, 또는 반대로 함수가 값을 `AL`(8비트)에만 넣었는데 `$eax` 전체와 비교하면 상위 바이트의 잔여값 때문에 항상 다르게 나온다. GDB는 `$eax`를 쓰면 자동으로 하위 32비트만 비교하지만, x64dbg의 조건식 문법은 레지스터 별칭을 정확히 구분해서 써야 한다.

### 부호 있음/없음 혼동
`$eax == -1`처럼 음수로 비교했는데 조건식 평가기가 이를 부호 없는 값(`0xFFFFFFFF`)으로 해석하거나 그 반대인 경우, 겉보기엔 같은 값인데도 비교가 항상 실패한다. GDB에서는 `(int)$eax == -1`처럼 명시적으로 캐스팅하면 확실해진다.

### 조건을 평가하는 "시점"이 값이 만들어지기 전
`break check_password if input[0] == 'A'`를 함수 진입 지점에 걸면, 그 시점엔 아직 인자가 스택/레지스터에 다 세팅되기 전(프롤로그 실행 전)일 수 있어 `input`이 쓰레기 값을 가리킨다. 프롤로그가 끝난 다음 줄(첫 실제 명령어)에 걸어야 인자가 정상적으로 보인다.

### 포인터 값과 문자열 내용의 혼동
`buf == "flag"`처럼 쓰면 대부분의 디버거는 이를 "포인터 값과 문자열 리터럴의 메모리 주소를 비교"하는 것으로 처리해 버려서, 문자열 내용이 실제로 "flag"여도 항상 거짓이 된다. 내용 비교가 필요하면 `strcmp(buf, "flag") == 0`처럼 함수 호출 형태의 조건식을 GDB에서 직접 평가시켜야 한다(단, 함수 호출형 조건은 평가할 때마다 대상 함수를 실제로 실행하므로 부작용이 있을 수 있다는 점도 감안해야 한다).

### 지역 변수 스코프 밖에서 참조
조건식에 그 브레이크포인트 위치의 스코프 밖에 있는 지역 변수명을 그대로 썼다면, GDB는 "No symbol in current context" 에러를 내야 정상인데, 최적화된 빌드에서는 같은 이름의 다른 변수(예: 이전 스택 프레임에 남은 값)를 우연히 읽어 항상 예상과 다른 값이 나올 수 있다.

## 화면/코드에서 보이는 징후
- GDB에서 `condition N EXPR` 또는 `break ... if ...`를 걸어도 `continue`를 몇 번을 눌러도 안 멈춤
- x64dbg에서 브레이크포인트 우클릭 → Edit breakpoint의 조건식(Break condition)을 채웠는데 실행이 그냥 끝까지 진행됨
- `print CONDITION`으로 직접 평가해보면 항상 `false`/`0`이 나옴

## 가장 먼저 할 것
조건식을 브레이크포인트에 걸어두지 말고, 먼저 **무조건 브레이크포인트**로 그 지점에 멈춘 뒤 조건식을 수동으로 `print`(GDB) 또는 워치 창(x64dbg)에 직접 평가해서 실제 값과 타입을 눈으로 확인한다.
```gdb
(gdb) break FUNC
(gdb) run
(gdb) print $eax
(gdb) print (int)$eax == 0x1337
```

## 단계별 절차

**1) 무조건 브레이크포인트로 실제 값 확인**
```gdb
(gdb) break check_password
(gdb) run
(gdb) print input
(gdb) print *input
(gdb) print input[0]
```
값의 타입과 실제 내용을 먼저 확인한다.

**2) 조건식을 그 자리에서 직접 평가**
```gdb
(gdb) print input[0] == 'A'
$1 = false
```
`false`가 나오면 무엇이 다른지(대소문자, 부호, 자료형) 하나씩 좁혀본다.

**3) 레지스터 폭/캐스팅 명시**
```gdb
(gdb) condition 1 (int)$eax == -1
```

**4) 조건 위치를 프롤로그 이후로 이동**
```gdb
(gdb) break *(check_password+10)
```
`disassemble check_password`로 프롤로그(`push rbp; mov rbp, rsp; sub rsp, ...`)가 끝나는 주소를 확인한 뒤 그 다음 주소에 건다.

**5) 문자열 내용 비교가 필요하면 strcmp 사용**
```gdb
(gdb) break strcmp if strcmp((char*)$rdi, "flag") == 0
```

**6) x64dbg에서는 레지스터 별칭과 자료형 크기를 맞춰서 조건식 작성**
```
[eax] == 1337        // 메모리 역참조 시 대괄호 문법 확인
eax == 1              // 레지스터 직접 비교
```
x64dbg 조건식 문법은 C 표현식과 다르게 `==` 대신 필요 시 `=`를 쓰는 버전도 있으므로, Help 아이콘이나 상태표시줄에 뜨는 문법 힌트를 반드시 확인한다.

## 명령어/단축키
```gdb
(gdb) condition N EXPR
(gdb) break FUNC if EXPR
(gdb) print EXPR
(gdb) disassemble FUNC
(gdb) break *(FUNC+OFFSET)
```
```
x64dbg: 브레이크포인트 우클릭 → Edit breakpoint → Break condition
x64dbg: Log condition으로 조건이 어떻게 평가되는지 로그만 먼저 남겨보기
```

## 출력 해석
- `print EXPR`이 `$1 = false`(또는 `0`) → 조건식 자체가 실제 상황과 안 맞는 것. 값과 타입을 다시 확인.
- `No symbol "input" in current context` → 그 위치에서는 아직/이미 그 변수가 스코프 밖. 브레이크포인트 위치를 옮겨야 함.
- `print`가 세그폴트를 유발하며 값이 이상하게 나옴 → 포인터가 아직 초기화 전. 프롤로그 이후로 이동.

## 흔한 실수
- `$eax`와 `$al`/`$ax`를 구분 안 하고 전체 32/64비트로 비교해서 상위 비트 쓰레기값 때문에 항상 실패하는 것.
- 문자열 포인터를 문자열 리터럴과 `==`로 비교해 놓고 왜 안 걸리는지 모르는 것 — 반드시 `strcmp` 호출형 조건이 필요하다.
- 함수 진입 주소(프롤로그 시작)에 조건을 걸어서 인자 레지스터/스택이 아직 안 세팅된 상태를 조건에 넣는 것.
- 조건식 문법을 GDB식(C 표현식)과 x64dbg식을 혼동해서 쓰는 것 — 둘의 조건식 문법은 다르다.

## 막혔을 때 다음 체크
- 조건부 브레이크포인트 기본 문법 자체가 헷갈린다면 → REV-0183 x64dbg 조건부 Breakpoint 기초.
- GDB의 `condition`/`ignore`/`commands` 조합을 더 깊게 쓰고 싶다면 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak).
- CALL 직전 인자 레지스터 값을 정확히 확인하는 법이 궁금하다면 → REV-0175 CALL 직전 함수 인자 확인하는 법.

## 미니 예제
```gdb
(gdb) break check_password if input == "1337"
(gdb) run
# 전혀 안 멈춤 — input은 char* 포인터이고 "1337"은 별도 메모리의 문자열 리터럴이라 주소 비교가 되어버림

(gdb) break check_password
(gdb) run
(gdb) print input
$1 = 0x7fffffffe420 "1337"
(gdb) delete 1
(gdb) break check_password if strcmp(input, "1337") == 0
(gdb) continue
Breakpoint 2, check_password (input=0x7fffffffe420 "1337") at chall.c:20
```
`==`로 포인터를 비교하던 첫 시도는 절대 걸리지 않았고, `strcmp` 호출로 바꾸자 즉시 걸렸다.

## 관련 글
- REV-0183 — x64dbg 조건부 Breakpoint 기초
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)
- REV-0175 — CALL 직전 함수 인자 확인하는 법

## 출처/검증
- GDB 조건식 평가(`condition`, `break ... if`)와 표현식 문법: GDB 공식 매뉴얼 "Break Conditions" 섹션 기준.
- x64dbg 브레이크포인트 조건식 문법: x64dbg 공식 문서(Conditional breakpoints) 기준 (2026-09-09 검증).
