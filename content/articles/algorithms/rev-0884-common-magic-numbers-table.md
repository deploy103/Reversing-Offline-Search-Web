---
id: REV-0884
title: "리버싱에서 자주 보는 매직넘버 모음표"
slug: "rev-0884-common-magic-numbers-table"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, HxD]
keywords: ["매직넘버", "MZ 헤더", "PE 시그니처", "ELF 매직", "0xDEADBEEF", "0xCAFEBABE", "0xCCCCCCCC", "0xCDCDCDCD", "파일 시그니처"]
aliases: ["파일 매직 넘버 표", "디버그 힙 패턴 값", "0xdeadbeef가 뭐임", "파일 시그니처 목록"]
symptom_keywords: ["파일 앞부분에 이상한 바이트가 있음", "0xcccccccc가 보임", "0xdeadbeef가 보임", "메모리에 규칙적인 패턴이 채워짐"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
파일 헤더나 메모리에서 특정 고정 바이트 패턴(`MZ`, `7F 45 4C 46`, `0xCCCCCCCC`, `0xDEADBEEF` 등)을 보면, 그 자체로 파일 형식이나 메모리 상태(초기화 안 됨/해제됨 등)를 즉시 알아낼 수 있다 — 이 문서는 리버싱 중 가장 자주 마주치는 매직넘버들을 한 번에 찾아볼 수 있도록 정리한 표다.

## 언제 검색해야 하나
- HxD/IDA로 파일을 열었는데 시작 부분의 바이트가 무슨 의미인지 모를 때
- 디버거에서 메모리를 봤는데 `CC CC CC CC`나 `CD CD CD CD`처럼 반복되는 패턴이 있어서 이게 의도적인 값인지 우연인지 헷갈릴 때
- 코드에 `0xDEADBEEF`, `0xCAFEBABE` 같은 눈에 띄는 16진수 상수가 하드코딩되어 있을 때
- 알 수 없는 바이너리 blob의 포맷을 시그니처만으로 빠르게 추측하고 싶을 때

## 핵심 개념

**실행 파일/아카이브 포맷 시그니처 (파일 맨 앞 몇 바이트)**
| 바이트 (hex) | ASCII | 의미 |
|---|---|---|
| `4D 5A` | `MZ` | DOS/PE 실행 파일(EXE) 헤더 시작 |
| `50 45 00 00` | `PE\0\0` | PE(Portable Executable) 헤더 시그니처(DOS 스텁 뒤에 위치) |
| `7F 45 4C 46` | `.ELF` | ELF(Executable and Linkable Format) 매직 |
| `50 4B 03 04` | `PK..` | ZIP 아카이브(및 ZIP 기반 포맷: JAR, APK, DOCX/XLSX/PPTX, APPX) |
| `1F 8B` | - | GZIP 압축 |
| `52 61 72 21` | `Rar!` | RAR 아카이브 |
| `37 7A BC AF 27 1C` | - | 7-Zip 아카이브 |
| `89 50 4E 47 0D 0A 1A 0A` | `.PNG....` | PNG 이미지 |
| `FF D8 FF` | - | JPEG 이미지 |
| `42 4D` | `BM` | BMP 이미지 |
| `25 50 44 46` | `%PDF` | PDF 문서 |
| `CA FE BA BE` | - | Java `.class` 파일(빅엔디안) 또는 Mach-O Fat/Universal Binary |
| `FE ED FA CE` / `FE ED FA CF` | - | Mach-O 32/64비트 실행 파일(macOS/iOS) |
| `55 50 58 21` | `UPX!` | UPX로 패킹된 실행 파일의 표식 |

**디버거/힙에서 보이는 "채움(fill) 패턴" 상수 — Windows 디버그 빌드 전용**
| 값 (hex) | 의미 |
|---|---|
| `0xCCCCCCCC` | MSVC 디버그 빌드에서 **초기화되지 않은 스택** 변수를 채우는 값(`0xCC`는 `INT3` 브레이크포인트 opcode이기도 함) |
| `0xCDCDCDCD` | MSVC 디버그 힙에서 **`malloc`/`new`로 갓 할당되어 아직 값이 안 채워진** 메모리 |
| `0xDDDDDDDD` | MSVC 디버그 힙에서 **`free`/`delete`로 이미 해제된** 메모리(use-after-free 탐지용) |
| `0xFEEEFEEE` | Windows 힙(HeapFree 이후)에서 해제된 블록을 채우는 값 |
| `0xABABABAB` | MSVC 디버그 힙에서 할당 블록 앞뒤의 **가드 바이트(버퍼 오버런 탐지용)** |
| `0xBAADF00D` | Windows `LocalAlloc(LMEM_FIXED)` 등으로 할당은 됐지만 **아직 초기화 안 된** 힙 메모리 |

**코드에 자주 하드코딩되는 "장난스러운" 상수 (플레이스홀더/테스트/매직값)**
| 값 (hex) | 흔히 쓰이는 맥락 |
|---|---|
| `0xDEADBEEF` | 범용 플레이스홀더/센티널 값. "여기 값이 있어야 하는데 없다"는 의도적 표식으로 자주 사용 |
| `0xDEADC0DE` | ARM 임베디드/부트로더에서 크래시 덤프 표식으로 자주 사용 |
| `0x8BADF00D` | iOS 크래시 리포트에서 "watchdog timeout"을 뜻하는 코드(Apple 고유 관례) |
| `0xFACEFEED` / `0xFEEDFACE` | 여러 시스템에서 매직 헤더/버전 표식으로 재사용(Mach-O와는 바이트 순서가 다름에 주의) |
| `0x0BADC0DE` | 마이크로소프트류 코드에서 오류/예외 표식으로 종종 등장 |

## 화면/코드에서 보이는 징후
```text
00000000: 4D 5A 90 00 03 00 00 00  MZ......   <- DOS 헤더
...
000000F0: 50 45 00 00 64 86 07 00  PE..d...   <- PE 시그니처(64 86h = IMAGE_FILE_MACHINE_AMD64)
```
```text
스택 덤프: CC CC CC CC CC CC CC CC   <- 아직 값이 대입되지 않은 지역변수
힙 덤프:   CD CD CD CD CD CD CD CD   <- malloc 직후, memset/초기화 이전
```

## 가장 먼저 할 것
분석 대상 파일을 HxD/IDA로 열어 첫 4~8바이트를 위 표와 대조한다. 파일 포맷을 먼저 확정하면 이후 어떤 파서/도구(PE-bear, readelf 등)를 써야 할지 바로 정해진다.

## 단계별 절차
**1) 파일 시작 바이트 확인** — `MZ`(PE), `\x7fELF`(ELF), `PK\x03\x04`(ZIP류) 중 어디에 해당하는지 확인.

