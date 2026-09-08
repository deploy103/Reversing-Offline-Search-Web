---
id: REV-0394
title: "PCMPEQB: SIMD 바이트 비교 명령"
slug: "rev-0394-pcmpeqb"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - pcmpeqb
  - PCMPEQB
  - pcmpeqw
  - pcmpeqd
  - pcmpeqb instruction
  - pcmpeqb 명령어
  - pmovmskb
  - simd 바이트 비교
  - packed compare
  - xmm
  - XMM
  - SSE2
  - strlen simd
  - strchr simd
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - pcmpeqb 뭐임
  - pcmpeqb가 뭐죠
  - pcmpeqb 명령
  - PCMPEQB 명령어
  - simd 문자열 비교
  - pmovmskb가 뭔지
symptom_keywords:
  - pcmpeqb가 뭔지 모르겠음
  - strlen이 simd 명령으로 되어있음
  - 문자열 비교 코드에 xmm이 나옴
  - pmovmskb 결과 해석이 안됨
last_verified: "2026-09-08"
---

## 한 줄 요약
`PCMPEQB`는 두 XMM 레지스터의 16개 바이트를 각각 원소별로 비교해, **같으면 해당 바이트를 전부 `0xFF`, 다르면 전부 `0x00`으로 채우는** SIMD 비교 명령으로, `strlen`/`strchr`/`memcmp` 같은 문자열·버퍼 함수의 SIMD 최적화 구현에서 핵심적으로 쓰인다.

## 언제 검색해야 하나
- 문자열 처리 함수(`strlen`, `strchr`, `memchr`, `memcmp` 등)의 내부 구현이 예상과 달리 XMM 레지스터와 `pcmpeqb`를 쓰고 있어서 당황할 때
- `pcmpeqb` 뒤에 `pmovmskb`가 이어져서 그 결과 정수 값을 어떻게 해석해야 할지 모를 때
- SIMD 기반 버퍼 검색/비교 루프를 분석해야 할 때

## 핵심 개념

### Intel 문법과 동작
```
PCMPEQB xmm_dest, xmm/m128_src
```
`dest`와 `src`를 16개의 바이트(8비트) 단위로 나눠 대응 위치끼리 비교한다:
- 두 바이트가 같으면 → 결과의 그 바이트 위치를 **`0xFF`(모든 비트 1)** 로 채움
- 두 바이트가 다르면 → 결과의 그 바이트 위치를 **`0x00`(모든 비트 0)** 으로 채움

즉 결과는 "참/거짓 하나의 값"이 아니라 **16개의 독립적인 참/거짓(0xFF/0x00) 마스크가 나란히 들어있는 128비트 값**이다. `B`(Byte) 대신 `W`(Word, 16비트)/`D`(Doubleword, 32비트)를 쓰는 `PCMPEQW`/`PCMPEQD`도 같은 원리로 원소 크기만 다르다([REV-0393](rev-0393-paddb-paddw-paddd.md)의 B/W/D 규칙과 동일).

### 플래그 변화
EFLAGS를 건드리지 않는다. 비교 결과는 EFLAGS가 아니라 XMM 레지스터 자체(마스크)에 담긴다.

### 결과를 실제로 쓰는 법 — PMOVMSKB
`PCMPEQB`의 128비트 마스크 결과 그 자체는 조건 분기에 바로 쓸 수 없다. 그래서 거의 항상 뒤이어 **`PMOVMSKB reg32, xmm`** 명령이 나온다. 이 명령은 XMM의 16개 바이트 각각의 **최상위 비트(bit 7)** 만 뽑아 32비트 범용 레지스터의 하위 16비트에 모아준다. `PCMPEQB` 결과에서 같았던 바이트는 `0xFF`(최상위 비트 1), 달랐던 바이트는 `0x00`(최상위 비트 0)이므로, `PMOVMSKB` 결과는 **"몇 번째 바이트가 일치했는지"를 나타내는 16비트 비트마스크**가 된다. 이 정수 결과는 이후 `TEST`([REV-0059](rev-0059-test.md))나 `BSF`(최하위 1비트 찾기) 같은 일반 정수 명령으로 넘겨져 "몇 번째 바이트에서 일치가 처음 나왔는가"를 계산하는 데 쓰인다.

