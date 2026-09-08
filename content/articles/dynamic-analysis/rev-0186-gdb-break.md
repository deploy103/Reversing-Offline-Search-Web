---
id: REV-0186
title: "GDB break와 address breakpoint"
slug: "rev-0186-gdb-break"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb break", "브레이크포인트", "address breakpoint", "tbreak", "조건부 브레이크포인트", "break *주소"]
aliases: ["gdb 브레이크포인트 거는법", "gdb break 명령어", "gdb 특정 주소에서 멈추기", "gdb 조건부 중단점"]
symptom_keywords: ["gdb break가 안 걸림", "break 주소를 넣었는데 반응이 없음", "gdb에서 특정 함수에서 멈추고 싶음", "breakpoint pending", "gdb 조건에서만 멈추고 싶음"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB의 `break`(단축 `b`)는 함수 이름, 파일:줄번호, 또는 `*주소` 형태의 절대/상대 주소에 실행을 멈추는 지점을 지정하는 명령으로, 조건식(`if`)이나 임시 여부(`tbreak`)까지 함께 조절할 수 있어 원하는 코드 지점에 정확히 멈춰서 상태를 확인하는 동적 분석의 출발점이다.

## 언제 검색해야 하나
- `check_password` 같은 특정 함수가 호출되는 순간에 딱 멈추고 싶은데 `break` 문법을 정확히 모를 때
- IDA에서 본 특정 주소(`0x401234`)에서 멈추고 싶은데 `break *0x401234`와 `break 0x401234`의 차이가 헷갈릴 때
- `break`를 걸었는데 `Breakpoint 1 at 0x...`는 뜨는데 실제로 그 지점에서 멈추지 않을 때
- 반복문 안에서 특정 조건(예: `i == 5`)일 때만 멈추고 싶은데 매번 수동으로 `continue`를 누르기 귀찮을 때
- 걸어둔 브레이크포인트 목록을 확인하거나 지우고 싶을 때

## 핵심 개념

### `break`의 기본 형태 세 가지
GDB의 `break`는 위치(location)를 지정하는 방식에 따라 크게 세 가지로 나뉜다.
1. **함수 이름**: `break main`, `break check_password` — 심볼 테이블에 이름이 있는 함수의 시작 지점(정확히는 프롤로그 이후, 지역 변수 공간이 확보된 직후)에 건다.
2. **파일:줄번호**: `break chall.c:42` — 소스 코드가 있고 디버그 심볼(`-g`로 컴파일)이 있을 때, 해당 줄의 첫 명령어에 건다.
3. **주소**: `break *0x401234` — **반드시 `*`(별표)를 붙여야** 그 값을 "주소"로 해석한다. 별표 없이 `break 0x401234`라고 쓰면 GDB는 이를 "현재 파일의 0x401234번째 줄"로 오해석해서 엉뚱한 곳에 걸리거나 에러가 난다. 이건 초보자가 가장 많이 저지르는 실수 중 하나다.

### 함수 이름 vs 주소 — 언제 뭘 써야 하나
함수 이름으로 거는 방식은 PIE 바이너리에서도 GDB가 알아서 런타임 베이스를 계산해주기 때문에 훨씬 안전하다. 반면 주소로 거는 방식은 정확한 지점(함수 중간의 특정 명령어 등)을 지정할 수 있다는 장점이 있다. 함수 이름 + 오프셋 조합도 가능하다:
```gdb
break *check_password+37
```
이 표현은 "`check_password` 함수 시작 주소로부터 37바이트 뒤"를 뜻하며, GDB가 심볼 기준으로 계산하므로 PIE에서도 안전하다. IDA에서 특정 명령어의 오프셋(함수 시작 기준)을 확인한 뒤 이 형태로 걸면 정확하다.

### `tbreak` — 한 번만 걸리는 임시 브레이크포인트
`tbreak`(temporary break)는 `break`와 문법이 완전히 같지만, **한 번 멈춘 뒤 자동으로 삭제**된다는 점만 다르다. 반복문 안의 특정 지점을 한 번만 보고 싶을 때, 또는 `start` 명령이 내부적으로 쓰는 것처럼 `main` 진입 후에는 더 이상 필요 없는 브레이크포인트에 유용하다.

### 조건부 브레이크포인트 — `if`
반복문 안에서 특정 조건일 때만 멈추고 싶다면 `break` 뒤에 `if 조건식`을 붙인다.
```gdb
break chall.c:42 if i == 5
break *0x401234 if $rax == 0
```
조건식에는 C와 비슷한 문법(`==`, `!=`, `>`, `&&` 등)을 쓸 수 있고, 레지스터는 `$rax`, `$rdi`처럼 `$`를 붙여서 참조한다. 이렇게 하면 조건이 맞지 않는 동안은 GDB가 자동으로 `continue`를 반복해주므로, 수십 번 `continue`를 누를 필요 없이 원하는 순간에만 멈춘다.

### 브레이크포인트 목록 확인, 비활성화, 삭제
```gdb
info breakpoints    # 또는 i b — 현재 걸린 모든 브레이크포인트 목록과 번호, 히트 횟수 확인
disable 1           # 1번 브레이크포인트를 잠깐 꺼둠(삭제는 아님)
enable 1            # 다시 켬
delete 1            # 1번 브레이크포인트 완전히 삭제
delete               # 전체 삭제
```
번호는 브레이크포인트를 걸 때마다 GDB가 순서대로 자동 부여하며(`Breakpoint 1 at ...`, `Breakpoint 2 at ...`), 이 번호로 이후 관리한다.

### 브레이크포인트가 걸린 횟수 제한 — `ignore`
반복문에서 첫 4번은 건너뛰고 5번째부터 멈추고 싶다면:
```gdb
ignore 1 4
```
1번 브레이크포인트를 4번 무시하고 5번째 히트부터 실제로 멈추게 한다. 조건식(`if i==5`)을 쓸 수 없을 만큼 조건 표현이 복잡할 때 대안으로 쓴다.

### "break가 안 걸린다"의 흔한 원인 — 아직 로드되지 않은 주소
공유 라이브러리 함수(`printf` 등)나 PIE 실행 파일 자체의 주소에 `break *주소` 형태로 걸 때, **해당 코드가 아직 메모리에 매핑되지 않은 시점**이면 GDB가 "Breakpoint N (실제 심볼 없음) pending"으로 표시하고 실행 중 그 라이브러리가 로드될 때 자동으로 활성화된다. 이건 정상 동작이지만, PIE 실행 파일 자신의 raw 주소를 실행 전에 걸었을 때는 얘기가 다르다 — 이 경우엔 애초에 주소 계산 자체가 잘못된 경우가 대부분이다(REV-0194 참고).

## 화면/코드에서 보이는 징후
- `break main` 입력 시 `Breakpoint 1 at 0x555555555185: file chall.c, line 10.`처럼 파일/줄 정보가 함께 나오면 디버그 심볼이 있다는 뜻
- 디버그 심볼이 없으면 `Breakpoint 1 at 0x555555555185`만 나오고 파일/줄 정보가 생략됨(그래도 정상 동작)
- 잘못된 주소에 걸면 `Make breakpoint pending on future shared library load? (y or [n])`처럼 물어보거나, 별표 없이 숫자를 넣었을 때 `No line 401234 in the current file.`같은 에러
- `continue` 후 브레이크포인트에 도달하면 `Breakpoint 1, main () at chall.c:10` 형태로 멈춘 위치를 보여줌

## 가장 먼저 할 것
분석하려는 지점이 이름 있는 함수라면 무조건 함수 이름으로 먼저 걸어본다(`break 함수이름`). 이름이 없는 임의의 주소(예: 특정 `cmp` 명령어 바로 앞)에서 멈춰야 한다면, 그 주소가 어느 함수의 몇 바이트 지점인지부터 확인하고 `*함수이름+오프셋` 형태로 건다.

## 단계별 절차

**1) 함수 이름으로 걸기**
```gdb
break check_password
```

