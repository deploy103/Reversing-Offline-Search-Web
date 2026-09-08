---
id: REV-0222
title: "검증 루틴을 Python으로 그대로 재현하기"
slug: "rev-0222-reimplement-in-python"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["파이썬 재구현", "check function port", "rol32", "ror32", "32비트 마스킹", "instruction by instruction port", "오라클 함수", "solver script"]
aliases: ["체크 함수 파이썬으로 옮기기", "어셈블리를 파이썬으로", "디스어셈블리 python 변환", "check 함수 재현"]
symptom_keywords: ["파이썬으로 어떻게 옮기지", "레지스터를 변수로 바꾸는 법", "rol 파이썬 함수 없음", "값이 계속 달라짐 마스크"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
체크 함수의 어셈블리/디컴파일을 한 줄이라도 이해했으면, 그 로직을 "추상적으로 파악해서 내 방식대로 재구현"하지 말고 **명령어 하나하나를 그대로 파이썬 한 줄씩으로 직역**하는 것이 가장 빠르고 실수가 적은 길이다.

## 언제 검색해야 하나
- 체크 함수를 다 읽었는데 "이걸 파이썬으로 어떻게 옮겨야 할지" 막막할 때
- 레지스터가 어떤 파이썬 변수에 대응되는지 정리가 안 될 때
- `rol`/`ror`처럼 파이썬에 없는 연산을 어떻게 구현해야 할지 모를 때
- 파이썬으로 옮긴 함수의 결과가 실제 바이너리와 다르게 나와서 어디서 틀렸는지 찾아야 할 때

## 핵심 개념
CTF 체크 함수를 처음 보는 사람은 "이 알고리즘이 뭔지 이름부터 알아내고, 그 알고리즘의 표준 구현을 인터넷에서 찾아 붙여넣자"는 유혹을 받는다. 하지만 실제로는 **바이너리에 있는 코드를 그대로, 줄 단위로 파이썬으로 옮기는 것**이 훨씬 안전하다. 이유는 두 가지다.

첫째, CTF 문제의 체크 함수는 표준 알고리즘을 "약간 비틀어서" 쓰는 경우가 매우 많다(상수를 바꾸거나, 루프 방향을 반대로 하거나, XOR과 곱셈 순서를 바꾸는 식). 이름만 보고 표준 구현을 가져다 쓰면 이 미묘한 차이를 놓친다.

둘째, 어셈블리를 한 줄씩 그대로 옮기면 **각 줄이 정확히 무엇을 검증해야 하는지**가 명확해서, 틀렸을 때 어느 줄이 문제인지 바로 좁힐 수 있다. "알고리즘을 이해해서 재구현"한 코드는 틀렸을 때 어디가 잘못됐는지 찾기가 훨씬 어렵다.

**핵심 매핑 규칙**

| 어셈블리 요소 | 파이썬 대응 |
|---|---|
| 입력 버퍼 포인터(`rdi`, `rcx` 등, ABI에 따라 다름) | `bytes` 객체 변수 |
| 길이 레지스터 | `len(입력_변수)` |
| 루프 카운터(`eax`, `i` 등) | `for i in range(...)` |
| 누산 변수(`ecx`, hash/checksum 등) | 파이썬 변수 + 매 연산 뒤 `& 0xFFFFFFFF` 마스킹 |
| `rol`/`ror` | 파이썬에 없으므로 직접 헬퍼 함수 작성 필요 |
| `cmp X, const` + `je correct` | `return X == const` |

레지스터가 몇 번째 인자인지는 호출 규약에 따라 다르다. Windows x64는 정수 인자를 `RCX, RDX, R8, R9` 순서로 넘기고, Linux SysV x64는 `RDI, RSI, RDX, RCX, R8, R9` 순서로 넘긴다. PE 파일이면 Windows 규약, ELF 파일이면 SysV 규약을 먼저 확인해야 몇 번째 레지스터가 "입력 포인터"이고 몇 번째가 "길이"인지 헷갈리지 않는다. 다만 이 글의 예제처럼 함수 내부의 루프 로직 자체를 옮기는 단계에서는, 이미 레지스터에 값이 들어와 있다고 가정하고 로직만 보면 되므로 정확한 ABI 여부가 결과에 영향을 주지 않는다.

## 화면/코드에서 보이는 징후
- 루프 안에서 레지스터 하나가 계속 누적되고(`add`, `xor`, `imul`), 마지막에 상수와 `cmp` 하는 패턴
- `rol`/`ror` 명령어가 보이는데 IDA 디컴파일에서는 `__ROL4__(x, 3)` 같은 컴파일러 내장함수 형태로 표시됨
- 함수 인자가 `char *`(또는 `unsigned char *`)와 `int len`(또는 `size_t`) 두 개인 전형적인 "입력 버퍼 + 길이" 시그니처

## 가장 먼저 할 것
루프 본문의 명령어를 위에서 아래로 순서대로 나열하고, 오른쪽에 파이썬 한 줄씩을 대응시켜 표를 만든다. 이 표가 완성되면 그대로 함수로 조립하면 된다 — 별도로 "알고리즘이 뭔지" 고민할 필요가 없다.

## 단계별 절차

**1) 원본 어셈블리 확보**

