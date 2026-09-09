---
id: REV-0668
title: "strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)"
slug: "rev-0668-stripped-static-libc-signature-matching"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, readelf, objdump]
keywords: ["FLIRT", "시그니처 매칭", "signature matching", "strip된 정적 바이너리", "Function ID", "libc 함수 식별"]
aliases: ["strip 정적 바이너리 함수 식별", "FLIRT 시그니처", "IDA FLIRT", "Ghidra Function ID"]
symptom_keywords: ["strip된 정적 바이너리라 함수 이름이 다 sub_로 나옴", "nm이 no symbols라고 나옴", "정적 바이너리인데 어떤 함수가 malloc인지 모르겠음", "IDA에서 함수가 전부 무명 함수임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
strip된 정적 바이너리는 `nm`/`readelf -s`로 이름을 얻을 수 없지만, glibc 함수들은 컴파일러 버전과 최적화 옵션이 같으면 명령어 바이트 시퀀스가 거의 그대로 반복되기 때문에, IDA의 FLIRT나 Ghidra의 Function ID 같은 "시그니처 매칭" 기능으로 바이트 패턴을 알려진 libc 함수 목록과 대조해 함수 이름을 자동으로 복원할 수 있다.

## 언제 검색해야 하나
- `file ./chall` 결과에 `statically linked, stripped`가 같이 보일 때
- `nm ./chall` 결과가 `nm: ./chall: no symbols`로 나와서 함수 이름을 하나도 알 수 없을 때
- IDA/Ghidra에서 함수가 전부 `sub_401xxx` 형태의 무명 함수로만 나오는데, 그중 어떤 게 `malloc`이고 어떤 게 `printf`인지 구분해야 할 때

## 핵심 개념

### 왜 바이트 패턴 매칭이 가능한가
같은 glibc 소스 코드를 같은 컴파일러(GCC 특정 버전), 같은 최적화 옵션(`-O2` 등)으로 컴파일하면 함수 내부의 명령어 바이트 시퀀스가 거의 동일하게 나온다. 차이가 나는 부분은 대개 상대 주소를 담은 오퍼랜드(`call`, `jmp`, `lea`의 대상 주소, 재배치되는 부분)뿐이다. 시그니처 매칭 도구는 이런 "가변 바이트"를 와일드카드로 마스킹한 뒤, 나머지 고정 바이트들의 체크섬(또는 패턴)을 미리 계산해둔 데이터베이스와 대조하는 방식으로 동작한다.

### IDA FLIRT (Fast Library Identification and Recognition Technology)
IDA의 대표적인 시그니처 매칭 기능으로, `.sig`/`.pat` 형식의 시그니처 파일을 사용한다. IDA는 분석 시작 시 컴파일러/라이브러리 조합에 맞는 시그니처 파일을 자동 적용하거나, `File → Load file → FLIRT signature file...`로 수동 적용할 수 있다. glibc 정적 라이브러리(`libc.a`)에서 직접 시그니처를 뽑아주는 `pcf`/`sigmake` 같은 IDA SDK 도구도 존재하며, CTF 커뮤니티에서 자주 쓰이는 glibc 버전별 FLIRT 시그니처 모음이 공개되어 있기도 하다.

### Ghidra Function ID (FID)
Ghidra는 FLIRT와 비슷한 목적의 "Function ID" 프레임워크를 내장하고 있다. `libc.a`, `libgcc.a` 등에서 함수 바이트 해시를 뽑아 FID 데이터베이스를 만들고(`Function ID → Create New Empty Function ID Database`, `Populate Function ID Database`), 분석 시 `Analysis → Auto Analyze → Function ID`를 켜면 일치하는 함수에 자동으로 이름이 붙는다. Ghidra 배포판에는 일부 표준 라이브러리용 FID 데이터베이스가 기본 포함되어 있다.

### 시그니처가 없거나 안 맞을 때의 수동 식별
컴파일러/glibc 버전이 시그니처 DB와 다르면 자동 매칭이 실패할 수 있다. 이때는 몇 가지 수동 단서를 쓴다.
- **`.rodata`의 에러 메시지 문자열**: glibc는 내부적으로 `"malloc(): invalid size"`, `"free(): double free detected"` 같은 고정 문자열을 갖고 있어, `strings ./chall`로 이런 문구를 찾으면 근처 함수가 `malloc`/`free` 계열임을 추정할 수 있다.
- **`__libc_csu_init`/`__libc_start_main` 특유의 프롤로그 패턴**: `__libc_start_main`은 `argc`, `argv`를 받아 `main`을 호출하는 고정된 호출 구조를 가지므로, `_start`(REV-0098)에서 바로 이어지는 큰 함수를 보면 식별 가능하다.
- **`.comment` 섹션**: `readelf -p .comment ./chall`로 GCC/Clang 버전 문자열이 남아있는지 확인하면, 어느 버전의 FLIRT/FID 시그니처를 써야 할지 힌트가 된다.
- **호출 그래프 위치**: `main`에서 직접 호출되는 함수가 인자 개수/패턴상 `scanf`류로 보이면(REV-0109), 근처의 다른 무명 함수들과 비교해 라이브러리 함수 군집을 추정할 수 있다.

### Diaphora / BinDiff — 같은 문제 다른 문제 사이의 심볼 이식
같은 CTF 시리즈에서 심볼이 살아있는 유사 바이너리(같은 spec으로 컴파일된 버전)를 구했다면, Diaphora나 BinDiff 같은 바이너리 비교 도구로 함수를 매칭시켜 이름을 그대로 옮겨올 수도 있다. 이는 FLIRT/FID가 실패했을 때 실전에서 자주 쓰이는 우회법이다.

## 화면/코드에서 보이는 징후
```
$ file ./chall
./chall: ELF 64-bit LSB executable, x86-64, ... statically linked, stripped
$ nm ./chall
nm: ./chall: no symbols
```
IDA/Ghidra를 열면 Functions 창에 `sub_401000`, `sub_401230`, ... 처럼 이름 없는 함수만 수천 개 나열된다.

## 가장 먼저 할 것
```bash
file ./chall
readelf -p .comment ./chall
strings ./chall | grep -iE "malloc|free|glibc|GNU C Library"
```
컴파일러/glibc 버전 힌트를 먼저 확보한 뒤, IDA/Ghidra에서 해당 버전에 맞는 FLIRT/FID 시그니처를 적용해본다.

## 단계별 절차

**1) 버전 힌트 수집**
```bash
readelf -p .comment ./chall
strings ./chall | grep "GNU C Library"
```