### 신호 있음/없음 관점
바이트를 부호 있는/없는 값으로 볼지는 이 명령 자체와 무관하다 — `PCMPEQB`는 순수하게 "비트가 완전히 같은가"만 비교하며 크기 비교(`>`, `<`)는 하지 않는다(크기 비교가 필요하면 `PCMPGTB` 같은 별도 명령이 쓰인다, 본 배치 범위 밖).

### 스택/RSP/RIP 변화
없음.

### 컴파일러/라이브러리 패턴 — strlen의 SIMD 구현
현대 libc(glibc, MSVC CRT 등)의 `strlen` 최적화 구현은 대략 다음 흐름을 따른다:
1. 문자열을 16바이트씩 XMM에 로드(`movdqu`).
2. 미리 0으로 채워둔 XMM(`pxor xmm0, xmm0`, [REV-0392](rev-0392-pxor.md))과 `pcmpeqb`로 비교 — NUL 바이트(`\0`, 값 0)가 있는 위치를 찾는 것.
3. `pmovmskb`로 비트마스크 추출.
4. 마스크가 0이 아니면(즉 이 16바이트 안에 NUL이 있으면) `BSF`로 그 위치를 계산해 문자열 길이 확정, 0이면 다음 16바이트로 이동.

이 패턴을 알아두면, 직접 작성한 것처럼 보이지 않는 낯선 SIMD 루프를 만났을 때 "이건 최적화된 strlen/strchr일 가능성이 높다"고 빠르게 판단할 수 있다.

### IDA/Ghidra 디컴파일
IDA/Ghidra가 시그니처(FLIRT/함수 지문)를 인식하면 `strlen`으로 바로 이름 붙여주지만, 그렇지 못하면 `pcmpeqb`+`pmovmskb`+`bsf` 조합의 루프 그대로 남는 경우가 많다. 이럴 때는 위 4단계 패턴을 알고 있는 것이 함수 이름 없이도 "이건 strlen이다"라고 판단하는 가장 빠른 방법이다.

## 화면/코드에서 보이는 징후
- `pxor xmm0, xmm0` → `movdqu xmm1, [rdi]` → `pcmpeqb xmm1, xmm0` → `pmovmskb eax, xmm1` — NUL 바이트 탐색(strlen/strcpy류)
- `pcmpeqb` 결과를 두 버퍼 비교에 쓰는 경우(`memcmp`/`strcmp` 최적화) — 각 청크가 완전히 같은지 빠르게 검사
- `pmovmskb` 뒤에 `test eax, eax` + `jnz`, 또는 `bsf` — 일치 위치를 찾는 표준 후속 처리

## 가장 먼저 할 것
1. `pcmpeqb`의 두 오퍼랜드가 무엇인지(하나가 `pxor`로 만든 0인지, 특정 문자 상수인지, 다른 버퍼인지) 확인한다.
2. 뒤이어 `pmovmskb`가 있는지 확인해 결과가 정수 비트마스크로 변환되는지 본다.
3. 그 정수 결과가 `test`/`bsf`/`jnz` 등으로 어떻게 쓰이는지 추적해 "무엇을 찾는 루프인지" 판단한다.

## 단계별 절차
**1) NUL 바이트 탐색(strlen류) 인식**
```asm
pxor    xmm0, xmm0        ; 비교 기준값 0
scan_loop:
    movdqu  xmm1, [rdi]
    pcmpeqb xmm1, xmm0     ; 각 바이트가 0인지 비교
    pmovmskb eax, xmm1      ; 16비트 마스크로 추출
    test    eax, eax
    jnz     found_nul       ; 마스크가 0이 아니면 NUL 발견
    add     rdi, 16
    jmp     scan_loop
```
**2) 특정 문자 탐색(strchr류) 인식**: 위와 동일하되 `xmm0`이 0이 아니라 찾으려는 문자를 16번 복제한 값(`pshufb`/`movd`+브로드캐스트로 준비)인 경우.

