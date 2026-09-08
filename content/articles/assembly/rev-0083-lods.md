---
id: REV-0083
title: "LODS 문자열 로드 명령"
slug: "rev-0083-lods"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - lods
  - LODS
  - lodsb
  - LODSB
  - lodsw
  - LODSW
  - lodsd
  - LODSD
  - lodsq
  - LODSQ
  - rep lodsb
  - string load
  - 문자열 로드 명령
  - RSI AL EAX RAX
  - 순차 읽기
  - sequential read
aliases:
  - lodsb가 뭐임
  - lodsd 뭐죠
  - lods 명령이란
  - 어셈블리 순차 읽기
symptom_keywords:
  - lodsb가 왜 있는지 모르겠음
  - rsi가 계속 증가하며 al에 값이 들어가는 코드
  - lods 명령이 왜 rep 없이 쓰이는지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LODS`(및 `LODSB`/`LODSW`/`LODSD`/`LODSQ`)는 `[RSI]`가 가리키는 메모리에서 값을 하나 읽어 `AL`/`AX`/`EAX`/`RAX`에 넣고 `RSI`를 자동으로 전진(또는 후진)시키는 명령이다. 다섯 개의 문자열 명령 중 유일하게 **REP와 함께 쓰이는 경우가 드물며**, 대신 한 바이트씩 읽어서 즉시 검사/가공하는 손으로 짠 루프(수제 파서, 커스텀 strlen/hash 등)에서 자주 보인다.

## 언제 검색해야 하나
- `lodsb`, `lodsd` 같은 명령이 루프 안에서 반복되는데 `rep` 접두사가 안 붙어 있어서 헷갈릴 때
- `RSI`가 계속 증가하면서 `AL`에 새 값이 들어가고, 그 값으로 뭔가 비교/연산을 하는 코드를 볼 때
- 손으로 최적화한(hand-optimized) 문자열 처리 루틴이나 CTF의 커스텀 인코딩/해시 루틴을 분석할 때
- `lods` 뒤에 `AL`을 검사하는 `cmp`/`test`/`jcc`가 바로 이어지는 패턴을 볼 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
lodsb          ; AL  <- BYTE PTR [RSI]
lodsw          ; AX  <- WORD PTR [RSI]
lodsd          ; EAX <- DWORD PTR [RSI]
lodsq          ; RAX <- QWORD PTR [RSI]   (x64 전용)
```
오퍼랜드는 암묵적으로 `RSI`(소스 주소)와 `AL`/`AX`/`EAX`/`RAX`(목적지 레지스터)를 사용한다.

### 방향 및 레지스터 효과
- **소스**: `RSI`가 가리키는 메모리.
- **목적지**: `AL`/`AX`/`EAX`/`RAX` — 크기에 맞는 누산기 레지스터.
- 실행 후 `DF`(방향 플래그, REV-0080 참고)에 따라 `RSI`만 증가 또는 감소한다.
  - `DF=0`: `RSI += size`
  - `DF=1`: `RSI -= size`
- `RDI`는 `LODS`와 무관하며 변하지 않는다.

### 왜 REP와 잘 안 어울리는가
`REP LODSB`도 문법적으로는 가능하지만 실무에서는 거의 안 쓰인다. 이유는 간단하다 — `REP`로 반복시키면 매번 `AL`에 새 값이 덮어써지므로, **반복이 끝난 시점에는 마지막으로 읽은 1바이트만 `AL`에 남고 나머지는 다 사라진다.** `memcpy`처럼 "전체를 어딘가에 다 옮겨야" 의미가 있는 `MOVS`/`STOS`와 달리, `LODS`는 "읽은 값을 즉시 그 자리에서 써먹어야" 의미가 있는 명령이라서, 보통 `REP` 없이 **직접 만든 루프(`loop`, `dec`+`jnz`, 또는 조건 분기)** 안에 넣고 매 반복마다 `lodsb` 한 번 → 읽은 `AL` 검사/가공 → 다시 반복, 형태로 쓴다.

### 플래그 변화
`LODS`는 **플래그를 바꾸지 않는다.** 단순 로드이기 때문이다.

### 스택/RIP 변화
직접적인 영향 없음.

