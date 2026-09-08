---
id: REV-0454
title: "나눗셈이 곱셈과 시프트로 최적화되는 패턴(Magic Number)"
slug: "rev-0454-division-magic-number-pattern"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - magic number division
  - 매직 넘버 나눗셈
  - IMUL SAR 나눗셈
  - 상수 나눗셈 최적화
  - reciprocal multiplication
  - division by invariant integers
  - 0x66666667
  - 0xCCCCCCCD
aliases:
  - 나눗셈인데 div가 안 보임
  - imul 다음에 sar가 나오는데 나눗셈 같음
  - 이상한 큰 상수를 곱하는 코드
  - 나눗셈 매직넘버가 뭔지 모르겠음
symptom_keywords:
  - imul edx 다음에 sar가 나오고 원래 값을 더함
  - 이해할 수 없는 16진수 상수를 곱함
  - div idiv가 안 보이는데 나눗셈처럼 동작함
  - 상수로 나누는 코드인데 곱셈 명령만 보임
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`x / 10`처럼 **컴파일 시점에 알려진 상수로 나누는** 코드는 느린 `DIV`/`IDIV`(REV-0052/REV-0053) 대신, 그 상수에 대응하는 특수한 "매직 넘버(magic number)"를 곱하고(`IMUL`/`MUL`) 결과를 시프트(`SAR`/`SHR`)하는 방식으로 컴파일되는 경우가 대부분이며, 이는 나눗셈과 전혀 무관해 보이는 이상한 상수를 곱하는 코드를 보고도 "이건 나눗셈이다"라고 알아볼 수 있어야 하는 매우 흔한 패턴이다.

## 언제 검색해야 하나
- 소스에 `x / N`(N은 상수) 같은 나눗셈이 있어야 할 것 같은데, 디스어셈블리에 `DIV`/`IDIV`가 전혀 안 보이고 대신 `0x66666667`, `0xCCCCCCCD` 같은 알 수 없는 16진수 상수를 `IMUL`/`MUL`로 곱하는 코드가 나올 때
- `IMUL` 뒤에 `SAR`(산술 오른쪽 시프트)가 오고, 그 다음 부호 보정을 위한 `ADD`나 `SHR`이 한 번 더 붙는 패턴을 봤을 때
- CTF 문제에서 "이 이상한 상수 곱셈이 무엇을 하는지 알아내라"는 리버싱 과제를 만났을 때
- 나눗셈 결과를 역산해서 원래 나눈 값(divisor)이 무엇이었는지 알아내고 싶을 때

## 핵심 개념

### 왜 컴파일러가 DIV/IDIV를 피하는가
`DIV`/`IDIV`는 x86에서 가장 느린 정수 연산 축에 속한다 — 최신 CPU에서도 수십 사이클이 걸릴 수 있다(REV-0052, REV-0053 참고). 반면 `IMUL`/`MUL`은 몇 사이클이면 끝난다. 나누는 값(divisor)이 컴파일 시점에 확정된 상수라면, "**정확히 나눈 것과 같은 결과를 내는 곱셈+시프트 조합**"을 수학적으로 미리 계산해서 그 조합으로 바꿔치기하는 것이 훨씬 빠르다 — 이를 **부호 있는/없는 정수의 불변 나눗셈을 곱셈으로 대체(division by invariant integers using multiplication)** 라고 부르며, 컴파일러 최적화 이론에서 매우 잘 알려진 고전적인 기법이다(Henry S. Warren Jr.의 "Hacker's Delight" 책에 이 알고리즘이 상세히 정리되어 있다).

핵심 아이디어는 "1/N"을 정확한 분수 대신, 충분히 큰 고정 소수점(fixed-point) 정밀도로 근사한 정수(매직 넘버)를 만들어서, `x * 매직넘버`를 계산한 뒤 상위 비트만 취하면(즉 큰 값으로 나눈 것과 같은 효과, 시프트로 구현) 원래의 `x / N`과 정확히 같은 결과가 나오도록 매직 넘버와 시프트 양을 정밀하게 골라내는 것이다. 이 상수들은 임의로 아무거나 고른 게 아니라, 모든 가능한 `x` 값에 대해 정확한 결과를 보장하도록 정수론적으로 유도된 정확한 값이다.

