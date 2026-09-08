---
id: REV-0025
title: "Signed와 Unsigned 해석"
slug: "rev-0025-signed-unsigned"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["signed", "unsigned", "부호 있는 비교", "부호 없는 비교", "JL JB 차이", "MOVSX MOVZX", "CMP 조건 점프"]
aliases: ["jl jb 차이", "signed unsigned 비교 차이", "부호 비교가 왜 다름", "같은 값인데 비교 결과가 다름"]
symptom_keywords: ["같은 값인데 조건문 결과가 다르게 나옴", "jl이랑 jb 뭐가 다른지 모르겠음", "unsigned인데 음수 비교를 함", "len이 unsigned인데 0보다 작은지 체크함", "movzx movsx 차이 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
같은 비트 패턴이라도 CPU와 컴파일러가 그것을 **signed(부호 있음)로 읽느냐 unsigned(부호 없음)로 읽느냐**에 따라 완전히 다른 숫자이자 다른 비교 결과가 되며, 이 해석은 `CMP` 뒤에 어떤 조건 점프(`JL` 계열 vs `JB` 계열)를 쓰는지로 어셈블리에 그대로 드러난다.

## 언제 검색해야 하나
- 디스어셈블리에서 `cmp` 다음에 `jl`, `jle`, `jg`, `jge`가 나오는지 `jb`, `jbe`, `ja`, `jae`가 나오는지 구분해야 할 때
- IDA 디컴파일에서 어떤 변수가 `int`로 보였다가 다른 곳에서는 `unsigned int`로 보여서 값 해석이 헷갈릴 때
- `if (len < 0)` 같은 코드가 있는데 아무리 봐도 절대 참이 될 것 같지 않을 때
- `movzx`와 `movsx` 중 어떤 걸 써야 하는지, 또는 코드에 왜 둘 다 나오는지 궁금할 때

## 핵심 개념
이 글을 읽기 전에 **2의 보수(two's complement) 표현 자체**는 이미 안다고 가정한다 — 양수의 비트를 뒤집고 1을 더하면 음수가 되고, 그래서 `0xFFFFFFFF`가 32비트 signed로는 `-1`이 된다는 내용은 [REV-0024 2의 보수와 음수 표현](./rev-0024-twos-complement.md)에서 다뤘다. 여기서는 그 비트 패턴을 **CPU와 컴파일러가 실제로 어떻게 다르게 취급하는지**, 특히 비교(`CMP`)와 조건 점프, 그리고 값을 읽어들이는 명령어(`MOVSX`/`MOVZX`) 수준에서 무슨 일이 벌어지는지에 집중한다.

**핵심 사실**: 레지스터나 메모리에 저장된 비트 자체에는 "이건 signed다" "이건 unsigned다"라는 표식이 전혀 없다. 그 해석은 순전히 **소스 코드에서 그 변수가 어떤 C 타입으로 선언되었는가**(`int` vs `unsigned int`, `char` vs `unsigned char`, `short` vs `unsigned short`)에 달려 있고, 컴파일러는 그 타입 정보를 보고 어떤 어셈블리 명령어를 쓸지 결정한다. 즉 signed/unsigned 구분은 런타임에 CPU가 값을 보고 판단하는 게 아니라, **컴파일 시점에 이미 명령어 선택에 녹아 들어가 있는 정보**다.

**결정적인 예시**: `0xFFFFFFFF`와 `0`을 비교한다고 하자.
- **signed 32비트로 해석**: `0xFFFFFFFF` = `-1`. 따라서 `-1 < 0`은 **참(TRUE)**이다.
- **unsigned 32비트로 해석**: `0xFFFFFFFF` = `4294967295`. 따라서 `4294967295 < 0`은 **거짓(FALSE)**이다 — unsigned 세계에는 애초에 0보다 작은 값 자체가 존재하지 않는다.

똑같은 32비트, 똑같은 `0xFFFFFFFF`라는 비트 패턴인데, "이걸 signed로 보느냐 unsigned로 보느냐"만 바뀌어도 비교 결과가 정반대가 된다. 이게 이 글 전체의 핵심이다.

**CMP 뒤에 오는 조건 점프가 나뉘는 이유**: x86/x64에서 `CMP a, b`는 내부적으로 `a - b`를 계산하고 그 결과에 따라 플래그 레지스터(SF, ZF, OF, CF)를 세팅한다. 실제 뺄셈 결과값은 버리고 플래그만 남긴다. 그런데 "a가 b보다 작다"는 판단 기준이 signed냐 unsigned냐에 따라 완전히 다른 플래그 조합을 쓴다.

- **signed 비교** (`int`, `short`, `char`처럼 부호 있는 타입에서 컴파일러가 생성): `JL`/`JNGE`(작음), `JLE`/`JNG`(작거나 같음), `JG`/`JNLE`(큼), `JGE`/`JNL`(크거나 같음). 이 명령어들은 **SF(부호 플래그)와 OF(오버플로 플래그)의 관계**를 본다. 예를 들어 `JL`은 `SF != OF`일 때 점프한다 — 오버플로가 나면서 부호가 뒤집힌 경우까지 고려해서 "진짜 수학적으로 작은가"를 판단하는 로직이다.
- **unsigned 비교** (`unsigned int`, `unsigned short`, `unsigned char`에서 생성): `JB`/`JNAE`(미만, below), `JBE`/`JNA`(이하, below or equal), `JA`/`JNBE`(초과, above), `JAE`/`JNB`(이상, above or equal). 이 명령어들은 **CF(캐리 플래그)와 ZF(제로 플래그)**만 본다. `CMP`에서 뺄셈을 할 때 자리 빌림(borrow)이 발생했는지만 확인하면 되므로, 부호 개념 자체가 끼어들지 않는다.

이름도 의도적으로 다르다: signed 쪽은 "less/greater"(작다/크다), unsigned 쪽은 "below/above"(밑에/위에)라는 단어를 쓴다. 어셈블리를 읽을 때 `jl`/`jg`가 보이면 "이건 signed 비교구나", `jb`/`ja`가 보이면 "이건 unsigned 비교구나"라고 바로 판단할 수 있다.

**같은 값, 다른 명령어, 다른 결과 — 구체적 예시**: 레지스터 `eax = 0xFFFFFFFF`, `ebx = 0x00000001`이라고 하자.

```asm
cmp eax, ebx
jl  target      ; signed 비교: eax(-1) < ebx(1) → TRUE → 점프함
```
```asm
cmp eax, ebx
jb  target      ; unsigned 비교: eax(4294967295) < ebx(1) → FALSE → 점프 안 함
```

똑같은 `cmp eax, ebx` 다음에 오는 조건 점프 하나만 `jl`이냐 `jb`냐로 바뀌었을 뿐인데, 같은 레지스터 값으로 실행했을 때 한쪽은 점프하고 한쪽은 점프하지 않는다. 이 차이는 오직 **컴파일러가 원래 소스 코드에서 이 비교를 signed 타입끼리 했는지 unsigned 타입끼리 했는지**를 보고 결정한 것이다.

**읽어들이는 쪽(load)의 대응: MOVSX vs MOVZX**: 작은 크기의 값을 더 큰 레지스터로 옮길 때도 signed/unsigned 구분이 그대로 이어진다.
- `MOVZX`(zero-extend, 0으로 채움): 원본이 unsigned일 때 쓴다. 남는 상위 비트를 전부 0으로 채운다.
- `MOVSX`(sign-extend, 부호로 채움): 원본이 signed일 때 쓴다. 남는 상위 비트를 원본의 최상위 비트(부호 비트)로 채워서, 숫자로서의 값을 그대로 보존한다.

구체적 예시로, signed 8비트 값 `0xFF`(즉 `-1`)를 32비트로 옮긴다고 하자.
```asm
movsx eax, byte_value   ; byte_value = 0xFF (signed -1)
; eax = 0xFFFFFFFF  → 여전히 -1
```
```asm
movzx eax, byte_value   ; 같은 바이트 0xFF를 unsigned로 취급
; eax = 0x000000FF  → 255
```
원본 바이트는 완전히 동일한 `0xFF`인데, `MOVSX`로 읽으면 32비트에서도 여전히 `-1`(값 보존), `MOVZX`로 읽으면 `255`(단순히 상위 비트를 0으로 채운 것)가 된다. `MOVSX`는 "이 값이 signed였다면 원래 의미하던 숫자를 유지해야 한다"는 목적이고, `MOVZX`는 "이 값은 애초에 unsigned니까 그냥 빈 자리를 0으로 채우면 된다"는 목적이다.

## 화면/코드에서 보이는 징후
- 디컴파일 결과에서 어떤 함수는 매개변수를 `int len`으로 보여주는데 다른 코드 경로에서는 같은 변수가 `unsigned int`나 `size_t`처럼 보이는 경우
- `cmp`/`test` 다음에 오는 조건 점프가 `jl`, `jle`, `jg`, `jge`(signed 계열)인지 `jb`, `jbe`, `ja`, `jae`(unsigned 계열)인지가 코드 흐름 이해에 결정적인데 무심코 넘어가는 경우
- `movzx`와 `movsx`가 비슷한 위치에서 섞여 나와서 왜 다른지 헷갈리는 경우
- IDA 디컴파일에서 `if ( v4 < 0 )` 같은 조건이 있는데, `v4`의 실제 선언이 `unsigned int`라서 이 조건이 절대 참이 될 수 없는 경우(항상 거짓인 데드 코드)

## 가장 먼저 할 것
어셈블리에서 `cmp` 바로 다음에 오는 조건 점프 명령어의 **철자**부터 확인한다. `l`/`g`(less/greater)가 들어가 있으면 signed 비교, `a`/`b`(above/below)가 들어가 있으면 unsigned 비교다. 이 한 글자 차이가 코드의 의도를 완전히 바꾼다.

## 단계별 절차

**1) 조건 점프 명령어로 signed/unsigned 먼저 구분**

디스어셈블리에서 다음 두 그룹을 구분해서 외운다.

| 구분 | 명령어 | 의미 | 보는 플래그 |
|---|---|---|---|
| signed | `JL`/`JNGE` | 작음 | SF, OF |
| signed | `JLE`/`JNG` | 작거나 같음 | SF, OF, ZF |
| signed | `JG`/`JNLE` | 큼 | SF, OF, ZF |
| signed | `JGE`/`JNL` | 크거나 같음 | SF, OF |
| unsigned | `JB`/`JNAE` | 미만(below) | CF |
| unsigned | `JBE`/`JNA` | 이하(below or equal) | CF, ZF |
| unsigned | `JA`/`JNBE` | 초과(above) | CF, ZF |
| unsigned | `JAE`/`JNB` | 이상(above or equal) | CF |

**2) 그 비교에 쓰인 변수의 원래 C 타입 역추적**

