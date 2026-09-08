---
id: REV-0400
title: "BTC: 비트 토글하며 테스트"
slug: "rev-0400-btc"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - btc
  - BTC
  - Btc
  - btc 명령어
  - btc instruction
  - bit test and complement
  - 비트 토글
  - 비트 반전
  - "btc eax, 3"
  - toggle bit
  - flip bit
  - 플래그 토글
aliases:
  - btc 뭐임
  - btc가 뭐죠
  - BTC 명령어
  - 비트 토글 테스트 명령어
  - btc와 xor 차이
symptom_keywords:
  - btc eax 3이 뭔지 모르겠음
  - 비트를 켰다 껐다 하는 명령어를 모르겠음
  - 비트를 반전시키면서 이전값도 확인하는 명령어를 모르겠음
  - 토글 코드에서 btc를 봤는데 뭔지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`BTC`(Bit Test and Complement)는 지정한 비트의 **원래 값을 CF로 복사한 뒤, 그 비트를 반전(0↔1 토글)** 시키는 명령어다. BT 계열의 마지막 변형이다.

## 언제 검색해야 하나
- `btc eax, 3` 같은 코드를 만나서 [BTS](rev-0398-bts.md)/[BTR](rev-0399-btr.md)과 어떻게 다른지 궁금할 때
- 상태를 켰다 껐다 반복하는(toggle) 코드, 예를 들어 LED/체크박스/양방향 플래그 로직을 분석할 때
- `XOR eax, mask`로 비트를 토글하는 코드와 BTC의 차이가 궁금할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
BTC r/m16, r16
BTC r/m32, r32
BTC r/m64, r64
BTC r/m16/32/64, imm8
```
오퍼랜드 형식은 BT/BTS/BTR과 동일하다.

### 실제로 하는 일
```
CF   = (dest >> n) & 1     ; 원래 비트 값을 CF에 저장
dest = dest XOR (1 << n)   ; 그 비트만 반전(토글)
```
원래 0이었으면 1로, 원래 1이었으면 0으로 바뀐다. "지금 상태를 반대로 뒤집는" 연산이다.

### 플래그 변화
- **CF**: 수정 전 원래 비트 값 (즉, 반전 후 값은 CF의 반대라고 유추 가능)
- **OF, SF, ZF, AF, PF**: 정의되지 않음

### 스택/RSP/RIP 변화
없음.

### BTC vs XOR — 비슷해 보이지만 다른 점
`xor eax, mask`(mask에 해당 비트만 1로 설정된 상수)로도 특정 비트를 토글할 수 있다. 차이는:
- `XOR`는 **여러 비트를 한 번에** 토글할 수 있고(마스크에 여러 비트가 1이면), CF는 항상 0으로 클리어된다(토글 전 값 정보 없음).
- `BTC`는 **비트 하나만** 토글하지만, 그 비트가 토글 전에 무슨 값이었는지 CF로 정확히 알려준다. 또한 비트 위치를 **레지스터로 동적 지정**할 수 있다는 점이 XOR 상수 마스크 방식과 다르다.

컴파일러는 토글할 비트 번호가 런타임에 결정되는 경우(`bitmap ^= (1 << idx)`처럼 idx가 변수)에 BTC를 선택하는 경향이 있다.

### BT 계열 정리
- `BT` — 읽기 전용 ([REV-0397](rev-0397-bt.md))
- `BTS` — 읽고 1로 설정 ([REV-0398](rev-0398-bts.md))
- `BTR` — 읽고 0으로 해제 ([REV-0399](rev-0399-btr.md))
- `BTC` — 읽고 **반전/토글** (이 글)

네 명령 모두 dest가 메모리일 때 `LOCK` 접두사와 결합해 원자적 연산이 가능하다(`LOCK BTC`도 유효). 다만 실무에서는 BTS(설정/락 획득)와 BTR(해제/락 해제)이 압도적으로 더 자주 보이고, BTC는 진짜 "토글" 의미가 필요한 코드(상태 반전, 더블 버퍼링 인덱스 전환 등)에서 상대적으로 드물게 나타난다.

### 더블 버퍼링/핑퐁 인덱스 전환 패턴
그래픽/오디오 처리나 큐 구현에서 "현재 사용 중인 버퍼가 0번인지 1번인지"를 1비트로 관리하고, 매 프레임/매 처리마다 그 비트를 반전시켜 버퍼를 바꿔가며 쓰는 "더블 버퍼링(핑퐁 버퍼링)" 기법이 흔하다. 이럴 때 `btc eax, 0` 한 줄이 "지금 버퍼 인덱스를 반대로 바꾼다"는 뜻으로 반복문 안에 등장할 수 있다. 이런 코드를 만나면 근처에 두 개의 버퍼 포인터 배열이나 `buffers[idx]` 형태의 인덱싱이 있는지 확인해보면 도움이 된다.

## 화면/코드에서 보이는 징후
- `btc eax, 2` — 2번 비트를 반전시키며 이전 상태를 CF로 확인
- `btc eax, ecx` — 토글할 비트 번호가 변수(런타임 결정)
- BTC 직후 `jc` — "토글 전에 켜져 있었다면 분기"(즉 지금은 꺼진 상태가 됐다는 뜻)

## 가장 먼저 할 것
1. dest와 비트 위치(상수/레지스터) 확인
2. BTC 직후 CF 기반 분기가 있다면, "토글 전" 상태를 기준으로 해석 중임을 기억
3. 반복되는 토글 패턴(같은 비트를 여러 번 왔다갔다)인지 확인 — 상태 전환(state flip) 로직일 가능성

## 단계별 절차

**1) 상태 토글**
```asm
btc  eax, 0
mov  [state], eax
```
→ `state ^= 1;` (0번 비트만 반전)

**2) 토글 전 상태에 따른 분기**
```asm
btc  eax, ecx
jc   was_on_now_off
; CF=0이면 원래 꺼져 있었고 지금 켜진 것
```

## 명령어/단축키
- IDA/Ghidra 의사코드: `btc`는 대개 `value ^= (1 << n)` 형태로 정리된다.
- x64dbg/GDB: 실행 전후 dest 값을 비교해서 정확히 한 비트만 뒤집혔는지 확인한다.

## 출력 해석
- CF=1이면 토글 전에 그 비트가 1이었다는 뜻(반전 후 지금은 0).
- CF=0이면 토글 전에 그 비트가 0이었다는 뜻(반전 후 지금은 1).
- 여러 번 반복 실행되는 BTC를 디버거에서 관찰할 때는, 매 실행마다 CF 값이 이전 실행의 결과(즉 직전 반전 후 값)와 정반대로 나온다는 규칙성을 이용하면 몇 번째 반복인지도 추적할 수 있다(짝수 번째면 초기값과 같은 CF, 홀수 번째면 반대 CF).

## 흔한 실수
- BTC가 여러 비트를 한 번에 토글한다고 착각하는 것 — 오직 지정한 **하나의 비트**만 반전한다. 여러 비트를 한 번에 토글하려면 [XOR](rev-0057-xor.md)에 다중 비트 마스크를 써야 한다.
- CF를 "토글 후" 값으로 오해하는 것 — CF는 항상 **토글 전** 원래 값이다.
- BTC와 BTS/BTR을 혼동하는 것 — BTS는 무조건 1로, BTR은 무조건 0으로 만들지만 BTC는 원래 값의 반대로 만든다(원래 값에 의존적).
- 반복 실행되는 BTC를 보고 최종 상태를 헷갈리는 것 — 짝수 번 토글되면 원상태로 돌아오고, 홀수 번 토글되면 반전된 상태가 된다는 점을 놓치지 말 것.

## 막혔을 때 다음 체크
- CF 분기 의미가 헷갈리면 → "CF는 항상 수정 전 값" 규칙 재확인.
- BTC가 왜 쓰였는지 모르겠다면 → 근처 코드에서 이 비트가 반복적으로 켜졌다 꺼졌다 하는 상태 머신(state machine)이나 더블 버퍼링 로직이 있는지 확인.
- BT/BTS/BTR/BTC 구분이 헷갈리면 → 마지막 글자(없음=읽기전용, S=Set, R=Reset, C=Complement)로 기억.

## 미니 예제

**예제 1 — 불리언 상태 토글**
```c
void toggle_flag(unsigned *state, int idx) {
    *state ^= (1u << idx);
}
```
```asm
mov  eax, [state]
mov  ecx, idx
btc  eax, ecx
mov  [state], eax
```

**예제 2 — 토글 전 상태에 따라 다르게 처리**
```c
if (flags & (1 << 3)) {
    // 켜져 있었으므로 끄는 처리 실행
    on_turned_off();
}
flags ^= (1 << 3);
```
```asm
mov  eax, [flags]
btc  eax, 3
jnc  skip_notify     ; 토글 전 꺼져 있었으면 알림 불필요
call on_turned_off
skip_notify:
mov  [flags], eax
```

**예제 3 — 더블 버퍼링 인덱스 반전**
```c
int current_buffer = 0;
void swap_buffer(void) {
    current_buffer ^= 1;
}
```
```asm
mov  eax, [current_buffer]
btc  eax, 0
mov  [current_buffer], eax
```

## 관련 글
- REV-0397 — BT: 비트 테스트
- REV-0398 — BTS: 비트 설정하며 테스트
- REV-0399 — BTR: 비트 지우며 테스트
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화

## 출처/검증
- BTC 명령어의 오퍼랜드/플래그/원자성 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "BTC—Bit Test and Complement" 섹션 기준 (2026-09-08 검증).
