---
id: REV-0053
title: "IDIV: Signed 나눗셈"
slug: "rev-0053-idiv"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - idiv
  - IDIV
  - Idiv
  - idiv 명령어
  - idiv instruction
  - "idiv ecx"
  - "idiv rcx"
  - "idiv eax"
  - "idiv ebx"
  - "idiv dword ptr"
  - signed division
  - signed 나눗셈
  - 부호있는 나눗셈
  - cdq
  - CDQ
  - cqo
  - CQO
  - cbw
  - cwd
  - cdqe
  - sign extension
  - 부호 확장
  - EDX:EAX
  - RDX:RAX
  - divide error
  - "#DE"
  - 0으로 나누기
  - 음수 나눗셈
  - 음수 나눗셈 버그
  - truncate toward zero
  - 0을 향한 절삭
  - 몫과 나머지
  - idiv div 차이
  - signed unsigned 나눗셈 차이
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - idiv 뭐임
  - idiv가 뭐죠
  - idiv 명령
  - IDIV 명령어
  - cdq가 왜 있어요
  - cqo가 뭐예요
  - idiv랑 div 차이
  - 음수 나눗셈이 이상해요
  - 양수는 되는데 음수는 안돼요
  - idiv하면 결과가 이상해요
symptom_keywords:
  - 음수 나눗셈만 결과가 이상해요
  - cdq 없이 idiv를 썼어요
  - 양수일때만 정상이에요
  - 나눗셈 결과가 음수인데 이상해요
  - 나머지 부호가 이상해요
  - idiv 하면 크래시가 나요
---

## 한 줄 요약
`IDIV`는 부호 있는(signed) 나눗셈을 수행한다. `DIV`([REV-0052](./rev-0052-div.md))와 레지스터 구조는 똑같지만, 나누기 전에 피제수 상위 절반을 **부호 확장**(`CDQ`/`CQO` 등)으로 채워야 한다는 점이 결정적으로 다르다 — 이걸 빠뜨리면 양수는 우연히 맞고 음수만 틀리는 아주 헷갈리는 버그가 생긴다.

## 언제 검색해야 하나
- 디스어셈블리에서 `cdq` 또는 `cqo`가 `idiv` 바로 앞에 항상 붙어 있는 이유가 궁금할 때
- 나눗셈 코드가 양수 입력에서는 잘 되는데 음수 입력에서만 결과가 이상할 때
- `int`로 나눗셈했는데 결과가 `floor()`가 아니라 다르게 반올림되는 것 같을 때 (`-7 / 2`가 왜 `-3`인지)
- `DIV`([REV-0052](./rev-0052-div.md))와 `IDIV`의 차이, 컴파일러가 둘 중 무엇을 왜 골랐는지 알고 싶을 때
- IDA/Ghidra 의사코드가 `CONCAT44(extraout_EDX, EAX)` 같은 이상한 표현을 보여줄 때

## 핵심 개념

### 오퍼랜드 구조는 DIV와 완전히 동일하다 — 단, 부호 있는 값으로 해석
`IDIV`도 오퍼랜드는 제수 하나뿐이고, 피제수는 암묵적 레지스터 쌍에서 가져오며, 몫/나머지가 나오는 레지스터도 `DIV`와 정확히 같은 자리다:

| IDIV 형태 | 피제수(암묵) | 몫 | 나머지 |
|---|---|---|---|
| `IDIV r/m8` | AX (16비트) | AL | AH |
| `IDIV r/m16` | DX:AX (32비트) | AX | DX |
| `IDIV r/m32` | EDX:EAX (64비트) | EAX | EDX |
| `IDIV r/m64` | RDX:RAX (128비트) | RAX | RDX |

차이는 딱 하나: 이 값들이 전부 **부호 있는(2의 보수)** 값으로 해석된다는 것이다.

### 반드시 알아야 할 핵심 — 피제수 상위 절반은 "0"이 아니라 "부호 확장"이어야 한다
`DIV`에서는 상위 레지스터(EDX)를 단순히 0으로 지우면 됐다(`xor edx,edx`). 하지만 `IDIV`는 부호 있는 나눗셈이므로, 피제수의 상위 절반은 **하위 절반 값의 부호에 맞춰 확장**되어야 한다:
- 하위 값이 **양수**라면 → 상위 절반은 전부 **0**이어야 한다.
- 하위 값이 **음수**라면 → 상위 절반은 전부 **1**(0xFFFFFFFF 등)이어야 한다.

