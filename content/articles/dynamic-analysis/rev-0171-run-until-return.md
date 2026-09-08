---
id: REV-0171
title: "Run Until Return과 함수 빠져나오기"
slug: "rev-0171-run-until-return"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg]
keywords:
  - run until return
  - execute till return
  - step out
  - finish
  - Ctrl+F9
  - 함수 빠져나오기
  - 함수 탈출
  - 리턴까지 실행
aliases:
  - 함수에서 빠져나오는법
  - 잘못 들어간 함수 나오는법
  - Ctrl+F9가 뭐임
  - finish 명령어
  - step out이 뭔가요
  - RET까지 실행
symptom_keywords:
  - 라이브러리 함수 안에서 못빠져나옴
  - step into 잘못눌렀음
  - 함수 안에서 길을 잃음
  - 반환될때까지 실행하는법
  - finish 명령어 사용법
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Run Until Return(x64dbg의 Execute till Return, GDB의 `finish`)은 지금 있는 함수가 `RET`으로 끝나서 호출자에게 돌아갈 때까지 자동으로 실행시켜주는 기능으로, Step Into를 잘못 눌러 낯선 함수 안으로 들어갔을 때 가장 빠르게 탈출하는 방법이다.

## 언제 검색해야 하나
- Step Into(F7)를 눌렀더니 라이브러리 함수(예: `malloc`, `strcpy`) 내부로 들어가버렸고, 한 줄씩 F8/F7을 눌러 나오기엔 너무 깊거나 코드가 복잡할 때
- 지금 있는 함수의 **반환값(RAX/EAX)** 이 뭔지만 빨리 확인하고 원래 위치로 돌아가고 싶을 때
- GDB에서 `finish`를 쳤는데 "Run till exit" 메시지 이후 아무 반응이 없거나 이해가 안 될 때
- x64dbg의 `Ctrl+F9`가 `F9`(그냥 실행)와 뭐가 다른지 헷갈릴 때
- 재귀 함수나 콜백 함수 안에서 여러 단계 중첩된 상태로 시작 함수까지 한 번에 돌아가고 싶을 때

## 핵심 개념

### Run Until Return이 하는 일
현재 실행 위치가 어떤 함수 내부에 있다고 하자. 이 함수는 언젠가 `RET` 명령어를 실행해서 자신을 호출한 곳(반환 주소)으로 돌아간다. Run Until Return은 내부적으로 **"현재 함수의 반환 주소"에 임시 브레이크포인트를 걸고 실행을 재개**하는 방식으로 동작한다. 그 함수 안에서 무슨 일이 일어나든(반복문, 중첩 CALL 등) 무시하고, 함수가 실제로 `RET`을 실행해서 호출자에게 돌아가는 순간 자동으로 멈춘다.

이 동작은 Step Over(REV-0170)가 CALL 하나를 건너뛸 때 쓰는 메커니즘과 원리가 동일하다 — 차이는 Step Over는 "다음 CALL 하나"에 대해 적용하고, Run Until Return은 "지금 내가 들어와 있는 함수 자체"에 대해 적용한다는 점이다. 즉 Run Until Return은 "Step Into를 이미 저질러서 함수 안에 들어와 있는 상태에서 탈출하는 기능"이라고 생각하면 된다.

### 반환 주소는 어디서 가져오는가
현재 함수에 진입할 때 `CALL`이 실행되면서 스택 맨 위에 반환 주소가 PUSH되어 있다(REV-0071, REV-0044 참고). 표준적인 프롤로그(`push rbp; mov rbp, rsp`)를 쓰는 함수라면 이 반환 주소는 `[rbp+8]`(x64) 또는 스택 최상단 근처에서 찾을 수 있다. 디버거는 이 값을 읽어서 그 주소에 임시 브레이크포인트를 걸고, 프로그램을 실행한 뒤, 도달하면 그 임시 브레이크포인트를 제거한다. 사용자는 이 과정을 신경 쓸 필요 없이 버튼/명령 하나로 처리된다.

### Run Until Return vs 그냥 F9(Run)
`F9`(그냥 실행/`continue`)는 다음 브레이크포인트를 만날 때까지 계속 실행한다 — 만약 아무 브레이크포인트도 안 걸려 있으면 프로그램이 끝까지 실행되거나 종료돼버릴 수 있다. Run Until Return은 **정확히 "현재 함수의 반환 지점"** 이라는 목표를 자동으로 계산해서 그 지점에만 임시로 멈춘다는 점이 다르다. 즉 목적이 분명한 상황(지금 함수에서 나가고 싶다)에서는 F9보다 Run Until Return이 훨씬 정확하고 안전하다.

