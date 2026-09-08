---
id: REV-0206
title: "음수 상수를 Unsigned Hex로 다시 읽기"
slug: "rev-0206-negative-to-unsigned-hex"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["음수 상수", "2의 보수", "signed unsigned 변환", "음수 hex 변환", "-1937337436"]
aliases: ["이상한 음수 상수", "디컴파일에 음수가 보임", "음수를 hex로", "signed 상수 변환"]
symptom_keywords: ["값이 갑자기 음수로 보임", "디컴파일 코드에 이상한 음수가 있음", "곱셈 상수가 음수임", "add에 큰 음수가 더해짐"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
IDA/Ghidra 디컴파일러가 `v1 = v1 + -1520786223;`처럼 이상하게 큰 음수 상수를 보여줄 때는, 이 값이 실제로는 **32비트(또는 64비트) unsigned hex 상수를 signed int로 잘못(?) 해석해서 출력한 것**뿐이므로, `& 0xFFFFFFFF`로 부호를 unsigned로 되돌리면 원래의 "낯익은" hex 상수(해시 초기값, 매직 넘버 등)가 그대로 드러난다.

## 언제 검색해야 하나
- 디컴파일 코드에 `+ -1234567890` 같은 이상한 음수 덧셈/뺄셈 상수가 보일 때
- `cmp eax, 0xFFFFFF9Ch`처럼 disassembly의 hex 상수가 디컴파일러에서는 `-100`처럼 음수로 표시될 때
- 곱셈 상수(해시 계산으로 의심되는 부분)가 음수로 나와서 "이게 무슨 상수인지" 감이 안 잡힐 때
- MASTER_PROMPT 검색 테스트 예시: `-87097619` 같은 이상한 음수를 그대로 검색창에 넣는 상황

## 핵심 개념
x86/x64는 부호 있는 정수를 **2의 보수(two's complement)** 방식으로 표현한다(REV-0024 참고). 32비트 레지스터의 최상위 비트가 1이면, CPU 입장에서는 이 값이 "아주 큰 unsigned 수"일 수도 있고 "음수"일 수도 있다 — 비트 패턴 자체는 완전히 동일하고, 오직 **그 값을 signed로 해석하느냐 unsigned로 해석하느냐**에 따라 사람이 읽는 표현만 달라진다.

디스어셈블리(asm)는 보통 상수를 hex로 그대로 보여주지만(`0xFFFFFF9C`), 디컴파일러(IDA/Ghidra)가 C 코드를 생성할 때는 변수의 선언 타입(`int` vs `unsigned int`)에 따라 그 값을 **부호 있는 10진수**로 바꿔서 보여주는 경우가 많다. 이때 `0xFFFFFF9C`가 `-100`으로 둔갑해서 나타난다.

변환 공식(32비트 기준):
```
signed_value = unsigned_value          (unsigned_value < 0x80000000일 때)
signed_value = unsigned_value - 0x100000000   (unsigned_value >= 0x80000000일 때)

역변환:
unsigned_value = signed_value & 0xFFFFFFFF
```
64비트는 `0x100000000` 대신 `0x10000000000000000`(2^64)을 쓴다.

이게 왜 리버싱에서 중요한가 — 해시 알고리즘의 매직 넘버(FNV offset basis, CRC 초기값, MurmurHash 상수 등)는 원래 unsigned hex로 정의되지만, 디컴파일러가 이를 signed int 변수에 대입하는 코드로 표현하면 전혀 못 알아볼 음수로 바뀌어 버린다. 이 변환을 모르면 "익숙한 상수를 보고도 못 알아채는" 상황이 발생한다.

## 화면/코드에서 보이는 징후
**디스어셈블리(원본):**
```asm
mov     eax, 811C9DC5h    ; unsigned hex 그대로 보임
```
**같은 값을 IDA/Ghidra가 디컴파일할 때(signed로 표시):**
```c
int h = -2128831035;      // 0x811C9DC5를 signed int로 읽으면 이 값
```
**비교 상수도 마찬가지:**
```asm
cmp     eax, 0FFFFFF9Ch   ; asm은 hex 그대로
```
```c
if (v == -100)            // 디컴파일러가 signed로 표시
```

## 가장 먼저 할 것
디컴파일 코드에 낯선 큰 음수가 보이면, **가장 먼저 32비트인지 64비트인지 변수 타입을 확인**하고, 파이썬으로 즉시 unsigned hex로 변환해서 "혹시 아는 상수인지" 확인한다.

## 단계별 절차
**1) 변수 타입(비트 폭) 확인**: IDA에서 변수 위에 커서를 놓고 `Y`(타입 지정)를 누르거나, 선언부의 `int`/`__int64` 여부를 확인.

**2) 파이썬으로 unsigned hex 변환**
```python
def to_u32(n: int) -> int:
    return n & 0xFFFFFFFF

def to_s32(n: int) -> int:
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n >= 0x80000000 else n

def to_u64(n: int) -> int:
    return n & 0xFFFFFFFFFFFFFFFF

print(hex(to_u32(-2128831035)))   # 0x811c9dc5  -> FNV offset basis!
print(hex(to_u32(-100)))          # 0xffffff9c
```

