---
id: REV-0807
title: "GDB 표현식/포맷 지정자(x/nfu) 빠른 참조"
slug: "rev-0807-gdb-expression-format-specifier-quickref"
category: "dynamic-analysis"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb x command", "x/nfu", "gdb format letter", "gdb print format", "gdb examine memory format", "gdb x/4xw"]
aliases: ["gdb x 명령 포맷", "gdb 메모리 출력 형식", "gdb print /x", "gdb 포맷 지정자표"]
symptom_keywords: ["gdb x 명령 문법이 헷갈림", "gdb에서 4바이트씩 몇 개를 볼지 모름", "gdb print 출력 형식을 바꾸고 싶음", "gdb x/i가 뭔지 모름", "gdb 문자열로 메모리 보고싶음"]
source_ids: ["SRC-GDB-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
GDB의 `x/NFU ADDR` 명령은 "몇 개(N)를, 어떤 형식(F)으로, 얼마 크기의 단위(U)로 보여줄지"를 한 번에 지정하는 문법이고, `print`(`p`) 명령도 `/F`를 붙이면 같은 형식 문자를 그대로 재사용할 수 있다.

## 언제 검색해야 하나
- `x/4xw $rsp` 같은 명령에서 `4`, `x`, `w`가 각각 무슨 뜻인지 헷갈릴 때
- 메모리를 문자열로, 명령어로, 부호 있는 10진수로 각각 다르게 보고 싶을 때
- `print`로 본 값을 16진수/2진수/문자로 바꿔서 다시 보고 싶을 때
- 이전에 쓴 `x` 명령의 크기/형식이 계속 이어져서 다음 명령 결과가 이상하게 나올 때

## 핵심 개념

### 기본 형식: `x/NFU ADDR`
```gdb
x/4xw $rsp
```
이 명령은 `$rsp`부터 시작해서 **N=4개**의 항목을, **F=x(16진수)** 형식으로, **U=w(word=4바이트)** 단위로 보여준다. N, F, U는 각각 생략 가능하며, 생략하면 마지막으로 썼던 값이 그대로 재사용된다.

### N — 개수
표시할 항목의 개수. 생략하면 1.

### F — 출력 형식(format letter)
| 문자 | 의미 |
|---|---|
| `x` | 16진수 |
| `d` | 부호 있는(signed) 10진수 |
| `u` | 부호 없는(unsigned) 10진수 |
| `o` | 8진수 |
| `t` | 2진수(binary) |
| `a` | 주소 형식(가능하면 가장 가까운 심볼+오프셋도 함께 표시) |
| `c` | 문자(char)로 해석 |
| `f` | 부동소수점 |
| `s` | 널 종료 문자열로 해석 |
| `i` | 어셈블리 명령어로 디스어셈블 |
| `z` | 앞에 0을 채운 고정폭 16진수 |

### U — 단위 크기(unit letter)
| 문자 | 크기 |
|---|---|
| `b` | byte, 1바이트 |
| `h` | halfword, 2바이트 |
| `w` | word, 4바이트 |
| `g` | giant word, 8바이트 |

`s`(문자열)와 `i`(명령어) 형식은 단위 개념이 의미가 없어서 U를 무시하고 각 항목의 실제 길이만큼 알아서 진행한다.

### 값이 유지되는 규칙
`x` 명령을 한 번 쓰고 나면, 다음에 `x` 또는 `x ADDR`처럼 N/F/U를 생략하고 다시 쓰면 **직전에 썼던 F와 U가 그대로 유지**된다. 주소는 매번 마지막으로 출력한 위치 다음으로 자동 이동한다. 그래서 `x/8i $pc` 한 번 친 뒤 그냥 `x`만 계속 치면 이어지는 명령어를 계속 볼 수 있다.

### `print`(`p`)와 형식 문자 공유
```gdb
p/x $rax
p/t $eflags
p/c my_char_var
```
`print`도 `/F` 뒤에 위의 형식 문자를 그대로 쓸 수 있다. 다만 `print`는 "몇 개(N)"나 "단위(U)" 개념이 없고, 지정한 표현식 하나의 값을 그 형식으로만 바꿔서 보여준다.

## 화면/코드에서 보이는 징후
GDB 세션 프롬프트(`(gdb)`)에서 직접 입력하는 명령이며, 화면 출력 자체가 "주소: 값 값 값 값" 형태로 여러 줄에 걸쳐 나타난다.

## 가장 먼저 할 것
지금 보고 싶은 게 "숫자로서의 값"인지 "명령어"인지 "문자열"인지부터 정한다. 숫자면 `x`/`d`/`u`, 명령어면 `i`, 문자열이면 `s`를 F 자리에 넣고 시작한다.

## 단계별 절차

**1) 스택을 16진수로 8개(4바이트 단위) 보기**
```gdb
x/8xw $rsp
```