이건 정확히 2의 보수 부호 확장(sign extension) 규칙이고, x86은 이 작업을 전담하는 명령어를 따로 두고 있다. 컴파일러는 `IDIV` 바로 앞에 **반드시** 이 중 하나를 넣는다:

| 명령어 | 동작 |
|---|---|
| `CBW` | AL(8비트) → AX(16비트)로 부호 확장 |
| `CWD` | AX(16비트) → DX:AX(32비트)로 부호 확장 |
| `CDQ` | EAX(32비트) → EDX:EAX(64비트)로 부호 확장 — `idiv r/m32` 앞에 가장 흔히 보임 |
| `CDQE` | EAX(32비트) → RAX(64비트)로 부호 확장 (나눗셈 전용은 아니고 다른 용도로도 쓰임, 간단히만 알아두면 됨) |
| `CQO` | RAX(64비트) → RDX:RAX(128비트)로 부호 확장 — `idiv r/m64` 앞에 가장 흔히 보임 |

표준 관용구는 이렇다:
```asm
cdq                 ; EDX = EAX의 부호를 32비트 전체로 확장
idiv ecx             ; (EDX:EAX) / ECX, signed
```
64비트에서는:
```asm
cqo                  ; RDX = RAX의 부호를 64비트 전체로 확장
idiv rcx
```

**`CDQ`/`CQO`가 실제로 하는 일**: 개념적으로는 EAX(또는 RAX)를 산술 오른쪽으로 31비트(또는 63비트) 시프트해서 부호 비트를 모든 비트에 복사하는 것과 같다. EAX의 최상위 비트(부호 비트)가 0이면 EDX는 전부 0이 되고, 최상위 비트가 1이면 EDX는 전부 1(0xFFFFFFFF)이 된다 — 이게 정확히 2의 보수 부호 확장이다.

### 이 셋업을 빠뜨리면 왜 "양수는 되는데 음수만 틀리는" 버그가 생기는가
초보자가 흔히 저지르는 실수는 두 가지다: `cdq`/`cqo`를 아예 빠뜨리거나, `DIV`용 관용구인 `xor edx,edx`를 실수로 `IDIV` 앞에 쓰는 것. 두 경우 모두 **양수 입력에서는 우연히 정상 동작한다는 것이 이 버그를 특히 위험하게 만든다.** 왜냐하면 양수를 부호 확장한 상위 절반도 어차피 전부 0이기 때문에, "부호 확장"과 "그냥 0으로 지우기"가 양수에 한해서는 결과가 똑같이 나온다. **버그는 오직 음수 입력을 넣을 때만 드러난다** — 그래서 간단한 양수 테스트 케이스로는 절대 못 잡아내는 전형적인 함정이고, CTF 문제 풀이 중 셀프 작성 어셈블리나 패치 코드에서 자주 나오는 실수다.

구체적인 숫자로 추적해보자. `-14 / 4`를 32비트로 계산한다고 하자(정답은 `-3`, 나머지 `-2` — C의 0을 향한 절삭 규칙).

**올바른 경우 (`cdq` 사용):**
```
eax = -14  (비트 패턴: 0xFFFFFFF2)
cdq        ; eax의 부호비트(1, 음수)가 전체로 퍼져서 edx = 0xFFFFFFFF
idiv ecx    ; ecx = 4
; (edx:eax) = 0xFFFFFFFF_FFFFFFF2 (부호 있는 -14, 64비트로 정확히 확장된 값)
; 결과: eax = -3 (몫), edx = -2 (나머지)  ← 정답
```

**틀린 경우 (`xor edx,edx`를 잘못 사용, 또는 이전 값이 우연히 0이 아닌 경우):**
```
eax = -14  (비트 패턴: 0xFFFFFFF2)
xor edx, edx   ; edx = 0  <- 잘못된 셋업! 부호 확장이 아니라 그냥 0
idiv ecx        ; ecx = 4
; (edx:eax) = 0x00000000_FFFFFFF2 (이건 -14가 아니라 아주 큰 양수로 해석됨: 4294967282)
; 결과: 완전히 엉뚱한 몫이 나오거나, 몫이 32비트를 넘으면 #DE 크래시
```
같은 명령어(`idiv ecx`)인데 그 앞의 EDX 셋업 방식 하나 때문에 결과가 하늘과 땅 차이로 갈린다.

