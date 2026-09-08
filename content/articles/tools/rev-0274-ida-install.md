---
id: REV-0274
title: "IDA 설치와 오프라인 준비"
slug: "rev-0274-ida-install"
category: "tools"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["IDA 설치", "IDA Free 다운로드", "IDA Pro 라이선스", "hex-rays.com", "My Hex-Rays", "ida.hexlic", "IDA 오프라인 설치", "IDAPython Python 설치"]
aliases: ["IDA 설치 방법", "IDA Free 설치", "IDA 다운로드 방법", "IDA 라이선스 파일"]
symptom_keywords: ["IDA 어디서 다운받음", "IDA 설치 파일이 없음", "경기장에 인터넷이 없는데 IDA 써야 함", "IDA 라이선스 파일 어디에 둠", "IDA Free랑 Pro 차이"]
source_ids: ["SRC-HEXRAYS-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
IDA는 반드시 공식 Hex-Rays 사이트(hex-rays.com, 다운로드는 My Hex-Rays 포털)에서만 받아야 하며, 대회장처럼 인터넷이 끊긴 PC에서 쓰려면 **인터넷이 되는 동안** 설치 파일과 라이선스 파일(`ida.hexlic`)을 미리 받아두고 USB로 옮겨서 오프라인으로 설치·활성화까지 마쳐 두는 것이 핵심이다.

## 언제 검색해야 하나
- 대회/CTF 전에 오프라인 PC에 IDA를 미리 깔아두고 싶을 때
- IDA Free와 IDA Pro/Home의 차이가 헷갈릴 때
- 설치는 했는데 라이선스 파일을 어디에 둬야 하는지 모를 때
- 인터넷이 없는 환경에서 IDA가 실행이 안 될까 봐 걱정될 때
- Python이 있어야 IDAPython이 되는지 궁금할 때

## 핵심 개념
IDA는 Hex-Rays라는 회사가 만드는 상용 디스어셈블러/디컴파일러다. 무료로 배포되는 버전과 유료 버전이 나뉘어 있고, 다운로드는 항상 로그인 기반의 **My Hex-Rays** 포털을 거친다.

### 제품 등급 차이
- **IDA Free** — 회원가입만 하면 누구나 무료로 받을 수 있는 가벼운 버전. x86/x64 아키텍처만 지원하고, 디컴파일러(F5, Pseudocode)가 포함되지 않으며(버전에 따라 제한 범위가 달라질 수 있다), 상업적 용도로는 쓸 수 없다는 라이선스 제약이 있다. CTF/학습 목적으로는 충분히 강력하지만, "F5로 C처럼 읽기"가 안 될 수 있다는 점은 미리 알아두어야 한다.
- **IDA Home** — 개인 구매자용 유료 라이선스. 상업적 이용은 여전히 제한되지만 더 많은 아키텍처와 디컴파일러를 포함하는 구성이 있다.
- **IDA Pro** — 가장 완전한 유료 버전. 다양한 CPU 아키텍처용 디컴파일러, 협업 기능, 상업적 이용 등을 지원하며 named license(컴퓨터/사용자 단위) 또는 floating license(라이선스 서버 대여 방식)로 제공된다.

어느 등급이든 다운로드와 라이선스 발급은 **my.hex-rays.com** 계정을 통해 이루어진다. 즉 "설치 파일만 있으면 끝"이 아니라, 그 설치 파일이 인식할 **라이선스 파일**이 한 쌍으로 필요하다.

### 오프라인으로 쓰기 위한 기본 원리
IDA 설치 프로그램(.exe) 자체는 평범한 Windows 인스톨러라서 인터넷 연결 없이도 설치를 진행할 수 있다. 문제가 되는 부분은 **라이선스 인증**이다. named license는 로컬 파일(`ida.hexlic`)을 이용해 오프라인으로도 실행 가능하도록 설계되어 있지만, floating license는 라이선스 서버에 네트워크로 접속해서 라이선스를 "대여(borrow)"하는 방식이라 서버 접근이 아예 불가능한 폐쇄망에서는 사용이 까다롭다. 따라서 대회용 PC처럼 완전히 오프라인인 환경에는 **named license(개인용 고정 라이선스) + 로컬 `ida.hexlic` 파일** 조합이 훨씬 적합하다.

## 화면/코드에서 보이는 징후
- My Hex-Rays 포털 로그인 후 "Download Center"에 Windows/Linux/macOS용 설치 파일 목록이 보인다.
- 같은 포털의 라이선스 관리 화면에서 `.hexlic` 확장자의 라이선스 파일을 내려받을 수 있다.
- 설치 후 첫 실행 시 "License Manager" 팝업이 뜨며 라이선스 파일 경로를 요구한다.
- 라이선스 파일 경로를 지정하지 못하면 IDA가 демо/제한 모드로 뜨거나 실행 자체가 거부된다.

## 가장 먼저 할 것
아직 인터넷이 되는 PC에서 먼저 **my.hex-rays.com 계정을 만들고(IDA Free도 가입 필요)**, 사용할 제품 등급(Free/Home/Pro)에 맞는 Windows 설치 파일과 라이선스 파일(`ida.hexlic`)을 함께 내려받는다. 이 둘을 같은 폴더(예: `offline-kit/installers/ida/`)에 모아두고 USB로 옮길 준비를 한다.

## 단계별 절차

**1) 온라인 상태에서 계정·다운로드 준비**

