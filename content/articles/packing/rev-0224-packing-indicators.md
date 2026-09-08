---
id: REV-0224
title: "패킹된 바이너리인지 의심하는 기준"
slug: "rev-0224-packing-indicators"
category: "packing"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["Detect It Easy", "UPX", x64dbg, IDA]
keywords: ["패킹 탐지", "packing indicator", "패킹 의심", "패커 확인", "섹션 이름 이상", "높은 entropy", "import 거의 없음", "entry point 이상", "UPX 흔적", "packed binary"]
aliases: ["패킹 여부 확인", "packed binary check", "이 파일 패킹된 거야", "패킹인지 아닌지 구분", "packer detected"]
symptom_keywords: ["함수가 하나도 안 보임", "strings 쳤는데 아무것도 안 나옴", "import가 3개밖에 없음", "섹션 이름이 이상함", "파일 크기는 큰데 코드가 없음", "IDA가 분석을 거의 못함", "entry point가 이상한 데로 점프함", "디컴파일이 전부 쓰레기값"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
파일 크기에 비해 문자열/함수/import가 비정상적으로 적고, 섹션 이름이 낯설거나 엔트로피가 8.0에 가깝고, entry point가 정상적인 컴파일러 stub이 아니라 이상한 곳으로 바로 점프한다면 패킹(packing)을 의심해야 한다.

## 언제 검색해야 하나
- IDA나 Ghidra에 바이너리를 열었는데 함수가 1~5개밖에 안 잡히고 나머지가 전부 회색(코드 아님)으로 보일 때
- `strings` 명령이나 IDA Strings 창(Shift+F12)에 의미 있는 문자열이 거의 안 나올 때
- Imports 창에 `LoadLibraryA`, `GetProcAddress` 몇 개 말고는 API가 거의 없을 때
- 파일 크기는 몇백 KB인데 실제 코드 섹션은 몇 KB짜리 스텁(stub) 코드만 있을 때
- 30초 트리아지(REV-0001) 도중 "뭔가 이상하다"는 느낌을 받았을 때 구체적인 체크리스트가 필요할 때

## 핵심 개념
**패킹(packing)**은 원본 실행 파일(코드+데이터)을 압축하거나 암호화한 뒤, 그 압축/암호화된 덩어리와 함께 "실행 시점에 원본을 메모리에 복원하고 원래 코드로 점프하는" 작은 압축 해제 스텁(stub)을 합쳐 새 실행 파일을 만드는 기법이다. 원래 목적은 파일 크기를 줄이는 것이었지만(UPX 등), 리버싱 관점에서는 정적 분석(디스어셈블/디컴파일)을 방해하는 효과가 있어서 악성코드나 CTF 문제에서 안티 리버싱 목적으로도 널리 쓰인다.

패킹된 파일을 디스크에서 열어보면 디스어셈블러가 보는 것은 **압축된 원본 데이터**이지 실제 실행될 코드가 아니다. 진짜 코드는 프로그램이 실행되어 압축 해제 스텁이 메모리에 원본을 풀어놓은 **다음에만** 존재한다. 그래서 IDA/Ghidra 같은 정적 분석 도구는 패킹된 파일을 열면 "코드가 거의 없다"는 이상한 결과를 보여주게 된다.

이 개념을 이해하면 왜 아래 징후들이 패킹의 단서가 되는지 자연스럽게 설명된다: 압축된 데이터는 사람이 읽을 수 있는 문자열이 아니고(문자열 부족), 원본 프로그램이 쓰던 API 호출 흔적도 아직 바인딩되지 않았고(import 부족), 코드처럼 보이는 부분도 실제로는 무작위에 가까운 압축 바이트일 뿐이다(엔트로피 상승, 함수 인식 실패).

## 화면/코드에서 보이는 징후
다음 항목이 **여러 개 동시에** 겹치면 패킹을 강하게 의심해야 한다. 하나만으로는 오탐(예: 정말로 문자열이 적은 유틸리티)일 수 있다.

1. **함수 개수가 비정상적으로 적음** — IDA Functions 창(Ctrl+P)에서 파일 크기 대비 함수가 몇 개 안 잡힘. 정상적인 C/C++ 프로그램은 몇백 KB만 되어도 수십~수백 개의 함수(라이브러리 함수 포함)가 잡히는 것이 보통이다.
2. **문자열이 거의 없음** — `strings` 명령이나 Strings 창에 의미 있는 텍스트가 안 보이고, 있어도 압축 알고리즘 관련 매직 바이트나 랜덤해 보이는 조각뿐.
3. **Import table이 텅 비어 있음** — Imports 창에 `kernel32.dll`의 `LoadLibraryA`, `GetProcAddress`, `VirtualAlloc`, `VirtualProtect` 정도만 있고 나머지 API가 하나도 안 보임. 이는 원본이 쓰는 진짜 API들이 압축 해제 이후 스텁이 직접 주소를 찾아서 쓰기 때문이다(REV-0229 참고).
4. **섹션 이름이 낯설거나 크기가 이상함** — 표준 PE는 보통 `.text`, `.data`, `.rdata`, `.rsrc` 등을 쓰는데, `UPX0`, `UPX1`, `.aspack`, `.themida`, `.vmp0` 같은 패커 고유 섹션 이름이 보이거나, `.text` 섹션의 "raw size"는 0에 가까운데 "virtual size"만 몇 배 큰 경우(압축 해제 후 펼쳐질 공간만 미리 예약해둔 것).
5. **섹션 엔트로피가 높음** — Detect It Easy나 PE-bear로 섹션별 엔트로피를 보면 코드/데이터 섹션이 7.5~8.0 bits/byte에 가까움(정상 `.text`는 보통 5.5~6.5 정도). 자세한 내용은 REV-0228 참고.
6. **entry point 코드가 짧고 이상함** — IDA View에서 entry point로 가보면 익숙한 컴파일러 초기화 코드(`__security_init_cookie`, `__libc_start_main` 호출 등)가 아니라, 몇 개의 `PUSHAD`/`POPAD`, 큰 루프, 이상한 API 호출(`VirtualAlloc`, `VirtualProtect`) 몇 줄만 있고 바로 알 수 없는 주소로 점프함.
7. **파일 자체의 엔트로피가 높음** — Detect It Easy의 "Entropy" 탭에서 파일 전체 엔트로피를 보여주는데, 실행 파일 전체가 7.9 이상이면 거의 확실히 압축 또는 암호화되어 있다는 뜻이다.
8. **패커 시그니처 문자열이 그대로 남아 있음** — `strings` 결과에 `UPX!`, `This program cannot be run in DOS mode`만 있고 그 외 텍스트가 없거나, `$Info: This file is packed` 같은 패커 특유의 문구가 보임(UPX는 오히려 친절하게 이런 문구를 남긴다).

## 가장 먼저 할 것
IDA/Ghidra에서 함수나 문자열이 이상하게 적다고 느끼는 순간, 바로 디스어셈블을 계속 파고들지 말고 **Detect It Easy(DIE)로 먼저 열어본다.** DIE는 시그니처 데이터베이스를 기반으로 "이 파일이 어떤 패커/컴파일러로 만들어졌는지"를 즉시 알려주므로, 몇 분간 헛수고할 시간을 절약해준다. DIE 사용법은 REV-0126(Detect It Easy 기본 사용법, ../windows-pe/rev-0126-die-basics.md)을 참고한다.

## 단계별 절차

**1) 파일 크기와 문자열 양을 먼저 비교한다**

