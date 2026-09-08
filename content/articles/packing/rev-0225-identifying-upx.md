---
id: REV-0225
title: "UPX인지 확인하는 법"
slug: "rev-0225-identifying-upx"
category: "packing"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["Detect It Easy", "UPX", x64dbg, IDA]
keywords: ["UPX", "UPX 확인", "UPX0", "UPX1", "UPX2", "UPX 시그니처", "UPX!", "upx -V", "upx -l", "Ultimate Packer for eXecutables", "UPX 매직 바이트"]
aliases: ["upx 확인", "이거 upx야", "upx인지 아닌지", "UPX packed", "UPX 판별", "UPX 여부"]
symptom_keywords: ["섹션 이름이 UPX0 UPX1", "strings에 UPX! 나옴", "IDA에서 UPX 섹션 보임", "이 파일 upx로 패킹된 건가", "UPX인지 확인하는 방법", "die에서 upx라고 뜸"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
섹션 이름이 `UPX0`/`UPX1`(/`UPX2`)이거나, `strings` 결과에 `UPX!`나 `$Info: This file is packed with the UPX executable packer`가 보이거나, Detect It Easy가 "Packer: UPX"라고 표시하면 그 바이너리는 **UPX**로 패킹된 것이다.

## 언제 검색해야 하나
- REV-0224 체크리스트로 패킹을 의심했고, 구체적으로 UPX인지 아닌지 확실히 확인하고 싶을 때
- IDA/PE-bear에서 섹션 이름이 `UPX0`, `UPX1` 같은 낯선 이름으로 보일 때
- `strings sample.exe`를 쳤는데 `UPX!`라는 짧은 문자열이 보일 때
- 언패킹을 시도하기 전에 "정말 UPX 명령으로 풀 수 있는 종류가 맞는지" 미리 확인하고 싶을 때
- Detect It Easy가 패커 이름을 보여주긴 했는데 그게 진짜 UPX인지, UPX를 흉내 낸 다른 것인지 헷갈릴 때

## 핵심 개념
**UPX(Ultimate Packer for eXecutables)**는 가장 널리 쓰이는 오픈소스 실행 파일 압축기다. Markus Oberhumer, László Molnár, John Reiser가 만들었으며 Windows PE(exe/dll), Linux ELF, macOS Mach-O 등 여러 실행 파일 포맷을 지원한다. UPX가 유명한 이유는 두 가지다. 첫째, 오픈소스이고 무료라서 정상적인 소프트웨어 배포에도, CTF 문제 출제나 악성코드 제작에도 흔히 쓰인다. 둘째, **`upx -d`라는 명령 한 줄로 대부분 자동 언패킹이 가능**하다(REV-0226 참고). 그래서 "이 파일이 UPX인지 아닌지"를 정확히 구분하는 것 자체가 실전에서 시간을 크게 아껴주는 첫 단계다.

UPX는 압축 해제 스텁(unpacking stub)을 원본 실행 파일 앞에 붙이는 방식으로 동작한다. 원본 코드/데이터는 압축되어 별도 섹션에 저장되고, 프로그램이 실행되면 스텁이 그 압축 데이터를 메모리에 풀어놓은 뒤 원래 프로그램의 시작 지점(OEP, Original Entry Point — REV-0227 참고)으로 점프한다. 이 과정에서 UPX는 몇 가지 알아보기 쉬운 흔적을 파일에 남기는데, 이 흔적들이 바로 "UPX인지 확인하는" 근거가 된다.

## 화면/코드에서 보이는 징후
UPX로 패킹된 PE 파일은 다음과 같은 특징을 거의 항상 보인다.

1. **섹션 이름 `UPX0`, `UPX1`, (`UPX2`)** — Windows PE 기준으로 UPX는 보통 섹션을 두세 개로 나눈다. `UPX0`은 압축 해제 후 코드가 펼쳐질 빈 공간(raw size 0, virtual size만 큼), `UPX1`은 실제 압축된 데이터와 압축 해제 스텁 코드, `UPX2`는 원본에 리소스 섹션(.rsrc)이 있었을 경우 그것을 담는 섹션이다. IDA의 Segments 창이나 PE-bear의 Section Headers 탭에서 바로 확인할 수 있다.
2. **`strings` 결과에 `UPX!` 매직 바이트** — UPX는 압축 헤더에 4바이트짜리 매직 시그니처 `UPX!`(0x21585055)를 남긴다. `strings sample.exe | grep UPX`로 찾을 수 있다.
3. **UPX 저작권/안내 문자열** — 오래된 버전이나 옵션에 따라 `$Info: This file is packed with the UPX executable packer http://upx.sf.net $`, `$Id: UPX ...` 같은 문자열이 그대로 남아 있는 경우가 많다. UPX 제작자들은 이 압축기가 "무해한 압축 도구"임을 명확히 하기 위해 일부러 이런 식별 정보를 남긴다.
4. **Detect It Easy(DIE) 상단 결과란에 "Packer: UPX(버전) [...]"** — DIE는 UPX 전용 시그니처를 갖고 있어서 파일을 드래그하는 즉시 UPX 여부와 버전(예: `UPX(3.96)`)까지 알려준다. REV-0126(../windows-pe/rev-0126-die-basics.md)에서 DIE 사용법을 참고한다.
5. **entry point 코드 패턴** — IDA View-A로 entry point에 가보면 `PUSHAD` 한 줄, 그 다음 `MOV ESI, ...` / `LEA EDI, ...`로 시작하는 압축 해제 루프, 마지막에 `POPAD` 후 `JMP` 한 줄로 끝나는 매우 짧고 규칙적인 코드가 보인다. 이는 UPX 스텁의 전형적인 x86 어셈블리 패턴이다.
6. **UPX 전용 명령으로 정보 확인 가능** — 만약 로컬에 upx 실행 파일이 있다면 `upx -l sample.exe`(list, 압축 정보만 조회)나 `upx -V`(버전 확인용, 파일과 무관)를 시도해서 UPX가 이 파일을 인식하는지 바로 검증할 수 있다.

## 가장 먼저 할 것
바이너리를 열자마자 `strings sample.exe | grep -i upx`부터 실행해본다(WSL/Git Bash/Linux). 이 한 줄로 `UPX!`나 안내 문자열이 나오면 사실상 확정이다. 문자열 검색이 애매하면 Detect It Easy에 파일을 드래그해서 상단 결과란을 확인한다.

## 단계별 절차

**1) strings로 매직 바이트/문자열 확인**

