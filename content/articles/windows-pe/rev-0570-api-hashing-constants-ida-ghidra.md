---
id: REV-0570
title: "API Hashing 상수를 IDA/Ghidra에서 찾는 법"
slug: "rev-0570-api-hashing-constants-ida-ghidra"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, Ghidra, x64dbg]
keywords: ["API Hashing", "IDAPython", "Ghidra Script", "해시 상수 매칭", "hash lookup table", "ROR13 매칭"]
aliases: ["해시 상수 찾기", "API 해시 브루트포스", "IDAPython 해시 스크립트", "Ghidra 해시 스크립트"]
symptom_keywords: ["매직넘버가 여러 개 있는데 뭔지 모르겠다", "IDAPython으로 해시를 계산하고 싶다", "Ghidra 스크립트로 해시 매칭하고 싶다", "해시값 목록을 API 이름으로 바꾸고 싶다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
REV-0569에서 API Hashing의 원리를 이해했다면, 이번 글은 실제로 IDA/Ghidra에서 그 해시 상수들을 자동으로 찾아내고, 스크립트로 알려진 API 이름과 매칭시켜 함수 이름을 자동으로 붙이는 실전 작업 흐름을 다룬다 — 상수를 하나하나 손으로 계산하는 것은 현실적이지 않으므로 IDAPython/Ghidra 스크립팅이 사실상 필수다.

## 언제 검색해야 하나
- REV-0569를 읽고 API Hashing의 원리는 이해했는데, 실제 샘플에서 수십~수백 개의 해시 상수를 어떻게 일일이 매칭할지 막막할 때
- IDAPython이나 Ghidra 스크립트로 해시를 계산해서 함수 이름을 자동으로 붙이는 방법이 필요할 때
- 디스어셈블리에서 해시 계산 함수는 찾았는데, 그 함수가 어떤 상수들과 비교되는지 한꺼번에 뽑아내고 싶을 때

## 핵심 개념
API Hashing 상수를 실전에서 풀어내는 작업은 크게 세 단계로 나뉜다: (1) 바이너리 안의 해시 상수를 모두 추출하기, (2) 해시 알고리즘을 재구현해 알려진 API 이름들의 해시값 룩업 테이블을 만들기, (3) 두 목록을 매칭해 이름을 복원하고 IDA/Ghidra에 자동으로 주석/이름을 붙이기.

**1단계: 상수 추출**는 두 가지 방식이 있다. 첫째는 IDA에서 해시 비교(`cmp reg, immediate`) 패턴을 검색(`Alt+B`로 바이너리 검색하거나, IDAPython으로 명령어를 순회하며 `cmp`이고 두 번째 오퍼랜드가 즉시값인 경우를 필터링)하는 방법이다. 둘째는 동적 분석으로, x64dbg에서 해시 계산 함수에 브레이크포인트를 걸고 리턴값을 로그로 남기는 방법인데, 이 방식은 실제로 그 실행 경로에서 쓰인 API만 잡히므로 정적 추출보다 커버리지가 낮을 수 있다.

**2단계: 룩업 테이블 생성**은 IDAPython/Ghidra 스크립트로 대상 DLL(`kernel32.dll`, `ntdll.dll`, `advapi32.dll`, `user32.dll`, `ws2_32.dll`, `wininet.dll` 등 실제로 시스템에 설치된 DLL 파일)의 익스포트 이름을 읽어와, 코드에서 재구현한 것과 동일한 해시 함수를 각 이름에 적용해 `{해시값: 함수이름}` 딕셔너리를 만드는 것이다. 여기서 가장 중요한 것은 대소문자 정규화 여부, 널 종료 포함 여부, 회전 방향과 비트 수를 디스어셈블리와 **정확히** 동일하게 재현하는 것이다.

**3단계: 매칭 및 자동 주석**은 1단계에서 뽑은 상수 목록을 2단계의 딕셔너리에서 조회해서, 일치하는 항목이 있으면 IDA에서 해당 상수가 쓰인 주소에 코멘트를 달거나(`idc.set_cmt`), 근처 변수/함수 이름을 바꿔주는(`idc.set_name`) 자동화 스크립트로 마무리한다.

이 워크플로우는 한 번 스크립트를 만들어두면 같은 패커/악성코드 계열의 다른 샘플에도 거의 그대로 재사용할 수 있다는 것이 실전에서 큰 이점이다.

## 화면/코드에서 보이는 징후
- IDA에서 `cmp eax, offset`류가 아니라 `cmp eax, 12345678h` 형태로 즉시값 비교가 연달아 여러 개(보통 5개 이상) 나오는 함수 — 해시 디스패치 함수일 가능성
- Ghidra 디컴파일 결과에서 `if (uVar1 == 0x91afca54) { ... }` 같은 조건문이 반복되는 함수
- 같은 매직넘버가 서로 다른 위치에서 재사용되는 경우 — 같은 API를 여러 곳에서 호출할 때 해시 계산을 다시 안 하고 캐시된 함수 포인터를 쓰거나, 상수 자체가 재사용됨

## 가장 먼저 할 것
1. 해시 계산 루틴(REV-0569에서 찾은 `ror`/`add` 루프)을 정확히 손으로 옮겨 적어 파이썬 함수로 재구현한다. 이 재구현이 틀리면 이후 모든 매칭이 실패한다.
2. Python `ctypes` 없이도 `ctypes.c_uint32` 연산이나 `& 0xFFFFFFFF` 마스킹으로 32비트 오버플로우를 정확히 재현했는지 확인한다(파이썬 정수는 임의 정밀도이므로 마스킹을 빼먹으면 상위 비트가 사라지지 않아 결과가 틀어진다).

## 단계별 절차
**1) 해시 함수 파이썬으로 재구현 및 검증**
```python
def api_hash(name: str) -> int:
    h = 0
    for ch in name.upper():          # 대소문자 정규화 여부는 디스어셈블리로 반드시 확인
        h = ((h >> 13) | (h << (32 - 13))) & 0xFFFFFFFF  # ROR13
        h = (h + ord(ch)) & 0xFFFFFFFF
    return h

assert api_hash("VirtualAlloc") == 0x91AFCA54  # 실제 값은 샘플마다 재현 필요
```
- 이미 알고 있는 상수-함수명 쌍이 하나라도 있다면(예: 디버거로 확인한 값) 이걸로 재구현이 맞는지 먼저 검증한다.

