---
id: REV-0272
title: "Capstone으로 디스어셈블 자동화"
slug: "rev-0272-capstone-basics"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python, Capstone]
keywords: ["Capstone", "디스어셈블러 라이브러리", "CS_ARCH_X86", "CS_MODE_64", "md.disasm", "mnemonic operand", "파이썬 디스어셈블", "커스텀 디스어셈블 패스"]
aliases: ["capstone 파이썬", "capstone 사용법", "디스어셈블 스크립팅", "capstone disasm 예제"]
symptom_keywords: ["capstone 어떻게 씀", "바이너리 코드 자동으로 디스어셈블", "mnemonic 자동 추출", "명령어 목록 자동 분석", "capstone CS_ARCH CS_MODE 뭐임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`Capstone`은 IDA/Ghidra 같은 GUI 없이도 파이썬 코드에서 raw 바이트열을 어셈블리 명령어(mnemonic + operand)로 변환해주는 경량 디스어셈블러 라이브러리로, `Cs(CS_ARCH_X86, CS_MODE_64)`로 엔진을 만들고 `md.disasm(code, addr)`을 반복문으로 돌리면 대량의 코드를 스크립트로 자동 분석할 수 있다.

## 언제 검색해야 하나
- IDA/Ghidra 없이 파이썬만으로 특정 바이트열이 어떤 명령어인지 빠르게 확인하고 싶을 때
- 바이너리 안의 특정 함수 범위를 대상으로 특정 패턴(예: 모든 `call` 명령어, 특정 opcode 사용 위치)을 자동으로 수집하는 스크립트를 짜고 싶을 때
- Unicorn(REV-0273)으로 에뮬레이션하기 전에, 대상 코드 블록에 어떤 명령어들이 들어있는지 먼저 사람이 읽을 수 있는 형태로 확인하고 싶을 때
- 메모리 덤프나 셸코드 조각처럼 실행 파일 구조가 없는 raw 바이트열을 디스어셈블해야 할 때

## 핵심 개념
`Capstone`은 다중 아키텍처를 지원하는 오픈소스 디스어셈블 엔진으로, x86/x64뿐 아니라 ARM, MIPS 등도 지원한다. IDA나 Ghidra가 "바이너리 파일 전체를 로드하고 분석하는 무거운 GUI 도구"라면, Capstone은 "바이트열 하나를 넣으면 명령어로 바꿔주는 가벼운 라이브러리 함수"에 가깝다. 그래서 GUI를 켤 필요 없이 스크립트 안에서 즉석으로, 또는 대량의 바이트열에 대해 반복적으로 디스어셈블 작업을 자동화하는 데 적합하다.

기본 사용 흐름은 세 단계다.

1. **엔진 생성** — `Cs(arch, mode)`로 디스어셈블 엔진 객체를 만든다. `arch`는 `CS_ARCH_X86`, `CS_ARCH_ARM` 등 아키텍처 종류를, `mode`는 `CS_MODE_32`/`CS_MODE_64`처럼 비트 폭이나 세부 모드를 지정한다. x64 코드를 다룬다면 `Cs(CS_ARCH_X86, CS_MODE_64)`가 표준 조합이다.
2. **디스어셈블 실행** — `md.disasm(code, addr)`을 호출한다. `code`는 디스어셈블할 raw 바이트열(`bytes`), `addr`은 이 코드가 메모리에 로드됐다고 가정할 시작 주소다. 이 함수는 명령어 하나하나를 나타내는 객체들을 순서대로 만들어내는 제너레이터를 반환한다.
3. **결과 순회** — `for insn in md.disasm(code, addr):` 형태로 반복하면서 각 `insn` 객체의 `insn.address`(주소), `insn.mnemonic`(명령어 이름, 예: `mov`), `insn.op_str`(오퍼랜드 문자열, 예: `eax, ebx`)을 읽어낸다.

Capstone은 어디까지나 "디스어셈블(바이트 → 명령어 텍스트)"만 하는 도구이지, 실제로 코드를 실행하지는 않는다는 점이 중요하다. 명령어가 실제로 어떤 값을 만들어내는지 보려면 Unicorn(REV-0273)처럼 에뮬레이션 엔진이 별도로 필요하다. 반대로 실제 실행 없이 "이 코드에 어떤 명령어가 있는지"만 빠르게 훑고 싶을 때는 Capstone만으로 충분하고 훨씬 빠르다.

## 화면/코드에서 보이는 징후
- `from capstone import *`로 시작하고 `CS_ARCH_X86`, `CS_MODE_64`, `CS_MODE_32` 같은 대문자 상수가 등장한다.
- `md = Cs(CS_ARCH_X86, CS_MODE_64)` 형태로 엔진 객체를 한 번 만들고 재사용한다.
- `for insn in md.disasm(code, 0x1000):` 반복문 안에서 `insn.mnemonic`, `insn.op_str`, `insn.address`를 조합해 출력하는 코드가 있다.
- `md.detail = True`를 설정한 뒤 `insn.operands`처럼 오퍼랜드를 더 세밀하게(레지스터 번호, 즉시값 등) 분석하는 코드가 있다 — 상세 모드는 기본보다 느리지만 정보가 더 풍부하다.
- 결과 출력이 `0x1000:  mov  eax, ebx`처럼 주소, mnemonic, operand 세 부분으로 정렬되어 있다.

## 가장 먼저 할 것
디스어셈블하려는 바이트열이 정확히 어떤 아키텍처/모드로 만들어졌는지부터 확인한다(32비트 x86인지 64비트 x64인지, PE인지 ELF인지). `CS_MODE_32`로 열어야 할 코드를 `CS_MODE_64`로 열면 명령어 경계가 완전히 어긋나서 전혀 다른(의미 없는) 명령어들이 출력된다. 파일 헤더(PE의 `Machine` 필드, ELF의 `e_machine` 필드)나 `file` 명령으로 아키텍처를 먼저 확인하는 습관이 중요하다.

## 단계별 절차

**1) 설치 확인**

