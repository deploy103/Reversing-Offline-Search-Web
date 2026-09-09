---
id: REV-1107
title: "IDAPython으로 반복 작업 자동화하기"
slug: "rev-1107-idapython-automation"
category: "tools"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Python]
keywords: ["IDAPython", "idautils", "idc", "idaapi", "IDA 스크립팅", "IDA 자동화"]
aliases: ["IDA 파이썬 스크립트", "IDAPython 사용법", "idautils.Functions"]
symptom_keywords: ["IDA에서 함수마다 같은 작업을 반복해야 함", "IDAPython이 뭔지 모름", "IDA Functions 창을 스크립트로 순회하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
IDAPython은 IDA에 내장된 파이썬 스크립팅 환경으로, `idautils`(고수준 순회: `Functions()`, `FuncItems()`, `XrefsTo()` 등)와 `idc`(개별 항목 조회/수정: `get_func_name()`, `print_insn_mnem()`, `set_cmt()` 등) 두 모듈을 조합하면 "함수 수천 개 중 특정 패턴을 가진 곳 찾기", "call 명령어마다 주석 달기" 같은 반복 작업을 몇 줄짜리 스크립트로 끝낼 수 있다.

## 언제 검색해야 하나
- 정적 링킹 바이너리(REV-0646)처럼 함수가 수천 개라서 손으로 하나씩 보기엔 너무 많을 때
- 특정 문자열을 참조하는 모든 함수, 또는 특정 API를 호출하는 모든 위치를 한 번에 나열하고 싶을 때
- 같은 패턴의 주석/이름 바꾸기 작업을 함수마다 반복하고 있어서 스크립트로 자동화하고 싶을 때
- writeup에 `idautils.Functions()`, `idc.get_func_name()` 같은 코드가 나왔는데 무슨 뜻인지 모를 때

## 핵심 개념

### IDAPython 실행 방법
IDA 메뉴의 File → Script command...(또는 단축키 `Shift+F3`을 눌러 여는 IDC/Python 콘솔창, 최신 IDA에서는 하단 Output 창 옆의 "Execute script" 아이콘)로 파이썬 코드를 즉시 실행할 수 있다. 콘솔에서 한 줄씩 실험하다가, 반복해서 쓸 로직은 `.py` 파일로 저장해 File → Script file...로 실행하는 흐름이 일반적이다.

### 세 가지 핵심 모듈
- **`idc`**: "IDC 호환 레이어"로, 전통적인 IDC 스크립트 함수들을 파이썬에서 그대로 쓸 수 있게 해준다. `get_func_name(ea)`(주소의 함수 이름 조회), `set_name(ea, name)`(이름 바꾸기), `print_insn_mnem(ea)`(해당 주소 명령어의 니모닉 문자열), `set_cmt(ea, text, 0)`(주석 달기), `get_wide_byte(ea)` 등이 대표적이다.
- **`idaapi`**: 더 저수준·레거시 호환 API를 제공하는 모듈이다. 최신 코드에서는 대부분 `idautils`/`idc`로 대체되지만, 일부 저수준 구조체 접근에는 여전히 쓰인다.
- **`idautils`**: "고수준 순회(iteration)"를 담당한다. `Functions()`(데이터베이스의 모든 함수 시작 주소를 순회), `FuncItems(ea)`(한 함수 안의 모든 명령어/데이터 항목 주소를 순회), `Segments()`(세그먼트 순회), `XrefsTo(ea)` / `XrefsFrom(ea)`(참조 관계 순회), `Names()`(이름 붙은 주소 전부) 등이 있다.

가장 흔한 조합 패턴은 "`idautils`로 큰 단위를 순회하고, 그 안에서 `idc`로 개별 값을 읽거나 바꾸는 것"이다.

### 기본 패턴 — 모든 함수 순회
```python
import idautils
import idc

for func_ea in idautils.Functions():
    name = idc.get_func_name(func_ea)
    print(f"Function: {name} at {hex(func_ea)}")
```
`idautils.Functions()`는 함수 시작 주소(effective address, `ea`)를 하나씩 내놓고, `idc.get_func_name(ea)`로 그 주소의 함수 이름을 얻는다.

### 함수 안의 명령어까지 순회 — call 명령어 자동 주석
```python
import idautils
import idc

for func_ea in idautils.Functions():
    func_name = idc.get_func_name(func_ea)

    for item_ea in idautils.FuncItems(func_ea):     # 함수 안의 모든 명령어/데이터 주소
        mnem = idc.print_insn_mnem(item_ea)         # 이 주소의 니모닉("call", "mov" 등)

        if mnem == "call":
            idc.set_cmt(item_ea, "auto-commented call", 0)   # 이 주소에 주석 추가
```
`idautils.FuncItems(func_ea)`는 한 함수 내부의 모든 항목 주소를 순서대로 내놓고, `idc.print_insn_mnem(ea)`로 그 위치의 니모닉을 문자열로 얻어 조건을 검사한다. `idc.set_cmt(ea, text, 0)`의 마지막 인자 `0`은 "일반 주석"(반복 주석이 아닌)을 의미한다.

### 자동 이름 바꾸기 — strip된 정적 바이너리에서 후보 찾기
```python
import idautils
import idc

for func_ea in idautils.Functions():
    name = idc.get_func_name(func_ea)
    if name.startswith("sub_"):
        # 예: 인자 개수/호출 패턴으로 후보를 추리고 리네이밍(SN_NOWARN: 경고 없이 이름 변경)
        idc.set_name(func_ea, "cand_" + name, idc.SN_NOWARN)
```
정적 링킹 바이너리(REV-0646)에서 시그니처 매칭(FLIRT)이 실패한 함수들을 `sub_` 접두어로 걸러내고, 별도 기준(호출 횟수, 인자 개수 등)으로 후보 이름을 임시로 붙여두면 나중에 사람이 검토하기 쉬워진다.

### 왜 스크립트로 자동화하는 게 유리한가
IDA GUI에서 함수 하나씩 클릭하며 확인하는 방식은 함수가 수십 개 수준일 때는 괜찮지만, 정적 링킹 바이너리나 대형 CTF 바이너리처럼 함수가 수천 개면 비현실적이다. IDAPython으로 "이런 패턴을 가진 함수/명령어를 전부 찾아 표시"를 코드 몇 줄로 처리하면, 사람은 그 결과 목록만 검토하면 되므로 시간이 크게 줄어든다.

## 화면/코드에서 보이는 징후
- writeup 코드 블록에 `import idautils`, `import idc`, `idaapi`가 등장
- `idc.get_func_name`, `idautils.Functions()`, `idautils.FuncItems()`, `idc.print_insn_mnem`, `idc.set_cmt`, `idc.set_name` 같은 함수 호출이 보임
- IDA 하단에 Python 콘솔(Output 창의 스크립팅 프롬프트)이 열려 있고 `>>>` 프롬프트가 보임

## 가장 먼저 할 것
IDA 콘솔(하단 Output 창 옆 스크립팅 프롬프트)을 열고 `import idautils; print(len(list(idautils.Functions())))`처럼 아주 짧은 한 줄을 먼저 실행해 함수 개수를 세어본다. 이게 동작하면 이후 반복 작업 로직을 이어서 짤 수 있다.

## 단계별 절차
1. IDA에서 분석할 바이너리를 로드하고 자동 분석이 끝날 때까지 기다린다.
2. 하단 Output 창 옆 스크립팅 콘솔에서 `import idautils, idc`를 실행해 모듈이 정상 로드되는지 확인한다.
3. `for ea in idautils.Functions(): print(idc.get_func_name(ea))`처럼 간단한 순회부터 콘솔에 직접 입력해 결과를 눈으로 확인한다.
4. 반복해서 쓸 로직이 굳어지면 `.py` 파일로 저장하고, File → Script file...로 실행한다(또는 콘솔에 `exec(open("script.py").read())`).
5. 이름/주석을 바꾸는 스크립트는 먼저 `print`로 "무엇을 바꿀지"만 출력해 검증한 뒤, 확인 후에 실제 `set_name`/`set_cmt` 호출로 바꾼다 — 실수로 잘못된 대량 리네이밍을 하면 되돌리기 번거롭다.
6. 결과를 IDB(데이터베이스 파일)에 저장(`Ctrl+W` 또는 File → Save)해 다음에 이어서 볼 수 있게 한다.

## 명령어/단축키
```python
# 특정 문자열을 참조하는 함수 목록 뽑기
import idautils
import idc

target_str_ea = 0x402000   # 대상 문자열의 주소(Strings 창에서 확인)
for xref in idautils.XrefsTo(target_str_ea):
    caller_func = idc.get_func_name(xref.frm)
    print(f"{caller_func} references string at {hex(xref.frm)}")
```
- 스크립트 콘솔 열기: 하단 Output 창(단축키 환경에 따라 `Shift+F2`가 IDC 스크립트 실행창, 최신 버전은 콘솔이 항상 하단에 있음)
- 스크립트 파일 실행: File → Script file... (`Alt+F7` 계열, 버전에 따라 다를 수 있음)

## 출력 해석
- `idautils.Functions()`가 빈 리스트를 내놓으면 자동 분석이 아직 안 끝났거나(Auto Analysis 진행 중), 함수로 인식된 코드가 하나도 없다는 뜻이다. IDA 상태 표시줄에서 분석이 끝났는지 먼저 확인한다.
- `idc.get_func_name(ea)`가 빈 문자열이나 `None`을 반환하면 그 주소가 함수 시작이 아니거나 함수로 인식되지 않은 코드 영역이라는 뜻이다.
- `idc.print_insn_mnem(ea)`가 빈 문자열이면 그 주소가 코드가 아니라 데이터로 인식되어 있다는 신호다.

## 흔한 실수
- 검증 없이 바로 `set_name`/`set_cmt`로 대량 변경부터 실행하는 것 — 먼저 `print`로 무엇이 바뀔지 확인하는 습관이 안전하다.
- `idc`와 `idaapi`의 옛날 함수 이름(예: 구버전의 `GetFunctionName`)과 최신 소문자 함수 이름(`get_func_name`)을 혼동하는 것 — IDA 버전에 따라 API 이름 표기 규칙(카멜케이스 vs 스네이크케이스)이 다르므로 사용 중인 IDA 버전의 문서를 확인해야 한다.
- 자동 분석이 끝나기 전에 스크립트를 실행해서 함수 목록이 불완전한 상태로 결과를 신뢰하는 것.
- `FuncItems`로 얻은 주소가 항상 "명령어"라고 가정하는 것 — 함수 내부에 데이터(점프 테이블 등)가 섞여 있을 수 있으므로 `idc.print_insn_mnem`이 빈 값이면 건너뛰는 방어 코드가 필요하다.

## 막혔을 때 다음 체크
- IDA 자체 설치·기본 단축키가 궁금하면 → REV-0274 IDA 설치와 오프라인 준비, REV-0275 IDA 핵심 단축키 치트시트
- 함수가 수천 개인 정적 링킹 바이너리를 다루는 전략이 궁금하면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- radare2 기반 스크립팅이 궁금하면 → REV-1108 radare2 r2pipe로 스크립팅하기
- angr로 아예 심볼릭 실행까지 자동화하고 싶다면 → REV-0271 angr 심볼릭 실행 기초

## 미니 예제
바이너리 안의 모든 `call` 명령어 개수를 함수별로 세는 스크립트:
```python
import idautils
import idc

for func_ea in idautils.Functions():
    name = idc.get_func_name(func_ea)
    call_count = 0
    for item_ea in idautils.FuncItems(func_ea):
        if idc.print_insn_mnem(item_ea) == "call":
            call_count += 1
    if call_count > 0:
        print(f"{name}: {call_count} call(s)")
```
실행하면 다음과 비슷한 출력을 볼 수 있다(함수명/개수는 바이너리마다 다름).
```text
main: 7 call(s)
check_input: 3 call(s)
sub_401500: 12 call(s)
```
`call` 개수가 유난히 많은 `sub_` 접두어 함수는 헬퍼 함수(strcmp, malloc 등 라이브러리 래퍼)가 아니라 여러 검증 단계를 호출하는 상위 로직일 가능성이 높으므로 우선순위를 높여 살펴볼 후보로 삼을 수 있다.

## 관련 글
- REV-0274 — IDA 설치와 오프라인 준비
- REV-0275 — IDA 핵심 단축키 치트시트
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-1106 — Binary Ninja 기초 소개(IDA/Ghidra 대비 언제 쓰는지)
- REV-1108 — radare2 r2pipe로 스크립팅하기
- REV-0271 — angr 심볼릭 실행 기초

## 출처/검증
- `idc`, `idaapi`, `idautils` 모듈의 역할 구분과 `idautils.Functions()`, `idc.get_func_name()` 사용 패턴: Hex-Rays 공식 IDAPython 문서(`python.docs.hex-rays.com`) 기준 (2026-09-10 확인).
- `idautils.FuncItems()`를 이용한 함수 내부 항목 순회와 `idc.print_insn_mnem`/`idc.set_cmt`/`idc.set_name` 조합 패턴: Hex-Rays 공식 IDAPython 예제 저장소(`HexRaysSA/IDAPython` examples) 및 공식 문서 기준 (2026-09-10 확인).
