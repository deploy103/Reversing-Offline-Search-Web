---
id: REV-0441
title: "Switch문 점프 테이블(Jump Table) 완전 분석"
slug: "rev-0441-switch-jump-table"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - jump table
  - 점프 테이블
  - switch문 어셈블리
  - switch case 컴파일
  - "jmp [rax*4+table]"
  - jtable
  - indirect jump table
  - 분기 테이블
  - dense switch
  - sparse switch
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - 점프테이블이 뭐임
  - switch문이 어떻게 컴파일됨
  - jump table 분석하는 법
  - "jmp [reg*4+addr]가 뭐임"
  - switch 최적화 어셈블리
symptom_keywords:
  - switch문이 어셈블리에서 안 보임
  - jmp 대상이 테이블 주소임
  - ida가 switch를 자동으로 못 알아봄
  - 점프 테이블을 수동으로 지정해야 함
last_verified: "2026-09-08"
---

## 한 줄 요약
`switch` 문의 case 값이 촘촘하게 이어져 있으면 컴파일러는 `if-else` 체인 대신 **케이스 값을 인덱스로 삼아 목적지 주소 배열을 한 번에 점프**하는 점프 테이블을 만드는데, 어셈블리에서는 `cmp`(범위 체크) 직후 `jmp [reg*4+table]` 형태로 나타난다.

## 언제 검색해야 하나
- 디스어셈블리에 `jmp` 대상이 레지스터나 `[rax*4+addr]`처럼 계산된 주소로 나와서 "어디로 뛰는지" 바로 안 보일 때
- IDA/Ghidra가 자동으로 `switch(x) { case ...: }` 형태로 예쁘게 디컴파일해주는데 그 근거가 되는 원본 어셈블리를 이해하고 싶을 때
- 메뉴 선택형 크랙미("1. 입력 2. 확인 3. 종료")에서 옵션 처리 로직이 어디서 갈라지는지 빠르게 찾고 싶을 때
- IDA가 점프 테이블을 자동으로 인식하지 못해서 `jmp rax` 아래 코드가 함수처럼 안 보이고 깨져 있을 때(수동으로 테이블을 지정해야 하는 상황)

## 핵심 개념

### switch가 항상 점프 테이블이 되는 건 아니다
컴파일러는 `switch`의 case 값 분포를 보고 세 가지 전략 중 하나를 고른다.
1. **점프 테이블(Jump Table)**: case 값들이 촘촘하게 이어져 있을 때(예: `case 0`~`case 7`처럼 연속되거나 빈틈이 적을 때). 인덱스 하나로 O(1) 시간에 목적지를 찾는다.
2. **이진 탐색(binary search) 트리**: case 값이 듬성듬성(sparse) 흩어져 있을 때. `cmp`/`jg`/`jl`을 이용해 값의 범위를 절반씩 좁혀가며 분기한다(REV-0069 참고).
3. **혼합형**: 값이 몇 개의 촘촘한 구간으로 뭉쳐 있으면, 구간별로는 점프 테이블을 쓰고 구간 사이는 이진 탐색이나 순차 비교로 연결한다.

즉 어셈블리에 점프 테이블이 안 보인다고 해서 원본 코드에 `switch`가 없었다고 단정하면 안 된다 — case 값 분포에 따라 완전히 다른 모양으로 컴파일된다.

