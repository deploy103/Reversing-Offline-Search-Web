---
id: REV-0486
title: "REP 프리픽스가 있는 명령이 안 끝나는 것처럼 보일 때"
slug: "rev-0486-rep-not-terminating"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - rep movsb 멈춤
  - rep stosb 무한루프
  - rep 안 끝남
  - REP
  - rep prefix stuck
  - RCX 카운터
  - stepi 같은 주소
  - single step rep
  - direction flag
  - DF 플래그
  - repe cmpsb
  - repne scasb
  - x64dbg step into rep
  - gdb stepi rep movsb
aliases:
  - rep movsb가 안 끝나요
  - rep 명령에서 멈춰있음
  - 디버거가 rep에서 안 넘어감
  - rep stosb 무한루프처럼 보임
  - rep 명령 계속 반복
symptom_keywords:
  - stepi를 눌러도 같은 주소에 계속 멈춤
  - rep movsb에서 디버거가 안 넘어감
  - rcx가 엄청 큰 값인데 줄어드는지 모르겠음
  - rep 명령이 무한루프인지 정상인지 구분이 안 됨
  - F7을 눌렀는데 같은 줄에서 안 움직임
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`rep movsb`, `rep stosb` 같은 명령을 디버거에서 스텝 실행(Step Into)했을 때 계속 같은 주소에 멈춰 있는 것처럼 보이는 이유는 코드가 무한루프에 빠진 게 아니라, `RCX`에 담긴 큰 반복 횟수를 하드웨어 수준에서 한 명령으로 소화하고 있기 때문이다 — `RCX`가 실제로 줄어들고 있는지만 확인하면 된다.

## 언제 검색해야 하나
- x64dbg나 IDA 디버거에서 `F7`(Step Into)을 여러 번 눌러도 `RIP`가 `rep movsb` 줄에서 벗어나지 않을 때
- GDB/Pwndbg에서 `stepi`를 반복해도 `$rip`가 계속 같은 주소를 가리킬 때
- 큰 버퍼(수백 KB~수 MB)를 복사/채우는 코드에서 실행이 "멈춘 것 같다"는 느낌이 들 때
- `rep`가 정말 무한루프인지, 그냥 반복 횟수가 커서 시간이 걸리는 것인지 구분이 안 될 때

## 핵심 개념

### REP는 "한 줄"이지만 내부적으로는 RCX번 반복이다
`REP` 계열 프리픽스(`REP`, `REPE`/`REPZ`, `REPNE`/`REPNZ`)는 바로 뒤에 오는 문자열 명령(`MOVSB`, `STOSB`, `SCASB`, `CMPSB` 등)을 `RCX`(32비트 모드는 `ECX`)가 0이 될 때까지 CPU가 마이크로코드 수준에서 반복시키는 구조다. 자세한 의미와 계열별 차이는 REV-0080(REP Prefix와 반복 문자열 명령)에서 다뤘으니 여기서는 핵심만 짚는다.

```
반복:
    if RCX == 0: 종료하고 다음 명령으로
    (문자열 명령 1회 실행)
    RCX -= 1
    DF==0 이면 RSI/RDI 증가, DF==1 이면 감소
    (REPE/REPNE면 ZF 조건도 검사)
```

문제는 어셈블리 소스코드 상으로는 `rep movsb`가 딱 한 줄이라는 점이다. 디스어셈블리 창에는 이 한 줄만 보이고, `RIP`(명령어 포인터) 값도 그 한 주소를 계속 가리키는 것처럼 보일 수 있다 — 디버거가 인터럽트 가능한 반복 명령(interruptible/restartable instruction)의 중간 상태를 다시 같은 주소에서 재개하도록 설계되어 있기 때문이다. 그래서 "Step Into를 눌렀는데 다음 줄로 안 넘어간다"는 인상을 받기 쉽다.

### 진짜 확인해야 할 것: RCX가 줄어드는가
같은 주소에 멈춰 있는 것처럼 보여도, 매번 `RCX`(레지스터 창에서 확인) 값을 보면 실제로는 계속 감소하고 있다. 예를 들어 `RCX = 0x100000`(1MB 복사)이었다면 스텝을 여러 번 눌러도 자연스럽게 계속 그 줄에 있는 것이 정상이다 — 반복이 백만 번 가까이 남아 있으니까. `RCX`가 전혀 줄지 않고 같은 값에 고정돼 있을 때만 진짜 문제(무한루프 또는 잘못된 값 세팅)를 의심해야 한다.

