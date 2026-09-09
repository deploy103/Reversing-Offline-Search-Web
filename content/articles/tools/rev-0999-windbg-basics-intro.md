---
id: REV-0999
title: "WinDbg 기초 소개와 언제 쓰는지"
slug: "rev-0999-windbg-basics-intro"
category: "tools"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [WinDbg]
keywords: ["WinDbg", "WinDbg 기초", "!analyze -v", "커널 디버깅", "크래시 덤프 분석", "g bp k dt 명령어"]
aliases: ["윈드박", "windbg 사용법", "windbg 기초", "윈도우 커널 디버거", "윈드박 사용법"]
symptom_keywords: ["windbg가 뭔지 모르겠음", "크래시 덤프 어떻게 분석함", "커널 디버깅 어떻게 함", "windbg 언제 써야 함", "x64dbg랑 windbg 차이"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
WinDbg는 마이크로소프트가 공식 제공하는 윈도우 전용 디버거로, x64dbg가 유저모드 프로그램을 다루는 데 최적화되어 있는 반면 WinDbg는 **커널 모드 디버깅**과 **크래시 덤프(.dmp) 파일 사후 분석**에서 사실상 대체 불가능한 표준 도구이며, 리버싱 입문자는 평소에는 x64dbg를 쓰다가 드라이버 분석이나 블루스크린(BSOD) 원인 분석이 필요할 때 WinDbg로 넘어가면 된다.

## 언제 검색해야 하나
- 프로그램이 크래시 나서 만들어진 `.dmp`(덤프) 파일을 열어서 원인을 분석해야 할 때
- `.sys` 드라이버 파일이나 커널 모드 코드를 디버깅해야 할 때(x64dbg는 유저모드 전용)
- 블루스크린(BSOD)이 발생했는데 그 원인이 된 드라이버/모듈을 찾아야 할 때
- 마이크로소프트 심볼 서버(symbol server)를 이용해서 윈도우 시스템 DLL의 함수 이름을 정확히 복원하고 싶을 때
- `!analyze -v`, `k`, `dt` 같은 WinDbg 전용 명령을 라이트업에서 봤는데 뭘 하는 명령인지 모를 때

## 핵심 개념
WinDbg는 마이크로소프트가 Windows SDK/WDK(Windows Driver Kit)의 일부로 배포하는 디버거로, 최신 버전은 Microsoft Store에서 "WinDbg Preview"로도 받을 수 있다. x64dbg가 GUI 중심에 유저모드 실행 파일(EXE/DLL) 분석에 특화되어 직관적인 반면, WinDbg는 명령어 기반(콘솔형 인터페이스)이고 다음 두 가지 영역에서 x64dbg가 하지 못하는 일을 한다.

1. **커널 모드 디버깅** — 윈도우 커널 자체나 `.sys` 드라이버 파일은 유저모드 디버거로는 디버깅할 수 없다. WinDbg는 두 대의 컴퓨터(또는 VM)를 네트워크/시리얼/USB로 연결해 한쪽(타겟)의 커널을 다른 쪽(호스트)에서 멈추고 조사하는 커널 디버깅을 지원한다.
2. **사후 크래시 덤프 분석** — 프로그램이나 시스템이 크래시났을 때 생성되는 `.dmp` 파일을 열어, 크래시가 "실제로 일어나는 순간"이 아니라 "이미 끝난 뒤에" 그 시점의 메모리/레지스터/콜스택 상태를 그대로 재구성해서 분석할 수 있다. 이는 재현이 어려운 간헐적 크래시나 고객 PC에서만 발생하는 문제를 분석할 때 특히 중요하다.

WinDbg의 명령어 체계는 GDB와 개념적으로 비슷한 부분이 많지만(중단점, 스텝, 레지스터/메모리 조회) 문법이 다르다. 핵심 명령 몇 가지는 다음과 같다.

- **`g`(Go)** — 실행을 계속 진행한다. GDB의 `continue`, x64dbg의 `F9`에 대응.
- **`bp 주소`** — 소프트웨어 브레이크포인트를 건다. GDB의 `break`에 대응.
- **`k`** — 현재 콜스택(call stack)을 출력한다. GDB의 `bt`(backtrace)에 대응.
- **`dt 타입이름 주소`** — 지정한 구조체 타입으로 메모리를 해석해서 필드별로 보여준다("display type"). C의 구조체 정의를 알고 있을 때 메모리를 필드 단위로 읽는 데 필수적인 명령이다.
- **`!analyze -v`** — 크래시 덤프를 열었을 때 가장 먼저 치는 명령. WinDbg 확장 명령(익스텐션 커맨드, `!`로 시작)이 자동으로 크래시 원인을 분석해서 스택 트레이스, 예외 코드, 문제가 된 모듈 이름 등을 요약해서 보여준다.

`!`로 시작하는 명령은 "확장 명령(extension command)"이라고 부르며, 기본 명령어 세트로는 부족한 고수준 분석(힙 분석, 예외 분석, 프로세스/스레드 목록 등)을 제공하는 별도의 확장 DLL이 제공하는 기능이다.

## 화면/코드에서 보이는 징후
크래시 덤프를 WinDbg로 열면(`File > Open Dump File`) 명령창에 다음과 비슷한 안내가 뜬다.
```text
Microsoft (R) Windows Debugger Version ...
Loading Dump File [C:\dumps\crash.dmp]
...
This dump file has an exception of interest stored in it.
...
0:000> 
```
`0:000>`이 WinDbg의 명령 프롬프트다. 여기에 `!analyze -v`를 입력하면 자동 분석이 시작된다.

## 가장 먼저 할 것
지금 하려는 작업이 정말 커널 디버깅이나 덤프 분석이 필요한 작업인지부터 확인한다. 일반적인 유저모드 EXE 리버싱(패스워드 검증 로직 찾기, 문자열 xref 추적 등)이라면 x64dbg가 훨씬 편하고 빠르다. WinDbg는 다음 두 상황 중 하나일 때만 꺼낸다: (1) `.sys` 드라이버나 커널 코드를 봐야 할 때, (2) 이미 만들어진 `.dmp` 크래시 덤프 파일을 분석해야 할 때.

## 단계별 절차

**1) 크래시 덤프 파일 열기**
`File > Open Dump File`(또는 명령줄에서 `windbg -z crash.dmp`)로 덤프를 로드한다.

