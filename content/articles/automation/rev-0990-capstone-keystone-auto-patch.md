---
id: REV-0990
title: "Capstone+Keystone으로 패치 코드 자동 생성하기"
slug: "rev-0990-capstone-keystone-auto-patch"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Capstone, Keystone, Python]
keywords: ["Keystone 어셈블러", "Ks(KS_ARCH_X86, KS_MODE_64)", "ks.asm", "바이너리 패치 자동화", "NOP 패딩", "jmp 리다이렉트 패치"]
aliases: ["keystone 사용법", "keystone 파이썬", "capstone keystone 조합", "자동 패치 스크립트"]
symptom_keywords: ["패치할 명령어를 기계어로 어떻게 바꿈", "패치 코드가 원본보다 길어서 안 들어감", "jmp로 다른 곳에 패치 붙이는 법", "keystone ks.asm 사용법"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Capstone(REV-0272)이 "바이트 → 명령어 텍스트"를 담당하는 디스어셈블러라면, `Keystone`은 그 반대인 "어셈블리 텍스트 → 바이트"를 담당하는 어셈블러로, 두 도구를 조합하면 원본 코드를 읽고(Capstone) → 원하는 로직으로 명령어를 바꾼 뒤(사람이 직접 작성) → 새 기계어 바이트로 조립해서(Keystone) 바이너리 파일에 자동으로 되써 넣는 패치 파이프라인 전체를 스크립트 하나로 완성할 수 있다.

## 언제 검색해야 하나
- IDA/Ghidra의 GUI 패치 기능 없이, 파이썬 스크립트만으로 여러 바이너리에 같은 패치를 일괄 적용하고 싶을 때
- 검증 로직의 조건 분기(`je`/`jne` 등)를 반대로 뒤집거나 `nop`으로 무력화하는 패치를 자동화하고 싶을 때
- 패치할 새 코드가 원래 명령어보다 바이트 수가 길어서 원래 자리에 안 들어갈 때 어떻게 처리해야 할지 모를 때
- 어셈블리 텍스트를 손으로 기계어 바이트로 변환하는 게 번거로워서 자동화하고 싶을 때

## 핵심 개념
`Keystone`은 Capstone과 같은 제작진이 만든 다중 아키텍처 어셈블러 라이브러리로, 사용법이 Capstone과 대칭적이다.

```python
from keystone import *
ks = Ks(KS_ARCH_X86, KS_MODE_64)
encoding, count = ks.asm("mov eax, ebx; add eax, 5; ret")
```

`ks.asm(문자열, addr=주소)`을 호출하면 어셈블리 텍스트를 그 아키텍처의 기계어 바이트 리스트로 변환해준다. `addr` 인자를 지정하면 `jmp`/`call`처럼 상대주소를 계산해야 하는 명령어도 올바른 오프셋으로 조립된다.

### 자동 패치 파이프라인의 4단계
1. **원본 읽기** — 대상 바이너리 파일에서 패치할 범위의 raw 바이트를 읽는다.
2. **디스어셈블(Capstone)** — 그 바이트가 어떤 명령어들인지 확인해서, 정확히 어느 명령어를 바꿔야 하는지, 그리고 원본이 차지하는 바이트 수가 몇인지 파악한다.
3. **새 코드 조립(Keystone)** — 원하는 어셈블리 텍스트를 새 기계어 바이트로 변환한다.
4. **바이트 길이 처리 후 파일에 기록** — 새 코드가 원본과 정확히 같은 길이면 그대로 덮어쓰면 되지만, 다르면 아래 두 전략 중 하나를 쓴다.

### 패치 코드가 원본보다 길 때: 코드 동굴(code cave) + jmp 리다이렉트
새 코드가 원래 자리(원본 명령어들이 차지하던 바이트 수)보다 길면, 그 자리에는 남는 공간(주로 파일 끝의 여유 섹션, 흔히 "코드 동굴"이라 부름)으로 점프하는 `jmp` 명령만 심고, 실제 새 로직은 그 코드 동굴에 채워 넣은 뒤 마지막에 원래 흐름으로 되돌아오는 `jmp`를 추가한다. 반대로 새 코드가 원본보다 짧으면 남는 바이트를 `nop`(x86: `0x90`)으로 채워 정렬을 맞춘다.

## 화면/코드에서 보이는 징후
- `from keystone import *`와 `Ks(KS_ARCH_X86, KS_MODE_64)`가 Capstone의 `Cs(CS_ARCH_X86, CS_MODE_64)`와 나란히 등장한다.
- `encoding, count = ks.asm(asm_text, addr)`처럼 두 개의 반환값(바이트 리스트, 명령어 개수)을 받는 코드가 있다.
- `bytes(encoding)`으로 리스트를 바이트열로 변환해서 파일에 `seek`+`write`하는 코드가 있다.
- `b'\x90' * n`처럼 NOP 패딩을 만드는 코드나, 코드 동굴 주소로 향하는 `jmp`를 조립하는 코드가 함께 있다.

## 가장 먼저 할 것
패치하려는 원본 명령어 범위를 Capstone으로 먼저 디스어셈블해서, 정확히 몇 바이트를 차지하는지부터 확인한다. 이 바이트 수를 모르면 새 코드를 몇 바이트까지 채워 넣을 수 있는지, NOP 패딩이 몇 개 필요한지, 코드 동굴이 필요한지조차 판단할 수 없다.

## 단계별 절차

**1) 설치 확인**

