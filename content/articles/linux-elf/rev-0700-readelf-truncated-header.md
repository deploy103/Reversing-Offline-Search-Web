---
id: REV-0700
title: "readelf가 잘린 헤더라고 오류를 낼 때(손상된 ELF)"
slug: "rev-0700-readelf-truncated-header"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["readelf", "objdump", "file", "xxd"]
keywords: ["readelf Error Reading bytes extends past end of file", "손상된 ELF", "readelf 헤더 오류", "ELF 파일 잘림", "section headers not available"]
aliases: ["readelf 오류남", "ELF 파일 깨짐", "readelf Error 뜸", "손상된 바이너리 분석"]
symptom_keywords: ["readelf: Error: Reading ... bytes extends past end of file", "Section headers are not available", "readelf가 파일을 못 읽음", "CTF 바이너리가 손상된 것처럼 보임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`readelf`가 `Error: Reading 0x... bytes extends past end of file for section headers` 같은 오류를 내는 것은 파일이 진짜로 다운로드 중 잘렸거나(전송 오류), 혹은 CTF 문제 출제자가 **일부러 ELF 헤더의 `e_shoff`/`e_shnum` 값을 조작해서 분석 도구를 방해**했기 때문이며, 먼저 파일 크기와 다운로드 무결성을 확인하고, 그래도 안 되면 Section Header 없이도 동작하는 `readelf -h`/`-l`과 Program Header 기반 분석으로 우회하면 된다.

## 언제 검색해야 하나
- `readelf -S ./chall` 또는 `readelf -a ./chall`을 실행했는데 `readelf: Error: Reading 0x... bytes extends past end of file for section headers`류 메시지가 뜰 때
- `Section headers are not available!` 또는 `Section headers are corrupt` 문구를 봤을 때
- CTF에서 받은 바이너리가 이상하게 안 열려서 "다운로드가 잘못됐나?" 의심될 때

## 핵심 개념

### readelf 오류의 근본 원인: e_shoff/e_shnum이 파일 범위를 벗어남
ELF 헤더(REV-0089)에는 Section Header Table의 시작 오프셋(`e_shoff`)과 개수(`e_shnum`), 각 엔트리 크기(`e_shentsize`)가 들어있다. `readelf`는 이 값들을 곱하고 더해서 "Section Header Table 전체 크기"를 계산한 뒤, 그 범위가 실제 파일 크기 안에 들어오는지 검사한다. 계산된 끝 지점이 파일 끝을 넘어서면 `Reading N bytes extends past end of file for section headers`라는 오류를 내고 Section Header 파싱을 포기한다.

이 상황이 생기는 원인은 크게 세 가지다.
1. **파일이 실제로 잘렸다**: 다운로드가 중간에 끊기거나, `scp`/`git` 전송 중 오류로 파일 뒷부분이 잘려나간 경우. 파일 크기를 원본과 비교하면 바로 드러난다.
2. **CTF 바이너리가 의도적으로 조작됨**: 출제자가 `e_shoff`를 아주 큰 값으로 바꾸거나 `e_shnum`을 비정상적으로 늘려서, `readelf`/`objdump` 같은 표준 도구가 Section Header를 못 읽게 만드는 안티 리버싱 트릭. 실제로 실행하는 데는 Section Header가 전혀 필요 없으므로(커널은 Program Header만 본다) 바이너리는 정상 실행되는데 정적 분석 도구만 곤란해진다.
3. **`e_shnum == 0`인 정상 케이스를 readelf가 잘못 처리하는 바이너리 버그**: ELF 사양상 Section Header가 없는 파일은 `e_shoff == 0`, `e_shnum == 0`이 정상인데, 일부 readelf 버전은 이 경우를 잘못 처리해 첫 섹션의 `sh_size`를 `e_shnum`으로 오인하는 알려진 버그가 있었다. 흔한 경우는 아니지만 binutils 버전에 따라 발생할 수 있다.

### 왜 실행은 되는데 readelf만 안 되는가
프로그램을 실제로 로드하고 실행하는 커널의 ELF 로더는 **Program Header만** 사용한다(REV-0090). Section Header는 링커/디버거/분석 도구가 심볼, 재배치 정보 등을 더 편하게 찾기 위한 부가 정보일 뿐, 실행에는 불필요하다. 그래서 Section Header가 깨졌거나 조작된 바이너리도 `./chall`로 정상 실행되는 경우가 많고, 이 비대칭이 "실행은 되는데 readelf/objdump만 이상하다"는 상황을 만든다.

## 화면/코드에서 보이는 징후
```text
$ readelf -S ./chall
readelf: Error: Reading 0x1948 bytes extends past end of file for section headers
Section headers are not available!
```
또는
```text
$ readelf -a ./chall
readelf: Warning: the e_shentsize field in the ELF header is larger than the size of an ELF section header
readelf: Error: Reading 9631435 bytes extends past end of file for section headers
```

## 가장 먼저 할 것
1. 파일 크기와 다운로드 무결성부터 확인한다 — 진짜 전송 오류인지 아닌지가 이후 절차를 결정한다.
   ```bash
   ls -l ./chall
   file ./chall
   ```
2. 다운로드 문제가 아니라면(파일 크기가 다른 팀원/원본과 동일하다면) 조작된 Section Header일 가능성이 높으므로, Section Header 없이 분석하는 절차로 넘어간다.

## 단계별 절차

**1) 파일 무결성 재확인**
```bash
ls -l ./chall
md5sum ./chall        # 문제 서버/원본 배포 파일과 해시 비교 가능하면 비교
file ./chall
```
`file` 명령이 `ELF 64-bit LSB ..., corrupted section header size`처럼 이미 손상을 감지해 알려주는 경우도 있다.