### 진짜 무한루프가 되는 경우
다음과 같은 상황에서는 실제로 `rep`가 끝나지 않을 수 있다:
1. **`RCX`에 `-1`(즉 `0xFFFFFFFFFFFFFFFF`)처럼 매우 큰 값이 실수로 들어간 경우** — 원래 `repne scasb`로 문자열 길이를 잴 때 카운터를 "사실상 무한대"로 설정하는 정상 패턴(REV-0084 참고)과 혼동하기 쉽지만, 이건 `REPNE`가 `ZF`로 조기 종료하는 것을 전제로 한 의도적 설계다. 만약 대상 메모리에 종료 조건(NUL 바이트 등)이 끝까지 없다면 정말로 메모리 끝까지(또는 접근 위반이 날 때까지) 반복한다.
2. **DF(방향 플래그)가 잘못 설정되어 포인터가 원하는 방향과 반대로 움직이는 경우** — 유효하지 않은 메모리 영역으로 계속 진행하다가 결국 접근 위반(access violation/segfault)으로 멈춘다. 이는 "안 끝나는 것"이 아니라 "충돌로 끝나는 것"이라 별개 문제다.
3. **`REPE`/`REPNE`가 걸린 비교 명령인데 비교 대상 버퍼가 계속 같은 결과(또는 계속 다른 결과)만 내서 종료 조건에 절대 도달하지 못하는 경우** — 예를 들어 `repne scasb`로 NUL 바이트를 찾는데 대상이 NUL로 끝나지 않는 손상된 문자열이라면 버퍼 끝을 넘어 계속 스캔한다.

## 화면/코드에서 보이는 징후
```asm
lea     rdi, [big_buffer]
mov     rcx, 100000h      ; 1,048,576 (1MB)
xor     al, al
cld
rep stosb                  ; 이 한 줄에서 스텝이 계속 "안 넘어가는 것처럼" 보임
```
- x64dbg/IDA 디버거: `F7`을 눌러도 디스어셈블리 하이라이트가 `rep stosb` 줄에 계속 남아있음, 레지스터 창의 `RCX`만 조금씩 줄어듦
- GDB: `stepi` 반복 시 `$rip`가 같은 주소, `info registers rcx`로 보면 값이 계속 감소

## 가장 먼저 할 것
`rep` 계열 명령에서 실행이 멈춘 것처럼 보이면, 무조건 **Step Into를 계속 누르지 말고** 다음 두 가지부터 확인한다.
1. 레지스터 창에서 `RCX`(또는 `ECX`) 값을 두 번 이상 연속으로 비교해서 실제로 줄고 있는지 본다.
2. `RCX`의 초기값이 얼마나 큰지 확인한다(반복 직전 `mov rcx, ...` 줄을 위에서 찾는다). 값이 크면 스텝 실행으로 끝까지 보는 것 자체가 비현실적이다.

## 단계별 절차
**1) Step Over로 통째로 건너뛰기 (가장 간단)**

이미 이 블록이 `memcpy`/`memset`류라는 걸 알고 내부 반복 과정이 궁금하지 않다면, `F7`(Step Into) 대신 `F8`(Step Over, x64dbg/IDA 공통)을 누른다. `REP` 명령 전체가 한 번에 실행되고 그 다음 명령에서 멈춘다.

**2) "Run to Cursor"로 반복 종료 지점까지 건너뛰기**

`rep` 다음 줄에 커서를 놓고 x64dbg는 `F4`("Run until Selection"), IDA는 다음 줄에 임시 브레이크포인트를 걸고 `F9`를 누른다. GDB/Pwndbg는 다음 명령 주소에 `tbreak *주소` 후 `continue`.

**3) RCX 값으로 무한루프 여부 판단**

브레이크포인트를 `rep` 명령 위치에 걸고(`F2`, GDB `break *주소`) 여러 번 실행을 멈췄다 재개하면서 `RCX`를 기록한다. 계속 줄어들면 정상, 값이 고정돼 있으면 다른 원인(브레이크포인트가 반복문 진입 전에 걸려서 매번 처음부터 다시 도는 경우 등)을 의심한다.

**4) 접근 위반으로 끝나는지 확인**

정말 끝나지 않는다면 결국 유효하지 않은 메모리에 닿아 예외가 발생하는 경우가 많다. 디버거의 예외 로그(x64dbg 하단 로그, GDB의 `SIGSEGV` 메시지)를 확인해서 어느 주소에서 멈췄는지 본다.

## 명령어/단축키
- IDA: `F8`(Step Over — rep 블록 전체 건너뛰기 권장), `F2`(브레이크포인트), 다음 줄에 브레이크포인트 걸고 `F9`
- x64dbg: `F8`(Step Over), `F4`(Run until Selection), 레지스터 패널에서 `RCX` 실시간 확인
- GDB/Pwndbg: `nexti`(ni, step over), `tbreak *주소` + `continue`, `watch $rcx`로 `RCX` 값이 바뀔 때마다 멈추는 워치포인트 설정 가능(단, 반복이 매우 크면 워치포인트도 느려짐에 주의)

## 출력 해석
- `RCX`가 매 확인마다 감소한다 → 정상적으로 반복 중. 그냥 기다리거나 Step Over/Run to Cursor로 건너뛴다.
- `RCX`가 전혀 안 바뀐다 → 브레이크포인트가 반복 진입 지점(예: 루프 바깥을 감싸는 외부 코드)에 걸려서 매번 초기화된 상태에서 멈추고 있을 가능성이 크다. 브레이크포인트 위치를 `rep` 명령 자체가 아니라 그 이후 주소로 옮겨서 재확인한다.
- `SIGSEGV`/접근 위반 예외가 뜬다 → 무한루프가 아니라 잘못된 `RCX`/`DF`/포인터 값으로 유효 범위를 넘어간 것. `RDI`/`RSI`가 가리키던 원래 버퍼 크기와 `RCX` 값을 비교해서 오버런 여부를 확인한다.

