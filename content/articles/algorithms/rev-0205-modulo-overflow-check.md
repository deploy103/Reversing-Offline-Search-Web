---
id: REV-0205
title: "Modulo와 오버플로를 이용한 검증"
slug: "rev-0205-modulo-overflow-check"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["modulo", "나머지 연산", "idiv", "magic number division", "정수 오버플로", "체크섬 mod"]
aliases: ["mod 연산 역산", "나머지 검증", "idiv 이상한 상수", "매직넘버 나눗셈"]
symptom_keywords: ["idiv 뒤에 이상한 곱셈이 있음", "나머지 연산이 이상한 상수로 최적화됨", "오버플로로 검증하는 것 같음", "mod로 값이 좁아짐"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
나머지 연산(`%`, `mod`)은 여러 입력이 같은 출력을 만들 수 있는 **다대일(many-to-one) 연산**이라 일반적으로 완전히 역산할 수 없지만, 검증 로직이 "누적 합/곱의 결과가 특정 나머지(또는 32비트 오버플로 후 특정 값)와 같아야 한다"는 형태라면 자유도가 있는 바이트 하나를 이용해 **원하는 나머지를 정확히 맞추는 값을 방정식으로 계산**할 수 있다.

## 언제 검색해야 하나
- `idiv`/`div` 명령 뒤에 나머지(`edx`)를 사용하는 코드, 또는 반대로 `imul`과 `shr`/`sar`가 조합된 이상한 상수 곱셈(나머지 연산의 최적화된 형태)이 보일 때
- 디컴파일 결과에 `% N` 연산자가 그대로 보일 때(2의 거듭제곱 나머지는 `& (N-1)`로 최적화되어 REV-0203/0204와 겹쳐 보일 수 있음)
- 체크섬/합계가 특정 값으로 "딱 맞아떨어져야" 통과하는 검증 로직을 만났을 때
- 32비트 정수 곱셈/덧셈이 반복되며 최종적으로 오버플로된 값을 목표값과 비교하는 코드를 만났을 때

## 핵심 개념
**나머지 연산의 두 가지 컴파일 형태**

1. **모듈러스가 2의 거듭제곱**(예: `% 256`, `% 16`): 컴파일러는 나눗셈을 아예 쓰지 않고 `AND` 마스크로 바꿔버린다. `x % 256`은 `x & 0xFF`(REV-0203)와 완전히 동일하고, `x % 65536`은 `x & 0xFFFF`와 동일하다.
2. **모듈러스가 2의 거듭제곱이 아님**(예: `% 10`, `% 97`): CPU의 `div`/`idiv`는 느리기 때문에, 최적화된 컴파일러는 나눗셈을 **"매직 넘버(magic number)를 곱하고 시프트하는" 조합**으로 바꿔버린다. 이걸 "매직 넘버 나눗셈(magic number division)"이라 부른다. 겉보기엔 이상한 곱셈 상수(`0x66666667` 같은)와 `sar`/`shr`가 함께 나오는데, 실제로는 나눗셈/나머지 연산이라는 뜻이다.

매직 넘버 나눗셈의 전형적인 형태(`x / 10`을 계산하는 예):
```asm
mov     eax, x
mov     edx, 0x66666667      ; 10으로 나누기 위한 매직 넘버 (2^35 / 10 근사값 기반)
imul    edx
sar     edx, 2               ; edx가 몫(quotient)
```
나머지는 몫을 다시 원래 모듈러스와 곱해서 뺀 값으로 구한다: `remainder = x - quotient * 10`. 이 패턴 전체가 `x % 10`이나 `x / 10`을 계산하는 것임을 알아채는 게 중요하다.

**오버플로를 이용한 검증**

32비트(또는 64비트) 정수 연산은 결과가 레지스터 폭을 넘으면 자동으로 상위 비트가 잘린다(REV-0203의 8비트 wraparound와 같은 원리를 32/64비트로 확장한 것). 어떤 검증 로직이 "여러 바이트를 곱하거나 더한 결과가 정확히 특정 32비트 값과 같아야 한다"는 형태라면, 이는 사실상 `mod 2^32` 연산과 동일하다. 곱셈/덧셈이 섞여 있어도, 마지막 한 바이트(또는 한 항)를 변수로 남겨두면 나머지 방정식을 풀어서 정확히 그 값을 구할 수 있다.

## 화면/코드에서 보이는 징후
**2의 거듭제곱 나머지(AND로 최적화됨):**
```c
if ((sum % 256) != target) return 0;   // sum & 0xFF 와 동일
```

**비2의 거듭제곱 나머지(매직 넘버):**
```c
int r = value % 97;
if (r != target) return 0;
```
```asm
mov     eax, value
mov     edx, 0x8880881B   ; 97으로 나누기 위한 매직 넘버 예시 형태
imul    edx
...
sar     edx, N
imul    eax, edx, 97
sub     ecx, eax           ; ecx = value - quotient*97 = remainder
```

**오버플로 기반 검증(체크섬 방정식):**
```c
unsigned int total = 1;
for (i = 0; i < len; ++i)
    total = total * 31 + input[i];    // 다항식 해시, 32비트 자동 오버플로
if (total != 0xCAFEBABE) return 0;
```

## 가장 먼저 할 것
모듈러스가 **2의 거듭제곱인지 아닌지**부터 확인한다. 2의 거듭제곱이면 REV-0203/0204와 동일하게 그냥 AND 마스크로 처리하면 되고, 아니면 매직 넘버 나눗셈 패턴을 인식해서 실제 모듈러스 값(`div ebx`나 `imul edx, 0x97` 같은 후속 곱셈에 등장하는 상수)을 역추적한다.

## 단계별 절차
**1) 나머지/오버플로 검증의 자유도 확인**

