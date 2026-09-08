---
id: REV-0452
title: "삼항 연산자(?:)가 CMOVcc로 컴파일되는 패턴"
slug: "rev-0452-ternary-cmovcc-pattern"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - 삼항 연산자
  - ternary operator
  - CMOVcc
  - CMOVG
  - CMOVL
  - CMOVE
  - branchless
  - 분기 없는 코드
  - conditional move
aliases:
  - 삼항연산자 어셈블리
  - a > b ? a : b 어셈블리
  - cmovg가 뭔지 모르겠음
  - 분기가 없는데 조건이 반영됨
symptom_keywords:
  - cmp 다음에 jcc 없이 바로 cmovcc가 나옴
  - 두 값을 다 계산해놓고 하나만 고름
  - 삼항연산자인데 jmp가 안 보임
  - 분기예측 실패를 피하려고 cmov를 쓴 것 같음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`x = cond ? a : b;` 같은 삼항 연산자는 `a`와 `b`를 조건 분기 없이 **둘 다 미리 계산**해 둔 뒤, `CMOVcc`(조건부 이동, REV-0075)로 조건이 참일 때만 레지스터 값을 덮어쓰는 방식으로 컴파일되는 경우가 많으며, 이는 분기 예측 실패(branch misprediction) 비용을 없애기 위한 최적화다.

## 언제 검색해야 하나
- 소스에 `? :`(삼항 연산자)나 짧은 `if-else` 대입문이 있는데, 대응하는 어셈블리에 `JMP`/`Jcc`로 분기하는 대신 `CMP` 직후 `CMOVcc`가 바로 나올 때
- `CMOVG`, `CMOVL`, `CMOVE`, `CMOVNE`, `CMOVA`, `CMOVB` 등 `CMOV` 계열 명령이 낯설어서 뭘 하는지 모를 때
- 두 값(`a`, `b`)을 모두 계산하는 코드가 먼저 나오고, 그 다음에야 조건 검사가 나와서 "왜 둘 다 계산하지? 하나는 버려질 텐데"라는 의문이 들 때
- `min`/`max` 매크로나 함수가 분기 없이 구현된 것처럼 보일 때

## 핵심 개념

### 왜 분기 대신 CMOV를 쓰는가
`if (cond) x = a; else x = b;` 형태의 코드를 그대로 번역하면 `CMP`+`Jcc`+`MOV`+`JMP`+`MOV` 같은 분기 구조가 된다. 하지만 현대 CPU는 **분기 예측(branch prediction)** 을 통해 다음 명령을 미리 가져와 실행하는데, 예측이 틀리면 파이프라인을 통째로 비우고 다시 시작해야 하는 큰 페널티(수 사이클~수십 사이클)가 발생한다. 특히 `cond`가 실행할 때마다 무작위에 가깝게 참/거짓이 바뀌는 경우(정렬 안 된 데이터의 min/max 계산 등) 분기 예측은 계속 틀리기 쉽다.

`CMOVcc`는 이 문제를 피한다 — **분기 자체를 아예 없애고**, `a`와 `b`를 모두 미리 계산해 둔 뒤, 조건이 참이면 레지스터에 `a`를, 거짓이면 원래 값(`b`가 이미 들어있는 상태)을 그대로 유지한다. 분기가 없으니 예측 실패도 없다. 다만 그 대신 **양쪽 값을 항상 다 계산**해야 하므로, `a`와 `b`의 계산 비용이 크거나 부작용(side effect, 예: 함수 호출, 널 포인터 역참조)이 있으면 컴파일러는 CMOVcc 대신 원래의 분기 방식을 유지한다 — 그래서 삼항 연산자가 항상 CMOVcc로 바뀌는 것은 아니다.