**2) 현재 rip 주변 명령어 10개 디스어셈블**
```gdb
x/10i $pc
```

**3) 버퍼를 문자열로 보기**
```gdb
x/s buf
```

**4) 8바이트 단위로 포인터 체인처럼 훑기**
```gdb
x/4xg $rsp
```

**5) 레지스터 값을 2진수로 즉시 확인**
```gdb
p/t $eflags
```

**6) 직전 형식 유지한 채 이어서 보기**
```gdb
x/8i $pc
x
x
```
매번 그 다음 8개(또는 직전 개수)만큼 이어서 보여준다.

## 명령어/단축키
```gdb
x/NFU ADDR
x/4xw ADDR    # 4개, 16진수, 4바이트 단위
x/10i $pc     # 10개 명령어 디스어셈블
x/s ADDR      # 널 종료 문자열
x/g ADDR      # 8바이트 1개(형식은 직전 유지)
p/F EXPR      # print에 형식만 적용
```

## 출력 해석
```
0x7fffffffe4a0: 0x00000001      0x00000000      0x7fffffffe560  0x00000000
```
맨 앞은 시작 주소, 그 뒤로 지정한 개수만큼 지정한 형식/단위로 값이 나열된다. `x/10i $pc` 형식이면 각 줄이 `주소 <심볼+오프셋>: 니모닉  오퍼랜드` 형태로 나오고, 현재 실행할 명령어 줄 앞에는 `=>` 표시가 붙는다.

## 흔한 실수
- N/F/U 순서를 헷갈려서 `x/wx4`처럼 잘못 쓰는 것 — 항상 `x/개수형식단위` 순서다(`x/4xw`).
- 직전 `x` 명령의 형식이 유지된다는 걸 모르고, 방금 `s`(문자열)로 봤다가 다음에 숫자를 기대하고 그냥 `x ADDR`만 쳐서 계속 문자열로 나오는 것.
- `w`(word=4바이트)를 32비트 시대의 감각으로 "레지스터 크기"라고 착각하는 것 — x64에서 레지스터 전체를 보려면 `g`(8바이트)를 써야 한다.
- `i` 형식에 단위(U)를 같이 쓰려다 무시된다는 걸 모르고 헷갈리는 것 — 명령어 형식은 단위 대신 실제 인코딩 길이를 따른다.

## 막혔을 때 다음 체크
- `x` 명령 자체의 기본 사용법과 실습 흐름이 궁금하면 → REV-0189 GDB x 명령으로 메모리 보기.
- 이 형식 문자를 조건부 브레이크포인트나 dprintf와 함께 쓰고 싶다면 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak).
- Pwndbg의 `telescope`/`hexdump`처럼 더 읽기 좋은 대안이 궁금하면 → REV-0193 Pwndbg context telescope vmmap.

## 미니 예제
```gdb
(gdb) x/4xg $rsp
0x7fffffffe4a0: 0x0000000000000001      0x00007ffff7dc0000
0x7fffffffe4b0: 0x0000555555555169      0x0000000000000000
(gdb) x/6i $pc
=> 0x555555555169 <check_password+16>: cmp    eax,0x1
   0x55555555516c <check_password+19>: je     0x555555555180 <check_password+39>
   0x55555555516e <check_password+21>: mov    edi,0x0
   ...
```
같은 `$rsp` 주변을 8바이트(`g`) 단위로 두 개씩 4번, 그 다음 `$pc` 주변을 명령어(`i`) 6개로 이어서 확인한 예시다.

## 관련 글
- REV-0189 — GDB x 명령으로 메모리 보기
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)
- REV-0193 — Pwndbg context telescope vmmap
- REV-0806 — x64dbg 표현식(Expression) 문법 빠른 참조

## 출처/검증
- `x/NFU` 문법, 형식 문자(`x d u o t a c f s i z`)와 단위 문자(`b h w g`) 목록, 형식/단위가 다음 명령에 유지되는 동작: GDB 공식 온라인 매뉴얼("Debugging with GDB") "Examining Memory" 챕터 기준.
- `print/F` 형식 지정자 공유: 같은 매뉴얼 "Output Formats" 섹션 기준 (2026-09-09 검증).
