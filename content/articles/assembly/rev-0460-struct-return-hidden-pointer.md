---
id: REV-0460
title: "구조체 반환값이 숨은 포인터로 전달되는 패턴(RVO 기초)"
slug: "rev-0460-struct-return-hidden-pointer"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - hidden pointer return
  - 숨은 포인터 반환
  - sret
  - struct return
  - 구조체 반환값
  - RVO
  - NRVO
  - return value optimization
  - "RDI hidden argument"
  - "RCX hidden argument"
  - large struct return ABI
aliases:
  - 구조체 리턴 어셈블리
  - 구조체 반환 숨겨진 인자
  - RVO 어셈블리 예제
  - sret 패턴
symptom_keywords:
  - 함수 인자가 하나씩 밀려있음
  - rdi가 첫 인자가 아닌 것 같음
  - 구조체 리턴하는데 rax에 없음
  - 함수 시그니처보다 인자가 하나 더 많은 느낌
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
레지스터 한두 개에 담기에 너무 큰 구조체를 함수가 값으로 반환(`return`)하면, 호출자가 미리 결과를 저장할 메모리 공간을 마련해 그 주소를 **숨겨진 첫 번째 인자(hidden pointer, "sret")**로 넘기고, 함수 내부는 반환값을 그 주소에 직접 써넣는다 — 이 때문에 소스에는 없던 포인터 인자 하나가 실제 레지스터 배치에는 존재하게 된다.

## 언제 검색해야 하나
- 소스(또는 함수 시그니처를 안다고 생각한 함수)의 첫 번째 인자가 `RDI`(SysV)나 `RCX`(Windows x64)가 아니라 그 다음 레지스터(`RSI`/`RDX`)에 들어있는 것처럼 보여서 인자 매핑이 하나씩 밀려 보일 때
- 구조체를 반환하는 함수인데 `RAX`(64비트) 하나만으로는 다 담을 수 없는 크기라서 반환값이 어디 있는지 헷갈릴 때
- IDA/Ghidra 디컴파일에서 `func(&dest, a, b)`처럼 원래 시그니처에 없던 포인터가 첫 인자로 추가되어 나올 때
- C++ 코드에서 "RVO(Return Value Optimization)"라는 용어를 듣고 실제로 어셈블리에서 어떻게 구현되는지 확인하고 싶을 때

## 핵심 개념

### 왜 필요한가: 레지스터로 못 담는 반환값
함수의 반환값은 보통 정수/포인터면 `RAX`, 실수면 `XMM0`에 담긴다. 그런데 구조체(struct)를 값으로 반환하면 그 구조체가 레지스터 한두 개보다 클 수 있다. 예를 들어 `struct Point3D { double x, y, z; }`는 24바이트라서 레지스터 두세 개로도 부족하다. 이런 경우 CPU 레지스터만으로는 반환값을 넘길 방법이 없으므로, ABI(호출 규약)는 **메모리를 통한 반환**이라는 별도 규칙을 정의해뒀다.

### 동작 원리: 호출자가 공간을 만들고 주소를 넘긴다
1. **호출자(caller)**가 함수를 부르기 전에 반환값을 담을 메모리 공간(대개 자신의 스택 프레임 안)을 미리 확보한다.
2. 그 공간의 주소를 **숨겨진 첫 번째 인자**로 함수에 전달한다. 이 때문에 소스에는 없는 포인터 인자가 실제 호출 규약상 맨 앞에 끼어든다.
3. **피호출자(callee)**는 자신의 반환문(`return value;`)을 실행할 때, 그 값을 레지스터에 담는 대신 전달받은 주소가 가리키는 메모리에 직접 필드별로 써넣는다.
4. 관례적으로 함수는 끝날 때 그 숨겨진 포인터를 **RAX에도 다시 담아 반환**한다 — 호출자가 반환값 주소를 다시 계산할 필요 없이 바로 체이닝(예: `f(g())`)할 수 있게 하기 위한 편의다.

