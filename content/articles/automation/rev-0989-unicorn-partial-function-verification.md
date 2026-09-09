---
id: REV-0989
title: "Unicorn 에뮬레이션으로 부분 함수만 실행해서 검증하기 심화"
slug: "rev-0989-unicorn-partial-function-verification"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Unicorn, Python]
keywords: ["unicorn hook_add", "UC_HOOK_CODE", "UC_HOOK_MEM_UNMAPPED", "unicorn 라이브러리 호출 후킹", "unicorn 자동 검증 프레임워크"]
aliases: ["unicorn 심화 사용법", "unicorn 후킹", "unicorn 함수 호출 흉내내기", "unicorn 자동 테스트"]
symptom_keywords: ["함수 안에서 라이브러리 호출이 있어서 에뮬레이션이 막힘", "unmapped memory 에러가 계속 남", "매 명령어마다 추적하고 싶음", "여러 테스트케이스를 자동으로 돌리고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
REV-0273에서 다룬 기본 Unicorn 사용법(코드/스택 매핑, `emu_start`, 결과 읽기)에서 한 단계 더 나아가, `hook_add`로 매핑되지 않은 메모리 접근이나 라이브러리 함수 호출 지점을 가로채 흉내 내면 대상 함수가 `malloc`/`memcpy`/전역 테이블 참조를 포함하고 있어도 전체 프로그램을 띄우지 않고 그 함수 하나만 안정적으로 반복 검증할 수 있다.

## 언제 검색해야 하나
- 대상 함수 안에 `strlen`, `memcpy` 같은 라이브러리 호출이나 전역 변수 접근이 있어서 REV-0273의 기본 방식만으로는 `UC_ERR_*` 예외가 계속 날 때
- 같은 함수에 대해 수백~수천 개의 입력 후보를 자동으로 빠르게 반복 검증하는 테스트 하네스를 만들고 싶을 때
- 명령어 하나하나가 실제로 어떤 값을 만들어내는지 실행 도중 실시간으로 추적(trace)하고 싶을 때
- 함수가 매핑 안 된 메모리를 건드릴 때 그냥 실패시키지 않고, 그 순간에 필요한 메모리를 즉석에서 채워 넣고 계속 진행시키고 싶을 때

## 핵심 개념
Unicorn은 순수 CPU 에뮬레이션 엔진이라 운영체제 기능, 라이브러리 함수, 동적 링킹을 전혀 대신해주지 않는다는 것은 REV-0273에서 다룬 그대로다. 여기서 한 단계 나아가려면 Unicorn의 **후크(hook)** 메커니즘을 적극적으로 활용해야 한다.

### hook_add의 세 가지 핵심 훅 타입
- **`UC_HOOK_CODE`** — 지정한 범위의 명령어가 실행되기 직전마다 콜백이 호출된다. 매 명령어 단위 추적(트레이스)에 쓴다.
- **`UC_HOOK_MEM_UNMAPPED`** — 매핑되지 않은 메모리에 접근이 발생하면 콜백이 호출된다. 콜백 안에서 즉석으로 `mu.mem_map()`을 호출해 그 영역을 채워주고 `True`를 반환하면, 에뮬레이션이 예외 없이 계속 진행된다. 이는 "필요한 순간에만 메모리를 준비하는" 지연 매핑(lazy mapping) 패턴이다.
- **`UC_HOOK_CODE`(특정 주소 하나만 지정)** — 라이브러리 함수의 시작 주소에 훅을 걸어, 그 함수의 실제 코드를 실행하는 대신 콜백 안에서 원하는 반환값을 레지스터에 직접 써넣고 `PC`(RIP/EIP)를 그 함수의 반환 주소로 강제 이동시키는 방식으로 "함수 호출을 흉내(스텁, stub)"낼 수 있다.

### 반복 검증 하네스 만들기
CTF에서 이 기법이 특히 유용한 상황은 "이 검증 함수에 어떤 입력을 넣어야 특정 결과가 나오는가"를 브루트포스나 순차 탐색으로 알아내야 할 때다. 매번 새 프로세스를 fork/exec 하는 pwntools 방식(REV-0266)보다, 이미 매핑된 Unicorn 인스턴스의 레지스터/일부 메모리만 초기화하고 재실행하는 방식이 훨씬 빠르다. 다만 매번 완전히 새 `Uc` 객체를 만드는 편이 상태 오염을 피하기에 더 안전하며, 성능이 정말 중요할 때만 상태 재사용 최적화를 고려한다.

## 화면/코드에서 보이는 징후
- `mu.hook_add(UC_HOOK_CODE, trace_callback, begin=START, end=END)`처럼 특정 주소 범위에 코드 훅을 등록하는 코드가 있다.
- `mu.hook_add(UC_HOOK_MEM_UNMAPPED, on_unmapped)`가 등록되어 있고, 콜백 안에서 `mu.mem_map(align_addr, size)`를 호출한 뒤 `return True`로 끝난다.
- 특정 함수 주소에 코드 훅을 걸고, 콜백 안에서 `mu.reg_write(UC_X86_REG_RIP, return_addr)`처럼 강제로 실행 위치를 옮기는 코드가 있다 — 함수 호출을 스텁으로 대체하는 패턴이다.
- 여러 입력값에 대해 `Uc(...)`를 매번 새로 생성하는 반복문 안에 매핑/후킹 설정 코드가 함수로 묶여 있다.

## 가장 먼저 할 것
대상 함수를 REV-0273의 기본 방식으로 먼저 한 번 실행해보고, 정확히 어떤 `UC_ERR_*` 예외가 어느 주소에서 나는지 확인한다. 그 주소가 매핑 안 된 데이터 영역 참조인지, 아니면 실제 라이브러리 함수 호출(`call`)인지에 따라 대응 방법(지연 매핑 vs 함수 스텁)이 달라진다.

## 단계별 절차

**1) 명령어 단위 추적으로 실행 흐름 확인**