**2) 자동 분석 먼저 실행**
```windbg
!analyze -v
```
크래시 원인 후보, 예외 코드, 문제가 발생한 모듈/함수, 콜스택 요약이 자동으로 출력된다. 대부분의 분석은 이 명령의 출력을 읽는 것부터 시작한다.

**3) 콜스택 직접 확인**
```windbg
k
```
`!analyze -v` 요약만으로 부족하면 `k`로 직접 콜스택을 확인해서 어떤 함수 호출 경로로 여기까지 왔는지 본다.

**4) 특정 구조체로 메모리 해석**
```windbg
dt ntdll!_TEB @$teb
```
현재 스레드의 TEB(Thread Environment Block)를 구조체 필드 단위로 펼쳐서 보여준다. `dt`는 "이 메모리 영역을 이 타입으로 해석해서 보여줘"라는 의미로, C 구조체 정의를 아는 상태에서 raw 메모리를 사람이 읽을 수 있게 바꿔준다.

**5) 라이브 프로세스에 브레이크포인트 걸고 진행**
```windbg
bp mymodule!MyFunction
g
```
유저모드 프로세스를 WinDbg로 직접 붙여서(Attach) 디버깅할 때도 `bp`로 브레이크포인트를 걸고 `g`로 실행을 재개하는 흐름은 GDB/x64dbg와 개념적으로 동일하다.