```bash
pip install keystone-engine
python3 -c "import keystone; print(keystone.__version__)"
```

**2) 원본 명령어 크기 확인(Capstone)**

```python
from capstone import *

with open('chall', 'rb') as f:
    f.seek(0x1200)
    original_bytes = f.read(16)

md = Cs(CS_ARCH_X86, CS_MODE_64)
total_size = 0
for insn in md.disasm(original_bytes, 0x401200):
    print(f'0x{insn.address:x}: {insn.mnemonic} {insn.op_str} ({insn.size} bytes)')
    total_size += insn.size
    if total_size >= 2:   # 예: 처음 2바이트짜리 명령어 하나만 바꾸고 싶은 경우
        break

print('patch target size:', total_size)
```

**3) 같은 크기로 딱 맞게 패치(가장 단순한 경우)**

원본이 `je 0x401210` (짧은 조건 분기, 2바이트: 0x74 XX)이고 이를 무조건 뛰어넘도록(`jmp`) 바꾸고 싶다고 하자. 짧은 분기(short jump)는 opcode만 `0x74`(je) → `0xEB`(jmp)로 바꾸면 오프셋 바이트는 그대로 재사용할 수 있어 크기가 완전히 동일하게 유지된다.

```python
with open('chall', 'r+b') as f:
    f.seek(0x1200)
    original = f.read(2)
    assert original[0] == 0x74, 'je(short) opcode가 아님'
    patched = bytes([0xEB, original[1]])  # je -> jmp, 오프셋은 그대로 재사용
    f.seek(0x1200)
    f.write(patched)
```

**4) Keystone으로 새 로직을 조립해서 크기가 다를 때(NOP 패딩)**

새 코드가 원본보다 짧으면 남는 자리를 NOP으로 채운다.

```python
from keystone import *

ks = Ks(KS_ARCH_X86, KS_MODE_64)

ORIGINAL_SIZE = 5   # Capstone으로 확인한 원본 명령어 총 바이트 수
NEW_ASM = "xor eax, eax"   # 예: 항상 0을 반환하도록 강제

encoding, count = ks.asm(NEW_ASM)
new_bytes = bytes(encoding)

if len(new_bytes) > ORIGINAL_SIZE:
    raise ValueError('새 코드가 원본보다 커서 코드 동굴이 필요합니다')

padded = new_bytes + b'\x90' * (ORIGINAL_SIZE - len(new_bytes))
print(padded.hex())

with open('chall', 'r+b') as f:
    f.seek(0x1200)
    f.write(padded)
```

**5) 새 코드가 더 클 때: 코드 동굴 + jmp 리다이렉트**