**3) 알려진 상수 목록과 대조**

| unsigned hex | 알려진 알고리즘 |
|---|---|
| `0x811C9DC5` | FNV-1/1a 32비트 offset basis |
| `0x01000193` | FNV-1/1a 32비트 prime |
| `0xEDB88320` | CRC-32(reflected) 다항식 |
| `0x04C11DB7` | CRC-32(normal) 다항식 |
| `0x9E3779B9` | 황금비 기반 해시 상수(예: Boost hash_combine) |
| `0xFFFFFFFF` (=`-1`) | 에러 코드/EOF 센티널로 흔히 쓰임 |

**4) IDA 자체 기능으로도 확인 가능**: 디스어셈블리 뷰(F5 이전의 원본 asm)로 돌아가 같은 위치의 hex 값을 직접 대조하면, 파이썬 변환 없이도 원본 hex를 바로 볼 수 있다. `Space`로 그래프뷰/텍스트뷰 전환, 디컴파일 창에서는 상수 위에서 `\`(백슬래시) 또는 우클릭 → "Number format" → "Hexadecimal"로 표시 형식을 바꿀 수 있는 경우도 있다.

## 명령어/단축키
- IDA: 디컴파일 창에서 상수 위 우클릭 → `Hexadecimal`(또는 단축키 `\`, 버전에 따라 다름)로 즉시 hex 표시 전환 — 파이썬 변환 없이 가장 빠른 방법
- Python: `n & 0xFFFFFFFF`(32비트), `n & 0xFFFFFFFFFFFFFFFF`(64비트)

## 출력 해석
- 변환한 unsigned hex가 알려진 표(위 목록)와 일치하면 해당 알고리즘 확정.
- 일치하는 게 없다면 커스텀 상수이므로, 최소한 "이 값이 32비트 unsigned로 어떤 값인지"는 확정해두고 다음 단계(해당 값이 곱셈 상수인지 초기값인지) 분석을 이어간다.

## 흔한 실수
- IDA 디컴파일 창의 숫자를 보고 "음수가 나왔으니 이 변수는 실제로 음수 값을 갖는다"고 그대로 믿어버리는 것 — 이건 표시 방식의 문제일 뿐, 비트 패턴 자체는 CPU 입장에서 unsigned로 쓰였을 수도 있다.
- 32비트와 64비트 변환 공식을 헷갈려서 `& 0xFFFFFFFF`를 64비트 값에 써버리는 것(상위 32비트를 실수로 날림) — 반드시 변수 크기(`int` vs `int64`/`long long`)를 먼저 확인.
- 변환 방향을 반대로 하는 것(unsigned를 signed로 바꿔야 하는데 반대로 계산) — 두 함수(`to_u32`/`to_s32`)를 명확히 구분해서 사용.

## 막혔을 때 다음 체크
- 변환한 값이 `0xFF`, `0xFFFF`, `0xFFFFFF`, `0xFFFFFFFF` 패턴이면 → REV-0203/REV-0204(마스크)를 의심.
- 변환한 값이 `16777619`나 `0x811C9DC5`라면 → REV-0207/REV-0208(FNV).
- 값이 2의 보수 자체가 왜 이렇게 동작하는지 원리부터 다시 보고 싶다면 → `../binary-basics/rev-0024-twos-complement.md`(2의 보수와 음수 표현).

## 미니 예제
**예제 1 — FNV 초기값을 못 알아본 경우**
```c
unsigned int h = -2128831035;
```
```python
print(hex(-2128831035 & 0xFFFFFFFF))  # 0x811c9dc5
```
→ FNV offset basis 확정, REV-0208 참고.

**예제 2 — 에러 코드 비교**
```c
if (ret == -1)
```
`-1`을 32비트 unsigned hex로 바꾸면 `0xFFFFFFFF` — 흔히 "실패/EOF" 센티널 값으로 쓰인다는 걸 바로 알 수 있다.

**예제 3 — 64비트 상수 변환**
```python
val = -3819410105021120000  # 디컴파일러가 보여준 __int64 값
print(hex(val & 0xFFFFFFFFFFFFFFFF))
```

## 관련 글
- REV-0203 — AND 0xFF 마스크 이해
- REV-0204 — AND 0xFFFFFF 24비트 마스크 이해
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- ./rev-0208-fnv-16777619.md — 16777619 상수가 보일 때 FNV 의심하기
- ../binary-basics/rev-0024-twos-complement.md — 2의 보수와 음수 표현

## 출처/검증
- 2의 보수 표현과 signed/unsigned 재해석 규칙은 Intel 64 and IA-32 Architectures Software Developer's Manual의 정수 표현 및 ISO C 정수 타입 규칙 기준.
- FNV/CRC 등 상수표는 각 알고리즘 공식 스펙 기준(2026-09-08 확인, REV-0208 출처 항목과 동일 자료 참고).