Windows라면 `strings sample.exe | wc -l`(WSL/Git Bash), Linux라면 `strings sample | wc -l`로 문자열 줄 수를 센다. 파일이 200KB인데 문자열이 20줄도 안 되면 의심스럽다.

**2) Imports 창을 확인한다**

IDA에서 `View → Open Subviews → Imports`를 열어 API 개수를 센다. 10개 미만이고 그나마 `LoadLibraryA`/`GetProcAddress`/`VirtualAlloc`/`VirtualProtect` 위주라면 패킹 스텁의 전형적인 패턴이다.

**3) 섹션 헤더를 확인한다**

IDA의 `View → Open Subviews → Segments`나 PE-bear의 Section Headers 탭에서 섹션 이름과 raw size/virtual size 차이를 본다. `UPX0`처럼 낯선 이름, 또는 raw size가 거의 0인데 virtual size만 큰 섹션이 있는지 확인한다.

**4) Detect It Easy로 패커 시그니처를 확인한다**

파일을 DIE에 드래그하면 상단에 "Packer: UPX(...)" 같은 결과가 바로 뜬다(REV-0225 참고). 시그니처가 안 잡혀도 하단 Entropy 탭에서 전체/섹션별 엔트로피를 확인한다(REV-0228 참고).

**5) entry point 코드를 눈으로 확인한다**

