---
id: REV-0466
title: "함수가 여러 번 복제된 것처럼 보이는 이유(Function Cloning)"
slug: "rev-0466-function-cloning"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - function cloning
  - 함수 복제
  - constprop
  - isra
  - part
  - cold
  - foo.constprop.0
  - foo.isra.0
  - foo.part.0
  - foo.cold
  - IPA-CP
  - interprocedural constant propagation
  - 함수 특수화
  - function specialization
  - gcc clone
  - clang clone
aliases:
  - 같은 함수가 여러 개 있음
  - 함수 이름 뒤에 이상한 숫자
  - constprop 뭐임
  - isra 뭐임
  - 함수가 복사된 것 같음
symptom_keywords:
  - 함수 이름 끝에 .constprop .isra .part .cold가 붙어있음
  - 똑같이 생긴 함수가 여러 개 보임
  - 이름은 다른데 로직이 거의 같은 함수가 있음
  - IDA에서 sub_ 함수 여러 개가 거의 동일함
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
컴파일러가 최적화를 위해 **하나의 소스 함수**를 호출 상황(전달되는 상수, 호출 빈도, 인자 사용 패턴)에 맞춰 **여러 개의 비슷한 기계어 사본**으로 찍어내는 것이 함수 복제(Function Cloning)이며, `foo.constprop.0`, `foo.isra.1`, `foo.part.0`, `foo.cold` 같은 접미사가 붙은 함수들이 그 결과물이다.

## 언제 검색해야 하나
- IDA/Ghidra Functions 창에 `sub_401000`, `sub_401200`처럼 이름이 다른데 디스어셈블리를 열어보면 로직이 거의 똑같은 함수가 여러 개 보일 때
- Linux 바이너리를 `nm`이나 `objdump -d`로 열었을 때 `parse_input.constprop.0`, `parse_input.isra.2`, `parse_input.part.0` 처럼 원래 이름 뒤에 점(`.`)과 접미사가 붙은 심볼이 여러 개 보일 때
- 어떤 함수를 패치했는데 프로그램이 여전히 이전 동작을 하는 것 같을 때(사실은 다른 복제본이 실행되고 있는 경우)
- "함수가 왜 이렇게 많지?"라는 의문이 들 때

## 핵심 개념

### 왜 컴파일러가 함수를 복제하는가
`-O2`/`-O3` 최적화에서 GCC와 Clang은 **하나의 함수를 여러 버전으로 다시 컴파일**해서 각각 다른 호출 지점에 연결하는 경우가 있다. 목적은 항상 "이 특정 상황에서는 원본보다 더 빠르거나 작은 코드를 만들 수 있다"는 것이다. 대표적인 이유 세 가지:

1. **상수 전파(IPA-CP, Interprocedural Constant Propagation)**: 어떤 함수를 호출할 때 항상 같은 상수 인자를 넘기는 호출 지점이 있으면, 컴파일러는 그 상수를 아예 함수 본문에 박아 넣은 "전용 버전"을 새로 만든다. 이러면 그 인자를 위한 분기/곱셈 등이 상수 계산으로 바뀌어 사라질 수 있다. GCC는 이런 복제본에 `.constprop.N` 접미사를 붙인다.
2. **인자 구조체 분해(IPA-SRA, Scalar Replacement of Aggregates)**: 구조체나 사용하지 않는 인자를 통째로 넘기는 대신, 실제로 쓰는 필드/값만 레지스터로 바로 넘기도록 함수 시그니처 자체를 바꾼 버전을 만든다. GCC는 `.isra.N`(Interprocedural Scalar Replacement of Aggregates) 접미사를 붙인다.
3. **차가운 경로 분리(cold path splitting)**: 함수 안에서 거의 실행되지 않는 부분(에러 처리, `abort()` 직전 로직 등)을 별도의 함수로 떼어내서 원래 함수의 코드 크기를 줄이고 명령어 캐시 지역성을 높인다. 이 분리된 부분은 `.part.N`(partial) 또는 `.cold` 접미사가 붙으며, 실제로는 원래 함수 안에서 `jmp`나 `call`로 연결된다.

Clang/LLVM도 비슷한 최적화(인라이닝 후 재분할, `.cold` 섹션 분리 등)를 수행하지만 접미사 표기 관례는 GCC와 다를 수 있고, MSVC는 다른 이름 규칙(`?foo@@...`처럼 맹글링된 이름에 별도 표시가 붙거나, PGO 빌드에서 `foo$hot`, `foo$cold`처럼 표시)을 쓴다.

