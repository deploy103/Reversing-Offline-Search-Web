---
id: REV-0802
title: "IDA/Ghidra에서 잘못된 아키텍처로 로드되어 전부 깨질 때"
slug: "rev-0802-wrong-architecture-load"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["잘못된 아키텍처 로드", "wrong processor type", "disassembly garbage", "language 잘못 선택", "processor module 오선택"]
aliases: ["디스어셈블리가 전부 깨져보임", "함수가 하나도 안 잡힘 아키텍처 문제", "IDA Ghidra 로드 옵션 잘못됨", "명령어가 전부 이상하게 나옴"]
symptom_keywords: ["디스어셈블리가 전부 말이 안 되는 명령어로 나옴", "Functions 창이 거의 비어있음", "F5가 아예 안 먹힘", "문자열이 하나도 안 잡힘"]
source_ids: ["SRC-HEXRAYS-DOCS", "SRC-GHIDRA-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
바이너리를 열자마자 디스어셈블리 전체가 알아볼 수 없는 명령어 나열처럼 보이고 함수/문자열이 거의 안 잡힌다면, 코드 자체의 문제가 아니라 IDA/Ghidra가 **실제 CPU 아키텍처와 다른 프로세서 모듈(processor type/language)로 파일을 로드**했을 가능성이 매우 높으므로, 분석을 계속하기 전에 셸에서 `file`이나 `readelf -h`로 진짜 아키텍처를 먼저 확인하고 올바른 옵션으로 다시 로드해야 한다.

## 언제 검색해야 하나
- 파일을 열자마자 디스어셈블리가 유효하지 않은 명령어(invalid opcode)나 의미 없어 보이는 명령어로 가득 찰 때
- Functions 창이 거의 텅 비어 있고, entry point 근처조차 코드로 인식되지 않을 때
- Strings 창에 아무 문자열도 안 잡히는데 `strings` 명령으로는 분명히 문자열이 보일 때
- ARM/MIPS/RISC-V 등 x86이 아닌 바이너리를 실수로 x86 모듈로 열었거나, 반대의 경우

## 핵심 개념
IDA와 Ghidra는 파일 헤더(ELF의 `e_machine`, PE의 Machine 필드)를 보고 자동으로 아키텍처를 추정하지만, 이 자동 인식이 항상 성공하는 것은 아니다. 헤더가 손상되었거나, 파일 형식 자체가 특이하거나(펌웨어 raw 바이너리처럼 헤더가 아예 없는 경우), 사용자가 로드 대화상자에서 수동으로 다른 프로세서 모듈을 선택해버리면, 완전히 다른 명령어 집합의 CPU로 바이트를 해석하게 된다.

예를 들어 ARM 바이너리를 x86 모듈로 열면, ARM의 4바이트 고정 길이 명령어 인코딩이 x86의 가변 길이 명령어 인코딩 규칙으로 잘못 쪼개져서 완전히 의미 없는 니모닉의 나열이 출력된다. 이 상태에서는 코드 흐름 분석(함수 경계, 분기)도 전부 엉망이 되므로 Functions 창이 거의 비게 되고, 디컴파일은 당연히 실패한다(REV-0152와는 원인이 다르다 — 여기서는 애초에 올바른 명령어로조차 해석되지 않고 있다).

이 문제는 REV-0803(32비트/64비트 혼동)과 사촌 관계지만 다르다. REV-0803은 **같은 아키텍처 계열 안에서 비트폭만** 잘못 고른 경우(x86을 x64로, 혹은 그 반대)이고, 이 글은 **아키텍처 자체(x86, ARM, MIPS 등)를 완전히 잘못 고른 경우**다. 증상은 비슷하게 "전부 깨져 보인다"로 나타나지만, 확인 방법과 고치는 옵션이 다르다.

## 화면/코드에서 보이는 징후
- 디스어셈블리 창에 `??`, `bad opcode`, 혹은 이상한 니모닉이 계속 반복됨
- entry point 근처인데도 함수 하나 안 잡힘
- 알려진 표준 프롤로그(`push ebp` / `endbr64` 등)가 전혀 안 보임
- 로드 시 IDA가 물어본 "Processor type" 대화상자에서 무의식적으로 아무 값이나 선택하고 넘어갔던 기억이 있음

## 가장 먼저 할 것
IDA/Ghidra를 다시 만지기 전에, 셸에서 파일 자체의 진짜 아키텍처부터 확인한다.

## 단계별 절차

**1) 셸에서 진짜 아키텍처 확인**
```bash
file chall
readelf -h chall | grep Machine
```
PE라면:
```bash
file chall.exe
# 또는 objdump -f chall.exe 로 Machine 필드 확인
```
`file` 출력에 `ARM`, `MIPS`, `x86-64`, `Intel 80386` 등 정확한 아키텍처 이름이 나온다.

