---
id: REV-0039
title: "MOV: 값 복사와 레지스터 메모리 이동"
slug: "rev-0039-mov"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - mov
  - MOV
  - Mov
  - mov instruction
  - mov 명령어
  - "mov rax rbx"
  - "mov eax ebx"
  - "mov eax, ebx"
  - "mov [rbp-4] eax"
  - "mov [rbp-0x10], eax"
  - "mov rax [rbp-8]"
  - "mov rax, [rbp-8]"
  - "mov dword ptr"
  - "mov qword ptr"
  - "mov word ptr"
  - "mov byte ptr"
  - movabs
  - 값 복사
  - 레지스터 이동
  - 메모리 이동
  - 데이터 이동
  - data movement
  - register to register
  - memory to register
  - register to memory
  - immediate to register
aliases:
  - mov 뭐임
  - mov가 뭐죠
  - mov 명령
  - MOV 명령어
  - 값 옮기기
  - 값 대입
  - 대입 명령어
  - 복사 명령어
symptom_keywords:
  - 레지스터에 값이 어디서 왔는지 모르겠음
  - mov가 플래그를 바꾸나요
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`MOV dst, src`는 "src 값을 dst에 복사"하는 명령어다. 이름은 이동(move)이지만 실제로는 **복사(copy)**다 — 실행 후에도 src 자리의 값은 그대로 남아있다.

## 언제 검색해야 하나
- 어셈블리를 처음 읽는데 `mov rax, rbx` 같은 코드가 계속 나와서 어느 쪽이 목적지고 어느 쪽이 출발지인지 헷갈릴 때
- `mov [rbp-4], eax`(메모리에 쓰기)와 `mov eax, [rbp-4]`(메모리에서 읽기)가 순서만 바뀌었는데 뜻이 정반대라 헷갈릴 때
- `mov eax, ebx` 실행 후 상위 64비트(RAX의 상위 32비트)가 어떻게 되는지 궁금할 때
- MOV 다음에 조건 분기가 나오는데 MOV가 플래그를 바꾸는 줄 알고 헷갈릴 때

## 핵심 개념

### 문법과 방향
Intel 문법(이 프로젝트 전체에서 사용하는 표기)은 항상:
```
MOV destination, source
```
**왼쪽이 목적지, 오른쪽이 출발지**다. `mov rax, rbx`는 "RBX의 값을 RAX에 복사"라는 뜻이며, C로 쓰면 `rax = rbx;`와 같다. (AT&T 문법은 반대로 `mov src, dst`이지만 이 사전은 Intel 문법만 다룬다.)

### 가능한 오퍼랜드 조합
- 레지스터 ← 레지스터: `mov eax, ecx`
- 레지스터 ← 메모리: `mov eax, [rbp-0x10]` (메모리에서 읽기)
- 메모리 ← 레지스터: `mov [rbp-0x10], eax` (메모리에 쓰기)
- 레지스터 ← 즉시값(상수): `mov eax, 5`
- 메모리 ← 즉시값: `mov dword ptr [rax], 0`

**메모리 ← 메모리는 불가능하다.** x86/x64 명령어 인코딩상 MOV는 오퍼랜드 두 개 중 하나만 메모리일 수 있다. 메모리에서 메모리로 값을 옮기려면 반드시 레지스터를 거쳐야 한다:
```asm
mov eax, [rsi]   ; 먼저 레지스터로 읽고
mov [rdi], eax   ; 그 다음 메모리에 쓴다
```

### 오퍼랜드 크기와 ptr 지정자
두 오퍼랜드의 크기(바이트 수)는 반드시 같아야 한다. 레지스터끼리는 이름 자체가 크기를 정한다(`al`=1바이트, `ax`=2바이트, `eax`=4바이트, `rax`=8바이트). 메모리 오퍼랜드는 크기가 문맥상 애매할 수 있어서 `byte ptr`, `word ptr`, `dword ptr`, `qword ptr`로 명시한다.
```asm
mov byte  ptr [rbx], 1     ; 1바이트만 씀
mov dword ptr [rbx], 1     ; 4바이트 씀
```