## 흔한 실수
- Step Into(F7)를 큰 반복 횟수의 `rep` 명령에 계속 눌러서 "프로그램이 멈췄다"고 오판하는 것 — 실제로는 정상 진행 중이며 단지 반복 횟수가 많을 뿐이다.
- `RCX = -1`(스캔 계열에서 사실상 무한대로 쓰는 관용 패턴)을 보고 무조건 "이건 버그"라고 판단하는 것 — `REPNE scasb`처럼 `ZF` 조건으로 조기 종료하도록 설계된 정상 패턴일 수 있다(REV-0084 참고).
- `DF` 플래그를 확인하지 않고 "그냥 앞으로 진행하겠지"라고 가정하는 것 — `STD`로 방향이 뒤집힌 상태면 포인터가 예상과 반대 방향으로 움직여 완전히 다른 메모리를 건드리다가 충돌한다.
- 큰 반복을 Step Into로 끝까지 보려다가 디버거 UI가 느려지거나 응답이 없는 것처럼 보이는 것을 "프로그램 버그"로 착각하는 것 — 디버거 자체가 매 스텝마다 화면을 갱신하느라 느려지는 것뿐이다.

## 막혔을 때 다음 체크
- `RCX`가 계속 줄어드는데도 너무 오래 걸린다면 → Step Into를 멈추고 Step Over(F8) 또는 Run to Cursor로 전환.
- 접근 위반이 발생했다면 → `RDI`/`RSI`가 가리키는 원래 버퍼의 크기와 `RCX` 초기값을 비교해서 오버플로우 여부 확인.
- `RCX`가 아예 안 바뀌는 것 같다면 → 브레이크포인트 위치가 반복 시작 지점(루프 밖)인지 다시 확인.
- REP 계열 자체의 동작(REPE/REPNE 차이, DF 의미)이 헷갈리면 → REV-0080으로 이동해서 기본 개념부터 복습.

## 미니 예제

**예제 1 — 정상: 큰 버퍼 복사 (Step Over로 건너뛰어야 함)**
```asm
lea     rdi, [dest]
lea     rsi, [src]
mov     rcx, 500000h    ; 약 5백만 바이트
cld
rep movsb                ; Step Into로 5백만 번 밟으려 하면 매우 오래 걸림 -> Step Over 권장
```
C로 표현하면 그냥 `memcpy(dest, src, 0x500000);` 한 줄이다.

**예제 2 — 진짜 무한루프 후보: 종료 조건이 없는 SCAS**
```asm
lea     rdi, [buf]      ; buf에 NUL 바이트가 전혀 없는 손상된 데이터라고 가정
xor     al, al
mov     rcx, -1          ; 사실상 무한대
cld
repne scasb               ; NUL을 찾을 때까지 반복 -> NUL이 없으면 buf 뒤 메모리까지 계속 진행하다 접근 위반
```
정상적인 `strlen` 스캔이라면 문자열이 NUL로 끝나므로 금방 멈춘다. 멈추지 않는다면 버퍼가 손상되었거나 크기 계산이 잘못됐다는 신호다.

**예제 3 — DF가 뒤집혀서 엉뚱한 방향으로 진행**
```asm
lea     rsi, [buf]
lea     rdi, [dest]
mov     rcx, 1000h
std                       ; 방향 = 역방향(주의: cld가 아니라 std!)
rep movsb                  ; RSI/RDI가 buf/dest 시작 주소에서 "아래로" 내려가며 접근 -> 유효 범위 밖으로 진행 가능
```
이런 코드가 크래시 없이 오래 도는 것처럼 보인다면, `RSI`/`RDI`가 실제로 어느 방향으로 이동하는지 레지스터 창에서 직접 관찰해야 한다.

**예제 4 — GDB에서 반복 여부를 정량적으로 확인**
```text
(gdb) break *0x401020        # rep movsb 명령 주소
(gdb) run
(gdb) p/x $rcx
$1 = 0xfffe0
(gdb) continue
(gdb) p/x $rcx
$2 = 0xffdf0
```
`RCX`가 실제로 줄어드는 것이 확인되면(0xfffe0 -> 0xffdf0) 정상 반복이다.

## 관련 글
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0084 — SCAS와 문자열 검색 패턴
- REV-0490 — 명령어 하나를 건너뛰고 실행되는 것처럼 보일 때
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- `REP`/`REPE`/`REPNE` 프리픽스의 반복·인터럽트 가능(restartable) 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2C, "REP/REPE/REPZ/REPNE/REPNZ" 섹션 기준 (2026-09-08 검증).
- 디버거의 Step Into/Step Over 및 Run to Cursor 동작: x64dbg 공식 문서, Hex-Rays IDA 공식 문서(Hotkeys) 기준.
- GDB `stepi`/`nexti`/`tbreak`/`watch` 동작: GNU GDB 공식 매뉴얼 기준.