**2) 히트 여부 확인하며 실행**
```gdb
run
```
(또는 이미 실행 중이면 `continue`)

**3) 정확한 명령어 지점으로 좁히고 싶다면 오프셋 사용**
```gdb
disassemble check_password
break *check_password+37
```

**4) 조건이 필요하면 `if` 추가**
```gdb
break *check_password+37 if $rax != 0
```

**5) 목록 확인 및 정리**
```gdb
info breakpoints
delete 2
```

## 명령어/단축키
```gdb
break FUNC
break *ADDR
break FILE:LINE
break *FUNC+OFFSET
break LOC if COND
tbreak LOC
info breakpoints    # i b
disable N
enable N
delete N
delete
ignore N COUNT
```

## 출력 해석
- `Breakpoint 1 at 0x555555555185`: 그 브레이크포인트에 부여된 GDB 내부 번호(1)와 실제 걸린 주소.
- `Num     Type           Disp Enb Address            What` 로 시작하는 `info breakpoints` 표에서 `Disp` 열이 `keep`이면 계속 남는 일반 브레이크포인트, `del`이면 `tbreak`로 건 임시 브레이크포인트다. `Enb` 열이 `y`면 활성, `n`이면 `disable`된 상태.
- `breakpoint already hit N time(s)`: 지금까지 이 브레이크포인트에 몇 번 도달했는지 알려준다. 반복문 안에서 몇 번째 순회인지 가늠하는 데 유용하다.

