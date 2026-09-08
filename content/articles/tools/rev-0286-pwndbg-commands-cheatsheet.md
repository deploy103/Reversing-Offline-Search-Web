---
id: REV-0286
title: "Pwndbg 명령어 치트시트"
slug: "rev-0286-pwndbg-commands-cheatsheet"
category: "tools"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pwndbg 명령어", "pwndbg cheatsheet", "pwndbg context", "pwndbg telescope", "pwndbg vmmap", "pwndbg search", "pwndbg hexdump", "pwndbg heap"]
aliases: ["pwndbg 치트시트", "pwndbg 명령 정리", "pwndbg 자주쓰는 명령"]
symptom_keywords: ["pwndbg context가 뭔지 모름", "pwndbg telescope 사용법", "pwndbg vmmap 사용법", "pwndbg에서 메모리 검색하는법", "pwndbg heap 명령어"]
source_ids: ["SRC-PWNDBG-DOCS", "SRC-GDB-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg를 설치했다면 순정 GDB 명령 위에 `context`(자동 상황판), `telescope`(스택/메모리 역참조 추적), `vmmap`(메모리 맵), `hexdump`(헥스 덤프), `search`(패턴 검색) 다섯 개만 익혀도 CTF 실전에서 필요한 관찰의 80%를 해결할 수 있다.

## 언제 검색해야 하나
- Pwndbg를 설치했는데 `context`, `telescope` 같은 명령이 정확히 뭘 보여주는지 몰라서 안 쓰고 있을 때
- 스택에 쌓인 포인터가 결국 어떤 문자열/구조체를 가리키는지 손으로 하나씩 `x/`로 추적하기 귀찮을 때
- 메모리 어느 영역이 실행 가능(executable)한지, 어디가 스택/힙/라이브러리인지 한눈에 보고 싶을 때
- 메모리 전체에서 특정 문자열이나 바이트 패턴, 또는 특정 값이 어디에 있는지 찾고 싶을 때
- 힙(heap) 문제를 풀 때 청크 구조를 손으로 계산하지 않고 명령으로 보고 싶을 때

## 핵심 개념
Pwndbg 명령은 크게 **(1) 자동 상황판(context)**, **(2) 메모리 추적(telescope)**, **(3) 메모리 지도(vmmap)**, **(4) 원시 데이터 보기(hexdump)**, **(5) 검색(search)**, **(6) 힙 분석**으로 나뉜다. 순정 GDB의 `x/`, `info registers` 등을 대체하는 것이 아니라 훨씬 읽기 편한 형태로 감싸주는 것이라고 이해하면 된다.

## 가장 먼저 할 것
브레이크포인트에 멈추면 아무 명령 없이도 `context`가 자동으로 화면을 채워준다 — 먼저 그 화면부터 읽고, 더 자세히 봐야 할 부분만 아래 표의 개별 명령으로 파고든다.

## 단계별 절차
1. `gdb ./chall` 실행 후 `break main`, `run`.
2. 멈추면 자동 출력되는 `context`(레지스터/디스어셈블/스택/backtrace)를 먼저 읽는다.
3. 특정 포인터가 뭘 가리키는지 궁금하면 `telescope <addr>`.
4. 메모리 보호기법/섹션 배치가 궁금하면 `vmmap`.

## 명령어/단축키

### 1) `context` — 자동 상황판
| 명령 | 설명 |
|---|---|
| `context` | REGISTERS/DISASM/STACK/BACKTRACE를 한 화면에 정리해서 출력 |
| `context regs` | 레지스터 구획만 출력 |
| `context disasm` | 디스어셈블리 구획만 출력 |
| `context stack` | 스택 구획만 출력 |

설치 후에는 `break`가 걸리거나 `stepi`/`nexti`로 한 줄 진행할 때마다 **자동으로** `context`가 다시 출력된다. 즉 따로 호출할 필요 없이 항상 최신 상태를 보게 된다. 값이 바뀐 레지스터는 다른 색으로 강조돼서 "방금 뭐가 바뀌었는지"가 바로 보인다.

### 2) `telescope` — 메모리를 따라가며 역참조
| 명령 | 설명 |
|---|---|
| `telescope $rsp` | 스택 포인터부터 시작해서 각 8바이트가 가리키는 값을 연쇄적으로 추적 출력 |
| `telescope $rsp 20` | 20줄까지 출력 |
| `telescope 0x404040` | 임의 주소부터 역참조 추적 |

순정 GDB의 `x/10gx $rsp`는 그냥 8바이트 값만 나열하지만, `telescope`는 그 값이 다시 유효한 포인터면 "그 포인터가 가리키는 곳"까지 따라가서 문자열이면 문자열로, 코드 주소면 함수명으로 보여준다. 스택에 남은 포인터가 어떤 데이터를 가리키는지 파악할 때 압도적으로 빠르다.

### 3) `vmmap` — 프로세스 메모리 지도
| 명령 | 설명 |
|---|---|
| `vmmap` | 현재 프로세스의 전체 메모리 매핑(주소 범위, 권한, 파일명) 출력 |
| `vmmap chall` | 이름에 `chall`이 포함된 매핑만 필터링 |
| `vmmap $rsp` | 특정 주소가 속한 매핑만 출력 |

각 줄에 `r-xp`(읽기+실행), `rw-p`(읽기+쓰기) 같은 권한이 함께 나오므로, "이 주소가 실행 가능한 코드 영역인지, 아니면 쓰기만 되는 데이터 영역인지"를 셸코드 주입/ROP 문제에서 바로 확인할 수 있다.

### 4) `hexdump` — 원시 바이트 보기
| 명령 | 설명 |
|---|---|
| `hexdump $rsp` | 스택 시작 지점부터 헥스+아스키 덤프 |
| `hexdump 0x404040 64` | 지정 주소부터 64바이트 덤프 |

IDA/HxD의 헥스 뷰와 동일한 느낌으로, 왼쪽은 16진수 바이트, 오른쪽은 아스키 표현이 함께 나온다. 구조체나 인코딩된 문자열을 눈으로 바로 확인할 때 쓴다.

### 5) `search` — 메모리 전역 검색
| 명령 | 설명 |
|---|---|
| `search "flag"` | 프로세스 메모리 전체에서 해당 문자열이 있는 위치를 모두 찾음 |
| `search -t dword 0xdeadbeef` | 지정 타입(byte/word/dword/qword)의 값을 검색 |
| `search -x 4142434445` | 헥스 바이트 시퀀스로 검색 |

"이 문자열/값이 메모리 어딘가에 있을 텐데 어디인지 모르겠다"는 상황에서 가장 빠른 해결책이다. 예를 들어 입력한 패스워드가 복사된 위치를 찾거나, 특정 매직 넘버가 저장된 주소를 찾을 때 쓴다.

### 6) 그 외 자주 쓰는 Pwndbg 전용 명령
| 명령 | 설명 |
|---|---|
| `nearpc` | 현재 위치 주변 명령어를 보기 좋게 출력(디스어셈블리 보조) |
| `entry` | 프로그램 엔트리 포인트(`_start`)에 브레이크포인트 걸고 실행 |
| `piebase` | PIE 바이너리의 로드 베이스 주소 확인 |
| `heap` | glibc 힙 청크 구조를 파싱해서 출력 |
| `bins` | tcache/fastbin/unsorted bin 등 힙 프리리스트 상태 출력 |
| `checksec` | 현재 로드된 바이너리의 보호 기법(NX, PIE, Canary 등) 요약 |
| `got` | GOT(Global Offset Table) 항목 목록 출력 |
| `xinfo <주소>` | 주소가 어떤 매핑/심볼에 속하는지 상세 정보 |
| `cyclic <길이>` | pwntools 스타일 De Bruijn 패턴 생성(오프셋 찾기용) |
| `cyclic -l <값>` | 크래시 시 레지스터/스택에 남은 패턴 값으로 정확한 오프셋 역산 |

## 출력 해석
- `context` 화면에서 레지스터 값이 빨간색/강조색으로 표시되면 바로 직전 명령으로 값이 바뀐 것
- `telescope` 출력에서 `0x7ffee...  →  0x00007f...  →  "hello"`처럼 화살표가 이어지면 포인터 체인을 따라간 결과이며, 마지막이 사람이 읽을 수 있는 문자열이면 그 값이 최종 데이터
- `vmmap` 출력에서 `[stack]`, `[heap]`, 라이브러리 경로(`libc.so.6`)가 각 줄 끝에 표시되어 영역을 바로 식별 가능
- `checksec` 출력은 x64dbg/CTF 관례와 동일하게 `Canary : Yes`, `PIE : Yes`, `NX : Enabled` 형태로 나온다

## 흔한 실수
- `telescope`를 쓰지 않고 `x/gx`를 여러 번 반복 호출하며 손으로 포인터를 따라가는 비효율 (Pwndbg 도입 목적 자체를 놓치는 것)
- `vmmap` 결과에서 권한 컬럼을 확인하지 않고 무작정 데이터 영역에 셸코드를 넣으려다 실행 안 되는 이유를 못 찾는 경우
- `search`로 문자열을 찾을 때 대소문자/인코딩(UTF-16 등)을 고려하지 않아 결과가 안 나오는 경우
- `heap`/`bins` 명령을 glibc 버전이 다른 환경에서 쓰고 파싱이 이상하다고 착각하는 경우(로컬 GDB의 libc와 대상 바이너리의 libc가 다를 수 있음 — `set solib-search-path` 등으로 맞춰야 함)

## 막혔을 때 다음 체크
1. `context` 자체가 안 뜨면 Pwndbg가 로드됐는지부터 확인(REV-0285)
2. `telescope`/`vmmap` 결과가 비어 있으면 프로세스가 `run`/`start`로 실제로 떠 있는지 확인(정적 로드 단계에서는 프로세스 메모리가 없음)
3. `search` 결과가 없으면 대소문자, 널 종료 여부, 인코딩을 바꿔서 재시도
4. `heap`/`bins`가 깨져 보이면 `checksec`으로 로드된 libc 버전을 확인하고 로컬 환경과 대조

## 미니 예제
```gdb
pwndbg> break main
pwndbg> run
pwndbg> context
pwndbg> telescope $rsp 10
pwndbg> vmmap
pwndbg> search "flag{"
pwndbg> hexdump $rsp 32
```

## 관련 글
- REV-0285 — Pwndbg 설치와 오프라인 준비
- REV-0284 — GDB 명령어 치트시트
- REV-0192 — Pwndbg 설치와 실행

## 출처/검증
- Pwndbg 공식 문서(pwndbg.re)와 공식 GitHub 저장소의 명령 목록(commands)을 기준으로 정리했다.
- 최종 확인일: 2026-09-08
