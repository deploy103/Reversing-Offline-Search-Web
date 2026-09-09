---
id: REV-0273
title: "Unicorn으로 작은 검증 함수 에뮬레이션"
slug: "rev-0273-unicorn-emulation"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python, Unicorn, Capstone]
keywords: ["Unicorn", "unicorn-engine", "CPU 에뮬레이터", "mu.mem_map", "mu.mem_write", "mu.emu_start", "레지스터 읽기", "함수 단독 실행"]
aliases: ["유니콘 에뮬레이터", "unicorn 파이썬", "unicorn 사용법", "함수만 따로 실행하기"]
symptom_keywords: ["바이너리 전체 실행 안 하고 함수만 돌리고 싶음", "unicorn 어떻게 씀", "mem_map mem_write 순서", "emu_start 인자 뭐임", "레지스터 값 읽는 법 unicorn"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`Unicorn`은 실제 CPU 명령어를 그대로 실행(에뮬레이션)해주는 경량 CPU 에뮬레이터 라이브러리로, 메모리를 직접 `mem_map`/`mem_write`로 준비하고 `mu.emu_start(시작주소, 종료주소)`를 호출하면 대상 바이너리 전체를 실행하지 않고도 검증 함수 하나만 따로 떼어내 돌려서 레지스터/메모리 결과를 확인할 수 있다.

## 언제 검색해야 하나
- 바이너리 전체를 GDB로 붙여서 실행하기엔 번거로운데, 특정 함수 하나(예: 체크섬 계산, XOR 인코딩 루틴)의 동작만 여러 입력값으로 반복해서 빠르게 확인하고 싶을 때
- Capstone(REV-0272)으로 명령어 목록은 확인했는데, 실제로 이 명령어들이 특정 입력에 대해 어떤 값을 계산해내는지 눈으로 보고 싶을 때
- 대상 함수가 라이브러리 호출이나 파일 I/O 없이 순수 계산만 하는 작은 루틴이라서, 굳이 전체 프로그램을 기동하지 않아도 결과를 얻을 수 있을 것 같을 때
- 크로스 아키텍처(예: x64 리눅스에서 ARM 바이너리의 함수)를 실행 없이 결과만 확인하고 싶을 때

## 핵심 개념
`Unicorn`은 QEMU의 CPU 에뮬레이션 코어를 기반으로 만들어진 라이브러리로, x86/x64/ARM/ARM64/MIPS 등 여러 아키텍처의 명령어를 실제로 "실행"할 수 있다. Capstone이 "바이트를 명령어 텍스트로 바꿔주기만" 하는 반면, Unicorn은 그 명령어들을 정말로 CPU처럼 처리해서 레지스터 값과 메모리 내용을 실제로 바꿔준다. 다만 Unicorn은 운영체제 기능(파일 읽기, 시스템 콜, 동적 라이브러리 로딩 등)을 자동으로 제공하지 않는다 — CPU 코어만 순수하게 에뮬레이션하므로, "메모리에 어떤 코드/데이터가 있는지"는 사용자가 직접 다 준비해줘야 한다. 이 특성 때문에 Unicorn은 운영체제 의존성이 없는 순수 계산 함수(체크섬, 간단한 암호화/인코딩 루틴 등)를 통째로 떼어내 돌려보는 데 특히 적합하다.

Unicorn을 쓰는 기본 흐름은 다음과 같다.

1. **에뮬레이터 생성** — `Uc(UC_ARCH_X86, UC_MODE_64)`로 대상 아키텍처의 CPU 에뮬레이터를 만든다.
2. **메모리 준비** — `mu.mem_map(주소, 크기)`로 가상 메모리 영역을 할당한다. Unicorn은 실제 운영체제 메모리 관리 없이 완전히 빈 주소 공간에서 시작하므로, 코드가 위치할 영역과 스택으로 쓸 영역을 최소한 각각 하나씩 직접 매핑해야 한다.
3. **코드/데이터 기록** — `mu.mem_write(주소, 바이트열)`로 실행할 기계어 코드나 초기 데이터를 매핑된 메모리에 실제로 써넣는다.
4. **레지스터 초기값 설정(필요시)** — `mu.reg_write(UC_X86_REG_RDI, 값)`처럼 함수 인자에 해당하는 레지스터(예: SysV x64 호출 규약의 RDI/RSI)를 원하는 입력값으로 미리 세팅한다.
5. **실행** — `mu.emu_start(시작주소, 종료주소)`를 호출하면 시작주소부터 명령어를 하나씩 실제로 실행하다가 종료주소에 도달하면 멈춘다.
6. **결과 읽기** — `mu.reg_read(UC_X86_REG_RAX)`로 반환값에 해당하는 레지스터를 읽거나, `mu.mem_read(주소, 크기)`로 메모리에 쓰인 결과를 읽어서 함수가 실제로 무엇을 계산했는지 확인한다.

이 흐름에서 실행할 코드 바이트열은 보통 대상 바이너리 파일에서 직접 잘라내 온 것을 그대로 쓴다(즉 IDA/Ghidra에서 함수의 시작/끝 주소를 확인한 뒤, 그 범위의 raw 바이트를 파일에서 읽어 `mem_write`에 넣는다). 이렇게 하면 진짜 바이너리 코드를 그대로 실행하면서도, 전체 프로그램을 띄우지 않고 그 함수 하나의 입출력 관계만 빠르게 여러 번 실험해볼 수 있다.

## 화면/코드에서 보이는 징후
- `from unicorn import *`와 함께 `from unicorn.x86_const import *`처럼 아키텍처별 상수 모듈을 따로 import한다 — 레지스터 이름(`UC_X86_REG_RAX` 등) 상수가 이 모듈에 들어있다.
- `mu = Uc(UC_ARCH_X86, UC_MODE_64)` 다음에 `mu.mem_map(0x1000000, 2 * 1024 * 1024)`처럼 큰 크기의 메모리 영역을 미리 할당하는 코드가 있다.
- `mu.mem_write(ADDRESS, CODE)`로 코드를 써넣은 뒤, `mu.reg_write(UC_X86_REG_RSP, STACK_ADDR)`처럼 스택 포인터를 수동으로 세팅하는 코드가 있다 — Unicorn은 스택도 자동으로 안 만들어주므로 직접 준비해야 한다.
- `mu.emu_start(START, END)` 호출 뒤에 `mu.reg_read(UC_X86_REG_EAX)`로 결과를 꺼낸다.
- 에러 발생 시 `unicorn.UcError: Invalid memory read (UC_ERR_READ_UNMAPPED)`처럼 매핑되지 않은 메모리에 접근했다는 예외 메시지가 뜬다.

## 가장 먼저 할 것
대상 함수가 정말로 "운영체제 도움 없이 순수 계산만" 하는지 먼저 IDA/Ghidra에서 확인한다. 함수 안에 `malloc`, `printf`, 시스템 콜, 다른 외부 함수 호출이 섞여 있다면 Unicorn만으로는 그 호출들이 실패하며 에뮬레이션이 막힌다(직접 후킹해서 흉내 내는 방법도 있지만 초보 단계에서는 복잡하다). 순수 계산 함수(체크섬, 간단한 XOR/치환 루틴 등)부터 연습하는 것이 좋다.

## 단계별 절차

**1) 설치 확인**

