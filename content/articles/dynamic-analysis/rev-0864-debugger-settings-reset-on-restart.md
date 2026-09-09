---
id: REV-0864
title: "디버거 재시작할 때마다 설정이 초기화될 때"
slug: "rev-0864-debugger-settings-reset-on-restart"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg]
keywords:
  - x64dbg database
  - .dd32 .dd64
  - x64dbg.ini
  - gdbinit
  - save breakpoints
  - 설정 초기화
symptom_keywords:
  - 브레이크포인트가 다 사라짐
  - 재실행하면 설정이 리셋됨
  - 주석 라벨이 다 없어짐
  - gdb 다시 켜면 브레이크포인트 없어짐
aliases:
  - x64dbg 설정 안 저장됨
  - 디버거 브레이크포인트 매번 다시걸어야함
  - dd32 dd64 파일
  - gdbinit 설정법
source_ids: ["SRC-X64DBG-DOCS", "SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
x64dbg는 브레이크포인트·주석·라벨 같은 분석 정보를 대상 파일 옆(또는 지정된 데이터베이스 폴더)에 `.dd32`/`.dd64` 데이터베이스 파일로 저장하고, GDB는 기본적으로 세션이 끝나면 브레이크포인트를 기억하지 않으므로, 이 저장 위치에 쓰기 권한이 없거나 저장/자동 로드 설정을 켜두지 않으면 재시작할 때마다 모든 설정이 사라진 것처럼 보인다.

## 언제 검색해야 하나
- x64dbg로 어제 열심히 걸어둔 브레이크포인트, 주석, 라벨이 오늘 다시 열었더니 전부 사라져 있을 때
- GDB를 껐다 켤 때마다 매번 같은 `break` 명령들을 손으로 다시 입력해야 해서 번거로울 때
- USB/외장 SSD나 읽기 전용 폴더에서 x64dbg를 실행했더니 설정이 계속 초기화될 때
- 같은 실행 파일인데 폴더 경로를 옮겼더니 이전 분석 정보가 안 불러와질 때

## 핵심 개념

### x64dbg의 데이터베이스 파일(.dd32/.dd64)
x64dbg는 대상 실행 파일을 닫거나 디버깅을 종료할 때, 그 파일에 대한 브레이크포인트/주석/라벨/북마크 등 분석 정보를 JSON 형식의 데이터베이스 파일로 저장한다. 기본 설정에서는 이 파일이 대상 실행 파일과 같은 폴더에 `<파일명>.dd32`(32비트) 또는 `<파일명>.dd64`(64비트) 이름으로 생성된다(설정에서 별도의 중앙 데이터베이스 디렉터리를 쓰도록 바꿀 수도 있다). 다음에 그 파일을 다시 열면 x64dbg가 이 데이터베이스를 자동으로 불러와 이전 분석 상태를 복원한다.

### 저장이 안 되는 흔한 이유
- **쓰기 권한 부족**: `Program Files` 하위처럼 관리자 권한이 필요한 폴더, 또는 읽기 전용으로 마운트된 외장 드라이브/네트워크 공유에 대상 파일이 있으면 `.dd32/.dd64` 파일 자체를 생성하지 못해 매번 초기화된 것처럼 보인다.
- **경로가 매번 달라짐**: 대상 파일을 압축 해제할 때마다 임시 폴더 경로가 바뀌거나, 다른 위치로 복사해서 열면 데이터베이스 파일과 대상 파일의 경로 매칭이 깨져 이전 정보를 못 찾는다.
- **"Save database on close" 설정이 꺼져 있음**: 환경설정에서 종료 시 자동 저장 옵션이 비활성화되어 있으면 수동으로 저장하지 않는 한 다음 실행 때 아무 것도 남아있지 않다.
- **x64dbg.ini 자체가 저장 안 됨**: 브레이크포인트가 아닌 전역 UI 설정(테마, 단축키, 창 배치 등)은 x64dbg 실행 파일이 있는 폴더의 `x64dbg.ini`에 저장되는데, 이 폴더가 쓰기 금지되어 있으면 전역 설정도 매번 초기화된다.

### GDB는 원래 세션 간 상태를 자동 저장하지 않는다
GDB는 원칙적으로 매 실행이 독립적인 세션이며, 브레이크포인트 목록은 메모리에만 있다가 GDB 프로세스가 끝나면 사라진다. 이것은 "설정이 초기화되는 버그"가 아니라 정상 동작이며, 영속적으로 쓰고 싶다면 다음 두 방법을 조합해야 한다.
1. `save breakpoints <파일>` 명령으로 현재 브레이크포인트 목록을 텍스트 파일로 저장해두고, 다음 세션에서 `source <파일>`로 다시 불러온다.
2. 자주 쓰는 설정(`set` 명령들, 자주 쓰는 `break`/`define` 매크로 등)은 홈 디렉터리의 `~/.gdbinit` 파일에 적어두면 GDB가 시작할 때마다 자동으로 실행된다.

## 화면/코드에서 보이는 징후
- x64dbg에서 대상 파일이 있는 폴더를 봐도 `.dd32`/`.dd64` 파일이 아예 생성되어 있지 않다.
- x64dbg 로그 창에 데이터베이스 저장/로드 관련 오류나 경고가 뜬 적이 있다(잘 안 보일 수 있으므로 폴더에 파일이 생겼는지 직접 확인하는 게 더 확실하다).
- GDB를 새로 열 때마다 `info breakpoints`가 `No breakpoints or watchpoints.`로 나온다.

## 가장 먼저 할 것
1. x64dbg라면 대상 파일이 있는 폴더에 실제로 `.dd32`/`.dd64` 파일이 생성되는지 확인한다.
2. 생성되지 않는다면 그 폴더에 대한 쓰기 권한부터 의심한다(관리자 권한 실행, 읽기 전용 속성, 네트워크/외장 드라이브 권한).
3. GDB라면애초에 "세션 간 자동 저장"이 기본 동작이 아니라는 것을 이해하고, `save breakpoints`/`~/.gdbinit`를 직접 활용한다.

## 단계별 절차

**x64dbg**
1. `Options` → `Preferences`에서 데이터베이스 저장 관련 옵션("Save database on close" 등)이 켜져 있는지 확인한다.
2. 대상 파일이 쓰기 가능한 폴더(예: 사용자 문서 폴더, 바탕화면 등)에 있는지 확인하고, 필요하면 그런 폴더로 복사해서 다시 연다.
3. 관리자 권한으로 x64dbg를 실행해서 문제가 해결되는지 시험해본다(단, 이 경우는 근본적으로 파일 위치를 옮기는 것이 더 안전하다).
4. 수동으로 저장하고 싶다면 `File` → `Save database`(또는 유사 메뉴)를 사용한다.

**GDB / Pwndbg**
1. 원하는 브레이크포인트를 다 걸어둔 상태에서 목록을 파일로 저장한다.
   ```
   save breakpoints my_breakpoints.txt
   ```
2. 다음 세션에서 이 파일을 불러온다.
   ```
   source my_breakpoints.txt
   ```
3. 매번 반복하기 귀찮은 공통 설정은 `~/.gdbinit`에 적어둔다.
   ```
   # ~/.gdbinit 예시
   set pagination off
   set disassembly-flavor intel
   source my_breakpoints.txt
   ```

## 명령어/단축키
- x64dbg: `Options` → `Preferences`(데이터베이스 저장 옵션), `File` → `Save database`(수동 저장)
- GDB/Pwndbg: `save breakpoints <파일>`, `source <파일>`, `~/.gdbinit`(자동 실행 스크립트)

## 출력 해석
- x64dbg 대상 폴더에 `target.dd64` 같은 파일이 생겼다면 저장은 정상적으로 되고 있는 것이다 — 이후에도 초기화된다면 "로드"가 실패하는 다른 문제(경로 불일치 등)를 의심해야 한다.
- GDB `source my_breakpoints.txt` 실행 후 `Breakpoint 1 at 0x401234` 같은 메시지가 여러 줄 뜨면 정상적으로 이전 브레이크포인트들이 복원된 것이다.

## 흔한 실수
- 대상 실행 파일을 매번 다른 임시 폴더(압축 해제 폴더 등)에서 열어서, x64dbg 입장에서는 "새로운 파일"로 인식돼 데이터베이스가 매칭되지 않는 것 — 항상 같은 고정 경로에서 작업하는 습관이 필요하다.
- GDB가 세션 간 설정을 자동으로 기억해줄 것이라고 기대하는 것 — 반드시 `.gdbinit`이나 `save breakpoints`를 직접 활용해야 한다.
- 관리자 권한 폴더에 있는 파일을 일반 권한으로 열어 데이터베이스 저장이 조용히 실패하는데 알아채지 못하는 것.

## 막혔을 때 다음 체크
- x64dbg 데이터베이스 파일은 생기는데도 다음에 안 불러와진다면 → 파일 경로(대소문자, 드라이브 문자)가 완전히 똑같은지 확인한다.
- GDB 스크립팅으로 더 정교하게 자동화하고 싶다면 → REV-0656(GDB Python 스크립팅 기초)을 참고한다.
- Pwndbg 자체 설정(테마, alias 등)이 초기화된다면 → Pwndbg도 결국 GDB의 `.gdbinit` 로딩 방식 위에서 동작하므로 같은 원리로 접근한다(REV-0192 참고).

## 미니 예제
```
(gdb) break main
(gdb) break check_password
(gdb) save breakpoints my_bp.txt
(gdb) quit
```
다음 실행:
```
$ gdb ./target
(gdb) source my_bp.txt
Breakpoint 1 at 0x401156: file main.c, line 10.
Breakpoint 2 at 0x4011a2: file main.c, line 25.
```
이렇게 하면 GDB를 새로 켤 때마다 브레이크포인트를 손으로 다시 입력할 필요가 없다.

## 관련 글
- REV-0192 — Pwndbg 설치와 실행
- REV-0656 — GDB Python 스크립팅 기초(gdb.Breakpoint 등)
- REV-0178 — x64dbg Breakpoint 설정과 삭제

## 출처/검증
- x64dbg 데이터베이스 파일(`.dd32`/`.dd64`)과 저장/로드 동작: x64dbg 공식 문서(Introduction, Database) 기준.
- GDB `save breakpoints`, `source`, `.gdbinit` 자동 실행 동작: GNU GDB 공식 매뉴얼 "Command Files" 및 "Breakpoints" 챕터 기준.
- 2026-09-09 검증.