`jl`/`jg` 계열이 보이면 그 비교에 쓰인 변수는 컴파일러가 signed 타입(`int`, `short`, `char`)으로 다뤘다는 뜻이고, `jb`/`ja` 계열이면 unsigned 타입(`unsigned int`, `size_t`, `unsigned char` 등)으로 다뤘다는 뜻이다. IDA/Ghidra 디컴파일에서 변수 선언부를 보면 대개 이 명령어와 일치하는 타입이 붙어 있다.

**3) IDA에서 직접 타입을 바꿔서 검증**

디컴파일러가 추론한 타입이 실제 비교 명령어와 안 맞아 보이거나, 값을 signed/unsigned 양쪽으로 다 확인해보고 싶으면 변수를 클릭하고 `Y`(Set type)를 눌러 `int`를 `unsigned int`로, 또는 그 반대로 바꿔본다. [REV-0024](./rev-0024-twos-complement.md)에서 다룬 것처럼 이건 비트 패턴 자체를 바꾸는 게 아니라 "같은 비트를 어떻게 읽을지"만 바꾸는 것이므로, 바꿔봤을 때 조건문이 훨씬 말이 되는 쪽이 원래 의도된 타입일 가능성이 높다.

**4) MOVZX/MOVSX로 원본 타입 크기와 부호 확인**

