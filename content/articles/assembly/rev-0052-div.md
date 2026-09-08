---
id: REV-0052
title: "DIV: Unsigned 나눗셈"
slug: "rev-0052-div"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - div
  - DIV
  - Div
  - div 명령어
  - div instruction
  - "div ecx"
  - "div rcx"
  - "div eax"
  - "div ebx"
  - "div dword ptr"
  - "div qword ptr"
  - unsigned division
  - unsigned 나눗셈
  - 부호없는 나눗셈
  - EDX:EAX
  - edx eax
  - RDX:RAX
  - rdx rax
  - "xor edx, edx"
  - xor edx edx
  - divide error
  - "#DE"
  - DE 예외
  - 0으로 나누기
  - divide by zero
  - integer divide by zero
  - SIGFPE
  - STATUS_INTEGER_DIVIDE_BY_ZERO
  - 나눗셈 오류
  - 나눗셈 결과 이상
  - 몫과 나머지
  - quotient remainder
  - 몫 나머지
  - AH AL 나눗셈
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - div 뭐임
  - div가 뭐죠
  - div 명령
  - DIV 명령어
  - 나눗셈 명령어가 뭐야
  - div랑 idiv 차이
  - div idiv 차이
  - 나눗셈 결과가 이상해요
  - edx를 왜 지워야 하나요
  - div하면 프로그램이 죽어요
symptom_keywords:
  - 나눗셈 결과가 이상해요
  - 0으로 나누기 오류
  - edx를 안 비웠는데
  - div하면 크래시가 나요
  - 몫이 말도 안 되게 커요
  - divide error가 떴어요
  - 나눗셈인데 SIGFPE가 떠요
---

## 한 줄 요약
`DIV`는 부호 없는(unsigned) 나눗셈을 수행하며, 나눌 값(피제수)을 `AX`/`DX:AX`/`EDX:EAX`/`RDX:RAX` 레지스터 쌍에서 가져오고, 오퍼랜드로 준 나누는 값(제수)으로 나눠서 몫과 나머지를 각각 다른 레지스터에 남긴다.

## 언제 검색해야 하나
- 디스어셈블리에 `div ecx`, `div rcx`, `div dword ptr [rbp-4]` 같은 코드가 나오는데 나누는 대상이 어디 있는지 헷갈릴 때
- `div` 직전에 `xor edx, edx`가 왜 붙어 있는지 궁금할 때
- `div`를 실행했더니 결과가 말도 안 되게 크거나(몫이 이상함), 프로그램이 "divide error"로 죽었는데 나누는 값이 0이 아닌데도 죽어서 원인을 못 찾을 때
- `unsigned int`/`size_t` 나눗셈이 어셈블리로 어떻게 변하는지 확인할 때
- `DIV`와 `IDIV`([REV-0053](./rev-0053-idiv.md))의 차이가 궁금할 때

## 핵심 개념

### DIV의 오퍼랜드는 "제수" 하나뿐이다 — 피제수는 항상 암묵적 레지스터 쌍
`DIV`는 명령어에 오퍼랜드를 하나만 적는다. 이 오퍼랜드는 **나누는 값(divisor, 제수)** 이다. 그런데 **나뉘는 값(dividend, 피제수)** 은 명령어에 적지 않는다 — 항상 정해진 레지스터(쌍)에서 암묵적으로 읽어온다. 이게 DIV/IDIV를 처음 볼 때 가장 헷갈리는 부분이다.

오퍼랜드 폭에 따라 피제수/몫/나머지가 어디 있는지가 다음처럼 정확히 정해져 있다:

| DIV 형태 | 피제수(암묵) | 몫 | 나머지 |
|---|---|---|---|
| `DIV r/m8` | AX (16비트) | AL | AH |
| `DIV r/m16` | DX:AX (32비트) | AX | DX |
| `DIV r/m32` | EDX:EAX (64비트) | EAX | EDX |
| `DIV r/m64` | RDX:RAX (128비트) | RAX | RDX |

즉 `div ecx`라고 쓰면: "EDX:EAX(위 32비트가 EDX, 아래 32비트가 EAX인 64비트 값)를 ECX로 나눠서, 몫은 EAX에, 나머지는 EDX에 넣어라"라는 뜻이다. `div rcx`는 폭만 64비트로 커져서 RDX:RAX를 RCX로 나눈 뒤 몫은 RAX, 나머지는 RDX에 들어간다.

