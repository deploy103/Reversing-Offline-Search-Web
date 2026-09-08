---
id: REV-0409
title: "TZCNT: 후행 0 개수 세기"
slug: "rev-0409-tzcnt"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - tzcnt
  - TZCNT
  - Tzcnt
  - tzcnt 명령어
  - tzcnt instruction
  - trailing zero count
  - 후행 0 개수
  - count trailing zeros
  - ctz
  - __builtin_ctz
  - _tzcnt_u32
  - "tzcnt eax, ebx"
  - "tzcnt rax, rax"
  - BMI1
  - 최하위 1비트 위치
aliases:
  - tzcnt 뭐임
  - tzcnt이 뭐죠
  - tzcnt 명령
  - TZCNT 명령어
  - 후행 0 카운트 명령어
symptom_keywords:
  - 최하위 1비트 위치 찾는 코드
  - 비트마스크 순회하는 루프
  - tzcnt와 bsf 차이
  - x & -x 트릭 관련 코드
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`TZCNT`(Trailing Zero Count)는 오퍼랜드의 최하위 비트(LSB)부터 세어 처음으로 1이 나올 때까지의 연속된 0의 개수를 계산하는 명령어로, `BSF`(REV-0410)와 목적은 같지만 0 입력에 대한 동작이 명확히 정의되어 있다는 점이 다르다.

## 언제 검색해야 하나
- `tzcnt eax, ebx` 명령어가 비트마스크 순회 루프나 "가장 낮은 세팅된 비트 찾기" 코드 근처에 나올 때
- `TZCNT`와 `BSF`(비트 스캔 포워드)의 차이가 궁금할 때
- 메모리 할당기(비트맵 기반 프리 슬롯 탐색), 비트마스크 반복 처리 루프를 분석할 때
- `x & -x`(최하위 세팅 비트만 남기는 트릭)와 함께 등장하는 코드를 볼 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
TZCNT r16, r/m16
TZCNT r32, r/m32
TZCNT r64, r/m64   (REX.W, x64)
```
목적지는 레지스터, 소스는 레지스터 또는 메모리. 소스의 최하위 비트(비트 0)부터 위로 올라가며 처음 1이 나오기 전까지의 0의 개수를 센다.

### 소스가 0일 때 — BSF와의 결정적 차이
소스가 완전히 0이면 `TZCNT`는 **결과를 오퍼랜드 크기(32비트면 32, 64비트면 64)로 명확히 정의**한다. 반면 [BSF](rev-0410-bsf-bsr.md)는 소스가 0일 때 목적지 레지스터 값이 **정의되지 않는다(undefined)** — 반드시 ZF를 먼저 확인해야 안전하다. `TZCNT`는 이 애매함을 없애서 다루기 쉽다.

### CPU 지원 여부와 인코딩 함정
`TZCNT`는 BMI1 확장에 속하며 `CPUID.(EAX=07H,ECX=0):EBX.BMI1[bit 3]`로 지원 여부를 확인한다. 이 명령어는 옛 `BSF`와 **완전히 같은 오피코드(`F3 0F BC`)에 REP 접두사(`F3`)를 붙인 형태**로 인코딩된다 — 즉 BMI1을 지원하지 않는 CPU에서 같은 바이트를 실행하면 `#UD`가 나는 게 아니라 **`F3` 접두사가 그냥 무시되고 옛날 BSF처럼 동작**한다. 겉보기엔 정상 실행되지만 0 입력에 대한 결과가 undefined가 되어버리므로, 이식성이 필요한 코드는 CPUID로 미리 확인해야 한다.

### 플래그 변화
- **CF**: 소스가 0이었으면(결과가 오퍼랜드 크기와 같으면) 1로 세팅.
- **ZF**: 결과가 0이면(즉 소스의 최하위 비트가 이미 1이면) 1로 세팅.
- **OF, SF, AF, PF**: 정의되지 않음.