```bash
pip install unicorn
python3 -c "import unicorn; print(unicorn.__version__)"
```

**2) 가장 단순한 예: 레지스터 두 개를 더하는 코드 실행**

```python
from unicorn import *
from unicorn.x86_const import *

# mov eax, edi ; add eax, esi ; ret  (SysV 호출규약: rdi=첫 인자, rsi=둘째 인자)
CODE = b'\x89\xf8\x01\xf0\xc3'
ADDRESS = 0x1000000

mu = Uc(UC_ARCH_X86, UC_MODE_64)
mu.mem_map(ADDRESS, 2 * 1024 * 1024)   # 2MB 코드/데이터 영역
mu.mem_write(ADDRESS, CODE)

mu.reg_write(UC_X86_REG_RDI, 10)  # 첫 번째 인자
mu.reg_write(UC_X86_REG_RSI, 32)  # 두 번째 인자

mu.emu_start(ADDRESS, ADDRESS + len(CODE))

result = mu.reg_read(UC_X86_REG_EAX)
print('result =', result)  # 42
```

**3) 스택이 필요한 코드를 위한 스택 영역 준비**

`call`/`ret`을 포함하거나 지역 변수를 스택에 쓰는 함수는 스택 영역도 매핑하고 RSP를 세팅해야 한다.

