---
id: REV-0834
title: "API 호출 순서만으로 프로그램 동작을 재구성하는 법"
slug: "rev-0834-reconstruct-behavior-from-api-order"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords: ["API 호출 순서 분석", "strace ltrace 활용", "x64dbg API 브레이크포인트", "행위 기반 분석", "시스템콜 순서 재구성", "API 시퀀스 추론"]
aliases: ["API 콜 시퀀스 분석", "행동 기반 리버싱", "API 트레이스로 동작 파악", "시스템콜 순서로 로직 재구성"]
symptom_keywords: ["디스어셈블리를 다 안 읽고도 프로그램이 뭘 하는지 알고 싶음", "어떤 API를 어떤 순서로 호출하는지만 보고 싶음", "strace/ltrace 결과를 어떻게 해석해야 할지 모르겠음", "여러 API 호출의 조합으로 상위 동작을 추측하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
디스어셈블리를 명령어 단위로 전부 읽는 대신, 프로그램이 호출하는 API(Windows API 또는 Linux 시스템 콜)의 이름과 순서만 `strace`/`ltrace`나 x64dbg의 다중 API 브레이크포인트로 기록하면, "파일을 열고 → 읽고 → 복호화 함수를 부르고 → 다시 쓴다"처럼 프로그램의 상위 수준 동작을 훨씬 빠르게 재구성할 수 있다.

## 언제 검색해야 하나
- 바이너리가 크고 복잡해서 명령어 단위 분석보다 먼저 "이 프로그램이 대략 뭘 하는 프로그램인지" 큰 그림부터 잡고 싶을 때
- 특정 동작(파일 암호화, 네트워크 통신, 레지스트리 조작)이 있는지 없는지부터 빠르게 확인하고 싶을 때
- REV-0829(블랙박스 입출력 관찰)보다 한 단계 더 깊이, 내부에서 어떤 시스템 자원을 건드리는지까지 보고 싶지만 모든 명령어를 다 읽고 싶지는 않을 때
- 여러 스레드가 API를 호출하는 순서가 뒤섞여서(REV-0617) 어떤 흐름이 어떤 작업에 해당하는지 정리하고 싶을 때

## 핵심 개념

### 명령어 단위 대신 "행위 단위"로 프로그램을 본다
개별 어셈블리 명령어(`mov`, `add`, `cmp`)는 그 자체로는 어떤 목적을 위한 것인지 알기 어렵다. 반면 `CreateFileW` → `ReadFile` → `CryptDecrypt` → `WriteFile`처럼 API 호출의 나열은 곧바로 "파일을 읽어서 복호화한 뒤 다시 쓴다"는 의미로 해석된다. API는 이미 이름 자체가 그 기능을 설명하기 때문에, API 호출 순서만 모아도 프로그램의 의도를 상당 부분 재구성할 수 있다.

### Linux — strace/ltrace로 손쉽게 얻기
- `strace`는 커널에 요청하는 시스템 콜(`open`, `read`, `write`, `mmap`, `execve` 등)을 순서대로 출력한다. `strace -f ./chall`처럼 `-f`를 붙이면 `fork`로 생긴 자식 프로세스의 호출까지 함께 추적한다.
- `ltrace`는 그보다 더 상위 수준인 라이브러리 함수 호출(`malloc`, `strcpy`, `fopen` 등)을 추적한다. 정적 링킹된 바이너리에서는 `ltrace`가 라이브러리 호출을 제대로 못 잡을 수 있으니 이 경우 `strace`나 디버거의 함수 브레이크포인트로 대체한다.

### Windows — x64dbg 다중 API 브레이크포인트 또는 Process Monitor
- x64dbg에서 관심 있는 API 여러 개(`bp CreateFileW`, `bp ReadFile`, `bp CryptDecrypt`, `bp WriteFile`)에 로그 브레이크포인트(REV-0828 방식, Break condition 0, Log condition 1)를 걸어두면 실행을 멈추지 않고 호출 순서가 Log 탭에 그대로 남는다.
- Sysinternals **Process Monitor**는 디버거 없이도 파일/레지스트리/프로세스/네트워크 API 호출을 시간 순서로 GUI에서 보여주며, 필터를 걸어 원하는 프로세스의 활동만 추릴 수 있어 큰 그림을 잡을 때 특히 편리하다.

### 순서가 의미를 만든다
같은 API라도 호출 순서가 다르면 의미가 달라진다. 예를 들어 `CreateFileW`(쓰기 모드) 다음 바로 `WriteFile`이 오면 "새 파일 생성 후 기록"이지만, `CreateFileW`(읽기 모드) → `ReadFile` → `CreateFileW`(쓰기 모드) → `WriteFile` 순서라면 "원본을 읽어서 가공한 뒤 다른 파일에 쓰기"라는 패턴으로 해석된다. 이처럼 API 이름 하나하나보다 그 앞뒤 관계(시퀀스)가 더 많은 정보를 준다.

### 멀티스레드 환경에서는 순서가 스레드별로 뒤섞일 수 있음
REV-0617에서 다뤘듯 멀티스레드 프로그램은 여러 스레드가 동시에 API를 호출해 로그상 순서가 실행마다 달라 보일 수 있다. 이 경우 REV-0824의 스레드별 필터를 함께 적용하거나, 로그에 TID를 같이 남겨(`strace -f`는 기본적으로 PID를 함께 출력) 스레드별로 순서를 재정렬해서 봐야 한다.

## 화면/코드에서 보이는 징후
- 바이너리가 너무 커서(수 MB 이상) 디컴파일 결과를 처음부터 끝까지 읽는 게 비현실적으로 느껴짐
- Import 목록(REV-0101)에 `CryptEncrypt`, `InternetOpenUrlA`, `RegSetValueExW` 같은 눈에 띄는 API 이름이 보여서 이것들의 호출 순서만 먼저 확인하고 싶어짐
- `strace ./chall` 실행 결과가 수백 줄 나오는데, 그 중 `open`, `connect`, `write` 같은 핵심 계열만 골라보고 싶음

## 가장 먼저 할 것
Import 목록이나 문자열에서 눈에 띄는 API(파일, 네트워크, 암호화, 레지스트리 관련)를 먼저 추려낸다. 그 API들만 대상으로 `strace`의 `-e trace=` 옵션이나 x64dbg의 다중 로그 브레이크포인트를 걸어, 전체 명령어가 아니라 그 API들의 호출 순서만 뽑아본다.

## 단계별 절차
1. Import/문자열에서 관심 API 목록 추리기(파일 I/O, 네트워크, 암호화, 레지스트리 등)
2. Linux는 `strace -f -e trace=<카테고리> ./chall`로 해당 카테고리 시스템 콜만 필터링해 실행
3. Windows는 x64dbg에서 관심 API마다 `bp API이름` + Log condition 로그 브레이크포인트 설정
4. 프로그램을 정상적으로 한 번 실행해 호출 순서 전체를 로그로 확보(REV-0830으로 파일 저장)
5. 로그를 순서대로 읽으며 "이 API 다음에 이 API가 왔다"는 인접 관계를 하나씩 표시
6. 인접한 API 조합이 익숙한 패턴(파일 읽기+쓰기, 소켓 연결+송수신, 레지스트리 조회+수정)인지 확인
7. 패턴이 애매한 구간만 그 부분의 디스어셈블리를 REV-0175/0176 방식으로 자세히 들여다봄(전체를 다 볼 필요는 없음)

## 명령어/단축키
Linux:
```bash
strace -f ./chall
strace -f -e trace=file,network ./chall
ltrace ./chall
```
x64dbg(Windows):
```
bp CreateFileW
bp ReadFile
bp WriteFile
bp CryptDecrypt
(각 브레이크포인트 Edit → Break condition 0, Log condition 1)
```
Windows(Process Monitor):
```
Filter → Process Name is chall.exe → Include
Operation 컬럼으로 시간순 API 호출 확인
```

## 출력 해석
- `strace` 출력의 각 줄은 `시스템콜이름(인자...) = 반환값` 형식이다. 예를 들어 `openat(AT_FDCWD, "secret.dat", O_RDONLY) = 3`은 `secret.dat`를 읽기 모드로 열어 파일 디스크립터 3을 받았다는 뜻이며, 이후 `read(3, ...)`가 나오면 그 파일을 읽는 것으로 이어진다.
- x64dbg Log 탭에 쌓인 API 이름들의 순서를 위에서부터 아래로 읽으면 그것이 곧 실제 실행 순서다. 같은 API가 여러 번 반복되면(예: `ReadFile`이 여러 번) 파일을 여러 청크로 나눠 읽는 루프일 가능성이 있다.
- Process Monitor의 Result 컬럼에 `SUCCESS`가 아닌 값(`NAME NOT FOUND`, `ACCESS DENIED`)이 보이면, 그 API 호출이 실패했고 프로그램이 실패 처리 분기로 갔을 가능성을 염두에 둬야 한다.

## 흔한 실수
- API 이름만 보고 순서(인접 관계)는 신경 쓰지 않아서, 실제로는 서로 관련 없는 두 API를 하나의 흐름으로 잘못 엮어 해석하는 것
- 멀티스레드 프로그램의 로그를 스레드 구분 없이 하나로 뒤섞어 읽어서, 실제로는 별개의 두 작업이 동시에 진행 중인데 하나의 순차 흐름으로 착각하는 것(REV-0617, REV-0824 참고)
- `strace`/`ltrace`가 붙으면 실행 속도가 크게 느려지거나 일부 안티디버깅에 걸릴 수 있다는 점을 감안하지 않고 결과가 이상하다고 오해하는 것
- API 호출 순서만으로 전체를 이해했다고 확신하고, 실제 로직(예: 복호화 알고리즘의 세부 계산)까지 API 이름만으로 알 수 있다고 과신하는 것 — 순서는 큰 그림이고, 세부 알고리즘은 여전히 정적/동적 분석이 필요함

## 막혔을 때 다음 체크
- 시스템 콜 하나하나의 힌트를 더 자세히 보고 싶다면 → REV-0112 strace로 시스템 콜에서 힌트 찾기
- 멀티스레드라서 API 순서가 실행마다 달라 보이는 문제는 → REV-0617 실행마다 API 호출 순서가 달라 보일 때(멀티스레드)
- 특정 API 호출 이후 x64dbg가 멈춘 것처럼 보이는 문제는 → REV-0618 특정 API 호출 이후 x64dbg가 응답이 없을 때
- 이렇게 얻은 로그를 파일로 남겨 나중에 분석하려면 → REV-0830 디버거 로그를 파일로 남겨서 나중에 분석하는 법
- 완전히 블랙박스로(API조차 못 보고) 접근해야 하는 상황이면 → REV-0829 블랙박스 방식으로 입력-출력 관계만 파악하는 전략

## 미니 예제
```bash
$ strace -f ./chall secret.dat 2>&1 | grep -E "open|read|write"
openat(AT_FDCWD, "secret.dat", O_RDONLY) = 3
read(3, "\x1f\x8b\x08\x00...", 4096) = 128
openat(AT_FDCWD, "secret.dat.out", O_WRONLY|O_CREAT, 0644) = 4
write(4, "PK\x03\x04...", 96)          = 96
```
`open(읽기)` → `read` → `open(쓰기)` → `write` 순서만으로도 "입력 파일을 읽어서 가공한 뒤 다른 파일에 쓰는 프로그램"이라는 상위 동작을 디스어셈블리를 한 줄도 안 읽고 파악할 수 있었다. 이후 `read`로 읽은 원본과 `write`로 쓴 결과를 비교하면 가공 방식(압축, 암호화 등)의 실마리도 얻을 수 있다.

## 관련 글
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0617 — 실행마다 API 호출 순서가 달라 보일 때(멀티스레드)
- REV-0618 — 특정 API 호출 이후 x64dbg가 응답이 없을 때
- REV-0830 — 디버거 로그를 파일로 남겨서 나중에 분석하는 법
- REV-0829 — 블랙박스 방식으로 입력-출력 관계만 파악하는 전략
- REV-0824 — 멀티스레드 프로그램에서 특정 스레드만 멈추는 법

## 출처/검증
- `strace`/`ltrace`의 시스템 콜/라이브러리 호출 추적 방식과 `-e trace=` 필터 옵션: strace(1), ltrace(1) 공식 매뉴얼 페이지 기준.
- Sysinternals Process Monitor의 필터링 및 Operation 컬럼: Microsoft Sysinternals 공식 문서 기준.
- x64dbg 다중 로그 브레이크포인트를 이용한 API 시퀀스 기록: x64dbg 공식 GitHub Wiki 문서 및 저자 실습 확인 (2026-09-09 검증).
