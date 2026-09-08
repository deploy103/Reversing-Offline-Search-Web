---
id: REV-0226
title: "UPX 기본 언패킹"
slug: "rev-0226-upx-basic-unpacking"
category: "packing"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["UPX", "Detect It Easy", x64dbg, IDA]
keywords: ["upx -d", "UPX 언패킹", "upx 압축 해제", "UPX unpack", "upx decompress", "UPX 자동 언패킹", "upx --force", "upx -d 사용법"]
aliases: ["upx 언패킹", "upx 푸는법", "upx -d 명령어", "upx 압축 풀기", "UPX 디컴프레스"]
symptom_keywords: ["upx -d 안됨", "upx 언패킹 에러", "packed by upx how to unpack", "upx 압축 해제 방법", "upx로 패킹된 파일 여는법", "CantUnpackException"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
UPX로 패킹된 것이 확인된 파일은 원본을 복사해둔 뒤 `upx -d packed.exe` 한 줄로 대부분 자동으로 원래 코드가 복원되며, 이후 IDA/Ghidra에 다시 열면 정상적인 함수/문자열/import가 그대로 보인다.

## 언제 검색해야 하나
- REV-0225 절차로 파일이 UPX로 패킹되었음을 확인했고, 이제 실제로 풀어서 분석하고 싶을 때
- `upx -d`를 실행했는데 에러가 나서 원인을 파악하고 싶을 때
- UPX 언패킹 후 IDA에 다시 열었을 때 정상적으로 함수/문자열이 보이는지 검증하는 방법을 알고 싶을 때
- CTF 문제 바이너리가 UPX로 패킹되어 있어서 빠르게 원본 코드를 보고 싶을 때

## 핵심 개념
UPX는 "reversible(가역적인)" 압축기로 설계되었다. 즉 `upx`로 압축한 파일은 같은 `upx` 도구의 `-d`(decompress, 압축 해제) 옵션으로 **원본과 100% 동일한 실행 파일**로 복원할 수 있다. 이는 UPX가 원래 "실행 파일을 작게 만들어서 배포"하는 정상적인 용도로 설계되었기 때문이며, 압축 해제 알고리즘이 공개되어 있고 UPX 실행 파일 자체에 내장되어 있다.

이 특성 덕분에 UPX로 패킹된 CTF 바이너리나 악성코드 샘플은 별도의 리버싱 없이 **UPX 실행 파일 하나만 있으면 몇 초 만에 언패킹**할 수 있다. 이것이 바로 UPX가 다른 상용 패커(VMProtect, Themida 등)와 결정적으로 다른 점이다. 상용 패커들은 압축 해제 후 원본 OEP로 점프하고 나면 스텁 코드가 스스로를 흔적 없이 지우거나, 아예 자동 복원용 도구를 공개하지 않기 때문에 REV-0227에서 다루는 수동 언패킹(OEP 찾기 + 메모리 덤프)이 필요하다. 반면 UPX는 "압축기 벤더가 직접 제공하는 공식 압축 해제 기능"이 있다는 점에서 예외적으로 쉽다.

## 화면/코드에서 보이는 징후
언패킹 전:
- IDA Functions 창에 함수 몇 개만 보임, 섹션 이름이 `UPX0`/`UPX1`
- entry point 코드가 `PUSHAD` → 압축 해제 루프 → `POPAD` → `JMP`로 끝나는 짧은 스텁

언패킹 후(`upx -d` 실행 성공 시):
- 파일 크기가 원래보다 커짐(압축 해제되었으므로)
- 섹션 이름이 다시 `.text`, `.data`, `.rdata` 등 표준 이름으로 복원됨(UPX가 원본 섹션 이름을 기억해두었다가 되살림)
- IDA에 다시 열면 함수 개수가 수십~수백 개로 늘어나고, `strings` 결과에 원래 프로그램의 문자열(에러 메시지, 포맷 문자열 등)이 그대로 보임
- Imports 창에 원본이 실제로 쓰던 API들이 전부 복원되어 있음

## 가장 먼저 할 것
`upx -d`는 **기본적으로 원본 파일을 그 자리에서 덮어쓴다.** 언패킹을 시도하기 전에 반드시 원본 파일을 복사해서 백업해둔다.

```bash
cp packed.exe packed.exe.bak
```

Windows PowerShell이라면:

```powershell
Copy-Item packed.exe packed.exe.bak
```

## 단계별 절차

**1) 원본 백업**

