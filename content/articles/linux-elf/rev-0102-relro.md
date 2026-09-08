---
id: REV-0102
title: "RELRO가 리버싱에 의미하는 것"
slug: "rev-0102-relro"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [IDA, GDB, Pwndbg, checksec, readelf]
keywords: ["RELRO", "Full RELRO", "Partial RELRO", "No RELRO", "GNU_RELRO", "BIND_NOW", "GOT 보호", "relocation read-only"]
aliases: ["relro란", "full relro partial relro 차이", "relro 리버싱", "got overwrite 방어"]
symptom_keywords: ["checksec에 RELRO가 뭐라고 나오는지 모르겠음", "got 값이 왜 안 바뀌는지 모르겠음", "got가 read-only라 write이 안됨"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
RELRO(RELocation Read-Only)는 GOT(Global Offset Table)를 공격 대상으로 쓰지 못하게 만드는 바이너리 보호 기법으로, `checksec` 출력의 `RELRO` 항목이 `No/Partial/Full` 중 무엇이냐에 따라 GOT가 언제 채워지고 쓰기 가능한지가 완전히 달라진다.

## 언제 검색해야 하나
- `checksec ./chall` 결과에 `RELRO: Partial RELRO` 또는 `Full RELRO`라고 나오는데 그 의미를 모를 때
- GDB에서 GOT 슬롯을 덮어쓰려고(`set {long}addr = value`) 했는데 세그멘테이션 폴트가 날 때
- REV-0100(PLT/GOT)에서 설명한 lazy binding이 실제로는 동작하지 않고, 프로그램 시작부터 GOT에 이미 진짜 주소가 채워져 있는 걸 봤을 때
- `readelf -l` 출력에 `GNU_RELRO`라는 세그먼트가 왜 있는지 궁금할 때

## 핵심 개념

### RELRO가 막으려는 것
REV-0100에서 봤듯, GOT는 함수 포인터가 저장된 **쓰기 가능한** 데이터 영역이다. 원래 목적은 lazy binding을 위해 로더가 런타임에 값을 채워 넣는 것이지만, 쓰기 가능하다는 성질 자체가 공격 표면이 된다 — 만약 공격자가 임의 주소 쓰기(arbitrary write) 취약점을 가지고 있다면, `printf`의 GOT 슬롯을 `system`의 주소로 덮어써서 `printf("...")` 호출을 `system("...")` 호출로 바꿔치기할 수 있다(GOT overwrite 공격). RELRO는 이걸 막기 위해 GOT(정확히는 `.got` 및 관련 재배치 영역)를 프로그램 초기화가 끝난 뒤 읽기 전용으로 바꿔버리는 보호 기법이다.

### No RELRO
아무 보호도 없는 상태다. GOT 전체(`.got`, `.got.plt`)가 프로그램 종료 시까지 계속 쓰기 가능하다. lazy binding도 그대로 동작한다. 요즘 배포판 기본 gcc에서는 거의 나오지 않고, 일부러 `-z norelro` 옵션을 줘야 나온다.

### Partial RELRO
현재 대부분의 리눅스 배포판 기본값이다. `.got`(전역 변수용, `GLOB_DAT` 재배치)는 읽기 전용으로 바뀌지만, `.got.plt`(함수용, `JUMP_SLOT` 재배치 — 즉 PLT가 참조하는 GOT)는 여전히 **쓰기 가능**하게 남는다. lazy binding도 그대로 유지된다. 즉 Partial RELRO는 함수 GOT를 보호하지 못하며, GOT overwrite 공격이 여전히 가능하다.

### Full RELRO
가장 강한 보호다. 프로그램이 시작될 때(`_start`가 `main`을 부르기 전) **모든 심볼을 즉시 다 resolve**(Eager binding, `-z now`)해서 `.got.plt`에 진짜 함수 주소를 전부 채워 넣은 뒤, GOT 전체(`.got`, `.got.plt`)를 `mprotect`로 읽기 전용 세그먼트로 바꿔버린다. 이후에는 GOT에 어떤 값도 쓸 수 없다. 이때 lazy binding이 사라지므로 REV-0100에서 설명한 "첫 호출은 resolver를 거치고, 두 번째 호출부터 빠르다"는 동작 자체가 없어진다 — Full RELRO 바이너리는 **모든 호출이 처음부터 이미 채워진 진짜 주소로 바로 점프**한다.

### 리버싱 관점에서 왜 중요한가
1. **정적 분석 신뢰도**: Full RELRO 바이너리는 프로그램 시작 시점에 GOT가 이미 다 채워지므로, GDB에서 `break main` 이후 아무 때나 GOT를 읽어도 항상 진짜 함수 주소가 나온다. Partial RELRO에서는 아직 호출 안 된 함수의 GOT 슬롯이 PLT resolver 주소를 가리키고 있을 수 있다는 점을 기억해야 한다.
2. **exploit 전략 판단**: pwn 문제를 겸하는 리버싱 문제에서 GOT overwrite가 통하는지 여부는 RELRO 상태로 즉시 판단된다. Full RELRO면 GOT 공격 대신 다른 타겟(예: 스택, 힙 메타데이터, `.fini_array` 등)을 찾아야 한다.
3. **세그먼트 구조 이해**: `readelf -l`(program headers)에서 `GNU_RELRO`라는 별도의 세그먼트가 보이는데, 이건 로더에게 "프로그램 시작 후 이 범위를 읽기 전용으로 바꿔라"라고 알려주는 역할을 한다. 이 세그먼트가 존재하면 최소 Partial RELRO 이상이다.

## 화면/코드에서 보이는 징후
- `checksec` 결과 줄에 `RELRO:` 항목이 `No RELRO` / `Partial RELRO` / `Full RELRO` 중 하나로 표시됨
- `readelf -l ./chall` 출력에 `GNU_RELRO` 세그먼트가 있으면 Partial 이상
- `readelf -d ./chall` 출력에 `BIND_NOW` 플래그(또는 `FLAGS_1`에 `NOW` 비트)가 있으면 Full RELRO
- GDB로 GOT 슬롯에 값을 쓰려다 `Cannot access memory` 또는 프로그램이 SIGSEGV로 죽는 경우 Full RELRO일 가능성이 높음

## 가장 먼저 할 것
새 바이너리를 받으면 `checksec ./chall` 한 번으로 RELRO 상태를 포함한 모든 주요 보호 기법(NX, PIE, Canary, RELRO)을 한꺼번에 확인한다(전체 조합은 REV-0105 참고). RELRO가 Full이면 "GOT는 건드릴 수 없는 읽기 전용 데이터"라고 못 박고 다른 분석 방향을 잡고, Partial 이하이면 GOT 조작 가능성을 열어둔 채 분석한다.

## 단계별 절차

**1) checksec으로 빠르게 확인**
```bash
checksec --file=./chall
```

