---
id: REV-0821
title: "GDB reverse debugging 개념 소개(record/replay)"
slug: "rev-0821-gdb-reverse-debugging-record-replay"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB]
keywords: ["gdb record", "gdb record full", "gdb reverse-step", "gdb reverse-continue", "gdb record btrace", "gdb 역방향 실행", "gdb reverse debugging"]
aliases: ["gdb 리버스 디버깅", "gdb 실행 되돌리기", "gdb record replay", "gdb 시간여행 디버깅", "gdb 역방향 스텝"]
symptom_keywords: ["gdb에서 한 스텝만 뒤로 가고 싶음", "gdb record가 뭔지 모름", "gdb reverse-continue 사용법 모름", "gdb에서 크래시 직전 상태로 되돌리고 싶음", "gdb record btrace와 record full 차이"]
source_ids: ["SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
GDB의 `record`(또는 `record full`) 명령은 프로그램 실행 중 명령어·레지스터·메모리 변화를 기록해두었다가, `reverse-step`/`reverse-next`/`reverse-continue`/`reverse-finish`로 **시간을 거슬러 이전 상태로 되돌아갈 수 있게** 해주는 기능으로, "이 값이 왜 이렇게 됐는지, 방금 무슨 일이 있었는지"를 다시 실행하지 않고 곧바로 되짚어볼 수 있다.

## 언제 검색해야 하나
- 어떤 값이 잘못됐다는 걸 발견했는데, 그 값이 **어디서부터** 잘못되기 시작했는지 앞으로 다시 실행하지 않고 뒤로 거슬러 찾고 싶을 때
- 크래시(세그폴트)가 난 직후 콜스택은 보이는데, 크래시 직전에 무슨 값들이 있었는지 재현 없이 바로 보고 싶을 때
- 조건부 브레이크포인트(REV-0819)나 watch(REV-0642)로 "값이 바뀌는 순간"은 잡았는데, 그 직전 상태와 비교하고 싶을 때
- `record`, `record full`, `record btrace`라는 용어를 봤는데 서로 뭐가 다른지, CTF에서 실제로 쓸 만한지 궁금할 때

## 핵심 개념

### 왜 "역방향 실행"이 필요한가
평소 디버깅은 항상 **앞으로만** 진행한다 — 멈춘 시점보다 이전 상태가 궁금하면 프로그램을 처음부터 다시 실행하고, 원하는 지점 전까지 다시 브레이크포인트/조건을 걸어 도달해야 한다. 반복 재현이 번거롭거나(랜덤 요소가 있거나, 준비 과정이 길거나), 애초에 "언제부터 잘못됐는지" 자체를 모르는 상황이라면 이 과정을 여러 번 반복해야 할 수 있다. GDB의 record/replay는 한 번 기록해두면 그 구간 안에서는 **자유롭게 앞뒤로 이동**할 수 있어 이런 반복을 줄여준다.

### record와 record full — 소프트웨어 기반 완전 기록
```gdb
record
```
는 사실상 `record full`의 별칭으로, GDB가 소프트웨어적으로 **명령어 실행마다 레지스터/메모리 변화를 전부 기록**하는 방식이다. 이 방식은 다음 명령들로 자유롭게 되돌아갈 수 있게 해준다.

- `reverse-step` — 소스 줄 단위로 한 줄 뒤로. 방금 실행한 줄을 "되돌리는" 효과이며, 그 줄이 함수 호출을 포함했다면 그 함수의 마지막 문장 안으로 거꾸로 들어간다(`step`의 반대 동작).
- `reverse-next` — 함수 호출 내부로는 들어가지 않고 한 줄 뒤로(`next`의 반대).
- `reverse-continue` — 마지막으로 멈췄던 지점부터 거꾸로 계속 실행해서, 브레이크포인트나 (역방향으로 의미가 맞는) 예외를 만나면 멈춘다.
- `reverse-finish` — 현재 함수의 시작 지점(호출되기 직전)까지 거꾸로 진행한다(`finish`의 반대).

`set exec-direction reverse`로 실행 방향 자체를 "역방향"으로 바꿔두면, 이후 `step`/`next`/`continue`/`stepi`/`nexti` 같은 **일반 명령도 전부 자동으로 역방향으로 동작**한다. 다시 정방향으로 돌아오려면 `set exec-direction forward`를 쓴다.

이 방식의 대가는 **속도와 메모리**다. 매 명령어의 상태 변화를 전부 저장해야 하므로 기록 중에는 프로그램이 눈에 띄게 느려지고, 오래 기록할수록 메모리를 많이 쓴다. 그래서 보통은 관심 있는 구간 직전에 브레이크포인트로 먼저 멈춘 뒤 그 지점부터 `record`를 시작하는 것이 실전적이다.

### record btrace — 하드웨어 기반 경량 기록
```gdb
record btrace
```
는 인텔 CPU의 **BTS(Branch Trace Store)** 또는 **Intel PT** 하드웨어 기능을 이용해 분기(branch) 지점만 하드웨어가 자체적으로 기록하게 하는 방식이다. 다음과 같은 차이가 있다.

- 오버헤드가 `record full`보다 훨씬 작아 멀티스레드 프로그램에서도 비교적 실용적이다.
- 다만 **프로그램 카운터(실행 경로)만 기록**하고 메모리/레지스터 값은 기록하지 않으므로, "그때 그 변수 값이 무엇이었는지"는 역방향으로 이동해도 알 수 없는 경우가 많다(경로는 재구성되지만 데이터는 재구성되지 않는다).
- 인텔 CPU + 커널의 Intel PT 지원이 필요해 실행 환경을 많이 탄다(모든 CTF 서버/로컬 환경에서 되는 게 아니다).
- `record full`에는 있는 `record save`/`record full restore`(기록을 파일로 저장하고 나중에 불러오기) 기능이 `record btrace`에는 없다.
- 반대로 `function-call-history`(함수 호출 이력 조회) 같은 기능은 `record btrace`에서만 쓸 수 있다.

즉 "값 자체가 궁금하다" → `record full`, "실행 경로(어디로 분기했는지)만 가볍게 훑고 싶다" → `record btrace`로 나눠서 고르면 된다.

### 기록 저장/복원과 한계
`record save FILE`로 지금까지의 기록을 파일에 저장하고, 나중에 `record full restore FILE`로 다시 불러올 수 있다(단, `record full`에서만 지원).

역방향 실행에는 근본적인 한계도 있다. 메모리·레지스터 같은 값은 되돌리기 쉽지만, 파일 I/O나 네트워크 통신 같은 **외부 세계에 대한 부수 효과**는 실제로 되돌릴 수 없다 — GDB는 "그 시점에 이런 값이었다"는 기록을 재생해 보여줄 뿐, 실제로 시스템 콜을 거꾸로 실행하는 것은 아니다. 그래서 `record full` 상태에서는 보통 시스템 콜이 포함된 코드 구간을 온전히 기록/재생하기 어렵고, `return` 명령은 역방향 모드에서 사용할 수 없다.

## 화면/코드에서 보이는 징후
- `record` 명령을 치면 별다른 출력 없이 기록이 시작되고, 이 상태에서 프로그램 실행 속도가 눈에 띄게 느려진다.
- `reverse-step` 등을 실행하면 일반 `step`과 똑같은 형식(파일:줄번호, 소스 코드)으로 출력되지만, 줄 번호가 **이전 방향**으로 이동한다.
- 기록된 히스토리의 맨 처음(가장 과거)까지 되돌아가면 "그 이전 기록이 없다"는 취지의 메시지가 나오고, 이 시점에서 다시 앞으로(`continue` 등) 진행하는 것은 여전히 가능하다.
- `record btrace` 상태에서 값을 `print`하려고 하면, 그 시점의 레지스터/메모리가 기록되지 않았다는 취지의 메시지가 나올 수 있다.

## 가장 먼저 할 것
전체 실행을 처음부터 기록하려 하지 말고, 관심 있는 지점(예: 크래시 직전 근처, 의심스러운 함수 진입 지점) 바로 앞에 일반 브레이크포인트로 먼저 멈춘 뒤 거기서부터 `record`를 시작한다. 이렇게 하면 기록 범위가 작아 속도 저하와 메모리 사용을 최소화할 수 있다.

## 단계별 절차

**1) 관심 지점 직전까지 정상적으로 진행**
```gdb
break suspicious_func
run
```

