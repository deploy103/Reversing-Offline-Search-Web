---
id: REV-0404
title: "XLAT: 테이블 변환 명령"
slug: "rev-0404-xlat"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - xlat
  - XLAT
  - xlatb
  - XLATB
  - xlat 명령어
  - xlat instruction
  - table lookup
  - 테이블 변환
  - 룩업 테이블
  - lookup table
  - AL BX 변환
  - substitution table
  - 치환 테이블
aliases:
  - xlat 뭐임
  - xlatb가 뭐죠
  - XLAT 명령어
  - 테이블 변환 명령어
  - xlat 룩업 테이블
symptom_keywords:
  - xlatb가 뭔지 모르겠음
  - al bx로 메모리를 읽는 이유를 모르겠음
  - 치환 테이블 코드가 뭔지 모르겠음
  - crc 테이블 조회 코드에서 xlat을 봤는데 뭔지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`XLAT`(Table Look-up Translation)은 **`AL`의 현재 값을 인덱스로 삼아, `BX`/`EBX`/`RBX`가 가리키는 256바이트 테이블에서 그 위치의 바이트를 읽어와 다시 `AL`에 저장**하는, 바이트 단위 룩업 테이블 전용 명령이다.

## 언제 검색해야 하나
- `xlat` 또는 `xlatb` 명령어를 만났는데 오퍼랜드가 없어서 뭘 하는지 모를 때
- 대문자↔소문자 변환, 문자 치환(substitution cipher), CRC 룩업 테이블 조회 같은 코드에서 이 명령을 만났을 때
- 크랙미(crackme)나 난독화된 코드에서 "값이 어디선가 테이블을 거쳐 바뀌는" 패턴을 봤을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
XLAT           ; 오퍼랜드 없음 (실제로는 항상 AL, BX 암묵적 사용)
XLATB          ; XLAT과 완전히 동일, 어셈블러가 명확성을 위해 주로 이 이름을 씀
```
- 겉보기엔 오퍼랜드가 없는 것처럼 보이지만, 실제로는 **암묵적으로 AL과 BX(32/64비트 모드에서는 EBX/RBX)를 사용**한다.
- 매우 드물게 `XLAT m8` 형태로 테이블의 세그먼트를 명시하는 옛 문법도 존재하지만(세그먼트 오버라이드 접두사와 결합), 현대 x86/x64 코드에서는 사실상 `XLATB`만 쓰인다고 봐도 무방하다.

### 실제로 하는 일
```
AL = [(E/R)BX + (unsigned)AL]
```
1. 현재 `AL`의 값을 **부호 없는 인덱스(0~255)** 로 취급한다.
2. `BX`/`EBX`/`RBX`가 가리키는 주소에 그 인덱스를 더한 위치에서 1바이트를 읽는다.
3. 읽어온 바이트를 다시 `AL`에 저장한다(원래 AL 값은 사라진다 — 입력이자 동시에 출력).

즉 `RBX`는 "256개 항목짜리 변환 테이블"의 시작 주소 역할을 하고, `AL`은 "입력값이자 결과값"이다.

### 플래그 변화
**없음.** 어떤 플래그도 건드리지 않는다.

### 스택/RSP/RIP 변화
없음.

### 왜 이 명령이 존재하는가 — 룩업 테이블 치환의 하드웨어 지원
`XLAT`은 8086 시절부터 있던 명령으로, "입력 바이트 하나를 미리 정해둔 256바이트 표에 따라 다른 바이트로 바꾼다"는 연산을 **1개 명령으로** 처리하기 위해 만들어졌다. 이런 변환은 다음과 같은 곳에서 자주 필요하다:
- **대소문자 변환(toupper/tolower)**: 테이블의 각 위치에 이미 변환된 문자를 미리 채워두면, 입력 바이트를 인덱스 삼아 XLAT 한 번으로 변환 완료.
- **문자 치환 암호(substitution cipher)**: 간단한 아스키 치환형 인코딩/난독화에서 "치환표"를 그대로 XLAT용 룩업 테이블로 사용.
- **CRC/체크섬 계산**: CRC8류 알고리즘의 사전 계산된 룩업 테이블 조회.
- **문자 인코딩 변환**: EBCDIC↔ASCII 같은 구식 문자 집합 변환.

현대 컴파일러는 최적화 시 이런 변환을 대개 `movzx`+메모리 인덱싱(`mov al, [table + rax]`)으로 풀어써서 XLAT을 거의 생성하지 않지만, XLAT과 이 방식은 결과적으로 동일한 일을 한다 — 그래서 XLAT을 몰라도 `mov al, [rbx + rax]` 형태의 코드를 보면 "룩업 테이블 치환"이라는 같은 패턴임을 알아챌 수 있어야 한다.

### 리버싱 관점에서의 의미
디스어셈블리에서 `xlat`/`xlatb`가 보인다면, 이는 **매우 강력한 신호**다: "지금 이 코드는 입력 바이트를 고정된 256바이트 표를 통해 변환하고 있다." 크랙미/CTF에서 이런 코드를 만나면:
1. `RBX`(또는 `EBX`)가 가리키는 주소로 가서 그 256바이트 데이터를 덤프한다(IDA에서 해당 주소로 이동 후 데이터로 변환, 또는 x64dbg의 Dump 창에서 확인).
2. 그 256바이트를 배열로 추출하면, 이것이 바로 "치환 테이블"이다 — 정방향(암호화) 테이블이면, 인덱스와 값을 뒤집어서(역함수 계산) 복호화 테이블도 만들 수 있다.
3. 이후 전체 로직은 "입력 각 바이트를 이 표로 치환"하는 단순 반복이므로, 파이썬 등으로 테이블만 추출하면 전체 알고리즘을 손쉽게 재현할 수 있다.

## 화면/코드에서 보이는 징후
- `xlatb` 단독 명령, 직전에 `mov al, [buf + i]`(입력 바이트 로드)와 `lea rbx, [table]`(테이블 주소 로드)가 선행
- 반복문 안에서 `xlatb`가 매 반복마다 실행 — 버퍼 전체를 한 바이트씩 테이블로 치환하는 루프
- `mov al, [rbx + rax]` 형태(오퍼랜드로 풀어쓴 XLAT의 컴파일러 버전) — RBX가 고정 테이블 주소이고 RAX/AL이 매번 바뀌는 인덱스일 때

## 가장 먼저 할 것
1. RBX/EBX가 가리키는 주소 확인 → 그 주소의 데이터(256바이트)를 룩업 테이블로 추출
2. XLAT을 감싸는 반복문이 있는지 확인 → 버퍼 전체를 치환하는 구조인지 파악
3. 테이블 내용을 덤프해서 알려진 패턴(ASCII 순열, 특정 암호 S-box 등)과 비교

## 단계별 절차

**1) 룩업 테이블 위치 특정**
```asm
lea   rbx, [rip + subst_table]   ; 테이블 시작 주소를 rbx에 로드
```
IDA에서 `subst_table`로 이동해 256바이트를 배열(byte[256])로 변환한다(단축키 `*` 또는 우클릭 → Array).

**2) 변환 루프 해석**
```asm
lea   rbx, [subst_table]
lea   rsi, [input]
lea   rdi, [output]
mov   ecx, len
conv_loop:
    lodsb            ; al = [rsi], rsi += 1
    xlatb             ; al = [rbx + al]
    stosb             ; [rdi] = al, rdi += 1
    loop  conv_loop
