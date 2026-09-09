---
id: REV-0307
title: "Ghidra와 GDB를 같이 쓰는 워크플로"
slug: "rev-0307-ghidra-gdb-combined-workflow"
category: "triage"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [Ghidra, GDB, Pwndbg]
keywords: [Ghidra GDB 연동, Ghidra 디버거 연결, GDB로 Ghidra 검증, Linux 리버싱 워크플로, Ghidra Debugger 모듈]
aliases: ["Ghidra GDB 같이 쓰기", "Ghidra로 분석 GDB로 확인", "Ghidra Debugger 연동", "리눅스 정적동적 워크플로"]
symptom_keywords: ["Ghidra 디컴파일 결과를 실제로 확인하고 싶음", "Ghidra 주소랑 GDB 주소가 다름", "Ghidra의 Debugger 기능 사용법을 모름", "GDB로 함수 위치를 못 찾겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Linux ELF 문제는 **Ghidra로 함수 구조와 디컴파일 의사코드를 확보한 뒤, GDB(+Pwndbg)로 그 의사코드가 실제 실행 중에 맞는지 레지스터/메모리 값으로 검증**하는 흐름이 기본이며, 두 도구를 오갈 때는 PIE 오프셋 계산과 심볼 이름 동기화가 핵심이다.

## 언제 검색해야 하나
- Ghidra에서 디컴파일한 C 유사 코드를 실제 실행 결과와 대조해서 맞는지 확인해야 할 때
- PIE(Position Independent Executable)라서 Ghidra의 주소와 GDB에서 보이는 실제 주소가 다를 때
- Ghidra 내장 Debugger 모듈과 별도 터미널 GDB 중 무엇을 쓸지, 어떻게 연동할지 모를 때

## 핵심 개념
Ghidra는 정적 디컴파일에 강하고(무료로 C 유사 의사코드 생성), GDB는 실제 프로세스를 제어하며 값 확인에 강하다. 이 조합의 핵심 이슈는 두 가지다.

1. **PIE 오프셋 문제**: 최신 리눅스 배포판의 ELF는 대부분 PIE로 빌드되어(`readelf -h`의 `Type: DYN`), 매 실행마다 로드 베이스 주소가 바뀐다(ASLR). Ghidra는 파일 기준 주소(보통 `0x00100000`대)를 보여주지만, 실제 실행 중인 프로세스는 그 주소에 임의의 베이스가 더해진 곳에 있다.
2. **심볼 이름 동기화**: Ghidra에서 함수를 리네임(`L` 단축키)해도 GDB는 그 이름을 자동으로 모른다. strip된 바이너리라면 GDB는 애초에 `FUN_00101234` 같은 이름조차 모르고 순수 주소로만 보여준다.

이 문제를 푸는 표준 방법은 GDB에서 프로세스의 실제 메모리 매핑을 확인해 베이스 주소를 얻고, 거기에 Ghidra의 파일 주소(가상 주소, PIE는 보통 링크 베이스가 `0x100000`)를 더해 실제 위치를 계산하는 것이다. Pwndbg를 쓰면 `vmmap` 명령으로 이 매핑을 한눈에 볼 수 있어 훨씬 편하다.

또한 Ghidra 9.2+ 버전은 내장 **Debugger** 모듈을 제공해서, GDB를 백엔드로 붙여 Ghidra 안에서 직접 브레이크포인트를 걸고 실행 상태를 볼 수도 있다. 별도 터미널 GDB와 Ghidra Debugger 둘 다 같은 GDB 엔진을 쓰므로 선택은 취향 문제지만, 이 문서는 더 널리 쓰이고 스크립팅이 쉬운 "별도 터미널 GDB" 방식을 기준으로 설명한다.

## 화면/코드에서 보이는 징후
- Ghidra 디컴파일에서 함수 시작 주소가 `0x00101a1d`인데, GDB `info proc mappings` 결과의 실행 파일 베이스가 `0x00555555554000`처럼 완전히 다른 자릿수로 보인다.
- `break *0x00101a1d`를 GDB에서 입력했는데 브레이크포인트가 걸리지 않거나 프로그램 시작 전에는 "No symbol table" 경고가 뜬다.
- Ghidra에서 붙인 함수 이름(`check_flag`)이 GDB `disassemble` 결과에는 안 보이고 주소만 나온다.

## 가장 먼저 할 것
`readelf -h ./chall | grep Type`으로 PIE(`DYN`) 여부를 확인한다. PIE라면 이후 모든 주소 계산에 베이스 주소 보정이 필요하다는 것을 전제로 시작한다.

## 단계별 절차

**1) Ghidra에서 정적 분석 및 함수 주소 확보**
Ghidra의 Symbol Tree 또는 Function Manager에서 관심 함수(예: `check_flag`)를 찾고, 그 함수의 시작 주소(Ghidra 기준 가상 주소, 예: `0x00101a1d`)를 기록한다. Decompile 창(자동으로 우측에 표시)에서 의사코드를 읽고 가설을 세운다.

