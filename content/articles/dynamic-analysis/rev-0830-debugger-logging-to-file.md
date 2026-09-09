---
id: REV-0830
title: "디버거 로그를 파일로 남겨서 나중에 분석하는 법"
slug: "rev-0830-debugger-logging-to-file"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB]
keywords: ["GDB set logging", "x64dbg 로그 저장", "디버거 세션 기록", "로그 파일 분석", "실행 기록 export", "브레이크포인트 로그 저장"]
aliases: ["디버거 로그 export", "GDB 로그 파일로 남기기", "x64dbg 로그창 저장", "실행 흔적 파일로 저장"]
symptom_keywords: ["디버거 창을 닫으면 로그가 다 사라짐", "긴 실행 기록을 나중에 다시 보고 싶음", "여러 번 실행한 결과를 비교하고 싶은데 화면 스크롤로는 안 됨", "로그를 텍스트 파일로 뽑아서 grep하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
GDB의 `set logging file`/`set logging enabled on`과 x64dbg Log 탭의 "Log to file"(또는 로그 내용 우클릭 저장) 기능을 쓰면, REV-0828 방식으로 걸어둔 로그 브레이크포인트나 실행 중 확인한 값들을 화면이 아니라 텍스트 파일로 영구히 남겨 나중에 `grep`/`diff`/스프레드시트로 분석할 수 있다.

## 언제 검색해야 하나
- REV-0828처럼 로그 브레이크포인트로 수백~수천 줄의 입출력 기록을 쌓았는데, 디버거 창의 스크롤만으로는 패턴을 찾기 어려울 때
- 같은 프로그램을 여러 번 실행한 결과(예: 서로 다른 입력에 대한 실행 로그)를 나중에 `diff`로 비교하고 싶을 때
- 디버거를 종료하거나 컴퓨터를 재시작해도 지금까지의 실행 기록을 남겨두고 싶을 때
- 팀원이나 미래의 나에게 "이 지점까지 실행했을 때 이런 값들이 나왔다"는 근거를 파일로 공유하고 싶을 때

## 핵심 개념

### GDB — 세션 전체를 파일로 미러링
GDB의 `set logging` 계열 명령은 GDB 콘솔에 출력되는 모든 내용(명령 입력 및 결과, `dprintf` 출력 포함)을 지정한 파일에 동시에 기록한다.

- `set logging file gdb_trace.log`: 로그를 저장할 파일 이름 지정(기본값은 `gdb.txt`)
- `set logging enabled on`: 로깅 시작(과거 GDB 버전에서는 `set logging on`)
- `set logging enabled off`: 로깅 중지
- `set logging overwrite on`: 매번 새로 실행할 때 기존 파일을 덮어쓸지, 이어서 추가할지 결정(`off`가 기본값으로 이어쓰기)
- `set logging redirect on`: 화면에는 출력하지 않고 파일에만 기록(대량의 `dprintf` 로그를 화면 없이 파일로만 뽑을 때 유용)

### x64dbg — Log 탭 전용 저장
x64dbg는 GDB처럼 전체 세션을 자동으로 파일 미러링하는 명령형 옵션은 기본 제공하지 않지만, Log 탭에 쌓인 내용을 다음 방법으로 파일로 옮길 수 있다.

- Log 탭 내용을 전체 선택 후 우클릭 → **Copy**로 복사해 텍스트 파일에 붙여넣기
- 일부 x64dbg 빌드/플러그인은 Log 탭 우클릭 메뉴에 "Save log to file" 옵션을 제공(빌드에 따라 다름)
- 스크립트 탭(REV-0814, 예정)에서 `log` 계열 스크립트 명령으로 로그를 직접 파일에 쓰도록 자동화하는 것도 가능

### 로그 파일을 나중에 활용하는 법
텍스트 파일로 남긴 로그는 일반적인 커맨드라인 도구로 바로 분석할 수 있다는 것이 핵심 이점이다.

- `grep "ret=1" gdb_trace.log`로 성공했던 케이스만 필터링
- 두 번의 실행 로그를 `diff run1.log run2.log`로 비교해 입력 차이에 따른 결과 차이를 한눈에 확인
- 엑셀/스프레드시트로 옮겨 정렬·필터링(입력값, 반환값 두 컬럼으로 정리해두면 특히 유용)

## 화면/코드에서 보이는 징후
- 디버거 Log/콘솔 창에 스크롤이 너무 길어져서 처음 부분을 다시 찾기 어려움
- 여러 번 재실행하면서 이전 실행 결과와 지금 결과를 비교하고 싶은데 화면에는 최신 실행 내용만 남아있음
- REV-0828의 로그 브레이크포인트를 오랜 시간 돌려서 로그가 수만 줄에 달해, 눈으로 훑는 것 자체가 비현실적임

## 가장 먼저 할 것
로그를 남기기로 정하기 전에, 무엇을 몇 개의 컬럼으로 남길지(예: "입력값, 반환값" 두 개, 또는 "함수 진입 인자, 반환값, 소요 사이클" 세 개) 미리 포맷을 정해두면 나중에 `grep`/`diff`/스프레드시트로 다루기 훨씬 쉽다. GDB는 세션을 시작하기 전에 `set logging` 설정부터 해두고, x64dbg는 로그 브레이크포인트의 Log text 표현식을 파일로 옮겨 적기 편한 고정 포맷(예: `IN=%s OUT=%d`)으로 미리 정리한다.

## 단계별 절차
### GDB
1. `set logging file trace_run1.log`로 파일 이름 지정
2. `set logging overwrite off`로 이어쓰기 설정(원하면 `on`으로 매번 새로 시작)
3. `set logging enabled on`으로 기록 시작
4. `dprintf` 등으로 원하는 값을 계속 출력시키며 프로그램 실행
5. 실행이 끝나면 `set logging enabled off`
6. 셸에서 `grep`, `diff`, `awk` 등으로 `trace_run1.log` 분석

### x64dbg
1. 로그 브레이크포인트(REV-0828)의 Log text 표현식을 고정 포맷으로 정리
2. 실행을 끝까지 진행해 Log 탭에 기록 누적
3. Log 탭 내용 전체 선택 → 우클릭 → Copy(또는 지원 빌드의 Save log to file)
4. 텍스트 에디터에 붙여넣어 `.log`/`.txt` 파일로 저장
5. 다른 입력으로 재실행할 때는 파일명을 다르게(`run1.txt`, `run2.txt`) 저장해 비교 가능하게 유지

## 명령어/단축키
GDB(Linux):
```
set logging file trace_run1.log
set logging overwrite off
set logging redirect off
set logging enabled on
...
set logging enabled off
```
셸(Linux):
```bash
grep "ret=1" trace_run1.log
diff trace_run1.log trace_run2.log
```
x64dbg(Windows):
```
Log 탭 전체 선택 → 우클릭 → Copy
(붙여넣을 메모장/에디터에서 .txt로 저장)
```

## 출력 해석
- GDB 로그 파일을 열어보면 콘솔에서 봤던 것과 동일한 텍스트가 그대로 들어있다. `set logging redirect on`을 켰다면 콘솔에는 아무것도 안 보이고 파일에만 쌓이므로, 처음 사용할 때는 `redirect off` 상태로 화면과 파일 양쪽에 다 나오는지 먼저 확인하는 것이 안전하다.
- `diff run1.log run2.log` 결과에서 `<`로 시작하는 줄은 run1에만 있는 내용, `>`로 시작하는 줄은 run2에만 있는 내용이다. 두 실행의 차이가 예상한 입력 차이와 일치하는지 대조한다.

## 흔한 실수
- `set logging enabled on`을 잊고 실행부터 해버려서, 정작 필요한 구간의 로그가 하나도 안 남는 것
- `set logging overwrite on` 상태를 모르고 재실행해서 이전 실행 로그가 사라지는 것 — 비교가 필요하면 매번 다른 파일명을 지정하거나 `overwrite off`를 유지
- x64dbg에서 Log 탭 내용을 복사할 때 일부만 선택해서 앞부분 로그가 누락되는 것
- 로그 포맷을 미리 정하지 않고 매번 다른 표현식으로 남겨서, 나중에 `grep`/`awk`로 파싱하기 어려운 비정형 텍스트가 되는 것

## 막혔을 때 다음 체크
- 애초에 어떤 값을 로그로 남길지부터 정하려면 → REV-0828 동적분석으로 검증 함수의 입출력만 계속 관찰하는 전략
- 남긴 로그로 발견한 상수를 정적분석과 맞춰보고 싶다면 → REV-0832 동적분석 중 발견한 상수를 정적분석과 다시 대조하는 법
- 지금까지의 진행 상황을 기록해 나중에 이어서 분석하고 싶다면 → REV-0317 Write-up을 읽기 전에 스스로 어디까지 풀었는지 기록하는 법
- x64dbg 자체 스크립트로 로그 남기기를 자동화하고 싶다면 → REV-0814 x64dbg 스크립트(Script) 탭으로 자동화하기 (예정)

## 미니 예제
```
(gdb) set logging file trace_run1.log
(gdb) set logging enabled on
(gdb) dprintf validate_input, "IN=%s\n", (char*)$rdi
(gdb) run
IN=AAAAAAAA
IN=passw12
(gdb) set logging enabled off
```
셸에서 확인:
```bash
$ cat trace_run1.log
IN=AAAAAAAA
IN=passw12
$ grep "passw" trace_run1.log
IN=passw12
```
GDB 콘솔에서 본 것과 동일한 내용이 `trace_run1.log` 파일에 그대로 남아, 이후 `grep`으로 원하는 줄만 골라볼 수 있었다.

## 관련 글
- REV-0828 — 동적분석으로 검증 함수의 입출력만 계속 관찰하는 전략
- REV-0832 — 동적분석 중 발견한 상수를 정적분석과 다시 대조하는 법
- REV-0317 — Write-up을 읽기 전에 스스로 어디까지 풀었는지 기록하는 법
- REV-0814 — x64dbg 스크립트(Script) 탭으로 자동화하기
- REV-0820 — GDB dprintf로 로그만 찍고 계속 실행하기

## 출처/검증
- GDB `set logging file`, `set logging enabled`, `set logging overwrite`, `set logging redirect` 명령: GNU GDB 공식 매뉴얼("Logging Output") 기준.
- x64dbg Log 탭의 텍스트 복사/저장 절차: x64dbg 공식 GitHub Wiki 문서 및 실제 UI 동작 기준 (2026-09-09 검증).