**2) IDA FLIRT 적용**
- `File → Load file → FLIRT signature file...`에서 glibc/libc 관련 `.sig` 선택
- 자동 인식이 안 되면 `libc.a`가 있는 유사 환경(같은 배포판 Docker 이미지 등)에서 직접 시그니처를 생성

**3) Ghidra Function ID 적용**
- `File → Configure → Function ID` 활성화 확인
- `Analysis → Auto Analyze` 재실행, 또는 이미 분석된 바이너리라면 `Function ID → Apply FID Database`

**4) 자동 매칭 후에도 남는 함수는 수동 대조**
- `main` 호출 직후의 함수 인자 개수, 반환값 사용 패턴을 REV-0106(SysV AMD64 Calling Convention) 기준으로 추정
- `.rodata` 문자열 xref로 어떤 함수가 어떤 에러 메시지를 참조하는지 REV-0165(constant-search류 접근)로 좁히기

**5) 결과를 GDB에서 검증**
시그니처로 "이 주소가 `malloc`일 것"이라 추정했다면, GDB로 실행 중 힙 동작을 관찰해 실제로 청크가 할당되는지 REV-0659/Pwndbg 힙 명령으로 교차 검증한다.

## 명령어/단축키
```bash
file ./chall
nm ./chall
readelf -p .comment ./chall
strings ./chall | grep -i "GNU C Library"
```
(IDA/Ghidra 쪽은 GUI 메뉴 조작이라 별도 CLI 명령은 없다. IDA는 `File → Load file → FLIRT signature file...`, Ghidra는 `Function ID` 메뉴를 사용한다.)