## 명령어/단축키
- x64dbg/GDB: `pcmpeqb` 실행 후 XMM 레지스터를 바이트(hex) 형식으로 봐서 0xFF/0x00 패턴 확인 (GDB: `p/x $xmm1.uint8`).
- IDA: F5 디컴파일이 이 루프를 알아보지 못하면, 위 패턴과 맞는지 수동으로 대조해 "strlen 최적화 구현"이라 주석을 남겨둔다.

## 출력 해석
- `pmovmskb` 결과가 예를 들어 `0b0000000000010000`(0x10)이면, 이는 16바이트 중 **4번째(0-indexed) 바이트**가 일치했다는 뜻이다(비트 위치 = 바이트 오프셋).
- 마스크가 전부 0이면 이번 16바이트 청크 안에는 찾는 값이 없다는 뜻이므로 다음 청크로 넘어간다.

## 흔한 실수
- `PCMPEQB` 결과 하나(128비트)를 "참/거짓 값 하나"로 착각하는 것 — 실제로는 16개의 독립적인 바이트별 마스크다. 정수 하나로 요약하려면 반드시 `PMOVMSKB` 같은 후속 명령이 필요하다.
- `pcmpeqb`가 크기 비교(`>`, `<`)도 할 수 있다고 착각하는 것 — 오직 "완전히 같은가"만 검사한다.
- 이런 루프를 보고 "직접 짠 문자열 알고리즘"이라 오해하는 것 — 대부분 컴파일러/libc가 제공하는 최적화된 `strlen`/`strchr`/`memcmp` 구현일 뿐이며, 프로그램 고유 로직이 아니다.

## 막혔을 때 다음 체크
- `pmovmskb` 결과 해석이 안 되면 → 결과를 2진수로 펼쳐서 어느 비트가 1인지 바이트 오프셋으로 환산.
- 이 루프가 무슨 라이브러리 함수인지 모르겠다면 → 비교 기준(`pxor`로 만든 0인지 특정 문자인지)을 보고 strlen/strchr 패턴표와 대조.
- IDA가 함수를 인식 못 하면 → FLIRT 시그니처가 없는 최신/커스텀 CRT일 수 있으니 수동으로 이름을 붙여둔다.

## 미니 예제

**예제 1 — strlen의 SIMD 스캔 (개념 단순화)**
```c
size_t my_strlen(const char *s) {
    size_t i = 0;
    while (s[i] != '\0') i++;
    return i;
}
```
```asm
pxor    xmm0, xmm0
scan:
    movdqu  xmm1, [rdi+rcx]
    pcmpeqb xmm1, xmm0
    pmovmskb eax, xmm1
    test    eax, eax
    jnz     found
    add     rcx, 16
    jmp     scan
found:
    bsf     eax, eax        ; 마스크에서 최하위 1비트 위치 = NUL까지의 오프셋
    add     rax, rcx
```

**예제 2 — 두 16바이트 청크가 완전히 같은지 검사 (memcmp류)**
```asm
movdqu  xmm0, [rsi]
movdqu  xmm1, [rdi]
pcmpeqb xmm0, xmm1
pmovmskb eax, xmm0
cmp     eax, 0xFFFF         ; 16비트 전부 1이어야 완전 일치
jne     not_equal
```

## 관련 글
- REV-0393 — PADDB PADDW PADDD: SIMD 정수 덧셈
- REV-0392 — PXOR: XMM 레지스터 초기화와 XOR
- REV-0389 — MOVDQA와 MOVDQU: 정수 XMM 이동
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교

## 출처/검증
- `PCMPEQB`/`PCMPEQW`/`PCMPEQD` 명령어 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "PCMPEQB/PCMPEQW/PCMPEQD—Compare Packed Data for Equal" 섹션 기준 (2026-09-08 검증).
- `PMOVMSKB` 명령어 동작: Intel SDM Volume 2B, "PMOVMSKB—Move Byte Mask" 섹션 기준.
- glibc/최적화 라이브러리의 SIMD 기반 strlen/strchr 구현 패턴: glibc 공식 소스(sysdeps/x86_64) 및 일반 SIMD 문자열 처리 참고자료 기준.