### 전형적인 어셈블리 구조 (x64 SysV, PIE)
```asm
; switch (x) { case 0: ... case 1: ... ... case 4: ... default: ... }
cmp     edi, 4
ja      default_case          ; unsigned 비교 한 방으로 "0보다 작음"과 "4보다 큼"을 동시에 걸러냄
movsxd  rax, edi               ; 인덱스를 64비트로 부호 확장(REV-0041)
lea     rdx, [rip+jump_table]  ; 테이블 시작 주소(RIP 상대, REV-0439)
movsxd  rax, dword ptr [rdx+rax*4]  ; 테이블에서 "RIP 기준 상대 오프셋"을 읽음 (PIE 표준 패턴)
add     rax, rdx               ; 상대 오프셋 + 테이블 주소 = 실제 목적지
jmp     rax                    ; 계산된 주소로 점프

jump_table:
    dd  case0 - jump_table
    dd  case1 - jump_table
    dd  case2 - jump_table
    dd  case3 - jump_table
    dd  case4 - jump_table
```
핵심 순서는 항상 **① 범위 체크(`cmp`+`ja`/`jbe`) → ② 인덱스 확장/스케일 → ③ 테이블에서 목적지 읽기 → ④ 간접 `jmp`** 다. 범위 체크에서 `unsigned` 비교(`ja`, REV-0070)를 쓰는 이유는, `x`가 음수인 경우도 `unsigned`로 보면 아주 큰 값이 되어 "범위를 벗어남" 조건 하나로 자연스럽게 걸러지기 때문이다(부호 있는 값의 하한/상한을 따로 검사할 필요가 없어짐).

### 32비트/비-PIE 바이너리에서는 더 단순하다
재배치가 자유로운 32비트나 PIE가 아닌 바이너리에서는 테이블이 **절대 주소**를 직접 담고, 계산도 더 짧다.
```asm
cmp     eax, 4
ja      default_case
jmp     dword ptr [eax*4 + jump_table]   ; 테이블 원소 = 목적지의 절대 주소
```
x64 PIE 바이너리가 굳이 "RIP 상대 오프셋을 읽고 더하는" 한 단계를 더 거치는 이유는, 테이블 자체도 재배치 없이 위치 독립적으로 만들기 위해서다(절대 주소를 담으면 로드 위치가 바뀔 때마다 테이블도 재배치해야 함).

### IDA/Ghidra에서의 인식과 표시
IDA는 이 패턴(범위 체크 + 계산된 `jmp`)을 자동으로 인식하면, `jmp`가 있던 자리에 **점프 테이블(jtable_xxx로 이름 붙은 배열)** 을 만들고, 디스어셈블리 화면에 "switch jump table for switch statement"라는 주석과 함께 각 case로 가는 화살표들을 보여준다. F5로 디컴파일하면 완전히 자연스러운 `switch (x) { case 0: ...; case 1: ...; default: ...; }` 형태로 재구성된다. Ghidra도 동일하게 자동 switch 분석 기능이 있다.

**자동 인식이 실패하는 경우**도 흔하다 — 테이블이 암호화/난독화되어 있거나, 컴파일러가 흔치 않은 스케일을 쓰거나, 코드가 손으로 짜여진 경우다. 이럴 때는 `jmp rax` 아래 코드가 하나의 이어진 함수로 인식되지 않고 조각조각 끊겨 보인다. 수동으로 고치려면:
1. 테이블로 추정되는 데이터 영역에서 `D` 키로 데이터를 재해석하거나, 배열로 지정한다.
2. `jmp`가 있는 라인에서 우클릭 → **"Create Switch/jump table"**(IDA) 또는 Edit → Other → Specify New/Edit jump table을 선택해서, IDA에게 테이블의 시작 주소, 원소 개수, 원소 크기, base 조정 방식을 직접 알려준다.
3. 완료하면 나머지는 자동 인식된 것과 동일하게 표시된다.

### 다른 패턴과 헷갈리지 않기 — vtable과의 차이
점프 테이블과 vtable(REV-0444)은 둘 다 "메모리에서 주소를 읽어 간접 분기"한다는 점에서 겉보기에 비슷하지만 본질이 다르다.
- **점프 테이블**: 원소들이 **같은 함수 내부**의 여러 기본 블록(basic block) 주소를 가리킨다. 대상은 `jmp`(반환 주소를 남기지 않음)로 이동한다.
- **vtable**: 원소들이 **서로 다른, 완전히 독립적인 함수**의 시작 주소를 가리킨다. 대상은 `call`(반환 주소를 남김)로 호출된다.

