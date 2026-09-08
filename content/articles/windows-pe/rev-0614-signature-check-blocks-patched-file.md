---
id: REV-0614
title: "서명 검증 때문에 수정한 파일이 실행이 안 될 때"
slug: "rev-0614-signature-check-blocks-patched-file"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", HxD]
keywords: ["Authenticode", "WinVerifyTrust", "IMAGE_DIRECTORY_ENTRY_SECURITY", "WIN_CERTIFICATE", "signtool", "CVE-2013-3900"]
aliases: ["서명 검증 실패", "패치 후 실행 안 됨", "디지털 서명 무효화", "Authenticode 서명 제거"]
symptom_keywords: ["패치했더니 실행이 안 된다", "디지털 서명이 유효하지 않다는 메시지가 뜬다", "이 앱은 실행할 수 없습니다 메시지가 뜬다", "SmartScreen이 막는다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
바이트를 수정한 파일이 실행되지 않거나 "게시자를 확인할 수 없습니다/디지털 서명이 유효하지 않습니다"라는 경고가 뜬다면 원본 파일이 Authenticode로 서명되어 있었고 그 서명이 파일 내용 전체의 해시를 담고 있어서 patch로 내용이 바뀌는 순간 검증이 깨진 것이므로, 실행이 막힌 원인을 서명 문제로 정확히 진단한 뒤 데이터 디렉터리에서 서명 자체를 제거하거나(리버싱/분석 목적) 아예 서명 검사를 강제하지 않는 방식(로컬 실행)으로 우회해야 한다.

## 언제 검색해야 하나
- HxD나 IDA로 EXE/DLL의 바이트를 직접 수정한 뒤 실행했더니 이전과 다른 이유로 실행이 안 될 때
- "Windows에서 PC를 보호했습니다"(SmartScreen), "이 파일의 게시자를 확인할 수 없습니다", "디지털 서명이 유효하지 않습니다" 같은 메시지가 뜰 때
- `signtool verify /pa /v file.exe` 실행 결과가 패치 전에는 성공했는데 패치 후에는 실패로 바뀌었을 때

## 핵심 개념
정상 배포되는 많은 Windows 실행 파일(특히 상용 소프트웨어, 드라이버, 일부 상용 게임/DRM이 걸린 프로그램)은 **Authenticode**라는 방식으로 디지털 서명되어 있다. 이 서명은 PE 파일의 데이터 디렉터리 중 인덱스 4번, `IMAGE_DIRECTORY_ENTRY_SECURITY`가 가리키는 위치에 `WIN_CERTIFICATE` 구조체 형태로 저장된다.

여기서 중요한 구조적 특징이 있다.

- `IMAGE_DIRECTORY_ENTRY_SECURITY`의 `VirtualAddress` 필드는 다른 데이터 디렉터리와 달리 **RVA가 아니라 파일 상의 실제 오프셋(raw file offset)**이다. 그리고 이 서명 블록은 보통 파일의 맨 끝, 마지막 섹션 뒤에 덧붙여진다(메모리에 매핑되는 섹션 영역이 아니라 파일에만 존재).
- 이 서명은 파일 내용(정확히는 서명 블록 자신을 제외한 나머지 전체, 그리고 PE 체크섬 필드 등 일부 예외 필드)에 대한 해시를 서명한 것이다. `WinVerifyTrust` API(`wintrust.dll`)가 이 서명을 검증할 때, 파일을 다시 해시해서 서명에 포함된 해시값과 일치하는지 확인한다.
- 파일의 코드/데이터를 단 1바이트라도 바꾸면 이 해시가 달라지므로, 서명 검증은 반드시 실패하게 된다. 이때 Windows는 그 실행 파일을 "서명되지 않은 파일"로 취급하거나, 정책에 따라 아예 실행을 차단할 수 있다(특히 커널 드라이버, 일부 서명 강제 정책이 걸린 환경, SmartScreen 평판 검사 등에서 두드러진다).

참고로 `CVE-2013-3900`이라는 잘 알려진 취약점은, `WIN_CERTIFICATE` 구조체 안에 서명 검증 범위를 벗어나는 여분의 데이터를 추가해도 기본 설정에서는 서명이 깨지지 않는다는 허점을 이용한 것이었다. 다만 이는 서명 블록 뒤에 데이터를 "추가"하는 특수한 경우에 한정되며, 코드/데이터 섹션 자체를 수정하는 일반적인 패치와는 다르다. 게다가 이 취약점의 엄격 검증 모드(`EnableCertPaddingCheck` 레지스트리 값)는 기본적으로 꺼져 있어 여전히 사용되는 환경이 있다는 점만 참고로 알아두면 된다.

## 화면/코드에서 보이는 징후
- 패치 전 파일에서는 우클릭 → 속성 → "디지털 서명" 탭에 서명 정보가 보이지만, 패치 후 같은 파일에서는 이 탭 자체가 사라지거나 "서명이 유효하지 않음"으로 표시됨
- 실행 시 UAC 대화상자의 "확인된 게시자" 문구가 패치 후에는 "알 수 없는 게시자"로 바뀜
- PE-bear/IDA로 데이터 디렉터리 목록을 보면 `Security`(`IMAGE_DIRECTORY_ENTRY_SECURITY`) 항목에 0이 아닌 `VirtualAddress`/`Size`가 있음
- `signtool verify /pa /v file.exe` 명령이 `SignTool Error: WinVerifyTrust returned an error` 류의 메시지와 함께 실패

## 가장 먼저 할 것
1. 지금 겪는 실행 실패가 정말로 서명 문제 때문인지부터 확정한다. 파일 속성의 "디지털 서명" 탭 유무, 또는 `signtool verify /pa /v file.exe`(Windows SDK에 포함) 결과로 확인한다.
2. PE-bear나 IDA로 데이터 디렉터리 중 `Security` 항목의 `VirtualAddress`/`Size`가 0이 아닌지 확인해, 원본 파일이 애초에 서명되어 있었는지 확인한다.
3. 분석/리버싱 목적이라면, 애초에 깨질 수밖에 없는 서명을 억지로 유지하려 하지 말고, 서명 정보 자체를 파일에서 깔끔히 제거하는 방향으로 접근한다.

## 단계별 절차
**1) 서명 유무와 검증 실패 확인**
- `signtool verify /pa /v file.exe`를 원본과 패치본 각각에 실행해 결과를 비교한다. 원본은 성공, 패치본은 실패라면 패치로 인한 해시 불일치가 원인임이 확정된다.

