---
id: REV-0419
title: "CLD와 STD: 방향 플래그와 문자열 명령 방향"
slug: "rev-0419-cld-std"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - cld
  - std
  - CLD
  - STD
  - cld 명령어
  - std 명령어
  - direction flag
  - 방향 플래그
  - DF 플래그
  - forward copy
  - backward copy
  - 정방향 복사
  - 역방향 복사
  - rep movsb
  - string instruction direction
  - 문자열 명령 방향
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - cld 뭐임
  - std가 뭐죠
  - 방향 플래그 초기화
  - DF 세우기
  - DF 지우기
symptom_keywords:
  - rep movsb 앞에 cld가 왜 있는지 모르겠음
  - std 다음에 rep movsb가 나오는데 뭔지 모르겠음
  - 문자열 복사가 거꾸로 되는 것 같음
  - 함수 호출 후 이상하게 동작하는데 std 때문인 것 같음
  - esi edi가 감소하는 이유를 모르겠음
---

## 한 줄 요약
`CLD`/`STD`는 방향 플래그(DF)를 각각 0/1로 설정해, 이후 실행되는 `MOVS`/`STOS`/`LODS`/`SCAS`/`CMPS` 같은 문자열 명령이 `ESI`/`EDI`(또는 `RSI`/`RDI`)를 매 반복마다 증가(정방향)시킬지 감소(역방향)시킬지를 결정한다.

## 언제 검색해야 하나
- `rep movsb`, `rep stosb` 같은 문자열 반복 명령 바로 앞에 `cld`가 붙어 있는 이유가 궁금할 때
- `std`가 나온 뒤 포인터 레지스터(`RSI`/`RDI`)가 감소하는 이유를 모를 때
- 함수가 끝난 뒤 다른 라이브러리 함수(memcpy 등)가 이상하게 동작하는데 원인이 DF 상태 같을 때
- memmove의 backward copy(겹치는 영역 복사) 구현을 리버싱할 때

## 핵심 개념

### DF가 무엇을 제어하는가
`DF`(Direction Flag)는 EFLAGS의 10번 비트다. 문자열 처리 명령(`MOVS`, `STOS`, `LODS`, `SCAS`, `CMPS`, 그리고 이들에 `REP`류 접두사가 붙은 형태)이 실행될 때마다, 관련된 인덱스 레지스터(`ESI`/`EDI`, 64비트에서는 `RSI`/`RDI`)를 자동으로 증감시킨다.
- `DF = 0` (`CLD`로 설정): 매 반복마다 **증가** — 메모리 앞쪽에서 뒤쪽으로 진행(정방향).
- `DF = 1` (`STD`로 설정): 매 반복마다 **감소** — 메모리 뒤쪽에서 앞쪽으로 진행(역방향).

증감 크기는 오퍼랜드 크기에 따라 다르다 — 바이트 단위(`MOVSB`)면 ±1, 워드(`MOVSW`)면 ±2, 더블워드(`MOVSD`)면 ±4, 쿼드워드(`MOVSQ`)면 ±8.

### CLD/STD 자체의 효과
- `CLD`: `DF = 0`. `STD`: `DF = 1`. 오퍼랜드 없음.
- 이 둘은 **DF 외의 다른 플래그를 전혀 건드리지 않는다** (CF, ZF, SF, OF, PF, AF 모두 그대로).
- 범용 레지스터/메모리에 직접 영향 없음. 스택/RIP 변화도 없음(RIP는 1바이트만큼 증가).
- 이후에 실행되는 문자열 명령들의 "방향"만 결정한다는 점에서, 직접적인 효과보다는 **후속 명령의 동작 방식을 설정**하는 역할이다.

### 왜 STD가 필요한가: 겹치는 메모리 복사
`memcpy`는 원본과 대상이 겹치지 않는다고 가정하지만, `memmove`는 겹치는 경우도 안전하게 처리해야 한다. 대상 주소가 원본보다 **뒤쪽**에 있고 두 영역이 겹친다면, 앞에서부터 복사하면 아직 읽지 않은 원본 데이터를 미리 덮어써버리는 문제가 생긴다. 이럴 때 **뒤에서부터** 복사하면(`STD` + 끝 주소부터 시작) 안전하다.
```asm
; dest > src 이고 겹치는 경우, 뒤에서부터 복사
std
lea  rdi, [dest+len-1]
lea  rsi, [src+len-1]
mov  rcx, len
rep  movsb
cld                    ; 반드시 원상복구!
```

### ABI 규약: 함수 경계에서는 항상 DF=0
Windows x64와 SysV AMD64 ABI 모두, **함수 호출 시점과 반환 시점에 DF는 반드시 0(clear)이어야 한다**는 규약이 있다. 즉 어떤 함수가 내부적으로 `STD`를 써서 역방향 복사를 했다면, 그 함수가 반환하기 전에 반드시 `CLD`로 DF를 원상복구해야 한다. 이걸 빠뜨리면 그 함수를 호출한 쪽이나 이후에 실행되는 CRT/라이브러리 함수(내부적으로 `rep movs`류를 쓰는 `memcpy` 등)가 방향을 착각해 메모리를 잘못된 방향으로 읽고 써서 크래시나 데이터 손상을 일으킬 수 있다.

