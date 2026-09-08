---
id: REV-0040
title: "MOVZX: Zero Extension 이해"
slug: "rev-0040-movzx"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - movzx
  - MOVZX
  - Movzx
  - movzx instruction
  - movzx 명령어
  - "movzx eax al"
  - "movzx eax, al"
  - "movzx eax, byte ptr"
  - "movzx ecx, word ptr"
  - "movzx rax, al"
  - zero extension
  - 제로 익스텐션
  - 부호 없는 확장
  - unsigned extend
  - 0으로 채우기
  - byte to dword
  - 8비트를 32비트로
aliases:
  - movzx 뭐임
  - movzx가 뭐죠
  - movzx 명령
  - MOVZX 명령어
  - 제로 확장
  - 0 채우기 확장
symptom_keywords:
  - unsigned char를 int로 바꿀 때 어떻게 되는지 모르겠음
  - 상위 비트가 왜 0으로 채워지는지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`MOVZX dst, src`는 작은 크기(8비트/16비트)의 값을 큰 레지스터(16/32/64비트)로 복사하면서, **남는 상위 비트를 전부 0으로 채우는(zero-extend)** 명령어다. `unsigned char`/`unsigned short`를 더 큰 정수로 변환할 때 컴파일러가 생성한다.

## 언제 검색해야 하나
- `movzx eax, byte ptr [rbp-0x1]`처럼 MOV인데 뒤에 `zx`가 붙은 낯선 명령어를 만났을 때
- IDA 디컴파일에서 `unsigned char`, `BYTE`, `unsigned __int8` 같은 타입이 `int`로 바뀌는 자리를 찾고 있을 때
- 부호 없는(unsigned) 작은 타입을 큰 타입으로 캐스팅하는 코드를 어셈블리에서 확인하고 싶을 때

## 핵심 개념

### 왜 그냥 MOV로는 안 되는가
`mov`는 두 오퍼랜드의 **크기가 같아야** 한다. 그런데 `unsigned char c`(1바이트) 값을 `int x`(4바이트)에 대입하는 것처럼 **작은 값을 큰 레지스터로 옮겨야 하는 상황**이 매우 흔하다. 이때 그냥 1바이트만 복사하면 나머지 3바이트가 쓰레기 값으로 남는다. 이를 해결하기 위해 "복사하면서 남는 상위 비트를 확실하게 채워주는" 전용 명령어가 필요한데, 그게 `MOVZX`(부호 없는 값용)와 `MOVSX`/`MOVSXD`(부호 있는 값용)다.

### 동작
```
MOVZX dst, src
```
- src는 8비트(`byte ptr`, `al`류) 또는 16비트(`word ptr`, `ax`류) 크기
- dst는 src보다 큰 레지스터(16/32/64비트)
- src 값을 dst의 하위 비트에 그대로 복사하고, **dst의 나머지 상위 비트는 전부 0**으로 채운다.

```asm
mov  al, 0FFh        ; AL = 0xFF (부호 없는 255, 부호 있는 -1)
movzx eax, al         ; EAX = 0x000000FF  (255) - 상위 비트가 0으로 채워짐
```
값의 "부호"를 신경 쓰지 않고 그냥 있는 비트만 복사하고 나머지는 무조건 0이라서, **부호 없는(unsigned) 값을 확장할 때만 의미상 맞다.** 부호 있는 값(음수)을 MOVZX로 확장하면 원래 음수였던 값이 큰 양수로 바뀌어버리는 오류가 생긴다(이 경우엔 [MOVSX](./rev-0041-movsx-movsxd.md)를 써야 함).

### 오퍼랜드 조합
- `movzx r32, r/m8` — 8비트 → 32비트
- `movzx r32, r/m16` — 16비트 → 32비트
- `movzx r16, r/m8` — 8비트 → 16비트
- x64에서는 `movzx r64, r/m8`, `movzx r64, r/m16`도 존재 (REX 접두사로 목적지를 64비트 레지스터로)