**2) 서명 정보를 파일에서 제거**
- PE 헤더의 데이터 디렉터리 배열에서 `IMAGE_DIRECTORY_ENTRY_SECURITY`(인덱스 4) 항목을 찾아 `VirtualAddress`와 `Size`를 모두 `0`으로 만든다. PE-bear의 헤더 편집 기능이나 헥스 에디터로 직접 이 두 필드를 0으로 덮어쓰면 된다.
- 파일 끝에 실제로 붙어 있던 `WIN_CERTIFICATE` 데이터 블록도 함께 잘라내면 파일 크기도 줄어들고 더 깔끔해진다(선택 사항이지만 권장).
- 이렇게 하면 Windows는 이 파일을 애초에 서명이 없는 파일로 인식하므로, "서명이 있었는데 깨졌다"는 경고 대신 일반적인 미서명 실행 파일로 취급되어 정상적으로(단, 미서명 파일에 대한 일반적인 SmartScreen 경고는 별개로 뜰 수 있다) 실행된다.

**3) PE 체크섬 재계산(필요한 경우)**
- 일부 로더/드라이버는 `IMAGE_OPTIONAL_HEADER.CheckSum` 필드도 함께 검증한다. PE-bear의 "Recalculate Checksum" 기능이나 유사 도구로 체크섬을 갱신해준다.

**4) 커널 드라이버 등 서명이 강제되는 경우**
- 커널 드라이버는 서명이 없으면 아예 로드가 거부되는 정책(드라이버 서명 강제)이 걸려 있을 수 있다. 이 경우는 서명 제거만으로 해결되지 않고, 테스트 서명 모드(`bcdedit /set testsigning on`)나 별도의 테스트 인증서로 재서명하는 절차가 필요하다. 이는 시스템 전역 설정을 바꾸는 작업이므로 신중히 접근해야 한다.

