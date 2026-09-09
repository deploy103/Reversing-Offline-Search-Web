---
id: REV-0819
title: "GDB에서 조건부 브레이크포인트(condition) 활용하기"
slug: "rev-0819-gdb-conditional-breakpoint-condition"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB]
keywords: ["gdb condition", "gdb break if", "gdb 조건부 브레이크포인트", "gdb condition -force", "gdb ignore", "gdb 브레이크포인트 조건식"]
aliases: ["gdb 조건 중단점", "gdb break if 문법", "gdb condition 명령어", "gdb 조건식 활용", "gdb 반복문 조건 탐색"]
symptom_keywords: ["gdb 브레이크포인트가 너무 자주 걸림", "gdb break if 문법 모름", "gdb condition 명령이 안 먹힘", "gdb 반복문 안 특정 값일 때만 멈추고 싶음", "gdb condition -force가 뭔지 모름"]
source_ids: ["SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
GDB의 `condition N EXPR`(또는 브레이크포인트를 걸 때 바로 `break LOCATION if EXPR`)은 지정한 표현식이 참(0이 아님)일 때만 그 브레이크포인트에서 실제로 멈추게 만드는 기능으로, 반복문 안에서 원하는 조건 하나만 콕 집어 멈추고 싶을 때 `continue`를 수백 번 치는 것을 대체한다.

## 언제 검색해야 하나
- 반복 호출되는 비교 함수(`strcmp`, `memcmp` 등)에서 특정 인자/인덱스일 때만 멈추고 싶을 때
- `break` 시점에 조건식을 바로 같이 걸고 싶은데 `break LOCATION if EXPR` 문법을 정확히 몰라서 헷갈릴 때
- 이미 걸어둔 브레이크포인트에 나중에 조건을 추가하거나, 조건을 완전히 지우고 싶을 때
- 조건식에 함수 호출(`strlen(...)` 등)을 넣었더니 GDB가 이상하게 느려지거나 함수 호출이 안전한지 궁금할 때
- `ignore`와 `condition`을 같이 쓰는 법이 궁금할 때

## 핵심 개념

### 두 가지 조건 지정 방법
GDB에서 조건부 브레이크포인트를 거는 방법은 크게 두 가지다.

**1) 브레이크포인트를 걸면서 바로 조건 지정**
```gdb
break check_password if idx == 5
break *0x401234 if $rax == 0x1337
```
`break LOCATION if EXPR` 형태로, 브레이크포인트를 생성하는 시점에 조건까지 한 줄로 끝낸다.

**2) 이미 있는 브레이크포인트에 나중에 조건 붙이기**
```gdb
break check_password
condition 1 idx == 5
```
`condition N EXPR`에서 `N`은 `break`가 걸릴 때 알려주는 브레이크포인트 번호(`info breakpoints`로도 확인 가능)다. 이미 걸어둔 브레이크포인트를 지우지 않고 조건만 나중에 추가하거나 바꿀 수 있어서, 실전에서는 이 방식을 더 자주 쓰게 된다.

### 조건을 지우는 법
`condition N`처럼 표현식 없이 번호만 주면, 그 브레이크포인트의 조건이 제거되고 다시 무조건 멈추는 상태로 돌아간다.
```gdb
condition 1
```

### condition -force — 위험한 표현식도 강제로 걸기
조건식에 오타가 있거나, 그 시점에는 아직 유효하지 않은 변수를 참조하면 GDB는 보통 에러를 내고 조건을 걸지 않는다. `-force` 옵션을 주면 GDB가 표현식을 지금 당장 검증하지 않고 일단 그대로 등록한다.
```gdb
condition -force 1 some_var_not_yet_valid == 1
```
이건 "지금은 이 변수가 아직 스코프에 없지만, 나중에 이 지점에 도달했을 때는 유효할 것"이라고 확신할 때 쓰는 옵션이다. 무분별하게 쓰면 매번 평가 실패로 조용히 항상 멈춰버릴 수 있으니 주의한다.

### 조건식 안에서 함수 호출도 가능하다
GDB의 조건식은 C에 가까운 표현식 평가기를 그대로 쓰기 때문에, 디버기(대상 프로그램) 안의 함수를 직접 호출하는 것도 가능하다.
```gdb
break strcmp
condition 1 strlen((char*)$rdi) > 5
```
이 조건은 "`strcmp`가 호출될 때마다, 첫 번째 인자 문자열의 길이가 5보다 클 때만 멈춰라"는 뜻이다. 다만 **조건식 안에서 함수를 호출하면 그때마다 실제로 대상 프로그램 안에서 그 함수가 실행된다** — 부작용이 있는 함수(전역 상태를 바꾸는 함수 등)를 조건식에 넣으면 프로그램 동작 자체가 바뀔 수 있으므로, 가능하면 부작용 없는 순수 함수만 조건식에서 호출하는 것이 안전하다.