### signed/unsigned 관점
비트 패턴을 그대로 다루므로 signed/unsigned 구분이 없다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴과 활용
- GCC/Clang: `__builtin_ctz(x)`(32비트), `__builtin_ctzll(x)`(64비트)
- Intel 인트린식: `_tzcnt_u32(x)`, `_tzcnt_u64(x)`
- 활용: 비트마스크를 반복 처리할 때 "다음으로 세팅된 비트의 위치"를 빠르게 찾는 용도로 가장 많이 쓰인다 — `while (mask) { int idx = tzcnt(mask); process(idx); mask &= mask - 1; }` 패턴은 스파스 비트셋, 메모리 할당기의 프리 비트맵 탐색, 그래프 알고리즘(인접 리스트를 비트마스크로 표현) 등에서 매우 흔하다.
- `x & -x`(또는 `x & (~x + 1)`)는 "최하위로 세팅된 비트 하나만 남기는" 고전적인 비트 트릭인데, 그 위치(인덱스)를 구할 때 `TZCNT`나 `BSF`가 뒤따르는 경우가 많다.

### IDA/Ghidra 디컴파일에서 보이는 형태
`_tzcnt_u32(v1)` 또는 `__builtin_ctz(v1)` 형태로 보이는 경우가 많다. 루프 안에서 `tzcnt` 다음에 `and reg, reg-1`(최하위 세팅 비트 제거) 조합이 반복되면 비트마스크 순회 루프임을 바로 알아챌 수 있다.

### 리버싱 의미
`TZCNT`(또는 `BSF` 기반 대체 코드)가 루프 안에서 반복된다면 "비트마스크로 표현된 집합을 하나씩 순회한다"는 뜻이다. 어떤 항목들의 집합(파일 디스크립터, 큐 인덱스, 페이지 프레임 번호 등)을 비트마스크로 관리하는 코드에서 흔히 나타난다.

## 화면/코드에서 보이는 징후
- `tzcnt eax, ebx` — EBX의 후행 0 개수를 EAX에 저장
- `tzcnt` 다음에 CF 검사 — 소스가 0(마스크가 비었음)이었는지 확인
- 루프 안에서 반복되는 `tzcnt` + `and reg, reg-1`(또는 `blsr`) — 비트마스크 순회 패턴
- `neg`/`sub 0, reg` 직후 `and` 조합(`x & -x`) 다음에 이어지는 `tzcnt`/`bsf` — 최하위 세팅 비트의 인덱스 추출

## 가장 먼저 할 것
1. `tzcnt`의 소스가 어떤 집합/플래그를 나타내는 비트마스크인지 문맥으로 파악.
2. 루프 안에 있다면 반복마다 마스크가 어떻게 줄어드는지(`and reg, reg-1` 등) 확인.
3. 결과 인덱스가 배열 접근이나 다른 자료구조의 인덱스로 쓰이는지 추적.

## 단계별 절차

**1) 최하위 세팅 비트 위치 찾기**
```asm
mov   eax, [mask]
tzcnt eax, eax        ; eax = 최하위 1비트의 위치 (마스크가 0이면 32)
```

**2) 0 입력 안전 처리 비교**
```asm
; TZCNT: 별도 분기 없이 바로 사용 가능 (0이면 결과가 32/64로 정의됨)
tzcnt eax, [mask]

; BSF 폴백: 반드시 먼저 0 검사 필요
test  eax, eax
jz    mask_empty
bsf   eax, eax
```

**3) 비트마스크 전체 순회 루프**
```asm
loop_bits:
    tzcnt  eax, [mask]     ; 다음 세팅된 비트 위치
    cmp    eax, 32
    je     loop_done         ; 더 이상 세팅된 비트 없음
    ; ... eax번째 항목 처리 ...
    mov    ecx, [mask]
    lea    edx, [ecx-1]
    and    ecx, edx           ; mask &= mask - 1  (최하위 세팅 비트 제거)
    mov    [mask], ecx
    jmp    loop_bits
loop_done:
```

