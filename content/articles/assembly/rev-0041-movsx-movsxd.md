---
id: REV-0041
title: "MOVSX와 MOVSXD: Sign Extension 이해"
slug: "rev-0041-movsx-movsxd"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - movsx
  - MOVSX
  - Movsx
  - movsxd
  - MOVSXD
  - Movsxd
  - movsx instruction
  - movsxd instruction
  - movsx 명령어
  - movsxd 명령어
  - "movsx eax al"
  - "movsx eax, al"
  - "movsx eax, byte ptr"
  - "movsxd rax, eax"
  - "movsx ecx, word ptr"
  - sign extension
  - 사인 익스텐션
  - 부호 확장
  - signed extend
  - 부호 있는 확장
  - 1로 채우기
  - char to int
  - 8비트를 32비트로 부호확장
aliases:
  - movsx 뭐임
  - movsxd 뭐임
  - movsx가 뭐죠
  - movsx 명령
  - movsxd 명령
  - MOVSX 명령어
  - MOVSXD 명령어
  - 부호 확장 명령어
  - 음수 확장
symptom_keywords:
  - char를 int로 바꿀 때 음수가 이상하게 나옴
  - 음수인데 큰 양수로 보임
  - 부호 확장이 왜 필요한지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`MOVSX`(8/16→16/32/64비트)와 `MOVSXD`(32→64비트)는 작은 크기의 **부호 있는(signed)** 값을 큰 레지스터로 복사하면서, 남는 상위 비트를 원래 값의 **부호 비트(최상위 비트)로 채우는(sign-extend)** 명령어다. `signed char`/`short`/`int`를 더 큰 정수로 변환할 때 컴파일러가 생성한다.

## 언제 검색해야 하나
- `movsx eax, byte ptr [rbp-0x1]`이나 `movsxd rax, eax` 같은 낯선 명령어를 만났을 때
- `char`, `short`, `signed int` 같은 부호 있는 작은 타입을 큰 타입으로 바꾸는 코드가 어셈블리에서 어떻게 보이는지 알고 싶을 때
- 음수 값을 다루는 코드인데 [MOVZX](./rev-0040-movzx.md)로 착각하고 있지는 않은지 확인하고 싶을 때
- 배열 인덱스로 32비트 값을 쓰다가 `movsxd rax, ecx` 같은 코드를 만났을 때(포인터 연산을 위한 64비트 확장)

## 핵심 개념

