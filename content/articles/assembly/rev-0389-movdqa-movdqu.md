---
id: REV-0389
title: "MOVDQA와 MOVDQU: 정수 XMM 이동"
slug: "rev-0389-movdqa-movdqu"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - movdqa
  - MOVDQA
  - movdqu
  - MOVDQU
  - movdqa instruction
  - movdqu instruction
  - movdqa 명령어
  - movdqu 명령어
  - packed integer
  - double quadword
  - xmm
  - XMM
  - SSE2
  - "movdqa xmm0"
  - "movdqu xmm0"
  - memset simd
  - memcpy simd
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - movdqa 뭐임
  - movdqu 뭐임
  - movdqa movdqu 차이
  - movaps movdqa 차이
  - 정수 xmm 이동
symptom_keywords:
  - movdqa랑 movaps 차이를 모르겠음
  - memset이 movdqa로 되어있음
  - dq 접미사가 뭔지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`MOVDQA`/`MOVDQU`는 128비트 XMM 레지스터를 **"정수/바이트 뭉치(packed integer)"** 로 취급해 이동하는 명령으로, 부동소수점 의미를 부여하지 않는다는 점만 빼면 각각 [MOVAPS](rev-0386-movaps.md)(정렬, 예외 발생)/[MOVUPS](rev-0387-movups.md)(비정렬)와 동일한 역할을 한다.

## 언제 검색해야 하나
- `memset`/`memcpy`처럼 정수/바이트 데이터를 다루는 코드가 `movdqa`/`movdqu`로 컴파일된 것을 볼 때
- 함수 시작부에서 `pxor xmm0, xmm0` 다음 `movdqu [buf], xmm0`가 반복되어 "이게 뭘 초기화하는 코드인지" 알고 싶을 때
- 문자열/버퍼 비교, 해시 계산 같은 정수 SIMD 코드를 분석할 때

## 핵심 개념

### DQ = Double Quadword, 정수 데이터를 위한 이동
`DQ`는 **Double Quadword**(64비트 quadword 2개 = 128비트)의 약자로, 이 명령이 부동소수점이 아니라 **정수/바이트열**을 128비트 단위로 다룬다는 뜻이다. `MOVAPS`/`MOVUPS`가 float 데이터를 위한 이동이라면, `MOVDQA`/`MOVDQU`는 정수/바이트 데이터를 위한 이동이다. 비트를 그대로 복사한다는 점에서는 셋 다 동일하지만, **명령어 선택 자체가 컴파일러/사람에게 "이 데이터를 실수로 볼지 정수로 볼지"에 대한 의도를 알려준다**는 점이 리버싱에서 유용하다.

### Intel 문법과 정렬 규칙
```
MOVDQA xmm_dest, xmm/m128_src   ; 16바이트 정렬 필수, 안 맞으면 #GP
MOVDQU xmm_dest, xmm/m128_src   ; 정렬 불필요
```
`A`(Aligned)/`U`(Unaligned) 접미사 규칙은 `PS`/`PD` 계열과 완전히 동일하다: `MOVDQA`는 정렬이 안 맞으면 예외가 나고, `MOVDQU`는 항상 동작한다.

### 플래그, 스택/RSP/RIP 변화
EFLAGS를 건드리지 않는다. 스택/RIP에 직접 영향 없음.

### 컴파일러 패턴 — memset/memcpy의 SIMD 전개
정수/바이트 버퍼를 다루는 표준 라이브러리 함수의 컴파일러 인라인 전개에서 가장 흔하게 나타난다:
- **`memset(buf, 0, n)`**: 먼저 `pxor xmm0, xmm0`(또는 `PCMPEQD` 자기 자신으로 전부 1을 만든 뒤 필요시 변형)로 XMM 레지스터를 원하는 값(대개 0)으로 채운 뒤, `movdqu [buf+offset], xmm0`을 반복해 16바이트씩 채운다.
- **`memcpy(dst, src, n)`**: `movdqu xmm0, [src+offset]` → `movdqu [dst+offset], xmm0` 반복.
- 버퍼가 지역 배열(스택, 컴파일러가 정렬을 보장)이면 `movdqa`, 함수 인자로 받은 임의 포인터면 `movdqu`가 선택되는 경향은 `MOVAPS`/`MOVUPS`와 동일하다.

### IDA/Ghidra 디컴파일
대부분 `memset`/`memcpy` 호출로 인식되거나(컴파일러 관용구 인식 기능이 있는 경우), 그렇지 않으면 배열 대입/루프 형태로 그대로 남는다. Ghidra는 종종 `undefined1 auStack_XX [16]` 같은 16바이트 임시 배열에 대한 대입으로 보여준다.

### MOVDQA/MOVDQU와 MOVAPS/MOVUPS를 같은 자리에 써도 되는가
CPU 입장에서 `MOVDQA`와 `MOVAPS`는 옮기는 128비트 데이터 자체는 동일하게 취급하며(둘 다 정렬 필수, 예외 조건도 동일), 실행 성능도 사실상 같다. 다만 명령어 인코딩이 다르기 때문에 디스어셈블리 상에서는 구분되어 보인다. 과거 일부 CPU 마이크로아키텍처에서는 정수 파이프라인(`MOVDQA`)과 부동소수점 파이프라인(`MOVAPS`) 간 전환에 약간의 지연(domain-crossing penalty)이 있었으나, 최신 CPU에서는 이 차이가 거의 사라졌다. 리버싱 관점에서 중요한 것은 성능이 아니라 **컴파일러가 이 데이터를 정수/바이트로 보고 있는지, 실수로 보고 있는지에 대한 힌트**로 접미사를 활용하는 것이다.