### 반환값 확인과의 조합
Run Until Return으로 멈춘 직후는 곧 "CALL 직후" 상태와 같다. 따라서 이 시점에 RAX(64비트)/EAX(32비트)를 보면 방금 빠져나온 함수의 반환값을 바로 알 수 있다(REV-0176 참고). GDB의 `finish`는 이를 더 편하게 만들어서, 멈춘 직후 `Value returned is $1 = ...` 형태로 반환값을 자동으로 출력해준다.

### 중첩된 상태에서 여러 단계 빠져나오기
만약 Step Into를 세 번 연속 눌러서 A → B → C 세 단계 함수 내부까지 들어가 있다면, Run Until Return을 세 번 반복 실행하면 C에서 B로, B에서 A로, A에서 원래 위치로 차례로 빠져나올 수 있다. GDB에서는 `finish`를 여러 번 입력하거나, 콜스택 깊이를 `bt`로 먼저 확인한 뒤 몇 번 반복할지 판단하면 된다.

### 함수가 끝나지 않으면 어떻게 되는가
현재 함수가 무한루프에 빠지거나 사용자 입력을 기다리는 중(예: `scanf` 호출)이라면 Run Until Return도 반환 지점에 도달하지 못해 멈추지 않는다. 이때는 콘솔/터미널 창에 입력을 넣어주거나, 그래도 안 끝나면 강제로 일시정지(x64dbg 상단 Pause 버튼, GDB `Ctrl+C`)해야 한다.

## 화면/코드에서 보이는 징후
- x64dbg에서 Execute till Return을 실행하면 화면이 순간적으로 실행되다가 CALL 다음 줄(호출자 함수 안)로 화살표가 이동하고, 레지스터 창의 RAX 값이 갱신된다.
- GDB에서 `finish`를 실행하면 `Run till exit from #0 check_flag ()` 메시지가 뜨고, 잠시 후 `0x0000000000401235 in main ()` 및 `Value returned is $1 = 0x1` 같은 반환값 정보가 출력된다.
- 만약 반환값 타입이 `void`인 함수라면 GDB는 `Value returned is $1 = ...` 줄을 출력하지 않는다(반환값이 없으므로).

## 가장 먼저 할 것
1. 지금 정말로 "함수 내부에 들어와 있는 상태"인지 확인한다(콜스택 창/`bt`로 확인).
2. 이 함수를 빠져나가서 호출자로 돌아가고 싶은 것이 목적인지, 아니면 이 함수 안에서 계속 분석해야 하는지 판단한다.
3. 빠져나가는 게 목적이면 x64dbg `Ctrl+F9` 또는 GDB `finish`를 실행한다.

## 단계별 절차

**x64dbg**
1. 현재 함수 내부(예: 실수로 Step Into한 라이브러리 함수)에 있는 상태에서 `Ctrl+F9`를 누른다(메뉴: Debug → Execute till Return, 또는 우클릭 메뉴에도 존재).
2. 실행이 자동으로 진행되다가 현재 함수의 `RET` 직후, 즉 호출자 함수로 돌아온 지점에서 멈춘다.
3. 레지스터 창에서 EAX/RAX를 확인하면 방금 나온 함수의 반환값을 볼 수 있다.
4. 여러 단계 중첩되어 있다면 `Ctrl+F9`를 필요한 만큼 반복한다.

**GDB / Pwndbg**
1. 현재 함수 내부에 있는 상태에서:
   ```
   finish
   ```
2. `Run till exit from #0 <함수명> ()` 메시지가 뜨고 자동으로 실행된다.
3. 함수가 반환하면 `Value returned is $1 = ...` 형태로 반환값이 출력된다(반환 타입이 `void`가 아닐 때).
4. 여러 단계를 한 번에 빠져나오고 싶다면 `finish`를 여러 번 입력하거나, 먼저 `bt`로 콜스택 깊이를 확인한다.
5. `finish`가 멈추지 않는다면(무한루프/입력 대기) `Ctrl+C`로 강제 중단한다.

