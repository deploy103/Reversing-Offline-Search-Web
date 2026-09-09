---
id: REV-0820
title: "GDB dprintf로 로그만 찍고 계속 실행하기"
slug: "rev-0820-gdb-dprintf-logging"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB]
keywords: ["gdb dprintf", "gdb dynamic printf", "gdb dprintf-style", "gdb dprintf-function", "gdb set logging", "gdb 로그만 찍는 브레이크포인트"]
aliases: ["gdb 동적 printf", "gdb 로그 브레이크포인트", "gdb dprintf 문법", "gdb 멈추지 않는 브레이크포인트", "gdb printf 디버깅"]
symptom_keywords: ["gdb에서 멈추지 않고 값만 찍고 싶음", "gdb dprintf 문법 모름", "gdb dprintf-style이 뭔지 모름", "gdb 함수 호출 인자를 전부 기록하고 싶음", "gdb 로그를 파일로 저장하고 싶음"]
source_ids: ["SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`dprintf LOCATION,"포맷",인자...`는 지정한 위치에 도달할 때마다 프로그램을 멈추지 않고 `printf` 형식으로 값을 찍은 뒤 자동으로 계속 실행하는 GDB의 "동적 printf" 브레이크포인트로, 소스 코드를 수정하고 재컴파일할 수 없는 상황에서도 로깅 코드를 심어놓은 것과 같은 효과를 낸다.

## 언제 검색해야 하나
- 반복 호출되는 함수의 인자/반환값을 전부 기록해서 나중에 한 번에 훑어보고 싶을 때
- 소스 코드가 없거나 재컴파일이 불가능한 바이너리에서 `printf` 디버깅과 같은 효과를 내고 싶을 때
- `break` + `commands` + `print` + `continue` 조합이 번거로워서 더 간단한 방법을 찾고 있을 때
- `dprintf-style`이 `gdb`, `call`, `agent` 세 가지라는데 각각 언제 써야 하는지 헷갈릴 때
- 로그를 화면 대신 파일로 저장하고 싶을 때

## 핵심 개념

### 기본 문법
```gdb
dprintf LOCATION,"포맷 문자열",인자1,인자2,...
```
`LOCATION`은 함수 이름, `파일:줄번호`, `*주소` 등 일반 `break`와 동일한 위치 지정 방식을 그대로 쓴다. 포맷 문자열과 인자는 C의 `printf`와 같은 규칙(`%d`, `%s`, `%p`, `%x` 등)을 따른다.
```gdb
dprintf compare_char,"i=%d input=%c key=%c\n", i, input[i], key[i]
```
이 한 줄은 `compare_char`에 진입할 때마다 `i`, `input[i]`, `key[i]` 값을 자동으로 출력하고 **멈추지 않고 계속 실행**한다. `info breakpoints`로 확인하면 dprintf도 브레이크포인트 목록에 `dprintf` 타입으로 나타나며, 실제로는 "멈추면 지정한 printf를 실행하고 자동으로 continue하는 브레이크포인트"로 내부적으로 구현되어 있다. 그래서 `delete N`, `disable N`, `condition N EXPR`(REV-0819에서 배운 조건부 문법)까지 dprintf에도 그대로 적용할 수 있다.

### dprintf-style 세 가지
`set dprintf-style STYLE`로 출력 방식을 바꿀 수 있다.

- **`gdb`(기본값)** — GDB 자신의 내부 printf 기능을 써서 **GDB 콘솔**에 출력한다. 가장 간단하고 대부분의 상황에서 충분하다.
- **`call`** — GDB가 대상 프로그램(디버기) 안에서 실제로 함수 호출(inferior function call)을 수행한다. 기본적으로 대상 프로그램의 `printf`를 호출하므로, **출력이 프로그램 자신의 표준 출력(stdout)으로 나가서** 리다이렉트나 파이프로 다른 도구와 연계하기 좋다. 호출할 함수는 `set dprintf-function`으로 바꿀 수 있고, 기본값은 `printf`다.
- **`agent`** — `gdbserver` 같은 원격 디버깅 에이전트가 자체적으로 출력을 처리하게 한다. GDB와 통신할 필요 없이 타겟 쪽에서 바로 처리하므로 더 효율적이며, GDB가 연결을 끊어도(`disconnect`) 계속 동작하게 할 수 있다(`set disconnected-dprintf on`). 다만 이 스타일은 `%V` 포맷 지정자를 지원하지 않는다.

```gdb
set dprintf-style call
set dprintf-function fprintf
set dprintf-channel mylog
dprintf 25,"at line 25, glob=%d\n", glob
```
`dprintf-channel`을 지정하면 `fprintf`처럼 첫 번째 인자로 파일 스트림을 받는 함수를 호출할 때, 그 채널 표현식이 첫 번째 인자로 자동 전달된다(예: 이미 프로그램 안에서 열어둔 로그 파일 포인터).

### 함수 호출 스타일(call)의 주의점
`call` 스타일은 정말로 **대상 프로그램 안에서 함수를 실행**시키는 것이므로, 그 함수 호출 자체가 프로그램 상태에 부작용을 낼 수 있다(예: 파일 포인터 위치 이동). 또한 지정한 함수가 지원하지 않는 포맷 지정자를 쓰면 결과가 정의되지 않으므로, `printf` 계열 함수와 호환되는 포맷만 사용해야 한다.

### GDB 콘솔 출력을 파일로 남기기
`dprintf-style`이 기본값(`gdb`)이어도, GDB 자체의 로깅 기능으로 콘솔에 찍히는 모든 내용을 파일로 저장할 수 있다.
```gdb
set logging file trace.log
set logging on
```
이렇게 하면 dprintf가 GDB 콘솔에 출력하는 내용이 화면과 동시에 `trace.log` 파일에도 그대로 쌓여서, 나중에 텍스트 편집기나 `grep`으로 분석할 수 있다.

### condition과 조합해 로그 양 줄이기
dprintf도 일반 브레이크포인트이므로 REV-0819에서 배운 `condition`을 그대로 적용할 수 있다.
```gdb
dprintf compare_char,"i=%d input=%c key=%c\n", i, input[i], key[i]
condition 1 i > 5
```
이렇게 하면 `i > 5`일 때만 로그가 남아서, 관심 없는 앞부분 반복은 건너뛸 수 있다.

### break+commands+continue와의 관계
dprintf가 나오기 전에는 다음처럼 여러 줄로 같은 효과를 냈다.
```gdb
break compare_char
commands
  printf "i=%d\n", i
  continue
end
```
dprintf는 이 패턴을 한 줄로 압축한 문법 설탕(syntactic sugar)에 가깝다. 다만 dprintf 쪽이 `condition`/`ignore`/`delete`를 일반 브레이크포인트와 완전히 동일하게 관리할 수 있어 더 깔끔하다.

## 화면/코드에서 보이는 징후
- `dprintf` 명령을 실행하면 `Dprintf 1 at 0x123456: file main.c, line 25.`처럼 일반 브레이크포인트 생성과 비슷한 메시지가 뜬다.
- `run`/`continue` 이후 프로그램이 멈추지 않고 계속 진행되면서, 지정한 위치를 지날 때마다 콘솔에 로그 줄이 계속 출력된다.
- `info breakpoints`에서 해당 항목의 Type이 `dprintf`로 표시되고, `printf` 부분에 등록된 포맷 문자열이 그대로 보인다.
- `call` 스타일에서는 로그가 GDB 콘솔이 아니라 프로그램 자체의 표준 출력에 섞여서 나온다 — 두 스타일을 혼동하면 "로그가 안 나온다"고 착각하기 쉽다.

## 가장 먼저 할 것
로그를 어디에 남기고 싶은지(GDB 콘솔인지, 프로그램 stdout인지, 파일인지) 먼저 정한다. 대부분의 CTF/리버싱 상황에서는 기본 스타일(`gdb`)로 충분하며, 원격 타겟이나 성능이 중요한 경우에만 `agent`를, 프로그램 출력과 섞어서 보고 싶을 때만 `call`을 고려한다.

## 단계별 절차

**1) 기본 dprintf 걸기**
```gdb
dprintf compare_char,"i=%d input=%c key=%c\n", i, input[i], key[i]
```

