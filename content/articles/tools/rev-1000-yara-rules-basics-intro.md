---
id: REV-1000
title: "YARA 규칙 기초와 활용 소개"
slug: "rev-1000-yara-rules-basics-intro"
category: "tools"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [YARA]
keywords: ["YARA", "YARA 규칙", "yara rule", "strings condition", "악성코드 시그니처", "패턴 매칭 도구"]
aliases: ["야라 규칙", "yara 사용법", "yara 규칙 문법", "yara rule 작성법", "yara 패턴 매칭"]
symptom_keywords: ["yara가 뭔지 모르겠음", "yara 규칙 어떻게 씀", "yara rule 문법", "특정 바이너리를 자동으로 분류하고 싶음", "패턴으로 파일 찾기"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
YARA는 "이 바이너리 안에 이런 문자열/바이트 패턴들이 이런 조건으로 존재하면 이름을 붙여서 매칭시켜라"라는 규칙(rule)을 텍스트로 작성해서, 대량의 파일을 자동으로 분류하거나 특정 패커/악성코드 계열/CTF 문제 패턴을 빠르게 식별하는 데 쓰는 패턴 매칭 도구다.

## 언제 검색해야 하나
- 여러 개의 바이너리(CTF 문제 여러 개, 또는 샘플 여러 개)에서 공통된 문자열/바이트 패턴을 자동으로 찾아 분류하고 싶을 때
- 악성코드 분석 라이트업에서 `rule ...{ strings: ... condition: ... }` 형태의 코드 블록을 봤는데 문법을 모를 때
- UPX 같은 특정 패커로 패킹된 파일인지, 혹은 특정 취약점 패턴이 들어있는 파일인지 여러 파일에 걸쳐 한 번에 검사하고 싶을 때
- `strings`/`grep`으로 파일 하나씩 찾는 것보다, 재사용 가능한 "탐지 규칙" 형태로 패턴을 정리해두고 싶을 때

## 핵심 개념
YARA는 원래 바이러스토탈(VirusTotal)의 개발자가 만든 도구로, "악성코드에게 이름을 붙이고 식별하는 패턴 매칭 스위스 군용 칼(Swiss Army knife)"라는 별명으로 불린다. 하지만 그 쓰임새는 악성코드 분석에 국한되지 않으며, 리버싱/CTF에서도 "여러 파일 중 특정 패턴을 가진 것만 골라내기" 같은 용도로 자주 쓰인다.

YARA 규칙은 하나의 텍스트 파일(`.yar` 또는 `.yara`)에 여러 개의 `rule` 블록을 담는 형태로 작성한다. 각 `rule` 블록은 보통 세 부분으로 구성된다.

1. **`rule 이름`** — 이 규칙에 붙이는 이름. 매칭이 되면 이 이름으로 결과가 출력된다.
2. **`strings:`** — 찾고자 하는 패턴들을 나열하는 섹션. 각 패턴에는 `$변수이름`을 붙여서 나중에 `condition`에서 참조한다. 패턴은 세 종류를 쓸 수 있다.
   - 일반 텍스트 문자열: `$s1 = "password_check"`
   - 와이드(유니코드, UTF-16LE) 문자열: `$s2 = "secret" wide`
   - 정규식: `$s3 = /flag\{.*\}/`
   - 16진수 바이트 패턴: `$hex1 = { E8 ?? ?? ?? ?? 90 90 }` (여기서 `??`는 "아무 바이트나 매칭"이라는 와일드카드다)
3. **`condition:`** — 위에서 정의한 `$변수`들을 논리 연산자(`and`, `or`, `not`)나 개수 조건(`2 of them`, `all of them`)으로 조합해서, "언제 이 규칙이 매칭됐다고 볼 것인지"를 결정하는 부분. 실제 매칭 여부를 최종 결정하는 것은 항상 이 `condition` 섹션이다.

`strings`에 여러 패턴을 나열해도 `condition`에서 그 패턴들을 어떻게 조합할지 명시하지 않으면 규칙 자체가 아무 의미가 없다는 점이 중요하다. 예를 들어 특정 문자열 두 개 중 하나만 있어도 매칭되게 하려면 `condition: $s1 or $s2`처럼 써야 하고, 둘 다 있어야 매칭되게 하려면 `$s1 and $s2`로 써야 한다.

## 화면/코드에서 보이는 징후
YARA 규칙 파일(`.yar`)은 보통 다음과 같은 형태로 보인다.
```yara
rule Example_Password_Check
{
    strings:
        $s1 = "Enter password"
        $s2 = "Correct!"
        $hex1 = { 55 8B EC 83 EC }  // 함수 프롤로그 바이트 패턴 예시

    condition:
        $s1 and $s2 and $hex1
}
```
명령줄에서는 다음처럼 실행한 결과가 나온다.
```text
$ yara myrules.yar ./chall
Example_Password_Check ./chall
```
매칭된 규칙 이름과 대상 파일 경로가 한 줄로 출력된다.

## 가장 먼저 할 것
YARA를 쓰기 전에, 손으로 `strings ./chall`이나 `grep`으로 먼저 대상 파일 안에서 어떤 문자열/패턴이 실제로 존재하는지 확인한다. YARA 규칙은 이렇게 사람이 먼저 찾아낸 패턴을 "재사용 가능한 형태"로 정리하는 도구이지, 패턴을 몰라도 자동으로 찾아주는 마법 도구가 아니다.

## 단계별 절차

**1) 설치 확인**
```bash
yara --version
```
윈도우에서는 공식 GitHub 릴리스의 실행 파일을, 리눅스에서는 `apt install yara` 또는 소스 빌드로 설치할 수 있다.

