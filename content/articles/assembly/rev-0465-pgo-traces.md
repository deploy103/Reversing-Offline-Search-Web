---
id: REV-0465
title: "PGO(Profile Guided Optimization) 흔적 인식 기초"
slug: "rev-0465-pgo-traces"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - PGO
  - Profile Guided Optimization
  - 프로파일 기반 최적화
  - text.hot
  - text.unlikely
  - "__builtin_expect"
  - basic block layout
  - cold path
  - hot path
  - branch hint
aliases:
  - PGO 흔적
  - 프로파일 최적화 어셈블리
  - hot cold 섹션
  - 컴파일러 프로파일 최적화
symptom_keywords:
  - 함수 순서가 소스랑 다르게 배치됨
  - 에러 처리 코드가 함수 끝에 몰려있음
  - text unlikely 섹션이 뭔지 모르겠음
  - 분기가 항상 멀리 떨어진 곳으로 감
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
PGO(Profile Guided Optimization)는 실제 실행 시 수집한 "어느 분기가 자주 타는지, 어느 함수가 자주 불리는지" 프로파일 데이터를 이용해 컴파일러가 자주 실행되는(hot) 경로는 분기 없는 직선 코드로, 드물게 실행되는(cold) 경로는 코드 밖 먼 곳으로 밀어내는 최적화이며, 이 결과 바이너리에는 `.text.hot`/`.text.unlikely` 같은 섹션 분리와 소스 순서와 무관하게 재배치된 함수 배열이라는 특징적인 흔적이 남는다.

## 언제 검색해야 하나
- 함수들이 소스 파일의 선언 순서와 전혀 다른 순서로 바이너리에 배치되어 있어서 원래 구조를 파악하기 어려울 때
- 에러 처리/예외적인 코드처럼 보이는 작은 블록들이 여러 함수에서 공통적으로 파일 뒤쪽(또는 특정 섹션)에 몰려 있을 때
- `readelf -S`로 섹션 목록을 봤는데 `.text.hot`, `.text.unlikely`, `.text.startup` 같은 낯선 이름의 섹션이 보일 때
- 조건부 분기 하나가 유독 멀리 떨어진 주소로 점프해서 "이게 왜 이렇게 멀리 있지"라는 의문이 들 때

## 핵심 개념

### PGO가 하는 일
일반적인 정적 최적화(`-O2`)는 컴파일러가 코드만 보고 "이 분기가 자주 탈 것 같다"를 휴리스틱으로 추측한다(예: 에러 처리 분기는 드물 것이라는 가정, 루프 안쪽은 자주 실행될 것이라는 가정). PGO는 이 추측을 실제 데이터로 대체한다.
1. **계측 빌드(instrumented build)**: 컴파일러가 각 분기/함수 호출 지점에 카운터를 심은 특수 빌드를 만든다.
2. **훈련 실행(training run)**: 이 계측된 바이너리를 대표적인 실제 워크로드로 몇 차례 실행해서 카운터 데이터(프로파일)를 파일로 저장한다.
3. **최종 빌드**: 저장된 프로파일 데이터를 입력으로 다시 컴파일해서, 실제로 자주 실행된 경로와 드물게 실행된 경로를 정확히 알고 있는 상태로 최적화를 수행한다.

### 코드 배치에 남는 흔적 — Hot/Cold 분리
PGO가 만드는 가장 눈에 띄는 흔적은 **기본 블록 배치(basic block layout)**의 변화다.
- **Hot 경로(자주 실행)**: 조건부 분기의 "자주 타는 쪽"을 분기 명령 바로 다음의 **자연스러운 순차 실행(fall-through)** 경로에 놓는다. 분기 예측이 틀릴 일이 거의 없고, 애초에 점프 자체가 필요 없는 경우도 많다.
- **Cold 경로(드물게 실행)**: 에러 처리, `assert` 실패, 예외 클린업처럼 거의 안 타는 분기의 목적지는 함수 본문에서 **물리적으로 멀리 떨어진 곳**(함수 끝부분, 또는 별도의 "unlikely" 섹션)으로 옮겨진다. 이 경로에 도달하려면 명시적인 `jcc`/`jmp`가 필요해지지만, 어차피 거의 실행 안 되므로 상관없다.

