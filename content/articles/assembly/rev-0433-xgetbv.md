---
id: REV-0433
title: "XGETBV: 확장 레지스터 상태 확인 개념"
slug: "rev-0433-xgetbv"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - XGETBV
  - xgetbv 명령어
  - XCR0
  - extended control register
  - OSXSAVE
  - AVX 지원 확인
  - CPU feature detection
  - _xgetbv intrinsic
  - CPU 기능 감지
  - AVX 런타임 디스패치
  - ifunc resolver
aliases:
  - xgetbv가 뭔가요
  - xgetbv 명령
  - xcr0가 뭔가요
  - avx 지원 확인 어셈블리
  - cpu 기능 감지 코드
symptom_keywords:
  - xgetbv가 뭔지 모르겠음
  - cpuid 다음에 xgetbv가 나옴
  - avx 지원 여부 확인 코드
  - 프로그램 시작 부분에 이상한 명령이 있음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`XGETBV`는 오퍼랜드 없이 `ECX`가 지정하는 확장 제어 레지스터(XCR, 보통 `XCR0`)의 값을 `EDX:EAX`로 읽어오는 명령으로, 운영체제가 AVX/AVX-512 같은 확장 SIMD 레지스터 상태를 저장·복원하도록 활성화해 뒀는지 프로그램이 실행 시점에 스스로 확인할 때 쓰인다.

## 언제 검색해야 하나
- `cpuid` 바로 다음이나 그 근처에 `xgetbv`가 나오는, 프로그램 시작 부분의 CPU 기능 감지 코드를 만났을 때
- AVX/AVX-512 명령을 쓰는 함수가 여러 버전(SSE용, AVX용)으로 컴파일되어 있고, 실행 시점에 어느 버전을 쓸지 고르는 "디스패치/리졸버" 코드를 분석할 때
- 이상한 명령 하나 때문에 프로그램이 오래된 에뮬레이터나 특정 가상화 환경에서 `#UD`로 죽는 이유를 추적할 때

## 핵심 개념

### XGETBV가 실제로 하는 일
```
ECX 값으로 지정된 XCR(확장 제어 레지스터)의 64비트 값을 읽어서
EDX:EAX (상위:하위)에 저장한다.
```
실무에서는 거의 항상 `ECX = 0`으로 호출해서 `XCR0`(XFEATURE_ENABLED_MASK) 레지스터를 읽는다. `XCR0`의 각 비트는 특정 확장 레지스터 상태가 OS에 의해 저장/복원되도록 활성화되었는지를 나타낸다.
```
bit 0: x87 FPU 상태 (항상 1)
bit 1: SSE 상태 (XMM 레지스터)
bit 2: AVX 상태 (YMM 레지스터 상위 128비트)
bit 5-7: AVX-512 관련 상태
```

### 오퍼랜드와 문법
```
XGETBV     ; 오퍼랜드 없음. 암묵적으로 ECX(입력), EDX:EAX(출력) 사용
```
소스는 `ECX`(레지스터 인덱스), 목적지는 `EDX:EAX`(결과값) — 둘 다 오퍼랜드 자리에 명시적으로 적히지 않고 정의상 고정되어 있다는 점이 [REV-0429 — CDQ 계열](./rev-0429-cbw-cwd-cdq-cqo.md)과 비슷하다.

### 실행 조건과 예외
이 명령은 아무 때나 실행할 수 있는 게 아니다. 다음이 선행되어야 정상 동작한다.
1. `CPUID`([REV-0086](./rev-0086-cpuid.md))의 `CPUID.1:ECX.OSXSAVE[bit 27]`가 1인지 확인 — OS가 `XSAVE`/`XRSTOR` 메커니즘을 활성화했는지(즉 `CR4.OSXSAVE`가 켜져 있는지)를 알려준다.
2. 이 비트가 0인 상태에서 `XGETBV`를 실행하면 `#UD`(Invalid Opcode) 예외가 발생한다.

