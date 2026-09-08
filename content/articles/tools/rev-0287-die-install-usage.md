---
id: REV-0287
title: "Detect It Easy 설치와 사용법"
slug: "rev-0287-die-install-usage"
category: "tools"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [DIE]
keywords: ["detect it easy", "die 설치", "die 사용법", "packer detector", "die scan", "컴파일러 탐지", "패커 탐지", "horsicq"]
aliases: ["DIE", "디텍트 잇 이지", "패커 탐지 도구", "파일 시그니처 스캐너"]
symptom_keywords: ["이 바이너리가 어떤 언어로 컴파일됐는지 모름", "패킹됐는지 확인하는법", "UPX인지 확인하는법", "die 스캔 결과 해석 못함", "die 설치 방법 모름"]
source_ids: ["SRC-DIE-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Detect It Easy(DIE)는 실행 파일을 열자마자 컴파일러, 언어, 링커, 패커(UPX 등), 프로텍터를 시그니처 기반으로 즉시 알려주는 무료 오프라인 도구로, "이 바이너리부터 뭘 해야 하나"를 결정하는 리버싱의 첫 단추 역할을 한다.

## 언제 검색해야 하나
- 처음 보는 바이너리를 받았는데 IDA/Ghidra를 열기 전에 "이게 C인지 C++인지 .NET인지 Go인지"부터 알고 싶을 때
- 문자열이 거의 안 보이고 섹션 이름이 이상해서 패킹(UPX 등)됐는지 의심될 때
- 정적 분석 도구에서 함수가 거의 안 잡히는 이유가 프로텍터/난독화 때문인지 확인하고 싶을 때
- 대회 PC에 인터넷 없이 DIE를 설치해서 쓰고 싶을 때
- DIE 스캔 결과에 나온 용어(예: "Compiler: Microsoft Visual C/C++", "Packer: UPX")를 해석하지 못할 때

## 핵심 개념

### DIE는 무엇을 위한 도구인가
DIE는 파일의 바이트 패턴(시그니처)과 구조적 특징을 분석해서 "이 파일이 어떤 컴파일러/링커로 만들어졌는지", "패킹/난독화가 적용됐는지"를 자동으로 판별해주는 파일 식별 도구다. `file` 명령어의 훨씬 정교한 버전이라고 생각하면 된다. Windows/Linux/macOS 실행 파일(PE, ELF, Mach-O)을 모두 지원하며, CTF에서는 보통 IDA나 Ghidra로 정적 분석을 시작하기 **직전**에 가장 먼저 실행해서 "언팩이 필요한지, 어떤 언어 런타임의 관용구를 예상해야 하는지"를 결정하는 데 쓴다.

### 시그니처 기반 탐지의 한계도 알아야 한다
DIE는 알려진 패턴(시그니처) 데이터베이스와 대조해서 판정하므로, 아주 최신 컴파일러 버전이나 커스텀 패커는 "Unknown"으로 나올 수 있다. 이때는 결과를 100% 믿기보다 "패킹 의심 신호(엔트로피 높음, 섹션 이름 이상, import 개수 적음)"를 참고 정보로 활용한다. DIE 안에는 자체적으로 시그니처를 확장할 수 있는 스크립팅 기능(DIE-JS)도 있어서, 필요하면 직접 탐지 규칙을 추가할 수도 있다.

### 공식 배포 구조: 소스 저장소와 릴리스 저장소가 분리되어 있다
DIE 프로젝트는 개발자 `horsicq`가 관리하며, 소스 코드는 `horsicq/Detect-It-Easy` 저장소에 있지만 실제 컴파일된 배포 파일(Windows 설치 파일, Linux AppImage, `.deb` 등)은 `horsicq/DIE-engine` 저장소의 Releases 페이지에서 받는다. 이 구조를 모르면 "소스 저장소에는 왜 다운로드할 게 없지"라고 헷갈릴 수 있다.

## 화면/코드에서 보이는 징후
- 패킹된 바이너리를 IDA/Ghidra로 열었는데 함수가 거의 안 잡히고 진입점 근처 코드가 알 수 없는 루프(압축 해제 루틴)로 보일 때
- `strings` 결과에 정상적인 텍스트가 거의 없고 의미 없는 바이트 나열만 보일 때
- PE의 섹션 이름이 `.text`, `.data`처럼 표준이 아니라 `UPX0`, `UPX1`처럼 낯선 이름일 때 (UPX 패킹의 전형적 흔적)
- ELF인데 심볼이 거의 없고 `readelf -d`로 본 동적 섹션이 이상하게 짧을 때

## 가장 먼저 할 것
바이너리를 받으면 IDA/Ghidra를 열기 전에 DIE부터 실행해서 파일을 드래그&드롭한다. 상단의 결과 한 줄(예: `PE64 / Microsoft Visual C/C++(...)` 또는 `Packer: UPX(3.96)[...]`)을 가장 먼저 확인한다. 패커가 감지되면 언팩(UPX는 `upx -d`로 대부분 해결)부터 하고 그다음 정적 분석 도구를 연다.

## 단계별 절차

**1) 공식 다운로드 (인터넷 되는 곳에서, 한 번만)**
- 배포 파일은 `https://github.com/horsicq/DIE-engine/releases`에서 받는다
- Windows: 압축 파일(zip) 형태의 포터블 배포판, 설치 없이 압축만 풀면 실행 가능
- Linux: `Detect_It_Easy-<버전>-x86_64.AppImage`(포터블) 또는 Debian/Ubuntu/Kali용 `.deb` 패키지 중 자신의 배포판에 맞는 것 선택

