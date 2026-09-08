---
id: REV-0193
title: "Pwndbg context telescope vmmap"
slug: "rev-0193-pwndbg-context-telescope-vmmap"
category: "dynamic-analysis"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pwndbg context", "pwndbg telescope", "pwndbg vmmap", "pwndbg hexdump", "pwndbg search", "pwndbg 명령어"]
aliases: ["pwndbg context 명령어", "pwndbg telescope 사용법", "pwndbg vmmap 보는법", "pwndbg 메모리 검색", "pwndbg hexdump 사용법"]
symptom_keywords: ["pwndbg context가 뭔지 모름", "pwndbg telescope 결과 해석법", "pwndbg vmmap 권한 표시 뜻", "pwndbg에서 특정 문자열 찾고싶음", "pwndbg 포인터 체인 보는법"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg의 `context`는 레지스터/디스어셈블리/스택/백트레이스를 한 화면에 자동으로 보여주는 대시보드이고, `telescope`는 포인터를 재귀적으로 따라가며 메모리를 보여주며, `vmmap`은 프로세스의 메모리 매핑을 권한(r/w/x)과 함께 색깔로 보여주고, `hexdump`와 `search`는 각각 raw 바이트를 보기 좋게 덤프하거나 메모리 전체에서 특정 값을 찾아준다.

## 언제 검색해야 하나
- Pwndbg가 멈출 때마다 자동으로 보여주는 그 화면(레지스터/코드/스택 박스)이 정확히 뭘 의미하는지 궁금할 때
- 스택이나 레지스터에 있는 값이 포인터인지 아닌지, 포인터라면 그 끝에 뭐가 있는지 한 번에 확인하고 싶을 때
- 지금 이 주소가 스택인지 힙인지 라이브러리인지, 실행 가능한 영역인지 빠르게 판단하고 싶을 때
- 메모리 전체에서 특정 문자열이나 값(예: `"flag"`, `0xdeadbeef`)이 어디 있는지 찾고 싶을 때
- `x/`로 여러 번 나눠서 보던 바이트 덤프를 더 깔끔하게 한 번에 보고 싶을 때

## 핵심 개념

### `context` — 모든 걸 한 화면에
Pwndbg가 로드된 상태에서 `start`, `stepi`, `continue` 등으로 프로그램이 멈출 때마다 **자동으로** `context` 화면이 출력된다. 수동으로도 아무 때나 `context` 명령을 쳐서 다시 볼 수 있다. 이 화면은 보통 다음 섹션들로 구성된다.
- `REGISTERS`: 현재 레지스터 값. 직전 값과 달라진 레지스터는 색이 강조되어 한눈에 "방금 뭐가 바뀌었는지" 알 수 있다.
- `DISASM`: 현재 `$rip` 주변 명령어 목록. `►` 표시가 지금 실행할 명령어.
- `STACK`: 스택 맨 위 몇 줄. 각 줄이 `telescope`처럼 포인터를 자동으로 따라가서 보여준다.
- `BACKTRACE`: 현재 호출 스택 요약.

원하는 섹션만 골라서 볼 수도 있다.
```
context regs
context disasm
context stack
context backtrace
```
섹션 구성과 줄 수는 `.gdbinit`이나 Pwndbg 설정(`set context-code-lines` 등)으로 조절할 수 있다.

### `telescope` — 포인터 체인을 자동으로 따라가기
`telescope`(줄여서 자동완성으로 `tele`도 인식되는 버전이 많다)는 지정한 주소부터 연속된 메모리 값을 한 줄씩 보여주는데, 각 값이 **유효한 메모리 주소처럼 보이면 그 주소가 가리키는 곳까지 자동으로 역참조해서 함께 보여준다**. 이게 순정 GDB의 `x/8xg`보다 압도적으로 편한 이유다 — 포인터의 포인터, 심지어 그 끝에 있는 문자열까지 한 줄에 다 보여준다.
```
pwndbg> telescope $rsp
00:0000│ rsp 0x7fffffffe4a0 —▸ 0x7fffffffe4c0 ◂— 'test123'
01:0008│     0x7fffffffe4a8 ◂— 0x68732f6e69622f
02:0010│     0x7fffffffe4b0 —▸ 0x555555555169 (check_password) ◂— push rbp
...
```
`—▸`는 "이 값이 저 주소를 가리킨다"는 화살표이고, `◂—`는 "그 주소의 실제 내용"이다. 개수를 지정하려면:
```
pwndbg> telescope $rsp 20
```

### `vmmap` — 메모리 지도를 색깔로
`vmmap`은 순정 GDB의 `info proc mappings`와 같은 정보(메모리 영역별 시작/끝 주소, 권한, 매핑된 파일)를 보여주되, **권한별로 색을 다르게 칠해서** 실행 가능한 영역(`r-x`, 코드), 쓰기 가능한 영역(`rw-`, 스택/힙/데이터), 읽기 전용 영역을 한눈에 구분할 수 있게 해준다. 인자 없이 쓰면 전체 매핑을, 특정 주소나 패턴을 주면 그 부분만 필터링해서 보여준다.
```
pwndbg> vmmap
pwndbg> vmmap libc
pwndbg> vmmap $rsp
```
PIE 바이너리의 런타임 베이스 주소를 확인할 때도 `vmmap`을 쓴다 — 결과 맨 위쪽, 실행 파일 자신의 경로가 적힌 첫 줄의 시작 주소가 바로 그 실행에서의 로드 베이스다(REV-0194에서 이 용도를 자세히 다룬다).

### `hexdump` — 보기 좋은 바이트+ASCII 덤프
`hexdump`는 지정한 주소부터 지정한 길이만큼을, 한 줄에 16바이트씩 16진수와 ASCII를 나란히 보여주는 전통적인 hex editor 스타일 출력이다.
```
pwndbg> hexdump $rsp 64
+0000 0x7fffffffe4a0  74 65 73 74 31 32 33 00  00 00 00 00 00 00 00 00  │test123·│········│
```
`x/xb`를 여러 줄 나눠서 보는 것보다 한 번에 훨씬 많은 정보를, ASCII 해석까지 곁들여서 볼 수 있어 버퍼 내용을 통째로 확인할 때 유용하다.

### `search` — 메모리 전체에서 값 찾기
`search`는 프로세스의 매핑된 메모리 전체(또는 특정 영역)를 뒤져서 지정한 패턴이 있는 모든 주소를 찾아준다.
```
pwndbg> search "flag"
pwndbg> search -t string "secret_key"
pwndbg> search -t dword 0xdeadbeef
pwndbg> search -t qword 0x1234567890abcdef
```
`-t` 옵션으로 타입(문자열, 4바이트 정수, 8바이트 정수 등)을 지정할 수 있다. CTF에서 힙이나 스택 어딘가에 남아있는 플래그 문자열, 혹은 특정 매직 넘버가 어느 주소에 있는지 찾을 때 아주 강력하다. 검색 범위를 특정 매핑으로 좁히고 싶으면 `-m` 옵션(버전에 따라 문법이 조금씩 다르므로 `search --help`로 확인)을 함께 쓴다.

### 이 네 가지 명령의 조합이 실전 워크플로다
전형적인 흐름은 다음과 같다: `vmmap`으로 지금 이 프로세스의 메모리 구조(코드/힙/스택/라이브러리 위치)를 먼저 파악 → `context`로 지금 멈춘 지점의 레지스터/코드/스택을 확인 → 스택이나 레지스터에 보이는 의심스러운 포인터를 `telescope`로 끝까지 따라가서 실제 값 확인 → 필요하면 `hexdump`로 버퍼 원본을 통째로 보거나 `search`로 특정 값이 메모리 어디에 더 있는지 찾는다.

## 화면/코드에서 보이는 징후
- 브레이크포인트에 멈출 때마다 색깔 박스로 `REGISTERS`/`DISASM`/`STACK`/`BACKTRACE` 섹션이 자동으로 쭉 출력됨
- `telescope` 결과에서 `—▸` 화살표가 여러 번 이어지며 포인터 체인을 보여줌
- `vmmap` 결과에서 실행 파일 경로 옆에 초록/빨강 등으로 권한이 색칠되어 나옴(터미널 색상 지원 시)
- `search` 결과가 여러 줄의 주소 목록으로 출력됨

## 가장 먼저 할 것
프로세스가 멈춘 직후에는 일단 자동으로 뜬 `context` 화면부터 훑어본다. 특정 스택 값이나 레지스터가 가리키는 곳이 궁금하면 바로 `telescope 주소`를 쳐본다.

## 단계별 절차

**1) 프로세스를 멈춘 상태에서 기본 context 확인**
```
pwndbg> context
```

