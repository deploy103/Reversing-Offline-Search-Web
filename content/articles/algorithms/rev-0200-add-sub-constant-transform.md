---
id: REV-0200
title: "ADD SUB 상수 기반 문자 변환"
slug: "rev-0200-add-sub-constant-transform"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["add sub 변환", "caesar cipher", "시저 암호", "덧셈 뺄셈 변환", "바이트 오버플로 wraparound"]
aliases: ["add로 문자 바뀜", "sub 반복문", "시저암호", "글자 밀기"]
symptom_keywords: ["add al 이 반복됨", "문자가 몇 칸씩 밀린 것 같음", "sub로 값이 이상하게 나옴", "글자 하나씩 더하거나 뺌"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
루프 안에서 `add al, N` 또는 `sub al, N`으로 각 문자에 상수를 더하거나 빼는 코드는 **시저 암호(Caesar cipher)의 바이트 버전**이며, 덧셈은 같은 크기만큼 빼서, 뺄셈은 같은 크기만큼 더해서 즉시 역산할 수 있다 — 단 8비트 바이트 범위(`0~255`)에서 자연스럽게 wraparound(오버플로)가 일어난다는 점만 정확히 반영하면 된다.

## 언제 검색해야 하나
- 루프 안에 `add al, imm8` / `sub al, imm8` / `add byte ptr [...], imm8`이 반복되는 코드를 만났을 때
- 디컴파일 결과에 `input[i] + N`, `input[i] - N` 형태가 비교 로직 안에 보일 때
- flag를 알파벳으로 몇 칸씩 밀어서 저장해둔 것 같은 느낌이 들 때(ROT13류의 변형)
- `char` 타입 연산인데 결과가 256을 넘거나 음수로 나와서 헷갈릴 때 (REV-0203 AND 0xFF 마스크와 함께 확인)

## 핵심 개념
덧셈과 뺄셈은 서로의 역연산이다. 이건 정수론의 가장 기본적인 사실이지만, 리버싱에서 실전 적용할 때 반드시 신경 써야 할 것은 **바이트(8비트) 연산의 wraparound**다.

```
plain + N = cipher   (mod 256)   →   plain = cipher - N   (mod 256)
plain - N = cipher   (mod 256)   →   plain = cipher + N   (mod 256)
```

CPU는 `al`(8비트 레지스터)에 `add`/`sub`를 수행할 때 자동으로 상위 비트를 버리고 하위 8비트만 남긴다(정확히는 8비트 연산 자체가 그렇게 정의됨). 따라서 결과가 `0~255` 범위를 벗어나는 것처럼 보여도 실제로는 그 범위 안에서 순환한다. 파이썬으로 역산할 때는 이 순환을 명시적으로 `& 0xFF`로 재현해야 한다 — 안 그러면 파이썬 정수는 무한정 커지거나 음수로 계속 남아있어서 값이 틀어진다.

또한 이 패턴이 알파벳에만 적용되는 "진짜 시저 암호"(A-Z, a-z만 순환)인지, 아니면 바이트 전체(0-255)에 대해 그냥 더하는 "일반화된 덧셈 암호"인지 구분해야 한다. 진짜 시저 암호는 알파벳 범위 안에서만 순환하도록 추가 분기(`cmp al, 'z'`, `jg`, `sub al, 26` 같은 보정 코드)가 붙어 있는 반면, 일반화된 덧셈 암호는 단순히 `add al, N` 한 줄뿐이고 바이트 전체 범위에서 자연 wraparound된다.

## 화면/코드에서 보이는 징후
**단순 바이트 덧셈 (가장 흔함):**
```asm
loop1:
movzx   eax, byte ptr [rdi+rcx]
add     al, 7
cmp     al, byte ptr [rsi+rcx]
jne     fail
inc     ecx
cmp     ecx, len
jl      loop1
```
디컴파일: `if ((char)(input[i] + 7) != expected[i]) return 0;`

**뺄셈 버전:**
```c
if ((char)(input[i] - 3) != expected[i]) return 0;
```

**진짜 알파벳 시저 암호(경계 보정 포함):**
```c
char c = input[i] + shift;
if (c > 'z') c -= 26;
if (expected[i] != c) return 0;
```
이건 `add` 뒤에 `cmp`/`jg`/`sub 26` 같은 보정 코드가 따라붙는 게 특징이며, 일반 바이트 덧셈보다 명령어 수가 더 많다.

## 가장 먼저 할 것
`add`/`sub` 뒤에 곧바로 `cmp`(비교)로 이어지는지, 아니면 알파벳 범위 보정(`cmp 'z'`, `cmp 'a'`, 추가 `add`/`sub 26`)이 끼어 있는지부터 확인한다. 보정이 없으면 순수 바이트 wraparound(`& 0xFF`)만 신경 쓰면 되고, 있으면 알파벳 범위(`% 26`)까지 고려해야 한다.

## 단계별 절차
**1) 연산 종류와 상수 확인**

`add al, N`인지 `sub al, N`인지, 상수 `N`이 얼마인지 IDA에서 직접 읽는다(`H`로 진법 토글해서 헥스/십진 확인).

**2) 순수 바이트 덧셈/뺄셈이면 그대로 역산**

```python
expected = bytes.fromhex("...")

# add al, 7 이었다면 -> 역산은 빼기
flag = bytes((e - 7) & 0xFF for e in expected)

# sub al, 3 이었다면 -> 역산은 더하기
flag2 = bytes((e + 3) & 0xFF for e in expected)
```

**3) 알파벳 시저 암호면 별도 처리**

