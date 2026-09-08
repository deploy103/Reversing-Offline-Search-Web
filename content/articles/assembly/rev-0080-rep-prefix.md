---
id: REV-0080
title: "REP Prefix와 반복 문자열 명령"
slug: "rev-0080-rep-prefix"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - rep
  - REP
  - rep prefix
  - repe
  - repz
  - repne
  - repnz
  - rep movsb
  - rep stosb
  - rep scasb
  - rep cmpsb
  - 반복 접두사
  - 문자열 명령
  - string instruction
  - RCX 카운터
  - ECX 카운터
  - direction flag
  - DF
  - 방향 플래그
  - CLD
  - STD
  - fast memcpy
  - fast memset
aliases:
  - rep이 뭐임
  - rep movsb 뭐임
  - rep 접두사란
  - 반복문 어셈블리
  - 문자열 반복 명령
symptom_keywords:
  - rep movsb 루프가 이해 안 됨
  - rcx가 계속 줄어드는 코드
  - DF 플래그가 뭔지 모르겠음
  - CLD STD 차이를 모르겠음
  - 컴파일러가 memcpy 대신 이상한 코드를 냄
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`REP`(그리고 `REPE`/`REPZ`, `REPNE`/`REPNZ`)는 뒤에 오는 문자열 명령(`MOVS`, `STOS`, `LODS`, `SCAS`, `CMPS`)을 `RCX`(또는 `ECX`)가 0이 될 때까지, 또는 비교 결과가 맞을 때까지 **하드웨어 수준에서 반복 실행**시키는 접두사다. 컴파일러가 `memcpy`/`memset`/`strlen`/`memcmp` 같은 함수를 인라인할 때 자주 등장하며, 사실상 "고속 루프 한 방"이므로 한 줄씩 따라 읽기보다 통째로 인식하는 게 핵심이다.

## 언제 검색해야 하나
- `rep movsb`, `rep stosd`, `rep scasb` 같은 코드를 만났는데 이게 반복문(loop)인지 단일 명령인지 헷갈릴 때
- 함수 앞부분에 `RCX`에 큰 수를 넣고 `rep ...`가 나와서 "이게 왜 for문처럼 보이지?"라는 의문이 들 때
- `cld`/`std` 명령이 문자열 명령 앞에 붙어 있는 걸 봤는데 무슨 뜻인지 모를 때
- IDA/Ghidra가 이 블록을 통째로 `memcpy`/`memset` 호출로 보여주는 이유가 궁금할 때

## 핵심 개념

### REP가 실제로 하는 일
`REP` 계열 접두사는 반드시 문자열 명령(`MOVSx`, `STOSx`, `LODSx`, `SCASx`, `CMPSx`) 바로 앞에 붙어서 그 명령을 반복시킨다. CPU 마이크로코드 레벨에서 다음과 같이 동작한다(의사코드):

```
반복:
    if RCX == 0: 종료
    (문자열 명령 1회 실행 — 예: MOVSB면 1바이트 복사)
    RCX = RCX - 1
    if DF == 0: 관련 레지스터(RSI/RDI 등) 증가
    else:       관련 레지스터(RSI/RDI 등) 감소
    (REPE/REPNE 계열이면 ZF 검사해서 조건 안 맞으면 조기 종료)
    반복으로
```

**핵심은 `RCX`가 카운터 역할을 한다는 것**이다. `RCX`가 0이면 `REP` 접두사가 붙은 명령은 **단 한 번도 실행되지 않고 그대로 다음 명령으로 넘어간다** — 이 부분이 초보자들이 자주 놓치는 지점이다(0번 반복도 유효하다).

### REP 계열 3가지
- **`REP`**: 조건 없이 순수하게 `RCX`가 0이 될 때까지 반복. `MOVS`, `STOS`, `LODS`에 사용 (비교를 안 하는 명령들).
- **`REPE`/`REPZ`** (Repeat while Equal / while Zero — 같은 인코딩): `RCX != 0` **그리고** `ZF == 1`(직전 비교가 "같음")인 동안 반복. `RCX`가 0이 되거나 `ZF`가 0이 되면(다른 값을 만나면) 멈춘다. `CMPS`, `SCAS`에서 "끝까지 같은지" 검사할 때 사용.
- **`REPNE`/`REPNZ`** (Repeat while Not Equal / Not Zero — 같은 인코딩): `RCX != 0` **그리고** `ZF == 0`(직전 비교가 "다름")인 동안 반복. `RCX`가 0이 되거나 `ZF`가 1이 되면(같은 값을 찾으면) 멈춘다. `SCAS`로 특정 바이트를 찾을 때(예: `strlen`이 NUL 바이트를 찾는 것) 대표적으로 쓰인다.