**2) GDB로 실행 후 베이스 주소 확인**
```bash
gdb ./chall
(gdb) break main
(gdb) run
(gdb) info proc mappings
```
`info proc mappings` 결과에서 `chall`(실행 파일 자신) 라인의 시작 주소가 실제 로드 베이스다. Pwndbg를 쓴다면 `vmmap` 명령이 더 보기 좋게 같은 정보를 보여준다.

**3) 실제 브레이크포인트 주소 계산**
```
실제 주소 = 로드 베이스 + (Ghidra 주소 - Ghidra의 링크 베이스)
```
대부분의 PIE 바이너리에서 Ghidra 링크 베이스는 `0x00100000`이므로, 실질적으로는 "Ghidra 주소의 하위 오프셋 부분"을 로드 베이스에 더하면 된다. GDB/Pwndbg는 이를 더 쉽게 하는 방법을 제공한다.

**4) PIE 대응 브레이크포인트 설정(더 쉬운 방법)**
바이너리가 strip되지 않았다면 GDB에서 이름으로 바로 브레이크포인트를 걸 수 있다.
```bash
(gdb) break check_flag
(gdb) run
```
strip되어 이름이 없다면 Pwndbg의 심볼 없는 주소 지정 방식을 쓴다.
```bash
(gdb) break *0x555555554000+0x1a1d
```
`0x555555554000`은 2단계에서 확인한 실제 로드 베이스, `0x1a1d`는 Ghidra 주소(`0x00101a1d`)의 하위 오프셋(링크 베이스 `0x100000`을 뺀 값)이다.

**5) 실행 및 값 확인**
```bash
(gdb) continue
(gdb) info registers
(gdb) x/8xb $rsi
```
브레이크포인트에 멈추면 레지스터와 메모리 값을 확인해 Ghidra에서 세운 가설(예: "이 인자가 사용자 입력 포인터")이 맞는지 검증한다.

**6) 값 확인 후 Ghidra로 복귀해 주석/이름 기록**
GDB에서 확인한 실제 값을 Ghidra 디컴파일 창에 주석(`;` 단축키)으로 남기고, 확인된 변수는 리네임(Ghidra에서 변수 우클릭 → Rename Variable, 단축키 없으면 컨텍스트 메뉴 사용)한다.

## 명령어/단축키
```bash
readelf -h ./chall | grep Type
gdb ./chall
(gdb) break main
(gdb) run
(gdb) info proc mappings     # 또는 pwndbg의 vmmap
(gdb) break check_flag       # strip 안 된 경우
(gdb) break *<실제주소>       # strip된 경우
(gdb) continue
(gdb) info registers
(gdb) x/8xb $rsi
(gdb) x/s $rdi
```
Ghidra: Symbol Tree에서 함수 더블클릭, `L`(리네임), `;`(주석), Decompile 창 자동 갱신.