```
→ `for (i=0;i<len;i++) output[i] = table[input[i]];`

**3) 테이블 추출 후 알고리즘 재현**
디버거나 IDA에서 `subst_table`의 256바이트를 그대로 복사해 파이썬 리스트로 만들면, `output = bytes(table[b] for b in input)`로 동일한 변환을 재현할 수 있다.

## 명령어/단축키
- IDA: 테이블 주소에서 `*`(별표) 또는 우클릭 → Array로 256바이트를 배열로 정리하면 표 전체를 한눈에 볼 수 있다.
- x64dbg: Dump 창에 RBX 주소를 입력해 256바이트를 헥스로 확인, 우클릭 → "Follow in Dump"로 빠르게 이동.
- GDB/Pwndbg: `x/256bx $rbx`로 테이블 256바이트를 헥스 덤프.

## 출력 해석
- XLAT 실행 전후 AL 값을 비교하면 "입력 바이트 → 변환된 바이트"의 한 쌍을 바로 확인할 수 있다.
- 여러 번 실행해서 (입력, 출력) 쌍을 모으면 테이블 전체를 실행 기반으로도 복원할 수 있다(정적 추출이 어려운 경우의 대안).

## 흔한 실수
- `xlat`을 산술 연산 명령으로 착각하는 것 — 계산이 아니라 순수 메모리 조회(lookup)다.
- AL이 인덱스이면서 동시에 결과값이라는 점을 놓치는 것 — 실행 후 원래 AL(입력값)은 사라지고 조회된 값으로 완전히 대체된다.
- 테이블 크기를 임의로 가정하는 것 — AL은 항상 0~255 범위이므로 XLAT이 참조하는 테이블은 항상 정확히 **256바이트**여야 한다(더 작으면 테이블 밖 메모리를 읽는 버그가 될 수 있음).
- RBX가 스택 프레임 주소라고 착각하는 것 — RBX는 여기서 콜리 세이브 레지스터가 아니라 전적으로 "테이블 베이스 주소"로 쓰이고 있다. 함수 진입부에서 RBX가 무엇으로 초기화됐는지 반드시 확인해야 한다.

## 막혔을 때 다음 체크
- RBX가 가리키는 주소를 못 찾겠다면 → 함수 시작 부분에서 `lea rbx, [...]` 또는 `mov rbx, ...` 형태로 RBX가 초기화되는 지점을 위로 거슬러 찾는다.
- 테이블 내용이 이해가 안 되면 → 256바이트를 전부 덤프해서 항등 치환(table[i]==i)에서 얼마나 벗어나 있는지 눈으로 비교해본다(단순 시프트/캐사르식 치환이면 패턴이 바로 보인다).
- XLAT 대신 `mov al, [rbx+rax]` 형태로 컴파일러가 풀어썼다면 → 개념은 완전히 동일하니 위 절차를 그대로 적용한다.

## 미니 예제

**예제 1 — 단순 문자 치환**
```c
unsigned char table[256] = { /* ... */ };
unsigned char c = input;
unsigned char result = table[c];
```
```asm
mov   al, input
lea   rbx, [table]
xlatb
mov   result, al
```

**예제 2 — 버퍼 전체 치환 루프**
```c
for (int i = 0; i < len; i++) {
    out[i] = table[in[i]];
}
```
```asm
lea   rbx, [table]
lea   rsi, [in]
lea   rdi, [out]
mov   ecx, len
loop_top:
    lodsb
    xlatb
    stosb
    loop  loop_top
```

## 관련 글
- REV-0083 — LODS 문자열 로드 명령
- REV-0082 — STOS STOSB STOSD STOSQ
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0401 — LOOP: 카운터 기반 반복 명령

## 출처/검증
- XLAT/XLATB 명령어의 오퍼랜드/동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "XLAT/XLATB—Table Look-up Translation" 섹션 기준 (2026-09-08 검증).