**2) 스택/레지스터의 포인터 값 추적**
```
pwndbg> telescope $rsp 16
pwndbg> telescope $rax
```

**3) 전체 메모리 구조 확인**
```
pwndbg> vmmap
```

**4) 특정 버퍼를 통째로 확인**
```
pwndbg> hexdump &buf 128
```

**5) 특정 값이 메모리 어디에 있는지 검색**
```
pwndbg> search "flag{"
pwndbg> search -t qword 0xcafebabe
```

## 명령어/단축키
```
context
context regs
context disasm
context stack
context backtrace
telescope ADDR
telescope ADDR COUNT
vmmap
vmmap PATTERN
hexdump ADDR
hexdump ADDR LEN
search "STRING"
search -t TYPE VALUE
```

## 출력 해석
- `telescope` 줄 앞의 `00:0000│`, `01:0008│`는 각각 시작 주소로부터의 순번과 바이트 오프셋이다. `rsp` 같은 레지스터 이름이 붙은 줄은 그 레지스터가 정확히 그 주소를 가리키고 있다는 뜻이다.
- `vmmap` 결과의 각 줄은 보통 `시작주소 끝주소 권한 오프셋 경로` 순서이며, 권한 문자열이 `r-xp`면 읽기+실행(코드), `rw-p`면 읽기+쓰기(데이터/스택/힙), `r--p`면 읽기 전용이다.
- `search` 결과는 매칭된 모든 주소를 나열하며, 같은 값이 여러 곳에 있으면 그만큼 여러 줄이 나온다 — 그 중 실제로 의미 있는 위치는 `vmmap`으로 어느 영역인지 대조해서 판단해야 한다.