**2) 실행**
```gdb
run
```
멈추지 않고 로그만 계속 출력되는 것을 확인한다.

**3) 필요하면 조건으로 좁히기**
```gdb
condition 1 i > 5
```

**4) 파일로 저장하고 싶다면**
```gdb
set logging file trace.log
set logging on
```

**5) 다 봤으면 정리**
```gdb
delete 1
set logging off
```

**6) 프로그램 stdout과 섞어서 보고 싶다면(선택)**
```gdb
set dprintf-style call
set dprintf-function printf
dprintf compare_char,"i=%d\n", i
```

## 명령어/단축키
```gdb
dprintf LOCATION,"fmt",args        # 동적 printf 브레이크포인트 생성
set dprintf-style gdb|call|agent   # 출력 방식 선택 (기본값 gdb)
set dprintf-function FUNC          # call 스타일에서 호출할 함수 (기본값 printf)
set dprintf-channel EXPR           # call 스타일에서 첫 인자로 전달할 채널(예: 파일 스트림)
set disconnected-dprintf on|off    # agent 스타일에서 GDB 연결 종료 후에도 계속 동작할지
set logging file FILE              # GDB 콘솔 출력을 저장할 파일 지정
set logging on / off               # 로깅 시작/종료
info breakpoints                    # dprintf 포함 전체 브레이크포인트 목록/조건 확인
condition N EXPR / ignore N COUNT   # dprintf에도 그대로 적용 가능
delete N                            # dprintf 삭제
```

