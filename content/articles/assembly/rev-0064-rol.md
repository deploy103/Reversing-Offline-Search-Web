---
id: REV-0064
title: "ROL: 왼쪽 Rotate"
slug: "rev-0064-rol"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - rol
  - ROL
  - rol 명령어
  - rol instruction
  - rotate left
  - 왼쪽 회전
  - 비트 회전
  - rotate vs shift
  - rol과 shl 차이
  - hash rotate
  - 해시 함수 rotate
  - "rol eax, 1"
  - ror
  - ROR
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - rol 뭐임
  - rol이 뭐죠
  - rol 명령
  - ROL 명령어
  - 롤 명령어
  - rol이 shl과 뭐가 다른지
symptom_keywords:
  - rol이 shl과 뭐가 다른지 모르겠음
  - 비트가 사라지지 않고 반대편에 나타나는 이유
  - 해시 함수에서 rol이 왜 나오는지
last_verified: "2026-09-08"
---

## 한 줄 요약
`ROL`(Rotate Left)은 왼쪽으로 밀려 나가는 비트를 버리지 않고 반대편(최하위)으로 순환시켜 다시 채워 넣는 명령어로, 어떤 비트도 잃지 않는다는 점이 [`SHL`](rev-0061-shl-sal.md)과 다르며 해시 함수와 커스텀 인코딩에서 자주 등장한다.