## 명령어/단축키
- Python으로 재현: `(x & -x).bit_length() - 1` (x != 0 일 때 최하위 세팅 비트의 인덱스)

## 출력 해석
- CF=1이면 마스크가 0(모든 비트가 꺼짐)이었고 결과는 오퍼랜드 크기다.
- CF=0이면 결과는 실제 최하위 세팅 비트의 인덱스(0부터 시작)다.

## 흔한 실수
- `TZCNT`와 `BSF`를 완전히 같은 명령어로 착각하는 것 — 0 입력 처리(정의됨 vs undefined)와 CF 세팅 여부가 다르며, BMI1 미지원 CPU에서는 조용히 BSF로 실행된다.
- 비트마스크 순회 루프에서 `and reg, reg-1`(최하위 비트 제거) 스텝을 놓치고 무한 루프처럼 오해하는 것 — 이 연산 없이는 같은 비트를 계속 찾게 되므로 반드시 짝을 이뤄서 봐야 한다.
- `TZCNT`를 `LZCNT`(REV-0408)와 혼동하는 것 — 하나는 최하위(LSB)에서부터, 다른 하나는 최상위(MSB)에서부터 센다는 방향이 정반대다.

## 막혔을 때 다음 체크
- 루프가 왜 끝나는지 이해가 안 되면 → `and reg, reg-1` 같은 "최하위 세팅 비트 제거" 연산이 마스크를 매번 줄이고 있는지 확인한다.
- 결과가 항상 오퍼랜드 크기(32/64)로 나온다면 → 마스크가 이미 0인 상태에서 루프를 돌고 있는 것이니 루프 종료 조건을 다시 본다.
- `TZCNT`인지 `BSF` 폴백인지 헷갈리면 → CPUID BMI1 검사 코드가 근처에 있는지, 결과 사용 전에 별도의 0 검사 분기가 있는지로 구분한다.

## 미니 예제

**예제 1 — 최하위 세팅 비트 위치**
```c
int idx = __builtin_ctz(mask);   // mask != 0
```
```asm
mov   eax, [mask]
tzcnt eax, eax
```

**예제 2 — 비트마스크 전체 순회**
```c
while (mask) {
    int idx = __builtin_ctz(mask);
    process(idx);
    mask &= mask - 1;
}
```
```asm
loop_bits:
    test   dword ptr [mask], -1
    jz     loop_done
    tzcnt  eax, [mask]
    call   process
    mov    ecx, [mask]
    lea    edx, [ecx-1]
    and    ecx, edx
    mov    [mask], ecx
    jmp    loop_bits
loop_done:
```

**예제 3 — x & -x 트릭과 결합**
```c
int lowest_bit_index = __builtin_ctz(x & -x);
```
```asm
mov   eax, [x]
mov   ecx, eax
neg   ecx
and   eax, ecx
tzcnt eax, eax
```

**예제 4 — 64비트 버전**
```c
int tz64 = __builtin_ctzll(x64);
```
```asm
mov   rax, [x64]
tzcnt rax, rax
```

## 관련 글
- REV-0410 — BSF와 BSR: 비트 스캔 명령
- REV-0408 — LZCNT: 선행 0 개수 세기
- REV-0407 — POPCNT: 1비트 개수 세기
- REV-0055 — AND: 마스크와 비트 제거

## 출처/검증
- TZCNT 명령어 오퍼랜드/플래그 동작(CF/ZF 정의, OF/SF/AF/PF undefined), 0 입력 시 결과가 오퍼랜드 크기, BSF와 동일 인코딩에 REP 접두사를 사용하는 호환성: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "TZCNT—Count the Number of Trailing Zero Bits" 섹션 기준 (2026-09-08 검증).
- CPUID.(EAX=07H,ECX=0):EBX.BMI1[bit 3] 지원 검사: 같은 매뉴얼 CPUID 명령어 섹션 기준.