## 흔한 실수
- `break 0x401234`처럼 별표 없이 숫자만 써서 "줄 번호"로 오해석되게 만드는 것 — 반드시 `break *0x401234`.
- 아직 `run`/`start`를 하지 않은 상태에서 PIE 바이너리의 raw 실행 주소로 브레이크포인트를 걸어 엉뚱한 위치에 걸리거나 아예 안 걸리는 것(REV-0194 참고).
- 조건식 안에서 C의 `=`(대입)과 `==`(비교)를 헷갈려서 `if i = 5`처럼 쓰는 것 — GDB도 이 경우 실제로 대입을 수행해버려 의도와 다르게 동작한다.
- 브레이크포인트를 여러 개 걸어놓고 뭐가 몇 번인지 잊어버려 엉뚱한 번호를 `delete`하는 것 — 항상 `info breakpoints`로 먼저 확인하는 습관을 들인다.

## 막혔을 때 다음 체크
- 멈춘 뒤 한 명령어씩 진행하고 싶다면 → REV-0187 GDB stepi nexti continue
- 브레이크포인트 자체의 개념(소프트웨어 브레이크포인트의 원리, INT3)이 궁금하다면 → REV-0169 Breakpoint가 무엇이고 어디에 걸어야 하는가
- 특정 메모리 값이 바뀔 때 멈추고 싶다면(브레이크포인트가 아니라 워치포인트가 필요한 경우) → REV-0191 GDB watchpoint 기초
- PIE 바이너리라 주소가 매번 바뀌어서 `break *주소`가 안 걸린다면 → REV-0194 PIE 바이너리 GDB 브레이크포인트 잡기

## 미니 예제
```gdb
(gdb) break check_password
Breakpoint 1 at 0x1189: file chall.c, line 15.
(gdb) run
Starting program: /home/user/chall
Breakpoint 1, check_password (input=0x7fffffffe4a0 "test123") at chall.c:15
15          if (strcmp(input, secret) == 0) {
(gdb) info breakpoints
Num     Type           Disp Enb Address            What
1       breakpoint     keep y   0x0000555555555189 in check_password at chall.c:15
	breakpoint already hit 1 time
```

## 관련 글
- REV-0187 — GDB stepi nexti continue
- REV-0191 — GDB watchpoint 기초
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기
- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가

## 출처/검증
- `break`, `tbreak`, 조건부 브레이크포인트(`if`), `ignore`, `info breakpoints`, `disable`/`enable`/`delete`: GDB 공식 온라인 문서("Breakpoints, Watchpoints, and Catchpoints") 기준.
- 별표(`*`) 없는 숫자 위치가 줄 번호로 해석된다는 점: GDB 공식 문서 "Specify Location" 섹션 기준 (2026-09-08 검증).
