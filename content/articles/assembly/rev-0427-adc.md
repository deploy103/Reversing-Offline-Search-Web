---
id: REV-0427
title: "ADC: 캐리 포함 덧셈"
slug: "rev-0427-adc"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - ADC
  - add with carry
  - 캐리 포함 덧셈
  - 자리올림 덧셈
  - adc 명령어
  - multi-precision addition
  - 다중 정밀도 덧셈
  - bignum addition
  - 128비트 덧셈
  - unsigned __int128
aliases:
  - adc가 뭔가요
  - adc 명령
  - add랑 adc 차이
  - 자리올림 더하기
  - 캐리 더하기 명령어
symptom_keywords:
  - add 다음에 adc가 나옴
  - adc가 뭔지 모르겠음
  - 128비트 덧셈 어셈블리
  - 큰 정수 연산 어셈블리
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`ADC dst, src`는 `dst = dst + src + CF`를 계산하는 명령으로, 이전 덧셈에서 넘어온 자리올림(캐리)까지 더해줘서 레지스터 폭보다 큰 정수를 여러 개의 `ADD`/`ADC` 조합으로 이어붙여 계산할 수 있게 해준다.

## 언제 검색해야 하나
- `add`로 하위 절반을 더하고 바로 다음 줄에 `adc`로 상위 절반을 더하는 코드를 만났을 때
- `unsigned __int128`, bignum 라이브러리(RSA, 큰 수 암호 연산 등)의 어셈블리를 리버싱하면서 자리올림 전파를 추적해야 할 때
- `ADD`와 `ADC`가 뭐가 다른지 헷갈릴 때

## 핵심 개념

### ADC가 실제로 하는 일
`ADC dst, src`는 다음을 계산한다.
```
dst = dst + src + CF
```
일반 `ADD`([REV-0047](./rev-0047-add.md))와 유일한 차이는 **덧셈을 시작하기 전에 현재 CF 값을 더한다**는 점이다. CF가 0이면 `ADC`는 `ADD`와 완전히 동일하게 동작한다.

이게 왜 필요한가: 레지스터 하나(예: 64비트)로 담을 수 없는 큰 수(예: 128비트)를 더하려면, 먼저 하위 64비트를 `ADD`로 더해서 혹시 자리올림이 발생했는지(CF=1) 확인하고, 그다음 상위 64비트를 더할 때 그 자리올림을 반영해야 정확한 결과가 나온다. 이 "자리올림을 다음 자리로 넘기는" 역할을 하는 것이 `ADC`다. 초등학교 세로셈에서 "받아올림"을 다음 자리에 더하는 것과 정확히 같은 개념이다.

### Intel 문법과 오퍼랜드
```
ADC r/m8,  r8         ADC r8,  r/m8
ADC r/m16, r16         ADC r16, r/m16
ADC r/m32, r32         ADC r32, r/m32
ADC r/m64, r64         ADC r64, r/m64
ADC r/m,   imm8/imm16/imm32   ; 즉시값을 더함 (부호 확장)
```
목적지(dst)는 레지스터 또는 메모리, 소스(src)는 레지스터·메모리·즉시값 중 하나다. `ADD`와 마찬가지로 dst와 src가 동시에 둘 다 메모리일 수는 없다.

### 방향
연산 결과는 항상 **첫 번째(목적지) 오퍼랜드에 저장**된다. 두 번째(소스) 오퍼랜드는 변하지 않는다.

### 플래그 변화
`ADC`는 `ADD`와 동일하게 CF, OF, SF, ZF, AF, PF를 전부 결과에 맞춰 갱신한다. 여기서 중요한 점: **입력으로 쓰인 CF와, 연산 후 새로 세팅되는 CF는 다른 값이다.** 즉 `ADC`가 끝나면 "이번 자리에서 새로 자리올림이 발생했는가"를 나타내는 새 CF 값이 남고, 이 새 CF를 다시 그다음 상위 워드의 `ADC`에 넘겨주면서 사슬처럼 연결한다.