## 출력 해석
- `info proc mappings`(또는 `vmmap`)의 첫 실행 파일 매핑 라인이 실제 로드 베이스다. 이 값이 실행할 때마다 바뀌면 ASLR이 켜져 있다는 뜻이며, 매번 새로 확인해야 한다(`disable-randomization` 설정으로 고정할 수도 있다).
- `x/8xb $rsi` 결과가 Ghidra에서 예상한 문자열/배열 값과 일치하면 그 지점의 함수 인자 해석이 맞다는 뜻이다.
- GDB에서 함수 이름으로 브레이크포인트가 걸리면(`Breakpoint 1 at 0x...`) 그 이름이 심볼 테이블에 남아있다는 뜻이므로, strip되지 않은 바이너리임이 재확인된다.

## 흔한 실수
- PIE인 것을 모르고 Ghidra 주소를 GDB에 그대로 `break *0x00101a1d`로 입력해서 브레이크포인트가 전혀 다른 곳(또는 매핑되지 않은 주소라 실패)에 걸리는 것.
- 매 실행마다 로드 베이스가 바뀌는데 이전 실행에서 계산한 베이스 주소를 재사용하는 것.
- Ghidra에서 변수/함수 이름을 바꿔놓고 GDB 세션에는 반영되지 않는다는 걸 잊고 GDB에서 그 이름으로 브레이크포인트를 걸려다 실패하는 것(디버그 정보가 없는 한 GDB는 Ghidra의 리네임을 모른다).
- `info registers`만 보고 메모리 내용(`x` 명령)은 확인하지 않아, 포인터가 가리키는 실제 데이터를 놓치는 것.

## 막혔을 때 다음 체크
- PIE 오프셋 계산 자체가 헷갈린다 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak), REV-0643 Pwndbg 명령어 심화 치트시트(heap/got/plt)에서 주소 관련 명령 재확인
- 아예 정적/동적 어느 단계로 넘어갈지부터 헷갈린다 → REV-0309 정적분석과 동적분석을 오가는 타이밍 판단법
- Windows PE 문제라 이 워크플로가 안 맞는다 → REV-0306 IDA로 정적분석 후 x64dbg로 검증하는 워크플로

## 미니 예제
`chall`(PIE, not stripped)의 `check_flag` 함수를 검증한다.

1. Ghidra에서 `check_flag` 디컴파일 → `if (input[i] ^ key[i] != target[i]) return 0;` 형태의 XOR 비교 루프 확인. 함수 시작 주소 `0x00101a1d` 기록.
2. `gdb ./chall` → `break check_flag`(strip 안 됐으므로 이름으로 바로 가능) → `run`.
3. 브레이크에 멈춤 → `info registers`로 인자 레지스터(`rdi`) 확인 → `x/s $rdi`로 실제 입력 문자열 확인.
4. `key`, `target` 배열 주소를 Ghidra에서 확인한 뒤 GDB `x/8xb <주소>`로 실제 값 덤프 → Ghidra가 보여준 초기값과 일치함을 확인.
5. 검증 완료 → Ghidra로 돌아가 `key`, `target` 배열에 주석으로 실제 16진수 값을 남기고, 이제 solve.py 작성 단계로 이동.

## 관련 글
- REV-0309 — 정적분석과 동적분석을 오가는 타이밍 판단법
- REV-0306 — IDA로 정적분석 후 x64dbg로 검증하는 워크플로
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)
- REV-0643 — Pwndbg 명령어 심화 치트시트(heap/got/plt)

## 출처/검증
- GDB `info proc mappings`, `break`, `x` 명령어: GNU GDB 공식 문서(sourceware.org/gdb) 기준.
- Pwndbg `vmmap` 명령: Pwndbg 공식 GitHub 문서 기준.
- Ghidra Symbol Tree/Decompile/리네임/주석 기능: Ghidra 공식 문서(Ghidra Help) 기준.
- PIE/ASLR과 실제 로드 베이스 관계: System V ABI 및 Linux 커널 ASLR 문서 기준 (2026-09-09 검증).