```python
from unicorn import *
from unicorn.x86_const import *
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

md = Cs(CS_ARCH_X86, CS_MODE_64)

def trace_callback(mu, address, size, user_data):
    code = mu.mem_read(address, size)
    for insn in md.disasm(code, address):
        print(f'0x{insn.address:x}: {insn.mnemonic} {insn.op_str}')

BASE = 0x400000
mu = Uc(UC_ARCH_X86, UC_MODE_64)
mu.mem_map(BASE, 0x10000)
mu.mem_write(BASE, b'\x89\xf8\x01\xf0\xc3')  # mov eax,edi; add eax,esi; ret

mu.hook_add(UC_HOOK_CODE, trace_callback, begin=BASE, end=BASE + 0x10000)
mu.reg_write(UC_X86_REG_RDI, 10)
mu.reg_write(UC_X86_REG_RSI, 5)
mu.emu_start(BASE, BASE + 5)
print('eax =', mu.reg_read(UC_X86_REG_EAX))
```

**2) 매핑되지 않은 메모리를 즉석에서 채워 넣기(지연 매핑)**

```python
from unicorn import *
from unicorn.x86_const import *

PAGE = 0x1000

def align_down(addr):
    return addr & ~(PAGE - 1)

def on_unmapped(mu, access, address, size, value, user_data):
    aligned = align_down(address)
    try:
        mu.mem_map(aligned, PAGE)
        print(f'[lazy-map] mapped page at 0x{aligned:x} for access at 0x{address:x}')
        return True  # True를 반환하면 에뮬레이션이 예외 없이 계속 진행됨
    except UcError:
        return False

mu = Uc(UC_ARCH_X86, UC_MODE_64)
mu.hook_add(UC_HOOK_MEM_UNMAPPED, on_unmapped)

CODE_BASE = 0x400000
mu.mem_map(CODE_BASE, PAGE)
# 매핑 안 된 0x500000 주소를 읽는 코드: mov eax, [0x500000] 형태(개념 예시, 실제 바이트는 대상에 맞게 준비)
```

**3) 라이브러리 함수 호출을 스텁으로 대체하기**

대상 함수가 내부에서 `strlen(char *s)`을 호출한다고 가정한다. `strlen`의 실제 구현을 실행하는 대신, 호출 지점에서 결과만 흉내 낸다.

