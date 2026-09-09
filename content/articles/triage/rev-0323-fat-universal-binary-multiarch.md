---
id: REV-0323
title: "여러 아키텍처를 포함한 바이너리(Fat/Universal)를 만났을 때 대응"
slug: "rev-0323-fat-universal-binary-multiarch"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [file, lipo, otool, IDA, Ghidra]
keywords: ["Fat binary", "Universal binary", "Mach-O multi-arch", "lipo 사용법", "여러 아키텍처 바이너리 분리"]
aliases: ["fat 바이너리란", "universal binary 분석", "lipo로 아키텍처 분리", "Mach-O 여러 개 들어있는 파일"]
symptom_keywords: ["file 명령이 universal binary라고 나옴", "IDA가 어떤 아키텍처로 열지 물어봄", "바이너리가 실행이 안 되는데 크기가 큼", "arm64와 x86_64가 같이 있다고 나옴"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`file` 명령 결과에 "Mach-O universal binary with N architectures"가 나오는 파일은 하나의 파일 안에 x86_64용 코드와 arm64용 코드 등 여러 아키텍처 슬라이스가 나란히 묶여 있는 것이므로, 그대로 분석하려 하지 말고 `lipo`나 `otool -f`로 원하는 아키텍처 슬라이스 하나만 골라 뽑아낸 뒤 그 슬라이스를 평범한 단일 아키텍처 바이너리처럼 분석하면 된다.

## 언제 검색해야 하나
- `file ./chall` 결과에 `Mach-O universal binary with 2 architectures` 같은 문구가 나올 때
- IDA나 Ghidra로 파일을 열었더니 어떤 아키텍처로 열지 선택하라는 창이 뜰 때
- 파일 크기가 이상하게 크고, `objdump`/`readelf`로는 아예 인식이 안 될 때(ELF가 아니라 Mach-O이기 때문)
- 문제 설명에 "macOS/iOS 바이너리"라는 언급이 있거나, 매직 바이트가 `0xCAFEBABE`로 시작할 때

## 핵심 개념

### Fat/Universal Binary란
Apple의 Mach-O 포맷은 하나의 실행 파일 안에 여러 CPU 아키텍처용 코드를 동시에 담을 수 있는 "Fat Binary"(공식 명칭은 Universal Binary) 구조를 지원한다. 예를 들어 인텔 맥(x86_64)과 애플 실리콘(arm64)에서 모두 실행되어야 하는 앱은 두 아키텍처의 코드를 한 파일에 같이 넣어 배포한다. 파일 맨 앞에는 "fat header"가 있고, 그 안에 각 아키텍처별 오프셋과 크기가 기록된 슬라이스 목록이 들어있다.

### 매직 바이트로 구분하기
- `0xCAFEBABE` (빅엔디안 기준): Fat/Universal binary 헤더의 매직 넘버. 참고로 이 값은 Java 클래스 파일의 매직 넘버와 동일하므로 확장자를 함께 봐야 헷갈리지 않는다(REV-0020).
- `0xFEEDFACE`: 32비트 Mach-O
- `0xFEEDFACF`: 64비트 Mach-O

`file` 명령은 이 매직 바이트를 읽어 "Mach-O universal binary with N architectures"처럼 사람이 읽기 쉬운 문자열로 바꿔 보여준다.

### 왜 이런 파일이 CTF에 나오는가
macOS/iOS 대상 리버싱 문제이거나, 문제 출제자가 인텔 맥과 애플 실리콘 채점 환경을 모두 지원하려고 fat binary로 배포하는 경우다. 드물게 여러 아키텍처를 테스트하는 크로스 컴파일 문제에서도 등장한다.

### 슬라이스를 분리해서 접근한다
Fat binary를 통째로 IDA/Ghidra에 로드하면 도구가 알아서 "어떤 아키텍처를 분석할지" 물어보는 경우가 많다. 하지만 명령줄에서 미리 원하는 슬라이스만 분리해두면 이후 작업(strings, objdump 계열 분석, 실행 테스트)이 훨씬 깔끔해진다. macOS 환경이라면 `lipo`가 표준 도구이고, macOS가 없는 환경(순수 Linux/Windows 오프라인 환경)이라면 IDA/Ghidra가 fat binary 파서를 내장하고 있어 열 때 아키텍처만 선택하면 된다는 점을 기억해둔다.

## 화면/코드에서 보이는 징후
- `file ./chall` → `Mach-O universal binary with 2 architectures: [x86_64:Mach-O 64-bit executable x86_64] [arm64]`
- 헥스 에디터로 파일 맨 앞을 봤을 때 `CA FE BA BE`로 시작
- IDA로 열 때 "Choose the type of file to load" 같은 아키텍처 선택 대화상자가 뜸
- `readelf`/`objdump`(ELF 전용 도구)로 열면 "not an ELF file" 오류가 남 — 애초에 Mach-O이기 때문

## 가장 먼저 할 것
`file ./chall`을 실행해 포함된 아키텍처 목록을 확인한다. macOS 환경이 있다면 `lipo -info ./chall`로 더 자세한 슬라이스 정보를 본다. 없다면 IDA/Ghidra로 바로 열어 아키텍처 선택 창에서 분석하려는 아키텍처(보통 자신의 실행 환경과 같은 것, 또는 문제에서 요구하는 것)를 고른다.

## 단계별 절차
1. `file ./chall`로 어떤 아키텍처들이 포함되어 있는지 확인
2. macOS 환경이 있다면 `lipo -info ./chall`로 슬라이스 목록을 정확히 나열
3. `lipo -thin <arch> ./chall -output chall_thin`으로 원하는 아키텍처 슬라이스만 추출 (예: `lipo -thin arm64`)
4. 추출한 `chall_thin`은 이제 평범한 단일 아키텍처 Mach-O이므로 `otool -l`, `otool -tv`(디스어셈블) 등으로 분석하거나 IDA/Ghidra에 로드
5. macOS 환경이 없다면 IDA/Ghidra로 원본 파일을 바로 열고, 아키텍처 선택 창에서 분석할 슬라이스를 고름(도구가 내부적으로 알아서 오프셋을 계산해줌)
6. 실행 테스트가 필요하다면 반드시 채점 서버/자신의 CPU와 같은 아키텍처 슬라이스를 골라야 실행이 된다는 점에 유의 (인텔 맥에서 arm64 슬라이스만 뽑으면 실행 안 됨)
7. 이후 분석은 REV-0004(ELF 접근 순서)와 유사하게, 선택한 단일 아키텍처 바이너리를 대상으로 일반적인 정적/동적 분석 절차를 그대로 적용

## 명령어/단축키
```bash
file ./chall
lipo -info ./chall
lipo -thin arm64 ./chall -output ./chall_arm64
lipo -thin x86_64 ./chall -output ./chall_x64
otool -f ./chall     # fat header 정보
otool -l ./chall_x64 # load command 확인(분리 후)
```

## 출력 해석
- `lipo -info`가 `Architectures in the fat file: chall are: x86_64 arm64`처럼 출력하면 두 슬라이스가 존재한다는 뜻이며, 각각을 `-thin`으로 분리할 수 있다.
- `file`이 "executable" 하나만 나열하면 애초에 fat binary가 아니라 단일 아키텍처 Mach-O이므로 이 문서의 절차는 필요 없다.
- IDA/Ghidra 아키텍처 선택 창에서 잘못된 아키텍처를 골라도 파일 자체가 깨지지는 않으니, 분석 중 코드가 이상하면 다시 열어 다른 슬라이스를 선택해본다.

## 흔한 실수
- fat binary를 ELF로 착각하고 `readelf`/`objdump`(ELF 전용)로 열어보려다 오류만 보고 "파일이 손상됐다"고 오해하는 것.
- 실행 테스트 시 자신의 CPU 아키텍처와 다른 슬라이스만 남겨서 "왜 실행이 안 되지"라고 헤매는 것.
- IDA/Ghidra의 아키텍처 선택 창을 대충 넘기고 아무 슬라이스나 골라 분석하다가, 나중에 함수 오프셋이 이상하다는 것을 뒤늦게 발견하는 것.
- `0xCAFEBABE` 매직 바이트만 보고 무조건 Java 클래스 파일이라 단정하는 것 — 확장자와 전체 구조(Fat header 뒤에 Mach-O 헤더들이 이어지는지)를 함께 확인해야 한다.

## 막혔을 때 다음 체크
- 애초에 매직 바이트로 파일 형식을 구분하는 법이 헷갈린다 → REV-0020 Magic Byte와 파일 시그니처
- 확장자만 보고 형식을 판단하다 틀린 적이 있다 → REV-0002 확장자를 믿으면 안 되는 이유와 실제 파일 형식 확인법
- 슬라이스 분리 후 일반적인 리버싱 절차가 기억 안 난다 → REV-0004 처음 보는 ELF 문제 접근 순서(포맷은 다르지만 접근 순서 원칙은 유사)
- 컴파일러/패커 정보까지 확인하고 싶다 → REV-0126 Detect It Easy로 컴파일러 패커 확인

## 미니 예제
```bash
$ file challenge
challenge: Mach-O universal binary with 2 architectures: [x86_64:Mach-O 64-bit executable x86_64] [arm64:Mach-O 64-bit executable arm64]

$ lipo -info challenge
Architectures in the fat file: challenge are: x86_64 arm64

$ lipo -thin x86_64 challenge -output challenge_x64
$ file challenge_x64
challenge_x64: Mach-O 64-bit executable x86_64
```
`lipo -thin`으로 뽑아낸 `challenge_x64`는 이제 평범한 단일 아키텍처 Mach-O 실행 파일이므로, 이후로는 일반적인 정적/동적 분석 도구로 다른 실행 파일과 똑같이 다루면 된다.

## 관련 글
- REV-0020 — Magic Byte와 파일 시그니처
- REV-0002 — 확장자를 믿으면 안 되는 이유와 실제 파일 형식 확인법
- REV-0004 — 처음 보는 ELF 문제 접근 순서
- REV-0126 — Detect It Easy로 컴파일러 패커 확인

## 출처/검증
- Mach-O Universal/Fat Binary 구조와 매직 넘버(`0xCAFEBABE`, `0xFEEDFACE`, `0xFEEDFACF`): Apple 공식 문서(Mach-O File Format Reference, Apple Developer Documentation) 기준.
- `lipo`, `otool` 명령어 사용법: Apple Developer Tools(Xcode Command Line Tools) 공식 매뉴얼 기준 (2026-09-09 검증).
