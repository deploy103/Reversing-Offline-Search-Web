---
id: REV-0988
title: "angr로 특정 주소 도달 조건 찾기(find/avoid)"
slug: "rev-0988-angr-find-avoid-addresses"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [angr, Python]
keywords: ["angr find avoid", "angr CFGFast", "angr PIE base", "angr lambda find", "angr 여러 목표 주소", "angr 조건 함수"]
aliases: ["angr find 여러 주소", "angr avoid 여러 주소", "angr find 함수형 조건", "angr PIE 주소 계산"]
symptom_keywords: ["find avoid에 정확히 뭘 넣어야 함", "PIE 바이너리 주소가 안 맞음", "find를 함수로 지정하고 싶음", "성공 지점이 여러 곳일 때 어떻게 함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`simgr.explore(find=..., avoid=...)`의 `find`/`avoid` 인자는 정수 주소 하나뿐 아니라 주소 리스트, 그리고 "이 상태가 목표인지 아닌지"를 직접 판단하는 함수(콜백)까지 받을 수 있어서, 문자열 xref로 찾은 주소를 그대로 쓰는 단순한 경우부터 PIE 바이너리의 런타임 베이스 보정, 반환값/레지스터 조건으로 목표를 정의하는 고급 패턴까지 모두 표현할 수 있다.

## 언제 검색해야 하나
- IDA/Ghidra에서 확인한 "Correct" 문자열 주소를 그대로 넣었는데 PIE 바이너리라 실제 로드 주소와 안 맞을 때
- 성공 출력 지점이 코드 안에 여러 군데 흩어져 있어서 주소를 하나만 지정하기 어려울 때
- 특정 주소 도달이 아니라 "함수가 반환할 때 특정 레지스터 값이 1이다" 같은 조건으로 목표를 정의하고 싶을 때
- `find=addr`를 줬는데 `simgr.found`가 계속 비어서 애초에 주소가 맞는지 의심스러울 때

## 핵심 개념
`explore(find=X, avoid=Y)`에서 `X`, `Y`는 세 가지 형태를 받을 수 있다.

1. **정수 하나** — 가장 단순한 형태. "이 명령어 주소에 도달하면 성공/회피"로 판단한다.
2. **정수(주소)들의 리스트/집합** — 여러 지점 중 아무 곳이나 먼저 도달하면 그 시점에서 멈춘다. 성공 메시지가 여러 함수에서 각각 출력되는 구조일 때 유용하다.
3. **콜백 함수(상태 → bool)** — `lambda state: 조건`형태로, 주소가 아니라 "이 상태의 레지스터/메모리 값이 어떤 조건을 만족하는가"로 목표를 정의한다. `call_state`로 함수 하나만 떼어내 테스트할 때 반환값(`state.regs.eax == 1`)으로 성공을 판정하는 방식이 대표적이다.

### PIE 바이너리와 주소 보정
PIE(Position Independent Executable)로 빌드된 바이너리는 실행할 때마다 로드 베이스 주소가 바뀐다. IDA/Ghidra는 보통 베이스를 `0`(또는 도구별 기본값)으로 가정한 **파일 내부 오프셋**을 보여주는데, angr가 실제로 그 바이너리를 로드했을 때의 베이스 주소는 `proj.loader.main_object.min_addr`로 확인할 수 있다. `find`에 넣을 주소는 "IDA에서 본 오프셋 + angr가 실제로 로드한 베이스"로 계산해야 정확히 일치한다. `auto_load_libs=False`로 라이브러리 로드를 꺼두면 각 오브젝트의 베이스가 더 예측 가능해져서 계산이 쉬워진다.

### CFGFast로 함수/블록 주소를 자동으로 찾기
문자열 xref를 눈으로 하나하나 따라가는 대신, angr 자체의 컨트롤 플로우 그래프 분석(`proj.analyses.CFGFast()`)으로 특정 문자열을 참조하는 코드 블록을 스크립트로 자동 검색할 수도 있다. 이렇게 하면 IDA를 오가지 않고도 `find` 주소를 스크립트 안에서 완전히 자동으로 결정할 수 있다.

## 화면/코드에서 보이는 징후
- `simgr.explore(find=[addr1, addr2])`처럼 리스트가 `find`에 들어간다.
- `simgr.explore(find=lambda s: s.regs.eax == 1)`처럼 람다가 들어간다.
- `proj.loader.main_object.min_addr`로 로드 베이스를 출력하는 코드가 있다.
- `proj.analyses.CFGFast()` 다음에 `cfg.kb.xrefs` 또는 문자열 참조를 순회하는 코드가 있다.

## 가장 먼저 할 것
`find`에 넣을 주소가 진짜 문제인지부터 확인한다. `print(hex(proj.loader.main_object.min_addr))`로 angr가 실제로 로드한 베이스를 출력해보고, PIE 바이너리인데 이 값이 0이 아니라면 IDA에서 본 오프셋에 이 베이스를 더해야 한다.

## 단계별 절차

**1) PIE 베이스 확인 및 주소 보정**

