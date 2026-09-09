---
id: REV-0837
title: "Step Over인데 함수 안으로 들어가 버릴 때"
slug: "rev-0837-step-over-enters-function"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords: ["Step Over 안 먹힘", "F8인데 함수 안으로 들어감", "gdb next가 step처럼 동작", "재귀 함수 step over", "리턴 지점 브레이크포인트"]
aliases: ["Step Over가 이상하게 동작함", "F8 눌렀는데 F7처럼 됨", "next인데 안으로 들어감"]
symptom_keywords: ["F8을 눌렀는데 CALL 대상 함수 안으로 들어감", "next를 눌렀는데 라이브러리 내부로 들어감", "재귀 함수에서 step over가 중간에 멈춤", "Step Over 도중 갑자기 예외로 멈춤"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Step Over(x64dbg F8, GDB `next`)는 내부적으로 "CALL 명령 바로 다음 주소(리턴 지점)에 임시 브레이크포인트를 걸고 실행"하는 것과 같아서, 그 함수 내부에 이미 걸려 있는 다른 브레이크포인트를 만나거나, 예외가 발생하거나, 함수에 라인 정보가 아예 없거나, 재귀 호출로 같은 리턴 주소가 더 안쪽에서 먼저 걸리면 리턴 지점까지 못 가고 함수 내부에서 멈춘다 — 이는 오작동이 아니라 설계된 동작이다.

## 언제 검색해야 하나
- x64dbg에서 F8(Step Over)을 눌렀는데 CPU 창이 `CALL` 대상 함수의 첫 명령어로 이동했을 때
- GDB에서 `next`를 눌렀는데 라이브러리/재귀 함수 내부로 들어가 버린 것처럼 보일 때
- Step Over 도중 상태 표시줄/콘솔에 예외나 브레이크포인트 관련 메시지가 함께 뜰 때
- 재귀 함수에서 Step Over를 반복했는데 예상보다 훨씬 이른 시점에 멈출 때

## 핵심 개념

### Step Over의 실제 구현: "리턴 지점에 임시 브레이크포인트"
x64dbg와 GDB 모두 Step Over를 "그 CALL 다음 주소에 임시 브레이크포인트를 걸고 계속 실행"하는 방식으로 구현한다. 즉 Step Over도 결국 "실행 → 멈춤"의 반복이며, 다음 상황 중 하나라도 해당하면 리턴 지점보다 먼저 멈춘다.

1. **콜백/헬퍼 함수 내부에 이미 브레이크포인트가 걸려 있음**: 예를 들어 이전에 `bp GetProcAddress`(x64dbg) 또는 `break malloc`(GDB)를 걸어뒀다면, 지금 Step Over 하려는 CALL이 내부적으로 그 함수를 호출할 때 그 브레이크포인트에서 먼저 멈춘다.
2. **호출된 함수 내부에서 예외 발생**: 안티디버깅 루틴이 널 포인터 역참조 등으로 의도적으로 예외를 일으켜 SEH/시그널로 흐름을 바꾸는 경우, 디버거의 예외 처리 설정에 따라 first-chance 시점에 멈출 수 있다.
3. **디버그 정보가 아예 없는 함수 안에서 next를 쓴 경우(GDB)**: 현재 멈춰 있는 프레임 자체에 라인 정보가 없으면 GDB의 `next`는 `step`과 똑같이 명령어 단위로 동작해버려, 마치 Step Into처럼 함수 안으로 들어가는 것처럼 보인다.
4. **재귀 함수에서의 리턴 주소 충돌**: 재귀 호출은 같은 CALL 명령의 리턴 주소가 스택 여러 프레임에 반복해서 나타난다. Step Over가 건 임시 브레이크포인트는 "그 주소"만 보고 거는 것이라, 더 안쪽 재귀 프레임이 먼저 그 주소를 통과하면 바깥쪽으로 돌아오기 전에 먼저 멈춰서 "함수 안으로 계속 들어간다"는 착각을 준다.
5. **단축키 혼동**: x64dbg 기본값은 F7=Step Into, F8=Step Over다. 다른 디버거 습관 때문에 실수로 F7을 누르는 경우도 실제로 흔하다.

## 화면/코드에서 보이는 징후
- CPU 창 주소가 CALL 대상 함수의 **첫 명령어**와 정확히 일치(진짜로 들어간 것)
- Log/콘솔에 "Breakpoint at ..." 또는 "Access violation" 메시지가 함께 뜸
- GDB에서 `next`를 눌렀는데 `Run till exit` 없이 그냥 다음 명령어 한 줄만 진행됨(라인 정보 없음 신호)
- 재귀 함수에서 `bt`/Call Stack을 보면 같은 함수가 여러 프레임 쌓여 있음

## 가장 먼저 할 것
멈춘 위치가 CALL 대상의 **첫 번째 명령어**인지, 아니면 함수 **중간**인지부터 확인한다. 첫 명령어면 브레이크포인트/단축키 혼동을, 중간이면 예외 발생이나 재귀 충돌을 의심한다.

## 단계별 절차
1. x64dbg: Breakpoints 탭에서 지금 멈춘 함수 범위 안에 다른 브레이크포인트가 있는지 확인 → 있으면 잠시 Disable 후 재시도.
2. GDB: `bt`로 콜스택 깊이를 확인해 재귀 중첩 여부를 판단.
3. x64dbg: Options → Preferences → Exceptions에서 first-chance 예외가 체크되어 있는지 확인.
4. 재귀 충돌이 의심되면, Step Over 대신 `finish`(GDB) / `Ctrl+F9`(x64dbg, Execute till return)로 현재 프레임만 명확히 빠져나온다.
5. GDB에서 현재 프레임에 라인 정보가 없어 `next`가 `step`처럼 동작한다면, 그 구간은 `finish`로 통째로 벗어난다.
6. 단축키가 헷갈린다면 툴바 아이콘을 직접 클릭해 Step Over를 실행해본다.

## 명령어/단축키
```text
x64dbg: F8(Step Over), F7(Step Into), Ctrl+F9(Execute till return)
```
```gdb
next
step
finish
bt
info breakpoints
```

## 출력 해석
정확히 CALL 대상 첫 명령어에서 멈췄고 Log에 별다른 메시지가 없다면 십중팔구 단축키 혼동이다. "Breakpoint reached"류 메시지가 있으면 콜백 내부 브레이크포인트가 원인이고, 예외 코드가 찍혔다면 안티디버깅/SEH 가능성을 REV-0841과 함께 확인한다.

## 흔한 실수
- 단축키를 확인하지 않고 무작정 디버거 버그로 단정하는 것.
- 콜백 내부에 걸어둔 브레이크포인트의 존재를 잊고 왜 멈추는지 헤매는 것.
- 재귀 함수에서 Step Over/next를 반복하며 "왜 계속 안으로 들어가지"라고 오해하는 것 — 실제로는 리턴 주소 충돌로 인한 정상 동작이다.
- GDB에서 현재 프레임에 라인 정보가 없다는 것을 확인하지 않고 `next`만 반복하는 것.

## 막혔을 때 다음 체크
- x64dbg에서만 겪는 상세 사례가 필요하다면 → REV-0625 x64dbg Step Over가 CALL 내부로 계속 들어갈 때
- 반대로 Step Into가 라이브러리에서 못 빠져나온다면 → REV-0836 Step Into가 라이브러리 내부로 계속 들어가서 못 나올 때
- Step Into/Step Over 기본 개념이 헷갈린다면 → REV-0170 Step Into와 Step Over 차이
- 브레이크포인트 충돌이 자꾸 반복된다면 → REV-0835 브레이크포인트가 안 걸릴 때 확인할 것들

## 미니 예제
x64dbg에서 `CALL sub_402000`을 F8로 넘기려 했는데 CPU 창이 `sub_402000`의 첫 명령어로 이동했다. 상태 표시줄에 "Access violation reading location 0x00000000"이 남아 있었는데, 이는 `IsDebuggerPresent` 우회를 확인하려고 프로그램이 일부러 널 포인터 역참조 예외를 일으킨 안티디버깅 루틴이었다. `Ctrl+F9`(Execute till return)로 함수를 완전히 빠져나온 뒤 분석을 이어갔다.

## 관련 글
- REV-0625 — x64dbg Step Over가 CALL 내부로 계속 들어갈 때
- REV-0836 — Step Into가 라이브러리 내부로 계속 들어가서 못 나올 때
- REV-0170 — Step Into와 Step Over 차이
- REV-0835 — 브레이크포인트가 안 걸릴 때 확인할 것들

## 출처/검증
- x64dbg의 Step Over 구현(임시 브레이크포인트를 통한 리턴 지점 실행)과 예외 처리 설정: x64dbg 공식 문서 기준.
- GDB의 `next`가 라인 정보 없는 프레임에서 `step`과 동일하게 동작하는 것, 재귀 호출 시 리턴 주소 기반 임시 브레이크포인트 동작: GDB 공식 매뉴얼("Continuing and Stepping" 챕터) 기준(2026-09-09 검증).
