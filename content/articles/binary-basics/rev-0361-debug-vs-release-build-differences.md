---
id: REV-0361
title: "Debug 빌드와 Release 빌드의 어셈블리 차이"
slug: "rev-0361-debug-vs-release-build-differences"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["Debug 빌드", "Release 빌드", "debug build", "release build", "/Od /O2", "-O0 -O2", "디버그 심볼", "최적화 여부 판별"]
aliases: ["디버그 빌드랑 릴리즈 빌드가 뭐가 다른가요", "이 바이너리가 디버그 빌드인지 어떻게 아나요", "디버그 빌드는 왜 분석하기 쉬운가요", "release 빌드가 왜 더 어려운가요"]
symptom_keywords: ["함수마다 변수가 다 스택에 있고 레지스터를 거의 안 씀", "PDB 파일이 같이 있거나 심볼이 풍부함", "코드가 원본 소스와 거의 1대1로 대응됨", "assert 관련 코드나 디버그 문자열이 많이 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Debug 빌드(MSVC `/Od`, GCC/Clang `-O0` + 디버그 정보)는 최적화를 끄고 디버깅 편의를 최우선으로 삼아 소스 코드와 거의 1대1로 대응되는 코드를 생성하는 반면, Release 빌드(MSVC `/O2`, GCC/Clang `-O2`/`-O3`)는 실행 속도와 크기를 위해 인라이닝·레지스터 할당·명령어 재배치 등 다양한 최적화를 적용해 원본 구조를 크게 바꿔버리므로, 같은 소스라도 두 빌드의 디스어셈블리는 전혀 다른 모습으로 나타난다.

## 언제 검색해야 하나
- 낯선 바이너리를 열었는데 코드가 유난히 읽기 쉽고 변수들이 계속 스택(`[rbp-N]`)에 저장되어 있어서, 이게 디버그 빌드인지 릴리즈 빌드인지 판단하고 싶을 때
- PDB(Windows) 또는 분리되지 않은 DWARF 디버그 정보(Linux)가 함께 있는 바이너리를 만나서 분석 난이도를 가늠하고 싶을 때
- CTF 문제나 상용 소프트웨어 바이너리가 실제로는 릴리즈 빌드인데 디버그 빌드처럼 분석하려다가 코드 구조가 안 맞아 헷갈릴 때
- 같은 프로그램의 디버그 버전과 릴리즈 버전을 둘 다 갖고 있어서, 디버그 버전으로 로직을 먼저 이해한 뒤 릴리즈 버전에 매칭하고 싶을 때
- `assert()` 관련 코드나 디버그 전용 로그 문자열이 보여서 이 빌드가 디버그 설정으로 컴파일됐을 가능성을 확인하고 싶을 때

## 핵심 개념

### 두 빌드 설정의 목적이 다르다
**Debug 빌드**의 목표는 "개발자가 소스 코드 한 줄 한 줄을 디버거로 정확히 따라갈 수 있게 하는 것"이다. 그래서 최적화를 최소화(MSVC `/Od`, GCC/Clang `-O0`)하고, 모든 변수를 예측 가능한 스택 위치에 두며, 디버그 정보(PDB, DWARF)를 풍부하게 남긴다. **Release 빌드**의 목표는 "최종 사용자에게 배포할 만큼 빠르고 작은 실행 파일을 만드는 것"이다. 그래서 최적화를 적극적으로 적용(MSVC `/O2`, GCC/Clang `-O2`/`-O3`)하고, 디버그 정보는 최소화하거나 아예 제거(strip)한다.

### 1) 변수 저장 위치의 차이
```c
int square_sum(int a, int b) {
    int s1 = a * a;
    int s2 = b * b;
    return s1 + s2;
}
```

**Debug 빌드** — 모든 지역 변수가 항상 스택에 있고, 값이 필요할 때마다 다시 로드한다(REV-0037에서 다룬 최적화 부재 패턴과 동일):
```asm
square_sum:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-4], edi     ; a
    mov     [rbp-8], esi      ; b
    mov     eax, [rbp-4]
    imul    eax, [rbp-4]       ; s1 = a*a (매번 스택에서 다시 읽음)
    mov     [rbp-0xC], eax
    mov     eax, [rbp-8]
    imul    eax, [rbp-8]        ; s2 = b*b
    mov     [rbp-0x10], eax
    mov     eax, [rbp-0xC]
    add     eax, [rbp-0x10]
    pop     rbp
    ret
```

**Release 빌드** — 변수가 레지스터에만 머물고 스택 접근이 거의 없다:
```asm
square_sum:
    imul    eax, edi, edi     ; s1 = a*a
    imul    edx, esi, esi      ; s2 = b*b
    add     eax, edx
    ret
```

### 2) 프롤로그/에필로그의 유무
Debug 빌드는 거의 항상 RBP 기반 스택 프레임(`push rbp` / `mov rbp, rsp`)을 명시적으로 만든다(REV-0031). 디버거가 콜스택을 신뢰성 있게 추적하려면 고정된 프레임 포인터가 있는 게 유리하기 때문이다. Release 빌드는 종종 "프레임 포인터 생략(omit frame pointer)" 최적화를 적용해 RBP를 일반 레지스터로 재활용하고, 지역 변수를 RSP 상대 오프셋으로 직접 참조한다.

### 3) 함수 인라이닝과 함수 경계
Debug 빌드는 디버거가 함수 단위로 정확히 스텝인/스텝오버(REV-0170)할 수 있도록 함수 인라이닝(REV-0357)을 거의 하지 않는다 — 작은 헬퍼 함수도 대부분 실제 `call`로 남는다. Release 빌드는 짧은 함수를 적극적으로 인라인해서, 원본 소스의 함수 경계가 바이너리에 거의 남지 않는 경우가 흔하다.

### 4) 디버그 전용 코드의 존재
Debug 빌드에는 `assert()` 매크로가 실제 검사 코드로 전개되어 남아있는 경우가 많다(Release 빌드는 보통 `NDEBUG` 매크로로 `assert()`를 완전히 제거). 또한 MSVC Debug 빌드는 힙 할당 시 디버그 힙(`_CrtSetDbgFlag` 등)을 쓰거나, 초기화되지 않은 스택/힙 메모리를 `0xCC`(스택), `0xCD`(힙, freed) 같은 특정 패턴으로 채워 넣기도 한다(REV-0361과 별개로 이는 MSVC CRT 디버그 힙의 특징이다). 이런 패턴이 메모리 덤프에서 보이면 디버그 빌드일 가능성이 매우 높다.

### 5) 스택 카나리/보안 기능 강도 차이
릴리즈 빌드는 배포용이므로 스택 보호(`/GS`, `-fstack-protector`), ASLR/PIE, DEP/NX 같은 보안 완화 기법이 기본으로 켜져 있는 경우가 많다. 반대로 일부 디버그 빌드는 개발 편의를 위해 이런 보호 기능이 약하게 설정되거나, 최적화가 꺼져 있어 오히려 스택 배치가 더 예측 가능해서 취약점 분석/PoC 개발에 유리한 경우도 있다. CTF 배포 바이너리는 보통 릴리즈 빌드에 보안 옵션을 조합해서 배포하지만, 문제 설계상 일부러 특정 보호를 끄기도 하므로 `checksec` 결과를 항상 직접 확인해야 한다.

### 6) 심볼/디버그 정보 존재 여부
Debug 빌드는 함수/변수 이름이 그대로 PDB(Windows) 또는 바이너리 내 DWARF 섹션(Linux, strip 안 됐다면)에 남아있어 IDA/Ghidra가 원본 이름을 그대로 보여줄 수 있다. Release 빌드는 배포 시 PDB를 따로 분리해서 제공하지 않거나 ELF를 strip하는 경우가 많아(REV-0038), 함수 이름이 `sub_401000` 같은 자동 생성 이름으로만 남는다.

## 화면/코드에서 보이는 징후
- 거의 모든 지역 변수가 매번 스택에 저장되고 다시 로드되는 반복적인 패턴(Debug)
- 계산이 레지스터 안에서 대부분 끝나고 스택 접근이 드묾(Release)
- 짧은 헬퍼 함수도 전부 독립된 `call`로 존재(Debug) vs 상당수가 호출자 안에 흡수되어 사라짐(Release)
- `assert` 관련 문자열(파일명, 줄 번호, 조건식 텍스트)이 `.rodata`/`.rdata`에 다수 존재(Debug 가능성)
- 함수/변수 이름이 원본 그대로 보임(디버그 정보 존재) vs `sub_XXXXXX`/`FUN_XXXXXX`만 보임(Release, strip됨)
- MSVC 디버그 힙 특유의 채움 패턴(`0xCC`, `0xCD`, `0xFEEEFEEE` 등)이 메모리 덤프에서 관찰됨

## 가장 먼저 할 것
낯선 바이너리를 열면 먼저 짧은 함수 몇 개를 훑어 "변수가 계속 스택을 오가는가, 레지스터에서 끝나는가"를 확인한다. 스택 왕복이 많고 함수 호출이 많으면 디버그 빌드에 가깝게 분석하고(소스와 1:1 대응을 기대), 레지스터 중심이고 함수가 적으면 릴리즈 빌드로 간주해 인라이닝·최적화 패턴(REV-0037)을 먼저 의심한다.

## 단계별 절차

**1) 디버그 정보/심볼 존재 여부 확인**