### x64에서 32비트 레지스터에 쓰면 상위 32비트가 0으로 클리어된다
이것이 x64에서 초보자가 가장 자주 놓치는 규칙이다. `eax`, `ecx` 같은 **32비트 레지스터에 값을 쓰면, 해당 64비트 레지스터(`rax`, `rcx`)의 상위 32비트가 자동으로 0으로 지워진다.**
```asm
mov rax, 0FFFFFFFFFFFFFFFFh   ; RAX = 전부 1
mov eax, 1                     ; 이제 RAX = 0x0000000000000001 (상위 32비트가 날아감!)
```
반면 **16비트(`ax`)나 8비트(`al`, `ah`) 레지스터에 쓰는 것은 상위 비트를 보존**한다(부분 레지스터 쓰기 — 이전 값 위에 덮어씀). 이 비대칭이 x64 설계 특성이며, 컴파일러가 `mov eax, ...` 형태를 자주 쓰는 이유이기도 하다(레지스터 전체를 깔끔하게 초기화하고 싶을 때).

### 플래그: 전혀 바꾸지 않는다
**MOV는 EFLAGS/RFLAGS를 단 하나도 바꾸지 않는다.** ZF, CF, SF, OF, PF, AF 전부 실행 전 값 그대로 유지된다. 그래서 `mov` 다음에 `jz`/`jnz` 같은 조건 분기가 나오면, 그건 MOV가 만든 플래그가 아니라 **그 이전에 실행된 `cmp`나 `test` 같은 명령이 남긴 플래그**를 보는 것이다. 이걸 착각하면 분기 조건을 완전히 잘못 해석하게 된다.

### RIP 상대 주소 (x64)
x64에서는 전역 변수 접근 시 `mov eax, [rip+0x2f10]`처럼 RIP(다음 명령 주소) 기준 상대 오프셋을 쓰는 경우가 매우 흔하다. 이는 위치 독립 코드(PIE/ASLR 대응)를 만들기 위한 패턴이다. IDA는 이런 걸 자동으로 `mov eax, cs:dword_140003000` 식으로 실제 주소를 계산해서 보여준다.

### MOV vs LEA 혼동 주의
`mov eax, [rbx]`는 RBX가 **가리키는 메모리 위치의 값**을 읽는다(역참조). 반면 `lea eax, [rbx]`는 RBX 자체가 아니라 `[rbx]`라는 **주소 계산식의 결과**(사실상 RBX 값 자체 또는 RBX+오프셋)를 레지스터에 넣는다 — 메모리 접근이 아예 없다. 자세한 내용은 [LEA](./rev-0042-lea.md) 문서 참고.

## 화면/코드에서 보이는 징후
- `mov eax, ebx` — 레지스터 간 복사
- `mov [rbp-0x10], eax` — 지역 변수에 값 저장
- `mov eax, [rbp-0x10]` — 지역 변수 값을 읽기
- `mov dword ptr [rax+4], 0` — 구조체 필드/배열 원소를 0으로 초기화
- `mov ecx, 0FFFFFFFFh` — 상수 로드
- IDA/Ghidra 디컴파일에서는 MOV 자체가 눈에 안 보이고 `v2 = v3;`, `a1->field = 0;` 같은 대입문으로 흡수되어 표현되는 경우가 대부분이다.

## 가장 먼저 할 것
1. 왼쪽이 목적지, 오른쪽이 출발지임을 확인한다.
2. 레지스터인지, `[...]`로 감싸인 메모리인지, 그냥 숫자(즉시값)인지 구분한다.
3. 오퍼랜드 크기(`byte/word/dword/qword`)를 확인한다.
4. 목적지가 32비트 레지스터라면 상위 64비트가 클리어된다는 점을 염두에 둔다.

## 단계별 절차
**1) 방향 판단**
```asm
mov rdi, rax   ; RAX -> RDI 로 복사 (RDI가 바뀜, RAX는 그대로)
```
**2) 메모리 읽기/쓰기 구분**
```asm
mov eax, [rbp-0x8]    ; 읽기: 스택의 지역변수 값을 EAX로 가져옴
mov [rbp-0x8], eax    ; 쓰기: EAX 값을 스택의 지역변수에 저장
```
**3) 상위 비트 클리어 여부 확인**
```asm
mov rax, 1122334455667788h
mov eax, 0AABBCCDDh     ; RAX = 0x00000000AABBCCDD (상위 32비트 사라짐)
```
**4) 플래그와 무관함을 확인**
```asm
cmp eax, 10        ; 여기서 플래그가 세팅됨
mov ecx, 0         ; MOV는 플래그를 안 건드림 - ZF 등 여전히 cmp 결과 유지
jz  label          ; 이 jz는 mov가 아니라 위 cmp의 결과를 본다
```

