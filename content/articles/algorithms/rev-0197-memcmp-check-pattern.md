---
id: REV-0197
title: "memcmp 기반 Flag 검증 패턴"
slug: "rev-0197-memcmp-check-pattern"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["memcmp", "flag 검증", "고정 길이 비교", "call memcmp", "rep cmpsb", "바이너리 비교"]
aliases: ["memcmp 뭐임", "memcmp이랑 strcmp 차이", "고정 길이 비교 함수", "해시값 비교"]
symptom_keywords: ["memcmp 세 번째 인자가 뭔지 모르겠음", "strcmp 없는데 비슷한 게 있음", "바이너리 데이터 비교", "16바이트 다이제스트 비교"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`memcmp(a, b, n)`은 `strcmp`와 달리 널(NUL) 종료를 신경 쓰지 않고 **정확히 n바이트를 그대로 비교**하며, 이 세 번째 인자(길이 `n`)를 disassembly에서 상수로 바로 읽을 수 있다는 점이 강력한 힌트가 된다 — 특히 해시/다이제스트(MD5=16바이트, SHA1=20바이트 등) 비교에서 흔히 등장한다.

## 언제 검색해야 하나
- `call memcmp` 직후 `test eax, eax`로 분기하는 코드를 만났을 때
- 비교 길이가 16, 20, 32처럼 잘 알려진 해시 다이제스트 크기로 보일 때 (MD5=16, SHA-1=20, SHA-256=32)
- flag 안에 널바이트(`\x00`)가 포함될 수 있는 이진 데이터 비교 상황
- `strcmp`가 아니라 `memcmp`가 Imports에 있고 그 세 번째 인자가 무엇인지 확인하고 싶을 때

## 핵심 개념
`memcmp(const void *a, const void *b, size_t n)`은 두 메모리 블록을 처음부터 정확히 `n`바이트 비교해서, 완전히 같으면 `0`, 다르면 첫 차이 바이트의 부호 있는 차이값(구현에 따라 다를 수 있음)을 반환한다. `strcmp`와의 결정적 차이는:

1. **NUL 바이트를 특별 취급하지 않는다.** 이진 데이터(해시값, 암호화된 블롭, 구조체)를 비교할 때 반드시 `memcmp`를 쓴다.
2. **길이가 명시적으로 필요하다.** 이 길이 인자가 disassembly에 상수로 박혀 있으므로, "비교 대상이 몇 바이트인지"를 소스코드 없이도 즉시 알 수 있다. 이는 `strcmp`보다 오히려 리버싱에 유리한 점이다 — flag 길이를 바로 확정할 수 있기 때문.

CTF에서 `memcmp`가 쓰이는 전형적인 상황:
- 사용자 입력을 해시(MD5, SHA-1, CRC32 등)로 변환한 뒤, 그 결과를 미리 정해둔 다이제스트와 `memcmp`로 비교
- flag 문자열 자체를 비교하지만 길이가 고정이라 컴파일러가 `strcmp` 대신 `memcmp`(또는 인라인된 워드 단위 비교)를 선택
- 구조체나 여러 필드를 한 번에 비교(예: `struct { int a; char b[12]; }`를 통째로 `memcmp`)

## 화면/코드에서 보이는 징후
**x64 리눅스 디스어셈블리:**
```asm
lea     rdi, [rbp-0x30]      ; 계산된 해시 버퍼
lea     rsi, [rip+0x2c10]    ; 정답 다이제스트 (예: MD5 16바이트)
mov     edx, 0x10            ; 길이 = 16 (memcmp 세 번째 인자)
call    memcmp
test    eax, eax
jne     wrong
```
`mov edx, 0x10`(=16)이 보이는 순간 "16바이트짜리 다이제스트 비교, 즉 MD5일 가능성이 높다"는 결론을 바로 낼 수 있다.

**x64 윈도우 디스어셈블리:**
```asm
lea     rcx, [computed_hash]
lea     rdx, [expected_hash]
mov     r8d, 20              ; 길이 = 20 -> SHA-1을 의심
call    memcmp
test    eax, eax
jne     wrong_label
```

**IDA/Ghidra 디컴파일:**
```c
if ( memcmp(computed_hash, expected_hash, 16) == 0 )
    puts("Correct!");
```
Ghidra는 세 번째 인자 상수(`16`)를 그대로 노출해주므로, 이 숫자만 봐도 어떤 해시 알고리즘 결과를 비교하는지 감을 잡을 수 있다.

**인라인 전개형(최적화 시):** 짧은 고정 길이(4바이트, 8바이트)는 컴파일러가 `memcmp` 호출 대신 워드/더블워드 단위 `cmp`로 직접 펼쳐버리기도 한다.
```asm
mov     eax, [rdi]
cmp     eax, [rsi]
jne     wrong
mov     eax, [rdi+4]
cmp     eax, [rsi+4]
jne     wrong
```
이건 여전히 "memcmp와 동일한 의미"이므로 같은 패턴으로 인식하면 된다.

## 가장 먼저 할 것
IDA Imports 탭에서 `memcmp`를 찾아 `X`로 xref를 추적하고, 호출 직전 **세 번째 인자(길이)**부터 확인한다. 길이가 유명한 해시 크기(16/20/32/64)와 일치하면 REV-0207/REV-0208(FNV)이나 REV-0209(CRC)와 함께 "해시 알고리즘 자체를 먼저 특정"하는 방향으로 분석을 넓힌다. 길이가 그냥 flag 길이(예: 20~40)면 REV-0196과 동일하게 값만 읽으면 끝이다.

## 단계별 절차
**1) 길이 인자로 1차 분류**