my.hex-rays.com에 로그인 → Download Center에서 원하는 IDA 버전의 **Windows installer**(.exe)를 내려받는다. 같은 포털의 License 메뉴에서 본인 라이선스에 해당하는 `ida.hexlic` 파일도 함께 내려받는다. IDA Free는 별도의 무료 다운로드 페이지/버튼으로 안내되며, 가입은 필요하지만 결제는 없다.

**2) IDAPython을 쓸 계획이면 Python도 같이 준비**

IDA는 Python 3가 설치되어 있으면 IDAPython을 자동으로 연동한다. 오프라인 PC에 Python이 없다면, python.org에서 Windows용 설치 파일(예: `python-3.x.x-amd64.exe`)을 같이 내려받아 둔다. 이미 Python이 설치돼 있다면 이 단계는 건너뛰어도 된다.

**3) USB/외장 SSD로 파일 옮기기**

`ida_installer.exe`, `ida.hexlic`, (필요 시) Python 설치 파일을 하나의 폴더에 모아 USB나 외장 SSD에 복사한다. `offline-kit/installers/ida/` 같은 이름으로 정리해 두면 나중에 재설치할 때도 헷갈리지 않는다.

**4) 오프라인 PC에서 설치**

대상 PC(인터넷이 없어도 됨)에서 `ida_installer.exe`를 더블클릭하고 마법사를 따라간다. 라이선스 동의 → 설치 경로 선택 → 설치 진행까지는 완전히 로컬에서 끝나는 작업이라 네트워크가 없어도 문제없다.

**5) 라이선스 파일 배치**