값을 레지스터로 옮기는 지점에서 `movzx`가 쓰였으면 원본은 unsigned(그리고 원본 크기는 오퍼랜드로 알 수 있음, 예: `movzx eax, byte ptr [...]`이면 원본은 1바이트 unsigned char), `movsx`가 쓰였으면 원본은 signed다. 이건 그 값이 나중에 signed로 비교될지 unsigned로 비교될지를 미리 알려주는 강한 단서다.

## 명령어/단축키
```text
IDA: 변수 선택 후 Y           → 타입 변경 (int ↔ unsigned int 등)
IDA: 숫자 리터럴 위에서 H     → 10진/16진 전환
GDB: p/d $eax                → eax를 signed 10진수로 출력
GDB: p/u $eax                → eax를 unsigned 10진수로 출력
GDB: p/x $eax                → eax를 16진수로 출력(부호 무관, 비트 패턴 그대로)
x64dbg: 레지스터 우클릭 → "부호 있는 십진수로 표시" 토글
```

## 출력 해석
- GDB에서 `p/d $eax`와 `p/u $eax`를 같은 레지스터에 실행했을 때 값이 다르게 나온다면, 그건 오류가 아니라 정확히 이 글의 핵심을 눈으로 확인한 것이다 — 같은 비트를 signed로 읽었는지 unsigned로 읽었는지 차이일 뿐이다.
- 어셈블리에서 `jl`/`jg` 계열이 보이는데 비교 대상 변수가 절대 음수가 될 수 없는 상황(예: 배열 인덱스, 길이 값)이라면, 원래 signed 타입으로 선언된 변수라는 뜻이고 이는 종종 버그나 익스플로잇 포인트의 단서가 된다(자세한 내용은 [REV-0027](./rev-0027-integer-overflow.md) 참고).
- `movzx`로 읽어들인 값은 항상 0 이상이고, 원본 바이트/워드 크기만큼의 최댓값을 넘지 못한다(예: `movzx`로 읽은 1바이트는 0~255 범위를 벗어나지 않음).

