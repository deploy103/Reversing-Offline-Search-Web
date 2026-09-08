---
id: REV-0410
title: "BSF와 BSR: 비트 스캔 명령"
slug: "rev-0410-bsf-bsr"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - bsf
  - BSF
  - Bsf
  - bsr
  - BSR
  - Bsr
  - bsf 명령어
  - bsr 명령어
  - bit scan forward
  - bit scan reverse
  - 비트 스캔
  - 비트 스캔 포워드
  - 비트 스캔 리버스
  - "bsf eax, ebx"
  - "bsr eax, ebx"
  - __builtin_ffs
  - log2 명령어
aliases:
  - bsf 뭐임
  - bsr 뭐임
  - bsf가 뭐죠
  - bsr이 뭐죠
  - bsf 명령
  - bsr 명령
  - BSF 명령어
  - BSR 명령어
symptom_keywords:
  - bsf bsr 결과가 undefined일 때
  - 비트마스크에서 첫 세팅 비트 위치 찾기
  - log2를 어셈블리로 구현한 코드
  - bsf zf 확인 안 해서 이상한 값 나올 때
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`BSF`(Bit Scan Forward)는 최하위 비트부터 위로 훑어 처음 나오는 1비트의 위치를, `BSR`(Bit Scan Reverse)은 최상위 비트부터 아래로 훑어 처음 나오는 1비트의 위치를 찾는 명령어로, 둘 다 소스가 0이면 결과가 **정의되지 않으므로** 반드시 ZF를 먼저 확인해야 한다.

## 언제 검색해야 하나
- `bsf eax, ebx` 또는 `bsr eax, ebx` 명령어를 만났는데 정확히 어느 방향에서 비트를 세는지 헷갈릴 때
- 비트마스크에서 "가장 낮은/가장 높은 세팅된 비트의 위치"를 찾는 코드를 분석할 때
- `log2(x)` 계산이나 값의 비트 길이를 구하는 오래된(또는 이식성 중시) 코드에서 `bsr`이 쓰인 이유가 궁금할 때
- 결과가 이상하게 튀는 코드를 봤는데 소스가 0이었을 가능성을 의심할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
BSF r16, r/m16
BSF r32, r/m32
BSF r64, r/m64   (REX.W, x64)

