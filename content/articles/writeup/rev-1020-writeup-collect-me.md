---
id: REV-1020
title: "[Write-up] Collect Me"
slug: "rev-1020-writeup-collect-me"
category: "writeup"
difficulty: "basic"
platform: [linux]
architecture: [x64]
format: [ELF]
tools: [GDB, IDA]
keywords: ["dreamhack Collect Me", "드림핵 Collect Me", "func_0 func_927", "gdb python 자동화"]
aliases: ["Collect Me 풀이", "콜렉트 미", "dreamhack collect me flag"]
symptom_keywords: ["Collect Me에서 함수가 928개라 손으로 못 봄", "func_927까지 어떻게 다 확인하나"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`func_0()`부터 `func_927()`까지 928개의 함수가 각각 char형 지역변수 하나씩을 갖고 있고, 이 값들을 순서대로 모으면 `DH{...}` 형태의 플래그 문자열이 완성되는 문제로, 사람이 손으로 928번 확인하는 대신 GDB Python 스크립팅으로 자동화하는 것이 핵심이다.

## 언제 검색해야 하나
- IDA/Ghidra Functions 창을 열었는데 `func_0`, `func_1`, ..., `func_927`처럼 이름이 규칙적으로 이어지는 함수가 수백~수천 개 보일 때
- 문제 설명에 "각 함수는 문자 하나짜리 지역 변수를 갖고 있다"는 문구가 있고 이를 순서대로 모으라고 할 때
- 함수를 하나씩 열어서 확인하는 게 명백히 비효율적이라고 느껴져 자동화 스크립트가 필요할 때

## 핵심 개념

### 문제 구조
Collect Me는 `func_0`부터 `func_927`까지 총 928개의 함수를 정의해 두고, 각 함수 내부에 char형 지역 변수를 하나씩 선언해 컴파일 시점에 정해진 문자 하나를 담아 둔다. 문제 설명 자체가 "이 문자들을 순서대로 모아 문자열로 만들고, 그 안에서 `DH{[a-z0-9]{32}}` 형태의 플래그를 찾아라"라고 명시하고 있다. 즉 실행 흐름을 분석하는 문제가 아니라, 컴파일 타임에 이미 정해진 데이터를 얼마나 효율적으로 추출하느냐를 묻는 문제다.

### 왜 실행하지 않고도 값을 읽을 수 있는가
각 지역 변수의 값은 실행 중에 계산되는 것이 아니라 함수 스택 프레임 안에 상수로 이미 박혀 있는 값이다(예: `mov byte [rbp-1], 0x41`처럼 즉시값을 스택에 그대로 써넣는 코드). 이런 경우 프로그램을 실제로 실행/브레이크시킬 필요 없이, 각 함수의 코드 바이트만 정적으로 읽어도 그 상수를 알아낼 수 있다. GDB에서는 함수를 실행하지 않고도 `gdb.parse_and_eval('func_N').address`로 함수의 시작 주소를 구하고, 그 주소에서 일정 오프셋 떨어진 위치의 메모리를 `read_memory`로 직접 읽어낼 수 있다.

### 오프셋 0xb(rbp-1)를 찾는 법
문자를 저장하는 명령이 함수 시작 지점으로부터 몇 바이트 뒤에 있는지는 함수 하나만 디스어셈블해 보면 알 수 있다. 예를 들어 `func_900` 하나를 IDA나 GDB의 `disassemble`로 열어 `mov byte ptr [rbp-1], <값>`에 해당하는 명령의 시작 주소와 함수 시작 주소의 차이를 계산하면 된다. 이 문제에서는 그 차이가 0xb(11바이트)로 확인되었고, 928개 함수가 전부 컴파일러가 동일한 패턴으로 찍어낸 코드이므로 이 오프셋이 모든 함수에 동일하게 적용된다는 점이 자동화를 가능하게 하는 전제다.

### GDB Python 스크립트로 자동 수집
GDB는 `python` 인터프리터를 내장하고 있어 `gdb.execute`, `gdb.parse_and_eval`, `gdb.selected_inferior().read_memory` 같은 API로 반복 작업을 자동화할 수 있다(REV-0656 참고). Collect Me는 0부터 927까지 반복하며 함수 이름을 문자열로 만들고, 그 함수의 주소 + 0xb 위치에서 1바이트씩 읽어 이어붙이는 루프 하나로 전체 플래그를 복원할 수 있다.

## 화면/코드에서 보이는 징후
- Functions 창에 `func_0` ~ `func_927`이 규칙적으로 나열됨
- 각 함수의 디컴파일 결과가 `char v1 = <상수>;` 한 줄 정도로 매우 단순함
- 문제 설명에 "1. 문자들을 모아서 문자열로 만들어라 2. 그 안에서 DH{...}를 찾아라" 같은 지침이 명시됨

## 가장 먼저 할 것
928개 함수를 손으로 열어보는 것은 처음부터 배제한다. `func_0` 하나만 디스어셈블해서 문자 상수가 몇 바이트째에 있는지(오프셋)를 확인하고, 그 오프셋이 다른 몇 개 함수(예: func_1, func_500, func_927)에도 동일하게 적용되는지 샘플로 검증한 뒤 전체 자동화 스크립트를 작성한다.

## 단계별 절차
1. `gdb ./collect_me`로 바이너리를 로드한다.
2. `disassemble func_0` (또는 IDA에서 func_0을 열어)로 문자 상수를 스택에 쓰는 명령의 오프셋을 확인한다.
3. 몇 개 함수를 더 샘플링해 오프셋이 항상 동일한지 확인한다.
4. GDB 안에서 `python` 명령으로 인터프리터에 들어가거나 스크립트 파일을 작성한다.
5. 0부터 927까지 반복하며 `f"func_{i}"` 문자열로 함수 심볼을 찾고, 그 주소에 오프셋을 더한 위치에서 1바이트를 읽어 바이트열에 이어붙인다.
6. 반복이 끝나면 모은 바이트열을 출력해 `DH{...}` 패턴이 나오는지 확인한다.

## 명령어/단축키
```
(gdb) disassemble func_0
(gdb) python
>>> import gdb
>>> inferior = gdb.selected_inferior()
>>> flag = b""
>>> for i in range(928):
...     addr = int(str(gdb.parse_and_eval(f"func_{i}").address).split()[0], 16)
...     flag += bytes(inferior.read_memory(addr + 0xb, 1))
...
>>> print(flag)
>>> end
```

## 출력 해석
최종적으로 이어붙인 바이트열을 문자열로 디코드하면 그 안에 `DH{...}` 형태의 문자열이 그대로 보여야 한다. 만약 중간에 이상한 문자가 섞여 있다면 오프셋(0xb)이 일부 함수에서만 다르게 적용되는 경우이므로, 그 구간의 함수 몇 개를 다시 디스어셈블해 오프셋을 재확인해야 한다.

## 흔한 실수
- 928개 함수를 하나씩 눈으로 확인하려다 시간을 낭비하는 것.
- 오프셋을 `func_0` 하나에서만 확인하고 전체에 그대로 적용했다가, 일부 함수에서 오프셋이 다르게 나올 가능성을 놓쳐 값이 깨지는 것 — 여러 지점을 샘플링해서 교차검증해야 한다.
- 함수를 실제로 호출(`call func_500`)해서 실행 흐름을 바꿔버리는 것 — 이 문제는 실행이 아니라 정적 데이터 추출이 목적이므로 실행할 필요가 없다.

## 막혔을 때 다음 체크
- GDB Python 스크립팅 문법 자체가 낯설면 REV-0656 GDB Python 스크립팅 기초(gdb.Breakpoint 등)를 먼저 본다.
- 함수 반환값이 아니라 지역 변수 값을 봐야 하는 이 문제와 달리, 반환값 확인이 필요한 경우는 REV-1019 [Write-up] Check Return Value를 참고한다.
- 928개처럼 큰 반복 작업이 실제로 자동화할 만한 규모인지 판단이 필요하면 REV-0219 Brute Force가 가능한 입력 공간 계산의 사고방식을 응용할 수 있다.

## 미니 예제
```python
flag = b""
for i in range(928):
    addr = int(str(gdb.parse_and_eval(f"func_{i}").address).split()[0], 16)
    flag += bytes(gdb.selected_inferior().read_memory(addr + 0xb, 1))
print(flag)
```
이 스크립트는 실행 중인 프로세스를 진행시키지 않고도(브레이크포인트 없이) 각 함수 코드 안에 상수로 박힌 문자 하나씩을 읽어 928바이트를 이어붙인다.

## 관련 글
- REV-0656 — GDB Python 스크립팅 기초(gdb.Breakpoint 등)
- REV-0657 — GDB에서 함수 반환값을 finish로 확인하는 법
- REV-1019 — [Write-up] Check Return Value
- REV-0219 — Brute Force가 가능한 입력 공간 계산

## 출처/검증
- 드림핵 워게임 Collect Me의 카테고리(reversing)·티어(Bronze 2)·풀이자 수(768명)와 문제 설명(928개 func_N 함수, 각 char 지역변수 하나, DH{[a-z0-9]{32}} 플래그 형식)은 dreamhack.io/wargame/challenges/672 공식 페이지 조회로 확인됨(2026-09-10).
- GDB Python 스크립트로 각 함수 주소 + 0xb 오프셋에서 1바이트씩 읽어 플래그를 복원하는 접근은 velog.io/@danmuginima 의 "Dreamhack Collect Me" 글을 참고해 새 문장으로 재구성했다. 코드는 동일한 알고리즘을 다시 작성한 것이며 원문을 그대로 옮기지 않았다.