### 왜 "부호"를 신경 써야 하는가
2의 보수(two's complement) 표현에서 음수는 최상위 비트가 1이다. 예를 들어 1바이트 `char`로 -1은 `0xFF`다. 이 값을 그냥 상위 비트를 0으로 채워서(MOVZX 방식) 32비트로 확장하면 `0x000000FF` = 255가 되어버려서, **원래 -1이라는 의미가 완전히 사라진다.** 부호를 보존하려면 상위 비트를 원본의 부호 비트(1)로 채워야 한다: `0xFFFFFFFF` = -1(부호 있는 32비트로 해석 시). 이걸 해주는 게 MOVSX/MOVSXD다.

### MOVSX (8/16비트 소스)
```
MOVSX dst, src
```
- src: 8비트(`byte ptr`) 또는 16비트(`word ptr`)
- dst: src보다 큰 레지스터(16/32/64비트)
- src의 최상위 비트(부호 비트)를 읽어서, 그 비트 값으로 dst의 남는 상위 비트를 전부 채운다.

```asm
mov   al, 0FFh        ; AL = 0xFF (부호 있는 1바이트로 보면 -1)
movsx eax, al          ; EAX = 0xFFFFFFFF (부호 있는 32비트로 보면 여전히 -1)
```
같은 `0xFF`라도 [MOVZX](./rev-0040-movzx.md)를 쓰면 255, MOVSX를 쓰면 -1이 된다 — **원본 값의 "의미"(부호 있는 타입이었는가)를 아는 것이 결정적으로 중요하다.**

### MOVSXD (32비트 → 64비트, x64 전용)
32비트에서 64비트로의 부호 확장은 별도 mnemonic인 `MOVSXD`를 쓴다(MOVSX가 아님 — 인코딩이 다르다).
```asm
mov    ecx, dword ptr [rbp-0x4]  ; ecx = int i (32비트, 부호 있음)
movsxd rax, ecx                    ; rax = (int64_t)i, 부호 확장
lea    rdx, [rbx+rax*4]            ; 배열 인덱싱: arr[i], i가 음수면 앞쪽 메모리 접근
```
이 패턴은 **`int` 타입 인덱스로 배열에 접근할 때** 매우 흔하다. x64에서 포인터 연산은 64비트로 이루어지므로, 32비트 `int i`를 배열 인덱스로 쓰려면 먼저 64비트로 부호 확장해야 하기 때문이다. 만약 `i`가 `unsigned int`였다면 컴파일러는 대신 그냥 `mov ecx, ...`(32비트 쓰기로 상위가 자동 0이 되므로 MOVZX와 동일한 효과)를 쓴다 — 그래서 **MOVSXD가 보인다는 것 자체가 그 인덱스 변수는 signed int라는 강한 힌트**다.

### 오퍼랜드 조합 정리
- `movsx r16, r/m8`
- `movsx r32, r/m8`
- `movsx r32, r/m16`
- `movsx r64, r/m8` (x64, REX 필요)
- `movsx r64, r/m16` (x64, REX 필요)
- `movsxd r64, r/m32` (x64 전용, 32→64비트 부호 확장)

### 플래그
MOVSX/MOVSXD 모두 **플래그를 전혀 바꾸지 않는다.**

## 화면/코드에서 보이는 징후
- `movsx eax, byte ptr [rbp-0x1]` — `char`/`signed char` 지역변수를 32비트로 부호 확장
- `movsx ecx, word ptr [rsi]` — `short`를 32비트로 부호 확장
- `movsxd rax, eax` 또는 `movsxd rax, dword ptr [rbp-0x4]` — `int`를 64비트로 부호 확장, 대개 배열 인덱싱/포인터 연산 직전에 등장
- 함수가 `char` 또는 `int8_t`/`int16_t`를 반환하고 그 값을 정수 연산에 쓰기 직전에 `movsx eax, al` 형태로 나타남

## 가장 먼저 할 것
1. src의 원래 크기를 확인한다.
2. **MOVZX인지 MOVSX/MOVSXD인지부터 정확히 구분한다** — 이게 원본 변수가 unsigned였는지 signed였는지 알려주는 직접적인 단서다.
3. MOVSXD가 보이면 "이 32비트 값이 배열 인덱스나 포인터 연산에 쓰이겠구나"라고 예상하고 다음 줄(대개 `lea` 또는 `add`)을 확인한다.

## 단계별 절차
**1) 부호 확인**
```asm
movsx eax, byte ptr [rbp-0x1]
```
→ 이 1바이트 변수는 `char`/`signed char` 계열. 값이 0x80~0xFF 범위면 음수로 해석된다.

**2) 확장 결과를 이후 코드에서 추적**
```asm
movsx eax, byte ptr [rbp-0x1]
cmp   eax, 0
jl    is_negative
```
→ 부호 확장된 값을 0과 비교해서 음수 여부 판단.

**3) MOVSXD + 배열 인덱싱 패턴**
```asm
mov    eax, dword ptr [rbp-0x8]   ; eax = idx (int)
movsxd rcx, eax                    ; 64비트로 부호 확장
mov    edx, dword ptr [rbx+rcx*4] ; arr[idx]
```
→ `idx`가 음수면 `rbx` 기준으로 배열 앞쪽(더 낮은 주소)을 가리키게 된다 — 배열 밖 접근(음수 인덱스) 취약점을 찾을 때 이 패턴을 눈여겨봐야 한다.