다음과 같은 x64 어셈블리를 IDA에서 봤다고 하자(Intel 문법):
```asm
check_input:
    xor     eax, eax        ; eax = i = 0
    xor     ecx, ecx        ; ecx = hash = 0
.loop:
    movzx   edx, byte [rdi+rax]   ; edx = input[i]
    rol     ecx, 3                ; hash = rotate_left(hash, 3)
    add     ecx, edx              ; hash += input[i]
    inc     eax                   ; i++
    cmp     eax, esi              ; i < len ?
    jl      .loop
    cmp     ecx, 1A2B3C4Dh        ; compare final hash to target
    je      correct
    jmp     wrong
```

**2) 한 줄씩 매핑**

- `xor eax, eax` → `i = 0` (사실상 파이썬 `for` 루프가 대신 처리하므로 별도 변수 불필요)
- `xor ecx, ecx` → `h = 0`
- `movzx edx, byte [rdi+rax]` → `b = input_bytes[i]` (`rdi`=입력 버퍼 시작 주소, `rax`=인덱스)
- `rol ecx, 3` → 파이썬에는 회전 연산자가 없으므로 직접 만든다:
```python
def rol32(x, n):
    x &= 0xFFFFFFFF
    n &= 31
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF
```
- `add ecx, edx` → `h = (h + b) & 0xFFFFFFFF` — CPU의 32비트 레지스터는 오버플로 시 자동으로 상위 비트를 버리므로, 파이썬의 무한정밀도 정수가 그 동작을 흉내내려면 매번 마스킹해야 한다.
- `inc eax` / `cmp eax, esi` / `jl .loop` → 파이썬 `for i in range(len(input_bytes))`가 이 세 줄을 통째로 대체한다.
- `cmp ecx, 1A2B3C4Dh` / `je correct` → `return h == 0x1A2B3C4D`

**3) 전체 함수로 조립**

```python
def rol32(x, n):
    x &= 0xFFFFFFFF
    n &= 31
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF

def check(input_bytes: bytes) -> bool:
    h = 0
    for b in input_bytes:
        h = rol32(h, 3)
        h = (h + b) & 0xFFFFFFFF
    return h == 0x1A2B3C4D

# 개발 중 빠르게 손으로 테스트
print(check(b"test"))   # 우연히 목표 해시와 맞지 않는 이상 False
```

**4) 오라클로 활용해 브루트포스에 연결**

`check()`가 정확히 바이너리와 같은 동작을 한다고 확신했으면, 이제 이 함수를 "정답인지 아닌지 알려주는 오라클"로 써서 후보를 돌린다(길이를 어떻게 좁히는지는 rev-0218-length-check-backtrace.md, 브루트포스가 시간 안에 끝나는지는 rev-0219-bruteforce-feasibility.md 참고):

```python
from itertools import product
import string

CHARSET = string.ascii_lowercase
for length in range(1, 7):
    for combo in product(CHARSET.encode(), repeat=length):
        if check(bytes(combo)):
            print("FOUND:", bytes(combo))
            break
```

이 브루트포스가 언제까지 현실적인지 숫자로 확인해보자. 소문자 26자, 길이 6이면 `26^6`을 계산한다. `26^2=676`, `26^3=17576`, `26^6 = 17576^2 = 308,915,776`(약 3.09×10^8). 순수 파이썬으로 초당 약 10^6개를 시도한다고 가정하면 `308,915,776 / 1,000,000 ≈ 309`초, 약 5.2분이다. 길이 6까지는 그냥 기다리면 되지만, 글자 수나 문자셋이 더 커지면 이 브루트포스는 곧 비현실적이 된다 — 그럴 때는 파이썬 오라클을 브루트포스용이 아니라 역연산용으로 쓰는 게 낫다.

## 명령어/단축키
```python
# 왕복 검증: 회전 방향이 맞는지 확인
assert rol32(0x1, 1) == 0x2
assert rol32(0x80000000, 1) == 0x1
```
IDA: 루프 블록을 그래프뷰에서 선택 후 텍스트뷰(`Space`)로 전환하면 명령어 순서를 한 줄씩 정확히 옮기기 쉽다. Ghidra: 디컴파일 창에서 `__ROL4__` 같은 내장함수가 보이면 더블클릭해서 정의를 확인하면 회전 폭 인자 순서를 헷갈리지 않는다.

## 출력 해석
- `check()`가 알려진 정답 입력을 넣었을 때 `True`를 반환하지 않으면, 마스킹 누락이나 회전 방향 오류일 확률이 높다.
- 브루트포스 루프가 몇 분째 아무것도 못 찾고 있다면, 길이/문자셋 가정이 틀렸거나 애초에 이 접근이 아니라 역연산(REV-0221)이 필요한 상황일 수 있다.

