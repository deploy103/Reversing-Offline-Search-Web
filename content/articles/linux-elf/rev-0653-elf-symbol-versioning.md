---
id: REV-0653
title: "ELF Symbol Versioning(GLIBC_2.x) 이해하기"
slug: "rev-0653-elf-symbol-versioning"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [readelf, objdump, GDB]
keywords: ["symbol versioning", "GLIBC_2.x", ".gnu.version", "versym", "verneed", "verdef", "심볼 버저닝"]
aliases: ["GLIBC_2.2.5란", "readelf 심볼에 붙은 @@GLIBC", "objdump에 나오는 @GLIBC_2.34", "symbol version 뜻"]
symptom_keywords: ["objdump 심볼 이름 뒤에 @@GLIBC_2.2.5가 붙어있음", "printf@GLIBC_2.2.5가 뭔지 모르겠음", "같은 함수 이름인데 버전이 다르게 두 개 보임", "readelf --dyn-syms에 이상한 버전 문자열이 나옴"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
동적 링킹된 ELF 바이너리의 심볼 이름 뒤에 붙는 `@GLIBC_2.2.5` 같은 문자열은 "이 심볼이 glibc의 몇 버전에서 정의된 ABI인지"를 나타내는 심볼 버저닝(symbol versioning) 정보이며, 이걸 이해하면 같은 이름의 함수가 왜 두 개씩 보이는지, 그리고 바이너리가 어느 glibc 버전 이상을 요구하는지를 정확히 읽어낼 수 있다.

## 언제 검색해야 하나
- `objdump -T` 또는 `readelf --dyn-syms` 출력에서 함수 이름 뒤에 `@GLIBC_2.2.5`, `@@GLIBC_2.34` 같은 문자열이 붙어 있어서 이게 뭔지 궁금할 때
- `nm -D`로 봤을 때 `memcpy`가 `memcpy@GLIBC_2.2.5`와 `memcpy@GLIBC_2.14`처럼 버전이 다른 두 개로 보여서 혼란스러울 때
- 바이너리를 다른 리눅스 배포판에서 실행했더니 `version 'GLIBC_2.34' not found` 에러가 나서 원인을 알고 싶을 때
- IDA/Ghidra에서 import된 함수 이름에 이상한 버전 접미사가 붙어 있어서 실제 함수 이름만 보고 싶을 때

## 핵심 개념

### 심볼 버저닝이 왜 필요한가
glibc는 시간이 지나며 같은 이름의 함수라도 ABI(인자 전달 방식, 반환값 구조, 내부 동작)를 바꿔야 할 때가 있다. 예를 들어 `memcpy`는 오래전에는 `src`와 `dst` 메모리 영역이 겹쳐도(overlap) 동작하도록 구현되어 있었는데, 이후 최적화 버전에서는 겹치는 경우의 동작이 달라졌다. 문제는 이미 옛날 glibc를 기준으로 컴파일되어 배포된 수많은 바이너리가 "옛날 동작"에 의존하고 있다는 점이다. glibc가 새 버전으로 업그레이드될 때 이 옛날 바이너리들이 갑자기 깨지면 안 되므로, glibc는 **같은 이름의 함수를 여러 버전으로 동시에 유지**하는 방법을 쓴다. 이것이 심볼 버저닝이다. 링커는 컴파일 시점의 glibc 헤더/버전 스크립트를 기준으로 "이 바이너리는 `memcpy`의 어느 버전을 써야 하는지"를 실행 파일 안에 기록해 두고, 런타임에 동적 로더(`ld.so`)가 정확히 그 버전의 구현을 연결해준다.

### 버전 이름의 형태 — `GLIBC_x.y`
버전 이름은 보통 `GLIBC_2.2.5`, `GLIBC_2.34`처럼 glibc가 그 함수(또는 ABI)를 도입하거나 변경한 시점의 glibc 릴리스 번호를 딴 이름이다. 숫자가 클수록 더 최근에 도입된 버전이라는 뜻이며, "이 실행 파일을 돌리려면 시스템에 최소 이 버전 이상의 glibc가 있어야 한다"는 최소 요구사항으로 해석하면 된다. `GLIBC_PRIVATE`처럼 glibc 내부 전용으로 예약된 특수 버전 이름도 있는데, 이는 외부에서 직접 링크해서 쓰라고 만든 것이 아니라 glibc 내부 함수들끼리만 참조하는 용도다.

### `@`와 `@@`의 차이 — 참조 vs 정의
`objdump -T`, `nm -D` 출력에서 `@`(단일 골뱅이)와 `@@`(이중 골뱅이)는 의미가 다르다.
- `printf@GLIBC_2.2.5` — 단일 `@`는 **이 심볼을 참조(reference)한다**는 뜻이다. 즉 "나는 이 버전의 printf를 써야 한다"는 요청이며, 주로 실행 파일이나 공유 라이브러리가 외부(예: `libc.so.6`) 함수를 가져다 쓸 때 이 표기가 붙는다.
- `printf@@GLIBC_2.2.5`는 이중 `@@`로, **이 심볼을 정의(definition)하는 쪽에서, 그리고 그 버전이 "기본(default) 버전"이라는 뜻**이다. 예를 들어 `libc.so.6` 자체를 `readelf --dyn-syms`로 보면 `memcpy@@GLIBC_2.14`처럼 이중 `@@`가 붙는데, 이는 "이 라이브러리가 제공하는 `memcpy` 심볼 중 기본으로 링크되는 버전이 `GLIBC_2.14`"라는 의미다. 같은 라이브러리 안에 `memcpy@GLIBC_2.2.5`(단일 `@`, 구버전 호환용, 기본 아님)도 함께 존재할 수 있다.

간단히 말해: 실행 파일 쪽에서 보이는 것은 대부분 "요청"(`@`)이고, `libc.so.6` 같은 라이브러리 쪽에서 보이는 것은 "제공"(`@@`가 기본, `@`는 비기본 구버전 호환 버전)이다.

### ELF 안에서 이 정보가 저장되는 위치
심볼 버저닝은 몇 개의 전용 섹션에 나뉘어 저장된다.
- `.gnu.version` (섹션 타입 `SHT_GNU_versym`): `.dynsym`의 각 심볼 항목과 1대1로 대응하는 16비트 정수 배열이다. 각 값은 "이 심볼이 어느 버전 정의/요구사항을 가리키는지"를 나타내는 인덱스다.
- `.gnu.version_d` (`SHT_GNU_verdef`, version definition): **자기 자신이 제공(정의)하는** 버전 목록. 주로 `libc.so.6`처럼 심볼을 export하는 공유 라이브러리에 존재한다.
- `.gnu.version_r` (`SHT_GNU_verneed`, version needed): **자신이 외부에서 참조(요구)하는** 버전 목록. 주로 일반 실행 파일이나 다른 공유 라이브러리를 링크해 쓰는 바이너리에 존재하며, "나는 `libc.so.6`의 `GLIBC_2.2.5` 버전 `printf`가 필요하다"는 요구사항을 담는다.

즉 요구하는 쪽(`verneed`)과 제공하는 쪽(`verdef`)이 나뉘어 있고, `.gnu.version` 배열이 실제 각 심볼을 그중 어느 항목과 연결할지 인덱스로 지정하는 구조다.

### 런타임에 무슨 일이 일어나나
프로그램이 실행되면 동적 로더(`ld-linux.so`, REV-0649)가 `libc.so.6`을 매핑하면서, 실행 파일의 `verneed` 목록에 있는 각 버전 요구사항이 `libc.so.6`의 `verdef` 목록에 실제로 존재하는지 확인한다. 존재하면 정상적으로 심볼을 연결(binding)한다. 만약 시스템에 설치된 `libc.so.6`이 그 버전을 아직 제공하지 않을 만큼 오래된 것이라면(예: 바이너리는 `GLIBC_2.34`를 요구하는데 시스템 glibc는 `2.31`까지만 있는 경우), 실행 시점에 다음과 같은 에러로 즉시 실패한다.

```
./chall: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.34' not found (required by ./chall)
```

이 에러는 CTF 환경에서 "로컬에서는 되는데 원격 서버에서는 안 된다"의 아주 흔한 원인 중 하나다. 원격 서버의 glibc가 로컬보다 오래되었을 때 발생한다.

## 화면/코드에서 보이는 징후
- `objdump -T ./libc.so.6` 또는 `readelf --dyn-syms ./chall` 출력의 함수 이름 뒤에 `@GLIBC_2.x` 또는 `@@GLIBC_2.x`가 붙어 나옴
- `nm -D ./libc.so.6 | grep memcpy`를 치면 같은 이름의 심볼이 서로 다른 버전 접미사로 두 줄 이상 나옴
- 프로그램 실행 시 `version 'GLIBC_2.xx' not found` 에러로 즉시 종료됨
- IDA/Ghidra Import 목록에서 함수 이름이 `printf`가 아니라 `printf_GLIBC_2_2_5`처럼 버전이 이름에 섞여 표시됨(툴에 따라 표시 방식이 다름)

## 가장 먼저 할 것
`readelf -V ./chall` (또는 `./libc.so.6`)를 먼저 실행해서 이 바이너리/라이브러리가 어떤 버전 정의(`verdef`)를 제공하고 어떤 버전 요구사항(`verneed`)을 갖고 있는지 한눈에 확인한다. 특정 함수 하나만 궁금하면 `objdump -T`에 `grep`을 걸어 그 함수의 버전 접미사만 뽑아본다.

## 단계별 절차
1. `file ./chall`로 동적 링킹 바이너리인지 확인 (정적 링킹이면 symbol versioning 자체가 의미 없다 — REV-0646 참고)
2. `readelf -V ./chall`로 `.gnu.version_r`(요구하는 버전 목록) 확인
3. 특정 함수의 요구 버전이 궁금하면:
   ```bash
   objdump -T ./chall | grep printf
   ```
4. 시스템 glibc가 그 버전을 제공하는지 확인:
   ```bash
   readelf -V /lib/x86_64-linux-gnu/libc.so.6 | grep -A2 "Version definition"
   ```
5. 원격 서버용으로 다른 glibc를 강제로 쓰고 싶다면(예: pwntools 문제 풀이), `patchelf --set-interpreter`와 `LD_LIBRARY_PATH`로 원하는 버전의 `ld.so`/`libc.so.6` 조합을 지정해 실행하는 방법도 있다(REV-0651 참고).
6. 같은 이름인데 버전이 다른 두 심볼 중 실제로 바이너리가 어떤 것에 바인딩되었는지 궁금하면 GDB로 실제 호출 주소를 확인한다:
   ```gdb
   break printf
   run
   info symbol $pc
   ```

## 명령어/단축키
```bash
readelf -V ./chall                 # 버전 정의/요구사항 전체 출력
readelf --dyn-syms ./chall          # 버전 접미사가 포함된 동적 심볼 테이블
objdump -T ./chall                  # 동적 심볼 + 버전 접미사
nm -D ./libc.so.6 | grep FUNCNAME   # 특정 함수의 모든 버전 나열
```

## 출력 해석
`readelf -V ./chall` 예시 중 요구사항(verneed) 부분:
```
Version needs section '.gnu.version_r' contains 2 entries:
 Addr: 0x0000000000000598  Offset: 0x000598  Link: 4 (.dynstr)
  000000: Version: 1  File: libc.so.6  Cnt: 2
  0x0010:   Name: GLIBC_2.34  Flags: none  Version: 3
  0x0020:   Name: GLIBC_2.2.5  Flags: none  Version: 2
```
`File: libc.so.6`은 이 요구사항이 어느 공유 라이브러리를 대상으로 하는지, `Name: GLIBC_2.34`는 필요한 최소 버전, `Version: 3`은 `.gnu.version` 배열에서 이 요구사항을 가리킬 때 쓰이는 내부 인덱스 번호다. 즉 이 실행 파일은 `libc.so.6`에서 `GLIBC_2.34`와 `GLIBC_2.2.5` 두 가지 버전 그룹의 심볼을 섞어서 쓴다는 뜻이며, 실행하려면 시스템 glibc가 최소한 `2.34`까지는 지원해야 한다.

`objdump -T ./libc.so.6 | grep " memcpy"` 예시:
```
0000000000101d70 g    DF .text  0000000000000024  GLIBC_2.14  memcpy
0000000000101d90 w   DF .text  0000000000000024  GLIBC_2.2.5 memcpy
```
`g`(global)와 `w`(weak)는 심볼 바인딩(REV-0639)이고, 뒤의 `GLIBC_2.14`/`GLIBC_2.2.5`가 버전이다. 이렇게 같은 함수 이름이 두 줄 나오는 것은 오류가 아니라 "구버전 호환용 구현"과 "현재 기본 구현"이 공존하고 있다는 정상적인 모습이다.

## 흔한 실수
- `@GLIBC_2.34` 같은 접미사를 함수 이름의 일부라고 착각해서, IDA에서 `printf_2_2_5`라는 완전히 다른 함수를 찾는 것처럼 헷갈리는 것 — 실제로는 그냥 `printf`이고 뒤는 버전 태그일 뿐이다.
- `@`(단일)과 `@@`(이중)의 의미 차이를 몰라서, 라이브러리 쪽 출력과 실행 파일 쪽 출력을 같은 의미로 읽어버리는 것.
- "버전 번호가 다르다 = 함수 동작이 완전히 다르다"로 오해하는 것. 대부분의 경우 동작 차이는 미묘하지만(예: 겹치는 메모리 처리, 로케일 처리 방식), 시그니처(인자 개수/타입)까지 달라지는 경우는 드물다 — 시그니처 자체가 다른 사례가 궁금하면 REV-0648을 참고한다.
- `version 'GLIBC_2.xx' not found` 에러를 보고 "라이브러리가 아예 없다"고 오해해서 `ldd` 결과만 보고 삽질하는 것 — 실제로는 라이브러리는 있지만 버전이 요구사항보다 낮은 것이 원인이다. `ldd`는 파일 존재 여부만 보여주고 버전 충돌은 실행 시점 에러로만 드러난다.

## 막혔을 때 다음 체크
- 애초에 동적 링킹/정적 링킹 구분이 헷갈리면 → REV-0101 Dynamic Linking과 Import 함수 추적, REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- 같은 함수인데 glibc 버전마다 인자나 동작이 바뀌는 구체적 사례가 궁금하면 → REV-0648 glibc 버전별 함수 시그니처 차이 확인법
- ELF 심볼의 WEAK/GLOBAL/LOCAL 바인딩 자체가 헷갈리면 → REV-0639 ELF 심볼 바인딩(WEAK/GLOBAL/LOCAL) 빠른 참조
- 동적 로더가 라이브러리를 찾는 순서/경로가 궁금하면 → REV-0651 LD_LIBRARY_PATH와 라이브러리 탐색 순서
- glibc 버전이 안 맞아서 원격 서버 전용 libc로 강제 실행하고 싶다면 → REV-0711 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때

## 미니 예제
```bash
$ readelf -V ./chall | grep -A4 "Version needs"
Version needs section '.gnu.version_r' contains 1 entries:
 Addr: 0x00000000000005f8  Offset: 0x0005f8  Link: 5 (.dynstr)
  000000: Version: 1  File: libc.so.6  Cnt: 1
  0x0010:   Name: GLIBC_2.34  Flags: none  Version: 2

$ ldd ./chall
    linux-vdso.so.1 (0x00007ffd...)
    libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f...)

$ readelf -V /lib/x86_64-linux-gnu/libc.so.6 | grep "Name: GLIBC_2.34"
  0x00d0: Name: GLIBC_2.34
```
이 예시에서는 `chall`이 `GLIBC_2.34` 심볼을 요구하고, 시스템 `libc.so.6`도 `GLIBC_2.34`를 실제로 제공(`verdef`에 존재)하므로 정상 실행된다. 만약 마지막 명령의 `grep` 결과가 비어 있다면(그 버전 문자열이 안 나온다면), 이 시스템의 glibc는 `chall`이 요구하는 최소 버전보다 낮은 것이므로 실행 시 `version not found` 에러가 날 것이라고 미리 예측할 수 있다.

## 관련 글
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0648 — glibc 버전별 함수 시그니처 차이 확인법
- REV-0639 — ELF 심볼 바인딩(WEAK/GLOBAL/LOCAL) 빠른 참조
- REV-0651 — LD_LIBRARY_PATH와 라이브러리 탐색 순서
- REV-0649 — ELF Interpreter(ld-linux.so)가 하는 일

## 출처/검증
- `.gnu.version`/`.gnu.version_d`/`.gnu.version_r` 섹션 구조와 `SHT_GNU_versym`/`SHT_GNU_verdef`/`SHT_GNU_verneed` 타입: System V ABI 및 GNU 확장 문서, `elf(5)` 매뉴얼 페이지 기준.
- `@`(참조) vs `@@`(기본 정의) 표기 규약: GNU binutils `objdump`/`readelf` 공식 문서 및 GNU ld 버전 스크립트(version script) 문서 기준.
- `version 'GLIBC_x.y' not found` 런타임 에러 메시지 형식: 실제 glibc 동적 로더(`ld.so`) 동작 확인 (2026-09-09 검증).
