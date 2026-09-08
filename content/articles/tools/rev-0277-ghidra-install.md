---
id: REV-0277
title: "Ghidra 설치와 오프라인 준비"
slug: "rev-0277-ghidra-install"
category: "tools"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra 설치", "ghidra-sre.org", "Ghidra 다운로드", "Ghidra JDK", "ghidraRun", "Ghidra 오프라인", "Ghidra Java 요구사항", "Ghidra 압축 해제"]
aliases: ["Ghidra 설치 방법", "Ghidra 다운로드 방법", "Ghidra JDK 설치", "Ghidra 실행 안 됨"]
symptom_keywords: ["Ghidra 어디서 다운받음", "Ghidra 실행하니 자바 없다고 뜸", "Ghidra JDK 버전 안 맞음", "인터넷 없는 PC에 Ghidra 깔기", "Ghidra 설치 파일이 exe가 아님"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Ghidra는 미국 NSA가 만들어 무료·오픈소스(Apache License 2.0)로 배포하는 도구로, 공식 사이트 ghidra-sre.org(실제 배포는 GitHub 릴리스)에서 zip 파일 하나를 받아 **압축만 풀면 설치가 끝나지만**, 실행하려면 해당 버전이 요구하는 특정 버전의 64비트 JDK가 별도로 필요하므로 이 JDK까지 미리 온라인에서 받아 오프라인 PC에 함께 준비해 둬야 한다.

## 언제 검색해야 하나
- Ghidra를 오프라인 대회용 PC에 미리 준비해두고 싶을 때
- Ghidra를 실행했더니 Java 관련 오류가 뜰 때
- Ghidra가 어떤 버전의 JDK를 요구하는지 헷갈릴 때
- "설치 프로그램(.exe)이 없는데 이게 맞나" 싶을 때
- Ghidra를 인터넷 없이 계속 써도 되는지 궁금할 때

## 핵심 개념
Ghidra는 IDA와 달리 **전통적인 설치 프로그램(installer)이 없다.** 배포되는 파일은 압축된 zip 하나뿐이고, 이를 원하는 위치에 풀어놓는 것 자체가 설치의 전부다. 공식 문서는 이를 "in-place extraction(제자리 압축 해제)"라고 표현한다.

### Ghidra와 Java의 관계
Ghidra 자체는 Java로 작성된 프로그램이라서, 실행하려면 시스템에 **호환되는 버전의 JDK(Java Development Kit)**가 있어야 한다. 여기서 중요한 함정이 있다.

- Ghidra가 요구하는 JDK 버전은 **릴리스마다 다르다.** 과거 버전은 JDK 11을, 이후 버전은 JDK 17을, 최신 계열은 JDK 21 이상을 요구하는 식으로 계속 올라왔다. 반드시 **자신이 받은 Ghidra 배포판의 릴리스 노트/설치 가이드**에서 요구 버전을 확인해야 하며, 오래된 블로그 글의 버전 번호를 그대로 믿으면 안 된다.
- Ghidra는 JDK를 **PATH 환경변수** 또는 **JAVA_HOME 환경변수**를 통해 찾는다. 둘 다 없거나 버전이 안 맞으면, 실행 시 Java 홈 디렉터리 경로를 직접 입력하라는 대화상자가 뜬다.
- 특정 JDK를 강제로 지정하고 싶다면 Ghidra 설치 폴더의 `support/launch.properties` 파일에서 `JAVA_HOME_OVERRIDE` 값을 설정할 수 있다.

### 오프라인으로 쓰기 위한 기본 원리
Ghidra 자체는 무료·오픈소스라 별도의 라이선스 인증이나 온라인 활성화가 필요 없다. 즉 **zip을 풀고 호환되는 JDK만 설치되어 있으면 완전히 오프라인으로 영구히 사용 가능**하다. Windows/Linux x86-64용 네이티브 바이너리(디컴파일러 등)는 배포판에 이미 빌드되어 포함되어 있으므로 추가로 인터넷에서 뭔가를 받아 빌드할 필요가 없다(단, macOS나 특수 아키텍처는 다를 수 있다). 문제는 딱 하나, **호환되는 JDK를 오프라인 PC에 어떻게 갖다 놓을 것인가**이다.

## 화면/코드에서 보이는 징후
- 공식 배포 파일 이름은 `ghidra_<버전>_<릴리스>_<날짜>.zip` 형태이며, GitHub 릴리스 페이지의 "Assets" 목록에서 찾을 수 있다("Source code" zip이 아니라 이 배포판 zip을 받아야 한다).
- 압축을 풀면 최상위에 `ghidraRun`(Linux/macOS용 스크립트), `ghidraRun.bat`(Windows용), `Ghidra`, `docs`, `Extensions`, `support` 등의 폴더/파일이 보인다.
- JDK가 없거나 버전이 안 맞는 상태에서 `ghidraRun.bat`을 실행하면 "Java home directory를 입력하라"는 대화상자나 콘솔 오류 메시지가 뜬다.

## 가장 먼저 할 것
아직 인터넷이 되는 PC에서 GitHub 릴리스 페이지(또는 ghidra-sre.org를 통해 연결되는 공식 배포처)에서 **최신 안정 버전의 zip 배포판**을 받고, 그 릴리스의 요구 JDK 버전을 확인한 뒤 Eclipse Temurin(Adoptium) 또는 Amazon Corretto 같은 신뢰할 수 있는 배포처에서 **정확히 그 버전, 64비트, Windows용 JDK 설치 파일(또는 zip)**을 함께 받아둔다.

## 단계별 절차

**1) 온라인 상태에서 Ghidra zip 다운로드**