### 반드시 알아야 할 핵심 — DIV 실행 전 상위 레지스터(EDX/RDX)를 반드시 0으로 만들어야 한다
`DIV`는 **부호 없는(unsigned)** 나눗셈이다. 그래서 피제수도 부호 없는 값으로 취급된다. 일반적인 `unsigned int a`처럼 32비트짜리 값 하나를 32비트 값으로 나누고 싶을 뿐이라면, 64비트 피제수(EDX:EAX)의 위쪽 32비트(EDX)는 **의미상 0이어야 한다** — a를 64비트 부호 없는 값으로 "확장"하면 상위 비트는 전부 0이기 때문이다.

그래서 컴파일러가 생성하는 표준 관용구는 항상 이렇다:
```asm
xor edx, edx      ; EDX = 0  (피제수 상위 32비트를 0으로 확장)
div ecx            ; EDX:EAX(= 0:EAX, 사실상 그냥 EAX) / ECX
```
64비트에서도 동일하게:
```asm
xor edx, edx        ; 32비트 xor지만 x64에서 상위 32비트도 자동으로 0이 되어 RDX 전체가 0이 됨
div rcx
```
(참고: x64에서 32비트 레지스터에 쓰기 연산을 하면 상위 32비트가 자동으로 0으로 클리어되는 규칙이 있어서, `xor edx,edx` 한 줄로 RDX 전체가 0이 된다. 만약 컴파일러가 RDX 전체를 명시적으로 0으로 만들고 싶다면 `xor edx, edx` 대신 `xor rdx, rdx`를 쓰기도 하는데 결과는 같다.)

**이 `xor edx, edx`를 빠뜨리면(혹은 이미 있는 줄로 착각하고 못 보면) 실제로 벌어지는 일:**
- EDX에 이전 계산에서 남은 쓰레기 값이 그대로 있는 상태로 `div ecx`가 실행된다.
- 그러면 CPU는 `(쓰레기:EAX) / ECX`를 계산한다 — 원하던 `(0:EAX) / ECX`가 아니다.
- 결과적으로 몫이 터무니없이 큰 값으로 나오거나,
- 만약 그 "진짜" 몫이 EAX(32비트)에 담기지 못할 만큼 크면 **CPU가 `#DE`(Divide Error) 예외를 발생시켜 프로그램이 죽는다.**

여기서 반드시 짚어야 할 함정이 있다: **이 `#DE` 예외는 리눅스에서는 `SIGFPE`, 윈도우에서는 `STATUS_INTEGER_DIVIDE_BY_ZERO`(정수 나눗셈 오류) 메시지로 뜨는데, 이름 때문에 초보자는 "0으로 나눴나?"라고 오해하기 쉽다.** 하지만 제수(ECX)가 0이 아닌데도 이 예외가 뜰 수 있다 — EDX를 비우지 않아서 몫이 32비트를 초과했을 때도 똑같은 예외가 뜬다.

### 진짜 0으로 나누기와 구분하는 법
`DIV`는 제수(오퍼랜드)가 실제로 0일 때도 동일하게 `#DE`를 낸다. 디버거로 크래시 지점을 잡았을 때 원인을 구분하려면:
1. **크래시 순간 제수 레지스터(예: ECX) 값을 확인한다.**
   - 제수가 **0**이면 → 소스 코드에 진짜 0으로 나누는 버그가 있다는 뜻.
   - 제수가 **0이 아니면** → 십중팔구 다음 셋 중 하나다: ① `xor edx,edx`(또는 `cdq`) 같은 상위 레지스터 셋업이 빠졌거나, ② 원래 `IDIV`([REV-0053](./rev-0053-idiv.md))를 써야 하는데 `DIV`를 쓴 경우(부호 있는 값을 부호 없는 나눗셈에 넣음), ③ 몫이 정말로 목적지 레지스터 폭을 넘길 만큼 큰 경우(진짜 오버플로우).
2. **`div` 바로 직전 EDX 값을 확인한다.** 0이 아니라면 그게 원인일 가능성이 매우 높다.

