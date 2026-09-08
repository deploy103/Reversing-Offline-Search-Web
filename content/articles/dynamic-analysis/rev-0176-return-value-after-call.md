---
id: REV-0176
title: "CALL 직후 반환값 확인하는 법"
slug: "rev-0176-return-value-after-call"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg]
keywords:
  - return value
  - 반환값
  - 리턴값
  - CALL 직후
  - EAX RAX
  - XMM0
  - finish 반환값
  - Value returned
aliases:
  - CALL 후에 반환값 보는법
  - 반환값 확인하는법
  - 함수가 뭘 리턴하는지
  - EAX 반환값
  - RAX 반환값
  - finish로 리턴값 확인
symptom_keywords:
  - 반환값이 뭔지 모르겠음
  - 함수가 리턴한 값을 못찾겠음
  - EAX RAX 어디서 확인
  - CALL 직후 뭘 봐야하는지 모르겠음
  - 함수 결과값 확인하는법
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
CALL 명령어가 실행된 **직후**(그 다음 명령 주소)에 브레이크포인트를 걸면, 정수/포인터 반환값은 RAX(64비트)/EAX(32비트)에, 실수 반환값은 XMM0에 이미 담겨 있으므로 디버거에서 그 값을 그대로 읽어 함수가 무엇을 반환했는지 확정할 수 있다.

## 언제 검색해야 하나
- `call strlen` 다음에 `cmp eax, 0Ah` 같은 코드가 나오는데, 실제로 EAX에 어떤 값이 들어왔는지 확인하고 싶을 때
- 크랙미(crackme)에서 검증 함수의 반환값(성공/실패를 나타내는 0 또는 1)이 실제로 몇인지 확인해서 분기 로직을 이해하고 싶을 때
- 함수가 포인터를 반환하는지, 정수를 반환하는지, 아니면 실수를 반환하는지 원형을 모를 때
- GDB `finish`가 자동으로 보여주는 `Value returned is $1 = ...`를 어떻게 해석해야 할지 모를 때
- 여러 함수가 중첩 호출되는 코드에서 "이 값은 어느 함수의 반환값인지" 헷갈릴 때

## 핵심 개념

### 왜 "CALL 직후"라는 타이밍이 중요한가
함수가 값을 돌려줄 때는 특정 레지스터에 그 값을 넣어놓고 `RET`으로 복귀한다. CALL이 실행되고 그 함수가 완전히 끝나서 호출자 코드로 돌아온 바로 다음 명령어 지점이면, 이 레지스터에 반환값이 이미 세팅되어 있는 상태다. 이 타이밍(CALL 다음 명령 주소)에 브레이크포인트를 걸면 되는데, 함수 내부가 복잡하거나 시간이 걸릴 수 있으므로 실무에서는 CALL 자체에 브레이크포인트를 걸고 Step Over(F8/`nexti`)로 한 번에 통과시키거나, Run Until Return(`Ctrl+F9`/`finish`, REV-0171 참고)으로 반환 시점까지 이동하는 방법을 더 많이 쓴다.

### 정수/포인터 반환값 — RAX/EAX
- 64비트 정수나 포인터를 반환하는 함수 → **RAX**
- 32비트 정수를 반환하는 함수 → **EAX**(RAX의 하위 32비트)
- `bool`을 반환하는 함수(C에서는 보통 int로 취급) → EAX의 최하위 바이트(AL)만 의미 있는 경우가 많다(0 또는 1)
- 이 규칙은 **SysV(Linux)와 Microsoft x64(Windows) 모두 동일**하다 — 인자 레지스터는 플랫폼마다 다르지만, 정수 반환값 레지스터(RAX/EAX)는 두 규약에서 공통이다.

### 실수 반환값 — XMM0
`float`/`double`을 반환하는 함수는 정수 레지스터가 아니라 **XMM0** 레지스터의 하위 32비트(float) 또는 64비트(double)에 값을 담아 반환한다. 정수 반환값과 반환 레지스터 자체가 다르므로, 함수 원형이 실수를 반환한다고 알고 있다면 EAX/RAX가 아니라 XMM0을 봐야 한다. 이 규칙도 SysV와 Windows x64에서 공통이다.

### 구조체를 반환하는 경우
작은 구조체(보통 8~16바이트 이하, 플랫폼별로 세부 규칙이 다름)는 RAX(또는 RAX:RDX 두 레지스터)에 나눠 담겨 반환될 수 있고, 더 큰 구조체는 "숨겨진 첫 번째 인자"로 반환할 메모리 주소를 미리 전달받아(호출자가 공간을 마련해서 그 주소를 첫 인자처럼 넘김) 그 메모리에 결과를 채워 넣는 방식(RVO/hidden pointer)으로 처리된다. 이 경우 CALL 직후 RAX에는 그 반환 버퍼의 주소가 다시 들어있는 경우가 많다.

