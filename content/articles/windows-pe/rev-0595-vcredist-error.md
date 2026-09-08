---
id: REV-0595
title: "Visual C++ 재배포 패키지 오류로 실행이 안 될 때"
slug: "rev-0595-vcredist-error"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, "Process Monitor"]
keywords: ["vc_redist", "MSVCP140.dll", "VCRUNTIME140.dll", "ucrtbase.dll", "0xc000007b", "Visual C++ Redistributable", "정적 링크 /MT"]
aliases: ["msvcp140.dll이 없다는 오류", "vcruntime140 오류", "0xc000007b 오류", "재배포 패키지 설치 오류"]
symptom_keywords: ["프로그램을 시작할 수 없습니다 msvcp140.dll", "0xc000007b 오류로 실행이 안된다", "vc_redist 설치할 때 0x80070643 오류가 난다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
실행 시 "The program can't start because MSVCP140.dll is missing from your computer."나 "The application was unable to start correctly (0xc000007b)."가 뜬다면 대부분 **대상 프로그램이 동적 링크한 Visual C++ 런타임(vcruntime140.dll, msvcp140.dll, ucrtbase.dll 등)이 시스템에 없거나 아키텍처(x86/x64)가 안 맞는 것**이 원인이며, 해결책은 Microsoft 공식 Visual C++ Redistributable을 프로그램과 같은 아키텍처로 설치하는 것이다.

## 언제 검색해야 하나
- 실행 파일을 더블클릭하면 `msvcp140.dll`, `vcruntime140.dll`, `vcruntime140_1.dll`, `msvcr120.dll` 등 이름에 숫자가 붙은 DLL이 없다는 오류가 뜰 때
- `0xc000007b` 오류 코드와 함께 "The application was unable to start correctly"가 뜰 때
- Visual C++ Redistributable 설치 프로그램 자체를 실행했는데 `0x80070643` 같은 설치 오류가 날 때
- CTF 문제 배포 파일을 여러 사람이 나눠 실행했는데 유독 특정 PC에서만 DLL 오류가 날 때

## 핵심 개념
Visual Studio로 C/C++ 프로그램을 빌드할 때 기본 설정(`/MD`, 동적 링크)을 쓰면, 표준 라이브러리 함수들의 실제 구현은 실행 파일 안에 포함되지 않고 별도의 공용 런타임 DLL에 들어 있다. 대표적으로 다음과 같은 DLL들이 있다.

- **VS2015~2022 계열(통합 런타임)**: `vcruntime140.dll`(64비트 전용 함수는 `vcruntime140_1.dll`도 추가로 필요할 수 있음), `msvcp140.dll`(C++ 표준 라이브러리), `ucrtbase.dll`/`api-ms-win-crt-*.dll`(Universal CRT, C 표준 라이브러리 부분)
- **VS2013 이전(버전별 독립 런타임)**: `msvcr120.dll`(VS2013), `msvcr110.dll`(VS2012), `msvcr100.dll`(VS2010) 등 — 버전마다 이름과 파일이 완전히 다르며 서로 호환되지 않는다.

프로그램을 실행하는 PC에 해당 버전의 재배포 패키지(Redistributable)가 설치되어 있지 않으면, 이 DLL들이 시스템(System32/SysWOW64)에 없으므로 REV-0586에서 다룬 것과 같은 "DLL을 찾을 수 없다" 오류가 뜬다. 재배포 패키지는 각 버전/아키텍처별로 별도 설치 파일(`vc_redist.x86.exe`, `vc_redist.x64.exe` 등)로 배포되며, 최신 VS2015~2022용은 하위/상위 버전 간 어느 정도 호환되도록 통합되어 있지만 여전히 x86용과 x64용은 분리되어 있다.

`0xc000007b`(`STATUS_INVALID_IMAGE_FORMAT`)는 조금 다른 문제로, DLL 자체는 어딘가에서 발견됐지만 **아키텍처가 실행 파일과 안 맞는 경우**(32비트 exe가 64비트 DLL을 찾았거나 그 반대) 또는 필요한 의존성 DLL 체인 중 하나가 깨져서 로더가 이미지를 검증하는 단계에서 실패했을 때 뜨는 오류다.

## 화면/코드에서 보이는 징후
- "`<프로그램>.exe - System Error`" 창에 "The code execution cannot proceed because MSVCP140.dll was not found. Reinstalling the program may fix this problem." 문구
- "The program can't start because VCRUNTIME140.dll is missing from your computer. Try reinstalling the program to fix this problem." 문구(구버전 Windows 표현)
- "`<프로그램>.exe - Application Error`" 창에 "The application was unable to start correctly (0xc000007b). Click OK to close the application." 문구
- Visual C++ Redistributable 설치 프로그램 실행 시 "Error 0x80070643: Fatal error during installation" 팝업

## 가장 먼저 할 것
오류 메시지에 나온 DLL 이름을 보고 어느 VS 버전 계열인지 먼저 구분한다(`vcruntime140`/`msvcp140`이면 VS2015+ 통합 런타임, `msvcr1xx`이면 그 이전 개별 버전). 그다음 Microsoft 공식 다운로드 페이지에서 **프로그램과 같은 아키텍처**(x86 또는 x64)의 재배포 패키지를 받아 설치한다.

## 단계별 절차
**1) 필요한 재배포 패키지 버전/아키텍처 확정**
- 대상 exe가 32비트인지 64비트인지 PE-bear나 파일 속성으로 확인한다(`IMAGE_FILE_HEADER.Machine` 필드, REV-0596 참고).
- 오류 메시지의 DLL 이름으로 필요한 VS 버전 계열을 특정한다.