### 플래그: DIV 이후 CF, OF, SF, ZF, AF, PF는 전부 미정의(undefined)
Intel SDM은 `DIV` 실행 후 **모든 플래그가 undefined(정의되지 않음)** 라고 명시한다. 즉 `div` 다음 줄에서 곧바로 `jc`나 `jz` 같은 조건 분기를 거는 코드는 없다고 봐야 한다 — 컴파일러도 그렇게 하지 않는다. 나눗셈 결과로 뭔가를 분기하려면 컴파일러는 `div` 다음에 **별도로 `test`나 `cmp`를 추가**해서 몫/나머지 값 자체를 검사한다. (플래그 전반에 대한 정리는 [REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기](./rev-0088-flags-overview.md) 참고.)

### Unsigned 전용 — 부호 있는 값을 넣으면 어떻게 되나
`DIV`는 오퍼랜드를 항상 부호 없는 값으로 해석한다. 만약 실제로는 음수인 값(예: `int x = -8;`의 비트 패턴)을 실수로 `DIV`에 넣으면, CPU는 그 비트 패턴을 "아주 큰 양수"로 취급해서 나눈다 — 원래 의도(-8을 4로 나눠서 -2)와 전혀 다른, 터무니없이 큰 몫이 나온다. 이것이 바로 부호 있는 나눗셈에 `IDIV`([REV-0053](./rev-0053-idiv.md))가 별도로 존재하는 이유다. **컴파일러가 `DIV`를 썼는지 `IDIV`를 썼는지 보는 것만으로 원본 C 변수가 `unsigned`였는지 `signed`였는지 역추적할 수 있다** — 이 인사이트는 IDIV 문서([REV-0053](./rev-0053-idiv.md))에서 더 자세히 다룬다.

### 컴파일러 패턴 — 몫과 나머지를 동시에 쓰는 코드
`DIV` 한 번으로 몫(EAX)과 나머지(EDX)가 **동시에** 나온다. 그래서 C 코드가 같은 두 값에 대해 `a / b`와 `a % b`를 모두 쓰면, 컴파일러는 `div`를 **딱 한 번만** 생성하고 EAX와 EDX를 각각 재사용한다 — `div`가 두 번 나오지 않는다고 이상하게 여기지 말 것.
```c
unsigned int q = a / b;
unsigned int r = a % b;
```
```asm
mov  eax, a
xor  edx, edx
div  ecx          ; ecx = b
; 이 시점: eax = q(몫), edx = r(나머지) — div는 한 번만 실행됐다
```

### 상수로 나누는 경우는 DIV가 아예 안 보일 수 있다
`x / 10`처럼 **컴파일 시점에 상수인 값**으로 나누는 코드는 대부분 실제 `div` 명령어로 컴파일되지 않는다. 최신 컴파일러는 나눗셈을 "매직 넘버 곱셈 + 시프트" 조합(`mul`/`imul` + `shr`)으로 바꿔서 훨씬 빠르게 실행되도록 최적화한다. 이 패턴은 이 문서의 범위를 벗어나지만, IDA/Ghidra의 디컴파일러는 대부분 이 패턴을 알아보고 의사코드에는 그냥 `x / 10`처럼 깔끔하게 보여준다 — 그래서 raw 디스어셈블리에서 `div`가 안 보인다고 나눗셈이 없다고 오해하지 말 것.

## 화면/코드에서 보이는 징후
- `xor edx, edx` 바로 다음 줄에 `div reg` — 표준 unsigned 나눗셈 셋업. 정상.
- `div reg`인데 바로 위에 EDX를 세팅하는 코드가 안 보임 — EDX 셋업을 놓쳤거나(버그), 위쪽 더 먼 곳에서 이미 0으로 세팅해뒀을 수도 있으니 위로 더 거슬러 올라가서 확인 필요.
- `div` 직후 EAX와 EDX를 각각 다른 곳에 저장(`mov [rbp-4], eax` / `mov [rbp-8], edx`) — 몫과 나머지를 둘 다 쓰는 코드.
- IDA/Ghidra 의사코드에 그냥 `a / b`, `a % b`로 깔끔하게 표시됨.

## 가장 먼저 할 것
`div` 명령어를 만나면 순서대로 확인한다:
1. 오퍼랜드 폭이 몇 비트인지 (8/16/32/64) → 피제수 레지스터 쌍이 무엇인지 결정
2. `div` 바로 위쪽에 EDX(또는 DX, RDX)를 0으로 만드는 코드(`xor edx,edx` 등)가 있는지
3. 없다면 더 위로 거슬러 올라가 EDX가 이미 0으로 보장되는 지점이 있는지, 아니면 이게 진짜 버그인지 확인
4. `div` 직후 EAX(몫)와 EDX(나머지) 중 어느 쪽이 실제로 쓰이는지 확인 — 둘 다 쓰이면 `/`와 `%`가 같이 있는 코드

