---
id: REV-0105
title: "Canary NX PIE RELRO 한 번에 이해"
slug: "rev-0105-binary-protections-overview"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [checksec, GDB, Pwndbg, IDA]
keywords: ["checksec", "stack canary", "NX", "PIE", "RELRO", "바이너리 보호기법", "보안 완화기법", "mitigation"]
aliases: ["checksec 결과 해석", "바이너리 보호기법 총정리", "canary nx pie relro"]
symptom_keywords: ["checksec 결과를 어떻게 읽는지 모르겠음", "canary found가 뭔지 모르겠음", "nx enabled가 뭔지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`checksec ./chall` 한 번이면 이 바이너리가 스택 카나리(Canary), 실행 방지(NX), 위치 독립 실행(PIE), GOT 보호(RELRO)를 각각 켜놓았는지 모두 확인할 수 있고, 이 네 가지 조합이 리버싱/분석 전략 전체를 결정한다.

## 언제 검색해야 하나
- `checksec ./chall`을 처음 실행했는데 표 형태 출력이 무엇을 뜻하는지 전체적으로 감이 안 잡힐 때
- 개별 보호 기법(Canary/NX/PIE/RELRO)은 각각 알고 있는데 이들이 어떻게 서로 연결되는지, 분석 순서를 어떻게 잡아야 하는지 궁금할 때
- CTF 문제를 받자마자 "이 바이너리는 어떤 종류의 취약점/분석이 가능할지" 5분 안에 감을 잡고 싶을 때

## 핵심 개념

### 네 가지 보호 기법 한눈에 정리
| 보호 기법 | 무엇을 막나 | 리버싱에서 의미 | 자세히 |
|---|---|---|---|
| **Canary** (Stack Protector) | 스택 버퍼 오버플로우로 리턴 주소를 덮어쓰는 것 | 함수 프롤로그/에필로그에 카나리 체크 코드가 추가로 보임, `__stack_chk_fail` import 확인 가능 | (본문 참고) |
| **NX** (No-eXecute, DEP) | 스택/힙 등 데이터 영역에 셸코드를 심어 실행하는 것 | 데이터 영역 실행이 막히므로 셸코드 injection 대신 ROP 등 코드 재사용 기법이 필요해짐 | (본문 참고) |
| **PIE** (Position Independent Executable) | 실행 파일 자신의 주소를 예측해 하드코딩하는 것 | IDA 주소가 실제 실행 주소가 아니라 오프셋이 됨 | `./rev-0103-pie.md` |
| **RELRO** (RELocation Read-Only) | GOT를 덮어써서 함수 호출을 가로채는 것 | Full이면 GOT가 프로그램 시작부터 읽기 전용, lazy binding 사라짐 | `./rev-0102-relro.md` |

이 네 가지는 서로 독립적인 컴파일 옵션이며, 어떤 조합이든 나올 수 있다. ASLR(REV-0104)은 커널 기능이라 `checksec`이 바이너리 자체에서는 보여주지 않지만, PIE와 짝을 이뤄 실질적인 보호 효과를 만든다는 점에서 항상 같이 고려해야 한다.

### Canary(스택 카나리) 자세히
`gcc`가 스택 버퍼를 쓰는 함수를 컴파일할 때, 로컬 버퍼와 저장된 레지스터/리턴 주소 사이에 무작위 값(카나리)을 하나 심어두고, 함수가 끝나기 직전(에필로그)에 그 값이 아직 그대로인지 검사한다. 만약 버퍼 오버플로우로 리턴 주소까지 덮어썼다면 카나리 값도 함께 깨졌을 가능성이 높으므로, 값이 달라졌으면 `__stack_chk_fail`을 호출해 프로그램을 즉시 강제 종료시킨다.

리버싱 관점에서 카나리가 있는 함수는 프롤로그에서 `mov rax, fs:0x28`(TLS의 카나리 값을 읽어 스택에 저장) 같은 코드가, 에필로그 직전에는 그 값을 다시 읽어 비교하는 `xor` + `jz`(또는 `je`) + `call __stack_chk_fail` 패턴이 함께 보인다. IDA 디컴파일러는 이 패턴을 자동으로 인식해서 의사코드에서 아예 생략하거나 `__stack_chk_fail` 호출로 간단히 보여주기도 한다. `checksec` 결과의 `Canary found`는 이 코드가 최소 한 함수 이상에 존재한다는 뜻이고, `No canary found`는 스택 버퍼 오버플로우에 대한 이 방어선이 아예 없다는 뜻이다.

### NX(실행 방지) 자세히
과거에는 스택이나 힙 같은 데이터 영역도 실행 권한을 가질 수 있어서, 공격자가 버퍼에 셸코드를 직접 넣고 그쪽으로 실행 흐름을 돌리는 공격(고전적인 스택 스매싱)이 통했다. NX(하드웨어의 DEP, Data Execution Prevention 지원을 이용)가 켜지면 데이터 영역에는 실행 권한(`x`)이 아예 부여되지 않아, 그런 셸코드 injection이 원천적으로 막힌다. `readelf -l`로 프로그램 헤더를 보면 `GNU_STACK` 세그먼트의 권한 플래그에 `E`(실행)가 없으면 NX가 켜진 것이다. 요즘 배포판에서는 사실상 항상 켜져 있다고 봐도 무방하다. 리버싱에서는 "이 바이너리는 스택에 셸코드를 심는 방식이 아니라 ROP/ret2libc 같은 기존 코드 재사용 방식으로 접근해야 한다"는 신호로 읽으면 된다.

### PIE와 RELRO는 각각 별도 문서에서
PIE는 주소 계산과 브레이크포인트 설정 방식 자체를 바꿔놓기 때문에 분량이 많아 `./rev-0103-pie.md`에서 깊게 다루고, RELRO는 GOT 조작 가능 여부를 결정하기 때문에 `./rev-0102-relro.md`에서 깊게 다룬다. 이 글에서는 넷을 조합했을 때 분석 전략이 어떻게 달라지는지에 집중한다.

### 네 가지 조합이 분석 전략을 바꾸는 예
- **전부 꺼짐(No Canary / NX disabled / No PIE / No RELRO)**: 오래된 스타일이거나 일부러 취약하게 만든 CTF 문제. 스택에 셸코드를 직접 심고 고정 주소로 점프하는 가장 고전적인 접근이 통할 가능성이 높다. 주소도 고정이라 분석이 가장 쉽다.
- **Canary + NX만 켜짐, PIE/RELRO 꺼짐**: 스택 버퍼 오버플로우로 셸코드를 직접 실행할 수는 없지만(NX), 카나리를 우회/leak하지 못하면 리턴 주소 자체를 못 덮어쓴다. 주소는 고정이므로 ROP 체인을 짜기는 비교적 쉽다.
- **전부 켜짐(Full RELRO + PIE + NX + Canary)**: 요즘 배포판 기본 컴파일 옵션에 가깝다. GOT 조작 불가(Full RELRO), 셸코드 직접 실행 불가(NX), 카나리 없이는 리턴 주소 컨트롤 불가, 주소는 매 실행 랜덤(PIE+ASLR). 정보 유출(leak)로 카나리 값과 베이스 주소를 먼저 알아내는 것이 거의 필수적인 첫 단계가 된다.
- **Partial RELRO + PIE + NX + Canary** (실무에서 가장 흔한 기본 조합): GOT 자체는 여전히 쓰기 가능하므로(REV-0102), 임의 쓰기 취약점만 있다면 GOT overwrite가 여전히 유효한 공격 경로로 남는다.

### 순수 리버싱(익스플로잇이 아닌) 관점에서의 의미
이 문서는 pwn 관점의 설명이 많이 섞여 있지만, 순수하게 "코드를 읽고 이해"하는 리버싱에서도 이 네 가지를 미리 파악해두면 이득이 크다.
- Canary가 있으면 디컴파일된 코드에 나타나는 카나리 체크/`__stack_chk_fail` 관련 코드를 "핵심 로직이 아닌 부수 코드"로 걸러내고 읽을 수 있다.
- PIE가 있으면 정적 분석 중에 보는 주소가 오프셋임을 항상 의식하고 GDB와 대조한다.
- RELRO 상태를 보면 GOT가 실행 중 바뀔 수 있는 값인지 아닌지 미리 판단해, 안티 디버깅/자기 수정 코드 여부를 헷갈리지 않는다.

## 화면/코드에서 보이는 징후
- `checksec` 표에 네 항목이 색상과 함께 한 줄로 요약되어 출력됨
- 디컴파일된 함수 시작/끝에 카나리 관련 코드(`__stack_chk_fail`, `fs:0x28`)가 반복적으로 나타남
- `readelf -l` 결과에 `GNU_STACK` 세그먼트가 있고 권한이 `RW`(NX 켜짐, 실행 권한 없음)인지 `RWE`(NX 꺼짐)인지로 구분됨

## 가장 먼저 할 것
새 바이너리를 받으면 다른 무엇보다 먼저 `checksec ./chall`을 실행해 네 항목을 표로 확인하고, 그 결과를 메모(또는 CTF writeup 상단)에 남겨둔다. 이후 모든 분석 단계에서 이 표를 계속 참고하며 "이 취약점이 이 보호 기법 조합에서 실제로 통하는가"를 검증하는 습관을 들인다.

## 단계별 절차

**1) checksec 실행**
```bash
checksec --file=./chall
```

