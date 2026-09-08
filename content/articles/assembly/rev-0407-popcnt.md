---
id: REV-0407
title: "POPCNT: 1비트 개수 세기"
slug: "rev-0407-popcnt"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - popcnt
  - POPCNT
  - Popcnt
  - popcnt 명령어
  - popcnt instruction
  - population count
  - population count 명령어
  - hamming weight
  - 해밍 웨이트
  - 비트 개수 세기
  - 1비트 개수
  - set bit count
  - 세운 비트 수
  - "popcnt eax, ebx"
  - "popcnt rax, rax"
  - SSE4.2
  - __builtin_popcount
  - __popcnt
aliases:
  - popcnt 뭐임
  - popcnt이 뭐죠
  - popcnt 명령
  - POPCNT 명령어
  - 팝카운트 명령어
  - 비트 카운트 명령어
symptom_keywords:
  - 1인 비트 개수 세는 코드
  - 비트마스크에서 켜진 비트 수 세기
  - popcnt가 왜 CPUID 체크 뒤에 나오는지
  - 해밍 거리 계산 코드
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`POPCNT`(Population Count)는 오퍼랜드 안에 몇 개의 비트가 1로 세팅되어 있는지(해밍 웨이트)를 세어 목적지 레지스터에 저장하는 명령어로, SSE4.2를 지원하는 CPU에서만 실행 가능하다.

## 언제 검색해야 하나
- `popcnt eax, ebx` 같은 명령어를 만났는데 산술 연산도 아니고 비교도 아닌 것 같아서 헷갈릴 때
- 비트마스크(권한 플래그, 체스 비트보드, 희소 집합 등)에서 "켜진 비트 개수"를 세는 코드를 분석할 때
- CPUID로 SSE4.2 지원 여부를 확인하는 코드 바로 뒤에 `popcnt`가 나올 때
- 두 값의 해밍 거리(다른 비트 개수)를 계산하는 코드(XOR 뒤에 POPCNT)를 만났을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
POPCNT r16, r/m16
POPCNT r32, r/m32
POPCNT r64, r/m64   (REX.W, x64)
```
목적지는 항상 레지스터이고, 소스는 레지스터 또는 메모리다. 목적지 레지스터에 "소스 안에서 값이 1인 비트의 개수"가 정수로 저장된다.

### CPU 지원 여부 — 반드시 CPUID로 확인해야 하는 이유
`POPCNT`는 SSE4.2 확장 명령어 집합에 속한다. 지원 여부는 `CPUID` 리프 1의 ECX 레지스터 23번 비트(`CPUID.01H:ECX.POPCNT[bit 23]`)로 확인한다. 이 비트가 0인 오래된 CPU에서 `popcnt`를 실행하면 `#UD`(잘못된 명령어) 예외가 발생한다. 그래서 이 명령어를 쓰는 코드는 보통 프로그램 초기화 시점에 [CPUID](rev-0086-cpuid.md)로 지원 여부를 확인한 뒤에만 `popcnt` 경로를 타도록 분기하는 구조를 갖는다.

### 플래그 변화
- **ZF**: 결과에 따라 세팅된다 — 즉 소스에 1인 비트가 하나도 없어서(소스 값이 0이어서) 결과가 0이면 ZF=1.
- **OF, SF, AF, CF, PF**: 항상 0으로 클리어된다.

### signed/unsigned 관점
`POPCNT`는 값을 순수 비트 패턴으로 취급하는 연산이라 signed/unsigned 구분이 없다. 부호 비트도 그냥 "비트 하나"로 세어진다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴
- GCC/Clang: `__builtin_popcount(x)`(32비트), `__builtin_popcountll(x)`(64비트) — 타겟이 SSE4.2를 지원하도록 컴파일 옵션(`-mpopcnt`, `-march=native` 등)이 설정된 경우에만 실제로 `popcnt` 명령어로 컴파일되고, 그렇지 않으면 소프트웨어 비트 카운팅 루프(`AND` + `SHR` 반복, 또는 룩업 테이블)로 대체된다.
- MSVC: `__popcnt(x)`, `__popcnt64(x)` 내장 함수.

### IDA/Ghidra 디컴파일에서 보이는 형태
Hex-Rays는 `popcnt`를 `__popcnt(v1)` 또는 `_mm_popcnt_u32(v1)` 형태로 정리해서 보여주는 경우가 많다. 만약 CPUID 지원 검사 코드와 함께 소프트웨어 폴백 루프(비트를 하나씩 검사하는 루프)가 나란히 존재한다면, 둘 다 "같은 일(비트 개수 세기)을 하는 두 가지 경로"임을 알아채는 것이 중요하다.

### 리버싱 의미
`POPCNT`가 보이면 다음을 의심할 수 있다:
- 비트마스크 기반 자료구조(권한 플래그 집합, 비트보드 게임 로직, 스파스 비트셋)에서 "몇 개가 켜져 있나" 세는 로직
- 해밍 거리 계산(`popcnt(a ^ b)`) — 오류 정정 코드, 유사도 비교, 일부 암호학적 검증 로직
- 성능이 중요한 코드에서 손으로 최적화된 비트 카운팅(일반적인 컴파일러가 자동으로 `popcnt`를 선택하지 않는 한, 프로그래머가 의도적으로 내장 함수를 썼다는 신호)