### ABI별 기준 크기
- **SysV AMD64 (Linux/macOS x64)**: 구조체가 16바이트 이하이고 "단순한(classify 규칙상 INTEGER/SSE로 분류 가능한)" 타입이면 `RAX:RDX`(정수) 또는 `XMM0:XMM1`(실수)에 나눠 담아 레지스터로 직접 반환한다. **16바이트를 초과**하거나 분류 규칙에 안 맞는 구조체는 숨은 포인터를 통해 반환하며, 이때 숨은 포인터는 **RDI**(원래 1번째 인자 자리)를 차지하고, 실제 소스상 1번째 인자는 **RSI**로, 2번째는 **RDX**로 한 칸씩 밀린다.
- **Microsoft x64 (Windows x64)**: 구조체가 1, 2, 4, 8바이트 중 하나의 크기이고 POD(Plain Old Data)면 정수 레지스터(RAX)에 직접 담아 반환할 수 있다. 그 외 크기(주로 8바이트 초과, 또는 8/16/32/64비트가 아닌 애매한 크기)나 비POD 타입은 숨은 포인터로 반환하며, 이때 숨은 포인터는 **RCX**(원래 1번째 인자 자리)를 차지하고 실제 1번째 인자는 **RDX**, 2번째는 **R8**로 밀린다.

### C++의 RVO/NRVO와의 관계 (개념 구분 주의)
"RVO(Return Value Optimization)"라는 용어는 종종 이 ABI 메커니즘 자체와 혼동되지만, 엄밀히는 서로 다른 층위의 개념이다.
- **ABI 레벨의 "숨은 포인터 반환"**: 크기가 큰 구조체를 반환할 때 컴파일러가 반드시 지켜야 하는 호출 규약이다. 최적화 여부(-O0/-O2)와 무관하게 항상 적용된다.
- **RVO/NRVO(컴파일러 최적화)**: C++에서 `return SomeClass(...)` 같은 임시 객체를 반환할 때, 원래는 "임시 객체 생성 → 복사(또는 이동) 생성자로 반환값에 복사 → 임시 객체 소멸" 과정을 거쳐야 하지만, 컴파일러가 이 복사/이동 생성자 호출 자체를 생략하고 **호출자가 넘겨준 숨은 포인터 위치에 곧바로 생성**해버리는 최적화다. C++17부터는 특정 조건(prvalue를 그대로 반환)에서 이 생략이 언어 표준상 보장된다(더 이상 "최적화"가 아니라 필수 동작).

즉 숨은 포인터 메커니즘은 RVO가 "그 위에서 작동할 수 있게 해주는 하드웨어/ABI 인프라"이고, RVO는 "그 인프라를 이용해 불필요한 복사를 생략하는 컴파일러 차원의 최적화"다.

### IDA/Ghidra 디컴파일에서 보이는 모습
디컴파일러가 이 패턴을 인식하면 두 가지 방식으로 보여준다.
- **인식 성공 시**: 숨은 포인터를 감춰서 `Point3D p = make_point(1.0, 2.0);`처럼 원래 소스와 거의 같은 모습으로 재구성한다.
- **인식 실패 시(또는 원본 그대로 보고 싶을 때)**: `make_point(&p, 1.0, 2.0)`처럼 숨은 포인터가 명시적인 첫 인자로 그대로 노출된다. Ghidra는 함수 시그니처에 리턴 타입이 `void`이고 첫 파라미터가 반환 타입과 같은 포인터인 함수를 sret 후보로 인식해 자동으로 함수 원형을 조정해주는 경우가 있다.

## 화면/코드에서 보이는 징후
- 함수 호출 직전에 `lea rdi, [rbp-0x30]`(SysV) 또는 `lea rcx, [rbp-0x30]`(Windows)처럼, 그 함수가 받아야 할 것 같은 진짜 인자보다 먼저 스택 지역 변수의 **주소**를 첫 인자 레지스터에 로드하는 코드
- 함수 반환 후 `RAX`에 들어있는 값이 정수/포인터가 아니라, 방금 그 함수 호출 전에 넘겼던 스택 주소와 동일한 경우
- 함수 내부에서 `RDI`(또는 `RCX`)가 실제 계산에는 안 쓰이고, 오직 여러 필드에 `mov [rdi+0x0], ...`, `mov [rdi+0x8], ...` 형태로 결과를 써넣는 목적으로만 쓰인다
- 함수 시그니처를 문서/헤더로 알고 있는데, 실제 코드의 인자 레지스터 배치가 한 칸씩 밀려 있다

