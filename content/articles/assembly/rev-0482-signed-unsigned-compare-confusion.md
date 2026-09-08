---
id: REV-0482
title: "부호 있는 비교와 없는 비교를 헷갈려서 틀렸을 때"
slug: "rev-0482-signed-unsigned-compare-confusion"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - signed unsigned confusion
  - 부호 비교 혼동
  - JG vs JA
  - JL vs JB
  - signed comparison
  - unsigned comparison
  - 음수가 큰 수로 보임
  - CF vs SF OF
  - 부호 없는 큰 수
  - 정수 오버플로우 우회
aliases:
  - signed unsigned 차이
  - jg랑 ja 차이
  - jl이랑 jb 차이
  - 음수 비교가 이상함
symptom_keywords:
  - 값이 갑자기 음수로 보임
  - 음수인데 엄청 큰 수로 표시됨
  - jg를 썼는데 결과가 이상함
  - ja jb jg jl 차이를 모르겠음
  - 배열 인덱스 체크가 우회되는 이유를 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
CPU는 레지스터에 든 비트 패턴이 "부호 있는 수"인지 "부호 없는 수"인지 스스로 알지 못하며, 어떤 `Jcc`(`JG/JL` 계열인지 `JA/JB` 계열인지)를 쓰느냐에 따라 **같은 비트 패턴이 음수로도, 매우 큰 양수로도 해석**될 수 있다는 것이 이 혼동의 근본 원인이다.

## 언제 검색해야 하나
- 디버거에서 어떤 값이 `0xFFFFFFFF`처럼 보이는데 이게 "-1"인지 "약 43억"인지 헷갈릴 때
- `JG`/`JL`(signed)과 `JA`/`JB`(unsigned)가 왜 별도로 존재하는지, 언제 뭘 써야 하는지 궁금할 때
- 배열 인덱스나 길이 검사 코드가 `JAE`/`JB` 하나로 "음수와 너무 큰 값"을 동시에 걸러내는 트릭을 이해하고 싶을 때
- CTF 문제에서 정수 비교 로직을 잘못 짚어서 계속 틀린 답을 낼 때

## 핵심 개념

### CPU는 부호를 모른다 — 프로그래머(컴파일러)가 명령어로 선택한다
32비트 레지스터에 `0xFFFFFFFF`가 들어있다고 하자. 이 비트 패턴은:
- **부호 있는(signed) 32비트 정수**로 보면 `-1`
- **부호 없는(unsigned) 32비트 정수**로 보면 `4294967295`(약 43억)

똑같은 비트 패턴인데 해석이 완전히 달라진다. CPU(하드웨어) 입장에서는 이 값 자체가 어느 쪽인지 저장돼 있지 않다 — **어떤 비교 명령어(Jcc)를 쓰느냐가 "이 값을 부호 있는 수로 취급하겠다" 또는 "부호 없는 수로 취급하겠다"는 프로그래머의 선택**이다.

### 두 계열의 Jcc가 왜 따로 있는가
`CMP a, b`는 내부적으로 `a - b`를 계산해서 플래그(ZF, SF, OF, CF)를 세팅한다(REV-0060 참고). 이후 어떤 Jcc를 쓰느냐에 따라 그 결과를 다르게 해석한다.

- **Signed 비교 (JG/JGE/JL/JLE)**: `SF`(부호 플래그)와 `OF`(오버플로우 플래그)를 결합해서 판단한다. 이 방식은 뺄셈 도중 오버플로우가 발생해도(예: `INT_MIN - 1`) 올바른 부호 있는 결과를 얻도록 설계되어 있다.
- **Unsigned 비교 (JA/JAE/JB/JBE)**: `CF`(캐리 플래그)와 `ZF`를 사용한다. 뺄셈에서 빌림(borrow)이 발생했는지만으로 크고 작음을 판단하며, 음수라는 개념 자체가 없다 — 모든 값은 0 이상의 큰 양수로 취급된다.

즉 `CMP`는 두 계열의 플래그를 **동시에** 다 세팅해두고, 이후 어떤 Jcc를 골라 쓰느냐가 "이걸 signed로 볼지 unsigned로 볼지"를 결정하는 구조다.

