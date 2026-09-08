---
id: REV-0201
title: "Rotate ROL ROR 기반 변환"
slug: "rev-0201-rotate-transform"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["rol", "ror", "비트 회전", "rotate 변환", "__ROL4__", "__ROR1__"]
aliases: ["rol 반복문", "ror 반복문", "비트 회전 역산", "회전 암호"]
symptom_keywords: ["rol이 뭔지 모르겠음", "ror 역산 어떻게 함", "비트가 순환하는 것 같음", "__ROL4__ 함수가 보임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
루프 안에서 각 바이트/워드에 `rol`(왼쪽 회전) 또는 `ror`(오른쪽 회전)을 적용해서 비교하는 코드를 만나면, **ROL n비트의 역연산은 정확히 ROR n비트(그 반대도 성립)** 이므로 회전 방향만 뒤집어서 그대로 되돌리면 원래 값이 복원된다 — 비트가 유실되지 않는 회전 연산의 특성 덕분에 완벽하게 역산 가능하다.

## 언제 검색해야 하나
- 디스어셈블리에 `rol al, N` / `ror al, N` / `rol eax, cl` 같은 명령이 루프 안에서 반복될 때
- IDA/Ghidra 디컴파일 결과에 `__ROL1__`, `__ROL4__`, `__ROR1__`, `__ROR4__`, `_rotl`, `_rotr`, `__builtin_rotateleft8` 같은 헬퍼 함수 호출이 보일 때 (컴파일러/디컴파일러가 rotate를 이런 의사함수로 표현하는 경우가 많음)
- shift(`shl`/`shr`) 두 개가 `or`로 합쳐진 코드가 보일 때 — 이것도 사실 rotate를 손으로 푼 것과 동일한 패턴(REV-0202와 겹치는 경계 케이스)
- 해시 알고리즘(SHA, RC5 등) 흔적을 찾다가 회전 상수가 나올 때

## 핵심 개념
회전(rotate)은 시프트와 달리 **비트가 밖으로 밀려나가는 대신 반대쪽 끝으로 다시 들어오는** 연산이다. 그래서 정보 손실이 전혀 없고, 항상 완벽하게 역산 가능하다.

- `ROL(x, n)`: x를 왼쪽으로 n비트 회전. 왼쪽 끝에서 밀려나온 비트가 오른쪽 끝으로 들어옴.
- `ROR(x, n)`: x를 오른쪽으로 n비트 회전. 오른쪽 끝에서 밀려나온 비트가 왼쪽 끝으로 들어옴.

핵심 성질:
```
ROL(x, n)의 역연산 = ROR(x, n)
ROR(x, n)의 역연산 = ROL(x, n)
```
즉 "왼쪽으로 3비트 돌렸다"면 "오른쪽으로 3비트 돌리면" 원래대로 돌아온다. 회전 크기(비트 폭, 8/16/32/64)를 정확히 맞추는 것만 주의하면 된다 — 8비트 레지스터(`al`)에서 회전한 걸 32비트로 착각해서 역산하면 값이 틀어진다.

## 화면/코드에서 보이는 징후
**x64 디스어셈블리 (8비트 rotate):**
```asm
loop1:
movzx   eax, byte ptr [rdi+rcx]
rol     al, 3
cmp     al, byte ptr [rsi+rcx]
jne     fail
inc     ecx
cmp     ecx, len
jl      loop1
```

**IDA 디컴파일 (의사함수로 표현되는 경우):**
```c
for ( i = 0; i < len; ++i )
{
    v = __ROL1__(input[i], 3);   // 8비트 rotate left by 3
    if ( v != expected[i] )
        return 0;
}
```
IDA는 회전 연산을 `__ROL1__`(1바이트), `__ROL2__`(2바이트/워드), `__ROL4__`(4바이트/dword), `__ROL8__`(8바이트/qword) 형태로 표시하며, 오른쪽 회전은 `__ROR1__`~`__ROR8__`로 표시한다. 숫자는 피연산자 크기(바이트 단위)를 의미하므로 `__ROL4__(x, 5)`는 "32비트 값 x를 왼쪽으로 5비트 회전"이라는 뜻이다.

**Ghidra 디컴파일:**
```c
uVar1 = input[i] << 3 | input[i] >> 5;   // 8비트 rol 3의 shift 조합 표현
if (uVar1 != expected[i]) return 0;
```
Ghidra는 종종 rotate를 `<<`와 `>>`를 `|`로 합친 형태로 그대로 풀어서 보여준다. `<<3`과 `>>5`(=8-3)처럼 두 시프트 양의 합이 정확히 전체 비트 폭과 같다면, 이는 rotate를 shift+or로 표현한 것이다.

**레지스터/즉시값이 아니라 CL로 회전량을 지정하는 경우:**
```asm
mov     cl, [shift_amount]
rol     al, cl
```
회전량이 상수가 아니라 변수/배열에서 오는 경우도 흔하다.

## 가장 먼저 할 것
회전 방향(`rol`/`ror` 또는 `__ROL_N__`/`__ROR_N__`)과 **회전량(비트 수)**, 그리고 **피연산자 크기(8/16/32/64비트)** 세 가지를 정확히 적어둔다. 이 세 가지만 알면 역산은 기계적이다.

## 단계별 절차
**1) 방향/크기/회전량 확정**

