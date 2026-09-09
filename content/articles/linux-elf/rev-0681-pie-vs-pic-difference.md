---
id: REV-0681
title: "Position Independent Executable과 Position Independent Code 차이"
slug: "rev-0681-pie-vs-pic-difference"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [readelf, GDB, checksec]
keywords: ["PIE", "PIC", "Position Independent Executable", "Position Independent Code", "PIE와 PIC 차이", "-fPIC -fPIE"]
aliases: ["PIE PIC 차이가 뭔지", "-fPIC과 -fPIE 차이", "PIE 실행 파일이 뭔지", "PIC 코드가 뭔지"]
symptom_keywords: ["readelf -h Type이 EXEC인지 DYN인지 헷갈림", "PIE와 PIC 용어를 같은 뜻으로 쓰고 있었음", "gcc -fPIC과 -fPIE 옵션 차이를 모르겠음", "공유 라이브러리는 항상 PIC인데 실행 파일과 뭐가 다른지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
PIC(Position Independent Code)는 "어느 메모리 주소에 로드되어도 동작하도록 작성된 코드 자체의 성질"을 뜻하고, PIE(Position Independent Executable)는 "그런 PIC 코드로 만들어져서 실행 시마다 로드 주소가 바뀔 수 있는 실행 파일 형태"를 뜻하는 서로 다른 층위의 개념이며, 공유 라이브러리(`.so`)는 항상 PIC이어야 하지만 실행 파일이 PIE인지 아닌지는 컴파일 옵션과 배포판 기본 설정에 따라 달라진다.

## 언제 검색해야 하나
- `readelf -h ./chall`의 `Type` 필드가 `EXEC`인지 `DYN`인지 보고 이게 PIE와 무슨 관계인지 헷갈릴 때
- `gcc -fPIC`과 `gcc -fPIE`의 차이가 뭔지, 왜 둘 다 있는지 궁금할 때
- checksec 결과에 `PIE: PIE enabled` / `PIE: No PIE (0x400000)`가 나오는데 이게 정확히 어떤 의미인지, ASLR과는 무슨 관계인지 헷갈릴 때
- 왜 공유 라이브러리는 무조건 위치 독립적이어야 하는데 일반 실행 파일은 그렇지 않아도 되는지 원리가 궁금할 때

## 핵심 개념

### PIC — 코드 자체의 성질
PIC(Position Independent Code)는 "코드가 메모리의 어느 주소에 로드되든 수정 없이 그대로 실행 가능하다"는 코드 생성 방식이다. 이걸 가능하게 하는 핵심 기법은 절대 주소 대신 **상대 주소**(RIP-relative addressing, x86-64에서는 `lea rax, [rip+offset]` 형태)를 쓰는 것이다. 예를 들어 전역 변수나 문자열 리터럴에 접근할 때, PIC가 아닌 코드는 `mov eax, [0x404050]`처럼 고정된 절대 주소를 코드에 그대로 박아 넣지만, PIC 코드는 `mov eax, [rip+0x2f0a]`처럼 "현재 명령어 위치(RIP) 기준 상대 오프셋"으로 접근한다. 이렇게 하면 코드 전체가 다른 베이스 주소로 옮겨져도 상대 위치 관계는 그대로이므로 별도 수정 없이 동작한다.

**공유 라이브러리(`.so`)는 반드시 PIC로 컴파일되어야 한다.** 왜냈면 하나의 `.so` 파일이 동시에 여러 프로세스에서 서로 다른 메모리 주소에 매핑되어 공유(REV-0652)될 수 있어야 하기 때문이다. 만약 라이브러리 코드가 절대 주소를 하드코딩하고 있다면, 각 프로세스마다 그 주소에 실제로 매핑할 수 있다는 보장이 없어 라이브러리 공유 자체가 불가능해진다.

### PIE — 실행 파일의 형태
PIE(Position Independent Executable)는 "PIC 방식으로 만들어져서, 매번 실행될 때 로드 베이스 주소가 달라질 수 있는 실행 파일"을 말한다. 전통적인(PIE가 아닌) 실행 파일은 컴파일 시점에 고정된 베이스 주소(전형적으로 `0x400000`)에 항상 로드된다는 가정 하에 만들어진다. 반면 PIE 실행 파일은 공유 라이브러리와 마찬가지로 상대 주소 지정 방식을 쓰기 때문에, 커널이 매번 다른 임의의 베이스 주소에 로드해도 정상 동작한다. 이 "매번 다른 주소에 로드"라는 성질이 바로 ASLR(Address Space Layout Randomization, REV-0104)이 실행 파일 자체에도 적용될 수 있게 해주는 전제 조건이다.

### 컴파일 옵션의 차이 — `-fPIC` vs `-fPIE`
- `gcc -fPIC -shared -o libfoo.so foo.c`: 공유 라이브러리를 만들 때 쓰는 조합. `-fPIC`은 "이 오브젝트 코드를 PIC로 생성하라"는 컴파일러 지시자다.
- `gcc -fPIE -pie -o chall chall.c`: PIE 실행 파일을 만들 때 쓰는 조합. `-fPIE`도 내부적으로는 `-fPIC`과 거의 같은 코드 생성 방식을 쓰지만, 실행 파일 전용으로 몇 가지 최적화(예: 전역 심볼 접근에서 공유 라이브러리처럼 항상 간접 참조를 거치지 않아도 되는 경우가 있음)가 다르게 적용될 수 있다. 링크 단계에서 `-pie` 플래그가 최종적으로 ELF 헤더의 `Type`을 `DYN`으로 만든다.
- `gcc -no-pie -o chall chall.c`: PIE를 명시적으로 끈 전통적인 고정 주소 실행 파일을 만든다. ELF 헤더 `Type`은 `EXEC`가 된다.

최신 배포판(Ubuntu, Debian, Fedora 등)의 `gcc`는 대부분 기본값으로 PIE를 켜둔 상태로 배포되므로, 옵션을 아무것도 안 줘도 자동으로 PIE 실행 파일이 만들어지는 경우가 많다. CTF 문제에서 `-no-pie`를 명시하는 것은 의도적으로 ASLR 효과를 없애 문제 난이도를 낮추려는 경우가 흔하다.

### ELF 헤더 `Type` 필드로 구분하기
`readelf -h ./chall`의 `Type` 필드가 판별 기준이다.
- `Type: EXEC` — 전통적인 고정 주소 실행 파일 (PIE 아님)
- `Type: DYN` — 공유 오브젝트 형식. PIE 실행 파일과 진짜 공유 라이브러리(`.so`)가 **ELF 레벨에서는 똑같이 `DYN`으로 표시**된다. 이 둘을 구분하려면 `readelf -h`의 `Entry point address`(공유 라이브러리는 보통 진입점이 없거나 의미가 다름) 또는 `file` 명령의 출력(`file`은 내부적으로 `DYN` + 특정 플래그를 조합해 "PIE executable"인지 "shared object"인지 알려준다)을 함께 봐야 한다.

```bash
file ./chall
# chall: ELF 64-bit LSB pie executable, x86-64, ...   <- PIE 실행 파일
# 또는
# chall: ELF 64-bit LSB shared object, x86-64, ...     <- 진짜 공유 라이브러리
```

### static-PIE — 정적 링킹 + PIE의 조합
`gcc -static-pie`로 빌드하면 외부 공유 라이브러리 없이도(정적 링킹) 여전히 로드 주소가 매번 바뀌는 실행 파일을 만들 수 있다(REV-0646에서 잠깐 언급). 이 경우 `.dynamic` 섹션에 `NEEDED` 항목(REV-0683)은 없지만 재배치를 위한 최소한의 동적 섹션은 남아있어, "정적 링킹인데 왜 `.dynamic`이 있지?"라는 혼란을 줄 수 있다.

## 화면/코드에서 보이는 징후
- `readelf -h ./chall`의 `Type` 필드가 `EXEC` 또는 `DYN`으로 표시됨
- `checksec --file=./chall` 결과에 `PIE: PIE enabled` 또는 `PIE: No PIE (0x400000)`
- GDB로 같은 프로그램을 여러 번 실행했을 때 `main` 함수 주소가 매번 다르게 나옴(PIE + ASLR) vs 항상 같은 고정 주소로 나옴(No PIE)
- 디스어셈블 결과에서 절대 주소(`mov eax,[0x404050]`) 대신 `lea rax,[rip+0x2f0a]` 형태의 RIP 상대 주소 지정이 많이 보임(PIC/PIE 코드의 특징)

## 가장 먼저 할 것
`checksec --file=./chall`로 PIE 여부를 바로 확인한다. `readelf -h ./chall`의 `Type`이 `DYN`이면서 `file ./chall` 출력에 `pie executable`이라고 명시되어 있으면 PIE, `executable`이라고만 나오고 `Type: EXEC`이면 PIE가 아니다.

## 단계별 절차
1. `file ./chall`로 `pie executable` / `executable` / `shared object` 중 무엇인지 1차 확인
2. `readelf -h ./chall | grep Type`으로 `EXEC`/`DYN` 재확인
3. `checksec --file=./chall`로 PIE 여부와 베이스 주소(No PIE인 경우) 확인
4. PIE라면 GDB에서 실제 로드 베이스를 확인:
   ```gdb
   (gdb) start
   (gdb) info proc mappings
   ```
   출력 맨 위 매핑 시작 주소가 이번 실행에서의 실제 베이스 주소다.
5. 코드 안에서 PIC 여부를 직접 확인하고 싶다면 `objdump -d`로 전역 데이터 접근 부분에 절대 주소가 하드코딩되어 있는지, RIP 상대 주소를 쓰는지 비교(REV-0664 참고)
6. PIE 바이너리에서 절대 주소를 계산해야 할 때는 실제 로드 베이스를 구한 뒤 "정적 오프셋(파일 상의 주소, PIE base 0 기준) + 실제 베이스"로 더해서 계산(REV-0103 참고)

## 명령어/단축키
```bash
file ./chall                          # pie executable / executable / shared object 구분
readelf -h ./chall | grep Type        # ELF 헤더 Type 필드 확인
checksec --file=./chall               # PIE 여부 요약(pwntools checksec)
gcc -fPIC -shared -o lib.so lib.c     # PIC 공유 라이브러리 빌드
gcc -fPIE -pie -o chall chall.c       # PIE 실행 파일 빌드
gcc -no-pie -o chall chall.c          # PIE 끈 고정 주소 실행 파일 빌드
```
```gdb
info proc mappings    # 현재 실행 중인 PIE 바이너리의 실제 로드 베이스 확인
```

## 출력 해석
```
$ readelf -h ./chall | grep Type
  Type:                              DYN (Position-Independent Executable)

$ file ./chall
chall: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked, ...
```
`Type: DYN`에 괄호로 `(Position-Independent Executable)`이라고 최신 `readelf`는 친절하게 덧붙여준다. `file` 명령도 `pie executable`이라고 명시적으로 알려주므로 둘 중 하나만 봐도 충분하다.

```
$ readelf -h ./chall2 | grep Type
  Type:                              EXEC (Executable file)
```
이 경우는 `Type: EXEC`이므로 PIE가 아닌 전통적인 고정 주소 실행 파일이다. GDB로 이 바이너리를 여러 번 실행해도 `main` 함수 주소는 항상 같게 나온다.

## 흔한 실수
- PIC와 PIE를 완전히 같은 개념으로 혼용해서 부르는 것 — PIC는 "코드의 성질"이고 PIE는 "그 코드로 만들어진 실행 파일의 형태"라는 층위 차이를 구분해야 한다.
- `Type: DYN`을 보고 무조건 "이건 공유 라이브러리다"라고 단정하는 것 — PIE 실행 파일도 ELF 레벨에서는 똑같이 `DYN`으로 표시된다. `file` 명령이나 진입점/`NEEDED` 여부 등을 더 봐야 정확히 구분된다.
- PIE와 ASLR을 같은 것으로 착각하는 것 — PIE는 "그럴 수 있는 능력(코드가 재배치돼도 동작)"이고, 실제로 매번 랜덤한 주소에 로드하는 것은 커널의 ASLR 기능이다(REV-0104). PIE가 아닌 바이너리는 ASLR이 커널에서 켜져 있어도 실행 파일 자체의 코드/데이터 영역만큼은 항상 고정 주소에 로드된다(공유 라이브러리 영역은 여전히 랜덤화될 수 있음).
- `-fPIC`으로 컴파일된 오브젝트 파일을 일반 실행 파일에 그냥 정적으로 링크하면 자동으로 PIE가 된다고 착각하는 것 — 실행 파일이 최종적으로 PIE가 되려면 링크 단계에서 `-pie` 플래그(또는 배포판 기본 설정)가 별도로 필요하다.
- static-PIE 바이너리를 보고 `.dynamic` 섹션이 있다는 이유만으로 "동적 링킹이다"라고 오판하는 것(REV-0646, REV-0683 참고) — `NEEDED` 항목이 없으면 외부 라이브러리 의존은 없는 것이다.

## 막혔을 때 다음 체크
- PIE 바이너리에서 실제 주소를 계산하는 구체적 절차가 더 필요하면 → REV-0103 PIE와 주소 계산
- ASLR 자체의 동작 원리(왜 실행마다 주소가 바뀌는지)가 궁금하면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유
- checksec 다른 보호 기법(Canary, NX, RELRO)까지 한 번에 정리하고 싶으면 → REV-0105 Canary NX PIE RELRO 한 번에 이해, REV-0096 checksec 결과 읽는 법
- 정적 링킹과 PIE가 동시에 적용된 static-PIE가 헷갈리면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- 공유 라이브러리 자체를 분석 대상으로 다루는 법이 궁금하면 → REV-0652 공유 라이브러리(.so) 자체를 분석 대상으로 다루기
- 필요한 라이브러리 목록(NEEDED)을 직접 확인하고 싶으면 → REV-0683 readelf -d로 필요한 공유 라이브러리 목록 확인하기

## 미니 예제
```bash
$ gcc -no-pie -o nopie_bin chall.c
$ gcc -pie -fPIE -o pie_bin chall.c

$ readelf -h nopie_bin | grep Type
  Type:                              EXEC (Executable file)
$ readelf -h pie_bin | grep Type
  Type:                              DYN (Position-Independent Executable)

$ objdump -d nopie_bin | grep -A1 "call.*<check_password>"
  4011a5:	e8 8c ff ff ff       	call   401136 <check_password>
$ objdump -d pie_bin | grep -A1 "call.*<check_password>"
  1215:	e8 8c ff ff ff       	call   11a6 <check_password>
```
같은 소스코드인데 `nopie_bin`은 `main`에서의 `call` 대상 주소가 `0x401136`처럼 전형적인 고정 베이스(`0x400000`대) 절대 주소로 나오는 반면, `pie_bin`은 `0x11a6`처럼 파일 오프셋에 가까운 작은 주소로 나온다. PIE 바이너리의 코드 안 주소는 "로드 베이스 0"을 가정한 상대 위치이고, 실제 실행 시에는 여기에 커널이 정한 실제 베이스 주소를 더해야 진짜 가상 주소가 나온다.

## 관련 글
- REV-0103 — PIE와 주소 계산
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0096 — checksec 결과 읽는 법
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0683 — readelf -d로 필요한 공유 라이브러리 목록 확인하기

## 출처/검증
- PIC/PIE 정의와 RIP 상대 주소 지정 방식: System V ABI AMD64 보충 문서(psABI) 및 GNU 문서의 "position independent code" 설명 기준.
- `-fPIC`/`-fPIE`/`-pie`/`-no-pie`/`-static-pie` 컴파일러/링커 옵션: GCC 공식 매뉴얼("Options for Code Generation Conventions") 및 GNU ld 문서 기준.
- ELF 헤더 `Type` 필드(`ET_EXEC`, `ET_DYN`)와 PIE 실행 파일이 `ET_DYN`으로 표시되는 이유: System V ABI 및 `elf(5)` 매뉴얼 페이지 기준.
- 최신 배포판 gcc가 기본적으로 PIE를 활성화한다는 사실: Ubuntu/Fedora 툴체인 보안 강화 기본값 공지 기준 (2026-09-09 검증).
