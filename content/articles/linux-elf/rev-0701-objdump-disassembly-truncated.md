---
id: REV-0701
title: "objdump 디스어셈블 결과가 중간에 끊길 때"
slug: "rev-0701-objdump-disassembly-truncated"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [objdump]
keywords: ["objdump", "objdump -d", "디스어셈블 끊김", "objdump 생략", "disassemble-zeroes"]
aliases: ["objdump 결과가 짧게 끊김", "objdump 출력 중간에 멈춤", "objdump ... 표시", "objdump 전체 안 나옴"]
symptom_keywords: ["objdump -d 결과가 함수 중간에서 끊김", "objdump 출력에 점점점(...)만 나오고 이어지지 않음", "objdump 결과 파일이 너무 짧아 보임", "objdump로 본 코드가 실제 함수보다 짧음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`objdump -d` 출력이 "끊긴 것처럼" 보이는 원인은 대부분 실제 디스어셈블 실패가 아니라, objdump가 반복되는 0 바이트 블록을 `...`으로 생략하거나, 코드가 있는 섹션 전체가 아니라 일부만 지정해서 보고 있거나, 터미널/파이프 때문에 화면에서 잘려 보이는 것이며, 진짜 문제는 점프 테이블 등 데이터가 코드 사이에 섞여 있어 선형 디스어셈블이 깨지는 경우다.

## 언제 검색해야 하나
- `objdump -d ./chall`을 실행했는데 함수가 중간에서 뚝 끊기고 그 뒤로 아무것도 안 나올 때
- 출력에 `...`만 찍히고 그 다음 코드가 안 보일 때
- 특정 함수의 disassembly만 보고 싶은데 `objdump -d` 결과가 원하는 함수까지 도달하지 못하는 것처럼 보일 때
- 파일로 저장한 `objdump -d ./chall > out.asm` 결과의 줄 수가 예상보다 훨씬 적을 때

## 핵심 개념

### objdump는 반복되는 동일한 바이트를 생략한다
objdump는 기본적으로 연속된 0(널 바이트)로만 이루어진 블록을 만나면 그 내용을 전부 출력하지 않고 `...`로 축약해서 보여준다. 이건 "디스어셈블이 실패했다"는 뜻이 아니라 "이 구간은 전부 0이라서 생략했다"는 뜻이다. 패딩 구간, 정렬을 위한 채움 바이트, 초기화되지 않은 `.bss` 근처 등에서 흔히 나타난다. `-z`(`--disassemble-zeroes`) 옵션을 주면 생략 없이 전부 출력한다.

### objdump는 기본적으로 실행 가능한 섹션만 디스어셈블한다
`objdump -d`는 `SHF_EXECINSTR` 플래그가 붙은 섹션(`.text`, `.plt`, `.init`, `.fini` 등)만 디스어셈블한다. `.rodata`나 `.data` 안에 있는 바이트는 아예 대상이 아니므로, 원하는 함수가 그 섹션에 없거나 특정 섹션만 남기고 싶다면 `-j SECTION`으로 명시해야 한다. 반대로 모든 섹션을 억지로 코드처럼 보고 싶다면 `-D`(전체 디스어셈블, 데이터 섹션 포함)를 쓸 수 있는데 이 경우 데이터가 의미 없는 명령어로 오역될 수 있다.

### 점프 테이블/데이터가 코드 사이에 섞여 선형 디스어셈블이 깨진다
컴파일러는 `switch`문을 점프 테이블(주소 배열)로 최적화하는 경우가 많은데, 이 테이블이 `.text` 섹션 한가운데에 데이터로 박혀 있을 수 있다. objdump는 흐름을 따라가는 게 아니라 주소 순서대로 바이트를 처음부터 끝까지 기계어로 해석하는 **선형 디스어셈블러**이기 때문에, 이 데이터 구간을 명령어로 잘못 해석해 이상한 옵코드나 `(bad)`를 뱉고 그 다음 줄부터 정렬이 완전히 어긋난다. 이후 진짜 코드가 나와도 바이트 경계가 밀려서 깨진 것처럼 보인다.

### 터미널/파이프로 인한 착시
`objdump -d ./chall | less` 없이 그냥 터미널에 출력하면 스크롤 버퍼 크기 때문에 앞부분이 잘려 보이거나, 반대로 `objdump -d ./chall | head`처럼 실수로 파이프를 걸어서 일부만 본 것을 "끊겼다"고 오해하는 경우도 흔하다. 이 경우는 objdump 자체 문제가 아니라 셸/파이프 사용 실수다.

## 화면/코드에서 보이는 징후
```
$ objdump -d ./chall
...
  401230:   55                      push   %rbp
  401231:   48 89 e5                mov    %rsp,%rbp
	...
```
`...` 한 줄만 출력되고 그 아래로 아무 내용도 없이 프롬프트가 바로 나오면 생략된 것이고, 반대로 옵코드가 깨진 채로 계속 이어지면 데이터-코드 혼재 문제다.

## 가장 먼저 할 것
`objdump -d ./chall > full.asm`으로 전체를 파일에 저장한 뒤 `wc -l full.asm`로 줄 수를 확인하고, `grep -n '\.\.\.$' full.asm`로 생략 표시 위치를 찾는다. 그다음 원하는 함수 이름이 파일 안에 실제로 있는지 `grep -n '<함수이름>:' full.asm`으로 확인한다.

## 단계별 절차
1. `objdump -d ./chall > full.asm`으로 표준출력이 아닌 파일에 전체 저장
2. `wc -l full.asm`로 실제 줄 수 확인 — 터미널 화면 착시인지 구분
3. `grep -n '\.\.\.$' full.asm`로 `...` 생략 지점 확인, 필요하면 `-z` 옵션으로 재실행
4. 원하는 함수가 애초에 어느 섹션에 있는지 `readelf -S ./chall`, `nm ./chall`로 확인 후 `-j .text` 등으로 섹션 명시
5. 옵코드가 깨진 구간이 있으면 그 앞뒤 주소를 `readelf`/`nm`으로 대조해 점프 테이블·데이터 구간인지 의심하고, 필요하면 IDA/Ghidra처럼 CFG 기반 디스어셈블러로 교차 확인
6. PLT 관련 함수가 안 보이면 `-d`가 아니라 `--disassemble=malloc@plt` 식으로 심볼 지정 디스어셈블도 시도

## 명령어/단축키
```bash
objdump -d ./chall > full.asm
objdump -dz ./chall            # 생략 없이 전부 출력
objdump -j .text -d ./chall    # 특정 섹션만 디스어셈블
objdump -D ./chall             # 데이터 섹션 포함 전체(오역 위험 있음)
objdump --disassemble=main ./chall
readelf -S ./chall
nm ./chall | grep ' T '
```

## 출력 해석
`...`만 있고 그 위/아래 주소 차이가 크면(예: `401300` 다음 줄이 바로 `401500`) 그 사이가 전부 0으로 채워진 패딩이라는 뜻이지 디스어셈블 실패가 아니다. 반대로 `(bad)`가 반복되거나 명령어 길이가 이상하게 짧게/길게 나오며 그 뒤로 코드가 전혀 말이 안 되면, 그 지점부터는 데이터를 코드로 잘못 해석하고 있다는 신호다.

## 흔한 실수
- `...`을 보고 "objdump가 뻗었다"고 오해하는 것 — 대부분 0 바이트 생략일 뿐이다.
- 원하는 함수가 애초에 strip되어 이름이 없거나 다른 섹션에 있는데 계속 `-d ./chall` 결과에서만 찾으려는 것.
- `| head`, `| less`를 걸어놓고 전체를 다 봤다고 착각하는 것.
- 점프 테이블 구간을 코드로 착각해 그 안의 깨진 옵코드를 실제 명령어처럼 분석하는 것.

## 막혔을 때 다음 체크
- objdump 기본 사용법 자체가 헷갈리면 → REV-0092 objdump 기본 사용법.
- 정적 링킹된 거대한 바이너리라 함수가 너무 많아서 원하는 곳을 못 찾는 것이라면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법.
- strip된 바이너리에서 함수 이름 자체가 없어서 못 찾는 것이라면 → REV-0668 strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭).

## 미니 예제
```bash
$ objdump -d ./chall | wc -l
842
$ objdump -dz ./chall | wc -l
15230
```
`-z` 없이는 842줄뿐이었는데 `-z`를 붙이자 15230줄로 늘어난 것은, 그 사이 대부분이 0으로 채워진 구간이라 생략되어 있었다는 뜻이다. 실제 코드가 사라진 게 아니라 출력 옵션 문제였다.

## 관련 글
- REV-0092 — objdump 기본 사용법
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0668 — strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- REV-0089 — ELF 헤더 읽는 법

## 출처/검증
- objdump의 `-z`/`--disassemble-zeroes` 옵션과 반복 구간 생략 동작: GNU Binutils 공식 매뉴얼(`objdump(1)`) 기준 (2026-09-09 검증).
- `SHF_EXECINSTR` 플래그와 실행 가능 섹션만 기본 디스어셈블 대상이 되는 점: ELF Specification 및 System V ABI 기준.
- 컴파일러가 switch문을 점프 테이블로 변환해 `.text` 내에 데이터가 섞이는 패턴: 일반적인 x86-64 GCC/Clang 최적화 관찰 결과(리버싱 커뮤니티 공통 지식) 기준.