### void 함수는 반환값이 없다
함수 원형이 `void`라면 애초에 반환값이라는 개념이 없으므로, CALL 직후 EAX/RAX에 어떤 값이 있어도 그건 "이전에 쓰이고 남은 잔여값"일 뿐 의미가 없다. GDB `finish`를 쓰면 반환 타입이 `void`인 경우 `Value returned is ...` 줄 자체가 출력되지 않으므로 이를 통해 구분할 수 있다.

### CALL 직후 반환값이 바로 쓰이는 전형적인 패턴
```asm
call    strlen
cmp     eax, 0Ah     ; 반환값을 즉시 비교
jnz     fail
```
```asm
call    malloc
mov     [rbp-0x8], rax   ; 반환된 포인터를 지역 변수에 저장
test    rax, rax          ; NULL 체크 (malloc 실패 시 0 반환)
jz      alloc_fail
```
이런 패턴은 매우 흔하므로, CALL 다음 줄이 `cmp eax, ...`, `test eax, eax`, `mov [...], rax` 형태라면 거의 확실히 반환값을 즉시 활용하는 코드라고 봐도 된다.

## 화면/코드에서 보이는 징후
- CALL 다음 줄이 곧바로 `test eax, eax` 또는 `cmp eax, ...`라면 반환값을 즉시 검사하는 매우 흔한 패턴이다.
- CALL 다음 줄이 `movss`/`movsd` 명령으로 XMM0을 다른 곳으로 옮긴다면 실수 반환값을 처리하는 코드다.
- x64dbg에서 CALL을 Step Over(F8)한 직후 레지스터 창에서 RAX 값이 빨간색으로 강조되어 바뀌어 있는 것이 보이면 그 값이 반환값이다.
- GDB `finish` 실행 후 `Value returned is $1 = ...` 줄이 출력되면 그 값이 바로 반환값이다. 이 줄이 없다면 `void` 반환이거나 GDB가 반환 타입을 알 수 없는 경우다.

## 가장 먼저 할 것
1. 분석할 CALL 명령어를 찾고, 그 함수가 정수/포인터를 반환하는지 실수를 반환하는지 짐작한다(함수 이름, 임포트 시그니처, 또는 다음 줄의 명령 종류로 판단).
2. CALL 명령어에 브레이크포인트를 걸거나, CALL 다음 주소에 직접 브레이크포인트를 건다.
3. Step Over(F8/`nexti`) 또는 Run Until Return(`Ctrl+F9`/`finish`)로 반환 시점까지 이동한다.
4. RAX/EAX(정수) 또는 XMM0(실수)을 확인한다.

## 단계별 절차

**x64dbg**
1. 분석할 `call` 명령어 줄을 찾는다.
2. 그 줄에서 `F8`(Step Over)을 눌러 함수 전체를 실행시키고 CALL 다음 줄에서 멈춘다.
3. 레지스터 창에서 RAX(64비트 값 전체) 또는 EAX(32비트만 필요하면 하위 32비트)를 확인한다.
4. 실수 반환값이 궁금하면 레지스터 창의 XMM 레지스터 섹션(또는 FPU 탭)에서 XMM0을 확인한다.
5. 함수가 이미 내부로 들어가 있는 상태(Step Into 후)라면, `Ctrl+F9`(Execute till Return)로 즉시 빠져나오면서 반환값을 확인할 수 있다(REV-0171 참고).

**GDB / Pwndbg**
1. CALL 직전에 브레이크포인트를 걸고 `run`으로 실행한다.
2. 함수 내부로 들어가지 않고 반환값까지 한 번에 보고 싶다면:
   ```
   nexti
   p/x $rax
   ```
3. 또는 함수 안으로 이미 들어간 상태라면:
   ```
   finish
   ```
   실행 결과에 `Value returned is $1 = 0x1` 형태로 자동 출력된다.
4. 실수 반환값을 직접 확인하고 싶다면:
   ```
   p $xmm0
   ```
   (Pwndbg에서는 `p $xmm0.v4_float` 등으로 세부 포맷을 지정할 수도 있다.)
5. 반환값이 포인터라면 가리키는 내용까지 확인:
   ```
   x/s $rax     ; 문자열이라면
   x/4xg $rax   ; 구조체/버퍼라면
   ```

## 명령어/단축키
- x64dbg: `F8`(Step Over로 CALL 통과), `Ctrl+F9`(Execute till Return), 레지스터 창(RAX/EAX), FPU/XMM 레지스터 탭(실수 반환값)
- GDB/Pwndbg: `nexti`(`ni`, CALL 통과), `finish`(반환값 자동 출력), `p/x $rax`, `p $xmm0`, `x/s $rax`(포인터가 가리키는 문자열 확인)

