---
id: REV-0494
title: "어셈블리 점프 목표 주소가 함수 바깥을 가리킬 때"
slug: "rev-0494-jump-target-outside-function"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - tail call
  - jmp 함수 밖
  - jump outside function boundary
  - 꼬리 호출 최적화
  - tail call optimization
  - jmp to another function
  - shared function tail
  - basic block outside range
  - IDA function chunk
  - Ghidra thunk function
aliases:
  - jmp가 함수 밖으로 나가요
  - call이 아니라 jmp로 함수를 부름
  - 함수 경계 밖으로 점프
  - tail call이 뭔지 모르겠음
  - jmp 대상이 다른 함수 안임
symptom_keywords:
  - jmp 명령의 목표가 현재 함수 범위를 벗어남
  - call 대신 jmp로 다른 함수를 호출하는 것처럼 보임
  - IDA에서 함수 끝에 jmp가 다른 함수로 감
  - 함수가 return 없이 jmp로 끝남
  - 여러 함수가 코드 조각을 공유하는 것처럼 보임
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
함수 끝부분에서 `JMP`가 그 함수 범위 밖(다른 함수의 시작 주소나 중간)으로 뛰는 코드는 대부분 버그나 오분석이 아니라 컴파일러의 **꼬리 호출 최적화(Tail Call Optimization, TCO)**이며, "마지막으로 다른 함수를 호출하고 그 함수의 반환값을 그대로 자신의 반환값으로 쓸 것"이므로 `CALL`+`RET` 대신 `JMP` 하나로 대체해서 스택 프레임을 아낀 것이다.

## 언제 검색해야 하나
- IDA에서 함수의 마지막 명령이 `RET`이 아니라 `JMP other_func`로 끝나 있을 때
- Ghidra에서 어떤 함수가 "Thunk Function"으로 표시되거나, 함수 코드가 다른 함수 코드 영역과 겹치는 것처럼 보일 때
- 디스어셈블리에서 `JMP`의 목표 주소가 현재 보고 있는 함수의 시작-끝 범위를 완전히 벗어난 곳(다른 함수 이름)을 가리킬 때
- 여러 함수가 뒷부분 코드(에필로그, 공통 처리 루틴)를 공유하는 것처럼 보일 때

## 핵심 개념

### 꼬리 호출(Tail Call)이란
함수 `A`의 **마지막으로 실행되는 문장**이 다른 함수 `B`를 호출하고, `A`가 그 호출 결과를 그대로 반환하는 경우를 "꼬리 호출"이라 한다.
```c
int A(int x) {
    // ... 처리 ...
    return B(x);   // A의 마지막 동작이 B 호출 -> 꼬리 호출
}
```
이 경우 `A`는 `B(x)`가 반환된 뒤 아무것도 더 할 게 없다. `B`가 반환하면 `A`도 곧바로 반환할 것이기 때문에, 컴파일러는 다음과 같이 최적화할 수 있다:
1. `A`의 스택 프레임(지역 변수 공간)을 미리 정리한다(`leave` 또는 `add rsp, N`).
2. `A`로 돌아올 반환 주소를 그대로 스택에 남겨둔 채(`CALL`로 새로 push하지 않고), `B`로 **`JMP`한다**.
3. `B`는 자신이 끝나면 스택 맨 위의 반환 주소(원래 `A`를 호출했던 곳의 주소)로 직접 `RET`한다 — `A`를 거치지 않고 바로.

결과적으로 `A`의 스택 프레임이 통째로 생략되어 **재귀 호출이 스택을 무한정 소비하지 않게** 되거나(꼬리 재귀 최적화), 일반적인 경우에도 함수 호출 하나(스택 프레임 하나)를 아끼는 효과가 있다.