```bash
strings sample.exe | grep -i upx
```

`UPX!`, `UPX0`, `UPX1`, `$Info: This file is packed with the UPX` 등이 나오면 UPX가 거의 확실하다.

**2) 섹션 이름 확인**

IDA에서 `View → Open Subviews → Segments`를 열거나, PE-bear에서 Section Headers 탭을 연다. 이름이 `UPX0`, `UPX1`로 되어 있는지 확인한다. 단, 일부 최신 UPX 버전이나 옵션은 섹션 이름을 랜덤하게 바꾸거나 지울 수 있으므로(안티 언패킹 목적), 섹션 이름이 안 보인다고 UPX가 아니라고 단정하지 않는다.

**3) Detect It Easy로 확정**

DIE에 파일을 드래그한다. 상단에 `Packer: UPX(3.96) [-]` 같은 형식으로 뜨면 UPX가 확실하며 괄호 안 숫자가 버전이다. DIE가 시그니처를 못 잡으면 "Unknown"이 뜨는데, 이 경우에도 1)/2) 단계의 흔적이 있다면 UPX일 가능성이 높다(변형되었거나 아주 오래되었거나 최신 버전일 수 있음).

**4) upx 명령 자체로 검증**

로컬에 UPX가 설치되어 있다면 다음을 실행해본다.

```bash
upx -l sample.exe
```

이 명령은 파일을 수정하지 않고 압축 정보(원본 크기, 압축 크기, 비율, 포맷)만 출력한다. UPX가 인식하지 못하는 파일이면 "NotPackedException" 또는 "CantPackException" 계열 오류가 난다.

**5) 결론에 따라 다음 단계로**

UPX로 확인되면 REV-0226(UPX 기본 언패킹)의 `upx -d` 절차로 바로 넘어간다. UPX가 아니라고 확인되면(다른 패커 시그니처가 뜨거나 upx가 인식을 거부하면) REV-0227(수동 언패킹 개념)로 이동한다.

## 명령어/단축키
- `strings sample.exe | grep -i upx` : UPX 관련 문자열 검색 (Linux/WSL/Git Bash)
- `upx -l sample.exe` : 압축 정보만 조회 (파일 수정 없음)
- `upx -V` : 설치된 upx 버전 확인
- IDA `View → Open Subviews → Segments` : 섹션 이름/크기 확인
- Detect It Easy: 파일 드래그 → 상단 결과란 확인

## 출력 해석
- `strings` 결과에 `UPX!`가 딱 한 줄만 나오고 다른 문자열이 거의 없으면 → 매우 전형적인 UPX 패킹. 압축 데이터 자체는 사람이 읽을 수 없으므로 `UPX!` 매직 외에 다른 문자열이 안 보이는 것이 정상이다.
- `upx -l sample.exe`가 다음과 비슷한 표를 출력하면 UPX가 확실하다.

```text
       File size         Ratio      Format      Name
   --------------------   ------   -----------   -----------
    245760 <-    102400   41.67%    win64/pe     sample.exe
```