## 화면/코드에서 보이는 징후
- `popcnt eax, ebx` — 32비트 값의 세운 비트 수를 EAX에 저장
- `popcnt rax, rax` — 64비트, 제자리(in-place) 카운트
- `popcnt` 직전에 `CPUID` 호출과 ECX 비트 23 검사 — 지원 여부 확인 후 분기
- `xor` 직후 `popcnt` — 해밍 거리(두 값이 몇 비트 다른지) 계산 패턴

## 가장 먼저 할 것
1. `popcnt`의 소스 오퍼랜드가 무엇을 나타내는 비트마스크인지(권한, 플래그, 게임판 등) 문맥으로 파악한다.
2. 바로 앞에 `xor`가 있다면 해밍 거리 계산 패턴임을 의심한다.
3. 함수 초반에 CPUID 검사가 있는지 확인해 소프트웨어 폴백 경로가 따로 있는지 본다.

## 단계별 절차

**1) 단순 비트 개수 세기**
```asm
mov    eax, [mask]
popcnt eax, eax        ; eax = mask 안에서 1인 비트의 개수
```

**2) 해밍 거리 계산**
```asm
mov    eax, [a]
xor    eax, [b]         ; 서로 다른 비트만 1로 남김
popcnt eax, eax          ; 다른 비트의 개수 = 해밍 거리
```

**3) CPUID 지원 검사 후 사용**
```asm
mov    eax, 1
cpuid
test   ecx, 800000h      ; bit 23 = POPCNT 지원 여부
jz     use_software_fallback
; ... popcnt 사용 경로 ...
```

**4) 비트보드(체스 등)에서의 활용**
```asm
mov    rax, [bitboard]
popcnt rax, rax           ; 말이 몇 개 있는지 세기
```

## 명령어/단축키
- x64dbg/IDA 디버거: `popcnt` 실행 전 소스 레지스터를 2진수로 펼쳐서 1의 개수를 눈으로 세어보면 결과를 검증할 수 있다.
- Python으로 재현: `bin(x).count('1')` 또는 `x.bit_count()`(Python 3.10+)

## 출력 해석
- `popcnt`의 결과 레지스터 값이 항상 `0 ~ 오퍼랜드 비트 수`(32비트면 0~32, 64비트면 0~64) 범위 안에 있어야 정상이다.
- ZF가 1이면 소스가 0이었다는(즉 세운 비트가 하나도 없었다는) 뜻이다.

## 흔한 실수
- CPUID 지원 확인 없이 `popcnt`가 항상 실행 가능하다고 가정하는 것 — 구형 CPU(SSE4.2 미지원)에서는 `#UD` 예외가 발생한다.
- `POPCNT`를 `LZCNT`/`TZCNT`(REV-0408, REV-0409)와 혼동하는 것 — POPCNT는 "1인 비트의 개수"를, LZCNT/TZCNT는 "특정 방향에서부터의 연속된 0의 개수"를 센다. 셋 다 비슷한 인코딩(`F3` 접두사)을 쓰지만 서로 다른 CPUID 기능 비트로 지원 여부가 결정된다.
- ZF 외의 플래그(CF, SF, OF 등)가 결과에 따라 의미 있게 바뀐다고 착각하는 것 — POPCNT는 ZF만 결과를 반영하고 나머지는 무조건 0이다.

## 막혔을 때 다음 체크
- `popcnt`를 실행하는 코드가 왜 CPUID 검사와 함께 있는지 모르겠다면 → SSE4.2 지원 여부에 따라 두 개의 서로 다른 구현(하드웨어 popcnt vs 소프트웨어 루프)이 존재하는 구조임을 의심한다.
- 결과 값의 의미가 이해 안 되면 → 소스 오퍼랜드가 어떤 비트마스크(파일 권한, 게임판, 집합)를 나타내는지 위쪽 코드에서 먼저 파악한다.
- `xor` 다음에 `popcnt`가 보이면 → 두 값의 차이(해밍 거리)를 구하는 코드라고 해석한다.

## 미니 예제

**예제 1 — 기본 비트 카운트**
```c
int count = __builtin_popcount(mask);
```
```asm
mov    eax, [mask]
popcnt eax, eax
mov    [count], eax
```

**예제 2 — 해밍 거리**
```c
int dist = __builtin_popcount(a ^ b);
```
```asm
mov    eax, [a]
xor    eax, [b]
popcnt eax, eax
mov    [dist], eax
```

**예제 3 — CPUID 검사 후 조건부 사용**
```c
if (cpu_has_popcnt) {
    count = __popcnt(mask);
} else {
    count = software_popcount(mask);
}
```
```asm
test   byte ptr [cpu_has_popcnt], 1
jz     software_path
mov    eax, [mask]
popcnt eax, eax
jmp    done
software_path:
call   software_popcount
done:
```

**예제 4 — 64비트 비트보드 카운트**
```c
int pieces = __builtin_popcountll(bitboard);
```
```asm
mov    rax, [bitboard]
popcnt rax, rax
mov    [pieces], eax
```

## 관련 글
- REV-0408 — LZCNT: 선행 0 개수 세기
- REV-0409 — TZCNT: 후행 0 개수 세기
- REV-0410 — BSF와 BSR: 비트 스캔 명령
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화
- REV-0086 — CPUID: CPU 정보와 안티VM 단서

## 출처/검증
- POPCNT 명령어 오퍼랜드/플래그 동작, CPUID.01H:ECX.POPCNT[bit 23] 지원 검사: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "POPCNT—Return the Count of Number of Bits Set to 1" 섹션 기준 (2026-09-08 검증).
- MSVC/GCC/Clang 내장 함수(`__popcnt`, `__builtin_popcount`): 각 컴파일러 공식 인트린식 문서 기준.