## 가장 먼저 할 것
1. 반환 타입이 큰 구조체(16바이트 초과, SysV 기준)인 함수를 만나면 우선 "숨은 포인터가 있을 수 있다"고 가정한다.
2. 호출 직전 첫 인자 레지스터(RDI/RCX)에 실제로 **스택 지역 변수 주소**(`lea`로 로드)가 들어가는지 확인한다.
3. 함수 내부에서 그 레지스터가 여러 필드 오프셋에 `mov`로 쓰이기만 하는지(읽지는 않는지) 확인한다.

## 단계별 절차

**1) 호출부에서 숨은 포인터 흔적 찾기**
```asm
lea   rdi, [rbp-0x30]   ; 반환값을 저장할 스택 공간 주소 (숨은 1번째 인자)
mov   esi, 1              ; 실제 소스상 1번째 인자 -> RSI로 밀림 (SysV)
mov   edx, 2              ; 실제 소스상 2번째 인자 -> RDX로 밀림
call  make_point
; 호출 후 RAX == rbp-0x30 (방금 넘긴 주소가 그대로 돌아옴)
```

**2) 함수 내부에서 필드 채우는 패턴 확인**
```asm
make_point:
    ; rdi = 반환값을 쓸 주소, rsi = x, rdx = y (예시)
    mov   [rdi], rsi        ; p.x = x
    mov   [rdi+8], rdx      ; p.y = y
    mov   rax, rdi           ; 관례: 그 주소를 RAX로도 반환
    ret
```

**3) 함수 시그니처 재구성**
알고 있던 소스 시그니처가 `Point3D make_point(double x, double y, double z)`였다면, 실제 어셈블리 레벨 시그니처는 `void make_point(Point3D *hidden_ret, double x, double y, double z)`로 재해석해야 인자/반환 매핑이 정확히 맞는다.

**4) 디컴파일러 원형과 대조**
IDA/Ghidra F5 결과가 숨은 포인터를 다시 감춰서 보여주는지, 아니면 그대로 노출하는지 확인하고, 노출된 경우 직접 위 분석으로 원래 시그니처를 재구성한다.

## 명령어/단축키
- IDA: 함수 위에서 `Y`(Set item type/함수 원형 변경)로 시그니처를 직접 수정해 sret 여부를 명시하면 디컴파일 결과가 더 읽기 쉬워진다
- Ghidra: 디컴파일 창에서 함수 시그니처 우클릭 → "Edit Function Signature"로 첫 파라미터를 숨김 처리하거나 반대로 노출 상태로 되돌릴 수 있다
- x64dbg/GDB: 호출 직전 `lea`가 로드하는 스택 주소를 기록해두고, 함수 반환 후 그 주소를 메모리 덤프로 확인(`dq <addr>` / `x/4gx <addr>`)해서 실제로 필드가 채워졌는지 검증

## 출력 해석
- 함수 반환 후 `RAX`가 함수 호출 전 계산했던 스택 주소와 동일하다 → 숨은 포인터 반환 관례가 지켜진 것이며, 그 스택 위치가 바로 반환된 구조체다.
- 함수 내부에서 첫 인자 레지스터가 계산에 전혀 관여하지 않고 오직 쓰기 목적지로만 쓰인다 → 그 레지스터가 실제 첫 인자가 아니라 숨은 반환 포인터라는 강한 신호다.

## 흔한 실수
- 숨은 포인터를 실제 함수의 1번째 인자로 착각해서 나머지 인자들을 전부 한 칸씩 잘못 읽는 것 — SysV에서 RDI가 아니라 RSI부터가 "진짜" 1번째 인자인 경우를 놓치는 게 대표적이다.
- "구조체 반환은 항상 RAX에 담긴다"고 일반화하는 것 — 이는 16바이트(SysV)/8바이트(Windows) 이하의 작은 구조체에서만 성립하며, 큰 구조체는 이 글에서 설명한 메모리 기반 반환을 쓴다.
- RVO(컴파일러 최적화)와 숨은 포인터(ABI 메커니즘)를 같은 것으로 혼동해서, "-O0으로 컴파일했으니 숨은 포인터도 없을 것"이라 착각하는 것 — 숨은 포인터 전달은 최적화 여부와 무관하게 ABI가 강제하는 규칙이다. 최적화 여부에 따라 달라지는 건 "복사가 생략되느냐"뿐이다.
- 반환값 주소가 힙이 아니라 호출자의 스택 프레임 안에 있다는 걸 놓치고, 함수가 끝난 뒤(스택 프레임이 해제된 뒤)에도 그 주소가 유효할 거라 착각하는 것 — 실제로는 호출자가 살아있는 동안만 유효하다.

