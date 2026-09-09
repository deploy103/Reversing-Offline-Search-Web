---
id: REV-0694
title: "GDB에서 스택 프레임이 corrupted stack frame이라고 나올 때"
slug: "rev-0694-gdb-corrupted-stack-frame"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB]
keywords: ["corrupted stack frame", "previous frame inner to this frame", "GDB 스택 언와인딩 실패", "bt full"]
aliases: ["gdb backtrace corrupt stack", "previous frame identical to this frame", "gdb 콜스택이 깨져 보임"]
symptom_keywords: ["bt 했더니 corrupt stack이라고 뜸", "backtrace stopped previous frame inner to this frame", "스택 오버플로우 후 콜스택이 이상하게 나옴"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
GDB가 `bt`(backtrace) 실행 중 `Backtrace stopped: previous frame inner to this frame (corrupt stack?)`를 출력한다면, 실제로 스택 버퍼 오버플로우 등으로 저장된 반환 주소/이전 프레임 포인터(RBP)가 덮여 GDB의 스택 언와인딩(unwinding) 알고리즘이 스스로 모순을 감지했다는 뜻이며, 이는 GDB의 버그가 아니라 스택이 실제로 깨졌음을 알려주는 중요한 신호다.

## 언제 검색해야 하나
- `bt` 명령을 쳤는데 정상적인 함수 호출 목록 대신 `Backtrace stopped: previous frame inner to this frame (corrupt stack?)` 문구가 뜰 때
- 스택 버퍼 오버플로우 취약점을 테스트하는 도중 백트레이스가 갑자기 이상하게 잘려 보일 때
- 최적화 옵션(`-O2` 등)으로 컴파일되어 프레임 포인터가 생략된 바이너리를 분석 중일 때
- `previous frame identical to this frame`처럼 비슷한 다른 경고 문구를 봤을 때

## 핵심 개념
GDB는 콜스택을 추적할 때 각 스택 프레임의 저장된 RBP(프레임 포인터)와 반환 주소를 순서대로 따라간다. 정상적인 상황에서는 각 프레임이 이전 프레임보다 항상 스택의 더 높은 주소(더 바깥쪽)에 위치해야 한다. 그런데 다음과 같은 경우 이 가정이 깨진다.
1. **스택 버퍼 오버플로우로 저장된 RBP/반환 주소가 실제로 덮어써진 경우**: 공격 대상 취약점을 테스트 중이라면 이 메시지 자체가 오버플로우가 실제로 스택 메타데이터까지 침범했다는 증거다.
2. **프레임 포인터 생략 최적화(`-fomit-frame-pointer`, 기본적으로 `-O1` 이상에서 활성화되는 경우가 많음)로 컴파일된 코드**: RBP가 프레임 포인터로 안 쓰이고 범용 레지스터로 재활용되면, GDB가 이를 프레임 포인터로 착각해서 스택을 잘못 해석하고 언와인딩에 실패할 수 있다.
3. **디버그 정보(CFI, Call Frame Information)가 없는 스트립된 바이너리**: 최신 GDB는 프레임 포인터가 없어도 `.eh_frame`의 CFI를 이용해 언와인딩할 수 있지만, 이 정보 자체가 없거나 손상되면 실패한다.

GDB는 이런 모순을 발견하면 잘못된 정보를 억지로 이어붙이는 대신 안전하게 언와인딩을 중단하고 이 경고를 낸다 — 즉 "GDB가 고장났다"가 아니라 "GDB가 스택이 신뢰할 수 없다고 정확히 판단했다"는 뜻이다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) bt
#0  0x0000000000401234 in vuln_func ()
#1  0x4141414141414141 in ?? ()
Backtrace stopped: previous frame inner to this frame (corrupt stack?)
```
또는 반환 주소 부분이 `0x4141414141414141`처럼 명백히 입력값(`AAAAAAAA`)으로 덮인 패턴으로 보이는 경우도 흔하다.

## 가장 먼저 할 것
`bt full`로 각 프레임의 지역 변수까지 함께 확인하고, `x/20gx $rsp`로 스택 내용을 직접 훑어 어디부터 값이 이상해지는지 눈으로 확인한다.

## 단계별 절차
1. `bt full`로 프레임별 지역 변수까지 포함해서 다시 확인 — 일반 `bt`보다 정보가 많아 어디서부터 꼬였는지 파악에 도움된다
2. `info frame`으로 현재 프레임의 저장된 반환 주소, 프레임 포인터 값을 직접 확인
3. `x/40gx $rsp`로 스택 메모리를 직접 덤프해서 반환 주소로 보이는 값이 어떻게 덮였는지(예: `0x4141414141414141`처럼 입력 문자로 덮였는지) 확인
4. 이것이 익스플로잇 대상 취약점 테스트 중이라면, 스택이 깨진 것 자체가 원하는 결과 — 정확히 몇 바이트째부터 반환 주소가 덮이는지 오프셋을 계산하는 다음 단계로 넘어간다
5. 의도치 않은 최적화/프레임 포인터 생략이 원인으로 의심되면, 자신이 컴파일한 코드라면 `-fno-omit-frame-pointer`를 붙여 다시 빌드해서 비교
6. 여전히 언와인딩이 안 되면 Pwndbg 등 확장이 제공하는 좀 더 관용적인 백트레이스/스택 탐색 기능(`stack`, `telescope $rsp`)으로 raw 메모리를 직접 훑는 방식으로 전환

## 명령어/단축키
```gdb
bt
bt full
info frame
x/40gx $rsp
info registers rbp rsp rip
```
Pwndbg:
```
stack 40
telescope $rsp 40
```

## 출력 해석
`x/40gx $rsp` 결과에서 `0x4141414141414141`, `0x4242424242424242`처럼 특정 패턴 문자가 반복되는 8바이트 값이 보이면, 그 위치가 입력값으로 덮인 지점이다. 그 값이 저장된 RBP나 반환 주소 자리와 일치한다면, 정확히 그 오프셋에서부터 스택 메타데이터가 덮이기 시작했다는 뜻이며, 이는 버퍼 오버플로우 취약점의 정확한 오프셋을 계산하는 데 직접 쓰이는 정보다.

## 흔한 실수
- `corrupted stack frame` 경고를 GDB 자체의 오류/버그로 오해해서 GDB를 재설치하거나 다른 버전을 찾아 헤매는 것 — 대부분 실제로 스택이 손상된 것이다.
- 이 메시지가 뜨면 그냥 `bt`를 포기하고 넘어가는 것 — `bt full`, `x/gx $rsp`로 직접 스택을 보면 오히려 취약점 분석에 유용한 정보를 얻을 수 있다.
- 최적화 빌드에서 프레임 포인터가 원래 생략된다는 사실을 모르고, 정상적인(공격받지 않은) 상황에서도 이 메시지가 나올 수 있다는 걸 감안하지 않는 것.
- 패턴 문자(cyclic pattern 등)를 쓰지 않고 단순 `AAAA...`만 넣어서, 정확히 몇 바이트째에서 덮였는지 애매하게 추정하는 것 — pwntools의 `cyclic()`/`cyclic_find()` 같은 도구로 정확한 오프셋을 구하는 편이 훨씬 정확하다.

## 막혔을 때 다음 체크
- 백트레이스가 아예 `??`로만 나와서 함수 이름조차 안 보인다면 → REV-0695 GDB backtrace가 ??로만 나와서 콜스택을 못 볼 때
- Core dump로 크래시 시점을 사후 분석하는 방법이 궁금하면 → REV-0113 Core dump와 크래시 지점 분석 기초
- 스택 카나리/보호기법 전반이 궁금하면 → REV-0105 Canary NX PIE RELRO 한 번에 이해

## 미니 예제
```gdb
(gdb) run < payload.txt
Program received signal SIGSEGV, Segmentation fault.
0x0000000000401234 in vuln_func ()
(gdb) bt
#0  0x0000000000401234 in vuln_func ()
Backtrace stopped: previous frame inner to this frame (corrupt stack?)
(gdb) x/6gx $rsp
0x7fffffffe4d0: 0x4141414141414141      0x4141414141414141
0x7fffffffe4e0: 0x4141414141414141      0x0000000000401256
```
저장된 RBP 자리(`0x4141414141414141`)가 입력 문자로 완전히 덮여 있어 GDB가 언와인딩을 포기했다. 그 아래 원래 반환 주소로 보이는 `0x0000000000401256`은 아직 살아있어, 정확히 어느 오프셋까지가 RBP이고 어디부터 반환 주소인지 계산할 수 있는 단서가 된다.

## 관련 글
- REV-0695 — GDB backtrace가 ??로만 나와서 콜스택을 못 볼 때
- REV-0113 — Core dump와 크래시 지점 분석 기초
- REV-0105 — Canary NX PIE RELRO 한 번에 이해

## 출처/검증
- GDB의 스택 언와인딩(프레임 포인터 체인 및 CFI 기반) 방식과 "corrupt stack" 판정 조건: GDB 공식 문서("Backtrace") 기준.
- `-fomit-frame-pointer` 최적화가 프레임 포인터 기반 언와인딩에 미치는 영향: GCC 공식 문서(최적화 옵션) 기준 (2026-09-09 검증).
