---
id: REV-0685
title: "binutils 버전 차이로 출력 포맷이 달라지는 경우 대응"
slug: "rev-0685-binutils-version-output-format-diff"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [readelf, objdump, nm]
keywords: ["binutils 버전 차이", "readelf --wide", "objdump 출력 포맷 다름", "binutils 호환성", "readelf --version"]
aliases: ["readelf 출력이 잘려서 나옴", "objdump 결과가 예전과 다름", "binutils 업데이트 후 스크립트 깨짐"]
symptom_keywords: ["readelf 출력이 화면 폭에서 줄바꿈되어 파싱이 깨짐", "objdump -d 결과 컬럼 순서가 예전과 다름", "스크립트로 readelf를 파싱했는데 새 버전에서 정규식이 안 맞음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`readelf`, `objdump`, `nm` 같은 GNU binutils 도구는 버전이 올라가면서 컬럼 폭, 줄바꿈, 일부 필드 표기가 바뀌는 경우가 있어, 오래된 튜토리얼/스크립트가 파싱하던 출력 형식과 최신 배포판의 실제 출력이 미묘하게 달라 보이거나 스크립트가 깨질 수 있으므로, 항상 `--version`으로 실제 버전을 확인하고 `--wide` 같은 안정적인 옵션을 우선 사용하는 습관이 필요하다.

## 언제 검색해야 하나
- 오래된 CTF 라이트업이나 블로그의 `readelf`/`objdump` 명령을 그대로 따라 했는데, 화면에 나온 출력 모양이 글의 스크린샷과 다를 때
- `readelf -S ./chall` 결과가 터미널 폭 때문에 컬럼이 줄바꿈되어 `grep`/`awk`로 파싱한 스크립트가 갑자기 값을 잘못 읽어올 때
- 신입 환경에서 apt로 새로 설치한 binutils 버전이 예전에 쓰던 버전보다 훨씬 최신이라 결과 포맷이 달라졌을 때
- 여러 리눅스 배포판(예: 오래된 Ubuntu 18.04 vs 최신 Ubuntu 24.04)에서 같은 명령을 돌렸는데 출력이 다를 때

## 핵심 개념

### binutils는 계속 업데이트되는 프로젝트다
`readelf`, `objdump`, `nm`, `strings`, `objcopy` 등은 모두 GNU Binutils라는 하나의 패키지에 속한 도구들이며, 이 패키지는 활발히 유지보수되어 새로운 ELF 확장(예: 새 섹션 타입, 새 재배치 타입)을 지원하고 사소한 출력 포맷을 개선하는 릴리스가 주기적으로 나온다. 따라서 몇 년 전에 쓰인 CTF 라이트업의 캡처 화면과 최신 배포판에서 실행한 결과가 컬럼 순서, 줄바꿈, 공백 개수 등에서 다를 수 있다. 이건 버그가 아니라 정상적인 버전 차이다.

### 가장 흔한 차이 유형
1. **터미널 폭에 따른 줄바꿈**: `readelf -S`(섹션 헤더), `readelf -l`(프로그램 헤더) 등은 기본적으로 출력 폭을 제한해서 긴 줄을 여러 줄로 접어 보여준다. 최신 버전일수록 이 접힘 기준이 조금씩 다르게 동작할 수 있다.
2. **필드 추가/이름 변경**: 새로운 ELF 확장(예: 새로운 동적 태그, 새로운 섹션 플래그 문자)이 추가되면서 플래그 문자 열이 늘어나거나, 헤더에 새 컬럼이 생기는 경우가 있다.
3. **색상/하이라이트 지원**: 최신 `objdump`/`readelf`는 터미널이 지원하면 일부 출력에 색을 넣는 옵션이 생기기도 해서, 파이프로 다른 프로그램에 넘기면 예상치 못한 이스케이프 시퀀스가 섞여 들어갈 수 있다.
4. **디스어셈블리 문법 미세 차이**: `objdump -d`의 opcode 문법 표현(특히 AT&T 문법에서 접미사, 메모리 피연산자 괄호 표기 등)이 binutils 버전과 아키텍처 확장(AVX-512 등 신규 명령어 지원)에 따라 조금씩 달라질 수 있다.

### 버전 확인이 첫 단계여야 하는 이유
```bash
readelf --version
objdump --version
nm --version
```
이 명령들은 첫 줄에 `GNU readelf (GNU Binutils) 2.42` 같은 형태로 정확한 버전을 보여준다. 어떤 예제/스크립트가 어느 버전 기준으로 작성됐는지 모른 채 출력이 다르다고 당황하기보다, 먼저 내 시스템의 버전을 확인하고 그 버전의 공식 문서(`man readelf`, `info binutils`)를 기준으로 삼는 것이 정확하다.

### 파싱 안정성을 높이는 옵션들
- `readelf --wide`(`-W`): 출력 폭 제한 없이 한 줄에 다 출력하도록 강제한다. 스크립트로 `readelf` 결과를 파싱할 때는 거의 필수로 붙여야 줄바꿈 때문에 정규식이 깨지는 문제를 피할 수 있다.
- `objdump --no-show-raw-insn`: opcode 바이트 나열을 빼고 니모닉만 남겨 출력 폭을 줄인다.
- 색상 출력이 방해된다면 `--color=never`(지원하는 버전의 경우)를 명시하거나, 파이프로 넘길 때는 대부분 자동으로 색상이 꺼진다(터미널이 아닌 파이프로 나갈 때 GNU 도구들이 흔히 따르는 관행이지만, 버전별로 옵션명이 다를 수 있으니 `--help`로 확인).
- 정확한 필드만 뽑고 싶다면 사람이 읽기 좋은 표 형식 대신 `readelf -x`(헥스 덤프), `objdump -j SECTION -s`처럼 특정 섹션만 지정해 출력 범위를 줄이는 것도 파싱 안정성에 도움이 된다.

## 화면/코드에서 보이는 징후
- `readelf -S ./chall` 결과의 섹션 이름/주소/오프셋 컬럼이 두 줄에 걸쳐 나뉘어 출력됨
- 블로그 스크린샷과 실제 실행 결과의 컬럼 순서/헤더 문구가 다름
- `awk '{print $5}'` 같은 고정 컬럼 위치 기반 스크립트가 최신 버전에서 엉뚱한 값을 뽑아냄
- `objdump -d` 결과에 예전엔 없던 opcode 바이트 나열 방식이나 새로운 명령어 니모닉이 보임

## 가장 먼저 할 것
`readelf --version`, `objdump --version`으로 실제 설치된 버전을 확인하고, 파싱용 스크립트를 쓴다면 `--wide` 옵션부터 추가해 줄바꿈 문제를 우선 제거한다.

## 단계별 절차
1. `readelf --version` / `objdump --version`으로 정확한 버전 확인
2. 참고하려는 튜토리얼/라이트업이 어느 버전 기준인지(대략적인 작성 연도로 추정) 감안
3. 사람이 읽을 때는 그냥 기본 출력을 눈으로 보되, 스크립트로 파싱해야 한다면 `readelf -W`(`--wide`)를 기본으로 추가
4. 컬럼 위치 기반 파싱(`awk '{print $N}'`) 대신 필드 이름 기반으로 `grep`/정규식을 짜서 컬럼 개수 변화에 덜 민감하게 만든다
5. 여전히 이상하면 `man readelf`/`man objdump` 또는 `readelf --help`로 현재 버전에 실제로 존재하는 옵션인지 재확인
6. 팀/CI 환경이라면 Dockerfile 등에 binutils 버전을 고정(`apt-get install binutils=2.38-*` 형태)해서 여러 환경 간 출력 차이 자체를 없애는 것도 방법이다

## 명령어/단축키
```bash
readelf --version
objdump --version
nm --version
readelf -W -S ./chall     # wide 모드로 섹션 헤더
readelf -W -l ./chall     # wide 모드로 프로그램 헤더
objdump --no-show-raw-insn -d ./chall
man readelf
readelf --help | less
```

## 출력 해석
`readelf --version` 첫 줄 예:
```
GNU readelf (GNU Binutils for Ubuntu) 2.42
```
이 `2.42`가 실제 사용 중인 binutils 버전이다. 블로그/CTF 라이트업이 훨씬 오래된 버전(예: `2.30`대) 기준으로 캡처됐다면, 컬럼 개수나 줄바꿈 위치가 다른 것이 당연하다. `readelf -W -S`로 얻은 결과는 한 섹션 정보가 항상 한 줄에 다 들어가므로, `grep`/`awk`로 안정적으로 컬럼을 잘라낼 수 있다.

## 흔한 실수
- 출력이 다르다고 "내 binutils가 고장났다"고 오해해서 재설치를 반복하는 것 — 대부분은 정상적인 버전 차이일 뿐이다.
- `readelf`/`objdump` 결과를 컬럼 번호(`$3`, `$5` 등)로만 파싱하는 스크립트를 짜서, 필드가 하나만 늘어나도 전체가 깨지는 것 — 가능하면 이름 기반 매칭이나 `--wide` + 고정 포맷 유지 옵션을 함께 쓴다.
- 여러 서버/CI 환경에서 각기 다른 binutils 버전이 깔려 있는데 이를 무시하고 같은 파싱 스크립트를 그대로 재사용하는 것.
- `readelf`의 오래된 옵션 문서만 참고하고 실제 설치된 버전에 그 옵션이 있는지 확인 안 하는 것 — 항상 `--help`나 `man`으로 현재 버전 기준 옵션을 재확인해야 한다.

## 막혔을 때 다음 체크
- `readelf`가 아예 잘린 헤더 오류를 내는 경우(버전 문제가 아니라 파일 손상 문제)라면 → REV-0700 readelf가 잘린 헤더라고 오류를 낼 때(손상된 ELF)
- ELF 구조 자체(섹션/세그먼트 헤더 필드 의미)가 헷갈리면 → REV-0640 ELF Section 이름 관례 사전(.text .rodata .bss 등)

## 미니 예제
```bash
$ readelf --version | head -1
GNU readelf (GNU Binutils for Ubuntu) 2.38

$ readelf -S ./chall | head -6
There are 30 section headers, starting at offset 0x3a08:

Section Headers:
  [Nr] Name              Type             Address           Offset
       Size              EntSize          Flags  Link  Info  Align
  [ 0]                   NULL             0000000000000000  00000000

$ readelf -W -S ./chall | head -4
There are 30 section headers, starting at offset 0x3a08:

Section Headers:
  [Nr] Name              Type            Address          Off    Size   ES Flg Lk Inf Al
```
기본 출력은 각 섹션 정보가 두 줄에 걸쳐 나오지만(`Address`/`Offset` 줄과 `Size`/`EntSize`/`Flags` 줄이 분리됨), `-W`(wide)를 추가하면 섹션 하나당 정확히 한 줄로 나와서 스크립트 파싱이 훨씬 안정적이다.

## 관련 글
- REV-0700 — readelf가 잘린 헤더라고 오류를 낼 때(손상된 ELF)
- REV-0640 — ELF Section 이름 관례 사전(.text .rodata .bss 등)

## 출처/검증
- GNU Binutils의 지속적 업데이트와 `readelf`/`objdump` 출력 옵션(`-W`/`--wide`, `--no-show-raw-insn` 등): GNU Binutils 공식 매뉴얼(`readelf(1)`, `objdump(1)`) 기준.
- binutils 릴리스별 출력 포맷 변경 이력은 각 배포 버전의 `NEWS`/체인지로그에서 반복적으로 확인되는 패턴 (2026-09-09 검증).
