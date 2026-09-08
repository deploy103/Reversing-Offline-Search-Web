---
id: REV-0081
title: "MOVS MOVSB MOVSW MOVSD MOVSQ"
slug: "rev-0081-movs"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - movs
  - MOVS
  - movsb
  - MOVSB
  - movsw
  - MOVSW
  - movsd
  - MOVSD
  - movsq
  - MOVSQ
  - rep movsb
  - rep movsd
  - rep movsq
  - string move
  - 문자열 이동 명령
  - memcpy
  - 메모리 복사
  - RSI RDI
  - source destination
  - DF 방향 플래그
aliases:
  - movsb가 뭐임
  - movsd 뭐죠
  - rep movsb 뭐임
  - 어셈블리 memcpy
  - 메모리 복사 명령어
symptom_keywords:
  - rep movsb 루프 이해가 안 됨
  - rsi rdi가 계속 증가하는 코드
  - memcpy 대신 이상한 어셈블리가 보임
  - movsd와 movsb 차이를 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`MOVS`(및 크기별 변형 `MOVSB`/`MOVSW`/`MOVSD`/`MOVSQ`)는 `[RSI]`가 가리키는 메모리에서 `[RDI]`가 가리키는 메모리로 1개 단위(1/2/4/8바이트)를 복사하고 `RSI`, `RDI`를 자동으로 전진(또는 후진)시키는 명령이다. `REP` 접두사와 함께 쓰이면 `memcpy(dest, src, n)`을 통째로 대체하는 고속 반복 복사 루프가 된다.

