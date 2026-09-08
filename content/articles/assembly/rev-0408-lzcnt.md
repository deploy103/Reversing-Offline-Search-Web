---
id: REV-0408
title: "LZCNT: 선행 0 개수 세기"
slug: "rev-0408-lzcnt"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - lzcnt
  - LZCNT
  - Lzcnt
  - lzcnt 명령어
  - lzcnt instruction
  - leading zero count
  - 선행 0 개수
  - count leading zeros
  - clz
  - __builtin_clz
  - __lzcnt
  - "lzcnt eax, ebx"
  - "lzcnt rax, rax"
  - ABM
  - BMI1
aliases:
  - lzcnt 뭐임
  - lzcnt이 뭐죠
  - lzcnt 명령
  - LZCNT 명령어
  - 선행 0 카운트 명령어
symptom_keywords:
  - 최상위 1비트 위치 찾는 코드
  - log2 계산하는 어셈블리
  - lzcnt와 bsr 차이
  - 정규화 코드에서 lzcnt가 왜 나오는지
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LZCNT`(Leading Zero Count)는 오퍼랜드의 최상위 비트(MSB)부터 세어 처음으로 1이 나올 때까지의 연속된 0의 개수를 계산하는 명령어로, `BSR`(REV-0410)과 비슷한 목적이지만 0 입력에 대해서도 결과가 명확히 정의된다는 점이 다르다.

## 언제 검색해야 하나
- `lzcnt eax, ebx` 같은 명령어가 `log2` 계산이나 비트 길이 계산 코드 근처에 나올 때
- `LZCNT`와 `BSR`(비트 스캔 리버스)가 비슷해 보이는데 정확히 뭐가 다른지 궁금할 때
- 부동소수점 정규화, 가변 길이 정수 인코딩(LEB128 등), 우선순위 인코더 로직을 분석할 때
- CPU가 이 명령어를 지원하는지 확인하는 CPUID 검사 코드를 만났을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
LZCNT r16, r/m16
LZCNT r32, r/m32
LZCNT r64, r/m64   (REX.W, x64)
```
목적지는 항상 레지스터, 소스는 레지스터 또는 메모리. 소스의 최상위 비트(비트 31 또는 63)부터 아래로 내려가며 처음 1이 나오기 전까지의 0의 개수를 센다.

### 소스가 0일 때 — BSR과의 결정적 차이
소스가 완전히 0이면, `LZCNT`는 **결과를 오퍼랜드 크기(32비트면 32, 64비트면 64)로 정의**한다. 즉 "0을 넣으면 항상 32/64가 나온다"는 것이 명확히 보장된다. 반면 [BSR](rev-0410-bsf-bsr.md)은 소스가 0일 때 목적지 레지스터 값이 **정의되지 않는다(undefined)** — 프로그래머가 반드시 ZF를 먼저 확인해야 한다. 이 "0 입력에 대한 정의된 동작"이 LZCNT가 BSR보다 다루기 쉬운 이유다.

### CPU 지원 여부
`LZCNT`는 `CPUID.80000001H:ECX.LZCNT[bit 5]`로 지원 여부를 확인한다(원래 AMD의 ABM 확장에서 시작했고 이후 Intel도 지원). 지원하지 않는 구형 CPU에서 같은 바이트 인코딩(`F3 0F BD`)을 실행하면 **`#UD`가 나는 것이 아니라 `F3` 접두사가 무시되고 옛날 `BSR` 명령어처럼 동작**해버린다는 점이 중요한 함정이다 — 즉 겉보기엔 정상 실행되지만 LZCNT가 아니라 BSR 의미로 동작해서 0 입력 시 결과가 undefined가 되어버린다.

### 플래그 변화
- **CF**: 소스가 0이었으면(즉 결과가 오퍼랜드 크기와 같으면) 1로 세팅.
- **ZF**: 결과가 0이면(즉 소스의 최상위 비트가 이미 1이어서 선행 0이 하나도 없으면) 1로 세팅.
- **OF, SF, AF, PF**: 정의되지 않음(undefined).

