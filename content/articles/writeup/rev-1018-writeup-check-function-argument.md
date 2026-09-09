---
id: REV-1018
title: "[Write-up] Check Function Argument"
slug: "rev-1018-writeup-check-function-argument"
category: "writeup"
difficulty: "basic"
platform: [linux]
architecture: [x64]
format: [ELF]
tools: [IDA, GDB, pwndbg]
keywords: ["dreamhack Check Function Argument", "드림핵 Check Function Argument", "sub_4015E2", "argv 리버싱"]
aliases: ["Check Function Argument 풀이", "체크 펑션 아규먼트", "dreamhack check function argument flag"]
symptom_keywords: ["Check Function Argument에서 sub_4015E2 안이 비어있음", "x32/x64로 안열리는 드림핵 리버싱 바이너리"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
플래그를 프로그램 실행 시 명령줄 인자(argv)로 넘겨야 하는 문제로, main에서 인자를 검증 함수에 넘기는 부분까지는 정적 분석으로 쉽게 보이지만 검증 함수 내부가 사실상 비어 있어 결국 pwndbg로 특정 주소에 브레이크포인트를 걸고 레지스터 값을 관찰하는 동적 분석으로 넘어가야 풀리는 문제다.

## 언제 검색해야 하나
- IDA에서 main을 열었더니 `sub_4015E2(qword_4040D0, a2)`처럼 두 번째 인자로 `a2`(argv)를 그대로 넘기는 호출이 보일 때
- 인자를 받는 함수 안으로 들어갔는데 코드가 거의 없어서 "이게 다야?" 싶을 때
- objdump나 x64dbg로 파일을 열려는데 32비트/64비트 뷰 어느 쪽으로도 제대로 안 열려서 당황스러울 때
- "Check Function Argument"라는 제목처럼, 함수에 어떤 인자가 들어가는지 직접 확인해야 하는 상황

## 핵심 개념

### argv를 그대로 검증 함수에 넘기는 구조
main(argc, argv, envp) 형태에서 argv(코드상 a2)를 그대로 다음 함수의 인자로 전달하는 패턴은 "이 프로그램은 커맨드라인에 값을 넘겨서 실행해야 한다"는 신호다(REV-0108 참고). 이 문제도 main이 puts로 안내 문구를 출력한 뒤 인자를 검증 함수로 그대로 넘기는 구조를 갖고 있어, 실행할 때 `./chall <추정 플래그>` 형태로 인자를 주는 것이 전제 조건이 된다.

### 정적 분석이 막히면 동적 분석으로 전환
검증 함수 내부를 IDA로 디컴파일했을 때 의미 있는 로직이 거의 안 보이는 경우가 있다. 이런 상황은 컴파일러 최적화, 인라인 처리, 혹은 진짜로 단순히 인자를 레지스터에 반영만 하고 끝나는 짧은 함수일 때 생긴다. 정적 디컴파일 결과가 부족하면 다음 전략은 GDB/pwndbg로 그 함수 근처에 브레이크포인트를 걸고 실제 실행 중 레지스터·메모리 값을 관찰하는 것이다. x86-64 System V 호출 규약에서 함수의 첫 번째 인자는 RDI, 두 번째는 RSI에 들어가고(REV-0071 참고), 함수의 반환값은 RAX에 담긴다. 브레이크포인트를 검증 함수 호출 직후 또는 함수 안의 특정 지점(이 문제의 경우 0x401612 부근)에 걸어 두면 그 시점에 RAX나 관련 레지스터에 어떤 값이 만들어지는지 직접 눈으로 확인할 수 있다.

### pwndbg가 필요한 이유
일반 GDB만으로는 레지스터와 메모리를 매번 수동 명령으로 조회해야 해서 번거롭다. pwndbg는 브레이크포인트에 걸릴 때마다 레지스터, 스택, 어셈블리, 디스어셈블리를 한 화면에 자동으로 정리해서 보여주므로, "이 브레이크포인트에서 무슨 값이 어떻게 바뀌는지"를 빠르게 파악하는 데 특히 유리하다.

## 화면/코드에서 보이는 징후
- main에서 `puts("... takes the flag as an argument ...")` 계열 안내 문구 출력
- 검증 함수 호출 시 두 번째 인자가 `argv`(a2) 그 자체
- 검증 함수 내부 디컴파일 결과가 이상하게 짧거나 의미 없어 보임
- 파일이 objdump/전형적인 x32dbg 뷰로 깔끔하게 안 열리는 느낌(리틀 엔디언 표기, 심볼 손상 등)

## 가장 먼저 할 것
`./chall aaaa`처럼 아무 인자나 넣어서 일단 프로그램을 실행해보고 결과 메시지가 어떻게 달라지는지 관찰한다. 그 다음 IDA에서 main의 인자 전달 구조를 확인해 검증 함수 주소를 특정하고, pwndbg를 연결해 그 함수 부근에 브레이크포인트를 건다.

## 단계별 절차
1. `checksec ./chall`, `file ./chall`로 아키텍처와 보호 기법을 먼저 확인한다.
2. IDA로 main을 디컴파일해 검증 함수 이름과 호출 시 넘기는 인자를 확인한다.
3. 검증 함수 내부를 봐서 의미 있는 로직이 보이면 정적 분석으로 끝내고, 안 보이면 4번으로 넘어간다.
4. `gdb ./chall`, pwndbg 로드 후 `run <임의의 인자>`로 실행하고 검증 함수 근처(예: 특정 오프셋)에 `break *0x401612`처럼 주소 기반 브레이크포인트를 건다.
5. 브레이크포인트에 걸리면 `info registers` 또는 pwndbg의 레지스터 표시로 rax 등 관련 레지스터 값을 확인한다.
6. 관찰한 값이 인자와 어떤 관계인지(비교값인지, 가공된 값인지) 추정하고, 그 관계를 이용해 올바른 인자를 역산한다.
7. 역산한 값을 실제 프로그램 인자로 넣어 재실행하며 결과를 검증한다.

## 명령어/단축키
```bash
file ./chall
checksec --file=./chall
gdb ./chall
(gdb) break *0x401612
(gdb) run AAAAAAAA
(gdb) info registers rax
```
pwndbg 사용 시 브레이크포인트에 걸리면 자동으로 레지스터/스택/디스어셈블리 창이 출력되므로 별도 명령 없이 값을 확인할 수 있다.

## 출력 해석
`info registers rax` 출력이 어떤 값이든, 그 값을 인자 문자열의 특정 바이트나 가공 결과와 비교해 보는 것이 핵심이다. 브레이크포인트 위치를 검증 로직 시작 지점보다 너무 앞이나 뒤에 걸면 의미 없는 값만 보이므로, 여러 지점에 나눠 걸어보며 값이 "언제" 의미 있게 바뀌는지 좁혀가야 한다.

## 흔한 실수
- 정적 디컴파일 결과가 비어 보인다고 바로 포기하는 것 — 인라인/최적화로 짧아진 것일 수 있으니 어셈블리 레벨(Disassembly view)까지 확인해야 한다.
- 인자를 안 주고 그냥 실행해서 "왜 아무 반응이 없지" 하고 헷갈리는 것 — 이 문제는 애초에 인자 없이 실행하면 검증 로직 자체가 별 의미 없는 경로를 탄다.
- pwndbg 브레이크포인트 주소를 ASLR 때문에 매번 다르게 계산해야 하는 PIE 바이너리에서 고정 주소로만 걸다가 안 걸리는 것 — PIE라면 베이스 주소를 먼저 확인해야 한다.

## 막혔을 때 다음 체크
- argv가 어셈블리에서 어떻게 스택/레지스터에 실리는지 기억이 안 나면 REV-0108 argc argv envp를 어셈블리에서 찾는 법을 본다.
- CALL 인자 전달 규칙(RDI/RSI/RDX...) 자체가 헷갈리면 REV-0071 CALL: 함수 호출, 반환 주소, 인자 추적을 본다.
- GDB에서 인자를 넘겨 실행하는 방법이 기억 안 나면 REV-0185 GDB 실행 run start args 사용법을 본다.
- 반환값을 어디서 확인하는지 헷갈리면 REV-1019 [Write-up] Check Return Value(같은 시리즈, 반환값 확인이 핵심인 문제)를 이어서 본다.

## 미니 예제
```c
// main의 구조를 새로 서술한 예시(실제 디스어셈블리 그대로가 아님)
int main(int argc, char **argv, char **envp) {
    puts("Below function takes the flag as an argument :)");
    check(some_global, argv);
    puts("Can you see that?");
}
```
`check` 내부가 정적으로 비어 보여도, `break`로 그 함수 근처에 멈춰서 레지스터를 보면 실제로 무슨 값이 만들어지는지 알 수 있다.

## 관련 글
- REV-0108 — argc argv envp를 어셈블리에서 찾는 법
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0185 — GDB 실행 run start args 사용법
- REV-1019 — [Write-up] Check Return Value

## 출처/검증
- 드림핵 워게임 Check Function Argument의 카테고리(reversing)·티어(Bronze 3)·풀이자 수(845명)는 dreamhack.io/wargame/challenges?tag=reversing 페이지 직접 조회로 확인됨(2026-09-10).
- 기술적 접근(main에서 sub_4015E2에 argv를 그대로 넘기는 구조, 정적 분석이 막혀 pwndbg로 0x401612 부근에서 rax를 관찰하는 흐름)은 velog.io/@danmuginima 의 "Dreamhack Check Function Argument" 글을 참고해 새 문장으로 재구성했다. 원문의 표현이나 전체 코드를 그대로 옮기지 않았다.
