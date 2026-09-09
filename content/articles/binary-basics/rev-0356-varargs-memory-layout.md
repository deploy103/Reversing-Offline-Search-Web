---
id: REV-0356
title: "가변 인자 함수(varargs)가 메모리에서 동작하는 방식"
slug: "rev-0356-varargs-memory-layout"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["가변 인자", "varargs", "va_list", "va_start", "va_arg", "printf 가변인자", "vararg 함수", "stdarg.h", "register save area"]
aliases: ["가변인자 함수가 뭔가요", "printf는 인자가 몇 개인지 어떻게 아나요", "va_list가 메모리에서 어떻게 생겼나요", "varargs 어셈블리로 보는 법"]
symptom_keywords: ["printf 호출 전에 al 레지스터를 설정하는 이유를 모르겠음", "인자 개수가 함수 시그니처에 안 나오는데 어떻게 처리되는지 모르겠음", "register save area가 뭔지 모르겠음", "va_list 구조체가 이상하게 생겼음"]
source_ids: ["SRC-SYSV-ABI", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`printf`처럼 인자 개수가 정해지지 않은 가변 인자 함수는 실제로는 특별한 CPU 기능이 있는 게 아니라, 호출자가 인자를 평소처럼 레지스터/스택에 늘어놓고 함수 자신은 포맷 문자열 등으로 "인자가 몇 개인지 추측"해서 `va_list`라는 규약을 통해 그 값들을 순서대로 읽어가는 것뿐이다.

## 언제 검색해야 하나
- `printf`, `sprintf`, `scanf` 같은 함수를 호출하기 직전에 `mov al, 0` 또는 `mov al, N` 같은 코드가 왜 있는지 궁금할 때(SysV x64)
- 디스어셈블리에서 함수 시그니처에 인자 개수가 안 보이는데 함수 내부에서 인자를 여러 개 순회하며 읽는 코드를 만났을 때
- `va_list`, `va_start`, `va_arg`, `va_end` 매크로가 실제로 어떤 어셈블리/메모리 구조로 컴파일되는지 알고 싶을 때
- 자체 제작 가변 인자 함수(로그 함수 등)를 리버싱하는데 인자가 스택 어디서부터 오는지 헷갈릴 때
- IDA/Ghidra가 가변 인자 함수의 인자 개수를 잘못 추정해서 함수 시그니처가 이상하게 보일 때

## 핵심 개념

### CPU에는 "가변 인자"라는 개념이 없다
`int printf(const char *fmt, ...)`처럼 인자 개수가 정해지지 않은 함수도, 호출하는 쪽(caller)은 여전히 일반적인 호출 규약(REV-0106, REV-0122)에 따라 인자를 레지스터와 스택에 순서대로 배치한다. CPU와 CALL 명령어 입장에서는 이것이 가변 인자 호출인지 고정 인자 호출인지 전혀 구분하지 않는다. 차이는 오직 **콜리(callee)가 "인자가 몇 개인지, 각각 무슨 타입인지"를 스스로 알아내야 한다**는 점뿐이다.

```c
printf("%d + %d = %d\n", 1, 2, 3);
```

이 호출은 SysV x64에서 대략 다음처럼 컴파일된다.

```asm
lea     rdi, [fmt_string]   ; 1번째 인자: 포맷 문자열
mov     esi, 1               ; 2번째 인자
mov     edx, 2               ; 3번째 인자
mov     ecx, 3               ; 4번째 인자
mov     al, 0                ; SSE 레지스터로 넘긴 가변 인자 개수 = 0
call    printf
```

`mov al, 0`이 가변 인자 함수 호출에서만 나타나는 특징적인 코드다. 다음 절에서 이게 왜 필요한지 설명한다.

### AL 레지스터로 SSE 인자 개수를 알려주는 이유(SysV x64)
SysV AMD64 ABI는 가변 인자 함수에서, 실수(float/double) 인자가 `XMM0`~`XMM7` 중 몇 개나 쓰였는지를 콜리가 알아야 한다고 규정한다. 정수 인자는 레지스터 개수(RDI, RSI, RDX, RCX, R8, R9 중 몇 개 썼는지)로 유추 가능하지만, 가변 인자 함수 내부에서 부동소수점 레지스터 저장 영역을 준비하려면 몇 개가 쓰였는지 미리 알아야 하기 때문에, **AL 레지스터에 사용된 벡터 레지스터 개수(0~8)를 넣어서 전달**한다. 부동소수점 인자가 하나도 없으면 `mov al, 0`이 나온다. 이 규칙은 Windows x64에는 없다(Windows x64는 가변 인자에 다른 방식을 쓴다).

### 콜리는 포맷 문자열로 "인자 개수"를 추측한다
`printf` 자신은 컴파일 시점에 몇 개의 인자가 넘어올지 전혀 모른다. 대신 런타임에 첫 번째 인자인 포맷 문자열(`"%d + %d = %d\n"`)을 파싱해서 `%` 지정자 개수를 세고, 그 개수만큼 `va_arg`로 값을 순서대로 꺼내온다. 이것이 `printf` 계열 함수가 **포맷 문자열과 실제 인자 개수가 안 맞으면 정의되지 않은 동작(쓰레기 값을 읽거나 크래시)**을 일으키는 근본 이유다 — 함수는 인자 개수를 스스로 알 방법이 없고 오직 포맷 문자열의 내용만 믿기 때문이다.

### va_list의 실제 구조 — Register Save Area
`stdarg.h`의 `va_start`/`va_arg` 매크로는 컴파일러마다 다르게 구현되지만, SysV x64 리눅스(GCC/Clang)에서는 대략 다음과 같은 구조체로 구현된다.

```c
typedef struct {
    unsigned int gp_offset;     // 다음에 읽을 정수 레지스터 저장 영역 오프셋
    unsigned int fp_offset;     // 다음에 읽을 SSE 레지스터 저장 영역 오프셋
    void *overflow_arg_area;    // 레지스터로 다 못 채운 나머지 인자(스택에서 온 것들)
    void *reg_save_area;        // 레지스터 인자들이 실제로 복사되어 저장된 스택 영역
} va_list[1];
```

가변 인자 함수가 시작되면, 프롤로그에서 **레지스터로 받은 인자들(RDI~R9, XMM0~XMM7 중 실제로 쓰인 것들)을 전부 스택의 한 영역(Register Save Area)에 미리 복사**해둔다. 그 다음 `va_arg`가 호출될 때마다 `gp_offset`/`fp_offset`을 이 영역의 시작 주소에 더해서 다음 인자를 읽고, 오프셋을 8(또는 16)씩 증가시킨다. 레지스터 몫을 다 쓰면 그 이후 인자는 `overflow_arg_area`(호출자가 스택에 남겨둔 부분)에서 계속 읽는다.

```asm
; 가변 인자 함수 프롤로그에서 흔히 보이는 패턴 (개념적 예시)
test    al, al
je      skip_fp_save
movaps  [rbp-0x90], xmm0        ; XMM 레지스터 인자들을 Register Save Area에 저장
movaps  [rbp-0x80], xmm1
...
skip_fp_save:
mov     [rbp-0xd0], rdi          ; GP 레지스터 인자들도 저장
mov     [rbp-0xc8], rsi
mov     [rbp-0xc0], rdx
mov     [rbp-0xb8], rcx
mov     [rbp-0xb0], r8
mov     [rbp-0xa8], r9
```

이 코드가 있기 때문에, `va_arg`가 나중에 순서대로 값을 읽어도 그 값이 이미 스택에 안전하게 보관되어 있는 것이다. 함수가 자기 자신의 인자를 받고 나서 곧바로 이걸 다시 스택에 복사하는 것처럼 보이는 이유가 바로 이것이다 — 일반 함수의 인자 스필(REV-0359)과 비슷해 보이지만, 목적이 "va_arg가 나중에 순서대로 접근할 수 있게 미리 한곳에 몰아두는 것"이라는 점이 다르다.

### Windows x64에서는 더 단순하다
Windows x64는 애초에 정수/포인터/부동소수점 인자를 구분 없이 항상 4개까지 `RCX, RDX, R8, R9`로 전달하고(REV-0122), 가변 인자 함수를 호출할 때도 shadow space(REV-0124)에 인자가 그대로 스필된다. `va_arg`는 단순히 shadow space 시작 주소부터 8바이트씩 순서대로 읽어가는 방식으로 구현되어, SysV처럼 정수/부동소수점 레지스터를 별도 영역으로 나누는 복잡함이 없다.

## 화면/코드에서 보이는 징후
- SysV x64에서 `printf`/`sprintf` 등 가변 인자 함수 호출 직전에 `mov al, N`(N은 0~8)이 있는 코드
- 함수 프롤로그에서 인자 레지스터(`RDI, RSI, RDX, RCX, R8, R9`, `XMM0`~`XMM7`)를 스택의 넓은 영역(보통 176바이트 전후, Register Save Area 크기)에 몰아서 저장하는 코드
- `va_list` 타입의 지역 변수가 4개 필드(`gp_offset`, `fp_offset`, `overflow_arg_area`, `reg_save_area`)를 가진 구조체로 디컴파일되는 경우
- 함수 시그니처에 `...`(ellipsis)가 있거나, 첫 인자가 포맷 문자열이고 함수 본문이 그 문자열을 파싱하는 루프를 포함하는 경우

## 가장 먼저 할 것
가변 인자 함수로 의심되는 호출을 만나면, 먼저 호출 직전 코드에서 `mov al, N`이 있는지(SysV x64 신호) 확인하고, 첫 번째 인자로 넘어가는 문자열(포맷 문자열일 가능성이 높음)을 `.rodata`/`.rdata`에서 찾아 실제 내용을 읽어본다. 포맷 지정자(`%d`, `%s` 등) 개수를 세면 이 호출에서 실제로 몇 개의 가변 인자가 쓰이는지 바로 알 수 있다.

## 단계별 절차

**1) 호출부에서 mov al, N 확인(SysV x64)**

