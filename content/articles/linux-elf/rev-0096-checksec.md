---
id: REV-0096
title: "checksec 결과 읽는 법"
slug: "rev-0096-checksec"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["checksec", "readelf", "binutils"]
keywords: ["checksec", "RELRO", "Stack Canary", "NX", "PIE", "Fortify", "바이너리 보호 기법"]
aliases: ["checksec 사용법", "checksec 결과", "checksec 옵션", "바이너리 보호 확인"]
symptom_keywords: ["checksec 결과 해석이 안됨", "canary 있는지 없는지 확인하고 싶음", "nx pie relro가 뭔지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`checksec`은 ELF 바이너리에 어떤 보호 기법(RELRO, Stack Canary, NX, PIE, Fortify)이 적용되어 있는지 한 줄 표로 요약해주는 스크립트로, pwn/CTF에서 공격 전략(어떤 취약점이 쓸모 있을지)을 정하기 전에 항상 먼저 실행하는 명령이다.

## 언제 검색해야 하나
- pwn 계열 문제를 받았을 때, 어떤 종류의 공격(스택 오버플로우, GOT overwrite 등)이 가능한지 미리 가늠하고 싶을 때
- `RELRO`, `Canary`, `NX`, `PIE` 같은 용어가 정확히 뭘 막는 건지 헷갈릴 때
- checksec 결과의 `Partial RELRO`와 `Full RELRO` 차이, `No canary found`와 `Canary found`가 리버싱/디버깅에 어떤 영향을 주는지 알고 싶을 때

## 핵심 개념
`checksec`은 새로운 정보를 만들어내는 도구가 아니다 — ELF 헤더, Program Header, `.dynamic` 섹션에 이미 있는 정보(REV-0089, REV-0090 참고)를 조합해서 "이 바이너리에 어떤 보호 기법이 켜져 있는가"를 사람이 보기 쉽게 정리해줄 뿐이다. 즉 `readelf`만으로도 같은 정보를 얻을 수 있지만, `checksec`은 그걸 대신 판독해서 한 줄로 요약해준다.

### 5가지 핵심 항목

**RELRO (RELocation Read-Only)** — GOT(REV-0100 참고)를 공격으로부터 보호하는 정도.
- `No RELRO`: GOT가 항상 쓰기 가능. 가장 취약.
- `Partial RELRO`: `.got`(비함수용)은 읽기전용이 되지만 `.got.plt`(함수용, lazy binding에 필요)는 여전히 쓰기 가능.
- `Full RELRO`: 프로그램 시작 시 모든 GOT 엔트리를 즉시 채우고(eager binding) GOT 전체를 읽기 전용으로 만듦. GOT overwrite 공격이 원천 차단됨.

**Stack Canary** — 스택 버퍼 오버플로우로 리턴 주소를 덮어쓰기 전에 먼저 덮이는 위치에 임의의 값(카나리)을 심어두고, 함수 리턴 직전에 그 값이 바뀌었는지 검사하는 기법.
- `Canary found`: 함수 프롤로그에 `mov rax, fs:0x28`처럼 카나리를 스택에 심는 코드가 있고, 에필로그에 `cmp`/`jne __stack_chk_fail`로 검사하는 코드가 있음.
- `No canary found`: 이런 코드가 없음 — 스택 버퍼 오버플로우로 리턴 주소를 직접 덮어쓰기가 상대적으로 쉬움.

**NX (No-eXecute, 실행 방지 스택/힙)**
- `NX enabled`: 스택/힙 영역이 실행 불가능(W^X) — 셸코드를 스택에 넣고 바로 점프해서 실행하는 전통적 공격이 막힘. Program Header의 `GNU_STACK` 세그먼트에 `E`(실행) 플래그가 없으면 이 상태.
- `NX disabled`: 스택이 실행 가능 — 셸코드 인젝션 공격이 가능.

**PIE (Position-Independent Executable)**
- `PIE enabled`: ELF 헤더 `Type: DYN`(REV-0089 참고), 실행할 때마다 로드 베이스 주소가 ASLR로 랜덤화됨. 코드/함수 주소를 미리 하드코딩해서 공격할 수 없고, 먼저 주소 하나를 leak해야 함.
- `No PIE` (`Type: EXEC`): 항상 같은 고정 주소에 로드됨 — 정적 분석에서 본 주소를 그대로 익스플로잇에 쓸 수 있음.

**Fortify (FORTIFY_SOURCE)**
- `Fortified`: `strcpy` 대신 `__strcpy_chk`처럼, 버퍼 크기를 알 때 이를 검사하는 안전한 libc 함수로 컴파일 시 자동 치환됨.
- Fortify 관련 함수(`__printf_chk`, `__memcpy_chk` 등)가 심볼에 보이면 이 보호가 켜진 것.

## 화면/코드에서 보이는 징후
pwn 문제를 받으면 소스 코드보다 먼저 `checksec` 결과부터 확인하는 게 관례다. 보호 기법 조합이 문제의 의도된 공격 기법을 암시하는 경우가 많다(예: `No canary`+`No PIE`면 전형적인 스택 버퍼 오버플로우로 리턴 주소 직접 덮어쓰기 문제일 확률이 높음).

## 가장 먼저 할 것
```bash
checksec --file=./chall
```
결과 5줄을 보고 이 바이너리에서 어떤 공격이 배제되고 어떤 공격이 여전히 가능한지 먼저 머릿속으로 정리한다.

## 단계별 절차

**1) 설치 확인 및 기본 실행**
```bash
checksec --file=./chall
```
`checksec`이 없다면 `pwntools`를 설치하면 같이 딸려오는 `pwn checksec` 명령을 쓸 수도 있다:
```bash
pwn checksec ./chall
```