설치가 끝나면 `ida.hexlic` 파일을 IDA 설치 폴더(예: `C:\Program Files\IDA Pro 9.x\`) 또는 `%APPDATA%\Hex-Rays\IDA Pro\` 경로에 복사해 둔다. 두 위치 중 아무 곳이나 IDA가 인식하는 표준 경로이므로 하나만 선택해도 된다.

**6) 첫 실행과 활성화 확인**

IDA를 실행하면 License Manager 창이 뜬다. named license라면 앞서 복사해 둔 `ida.hexlic` 경로를 지정(또는 자동 인식)하면 활성화된다. **이 첫 활성화 절차는 라이선스 종류에 따라 최초 1회 인터넷 접속을 요구할 수 있으므로, 반드시 인터넷이 되는 상태에서 먼저 한 번 실행해서 정상적으로 열리는지 확인**해야 한다. 확인이 끝나면 이후에는 네트워크 없이도 같은 라이선스 파일로 계속 실행할 수 있다.

**7) 오프라인 동작 실제 검증**

가능하다면 설치 PC의 네트워크를 물리적으로 끊거나 비행기 모드로 전환한 뒤 IDA를 다시 실행해서, 라이선스 오류 없이 정상적으로 뜨는지 반드시 검증한다. 이 검증을 대회 전에 미리 해 두면 현장에서 "라이선스 서버에 연결할 수 없습니다" 같은 팝업 때문에 당황하는 상황을 피할 수 있다.

**8) 자동 업데이트 확인 끄기**

`Help → Check for free update` 또는 시작 시 업데이트 확인 옵션이 켜져 있으면 인터넷이 없는 환경에서 불필요한 지연이나 오류 메시지가 뜰 수 있다. 옵션에서 자동 업데이트 확인을 꺼두면 완전히 오프라인으로 조용히 실행된다.

## 명령어/단축키
- `File → Open...` : 설치 후 바이너리를 여는 기본 진입점(REV-0142 참고)
- `Help → About` : 현재 설치된 IDA 버전/빌드 확인
- `Help → Check for free update` : 업데이트 확인(오프라인이면 꺼두는 것을 권장)
- 라이선스 파일 배치 경로: 설치 폴더 루트 또는 `%APPDATA%\Hex-Rays\IDA Pro\`

## 출력 해석
- License Manager 창에서 라이선스 파일 경로를 정상 인식하면 곧바로 메인 화면(시작 화면)으로 넘어간다.
- "License file not found" 또는 "Unable to validate license" 메시지가 뜨면 `.hexlic` 파일이 인식 경로에 없거나, 만료/다른 컴퓨터 바인딩된 라이선스일 가능성이 높다.
- floating license 설정에서 서버 호스트를 지정했는데 오프라인 상태면 라이선스 대여(borrow) 자체가 실패한다 — 이 경우 named license로 바꾸거나, 최소 대회 시작 전 온라인 상태에서 필요한 기간만큼 라이선스를 미리 "빌려(borrow)" 두는 기능이 있는지 자신의 라이선스 유형에서 확인해야 한다.

## 흔한 실수
- 설치 파일만 내려받고 라이선스 파일(`ida.hexlic`)은 깜빡해서, 오프라인 현장에서 라이선스를 발급받으려다 인터넷이 없어 막히는 경우.
- IDA Free를 받아놓고 F5(디컴파일)가 안 된다고 당황하는 경우 — 등급별 기능 차이를 미리 확인하지 않은 탓이다.
- floating license로 설치해 놓고 완전 폐쇄망에서 실행하려다 서버 연결 실패로 아예 켜지지 않는 경우.
- 설치 프로그램과 라이선스 파일의 "버전"이 안 맞는 경우 — 라이선스는 특정 메이저 버전 범위에 한정될 수 있으므로, 다운로드 센터에서 라이선스가 커버하는 버전의 설치 파일을 받아야 한다.
- 오프라인 검증(4단계~7단계)을 대회 전에 안 해보고 당일 처음 켜보는 경우 — 반드시 미리 네트워크를 끊고 한 번 실행해서 확인해야 한다.

## 막혔을 때 다음 체크
- 설치는 됐는데 첫 실행 방법 자체가 궁금하면 → REV-0142(IDA에 바이너리 처음 열었을 때 해야 할 것)를 참고한다.
- 단축키를 빠르게 훑고 싶다면 → REV-0275(IDA 핵심 단축키 치트시트)를 참고한다.
- 설치 후 실제로 크랙미를 하나 풀어보며 손에 익히고 싶다면 → REV-0276(IDA 10분 실전 워크플로)을 참고한다.
- 라이선스 문제가 계속 안 풀리면 → 대회 주최 측/Hex-Rays 고객지원에 사전 문의하는 것이 가장 확실하다(현장에서 처음 겪으면 시간이 크게 낭비된다).

## 미니 예제
대회 3일 전, 인터넷이 되는 개인 PC에서 오프라인 대회용 PC로 IDA를 옮기는 흐름을 요약하면 다음과 같다.

```text
[인터넷 되는 PC]
1. my.hex-rays.com 로그인 (IDA Free도 가입 필요)
2. Download Center → ida_installer.exe 다운로드
3. License 메뉴 → ida.hexlic 다운로드
4. (필요 시) python.org → python-3.x.x-amd64.exe 다운로드
5. 위 3개 파일을 offline-kit/installers/ida/ 폴더에 모음
6. USB로 복사

[대회용 오프라인 PC]
7. USB에서 ida_installer.exe 실행 → 설치 완료
8. ida.hexlic을 설치 폴더 또는 %APPDATA%\Hex-Rays\IDA Pro\ 에 복사
9. IDA 실행 → License Manager에서 정상 인식 확인
10. (권장) 네트워크를 완전히 끊고 다시 실행해 오프라인 동작 재확인
11. Help → Check for free update 옵션 끄기
```

## 관련 글
- REV-0142 — IDA에 바이너리 처음 열었을 때 해야 할 것
- REV-0275 — IDA 핵심 단축키 치트시트
- REV-0276 — IDA 10분 실전 워크플로

## 출처/검증
- 제품 등급(Free/Home/Pro), 다운로드 경로(My Hex-Rays 포털), 설치 절차, 라이선스 파일(`ida.hexlic`) 배치와 License Manager 동작은 Hex-Rays 공식 문서(docs.hex-rays.com/getting-started/install-ida) 및 hex-rays.com 제품 페이지를 기준으로 정리했다(2026-09-08 검증).
- named license의 최초 활성화가 정확히 어떤 조건에서 인터넷 접속을 요구하는지, 그리고 완전 오프라인 상태에서 재실행이 항상 문제없이 되는지는 라이선스 종류/버전에 따라 달라질 수 있어 공식 문서만으로 100% 확정하기 어렵다. 실제 대회 전에 반드시 오프라인 상태로 재실행 테스트를 해서 재검증할 것을 강력히 권장한다.
- IDA Free의 정확한 기능 제한 범위(디컴파일러 포함 여부 등)는 버전마다 바뀌어 왔으므로, 설치 시점의 공식 제품 비교표를 다시 확인하는 것이 안전하다.