### 전형적인 코드 형태
```asm
; x = (a > b) ? a : b;   (max(a, b))
mov     eax, a
mov     ecx, b
cmp     eax, ecx
cmovle  eax, ecx      ; a <= b이면 eax(결과)를 ecx(b)로 덮어씀; a > b면 그대로 a 유지
```
여기서 핵심은 **두 값(a와 b)이 이미 각각 레지스터(EAX, ECX)에 준비되어 있고, CMOVcc는 조건에 따라 목적지 레지스터의 내용을 "그대로 둘지 소스로 덮어쓸지"만 결정한다**는 점이다. `CMOVcc dst, src`는 조건이 참이면 `dst = src`를, 거짓이면 `dst`를 **전혀 건드리지 않는다**(변경 없음) — 이건 `MOV`와 근본적으로 다른 "선택적 대입"이다.

### CMOVcc의 조건 코드는 CMP/TEST 뒤의 Jcc와 완전히 동일한 규칙
`CMOVG`(signed greater), `CMOVL`(signed less), `CMOVE`(equal), `CMOVNE`(not equal), `CMOVA`(unsigned above), `CMOVB`(unsigned below) 등, 접미사 `cc`는 REV-0069/REV-0070/REV-0088에서 다룬 `Jcc`의 조건 코드와 완전히 같은 인코딩을 공유한다. 즉 `JG`가 참일 조건이면 `CMOVG`도 똑같은 플래그 조합에서 참이다 — `Jcc`를 이해했다면 `CMOVcc`는 "그 조건에서 MOV를 실행한다"는 것만 추가로 알면 된다.

### 레지스터/메모리 효과와 플래그
- `CMOVcc`는 **EFLAGS를 전혀 변경하지 않는다** — 오직 읽기만 한다(REV-0075 참고). 그래서 `CMP`/`TEST` 직후 `CMOVcc`를 여러 개 연달아 써도 플래그가 계속 같은 상태로 유지되어 재사용 가능하다.
- 소스 오퍼랜드가 메모리일 수 있다(`cmovg eax, [rbx]`). **중요한 함정**: 조건이 거짓이라 실제로 `eax`에 반영되지 않더라도, x86 아키텍처 정의상 CMOVcc는 조건과 무관하게 **메모리 읽기 자체는 항상 수행**할 수 있다(구현에 따라 다를 수 있으나, 소스가 메모리면 접근이 이루어진다고 가정하는 것이 안전하다). 이는 분기 기반 코드라면 조건이 거짓일 때 아예 그 메모리를 읽지 않는 것과 다른 점이며, 널 포인터가 될 수 있는 포인터를 CMOVcc의 소스로 무심코 쓰면 조건과 무관하게 접근 위반이 날 수 있다는 뜻이다. 그래서 컴파일러는 이런 부작용 가능성이 있는 경우 CMOVcc 변환을 포기하고 분기를 유지한다.
- signed/unsigned은 어떤 `CMOVcc` 변형을 쓰느냐로 결정된다 — `CMOVG/CMOVL/CMOVGE/CMOVLE`는 signed, `CMOVA/CMOVB/CMOVAE/CMOVBE`는 unsigned 비교 결과를 따른다.
- 스택/RIP에는 영향이 없다 — `CMOVcc`는 순수 레지스터/메모리 간 조건부 데이터 이동이다.

### IDA/Ghidra 디컴파일에서 보이는 형태
Hex-Rays와 Ghidra는 `CMOVcc` 패턴을 매우 잘 인식해서, 대부분 원본과 거의 동일한 `x = (a > b) ? a : b;` 형태로 정확히 복원해준다. 드물게 복잡한 중첩 삼항식은 `if`문으로 풀어서 보여주기도 하는데, 의미는 동일하다.

## 화면/코드에서 보이는 징후
```asm
; max(a, b) 패턴
mov     eax, [a]
cmp     eax, [b]
cmovl   eax, [b]        ; a < b면 b로 교체
```
```asm
; abs(x) 패턴 (분기 없는 절대값)
mov     eax, x
mov     ecx, eax
neg     ecx               ; ecx = -x
cmovs   eax, ecx           ; SF=1(x가 음수)이면 -x로 교체
```
```asm
; 포인터 선택 (삼항으로 다른 버퍼를 고르는 경우)
mov     rax, ptr_a
mov     rcx, ptr_b
test    edx, edx
cmovz   rax, rcx           ; edx == 0이면 ptr_b 선택
```