**2) 서브 시그니처 확인** — PE라면 DOS 헤더의 `e_lfanew` 필드가 가리키는 오프셋에 `PE\0\0`이 있는지 재확인(`readelf`/`file` 명령으로도 빠르게 확인 가능).

**3) 메모리 채움 패턴이면 디버그 빌드임을 인지** — `0xCCCCCCCC`/`0xCDCDCDCD`/`0xDDDDDDDD` 계열이 보이면 릴리즈 최적화가 아니라 디버그 빌드 환경에서 실행 중이라는 뜻이므로, 실제 버그와 "디버그 채움 패턴"을 혼동하지 않도록 구분한다.

**4) 코드 내 장난스러운 상수는 그대로 검색 키워드로 활용** — `0xDEADBEEF`류는 종종 인터넷 검색만으로도 어떤 오픈소스 라이브러리/샘플 코드에서 왔는지 바로 찾아낼 수 있다.

**5) `file` 명령으로 교차 확인**
```bash
file challenge.bin
```
리눅스 `file` 유틸리티는 내부적으로 이런 매직넘버 데이터베이스(`/usr/share/file/magic`)를 갖고 있어 즉시 포맷을 알려준다.

## 명령어/단축키
- Linux: `file <파일>`, `xxd <파일> | head`, `readelf -h <파일>`
- IDA/Ghidra: 파일을 열 때 자동으로 포맷을 인식하지만, 헤더가 손상된 경우 HxD로 직접 매직바이트를 비교
- HxD: `Ctrl+G`(주소 이동)로 오프셋 0으로 이동해 첫 바이트 확인

## 출력 해석
- 파일 시그니처가 알려진 표와 정확히 일치하면 해당 포맷 전용 도구(PE-bear, readelf, `unzip -l` 등)로 넘어간다.
- 매직바이트가 표에 없는 낯선 값이면, 커스텀/난독화된 포맷이거나 헤더가 암호화·패킹되어 있을 가능성을 의심(REV-0652 공유 라이브러리 분석이나 패킹 탐지 관련 문서로 이동).
- 디버그 채움 패턴(`0xCCCCCCCC` 등)이 스택/힙에 남아 있다면, 그 위치의 변수가 실제로 한 번도 초기화되지 않고 사용됐다는 버그 신호일 수 있다.