### 복제와 인라이닝의 차이
인라이닝은 호출자 코드 안에 피호출자 코드를 통째로 붙여넣어서 CALL 자체를 없애는 것이고, 함수 복제는 **여전히 독립된 함수로 존재하되 내용이 조금씩 다른 여러 벌**을 만드는 것이다. 실제로는 두 최적화가 같이 쓰인다 — 복제된 특수 버전이 다시 특정 호출 지점에 인라인되기도 한다.

### IDA/Ghidra에서 보이는 모습
Windows PE(MSVC)에서는 함수 이름이 원래부터 없는 경우가 많아 `sub_140001200`처럼 주소 기반 이름만 붙기 때문에, "복제된 함수들"이라는 사실 자체가 안 보이고 그냥 "비슷하게 생긴 함수가 여러 개"로만 보인다. 반면 Linux ELF(GCC/Clang, 특히 디버그 심볼이 남아있는 경우)에서는 `objdump -d --demangle`이나 `nm`으로 열면 접미사가 그대로 보여서 "원본이 무엇인지" 바로 알 수 있다.

## 화면/코드에서 보이는 징후
```text
$ nm ./binary | grep parse_input
0000000000401120 t parse_input
0000000000401340 t parse_input.constprop.0
0000000000401410 t parse_input.isra.1
0000000000401520 t parse_input.part.0
```
```asm
; parse_input.constprop.0 - flag 인자가 항상 1로 고정된 버전
mov     eax, 1          ; 원본에서는 인자로 받던 값이 상수로 박혀있음
; (원본의 flag == 0 분기 전체가 사라져 있음)
```
IDA에서는 이런 함수들이 서로 다른 주소의 별개 `sub_`로 보이지만, F5로 디컴파일해서 나란히 놓고 보면 분기 개수, 상수 사용, 지역 변수 개수가 미묘하게 다른 "형제 함수"임을 알 수 있다.

## 가장 먼저 할 것
1. 심볼 이름에 `.constprop`, `.isra`, `.part`, `.cold`가 붙어 있는지 확인한다 — 있다면 원본 이름(점 앞부분)으로 다른 복제본이 더 있는지 `nm`/`objdump`에서 같이 검색한다.
2. 로직이 거의 같아 보이는 함수 두 개를 발견하면, 어떤 상수/분기가 한쪽에서만 빠져있는지 비교해서 어떤 호출 상황을 위해 특수화됐는지 유추한다.
3. 패치/후킹 대상이라면 **모든 복제본**을 함께 찾아 수정해야 한다. 원본 하나만 고치면 다른 복제본을 호출하는 코드 경로에서는 여전히 옛 동작이 남는다.

## 단계별 절차
**1) 접미사가 붙은 심볼 모아보기 (Linux)**
```bash
nm ./binary | grep -E '\.(constprop|isra|part|cold)\.'
objdump -d --demangle ./binary | grep '^[0-9a-f]* <.*\.(constprop|isra|part|cold)'
```

**2) 원본과 복제본 나란히 비교**
IDA에서 두 함수를 각각 F5로 디컴파일한 뒤, 텍스트 편집기에 나란히 붙여넣고 diff를 뜬다. 상수 하나가 다르거나, 분기 하나가 통째로 없는 정도의 차이라면 함수 복제로 확신할 수 있다.

**3) 어떤 호출 지점이 어떤 복제본을 쓰는지 확인**
복제본 함수 이름 위에서 `X`(Xrefs to)를 눌러 어느 호출 지점들이 이 특수화된 버전을 쓰는지 확인한다. 이걸 보면 "이 호출 지점들은 항상 같은 상수를 넘긴다"는 컴파일 시점의 사실을 역으로 알아낼 수 있다.

**4) `.part`/`.cold`는 별도 함수가 아니라 "떨어져 나간 조각"으로 취급**
`foo.part.0`이 `foo`에서 `jmp`나 `call`로만 연결된다면, 논리적으로는 `foo`의 일부다. 분석 시 두 개를 하나의 함수처럼 묶어서 이해하는 게 낫다.

## 명령어/단축키
- Linux: `nm binary`, `objdump -d --demangle binary`, `readelf -s binary`
- IDA: `X`(Xrefs to), `N`(이름 변경으로 원본/복제본 관계 표시), Functions 창에서 이름순 정렬 후 접두어가 같은 함수 묶어보기
- Ghidra: Symbol Tree에서 이름순 정렬, Function Diff(버전 추적 플러그인) 사용 가능

