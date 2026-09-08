---
id: REV-0188
title: "GDB info registers와 flags 확인"
slug: "rev-0188-gdb-info-registers"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb info registers", "gdb 레지스터 확인", "eflags", "gdb flags", "print 레지스터", "gdb rax rdi rsi"]
aliases: ["gdb 레지스터 보는법", "gdb eflags 확인", "gdb 플래그 확인", "gdb i r", "gdb 레지스터 값 출력"]
symptom_keywords: ["gdb에서 rax 값이 뭔지 모름", "gdb 플래그가 어떻게 바뀌는지 모름", "zf sf cf 확인하는법", "gdb에서 특정 레지스터만 보고싶음", "cmp 이후 플래그 확인법"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`info registers`(줄여서 `i r`)는 현재 멈춰있는 시점의 CPU 레지스터 전체 값을 보여주는 GDB 명령으로, `info registers rax rdi rsi`처럼 특정 레지스터만 골라볼 수도 있고, `eflags`(플래그 레지스터)는 `ZF`, `SF`, `CF`, `OF` 같은 비트가 사람이 읽을 수 있는 이름으로 함께 표시되어 `cmp`, `test` 직후 분기 조건을 판단할 때 핵심적으로 쓰인다.

## 언제 검색해야 하나
- `cmp`나 `test` 명령어를 실행한 직후, 다음에 나올 `je`/`jne` 같은 조건 분기가 실제로 어느 쪽으로 갈지 미리 판단하고 싶을 때
- 지금 함수 인자로 뭐가 들어왔는지 SysV 호출 규약대로 `RDI`, `RSI`, `RDX` 값을 확인하고 싶을 때
- `RAX`에 함수 리턴값이 얼마나 들어있는지 확인하고 싶을 때
- `info registers`를 쳤는데 결과가 너무 많아서 원하는 값만 빠르게 찾고 싶을 때
- `eflags` 옆에 적힌 `[ ZF PF ]` 같은 표기가 무슨 뜻인지 모를 때

## 핵심 개념

### `info registers` — 범용 레지스터 전체 덤프
아무 인자 없이 `info registers`를 치면 x86-64 기준 `rax`부터 `r15`까지의 범용 레지스터, `rip`(현재 실행 중인 명령어 주소), `eflags`, 세그먼트 레지스터(`cs`, `ss`, `ds` 등)까지 한 번에 출력한다. 각 줄은 "레지스터 이름 / 16진수 값 / 부가 정보(가능하면 심볼이나 10진수)" 순서로 표시된다.

### 특정 레지스터만 골라보기
전체 목록이 너무 길다면 원하는 레지스터 이름을 인자로 준다.
```gdb
info registers rax rdi rsi
```
이렇게 하면 딱 세 개만 출력되어, SysV x64 호출 규약에서 함수의 1번째(`rdi`), 2번째(`rsi`) 인자와 리턴값(`rax`)만 빠르게 확인할 때 유용하다. `info registers rip`처럼 하나만 볼 수도 있다.

### `print`(p)로 개별 레지스터 값 다루기
레지스터는 `$` 접두사를 붙여 `print` 명령의 표현식 안에서도 그대로 쓸 수 있다.
```gdb
print $rax
print/x $rax     # 16진수로
print $rdi + 8
```
`info registers`는 "보여주기 전용"이지만 `print`는 산술 연산, 형 변환, 조건식 안에서까지 자유롭게 레지스터를 조합할 수 있어 더 유연하다. 32비트 하위 레지스터(`$eax`), 16비트(`$ax`), 8비트(`$al`)도 GDB가 자동으로 지원한다.

### `eflags`(플래그 레지스터) 읽는 법
`info registers eflags`(또는 `p/x $eflags`)를 치면 다음과 같은 형태로 나온다.
```
eflags         0x246               [ PF ZF IF ]
```
대괄호 안에 나열된 이름이 현재 **1로 세팅된 플래그**들이다. 리버싱에서 특히 자주 보는 플래그는 다음과 같다.
- `ZF`(Zero Flag): 연산 결과가 0일 때 1. `cmp a, b` 후 `ZF=1`이면 `a == b`.
- `SF`(Sign Flag): 연산 결과의 최상위 비트(부호 비트)가 1일 때 1. 결과가 음수(2의 보수 기준)라는 뜻.
- `CF`(Carry Flag): 부호 없는(unsigned) 연산에서 자리올림/빌림이 발생했을 때 1. 부호 없는 비교의 대소 판단에 쓰인다.
- `OF`(Overflow Flag): 부호 있는(signed) 연산에서 오버플로우가 발생했을 때 1.
- `PF`(Parity Flag): 결과의 하위 바이트에 1비트 개수가 짝수일 때 1(요즘 리버싱에서는 거의 안 씀).

`cmp a, b`는 내부적으로 `a - b`를 계산해서 결과는 버리고 플래그만 갱신한다. 그 뒤 나오는 `je`(ZF=1이면 점프), `jg`(부호 있는 비교로 a>b면 점프, 정확히는 `ZF=0 && SF=OF`), `ja`(부호 없는 비교로 a>b면 점프, 정확히는 `CF=0 && ZF=0`) 같은 조건 분기가 바로 이 플래그들을 읽어서 동작한다. 그래서 `cmp` 직후 `info registers eflags`로 플래그를 확인하면, 다음 조건 분기가 어느 쪽으로 갈지 코드를 더 실행하지 않고도 예측할 수 있다.

### `rip`은 "현재 실행 중인 명령어"의 주소다
`info registers rip`으로 보이는 값은 지금 CPU가 실행하려는 다음 명령어의 주소다. `x/i $rip`(REV-0189, REV-0190 참고)과 함께 쓰면 "지금 정확히 어느 줄에 있는지"를 명령어 텍스트로 바로 확인할 수 있다.

### 스택 관련 레지스터: `rsp`, `rbp`
`rsp`(stack pointer)는 현재 스택의 맨 위(가장 낮은 주소 방향)를 가리키고, `rbp`(base pointer, 프레임 포인터)는 관례적으로 현재 함수 스택 프레임의 기준점을 가리킨다(컴파일러 최적화나 `-fomit-frame-pointer`가 켜지면 `rbp`가 이 역할을 안 할 수도 있다). 함수 인자나 지역 변수 위치를 스택 오프셋으로 추적할 때 이 두 값이 기준이 된다.

### 부동소수점/SIMD 레지스터
`info registers`는 기본적으로 범용 레지스터만 보여준다. `xmm0` 같은 SSE 레지스터는 별도로 확인해야 한다.
```gdb
info registers xmm0
info all-registers   # 부동소수점, 세그먼트 등 전부
```

## 화면/코드에서 보이는 징후
- `info registers` 출력이 20줄 넘게 쭉 나와서 원하는 값 찾기 번거로움
- `cmp` 명령어 바로 다음 줄에서 `eflags`를 확인하려는 흐름
- IDA 디컴파일 코드의 `if (v1 == v2)`가 어셈블리에서 `cmp`+`je`/`jne` 쌍으로 나타나는 패턴과 맞춰보는 과정
- `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` 순서로 함수 인자를 확인하는 흐름(SysV x64 calling convention, REV-0106 참고)

## 가장 먼저 할 것
전체를 다 보고 싶다면 `info registers`, 특정 값만 빠르게 확인하고 싶다면 이름을 지정해서 `info registers rax rdi rsi`처럼 좁혀서 본다. 조건 분기를 예측하려면 `cmp`/`test` 바로 다음 줄에서 `info registers eflags`를 습관적으로 확인한다.

## 단계별 절차

**1) 전체 레지스터 한 번 확인**
```gdb
info registers
```