```python
import angr

proj = angr.Project('./chall', auto_load_libs=False)
base = proj.loader.main_object.min_addr
print('load base:', hex(base))

# IDA에서 파일 오프셋 기준 0x1236으로 봤다면
FOUND_OFFSET = 0x1236
FOUND_ADDR = base + FOUND_OFFSET
print('actual find addr:', hex(FOUND_ADDR))
```

Non-PIE 바이너리라면 `base`가 보통 IDA가 보여준 주소와 이미 일치하므로 이 보정이 필요 없는 경우가 많지만, 습관적으로 확인해두면 PIE/non-PIE를 오갈 때 실수를 줄일 수 있다.

**2) 여러 성공 지점을 리스트로 지정**

```python
import angr

proj = angr.Project('./chall', auto_load_libs=False)
state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)

# "Correct!"를 출력하는 코드가 두 함수에 나뉘어 있는 경우
FOUND_ADDRS = [0x401236, 0x401450]
AVOID_ADDRS = [0x401250, 0x401470]

simgr.explore(find=FOUND_ADDRS, avoid=AVOID_ADDRS)

if simgr.found:
    print(simgr.found[0].posix.dumps(0))
```

**3) 콜백 함수로 목표 정의(레지스터 조건)**

```python
import angr, claripy

proj = angr.Project('./chall', auto_load_libs=False)

CHECK_FUNC_ADDR = 0x401100  # 예: int check(char *input) 함수 주소
arg = claripy.BVS('arg', 8 * 16)  # 16바이트 문자열 인자(포인터로 넘기려면 별도 메모리 준비 필요)

state = proj.factory.call_state(CHECK_FUNC_ADDR, arg)
simgr = proj.factory.simgr(state)

# 주소가 아니라 "반환값(eax)이 1인가"로 목표를 정의
simgr.explore(find=lambda s: s.solver.eval(s.regs.eax) == 1)

if simgr.found:
    print(simgr.found[0].solver.eval(arg, cast_to=bytes))
```

**4) CFGFast로 문자열 xref를 자동 검색해서 find 주소 결정**

```python
import angr

proj = angr.Project('./chall', auto_load_libs=False)
cfg = proj.analyses.CFGFast()

target_string = b'Correct!'
found_addr = None

for addr, ref_list in cfg.kb.xrefs.xrefs_by_dst.items():
    # 문자열 상수를 참조하는 블록 주소를 찾는 개념적 예시
    # 실제 문자열 매칭 방법은 angr 버전에 따라 seg/메모리 직접 검색이 필요할 수 있음
    pass

# 간단한 대안: 메모리에서 직접 문자열 위치를 찾고, 그 위치를 참조하는 xref를 조회
string_addr = None
for section in proj.loader.main_object.sections:
    if section.name == '.rodata':
        data = proj.loader.memory.load(section.vaddr, section.memsize)
        idx = data.find(target_string)
        if idx != -1:
            string_addr = section.vaddr + idx
            break

print('string_addr:', hex(string_addr) if string_addr else 'not found')
```

이 방식은 버전에 따라 API 세부사항이 다를 수 있으므로, 실전에서는 문자열 주소를 IDA/Ghidra에서 확인한 뒤 이를 참조하는 코드 블록(xref)만 angr `cfg.kb.xrefs`로 자동 검색하는 하이브리드 방식이 더 안정적이다.