### Signed 나눗셈의 전형적인 예 — x / 10
컴파일러(gcc, clang, MSVC 모두 유사한 형태)가 `int x`에 대해 `x / 10`을 컴파일하면 대략 다음과 같은 코드가 나온다(정확한 상수/레지스터 배치는 컴파일러/버전에 따라 다를 수 있다).
```asm
mov     eax, x
mov     edx, 66666667h      ; 매직 넘버 (1717986919)
imul    edx                  ; EDX:EAX = EAX(x) * 매직넘버 (64비트 곱)
sar     edx, 2               ; 상위 32비트 결과를 2비트만큼 더 시프트 (스케일 조정)
mov     eax, edx
shr     eax, 1Fh              ; x의 부호 비트를 뽑아냄 (0 또는 1)
add     eax, edx              ; 음수일 때 결과를 1 보정 (0을 향한 절삭을 맞추기 위함)
```
여기서 `IMUL edx`(오퍼랜드 하나짜리 형태)는 `EAX`와 `EDX`의 곱을 64비트 결과로 `EDX:EAX`에 남긴다(REV-0051 참고) — 즉 원래 32비트 값을 64비트 정밀도로 곱해서, 상위 32비트(`EDX`)에 "몫에 아주 가까운 값"이 나오도록 만든 것이다. 그 뒤 `SAR`로 추가 스케일을 맞추고, 마지막 `SHR`+`ADD`는 **음수를 0 방향으로 절삭(truncation toward zero)해야 하는 C의 정수 나눗셈 규칙**을 맞추기 위한 부호 보정이다(단순 시프트만으로는 음수 나눗셈이 절삭이 아니라 내림(floor)이 되어버리기 때문).

### Unsigned 나눗셈의 예 — x / 10 (unsigned)
부호 없는 나눗셈은 부호 보정이 필요 없어 더 단순하다.
```asm
mov     eax, x
mov     edx, 0CCCCCCCDh    ; unsigned 매직 넘버
mul     edx                 ; EDX:EAX = EAX * 매직넘버 (unsigned 64비트 곱)
shr     edx, 3               ; 상위 32비트를 3비트 시프트 → 몫
```
`MUL`(REV-0050, unsigned 곱셈)을 쓰고 부호 보정이 없다는 점이 signed 버전과의 핵심 차이다.

### 2의 거듭제곱으로 나누기 — 훨씬 단순한 특수 케이스
나누는 값이 2의 거듭제곱(2, 4, 8, 16, ...)이면 곱셈조차 필요 없이 시프트만으로 충분하다.
- **Unsigned**: `x / 4` → 그냥 `SHR eax, 2` (REV-0062). 보정이 전혀 필요 없다.
- **Signed**: `x / 4`는 `SAR eax, 2`만으로는 안 된다 — 음수일 때 `SAR`은 내림(floor, 더 작은 쪽으로 버림)이지만 C의 정수 나눗셈은 0을 향한 절삭이기 때문이다. 그래서 나눗셈 전에 **바이어스(bias) 보정**을 추가한다.
```asm
; signed x / 4  (x가 음수일 수도 있는 int)
mov     eax, x
cdq                      ; eax의 부호를 edx 전체에 복제 (양수면 edx=0, 음수면 edx=0xFFFFFFFF)
shr     edx, 30            ; 음수면 edx = 3(=4-1), 양수면 edx = 0
add     eax, edx            ; 음수일 때만 (divisor-1)을 더해 절삭 방향 보정
sar     eax, 2               ; 이제 산술 시프트해도 절삭 결과와 일치
```

### 레지스터/메모리 효과와 플래그
- `IMUL`/`MUL`은 곱셈 결과에 따라 `CF`/`OF`를 세팅하지만(REV-0050/0051), 이 매직 넘버 곱셈 패턴에서는 오버플로우 여부(CF/OF)를 전혀 확인하지 않는다 — 애초에 이 곱셈은 "몫을 근사"하기 위한 계산일 뿐, 곱셈 자체의 오버플로우 의미와는 무관하기 때문이다.
- `SAR`/`SHR`은 시프트되는 비트에 따라 `CF`를 세팅하지만 역시 이 패턴에서는 사용되지 않는다.
- signed/unsigned 구분은 이 최적화의 핵심 갈림길이다 — signed는 부호 보정(음수 절삭 처리) 코드가 반드시 추가로 붙고, unsigned는 곱셈+시프트만으로 끝난다.
- 스택/RIP에는 영향이 없다. 순수 레지스터 연산이다.

### 리버싱 관점의 의미
이 패턴은 **암호화나 난독화가 아니라 순수한 컴파일러 최적화**다. `IMUL`에 쓰인 이상한 상수를 보고 "해시 함수인가?", "커스텀 암호화인가?"라고 오판하지 않는 것이 중요하다. 이 패턴을 알아보는 가장 빠른 방법은:
1. `IMUL`/`MUL` 뒤에 `SAR`/`SHR`이 바로 따라오는지 확인한다.
2. 곱해지는 상수가 `0x80000000` 근처의 큰 32비트(또는 64비트) 값인지 확인한다(1/N을 32비트 고정소수점으로 근사한 값은 대체로 이런 범위에 몰린다).
3. 정 원래 나눈 값(N)이 궁금하면, Compiler Explorer(godbolt.org, 오프라인 환경이면 미리 참고 자료로 정리해두는 것을 권장) 같은 도구에 여러 N값으로 나눈 코드를 컴파일해보고 상수를 비교하거나, Hacker's Delight의 매직 넘버 표를 참고한다.

