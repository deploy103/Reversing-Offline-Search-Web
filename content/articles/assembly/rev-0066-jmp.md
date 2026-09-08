---
id: REV-0066
title: "JMP: 무조건 분기"
slug: "rev-0066-jmp"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - jmp
  - JMP
  - Jmp
  - jmp 명령어
  - jmp instruction
  - 무조건 분기
  - 무조건 점프
  - unconditional jump
  - "jmp rax"
  - "jmp short"
  - "jmp near"
  - "jmp [rax]"
  - jump table
  - 점프 테이블
  - 스위치 케이스
  - switch case
  - jmp와 call 차이
  - jmp chain
  - 점프 체인
  - tail call
  - 꼬리 호출
  - goto
aliases:
  - jmp가 뭐임
  - 무조건 점프가 뭐임
  - 조건 없는 분기
  - unconditional branch
symptom_keywords:
  - 왜 조건도 없이 점프함
  - switch문이 점프 테이블로 바뀜
  - jmp가 계속 jmp로 이어짐
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`JMP`는 조건 검사 없이 무조건 RIP(다음 실행할 명령의 주소)를 목표 주소로 바꾸는 명령어다. `Jcc`(조건 분기)와 달리 항상 분기하며, `CALL`과 달리 스택에 반환 주소를 남기지 않는다.

## 언제 검색해야 하나
- 어셈블리에 `jmp short loc_401050`, `jmp rax`, `jmp qword ptr [rcx+rdx*8]` 같은 코드가 나오는데 왜 조건도 없이 그냥 분기하는지 헷갈릴 때
- 함수 끝부분에 `call`이 아니라 `jmp`로 다른 함수를 부르는 것처럼 보이는 코드(tail call)를 만났을 때
- `switch`문처럼 보이는 C 코드가 컴파일된 결과에서 `jmp [reg*8 + 주소]`와 그 앞에 낯선 주소 배열이 있는 걸 봤을 때
- CALL을 JMP로(또는 반대로) 패치하려는데 스택이 깨질까 봐 걱정될 때
- IDA 그래프 뷰에서 JMP가 JMP로, 또 JMP로 계속 이어지는 지저분한 흐름을 만났을 때

## 핵심 개념

### JMP가 실제로 하는 일
`JMP target`은 단 하나의 일만 한다: **RIP를 target 주소로 설정한다.** 그게 전부다. 스택을 건드리지 않고, 플래그도 읽거나 바꾸지 않는다. `CALL`이 "반환 주소를 PUSH하고 이동"하는 것과 달리, JMP는 "그냥 이동"이다 — 그래서 JMP로 이동한 곳에서 원래 자리로 "돌아올" 방법이 원칙적으로 없다(누군가 스택에 직접 반환 주소를 만들어두지 않는 한).

### Intel 문법과 오퍼랜드 형태
```asm
JMP rel8         ; short jump — 목표가 현재 위치에서 -128~+127 바이트 이내일 때 (2바이트 인코딩)
JMP rel32        ; near jump — 그보다 멀리 떨어진 목표 (5바이트 인코딩)
JMP reg          ; 예: jmp rax — 레지스터 값을 목표 주소로 사용 (indirect)
JMP [mem]        ; 예: jmp qword ptr [rax+8] — 메모리에서 목표 주소를 읽어와 사용 (indirect)
JMP [table+idx*8]; 점프 테이블 인덱싱 — switch-case에서 흔히 등장 (indirect)
JMP far ptr seg:offset  ; far jump — 세그먼트까지 바꾸는 점프. 유저모드 리버싱에서는 거의 안 보임
```
오퍼랜드는 하나뿐이며, MOV처럼 "목적지/출발지" 개념이 없다 — 오퍼랜드 자체가 곧 "어디로 갈지"다.

### 레지스터/메모리/스택 효과
- RIP(EIP)만 바뀐다.
- RSP는 **전혀 변하지 않는다.** 이 점이 CALL과의 가장 중요한 차이다 — CALL은 실행 시 RSP가 8만큼(x64 기준) 줄어들며 반환 주소가 스택에 쌓이지만, JMP는 스택에 아무것도 쓰지 않고 그냥 이동만 한다.
- 플래그 레지스터도 전혀 건드리지 않는다 — JMP는 플래그를 읽지도(Jcc처럼 조건 검사를 하지 않으므로) 쓰지도 않는다.