`file ./bin`(Linux) 결과에서 `not stripped`인지, PDB가 같은 폴더에 있는지(`.pdb` 파일) 확인한다. 있다면 디버그 빌드이거나 디버그 정보를 보존한 릴리즈 빌드(release with debug info)일 가능성이 높다.

**2) 대표 함수 하나를 골라 변수 저장 패턴 관찰**

작은 함수 하나를 열어 지역 변수가 매번 스택을 오가는지, 레지스터에서 계산이 끝나는지 본다.

**3) assert/디버그 문자열 검색**

`strings ./bin | grep -i assert`로 조건식/파일명 텍스트가 다수 나오면 디버그 빌드 신호로 참고한다.

**4) 스택 카나리/보안 옵션 확인**

`checksec --file=./bin`(Linux) 또는 PE 헤더의 `/GS`, ASLR/DEP 플래그를 확인해 배포 설정과 일치하는지 본다.

**5) 함수 인라이닝 정도로 최종 판단**

작은 헬퍼 함수들이 대부분 독립적으로 `call`되면 디버그, 흡수되어 사라진 게 많으면 릴리즈로 결론짓는다.

## 명령어/단축키
```bash
file ./bin                      # stripped 여부 확인
strings ./bin | grep -i assert   # 디버그 전용 assert 문자열 탐색
readelf -S ./bin | grep debug     # .debug_info 등 DWARF 섹션 존재 확인(Linux)
checksec --file=./bin              # 보안 옵션(카나리, PIE, NX 등) 확인
```
IDA: 파일 열 때 자동으로 PDB를 찾아 로드 시도(찾으면 심볼이 원본 그대로 표시됨). Ghidra: 프로젝트 임포트 시 DWARF 자동 인식 옵션 확인.

