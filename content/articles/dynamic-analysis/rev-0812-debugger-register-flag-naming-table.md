---
id: REV-0812
title: "디버거별 레지스터/플래그 표시 명칭 대조표"
slug: "rev-0812-debugger-register-flag-naming-table"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg, WinDbg]
keywords: ["gdb eflags", "x64dbg flags", "windbg flags iopl", "레지스터 이름 비교", "플래그 표시 명칭", "zr nz pl ng cy nc"]
aliases: ["디버거 레지스터 이름표", "디버거 플래그 표기 비교", "gdb x64dbg windbg 플래그 차이"]
symptom_keywords: ["gdb eflags 출력이 windbg랑 다르게 생김", "windbg에서 zr pl cy가 뭔지 모름", "x64dbg 플래그창 표기가 헷갈림", "디버거마다 플래그 이름이 달라서 헷갈림", "eflags랑 rflags 차이 모름"]
source_ids: ["SRC-GDB-DOCS", "SRC-X64DBG-DOCS", "SRC-WINDBG-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
같은 x86/x64 EFLAGS/RFLAGS 레지스터라도 GDB는 "현재 세트(set)된 플래그 이름만" 대괄호 안에 나열하고, x64dbg는 각 플래그를 체크박스가 붙은 개별 행으로 보여주며, WinDbg는 "설정/해제 상태를 각각 다른 두 글자 약어"로 표시한다 — 셋 다 결국 같은 비트를 가리키지만 화면에 찍히는 문자열이 완전히 다르다.

## 언제 검색해야 하나
- GDB의 `eflags 0x246 [ PF ZF IF ]` 출력이 WinDbg의 `iopl=0 nv up ei pl zr na po nc`와 대응이 안 돼서 헷갈릴 때
- WinDbg에서 `zr`, `pl`, `cy` 같은 두 글자 약어가 어떤 플래그의 어떤 상태를 뜻하는지 모를 때
- x64dbg 레지스터 패널의 플래그 체크박스 이름이 어떤 EFLAGS 비트에 대응하는지 확인하고 싶을 때
- 툴 문서/CTF 라이트업을 넘나들며 같은 레지스터를 가리키는 다른 표기(RAX vs rax, EFLAGS vs Flags)를 통일해서 이해하고 싶을 때

## 핵심 개념

### 범용 레지스터 이름 규칙
세 디버거 모두 레지스터 이름 자체는 인텔 공식 명칭(`RAX`/`EAX`/`AX`/`AL`, `RIP`/`EIP` 등)을 그대로 쓰지만 대소문자 관례가 다르다.
| 항목 | GDB | x64dbg | WinDbg |
|---|---|---|---|
| 표기 대소문자 | 소문자(`$rax`, `$rip`) | 대문자(`RAX`, `RIP`) | 소문자(`rax`, `rip`) |
| 참조 접두사 | `$` 필요(`$rax`) | 접두사 없음 | 접두사 없음, `@rax`(표현식 안에서) |
| 플래그 레지스터 이름 | `$eflags`(x86)/`$eflags`(x64에서도 관례상 eflags로 표시) | Flags 패널(EFLAGS 하위 비트를 개별 표시) | `efl` 레지스터 |

### 플래그 대조표(EFLAGS/RFLAGS 공통 비트)
| 의미 | 비트 이름 | GDB `info registers` 표시 | x64dbg Flags 패널 | WinDbg `r` 출력(세트/해제) |
|---|---|---|---|---|
| 캐리 | CF | `CF`(세트일 때만 표시) | `CF` 체크박스 | `cy` / `nc` |
| 패리티 | PF | `PF` | `PF` 체크박스 | `pe` / `po` |
| 보조 캐리 | AF | `AF` | `AF` 체크박스 | `ac` / `na` |
| 제로 | ZF | `ZF` | `ZF` 체크박스 | `zr` / `nz` |
| 사인 | SF | `SF` | `SF` 체크박스 | `ng` / `pl` |
| 트랩 | TF | `TF` | `TF` 체크박스 | (기본 `r` 출력에 보통 생략) |
| 인터럽트 허용 | IF | `IF` | `IF` 체크박스 | `ei` / `di` |
| 방향 | DF | `DF` | `DF` 체크박스 | `dn` / `up` |
| 오버플로우 | OF | `OF` | `OF` 체크박스 | `ov` / `nv` |

### GDB 표시 방식의 특징
GDB의 `info registers`는 `eflags`를 `0x246 [ PF ZF IF ]`처럼 **원시 16진수 값 + 현재 세트된 플래그 이름만 나열**하는 방식이다. 세트되지 않은 플래그는 아예 나타나지 않으므로, "CF가 없다 = CF가 0이다"로 해석해야 한다.

### x64dbg 표시 방식의 특징
x64dbg는 Registers 패널에 각 플래그를 별도의 행으로 나열하고 0/1 상태를 체크박스로 보여준다. 체크박스를 직접 더블클릭해서 값을 토글할 수도 있어, 조건 분기 결과를 즉석에서 실험해보고 싶을 때 편리하다.

### WinDbg 표시 방식의 특징
WinDbg의 `r` 명령은 `iopl=0 nv up ei pl zr na po nc`처럼, 플래그마다 "세트일 때 약어"와 "해제일 때 약어"가 서로 다른 한 쌍으로 정의되어 있다. 즉 GDB처럼 세트된 것만 골라 보여주는 게 아니라 **모든 플래그를 항상 어떤 상태로든 표시**하며, 어느 약어가 나왔는지로 세트/해제를 구분해야 한다. `iopl=N`은 플래그가 아니라 I/O 권한 레벨(0~3) 값이다.

## 화면/코드에서 보이는 징후
같은 디버깅 세션 스크린샷이나 라이트업이라도 도구가 다르면 플래그 부분의 문자열이 완전히 다르게 보인다. `ZF`라는 이름 자체가 아예 안 보이고 `zr`/`nz`만 보이면 WinDbg 출력이고, 체크박스 목록이면 x64dbg, 대괄호 안에 세트된 것만 나열되어 있으면 GDB다.

## 가장 먼저 할 것
지금 보고 있는 출력이 어느 디버거의 것인지부터 확인한 뒤, 위 대조표에서 같은 줄(같은 의미)을 찾아 비교한다. WinDbg 출력이라면 두 글자 약어 중 어느 쪽이 나왔는지부터 확인한다(예: `zr`이면 ZF=1, `nz`면 ZF=0).

## 단계별 절차

**1) 지금 보는 화면이 어느 도구인지 확인**
프롬프트 모양(`(gdb)`, x64dbg GUI 패널, `0:000>` 형태의 WinDbg 프롬프트)으로 구분한다.

