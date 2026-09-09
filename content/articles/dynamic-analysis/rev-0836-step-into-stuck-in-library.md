---
id: REV-0836
title: "Step Into가 라이브러리 내부로 계속 들어가서 못 나올 때"
slug: "rev-0836-step-into-stuck-in-library"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords: ["Step Into 라이브러리", "step-mode", "gdb skip", "F7 계속 들어감", "ntdll 안에 갇힘", "printf 안에서 못 빠져나옴"]
aliases: ["Step Into가 안 빠져나옴", "F7 눌렀는데 라이브러리로 들어감", "gdb step이 라이브러리에서 반복됨"]
symptom_keywords: ["F7을 계속 눌러도 ntdll 안에서 못 나옴", "step을 눌러도 printf 안에서 계속 머무름", "라이브러리 함수 내부에서 몇백 번 스텝해야 함", "step-mode가 뭔지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Step Into(x64dbg F7, GDB `step`)는 CALL을 만나면 무조건 함수 내부로 들어가므로, 디버그 정보가 없는 라이브러리 함수(`printf`, `ntdll!Rtl*` 등) 안으로 들어가면 소스 라인 대응이 없어 명령어 단위로 수백 번을 눌러야 벗어나는 것처럼 느껴지는데, 이는 정상 동작이며 GDB는 `finish`/`skip`으로, x64dbg는 `Ctrl+F9`(Execute till return)나 Step Over로 즉시 빠져나올 수 있다.

## 언제 검색해야 하나
- x64dbg에서 F7(Step Into)을 누르다가 `ntdll.dll`, `kernel32.dll` 내부로 들어가 CPU 창 주소가 `함수+오프셋`만 계속 바뀔 때
- GDB에서 `step`을 눌렀는데 소스 라인(`chall.c:12` 같은 표시)이 안 보이고 `__vfprintf_internal ()`처럼 함수 이름+주소만 계속 나올 때
- 라이브러리 함수 안에서 아무리 스텝해도 원래 보던 `main` 코드로 안 돌아올 때
- GDB `step-mode`가 무엇인지, x64dbg에 그런 옵션이 있는지 궁금할 때

## 핵심 개념

### 왜 Step Into는 라이브러리 안에서 "반복"처럼 보이는가
디버그 정보(DWARF의 라인 테이블, PDB)가 있는 코드는 한 소스 라인이 끝나면 다음 라인으로 한 번에 넘어가지만, 디버그 정보가 없는 라이브러리 함수는 그런 경계가 없어 디버거가 명령어 단위로만 멈춘다. `printf` 안에서 `__vfprintf_internal`, `_IO_*` 계열 헬퍼를 거치며 수백 개의 명령어를 통과해야 리턴하는 경우, Step Into를 누른 횟수만큼만 진행되므로 체감상 "안 빠져나온다"고 느껴진다.

### GDB — step-mode와 skip
GDB의 `step`은 라인 정보가 없는 함수를 만나면 기본적으로(`step-mode off`) 그 함수를 통째로 실행하고 건너뛴다. 하지만 Pwndbg나 일부 `.gdbinit`이 `set step-mode on`을 걸어두면, 라인 정보가 없어도 명령어 단위로 억지로 멈춰 세워 라이브러리 내부를 벗어나지 못하는 것처럼 보인다. `show step-mode`로 확인하고 `set step-mode off`로 끄면 근본적으로 해결된다. 자세한 사례는 REV-0720에서 다룬다.

### x64dbg — 라이브러리 내부에서 즉시 빠져나오기
x64dbg는 GDB의 `skip` 같은 "이후로 이 함수는 건너뛴다" 기능이 기본으로 없으므로, 실전에서는 다음 두 가지를 쓴다.
1. **Ctrl+F9(Execute till return)**: 현재 함수가 리턴할 때까지 실행해서 즉시 호출자로 돌아온다.
2. **애초에 F8(Step Over)을 쓴다**: 라이브러리 호출 라인에서는 처음부터 F7 대신 F8을 눌러 함수 내부에 들어가지 않는다.

### 콜스택으로 몇 단계나 들어와 있는지 먼저 확인
`printf` → `vfprintf` → `_IO_vfprintf`처럼 여러 단계 중첩된 경우, GDB `bt`나 x64dbg Call Stack 창으로 몇 단계 들어와 있는지 먼저 보면 `finish`/`Ctrl+F9`를 몇 번 반복해야 할지 가늠할 수 있다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) step
0x00000000004a3d21 in __vfprintf_internal ()
(gdb) step
0x00000000004a3d2f in __vfprintf_internal ()
```
소스 파일/라인 번호 없이 `함수이름+오프셋` 표시만 반복되면 전형적인 증상이다. x64dbg에서는 CPU 창 상단 모듈 표시가 대상 EXE가 아니라 `ntdll.dll`/`KERNELBASE.dll`로 바뀐 채 F7을 눌러도 그 안에서만 머문다.

## 가장 먼저 할 것
지금 당장 빠져나오고 싶다면 GDB는 `finish`, x64dbg는 `Ctrl+F9`(Execute till return)를 누른다. 애초에 라이브러리 내부를 볼 필요가 없었다면 다음부터는 그 호출 줄에서 Step Into 대신 Step Over를 쓴다.

## 단계별 절차
1. `bt`(GDB) 또는 Call Stack 창(x64dbg)으로 몇 단계나 들어와 있는지 확인한다.
2. GDB: `show step-mode`로 원인 확인 → `set step-mode off`로 근본 해결.
3. GDB: 반복적으로 들어가고 싶지 않은 함수는 `skip function 함수이름` 또는 `skip -rfunction ^__.*`로 등록한다.
4. x64dbg: `Ctrl+F9`로 현재 함수를 즉시 빠져나온다. 여러 단계 중첩됐다면 필요한 만큼 반복한다.
5. 다음부터는 라이브러리 호출 줄에서 F8/`next`를 기본으로 쓰고, 정말 내부를 봐야 할 때만 F7/`step`을 쓴다.

## 명령어/단축키
```gdb
show step-mode
set step-mode off
finish
bt
skip function FUNC
info skip
```
```text
x64dbg: F7(Step Into), F8(Step Over), Ctrl+F9(Execute till return)
```

## 출력 해석
`bt`/Call Stack에서 여러 프레임이 라이브러리 내부 함수로 쌓여 있다면 `finish`/`Ctrl+F9`를 그 프레임 수만큼 반복해야 원래 코드로 돌아온다. `show step-mode`가 `on`으로 나오면 그것이 근본 원인이다.

## 흔한 실수
- `step-mode`가 켜진 줄 모르고 GDB가 고장났다고 오해하는 것.
- x64dbg에 GDB의 `skip` 같은 기능이 있을 거라 기대하고 찾아 헤매는 것 — 대신 Execute till return이나 Step Over 습관으로 대체해야 한다.
- 몇 단계나 들어와 있는지 확인하지 않고 무작정 `finish`/`Ctrl+F9`를 한 번만 누르고 "안 나왔다"고 포기하는 것.
- 관심 없는 라이브러리 호출에서도 습관적으로 Step Into를 눌러 이 상황을 반복하는 것.

## 막혔을 때 다음 체크
- Step Into와 Step Over의 기본 차이가 헷갈린다면 → REV-0170 Step Into와 Step Over 차이
- 반대로 Step Over가 오히려 함수 안으로 들어가 버린다면 → REV-0837 Step Over인데 함수 안으로 들어가 버릴 때
- GDB의 step-mode/skip 사례를 더 자세히 보고 싶다면 → REV-0720 GDB에서 특정 라이브러리 함수 스텝 진입이 계속 반복될 때
- 함수를 빠져나와 리턴값을 확인하는 법이 궁금하다면 → REV-0171 Run Until Return과 함수 빠져나오기

## 미니 예제
GDB에서 `printf` 호출 줄에 `step`을 눌렀더니 `__vfprintf_internal` 내부로 들어가 수십 번을 눌러도 안 빠져나왔다. `bt`로 확인하니 `main → printf → __vfprintf_internal` 3단계였고, `finish`를 두 번 실행하자 곧바로 `main`으로 돌아왔다. 이후로는 그 줄에서 `step` 대신 `next`를 사용해 애초에 들어가지 않도록 바꿨다.

## 관련 글
- REV-0170 — Step Into와 Step Over 차이
- REV-0171 — Run Until Return과 함수 빠져나오기
- REV-0720 — GDB에서 특정 라이브러리 함수 스텝 진입이 계속 반복될 때
- REV-0837 — Step Over인데 함수 안으로 들어가 버릴 때

## 출처/검증
- GDB `step`/`step-mode`/`skip`/`finish` 동작: GDB 공식 매뉴얼("Continuing and Stepping", "Skipping Over Functions and Files" 챕터) 기준(2026-09-09 검증).
- x64dbg의 Step Into/Step Over/Execute till return 동작: x64dbg 공식 문서 기준.
