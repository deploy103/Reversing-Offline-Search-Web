---
id: REV-0761
title: "Import된 CRT 함수 이름으로 원본 로직 추정하기"
slug: "rev-0761-crt-import-names-logic-inference"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["CRT 함수 Import", "malloc free 추정", "fopen fread 추정", "rand srand 추정", "memcmp strcmp 추정", "libc 함수로 로직 추측", "UCRT __stdio_common_vfprintf"]
aliases: ["Import 목록으로 기능 추측", "CRT 함수 카테고리 분류", "라이브러리 함수로 알고리즘 감 잡기"]
symptom_keywords: ["Import 목록에 CRT 함수만 잔뜩 있음", "malloc free만 보고 뭘 하는 함수인지 모르겠음", "rand가 보이는데 왜 쓰는지 모르겠음", "printf가 직접 안 보이고 이상한 이름만 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Import 테이블에 `malloc`/`fopen`/`memcmp`/`rand` 같은 CRT(C Runtime) 함수 이름이 보이면, 함수 하나하나를 전부 디컴파일해서 읽기 전에 그 이름들을 "메모리·문자열·파일 입출력·수학/난수·시간" 같은 카테고리로 먼저 분류하는 것만으로도 프로그램이 대략 무엇을 하는지(파일을 읽는지, 난수 기반 키를 생성하는지, 바이트 단위로 직접 비교하는지) 빠르게 추정할 수 있다.

## 언제 검색해야 하나
- IDA Imports 창이나 Ghidra Symbol Tree의 External 노드를 열었는데 `malloc`, `strcpy`, `memcmp`, `fopen`, `rand` 같은 CRT 함수 이름만 잔뜩 보이고 사용자 정의 함수 이름은 하나도 없을 때
- REV-0164(Imports에서 검증 함수 후보 좁히기)로 검증 함수 자체는 찾았지만, 그 앞뒤에서 호출되는 다른 CRT 함수들이 전체적으로 무슨 역할을 하는지 감이 안 잡힐 때
- `printf`나 `scanf`가 Import 목록에 안 보이고 대신 `__stdio_common_vfprintf`, `__acrt_iob_func` 같은 낯선 이름만 보여서 당황스러울 때
- 정적 분석만으로 프로그램의 큰 그림(입력 방식, 저장 방식, 알고리즘 종류)을 먼저 잡고 세부 함수 분석에 들어가고 싶을 때

## 핵심 개념

### CRT 함수 이름은 이미 그 자체로 강력한 단서다
CRT 함수는 표준으로 정해진 시그니처와 동작을 갖는다. 즉 `malloc`이 Import되어 있다는 것은 "이 프로그램은 힙 메모리를 동적으로 할당한다"는 사실을 함수 내부를 한 줄도 안 읽고도 확정할 수 있다는 뜻이다. 이 원리를 확장하면, Import 목록 전체를 다음과 같은 카테고리로 분류해서 프로그램의 큰 그림을 세울 수 있다.

| 카테고리 | 대표 함수(Windows CRT / glibc) | 추정되는 로직 |
|---|---|---|
| 메모리 관리 | `malloc`/`calloc`/`realloc`/`free`, `HeapAlloc`/`HeapFree` | 동적 크기 데이터(가변 길이 입력, 버퍼 등)를 다룬다 |
| 문자열 비교 | `strcmp`/`strncmp`/`memcmp`/`_stricmp` | 직접적인 문자열/바이트 비교 검증 로직이 있다(REV-0164 참고) |
| 문자열 조작 | `strcpy`/`strcat`/`strtok`/`sprintf` | 입력을 가공·조합해서 새 문자열을 만든다 |
| 파일 입출력 | `fopen`/`fread`/`fwrite`/`fclose`, `open`/`read`/`write` | 외부 파일에서 키/데이터를 읽어오거나 결과를 저장한다 |
| 표준 입출력 | `scanf`/`gets`/`fgets`, `printf`/`puts` | 콘솔에서 직접 입력을 받고 결과를 출력한다(가장 흔한 crackme 패턴) |
| 난수 | `rand`/`srand`, `time` | 난수 기반 키 생성, 시드로 `time(NULL)`을 쓰면 시간 기반 취약점 가능성(REV-0165 상수 검색과 함께 확인) |
| 수학 연산 | `pow`/`sqrt`/`abs` | 수학 공식 기반 검증(암호/체크섬 알고리즘일 가능성, REV-0165 참고) |
| 프로세스/스레드 | `fork`/`exec`, `CreateThread`/`CreateProcess` | 멀티프로세스/스레드 구조, 안티디버깅 가능성 |
| 종료 제어 | `exit`/`abort`/`_exit` | 검증 실패 시 조기 종료 지점 후보 |

### 이름만 보고 "정확한 인자"까지 유추할 수 있다
CRT 함수는 표준 시그니처가 정해져 있으므로, IDA/Ghidra가 자동으로 인자 타입과 개수를 붙여준다. 예를 들어 `fread(buf, size, count, fp)` 호출을 보면 네 번째 인자가 `FILE*`이라는 것만으로 그 앞 코드에서 `fopen`으로 연 파일 핸들이 이어졌으리라 예상할 수 있고, 세 번째 인자(`count`)가 상수라면 "정확히 몇 바이트/몇 개의 항목을 읽는 고정 크기 데이터"라는 것도 알 수 있다. 이는 함수 내부를 안 읽고도 데이터 구조를 추정하는 지름길이다.

### UCRT(Universal CRT)의 함정 — 이름이 그대로 안 보일 수 있다
최신 Visual Studio(2015 이후)로 빌드된 바이너리는 `printf`/`scanf`가 헤더에서 인라인 래퍼로 처리되고, 실제 Import 테이블에는 `__stdio_common_vfprintf`, `__stdio_common_vfscanf`, `__acrt_iob_func` 같은 내부 UCRT 함수만 남는다. 이 경우에도 원리는 같다 — `vfprintf` 계열은 결국 포맷 문자열 기반 출력이라는 뜻이므로, 첫 인자로 넘어가는 포맷 문자열을 REV-0163 방식으로 추적하면 실제 출력 내용을 알 수 있다. `__acrt_iob_func(1)`은 `stdout`, `__acrt_iob_func(0)`은 `stdin`에 해당한다는 것도 알아두면 코드 흐름을 읽는 데 도움이 된다.

## 화면/코드에서 보이는 징후
- IDA Imports 탭이나 Ghidra External 심볼 목록에 CRT 함수 이름이 나열되어 있고, 디컴파일된 코드에서 그 함수들이 호출되는 지점에 손잡이(사용자 함수 이름)가 붙어 있지 않다.
- 디컴파일 결과에 `FILE *`, `size_t`, `void *` 같은 표준 타입이 자동으로 붙어 있는데, 이는 IDA/Ghidra가 CRT 함수의 표준 프로토타입(type library, `.sig`/`.gdt`)을 알고 있어서다.
- `printf`/`scanf` 대신 `__stdio_common_vfprintf`, `__acrt_iob_func` 등이 보이면 UCRT 기반 최신 MSVC 빌드라는 신호다.

## 가장 먼저 할 것
Import 목록 전체를 한 번 쭉 훑으며 위 표의 카테고리에 맞춰 머릿속(또는 노트, REV-0770 참고)으로 분류한다. `malloc`+`free`만 있는지, `fopen`류가 있는지, `rand`가 있는지부터 확인하면 이후 세부 분석의 방향이 정해진다.

## 단계별 절차
1. IDA는 `Imports` 탭(View → Open subviews → Imports), Ghidra는 Symbol Tree의 `External` 노드를 연다.
2. 목록 전체를 카테고리 표 기준으로 분류하고, 특히 파일 I/O·난수·수학 함수가 있는지 표시해 둔다.
3. 각 카테고리에서 가장 의심스러운 함수(예: `fopen`, `rand`, `memcmp`)를 하나씩 골라 Xref(IDA `X` 키, Ghidra는 REV-0160 방식)로 호출 위치를 확인한다.
4. 호출 인자를 확인해 상수 크기, 고정 포맷 문자열, 고정 파일 경로 등이 있는지 REV-0163/0165와 함께 대조한다.
5. UCRT 내부 함수(`__stdio_common_vfprintf` 등)가 보이면 첫 문자열 인자(포맷 문자열)를 추적해 실제 `printf`/`scanf` 호출로 재해석한다.
6. 분류 결과를 바탕으로 "이 프로그램은 파일에서 키를 읽어 입력과 XOR 비교한다" 같은 한 문장 요약을 먼저 세우고, 그 가설을 검증하는 방향으로 REV-0166(Call Graph)을 이어서 적용한다.

## 명령어/단축키
- IDA: Imports 탭 열기(`View → Open subviews → Imports`), 함수 Xref `X`, 문자열 창 `Shift+F12`
- Ghidra: Symbol Tree `External` 노드, 함수 더블클릭 후 Decompile 창에서 우클릭 `References → Show References to`
- 공통: 의심 함수 이름을 그대로 검색창에 입력해 여러 위치의 호출을 한 번에 확인

## 출력 해석
- `fopen` 인자에 하드코딩된 파일명 문자열이 보이면, 그 파일이 실행 파일과 같은 디렉터리에 있는지(오프라인 환경에서 챌린지 배포 파일 목록 확인) 먼저 살펴야 한다.
- `rand`/`srand` 조합에서 시드가 `time(NULL)`이면 실행 시각에 따라 값이 달라지는 취약점 구조이고, 시드가 고정 상수면 항상 같은 시퀀스가 나오는 결정론적 구조다 — 후자는 Python `random`이 아니라 C 표준 라이브러리의 `rand()` 알고리즘을 그대로 재현해야 값이 일치한다는 점에 주의한다.
- `memcmp`/`strcmp` 인자 중 하나가 `.rodata`/`.rdata`의 고정 문자열이면, 그 문자열 자체가 정답이거나 정답을 만드는 변환의 결과물일 가능성이 크다(REV-0163과 연결).

## 흔한 실수
- CRT 함수 이름만 보고 "이건 라이브러리 코드니까 안 중요하다"고 전부 건너뛰는 것 — CRT 함수 자체는 표준 동작이지만, 그 함수를 *어떻게 호출하는지*(인자, 순서, 반복 횟수)가 문제의 핵심 로직인 경우가 대부분이다. REV-0762(컴파일러 헬퍼 함수 걸러내기)와 혼동하지 않아야 한다 — 그쪽은 사용자가 호출하지 않는데 컴파일러가 자동 삽입한 코드를 가리키고, 이 문서는 사용자 코드가 명시적으로 호출하는 표준 라이브러리 함수를 가리킨다.
- UCRT 내부 함수 이름을 보고 낯설다고 무시하는 것 — `__stdio_common_vfprintf`도 결국 `printf` 계열이라는 것만 알면 나머지는 REV-0163과 동일하게 접근할 수 있다.
- Windows `rand()`와 Linux `rand()`가 같은 알고리즘이라고 착각하는 것 — 표준이 값 자체를 보장하지 않으므로, 정확한 재현이 필요하면 대상 플랫폼의 실제 구현(glibc `random()` 계열 또는 MSVC `rand()` 구현)을 확인해야 한다.

## 막혔을 때 다음 체크
- 특정 CRT 함수가 정확히 검증 로직의 어느 부분에 쓰이는지 좁히고 싶다면 → REV-0164(Imports에서 검증 함수 후보 좁히기)
- CRT 함수 호출 주변에 알 수 없는 상수가 섞여 있다면 → REV-0165(상수 검색으로 알고리즘 찾기)
- Import 목록에 CRT 함수 말고 컴파일러가 자동으로 넣은 것 같은 낯선 이름이 섞여 있다면 → REV-0762(컴파일러가 생성한 헬퍼 함수 걸러내기)
- 전체 흐름을 다 정리한 뒤 Flag 검증 로직을 끝까지 복원하고 싶다면 → REV-0767(정적분석만으로 Flag 검증 로직을 완전히 복원하는 절차)

## 미니 예제
Windows PE 바이너리의 Import 목록에서 다음 함수들만 보인다고 하자.

```
fopen, fread, fclose, malloc, free, memcmp, printf
```

1. `fopen`/`fread`/`fclose`가 있으니 "외부 파일에서 무언가를 읽는다"고 1차 가정한다.
2. `malloc`/`free`가 있으니 그 파일 내용을 담을 버퍼를 동적으로 할당한다고 추정한다.
3. `memcmp`가 있으니 "그 버퍼 내용을 다른 무언가(사용자 입력 또는 다른 상수 버퍼)와 바이트 단위로 비교한다"고 추정한다.
4. `printf`는 결과 메시지 출력용일 가능성이 크다.

이 네 줄의 추론만으로 "이 프로그램은 사용자 입력을 받아 외부 파일(예: `key.bin`)의 내용과 `memcmp`로 비교하는 구조"라는 가설을 세울 수 있고, 실제 디컴파일은 이 가설을 검증하는 방향으로 훨씬 빠르게 진행할 수 있다.

## 관련 글
- REV-0137 — Visual C++ Runtime 함수가 많은 바이너리 정리법
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0164 — Imports에서 검증 함수 후보 좁히기
- REV-0163 — 문자열에서 검증 함수로 이동하는 정적 분석
- REV-0762 — 컴파일러가 생성한 헬퍼 함수(__security_check_cookie 등) 걸러내기
- REV-0767 — 정적분석만으로 Flag 검증 로직을 완전히 복원하는 절차

## 출처/검증
- Windows CRT/UCRT 함수 목록과 `__stdio_common_vfprintf`/`__acrt_iob_func` 내부 구조는 Microsoft Learn의 C Runtime Library Reference 및 Universal CRT 관련 공식 문서 기준으로 정리했다.
- glibc `fopen`/`fread`/`rand`/`memcmp` 계열의 표준 시그니처는 POSIX 및 ISO C 표준(C11) 명세, glibc 공식 매뉴얼 기준이다.
- IDA/Ghidra가 CRT 함수에 표준 프로토타입을 자동 부여하는 동작은 각 도구의 타입 라이브러리(IDA `.til`, Ghidra `.gdt`) 공식 문서 기준이다.
