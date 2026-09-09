---
id: REV-0369
title: "자료형 크기 치트시트: char short int long long long pointer"
slug: "rev-0369-data-type-size-cheatsheet"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["자료형 크기", "data type size", "sizeof", "char short int long", "포인터 크기", "LP64 LLP64"]
aliases: ["int가 몇바이트임", "long 크기가 왜 다름", "포인터 크기 8바이트 4바이트", "sizeof 치트시트"]
symptom_keywords: ["long 크기가 리눅스랑 윈도우에서 다름", "int가 몇바이트인지 헷갈림", "포인터 크기가 4인지 8인지 모르겠음", "sizeof 결과가 예상과 다름"]
source_ids: ["SRC-SYSV-ABI", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
C 기본 자료형의 바이트 크기는 아키텍처(x86/x64)와 플랫폼(Windows/Linux)에 따라 달라지며, 특히 `long`은 Windows x64(LLP64)에서 4바이트지만 Linux x64(LP64)에서는 8바이트라는 차이가 리버싱 중 스택/구조체 오프셋 계산을 틀리게 만드는 가장 흔한 원인이다.

## 언제 검색해야 하나
- 디스어셈블리에서 변수 하나가 몇 바이트를 차지하는지 보고 원래 C 타입이 `int`인지 `long`인지 `long long`인지 추측해야 할 때
- 같은 소스코드를 Windows와 Linux에서 각각 컴파일했는데 구조체 크기나 오프셋이 다르게 나와서 당황했을 때
- 포인터 크기가 4바이트인지 8바이트인지 헷갈려서 구조체 멤버 오프셋 계산이 안 맞을 때
- IDA/Ghidra가 변수 타입을 `__int64`, `unsigned int`처럼 표시하는데 이게 C의 어떤 표준 타입에 대응하는지 확인하고 싶을 때

## 핵심 개념
C 표준은 각 정수 타입의 "최소 보장 크기"만 정의하고, 실제 크기는 컴파일러와 플랫폼의 **데이터 모델(data model)**이 결정한다. 리버싱에서 실제로 마주치는 것은 크게 두 모델이다: Linux/macOS 64비트에서 쓰는 **LP64**(Long, Pointer가 64비트)와 Windows 64비트에서 쓰는 **LLP64**(Long Long, Pointer만 64비트, `long`은 그대로 32비트). 이 차이 때문에 같은 `long`이라는 이름의 변수가 플랫폼에 따라 4바이트일 수도, 8바이트일 수도 있다.

### 자료형별 바이트 크기 (x86 / x64, Windows / Linux)

| C 타입 | x86 (32비트, 공통) | x64 Linux (LP64) | x64 Windows (LLP64) |
|---|---|---|---|
| `char` | 1 | 1 | 1 |
| `short` | 2 | 2 | 2 |
| `int` | 4 | 4 | 4 |
| `long` | 4 | **8** | **4** |
| `long long` | 8 | 8 | 8 |
| `float` | 4 | 4 | 4 |
| `double` | 8 | 8 | 8 |
| `long double` | 12 (x86 관습상, 실제 유효비트 80비트) | 16 (Linux x64 관습) | 8 (Windows에서는 `double`과 동일 취급) |
| 포인터(`void*`, `int*` 등) | 4 | **8** | **8** |
| `size_t` | 4 | 8 | 8 |
| `wchar_t` | 4 (Linux) / 2 (Windows) | 4 (Linux) | 2 (Windows) |

### 왜 이 표를 외워야 하는가
- **포인터 크기**는 아키텍처가 x86인지 x64인지만으로 결정된다(4바이트 vs 8바이트) — 플랫폼(Windows/Linux)과는 무관하다.
- **`long`의 크기**는 반대로 아키텍처가 아니라 **플랫폼(OS/컴파일러)**이 결정한다 — 같은 x64라도 Windows는 4바이트, Linux는 8바이트다. 이 표에서 유일하게 "아키텍처가 아니라 플랫폼에 좌우되는" 항목이라 가장 자주 실수가 나온다.
- `wchar_t`도 플랫폼마다 크기가 다르다(Windows 2바이트=UTF-16 코드유닛, Linux 4바이트=UTF-32) — 문자열 리버싱(REV-0036)에서 자주 헷갈리는 부분이다.

### IDA/Ghidra 타입 표시와의 대응
IDA는 플랫폼에 덜 의존적인 고정 크기 이름을 즐겨 쓴다.

| IDA/Ghidra 표시 | 실제 크기 | 대응 C 타입(대략) |
|---|---|---|
| `_BYTE` / `unsigned __int8` | 1 | `unsigned char` |
| `__int16` | 2 | `short` |
| `__int32` / `int` | 4 | `int` |
| `__int64` | 8 | `long long` (Windows), `long` (Linux x64) |
| `_QWORD` | 8 | 포인터 또는 64비트 정수 |
| `_DWORD` | 4 | 포인터(x86) 또는 32비트 정수 |

## 화면/코드에서 보이는 징후
- 스택 변수 선언에서 `sub rsp, N` 이후 `[rbp-8]`, `[rbp-4]` 등 오프셋 간격이 4 또는 8 단위로 나뉘는 경우 — 각각 4바이트 타입(`int`), 8바이트 타입(포인터/`long long`/Linux `long`) 변수일 가능성
- Windows x64 바이너리인데 `long` 타입 변수가 4바이트(`mov dword ptr`)로 처리되는 경우 — LLP64 정상 동작
- Linux x64 바이너리에서 `long` 타입이 8바이트(`mov qword ptr`)로 처리되는 경우 — LP64 정상 동작

## 가장 먼저 할 것
분석 대상 바이너리의 플랫폼(PE인지 ELF인지)과 아키텍처(x86/x64)를 먼저 확정한다. 그 다음 이 표에서 해당 열만 골라 참고하면 된다 — 특히 `long`과 포인터는 반드시 플랫폼/아키텍처를 확인한 후 크기를 판단해야 한다.

## 단계별 절차
1. 바이너리가 PE(Windows)인지 ELF(Linux)인지 확인한다.
2. `file` 명령이나 IDA/Ghidra 아키텍처 표시로 x86인지 x64인지 확인한다.
3. 위 표에서 해당 플랫폼·아키텍처 열을 찾아 `long`과 포인터 크기부터 확정한다(가장 실수가 잦은 두 항목).
4. 문제가 되는 변수의 스택/구조체 오프셋 간격(4바이트 단위인지 8바이트 단위인지)을 실제 디스어셈블리에서 확인해, 추정한 타입 크기와 일치하는지 검증한다.
5. 확신이 안 서면 같은 플랫폼에서 `sizeof()`를 직접 찍어보는 짧은 C 코드로 교차검증한다.

## 명령어/단축키
```c
// 실제 환경에서 직접 검증하는 가장 확실한 방법
#include <stdio.h>
int main() {
    printf("%zu %zu %zu %zu %zu\n",
        sizeof(char), sizeof(short), sizeof(int),
        sizeof(long), sizeof(void*));
}
```
```python
import struct
struct.calcsize("i")   # int 크기 (플랫폼 기본 정렬 기준)
struct.calcsize("l")   # long 크기 (플랫폼에 따라 다름, Windows 파이썬도 4)
struct.calcsize("q")   # long long / 64비트 고정
struct.calcsize("P")   # 포인터 크기 (빌드 아키텍처 기준)
```

## 출력 해석
- `sizeof(long)`이 4로 나오면 Windows 빌드이거나 32비트 빌드다.
- `sizeof(long)`이 8로 나오면 Linux/macOS 64비트 빌드다.
- `sizeof(void*)`가 4면 x86, 8이면 x64로 아키텍처를 바로 판단할 수 있다.

## 흔한 실수
- `long`은 어디서나 4바이트일 거라고 가정하는 것 — Linux x64에서는 8바이트다.
- 포인터 크기를 플랫폼(Windows/Linux) 차이로 착각하는 것 — 포인터 크기는 아키텍처(x86/x64)에만 좌우된다.
- `wchar_t`를 항상 2바이트로 가정해 Linux 문자열을 잘못 디코딩하는 것 — Linux의 `wchar_t`는 4바이트(UTF-32)다.
- IDA의 `__int64`를 무조건 `long long`으로 단정하는 것 — 실제 원본 소스에서는 플랫폼에 따라 `long`이었을 수도 있다(의미상 차이는 크지 않지만 이식성 코드 분석 시 혼동 요인).

## 막혔을 때 다음 체크
- 정수 타입별 최대/최소값이 필요하면 → REV-0370 정수 자료형 최대/최소값 치트시트
- 이 크기 차이가 실제 구조체 오프셋 계산에 어떻게 반영되는지 감이 안 잡히면 → REV-0035 구조체 접근이 어셈블리로 변하는 방식
- 문자열 인코딩(ASCII/UTF-8/UTF-16)과 `wchar_t` 크기 차이가 헷갈리면 → REV-0036 문자열이 메모리에 저장되는 방식 ASCII UTF-8 UTF-16

## 미니 예제
같은 구조체가 플랫폼에 따라 크기가 달라지는 예:
```c
struct Example {
    char  a;     // 1바이트
    long  b;     // Linux x64: 8바이트 / Windows x64: 4바이트
    void* p;     // x64: 8바이트 (공통)
};
```
Linux x64에서는 `long`이 8바이트라 정렬 패딩까지 고려하면 `sizeof(struct Example)`이 24가 되기 쉽지만, Windows x64에서는 `long`이 4바이트라 같은 구조체가 16이 될 수 있다. 크로스 플랫폼 코드나 문제 파일을 다른 OS에서 재현하려 할 때 이 차이를 놓치면 구조체 오프셋 전체가 틀어진다.

## 관련 글
- REV-0370 — 정수 자료형 최대/최소값 치트시트
- REV-0035 — 구조체 접근이 어셈블리로 변하는 방식
- REV-0036 — 문자열이 메모리에 저장되는 방식 ASCII UTF-8 UTF-16

## 출처/검증
- LP64/LLP64 데이터 모델 정의 및 각 타입 크기: System V AMD64 ABI 문서(Linux/Unix 계열), Microsoft 공식 문서(Data Type Ranges, MSVC) 기준 (2026-09-09 검증).
- C 표준 정수 타입 최소 크기 보장: ISO/IEC 9899(C 표준) 기준.