## 흔한 실수
- 덧셈/곱셈/시프트 연산 뒤에 `& 0xFFFFFFFF` 마스킹을 빼먹는 것 — 파이썬 정수는 임의 정밀도라서 몇 번 반복하면 32비트 CPU 레지스터의 실제 동작(오버플로 시 상위 비트 버림)과 값이 완전히 갈라진다. 덧셈/곱셈/시프트 직후에 곧바로 마스킹하는 습관을 들여야 한다.
- 회전 방향을 반대로 구현하는 것 — x86의 `rol`(rotate left)은 비트를 상위 방향으로 밀어내면서 넘치는 비트를 최하위로 감아 넣는다. 검증은 아주 간단한 값으로 하면 된다: `rol32(0x1, 1)`은 `0x2`가 나와야 하고, `rol32(0x80000000, 1)`은 최상위 비트 하나만 있던 값이 왼쪽으로 밀려 넘치면서 최하위로 감기므로 정확히 `0x1`이 나와야 한다. 직접 계산해보면 `(0x80000000 << 1) & 0xFFFFFFFF = 0`이고 여기에 `x >> 31 = 1`을 OR 하므로 결과는 `1`. 두 값 다 맞으면 구현이 올바른 것이다.
- 해시류 루프를 "직접 역연산"하려 드는 것 — 이 예제처럼 `rol`과 `add`가 둘 다 개별적으로는 가역(rev-0221-is-it-invertible.md)이라도, 최종 32비트 해시 하나만 갖고 원래 입력 전체(길이가 해시 폭보다 긴 경우)를 복원하는 건 불가능하다. 여러 입력이 같은 해시로 압축될 수 있기 때문이다. 이런 경우 파이썬 포트는 "브루트포스용 오라클"로만 쓰고, 반대로 TEA/XTEA나 순수 XOR 체인처럼 라운드마다 완전히 가역인 구조라면 오라클이 아니라 역함수 자체를 파이썬으로 계산하는 게 맞다. 어느 쪽이 맞는지는 항상 rev-0221-is-it-invertible.md의 분류표로 먼저 판단해야 한다.

## 막혔을 때 다음 체크
- 레지스터가 몇 번째 함수 인자인지 헷갈린다면 → Windows PE는 RCX/RDX/R8/R9, Linux ELF는 RDI/RSI/RDX/RCX/R8/R9 순서이니 바이너리 포맷부터 확인.
- 브루트포스가 너무 오래 걸릴 것 같다면 → rev-0219-bruteforce-feasibility.md에서 정확한 소요 시간 계산법 확인.
- 이 루프가 해시가 아니라 완전히 되돌릴 수 있는 구조인지 애매하다면 → rev-0221-is-it-invertible.md의 연산별 표로 먼저 분류.
- 길이 자체를 아직 모른다면 → rev-0218-length-check-backtrace.md에서 길이 검증 코드를 역추적하는 법 확인.

## 미니 예제
위 절차 전체가 이미 하나의 완전한 미니 예제다. 정리하면:

1. 원본 어셈블리 8줄을 확보한다.
2. 각 줄을 레지스터→변수, 명령어→연산으로 매핑한다.
3. `rol32` 헬퍼를 만들고, 마스킹을 빠짐없이 넣어 `check()` 함수를 완성한다.
4. 알려진 문자열로 `check()`를 테스트해서 바이너리와 동일하게 동작하는지 확인한다(가능하면 실제 바이너리에 같은 입력을 넣고 x64dbg/GDB로 최종 `ecx` 값을 직접 읽어 대조하는 것이 가장 확실하다).
5. 오라클이 검증되면 브루트포스든 역연산이든 그 위에서 풀이를 진행한다.

이 순서를 지키면, "알고리즘 이름이 뭔지 몰라서 못 풀겠다"는 상황 자체가 거의 발생하지 않는다 — 이름을 몰라도 명령어를 그대로 옮기면 정확히 동일하게 동작하는 파이썬 함수를 만들 수 있기 때문이다.

## 관련 글
- [rev-0218-length-check-backtrace.md](./rev-0218-length-check-backtrace.md) — 브루트포스 전에 입력 길이를 먼저 알아내는 법
- [rev-0219-bruteforce-feasibility.md](./rev-0219-bruteforce-feasibility.md) — 파이썬 오라클을 브루트포스에 걸었을 때 시간이 현실적인지 계산하는 법
- [rev-0221-is-it-invertible.md](./rev-0221-is-it-invertible.md) — 파이썬 포트를 오라클(브루트포스용)로 쓸지 역함수로 쓸지 먼저 판단하는 기준

## 출처/검증
- x86 `ROL`/`ROR`의 비트 이동 방향 및 오버플로 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2 (ROL/ROR/RCL/RCR 명령어 정의) 기준 (2026-09-08 검증).
- Windows x64 및 System V AMD64 호출 규약의 정수 인자 레지스터 순서: Microsoft x64 calling convention 문서 및 System V AMD64 ABI 문서 기준.