## 화면/코드에서 보이는 징후
```asm
; signed x / 10
mov     eax, ecx
mov     edx, 66666667h
imul    edx
sar     edx, 2
mov     eax, edx
shr     eax, 1Fh
add     eax, edx
```
```asm
; unsigned x / 10
mov     eax, ecx
mov     edx, 0CCCCCCCDh
mul     edx
shr     edx, 3
mov     eax, edx
```
```asm
; signed x / 4 (2의 거듭제곱, 곱셈 없이 시프트+보정만)
mov     eax, ecx
cdq
shr     edx, 30h
add     eax, edx
sar     eax, 2
```

## 가장 먼저 할 것
1. `IMUL`/`MUL` 다음에 `SAR`/`SHR`이 오는지 확인한다 — 있으면 상수 나눗셈 최적화일 가능성이 매우 높다.
2. 곱해지는 상수가 `0x8000_0000`~`0xFFFF_FFFF`(또는 64비트 유사 범위) 사이의 크고 애매한 값인지 확인한다.
3. `IMUL`/`MUL` 뒤에 부호 보정 코드(`SHR ..., 1Fh` + `ADD`, 또는 `CDQ` + `SHR` + `ADD`)가 있으면 signed 나눗셈, 없으면 unsigned 나눗셈이다.

## 단계별 절차

**1) signed/unsigned 판별**

`IMUL`(부호 있는 곱셈)이 쓰였는지 `MUL`(부호 없는 곱셈)이 쓰였는지 먼저 확인한다. 이후 부호 보정 코드 유무로 다시 한번 교차 확인한다.

**2) 원래 나눈 값(N) 추정**

정확한 매직 넘버 계산은 손으로 하기 번거로우므로, 실전에서는 (a) 알려진 상수를 표/사전 자료와 대조하거나, (b) 오프라인이라면 파이썬으로 직접 몇 가지 후보 N에 대해 매직 넘버를 계산하는 스크립트를 돌려 비교하는 방법이 실용적이다. 대략의 감으로는, N이 작을수록(2, 3, 5, 10 등) CTF/실전 바이너리에 흔히 등장한다.

**3) 시프트 양과 곱셈 상수의 관계 확인**

`SAR`/`SHR`의 시프트 양(예: 위 예제의 2, 3)은 매직 넘버 계산의 일부이므로, 이 값과 곱셈 상수를 함께 기록해두면 나중에 같은 패턴을 더 빠르게 알아볼 수 있다.

**4) IDA/Ghidra 디컴파일과 대조**

F5로 디컴파일했을 때 이미 `x / 10`처럼 깔끔하게 재인식되어 나오는 경우가 대부분이다(Hex-Rays와 Ghidra 모두 이 패턴에 대한 강력한 인식 로직을 갖고 있다) — 재인식됐다면 그대로 믿고 넘어가면 된다.

## 명령어/단축키
- IDA: `F5`(디컴파일, `/` 연산자로 재인식되는지 확인이 가장 빠른 방법), `IMUL`/`MUL` 오퍼랜드 위에서 `H`(16진수 ↔ 10진수 토글)로 상수 값을 편하게 확인
- Ghidra: Decompile 창 자동 재인식 확인, Listing에서 `imul`/`mul` 검색 후 뒤따르는 `sar`/`shr` 패턴 확인
- Python(오프라인 스크립트): `x // N`을 여러 정수로 반복 검증하는 브루트포스 스크립트로 매직 넘버 후보와 실제 나눗셈 결과가 일치하는지 검증 가능

## 출력 해석
- IDA가 `x / 10`으로 정확히 복원했다면 디컴파일러가 매직 넘버 패턴을 인식한 것이므로, 원래 어셈블리의 이상한 상수를 몰라도 결과를 신뢰할 수 있다.
- 재인식이 안 되고 `(x * -1840700269 >> 34) + ...`처럼 이상하게 남아있다면, 사람이 직접 "이건 나눗셈이다"라는 사실만 알아채고, 정확한 N값은 몰라도 로직 이해에는 지장 없는 경우가 많다(디컴파일러가 낸 수식 자체가 이미 원래 나눗셈과 수학적으로 동치이기 때문).
- 시프트 양이 매우 크면(32 이상) 64비트 나눗셈(`x64` divisor)일 가능성이 높다.