**2) 각 항목을 직접 원시 정보로 재확인(신뢰도 검증용)**
```bash
readelf -h ./chall | grep Type          # ET_EXEC(No PIE) vs ET_DYN(PIE)
readelf -l ./chall | grep -A1 GNU_STACK # NX
readelf -l ./chall | grep GNU_RELRO     # RELRO
readelf --dyn-syms ./chall | grep stack_chk # Canary
```

**3) GDB/Pwndbg 안에서 실시간 확인**
```gdb
checksec
```
Pwndbg가 설치돼 있으면 GDB 프롬프트에서 바로 같은 요약을 볼 수 있어 파일 시스템을 오가지 않아도 된다.

**4) 조합에 따라 분석 우선순위 정하기**
- PIE enabled → 먼저 `./rev-0103-pie.md` 방식으로 베이스 계산 워크플로를 세팅.
- Full RELRO → GOT 변조 시나리오는 배제, 다른 데이터 타겟 검토.
- Canary found → 함수 프롤로그의 카나리 저장 코드를 핵심 로직과 구분해서 읽기.
- NX enabled(거의 항상) → 셸코드 직접 실행이 아닌 코드 재사용 관점으로 접근.

## 명령어/단축키
```bash
checksec --file=./chall
readelf -h ./chall
readelf -l ./chall
readelf --dyn-syms ./chall
```
GDB/Pwndbg: `checksec`