**2) GNU_RELRO 세그먼트 확인**
```bash
readelf -l ./chall | grep -A1 GNU_RELRO
```
출력 예:
```
GNU_RELRO      0x0000000000002dc8 0x0000000000003dc8 0x0000000000003dc8
               0x0000000000000238 0x0000000000000238  R      0x1
```
이 세그먼트가 있으면 로더가 이 주소 범위를 읽기 전용으로 바꾼다는 뜻이다.

**3) BIND_NOW(Full RELRO) 여부 확인**
```bash
readelf -d ./chall | grep -i 'BIND_NOW\|FLAGS'
```
`BIND_NOW`가 있으면 Full RELRO, 없고 `GNU_RELRO` 세그먼트만 있으면 Partial RELRO다.

**4) GDB로 GOT 쓰기 가능 여부 실측**
```gdb
break main
run
p &puts
set {long}&puts = 0x4141414141414141
```
Full RELRO면 이 `set` 명령이 `Cannot access memory at address ...` 에러를 낸다. Partial/No RELRO면 값이 정상적으로 바뀐다.

**5) Pwndbg로 GOT와 보호 상태 함께 확인**
```gdb
checksec
got
```
Pwndbg의 `checksec` 명령은 GDB 안에서 바로 보호 기법 요약을 보여주고, `got` 명령은 각 GOT 슬롯이 resolve됐는지 아닌지를 색으로 표시한다.

