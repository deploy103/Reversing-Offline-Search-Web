---
id: REV-0718
title: "GDB info registers 값이 화면마다 다르게 보여서 헷갈릴 때"
slug: "rev-0718-gdb-info-registers-inconsistent-across-runs"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["info registers", "disable-randomization", "ASLR", "COLUMNS LINES 환경변수", "스택 주소 불일치"]
aliases: ["gdb 레지스터 값이 매번 다름", "gdb rsp 주소 안맞음", "gdb랑 직접 실행이랑 주소 다름", "info registers 재현 안됨"]
symptom_keywords: ["info registers 값이 스크린샷마다 다름", "gdb에서 실행할때랑 그냥 실행할때랑 rsp가 다름", "팀원 화면이랑 내 화면 주소가 다름", "같은 바이너리인데 주소가 계속 바뀜"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB 안에서 `run`을 반복할 때는 `disable-randomization` 옵션이 기본으로 켜져 있어 같은 GDB 세션·같은 실행 환경이면 주소가 항상 똑같이 나오지만, "화면마다 값이 다르다"는 혼란은 대부분 ASLR 자체보다 **GDB가 몰래 주입하는 `COLUMNS`/`LINES` 환경변수, 실행 경로 길이, argv/envp 차이**가 스택 시작 주소를 미묘하게 바꾸기 때문이며, 절대 주소를 하드코딩해서 비교하지 말고 항상 베이스 대비 오프셋으로 봐야 한다.

## 언제 검색해야 하나
- GDB에서 `info registers`로 본 RSP/RBP 주소가 어제 캡처한 화면이나 팀원이 공유한 스크린샷과 값이 달라서 "내가 뭘 잘못했나" 헷갈릴 때
- GDB 안에서 `run`할 때 나온 주소와, 터미널에서 그냥 `./chall`로 직접 실행했을 때 스크립트가 계산한 주소가 안 맞을 때
- 분명 ASLR을 껐다고 생각했는데도 실행할 때마다 주소가 바뀌는 것처럼 보일 때

## 핵심 개념

### GDB는 기본적으로 ASLR을 꺼서 실행한다
GDB는 디버깅 편의를 위해 `disable-randomization` 옵션이 **기본값 on**이다. 즉 GDB 안에서 `break main; run`을 열 번 반복해도, 다른 조건이 동일하면 스택/힙/PIE 베이스 주소가 매번 완전히 똑같이 나온다. `show disable-randomization`으로 확인할 수 있다:
```
(gdb) show disable-randomization
Disabling randomization of debuggee's virtual address space is on.
```
그래서 "GDB 안에서 실행할 때마다 값이 바뀐다"면 ASLR 문제가 아니라 다른 원인(아래)을 의심해야 한다.

### 그런데도 값이 다르게 보이는 진짜 원인들

1. **GDB가 주입하는 환경변수 `COLUMNS`, `LINES`**: GDB는 터미널 창 크기를 자식 프로세스에 전달하려고 `COLUMNS`, `LINES` 환경변수를 자동으로 넣어준다(`show environment COLUMNS`로 확인 가능). 이 환경변수들은 프로그램을 `./chall`로 직접 실행할 때는 존재하지 않는다. 환경변수 총 바이트 수가 스택 최상단에서부터 몇 바이트를 차지하는지에 영향을 주므로, **GDB 안에서 실행 vs 터미널에서 직접 실행**은 같은 ASLR 설정이어도 스택 시작 주소가 몇 바이트씩 어긋날 수 있다.
2. **실행 파일 경로 길이 차이**: `argv[0]`으로 전달되는 경로 문자열(`./chall` vs `/home/user/ctf/problem/chall`)도 스택에 그대로 올라가는 데이터라서, 절대경로로 실행하는지 상대경로로 실행하는지에 따라 스택 정렬이 달라질 수 있다.
3. **원래 ASLR 자체가 켜진 상태에서 GDB 밖에서 여러 번 실행 비교**: `./chall`을 GDB 없이 터미널에서 여러 번 실행하며 나온 로그(또는 `strace` 결과)를 비교하면, 커널 ASLR(`/proc/sys/kernel/randomize_va_space`가 기본값 2)이 그대로 적용되어 스택/힙/라이브러리 베이스가 매 실행마다 랜덤이다. 이건 GDB 문제가 아니라 정상적인 리눅스 ASLR 동작이다.
4. **다른 사람 화면과 절대 주소를 그대로 비교하는 것 자체가 원천적으로 무의미**: PIE 바이너리(REV-0103)는 실행할 때마다(또는 사람마다 커널·glibc 버전이 다르면) 베이스 자체가 다르므로, 절대 주소를 비교하는 것은 애초에 성립하지 않는 비교다. 항상 "베이스 주소 + 오프셋" 형태로 비교해야 한다.

## 화면/코드에서 보이는 징후
```
(gdb) show environment COLUMNS
COLUMNS = 80
(gdb) show environment LINES
LINES = 24
```
```
(gdb) info registers rsp
rsp            0x7fffffffd490      0x7fffffffd490
```
같은 바이너리를 터미널에서 직접 실행했을 때 계산된 스택 주소(예: pwntools `process()`로 얻은 값)와 위 GDB의 `rsp` 값이 몇 바이트 단위로 어긋나 있는 것이 전형적인 증상이다.

## 가장 먼저 할 것
"GDB 안에서 반복 실행"이 아니라 "GDB 실행 vs 실제 실행(또는 다른 사람 화면)"을 비교하고 있는 상황인지부터 구분한다. 전자라면 값이 달라질 이유가 없으므로 오타나 다른 실수를 의심하고, 후자라면 아래 절차로 환경 차이를 맞춘다.

## 단계별 절차

**1) GDB 안에서 진짜로 값이 바뀌는지 재현**
```
(gdb) break main
(gdb) run
(gdb) info registers rsp
(gdb) run
(gdb) info registers rsp
```
`disable-randomization`이 on인 기본 상태라면 두 `rsp` 값은 완전히 동일해야 한다. 만약 다르다면 `show disable-randomization`으로 정말 on인지 확인한다.

