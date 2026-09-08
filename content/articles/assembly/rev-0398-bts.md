---
id: REV-0398
title: "BTS: 비트 설정하며 테스트"
slug: "rev-0398-bts"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - bts
  - BTS
  - Bts
  - bts 명령어
  - bts instruction
  - bit test and set
  - 비트 설정
  - "bts eax, 3"
  - "lock bts"
  - atomic bit set
  - 원자적 비트 설정
  - 스핀락 비트
  - spinlock bit set
aliases:
  - bts 뭐임
  - bts가 뭐죠
  - BTS 명령어
  - 비트 설정 테스트 명령어
  - lock bts가 뭔지
symptom_keywords:
  - bts eax 3이 뭔지 모르겠음
  - lock bts가 왜 나오는지 모르겠음
  - 비트를 켜면서 이전값도 확인하는 명령어를 모르겠음
  - 스핀락 코드에서 bts를 봤는데 뭔지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`BTS`(Bit Test and Set)는 지정한 비트의 **원래 값을 CF로 복사한 뒤, 그 비트를 강제로 1로 설정(set)** 하는 명령어다. "이 비트가 이미 켜져 있었나?"와 "지금부터 켜져 있게 만들기"를 한 번에 처리한다.

## 언제 검색해야 하나
- `bts eax, 3` 같은 코드를 보고 [BT](rev-0397-bt.md)와 뭐가 다른지 궁금할 때
- `lock bts` 처럼 `LOCK` 접두사가 붙은 코드를 커널 드라이버나 락(lock) 관련 코드에서 만났을 때
- 비트셋(bitset) 자료구조의 `set()` 함수가 어셈블리로 어떻게 컴파일되는지 알고 싶을 때
- CF가 켜지는데 원본 값도 동시에 바뀌는 코드를 보고 혼란스러울 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
BTS r/m16, r16
BTS r/m32, r32
BTS r/m64, r64
BTS r/m16/32/64, imm8
```
[BT](rev-0397-bt.md)와 오퍼랜드 형식이 완전히 같다 — dest(검사·수정할 값), src(비트 위치, 즉시값 또는 레지스터).

### 실제로 하는 일
```
CF   = (dest >> n) & 1     ; 원래 비트 값을 먼저 CF에 저장
dest = dest | (1 << n)     ; 그 다음 해당 비트를 1로 설정
```
즉 BT와 마찬가지로 **원래 값을 CF에 남기지만**, BT와 달리 **dest 자체도 수정한다** — 지정한 비트를 무조건 1로 만든다. "테스트하면서 동시에 설정한다"는 이름 그대로다.

### 플래그 변화
- **CF**: 수정 전 원래 비트 값
- **OF, SF, ZF, AF, PF**: 정의되지 않음

### 스택/RSP/RIP 변화
없음.

### LOCK 접두사와 원자적(atomic) 비트 설정
`BTS`는 `LOCK` 접두사(`lock bts [addr], eax`)와 함께 쓰이면 메모리 상의 해당 비트를 **원자적으로(다른 CPU 코어가 끼어들 수 없게)** 읽고-설정한다. 이는 멀티스레드/커널 환경에서 "이 비트를 내가 먼저 켰는가"를 판단하는 매우 흔한 저수준 락(lock) 구현 패턴이다:
```asm
lock bts [lock_var], 0
jc   already_locked   ; CF=1이면 이미 누군가 비트를 켜놨던 것 -> 락 획득 실패
; CF=0이면 내가 최초로 비트를 켠 것 -> 락 획득 성공
```
`LOCK BTS`가 보인다면 스핀락(spinlock), 뮤텍스 내부 구현, 커널 동기화 프리미티브, 혹은 `std::atomic`/`std::bitset` 계열 라이브러리 코드일 가능성이 높다. 리버싱 관점에서 이건 "이 코드가 멀티스레드 안전성을 신경 쓰고 있다"는 강력한 신호다.

### BT/BTS/BTR/BTC 계열에서 BTS의 위치
- `BT` — 읽기 전용 (아무것도 안 바꿈)
- `BTS` — 읽고 **1로 설정(Set)**
- `BTR` — 읽고 **0으로 해제(Reset)** ([REV-0399](rev-0399-btr.md))
- `BTC` — 읽고 **반전(Complement/토글)** ([REV-0400](rev-0400-btc.md))

네 명령 모두 CF에 "수정 전" 원래 값을 담아준다는 공통점이 있다.

### 자원 풀에서 슬롯 할당 패턴
비트맵으로 자원(스레드 풀 슬롯, 페이지 프레임, 핸들 테이블 인덱스 등)을 관리하는 코드에서 `BTS`는 "이 인덱스를 사용 중으로 표시한다"는 할당 동작으로도 자주 쓰인다. 보통 먼저 비어있는(0인) 비트를 BSF(비트 스캔) 같은 명령으로 찾은 뒤, 그 인덱스에 BTS로 1을 세팅해 "이 슬롯은 이제 사용 중"이라고 표시하는 흐름이 이어진다. 이런 코드가 보이면 자원 할당자(allocator) 내부 구현일 가능성이 높다.

## 화면/코드에서 보이는 징후
- `bts eax, 2` — 2번 비트를 켜면서 이전 상태를 CF로 확인
- `lock bts [rdi], eax` — 원자적 비트 설정, 락/플래그 동기화 코드 의심
- BTS 직후 `jc` — "이미 켜져 있었다면 분기"(중복 설정 방지, 락 실패 처리 등)

## 가장 먼저 할 것
1. LOCK 접두사가 붙어 있는지 확인 (붙어 있으면 동시성/락 관련 코드로 우선 의심)
2. dest와 비트 위치(상수/레지스터) 확인
3. BTS 직후 CF 기반 분기의 의미(이미 켜져 있었는가?) 해석

## 단계별 절차

**1) 비트 플래그를 켜면서 중복 여부 확인**
```asm
bts  eax, ecx
jc   already_set
; 여기 도달하면 원래 꺼져 있었고 방금 켰다는 뜻
```

**2) 원자적 락 획득 패턴**
```asm
lock bts dword ptr [lock_flag], 0
jc   spin_wait      ; 다른 스레드가 이미 잡고 있음
; 락 획득 성공, 임계 구역 진입
```

## 명령어/단축키
- IDA/Ghidra 의사코드: `bts` 단독은 `value |= (1 << n)` 형태로, `lock bts` + `jc`는 원자적 CAS/spinlock 패턴으로 종종 별도 표시되거나 그대로 인라인 어셈블리 형태로 남아 디컴파일이 완전히 정리되지 않을 수 있다.
- x64dbg/GDB: 실행 후 CF와 dest 레지스터/메모리 값을 함께 확인해서 "이전 값"과 "설정 후 값"을 비교하면 동작이 명확해진다.

## 출력 해석
- CF=1이고 dest의 해당 비트가 1이면: 원래도 켜져 있었고, 지금도 켜져 있음(설정은 사실상 no-op이었음).
- CF=0이고 dest의 해당 비트가 1이면: 원래 꺼져 있었는데 이번에 처음 켜짐 — 이 전이(0→1) 자체가 의미 있는 이벤트인 경우가 많다(락 획득, 최초 초기화 등).

## 흔한 실수
- BTS를 BT처럼 "읽기 전용"이라고 착각하는 것 — BTS는 반드시 dest를 수정한다(해당 비트를 1로).
- CF가 "설정 후" 값이라고 착각하는 것 — CF는 항상 **수정 전** 원래 값이다. 설정 후 값은 항상 1이므로 CF로 확인할 이유가 없다.
- `lock` 접두사를 단순 문법적 장식으로 넘기는 것 — `LOCK BTS`는 실제 하드웨어 버스/캐시 라인 수준의 원자성을 보장하며, 이게 빠지면 멀티코어 환경에서 레이스 컨디션이 발생한다. 리버싱 중 `LOCK`이 있고 없고는 동시성 버그 분석에서 중요한 단서다.
- BTS와 [OR](rev-0056-or.md)을 완전히 동일하다고 생각하는 것 — 결과적으로 비트를 켠다는 점은 같지만, BTS는 이전 값을 CF로 알려주고 LOCK과 결합해 원자적으로 동작할 수 있다는 점에서 OR과 용도가 다르다.

## 막혔을 때 다음 체크
- CF 분기 의미가 헷갈리면 → "CF는 항상 수정 전 값"이라는 규칙부터 다시 확인.
- `lock bts`가 있는데 왜 있는지 모르겠다면 → 이 코드 주변에 스레드 생성(`CreateThread`, `pthread_create`) 또는 뮤텍스/스핀락 관련 함수 호출이 있는지 xref로 확인.
- BTS/BTR/BTC 중 무엇인지 헷갈리면 → 니모닉 마지막 글자(S=Set, R=Reset, C=Complement)로 구분.

## 미니 예제

**예제 1 — 비트셋에서 특정 인덱스 켜기**
```c
void set_bit(unsigned *bitmap, int idx) {
    *bitmap |= (1u << idx);
}
```
```asm
mov  eax, [bitmap]
mov  ecx, idx
bts  eax, ecx
mov  [bitmap], eax
```

**예제 2 — 원자적 스핀락 획득**
```c
while (__sync_lock_test_and_set(&lock, 1)) {
    // busy wait
}
```
```asm
acquire:
lock bts dword ptr [lock], 0
jc   acquire        ; 이미 잠겨 있으면 재시도
; 임계 구역
```

**예제 3 — 자원 풀에서 빈 슬롯을 할당하고 표시**
```c
int allocate_slot(unsigned *bitmap) {
    for (int i = 0; i < 32; i++) {
        if (!(*bitmap & (1u << i))) {
            *bitmap |= (1u << i);
            return i;
        }
    }
    return -1;
}
```
```asm
mov   eax, [bitmap]
mov   ecx, 0
find_free:
    bts   eax, ecx
    jnc   found        ; CF=0이면 원래 비어있던 슬롯을 방금 표시함
    inc   ecx
    cmp   ecx, 32
    jl    find_free
    mov   eax, -1
    jmp   done
found:
    mov   [bitmap], eax
    mov   eax, ecx
done:
```

## 관련 글
- REV-0397 — BT: 비트 테스트
- REV-0399 — BTR: 비트 지우며 테스트
- REV-0400 — BTC: 비트 토글하며 테스트
- REV-0056 — OR: 비트 설정
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교

## 출처/검증
- BTS 명령어의 오퍼랜드/플래그/원자성 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "BTS—Bit Test and Set" 및 Volume 3A "Locked Atomic Operations" 섹션 기준 (2026-09-08 검증).