**6) 심볼(symbol) 경로 설정 — 함수 이름이 안 보일 때**
```windbg
.symfix
.reload
```
`.symfix`는 마이크로소프트 공식 심볼 서버를 심볼 경로로 자동 설정하고, `.reload`는 현재 로드된 모듈의 심볼을 다시 불러온다. 이 두 명령을 실행해야 `ntdll.dll`, `kernel32.dll` 같은 윈도우 시스템 모듈의 함수 이름이 주소 대신 사람이 읽을 수 있는 이름으로 표시된다.

## 명령어/단축키
```windbg
g                       ; 실행 계속(Go)
p                       ; 한 줄 실행(Step Over, 함수 호출은 통째로 건너뜀)
t                       ; 한 줄 실행(Step Into, 함수 호출 내부로 들어감)
bp 주소또는심볼         ; 소프트웨어 브레이크포인트 설정
bl                      ; 브레이크포인트 목록 확인
bc 번호                 ; 브레이크포인트 삭제
k                       ; 콜스택(backtrace) 출력
r                       ; 레지스터 값 확인
dt 타입 주소            ; 구조체 타입으로 메모리 해석
dd / dq / db 주소       ; 메모리를 4바이트/8바이트/1바이트 단위로 덤프
u 주소                  ; 디스어셈블(unassemble)
!analyze -v             ; 크래시 자동 분석(덤프 분석의 시작점)
!process 0 0            ; 전체 프로세스 목록(커널 디버깅 시)
.symfix / .reload       ; 심볼 서버 자동 설정 및 심볼 재로딩
```

## 출력 해석
- `!analyze -v` 결과에 나오는 **`FAULTING_IP`** — 크래시가 발생한 정확한 명령어 주소. 이 주소가 어떤 모듈(DLL/드라이버) 소속인지가 문제의 첫 단서다.
- **`STACK_TEXT`** — 크래시 시점의 콜스택. 위에서부터 "가장 최근에 호출된 함수"이며, 이 목록을 위에서 아래로 읽으면 어떤 함수 호출 경로로 크래시 지점까지 왔는지 알 수 있다.
- **`BUCKET_ID`** / **`FAILURE_BUCKET_ID`** — 마이크로소프트가 유사한 크래시를 자동 분류하는 데 쓰는 식별자로, 같은 버그로 인한 다른 크래시 리포트와 비교할 때 유용하다.
- `k` 출력에서 함수 이름 대신 `모듈+0x1234` 형태(예: `ntdll!0x7ffabc123456`)로만 나온다면, 그 모듈의 심볼이 로드되지 않았다는 뜻이다 — `.symfix`/`.reload`를 실행해야 한다.

## 흔한 실수
- 일반적인 유저모드 EXE 리버싱까지 전부 WinDbg로 하려다가, x64dbg의 직관적인 GUI(레지스터 뷰, 메모리 뷰, 그래프 뷰가 한 화면에 동시에 보이는 구조)에 비해 훨씬 느리고 번거로운 경험을 하는 것 — 용도가 다른 도구라는 점을 먼저 이해해야 한다.
- 심볼 경로를 설정하지 않고(`.symfix`/`.reload` 생략) 콜스택을 봐서, 함수 이름 없이 주소만 잔뜩 나오는 화면을 보고 "덤프가 망가졌다"고 오해하는 것.
- 오프라인 환경에서는 마이크로소프트 심볼 서버에 접속할 수 없으므로 `.symfix`가 제대로 동작하지 않을 수 있다는 점을 모르고 계속 시도하는 것 — 오프라인 대회 환경에서는 시스템 DLL 심볼이 없는 상태로 분석해야 할 수도 있음을 감안해야 한다.
- 커널 디버깅을 하려면 두 대의 머신(또는 VM 스냅샷 2개) 구성이 필요하다는 걸 모르고, 한 대의 컴퓨터에서 자기 자신의 커널을 실시간으로 디버깅하려 시도하는 것.
- `!analyze -v`가 제시하는 결론(추정 원인 모듈)을 그대로 최종 원인으로 확정해버리는 것 — 이 명령은 자동 추정이며, 실제로는 `k`(콜스택)와 `dt`(구조체 조회)로 직접 확인하는 검증이 필요한 경우가 많다.