체크섬처럼 마지막 바이트 하나만 자유롭게 고를 수 있는 구조인지 확인한다. 그렇다면 나머지 바이트를 미리 고정하고 방정식을 풀 수 있다.

**2) 단순 합 체크섬 역산**
```python
data_prefix = b"CTF{partial"
target = 42          # sum(data) % 97 == target
mod = 97
partial = sum(data_prefix) % mod
# 마지막 바이트 x를 구하는 방정식: (partial + x) % 97 == target
x = (target - partial) % mod
print(x)   # 0~96 범위의 값. 아스키 범위(32~126)에 없으면 더 뒤쪽 바이트 여러 개로 분배해야 함
```

**3) 다항식 해시형 오버플로 역산 (곱셈이 홀수 배수일 때 모듈러 역원 이용)**
```python
MOD = 1 << 32
MULT = 31

def mod_inverse(a: int, m: int) -> int:
    return pow(a, -1, m)   # MULT가 MOD와 서로소(홀수)일 때만 가능

target = 0xCAFEBABE
prefix = b"CTF{"
total = 1
for b in prefix:
    total = (total * MULT + b) % MOD

# 마지막 한 바이트 x를 구하고 싶다면:
# target == (total * MULT + x) % MOD  ->  x = (target - total*MULT) % MOD (단, x가 0~255 범위인지 확인)
x = (target - total * MULT) % MOD
print(x if x < 256 else "직접 대입으로 뒤쪽 여러 바이트를 함께 조정해야 함")
```
곱셈 상수(`MULT`)가 짝수라면 모듈러 역원이 존재하지 않을 수 있으므로(홀수여야 `mod 2^32`에서 항상 역원 존재), 이 경우 방정식을 풀기보다 브루트포스로 접근하는 게 더 현실적일 수 있다.

**4) 매직 넘버 나눗셈이면 우선 실제 모듈러스부터 특정**

디스어셈블리에서 매직 넘버 곱셈 뒤에 `imul eax, edx, N`처럼 원래 모듈러스 `N`을 다시 곱하는 코드가 있는지 찾는다. 이 `N`이 진짜 나머지 연산의 모듈러스다. (예: `% 97`이면 최종적으로 `97`이라는 상수가 코드 어딘가에 다시 나타난다.)