**2) 결과 해석**

출력 예:
```
RELRO           STACK CANARY      NX            PIE             RPATH      RUNPATH      Symbols
Full RELRO      Canary found      NX enabled    PIE enabled     No RPATH   No RUNPATH   66 Symbols
```

**3) checksec 없이 readelf만으로 직접 확인 (checksec을 못 쓰는 환경)**
```bash
# RELRO 확인
readelf -l ./chall | grep GNU_RELRO      # 있으면 최소 Partial RELRO
readelf -d ./chall | grep BIND_NOW       # 있으면 Full RELRO

# NX 확인
readelf -l ./chall | grep GNU_STACK      # 이 줄의 플래그에 E가 없으면 NX enabled

# PIE 확인
readelf -h ./chall | grep Type            # DYN이면 PIE, EXEC면 No PIE

# Canary 확인 (심볼이 남아있을 때)
nm ./chall | grep stack_chk
```

**4) 동적 라이브러리(libc)에도 checksec 적용 가능**
```bash
checksec --file=./libc.so.6
```
pwn 문제에서 제공된 libc 버전 자체의 보호 기법도 확인할 때 사용.

## 명령어/단축키
```bash
checksec --file=./chall
pwn checksec ./chall
readelf -l ./chall | grep -E 'GNU_RELRO|GNU_STACK'
readelf -d ./chall | grep BIND_NOW
```

## 출력 해석
- `Partial RELRO` + `No canary`: 가장 자주 보는 CTF 초급 pwn 설정 — 스택 오버플로우와 GOT overwrite 둘 다 시도해볼 수 있음.
- `Full RELRO`: GOT overwrite 계열 공격은 포기하고 다른 접근(스택, 힙, 포맷 스트링의 다른 활용법)을 찾아야 함.
- `No PIE`: 정적 분석에서 확인한 함수 주소를 그대로 익스플로잇 스크립트에 하드코딩해도 됨 — 리버싱 관점에서도 GDB 실행 중 주소와 IDA 정적 주소가 항상 일치해서 분석이 더 쉬움.
- `PIE enabled`: 주소 leak이 선행되어야 함. 리버싱 중 GDB로 확인한 주소는 매 실행마다 다르므로, 오프셋(ASLR 베이스와의 차이)으로 환산해서 기록해야 한다.

## 흔한 실수
- `Canary found`를 보고 "이 함수는 스택 오버플로우가 절대 불가능하다"고 오해하는 것 — 카나리는 **리턴 주소를 덮어쓰기 전에 검사**하는 것뿐이라, 카나리 자체를 먼저 leak하거나, 카나리를 건드리지 않는 다른 변수(함수 포인터 등)만 덮는 오버플로우는 여전히 가능하다.
- `NX enabled`를 보고 셸코드 공격이 완전히 불가능하다고 단정하는 것 — ROP(Return-Oriented Programming)로 NX를 우회하는 기법이 존재한다(이 저장소의 pwn 관련 별도 문서 참고).
- checksec 결과만 보고 소스/디스어셈블리 분석을 건너뛰는 것 — checksec은 "가능성의 지도"일 뿐, 실제 취약점이 어디 있는지는 코드를 읽어야 안다.

## 막혔을 때 다음 체크
- RELRO와 GOT의 관계를 더 깊이 알고 싶으면 → [REV-0100 PLT와 GOT 기초](./rev-0100-plt-got.md)
- PIE/ASLR이 주소 분석에 미치는 영향이 궁금하면 → [REV-0089 ELF 헤더 읽는 법](./rev-0089-elf-header.md)의 `e_type` 설명
- Program Header의 `GNU_STACK`, `GNU_RELRO` 세그먼트 구조가 궁금하면 → [REV-0090 ELF Program Header와 Section Header 차이](./rev-0090-program-vs-section-header.md)

## 미니 예제
```bash
$ checksec --file=chall
RELRO           STACK CANARY      NX            PIE             RPATH      RUNPATH      Symbols
Partial RELRO   No canary found   NX enabled    No PIE          No RPATH   No RUNPATH   66 Symbols
```
이 결과만 보고도 "카나리가 없으니 스택 버퍼 오버플로우로 리턴 주소를 직접 덮어쓸 수 있고, No PIE라서 함수 주소가 고정이니 리턴 주소를 원하는 함수로 바로 조작할 수 있겠다"는 공격 가설을 코드를 읽기 전에 세울 수 있다.

## 관련 글
- [REV-0089 — ELF 헤더 읽는 법](./rev-0089-elf-header.md)
- [REV-0090 — ELF Program Header와 Section Header 차이](./rev-0090-program-vs-section-header.md)
- [REV-0100 — PLT와 GOT 기초](./rev-0100-plt-got.md)

## 출처/검증
- checksec 판정 기준(RELRO/Canary/NX/PIE): `checksec.sh`(Trail of Bits/slimm609 계열) 공식 스크립트 로직 및 pwntools `checksec` 구현 기준 (2026-09-08 검증).
- RELRO 개념: Red Hat/Fedora "Full/Partial RELRO" 공식 설명 기준.
- Stack Canary(`__stack_chk_fail`): glibc `__stack_chk_fail` 구현 개념 기준.
