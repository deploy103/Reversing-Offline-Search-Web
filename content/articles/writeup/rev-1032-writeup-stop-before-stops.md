---
id: REV-1032
title: "[Write-up] Stop before stops!"
slug: "rev-1032-writeup-stop-before-stops"
category: "writeup"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB, Pwndbg]
keywords: ["dreamhack Stop before stops", "드림핵 Stop before stops", "Stop before stops 리버싱", "안티디버깅 브레이크포인트 탐지"]
aliases: ["Stop before stops 못풀겠음", "스탑 비포어 스탑스 풀이"]
symptom_keywords: ["드림핵 Stop before stops 어떻게 풀어야 할지 모르겠음", "디버거로 멈추면 프로그램이 이상하게 종료됨"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
"Stop before stops!"는 공개된 상세 write-up을 찾지 못한 문제로, 이 글은 그 사실을 먼저 밝히고, 제목의 "멈추기 전에 멈춰라"라는 표현에서 강하게 유추되는 **안티디버깅(디버거가 프로그램을 멈추게 하는 것을 프로그램이 먼저 감지해서 막는) 계열 문제**로 가정했을 때의 일반적인 접근 절차를 정리한다.

## 언제 검색해야 하나
- 드림핵 "Stop before stops!"를 열었는데 디버거로 실행하면 정상 실행과 다르게 동작하거나 곧바로 종료될 때
- 문제 이름 자체가 "정지시키기 전에 (프로그램이 먼저) 정지시킨다"는 뜻으로 읽혀서, 안티디버깅 관련 문제인지 확인하고 싶을 때
- 브레이크포인트를 걸었더니 프로그램이 크래시하거나 다른 경로로 흘러가서 원인을 모를 때

## 핵심 개념
"dreamhack Stop before stops 리버싱 write-up", "dreamhack Stop before stops reversing writeup" 등으로 검색했으나 이 문제를 구체적으로 다루는 공개 자료를 찾지 못했다. 아래 내용은 **문제명에서 유추한 가설**이며, 실제 바이너리를 분석한 결과가 아니라는 점을 분명히 한다.

제목을 "Stop before (it) stops (you)!" 또는 "(내가 너를) 멈추기 전에 (네가 나를) 멈춘다"로 읽으면, 다음 두 방향의 해석이 가능하다.

1. **디버거 탐지형 안티디버깅**: 프로그램이 실행 중 스스로 "내가 디버거에 의해 멈춰지고(중단되고) 있는가"를 검사한다. Windows라면 `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, PEB의 `BeingDebugged` 플래그 검사, 부모 프로세스 확인(REV-0542) 등이 있고, Linux라면 `ptrace(PTRACE_TRACEME, ...)`을 자기 자신에게 걸어 다른 디버거가 붙지 못하게 막는 기법(REV-0234)이 대표적이다. "Stop"이라는 단어가 디버거의 "멈춤(브레이크)" 동작을 가리킨다고 보는 해석이다.
2. **타이밍 기반 탐지형**: 브레이크포인트에 걸려 실행이 일시 정지되면 실제 걸리는 시간이 정상 실행보다 훨씬 길어진다는 점을 이용해, 두 시점 사이의 시간을 측정(`rdtsc`, `GetTickCount`)해서 "너무 오래 멈춰 있었다"를 감지하는 기법(REV-0237, REV-0872)이다. 이 경우 "stops"는 디버거가 프로그램을 실제로 멈춘 시간 그 자체를 가리킨다고 볼 수 있다.

어느 해석이 맞든, Bronze 2 등급이라는 점을 고려하면 극단적으로 정교한 기법(가상머신 탐지, 커널 드라이버 기반 안티디버깅 등)보다는 위에 나열한 표준적이고 잘 알려진 안티디버깅 API 한두 개를 사용하는 초급 수준일 가능성이 높다.

## 화면/코드에서 보이는 징후
- 디버거 없이 실행하면 정상적으로 진행되는데, x64dbg/GDB로 붙여서 실행하면 곧바로 종료되거나 다른 메시지가 출력됨
- 코드에 `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, `ptrace`, `GetTickCount`, `rdtsc` 같은 함수/명령이 보임
- 정상 흐름과 별개로 프로그램 초반에 짧게 실행되고 사라지는 검사 루틴이 있음

## 가장 먼저 할 것
디버거를 붙이지 않은 "맨 실행" 상태와, 디버거를 붙인 상태에서 동작이 다른지부터 비교한다. 다르다면 안티디버깅이 실제로 걸려 있다는 뜻이므로, `strings`/Import Table에서 `IsDebuggerPresent`, `ptrace`, `GetTickCount` 같은 이름이 있는지 먼저 확인한다.

## 단계별 절차
1. 디버거 없이 한 번, 디버거를 붙인 채로 한 번 실행해 동작 차이를 비교한다.
2. Import Table/strings에서 안티디버깅 관련 API 이름을 찾는다(REV-0119 방식).
3. 해당 API가 호출되는 지점을 IDA/Ghidra에서 찾아, 그 반환값을 검사하는 조건 분기를 확인한다.
4. Windows API 계열이면 그 API의 반환값(또는 PEB 플래그)을 직접 조작하거나, 조건 분기를 무력화(NOP 처리 또는 조건 반전)하는 방식으로 우회한다.
5. Linux `ptrace` 계열이면 `PTRACE_TRACEME` 호출 자체가 실패하도록 만들거나(이미 다른 디버거가 붙어있으면 자연히 실패함을 활용), 해당 호출을 패치해 무력화한다.
6. 타이밍 기반이라면 두 시점 측정값을 비교하는 조건 분기를 찾아 우회하거나, 싱글스텝 대신 조건 분기 이후 지점에 브레이크포인트를 걸어 타이밍 측정 구간 자체를 건너뛴다.
7. 우회 후 정상 흐름대로 디버거에서 계속 분석을 진행한다.

## 명령어/단축키
```text
Windows/x64dbg:
  Options → Anti-Attach 관련 플러그인/옵션 활성화(있다면)
  IsDebuggerPresent 호출 직후 반환값(EAX)을 0으로 강제 설정

Linux/GDB(Pwndbg):
  catch syscall ptrace   # ptrace 호출 지점에서 멈추기
  set $rax = 0           # 필요 시 반환값 조작(문맥에 따라 다름)
```

## 출력 해석
우회에 성공하면 디버거를 붙인 상태에서도 디버거 없이 실행했을 때와 동일한 흐름으로 진행된다. 여전히 다르게 동작한다면 탐지 지점이 하나가 아니라 여러 곳에 흩어져 있을 수 있으므로, Import Table에서 안티디버깅 관련 API를 하나씩 전부 xref로 확인해야 한다.

## 흔한 실수
- 문제 이름에서 유추한 가설을 검증 없이 확정된 사실처럼 다루는 것 — 이 글의 내용도 실제 바이너리를 열어보기 전까지는 가설일 뿐이다.
- 안티디버깅 우회에만 집중하다가, 우회 이후에 나오는 진짜 검증 로직(플래그 비교 등)을 놓치는 것 — 안티디버깅은 대부분 "진짜 문제"로 가기 전의 관문일 뿐이다.
- 정적 분석 없이 무작정 디버거를 계속 재시작하며 시행착오만 반복하는 것 — Import Table과 문자열을 먼저 훑으면 어떤 종류의 안티디버깅인지 훨씬 빨리 감을 잡을 수 있다.

## 막혔을 때 다음 체크
- Windows `IsDebuggerPresent` 우회 개념이 필요하면 → REV-0235 IsDebuggerPresent 우회 개념
- Linux `ptrace PTRACE_TRACEME` 안티디버깅 개념이 필요하면 → REV-0234 ptrace PTRACE_TRACEME 안티디버깅
- 부모 프로세스 확인 방식의 안티디버깅이 궁금하면 → REV-0542 부모 프로세스 확인 안티디버깅(explorer.exe 체크)
- 타이밍 기반 안티디버깅 전반이 궁금하면 → REV-0237 RDTSC Time Check 안티디버깅
- 디버거에서 갑자기 종료될 때 체크리스트가 필요하면 → REV-0240 디버거에서 갑자기 종료될 때 체크리스트

## 미니 예제
검증되지 않은 추정이지만, 흔한 안티디버깅 초급 패턴을 예시로 들면 다음과 같다.
```c
if (IsDebuggerPresent()) {
    printf("Stop debugging!\n");
    exit(1);
}
// 정상 로직 계속...
```
이 구조라면 `IsDebuggerPresent` 호출 직후의 조건 분기를 찾아 무조건 "거짓"으로 평가되게 만들면(반환값을 0으로 바꾸거나 분기 자체를 NOP 처리) 우회할 수 있다. 다시 강조하지만 이는 실제 "Stop before stops!" 문제의 코드가 아니라 이름에서 유추한 예시일 뿐이다.

## 관련 글
- REV-0235 — IsDebuggerPresent 우회 개념
- REV-0234 — ptrace PTRACE_TRACEME 안티디버깅
- REV-0542 — 부모 프로세스 확인 안티디버깅(explorer.exe 체크)
- REV-0237 — RDTSC Time Check 안티디버깅
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트

## 출처/검증
- WebSearch로 "dreamhack Stop before stops writeup", "Stop before stops reversing challenge dreamhack anti-debugging" 등을 검색했으나 이 문제를 구체적으로 다루는 공개 write-up을 찾지 못했다(2026-09-10 검증).
- 문제명(Stop before stops!), 티어(Bronze 2), 풀이자 수(455명)는 작업 지시에 포함된 드림핵 워게임 목록 조사 결과를 그대로 인용했다.
- 본문의 안티디버깅 관련 추정과 우회 절차는 실제 이 문제의 검증된 분석이 아니라, 문제명에서 유추한 가설과 일반적인 안티디버깅 기법 지식(REV-0234, REV-0235, REV-0237, REV-0542 등 기존 문서 기준)을 조합한 가이드임을 명시한다.