### 컴파일러가 JMP를 만드는 대표 패턴

**1) 반복문의 뒤쪽 화살표(back-edge)**
```c
while (cond) { body(); }
```
컴파일러는 보통 조건 검사를 반복문 끝으로 옮기고, 몸통이 끝난 뒤 조건 검사 위치로 무조건 되돌아가는 `JMP`(또는 조건부로 되돌아가는 `Jcc`)를 만든다. 아래 "if/else" 예제와 함께 보면 감이 온다.

**2) if/else의 else 블록 건너뛰기**
```c
if (cond) { A(); } else { B(); }
```
컴파일러는 조건이 거짓이면 A블록을 건너뛰는 `Jcc`를 만들고, A블록이 끝나는 지점에 B블록 전체를 건너뛰는 **무조건** `JMP`를 넣는다:
```asm
    test  eax, eax
    jz    else_branch     ; 조건부 분기 (Jcc) — 거짓이면 else로
    call  A
    jmp   end_if           ; 무조건 분기 (JMP) — A를 실행했으면 else를 건너뜀
else_branch:
    call  B
end_if:
```

**3) 꼬리 호출 최적화(Tail Call Optimization)**
함수 맨 마지막 동작이 "다른 함수를 호출하고 그 결과를 그대로 반환하는 것"뿐이라면, 컴파일러는 `CALL other_func` + `RET` 대신 그냥 `JMP other_func`로 바꿔버린다. `other_func`가 끝나면 `other_func`의 `RET`이 (현재 함수가 아니라) **현재 함수를 호출한 쪽**으로 바로 돌아간다 — 스택에 현재 함수의 프레임이 남아있지 않기 때문에 가능한 최적화다. 이 패턴은 rev-0071-call.md의 "흔한 실수"에서도 다룬다 — CALL과 JMP를 혼동하면 이런 코드에서 "왜 함수가 안으로 안 들어가지?" 하고 헷갈리게 된다.

**4) 스위치-케이스 점프 테이블**
```c
switch (n) {
    case 0: A(); break;
    case 1: B(); break;
    case 2: C(); break;
}
```
case 값들이 촘촘하게 이어져 있으면(예: 0,1,2,3...) 컴파일러는 각 case의 코드 주소를 담은 **테이블**을 `.rodata`나 `.text`에 만들어두고, `n` 값으로 그 테이블을 인덱싱해서 바로 해당 case로 점프한다:
```asm
cmp   eax, 2          ; 범위 체크 (n <= 2 인지)
ja    default_case
lea   rcx, [rip+jump_table]
movsxd rdx, eax
jmp   qword ptr [rcx+rdx*8]   ; 테이블에서 목표 주소를 읽어 그 자리로 점프
```
IDA/Ghidra에서 `jmp [reg*8+주소]` 형태가 보이고 그 근처(대개 `.rodata`)에 코드 주소로 보이는 값들이 줄지어 있다면 이게 점프 테이블이다. 이 패턴 자체를 처음부터 끝까지 손으로 읽는 방법은 더 깊이 있게 다루는 별도 글(스위치-케이스 점프 테이블, 예정)에서 다룬다 — 여기서는 "JMP의 오퍼랜드가 계산된 메모리 주소일 수 있다"는 것만 기억해두면 된다.

