---
id: REV-0084
title: "SCAS와 문자열 검색 패턴"
slug: "rev-0084-scas"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - scas
  - SCAS
  - scasb
  - SCASB
  - scasw
  - SCASW
  - scasd
  - SCASD
  - scasq
  - SCASQ
  - repne scasb
  - repnz scasb
  - repe scasb
  - string scan
  - 문자열 검색 명령
  - strlen
  - NUL 바이트 검색
  - RDI AL EAX
aliases:
  - scasb가 뭐임
  - scasd 뭐죠
  - repne scasb 뭐임
  - 어셈블리 strlen
  - 문자열 길이 구하는 어셈블리
symptom_keywords:
  - repne scasb가 이해가 안 됨
  - strlen이 함수 호출 없이 구현된 코드
  - scasb 뒤에 zf 검사하는 이유를 모르겠음
  - rdi가 nul 바이트를 찾는 코드
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`SCAS`(및 `SCASB`/`SCASW`/`SCASD`/`SCASQ`)는 `AL`/`AX`/`EAX`/`RAX`에 들어있는 값과 `[RDI]`가 가리키는 메모리 값을 비교해 플래그(특히 `ZF`)를 세팅하고 `RDI`를 자동으로 전진(또는 후진)시키는 명령이다. `REPNE`(REPNZ) 접두사와 함께 쓰이면 "특정 값을 찾을 때까지 스캔"하는 루프가 되며, 그 대표 용례가 바로 **NUL 바이트를 찾는 `strlen` 스타일 스캔**이다.

## 언제 검색해야 하나
- `repne scasb`, `repnz scasb` 같은 코드가 함수 안에 보이는데 `strlen` 호출은 안 보일 때
- `SCAS`가 `MOVS`/`STOS`와 뭐가 다른지, 어느 레지스터를 쓰는지 헷갈릴 때
- `scasb` 직후 `RDI`나 `RCX` 값을 가지고 뭔가 계산(빼기)하는 코드를 볼 때 (문자열 길이를 구하는 관용구)
- `repe scasb`/`repne scasb`의 차이, `ZF`가 왜 관여하는지 궁금할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
scasb          ; AL  와 BYTE PTR [RDI] 비교, 플래그만 갱신 (뺄셈 후 결과 버림)
scasw          ; AX  와 WORD PTR [RDI] 비교
scasd          ; EAX 와 DWORD PTR [RDI] 비교
scasq          ; RAX 와 QWORD PTR [RDI] 비교   (x64 전용)
```
동작은 `CMP AL, [RDI]`(플래그만 세팅, 값은 저장 안 함)와 사실상 같지만, 추가로 `RDI`를 자동 증감시킨다는 점이 다르다.

### 방향 및 레지스터 효과
- **찾을 값(비교 기준)**: `AL`/`AX`/`EAX`/`RAX`.
- **스캔 대상**: `RDI`가 가리키는 메모리(주의: `MOVS`/`CMPS`의 소스는 `RSI`인데, `SCAS`는 `STOS`처럼 **`RDI`만** 사용한다 — "쓰기든 스캔이든 목적지 계열 레지스터인 `RDI`"라고 기억하면 헷갈리지 않는다).
- 매 비교 후 `DF`(REV-0080 참고)에 따라 `RDI`만 증가 또는 감소한다.
  - `DF=0`: `RDI += size`
  - `DF=1`: `RDI -= size`
- `RSI`는 `SCAS`와 무관하다.

### REPNE SCAS — "다를 때까지" 반복해서 "찾을 때까지" 스캔하기
`REPNE`(또는 `REPNZ`)는 "**같지 않은(ZF=0) 동안** 반복"이라는 뜻이므로, 반대로 말하면 "**같아지는 순간(ZF=1) 멈춘다**" — 즉 `찾는 값과 일치하는 위치를 찾으면 자동으로 멈추는 루프가 된다. `strlen`처럼 NUL 바이트(값 0)를 찾을 때 전형적으로 쓰인다:
```asm
lea     rdi, [str]
xor     al, al        ; 찾을 값 = 0 (NUL)
mov     rcx, -1        ; 사실상 무제한 (0xFFFFFFFFFFFFFFFF)
cld
repne scasb              ; NUL을 만날 때까지 RDI를 전진시키며 스캔
; 스캔이 끝나면 RDI는 "NUL 바이트의 다음 주소"를 가리킨다
```
`REPE`/`REPZ` `SCAS`도 문법적으로 가능한데, 이건 반대로 "**값이 계속 같은 동안** 반복 → 다른 값이 나오면 멈춘다"는 의미다. 예를 들어 "0x00으로 채워진 영역이 어디까지인지"를 찾을 때(패딩 영역의 끝을 찾는 등) `REPE SCAS`가 쓰일 수 있다. 실무에서는 `REPNE SCAS`(뭔가를 찾을 때까지)가 압도적으로 흔하다.