`jmp [reg*4+addr]`이면 점프 테이블, `call [reg*8+addr]`이나 이중 역참조(`mov rax,[rcx]; call [rax+offset]`)면 vtable일 가능성이 높다는 규칙으로 우선 구분하고, 애매하면 테이블 원소가 가리키는 주소들이 한 함수 안에 몰려있는지(점프 테이블) 서로 다른 함수 시작 지점들인지(vtable) 직접 확인한다.

### 리버싱 관점에서의 의미
CTF 크랙미의 "메뉴 선택" 로직(`1) 입력 2) 검증 3) 종료`)은 거의 항상 switch문으로 짜여지고, 옵션 개수가 적으면 점프 테이블로 컴파일된다. 점프 테이블을 찾으면 **한 번에 모든 case 핸들러의 시작 주소를 알 수 있어서**, 문자열이나 xref를 일일이 따라가지 않고도 전체 메뉴 구조를 빠르게 파악할 수 있다. 또한 범위 체크(`cmp`+`ja`)가 없거나 우회 가능하다면(버그가 있는 코드), 잘못된 인덱스로 테이블 범위 밖의 임의 주소로 점프하는 취약점(out-of-bounds jump)이 될 수 있다는 점도 pwn 계열 문제에서 중요하다.

## 화면/코드에서 보이는 징후
- `cmp reg, N` 다음에 `ja`/`jbe`/`jnbe` 같은 unsigned 분기가 곧바로 이어짐(범위 체크)
- 그 직후 `jmp [reg*4+addr]` 또는 `movsxd`/`add`를 거쳐 `jmp reg`로 마무리
- `.rodata`/`.text`에 `dd`(4바이트) 값들이 촘촘히 나열된 데이터 블록(테이블 그 자체)
- IDA 그래프 뷰에서 하나의 블록에서 여러 개의 화살표가 동시에 뻗어나가는 모양

## 가장 먼저 할 것
1. `jmp`(또는 `call`) 대상이 레지스터/메모리 계산식인지 확인하고, 그 앞에 범위 체크(`cmp`+`ja`류)가 있는지 찾는다.
2. 범위 체크의 상수(N)를 확인해서 case 개수(대략 N+1개, default 포함)를 가늠한다.
3. IDA가 이미 자동으로 `switch` 문으로 디컴파일했는지 F5로 먼저 확인하고, 실패했으면 수동 지정이 필요하다고 판단한다.

## 단계별 절차
1. `cmp`/`ja` 같은 범위 체크가 점프 테이블 직전에 있는지 확인한다(case 값 범위를 벗어나면 default로 감).
2. `jmp [table + idx*8]`(또는 4) 형태의 간접 점프를 찾는다.
3. 테이블 시작 주소(`table`)를 Hex View/데이터 뷰로 열어 8(또는 4)바이트씩 끊어 읽으며 각 항목이 가리키는 코드 주소를 나열한다.
4. 각 코드 주소로 이동해 그 case의 실제 동작을 확인하고, 인덱스 0부터 순서대로 어떤 case에 대응하는지 표로 정리한다.

## 명령어/단축키
- IDA: `jmp` 라인에서 우클릭 → **"Create Switch/jump table"**, 함수 목록에서 `jtable_` 접두사로 자동 생성된 테이블 확인. 그래프 뷰는 `스페이스바`로 전환.
- Ghidra: Analysis → Auto Analyze로 switch 분석기가 자동 실행되며, 실패 시 테이블 데이터를 우클릭 → "Data" → 배열로 재정의 후 `Override Jump Table`.
- x64dbg: `jmp rax` 지점에 브레이크포인트를 걸고 RAX 값을 확인해 실제 목적지를 동적으로 검증.

