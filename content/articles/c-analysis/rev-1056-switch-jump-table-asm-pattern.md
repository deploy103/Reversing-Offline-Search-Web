---
id: REV-1056
title: "switch-case가 점프 테이블로 컴파일되는 패턴"
slug: "rev-1056-switch-jump-table-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["switch 점프 테이블 어셈블리", "switch jump table c code", "dense switch case asm"]
aliases: ["switch문이 점프 테이블로 컴파일되는 예", "case 값이 촘촘할 때 switch 어셈블리", "switch 점프 테이블 C 코드 대조"]
symptom_keywords: ["switch case가 촘촘한데 jmp 하나로 처리되는 이유를 모르겠음", "case 값과 테이블 인덱스 대응이 헷갈림"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-INTEL-SDM"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`case` 값들이 0부터 촘촘하게(빈틈 없이 또는 빈틈이 적게) 이어져 있으면 컴파일러는 `switch` 변수 값을 그대로 배열 인덱스로 써서 목적지 주소 테이블을 한 번에 조회하는 **점프 테이블**을 만들며, 어셈블리에서는 범위 체크(`cmp`+`ja`) 뒤에 `jmp`가 레지스터나 계산된 메모리 주소를 대상으로 하는 것으로 나타난다.

## 언제 검색해야 하나
- `switch` 문 C 코드를 눈으로 보고 있는데, 실제 어셈블리에서는 각 case별 `cmp`가 하나도 안 보이고 `jmp` 한 줄로 바로 여러 곳으로 갈라지는 걸 봤을 때
- case 값이 0, 1, 2, 3, 4처럼 연속된 정수인 switch문을 분석하면서 "이게 왜 if 체인이 아니라 이런 모양인지" 원리부터 이해하고 싶을 때
- REV-0441에서 점프 테이블 자체는 배웠지만, 원본 C `switch` 코드와 나란히 놓고 대조해서 확인하고 싶을 때

## 핵심 개념

### 원본 C 코드
```c
int op_name(int code) {
    switch (code) {
        case 0: return 100;
        case 1: return 101;
        case 2: return 102;
        case 3: return 103;
        case 4: return 104;
        default: return -1;
    }
}
```

### -O0 x86-64 어셈블리 (x64 PIE 기준, Intel 문법)
```asm
op_name:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-4], edi        ; code
    mov     eax, [rbp-4]
    cmp     eax, 4
    ja      .L_default           ; code가 0~4 범위를 벗어나면(unsigned 비교) default
    lea     rdx, [rip+.L_jtable]
    movsxd  rax, dword [rdx+rax*4]  ; 테이블에서 상대 오프셋 읽기
    add     rax, rdx
    jmp     rax                   ; 계산된 주소로 간접 점프
.L_case0:
    mov     eax, 100
    jmp     .L_end
.L_case1:
    mov     eax, 101
    jmp     .L_end
.L_case2:
    mov     eax, 102
    jmp     .L_end
.L_case3:
    mov     eax, 103
    jmp     .L_end
.L_case4:
    mov     eax, 104
    jmp     .L_end
.L_default:
    mov     eax, -1
.L_end:
    leave
    ret

.L_jtable:
    dd      .L_case0 - .L_jtable
    dd      .L_case1 - .L_jtable
    dd      .L_case2 - .L_jtable
    dd      .L_case3 - .L_jtable
    dd      .L_case4 - .L_jtable
```

### 줄 단위 대응
- `cmp eax, 4` / `ja .L_default` — `switch`의 **모든 case 값**(0~4)이 이 한 번의 범위 체크로 커버된다. 개별 case마다 `cmp code, 0`, `cmp code, 1` ... 하는 코드가 **전혀 없다** — 이게 if-elseif 체인(REV-1057, REV-1055)과의 가장 큰 시각적 차이다.
- `lea rdx, [rip+.L_jtable]` — 테이블 시작 주소를 RIP 상대로 계산.
- `movsxd rax, dword [rdx+rax*4]` — `code` 값을 인덱스로 그대로 써서(`rax*4`, 정수 4바이트 스케일) 테이블 원소(상대 오프셋)를 읽는다. **case 값이 곧 배열 인덱스**라는 점이 점프 테이블의 본질이다.
- `add rax, rdx` / `jmp rax` — 오프셋을 테이블 base에 더해 실제 목적지를 계산하고 그 주소로 바로 점프한다. `call`이 아니라 `jmp`이므로 반환 주소가 스택에 남지 않는다.
- 각 `.L_caseN` 블록 끝의 `jmp .L_end`는 REV-1054의 if-else에서 본 것과 같은 "합류 지점으로 가는 무조건 점프" 역할이다.

### 디컴파일러가 복원한 pseudocode
```c
int op_name(int code)
{
  switch (code) {
    case 0: return 100;
    case 1: return 101;
    case 2: return 102;
    case 3: return 103;
    case 4: return 104;
    default: return -1;
  }
}
```
IDA/Ghidra는 `cmp`+`ja`(범위 체크)와 그 뒤의 계산된 `jmp`를 자동으로 인식하면 `jtable_xxx`라는 이름의 데이터 배열을 만들고, `switch(code) { ... }` 구문으로 거의 원본과 동일하게 복원해준다. 다만 테이블이 암호화되어 있거나 컴파일러가 흔치 않은 스케일을 쓰면 자동 인식이 실패해서 `jmp rax` 아래 코드가 조각조각 끊겨 보일 수 있다 — 이때는 수동으로 점프 테이블을 지정해야 한다(자세한 수동 지정 절차는 REV-0441 참고).

## 화면/코드에서 보이는 징후
- `cmp reg, N` 다음 `ja`/`jbe` 같은 unsigned 조건부 분기(범위 체크) 하나만 있고, 개별 case 값에 대한 `cmp`가 없다.
- 그 직후 `lea`로 테이블 주소를 구하고, `movsxd`나 `mov`로 테이블 원소를 읽고, `add`/`jmp reg`로 마무리되는 3~4줄 조합.
- `.rodata`나 `.text` 안에 4바이트(또는 8바이트) 단위로 촘촘히 나열된 데이터 블록(테이블 자체).
- case 개수만큼의 짧은 블록들이 코드 뒤쪽에 나열되어 있고, 각 블록 끝이 공통 `.L_end`로 점프한다.

## 가장 먼저 할 것
`jmp` 대상이 상수 레이블이 아니라 레지스터나 `[reg*4+addr]` 같은 계산식인지 확인한다. 맞다면 그 바로 위에서 범위 체크(`cmp`+`ja`류)를 찾아 case 값의 범위(대략 0~N)를 먼저 파악한다.

## 단계별 절차
1. 간접 `jmp`(레지스터 또는 계산된 메모리 피연산자)를 찾는다.
2. 그 위의 `cmp`+조건부 분기로 case 값의 유효 범위와 default로 가는 경로를 확인한다.
3. 테이블 데이터 영역을 4(또는 8)바이트씩 끊어 읽어 각 원소가 가리키는 코드 블록 주소를 나열한다.
4. 인덱스 0부터 순서대로 각 블록을 case 값에 매칭시켜 표로 정리한다.
5. 각 블록의 실제 동작(반환값, 호출하는 함수 등)을 확인한다.

## 명령어/단축키
```
(gdb) disas op_name
(gdb) x/5xg &jtable      # 테이블 원소를 8바이트씩 덤프
(gdb) print $rax          # jmp 직전 계산된 목적지 확인
```
IDA: `jmp` 라인 우클릭 → "Create Switch/jump table"로 자동/수동 인식. Ghidra: Analysis → Auto Analyze의 switch 분석기가 자동 처리, 실패 시 데이터 재정의 후 override.

## 출력 해석
- `cmp eax, 4` / `ja`의 4는 "case 개수 - 1"이다. 이 상수만 보고도 대략 몇 개의 case가 있는지(default 제외) 짐작할 수 있다.
- 테이블 원소가 절대 주소가 아니라 "테이블 기준 상대 오프셋"으로 저장된 x64 PIE 환경에서는, 원소 값을 그대로 주소로 오해하면 안 되고 반드시 테이블 base를 더해야 한다.

## 흔한 실수
- case 값이 0부터 시작하지 않고(예: `case 10`부터 시작) 이어지는 경우, 컴파일러가 먼저 `sub eax, 10` 같은 코드로 최솟값을 빼서 인덱스를 0부터 시작하도록 정규화한다는 것을 놓치는 것 — 이 `sub`를 못 보면 case 값과 테이블 인덱스가 안 맞아 보인다.
- case 값 중 일부가 비어 있는 경우(예: 0,1,2,4는 있고 3이 없음) 테이블의 3번 원소가 default 블록을 가리키도록 채워지는데, 이걸 "테이블이 잘못됐다"고 오판하는 것 — 빈 case는 정상적으로 default를 가리키는 것이 맞다.
- `-O0`이 아닌 `-O2` 이상에서는 case가 몇 개 안 되면 오히려 점프 테이블 대신 `cmovcc` 체인이나 if 체인으로 역변환될 수 있다는 점(테이블 생성 자체의 오버헤드가 케이스 수가 적을 때는 더 크다고 판단되면). case가 20개 이상으로 많을 때 점프 테이블이 훨씬 확실하게 나타난다.
- 점프 테이블을 vtable(REV-0444)과 혼동하는 것 — 점프 테이블 원소는 같은 함수 내부의 블록을, vtable 원소는 서로 다른 함수의 시작 주소를 가리킨다.

## 막혔을 때 다음 체크
- 점프 테이블의 RIP 상대 오프셋 계산, PIE/비-PIE 차이, IDA 수동 지정 절차 등 더 깊은 내용은 → REV-0441(Switch문 점프 테이블(Jump Table) 완전 분석).
- case 값이 듬성듬성 떨어져 있어서 점프 테이블이 아니라 순차 비교로 컴파일된 경우가 궁금하면 → REV-1057(switch-case가 if 체인으로 컴파일되는 패턴).
- 범위 체크에 쓰인 unsigned 비교(`ja`)의 의미가 헷갈리면 → REV-0070(JA JAE JB JBE: Unsigned 비교 분기).
- 테이블 주소 계산에 쓰인 RIP 상대 주소 지정이 헷갈리면 → REV-0042(LEA: 주소 계산인데 왜 산술 연산처럼 보이는가).

## 미니 예제
문자를 소문자 알파벳 순서로 인덱싱해서 특수 처리하는 경우도 같은 원리로 컴파일된다.
```c
int vowel_code(char c) {
    switch (c) {
        case 'a': return 1;
        case 'b': return 2;
        case 'c': return 3;
        case 'd': return 4;
        default:  return 0;
    }
}
```
```asm
vowel_code:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-4], dil
    movzx   eax, byte [rbp-4]
    sub     eax, 0x61            ; 'a'(0x61)를 빼서 인덱스를 0부터 시작하도록 정규화
    cmp     eax, 3
    ja      .L_default
    lea     rdx, [rip+.L_jtable]
    movsxd  rax, dword [rdx+rax*4]
    add     rax, rdx
    jmp     rax
.L_case_a:
    mov     eax, 1
    jmp     .L_end
.L_case_b:
    mov     eax, 2
    jmp     .L_end
.L_case_c:
    mov     eax, 3
    jmp     .L_end
.L_case_d:
    mov     eax, 4
    jmp     .L_end
.L_default:
    mov     eax, 0
.L_end:
    leave
    ret
```
`sub eax, 0x61`이 case 값('a'~'d', 아스키 0x61~0x64)을 0~3으로 정규화하는 과정이며, 이 한 줄을 놓치면 테이블 인덱스가 case 값과 안 맞는 것처럼 보인다.

## 관련 글
- REV-0441 — Switch문 점프 테이블(Jump Table) 완전 분석
- REV-1057 — switch-case가 if 체인으로 컴파일되는 패턴(sparse case)
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0042 — LEA: 주소 계산인데 왜 산술 연산처럼 보이는가

## 출처/검증
- 점프 테이블 생성 조건(case 값이 촘촘할 때)과 SIB 기반 인덱싱, RIP 상대 오프셋 테이블 구조: Intel 64 and IA-32 Architectures Software Developer's Manual 및 GCC/Clang 실제 출력 기준.
- IDA/Ghidra의 switch 자동 인식(jump table analysis): Hex-Rays 및 Ghidra 공식 문서 기준 (2026-09-10 검증).