**2) 기록 시작**
```gdb
record
```
(하드웨어 지원 환경이고 값보다 경로가 중요하다면 `record btrace`)

**3) 평소처럼 조금 더 진행해서 문제 지점을 지나침**
```gdb
next
next
continue
```

**4) 문제를 발견한 뒤 거꾸로 돌아가며 원인 추적**
```gdb
reverse-step
reverse-step
print some_var
```

**5) 필요하면 실행 방향 자체를 반대로 고정**
```gdb
set exec-direction reverse
step
step
set exec-direction forward
```

**6) 기록 종료(선택)**
```gdb
record stop
```

## 명령어/단축키
```gdb
record                     # = record full, 소프트웨어 기반 완전 기록 시작
record full                # 명시적으로 완전 기록
record btrace              # 하드웨어(BTS/Intel PT) 기반 분기 경로만 기록
record stop                # 기록 종료
record save FILE           # 기록을 파일로 저장 (record full 전용)
record full restore FILE   # 저장된 기록 불러오기 (record full 전용)
reverse-step                # 소스 줄 단위 역방향 (호출 내부로 진입)
reverse-next                 # 소스 줄 단위 역방향 (호출 내부 건너뜀)
reverse-continue             # 역방향으로 계속 실행
reverse-finish                # 현재 함수 호출 이전 지점까지 역방향
set exec-direction reverse|forward   # 이후 모든 실행 명령의 방향 전환
```