```python
from unicorn import *
from unicorn.x86_const import *

STRLEN_ADDR = 0x401500  # PLT/실제 함수 시작 주소(대상에 맞게 확인)

def strlen_stub(mu, address, size, user_data):
    # SysV: 첫 인자는 rdi(문자열 포인터)
    ptr = mu.reg_read(UC_X86_REG_RDI)
    data = b''
    # 널 종료 문자를 만날 때까지 한 바이트씩 읽어 길이 계산(실제 strlen 흉내)
    length = 0
    while True:
        b = mu.mem_read(ptr + length, 1)
        if b == b'\x00':
            break
        length += 1
        if length > 4096:  # 안전장치
            break
    mu.reg_write(UC_X86_REG_RAX, length)

    # 반환 주소는 호출 시 스택 최상단에 push되어 있음
    ret_addr = int.from_bytes(mu.mem_read(mu.reg_read(UC_X86_REG_RSP), 8), 'little')
    mu.reg_write(UC_X86_REG_RSP, mu.reg_read(UC_X86_REG_RSP) + 8)  # call이 push한 return addr pop
    mu.reg_write(UC_X86_REG_RIP, ret_addr)

mu = Uc(UC_ARCH_X86, UC_MODE_64)
# ... 코드/스택 매핑 생략 ...
mu.hook_add(UC_HOOK_CODE, strlen_stub, begin=STRLEN_ADDR, end=STRLEN_ADDR + 1)
```

**4) 여러 입력값을 자동으로 반복 검증하는 하네스**

```python
from unicorn import *
from unicorn.x86_const import *

def make_emulator(code, base=0x400000, stack_base=0x500000, stack_size=0x10000):
    mu = Uc(UC_ARCH_X86, UC_MODE_64)
    mu.mem_map(base, 0x1000)
    mu.mem_write(base, code)
    mu.mem_map(stack_base, stack_size)
    mu.reg_write(UC_X86_REG_RSP, stack_base + stack_size // 2)
    return mu

def run_check(code, base, input_val):
    mu = make_emulator(code, base)
    mu.reg_write(UC_X86_REG_RDI, input_val)
    mu.emu_start(base, base + len(code))
    return mu.reg_read(UC_X86_REG_EAX)

CODE = b'\x81\xf7\x5a\x00\x00\x00\x8d\x47\x01\xc3'  # xor edi,0x5a; lea eax,[rdi+1]; ret
BASE = 0x400000

target = 0x2f
for candidate in range(0, 256):
    if run_check(CODE, BASE, candidate) == target:
        print('found candidate:', hex(candidate))
        break
```

매번 `Uc()`를 새로 생성해서 이전 실행의 상태(레지스터, 메모리 잔여 값)가 다음 테스트에 영향을 주지 않도록 격리하는 것이 핵심이다.

## 명령어/단축키
- `mu.hook_add(UC_HOOK_CODE, cb, begin=, end=)` : 명령어 단위 추적/개입
- `mu.hook_add(UC_HOOK_MEM_UNMAPPED, cb)` : 매핑되지 않은 메모리 접근 가로채기(지연 매핑)
- `mu.hook_add(UC_HOOK_MEM_WRITE, cb)` / `UC_HOOK_MEM_READ` : 특정 메모리 접근 감시
- 콜백에서 `return True` : `UC_HOOK_MEM_UNMAPPED`에서 예외를 무시하고 계속 진행
- `mu.reg_write(UC_X86_REG_RIP, addr)` : 강제로 실행 위치 이동(함수 스텁 구현의 핵심)
- `mu.mem_read(addr, size)` / `mu.mem_write(addr, data)` : 훅 콜백 안에서도 동일하게 사용 가능

## 출력 해석
- `UC_HOOK_CODE` 트레이스 로그가 예상한 명령어 순서와 다르게 나온다면, 코드 시작 주소나 함수 경계를 잘못 잘라온 것일 수 있다.
- 지연 매핑 콜백이 반복적으로 여러 페이지를 매핑하고 있다면, 함수가 예상보다 넓은 메모리 영역(전역 배열, 큰 버퍼)에 접근하고 있다는 뜻이며, 처음부터 그 영역을 통째로 매핑해두는 편이 더 깔끔할 수 있다.
- 스텁으로 대체한 라이브러리 함수 이후 실행이 엉뚱한 곳으로 튀면, 반환 주소 계산(스택에서 pop하는 로직)이나 호출 규약(인자 레지스터 순서)을 잘못 흉내 낸 것일 가능성이 크다.

