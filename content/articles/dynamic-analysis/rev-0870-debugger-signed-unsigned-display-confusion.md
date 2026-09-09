---
id: REV-0870
title: "디버거 값 표시가 Signed/Unsigned로 헷갈려서 잘못 판단할 때"
slug: "rev-0870-debugger-signed-unsigned-display-confusion"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg, IDA]
keywords:
  - signed unsigned 디버거 표시
  - p vs p/x 차이
  - x64dbg 레지스터 signed 전환
  - 음수인데 큰 양수로 보임
  - decimal hex 표시 헷갈림
symptom_keywords:
  - 레지스터 값이 엄청 큰 양수로 나옴
  - 분명 음수인데 이상한 숫자
  - p랑 p/x 결과가 다름
  - 이 값이 음수인지 양수인지 모르겠음
aliases:
  - 디버거 signed unsigned 헷갈림
  - 레지스터 값 부호 착각
  - x64dbg 값 표시 전환
  - GDB print 부호 문제
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
CPU 레지스터와 메모리에는 부호 정보가 따로 저장되지 않고 그냥 비트 패턴만 있으므로, 같은 값이라도 디버거가 그것을 signed로 해석해서 보여주는지 unsigned로 해석해서 보여주는지에 따라 완전히 다른 숫자로 보이며, 이 표시 방식을 안 바꾸고 그대로 판단하면 "음수 비교"를 "말도 안 되게 큰 양수"로 착각해 로직을 잘못 이해하게 된다.

## 언제 검색해야 하나
- 디버거 레지스터 창에 `0xFFFFFFFF`나 `4294967295`처럼 이상하게 큰 값이 보이는데, 코드 로직상 이 값이 `-1`이어야 할 것 같을 때
- GDB에서 `p $eax`와 `p/x $eax`, `p (int)$eax`의 결과가 서로 다르게 나와서 어떤 걸 믿어야 할지 헷갈릴 때
- x64dbg 레지스터 창에서 우클릭했을 때 "Signed"/"Unsigned"/"Hex" 같은 표시 옵션이 있는 걸 처음 봤을 때
- IDA 디컴파일 결과의 자료형(`int` vs `unsigned int`)과 디버거가 보여주는 값이 안 맞아 보일 때

## 핵심 개념

### CPU는 부호를 저장하지 않는다
x86/x64 레지스터와 메모리는 그냥 비트 나열일 뿐이며, "이 비트 패턴을 signed로 읽을지 unsigned로 읽을지"는 그 값을 사용하는 명령어(예: `IDIV`/`DIV`, `JG`/`JA`, REV-0482 참고)와 그것을 보여주는 도구(디버거, 디컴파일러)의 해석에 달려 있다. 32비트 값 `0xFFFFFFFF`는 unsigned로 읽으면 `4294967295`이고, signed(2의 보수)로 읽으면 `-1`이다(REV-0024 참고). 둘 다 "맞는" 해석이며, 어느 쪽이 맥락에 맞는지는 그 값이 어떤 자료형으로 쓰이고 있었는지에 달려 있다.

### x64dbg에서 표시 방식 바꾸기
x64dbg의 레지스터 창은 기본적으로 16진수(Hex)로 값을 보여준다. 레지스터를 우클릭하면 "Signed"/"Unsigned"/"Hex" 등으로 표시 형식을 바꿀 수 있는 메뉴가 있으며, 원하는 해석으로 바꿔서 확인하면 된다. 스택/덤프 창에서도 마찬가지로 특정 크기(byte/word/dword/qword)와 부호를 지정해서 볼 수 있다.

### GDB에서 표시 방식 다루기
GDB의 `print`(`p`) 명령은 기본적으로 레지스터를 **부호 있는 정수**로 해석해서 출력한다(`p $eax`는 음수면 음수로 나온다). 반면 `p/x`는 16진수로, `p/u`는 unsigned 10진수로 출력한다. 정확한 자료형으로 캐스팅해서 보고 싶다면 C 캐스트 문법을 그대로 쓸 수 있다.
```
p (int)$eax        ; signed 32비트로 해석
p (unsigned int)$eax  ; unsigned 32비트로 해석
p (short)$ax        ; signed 16비트로 해석
```
비트 폭을 착각하면(예: 64비트 레지스터를 32비트인 것처럼 캐스팅) 잘못된 부호 판정이 나올 수 있으므로, 원래 소스 자료형의 정확한 크기와 부호를 먼저 확인하고 캐스팅해야 한다(REV-0369, REV-0370 참고).

### 어떤 상황에서 특히 조심해야 하는가
- `IMUL`/`IDIV` 결과를 볼 때(signed 연산이므로 signed로 해석해야 함, REV-0053/REV-0052 참고)
- `jg`/`jl`(signed 분기)와 `ja`/`jb`(unsigned 분기)가 같은 `cmp` 결과를 다르게 판단하는 경우(REV-0088, REV-0174 참고)
- 함수의 리턴값이 `int`가 아니라 `unsigned int`/`size_t`인데 무심코 signed로 해석해서 "음수가 리턴됐다"고 오해하는 경우