### signed/unsigned 관점
`LZCNT`는 비트 패턴을 그대로 읽으므로 signed/unsigned 구분이 없다. 다만 이 값을 "숫자 표현에 필요한 비트 수"로 해석할 때는 부호 없는(unsigned) 정수를 대상으로 쓰는 것이 일반적이다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴과 활용
- GCC/Clang: `__builtin_clz(x)`(32비트), `__builtin_clzll(x)`(64비트) — 대상 CPU가 LZCNT를 지원하도록 컴파일 옵션이 설정되어 있으면 `lzcnt`로, 아니면 `bsr` + 보정(`31 - bsr_result`) 코드로 컴파일된다.
- MSVC: `__lzcnt(x)`, `__lzcnt64(x)`
- 활용 예: 부동소수점 정규화(가수의 선행 0 개수만큼 시프트해서 정규화), `log2(x)` 근사(`31 - lzcnt(x)`), 가변 길이 정수 인코딩에서 필요한 바이트 수 계산, 우선순위 큐/스케줄러의 비트마스크 기반 최고 우선순위 탐색.

### IDA/Ghidra 디컴파일에서 보이는 형태
`__lzcnt32(v1)` 또는 `__builtin_clz(v1)` 형태로 정리되어 보이는 경우가 많다. `BSR` 기반 폴백 코드를 함께 본다면 `31 - result` 또는 `xor result, 31` 같은 보정 연산이 뒤따르는 것을 확인해서 "이건 LZCNT를 흉내 내는 BSR 코드구나"라고 알아챌 수 있어야 한다.

### 리버싱 의미
`LZCNT`(또는 이를 대체하는 `BSR` + 보정 패턴)가 보이면 비트 길이 계산, 정규화, 로그 근사 계산 로직임을 의심할 수 있다. 암호학 라이브러리(빅넘버 정규화), 압축 알고리즘, 부동소수점 소프트웨어 에뮬레이션 코드에서 자주 나타난다.

## 화면/코드에서 보이는 징후
- `lzcnt eax, ebx` — EBX의 선행 0 개수를 EAX에 저장
- `lzcnt` 직후 CF 검사 — 소스가 0이었는지 확인하는 분기
- `bsr` 다음에 `xor reg, 31` 또는 `31 - result` 계산 — LZCNT를 지원하지 않는 구형 타겟용 BSR 기반 대체 코드

## 가장 먼저 할 것
1. `lzcnt`의 소스가 어떤 값(정수 크기, 비트마스크, 부동소수점 가수 등)을 나타내는지 문맥 파악.
2. 결과가 이후 시프트량이나 로그 계산에 쓰이는지 확인.
3. `LZCNT`인지 `BSR` 기반 대체 코드인지 구분해서, 0 입력 처리 방식이 다르다는 점을 감안한다.

## 단계별 절차

**1) 비트 길이 계산**
```asm
mov    eax, [x]
lzcnt  eax, eax        ; eax = 선행 0 개수
mov    ecx, 32
sub    ecx, eax          ; ecx = 32 - 선행0개수 = 값을 표현하는 데 필요한 비트 수
```

**2) 0 입력 안전 처리**
```asm
lzcnt  eax, [x]
jc     was_zero          ; CF=1이면 x가 0이었다는 뜻
```

**3) BSR 기반 폴백과의 비교**
```asm
; LZCNT 미지원 CPU용 대체 코드
mov    eax, [x]
test   eax, eax
jz     handle_zero        ; BSR은 0 입력을 직접 처리 못하므로 먼저 검사해야 함
bsr    eax, eax
xor    eax, 31             ; bsr 결과(최상위 1비트 인덱스)를 lzcnt 결과로 변환
```