`rol al, 3` → 방향=left, 크기=8비트, 회전량=3.
`__ROL4__(x, 5)` → 방향=left, 크기=32비트, 회전량=5.

**2) 파이썬 rotate 함수 준비**

```python
def rol(val: int, n: int, bits: int = 8) -> int:
    n %= bits
    mask = (1 << bits) - 1
    return ((val << n) | (val >> (bits - n))) & mask

def ror(val: int, n: int, bits: int = 8) -> int:
    n %= bits
    mask = (1 << bits) - 1
    return ((val >> n) | (val << (bits - n))) & mask
```

**3) 반대 방향으로 역산**

원본이 `rol(x, n)`이었다면 역산은 `ror(cipher, n)`, 원본이 `ror(x, n)`이었다면 역산은 `rol(cipher, n)`.

```python
expected = bytes.fromhex("...")
# 원본이 8비트 rol 3 이었다면
flag = bytes(ror(b, 3, bits=8) for b in expected)
```

**4) 32비트 단위 회전이면 struct로 묶어서 처리**

```python
import struct

expected = bytes.fromhex("...")  # 4의 배수 길이
out = b""
for i in range(0, len(expected), 4):
    v = struct.unpack_from("<I", expected, i)[0]
    out += struct.pack("<I", ror(v, 5, bits=32))
print(out)
```

## 명령어/단축키
- IDA: `rol`/`ror` 명령 즉시값 위에서 `H`로 진법 확인, `__ROL4__`류 의사함수는 더블클릭하면 정의(내부 shift/or 조합)를 볼 수 있음
- Ghidra: Decompile 창에서 `<<`/`>>`/`|` 조합이 나오면 두 시프트 양의 합이 데이터 폭과 같은지 암산으로 확인(같으면 rotate 확정)
- Python: 위 `rol`/`ror` 헬퍼 함수를 항상 `bits` 인자와 함께 사용(기본값을 8로 두면 32비트 케이스에서 실수하기 쉬움)

## 출력 해석
- 역산 결과가 아스키로 안 읽히면 방향(`rol`↔`ror`)이 뒤바뀌었을 가능성이 가장 크다 — 방향만 바꿔서 재시도.
- 그다음으로 흔한 원인은 회전량(비트 수)이 피연산자 크기를 기준으로 정규화(`% bits`)되지 않은 것 — 예를 들어 8비트 값에 `rol al, 11`을 적용한 것과 `rol al, 3`(11 mod 8 = 3)을 적용한 것은 결과가 같아야 한다.
- 32비트 회전인데 8비트로 착각해서 역산하면 상위 바이트가 뒤섞여 완전히 다른 값이 나온다 — 피연산자 크기(al/ax/eax/rax)를 다시 확인.

