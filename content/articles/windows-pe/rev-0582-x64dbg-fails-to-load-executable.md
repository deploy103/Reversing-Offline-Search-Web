---
id: REV-0582
title: "x64dbg가 실행 파일을 로드하지 못할 때"
slug: "rev-0582-x64dbg-fails-to-load-executable"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, DIE, PE-bear]
keywords: ["x64dbg 로드 실패", "only x64 applications are supported", "x32dbg", "not a valid Win32 application", "아키텍처 불일치"]
aliases: ["x64dbg가 실행파일을 못 엶", "x64dbg open file 실패", "x32dbg x64dbg 구분"]
symptom_keywords: ["x64dbg로 exe를 열면 에러가 뜬다", "only x64 applications are supported 메시지", "x64dbg가 아무 반응이 없다", "디버거에 파일이 안 열린다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x64dbg가 실행 파일 로드에 실패하면 대부분 32/64비트 불일치, 손상된 PE 헤더, 권한 문제, 백신 차단 중 하나이며 오류 메시지 문구로 원인을 좁힐 수 있다.

## 진단 먼저: 어떤 증상인지부터 구분한다
x64dbg가 파일을 못 여는 상황은 크게 세 가지로 나뉘며, 원인과 해결책이 서로 다르다.

1. **"Only x64 applications are supported!"** 같은 메시지가 뜨거나 File → Open 직후 아무 반응 없이 실패한다 → **아키텍처 불일치**. 가장 흔한 원인이다.
2. Windows 자체가 **"이 앱은 사용 중인 PC에서 실행할 수 없습니다"/"~은(는) 올바른 Win32 응용 프로그램이 아닙니다"** 같은 대화상자를 띄운다 → **파일 자체가 손상되었거나 대상 아키텍처의 Windows에서 실행 불가능**.
3. 파일은 열리는데(디스어셈블리는 보임) 실행(`F9`)만 누르면 즉시 죽거나 반응이 없다 → 이건 로드 실패가 아니라 **REV-0583(anti-attach)** 또는 **REV-0585(entry point 오류)** 문제이므로 해당 글을 참고한다.

## 언제 검색해야 하나
- x64dbg로 File → Open File(`F3`)을 했는데 파일이 열리지 않거나 에러 메시지가 뜰 때
- 32비트 실행 파일을 x64dbg(64비트용)로 열었을 때, 또는 그 반대일 때
- 방금 언패킹/덤프한 파일이 x64dbg는 물론 탐색기에서 더블클릭해도 안 열릴 때
- 관리자 권한 없이 x64dbg를 실행해서 특정 프로세스나 파일에 접근이 막힐 때

## 핵심 개념
x64dbg 프로젝트는 아키텍처별로 완전히 분리된 두 개의 실행 파일을 제공한다: **`x32dbg.exe`**(32비트 대상 전용)와 **`x64dbg.exe`**(64비트 대상 전용). `x64dbg.exe`는 시작 시 `x96dbg.exe` 런처를 통해 대상 파일의 PE 헤더(`IMAGE_FILE_HEADER.Machine`)를 보고 자동으로 올바른 서브 프로세스를 실행해주지만, `x32dbg.exe`/`x64dbg.exe`를 직접(런처를 거치지 않고) 실행한 상태에서 반대 아키텍처 파일을 열면 명시적으로 거부한다. 이는 디버거가 대상 프로세스와 같은 비트수의 메모리 공간을 다뤄야 레지스터/스택/구조체 크기를 정확히 해석할 수 있기 때문이다.

Windows 로더 차원의 실패("올바른 Win32 응용 프로그램이 아님")는 x64dbg와 무관하게 파일 자체가 실행 가능한 PE 구조를 갖추지 못했다는 뜻이며, PE 헤더가 손상되었거나(수동 편집 실수), 32비트 전용 Windows에서 64비트 EXE를 실행하려 했거나, 파일이 아예 PE가 아닌데 확장자만 `.exe`인 경우다.

## 화면/코드에서 보이는 징후
- x64dbg 로그 창(하단)에 `Only x64 applications are supported, use x32dbg instead!`(또는 반대) 메시지가 출력됨
- Windows 대화상자: `%1은(는) 올바른 Win32 응용 프로그램이 아닙니다.` 또는 `이 앱은 사용 중인 PC에서 실행할 수 없습니다.`
- x64dbg가 파일 선택 대화상자까지는 정상 동작하지만, 확인을 누른 직후 아무 창도 안 뜨고 로그에만 실패 메시지가 남음
- PE-bear로 열었을 때 `IMAGE_FILE_HEADER.Machine` 필드가 `0x8664`(AMD64)인데 32비트용 도구로 열려 했거나, `0x014c`(I386)인데 64비트용 도구로 열려 한 경우

## 가장 먼저 할 것
대상 파일이 32비트인지 64비트인지부터 확인한다. PE-bear로 열어 `File Header` → `Machine` 필드를 보거나, DIE로 열어 상단에 표시되는 "32-bit"/"64-bit" 표시를 확인한다. 그다음 그에 맞는 실행 파일(`x32dbg.exe` 또는 `x64dbg.exe`)을 직접 실행해서 다시 시도한다.

## 단계별 절차
**1) 아키텍처 확인 및 올바른 실행 파일 선택**
- x64dbg 설치 폴더에는 `x32dbg.exe`, `x64dbg.exe`, 그리고 자동 판별용 `x96dbg.exe`가 함께 있다. 어떤 비트인지 모르겠다면 `x96dbg.exe`(또는 바탕화면에 x96dbg로 만든 바로가기)로 열면 자동으로 알맞은 쪽을 실행해준다.
- 32비트 파일은 `x32dbg.exe`로, 64비트 파일은 `x64dbg.exe`로 직접 열면 이 문제는 대부분 해결된다.

