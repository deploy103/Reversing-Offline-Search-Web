---
id: REV-0687
title: "GDB에서 Cannot access memory at address 오류가 뜰 때"
slug: "rev-0687-gdb-cannot-access-memory-at-address"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["Cannot access memory at address", "gdb 메모리 접근 오류", "gdb x 명령 오류", "unmapped memory gdb", "gdb 세그폴트 분석"]
aliases: ["gdb cannot access memory", "gdb 메모리를 읽을 수 없음", "gdb x/examine 오류"]
symptom_keywords: ["gdb에서 x/s로 봤더니 Cannot access memory at address가 뜸", "gdb print 했더니 Cannot access memory", "gdb에서 포인터를 따라갔더니 접근 불가 오류", "pie 주소 계산했는데 gdb 메모리 접근 오류"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`Cannot access memory at address 0x...`는 GDB가 **그 주소에 아무 것도 매핑되어 있지 않다**고 커널로부터 통보받았다는 뜻이며, 원인은 대부분 (1) 포인터 값 자체가 NULL/쓰레기값인 진짜 버그, (2) PIE 베이스를 안 더하고 정적 오프셋을 그대로 쓴 계산 실수, (3) 프로세스가 아직 실행 전이거나 이미 종료된 상태에서 메모리를 조회한 경우 중 하나이므로, `info registers`로 포인터 값을 먼저 확인하고 `vmmap`/`info proc mappings`로 실제 매핑된 범위와 비교하는 것이 가장 빠른 진단 순서다.

## 언제 검색해야 하나
- `x/s $rax`나 `print *ptr`을 쳤는데 `Cannot access memory at address 0x0` 또는 `0x41414141`처럼 낯선 값이 뜰 때
- PIE 바이너리에서 IDA로 확인한 오프셋을 그대로 `x/4xg 0x1349`처럼 썼는데 이 오류가 뜰 때
- 스택 버퍼 오버플로우 익스플로잇을 테스트하다가 `bt`나 `print $rbp` 근처에서 이 오류가 뜨는데, 이게 버그인지 익스플로잇이 실제로 먹힌 증거인지 헷갈릴 때
- 프로그램이 이미 끝났는데 이전에 봐뒀던 주소를 다시 조회하려다 이 오류를 만났을 때

## 핵심 개념

### 세 갈래 원인 구분이 핵심
1. **포인터 값 자체가 잘못됨(진짜 버그/취약점의 증거)**: `x/s $rdi`처럼 레지스터를 역참조했는데 그 레지스터 값이 `0x0`이거나 `0x4141414141414141`(`AAAAAAAA`) 같은 패턴이면, 이건 GDB 문제가 아니라 **NULL 포인터 역참조**이거나 **버퍼 오버플로우로 저장된 포인터/리턴 주소가 사용자 입력으로 덮인 것**이다. pwn 문제를 풀 때는 오히려 이 오류가 "내가 스택을 컨트롤하고 있다"는 긍정적 신호일 수 있다.
2. **PIE 베이스 계산 누락**: PIE 바이너리는 실행할 때마다 로드 베이스가 바뀐다(REV-0103, REV-0104). IDA에서 본 오프셋(예: `0x1349`)을 실행 후 베이스를 더하지 않고 그대로 `x` 명령에 넣으면, 그 작은 숫자는 현재 프로세스 주소 공간에 아예 매핑되어 있지 않은 위치라서 이 오류가 뜬다. → REV-0693 참고.
3. **타이밍 문제**: 프로세스가 아직 시작되지 않았거나(`run`/`start` 전) 이미 종료된 뒤에는 메모리 자체가 매핑되어 있지 않다. `info proc mappings`가 비어 있거나 오류를 내면 지금 조회할 살아있는 프로세스가 없다는 뜻이다.

### "매핑 여부"와 "값이 옳은지"는 다른 질문
GDB가 이 오류를 낸다는 것은 **커널이 해당 페이지에 대해 프로세스에게 어떤 권한도 부여하지 않았다**(페이지 폴트가 나며 유효하지 않은 접근)는 뜻일 뿐, 주소 계산이 "거의 맞았는데 조금 틀렸다"는 것과 "완전히 엉뚱한 값"이라는 것을 구분해주지는 않는다. 그래서 이 오류를 만나면 항상 "그 주소가 어디 근처인지"를 `vmmap`으로 먼저 눈으로 확인하는 습관이 중요하다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) x/s $rax
0x0:    Cannot access memory at address 0x0
(gdb) print *(int*)0x1349
Cannot access memory at address 0x1349
(gdb) bt
#0  0x0000000000000000 in ?? ()
Cannot access memory at address 0x0
```

## 가장 먼저 할 것
`info registers`로 문제가 된 포인터/주소 값을 먼저 눈으로 확인하고, `vmmap`(Pwndbg) 또는 `info proc mappings`(순정 GDB)로 지금 프로세스에 실제로 매핑되어 있는 주소 범위와 비교한다.

## 단계별 절차

**1) 문제의 주소가 어디서 왔는지 확인**
```gdb
(gdb) info registers
(gdb) print $rdi
(gdb) print/x $rax
```
값이 `0x0`이거나 `0x41414141`류의 반복 패턴이면 진짜 버그/오버플로우일 가능성이 높다 — REV-0694, REV-0113(core dump)로 이어서 분석한다.

**2) 실제 매핑된 범위 확인**
```gdb
(gdb) info proc mappings
```
Pwndbg가 있다면:
```
pwndbg> vmmap
```

**3) PIE 오프셋 계산 실수인지 확인**
```bash
checksec --file=./chall
```
`PIE enabled`인데 조회한 주소가 `vmmap`의 어느 범위와도 안 겹친다면, 십중팔구 베이스를 안 더한 정적 오프셋 그대로다. → `베이스 + 오프셋`으로 다시 계산(REV-0693).

**4) 프로세스가 살아있는지 확인**
```gdb
(gdb) info program
```
`The program being debugged is not being run.`이 나오면 프로세스가 아직 시작 전이거나 이미 종료된 상태이므로, `start`나 `run` 이후에 다시 조회한다.

**5) 근처를 넓게 살펴보며 감을 잡기**
```gdb
(gdb) x/20gx $rsp-0x50
```
Pwndbg의 `telescope`를 쓰면 포인터 체인까지 자동으로 따라가며 보여준다:
```
pwndbg> telescope $rsp -l 20
```

## 명령어/단축키
```gdb
info registers
info proc mappings
info program
x/20gx $rsp
```
```
pwndbg> vmmap
pwndbg> telescope $rsp -l 20
```
```bash
checksec --file=./chall
```

## 출력 해석
- `vmmap`/`info proc mappings`에 나온 범위 중 어느 것과도 겹치지 않는 주소를 읽으려 했다면 그 주소는 애초에 존재하지 않는 페이지다.
- 조회 주소가 `vmmap`의 실행 파일 자신의 베이스보다 훨씬 작은 값(예: `0x1349`처럼 4~5자리)이라면 PIE 오프셋을 그대로 쓴 전형적인 실수다.
- `0x4141414141414141`, `0x6161616161616161`(`aaaaaaaa`)처럼 사람이 입력한 패턴이 그대로 레지스터/스택에 보인다면 버퍼 오버플로우로 그 값이 덮였다는 뜻이며, pwntools의 `cyclic`/`cyclic_find`로 정확한 오프셋을 역산할 수 있다.

## 흔한 실수
- PIE 베이스를 더하지 않고 IDA 오프셋을 그대로 `x`/`print`에 넣는 것 — 반드시 `start`나 `run` 이후 `vmmap`으로 베이스를 구해서 더한다.
- 프로세스가 이미 종료됐는데 이전 세션에서 봐둔 주소를 그대로 다시 조회하는 것 — `run`을 다시 실행하고 나서 조회해야 한다.
- 이 오류를 무조건 "GDB가 고장났다"고 오해하는 것 — 대부분 정상적인 커널의 페이지 폴트 보고이며, pwn 문제에서는 오히려 취약점이 동작하고 있다는 증거일 때가 많다.
- `print`의 결과 타입을 잘못 캐스팅해서(`(char*)` 대신 `(int*)` 등) 실제로는 유효한 주소인데 크기를 잘못 읽어 인접 페이지까지 넘어가 버리는 것.

## 막혔을 때 다음 체크
- PIE 베이스 계산 자체가 헷갈리면 → REV-0693 PIE 바이너리에서 GDB 브레이크포인트 주소가 계속 안 맞을 때
- 스택 프레임이 깨진 것 같으면 → REV-0694 GDB에서 스택 프레임이 corrupted stack frame이라고 나올 때
- 크래시 이후 사후 분석이 필요하면 → REV-0113 Core dump와 크래시 지점 분석 기초
- PIE/ASLR 원리 자체가 궁금하면 → REV-0103 PIE와 주소 계산, REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유

## 미니 예제
```gdb
(gdb) run
Starting program: /home/user/chall
Breakpoint 1, main () at chall.c:12
(gdb) x/s 0x1349
Cannot access memory at address 0x1349
(gdb) info proc mappings
0x555555554000     0x555555555000 ... r--p   /home/user/chall
0x555555555000     0x555555556000 ... r-xp   /home/user/chall
(gdb) x/s (0x555555554000 + 0x1349)
0x555555555349 <banner>:       "Welcome!"
```
정적 오프셋 `0x1349`만으로는 매핑되지 않은 주소라 실패했지만, 이번 실행의 베이스(`0x555555554000`)를 더한 절대 주소로는 정상적으로 문자열을 읽었다.

## 관련 글
- REV-0693 — PIE 바이너리에서 GDB 브레이크포인트 주소가 계속 안 맞을 때
- REV-0694 — GDB에서 스택 프레임이 corrupted stack frame이라고 나올 때
- REV-0113 — Core dump와 크래시 지점 분석 기초
- REV-0103 — PIE와 주소 계산
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유

## 출처/검증
- `Cannot access memory at address` 메시지의 의미(매핑되지 않은 페이지 접근): GDB 공식 문서 "Examining Memory" 섹션 기준.
- `info proc mappings`, `vmmap`을 통한 매핑 확인 절차: GDB 공식 문서 및 Pwndbg 공식 문서(pwndbg.re) 기준.
- 버퍼 오버플로우로 인한 포인터/리턴주소 오염 패턴(`0x41414141` 등)과 `cyclic`/`cyclic_find`: pwntools 공식 문서의 `cyclic` 유틸리티 설명 기준 (2026-09-08 검증).