ghidra-sre.org 또는 GitHub의 `NationalSecurityAgency/ghidra` 릴리스 페이지에서 최신(또는 대회에서 허용하는) 버전의 `ghidra_<version>_PUBLIC_<date>.zip`을 내려받는다. 압축 해제 전 zip 파일 자체의 SHA-256 체크섬이 릴리스 노트에 함께 게시되어 있으면 대조해서 무결성을 확인한다.

**2) 요구 JDK 버전 확인**

압축을 풀지 않고도, 같은 릴리스의 설치 가이드(zip 안의 `docs/InstallationGuide.html` 또는 GitHub의 `GhidraDocs/InstallationGuide.md`)에서 "권장 JDK 버전"을 확인한다. 문서마다 표기가 다를 수 있다는 점이 알려진 이슈이므로, README와 InstallationGuide 두 군데를 같이 확인하는 것이 안전하다.

**3) JDK 다운로드**

확인한 버전에 맞는 **64비트 Windows용 JDK**를 Eclipse Temurin(adoptium.net) 또는 Amazon Corretto에서 받는다. `.msi` 설치형이나 `.zip` 압축형 둘 다 있는데, 오프라인 PC에 관리자 권한 설치가 부담스럽다면 zip 압축형을 받아서 그냥 풀어놓는 방식이 더 간편하다.

**4) 파일 정리 및 이동**

`ghidra_<version>.zip`과 JDK 설치 파일/zip을 한 폴더(예: `offline-kit/installers/ghidra/`)에 모아 USB나 외장 SSD로 옮긴다.

**5) 오프라인 PC에서 JDK 먼저 준비**

JDK를 설치하거나(msi) 원하는 위치에 압축 해제한다(zip). 압축 해제 방식이라면 그 `bin` 폴더 경로를 기억해 둔다.

**6) Ghidra 압축 해제**

