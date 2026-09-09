---
id: REV-1104
title: "Ghidra/IDA에서 ARM 바이너리 아키텍처 설정하기"
slug: "rev-1104-ghidra-ida-arm-arch-setup"
category: "other-targets"
difficulty: "basic"
platform: [linux, android]
architecture: [ARM, ARM64]
format: [ELF]
tools: [Ghidra, IDA]
keywords: ["Ghidra ARM Language", "IDA processor type ARM", "Thumb 강제 디스어셈블", "ARM v7 v8 little endian"]
aliases: ["Ghidra에서 ARM 로드하는 법", "IDA ARM 아키텍처 설정", "잘못된 아키텍처로 열림", "Thumb으로 다시 disassemble"]
symptom_keywords: ["Ghidra가 ARM 바이너리를 이상하게 분석함", "함수가 하나도 안 잡힘", "명령어가 계속 invalid로 나옴"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
ELF 헤더가 있는 정상적인 ARM 실행파일/공유 라이브러리는 대부분 Ghidra/IDA가 아키텍처를 자동으로 인식하지만, raw 펌웨어 덤프이거나 자동 인식이 틀렸을 때는 Ghidra는 Import 대화상자의 Language 드롭다운에서, IDA는 Load new file 대화상자의 Processor type에서 ARM 버전(v4t/v5t/v7/v8)과 엔디안, 그리고 필요하면 Thumb 여부까지 직접 지정해야 한다.

## 언제 검색해야 하나
- Ghidra/IDA로 ARM 바이너리를 열었는데 함수가 거의 안 잡히거나 디스어셈블리가 전부 `??`/`invalid instruction`으로 나올 때
- 펌웨어에서 뽑아낸 raw 바이너리(ELF 헤더가 없는 순수 바이너리 덤프)를 분석해야 할 때
- REV-1102에서 다룬 ARM/Thumb 모드 오판이 의심되어 특정 구간만 다시 디스어셈블해야 할 때
- 32비트 ARM인지 64비트 ARM64인지조차 확신이 안 설 때

## 핵심 개념

### 자동 인식이 되는 경우와 안 되는 경우
`.elf`나 안드로이드의 `.so`처럼 표준 ELF 헤더(`e_machine` 필드에 `EM_ARM` 또는 `EM_AARCH64` 값 포함)를 가진 파일은 Ghidra의 Importer와 IDA 모두 헤더를 읽어 아키텍처를 자동으로 맞춘다. 반면 헤더가 없는 raw 펌웨어 덤프(`.bin`)는 두 도구 모두 파일 포맷을 스스로 판단할 근거가 없으므로 사용자가 수동으로 CPU 종류, 엔디안, 시작 주소(base address)를 지정해야 한다.

### Ghidra — Import 시 Language 선택
Ghidra는 파일을 열 때(Import) 나오는 대화상자에서 "Format"(예: Raw Binary, Executable and Linking Format)과 "Language" 두 항목을 지정한다. Language를 클릭하면 프로세서/버전/엔디안/컴파일러 조합 목록이 뜨는데, ARM 계열은 버전별로 세분화되어 있다.
- `ARM:LE:32:v4t` — ARMv4T(예: 오래된 임베디드 기기, Game Boy Advance 등), little endian
- `ARM:LE:32:v5t` — ARMv5T, little endian
- `ARM:LE:32:v7` — ARMv7 계열, little endian(가장 흔한 32비트 안드로이드 네이티브 라이브러리)
- `ARM:LE:64:v8A` — ARM64(AArch64) v8, little endian(64비트 안드로이드 네이티브 라이브러리, 최신 임베디드)
- Cortex-M 계열 마이크로컨트롤러는 Thumb 전용이므로 Thumb 관련 옵션만 선택 가능한 경우가 많다.

어떤 버전인지 정확히 모르겠으면, 유력한 후보 몇 개로 각각 열어보고 Ghidra의 자동 분석(Auto Analysis) 후 함수가 더 많이 잡히고 디코딩 오류(빨간 글씨의 `??`)가 더 적은 쪽을 선택하는 것이 실전적인 방법이다. 한 번 특정 언어로 임포트한 뒤 다른 언어로 바꾸려 하면 "Language translation not supported" 오류가 나서 실패할 수 있으므로, 처음 임포트할 때 신중하게 고르거나 잘못되면 새로 임포트하는 것이 안전하다.

### Ghidra — 특정 구간만 Thumb으로 재해석
자동 분석 중 일부 함수가 ARM/Thumb 모드를 잘못 판단해 깨진 디스어셈블리가 나오는 경우, Ghidra의 Listing 창에서 해당 주소를 우클릭하면 "Disassemble"과 "Disassemble (Thumb mode)" 같은 컨텍스트 메뉴 항목으로 강제로 다시 디스어셈블할 수 있다. 이는 REV-1102에서 설명한 "심볼 주소 LSB로 Thumb 여부 판단" 지식과 함께 쓰면 효과적이다.

### IDA — Load new file 대화상자의 Processor type
IDA에서 File → Open으로 파일을 열면 "Load a new file" 대화상자가 뜨는데, 여기에 인식된 파일 포맷 목록과 함께 "Processor type" 드롭다운이 있다. ELF 헤더가 있으면 IDA가 자동으로 ARM Little-endian/ARM Big-endian 등을 선택해주지만, raw 바이너리를 강제로 "Binary File" 포맷으로 로드할 때는 이 드롭다운에서 사용자가 직접 ARM 계열을 선택해야 하고, 이때 "MANUAL LOAD" 옵션을 함께 켜면 세그먼트 시작 주소 등도 직접 지정할 수 있다.

## 화면/코드에서 보이는 징후
- Ghidra Listing 창에 빨간색 `??` 또는 `Bad Instruction`이 반복해서 나타남
- Ghidra Functions 창에 함수가 거의 안 잡힘(자동 분석이 코드 경계를 못 찾음)
- IDA에서 열자마자 Processor type이 `metapc`(x86)로 잘못 잡혀 있음(raw 바이너리를 잘못된 기본값으로 연 경우)
- 디스어셈블리 중간에 갑자기 명령어가 깨지기 시작하는 지점이 있음(ARM/Thumb 경계 오판)

## 가장 먼저 할 것
파일에 ELF 헤더가 있는지(`file ./chall.so` 결과에 `ELF 32-bit`/`ELF 64-bit`, `ARM`/`ARM aarch64` 등이 나오는지) 먼저 확인한다. 있다면 자동 인식을 믿고 열되 결과가 이상하면 버전(v7 vs v8, LE vs BE)만 다시 확인한다. 없다면(raw 덤프) 처음부터 Language/Processor type을 수동으로 골라야 한다는 것을 인지하고 시작한다.

## 단계별 절차
1. `file ./target`으로 ELF 여부와 32/64비트, 아키텍처 문자열 확인
2. ELF가 있으면: Ghidra는 Import 시 Format을 "Executable and Linking Format (ELF)"로 두고 자동 인식된 Language를 그대로 신뢰, IDA도 자동 인식 결과를 우선 신뢰
3. ELF가 없으면(raw 펌웨어): Ghidra Import에서 Format을 "Raw Binary"로 바꾸고 Language에서 ARM 버전 후보를 하나씩 선택해 Auto Analysis 결과(함수 개수, Bad Instruction 개수)를 비교
4. IDA에서 raw 바이너리를 열 때는 "Binary File" 포맷 선택 후 Processor type에서 ARM 계열을 직접 지정, 필요하면 MANUAL LOAD로 로드 주소 지정
5. 일부 구간만 디스어셈블리가 깨지면 REV-1102를 참고해 해당 함수 심볼 주소의 LSB를 확인하고, Ghidra는 우클릭 "Disassemble (Thumb mode)", IDA는 해당 위치에서 Alt+G(세그먼트 레지스터 값 변경, `T` 레지스터를 0/1로 설정)로 강제 재해석
6. 32비트/64비트조차 불확실하면 `file` 결과의 `ELF 32-bit`/`ELF 64-bit` 표기 또는 레지스터 이름 패턴(디스어셈블리에 `X0`~`X30`이 보이면 확실히 ARM64)으로 최종 확인

## 명령어/단축키
```bash
# 아키텍처/엔디안/32-64비트 빠르게 확인
file ./target
readelf -h ./target | grep -E "Class|Data|Machine"
```
Ghidra: File → Import File → Language 필드 클릭 → 필터 창에 `ARM` 입력 후 버전/엔디안 선택.
Ghidra 특정 구간 재해석: Listing 창에서 우클릭 → Disassemble / Disassemble (Thumb mode).
IDA: File → Open → Load new file 대화상자의 Processor type 드롭다운.
IDA 특정 구간 재해석: 해당 주소에서 Edit → Segments → Change segment register value(단축키 `Alt+G`)로 `T` 레지스터를 0(ARM)/1(Thumb)로 설정.

## 출력 해석
`readelf -h`의 `Machine:` 필드가 `ARM`이면 32비트 ARM, `AArch64`면 64비트 ARM64다. `Data:` 필드가 `2's complement, little endian`인지 `big endian`인지도 함께 확인해야 Ghidra/IDA에서 올바른 엔디안 옵션을 고를 수 있다(대부분의 안드로이드/임베디드 ARM은 little endian이지만 일부 네트워크 장비 펌웨어는 big endian인 경우도 있다).

## 흔한 실수
- ELF 헤더가 있는 파일인데도 자동 인식 결과를 무시하고 임의로 다른 버전을 선택해 오히려 분석을 망치는 것.
- 한 번 잘못된 Language/Processor type으로 임포트한 뒤 도구 내에서 언어만 바꾸려다 실패를 반복하는 것 — 처음부터 다시 Import/Open 하는 것이 더 빠르다.
- Thumb 전용(Cortex-M) 펌웨어를 일반 ARM(32비트 명령어 지원) 언어로 열어 명령어가 전부 깨지는 것.
- v7과 v8(64비트) 두 후보를 헷갈려서 완전히 다른 명령어 집합으로 여는 것 — 파일이 32비트 ELF인지 64비트 ELF인지부터 확인하면 방지 가능하다.

## 막혔을 때 다음 체크
- ARM/Thumb 모드 개념 자체가 헷갈리면 → REV-1102 ARM Thumb 모드가 무엇이고 왜 헷갈리는지
- 레지스터 이름으로 32/64비트를 구분하는 법이 필요하면 → REV-1101 ARM/ARM64 레지스터와 호출 규약 기초
- Ghidra/IDA 설치 자체가 안 되어 있다면 → REV-0277 Ghidra 설치와 오프라인 준비, REV-0274 IDA 설치와 오프라인 준비
- ARM 바이너리를 실제로 실행해서 동적으로 검증하고 싶다면 → REV-1105 QEMU user-mode로 다른 아키텍처 바이너리 실행하기(qemu-arm/qemu-mips)

## 미니 예제
```bash
$ file libnative.so
libnative.so: ELF 32-bit LSB shared object, ARM, EABI5 version 1 (SYSV), ...

$ readelf -h libnative.so | grep -E "Class|Data|Machine"
  Class:                             ELF32
  Data:                              2's complement, little endian
  Machine:                           ARM
```
이 결과라면 Ghidra Import에서 Language를 `ARM:LE:32:v7`(EABI5는 대체로 ARMv7 이상 툴체인에서 쓰임) 계열로, IDA에서는 Processor type을 ARM Little-endian(32비트)으로 선택하면 된다. 만약 `Machine: AArch64`였다면 64비트 ARM64용 언어(`ARM:LE:64:v8A`)를 선택해야 한다.

## 관련 글
- REV-1101 — ARM/ARM64 레지스터와 호출 규약 기초
- REV-1102 — ARM Thumb 모드가 무엇이고 왜 헷갈리는지
- REV-0277 — Ghidra 설치와 오프라인 준비
- REV-0274 — IDA 설치와 오프라인 준비
- REV-1105 — QEMU user-mode로 다른 아키텍처 바이너리 실행하기(qemu-arm/qemu-mips)

## 출처/검증
- Ghidra Import 대화상자의 Format/Language 선택, ARM 버전별 Language ID(`ARM:LE:32:v4t`, `ARM:LE:32:v7`, `ARM:LE:64:v8A` 등), raw 바이너리 시 수동 지정 필요성: NationalSecurityAgency/ghidra 저장소 ARM.ldefs (https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/Processors/ARM/data/languages/ARM.ldefs), Feabhas "Disassembling a Cortex-M raw binary file with Ghidra" 기준 확인(2026-09-10).
- 여러 후보 언어로 열어 함수 인식률/오류로 아키텍처를 추정하는 실전 접근법과 "Language translation not supported" 오류: ARM Community 포럼 "Reverse engineering ARM firmware: selecting an architecture" 스레드 및 관련 GitHub 이슈(NationalSecurityAgency/ghidra Discussions #9063) 기준.
- IDA의 Load new file 대화상자에서 Processor type을 지정하는 절차는 Hex-Rays IDA 공식 문서 체계(Basic Usage/Supported Processors) 기준의 일반적으로 알려진 워크플로.
