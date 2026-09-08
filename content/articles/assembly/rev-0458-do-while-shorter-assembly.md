---
id: REV-0458
title: "do-while 루프가 다른 루프보다 어셈블리가 짧은 이유"
slug: "rev-0458-do-while-shorter-assembly"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - do-while assembly
  - do while 어셈블리
  - loop rotation
  - 루프 회전
  - loop inversion
  - loop guard
  - 루프 가드
  - 조건이 아래에 있는 루프
  - post-condition loop
  - pre-condition loop
aliases:
  - do while이 더 빠른 이유
  - 루프 최적화 do while
  - while이 do while로 바뀌는 이유
  - 컴파일러가 루프를 뒤집는 이유
symptom_keywords:
  - for문인데 조건 체크가 맨 밑에 있음
  - jmp가 하나 없어짐
  - while이 do while처럼 컴파일됨
  - 루프 진입부에 점프가 없어서 이상함
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`do { body } while(cond)`는 정의상 몸체가 최소 1번은 실행됨을 보장하므로 "0번 실행 여부"를 미리 확인하는 가드(guard) 점프가 필요 없는 반면, `for`/`while`은 0번 실행 가능성 때문에 컴파일러가 루프 진입 전 한 번의 추가 점프(또는 중복 체크)를 넣어야 한다 — 이 차이가 do-while 스타일 루프의 어셈블리를 한 명령어만큼 더 짧고 단순하게 만든다.

## 언제 검색해야 하나
- 최적화된 바이너리에서 원래 `for`/`while`이었을 것 같은 루프인데 조건 체크가 몸체 맨 아래에만 있고 진입 시 별도 조건 검사가 없어 보일 때
- "루프 회전(loop rotation)", "loop inversion" 같은 컴파일러 최적화 용어를 만나서 정확히 무엇을 하는 최적화인지 알고 싶을 때
- IDA/Ghidra 디컴파일 결과가 소스와 다르게 `do { ... } while (...)` 형태로 나와서 당황스러울 때
- 반복문의 명령어 개수/분기 횟수를 최소화하는 관점에서 컴파일러가 왜 굳이 코드 형태를 바꾸는지 이해하고 싶을 때

## 핵심 개념

### 세 가지 루프 형태의 근본적 차이
- **전위 조건(pre-condition) 루프 — `while`, `for`**: 몸체를 실행하기 **전에** 조건을 검사한다. 조건이 처음부터 거짓이면 몸체는 단 한 번도 실행되지 않는다 (0회 실행 가능).
- **후위 조건(post-condition) 루프 — `do-while`**: 몸체를 **먼저 실행**하고 나서 조건을 검사한다. 정의상 몸체는 최소 1회는 반드시 실행된다 (0회 실행 불가능).

이 차이 때문에 순수하게 소스 구문 그대로("나이브하게") 기계어로 옮기면 while/for는 매 반복마다 조건을 몸체 "앞"에서 검사해야 하고, 그러려면 몸체 뒤에서 다시 앞으로 돌아가는 무조건 점프(`jmp`)가 하나 더 필요하다.

### 나이브 번역: while이 do-while보다 명령어가 많은 이유
```asm
; 나이브하게 그대로 옮긴 while(cond) { body }
L_cond:
    <cond 평가>
    jcc_false  L_end        ; 조건 거짓이면 탈출
    <body>
    jmp        L_cond        ; ★ 매 반복마다 조건 체크로 되돌아가는 무조건 점프
L_end:
```
```asm
; do { body } while(cond) — 애초에 이 점프가 필요 없음
L_body:
    <body>
    <cond 평가>
    jcc_true   L_body        ; 조건 참이면 몸체로 되돌아감 (이거 하나로 끝)
```
나이브 while 버전은 반복마다 "조건 검사 → 몸체 → 무조건 jmp로 조건 검사 복귀"라는 3단계 점프 구조지만, do-while은 "몸체 → 조건 검사 → 조건부 점프로 몸체 복귀"라는 2단계 구조다. 반복이 N번 일어나면 나이브 while은 N번의 무조건 `jmp` + N번의 조건부 분기를 실행하지만, do-while은 N번의 조건부 분기만 실행한다 — 즉 반복마다 명령어 하나(그리고 분기 예측기 부담)를 아낀다.

### 컴파일러의 해결책: 루프 회전(Loop Rotation)
그래서 최적화 컴파일러(GCC/Clang -O1 이상)는 for/while도 do-while과 같은 효율적인 형태로 바꾸는 **루프 회전(loop rotation, loop inversion이라고도 함)** 최적화를 적용한다. 방법은:
1. 루프 진입 직전에 "혹시 0번 실행일 수도 있으니" 조건을 **한 번만 미리 검사하는 가드(guard)**를 추가한다.
2. 가드를 통과하면(즉 최소 1번은 실행됨이 확정되면) 본체는 do-while 형태(몸체 먼저, 조건은 맨 뒤에서 조건부 점프로 복귀)로 실행한다.