IDA View-A에서 시작 지점 코드를 본다. `PUSHAD`, 반복문, `VirtualAlloc`/`VirtualProtect` 호출 직후 알 수 없는 주소로 `JMP`하는 패턴이면 패킹 스텁일 가능성이 매우 높다.

**6) 결론을 내리고 다음 단계로 넘어간다**

위 징후 중 3개 이상이 겹치면 "패킹됨"으로 결론짓고, 패커 종류에 따라 다음 문서로 이동한다: UPX라면 REV-0225/REV-0226, 다른 패커거나 커스텀 패커라면 REV-0227(수동 언패킹 개념).

## 명령어/단축키
- `strings sample.exe | wc -l` : 문자열 줄 수 세기 (WSL/Linux/Git Bash)
- `strings sample.exe | less` : 문자열 목록 훑어보기
- IDA `Ctrl+P` : Functions window
- IDA `Shift+F12` : Strings window
- IDA `View → Open Subviews → Imports` : Import 목록
- IDA `View → Open Subviews → Segments` : 섹션 헤더 확인
- Detect It Easy: 파일을 창에 드래그 → 상단 결과란 확인, 우측 하단 "Entropy" 버튼 클릭

## 출력 해석
- `strings` 결과가 몇 줄뿐이고 대부분 알아볼 수 없는 조각이면 → 데이터가 압축/암호화되어 사람이 읽을 텍스트가 애초에 존재하지 않는다는 뜻.
- Imports 창에 `KERNEL32.dll`만 있고 `USER32.dll`, `msvcrt.dll` 등 원래 필요할 법한 라이브러리가 안 보이면 → 원본 import table이 아직 복원되지 않은 상태.
- 섹션 이름이 `UPX0`/`UPX1`이면 → 사실상 UPX로 확정(REV-0225로 이동).
- 섹션 이름이 `.aspack`, `.adata`, `.vmp0`, `.themida`, `.enigma1` 등이면 각각 ASPack, VMProtect, Themida, Enigma Protector라는 상용/전문 패커의 흔적이다. 이런 패커는 UPX처럼 간단히 `-d` 옵션으로 풀리지 않고, 수동 언패킹(REV-0227)이나 동적 분석이 필요하다.
- Detect It Easy가 "Nothing found"라고만 뜨고 아무 패커도 못 잡으면 → 알려지지 않은 커스텀 패커이거나, 컴파일러가 만든 정상 실행 파일일 수 있으니 엔트로피와 entry point 코드를 직접 눈으로 재확인한다.