## 언제 검색해야 하나
- `rol eax, 8` 처럼 시프트 계열 명령어인데 [`SHL`](rev-0061-shl-sal.md)과 결과가 다른 코드를 만났을 때
- 해시 함수(MD5, SHA류, xxHash, 커스텀 체크섬)나 CTF 인코딩 알고리즘 코드에 `rol`/`ror`가 반복적으로 나올 때
- Rotate 명령어가 다른 시프트 명령어와 달리 SF/ZF를 안 건드리는 이유가 궁금할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
ROL dest, count
```
- `dest`는 레지스터 또는 메모리, `count`는 즉시값 또는 `CL` 레지스터.
- `dest`의 모든 비트를 왼쪽으로 `count`번 **순환(회전)** 시킨다. 왼쪽 끝(최상위)에서 밀려 나가는 비트는 사라지지 않고 오른쪽 끝(최하위)으로 다시 들어온다.
- `count`는 32비트에서 `& 0x1F`, 64비트에서 `& 0x3F`로 마스킹.
- 예: `rol eax, 1`, `rol eax, 8`, `rol eax, cl`.

### SHL과의 결정적 차이 — 비트가 사라지지 않는다
```
eax = 1010 0000 0000 0000 0000 0000 0000 0001
```
`shl eax, 1`을 하면:
```
eax = 0100 0000 0000 0000 0000 0000 0000 0010   ; 최상위 비트(1)는 그냥 사라짐, 최하위는 0으로 채워짐
```
`rol eax, 1`을 하면:
```
eax = 0100 0000 0000 0000 0000 0000 0000 0011   ; 최상위 비트(1)가 사라지지 않고 최하위로 돌아옴
```
`SHL`은 밀려 나가는 비트를 버리고 빈 자리를 0으로 채우는 반면, `ROL`은 밀려 나가는 비트를 정확히 반대편에 다시 끼워 넣는다. 그래서 `ROL`은 **정보 손실이 전혀 없는(가역적인)** 연산이다 — `rol eax, n` 뒤에 `ror eax, n`(오른쪽 회전, [REV-0065](rev-0065-ror.md))을 적용하면 정확히 원래 값으로 되돌아온다. 이 가역성이 해시/체크섬/경량 인코딩에서 회전 연산이 애용되는 이유다.

### 플래그 변화 — 시프트 계열과 뚜렷하게 다른 규칙
**`ROL`(그리고 자매 명령어 `ROR`/`RCL`/`RCR`)은 오직 CF와 OF만 건드리고, SF/ZF/PF/AF는 전혀 영향을 받지 않는다.** 이는 `AND`/`OR`/`XOR`/`SHL`/`SHR`/`SAR`이 대부분 SF/ZF/PF를 결과에 맞춰 갱신하는 것과 뚜렷하게 대비되는, Rotate 계열만의 고유한 규칙이다.
- **CF**: 마지막으로 회전되어 나간(그리고 반대편으로 다시 들어간) 비트 값이 그대로 들어감 (즉 결과의 최하위 비트와 같은 값)
- **OF**: `count == 1`일 때만 정의됨 — 결과의 최상위 비트와 CF를 XOR한 값. `count > 1`이면 undefined.
- **SF, ZF, PF, AF**: **영향 받지 않음(unaffected)** — Rotate 이전 값 그대로 유지된다.

이 때문에 `ROL` 앞에 `CMP`나 `TEST`가 있었다면, `ROL` 이후에도 그 플래그(ZF 등)가 살아있어 `ROL`을 건너뛰고 이전 비교 결과로 분기하는 코드가 자연스럽게 성립할 수 있다.

### 신호 있음/없음(signed/unsigned) 관점
Rotate는 값을 순수 비트 패턴으로 다루는 연산이라 signed/unsigned 구분이 의미가 없다. 회전 자체는 "곱하기/나누기" 같은 산술적 의미를 갖지 않으며, 오직 비트의 위치를 순환시킬 뿐이다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러/알고리즘 패턴 — 해시와 난독화의 rotate
`ROL`(그리고 `ROR`)은 일반적인 컴파일러 최적화(곱셈/나눗셈 대체)에서는 거의 등장하지 않는다. 대신 다음 두 상황에서 매우 흔하게 나타난다:
1. **해시/체크섬 알고리즘**: MD5, SHA-1/SHA-2, xxHash, MurmurHash, 그리고 다양한 커스텀 해시 함수들이 "비트를 섞기 위해(bit mixing)" 고정된 양만큼 회전시키는 연산을 핵심 단계로 사용한다. 이런 코드에서 `rol eax, 7`, `rol eax, 13`처럼 특정 상수만큼 회전하는 코드가 루프 안에서 반복되면 해시 알고리즘을 구현 중이라고 강하게 의심할 수 있다.
2. **CTF 커스텀 인코딩/난독화**: `rol`/`ror`은 XOR와 결합되어 "간단하지만 손으로 계산하기 번거로운" 인코딩을 만드는 데 자주 쓰인다. 예: `byte = ROL(byte, 3) ^ key`.

## 화면/코드에서 보이는 징후
- `rol eax, 8` — 바이트 단위로 위치를 순환 (예: `0x11223344` → `0x22334411`, 엔디안 뒤섞기/커스텀 인코딩에 흔함)
- 루프 안에서 반복되는 `rol reg, 상수` — 해시 함수의 믹싱 단계 의심
- `rol`/`ror`이 `xor`과 번갈아 나오는 패턴 — CTF 커스텀 암호화/인코딩 알고리즘
- `rol eax, 1` 직후에도 이전 `cmp`/`test`의 분기가 그대로 유효한 코드 — Rotate가 SF/ZF를 안 건드리는 것을 이용한 코드

## 가장 먼저 할 것
1. 회전량(count)이 고정 상수인지 확인 — 해시 알고리즘은 보통 논문/스펙에 정의된 고정 회전량을 쓴다 (예: MD5는 라운드마다 7, 12, 17, 22 등)
2. 루프 구조와 함께 등장하는지 확인 (단발성 회전은 단순 인코딩, 반복 회전은 해시/믹싱 함수일 가능성)
3. 회전 상수를 검색해서 알려진 해시 알고리즘과 일치하는지 대조

## 단계별 절차

**1) 단순 회전 인식 및 값 계산**
```asm
mov eax, 0abh   ; 1010 1011
rol eax, 1        ; 0101 0111 (최상위 1이 최하위로 순환)
```

**2) 바이트 순서 뒤섞기 인식**
```asm
rol eax, 8   ; 32비트 값을 8비트(1바이트) 단위로 회전 -> 바이트 순서가 한 칸씩 밀림
```

**3) 해시 믹싱 루프 인식**
```asm
hash_loop:
    mov  eax, [state]
    xor  eax, [data+rcx]
    rol  eax, 5          ; 고정 회전량 -> 알려진 해시와 대조해볼 값
    mov  [state], eax
    inc  rcx
    cmp  rcx, len
    jl   hash_loop