`ghidra_<version>.zip`을 원하는 폴더(예: `C:\tools\ghidra\`)에 통째로 압축 해제한다. 기존에 다른 버전이 설치되어 있던 폴더 위에 그대로 덮어쓰지 않도록 새 폴더를 쓴다.

**7) JAVA_HOME 지정(필요한 경우)**

시스템 환경변수 `JAVA_HOME`을 3단계에서 준비한 JDK 경로로 설정하거나, PATH에 JDK의 `bin` 폴더를 추가한다. 환경변수를 건드리기 어려운 제한된 계정이라면, Ghidra 설치 폴더의 `support/launch.properties` 파일을 열어 `JAVA_HOME_OVERRIDE=<JDK 경로>` 항목을 채워 넣는 방법도 있다.

**8) 첫 실행**

Windows 탐색기에서 Ghidra 설치 폴더의 `ghidraRun.bat`을 더블클릭한다. 처음 실행 시 사용자 동의(라이선스, 통계 수집 여부 등)를 묻는 대화상자가 뜰 수 있으며, 통계/사용량 보고 관련 옵션이 있다면 오프라인 환경에서는 꺼두는 것이 안전하다.

**9) 오프라인 동작 검증**

가능하면 네트워크를 끊은 상태로 다시 `ghidraRun.bat`을 실행해서 정상적으로 메인 화면(프로젝트 창)이 뜨는지 확인한다. Ghidra는 온라인 라이선스 인증이 필요 없는 도구이므로 JDK만 제대로 잡혀 있으면 이 단계는 대개 문제없이 통과한다.

## 명령어/단축키
- `ghidraRun.bat` : Windows에서 Ghidra 실행(더블클릭 또는 명령 프롬프트에서 실행)
- `ghidraRun` : Linux/macOS에서 Ghidra 실행
- `support/launch.properties` 안의 `JAVA_HOME_OVERRIDE` : 특정 JDK 경로 강제 지정
- `File → Import File` : 실행 후 바이너리 불러오기(REV-0156, Ghidra Project Import 참고)

## 출력 해석
- 실행 직후 "A compatible JDK/JRE could not be found" 류의 메시지가 뜨면 JDK 버전이 안 맞거나 PATH/JAVA_HOME이 안 잡힌 것이다 — 요구 버전을 다시 확인하고 launch.properties 오버라이드를 시도한다.
- 콘솔 창이 잠깐 떴다가 아무 창도 안 뜨고 사라지면, 명령 프롬프트에서 직접 `ghidraRun.bat`을 실행해 에러 로그를 눈으로 확인하는 것이 원인 파악에 훨씬 빠르다.
- 정상 실행되면 "Ghidra Project" 창(프로젝트 생성/열기 화면)이 뜬다. 여기서부터는 REV-0156(Ghidra Project Import)을 참고한다.

## 흔한 실수
- 오래된 블로그 글만 보고 "JDK 11만 있으면 된다"고 믿었다가, 실제로 받은 최신 Ghidra 버전은 더 높은 JDK를 요구해서 실행이 안 되는 경우 — 반드시 자신이 받은 배포판의 문서를 확인해야 한다.
- GitHub 릴리스 페이지에서 실수로 "Source code (zip)"을 받는 경우 — 이건 소스 코드일 뿐 실행 가능한 배포판이 아니다. 반드시 `ghidra_<version>_PUBLIC_<date>.zip` 형태의 Assets 파일을 받아야 한다.
- 32비트 JDK를 받아버리는 경우 — Ghidra는 64비트 JDK를 요구한다.
- 이미 설치된 Ghidra 폴더 위에 새 버전 zip을 그대로 덮어써서 설정/확장 파일이 뒤섞이는 경우 — 새 버전은 새 폴더에 푸는 것이 안전하다.
- JDK와 Ghidra 둘 다 온라인에서 받아야 하는데 하나만 챙겨서 대회장에 가는 경우 — 이 문서의 체크리스트대로 둘 다 준비했는지 출발 전에 재확인한다.

## 막혔을 때 다음 체크
- Ghidra 실행은 됐는데 프로젝트를 어떻게 만들고 파일을 불러오는지 모르겠다면 → REV-0156(Ghidra Project Import)을 참고한다.
- 단축키를 빠르게 훑고 싶다면 → REV-0278(Ghidra 핵심 단축키 치트시트)을 참고한다.
- 실제로 크랙미를 하나 풀어보고 싶다면 → REV-0279(Ghidra 10분 실전 워크플로)를 참고한다.
- 자동 분석(Auto Analysis) 옵션이 헷갈리면 → REV-0157(Ghidra Auto Analysis)을 참고한다.
- 확장(Extension)을 오프라인으로 설치하고 싶다면 → GUI 설치 대신 확장 zip 파일을 Ghidra 설치 폴더의 `Ghidra/Extensions` 디렉터리에 직접 풀어 넣는 방법을 쓸 수 있다.

## 미니 예제
대회 전, Ghidra 12.x 계열을 오프라인 PC에 준비하는 흐름 예시:

```text
[인터넷 되는 PC]
1. GitHub NationalSecurityAgency/ghidra 릴리스 페이지 접속
2. ghidra_12.x_PUBLIC_20260818.zip (Assets) 다운로드
3. 같은 릴리스의 InstallationGuide에서 요구 JDK 버전 확인 (예: JDK 21)
4. adoptium.net 에서 Windows x64용 Temurin JDK 21 zip 다운로드
5. 두 zip을 offline-kit/installers/ghidra/ 폴더에 정리 → USB 복사

[대회용 오프라인 PC]
6. Temurin JDK zip을 C:\tools\jdk-21\ 에 압축 해제
7. ghidra_12.x.zip을 C:\tools\ghidra\ 에 압축 해제
8. C:\tools\ghidra\support\launch.properties 에서
   JAVA_HOME_OVERRIDE=C:\tools\jdk-21 설정
9. ghidraRun.bat 더블클릭 → 정상적으로 프로젝트 창 뜸 확인
10. 네트워크 끊고 재실행 → 동일하게 정상 동작 재확인
```

## 관련 글
- REV-0156 — Ghidra 프로젝트 생성과 바이너리 Import
- REV-0157 — Ghidra Auto Analysis 옵션
- REV-0278 — Ghidra 핵심 단축키 치트시트
- REV-0279 — Ghidra 10분 실전 워크플로

## 출처/검증
- Ghidra의 배포 방식(압축 해제만으로 설치 완료), JDK 탐색 방식(PATH/JAVA_HOME/launch.properties의 JAVA_HOME_OVERRIDE), 릴리스별 zip 배포 파일 이름 규칙, 실행 스크립트(`ghidraRun`/`ghidraRun.bat`)는 GitHub `NationalSecurityAgency/ghidra` 저장소의 공식 `GhidraDocs/GettingStarted.md`를 기준으로 정리했다(2026-09-08 검증).
- 요구 JDK 버전은 릴리스마다 계속 바뀌어 왔고, 심지어 같은 릴리스 안에서도 문서 간 표기가 엇갈렸던 사례가 공식 이슈 트래커에 보고된 바 있다. 이 문서에 등장하는 특정 JDK 버전 숫자는 예시일 뿐이며, 실제 설치 시점에는 반드시 자신이 받은 Ghidra 배포판에 동봉된 `docs/InstallationGuide.html`(또는 README)에서 정확한 요구 버전을 재확인해야 한다.
