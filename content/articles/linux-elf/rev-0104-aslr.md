---
id: REV-0104
title: "ASLR 때문에 실행할 때 주소가 바뀌는 이유"
slug: "rev-0104-aslr"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, checksec]
keywords: ["ASLR", "Address Space Layout Randomization", "randomize_va_space", "주소 무작위화", "스택 주소 랜덤", "라이브러리 베이스 랜덤"]
aliases: ["aslr란", "aslr 끄는법", "aslr 비활성화", "주소 랜덤화"]
symptom_keywords: ["주소가 실행할 때마다 바뀜", "같은 코드인데 주소가 다르게 나옴", "gdb랑 실제 실행이랑 주소가 다름", "스택 주소가 매번 다름", "libc 주소가 매번 다름"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
ASLR(Address Space Layout Randomization)은 리눅스 커널이 프로세스를 실행할 때마다 스택, 힙, 공유 라이브러리, (PIE라면) 실행 파일 자신의 로드 위치를 무작위 주소로 배치하는 보안 기능으로, 이 때문에 같은 바이너리를 두 번 실행해도 GDB가 보여주는 실제 주소가 매번 달라진다.

## 언제 검색해야 하나
- 같은 프로그램을 두 번 실행했는데 `print &buf`, `info proc mappings`로 본 스택/힙 주소가 매번 다를 때
- `libc` 함수(`printf` 등)의 실제 주소가 실행할 때마다 바뀌어서 "어느 주소가 진짜인지" 헷갈릴 때
- PIE 바이너리(REV-0103)에서 실행 파일 코드 자체의 주소도 매번 바뀌는 걸 보고 원리가 궁금할 때
- CTF pwn/rev에서 "ASLR을 꺼라"는 조언을 들었는데 실제로 어떻게 끄는지 모를 때

## 핵심 개념

### ASLR이 존재하는 이유
공격자가 메모리 손상 취약점(버퍼 오버플로우 등)을 악용하려면 대개 "어떤 주소로 실행 흐름을 돌릴지" 미리 알아야 한다. 예전처럼 스택/힙/라이브러리 주소가 항상 고정이었다면, 공격자는 그 고정 주소를 하드코딩해서 exploit을 짤 수 있었다. ASLR은 이 고정된 주소들을 프로세스가 시작될 때마다 커널이 무작위로 재배치함으로써, 공격자가 주소를 미리 알 수 없게 만든다. 리버싱 관점에서는 공격/방어 어느 쪽이든 "지금 내가 보는 주소가 다음 실행에도 유효한가"를 항상 의심해야 한다는 뜻이다.

### ASLR이 무작위화하는 영역
ASLR은 프로세스 주소 공간 안의 여러 영역을 독립적으로 무작위화한다.
- **스택**: 매 실행마다 시작 위치가 몇십 비트 범위 안에서 무작위로 이동한다.
- **힙**: `brk`/`mmap`으로 확보되는 힙 영역의 시작 위치도 무작위화된다.
- **공유 라이브러리(mmap 영역)**: `libc.so.6` 같은 라이브러리가 매핑되는 베이스 주소가 실행마다 바뀐다. `ldd` 명령의 출력 괄호 안 주소가 매번 다르게 나오는 것도 이 때문이다.
- **실행 파일 자신**: 단, 이건 바이너리가 **PIE로 컴파일된 경우에만** 해당한다. non-PIE(고정 베이스, `ET_EXEC`) 바이너리는 ASLR이 켜져 있어도 실행 파일 자체의 코드/데이터 주소는 항상 고정이다 — ASLR이 재배치할 수 있는 대상 자체가 아니기 때문이다. PIE와 ASLR의 관계는 REV-0103에서 더 자세히 다룬다.

### 커널의 ASLR 설정: /proc/sys/kernel/randomize_va_space
리눅스 커널은 이 값 하나로 ASLR의 강도를 조절한다.
- `0`: ASLR 완전히 꺼짐. 스택, 힙, 라이브러리, PIE 실행 파일 모두 고정 주소.
- `1`: 스택, 라이브러리, mmap 영역은 무작위화되지만 힙은 고정(레거시 방식).
- `2`(대부분의 배포판 기본값): 스택, 라이브러리, mmap, **힙까지 포함** 전부 무작위화.

값을 확인/변경하려면:
```bash
cat /proc/sys/kernel/randomize_va_space
echo 0 | sudo tee /proc/sys/kernel/randomize_va_space   # 시스템 전체 ASLR 끄기 (root 필요)
```
시스템 전체를 건드리는 건 부담스러우므로, 실무에서는 프로세스 단위로 끄는 방법을 훨씬 더 많이 쓴다.

### 프로세스 단위로 ASLR 끄기
```bash
setarch $(uname -m) -R ./chall
```
`setarch -R`(또는 `--addr-no-randomize`)은 커널에게 "이 프로세스만큼은 ADDR_NO_RANDOMIZE personality 플래그를 켜서 실행해달라"고 요청한다. 시스템 전체 설정은 그대로 두고 특정 실행만 고정 주소로 돌릴 수 있어 CTF 환경에서 가장 많이 쓰는 방법이다.

pwntools를 쓴다면 `process(..., aslr=False)`로 같은 효과를 낼 수 있고, GDB는 기본적으로 **디버깅 대상 프로세스의 ASLR을 자동으로 끄고** 실행한다(아래 참고).

### GDB와 ASLR의 관계 — 왜 GDB 안에서는 주소가 안정적으로 보이나
GDB는 기본 설정으로 `set disable-randomization on` 상태다. 즉 **GDB로 실행한 프로세스는 ASLR이 꺼진 채로 돈다.** 그래서 GDB 안에서 여러 번 `run`을 해봐도 스택/힙/라이브러리 주소가 항상 똑같이 나온다. 이건 디버깅을 편하게 하기 위한 GDB의 배려이지만, 동시에 함정이기도 하다 — **GDB 밖에서 그냥 `./chall`로 직접 실행하면 ASLR이 정상적으로 켜진 채 돌기 때문에, GDB 안에서 확인한 주소가 실제 배포 환경에서는 전혀 다른 값일 수 있다.** 문제 서버에 그대로 붙는 exploit을 짤 때 이 차이를 반드시 감안해야 한다.

```gdb
show disable-randomization
set disable-randomization off   # GDB에서도 ASLR을 실제로 켜서 테스트하고 싶을 때
```

### 리버싱/CTF 실전에서의 ASLR 대응 워크플로
1. **분석 단계**: ASLR을 꺼두고(GDB 기본값 그대로, 또는 `setarch -R`) 코드를 반복 실행하며 안정적인 주소로 분석한다.
2. **exploit 개발 단계**: 실제로는 ASLR이 켜진 원격 서버를 상대해야 하므로, 고정 주소를 그대로 하드코딩하지 않고 **정보 유출(leak)로 베이스 주소를 알아낸 뒤, 알려진 오프셋을 더해서 목표 주소를 계산**하는 방식으로 짠다. 예: `libc` 안의 아무 함수 주소 하나를 leak → 그 함수의 libc 내부 오프셋을 빼서 libc 베이스 계산 → `system`의 오프셋을 더해 `system`의 실제 주소 계산.
3. **검증 단계**: `setarch -R` 없이, ASLR을 켠 상태로 로컬에서 최소 몇 번은 실제로 재현되는지 반복 실행해서 확인한다. 무작위 주소에 의존하는 로직이 있으면 이 단계에서 실패가 드러난다.

## 화면/코드에서 보이는 징후
- 같은 바이너리를 `./chall`로 여러 번 실행하며 `cat /proc/self/maps`(또는 프로그램 자체가 자기 주소를 출력하도록 만든 디버그 코드)를 찍어보면 스택/힙/라이브러리 시작 주소가 매번 다름
- GDB 안에서는 여러 번 `run`해도 주소가 똑같이 나오는데, 터미널에서 직접 실행하면 다르게 나옴(위에서 설명한 GDB의 `disable-randomization on` 기본값 때문)
- `ldd ./chall`을 반복 실행하면 라이브러리 경로 옆 괄호 안 주소가 매번 바뀜

## 가장 먼저 할 것
지금 분석 목적이 "코드 로직을 이해하는 것"이라면 ASLR을 신경 쓰지 말고 GDB 기본 설정(ASLR 꺼짐) 그대로 진행한다. 목적이 "실제 원격 서버를 상대로 동작하는 exploit/자동화 스크립트를 만드는 것"이라면, 지금부터는 모든 주소를 "언젠가 leak해서 계산해야 하는 값"이라고 가정하고 접근한다.

## 단계별 절차

**1) 현재 시스템의 ASLR 설정 확인**
```bash
cat /proc/sys/kernel/randomize_va_space
```