## 단계별 절차

**1) 정상적인 32비트 unsigned 나눗셈 셋업 확인**
```asm
mov  eax, [rbp-4]   ; eax = a (unsigned int)
xor  edx, edx        ; edx = 0  (필수 셋업)
div  dword ptr [rbp-8]   ; eax(quotient) = a / b, edx(remainder) = a % b
```
IDA에서 `xor edx,edx` → `div`가 붙어 있는 패턴을 보면 unsigned 32비트 나눗셈이라고 바로 판단할 수 있다.

**2) EDX 셋업이 빠진 것처럼 보이는 경우**
`div` 바로 위에 EDX 관련 코드가 없다면, 함수 시작부터 EDX를 아무도 건드리지 않았는지 위로 스크롤하며 확인한다. 정말 없다면 컴파일러 버그가 아니라 리터럴하게 EDX가 이전 계산 결과를 그대로 들고 있다는 뜻이므로, 디버거로 실제 그 시점 EDX 값을 확인해본다(x64dbg/IDA 디버거에서 `div` 명령 주소에 브레이크포인트).

**3) `#DE` 크래시 원인 분류**
크래시가 나면 크래시 지점(정확히 `div` 명령 주소)에서 레지스터 창을 열어 제수 레지스터 값과 EDX 값을 확인한다. 제수가 0이면 진짜 0으로 나누기 버그, 제수가 0이 아니면 EDX 미설정 또는 signed/unsigned 혼동 의심.

**4) 몫/나머지 사용처 추적**
`div` 직후 EAX를 저장/사용하는 줄과 EDX를 저장/사용하는 줄을 각각 찾아서, 그게 각각 `/`와 `%` 중 무엇에 해당하는지 표시해둔다.

## 명령어/단축키
- IDA: `F5`(디컴파일 — `div`가 대부분 `/`, `%`로 정리되어 나옴), 레지스터 창에서 EDX/EAX 실시간 확인, `F2`(브레이크포인트를 `div` 주소에 걸기), `F9`(실행)
- x64dbg: CPU 창에서 `div` 라인 우클릭 → "Set breakpoint", 상단 레지스터 패널에서 EDX/EAX 값 확인
- GDB/Pwndbg: `break *0x주소`로 `div` 명령 주소에 브레이크포인트, `info registers edx eax`(또는 pwndbg의 레지스터 패널)로 값 확인

## 출력 해석
- 디버거 레지스터 창에서 `div` 실행 직후 EAX 값이 비정상적으로 크면(예: 32비트 거의 끝값) → EDX가 0이 아니었을 가능성이 매우 높다. `div` 실행 직전으로 되돌아가 EDX 값을 확인해본다.
- `#DE`/`SIGFPE`/`STATUS_INTEGER_DIVIDE_BY_ZERO` 예외 메시지는 "0으로 나눔"과 "몫 오버플로우" 두 원인을 구분하지 않고 동일하게 뜬다는 점을 기억한다.
- IDA 의사코드에서 `a / b`와 `a % b`가 같은 두 변수(a, b)에 대해 함께 나타나면, 원본 어셈블리에는 `div`가 한 번만 있었을 가능성이 높다.

## 흔한 실수
- `xor edx, edx`를 생략하고 `div`를 쓰는 것 — 이전 계산의 쓰레기 값이 EDX에 남아있으면 결과가 완전히 틀어지거나 프로그램이 죽는다.
- `#DE`/`SIGFPE` 예외를 보고 무조건 "0으로 나눴다"고 단정하는 것 — 제수가 0이 아닌데도 EDX 미설정만으로 똑같은 예외가 뜬다는 걸 모르면 원인 파악이 늦어진다.
- 부호 있는 값(음수 비트 패턴)을 실수로 `DIV`에 넣는 것 — `DIV`는 항상 unsigned로 해석하므로 음수는 거대한 양수로 취급되어 몫이 터무니없이 커진다. 부호 있는 나눗셈은 반드시 `IDIV`([REV-0053](./rev-0053-idiv.md))를 써야 한다.
- `div` 다음에 곧바로 `jc`, `jz` 같은 조건 분기가 있을 거라 기대하는 것 — `div`는 모든 플래그를 undefined로 만들므로 그런 분기는 없다. 결과를 검사하는 코드는 `div` 다음에 별도의 `test`/`cmp`로 나타난다.