### 부분 초기화와 나머지 바이트 처리
`memset`/`memcpy`가 16의 배수가 아닌 크기를 다룰 때는, SIMD 루프로 큰 덩어리를 처리한 뒤 마지막에 `mov`(1/2/4/8바이트)로 나머지를 스칼라 처리하는 "테일(tail) 코드"가 이어지는 경우가 매우 흔하다. `movdqu` 반복 다음에 짧은 `mov byte ptr`/`mov word ptr` 몇 줄이 더 있다면, 이는 정확한 나머지 바이트를 처리하는 정상적인 마무리 코드이지 별개의 로직이 아니다.

## 화면/코드에서 보이는 징후
- `pxor xmm0, xmm0` 직후 여러 줄의 `movdqu [rdi+N], xmm0` — 버퍼를 0으로 채우는 memset 패턴
- `movdqu xmm0, [rsi+N]` / `movdqu [rdi+N], xmm0` 쌍의 반복 — memcpy 패턴
- 문자열 비교/검색 함수 내부에서 `movdqu` 뒤에 `pcmpeqb`가 이어지는 코드 — SIMD 문자열 스캔 (`strlen`/`strchr` 최적화 구현)

## 가장 먼저 할 것
1. 이동 직전/직후에 `pxor`(제로화) 또는 다른 상수 설정이 있는지 확인해 memset류인지 판단한다.
2. 두 개의 서로 다른 메모리 오퍼랜드 사이를 오가면 memcpy류로 판단한다.
3. `A`/`U` 접미사로 정렬 가정 여부를 확인한다.

## 단계별 절차
**1) memset(0) 패턴 인식**
```asm
pxor    xmm0, xmm0
movdqu  [rdi], xmm0
movdqu  [rdi+16], xmm0
movdqu  [rdi+32], xmm0
```
→ `memset(rdi, 0, 48)`과 동일한 효과.

**2) memcpy 패턴 인식**
```asm
movdqu xmm0, [rsi]
movdqu [rdi], xmm0
```
→ 16바이트 복사, 반복되면 더 큰 버퍼 복사.

**3) 정렬 버전과 비정렬 버전 구분**
지역 배열(스택, 보통 16바이트 정렬)에는 `movdqa`, 함수 파라미터로 받은 포인터에는 `movdqu`가 쓰이는지 확인해서 컴파일러가 정렬을 어떻게 판단했는지 역으로 추론한다.

## 명령어/단축키
- x64dbg/GDB에서 XMM 값을 16진수(정수 뭉치)로 보려면 표시 형식을 "hex bytes"로 지정 (GDB: `p/x $xmm0.uint8`).
- IDA: `movdqu`/`movdqa` 반복이 memset/memcpy로 자동 인식되지 않으면, 반복 오프셋 패턴을 보고 수동으로 크기를 계산한다.

## 출력 해석
- 반복 횟수 × 16바이트로 총 복사/초기화 크기를 계산할 수 있다(마지막에 나머지 바이트를 처리하는 스칼라 `mov`가 덧붙는 경우도 흔하다).
- Ghidra의 `undefined1[16]` 타입으로 나오는 로컬 변수는 사실상 XMM 레지스터 크기(128비트)의 스크래치 공간임을 뜻한다.

## 흔한 실수
- `movdqa`/`movdqu`를 보고 "정수 암호화/해시 알고리즘"이라 단정하는 것 — 대부분은 memset/memcpy의 SIMD 전개일 뿐이다. `pxor`로 0을 채우고 반복 저장하는 패턴이면 거의 확실히 memset이다.
- `DQ`(Double Quadword, 128비트 정수 이동)를 `DWORD`(32비트)와 혼동하는 것 — 이름이 비슷해 보이지만 전혀 다른 크기다.
- `MOVDQA`를 아무 포인터에나 써도 된다고 가정하고 패치하는 것 — 정렬이 안 맞으면 여전히 #GP 예외가 난다.

## 막혔을 때 다음 체크
- 반복되는 `movdqu` 블록이 무슨 함수인지 모르겠다면 → 직전에 `pxor xmm0, xmm0`가 있는지(memset) 또는 서로 다른 두 포인터 사이 이동인지(memcpy) 확인.
- 정렬 크래시가 의심되면 → [REV-0386](rev-0386-movaps.md)과 동일하게 주소 정렬 여부를 계산.

## 미니 예제

**예제 1 — memset(buf, 0, 32) 전개**
```c
memset(buf, 0, 32);
```
```asm
pxor   xmm0, xmm0
movdqu [rdi], xmm0
movdqu [rdi+16], xmm0
```

**예제 2 — memcpy 전개**
```c
memcpy(dst, src, 16);
```
```asm
movdqu xmm0, [rsi]
movdqu [rdi], xmm0
```

**예제 3 — 정렬된 지역 버퍼 초기화**
```asm
sub    rsp, 0x20
pxor   xmm0, xmm0
movdqa [rsp], xmm0    ; 스택은 정렬 보장 -> movdqa 사용
```

**예제 4 — SIMD 문자열 스캔의 일부**
```asm
movdqu  xmm1, [rdi]
pcmpeqb xmm1, xmm0     ; 각 바이트를 0과 비교 (문자열 끝 탐색)
```

## 관련 글
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0387 — MOVUPS: 비정렬 XMM 레지스터 이동
- REV-0392 — PXOR: XMM 레지스터 초기화와 XOR
- REV-0394 — PCMPEQB: SIMD 바이트 비교 명령

## 출처/검증
- `MOVDQA`/`MOVDQU` 명령어 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A/2B, "MOVDQA—Move Aligned Double Quadword" / "MOVDQU" 섹션 기준 (2026-09-08 검증).
- memset/memcpy의 SIMD 자동 벡터화 및 정렬에 따른 명령 선택: Agner Fog, "Optimizing subroutines in assembly language" 기준.