**2) 특정 프로세스만 ASLR 끄고 실행**
```bash
setarch $(uname -m) -R ./chall
```

**3) GDB의 ASLR 처리 상태 확인**
```gdb
show disable-randomization
```
기본값은 `on`(즉 GDB 안에서는 ASLR이 꺼짐)이다.

**4) 실행 중 실제 매핑 주소 확인**
```gdb
break main
run
info proc mappings
```
또는 셸에서 직접:
```bash
cat /proc/<pid>/maps
```

**5) 여러 번 실행하며 주소 변화 관찰**
GDB 밖에서 `for i in 1 2 3; do ./chall & sleep 0.1; cat /proc/$!/maps | head -1; kill $! ; done` 같은 방식으로 스택/코드 베이스가 실행마다 바뀌는 것을 직접 확인해보면 감이 확실히 잡힌다.

## 명령어/단축키
```bash
cat /proc/sys/kernel/randomize_va_space
setarch $(uname -m) -R ./chall
cat /proc/<pid>/maps
```
GDB: `show disable-randomization`, `set disable-randomization on|off`, `info proc mappings`

## 출력 해석
- `randomize_va_space` 값이 `0`이면 ASLR 완전히 꺼짐, `2`면 전체 무작위화(가장 흔한 배포판 기본값).
- `/proc/<pid>/maps`에서 같은 프로세스를 다시 실행했을 때 각 영역(스택 `[stack]`, 힙 `[heap]`, 라이브러리 경로)의 시작 주소가 달라져 있다면 ASLR이 정상 동작 중이라는 뜻이다.
- GDB `show disable-randomization` 결과가 `on`이면 지금 이 GDB 세션의 실행은 ASLR이 꺼진 상태다.