## 출력 해석
- `reverse-step` 결과로 표시된 소스 줄이 방금 전에 실행했던 줄이라면, 그 줄이 "방금 실행되어 지금 상태를 만든 원인"이라는 뜻이다. 여기서 `print`로 관련 변수를 확인하면 "이 줄이 실행되기 전"의 값을 볼 수 있다.
- `record btrace` 상태에서 함수 호출 이력을 보고 싶다면 `record function-call-history`(간단히 실행 경로만)를 쓸 수 있다 — 다만 이는 `record full`에는 없는 기능이다.
- 기록의 맨 앞(가장 과거)에 도달했다는 메시지가 나온 뒤에도, 다시 정방향(`continue`, `step` 등)으로는 문제없이 진행할 수 있다 — "더 이상 뒤로는 못 간다"는 뜻이지 "더 이상 진행 못 한다"는 뜻이 아니다.

## 흔한 실수
- 프로그램 시작부터 `record`를 걸어서 오래 실행되는 프로그램이 지나치게 느려지거나 메모리를 과도하게 쓰는 것 — 반드시 관심 구간 직전부터 기록을 시작한다.
- `record btrace`로 기록해놓고 역방향 이동 후 변수 값을 확인하려다가 "기록되지 않았다"는 결과를 보고 당황하는 것 — `record btrace`는 실행 경로(분기)만 기록하지 메모리/레지스터 값 전체를 기록하지 않는다.
- 시스템 콜(파일 열기, 네트워크 송수신 등)이 포함된 구간을 `record full`로 기록하려다 제약에 부딪히는 것 — 외부 세계에 대한 부수 효과는 근본적으로 되돌릴 수 없으므로, I/O가 적은 순수 연산 구간 위주로 활용하는 것이 실전적이다.
- 역방향 모드(`set exec-direction reverse`)로 바꿔놓은 채 그대로 잊고 계속 `step`/`continue`를 써서 "왜 자꾸 뒤로 가지"라고 헷갈리는 것 — 작업이 끝나면 반드시 `set exec-direction forward`로 되돌린다.
- 멀티스레드 프로그램에서 `record full`을 쓸 때, 기록된 히스토리가 스레드 구분 없이 전역적으로 관리된다는 점을 모르고 다른 스레드의 기록과 혼동하는 것.