## 흔한 실수
- 점프 테이블을 vtable/함수 포인터 배열과 같은 것으로 착각하는 것 — 앞서 설명한 대로 대상이 같은 함수 내부인지, 여러 다른 함수인지로 구분해야 한다.
- x64 PIE 바이너리의 테이블 원소를 **절대 주소**로 착각해서 그대로 읽고 마는 것 — 실제로는 "테이블 시작 기준 상대 오프셋(32비트)"이 들어있으므로, 반드시 테이블 base를 더해야 진짜 목적지가 나온다.
- 범위 체크(`cmp`+`ja`/`jbe`)를 못 보고 지나쳐서, 각 case가 왜 "0~4"로 제한되는지 놓치는 것 — 이 비교문이 사실상 switch의 case 개수와 default 분기 조건을 알려주는 핵심 단서다.
- IDA가 점프 테이블을 자동 인식하지 못했을 때 "이 코드는 분석 불가능하다"고 포기하는 것 — 수동으로 "Create Switch/jump table"을 지정하면 대부분 정상 인식된다.

## 막혔을 때 다음 체크
- 테이블 원소가 함수가 아니라 다른 함수 시작 주소들처럼 보이면 → vtable(REV-0444)일 가능성을 다시 검토한다.
- 테이블 base 계산에 쓰인 RIP 상대 주소 계산이 헷갈리면 → REV-0439.
- 범위 체크에 쓰인 unsigned 비교(`ja`)의 의미가 헷갈리면 → REV-0070.
- IDA 그래프 뷰에서 여러 분기가 뒤엉켜 보여 구조 파악이 힘들면 → REV-0150.

## 미니 예제

**예제 1 — 원본 C 코드**
```c
switch (choice) {
    case 0: do_add();    break;
    case 1: do_sub();    break;
    case 2: do_mul();    break;
    case 3: do_div();    break;
    case 4: do_exit();   break;
    default: puts("invalid"); break;
}
```

**예제 2 — x64 PIE 어셈블리 (전체)**
```asm
cmp     edi, 4
ja      .default
movsxd  rax, edi
lea     rdx, [rip+jtable]
movsxd  rax, dword ptr [rdx+rax*4]
add     rax, rdx
jmp     rax

case0: call do_add
       jmp .end
case1: call do_sub
       jmp .end
; ...
.default:
       lea rdi, [rip+invalid_str]
       call puts
.end:
       ret

jtable:
    dd case0 - jtable
    dd case1 - jtable
    dd case2 - jtable
    dd case3 - jtable
    dd case4 - jtable
```

**예제 3 — IDA Hex-Rays 디컴파일 결과**
```c
switch ( choice )
{
  case 0: do_add(); break;
  case 1: do_sub(); break;
  case 2: do_mul(); break;
  case 3: do_div(); break;
  case 4: do_exit(); break;
  default: puts("invalid"); break;
}
```
원본과 사실상 동일하게 복원된다 — IDA가 자동 인식에 성공한 대표적인 경우다.

**예제 4 — 비-PIE/32비트 단순형**
```asm
cmp     eax, 4
ja      default_case
jmp     dword ptr [eax*4 + 00403010h]   ; 테이블 원소가 절대 주소 그 자체
```

## 관련 글
- REV-0442 — 스택 카나리(Stack Canary) 체크 시퀀스 분석
- REV-0444 — vtable과 가상함수 호출 패턴 분석
- REV-0066 — JMP: 무조건 분기
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0439 — RIP 상대 주소 지정 방식(RIP-relative addressing)
- REV-0150 — IDA Graph View에서 분기 읽기

## 출처/검증
- 간접 점프와 SIB 기반 테이블 인덱싱(`jmp [reg*scale+table]`) 인코딩: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "JMP—Jump" 및 "2.1.5 Addressing-Mode Encoding of ModR/M and SIB Bytes" 기준 (2026-09-09 검증).
- switch문의 점프 테이블 vs 이진 탐색 vs 혼합 전략 선택: GCC/Clang(LLVM) 공식 최적화 문서 및 IDA/Ghidra의 switch 자동 인식(jump table analysis) 공식 문서 기준.