`call printf` 직전에 `mov al, N`이 있으면 N이 SSE 레지스터로 넘어간 부동소수점 인자 개수다. Windows x64에는 이 코드가 없다.

**2) 포맷 문자열을 찾아 지정자 개수 세기**

첫 번째 인자(RDI 또는 RCX)로 들어가는 문자열 리터럴 주소를 따라가서 실제 내용을 확인하고, `%d`, `%s`, `%x` 등 지정자 개수를 세면 이 호출에 필요한 가변 인자 개수를 알 수 있다.

**3) 가변 인자 함수 내부라면 프롤로그의 Register Save Area 저장 코드 확인**

`stdarg.h`를 쓰는 자체 함수를 분석 중이라면, 프롤로그에서 인자 레지스터들을 한 번에 스택으로 복사하는 넓은 블록을 찾는다. 이 블록의 시작 주소가 `va_list`의 `reg_save_area`다.

**4) va_arg 호출 지점을 오프셋 증가 패턴으로 추적**

함수 본문에서 `gp_offset`/`fp_offset` 역할을 하는 변수가 8(또는 16)씩 증가하면서 `reg_save_area + offset`을 읽는 반복 패턴이 있으면, 그것이 `va_arg`가 인라인된 결과다.

**5) 디버거로 실제 스택 값을 확인**

