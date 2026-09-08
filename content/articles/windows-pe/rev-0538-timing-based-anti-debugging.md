---
id: REV-0538
title: "타이밍 기반 안티디버깅 다양한 변형"
slug: "rev-0538-timing-based-anti-debugging"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["RDTSC", "GetTickCount", "QueryPerformanceCounter", "timeGetTime", "타이밍 안티디버깅", "NtQuerySystemTime", "timing check"]
aliases: ["타이밍 체크 안티디버깅", "RDTSC 트릭", "실행 시간 측정 탐지", "GetTickCount 안티디버깅", "타임 델타 검사"]
symptom_keywords: ["rdtsc 명령어가 두 번 연속으로 나온다", "GetTickCount를 호출 전후로 두 번 부르고 차이를 비교한다", "QueryPerformanceCounter로 시간을 재는 코드가 있다", "디버깅할 때만 타임아웃처럼 종료된다", "스텝 실행하면 감지되고 그냥 실행하면 통과한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
디버거로 코드를 한 줄씩 실행(스텝 실행)하거나 브레이크포인트에서 멈추면 실제 CPU 실행 시간이 눈에 띄게 늘어나기 때문에, `RDTSC`나 `GetTickCount`/`QueryPerformanceCounter` 같은 시간 측정 수단으로 특정 구간 실행 전후 시간 차이를 재서 그 값이 정상적인 실행 속도보다 비정상적으로 크면 "디버거가 개입하고 있다"고 판단하는 것이 타이밍 기반 안티디버깅의 핵심이다.

## 언제 검색해야 하나
- 코드 중간에 `RDTSC` 명령어가 짧은 간격을 두고 두 번 나오고, 그 사이 값을 빼서 어떤 임계값과 비교하는 패턴을 발견했을 때
- Import Table에 `GetTickCount`/`GetTickCount64`/`timeGetTime`/`QueryPerformanceCounter`가 있고, 이 함수들이 코드 블록 앞뒤로 쌍을 이루어 호출될 때
- x64dbg로 스텝 실행(`F7`/`F8`)하면서 코드를 따라갈 때만 프로그램이 갑자기 종료되거나 다른 값을 내놓고, `F9`(Run)로 쭉 실행하면 정상 동작하는 상황을 마주쳤을 때
- CTF 문제 설명에 "너무 느리게 분석하면 막힌다"는 힌트가 있을 때

## 핵심 개념

### 왜 디버깅하면 시간이 늘어나는가
디버거로 프로그램을 실행하면 다음과 같은 이유로 실제 실행 시간이 정상 실행 대비 훨씬 길어진다.
- 브레이크포인트에서 멈춰 있는 동안 사람이 레지스터/메모리를 살펴보는 시간이 그대로 흘러간다.
- 싱글 스텝(`F7`)으로 한 줄씩 실행하면 명령어 하나마다 CPU가 트랩(디버그 예외)을 걸고 디버거로 제어가 넘어갔다가 다시 돌아오는 오버헤드가 매 명령어마다 발생한다.
- 조건부 로깅, 조건부 브레이크포인트 등 디버거의 부가 기능이 켜져 있으면 추가 오버헤드가 생긴다.

정상적으로(디버거 없이) 실행하면 아주 짧은 코드 블록은 마이크로초~나노초 단위로 끝나지만, 디버깅 중에는 이 값이 수백 밀리초~수 초로 뛸 수 있다. 이 차이를 감지하는 것이 타이밍 기반 안티디버깅이다.

### 주요 변형 1: RDTSC (Read Time-Stamp Counter)
```asm
rdtsc          ; EDX:EAX에 CPU 사이클 카운터 로드
mov  [t1], eax
; ... 보호 대상 코드 ...
rdtsc
sub  eax, [t1]
cmp  eax, THRESHOLD
ja   detected
```
`RDTSC`는 CPU가 부팅된 이후 누적된 클럭 사이클 수를 `EDX:EAX`에 반환하는 특권 없는 명령어라 유저 모드 코드에서 바로 사용할 수 있고, 오버헤드가 거의 없어 매우 자주 쓰인다. 가상화 환경(VM)에서는 `RDTSC`가 하이퍼바이저에 의해 트랩되어 값이 왜곡될 수 있다는 점도 참고할 만하다.

### 주요 변형 2: GetTickCount / GetTickCount64 / timeGetTime
```c
DWORD t1 = GetTickCount();
// ... 보호 대상 코드 ...
DWORD t2 = GetTickCount();
if (t2 - t1 > 100) { /* detected */ }
```
`GetTickCount`는 시스템이 부팅된 이후 경과한 밀리초를 반환하는 Win32 API로, 해상도가 낮지만(보통 15.6ms 단위) 구현이 매우 간단해 흔히 쓰인다. `timeGetTime`(winmm.dll)은 더 높은 해상도를 제공하는 유사한 함수다.

### 주요 변형 3: QueryPerformanceCounter / QueryPerformanceFrequency
```c
LARGE_INTEGER f, t1, t2;
QueryPerformanceFrequency(&f);
QueryPerformanceCounter(&t1);
// ... 보호 대상 코드 ...
QueryPerformanceCounter(&t2);
double elapsed = (double)(t2.QuadPart - t1.QuadPart) / f.QuadPart;
```
`QueryPerformanceCounter`는 고해상도 타이머로 마이크로초 단위까지 정밀하게 시간을 측정할 수 있어, 훨씬 짧은 코드 구간에도 타이밍 검사를 적용할 수 있다.

### 주요 변형 4: 예외 처리 지연 측정
`INT 3`이나 `INT 2D` 같은 예외를 일부러 발생시키고, 그 예외가 처리되어 코드가 다시 실행되기까지 걸리는 시간을 재는 방식도 있다. 디버거가 붙어 있으면 예외를 먼저 가로채 사용자에게 보여주는 과정에서 지연이 생기기 때문에, 이 지연 시간 자체가 탐지 신호가 된다.

### 임계값(threshold) 설정의 어려움
타이밍 기반 검사는 느린 CPU, 시스템 부하, VM 환경 등에서도 오탐(false positive)이 나올 수 있어 임계값을 너무 낮게 잡으면 정상 사용자 환경에서도 오작동하고, 너무 높게 잡으면 디버깅 탐지력이 떨어진다는 근본적인 트레이드오프가 있다. 이 때문에 실전에서는 여러 변형을 조합하거나, 절대적인 임계값 대신 "여러 번 반복 측정한 값의 통계적 편차"를 보는 정교한 구현도 존재한다.

## 화면/코드에서 보이는 징후
- 짧은 구간을 사이에 두고 같은 시간 측정 API(또는 `RDTSC`)가 정확히 두 번 호출됨.
- 두 값의 차이를 계산한 뒤 상수와 `cmp`하는 코드가 바로 뒤따름.
- x64dbg로 스텝 실행할 때만 감지되고, `F9`로 자유 실행하면 감지되지 않는 비대칭적인 동작.
- 코드 안에 `THRESHOLD` 역할을 하는 작은 상수(예: `100`, `1000`, `0x100000` 등 문맥에 따라 밀리초 또는 사이클 수)가 하드코딩되어 있음.

## 가장 먼저 할 것
`RDTSC` 또는 시간 측정 API 호출 쌍을 찾으면, 그 사이에 있는 "보호 대상 코드"가 실제로 무엇을 하는지부터 확인한다. 단순히 시간만 재는 게 목적이 아니라, 그 사이 구간에서 실제로 중요한 로직(예: 키 검증)이 함께 실행되는 경우도 많으므로 검사 로직과 보호 대상 로직을 분리해서 파악해야 한다.

## 단계별 절차
**1) 측정 쌍 찾기**