즉 프로그램은 반드시 "CPUID로 OSXSAVE 지원 여부 확인 → 지원되면 XGETBV로 XCR0 읽기 → 원하는 비트(AVX=bit1&bit2)가 켜져 있는지 확인" 순서를 지켜야 안전하게 AVX 명령을 쓸 수 있다.

### 플래그/스택/RIP 변화
플래그는 전혀 바뀌지 않는다. 스택에도 영향이 없다. `RIP`는 다음 명령으로 이동한다(예외가 나지 않는 정상 경로 기준).

### 컴파일러/런타임이 만드는 전형적 패턴
- GCC/Clang의 `__builtin_cpu_supports("avx2")`, MSVC의 `_xgetbv` 인트린식을 사용한 런타임 디스패치 코드
- glibc의 IFUNC(인다이렉트 함수) 리졸버: 프로그램 시작 시 한 번 CPU 기능을 검사해서 이후 호출될 최적화된 함수 포인터(SSE용/AVX용/AVX-512용)를 결정
- 벡터화된 라이브러리(수학 라이브러리, 이미지/암호 처리 라이브러리)가 시작 시점에 최적 SIMD 경로를 선택하는 코드

### IDA/Ghidra 디컴파일에서 보이는 모습
`_xgetbv(0)` 인트린식 호출로 정리되어 보이는 경우가 많고, 그 반환값을 `& 6`(bit1과 bit2, 즉 SSE와 AVX 상태) 같은 마스크와 비교하는 코드가 뒤따르는 것이 전형적이다.

### 리버싱에서의 의미
1. **다중 코드 경로 파악**: `CPUID`+`XGETBV` 조합을 시작 지점에서 발견하면, 이 바이너리는 실행되는 CPU에 따라 서로 다른 함수 구현(SSE vs AVX vs AVX-512)으로 분기한다는 뜻이다. 디버깅 중 "왜 예상한 코드로 안 들어가지?"라는 의문이 들면 이 디스패치 로직부터 확인해야 한다.
2. **경량 안티-에뮬레이션/안티-VM 신호**: 일부 오래된 에뮬레이터나 특정 하이퍼바이저는 `XGETBV`를 제대로 가상화하지 못해 값이 이상하게 나오거나 예외를 던졌다. 이런 특성을 이용해 자신이 실제 하드웨어에서 실행되는지 간접적으로 확인하려는 보호 코드에서도(빈도는 낮지만) 관찰될 수 있다.

## 화면/코드에서 보이는 징후
- `mov eax, 1` → `cpuid` → (ECX의 OSXSAVE 비트 검사) → `xor ecx, ecx` → `xgetbv` → `and eax, 6` → `cmp eax, 6` 형태의 연쇄
- 프로그램 진입점(entry point)이나 라이브러리 초기화 함수 근처에서 한 번만 실행되고 그 결과를 전역 변수에 캐시하는 패턴

## 가장 먼저 할 것
1. `xgetbv` 앞에서 `ECX`에 어떤 값이 들어갔는지 확인한다(거의 항상 0, 즉 XCR0 조회).
2. `xgetbv` 직후 `EAX`(하위 32비트)에 대해 어떤 마스크로 `AND`/`CMP`를 하는지 확인해서 어떤 SIMD 확장(SSE/AVX/AVX-512)을 검사하는지 판단한다.

## 단계별 절차
**1) OSXSAVE 확인 → XGETBV → AVX 지원 판정 흐름 추적**
```asm
mov  eax, 1
cpuid
test ecx, 08000000h   ; bit 27 = OSXSAVE
jz   no_avx
xor  ecx, ecx          ; XCR0 조회
xgetbv
and  eax, 6             ; bit1(SSE) | bit2(AVX)
cmp  eax, 6
jne  no_avx
; 여기부터 AVX 코드 경로 사용 가능
```

**2) 디버거로 실제 XCR0 값 확인**
x64dbg/GDB에서 `xgetbv` 실행 직후 EAX/EDX 값을 확인하면 현재 OS/CPU가 어떤 확장 상태를 활성화했는지 직접 알 수 있다.