### 플래그: IDIV 이후에도 CF, OF, SF, ZF, AF, PF는 전부 미정의(undefined)
`DIV`와 마찬가지로 `IDIV` 실행 후 모든 플래그는 undefined다. 결과를 검사하는 분기가 필요하면 컴파일러는 `idiv` 뒤에 별도로 `test`/`cmp`를 추가한다 — `idiv` 직후에 곧바로 `jz`/`js` 같은 분기가 있다면, 그건 idiv의 결과가 아니라 그 앞의 다른 명령이나 그 뒤에 숨은 별도 비교 명령을 보고 있는 것이다. (플래그 전반 정리는 [REV-0088](./rev-0088-flags-overview.md) 참고.)

### 부호 있는 나눗셈의 반올림 방향 — "0을 향한 절삭(truncate toward zero)"
`IDIV`는 몫을 계산할 때 소수점 이하를 **0 방향으로 잘라낸다.** 이것은 C99/C11 표준에서 정의한 정수 나눗셈 `/`의 동작과 정확히 일치한다. 그래서 컴파일러는 signed `/`와 `%`를 별도의 보정 코드 없이 그냥 `idiv` 하나로 처리할 수 있다(과거 일부 아키텍처나 오래된 C 표준은 음의 무한대 방향으로 내림(`floor`)했기 때문에 나눗셈 결과를 보정하는 추가 명령이 필요했다).

예시로 `-7 / 2`는 수학적으로 `-3.5`인데, IDIV/C는 이걸 **`-3`으로 자른다** (`-4`가 아니다!). `floor(-3.5) = -4`와 헷갈리지 말 것 — x86 `IDIV`와 C의 정수 `/`는 항상 0에 더 가까운 쪽으로 자른다.

### 아주 중요한 리버싱 인사이트 — CDQ/CQO vs XOR EDX,EDX로 원본 변수의 signed/unsigned를 역추적
DIV/IDIV, MUL/IMUL 어느 쪽을 쓰든 원본 C 소스는 남아있지 않지만, 나눗셈 직전의 셋업 명령만 보면 원본 변수의 부호 여부를 정확히 추론할 수 있다:
- 나눗셈 직전에 **`cdq`/`cqo`(부호 확장)** 가 있다 → 원본 변수는 **`int`/`long` 같은 signed 타입**이었고, `idiv`가 쓰인다.
- 나눗셈 직전에 **`xor edx,edx`/`xor rdx,rdx`(제로 확장)** 가 있다 → 원본 변수는 **`unsigned int`/`unsigned long`/`size_t` 같은 unsigned 타입**이었고, `div`([REV-0052](./rev-0052-div.md))가 쓰인다.

디스어셈블리만 봐서는 사라진 타입 정보를 이 규칙 하나로 되살릴 수 있다 — 이 문서 전체에서 가장 실전에 유용한 리버싱 휴리스틱 중 하나다.

### 컴파일러 패턴 — 몫과 나머지 동시 사용
`DIV`와 마찬가지로 `IDIV` 한 번으로 몫(EAX)과 나머지(EDX)가 동시에 나오므로, `a/b`와 `a%b`가 같이 쓰인 코드는 `idiv`가 한 번만 등장한다.
```c
int q = a / b;
int r = a % b;
```
```asm
mov  eax, a
cdq
idiv ecx        ; ecx = b
; eax = q, edx = r
```

### IDA/Ghidra 의사코드에서 보이는 모습
대부분은 그냥 깔끔하게 `a / b`, `a % b`로 표시되거나, signed임을 명시하려고 `(int)a / (int)b`처럼 캐스트가 붙기도 한다. 가끔 Ghidra가 `CDQ`+`IDIV` 조합을 완전히 인식하지 못하면 `CONCAT44(extraout_EDX, EAX)` 같은 로우레벨 표현이 그대로 남아있는 경우가 있다 — 이건 디컴파일러가 EDX:EAX 레지스터 쌍 패턴을 온전히 해석하지 못했다는 표시이니, 그럴 땐 raw 디스어셈블리를 직접 보고 `cdq`/`idiv` 조합을 손으로 해석하면 된다.

