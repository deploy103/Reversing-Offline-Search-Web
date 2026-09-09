---
id: REV-0370
title: "정수 자료형 최대/최소값 치트시트"
slug: "rev-0370-integer-type-min-max-cheatsheet"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["정수 최대값", "정수 최소값", "INT_MAX", "INT_MIN", "UINT_MAX", "정수 범위", "signed unsigned 범위"]
aliases: ["int max값이 뭐임", "signed 범위", "unsigned 최대값", "정수 오버플로 경계값"]
symptom_keywords: ["int max값이 갑자기 음수로 바뀜", "0x7fffffff가 뭔지 모르겠음", "signed 범위를 넘었을때 값", "unsigned 최대값이 헷갈림"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
N비트 signed 정수의 범위는 `-2^(N-1)` ~ `2^(N-1)-1`이고 unsigned 정수의 범위는 `0` ~ `2^N-1`이며, 이 경계값들(`0x7FFFFFFF`, `0x80000000`, `0xFFFFFFFF` 등)은 CTF/리버싱에서 정수 오버플로 버그를 찾을 때 가장 먼저 눈에 익혀야 하는 헥스 상수들이다.

## 언제 검색해야 하나
- 디스어셈블리나 디컴파일 결과에 `0x7FFFFFFF`, `0x80000000`, `0xFFFFFFFF` 같은 값과의 비교(`cmp`)가 나오는데 이게 무슨 경계값인지 바로 안 떠오를 때
- 정수 오버플로 취약점을 찾고 있는데 "이 타입에서 최댓값에 1을 더하면 어떤 값이 되는지" 즉시 계산이 필요할 때
- signed 변수가 특정 연산 후 갑자기 음수가 되는 걸 보고 그게 오버플로로 인한 정상적인 랩어라운드인지 확인하고 싶을 때
- 32비트와 64비트, 8/16비트 정수의 최대/최소값을 표로 한눈에 정리해두고 싶을 때

## 핵심 개념
정수 타입의 범위는 비트 폭(N)과 부호 여부(signed/unsigned)만으로 결정된다. signed는 최상위 비트(MSB)를 부호 비트로 쓰는 2의 보수(REV-0024) 표현을 쓰므로 표현 가능한 양수 범위가 unsigned의 절반이 되는 대신 음수도 표현할 수 있다.

- **Unsigned N비트**: `0` ~ `2^N - 1`
- **Signed N비트(2의 보수)**: `-2^(N-1)` ~ `2^(N-1) - 1`

### 정수 타입별 최대/최소값 치트시트

| 타입 (비트폭) | Signed 최소값 | Signed 최대값 | Unsigned 최대값 |
|---|---|---|---|
| 8비트 (`char`) | -128 (`0x80`) | 127 (`0x7F`) | 255 (`0xFF`) |
| 16비트 (`short`) | -32768 (`0x8000`) | 32767 (`0x7FFF`) | 65535 (`0xFFFF`) |
| 32비트 (`int`/`long` Windows) | -2147483648 (`0x80000000`) | 2147483647 (`0x7FFFFFFF`) | 4294967295 (`0xFFFFFFFF`) |
| 64비트 (`long long`/`long` Linux) | -9223372036854775808 (`0x8000000000000000`) | 9223372036854775807 (`0x7FFFFFFFFFFFFFFF`) | 18446744073709551615 (`0xFFFFFFFFFFFFFFFF`) |

### 경계값을 헥스로 즉시 알아보는 패턴
- **`Signed 최대값` = `0x7...F` (F가 아니라 7로 시작, 나머지는 F로 꽉 참)**: 부호 비트(최상위 비트)만 0이고 나머지가 전부 1인 값. 예: 32비트는 `0x7FFFFFFF`.
- **`Signed 최소값` = `0x8000...0`**: 부호 비트만 1이고 나머지는 전부 0인 값. 예: 32비트는 `0x80000000`. 이는 2의 보수 표현의 특성상 "가장 큰 음수"가 되며, 특이하게 이 값의 절댓값을 취하려 하면(`-INT_MIN`) 같은 비트폭 안에서 표현할 수 없어 그 자체로 오버플로가 발생하는 유명한 함정이다.
- **`Unsigned 최대값` = `0xF...F` (전부 F)**: 모든 비트가 1인 값. 예: 32비트는 `0xFFFFFFFF`, 이는 부호 없이 보면 최댓값이지만 signed로 해석하면 `-1`이다.

### 랩어라운드(오버플로) 경계에서 정확히 무슨 일이 일어나는가
- Signed 최대값(`0x7FFFFFFF`)에 1을 더하면 → `0x80000000` = signed 최소값(음수로 뒤집힘). 이것이 "정수 오버플로로 양수가 갑자기 최솟값 음수가 되는" 전형적인 현상이다.
- Unsigned 최대값(`0xFFFFFFFF`)에 1을 더하면 → `0x00000000`으로 랩어라운드(0으로 돌아감).
- Unsigned 0에서 1을 빼면(underflow) → `0xFFFFFFFF`(unsigned 최댓값)로 랩어라운드.

## 화면/코드에서 보이는 징후
- `cmp eax, 7FFFFFFFh` 또는 `cmp eax, 80000000h` 같은 경계값 비교가 정수 오버플로 방어 코드(또는 취약점)에 자주 등장
- 디컴파일 결과에서 특정 덧셈/곱셈 직후 값이 음수 범위로 "갑자기" 바뀌는 것처럼 보이는 코드
- `INT_MAX`, `INT_MIN`, `UINT_MAX` 같은 매크로 이름이 strip 전 심볼이나 주석에 남아있는 경우

## 가장 먼저 할 것
문제의 변수가 몇 비트짜리(8/16/32/64)이고 signed인지 unsigned인지부터 확정한 뒤, 이 표에서 해당 행만 골라 경계값을 대입해본다. 오버플로 의심 코드라면 "그 연산이 최대값을 넘기거나 최소값 아래로 내려가는 입력을 만들 수 있는가"를 계산기로 직접 검증한다.

## 단계별 절차
1. 의심되는 변수의 비트 폭(8/16/32/64)을 디스어셈블리의 레지스터/메모리 접근 크기(`al`/`ax`/`eax`/`rax`, `byte`/`word`/`dword`/`qword`)로 확정한다.
2. signed/unsigned 여부를 주변 명령어(`movsx`=signed, `movzx`=unsigned, `jg`/`jl`=signed 비교, `ja`/`jb`=unsigned 비교)로 판단한다.
3. 이 표에서 해당 비트폭·부호 조합의 최대/최소값을 찾는다.
4. 해당 연산(덧셈, 곱셈 등)에 입력을 넣었을 때 그 경계값을 넘어서는지 파이썬 등으로 직접 계산해 오버플로 가능 여부를 검증한다.
5. 오버플로가 실제로 보안 취약점으로 이어지는지, 검증 로직(`if` 조건)이 오버플로 이후 값을 어떻게 처리하는지 함께 확인한다.

## 명령어/단축키
```python
import ctypes

ctypes.c_int32(0x7FFFFFFF + 1).value    # -2147483648 (오버플로 확인)
ctypes.c_uint32(0xFFFFFFFF + 1).value   # 0 (unsigned 랩어라운드, 실제로는 모듈로 연산 필요)
(0xFFFFFFFF + 1) & 0xFFFFFFFF            # 0  (더 일반적인 unsigned 랩어라운드 계산법)
(0x7FFFFFFF + 1) - (1 << 32)             # -2147483648 (signed 오버플로 직접 계산)
```
```c
#include <limits.h>
// INT_MIN, INT_MAX, UINT_MAX, LONG_MIN, LONG_MAX, LLONG_MAX 등 표준 매크로
printf("%d %d %u\n", INT_MIN, INT_MAX, UINT_MAX);
```

## 출력 해석
- 계산 결과가 `0x80000000`(32비트 기준)이라면 signed 최소값에 도달한 것 — 오버플로가 발생했다는 강력한 신호.
- 계산 결과가 `0xFFFFFFFF`인데 unsigned로 취급되면 최댓값, signed로 취급되면 `-1`이다. 같은 비트 패턴이라도 부호 해석에 따라 완전히 다른 숫자가 된다(REV-0025).
- 32비트 값이 64비트 레지스터에 부호 확장(sign-extend)되어 저장되면, 원래 32비트에서는 안 보이던 상위 32비트가 전부 `1`로 채워진 것(`0xFFFFFFFF80000000` 같은 패턴)을 볼 수 있다 — 이는 음수였다는 뜻이다.

## 흔한 실수
- `0x7FFFFFFF`를 unsigned 최댓값으로 착각하는 것 — 이는 signed 최댓값이고, unsigned 최댓값은 `0xFFFFFFFF`다.
- `INT_MIN`(`-2147483648`)의 절댓값을 그냥 `2147483648`로 계산 가능하다고 가정하는 것 — 32비트 signed 범위에서는 `2147483648`을 표현할 수 없어(최댓값이 `2147483647`) `abs(INT_MIN)` 자체가 정의되지 않은 동작(UB)이 되거나 그대로 `INT_MIN`을 반환하는 구현이 흔하다.
- 8/16비트처럼 32비트보다 작은 타입의 경계값을 32비트 기준으로 착각하는 것 — 비트폭마다 경계값이 다르다.
- 비트폭을 확인하지 않고 표의 아무 행이나 대입해서 계산하는 것 — 항상 대상 변수의 정확한 비트폭을 먼저 확정해야 한다.

## 막혔을 때 다음 체크
- 오버플로/랩어라운드의 일반 개념 자체가 헷갈리면 → REV-0027 정수 Overflow와 Wraparound
- signed/unsigned 해석 규칙 자체가 헷갈리면 → REV-0025 Signed와 Unsigned 해석
- 2의 보수 표현 원리가 궁금하면 → REV-0024 2의 보수와 음수 표현
- 각 타입의 바이트 크기가 헷갈리면 → REV-0369 자료형 크기 치트시트: char short int long long long pointer

## 미니 예제
정수 오버플로 취약점 코드에서 자주 보이는 패턴:
```c
int len = get_user_input_length();   // 공격자가 제어 가능
if (len + 10 > BUFFER_SIZE) {        // len이 0x7FFFFFF9 이상이면 len+10이 오버플로되어 음수가 됨
    error("too long");
}
char buf[BUFFER_SIZE];
memcpy(buf, data, len);              // 오버플로로 검사를 통과한 뒤 거대한 len으로 memcpy 실행
```
`len`이 `0x7FFFFFFF - 9 + 1 = 0x7FFFFFF7`보다 크면 `len + 10`이 `0x7FFFFFFF`(signed 최댓값)를 넘어 `0x80000000` 근방의 음수로 랩어라운드된다. 그러면 `len + 10 > BUFFER_SIZE` 비교가 (음수이므로) 거짓이 되어 검사를 통과하지만, 실제 `memcpy`에는 원래의 거대한 `len` 값이 그대로 전달되어 버퍼 오버플로가 발생한다. 이 표의 경계값(`0x7FFFFFFF`)을 즉시 알아볼 수 있으면 이런 코드를 훨씬 빨리 의심할 수 있다.

## 관련 글
- REV-0027 — 정수 Overflow와 Wraparound
- REV-0025 — Signed와 Unsigned 해석
- REV-0024 — 2의 보수와 음수 표현
- REV-0369 — 자료형 크기 치트시트: char short int long long long pointer

## 출처/검증
- 2의 보수 signed/unsigned 정수 범위 공식 및 C 표준 `<limits.h>` 매크로: ISO/IEC 9899(C 표준) 기준 (2026-09-09 검증).
- 정수 오버플로 발생 시 랩어라운드 동작(unsigned는 정의된 동작, signed는 구현별 동작이나 실무상 2의 보수 랩어라운드로 관찰됨): C 표준 및 Intel 64 and IA-32 Architectures Software Developer's Manual 기준.
