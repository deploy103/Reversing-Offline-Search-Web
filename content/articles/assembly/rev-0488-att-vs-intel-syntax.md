---
id: REV-0488
title: "어셈블리 니모닉이 도구마다 다르게 표기될 때(AT&T vs Intel)"
slug: "rev-0488-att-vs-intel-syntax"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - AT&T syntax
  - Intel syntax
  - att 문법
  - 인텔 문법
  - objdump att
  - gdb att syntax
  - "%rax"
  - "movl %eax, %ebx"
  - "mov eax, ebx"
  - set disassembly-flavor
  - objdump -M intel
  - 오퍼랜드 순서 반대
aliases:
  - att랑 intel 문법 차이
  - gdb에서 니모닉이 이상하게 나옴
  - objdump 결과가 IDA랑 다름
  - 퍼센트 기호 레지스터
  - 오퍼랜드 순서가 반대로 나옴
symptom_keywords:
  - gdb 디스어셈블리가 IDA랑 순서가 반대임
  - 레지스터 앞에 퍼센트 기호가 붙어 나옴
  - objdump 결과에 movl movq처럼 l q가 붙어 나옴
  - 목적지 소스 순서가 헷갈림
  - att 문법을 intel로 바꾸는 법을 모름
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
같은 명령인데 GDB/objdump의 기본 출력과 IDA/Ghidra/x64dbg의 출력이 다르게 보이는 이유는 어셈블리 표기법이 **AT&T 문법**과 **Intel 문법** 두 가지로 나뉘어 있기 때문이며, 오퍼랜드 순서가 반대이고 레지스터에 `%`가 붙고 크기 접미사(`l`, `q` 등)가 붙는 차이만 알면 바로 서로 변환해서 읽을 수 있다.

## 언제 검색해야 하나
- Linux에서 `objdump -d`나 GDB로 디스어셈블리를 봤는데 IDA에서 본 것과 오퍼랜드 순서가 반대로 보일 때
- `movl %eax, %ebx`, `subq $0x10, %rsp` 처럼 레지스터 앞에 `%`가 붙고 명령어 끝에 `l`/`q`/`b`/`w` 같은 글자가 붙어 있어서 니모닉이 이상해 보일 때
- 어디서는 `mov eax, ebx`(목적지가 먼저), 어디서는 `mov %ebx, %eax`(소스가 먼저)처럼 같은 의미인데 표기가 반대로 보일 때
- GDB에서 디스어셈블리 문법을 Intel 스타일로 바꾸는 설정을 찾고 있을 때

## 핵심 개념

### 두 문법 체계가 왜 존재하는가
x86 어셈블리를 텍스트로 표기하는 방식은 하나가 아니다. 크게 두 진영이 있다.
- **Intel 문법**: 인텔이 공식 매뉴얼에서 쓰는 표기법. IDA, Ghidra, x64dbg, MASM, NASM(옵션), 대부분의 Windows 리버싱 도구가 기본으로 이 문법을 쓴다.
- **AT&T 문법**: 유닉스 계열 툴체인(GNU 어셈블러 `gas`, `objdump`, GDB)에서 전통적으로 써 온 표기법. Linux에서 `objdump -d`나 `gdb`를 기본 설정으로 쓰면 이 문법이 나온다.

같은 CPU 명령을 표현하는 것이므로 의미는 완전히 동일하다 — 그냥 **문자로 적는 규칙**이 다를 뿐이다.

### 핵심 차이 3가지

**1) 오퍼랜드 순서가 정반대다.**
- Intel: `mov destination, source` (목적지가 먼저)
- AT&T: `mov source, destination` (소스가 먼저)