## 명령어/단축키
- IDA: `imul`/`idiv` 근처 상수를 `H`로 진법 토글, Hex-Rays는 매직 넘버 나눗셈을 자동으로 `% N`이나 `/ N`으로 깔끔하게 복원해주는 경우가 많으므로 **디컴파일(F5) 결과를 우선 신뢰**하고, 원본 asm은 교차검증용으로만 사용
- Python: `pow(a, -1, m)`(모듈러 역원, Python 3.8+)

## 출력 해석
- 계산한 `x`가 아스키 범위를 벗어나면(0~255는 맞아도 flag 문자로 부적합), 자유도를 가진 바이트가 하나가 아니라 여러 개일 가능성을 고려해서 마지막 몇 바이트를 함께 조정하는 방식으로 다시 접근한다.
- Hex-Rays가 이미 `% N`으로 깔끔하게 복원했다면 매직 넘버 asm 패턴을 굳이 손으로 해석할 필요 없이 그 값을 그대로 믿어도 된다(단, 다른 컴파일러/버전에서 오역이 있었다는 보고가 있으면 원본 asm과 대조).

## 흔한 실수
- 나머지 연산이 "완전히 역산 가능하다"고 착각하는 것 — 나머지는 본질적으로 정보 손실이 있는 다대일 연산이다. 자유도(자유롭게 정할 수 있는 바이트)가 있을 때만 "그 자유도를 이용해 원하는 나머지를 맞추는" 방식으로 풀 수 있는 것이지, 임의의 나머지 검증을 항상 역산할 수 있는 건 아니다.
- 매직 넘버 나눗셈 상수(`0x66666667` 같은)를 보고 이걸 그냥 "이상한 해시 상수"로 오인해서 REV-0207(FNV) 같은 걸로 착각하는 것 — `imul` 직후 `sar`/`shr`로 몫을 뽑아내는 전형적인 조합이 있으면 나눗셈 최적화임을 먼저 의심해야 한다.
- 곱셈 상수가 짝수인 다항식 해시에서 모듈러 역원이 존재하지 않는데도 `pow(a, -1, m)`을 그대로 써서 예외가 나는 것 — 곱셈 상수의 홀짝을 먼저 확인.

## 막혔을 때 다음 체크
- 모듈러스가 2의 거듭제곱이면 → REV-0203/REV-0204(AND 마스크)로 훨씬 간단하게 처리 가능.
- 곱셈-XOR 조합이 함께 있다면 → REV-0207/REV-0208(FNV).
- 256개 테이블을 참조하는 나머지형 구조라면 → REV-0209(CRC, 다항식 나눗셈의 일종).
- 상수가 음수로 표시되어 알아보기 힘들다면 → REV-0206.

## 미니 예제
**예제 1 — 2의 거듭제곱 나머지(AND로 위장)**
```c
if ((sum(input) % 128) != 0x2A) return 0;
```
`128 = 2^7`이므로 `sum & 0x7F`와 동일. 자유도 있는 바이트로 바로 방정식 풀이 가능.

**예제 2 — 소수 모듈러스 체크섬**
```python
data_prefix = b"flag{mod_"
mod = 97
target = 55
partial = sum(data_prefix) % mod
x = (target - partial) % mod
print(chr(x) if 32 <= x <= 126 else x)
```

**예제 3 — 32비트 오버플로 다항식 해시**
```c
unsigned int h = 0;
for (i = 0; input[i]; i++)
    h = h * 131 + input[i];
if (h != 0x9E3A21F0) return 0;
```
곱셈 상수 131은 홀수이므로 모듈러 역원 존재 → 뒤에서부터 순서대로 역산 가능(각 단계에서 `h_prev = (h_cur - input[i]) * inverse(131) mod 2^32`).

**예제 4 — 처음부터 끝까지 실행되는 전체 스크립트 (소수 모듈러스 체크섬 + 다항식 해시, 두 케이스 모두 역산)**