### IDA/Ghidra 디컴파일에서 보이는 모습
- **앞으로 가는(forward) 무조건 JMP**가 단순히 두 코드 블록을 합치는 용도라면, 디컴파일러는 이를 아예 없애고 그냥 이어붙인 직선 코드나 `if/else` 구조로 재구성해서 보여준다 — 즉 디컴파일 결과에는 JMP 자체가 안 보이는 경우가 많다.
- **뒤로 가는(backward) 무조건 JMP**는 대부분 `while(1)`이나 `for(;;)` 같은 반복문의 되돌아가는 화살표로 해석되어 `while`/`for` 구문으로 표시된다.
- **점프 테이블을 통한 간접 JMP**는 디컴파일러가 인식에 성공하면 깔끔한 `switch` 문으로 재구성해준다.
- **레지스터/메모리 기반 간접 JMP를 디컴파일러가 정적으로 못 풀어내면**, 함수 흐름이 끊기거나(그래프가 중간에 끊어짐), `switch` 인식에 실패하고 원본에 가까운 형태로 남는다. 이럴 때는 목표 주소가 담긴 메모리(테이블)를 직접 찾아 Xrefs나 Hex View로 그 위치의 데이터를 확인해야 한다.

### 리버싱에서의 의미 — JMP 체인과 난독화
`JMP → JMP → JMP → ...` 처럼 의미 없는 JMP가 여러 번 이어지는 코드를 종종 보게 된다. 이는 컴파일러 최적화의 부작용일 수도 있지만, 난독화 도구가 **일부러** 짧은 JMP 조각들을 여기저기 흩어놓아 그래프 뷰를 지저분하게 만들고 정적 분석을 방해하는 기법(control-flow obfuscation)으로도 흔히 쓰인다. 이런 경우 IDA에서 여러 JMP를 하나하나 따라가며 "결국 최종적으로 어디로 가는지"를 확인하는 수밖에 없다.

## 화면/코드에서 보이는 징후
- `jmp short loc_401030` — 가까운 곳으로의 무조건 분기 (반복문 되돌아가기 등)
- `jmp loc_402000` — near jump, 좀 더 먼 목표
- `jmp rax` — 레지스터 기반 간접 점프 (함수 포인터, 트램폴린 코드)
- `jmp qword ptr [rcx+rdx*8]` — 점프 테이블을 통한 간접 점프 (switch-case 의심)
- 함수 맨 끝(에필로그 자리, `leave`/`pop rbp` 이후가 아니라 그 자리를 대신해서)에 `jmp other_func` — tail call
- 짧은 JMP 여러 개가 연쇄적으로 이어짐 — 난독화 의심

## 가장 먼저 할 것
1. JMP 앞에 조건 검사(`cmp`/`test` + `Jcc`)가 있는지 확인한다 — 있다면 이 JMP는 그 if/else의 "else 건너뛰기" 부분일 가능성이 크다.
2. 오퍼랜드가 상수 주소(direct)인지 레지스터/메모리(indirect)인지 구분한다.
3. 목표 주소가 현재 코드보다 **앞쪽**(작은 주소)이면 반복문의 되돌아가기, **뒤쪽**(큰 주소)이면 건너뛰기 패턴일 가능성이 높다.
4. 함수의 맨 끝자리에 있다면 tail call인지 확인한다(RET/LEAVE 없이 바로 JMP로 함수가 끝나는가).

## 단계별 절차

**1) 단순 무조건 분기 — 반복문 되돌아가기**
```asm
loop_top:
    ; ... 반복 몸통 ...
    dec  ecx
    test ecx, ecx
    jnz  loop_top     ; (참고: 이건 Jcc다. 순수 JMP 예시는 아래 참고)
```
반복 조건이 항상 참인 `while(1)` 패턴이면 조건 없이 그냥:
```asm
loop_top:
    ; ... 몸통 ...
    jmp  loop_top      ; 무조건 되돌아가기
```

**2) if/else 건너뛰기 패턴 읽기**
위 "핵심 개념" 2번 예제를 다시 보면서, `jz else_branch`(조건부)와 `jmp end_if`(무조건)를 구분해서 읽는다. 각 라벨(`else_branch:`, `end_if:`)이 정확히 어디를 가리키는지 IDA에서 더블클릭해 따라가 본다.

**3) Tail call 확인**
```asm
sub_401000:
    mov  rcx, rdx
    jmp  sub_402000    ; call/ret 대신 그냥 jmp로 끝남 — tail call
```
디버거로 `sub_401000`에 진입해 `jmp sub_402000`까지 실행한 뒤 `sub_402000`이 끝나면 콜스택에서 `sub_401000`이 아니라 그보다 더 위의 호출자로 바로 돌아가는지 확인해보면 tail call임을 체감할 수 있다.

