---
id: REV-0085
title: "CMPS와 문자열 비교 패턴"
slug: "rev-0085-cmps"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - cmps
  - CMPS
  - cmpsb
  - CMPSB
  - cmpsw
  - CMPSW
  - cmpsd
  - CMPSD
  - cmpsq
  - CMPSQ
  - repe cmpsb
  - repz cmpsb
  - repne cmpsb
  - string compare
  - 문자열 비교 명령
  - memcmp
  - strcmp
  - RSI RDI 비교
aliases:
  - cmpsb가 뭐임
  - cmpsd 뭐죠
  - repe cmpsb 뭐임
  - 어셈블리 memcmp
  - 두 버퍼 비교하는 어셈블리
symptom_keywords:
  - repe cmpsb가 이해가 안 됨
  - memcmp가 함수 호출 없이 구현된 코드
  - 두 버퍼가 같은지 비교하는 루프를 못찾음
  - cmpsb 뒤에 왜 zf를 확인하는지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CMPS`(및 `CMPSB`/`CMPSW`/`CMPSD`/`CMPSQ`)는 `[RSI]`와 `[RDI]`가 가리키는 두 메모리 값을 비교해 플래그를 세팅하고 `RSI`, `RDI`를 자동으로 전진(또는 후진)시키는 명령이다. `REPE`(REPZ) 접두사와 함께 쓰이면 "두 버퍼가 같은 동안 계속 비교"하는 루프가 되어, 컴파일러가 `memcmp`/`strcmp`류를 인라인할 때의 전형적인 모습이 된다.

## 언제 검색해야 하나
- `repe cmpsb`, `repz cmpsb` 코드가 함수 안에 보이는데 `memcmp`/`strcmp` 호출이 안 보일 때
- 두 개의 버퍼(비밀번호 입력값과 정답값 등)를 비교하는 로직을 CTF 크랙미에서 찾고 있을 때
- `CMPS`와 `SCAS`의 차이(둘 다 비교 명령인데 뭐가 다른지)가 헷갈릴 때
- `cmpsb` 실행 후 바로 `jne`/`jnz`로 분기하는 코드를 볼 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
cmpsb          ; BYTE PTR [RSI] 와 BYTE PTR [RDI] 비교 (== CMP [RSI], [RDI] 처럼 동작, 플래그만 갱신)
cmpsw          ; WORD  단위 비교
cmpsd          ; DWORD 단위 비교   (SSE의 CMPSD와 이름이 겹치니 오퍼랜드 유무로 구분)
cmpsq          ; QWORD 단위 비교   (x64 전용)
```
`CMPS`는 다섯 문자열 명령 중 유일하게 **두 메모리 피연산자를 동시에** 다룬다(나머지는 메모리-레지스터 조합).

### 방향 및 레지스터 효과 (MOVS와 동일한 소스/목적지 배치)
- **첫 번째 피연산자(비교 기준 좌변)**: `RSI`가 가리키는 메모리.
- **두 번째 피연산자(비교 기준 우변)**: `RDI`가 가리키는 메모리.
- 매 비교 후 `DF`(REV-0080 참고)에 따라 `RSI`와 `RDI`가 **동시에** 증가 또는 감소한다.
  - `DF=0`: `RSI += size`, `RDI += size`
  - `DF=1`: `RSI -= size`, `RDI -= size`
- `MOVS`와 레지스터 역할 배치가 완전히 같다(`RSI`=첫 번째/소스 계열, `RDI`=두 번째/목적지 계열) — `MOVS`를 먼저 이해했다면 `CMPS`는 "복사 대신 비교"로 바꿔서 그대로 적용하면 된다.

### REPE CMPS — "같은 동안" 반복해서 "다를 때" 멈추기
`REPE`(또는 `REPZ`)는 "**같은(ZF=1) 동안** 반복"이므로, 반대로 말하면 "**다른 바이트를 만나는 순간(ZF=0) 멈춘다**". 이것이 `memcmp`/`strcmp`의 핵심 동작과 정확히 일치한다:
```asm
lea     rsi, [bufA]
lea     rdi, [bufB]
mov     rcx, 16
cld
repe cmpsb                ; 16바이트를 비교하다가 다른 바이트가 나오면 즉시 중단
jne     not_equal          ; 마지막 비교 결과(ZF)로 분기: 다르면 not_equal로
; 여기 도달하면 16바이트 전부 같음
```
`REPNE CMPS`(다를 때 반복 → 같아지면 멈춤)도 문법적으로 가능하지만 실무에서는 드물다(예: "두 버퍼가 처음으로 일치하는 지점을 찾는" 특수한 경우).

### 종료 후 상태로 "어디까지 같았는지" 알아내기
`REPE CMPS`가 중간에 멈췄다면, `RCX`가 남은 반복 횟수를 담고 있으므로 `초기 RCX - 종료 RCX`가 "몇 바이트까지 같았는지"가 된다. 완전히 끝까지 돌았다면(`RCX == 0`) 전체가 동일하다는 뜻이다. `strcmp`처럼 대소 비교 결과까지 필요하면, 마지막으로 비교된 두 바이트의 대소 관계가 `CF`/`SF`/`OF` 조합에 남아 있어 이를 이용해 양수/음수/0을 만드는 후속 코드가 이어지는 경우가 많다.