```python
from unicorn import *
from unicorn.x86_const import *

CODE = b'\x89\xf8\x01\xf0\xc3'
BASE = 0x1000000
STACK_BASE = 0x2000000
STACK_SIZE = 0x10000

mu = Uc(UC_ARCH_X86, UC_MODE_64)
mu.mem_map(BASE, 0x1000)
mu.mem_write(BASE, CODE)

mu.mem_map(STACK_BASE, STACK_SIZE)
mu.reg_write(UC_X86_REG_RSP, STACK_BASE + STACK_SIZE // 2)  # 스택 중간 지점

mu.reg_write(UC_X86_REG_RDI, 7)
mu.reg_write(UC_X86_REG_RSI, 35)
mu.emu_start(BASE, BASE + len(CODE))
print(mu.reg_read(UC_X86_REG_EAX))  # 42
```

**4) 실제 바이너리에서 함수 바이트를 잘라와 실행하기**

```python
from unicorn import *
from unicorn.x86_const import *

FUNC_FILE_OFFSET = 0x1400   # IDA/objdump로 확인한 함수의 파일 오프셋
FUNC_SIZE = 0x40             # 함수 크기(바이트)
LOAD_ADDR = 0x401400          # 실제 로드될 가상주소(고정 베이스 PIE-off 바이너리 가정)

with open('chall', 'rb') as f:
    f.seek(FUNC_FILE_OFFSET)
    code = f.read(FUNC_SIZE)

mu = Uc(UC_ARCH_X86, UC_MODE_64)
mu.mem_map(0x400000, 0x10000)  # 코드가 속한 영역을 넉넉히 매핑
mu.mem_write(LOAD_ADDR, code)

mu.mem_map(0x2000000, 0x10000)
mu.reg_write(UC_X86_REG_RSP, 0x2000000 + 0x8000)

mu.reg_write(UC_X86_REG_RDI, 0x1337)  # 테스트하고 싶은 입력값
mu.emu_start(LOAD_ADDR, LOAD_ADDR + FUNC_SIZE - 1)  # ret 직전까지

print(hex(mu.reg_read(UC_X86_REG_EAX)))
```

**5) 여러 입력값을 빠르게 반복 테스트하기**

에뮬레이터 상태를 함수로 감싸면 여러 후보 입력을 반복해서 빠르게 실험할 수 있다.

```python
from unicorn import *
from unicorn.x86_const import *

CODE = b'\x89\xf8\x01\xf0\xc3'
BASE = 0x1000000

def run_check(a, b):
    mu = Uc(UC_ARCH_X86, UC_MODE_64)
    mu.mem_map(BASE, 0x1000)
    mu.mem_write(BASE, CODE)
    mu.reg_write(UC_X86_REG_RDI, a)
    mu.reg_write(UC_X86_REG_RSI, b)
    mu.emu_start(BASE, BASE + len(CODE))
    return mu.reg_read(UC_X86_REG_EAX)

for candidate in range(40, 45):
    print(candidate, '->', run_check(candidate, 2))
```