```bash
pip install capstone
python3 -c "import capstone; print(capstone.__version__)"
```

**2) 가장 단순한 예: 짧은 바이트열 디스어셈블**

```python
from capstone import *

# mov eax, ebx ; add eax, 5 ; ret 에 해당하는 x64 기계어 바이트열
code = b'\x89\xd8\x83\xc0\x05\xc3'

md = Cs(CS_ARCH_X86, CS_MODE_64)
for insn in md.disasm(code, 0x1000):
    print(f'0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}')
```

출력 예시:

```text
0x1000: mov     eax, ebx
0x1002: add     eax, 5
0x1005: ret
```

**3) 실제 실행 파일에서 특정 구간 읽어와 디스어셈블**

```python
from capstone import *

with open('chall', 'rb') as f:
    f.seek(0x1000)          # 파일 오프셋(예: .text 섹션 시작 근처)
    code = f.read(0x100)     # 256바이트만 읽기

md = Cs(CS_ARCH_X86, CS_MODE_64)
for insn in md.disasm(code, 0x401000):  # 실제 로드 주소(가상주소)로 지정
    print(f'0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}')
```

파일 오프셋과 실제 가상주소(virtual address)는 다를 수 있으므로, `disasm()`의 두 번째 인자에는 반드시 "이 코드가 실행될 때의 가상주소"를 넣어야 상대주소 오퍼랜드(`call`, `jmp`의 대상 등)가 올바르게 계산되어 출력된다.

**4) 특정 명령어 패턴 자동으로 수집하기(예: 모든 call 찾기)**

```python
from capstone import *

code = b'\x89\xd8\xe8\x10\x00\x00\x00\x83\xc0\x05\xc3'
md = Cs(CS_ARCH_X86, CS_MODE_64)

call_targets = []
for insn in md.disasm(code, 0x401000):
    if insn.mnemonic == 'call':
        call_targets.append((insn.address, insn.op_str))

print(call_targets)
```

**5) 상세 모드(detail)로 오퍼랜드 구조 뜯어보기**

```python
from capstone import *

code = b'\x89\xd8'  # mov eax, ebx
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

for insn in md.disasm(code, 0x1000):
    print(insn.mnemonic, insn.op_str)
    for op in insn.operands:
        if op.type == CS_OP_REG:
            print('  reg operand:', insn.reg_name(op.reg))
        elif op.type == CS_OP_IMM:
            print('  imm operand:', hex(op.imm))
```

## 명령어/단축키
- `Cs(CS_ARCH_X86, CS_MODE_64)` : x64 디스어셈블 엔진 생성(`CS_MODE_32`는 32비트용)
- `md.disasm(code, addr)` : 바이트열을 명령어 스트림으로 변환(제너레이터 반환)
- `insn.address` / `insn.mnemonic` / `insn.op_str` : 주소 / 명령어 이름 / 오퍼랜드 문자열
- `insn.size` : 이 명령어가 차지하는 바이트 수(가변 길이 x86 명령어 분석에 유용)
- `md.detail = True` + `insn.operands` : 오퍼랜드를 레지스터/즉시값/메모리 단위로 세분화
- `insn.reg_name(reg_id)` : 레지스터 번호를 사람이 읽는 이름(`eax` 등)으로 변환