**2) 확인하려는 플래그 하나를 정한다**
예: 방금 `cmp` 이후 분기 예측에 필요한 ZF, SF, OF.

**3) 대조표에서 같은 행을 찾는다**
예: ZF 행 → GDB `ZF`(세트 시 표시), x64dbg `ZF` 체크박스, WinDbg `zr`(세트)/`nz`(해제).

**4) 실제 값 읽기**
```gdb
(gdb) p/x $eflags
```
```text
x64dbg: Registers 패널의 ZF 체크박스 상태 확인
```
```text
WinDbg: r 명령 실행 후 출력 문자열에서 zr/nz 검색
```

**5) 조건부 분기(JE/JNE 등)와 연결해서 해석**
ZF=1(GDB `ZF` 표시, x64dbg 체크됨, WinDbg `zr`)이면 직전 `cmp`/`test`의 두 값이 같았다는 뜻이다.

## 명령어/단축키
```gdb
info registers eflags     # GDB: 플래그 레지스터 확인
p/x $eflags                # GDB: 16진수로 확인
```
```text
Registers 패널            # x64dbg: 플래그 체크박스 확인/토글
```
```text
r                          # WinDbg: 전체 레지스터+플래그 문자열 출력
r efl                      # WinDbg: eflags 값만 확인
```