**2) 관심 있는 레지스터만 좁혀서 확인**
```gdb
info registers rax rdi rsi
```

**3) `cmp`/`test` 직후 플래그 확인**
```gdb
x/i $rip-5      # 방금 실행한 cmp 명령 확인(선택)
info registers eflags
```

**4) 다음 조건 분기 예측**
플래그 값을 보고 `je`/`jne`/`jg`/`ja` 등이 어느 쪽으로 튈지 판단한 뒤 `stepi`로 실제 결과와 비교해본다.

**5) 필요하면 `print`로 직접 계산**
```gdb
print $rax == $rbx
print/x $rdi
```

## 명령어/단축키
```gdb
info registers        # i r
info registers rax rdi rsi
info registers eflags
info registers rip
info all-registers
print $rax
print/x $rax
```

## 출력 해석
- `rax            0x1                 1`: 왼쪽은 16진수, 오른쪽은 10진수(가능하면). 포인터 값이면 오른쪽에 심볼 이름이 붙기도 한다.
- `rip            0x555555555199      0x555555555199 <main+16>`: `<main+16>`은 이 주소가 `main` 함수 시작으로부터 16바이트 뒤라는 뜻이다.
- `eflags         0x246               [ PF ZF IF ]`: 대괄호 안에 없는 플래그(예: `CF`, `SF`, `OF`)는 전부 0이라는 뜻이다. `IF`는 인터럽트 활성화 플래그로 일반적인 유저 모드 코드 분석에서는 크게 신경 쓸 필요가 없다.

