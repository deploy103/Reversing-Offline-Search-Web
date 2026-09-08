---
id: REV-0440
title: "SIB 바이트로 복잡한 주소 지정 읽는 법"
slug: "rev-0440-sib-byte-addressing"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - SIB byte
  - SIB 바이트
  - Scale Index Base
  - "[base+index*scale]"
  - "rbx+rcx*4"
  - scale factor
  - 배열 인덱스 주소 지정
  - 복합 주소 지정
  - "rax+rax*4"
  - addressing mode x64
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - sib바이트가 뭐임
  - "base+index*scale이 뭐임"
  - 스케일 인덱스 베이스
  - 배열 주소 계산 어셈블리
  - "rax+rax*4가 뭐임"
symptom_keywords:
  - "[rbx+rcx*4]가 뭔지 모르겠음"
  - 배열 인덱스 어셈블리 해석이 안 됨
  - scale이 4 8인 이유를 모르겠음
  - lea로 곱셈하는 이유를 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`[base + index*scale + disp]` 형태의 주소는 SIB(Scale-Index-Base) 바이트로 인코딩되며, 배열/구조체 배열 접근(`arr[i]`)을 나타내는 가장 흔한 패턴이자 컴파일러가 `*3`, `*5`, `*9` 같은 곱셈을 `LEA` 트릭으로 대체할 때도 쓰인다.

## 언제 검색해야 하나
- `mov eax, [rbx+rcx*4]`, `lea rax, [rax+rax*4]` 같은 코드에서 `*4`, `*8` 같은 숫자가 왜 붙어있는지, 어느 게 base고 어느 게 index인지 헷갈릴 때
- `arr[i]` 형태의 C 배열 접근이 어셈블리에서 어떻게 보이는지 확인하고 싶을 때
- `lea rax, [rax+rax*4]`처럼 곱셈(`IMUL`) 없이 갑자기 `LEA`로 값을 5배 만드는 코드를 만났을 때
- 구조체 배열(`arr[i].field`)처럼 스케일이 1/2/4/8이 아닌 경우 어셈블리가 왜 더 복잡해지는지 궁금할 때

## 핵심 개념

### SIB 바이트란
x86/x64 명령어 인코딩에서 ModRM 바이트만으로는 "레지스터 하나 + 고정 변위"만 표현할 수 있다. `base + index*scale + displacement`처럼 두 개의 레지스터를 조합하는 복잡한 주소가 필요할 때, ModRM 뒤에 **SIB(Scale-Index-Base) 바이트**가 추가로 붙는다. SIB는 3개 필드로 이루어진다.
```
비트 7-6: Scale (2비트)  → 곱셈 배수: 00=1, 01=2, 10=4, 11=8
비트 5-3: Index (3비트, x64는 REX.X로 1비트 확장) → 인덱스로 쓸 레지스터
비트 2-0: Base  (3비트, x64는 REX.B로 1비트 확장) → 기준 주소로 쓸 레지스터
```
실효 주소 계산식은 다음과 같다.
```
실효 주소 = Base 레지스터 값 + (Index 레지스터 값 × Scale) + Displacement
```
Scale은 하드웨어 수준에서 **1, 2, 4, 8 네 가지만** 가능하다(각각 byte, word/short, dword/int, qword/pointer 크기와 자연스럽게 대응). 그 외의 배수(3, 5, 6, 9, 24 등)는 SIB 하나로 표현할 수 없다.

### 왜 이 방식이 배열 접근의 표준 패턴인가
C의 `int arr[N]`에서 `arr[i]`는 `*(arr + i*4)`와 같다(int 크기가 4바이트이므로). 이건 정확히 `[base + index*scale]` 구조와 일치한다.
```c
int v = arr[i];
```
```asm
mov     eax, [rbx + rcx*4]   ; rbx = arr의 시작 주소(base), rcx = i(index), scale=4(sizeof(int))
```
`char` 배열이면 `scale=1`, `short`면 `scale=2`, `long`/포인터 배열이면 `scale=8`이 자연스럽게 대응된다. 그래서 SIB의 `*4`, `*8` 숫자만 봐도 원소 크기(따라서 대략적인 타입)를 짐작할 수 있다.

### 구조체 배열처럼 스케일이 1/2/4/8이 아닐 때
`struct Item { ... };` 크기가 24바이트인 배열 `items[i]`처럼 원소 크기가 1/2/4/8이 아니면, SIB 하나로는 표현이 안 되므로 컴파일러는 **먼저 인덱스에 원소 크기를 곱하는 명령**(IMUL 또는 LEA 조합)을 넣고, 그 결과를 base로 다시 조합한다.
```asm
; items[i].field,  sizeof(Item) = 24
imul    rax, rcx, 24        ; rax = i * 24  (IMUL로 직접 곱셈, REV-0051 참고)
mov     edx, [rbx+rax+8]    ; items 시작(rbx) + i*24(rax, base로 재활용) + field 오프셋(8)
```
여기서는 `imul` 결과 레지스터(`rax`)가 SIB의 base 자리로 들어가고, disp(`+8`)가 구조체 멤버 오프셋을 담당한다.