## 출력 해석
- `.debug_info`, `.debug_line` 섹션이 있으면(strip 안 된 Linux 바이너리) 원본 소스 파일명과 줄 번호까지 매핑 가능한 풍부한 디버그 빌드다.
- PDB가 없고 ELF가 stripped라면, 함수 인라이닝/레지스터 최적화 정도를 보고 릴리즈 빌드 여부를 간접적으로만 추정해야 한다.
- 같은 로직인데 디버그 버전은 함수가 20개, 릴리즈 버전은 함수가 8개라면 나머지 12개는 인라인되어 흡수된 것으로 해석할 수 있다.

## 흔한 실수
- Strip 여부와 최적화 여부를 같은 것으로 혼동하는 것 — strip은 심볼 정보 유무의 문제이고, 최적화는 코드 구조 자체의 문제다. Strip된 최적화 없는 빌드(`-O0` + strip)도 존재하고, strip 안 된 최적화 빌드(`-O2` + 심볼 유지)도 흔하다.
- 릴리즈 빌드를 디버그 빌드처럼 "소스와 1:1 대응될 것"이라 기대하고 줄 단위로 억지로 맞추려는 것 — REV-0037에서 다룬 최적화 패턴을 먼저 인식해야 한다.
- 디버그 빌드라고 해서 항상 분석이 쉬울 거라 단정하는 것 — 안티디버깅/난독화가 별도로 추가된 디버그 빌드는 오히려 더 복잡할 수 있다. 디버그/릴리즈 구분은 "코드 구조의 예측 가능성"에 대한 것이지 전체 난이도를 보장하지 않는다.
- MSVC 디버그 힙의 채움 패턴(`0xCC`, `0xCD` 등)을 셸코드나 악성 패턴으로 오인하는 것 — 이는 CRT가 의도적으로 초기화/해제된 메모리를 표시해두는 디버깅 보조 장치다.