**4) 점프 테이블 따라가기**
```asm
jmp qword ptr [rcx+rdx*8]
```
IDA에서 `rcx`가 가리키는 주소(점프 테이블 시작)를 Hex View나 데이터 뷰로 연다. 8바이트씩 끊어 읽으면 각 항목이 코드 주소들이다. `rdx`(인덱스)가 0일 때 첫 항목, 1일 때 두 번째 항목… 순서로 어떤 case로 가는지 계산해본다. IDA가 자동으로 switch를 인식했다면 그래프 뷰에서 여러 갈래로 갈라지는 노드로 이미 예쁘게 그려져 있을 것이다.

## 명령어/단축키
- IDA: JMP 대상 라벨 위에서 `Enter`(또는 더블클릭)로 그 위치로 이동, `Esc`로 이전 위치로 복귀, 그래프 뷰에서 화살표 색으로 분기 방향 확인(초록/빨강은 조건부 Jcc의 참/거짓 경로, 파랑은 무조건 JMP 경로), 점프 테이블 주소 위에서 `D`를 눌러 데이터로 변환 후 배열처럼 보기
- x64dbg: JMP 라인 우클릭 → "Follow in Disassembler"로 목표 주소로 이동, 그래프 뷰(우클릭 → Graph)로 분기 구조 시각화
- GDB/Pwndbg: `x/10gx <table_addr>`로 점프 테이블 메모리를 8바이트씩 10개 덤프, `stepi`로 JMP 실행 후 `$rip`가 정확히 예상 주소로 바뀌었는지 확인

## 출력 해석
- IDA 그래프 뷰에서 화살표가 **파란색**이면 조건 없는 흐름(무조건 JMP 또는 다음 명령으로의 자연스러운 흐름), **초록/빨강**이면 Jcc의 참/거짓 분기다. 파란 화살표만 있는데 원래 코드에 조건이 있어야 할 것 같다면, 컴파일러가 최적화로 조건을 단순화했거나 애초에 무조건 분기가 맞는 것이다.
- 점프 테이블 항목을 덤프했을 때 나오는 값들이 모두 `.text` 섹션 범위 안의 유효한 코드 주소처럼 보인다면 switch-case 테이블이 맞다는 강한 신호다.
- 디컴파일러가 JMP를 아예 안 보여주고 곧바로 `if/else`나 `while`로 표시했다면, 정상적으로 제어 흐름을 재구성한 것이니 걱정할 필요 없다 — 원본 어셈블리를 볼 때만 JMP가 직접 보인다.

## 흔한 실수
- **JMP를 CALL과 혼동해서 "여기서 실행하고 다시 돌아올 것"이라고 착각하는 것** — JMP는 반환 주소를 스택에 남기지 않으므로 절대 자동으로 돌아오지 않는다. 패치 작업 중 CALL을 JMP로 바꾸면(또는 반대로) 스택 균형이 깨져 이후 RET이 엉뚱한 주소로 돌아가며 프로그램이 크래시하거나 이상하게 동작한다.
- **빠르게 코드를 훑다가 Jcc(`je`, `jnz` 등)를 JMP로 착각하는 것** — JMP는 조건 접미사가 없는 순수 3글자(`jmp`)이고, Jcc는 항상 조건을 뜻하는 접미사(`e`, `ne`, `z`, `g`, `a` 등)가 붙는다. 니모닉을 항상 정확히 확인하는 습관이 중요하다.
- **간접 JMP(`jmp rax` 등)를 보고 "이 함수가 여기서 끝난다"고 단정하는 것** — 목표가 무엇인지 확인하지 않고 넘어가면 실제로는 다른 함수로 tail call되어 흐름이 계속 이어지고 있는데도 분석을 중단해버리는 실수를 하게 된다.
- **점프 테이블의 인덱스 범위 체크(`cmp`+`ja default_case` 같은 코드)를 놓치고 테이블만 보는 것** — 실제 case 개수와 테이블 인덱싱 범위를 맞춰보지 않으면 존재하지 않는 case를 만들어내거나 default 분기를 놓칠 수 있다.

