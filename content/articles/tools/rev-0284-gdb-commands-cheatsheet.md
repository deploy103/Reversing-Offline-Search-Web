---
id: REV-0284
title: "GDB 명령어 치트시트"
slug: "rev-0284-gdb-commands-cheatsheet"
category: "tools"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB]
keywords: ["gdb 명령어", "gdb cheatsheet", "gdb break", "gdb x 명령어", "gdb backtrace", "gdb disassemble", "gdb watch", "gdb info registers", "gdb stepi nexti"]
aliases: ["gdb 단축 명령", "gdb 치트시트", "gdb 명령 정리", "gdb 자주쓰는 명령"]
symptom_keywords: ["gdb에서 다음 명령이 뭔지 모름", "gdb break 안 걸림", "gdb에서 메모리 보는법 모름", "gdb에서 레지스터 보는법", "gdb backtrace 사용법 모름", "gdb watch 사용법 모름"]
source_ids: ["SRC-GDB-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB로 CTF 바이너리를 분석할 때 실제로 반복해서 쓰는 명령은 `break`/`continue`/`stepi`/`nexti`/`disassemble`/`x`/`info registers`/`backtrace`/`watch` 정도로 좁혀지며, 이 카드 한 장만 옆에 두면 대부분의 상황에서 다음에 뭘 쳐야 할지 바로 찾을 수 있다.

## 언제 검색해야 하나
- GDB 프롬프트 앞에서 "다음에 뭘 쳐야 하지"라는 생각이 들 때
- `break`는 걸었는데 그다음 한 줄씩 진행하는 명령이 `step`인지 `stepi`인지 헷갈릴 때
- 특정 주소의 메모리 값을 16진수/문자열/명령어로 각각 어떻게 보는지 헷갈릴 때
- 레지스터 값, 콜스택, 워치포인트 설정 명령을 빠르게 찾고 싶을 때
- PIE 바이너리에서 실제 런타임 주소를 계산하는 방법이 기억 안 날 때

## 핵심 개념
GDB 명령은 크게 다섯 그룹으로 나눠 기억하면 편하다: **(1) 실행 제어**(멈추고 진행시키는 것), **(2) 관찰**(레지스터/메모리/스택을 읽는 것), **(3) 디스어셈블**(명령어를 보는 것), **(4) 조건부 정지**(watch), **(5) 프로세스 다루기**(attach/PIE). 아래 표는 이 다섯 그룹 순서로 정리했다.

## 가장 먼저 할 것
지금 뭘 하고 싶은지에 따라 표에서 해당 그룹만 찾아 쓰면 된다 — 처음 붙일 때는 "실행 제어", 값을 확인할 때는 "관찰", 코드를 읽을 때는 "디스어셈블" 그룹부터 본다.

## 단계별 절차
1. `gdb ./chall`로 실행한다.
2. `break main`(또는 원하는 지점)으로 멈출 곳을 정한다.
3. `run`(인자가 있으면 `run arg1 arg2`)으로 시작한다.
4. 아래 표의 명령으로 레지스터/메모리/디스어셈블을 확인하며 `stepi`/`nexti`/`continue`로 진행한다.

## 명령어/단축키

### 1) 시작과 실행 제어
| 명령 | 축약 | 설명 |
|---|---|---|
| `run` | `r` | 프로그램을 처음부터(또는 재시작) 실행. 브레이크포인트 없으면 끝까지 실행 |
| `run arg1 arg2` | `r arg1 arg2` | 명령줄 인자를 주며 실행 |
| `start` | | `main`에 임시 브레이크포인트를 걸고 `run` |
| `starti` | | ELF 진입점(`_start`)에서 멈춤. `main` 실행보다도 이전 시점 |
| `set args a b c` | | 이후 `run`에 쓰일 인자를 미리 지정 |
| `continue` | `c` | 멈춘 지점에서 다음 브레이크포인트/종료까지 계속 진행 |
| `kill` | `k` | 실행 중인 대상 프로세스를 강제 종료 |
| `quit` | `q` | GDB 종료 |

### 2) 브레이크포인트
| 명령 | 설명 |
|---|---|
| `break main` (`b main`) | `main` 함수 시작에 브레이크포인트 |
| `break *0x401234` | 특정 주소에 브레이크포인트(디스어셈블리 상 주소) |
| `break file.c:42` | 소스 라인 기준 브레이크포인트(디버그 심볼 있을 때) |
| `tbreak <위치>` | 한 번 걸리면 자동 삭제되는 임시 브레이크포인트 |
| `delete <번호>` | 지정 브레이크포인트 삭제. 번호 생략 시 전체 삭제 |
| `disable`/`enable <번호>` | 삭제하지 않고 끄기/켜기 |
| `info breakpoints` | 현재 걸린 브레이크포인트 목록 확인 |
| `condition <번호> <식>` | 조건이 참일 때만 걸리는 조건부 브레이크포인트 |

### 3) 한 줄씩 진행하기 (step 계열)
| 명령 | 축약 | 설명 |
|---|---|---|
| `stepi` | `si` | 어셈블리 명령어 1개 진행. `call`이면 함수 안으로 들어감 |
| `nexti` | `ni` | 어셈블리 명령어 1개 진행하되 `call`은 통째로 실행하고 다음 줄로 |
| `step` | `s` | 소스 라인 기준으로 1줄 진행(디버그 심볼 필요), 함수 안으로 들어감 |
| `next` | `n` | 소스 라인 기준 1줄, 함수는 건너뜀 |
| `finish` | | 현재 함수가 끝날 때까지 실행하고 리턴값까지 보여줌 |
| `until` | | 현재 위치보다 뒤쪽 주소까지 진행(루프 탈출용) |

스트립된 바이너리나 디버그 심볼이 없는 CTF 바이너리에서는 `step`/`next` 대신 `stepi`/`nexti`를 훨씬 자주 쓴다.

### 4) 레지스터/메모리 관찰
| 명령 | 설명 |
|---|---|
| `info registers` (`i r`) | 모든 범용 레지스터 값 출력 |
| `info registers rax` | 특정 레지스터만 출력 |
| `print $rip` (`p $rip`) | 표현식 평가 (레지스터, 변수, 산술식 모두 가능) |
| `x/4xw $rsp` | 메모리 조사(examine). `4xw` = 4개, 16진수(x), word(4바이트) 단위 |
| `x/s 0x402004` | 해당 주소를 문자열로 출력 |
| `x/10i $rip` | 해당 주소부터 명령어 10개를 디스어셈블 출력 |
| `x/g $rsp` | 8바이트(giant) 단위로 출력 |

`x/NFU ADDR` 형식이 핵심이다: N=개수, F=포맷(x 16진수, d 10진수, u 부호없는10진수, s 문자열, i 명령어), U=단위(b=1바이트, h=2바이트, w=4바이트, g=8바이트).

### 5) 디스어셈블
| 명령 | 설명 |
|---|---|
| `disassemble` (`disas`) | 현재 함수 전체 디스어셈블 |
| `disassemble main` | 지정 함수 디스어셈블 |
| `disassemble 0x401000,0x401050` | 주소 범위 디스어셈블 |
| `set disassembly-flavor intel` | AT&T 대신 Intel 문법 사용(IDA/Ghidra와 동일 표기) |

### 6) 콜스택
| 명령 | 축약 | 설명 |
|---|---|---|
| `backtrace` | `bt` | 현재까지의 함수 호출 스택 전체 출력 |
| `backtrace N` | | 최근 N개 프레임만 출력 |
| `frame N` | `f N` | N번 스택 프레임으로 이동해서 그 시점 변수를 봄 |
| `info frame` | | 현재 프레임의 상세 정보(리턴 주소, 저장된 레지스터 위치 등) |

### 7) 워치포인트 (값이 바뀌는 순간 정지)
| 명령 | 설명 |
|---|---|
| `watch <변수/주소>` | 해당 값이 쓰기로 바뀌는 순간 자동 정지 |
| `watch *(int*)0x404040` | 특정 메모리 주소를 감시 |
| `rwatch <대상>` | 읽기(read)가 발생하면 정지 |
| `awatch <대상>` | 읽기/쓰기 둘 다 감지 |
| `info watchpoints` | 현재 설정된 워치포인트 목록 |

워치포인트는 "이 변수가 대체 어디서 바뀌는지 모르겠다"는 상황(예: 전역 플래그 변수, 카나리 값)에서 매우 강력하다.

### 8) PIE(ASLR) 주소 다루기
| 명령 | 설명 |
|---|---|
| `info proc mappings` | 현재 프로세스의 메모리 맵과 로드 베이스 주소 확인 |
| `break *0x1234` (PIE 오프셋) | GDB는 PIE 바이너리에서 `break *심볼오프셋` 형태 자동 보정 일부 지원, 함수명 사용이 더 안전 |
| `set disable-randomization on` | (기본값) GDB가 실행할 때 ASLR을 꺼서 매번 같은 베이스로 로드 — 재현성 확보 |
| `p/x $rip - <베이스>` | 현재 RIP에서 로드 베이스를 빼서 바이너리 파일 기준 오프셋 계산 |

기본적으로 GDB는 자신이 `run`으로 띄운 프로세스의 ASLR을 꺼두기 때문에, `start` 후 확인한 주소는 다시 실행해도 대부분 동일하다.

### 9) 프로세스 attach
| 명령 | 설명 |
|---|---|
| `gdb -p <PID>` | 이미 실행 중인 프로세스에 붙기(attach) |
| `attach <PID>` | GDB 안에서 붙기 |
| `detach` | 붙인 프로세스에서 떨어지기(프로세스는 계속 실행됨) |

## 출력 해석
- `x/4xw $rsp` 결과 예: `0x7fffffffe420: 0x00000000 0x00007fff 0x004011a9 0x00000001` — 왼쪽이 주소, 오른쪽 4개가 4바이트씩 16진수 값
- `bt` 결과에서 `#0`이 현재 위치, 번호가 커질수록 호출한 쪽(caller) 방향
- `Breakpoint 1, 0x0000555555555169 in main ()`은 브레이크포인트 1번이 `main`에서 걸렸다는 뜻이며, 앞의 주소는 PIE 로드 베이스가 반영된 실제 런타임 주소

## 흔한 실수
- 스트립된 바이너리에서 `step`/`next`를 썼다가 "소스 정보 없음" 에러를 보고 당황 — `stepi`/`nexti`로 바꿔야 함
- `x/4xw`처럼 단위를 안 붙이고 그냥 `x $rsp`만 써서 원하는 크기와 다른 값이 나옴
- `break *main`처럼 함수명 앞에 `*`를 붙여 심볼과 주소 문법을 혼동(함수명은 `*` 없이, 주소는 `*` 붙여서)
- PIE 바이너리인데 IDA/Ghidra에서 본 주소를 그대로 `break`에 써서 안 걸림 — 로드 베이스를 더해야 함

## 막혔을 때 다음 체크
1. `info breakpoints`로 브레이크포인트가 실제로 걸려 있는지, enable 상태인지 확인
2. PIE 여부는 `file ./chall` 또는 `checksec ./chall`로 확인
3. `disassemble`이 이상하게 나오면 `set disassembly-flavor intel`이 적용됐는지 확인
4. 값이 예상과 다르면 단위(b/h/w/g)를 다시 확인 — 가장 흔한 실수 지점

## 미니 예제
```gdb
(gdb) break main
(gdb) run
(gdb) info registers rax rdi rsi
(gdb) x/8xb $rsp
(gdb) disassemble
(gdb) stepi
(gdb) backtrace
(gdb) watch global_flag
(gdb) continue
```

## 관련 글
- REV-0283 — GDB 설치와 기본 설정
- REV-0286 — Pwndbg 명령어 치트시트
- REV-0185 — GDB 실행 run start args 사용법

## 출처/검증
- GDB 공식 온라인 문서(sourceware.org, 브레이크포인트/스텝/메모리 조사/워치포인트 챕터)를 기준으로 명령을 정리했다.
- 최종 확인일: 2026-09-08
