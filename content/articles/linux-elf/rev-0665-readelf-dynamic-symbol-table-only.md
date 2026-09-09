---
id: REV-0665
title: "readelf로 동적 심볼 테이블만 뽑아보기"
slug: "rev-0665-readelf-dynamic-symbol-table-only"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [readelf]
keywords: ["readelf --dyn-syms", "readelf -sD", ".dynsym", "동적 심볼 테이블", "readelf 심볼 필터링"]
aliases: ["readelf 동적 심볼만 보기", ".dynsym 확인하는 법", "readelf -s 결과가 너무 많을 때", "readelf로 import 함수만 뽑기"]
symptom_keywords: ["readelf -s 결과가 너무 많아서 원하는 함수를 못 찾겠음", "동적 심볼 테이블과 정적 심볼 테이블 차이를 모르겠음", "readelf로 이 바이너리가 어떤 외부 함수를 쓰는지 빠르게 보고 싶음", "UND 심볼이 뭔지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`readelf -s ./chall`은 `.symtab`(정적 심볼 테이블)과 `.dynsym`(동적 심볼 테이블)을 둘 다 출력해 내용이 뒤섞이지만, `--dyn-syms`(또는 `-s --use-dynamic`) 옵션을 쓰면 이 바이너리가 실행 시점에 외부 라이브러리와 주고받는 심볼(가져다 쓰는 함수 = import, 내보내는 함수 = export)만 정확히 걸러서 볼 수 있다.

## 언제 검색해야 하나
- `readelf -s ./chall` 결과가 너무 길어서 이 바이너리가 실제로 외부에서 가져다 쓰는 함수만 빠르게 추려보고 싶을 때
- strip된 바이너리인데도 `printf`, `malloc` 같은 이름이 여전히 보여서 "strip이 덜 된 건가" 헷갈릴 때(동적 심볼은 strip해도 대부분 남는다)
- 공유 라이브러리(`.so`) 파일이 어떤 함수 이름을 외부에 공개(export)하는지 확인하고 싶을 때
- IDA/Ghidra 없이 터미널만으로 "이 바이너리가 어떤 API를 쓰는지" 감을 잡고 싶을 때

## 핵심 개념

### `.symtab` vs `.dynsym` — 두 개의 서로 다른 심볼 테이블
ELF 바이너리는 최대 두 종류의 심볼 테이블을 가질 수 있다.
- `.symtab`(정적 심볼 테이블, 섹션 타입 `SHT_SYMTAB`): 컴파일/링크 과정에서 생긴 모든 심볼(지역 변수, 지역 함수, 디버깅용 이름 등)을 담는다. 링킹 이후에는 실행에 필요하지 않은 정보라서, `strip` 명령으로 완전히 제거될 수 있다.
- `.dynsym`(동적 심볼 테이블, 섹션 타입 `SHT_DYNSYM`): 동적 링킹 시 반드시 필요한 심볼만 담는다. 실행 파일이 외부 공유 라이브러리에서 가져다 쓰는 함수(import), 공유 라이브러리가 외부에 공개하는 함수(export)가 여기 들어간다. **이 테이블은 런타임에 동적 로더가 실제로 참조해야 하므로, `strip` 명령으로 지워지지 않는다.** (단, `strip` 명령에 별도 옵션을 주면 지울 수도 있지만 이러면 동적 링킹 자체가 깨지므로 일반적으로는 남아있다.)

즉 "strip된 바이너리인데 왜 `printf` 이름이 여전히 보이지?"라는 의문의 답은, 그것이 `.symtab`이 아니라 `.dynsym`에 들어있는 이름이기 때문이다.

### `readelf -s`의 기본 동작 — 둘 다 출력
`readelf -s ./chall`(또는 `--syms`)는 기본적으로 존재하는 심볼 테이블을 전부 출력한다. `.symtab`이 있으면 그것을, 없으면 `.dynsym`을 보여준다. 문제는 `.symtab`이 남아있는 strip 안 된 바이너리에서는 지역 변수, 컴파일러가 생성한 내부 심볼까지 전부 섞여 나와 수백~수천 줄이 될 수 있다는 점이다.

### `--dyn-syms`로 동적 심볼만 강제 지정
```bash
readelf --dyn-syms ./chall
```
이 옵션은 `.symtab` 존재 여부와 무관하게 오직 `.dynsym` 섹션만 읽어서 보여준다. `objdump -T ./chall`도 사실상 같은 정보(동적 심볼 테이블)를 보여주는 대체 명령이다.

### `UND`(undefined) — import 함수 판별 기준
`readelf --dyn-syms` 출력의 `Ndx`(섹션 인덱스) 열에 `UND`라고 나오면, 이 심볼은 "이름은 알지만 실제 코드/데이터는 이 파일 안에 없다"는 뜻이다. 즉 **런타임에 다른 공유 라이브러리에서 가져와야 하는 import 함수**라는 뜻이다. 반대로 `Ndx`에 실제 숫자(섹션 번호)가 있으면 이 바이너리 자신이 그 심볼을 정의(export)하고 있다는 뜻이다.

```bash
readelf --dyn-syms ./chall | grep UND
```
이 한 줄로 "이 실행 파일이 외부에서 가져다 쓰는 함수 목록"만 정확히 뽑아낼 수 있다. 이는 IDA/Ghidra의 Import 창이 보여주는 것과 사실상 동일한 정보다(REV-0101 참고).

### Bind/Type 열 읽는 법
`readelf` 출력에는 `Bind`(GLOBAL/WEAK/LOCAL, REV-0639)와 `Type`(FUNC/OBJECT/NOTYPE 등) 열도 함께 나온다. `FUNC`는 함수, `OBJECT`는 전역 변수(데이터)다. `printf` 같은 함수만 보고 싶다면 `Type` 열이 `FUNC`인 것만 걸러도 좋다.

```bash
readelf --dyn-syms ./chall | grep FUNC | grep UND
```

## 화면/코드에서 보이는 징후
- `readelf -s ./chall` 결과가 수백 줄이 넘어가 스크롤이 길어짐
- `file ./chall`에 `not stripped`가 아니라 `stripped`라고 나오는데도 `printf`, `malloc` 같은 익숙한 이름이 여전히 출력에 보임
- 출력 열에 `UND`, `GLOBAL`, `FUNC` 같은 단어가 반복해서 나옴

## 가장 먼저 할 것
`readelf --dyn-syms ./chall | grep UND | grep FUNC`부터 실행해서 "이 바이너리가 실행 시 반드시 가져와야 하는 외부 함수 목록"부터 뽑아본다. 이 목록이 그 바이너리의 대략적인 기능(문자열 처리, 파일 입출력, 소켓 통신 등)을 짐작하는 가장 빠른 단서가 된다.

## 단계별 절차
1. `file ./chall`로 동적 링킹 여부 확인(정적 링킹이면 `.dynsym`이 없거나 의미가 제한적 — REV-0646 참고)
2. 전체 동적 심볼 테이블 확인:
   ```bash
   readelf --dyn-syms ./chall
   ```
3. import(외부에서 가져오는 것)만 걸러보기:
   ```bash
   readelf --dyn-syms ./chall | grep UND
   ```
4. 함수만 남기기:
   ```bash
   readelf --dyn-syms ./chall | grep UND | grep FUNC
   ```
5. 이 바이너리가 반대로 무엇을 export하는지(공유 라이브러리 분석 시 특히 중요, REV-0652 참고) 확인:
   ```bash
   readelf --dyn-syms ./chall | grep -v UND | grep FUNC
   ```
6. 특정 함수 하나의 존재 여부만 빠르게 확인:
   ```bash
   readelf --dyn-syms ./chall | grep -w system
   ```
7. 버전 정보까지 함께 보고 싶으면 REV-0653 참고해 `readelf -V ./chall`도 함께 실행

## 명령어/단축키
```bash
readelf -s ./chall                          # symtab + dynsym 모두 출력(있는 것 다)
readelf --dyn-syms ./chall                  # .dynsym만 강제 출력
readelf --dyn-syms ./chall | grep UND       # import(미정의) 심볼만
readelf --dyn-syms ./chall | grep -v UND    # export(정의된) 심볼만
objdump -T ./chall                          # readelf --dyn-syms와 동등한 대체 명령
nm -D ./chall                               # 마찬가지로 동적 심볼만 보는 대체 명령
```

## 출력 해석
```
Symbol table '.dynsym' contains 12 entries:
   Num:    Value          Size Type    Bind   Vis      Ndx Name
     0: 0000000000000000     0 NOTYPE  LOCAL  DEFAULT  UND
     1: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND printf@GLIBC_2.2.5 (2)
     2: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND strcmp@GLIBC_2.2.5 (2)
     3: 0000000000401136     0 FUNC    GLOBAL DEFAULT   13 check_password
```
- `Num 0`은 관례적으로 항상 비어있는 더미 항목(NULL 심볼)이다.
- `Num 1`, `Num 2`의 `Ndx` 열이 `UND`이므로 이 둘은 정의가 없는(import) 심볼이다. 즉 `printf`와 `strcmp`는 이 실행 파일이 `libc.so.6`에서 가져와야 하는 함수다. 이름 뒤의 `@GLIBC_2.2.5`는 REV-0653에서 다룬 심볼 버전 요구사항이다.
- `Num 3`(`check_password`)은 `Ndx`가 `13`(실제 섹션 번호, 보통 `.text`)이므로 이 바이너리 **자신이 정의**하고 있는 심볼이다. 이 항목이 `.dynsym`에 있다는 것은 이 함수가 외부에 노출(export)되어 있다는 뜻인데, 일반 실행 파일에서는 보통 흔하지 않고, 공유 라이브러리(`.so`)에서 자주 보인다.

## 흔한 실수
- `readelf -s` 결과에서 `.symtab` 항목과 `.dynsym` 항목이 섞여 나오는 것을 모르고 개수를 세거나 검색하다가 헷갈리는 것 — `--dyn-syms`로 명확히 분리해서 봐야 한다.
- `UND`를 "정의되지 않아서 쓸모없는 심볼"이라고 착각하는 것 — 실제로는 "외부에서 가져와야 할 함수"라는 정상적이고 중요한 표시다.
- strip된 바이너리에서 `.dynsym`에 남은 이름(`printf` 등)을 보고 "strip이 안 됐다"고 오판하는 것 — `.dynsym`은 동적 링킹에 필수라 일반적인 `strip`으로는 지워지지 않는다.
- 정적 링킹 바이너리에서 `readelf --dyn-syms`를 실행해 결과가 비거나 에러(`There is no dynamic section`)가 나오는데 "명령어가 잘못됐다"고 오해하는 것 — 정적 바이너리는 `.dynsym` 자체가 없는 것이 정상이다(REV-0646 참고).
- export된 심볼(`Ndx`가 UND가 아닌 경우)의 `Bind`가 `WEAK`인지 `GLOBAL`인지 구분하지 않고 넘어가는 것 — WEAK 심볼은 같은 이름의 다른 정의로 덮어써질 수 있다는 의미를 갖는다(REV-0639 참고).

## 막혔을 때 다음 체크
- import 함수 이름 뒤에 붙는 `@GLIBC_2.x` 버전 표기가 궁금하면 → REV-0653 ELF Symbol Versioning(GLIBC_2.x) 이해하기
- 심볼의 WEAK/GLOBAL/LOCAL 바인딩 의미 자체가 헷갈리면 → REV-0639 ELF 심볼 바인딩(WEAK/GLOBAL/LOCAL) 빠른 참조
- 정적 심볼 테이블(`.symtab`)에서 이름을 찾는 법이 필요하면 → REV-0093 nm으로 심볼 찾기, REV-0666 nm으로 정적 바이너리에서 원하는 심볼 찾기
- import 함수로부터 실제 동적 링킹/PLT 흐름을 더 알고 싶으면 → REV-0100 PLT와 GOT 기초, REV-0101 Dynamic Linking과 Import 함수 추적
- 공유 라이브러리(`.so`) 자체를 분석 대상으로 볼 때 export 심볼이 어떻게 쓰이는지 궁금하면 → REV-0652 공유 라이브러리(.so) 자체를 분석 대상으로 다루기

## 미니 예제
```bash
$ file ./chall
chall: ELF 64-bit LSB pie executable, x86-64, ..., dynamically linked, stripped, ...

$ readelf --dyn-syms ./chall | grep UND | grep FUNC
     3: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND printf@GLIBC_2.2.5 (2)
     4: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND fgets@GLIBC_2.2.5 (2)
     5: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND strcmp@GLIBC_2.2.5 (2)
     6: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND puts@GLIBC_2.2.5 (2)
```
`stripped`라고 나온 바이너리인데도 `.dynsym` 덕분에 이 프로그램이 `printf`, `fgets`, `strcmp`, `puts`를 쓴다는 것을 즉시 알 수 있다. 이것만으로도 "표준 입력을 받아서(fgets) 문자열을 비교(strcmp)하고 결과를 출력(printf/puts)하는 전형적인 비밀번호 확인 프로그램"이라는 감을 IDA를 열기도 전에 잡을 수 있다.

## 관련 글
- REV-0653 — ELF Symbol Versioning(GLIBC_2.x) 이해하기
- REV-0639 — ELF 심볼 바인딩(WEAK/GLOBAL/LOCAL) 빠른 참조
- REV-0093 — nm으로 심볼 찾기
- REV-0666 — nm으로 정적 바이너리에서 원하는 심볼 찾기
- REV-0100 — PLT와 GOT 기초
- REV-0101 — Dynamic Linking과 Import 함수 추적

## 출처/검증
- `.symtab`/`.dynsym` 섹션 타입(`SHT_SYMTAB`/`SHT_DYNSYM`)과 strip 시 동작 차이: System V ABI 및 `elf(5)` 매뉴얼 페이지 기준.
- `readelf --dyn-syms`, `readelf -s` 옵션 동작: GNU binutils `readelf(1)` 공식 매뉴얼 페이지 기준.
- `Ndx` 열의 `UND` 표기가 미정의 심볼(외부 참조)을 의미한다는 것: ELF 스펙의 심볼 테이블 섹션 인덱스 규약(`SHN_UNDEF`) 기준 (2026-09-09 검증).