### 왜 CALL이 아니라 JMP인가
`CALL`은 반환 주소를 새로 스택에 push하지만, `JMP`는 스택을 전혀 건드리지 않는다. 꼬리 호출에서는 "이미 스택에 있는 반환 주소(A를 호출한 곳)"를 그대로 재사용하면 되므로, 새로 반환 주소를 쌓을 필요가 없다 — 그래서 `JMP`를 쓴다. 이게 REV-0071(CALL)에서 언급한 "JMP는 스택에 아무것도 남기지 않는다"는 성질을 정확히 활용한 사례다.

### IDA/Ghidra가 이걸 어떻게 다루는가
- **IDA**: 함수의 마지막이 `JMP other_func`로 끝나면, 함수 목록에서 이 함수의 범위가 그 `JMP` 명령까지로 표시되고 `RET`가 없다. `other_func`로 더블클릭해서 이동하면 완전히 별개의 함수로 정의되어 있는 경우가 많다. 때로는 "Function Chunk"(함수가 여러 조각으로 나뉘어 표시되는 기능)로 인해 진짜 함수 경계가 헷갈릴 수 있다.
- **Ghidra**: 아예 함수 전체가 `JMP` 한 줄로만 구성된 경우 "Thunk Function"(위임 함수)으로 자동 인식해서, 함수 목록에 원래 함수 이름 대신 `thunk_FUNCNAME` 같은 형태로 표시하고 실제로는 대상 함수로 바로 연결해서 보여주기도 한다.
- 두 도구 모두 F5(디컴파일) 결과에서는 꼬리 호출을 `return B(x);` 형태로 비교적 깔끔하게 재구성해주는 경우가 많다 — 어셈블리 원문에서만 `JMP`로 보이고, 디컴파일 결과는 오히려 이해하기 쉬울 수 있다.

### 흔히 헷갈리는 다른 상황과의 구분
- **일반 조건 분기(`Jcc`)로 함수 안의 다른 블록으로 가는 것**: 이건 함수 범위 "안"에서의 정상적인 분기이므로 이 문서의 대상이 아니다. 목표 주소가 함수 시작-끝 범위 **밖**일 때만 이 패턴을 의심한다.
- **점프 테이블을 통한 간접 JMP(switch문)**: 이것도 함수 내부의 여러 케이스 블록으로 가는 것이라 보통 함수 범위 안에 있다(REV-0441 참고). 범위 밖의 다른 함수로 가는 이 문서의 패턴과 다르다.
- **PLT(Procedure Linkage Table) 스텁**: Linux ELF에서 외부 라이브러리 함수를 부를 때, `PLT` 안의 작은 스텁 함수는 `jmp qword ptr [GOT 슬롯]`으로 끝난다. 이것도 넓게 보면 "함수처럼 보이는 것이 JMP로 끝나서 다른 곳(실제 라이브러리 함수)으로 간다"는 점에서 비슷한 현상이며, 로더가 GOT를 채워야 실제 목적지가 확정된다(REV-0100 참고).
- **난독화/패킹에 의한 의도적 흐름 조작**: 정상적인 컴파일러 출력이 아니라 난독화 도구가 일부러 함수 경계를 흐트러뜨리는 경우도 있으나, 훨씬 드물고 다른 정황(문자열 암호화, 안티디버깅 등)과 함께 나타나는 경우가 많다. 우선 꼬리 호출부터 의심하는 게 합리적이다.

## 화면/코드에서 보이는 징후
```asm
funcA:
    push    rbp
    mov     rbp, rsp
    ; ... 처리 ...
    mov     ecx, eax        ; funcB의 인자를 세팅
    pop     rbp               ; 스택 프레임 정리 (leave 대신 수동으로)
    jmp     funcB              ; call funcB + ret 대신 이렇게 끝남 -> 꼬리 호출
```
IDA 함수 목록에서 `funcA`의 끝 주소가 이 `jmp` 명령이고, `funcA` 안에 `retn`이 아예 없다.

## 가장 먼저 할 것
`JMP`의 목표가 함수 범위 밖이라고 판단되면, 먼저 그 목표 주소가 **독립적인 함수의 시작 지점**인지 확인한다(IDA에서 목표 주소가 어떤 함수의 첫 명령인지). 맞다면 꼬리 호출일 가능성이 매우 높다.

