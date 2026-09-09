---
id: REV-1055
title: "if-elseif-else 체인이 어셈블리에서 보이는 패턴"
slug: "rev-1055-if-elseif-else-chain-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["else if 체인 어셈블리", "if elseif else assembly pattern", "다중 조건 분기"]
aliases: ["else if 어셈블리에서 어떻게 보임", "else if 체인 디스어셈블", "다단계 조건문 패턴"]
symptom_keywords: ["else if가 여러 개인데 어셈블리에서 어떻게 구분해야 할지 모르겠음", "cmp가 여러 번 연속으로 나오는 이유를 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`if-elseif-else` 체인은 각 조건이 거짓일 때 **다음 조건 검사로 그냥 흘러가고(fall-through)**, 참일 때만 자기 블록을 실행한 뒤 **전체 체인 끝의 공통 합류 지점으로 점프**하는 "연쇄적인 cmp들"로 컴파일되며, 이는 REV-1054의 단일 if-else 하나가 여러 번 이어붙은 모양과 구분된다.

## 언제 검색해야 하나
- `cmp`와 조건부 분기가 두 번, 세 번 연속으로 나오는데 각 분기의 목적지가 서로 다른 코드 블록일 때, 이게 독립된 if문 여러 개인지 하나의 else-if 체인인지 궁금할 때
- 등급 매기기(grade), 범위 분류처럼 조건이 여러 단계로 이어지는 함수를 분석할 때
- 조건부 분기 실패(fall-through) 시 다음 `cmp`로 바로 이어지는 패턴을 보고 이게 왜 REV-1054의 if-else와 다른지 궁금할 때

## 핵심 개념

### 원본 C 코드
```c
int grade(int score) {
    if (score >= 90) {
        return 4;
    } else if (score >= 80) {
        return 3;
    } else if (score >= 70) {
        return 2;
    } else {
        return 1;
    }
}
```

### -O0 x86-64 어셈블리
```asm
grade:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-4], edi     ; score
    cmp     dword [rbp-4], 89
    jg      .L_ge90            ; score > 89 (즉 >= 90)이면 첫 분기
    cmp     dword [rbp-4], 79
    jg      .L_ge80            ; 여기까지 흘러왔다는 건 score < 90, 이제 >= 80 검사
    cmp     dword [rbp-4], 69
    jg      .L_ge70            ; 여기까지 흘러왔다는 건 score < 80, 이제 >= 70 검사
    mov     eax, 1              ; else: score < 70
    jmp     .L_end
.L_ge70:
    mov     eax, 2
    jmp     .L_end
.L_ge80:
    mov     eax, 3
    jmp     .L_end
.L_ge90:
    mov     eax, 4
.L_end:
    leave
    ret
```

### 줄 단위 대응 및 if-else와의 차이
- `cmp [rbp-4], 89` / `jg .L_ge90` — `score >= 90`이 `score > 89`(정수라서 등가)로 바뀌어 표현됐고, 참이면 최종 블록으로 바로 뛴다.
- **조건이 거짓일 때 다음 `cmp`로 그냥 흘러간다(fall-through)** — 이게 else-if 체인의 핵심 특징이다. REV-1054의 단일 if-else는 조건이 거짓이면 `.L_else` 레이블로 **점프**했지만, 여기서는 다음 조건 검사가 **바로 다음 줄에 이어져 있어서 점프조차 필요 없다**. 즉 첫 번째 `cmp`가 실패하면 자동으로 두 번째 `cmp`가 실행되는 구조다.
- 각 조건이 참일 때만 그 결과를 설정하고 `.L_end`로 점프해서 나머지 조건 검사들을 모두 건너뛴다.
- 조건 블록들의 코드 배치 순서가 소스 순서와 다르게 재배열될 수 있다(위 예시에서 `.L_ge70`, `.L_ge80`, `.L_ge90` 블록의 물리적 순서가 조건 검사 순서와 다르게 배치된 것에 주의) — 컴파일러가 각 케이스 코드를 편한 순서로 배치하기 때문이며, 논리적 순서는 여전히 조건 검사 순서(`cmp` 등장 순서)로 읽어야 한다.

### 독립된 if문 여러 개와의 구분
만약 소스가 `else if`가 아니라 독립된 `if` 세 개였다면:
```c
if (score >= 90) return 4;
if (score >= 80) return 3;
if (score >= 70) return 2;
return 1;
```
이 경우도 각 `if`에 else가 없으므로 `return`이 곧바로 함수를 빠져나가는 형태라 어셈블리 모양이 이 글의 else-if 체인과 **거의 동일하게** 나올 수 있다(각 조건이 참이면 그 자리에서 값 설정 후 종료, 거짓이면 다음 조건으로 흘러감). 이 둘을 어셈블리만으로 완벽히 구분하기는 어렵고, "조건들이 상호 배타적으로 설계되어 순차적으로 좁혀진다"는 동작 관점으로 이해하면 리포트 작성에는 충분하다.

### 디컴파일러가 복원한 pseudocode
```c
int grade(int score)
{
  if (score > 89) {
    return 4;
  }
  else if (score > 79) {
    return 3;
  }
  else if (score > 69) {
    return 2;
  }
  else {
    return 1;
  }
}
```
IDA/Ghidra는 연쇄된 fall-through `cmp` 구조를 정확히 `else if` 체인으로 잘 복원해준다. 다만 조건의 경계값이 `>= 90`에서 `> 89`로 바뀌어 보이는 것처럼, 정수 비교는 항상 등가인 여러 형태 중 컴파일러/디컴파일러가 고른 하나로 표시되므로 원본 소스의 정확한 연산자(`>=`인지 `>`인지)는 숫자를 보고 역산해야 할 때가 있다.

## 화면/코드에서 보이는 징후
- `cmp` + 조건부 분기가 연속으로 여러 번 나오고, 각 조건부 분기가 실패(fall-through)하면 바로 다음 `cmp`로 이어진다(중간에 다른 `jmp`가 없다).
- 각 조건이 참일 때 도달하는 블록들이 모두 같은 합류 지점(`.L_end`)으로 `jmp`한다.
- 조건 블록들의 물리적 배치 순서가 조건 검사 순서와 다를 수 있다(레이블 이름과 등장 순서를 같이 봐야 함).

## 가장 먼저 할 것
연속된 `cmp`들의 개수를 세어 몇 단계의 else-if인지 파악한다. 각 `cmp`의 조건부 분기가 실패했을 때 바로 다음 `cmp`로 흘러가는지(체인) 아니면 별도 else 블록으로 점프하는지(REV-1054의 단순 if-else가 중첩된 것) 구분한다.

## 단계별 절차
1. 첫 `cmp`와 그 조건부 분기의 목적지를 확인한다.
2. 조건부 분기가 실패했을 때 다음 명령이 또 다른 `cmp`인지 확인한다 — 맞으면 else-if 체인이 계속된다는 뜻이다.
3. 모든 `cmp`를 순서대로 나열해서 각 단계의 조건과 경계값을 정리한다.
4. 각 조건이 참일 때 점프하는 목적지 블록의 코드를 읽고, 그 블록 끝이 공통 `.L_end`로 가는지 확인해 체인의 전체 범위를 확정한다.

## 명령어/단축키
```
(gdb) disas grade
(gdb) break *0x<addr_of_first_cmp>
(gdb) print/d $edi     # score 인자 값 확인
```
IDA: 그래프 뷰에서 각 조건 블록이 세로로 길게 이어진 "체인" 모양을 눈으로 바로 확인할 수 있다. Ghidra: Decompile 창에서 `else if`로 이미 정리된 형태를 우선 참고하고, 필요하면 Listing에서 실제 `cmp` 순서를 원문 검증한다.

## 출력 해석
- 조건 경계값들이 등장 순서대로 90, 80, 70처럼 내려가면 "높은 조건부터 검사하는" 일반적인 등급 매기기 패턴이다. 순서가 뒤섞여 있다면 조건들이 상호 배타적이지 않을 수 있으니 로직을 더 신중히 재확인해야 한다.
- 각 조건 블록이 단순 `mov eax, N`(상수 반환)뿐이라면 최적화 시 전체가 조건부 이동이나 룩업 테이블로 바뀔 여지가 있다는 뜻이다.

## 흔한 실수
- 여러 개의 `cmp`를 보고 무조건 else-if 체인이라고 단정하는 것 — 독립된 if문 여러 개(위의 "독립된 if문" 절 참고)도 비슷하게 보일 수 있으므로 각 블록이 정말 상호 배타적인지 확인해야 한다.
- 조건 블록의 물리적 배치 순서를 논리적 조건 검사 순서로 착각하는 것 — 컴파일러가 재배치할 수 있으므로 반드시 `cmp`가 등장하는 순서(코드가 실제로 실행되는 순서)를 따라가야 한다.
- 경계값 표현(`> 89`가 `>= 90`과 같다는 것)을 놓치고 오프바이원(off-by-one) 오류로 조건을 잘못 해석하는 것.
- 조건이 3개 이상으로 많아지면 `-O2`에서 이지선다형 이진 탐색(binary search) 구조로 재작성되거나, 조건들이 특정 패턴(연속된 정수 등)일 경우 switch-case의 점프 테이블(REV-1056)과 유사한 형태로 바뀔 수 있다는 점을 놓치는 것.

## 막혔을 때 다음 체크
- 조건이 두 개뿐인 단순 형태가 궁금하면 → REV-1054(if-else가 어셈블리에서 보이는 패턴).
- 조건이 정수 값 하나와의 동등 비교(`==`)로만 이루어진 경우가 궁금하면 → REV-1056(switch-case가 점프 테이블로 컴파일되는 패턴), REV-1057(switch-case가 if 체인으로 컴파일되는 패턴).
- `cmp`/조건부 분기 명령어 자체의 세부 동작이 헷갈리면 → REV-0060(CMP), REV-0069(JG JGE JL JLE: Signed 비교 분기).

## 미니 예제
문자 하나를 보고 종류를 분류하는 함수도 같은 체인 구조를 따른다.
```c
int classify_char(char c) {
    if (c == ' ') {
        return 0;
    } else if (c >= '0' && c <= '9') {
        return 1;
    } else if (c >= 'a' && c <= 'z') {
        return 2;
    } else {
        return 3;
    }
}
```
```asm
classify_char:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     [rbp-4], dil     ; c
    cmp     byte [rbp-4], 0x20
    jne     .L_check_digit
    mov     eax, 0
    jmp     .L_end
.L_check_digit:
    cmp     byte [rbp-4], 0x30
    jl      .L_check_lower
    cmp     byte [rbp-4], 0x39
    jg      .L_check_lower
    mov     eax, 1
    jmp     .L_end
.L_check_lower:
    cmp     byte [rbp-4], 0x61
    jl      .L_else
    cmp     byte [rbp-4], 0x7a
    jg      .L_else
    mov     eax, 2
    jmp     .L_end
.L_else:
    mov     eax, 3
.L_end:
    leave
    ret
```
`&&`로 묶인 범위 조건(`c >= '0' && c <= '9'`)이 `cmp`+`jl`과 `cmp`+`jg` 두 개로 나뉘어 순차적으로 검사되는 것이 눈에 띈다. `&&`의 단축 평가가 어셈블리에서 어떻게 보이는지는 REV-1074에서 더 자세히 다룬다.

## 관련 글
- REV-1054 — if-else가 어셈블리에서 보이는 패턴
- REV-1056 — switch-case가 점프 테이블로 컴파일되는 패턴
- REV-1057 — switch-case가 if 체인으로 컴파일되는 패턴(sparse case)
- REV-1074 — && / || 단축 평가가 어셈블리에서 보이는 패턴
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0069 — JG JGE JL JLE: Signed 비교 분기

## 출처/검증
- else-if 체인이 fall-through 방식의 연쇄 `cmp`로 컴파일되고 각 참 분기가 공통 종료 지점으로 합류하는 패턴은 x86-64 gcc/clang `-O0` 실제 출력에서 반복 확인된다.
- 정수 경계 비교의 등가 변환(`>= 90`과 `> 89`)은 정수 비교의 일반적 산술 성질에 근거한다 (2026-09-10 검증).
