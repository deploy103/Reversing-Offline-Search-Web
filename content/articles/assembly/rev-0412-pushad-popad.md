---
id: REV-0412
title: "PUSHAD와 POPAD 차이"
slug: "rev-0412-pushad-popad"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - pushad
  - PUSHAD
  - Pushad
  - popad
  - POPAD
  - Popad
  - pushad 명령어
  - popad 명령어
  - push all doubleword
  - pop all doubleword
  - 32비트 레지스터 일괄 저장
  - 32비트 레지스터 일괄 복원
  - "pushad"
  - "popad"
  - 셸코드 pushad
  - shellcode pushad
aliases:
  - pushad 뭐임
  - popad 뭐임
  - pushad가 뭐죠
  - popad가 뭐죠
  - pushad 명령
  - popad 명령
  - PUSHAD 명령어
  - POPAD 명령어
symptom_keywords:
  - pushad popad가 shellcode에서 왜 나오는지
  - pushad와 pusha 차이
  - 32비트 레지스터 8개 저장 명령어
  - pushad가 x64에서 안 되는 이유
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`PUSHAD`는 32비트 범용 레지스터 8개(EAX, ECX, EDX, EBX, ESP, EBP, ESI, EDI)를 한 번에 스택에 저장하고 `POPAD`는 반대로 복원하는 명령어로, [`PUSHA`/`POPA`](rev-0411-pusha-popa.md)의 32비트 버전이며 마찬가지로 64비트 모드에서는 사용할 수 없다.

## 언제 검색해야 하나
- 32비트 PE 바이너리나 셸코드에서 `pushad`, `popad`를 만났는데 왜 레지스터 8개를 한 번에 다루는지 궁금할 때
- 함수/스텁의 맨 앞에 `pushad`, 맨 끝에 `popad`가 있어서 "이 블록은 레지스터를 안 건드리고 지나가겠구나"라고 판단하려 할 때
- `PUSHA`(REV-0411)와 `PUSHAD`가 정확히 무엇이 다른지 헷갈릴 때
- 패커/언패킹 스텁, 32비트 CTF 익스플로잇 코드에서 이 패턴을 볼 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
PUSHAD   ; 오퍼랜드 없음
POPAD    ; 오퍼랜드 없음
```
`PUSHA`/`POPA`(REV-0411)와 동일하게 오퍼랜드가 없다.

### PUSHAD가 하는 일 — 32비트 레지스터 8개를 순서대로 PUSH
`PUSHAD`는 EAX, ECX, EDX, EBX, **원래(시작 전) ESP 값**, EBP, ESI, EDI를 이 순서로 스택에 [PUSH](rev-0044-push.md)한다. 각 PUSH가 4바이트씩이므로 총 32바이트(8개 x 4바이트)만큼 ESP가 감소한다.

### POPAD가 하는 일 — 반대 순서로 POP, ESP 슬롯은 버림
`POPAD`는 EDI, ESI, EBP, **(ESP 슬롯 — 읽지만 버림)**, EBX, EDX, ECX, EAX 순서로 [POP](rev-0045-pop.md)한다. ESP 자리는 [PUSHA/POPA](rev-0411-pusha-popa.md)와 완전히 같은 이유로 실제 ESP 레지스터에 재로드되지 않는다 — 나머지 7개를 POP하면 ESP는 자연스럽게 PUSHAD 실행 전 값으로 돌아온다.

### PUSHA/POPA와의 차이 — 오퍼랜드 크기와 인코딩
| 항목 | PUSHA/POPA (REV-0411) | PUSHAD/POPAD (이 문서) |
|---|---|---|
| 레지스터 크기 | 16비트 (AX, BX, CX, DX, SP, BP, SI, DI) | 32비트 (EAX, EBX, ECX, EDX, ESP, EBP, ESI, EDI) |
| 스택 소비량 | 16바이트 (8 x 2) | 32바이트 (8 x 4) |
| 주 사용 환경 | 16비트 코드 세그먼트 (DOS, 부트로더 초기 단계) | 32비트 코드 세그먼트 (32비트 PE/ELF, 셸코드) |

두 명령어는 사실 **같은 오피코드(`0x60`/`0x61`)를 공유**하며, 실행되는 코드 세그먼트의 기본 오퍼랜드 크기(D 비트)와 `66h`(오퍼랜드 크기 오버라이드) 접두사 유무의 조합으로 어셈블러가 `PUSHA`로 어셈블할지 `PUSHAD`로 어셈블할지 결정한다. 32비트 기본 세그먼트에서는 접두사 없는 `0x60`이 `PUSHAD`, `66h 0x60`이 `PUSHA`가 된다(16비트 세그먼트에서는 반대).

### 플래그 변화
`PUSHAD`/`POPAD` 자체는 플래그를 전혀 건드리지 않는다.

### signed/unsigned 관점
해당 없음 — 레지스터 값을 그대로 복사하는 연산이다.

### 스택/ESP 변화
```
PUSHAD 실행 전: ESP = S
PUSHAD 실행 후: ESP = S - 32
POPAD  실행 후: ESP = S       (정확히 복귀)
```

### 왜 64비트 모드에서는 쓸 수 없는가
`PUSHA`/`POPA`와 정확히 같은 이유다 — 오피코드 `0x60`/`0x61`이 x64 모드에서는 유효하지 않은 인코딩으로 처리되며(REX 접두사 도입으로 오피코드 공간이 재구성되면서 되살리지 않기로 결정), 이 바이트를 실행하면 `#UD` 예외가 발생한다. `PUSHADQ`/`POPADQ` 같은 64비트 버전도 아예 존재하지 않는다 — 애초에 x64에는 EFLAGS 위치의 원래 ESP 저장 슬롯 개념 자체가 다시 도입되지 않았다.

