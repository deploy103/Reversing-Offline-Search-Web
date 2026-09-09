---
id: REV-0861
title: "32비트 디버거로 64비트 프로세스를 못 열 때(또는 반대)"
slug: "rev-0861-debugger-bitness-mismatch"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords:
  - x32dbg
  - x64dbg
  - WOW64
  - 32비트 64비트 디버거 불일치
  - could not attach
  - architecture mismatch
symptom_keywords:
  - x32dbg로 여니까 에러가 남
  - 64비트 프로세스인데 안 열림
  - 32비트 바이너리인데 x64dbg로 열림
  - attach 실패 architecture
aliases:
  - 디버거 비트수 안맞음
  - x32dbg x64dbg 헷갈림
  - 32비트 프로세스 attach 실패
  - WOW64 디버거 문제
source_ids: ["SRC-X64DBG-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
x32dbg/x64dbg처럼 32비트·64비트 디버거가 실행 파일 형태로 분리되어 있는 도구는 대상 프로세스의 비트수와 디버거의 비트수가 정확히 일치해야만 정상적으로 열리거나 attach되며, 이를 헷갈리면 "Could not attach"류의 오류나 잘못된 레지스터/스택 해석으로 이어진다.

## 언제 검색해야 하나
- x32dbg로 실행 파일을 열려고 했더니 오류가 뜨거나, 열리긴 했는데 레지스터가 이상하게 보일 때
- 64비트 EXE를 x64dbg 대신 x32dbg로 실수로 열었을 때
- 작업 관리자에서 "\*32"로 표시된 프로세스(WOW64, 즉 64비트 Windows 위에서 도는 32비트 프로세스)에 잘못된 비트수의 디버거로 attach를 시도할 때
- Linux에서 32비트 ELF를 디버깅하려는데 GDB가 아키텍처를 잘못 인식하거나 라이브러리를 못 찾을 때

## 핵심 개념

### x32dbg와 x64dbg는 서로 다른 실행 파일이다
x64dbg 패키지에는 사실 `x32dbg.exe`와 `x64dbg.exe`라는 두 개의 별도 실행 파일이 들어 있다(공용 런처인 `x96dbg.exe`를 통해 열면 대상 파일의 PE 헤더를 보고 자동으로 알맞은 쪽을 실행해준다). `x32dbg.exe`는 32비트 프로세스만, `x64dbg.exe`는 64비트 프로세스만 디버깅할 수 있다. 32비트 EXE를 `x64dbg.exe`로 직접 열려고 하면 대부분 열기 자체를 거부하거나 곧바로 오류를 낸다.

### WOW64란 무엇이고 왜 헷갈리는가
64비트 Windows에서 32비트 프로그램은 WOW64(Windows-on-Windows 64)라는 호환 계층 위에서 실행된다. 작업 관리자에서 이런 프로세스는 이름 뒤에 `*32`가 붙어 표시된다. 겉보기엔 64비트 OS 위에서 도는 프로세스라 64비트 디버거로 붙여야 할 것 같지만, 실제 프로세스의 코드/레지스터 문맥은 32비트이므로 `x32dbg.exe`로 붙여야 정상적으로 분석된다. `x64dbg.exe`로 WOW64 프로세스에 attach를 시도하면 잘못 붙거나 스택/레지스터가 뒤섞여 보일 수 있다(REV-0362 WOW64 개념 참고).

### Linux/GDB에서의 32비트-64비트 문제
GDB 자체는 하나의 바이너리로 32비트·64비트 ELF를 모두 인식할 수 있어 Windows만큼 "디버거 자체가 안 열리는" 문제는 잘 없지만, 대신 다음 문제가 흔하다.
- 32비트 바이너리를 실행하려는데 필요한 32비트 공유 라이브러리(`libc.so.6` 32비트판 등)가 시스템에 없어서 `run` 자체가 실패한다(REV-0675 multilib 설정 참고).
- 크로스 아키텍처 코어덤프나 원격 타깃을 분석할 때 `set architecture` 명령으로 대상 아키텍처를 명시해줘야 하는 경우가 있다.

### 어떤 비트수인지 미리 확인하는 법
Windows에서는 `file` 계열 도구나 PE-bear, Detect It Easy(DIE)로 대상 EXE의 `Machine` 필드(`IMAGE_FILE_MACHINE_I386` vs `IMAGE_FILE_MACHINE_AMD64`)를 확인하면 되고(REV-0021 x86 vs x64 참고), Linux에서는 `file <바이너리>` 명령으로 `ELF 32-bit`/`ELF 64-bit`를 바로 확인할 수 있다(REV-0095 file 명령 참고).

## 화면/코드에서 보이는 징후
- x32dbg로 64비트 EXE를 열려고 하면 "이 파일을 열 수 없습니다" 류의 오류 또는 아무 반응 없이 로드가 실패한다.
- x64dbg로 32비트 EXE를 attach하면 레지스터 창에 `RAX`/`RBX` 같은 64비트 레지스터만 보이고, 실제 코드 흐름과 스택 값이 맞물리지 않는 것처럼 보인다.
- 작업 관리자의 "세부 정보" 탭에서 대상 프로세스 이름 옆에 `*32`가 붙어 있는데도 64비트 디버거 목록에서 그 프로세스를 attach 대상으로 골라 시도한다.
- Linux에서 `file target`을 안 해보고 그냥 `gdb ./target`을 실행했는데, 라이브러리 로드 오류(`error while loading shared libraries`, REV-0706 참고)가 뜬다.

## 가장 먼저 할 것
1. 대상 파일/프로세스의 비트수를 먼저 확정한다(Windows: PE Machine 필드, Detect It Easy / Linux: `file` 명령).
2. Windows라면 그 비트수에 맞는 실행 파일(`x32dbg.exe` 또는 `x64dbg.exe`)을 직접 골라 실행한다.
3. WOW64 프로세스라면 작업 관리자의 `*32` 표시를 반드시 확인한 뒤 32비트 디버거로 attach한다.

## 단계별 절차

**Windows / x64dbg**
1. 대상 EXE를 Detect It Easy나 PE-bear로 열어 `Machine` 필드를 확인한다(`I386`이면 32비트, `AMD64`이면 64비트).
2. 32비트면 `x32dbg.exe`를, 64비트면 `x64dbg.exe`를 직접 실행한다. 어느 쪽인지 매번 헷갈린다면 `x96dbg.exe`(통합 런처)로 파일을 열어 자동 판별에 맡긴다.
3. 이미 실행 중인 프로세스에 attach하려면, 먼저 작업 관리자에서 그 프로세스가 `*32`인지 확인하고 그에 맞는 디버거를 실행한 뒤 `File` → `Attach`로 목록에서 선택한다.

**Linux / GDB**
1. `file ./target`으로 32비트/64비트를 확인한다.
2. 32비트 바이너리를 64비트 시스템에서 실행해야 한다면, 먼저 multilib 관련 패키지(예: `libc6-i386` 계열)가 설치되어 있는지 확인한다(REV-0675 참고).
3. 크로스 아키텍처 코어덤프 등 특수한 경우에는 `set architecture i386`처럼 명시적으로 아키텍처를 지정한다.

## 명령어/단축키
- Windows: `x32dbg.exe`, `x64dbg.exe`, `x96dbg.exe`(자동 판별 런처), 작업 관리자 "세부 정보" 탭의 `*32` 표시 확인
- Linux: `file <바이너리>`, GDB `set architecture <arch>`, `show architecture`

## 출력 해석
- `file target` 결과에 `ELF 32-bit LSB executable, Intel 80386`이 보이면 32비트, `ELF 64-bit LSB executable, x86-64`면 64비트다.
- Windows 작업 관리자에서 프로세스 이름 뒤에 `*32`가 있으면 해당 프로세스는 32비트이며 WOW64 위에서 실행 중이라는 뜻이다. `*32`가 없으면 네이티브 64비트 프로세스다.

## 흔한 실수
- 파일 확장자나 폴더 이름만 보고 비트수를 추측해서 엉뚱한 디버거로 여는 것 — 반드시 PE Machine 필드나 `file` 명령으로 실제 값을 확인해야 한다.
- WOW64 프로세스를 64비트 디버거로 붙인 뒤, 레지스터/스택이 이상하다고 프로그램이 난독화됐다고 오해하는 것 — 사실은 디버거 비트수가 틀린 것이다.
- x96dbg 런처 없이 항상 `x64dbg.exe`만 써서 32비트 대상은 항상 실패한다고 생각하는 것 — 32비트 대상에는 반드시 `x32dbg.exe`가 필요하다.

## 막혔을 때 다음 체크
- attach 자체가 안 된다면 → 관리자 권한으로 디버거를 실행했는지도 함께 확인한다(권한 부족도 attach 실패의 흔한 원인).
- 정적 분석 도구(IDA/Ghidra)에서도 비슷하게 비트수를 잘못 골라 로드했다면 → REV-0803(32비트/64비트를 헷갈려서 잘못 로드했을 때)을 참고한다.
- Linux에서 32비트 실행 자체가 안 된다면 → REV-0675(x86 32비트 multilib 설정)를 먼저 따라간다.

## 미니 예제
```text
작업 관리자 → 세부 정보 탭
chall.exe   *32   ...
```
이 표시를 보고 `x32dbg.exe`를 실행 → `File` → `Attach` → `chall.exe (*32)` 선택 → 정상적으로 EIP/EAX 등 32비트 레지스터 컨텍스트로 붙는다. 반대로 `x64dbg.exe`로 같은 프로세스를 attach 목록에서 찾으면 아예 목록에 안 뜨거나 잘못된 상태로 붙는다.

## 관련 글
- REV-0859 — Just-In-Time 디버거 팝업이 떠서 당황스러울 때
- REV-0803 — 32비트/64비트를 헷갈려서 잘못 로드했을 때
- REV-0021 — x86와 x64를 구분하는 법

## 출처/검증
- x32dbg/x64dbg 분리 실행 구조와 x96dbg 런처 동작: x64dbg 공식 문서(Introduction) 기준.
- WOW64와 `*32` 표시: Microsoft Learn "WOW64 Implementation Details" 문서 기준.
- GDB `set architecture` 명령: GNU GDB 공식 매뉴얼 "Specifying a Debugging Target" 섹션 기준.
- 2026-09-09 검증.