```
Intel: mov eax, ebx     ; ebx의 값을 eax로 복사 (eax = ebx)
AT&T:  mov %ebx, %eax   ; 똑같이 ebx의 값을 eax로 복사 (eax = ebx)
```
두 줄은 **완전히 같은 명령**이다. 순서만 반대로 적었을 뿐이다. 이 차이를 모르고 AT&T 문법을 Intel처럼 읽으면(또는 반대로) "소스와 목적지를 반대로 해석"하는 치명적인 실수를 하게 된다.

**2) 레지스터/즉시값 표기에 접두사가 붙는다.**
- AT&T: 레지스터 앞에 `%`(예: `%rax`, `%eax`), 즉시값(리터럴 상수) 앞에 `$`(예: `$0x10`)
- Intel: 레지스터는 그냥 이름만(`rax`, `eax`), 즉시값도 접두사 없이 숫자만(`10h` 또는 `0x10`)

```
AT&T:  mov $0x10, %eax     ; eax = 0x10
Intel: mov eax, 10h        ; eax = 0x10 (같은 의미)
```

**3) 명령어에 오퍼랜드 크기를 나타내는 접미사가 붙는다.**
AT&T는 오퍼랜드에 크기 정보가 레지스터 이름만으로 항상 드러나지 않는 경우(특히 메모리 오퍼랜드)를 위해 니모닉 끝에 크기 접미사를 붙인다:
```
b = byte (8비트)
w = word (16비트)
l = long/doubleword (32비트)
q = quadword (64비트)
```
```
AT&T:  movl   $0x0, -0x4(%rbp)     ; 32비트 0을 [rbp-4]에 저장
Intel: mov    dword ptr [rbp-4], 0  ; 같은 의미, Intel은 "dword ptr"로 크기를 명시
```

**4) 메모리 오퍼랜드(주소 지정) 표기도 다르다.**
```
AT&T:  -0x8(%rbp,%rax,4)
Intel: [rbp+rax*4-8]
```
공식은 동일하다 `base + index*scale + disp`. AT&T는 괄호 앞에 변위(disp)를 적고 괄호 안에 `(base, index, scale)` 순서로 콤마로 구분해서 적는다. Intel은 대괄호 안에 산술식처럼 그대로 적는다.

### 빠른 변환 표
| 항목 | Intel | AT&T |
|---|---|---|
| 순서 | `op dst, src` | `op src, dst` |
| 레지스터 | `eax` | `%eax` |
| 즉시값 | `10h` | `$0x10` |
| 메모리 | `[rbp-4]` | `-4(%rbp)` |
| 크기 명시 | `dword ptr [...]` | 니모닉 접미사(`l` 등) |
| 인덱스 주소 | `[rbp+rax*4-8]` | `-8(%rbp,%rax,4)` |

### 도구별 기본값
| 도구 | 기본 문법 | 변경 방법 |
|---|---|---|
| IDA | Intel | Options → General → Disassembly → "Use assembler..."에서 변경 가능(기본은 거의 항상 Intel 유지) |
| Ghidra | Intel | 기본적으로 Intel 스타일로 표시 |
| x64dbg | Intel | 기본이 Intel, 별도 설정 거의 불필요 |
| GDB | **AT&T가 기본** | `set disassembly-flavor intel` 로 변경 가능 |
| objdump | **AT&T가 기본** | `objdump -d -M intel <파일>` 로 변경 가능 |
| pwndbg/GEF (GDB 확장) | 대부분 Intel로 기본 설정되어 있음 | 확장이 자동으로 `set disassembly-flavor intel`을 실행해두는 경우가 많음(확장별로 다르므로 확인 필요) |

**실전 팁**: 순정 GDB나 `objdump`를 쓰다가 오퍼랜드 순서 때문에 헷갈린다면, 매번 변환하며 읽지 말고 아예 처음부터 Intel 문법으로 출력되도록 설정을 바꿔서 IDA/x64dbg와 표기를 통일하는 것이 실수를 줄이는 가장 확실한 방법이다.