```python
from keystone import *

ks = Ks(KS_ARCH_X86, KS_MODE_64)

PATCH_ADDR = 0x401200      # 원래 패치할 위치(가상주소)
ORIGINAL_SIZE = 5           # 그 자리 원본 명령어들의 총 바이트 수
CAVE_ADDR = 0x402000        # 여유 공간(코드 동굴)의 가상주소
RESUME_ADDR = PATCH_ADDR + ORIGINAL_SIZE  # 패치 후 원래 흐름으로 복귀할 지점

# 1) 코드 동굴에 실제 새 로직 + 원래 흐름 복귀용 jmp를 함께 조립
cave_asm = f"""
xor eax, eax
inc eax
jmp {hex(RESUME_ADDR)}
"""
cave_encoding, _ = ks.asm(cave_asm, addr=CAVE_ADDR)
cave_bytes = bytes(cave_encoding)

# 2) 원래 패치 위치에는 코드 동굴로 향하는 jmp 한 줄만 심는다
jmp_asm = f"jmp {hex(CAVE_ADDR)}"
jmp_encoding, _ = ks.asm(jmp_asm, addr=PATCH_ADDR)
jmp_bytes = bytes(jmp_encoding)

if len(jmp_bytes) > ORIGINAL_SIZE:
    raise ValueError('jmp 명령어조차 원본 자리에 안 들어감(극히 드묾)')

jmp_bytes_padded = jmp_bytes + b'\x90' * (ORIGINAL_SIZE - len(jmp_bytes))

with open('chall', 'r+b') as f:
    f.seek(PATCH_ADDR)          # 가상주소=파일오프셋으로 가정한 단순화(실제로는 섹션 매핑 계산 필요)
    f.write(jmp_bytes_padded)
    f.seek(CAVE_ADDR)
    f.write(cave_bytes)
```

실제 PE/ELF 파일에서는 가상주소와 파일 오프셋이 다를 수 있으므로, 파일에 쓰기 전에 그 섹션의 로드 주소와 파일 오프셋 차이를 반드시 계산해서 보정해야 한다.

## 명령어/단축키
- `Ks(KS_ARCH_X86, KS_MODE_64)` : x64 어셈블러 엔진 생성
- `ks.asm(asm_text, addr=0)` : 어셈블리 텍스트 → `(encoding 리스트, 명령어 개수)`
- `bytes(encoding)` : Keystone 결과를 파이썬 bytes로 변환
- `b'\x90' * n` : x86 NOP n개로 패딩
- Capstone `insn.size` : 원본 명령어들의 정확한 바이트 크기 합산(패치 가능 공간 계산의 기준)
- `jmp 절대주소` (Keystone asm 텍스트에 그대로 씀) : 코드 동굴 리다이렉트에 사용

## 출력 해석
- `ks.asm()`이 예외를 던지면 어셈블리 문법 오류(레이블 미정의, 지원 안 되는 명령어)일 가능성이 크다 — 에러 메시지에 나온 위치를 확인한다.
- 조립된 `encoding` 길이가 예상보다 크면(예: `jmp far_addr`이 5바이트가 아니라 더 크게 조립됨) 상대/절대 주소 인코딩 방식 차이 때문일 수 있다 — 짧은 점프(2바이트)와 근접 점프(5바이트)의 거리 제한을 확인해야 한다.
- 패치 후 Capstone으로 다시 디스어셈블해서 의도한 명령어가 정확히 나오는지 재검증하는 것이 안전하다 — "조립은 성공했지만 의도와 다른 인코딩"인 경우를 사전에 걸러낼 수 있다.

## 흔한 실수
- 원본 명령어의 정확한 바이트 크기를 Capstone으로 확인하지 않고 감으로 크기를 가정해서, 패치가 다음 명령어의 앞부분까지 덮어써버리는 것.
- 새 코드가 원본보다 큰데도 그냥 덮어써서 이후 명령어들을 깨뜨리는 것 — 반드시 크기를 먼저 비교하고 필요하면 코드 동굴 방식으로 전환해야 한다.
- 코드 동굴에 새 로직만 넣고 원래 흐름으로 복귀하는 `jmp`를 빠뜨려서, 패치된 코드가 실행된 후 엉뚱한 다음 명령어로 이어지거나 크래시나는 것.
- 가상주소와 파일 오프셋을 혼동해서 엉뚱한 파일 위치에 바이트를 써넣는 것 — PE/ELF 모두 섹션 헤더의 가상주소(VA/RVA)와 파일 오프셋 매핑을 먼저 확인해야 한다.
- 패치 후 재검증(다시 디스어셈블해서 의도한 명령어인지 확인) 없이 바로 실행해보고 결과가 이상하면 무작정 다시 처음부터 시도하는 것.