**2) 오프라인 반입**
- Windows 포터블 zip 또는 Linux AppImage/`.deb`를 USB에 담아 대회 PC로 옮긴다
- AppImage는 실행 권한만 주면 별도 설치 없이 바로 실행된다: `chmod +x Detect_It_Easy-*.AppImage && ./Detect_It_Easy-*.AppImage`
- `.deb`는 `sudo dpkg -i die_*.deb`로 오프라인 설치

**3) 첫 실행**
- 실행 파일(Windows: `die.exe`, Linux: AppImage 또는 `die` 바이너리)을 더블클릭하면 GUI가 뜬다
- 상단에 "..." 버튼 또는 파일 열기 아이콘으로 대상 바이너리를 선택하거나, 창에 파일을 그대로 드래그&드롭한다

**4) 스캔 결과 확인**
- 상단 텍스트 박스에 판정 결과 한 줄이 표시된다 (예: `PE32 / GUI / Microsoft Visual C/C++(19.29.30146)[-]`)
- 하단 탭에서 더 상세한 정보(Import, Export, 섹션, 리소스, 해시)를 확인할 수 있다

**5) 딥 스캔 (필요할 때)**
- 기본 스캔에서 결과가 애매하면 "Deep scan" 옵션을 켜서 더 오래 걸리더라도 정밀 탐지를 시도한다

## 명령어/단축키
| 목적 | 조작 |
|---|---|
| 파일 열기 | 상단 툴바 "..." 버튼 또는 드래그&드롭 |
| 딥 스캔 | 옵션에서 "Deep scan" 체크 |
| 해시 확인 | 하단 탭 중 Hash 탭 (MD5/SHA1/SHA256) |
| 엔트로피 확인 | 하단 탭 중 Entropy 또는 우클릭 메뉴 |
| 익스포트 결과 | 결과를 텍스트로 복사(Ctrl+C 가능한 영역) |
| 콘솔(CLI) 버전 | GUI 대신 커맨드라인 `diec`(엔진 콘솔 버전) 실행 가능 |

## 출력 해석
- `PE32` / `PE64`: 32비트/64비트 Windows 실행 파일이라는 뜻
- `Microsoft Visual C/C++(19.29...)`: 컴파일러와 버전 — MSVC로 빌드된 네이티브 바이너리
- `.NET(...)`이 보이면 네이티브 코드가 아니라 C#/VB.NET 어셈블리이므로 IDA보다 dnSpyEx/ILSpy가 우선
- `Packer: UPX(3.96)[NRV,brute]`: UPX로 패킹됐다는 뜻이며 괄호 안은 UPX 버전/압축 방식 — `upx -d 파일` 로 대부분 복원 가능
- `Protector:`로 시작하면 단순 압축이 아니라 안티디버깅/난독화가 포함된 상용 프로텍터일 수 있어 언팩이 훨씬 어려움
- 결과가 `Unknown`이면 시그니처 DB에 없는 케이스 — 엔트로피와 섹션 구조를 직접 눈으로 확인해야 함

## 흔한 실수
- DIE 결과의 "Unknown"을 "패킹 안 됨"으로 오해하는 경우 — Unknown은 판정 실패일 뿐 패킹 여부와 무관
- 컴파일러 판정 결과만 보고 언어까지 확정 짓는 경우 (`Microsoft Visual C/C++`가 나와도 C인지 C++인지는 별도로 문자열/심볼로 확인 필요)
- UPX로 감지됐는데 그냥 IDA에서 억지로 분석하려는 경우 — 먼저 `upx -d`로 언팩해야 함수가 정상적으로 보임
- Deep scan을 켜지 않고 애매한 결과를 그대로 신뢰하는 경우

## 막혔을 때 다음 체크
1. Deep scan 옵션을 켜서 재스캔
2. 하단 Hex/Entropy 탭에서 실제 바이트 분포를 눈으로 확인(엔트로피가 7.5 이상이면 압축/암호화 의심)
3. `file`, `readelf -h`(ELF) 또는 PE-bear(REV-0288)로 헤더를 교차 확인
4. 패커가 감지됐다면 해당 패커 전용 언패커(UPX는 `upx -d`)부터 시도
5. 그래도 판정이 안 되면 섹션 이름과 import 개수를 직접 눈으로 보고 수동 판단

## 미니 예제
```text
파일: chall.exe (드래그&드롭)
결과: PE32(+) / GUI / Microsoft Visual C/C++(19.38.33135)[LTCG]
→ 패킹 없음, 최신 MSVC로 빌드된 64비트 GUI 프로그램
→ 바로 IDA/Ghidra로 정적 분석 시작 가능
```
```text
파일: packed.exe (드래그&드롭)
결과: PE32 / GUI / UPX(3.96)[NRV,brute]
→ UPX 패킹 확인
→ upx -d packed.exe 로 언팩 후 다시 분석
```

## 관련 글
- REV-0288 — PE-bear 설치와 사용법
- REV-0289 — ImHex 설치와 기본 사용법
- REV-0126 — Detect It Easy로 컴파일러 패커 확인
- REV-0297 — UPX 설치와 명령어

## 출처/검증
- 공식 저장소 `horsicq/Detect-It-Easy`(소스)와 `horsicq/DIE-engine`(릴리스) GitHub 페이지를 기준으로 배포 구조와 기능을 확인했다.
- 최종 확인일: 2026-09-08
