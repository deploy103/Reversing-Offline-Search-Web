---
id: REV-0170
title: "Step Into와 Step Over 차이"
slug: "rev-0170-step-into-vs-over"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg]
keywords:
  - step into
  - step over
  - 스텝 인
  - 스텝 오버
  - F7
  - F8
  - stepi
  - nexti
  - si
  - ni
  - single step
  - 한줄씩 실행
  - 디버거 스텝
aliases:
  - step into가 뭔가요
  - step over가 뭔가요
  - F7 F8 차이
  - 스텝인 스텝오버 차이
  - stepi nexti 차이
  - si ni 차이
  - 함수 안으로 안들어가고 넘기는법
symptom_keywords:
  - F7 눌렀는데 라이브러리 코드로 들어감
  - printf 안으로 계속 들어감
  - 함수 내부를 안보고 건너뛰고싶음
  - step into step over 헷갈림
  - 디버거에서 길을 잃었음
  - 한줄씩 실행하는 방법
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Step Into는 CALL을 만나면 그 함수 **내부로 들어가서** 한 줄씩 실행하는 것이고, Step Over는 CALL을 **한 번에 통째로 실행**하고 바로 다음 줄(반환 직후)에서 멈추는 것이다 — 이미 아는 함수인지 모르는 함수인지에 따라 골라 써야 헤매지 않는다.

## 언제 검색해야 하나
- 디버거에서 F7을 눌렀는데 `printf`, `malloc` 같은 라이브러리 함수 내부로 들어가서 알 수 없는 코드가 수백 줄 나오고 어떻게 빠져나와야 할지 모를 때
- Step Into와 Step Over의 차이가 헷갈려서 아무 키나 누르다가 실행 위치를 놓쳤을 때
- GDB에서 `stepi`/`si`와 `nexti`/`ni`의 차이, 또는 `step`/`next`와 `stepi`/`nexti`의 차이를 모를 때
- 관심 있는 사용자 정의 함수(예: `check_password`)에만 들어가고 나머지 라이브러리 호출은 건너뛰고 싶을 때
- 반복문(loop) 안을 한 줄씩 실행하다가 시간이 너무 오래 걸릴 때

## 핵심 개념

### 왜 두 가지 스텝 기능이 필요한가
디버거로 프로그램을 한 줄씩 실행하다 보면 반드시 CALL 명령어를 만난다. 이때 디버거는 두 가지 선택지를 준다.
- **그 함수 안으로 들어가서** 내부 로직까지 한 줄씩 볼 것인가 (Step Into)
- **그 함수는 신경 쓰지 않고 통째로 실행**해서 결과(반환값)만 받고 다음 줄로 넘어갈 것인가 (Step Over)

이 선택이 왜 중요하냐면, 실전 바이너리에는 `printf`, `malloc`, `strlen` 같은 라이브러리 함수 호출이 수없이 나오는데, 이런 함수는 내부 구현을 볼 필요가 거의 없다(어차피 표준 라이브러리 소스다). 매번 Step Into를 누르면 라이브러리 내부의 수백~수천 줄짜리 코드 속에서 길을 잃고, 원래 보려던 사용자 코드(예: 패스워드 검증 로직)에서 한참 멀어지게 된다. 반대로 정말 궁금한 사용자 정의 함수(`sub_401500`, `check_flag` 등)에는 Step Into로 들어가서 내부를 봐야 한다.

### Step Into — CALL 내부로 진입
CALL 명령어를 만나면, 그 CALL이 가리키는 함수의 **첫 번째 명령어**로 실행 위치(RIP/EIP)를 옮기고 거기서 멈춘다. 즉 함수 호출이 실제로 일어나고, 그 함수의 프롤로그(`push rbp` 등)부터 한 줄씩 보게 된다. CALL이 아닌 일반 명령어(예: `mov`, `add`)에서 Step Into를 눌러도 그냥 다음 명령어로 한 줄 진행할 뿐이다 — Step Into와 Step Over는 **CALL을 만났을 때만** 동작이 갈라진다.

### Step Over — CALL을 통째로 건너뛰기
CALL 명령어를 만나면, 디버거가 내부적으로 "CALL 다음 주소(반환 주소)에 임시 브레이크포인트를 걸고 실행을 재개"하는 방식으로 동작한다. 그 함수 내부에서 무슨 일이 일어나든(그 안에서 다시 다른 함수를 열 번 호출하든) 사용자에게는 보이지 않고, 함수가 끝나서 반환 주소로 돌아오면 그 자리에서 다시 멈춘다. 결과적으로 화면상으로는 "CALL 한 줄을 실행했더니 바로 다음 줄로 넘어갔다"처럼 보인다. CALL이 아닌 일반 명령어에서는 Step Into와 동일하게 그냥 한 줄 진행한다.