### 플래그 변화
`CMPS`는 `CMP`와 동일하게 **`CF`, `ZF`, `SF`, `OF`, `AF`, `PF`를 갱신**한다. `REPE`/`REPNE`의 조기 종료 판단은 이 중 `ZF`를 사용한다.

### 스택/RIP 변화
직접적인 영향 없음.

## 컴파일러 패턴 — memcmp/strcmp 인라인 인식하기
```asm
lea     rsi, [input]
lea     rdi, [expected]
mov     rcx, 8
cld
repe cmpsb
sete    al             ; ZF를 0/1로 변환 (REV-0076 SETcc 참고) → memcmp 결과가 0인지(같은지) bool로
```
이 조합이 통째로 보이면 "이건 `memcmp(input, expected, 8) == 0` 검사 한 줄이다"라고 인식하는 게 핵심이다. CTF 크랙미에서 정답 문자열과 입력을 비교하는 부분이 바로 이런 형태로 최적화되어 있는 경우가 많다.

## IDA/Ghidra 디컴파일에서 보이는 방식
- 표준 패턴이 인식되면 `memcmp(a, b, n) == 0` 또는 `if (memcmp(a, b, n)) ...` 형태로 표시된다.
- 인식되지 않으면 `while (n-- && *p1 == *p2) { p1++; p2++; }` 같은 raw 비교 루프, 또는 `for` 루프 형태로 표시된다.
- `strcmp`가 인라인된 경우는 길이를 미리 모르기 때문에 `RCX = -1`과 `SCAS`(NUL 탐색)가 먼저 나오고 그 뒤에 `CMPS`가 오는 좀 더 복잡한 조합으로 나타날 수도 있다 — 이 경우도 "길이 확인 + 내용 비교"라는 두 단계로 나눠서 읽으면 이해하기 쉽다.

## 리버싱 관점에서의 의미
- **CTF/크랙미에서 가장 자주 찾게 되는 패턴 중 하나**다 — "입력값 검증"의 핵심이 바로 이 비교 루프인 경우가 많다.
- `RSI`/`RDI` 중 어느 쪽이 "사용자 입력"이고 어느 쪽이 "정답/기대값"인지 구분하면, 정답 버퍼의 주소를 알아내 메모리 덤프로 바로 정답을 읽어낼 수 있는 경우가 있다(정적 문자열로 하드코딩되어 있다면).
- `REP CMPS` 대신 한 바이트씩 XOR/변환 후 비교하는 형태(예: `lodsb`로 읽고 변형 후 비교)라면 단순 `memcmp`가 아니라 커스텀 검증 알고리즘이므로 REV-0083(LODS) 패턴과 함께 분석해야 한다.

## 가장 먼저 할 것
`cmpsb`/`repe cmpsb`를 봤다면 가장 먼저 확인할 것:
1. **`RSI`와 `RDI`가 각각 어떤 버퍼를 가리키는지** — 하나는 대개 "사용자 입력", 다른 하나는 "정답/기대값(하드코딩된 상수일 수 있음)"이다. CTF에서는 정답 버퍼 쪽 주소를 알아내는 것 자체가 목표일 수 있다.
2. **`RCX`(비교 길이)** — 상수인지, 다른 곳에서 계산된 값(예: `strlen` 결과)인지.
3. **`REPE`/`REPZ`인지** — "같은 동안 반복 → 다르면 즉시 멈춤"이 압도적으로 흔한 형태(`memcmp`/`strcmp` 스타일)다.
4. **`cmpsb` 반복 직후의 `jne`/`je`(또는 `setcc`)** — 이게 바로 "같았는가"의 최종 판정이다.

## 단계별 절차
1. `repe cmpsb` 바로 앞에서 `RSI`, `RDI` 세팅 지점을 각각 역추적해 두 버퍼의 정체(사용자 입력 vs 상수/정답)를 확정한다.
2. `RDI`(또는 `RSI`) 쪽이 프로그램 내부에 하드코딩된 상수 문자열이면, IDA에서 그 주소로 이동(`G` 또는 더블클릭)해 실제 값을 바로 읽는다 — 정답이 그대로 노출되어 있을 수 있다.
3. `RCX`(비교 길이)를 확인한다.
4. `repe cmpsb` 직후의 `jne`/`je`/`sete` 명령을 확인해서 "같으면 통과"인지 "다르면 통과"인지(반전 여부, REV-0067/0068 참고) 판단한다.
5. F5로 디컴파일해서 `memcmp(a, b, n) == 0` 형태로 인식됐는지 확인한다.
6. 값이 정적으로 안 나오면(런타임 계산된 버퍼) `repe cmpsb` 직후에 브레이크포인트를 걸고, 두 버퍼의 실제 메모리 내용을 덤프 창에서 나란히 비교한다.

