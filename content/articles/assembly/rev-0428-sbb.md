---
id: REV-0428
title: "SBB: 캐리 포함 뺄셈"
slug: "rev-0428-sbb"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - SBB
  - subtract with borrow
  - 캐리 포함 뺄셈
  - 빌림 뺄셈
  - sbb 명령어
  - sbb eax eax
  - multi-precision subtraction
  - 다중 정밀도 뺄셈
  - 0 또는 -1 마스크
  - branchless mask
aliases:
  - sbb가 뭔가요
  - sbb 명령
  - sub랑 sbb 차이
  - sbb eax eax가 뭐임
  - 캐리 빼기 명령어
symptom_keywords:
  - sub 다음에 sbb가 나옴
  - sbb eax eax 패턴이 뭔지 모르겠음
  - cmp 다음에 sbb가 나옴
  - 분기 없는 마스크 생성 코드
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`SBB dst, src`는 `dst = dst - src - CF`를 계산하는 명령으로, 다중 정밀도 뺄셈에서 빌림(borrow)을 다음 자리로 전달하는 역할을 하며, `sbb eax, eax`처럼 자기 자신을 빼는 관용구는 CF 값을 그대로 `0` 또는 `0xFFFFFFFF`(전체 1비트) 마스크로 바꾸는 분기 없는(branchless) 트릭으로도 매우 자주 쓰인다.

## 언제 검색해야 하나
- `sub` 다음에 `sbb`가 나오는 다중 정밀도(bignum) 뺄셈 코드를 만났을 때
- `cmp` 직후 `sbb eax, eax` 같은 이상한 패턴이 나와서 뭘 하는 건지 모를 때
- 분기(`jcc`) 없이 조건에 따라 값을 0 또는 전체 1비트로 바꾸는 최적화된 코드를 만났을 때

## 핵심 개념

### SBB가 실제로 하는 일
`SBB dst, src`는 다음을 계산한다.
```
dst = dst - src - CF
```
`SUB`([REV-0048](./rev-0048-sub.md))와 유일한 차이는 **뺄셈 전에 현재 CF(빌림 여부)를 추가로 뺀다**는 점이다. CF가 0이면 `SBB`는 `SUB`와 완전히 동일하게 동작한다. 세로 뺄셈에서 "아랫자리에서 빌려온 만큼 이번 자리에서 하나 더 빼는" 것과 같은 개념이다.

### Intel 문법과 오퍼랜드
```
SBB r/m8,  r8      SBB r8,  r/m8
SBB r/m16, r16      SBB r16, r/m16
SBB r/m32, r32      SBB r32, r/m32
SBB r/m64, r64      SBB r64, r/m64
SBB r/m, imm8/imm16/imm32
```
결과는 항상 첫 번째(목적지) 오퍼랜드에 저장되고, `dst = dst - (src + CF)`로 계산된다.

### 플래그 변화
`SUB`와 동일하게 CF, OF, SF, ZF, AF, PF를 모두 결과에 맞춰 갱신한다. 여기서도 입력으로 쓰인 CF와 연산 후 새로 세팅되는 CF는 별개의 값이며, 새 CF는 "이번 자리에서 빌림이 또 필요했는가"를 의미한다.

### Signed/Unsigned
CF=1은 unsigned 관점에서 뺄셈 결과가 음수가 되어(즉 dst < src+CF) 빌림이 필요했다는 뜻이다. `ADC`/`SBB` 사슬에서는 최하위 워드부터 최상위 워드까지 CF(빌림)를 계속 전파시켜 다중 정밀도 값 전체를 하나의 뺄셈처럼 처리한다.

### 스택/RSP/RIP 변화
스택에는 영향이 없다. `RIP`는 명령 길이만큼 다음 명령으로 이동한다.

