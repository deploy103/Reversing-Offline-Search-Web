---
id: REV-0422
title: "JS와 JNS: 부호 플래그 기반 분기"
slug: "rev-0422-js-jns"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - js
  - jns
  - JS
  - JNS
  - js 명령어
  - jns 명령어
  - sign flag
  - 부호 플래그
  - SF 플래그
  - 음수 판별
  - negative check
  - sign jump
  - 부호 분기
  - test eax eax js
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - js 뭐임
  - jns가 뭐죠
  - 음수인지 분기
  - SF 분기
  - 부호 플래그 조건 분기
symptom_keywords:
  - test eax eax 다음에 js가 나옴
  - js가 jl이랑 뭐가 다른지 모르겠음
  - 값이 음수인지 확인하는 코드가 이해 안 됨
  - neg 다음에 jns가 나옴
  - 부호 판별 분기가 어떻게 동작하는지 모르겠음
---

## 한 줄 요약
`JS`/`JNS`는 부호 플래그(SF)만 검사해서 분기하는 명령으로, 직전 연산 결과의 최상위 비트(부호 비트)가 1이면(음수로 해석되면) `JS`가, 0이면(음수가 아니면) `JNS`가 분기한다.

## 언제 검색해야 하나
- `test eax, eax` 뒤에 `js`가 나오는데 `jl`이나 `jz`와 뭐가 다른지 궁금할 때
- `if (x < 0)` 같은 C 코드가 어셈블리로 어떻게 컴파일되는지 확인할 때
- `NEG` 연산 뒤에 `jns`가 붙어서 원래 값의 부호를 판별하는 코드를 만났을 때
- `JS`/`JNS`와 `JL`/`JGE`(부호 있는 대소 비교)의 차이가 헷갈릴 때

## 핵심 개념

### 정확한 동작
- `JS` (Jump if Sign): `SF = 1`이면 분기.
- `JNS` (Jump if Not Sign): `SF = 0`이면 분기.

`SF`는 직전 산술/논리 연산 결과의 최상위 비트(MSB)를 그대로 복사한 값이다. 부호 있는(signed) 정수 표현(2의 보수)에서는 MSB가 1이면 음수이므로, `SF=1`은 "결과가 음수"라는 뜻이 된다.

### 오퍼랜드와 방향
`js label`, `jns label` — 오퍼랜드는 상대 오프셋(rel8/rel32)으로 표현되는 분기 대상 레이블 하나뿐이다. 오퍼랜드가 조건이나 값을 직접 갖지 않고, 오직 SF 플래그만 읽는다.

### 레지스터/메모리/플래그 영향
- 레지스터/메모리에 아무 영향 없음.
- **플래그를 전혀 바꾸지 않는다** — SF를 포함해 모든 플래그를 읽기만 할 뿐 쓰지 않는다.
- RIP: 분기가 성립하면 목표 주소로, 아니면 다음 명령으로. 스택 변화는 없다(`CALL`과 달리 반환 주소를 남기지 않는다).

### JS/JNS vs JL/JGE: SF만 볼 것인가, SF와 OF를 같이 볼 것인가
`JL`(REV-0069)은 `SF != OF`일 때 분기하는데, 이는 오버플로가 발생한 경우까지 고려한 "진짜 부호 있는 미만" 판정이다. 반면 `JS`는 오직 `SF`만 보고 `OF`는 신경 쓰지 않는다.

두 조건이 갈라지는 지점은 **오버플로가 발생했을 때**뿐이다. 예를 들어 `CMP`/`SUB`처럼 뺄셈 기반 연산이라면, 결과가 오버플로되면 SF만으로 판단한 부호와 실제 수학적 부호가 어긋날 수 있다. 반면 `TEST`, `AND`, `OR` 같은 논리 연산은 **정의상 항상 OF를 0으로 클리어**하므로, 논리 연산 뒤에서는 `SF`(=JS/JNS)만 봐도 결과가 `JL`/`JGE`와 완전히 일치한다. 그래서 컴파일러는 `test eax, eax` 뒤에 부호 판별이 필요하면 `JL`이 아니라 더 단순한 `JS`를 즐겨 쓴다.

### 컴파일러 패턴
`if (x < 0)`처럼 0과 비교하는 부호 판별은 대부분 다음처럼 컴파일된다:
```asm
test    eax, eax
js      negative_case
```
또는 직전 산술 연산(`SUB`, `NEG`, `ADD` 등)의 플래그가 아직 유효하다면 별도의 `TEST`/`CMP` 없이 곧바로 `JS`/`JNS`가 붙기도 한다:
```asm
sub     eax, ebx
js      result_negative
```

### IDA/Ghidra 디컴파일에서의 모습
`test eax, eax` + `js label` 시퀀스는 IDA F5나 Ghidra에서 거의 예외 없이 `if (x < 0)` 또는 `if ((int)x < 0)` 형태로 깔끔하게 재구성된다. 다만 앞선 연산이 부호 확장 없이 처리된 값이라면(예: `unsigned int`를 `int`로 강제 캐스팅한 경우), 디컴파일러가 붙이는 타입 캐스팅 표기(`(int)`)를 눈여겨보면 원래 값의 실제 타입과 분석 중인 부호 판별이 서로 어긋나 있는지 확인할 수 있다.

