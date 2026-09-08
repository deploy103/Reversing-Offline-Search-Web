---
id: REV-0187
title: "GDB stepi nexti continue"
slug: "rev-0187-gdb-stepi-nexti-continue"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb stepi", "gdb nexti", "gdb continue", "gdb step", "gdb next", "gdb until", "명령어 단위 실행"]
aliases: ["gdb si ni", "gdb 한줄씩 실행", "gdb 스텝 오버", "gdb 스텝 인투", "gdb 계속 실행"]
symptom_keywords: ["gdb에서 call 안으로 들어가고 싶음", "gdb에서 call 함수를 건너뛰고 싶음", "gdb continue가 안 멈춤", "gdb step과 next 차이 모름", "gdb 명령어 하나씩 실행하는법"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB에서 브레이크포인트에 멈춘 뒤 실행을 이어가는 방법은 목적에 따라 갈리는데, 어셈블리 명령어 하나만 실행하며 `call` 안으로 들어가는 `stepi`(si), `call`을 통째로 건너뛰는 `nexti`(ni), 다음 브레이크포인트나 프로그램 종료까지 쭉 진행하는 `continue`(c)가 가장 핵심이며, 소스 코드 단위로 움직이는 `step`/`next`와는 명확히 구분해서 써야 한다.

## 언제 검색해야 하나
- 브레이크포인트에서 멈춘 뒤 딱 한 개의 어셈블리 명령어만 실행해보고 싶은데 어떤 명령을 써야 할지 모를 때
- `call printf` 같은 라인에서 함수 안으로 들어가서 내부를 보고 싶은지, 아니면 그냥 통째로 건너뛰고 다음 줄로 가고 싶은지에 따라 다른 명령이 필요하다는 걸 처음 알았을 때
- `continue`를 쳤는데 프로그램이 끝까지 실행되고 멈추지 않아서 당황할 때
- 반복문을 벗어날 때까지 계속 `nexti`를 누르기 귀찮아서 더 빠른 방법을 찾을 때
- `step`/`next`(소스 레벨)와 `stepi`/`nexti`(명령어 레벨)의 차이가 헷갈릴 때

## 핵심 개념

### 소스 레벨 vs 명령어 레벨
GDB는 두 계층의 "한 걸음 실행" 명령을 제공한다.
- **소스 레벨**: `step`(s), `next`(n) — 디버그 심볼이 있을 때, C 소스 코드의 **한 줄**을 실행한다. 한 줄이 여러 어셈블리 명령어로 컴파일됐다면 그 명령어들을 전부 실행하고 다음 소스 줄에서 멈춘다.
- **명령어 레벨**: `stepi`(si), `nexti`(ni) — 디버그 심볼 유무와 상관없이, **어셈블리 명령어 딱 하나**를 실행한다. 리버싱에서 소스 코드 없이 바이너리만 놓고 분석하는 상황이 대부분이므로, 실전에서는 `stepi`/`nexti`를 훨씬 많이 쓴다.

### `stepi`(si) — call 안으로 들어간다
`stepi`는 현재 명령어를 하나 실행하고 바로 다음 명령어에서 멈춘다. 만약 현재 명령어가 `call some_func`라면, `stepi`는 그 호출된 함수의 **첫 번째 명령어**에서 멈춘다 — 즉 함수 내부로 "들어간다"(step into). `printf`, `malloc` 같은 라이브러리 함수 안까지 전부 따라 들어가게 되므로, 디버그 심볼이 없는 라이브러리 안에서는 알아보기 힘든 코드가 잔뜩 나올 수 있다.

### `nexti`(ni) — call을 건너뛴다
`nexti`도 명령어를 하나 실행하는 것은 같지만, 현재 명령어가 `call`이면 **그 함수 전체를 끝까지 실행한 뒤, call 다음 명령어에서 멈춘다** — 함수 내부는 보지 않고 통째로 "건너뛴다"(step over). 이미 내부 로직을 알고 있는 라이브러리 함수(`printf`, `strcmp` 등)를 호출하는 지점에서는 대개 `nexti`를 써서 시간을 아낀다. 반대로 분석 대상인 사용자 정의 함수(`check_password` 등)라면 `stepi`로 안까지 들어가야 한다.

### `continue`(c) — 다음 브레이크포인트/워치포인트까지 계속 진행
`continue`는 현재 멈춘 지점부터 프로그램을 다시 정상 속도로 실행시키고, **다음 브레이크포인트나 워치포인트에 도달하거나 프로그램이 종료될 때까지** 멈추지 않는다. 남은 브레이크포인트가 없다면 그냥 끝까지 실행되고 "exited normally"로 끝난다 — 이게 "continue가 안 멈춘다"는 흔한 증상의 정체다: 멈출 이유(브레이크포인트/워치포인트)가 남아있지 않을 뿐 GDB가 고장난 게 아니다. `continue 5`처럼 숫자를 주면 "현재 브레이크포인트를 5번 더 무시하고 6번째부터 멈춰라"는 뜻이 된다(`ignore`와 같은 효과).

### `until` — 반복문을 빠르게 빠져나가기
반복문 안에서 `nexti`를 수십 번 눌러가며 루프를 빠져나가는 건 비효율적이다. `until`(줄여서 `u`)은 인자 없이 쓰면 "현재 프레임에서, 현재 주소보다 큰 주소에 도달하거나 현재 함수가 리턴할 때까지" 실행한다 — 즉 뒤로 도는(backward jump) 반복문 안에서는 루프가 끝나는 지점까지 자동으로 진행해준다. 특정 줄이나 주소를 인자로 줄 수도 있다:
```gdb
until 42
until *0x401256
```

### `finish` — 현재 함수가 리턴할 때까지 실행
`stepi`로 함수 안까지 들어갔는데 더 볼 게 없어서 빨리 빠져나오고 싶다면 `finish`를 쓴다. 현재 스택 프레임이 리턴할 때까지 실행하고, **리턴값**(RAX에 들어있는 값)까지 자동으로 보여준다.
```gdb
(gdb) finish
Run till exit from #0  strlen (s=0x7fffffffe4a0 "hello") at strlen.c:...
0x0000555555555199 in main ()
Value returned is $1 = 5
```

### 반복 실행 — 마지막 명령을 그냥 다시 치기
GDB는 빈 줄(그냥 Enter)을 입력하면 **직전에 실행한 명령을 그대로 반복**한다. `stepi`를 한 번 친 뒤 계속 Enter만 눌러서 명령어를 하나씩 훑어보는 게 실무에서 아주 흔한 패턴이다.

### `backtrace`로 지금 어디까지 들어와 있는지 확인
`stepi`로 여러 함수를 들락날락하다 보면 지금 콜스택이 몇 겹인지 헷갈릴 수 있다. 이럴 때 `backtrace`(bt)로 현재 호출 스택을 확인한다.
```gdb
(gdb) bt
#0  strcmp ()
#1  0x0000555555555199 in check_password (input=...) at chall.c:15
#2  0x00005555555551f0 in main () at chall.c:22
```

## 화면/코드에서 보이는 징후
- `stepi` 실행 시마다 `0x0000555555555185	15	    if (strcmp(input, secret) == 0) {`처럼 주소와 소스 줄이 함께 뜸(디버그 심볼이 있을 때)
- `nexti`로 `call` 라인을 건너뛰면 화면이 바로 다음 줄로 넘어가고, 중간 과정은 보이지 않음
- `continue` 후 아무 메시지 없이 한참 대기하다가 프로그램이 사용자 입력을 기다리는 상태(표준입력 대기)
- `finish` 실행 시 `Value returned is $1 = ...`로 리턴값이 표시됨

## 가장 먼저 할 것
지금 멈춰있는 명령어가 분석 대상 함수를 향한 `call`인지, 아니면 이미 아는 라이브러리 함수를 향한 `call`인지부터 판단한다. 전자는 `stepi`, 후자는 `nexti`를 쓴다. 그냥 다음 브레이크포인트까지 빠르게 가고 싶다면 `continue`.

## 단계별 절차

**1) 현재 명령어 확인**
```gdb
x/i $rip
```