### Signed/Unsigned
CF는 unsigned 관점의 자리올림, OF는 signed 관점의 오버플로를 나타낸다는 점은 `ADD`와 동일하다([REV-0088](./rev-0088-flags-overview.md) 참고). 다중 정밀도 연산에서는 대개 CF(자리올림 전파)가 핵심이고, 최상위 워드에서만 최종적으로 OF를 봐서 전체 결과의 signed 오버플로 여부를 판단한다.

### 스택/RSP/RIP 변화
스택에는 영향이 없다. `RIP`는 명령 길이만큼 다음 명령으로 이동할 뿐이다.

### 컴파일러가 만드는 전형적 패턴
`unsigned __int128`(GCC/Clang 확장 타입)이나 자체 bignum 구조체의 덧셈 연산자를 구현할 때, 컴파일러는 항상 다음 순서를 만든다.
```
ADD  (하위 워드끼리)
ADC  (그다음 워드끼리, 낮은 자리에서 넘어온 CF 반영)
ADC  (그다음 워드끼리, ...)
...
```
암호 라이브러리(RSA, ECC 등 큰 수를 다루는 코드)에서 이 패턴이 매우 자주 나오며, `ADD` 하나만 있고 `ADC`가 없다면 32/64비트 범위 안에서 끝나는 일반 정수 연산이라는 뜻이다.

### IDA/Ghidra 디컴파일에서 보이는 모습
디컴파일러가 두 워드짜리 배열을 하나의 논리적인 큰 정수로 인식하면 `unsigned __int128 sum = (unsigned __int128)a + b;`처럼 깔끔하게 합쳐 보여주기도 하지만, 인식하지 못하면 `CARRY`류의 가짜(pseudo) 함수 호출이나 `extraout_EDX` 같은 낯선 변수와 함께 `ADD`/`ADC`가 거의 원문 그대로 남아 있는 경우가 많다. 이런 낯선 표기가 보이면 다중 정밀도 산술을 의심해야 한다.

### 리버싱에서의 의미
`ADC`가 등장한다는 것 자체가 "이 코드가 레지스터 하나로는 표현 못 하는 큰 수를 다루고 있다"는 강력한 신호다. CTF에서는 RSA 직접 구현, 체크섬/해시의 일부 단계, 커스텀 암호화 루틴에서 자주 나타난다.

## 화면/코드에서 보이는 징후
- `add eax, [rsi]` 다음 줄에 `adc edx, [rsi+4]` — 64비트 두 조각을 하나의 논리적 값으로 더함
- 반복문 안에서 `adc`가 여러 번 나오면 임의 정밀도(arbitrary precision) 큰 수 연산
- `adc`만 있고 그 전에 `CLC`(CF를 0으로 클리어)나 `ADD`가 없으면, 이전 CF 값이 무엇이었는지부터 위로 거슬러 확인해야 함

## 가장 먼저 할 것
1. 이 `ADC`가 몇 번째 워드를 더하는 중인지(첫 워드=ADD, 그 이후=ADC 사슬) 위아래 문맥을 확인한다.
2. 최종 결과가 몇 비트짜리 값을 표현하려는 것인지(64비트 두 개=128비트, 네 개=256비트 등) 파악한다.

## 단계별 절차
**1) ADD-ADC 사슬 식별**
```asm
mov  eax, [rdi]
add  eax, [rsi]        ; 하위 32비트 덧셈, CF 세팅
mov  [rbx], eax
mov  eax, [rdi+4]
adc  eax, [rsi+4]       ; 상위 32비트 + 하위에서 넘어온 CF
mov  [rbx+4], eax
```
→ `rdi`와 `rsi`가 가리키는 두 64비트(8바이트) 값을 더해 `rbx`에 저장하는 코드로 해석한다.

**2) 디버거로 CF 전파 확인**
`ADD` 실행 직후 레지스터 창에서 CF 값을 확인하고, 바로 다음 `ADC`를 한 줄 실행(F7/F8)한 뒤 결과 레지스터 값이 그 CF만큼 추가로 반영됐는지 비교한다.