**2) Windows 자체 로드 실패("올바른 Win32 응용 프로그램 아님")일 때**
- PE-bear나 HxD로 파일을 열어 첫 두 바이트가 `MZ`(0x4D 0x5A)로 시작하는지, DOS 헤더의 `e_lfanew` 필드가 실제 `PE\0\0` 시그니처 위치를 정확히 가리키는지 확인한다. 수동 편집 중 이 값이 틀어지면 이 오류가 뜬다.
- 언패킹 도구나 덤프 도구(Scylla 등)로 만든 파일이라면, 헤더 재구성(섹션 정렬, `SizeOfImage` 재계산)이 제대로 되었는지 다시 확인한다.
- 64비트 EXE를 32비트 전용 Windows에서 실행하려는 것은 아닌지 확인한다(과거 32비트 Windows 환경에서 흔한 문제).

**3) 관리자 권한/보안 소프트웨어 문제일 때**
- 대상 파일이 서비스 실행 파일이거나 시스템 보호 폴더에 있다면 x64dbg를 관리자 권한("관리자 권한으로 실행")으로 다시 열어본다.
- 백신/EDR이 새로 만든(패치/덤프한) 실행 파일을 격리(quarantine)했을 수 있으므로 백신 로그를 확인한다.

## 명령어/단축키
- x64dbg: `F3`(File → Open File), 로그 창은 기본적으로 하단에 표시(안 보이면 View → Log)
- PE-bear: 파일 드래그 후 좌측 트리에서 `IMAGE_FILE_HEADER` → `Machine` 필드 확인
- DIE: 상단 요약 영역에서 비트수(32-bit/64-bit) 즉시 확인 가능

## 출력 해석
- `Machine` 필드가 `0x014c`면 x86(32비트), `0x8664`면 x64(AMD64, 64비트), `0x01c0`이면 ARM 계열이므로 x64dbg가 아예 지원하지 않는 대상일 수 있다.
- x64dbg 로그에 `Failed to load the debuggee!`가 뜨면 아키텍처 문제가 아니라 파일 경로/권한/파일 자체 손상 쪽을 의심해야 한다 — 파일 경로에 한글/공백이 포함된 경우도 드물게 문제를 일으키므로 영문 경로로 옮겨서 재시도해본다.

## 흔한 실수
- `x64dbg.exe`라는 이름만 보고 "64비트 프로그램은 이걸로, 32비트도 이걸로 다 된다"고 착각하는 것 — 이름 자체가 "64비트 대상 전용"이라는 뜻이다.
- `x96dbg.exe` 런처를 안 쓰고 매번 수동으로 어떤 걸 써야 할지 헷갈려하는 것 — 바탕화면 바로가기를 x96dbg로 만들어두면 이후 계속 편하다.
- 파일이 손상된 것을 x64dbg의 버그로 오인해서 재설치를 반복하는 것 — PE-bear/HxD로 헤더를 먼저 확인하면 원인이 x64dbg가 아니라 파일 자체임을 바로 알 수 있다.
- 관리자 권한 문제를 아키텍처 문제로 착각해서 계속 다른 아키텍처의 x64dbg/x32dbg를 번갈아 시도하는 것.

## 막혔을 때 다음 체크
- 파일은 열리는데 실행하자마자 바로 죽는다면 → REV-0583(x64dbg로 붙였는데 바로 종료(anti-attach)될 때) 참고
- "Entry Point를 찾을 수 없다"는 별도 오류가 뜬다면 → REV-0585(Entry Point를 찾을 수 없다는 오류가 뜰 때) 참고
- x64dbg 자체 사용법이 처음이라면 → REV-0127(x64dbg로 EXE 첫 분석 시작) 참고

## 미니 예제
```
x64dbg 상태바: "Failed to load module!"
→ file target.exe 결과: "PE32 executable" (32비트)
→ 실행한 도구: x64dbg.exe (64비트 전용)
→ x32dbg.exe로 다시 열면 정상 로드됨
```

## 관련 글
- REV-0127 — x64dbg로 EXE 첫 분석 시작
- REV-0583 — x64dbg로 붙였는데 바로 종료(anti-attach)될 때
- REV-0585 — Entry Point를 찾을 수 없다는 오류가 뜰 때
- REV-0114 — PE 파일 구조 한 번에 보기

## 출처/검증
- x64dbg가 `x32dbg.exe`/`x64dbg.exe`로 아키텍처별 실행 파일을 분리 제공하고, `x96dbg.exe`가 자동 판별 런처 역할을 한다는 점은 x64dbg 공식 프로젝트(x64dbg.com, GitHub x64dbg/x64dbg)의 배포 구조 기준이다.
- `IMAGE_FILE_HEADER.Machine` 필드 값(`0x014c`=I386, `0x8664`=AMD64)은 Microsoft PE Format 공식 문서 기준이다.
- Windows의 "올바른 Win32 응용 프로그램이 아닙니다" 오류는 일반적으로 알려진 Windows 로더 동작에 대한 서술이다(2026-09-08 기준).