## 컴파일러 패턴 — "한 바이트씩 읽어서 즉시 처리하는 루프"로 인식하기
```asm
loop_start:
    lodsb                  ; AL = [RSI], RSI += 1
    test    al, al          ; NUL 문자인지 검사
    jz      loop_end
    ; ... AL로 뭔가 처리 (해시 갱신, 대소문자 변환, 카운트 등) ...
    jmp     loop_start
loop_end:
```
이 패턴은 C로 치면 대략:
```c
while (*p != '\0') {
    unsigned char c = *p++;
    // c로 무언가 처리
}
```
에 해당한다. 최신 컴파일러(GCC -O2, MSVC /O2)는 사실 `LODS`류를 잘 안 쓰고 일반 `mov al, [rsi]` + `inc rsi`로 풀어서 컴파일하는 경우가 더 흔하다 — `LODS`가 실제로 등장하면 (1) 손으로 짠 어셈블리, (2) 매우 오래된/비최적화 컴파일러 산출물, (3) 크랙미/CTF에서 의도적으로 삽입한 코드일 가능성이 높다.

## IDA/Ghidra 디컴파일에서 보이는 방식
`REP` 없는 단독 `lodsb` 루프는 함수 호출로 뭉쳐지지 않고, 대부분 그대로 **포인터 역참조 + 증가 + 조건 분기**로 이루어진 `while`/`for` 루프 형태의 C 코드로 디컴파일된다:
```c
while ( (c = *p++) != 0 ) {
    ...
}
```
IDA/Ghidra가 `memcpy`처럼 통째로 라이브러리 함수로 뭉뚱그려 인식하는 경우는 거의 없다 — 이 루프 안에서 `AL`로 무엇을 하는지가 실제 로직이므로 직접 읽어야 한다.

## 리버싱 관점에서의 의미
- `lodsb` + 조건 분기 조합은 **strlen, 문자열 파서, 커스텀 인코더/디코더, 간단한 해시 함수(체크섬)** 등에서 자주 보인다. CTF 크랙미에서 "입력 문자열을 한 글자씩 읽어 XOR/회전/누적합 등을 적용하는 검증 로직"의 전형적인 뼈대다.
- `RSI` 시작 주소를 확인하면 어떤 버퍼(보통 사용자 입력)를 순회하는지 알 수 있고, 루프 안에서 `AL`이 어떻게 쓰이는지 추적하면 검증 알고리즘 전체를 재구성할 수 있다.
- 루프 종료 조건(`test al, al` / `jz`, 또는 카운터 비교)을 확인하면 몇 바이트까지 처리하는지(전체 문자열 vs 고정 길이) 알 수 있다.

## 가장 먼저 할 것
`lods`/`lodsb`/`lodsd`(REP 없이 루프 안에 있는 경우가 대부분)를 봤다면 가장 먼저 확인할 것:
1. **이 명령이 어떤 루프 안에 있는가** — 루프의 시작/끝 레이블과 반복 조건(`dec`+`jnz`, `loop`, 비교+`jcc` 등)을 먼저 파악한다.
2. **`RSI`가 가리키는 시작 주소** — 어떤 버퍼(대개 사용자 입력 문자열)를 순회하는지.
3. **`lodsb` 직후 `AL`로 무엇을 하는지** — `test al,al`/`jz`로 끝을 검사하는지, 아니면 `xor`/`add`/`rol` 등으로 값을 가공하는지. 이게 바로 알고리즘의 본체이므로 반드시 읽어야 한다.

## 단계별 절차
1. IDA 그래프뷰에서 `lodsb`가 포함된 루프 블록 전체(시작 레이블부터 조건 분기로 되돌아가는 지점까지)를 먼저 눈으로 훑는다.
2. `lodsb` 직전에서 `RSI` 초기값이 어디서 오는지(함수 인자, 전역 버퍼 등) 역추적한다.
3. `lodsb` 직후 몇 줄을 읽으면서 `AL`이 어떤 연산에 쓰이는지 순서대로 적어둔다 — 이것이 곧 문자 단위 처리 알고리즘이다.
4. **F5로 디컴파일**해서 `while (*p) { ... }` 형태의 C 유사 루프로 재구성되었는지 확인하고, 어셈블리에서 읽은 연산과 대조한다.
5. 루프 종료 조건(`test al,al`/`jz` 또는 카운터 비교)을 확인해서 전체 문자열을 처리하는지, 고정 길이만 처리하는지 판단한다.
6. 알고리즘이 복잡해서 손으로 따라가기 힘들면, 루프 시작 지점에 브레이크포인트를 걸고(`F2`) 한 바퀴씩 `F9`/`F8`(Step Over)로 실행하며 매 반복마다 `AL`과 관련 누적 변수가 어떻게 바뀌는지 직접 관찰한다.

