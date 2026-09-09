---
id: REV-0684
title: "Linux strings의 -e 옵션으로 와이드 문자열 찾기"
slug: "rev-0684-strings-e-option-wide-strings"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [strings, readelf]
keywords: ["strings -e", "와이드 문자열", "wide string", "UTF-16", "wchar_t", "strings 인코딩 옵션"]
aliases: ["strings로 UTF-16 찾기", "strings 와이드 캐릭터", "strings -e l", "strings singlebyte 아닌 문자열"]
symptom_keywords: ["strings 결과에 문자열이 하나도 안 보이는데 실행하면 메시지가 뜸", "UTF-16으로 저장된 문자열이 strings에서 안 보임", "wchar_t 문자열을 못 찾겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
기본 `strings`는 한 바이트(싱글바이트, ASCII/UTF-8 계열)로 인코딩된 연속된 출력 가능 문자만 찾기 때문에, 2바이트 단위(UTF-16 등)로 저장된 와이드 문자열은 그대로 놓치며, 이때는 `strings -e {s,S,b,l,B,L}` 옵션으로 인코딩과 엔디안을 지정해줘야 문자열이 제대로 추출된다.

## 언제 검색해야 하나
- 바이너리를 실행하면 분명 어떤 메시지/문자열이 화면에 출력되는데, `strings ./chall`에는 그 문자열이 전혀 안 보일 때
- Windows용으로 만들어졌다가 Wine/크로스컴파일된 바이너리나, `wchar_t` 기반 문자열 처리 라이브러리를 쓰는 리눅스 바이너리를 분석 중일 때
- `.rodata` 섹션을 IDA/Ghidra/hexdump로 직접 봤더니 각 문자 사이에 `00` 바이트가 규칙적으로 끼어있는 패턴(`4800 4900 ...`처럼)이 보일 때
- 문자열이 리틀엔디안/빅엔디안 중 어느 쪽으로 저장됐는지 확신이 안 서서 둘 다 시도해봐야 할 때

## 핵심 개념

### 기본 strings가 놓치는 것
`strings`의 기본 동작은 파일을 바이트 스트림으로 훑으면서, 출력 가능한(printable) 문자가 일정 길이(기본 4바이트) 이상 연속되면 그것을 하나의 문자열로 뽑아내는 것이다(REV-0094 참고). 이 기본 동작은 ASCII/UTF-8처럼 "문자 하나 = 대부분 1바이트"인 인코딩에는 잘 맞지만, `wchar_t`(리눅스에서 보통 4바이트) 또는 UTF-16(Windows `WCHAR`, 2바이트) 문자열은 각 문자 사이에 `0x00` 같은 널 바이트가 끼어 있어서, 기본 모드로 보면 널 바이트 직전까지의 단 한 글자만 "연속된 출력 가능 문자"로 인식되고 나머지는 다 끊겨버린다. 결과적으로 진짜 문자열이 있는데도 `strings` 출력에 거의 안 잡히거나, 의미 없는 한두 글자짜리 조각들만 나온다.

### `-e` 옵션의 의미
GNU binutils `strings`는 `-e ENCODING` 옵션으로 문자 하나가 차지하는 바이트 수와 엔디안을 지정할 수 있다.
```text
-e s   싱글바이트(기본값, 7비트 ASCII 위주)
-e S   싱글바이트, 8비트까지 포함(확장 ASCII)
-e b   16비트 빅엔디안(2바이트, big-endian)
-e l   16비트 리틀엔디안(2바이트, little-endian) — Windows UTF-16LE(WCHAR)에 해당
-e B   32비트 빅엔디안(4바이트)
-e L   32비트 리틀엔디안(4바이트) — 리눅스 glibc의 wchar_t(4바이트, 리틀엔디안 시스템 기준)에 해당
```
소문자(`s`, `b`, `l`)는 7비트 문자, 대문자(`S`, `B`, `L`)는 8비트까지 포함해서 조금 더 넓게 인식한다는 차이가 있다(정확한 바이트 폭은 `b`/`l`이 2바이트, `B`/`L`이 4바이트로 대소문자와 무관하게 고정이며, 대소문자 차이는 문자 판정 기준의 비트 폭 차이다).

### 어떤 옵션을 언제 쓰나
- 리눅스 x86-64 네이티브 바이너리에서 `wchar_t` 문자열(예: `wprintf`, `wcscpy` 사용 코드)을 찾을 때: `strings -e L ./chall` (4바이트, 리틀엔디안)
- Windows PE를 크로스 분석하거나 Wine 환경, 혹은 UTF-16LE로 저장된 데이터를 리눅스 도구로 볼 때: `strings -e l ./file.exe` (2바이트, 리틀엔디안) — Windows의 `WCHAR`/UTF-16LE와 정확히 맞는 옵션
- 엔디안을 확신할 수 없을 때: `-e l`과 `-e b`(또는 `-e L`/`-e B`)를 모두 시도해보고 의미 있는 문자열이 나오는 쪽을 채택

### 기본 strings와 결과를 나란히 비교하는 습관
`-e` 옵션 없는 기본 `strings` 결과와 `-e l`/`-e L` 결과를 각각 파일로 뽑아 `diff` 또는 나란히 살펴보면, 어떤 인코딩으로 저장된 문자열이 이 바이너리에 있는지 빠르게 감을 잡을 수 있다. 두 결과 모두 의미 있는 문자열이 거의 없다면 문자열 자체가 암호화/난독화되어 있을 가능성도 고려해야 한다.

## 화면/코드에서 보이는 징후
- `strings ./chall` 결과가 유난히 빈약한데, `objdump -s -j .rodata ./chall` 또는 hex 에디터로 본 `.rodata`에는 분명 텍스트처럼 보이는 바이트열이 있음
- hexdump에서 `48 00 65 00 6c 00 6c 00 6f 00`처럼 각 문자 바이트 사이에 `00`이 규칙적으로 반복
- 프로그램 실행 시 나오는 출력 메시지를 `strings` grep으로 찾을 수 없음

## 가장 먼저 할 것
`strings ./chall`을 인코딩 옵션 없이 한 번 돌려보고, 기대한 문자열이 안 보이면 곧바로 `strings -e l ./chall`과 `strings -e L ./chall`을 각각 시도해본다.

## 단계별 절차
1. 기본 `strings ./chall`로 1차 확인
2. 원하는 문자열이 안 보이면 `.rodata`/`.data` 섹션을 hex로 직접 열어 바이트 사이 패턴(00이 규칙적으로 끼는지) 확인
   ```bash
   objdump -s -j .rodata ./chall | head -30
   ```
3. 패턴이 2바이트 간격이면 `strings -e l ./chall`(리틀엔디안 우선 시도), 필요하면 `-e b`도 시도
4. 패턴이 4바이트 간격이면 `strings -e L ./chall`(리틀엔디안), 필요하면 `-e B`도 시도
5. 원하는 문자열을 찾았으면 그 문자열의 오프셋을 `strings -e L -t x ./chall`(주소 포함 출력)로 확인해서 IDA/Ghidra에서 xref를 따라간다

## 명령어/단축키
```bash
strings ./chall
strings -e l ./chall     # UTF-16LE / WCHAR
strings -e b ./chall     # UTF-16BE
strings -e L ./chall     # wchar_t(4바이트) 리틀엔디안
strings -e B ./chall     # 4바이트 빅엔디안
strings -e L -t x ./chall   # 주소(오프셋) 함께 출력
```

## 출력 해석
`strings -e L -t x ./chall` 결과 예:
```
     1a20 Access Denied
     1a40 Welcome
```
왼쪽 숫자는 해당 문자열이 파일 안에서 시작하는 오프셋(16진수)이다. 이 오프셋을 IDA/Ghidra에서 `.rodata` 뷰의 같은 주소로 찾아가면, 그 문자열을 참조하는 코드(xref)를 바로 추적할 수 있다. 인코딩 옵션이 실제 저장 방식과 안 맞으면 이 출력 자체가 텅 비거나 의미 없는 한두 글자만 나오므로, 결과가 비었다고 "문자열이 없다"고 단정하지 말고 다른 `-e` 옵션도 시도해봐야 한다.

## 흔한 실수
- `strings` 결과가 비었다고 바로 "문자열이 암호화됐다"고 단정하는 것 — 와이드 문자열일 가능성을 먼저 배제해야 한다.
- 엔디안을 반대로 지정해서(`-e b`를 써야 할 자리에 `-e l`을 쓰는 등) 여전히 문자열이 안 보이는데 옵션 자체를 포기하는 것 — 리틀/빅 두 가지를 모두 시도하는 습관이 필요하다.
- 2바이트(`-e l`)와 4바이트(`-e L`) 폭을 혼동해서 UTF-16 문자열에 4바이트 옵션을 쓰거나 그 반대로 쓰는 것 — Windows 문자열은 거의 항상 2바이트(UTF-16LE), 리눅스 네이티브 `wchar_t`는 4바이트라는 기본 원칙을 기억해두면 시행착오를 줄인다.
- `-e` 옵션이 유효한 문자를 판정하는 최소 길이 기준(`-n` 옵션과 함께 조정 가능)을 모른 채 짧은 와이드 문자열이 필터링되는 것을 눈치채지 못하는 것 — 필요하면 `-n 2`처럼 최소 길이를 낮춰서 재시도한다.

## 막혔을 때 다음 체크
- `strings`의 기본 사용법과 다른 옵션(`-n`, `-a` 등)이 궁금하면 → REV-0094 strings로 빠르게 단서 찾기
- 문자열 인코딩 자체(멀티바이트, UTF-8/UTF-16 개념)가 헷갈리면 → REV-0036 문자열이 메모리에 저장되는 방식 ASCII UTF-8 UTF-16 (binary-basics 카테고리)

## 미니 예제
```bash
$ strings ./chall | grep -i welcome
(아무 결과 없음)

$ objdump -s -j .rodata ./chall | head -5
Contents of section .rodata:
 2000 00000000 57006500 6c006300 6f006d00  ....W.e.l.c.o.m.
 2010 65000000 00000000                    e.......

$ strings -e l ./chall | grep -i welcome
Welcome
```
기본 `strings`는 문자 사이 `00` 바이트 때문에 아무것도 못 찾았지만, hexdump로 2바이트 간격 패턴(`57 00 65 00 6c 00 ...` = UTF-16LE의 `W e l c o m e`)을 확인한 뒤 `-e l` 옵션을 쓰자 정확히 `Welcome`이 추출됐다.

## 관련 글
- REV-0094 — strings로 빠르게 단서 찾기

## 출처/검증
- GNU binutils `strings` 명령의 `-e` 옵션(`s`, `S`, `b`, `l`, `B`, `L` 인코딩 지정)과 각 값의 바이트 폭/엔디안 의미: GNU Binutils 공식 매뉴얼(`strings(1)`) 기준.
- Windows `WCHAR`(UTF-16LE, 2바이트)와 리눅스 glibc `wchar_t`(4바이트, 리틀엔디안 아키텍처 기준)의 크기 차이: glibc 공식 문서 및 각 플랫폼 ABI 문서 기준 (2026-09-09 검증).