## 명령어/단축키
```bash
checksec --file=./chall
readelf -l ./chall | grep GNU_RELRO
readelf -d ./chall | grep BIND_NOW
```
GDB/Pwndbg: `checksec`, `got`, `set {long}addr = value`(쓰기 테스트)

## 출력 해석
- `checksec` 표에서 `RELRO` 열이 빨간색/`No RELRO`이면 GOT 전체가 열려 있는 가장 취약한 상태다.
- `Partial RELRO`(노란색 계열)는 실무에서 가장 흔한 기본값이며, `.got.plt`(함수 GOT)는 여전히 쓰기 가능하다는 점이 핵심이다.
- `Full RELRO`(초록색)는 GOT 전체가 잠긴 가장 강한 상태이며, `BIND_NOW`가 함께 표시된다.
- `readelf -d` 출력에서 `NOW` 플래그가 안 보이고 `GNU_RELRO`만 있다면 Partial RELRO로 판단한다.

## 흔한 실수
- "RELRO가 Full이니까 GOT 관련 취약점은 전혀 없다"고 단정하는 것 — Full RELRO는 GOT를 **쓰는 것**만 막을 뿐, GOT 값을 **읽어서 라이브러리 베이스를 leak**하는 데는 아무 제약이 없다. GOT leak을 통한 ASLR 우회는 Full RELRO에서도 여전히 유효한 기법이다.
- RELRO와 NX(실행 방지)를 혼동하는 것 — RELRO는 "GOT를 쓰기 금지"이고 NX는 "스택/힙 등의 데이터 영역을 실행 금지"로, 보호 대상과 방식이 전혀 다르다.
- Partial RELRO에서도 `.got`(변수용)는 이미 읽기 전용이라는 사실을 잊고 무작정 전역 변수 GOT를 덮어쓰려 시도하는 것.

## 막혔을 때 다음 체크
- GOT/PLT 구조 자체가 헷갈린다면 → REV-0100 PLT와 GOT 기초
- RELRO 외 다른 보호 기법(NX, Canary, PIE)까지 한 번에 정리하고 싶다면 → REV-0105 Canary NX PIE RELRO 한 번에 이해
- PIE와 주소 계산이 궁금하다면 → REV-0103 PIE와 주소 계산

## 미니 예제
```bash
$ checksec --file=./chall
RELRO           STACK CANARY      NX            PIE
Full RELRO      Canary found      NX enabled    PIE enabled

$ readelf -d ./chall | grep -i flags
 0x000000006ffffffb (FLAGS_1)    Flags: NOW PIE
```
`FLAGS_1`에 `NOW`가 있으므로 Full RELRO가 확정이다. 이 바이너리에서는 GDB로 `set {long}&puts = ...` 같은 GOT 쓰기 시도가 모두 실패한다.

## 관련 글
- REV-0100 — PLT와 GOT 기초
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0103 — PIE와 주소 계산

## 출처/검증
- RELRO 3단계(No/Partial/Full) 및 `-z relro`/`-z now` 옵션: Red Hat/Fedora 보안 기능 문서 및 GNU `ld` 매뉴얼(`-z relro`, `-z now`) 기준.
- `GNU_RELRO` 프로그램 헤더 및 GOT 보호 메커니즘: ELF/glibc 동적 링커(`elf/dl-reloc.c`의 `_dl_protect_relro` 개념) 기준.
- `checksec` 출력 항목 정의: `checksec.sh`/pwntools `checksec` 공식 도구 문서 기준 (2026-09-08 검증).