| 길이(바이트) | 의심되는 대상 |
|---|---|
| 4 | CRC32, FNV-1/1a(32비트), 단순 int 비교 |
| 8 | FNV(64비트), int64 비교 |
| 16 | MD5, MD4 |
| 20 | SHA-1 |
| 32 | SHA-256, FNV-1(256비트 변형은 드묾) |
| flag 길이와 동일(가변) | 문자열 자체를 직접 비교 |

**2) 비교 대상 버퍼 확인**

`memcmp`의 두 번째 인자(정답 쪽)가 리터럴 상수 배열이면 IDA에서 해당 주소를 `.rodata`/`.data`에서 바로 읽는다. Hex view(`Alt+8` 또는 View → Open subviews → Hex dump)로 raw byte를 확인하고, 파이썬으로 그대로 옮긴다.

```python
expected = bytes.fromhex("d41d8cd98f00b204e9800998ecf8427e")  # 예: 32자리 hex 문자열이면 16바이트
```

**3) 첫 번째 인자(계산된 값)가 어떻게 만들어지는지 역추적**

`memcmp`의 첫 번째 인자 버퍼가 어느 함수의 결과인지 추적한다. MD5/SHA 계열이면 표준 구현이므로 파이썬 `hashlib`으로 그대로 재현 가능:
```python
import hashlib

def try_password(guess: bytes) -> bytes:
    return hashlib.md5(guess).digest()

expected = bytes.fromhex("...")  # 바이너리에서 뽑은 16바이트
# expected와 같은 MD5를 만드는 입력을 찾아야 한다면 브루트포스/사전공격 영역
```

**4) 동적 검증**

x64dbg/gdb에서 `memcmp` 호출 시점에 브레이크를 걸고 인자 3개(버퍼1, 버퍼2, 길이)를 모두 덤프해서 정적 분석 결과와 대조한다.
```text
bp memcmp
run
dq rdi L2   ; 버퍼1 (계산된 값)
dq rsi L2   ; 버퍼2 (정답)
```
RDX(64비트 fastcall의 경우 세 번째 인자는 R8이지만 SysV에서는 RDX)에 담긴 길이 값도 함께 확인한다. (Windows x64: RCX, RDX, R8 / Linux SysV: RDI, RSI, RDX 순서를 헷갈리지 않도록 주의.)