## 화면/코드에서 보이는 징후
```asm
cld
mov  rdi, dest
mov  rsi, src
mov  rcx, len
rep  movsb
```
```asm
std
lea  rdi, [dest+len-1]
lea  rsi, [src+len-1]
mov  rcx, len
rep  movsb
cld
```
`REP` 계열 명령 바로 앞에 `CLD`나 `STD`가 붙어 있는 패턴이 전형적이다. 함수 시작부에 `CLD`만 있고 `STD`가 전혀 없다면 그 함수는 항상 정방향으로만 문자열 명령을 쓴다는 뜻이다.

## 가장 먼저 할 것
1. `CLD`인지 `STD`인지부터 확인해 이후 `REP` 블록이 정방향인지 역방향인지 판단한다.
2. `STD`가 있다면 그 뒤 어딘가에 `CLD`로 복원하는 코드가 있는지 반드시 찾아본다 — 없다면 ABI 위반 버그이거나 의도적인 안티분석 트릭일 수 있다.
3. `RDI`/`RSI` 초기값이 버퍼의 시작 주소인지 끝 주소(`+len-1`)인지 확인해 방향과 앞뒤가 맞는지 검증한다.

## 단계별 절차
1. `CLD`/`STD` 위치를 찾는다.
2. 뒤따르는 `MOV RDI, ...` / `MOV RSI, ...` / `LEA` 값이 버퍼의 시작인지 끝인지 확인한다 — `STD`인데 시작 주소를 쓰면 역방향으로 진행하면서 버퍼 밖으로 벗어나는 버그가 될 수 있다.
3. `REP` 계열 명령(`REV-0080` 참고)이 몇 바이트/워드 단위로 반복되는지 `RCX` 초기값으로 확인한다.
4. 함수 끝까지 `STD` 이후 `CLD`로 복원되는지 추적한다.

## 명령어/단축키
- IDA/Ghidra: `rep movsb`와 `cld`가 함께 있으면 대개 `memcpy()` 호출로 인식/재구성되고, `std` + `rep movsb` + `cld` 조합은 역방향 복사 루프로 표시되거나 raw 명령으로 남는다.
- GDB/x64dbg: EFLAGS 창에서 `DF` 비트(비트 10)를 직접 확인할 수 있다.

## 출력 해석
- 디버거 레지스터/플래그 창에서 `DF=1`로 표시되면 역방향 모드, `DF=0`이면 정방향 모드다.
- `RSI`/`RDI` 값을 반복(step) 실행하면서 관찰하면 실제로 증가하는지 감소하는지 눈으로 확인할 수 있다.

## 흔한 실수
- `STD`를 "start"의 약자로 착각하는 것 — 실제로는 "Set Direction flag"다.
- DF가 `ESI`/`EDI`의 증감 방향만 바꾼다는 것을 모르고, 루프 반복 횟수(`RCX`)나 비교 로직까지 바뀐다고 오해하는 것 — `RCX`는 여전히 매 반복 1씩 감소하며 0이 되면 멈춘다(REV-0080 참고). 바뀌는 건 오직 `RSI`/`RDI`의 증감 부호뿐이다.
- `STD` 이후 `CLD`로 복원하지 않아, 그 함수를 호출한 코드나 CRT 함수가 오작동하는 것을 디버깅할 때 원인을 못 찾는 것 — ABI가 DF=0을 요구한다는 사실 자체를 모르면 이 버그의 원인을 영영 못 찾는다.
- 정방향/역방향과 무관하게 항상 시작 주소를 버퍼의 맨 앞이라고 가정하는 것 — `STD` 모드에서는 반드시 끝 주소(`buf+len-1`)에서 시작해야 한다.

## 막혔을 때 다음 체크
- 복사 결과가 뒤집혀 나오거나 깨진다면 `CLD`/`STD` 상태부터 확인한다.
- 함수 반환 이후 다른 코드가 이상 동작한다면, 이 함수 내부에 `STD`만 있고 `CLD` 복원이 없는지 확인한다.
- `RDI`/`RSI` 초기값이 방향(`DF`)과 앞뒤가 맞는지 재확인한다.

## 미니 예제

**예제 1 — 정방향 복사 (memcpy 유사)**
```c
memcpy(dest, src, len);
```
```asm
cld
mov  rdi, dest
mov  rsi, src
mov  rcx, len
rep  movsb
```

**예제 2 — 역방향 복사 (겹치는 memmove, dest > src)**
```c
memmove(dest, src, len);  // dest가 src보다 뒤쪽이고 겹칠 때
```
```asm
std
lea  rdi, [dest+len-1]
lea  rsi, [src+len-1]
mov  rcx, len
rep  movsb
cld              ; ABI 요구사항: 함수 반환 전 DF 복원
```

**예제 3 — DF 상태를 몰라 헷갈리는 SCAS 방향**
```asm
std
mov  rdi, buf_end
mov  al, 0
mov  rcx, len
repne scasb        ; buf_end에서부터 거꾸로 0 바이트를 찾음
cld
```

## 관련 글
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0081 — MOVS MOVSB MOVSW MOVSD MOVSQ
- REV-0082 — STOS STOSB STOSD STOSQ
- REV-0084 — SCAS와 문자열 검색 패턴
- REV-0085 — CMPS와 문자열 비교 패턴
- REV-0046 — PUSHF와 POPF: 플래그 저장과 복원
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- CLD/STD 명령어 동작 및 DF 정의: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CLD—Clear Direction Flag" / "STD—Set Direction Flag" 섹션 기준 (2026-09-08 검증).
- 함수 경계에서 DF=0을 요구하는 ABI 규약: System V Application Binary Interface AMD64 Architecture Processor Supplement 및 Microsoft Learn x64 calling convention 문서 기준.