### 배열 인덱스/버퍼 크기 검증에서의 등장
`JS`/`JNS`는 특히 배열 인덱스나 버퍼 오프셋이 음수인지 검사하는 방어 코드에서 자주 나타난다.
```c
if (index < 0 || index >= size) { return ERROR; }
```
이런 코드는 흔히 `test`/`js`로 먼저 음수 여부를 걸러내고, 이어서 `cmp`/`jae`로 상한을 검사하는 두 단계로 컴파일된다. 이 패턴을 알아두면 바운드 체크 로직을 빠르게 식별하고, 혹시 음수 검사 단계가 누락된 함수가 있는지(정수 오버플로/언더플로 취약점의 단서) 빠르게 훑어볼 수 있다.

## 화면/코드에서 보이는 징후
```asm
test    eax, eax
js      negative_value
```
```asm
neg     eax
jns     was_non_positive
```
```asm
cmp     eax, 0
jns     positive_or_zero
```

## 가장 먼저 할 것
1. `JS`/`JNS` 바로 앞의 명령이 무엇의 결과를 세팅했는지(`TEST`, `CMP`, `SUB`, `NEG` 등) 확인한다.
2. 그 값이 부호 있는(signed) 타입으로 해석되는 값인지 확인한다 — 부호 없는(unsigned) 값이라면 SF 판정 자체가 의미 없다.
3. 앞선 연산이 논리 연산(`TEST`/`AND`/`OR`)인지 산술 연산(`SUB`/`CMP`)인지 구분해, 오버플로 가능성을 고려해야 하는지 판단한다.

## 단계별 절차
```asm
mov     eax, [rbp-4]
test    eax, eax
js      handle_negative
```
1. `[rbp-4]`가 `int` 타입 지역 변수라고 가정.
2. `test eax, eax`는 `eax & eax`를 계산해 SF/ZF/PF만 세팅하고 결과는 버린다(REV-0059 참고).
3. `js handle_negative`는 `eax`의 MSB(비트31)가 1이면, 즉 `eax < 0`(signed)이면 분기.
4. 원래 C 코드는 `if (x < 0) { handle_negative(); }` 형태로 재구성할 수 있다.

## 명령어/단축키
- IDA/Ghidra: F5 디컴파일 시 `if (x < 0)` / `if (x >= 0)` 형태로 바로 재구성되는 경우가 많다.
- GDB/x64dbg: EFLAGS 창에서 `SF` 비트를 직접 확인해 분기 여부를 미리 예측할 수 있다.

## 출력 해석
- 디버거 플래그 창에서 `SF=1`이면 다음 `JS`가 분기하고, `SF=0`이면 `JNS`가 분기한다.
- IDA 디컴파일 결과에서 `< 0`, `>= 0` 비교로 보이는 조건문은 대부분 이 SF 기반 분기에서 온 것이다.

## 흔한 실수
- `JS`가 항상 "그 값이 최종적으로 음수"임을 100% 보장한다고 맹신하는 것 — 산술 연산(특히 `SUB`/`CMP`) 직후라면 오버플로 여부까지 고려해야 진짜 부호 있는 비교가 되며, 그럴 땐 `JL`/`JGE`(SF^OF)를 써야 한다. `JS`/`JNS`는 오직 "결과 MSB가 1인가"만 볼 뿐이다.
- `JS`/`JNS`와 `JL`/`JGE`를 혼용해도 항상 같은 결과라고 오해하는 것 — 논리 연산(`TEST`/`AND`/`OR`) 뒤에서는 OF가 항상 0이라 실제로 같지만, `SUB`/`CMP`처럼 오버플로가 발생할 수 있는 연산 뒤에서는 다를 수 있다.
- 부호 없는(unsigned) 값에 `JS`/`JNS`를 적용해 "음수인지" 판별하려는 것 — unsigned 값에는 애초에 "음수"라는 개념이 없으므로, 이런 코드가 있다면 값이 실제로는 signed로 취급되고 있다는 신호로 봐야 한다.

## 막혔을 때 다음 체크
- `JS`/`JNS` 앞의 명령이 `SUB`/`CMP` 계열인지 `TEST`/`AND`/`OR` 계열인지 다시 확인했는가?
- 관련 값이 `int`인지 `unsigned int`인지 원래 타입을 추정해봤는가?
- 결과가 예상과 다르다면 오버플로가 발생한 경계값(`INT_MIN`, `INT_MAX` 근처)인지 의심해본다.

## 미니 예제

**예제 1 — 단순 음수 판별**
```c
int x = get_value();
if (x < 0) { handle_negative(); }
```
```asm
call    get_value
test    eax, eax
js      handle_negative
```

**예제 2 — NEG 이후 원래 값의 부호 판별**
```asm
mov     eax, [val]
neg     eax          ; eax = -val
jns     val_was_non_positive   ; NEG 결과가 음수가 아니면(즉 원래 val <= 0)
```

**예제 3 — CMP 0 후 분기**
```c
if (balance >= 0) { proceed(); }
```
```asm
mov     eax, [balance]
cmp     eax, 0
jns     proceed
```

## 관련 글
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0423 — JO와 JNO: 오버플로 플래그 기반 분기
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- JS/JNS 명령어 동작과 SF 정의: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "Jcc—Jump if Condition Is Met" 섹션 기준 (2026-09-08 검증).
- 논리 연산이 OF를 항상 0으로 클리어하는 규칙: Intel SDM Volume 1, 정수 논리 연산 및 EFLAGS 챕터 기준.
