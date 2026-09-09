---
id: REV-0932
title: "안티디버깅 기법 종류 빠른 참조표(정리본)"
slug: "rev-0932-anti-debug-techniques-summary-quickref"
category: "packing"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, "Detect It Easy"]
keywords: ["안티디버깅", "안티디버깅 정리", "anti-debugging", "anti-debugging summary", "ptrace", "IsDebuggerPresent", "RDTSC", "CPUID", "예외 기반 안티디버깅", "안티디버깅 지도"]
aliases: ["안티디버깅 종류 총정리", "안티디버깅 전체 목록", "패킹 안티디버깅 정리", "윈도우 리눅스 안티디버깅 비교"]
symptom_keywords: ["안티디버깅 종류가 헷갈림", "윈도우랑 리눅스 안티디버깅이 다른가", "이 프로그램에 어떤 안티디버깅이 있는지 모르겠음", "디버거 붙이면 바로 죽음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
안티디버깅 기법은 플랫폼과 무관하게 "디버거 존재 여부를 물어본다(API/시스템콜)", "구조체/플래그를 직접 읽는다", "타이밍을 잰다", "예외/VM 여부를 이용한다"의 네 갈래로 나뉘며, 이 문서는 packing 카테고리에 흩어진 개별 안티디버깅 문서(REV-0234~0240)와 Windows 전용 심화 표(REV-0529)를 한 장으로 빠르게 잇는 색인 역할을 한다.

## 언제 검색해야 하나
- Windows와 Linux 바이너리를 오가며 분석하는데, 안티디버깅 기법 이름이 플랫폼마다 달라서 전체 지형이 헷갈릴 때
- 이 packing 카테고리 안에 안티디버깅 관련 글이 여러 개 있는데 어느 글부터 봐야 할지 순서를 잡고 싶을 때
- Linux ELF에서 `ptrace` 기반 기법과 Windows PE에서 `IsDebuggerPresent` 기반 기법이 개념적으로 같은 갈래인지 다른 갈래인지 확인하고 싶을 때
- 디버거를 붙이자마자 프로그램이 종료되는데, 정확히 어떤 종류의 검사인지부터 분류하고 싶을 때

## 핵심 개념
Windows와 Linux는 API/시스템콜 이름이 다르지만, 안티디버깅이 "디버거의 존재가 프로세스에 남기는 흔적"을 이용한다는 원리 자체는 같다. 아래 표는 같은 원리를 플랫폼별로 어떻게 구현하는지 짝지어 정리한 것이다.

| 분류 | 원리 | Windows 대표 예 | Linux 대표 예 |
|---|---|---|---|
| 직접 질의(자기 자신이 디버깅되는지 물어봄) | 커널/런타임에 상태를 물어보는 API 또는 시스템콜 호출 | `IsDebuggerPresent` (REV-0130, windows-pe) | `ptrace(PTRACE_TRACEME, ...)`가 실패하면 이미 디버거가 붙어있다는 뜻 (REV-0234) |
| 구조체/플래그 직접 읽기 | 커널이 관리하는 프로세스 메타데이터를 직접 열람 | PEB의 `BeingDebugged` 필드 직접 읽기 (REV-0236) | `/proc/self/status`의 `TracerPid` 필드 확인 |
| 타이밍 측정 | 디버깅 중 명령어 실행이 비정상적으로 느려지는 것을 이용 | `RDTSC`/`QueryPerformanceCounter` (REV-0237) | `RDTSC` 또는 `clock_gettime` 두 지점 비교(원리는 Windows와 동일) |
| 예외/VM 이용 | CPU 예외 처리 방식 또는 가상화 환경 여부 확인 | SEH 기반 트릭, 하드웨어 브레이크포인트 검사 (REV-0239) | 시그널(`SIGTRAP`) 처리 방식 차이, `CPUID` 기반 VM 탐지 (REV-0238) |

## 화면/코드에서 보이는 징후
- Windows: Import Table에 `IsDebuggerPresent`, `NtQueryInformationProcess` 등이 보이거나, `rdtsc`/PEB 직접 접근 코드가 있음.
- Linux: 프로그램 시작부에 `ptrace(PTRACE_TRACEME, 0, NULL, NULL)` 호출이 있고 반환값을 검사하는 분기가 있음(REV-0234), 또는 `/proc/self/status`를 열어 읽는 코드가 있음.
- 두 플랫폼 공통: `RDTSC`/`CPUID` 명령어가 반복 등장하고 그 결과를 비교/분기하는 코드가 있음.

## 가장 먼저 할 것
분석 중인 바이너리가 PE인지 ELF인지부터 확인한다(`file` 명령 또는 확장자). PE라면 REV-0529(Windows 전용 4분류 심화 표)로 바로 이동해 세부 API를 확인하고, ELF라면 REV-0234(ptrace)부터 확인한다. 두 경우 모두 이 문서의 표로 "어느 분류에 속하는 코드인지"만 먼저 분류한 뒤 세부 문서로 이동하는 순서를 권장한다.

## 단계별 절차
**1) 파일 포맷 확인**: `file sample`로 PE/ELF를 구분한다.
**2) 분류표와 대조**: 위 표에서 어느 분류에 해당하는 흔적(API 이름, 시스템콜, 명령어)이 보이는지 확인한다.
**3) 세부 문서로 이동**: Windows는 REV-0529, Linux는 REV-0234/0237/0238/0239 중 해당 문서로 이동해 상세 내용을 확인한다.
**4) 조합 여부 확인**: 한 가지 기법을 우회했다고 끝내지 말고 다른 분류의 흔적도 함께 훑는다.
**5) 디버거가 갑자기 종료되는 증상이면**: REV-0240 체크리스트로 바로 이동해 원인을 좁힌다.