### RCX = -1 관용구
`strlen`처럼 문자열 길이를 모르는 상태에서 스캔할 때는 `RCX`에 실제 반복 횟수 대신 **-1(즉 `0xFFFFFFFFFFFFFFFF`, 사실상 무한대에 가까운 값)**을 넣어두는 관용구가 흔하다. 어차피 `REPNE`는 `ZF`가 1이 되는 순간(=NUL을 찾는 순간) 먼저 멈추므로 `RCX`가 실질적인 반복 상한 역할을 거의 하지 않기 때문이다. 이 패턴(`mov ecx, 0FFFFFFFFh` 또는 `or rcx, -1` 다음 `repne scasb`)을 보면 십중팔구 "길이를 모르는 문자열/버퍼를 끝까지 스캔한다"는 뜻이다.

### 문자열 길이 계산 관용구
스캔이 끝난 후 `RDI`는 "찾은 위치의 다음 주소"를 가리키고 있다. 그래서 길이를 구하려면 보통:
```
길이 = (스캔 후 RDI) - (스캔 시작 시 RDI) - 1
```
또는 `RCX`를 초기값(-1)에서 빼는 방식으로 계산한다(`시작 RCX - 종료 RCX - 1`). IDA/Ghidra 디컴파일에서는 이 뺄셈 계산이 그대로 `strlen(str)` 결과값으로 뭉쳐 보이는 경우가 많다.

### 플래그 변화
`SCAS`는 `CMP`와 동일하게 **`CF`, `ZF`, `SF`, `OF`, `AF`, `PF`를 갱신**한다. `REPNE`/`REPE` 접두사가 종료 조건 판단에 쓰는 것이 바로 이 `ZF`다.

### 스택/RIP 변화
직접적인 영향 없음.

## 컴파일러 패턴 — strlen 인라인 인식하기
```asm
lea     rdi, [rbp-0x50]   ; 문자열 버퍼
xor     eax, eax            ; 찾을 값 = 0 (NUL)
or      rcx, -1              ; RCX = 0xFFFFFFFFFFFFFFFF
repne scasb
not     rcx
dec     rcx                   ; == strlen(rbp-0x50)
```
`repne scasb` + 그 뒤의 `not`/`dec`/뺄셈 조합이 통째로 보이면 "이건 그냥 `strlen` 한 번이다"라고 인식하면 된다. 한 줄씩 따라가며 "왜 NOT을 하지?"라고 고민할 필요 없이, 전체 블록을 `strlen` 호출과 동일시하고 다음 코드로 넘어가는 게 효율적이다.

## IDA/Ghidra 디컴파일에서 보이는 방식
- 표준 패턴이 인식되면 `strlen(str)` 호출로 깔끔하게 표시되거나, 최소한 그 결과가 담기는 변수에 대해 "이건 길이"라는 힌트를 주는 형태로 보인다.
- 인식되지 않으면 `for (p = str; *p; p++);` 같은 raw 스캔 루프나, `n = 0; while(str[n]) n++;` 형태로 표시된다.
- Ghidra는 특히 `RCX = -1` 초기화와 `repne scasb` 조합을 잘 인식하지 못하는 경우가 있어 raw 루프로 남는 일이 IDA보다 상대적으로 흔하다 — 이럴 때 어셈블리 원문에서 이 패턴을 직접 확인하면 빠르다.