## 막혔을 때 다음 체크
- 함수 이름이 하나도 안 보인다면 → `.symfix` 후 `.reload` 실행, 오프라인이면 애초에 온라인 심볼 서버 접속이 안 될 수 있음을 감안한다.
- WinDbg와 GDB/x64dbg 명령어를 서로 대응시켜 외우고 싶다면 → REV-0813 디버거별 명령어 대응표(GDB vs x64dbg vs WinDbg).
- 시간을 거슬러 재실행(Time Travel Debugging) 개념이 궁금하다면 → REV-0822 Time Travel Debugging 개념 소개(WinDbg 참고).
- 드라이버(.sys) 파일 자체를 처음 만났을 때 최소한 뭘 확인해야 하는지는 → REV-0562 드라이버(.sys) 파일을 만났을 때 최소 대응.
- 유저모드 EXE 분석에 더 편한 도구가 필요하면 → REV-0280 x64dbg 설치 및 REV-0281 x64dbg 단축키 치트시트.

## 미니 예제
간단한 크래시 덤프를 열어 원인을 좁혀가는 전형적인 흐름이다.
```windbg
0:000> !analyze -v
...
FAULTING_IP:
mymodule!ProcessData+0x42
...
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - Access violation
...
STACK_TEXT:
00 mymodule!ProcessData+0x42
01 mymodule!HandleRequest+0x1a0
02 kernel32!BaseThreadInitThunk+0x14

0:000> k
 # Child-SP          RetAddr           Call Site
00 00000000`0012fa20 00007ff6`12340a10 mymodule!ProcessData+0x42
01 00000000`0012fa60 00007ff8`abcd1234 mymodule!HandleRequest+0x1a0
02 00000000`0012fb00 00000000`00000000 kernel32!BaseThreadInitThunk+0x14

0:000> dt mymodule!MYSTRUCT @rcx
   +0x000 field1 : 0x1337
   +0x008 field2 : 0x00000000`00000000
```
`EXCEPTION_CODE: 0xc0000005`(Access Violation, 잘못된 메모리 접근)이 크래시 원인이고, `STACK_TEXT`를 보면 `HandleRequest`가 `ProcessData`를 호출했다가 그 안의 `+0x42` 오프셋에서 문제가 생겼다는 흐름을 알 수 있다. 이어서 `dt`로 관련 구조체(`MYSTRUCT`)의 필드값을 확인하면, `field2`가 `NULL`인 상태에서 참조되어 크래시가 났다는 식의 구체적 원인까지 좁혀갈 수 있다.

## 관련 글
- REV-0813 — 디버거별 명령어 대응표(GDB vs x64dbg vs WinDbg)
- REV-0822 — Time Travel Debugging 개념 소개(WinDbg 참고)
- REV-0562 — 드라이버(.sys) 파일을 만났을 때 최소 대응
- REV-0280 — x64dbg 설치와 오프라인 준비

## 출처/검증
- WinDbg 명령어(`g`, `bp`, `k`, `dt`, `dd`, `u`, `!analyze -v`, `.symfix`, `.reload`)와 커널/유저모드 디버깅 구분, 크래시 덤프 분석 개념은 마이크로소프트 공식 문서(Microsoft Learn, "Debugging Tools for Windows", "WinDbg overview", "Getting Started with WinDbg") 기준으로 정리했다(2026-09-09 검증).
- 예외 코드 `0xc0000005`(STATUS_ACCESS_VIOLATION)는 Windows NTSTATUS 값 공식 문서 기준이다.
- 마이크로소프트 공식 심볼 서버 및 `.symfix`/`.reload` 동작은 Microsoft Learn "Symbols" 문서 기준이다.