## 명령어/단축키
- `proj.loader.main_object.min_addr` : angr가 실제로 로드한 오브젝트의 베이스 주소
- `simgr.explore(find=addr)` : 단일 주소
- `simgr.explore(find=[addr1, addr2, ...])` : 여러 주소 중 하나
- `simgr.explore(find=lambda s: 조건)` : 상태 조건 콜백
- `proj.analyses.CFGFast()` : 빠른 정적 CFG 분석, xref 조회에 활용
- `state.solver.eval(expr)` : 심볼릭 표현식을 구체값으로 평가
- `state.solver.eval(expr, cast_to=bytes)` : 바이트열로 평가(문자열 인자 등)

## 출력 해석
- `find`에 넣은 주소가 실제 실행 흐름 밖의 값이면(예: 잘못 계산된 PIE 주소) `simgr.found`가 계속 비고 결국 `deadended`/`errored`만 쌓인다 — 이럴 땐 항상 `min_addr` 보정부터 재확인한다.
- 콜백 형태의 `find`가 한 번도 참을 반환하지 않으면, `call_state`로 넘긴 인자 준비 방식(포인터 vs 값 전달)이 실제 함수 시그니처와 다를 가능성을 의심해야 한다.
- 리스트로 넘긴 `find` 중 어느 주소에서 멈췄는지 확인하려면 `found_state.addr`를 출력해서 실제 도달 지점을 역으로 확인할 수 있다.

## 흔한 실수
- PIE 바이너리인데 IDA에서 본 주소를 그대로 `find`에 넣어서 계속 실패하는 것 — 반드시 `min_addr`로 실제 로드 베이스를 확인해야 한다.
- `call_state`에 문자열 인자를 넘길 때 실제로는 포인터가 필요한데 `BVS` 값 자체를 그대로 넘겨서 함수가 엉뚱한 메모리를 역참조하다 에러가 나는 것 — 문자열 인자는 별도 메모리에 심볼릭 바이트를 써넣고 그 주소를 인자로 넘겨야 한다.
- 콜백 조건에서 `s.regs.eax`처럼 아직 심볼릭인 값을 `==` 비교 없이 그대로 `if`문에 써서 파이썬 예외(`ClaripyError`, 모호한 진위 판단)가 나는 것 — 반드시 `s.solver.eval(...)`이나 Z3 스타일 조건식으로 비교해야 한다.
- 여러 목표 주소를 리스트로 넣어놓고 어느 주소에서 멈췄는지 확인하지 않아, 의도와 다른(더 이른) 성공 지점에서 멈춘 것을 알아채지 못하는 것.

## 막혔을 때 다음 체크
- 상태가 너무 많아져서 탐색 자체가 안 끝난다면 → REV-0987 angr 심볼릭 실행 심화(상태 탐색 전략)
- 기본 `find`/`avoid` 개념 자체가 처음이라면 → REV-0271 angr 심볼릭 실행 기초
- `RecursionError`가 발생한다면 → REV-0991 angr에서 RecursionError가 발생할 때
- 상태 공간이 다 소진되도록 못 찾으면 → REV-0992 angr 탐색이 State Explosion으로 끝나지 않을 때

## 미니 예제
PIE로 빌드된 바이너리에서 "Correct!"가 두 갈래 함수 중 어디서든 출력되면 성공으로 간주하는 예제다.

```python
import angr

proj = angr.Project('./pie_chall', auto_load_libs=False)
base = proj.loader.main_object.min_addr

# IDA에서 파일 오프셋 기준으로 확인한 값들
FOUND_OFFSETS = [0x1236, 0x1450]
AVOID_OFFSETS = [0x1250, 0x1470]

FOUND_ADDRS = [base + off for off in FOUND_OFFSETS]
AVOID_ADDRS = [base + off for off in AVOID_OFFSETS]

state = proj.factory.entry_state()
simgr = proj.factory.simgr(state)
simgr.explore(find=FOUND_ADDRS, avoid=AVOID_ADDRS)

if simgr.found:
    hit = simgr.found[0]
    print('reached:', hex(hit.addr))
    print('input:', hit.posix.dumps(0))
else:
    print('not found')
```

