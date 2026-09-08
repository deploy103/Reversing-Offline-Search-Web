---
id: REV-0002
title: "확장자를 믿으면 안 되는 이유와 실제 파일 형식 확인법"
slug: "rev-0002-dont-trust-extension"
category: "triage"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [file, "Detect It Easy", HxD, ImHex]
keywords: [매직바이트, magic byte, 시그니처, 파일 헤더, 확장자, 파일 형식 확인]
aliases: ["확장자 없음", "exe인데 안열림", "이거 진짜 exe 맞아?", "파일 형식 확인"]
symptom_keywords: ["확장자가 이상함", "확장자가 없는 파일", "IDA가 안열림", "exe라는데 실행이 안됨"]
source_ids: []
last_verified: "2026-09-08"
---

## 한 줄 요약
파일이 실제로 무엇인지는 확장자가 아니라 파일 맨 앞의 **매직 바이트(Magic Byte)** 로 판단해야 하며, `file` 명령이나 헥스 에디터로 직접 확인하는 습관을 들여야 한다.

## 언제 검색해야 하나
- 문제에서 준 파일에 확장자가 없거나(`chall`, `prob1`), 확장자가 의심스러울 때(`.exe`인데 크기가 이상하게 작음)
- 확장자를 `.txt`나 `.dat`로 바꿔서 위장한 문제를 만났을 때
- IDA/Ghidra에 파일을 넣었더니 "Unknown format"이라고 뜰 때

## 핵심 개념
운영체제와 도구들은 파일 확장자를 사람이 보기 편하라고 붙여놓은 이름표일 뿐, 실제로 파일이 어떤 형식인지는 **파일 맨 앞 몇 바이트(매직 바이트/시그니처)** 로 결정된다. CTF 문제 출제자는 종종 일부러 확장자를 지우거나 틀리게 붙여서 "확장자만 믿지 말라"는 테스트를 넣는다.

대표적인 매직 바이트:

| 형식 | 매직 바이트(헥스) | 아스키로 보면 |
|---|---|---|
| PE (Windows EXE/DLL) | `4D 5A` | `MZ` |
| ELF (Linux) | `7F 45 4C 46` | `.ELF` |
| ZIP / APK / JAR / docx | `50 4B 03 04` | `PK..` |
| PNG | `89 50 4E 47` | `.PNG` |
| PDF | `25 50 44 46` | `%PDF` |
| gzip | `1F 8B` | - |
| 7z | `37 7A BC AF 27 1C` | - |

즉 `MZ`로 시작하면 확장자가 뭐든 Windows PE 계열이고, `7F 45 4C 46`으로 시작하면 확장자가 없어도 ELF다.

## 화면/코드에서 보이는 징후
- 헥스 에디터로 파일을 열었을 때 처음 두 바이트가 `4D 5A` (`MZ`) — PE 파일
- 처음 네 바이트가 `7F 45 4C 46` — ELF 파일
- `file` 명령 실행 시 확장자와 무관하게 실제 형식이 텍스트로 출력됨

## 가장 먼저 할 것
확장자를 지우거나 바꾸지 말고, 파일을 손대기 전에 **먼저 `file` 명령이나 헥스 에디터로 첫 몇 바이트를 확인**한다. 그다음에 필요하면 올바른 확장자로 복사본을 만든다(원본은 보존).

## 단계별 절차

**1) 커맨드라인에서 빠르게 확인 (WSL/Linux)**
```bash
file ./mystery_file
```
출력 예:
```
mystery_file: PE32+ executable (console) x86-64, for MS Windows
```
확장자가 없어도 `file`은 내용을 읽어서 정확히 알려준다.

**2) 헥스 에디터로 직접 확인 (Windows, HxD)**
1. HxD 실행 → 파일 열기(Ctrl+O)로 문제 파일을 연다.
2. 창 왼쪽 위, 오프셋 `00000000`부터 시작하는 첫 줄을 본다.
3. `4D 5A`로 시작하면 PE, `7F 45 4C 46`(아스키 칸에 `.ELF`)로 시작하면 ELF다.