## 리버싱 관점에서의 의미
- `repne scasb`는 사실상 "strlen을 함수 호출 없이 인라인한 것"이므로, 문자열 길이를 구하는 코드를 찾을 때 함수 호출 목록(Imports)에서 `strlen`이 안 보이더라도 이 패턴이 있는지 먼저 찾아봐야 한다.
- 찾는 값이 0(NUL)이 아니라 다른 값(예: 특정 구분자 `,`, `\n` 등)이라면 `strchr`류 함수가 인라인된 것일 수 있다.
- `RDI` 시작 주소를 확인하면 어떤 버퍼(사용자 입력, 파일 경로 등)의 길이/특정 문자를 찾는지 알 수 있어, 뒤이어 나오는 검증/분기 로직의 맥락을 빠르게 잡을 수 있다.

## 가장 먼저 할 것
`scasb`/`repne scasb`(또는 `repe scasb`)를 봤다면 가장 먼저 확인할 것:
1. **찾는 값** — 직전에 `AL`/`EAX`에 세팅된 값. 0이면 NUL 탐색(`strlen`류), 다른 문자면 구분자 탐색(`strchr`류)이다.
2. **`REPNE`인지 `REPE`인지** — `REPNE`(다를 때 반복 → 같으면 멈춤, 즉 "찾으면 멈춤")가 압도적으로 흔하다. `REPE`라면 반대로 "달라지면 멈춤"이므로 무엇을 찾는지 반대로 해석해야 한다.
3. **`RCX` 초기값이 `-1`(무제한)인지 특정 상수인지** — `-1`이면 길이를 모르는 채로 끝까지 스캔, 상수면 최대 탐색 범위가 제한된 것이다.

## 단계별 절차
1. `repne scasb`(또는 `repe scasb`) 바로 앞에서 `AL`/`EAX`에 어떤 값이 들어가는지 확인해 "무엇을 찾는지" 확정한다.
2. `RDI` 세팅 지점을 역추적해서 스캔 대상 버퍼가 무엇인지 확인한다.
3. `RCX`가 `-1`(또는 `or rcx, -1`)인지 확인한다 — 맞다면 "길이 제한 없이 찾을 때까지" 패턴이다.
4. F5로 디컴파일해서 `strlen(...)` 또는 유사 스캔으로 인식됐는지 확인한다. Ghidra는 이 패턴을 못 알아채고 raw 루프로 남기는 경우가 IDA보다 잦으니, 그럴 땐 어셈블리 원문을 기준으로 판단한다.
5. `repne scasb` 직후에 이어지는 `not`/`dec`/`sub` 등 산술 명령을 따라가서 최종 결과(길이 또는 발견 위치)가 어느 레지스터/변수에 담기는지 확인한다.
6. 결과가 맞는지 확신이 안 서면 `repne scasb` 다음 명령에 브레이크포인트를 걸고 실행 후 `RDI`/`RCX` 실제 값을 확인해 손으로 계산한 값과 대조한다.

## 명령어/단축키
- IDA: `F5`(디컴파일), `Strings` 창(Shift+F12)에서 찾는 값이 상수 문자가 아니라 NUL인지 정황 확인, `F2`/`F9`로 브레이크포인트 후 실행
- x64dbg: `repne scasb` 다음 줄에 브레이크포인트를 걸고 `F9`로 실행 후 레지스터 패널에서 `RDI`, `RCX`, 플래그 패널의 `ZF` 확인
- GDB/Pwndbg: `break *0x<repne_scasb_다음주소>`, `info registers rdi rcx eflags`로 스캔 종료 시점의 상태를 한 번에 확인