### 조건식은 매 히트마다 평가된다 — 성능 고려
조건이 걸린 브레이크포인트는 그 위치에 도달할 때마다 **반드시 조건식을 평가**한 뒤에야 멈출지 말지를 결정한다. 단순 비교(`eax == 1`)라면 무시할 만한 비용이지만, 조건식에 함수 호출이나 복잡한 메모리 역참조가 들어가면 그 지점을 지나칠 때마다 그 계산 비용이 매번 들어간다. 아주 뜨거운(hot) 반복문 안에 무거운 조건을 걸면 프로그램이 체감될 정도로 느려질 수 있다.

### ignore와의 조합 — "조건은 맞지만 몇 번째부터"
`ignore N COUNT`는 조건과는 별개로 "브레이크포인트를 앞으로 COUNT번은 무조건 무시하라"는 명령이다. 조건과 조합하면 "조건이 참인 경우 중에서도 3번째부터"처럼 더 세밀하게 좁힐 수 있다.
```gdb
condition 1 idx == 5
ignore 1 2
```
이렇게 하면 `idx == 5`를 만족하는 히트가 3번째로 발생할 때부터 실제로 멈춘다(처음 2번은 조건을 만족해도 무시 카운트가 먼저 소모된다).

### tbreak와 condition을 함께 쓰기
한 번만 조건부로 멈추고 이후 자동으로 삭제되게 하고 싶다면 `tbreak`(임시 브레이크포인트)에도 조건을 걸 수 있다.
```gdb
tbreak check_password if idx == 5
```

## 화면/코드에서 보이는 징후
- `break LOCATION if EXPR`로 걸면 브레이크포인트 생성 메시지 다음에 별도 알림 없이 바로 조건이 적용된 상태다.
- `info breakpoints`로 목록을 보면 각 브레이크포인트 아래에 `stop only if EXPR` 줄이 표시되어, 현재 어떤 조건이 걸려 있는지 확인할 수 있다.
- 조건이 거짓으로 평가되는 동안은 `continue`를 쳐도 화면에 별다른 출력 없이 프로그램이 계속 실행되다가, 조건이 참이 되는 순간에만 멈춘 위치와 소스 줄이 출력된다.
- 조건식에 문법 오류가 있으면 `condition` 명령 자체에서 즉시 에러 메시지가 나온다(`-force`를 쓰지 않는 한).

## 가장 먼저 할 것
멈추고 싶은 정확한 조건(어떤 변수가 어떤 값일 때인지)을 먼저 `print`로 실제 값을 확인하며 표현식을 검증한다. 예를 들어 `p idx`, `p $rdi`로 그 시점의 실제 타입과 값을 본 뒤 조건식을 작성하면 문법 오류나 타입 캐스팅 실수를 줄일 수 있다.

## 단계별 절차

**1) 위치와 조건을 함께 걸기**
```gdb
break check_password if idx == 5
```

**2) 이미 건 브레이크포인트에 조건 추가/변경**
```gdb
info breakpoints
condition 2 idx == 5
```

**3) 조건 제거**
```gdb
condition 2
```

**4) 함수 호출이 들어간 조건 걸기**
```gdb
break strcmp
condition 1 strlen((char*)$rdi) > 5
```

**5) ignore와 조합해 몇 번째 히트부터 멈출지 좁히기**
```gdb
condition 1 idx == 5
ignore 1 2
```

**6) 실행하고 확인**
```gdb
run
```
조건을 만족하는 정확한 순간에만 멈춘 것을 `bt`, `p idx`로 확인한다.

## 명령어/단축키
```gdb
break LOCATION if EXPR      # 생성과 동시에 조건 지정
tbreak LOCATION if EXPR     # 1회용 브레이크포인트 + 조건
condition N EXPR            # 기존 브레이크포인트 N에 조건 부여/변경
condition N                 # 조건 제거(무조건 멈춤으로 복귀)
condition -force N EXPR     # 지금 당장 검증 안 되는 표현식도 강제로 등록
ignore N COUNT               # 조건과 무관하게 앞으로 COUNT번은 무시
info breakpoints             # 각 브레이크포인트의 조건(stop only if ...) 확인
delete N                     # 브레이크포인트 자체 삭제
```

## 출력 해석
`info breakpoints` 출력 예:
```
Num     Type           Disp Enb Address            What
1       breakpoint     keep y   0x0000000000401196 in check_password at chall.c:40
        stop only if idx == 5
        breakpoint already hit 1 time
```
`stop only if idx == 5` 줄이 현재 걸려 있는 조건을 그대로 보여준다. `breakpoint already hit N time`은 **조건을 만족해서 실제로 멈춘 횟수**이지, 그 지점을 지나간 전체 횟수가 아니라는 점에 주의한다(전체 통과 횟수를 보고 싶다면 `dprintf`나 로그 방식이 더 적합하다 — REV-0820 참고).