**2) Microsoft 공식 재배포 패키지 설치**
- `vc_redist.x86.exe`(32비트용) 또는 `vc_redist.x64.exe`(64비트용)를 Microsoft 공식 다운로드 페이지에서 받아 관리자 권한으로 실행한다. 오프라인 경쟁 환경이라면 이 설치 파일을 미리 `offline-kit/installers/`에 캐시해두고 쓰는 것을 권장한다.
- 32비트 프로그램이라도 64비트 Windows에서는 x86용 재배포 패키지가 별도로 필요하다(WOW64 하위 시스템용).

**3) 설치가 안 되거나 오류가 날 때(0x80070643 등)**
- 이미 설치된 손상된 버전이 있는지 `제어판 → 프로그램 및 기능`에서 "Microsoft Visual C++ 20xx Redistributable" 항목을 찾아 제거한 뒤 다시 설치한다.
- Windows Update가 최신 상태인지 확인한다. 시스템 구성 요소 손상이 원인일 때는 `sfc /scannow`(관리자 권한 명령 프롬프트)로 시스템 파일 검사를 먼저 시도해볼 수 있다.

**4) 설치 후에도 안 되면 Process Monitor로 재확인**
- REV-0586의 절차대로 Process Monitor로 어떤 DLL을 어느 경로에서 못 찾는지 다시 확인해, 설치된 재배포 패키지가 실제로 필요한 DLL을 제공하는지 교차 검증한다.

**5) CTF 문제를 직접 만드는 입장이라면**
- 배포용 바이너리는 컴파일러 옵션에서 **정적 링크**(`/MT` 또는 `/MTd`)로 빌드하면 VC++ 런타임이 exe 안에 통째로 포함되어, 참가자 PC에 재배포 패키지가 없어도 실행할 수 있다. 파일 크기는 커지지만 배포 신뢰성이 크게 올라간다.

## 명령어/단축키
```text
관리자 명령 프롬프트: sfc /scannow
설치 파일: vc_redist.x86.exe /install /quiet /norestart  (무인 설치 옵션)
Process Monitor: REV-0586 절차와 동일하게 NAME NOT FOUND 필터링
```