## 명령어/단축키
- IDA: F5 디컴파일 시 `_xgetbv(0)` 형태의 인트린식 호출로 표시되는지 확인
- x64dbg/GDB: `cpuid`/`xgetbv` 실행 지점에 브레이크포인트를 걸고 F7/stepi로 EAX/ECX/EDX 값을 관찰

## 출력 해석
- `EDX:EAX`의 bit 0 = 1은 항상 참(x87 FPU는 기본 활성화). bit 1 = SSE 활성화 여부. bit 2 = AVX(YMM 상위 128비트) 활성화 여부. `(EAX & 6) == 6`이면 AVX를 안전하게 사용할 수 있다는 뜻이다.

## 흔한 실수
- `XGETBV`를 `CPUID`와 같은 것으로 착각하는 것 — `CPUID`는 "CPU가 그 기능을 물리적으로 지원하는가"를 알려주고, `XGETBV`는 "OS가 그 상태를 저장/복원하도록 실제로 켜뒀는가"를 알려준다. 둘 다 통과해야 안전하게 AVX를 쓸 수 있다.
- `CPUID`로 OSXSAVE를 먼저 확인하지 않고 `XGETBV`가 항상 실행 가능하다고 가정하는 것 — 구형 OS/CPU에서는 `#UD`가 날 수 있다.
- 이 명령을 단순한 안티 디버깅/안티 VM 트릭으로만 보고 CPU 기능 감지라는 본래 목적을 간과하는 것 — 대부분의 경우는 그냥 정상적인 SIMD 최적화 디스패치 코드다.

## 막혔을 때 다음 체크
- `CPUID` 자체의 동작이 궁금하면 → [REV-0086 — CPUID](./rev-0086-cpuid.md)로 이동.
- AVX 관련 SIMD 명령의 실제 동작이 궁금하면 → [REV-0386 — MOVAPS](./rev-0386-movaps.md), [REV-0387 — MOVUPS](./rev-0387-movups.md) 참고.
- 디스패치 코드가 어떤 함수 포인터를 최종적으로 선택하는지 추적하고 싶다면 → `xgetbv` 이후 분기가 최종적으로 어떤 주소로 향하는지 xref를 따라간다.

## 미니 예제
**예제 1 — AVX 지원 여부를 확인하는 전형적 초기화 코드**
```c
bool has_avx() {
    unsigned int a, b, c, d;
    __cpuid(1, &a, &b, &c, &d);
    if (!(c & (1 << 27))) return false;   // OSXSAVE
    unsigned long long xcr0 = _xgetbv(0);
    return (xcr0 & 0x6) == 0x6;            // SSE + AVX
}
```
```asm
mov  eax, 1
cpuid
test ecx, 08000000h
jz   no_avx
xor  ecx, ecx
xgetbv
and  eax, 6
cmp  eax, 6
sete al
ret
no_avx:
xor  eax, eax
ret
```

**예제 2 — 결과를 전역 변수에 캐시하는 초기화 패턴**
```asm
xgetbv
and  eax, 6
mov  [g_avx_supported], eax   ; 매번 다시 검사하지 않도록 캐시
```

## 관련 글
- REV-0086 — CPUID: CPU 정보와 안티VM 단서
- REV-0429 — CBW CWD CDQ CQO: 부호 확장 전용 명령
- REV-0087 — RDTSC: 타이밍 측정과 안티디버깅

## 출처/검증
- `XGETBV`의 정의, `XCR0` 비트 레이아웃, `OSXSAVE` 선행 조건: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "XGETBV—Get Value of Extended Control Register" 및 Volume 1, "13.3 Enabling the XSAVE Feature Set" 섹션 기준 (2026-09-08 검증).
- `CPUID`+`XGETBV` 조합을 이용한 AVX 런타임 감지 관례: Intel "Detection of AVX/AVX2/AVX-512" 공식 애플리케이션 노트 및 GCC `__builtin_cpu_supports` 구현 기준.