**3) Detect It Easy로 한 번에 확인**
DIE에 파일을 드래그하면 "File type" 칸에 `PE32+` 또는 `ELF64` 등으로 바로 표시되고, 확장자와 무관하게 동작한다. 확장자가 없는 파일도 그대로 열 수 있다.

**4) 올바른 확장자로 복사본 생성**
분석 도구(IDA 등)가 확장자를 보고 플러그인을 다르게 적용하는 경우가 있으므로, 원본은 그대로 두고 사본을 만들어 형식에 맞는 확장자를 붙인다.
```bash
cp mystery_file mystery_file.exe   # PE로 확인된 경우
```

## 명령어/단축키
```bash
file ./mystery_file
xxd -l 16 ./mystery_file   # 처음 16바이트를 헥스로 출력
```
`xxd -l 16` 출력 예:
```
00000000: 4d5a 9000 0300 0000 0400 0000 ffff 0000  MZ..............
```
`4d5a`가 보이면 PE 확정.

## 출력 해석
- `file` 출력의 `PE32`는 32비트 PE, `PE32+`는 64비트 PE를 의미한다.
- `ELF 32-bit` / `ELF 64-bit`는 각각 32/64비트 ELF.
- `ASCII text`라고 나오면 실행 파일이 아니라 스크립트이거나 텍스트로 인코딩된 데이터(예: base64로 인코딩된 바이너리)일 수 있다 — 이 경우 디코딩부터 해야 한다.

## 흔한 실수
- 확장자를 보고 "이건 이미지겠지"라며 무시했는데 실제로는 매직 바이트가 `MZ`인 실행 파일인 경우 (스테가노그래피/위장 문제)
- 파일 앞부분에 쓰레기 바이트를 몇 개 붙여서 매직 바이트를 가리는 문제 — 이 경우 `file`이 실패하면 헥스 에디터로 중간부터 `MZ`나 `ELF` 시그니처를 직접 검색(HxD의 Ctrl+F → Hex-values 검색)해야 한다.
- 원본 파일을 확장자 변경하면서 덮어써서 원본을 잃어버리는 것 — 항상 사본에서 작업한다.

## 막혔을 때 다음 체크
- `file`이 `data`라고만 나오고 아무 정보가 없다면 → 파일이 암호화/인코딩되어 있거나 커스텀 포맷일 가능성. 문제 설명을 다시 읽고 엔트로피를 확인(REV-0228).
- ZIP 시그니처(`PK`)가 나오면 APK, JAR, docx, 또는 그냥 zip일 수 있으니 `unzip -l`로 내부 목록을 먼저 본다.
- PE/ELF가 확인되면 → REV-0001(30초 트리아지)의 다음 단계(문자열, 임포트 확인)로 진행.

## 미니 예제
```bash
$ ls
chall

$ file chall
chall: data

$ xxd chall | head -3
00000000: 4141 4141 7f45 4c46 0201 0100 0000 0000  AAAA.ELF........
00000010: ...
```
앞에 `AAAA`(0x41414141) 4바이트가 붙어 있어 `file`이 형식을 못 알아봤지만, 5번째 바이트부터 `7f 45 4c 46`(`.ELF`)가 보인다. 이 경우 HxD/파이썬으로 앞 4바이트를 잘라내면 정상 ELF가 된다:
```bash
$ dd if=chall of=chall_fixed bs=1 skip=4
$ file chall_fixed
chall_fixed: ELF 64-bit LSB executable, x86-64, ...
```

## 관련 글
- REV-0001 — 리버싱 문제 파일을 받았을 때 30초 트리아지
- REV-0020 — Magic Byte와 파일 시그니처 (예정)
- REV-0100 — PLT와 GOT 기초

## 출처/검증
- 매직 바이트 표는 각 형식 공식 스펙(PE: Microsoft PE/COFF Specification, ELF: System V ABI) 기준으로 작성 (2026-09-08 검증).
- `file(1)`, `xxd(1)` man page 기준.