## 출력 해석
- GDB: `eflags 0x246 [ PF ZF IF ]` → 0x246의 세트된 비트 중 이름이 붙은 것만 나열, 나머지(CF/AF/SF/TF/DF/OF)는 전부 0.
- x64dbg: 체크된 플래그 행 = 1, 체크 안 된 행 = 0.
- WinDbg: `nv up ei pl zr na po nc` → 순서대로 OF=0(`nv`), DF=0(`up`), IF=1(`ei`), SF=0(`pl`), ZF=1(`zr`), AF=0(`na`), PF=0(`po`), CF=0(`nc`).

## 흔한 실수
- WinDbg의 `pl`(Sign Flag 해제=Plus/양수)을 "PF(패리티)"와 혼동하는 것 — `pl`은 SF 관련 약어이고 패리티는 `pe`/`po`다.
- GDB 출력에서 특정 플래그 이름이 안 보이는 것을 "그 플래그가 없다/지원 안 한다"로 오해하는 것 — 단순히 값이 0이라 생략된 것뿐이다.
- x64dbg 체크박스를 실수로 더블클릭해 플래그 값을 바꿔버리고, 그 상태로 계속 실행해서 분기 결과가 의도와 다르게 나오는 것.
- 32비트 문서의 EFLAGS 설명과 64비트 RFLAGS를 완전히 동일하다고 가정하는 것 — 하위 32비트의 플래그 의미는 동일하지만 레지스터 이름과 폭이 다르다는 점은 구분해야 한다.

## 막혔을 때 다음 체크
- GDB에서 레지스터/플래그를 텍스트로 확인하는 기본 사용법이 궁금하면 → REV-0188 GDB info registers와 flags 확인.
- 세 디버거의 다른 명령들도 한 번에 대응해서 보고 싶다면 → REV-0813 디버거별 명령어 대응표(GDB vs x64dbg vs WinDbg).
- x64dbg 표현식에서 플래그/레지스터를 조건식에 쓰는 법이 궁금하면 → REV-0806 x64dbg 표현식(Expression) 문법 빠른 참조.

## 미니 예제
```text
상황: cmp eax, ebx 실행 직후 eax == ebx였다.

GDB      : info registers eflags → eflags 0x246 [ PF ZF IF ]  (ZF 표시됨 = 1)
x64dbg   : Registers 패널에서 ZF 체크박스가 체크된 상태
WinDbg   : r 실행 결과에 ...zr... 포함(nz가 아니라 zr)

세 출력 모두 "ZF=1, 즉 두 값이 같았다"는 동일한 사실을 다르게 표시하고 있을 뿐이다.
```

## 관련 글
- REV-0813 — 디버거별 명령어 대응표(GDB vs x64dbg vs WinDbg)
- REV-0188 — GDB info registers와 flags 확인
- REV-0806 — x64dbg 표현식(Expression) 문법 빠른 참조

## 출처/검증
- GDB `info registers`의 `eflags` 출력 형식(세트된 플래그 이름만 대괄호로 나열): GDB 공식 온라인 매뉴얼("Debugging with GDB") "Registers" 챕터 기준.
- x64dbg Registers 패널의 플래그 체크박스 표시/토글 방식: x64dbg 공식 문서 및 GUI 레퍼런스 기준.
- WinDbg `r` 명령의 플래그 세트/해제 약어 쌍(`ov`/`nv`, `dn`/`up`, `ei`/`di`, `ng`/`pl`, `zr`/`nz`, `ac`/`na`, `pe`/`po`, `cy`/`nc`)과 `iopl` 표시: Microsoft 공식 WinDbg 문서("r (Registers)") 기준 (2026-09-09 조사).