### LEA와 결합한 곱셈 트릭: `*3`, `*5`, `*9`
SIB의 `base`와 `index`가 **같은 레지스터**를 가리켜도 되기 때문에, 컴파일러는 곱셈 명령(`IMUL`, 비교적 느림) 대신 `LEA`(주소 계산이지만 사실상 산술 연산, REV-0042 참고) 한 줄로 특정 상수배를 만드는 트릭을 자주 쓴다.
```asm
lea     rax, [rax+rax*2]   ; rax = rax + rax*2 = rax*3
lea     rax, [rax+rax*4]   ; rax = rax*5
lea     rax, [rax+rax*8]   ; rax = rax*9
lea     rax, [rax*4]       ; rax = rax*4  (base 없이 index*scale만)
lea     rax, [rax*8+rax]   ; 위와 같은 rax*9를 표기 순서만 바꿔 쓴 것
```
이건 배열 접근이 아니라 **정수 곱셈 최적화**의 흔적이지만, SIB 인코딩(`base+index*scale`)을 그대로 재활용한다는 점에서 같은 주소 지정 방식을 이해하고 있어야 알아볼 수 있다.

### 레지스터 제약: ESP/RSP는 index가 될 수 없다
x86/x64 인코딩 규칙상 **ESP/RSP는 SIB의 index 필드에 올 수 없다**(index=100 조합은 "인덱스 없음"을 뜻하는 특수 값으로 예약되어 있다). 즉 `[rsp+rax*4]`처럼 RSP가 base로 쓰이는 코드는 흔하지만(스택에 있는 지역 배열 접근), `[rax+rsp*4]`처럼 RSP가 index로 쓰이는 코드는 나오지 않는다. 이 규칙 때문에 스택 지역 배열은 항상 RSP/RBP가 base 자리에 있는 형태로만 나타난다.

### 플래그와 signed/unsigned
주소 계산 자체는 플래그를 바꾸지 않는다. 다만 index로 쓰이는 레지스터가 **signed 인덱스**(음수 인덱스 접근 가능, 배열 경계를 넘어 이전 메모리를 가리킬 수 있음)인지 **unsigned로 취급되도록 zero-extend된 값**(`movzx eax, cl` 후 index로 사용)인지 구분하는 것이 중요하다. `int i`가 signed면 `movsxd rcx, edi` 같은 부호 확장이 index 계산 전에 선행되는 패턴이 자주 보인다(REV-0041 MOVSX/MOVSXD 참고).

### 컴파일러 패턴과 디컴파일러 화면
IDA/Ghidra는 SIB 기반 주소를 대부분 잘 인식해서, 배열 타입 정보가 있으면 `arr[i]`처럼, 없으면 `*(int *)(base + i * 4)`처럼 재구성해 보여준다. 구조체 배열 접근은 `items[i].field`로 깔끔하게 보여주기도 하지만, IDA가 구조체 타입을 모르면 `*(int *)(base + i*24 + 8)`처럼 원시 산술식 그대로 노출한다 — 이 경우 리버서가 직접 구조체를 정의(Structs 창, Alt+T 또는 "Create struct")해주면 이후 모든 접근이 자동으로 깔끔해진다.

### 리버싱 관점에서의 의미
SIB 표기(`[base+index*scale+disp]`)를 보면 즉시 "배열 또는 배열형 데이터 접근"이라고 판단할 수 있고, scale 값으로 원소 크기(1/2/4/8바이트)를 추정할 수 있다. index가 없고 base+disp만 있으면(`[rdi+0x18]`) 이건 배열이 아니라 **고정된 구조체 멤버 접근**일 가능성이 높다 — 이 구분만으로도 "이게 배열 순회 코드인지, 아니면 단일 객체의 필드 접근인지"를 빠르게 판단할 수 있다.

## 화면/코드에서 보이는 징후
- `[base+index*4]`, `[base+index*8]` 같은 `*숫자`가 붙은 메모리 오퍼랜드
- `lea reg, [reg+reg*N]` 형태로 곱셈 명령(`imul`) 없이 값이 N+1배로 계산되는 코드
- `imul` 뒤에 곧바로 그 결과 레지스터가 다른 명령의 base로 재사용되는 패턴(스케일이 1/2/4/8이 아닌 구조체 배열)
- `[rsp+idx*4]`, `[rbp+idx*8]`처럼 스택 포인터가 base로 쓰이는 지역 배열 접근