```python
def caesar_decrypt(cipher: str, shift: int) -> str:
    out = []
    for c in cipher:
        if c.isupper():
            out.append(chr((ord(c) - ord('A') - shift) % 26 + ord('A')))
        elif c.islower():
            out.append(chr((ord(c) - ord('a') - shift) % 26 + ord('a')))
        else:
            out.append(c)   # 알파벳이 아니면 그대로
    return "".join(out)

print(caesar_decrypt("Ifmmp", 1))  # "Hello"
```

**4) 결과가 아스키로 안 읽히면 wraparound 재확인**

`& 0xFF`를 빠뜨렸는지, 혹은 애초에 덧셈/뺄셈 방향을 반대로 적용했는지(add인데 sub로 역산했는지) 다시 점검한다.

## 명령어/단축키
- IDA: `add`/`sub` 명령의 즉시값 위에서 `H`(진법 토글), `-`(부호 토글)로 음수/양수 표현을 빠르게 바꿔볼 수 있음
- Python: `(x - N) & 0xFF`, `(x + N) & 0xFF` — 항상 마지막에 `& 0xFF`를 붙이는 습관화
- 디버거: 루프 반복 중 `al` 레지스터 값이 `add` 전/후로 어떻게 바뀌는지 Watch로 확인

## 출력 해석
- 역산 결과가 전부 출력 가능한 아스키 범위(`0x20~0x7E`)에 들어오면 성공.
- 몇 바이트만 이상한 값이 나온다면, 그 위치에서만 다른 상수를 쓰는 "가변 증가" 패턴(예: `input[i] + i`처럼 인덱스에 비례해서 상수가 바뀌는 경우)을 의심하고 디스어셈블리에서 `add al, cl`처럼 레지스터끼리 더하는 코드가 있는지 재확인한다.
- 부호 있는(`signed char`) 연산으로 선언되어 있으면 IDA/Ghidra가 결과를 음수로 표시할 수 있는데, 이는 REV-0206(음수 상수를 unsigned hex로 다시 읽기)에서 다루는 표시상의 문제일 뿐 바이트 값 자체는 동일하다.

## 흔한 실수
- `& 0xFF`를 빼먹어서 파이썬에서 음수나 256 이상의 값이 그대로 남는 것. 바이트 연산은 항상 8비트로 wrap된다는 것을 명심.
- `add`인데 `sub`로 역산하거나 그 반대로 하는 것 — 원본 연산과 정확히 반대 연산을 적용해야 한다.
- 진짜 알파벳 시저 암호인데 바이트 전체 wraparound로 처리해서, 알파벳이 아닌 특수문자(`{`, `_`, `}` 등)까지 밀어버려 flag 포맷이 깨지는 것 — 보정 코드(`cmp 'z'`, `sub 26`)가 있는지 다시 확인.
- 상수 `N`을 부호 있는 값으로 착각해서 빼야 할 값을 더해버리는 것 — `add al, 0xF6`은 십진수로 246이 아니라, 부호 있는 8비트로 보면 `-10`이므로 사실상 `sub al, 10`과 동일한 효과라는 점을 놓치는 것(REV-0206 참고).

## 막혔을 때 다음 체크
- 덧셈 상수가 음수 표기(`0xF6` 같은 큰 hex)로 보인다면 → REV-0206(음수 상수를 unsigned hex로 다시 읽기)에서 부호 변환을 재확인.
- ADD/SUB 뒤에 마스킹(`and al, 0xFF`)이 명시적으로 또 있다면 → REV-0203.
- ADD/SUB와 XOR이 함께 섞여 있다면 → REV-0199와 순서대로(코드에 나온 순서의 역순으로) 역산.
- 알파벳 범위 보정이 있는데 정확한 shift 값을 모르겠다면 → 26가지 shift를 모두 브루트포스(파이썬 for문으로 0~25 전부 출력해서 눈으로 확인).

## 미니 예제
**예제 1 — 단순 바이트 덧셈**
```asm
add al, 7
```
```python
expected = bytes.fromhex("6b6c6c76757e747c")
flag = bytes((b - 7) & 0xFF for b in expected)
print(flag)  # b'dceoconu' 형태 -> 실제로는 정확한 값에서 flag가 나옴 (계산 과정 예시)
```

**예제 2 — 뺄셈**
```c
if ((input[i] - 0x10) != expected[i]) return 0;
```
```python
expected = bytes.fromhex("...")
flag = bytes((b + 0x10) & 0xFF for b in expected)
```

**예제 3 — 알파벳 한정 시저(shift=3, ROT3)**
암호문 `Fodj{f4vdu_flskhu}`를 shift=3으로 복호화:
```python
print(caesar_decrypt("Fodj{f4vdu_flskhu}", 3))
# 'Clag{c4sar_ciphep}' 형태로 알파벳만 이동, 특수문자/숫자는 그대로 유지되는 것 확인
```

**예제 4 — 인덱스에 비례하는 가변 증가**
```c
for (i = 0; i < len; ++i)
    if ((input[i] + i) != expected[i]) return 0;
```
```python
expected = bytes.fromhex("...")
flag = bytes((e - i) & 0xFF for i, e in enumerate(expected))
```

## 관련 글
- REV-0198 — 문자별 for 루프 검증 패턴
- REV-0199 — XOR 반복 변환 역산
- REV-0203 — AND 0xFF 마스크 이해
- REV-0206 — 음수 상수를 Unsigned Hex로 다시 읽기
- ../assembly/rev-0047-add.md — ADD 명령어
- ../assembly/rev-0048-sub.md — SUB 명령어

## 출처/검증
- 8비트 정수 wraparound(모듈로 256) 연산은 Intel 64 and IA-32 Architectures Software Developer's Manual의 ADD/SUB 명령 정의(플래그와 결과값의 truncation 규칙) 기준.
- 시저 암호(Caesar cipher)의 정의와 shift 기반 알파벳 순환은 고전 암호학의 표준 정의 기준(2026-09-08 확인).