## 화면/코드에서 보이는 징후
```text
# objdump -d (AT&T, 기본값)
401136:  48 89 c3        mov    %rax,%rbx
401139:  83 c0 05        add    $0x5,%eax
40113c:  8b 45 fc        mov    -0x4(%rbp),%eax

# objdump -d -M intel (같은 코드, Intel 문법)
401136:  48 89 c3        mov    rbx,rax
401139:  83 c0 05        add    eax,0x5
40113c:  8b 45 fc        mov    eax,[rbp-0x4]
```
두 출력은 **완전히 같은 바이너리, 같은 명령**이다. 오퍼랜드 순서와 표기 방식만 다를 뿐이다.

## 가장 먼저 할 것
지금 보고 있는 디스어셈블리가 어느 문법인지부터 확정한다.
1. 레지스터 앞에 `%`가 붙어 있는가? → AT&T
2. 오퍼랜드 두 개 중 어느 쪽이 목적지인지 헷갈린다면 → `%`가 있으면 AT&T(소스, 목적지 ���서), 없으면 Intel(목적지, 소스 순서)로 판단

## 단계별 절차
**1) GDB를 Intel 문법으로 바꾸기 (가장 실용적인 해결책)**
```text
(gdb) set disassembly-flavor intel
(gdb) disassemble
```
`.gdbinit` 파일(홈 디렉터리 또는 프로젝트 폴더의 `~/.gdbinit`)에 이 줄을 추가해두면 매번 다시 설정할 필요가 없다.

**2) objdump를 Intel 문법으로 바꾸기**
```bash
objdump -d -M intel ./binary
```

**3) 문법을 바꿀 수 없는 상황이면 수동 변환**
AT&T 코드를 읽어야 하는데 설정을 못 바꾸는 상황(예: 다른 사람이 캡처한 로그를 볼 때)이라면, 위의 "빠른 변환 표"를 기준으로 오퍼랜드 순서를 뒤집고 `%`/`$` 접두사를 제거하면서 읽는다.

**4) 크기 접미사 해석**
AT&T에서 `movl`, `movq`, `movb`, `movw`처럼 접미사가 붙은 명령을 보면, 접미사를 떼고 오퍼랜드 크기를 별도로 확인한다는 느낌으로 Intel의 `dword ptr`/`qword ptr`/`byte ptr`/`word ptr`에 대응시킨다.

## 명령어/단축키
- GDB: `set disassembly-flavor intel`(영구 적용하려면 `.gdbinit`에 추가), `show disassembly-flavor`(현재 설정 확인)
- objdump: `objdump -d -M intel <파일>` (Intel), `objdump -d <파일>` (AT&T, 기본값)
- IDA: Options → General → "Number of opcode bytes"/Disassembly 탭에서 문법 관련 설정 확인(기본이 Intel이라 거의 건드릴 일 없음)
- radare2/rizin: `e asm.syntax=intel` 또는 `e asm.syntax=att`로 전환 가능

## 출력 해석
- `mov %rax, %rbx` (AT&T) = `mov rbx, rax` (Intel) — 둘 다 "rax의 값을 rbx로 복사"라는 뜻이다. AT&T만 보고 "rax에 rbx를 넣는다"고 반대로 읽으면 데이터 흐름을 완전히 거꾸로 해석하게 되므로 주의한다.
- `sub $0x20, %rsp` (AT&T) = `sub rsp, 0x20` (Intel) — 스택 20h(32)바이트 확보, 함수 프롤로그에서 흔히 보이는 패턴.
- `call 0x401230 <func_name>` — 이건 두 문법에서 표기가 거의 동일하다(호출 규약이나 함수 이름 표시 방식은 문법과 무관).

