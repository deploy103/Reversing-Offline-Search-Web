---
id: REV-0453
title: "짧은 if문이 SETcc로 컴파일되는 패턴"
slug: "rev-0453-short-if-setcc-pattern"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - SETcc
  - SETE
  - SETNE
  - SETG
  - SETL
  - bool 대입 패턴
  - boolean 변환 어셈블리
  - MOVZX SETcc
  - branchless boolean
aliases:
  - bool 변수가 어떻게 만들어지는지 모르겠음
  - a == b 어셈블리에 jmp가 없음
  - sete al이 뭔지 모르겠음
  - 비교 결과가 바로 변수로 저장됨
symptom_keywords:
  - cmp 다음에 바로 sete나 setne가 나옴
  - setcc 다음에 movzx eax al이 나옴
  - if문인데 jcc 대신 setcc가 쓰임
  - bool 반환값이 al 레지스터로만 나옴
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`bool r = (a == b);`처럼 비교 결과 자체를 `0` 또는 `1`이라는 **값**으로 저장하기만 하고 그 값에 따라 즉시 다른 실행 경로로 갈라지지는 않는 코드는, `CMP`/`TEST` 직후 `Jcc`로 분기하는 대신 `SETcc`(REV-0076)로 플래그를 바로 0/1 바이트로 바꿔서 저장하고, 그 뒤에 상위 바이트를 정리하는 `MOVZX`가 따라붙는 형태로 컴파일되는 경우가 많다.

## 언제 검색해야 하나
- `bool`을 반환하거나 대입하는 짧은 비교식(`a == b`, `a > b`, `x != 0`)인데 어셈블리에 `Jcc`+`MOV 0`+`JMP`+`MOV 1` 같은 분기 구조가 아니라 `CMP` 직후 바로 `SETcc`가 나올 때
- `SETE`, `SETNE`, `SETG`, `SETL`, `SETA`, `SETB` 뒤에 `MOVZX eax, al` 같은 코드가 항상 붙어 있어서 왜 al만 쓰고 바로 eax로 확장하는지 궁금할 때
- 함수의 반환값이 `AL`(1바이트)만 사용하는데 IDA가 `bool` 반환형으로 인식했을 때
- REV-0452(CMOVcc/삼항 연산자 패턴)와 뭐가 다른지 헷갈릴 때

## 핵심 개념

### SETcc는 "값을 만드는" 명령, CMOVcc는 "값을 고르는" 명령
REV-0452에서 다룬 `CMOVcc`는 **미리 계산된 두 값(a, b) 중 하나를 조건에 따라 선택**하는 명령이다. 반면 `SETcc`는 선택할 두 값이 없다 — 그냥 **플래그 조건 자체를 0 또는 1이라는 새로운 값으로 만들어낸다.** 이 차이는 원본 C 코드의 형태와 직결된다.
- `x = cond ? a : b;` (서로 다른 두 값 중 선택) → `CMOVcc` 패턴(REV-0452)
- `bool b = cond;` 또는 `int r = (a > b);` (조건 자체가 결과값, 참=1/거짓=0) → `SETcc` 패턴(이 글)

### 전형적인 코드 형태
```asm
; bool eq = (a == b);
mov     eax, [a]
cmp     eax, [b]
sete    al           ; ZF=1(같음)이면 al=1, 아니면 al=0
movzx   eax, al       ; 상위 24/56비트를 0으로 채워 eax 전체를 깨끗한 0 또는 1로 만듦
```
`SETcc`는 **오직 1바이트 레지스터(AL, BL, CL, DL, 또는 SIL/DIL/R8B 등)에만 쓸 수 있다.** 8/16/32/64비트 전체 레지스터에는 직접 쓸 수 없다. 그리고 `SETcc`는 그 1바이트 레지스터에 정확히 `0`(조건 거짓) 또는 `1`(조건 참)만 써넣으며, **레지스터의 상위 바이트는 전혀 건드리지 않는다.** 그래서 이 값을 진짜 `int`/`bool` 변수처럼 온전한 32/64비트 값으로 쓰려면, 반드시 `MOVZX`(REV-0040, 상위 비트를 0으로 채우는 zero-extension)로 상위 바이트를 정리해야 한다 — 이 `SETcc` 다음의 `MOVZX`는 거의 예외 없이 따라붙는 짝꿍이다.

### CMOVcc 조건 코드와 동일한 규칙
`SETE/SETNE/SETG/SETL/SETGE/SETLE`(signed), `SETA/SETB/SETAE/SETBE`(unsigned) 등, `cc` 접미사는 REV-0069/REV-0070/REV-0075/REV-0452에서 다룬 `Jcc`/`CMOVcc`와 완전히 동일한 조건 코드 인코딩을 공유한다. 즉 "`JG`가 참일 조건"과 "`SETG`가 1을 쓰는 조건"은 정확히 같다.

