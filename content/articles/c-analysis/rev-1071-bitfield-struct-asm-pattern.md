---
id: REV-1071
title: "비트필드 구조체가 어셈블리에서 보이는 패턴"
slug: "rev-1071-bitfield-struct-asm-pattern"
category: "c-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["비트필드 어셈블리", "bitfield struct assembly pattern", "shr and shl 비트 추출", "구조체 비트필드 디스어셈블"]
aliases: ["비트필드 구조체 디스어셈블", "bitfield 어셈블리에서 어떻게 보임", "struct bit field 아니 int 하나만 있음"]
symptom_keywords: ["비트필드 접근을 어셈블리에서 못 알아봄", "구조체 멤버가 하나뿐인데 shr and 연산이 나옴", "필드 하나 읽는데 mov 대신 shr and가 나옴"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
C 비트필드(bit-field) 멤버는 실제로 메모리에 각자의 주소를 갖지 않고 하나의 정수(보통 `int`) 안에 비트 단위로 압축되어 있으므로, 어셈블리에서는 `mov`로 그 정수 전체를 읽은 뒤 `shr`(오른쪽 시프트)로 원하는 비트를 맨 아래로 내리고 `and`로 나머지 비트를 지워서 값을 꺼내고, 쓸 때는 `and`로 자리 비우고 `shl`+`or`로 끼워 넣는 식으로 컴파일된다.

## 언제 검색해야 하나
- 구조체 멤버 하나를 읽는 코드인데 `mov` 한 줄이 아니라 `shr eax, N` 다음에 `and eax, M` 같은 조합이 나와서 "이게 무슨 필드지?" 싶을 때
- IDA/Ghidra가 구조체를 인식하지 못하고 그냥 `int` 하나로 표시하는데, 실제 C 소스에는 `unsigned int flag : 1;` 처럼 비트필드가 선언되어 있을 때
- 값을 쓰는 코드에서 `and eax, 0xFFFFFF0F` 처럼 특정 비트만 0으로 만드는 상수가 나오고, 그다음 `or`로 새 값을 합치는 패턴을 볼 때
- CTF 문제에서 `flags` 같은 이름의 필드가 여러 개의 불(bool)/작은 정수 값을 한 변수에 압축해서 저장하고 있다고 의심될 때

## 핵심 개념
비트필드는 컴파일러가 알아서 여러 멤버를 한 저장 단위(storage unit, 보통 4바이트 `int`) 안에 쪼개 넣는 문법적 설탕이다. 링커/CPU 입장에서는 그런 멤버가 존재하지 않고, 그냥 하나의 정수에 대한 시프트와 마스크 연산만 존재한다.

```c
struct Flags {
    unsigned int a : 1;   /* bit 0 */
    unsigned int b : 3;   /* bit 1~3 */
    unsigned int c : 4;   /* bit 4~7 */
};

unsigned int get_b(struct Flags *f) {
    return f->b;
}

void set_b(struct Flags *f, unsigned int v) {
    f->b = v;
}
```

x86-64 SysV, `-O0`, Intel 문법:

```asm
get_b:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-8], rdi      ; f 저장
    mov     rax, [rbp-8]      ; rax = f
    mov     eax, [rax]        ; eax = 저장 단위 4바이트 전체 (a,b,c가 모두 들어있음)
    shr     eax, 1            ; b는 bit1에서 시작하므로 1비트 오른쪽으로 밀어 맨 아래로
    and     eax, 7            ; 0b111 마스크로 b가 차지하는 3비트만 남김
    pop     rbp
    ret

set_b:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-24], rdi     ; f 저장
    mov     [rbp-28], esi     ; v 저장
    mov     rax, [rbp-24]     ; rax = f
    mov     edx, [rax]        ; edx = 저장 단위 4바이트 (기존 a,b,c 값)
    mov     ecx, [rbp-28]     ; ecx = v
    and     ecx, 7            ; v의 하위 3비트만 사용 (b는 3비트니까)
    shl     ecx, 1            ; b 자리(bit1~3)에 맞춰 1비트 왼쪽으로 이동
    and     edx, -15          ; edx &= 0xFFFFFFF1, 기존 b 비트(1~3)를 0으로 클리어 (a,c는 보존)
    or      edx, ecx          ; 클리어된 자리에 새 b 값을 끼워 넣음
    mov     rax, [rbp-24]     ; rax = f (다시 로드)
    mov     [rax], edx        ; 수정된 4바이트 전체를 통째로 되씀
    pop     rbp
    ret
```

`get_b`는 "읽고 → 자리맞춤(shr) → 마스킹(and)" 두 단계, `set_b`는 "기존 값 읽기 → 새 값 마스킹+자리맞춤 → 기존 값에서 해당 자리 지우기(and) → 합치기(or) → 통째로 쓰기" 다섯 단계로 구성된다. 어느 쪽이든 필드 하나만 다루더라도 항상 저장 단위 전체(4바이트)를 대상으로 연산한다는 점이 핵심이다.

## 화면/코드에서 보이는 징후
- 멤버 하나를 읽는데 `mov`가 아니라 `shr`/`shl` 뒤에 `and`가 따라오는 짧은 명령어 묶음
- `and eax, N` 에서 `N`이 `1`, `3`, `7`, `0xF`, `0xFF` 같은 `2^n - 1` 형태의 수(비트 마스크)
- 값을 쓸 때 `and edx, -M` 처럼 음수 상수로 특정 비트만 0으로 지우는 연산 뒤에 `or`가 나옴
- 서로 다른 필드를 읽는 코드가 같은 주소 `[rax]`를 대상으로 하되 시프트 양(`shr 1`, `shr 4` 등)만 다름

## 가장 먼저 할 것
같은 포인터/주소에서 시프트 양이 다른 여러 `shr`+`and` 조합이 반복된다면 십중팔구 비트필드 구조체다. 각 조합의 시프트 값과 마스크 값을 적어 두면 `필드 시작 비트 = shr 값`, `필드 폭 = log2(mask+1)` 로 바로 역산할 수 있다.

## 단계별 절차
1. 문제가 되는 함수에서 `[rax]`, `[rcx+N]` 처럼 하나의 메모리 주소를 대상으로 하는 `shr`/`shl`/`and`/`or` 조합을 모두 모은다.
2. 각 조합의 `shr` 값을 필드 시작 비트로, `and` 마스크를 `2^폭 - 1` 형태로 놓고 필드 폭을 계산한다.
3. IDA에서는 해당 구조체 위에 커서를 놓고 `Alt+Q` 또는 Structures 창에서 새 struct를 만들고 비트필드로 멤버를 추가해 이름을 붙인다. Ghidra는 Data Type Manager에서 새 구조체를 만들고 필드 크기를 비트 단위로 지정한다.
4. 이름을 붙인 뒤 함수 전체를 다시 보며 `f->b` 같은 자연스러운 표현으로 재해석한다.

## 명령어/단축키
- IDA: 구조체 위에서 `Alt+Q` (변수를 구조체 포인터로 변환), Structures 창에서 비트필드 멤버 추가
- Ghidra: Data Type Manager → New → Structure, 필드 편집 시 크기(bit) 지정
- GDB: `p/x *(unsigned int*)ptr` 로 저장 단위 전체 값을 16진수로 확인, `p (val >> 1) & 7` 로 특정 필드 수동 추출
- x64dbg: 레지스터 창에서 `shr`/`and` 실행 전후 값을 단계 실행(F7)하며 직접 비교

## 출력 해석
`and eax, 7`은 하위 3비트만 남긴다는 뜻이므로 해당 필드 폭이 3비트임을 알려준다. `shr eax, 1`은 그 필드가 저장 단위의 bit 1에서 시작한다는 뜻이다. 두 정보를 합치면 필드가 "bit 1~3"을 차지한다고 확정할 수 있고, 이는 소스의 `unsigned int b : 3;` 선언(1비트짜리 `a` 다음에 옴)과 정확히 일치한다.

## 흔한 실수
- `shr`/`and` 조합을 그냥 "이상한 비트 연산"으로 치부하고 구조체라는 걸 눈치채지 못하는 것.
- 마스크 값을 `2^n - 1` 형태로 보지 않고 임의의 매직 넘버로 오해하는 것. `7`은 3비트, `0xF`는 4비트, `0xFF`는 8비트 마스크라는 감을 잡아야 한다.
- `set_b`처럼 쓰기 코드에서 `and edx, -15`(즉 `0xFFFFFFF1`) 같은 음수 상수를 보고 당황하는 것 — 이는 특정 비트 구간만 0으로 지우는 "클리어 마스크"이며 비트필드 쓰기의 표준 패턴이다.
- 필드 폭이 8/16/32비트 정렬에 딱 맞아 컴파일러가 `shr`/`and` 없이 그냥 `movzx`/`mov`로 처리하는 경우(바이트/워드 경계에 정확히 맞는 필드)까지 전부 비트필드로 확대 해석하는 것.

## 막혔을 때 다음 체크
- 이 정수와 겹치는 다른 타입 재해석이 섞여 있다면 → REV-1072 union이 어셈블리에서 보이는 패턴
- 시프트/마스크로 값을 만든 뒤 그 결과를 다시 필드에 누적 대입하는 형태라면 → REV-1080 복합 대입 연산자(+=, -=, *= 등)가 어셈블리에서 보이는 패턴
- 이 정수 필드가 구조체의 한 멤버일 뿐이고 다른 멤버 접근 패턴이 궁금하다면 → REV-1060 구조체 필드 접근이 어셈블리에서 보이는 패턴(예정)

## 미니 예제
아래는 세 개의 1비트 플래그를 압축한 구조체와, 그중 두 번째 플래그만 켜는 코드다.

```c
struct Perm {
    unsigned int read  : 1;  /* bit 0 */
    unsigned int write : 1;  /* bit 1 */
    unsigned int exec  : 1;  /* bit 2 */
};

void enable_write(struct Perm *p) {
    p->write = 1;
}
```

```asm
enable_write:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-8], rdi     ; p 저장
    mov     rax, [rbp-8]     ; rax = p
    mov     eax, [rax]       ; eax = 저장 단위 4바이트 전체
    or      eax, 2           ; write 비트(bit 1, 값 0b10=2)만 세팅, 나머지 비트는 그대로 유지
    mov     rdx, [rbp-8]     ; rdx = p (다시 로드)
    mov     [rdx], eax       ; 통째로 되씀
    pop     rbp
    ret
```

1비트 필드를 1로 "세팅"만 하는 경우는 기존 값을 지울 필요가 없으므로 `and` 없이 `or eax, 2` 한 줄로 끝난다. 반대로 0으로 "끄는" 코드라면 `and eax, -3`(즉 `0xFFFFFFFD`, bit 1만 지우는 마스크) 한 줄로 표현된다. 이 차이를 알아두면 `or`만 있는지 `and`만 있는지 `and`+`or`가 같이 있는지만 보고도 세팅/클리어/치환 연산인지 바로 구분할 수 있다.

## 관련 글
- REV-0352 — 비트필드(Bit-field) 구조체가 어셈블리로 변하는 방식
- REV-1072 — union이 어셈블리에서 보이는 패턴
- REV-1080 — 복합 대입 연산자(+=, -=, *= 등)가 어셈블리에서 보이는 패턴
- REV-1060 — 구조체 필드 접근이 어셈블리에서 보이는 패턴

## 출처/검증
- C 비트필드가 하나의 저장 단위(storage unit) 내에서 컴파일러 정의 순서/방향으로 배치된다는 규칙: C 표준(ISO/IEC 9899) 구조체 비트필드 섹션 및 System V AMD64 ABI 문서 기준.
- `shr`+`and`(읽기), `and`+`shl`+`or`(쓰기) 조합은 gcc/clang `-O0` x86-64 출력에서 반복적으로 확인되는 표준 코드 생성 패턴이다 (2026-09-10 검증).
