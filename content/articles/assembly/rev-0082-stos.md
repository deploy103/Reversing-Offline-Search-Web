---
id: REV-0082
title: "STOS STOSB STOSD STOSQ"
slug: "rev-0082-stos"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - stos
  - STOS
  - stosb
  - STOSB
  - stosw
  - STOSW
  - stosd
  - STOSD
  - stosq
  - STOSQ
  - rep stosb
  - rep stosd
  - rep stosq
  - string store
  - 문자열 저장 명령
  - memset
  - 메모리 채우기
  - buffer zero
  - 버퍼 초기화
  - RDI AL EAX
aliases:
  - stosb가 뭐임
  - stosd 뭐죠
  - rep stosb 뭐임
  - 어셈블리 memset
  - 메모리 채우기 명령어
  - 버퍼 0으로 채우기 어셈블리
symptom_keywords:
  - rep stosb 루프 이해가 안 됨
  - rdi가 계속 증가하며 값을 쓰는 코드
  - memset 대신 이상한 어셈블리가 보임
  - 스택 버퍼가 0으로 채워지는 코드를 못찾음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`STOS`(및 `STOSB`/`STOSW`/`STOSD`/`STOSQ`)는 `AL`/`AX`/`EAX`/`RAX`에 들어있는 값을 `[RDI]`가 가리키는 메모리에 반복해서 써 넣고 `RDI`를 자동으로 전진(또는 후진)시키는 명령이다. `REP` 접두사와 함께 쓰이면 `memset(dest, value, n)`을 통째로 대체하는 고속 반복 채우기 루프가 되며, 스택 버퍼를 0으로 초기화하는 컴파일러 생성 코드에서 매우 흔하게 등장한다.