### 짧은 &&/||와 결합될 때
여러 비교를 `&&`/`||`로 묶은 짧은 표현식도 SETcc + 논리 연산으로 압축되는 경우가 있다.
```c
bool both = (a > 0) && (b > 0);
```
```asm
xor     eax, eax
cmp     [a], 0
setg    al             ; a > 0 이면 al = 1
xor     ecx, ecx
cmp     [b], 0
setg    cl              ; b > 0 이면 cl = 1
and     eax, ecx         ; 둘 다 1이어야 최종 결과가 1 (AND = 논리곱)
```
이는 REV-0459(`&&`, `||`의 단축 평가 컴파일 패턴)와 이어지는 내용이며, 두 조건 모두 부작용이 없고 계산이 저렴할 때 컴파일러가 분기(단축 평가) 대신 이런 비트 연산 압축을 선택한다.

### 레지스터/메모리 효과와 플래그
- `SETcc`는 **EFLAGS를 전혀 변경하지 않는다** — 오직 읽기만 한다. 그래서 같은 `CMP`/`TEST` 결과를 여러 `SETcc`로 재사용하는 코드(예: `sete al` 다음에 다른 레지스터에 `setne bl`)가 가능하다.
- 목적지가 **반드시 8비트 레지스터 또는 8비트 메모리**여야 한다 — `SETcc eax`처럼 32비트 레지스터를 직접 쓸 수 없다.
- 목적지 레지스터의 값을 미리 0으로 만들어두는 관용구(`xor eax, eax` 후 `sete al`)도 흔하다 — 이러면 `MOVZX` 없이도 `AL`을 채우는 즉시 `EAX` 전체가 0 또는 1이 되기 때문에, 컴파일러가 `MOVZX` 대신 이 순서를 선택하기도 한다.
- signed/unsigned은 `CMOVcc`와 마찬가지로 어떤 `SETcc` 변형(G/L 계열 vs A/B 계열)을 쓰느냐로 결정된다.
- 스택/RIP에는 영향이 없다.

### IDA/Ghidra 디컴파일에서 보이는 형태
Hex-Rays와 Ghidra 모두 `SETcc`+`MOVZX` 조합을 거의 항상 원본 `a == b`, `a > b` 같은 boolean 표현식으로 정확히 복원한다. 함수 반환 타입이 `bool`이나 `BOOLEAN`으로 추론되는 것도 이 패턴이 있을 때 흔히 나타난다.

## 화면/코드에서 보이는 징후
```asm
; bool 함수 반환값
cmp     [rbp-4], 0
setne   al
movzx   eax, al
ret
```
```asm
; 비교 결과를 정수 0/1로 저장
cmp     eax, ecx
setg    al
movzx   eax, al
mov     [result], eax
```
```asm
; 0으로 미리 초기화 후 SETcc (MOVZX 생략형)
xor     eax, eax
cmp     rdi, rsi
sete    al
```

## 가장 먼저 할 것
1. `CMP`/`TEST` 직후 `Jcc`가 아니라 `SETcc`가 오는지 확인한다 — 있으면 boolean 값 생성 패턴이다.
2. `SETcc` 목적지가 1바이트 레지스터(`AL` 등)인지 확인하고, 바로 뒤에 `MOVZX`(또는 사전 `XOR`로 상위 비트 정리)가 따라오는지 본다.
3. 이 0/1 값이 이후 그대로 반환되는지, 다른 변수에 저장되는지, 아니면 추가 논리 연산(`AND`/`OR`)에 쓰이는지 추적한다.

## 단계별 절차

**1) 조건 복원**

`CMP`/`TEST` 오퍼랜드와 `SETcc`의 `cc` 접미사를 REV-0069/REV-0070 대응표에 대입해서 원래 비교 연산자를 복원한다. 예: `cmp eax, ecx` 후 `setl al`이면 "eax < ecx이면 al=1" → `al = (eax < ecx)`.

**2) 확장 방식 확인**

`MOVZX eax, al`이 뒤따르면 부호 없는 0/1 값 그대로 확장(zero-extension)된 것이고, 드물게 `MOVSX`가 쓰였다면(거의 없음, SETcc 결과는 항상 0 또는 1이라 부호 확장과 결과가 같음) 특별한 의미는 없다.

**3) 최종 사용처 확인**

이 0/1 값이 `return`으로 바로 나가면 `bool` 함수, 변수에 저장되면 플래그성 멤버 변수, `AND`/`OR`로 다른 SETcc 결과와 합쳐지면 복합 조건식(REV-0459 참고 대상)이다.

**4) CMOVcc 패턴과 구분**

목적지가 항상 0/1 두 값 중 하나라면 `SETcc`, 서로 다른 임의의 두 값(a, b) 중 하나라면 `CMOVcc`(REV-0452)다. 헷갈리면 목적지 레지스터 크기(1바이트냐 아니냐)를 보면 바로 구분된다 — `SETcc`는 항상 1바이트만 쓴다.

## 명령어/단축키
- IDA: `F5`(디컴파일, bool 표현식으로 복원되는지 확인), `SETcc` 명령 검색은 `Alt+T`(텍스트 검색)로 `set` 입력
- Ghidra: Decompile 창 자동 bool 타입 추론 확인, Listing에서 `sete`/`setne`/`setg` 등 검색
- x64dbg/GDB: `SETcc` 실행 전후 `AL`/`EAX` 값을 스텝 실행으로 비교, `p $eax`(GDB)로 최종 0/1 값 확인