나머지 연산은 여러 입력이 같은 결과를 만들 수 있는 다대일 연산이라, 방정식으로 구한 값을 "그대로" 믿으면 안 되고 반드시 아스키 범위 안에서 실제로 맞는 후보를 찾아야 한다. 아래 스크립트는 이 점까지 반영해서 실제로 검증된 값을 계산한다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# REV-0205 실전 스크립트: (A) 소수 모듈러스 체크섬의 자유 바이트 역산과
# (B) 32비트 오버플로 다항식 해시의 마지막 바이트 역산을 모두 다룬다.

# ===== (A) sum(data) % 97 == target 형태의 체크섬 =====
mod = 97
data_prefix_a = b"flag{mod_97"     # 이미 알고 있는 flag의 앞부분(마지막 한 글자만 모름)
target_a = 21                      # 바이너리에서 확인한 "sum % 97 이어야 하는 값"

partial_a = sum(data_prefix_a) % mod
residue = (target_a - partial_a) % mod
print("나머지 방정식으로 구한 residue:", residue)
# 실행 결과: 나머지 방정식으로 구한 residue: 28

# residue 자체가 곧 실제 바이트값이 아닐 수 있다(나머지 연산은 다대일이기 때문).
# 그래서 "0~255 범위에서 mod 97한 나머지가 residue와 같고, 동시에 출력 가능한 아스키인" 값을
# 전부 찾아서 그중에서 진짜 후보를 고른다.
candidates = [x for x in range(256) if x % mod == residue and 32 <= x <= 126]
print("아스키 범위의 후보들:", candidates, [chr(c) for c in candidates])
# 실행 결과: 아스키 범위의 후보들: [125] ['}']  -> 후보가 딱 하나뿐이므로 이 값으로 확정한다.

recovered_char = chr(candidates[0])
print("복원한 마지막 문자:", recovered_char)
# 실행 결과: 복원한 마지막 문자: }

# ===== (B) h = h*131 + input[i] (mod 2**32) 형태의 다항식 해시 =====
MOD = 1 << 32
MULT = 131   # 홀수이므로 mod 2**32에서 곱셈의 역원이 항상 존재한다(짝수면 존재하지 않을 수 있음)

def poly_hash(data: bytes, mult: int = MULT) -> int:
    h = 0
    for b in data:
        h = (h * mult + b) & 0xFFFFFFFF     # 32비트 자동 오버플로를 & 0xFFFFFFFF로 그대로 재현
    return h

known_prefix_b = b"CTF{poly_hash"     # 마지막 '}' 한 글자를 제외한 나머지(이미 알고 있음)
target_b = 0x291C4C06                  # 바이너리에서 확인한 최종 해시 목표값

h_prefix = poly_hash(known_prefix_b)
# target = h_prefix * MULT + x (mod 2**32) 라는 방정식을 x에 대해 풀면:
# x = target - h_prefix * MULT (mod 2**32)
x = (target_b - h_prefix * MULT) & 0xFFFFFFFF
print("복원한 마지막 바이트:", x, repr(chr(x)) if x < 256 else "범위 밖")
# 실행 결과: 복원한 마지막 바이트: 125 '}'

# 실제로 이어붙여서 다시 해시를 계산해보고 목표값과 일치하는지 최종 재검증한다.
full_b = known_prefix_b + bytes([x])
print("최종 검증:", hex(poly_hash(full_b)), "== 목표값", hex(target_b))
# 실행 결과: 최종 검증: 0x291c4c06 == 목표값 0x291c4c06
```

## 관련 글
- REV-0203 — AND 0xFF 마스크 이해
- REV-0204 — AND 0xFFFFFF 24비트 마스크 이해
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- ../assembly/rev-0052-div.md — DIV 명령어
- ../assembly/rev-0053-idiv.md — IDIV 명령어

## 출처/검증
- 매직 넘버 나눗셈(정수 상수 나눗셈을 곱셈+시프트로 대체하는 컴파일러 최적화)은 Henry S. Warren, "Hacker's Delight" 및 GCC/LLVM 최적화 문서에서 널리 다루는 표준 기법 기준.
- 모듈러 역원과 `pow(a, -1, m)`은 Python 3.8+ 공식 문서(`pow()` 내장 함수의 modular inverse 지원) 기준(2026-09-08 확인).