**2) 가장 단순한 규칙 작성 — 문자열 하나만 찾기**
```yara
rule Find_Flag_Format
{
    strings:
        $flag = "flag{"

    condition:
        $flag
}
```
```bash
yara find_flag.yar ./chall
```

**3) 여러 조건을 논리적으로 조합하기**
```yara
rule Suspicious_Combo
{
    strings:
        $s1 = "CreateRemoteThread"
        $s2 = "VirtualAllocEx"
        $s3 = "WriteProcessMemory"

    condition:
        2 of ($s1, $s2, $s3)   // 셋 중 2개 이상이 동시에 있어야 매칭
}
```
`2 of (...)`처럼 "지정한 패턴 목록 중 몇 개 이상"이라는 개수 조건을 쓸 수 있다.

**4) 바이트 패턴(16진수)으로 특정 opcode 시퀀스 찾기**
```yara
rule Contains_NOP_Sled
{
    strings:
        $nopsled = { 90 90 90 90 90 90 90 90 }  // NOP(0x90) 8개 연속

    condition:
        $nopsled
}
```

**5) 파일 크기/헤더 조건까지 함께 검사하기**
```yara
rule Small_PE_With_Marker
{
    strings:
        $marker = "SECRET_MARKER"

    condition:
        uint16(0) == 0x5A4D and     // PE 파일 시그니처('MZ') 확인
        filesize < 100KB and
        $marker
}
```
`uint16(0) == 0x5A4D`은 파일의 첫 2바이트가 `MZ`(PE 파일 시그니처)인지 확인하는 조건이며, `filesize`는 YARA가 기본 제공하는 내장 변수다.

**6) 여러 파일/디렉터리 전체에 규칙 적용**
```bash
yara -r myrules.yar ./samples/   # -r: 하위 디렉터리까지 재귀적으로 검사
```

## 명령어/단축키
```bash
yara rules.yar target_file          # 파일 하나에 규칙 적용
yara -r rules.yar target_dir/       # 디렉터리 재귀 검사
yara -s rules.yar target_file        # 매칭된 문자열의 실제 내용/오프셋까지 출력
yara -c rules.yar target_file        # 매칭 개수만 출력
yara -n rules.yar target_file        # 매칭 안 된 규칙까지 표시(negate)
```
```yara
$변수 = "문자열"        ; 일반 텍스트 문자열
$변수 = "문자열" wide    ; UTF-16LE(유니코드) 문자열
$변수 = "문자열" nocase  ; 대소문자 구분 없이 매칭
$변수 = /정규식/         ; 정규식 패턴
$변수 = { AA BB ?? CC }  ; 16진수 바이트 패턴, ??는 와일드카드 1바이트
and / or / not           ; 조건 논리 연산
N of ($a, $b, $c)        ; 지정한 패턴 중 N개 이상 매칭되면 참
all of them / any of them ; strings 섹션 전체 중 전부/하나 이상
```

## 출력 해석
- `규칙이름 파일경로` 형태의 출력 한 줄 — 해당 파일이 그 규칙의 `condition`을 만족했다는 뜻. 아무 출력도 없으면 매칭되는 규칙이 없었다는 뜻이다(에러가 아니다).
- `yara -s` 옵션을 쓰면 매칭된 각 `$변수`가 파일의 몇 번째 오프셋에서 어떤 바이트로 발견됐는지까지 보여준다 — 어느 부분이 실제로 매칭을 유발했는지 검증할 때 필수적으로 확인해야 한다.
- 문법 오류가 있으면 컴파일 단계에서 `error: syntax error, unexpected ...` 형태의 메시지가 나오며, 이 경우 `strings`/`condition` 섹션의 중괄호나 따옴표 짝이 맞는지부터 확인한다.