## 막혔을 때 다음 체크
- `div` 직전 EDX 값이 확실히 0인지 디버거로 직접 찍어봤는가? 정적으로만 보고 넘겨짚지 말 것.
- 크래시가 진짜 "0으로 나누기"인지 "EDX 미설정"인지 제수 레지스터 값을 직접 확인했는가?
- 혹시 이 명령어가 `DIV`가 아니라 `IDIV`([REV-0053](./rev-0053-idiv.md))는 아닌지 오퍼랜드/니모닉을 다시 확인했는가?
- 상수로 나누는 코드인데 `div`가 안 보인다면, `mul`/`imul` + `shr` 조합(매직 넘버 나눗셈 최적화)으로 대체됐을 가능성을 의심하고 디컴파일 결과(F5)를 먼저 신뢰할 것.

## 미니 예제

**예제 1 — 표준 32비트 unsigned 나눗셈 (정상)**
```c
unsigned int a = 100;
unsigned int b = 7;
unsigned int q = a / b;   // 14
```
```asm
mov  eax, 100
xor  edx, edx      ; 필수: 피제수 상위 32비트를 0으로
mov  ecx, 7
div  ecx             ; eax = 14 (몫), edx = 2 (나머지)
```

**예제 2 — `xor edx,edx`를 빠뜨린 깨진 코드 (버그 상황 재현)**
```asm
; 이전에 다른 계산에서 edx = 0x00000003 이 남아있었다고 가정
mov  eax, 100
; xor edx, edx   <-- 이 줄이 빠졌다!
mov  ecx, 7
div  ecx             ; 실제로는 (3:100)/7 = (0x300000064)/7 을 계산 → 몫이 거대한 값
                       ; 심지어 몫이 32비트(EAX)에 안 들어갈 만큼 크면 #DE 발생
```
이 코드는 겉보기엔 예제 1과 거의 똑같아 보이지만, `xor edx,edx` 한 줄이 빠졌다는 이유만으로 결과가 완전히 틀어지거나 프로그램이 크래시한다.

**예제 3 — 8비트 형태 (AX → AL/AH)**
```c
unsigned char a = 200;
unsigned char b = 9;
unsigned char q = a / b;   // 22
unsigned char r = a % b;   // 2
```
```asm
mov  ax, 200        ; 피제수는 AX (8비트 div의 암묵 피제수는 16비트 AX)
mov  cl, 9
div  cl               ; al = 22 (몫), ah = 2 (나머지)
```

**예제 4 — 몫과 나머지를 동시에 쓰는 경우**
```c
unsigned int q = a / b;
unsigned int r = a % b;
printf("%u %u", q, r);
```
```asm
mov  eax, a
xor  edx, edx
div  ecx              ; ecx = b, 이 한 줄로 eax=q, edx=r 둘 다 계산됨
mov  [rbp-4], eax    ; q 저장
mov  [rbp-8], edx    ; r 저장
```

## 관련 글
- [REV-0053 — IDIV: Signed 나눗셈](./rev-0053-idiv.md)
- [REV-0050 — MUL: Unsigned 곱셈](./rev-0050-mul.md)
- [REV-0051 — IMUL: Signed 곱셈과 컴파일러 패턴](./rev-0051-imul.md)
- [REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기](./rev-0088-flags-overview.md)
- REV-0041 — MOVSX와 MOVSXD: Sign Extension 이해 (예정)
- REV-0069 — JG JGE JL JLE: Signed 비교 분기 (예정)
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기 (예정)

## 출처/검증
- `DIV` 명령어 동작(오퍼랜드 폭별 피제수/몫/나머지 레지스터, 플래그 undefined 여부, `#DE` 예외 조건): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "DIV—Unsigned Divide" 섹션 기준 (2026-09-08 검증).
- EFLAGS 영향(CF/OF/SF/ZF/AF/PF undefined): 동 매뉴얼 "DIV" 섹션의 "Flags Affected" 항목 기준.
- x64 레지스터 상위 32비트 자동 클리어 규칙: Intel SDM Volume 1, "3.4.1.1 General-Purpose Registers in 64-Bit Mode" 기준.