### 리버싱에서 특히 중요한 관용구: `SBB reg, reg`
같은 레지스터끼리 빼면 값 자체는 항상 0이 되므로(`x - x = 0`), 결과는 오직 CF에만 좌우된다.
```
CF = 0 이면: reg - reg - 0 = 0            -> reg = 0x00000000
CF = 1 이면: reg - reg - 1 = -1(전체 1비트) -> reg = 0xFFFFFFFF
```
즉 `sbb eax, eax`는 "직전 CF가 1이었으면 EAX를 전부 1비트(0xFFFFFFFF)로, 0이었으면 EAX를 전부 0으로 만든다." 이렇게 만들어진 값은 뒤따르는 `AND`/`OR`와 결합해 **조건 분기 없이** 두 값 중 하나를 선택하는 마스크로 자주 쓰인다(분기 예측 실패 페널티를 피하려는 최적화). `CMOVcc`([REV-0075](./rev-0075-cmovcc.md))와 목적은 비슷하지만 구현 방식이 다른, 더 오래된 스타일의 분기 없는 관용구다.

### 컴파일러가 만드는 전형적 패턴
1. **다중 정밀도 뺄셈**: `unsigned __int128`이나 bignum 뺄셈에서 하위 워드는 `SUB`, 그다음 워드부터는 `SBB`.
2. **부호 없는 비교 후 마스크 생성**: `cmp a, b` 다음 `sbb reg, reg`로 "a < b이면 전체 1비트, 아니면 0"인 마스크를 만들고, 이후 `and`/`or`로 두 값을 선택(예: min/max, 절댓값, 클램프 구현의 최적화된 형태).

### IDA/Ghidra 디컴파일에서 보이는 모습
디컴파일러가 `sbb reg, reg` 패턴을 인식하면 삼항 연산자나 `-(a < b)` 같은 표현으로 정리해서 보여주기도 하지만, 인식하지 못하면 원문 그대로 `CARRY` 관련 pseudo 표현이나 낯선 임시 변수와 함께 남는 경우가 많다.

## 화면/코드에서 보이는 징후
- `sub eax, [rsi]` 다음 줄에 `sbb edx, [rsi+4]` — 다중 정밀도 뺄셈
- `cmp eax, ebx` 다음 `sbb ecx, ecx` — 분기 없는 0/0xFFFFFFFF 마스크 생성 (unsigned 비교 결과 기반)
- `sbb`로 만든 마스크 레지스터가 곧바로 `and`나 `or`에 쓰이는 코드

## 가장 먼저 할 것
1. `SBB`의 두 오퍼랜드가 서로 다른 레지스터/메모리인지, 아니면 같은 레지스터끼리인지부터 확인한다. 같은 레지스터면 마스크 생성 관용구를 의심한다.
2. 다르다면 다중 정밀도 뺄셈 사슬의 일부인지 위아래 `SUB`/`SBB` 흐름을 확인한다.

## 단계별 절차
**1) 마스크 생성 관용구 해석**
```asm
cmp  eax, ebx     ; eax - ebx, unsigned 비교 -> CF = (eax < ebx)
sbb  ecx, ecx     ; ecx = 0xFFFFFFFF if eax<ebx(unsigned) else 0
and  ecx, edi     ; edi 값을 조건부로 선택 (마스킹)
```
→ `ecx = (eax < ebx) ? edi : 0` 형태의 분기 없는 선택으로 해석한다.

**2) 다중 정밀도 뺄셈 사슬 해석**
```asm
mov  eax, [rdi]
sub  eax, [rsi]      ; 하위 32비트
mov  [rbx], eax
mov  eax, [rdi+4]
sbb  eax, [rsi+4]     ; 상위 32비트 - 하위에서 빌려온 만큼 추가로 뺌
mov  [rbx+4], eax
```

## 명령어/단축키
- IDA/x64dbg: F7/F8로 `CMP`→`SBB`를 한 줄씩 실행하며 CF와 목적지 레지스터 값을 비교
- GDB/Pwndbg: `stepi`, `info registers eflags`로 CF 확인