## 출력 해석
- IDA가 `return a == b;` 또는 `v1 = (a > b);`로 복원하면, 원본은 `SETcc`+`MOVZX` 조합이었다는 뜻이다.
- `SETcc` 뒤에 `MOVZX`가 없고 바로 `AND`/`OR`/`TEST`가 이어진다면, 그 결과가 다른 boolean 값과 합쳐지는 복합 조건식일 가능성이 높다.
- 함수 반환값이 `AL`만 쓰고 상위 `EAX`를 신경 안 쓰는 것처럼 보인다면(호출자가 `movzx`/`and eax, 1` 등으로 정리), 그 함수가 `bool` 반환형이라는 강한 신호다.

## 흔한 실수
- `SETcc`가 32/64비트 레지스터 전체에 값을 쓴다고 착각하는 것 — 실제로는 딱 1바이트만 쓰며, 상위 비트를 정리하는 `MOVZX`가 없으면 그 값을 그대로 32/64비트로 쓸 때 이전에 남아있던 쓰레기 값이 섞일 수 있다(실제로 컴파일러 버그나 인라인 어셈블리 실수로 이런 문제가 생기기도 한다).
- `SETcc`와 `CMOVcc`를 같은 것으로 뭉뚱그려 이해하는 것 — `SETcc`는 "조건 자체를 값(0/1)으로 만든다", `CMOVcc`는 "이미 있는 두 값 중 하나를 고른다"는 근본적인 차이가 있다.
- `xor eax, eax` 다음에 오는 `SETcc`를 보고 "왜 굳이 0으로 초기화하지? SETcc가 어차피 값을 쓰는데"라고 의아해하는 것 — 이는 `MOVZX`를 아예 생략하기 위한 최적화 관용구다. `AL`만 갱신해도 `EAX` 전체가 이미 0이었으니 상위 바이트가 자동으로 0으로 유지된다.
- 부호 있는 값 비교(`SETG`/`SETL`)와 부호 없는 값 비교(`SETA`/`SETB`)를 혼동해서 결과를 반대로 해석하는 것 — REV-0069/REV-0070과 동일한 원리이므로 그 문서의 대응표를 그대로 적용해야 한다.

## 막혔을 때 다음 체크
- 조건 코드(`E`, `NE`, `G`, `L`, `A`, `B` 등)의 정확한 의미가 헷갈리면 → REV-0069(JG JGE JL JLE), REV-0070(JA JAE JB JBE), REV-0076(SETcc 원본 항목)을 다시 확인한다.
- `SETcc` 결과가 두 개 이상 합쳐지는 복잡한 조건식이면 → REV-0459(여러 조건(&&, ||)이 단축 평가로 컴파일되는 패턴)로 확장해서 이해한다.
- 이게 `SETcc`가 아니라 서로 다른 두 값을 고르는 것 같으면 → REV-0452(삼항 연산자/CMOVcc 패턴)로 이동해서 다시 구분한다.

## 미니 예제

**예제 1 — bool 반환 함수**
```c
bool is_positive(int x) {
    return x > 0;
}
```
```asm
is_positive proc near
    cmp     ecx, 0
    setg    al
    movzx   eax, al
    ret
```

**예제 2 — 동등 비교 결과를 지역 변수에 저장**
```c
int flag = (a == b);
```
```asm
mov     eax, [a]
cmp     eax, [b]
sete    al
movzx   eax, al
mov     [flag], eax
```

**예제 3 — 사전 XOR로 MOVZX 생략**
```c
bool ge = (x >= 100);
```
```asm
xor     eax, eax
cmp     [x], 64h
setge   al          ; eax의 상위 바이트는 이미 0이므로 MOVZX 불필요
```

**예제 4 — 여러 SETcc 결과를 AND로 결합**
```c
bool in_range = (x >= 0) && (x < 100);
```
```asm
xor     eax, eax
cmp     [x], 0
setge   al
xor     ecx, ecx
cmp     [x], 64h
setl    cl
and     eax, ecx      ; 둘 다 참이어야 1
```

## 관련 글
- REV-0076 — SETcc: 조건 결과를 0 또는 1로 만들기
- REV-0452 — 삼항 연산자(?:)가 CMOVcc로 컴파일되는 패턴
- REV-0040 — MOVZX: Zero Extension 이해
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0459 — 여러 조건(&&, ||)이 단축 평가로 컴파일되는 패턴

## 출처/검증
- `SETcc` 동작(1바이트 목적지에만 0/1 저장, 플래그 미변경, 조건 코드가 Jcc/CMOVcc와 동일)은 Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2, "SETcc—Set Byte on Condition" 항목 기준.
- `MOVZX`의 zero-extension 동작은 Intel SDM Volume 2, "MOVZX" 항목 기준.
- 상위 바이트 정리를 위한 `SETcc`+`MOVZX` 또는 `XOR`+`SETcc` 코드 생성 관용구는 GCC/Clang/MSVC의 일반적인 boolean 표현식 코드 생성 관례 기준.