## 흔한 실수
- `strings`에 패턴만 나열하고 `condition`에서 그 변수를 하나도 참조하지 않아서, 규칙이 정의는 됐지만 실제로는 아무 것도 검사하지 않는(항상 매칭 안 되거나 항상 매칭되는) 상태가 되는 것.
- 텍스트 문자열이 실제로는 UTF-16LE(유니코드)로 저장되어 있는데(윈도우 프로그램의 문자열은 이런 경우가 흔하다) `wide` 옵션을 빠뜨려서 매칭이 전혀 안 되는 것.
- `and`/`or`의 논리를 반대로 써서, "이 중 하나라도 있으면 위험"이라는 의도로 규칙을 짰는데 실제로는 `and`를 써서 모든 조건이 동시에 있어야만 매칭되게 만든 것.
- 16진수 바이트 패턴에서 와일드카드(`??`)를 빠뜨려서, 컴파일러 버전이나 오프셋이 조금만 달라져도 매칭이 실패하는 지나치게 엄격한 규칙을 만드는 것.
- 규칙 하나에 패턴을 너무 적게(문자열 1개) 넣어서 오탐(false positive)이 매우 잦은 규칙을 만드는 것 — 실무에서는 여러 패턴을 조합한 `condition`을 쓰는 것이 훨씬 신뢰도가 높다.

## 막혔을 때 다음 체크
- 대상 파일 안에 어떤 문자열이 있는지부터 다시 확인하고 싶다면 → 이진 파일에서 문자열을 추출하는 기본기(triage/binary-basics 또는 static-analysis 카테고리의 strings 관련 문서)를 먼저 참고한다.
- 패킹된 파일이라 문자열 자체가 안 보인다면 → packing 카테고리의 UPX/패커 탐지 관련 문서를 먼저 확인한 뒤, 언패킹 이후 YARA를 적용하는 순서를 고려한다.
- 바이트 패턴을 정확히 뽑아내려면 opcode를 알아야 하는데 그게 막막하다면 → REV-0272 Capstone으로 디스어셈블 자동화로 먼저 대상 코드를 사람이 읽을 수 있는 형태로 바꾼 뒤, 특징적인 바이트 시퀀스를 뽑아 YARA 패턴으로 옮기는 순서를 고려한다.

## 미니 예제
CTF 문제 여러 개 중에서 "특정 시리얼 검증 패턴"과 "flag 형식 문자열"을 동시에 가진 바이너리만 자동으로 골라내는 규칙이다.
```yara
rule CTF_Serial_Check_Pattern
{
    meta:
        author = "example"
        description = "flag{ 형식과 시리얼 검증 관련 문자열을 동시에 포함한 바이너리 탐지"

    strings:
        $flag_format = /flag\{[a-zA-Z0-9_]+\}/
        $s1 = "Enter serial"
        $s2 = "Invalid serial"
        $prologue = { 55 48 89 E5 }  // x64 함수 프롤로그: push rbp; mov rbp, rsp

    condition:
        $flag_format and ($s1 or $s2) and $prologue
}
```
```bash
yara -s ctf_pattern.yar ./challenges/
```
`meta:` 섹션은 규칙 자체의 동작에는 영향을 주지 않지만, 누가 언제 왜 만든 규칙인지 기록해두는 용도로 실무에서 널리 쓰인다. `condition`에서 `flag{...}` 정규식과, 시리얼 관련 문자열 중 하나, 그리고 x64 함수 프롤로그 바이트 패턴을 모두 `and`로 묶어, 세 조건을 동시에 만족하는 파일만 정확히 골라낸다.

## 관련 글
- REV-0272 — Capstone으로 디스어셈블 자동화
- REV-0294 — readelf objdump nm strings 치트시트
- REV-0999 — WinDbg 기초 소개와 언제 쓰는지

## 출처/검증
- YARA 규칙 문법(`rule`, `strings`, `condition`, `meta`, `wide`/`nocase`/정규식/16진수 패턴, `N of (...)`, 내장 변수 `filesize`/`uint16` 등)은 YARA 공식 문서(yara.readthedocs.io) 및 공식 GitHub(VirusTotal/yara)를 기준으로 정리했다(2026-09-09 검증).
- YARA가 바이러스토탈에서 개발되어 "패턴 매칭 스위스 군용 칼"로 소개된다는 배경 설명은 YARA 공식 문서 소개(Introduction) 페이지 기준이다.
- 명령줄 옵션(`-r`, `-s`, `-c`, `-n`)은 YARA 공식 문서의 "Command-line interface" 챕터 기준이다.