## 출력 해석
- `.constprop.N` — 특정 인자가 상수로 고정된 특수화 버전. 원본에 있던 그 인자 관련 분기/계산이 사라져 있으면 정상.
- `.isra.N` — 인자 전달 방식(구조체 대신 개별 필드/레지스터)이 바뀐 버전. 함수 시그니처(인자 개수/타입)가 원본과 달라 보이는 게 정상.
- `.part.N` — 원래 함수에서 잘려나간 일부. 대개 크기가 작고, 원본 함수 끝부분에서 `jmp`/`call`로 진입한다.
- `.cold` — 거의 실행되지 않는 예외/에러 경로. 실행 빈도가 낮으므로 핵심 로직(예: flag 검증)일 가능성은 낮지만, 에러 메시지 등 단서가 있을 수 있으니 완전히 무시하지는 않는다.

## 흔한 실수
- 접미사가 붙은 함수를 완전히 별개의 새 함수로 오해하고 처음부터 다시 분석하는 것 — 원본 이름으로 먼저 검색해서 "형제 함수"가 있는지 확인하는 습관을 들이면 시간을 절약한다.
- 후킹/패치 시 원본 함수만 수정하고 `.constprop`/`.isra` 복제본은 그대로 두는 것 — 실행 경로에 따라 어느 쪽이 실제로 호출될지 모르므로 관련된 모든 복제본을 확인해야 한다.
- `.cold`로 분리된 코드를 "죽은 코드(dead code)"로 착각해서 무시하는 것 — 실제로 실행되는 정상 경로이며 단지 자주 실행되지 않을 뿐이다.
- MSVC 바이너리에는 이런 접미사 표기가 없다는 것을 모르고 Linux ELF 사례만 기준으로 찾으려는 것 — Windows에서는 함수 이름이 아니라 코드 구조 유사성으로 직접 비교해야 한다.

## 막혔을 때 다음 체크
- 복제본으로 의심되는 함수들의 차이가 상수 하나뿐이라면 → REV-0464(-O0과 -O2 비교) 방식으로 최적화 없는 빌드와 비교해서 원본 로직을 먼저 파악한다.
- 어떤 상수가 왜 그 값으로 고정됐는지 궁금하다면 → 호출 지점(Xref)에서 그 인자 위치에 항상 같은 리터럴이 들어가는지 확인한다.
- `.part`/`.cold`가 어디서 진입하는지 못 찾겠다면 → 원본 함수 끝부분(에필로그 직전)의 `jmp`/`call`을 다시 확인한다.

## 미니 예제
**예제 1 — constprop로 사라지는 분기**
```c
// 원본 소스
static void apply(int *arr, int n, int mode) {
    for (int i = 0; i < n; i++) {
        if (mode) arr[i] *= 2;
        else      arr[i] += 1;
    }
}
void caller_a(int *arr, int n) { apply(arr, n, 1); }  // 항상 mode=1로 호출
```
```asm
; apply.constprop.0 (mode=1로 특수화된 버전)
loop_top:
    shl     dword ptr [rdi+rax*4], 1   ; *2 만 남고 else 분기는 통째로 사라짐
    inc     rax
    cmp     rax, rsi
    jl      loop_top
```

**예제 2 — .part로 분리된 에러 처리**
```c
int validate(int x) {
    if (x < 0) {
        log_error("negative value");   // 드물게 실행 -> .part.0으로 분리될 수 있음
        return -1;
    }
    return x * 2;
}
```
```asm
validate:
    test    edi, edi
    js      validate.part.0     ; 음수일 때만 별도 조각으로 점프
    lea     eax, [rdi+rdi]
    ret
```

## 관련 글
- REV-0464 — -O0과 -O2 컴파일 결과를 나란히 비교하는 법
- REV-0467 — Common Subexpression Elimination이 코드에 남기는 흔적
- REV-0469 — 레지스터 할당 차이로 같은 로직이 다르게 보이는 이유
- REV-0472 — 함수 하나가 여러 진입점을 가진 것처럼 보이는 이유(ifunc/dispatch)
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- GCC 최적화 패스(IPA-CP, IPA-SRA, cold/hot 코드 분리)와 심볼 접미사 명명 규칙: GNU GCC 공식 문서(GCC Internals, Interprocedural Optimization 챕터) 기준.
- Clang/LLVM의 함수 특수화 및 cold 섹션 분리: LLVM 공식 문서(Function Attributes, `-fsplit-cold-code` 관련 설명) 기준.
- 위 어셈블리 예제는 x86-64 GCC/Clang `-O2` 빌드 결과를 단순화해 재구성한 예시다(2026-09-08 검증).