## 흔한 실수
- AT&T 문법을 Intel처럼 "첫 번째가 목적지"로 착각하고 데이터 흐름을 반대로 해석하는 것 — 리버싱 초기에 가장 흔하게 발생하는 혼동이다.
- GDB로 디버깅하다가 IDA에서 본 것과 오퍼랜드 순서가 달라서 "바이너리가 다르다" 또는 "버그다"라고 오해하는 것 — 실제로는 같은 코드를 다른 문법으로 보여주는 것뿐이다.
- 크기 접미사(`movl`, `movq`)를 명령어 이름의 일부(별도 명령)로 착각하는 것 — `mov`에 크기 정보만 추가된 것이지 `MOVL`이라는 별도 명령이 존재하는 게 아니다.
- 매번 두 문법을 머릿속으로 변환하며 읽으려다 시간을 낭비하는 것 — `set disassembly-flavor intel` 한 줄이면 해결되는 문제를 매번 수동으로 변환하는 건 비효율적이다.

## 막혔을 때 다음 체크
- GDB 출력이 계속 AT&T로 나온다면 → `show disassembly-flavor`로 현재 설정 확인 후 다시 `set disassembly-flavor intel` 실행, `.gdbinit`에 저장됐는지 확인.
- pwndbg/GEF/peda 같은 확장을 쓰는데도 AT&T가 나온다면 → 확장 자체의 설정 파일이나 환경변수를 확인(확장에 따라 GDB 기본 설정을 덮어쓰는 경우가 있음).
- 오퍼랜드 순서가 아직도 헷갈린다면 → "AT&T는 사람이 말하듯 소스에서 목적지로(source to dest), Intel은 수학식처럼 결과를 먼저(dest = src)"라는 문장으로 암기.

## 미니 예제

**예제 1 — 같은 함수 프롤로그, 두 문법 비교**
```text
AT&T:
push   %rbp
mov    %rsp,%rbp
sub    $0x20,%rsp

Intel:
push   rbp
mov    rbp, rsp
sub    rsp, 0x20
```
둘 다 "RBP를 저장하고, RSP를 RBP에 복사하고, 지역변수 공간 0x20을 확보"하는 완전히 동일한 코드다.

**예제 2 — 메모리 오퍼랜드 비교**
```text
AT&T:  mov    -0x18(%rbp,%rax,8),%rcx
Intel: mov    rcx, [rbp+rax*8-0x18]
```
`RBP + RAX*8 - 0x18` 주소에서 8바이트를 읽어 `RCX`에 넣는, 배열 인덱싱(`array[i]`)의 전형적인 형태다.

**예제 3 — 조건 분기 비교 (거의 차이 없음)**
```text
AT&T:  cmp    $0xa,%eax
       jne    0x401050
Intel: cmp    eax, 0xa
       jne    0x401050
```
`Jcc` 계열은 오퍼랜드가 주소(레이블) 하나뿐이라 순서 문제가 없어서 두 문법의 표기 차이가 크지 않다.

**예제 4 — GDB에서 직접 전환해보기**
```text
(gdb) disassemble main
   0x0000000000401136 <+0>:  push   %rbp
   0x0000000000401137 <+1>:  mov    %rsp,%rbp
(gdb) set disassembly-flavor intel
(gdb) disassemble main
   0x0000000000401136 <+0>:  push   rbp
   0x0000000000401137 <+1>:  mov    rbp,rsp
```

## 관련 글
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0039 — MOV: 값 복사와 레지스터 메모리 이동
- REV-0042 — LEA: 주소 계산인데 왜 산술 연산처럼 보이는가

## 출처/검증
- AT&T 문법과 Intel 문법의 오퍼랜드 순서·접두사·크기 접미사 차이: GNU Binutils(`as`, `objdump`) 공식 문서 및 GNU Assembler Manual "i386-Syntax" 섹션 기준 (2026-09-08 검증).
- GDB `disassembly-flavor` 설정: GNU GDB 공식 매뉴얼, "Configuring the Current ABI" / "x86 Disassembly Options" 기준.
- Intel 문법(레지스터/즉시값/크기 표기): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2, "Instruction Format" 및 어셈블러 관례 기준.
