---
id: REV-0851
title: "워치포인트가 걸려야 하는데 한 번도 안 걸릴 때"
slug: "rev-0851-watchpoint-never-triggers"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB]
keywords: ["watch 안걸림", "워치포인트 안먹힘", "하드웨어 워치포인트 슬롯 부족", "스코프 벗어남"]
aliases: ["워치포인트가 트리거되지 않음", "watch가 무시됨", "값이 바뀌는데 안멈춤"]
symptom_keywords: ["값이 분명히 바뀌는데 watch가 안걸린다", "워치포인트를 걸었는데 그냥 지나가버린다", "watchpoint deleted 메시지가 뜬다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
값이 분명히 바뀌는 것 같은데 `watch`가 걸리지 않는다면, 대부분 **감시 대상이 스코프를 벗어나 워치포인트가 조용히 삭제됐거나**, **값이 레지스터에만 머물고 메모리에는 실제로 안 쓰이거나**, **하드웨어 워치포인트 슬롯이 부족해 설정 자체가 실패했거나**, **감시 중인 주소가 ASLR/재컴파일로 이미 바뀌었기** 때문이다.

## 언제 검색해야 하나
- 변수 값이 화면상 분명히 바뀌었는데(다시 확인해보면 New value) `watch`가 한 번도 안 걸렸을 때
- 지역 변수에 `watch`를 걸었는데 함수가 리턴한 뒤 아무 알림 없이 그냥 넘어갈 때
- `watch`를 여러 개 걸었더니 그중 일부가 조용히 무시되는 것 같을 때
- 재실행할 때마다 워치포인트가 걸리다 안 걸리다 반복될 때

## 핵심 개념

### 지역 변수 스코프를 벗어나면 자동 삭제됨
지역 변수에 건 워치포인트는 그 변수가 존재하는 스택 프레임이 사라지면(함수가 리턴하면) GDB가 자동으로 삭제한다. 이때 `Watchpoint N deleted because the program has left the block...` 메시지가 뜨긴 하지만, 스크롤에 묻혀 놓치기 쉽다. 다음 반복에서 같은 이름의 지역 변수가 다시 생겨도 이미 삭제된 워치포인트는 자동으로 되살아나지 않는다.

### 값이 레지스터에만 있고 메모리에 안 쓰인다
컴파일러 최적화로 인해 변수가 스택/전역 메모리에 저장되지 않고 레지스터에만 머무는 경우, `watch`(메모리 주소 기반)는 그 변경을 감지할 수 없다. 이 경우는 REV-0854(스택에서 원하는 값이 안 보일 때)와 원인이 같다 — 애초에 메모리 위치가 없다.

### 하드웨어 워치포인트 슬롯 소진
x86 계열 CPU는 보통 디버그 레지스터(DR0~DR3) 4개만 제공하므로, 워치포인트를 4개 넘게 걸면 일부는 설정 자체가 실패하거나 `Hardware watchpoints not available` 에러가 나면서 조용히 동작하지 않을 수 있다.

### ASLR/재컴파일로 주소가 바뀜
`watch *(int*)0x404060`처럼 절대 주소로 걸었는데, PIE 바이너리라 실행할 때마다 베이스 주소가 바뀌거나 재컴파일로 오프셋이 바뀌면 그 주소는 더 이상 원하는 변수를 가리키지 않는다.

### 조건식이 틀려서 항상 통과됨
워치포인트에 `condition`을 걸었는데 조건식 자체가 틀려서(REV-0849 참고) 값은 바뀌었지만 조건이 항상 거짓으로 평가돼 멈추지 않는 경우도 많다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) watch local_flag
Hardware watchpoint 3: local_flag
(gdb) continue
Watchpoint 3 deleted because the program has left the block in
which its expression is valid.
0x0000000000401278 in main () at chall.c:20
```
이후 아무리 `continue`해도 다시 안 걸림 — 스코프를 벗어나 이미 삭제됐기 때문.

## 가장 먼저 할 것
`info watchpoints`로 워치포인트가 지금도 살아 있는지부터 확인한다. 목록에 없으면 이미 삭제된 것이고, 있으면 조건식이나 주소가 잘못됐다는 뜻이다.
```gdb
(gdb) info watchpoints
No watchpoints.
```

## 단계별 절차

**1) 워치포인트 생존 여부 확인**
```gdb
(gdb) info watchpoints
```
목록에 없다면 스코프 이탈로 삭제됐거나 애초에 설정이 실패한 것이다.

**2) 지역 변수라면 전역/힙 주소 기준으로 다시 걸기**
지역 변수 자체 대신, 그 값이 저장되는 더 상위 스코프의 구조체 필드나 전역 변수를 감시 대상으로 바꾼다. 또는 함수에 진입할 때마다 자동으로 다시 `watch`를 걸도록 브레이크포인트에 `commands`를 연결한다.
```gdb
(gdb) break check_input
(gdb) commands
> watch local_flag
> continue
> end
```
함수에 진입할 때마다 새로 워치포인트를 건다.

**3) 값이 레지스터에만 있는지 확인**
```gdb
(gdb) info locals
```
`<optimized out>`으로 나오거나 애초에 이름이 안 보이면 메모리에 안 실린 것이다. `-O0`로 다시 컴파일된 디버그 빌드가 있다면 그걸로 재현하거나, 레지스터 값을 직접 스텝 단위로 추적한다(REV-0172 참고).

**4) 하드웨어 워치포인트 슬롯 확인**
```gdb
(gdb) watch a
(gdb) watch b
(gdb) watch c
(gdb) watch d
(gdb) watch e
Hardware watchpoints not available
```
필요 없는 워치포인트를 `delete`로 정리하거나, 우선순위가 낮은 것을 `rwatch`/`awatch` 대신 조건부 브레이크포인트로 대체한다.

**5) PIE/ASLR 환경이면 절대 주소 대신 심볼/오프셋 기준으로 걸기**
```gdb
(gdb) watch g_flag        # 심볼 이름 기준(권장)
(gdb) watch *(int*)($rbp - 0x14)   # 실행 중 계산된 상대 주소
```
절대 주소 하드코딩은 피한다.

**6) 조건식 재검토**
`condition`을 걸었다면 REV-0849 절차대로 조건식을 직접 `print`로 평가해 값과 타입을 재확인한다.

## 명령어/단축키
```gdb
(gdb) info watchpoints
(gdb) info locals
(gdb) watch EXPR
(gdb) break FUNC
(gdb) commands ... watch ... continue ... end
```

## 출력 해석
- `Watchpoint N deleted because the program has left the block...` → 스코프 이탈로 자동 삭제. 정상 동작이며, 다음 반복에서 다시 걸어야 한다.
- `Hardware watchpoints not available` → 슬롯 소진. 기존 워치포인트를 정리해야 한다.
- `info locals`에서 `<optimized out>` → 메모리에 없는 값. `watch` 대상이 될 수 없다.
- `info watchpoints`가 `No watchpoints.`인데 분명히 걸었었다면, 스코프 이탈이나 슬롯 부족으로 조용히 사라진 것이니 위 절차로 원인을 좁힌다.

## 흔한 실수
- 지역 변수에 건 워치포인트가 함수 리턴과 함께 자동 삭제된다는 사실을 모르고, 다음 호출에서 "왜 안 걸리지"라고 헷갈리는 것.
- 최적화 빌드에서 변수가 레지스터에만 있다는 사실을 확인하지 않고 계속 같은 방식으로 `watch`를 재시도하는 것.
- PIE 바이너리에서 한 번 확인한 절대 주소를 재실행 후에도 그대로 재사용하는 것.
- 워치포인트 4개를 다 채워놓고 5번째가 실패하는 걸 놓친 채 "이상하게 하나만 안 걸린다"고 헷갈리는 것.

## 막혔을 때 다음 체크
- 반대로 너무 자주 걸려서 문제라면 → REV-0850 워치포인트가 너무 자주 걸려서 못 쓸 때.
- 값이 레지스터에만 있어서 스택에서 안 보이는 문제라면 → REV-0854 스택에서 원하는 값이 안 보일 때(레지스터에만 있을 때).
- ASLR로 라이브러리/베이스 주소가 계속 바뀌는 문제라면 → REV-0714 동적분석 중 ASLR 때문에 라이브러리 베이스 주소가 계속 바뀔 때.
- 워치포인트 기본 문법이 헷갈린다면 → REV-0191 GDB watchpoint 기초.

## 미니 예제
```gdb
(gdb) break check_input
(gdb) run
(gdb) next
(gdb) watch local_result
Hardware watchpoint 3: local_result
(gdb) continue
Watchpoint 3 deleted because the program has left the block in
which its expression is valid.
0x0000000000401278 in main () at chall.c:22
```
`local_result`가 함수 안에서 분명히 바뀌었을 텐데도 다음 `continue`에서 아무 알림이 없었던 이유는, `check_input`이 이미 리턴하면서 워치포인트가 스코프 이탈로 삭제됐기 때문이다. 함수 진입 지점에 `commands`로 재설정 루틴을 걸어 해결했다.

## 관련 글
- REV-0850 — 워치포인트가 너무 자주 걸려서 못 쓸 때
- REV-0714 — 동적분석 중 ASLR 때문에 라이브러리 베이스 주소가 계속 바뀔 때
- REV-0191 — GDB watchpoint 기초

## 출처/검증
- 지역 변수 워치포인트의 스코프 이탈 자동 삭제 동작과 하드웨어 워치포인트 슬롯 제한: GDB 공식 매뉴얼 "Setting Watchpoints" 섹션 기준.
- 최적화된 빌드에서 변수가 레지스터에만 존재해 메모리 기반 워치포인트로 감지 불가능한 현상: GDB 매뉴얼 "Variables" 챕터(`<optimized out>` 설명) 기준 (2026-09-09 검증).
