---
id: REV-0678
title: "RELRO 미적용 바이너리에서 GOT Overwrite 패턴이 보이는 이유"
slug: "rev-0678-got-overwrite-no-relro"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["GOT overwrite", "No RELRO", "Partial RELRO", "lazy binding", "arbitrary write", "JUMP_SLOT", ".got.plt", "GOT hijacking"]
aliases: ["got overwrite가 뭔가요", "got 덮어쓰기 공격 원리", "relro 없을 때 got 공격", "got hijack 패턴"]
symptom_keywords: ["got 슬롯에 임의 주소를 써도 세그폴트가 안 남", "got overwrite exploit이 왜 통하는지 모르겠음", "printf got를 system으로 바꾸는 원리를 모르겠음", "checksec에 no relro 또는 partial relro라고 나옴"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
No RELRO 또는 Partial RELRO 바이너리는 `.got.plt`(함수 GOT)가 프로그램 종료 시점까지 쓰기 가능한 상태로 남아 있기 때문에, 공격자가 임의 주소 쓰기 취약점 하나만 확보하면 GOT 슬롯에 `system` 같은 임의 함수 주소를 덮어써 이후의 함수 호출을 통째로 가로챌 수 있다.

## 언제 검색해야 하나
- `checksec` 결과에 `RELRO: No RELRO` 또는 `Partial RELRO`라고 나와서 GOT 공격이 가능한지 판단해야 할 때
- 익스플로잇 코드에서 `puts` 또는 `printf`의 GOT 주소에 `system` 주소를 쓰는 패턴을 봤는데 원리가 이해 안 될 때
- GDB에서 GOT 슬롯에 값을 썼는데 세그폴트 없이 정상적으로 바뀌는 이유가 궁금할 때
- REV-0102(RELRO)를 읽었지만 "왜 GOT overwrite가 실제로 통하는지"를 코드 흐름으로 다시 확인하고 싶을 때

## 핵심 개념

### 전제: lazy binding과 .got.plt
REV-0100(PLT와 GOT 기초)에서 설명했듯, 동적 링크된 함수(예: `puts`)를 처음 호출하면 `.plt` 스텁이 `.got.plt`의 슬롯을 점프하는데, 이 슬롯은 처음에는 아직 실제 `puts` 주소가 아니라 PLT의 다음 명령(resolver 트램폴린, `push` + `jmp .plt[0]`)을 가리킨다. 첫 호출 시에만 `_dl_runtime_resolve`가 실제 `puts` 주소를 찾아 `.got.plt` 슬롯에 써넣고, 두 번째 호출부터는 이 슬롯을 통해 바로 점프한다. 이게 lazy binding이다.

이 메커니즘이 성립하려면 `.got.plt`가 프로그램 실행 내내 **쓰기 가능한 메모리**여야 한다 — 로더가 런타임에 값을 채워 넣어야 하기 때문이다. 문제는 "런타임에 쓰기 가능하다"는 성질이 로더뿐 아니라 공격자에게도 열려 있는 문이 된다는 점이다.

### No RELRO / Partial RELRO에서 무엇이 뚫려 있는가
- **No RELRO**: `.got`(전역 변수용)와 `.got.plt`(함수용) 모두 프로세스가 끝날 때까지 쓰기 가능하다.
- **Partial RELRO**(대부분의 배포판 기본값): `.got`는 초기화 후 읽기 전용으로 바뀌지만, `.got.plt`는 여전히 쓰기 가능한 채로 남는다. 이유는 lazy binding이 여전히 동작해야 하기 때문 — Partial RELRO는 `-z now`(즉시 바인딩)를 켜지 않으므로 `.got.plt`를 잠글 수 없다.

즉 **Full RELRO가 아닌 모든 경우, 함수 GOT(`.got.plt`)는 항상 쓰기 가능하다.** 이것이 GOT overwrite 공격의 전제조건이다.

### 공격이 성립하는 조건
GOT overwrite가 통하려면 아래 두 가지가 동시에 필요하다.
1. **임의 주소 쓰기(arbitrary write) 취약점** — 포맷 스트링 버그(`printf(buf)`에서 `%n`), 힙 오버플로우로 인접 청크의 메타데이터/포인터 조작, 배열 인덱스 out-of-bounds 쓰기 등으로 임의의 메모리 주소에 임의의 값을 쓸 수 있어야 한다.
2. **RELRO가 Full이 아님** — GOT가 쓰기 가능해야 한다.

이 두 조건이 맞으면 다음과 같은 흐름으로 공격한다.
1. `readelf -r` 또는 GDB `got`(Pwndbg)로 아직 자주 호출될 함수(예: `printf`, `puts`, `exit`)의 GOT 슬롯 주소를 찾는다.
2. `system` 함수의 실제 주소를 알아낸다(정적 바이너리거나, libc 베이스가 이미 leak된 상태이거나, PIE가 아니어서 고정 주소인 경우).
3. 취약점을 이용해 그 GOT 슬롯에 `system`의 주소를 덮어쓴다.
4. 프로그램이 이후 원래 함수(예: `printf("%s", "/bin/sh")`)를 호출하는 순간, `.plt` 스텁은 여전히 그 GOT 슬롯을 점프하지만 이제 그 슬롯에는 `system` 주소가 들어있으므로 실제로는 `system("/bin/sh")`가 실행된다.

핵심은 **호출하는 코드(`call printf@plt`)는 전혀 바뀌지 않는다**는 점이다. 바뀌는 것은 그 호출이 최종적으로 점프하는 목적지(GOT 슬롯 안의 값)뿐이다. 그래서 이 기법을 "GOT hijacking"이라고도 부른다.

### 왜 Full RELRO에서는 이게 막히는가
Full RELRO는 시작 시점에 모든 심볼을 즉시 바인딩(eager binding, `-z now`)한 뒤 `.got`와 `.got.plt` 전체를 `mprotect(..., PROT_READ)`로 읽기 전용으로 바꿔버린다. 이 시점 이후에는 GOT에 어떤 값도 쓸 수 없으므로, 위 3단계("GOT 슬롯에 값 쓰기")가 SIGSEGV로 실패한다. 다만 Full RELRO는 **쓰기만** 막을 뿐 **읽기**는 막지 않으므로, GOT를 읽어서 libc 베이스를 leak하는 것 자체는 Full RELRO에서도 여전히 가능하다는 점은 REV-0102에서 다룬 그대로다.

## 화면/코드에서 보이는 징후
- `checksec` 출력에서 `RELRO` 항목이 `No RELRO` 또는 `Partial RELRO`로 나온다.
- `readelf -l ./chall`에 `GNU_RELRO` 세그먼트가 아예 없거나(No RELRO), 있어도 `readelf -d`에 `BIND_NOW`가 없다(Partial RELRO).
- 취약점 코드에 `printf(user_input)`처럼 포맷 문자열을 사용자가 직접 제어하는 패턴, 또는 `arr[user_index] = value`처럼 인덱스 검증이 없는 배열 쓰기가 보인다.
- 익스플로잇 스크립트(pwntools 등)에 `elf.got['puts']`, `elf.sym['system']` 같은 값을 조합해 페이로드를 만드는 코드가 보인다.

## 가장 먼저 할 것
바이너리를 받으면 `checksec`으로 RELRO 상태부터 확인한다. Full RELRO면 GOT 쓰기는 포기하고 다른 타겟(스택 리턴 주소, `.fini_array`, 힙 `__free_hook`/`__malloc_hook` 등 — 단, 최신 glibc 2.34+에서는 hook이 제거됨에 유의)을 찾는다. No/Partial RELRO면 GOT 쓰기가 여전히 유효한 카드이므로, 바이너리에 임의 쓰기 취약점이 있는지를 우선순위로 찾는다.

## 단계별 절차

**1) RELRO 상태 확인**
```bash
checksec --file=./chall
```