## 가장 먼저 할 것
1. `CMP`/`TEST` 바로 뒤에 `Jcc`가 아니라 `CMOVcc`가 오는지 확인한다 — 있으면 분기 없는 조건부 대입(삼항 연산자 또는 짧은 if-else 대입)이 거의 확실하다.
2. `CMOVcc`의 목적지 레지스터가 그 이전에 어떤 값으로 미리 채워져 있었는지(참일 때/거짓일 때 각각 어떤 값인지) 추적한다.
3. 조건 코드(`G`, `L`, `E`, `A`, `B` 등)를 REV-0069/REV-0070의 대응표에 대입해서 원래 비교 연산자를 복원한다.

## 단계별 절차

**1) 두 후보 값 찾기**

`CMOVcc dst, src`에서 `dst`(변경 안 될 수도 있는 값)와 `src`(조건 참일 때 덮어쓸 값)가 각각 무엇인지 확인한다. 보통 바로 위 몇 줄에서 두 값이 서로 다른 레지스터에 준비되어 있다.

**2) 조건 복원**

`CMOVcc` 직전의 `CMP`/`TEST` 오퍼랜드와 `cc` 접미사를 REV-0069(signed)/REV-0070(unsigned) 표에 대입한다. 예: `cmp eax, ecx` 후 `cmovl eax, ecx`라면 "만약 eax < ecx이면 eax를 ecx로 바꾼다" → 결과적으로 `eax = min(eax, ecx)`.

**3) 원래 C 표현 재구성**

"조건 참이면 src, 거짓이면 원래 dst 값"이라는 논리를 `dst = cond ? src : dst_원래값` 형태로 정리한다.

**4) 왜 CMOVcc가 선택됐는지 문맥 확인**

두 값 모두 계산 비용이 낮고(단순 레지스터 읽기, 산술 몇 개) 부작용이 없는(메모리 쓰기, 함수 호출 없음) 경우에 CMOVcc가 자주 선택된다 — 이는 이 코드가 성능에 민감한 핫패스(hot path)일 가능성을 시사한다.

## 명령어/단축키
- IDA: `F5`(디컴파일, 삼항 연산자로 재구성되는지 확인), `CMOVcc` 명령 위에서 우클릭 → "Convert to..." 등으로 오퍼랜드 표현 변경 가능
- Ghidra: Decompile 창에서 자동 삼항식 복원 확인, Listing에서 `cmov` 텍스트 검색으로 전체 사용처 나열
- x64dbg/GDB: `CMOVcc` 명령에 브레이크포인트를 걸고, 실행 전후 목적지 레지스터 값이 실제로 바뀌었는지/안 바뀌었는지 스텝 실행으로 직접 확인(`p/x $eax` 전후 비교)

## 출력 해석
- IDA/Ghidra가 `x = a > b ? a : b;`로 정확히 복원했다면, 원본은 CMOVcc 기반 분기 없는 코드였다는 뜻이다.
- 같은 로직인데 다른 함수에서는 `JMP`/`Jcc` 기반 분기로 컴파일되어 있다면, 컴파일러가 그 지점에서는 부작용이 있다고 판단했거나 최적화 레벨이 다르다는 뜻이니 문맥을 다시 살핀다.
- `CMOVcc`의 소스가 메모리 오퍼랜드라면, 그 메모리가 항상 유효한 주소인지(널 체크가 없는지) 확인할 가치가 있다 — 조건과 무관하게 읽기가 일어날 수 있기 때문이다.