정리하면:
```
rep    movsb   ; 그냥 RCX번 반복 (비교 없음)
repe   cmpsb   ; RCX != 0 && 같다(ZF=1) 인 동안 반복 → 다르면 즉시 멈춤 (memcmp류)
repne  scasb   ; RCX != 0 && 다르다(ZF=0) 인 동안 반복 → 같으면 즉시 멈춤 (strlen/문자 탐색류)
```

### 방향 플래그(DF)와 CLD/STD — 여기서 초보자가 가장 많이 헤맨다
문자열 명령들은 매 반복마다 관련 포인터 레지스터(`RSI`, `RDI`, 때로는 둘 다)를 자동으로 증가시키거나 감소시킨다. **어느 쪽으로 움직일지는 `EFLAGS`의 `DF`(Direction Flag) 비트 하나가 결정한다.**

- **`DF = 0`** → 매 반복마다 포인터가 **+1/+2/+4/+8(오퍼랜드 크기만큼) 증가**한다. 즉 메모리 낮은 주소 → 높은 주소로 순차 진행. `CLD`(Clear Direction Flag) 명령으로 이 상태를 만든다.
- **`DF = 1`** → 매 반복마다 포인터가 **감소**한다. 높은 주소 → 낮은 주소로 역순 진행. `STD`(Set Direction Flag) 명령으로 이 상태를 만든다.

거의 모든 컴파일러 생성 코드는 **`CLD`로 `DF`를 0으로 만들어놓고** 정방향으로 복사/스캔한다 — 그래서 `rep movsb`가 나오면 십중팔구 "낮은 주소에서 높은 주소로 순서대로 복사한다"고 가정해도 무방하다. `STD`(역방향)는 `memmove`처럼 소스/대상 영역이 겹치는데 뒤에서부터 복사해야 안전한 특수한 경우, 또는 일부 레거시/난독화 코드에서나 등장한다.

**같은 `rep movsb` 코드라도 직전에 `cld`가 있었는지 `std`가 있었는지에 따라 완전히 다르게 동작한다** — 이걸 확인하지 않고 "그냥 앞에서 뒤로 복사하겠지"라고 넘겨짚는 것이 매우 흔한 실수다. 함수 진입 시 `DF`는 보통 0이라고 가정되지만(대부분의 ABI에서 함수 호출 시 `DF=0`이 보장되는 관례), 직접 `std`를 실행하는 코드가 섞여 있다면 반드시 확인해야 한다.

### 레지스터 역할 총정리
`REP` 계열이 반복시키는 문자열 명령들이 공통으로 쓰는 레지스터:

```
RSI (ESI/SI) = 소스(source) 포인터  — MOVS, LODS, CMPS 에서 사용
RDI (EDI/DI) = 목적지(destination) 포인터 — MOVS, STOS, SCAS, CMPS 에서 사용
RCX (ECX/CX) = 반복 횟수 카운터 — REP 계열 접두사가 붙었을 때만 의미 있음
RAX/AL/AX/EAX/RAX = STOS의 "채울 값" 소스, LODS의 "읽은 값" 목적지, SCAS의 "찾을 값"
```
x86 문자열 명령 이름 자체가 이 레지스터 이름에서 유래했다: **S**tring, 소스는 e**SI**, 목적지는 e**DI**. 이 규칙만 외워두면 `MOVS`/`STOS`/`LODS`/`SCAS`/`CMPS` 각각을 개별로 다시 안 외워도 된다.

### 플래그 변화
`REP` 접두사 자체는 플래그를 바꾸지 않는다. 반복되는 내부 명령(`CMPS`, `SCAS`)이 매 반복마다 `CF/ZF/SF/OF/AF/PF`를 갱신하며, 루프가 끝난 시점에는 **마지막으로 실행된 비교의 결과**가 플래그에 남아 있다. `MOVS`, `STOS`, `LODS`는 플래그를 바꾸지 않는다(단순 데이터 이동이므로).

