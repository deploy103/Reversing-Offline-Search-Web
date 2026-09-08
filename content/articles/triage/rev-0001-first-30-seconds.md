---
id: REV-0001
title: "리버싱 문제 파일을 받았을 때 30초 트리아지"
slug: "rev-0001-first-30-seconds"
category: "triage"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [file, "Detect It Easy", strings, IDA]
keywords: [트리아지, triage, 30초 체크리스트, 첫 분석, 파일 분석 순서]
aliases: ["처음 뭐부터", "뭐부터 해야됨", "파일 받았는데 뭐부터", "리버싱 시작"]
symptom_keywords: ["아무것도 모르겠음", "뭐부터 해야 할지 모르겠음", "문제 파일 받음", "처음 봄"]
source_ids: []
last_verified: "2026-09-08"
---

## 한 줄 요약
문제 파일을 받으면 열기 전에 **file 타입 → 아키텍처 → 문자열 → 임포트 → 보호기법** 순서로 30초 안에 훑어서, 이후 분석 방향(정적/동적, 어떤 도구)을 먼저 정한다.

## 언제 검색해야 하나
- CTF나 워게임에서 처음 보는 실행 파일을 받았고, 뭐부터 눌러야 할지 감이 안 잡힐 때
- 무작정 IDA부터 켜고 스크롤만 하다가 시간을 날리고 있을 때

## 핵심 개념
리버싱은 "무작정 디스어셈블러를 켜고 코드를 읽는 것"이 아니다. 실제로는 **파일 자체가 이미 많은 정보를 갖고 있고**, 그 정보를 먼저 뽑아내면 코드를 읽을 때 어디를 봐야 하는지가 훨씬 명확해진다. 30초 트리아지는 "이 파일이 무엇인지, 어떤 도구로, 어디서부터 봐야 하는지"를 결정하는 사전 정찰 단계다.

핵심은 순서다:
1. **확장자 말고 실제 형식** — `.exe`인데 사실 .NET이거나, 확장자가 없는데 ELF일 수 있다.
2. **아키텍처/비트수** — x86인지 x64인지에 따라 레지스터 이름과 호출 규약이 통째로 바뀐다.
3. **문자열** — "Correct!", "Wrong flag", "Enter password" 같은 문자열이 있으면 검증 로직으로 가는 지도가 생긴다.
4. **임포트 함수 목록** — `scanf`, `strcmp`, `IsDebuggerPresent` 등 이름만 봐도 무엇을 하는 프로그램인지 짐작 가능.
5. **섹션/보호 기법** — 패킹되었는지, 스택 카나리·NX·PIE가 켜져 있는지에 따라 접근 방식이 달라진다.

## 화면/코드에서 보이는 징후
- 파일 아이콘이 EXE인데 실제로는 Mono/.NET일 수도 있음 (아이콘/확장자는 신뢰 불가)
- `strings` 결과에 `mscorlib`, `System.` 같은 문자열이 보이면 .NET
- `readelf -h` 또는 `file` 결과에 `ELF 64-bit LSB`처럼 명확히 표시됨
- IDA/Ghidra가 함수를 거의 못 찾으면 stripped 또는 패킹 의심

## 가장 먼저 할 것
바이너리를 IDA에 던지기 **전에** 터미널(또는 Detect It Easy)에서 파일 타입부터 확인한다. Windows라면 PowerShell + Detect It Easy(DIE), Linux/WSL이라면 `file` 명령을 쓴다.

## 단계별 절차

**1) 파일 형식 확인**

Linux/WSL:
```bash
file ./challenge
```
출력 예시:
```
challenge: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked, ...
```
이 한 줄에 이미 "ELF, 64비트, PIE(주소가 실행마다 바뀜), 동적 링크"라는 정보가 다 들어있다.

Windows: Detect It Easy(DIE)를 실행하고 파일을 드래그 앤 드롭하면 우측 상단에 파일 형식(PE32/PE32+), 컴파일러, 패커 여부가 바로 표시된다.

**2) 문자열 훑기**
```bash
strings -n 6 ./challenge | less
```
`-n 6`은 최소 길이 6 이상인 문자열만 보여줘서 노이즈를 줄인다. `Correct`, `Wrong`, `flag{`, `password` 같은 단어를 찾는다. 찾으면 그 문자열의 주소를 기억해 둔다 (나중에 IDA에서 이 문자열을 참조하는 코드로 바로 점프할 것이다).

