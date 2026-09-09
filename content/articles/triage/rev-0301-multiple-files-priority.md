---
id: REV-0301
title: "문제 파일이 여러 개일 때 우선순위 정하는 법"
slug: "rev-0301-multiple-files-priority"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [file, IDA, Ghidra, x64dbg, GDB]
keywords: [여러 파일 우선순위, 분석 순서 정하기, 다중 바이너리 문제, 어떤 파일부터 볼지, 문제 파일 여러 개]
aliases: ["파일이 여러 개인데 뭐부터", "여러 바이너리 우선순위", "분석 순서 못 정함", "어떤 exe부터 열지"]
symptom_keywords: ["첨부파일이 여러 개라 뭐부터 봐야 할지 모르겠음", "실행파일이 여러 개인데 하나만 열어봐서 놓침", "DLL이랑 exe가 같이 있는데 어디부터", "메인 바이너리가 어떤 건지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
문제 파일이 여러 개일 때는 무작정 첫 번째 파일부터 열지 말고, **파일 크기·이름·형식·상호 참조 관계**로 "메인 실행 흐름"과 "보조 자료"를 먼저 구분한 뒤, 메인 흐름을 결정하는 파일부터 우선순위를 매겨 분석한다.

## 언제 검색해야 하나
- 압축을 풀었더니 `.exe` 여러 개, 또는 `.exe`와 `.dll` 여러 개, 또는 `main`과 `sub1`, `sub2` 같은 파일이 같이 있을 때
- 어떤 파일을 먼저 열어야 할지 감이 안 잡혀서 아무거나 열었다가 시간을 허비했을 때
- 파일 하나를 다 분석했는데 알고 보니 진짜 로직은 다른 파일에 있었다는 걸 뒤늦게 알았을 때

## 핵심 개념
CTF/워게임 첨부파일에 실행 가능한 바이너리가 두 개 이상 있는 경우는 크게 세 가지 패턴으로 나뉜다.

1. **메인 + 보조 라이브러리**: `chall.exe` + `custom.dll`, 또는 `chall` + `libcustom.so`처럼 메인 실행파일이 자체 제작 라이브러리를 불러오는 구조. 이때 실제 검증 로직은 라이브러리 쪽에 있는 경우가 많다.
2. **다단계 실행(프로세스 체인)**: `launcher.exe`가 `payload.exe`를 실행(`CreateProcess`)하거나, 부모 프로세스가 자식 프로세스를 `fork`/`exec`하는 구조. 이 경우 launcher는 안티디버깅이나 환경 체크만 하고, 진짜 로직은 다음 단계 파일에 있는 일이 흔하다.
3. **독립적인 다중 문제(멀티 파트)**: 실제로는 서로 관련 없는 여러 개의 작은 문제가 zip 하나에 묶여 있는 경우. 문제 설명에 "Part 1", "Part 2"처럼 구분되어 있으면 이 경우다.

우선순위를 정하는 원칙은 "**제어 흐름의 출발점을 찾는다**"이다. 즉 어떤 파일이 먼저 실행되고, 어떤 파일이 실제로 flag 검증을 담당하는지를 먼저 판별한 다음, 검증 로직이 있는 파일에 분석 시간을 집중한다. 파일 크기가 크다고 무조건 메인은 아니다 — 언어 런타임(Go, .NET, 정적 링크된 C)이 포함되면 단순 파일이라도 수 MB가 될 수 있다.

## 화면/코드에서 보이는 징후
- 폴더 안에 실행 가능한 파일이 2개 이상 있고, 파일명이 `chall`, `chall_helper`, `lib.so`처럼 역할이 암시된다.
- `file` 명령으로 확인했더니 하나는 `PE32+ executable`, 하나는 `PE32+ executable (DLL)`로 서로 다른 타입이다.
- Import 목록을 보니 한 파일에서 다른 파일 이름(`custom.dll`, `libcustom.so`)이 그대로 임포트되어 있다.
- 프로세스를 실행해보니 순식간에 다른 프로세스가 새로 뜨거나(작업 관리자/`ps`에서 확인), 콘솔에 "Loading module..." 같은 메시지가 뜬다.

## 가장 먼저 할 것
모든 파일에 `file`(Linux) 또는 Detect It Easy(Windows)를 돌려서 각 파일의 형식(EXE/DLL/SO/ELF), 아키텍처, 링킹 방식을 한 번에 표로 정리한다. 이 표만으로도 "이건 라이브러리다", "이건 실행 진입점이다"가 대부분 구분된다.

## 단계별 절차

**1) 전체 파일 인벤토리 작성**
```bash
file *
```
출력 예시:
```
chall.exe: PE32+ executable (console) x86-64, for MS Windows
custom.dll: PE32+ executable (DLL) (console) x86-64, for MS Windows
data.bin: data
```
`data.bin`처럼 실행 파일이 아닌 것은 나중에 확인할 "자료"로 분류하고, 실행/라이브러리 파일에 집중한다.