## 가장 먼저 할 것
1. 오퍼랜드에서 `*` 뒤 숫자(scale)를 확인해 원소 크기를 추정한다(1=byte, 2=short, 4=int/float, 8=long/pointer/double).
2. base와 index 중 어느 쪽이 "고정된 시작 주소"이고 어느 쪽이 "반복문 변수"인지 문맥으로 판단한다.
3. `lea`로 시작하는데 결과가 메모리 값이 아니라 계산값처럼 쓰인다면, 배열 접근이 아니라 곱셈 트릭인지 먼저 의심한다.

## 단계별 절차
1. `[base+index*scale+disp]` 형태에서 base/index/scale/disp 네 요소를 각각 식별한다.
2. scale(1/2/4/8)로 배열 원소 크기를 추정한다 — 4면 int/float, 8이면 long/double/포인터일 가능성이 높다.
3. index가 없고 base+disp만 있으면 배열이 아니라 구조체 멤버 접근으로 잠정 판단한다.
4. IDA/Ghidra에서 구조체 타입을 알고 있다면 Structs 정의 후 재해석해서 `arr[i]`/`obj.field` 형태로 깔끔하게 바꿔본다.

## 명령어/단축키
- IDA: 배열로 추정되는 데이터에 `*` 키(Array)를 눌러 배열로 정의하면 이후 SIB 기반 접근이 `arr[i]`로 자동 정리된다.
- x64dbg: 디스어셈블리에서 오퍼랜드를 우클릭 → "Follow in Dump"로 base 주소부터 실제 배열 데이터를 눈으로 확인.
- GDB/Pwndbg: `x/10gx $rbx`처럼 base 레지스터 기준으로 배열 전체를 덤프해서 index별 값을 한 번에 확인.

## 흔한 실수
- scale이 1/2/4/8 외의 임의의 수라고 착각하는 것 — SIB 하드웨어 인코딩은 이 네 값만 지원하며, 다른 배수는 별도의 곱셈 명령으로 만들어진다.
- `[rax+rcx*4]`에서 어느 게 base고 어느 게 index인지 헷갈리는 것 — `*scale`이 붙은 쪽이 index, 안 붙은 쪽이 base다.
- `lea rax, [rax+rax*4]` 같은 코드를 "배열 접근"으로 오인하는 것 — 이건 배열이 아니라 상수 곱셈(`*5`) 최적화 관용구다. LEA의 목적지가 메모리를 읽지 않고 값만 계산해서 레지스터에 넣는다는 점(REV-0042)을 떠올리면 구분이 쉽다.
- ESP/RSP가 index로 쓰일 수 없다는 인코딩 제약을 모른 채, 스택 관련 주소 패턴을 임의로 예상하는 것.

## 막혔을 때 다음 체크
- RIP 기준 주소와 결합된 형태(`[rip+disp]`에 인덱스까지)가 헷갈리면 → REV-0439.
- 배열 접근이 소스 레벨에서 어떻게 이런 형태로 컴파일되는지 전체 흐름이 궁금하면 → REV-0034.
- 인덱스 레지스터의 부호 확장 과정이 궁금하면 → REV-0041(MOVSX/MOVSXD).

## 미니 예제

**예제 1 — int 배열 인덱싱**
```c
int v = arr[i];
```
```asm
mov     eax, [rbx+rcx*4]   ; rbx=arr, rcx=i, scale=4(sizeof(int))
```

**예제 2 — LEA 곱셈 트릭 (`x*5`)**
```c
int y = x * 5;
```
```asm
lea     eax, [rax+rax*4]   ; eax = rax + rax*4 = rax*5, IMUL 없이 곱셈 수행
```

**예제 3 — 구조체 배열 + 필드 접근**
```c
int v = ptrs[i]->field;   // ptrs: 8바이트 포인터 배열
```
```asm
mov     rdx, [rdi+rcx*8]    ; ptrs[i] (포인터 값 자체를 읽음, scale=8)
mov     eax, [rdx+0x10]     ; ptrs[i]->field (그 포인터가 가리키는 곳 + 오프셋)
```

**예제 4 — byte 배열, scale=1**
```asm
movzx   eax, byte ptr [rsi+rdx*1]   ; byte 배열 접근, scale 1은 흔히 생략되어 [rsi+rdx]로도 표기됨
```

## 관련 글
- REV-0439 — RIP 상대 주소 지정 방식(RIP-relative addressing)
- REV-0042 — LEA: 주소 계산인데 왜 산술 연산처럼 보이는가
- REV-0034 — 배열 접근이 어셈블리로 변하는 방식
- REV-0041 — MOVSX와 MOVSXD: Sign Extension 이해
- REV-0051 — IMUL: Signed 곱셈과 컴파일러 패턴

## 출처/검증
- SIB 바이트 인코딩(Scale/Index/Base 필드, index=100 예약)과 ESP/RSP index 제약: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "2.1.5 Addressing-Mode Encoding of ModR/M and SIB Bytes" 기준 (2026-09-08 검증).