- `upx -l sample.exe`가 `sample.exe: NotPackedException: not packed by UPX`를 출력하면 → UPX가 아니거나, UPX로 패킹됐어도 이후 다른 도구로 한 번 더 변형(예: 섹션 이름 지우기, 헤더 훼손)되어 UPX가 인식을 거부하는 상태다. 이런 경우는 REV-0227의 수동 언패킹 개념이 필요하다.
- DIE가 `Packer: UPX(4.2.4) [NRV,brute]` 처럼 압축 알고리즘 옵션까지 보여주면, `upx -d`로 언패킹할 때 특별한 옵션 없이도 대부분 잘 풀린다는 신호다.

## 흔한 실수
- 섹션 이름이 `UPX0`/`UPX1`이 아니라고 해서 UPX가 아니라고 단정하는 것. 일부 CTF 문제나 변형 UPX는 섹션 이름을 일부러 다른 이름(`.text`, 랜덤 문자열 등)으로 바꿔서 자동 탐지를 회피하기도 한다. 이럴 땐 `UPX!` 매직 바이트나 entry point 코드 패턴을 함께 봐야 한다.
- `upx -l`이 실패했다고 바로 포기하는 것. 헤더가 살짝 손상되었거나 섹션 이름이 지워진 경우, `upx -d`의 `--force` 옵션으로 강제 시도가 가능한 경우도 있다(REV-0226 참고).
- DIE가 "Unknown"이라고만 뜨는 것을 "UPX가 아니다"로 오해하는 것. DIE 시그니처 DB가 아주 최신/변형 버전을 못 알아볼 수도 있으므로 문자열/섹션 흔적을 추가로 확인해야 한다.
- `strings` 결과에 `UPX!`가 있다고 무조건 `upx -d`부터 실행하는 것. 실행 전에 원본 파일을 반드시 백업해두어야 한다(REV-0226 참고). `upx -d`는 기본적으로 파일을 덮어쓴다.

## 막혔을 때 다음 체크
- `strings`, 섹션 이름, DIE 모두 UPX 흔적이 없다면 → REV-0224로 돌아가 다른 패커 가능성(엔트로피, entry point 코드)을 재검토한다.
- UPX가 맞는 것 같은데 `upx -l`이 계속 실패한다면 → 헤더가 변형되었을 가능성이 있으니 REV-0226의 `--force` 관련 안내를 확인한다.
- UPX 버전이 너무 오래되었거나 너무 최신이라 로컬 upx 도구와 호환이 안 되면 → 공식 GitHub 릴리스(github.com/upx/upx/releases)에서 여러 버전을 받아 시도해본다.
- 확실히 UPX로 확인됐다면 → REV-0226로 바로 이동한다.

## 미니 예제
Linux ELF 파일 `chall`을 받았다고 하자.

```bash
$ file chall
chall: ELF 64-bit LSB pie executable, x86-64, ...

$ strings chall | grep -i upx
UPX!
$Info: This file is packed with the UPX executable packer http://upx.sf.net $
$Id: UPX 4.2.4 Copyright (C) 1996-2024 the UPX Team. All Rights Reserved. $

$ upx -l chall
       File size         Ratio      Format      Name
   --------------------   ------   -----------   -----------
     18432 <-      9216   50.00%   linux/amd64   chall
```

`UPX!` 매직과 안내 문자열, 그리고 `upx -l`이 정상적으로 압축 정보를 출력하는 것까지 확인했으므로 이 파일은 100% UPX로 패킹된 것이다. 이제 REV-0226에서 설명하는 `upx -d chall` 한 줄로 언패킹을 진행하면 된다.

## 관련 글
- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0226 — UPX 기본 언패킹
- REV-0228 — Entropy가 높은 Section의 의미
- ../windows-pe/rev-0126-die-basics.md — Detect It Easy 기본 사용법

## 출처/검증
- UPX의 섹션 명명 규칙(UPX0/UPX1/UPX2), `UPX!` 매직 바이트, 안내 문자열, `-l`/`-V` 옵션 동작은 UPX 공식 GitHub 저장소(github.com/upx/upx) 및 공식 매뉴얼(`upx --help`, man 페이지) 내용을 기준으로 정리했다(2026-09-08 검증).
- Detect It Easy의 UPX 시그니처 인식은 프로젝트 공식 저장소(github.com/horsicq/Detect-It-Easy)의 시그니처 데이터베이스 설명을 참고했다.
- UPX 버전에 따라 출력 형식(표 컬럼, 문자열 위치)이 조금씩 달라질 수 있으므로, 실제 설치된 upx 버전에서 `upx -V`로 버전을 확인하고 재검증하는 것을 권장한다.