**주의**: `movzx eax, ...`처럼 목적지가 32비트 레지스터면, x64의 "32비트 쓰기는 상위 32비트를 0으로 클리어" 규칙([MOV](./rev-0039-mov.md) 참고)까지 겹쳐서 RAX 전체(64비트)가 깔끔하게 0-확장된다. 그래서 32비트 크기의 값을 64비트로 완전히 zero-extend하고 싶을 때, 사실 그냥 `mov eax, ...`만 해도 결과적으로 RAX 상위가 0이 된다 — 다만 이건 32→64 확장 얘기고, MOVZX 자체는 8/16비트 소스에만 쓰인다는 점을 헷갈리지 말 것.

### 플래그
`MOVZX`는 **플래그를 전혀 바꾸지 않는다** — MOV와 마찬가지다. ZF, CF, SF, OF 등 모두 그대로 유지.

### 컴파일러 패턴 / IDA·Ghidra 표현
소스 C 코드에서 `unsigned char`, `unsigned short`, `BYTE`, `WORD`, `uint8_t`, `uint16_t` 같은 작은 부호 없는 타입을 `int`나 더 큰 타입에 대입/연산할 때 컴파일러가 `movzx`를 생성한다. IDA/Ghidra 디컴파일에서는 보통 `(unsigned int)someByte` 같은 명시적 캐스트나, 그냥 자연스러운 대입문으로 표현되어 MOVZX 자체는 잘 드러나지 않는다 — 대신 원본 타입이 `unsigned char`/`BYTE` 등으로 추론되어 있다면 그 대입이 MOVZX였을 가능성이 높다.

## 화면/코드에서 보이는 징후
- `movzx eax, byte ptr [rbp-0x1]` — 1바이트 지역변수(예: `unsigned char`)를 32비트로 확장해서 읽기
- `movzx ecx, word ptr [rsi]` — 2바이트 값(예: `unsigned short`, 문자열의 wchar_t 한 글자)을 32비트로 확장
- `movzx eax, al` — 이미 레지스터에 있는 1바이트 값을 같은 레지스터의 32비트 형태로 확장(상위 클리어 목적)
- 함수 반환 타입이 `unsigned char`/`bool`인 함수 뒤에 `movzx eax, al`이 따라오는 패턴 — 반환값(AL)을 정수로 안전하게 확장해서 이후 비교에 쓰기 위함

## 가장 먼저 할 것
1. src 오퍼랜드의 원래 크기(byte/word)를 확인한다 — 이게 원본 변수의 실제 타입 크기다.
2. dst 오퍼랜드의 크기를 확인한다 — 이후 코드가 이 값을 어떤 크기로 쓰는지 알 수 있다.
3. "부호 없는 확장"이라는 것을 기억한다 — 원본 값이 음수 의미를 가진 타입이었다면 이 명령어가 나온다는 것 자체가 "이 변수는 unsigned"라는 강력한 힌트다.

## 단계별 절차
**1) 소스 타입 추정**
```asm
movzx eax, byte ptr [rbp-0x1]
```
→ `[rbp-0x1]`은 1바이트 크기의 변수. 이 변수는 unsigned 계열(`unsigned char`, `BYTE`, `uint8_t`, `bool`)일 가능성이 매우 높다.

**2) 확장 후 사용처 확인**
```asm
movzx eax, byte ptr [rbp-0x1]
cmp   eax, 0Ah
jl    label
```
→ 1바이트 값을 0~255 범위의 부호 없는 정수로 취급해서 10과 비교.

**3) MOVSX와 구분해서 판단**
같은 위치에서 `movsx`가 나왔다면 원본 타입은 `char`(부호 있음)였을 가능성이 높다는 뜻이니, 두 명령어를 나란히 비교해서 어떤 게 나왔는지 확인하는 습관을 들인다.