GDB/x64dbg로 가변 인자 함수 프롤로그 직후에 브레이크포인트를 걸고, Register Save Area로 추정되는 스택 영역을 덤프해서 예상한 인자 값들이 순서대로 들어있는지 검증한다.

## 명령어/단축키
```text
(gdb) break *0x555555555169    # 가변 인자 함수 프롤로그 직후
(gdb) run
(gdb) x/8xg $rbp-0xd0           # Register Save Area로 추정되는 영역 덤프
(gdb) print (char*)$rdi          # 포맷 문자열로 추정되는 포인터 내용 확인
(gdb) x/s $rdi                   # 포맷 문자열 직접 읽기
```
IDA: 포맷 문자열 인자에서 `Alt+T`(텍스트 검색) 또는 문자열 창(`Shift+F12`)으로 `.rodata`의 실제 문자열 확인. Ghidra: Decompile 창에서 `va_list` 관련 구조체가 자동 인식되면 필드 이름이 표시됨.

## 출력 해석
- `mov al, N`에서 N이 0이면 이 호출에는 부동소수점 가변 인자가 없다는 뜻이지, 가변 인자 자체가 없다는 뜻은 아니다(정수 가변 인자는 여전히 있을 수 있음).
- 포맷 문자열의 지정자 개수와 실제 호출부에서 준비된 레지스터/스택 인자 개수가 안 맞으면, 그 호출은 버그이거나(format string bug 취약점의 전형적 형태) 컴파일러가 이미 상수 폴딩으로 인자를 줄인 것일 수 있다 — 원본 소스를 확인해야 확실하다.
- Register Save Area 크기가 SysV x64에서 보통 176바이트(정수 레지스터 6개×8 + XMM 레지스터 8개×16)로 고정되어 있으면 이는 컴파일러가 항상 최대 크기로 예약해두는 것이며, 실제로 그 인자들이 모두 쓰였다는 뜻은 아니다.