**2) 대상 DLL의 익스포트 이름을 IDAPython으로 덤프**
```python
import idautils, ida_nalt

def dump_exports(dll_path):
    # 실제로는 대상 DLL 파일(System32의 kernel32.dll 등)을 별도로 열어
    # Exports 리스트를 얻는 방식이 가장 정확하다.
    names = []
    for ea, ordinal, name, _ in idautils.Entries():
        names.append(name)
    return names
```
- IDA에서 분석 중인 파일이 아니라 시스템에 실제 설치된 `kernel32.dll` 등을 별도로 열어 Exports 탭(`Shift+F11`)의 이름 목록을 뽑는 것이 가장 정확하다. 여러 DLL(`kernel32`, `ntdll`, `advapi32`, `user32`, `ws2_32` 등)을 대상으로 반복한다.

**3) 룩업 테이블 생성 및 매칭**
```python
lookup = {api_hash(name): name for name in dump_exports("kernel32.dll")}

found_constants = [0x91AFCA54, 0x7C0DFCAA, 0xE449F330]  # 1단계에서 IDA로 추출한 값들
for h in found_constants:
    print(hex(h), "->", lookup.get(h, "매칭 없음, 다른 DLL 확인 필요"))
```
- 매칭이 안 되는 값은 다른 DLL(`ntdll.dll`, `ws2_32.dll` 등)의 익스포트로도 시도해본다.

**4) IDA에 자동으로 이름/주석 붙이기**
```python
import idc
matches = {0x91AFCA54: "VirtualAlloc", 0x7C0DFCAA: "WriteProcessMemory"}
for ea in idautils.Heads():
    if idc.print_insn_mnem(ea) == "cmp":
        val = idc.get_operand_value(ea, 1)
        if val in matches:
            idc.set_cmt(ea, matches[val], 0)
```
- 이 스크립트를 `File → Script file...`(`Alt+F7`)로 실행하면 매칭된 상수가 있는 모든 `cmp` 명령어 위치에 실제 함수 이름이 주석으로 자동으로 달린다.

**5) Ghidra에서 동일 작업**
- Ghidra는 Script Manager(`Window → Script Manager`, 또는 상단 초록색 재생 버튼 아이콘)에서 Python 또는 Java 스크립트를 새로 만들어 같은 로직을 구현한다. `currentProgram.getListing()`으로 명령어를 순회하고, 상수 오퍼랜드를 `Instruction.getOpObjects()`로 추출한 뒤, 매칭되면 `setComment(...)`로 주석을 단다.

## 명령어/단축키
- IDA: `Alt+F7`(스크립트 파일 실행), `Shift+F2`(IDAPython 즉시 실행 콘솔), `Shift+F11`(Exports)
- Ghidra: `Window → Script Manager`(스크립트 관리자), 스크립트 생성 후 상단 재생(▶) 버튼으로 실행
- x64dbg: 해시 함수 리턴 지점에 조건부 로그 브레이크포인트(`Log`)를 걸어 실제 실행 중 계산된 해시값을 확인 가능