## 출력 해석
- GDB 콘솔에 `i=3 input=x key=y` 같은 줄이 계속 쌓이면, 그 위치가 프로그램 실행 중 실제로 몇 번, 어떤 값으로 지나갔는지를 한 번에 파악할 수 있는 실행 로그가 만들어진 것이다.
- 로그가 전혀 안 나온다면 그 위치에 실행이 아예 도달하지 않았거나(다른 코드 경로), `dprintf-style`을 `call`로 바꾼 뒤 화면(GDB 콘솔)만 보고 있어서 실제 출력은 프로그램 stdout 쪽에 나가고 있는 경우다.
- `info breakpoints`에서 dprintf 항목의 `printf` 줄에 등록된 포맷/인자가 의도한 것과 다르다면, dprintf를 다시 걸기 전에 기존 것을 `delete`부터 해야 한다(같은 위치에 여러 개가 중첩될 수 있다).

## 흔한 실수
- `dprintf-style`을 `call`로 바꿔놓고 계속 GDB 콘솔만 쳐다보며 "로그가 안 찍힌다"고 헤매는 것 — `call` 스타일의 출력은 프로그램 자신의 stdout으로 나간다.
- 포맷 문자열의 `%` 지정자 개수와 뒤에 나열한 인자 개수를 맞추지 않아 엉뚱한 값이 찍히거나 크래시가 나는 것 — C `printf` 규칙 그대로이므로 타입과 개수를 정확히 맞춰야 한다.
- `call` 스타일에서 호출한 함수(`printf` 등)가 프로그램 내부 상태를 바꾸는 부작용을 가질 수 있다는 걸 모르고 사용하는 것 — 일반적으로 `printf` 자체는 안전하지만, `dprintf-function`을 커스텀 함수로 바꿀 때는 그 함수의 부작용을 반드시 고려해야 한다.
- 로그가 너무 많이 쌓여서 정작 필요한 부분을 못 찾는 것 — `condition`(REV-0819)으로 관심 있는 범위만 남기거나, 처음부터 로그를 파일로 저장해 나중에 검색하는 방식으로 접근해야 한다.
- dprintf도 일반 브레이크포인트처럼 `disable`/`delete`가 필요하다는 걸 잊고 방치해서, 이후 디버깅 세션에서 예상치 못한 로그가 계속 섞여 나오는 것.

## 막혔을 때 다음 체크
- dprintf에 조건을 걸어 특정 상황에서만 로그를 남기고 싶다면 → REV-0819 GDB에서 조건부 브레이크포인트(condition) 활용하기를 참고한다.
- `watch`/`catch`/`tbreak`처럼 dprintf 외의 다른 정지·감시 방식이 궁금하면 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak)를 참고한다.
- x64dbg 환경에서 같은 개념(멈추지 않는 로그 브레이크포인트)을 쓰고 싶다면 → REV-0816 x64dbg Conditional Log Breakpoint 활용하기를 참고한다.
- 로그로 확인한 실행 경로를 시간상 거슬러 올라가 원인을 추적하고 싶다면 → REV-0821 GDB reverse debugging 개념 소개(record/replay)를 참고한다.

## 미니 예제
문자열 비교 반복문의 모든 인덱스별 비교 값을 한 번에 기록하는 상황이다.

```gdb
(gdb) dprintf compare_char,"i=%d input=%c key=%c\n", i, input[i], key[i]
Dprintf 1 at 0x4011a0: file chall.c, line 22.
(gdb) run
Starting program: /home/user/chall
i=0 input=h key=f
i=1 input=e key=l
i=2 input=l key=a
i=3 input=l key=g
i=4 input=o key=!
[Inferior 1 (process 1234) exited with code 01]
```
프로그램이 한 번도 멈추지 않고 끝까지 실행되면서, 다섯 글자 전부의 비교 값을 한 번에 얻었다. 손으로 `break` + `continue`를 5번 반복하며 매번 값을 확인하던 작업을 실행 한 번으로 끝낸 것이다.

## 관련 글
- REV-0819 — GDB에서 조건부 브레이크포인트(condition) 활용하기
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)
- REV-0816 — x64dbg Conditional Log Breakpoint 활용하기
- REV-0821 — GDB reverse debugging 개념 소개(record/replay)

## 출처/검증
- `dprintf LOCATION,"fmt",args` 문법과 내부적으로 브레이크포인트로 취급되어 `condition`/`ignore`/`delete`가 그대로 적용된다는 점: GDB 공식 온라인 매뉴얼("Debugging with GDB") "Dynamic Printf" 섹션 기준(2026-09-09 조사).
- `dprintf-style`의 세 값(`gdb`/`call`/`agent`), 각 스타일의 출력 대상과 동작 차이, `dprintf-function`/`dprintf-channel`/`disconnected-dprintf` 설정, `%V` 포맷 지정자가 `agent` 스타일에서 지원되지 않는다는 점: 같은 GDB 매뉴얼 "Dynamic Printf" 섹션 기준.
- `set logging file`/`set logging on`으로 GDB 콘솔 출력을 파일로 저장할 수 있다는 점: GDB 매뉴얼 "Logging Output" 섹션의 일반적으로 잘 알려진 기능에 근거.
