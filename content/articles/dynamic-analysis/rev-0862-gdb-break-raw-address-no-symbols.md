---
id: REV-0862
title: "GDB에서 브레이크포인트 주소를 심볼 없이 절대주소로 지정해야 할 때"
slug: "rev-0862-gdb-break-raw-address-no-symbols"
category: "dynamic-analysis"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords:
  - break asterisk address
  - break * 0x
  - No symbol table is loaded
  - Function not defined
  - stripped binary breakpoint
  - GDB 절대주소 브레이크포인트
symptom_keywords:
  - break 0x주소 했더니 오류남
  - 심볼이 없어서 함수이름으로 못걺
  - Function not defined 오류
  - No line 0x 오류
aliases:
  - GDB 주소로 브레이크포인트
  - break star address
  - stripped 바이너리 breakpoint
  - GDB No symbol table
source_ids: ["SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
GDB에서 함수 이름으로 브레이크포인트를 걸 수 없는 스트립된(symbol이 제거된) 바이너리나 심볼이 없는 코드 영역에서는 `break *0x401234`처럼 주소 앞에 **반드시 별표(`*`)를 붙여** 절대주소로 지정해야 하며, 별표를 빠뜨리면 GDB가 그 숫자를 소스 라인 번호로 오해해서 엉뚱한 오류를 낸다.

## 언제 검색해야 하나
- `strip`된 바이너리라 `break main`, `break check_password` 같은 함수 이름 지정이 `Function "check_password" not defined`로 실패할 때(REV-0689 참고)
- IDA/Ghidra/objdump로 확인한 정확한 주소에 브레이크포인트를 걸고 싶은데 GDB 문법을 몰라서 `break 0x401234`라고 쳤다가 이상한 오류를 만났을 때
- `No symbol table is loaded, no symbols` 같은 메시지가 뜨면서 함수 이름 기반 명령이 전부 실패할 때
- PIE 바이너리라서 베이스 주소를 더한 실제 런타임 주소를 직접 계산해서 걸어야 할 때(REV-0693, REV-0194 참고)

## 핵심 개념

### `break 0x401234`와 `break *0x401234`의 차이
GDB의 `break` 명령은 기본적으로 "linespec"(파일명:줄번호, 함수명, 또는 그냥 숫자)을 받는다. 별표 없이 그냥 숫자를 주면 GDB는 이것을 **소스 코드의 줄 번호**로 해석하려고 시도한다. 소스 정보가 없거나 그 줄 번호가 존재하지 않으면 `No line 0x401234 in the current file.` 같은 오류가 난다. 반면 별표를 붙인 `*0x401234`는 "이것은 줄 번호가 아니라 메모리 주소 표현식이다"라는 뜻으로, GDB가 심볼 정보 없이도 그 주소에 직접 브레이크포인트를 건다.

### 심볼이 없을 때 함수 이름을 쓸 수 없는 이유
`strip` 명령으로 심볼 테이블이 제거된 바이너리는 GDB가 함수 이름과 주소를 매핑할 방법이 없다. 이 상태에서 `break some_func`를 치면 `Function "some_func" not defined.`가 뜬다(REV-0689). 이런 경우 objdump, IDA, Ghidra, radare2 등 정적 분석 도구로 미리 확인해둔 **주소**를 직접 써야 하며, 이때 문법이 바로 `break *0xADDR`이다.

### PIE 바이너리에서는 베이스 주소를 더해야 한다
대상 바이너리가 PIE(Position Independent Executable)라면 정적 분석 도구가 보여주는 주소는 "파일 오프셋 기준" 또는 "베이스 0 기준"인 경우가 많다. 실행 중에는 ASLR에 의해 실제 로드 베이스가 매번 달라지므로, `*0xADDR` 형태로 절대주소를 걸려면 그 베이스 주소를 알아내 정적 오프셋에 더해야 한다(REV-0194, REV-0693 참고). 함수 이름이 살아있는 심볼이라면 차라리 `break some_func`처럼 이름으로 거는 편이 베이스 계산 실수를 피할 수 있어 더 안전하다.

## 화면/코드에서 보이는 징후
- `(gdb) break 0x401234` 입력 후 `No line 0x401234 in the current file.` 오류가 뜬다.
- `(gdb) break check_password` 입력 후 `Function "check_password" not defined.` 오류가 뜬다(스트립된 바이너리, REV-0689).
- `(gdb) info functions` 실행 시 결과가 텅 비어 있거나, 시스템 라이브러리 함수 몇 개만 보인다.

## 가장 먼저 할 것
1. 대상이 스트립되어 있는지 확인한다: `file target` 결과에 `not stripped` 대신 `stripped`가 보이면 심볼이 없는 것이다(REV-0095 참고).
2. 심볼이 없다면 objdump/IDA/Ghidra로 목표 주소를 먼저 확정한다.
3. 그 주소 앞에 별표(`*`)를 붙여 `break *0xADDR` 형태로 건다.

## 단계별 절차
1. 정적 분석 도구로 목표 명령어의 주소를 확인한다. objdump 예시:
   ```
   objdump -d target | grep -A2 "위치 근처 명령어"
   ```
2. PIE 바이너리라면 실행 중 실제 베이스 주소를 먼저 확인한다.
   ```
   (gdb) start
   (gdb) info proc mappings
   ```
   (Pwndbg라면 `vmmap` 한 줄로 더 보기 좋게 확인 가능)
3. 정적 오프셋에 베이스 주소를 더해 실제 런타임 주소를 계산한다.
4. 별표를 붙여 브레이크포인트를 건다.
   ```
   (gdb) break *0x555555555234
   ```
5. `run` 또는 `continue`로 실행해 해당 주소에서 멈추는지 확인한다.
6. 반복 실행마다 베이스가 바뀌는 것이 번거롭다면, PIE 오프셋을 자동으로 계산해주는 방법(REV-0194의 `break *(0x1234 + (($_base = (unsigned long)&_start) - 0x1000))` 류의 트릭이나 Pwndbg의 심볼 지원)을 활용한다.

## 명령어/단축키
- `break *0xADDR` — 주소에 소프트웨어 브레이크포인트(별표 필수)
- `break *ADDR_EXPR` — 표현식도 가능(예: `break *($rip+0x10)`)
- `info proc mappings` — 현재 프로세스의 메모리 맵(베이스 주소 확인)
- `info breakpoints` — 현재 걸린 브레이크포인트 목록과 실제 해석된 주소 확인
- `file target` — 스트립 여부 확인

## 출력 해석
- `Breakpoint 1 at 0x401234`처럼 뜨면 정상적으로 그 주소에 브레이크포인트가 걸린 것이다.
- `info breakpoints` 결과에 `<PENDING>`이 보이면 해당 주소/심볼이 아직 유효하지 않다는 뜻이며, 대개 모듈이 아직 로드되지 않았거나 주소 계산이 틀렸을 때 나타난다.
- `No line 0x401234 in the current file.`은 별표를 빠뜨렸다는 신호이지, 주소 자체가 잘못됐다는 뜻이 아니다.

## 흔한 실수
- 별표를 빠뜨리고 `break 0x401234`라고만 써서 "줄 번호로 브레이크포인트를 걸 수 없다"는 오류를 주소 자체 문제로 오해하는 것.
- PIE 바이너리에서 IDA가 보여주는 오프셋을 베이스 주소 없이 그대로 `break *0xADDR`에 넣어서 엉뚱한 위치(혹은 매핑되지 않은 메모리)에 걸리는 것 — 결과적으로 브레이크포인트가 절대 히트되지 않는다.
- 스트립된 바이너리인 줄 모르고 함수 이름으로 계속 시도하며 시간을 낭비하는 것 — `file` 명령으로 미리 확인하는 습관이 필요하다.

## 막혔을 때 다음 체크
- 주소를 정확히 걸었는데도 안 멈춘다면 → PIE 베이스 계산이 맞는지 다시 확인한다(REV-0693 참고).
- 함수 이름 자체는 살아있는데도 안 걸린다면 → 동적 링킹된 함수라 아직 심볼이 해석 안 된 경우일 수 있다(REV-0696 참고).
- 여전히 `Cannot access memory at address` 오류가 뜬다면 → REV-0687을 참고해 메모리 접근 오류 원인을 좁힌다.

## 미니 예제
```
$ file target
target: ELF 64-bit LSB pie executable, x86-64, ..., stripped

(gdb) start
Temporary breakpoint 1, 0x0000555555555139 in _start ()
(gdb) info proc mappings
...
0x555555555000  0x555555556000  0x1000  0x0  r-xp   /path/target
(gdb) break *0x555555555234
Breakpoint 2 at 0x555555555234
(gdb) continue
```
정적 분석에서 확인한 오프셋 `0x1234`에 베이스 `0x555555555000`을 더해 `0x555555555234`를 계산하고, 별표를 붙여 절대주소 브레이크포인트로 걸어서 스트립된 바이너리에서도 원하는 지점에 정확히 멈출 수 있다.

## 관련 글
- REV-0689 — GDB에서 breakpoint를 걸었는데 Function not defined라고 할 때
- REV-0693 — PIE 바이너리에서 GDB 브레이크포인트 주소가 계속 안 맞을 때
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기
- REV-0696 — 동적 링킹된 함수에 브레이크포인트가 심볼 없이는 안 걸릴 때
- REV-0186 — GDB break와 address breakpoint

## 출처/검증
- `break` 명령의 linespec 문법과 `*address` 표기: GNU GDB 공식 매뉴얼 "Setting Breakpoints" 섹션 기준.
- 스트립된 바이너리에서 심볼 조회 실패 동작: GNU GDB 공식 매뉴얼 및 binutils `strip` 문서 기준.
- 2026-09-09 검증.
