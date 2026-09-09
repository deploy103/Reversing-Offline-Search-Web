---
id: REV-0998
title: "Capstone/Keystone 아키텍처 설정을 잘못해서 결과가 이상할 때"
slug: "rev-0998-capstone-keystone-arch-mode-mismatch"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Capstone, Keystone, Python]
keywords: ["CS_ARCH CS_MODE 잘못됨", "KS_ARCH KS_MODE 잘못됨", "capstone 결과 이상함", "keystone 어셈블 실패", "capstone keystone 아키텍처 불일치"]
aliases: ["capstone 디스어셈블이 이상하게 나옴", "keystone asm 에러", "capstone 32비트 64비트 헷갈림", "keystone KsError"]
symptom_keywords: ["capstone 결과가 전부 이상한 명령어로 나옴", "keystone에서 어셈블이 안 됨", "디스어셈블 결과가 원본과 다름", "keystone KsError가 남"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Capstone(디스어셈블러)과 Keystone(어셈블러)은 둘 다 엔진을 만들 때 아키텍처(`CS_ARCH_*`/`KS_ARCH_*`)와 모드(`CS_MODE_*`/`KS_MODE_*`)를 명시적으로 지정해야 하며, 이 값이 실제 대상 바이트/코드와 다르면 예외 없이 조용히 완전히 엉뚱한(하지만 문법적으로는 유효해 보이는) 결과를 내놓거나 어셈블 자체에 실패하기 때문에, 결과가 이상하면 가장 먼저 의심해야 할 것이 바로 이 아키텍처/모드 설정이다.

## 언제 검색해야 하나
- Capstone으로 디스어셈블한 결과가 원래 알고 있던 명령어와 전혀 다르게 나올 때
- Keystone으로 어셈블한 바이트열을 다시 디스어셈블했더니 원래 의도한 명령어가 안 나올 때
- 32비트 바이너리인지 64비트 바이너리인지 확인하지 않고 스크립트를 짜서 결과가 이상하게 나올 때
- `CS_MODE_32`와 `CS_MODE_64`, 또는 `KS_MODE_32`와 `KS_MODE_64`의 차이와 올바른 선택 기준이 헷갈릴 때

## 핵심 개념
Capstone과 Keystone은 서로 반대 방향의 작업을 하는 짝꿍 라이브러리다. **Capstone**은 "바이트열 → 사람이 읽는 명령어"(디스어셈블), **Keystone**은 "사람이 쓰는 어셈블리 텍스트 → 바이트열"(어셈블)을 한다. 둘 다 엔진 생성 시 반드시 두 가지를 지정해야 한다.

1. **아키텍처(arch)** — x86 계열인지, ARM인지, MIPS인지 등. 예: `CS_ARCH_X86`/`KS_ARCH_X86`.
2. **모드(mode)** — 같은 아키텍처 안에서도 비트 폭이나 세부 동작 방식이 다르다. x86 계열에서 가장 흔한 것이 `CS_MODE_32`(32비트 x86)와 `CS_MODE_64`(64비트 x64)다. Keystone도 동일하게 `KS_MODE_32`/`KS_MODE_64`가 있다.

문제는 이 아키텍처/모드가 실제 코드와 다르더라도 **프로그램이 죽거나 명확한 에러를 내는 것이 아니라, 그냥 다른 방식으로 바이트를 해석해서 조용히 엉뚱한 결과를 내놓는다**는 점이다. x86 계열은 명령어 인코딩이 32비트와 64비트에서 상당 부분 겹치기 때문에(특히 프리픽스 바이트나 레지스터 인코딩), 모드를 잘못 지정해도 "문법적으로 유효한 것처럼 보이는" 명령어가 출력되는 경우가 많다. 이것이 이 문제를 특히 알아채기 어렵게 만든다.

또한 Capstone에서 디스어셈블 시작 위치를 잘못 잡는 것(가변 길이 x86 명령어 특성상 한 바이트만 밀려도 그 이후 전부 다르게 해석됨)도 아키텍처 문제와 겉보기 증상이 비슷하므로 함께 점검해야 한다.

## 화면/코드에서 보이는 징후
```python
from capstone import *

# 실제로는 64비트 코드(mov rax, rbx ; ret)인 바이트열을 32비트 모드로 잘못 열기
code = b'\x48\x89\xd8\xc3'
md = Cs(CS_ARCH_X86, CS_MODE_32)  # 잘못된 모드
for insn in md.disasm(code, 0x1000):
    print(insn.mnemonic, insn.op_str)
```
출력 예(원래 의도와 전혀 다른 명령어들):
```text
dec eax
mov eax, ebx
ret
```
`0x48`이 64비트 모드에서는 REX 프리픽스(64비트 레지스터를 쓰겠다는 표시)인데, 32비트 모드에서는 `dec eax`라는 완전히 다른 독립 명령어로 해석되어 그 뒤 바이트 정렬까지 전부 어긋난다. 에러 없이 "그럴듯한" 명령어가 나오기 때문에 눈으로만 봐서는 뭐가 잘못됐는지 알아채기 어렵다.

Keystone에서는 아키텍처/모드가 완전히 안 맞으면 보통 예외를 던진다.
```python
from keystone import *

ks = Ks(KS_ARCH_X86, KS_MODE_64)
try:
    encoding, count = ks.asm("mov r8, rax")  # 64비트 전용 레지스터
except KsError as e:
    print("에러:", e)
```
반면 모드를 32비트로 잘못 설정하면 `r8`처럼 64비트 전용 레지스터 이름 자체를 인식하지 못해 `KsError`가 명확히 발생하는 경우가 많다 — 이 경우는 오히려 알아채기 쉬운 편이다. 진짜 위험한 경우는 앞의 Capstone 예시처럼 **에러 없이 조용히 다른 결과**가 나오는 쪽이다.

## 가장 먼저 할 것
대상 바이트/바이너리가 정확히 어떤 아키텍처와 비트 폭인지부터 확인한다. 리눅스라면 `file 바이너리이름`, 윈도우 PE라면 PE 헤더의 `Machine` 필드(예: `0x14c`=x86, `0x8664`=x64)를 먼저 본다. 확신 없이 `CS_MODE_64`/`CS_MODE_32`를 습관적으로 고정해서 쓰지 않는다.

## 단계별 절차

**1) 대상 아키텍처 확인**
```bash
file ./chall
# 출력 예: ELF 64-bit LSB executable, x86-64, ...
```