**2) GOT 슬롯 주소 확인**
```bash
readelf -r ./chall | grep JUMP_SLOT
```
출력 예:
```
000000004018  000300000007 R_X86_64_JUMP_SLOT     0000000000000000 printf@GLIBC_2.2.5 + 0
000000004020  000400000007 R_X86_64_JUMP_SLOT     0000000000000000 puts@GLIBC_2.2.5 + 0
```
여기서 왼쪽 `Offset` 칸(`0x4018`, `0x4020`)이 바로 GOT 슬롯의 가상 주소다.

**3) GDB/Pwndbg에서 현재 GOT 상태 확인**
```gdb
break main
run
got
```
Pwndbg의 `got` 명령은 각 슬롯이 아직 resolve되지 않았는지(PLT resolver를 가리킴), 이미 resolve됐는지, 그리고 읽기 전용(RELRO로 보호됨)인지를 색으로 구분해 보여준다.

**4) 실제로 쓰기 가능한지 실측**
```gdb
set {long}0x404018 = 0x4141414141414141
x/gx 0x404018
```
No/Partial RELRO면 값이 그대로 바뀌고, Full RELRO면 `Cannot access memory at address 0x404018` 에러가 난다.

**5) system 주소 확보 후 실제 덮어쓰기(개념 시연)**
```gdb
p system
set {long}0x404018 = <system의 주소>
```
이후 프로그램이 `printf(...)`를 호출하는 지점을 지나가면 실제로는 `system`이 그 인자로 호출된다.

## 명령어/단축키
```bash
checksec --file=./chall
readelf -r ./chall | grep JUMP_SLOT
readelf -d ./chall | grep -i 'bind_now\|flags'
```
GDB/Pwndbg: `got`, `set {long}addr = value`, `x/gx addr`