```bash
cp packed.exe packed.exe.bak
```

**2) 언패킹 실행**

```bash
upx -d packed.exe
```

**3) 출력 확인**

명령이 끝나면 터미널에 압축 해제 전/후 크기와 "Unpacked 1 file." 메시지가 뜨는지 확인한다(아래 "출력 해석" 참고).

**4) 파일 크기/섹션 변화 확인**

`ls -l packed.exe`(또는 `dir`)로 파일 크기가 커졌는지 확인한다. PE-bear나 IDA로 다시 열어 섹션 이름이 `UPX0`/`UPX1`에서 정상 이름으로 바뀌었는지 본다.

**5) IDA/Ghidra로 재분석**

이미 IDA에 원본을 열어두었다면 데이터베이스를 새로 만들어야 한다(언패킹된 파일은 바이트 배치가 완전히 다르므로 기존 idb 재사용 불가). `File → Close`로 닫고, 언패킹된 `packed.exe`를 새로 연다. Functions 창(Ctrl+P), Strings 창(Shift+F12), Imports 창을 다시 확인해서 함수/문자열/API가 정상적으로 늘어났는지 검증한다.

**6) 실패 시 강제 옵션 시도**

기본 `upx -d`가 "not packed by UPX" 또는 헤더 손상 관련 오류를 낸다면, 다음을 시도해볼 수 있다.

```bash
upx -d --force packed.exe
```

`--force`는 UPX가 내부 검증에서 약간 의심스럽다고 판단해도 강제로 언패킹을 시도하게 한다. 다만 파일이 UPX가 아니거나 심하게 변형되었다면 이 옵션으로도 실패하며, 이 경우 REV-0227의 수동 언패킹 개념으로 넘어가야 한다.

## 명령어/단축키
- `cp packed.exe packed.exe.bak` : 언패킹 전 원본 백업 (Linux/WSL/Git Bash)
- `upx -d packed.exe` : 기본 언패킹 (파일을 덮어씀)
- `upx -d -o unpacked.exe packed.exe` : 원본을 덮어쓰지 않고 다른 파일명(`unpacked.exe`)으로 출력
- `upx -d --force packed.exe` : 검증을 완화하고 강제 언패킹 시도
- `upx -l packed.exe` : 언패킹 없이 압축 정보만 조회
- `upx -V` : upx 버전 확인

## 출력 해석
정상적으로 언패킹되면 다음과 비슷한 출력이 나온다.

```text
                       Ultimate Packer for eXecutables
                          Copyright (C) 1996 - 2024
UPX 4.2.4       Markus Oberhumer, Laszlo Molnar & John Reiser   Aug 30th 2024

        File size         Ratio      Format      Name
   --------------------   ------   -----------   -----------
    245760 <-    102400   41.67%    win64/pe     packed.exe

Unpacked 1 file.
```

- `File size` 열의 왼쪽 숫자(예: 245760)가 **언패킹 후(원본) 크기**, 화살표 오른쪽 숫자(예: 102400)가 **압축된 상태였던 크기**다. 왼쪽이 오른쪽보다 커야 정상이다.
- `Ratio` 열은 압축 비율로, UPX는 보통 30~60% 정도로 파일을 줄인다.
- 마지막 줄 `Unpacked 1 file.`이 뜨면 성공이다.
- 실패 시 `packed.exe: NotPackedException: not packed by UPX` 또는 `CantUnpackException: header corrupted`가 뜬다. 전자는 애초에 UPX가 아니거나 이미 언패킹된 파일, 후자는 UPX가 맞지만 헤더 일부가 손상/변형되어 자동 복원이 불가능한 상태다.
- `AlreadyPackedException`은 이미 UPX로 두 번 이상 압축을 시도했거나 이미 풀린 파일에 다시 `-d`를 시도할 때 나올 수 있는 관련 오류 계열이다.