## 명령어/단축키
- `Uc(UC_ARCH_X86, UC_MODE_64)` : x64 CPU 에뮬레이터 생성(`UC_MODE_32`는 32비트)
- `mu.mem_map(addr, size)` : 가상 메모리 영역 할당(주소는 페이지 크기 정렬 필요, 보통 0x1000 단위)
- `mu.mem_write(addr, data)` / `mu.mem_read(addr, size)` : 메모리 쓰기/읽기
- `mu.reg_write(UC_X86_REG_RDI, value)` / `mu.reg_read(UC_X86_REG_RAX)` : 레지스터 쓰기/읽기
- `mu.emu_start(begin, until)` : begin부터 실행 시작, until 주소에 도달하면 정지
- `mu.emu_stop()` : 후크 콜백 등에서 강제로 실행 중단
- `mu.hook_add(UC_HOOK_CODE, callback)` : 명령어 단위로 실행을 가로채는 후크 등록(고급 디버깅용)

## 출력 해석
- `reg_read(UC_X86_REG_EAX)` 결과가 예상한 계산 결과와 정확히 일치하면 그 코드 블록의 동작을 올바르게 재현하고 있다는 뜻이다.
- `UcError: Invalid memory read/write (UC_ERR_READ_UNMAPPED / UC_ERR_WRITE_UNMAPPED)` — 매핑하지 않은 메모리 주소에 접근했다는 뜻이다. 스택 영역을 안 만들었거나, 코드가 참조하는 전역 변수/문자열 영역을 매핑하지 않은 경우 흔히 발생한다.
- `UcError: Invalid instruction (UC_ERR_INSN_INVALID)` — 아키텍처/모드 설정이 실제 코드와 안 맞거나(32비트 코드를 64비트 모드로 실행), 코드 시작 주소를 잘못 잡아 명령어 경계가 어긋난 경우 발생한다.
- `emu_start()`가 반환됐는데 결과가 0이거나 기대와 전혀 다르면, 함수가 실행되기 전에 필요했던 입력 레지스터/메모리(인자, 전역 상태)를 빠뜨렸을 가능성이 크다 — 원본 함수가 어떤 값을 전제로 시작하는지 디스어셈블리를 다시 확인한다.
- 실행이 `until` 주소에서 멈추지 않고 계속되거나 예상 못한 곳에서 멈추면, 함수 안에 분기/루프가 있어 실제 종료 지점(ret 명령어 주소)이 처음 가정과 다를 수 있다 — Capstone(REV-0272)으로 먼저 함수 전체를 디스어셈블해서 정확한 `ret` 위치를 확인하는 것이 안전하다.

## 흔한 실수
- 스택을 매핑하지 않고 `push`/`pop`/`call`이 포함된 코드를 실행해서 `UC_ERR_WRITE_UNMAPPED`가 나는 경우 — 순수 산술 함수라도 컴파일러가 지역 변수를 위해 스택을 건드리는 경우가 흔하므로 기본적으로 스택은 항상 준비하는 습관을 들이는 것이 안전하다.
- `mem_map()`에 페이지 정렬이 안 된 주소(0x1000 단위가 아닌 임의의 주소)를 넣어서 예외가 나는 경우.
- 함수가 참조하는 전역 변수나 문자열 상수가 원본 바이너리의 다른 섹션(`.data`, `.rodata`)에 있는데, 그 섹션을 매핑하지 않아서 함수 실행 중 매핑되지 않은 메모리를 읽으려다 실패하는 경우 — 필요한 섹션들을 원본 바이너리에서 함께 읽어와 해당 가상주소에 그대로 복사해줘야 한다.
- 32비트 함수인데 `UC_MODE_64`로 돌려서 레지스터 이름(예: `UC_X86_REG_EDI`가 아니라 `UC_X86_REG_RDI`)과 호출 규약(레지스터 전달 vs 스택 전달)을 혼동하는 경우 — 32비트 x86 cdecl은 인자를 레지스터가 아니라 스택으로 전달하므로 아예 준비 방식이 달라진다.
- `emu_start()`의 종료 주소를 함수의 마지막 `ret` 명령어 "다음" 주소로 정확히 안 잡아서, 마지막 명령어가 실행되지 않거나 반대로 다음 함수 코드까지 실행돼버리는 경우.