## 명령어/단축키
- IDA: 레지스터 창(디버깅 중 자동 표시)에서 MOV 실행 전/후 값 비교, `F5`로 디컴파일하면 대입문으로 단순화되어 표시
- x64dbg: 레지스터 패널에서 실시간 값 확인, 값이 바뀐 레지스터는 빨간색으로 강조 표시됨
- GDB/Pwndbg: `info registers` 또는 `i r rax`로 특정 레지스터 값 확인, `x/4xb $rbp-0x10`으로 메모리 값 확인

## 출력 해석
- 디버거 레지스터 창에서 `mov eax, 1` 실행 직후 RAX 전체가 `0x0000000000000001`로 바뀌어 있으면, 32비트 쓰기의 상위 클리어 규칙이 적용된 것이다.
- `mov` 실행 전후로 플래그 레지스터(EFL/RFLAGS) 값이 한 비트도 안 바뀌었다면 정상이다 — MOV는 플래그 불변.
- IDA 디컴파일에서 여러 개의 MOV가 사라지고 `struct.field = local_var;` 하나로 합쳐져 보이는 건 컴파일러 최적화/IDA의 표현 단순화이지, 원본 어셈블리에 MOV가 없었다는 뜻이 아니다.

## 흔한 실수
- **"이동"이라는 이름 때문에 원본이 사라진다고 착각**하는 것 — 실제로는 복사이며 src 값은 그대로 남는다.
- **메모리에서 메모리로 바로 옮길 수 있다고 착각**하는 것 — 반드시 레지스터를 거쳐야 한다(mem→mem 인코딩 자체가 없음).
- **32비트 레지스터에 쓸 때 상위 32비트가 그대로 남을 거라 착각**하는 것 — `mov eax, ...`는 RAX 상위 32비트를 0으로 지운다. (반대로 `mov ax, ...`/`mov al, ...`는 상위 비트를 보존한다.)
- **MOV가 플래그를 바꾼다고 착각**해서 MOV 다음의 조건 분기를 MOV 결과로 해석하는 것 — 항상 그 앞의 `cmp`/`test`/산술 명령을 찾아야 한다.
- MOV와 [LEA](./rev-0042-lea.md)를 혼동하는 것 — `mov eax, [rbx]`는 메모리를 읽고, `lea eax, [rbx]`는 주소만 계산한다(메모리 접근 없음).

## 막혔을 때 다음 체크
- 오퍼랜드 크기가 안 맞아 이상해 보이면 → `byte/word/dword/qword ptr` 지정자를 다시 확인한다.
- 디스어셈블리에서 `movzx`나 `movsx`처럼 보이는데 그냥 `mov`인 줄 알았다면 → mnemonic 전체 철자를 다시 본다([MOVZX](./rev-0040-movzx.md), [MOVSX](./rev-0041-movsx-movsxd.md) 참고).
- MOV 다음 분기 조건이 이해 안 되면 → MOV가 아니라 그 이전 `cmp`/`test`를 찾는다.

## 미니 예제

**예제 1 — 레지스터 간 복사**
```c
int b = a;
```
```asm
mov eax, [rbp-0x4]   ; eax = a
mov [rbp-0x8], eax   ; b = eax
```

**예제 2 — 상수 초기화**
```c
int x = 0;
```
```asm
mov dword ptr [rbp-0x4], 0
```

**예제 3 — 포인터 역참조 읽기/쓰기**
```c
*p = *q;
```
```asm
mov rax, [rbp-0x10]   ; rax = q (포인터 값)
mov rax, [rax]         ; rax = *q (역참조)
mov rcx, [rbp-0x18]   ; rcx = p
mov [rcx], rax         ; *p = rax
```

**예제 4 — 32비트 쓰기로 인한 상위 비트 클리어**
```asm
mov rax, 0FFFFFFFFFFFFFFFFh  ; RAX 전체 1
mov eax, 0                    ; RAX = 0 (상위 32비트도 함께 0)
```

## 관련 글
- [MOVZX: Zero Extension 이해](./rev-0040-movzx.md)
- [MOVSX와 MOVSXD: Sign Extension 이해](./rev-0041-movsx-movsxd.md)
- [LEA: 주소 계산인데 왜 산술 연산처럼 보이는가](./rev-0042-lea.md)
- [XCHG: 두 값 교환](./rev-0043-xchg.md)
- [PUSH: 스택에 값 넣기](./rev-0044-push.md)
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)

## 출처/검증
- MOV 명령어 동작 및 32비트 쓰기 시 상위 비트 클리어 규칙: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "MOV—Move" 섹션 기준 (2026-09-08 검증).
- MOV가 플래그에 영향을 주지 않는다는 점: 위 문서의 "Operation"/"Flags Affected" 절 기준.