## 막혔을 때 다음 체크
- 릴리즈 빌드의 구체적인 최적화 패턴들(인라이닝, 루프 언롤링, CMOV 등)이 궁금하면 → REV-0037 컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유
- 함수 인라이닝만 따로 더 자세히 보고 싶으면 → REV-0357 함수 인라인이 코드 흐름에 미치는 영향
- Strip된 바이너리와 심볼이 있는 바이너리의 차이 자체가 궁금하면 → REV-0038 심볼이 있는 바이너리와 Stripped 바이너리 차이
- `-O0`과 `-O2` 결과를 실제로 나란히 비교하는 구체적 방법이 궁금하면 → REV-0464 -O0과 -O2 컴파일 결과를 나란히 비교하는 법
- 컴파일러 계열(MSVC/GCC/Clang) 자체를 구분하는 방법이 궁금하면 → REV-0360 컴파일러별(MSVC/GCC/Clang) 코드 패턴 차이 기초

## 미니 예제
조건부 로직이 있는 함수를 디버그/릴리즈로 비교해보자.

```c
int classify(int score) {
    if (score >= 90) return 3;
    if (score >= 70) return 2;
    return 1;
}
```

**Debug (`-O0`)** — 소스의 `if`문 순서 그대로, 스택 경유:
```asm
classify:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-4], edi      ; score
    cmp     dword [rbp-4], 89
    jle     .check70
    mov     eax, 3
    jmp     .done
.check70:
    cmp     dword [rbp-4], 69
    jle     .default
    mov     eax, 2
    jmp     .done
.default:
    mov     eax, 1
.done:
    pop     rbp
    ret
```

**Release (`-O2`)** — 스택 없이 레지스터만으로, 비교 순서도 컴파일러가 재배치:
```asm
classify:
    cmp     edi, 89
    jg      .three
    cmp     edi, 69
    mov     eax, 1
    jle     .ret
    mov     eax, 2
    jmp     .ret
.three:
    mov     eax, 3
.ret:
    ret
```

두 코드는 동일한 입력에 대해 항상 동일한 결과를 내지만, Debug 버전은 `[rbp-4]`를 반복해서 읽으며 소스의 `if` 순서를 그대로 따라가는 반면, Release 버전은 스택을 전혀 쓰지 않고 비교 순서도 최적화러 판단에 따라 재배치되어 있다. 둘 다 처음 만나면 낯설 수 있지만, "이 함수가 디버그인지 릴리즈인지"를 먼저 판단하고 그에 맞는 읽기 전략(1:1 대응 기대 vs 입출력 관계 중심 파악)을 쓰면 분석 속도가 크게 빨라진다.

## 관련 글
- REV-0037 — 컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유
- REV-0357 — 함수 인라인이 코드 흐름에 미치는 영향
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이
- REV-0464 — -O0과 -O2 컴파일 결과를 나란히 비교하는 법
- REV-0360 — 컴파일러별(MSVC/GCC/Clang) 코드 패턴 차이 기초

## 출처/검증
- MSVC `/Od`/`/O2` 옵션과 디버그 힙 채움 패턴(`0xCC`, `0xCD` 등): Microsoft Learn "/Od (Disable Debug)", "/O2 (Maximize Speed)" 및 "CRT Debug Heap Details" 공식 문서 기준.
- GCC/Clang `-O0`/`-O2` 최적화 레벨 정의: GCC 공식 문서 "Options That Control Optimization" 및 LLVM/Clang 공식 문서 기준 (2026-09-09 검증).