```
회전량 `5`나 데이터 처리 순서를 실제 해시 알고리즘 스펙(SDBM, djb2 변형, 커스텀 등)과 비교해본다.

**4) 플래그 미변경을 활용한 코드 인식**
```asm
cmp  eax, ebx
rol  ecx, 3     ; ecx만 회전, cmp가 세팅한 ZF/SF/CF/OF는 유지되지 않음(CF/OF는 rol이 덮어씀)에 주의
jz   still_equal
```
주의: `ROL`도 CF와 OF는 갱신하므로, 이전 `CMP`가 CF/OF 기반 분기(unsigned/signed 비교)를 준비해뒀다면 `ROL` 이후에는 그 값이 깨진다. 반면 SF/ZF는 안전하게 유지된다.

## 명령어/단축키
- Python으로 32비트 회전 재현:
  ```python
  def rol32(x, n):
      n &= 31
      return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF
  ```

## 출력 해석
- IDA/Ghidra는 `rol`/`ror`을 C 표준에 직접 대응하는 연산자가 없어서 `_rotl`/`_rotr`(MSVC 내장 함수) 형태로 표시하거나, `(x << n) | (x >> (32-n))` 형태로 풀어서 보여주는 경우가 많다.
- 반복 회전이 있는 루프를 디컴파일 결과에서 보면, 이미 알려진 해시 함수 시그니처(상수, 회전량 순서)와 비교해 알고리즘을 식별하는 것이 분석의 지름길이다.

## 흔한 실수
- `ROL`을 `SHL`과 같은 결과를 낸다고 착각하는 것 — 밀려 나가는 비트의 운명이 다르다(버려짐 vs 반대편으로 순환).
- Rotate 명령어가 `AND`/`OR`/`XOR`/`SHL`/`SHR`/`SAR`처럼 SF/ZF/PF를 갱신한다고 가정하는 것 — Rotate 계열(`ROL`/`ROR`/`RCL`/`RCR`)은 CF와 OF만 건드린다.
- `rol eax, 8`을 단순 곱셈/나눗셈으로 해석하려는 것 — Rotate는 산술 연산이 아니라 순수 비트 재배열이므로 값의 "크기"와는 무관하다.
- CTF에서 `rol`/`ror`이 나오면 "복잡한 암호화"라고 지레짐작하는 것 — 회전은 대칭적이고(고정 상수만 알면) 항상 역연산(`ROR`↔`ROL`)으로 즉시 되돌릴 수 있는 매우 약한 변환이다.

## 막혔을 때 다음 체크
- 회전량과 결합 방식을 알려진 해시(MD5/SHA/xxHash/MurmurHash/FNV 변형)와 대조해도 안 맞으면 → 커스텀(직접 설계된) 알고리즘일 가능성이 높으니 상수들을 모두 기록해두고 파이썬으로 그대로 재현.
- 회전 방향(왼쪽/오른쪽)이 헷갈리면 → 니모닉 마지막 글자(`L`=Left, `R`=Right)로 구분.
- 회전 후 플래그 기반 분기가 예상과 다르게 동작하면 → CF/OF는 ROL이 덮어쓴다는 점을 감안해서 그 이전 CMP/TEST의 CF/OF 기반 분기(unsigned/signed 비교)가 이미 깨졌을 수 있음을 의심.

## 미니 예제

**예제 1 — 단순 회전**
```c
unsigned int y = (x << 1) | (x >> 31);   // MSVC라면 _rotl(x, 1)
```
```asm
mov eax, [x]
rol eax, 1
```

**예제 2 — 바이트 순환 (엔디안 뒤섞기 인코딩)**
```c
unsigned int y = _rotl(x, 8);
```
```asm
mov eax, [x]
rol eax, 8
```

**예제 3 — 해시 믹싱 루프**
```c
unsigned int h = seed;
for (int i = 0; i < len; i++) {
    h ^= data[i];
    h = (h << 5) | (h >> 27);   // rol h, 5
}
```
```asm
hash_loop:
    movzx eax, byte ptr [rsi+rcx]
    xor   [h], eax
    mov   eax, [h]
    rol   eax, 5
    mov   [h], eax
    inc   rcx
    cmp   rcx, len
    jl    hash_loop
```

**예제 4 — XOR와 결합된 CTF 스타일 인코딩**
```c
byte = (byte << 3 | byte >> 5) ^ 0x2A;   // rol byte, 3 다음 xor
```
```asm
mov  al, [byte]
rol  al, 3
xor  al, 2Ah
```

## 관련 글
- [REV-0061 — SHL과 SAL: 왼쪽 시프트](rev-0061-shl-sal.md)
- [REV-0062 — SHR: 논리 오른쪽 시프트](rev-0062-shr.md)
- [REV-0063 — SAR: 산술 오른쪽 시프트](rev-0063-sar.md)
- [REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화](rev-0057-xor.md)
- [REV-0065 — ROR: 오른쪽 Rotate](rev-0065-ror.md)

## 출처/검증
- ROL 명령어의 오퍼랜드/플래그 동작(CF/OF만 영향, SF/ZF/PF/AF 미변경 포함): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "RCL/RCR/ROL/ROR—Rotate" 섹션 기준 (2026-09-08 검증).
- 해시 함수에서의 회전 연산 사용(MD5/SHA류 비트 믹싱): RFC 1321 (MD5), FIPS 180-4 (SHA) 공식 스펙 기준.