### 재귀나 무한루프 함수에서 Step Over가 멈추지 않는다면
Step Over는 "반환 주소에 브레이크포인트를 걸고 실행"하는 방식이므로, 그 함수가 끝나지 않고 무한루프에 빠지거나 프로그램이 멈춰버리면 Step Over도 영원히 반환되지 않는다. 이런 경우 디버거를 강제로 일시정지(x64dbg는 상단 Pause 버튼, GDB는 `Ctrl+C`)해서 현재 어디서 멈춰있는지 확인해야 한다.

### 명령어 단위 vs 소스 라인 단위
GDB에는 두 계층의 스텝 명령이 있다.
- `step`/`next` — 소스 코드가 있을 때(디버그 심볼 포함 빌드) **소스 한 줄** 단위로 진행한다. `step`이 Step Into, `next`가 Step Over에 해당한다.
- `stepi`(`si`)/`nexti`(`ni`) — 소스 유무와 무관하게 **어셈블리 명령어 한 개** 단위로 진행한다. 리버싱에서는 대부분 소스 코드/디버그 심볼이 없으므로 `stepi`/`nexti`를 압도적으로 많이 쓴다.

x64dbg는 애초에 어셈블리 레벨 디버거이므로 F7/F8이 항상 명령어 단위로 동작하며, GDB의 `stepi`/`nexti`와 대응 개념이다.

### 실전 판단 기준 — 언제 Into, 언제 Over
1. CALL 대상이 **라이브러리/시스템 함수**(printf, malloc, strcpy, CreateFileW 등)라면 → **Step Over**. 이미 동작이 알려진 함수이므로 내부를 볼 필요가 없다.
2. CALL 대상이 **사용자 정의 함수**이고 그 로직이 궁금하다면(예: 시리얼 검증 함수) → **Step Into**로 들어가서 계속 분석한다.
3. CALL 대상이 사용자 함수인지 라이브러리 함수인지 애매하다면 → 일단 IDA/Ghidra에서 함수 이름과 임포트 목록을 먼저 확인해 판단한다(REV-0071 CALL 문서 참고).
4. 실수로 Step Into해서 라이브러리 내부로 들어가 버렸다면 → 되돌아갈 필요 없이 Run Until Return(REV-0171)을 써서 그 함수가 끝날 때까지 한 번에 빠져나온다.

## 화면/코드에서 보이는 징후
- x64dbg에서 Step Into 직후 디스어셈블리 창의 주소 범위가 완전히 바뀌고(다른 모듈/섹션으로 이동), 함수 프롤로그(`push rbp`, `mov rbp, rsp`)가 보이면 실제로 함수 내부로 들어간 것이다.
- x64dbg에서 Step Over 직후에는 현재 CALL 다음 줄로 화살표가 바로 이동하고 EAX/RAX(반환값)가 갱신된 것이 보인다.
- GDB에서 `stepi` 후 `Cannot access memory` 또는 심볼 없는 raw 주소(`0x00007ffff7...`)만 나온다면 libc 등 심볼 없는 라이브러리 내부로 들어간 것 — Step Over를 썼어야 했다는 신호다.

## 가장 먼저 할 것
1. 지금 멈춰있는 줄이 CALL 명령어인지 확인한다(CALL이 아니면 Into/Over 구분이 의미 없다).
2. CALL 대상이 사용자 코드인지 라이브러리/임포트 함수인지 판단한다(이름, 모듈 위치로 구분).
3. 사용자 코드면 Step Into, 라이브러리면 Step Over를 누른다.

## 단계별 절차

**x64dbg**
1. 현재 정지 위치가 CALL 명령어 줄인지 디스어셈블리 창에서 확인한다.
2. 그 함수 내부를 보고 싶으면 `F7`(Step Into)을 누른다 — 함수 첫 줄로 진입한다.
3. 그 함수를 건너뛰고 반환값만 받고 싶으면 `F8`(Step Over)을 누른다 — CALL 다음 줄에서 멈춘다.
4. 실수로 Step Into해서 라이브러리 코드로 들어갔다면 `Ctrl+F9`(Execute till Return, REV-0171 참고)로 즉시 빠져나온다.
5. CALL이 아닌 일반 명령어에서는 F7과 F8이 동일하게 동작한다(둘 다 한 줄 진행).

**GDB / Pwndbg**
1. 명령어 단위로 함수 내부까지 들어가려면:
   ```
   stepi
   si
   ```
2. 명령어 단위로 CALL을 건너뛰려면:
   ```
   nexti
   ni
   ```
3. 디버그 심볼이 있는 소스 레벨 코드에서 소스 한 줄 단위로 진행하려면:
   ```
   step   ; Into (소스 라인 단위)
   next   ; Over (소스 라인 단위)
   ```
4. 여러 번 반복하려면 숫자를 붙인다: `si 5` (명령어 5개만큼 Step Into 반복), `ni 10`
5. Step Into 후 잘못 들어갔다고 판단되면 `finish`(REV-0171)로 즉시 현재 함수를 빠져나온다.