## 언제 검색해야 하나
- `rep stosb`, `rep stosd`, `rep stosq` 코드가 함수 진입부에서 보이는데 무슨 뜻인지 모를 때
- 지역 변수/버퍼를 0으로 초기화하는 것 같은데 `memset` 호출이 안 보여서 어디서 초기화되는지 못 찾을 때
- `xor eax, eax` 다음에 `rep stosd`가 나오는 패턴을 봤을 때
- IDA가 이 블록을 `memset(...)`으로 바꿔 보여줬는데 원본과 안 맞는 것 같을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
stosb          ; BYTE PTR [RDI] <- AL
stosw          ; WORD PTR [RDI] <- AX
stosd          ; DWORD PTR [RDI] <- EAX
stosq          ; QWORD PTR [RDI] <- RAX   (x64 전용)
```
오퍼랜드는 암묵적으로 `AL`/`AX`/`EAX`/`RAX`(값)와 `RDI`(주소)를 사용한다.

### 방향 및 레지스터 효과 (destination만 사용, 소스는 레지스터)
`STOS`는 `MOVS`와 달리 **소스가 메모리(`RSI`)가 아니라 레지스터(`RAX` 계열)**라는 점이 핵심 차이다.
- **값(소스)**: `AL`(1바이트) / `AX`(2바이트) / `EAX`(4바이트) / `RAX`(8바이트) — 채워 넣을 값.
- **목적지**: `RDI`가 가리키는 메모리.
- 매 반복마다 값을 `[RDI]`에 쓴 뒤, `DF`(방향 플래그, REV-0080 참고)에 따라 `RDI`만 증가 또는 감소한다(`RSI`는 `STOS`와 무관하므로 변하지 않는다).
  - `DF=0`: `RDI += size`
  - `DF=1`: `RDI -= size`
- `REP` 접두사가 붙으면 `RCX`가 반복 횟수 카운터가 되어, `RCX`번 이 동작을 반복한다.

### 플래그 변화
`STOS`도 `MOVS`와 마찬가지로 **플래그를 전혀 바꾸지 않는다.** 단순 저장 동작이기 때문이다.

### 스택/RIP 변화
직접적인 영향 없음. 단, `STOS`로 채우는 대상 메모리가 **스택 위(로컬 변수 영역)**인 경우가 매우 흔하므로 "스택에 어떤 값을 쓰는가"라는 관점에서는 중요하게 봐야 한다.

## 컴파일러 패턴 — memset 인식하기
가장 흔한 형태는 **스택 버퍼를 0으로 초기화하는 코드**다:
```asm
lea     rdi, [rbp-0x40]  ; 목적지: 지역 버퍼 시작
xor     eax, eax           ; 채울 값 = 0 (AL/EAX/RAX 전부 0이 됨)
mov     rcx, 16             ; 16 * 4바이트 = 64바이트를 0으로
cld
rep stosd                    ; == memset(rbp-0x40, 0, 64)
```
`xor eax, eax` 직후 바로 `rep stos*`가 나오는 조합은 "이 버퍼를 0으로 초기화한다"는 매우 강한 신호다. 값이 0이 아니라면(`mov al, 0x41` 처럼) 특정 바이트 패턴으로 채우는 `memset(buf, 0x41, n)` 같은 코드다.

디버그 빌드에서는 초기화되지 않은 스택 메모리를 `0xCC`나 `0xCD`(MSVC 디버그 빌드의 스택 카나리/가드 패턴, 예: `0xCCCCCCCC`)로 채우는 코드도 `stosd` 패턴으로 나타날 수 있다 — 이건 실제 로직이 아니라 컴파일러의 디버그용 안전장치이므로 혼동하지 않는다.

`movsd`와 마찬가지로, 컴파일러는 정렬과 크기가 맞으면 `stosb` 대신 `stosd`/`stosq`를 선택해 반복 횟수를 줄인다.

## IDA/Ghidra 디컴파일에서 보이는 방식
- 표준 패턴이면 `memset(dst, value, n);` 한 줄로 인식되어 표시된다. 특히 `value`가 0이면 `memset(dst, 0, n);`으로 아주 자주 보인다.
- 인식이 안 되면 `do { *pDst++ = value; } while(--n);` 형태의 raw 채우기 루프로 표시된다.
- IDA는 지역 배열 선언부(`char buf[64];`)와 이 `memset`/루프 호출을 나란히 보여주므로, 어떤 변수가 초기화되는지는 스택 프레임 레이아웃과 함께 보면 바로 파악된다.

## 리버싱 관점에서의 의미
- 함수 진입부의 `rep stosd`/`rep stosq` 블록은 대부분 "지역 변수 초기화"이므로, 로직 분석의 핵심이 아니라 **건너뛰어도 되는 하우스키핑 코드**인 경우가 많다 — 처음 읽을 때 여기서 시간을 쓰지 않는 게 좋다.
- 반대로 채우는 값이 0이 아니고 크기가 의미심장하다면(예: 키/패스워드 버퍼를 특정 패턴으로 채움), 그 자체가 분석 대상일 수 있다.
- `RCX`(반복 횟수)가 사용자 입력과 연동되어 있다면, 스택 버퍼를 넘어서는 크기로 채워질 수 있어 취약점 후보가 된다.

## 가장 먼저 할 것
`stos`/`stosb`/`stosd`/`stosq`(또는 `rep stos*`)를 봤다면 가장 먼저 확인할 것:
1. **채우는 값** — 바로 위에서 `AL`/`EAX`/`RAX`에 마지막으로 쓰인 값. `xor eax, eax`면 0으로 초기화, 다른 상수면 특정 패턴 채우기다.
2. **목적지(`RDI`)와 범위(`RCX`)** — 어떤 버퍼를 얼마나 채우는지.
3. **이게 단순 초기화(하우스키핑)인지, 의미 있는 값 채우기인지** — 값이 0이고 함수 초반부라면 대개 지역 변수 초기화이므로 깊이 볼 필요 없이 넘어가도 된다.

## 단계별 절차
1. **F5로 디컴파일**해서 `memset(dst, value, n);`으로 인식되었는지 먼저 확인한다.
2. 인식이 안 되면 디스어셈블리 뷰로 돌아가 `rep stos*` 바로 위에서 `AL`/`EAX`/`RAX`(채울 값)와 `RDI`(목적지), `RCX`(반복 횟수) 세팅 지점을 각각 찾는다.
3. `stosd`/`stosq`라면 실제 바이트 수 = `RCX * 4` 또는 `RCX * 8`임을 계산에 반영한다.
4. `RDI`가 가리키는 오프셋을 IDA 스택 뷰(`Ctrl+K` 또는 함수 상단 주석)와 대조해 어떤 지역 변수/배열이 채워지는지 확인한다.
5. 채우는 값이 0이 아니고(`0xCCCCCCCC` 같은 디버그 패턴이 아니라면) 의미 있는 상수라면, 그 값이 이후 코드에서 어떻게 쓰이는지(비교, XOR 키 등) 계속 추적한다.
6. 런타임에만 값/길이가 정해지면 `rep stos*` 주소에 브레이크포인트(`F2`) 후 `F9`로 실행해 실제 값을 확인한다.

## 명령어/단축키
- IDA: `F5`(디컴파일), `Ctrl+K`(스택 변수 뷰), `F2`(브레이크포인트), `F9`(실행)
- x64dbg: 목적지 주소를 덤프 창에서 "Follow in Dump"로 열어두고 `F9`로 `rep stos*` 실행 전/후 메모리가 실제로 채워지는지 시각적으로 비교
- GDB/Pwndbg: `info registers rdi rcx rax`, `x/20xb $rdi`(채우기 전 목적지 메모리 확인), 실행 후 다시 `x/20xb $rdi`로 채워진 값을 대조

## 흔한 실수
- `STOS`도 `MOVS`처럼 `RSI`에서 값을 읽어온다고 착각하는 것 — `STOS`의 값은 항상 레지스터(`AL/AX/EAX/RAX`)에서 온다. `RSI`는 아예 관여하지 않는다.
- `rep stosd`의 `RCX`를 바이트 수로 착각하는 것 — `stosd`는 4바이트 단위이므로 총 바이트 수는 `RCX * 4`.
- 채우는 값이 항상 0이라고 가정하는 것 — `xor eax, eax` 없이 `mov eax, 0xdeadbeef` 뒤에 `rep stosd`가 오면 특정 패턴으로 채우는 코드다.
- 이 블록을 "복잡한 반복 로직"으로 오해해서 시간을 낭비하는 것 — 대부분은 단순 초기화이므로 값과 길이만 확인하고 넘어가면 된다.

## 막혔을 때 다음 체크
- 채우는 값이 궁금하면 → `rep stos*` 직전 `AL`/`EAX`/`RAX`에 마지막으로 쓰인 값을 확인.
- 채우는 범위(길이)가 궁금하면 → `RCX`와 `RDI` 시작 주소를 역추적. `stosd`/`stosq`면 실제 바이트 수는 `RCX * 4` 또는 `RCX * 8`.
- 이게 어떤 지역 변수를 초기화하는지 궁금하면 → IDA의 스택 뷰(`Ctrl+K` 또는 함수 상단 `; [rsp+...] [rbp-...]` 주석)에서 `RDI`가 가리키는 오프셋과 대응하는 변수를 찾는다.

## 미니 예제

**예제 1 — 스택 버퍼 0 초기화 (memset 0)**
```c
char buf[64];
memset(buf, 0, sizeof(buf));
```
```asm
lea     rdi, [rbp-0x40]
xor     eax, eax
mov     rcx, 16       ; 16 * 4바이트 = 64
cld
rep stosd
```

**예제 2 — 바이트 단위로 특정 값 채우기**
```c
memset(buf, 0x41, 32);   // 'A'로 채움
```
```asm
lea     rdi, [buf]
mov     al, 0x41
mov     rcx, 32
cld
rep stosb
```

**예제 3 — REP 없는 단독 STOSQ (레지스터 0클리어 후 한 칸 저장)**
```asm
xor     rax, rax
mov     rdi, offset ptr
stosq             ; *ptr = 0, RDI += 8   (RCX와 무관하게 1회만 실행)
```

**예제 4 — 디버그 빌드의 "가비지 패턴" 채우기 (실제 로직 아님)**
```asm
lea     rdi, [rbp-0x30]
mov     eax, 0CCCCCCCCh   ; MSVC 디버그 빌드 특유의 미초기화 표시 패턴
mov     ecx, 12
rep stosd                    ; 실제 값 계산과 무관한 컴파일러 안전장치
```

## 관련 글
- [rev-0080-rep-prefix.md](./rev-0080-rep-prefix.md) — REP Prefix와 반복 문자열 명령
- [rev-0081-movs.md](./rev-0081-movs.md) — MOVS/MOVSB/MOVSW/MOVSD/MOVSQ (memcpy 대응)
- [rev-0083-lods.md](./rev-0083-lods.md) — LODS 문자열 로드 명령
- [rev-0084-scas.md](./rev-0084-scas.md) — SCAS와 문자열 검색 패턴
- [rev-0085-cmps.md](./rev-0085-cmps.md) — CMPS와 문자열 비교 패턴
- [rev-0071-call.md](./rev-0071-call.md) — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- `STOS`/`STOSB`/`STOSW`/`STOSD`/`STOSQ` 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2C, "STOS/STOSB/STOSW/STOSD/STOSQ—Store String" 섹션 기준 (2026-09-08 검증).
- MSVC 디버그 빌드의 `0xCC`/`0xCD` 미초기화 스택 패턴: Microsoft Learn "MSVC: Debugging Uninitialized Memory" 관련 공식 문서 기준.
