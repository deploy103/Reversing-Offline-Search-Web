---
id: REV-0872
title: "타이밍 기반 안티디버깅으로 스텝 실행이 너무 느려서 걸릴 때"
slug: "rev-0872-timing-anti-debug-slow-stepping-detected"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg]
keywords:
  - RDTSC 타이밍 체크
  - GetTickCount QueryPerformanceCounter
  - step 실행 시간 초과
  - timing anti-debug bypass
  - 스텝하면 걸림
symptom_keywords:
  - 한줄씩 스텝하면 프로그램이 종료됨
  - 그냥 실행하면 되는데 스텝하면 안됨
  - RDTSC 값 차이가 너무 큼
  - 타이밍 체크 때문에 분석이 안됨
aliases:
  - 타이밍 안티디버깅 대응
  - RDTSC 스텝 감지
  - GetTickCount 스텝 감지
  - 느린 스텝 걸림
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
타이밍 기반 안티디버깅은 코드 구간 실행 전후의 타임스탬프(`RDTSC`, `GetTickCount`, `QueryPerformanceCounter`, Linux의 `clock_gettime` 등) 차이를 재서 "이 짧은 구간이 비정상적으로 오래 걸렸다"는 사실만으로 디버거의 존재(특히 사람이 한 줄씩 Step 하고 있다는 것)를 추측하므로, 그냥 실행(`F9`/`continue`)하면 통과하던 구간도 Step Into/Over로 한 줄씩 밟으면 그 구간 자체가 실제로 느려져서 걸리게 된다.

## 언제 검색해야 하나
- 프로그램을 F9로 그냥 쭉 실행하면 멀쩡한데, F7/F8로 한 줄씩 스텝하며 확인하면 특정 지점에서 프로그램이 이상 종료되거나 다른 분기를 탈 때
- `rdtsc` 명령어 두 번 사이의 값 차이를 비교하는 코드나, `GetTickCount()`/`QueryPerformanceCounter()`를 시작·끝에 각각 호출하는 패턴을 발견했을 때(REV-0087, REV-0237, REV-0538, REV-0572 참고)
- 재현이 매번 불안정해서(빠르게 스텝하면 통과, 느리게 스텝하면 실패) 원인을 못 찾고 있을 때
- 이 체크를 통과시키면서 그 구간의 코드를 여전히 자세히 들여다보고 싶을 때

## 핵심 개념

### 타이밍 체크의 기본 구조
```c
start = read_timestamp();
... // 보호하려는 코드 구간 (보통 몇 개 안 되는 명령어)
end = read_timestamp();
if (end - start > THRESHOLD) {
    // 디버거가 붙어 스텝 중이라고 판단 → 종료/오동작
}
```
정상적으로 CPU가 이 구간을 그냥 실행하면 수십~수백 사이클 만에 끝나지만, 사람이 Step Into(`F7`, `si`)로 한 줄씩 밟으면 각 스텝마다 디버거가 사용자 입력을 기다리고 화면을 갱신하는 시간이 끼어들어 같은 구간이 수백만 배 더 오래 걸린다. 이 차이가 `THRESHOLD`를 넘는 순간 안티디버깅 코드는 "지금 이 구간이 비정상적으로 느리다 = 디버거가 붙어서 한 줄씩 실행되고 있다"고 판단한다.

### 왜 재현이 "가끔만" 되는 것처럼 보이는가
이 체크는 절대적인 디버거 존재 여부가 아니라 **그 순간 실행 속도**만 본다. 그래서 같은 디버거를 붙여도 F9로 빠르게 실행하면 통과하고, F7로 천천히 스텝하면 걸린다. 분석자 입장에서는 "왜 어떨 때는 되고 어떨 때는 안 되지"라며 혼란스러울 수 있지만, 실제로는 일관된 규칙(느리면 걸린다)을 따르고 있는 것이다.

### 대응 전략의 방향
핵심은 "그 짧은 보호 구간 자체는 스텝하지 않고 통과시키되, 그 앞뒤는 원하는 만큼 자세히 본다"는 것이다.
1. 타임스탬프를 읽는 두 지점을 미리 찾아, 그 사이 구간은 Step 대신 **Run to cursor**(그 구간 끝까지 한 번에 실행)로 건너뛴다.
2. 비교 직후의 분기(`Jcc`)에 브레이크포인트를 걸어, 그 분기 결과(`end - start`가 THRESHOLD를 넘었는지)를 값으로 확인만 하고 필요하면 플래그를 조작해 원하는 방향으로 보낸다(REV-0174 참고).
3. 타임스탬프 자체를 읽는 명령(`rdtsc`) 직후 반환값을 조작해서 "차이가 작게 나온 것처럼" 속이는 방법도 있으나, 이는 실행 중 레지스터 값을 직접 바꾸는 방식이라 신중하게 적용해야 한다.

## 화면/코드에서 보이는 징후
- 코드에 `rdtsc` 명령어가 짧은 간격을 두고 두 번 나오고, 그 사이 값을 빼서 비교하는 `sub`/`cmp` 패턴이 보인다.
- Import 목록에 `GetTickCount`, `GetTickCount64`, `QueryPerformanceCounter`가 있고, 두 번 호출한 결과를 빼는 코드가 근처에 있다.
- F9로 실행할 때는 안 보이던 크래시/조기 종료가 F7/F8로 스텝할 때만 재현된다.
- 스텝 속도(빠르게 연타 vs 천천히 하나씩)에 따라 결과가 달라진다.

## 가장 먼저 할 것
1. 문제가 되는 구간이 타이밍 체크인지부터 확인한다(직전에 `rdtsc`/`GetTickCount`류 호출이 있는지).
2. 그 구간의 시작과 끝(두 번째 타임스탬프를 읽는 지점) 주소를 각각 확인한다.
3. 그 구간을 Step 대신 Run to cursor/임시 브레이크포인트로 건너뛰도록 계획한다.