이렇게 하면 CPU 입장에서 hot 경로를 실행할 때 명령어 캐시(iCache)에 불필요한 cold 코드가 섞여 들어가지 않아 캐시 효율이 좋아지고, 분기 예측기도 "분기 안 탐(fall-through)"을 기본값으로 예측하기 쉬워진다.

### 섹션 이름으로 보는 흔적 (Linux/ELF, GCC/Clang)
GCC/Clang은 PGO(또는 `__builtin_expect`) 결과에 따라 함수나 함수의 일부를 특별한 이름의 섹션으로 분리해 배치하는 경우가 있다.
- `.text.hot` — 자주 호출되는 함수들이 모이는 섹션
- `.text.unlikely` — `__builtin_expect`로 unlikely 표시되거나 프로파일상 거의 안 타는 코드(주로 에러 경로, cold 클린업)가 모이는 섹션
- `.text.startup`/`.text.exit` — 프로그램 시작/종료 시 한 번만 실행되는 코드

`readelf -S <binary>` 또는 `objdump -h <binary>`로 섹션 헤더 목록을 보면 이런 이름을 직접 확인할 수 있다. 이 명명 규칙 자체가 PGO(또는 최소한 `__builtin_expect` 힌트)가 사용됐다는 강한 정적 증거다.

### 함수 재배치(reordering) 흔적
PGO는 자주 서로를 호출하는 함수들을 바이너리 안에서 물리적으로 가깝게 배치해서, 한 함수를 실행하며 다른 함수로 넘어갈 때 명령어 캐시/페이지 지역성이 좋아지도록 만든다(이를 함수 재배치, function reordering/hot-cold splitting이라 부른다). 그 결과 바이너리 안 함수들의 나열 순서가 **소스 파일에 선언된 순서와 무관하게 뒤섞여** 보일 수 있다. PGO 없이 컴파일된 바이너리는 보통 소스/컴파일 유닛 순서를 어느 정도 따르는 경향이 있어 비교가 가능하다.

### 더 공격적인 인라이닝
정적 휴리스틱만으로는 "이 함수를 인라인하기엔 너무 크다"고 판단했을 함수도, 프로파일 데이터로 그 함수가 실제로 매우 자주 호출된다는 게 확인되면 컴파일러가 인라인 임계값을 넘겨서라도 인라인해버리는 경우가 있다. 이는 REV-0466(함수 복제, 계획된 항목)류의 "같은 로직이 여러 번 나타나는 것처럼 보이는" 현상과도 연결된다.

### `__builtin_expect`: PGO의 경량 사촌
`if (__builtin_expect(cond, 0))`처럼 개발자가 직접 "이 조건은 거의 참이 아닐 것"이라고 컴파일러에 힌트를 주는 매크로다(리눅스 커널의 `unlikely()` 매크로가 대표적). 이는 실제 프로파일 데이터 없이 개발자의 지식만으로 hot/cold 배치를 유도하는 것으로, PGO와 결과물의 형태(hot/cold 분리)가 매우 비슷하지만 실제 실행 데이터에 기반하지 않는다는 점에서 가볍고 정적인 대체재다.

### Windows/PE에서의 PGO
MSVC의 PGO(`/GENPROFILE`+`/USEPROFILE`, 과거 `/LTCG:PGI`+`/LTCG:PGO`)도 동일한 개념(계측 빌드 → 훈련 실행 → 최종 빌드)을 따른다. PE는 ELF처럼 표준화된 `.text.hot`류 섹션 명명 관례가 널리 쓰이지는 않지만, 결과적으로 만들어지는 코드 배치(hot 경로가 직선, cold 경로가 함수 밖으로 이동)의 특징은 동일하게 나타난다.