## 출력 해석
- GDB `finish` 결과 `Value returned is $1 = 10`이 나오면 그 함수가 정수 10을 반환했다는 뜻이다.
- GDB `finish` 결과 `Value returned is $1 = (char *) 0x603010 "flag{...}"` 처럼 나오면 반환값이 포인터이고 GDB가 그 포인터가 가리키는 문자열까지 자동으로 보여준 것이다(디버그 심볼/타입 정보가 있을 때).
- x64dbg에서 RAX가 `0000000000000000`이면 반환값이 0(NULL 포인터, 실패, false 등 문맥에 따라 다르게 해석)이라는 뜻이다.
- XMM0의 값이 이상하게 큰 정수처럼 보인다면, 이는 IEEE 754 부동소수점 비트 패턴을 정수로 잘못 해석한 것일 수 있다 — 반드시 float/double 포맷으로 별도 확인해야 한다.

## 흔한 실수
- 반환값이 EAX(32비트)인지 RAX(64비트) 전체인지 구분하지 않고 대충 보는 것 — 함수가 64비트 포인터를 반환하는데 EAX(하위 32비트)만 보면 상위 비트가 잘려서 잘못된 주소로 오인할 수 있다.
- `void` 함수인데도 EAX/RAX에 남아있는 이전 값을 "반환값"이라고 착각하는 것 — 함수 원형을 먼저 확인해야 한다.
- 실수를 반환하는 함수인데 EAX/RAX만 보고 "반환값이 0이다"라고 잘못 결론짓는 것 — XMM0을 확인해야 한다.
- CALL **직전**에 멈춘 상태에서 RAX를 보고 "이게 반환값이다"라고 착각하는 것 — 아직 함수가 실행되지 않았으므로 그 RAX 값은 이전 코드에서 남은 값일 뿐이다. 함수가 끝난 뒤(CALL 다음 시점)의 값을 봐야 한다.
- 중첩 호출에서 안쪽 함수의 반환값과 바깥쪽 함수의 반환값을 혼동하는 것 — 콜스택(REV-0173)을 함께 확인해서 지금 어느 함수가 막 반환했는지 명확히 한다.

## 막혔을 때 다음 체크
- 반환값이 예상과 다르다면 → 정말 CALL **이후** 시점에서 확인하고 있는지, Step Over가 제대로 함수를 통과했는지(중간에 다른 브레이크포인트에 안 걸렸는지) 확인한다.
- 함수 원형(반환 타입)을 모르겠다면 → 임포트 함수라면 공식 API 문서를, 사용자 함수라면 IDA F5 디컴파일 결과를 참고해 정수/포인터/실수 중 무엇인지 먼저 판단한다.
- 반환값이 곧바로 다른 곳에 안 쓰이는 것 같다면 → 그 함수가 사실 부작용(side effect, 예: 파일에 쓰기)을 위해 호출됐을 뿐 반환값 자체는 안 쓰이는(`void`처럼 취급되는) 경우일 수 있다.
- 구조체 반환이 의심된다면 → RAX가 스택/힙 주소처럼 보이는지 확인하고, 그 주소를 Dump/`x`로 열어 구조체 필드 전체를 살펴본다.

## 미니 예제

**x64dbg — strlen 반환값(길이) 확인**
```asm
lea     rcx, [rbp-0x40]  ; 인자: 문자열 포인터
call    strlen
cmp     eax, 0Ah          ; 반환값(길이)을 10과 비교
jnz     fail
```
`call strlen` 줄에서 `F8`(Step Over) → 레지스터 창에서 EAX 확인(예: `0000000A`, 즉 10) → 다음 줄 `cmp`가 왜 `jnz`로 안 빠지는지(길이가 정확히 10이므로) 바로 이해할 수 있다.

**GDB/Pwndbg — finish로 검증 함수 반환값 확인**
```
(gdb) break check_flag
(gdb) run
(gdb) finish
Run till exit from #0  check_flag (input=0x7fffffffe420 "flag{test}") at chal.c:12
0x0000000000401235 in main () at chal.c:20
20          if (check_flag(buf)) {
Value returned is $1 = 1
```
`Value returned is $1 = 1`을 보고 `check_flag()`가 "성공"(1)을 반환했다는 것을 바로 확인했다 — 이 값이 왜 1이 나왔는지는 REV-0174(조건 분기)와 REV-0172(레지스터 추적)로 더 거슬러 올라가 확인할 수 있다.

## 관련 글
- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가
- REV-0170 — Step Into와 Step Over 차이
- REV-0171 — Run Until Return과 함수 빠져나오기
- REV-0172 — 레지스터 값을 실행 중 추적하는 법
- REV-0175 — CALL 직전 함수 인자 확인하는 법
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- 정수/포인터 반환값 레지스터(RAX/EAX)와 실수 반환값 레지스터(XMM0): System V Application Binary Interface AMD64 Architecture Processor Supplement "Return Values" 절, Microsoft Learn "x64 calling convention" 공식 문서 "Return values" 절 기준(두 규약 모두 RAX/XMM0 사용에서 동일).
- x64dbg Step Over/Execute till Return과 레지스터 창: x64dbg 공식 문서 기준.
- GDB `finish` 명령의 반환값 자동 출력(`Value returned is`): GNU GDB 공식 매뉴얼 "Returning from a Function" 절 기준.
- 2026-09-08 검증.