## 흔한 실수
- GDB에서 확인한 고정 주소를 그대로 원격 서버 exploit에 하드코딩하는 것 — 원격 서버는 ASLR이 켜져 있으므로 다른 주소가 나온다.
- ASLR과 PIE를 같은 것으로 착각하는 것 — ASLR은 커널 기능(스택/힙/라이브러리/PIE 실행 파일을 무작위 배치), PIE는 컴파일 옵션(실행 파일이 재배치 가능하게 만들어짐)이다. non-PIE 바이너리는 ASLR이 켜져 있어도 실행 파일 자체의 주소는 안 바뀐다.
- `setarch -R`로 ASLR을 껐다고 착각했는데 실제로는 GDB로 실행해서 이미 꺼져 있던 것이라 착시가 생기는 것 — 두 메커니즘이 겹치므로 지금 어떤 방식으로 껐는지 구분해서 기억해야 한다.
- 시스템 전체 `randomize_va_space`를 `0`으로 영구히 바꿔놓고 잊어버리는 것 — 다른 프로그램의 보안에도 영향을 주므로, 특정 프로세스만 끄는 `setarch -R`을 쓰는 습관을 들이는 것이 좋다.

## 막혔을 때 다음 체크
- 실행 파일 자체 주소가 왜 PIE에서만 ASLR 영향을 받는지 자세히 알고 싶다면 → REV-0103 PIE와 주소 계산
- ASLR을 포함한 전체 보호 기법 조합을 정리하고 싶다면 → REV-0105 Canary NX PIE RELRO 한 번에 이해

## 미니 예제
```bash
$ ./chall & sleep 0.2; cat /proc/$!/maps | grep -m1 heap; kill $! 2>/dev/null
55a1b2c00000-55a1b2c21000 rw-p 00000000 00:00 0  [heap]

$ ./chall & sleep 0.2; cat /proc/$!/maps | grep -m1 heap; kill $! 2>/dev/null
5601f4a00000-5601f4a21000 rw-p 00000000 00:00 0  [heap]
```
같은 바이너리를 두 번 실행했을 뿐인데 힙 시작 주소가 `55a1b2c00000`에서 `5601f4a00000`로 완전히 바뀌었다. 이것이 ASLR의 실체다.

## 관련 글
- REV-0103 — PIE와 주소 계산
- REV-0105 — Canary NX PIE RELRO 한 번에 이해

## 출처/검증
- `randomize_va_space` 3단계 정의: Linux 커널 문서(`Documentation/admin-guide/sysctl/kernel.rst`, `randomize_va_space` 항목) 기준.
- `setarch -R`/`ADDR_NO_RANDOMIZE`: `setarch(8)` man page 및 리눅스 `personality(2)` 시스템 콜 문서 기준.
- GDB의 `disable-randomization` 기본 동작: GDB 공식 온라인 문서("Starting your Program") 기준 (2026-09-08 검증).