## 출력 해석
- 재배포 패키지 설치 후에도 같은 DLL 오류가 그대로면, 설치한 패키지의 아키텍처(x86/x64)가 실행 파일과 안 맞았을 가능성이 가장 크다.
- `0xc000007b`가 재배포 패키지 설치 후에도 계속되면 DLL 부재 문제가 아니라 exe 자체가 손상됐거나, 32/64비트가 섞인 의존성 체인 문제일 수 있으므로 REV-0596을 함께 확인한다.

## 흔한 실수
- x64용 재배포 패키지만 설치하고 32비트 프로그램을 실행해서 여전히 오류가 나는 것 — 64비트 Windows에서도 32비트 프로그램을 위한 x86용 패키지가 별도로 필요하다.
- 오류 메시지의 DLL 이름만 보고 인터넷에서 그 DLL 파일 하나만 따로 다운로드해 넣는 것 — 출처가 불분명한 DLL은 버전 불일치나 보안 위험이 있으므로 반드시 Microsoft 공식 재배포 패키지 전체를 설치한다.
- VS2013 이전 버전(`msvcr1xx.dll`)과 VS2015+ 통합 런타임(`vcruntime140.dll`)을 같은 것으로 착각해서 엉뚱한 재배포 패키지를 설치하는 것 — 프로그램이 어느 VS 버전으로 빌드됐는지에 따라 정확히 맞는 패키지를 설치해야 한다.

## 막혔을 때 다음 체크
- 재배포 패키지를 설치해도 여전히 DLL을 못 찾는다면 → REV-0586(DLL이 로드되지 않아 실행이 안 될 때)의 Process Monitor 절차로 정확한 실패 경로를 다시 확인한다.
- `0xc000007b`가 계속된다면 → REV-0596(32비트 바이너리를 64비트 도구로 열어서 이상해질 때)에서 아키텍처 불일치 여부를 확인한다.
- 애초에 이 프로그램이 어떤 컴파일러/런타임으로 빌드됐는지 궁금하면 → REV-0137(Visual C++ Runtime 함수가 많은 바이너리 정리법)을 참고한다.

## 미니 예제
어떤 CTF 문제 파일을 실행했더니 "`chall.exe - System Error`" 창에 "The code execution cannot proceed because VCRUNTIME140.dll was not found. Reinstalling the program may fix this problem."가 떴다고 하자. 파일 속성을 확인해보니 `chall.exe`는 64비트(`PE32+`)였다. Microsoft 공식 페이지에서 `vc_redist.x64.exe`를 받아 설치한 뒤 다시 실행하니 정상적으로 프로그램이 시작됐다. 만약 이 문제를 여러 명이 풀어야 하는 대회 환경이라면, 출제자가 애초에 `/MT` 옵션으로 정적 링크해 배포했다면 이런 오류 자체가 발생하지 않았을 것이다.

## 관련 글
- REV-0586 — DLL이 로드되지 않아 실행이 안 될 때(Missing DLL)
- REV-0596 — 32비트 바이너리를 64비트 도구로 열어서 이상해질 때
- REV-0137 — Visual C++ Runtime 함수가 많은 바이너리 정리법
- REV-0119 — Import Table에서 중요한 API 찾기

## 출처/검증
- Visual C++ Redistributable의 버전별 DLL 구성(`vcruntime140.dll`, `msvcp140.dll`, `ucrtbase.dll` 등)과 x86/x64 분리 배포 방식은 Microsoft Learn "Latest supported Visual C++ Redistributable downloads" 공식 문서 기준.
- `0xc000007b`(`STATUS_INVALID_IMAGE_FORMAT`) 오류가 아키텍처 불일치/의존성 체인 문제에서 흔히 발생한다는 점은 Microsoft 지원 문서 및 다수의 트러블슈팅 레퍼런스에서 공통적으로 확인된다.
- 오류 대화상자 문구는 Windows 버전에 따라 다를 수 있으므로 실습 시 실제 화면 문구를 우선한다(2026-09-08 기준 서술).