**2) IDA에서 재로드**
File → Close, 그 다음 다시 File → Open으로 열 때 뜨는 "Load a new file" 대화상자에서 Processor type을 1단계에서 확인한 값과 정확히 일치하게 선택한다. 이미 잘못 로드된 상태라면 기존 IDB(데이터베이스)를 새로 만드는 것이 가장 깔끔하다 — 잘못된 분석 결과가 남아있는 기존 IDB를 재사용하지 않는다.

**3) Ghidra에서 재Import**
File → Close Project (또는 해당 프로그램만 제거) 후, File → Import File로 다시 가져올 때 Language 선택 대화상자에서 정확한 아키텍처/엔디안/컴파일러 규격을 고른다. Ghidra는 후보를 여러 개 보여주므로, 헤더 정보와 정확히 일치하는 것을 고른다(예: `ARM:LE:32:v8` 등 세부 버전까지).

**4) 재분석 확인**
올바른 프로세서로 다시 연 뒤, entry point 근처에 알려진 프롤로그 패턴이 정상적으로 보이는지, Functions 창에 함수가 정상적인 개수로 잡히는지, Strings 창에 문자열이 나오는지 확인한다.

**5) 그래도 이상하면 파일 자체 손상 의심**
올바른 아키텍처로 로드했는데도 여전히 깨져 보인다면, 파일 헤더 자체가 조작/손상되었거나 커스텀 로더용으로 만들어진 특수 포맷일 수 있다. 이 경우 헤더를 수동으로 수정하거나(REV-0332 파일이 깨진 것처럼 보일 때 참고) raw 바이너리로 강제 로드(IDA의 "Unknown" 포맷팅 후 처리 목록 프로세서 수동 지정)해야 한다.

## 명령어/단축키
```bash
file <binary>
readelf -h <binary> | grep -E "Machine|Class|Data"
objdump -f <binary>
```
- IDA: File → Open 시 "Processor type" 드롭다운
- Ghidra: File → Import File 시 Language 선택 목록

## 출력 해석
- `readelf -h`의 `Machine` 필드가 `Advanced Micro Devices X86-64`면 x64, `Intel 80386`이면 x86, `ARM`이면 ARM 계열이다.
- IDA/Ghidra에서 올바른 프로세서로 재로드한 뒤 함수 개수가 급격히 늘어나고 알아볼 수 있는 니모닉이 나온다면 문제가 해결된 것이다.

## 흔한 실수
- 로드 대화상자를 습관적으로 기본값(엔터)으로 넘겨서 무슨 프로세서가 선택됐는지 확인하지 않는 것.
- 잘못 로드된 IDB/Ghidra 프로젝트를 지우지 않고 그 위에서 계속 재분석만 반복하는 것 — 처음부터 새로 여는 것이 빠르다.
- 셸 도구(`file`)를 먼저 쓰지 않고 GUI 안에서만 이것저것 눌러보며 시간을 쓰는 것.
- 32/64비트 혼동(REV-0803)과 이 문제를 혼동해서 엉뚱한 옵션을 고치는 것 — 아키텍처 자체가 다른 건지, 비트폭만 다른 건지 먼저 구분한다.

## 막혔을 때 다음 체크
- 같은 아키텍처인데 비트폭만 헷갈린 것 같다면 → REV-0803
- 올바른 아키텍처로 열었는데도 여전히 함수가 하나도 안 잡힌다면 → REV-0772
- 파일 자체가 손상된 것처럼 보인다면 → REV-0332

## 미니 예제
`file chall` 결과가 `ELF 32-bit LSB executable, ARM, EABI5 version 1`인데, IDA에서 무심코 기본값(Intel x86)으로 열었다고 하자. 디스어셈블리는 전부 의미 없는 니모닉으로 채워지고 Functions 창은 텅 비어 있다. IDB를 새로 만들고 File → Open 시 Processor type을 "ARM Little-endian"으로 명시적으로 선택해 다시 열면, `push {r4, lr}` 같은 정상적인 ARM 프롤로그가 보이기 시작하고 Functions 창에도 함수가 정상적으로 채워진다.

## 관련 글
- REV-0803 — 32비트/64비트를 헷갈려서 잘못 로드했을 때
- REV-0772 — IDA에서 함수가 아예 하나도 안 잡힐 때
- REV-0152 — IDA Decompiler Failed가 뜰 때
- REV-0332 — 문제 파일이 손상된 것처럼 안 열릴 때

## 출처/검증
- ELF 헤더의 `e_machine` 필드로 아키텍처를 식별하는 방식은 System V ABI(ELF 스펙) 공식 문서 기준이다.
- IDA의 Processor type 선택 대화상자와 재로드 절차, Ghidra의 Language 선택 목록은 각각 Hex-Rays 공식 문서와 Ghidra 공식 문서(Importing Files 관련 챕터) 기준이다.
- 이 글은 2026-09-09 기준으로 작성되었다.
