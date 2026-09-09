---
id: REV-0353
title: "전역 변수와 지역 변수를 메모리 위치로 구분하는 법"
slug: "rev-0353-global-vs-local-variable-location"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["전역 변수", "지역 변수", "global variable", "local variable", "rip relative", "rbp relative", ".data", ".bss", "스택 변수"]
aliases: ["rip+offset이 뭔가요", "rbp-8이 뭔가요", "전역변수와 지역변수를 어떻게 구분하나요", "static 변수가 어셈블리에서 어떻게 보이나요"]
symptom_keywords: ["rip 상대 주소가 왜 나오는지 모르겠음", "rbp-0x10과 rip+0x2f5c 차이를 모르겠음", "이 변수가 전역인지 지역인지 어셈블리만 보고 모르겠음", "재귀 호출인데 변수 값이 유지되는 이유를 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
전역 변수(global)는 `.data`/`.bss` 섹션의 **고정된 절대 주소**를 갖고 프로그램 실행 내내 그 자리에 그대로 있어 `rip`(x64) 또는 고정 상수 주소로 접근되지만, 지역 변수(local)는 함수가 호출될 때마다 새로 마련되는 **스택 프레임 안의 상대 위치**(`rbp-N`, `rsp+N`)로 접근되므로, "베이스가 `rip`(고정 데이터)인지 `rbp`/`rsp`(그때그때 다른 스택 프레임)인지"만 보면 두 종류를 즉시 구분할 수 있다.

## 언제 검색해야 하나
- 어셈블리에 `mov eax, [rip + 0x2f5c]`처럼 `rip` 기준 상대 주소가 나오는데 이게 지역 변수 접근(`rbp-0x10`)과 뭐가 다른지 헷갈릴 때
- 함수를 재귀 호출했는데 어떤 변수는 호출마다 초기화되고 어떤 변수는 값이 계속 누적되어서, 소스 코드 없이 이게 지역/전역/`static` 중 뭔지 알아내야 할 때
- IDA 디컴파일 결과에 `dword_404050`처럼 함수 밖에서 정의된 변수와 `v1`, `a1` 같은 함수 안에서만 쓰이는 변수가 섞여 있는데 왜 이렇게 다르게 표시되는지 궁금할 때
- 멀티스레드 프로그램을 분석하다가 "이 변수는 스레드마다 다른 값을 가질 수 있는지"를 어셈블리 레벨에서 판단해야 할 때

## 핵심 개념

### 결정적 차이 — "주소가 고정인가, 매번 계산되는가"
전역 변수는 컴파일/링크 시점에 이미 메모리 주소가 확정된다. 프로그램이 실행되는 동안(ASLR이 있어도 베이스 오프셋만 바뀔 뿐 상대 위치는 고정) 그 변수는 항상 같은 상대 위치에 존재한다. 반면 지역 변수는 함수가 호출될 때마다 스택 위에 "새로" 자리를 배정받으며, 함수가 리턴하면 그 공간은 사라진다(REV-0031 스택 프레임). 그래서 지역 변수의 주소는 "이번 호출의 스택 포인터/베이스 포인터 기준 상대 위치"로만 의미가 있다.

### x64에서 전역 변수 접근 — RIP-상대 주소 지정(RIP-relative addressing)
x64에서는 위치 독립 코드(PIE, Position Independent Executable)를 지원하기 위해, 전역 변수/상수 접근에 `rip`(현재 명령어 포인터) 기준 상대 주소를 흔히 쓴다.
```c
int counter = 0;      // 전역 변수

void increment(void) {
    counter++;
}
```
```asm
increment:
    mov     eax, [rip + 0x2ee5]   ; counter 읽기 (rip + 고정 오프셋 = counter의 실제 주소)
    add     eax, 1
    mov     [rip + 0x2ee5], eax    ; counter에 다시 씀
    ret
```
`[rip + 0x2ee5]`가 가리키는 실제 주소는 "이 명령어 다음 명령어의 주소 + 0x2ee5"로 계산되는데, 이 값은 프로그램이 몇 번을 다시 실행하든 **바이너리 안에서는 항상 동일한 상대 오프셋**이다(ASLR로 전체 프로그램이 메모리 어디에 로드되든, `rip`와 데이터의 상대 거리는 링크 시점에 고정되어 있으므로 변하지 않는다). IDA/Ghidra는 이런 참조를 자동으로 실제 심볼 이름(`counter`)이나 `dword_404050` 같은 주소 기반 이름으로 보여준다.

x86(32비트)나 PIE가 아닌 바이너리에서는 `rip` 상대 대신 그냥 **절대 주소 상수**를 직접 쓴다.
```asm
mov     eax, [0x00404050]   ; counter (절대 주소, 32비트 또는 non-PIE x64)
```
어느 형태든 공통점은 **오프셋/주소가 상수(리터럴)이며 레지스터 값에 의존하지 않는다**는 것이다.

### 지역 변수 접근 — 스택 프레임 상대 주소
지역 변수는 함수 진입 시 확보된 스택 공간 안에서 `rbp`(또는 최적화된 경우 `rsp`) 기준 오프셋으로 접근한다(REV-0031).
```c
void increment_local(void) {
    int local_counter = 0;
    local_counter++;
}
```
```asm
increment_local:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     dword [rbp-4], 0     ; local_counter = 0
    mov     eax, [rbp-4]
    add     eax, 1
    mov     [rbp-4], eax          ; local_counter++
    leave
    ret
```
`[rbp-4]`는 "이번 함수 호출의 스택 프레임 시작점에서 4바이트 아래"라는 **상대적인** 위치다. 이 함수를 두 번 호출하면 `rbp` 값 자체는 매번 다르지만(스택 포인터가 호출마다 다른 실제 주소를 가리킴), 오프셋 `-4`는 항상 똑같다 — 이것이 핵심이다. **레지스터(`rbp`/`rsp`)를 기준으로 한 상대 오프셋으로 접근하면 지역 변수, 고정 주소/`rip` 상대 오프셋으로 접근하면 전역 변수**라는 규칙이 성립한다.

### static 지역 변수 — "지역처럼 선언, 전역처럼 저장"
C의 `static` 지역 변수는 함수 안에서 선언되지만 실제 메모리는 전역 변수와 똑같이 `.data`/`.bss`에 고정 배치된다.
```c
void counter_static(void) {
    static int count = 0;   // static 지역 변수
    count++;
}
```
```asm
counter_static:
    mov     eax, [rip + 0x2ee0]   ; count 읽기 (rbp 상대가 아니라 rip 상대!)
    add     eax, 1
    mov     [rip + 0x2ee0], eax
    ret
```
이 함수는 지역 변수처럼 보이는 `count`를 다루지만, 어셈블리는 **전역 변수와 완전히 동일한 패턴(`rip` 상대 고정 주소)** 으로 나타난다. 이것이 "소스 없이 어셈블리만 보고 `static` 지역 변수를 구분하는 법"이다 — 함수 안에서만 쓰이는 변수인데 그 변수가 `rbp`/`rsp` 상대가 아니라 고정 주소로 접근된다면, 그 변수는 `static`(또는 원래부터 전역이지만 이 함수에서만 참조)이라고 판단할 수 있다.

### 재귀 호출로 전역/지역을 실전 구분하기
재귀 함수를 디버거로 추적할 때, 어떤 변수가 매 호출마다 초기화되어 있으면(스택에 새로 잡힌) 지역 변수이고, 호출 깊이와 무관하게 이전 호출의 값이 계속 누적되어 있으면(모든 호출이 같은 메모리를 공유) 전역/`static` 변수라고 실전에서 바로 구분할 수 있다. 이는 정적 분석(주소 패턴)뿐 아니라 동적 분석(값의 지속성)으로도 같은 결론에 도달하는 좋은 교차검증 방법이다.

## 화면/코드에서 보이는 징후
- `[rip + 상수]` 또는 절대 주소 리터럴(`[0x00404050]`)로 접근 → 전역/static 변수.
- `[rbp - 상수]`, `[rbp + 상수]`, `[rsp + 상수]`로 접근 → 지역 변수/매개변수.
- IDA에서 `dword_404050`, `qword_405060`처럼 주소 기반 자동 명명이 붙은 변수는 전역, `var_10`, `a1`처럼 함수 스코프 안에서만 이름 붙은 변수는 지역이다.
- 함수 밖(전역 스코프)에서 정의되어 여러 함수에서 동시에 참조되는 변수는 항상 전역이다 — 여러 함수의 어셈블리에서 같은 `rip`-상대 오프셋(또는 같은 절대 주소)이 반복해서 나타난다.

## 가장 먼저 할 것
메모리 접근 명령어의 베이스가 무엇인지부터 확인한다. `rbp`/`rsp`가 베이스면 지역, `rip`나 고정 상수 주소가 베이스면 전역/static이다. 이 한 가지 규칙만으로 대부분의 경우를 즉시 분류할 수 있다.

## 단계별 절차
1. 메모리 오퍼랜드의 베이스 레지스터(또는 상수 주소 여부)를 확인한다.
2. `rbp`/`rsp` 기준이면 REV-0031/REV-0032 스택 프레임 규칙에 따라 지역 변수/매개변수로 분류한다.
3. `rip`-상대 또는 고정 절대 주소면 전역/static 변수로 분류하고, 그 주소가 속한 섹션(`.data`: 초기값 있음, `.bss`: 0으로 초기화)을 확인한다.
4. 같은 함수 안에서 지역 변수처럼 보이는데 `rip`-상대로 접근되는 변수를 발견하면 `static` 지역 변수로 판단한다.
5. 여러 함수에서 동일한 전역 주소를 공유해서 참조하는지 확인해, 그 변수가 실제로 함수 간 상태를 공유하는 용도인지 파악한다.

## 명령어/단축키
```
(gdb) info address counter        # 심볼이 있으면 counter가 전역인지, 어느 섹션에 있는지 확인
(gdb) info symbol 0x404050         # 해당 주소가 어떤 심볼(변수/함수)에 속하는지 역조회
(gdb) print &counter                 # 전역 변수의 실제 주소 확인 (실행마다 ASLR로 바뀔 수 있음)
(gdb) print $rbp - 4                 # 지역 변수 주소는 매 호출마다 rbp 값이 달라짐
```
IDA에서 `.data`/`.bss` 섹션을 열어 주소 기반 이름(`dword_XXXXXX`)이 어느 섹션에 속하는지 확인하면 전역 변수임이 재확인된다.

## 출력 해석
- `info address`가 "static storage at address 0x..."라고 답하면 전역/static 변수라는 뜻이다. "a variable in register $rbp offset N"처럼 답하면 지역 변수라는 뜻이다.
- 같은 전역 변수를 여러 번 실행해도(ASLR 켜진 상태에서) `print &counter`의 절대값은 매번 바뀌지만, `info address`가 보여주는 섹션과 상대 오프셋 개념은 바뀌지 않는다.
- 재귀 호출 중 `print $rbp`를 매 호출 프레임마다 확인하면 값이 계속 감소(스택이 아래로 자람)하는 것을 볼 수 있는데, 지역 변수의 절대 주소도 그에 따라 매번 달라진다 — 반면 전역 변수의 절대 주소는 재귀 깊이와 무관하게 항상 동일하다.

## 흔한 실수
- `rip`-상대 주소 지정을 보고 "이것도 레지스터를 쓰니까 지역 변수 아니야?"라고 오해하는 것 — `rip`는 매 명령어마다 값이 바뀌긴 하지만 그 변화는 컴파일 시점에 이미 정해진 고정된 방식이라 "상대적으로 매번 다른 스택 프레임"과는 근본적으로 다르다.
- `static` 지역 변수를 일반 지역 변수와 같은 방식으로 분석해서, 함수 재호출 시 값이 초기화될 것이라고 잘못 예상하는 것.
- 전역 변수가 여러 스레드에서 동시에 접근될 수 있다는 것을 간과하고, 단일 스레드 관점으로만 값의 변화를 추적하는 것(멀티스레드 프로그램에서는 레이스 컨디션 가능성도 함께 고려해야 함).
- IDA의 `dword_XXXXXX` 자동 명명을 보고 무조건 "이상한 이름이니 지역 변수겠지"라고 착각하는 것 — 오히려 이런 이름은 주소 기반이므로 전역 변수임을 나타내는 표시다.

## 막혔을 때 다음 체크
- 스택 프레임 자체가 헷갈리면 → REV-0031 스택 프레임이 무엇인지
- 함수 인자/반환값이 어디 저장되는지 헷갈리면 → REV-0032 함수 인자와 반환값이 어디에 있는지
- Code/Data/BSS/Stack/Heap의 전체 메모리 구획 개념이 헷갈리면 → REV-0030 Code Data BSS Stack Heap 기초
- 스택과 힙을 실전에서 구분하는 기준이 궁금하면 → REV-0354 스택 vs 힙: 리버싱에서 구분하는 실전 기준

## 미니 예제
```c
int global_count = 0;             // 전역 변수 (.data, 초기값 있음)

void bump(void) {
    static int static_count = 0;  // static 지역 변수 (.data/.bss)
    int local_count = 0;          // 진짜 지역 변수 (스택)

    global_count++;
    static_count++;
    local_count++;
}
```

x64 SysV 어셈블리(개념 설명용, PIE 기준):
```asm
bump:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x10
    mov     dword [rbp-4], 0             ; local_count = 0  (rbp 상대 = 지역)

    mov     eax, [rip + global_count]     ; global_count 읽기 (rip 상대 = 전역)
    add     eax, 1
    mov     [rip + global_count], eax

    mov     eax, [rip + static_count]     ; static_count 읽기 (rip 상대 = static 지역, 전역과 동일 패턴)
    add     eax, 1
    mov     [rip + static_count], eax

    mov     eax, [rbp-4]                   ; local_count 읽기 (rbp 상대 = 지역)
    add     eax, 1
    mov     [rbp-4], eax

    leave
    ret
```

세 변수 모두 C에서는 `count++` 형태로 똑같이 보이지만, 어셈블리에서는 `global_count`와 `static_count`가 똑같이 `rip`-상대(전역 저장소)로, `local_count`만 `rbp`-상대(스택)로 접근된다는 것이 이 예제의 핵심이다.

## 관련 글
- REV-0030 — Code Data BSS Stack Heap 기초
- REV-0031 — 스택 프레임이 무엇인지
- REV-0032 — 함수 인자와 반환값이 어디에 있는지
- REV-0354 — 스택 vs 힙: 리버싱에서 구분하는 실전 기준

## 출처/검증
- C의 정적 저장 기간(static storage duration)과 자동 저장 기간(automatic storage duration) 변수의 의미 차이: ISO C 표준(C11) 6.2.4 Storage durations of objects 섹션 기준.
- x86-64 RIP-relative addressing과 위치 독립 코드(PIE)에서의 전역 변수 접근 방식: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.1/2 및 System V AMD64 ABI(PIC/PIE 코드 생성 관례) 기준 (2026-09-09 확인).
