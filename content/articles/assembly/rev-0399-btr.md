---
id: REV-0399
title: "BTR: 비트 지우며 테스트"
slug: "rev-0399-btr"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - btr
  - BTR
  - Btr
  - btr 명령어
  - btr instruction
  - bit test and reset
  - 비트 해제
  - 비트 지우기
  - "btr eax, 3"
  - "lock btr"
  - atomic bit clear
  - 원자적 비트 해제
  - 스핀락 해제
  - spinlock release
aliases:
  - btr 뭐임
  - btr가 뭐죠
  - BTR 명령어
  - 비트 지우기 테스트 명령어
  - lock btr가 뭔지
symptom_keywords:
  - btr eax 3이 뭔지 모르겠음
  - lock btr가 왜 나오는지 모르겠음
  - 비트를 끄면서 이전값도 확인하는 명령어를 모르겠음
  - 스핀락 해제 코드에서 btr을 봤는데 뭔지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`BTR`(Bit Test and Reset)는 지정한 비트의 **원래 값을 CF로 복사한 뒤, 그 비트를 강제로 0으로 해제(reset)** 하는 명령어다. [BTS](rev-0398-bts.md)의 정반대(설정 대신 해제) 버전이다.

## 언제 검색해야 하나
- `btr eax, 3` 같은 코드를 보고 [BTS](rev-0398-bts.md)와 무엇이 다른지 궁금할 때
- 락(lock) 해제 코드나 플래그 초기화 코드에서 `lock btr`을 만났을 때
- 비트셋의 `clear()`/`reset()` 함수가 어셈블리로 어떻게 나오는지 알고 싶을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
BTR r/m16, r16
BTR r/m32, r32
BTR r/m64, r64
BTR r/m16/32/64, imm8
```
오퍼랜드 형식은 [BT](rev-0397-bt.md)/[BTS](rev-0398-bts.md)와 동일하다 — dest(검사·수정할 값), src(비트 위치).

### 실제로 하는 일
```
CF   = (dest >> n) & 1        ; 원래 비트 값을 CF에 저장
dest = dest & ~(1 << n)       ; 그 비트를 0으로 강제 해제
```
BTS가 `OR`로 비트를 켜는 것과 대칭적으로, BTR은 `AND NOT`(비트 마스크에서 해당 비트만 뺀 값과 AND)으로 비트를 끈다.

### 플래그 변화
- **CF**: 수정 전 원래 비트 값
- **OF, SF, ZF, AF, PF**: 정의되지 않음

### 스택/RSP/RIP 변화
없음.

### LOCK 접두사와 원자적 비트 해제 — 락 해제(release) 패턴
`LOCK BTR`은 스핀락/뮤텍스를 **해제(release)** 할 때 흔히 쓰인다. [BTS](rev-0398-bts.md)로 락을 잡았다면, BTR로 락을 놓는다:
```asm
lock btr dword ptr [lock_flag], 0   ; 락 비트를 원자적으로 0으로 해제
```
BTS와 짝을 이뤄 "락 획득/해제" 쌍을 이루는 경우가 많으므로, 한쪽을 발견하면 반드시 짝이 되는 다른 쪽도 코드 어딘가에 있는지 xref로 찾아보는 것이 동시성 로직을 이해하는 데 도움이 된다.

### BT 계열에서 BTR의 위치
| 명령 | dest 수정 여부 | 수정 방식 | CF에 담기는 값 |
|---|---|---|---|
| `BT` ([REV-0397](rev-0397-bt.md)) | 수정 안 함 | 없음(읽기 전용) | 원래 비트 값 |
| `BTS` ([REV-0398](rev-0398-bts.md)) | 수정함 | 무조건 1로 설정 | 수정 전 값 |
| `BTR` (이 글) | 수정함 | 무조건 0으로 해제 | 수정 전 값 |
| `BTC` ([REV-0400](rev-0400-btc.md)) | 수정함 | 반전(토글) | 수정 전 값 |

네 명령 모두 오퍼랜드 형식과 비트 위치 지정 방식(즉시값 또는 레지스터, 레지스터 dest일 때 오퍼랜드 크기로 모듈로 처리)이 완전히 동일하며, 차이는 오직 "수정 후 그 비트가 어떤 값이 되는가"에만 있다.

### 참조 카운트/자원 반납 패턴에서의 BTR
비트맵으로 자원 풀(예: 스레드 풀 슬롯, 페이지 프레임, 핸들 테이블 인덱스)을 관리하는 코드에서는 "이 슬롯을 반납한다"는 동작이 곧 해당 비트를 0으로 되돌리는 것과 같다. 이런 코드에서 `BTR`이 반복문 없이 단발성으로 등장한다면, 대개 "인덱스 하나를 반납/해제"하는 함수(예: `free_slot(idx)`, `release_handle(idx)`)일 가능성이 높다 — 함수 이름이 난독화되어 있어도 이 패턴만으로 기능을 추정할 수 있다.

## 화면/코드에서 보이는 징후
- `btr eax, 2` — 2번 비트를 끄면서 이전 상태를 CF로 확인
- `lock btr [rdi], eax` — 원자적 비트 해제, 락 해제/플래그 초기화 코드 의심
- BTR 직후 `jc` — "원래 켜져 있었다면 분기"(끄기 전 상태에 따른 후처리)

## 가장 먼저 할 것
1. LOCK 접두사 여부 확인
2. dest와 비트 위치(상수/레지스터) 확인
3. BTR 직후 CF 기반 분기 의미(원래 켜져 있었는가?) 해석
4. 근처에 대응되는 BTS(락 획득)가 있는지 xref로 확인

## 단계별 절차

**1) 비트 플래그를 끄면서 원래 상태 확인**
```asm
btr  eax, ecx
jnc  was_already_clear
; 여기 도달하면 원래 켜져 있었고 방금 껐다는 뜻
```

**2) 원자적 락 해제 패턴**
```asm
; 임계 구역 종료
lock btr dword ptr [lock], 0   ; 락 해제
```

**3) 자원 풀에서 인덱스 반납**
```asm
mov  eax, [pool_bitmap]
btr  eax, idx        ; idx번 슬롯을 사용 중(1) -> 미사용(0)으로 되돌림
mov  [pool_bitmap], eax
```
→ `pool_bitmap &= ~(1 << idx);` — "idx번 자원을 반납했다"는 의미.

## 명령어/단축키
- IDA/Ghidra 의사코드: `btr` 단독은 `value &= ~(1 << n)` 형태로 정리된다.
- x64dbg/GDB: 실행 전후 dest 값과 CF를 비교해서 "지워지기 전 값"을 확인한다.

## 출력 해석
- CF=1이면 지우기 전 그 비트가 켜져 있었다는 뜻(그리고 지금은 확실히 꺼짐).
- CF=0이면 원래도 꺼져 있었다는 뜻(연산이 사실상 no-op).
- 디버거로 `lock btr` 실행 전후 메모리 값을 비교할 때는, 다른 스레드가 동시에 같은 주소를 건드릴 수 있으므로 단일 스텝 실행 중에도 값이 예상과 다르게 보일 수 있다는 점을 감안해야 한다 — 이는 원자적 연산 자체의 문제가 아니라 디버거로 관찰하는 시점과 다른 스레드의 실행이 겹치기 때문이다.

## 흔한 실수
- BTR을 BT처럼 읽기 전용이라 착각하는 것 — BTR은 dest를 반드시 수정한다(해당 비트를 0으로).
- CF를 "해제 후" 값으로 착각하는 것 — CF는 항상 **수정 전** 값이다.
- BTR과 [AND](rev-0055-and.md)를 동일시하는 것 — 결과적으로 비트를 끈다는 점은 같지만, BTR은 이전 값을 CF로 돌려주고 LOCK과 결합해 원자적 해제가 가능하다는 점이 다르다.
- BTS(락 획득)만 보고 BTR(락 해제)이 코드 어딘가에 반드시 있어야 한다는 점을 놓치는 것 — 짝이 안 맞으면 데드락 버그를 의심해볼 수 있다.

## 막혔을 때 다음 체크
- CF 분기 의미가 헷갈리면 → "CF는 항상 수정 전 값" 규칙 재확인.
- `lock btr`이 왜 있는지 모르겠다면 → 앞서 나온 `lock bts`(락 획득)와 짝을 이루는지, 함수의 진입/종료 지점에 각각 위치하는지 확인.
- BT/BTS/BTR/BTC 구분이 헷갈리면 → 마지막 글자(없음=읽기전용, S=Set, R=Reset, C=Complement)로 기억.
- 자원 풀 반납 함수인지 확신이 안 서면 → 대응되는 "할당" 함수(비트맵에서 빈 슬롯을 찾아 BTS로 켜는 코드)가 같은 파일/모듈 안에 있는지 찾아 짝을 맞춰본다.

## 미니 예제

**예제 1 — 비트셋에서 특정 인덱스 끄기**
```c
void clear_bit(unsigned *bitmap, int idx) {
    *bitmap &= ~(1u << idx);
}
```
```asm
mov  eax, [bitmap]
mov  ecx, idx
btr  eax, ecx
mov  [bitmap], eax
```

**예제 2 — 원자적 스핀락 해제**
```c
__sync_lock_release(&lock);
```
```asm
lock btr dword ptr [lock], 0
```

## 관련 글
- REV-0397 — BT: 비트 테스트
- REV-0398 — BTS: 비트 설정하며 테스트
- REV-0400 — BTC: 비트 토글하며 테스트
- REV-0055 — AND: 마스크와 비트 제거
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교

## 출처/검증
- BTR 명령어의 오퍼랜드/플래그/원자성 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "BTR—Bit Test and Reset" 및 Volume 3A "Locked Atomic Operations" 섹션 기준 (2026-09-08 검증).