## 흔한 실수
- 가변 인자 함수를 "특수한 CPU 명령어/모드로 처리된다"고 오해하는 것 — 실제로는 평범한 레지스터/스택 전달 규약 위에서, 콜리가 포맷 문자열이나 별도의 카운트 인자로 개수를 스스로 알아내는 소프트웨어적인 관례일 뿐이다.
- `mov al, N`을 함수 인자 개수 전체로 오해하는 것 — 이 값은 오직 **SSE(부동소수점) 레지스터로 넘어간 가변 인자 개수**이며 정수 인자 개수와는 무관하다.
- 포맷 문자열 스캔 로직을 몰라서, 왜 `printf("%s", ptr)`에서 `ptr`이 문자열이 아닌 값이면 크래시가 나는지 이해하지 못하는 것 — 함수는 포맷 문자열만 믿고 그 타입으로 값을 해석하기 때문에, 포맷과 실제 인자 타입이 다르면 미정의 동작이 된다.
- Windows x64와 SysV x64의 가변 인자 구현 방식이 같다고 가정하는 것 — Windows는 부동소수점/정수 구분이 없고 shadow space를 그대로 활용하는 훨씬 단순한 구조다.

## 막혔을 때 다음 체크
- 일반적인 함수 인자/반환값의 레지스터·스택 위치가 헷갈리면 → REV-0032 함수 인자와 반환값이 어디에 있는지
- SysV x64와 Windows x64의 정수 인자 전달 규칙 자체가 헷갈리면 → REV-0106 SysV AMD64 Calling Convention / REV-0122 Microsoft x64 Calling Convention
- 인자 레지스터가 스택으로 복사되는 이유가 일반적인 스필과 뭐가 다른지 헷갈리면 → REV-0359 레지스터 스필(Register Spill)이 스택에 미치는 영향
- Windows x64 shadow space의 정확한 크기/역할이 궁금하면 → REV-0124 Shadow Space가 무엇인지
- 실제 `printf` 계열 함수의 내부 동작이 궁금하면 → REV-0635 libc printf family

## 미니 예제
직접 만든 간단한 로그 함수로 가변 인자 흐름을 살펴보자.

```c
#include <stdarg.h>
#include <stdio.h>

void log_ints(int count, ...) {
    va_list ap;
    va_start(ap, count);
    for (int i = 0; i < count; i++) {
        int v = va_arg(ap, int);
        printf("arg[%d] = %d\n", i, v);
    }
    va_end(ap);
}

int main(void) {
    log_ints(3, 10, 20, 30);
    return 0;
}
```

`main`에서의 호출부(SysV x64):
```asm
mov     ecx, 30          ; 4번째 실인자
mov     edx, 20          ; 3번째 실인자
mov     esi, 10          ; 2번째 실인자
mov     edi, 3            ; count = 3 (1번째 인자)
mov     al, 0             ; 부동소수점 가변 인자 없음
call    log_ints
```

`log_ints` 프롤로그(개념적으로 단순화):
```asm
log_ints:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0xd0
    test    al, al
    je      .no_fp
    ; xmm0~xmm7을 reg_save_area 상단에 저장(생략)
.no_fp:
    mov     [rbp-0xd0], edi   ; count
    mov     [rbp-0xc8], esi    ; 2번째 인자(=10)
    mov     [rbp-0xc0], edx    ; 3번째 인자(=20)
    mov     [rbp-0xb8], ecx    ; 4번째 인자(=30)
    ; va_start: gp_offset = 8(1개 정수 레지스터는 count가 이미 소비), reg_save_area = rbp-0xd0 ...
```

`va_arg(ap, int)`가 호출될 때마다 `gp_offset`이 가리키는 `reg_save_area + gp_offset` 위치에서 4바이트를 읽고 `gp_offset`을 8만큼 증가시킨다. 첫 호출은 `esi`가 저장된 `[rbp-0xc8]`(값 10)을 읽고, 두 번째 호출은 `edx`가 저장된 `[rbp-0xc0]`(값 20)을 읽는 식으로 이어진다. `count` 자신은 고정 인자이므로 `va_arg`의 순회 대상에 포함되지 않는다는 점에 주의한다.

## 관련 글
- REV-0032 — 함수 인자와 반환값이 어디에 있는지
- REV-0106 — SysV AMD64 Calling Convention
- REV-0122 — Microsoft x64 Calling Convention
- REV-0124 — Shadow Space가 무엇인지
- REV-0359 — 레지스터 스필(Register Spill)이 스택에 미치는 영향

## 출처/검증
- 가변 인자 함수에서 AL 레지스터로 SSE 레지스터 사용 개수를 전달하는 규칙과 `va_list`(Register Save Area, `gp_offset`/`fp_offset`/`overflow_arg_area`) 구조: System V AMD64 ABI(psABI) 공식 스펙 "Variable Argument Lists" 절 기준.
- Windows x64 가변 인자와 shadow space의 관계: Microsoft Learn "x64 calling convention" 및 "Varargs" 관련 공식 문서 기준 (2026-09-09 검증).