**2) 확인한 아키텍처에 맞게 Capstone 엔진 생성**
```python
from capstone import *

# 64비트 ELF/PE로 확인됐다면
md = Cs(CS_ARCH_X86, CS_MODE_64)
```

**3) 의심되는 결과를 다른 모드로도 한 번 더 디스어셈블해서 비교**
```python
from capstone import *

code = b'\x48\x89\xd8\xc3'

for mode_name, mode in [('32bit', CS_MODE_32), ('64bit', CS_MODE_64)]:
    md = Cs(CS_ARCH_X86, mode)
    print(f'--- {mode_name} ---')
    for insn in md.disasm(code, 0x1000):
        print(f'0x{insn.address:x}: {insn.mnemonic} {insn.op_str}')
```
두 모드의 결과를 나란히 비교하면, 어느 쪽이 "말이 되는" 코드인지(예: 함수가 `ret`으로 자연스럽게 끝나는지, 알려진 문자열/상수 값과 일치하는지) 판단하는 데 도움이 된다.

**4) Keystone도 동일한 아키텍처/모드로 맞추기**
```python
from keystone import *

ks = Ks(KS_ARCH_X86, KS_MODE_64)  # 대상이 64비트라면 반드시 64로
encoding, count = ks.asm("mov rax, rbx; ret")
print(bytes(encoding))
```

**5) Keystone으로 어셈블한 결과를 Capstone으로 다시 디스어셈블해서 왕복 검증**
```python
from keystone import *
from capstone import *

ks = Ks(KS_ARCH_X86, KS_MODE_64)
encoding, _ = ks.asm("xor eax, eax; inc eax; ret")
raw = bytes(encoding)

md = Cs(CS_ARCH_X86, CS_MODE_64)
for insn in md.disasm(raw, 0x1000):
    print(insn.mnemonic, insn.op_str)
```
이렇게 어셈블 → 디스어셈블을 왕복시켜서 원래 의도한 명령어와 같은 결과가 나오는지 확인하면, 두 엔진의 아키텍처/모드가 서로 일치하는지 교차 검증할 수 있다.