```asm
; for/while이 loop rotation을 거친 후의 모습
    <cond 평가>              ; 가드: 딱 한 번만 실행
    jcc_false  L_end          ; 애초에 0번 반복이면 여기서 끝
L_body:
    <body>
    <cond 평가>
    jcc_true   L_body         ; 반복 중에는 do-while과 동일하게 효율적
L_end:
```
가드 부분(`<cond 평가>` + `jcc_false`)은 루프 전체를 통틀어 **딱 한 번만** 실행되므로 반복 횟수와 무관하게 비용이 고정이다. 반면 몸체 안의 반복 경로는 do-while과 완전히 동일한 효율(반복당 조건부 분기 1개)을 갖게 된다. 결국 for/while이 do-while보다 "정적으로" 명령어 한두 개(가드 부분)가 더 많아 보이는 이유가 바로 이 최초 1회 가드 때문이다 — 반면 do-while은 애초에 0회 실행 가능성이 언어적으로 배제되어 있으므로 이 가드 자체가 필요 없다.

### 왜 반복문 성능 관점에서 중요한가
분기 예측기(branch predictor) 관점에서 조건부 분기 하나로만 이루어진 루프 백엣지는 예측이 매우 쉽다(거의 항상 "다시 반복"으로 예측되다가 마지막에 한 번만 틀림). 여기에 무조건 `jmp`가 추가로 끼어들면 명령어 인출/디코드 대역폭을 추가로 소모하고 코드 크기도 커진다. 그래서 이 회전은 사실상 모든 최적화 컴파일러가 기본으로 적용하는 표준 변환이며, 결과적으로 **-O1 이상에서는 for/while/do-while 세 가지 소스 구문이 전부 do-while 스타일의 유사한 코드로 수렴**한다(REV-0457에서 다룬 대로 keyword 자체를 구분할 수 없게 되는 이유이기도 하다).

### IDA/Ghidra 디컴파일에서 보이는 모습
Ghidra와 IDA의 디컴파일러는 회전된 형태(가드 + do-while 본체)를 다시 분석해서, 가드가 있으면 `while(cond) { ... }`나 `for(...)`로, 가드가 아예 없이 곧바로 몸체로 진입하면 `do { ... } while(cond);`로 재구성해서 보여주는 경향이 있다. 즉 **가드의 유무가 디컴파일러가 do-while로 표시할지 while로 표시할지를 가르는 실질적 단서**다 — 물론 이것도 100% 신뢰할 수 있는 소스 복원은 아니고 발견적(heuristic) 재구성이다.

## 화면/코드에서 보이는 징후
- 루프 진입 직후 곧바로 몸체 명령이 시작되고, 조건부 분기가 몸체 맨 끝에 한 번만 나타난다 (가드 없음 → do-while 스타일 또는 회전된 반복 구간)
- 함수 시작 근처에 `cmp`+`jcc`로 된 가드가 있고, 그 뒤에 별도의 do-while 스타일 반복 블록이 이어진다 (가드 있음 → 원래 for/while이었을 가능성)
- 무조건 `jmp`가 루프 백엣지에 전혀 없고 조건부 분기(`jl`, `jne` 등)만으로 반복이 이루어진다 — loop rotation이 적용된 전형적 흔적

## 가장 먼저 할 것
1. 루프 몸체로 진입하는 지점 바로 앞에 조건 검사(가드)가 있는지 확인한다.
2. 있다면 원래 for/while이 회전된 것, 없다면 원래부터 do-while이었거나 이미 회전이 끝난 반복 구간을 보고 있는 것이다.
3. 반복 중 백엣지가 무조건 `jmp` 하나로 되어 있는지, 조건부 분기 하나로 되어 있는지 비교해 최적화 여부를 가늠한다.

## 단계별 절차

**1) 가드 유무 확인**
```asm
cmp   [n], 0
jle   L_end        ; 가드: 이게 있으면 for/while 출신 가능성
L_body:
...
```

**2) 백엣지 형태 확인**
```asm
L_body:
    ...body...
    cmp   eax, ecx
    jl    L_body     ; 조건부 분기 하나만으로 반복 = 회전 완료(do-while과 동일 효율)
```
vs
```asm
L_cond:
    cmp   eax, ecx
    jge   L_end
    ...body...
    jmp   L_cond      ; 무조건 jmp 존재 = 회전 안 됨(-O0 스타일 나이브 번역)
L_end:
```

**3) -O0/-O2 여부와 연결**
가드 없이 곧바로 do-while식 백엣지만 있다면 최적화가 적용됐거나(-O1 이상) 원본이 정말 do-while이었을 가능성이 크다. 무조건 `jmp`가 섞여 있다면 -O0(비최적화) 컴파일 결과일 가능성이 크다.

## 명령어/단축키
- IDA: `Space`로 그래프 뷰 전환 후 백엣지 색(파랑=무조건, 녹/빨강=조건부)으로 회전 여부 빠르게 확인
- Ghidra: Function Graph에서 동일하게 화살표 종류 확인
- objdump: `objdump -d -M intel <binary>`로 정적 텍스트 비교, `-O0`/`-O2` 두 빌드를 나란히 diff(REV-0464 참고)