IDA에서 `RDTSC`나 시간 측정 API의 xref를 모두 나열해 짝을 이루는 호출을 찾는다.

**2) 비교 임계값 확인**

두 값의 차이를 계산한 직후 `cmp`/`ja`/`jg` 등으로 비교하는 상수를 확인한다. 이 값이 검사 민감도를 결정한다.

**3) x64dbg로 감지되는지 재현**

의심 구간에 `F7`로 스텝 실행하며 진입해, 실제로 감지 분기를 타는지 관찰한다. 반대로 `F9`로 전체 실행하면 통과하는지도 비교한다.

**4) 우회 방법 이해**

가장 흔한 우회는 두 가지다. 첫째, x64dbg의 `TitanHide`/ScyllaHide 플러그인으로 `RDTSC`를 후킹해 항상 짧은 델타를 리턴하도록 만드는 것. 둘째, 검사 직후 비교 분기(`ja detected` 등)를 NOP으로 패치하거나 조건을 반전시켜 검사 자체를 무력화하는 것이다. 단순히 스텝 실행 대신 검사 구간 전체를 건너뛰도록 브레이크포인트+`Set EIP/RIP`를 활용하는 방법도 있다.

## 명령어/단축키
- x64dbg: `F7`(Step Into), `F8`(Step Over), `F9`(Run) — 감지 여부가 실행 방식에 따라 달라지는지 비교
- x64dbg: 비교 분기 지점에 `bp`를 걸고 도달 시 레지스터 값을 확인해 실제 델타 값을 관찰
- IDA: `RDTSC` 명령어는 니모닉 검색(`Alt+T`)으로 전체 바이너리에서 빠르게 찾을 수 있음