### 스택/RIP
`REP` 계열은 스택이나 함수 호출 흐름에 직접 영향을 주지 않는다. `RIP`는 매 내부 반복마다 실질적으로 같은 명령 주소를 가리키는 것처럼 동작하다가(마이크로코드 반복이므로 명령어 포인터가 실제로 여러 번 움직이는 게 아니라 하나의 명령이 하드웨어적으로 반복됨) 반복이 끝나면 다음 명령으로 넘어간다. 디버거로 싱글스텝(`stepi`)하면 `rep movsb` 한 줄 전체가 **한 번의 스텝**으로 끝나는 것처럼 보일 수도 있고, 구현에 따라 매 반복마다 같은 주소에서 멈추는 것처럼 보일 수도 있다(인터럽트 가능하게 설계되어 있어 중간에 끊겼다가 재개 가능).

## 컴파일러 패턴 — "이건 그냥 빠른 memcpy/memset이다"라고 인식하기
현대 컴파일러(GCC, MSVC, Clang)는 크기가 크거나 컴파일 타임에 크기를 모르는 `memcpy`/`memset`/`strlen`/`memcmp` 호출을 최적화 옵션에 따라 **함수 호출 대신 `rep movsb`/`rep stosb` 등을 직접 인라인**해서 넣는 경우가 많다. 전형적인 모양:

```asm
mov     rdi, dest_ptr   ; 목적지 설정
mov     rsi, src_ptr    ; 소스 설정
mov     rcx, count       ; 반복 횟수(바이트 수 등) 설정
cld                       ; 방향 = 정방향 확정
rep movsb                 ; 이 세 줄 전부가 그냥 "memcpy(dest, src, count)" 한 줄이다
```

**이 블록을 읽을 때 명령어 하나하나를 좇지 말고, "RDI=목적지, RSI=소스, RCX=길이가 세팅된 뒤 `rep movsb`가 나오면 그냥 `memcpy` 호출 한 번"이라고 통으로 인식**하는 게 리버싱 속도를 크게 좌우한다. 마찬가지로:
- `rep stosb`/`rep stosd` 블록 → `memset` 한 방으로 인식
- `repne scasb` 블록 → `strlen` 유사 스캔으로 인식 (REV-0084 참고)
- `repe cmpsb` 블록 → `memcmp` 유사 비교로 인식 (REV-0085 참고)

## IDA/Ghidra 디컴파일에서 보이는 방식
디컴파일러는 이런 반복 문자열 명령 블록을 크게 두 가지로 표현한다:
1. **함수 호출로 인식**: `RCX/RSI/RDI` 세팅 패턴을 인식해서 `memcpy(dest, src, count);` 같은 라이브러리 함수 호출문으로 깔끔하게 바꿔준다. IDA의 최신 버전과 Ghidra 모두 이런 패턴 인식(idiom recognition)을 상당 부분 지원한다.
2. **원시 루프로 표현**: 패턴을 인식하지 못하면 `do { *dst++ = *src++; } while(--count);` 형태의 raw 루프나, 심하면 `__asm { rep movsb }` 형태의 인라인 어셈블리 블록으로 그대로 남겨둔다.

어느 쪽이 나오든 실제 동작은 같다 — **디컴파일 결과가 낯선 저수준 루프로 보인다면, 원본 어셈블리로 돌아가 `rep movsb`류가 있는지 먼저 확인**하면 "복잡한 알고리즘"이 아니라 "그냥 빠른 복사/채우기"였다는 걸 빨리 알아챌 수 있다.

## 리버싱 관점에서의 의미
- `rep movsb`/`rep stosb` 블록이 보이면 그 앞뒤 코드에서 **버퍼 크기(RCX 값)**를 확인하는 것이 우선이다 — 스택 버퍼에 대한 크기 미검증 복사라면 버퍼 오버플로우 취약점 후보다.
- `RCX`가 사용자 입력에서 직접 오는지, 상수인지 확인하면 취약점 분석에 바로 활용할 수 있다.
- `repne scasb`로 문자열 길이를 재는 패턴은 `strlen`이 인라인된 신호이며, 이후 코드에서 그 길이를 어떻게 쓰는지(버퍼 크기 비교, `malloc` 크기 계산 등) 추적하면 로직을 빠르게 이해할 수 있다.