## 출력 해석
- 가드가 있고 반복 구간이 do-while 스타일이면: 디컴파일러는 대개 `for`나 `while`로 재구성해서 보여준다(가드가 "0번 실행 가능성 처리"라는 것을 인식하기 때문).
- 가드가 전혀 없으면: 디컴파일러는 `do { ... } while (...)`로 보여줄 가능성이 높다 — 다만 이는 어디까지나 발견적 판단이라, 실제로는 그냥 다른 최적화 경로일 수도 있다는 점을 염두에 둔다.

## 흔한 실수
- "가드가 없으니 소스가 100% do-while이었다"고 단정하는 것 — 컴파일러가 정적 분석으로 "이 루프는 절대 0번 실행되지 않는다"(예: 상수 조건, 이미 앞에서 검증된 조건)는 것을 증명할 수 있으면 for/while도 가드 없이 회전될 수 있다.
- 루프 회전을 "코드를 아예 다른 알고리즘으로 바꾸는 최적화"라고 오해하는 것 — 실제로는 로직은 완전히 동일하게 유지하면서 제어 흐름의 물리적 배치만 바꾸는 것이다.
- 가드 부분의 조건과 반복 구간 안의 조건이 서로 미묘하게 다른 비교 연산자(`<` vs `<=`)를 쓸 수 있다는 것을 놓치는 것 — 회전 과정에서 컴파일러가 등가이지만 다른 형태의 비교로 바꾸는 경우가 있으므로 두 조건이 실제로 같은 의미인지 반드시 검증한다.
- 무조건 `jmp` 하나가 줄었다고 해서 전체 성능이 크게 달라진다고 과대평가하는 것 — 실제 이득은 반복 횟수가 많은 핫 루프에서만 유의미하며, 반복이 몇 번 안 되는 루프에서는 체감 차이가 거의 없다.

## 막혔을 때 다음 체크
- 루프가 회전됐는지 아닌지 확신이 안 서면 → 같은 소스를 `-O0`과 `-O2`로 각각 컴파일해 직접 비교한다(REV-0464 참고).
- for/while/do-while 중 원래 뭐였는지가 정말 중요한 상황이면 → 디버그 정보(PDB/DWARF)의 줄 번호 매핑을 확인한다. 그것도 없다면 정확히 알아낼 방법은 없다는 것을 받아들이고 로직 자체에 집중한다.
- 가드 조건과 반복 조건이 다르게 보이면 → REV-0069/REV-0070으로 각각 signed/unsigned 비교인지부터 재확인한다.

## 미니 예제

**예제 1 — do-while, 가드 없음**
```c
int i = 0;
do { arr[i] = 0; i++; } while (i < n);
```
```asm
xor   eax, eax
L_body:
    mov   dword [rdi+rax*4], 0
    add   rax, 1
    cmp   rax, rsi
    jl    L_body        ; 가드 없이 바로 진입, 조건부 분기 1개로 반복
```

**예제 2 — while이 회전되어 do-while처럼 컴파일된 경우 (가드 있음)**
```c
int i = 0;
while (i < n) { arr[i] = 0; i++; }
```
```asm
    test  esi, esi
    jle   L_end          ; ★ 가드: n <= 0이면 아예 진입 안 함
    xor   eax, eax
L_body:
    mov   dword [rdi+rax*4], 0
    add   rax, 1
    cmp   rax, rsi
    jl    L_body          ; 반복 구간은 예제1의 do-while과 완전히 동일
L_end:
```

**예제 3 — -O0에서 회전되지 않은 나이브 while (참고용, 무조건 jmp 존재)**
```asm
    jmp   L_cond
L_body:
    mov   eax, [i]
    mov   dword [rdi+rax*4], 0
    add   dword [i], 1
L_cond:
    mov   eax, [i]
    cmp   eax, [n]
    jl    L_body            ; 여기까지는 조건부지만
                              ; L_body 끝에 jmp L_cond가 반복마다 추가로 실행됨
```

## 관련 글
- REV-0457 — for문과 while문을 어셈블리에서 구분하는 법
- REV-0066 — JMP: 무조건 분기
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0464 — -O0과 -O2 컴파일 결과를 나란히 비교하는 법

## 출처/검증
- 루프 회전(loop rotation/loop inversion) 최적화: LLVM 공식 문서(LoopRotate Pass) 및 GCC 내부 문서(loop optimization passes) 기준.
- do-while/while/for의 언어 의미 차이(반복 0회 가능 여부): ISO/IEC 9899 (C 표준) 6.8.5 Iteration statements 기준.
- 분기 예측 및 코드 크기 관점의 최적화 근거: Intel 64 and IA-32 Architectures Optimization Reference Manual, 분기 예측 섹션 기준. (2026-09-08 검증)