## 화면/코드에서 보이는 징후
- 레지스터 값이 `0xFFFFFFF6`처럼 앞자리가 `F`로 가득한데, 이를 그대로 큰 양수로 받아들이고 "왜 이렇게 큰 값이 나왔지"라며 로직을 오해한다.
- GDB `p $eax` 결과는 `-10`인데, 같은 값을 `p/x $eax`로 보면 `0xfffffff6`으로 나와서 두 표시가 다른 값처럼 느껴진다(사실 같은 비트 패턴이다).
- `cmp`/`test` 뒤의 분기가 `jg`(signed)인데, unsigned 기준으로 값을 해석해서 "이 조건은 절대 참이 될 수 없다"고 잘못 결론짓는다.

## 가장 먼저 할 것
1. 지금 보고 있는 값이 signed 자료형에서 온 것인지 unsigned 자료형에서 온 것인지, 소스/디컴파일 코드의 자료형부터 확인한다.
2. 디버거의 표시 형식을 그 자료형에 맞게 명시적으로 바꿔서 다시 본다.
3. 그 값이 쓰이는 다음 명령어(`Jcc`, `IDIV`/`DIV` 등)가 signed 연산인지 unsigned 연산인지 함께 확인한다.

## 단계별 절차

**x64dbg**
1. 레지스터 창에서 확인하려는 레지스터를 우클릭한다.
2. "Signed"/"Unsigned"/"Hex" 중 원하는 표시 방식을 선택한다.
3. 스택/덤프 창에서도 값 하나를 우클릭해 크기(1/2/4/8바이트)와 부호를 지정해서 확인할 수 있다.

**GDB / Pwndbg**
1. 기본 `print`는 이미 signed로 보여준다는 것을 기억한다.
   ```
   p $eax
   ```
2. unsigned로 명시적으로 다시 보고 싶다면 `/u` 포맷이나 캐스팅을 쓴다.
   ```
   p/u $eax
   p (unsigned int)$eax
   ```
3. 16진수(부호와 무관한 순수 비트 패턴)로 항상 같이 확인하는 습관을 들인다.
   ```
   p/x $eax
   ```
4. 비트 폭이 다른 레지스터(예: `AL`, `AX`, `EAX`, `RAX`)를 볼 때는 정확한 크기로 캐스팅해서 확인한다.

## 명령어/단축키
- x64dbg: 레지스터 창 우클릭 → Signed/Unsigned/Hex, Dump 창 우클릭 → 크기/부호 지정
- GDB/Pwndbg: `p $reg`(signed), `p/x $reg`(hex), `p/u $reg`(unsigned), `p (int)$reg`, `p (unsigned int)$reg`, `p (short)$reg`

## 출력 해석
- `0xFFFFFFFF`(hex) = `4294967295`(unsigned 32비트) = `-1`(signed 32비트) — 이 세 표기는 전부 **같은 비트 패턴**을 다르게 읽은 것뿐이다.
- GDB `p $eax`가 음수를 보여줬다면, 그 레지스터의 최상위 비트(부호 비트)가 1이라는 뜻이다.

## 흔한 실수
- 16진수 값의 앞자리가 `F`로 시작하면 무조건 "이상한 값"이라 여기고, 음수일 가능성을 확인하지 않는 것.
- signed/unsigned 표시를 안 바꾸고 기본값만 보고 판단해서, 정작 그 값이 어떤 분기(`jg` vs `ja`)에 쓰이는지는 확인하지 않는 것.
- 캐스팅할 때 비트 폭을 실제 레지스터 폭과 다르게 지정해서(예: 64비트 값을 16비트로 캐스팅) 엉뚱한 결과를 얻는 것.

## 막혔을 때 다음 체크
- signed/unsigned 분기 자체의 판단 기준이 헷갈린다면 → REV-0174, REV-0088을 참고한다.
- 값 자체는 맞게 읽었는데 로직이 여전히 이해 안 된다면 → REV-0867(조건 분기 직전 값이 예상과 다를 때)을 참고한다.
- 최대/최소값 범위가 헷갈린다면 → REV-0370(정수 자료형 최대/최소값 치트시트)을 참고한다.

## 미니 예제
```
(gdb) p $eax
$1 = -10
(gdb) p/x $eax
$2 = 0xfffffff6
(gdb) p/u $eax
$3 = 4294967286
```
세 출력 모두 같은 레지스터의 같은 순간 값이며, 단지 해석 방식만 다르다. 이 값이 `int` 반환형 함수의 에러 코드(`-10`)로 쓰인다면 signed로 읽는 것이 맞고, `size_t` 같은 unsigned 자료형이라면 unsigned로 읽는 것이 맞다.

## 관련 글
- REV-0867 — 조건 분기 직전 값이 예상과 달라서 로직을 오해할 때
- REV-0174 — 조건 분기 직전에 무엇을 봐야 하는가

## 출처/검증
- 2의 보수 표현과 signed/unsigned 해석 차이: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 1, "Integer Registers" 및 "Operands" 섹션 기준.
- GDB `print` 명령의 기본 정수 출력 방식과 포맷 지정자(`/x`, `/u`): GNU GDB 공식 매뉴얼 "Output Formats" 섹션 기준.
- x64dbg 레지스터 표시 형식 전환(Signed/Unsigned/Hex): x64dbg 공식 문서(Registers) 기준.
- 2026-09-09 검증.