**2) 어떤 파일이 진입점인지 판별**
- 확장자 자체가 `.dll`/`.so`이면 그 파일은 단독 실행이 안 되므로 보조 라이브러리로 확정한다.
- 실행 가능한 파일이 여러 개면 각각을 Import/Dependency 관점에서 확인한다. Windows는 Dependency Walker 대신 PE-bear나 IDA의 Imports 탭으로, Linux는 `ldd ./chall` 또는 `readelf -d ./chall | grep NEEDED`로 확인한다.
- `chall.exe`의 Import 목록에 `custom.dll`이 있으면 `chall.exe`가 진입점이고 `custom.dll`이 보조 라이브러리다.

**3) 라이브러리 쪽에 실제 로직이 있는지 빠르게 확인**
진입점 파일(`chall.exe`)을 IDA/Ghidra로 열고 `main`에서 `custom.dll`의 함수를 호출하는 부분(Import 함수 호출)을 찾는다. 호출되는 함수 이름이 `Check`, `Verify`, `Encrypt`처럼 의미 있는 이름이면 라이브러리 쪽이 진짜 분석 대상이다. 이 경우 진입점 파일은 가볍게 훑고 라이브러리 파일 분석에 시간을 더 배분한다.

**4) 프로세스 체인(다단계 실행) 여부 확인**
진입점 파일의 Import에 `CreateProcessA/W`(Windows) 또는 `fork`/`execve`(Linux)가 있으면, 그 파일은 다른 실행파일을 새로 띄우는 launcher일 가능성이 높다. 실제로 실행해서 작업 관리자(Windows) 또는 `ps -ef --forest`(Linux)로 자식 프로세스가 뜨는지 확인한다.

**5) 독립적인 멀티 파트 문제인지 확인**
파일들 사이에 Import/Export 연결이 전혀 없고, 각자 독립적으로 실행되며 각자 다른 메시지("Part 1 solved!" 등)를 낸다면 사실상 서로 다른 문제다. 이 경우 우선순위는 문제 배점이나 난이도 표시, 또는 파일 크기가 작아 빨리 끝낼 수 있는 것부터 잡는다.

**6) 우선순위 확정 및 시간 배분**
정찰 결과를 `notes.md`에 "chall.exe = 진입점, custom.dll = 검증 로직 포함, data.bin = 암호화된 자료로 추정"처럼 한 줄씩 정리하고, 검증 로직이 들어있는 파일에 분석 시간의 대부분을 배분한다.

## 명령어/단축키
```bash
file *
ldd ./chall
readelf -d ./chall | grep NEEDED
readelf -d ./custom.so | grep NEEDED
ps -ef --forest
```
Windows: Detect It Easy로 각 파일 드래그해서 형식 확인, PE-bear의 Import Table 탭으로 DLL 의존관계 확인, 작업 관리자 "세부 정보" 탭에서 실행 중 자식 프로세스 확인.
IDA/Ghidra: Imports 창에서 외부 DLL/SO 이름과 함수 이름 목록 확인.