**2) GDB와 실제 실행 환경을 맞추기 — 환경변수 정리**
GDB가 주입하는 `COLUMNS`/`LINES`를 실제 실행 조건과 맞추려면 지운다:
```
(gdb) unset environment COLUMNS
(gdb) unset environment LINES
```

**3) pwntools로 GDB를 붙일 때도 같은 문제가 생길 수 있음을 기억**
pwntools의 `gdb.debug()`나 `gdb.attach()`를 쓸 때도 GDB가 실행 환경에 개입하므로, exploit 스크립트에서 계산한 주소와 실제 순정 실행 결과가 몇 바이트 어긋나는 사례가 실전에서 자주 보고된다. 익스플로잇 개발 시에는 오프셋을 하드코딩하지 말고, 가능하면 leak한 주소에서 상대 오프셋을 계산하는 방식으로 작성해야 한다.

**4) ASLR 자체를 완전히 끄고 비교하려면(리눅스 시스템 레벨)**
```bash
cat /proc/sys/kernel/randomize_va_space
# 0: 완전 비활성화, 1: 스택/힙만, 2: 기본값(전체 랜덤)
sudo sysctl -w kernel.randomize_va_space=0
```
또는 GDB 밖에서 단발성으로 끄고 실행하려면:
```bash
setarch $(uname -m) -R ./chall
```
`-R`은 `ADDR_NO_RANDOMIZE` 퍼소나리티를 적용해 그 실행 한 번만 ASLR을 끈다.

**5) 항상 오프셋 기준으로 비교하는 습관**
Pwndbg의 `vmmap`(REV-0193)으로 각 세그먼트의 베이스 주소를 확인한 뒤, 관심 있는 주소에서 베이스를 뺀 오프셋만 기록하고 비교한다. 오프셋은 ASLR/환경변수와 무관하게 항상 동일하다.