## 흔한 실수
- `UC_HOOK_MEM_UNMAPPED` 콜백에서 `mem_map` 호출 시 페이지 정렬을 하지 않아(`align_down` 누락) 또 다른 예외가 나는 것.
- 함수 스텁 구현 시 `call` 명령어가 스택에 push한 반환 주소를 pop하지 않고 그냥 `RIP`만 옮겨서, 이후 스택이 한 칸씩 밀려 이어지는 로직이 전부 깨지는 것.
- 여러 테스트 케이스에서 `Uc` 인스턴스를 재사용하면서 이전 테스트의 메모리 값이 남아있는 것을 모르고 결과를 오판하는 것 — 테스트마다 새 인스턴스를 만드는 것이 안전하다.
- 트레이스 훅을 코드 전체 범위에 걸어두고 대량 반복 테스트를 돌려서 속도가 극단적으로 느려지는 것 — 트레이스는 디버깅 단계에서만 켜고, 실제 대량 반복 검증 시에는 꺼야 한다.

## 막혔을 때 다음 체크
- Unicorn의 기본 개념(mem_map/mem_write/emu_start)이 아직 익숙하지 않다면 → REV-0273 Unicorn으로 작은 검증 함수 에뮬레이션
- 실행 전에 코드 구조를 먼저 사람이 읽을 수 있는 형태로 확인하고 싶다면 → REV-0272 Capstone으로 디스어셈블 자동화
- 패치용 코드 바이트를 자동으로 생성해서 이 에뮬레이션에 넣고 싶다면 → REV-0990 Capstone+Keystone으로 패치 코드 자동 생성하기
- 에뮬레이션 결과 확인이 아니라 "어떤 입력이 필요한지" 자체를 자동으로 찾고 싶다면 → REV-0271 angr 심볼릭 실행 기초(Unicorn은 결과 확인용, angr/Z3는 입력 탐색용)

## 미니 예제
전역 룩업 테이블을 참조하는 간단한 변환 함수를 매핑 없이 실행하려다 실패하는 상황을 지연 매핑으로 해결하는 전체 흐름이다.

```python
from unicorn import *
from unicorn.x86_const import *

# 개념: eax = table[edi]  (rdi는 인덱스, 0x500000에 테이블이 있다고 가정)
# mov eax, [0x500000 + rdi*4] ; ret  (실제 바이트는 예시로 단순화됨)
CODE = b'\x8b\x04\xbd\x00\x00\x50\x00\xc3'
BASE = 0x400000

def on_unmapped(mu, access, address, size, value, user_data):
    aligned = address & ~0xfff
    mu.mem_map(aligned, 0x1000)
    # 테이블 영역이면 알려진 값으로 채워줌
    if aligned == 0x500000:
        table = bytes([i * 2 for i in range(256)])
        mu.mem_write(0x500000, table)
    return True

mu = Uc(UC_ARCH_X86, UC_MODE_64)
mu.mem_map(BASE, 0x1000)
mu.mem_write(BASE, CODE)
mu.hook_add(UC_HOOK_MEM_UNMAPPED, on_unmapped)

mu.reg_write(UC_X86_REG_RDI, 5)
mu.emu_start(BASE, BASE + len(CODE))
print('result =', mu.reg_read(UC_X86_REG_EAX))  # table[5] = 10
```

이 패턴은 함수가 참조하는 모든 전역 데이터를 사전에 일일이 찾아 매핑해두지 않고도, 실행 도중 필요한 순간에만 값을 채워 넣어 검증을 완성할 수 있게 해준다.

## 관련 글
- REV-0273 — Unicorn으로 작은 검증 함수 에뮬레이션
- REV-0272 — Capstone으로 디스어셈블 자동화
- REV-0990 — Capstone+Keystone으로 패치 코드 자동 생성하기
- REV-0271 — angr 심볼릭 실행 기초

## 출처/검증
- Unicorn Engine의 후크 API(`hook_add`, `UC_HOOK_CODE`, `UC_HOOK_MEM_UNMAPPED`)와 콜백에서 `True` 반환 시 예외를 무시하고 진행하는 동작은 Unicorn 공식 문서(unicorn-engine.org) 및 공식 GitHub(unicorn-engine/unicorn) 샘플 코드를 기준으로 정리했다(2026-09-09 검증).
- SysV x64 호출 규약(인자 레지스터, 스택을 통한 반환주소 전달)은 System V AMD64 ABI 문서 기준.
- 코드 예제에 쓰인 기계어 바이트열은 개념 설명을 위해 단순화한 것이며, 실제 대상 바이너리의 바이트와 다를 수 있으므로 재현 시 실제 값으로 교체해야 한다.
