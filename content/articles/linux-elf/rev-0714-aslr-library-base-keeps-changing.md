---
id: REV-0714
title: "동적분석 중 ASLR 때문에 라이브러리 베이스 주소가 계속 바뀔 때"
slug: "rev-0714-aslr-library-base-keeps-changing"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, setarch]
keywords: ["disable-randomization", "setarch -R", "라이브러리 베이스 주소 변경", "ASLR 동적분석", "libc base 계산"]
aliases: ["gdb에서는 주소가 고정인데 직접 실행하면 다름", "libc 베이스가 매번 바뀜", "setarch -R 사용법", "randomize_va_space 끄기"]
symptom_keywords: ["gdb 안에서는 매번 같은 주소인데 터미널에서 직접 실행하면 주소가 다름", "libc 베이스 주소를 매번 다시 구해야 해서 번거로움", "스크립트로 반복 실행할 때마다 라이브러리 주소가 달라져 디버깅이 힘듦", "리크한 주소로 base를 계산해야 하는데 계산식이 헷갈림"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
ASLR이 왜 존재하는지는 REV-0104에서 다뤘지만, 실제 동적 분석 중에는 "GDB 안에서 실행하면 주소가 매번 똑같은데 터미널에서 직접 실행하면 다르다"는 혼란이 자주 생기는데, 이는 GDB가 기본적으로 자신이 실행시키는 자식 프로세스의 ASLR을 꺼놓기 때문이며, 재현 가능한 디버깅을 위해서는 이 동작을 이해하고 필요에 따라 `setarch -R`이나 리크 기반 오프셋 계산을 병행해야 한다.

## 언제 검색해야 하나
- GDB 안에서 `run`을 여러 번 해도 `info proc mappings` 결과의 라이브러리 주소가 항상 똑같아서 "ASLR이 꺼진 건가"라고 헷갈릴 때
- 반대로 GDB 밖에서 셸에 `./chall`을 직접 여러 번 실행했더니 매번 라이브러리 베이스가 달라져서 exploit 스크립트가 매번 실패할 때
- pwntools 스크립트에서 리크한 주소로 libc 베이스를 계산하는 공식이 헷갈릴 때
- 실행할 때마다 주소가 바뀌는 걸 완전히 고정하고 싶어서 ASLR을 끄는 방법을 찾을 때

## 핵심 개념

### GDB는 기본적으로 자신이 실행하는 프로세스의 ASLR을 끈다
GDB는 `set disable-randomization on`이 기본값으로 설정되어 있어서, `run`으로 실행하는 자식 프로세스는 **ASLR이 비활성화된 상태로 실행**된다. 그래서 GDB 안에서만 작업하다 보면 "이 프로그램은 원래 주소가 고정이구나"라고 착각하기 쉽지만, 실제로 셸에서 `./chall`을 직접 실행하면 커널의 정상적인 ASLR이 적용되어 매번 다른 주소가 나온다. 이 차이를 모르면 "GDB에서 확인한 주소를 그대로 실제 익스플로잇에 하드코딩했는데 실제 실행에서는 안 먹힌다"는 문제로 이어진다.

### GDB 안에서도 ASLR을 재현하고 싶을 때
GDB에서도 실제 배포 환경처럼 매번 주소가 바뀌는 걸 재현하려면 `set disable-randomization off`로 바꿔야 한다. 반대로 디버깅 편의를 위해 GDB 밖에서도 주소를 고정하고 싶다면 `setarch $(uname -m) -R ./chall`(또는 짧게 `setarch -R ./chall`)로 실행하면 그 프로세스만 ASLR이 꺼진 채로 실행된다.

### 시스템 전체 ASLR을 끄는 방법과 주의점
`echo 0 | sudo tee /proc/sys/kernel/randomize_va_space`로 시스템 전체 ASLR을 끌 수도 있지만, 이건 그 시스템에서 실행되는 모든 프로세스에 영향을 주는 전역 설정이라 실습/개인 환경이 아니면 권장되지 않는다. 실습이 끝나면 원래 값(`2`)으로 되돌려야 한다. CTF 환경이라면 프로세스 단위로 끄는 `setarch -R`이나 GDB의 `disable-randomization` 쪽이 더 안전한 선택이다.

### 진짜 익스플로잇에서는 주소를 고정하지 말고 리크 + 오프셋 계산으로 접근
실제 원격 서버를 상대할 익스플로잇이라면 ASLR을 끌 수 없으므로, 애초에 특정 주소를 하드코딩하는 접근 자체가 틀린 방향이다. 올바른 접근은 프로그램이 흘리는(leak) 라이브러리 내부 주소 하나를 얻은 뒤, `실제 베이스 = 리크한 주소 - (그 함수/오프셋의 libc 안에서의 상대 오프셋)`으로 그때그때 베이스를 계산하는 것이다. 이 상대 오프셋은 `readelf -s` 또는 `nm`으로 해당 libc 파일에서 직접 구하거나 pwntools의 `ELF('libc.so.6').symbols['이름']`으로 얻을 수 있다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) run
(gdb) info proc mappings
... libc-2.35.so 0x00007ffff7dc0000 ...
(gdb) run
(gdb) info proc mappings
... libc-2.35.so 0x00007ffff7dc0000 ...   # 재실행해도 항상 동일
```
같은 시각 셸에서는
```bash
$ ./chall &
$ cat /proc/$!/maps | grep libc
7f2a10203000-7f2a10230000 ...
$ ./chall &
$ cat /proc/$!/maps | grep libc
7f9b8c015000-7f9b8c042000 ...   # 실행할 때마다 다름
```

## 가장 먼저 할 것
지금 보고 있는 주소가 GDB 안에서 나온 것인지, 아니면 순수 셸 실행에서 나온 것인지부터 구분한다. GDB 안이라면 `show disable-randomization`으로 현재 설정을 확인한다.

## 단계별 절차
1. `show disable-randomization`으로 GDB의 현재 설정 확인(기본 `on`)
2. 실제 배포 환경처럼 ASLR이 살아있는 상태로 GDB에서 디버깅하고 싶다면 `set disable-randomization off` 후 재실행
3. GDB 없이도 특정 프로세스만 ASLR을 고정하고 싶다면 `setarch $(uname -m) -R ./chall`로 직접 실행
4. 여러 번 실행해서 매번 다른 주소가 재현되는지 `cat /proc/$!/maps`로 교차 검증
5. 실제 익스플로잇 스크립트에서는 주소를 고정값으로 넣지 말고, 리크한 주소에서 상대 오프셋을 빼서 베이스를 계산하는 방식으로 작성
6. 상대 오프셋은 배포받은 `libc.so.6`에서 `readelf -s ./libc.so.6 | grep 함수이름` 또는 pwntools `ELF` 객체로 확인

## 명령어/단축키
```gdb
show disable-randomization
set disable-randomization off
```
```bash
setarch $(uname -m) -R ./chall
cat /proc/<pid>/maps | grep libc
echo 0 | sudo tee /proc/sys/kernel/randomize_va_space   # 전역, 주의해서 사용
readelf -s ./libc.so.6 | grep printf
```
```python
# pwntools 예시
base = leaked_addr - libc.symbols['printf']
```

## 출력 해석
`/proc/<pid>/maps`에서 `libc-2.xx.so`가 매핑된 줄의 가장 왼쪽 숫자(예: `7f2a10203000`)가 그 실행에서의 libc 베이스다. 여러 번 실행해서 이 값이 계속 바뀌면 ASLR이 정상 동작 중인 것이고, GDB `info proc mappings`에서 재실행해도 값이 고정이면 `disable-randomization`이 `on`이라는 신호다.

## 흔한 실수
- GDB 안에서 구한 고정 주소를 그대로 실제 배포 서버 대상 익스플로잇에 하드코딩하는 것 — GDB 밖에서는 ASLR이 살아있어 실패한다.
- `setarch -R`을 안 쓰고 매번 `randomize_va_space`를 전역으로 껐다 켰다 하며 시스템 전체에 영향을 주는 것.
- 리크한 주소에서 베이스를 계산할 때 오프셋 부호를 반대로 써서(`+`를 써야 할 곳에 `-`) 엉뚱한 주소가 나오는 것.
- libc 버전이 실제 배포본과 다른데 그 libc의 오프셋으로 베이스를 계산해서 계속 틀린 값이 나오는 것(REV-0711 문제와 겹칠 수 있음).

## 막혔을 때 다음 체크
- ASLR이 애초에 왜 존재하고 무엇을 무작위화하는지 기초 개념이 필요하면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유.
- 로컬과 서버의 glibc 버전 자체가 달라서 오프셋 계산이 계속 안 맞는 상황이라면 → REV-0711 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때.
- PIE 바이너리 자체의 베이스 주소 랜덤화가 궁금하면 → REV-0103 PIE와 주소 계산.
- 프로세스 메모리 맵을 읽는 법이 헷갈리면 → REV-0670 프로세스 메모리 맵(/proc/pid/maps) 읽는 법.

## 미니 예제
```gdb
(gdb) show disable-randomization
Disabling randomization of debuggee's virtual address space is on.
(gdb) set disable-randomization off
(gdb) run
(gdb) info proc mappings
```
```bash
$ setarch $(uname -m) -R ./chall
$ cat /proc/$!/maps | grep libc
7f0000000000-... libc-2.35.so
$ setarch $(uname -m) -R ./chall
$ cat /proc/$!/maps | grep libc
7f0000000000-... libc-2.35.so   # setarch -R로 두 번 다 동일 주소
```
GDB의 `disable-randomization`을 끄면 GDB 안에서도 실제 환경처럼 재실행마다 주소가 바뀌고, 반대로 `setarch -R`을 쓰면 GDB 없이도 주소를 고정할 수 있다는 것을 확인할 수 있다.

## 관련 글
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0711 — 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때
- REV-0103 — PIE와 주소 계산
- REV-0670 — 프로세스 메모리 맵(/proc/pid/maps) 읽는 법

## 출처/검증
- GDB의 `set disable-randomization` 기본값(on)과 자식 프로세스 ASLR 비활성화 동작: GDB 공식 매뉴얼("Debugging with GDB") "Starting your Program" 챕터 기준 (2026-09-09 검증).
- `setarch -R` 옵션으로 특정 프로세스의 개인화(personality) ASLR을 끄는 동작: `setarch(8)` 공식 매뉴얼 기준.
- `/proc/sys/kernel/randomize_va_space`의 전역 ASLR 설정: Linux 커널 문서(`Documentation/admin-guide/sysctl/kernel.rst`) 기준.