## 흔한 실수
- `unsigned` 변수를 signed처럼 생각해서 `if (len < 0)`, `if (size < 0)` 같은 코드를 "음수 체크"로 오해하는 것 — `len`이 `unsigned int`나 `size_t`라면 이 조건은 **항상 거짓인 데드 코드**다. 이런 패턴을 보면 오히려 "이 값이 언더플로로 매우 큰 값이 될 수 있는데 이 코드는 그걸 못 막는다"는 신호로 읽어야 한다.
- 어셈블리의 `jl`과 `jb`(또는 `jg`와 `ja`)를 그냥 "작다/크다"로 뭉뚱그려 읽고 넘어가는 것 — 이 두 그룹은 서로 다른 플래그를 보고 서로 다른 결과를 낼 수 있으므로 반드시 구분해서 읽어야 한다.
- `MOVZX`와 `MOVSX`를 그냥 "값을 확장하는 명령어" 정도로만 이해하고 넘어가서, 같은 바이트가 왜 32비트에서 전혀 다른 두 숫자(`0xFF` → `-1` 또는 `255`)가 되는지를 놓치는 것.
- 디컴파일러가 보여주는 타입(`int`인지 `unsigned int`인지)을 무조건 신뢰하는 것 — 디컴파일러의 타입 추론은 틀릴 수 있으므로, 중요한 비교라면 실제 조건 점프 명령어(`jl` vs `jb`)를 직접 확인해서 교차검증해야 한다.