`base`를 실제 로드 주소에서 자동으로 가져오기 때문에, 같은 스크립트를 PIE 여부가 다른 여러 바이너리에도 오프셋만 바꿔서 재사용할 수 있다.

## 실전 예시: avoid도 콜백으로, find는 메모리 내용으로 판단하기
지금까지 본 `avoid`는 항상 고정 주소나 주소 리스트였다. 하지만 실전에서는 "실패"가 특정 주소 하나가 아니라 **특정 레지스터 값이 에러 코드를 갖는 모든 경우**로 정의되는 경우도 있다. 이럴 때는 `avoid`에도 `find`처럼 콜백 함수를 그대로 쓸 수 있다. 또한 결과가 레지스터가 아니라 **메모리에 쓰인 값**(예: 전역 변수 `result`)으로 판정되는 함수도 있는데, 이 경우 `state.memory.load()`로 그 메모리 값을 직접 읽어 조건으로 삼는다.

```python
import angr, claripy

proj = angr.Project('./chall', auto_load_libs=False)

CHECK_FUNC_ADDR = 0x401100   # int check(char *input) 함수 주소
RESULT_ADDR = 0x404040        # 전역 변수 int result; 가 위치한 주소(리버싱으로 확인)
ERROR_EAX = 0xdead             # 함수가 내부 에러 시 eax에 남기는 특수 값(리버싱으로 확인)

arg = claripy.BVS('arg', 8 * 16)   # 16바이트 문자열 인자를 표현하는 심볼릭 값
state = proj.factory.call_state(CHECK_FUNC_ADDR, arg)
simgr = proj.factory.simgr(state)

def is_success(s):
    # 성공 여부를 레지스터가 아니라 전역 변수 result의 메모리 값으로 판정한다
    result_val = s.memory.load(RESULT_ADDR, 4)          # 4바이트(int) 읽어오기
    return s.solver.eval(result_val) == 1                  # result == 1 이면 성공

def is_error(s):
    # 실패 조건을 "특정 주소"가 아니라 "eax가 에러 코드와 같은 모든 상태"로 정의한다
    return s.solver.eval(s.regs.eax) == ERROR_EAX

simgr.explore(find=is_success, avoid=is_error)

if simgr.found:
    solution = simgr.found[0].solver.eval(arg, cast_to=bytes)
    print('input:', solution)
else:
    print('not found')
```

여기서 `avoid=is_error`는 프로그램 실행 중 `eax`가 `0xdead`가 되는 **모든 지점**을 회피 대상으로 삼는다 — 그 값이 코드의 몇 군데에서 만들어지든 주소를 일일이 찾아 나열할 필요가 없다는 뜻이다. 마찬가지로 `find=is_success`는 특정 명령어 주소가 아니라 "전역 변수 `result`가 1이 되었는가"라는, 프로그램의 관찰 가능한 상태 자체를 조건으로 쓴다. `s.regs.eax`나 `s.memory.load(...)`가 반환하는 값은 아직 구체적인 숫자가 아니라 심볼릭 표현식이므로, 반드시 `s.solver.eval(...)`로 평가한 뒤에 `==`로 비교해야 한다는 점은(앞서 "흔한 실수"에서 다룬 대로) 여기서도 그대로 적용된다.

## 관련 글
- REV-0271 — angr 심볼릭 실행 기초
- REV-0987 — angr 심볼릭 실행 심화(상태 탐색 전략)
- REV-0991 — angr에서 RecursionError가 발생할 때
- REV-0992 — angr 탐색이 State Explosion으로 끝나지 않을 때

## 출처/검증
- `simgr.explore`의 `find`/`avoid` 인자가 주소, 리스트, 콜백을 모두 받을 수 있다는 사실과 `CFGFast`, `min_addr` API는 angr 공식 문서(docs.angr.io)의 "Simulation Manager" 및 "CFG Recovery" 챕터를 기준으로 정리했다(2026-09-09 검증).
- PIE 실행 파일의 런타임 로드 베이스 개념은 System V ABI 문서의 "Position-Independent Code" 설명과 일치한다.
- `angr`는 서드파티 패키지이므로 `pip install angr`가 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