## 흔한 실수
- `break LOCATION if EXPR`에서 `if` 앞뒤 공백을 빠뜨리거나, 여러 조건을 괄호 없이 `&&`로 길게 이어서 우선순위를 헷갈리는 것.
- 조건식에 아직 스코프에 들어오지 않은 지역 변수를 참조해서 매번 평가 에러가 나는데, 이를 무시하고 `-force`부터 쓰는 것 — 먼저 그 변수가 정말 그 시점에 유효한지 `break` 위치 자체를 재검토해야 한다.
- 조건식에 부작용이 있는 함수 호출을 넣어서, 조건을 평가하는 것만으로 프로그램 상태(전역 변수, 파일 포인터 등)가 바뀌어 버그를 만드는 것 — 조건식은 최대한 순수 함수/단순 비교로 구성한다.
- 아주 자주 실행되는 위치에 함수 호출이 포함된 무거운 조건을 걸어서 프로그램이 체감될 정도로 느려지는 것 — 가능하면 조건을 단순 정수/포인터 비교로 좁히고, 복잡한 판단은 조건이 걸린 뒤 수동으로 확인한다.
- `condition N EXPR`과 `break N if EXPR`을 혼동해서 이미 존재하는 브레이크포인트 번호에 `break`를 다시 쓰려다 새로운 브레이크포인트가 하나 더 생기는 것 — 기존 것을 바꾸려면 반드시 `condition`을 쓴다.

## 막혔을 때 다음 체크
- `watch`/`catch`/`tbreak`/`dprintf` 등 GDB의 다른 정지 방식들과 비교해서 어떤 걸 써야 할지 헷갈리면 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak)를 참고한다.
- 멈추지 않고 조건에 맞을 때 로그만 남기고 싶다면 → REV-0820 GDB dprintf로 로그만 찍고 계속 실행하기가 더 적합할 수 있다.
- 조건이 맞는 순간 이전 상태로 되돌려서 원인을 더 거슬러 올라가고 싶다면 → REV-0821 GDB reverse debugging 개념 소개(record/replay)를 참고한다.
- 애초에 브레이크포인트 기본 사용법 자체가 헷갈리면 → REV-0186 GDB break와 address breakpoint를 먼저 본다.

## 미니 예제
입력 문자열을 한 글자씩 비교하는 반복문에서, 인덱스 7일 때만 멈춰서 그 시점의 비교 대상을 확인하는 상황이다.

```gdb
(gdb) break compare_char if i == 7
Breakpoint 1 at 0x4011a0: file chall.c, line 22.
(gdb) run
Starting program: /home/user/chall

Breakpoint 1, compare_char (i=7, c='k') at chall.c:22
22          if (input[i] != key[i]) return 0;
(gdb) p key[i]
$1 = 107 'k'
(gdb) p input[i]
$2 = 106 'j'
```
`i == 7`일 때만 정확히 멈췄고, 그 시점에 기대값(`key[i]`)과 실제 입력값(`input[i]`)이 다르다는 것을 바로 확인했다 — 나머지 인덱스 0~6, 8 이후는 조건이 거짓이라 한 번도 멈추지 않고 그냥 지나갔다.

## 관련 글
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)
- REV-0820 — GDB dprintf로 로그만 찍고 계속 실행하기
- REV-0821 — GDB reverse debugging 개념 소개(record/replay)
- REV-0186 — GDB break와 address breakpoint
- REV-0191 — GDB watchpoint 기초

## 출처/검증
- `break LOCATION if EXPR`, `condition N EXPR`, `condition N`(조건 제거), `condition -force`, `ignore N COUNT` 명령의 구문과 동작: GDB 공식 온라인 매뉴얼("Debugging with GDB") "Break Conditions" 및 "Setting Breakpoints"/"Break, Watch, and Catchpoint Settings" 섹션 기준(2026-09-09 조사).
- 조건식 안에서 대상 프로그램의 함수를 호출할 수 있다는 점과 부작용 관련 주의사항: GDB 매뉴얼의 "Break Conditions" 섹션 및 "Calling Program Functions" 섹션의 일반적인 설명에 근거.
- `info breakpoints` 출력의 `stop only if EXPR` 표기와 `breakpoint already hit N time`이 조건을 만족해 실제로 멈춘 횟수를 의미한다는 점: GDB 매뉴얼 "Break Conditions" 및 "Set Breaks" 섹션 기준.