## 막혔을 때 다음 체크
- 인자 레지스터 매핑이 계속 이상하면 → 반환 타입 크기부터 다시 계산해서(16바이트/8바이트 초과 여부) 숨은 포인터 여부를 먼저 확정한다.
- 어느 ABI(SysV/Windows x64)인지 헷갈리면 → 바이너리 포맷(ELF=SysV, PE=Windows x64)으로 먼저 판단한다.
- 디컴파일러가 이상하게 인자를 나열하면 → Ghidra/IDA에서 함수 원형을 수동으로 sret 형태로 수정해 다시 디컴파일해본다.

## 미니 예제

**예제 1 — SysV x64, 큰 구조체 반환**
```c
struct Point3D { double x, y, z; };  // 24바이트
struct Point3D make_point(double x, double y, double z);

struct Point3D p = make_point(1.0, 2.0, 3.0);
```
```asm
lea   rdi, [rbp-0x18]     ; 숨은 반환 포인터 (p의 주소)
movsd xmm0, [rip+const_1_0]
movsd xmm1, [rip+const_2_0]
movsd xmm2, [rip+const_3_0]  ; double 인자는 XMM0/1/2로 전달, RDI는 정수 인자 슬롯과 별개로 소모됨
call  make_point
; RAX == &p
```

**예제 2 — 함수 내부에서 필드 채우기**
```asm
make_point:
    movsd [rdi], xmm0       ; p.x = x
    movsd [rdi+8], xmm1      ; p.y = y
    movsd [rdi+16], xmm2     ; p.z = z
    mov   rax, rdi            ; 반환값 주소를 RAX로도 반환
    ret
```

**예제 3 — Windows x64, 작은 구조체는 레지스터 직접 반환 (대비)**
```c
struct Small { int a, b; };  // 8바이트, POD -> 레지스터 반환 가능
struct Small make_small(int a, int b) { return (struct Small){a, b}; }
```
```asm
make_small:
    mov   eax, ecx           ; a (1번째 인자, RCX)
    mov   ecx, edx            ; b (2번째 인자, RDX) -> 임시로 옮김
    shl   rcx, 32
    or    rax, rcx             ; {a, b}를 8바이트 RAX 하나에 패킹해서 반환 — 숨은 포인터 없음
    ret
```
(위는 개념 예시이며 실제 필드 패킹 방식은 컴파일러/구조체 정렬에 따라 다르다. 핵심은 8바이트 이하라 숨은 포인터가 아예 등장하지 않는다는 점이다.)

**예제 4 — 체이닝 시 RAX 재활용**
```c
print_point(make_point(1.0, 2.0, 3.0));
```
```asm
lea   rdi, [rbp-0x18]
...
call  make_point            ; RAX = &(rbp-0x18)
mov   rdi, rax                ; make_point의 반환 주소를 그대로 print_point의 인자로 재사용
call  print_point
```

## 관련 글
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0459 — 여러 조건(&&, ||)이 단축 평가로 컴파일되는 패턴
- REV-0031 — 스택 프레임이 무엇인지

## 출처/검증
- SysV AMD64 큰 구조체(16바이트 초과)의 메모리 기반 반환(MEMORY 분류) 규칙: System V Application Binary Interface AMD64 Architecture Processor Supplement, "Classification" 및 "Returning of Values" 섹션 기준.
- Microsoft x64의 구조체 반환 규칙(8바이트 이하 POD는 레지스터, 그 외는 hidden pointer): Microsoft Learn 공식 문서 "x64 calling convention", "Return Values" 섹션 기준.
- C++17 필수 복사 생략(mandatory copy elision) 및 RVO/NRVO 개념: ISO/IEC 14882 (C++17 표준) 및 cppreference "Copy elision" 기준. (2026-09-08 검증)