## 출력 해석
- `mnemonic`이 `.byte` 또는 이상한 짧은 조각들로만 계속 나온다면 아키텍처/모드(`CS_MODE_32` vs `CS_MODE_64`)가 실제 코드와 맞지 않을 가능성이 크다.
- 디스어셈블이 중간에 멈추고 그 뒤 바이트가 출력되지 않는다면, 그 지점에서 Capstone이 유효한 명령어로 해석할 수 없는 바이트를 만났다는 뜻이다 — 데이터 영역이 코드 영역에 섞여 있거나(점프 테이블, 문자열 리터럴), 진짜 코드 시작 위치를 잘못 잡았을 수 있다.
- `call`/`jmp`의 `op_str`에 나온 주소가 실제 함수 목록과 안 맞는다면, `disasm()`에 넘긴 `addr` 인자(가상주소)가 파일 오프셋과 혼동되어 잘못 계산됐을 가능성이 크다.
- `insn.size`를 합산한 값이 원래 `code` 바이트열의 길이와 다르면, 마지막 몇 바이트가 완전한 명령어를 이루지 못해 디스어셈블에서 빠졌다는 뜻이다 — 버퍼를 더 넉넉히 읽어와야 할 수 있다.

## 흔한 실수
- 32비트 코드를 `CS_MODE_64`로, 또는 그 반대로 열어서 완전히 다른(의미 없는) 명령어가 나오는 경우 — 항상 대상 바이너리의 실제 아키텍처를 먼저 확인한다.
- 파일 오프셋을 그대로 가상주소인 것처럼 `disasm()`의 `addr` 인자에 넘겨서, `call`/`jmp`/`lea` 같은 상대주소 기반 오퍼랜드가 실제와 다르게 출력되는 경우.
- 코드 영역과 데이터 영역(문자열, 점프 테이블, 정렬용 패딩)을 구분하지 않고 통째로 디스어셈블해서, 데이터를 코드로 잘못 해석한 결과가 뒤섞이는 경우 — 실제 함수 경계는 가급적 IDA/Ghidra 등에서 먼저 확인한 뒤 Capstone은 그 범위 내에서 스크립팅용으로 쓰는 것이 안전하다.
- `md.disasm()`이 반환하는 것이 제너레이터라는 걸 모르고 `list(md.disasm(...))`을 여러 번 호출하려다 두 번째부터 빈 결과를 얻는 경우 — 재사용하려면 먼저 리스트로 한 번 변환해서 저장해둬야 한다.
- 가변 길이 x86 명령어의 특성상, 디스어셈블 시작 위치를 한 바이트만 잘못 잡아도(오프바이원) 그 이후 모든 명령어가 완전히 다르게(하지만 문법적으로는 유효하게) 해석되는 "디스어셈블 어긋남" 현상을 못 알아채는 경우.

## 막혔을 때 다음 체크
- 결과가 이상하게 깨져 보인다면 → `CS_MODE_32`/`CS_MODE_64` 설정과 실제 바이너리 아키텍처가 일치하는지, 그리고 디스어셈블 시작 바이트 위치가 실제 명령어 경계와 일치하는지부터 다시 확인한다.
- 디스어셈블한 코드가 실제로 어떤 값을 계산하는지까지 알아야 한다면 → REV-0273 문서에서 Unicorn으로 같은 코드를 직접 실행시켜 레지스터/메모리 결과를 확인하는 방법을 참고한다.
- 함수 경계나 전체 제어 흐름 구조까지 자동으로 파악하고 싶다면 → REV-0271 문서의 `angr`가 내부적으로 Capstone과 비슷한 디스어셈블을 포함해 더 높은 수준의 분석(심볼릭 실행)을 제공한다는 점을 참고한다.
- 대량의 함수에 반복적으로 이런 스크립트를 적용하고 싶다면 → 먼저 IDA/Ghidra로 함수 경계를 뽑아낸 뒤(예: 함수 시작 주소와 크기 목록), 그 목록을 파이썬 스크립트에서 순회하며 각 함수 범위만 Capstone으로 디스어셈블하는 방식이 안전하고 빠르다.

## 미니 예제
셸코드처럼 파일 구조 없이 raw 바이트열만 있는 상황을 가정하고, 그 안의 모든 명령어를 사람이 읽을 수 있는 형태로 출력하는 완전한 스크립트다.

```python
from capstone import *

# xor eax, eax ; inc eax ; cmp eax, 1 ; je 0x1009 ; ret
shellcode = b'\x31\xc0\xff\xc0\x83\xf8\x01\x74\x02\xc3'

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

print(f'{"ADDR":<10}{"MNEMONIC":<10}OPERANDS')
for insn in md.disasm(shellcode, 0x1000):
    print(f'0x{insn.address:<8x}{insn.mnemonic:<10}{insn.op_str}')
```

출력 예시:

```text
ADDR      MNEMONIC  OPERANDS
0x1000    xor       eax, eax
0x1002    inc       eax
0x1004    cmp       eax, 1
0x1007    je        0x100b
0x1009    ret
```

이렇게 사람이 읽을 수 있는 형태로 뽑아낸 명령어 목록은, 다음 단계로 REV-0273의 Unicorn에 그대로 넣어 실제 실행 결과(레지스터 값 변화)를 확인하는 흐름으로 자연스럽게 이어진다.

## 실전 예시: 함수 하나를 통째로 분석해서 조건부 분기만 자동 수집하기
실전에서는 명령어 하나하나를 눈으로 읽는 대신, "이 함수 안에 조건부 분기(`jg`, `je`, `jne` 등)가 어디에 있고 각각 어디로 뛰는지"만 스크립트로 자동 뽑아내는 경우가 많다. 아래는 `if (x > 10) return 1; else return 0;`을 컴파일한 것과 동일한 구조를 가진(직접 x64 바이트로 구성하고 Capstone으로 재현 검증한) 함수를 분석하는 예시다.

```c
// 원본 C: int check(int x) { if (x > 10) return 1; else return 0; }
```

```python
from capstone import *

# check(int x) 함수에 해당하는 x64 기계어 바이트열 (System V 호출 규약: 첫 인자는 edi)
code = bytes([
    0x55,                          # push rbp
    0x48, 0x89, 0xe5,              # mov rbp, rsp
    0x89, 0x7d, 0xfc,              # mov [rbp-4], edi      ; x를 지역변수에 저장
    0x83, 0x7d, 0xfc, 0x0a,        # cmp dword [rbp-4], 0xa ; x와 10을 비교
    0x7f, 0x07,                    # jg L1                   ; x > 10 이면 L1로 분기
    0xb8, 0x00, 0x00, 0x00, 0x00,  # mov eax, 0               ; x <= 10 인 경우: 반환값 0
    0xeb, 0x05,                    # jmp L2
    0xb8, 0x01, 0x00, 0x00, 0x00,  # L1: mov eax, 1            ; x > 10 인 경우: 반환값 1
    0xc3                            # L2: ret
])

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

BASE = 0x401000
insns = list(md.disasm(code, BASE))

for insn in insns:
    print(f'0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}')

# 조건부 분기 명령어(mnemonic이 j로 시작하되 무조건 분기인 jmp는 제외)만 자동으로 골라낸다
print('\n--- 조건부 분기 목록 ---')
for insn in insns:
    if insn.mnemonic.startswith('j') and insn.mnemonic != 'jmp':
        print(f'0x{insn.address:x}: {insn.mnemonic} {insn.op_str}')
```

이 스크립트를 실행하면 다음과 같은 디스어셈블 결과가 정확히 출력된다(실제 Capstone 6.x로 재현 검증됨).

```text
0x401000:      push    rbp
0x401001:      mov     rbp, rsp
0x401004:      mov     dword ptr [rbp - 4], edi
0x401007:      cmp     dword ptr [rbp - 4], 0xa
0x40100b:      jg      0x401014
0x40100d:      mov     eax, 0
0x401012:      jmp     0x401019
0x401014:      mov     eax, 1
0x401019:      ret

--- 조건부 분기 목록 ---
0x40100b: jg 0x401014
```

`jg 0x401014`의 목표 주소 `0x401014`가 정확히 `mov eax, 1`(반환값 1을 만드는 블록)을 가리키고 있다는 것을 코드 한 줄로 확인할 수 있다. 함수가 수십~수백 바이트로 커지면 이런 조건부 분기 목록을 자동으로 뽑아내는 스크립트가, "이 함수의 성공 경로가 정확히 어디인지"를 사람이 명령어를 하나씩 눈으로 훑는 것보다 훨씬 빠르게 찾아준다 — 그리고 이렇게 찾은 주소(`0x401014`)는 REV-0271의 `simgr.explore(find=...)`에 그대로 넣을 수 있는 후보가 된다.

## 관련 글
- REV-0273 — Unicorn으로 작은 검증 함수 에뮬레이션
- REV-0271 — angr 심볼릭 실행 기초

## 출처/검증
- Capstone 공식 문서(capstone-engine.org) 및 공식 GitHub(capstone-engine/capstone)의 파이썬 바인딩 API(`Cs`, `disasm`, `CS_ARCH_X86`, `CS_MODE_64`)를 기준으로 정리했다(2026-09-08 검증).
- `capstone`은 서드파티 패키지이므로 `pip install capstone`이 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
- 코드 예제에 쓰인 x64 기계어 바이트열은 표준 x86-64 인코딩을 기준으로 직접 구성했으며, `pip install capstone` 환경의 표준 CPython 3에서 그대로 재현 가능하다.
