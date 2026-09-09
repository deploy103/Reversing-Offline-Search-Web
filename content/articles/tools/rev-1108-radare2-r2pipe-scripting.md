---
id: REV-1108
title: "radare2 r2pipe로 스크립팅하기"
slug: "rev-1108-radare2-r2pipe-scripting"
category: "tools"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [radare2, Python]
keywords: ["r2pipe", "radare2 스크립팅", "radare2 파이썬", "cmdj", "aflj"]
aliases: ["r2pipe 사용법", "radare2 자동화", "r2 파이썬 바인딩"]
symptom_keywords: ["radare2 명령어를 파이썬에서 자동으로 실행하고 싶음", "r2pipe가 뭔지 모름", "radare2 결과를 JSON으로 받고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`r2pipe`는 radare2 콘솔 명령어를 파이썬(또는 다른 언어)에서 파이프로 실행하고 결과를 문자열 또는 JSON 객체로 돌려받게 해주는 공식 바인딩으로, `r2 = r2pipe.open("파일")` → `r2.cmd("aaa")`(분석) → `r2.cmdj("aflj")`(함수 목록을 JSON으로) 세 줄이면 radare2로 하던 반복 분석 작업을 파이썬 스크립트로 자동화할 수 있다.

## 언제 검색해야 하나
- radare2/Cutter로 분석하다가 같은 명령어(`afl`, `pdf`, `axt` 등)를 여러 바이너리에 반복 실행해야 할 때
- writeup 코드에 `import r2pipe`가 나왔는데 사용법을 모를 때
- radare2 명령어 출력(텍스트)을 파싱하기보다 구조화된 JSON으로 바로 받고 싶을 때
- CTF에서 여러 개의 유사한 바이너리(예: 같은 문제의 변형들)를 배치로 분석해야 할 때

## 핵심 개념

### r2pipe란 무엇인가
radare2는 원래 대화형 콘솔(`r2 ./chall` 실행 후 `>` 프롬프트에 명령어 입력)로 쓰지만, 그 콘솔 명령어 체계를 그대로 외부 스크립트에서 실행할 수 있게 해주는 것이 `r2pipe`다. 핵심 아이디어는 "문자열로 된 r2 명령어를 받아 문자열(또는 JSON)로 결과를 돌려주는 함수 하나"이며, 파이프(pipe)로 프로세스 간 통신을 하기 때문에 이름이 r2pipe다. Python, JavaScript, Go 등 여러 언어 바인딩이 있고, pipe(로컬 프로세스 spawn) 외에도 http/tcp/rap 등 원격 연결 방식도 지원한다.

### 기본 흐름 — open, cmd, cmdj, quit
```python
import r2pipe

r2 = r2pipe.open("/bin/ls")   # 바이너리를 열어 세션 시작
r2.cmd('aa')                   # 기본 분석 실행(analyze all)
print(r2.cmd("afl"))           # 함수 목록을 텍스트로 출력
print(r2.cmdj("aflj"))         # 같은 함수 목록을 JSON(파이썬 객체)으로 받기
print(r2.cmdj("ij").core.format)  # 파일 포맷 정보 중 일부 필드 접근
r2.quit()                      # 세션 종료
```
- `r2pipe.open(path)`: 지정한 바이너리로 radare2 세션을 새로 연다.
- `r2.cmd(command)`: radare2 콘솔에 명령어를 입력한 것과 동일하게 실행하고, 결과를 **문자열**로 돌려준다.
- `r2.cmdj(command)`: 명령어 뒤에 `j`가 붙는 JSON 출력 명령(`aflj`, `pdj`, `ij` 등)의 결과를 파싱해서 **파이썬 객체(dict/list)**로 돌려준다. 텍스트를 직접 파싱하는 것보다 훨씬 안전하고 편하다.
- `r2.quit()`: 세션을 종료해 자원을 정리한다.

### 자주 쓰는 명령어와 JSON 변형
- `aa` / `aaa`: 기본 분석 / 더 철저한 분석(느리지만 함수·xref 인식률이 높아짐)
- `afl` (텍스트) / `aflj` (JSON): 함수 목록
- `pdf @ 주소` (텍스트) / `pdfj @ 주소` (JSON): 특정 함수의 디스어셈블리
- `axt 주소` (텍스트) / `axtj 주소` (JSON): 특정 주소를 참조하는 곳(xref to) 목록
- `izz` / `izzj`: 바이너리 전체에서 문자열 검색(텍스트/JSON)
- `ij` / `ijj`: 파일 정보(포맷, 아키텍처, 비트수 등)

명령어 뒤에 `j`를 붙이면 JSON이 나온다는 규칙이 거의 일관되게 적용되므로, "이 명령어의 JSON 버전이 있을까?"는 먼저 `<명령어>j`를 시도해보면 된다.

### 왜 파이썬 스크립트로 자동화하는가
radare2 콘솔에서 매번 손으로 `afl`, `pdf @ main`을 치는 대신, r2pipe로 "모든 함수를 순회하며 이름에 특정 패턴이 있는 함수만 디스어셈블 출력" 같은 반복 작업을 한 번에 처리할 수 있다. 특히 CTF에서 같은 유형의 바이너리가 여러 개 있을 때(같은 체크섬 알고리즘이 문제마다 상수만 다르게 반복되는 경우 등), 스크립트 하나로 모든 파일을 순회하며 필요한 정보만 뽑아내면 시간을 크게 아낄 수 있다.

## 화면/코드에서 보이는 징후
- writeup/스크립트에 `import r2pipe`, `r2pipe.open(...)`, `.cmd(...)`, `.cmdj(...)` 호출이 보임
- 출력 결과가 파이썬 `dict`/`list`처럼 중괄호·대괄호로 구조화되어 있음(JSON 명령어 사용 시)
- pip로 설치된 패키지 목록에 `r2pipe`가 있음(`pip show r2pipe` 등으로 확인 가능)

## 가장 먼저 할 것
`pip install r2pipe`(오프라인 환경이면 REV-0300 오프라인 파이썬 패키지 준비 참고)로 설치되어 있는지 확인한 뒤, 분석할 바이너리 하나로 `r2 = r2pipe.open("파일"); r2.cmd("aa"); print(r2.cmd("afl"))` 세 줄만 콘솔에서 실행해 함수 목록이 정상적으로 나오는지 먼저 확인한다.

## 단계별 절차
1. radare2 본체가 설치되어 있는지 확인한다(`r2pipe`는 radare2 실행 파일을 내부적으로 호출하므로 radare2 자체가 시스템에 있어야 한다).
2. `pip install r2pipe`로 파이썬 바인딩을 설치한다.
3. 분석할 바이너리 경로로 `r2pipe.open(path)`를 호출해 세션을 연다.
4. `r2.cmd("aaa")`로 철저한 자동 분석을 먼저 실행한다(속도가 느리면 `aa`로 낮춰도 됨).
5. `r2.cmdj("aflj")`로 함수 목록을 JSON으로 받아 파이썬 반복문으로 순회한다.
6. 필요한 함수마다 `r2.cmdj(f"pdfj @ {addr}")`처럼 주소를 지정해 디스어셈블리를 JSON으로 받아 세부 분석을 이어간다.
7. 작업이 끝나면 `r2.quit()`으로 세션을 정리한다.

## 명령어/단축키
```python
import r2pipe

r2 = r2pipe.open("./chall")
r2.cmd("aaa")                       # 철저한 자동 분석

funcs = r2.cmdj("aflj")             # 함수 목록을 JSON으로
for f in funcs:
    print(f["name"], hex(f["offset"]), f["size"])

# 이름에 "check"가 들어간 함수만 디스어셈블리 출력
for f in funcs:
    if "check" in f["name"]:
        print(r2.cmd(f"pdf @ {f['offset']}"))

r2.quit()
```
콘솔에서 직접 실행할 때 자주 쓰는 radare2 명령어: `aaa`(분석), `afl`(함수 목록), `pdf @ main`(main 디스어셈블), `s main`(main으로 seek), `iz`(현재 섹션 문자열), `izz`(전체 문자열).

## 출력 해석
- `cmdj`가 `None`을 반환하면 해당 명령어가 JSON을 지원하지 않거나(오타 등), radare2가 그 시점에 유효한 JSON을 만들지 못했다는 뜻이다 — 먼저 `cmd`(텍스트 버전)로 같은 명령을 실행해 원본 출력이 정상인지 확인한다.
- `aflj`로 받은 각 함수 항목은 보통 `name`, `offset`, `size`, `nbbs`(기본 블록 수) 같은 키를 가진 dict다. 실제 키 구성은 radare2 버전에 따라 달라질 수 있으므로 `print(funcs[0])`로 한 번 구조를 확인하는 습관이 안전하다.
- `aa`만 실행했는데 함수 인식이 너무 적으면 `aaa`(더 철저한 분석, 느림)로 바꿔본다.

## 흔한 실수
- radare2 본체를 설치하지 않고 `pip install r2pipe`만 해서 "명령을 찾을 수 없다"는 오류를 만나는 것 — r2pipe는 radare2를 호출하는 바인딩일 뿐, radare2 자체를 대체하지 않는다.
- JSON 명령어(`aflj` 등)의 결과를 텍스트처럼 문자열 파싱하려는 것 — `cmdj`는 이미 파이썬 객체를 반환하므로 그대로 인덱싱/순회하면 된다.
- `r2.quit()`을 호출하지 않고 스크립트를 반복 실행해 프로세스가 쌓이는 것.
- 분석(`aa`/`aaa`)을 실행하지 않은 상태에서 바로 `afl`을 호출해 함수 목록이 비어 있다고 착각하는 것 — 분석 명령을 먼저 실행해야 함수가 인식된다.

## 막혔을 때 다음 체크
- radare2 콘솔 명령어 자체가 익숙하지 않다면 → REV-0291 radare2 설치와 첫 명령, REV-0292 radare2 명령어 치트시트
- GUI로 먼저 익히고 싶다면 → REV-0293 Cutter 설치와 기본 사용법(Cutter는 radare2를 GUI로 감싼 도구)
- 오프라인 환경에서 pip 패키지 설치가 막혀 있다면 → REV-0300 Z3 angr pwntools Python 오프라인 패키지 준비
- IDA 환경에서 비슷한 자동화를 하고 싶다면 → REV-1107 IDAPython으로 반복 작업 자동화하기

## 미니 예제
바이너리에서 `flag`라는 단어가 들어간 문자열을 자동으로 찾아 참조하는 함수까지 나열하는 스크립트:
```python
import r2pipe

r2 = r2pipe.open("./chall")
r2.cmd("aaa")

strings = r2.cmdj("izzj")           # 바이너리 전체 문자열을 JSON으로
for s in strings:
    if "flag" in s.get("string", "").lower():
        addr = s["vaddr"]
        print(f'"{s["string"]}" @ {hex(addr)}')
        xrefs = r2.cmdj(f"axtj {addr}")   # 이 문자열을 참조하는 곳
        for x in xrefs:
            print("  referenced by", hex(x["from"]))

r2.quit()
```
실행하면 다음과 비슷하게 나온다(실제 문자열/주소는 바이너리마다 다름).
```text
"flag_value" @ 0x402008
  referenced by 0x401a20
```
이렇게 나온 `0x401a20`이 문자열을 참조하는 함수이므로, 이어서 `r2.cmd("pdf @ 0x401a20")`로 그 함수의 디스어셈블리를 받아 검증 로직을 분석하면 된다.

## 관련 글
- REV-0291 — radare2 설치와 첫 명령
- REV-0292 — radare2 명령어 치트시트
- REV-0293 — Cutter 설치와 기본 사용법
- REV-0300 — Z3 angr pwntools Python 오프라인 패키지 준비
- REV-1107 — IDAPython으로 반복 작업 자동화하기
- REV-1106 — Binary Ninja 기초 소개(IDA/Ghidra 대비 언제 쓰는지)

## 출처/검증
- `r2pipe.open`, `cmd`, `cmdj`, `quit` 기본 사용 패턴과 `aa`/`afl`/`aflj`/`ij` 명령어 조합: radare2 공식 문서(`book.rada.re`) r2pipe 소개 페이지 및 `radareorg/radare2-r2pipe` 공식 저장소의 Python README 기준 (2026-09-10 확인).
- 명령어 뒤 `j` 접미사가 JSON 출력을 의미하는 규칙과 `axtj`/`izzj`/`pdfj` 등 파생 명령어: radare2 공식 명령어 체계 기준 (2026-09-10 확인).