**2) ELF 헤더 자체는 정상인지 확인 (Section Header 없이)**
```bash
readelf -h ./chall
```
`readelf -h`는 ELF 헤더만 읽으므로 Section Header가 깨져 있어도 대부분 정상 출력된다. 여기서 `e_shoff`, `e_shnum`, `e_shentsize` 값을 직접 확인한다.

**3) `e_shoff`가 파일 크기를 넘는지 직접 계산**
```bash
stat -c%s ./chall
readelf -h ./chall | grep -E "Start of section headers|Size of section headers|Number of section headers"
```
`Start of section headers`(예: 0x1948) + `Size of section headers`(보통 64바이트, 64비트 기준) × `Number of section headers`가 파일 크기를 초과하면 readelf가 오류를 내는 게 당연한 결과다.

**4) 재다운로드로 원본 파일 확보 시도**
CTF 문제 서버에서 받은 파일이라면, 다시 다운로드하거나 다른 배포 경로(문제 zip 재다운로드)로 확보해서 파일 크기가 달라지는지 비교한다. 크기가 달라지면 단순 전송 오류였던 것이다.

**5) 진짜로 조작된 것이면 Section Header 없이 분석 진행**
Section Header가 없어도 Program Header(REV-0090)만으로 코드/데이터 영역을 알아낼 수 있다.
```bash
readelf -l ./chall     # Program Header는 별도 오프셋이라 대부분 정상 파싱됨
```
`PT_LOAD` 세그먼트 중 실행 가능(`R E`) 플래그가 있는 항목의 `Offset`, `VirtAddr`, `FileSiz`를 확인하면, 코드가 파일 어느 범위에 있고 메모리 어디에 매핑되는지 알 수 있다.

**6) objdump로 raw 디스어셈블(섹션 정보 없이)**
```bash
objdump -D -b binary -m i386:x86-64 --start-address=0x1000 --adjust-vma=0x400000 ./chall
```
`-b binary`로 ELF 파싱을 아예 건너뛰고 파일을 순수 바이트 스트림으로 취급해 디스어셈블할 수 있다. `--adjust-vma`로 5단계에서 확인한 `VirtAddr`와 파일 오프�이 맞도록 보정한다.

**7) Ghidra/IDA로 우회**
정적 분석 도구 중 다수(Ghidra, IDA)는 Section Header가 없어도 Program Header만으로 로드/분석이 가능하도록 설계되어 있으므로, `readelf`/`objdump`가 막히면 이런 GUI 도구로 넘어가는 것도 실용적인 선택이다.

## 명령어/단축키
```bash
ls -l ./chall
readelf -h ./chall
readelf -l ./chall
stat -c%s ./chall
objdump -D -b binary -m i386:x86-64 ./chall
xxd ./chall | head -5    # 헤더 바이트 직접 확인
```