## 흔한 실수
- `ZF=1`을 "참(true)"으로, `ZF=0`을 "거짓(false)"으로 직관적으로 착각하는 것 — 실제로는 명령어별로 의미가 다르다. `cmp a,b; je`는 `ZF=1`일 때 점프하지만, 이건 `a==b`일 때 점프한다는 뜻이지 "참이라서" 점프하는 게 아니다. 항상 어떤 명령어가 플래그를 세팅했는지 먼저 확인해야 한다.
- 부호 있는 비교(`jg`, `jl` 계열)와 부호 없는 비교(`ja`, `jb` 계열)에 관여하는 플래그가 다르다는 걸 모르고 아무 플래그나 보는 것 — `jg`/`jl`은 `SF`, `OF`, `ZF`를 조합해서 판단하고, `ja`/`jb`는 `CF`, `ZF`만 본다.
- `info registers`만 보고 부동소수점 비교(`ucomiss` 등)의 결과는 `eflags`가 아니라 별도의 플래그에 반영된다는 걸 놓치는 것(x87/SSE 비교는 다른 메커니즘을 쓴다).
- 32비트 레지스터(`eax`)에 값을 쓰면 상위 32비트(`rax`의 위쪽 절반)가 자동으로 0으로 클리어된다는 x86-64 특성을 모르고 `rax` 전체 값을 잘못 추측하는 것.

## 막혔을 때 다음 체크
- 지금 명령어가 정확히 뭔지 텍스트로 보고 싶다면 → REV-0190 GDB disassemble와 현재 RIP 주변 보기
- 메모리 안의 값(레지스터가 가리키는 곳)을 보고 싶다면 → REV-0189 GDB x 명령으로 메모리 보기
- 함수 인자 전달 규약 자체를 더 알고 싶다면 → REV-0106 SysV AMD64 Calling Convention

## 미니 예제
```gdb
(gdb) x/i $rip
=> 0x555555555185 <check_password+15>:	cmp    eax,0x0
(gdb) stepi
(gdb) info registers eflags
eflags         0x246               [ PF ZF IF ]
(gdb) x/i $rip
=> 0x555555555189 <check_password+19>:	je     0x5555555551a5 <check_password+35>
```
`cmp eax,0x0` 실행 후 `ZF`가 세팅된 것을 확인했으므로, 다음 `je`(ZF=1이면 점프)는 실제로 점프가 일어날 것이라고 실행 전에 예측할 수 있다.

## 관련 글
- REV-0189 — GDB x 명령으로 메모리 보기
- REV-0190 — GDB disassemble와 현재 RIP 주변 보기
- REV-0106 — SysV AMD64 Calling Convention

## 출처/검증
- `info registers`, `print $레지스터`, `eflags` 표시 형식: GDB 공식 온라인 문서("Registers") 기준.
- `ZF`/`SF`/`CF`/`OF` 플래그의 의미와 `cmp`/조건 분기 관계: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 1 (EFLAGS 챕터) 기준 (2026-09-08 검증).