## 막혔을 때 다음 체크
- 간접 JMP의 목표가 계속 레지스터/메모리라서 정적으로 안 보이면 → 디버거로 브레이크포인트를 걸고 실행 중 실제 값을 확인한다.
- JMP 체인이 너무 길어서 최종 목적지를 못 찾겠다면 → 각 JMP 라벨을 순서대로 적어가며 손으로 따라가거나, 디버거로 `stepi`를 반복하며 `$rip`가 최종적으로 어디서 멈추는지 관찰한다.
- 점프 테이블처럼 보이는데 IDA가 switch로 인식하지 못했다면 → 테이블 시작 주소에서 `D`(데이터로 변환) 후 8바이트씩 끊어 배열로 만들고, 각 항목 위에서 `C`(코드로 변환)를 눌러 IDA가 그 위치를 함수/코드로 인식하게 도와준다.
- Tail call인지 일반 direct call인지 헷갈리면 → 함수 맨 끝에 `leave`/`pop rbp`/`ret`이 전혀 없이 곧바로 `jmp`로 끝나는지 확인한다. 있으면 그냥 일반 분기(반복문 등)일 수 있다.

## 미니 예제

**예제 1 — 반복문 되돌아가기 (무조건 JMP)**
```c
for (;;) { do_work(); }
```
```asm
loop_start:
    call do_work
    jmp  loop_start     ; 무조건 되돌아가기, 스택/플래그 변화 없음
```

**예제 2 — if/else의 else 건너뛰기**
```c
if (x == 0) a(); else b();
```
```asm
    test eax, eax
    jnz  else_branch    ; 조건부 (Jcc)
    call a
    jmp  end_if          ; 무조건 (JMP) — else를 건너뜀
else_branch:
    call b
end_if:
```

**예제 3 — 꼬리 호출(Tail Call)**
```c
int wrapper(int x) { return real_func(x); }
```
```asm
wrapper:
    ; 인자(x)는 이미 RCX/RDI에 있으므로 그대로 둔 채
    jmp  real_func       ; call+ret 대신 jmp로 대체 — real_func의 ret이 wrapper의 호출자로 바로 감
```

**예제 4 — 점프 테이블 (switch-case)**
```c
switch (op) {
    case 0: return add(a,b);
    case 1: return sub(a,b);
    case 2: return mul(a,b);
    default: return -1;
}
```
```asm
    cmp   edi, 2
    ja    default_case
    lea   rcx, [rip+jtable]
    movsxd rdx, edi
    jmp   qword ptr [rcx+rdx*8]   ; 테이블에서 목표를 읽어 해당 case로 점프
jtable:
    dq offset case0
    dq offset case1
    dq offset case2
```

## 관련 글
- ./rev-0071-call.md — CALL: 함수 호출, 반환 주소, 인자 추적 (JMP와의 차이, tail call)
- ./rev-0067-je-jz.md — JE/JZ: ZF가 1일 때 분기
- ./rev-0068-jne-jnz.md — JNE/JNZ: ZF가 0일 때 분기
- ./rev-0069-jg-jge-jl-jle.md — JG/JGE/JL/JLE: Signed 비교 분기
- ./rev-0070-ja-jae-jb-jbe.md — JA/JAE/JB/JBE: Unsigned 비교 분기
- ./rev-0088-flags-overview.md — 플래그 레지스터 전체 개요
- REV-0072 — RET: 함수 반환과 스택 변화
- REV-0073 — LEAVE: 함수 에필로그와 스택 프레임
- 스위치-케이스 점프 테이블 (예정)

## 출처/검증
- JMP 명령어 동작(short/near/far, direct/indirect 형태), 플래그 미변경: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "JMP—Jump" 섹션 기준 (2026-09-08 검증).
- 꼬리 호출 최적화와 스위치 점프 테이블 코드 생성 패턴: 컴파일러(GCC/Clang/MSVC) 최적화 관행에 대한 일반적인 리버싱/컴파일러 문헌 기준.