## 명령어/단축키
- IDA: `G`(특정 주소로 이동 — 정답 상수 버퍼 확인), `F5`(디컴파일), `F2`/`F9`(브레이크포인트/실행)
- x64dbg: `repe cmpsb` 직후에 브레이크포인트, 덤프 창 두 개를 열어 각각 `RSI`/`RDI` 주소를 "Follow in Dump"로 띄워 나란히 비교
- GDB/Pwndbg: `x/s $rsi`, `x/s $rdi`(두 버퍼를 문자열로 각각 출력해서 바로 비교), `info registers rcx eflags`

## 흔한 실수
- `CMPS`가 비교 결과를 메모리에 "저장"한다고 착각하는 것 — `CMP`와 마찬가지로 **플래그만 세팅**하고 값 자체는 버려진다.
- `REPE`와 `REPNE`를 반대로 이해하는 것 — `REPE`(같을 때 반복)는 "다르면 멈춘다", `REPNE`(다를 때 반복)는 "같으면 멈춘다".
- `cmpsb`를 반복 실행한 후의 `jne`/`je`가 **마지막 비교 1회의 결과**만 반영한다는 걸 잊고, "전체 비교의 총합 결과"라고 오해하는 것 — 정확히는 REPE 루프가 처음으로 다른 지점에서 멈춘 그 비교 결과다.
- `CMPSD`(문자열 명령)와 SSE `CMPSD xmm, xmm/m64, imm8`(스칼라 double 비교)를 혼동하는 것 — 오퍼랜드 유무로 구분한다.

## 막혔을 때 다음 체크
- 어느 버퍼가 입력이고 어느 버퍼가 정답인지 궁금하면 → `RSI`, `RDI` 세팅 지점을 각각 역추적해서 함수 인자/전역 상수 여부를 확인.
- 비교 길이(`RCX`)가 궁금하면 → `repe cmpsb` 직전 `RCX` 세팅값 확인. `cmpsd`/`cmpsq`면 실제 바이트 수는 `RCX * 4` 또는 `RCX * 8`.
- 몇 바이트째에서 달라졌는지 궁금하면 → 반복 종료 후 `초기 RCX - 종료 RCX`를 계산(디버거로 직접 확인 가능).

## 미니 예제

**예제 1 — 8바이트 매직 값 비교 (memcmp == 0 검사)**
```c
if (memcmp(input, "flagflag", 8) == 0) { ... }
```
```asm
lea     rsi, [input]
lea     rdi, [magic]     ; "flagflag"
mov     rcx, 8
cld
repe cmpsb
jne     wrong              ; 하나라도 다르면 wrong으로 분기
; 여기 도달하면 8바이트 전부 일치
```

**예제 2 — QWORD 단위 빠른 비교**
```asm
lea     rsi, [bufA]
lea     rdi, [bufB]
mov     rcx, 4       ; 4 * 8바이트 = 32바이트
cld
repe cmpsq
jne     differ
```

**예제 3 — REP 없는 단독 CMPSB (한 바이트만 비교)**
```asm
lea     rsi, [a]
lea     rdi, [b]
cmpsb              ; [a]와 [b] 딱 1바이트만 비교, RSI/RDI 각각 +1
jne     not_equal
```

**예제 4 — SETcc와 결합해 bool 결과로 변환**
```asm
lea     rsi, [pw_input]
lea     rdi, [pw_correct]
mov     rcx, 12
cld
repe cmpsb
sete    al          ; al = (전부 같았으면 1, 아니면 0)  -- REV-0076 SETcc 참고
movzx   eax, al
ret                  ; bool 함수의 반환값처럼 쓰임
```

## 관련 글
- [rev-0080-rep-prefix.md](./rev-0080-rep-prefix.md) — REP Prefix와 반복 문자열 명령 (REPE/REPNE 조건 반복 규칙)
- [rev-0081-movs.md](./rev-0081-movs.md) — MOVS/MOVSB/MOVSW/MOVSD/MOVSQ (RSI/RDI 배치가 CMPS와 동일)
- [rev-0083-lods.md](./rev-0083-lods.md) — LODS 문자열 로드 명령 (커스텀 비교 루프와 함께 쓰이는 경우)
- [rev-0084-scas.md](./rev-0084-scas.md) — SCAS와 문자열 검색 패턴

## 출처/검증
- `CMPS`/`CMPSB`/`CMPSW`/`CMPSD`/`CMPSQ` 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CMPS/CMPSB/CMPSW/CMPSD/CMPSQ—Compare String Operands" 섹션 기준 (2026-09-08 검증).
- `REPE`/`REPNE` 조건부 반복과 `ZF` 관계: 동 매뉴얼 "REP/REPE/REPZ/REPNE/REPNZ" 섹션 기준.
- 컴파일러의 `memcmp`/`strcmp` 인라인 시 `repe cmpsb` + `setcc` 조합: 일반적인 GCC/MSVC 산출물 관찰 및 리버싱 레퍼런스 기준.