## 명령어/단축키
- Python으로 재현: `32 - x.bit_length()` (x가 0이 아닐 때, 32비트 기준)

## 출력 해석
- CF=1이면 소스가 0이었고 결과는 오퍼랜드 크기(32 또는 64)다.
- CF=0이면 결과는 `0 ~ (오퍼랜드크기-1)` 범위의 정상적인 선행 0 개수다.

## 흔한 실수
- `LZCNT`와 `BSR`을 완전히 같은 명령어라고 착각하는 것 — 0 입력 처리와 CF 세팅 여부가 다르며, 심지어 미지원 CPU에서는 같은 바이트가 조용히 BSR로 실행되어버리는 함정도 있다.
- CPUID 검사 없이 `lzcnt`가 항상 LZCNT 의미로 실행된다고 가정하는 것 — 지원하지 않는 CPU에서는 BSR 의미로 실행되어 0 입력 시 결과가 undefined가 된다.
- OF/SF/AF/PF 값에 의미를 부여하려는 것 — 이 플래그들은 정의되지 않으므로 신뢰할 수 없다.
- `LZCNT`를 `POPCNT`(REV-0407)나 `TZCNT`(REV-0409)와 혼동하는 것 — 각각 "1비트 개수", "선행 0 개수", "후행 0 개수"로 서로 다르다.

## 막혔을 때 다음 체크
- 결과 값이 이상하게 크거나 작으면 → CF를 확인해서 소스가 0이었는지, 혹은 CPUID 미지원으로 BSR 의미로 실행된 건 아닌지 의심한다.
- `bsr` + `xor 31` 같은 조합을 봤다면 → LZCNT를 대체하는 폴백 코드로 해석하고 이 문서의 LZCNT 의미로 치환해서 읽는다.
- 이 값이 왜 필요한지 모르겠다면 → 바로 다음에 시프트(`shl`/`shr`)나 뺄셈(`32 - result`, `64 - result`)이 있는지 확인해서 정규화/비트 길이 계산 목적인지 파악한다.

## 미니 예제

**예제 1 — 비트 길이 계산**
```c
int bits_needed = 32 - __builtin_clz(x);   // x != 0
```
```asm
mov    eax, [x]
lzcnt  eax, eax
mov    ecx, 32
sub    ecx, eax
```

**예제 2 — 0 입력 안전 처리**
```c
int lz = (x == 0) ? 32 : __builtin_clz(x);
```
```asm
lzcnt  eax, [x]
```
(`LZCNT`는 이미 0 입력에서 32/64를 반환하므로 별도 분기가 필요 없다 — 이 점이 BSR 대비 장점이다.)

**예제 3 — log2 근사**
```c
int log2_approx = 31 - __builtin_clz(x);   // x != 0
```
```asm
mov    eax, [x]
lzcnt  eax, eax
mov    ecx, 31
sub    ecx, eax
```

**예제 4 — 64비트 버전**
```c
int lz64 = __builtin_clzll(x64);
```
```asm
mov    rax, [x64]
lzcnt  rax, rax
```

## 관련 글
- REV-0410 — BSF와 BSR: 비트 스캔 명령
- REV-0407 — POPCNT: 1비트 개수 세기
- REV-0409 — TZCNT: 후행 0 개수 세기
- REV-0086 — CPUID: CPU 정보와 안티VM 단서

## 출처/검증
- LZCNT 명령어 오퍼랜드/플래그 동작(CF/ZF 정의, OF/SF/AF/PF undefined), 0 입력 시 결과가 오퍼랜드 크기: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "LZCNT—Count the Number of Leading Zero Bits" 섹션 기준 (2026-09-08 검증).
- CPUID.80000001H:ECX.LZCNT[bit 5] 지원 검사 및 미지원 시 BSR로 폴백되는 인코딩 동작: 같은 매뉴얼 CPUID 명령어 섹션 및 LZCNT 섹션의 호환성 노트 기준.