## 단계별 절차
**1) JMP 직전 코드로 스택 프레임 정리 여부 확인**

`JMP` 바로 앞에 `leave`, `pop rbp`, `add rsp, N` 같은 스택 정리 코드가 있는지 본다. 있으면 "이 함수는 자기 볼일을 다 보고 나가는 것"이라는 신호다.

**2) JMP 목표가 다른 함수의 진짜 시작인지 확인**

목표 주소로 이동해서 그 주소가 어떤 함수의 첫 명령(보통 `push rbp` 등 프롤로그 시작)인지 확인한다. 맞으면 꼬리 호출이다.

**3) 디컴파일 결과로 교차 검증**

IDA/Ghidra의 F5 결과가 `return other_func(...);` 형태로 나오면 꼬리 호출로 확정할 수 있다.

**4) 디버거로 실제 반환 위치 확인**

동적으로 확인하고 싶다면, `funcA`를 호출한 지점에 브레이크포인트를 걸고 `funcA` 진입 시점의 반환 주소(스택 맨 위)를 기록해둔 뒤, `JMP funcB`를 넘어가서 `funcB`가 최종적으로 `RET`할 때 어디로 돌아가는지 확인한다 — 처음 기록해둔 `funcA`의 반환 주소와 같다면 꼬리 호출이 확정된다.

**5) Thunk/PLT와 구분**

함수 전체가 `JMP` 단 한 줄뿐이고 다른 처리가 전혀 없다면(스택 정리할 것도 없는 경우), Thunk 함수나 PLT 스텁일 가능성도 함께 고려한다.

## 명령어/단축키
- IDA: 함수 목록(`Functions` 창)에서 함수 끝 주소 확인, `Ctrl+E`(함수 청크/경계 관련 정보), `X`(Xrefs to)로 이 함수를 부르는 곳 확인
- Ghidra: 함수 우클릭 → "Function Graph"로 흐름 확인, Thunk 함수는 심볼 트리에 별도 아이콘으로 표시됨
- x64dbg/GDB: `JMP` 실행 후 `RSP`에 남아있는 반환 주소를 확인(`x/gx $rsp`)해서 원래 호출자로 이어지는지 검증

## 출력 해석
- `JMP` 목표가 다른 함수의 시작이고 그 직전에 스택 정리 코드가 있으면 → 꼬리 호출로 확정.
- `JMP` 목표가 같은 함수 안의 라벨(주소가 함수 범위 내부)이면 → 이건 그냥 일반적인 루프/분기이지 이 문서의 대상이 아니다.
- Ghidra가 함수를 "Thunk Function"으로 분류했으면 → 대체로 함수 전체가 다른 함수로의 단순 위임(꼬리 호출의 극단적 형태 또는 PLT류)이라는 뜻이다.

## 흔한 실수
- 함수 끝의 `JMP`를 보고 "역공학 도구가 함수 경계를 잘못 잡았다"고 단정해서 수동으로 억지로 이어붙이려는 것 — 실제로는 컴파일러가 의도적으로 만든 정상적인 꼬리 호출 최적화인 경우가 대부분이다.
- 꼬리 호출된 함수(`funcB`)를 분석할 때 "누가 이 함수를 불렀는지"를 `CALL` xref만으로 찾으려는 것 — 꼬리 호출은 `CALL`이 아니라 `JMP`이므로, IDA의 일반적인 "Xrefs to" 목록에 `JMP`로 인한 참조도 함께 나오는지 확인해야 한다(대부분 나오지만 필터 설정에 따라 놓칠 수 있음).
- 재귀 함수에서 꼬리 재귀 최적화가 적용된 경우, 디스어셈블리에 반복되는 `CALL`이 안 보여서 "재귀가 없는 함수"라고 오해하는 것 — 실제로는 `JMP`로 자기 자신을 다시 가리켜서(자기 자신의 시작 주소로 점프) 사실상 반복문처럼 동작하는 재귀다.
- 디버거로 `Step Over`(F8)를 눌렀는데 `JMP`가 다른 함수로 가버려서 "Step Over가 안 먹힌다"고 오해하는 것 — `Step Over`는 `CALL`에서만 "함수 끝까지 실행 후 다음 줄"로 동작하도록 설계되어 있고, `JMP`는 그냥 무조건 분기이므로 Step Over/Step Into 구분 없이 항상 그 목표로 이동하는 게 정상이다.