## 명령어/단축키
- Linux: `cat /proc/self/status | grep TracerPid`(직접 확인), `strace -f -e trace=ptrace ./sample`(ptrace 호출 관찰)
- Windows: x64dbg 우클릭 → `Search for` → `All Modules` → `Intermodular calls`
- 공통: `objdump -d`/IDA 디스어셈블리에서 `rdtsc`, `cpuid` 텍스트 검색

## 출력 해석
- `strace`에서 `ptrace(PTRACE_TRACEME, ...) = -1 EPERM`이 보이면, 이미 다른 디버거(strace 자체 포함 여부는 상황에 따라 다름)가 프로세스를 추적 중이라 실패한 것 — 안티디버깅 분기가 이 실패를 감지하도록 설계되어 있을 가능성이 높다.
- `/proc/self/status`의 `TracerPid`가 0이 아니면 현재 이 프로세스를 추적 중인 디버거 PID가 존재한다는 뜻이며, 프로그램이 이 값을 읽어 0인지 비교하는 코드가 있다면 그것이 바로 안티디버깅 분기다.

## 흔한 실수
- Windows 안티디버깅 지식만 알고 있어서 Linux ELF 문제에서 `ptrace` 기반 검사를 못 알아보는 것 — 원리가 같은 갈래(직접 질의)임을 인지하면 훨씬 빨리 파악된다.
- 하나의 분류만 우회하고 나머지 분류의 코드가 남아있는 것을 놓치는 것.
- 이 문서에서 우회 방법의 세부 절차까지 다 나올 것이라 기대하는 것 — 이 문서는 분류/색인용이며, 실제 우회 개념은 각 REV 문서(REV-0234~0240, REV-0529)에서 다룬다.

## 막혔을 때 다음 체크
- Windows API 기반 세부 분류가 더 필요하면 → REV-0529 Windows 안티디버깅 기법 종류 빠른 참조표.
- Linux `ptrace` 기반 기법 자체가 궁금하면 → REV-0234 ptrace PTRACE_TRACEME 안티디버깅.
- 타이밍 기반 기법이 궁금하면 → REV-0237 RDTSC Time Check 안티디버깅.
- 디버거가 실행 즉시 죽는 증상이면 → REV-0240 디버거에서 갑자기 종료될 때 체크리스트.

## 미니 예제
```c
/* Linux ELF: 직접 질의 분류 예시 */
#include <sys/ptrace.h>
int main(void) {
    if (ptrace(PTRACE_TRACEME, 0, NULL, NULL) == -1) {
        /* 이미 디버거가 붙어있음 -> 비정상 종료 */
        return 1;
    }
    /* 정상 로직 계속 */
    return 0;
}
```
```asm
; Windows PE: 직접 질의 분류 예시
call IsDebuggerPresent
test eax, eax
jnz  debugger_detected
```
두 코드는 API/시스템콜 이름은 다르지만 "커널에게 내가 추적당하는지 직접 물어본다"는 같은 분류(직접 질의)에 속한다.

## 관련 글
- REV-0234 — ptrace PTRACE_TRACEME 안티디버깅
- REV-0237 — RDTSC Time Check 안티디버깅
- REV-0238 — CPUID 기반 VM 탐지 기초
- REV-0239 — Exception 기반 안티디버깅 기초
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트
- REV-0529 — Windows 안티디버깅 기법 종류 빠른 참조표

## 출처/검증
- Windows/Linux 안티디버깅 기법의 4분류 체계는 Microsoft 공식 API 문서, `ptrace(2)` man 페이지, 그리고 CTF/리버싱 커뮤니티에서 공통적으로 통용되는 안티디버깅 분류 방식을 종합한 것이다(2026-09-09 검증).
- `/proc/self/status`의 `TracerPid` 필드는 Linux `proc(5)` man 페이지에 정의된 표준 필드다.
- 개별 API/시스템콜의 정확한 시그니처와 동작은 각 하위 문서(REV-0234, REV-0237~0240, REV-0529)에서 별도로 검증되어 있다.