**2) 상황에 맞는 진행 명령 선택**
```gdb
stepi     # call 안으로
nexti     # call 건너뛰고
continue  # 다음 브레이크포인트까지
until     # 현재 반복문 빠져나가기
finish    # 현재 함수 리턴까지
```

**3) 반복 훑어보기**
`stepi` 한 번 친 뒤 Enter를 계속 눌러 명령어를 순서대로 관찰한다.

**4) 콜스택 확인이 필요하면**
```gdb
bt
```

## 명령어/단축키
```gdb
stepi        # si
nexti        # ni
continue     # c
continue N
step         # s (소스 레벨)
next         # n (소스 레벨)
until        # u
finish
bt
```

## 출력 해석
- `si`/`ni` 뒤에 나오는 주소가 이전 명령어 주소 + 이전 명령어 길이와 일치하면 정상적으로 한 칸 진행한 것이다(점프/콜이 아니라면).
- `finish`의 `Value returned is $1 = N`에서 `$1`은 GDB의 값 히스토리 번호이며, 이후 `print $1`로 다시 참조할 수 있다.
- `Continuing.` 메시지 뒤 아무 것도 안 뜨고 프롬프트가 안 돌아오면, 프로그램이 `scanf`나 `read` 등으로 입력을 기다리고 있는 상태일 가능성이 높다 — 터미널에 값을 입력하면 이어서 진행된다.