## 출력 해석
- `RDTSC`의 결과는 `EDX:EAX`(상위 32비트:하위 32비트)에 담기는 64비트 값이다. 델타를 계산할 때 `EAX`만 보고 상위 비트를 무시하는 구현도 있으니, `EDX`도 함께 확인해야 값을 정확히 해석할 수 있다.
- `GetTickCount` 계열은 밀리초 단위이므로 델타 값이 두 자리수 이하로 나오면 정상, 수백~수천이면 디버깅 중일 가능성이 높다.
- `QueryPerformanceCounter` 델타는 `QueryPerformanceFrequency`로 얻은 주파수로 나눠야 실제 초 단위 시간이 되므로, 두 값을 함께 확인해야 한다.

## 흔한 실수
- `RDTSC` 결과 중 `EAX`만 보고 `EDX`를 무시해서 델타 계산을 잘못 이해하는 것.
- 타이밍 검사가 한 번만 있다고 가정하는 것 — 실전에서는 여러 구간에 흩어져 있는 경우가 흔하다.
- VM이나 저사양 환경에서 테스트하며 "임계값이 이상하게 낮다/높다"고 오해하는 것 — 환경에 따라 정상 실행 시간도 달라질 수 있음을 감안해야 한다.
- 검사 분기를 NOP 처리할 때 스택/레지스터 정리 코드까지 함께 지워버려서 이후 코드가 깨지는 것.

## 막혔을 때 다음 체크
- 예외 발생/처리 지연을 이용하는 변형이 SEH와 결합된 경우가 궁금하다면 → REV-0539 SEH 기반 안티디버깅 심화
- `RDTSC`가 아니라 프로세스 정보 API 기반 검사가 궁금하다면 → REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- 여러 안티디버깅 기법을 한눈에 비교하고 싶다면 → REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표
- x64dbg 스텝 실행 자체가 낯설다면 → REV-0127 x64dbg로 EXE 첫 분석 시작

## 미니 예제
```c
#include <windows.h>
#include <intrin.h>

BOOL TimingCheck(void) {
    unsigned __int64 t1 = __rdtsc();
    // 보호 대상 코드 (예: 짧은 루프)
    volatile int x = 0;
    for (int i = 0; i < 100; i++) x += i;
    unsigned __int64 t2 = __rdtsc();
    return ((t2 - t1) > 100000); // 임계값(환경에 따라 조정)
}

int main(void) {
    if (TimingCheck()) {
        ExitProcess(1);
    }
    printf("Enter flag: ");
    return 0;
}
```
디스어셈블리에서는 `rdtsc` 두 번 사이에 짧은 루프가 있고, `sub`로 델타를 계산한 뒤 `cmp eax, <threshold>` / `ja detected` 형태로 이어지는 패턴이 전형적이다.

## 관련 글
- REV-0539 — SEH 기반 안티디버깅 심화
- REV-0533 — NtQueryInformationProcess로 하는 안티디버깅
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- `RDTSC` 명령어의 동작(비특권 명령, `EDX:EAX`에 타임스탬프 카운터 반환)은 Intel SDM Volume 2B의 `RDTSC` 설명 기준.
- `GetTickCount`, `QueryPerformanceCounter`, `QueryPerformanceFrequency`, `timeGetTime` API 시그니처와 동작은 Microsoft 공식 문서(learn.microsoft.com) 기준.
- 타이밍 기반 안티디버깅의 일반적인 구현 패턴은 다수의 공개 안티디버깅 예제 및 CTF 라이트업에서 반복적으로 확인되는 방식을 정리한 것이다(2026-09-08 확인).