## 출력 해석
```
$ readelf -p .comment ./chall

String dump of section '.comment':
  [     0]  GCC: (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0
```
이 문자열로 Ubuntu 22.04 + GCC 11.4.0 조합임을 알 수 있고, 같은 조합으로 빌드된 FLIRT/FID 시그니처를 구하거나 직접 만들면 매칭 성공률이 크게 올라간다.

```
$ strings ./chall | grep "GNU C Library"
GNU C Library (Ubuntu GLIBC 2.35-0ubuntu3.4) stable release version 2.35.
```
glibc 버전 2.35임을 확인했으니, 이 버전 기준 소스/심볼 오프셋을 참고해 `malloc`/`free` 등의 내부 흐름(REV-0655 glibc malloc 내부 흐름 개요)과 대조할 수 있다.

## 흔한 실수
- 시그니처 매칭 결과를 100% 신뢰하는 것 — FLIRT/FID는 확률적 매칭이라 오탐(false positive)이 있을 수 있으므로, 중요한 함수(예: 취약점이 있는 `malloc`/`free`)는 반드시 GDB로 동작을 재확인해야 한다.
- 컴파일러 버전 확인 없이 아무 시그니처나 적용하는 것 — 버전이 다르면 매칭률이 크게 떨어지고, 심하면 엉뚱한 이름이 붙는다.
- strip된 정적 바이너리를 보자마자 포기하고 처음부터 끝까지 수작업으로 어셈블리를 읽는 것 — `main`과 사용자 정의 함수만 찾으면 되는 경우가 많으므로, 문자열 xref(REV-0008)로 사용자 로직부터 먼저 좁히고 glibc 내부 함수는 필요한 만큼만 식별하는 게 효율적이다.
- Diaphora/BinDiff로 이식한 이름을 검증 없이 그대로 믿는 것 — 비교 대상 바이너리가 실제로 충분히 유사한지 먼저 확인해야 한다.

## 막혔을 때 다음 체크
- 애초에 strip이 안 된 바이너리라면 → REV-0666 nm으로 정적 바이너리에서 원하는 심볼 찾기가 훨씬 빠르다
- 디버그 정보가 일부라도 남아있는지 다시 확인 → REV-0667 ELF에서 디버그 심볼(.debug_info)이 남아있는 경우 활용하기
- glibc 내부 malloc 흐름 자체를 더 알아야 한다면 → REV-0655 glibc malloc 내부 흐름 개요
- 정적 링킹 바이너리 분석의 전체 전략이 궁금하다면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법

## 미니 예제
```bash
$ file ./chall
./chall: ELF 64-bit LSB executable, x86-64, ... statically linked, stripped

$ readelf -p .comment ./chall
String dump of section '.comment':
  [     0]  GCC: (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0

$ strings ./chall | grep "GNU C Library"
GNU C Library (Ubuntu GLIBC 2.35-0ubuntu3.4) stable release version 2.35.
```
이 두 줄만으로 "Ubuntu 22.04 + GCC 11.4.0 + glibc 2.35" 조합을 확정했고, IDA/Ghidra에 해당 버전용 FLIRT/FID 시그니처를 적용하면 수천 개의 무명 함수 중 상당수에 `malloc`, `free`, `printf` 같은 실제 이름이 자동으로 붙는다.

## 관련 글
- REV-0666 — nm으로 정적 바이너리에서 원하는 심볼 찾기
- REV-0667 — ELF에서 디버그 심볼(.debug_info)이 남아있는 경우 활용하기
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0655 — glibc malloc 내부 흐름 개요(청크 헤더 수준)
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이
- REV-0091 — readelf 기본 사용법

## 출처/검증
- FLIRT 개념 및 시그니처 파일(.sig/.pat) 동작 방식: Hex-Rays IDA 공식 문서(FLIRT technology) 기준.
- Ghidra Function ID 프레임워크 동작: Ghidra 공식 문서(Function ID Plugin) 기준.
- `.comment` 섹션에 GCC 버전 문자열이 기록되는 동작: GNU Binutils/GCC 표준 빌드 동작 기준 (2026-09-08 검증).