## 흔한 실수
- 라이브러리 함수(`printf`, `malloc` 등) 앞에서 `stepi`를 눌러 심볼도 없는 내부 코드 속으로 끝없이 들어가버리는 것 — 이럴 땐 `nexti`를 썼어야 한다. 이미 들어가 버렸다면 `finish`로 즉시 빠져나올 수 있다.
- `continue`가 멈추지 않는 걸 GDB 오류로 착각하는 것 — 실제로는 남은 브레이크포인트가 없어서 끝까지 실행된 것뿐이다.
- `next`(소스 레벨)와 `nexti`(명령어 레벨)를 섞어 쓰다가, 디버그 심볼이 없는 바이너리에서 `next`를 눌렀는데 아무 반응이 없거나 이상하게 동작하는 것 — 심볼이 없으면 `nexti`/`stepi`를 써야 한다.
- 반복문 내부에서 `nexti`를 수백 번 눌러가며 시간을 낭비하는 것 — `until`이나 조건부 브레이크포인트(REV-0186)를 쓰면 훨씬 빠르다.

## 막혔을 때 다음 체크
- 애초에 원하는 지점에 브레이크포인트를 정확히 거는 법 → REV-0186 GDB break와 address breakpoint
- 지금 레지스터 값이 어떻게 바뀌었는지 확인하고 싶다면 → REV-0188 GDB info registers와 flags 확인
- 지금 명령어 주변 코드를 통째로 다시 보고 싶다면 → REV-0190 GDB disassemble와 현재 RIP 주변 보기

## 미니 예제
```gdb
(gdb) x/i $rip
=> 0x555555555199 <main+16>:	call   0x555555555169 <check_password>
(gdb) stepi
0x0000555555555169 in check_password ()
(gdb) bt
#0  0x0000555555555169 in check_password ()
#1  0x0000555555555199 in main ()
(gdb) finish
Run till exit from #0  check_password ()
0x000055555555519e in main ()
Value returned is $1 = 1
```
`call` 라인에서 `stepi`로 `check_password` 안까지 들어간 뒤, 더 볼 것이 없다고 판단해 `finish`로 바로 빠져나오면서 리턴값 `1`을 확인했다.

## 관련 글
- REV-0186 — GDB break와 address breakpoint
- REV-0188 — GDB info registers와 flags 확인
- REV-0190 — GDB disassemble와 현재 RIP 주변 보기

## 출처/검증
- `stepi`, `nexti`, `continue`, `until`, `finish`의 동작 차이: GDB 공식 온라인 문서("Continuing and Stepping") 기준.
- 빈 줄 입력 시 마지막 명령 반복 동작: GDB 공식 문서 "Command Syntax" 섹션 기준 (2026-09-08 검증).
