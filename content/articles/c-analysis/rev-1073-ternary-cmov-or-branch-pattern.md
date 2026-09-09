---
id: REV-1073
title: "삼항 연산자(?:)가 CMOV 또는 분기로 컴파일되는 패턴"
slug: "rev-1073-ternary-cmov-or-branch-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["삼항 연산자 어셈블리", "ternary operator assembly", "cmovg cmovle 패턴", "조건부 이동 명령어"]
aliases: ["? : 어셈블리에서 어떻게 보임", "cmov가 왜 나오는지", "삼항연산자 디스어셈블"]
symptom_keywords: ["짧은 if인데 분기 없이 cmov만 있음", "jmp 없는 조건문을 만났음", "cmovle cmovg가 뭔지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`a > b ? a : b` 같은 삼항 연산자는 최적화 없이(`-O0`) 컴파일하면 `cmp`+조건 분기(`jle` 등)+`jmp`로 이루어진 짧은 if-else와 똑같이 나오지만, 최적화를 켜면(`-O1` 이상) 분기 자체를 없애고 `cmovle`/`cmovg` 같은 조건부 이동(conditional move) 명령 하나로 압축되는 경우가 많다.

## 언제 검색해야 하나
- 디스어셈블 코드에 `cmp` 다음 바로 `cmovg`, `cmovle`, `cmove`, `cmovne` 같은 낯선 명령이 나와서 이게 조건문인지 확신이 안 갈 때
- 소스에 `if`가 있는데 컴파일된 코드에는 분기(`jXX`)가 하나도 안 보이고 대신 조건부 이동만 있을 때
- pseudocode(IDA/Ghidra)가 `x = cond ? a : b;` 형태로 예쁘게 복원되어 있어서 원래 삼항 연산자였는지 if-else였는지 소스와 대조하고 싶을 때
- `-O0`로 빌드된 바이너리인데 짧은 조건 대입이 분기+jmp 두 갈래로 퍼져 있어서 왜 이렇게 코드가 늘어졌는지 이해하고 싶을 때

## 핵심 개념
삼항 연산자는 값이 필요한 표현식이므로 컴파일러는 두 가지 방식 중 하나로 구현한다. `-O0`에서는 사람이 손으로 쓴 if-else와 동일하게 "조건에 따라 다른 곳으로 점프해서 다른 값을 대입"하는 분기 방식을 쓴다. 반면 최적화가 켜지면, 두 값을 계산하는 비용이 분기 예측 실패 비용보다 싸다고 판단될 경우 분기를 완전히 제거하고 `cmovcc`(조건부 이동) 한 줄로 대체한다.

```c
int max_val(int a, int b) {
    return a > b ? a : b;
}
```

x86-64 SysV, `-O0`(분기 방식), Intel 문법:

```asm
max_val:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-4], edi     ; a 저장
    mov     [rbp-8], esi     ; b 저장
    mov     eax, [rbp-4]     ; eax = a
    cmp     eax, [rbp-8]     ; a와 b 비교
    jle     .L_else          ; a <= b 이면(즉 a > b가 거짓) else 쪽으로 분기
    mov     eax, [rbp-4]     ; a > b 이므로 결과 = a
    jmp     .L_end
.L_else:
    mov     eax, [rbp-8]     ; a <= b 이므로 결과 = b
.L_end:
    pop     rbp
    ret
```

같은 함수를 `-O1` 이상(CMOV 방식)으로 컴파일하면:

```asm
max_val:
    mov     eax, edi         ; eax = a (기본값으로 a를 미리 넣어둠)
    cmp     edi, esi         ; a와 b 비교
    cmovle  eax, esi         ; a <= b 이면 eax를 b로 덮어씀 (분기 없이 조건부로 대체)
    ret
```

두 버전 모두 논리는 완전히 동일하다. `-O0` 버전은 "분기해서 서로 다른 코드 경로로 가서 각자 값을 넣는다"는 방식이고, `-O1` 버전은 "일단 한쪽 값을 넣어두고, 조건이 맞으면 다른 값으로 조건부로 덮어쓴다"는 방식이다. `cmovle`는 "이전 `cmp`가 세팅한 플래그를 보고 `<=` 조건이 참이면 이동을 수행하라"는 뜻이며, 분기가 없으므로 분기 예측(branch prediction) 실패로 인한 파이프라인 손실이 없다.

## 화면/코드에서 보이는 징후
- `cmp` 바로 다음 줄에 `jXX`가 아니라 `cmovXX`(예: `cmove`, `cmovne`, `cmovg`, `cmovle`, `cmova`, `cmovb`)가 나옴
- 조건에 상관없이 실행되는 명령어 수가 짧고, 분기/레이블(`.L_else`, `.L_end` 같은)이 전혀 없음
- IDA/Ghidra pseudocode에서 짧은 `x = cond ? y : z;` 형태로 아주 깔끔하게 한 줄로 복원됨

## 가장 먼저 할 것
`cmovXX` 명령을 만나면 우선 그 직전의 `cmp`(또는 `test`)가 어떤 두 값을 비교하는지 확인하고, `cmovXX`의 조건 코드(`g`, `le`, `e`, `ne` 등)를 REV-0075(CMOVcc 사전)에서 찾아 "그 조건이 참일 때 이동이 일어난다"는 사실만 확정하면 된다. 분기가 없다고 조건문이 없다고 착각하지 않는 것이 핵심이다.

## 단계별 절차
1. `cmovXX` 명령을 발견하면 그 직전 `cmp`/`test` 피연산자 두 개를 기록한다.
2. 조건 코드 접미사(`g`, `ge`, `l`, `le`, `e`, `ne`, `a`, `b` 등)를 REV-0075/REV-0069/REV-0070에서 확인해 "어떤 비교 결과일 때 이동하는지"를 해석한다.
3. `cmovXX eax, esi` 라면 "조건이 참이면 `eax`를 `esi`값으로 바꾼다"는 뜻이므로, 조건이 거짓이면 `eax`에 원래 있던 값(직전에 세팅된 기본값)이 그대로 결과가 된다.
4. 이렇게 얻은 "조건 → 대입" 관계를 `cond ? a : b` 형태로 재구성해 소스 삼항 연산자와 대응시킨다.

## 명령어/단축키
- IDA: pseudocode 뷰(F5)에서 `?:` 형태로 이미 복원되어 있는지 우선 확인
- Ghidra: Decompile 창에서 동일하게 삼항식 복원 여부 확인
- GDB: `disassemble` 후 `cmovXX` 직전 `cmp`의 두 오퍼랜드를 `p`로 직접 찍어보며 조건 판단
- x64dbg: `cmovXX` 명령 위에서 F7(step into)로 실행 전/후 레지스터 값 변화를 직접 비교

## 출력 해석
`cmovle eax, esi`가 실행되었는데 실행 후 `eax`가 바뀌지 않았다면, 그 시점의 플래그가 `<=` 조건을 만족하지 않았다는 뜻이다(즉 원래 `a > b`가 참이어서 `a` 값을 그대로 유지). 반대로 `eax`가 `esi` 값으로 바뀌었다면 `a <= b`였다는 뜻이다. `cmov`는 항상 명령어 자체는 실행되지만 "이동을 실제로 수행하느냐"만 조건에 따라 달라진다는 점을 기억하면 헷갈리지 않는다.

## 흔한 실수
- `jXX`가 없다고 "이 함수엔 조건문이 없다"고 결론짓는 것 — `cmovXX`도 조건부 실행이다.
- `cmovle`를 `jle`처럼 "조건이 참이면 그 다음 줄로 건너뛴다"는 식으로 잘못 해석하는 것. `cmov`는 분기가 아니라 그 자리에서 즉시 조건부 대입을 수행한다.
- 최적화 레벨에 따라 같은 소스가 분기(`-O0`)로도, `cmov`(`-O1`+)로도 나올 수 있다는 걸 모르고 "이 패턴이 항상 이렇게 나온다"고 단정하는 것.
- 삼항 연산자와 짧은 if문(REV-0453, SETcc 패턴)을 혼동하는 것 — `SETcc`는 결과를 0/1로 만들 때, `CMOVcc`는 두 값 중 하나를 고를 때 주로 쓰인다.

## 막혔을 때 다음 체크
- `cmov`가 아니라 `sete`/`setne` 같은 0/1 결과 생성 명령을 만났다면 → REV-0453 짧은 if문이 SETcc로 컴파일되는 패턴
- 여러 조건이 `&&`/`||`로 묶여 있고 그 결과로 삼항 연산자가 실행되는 형태라면 → REV-1074 && / || 단축 평가가 어셈블리에서 보이는 패턴
- 삼항 연산자 결과를 다시 변수에 복합 대입하는 형태(`x += cond ? a : b;`)라면 → REV-1080 복합 대입 연산자(+=, -=, *= 등)가 어셈블리에서 보이는 패턴

## 미니 예제
절댓값을 구하는 흔한 삼항 연산자 패턴이다.

```c
int abs_val(int x) {
    return x < 0 ? -x : x;
}
```

`-O1` 기준 CMOV 버전:

```asm
abs_val:
    mov     eax, edi        ; eax = x (기본값: x가 0 이상이라 가정)
    neg     eax             ; eax = -x (조건이 참일 때 쓸 후보값을 미리 계산)
    cmovns  eax, edi        ; x >= 0(부호 플래그가 아님, Not Sign)이면 eax를 원래 x로 되돌림
    ret
```

여기서는 순서가 반대다 — 먼저 "음수라고 가정한 결과(`-x`)"를 만들어 놓고, 실제로는 `x >= 0`일 때만 원래 값으로 덮어쓴다. `cmovns`(Not Sign, 즉 결과가 음수가 아닐 때 이동)처럼 조건이 반대로 걸릴 수도 있으므로, 항상 "이동이 일어나는 조건"과 "이동이 일어나지 않아 유지되는 조건"을 둘 다 짝지어 확인해야 한다.

## 관련 글
- REV-0452 — 삼항 연산자(?:)가 CMOVcc로 컴파일되는 패턴
- REV-0453 — 짧은 if문이 SETcc로 컴파일되는 패턴
- REV-1074 — && / || 단축 평가가 어셈블리에서 보이는 패턴
- REV-1080 — 복합 대입 연산자(+=, -=, *= 등)가 어셈블리에서 보이는 패턴

## 출처/검증
- `CMOVcc` 명령의 조건부 이동 동작과 플래그 해석: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2 (CMOVcc 명령 설명) 기준.
- `-O0`는 분기, `-O1` 이상에서 조건부 이동으로 대체되는 경향: gcc/clang 실제 출력 비교로 반복 확인되는 컴파일러 최적화 패턴 (2026-09-10 검증).