### 리버싱에서의 의미
- 코드 배치가 뒤섞여 있다고 해서 난독화나 이상 징후로 오해하면 안 된다 — PGO는 여전히 단순한 조건부/무조건 분기만 사용하며, 목적지가 명확한 정적 주소다. 이는 오퍼큐 프레디킷(opaque predicate)이나 제어 흐름 평탄화(control flow flattening) 같은 진짜 난독화 기법과는 근본적으로 다르다(그런 기법들은 목적지가 동적으로 계산되거나 항상 참/거짓인 위장 조건을 쓴다).
- Hot/cold 분리는 오히려 유용한 정보다 — "이 경로가 실제 운영 환경에서 자주 실행됐다"는 뜻이므로, CTF에서 "이게 진짜 검증 로직인지 미끼(decoy)인지" 판단하는 데 참고할 수 있다(다만 CTF 바이너리 자체가 PGO로 빌드되는 경우는 흔치 않다는 점은 감안).

## 화면/코드에서 보이는 징후
- `readelf -S`/`objdump -h` 결과에 `.text.hot`, `.text.unlikely`, `.text.startup` 섹션이 존재
- 함수의 정상 로직 흐름에서 가지 하나가 물리적으로 매우 먼 주소로 점프하고, 그 목적지에 에러 처리/`assert`/예외 클린업 코드가 있음
- 바이너리 안 함수 나열 순서가 소스/컴파일 순서와 무관하게 섞여 있음
- 정적 휴리스틱으로는 인라인되지 않을 것 같은 큰 함수가 실제로는 인라인되어 있음

## 가장 먼저 할 것
1. 섹션 헤더 목록에서 `.text.hot`/`.text.unlikely` 류의 이름이 있는지 확인해 PGO/`__builtin_expect` 사용 여부를 먼저 가늠한다.
2. 있다면 어떤 함수/블록이 hot에, 어떤 것이 unlikely에 속하는지 매핑해본다.
3. 멀리 떨어진 점프를 발견하면 그 목적지가 단순 에러 처리인지 확인해서 난독화와 구분한다.

## 단계별 절차

**1) 섹션 목록 확인**
```bash
readelf -S target | grep -E "\.text"
objdump -h target | grep -E "\.text"
```

**2) 특정 함수의 물리적 배치 확인**
```bash
nm -n target | less        # 주소 순 정렬로 함수 나열 순서 확인
```
소스 선언 순서와 비교해 뒤섞여 있는지 본다.

**3) 멀리 떨어진 분기 목적지 확인**
IDA/Ghidra에서 조건부 분기의 목적지 주소가 현재 함수 범위를 크게 벗어나거나 함수 맨 끝 근처인지 확인한다.

**4) 목적지 코드 성격 판단**
목적지가 `call abort`, `call __assert_fail`, 예외 관련 호출(REV-0461 참고)로 이어지면 정상적인 cold 경로다. 반대로 목적지가 정상적인 계산 로직을 담고 있고 자주 실행되어야 할 것 같은데 멀리 떨어져 있다면 재검토가 필요하다.

## 명령어/단축키
- `readelf -S <binary>` — ELF 섹션 헤더 목록(Linux)
- `objdump -h <binary>` — 섹션 헤더 요약(Linux/Windows PE 모두 GNU objdump로 확인 가능)
- `nm -n <binary>` — 심볼을 주소 순으로 정렬해 함수 물리적 배치 확인
- IDA: Segments 창(`Shift+F7`)에서 세그먼트/섹션 목록 확인
- Ghidra: Window → Memory Map에서 섹션 목록과 각 섹션의 속성(실행 가능 여부 등) 확인

## 출력 해석
- `.text.unlikely`에 속한 코드가 많다는 것은 해당 프로그램이 에러 처리 경로를 상당히 많이 갖고 있다는 뜻이며, 코드 품질과는 무관하다.
- 함수 순서가 뒤섞여 있어도 각 함수 자체의 로직(디스어셈블리 내용)은 정상적이며, 그저 "어디에 배치됐는가"만 바뀐 것이다.
- 멀리 떨어진 분기 목적지가 여러 함수에 걸쳐 뭉쳐있는 것처럼 보이면, 그 뭉친 영역이 사실상 여러 함수의 cold 경로 조각들이 모인 "쓰레기장" 섹션(`.text.unlikely`)일 가능성이 높다.