### 리버싱 의미 — 32비트 셸코드/패커 스텁의 전형적 패턴
`PUSHAD ... POPAD`로 감싸진 코드 블록은 "이 안에서 레지스터를 마음껏 써도 밖에서는 아무 영향이 없다"는 뜻이다. 이 패턴은 다음에서 특히 자주 나타난다:
- **32비트 셸코드**: 페이로드를 실행하기 전에 `pushad`로 호출 환경의 레지스터를 백업하고, 실행 후 `popad`로 복원해서 원래 실행 흐름(감염된 프로세스)이 눈치채지 못하게 하는 전형적 기법.
- **패커/언패킹 스텁**: 실행 파일의 진입점에서 압축 해제 루틴이 온갖 레지스터를 자유롭게 사용한 뒤, 실제 OEP(Original Entry Point)로 넘어가기 직전에 `popad`로 레지스터를 되돌려서 마치 아무 일도 없었던 것처럼 원본 프로그램이 시작되게 만드는 경우가 많다(UPX 등 일부 패커의 스텁 구조에서 관찰되는 패턴).
- **32비트 익스플로잇/ROP 준비 코드**: 레지스터 상태를 한 번에 저장/복원할 때.

### 컴파일러 패턴
`PUSHA`/`POPA`와 마찬가지로 일반 C 컴파일러는 `PUSHAD`/`POPAD`를 자동 생성하지 않는다. 손으로 작성된 어셈블리, 셸코드, 패커 스텁에서만 나타난다고 보면 된다.

### IDA/Ghidra 디컴파일에서 보이는 형태
IDA는 `pushad`/`popad`를 그대로 표시한다. Hex-Rays는 이를 직접적인 C 표현으로 변환하지 못하는 경우가 많아, 함수 시작/끝의 레지스터 저장 관례로 뭉뚱그려 처리하거나 디컴파일이 부정확해질 수 있다 — 이런 경우 어셈블리 원문을 직접 읽는 것이 더 정확하다.

## 화면/코드에서 보이는 징후
- `pushad` ... `popad` — 32비트 코드 블록 전체에서 레지스터를 보존하는 전형적 래핑
- 함수/스텁 진입부의 `pushad` — "이 함수는 호출자의 레지스터를 건드리지 않는다"는 신호
- 패커 스텁 끝부분의 `popad` 직후 `jmp`(OEP로 점프) — 언패킹 완료 후 원본 코드로 넘어가는 전형적 지점
- x64 바이너리에서는 절대 등장하지 않음

## 가장 먼저 할 것
1. `pushad`와 짝을 이루는 `popad`의 위치를 찾아 그 사이 전체를 하나의 "레지스터 보존 블록"으로 묶는다.
2. `popad` 직후에 무엇이 오는지 확인한다 — `jmp`(특히 계산된 주소로)가 온다면 OEP(원본 진입점)로의 점프일 가능성을 의심한다(언패킹 완료 신호).
3. 이 파일이 32비트 대상이 맞는지 확인한다(x64에서는 존재할 수 없는 명령어이므로).

## 단계별 절차

**1) 기본 저장/복원 인식**
```asm
pushad
mov  eax, 1234h
mov  ebx, 5678h
; 레지스터를 자유롭게 사용
popad
; 이 지점부터 모든 32비트 레지스터가 pushad 이전 값으로 복원됨
```