## 명령어/단축키
- IDA: 오퍼랜드 위에서 `Y`(타입 지정)로 변수 타입을 unsigned로 명시하면 이후 디컴파일 결과가 더 명확해짐, `F5`로 디컴파일해서 캐스트 표현 확인
- x64dbg: 레지스터 창에서 실행 전/후 값 비교(상위 바이트가 0으로 깨끗하게 채워지는지 직접 확인 가능)
- GDB/Pwndbg: `stepi`로 한 줄 실행 후 `info registers eax`로 값 확인

## 출력 해석
- `movzx eax, al` 실행 후 EAX가 항상 `0x000000XX` 형태(상위 24비트가 0)면 정상 동작이다.
- 디컴파일 결과에서 `(unsigned int)byteVar` 같은 캐스트가 보이면, 원본 어셈블리는 MOVZX였을 가능성이 크다.

## 흔한 실수
- MOVZX와 [MOVSX](./rev-0041-movsx-movsxd.md)를 헷갈려서, 원래 부호 있는 값(`char`, `short`)인데 상위 비트가 0으로만 채워졌다고 착각하는 것 — 부호 확장이 필요한 값에 MOVZX를 잘못 적용하면 음수가 큰 양수로 둔갑한다.
- "ZX"가 뭘 뜻하는지 몰라서 그냥 `mov`와 동일하다고 생각하는 것 — 크기가 다른 오퍼랜드 간 이동이라는 점, 그리고 명시적으로 0으로 채운다는 점이 핵심이다.
- 8/16비트 → 32/64비트가 아니라 32→64비트 확장도 MOVZX가 담당한다고 착각하는 것 — 32→64는 MOVZX 없이 그냥 `mov eax, ...`만으로 상위가 0이 된다([MOV](./rev-0039-mov.md) 문서의 "상위 32비트 클리어" 참고).

## 막혔을 때 다음 체크
- 확장된 값이 이상하게 크게 보이면 → 원본이 사실 부호 있는 타입이었는데 MOVZX가 잘못 쓰인 게 아니라, 애초에 컴파일러가 정확히 그 타입에 맞춰 생성한 것이니 원본 변수 선언 타입을 다시 확인(리버싱 대상이라면 타입 추정을 unsigned로 바꿔본다).
- MOVSX와 MOVZX가 같은 코드에 섞여 나오면 → 각 변수별로 원본 타입(부호 여부)이 다르다는 뜻이니 개별적으로 판단한다.

## 미니 예제

**예제 1 — unsigned char를 int로 확장**
```c
unsigned char c = 200;
int x = c;
```
```asm
mov   byte ptr [rbp-0x1], 0C8h
movzx eax, byte ptr [rbp-0x1]
mov   [rbp-0x4], eax          ; x = 200 (양수 그대로)
```

**예제 2 — unsigned short 비교**
```c
unsigned short len = get_len();
if (len > 100) { ... }
```
```asm
call  get_len
movzx eax, ax        ; 반환값(AX, 16비트)을 32비트로 zero-extend
cmp   eax, 64h
jle   skip
```

**예제 3 — bool/BYTE 반환값 처리**
```c
BOOL ok = IsValid();
if (ok) { ... }
```
```asm
call  IsValid
movzx eax, al         ; AL(0 또는 1)을 32비트로 확장
test  eax, eax
jz    skip
```

## 관련 글
- [MOV: 값 복사와 레지스터 메모리 이동](./rev-0039-mov.md)
- [MOVSX와 MOVSXD: Sign Extension 이해](./rev-0041-movsx-movsxd.md)
- [LEA: 주소 계산인데 왜 산술 연산처럼 보이는가](./rev-0042-lea.md)

## 출처/검증
- MOVZX 명령어 동작(제로 확장): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "MOVZX—Move with Zero-Extend" 섹션 기준 (2026-09-08 검증).
- x64에서 32비트 레지스터 쓰기가 상위 32비트를 0으로 클리어하는 규칙과의 상호작용: 같은 매뉴얼 Volume 1의 일반 레지스터 규칙 기준.