## 출력 해석
`checksec` 표 예시(pwntools 스타일):
```
RELRO           STACK CANARY      NX            PIE
Partial RELRO   Canary found      NX enabled    PIE enabled
```
- `RELRO`: `No RELRO` < `Partial RELRO` < `Full RELRO` 순으로 보호가 강해짐.
- `STACK CANARY`: `Canary found` / `No canary found`.
- `NX`: `NX enabled`(데이터 실행 불가) / `NX disabled`.
- `PIE`: `PIE enabled` / `No PIE (0x400000)`처럼 고정 베이스 주소가 함께 표시되기도 함.

## 흔한 실수
- 보호 기법이 다 켜져 있으면 "취약점이 없다"고 오해하는 것 — 보호 기법은 특정 공격 기법을 어렵게 만들 뿐, 로직 자체의 버그(인증 우회, 정수 오버플로우 등)와는 무관하다. 순수 리버싱 문제라면 보호 기법과 무관하게 알고리즘을 읽어야 한다.
- 네 항목을 따로따로만 이해하고 조합해서 생각하지 않는 것 — 예를 들어 Partial RELRO는 PIE 여부와 상관없이 GOT가 쓰기 가능하다는 사실이 바뀌지 않는다.
- `checksec` 결과를 한 번만 보고 끝내는 것 — 분석 중간에 카나리 체크 코드를 발견하면 그때마다 처음 확인한 `checksec` 결과와 일치하는지 다시 대조하는 습관이 실수를 줄여준다.

## 막혔을 때 다음 체크
- PIE 하나만 깊게 → REV-0103 PIE와 주소 계산
- ASLR과의 관계 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유
- RELRO/GOT 하나만 깊게 → REV-0102 RELRO가 리버싱에 의미하는 것, REV-0100 PLT와 GOT 기초

## 미니 예제
```bash
$ checksec --file=./chall
[*] './chall'
    Arch:     amd64-64-little
    RELRO:    Full RELRO
    Stack:    Canary found
    NX:       NX enabled
    PIE:      PIE enabled
```
이 결과만 보고도 "GOT 조작 불가, 스택에 셸코드 직접 실행 불가, 카나리 없이 리턴 주소 컨트롤 불가, 주소는 매 실행 랜덤"이라는 네 가지 제약을 즉시 정리할 수 있다.

## 관련 글
- REV-0100 — PLT와 GOT 기초
- REV-0102 — RELRO가 리버싱에 의미하는 것
- REV-0103 — PIE와 주소 계산
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유

## 출처/검증
- 스택 카나리(`-fstack-protector`) 동작: GCC 공식 문서(`-fstack-protector`, `-fstack-protector-strong`) 기준.
- NX/`GNU_STACK` 세그먼트: ELF 프로그램 헤더 명세 및 리눅스 실행 가능 스택 보호(`execstack`) 관련 문서 기준.
- `checksec` 출력 항목: pwntools `checksec`/`checksec.sh` 공식 도구 문서 기준 (2026-09-08 검증).
