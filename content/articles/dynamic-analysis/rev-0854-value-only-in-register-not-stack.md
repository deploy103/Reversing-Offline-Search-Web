---
id: REV-0854
title: "스택에서 원하는 값이 안 보일 때(레지스터에만 있을 때)"
slug: "rev-0854-value-only-in-register-not-stack"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg]
keywords: ["optimized out", "레지스터 할당 변수", "스택에 없는 변수", "컴파일러 최적화 변수 위치"]
aliases: ["스택 덤프에 값이 없음", "변수가 스택에 안 실림", "optimized out 문제"]
symptom_keywords: ["스택을 덤프했는데 값이 안 보인다", "info locals가 optimized out을 뜻한다", "변수가 메모리에 없는것 같다", "레지스터에만 값이 있고 스택엔 없다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
컴파일러 최적화(`-O1` 이상, Release 빌드)는 자주 쓰이는 지역 변수를 스택에 아예 쓰지 않고 레지스터 안에서만 계속 굴리는 경우가 많다 — 이럴 땐 스택 덤프를 아무리 뒤져도 그 값이 안 보이는 게 정상이며, 레지스터 창/`info registers`를 직접 봐야 한다.

## 언제 검색해야 하나
- 디스어셈블리나 소스에서 분명히 존재하는 변수인데, 스택 덤프(Hex 뷰/`x` 명령)를 아무리 찾아도 그 값이 안 보일 때
- GDB `info locals`나 `print 변수명`이 `<optimized out>`이라고 답할 때
- Release/최적화 빌드 바이너리를 분석 중인데 Debug 빌드에서 봤던 스택 레이아웃과 완전히 다르게 보일 때
- 루프 카운터나 임시 계산 결과가 스택 어디에도 안 쓰이고 사라진 것처럼 보일 때

## 핵심 개념

### 왜 변수가 스택에 없을 수 있는가
스택에 값을 쓰고 읽는 것(`mov [rbp-0x8], eax` 등)은 메모리 접근이라 레지스터 접근보다 느리다. 컴파일러는 최적화 시 레지스터가 남는 한 자주 쓰는 지역 변수를 계속 레지스터에만 두고(레지스터 할당, register allocation), 그 함수가 끝나거나 그 레지스터가 다른 용도로 필요해질 때만 스택에 "흘려보낸다"(spill). 흘려보낼 필요가 아예 없다면(변수가 함수 안에서만 쓰이고 주소를 아무도 안 가져간다면) 스택에는 끝까지 안 나타날 수 있다.

### `&변수`(주소를 취하는 코드)가 있으면 스택에 강제로 실린다
`scanf("%d", &x)`처럼 변수의 주소를 다른 함수에 넘기는 코드가 있다면, 컴파일러는 그 변수가 반드시 메모리 주소를 가져야 하므로 레지스터에만 둘 수 없다. 이런 변수는 최적화가 걸려도 스택에 나타난다. 반대로 사칙연산 중간 결과나 반복문 카운터처럼 주소를 아무도 안 가져가는 값은 레지스터에만 머물기 쉽다.

### GDB의 `<optimized out>`은 "값이 사라졌다"가 아니라 "디버그 정보가 위치를 추적 못 한다"는 뜻
`<optimized out>`이 뜬다고 그 값이 실제로 없는 것은 아니다. 대부분 그 순간 어떤 레지스터에는 반드시 존재한다. 다만 디버그 정보(DWARF)가 "이 시점에 이 변수는 이 레지스터에 있다"는 정보를 제공하지 않거나, GDB가 그 정보를 표시 못 하는 경우 `<optimized out>`으로 뭉뚱그려 표시한다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) info locals
result = <optimized out>
i = <optimized out>
```
```gdb
(gdb) x/4xw $rsp
0x7fffffffe410: 0x00000000 0x00401520 0x00000001 0x7fffe4a0
```
스택 어디에도 예상한 값이 안 보이는데, 정작 그 값은 어셈블리 상 `eax`/`ebx` 같은 레지스터에서 계속 쓰이고 있는 것이 디스어셈블리로는 확인됨.

## 가장 먼저 할 것
`info locals`가 `<optimized out>`을 내놓으면 스택 대신 바로 `info registers`(GDB) 또는 레지스터 창(x64dbg)을 확인한다. 그 값을 만들어내는 직전 명령어(디스어셈블리)를 보고 어떤 레지스터로 결과가 들어가는지부터 확인하는 것이 더 빠르다.

## 단계별 절차

**1) 디스어셈블리로 값이 어느 레지스터에 있는지 먼저 확인**
```gdb
(gdb) disassemble
=> 0x0000000000401203 <+10>:  mov    eax, DWORD PTR [rbp-0x4]
   0x0000000000401206 <+13>:  add    eax, 0x1
   0x0000000000401209 <+16>:  mov    DWORD PTR [rbp-0x4], eax