## 명령어/단축키
- `Cs(CS_ARCH_X86, CS_MODE_32|CS_MODE_64)` : Capstone x86 엔진 생성(32/64비트 선택)
- `Ks(KS_ARCH_X86, KS_MODE_32|KS_MODE_64)` : Keystone x86 엔진 생성(32/64비트 선택)
- `file 바이너리` : 리눅스에서 ELF의 아키텍처/비트 폭을 즉시 확인
- `md.disasm(code, addr)` : Capstone 디스어셈블 실행
- `ks.asm("어셈블리 텍스트")` : Keystone 어셈블 실행, `(encoding, count)` 튜플 반환
- `CS_ARCH_ARM`, `CS_ARCH_MIPS`, `KS_ARCH_ARM`, `KS_ARCH_MIPS` 등 : x86 외 다른 아키텍처 대상 시 반드시 대상에 맞게 변경

## 출력 해석
- 결과 명령어들이 원래 알던 코드와 전혀 다르지만 "문법적으로는 그럴듯하게" 보인다 — 아키텍처/모드 불일치를 최우선으로 의심한다. 에러가 안 났다고 결과가 맞다는 보장이 절대 아니다.
- `KsError: ... invalid operand` — Keystone에서 지정한 모드에 존재하지 않는 레지스터/명령어를 어셈블하려 한 경우(예: 32비트 모드에서 `r8`~`r15` 사용). 모드를 재확인한다.
- Capstone/Keystone 두 엔진에 서로 다른 모드를 넣은 뒤 왕복 검증(어셈블 후 디스어셈블)했을 때 결과가 원래 의도와 다르다 — 두 엔진의 모드 설정이 서로 어긋나 있다는 뜻이다.

## 흔한 실수
- 프로젝트 초반에 한 번 `CS_MODE_64`로 엔진을 만들어 놓고, 나중에 32비트 바이너리를 분석할 때도 그 엔진을 재사용하는 것.
- x86 명령어 인코딩이 32비트/64비트에서 상당 부분 겹친다는 사실을 몰라서, "에러가 안 났으니 결과가 맞다"고 안심하는 것 — Capstone/Keystone은 모드가 틀려도 대부분 예외 없이 그럴듯한 결과를 낸다.
- 디스어셈블 시작 주소(파일 오프셋 vs 가상주소)를 혼동해서, 아키텍처/모드는 맞는데 상대주소 오퍼랜드(`call`, `jmp`)만 이상하게 나오는 것을 모드 문제로 오인하는 것.
- ARM처럼 엔디안/Thumb 모드가 추가로 있는 아키텍처에서, x86만큼 익숙하지 않아 모드 플래그(`CS_MODE_THUMB`, `CS_MODE_LITTLE_ENDIAN` 등)를 빠뜨리는 것.

## 막혔을 때 다음 체크
- Capstone 자체의 기본 사용법이 헷갈리면 → REV-0272 Capstone으로 디스어셈블 자동화.
- 디스어셈블한 코드가 실제로 어떤 값을 만들어내는지까지 확인하려면 → REV-0273 Unicorn으로 작은 검증 함수 에뮬레이션(에뮬레이션 엔진도 아키텍처/모드를 별도로 맞춰야 한다는 점은 동일하다).
- 대상 바이너리의 아키텍처 자체를 확인하는 방법이 필요하면 → 이진 파일 형식 분류(예: `file` 명령, PE `Machine` 필드) 관련 문서를 triage/binary-basics 카테고리에서 참고한다.

## 미니 예제
같은 4바이트를 32비트/64비트 두 모드로 각각 디스어셈블해서 결과가 완전히 달라지는 것을 직접 비교한다.
```python
from capstone import *

code = b'\x48\x89\xd8\xc3'  # 의도: mov rax, rbx ; ret (64비트 코드)

print('--- 잘못된 모드(32비트로 해석) ---')
md32 = Cs(CS_ARCH_X86, CS_MODE_32)
for insn in md32.disasm(code, 0x1000):
    print(f'0x{insn.address:x}: {insn.mnemonic} {insn.op_str}')

print('--- 올바른 모드(64비트로 해석) ---')
md64 = Cs(CS_ARCH_X86, CS_MODE_64)
for insn in md64.disasm(code, 0x1000):
    print(f'0x{insn.address:x}: {insn.mnemonic} {insn.op_str}')
```
출력 예:
```text
--- 잘못된 모드(32비트로 해석) ---
0x1000: dec eax
0x1001: mov eax, ebx
0x1003: ret
--- 올바른 모드(64비트로 해석) ---
0x1000: mov rax, rbx
0x1003: ret
```
동일한 바이트열인데도 모드 하나 때문에 명령어 개수, 의미, 심지어 주소 정렬까지 완전히 달라진다는 것을 확인할 수 있다. 이것이 바로 아키텍처/모드 확인을 가장 먼저 해야 하는 이유다.