**2) 패커 스텁에서의 전형적 사용 (언패킹 → OEP 점프)**
```asm
unpack_stub:
    pushad
    ; ... 압축 해제 루프 (온갖 레지스터 사용) ...
    popad
    jmp   original_entry_point   ; OEP로 점프 — 언패킹 완료 신호
```
이 패턴을 보면 디버거에서 `popad` 다음의 `jmp` 대상 주소에 브레이크포인트를 걸고 실행하면 OEP에 바로 도달할 수 있다.

**3) 32비트 셸코드에서의 사용**
```asm
shellcode_start:
    pushad             ; 감염된 프로세스의 레지스터 백업
    call  do_payload
    popad               ; 복원 -> 감염된 프로세스는 아무 일 없었던 것처럼 계속 실행
    jmp   original_code
```

## 명령어/단축키
- x64dbg(32비트 대상, x32dbg): `pushad` 실행 전후 레지스터 창과 스택 창을 비교하면 8개 값이 정확히 32바이트로 쌓이는 것을 확인 가능
- IDA: `popad` 바로 다음의 `jmp` 대상에 브레이크포인트를 걸어 언패킹 완료 지점(OEP) 탐색에 활용

## 출력 해석
- `pushad` 실행 후 ESP가 정확히 32만큼 감소했는지 확인한다.
- `popad` 실행 후 ESP가 `pushad` 실행 전 값으로 정확히 복귀했는지 확인한다.
- 패커 분석 중이라면 `popad` 직후 레지스터 값들이 이제 "원본 프로그램이 기대하는 초기 상태"와 비슷해 보이는지 관찰한다(EAX가 특정 의미 있는 값으로 바뀌어 있는 경우가 흔함).

## 흔한 실수
- `PUSHAD`가 x64에서도 동작한다고 가정하는 것 — `#UD` 예외가 발생하는 유효하지 않은 인코딩이다.
- `PUSHA`(16비트)와 `PUSHAD`(32비트)를 같은 것으로 혼동해서 스택 소비량을 잘못 계산하는 것 — 16바이트 vs 32바이트로 다르다.
- `POPAD`가 ESP 자체도 스택에서 읽은 값으로 덮어쓴다고 착각하는 것 — 그 슬롯은 버려진다.
- 패커 스텁의 `pushad`/`popad` 블록 안을 명령어 단위로 하나하나 분석하려는 것 — 대부분은 "이 블록의 순수한 목적(압축 해제)"만 파악하면 되고, 굳이 모든 명령어를 이해할 필요는 없다(REV-0071의 Step Over 개념과 같은 발상).

## 막혔을 때 다음 체크
- x64 바이너리인데 `pushad`가 보인다면 → 실제로는 임베디드된 32비트 서브 모듈, 혹은 디스어셈블 위치 오분석을 의심한다.
- 패커로 보이는 스텁을 분석 중이라면 → `pushad`로 시작해서 `popad` + `jmp`로 끝나는 구간을 찾아 그 `jmp`의 목적지를 OEP 후보로 표시해둔다.
- 스택이 어긋나 보이면 → `pushad`/`popad`가 정확히 짝을 이루는지, 그 사이에 수동 `push`/`pop`이 균형 없이 섞여 있지 않은지 확인한다.

## 미니 예제

**예제 1 — 기본 저장/복원**
```asm
pushad
mov  eax, 0deadbeefh
; ... eax 등을 마음대로 사용 ...
popad
; eax는 pushad 이전 값으로 복원됨
```

**예제 2 — 패커 스텁 → OEP 점프**
```asm
entry:
    pushad
    call  decompress_routine
    popad
    jmp   00401000h      ; OEP로 점프, 언패킹 완료
```

**예제 3 — 32비트 셸코드 레지스터 보존**
```asm
start:
    pushad
    call  find_kernel32
    call  resolve_apis
    call  run_payload
    popad
    jmp   original_ep
```

## 관련 글
- REV-0411 — PUSHA와 POPA: 레거시 32비트 일괄 저장/복원
- REV-0044 — PUSH: 스택에 값 넣기
- REV-0045 — POP: 스택에서 값 꺼내기
- REV-0046 — PUSHF와 POPF: 플래그 저장과 복원
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- PUSHAD/POPAD 명령어의 레지스터 순서, 스택 변화, ESP 슬롯이 버려지는 동작, 64비트 모드에서 유효하지 않은 인코딩: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "PUSHA/PUSHAD—Push All General-Purpose Registers" / "POPA/POPAD—Pop All General-Purpose Registers" 섹션 기준 (2026-09-08 검증).
- 패커 스텁에서 pushad/popad + OEP 점프 패턴: 다수의 공개 언패킹 튜토리얼 및 리버싱 교육 자료에서 공통적으로 설명하는 관찰된 실무 패턴.