## 가장 먼저 할 것
`rep`류 접두사가 붙은 문자열 명령을 봤다면 다른 무엇보다 먼저 세 가지 레지스터부터 확인한다.
1. **`RCX`(카운터)** — 바로 위에서 마지막으로 세팅된 값이 상수인지, 사용자 입력에서 온 값인지. 이게 반복 횟수(또는 최대 스캔 범위)다.
2. **방향 플래그(DF)** — 직전에 `cld`가 있는지 `std`가 있는지. 없으면 함수 진입 시점부터 거슬러 올라가 확인한다(대부분 `cld`로 정방향이 이미 보장된 상태로 진입).
3. **뒤따르는 명령이 `movs`/`stos`/`lods`/`scas`/`cmps` 중 무엇인지** — 이것에 따라 `RSI`/`RDI`/`RAX` 중 어느 레지스터가 소스/목적지/비교값 역할을 하는지가 완전히 달라진다.

## 단계별 절차
1. **`rep`(또는 `repe`/`repne`) 접두사가 붙은 명령을 찾으면**, 그 줄 전체를 "루프 하나"로 취급하고 IDA 그래프뷰에서 이 블록의 시작과 끝을 확인한다.
2. **위로 거슬러 올라가며 `RCX`, `RSI`/`RDI`, `AL`/`EAX`/`RAX`에 마지막으로 쓰인 값을 각각 찾는다.** 보통 바로 위 3~5줄 안에 다 모여 있다.
3. **`cld`/`std` 여부를 확인**한다. 안 보이면 함수 최상단까지 더 거슬러 올라가거나, 함수 진입 시 `DF=0`이 보장된다는 일반 관례를 적용한다.
4. **F5로 디컴파일**해서 이 블록이 `memcpy`/`memset`/`strlen`류로 인식되었는지 확인한다. 인식됐다면 그 함수 호출 한 줄로 이해하고 넘어가면 충분하다.
5. 인식이 안 되고 raw 루프로 보이거나, 반복 횟수/조건이 런타임에 결정되는 값이라 정적으로 추적이 안 되면, `rep` 명령 주소에 브레이크포인트를 걸고(`F2`) 실행(`F9`)해서 그 시점의 `RCX`, `RSI`, `RDI` 실제 값을 레지스터 창에서 읽는다.
6. 반복이 끝난 뒤 결과(길이, 비교 결과 등)를 어디에 쓰는지 다음 몇 줄을 따라가서 확인한다.

## 명령어/단축키
- IDA: `F5`(디컴파일 — memcpy/memset류 인식 확인), `F2`(브레이크포인트), `F9`(실행), 레지스터/스택 뷰에서 `RCX`/`RSI`/`RDI` 직접 확인
- x64dbg: `F2`(브레이크포인트), `F9`(실행/계속), `F7`(Step Into) — `rep` 명령에서 Step Into를 반복하면 매 반복마다 멈추는 구현도 있으므로 대량 반복이면 대신 `F4`(커서까지 실행)나 조건부 브레이크포인트로 반복 종료 지점까지 건너뛰는 게 낫다, 우측 플래그 패널에서 `DF` 확인
- GDB/Pwndbg: `info registers rcx rsi rdi`, `p $eflags`(DF 비트 확인), `x/1i $rip` 후 `stepi`로 진행하되 반복 횟수가 크면 대신 `tbreak` + `continue`로 반복이 끝나는 다음 명령 주소에 임시 브레이크포인트를 걸어 한 번에 건너뛴다