## 출력 해석
- `sbb reg, reg` 직후 레지스터가 `0` 또는 `0xFFFFFFFF`(64비트면 `0xFFFFFFFFFFFFFFFF`)만 나온다면 마스크 생성 관용구가 맞다는 강력한 증거다.
- 다중 정밀도 사슬에서는 CF=1이 이어질수록 더 상위 워드까지 빌림이 전파된다.

## 흔한 실수
- `sbb eax, eax`를 보고 "왜 자기 자신을 빼지?"라며 의미 없는 코드로 착각하는 것 — 실제로는 CF를 마스크로 변환하는 매우 흔한 최적화 관용구다.
- `SBB`를 항상 다중 정밀도 뺄셈으로만 해석하는 것 — 오퍼랜드가 같은 레지스터인지 먼저 확인해야 어느 패턴인지 정확히 판단할 수 있다.
- `SUB`와 `SBB`를 같은 것으로 취급해 CF 반영을 빠뜨리는 것.

## 막혔을 때 다음 체크
- `sbb`로 만들어진 마스크가 어디에 쓰이는지 모르겠다면 → 바로 다음 줄의 `AND`/`OR`/`XOR` 사용처를 따라가 어떤 값을 조건부로 선택/제거하는지 확인한다.
- 다중 정밀도 뺄셈인지 확신이 안 서면 → 관련된 워드 개수(반복 횟수, 배열 크기)를 세어 몇 비트짜리 연산인지 역산한다.
- 캐리를 만드는 명령이 무엇인지 헷갈리면 → [REV-0088 — 플래그 레지스터 개요](./rev-0088-flags-overview.md) 표를 참고한다.

## 미니 예제
**예제 1 — CF를 0/0xFFFFFFFF 마스크로 바꾸는 관용구**
```c
unsigned int select(unsigned int a, unsigned int b, unsigned int x) {
    return (a < b) ? x : 0;
}
```
```asm
cmp  eax, ebx    ; a, b 비교
sbb  ecx, ecx    ; ecx = (a<b) ? 0xFFFFFFFF : 0
and  ecx, edx    ; edx = x, 결과는 x 또는 0
```

**예제 2 — 64비트 두 개로 표현된 128비트 뺄셈**
```asm
mov  rax, rdi
sub  rax, rdx        ; 하위 64비트
mov  rcx, rsi
sbb  rcx, r8           ; 상위 64비트 - 빌림
```

**예제 3 — 절댓값을 분기 없이 구하는 고전 트릭 (SBB + XOR)**
```c
int myabs(int x) {
    return x < 0 ? -x : x;
}
```
```asm
mov  eax, edi
cdq                  ; edx = (eax의 부호를 전체 비트로 확장) = 0 또는 0xFFFFFFFF
xor  eax, edx
sub  eax, edx         ; edx가 0xFFFFFFFF(즉 x<0)일 때 2의 보수 음수 변환 완성
```
이 예제는 엄밀히는 `SBB`가 아니라 `CDQ`+`XOR`+`SUB` 조합이지만, "부호/캐리를 전체 비트 마스크로 바꿔 분기 없이 값을 조작한다"는 점에서 `SBB reg,reg` 관용구와 사고방식이 같아 함께 알아두면 좋다.

## 관련 글
- REV-0048 — SUB: 뺄셈과 플래그
- REV-0427 — ADC: 캐리 포함 덧셈
- REV-0426 — JC와 JNC: 캐리 플래그 기반 분기 별칭
- REV-0075 — CMOVcc: 분기 없는 조건부 이동
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- `SBB` 연산 정의(`dst = dst - (src + CF)`)와 Flags Affected: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "SBB—Integer Subtraction with Borrow" 섹션 기준 (2026-09-08 검증).
- `sbb reg, reg`를 이용한 0/전체-1비트 마스크 생성 관용구: 컴파일러 최적화 출력(GCC/Clang `-O2`)에서 흔히 관찰되는 일반적 관례 기준.