## 막혔을 때 다음 체크
- 애초에 `0xFFFFFFFF`가 왜 `-1`이 되는지, 2의 보수 변환 자체가 헷갈리면 → [REV-0024 2의 보수와 음수 표현](./rev-0024-twos-complement.md)로 돌아간다.
- signed/unsigned 비교 자체는 이해했는데 오버플로/언더플로가 발생했을 때 값이 왜 그렇게 튀는지 궁금하면 → [REV-0027 정수 Overflow와 Wraparound](./rev-0027-integer-overflow.md)로 이동한다.
- 32비트/64비트 레지스터의 부분 이름(`eax` vs `rax` vs `ax` vs `al`)과 상위 비트 처리 규칙이 헷갈리면 → [REV-0022 레지스터 크기와 별칭](./rev-0022-register-widths.md)로 이동한다.
- 특정 크기(8/16/24/32/64비트)로 값을 잘라내는 `AND` 마스크 자체가 궁금하면 → [REV-0026](./rev-0026-bit-masks.md)(비트별 마스크)로 이동한다.

## 미니 예제
IDA 디컴파일에서 다음과 같은 길이 체크 코드를 봤다고 하자.

```c
int check_length(unsigned int len)
{
    if ( len < 0 )          // 항상 거짓 — 데드 코드
        return -1;
    if ( len > 0x100 )
        return -1;
    return 0;
}
```

어셈블리를 내려가 보면 `len < 0` 부분이 애초에 존재하지 않는다는 걸 알 수 있다.

```asm
; len(unsigned)에 대해 "len < 0" 비교는 컴파일러가 최적화로 아예 제거함
mov     eax, [ebp+len]
cmp     eax, 100h
ja      fail            ; unsigned 비교: len > 0x100 이면 실패로 점프
xor     eax, eax
ret
fail:
mov     eax, 0FFFFFFFFh
ret
```

여기서 `ja`(above, unsigned)가 쓰였다는 것 자체가 `len`이 unsigned로 컴파일러에 의해 취급되었다는 증거다. 만약 소스에서 `len`이 `int`(signed)였다면 컴파일러는 `jg`(greater, signed)를 썼을 것이고, 그때는 `len < 0` 체크가 실제로 의미 있는 코드로 남았을 것이다. 이런 차이를 눈여겨보면, CTF 문제에서 "음수 길이를 넣어서 체크를 우회하려 했는데 애초에 unsigned라서 음수 자체가 성립하지 않는" 함정과, 반대로 "unsigned 변수에 매우 큰 값을 넣어서 언더플로를 유도해야 하는" 문제를 구분할 수 있다.

## 관련 글
- [REV-0022 레지스터 크기와 별칭](./rev-0022-register-widths.md) — 부분 레지스터(`eax`/`ax`/`al`)와 상위 비트 처리 규칙
- [REV-0024 2의 보수와 음수 표현](./rev-0024-twos-complement.md) — 이 글이 전제로 삼는 비트 반전/음수 표현의 기초
- [REV-0026](./rev-0026-bit-masks.md) — 8비트 16비트 24비트 32비트 64비트 마스크
- [REV-0027 정수 Overflow와 Wraparound](./rev-0027-integer-overflow.md) — signed/unsigned 값이 오버플로될 때 벌어지는 일 (직접 후속편)
- REV-0055 — AND: 마스크와 비트 제거

## 출처/검증
- signed/unsigned 조건 점프와 플래그(SF, OF, CF, ZF) 관계: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.1, "Jcc—Jump if Condition Is Met" 및 "CMP—Compare Two Operands" 섹션 기준 (2026-09-08 검증).
- `MOVZX`/`MOVSX` 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.2, "MOVZX", "MOVSX" 명령어 레퍼런스 기준.
- C 언어의 signed/unsigned 정수 타입과 비교 규칙: ISO/IEC 9899(C 표준) 정수 승격(integer promotion) 및 비교 연산자 관련 조항 기준 개념 설명.