## 흔한 실수
- `IMUL`에 쓰인 이상한 16진수 상수를 보고 "해시 알고리즘"이나 "커스텀 암호화 키"로 오판해서 불필요하게 그 상수를 역산하려 드는 것 — 먼저 `SAR`/`SHR`이 뒤따르는지부터 확인하면 대부분 나눗셈임을 바로 알 수 있다.
- 매직 넘버가 특정 N에 대해 유일하다고 착각하는 것 — 실제로는 여러 개의 유효한 (매직넘버, 시프트) 조합이 같은 N에 대해 존재할 수 있으며, 컴파일러 버전/최적화 옵션에 따라 다른 상수가 나올 수 있다.
- 부호 보정 코드(`SHR ..., 1Fh` + `ADD`)를 나눗셈과 무관한 별도 로직으로 오판하는 것 — 이는 signed 나눗셈에서 음수를 0으로 절삭하기 위한 필수 보정이다.
- 2의 거듭제곱 나눗셈(`SAR`/`SHR`만 있고 곱셈이 아예 없는 경우)을 놓치고 항상 `IMUL`/`MUL`이 있어야 나눗셈이라고 단정하는 것 — 2의 거듭제곱일 때는 곱셈 없이 시프트(+ signed면 보정)만으로 끝난다는 점을 REV-0062(SHR), REV-0063(SAR)과 함께 기억해야 한다.

## 막혔을 때 다음 체크
- `IMUL`/`MUL`의 정확한 64비트 결과 배치(EDX:EAX)가 헷갈리면 → REV-0050(MUL), REV-0051(IMUL)을 다시 읽는다.
- `SAR`/`SHR`의 부호 있는/없는 시프트 차이가 헷갈리면 → REV-0062(SHR), REV-0063(SAR)을 다시 읽는다.
- 나머지 연산(`%`)이 이 패턴과 함께 나오는 코드를 만났다면 → REV-0455(나머지 연산이 어셈블리로 최적화되는 패턴)로 이동 — 나눗셈 매직 넘버를 그대로 재사용하는 후속 계산이다.
- 원래 divisor를 반드시 정확히 알아야 하는 상황(코드를 그대로 재현/패치해야 함)이라면 → 여러 후보 N에 대해 직접 컴파일해서 상수를 비교하거나, 파이썬으로 브루트포스 검증하는 것이 가장 확실하다.

## 미니 예제

**예제 1 — signed 나눗셈, 흔한 CTF 스타일**
```c
int average(int sum) {
    return sum / 3;
}
```
```asm
average proc near
    mov     eax, ecx
    mov     edx, 55555556h    ; 1/3에 대한 매직 넘버(예시)
    imul    edx
    sar     edx, 0
    mov     eax, edx
    shr     eax, 1Fh
    add     eax, edx
    ret
```
(정확한 상수는 컴파일러/버전에 따라 다를 수 있으며, 이 예제는 패턴 자체를 보여주기 위한 것이다.)

**예제 2 — unsigned 나눗셈**
```c
unsigned int avg_u(unsigned int sum) {
    return sum / 5;
}
```
```asm
mov     eax, ecx
mov     edx, 0CCCCCCCDh
mul     edx
shr     edx, 2
mov     eax, edx
```

**예제 3 — 2의 거듭제곱 나눗셈(가장 단순한 케이스)**
```c
int half(int x) {
    return x / 2;
}
```
```asm
mov     eax, ecx
mov     edx, eax
shr     edx, 1Fh    ; x가 음수면 1, 양수면 0
add     eax, edx      ; 음수일 때 절삭 보정
sar     eax, 1
```

## 관련 글
- REV-0455 — 나머지 연산(%)이 어셈블리로 최적화되는 패턴
- REV-0052 — DIV: Unsigned 나눗셈
- REV-0053 — IDIV: Signed 나눗셈
- REV-0051 — IMUL: Signed 곱셈과 컴파일러 패턴
- REV-0062 — SHR: 논리 오른쪽 시프트
- REV-0063 — SAR: 산술 오른쪽 시프트

## 출처/검증
- 상수 나눗셈을 곱셈+시프트로 대체하는 알고리즘(부호 있는/없는 경우 모두)은 Henry S. Warren Jr., "Hacker's Delight" 2nd Edition, Chapter 10 "Integer Division by Constants" 기준.
- `IMUL`/`MUL`의 64비트 결과 배치(EDX:EAX)와 `SAR`/`SHR` 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2, 각 명령어 항목 기준.
- C 정수 나눗셈이 0을 향한 절삭(truncation toward zero)이라는 규칙: ISO C 표준의 정수 나눗셈 연산자 규정 기준.
- GCC/Clang/MSVC가 상수 나눗셈에 이 최적화를 기본 적용한다는 사실은 각 컴파일러의 최적화 패스(constant division optimization) 관련 공개 문서 및 코드 생성 관례 기준.