## 명령어/단축키
- IDA: `F5`(디컴파일), `X`(Xrefs to — RSI가 가리키는 버퍼가 어디서 채워지는지 추적), `F2`(브레이크포인트), `F9`(실행), `F8`(Step Over로 루프 한 바퀴씩)
- x64dbg: 루프 상단에 브레이크포인트를 걸고 `F9`로 반복 진입 → 우측 레지스터 패널에서 `AL`/`RSI` 값을 반복마다 기록, "Run to selection" 기능으로 특정 반복 횟수까지 빠르게 건너뛰기
- GDB/Pwndbg: `break *0x<루프시작주소>`, `commands`로 매 히트마다 `p $al` 자동 출력하도록 설정하거나, Pwndbg의 `context`로 루프를 돌 때마다 레지스터 변화를 관찰

## 흔한 실수
- `LODS`도 `MOVS`/`STOS`처럼 `REP`가 항상 붙어 있을 거라 기대하는 것 — 대부분 `REP` 없이 커스텀 루프 안에 있다.
- `AL`에 남은 값을 "이 루프가 다룬 전체 데이터"라고 착각하는 것 — `AL`은 매 반복마다 덮어써지는 임시 값일 뿐이고, 실제 결과는 루프 안에서 다른 변수(레지스터/메모리)에 누적되는 경우가 대부분이다.
- 이 루프를 `rep movsb`처럼 "그냥 복사"라고 지레짐작하고 안의 로직을 안 읽는 것 — `LODS` 루프는 안의 처리 로직이 핵심이므로 반드시 읽어야 한다.

## 막혔을 때 다음 체크
- `RSI`가 가리키는 시작 주소가 무엇인지 궁금하면 → 루프 진입 전 `RSI` 세팅 지점을 역추적(대개 함수 인자로 받은 문자열 포인터).
- 루프가 언제 끝나는지 궁금하면 → `lodsb` 직후의 `test`/`cmp`와 그에 따른 `jcc`를 확인.
- `AL`로 어떤 연산을 하는지 궁금하면 → 루프 바디에서 `AL`/`EAX`가 관여하는 `xor`/`add`/`rol` 등의 명령을 순서대로 따라간다 — 이게 곧 알고리즘이다.

## 미니 예제

**예제 1 — 직접 짠 strlen 스타일 루프**
```asm
    lea     rsi, [str]
    xor     ecx, ecx
count_loop:
    lodsb
    test    al, al
    jz      done
    inc     ecx
    jmp     count_loop
done:
    ; ecx = 문자열 길이
```

**예제 2 — 한 바이트씩 XOR 디코딩 (CTF에서 흔한 패턴)**
```asm
    lea     rsi, [enc_buf]
    lea     rdi, [dec_buf]
    mov     ecx, 20
decode_loop:
    lodsb
    xor     al, 0x5A
    stosb            ; 디코딩한 값을 바로 저장 (STOS와 조합되는 대표 사례)
    loop    decode_loop
```

**예제 3 — REP LODSB (문법적으로 가능하지만 실무에서 드묾)**
```asm
    lea     rsi, [buf]
    mov     rcx, 4
    rep lodsb          ; AL에는 buf의 마지막 바이트만 남는다 (앞의 3바이트는 버려짐)
```
이 예제는 "왜 `LODS`에 `REP`를 잘 안 쓰는지" 보여주기 위한 것으로, 실제 유용한 코드는 아니다.

**예제 4 — LODSD로 4바이트 단위 체크섬 누적**
```asm
    lea     rsi, [data]
    mov     rcx, 8         ; 8 * 4바이트 = 32바이트 처리
    xor     edx, edx        ; 누적 체크섬
sum_loop:
    lodsd
    add     edx, eax
    loop    sum_loop
    ; edx = 32바이트에 대한 단순 합 체크섬
```

## 관련 글
- [rev-0080-rep-prefix.md](./rev-0080-rep-prefix.md) — REP Prefix와 반복 문자열 명령
- [rev-0081-movs.md](./rev-0081-movs.md) — MOVS/MOVSB/MOVSW/MOVSD/MOVSQ
- [rev-0082-stos.md](./rev-0082-stos.md) — STOS/STOSB/STOSD/STOSQ (LODS+STOS 조합 패턴)
- [rev-0084-scas.md](./rev-0084-scas.md) — SCAS와 문자열 검색 패턴
- [rev-0085-cmps.md](./rev-0085-cmps.md) — CMPS와 문자열 비교 패턴

## 출처/검증
- `LODS`/`LODSB`/`LODSW`/`LODSD`/`LODSQ` 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "LODS/LODSB/LODSW/LODSD/LODSQ—Load String" 섹션 기준 (2026-09-08 검증).
- `REP LODS`가 실무에서 드문 이유(반복마다 누산기 덮어쓰기): 동 매뉴얼의 문자열 명령 일반 설명 및 일반적인 컴파일러/어셈블리 관례 기준.