## 명령어/단축키
- `signtool verify /pa /v <file>` — Authenticode 서명 검증(Windows SDK 포함)
- PE-bear: 데이터 디렉터리 편집 화면에서 `Security` 항목의 `VirtualAddress`/`Size`를 0으로 수정, "Recalculate Checksum" 기능
- `bcdedit /set testsigning on` — 커널 드라이버 테스트 서명 허용(관리자 권한, 시스템 재부팅 필요)

## 출력 해석
- `signtool verify` 결과가 `Successfully verified`이면 서명이 유효한 것이고, `SignTool Error`나 `Number of errors: 1`류 메시지가 뜨면 검증 실패다.
- 파일 속성 창의 디지털 서명 탭 자체가 없다면(회색으로 비활성화가 아니라 탭이 아예 안 보이면) 이미 서명 정보가 파일에서 완전히 제거된 상태다.

## 흔한 실수
- 서명이 깨진 원인을 파악하지 않고 패치를 반복해서 시도하며 "왜 자꾸 실행이 안 되지"라고 헤매는 것. 먼저 서명 문제인지부터 확인해야 한다.
- 서명 데이터 블록만 파일 끝에서 잘라내고 데이터 디렉터리의 `VirtualAddress`/`Size` 필드는 그대로 남겨두는 것. 이러면 로더가 이제 존재하지 않는 위치를 서명 블록으로 착각해 오히려 더 이상한 오류가 날 수 있다. 두 가지를 함께 처리해야 한다.
- 정품 소프트웨어의 서명을 무력화해 배포/재배포하는 행위. 이 문서는 어디까지나 자신이 소유하거나 CTF/분석 목적으로 합법적으로 다루는 바이너리를 로컬에서 분석하기 위한 절차이며, 상용 소프트웨어의 라이선스 우회나 재배포 목적으로 사용해서는 안 된다.

## 막혔을 때 다음 체크
- 데이터 디렉터리 배열 자체의 구조가 헷갈린다면 → REV-0116(PE COFF Optional Header)을 확인한다.
- 서명을 제거했는데도 실행이 안 된다면 섹션 정렬/체크섬 문제일 수 있으므로 → REV-0117(PE Section Table)을 확인한다.
- 서명 대신 리소스에 숨겨진 다른 무결성 검사가 있는지 의심된다면 → REV-0141(Resource Section과 숨겨진 데이터 확인)을 확인한다.

## 미니 예제
`target.exe`를 HxD로 열어 문자열 하나를 다른 문자열로 덮어쓴 뒤 실행했더니 "Windows에서 이 앱이 PC를 손상시킬 수 있는지 확인할 수 없습니다"라는 SmartScreen 경고가 새로 나타났다. PE-bear로 데이터 디렉터리를 확인해보니 `Security` 항목에 `VirtualAddress = 0x00045000`, `Size = 0x2210`이 들어있었다. 이 두 값을 0으로 바꾸고, 파일 끝의 해당 오프셋부터 `0x2210`바이트를 잘라낸 뒤 체크섬을 재계산하자, 이제 이 파일은 "서명이 있었는데 깨진 파일"이 아니라 처음부터 서명이 없는 일반 실행 파일로 인식되어 이전과 동일하게 실행되었다(단, 미서명 파일 관련 일반적인 경고는 여전히 뜰 수 있다).

## 관련 글
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0117 — PE Section Table 읽기
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 출처/검증
- `IMAGE_DIRECTORY_ENTRY_SECURITY`가 RVA가 아닌 파일 오프셋을 가리키며 `WIN_CERTIFICATE` 구조체로 Authenticode 서명이 저장된다는 점, `WinVerifyTrust`가 파일 해시를 재계산해 서명과 비교한다는 점은 Microsoft PE/COFF 형식 공식 문서 및 Authenticode 관련 공개 기술 문서 기준이다.
- `CVE-2013-3900`(WinVerifyTrust 서명 패딩 검증 취약점)과 `EnableCertPaddingCheck` 레지스트리 값을 통한 엄격 검증 모드가 기본적으로 비활성화되어 있다는 점은 Microsoft 공식 권고(MS13-098) 및 관련 공개 문서 기준이다(2026-09-08 확인).
- `signtool verify` 사용법은 Windows SDK에 포함된 signtool 공식 문서 기준이다.