## 막혔을 때 다음 체크
- Capstone 디스어셈블 자체가 익숙하지 않다면 → REV-0272 Capstone으로 디스어셈블 자동화
- 패치한 결과를 실제로 실행해서 검증하고 싶다면 → REV-0989 Unicorn 에뮬레이션으로 부분 함수만 실행해서 검증하기 심화
- 패치 없이 검증 로직을 우회하는 다른 방법(값 자체를 역산)이 더 적합할 수도 있다면 → REV-0268 Z3 BitVec 기초, REV-0271 angr 심볼릭 실행 기초

## 미니 예제
`check` 함수 초반의 `test eax, eax; jz fail`(조건 분기)를 무조건 성공 경로로 가도록 패치하는 전체 흐름이다. 원본이 `test eax,eax`(2바이트) + `jz`(짧은 분기, 2바이트) 총 4바이트라고 가정한다.

```python
from capstone import *
from keystone import *

FILE_PATH = 'chall'
PATCH_OFFSET = 0x1300   # 파일 오프셋(사전에 IDA 등으로 확인)

with open(FILE_PATH, 'rb') as f:
    f.seek(PATCH_OFFSET)
    original = f.read(8)

md = Cs(CS_ARCH_X86, CS_MODE_64)
size = 0
for insn in md.disasm(original, 0x401300):
    print(f'{insn.mnemonic} {insn.op_str} ({insn.size}B)')
    size += insn.size
    if insn.mnemonic.startswith('j'):
        break

print('total patch region size:', size)  # 4라고 가정

ks = Ks(KS_ARCH_X86, KS_MODE_64)
# test eax,eax를 그대로 두되(부작용 없음), jz를 jmp로 강제 변경하는 대신
# 아예 처음부터 무조건 통과하도록 xor eax,eax; jmp <success 방향으로 흐르도록 nop 처리>
new_asm = "xor eax, eax\nnop\nnop"   # 4바이트에 맞춰 간단히 구성(예시)
encoding, _ = ks.asm(new_asm)
patched = bytes(encoding)
patched += b'\x90' * (size - len(patched))

with open(FILE_PATH, 'r+b') as f:
    f.seek(PATCH_OFFSET)
    f.write(patched)

# 패치 후 재검증
with open(FILE_PATH, 'rb') as f:
    f.seek(PATCH_OFFSET)
    check = f.read(size)
for insn in md.disasm(check, 0x401300):
    print(f'[patched] {insn.mnemonic} {insn.op_str}')
```

패치 직후 다시 Capstone으로 디스어셈블해서 의도한 명령어가 정확히 들어갔는지 확인하는 마지막 단계가, 실제로 대상 프로그램을 실행해보기 전에 실수를 잡아내는 가장 빠른 방법이다.

## 관련 글
- REV-0272 — Capstone으로 디스어셈블 자동화
- REV-0989 — Unicorn 에뮬레이션으로 부분 함수만 실행해서 검증하기 심화
- REV-0271 — angr 심볼릭 실행 기초

## 출처/검증
- Keystone Engine 공식 문서(keystone-engine.org) 및 공식 GitHub(keystone-engine/keystone)의 파이썬 바인딩 API(`Ks`, `ks.asm`)를 기준으로 정리했다(2026-09-09 검증).
- 코드 동굴(code cave) 및 jmp 리다이렉트를 이용한 바이너리 패치 기법은 일반적인 리버스 엔지니어링/바이너리 패칭 관행에 따른 서술이다.
- `keystone-engine`은 서드파티 패키지이므로 `pip install keystone-engine`이 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
- 코드 예제에 쓰인 x64 기계어/어셈블리는 표준 x86-64 인코딩을 기준으로 구성했으며, 실제 대상 파일의 오프셋/주소는 재현 시 직접 확인해서 교체해야 한다.