## 흔한 실수
- Hot/cold 분리를 보고 즉시 "이 바이너리는 난독화/패킹됐다"고 오판하는 것 — PGO의 코드 재배치는 여전히 단순하고 정적으로 추적 가능한 분기만 쓰므로, 동적 언패킹이 필요한 진짜 난독화와는 다르다.
- 멀리 떨어진 코드를 "죽은 코드(dead code)"라고 착각하고 분석에서 제외하는 것 — 실제로는 드물게라도 실행되는 정당한 에러 처리 로직인 경우가 대부분이다.
- 함수 배치 순서가 뒤섞인 것을 컴파일러/링커 버그로 오해하는 것 — 의도된 최적화 결과다.
- PGO와 `__builtin_expect`를 완전히 동일시하는 것 — 결과물의 형태는 비슷하지만 `__builtin_expect`는 실제 프로파일 데이터 없이 개발자 추측만으로 동작한다는 차이를 기억해야 한다.

## 막혔을 때 다음 체크
- 이 코드가 정말 PGO 결과인지 확신이 안 서면 → 섹션 이름과 함수 재배치 정도를 함께 보고, 둘 다 뚜렷하면 PGO 가능성이 높다고 판단한다.
- Cold 경로가 진짜 에러 처리인지 확신이 안 서면 → REV-0461(예외 흔적), 안티디버깅 관련 글(REV-0239)과 대조해 목적지 함수 성격을 재확인한다.
- 함수 재배치 때문에 전체 구조를 이해하기 어려우면 → IDA/Ghidra의 함수 목록을 이름/주소가 아니라 xref(누가 누구를 부르는지) 기준으로 재구성해서 논리적 순서로 다시 정리한다.

## 미니 예제

**예제 1 — Hot/Cold 분리 전형적 패턴**
```c
int process(int *data, int n) {
    if (n <= 0) {                 // 거의 안 타는 조건 (프로파일상 드묾)
        log_error("invalid n");
        return -1;
    }
    return sum(data, n);           // 거의 항상 타는 정상 경로
}
```
```asm
process:
    test  esi, esi
    jle   .cold_error          ; 드문 경로이므로 멀리 있는 라벨로 점프
    call  sum                    ; hot 경로: 분기 없이 바로 이어짐
    ret
; ... 함수 다른 곳에서 아주 멀리 떨어진 위치 (.text.unlikely 섹션) ...
.cold_error:
    lea   rdi, [rip+str_invalid_n]
    call  log_error
    mov   eax, -1
    ret
```

**예제 2 — 섹션 헤더에서 확인하는 방법**
```bash
$ readelf -S target | grep text
  [13] .text.unlikely PROGBITS ...
  [14] .text.hot       PROGBITS ...
  [15] .text            PROGBITS ...
```
이런 출력이 보이면 이 바이너리는 PGO 또는 최소한 `__builtin_expect` 힌트가 적용된 GCC/Clang 빌드일 가능성이 매우 높다.

**예제 3 — `__builtin_expect`의 경량 버전 (프로파일 데이터 없이)**
```c
if (__builtin_expect(ptr == NULL, 0)) {   // "ptr==NULL은 거의 없을 것" 힌트
    return -1;
}
```
```asm
    test  rdi, rdi
    jz    .cold_null_check      ; unlikely 힌트로 인해 cold 경로로 분리
    ; 정상 경로가 바로 이어짐
```

## 관련 글
- REV-0464 — -O0과 -O2 컴파일 결과를 나란히 비교하는 법
- REV-0461 — 예외 처리(try/catch)가 어셈블리에 남기는 흔적
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0066 — JMP: 무조건 분기

## 출처/검증
- Profile Guided Optimization의 계측-훈련-재컴파일 절차와 hot/cold 코드 분리: GCC 공식 문서(`-fprofile-use`, `-fprofile-generate`) 및 LLVM/Clang 공식 문서(PGO) 기준.
- `.text.hot`/`.text.unlikely` 섹션 명명 관례: GCC 공식 문서(함수 속성 `hot`/`cold`, `-freorder-functions`) 기준.
- `__builtin_expect`: GCC 공식 문서(Other Built-in Functions Provided by GCC) 기준.
- MSVC PGO(`/GENPROFILE`, `/USEPROFILE`): Microsoft Learn 공식 문서(Profile-Guided Optimizations) 기준. (2026-09-08 검증)