## 출력 해석
- 매칭된 함수 이름들을 모아보면 어떤 DLL 계열(파일 I/O, 네트워크, 프로세스 조작 등)이 주로 쓰이는지 한눈에 드러나며, 이는 REV-0569에서 말한 "정적 분석으로 기능 추정"을 다시 가능하게 해준다.
- 매칭이 하나도 안 되는 상수가 많다면 해시 알고리즘 재구현이 틀렸거나(회전 방향/비트수 재확인), 대상 DLL 목록에 실제로 쓰인 DLL이 빠져 있을 가능성이 크다.

## 흔한 실수
- 파이썬 정수 연산에서 32비트 마스킹(`& 0xFFFFFFFF`)을 빼먹어 회전/덧셈 결과가 실제 CPU 연산과 달라지는 것. 반드시 매 연산마다 마스킹한다.
- 대소문자 정규화 여부를 확인하지 않고 무작정 소문자/대문자 중 하나로만 시도하는 것. 디스어셈블리에서 `and`/`or`로 대소문자를 강제 변환하는 코드가 있는지 먼저 확인해야 한다.
- 익스포트 이름 목록을 분석 대상 파일 자체에서 뽑으려는 것. API Hashing을 쓰는 샘플 자체는 대개 Import/Export가 거의 없으므로, 대상 DLL(`kernel32.dll` 등)을 시스템에서 별도로 열어 이름을 뽑아야 한다.
- 한 번에 모든 DLL을 다 시도하지 않고 `kernel32.dll`만 시도한 뒤 매칭이 안 된다고 포기하는 것. `ntdll.dll`, `advapi32.dll`, `ws2_32.dll`, `wininet.dll`, `shell32.dll` 등도 흔히 쓰인다.

## 막혔을 때 다음 체크
- 해시 알고리즘 자체의 개념이나 왜 쓰이는지 헷갈리면 → REV-0569(Import 함수를 런타임에 해시로 찾는 API Hashing 개념)를 먼저 복습한다.
- 매칭한 API 목록으로 전체 동작을 추정하려면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.
- 이 기법이 인젝션 코드와 함께 나온다면 → REV-0568(프로세스 할로잉 개념 소개), REV-0567(Reflective DLL Loading 개념 소개)을 함께 확인한다.

## 미니 예제
아래는 위 절차를 하나로 합친 최소 스크립트 예시다(IDAPython 콘솔에 붙여넣어 바로 실행 가능한 형태).

```python
def api_hash(name):
    h = 0
    for ch in name.upper():
        h = ((h >> 13) | (h << 19)) & 0xFFFFFFFF
        h = (h + ord(ch)) & 0xFFFFFFFF
    return h

known_apis = ["VirtualAlloc", "WriteProcessMemory", "CreateRemoteThread",
              "GetProcAddress", "LoadLibraryA", "NtUnmapViewOfSection"]

lookup = {api_hash(n): n for n in known_apis}
target_constant = 0x91AFCA54
print(lookup.get(target_constant, "목록에 없음 — DLL 익스포트 전체를 대상으로 확장 필요"))
```
이렇게 만든 `api_hash` 함수와 룩업 테이블은, 실제 샘플에서 발견한 매직넘버 리스트를 통째로 넣고 한 번에 돌리면 대부분의 상수를 자동으로 함수 이름으로 바꿔준다. 소수의 함수(예: 프로그램 고유 헬퍼)만 이름이 안 남고, 나머지는 IDA/Ghidra 화면에 바로 주석으로 나타나 이후 분석 속도가 크게 빨라진다.

## 관련 글
- REV-0569 — Import 함수를 런타임에 해시로 찾는 API Hashing 개념
- REV-0567 — Reflective DLL Loading 개념 소개
- REV-0568 — 프로세스 할로잉(Process Hollowing) 개념 소개
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0120 — Export Table과 DLL 함수

## 출처/검증
- IDAPython API(`idautils.Entries`, `idc.set_cmt`, `idc.get_operand_value` 등)는 Hex-Rays IDA Python SDK 공식 문서 기준이다.
- Ghidra Script Manager와 스크립팅 API(`currentProgram`, `Listing`, `Instruction`)는 NSA Ghidra 공식 문서(Ghidra API Javadoc) 기준이다.
- 해시 알고리즘 재구현 시 32비트 마스킹 및 회전 방향은 실제 대상 샘플의 디스어셈블리를 직접 확인해 재현해야 하며, 이 글의 상수 값은 예시로서 실제 값과 다를 수 있다(2026-09-08 기준 서술).