## 흔한 실수
- `DF`가 항상 0이라고 무조건 가정하고 방향을 확인하지 않는 것 — `std`가 앞에 있으면 역방향으로 움직인다.
- `RCX`가 0인 채로 `rep ...`에 진입하면 "적어도 한 번은 실행되겠지"라고 착각하는 것 — 0이면 **0번** 실행된다(먼저 `RCX`를 검사하고 나서 실행하는 구조).
- `REP`, `REPE`, `REPNE`를 전부 같은 것으로 뭉뚱그려 읽는 것 — 뒤에 오는 명령이 비교 명령(`CMPS`/`SCAS`)인지에 따라 `ZF` 조건까지 함께 검사하는지가 완전히 달라진다.
- `rep movsb` 한 줄을 "그냥 명령 하나"로 보고 실행 시간이 짧을 거라 착각하는 것 — 실제로는 `RCX`번 반복되는 루프이므로 큰 값이면 상당한 시간이 걸릴 수 있다(디버거로 F8/Step Over 하지 않고 F7/Step Into로 들어가면 체감된다).

## 막혔을 때 다음 체크
- `rep` 뒤의 명령이 `movs`/`stos`/`lods`/`scas`/`cmps` 중 무엇인지 먼저 특정한다 → 각각 REV-0081~0085 개별 문서 참고.
- 방향이 헷갈리면 → 디버거로 `rep` 진입 직전 `EFLAGS`의 `DF` 비트를 확인하거나(x64dbg 플래그 창, GDB `info registers eflags`), 직전 명령이 `cld`인지 `std`인지 본다.
- 반복 횟수가 궁금하면 → `rep` 진입 직전 `RCX`에 마지막으로 쓰인 값을 역추적한다.

## 미니 예제

**예제 1 — REP (조건 없는 반복, memcpy형)**
```asm
lea     rsi, [src]
lea     rdi, [dst]
mov     rcx, 100
cld
rep movsb          ; 100바이트를 src부터 dst로 순서대로 복사
```

**예제 2 — REPE/REPZ (같은 동안 반복, memcmp형)**
```asm
lea     rsi, [bufA]
lea     rdi, [bufB]
mov     rcx, 16
cld
repe cmpsb          ; 16바이트를 비교하다가 다른 바이트가 나오면 즉시 중단
jne     not_equal    ; 마지막 비교의 ZF로 분기
```

**예제 3 — REPNE/REPNZ (다른 동안 반복, strlen형 SCAS)**
```asm
lea     rdi, [str]
mov     al, 0        ; 찾을 값 = NUL 바이트
mov     rcx, -1        ; 사실상 "무한대" 카운터
cld
repne scasb          ; NUL 바이트를 만날 때까지(같아질 때까지) 스캔 후 정지
; 이후 RDI - str_addr - 1 이 문자열 길이가 됨
```

**예제 4 — STD로 인한 역방향 복사 (겹치는 영역 대비, memmove형)**
```asm
lea     rsi, [src+99]   ; 마지막 바이트부터 시작
lea     rdi, [dst+99]
mov     rcx, 100
std                       ; 방향 = 역방향
rep movsb                 ; 뒤에서부터 앞으로 100바이트 복사
cld                       ; 관례상 다시 정방향으로 복원해두는 경우가 많음
```

## 관련 글
- [rev-0081-movs.md](./rev-0081-movs.md) — MOVS/MOVSB/MOVSW/MOVSD/MOVSQ (메모리 복사, memcpy 대응)
- [rev-0082-stos.md](./rev-0082-stos.md) — STOS/STOSB/STOSD/STOSQ (메모리 채우기, memset 대응)
- [rev-0083-lods.md](./rev-0083-lods.md) — LODS 문자열 로드 명령
- [rev-0084-scas.md](./rev-0084-scas.md) — SCAS와 문자열 검색 패턴 (strlen 대응)
- [rev-0085-cmps.md](./rev-0085-cmps.md) — CMPS와 문자열 비교 패턴 (memcmp 대응)
- [rev-0071-call.md](./rev-0071-call.md) — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- `REP`/`REPE`/`REPZ`/`REPNE`/`REPNZ` 접두사 동작과 의사코드: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2C, "REP/REPE/REPZ/REPNE/REPNZ—Repeat String Operation Prefix" 섹션 기준 (2026-09-08 검증).
- `DF`(Direction Flag), `CLD`/`STD`: 동 매뉴얼 Volume 1, "EFLAGS Register" 및 Volume 2A "CLD/STD" 섹션 기준.
- 컴파일러의 `rep movsb`/`rep stosb` 인라인 최적화 관행: GCC `-mstringop-strategy`/`-minline-all-stringops` 관련 공식 문서 및 MSVC `/O2` 최적화 동작 기준.