## 명령어/단축키
- x64dbg: `F7`(Step Into), `F8`(Step Over), `Ctrl+F9`(Execute till Return — 라이브러리에서 잘못 들어갔을 때 탈출용)
- GDB/Pwndbg: `stepi`(`si`, 명령어 단위 Step Into), `nexti`(`ni`, 명령어 단위 Step Over), `step`(소스 라인 Step Into), `next`(소스 라인 Step Over), `finish`(현재 함수 끝까지 실행 후 반환)

## 출력 해석
- x64dbg: Step Over 실행 직후 EAX/RAX 레지스터 값이 바뀌어 있다면, 그 값이 방금 건너뛴 함수의 반환값이다.
- GDB `si`/`ni` 실행 후 프롬프트에 다음 명령어 주소와 디스어셈블리가 한 줄 출력된다(예: `0x0000000000401237 in main ()`). 이 주소가 CALL 다음 주소와 같으면 정상적으로 Step Over가 완료된 것이다.
- GDB에서 `ni`를 눌렀는데도 주소가 CALL 안쪽(다른 모듈)으로 들어가 있다면, 그 CALL 내부에서 예외가 발생했거나 브레이크포인트에 걸려 멈춘 것일 수 있다 — `bt`(backtrace)로 현재 콜스택을 확인한다.

## 흔한 실수
- 라이브러리 함수(`printf`, `malloc`)에도 습관적으로 F7(Step Into)을 눌러서 관계없는 코드 수백 줄 속에서 길을 잃는 것 — 이름을 보고 미리 판단해서 F8을 쓴다.
- Step Into와 Step Over가 CALL이 아닌 명령어에서도 다르게 동작한다고 착각하는 것 — 둘의 차이는 오직 CALL을 만났을 때만 나타난다.
- 재귀 함수나 무한루프에 빠진 함수에 Step Over를 걸어놓고 응답이 없다고 디버거가 멈췄다고 착각하는 것 — Step Over는 내부적으로 반환을 기다리는 것이므로 함수가 끝나지 않으면 영원히 대기한다.
- GDB에서 심볼이 없는 바이너리인데 `step`/`next`(소스 라인 단위)를 써서 "Single stepping until exit from function..." 같은 메시지와 함께 이상하게 동작하는 것 — 심볼이 없으면 `stepi`/`nexti`를 써야 한다.

## 막혔을 때 다음 체크
- 실수로 라이브러리 내부로 Step Into했다면 → Run Until Return(x64dbg `Ctrl+F9`, GDB `finish`)로 즉시 탈출한다(REV-0171 참고).
- Step Over를 눌렀는데 응답이 없다면 → 그 함수가 무한루프이거나 사용자 입력을 기다리는 중(예: `scanf`)일 수 있다. 입력을 기다리는 경우라면 터미널/콘솔에 값을 입력해준다.
- 지금 어느 함수 안에 있는지 헷갈린다면 → x64dbg 콜스택 창 또는 GDB `bt`(backtrace)로 현재 콜스택을 확인한다.
- 같은 함수를 여러 번 반복해서 Step 해야 한다면 → 그 함수 시작 주소에 브레이크포인트를 걸고 F9/`continue`로 단번에 이동하는 게 더 빠르다(REV-0169 참고).

## 미니 예제

**x64dbg — 사용자 함수는 Into, 라이브러리는 Over**
```asm
call    sub_401500      ; 사용자 정의 함수 -> F7(Step Into)로 들어가서 로직 확인
...
call    printf           ; 라이브러리 함수 -> F8(Step Over)로 건너뛰고 반환값만 확인
```

**GDB/Pwndbg — 명령어 단위 스텝 비교**
```
(gdb) x/3i $pc
   0x401230 <main+10>:  call   0x401500 <check_flag>
(gdb) si
0x0000000000401500 in check_flag ()   ; Step Into: 함수 내부로 진입

(gdb) # 만약 대신 nexti를 눌렀다면:
(gdb) ni
0x0000000000401235 in main ()         ; Step Over: check_flag() 전체 실행 후 반환 지점에서 정지
```

## 관련 글
- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가
- REV-0171 — Run Until Return과 함수 빠져나오기
- REV-0175 — CALL 직전 함수 인자 확인하는 법
- REV-0176 — CALL 직후 반환값 확인하는 법
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0072 — RET: 함수 반환과 스택 변화

## 출처/검증
- x64dbg Step Into/Step Over(F7/F8) 동작: x64dbg 공식 문서(Debugging, Stepping) 기준.
- GDB `step`/`next`/`stepi`/`nexti` 명령: GNU GDB 공식 매뉴얼 "Continuing and Stepping" 챕터 기준.
- CALL/RET가 스택에 반환 주소를 저장하고 복원하는 메커니즘: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CALL—Call Procedure" 섹션 기준.
- 2026-09-08 검증.