## 화면/코드에서 보이는 징후
- `cdq` 바로 다음 줄에 `idiv reg` — 표준 signed 32비트 나눗셈. 정상.
- `cqo` 바로 다음 줄에 `idiv reg` — 표준 signed 64비트 나눗셈. 정상.
- `idiv` 바로 위에 `xor edx,edx`가 있다 — signed 나눗셈에 unsigned 셋업이 섞인 것처럼 보이면 버그 의심(직접 작성한 셸코드/패치 코드에서 특히 주의).
- IDA/Ghidra 의사코드에 `CONCAT44(extraout_EDX, EAX)` 등장 — 디컴파일러가 나눗셈 레지스터 쌍 패턴을 완전히 인식하지 못한 것.

## 가장 먼저 할 것
`idiv` 명령어를 만나면 순서대로 확인한다:
1. 오퍼랜드 폭이 몇 비트인지 (8/16/32/64) → 피제수 레지스터 쌍이 무엇인지 결정
2. `idiv` 바로 위쪽에 폭에 맞는 부호 확장 명령(`cbw`/`cwd`/`cdq`/`cqo`)이 있는지 — 없다면 버그 의심 지점
3. `cdq`(32비트용)와 `cqo`(64비트용)가 실제 나눗셈 폭과 맞는지 확인 — 폭이 안 맞으면 그것도 버그
4. `idiv` 직후 EAX(몫)와 EDX(나머지) 중 무엇이 쓰이는지 확인

## 단계별 절차

**1) 정상적인 32비트 signed 나눗셈 셋업 확인**
```asm
mov  eax, [rbp-4]   ; eax = a (int)
cdq                   ; edx = eax의 부호 확장 (필수)
idiv dword ptr [rbp-8]   ; eax(quotient) = a / b, edx(remainder) = a % b
```

**2) 부호 확장 명령이 없거나 폭이 안 맞는 경우**
`idiv ecx`(32비트) 앞에 `cdq`가 아니라 `cwd`(16비트용)나 아예 아무 것도 없다면, 실제 실행 시 EDX 값이 어떻게 되는지 디버거로 직접 확인한다. 음수 테스트 입력을 넣어서 결과가 틀어지는지 확인하는 것이 가장 확실하다.

**3) 음수 vs 양수 입력으로 버그 재현**
버그가 의심되면 양수 입력(예: `14 / 4`)과 음수 입력(예: `-14 / 4`)을 각각 넣어보고 결과를 비교한다. 양수만 맞고 음수가 틀리면 부호 확장 셋업 문제가 거의 확실하다.

**4) 몫/나머지 사용처 추적**
`idiv` 직후 EAX와 EDX 사용처를 각각 찾아 `/`와 `%` 중 무엇에 대응하는지 표시한다.

## 명령어/단축키
- IDA: `F5`(디컴파일), 레지스터 창에서 EDX/EAX 확인, `F2`(idiv 주소에 브레이크포인트), `F9`(실행)
- x64dbg: `idiv` 라인 우클릭 → 브레이크포인트, 상단 레지스터 패널에서 EDX/EAX 확인
- GDB/Pwndbg: `break *0x주소`, `info registers edx eax`, 음수/양수 입력값을 바꿔가며 `run`으로 재현

## 출력 해석
- `idiv` 실행 직후 EAX/EDX 값이 음수 입력에서만 이상하면 부호 확장 셋업 누락을 의심한다.
- `-7 / 2`가 `-3`으로 나오는 건 정상(0을 향한 절삭)이지, `-4`가 나와야 정상인 게 아니다.
- `cdq`/`cqo`가 보이면 원본 변수는 signed, `xor edx,edx`가 보이면 원본 변수는 unsigned — 타입을 역추적하는 근거로 삼는다.

## 흔한 실수
- `cdq`/`cqo`를 빠뜨리거나 `xor edx,edx`(DIV용 관용구)를 실수로 IDIV 앞에 쓰는 것 — 음수 입력에서만 결과가 틀어지는, 양수 테스트로는 절대 못 잡는 버그가 생긴다.
- `cdq`(32비트용)와 `cqo`(64비트용)를 헷갈려서 실제 나눗셈 폭과 다른 부호 확장 명령을 쓰는 것 — 실제 사용 중인 폭에 맞는 EDX/RDX가 오염된다.
- `IDIV`가 `floor()`처럼 반올림한다고 착각하는 것 — 실제로는 0을 향해 자르므로 `-7 / 2 = -3`이지 `-4`가 아니다.
- `idiv` 직후 곧바로 조건 분기가 그 결과를 반영한다고 가정하는 것 — 플래그는 전부 undefined이므로 결과 검사는 별도 `test`/`cmp`로 나타난다.

