---
id: REV-0057
title: "XOR: XOR 연산과 XOR reg reg 제로화"
slug: "rev-0057-xor"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - xor
  - XOR
  - Xor
  - xor 명령어
  - xor instruction
  - "xor eax, eax"
  - "xor rax, rax"
  - "xor eax eax"
  - 레지스터 제로화
  - zero register
  - 레지스터 초기화
  - xor swap
  - xor 암호화
  - xor 인코딩
  - xor cipher
  - single byte xor
  - 단일 바이트 xor
  - CTF xor
  - flag xor
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - xor 뭐임
  - xor이 뭐죠
  - xor 명령
  - XOR 명령어
  - 엑소어 명령어
  - xor eax eax 왜함
  - xor rax rax 왜함
  - xor로 제로화하는 이유
symptom_keywords:
  - xor eax eax가 왜 나오는지 모르겠음
  - xor rax rax가 왜 나오는지 모르겠음
  - xor 명령이 레지스터를 왜 0으로 만드는지 모르겠음
  - ctf에서 xor 루프가 나오는데 뭔지 모르겠음
  - xor 키로 복호화하는 코드
last_verified: "2026-09-08"
---

## 한 줄 요약
`XOR`는 두 오퍼랜드를 비트 단위 배타적 논리합(XOR) 연산해서 목적지에 저장하는 명령어이며, 특히 `xor eax, eax`(자기 자신과 XOR)는 디스어셈블리에서 가장 흔히 보이는 "레지스터를 0으로 만드는" 표준 관용구다.

## 언제 검색해야 하나
- `xor eax, eax`, `xor rax, rax`, `xor ecx, ecx` 처럼 같은 레지스터를 두 번 쓰는 코드를 만났는데 이게 계산인지 초기화인지 헷갈릴 때
- CTF 문제에서 반복문 안에 `xor al, key` 같은 코드가 나와서 이게 암호화/복호화 로직인지 판단해야 할 때
- 두 값을 스왑(교환)하는데 임시 변수 없이 XOR 세 번으로 처리된 코드를 만났을 때
- XOR 뒤에 오는 플래그(ZF, CF, OF)가 어떻게 세팅되는지 정확히 알아야 할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
XOR dest, src
```
- `dest = dest XOR src`, 결과는 dest에 저장.
- `dest`는 레지스터/메모리, `src`는 레지스터/메모리/즉시값. 메모리-메모리 조합은 불가.
- 예: `xor eax, ebx`, `xor eax, 0FFh`, `xor al, dl`.

### 레지스터/메모리에 미치는 효과
XOR는 "두 비트가 다르면 1, 같으면 0"이다.
```
  1010 1100
XOR 0000 1111
= 1010 0011
```
이 성질 때문에 XOR는 다음과 같은 독특한 특징을 가진다: **어떤 값을 같은 값으로 두 번 XOR하면 원래 값으로 되돌아온다** (`x ^ k ^ k == x`). 이것이 XOR 기반 암호화의 핵심 원리다.

### 플래그 변화
- **ZF**: 결과가 0이면 1
- **SF**: 결과의 최상위 비트가 1이면 1
- **PF**: 결과 하위 1바이트의 1비트 개수가 짝수면 1
- **CF = 0**, **OF = 0** (항상 무조건 클리어)
- **AF**: 정의되지 않음

### `xor eax, eax` — 레지스터를 0으로 만드는 표준 관용구
같은 오퍼랜드를 자기 자신과 XOR하면 모든 비트 쌍이 "같은 값끼리" 비교되므로 결과는 **항상 0**이다(원래 값이 무엇이었든 상관없다). 이때 세팅되는 플래그는 명확하다:
- **ZF = 1** (결과가 0이므로)
- **CF = 0**, **OF = 0** (XOR는 항상 클리어)
- **SF = 0** (0은 음수가 아니므로)
- **PF = 1** (0은 1비트 개수가 0개, 즉 짝수이므로)

**왜 `mov eax, 0` 대신 `xor eax, eax`를 쓰는가:**
1. **인코딩 크기**: `xor eax, eax`는 2바이트(`31 C0`)인 반면, `mov eax, 0`은 5바이트(`B8 00 00 00 00`)다. 코드 크기가 작아진다.
2. **속도/포트 활용**: 많은 x86 CPU에서 `xor reg, reg`는 "레지스터 제로화(zeroing idiom)"로 특별 인식되어 실행 유닛을 거치지 않고 처리되거나(제로화 전용 최적화), 레지스터 이름 변경(rename)만으로 끝나는 경우가 많아 사실상 무료에 가깝다.
3. **부수효과 차이**: `mov eax, 0`은 플래그를 **전혀 건드리지 않는다.** 반면 `xor eax, eax`는 ZF=1, CF=0, OF=0, SF=0, PF=1로 **플래그를 명시적으로 세팅한다.** 코드 흐름상 플래그가 이미 세팅되어 있어야 하거나, 반대로 플래그를 건드리면 안 되는 상황에서는 이 차이가 실제로 컴파일러의 명령어 선택에 영향을 준다.

**x64에서의 추가 효과 — 상위 32비트도 함께 0이 됨**: x64에서 32비트 레지스터(`eax` 등)에 쓰기 연산을 하면, x86-64 아키텍처 규칙에 따라 **상위 32비트가 자동으로 0으로 클리어**된다(이는 XOR만의 특별한 규칙이 아니라 모든 32비트 목적지 쓰기에 적용되는 일반 규칙이다). 따라서 `xor eax, eax` 한 줄로 `RAX` 전체 64비트가 0이 된다. 64비트 전체를 명시적으로 쓰려면 `xor rax, rax`(REX 프리픽스 포함, 3바이트)를 쓰기도 하지만, 결과는 `xor eax, eax`와 동일하다.

### 신호 있음/없음(signed/unsigned) 관점
XOR 자체는 부호 개념이 없는 순수 비트 연산이다. 다만 `xor eax, eax`의 결과 0은 signed/unsigned 어느 쪽으로 해석해도 0이므로 안전하다.

### 스택/RSP/RIP 변화
없음.

### XOR 기반 인코딩/암호화와 CTF
XOR는 CTF의 "플래그 검증(flag-checking)" 알고리즘에서 극도로 자주 등장한다. 이유는 간단하다: `encrypted[i] = plain[i] ^ key[i]`로 인코딩하면, 정확히 같은 연산을 다시 적용하는 것만으로 복호화가 된다(`plain[i] = encrypted[i] ^ key[i]`). 그래서 다음과 같은 반복문을 보면 단일 바이트(또는 반복 키) XOR 인코딩을 의심해야 한다:
```asm
loop_start:
    mov  al, [rsi + rcx]
    xor  al, 5Ah          ; 고정 키 0x5A와 XOR
    mov  [rdi + rcx], al
    inc  rcx
    cmp  rcx, len
    jl   loop_start