## 명령어/단축키
- IDA: `Alt+8`(Hex View), `X`(xref), `A`(문자열/배열로 재해석)
- x64dbg: `bp memcmp`, `dq rdi`, `dq rsi`, Registers 창에서 R8(Windows) 확인
- gdb/pwndbg: `b memcmp`, `x/16xb $rdi`, `x/16xb $rsi`, `p $rdx`(길이 확인)
- Python: `hashlib.md5()`, `hashlib.sha1()`, `hashlib.sha256()`, `binascii.hexlify()`

## 출력 해석
- `memcmp` 반환값이 정확히 `0`이어야 통과. `test eax, eax` + `jne`(또는 `jnz`) 조합이 실패 분기라는 뜻이므로 EAX==0이 목표.
- 길이 인자가 눈에 보이는 dword/qword 상수와 정확히 일치하지 않으면(예: 15 vs 16), off-by-one으로 마지막 바이트를 비교에서 제외하는 트릭일 수 있으니 값을 다시 확인.
- 비교 대상 버퍼가 전부 `0x00`이거나 이상한 패턴이면, 실행 시점이 아직 그 버퍼가 채워지기 전일 수 있다 — 브레이크포인트 위치를 `call memcmp` 명령어 자체(호출 직전)로 다시 잡는다.

## 흔한 실수
- 길이 인자를 `edx`/`r8d`가 아니라 다른 레지스터에서 찾아서 헷갈리는 것. Windows x64와 Linux SysV의 인자 레지스터 순서가 다르므로 플랫폼부터 확인해야 한다.
- 다이제스트 크기(16/20/32)만 보고 "이건 반드시 MD5/SHA1/SHA256"이라고 단정하는 것. CRC64나 커스텀 16바이트 해시일 수도 있으므로, 실제 계산 루프(REV-0207/0208/0209)까지 확인해서 교차검증해야 한다.
- `memcmp`가 단방향 해시 비교에 쓰였는데 "값을 안다고 원문을 바로 구할 수 있다"고 착각하는 것. 해시라면 memcmp 자체는 역산 불가능한 부분이고, 원문 복원은 브루트포스나 알고리즘 자체의 약점에 의존해야 한다.
- 짧은 고정 길이 비교가 컴파일러에 의해 `memcmp` 호출 없이 인라인 `cmp`로 펼쳐진 걸 놓치고 "memcmp가 없으니 이 패턴이 아니다"라고 오판하는 것.

## 막혔을 때 다음 체크
- 비교 길이가 4바이트이고 곱셈/XOR 루프가 앞에 있다면 → REV-0207/REV-0208(FNV)을 의심.
- 비교 대상이 256개짜리 테이블을 참조하는 루프 뒤에 나온다면 → REV-0209(CRC)를 의심.
- 문자열 자체(가변 길이) 비교라면 → REV-0196(strcmp)과 사실상 동일하게 처리.
- 한 바이트씩 개별 비교하는 것처럼 보인다면 → REV-0198(문자별 for 루프 검증 패턴).

## 미니 예제
**예제 1 — MD5 다이제스트 비교**
```c
MD5(input, strlen(input), digest);
if ( memcmp(digest, "\xd4\x1d\x8c\xd9\x8f\x00\xb2\x04\xe9\x80\x09\x98\xec\xf8\x42\x7e", 16) == 0 )
    puts("Correct!");
```
이 16바이트는 유명한 "빈 문자열의 MD5"이므로, `hashlib.md5(b"").hexdigest()`로 즉시 검증 가능하다.

**예제 2 — 고정 길이 flag 자체 비교**
```asm
mov     edx, 14
lea     rdi, [rbp-0x20]
lea     rsi, [flag_bytes]
call    memcmp
```
길이 14는 유명 해시 크기가 아니므로 "flag 문자열 자체(14글자)"임을 바로 알 수 있다. `flag_bytes` 주소의 raw 14바이트를 Hex View로 그대로 읽으면 끝.

**예제 3 — 구조체 통째 비교**
```c
struct Check { int magic; char code[12]; };
if ( memcmp(&user_input_struct, &expected_struct, sizeof(struct Check)) == 0 )
    ...
```
길이가 16(4+12)으로 나오는데 MD5로 착각하기 쉬운 경우다. 이럴 땐 첫 4바이트가 구조적인 magic number 패턴(예: 반복되는 값, 아스키 매직)인지 먼저 확인해서 해시가 아님을 교차검증한다.