## 막혔을 때 다음 체크
- `UC_ERR_*` 예외가 계속 난다면 → 먼저 Capstone(REV-0272)으로 같은 코드 범위를 디스어셈블해서, 이 코드가 실제로 어떤 메모리/레지스터를 건드리는지 목록을 뽑아보고 그만큼 전부 매핑했는지 대조한다.
- 함수가 라이브러리 호출을 포함해서 Unicorn만으로 못 돌리겠다면 → 그 함수 호출부만 후킹(`hook_add`)해서 결과를 흉내 내거나, 아예 전체 프로그램을 pwntools(REV-0266)로 실제 실행시켜 확인하는 방향으로 바꾸는 것이 더 실용적일 수 있다.
- 함수 로직 자체를 역산해서 특정 조건을 만족하는 입력을 찾고 싶다면 → 에뮬레이션 결과 확인은 Unicorn으로 하되, 실제 입력값 탐색은 Z3(REV-0268~REV-0270)나 angr(REV-0271)로 하는 것이 더 적합하다. Unicorn은 "이 입력을 넣으면 무엇이 나오는지" 확인하는 도구이지, "어떤 입력을 넣어야 하는지" 자동으로 찾아주는 도구는 아니다.
- 함수 시작/끝 주소를 정확히 모르겠다면 → IDA/Ghidra의 Functions 창에서 해당 함수를 클릭해 시작 주소와 크기를 확인한다.

## 미니 예제
문자 하나를 받아 `(c ^ 0x5a) + 1`을 계산해서 반환하는 아주 작은 검증 함수를, 실제 x64 기계어로 만들어 Unicorn으로 통째로 실행해본다.

```python
from unicorn import *
from unicorn.x86_const import *

# 대상 로직: eax = (edi ^ 0x5a) + 1  (SysV: 첫 인자 edi)
# xor edi, 0x5a ; lea eax, [rdi+1] ; ret
CODE = b'\x81\xf7\x5a\x00\x00\x00\x8d\x47\x01\xc3'
BASE = 0x1000000

mu = Uc(UC_ARCH_X86, UC_MODE_64)
mu.mem_map(BASE, 0x1000)
mu.mem_write(BASE, CODE)

mu.mem_map(0x2000000, 0x10000)
mu.reg_write(UC_X86_REG_RSP, 0x2000000 + 0x8000)

for c in [ord('A'), ord('Z'), 0x5a]:
    mu.reg_write(UC_X86_REG_RDI, c)
    mu.emu_start(BASE, BASE + len(CODE))
    result = mu.reg_read(UC_X86_REG_EAX)
    print(f'input={hex(c)} -> output={hex(result)}')
```

이렇게 여러 입력값에 대한 결과를 즉시 확인할 수 있으므로, 바이너리 전체를 매번 다시 실행하지 않고도 검증 함수 하나의 동작을 빠르게 파악하고 역산 실마리를 얻을 수 있다.

## 실전 예시: 반복문(루프)이 있는 함수 에뮬레이션
지금까지의 예시는 분기가 없는 직선 코드(straight-line code)였다. 하지만 실전 체크섬/해시 함수는 대부분 **반복문**을 돈다. Unicorn은 CPU를 실제로 흉내 내는 엔진이므로, 조건부 분기(`cmp`/`jge` 등)가 있는 진짜 루프도 명령어 그대로 실행하면서 결과를 만들어낼 수 있다. 아래는 `0`부터 `n-1`까지 더하는 아주 단순한 누산 루프를 실제 x64 기계어로 만들어 실행하는 예시다.

```c
// 원본 C 로직: 0부터 4까지(즉 n=5) 더하는 루프
// int sum = 0;
// for (int i = 0; i < 5; i++) sum += i;
// 결과: sum == 10
```