## 흔한 실수
- `telescope`가 보여주는 문자열이나 값을 절대 주소로 착각하고 그대로 다음 실행에도 재사용하는 것 — ASLR/PIE 환경에서는 실행마다 바뀔 수 있다(REV-0194 참고).
- `vmmap` 결과에서 라이브러리 경로가 여러 줄로 나뉘어 나오는 걸 보고 "여러 라이브러리가 로드됐다"고 착각하는 것 — 같은 라이브러리라도 코드 영역(`r-x`), 읽기 전용 데이터(`r--`), 쓰기 가능한 데이터(`rw-`)가 각각 별도의 매핑 줄로 나뉘어 나오는 것이 정상이다.
- `search`로 문자열을 찾을 때 대소문자나 인코딩(UTF-8, 널 종료 여부)을 신경 안 써서 결과가 하나도 안 나오는 것.
- `context`가 너무 길게 나와서 스크롤 버퍼를 넘어가면, 터미널 자체의 스크롤백 한도를 늘리거나 `context stack`처럼 필요한 섹션만 골라 보는 습관이 필요하다는 걸 모르는 것.

## 막혔을 때 다음 체크
- Pwndbg 설치 자체가 안 됐다면 → REV-0192 Pwndbg 설치와 실행
- 순정 GDB의 `x/` 명령과 비교하며 이해하고 싶다면 → REV-0189 GDB x 명령으로 메모리 보기
- PIE 바이너리에서 `vmmap`으로 런타임 베이스를 구해 브레이크포인트를 거는 법 → REV-0194 PIE 바이너리 GDB 브레이크포인트 잡기

## 미니 예제
```
pwndbg> vmmap
LEGEND: STACK | HEAP | CODE | DATA | RODATA | RWX | ...
             0x555555554000     0x555555555000 r--p     1000 0      /home/user/chall
             0x555555555000     0x555555556000 r-xp     1000 1000   /home/user/chall
             0x7ffff7dc0000     0x7ffff7de5000 r--p    25000 0      /usr/lib/x86_64-linux-gnu/libc.so.6
             0x7ffffffde000     0x7ffffffff000 rw-p    21000 0      [stack]
pwndbg> telescope $rsp 3
00:0000│ rsp 0x7fffffffe4a0 —▸ 0x7fffffffe4c0 ◂— 'test123'
01:0008│     0x7fffffffe4a8 ◂— 0x0
02:0010│     0x7fffffffe4b0 —▸ 0x555555555169 (main) ◂— push rbp
```

## 관련 글
- REV-0192 — Pwndbg 설치와 실행
- REV-0189 — GDB x 명령으로 메모리 보기
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기

## 출처/검증
- `context`, `telescope`, `vmmap`, `hexdump`, `search` 명령의 기능과 출력 형식: Pwndbg 공식 문서(pwndbg.re) 및 공식 저장소 명령어 레퍼런스 기준.
- `vmmap` 색상 범례(LEGEND: STACK/HEAP/CODE/DATA)와 필터 인자 지원: Pwndbg 공식 문서 "Commands" 섹션 기준 (2026-09-08 검증).