**3) 임포트/링크된 함수 확인**

Linux:
```bash
readelf -d ./challenge | grep NEEDED
nm -D ./challenge 2>/dev/null | grep ' U '
```
Windows: PE-bear나 IDA의 Imports 탭에서 확인. `scanf`, `strcmp`, `IsDebuggerPresent`, `ptrace` 같은 이름이 보이면 각각 "입력받음", "비교함", "안티디버깅 있음"이라는 힌트다.

**4) 보호 기법 확인 (Linux)**
```bash
checksec --file=./challenge
```
`Canary`, `NX`, `PIE`, `RELRO` 값이 나온다. 이 단계는 리버싱보다 pwn에 더 중요하지만, PIE가 켜져 있으면 "실행할 때마다 함수 주소가 바뀐다"는 걸 미리 알고 시작해야 GDB에서 당황하지 않는다.

**5) 방향 결정**
- 문자열에 "Enter flag"류가 있고 함수 몇 개면 → 정적 분석(IDA F5)으로 바로 검증 로직을 읽는다.
- 문자열이 거의 안 보이고 섹션 엔트로피가 높으면 → 패킹 의심, 동적 분석(디버거로 실행 후 언패킹된 코드 관찰)부터 고려한다.

## 명령어/단축키
```bash
file ./challenge
strings -n 6 ./challenge
readelf -h ./challenge
readelf -d ./challenge
checksec --file=./challenge
```
Windows에서는 Detect It Easy 실행 → 파일 드롭 → 상단 "File type" / "Compiler" / 하단 스캔 버튼(패커 탐지)을 확인한다.

## 출력 해석
- `file` 결과에 `pie executable`이 있으면 PIE가 켜져 있다는 뜻 (Position Independent Executable). 주소가 매번 바뀐다.
- `readelf -d` 결과에서 `NEEDED libc.so.6` 등은 이 바이너리가 어떤 공유 라이브러리에 의존하는지 보여준다.
- DIE에서 "Packer: UPX"라고 뜨면 언패킹부터 해야 코드가 제대로 보인다.

## 흔한 실수
- 확장자만 보고 "이건 그냥 EXE겠지"라고 단정하는 것 — .NET이나 설치 스크립트일 수 있다.
- `strings` 결과를 안 보고 바로 어셈블리부터 읽기 시작하는 것 — 문자열이 지도 역할을 한다.
- 32비트/64비트를 확인하지 않고 레지스터 이름(`eax` vs `rax`)에 혼란을 겪는 것.

## 막혔을 때 다음 체크
- `file` 명령이 없다면 WSL이나 Git Bash에 `file` 패키지가 설치되어 있는지 확인 (`sudo apt install file`).
- 문자열이 하나도 안 보인다면 → REV-0002(확장자/실제 형식 확인)와 패킹 의심 체크리스트(REV-0224)로 이동.
- 함수가 하나도 안 보인다면 → REV-0009(main이 안 보일 때), REV-0010(stripped에서 시작점 잡기)로 이동.

## 미니 예제
가상의 CTF 문제 `crackme`를 받았다고 하자.
```bash
$ file crackme
crackme: ELF 64-bit LSB executable, x86-64, ... not stripped

$ strings -n 6 crackme | grep -i -E "correct|wrong|flag"
Correct! Here is your flag:
Wrong password, try again.
```
이 두 줄만으로 "입력을 받아서 비교하는 crackme이고, 두 문자열 중 하나를 출력하는 분기가 있다"는 사실을 알 수 있다. 다음 할 일은 IDA에서 `Correct!` 문자열을 더블클릭 → Xrefs(X 키)로 이 문자열을 참조하는 함수로 이동하는 것이다.

## 관련 글
- REV-0002 — 확장자를 믿으면 안 되는 이유와 실제 파일 형식 확인법
- REV-0009 — main 함수가 안 보일 때 찾는 방법
- REV-0010 — stripped 바이너리에서 시작점 잡는 방법
- REV-0100 — PLT와 GOT 기초

## 출처/검증
- `file(1)`, `strings(1)`, `readelf(1)` — GNU binutils 공식 man page 내용 기준으로 작성 (2026-09-08 검증).
- Detect It Easy 공식 GitHub(horsicq/Detect-It-Easy) 기능 설명 기준.