## 막혔을 때 다음 체크
- 꼬리 호출인지 확신이 안 서면 → 디버거로 실제 반환 주소를 추적해서 최종적으로 원래 호출자에게 돌아가는지 검증.
- PLT/Thunk와 헷갈리면 → 목표 함수가 임포트된 외부 라이브러리 함수인지(Imports 탭) 먼저 확인.
- 점프 테이블(switch문)과 헷갈리면 → REV-0441 참고, 이쪽은 함수 "내부"의 여러 케이스로 가는 것이라 범위를 벗어나지 않는다.
- CALL/RET/JMP의 기본 동작 자체가 헷갈리면 → REV-0071(CALL), REV-0072(RET), REV-0066(JMP) 복습.

## 미니 예제

**예제 1 — 전형적인 꼬리 호출**
```c
int wrapper(int x) {
    return real_impl(x + 1);
}
```
```asm
wrapper:
    lea     edi, [rdi+1]     ; x+1 계산 (인자 준비)
    jmp     real_impl          ; call real_impl + ret 대신 그냥 jmp
                                  ; real_impl이 끝나면 wrapper를 호출한 곳으로 바로 돌아감
```

**예제 2 — 꼬리 재귀가 반복문처럼 보이는 경우**
```c
int sum_tail(int n, int acc) {
    if (n == 0) return acc;
    return sum_tail(n - 1, acc + n);
}
```
```asm
sum_tail:
    test    ecx, ecx
    jz      base_case
    add     edx, ecx
    dec     ecx
    jmp     sum_tail        ; 재귀 호출이지만 CALL이 아니라 JMP -> 사실상 반복문
base_case:
    mov     eax, edx
    ret
```

**예제 3 — PLT 스텁과의 비교 (Linux ELF)**
```asm
; PLT 스텁 - 이것도 함수 전체가 JMP 하나
printf@plt:
    jmp     qword ptr [rip+GOT_printf]   ; GOT를 통해 실제 libc printf로 점프
```
이건 꼬리 호출이 아니라 동적 링킹 매커니즘이지만, "함수가 JMP 하나로 끝나서 밖으로 나간다"는 겉모습이 비슷해서 함께 알아두면 구분에 도움이 된다.

**예제 4 — IDA에서 확인하는 절차 예시**
```text
1) funcA의 마지막 명령: jmp funcB
2) funcB로 더블클릭 이동 -> funcB가 독립된 함수로 정의돼 있고 push rbp로 시작함 확인
3) F5로 funcA 디컴파일 -> "return funcB(a1);" 형태로 나오면 꼬리 호출 확정
```

## 관련 글
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0072 — RET: 함수 반환과 스택 변화
- REV-0066 — JMP: 무조건 분기
- REV-0441 — Switch문 점프 테이블(Jump Table) 완전 분석
- REV-0495 — 인라인된 함수 때문에 CALL이 하나도 없는 함수를 만났을 때

## 출처/검증
- 꼬리 호출 최적화(Tail Call Optimization)의 컴파일러 구현 개념: GCC 공식 문서(`-foptimize-sibling-calls`) 및 LLVM 공식 문서(Tail Call Optimization) 기준 (2026-09-08 검증).
- `JMP`가 스택을 건드리지 않는다는 성질과 `CALL`/`RET`의 대응 관계: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "JMP" 및 "CALL/RET" 섹션 기준.
- IDA의 Function Chunk, Ghidra의 Thunk Function 개념: Hex-Rays IDA 공식 문서 및 Ghidra 공식 문서(Thunk Functions) 기준.