## 명령어/단축키
```
(gdb) show disable-randomization
(gdb) set disable-randomization on
(gdb) show environment COLUMNS
(gdb) unset environment COLUMNS
(gdb) unset environment LINES
(gdb) info registers rsp rbp rip
```
```bash
cat /proc/sys/kernel/randomize_va_space
setarch $(uname -m) -R ./chall
```

## 출력 해석
```
(gdb) info registers rsp
rsp            0x7fffffffd490      0x7fffffffd490
```
두 값이 똑같이 나오는 건 정상이다(16진수, 10진수 표기가 아니라 둘 다 16진수인데 GDB가 이름/값을 나란히 보여주는 형식). 만약 팀원 화면에서는 `0x7ffdxxxxxxxx`처럼 앞자리부터 다르다면, 그건 스택 값 자체가 문제가 아니라 커널 버전, 실행 시 전달된 환경변수 개수, argv 경로 길이 등 "그 실행을 만든 조건"이 서로 다르다는 신호다.

## 흔한 실수
- 다른 사람의 절대 주소 스크린샷을 보고 자기 환경에서 그대로 재현되길 기대하는 것 — PIE/ASLR 환경에서 절대 주소는 그 실행에만 유효하다.
- `disable-randomization`이 켜져 있는데도 GDB 안에서 값이 계속 바뀐다고 착각하는 것 — 대부분 `run`을 다른 인자나 다른 stdin으로 실행해서 실제로는 조건이 달라진 경우다.
- exploit 스크립트에 GDB에서 관찰한 절대 주소를 그대로 하드코딩하는 것 — GDB 실행 시 주입되는 `COLUMNS`/`LINES` 환경변수 때문에 실제 순정 실행과 몇 바이트 어긋날 수 있다.
- 커널의 `randomize_va_space`를 시스템 전역으로 0으로 바꿔놓고 원상복구를 잊는 것 — 로컬 실습이 끝나면 다시 2로 되돌리는 것이 안전하다.

## 막혔을 때 다음 체크
- ASLR 자체의 원리를 더 자세히 보고 싶다면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유
- PIE 바이너리에서 베이스 오프셋 계산법이 궁금하다면 → REV-0103 PIE와 주소 계산
- PIE 바이너리에서 브레이크포인트를 못 잡는 문제라면 → REV-0194 PIE 바이너리 GDB 브레이크포인트 잡기
- Pwndbg로 메모리 맵과 베이스 주소를 한눈에 보고 싶다면 → REV-0193 Pwndbg context telescope vmmap

## 미니 예제
```
(gdb) break main
(gdb) run
Breakpoint 1, 0x00005555555551f9 in main ()
(gdb) info registers rsp
rsp    0x7fffffffd490
(gdb) run
Breakpoint 1, 0x00005555555551f9 in main ()
(gdb) info registers rsp
rsp    0x7fffffffd490
```
같은 GDB 세션에서 `run`을 반복해도 `rip`, `rsp` 모두 완전히 동일하게 재현된다 — 이것이 `disable-randomization` 기본값 on의 실제 효과다. 이 값이 다른 화면과 다르게 나온다면, ASLR이 아니라 실행 환경(경로, 환경변수, GDB 사용 여부) 차이를 먼저 의심해야 한다.

## 관련 글
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0103 — PIE와 주소 계산
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기
- REV-0193 — Pwndbg context telescope vmmap
- REV-0188 — GDB info registers와 flags 확인

## 출처/검증
- `disable-randomization` 기본값 및 `info registers` 재현성: 본 환경 GDB 15.1에서 동일 바이너리 반복 `run` 후 `rsp`/`rip` 값 실측 비교로 검증 (2026-09-08).
- GDB가 `COLUMNS`/`LINES` 환경변수를 자식 프로세스에 자동 전달하는 동작: `show environment` 명령으로 실측 확인 (2026-09-08).
- `randomize_va_space`, `setarch -R`을 통한 ASLR 제어: Linux 커널 문서(`Documentation/admin-guide/sysctl/kernel.rst`) 및 `setarch(8)` man page 기준.