## 명령어/단축키
- x64dbg: `Ctrl+F9`(Execute till Return / Run Until Return), 강제 중단은 상단 Pause 아이콘
- GDB/Pwndbg: `finish`(현재 함수 끝까지 실행 후 반환값 표시), `Ctrl+C`(실행 강제 중단), `bt`(backtrace로 콜스택 깊이 확인)

## 출력 해석
- GDB `finish` 출력에서 `Value returned is $1 = 0x2a` 라인이 나오면 `0x2a`(십진수로 42)가 이 함수의 반환값(RAX)이다.
- 반환값이 포인터 타입이면 `Value returned is $1 = (void *) 0x555555559260` 처럼 주소로 표시된다.
- x64dbg에서는 별도 메시지 없이 그냥 레지스터 창의 RAX/EAX 값을 사람이 직접 읽어야 한다 — GDB의 `finish`가 자동으로 알려주는 것과 다른 점이다.

## 흔한 실수
- 그냥 `F9`/`continue`로 빠져나오려다가 다음 브레이크포인트가 없어서 프로그램이 끝까지 실행되거나 원치 않는 곳까지 지나가버리는 것 — 목적이 "현재 함수 탈출"이라면 반드시 Run Until Return/`finish`를 쓴다.
- 재귀 함수 안에서 `finish`를 눌렀는데 재귀 호출 하나만 빠져나오고 여전히 같은 함수 내부(상위 재귀 단계)에 있다는 것을 모르고 당황하는 것 — 재귀 함수는 여러 번 `finish`를 반복해야 완전히 빠져나온다.
- `scanf`처럼 입력을 기다리는 함수 내부에서 `finish`를 눌러놓고 왜 안 끝나는지 모르는 것 — 터미널에 값을 입력해줘야 함수가 반환된다.
- Run Until Return을 실행하는 동안 그 함수 내부에 있던 다른 브레이크포인트를 건드리는 것을 놓치는 것 — 중간에 다른 브레이크포인트에 걸리면 그 지점에서 먼저 멈추므로, 반환 지점까지 못 갔다고 착각하지 말고 콜스택을 다시 확인한다.

## 막혔을 때 다음 체크
- `finish`/`Ctrl+F9`를 눌렀는데 멈추지 않는다면 → 함수가 무한루프이거나 입력을 기다리는지 의심하고, 필요하면 입력을 넣거나 강제 중단한다.
- 몇 단계 함수 안에 들어와 있는지 헷갈린다면 → `bt`(GDB) 또는 x64dbg 콜스택 창으로 현재 깊이를 먼저 확인한다.
- 반환값이 이상하다면 → 정말 함수가 끝나서 반환된 게 맞는지, 아니면 중간에 다른 브레이크포인트에 걸려 멈춘 것뿐인지 현재 명령어 주소를 확인한다.

## 미니 예제

**x64dbg — 잘못 들어간 라이브러리 함수에서 탈출**
```
; F7(Step Into)을 눌렀는데 실수로 strcpy 내부로 들어감
; Ctrl+F9(Execute till Return) 실행
; -> strcpy가 끝나고 호출자로 돌아온 지점에서 정지, RAX는 strcpy의 반환값(dest 포인터)
```

**GDB/Pwndbg — finish로 반환값까지 한 번에 확인**
```
(gdb) step
check_flag (input=0x7fffffffe420 "flag{test}") at chal.c:12
12          int len = strlen(input);
(gdb) finish
Run till exit from #0  check_flag (input=0x7fffffffe420 "flag{test}") at chal.c:12
0x0000000000401235 in main () at chal.c:20
20          if (check_flag(buf)) {
Value returned is $1 = 1
```
`Value returned is $1 = 1`이 `check_flag()`의 반환값이며, 이후 `if`문에서 이 값으로 분기한다는 것을 바로 알 수 있다.

## 관련 글
- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가
- REV-0170 — Step Into와 Step Over 차이
- REV-0176 — CALL 직후 반환값 확인하는 법
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0072 — RET: 함수 반환과 스택 변화

## 출처/검증
- x64dbg Execute till Return(Ctrl+F9) 동작: x64dbg 공식 문서(Debugging, Stepping/Execute till Return) 기준.
- GDB `finish` 명령과 반환값 출력: GNU GDB 공식 매뉴얼 "Continuing and Stepping" 챕터, "Returning from a Function" 절 기준.
- CALL/RET와 반환 주소 스택 저장 메커니즘: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CALL—Call Procedure" / "RET—Return from Procedure" 섹션 기준.
- 2026-09-08 검증.