## 출력 해석
- `ldd ./chall` 출력에 `custom.so => not found`가 나오면 그 라이브러리가 같은 폴더에 있어야 실행되는 자체 제작 라이브러리라는 뜻이다. 실행 전에 `LD_LIBRARY_PATH=.`로 같은 폴더를 라이브러리 경로에 추가해야 할 수 있다.
- Import 목록에 있는 함수 이름이 `kernel32.dll`, `libc.so.6`처럼 표준 시스템 라이브러리 함수뿐이면, 첨부된 다른 커스텀 DLL/SO와는 무관한 별개 파일일 가능성이 있다.
- 실행 중 새 프로세스가 뜨는 게 확인되면 그 새 프로세스에도 디버거를 붙여야 하므로(x64dbg의 "Attach", GDB의 `attach <pid>`), 분석 계획에 이 단계를 미리 포함시킨다.

## 흔한 실수
- 파일명이 알파벳 순으로 먼저 나온다는 이유만으로 그 파일부터 분석해서, 정작 검증 로직이 있는 DLL/SO를 뒤늦게 발견하는 것.
- DLL/SO 확장자를 가진 파일을 "그냥 라이브러리니까 안 봐도 된다"고 넘겨서, 실제 검증 로직이 거기 있는데 놓치는 것.
- 여러 파일이 서로 무관한 멀티 파트 문제인데 하나로 묶어서 이해하려다 혼란에 빠지는 것.
- launcher가 자식 프로세스를 띄우는 걸 못 보고, launcher 자체에서만 몇 시간을 분석하는 것.

## 막혔을 때 다음 체크
- 어떤 파일이 진짜 실행 파일인지조차 헷갈린다 → REV-0302 첨부 파일에 여러 바이너리가 섞여 있을 때 분류하는 법
- 문제 설명 자체를 다시 읽어야 할 것 같다 → REV-0012 문제 설명과 첨부파일에서 힌트 뽑는 방법
- 우선순위는 정했는데 그 다음 접근이 막막하다 → REV-0018 대회장에서 리버싱 문제 하나를 끝까지 추적하는 실전 루틴

## 미니 예제
첨부파일: `game.exe`(2MB), `engine.dll`(500KB), `save.dat`(1KB)

1. `file *` → `game.exe`는 PE32+ 콘솔 실행파일, `engine.dll`은 PE32+ DLL, `save.dat`은 데이터.
2. PE-bear로 `game.exe`의 Import Table 확인 → `engine.dll`에서 `CheckSaveFile`, `Encrypt` 함수를 임포트하고 있음을 발견.
3. 즉시 판단: `game.exe`는 UI/진입점, 진짜 검증 로직은 `engine.dll`의 `CheckSaveFile`.
4. 분석 시간의 80%를 `engine.dll`의 `CheckSaveFile` 함수에 배분하고, `game.exe`는 이 함수를 어떤 인자로 호출하는지만 가볍게 확인.
5. `save.dat`은 `CheckSaveFile`이 읽는 입력 파일로 확인되어, 이 파일의 바이트 포맷을 역산 대상으로 확정.

이렇게 5분 안에 "무엇을 얼마나 볼지"를 정하고 시작하면, 3개 파일을 무작위로 오가며 시간을 낭비하는 일을 피할 수 있다.

## 관련 글
- REV-0302 — 첨부 파일에 여러 바이너리가 섞여 있을 때 분류하는 법
- REV-0012 — 문제 설명과 첨부파일에서 힌트 뽑는 방법
- REV-0018 — 대회장에서 리버싱 문제 하나를 끝까지 추적하는 실전 루틴

## 출처/검증
- PE Import Table/DLL 의존관계 분석 방식: Microsoft PE Format 공식 문서 및 PE-bear 공식 문서 기준.
- ELF `DT_NEEDED`/`ldd` 동작 방식: System V ABI 및 GNU `ldd` 매뉴얼 기준.
- 다중 실행파일 CTF 문제 패턴: 다수의 공개 CTF writeup 관행 요약 (2026-09-09 검증).