## 막혔을 때 다음 체크
- 애초에 "이 값이 언제 바뀌는지" 자체를 못 찾고 있다면 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak)의 `watch`로 먼저 변경 시점을 잡은 뒤, 그 직전 상태를 이 문서의 `reverse-step`으로 확인하는 조합이 효과적이다.
- 특정 조건에서만 정지 지점을 잡고 싶다면 → REV-0819 GDB에서 조건부 브레이크포인트(condition) 활용하기를 먼저 본다.
- Windows/WinDbg 환경에서 이와 비슷한(오히려 더 완성도 높은) 개념이 궁금하다면 → REV-0822 Time Travel Debugging 개념 소개(WinDbg 참고)를 참고한다.
- 멈추지 않고 흐름 전체를 로그로만 남기고 싶다면 → REV-0820 GDB dprintf로 로그만 찍고 계속 실행하기가 더 간단한 대안이 될 수 있다.

## 미니 예제
전역 카운터가 음수가 되는 버그를 발견했는데, 정확히 어느 줄에서 마이너스로 넘어갔는지 다시 실행하지 않고 거슬러 찾는 상황이다.

```gdb
(gdb) break main
(gdb) run
(gdb) record
(gdb) continue
Continuing.
...
Program received signal SIGFPE, Arithmetic exception.
0x0000000000401234 in divide_by_counter () at chall.c:30
30          return total / counter;
(gdb) p counter
$1 = -1
(gdb) reverse-step
29          counter--;
(gdb) p counter
$2 = 0
(gdb) reverse-step
28          if (should_decrement) counter--;
(gdb) p should_decrement
$3 = 1
```
크래시(0으로 나누기 직전, 카운터가 -1) 시점에서 두 번 `reverse-step`만으로 "28번째 줄의 `should_decrement` 조건이 참이 되어 카운터가 0에서 -1로 넘어갔다"는 원인을 프로그램을 다시 실행하지 않고 바로 찾아냈다.

## 관련 글
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)
- REV-0819 — GDB에서 조건부 브레이크포인트(condition) 활용하기
- REV-0820 — GDB dprintf로 로그만 찍고 계속 실행하기
- REV-0822 — Time Travel Debugging 개념 소개(WinDbg 참고)

## 출처/검증
- `record`(=`record full`)와 `record btrace`의 차이(소프트웨어 완전 기록 vs 하드웨어 BTS/Intel PT 기반 분기 전용 기록), `record save`/`record full restore`가 `record full` 전용이고 `function-call-history`가 `record btrace` 전용이라는 기능 차이: GDB 공식 온라인 매뉴얼("Debugging with GDB") "Process Record and Replay" 섹션 기준(2026-09-09 조사).
- `reverse-step`/`reverse-next`/`reverse-continue`/`reverse-finish`의 동작과 `set exec-direction reverse/forward`, 역방향 모드에서 `return` 명령을 쓸 수 없다는 제약: 같은 매뉴얼 "Reverse Execution" 섹션 기준.
- 역방향 실행이 메모리/레지스터는 되돌릴 수 있어도 장치 I/O 같은 부수 효과는 되돌리기 어렵다는 일반적 한계와 GDB-타겟 계약(target이 합리적으로 동작하고 결과를 보고하기만 하면 된다는 느슨한 계약): GDB 매뉴얼 "Reverse Execution" 섹션 및 FOSDEM 2024 GDB 시간여행 디버깅 발표 자료의 설명을 교차 확인.