## 흔한 실수
- `CMOVcc`를 보고 "이건 항상 실행되는 대입이니 조건이 의미 없다"고 착각하는 것 — `CMOVcc`는 여전히 조건부다. 다만 그 "조건부"가 `JMP`가 아니라 "레지스터를 덮어쓸지 말지"로 구현되어 있을 뿐이다.
- `CMOVcc`가 플래그를 바꾼다고 착각해서, 그 다음에 나오는 또 다른 `Jcc`/`CMOVcc`가 이전과 다른 조건을 검사한다고 오판하는 것 — `CMOVcc`는 플래그를 전혀 바꾸지 않으므로, 같은 `CMP` 결과를 여러 `CMOVcc`가 재사용하는 경우가 흔하다.
- 두 값(a, b) 중 하나만 계산되는 것으로 착각하고 코드를 반만 읽는 것 — CMOVcc 패턴에서는 **항상 둘 다 계산된다.** 이 때문에 계산 비용이 큰 함수 호출이 삼항 연산자 안에 있으면 컴파일러가 CMOVcc를 포기하고 분기로 되돌아간다는 사실과 연결지어 이해해야 한다.
- min/max 패턴을 보고 매번 "이게 왜 abs나 min/max인지" 처음부터 다시 유도하는 것 — `CMOVL`/`CMOVG` + 두 값 스왑이면 min/max, `CMOVS` + `NEG`면 절대값(abs)이라는 전형적인 관용구를 외워두면 빠르게 알아볼 수 있다.

## 막혔을 때 다음 체크
- `CMOVcc` 개별 명령의 정확한 의미(조건 코드 표)가 헷갈리면 → REV-0075(CMOVcc 원본 항목)를 먼저 읽는다.
- 조건 코드가 signed인지 unsigned인지 헷갈리면 → REV-0069(JG JGE JL JLE), REV-0070(JA JAE JB JBE)을 비교해서 읽는다.
- 비슷하지만 boolean 값(0/1)을 만드는 패턴이면 → 이건 CMOVcc가 아니라 REV-0453(SETcc 패턴)이니 그쪽으로 이동해서 구분한다.
- CMOVcc의 소스가 메모리라서 부작용이 걱정되면 → 그 메모리 주소가 항상 유효한지(널 포인터 아닌지) 위쪽 코드에서 확인.

## 미니 예제

**예제 1 — 삼항 연산자로 max 구현**
```c
int m = (a > b) ? a : b;
```
```asm
mov     eax, [a]
mov     ecx, [b]
cmp     eax, ecx
cmovle  eax, ecx     ; a <= b이면 b로 교체 → 결과적으로 max(a, b)
```

**예제 2 — 짧은 if-else 대입**
```c
int clamp = (x < 0) ? 0 : x;
```
```asm
mov     eax, x
xor     ecx, ecx     ; 0 준비
test    eax, eax
cmovs   eax, ecx      ; SF=1(x < 0)이면 0으로 교체
```

**예제 3 — 분기 없는 절대값(abs)**
```c
int a = abs(x);
```
```asm
mov     eax, x
mov     ecx, eax
neg     ecx
test    eax, eax
cmovl   eax, ecx      ; x < 0이면 -x로 교체
```

**예제 4 — 포인터를 조건에 따라 고르기**
```c
char *msg = ok ? "success" : "fail";
```
```asm
lea     rax, [success_str]
lea     rcx, [fail_str]
test    edx, edx        ; ok
cmovz   rax, rcx          ; ok == 0(거짓)이면 fail 문자열로 교체
```

## 관련 글
- REV-0075 — CMOVcc: 분기 없는 조건부 이동
- REV-0453 — 짧은 if문이 SETcc로 컴파일되는 패턴
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교

## 출처/검증
- `CMOVcc` 동작(조건부 이동, 플래그 미변경, 조건 코드가 Jcc와 동일)은 Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2, "CMOVcc—Conditional Move" 항목 기준.
- 분기 예측 실패 비용과 CMOVcc의 사용 동기는 Intel Optimization Reference Manual의 분기 예측(Branch Prediction) 및 조건부 이동 활용 권고 사항 기준.
- CMOVcc의 소스 메모리 오퍼랜드에 대한 접근 여부(조건과 무관하게 로드가 일어날 수 있음)는 Intel SDM Volume 2 CMOVcc 항목의 Operation 설명 기준.