## 명령어/단축키
- IDA/x64dbg: F7/F8로 ADD → ADC를 한 줄씩 실행하며 레지스터 창에서 CF와 목적지 레지스터 값을 비교 관찰
- GDB/Pwndbg: `stepi`로 한 명령씩 실행, `info registers eflags`로 CF 확인

## 출력 해석
- `ADD` 직후 CF=1이면, 이어지는 `ADC`는 결과에 1을 추가로 더한 값이 나온다. CF=0이면 `ADD`와 동일한 결과다.
- `ADC`가 끝난 뒤 CF가 다시 1이 되면, 그 자리올림은 그다음 상위 워드의 `ADC`(있다면)로 또 전달돼야 한다.

## 흔한 실수
- `ADC`를 그냥 `ADD`와 같은 것으로 착각해서 CF 반영을 빠뜨리고 해석하는 것 — 사슬의 중간 어디선가 CF가 1이었다면 결과값 계산이 1만큼 어긋난다.
- `ADC` 사슬 앞에 CF를 초기화하는 코드(`CLC`, 또는 첫 워드용 `ADD`)가 있는지 확인하지 않고 임의의 CF 값을 가정하는 것.
- 다중 워드 연산인 줄 모르고 상위/하위 워드를 서로 다른 독립적인 변수로 착각해서 분석하는 것.

## 막혔을 때 다음 체크
- `ADC` 앞뒤로 몇 개의 워드가 이어지는지 헷갈리면 → 반복문 구조(카운터, 배열 인덱스)를 먼저 확인해서 몇 비트짜리 연산인지 역산한다.
- CF가 어디서 왔는지 모르겠다면 → 바로 위 명령을 순서대로 거슬러 올라가며 CF를 세팅하는 명령(REV-0088 표 참고)을 찾는다.
- 뺄셈 버전이 필요하면 → [REV-0428 — SBB](./rev-0428-sbb.md)로 이동.

## 미니 예제
**예제 1 — 64비트 두 개로 표현된 128비트 덧셈**
```c
typedef unsigned __int128 u128;
u128 add128(u128 a, u128 b) { return a + b; }
```
```asm
mov  rax, rdi          ; a의 하위 64비트 (RDI:RSI 페어로 전달된다고 가정)
add  rax, rdx          ; b의 하위 64비트와 덧셈
mov  rcx, rsi          ; a의 상위 64비트
adc  rcx, r8            ; b의 상위 64비트 + 캐리 전파
; rax:rcx = 결과 (하위:상위)
```

**예제 2 — 32비트 워드 세 개짜리 bignum 배열 덧셈 루프**
```asm
xor  ecx, ecx           ; 인덱스 초기화, CF도 첫 반복 전까지는 미사용
loop_start:
mov  eax, [rsi+rcx*4]
adc  eax, [rdi+rcx*4]   ; 첫 반복은 CF가 이전 명령들 상태에 의존하므로
                        ; 실제 컴파일러는 첫 워드만 ADD로 따로 처리한다
mov  [rbx+rcx*4], eax
inc  ecx
cmp  ecx, 4
jl   loop_start
```

**예제 3 — CF 전파가 최종 자리올림까지 이어지는 경우**
```asm
mov  eax, 0FFFFFFFFh
add  eax, 1              ; 0xFFFFFFFF + 1 = 0x100000000 -> EAX=0, CF=1
mov  ebx, 0
adc  ebx, 0               ; EBX = 0 + 0 + CF(1) = 1  -> 자리올림이 상위 워드로 넘어감
```

## 관련 글
- REV-0047 — ADD: 덧셈과 플래그
- REV-0428 — SBB: 캐리 포함 뺄셈
- REV-0426 — JC와 JNC: 캐리 플래그 기반 분기 별칭
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기
- REV-0418 — CLC STC CMC: 캐리 플래그 직접 조작

## 출처/검증
- `ADC` 연산 정의(`dst = dst + src + CF`)와 Flags Affected: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "ADC—Add with Carry" 섹션 기준 (2026-09-08 검증).
- 다중 정밀도 정수 연산에서의 ADD/ADC 관용구: GCC/Clang `__int128` 확장 및 일반 bignum 구현 관례 기준.