```
이런 코드를 보면 파이썬 등으로 같은 키를 XOR해서 되돌리면 원본 문자열(플래그)을 복구할 수 있는 경우가 많다. 다만 XOR 인코딩은 암호학적으로 약하다 — 키가 반복되고 평문의 일부(예: `flag{`처럼 알려진 접두사)를 알고 있으면 키를 역산할 수 있다는 점도 리버싱에서 자주 활용된다.

### XOR 스왑 트릭
임시 변수 없이 두 값을 교환하는 고전적인 트릭도 XOR의 자기소거 성질을 이용한다:
```
a = a ^ b
b = a ^ b   ; b = (a^b)^b = a
a = a ^ b   ; a = (a^b)^a = b (여기서 b는 이미 원래 a)
```
컴파일러가 자동으로 이런 코드를 생성하는 경우는 드물지만(레지스터가 충분하면 그냥 `mov`+임시 레지스터를 씀), 난독화된 코드나 CTF의 손으로 짠 어셈블리, 옛날 최적화 기법에서 등장할 수 있다.

## 화면/코드에서 보이는 징후
- `xor eax, eax` / `xor ecx, ecx` / `xor rax, rax` — 레지스터를 0으로 초기화 (함수 시작부, 반환값 0 준비, 루프 카운터 초기화 등)
- 반복문 안의 `xor al/reg, 상수` — 단일 바이트/반복 키 XOR 인코딩·복호화 의심
- `xor eax, eax` 직후 바로 `ret` — 함수가 0을 반환 (`return 0;`)
- 세 개의 연속된 `xor` (`xor a,b` / `xor b,a` / `xor a,b`) — XOR 스왑

## 가장 먼저 할 것
1. 두 오퍼랜드가 완전히 같은 레지스터인지 확인 (같으면 100% 제로화 목적)
2. 다르다면 실제 데이터 변환(암호화/체크섬/난독화) 연산인지 확인
3. 반복문 안에 있다면 키가 고정 상수인지, 다른 배열/버퍼에서 오는지 확인

## 단계별 절차

**1) 자기 자신 XOR (제로화) 인식**
```asm
xor eax, eax   ; eax = 0, RAX 전체(x64) = 0
```
이후 `eax`/`rax`를 반환값이나 카운터로 쓰는지 확인한다.

**2) 반복문 안의 XOR 인코딩 인식**
```asm
xor_loop:
    movzx eax, byte ptr [rsi+rcx]
    xor   eax, 33h
    mov   [rdi+rcx], al
    inc   rcx
    cmp   rcx, 20h
    jl    xor_loop
```
키(`0x33`)와 길이(`0x20`)를 확인하고, 파이썬으로 동일하게 XOR해서 복호화를 재현한다.

**3) XOR 스왑 인식**
```asm
xor eax, ebx
xor ebx, eax
xor eax, ebx
```
결과적으로 `eax`와 `ebx`의 값이 교환된 것과 같다.

**4) 플래그 부수효과 활용 코드 인식**
```asm
xor eax, eax   ; ZF=1, SF=0, CF=0, OF=0을 만들어 놓고
jz  always_taken  ; 항상 분기 (거의 실행되지 않지만 이론상 가능한 패턴)
```

## 명령어/단축키
- Python으로 XOR 복호화 재현:
  ```python
  enc = bytes.fromhex("...")
  key = 0x5A
  plain = bytes(b ^ key for b in enc)
  ```
- IDA: `xor eax, eax` 패턴은 IDA가 자동으로 "mov eax, 0"과 동일하게 취급해 그래프 뷰에서 특별한 강조는 안 하지만, F5 디컴파일에서는 그냥 `eax = 0`으로 정리된다.

## 출력 해석
- IDA/Ghidra 디컴파일러는 `xor eax, eax`를 거의 예외 없이 `eax = 0`(또는 변수 초기화 `int v1 = 0;`)로 단순화해서 보여준다 — 원본이 XOR였다는 사실 자체는 디컴파일 결과에서 사라진다. 진짜 XOR 연산인지 확인하려면 디스어셈블리(어셈블리 원문)를 봐야 한다.
- 반복문 안의 실제 XOR 암호화는 Ghidra/IDA 모두 `v1 = v1 ^ key;` 형태로 그대로 보여준다(이건 결과가 0으로 고정되지 않으므로 단순화되지 않는다).

## 흔한 실수
- `xor eax, eax`를 "뭔가 복잡한 계산"이라 오해하고 값을 추적하려 애쓰는 것 — 두 오퍼랜드가 같으면 무조건 결과는 0이다. 계산이 아니라 초기화다.
- XOR를 "곱셈/나눗셈 같은 진짜 수학 연산"으로 착각하는 것 — XOR는 산술 연산이 아니라 순수 비트 연산이다. `x ^ 2`는 `x * 2`나 `x XOR 2진수 10`과 전혀 다른 결과를 낸다.
- CTF에서 XOR 인코딩을 보고 "복잡한 암호"라고 지레 겁먹는 것 — 키가 짧고 반복되는 XOR는 평문의 일부만 알아도(예: `flag{`) 키를 바로 역산할 수 있는 매우 약한 인코딩이다.
- `mov eax, 0`과 `xor eax, eax`가 "완전히 동일하다"고 착각하는 것 — 결과 레지스터 값은 같지만, **플래그에 미치는 영향이 다르다.** `mov`는 플래그를 전혀 안 건드리고, `xor`는 ZF/CF/OF/SF/PF를 명시적으로 세팅한다.

## 막혔을 때 다음 체크
- 반복문 안의 XOR가 도무지 안 풀린다면 → 키가 고정 상수가 아니라 인덱스에 따라 달라지는(예: `xor al, [key_table+rcx]`) 다중 바이트 키일 수 있으니 키 소스를 다시 확인.
- `xor eax, eax` 다음 코드가 예상과 다르게 동작한다면 → 정말로 두 오퍼랜드가 완전히 같은 레지스터인지(대소문자/크기 접미사까지) 다시 확인 — `xor eax, ebx`처럼 다른 레지스터면 진짜 계산이다.
- XOR 복호화 스크립트 결과가 깨진 문자로 나온다면 → 키 바이트 순서, 키 길이, 인코딩 시작 오프셋을 다시 확인.

## 미니 예제

**예제 1 — 함수가 0을 반환**
```c
return 0;
```
```asm
xor eax, eax
ret
```

**예제 2 — 반환값 레지스터 초기화 후 조건부 설정 (불리언 반환)**
```c
int result = (a == b);
```
```asm
xor eax, eax        ; result = 0으로 먼저 초기화
cmp ecx, edx
sete al              ; 같으면 al=1 (REV-00xx SETcc 참고 예정)
```

**예제 3 — 단일 바이트 XOR 키 복호화 루프**
```c
for (int i = 0; i < len; i++)
    buf[i] ^= 0x5A;
```
```asm
xor_loop:
    movzx eax, byte ptr [rdi+rcx]
    xor   al, 5Ah
    mov   [rdi+rcx], al
    inc   rcx
    cmp   rcx, len
    jl    xor_loop
```

**예제 4 — XOR 스왑 (임시 변수 없이 두 값 교환)**
```asm
xor eax, ebx
xor ebx, eax
xor eax, ebx
```

## 관련 글
- [REV-0055 — AND: 마스크와 비트 제거](rev-0055-and.md)
- [REV-0056 — OR: 비트 설정](rev-0056-or.md)
- [REV-0058 — NOT: 비트 반전](rev-0058-not.md)
- [REV-0059 — TEST: 값을 바꾸지 않는 AND 비교](rev-0059-test.md)
- [REV-0026 — 8비트 16비트 24비트 32비트 64비트 마스크](../binary-basics/rev-0026-bit-masks.md)
- 알고리즘 패턴 카테고리의 XOR 기반 인코딩/체크섬 탐지 글 (예정)

## 출처/검증
- XOR 명령어의 오퍼랜드/플래그 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "XOR—Logical Exclusive OR" 섹션 기준 (2026-09-08 검증).
- `xor reg, reg` 제로화 관용구와 컴파일러/CPU 최적화 근거: Agner Fog, "Optimizing subroutines in assembly language" (레지스터 제로화 관용구 섹션) 기준.
- x64에서 32비트 목적지 쓰기 시 상위 32비트 자동 클리어 규칙: Intel SDM Volume 1, "General-Purpose Registers in 64-Bit Mode" 기준.