```
이런 경우는 스택에도 쓰이므로 문제가 안 된다. 반대로 아래처럼 스택 접근 없이 레지스터끼리만 연산하는 구간이라면:
```gdb
0x0000000000401230 <+40>:  add    ebx, eax
0x0000000000401232 <+42>:  cmp    ebx, 0x64
```
`ebx`가 스택에 한 번도 안 실린 채 계속 누적되고 있는 것이다. 이 값을 보려면 `info registers ebx` 또는 `print $ebx`를 써야 한다.

**2) 레지스터 직접 확인**
```gdb
(gdb) print $eax
(gdb) info registers eax ebx
```

**3) 값의 변화를 스택 대신 레지스터로 추적**
```gdb
(gdb) display $ebx
(gdb) stepi
```
`display`로 등록해두면 한 스텝씩 진행할 때마다 자동으로 그 레지스터 값을 출력해준다(REV-0172 참고).

**4) 스택에 강제로 실리게 하고 싶다면 디버그 빌드로 재현**
분석 대상 소스가 있다면 `-O0`(GCC/Clang) 또는 Debug 구성(MSVC)으로 다시 빌드해 비교해보면, 최적화가 어떤 변수를 레지스터에만 뒀는지 정확히 확인할 수 있다. 소스가 없다면 이 방법은 쓸 수 없고 레지스터 추적만으로 분석을 이어간다.

**5) x64dbg에서도 동일 — Registers 창 우선 확인**
CPU 창 오른쪽 Registers 패널에서 해당 레지스터 값을 직접 보고, 코드가 스택(`[rbp-X]`)을 안 건드리는 구간이면 Dump 창에서 찾을 이유가 없다는 것을 먼저 인지한다.

## 명령어/단축키
```gdb
(gdb) info locals
(gdb) info registers [REG]
(gdb) print $REG
(gdb) display $REG
(gdb) disassemble
(gdb) stepi / si
```
```
x64dbg: Registers 패널(우측 상단), Watch 창에 레지스터 추가, F7(Step Into)로 값 변화 관찰
```

## 출력 해석
- `info locals`의 `<optimized out>` → 스택이 아니라 레지스터에 있다는 신호. 절대 "값이 사라졌다"로 해석하지 말 것.
- 디스어셈블리에서 특정 레지스터가 여러 명령어에 걸쳐 스택 접근(`[rbp-...]`, `[rsp+...]`) 없이 계속 재사용되면, 그 값은 끝까지 레지스터에만 머무는 변수다.
- 함수 마지막 부분에서 갑자기 `mov [rbp-0x8], eax`처럼 스택에 쓰는 명령이 나타난다면, 그 지점에서만 잠깐 spill된 것 — 그 지점 이후에는 스택에서도 확인 가능해진다.

## 흔한 실수
- `info locals`가 `<optimized out>`이라고 나오면 "이 변수는 이제 못 본다"고 포기하는 것 — 대부분 레지스터에서 그대로 확인 가능하다.
- 최적화 빌드에서 Debug 빌드와 똑같은 스택 오프셋 레이아웃을 기대하는 것 — 최적화 여부에 따라 스택 프레임 자체가 완전히 달라진다.
- 레지스터 값을 한 번만 확인하고 스텝마다 다시 확인 안 해서, 그 값이 다른 함수 호출로 덮어써진 것을 놓치는 것 — 함수 호출(`call`)을 지나면 caller-saved 레지스터(RAX, RCX, RDX 등)는 값이 보존된다는 보장이 없다.
- `display`를 등록해놓고 레지스터 폭(32비트 `eax`/64비트 `rax`)을 헷갈려서 상위 비트 값을 놓치는 것.

## 막혔을 때 다음 체크
- 레지스터 값을 실행 중 추적하는 기본기가 필요하다면 → REV-0172 레지스터 값을 실행 중 추적하는 법.
- 스택 값 추적 기본기가 궁금하다면 → REV-0173 스택 값을 실행 중 추적하는 법.
- 전역/지역 변수가 메모리 어디에 위치하는지 개념 자체가 헷갈린다면 → REV-0353 전역 변수와 지역 변수를 메모리 위치로 구분하는 법.

## 미니 예제
```gdb
(gdb) break loop_check
(gdb) run
(gdb) info locals
count = <optimized out>
(gdb) disassemble
=> 0x0000000000401230 <+16>:  add    ebx, 0x1
   0x0000000000401233 <+19>:  cmp    ebx, 0x64
   0x0000000000401236 <+22>:  jne    0x401230
(gdb) print $ebx
$1 = 12
(gdb) display $ebx
(gdb) stepi
1: $ebx = 13
```
`info locals`는 `count`를 못 찾았지만, 디스어셈블리를 보니 `ebx`가 그 역할을 하고 있었고 `print $ebx`로 정상적으로 값을 확인할 수 있었다.

## 관련 글
- REV-0172 — 레지스터 값을 실행 중 추적하는 법
- REV-0173 — 스택 값을 실행 중 추적하는 법
- REV-0353 — 전역 변수와 지역 변수를 메모리 위치로 구분하는 법

## 출처/검증
- 컴파일러 최적화 시 레지스터 할당(register allocation)과 스택 spill 동작: GCC/LLVM 최적화 문서(레지스터 할당 일반 이론) 및 DWARF 디버깅 정보 표준의 위치 표현식(location expression) 개념 기준.
- GDB `<optimized out>`이 변수의 메모리/레지스터 위치를 디버그 정보로 추적할 수 없을 때 표시되는 동작: GDB 공식 매뉴얼 "Variables" 챕터 기준 (2026-09-09 검증).
