---
id: REV-1057
title: "switch-case가 if 체인으로 컴파일되는 패턴(sparse case)"
slug: "rev-1057-switch-if-chain-sparse-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["switch sparse case 어셈블리", "switch if chain assembly", "switch case je 연속"]
aliases: ["switch가 점프 테이블이 안 되는 경우", "sparse switch 어셈블리", "switch case 값이 듬성듬성"]
symptom_keywords: ["switch인데 jmp 테이블이 안 보이고 cmp je가 계속 나옴", "switch case 값이 멀리 떨어져 있는데 어셈블리가 이상함"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-INTEL-SDM"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`case` 값들이 듬성듬성 떨어져 있으면(예: 10, 200, 5000처럼 간격이 크면) 점프 테이블을 만드는 게 오히려 메모리 낭비이므로 컴파일러는 각 case 값을 `cmp`+`je`로 하나씩 순서대로 비교하는 **if-else 체인과 똑같은 모양**으로 `switch`를 컴파일하며, 이 경우 원본이 `switch`였는지 `if-elseif`였는지 어셈블리만으로는 구분할 수 없다.

## 언제 검색해야 하나
- `switch` 문 C 코드를 보고 있는데 실제 어셈블리에는 점프 테이블도, 계산된 `jmp`도 없이 `cmp`+`je`가 케이스 개수만큼 연달아 나올 때
- REV-1056에서 배운 점프 테이블 패턴을 기대했는데 안 보여서 "이게 switch가 맞나" 헷갈릴 때
- case 값이 사용자 정의 상수(에러 코드, 매직 넘버 등)처럼 서로 멀리 떨어진 값일 때

## 핵심 개념

### 원본 C 코드
```c
int classify(int code) {
    switch (code) {
        case 10:   return 1;
        case 200:  return 2;
        case 5000: return 3;
        default:   return 0;
    }
}
```

### -O0 x86-64 어셈블리
```asm
classify:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-4], edi     ; code
    mov     eax, [rbp-4]
    cmp     eax, 10
    je      .L_case10
    cmp     eax, 200
    je      .L_case200
    cmp     eax, 5000
    je      .L_case5000
    jmp     .L_default
.L_case10:
    mov     eax, 1
    jmp     .L_end
.L_case200:
    mov     eax, 2
    jmp     .L_end
.L_case5000:
    mov     eax, 3
    jmp     .L_end
.L_default:
    mov     eax, 0
.L_end:
    leave
    ret
```

### 점프 테이블(REV-1056)과의 결정적 차이
```asm
; 점프 테이블 (REV-1056, case 값이 촘촘할 때)
cmp     eax, N        ; 범위 체크 딱 한 번
ja      .L_default
...테이블 조회...
jmp     rax            ; 목적지가 계산된 값 (레지스터)

; if 체인 (이 글, case 값이 듬성듬성일 때)
cmp     eax, 10        ; case 하나마다 cmp+je 반복
je      .L_case10
cmp     eax, 200
je      .L_case200
cmp     eax, 5000
je      .L_case5000
jmp     .L_default      ; 목적지가 고정된 레이블
```
가장 확실한 구분법은 **`jmp`의 목적지가 상수 레이블인가, 계산된 레지스터인가**이다. 점프 테이블은 `jmp rax`처럼 런타임에 계산된 주소로 뛰지만, if 체인으로 컴파일된 switch는 case 개수만큼의 `cmp eax, N` + `je .L_caseN`이 반복되고, 마지막에 `jmp .L_default`(상수 레이블)로 끝난다. **case 개수만큼 비교 연산이 선형으로 반복된다는 것**이 이 패턴의 시간 복잡도 특징이다(case가 많아지면 최악의 경우 case 개수만큼 비교가 필요).

### if-elseif-else(REV-1055)와 구분이 안 되는 이유
```c
// switch로 작성
switch (code) {
    case 10: return 1;
    case 200: return 2;
    case 5000: return 3;
    default: return 0;
}

// if-elseif로 작성해도 동일한 조건이면
if (code == 10) return 1;
else if (code == 200) return 2;
else if (code == 5000) return 3;
else return 0;
```
두 소스는 **완전히 동일한 어셈블리**로 컴파일된다. `switch`의 `case`가 정수 상수와의 동등 비교(`==`)로만 이루어져 있고 case 값이 흩어져 있다면, 컴파일러는 `if-elseif`와 구분할 이유가 전혀 없다. 따라서 이 모양의 코드를 봤을 때 "원본이 switch문이었다"고 확정할 수 없고, "여러 개의 정수 값과 동등 비교하는 조건 체인"이라고만 서술하는 것이 정확하다.

### 디컴파일러가 복원한 pseudocode
```c
int classify(int code)
{
  if (code == 10) {
    return 1;
  }
  else if (code == 200) {
    return 2;
  }
  else if (code == 5000) {
    return 3;
  }
  else {
    return 0;
  }
}
```
IDA/Ghidra는 이 패턴을 점프 테이블로 인식하지 못하고(테이블 자체가 없으므로 당연하다) 순수한 `if-else if` 체인으로 복원한다. 원본이 `switch`였더라도 디컴파일러 pseudocode에는 `switch` 키워드가 전혀 등장하지 않을 수 있다는 점이 이 패턴의 중요한 특징이다.

## 화면/코드에서 보이는 징후
- `cmp reg, 상수` + `je 레이블`이 케이스 개수만큼 연속으로 반복된다.
- 각 `cmp`의 상수 값 간격이 일정하지 않고 크게 떨어져 있다(10, 200, 5000처럼).
- 점프 테이블에서 보이는 `lea`(테이블 주소 계산), `movsxd`(오프셋 읽기), 계산된 `jmp reg`가 전혀 없다.
- 마지막 비교가 실패하면 `jmp .L_default`(고정 레이블)로 간다.

## 가장 먼저 할 것
`cmp`+`je` 반복 패턴을 보면 먼저 각 `cmp`의 상수 값을 순서대로 적어본다. 값들이 촘촘하면(REV-1056) 컴파일러 버전/최적화 수준에 따라 점프 테이블이 될 수도 있었는데 왜 안 됐는지 의심해보고, 값이 듬성듬성이면 이 패턴이 정상이라고 판단한다.

## 단계별 절차
1. 연속된 `cmp`+`je` 쌍을 모두 찾아 상수 값과 목적지 레이블을 나열한다.
2. 모든 비교가 실패했을 때 가는 마지막 `jmp` 목적지를 default 블록으로 확정한다.
3. 각 `.L_caseN` 블록의 코드를 확인하고, 끝에 공통 `.L_end`로 가는 `jmp`가 있는지 확인한다.
4. 상수 값들의 간격을 보고 "point 테이블을 안 쓴 이유(sparse)"를 리포트에 짧게 남긴다 — case 값과 코드 동작을 이해하는 데는 굳이 switch인지 if-elseif인지 구분할 필요가 없다는 점도 함께 기록한다.

## 명령어/단축키
```
(gdb) disas classify
(gdb) break *0x<addr_first_cmp>
(gdb) print $eax     ; code 값 확인
```
IDA: F5로 디컴파일했을 때 `switch` 키워드가 안 보이고 `if-else if`로만 나오면 이 패턴임을 바로 알 수 있다. Ghidra: Decompile 창에서도 동일하게 확인.

## 출력 해석
- `cmp`+`je`의 개수가 곧 case 개수(default 제외)와 같다. 개수를 세면 원본 switch의 case 수를 정확히 알 수 있다.
- 상수 값이 매직 넘버(에러 코드, 프로토콜 opcode 등)일 가능성이 높은 값(0x1000 이상, 특정 패턴)이라면 이 값들을 별도로 목록화해두면 이후 문자열/설정 파일과 대조할 때 유용하다.

## 흔한 실수
- 점프 테이블이 안 보인다고 "이 함수엔 switch가 없다"고 단정하는 것 — case 값 분포에 따라 얼마든지 if 체인으로 컴파일될 수 있다.
- case 값들이 몇 개는 촘촘하고 몇 개는 멀리 떨어진 "혼합형"인 경우, 컴파일러가 촘촘한 구간만 점프 테이블로 만들고 나머지는 `cmp`+`je`로 연결하는 혼합 코드를 생성할 수 있다는 걸 놓치는 것 — 이때는 코드 중간에 점프 테이블 조회 블록과 개별 `cmp`+`je` 블록이 섞여서 나타난다.
- `cmp`+`je` 개수가 많아지면(수십 개 이상) 컴파일러가 이진 탐색(binary search) 형태의 `cmp`+`jg`/`jl` 트리로 바꿀 수 있다는 점을 놓치는 것 — 이 경우 비교가 항상 순서대로 나열되지 않고 값 크기 순으로 절반씩 좁혀가는 트리 구조가 된다.
- default 블록으로 가는 마지막 `jmp`가 없고 그냥 다음 코드로 흘러가는(fall-through) 경우를 못 보고 default가 없다고 오판하는 것.

## 막혔을 때 다음 체크
- case 값이 촘촘해서 점프 테이블로 컴파일된 경우와의 차이를 다시 확인하려면 → REV-1056(switch-case가 점프 테이블로 컴파일되는 패턴).
- if-elseif-else 체인 자체의 기본 구조가 헷갈리면 → REV-1055(if-elseif-else 체인이 어셈블리에서 보이는 패턴).
- `cmp`/`je`의 정확한 동작이 헷갈리면 → REV-0060(CMP: 값을 바꾸지 않는 SUB 비교), REV-0067(JE와 JZ: ZF가 1일 때 분기).

## 미니 예제
HTTP 상태 코드처럼 값 간격이 넓은 case가 있는 실전 예시도 같은 패턴을 보인다.
```c
const char* status_text(int code) {
    switch (code) {
        case 200: return "OK";
        case 404: return "Not Found";
        case 500: return "Server Error";
        default:  return "Unknown";
    }
}
```
```asm
status_text:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-4], edi
    mov     eax, [rbp-4]
    cmp     eax, 200
    je      .L_200
    cmp     eax, 404
    je      .L_404
    cmp     eax, 500
    je      .L_500
    jmp     .L_default
.L_200:
    lea     rax, [rip+.LC_ok]
    jmp     .L_end
.L_404:
    lea     rax, [rip+.LC_notfound]
    jmp     .L_end
.L_500:
    lea     rax, [rip+.LC_servererr]
    jmp     .L_end
.L_default:
    lea     rax, [rip+.LC_unknown]
.L_end:
    leave
    ret
```
200, 404, 500이라는 값 간격이 커서 점프 테이블을 만들면 수백~수천 개의 빈 테이블 원소가 필요하므로, 컴파일러는 당연히 `cmp`+`je` 체인을 택한다.

## 관련 글
- REV-1056 — switch-case가 점프 테이블로 컴파일되는 패턴
- REV-1055 — if-elseif-else 체인이 어셈블리에서 보이는 패턴
- REV-0441 — Switch문 점프 테이블(Jump Table) 완전 분석
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0067 — JE와 JZ: ZF가 1일 때 분기

## 출처/검증
- case 값 분포에 따른 점프 테이블/이진 탐색/순차 비교 전략 선택은 GCC/Clang(LLVM) 공식 최적화 문서 및 실제 x86-64 컴파일 출력에서 반복 확인되는 동작이다.
- switch가 sparse case일 때 if-elseif와 동일한 어셈블리로 컴파일되는 현상은 -O0 실제 출력 비교로 확인된다 (2026-09-10 검증).