### 에러를 재현하는 잘못된 코드 vs 고쳐서 정상 동작하는 코드 (Keystone 쪽 KsError)
앞의 Capstone 예시는 "에러 없이 조용히 틀린 결과"가 나오는 위험한 경우였다. 이번에는 반대로, Keystone에서 모드를 잘못 지정하면 **명확한 예외**가 나서 오히려 알아채기 쉬운 경우를 재현한다. `pip install keystone-engine`만 되어 있으면 그대로 실행된다.

**잘못된 코드 — 64비트 전용 레지스터를 32비트 모드 엔진으로 어셈블 시도**
```python
from keystone import *

# *** 잘못된 부분: 대상이 실제로는 64비트 바이너리인데 엔진을 32비트 모드로 생성함 ***
ks_wrong = Ks(KS_ARCH_X86, KS_MODE_32)   # 잘못된 모드
try:
    # r8, rax는 64비트 전용 레지스터라서 32비트 모드 엔진은 이 이름 자체를 모른다
    encoding, count = ks_wrong.asm("mov r8, rax")
    print(bytes(encoding))
except KsError as e:
    print('어셈블 실패:', e)   # KsError: 32비트 모드에는 r8/rax 같은 64비트 레지스터가 없음
```

**고친 코드 — 대상 아키텍처를 먼저 확인하고 올바른 모드로 엔진 생성**
```python
from keystone import *

# 리눅스라면 먼저 `file 대상바이너리`로 "x86-64"인지 "Intel 80386"인지 확인한 뒤 모드를 정한다.
# 여기서는 대상이 64비트로 확인됐다고 가정한다.
ks_fixed = Ks(KS_ARCH_X86, KS_MODE_64)   # 올바른 모드
encoding, count = ks_fixed.asm("mov r8, rax")
print('어셈블 성공, 바이트:', bytes(encoding).hex())   # 정상적으로 기계어 바이트가 생성됨

# 왕복 검증: 방금 만든 바이트를 같은 모드의 Capstone으로 다시 디스어셈블해서 의도와 일치하는지 확인
from capstone import *
md = Cs(CS_ARCH_X86, CS_MODE_64)
for insn in md.disasm(bytes(encoding), 0x0):
    print(f'{insn.mnemonic} {insn.op_str}')   # mov r8, rax
```
잘못된 코드는 `KsError`라는 명시적인 예외로 실패를 즉시 알려주지만, 바로 앞의 Capstone 예시처럼 "모드가 틀렸는데도 예외 없이 그럴듯한 결과가 나오는" 경우가 훨씬 위험하다는 점을 함께 기억해야 한다.

## 관련 글
- REV-0272 — Capstone으로 디스어셈블 자동화
- REV-0273 — Unicorn으로 작은 검증 함수 에뮬레이션
- REV-0271 — angr 심볼릭 실행 기초

## 출처/검증
- Capstone `CS_ARCH_*`/`CS_MODE_*` API와 x86 32비트/64비트 인코딩 겹침으로 인한 오디스어셈블 가능성은 Capstone 공식 문서(capstone-engine.org) 및 공식 GitHub(capstone-engine/capstone)를 기준으로 정리했다(2026-09-09 검증).
- Keystone `KS_ARCH_*`/`KS_MODE_*` API와 `KsError` 동작은 Keystone 공식 문서(keystone-engine.org) 및 공식 GitHub(keystone-engine/keystone) 기준이다.
- x86 REX 프리픽스(`0x40`~`0x4f`)가 64비트 모드 전용이며 32비트 모드에서는 다른 단일 바이트 명령어로 해석된다는 점은 Intel 64 and IA-32 Architectures Software Developer's Manual 기준이다.
- 코드 예제는 `pip install capstone keystone-engine` 환경의 표준 CPython 3에서 그대로 재현 가능하다.