## 흔한 실수
- `SCAS`의 스캔 대상을 `RSI`로 착각하는 것 — `SCAS`는 `RDI`만 쓴다(`RSI`는 관여 안 함).
- `REPNE`와 `REPE`를 반대로 이해하는 것 — `REPNE`(다를 때 반복)는 "같아지면 멈춘다"(=찾으면 멈춘다), `REPE`(같을 때 반복)는 "달라지면 멈춘다".
- `RCX = -1` 세팅을 보고 "무한 루프인가?"라고 걱정하는 것 — `REPNE`가 조건에 따라 먼저 끝나므로 사실상 안전한 관용구다.
- 스캔이 끝난 후 `RDI`가 "찾은 값의 위치"라고 착각하는 것 — 정확히는 **찾은 위치의 다음 주소**(비교 후 이미 한 번 증가한 상태)라는 오프바이원(off-by-one)에 주의해야 한다.

## 막혔을 때 다음 체크
- 무엇을 찾고 있는지 궁금하면 → `scasb`(등) 직전 `AL`/`EAX`에 세팅된 값을 확인 (0이면 NUL, strlen류).
- 스캔 시작 위치가 궁금하면 → 직전 `RDI` 세팅 지점을 역추적.
- 결과 길이/오프셋이 어떻게 계산되는지 궁금하면 → `repne scasb` 직후의 `RDI`/`RCX` 관련 산술 명령(`sub`, `not`, `dec`)을 따라간다.

## 미니 예제

**예제 1 — strlen 인라인 (가장 흔한 패턴)**
```c
size_t n = strlen(str);
```
```asm
lea     rdi, [str]
xor     eax, eax     ; 찾을 값 = 0
or      rcx, -1
repne scasb
not     rcx
dec     rcx            ; rcx = strlen(str)
```

**예제 2 — 특정 문자(구분자) 탐색 (strchr류)**
```asm
lea     rdi, [line]
mov     al, ','        ; 콤마를 찾는다
mov     rcx, -1
repne scasb
; ZF=1 이면 찾음, RDI-1 이 콤마 위치
jne     not_found
```

**예제 3 — REPE SCAS로 "값이 이어지는 구간의 끝" 찾기 (드문 패턴)**
```asm
lea     rdi, [padding_area]
xor     al, al         ; 0이 계속되는 구간을 찾음
mov     rcx, 256
repe scasb                ; 0이 아닌 바이트를 만나면 멈춤
```

**예제 4 — 짧은 고정 길이 스캔 (RCX가 -1이 아닌 상수인 경우)**
```asm
lea     rdi, [buf]
mov     al, 0FFh
mov     ecx, 8          ; 최대 8바이트까지만 찾는다
repne scasb
jne     sentinel_missing  ; 8바이트 안에서 못 찾음
```

## 관련 글
- [rev-0080-rep-prefix.md](./rev-0080-rep-prefix.md) — REP Prefix와 반복 문자열 명령 (REPE/REPNE 조건 반복 규칙)
- [rev-0081-movs.md](./rev-0081-movs.md) — MOVS/MOVSB/MOVSW/MOVSD/MOVSQ
- [rev-0082-stos.md](./rev-0082-stos.md) — STOS/STOSB/STOSD/STOSQ
- [rev-0083-lods.md](./rev-0083-lods.md) — LODS 문자열 로드 명령
- [rev-0085-cmps.md](./rev-0085-cmps.md) — CMPS와 문자열 비교 패턴

## 출처/검증
- `SCAS`/`SCASB`/`SCASW`/`SCASD`/`SCASQ` 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2C, "SCAS/SCASB/SCASW/SCASD/SCASQ—Scan String" 섹션 기준 (2026-09-08 검증).
- `REPE`/`REPNE` 조건부 반복과 `ZF` 관계: 동 매뉴얼 "REP/REPE/REPZ/REPNE/REPNZ" 섹션 기준.
- `strlen` 인라인 시 `repne scasb` + `RCX=-1` 관용구: 일반적인 GCC/MSVC 산출물 관찰 및 리버싱 레퍼런스 기준.