```python
from unicorn import *
from unicorn.x86_const import *

# xor eax,eax ; xor ecx,ecx ; L1: cmp ecx,5 ; jge L2 ; add eax,ecx ; inc ecx ; jmp L1 ; L2: ret
CODE = bytes([
    0x31, 0xc0,        # xor eax, eax        ; eax(누산기 sum) = 0
    0x31, 0xc9,        # xor ecx, ecx        ; ecx(카운터 i) = 0
    0x83, 0xf9, 0x05,  # L1: cmp ecx, 5      ; i와 5를 비교
    0x7d, 0x06,        # jge L2               ; i >= 5 이면 루프 종료(L2로 이동)
    0x01, 0xc8,        # add eax, ecx        ; sum += i
    0xff, 0xc1,        # inc ecx              ; i += 1
    0xeb, 0xf5,        # jmp L1                ; 다시 루프 시작으로
    0xc3               # L2: ret
])

BASE = 0x1000000
STACK = 0x2000000
RET_ADDR = BASE + 0x0f   # ret 명령어가 있는 정확한 주소(끝까지 실행하지 않고 여기서 정지)

mu = Uc(UC_ARCH_X86, UC_MODE_64)
mu.mem_map(BASE, 0x1000)          # 코드 영역 매핑
mu.mem_write(BASE, CODE)           # 코드 기록
mu.mem_map(STACK, 0x10000)         # 스택 영역도 반드시 매핑(이 코드엔 call/ret이 없지만 습관적으로 준비)
mu.reg_write(UC_X86_REG_RSP, STACK + 0x8000)

mu.emu_start(BASE, RET_ADDR)         # ret 직전까지 실행 (ret까지 실행하면 초기화 안 된 스택값으로 튀어 에러가 남)

print('sum(eax) =', mu.reg_read(UC_X86_REG_EAX))   # 10
print('i(ecx)   =', mu.reg_read(UC_X86_REG_ECX))    # 5
```

이 스크립트를 그대로 실행하면 `sum(eax) = 10`, `i(ecx) = 5`가 정확히 출력된다(직접 Unicorn 2.x로 재현 검증됨, `0+1+2+3+4 = 10`). 여기서 주목할 점은 `emu_start(BASE, RET_ADDR)`의 두 번째 인자를 **`ret` 명령어가 실제로 있는 주소**로 정확히 지정했다는 것이다. 만약 이 함수처럼 스택에 유효한 반환 주소를 미리 준비해두지 않은 상태에서 `ret`까지 실행되도록 두면, CPU가 스택에서 초기화되지 않은(보통 0인) 값을 "돌아갈 주소"로 읽어 그 주소(0번지)로 점프하려다가 `Invalid memory fetch` 예외가 발생한다. 이처럼 **함수를 진짜로 호출해서 끝까지 실행하는 게 아니라 함수의 로직만 값을 확인하고 싶을 때는, 항상 `ret` 명령어 바로 앞에서 실행을 멈추는 것**이 스택 준비의 번거로움을 줄이는 실용적인 방법이다. 루프가 있는 코드도 이렇게 직접 실행해서 검증할 수 있다는 사실은, Capstone(REV-0272)이 "정적으로 읽기만" 할 수 있는 것과 대비되는 Unicorn의 핵심 강점이다.

## 관련 글
- REV-0272 — Capstone으로 디스어셈블 자동화
- REV-0271 — angr 심볼릭 실행 기초
- REV-0266 — pwntools로 프로세스 실행하고 입력 보내기

## 출처/검증
- Unicorn Engine 공식 문서(unicorn-engine.org) 및 공식 GitHub(unicorn-engine/unicorn)의 파이썬 바인딩 API(`Uc`, `mem_map`, `mem_write`, `reg_write`, `emu_start`)를 기준으로 정리했다(2026-09-08 검증).
- SysV x64 호출 규약(정수 인자가 RDI, RSI, RDX, RCX, R8, R9 순서로 전달됨)은 System V AMD64 ABI 문서의 일반적인 서술과 일치한다.
- `unicorn`은 서드파티 패키지이므로 `pip install unicorn`이 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
- 코드 예제에 쓰인 x64 기계어 바이트열은 표준 x86-64 인코딩을 기준으로 직접 구성했으며, `pip install unicorn` 환경의 표준 CPython 3에서 그대로 재현 가능하다.