## 단계별 절차

**x64dbg**
1. 첫 번째 `rdtsc`(또는 `GetTickCount` 호출) 직후에 멈춘 상태에서, 두 번째 타임스탬프를 읽는 명령어 줄을 찾는다.
2. 그 줄에서 우클릭 → "Run until this line"(또는 커서를 두고 `F4`, "Run to Cursor")을 사용해 그 사이 구간을 스텝 없이 한 번에 실행시킨다.
3. 두 번째 타임스탬프 직후, 값 비교(`cmp`/`sub`) 결과를 확인하고 필요하면 이제부터 다시 F7로 자세히 스텝을 재개한다.
4. 비교 결과 분기가 항상 "느림"으로 판단된다면, 플래그 창에서 관련 플래그를 직접 뒤집어 반대 분기로 보낸다(REV-0174의 플래그 강제 조작 참고).

**GDB / Pwndbg**
1. 첫 번째 타임스탬프 호출 이후 지점에 브레이크포인트를 건다.
2. 두 번째 타임스탬프를 읽는 지점에도 브레이크포인트를 걸어둔다.
3. 그 사이는 `si`/`ni` 대신 `continue`로 단번에 진행한다.
   ```
   (gdb) break *0x401210   ; 첫 rdtsc 직후
   (gdb) break *0x401230   ; 두 번째 rdtsc 직후
   (gdb) continue          ; 첫 브레이크포인트까지
   (gdb) continue          ; 바로 두 번째 브레이크포인트까지 (스텝 없이 순식간에 통과)
   ```
4. 비교 결과 레지스터/플래그를 확인하고, 필요하면 `set $eflags = ...`나 결과 레지스터 값을 직접 원하는 값으로 덮어써서 통과시킨다.

## 명령어/단축키
- x64dbg: "Run to Cursor"(`F4` 또는 우클릭 메뉴), 임시 브레이크포인트로 구간 건너뛰기, 플래그 창 직접 조작
- GDB/Pwndbg: `break *ADDR`로 구간 양 끝에 걸고 `continue`로 건너뛰기, `set $reg = value`(비교 결과 레지스터 강제 조작), `set $eflags = value`

## 출력 해석
- 비교 직후 분기 플래그를 확인했을 때 항상 "차이가 크다" 방향으로 나온다면, 그 구간을 스텝으로 지나왔다는 뜻이다 — Run to Cursor/브레이크포인트 건너뛰기로 다시 시도해본다.
- 값 차이를 직접 확인하고 싶다면 두 타임스탬프 값을 레지스터에서 읽어 직접 빼보고(`p $rax - $prev_rax`류), THRESHOLD로 추정되는 값과 비교해본다.

## 흔한 실수
- 보호 구간까지 포함해서 전체를 F7로 스텝하며 "이상하게 여기서 죽네"라고 반복 재현만 하는 것 — 원인이 스텝 자체라는 걸 깨닫지 못하면 계속 같은 실수를 반복하게 된다.
- Run to Cursor로 건너뛸 범위를 너무 넓게 잡아서, 정작 보고 싶었던 다른 로직까지 한 번에 지나쳐버리는 것 — 타임스탬프를 읽는 두 지점 "사이만" 정확히 건너뛰어야 한다.
- 이 문제를 REV-0865(CPU 사용량 급증)와 혼동하는 것 — 이쪽은 CPU 사용량이 아니라 "경과 시간"이 문제가 되는 경우다.

## 막혔을 때 다음 체크
- 타임스탬프 읽는 지점 자체를 못 찾겠다면 → REV-0237(RDTSC Time Check 안티디버깅), REV-0538(타이밍 기반 안티디버깅 다양한 변형), REV-0572(GetTickCount/QueryPerformanceCounter 안티디버깅)를 참고해 패턴을 먼저 식별한다.
- 다른 안티디버깅과 겹쳐 있는지 의심된다면 → REV-0871(안티디버깅 원인 좁히기 실전)로 전체 실행을 비교해본다.
- 이 체크를 우회한 후에도 계속 다른 곳에서 걸린다면 → REV-0240 체크리스트로 돌아가 다른 범주를 확인한다.

## 미니 예제
```asm
rdtsc
mov [ebp-4], eax        ; start 저장
call check_password       ; 보호하려는 구간
rdtsc
sub eax, [ebp-4]          ; end - start
cmp eax, 100000
ja  detected_debugger
```
`call check_password` 앞뒤 두 `rdtsc` 사이를 F7로 한 줄씩 밟으면 `eax`(경과 사이클)가 `100000`을 훌쩍 넘어 `ja detected_debugger`로 분기한다. 이 구간 전체를 Run to Cursor로 한 번에 통과시키면 정상 실행과 비슷한 사이클 수가 나와 분기를 피할 수 있다.

## 관련 글
- REV-0237 — RDTSC Time Check 안티디버깅
- REV-0538 — 타이밍 기반 안티디버깅 다양한 변형
- REV-0871 — 안티디버깅 때문에 디버거에서 갑자기 종료될 때 원인 좁히기(실전)
- REV-0865 — 디버깅 중 CPU 사용량이 100%로 치솟을 때

## 출처/검증
- `RDTSC` 명령어와 타이밍 기반 안티디버깅 원리: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "RDTSC—Read Time-Stamp Counter" 섹션 기준.
- `GetTickCount`/`QueryPerformanceCounter`를 이용한 타이밍 체크: Microsoft Learn API 문서 및 일반 안티디버깅 참고 자료 기준.
- x64dbg "Run to Cursor" 기능: x64dbg 공식 문서(Debugging) 기준.
- 2026-09-09 검증.