## 출력 해석
- `readelf -r`의 `R_X86_64_JUMP_SLOT` 줄은 함수 GOT 슬롯을 나타낸다. `Offset` 칸이 실제 GOT 주소, `Type` 옆 심볼 이름이 어떤 함수의 슬롯인지 알려준다.
- Pwndbg `got` 출력에서 초록색/노란색은 대체로 "resolve됨", 빨간색 계열은 "아직 PLT resolver를 가리킴"을 의미하도록 색칠되는 경우가 많다(버전에 따라 배색은 다를 수 있음).
- `set {long}addr = value` 명령이 조용히 성공하면 그 주소는 쓰기 가능한 상태 — 즉 GOT overwrite가 통할 수 있는 조건이라는 뜻이다.

## 흔한 실수
- No RELRO/Partial RELRO만 확인하고 "GOT 공격이 가능하다"고 바로 단정하는 것 — 임의 주소 쓰기 취약점이 실제로 있어야만 성립한다. RELRO 상태는 필요조건이지 충분조건이 아니다.
- `.got`(변수용)와 `.got.plt`(함수용)를 구분하지 않는 것 — Partial RELRO에서는 `.got`는 이미 읽기 전용이므로 전역 변수 GOT를 덮어쓰려는 시도는 실패한다. 반드시 `.got.plt`(함수) 슬롯을 노려야 한다.
- 아직 한 번도 호출되지 않은 함수의 GOT 슬롯을 덮어쓰고 나서, PLT resolver 로직이 그 값을 다시 덮어쓸 거라 착각하는 것 — 이미 resolve된 상태건 아니건, GOT 슬롯에 값을 직접 쓰면 다음 `call func@plt`는 그 값을 그대로 점프 대상으로 쓴다. 로더가 다시 개입하지 않는다.
- PIE 바이너리에서 `system` 주소를 정적 분석만으로 알아내려는 것 — PIE/ASLR이 걸려 있으면 libc 베이스를 먼저 leak해야 `system`의 런타임 주소를 계산할 수 있다.

## 막혔을 때 다음 체크
- RELRO 3단계 자체가 헷갈린다면 → REV-0102 RELRO가 리버싱에 의미하는 것
- PLT/GOT lazy binding 메커니즘이 아직 헷갈린다면 → REV-0100 PLT와 GOT 기초
- 다른 보호 기법과 조합해서 전체 그림을 보고 싶다면 → REV-0105 Canary NX PIE RELRO 한 번에 이해
- `readelf -r` 출력 자체를 더 자세히 읽는 법이 궁금하다면 → REV-0682 objdump로 relocation 엔트리 읽는 법

## 미니 예제
```bash
$ checksec --file=./chall
RELRO           STACK CANARY      NX            PIE
Partial RELRO   No canary found   NX enabled    No PIE

$ readelf -r ./chall | grep JUMP_SLOT
000000601018  000300000007 R_X86_64_JUMP_SLOT     0000000000000000 printf@GLIBC_2.2.5 + 0
000000601020  000400000007 R_X86_64_JUMP_SLOT     0000000000000000 system@GLIBC_2.2.5 + 0
```
`system`이 이미 임포트되어 있는 바이너리라면(예: 메뉴에서 다른 기능으로 `system`을 호출하는 코드가 있는 경우), 굳이 libc 베이스를 leak할 필요 없이 `system`의 GOT 슬롯 값을 그대로 읽어와 `printf`의 GOT 슬롯에 덮어쓰는 것만으로 `printf(...)` 호출을 `system(...)`으로 바꿔치기할 수 있다 — No PIE이므로 두 GOT 슬롯 주소(`0x601018`, `0x601020`) 모두 고정값이라는 점도 공격을 쉽게 만든다.

## 관련 글
- REV-0102 — RELRO가 리버싱에 의미하는 것
- REV-0100 — PLT와 GOT 기초
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0682 — objdump로 relocation 엔트리 읽는 법

## 출처/검증
- lazy binding과 `.got.plt` 쓰기 가능 조건, RELRO 3단계별 차이: GNU `ld` 매뉴얼(`-z relro`, `-z now`) 및 glibc 동적 링커 relocation 처리(`elf/do-rel.h`, `_dl_protect_relro`) 기준.
- GOT overwrite 공격 흐름(임의 쓰기 + 쓰기 가능한 GOT 조합): CTF/pwn 커뮤니티에서 표준적으로 통용되는 기법 설명(예: pwntools/ROP 관련 문서, 다수의 공개 CTF writeup) 기준 — 일반적으로 통용되는 기법이며 특정 단일 출처보다는 다수 자료에서 공통적으로 확인됨.
- `readelf -r`의 `R_X86_64_JUMP_SLOT` 재배치 타입 의미: binutils `readelf` 문서 및 System V ABI x86-64 psABI 재배치 타입 표 기준 (2026-09-08 검증).