## 언제 검색해야 하나
- `rep movsb`, `rep movsd`, `rep movsq` 같은 코드가 함수 안에 갑자기 나타나서 무슨 뜻인지 모를 때
- `movsb` 한 줄만 (REP 없이) 단독으로 있는 걸 봤을 때
- 디컴파일러가 이 블록을 `memcpy(...)` 호출로 바꿔서 보여줬는데 원본 어셈블리와 안 맞아 보일 때
- `RSI`, `RDI`가 반복문 안에서 계속 증가하는 걸 보고 이게 배열 순회인지 궁금할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
movsb          ; 1바이트: BYTE PTR [RDI] <- BYTE PTR [RSI]
movsw          ; 2바이트: WORD PTR [RDI] <- WORD PTR [RSI]
movsd          ; 4바이트: DWORD PTR [RDI] <- DWORD PTR [RSI]   (SSE의 movsd와 이름이 겹치니 문맥으로 구분!)
movsq          ; 8바이트(x64 전용): QWORD PTR [RDI] <- QWORD PTR [RSI]
```
오퍼랜드 없이 쓰는 게 일반적(`RSI`/`RDI`를 암묵적으로 사용)이지만, 원래 `MOVS`는 `movs BYTE PTR [rdi], BYTE PTR [rsi]`처럼 명시적 오퍼랜드 형태의 니모닉도 존재한다(어셈블러가 크기를 오퍼랜드에서 추론). 실전 디스어셈블리에서는 거의 항상 `movsb`/`movsd`/`movsq`처럼 크기가 접미사로 붙은 형태로 보인다.

**주의**: `MOVSD`라는 이름은 두 가지 완전히 다른 명령에 쓰인다 — 여기서 다루는 **문자열 명령(4바이트 이동)**과, SSE2의 **`MOVSD xmm, xmm/m64`(스칼라 double 이동)**. 오퍼랜드가 없으면 문자열 명령, `xmm0, [rax]`처럼 XMM 레지스터 오퍼랜드가 있으면 SSE 명령이다. IDA/Ghidra는 문맥에 맞춰 정확히 구분해서 보여준다.

### 방향 및 레지스터 효과 (source=RSI, dest=RDI)
- **소스**: `RSI` (또는 32비트 모드에서 `ESI`)가 읽어올 주소를 가리킨다.
- **목적지**: `RDI`(`EDI`)가 쓸 주소를 가리킨다.
- 한 번 실행될 때마다 `[RSI] -> [RDI]`로 값이 복사된 뒤, **`DF`(방향 플래그)에 따라 `RSI`와 `RDI`가 동시에 증가하거나 감소**한다(REV-0080 참고).
  - `DF=0`(`CLD` 실행 후, 대부분의 경우): `RSI += size`, `RDI += size` (size = 1/2/4/8)
  - `DF=1`(`STD` 실행 후): `RSI -= size`, `RDI -= size`
- `REP` 접두사가 붙으면 `RCX`가 반복 횟수 카운터로 쓰이고, 위 동작이 `RCX`번(또는 조건에 따라 조기 종료) 반복된다.

### 플래그 변화
`MOVS`는 **플래그를 전혀 바꾸지 않는다.** 단순 데이터 이동이기 때문이다(CF/ZF/SF/OF/AF/PF 모두 영향 없음). 이는 `CMPS`/`SCAS`와 뚜렷이 대비되는 부분이다.

### 스택/RIP 변화
직접적인 영향 없음. `RSP`, `RIP`는 `MOVS`/`REP MOVS` 실행으로 변하지 않는다(단, 반복이 끝나면 다음 명령으로 `RIP`가 진행하는 건 다른 모든 명령과 동일).

## 컴파일러 패턴 — memcpy 인식하기
```asm
lea     rsi, [rbp-0x40]   ; 소스 버퍼 주소
lea     rdi, [rbp-0x80]   ; 목적지 버퍼 주소
mov     rcx, 20            ; 복사할 개수 (바이트/워드/dword/qword 단위는 접미사가 결정)
cld
rep movsb                   ; == memcpy(rdi_addr, rsi_addr, 20)
```
`rep movsd`나 `rep movsq`가 나오면 `RCX`는 "4바이트 단위 개수" 또는 "8바이트 단위 개수"라는 점에 유의한다 — 총 바이트 수를 구하려면 `RCX * 4` 또는 `RCX * 8`을 계산해야 한다. 컴파일러는 정렬(alignment)이 보장되고 크기가 4/8의 배수인 경우 `movsb` 대신 `movsd`/`movsq`를 선택해 반복 횟수를 줄이는 최적화를 자주 한다(같은 총량을 더 적은 반복으로 복사 = 더 빠름).

작은 고정 크기 구조체 복사(`struct` 대입, 배열 복사)도 종종 `rep movsd`/`movsq` 몇 번 또는 REP 없이 `movsd`/`movsq`가 연속으로 풀려서(unroll) 나오는 경우가 있다 — 이 경우도 "복사 로직 몇 줄"이 아니라 "구조체 대입 한 줄"로 인식하면 된다.

## IDA/Ghidra 디컴파일에서 보이는 방식
- 패턴이 표준적이면(길이가 레지스터/상수로 명확) `memcpy(dst, src, n);` 한 줄로 인식되어 표시된다.
- 표준 패턴이 아니거나(예: 길이가 복잡한 계산식에서 나옴) 컴파일러가 완전히 인라인만 해놓은 경우, `do { *pDst++ = *pSrc++; } while(--n);` 같은 raw 포인터 증가 루프로 표시될 수 있다.
- 둘 다 정확히 같은 동작이므로, raw 루프가 보이면 "복잡한 알고리즘"이라 생각하지 말고 먼저 "이거 그냥 memcpy 아닌가?"를 의심하는 게 시간을 아낀다.

## 리버싱 관점에서의 의미
- `rep movsb`/`rep movsq` 앞의 `RCX` 값(길이)이 **사용자 입력에서 그대로 오는지**를 확인하는 것이 취약점 분석의 첫걸음이다 — 길이 검증 없이 고정 크기 스택 버퍼로 복사하면 버퍼 오버플로우다.
- 구조체나 배열을 통째로 복사하는 코드가 함수 호출 없이 인라인되어 있으면, 원래 소스 코드에서는 단순 대입문(`dst = src;`, `memcpy` 호출, 구조체 대입)이었을 가능성이 높다 — 복잡한 로직을 찾으려 헤매지 않아도 된다.

## 가장 먼저 할 것
`movs`/`movsb`/`movsd`/`movsq`(또는 `rep movs*`)를 봤다면 가장 먼저 확인할 것:
1. **`REP` 접두사가 붙어 있는가**? 없으면 딱 1개 단위만 이동하는 단독 명령(드묾)이고, 있으면 `RCX`번 반복되는 사실상의 `memcpy` 루프다.
2. **`RSI`(소스)와 `RDI`(목적지)에 각각 어떤 주소가 들어가는지** — 바로 위 몇 줄에서 `lea rsi, ...` / `lea rdi, ...` 형태를 찾는다.
3. **`RCX`에 들어가는 길이 값이 상수인지 사용자 입력에서 오는지** — 스택 버퍼로 복사하는데 길이가 검증 안 된 사용자 값이면 오버플로우 후보다.

## 단계별 절차
1. IDA에서 이 블록을 만나면 우선 **F5로 디컴파일**해서 `memcpy(dst, src, n);` 한 줄로 이미 인식되었는지 본다. 인식됐다면 3~6단계는 생략해도 된다.
2. 인식이 안 되고 raw 루프(`do { *pDst++ = *pSrc++; } while(--n);`)로 보이면, 디스어셈블리 뷰(Space)로 돌아간다.
3. `rep movsb`(또는 movsd/movsq) 바로 위에서 `RSI`, `RDI`, `RCX`에 마지막으로 쓰인 값을 각각 찾아 소스/목적지/길이를 확정한다.
4. `movsd`/`movsq`라면 실제 바이트 수 = `RCX * 4` 또는 `RCX * 8`이라는 점을 계산에 반영한다.
5. 목적지(`RDI`)가 스택 변수라면 IDA 스택 뷰(함수 상단 `; [rbp-...]` 주석 또는 `Ctrl+K`)에서 그 오프셋에 대응하는 지역 변수/버퍼 크기를 확인해서, 복사 길이가 버퍼 크기를 넘는지 비교한다.
6. 값이 런타임에만 결정되면, `rep movsb` 주소에 브레이크포인트(`F2`)를 걸고 `F9`로 실행해 그 시점의 `RSI`/`RDI`/`RCX` 실제 값을 레지스터 창에서 확인한다.

## 명령어/단축키
- IDA: `F5`(디컴파일), `Ctrl+K`(스택 뷰에서 변수 크기 확인), `F2`(브레이크포인트), `F9`(실행)
- x64dbg: `F2`/`F9`로 `rep movsb` 지점에서 멈춘 뒤 우측 레지스터 패널에서 `RSI`/`RDI`/`RCX` 확인, 덤프 창에 `RDI` 주소를 우클릭 → "Follow in Dump"로 실제로 써지는 메모리를 실시간으로 관찰
- GDB/Pwndbg: `info registers rsi rdi rcx`, `x/20xb $rdi`(목적지 메모리를 바이트 단위로 미리보기), `stepi`로 한 단위씩 진행하며 반복마다 메모리가 어떻게 채워지는지 관찰(반복 횟수가 크면 `tbreak` + 목적지 이후 주소로 건너뛰는 편이 빠름)

## 흔한 실수
- `rep movsb`의 `RCX`를 "바이트 수"로만 생각하고, `rep movsd`/`rep movsq`에서도 그대로 바이트 수라고 착각하는 것 — 접미사에 따라 단위가 다르다(`movsd`=4바이트 단위, `movsq`=8바이트 단위).
- 방향 플래그(`DF`)를 확인하지 않고 항상 정방향(주소 증가)이라고 가정하는 것 — `std`가 앞에 있으면 반대다.
- `movsd`(문자열 명령, 오퍼랜드 없음)와 `movsd xmm0, [rax]`(SSE 스칼라 double 이동)를 같은 명령으로 착각하는 것 — 오퍼랜드 유무로 구분한다.
- `RSI`/`RDI`가 소스/목적지 중 어느 쪽인지 헷갈리는 것 — **S**ource는 e**SI**, e**DI**는 **D**estination이라고 이름 자체로 외운다.

## 막혔을 때 다음 체크
- 복사 길이가 궁금하면 → `rep movsb`(또는 movsd/movsq) 직전 `RCX`에 마지막으로 쓰인 값을 역추적. `movsd`/`movsq`면 실제 바이트 수 = `RCX * 4` 또는 `RCX * 8`.
- 소스/목적지 주소가 궁금하면 → 직전 `RSI`, `RDI` 세팅 지점을 확인.
- 방향이 궁금하면 → `cld`/`std` 여부, 또는 디버거에서 `DF` 플래그 비트 직접 확인 (REV-0080 참고).

## 미니 예제

**예제 1 — 기본 REP MOVSB (memcpy)**
```c
// C
memcpy(dst, src, 32);
```
```asm
lea     rsi, [src]
lea     rdi, [dst]
mov     rcx, 32
cld
rep movsb
```

**예제 2 — MOVSQ로 8바이트씩 빠르게 복사 (정렬된 큰 버퍼)**
```asm
lea     rsi, [src]
lea     rdi, [dst]
mov     rcx, 8        ; 8 * 8바이트 = 64바이트 복사
cld
rep movsq
```

**예제 3 — REP 없는 단독 MOVSB (드묾, 디버거 싱글스텝 실습용)**
```asm
mov     rsi, offset src
mov     rdi, offset dst
movsb              ; RCX와 무관하게 딱 1바이트만 복사, RSI/RDI 각각 1 증가
```

**예제 4 — 구조체 대입이 REP 없이 풀려 나온(unroll) 패턴**
```c
struct Point { long x, y; };
struct Point a, b;
a = b;   // 16바이트 구조체 대입
```
```asm
lea     rsi, [b]
lea     rdi, [a]
movsq              ; a.x = b.x
movsq              ; a.y = b.y  (RSI/RDI가 이전 movsq로 이미 +8 되어 있음)
```

## 관련 글
- [rev-0080-rep-prefix.md](./rev-0080-rep-prefix.md) — REP Prefix와 반복 문자열 명령 (DF, CLD/STD, RCX 카운터의 전반적 규칙)
- [rev-0082-stos.md](./rev-0082-stos.md) — STOS/STOSB/STOSD/STOSQ (memset 대응)
- [rev-0083-lods.md](./rev-0083-lods.md) — LODS 문자열 로드 명령
- [rev-0084-scas.md](./rev-0084-scas.md) — SCAS와 문자열 검색 패턴
- [rev-0085-cmps.md](./rev-0085-cmps.md) — CMPS와 문자열 비교 패턴
- [rev-0071-call.md](./rev-0071-call.md) — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- `MOVS`/`MOVSB`/`MOVSW`/`MOVSD`/`MOVSQ` 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2C, "MOVS/MOVSB/MOVSW/MOVSD/MOVSQ—Move Data from String to String" 섹션 기준 (2026-09-08 검증).
- 컴파일러의 `rep movsb`/`memcpy` 인라인 관행: GCC/MSVC 최적화 관련 공식 문서 및 일반 리버싱 레퍼런스 기준.