## 명령어/단축키
- IDA: 변수 위에서 `Y`로 타입을 `signed char`/`int` 등으로 지정해 디컴파일 결과를 정확하게 만들기, `F5`로 캐스트 표현 확인
- x64dbg: 레지스터 창에서 실행 전/후 값 비교(상위 비트가 0xFF...로 채워지는지 0x00...으로 채워지는지가 MOVSX/MOVZX 판별 포인트)
- GDB/Pwndbg: `stepi` 후 `p/x $eax`로 16진수 값 확인, 최상위 니블이 F로 도배되면 음수로 부호 확장된 것

## 출력 해석
- `movsx eax, al`에서 AL이 `0x80` 이상(최상위 비트 1)이었다면, 실행 후 EAX는 `0xFFFFFF80`처럼 상위가 전부 F로 채워진다 — 이게 정상적인 부호 확장 결과다.
- 반대로 AL이 `0x7F` 이하(최상위 비트 0)였다면 EAX 상위는 전부 0이 된다 — 이 경우 MOVSX와 MOVZX 결과가 우연히 같아 보이니, 굳이 구분하려면 값이 0x80 이상인 케이스로 테스트해야 차이가 드러난다.

## 흔한 실수
- MOVSX와 [MOVZX](./rev-0040-movzx.md)를 혼동해서, 부호 있는 값을 다루는데 상위 비트가 0으로 채워질 거라 착각하는 것.
- MOVSXD를 MOVSX의 오타나 변형 정도로 여기고 32→64비트 전용 명령어라는 걸 모르는 것 — 인코딩이 실제로 다른 별개의 명령어다.
- MOVSXD가 나온 걸 보고도 "이 인덱스가 음수일 수 있다"는 가능성을 놓치는 것 — signed 인덱스는 음수 인덱스 버그/취약점의 단서가 될 수 있다.
- 부호 확장된 값을 다시 unsigned 비교(`ja`, `jb` 등)로 처리해서 결과를 오판하는 것 — 부호 확장 이후에는 그 값이 signed 비교(`jg`, `jl` 등)로 해석되어야 의미가 맞다.

## 막혔을 때 다음 체크
- 확장된 값이 예상보다 훨씬 크거나 음수로 보이면 → MOVZX와 MOVSX 중 어느 게 실제로 쓰였는지 명령어 철자를 다시 확인한다.
- MOVSXD 다음에 이어지는 산술이 이해 안 되면 → 대개 `lea reg, [base+idx*scale]` 형태의 배열/포인터 연산이니 그 관점에서 재해석한다([LEA](./rev-0042-lea.md) 참고).

## 미니 예제

**예제 1 — signed char의 부호 확장**
```c
signed char c = -1;
int x = c;
```
```asm
mov   byte ptr [rbp-0x1], 0FFh
movsx eax, byte ptr [rbp-0x1]
mov   [rbp-0x4], eax          ; x = -1 (0xFFFFFFFF, 부호 유지)
```

**예제 2 — short를 int로 부호 확장 후 비교**
```c
short delta = get_delta();
if (delta < 0) { ... }
```
```asm
call  get_delta
movsx eax, ax
test  eax, eax
jns   skip                     ; SF=0이면(양수/0) 분기 스킵
```

**예제 3 — int 인덱스의 64비트 부호 확장(배열 접근)**
```c
int idx = compute_index();
int val = arr[idx];
```
```asm
call    compute_index
movsxd  rax, eax
mov     ecx, dword ptr [rbx+rax*4]  ; val = arr[idx]
```

## 관련 글
- [MOVZX: Zero Extension 이해](./rev-0040-movzx.md)
- [MOV: 값 복사와 레지스터 메모리 이동](./rev-0039-mov.md)
- [LEA: 주소 계산인데 왜 산술 연산처럼 보이는가](./rev-0042-lea.md)

## 출처/검증
- MOVSX 명령어 동작(부호 확장): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "MOVSX—Move with Sign-Extension" 섹션 기준 (2026-09-08 검증).
- MOVSXD 명령어(32→64비트 전용): 같은 매뉴얼, "MOVSXD—Move with Sign-Extension" 섹션 기준.