**예제 4 — Python으로 정답 바이트 재현**
```python
expected_hex = "48656c6c6f2c20464c414721"  # IDA Hex View에서 복사한 값
print(bytes.fromhex(expected_hex))          # b'Hello, FLAG!'
```

**예제 5 — 처음부터 끝까지 실행되는 전체 스크립트 (길이로 분류 → 각각 처리)**

`memcmp`의 세 번째 인자(길이)가 유명한 해시 크기인지 아닌지에 따라 대응 방법이 완전히 달라진다. 아래 스크립트는 (A) 길이가 flag 길이인 "고정 길이 문자열 직접 비교"와 (B) 길이가 16인 "MD5 다이제스트 비교"를 한 번에 실습해본다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# REV-0197 실전 스크립트: memcmp 세 번째 인자(길이)로 먼저 분류하고 각 경우를 처리한다.

import hashlib

# ========== (A) 길이가 12 -> 유명 해시 크기가 아니므로 "문자열 자체" 비교로 판단 ==========
length_a = 12                                     # 어셈블리의 mov edx, 12 (또는 mov r8d, 12)에서 읽은 값
dumped_hex_a = "48656c6c6f2c20464c414721"          # Hex View에서 복사한 12바이트 raw byte

expected_a = bytes.fromhex(dumped_hex_a)
assert len(expected_a) == length_a, "길이가 안 맞으면 hex를 잘못 복사했을 가능성이 크다"

flag_a = expected_a.decode()                       # 사람이 읽을 수 있는 문자열로 변환
print("(A) 고정 길이 비교 결과 flag:", flag_a)
# 실행 결과: (A) 고정 길이 비교 결과 flag: Hello, FLAG!

# ========== (B) 길이가 16 -> MD5 다이제스트 크기이므로 해시 비교로 판단 ==========
length_b = 16                                      # mov edx, 16 에서 읽은 값
dumped_hex_b = "d41d8cd98f00b204e9800998ecf8427e"  # Hex View에서 복사한 16바이트(예: 빈 문자열의 MD5)

expected_b = bytes.fromhex(dumped_hex_b)
assert len(expected_b) == length_b

# memcmp의 첫 번째 인자(계산된 값)가 어떤 입력의 MD5인지 프로그램 로직을 보고 추정한 뒤
# 그 후보 입력을 hashlib으로 직접 계산해서 두 값이 진짜 같은지 재현·대조한다.
candidate_input = b""                              # 예: 프로그램이 빈 입력을 그대로 해시했다고 가정
computed_hash = hashlib.md5(candidate_input).digest()

print("(B) 후보 입력의 MD5:", computed_hash.hex())
print("(B) 바이너리의 기대값과 일치?", computed_hash == expected_b)
# 실행 결과: (B) 후보 입력의 MD5: d41d8cd98f00b204e9800998ecf8427e
# 실행 결과: (B) 바이너리의 기대값과 일치? True
```

## 관련 글
- REV-0196 — strcmp 기반 Flag 검증 패턴
- REV-0198 — 문자별 for 루프 검증 패턴
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- ./rev-0208-fnv-16777619.md — 16777619 상수가 보일 때 FNV 의심하기
- REV-0209 — CRC 계열 알고리즘 흔적 찾기
- ../assembly/rev-0085-cmps.md — CMPS/문자열 비교 계열 명령어

## 출처/검증
- `memcmp` 동작(0 반환 = 완전 일치, NUL 특별 취급 없음)은 ISO C 표준 라이브러리 `string.h` 명세 기준.
- MD5/SHA-1/SHA-256 다이제스트 크기(16/20/32바이트)는 각 알고리즘의 RFC 명세(RFC 1321, FIPS 180-4) 기준.
- Windows x64 및 SysV AMD64 호출 규약의 인자 레지스터 순서는 각 공식 ABI 문서 기준(2026-09-08 확인).