BSR r16, r/m16
BSR r32, r/m32
BSR r64, r/m64   (REX.W, x64)
```
목적지는 레지스터, 소스는 레지스터 또는 메모리. 두 명령어 모두 8086 이후로 계속 존재해온 오래된 명령어로, 최신 CPU 확장 없이도 항상 사용 가능하다(이 점이 `TZCNT`/`LZCNT`와 크게 다르다 — 그 둘은 각각 BMI1/ABM 확장이 있어야 실행 가능하다).

### 방향의 차이 — Forward vs Reverse
- **`BSF`**: 비트 0(최하위, LSB)부터 시작해서 위쪽으로 스캔하며 **처음 1이 나오는 비트의 인덱스**를 목적지에 저장한다. "가장 낮은 자리에서 세팅된 비트"를 찾는다.
- **`BSR`**: 비트 31(또는 63, 최상위 MSB)부터 시작해서 아래쪽으로 스캔하며 **처음 1이 나오는 비트의 인덱스**를 목적지에 저장한다. "가장 높은 자리에서 세팅된 비트"를 찾는다.

예: `x = 0b0010_1000` (0x28)이면 `BSF`는 3(비트 3이 최하위 1), `BSR`은 5(비트 5가 최상위 1)를 반환한다.

### 소스가 0일 때 — 반드시 알아야 할 함정
소스 오퍼랜드가 0이면(세팅된 비트가 하나도 없으면), Intel 매뉴얼은 명시적으로 **"목적지 레지스터의 내용은 정의되지 않는다(undefined)"** 라고 규정한다. 대신 이 경우 **ZF(Zero Flag)가 1로 세팅**된다. 그래서 `BSF`/`BSR`을 안전하게 쓰려면 항상 다음 순서를 지켜야 한다:
```asm
bsf   eax, ecx
jz    source_was_zero   ; ZF=1이면 eax 값은 신뢰할 수 없음, 소스가 0이었다는 뜻
; 여기 도달했으면 eax는 유효한 비트 인덱스
```
이 "0 입력 시 undefined" 특성은 [`TZCNT`](rev-0409-tzcnt.md)/[`LZCNT`](rev-0408-lzcnt.md)가 0 입력에 대해 결과를 명확히(오퍼랜드 크기로) 정의하는 것과 뚜렷하게 대비된다. 최신 컴파일러는 대상 CPU가 BMI1/ABM을 지원하면 `TZCNT`/`LZCNT`를 우선 사용하고, 지원하지 않는 구형 타겟에는 `BSF`/`BSR` + 별도의 0 검사 분기 코드를 생성한다.

### 플래그 변화
- **ZF**: 소스가 0이면 1, 아니면 0.
- **CF, OF, SF, AF, PF**: 모두 정의되지 않음(undefined) — `TZCNT`/`LZCNT`가 CF를 명확히 세팅하는 것과 다르다.

### signed/unsigned 관점
비트 위치를 찾는 연산이라 signed/unsigned 구분이 없다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴
- `__builtin_ffs(x)`(find first set, 1부터 시작하는 인덱스 반환)는 내부적으로 `BSF` 결과에 1을 더하고, x가 0인 경우 0을 반환하도록 보정하는 코드로 컴파일되곤 한다.
- `log2` 근사나 비트 길이 계산에서 BMI1/ABM 미지원 타겟용 폴백 코드는 `BSR` 결과를 직접 쓰거나, `BSR` + `xor 31`로 `LZCNT` 결과를 흉내 낸다(REV-0408 참고).
- 최적화 컴파일러(-O2 이상)는 대상 CPU가 확실하면 `BSF`/`BSR`을 아예 `TZCNT`/`LZCNT`로 대체해서 컴파일하기도 한다(정확한 의미 차이는 소스가 0이 아님이 정적으로 증명 가능할 때는 무시해도 되기 때문).

### IDA/Ghidra 디컴파일에서 보이는 형태
`_BitScanForward`/`_BitScanReverse`(MSVC 인트린식 대응) 또는 단순히 인라인된 비트 연산 표현식으로 나타난다. ZF 검사 분기가 함께 있으면 "소스가 0인 경우를 별도로 처리하는 안전한 코드"라고 해석하면 된다.

### 리버싱 의미
`BSF`/`BSR` 다음에 `ZF` 검사가 없다면, 그 코드는 "소스가 절대 0이 아님을 이미 알고 있다"고 가정하고 작성된 것이다 — 이런 가정이 실제로 깨질 수 있는 입력(예: 사용자 입력으로 만들어진 마스크가 우연히 0이 되는 경우)이 있는지 살펴보면 취약점이나 버그를 찾는 단서가 될 수 있다.

## 화면/코드에서 보이는 징후
- `bsf eax, ebx` — 최하위 세팅 비트 위치
- `bsr eax, ebx` — 최상위 세팅 비트 위치
- `bsf`/`bsr` 직후 `jz`/`je` — 소스가 0인 경우를 안전하게 처리하는 패턴
- `bsr` 결과에 `xor ..., 31` 또는 `31 - result` 보정 — LZCNT 흉내(REV-0408 참고)

## 가장 먼저 할 것
1. `BSF`인지 `BSR`인지(방향) 먼저 구분한다.
2. 명령어 직후에 `ZF` 검사 분기(`jz`/`jnz`)가 있는지 확인한다 — 없으면 소스가 0이 아님이 보장된 문맥인지 의심해본다.
3. 결과 인덱스가 이후 시프트, 배열 인덱싱, 로그 계산 중 어디에 쓰이는지 추적한다.

## 단계별 절차

**1) 최하위 세팅 비트 찾기 (안전한 패턴)**
```asm
mov   ecx, [mask]
bsf   eax, ecx
jz    mask_was_zero    ; ZF 확인 필수
; eax = 최하위 세팅 비트 인덱스
```

**2) 최상위 세팅 비트로 비트 길이 계산**
```asm
mov   ecx, [x]
bsr   eax, ecx           ; eax = 최상위 세팅 비트 인덱스 (0-based)
inc   eax                 ; 필요한 비트 수 = 인덱스 + 1
```

**3) BSF/BSR을 안 지켜서 생기는 버그 패턴 인식**
```asm
bsf   eax, [mask]   ; ZF 확인 없이 바로 사용
mov   [result], eax  ; mask가 0이면 eax는 쓰레기 값 -> 버그 가능성
```

## 명령어/단축키
- Python으로 재현: `x.bit_length() - 1`은 BSR과 동일(x != 0), 최하위 비트는 `(x & -x).bit_length() - 1`이 BSF와 동일.

## 출력 해석
- ZF=1이면 목적지 레지스터 값은 신뢰할 수 없다(undefined) — 소스가 0이었다는 뜻으로만 해석해야 한다.
- ZF=0이면 목적지 레지스터에 유효한 비트 인덱스(0부터 시작)가 들어있다.

## 흔한 실수
- `BSF`/`BSR` 실행 후 ZF를 확인하지 않고 목적지 레지스터 값을 곧바로 신뢰하는 것 — 소스가 0인 경우 결과가 undefined임을 놓치는 가장 흔한 실수다.
- `BSF`와 `BSR`의 방향(최하위 vs 최상위)을 헷갈리는 것 — 니모닉의 마지막 글자(`F`=Forward=아래에서 위로, `R`=Reverse=위에서 아래로)로 구분하면 쉽다.
- `BSF`/`BSR`이 `TZCNT`/`LZCNT`처럼 CF를 세팅한다고 착각하는 것 — CF는 이 두 명령어에서 정의되지 않는다.
- `BSR`의 결과를 그대로 "비트 수"라고 착각하는 것 — `BSR`은 0-based 인덱스를 반환하므로, 비트 수(비트 길이)가 필요하면 `+1`을 해줘야 한다.

## 막혔을 때 다음 체크
- 결과 값이 이상하면 → 소스가 0이었을 가능성을 의심하고, ZF 검사가 코드에 있는지 위아래로 살펴본다.
- `BSF`/`BSR`이 왜 여기 있는지 이해가 안 되면 → 최적화 이전의 소스에서 `log2`, `find first/last set bit`, 비트 길이 계산 같은 의도였을 가능성이 높다.
- 최신 CPU 타겟인데 `TZCNT`/`LZCNT` 대신 `BSF`/`BSR`이 쓰였다면 → 컴파일러가 이식성을 우선했거나(구형 CPU 지원), 소스가 0이 아님을 보장할 수 없어 undefined 동작을 감수하지 않으려 한 것일 수 있다.

## 미니 예제

**예제 1 — 최하위 세팅 비트 (안전 처리 포함)**
```c
unsigned long idx;
if (_BitScanForward(&idx, mask)) {
    // idx = 최하위 세팅 비트 위치
}
```
```asm
bsf   eax, [mask]
jz    not_found
mov   [idx], eax
```

**예제 2 — 최상위 세팅 비트로 log2 근사**
```c
int log2_x = 0;
if (x != 0) {
    unsigned long idx;
    _BitScanReverse(&idx, x);
    log2_x = idx;
}
```
```asm
test  eax, eax
jz    is_zero
bsr   eax, eax
mov   [log2_x], eax
```

**예제 3 — ZF 확인을 빠뜨린 버그 있는 코드**
```c
// 버그: mask가 0일 수 있는데 검사가 없음
unsigned long idx;
_BitScanForward(&idx, mask);
use(idx);
```
```asm
bsf  eax, [mask]     ; ZF 확인 없음
mov  [idx], eax        ; mask==0이면 eax는 쓰레기 값
```

**예제 4 — 64비트 버전**
```c
unsigned long idx64;
_BitScanReverse64(&idx64, x64);
```
```asm
bsr  rax, [x64]
```

## 관련 글
- REV-0409 — TZCNT: 후행 0 개수 세기
- REV-0408 — LZCNT: 선행 0 개수 세기
- REV-0407 — POPCNT: 1비트 개수 세기
- REV-0064 — ROL: 왼쪽 Rotate
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- BSF/BSR 명령어 오퍼랜드/플래그 동작(ZF 정의, 소스 0일 때 목적지 undefined, CF/OF/SF/AF/PF undefined): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "BSF—Bit Scan Forward" / "BSR—Bit Scan Reverse" 섹션 기준 (2026-09-08 검증).
- MSVC `_BitScanForward`/`_BitScanReverse` 인트린식 반환값 의미: Microsoft Learn 공식 문서 기준.