### 실전에서 가장 흔한 함정: 배열 인덱스/길이 체크
C 코드에서 흔히 이렇게 쓴다.
```c
if (index < 0 || index >= array_len) {
    // 잘못된 인덱스
}
```
이걸 컴파일러가 **unsigned 비교 하나로 합치는 최적화**를 하는 경우가 매우 흔하다.
```asm
cmp   eax, array_len     ; eax = index
jae   invalid_index      ; unsigned 비교: eax >= array_len 이면 (부호 없는 큰 수 포함) 무효
```
`index`가 음수(예: `-1` = `0xFFFFFFFF`)라면, 이걸 **unsigned로 재해석**하는 순간 매우 큰 값이 되어 `array_len`보다 항상 크게 되므로 자동으로 `jae`(즉 "무효 처리") 분기를 탄다. 이 트릭 하나로 "음수 검사"와 "너무 큰 값 검사"를 `JB`/`JAE` 단 하나의 unsigned 비교로 동시에 처리하는 것이다. 이걸 모르고 "부호 검사가 빠졌다"고 오해하는 게 흔한 실수다 — 사실은 unsigned 비교 자체가 이미 음수를 걸러내고 있다.

반대로, 이 트릭을 역이용해서 **정수 오버플로우/부호 취급 차이로 검증 로직을 우회하는 것**도 CTF에서 흔한 패턴이다. 프로그램이 실수로 signed 비교(`JL`)를 써야 할 자리에 unsigned(`JB`)를 쓰거나 그 반대인 경우, 음수 입력으로 검사를 우회할 여지가 생긴다.

### IDA에서 부호 표현 전환
IDA는 기본적으로 변수/상수를 부호 있는 형태로 보여줄지 없는 형태로 보여줄지 자동 판단하지만, 종종 실제 의도와 다르게 보일 수 있다. 값 위에 커서를 놓고 특정 단축키(R 계열, 상세는 REV-0149 참고)로 hex/signed/unsigned 표시를 전환하며 눈으로 직접 비교해보는 것이 가장 확실하다.

## 화면/코드에서 보이는 징후
- `cmp eax, 10 / jg over_ten`(signed) vs `cmp eax, 10 / ja over_ten`(unsigned) — 니모닉 한 글자 차이(G vs A)로 완전히 다른 해석
- 디버거에서 특정 레지스터 값이 `0xFFFFFFxx`처럼 최상위 비트가 1인 큰 hex 값으로 보임 — signed로 보면 음수일 가능성
- 디컴파일 결과에서 변수 타입이 `unsigned int`/`DWORD`로 나오는데 원본 로직은 음수를 다루는 것처럼 보임
- 하나의 `jae`/`jb`가 "0 이상 && 길이 미만" 두 조건을 동시에 처리하는 패턴

## 가장 먼저 할 것
1. 문제의 `Jcc`가 `G/L` 계열(signed)인지 `A/B` 계열(unsigned)인지부터 정확히 구분한다.
2. 그 값이 실제로 음수가 될 수 있는 변수(사용자 입력 등)인지 확인한다.
3. IDA에서 해당 값의 표시를 signed/unsigned로 전환해가며(REV-0149) 실제 의미를 눈으로 확인한다.

## 단계별 절차
**1) Jcc 계열 식별**

`JG/JGE/JL/JLE`(그리고 `JNG/JNGE/JNL/JNLE`)는 signed, `JA/JAE/JB/JBE`(그리고 `JNA/JNAE/JNB/JNBE`)는 unsigned라는 것을 REV-0069/REV-0070 표로 재확인한다.

**2) 값의 실제 범위 추적**

그 레지스터/변수가 사용자 입력에서 왔다면 음수 입력이 가능한지(부호 있는 타입으로 읽었는지) 함수 시그니처나 이전 코드에서 확인한다.

**3) 최상위 비트로 signed 해석 시 음수인지 판단**

32비트 값이라면 `0x80000000` 이상인 값은 signed로 보면 음수다(최상위 비트가 1). 64비트라면 `0x8000000000000000` 이상.

**4) 실제로 두 가지 해석을 다 계산해서 비교**

같은 비트 패턴을 signed와 unsigned 둘 다로 계산해보고, 어느 해석이 코드의 분기 결과와 일치하는지 대조한다.

## 명령어/단축키
- IDA: 값 위에서 우클릭 → "Hex"/"Signed"/"Decimal" 등 표시 전환(자세한 절차는 REV-0149)
- x64dbg: Registers 창에서 값 우클릭 → 십진수(부호 있음/없음) 토글
- GDB: `p (int)$eax` (signed로 해석) vs `p (unsigned int)$eax` (unsigned로 해석)해서 동시에 비교
- Python: `x & 0xFFFFFFFF` 로 unsigned 값 확인, `x - 0x100000000 if x >= 0x80000000 else x` 로 signed 값 수동 변환