## 출력 해석
- `readelf -h`가 정상 출력되면 ELF 헤더 자체는 살아있고, Section Header Table 관련 필드(`e_shoff`, `e_shnum`)만 문제라는 뜻이다.
- `Start of section headers`가 `0`이고 `Number of section headers`도 `0`이면 정상적인 "Section Header 없음" 상태다 — 이 경우는 오류가 아니라 원래 그렇게 만들어진 바이너리다.
- `xxd ./chall | head`로 첫 64바이트를 봤을 때 `7f 45 4c 46`(`\x7fELF`)로 시작하면 최소한 ELF 매직 넘버는 살아있는 것이므로 완전히 손상된 파일은 아니다.

## 흔한 실수
- readelf 오류 메시지만 보고 "이 파일은 분석 불가능"이라고 포기하는 것 — 실행에는 Section Header가 필요 없으므로 대부분 여전히 분석 가능하다.
- 파일 크기 비교 없이 바로 "일부러 조작된 안티 리버싱 바이너리"라고 단정하는 것 — 단순 다운로드/전송 오류일 수도 있으므로 먼저 크기부터 확인해야 한다.
- `readelf -a`(전체 정보) 하나만 시도해보고 포기하는 것 — `-h`, `-l`처럼 Section Header에 의존하지 않는 개별 옵션은 따로 시도해볼 가치가 있다.
- `objdump -d`(Section Header 필요)만 쓰고 `-b binary` 모드가 있다는 걸 몰라서 raw 디스어셈블을 못 하는 것.

## 막혔을 때 다음 체크
- ELF 헤더 필드(`e_shoff`, `e_shnum` 등) 자체의 의미가 헷갈린다면 → REV-0089 ELF 헤더 읽는 법
- Program Header와 Section Header의 역할 차이를 다시 보고 싶다면 → REV-0090 ELF Program Header와 Section Header 차이
- readelf 기본 사용법이 아직 익숙하지 않다면 → REV-0091 readelf 기본 사용법
- Section Header가 없어서 objdump 디스어셈블 자체가 끊기거나 안 되는 경우의 대응은 → REV-0701 objdump 디스어셈블 결과가 중간에 끊길 때
- 애초에 이 파일이 ELF가 맞는지부터 의심된다면 → REV-0095 file 명령으로 ELF 정보 확인

## 미니 예제
```text
$ ls -l chall
-rwxr-xr-x 1 user user 16728 Sep  8 10:00 chall

$ readelf -S ./chall
readelf: Error: Reading 0x1948 bytes extends past end of file for section headers
Section headers are not available!

$ readelf -h ./chall | grep -E "Start of section|Number of section"
  Start of section headers:          16728 (bytes into file)
  Number of section headers:         29

$ stat -c%s ./chall
16728
```
`Start of section headers`가 파일 크기(16728)와 정확히 같다 — 즉 Section Header Table을 위한 공간이 파일에 전혀 없는데도 헤더에는 "29개 섹션이 있다"고 기록되어 있는 것이다. 이는 전형적인 조작 사례이며, `readelf -l`로 Program Header만 가지고 분석을 이어가면 된다.

## 관련 글
- REV-0089 — ELF 헤더 읽는 법
- REV-0090 — ELF Program Header와 Section Header 차이
- REV-0091 — readelf 기본 사용법
- REV-0095 — file 명령으로 ELF 정보 확인
- REV-0701 — objdump 디스어셈블 결과가 중간에 끊길 때

## 출처/검증
- `e_shoff`/`e_shnum`/`e_shentsize` 필드로 Section Header Table 범위를 계산하고 파일 크기와 비교하는 readelf의 검증 로직, 그리고 `Reading N bytes extends past end of file for section headers` 오류 문구는 GNU binutils `readelf` 소스(`binutils/readelf.c`)의 공개 동작이며 다수의 CTF 라이트업과 binutils 버그 트래커에서 재현 보고된 내용이다.
- 커널 ELF 로더가 실행 시 Program Header만 사용하고 Section Header를 사용하지 않는다는 사실은 Linux 커널 `fs/binfmt_elf.c`의 `load_elf_binary()` 구현 및 System V ABI 명세 기준이다.
- `objdump -b binary -m i386:x86-64`로 헤더 없이 raw 바이트를 디스어셈블하는 방법은 GNU objdump 공식 문서(`objdump(1)`)의 `-b`/target 옵션 설명에 기반한다.