## 흔한 실수
- 문자열이 적다는 이유 하나만으로 성급하게 "패킹됨"이라 단정하는 것. 원래 문자열이 적은 아주 작은 유틸리티 프로그램도 있으므로, 반드시 여러 징후를 함께 봐야 한다.
- Import가 적은 것을 보고 바로 포기하는 것. 정적 링크(static linking)된 바이너리도 import가 적게 보일 수 있으니 섹션 이름/엔트로피와 함께 판단해야 한다.
- DIE 같은 시그니처 기반 도구의 결과를 절대적으로 믿는 것. 시그니처 DB에 없는 최신/변형 패커는 "Unknown"으로 나올 수 있으므로 시그니처가 안 잡혀도 다른 징후를 계속 확인해야 한다.
- 패킹을 확인한 뒤 곧바로 언패킹 도구부터 실행하는 것. 어떤 패커인지 먼저 식별해야(REV-0225 등) 올바른 언패킹 방법을 고를 수 있다.
- entry point 코드를 안 보고 넘어가는 것. 섹션 이름만으로 판단하면 최신 패커가 섹션 이름을 표준처럼 위장한 경우 놓칠 수 있다.

## 막혔을 때 다음 체크
- 패커 시그니처가 안 잡히는데 여전히 의심스럽다면 → REV-0228(엔트로피)로 이동해 섹션별 수치를 직접 확인한다.
- Import가 이상하게 적다면 → REV-0229(Import가 거의 없는 PE)에서 원인을 더 자세히 파악한다.
- 패커가 UPX로 확인됐다면 → REV-0226(UPX 기본 언패킹)으로 바로 이동한다.
- UPX가 아닌 다른 패커이거나 시그니처가 안 잡히면 → REV-0227(수동 언패킹 개념)에서 OEP와 덤프 개념을 먼저 이해한다.
- entry point에서 `VirtualProtect` 호출 후 자기 자신을 덮어쓰는 듯한 루프가 보인다면 → REV-0230(Self-modifying Code 기초)도 함께 참고한다.

## 미니 예제
`challenge.exe`(320KB)를 IDA에 열었더니 다음과 같았다고 하자.

```text
- Functions window: 함수 3개(sub_401000, sub401020, start)만 존재
- Strings window: "UPX!" 문자열 하나만 보임
- Imports: LoadLibraryA, GetProcAddress, ExitProcess 3개뿐
- Segments: UPX0 (raw size 0, virtual size 0x40000), UPX1 (raw size 0x28000)
- entry point 코드: PUSHAD → 큰 루프 → POPAD → JMP 알 수 없는 주소
```

문자열 "UPX!"와 `UPX0`/`UPX1` 섹션 이름만으로도 이미 UPX 패킹이 거의 확정적이다. 이럴 때는 REV-0225로 넘어가 `upx -V`, `strings`로 매직 바이트를 한 번 더 확인하고, REV-0226에서 설명하는 `upx -d challenge.exe` 명령으로 바로 언패킹을 시도하면 된다.

## 관련 글
- REV-0001 — 리버싱 문제 파일을 받았을 때 30초 트리아지
- REV-0225 — UPX인지 확인하는 법
- REV-0226 — UPX 기본 언패킹
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- REV-0228 — Entropy가 높은 Section의 의미
- REV-0229 — Import가 거의 없는 PE를 봤을 때
- ../windows-pe/rev-0126-die-basics.md — Detect It Easy 기본 사용법
- ../triage/rev-0009-finding-main.md — main 함수가 안 보일 때 찾는 방법
- ../triage/rev-0010-stripped-entry-point.md — stripped 바이너리에서 시작점 잡는 방법

## 출처/검증
- 패킹 스텁의 일반적인 동작(PUSHAD/POPAD, VirtualAlloc/VirtualProtect 사용, 섹션 raw/virtual size 불일치)은 UPX 및 여러 상용 패커(ASPack, Themida, VMProtect)의 공개된 동작 방식과 다수의 리버싱 교육 자료에서 공통적으로 설명하는 내용을 바탕으로 정리했다(2026-09-08 검증).
- Detect It Easy의 시그니처 기반 패커 탐지 방식은 프로젝트 공식 저장소(github.com/horsicq/Detect-It-Easy) 설명을 참고했다.
- 실제 파일에 대한 판단은 여러 징후를 종합해야 하며, 도구 버전에 따라 시그니처 인식 결과가 달라질 수 있으므로 최신 DIE 데이터베이스로 재검증하는 것을 권장한다.