## 흔한 실수
- 백업 없이 바로 `upx -d`를 실행해서 실패했을 때 원본을 잃어버리는 것. 반드시 `packed.exe.bak`처럼 복사본을 먼저 만든다.
- 언패킹 전에 열어둔 IDA idb를 그대로 재사용하려는 것. 언패킹 전후로 파일의 바이트 배치, 섹션 offset, entry point 주소가 완전히 달라지므로 반드시 새 데이터베이스를 만들어야 한다.
- `upx -d`가 실패했다고 바로 포기하고 REV-0227의 훨씬 복잡한 수동 언패킹으로 건너뛰는 것. 먼저 `--force` 옵션이나 최신/구버전 upx 실행 파일로 다시 시도해볼 가치가 있다.
- 언패킹된 파일을 실행해서 정상 동작하는지 확인하지 않고 바로 분석에 들어가는 것. 드물게 언패킹 결과물이 원본과 완전히 동일하지 않을 수 있으므로(특히 이미 변형된 UPX 헤더의 경우), 가능하면 실제로 실행해서 원래처럼 동작하는지 확인하는 것이 안전하다.
- `-o` 옵션 없이 실행해서 원본 압축 파일이 사라진 뒤에야 "패킹된 상태의 파일도 필요했는데"라고 뒤늦게 깨닫는 것. 패킹된 원본과 언패킹된 결과물을 둘 다 보존하려면 처음부터 `-o unpacked.exe`로 별도 저장하는 습관을 들인다.

## 막혔을 때 다음 체크
- `upx -d`가 `NotPackedException`을 낸다면 → REV-0225로 돌아가 정말 UPX가 맞는지 매직 바이트/섹션 이름을 다시 확인한다.
- `upx -d --force`도 실패한다면 → 이 파일은 UPX 헤더가 의도적으로 손상되었거나(안티 언패킹 트릭) 매우 특이한 변형 UPX일 수 있다. REV-0227(수동 언패킹 개념)로 이동해 OEP를 직접 찾는 방법을 검토한다.
- 언패킹은 성공했는데 IDA에서 여전히 함수가 적게 보인다면 → 다른 패커가 UPX 위에 한 번 더 씌워졌을(이중 패킹) 가능성이 있다. 다시 REV-0224 체크리스트로 돌아가 재확인한다.
- 언패킹된 파일을 실행했을 때 크래시가 난다면 → 백업해둔 `.bak` 파일로 다시 시작하고, upx 버전을 바꿔서(공식 GitHub 릴리스에서 여러 버전 다운로드) 재시도한다.

## 미니 예제
Windows PE 파일 `crackme.exe`가 REV-0225 절차로 UPX 4.2.4 패킹임이 확인되었다고 하자.

```powershell
PS> Copy-Item crackme.exe crackme.exe.bak
PS> upx -d crackme.exe

                       Ultimate Packer for eXecutables
                          Copyright (C) 1996 - 2024
UPX 4.2.4       Markus Oberhumer, Laszlo Molnar & John Reiser   Aug 30th 2024

        File size         Ratio      Format      Name
   --------------------   ------   -----------   -----------
    409600 <-    184320   45.00%    win64/pe     crackme.exe

Unpacked 1 file.
```

언패킹 후 `crackme.exe`를 IDA에 새로 열면 섹션 이름이 `.text`/`.rdata`/`.data`로 복원되어 있고, Functions 창에 함수가 120여 개, Strings 창에 "Enter password:" 같은 원래 문자열이 그대로 보인다. 이제부터는 일반적인 정적/동적 분석 절차(REV-0142 등)를 그대로 적용하면 된다.

## 관련 글
- REV-0225 — UPX인지 확인하는 법
- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- ../windows-pe/rev-0126-die-basics.md — Detect It Easy 기본 사용법

## 출처/검증
- `upx -d`, `-o`, `--force`, `-l` 옵션 동작과 출력 형식(파일 크기 표, Ratio, Unpacked 메시지)은 UPX 공식 GitHub 저장소(github.com/upx/upx) 문서 및 `upx --help` 출력 내용을 기준으로 정리했다(2026-09-08 검증).
- UPX가 원본과 동일하게 복원 가능한 가역적 압축기라는 설명은 UPX 공식 README의 설계 목표 설명을 참고했다.
- 실제 출력 문구/버전 배너는 설치된 UPX 버전에 따라 달라질 수 있으므로, 로컬 upx 버전에서 `upx -V`로 재확인할 것을 권장한다.