## 출력 해석
- signed로 해석했을 때 음수가 나오고 코드가 `JL`/`JG` 계열을 쓴다면 그 음수 자체를 정상적으로 다루도록 설계된 코드다.
- unsigned로 해석했을 때만 말이 되는 큰 값이 나오고 코드가 `JA`/`JB` 계열을 쓴다면, 음수 개념이 아예 없고 "매우 큰 양수"로 취급되는 코드다.
- 두 해석이 코드의 의도(변수명, 함수 목적)와 안 맞으면 signed/unsigned 선택 자체가 버그이거나, 의도적인 우회 지점일 수 있다.

## 흔한 실수
- `JG`와 `JA`, `JL`과 `JB`를 그냥 "크다/작다"로 뭉뚱그려 같은 의미라고 생각하는 것 — 음수가 섞이는 순간 결과가 완전히 달라진다.
- 값이 큰 hex(`0xFFFFFFF0` 등)로 보이면 무조건 "이상한 값" 또는 "포인터"라고 오해하는 것 — 부호 있는 관점에서는 그냥 작은 음수(`-16`)일 수 있다.
- unsigned 비교 하나(`jae`)가 실제로는 "음수 검사 + 상한 검사"를 동시에 하고 있다는 걸 못 보고, 음수 검사가 빠졌다고 착각해서 우회를 시도했다가 실패하는 것.
- signed/unsigned 여부를 변수의 C 타입 선언(`int` vs `unsigned int`)만으로 짐작하고 실제 어셈블리의 Jcc는 확인하지 않는 것 — 컴파일러가 항상 타입대로 명령어를 고르는 게 맞지만, 최적화로 다른 형태가 섞일 수 있으므로 실제 니모닉을 봐야 한다.

## 막혔을 때 다음 체크
- Jcc 조건 방향 자체가 헷갈리면 → REV-0481(Jcc 조건을 반대로 착각해서 로직을 잘못 해석했을 때)
- signed/unsigned Jcc 표를 각각 자세히 보고 싶으면 → REV-0069(JG JGE JL JLE: Signed 비교 분기), REV-0070(JA JAE JB JBE: Unsigned 비교 분기)
- IDA에서 숫자 표시 형식을 바꾸는 구체적 방법이 필요하면 → REV-0149(IDA 숫자 표현 Signed Unsigned Hex 바꾸기)
- CMP가 플래그를 세팅하는 원리 자체가 궁금하면 → REV-0060(CMP: 값을 바꾸지 않는 SUB 비교)

## 미니 예제
**예제 1 — 같은 비트 패턴, 다른 Jcc, 다른 결과**
```asm
mov   eax, 0FFFFFFFFh   ; EAX = 0xFFFFFFFF (signed: -1, unsigned: 4294967295)
cmp   eax, 0
jl    is_negative        ; signed 비교: -1 < 0 이므로 점프함
; ------
mov   eax, 0FFFFFFFFh
cmp   eax, 0
jb    is_smaller          ; unsigned 비교: 4294967295 < 0 은 거짓이므로 점프 안 함
```

**예제 2 — 음수와 상한을 unsigned 하나로 동시에 걸러내는 패턴**
```c
// 원본 C
if (index < 0 || index >= 10) {
    puts("invalid index");
}
```
```asm
cmp   eax, 0Ah          ; eax = index
jae   invalid_index      ; unsigned: index가 음수든(매우 큰 값으로 재해석) 10 이상이든 여기로 옴
```
`index = -1`이면 `0xFFFFFFFF`로 unsigned 재해석되어 `10`보다 훨씬 크므로 `jae`가 자동으로 걸러낸다.

**예제 3 — signed/unsigned 선택이 버그가 되는 경우 (우회 가능성)**
```asm
; 의도는 "길이가 0~99 사이인지" 검사였는데 실수로 signed 비교를 씀
cmp   eax, 63h           ; 99
jg    invalid_length      ; signed: eax가 99보다 크면 무효
; 문제: 음수 길이(예: -1)에 대한 검사가 없다! eax=-1은 99보다 크지 않으므로 통과해버림
```
이런 코드는 음수를 길이로 넘기면 검사를 통과할 수 있는 전형적인 취약점 패턴이다.

## 관련 글
- REV-0481 — Jcc 조건을 반대로 착각해서 로직을 잘못 해석했을 때
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- Signed 비교(SF/OF 결합)와 Unsigned 비교(CF) 판단 방식: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "Jcc—Jump if Condition Is Met" 및 "CMP—Compare Two Operands" 섹션 기준.
- 2의 보수(two's complement) 표현에서 동일 비트 패턴의 signed/unsigned 해석 차이: 동일 매뉴얼 Volume 1, "4.2 Integers" 기준(2026-09-08 확인).
