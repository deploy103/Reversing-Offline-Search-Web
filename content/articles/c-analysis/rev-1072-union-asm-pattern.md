---
id: REV-1072
title: "union이 어셈블리에서 보이는 패턴"
slug: "rev-1072-union-asm-pattern"
category: "c-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["union 어셈블리", "union assembly pattern", "같은 주소 다른 타입 재해석", "type punning 어셈블리"]
aliases: ["union 디스어셈블 패턴", "union이 메모리에서 어떻게 보임", "구조체인데 필드가 겹침"]
symptom_keywords: ["같은 오프셋을 int로도 읽고 float로도 읽음", "union 멤버 접근을 구조체로 착각함", "movss와 mov가 같은 주소를 가리킴"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`union`의 모든 멤버는 오프셋 0에서 시작해 같은 메모리 공간을 공유하므로, 어셈블리에서는 "서로 다른 필드"가 아니라 "같은 주소를 다른 명령어/레지스터 종류(정수용 `mov` vs 실수용 `movss`/`movsd`)로 읽고 쓰는" 형태로 나타난다.

## 언제 검색해야 하나
- 구조체처럼 보이는 타입인데 멤버별로 오프셋이 다르지 않고 전부 `[rax]`, `[rax+0]`으로 같은 주소를 가리킬 때
- 같은 주소를 어떤 곳에서는 `mov eax, [rax]`(정수)로 읽고 다른 곳에서는 `movss xmm0, [rax]`(부동소수)로 읽어서 "복사 실수 아닌가?" 의심될 때
- IDA/Ghidra가 구조체 크기를 멤버들 크기의 합이 아니라 가장 큰 멤버 하나 크기로만 잡고 있을 때
- 네트워크 패킷/파일 포맷 파서에서 4바이트를 정수로도 읽고 바이트 배열로도 접근하는 코드가 같은 오프셋을 가리킬 때(type punning)

## 핵심 개념
구조체(`struct`)는 멤버마다 오프셋이 누적되어 커지지만, `union`은 모든 멤버가 오프셋 0을 공유하고 union 전체 크기는 "가장 큰 멤버의 크기"로 고정된다. 즉 union은 메모리 관점에서는 그냥 "고정된 크기의 바이트 블록을 여러 타입으로 재해석하겠다"는 컴파일러 지시일 뿐이며, 실행 시점에는 union이라는 개념 자체가 사라지고 그냥 하나의 주소에 대한 서로 다른 로드/스토어 명령어만 남는다.

```c
union Value {
    int   i;
    float f;
    char  bytes[4];
};

int reinterpret_as_int(union Value *v) {
    return v->i;
}

void set_as_float(union Value *v, float f) {
    v->f = f;
}
```

x86-64 SysV, `-O0`, Intel 문법:

```asm
reinterpret_as_int:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-8], rdi     ; v 저장
    mov     rax, [rbp-8]     ; rax = v
    mov     eax, [rax]       ; eax = *(int*)v  -- 오프셋 0에서 4바이트를 "정수"로 로드
    pop     rbp
    ret

set_as_float:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 8
    mov     [rbp-8], rdi      ; v 저장
    movss   [rbp-4], xmm0     ; f(부동소수 인자, xmm0로 전달됨)를 임시로 스택에 저장
    mov     rax, [rbp-8]      ; rax = v
    movss   xmm0, [rbp-4]     ; f를 다시 xmm0로 로드
    movss   [rax], xmm0       ; *(float*)v = f  -- 같은 오프셋 0에 "부동소수"로 저장
    leave
    ret
```

`reinterpret_as_int`는 `[rax]`를 `mov`(정수 레지스터)로 읽고, `set_as_float`는 정확히 같은 `[rax]`(오프셋이 항상 0)를 `movss`(SSE 부동소수 레지스터)로 쓴다. 두 함수의 유일한 차이는 "그 4바이트를 어떤 종류의 레지스터·명령어로 다루느냐"뿐이며, 주소 계산에는 어떤 차이도 없다 — 이것이 union의 어셈블리 상 정체다.

## 화면/코드에서 보이는 징후
- 여러 함수/코드 경로가 같은 포인터의 오프셋 0(또는 항상 동일한 고정 오프셋)을 대상으로 하는데, 명령어 종류(`mov` 계열 vs `movss`/`movsd` 계열, 또는 크기가 다른 `mov`/`movzx`)가 서로 다름
- 구조체 정의상 멤버가 3~4개인데 실제 구조체 크기(`sizeof`)가 멤버 개수와 안 맞고 가장 큰 멤버 하나 크기와 같음
- 같은 변수를 바이트 단위(`char bytes[4]`)로 순회하는 루프와, 그 변수를 정수 하나로 통째로 비교하는 코드가 같은 시작 주소를 공유함

## 가장 먼저 할 것
같은 주소에 대해 명령어 종류가 바뀌는 지점을 발견하면, 그 주소를 가리키는 변수/포인터의 타입을 union으로 재정의해서 본다. IDA/Ghidra에서 해당 변수 타입을 union으로 바꾸면 이후 pseudocode에서 `v.i`, `v.f` 식으로 자연스럽게 표시된다.

## 단계별 절차
1. 같은 주소(같은 오프셋)에 대해 서로 다른 크기/종류의 로드·스토어가 있는지 확인한다(정수 4바이트 vs 부동소수 4바이트 vs 바이트 배열 등).
2. 그 주소를 가리키는 포인터/변수가 구조체가 아니라 union일 가능성을 검토한다 — 특히 오프셋이 전부 0으로 동일하면 확정적이다.
3. IDA에서는 Local Types에 새 union을 정의하고 각 멤버 크기를 실제 사용된 크기와 맞춘 뒤, 변수에 `Y` 키(타입 변경)로 적용한다. Ghidra는 Data Type Manager → New → Union으로 동일하게 처리한다.
4. 타입을 적용한 뒤 pseudocode를 다시 보면 `mov`/`movss` 혼재가 `v.i = ...`, `v.f = ...` 형태로 정리되어 훨씬 읽기 쉬워진다.

## 명령어/단축키
- IDA: Local Types 창에서 union 정의, 변수 위에서 `Y`로 타입 지정
- Ghidra: Data Type Manager → New → Union, Retype Variable
- GDB: `p *(int*)&v` 로 정수 해석값, `p *(float*)&v` 로 부동소수 해석값을 같은 주소에서 각각 확인
- x64dbg: 메모리 덤프 창에서 같은 주소를 "Hex"와 "Float"로 동시에 다른 포맷으로 표시해 비교

## 출력 해석
`mov eax, [rax]`와 `movss xmm0, [rax]`가 완전히 같은 `rax` 값(같은 주소)을 대상으로 나타난다면, 그 값은 실제로는 4바이트짜리 원시 데이터일 뿐이고 프로그램이 상황에 따라 정수 또는 부동소수로 "재해석"하고 있다는 뜻이다. 이때 실제 비트 패턴은 하나뿐이므로, 정수로 읽은 값과 부동소수로 읽은 값은 서로 다른 숫자로 보이는 게 정상이다(IEEE 754 비트 표현과 2의 보수 정수 표현이 다르기 때문).

## 흔한 실수
- union 멤버 접근을 구조체 멤버 접근처럼 생각해서 "오프셋이 왜 다 0이지?"라고 헷갈리는 것.
- `mov`와 `movss`가 같은 주소를 가리키는 걸 보고 컴파일러 버그나 복붙 실수로 오해하는 것 — 실제로는 정상적인 type punning이다.
- union 크기를 멤버 크기의 합으로 잘못 계산하는 것(구조체는 합, union은 최댓값).
- `char bytes[4]`처럼 배열 멤버가 있는 union을 볼 때, 배열 인덱싱과 다른 멤버 접근이 전혀 다른 주소를 가리킨다고 착각하는 것(실제로는 `bytes[0]`이 `i`/`f`의 최하위 바이트와 같은 주소).

## 막혔을 때 다음 체크
- 같은 주소를 시프트/마스크로 잘라서 쓰는 것까지 겹쳐 있다면 → REV-1071 비트필드 구조체가 어셈블리에서 보이는 패턴
- union이 구조체 안에 멤버로 들어있어 오프셋이 0이 아니라 특정 값으로 고정되어 있다면 → REV-1060 구조체 필드 접근이 어셈블리에서 보이는 패턴(예정)
- union 값을 저장한 뒤 그 위치를 함수 인자로 다시 넘기는 흐름이 궁금하면 → REV-1062 포인터 역참조가 어셈블리에서 보이는 패턴

## 미니 예제
아래는 IPv4 주소를 4바이트 정수로도, 4개의 개별 바이트로도 다루는 실전형 union이다.

```c
union IPv4 {
    unsigned int  whole;
    unsigned char octet[4];
};

unsigned char get_first_octet(union IPv4 *ip) {
    return ip->octet[0];
}
```

```asm
get_first_octet:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-8], rdi      ; ip 저장
    mov     rax, [rbp-8]      ; rax = ip
    movzx   eax, BYTE [rax]   ; octet[0] = 오프셋 0에서 1바이트만 읽음 (whole의 최하위 바이트와 동일한 주소)
    pop     rbp
    ret
```

`octet[0]`을 읽는 코드는 `whole`을 읽는 코드(`mov eax, [rax]`, 4바이트 전체)와 시작 주소가 완전히 같고, 단지 `movzx ... BYTE`로 크기만 1바이트로 줄어든 것뿐이다. 이 한 줄만 보고도 "이 변수는 4바이트 정수와 바이트 배열이 겹쳐 있는 union이구나"라고 추론할 수 있다.

## 관련 글
- REV-0351 — Union이 메모리에서 어떻게 겹치는지
- REV-1071 — 비트필드 구조체가 어셈블리에서 보이는 패턴
- REV-1062 — 포인터 역참조가 어셈블리에서 보이는 패턴
- REV-1060 — 구조체 필드 접근이 어셈블리에서 보이는 패턴

## 출처/검증
- union의 모든 멤버가 오프셋 0을 공유하며 크기는 최대 멤버 크기라는 규칙: C 표준(ISO/IEC 9899) union 섹션 기준.
- 정수/부동소수 재해석이 정수 레지스터(`mov`)와 SSE 레지스터(`movss`/`movsd`) 명령어로 각각 나타난다는 점: System V AMD64 ABI(부동소수는 XMM 레지스터로 전달/처리) 및 실제 gcc/clang `-O0` 출력에서 반복 확인 (2026-09-10 검증).