## 흔한 실수
- `0xCCCCCCCC`를 프로그램이 의도적으로 넣은 값이라고 착각하는 것 — 대부분 MSVC 디버그 런타임이 자동으로 채우는 "미초기화 표식"이며 실제 버그가 아니라 디버그 빌드의 정상적인 동작이다.
- PE와 ELF 매직을 혼동해서 잘못된 파서 도구를 쓰는 것 — `4D 5A`(MZ)는 PE, `7F 45 4C 46`은 ELF로 완전히 다른 플랫폼이다.
- Mach-O 매직(`0xFEEDFACE`/`0xFEEDFACF`)과 임베디드 크래시 덤프 표식(`0xDEADC0DE`)처럼 비슷하게 생긴 "장난스러운 hex" 상수를 서로 혼동하는 것 — 반드시 문맥(어떤 플랫폼, 어떤 로그 근처인지)과 함께 판단해야 한다.
- 매직넘버 하나만 보고 포맷 전체를 확정하는 것 — 일부 CTF 문제는 매직바이트를 일부러 조작해 파서를 오작동시키므로, 매직 이후의 구조(헤더 필드, 크기)도 함께 검증해야 한다.

## 막혔을 때 다음 체크
- PE 헤더 구조(MZ/DOS 헤더) 자체를 더 깊이 파악해야 하면 → REV-0115 — DOS Header와 MZ 시그니처.
- ELF 헤더/섹션 구조가 궁금하면 → REV-0089 — ELF 헤더 읽는 법.
- 매직바이트가 표준과 다르게 조작된 것 같으면(의도적 난독화) → REV-0885 — 알고리즘 유형별 판별 체크리스트에서 전체 판별 절차부터 다시 밟기.

## 미니 예제
`file` 명령으로 다음 결과를 얻었다:
```text
$ file challenge
challenge: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked, ...
```
`ELF 64-bit`라는 문구는 파일 시작이 `7F 45 4C 46`(ELF 매직)이고 그다음 클래스 바이트가 `02`(ELFCLASS64)였다는 뜻이다. HxD로 직접 열어도 같은 바이트를 확인할 수 있다:
```text
00000000: 7F 45 4C 46 02 01 01 00  .ELF....
```
`02`(64비트), `01`(리틀엔디안), `01`(현재 ELF 버전)까지 표준 헤더 구조와 정확히 일치하는지 바로 눈으로 확인 가능하다.

## 관련 글
- REV-0115 — DOS Header와 MZ 시그니처
- REV-0089 — ELF 헤더 읽는 법
- REV-0885 — 알고리즘 유형별 판별 체크리스트
- REV-0876 — 해시 함수 매직 상수 빠른 참조(MD5/SHA1/SHA256 초기값)
- REV-0877 — CRC 다항식 상수 빠른 참조표

## 출처/검증
- PE(`MZ`/`PE\0\0`) 시그니처: Microsoft PE/COFF 공식 명세("Microsoft Portable Executable and Common Object File Format Specification") 기준 (2026-09-09 검증).
- ELF(`7F 45 4C 46`) 매직: System V ABI / ELF 명세("Executable and Linkable Format (ELF)") 기준.
- ZIP/GZIP/PNG/JPEG/PDF/Mach-O/Java class 파일 시그니처: 각 포맷의 공개 표준 문서 및 널리 알려진 파일 시그니처 데이터베이스(예: 리눅스 `file` 유틸리티의 magic 데이터베이스) 기준.
- MSVC 디버그 힙/스택 채움 패턴(`0xCCCCCCCC`, `0xCDCDCDCD`, `0xDDDDDDDD`, `0xABABABAB`, `0xFEEEFEEE`): Microsoft Learn 공식 문서("CRT Debug Heap Details") 기준 (2026-09-09 검증).
- `0xBAADF00D`(LocalAlloc 미초기화 표식), `0x8BADF00D`(iOS watchdog 크래시 코드): Microsoft 및 Apple의 공개 디버깅/크래시 리포트 문서에서 널리 알려진 관례 기준.