## 막혔을 때 다음 체크
- 버그가 음수 입력에서만 재현되는가? 그렇다면 `cdq`/`cqo` 부호 확장 셋업부터 의심할 것.
- `idiv` 앞의 셋업 명령이 정확히 나눗셈 폭(8/16/32/64비트)과 일치하는지 다시 확인했는가?
- 이 명령어가 `IDIV`가 아니라 `DIV`([REV-0052](./rev-0052-div.md))는 아닌지 니모닉을 다시 확인했는가?
- 반올림 방향이 이상하다고 느껴진다면 "0을 향한 절삭"이 맞는지, 기대값이 `floor()` 기준으로 잘못 계산된 건 아닌지 재확인할 것.

## 미니 예제

**예제 1 — 표준 32비트 signed 나눗셈 (정상)**
```c
int a = -14;
int b = 4;
int q = a / b;   // -3
int r = a % b;   // -2
```
```asm
mov  eax, -14
cdq                ; 필수: eax의 부호를 edx 전체로 확장
mov  ecx, 4
idiv ecx            ; eax = -3 (몫), edx = -2 (나머지)
```

**예제 2 — `cdq`를 빠뜨린 깨진 코드 (음수에서만 터지는 버그 재현)**
```asm
mov  eax, -14
; cdq   <-- 이 줄이 빠졌다! edx에 이전 값이 남아있거나 실수로 0으로 지워짐
mov  ecx, 4
idiv ecx            ; edx:eax가 -14가 아니라 거대한 양수로 해석되어 완전히 틀린 몫/나머지가 나오거나 #DE 발생
```
같은 입력, 같은 `idiv ecx`인데 `cdq` 한 줄이 있고 없고에 따라 결과가 완전히 달라진다. 양수 `a`로 테스트하면 이 버그는 절대 드러나지 않는다는 점을 다시 강조한다.

**예제 3 — 64비트 signed 나눗셈**
```c
long long a = -1000000000000LL;
long long b = 7;
long long q = a / b;
```
```asm
mov  rax, -1000000000000
cqo                  ; rax의 부호를 rdx 전체로 확장 (64비트용)
mov  rcx, 7
idiv rcx              ; rax = 몫
```

**예제 4 — 몫과 나머지 동시 사용**
```c
int q = a / b;
int r = a % b;
printf("%d %d", q, r);
```
```asm
mov  eax, a
cdq
idiv ecx             ; ecx = b, 이 한 줄로 eax=q, edx=r 둘 다 계산됨
mov  [rbp-4], eax   ; q 저장
mov  [rbp-8], edx   ; r 저장
```

## 관련 글
- [REV-0052 — DIV: Unsigned 나눗셈](./rev-0052-div.md)
- [REV-0050 — MUL: Unsigned 곱셈](./rev-0050-mul.md)
- [REV-0051 — IMUL: Signed 곱셈과 컴파일러 패턴](./rev-0051-imul.md)
- [REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기](./rev-0088-flags-overview.md)
- REV-0041 — MOVSX와 MOVSXD: Sign Extension 이해
- REV-0069 — JG JGE JL JLE: Signed 비교 분기

## 출처/검증
- `IDIV` 명령어 동작(오퍼랜드 폭별 피제수/몫/나머지 레지스터, 플래그 undefined 여부, `#DE` 예외 조건): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "IDIV—Signed Divide" 섹션 기준 (2026-09-08 검증).
- `CDQ`/`CQO`/`CWD`/`CBW`/`CDQE` 부호 확장 명령어 동작: 동 매뉴얼 "CWD/CDQ/CQO—Convert Word to Doubleword/Convert Doubleword to Quadword" 섹션 기준.
- 부호 있는 정수 나눗셈의 0을 향한 절삭(truncate toward zero) 규칙: ISO/IEC 9899 (C99/C11) 표준의 정수 나눗셈 연산자(`/`, `%`) 정의 기준.