## 흔한 실수
- ROL과 ROR을 반대로 적용해서 역산하는 것(가장 흔한 실수) — 원본이 왼쪽 회전이면 역산은 반드시 오른쪽 회전이어야 한다.
- 회전량을 비트 폭으로 나눈 나머지로 정규화하지 않아서 음수나 비트 폭을 넘는 값으로 잘못 계산하는 것.
- IDA의 `__ROL4__`를 보고 "4비트 회전"으로 착각하는 것 — 이 숫자는 회전 비트 수가 아니라 **피연산자의 바이트 크기**(4바이트=32비트)를 의미한다. 실제 회전 비트 수는 함수의 두 번째 인자다.
- x86의 `rol`/`ror`는 회전량이 레지스터 크기를 넘으면 자동으로 모듈로 처리된다는 걸 모르고, `rol eax, 40`처럼 32를 넘는 즉시값을 보고 당황하는 것 — 실제로는 `40 mod 32 = 8`비트 회전과 동일하게 동작한다(단, 이 자동 모듈로 처리는 CPU에 내장된 동작이며 8/16비트 오퍼랜드에서는 모듈로 기준이 다를 수 있으니 Intel SDM의 정확한 규칙을 다시 확인).

## 막혔을 때 다음 체크
- shift(`shl`/`shr`)만 있고 `or`로 합쳐지지 않는다면 → REV-0202(진짜 shift, 정보 손실 있음)로 이동.
- rotate와 XOR이 함께 나온다면(해시 함수 느낌) → REV-0207/REV-0208(FNV), REV-0209(CRC)와 비교.
- 회전 상수(`3`, `5`, `13` 등)가 유명 해시 알고리즘의 상수표와 일치하는지 궁금하면 → REV-0209(CRC 계열)의 다항식 상수 목록과 대조.
- `__ROL4__`/`__ROR4__` 의사함수 자체가 처음 본다면 → IDA 헬퍼 함수 목록에서 정의를 다시 확인(디컴파일러가 자동 생성하는 표준 매크로).

## 미니 예제
**예제 1 — 8비트 rol 3**
```asm
rol al, 3
```
```python
def ror(val, n, bits=8):
    n %= bits
    mask = (1 << bits) - 1
    return ((val >> n) | (val << (bits - n))) & mask

expected = bytes.fromhex("d8983868b8f8d838")
flag = bytes(ror(b, 3) for b in expected)
print(flag)
```

**예제 2 — 32비트 ror 7 (IDA `__ROR4__` 형태)**
```c
v = __ROR4__(input_dword, 7);
if (v != expected_dword) return 0;
```
```python
def rol(val, n, bits=32):
    n %= bits
    mask = (1 << bits) - 1
    return ((val << n) | (val >> (bits - n))) & mask

expected_dword = 0xA1B2C3D4
flag_dword = rol(expected_dword, 7, bits=32)
print(hex(flag_dword))
```

**예제 3 — Ghidra의 shift+or 표현을 rotate로 재해석**
```c
uVar1 = (byte)input[i] << 5 | (byte)input[i] >> 3;
```
`5 + 3 = 8`이므로 이건 8비트 `rol 5`(또는 동치로 `ror 3`)이다. 역산:
```python
flag_byte = ror(expected_byte, 5, bits=8)
```

**예제 4 — 회전량이 인덱스에 따라 달라지는 경우**
```c
for (i = 0; i < len; ++i)
    if (rol8(input[i], i % 8) != expected[i]) return 0;
```
```python
flag = bytes(ror(e, i % 8, bits=8) for i, e in enumerate(expected))
```

## 관련 글
- REV-0198 — 문자별 for 루프 검증 패턴
- REV-0202 — Shift SHL SHR SAR 기반 변환
- REV-0209 — CRC 계열 알고리즘 흔적 찾기
- ../assembly/rev-0064-rol.md — ROL 명령어
- ../assembly/rev-0065-ror.md — ROR 명령어

## 출처/검증
- ROL/ROR의 정의와 회전량 모듈로 처리 규칙은 Intel 64 and IA-32 Architectures Software Developer's Manual의 ROL/ROR 명령 설명 기준.
- IDA Hex-Rays 디컴파일러의 `__ROL_N__`/`__ROR_N__` 의사함수 표기는 Hex-Rays 공식 디컴파일러 출력 관례 기준(2026-09-08 확인).
