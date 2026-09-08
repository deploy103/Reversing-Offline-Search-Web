---
id: REV-0297
title: "UPX 설치와 명령어"
slug: "rev-0297-upx-install-commands"
category: "tools"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["UPX"]
keywords: ["UPX 설치", "UPX 명령어", "upx -d", "upx 압축 해제", "UPX 사용법"]
aliases: ["UPX 설치법", "UPX 언패킹 명령어", "upx 옵션"]
symptom_keywords: ["upx 명령이 없다고 뜸", "upx 설치가 안됨", "upx -d 실패함"]
source_ids: ["SRC-UPX-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
UPX(Ultimate Packer for eXecutables)는 실행 파일 압축 도구로, 설치는 공식 GitHub 릴리스에서 압축 파일 하나만 받으면 끝나고, 리버싱 실무에서는 대부분 `upx -d`(압축 해제) 명령 하나만 기억하면 된다.

## 언제 검색해야 하나
- 오프라인 대회 전에 UPX를 미리 준비해 두고 싶을 때
- `upx` 명령이 설치되어 있지 않아 압축을 풀 수 없을 때
- UPX로 직접 파일을 압축해서 테스트용 패킹 샘플을 만들어보고 싶을 때

UPX로 압축된 바이너리를 어떻게 알아보는지, `upx -d`가 실패할 때의 대응(수동 언패킹, OEP 찾기 등)은 이 문서에서 다루지 않는다. 리버싱 관점의 식별·언패킹 절차는 별도 문서를 참고할 것.
- `../packing/rev-0225-identifying-upx.md` (UPX로 패킹된 바이너리 식별하기)
- `../packing/rev-0226-upx-basic-unpacking.md` (UPX 기본 언패킹 실습)

## 핵심 개념
UPX는 원본 실행 파일을 압축해서, 실행 시 자기 자신을 메모리에 풀어(unpack) 원래 코드로 점프하는 스텁을 앞에 붙이는 방식으로 동작한다. 오픈소스이고 Windows(PE)와 Linux(ELF) 양쪽을 모두 지원하며, CTF에서는 "리버싱 난이도를 인위적으로 높이기 위한" 가장 흔한 1차 관문으로 자주 등장한다. 설치 자체는 매우 단순하다 — 컴파일이 필요 없는 단일 실행 파일 배포판을 그대로 받아 쓰면 된다.

## 화면/코드에서 보이는 징후
바이너리를 열었는데 `strings`/`nm` 결과가 거의 없고, 섹션 이름이 `UPX0`, `UPX1`, `UPX!`처럼 보이거나, `file` 명령 결과에 별다른 특이사항이 없는데도 함수가 거의 안 보인다면 UPX 패킹을 의심할 신호다. 자세한 식별 방법은 `../packing/rev-0225-identifying-upx.md`에서 다룬다.

## 가장 먼저 할 것
```bash
upx -V
```
버전이 출력되면 정상 설치된 것이다. 이후 의심되는 파일에 바로 시도한다.
```bash
upx -d ./chall -o ./chall_unpacked
```

## 단계별 절차

### 1) 설치 — Windows
공식 GitHub 릴리스(`https://github.com/upx/upx/releases`)에서 `upx-X.X.X-win64.zip`을 받아 압축을 풀면 그 안의 `upx.exe`를 바로 실행할 수 있다. 설치 프로그램이 없는 포터블 배포이므로, 압축을 푼 폴더를 그대로 오프라인 대회용 USB/외장 SSD에 복사해 가면 된다.
```powershell
.\upx-X.X.X-win64\upx.exe -V
```

### 2) 설치 — Linux
```bash
# 배포판 패키지(간단)
sudo apt install upx-ucl

# 또는 공식 정적 바이너리 tarball(버전을 더 최신으로 맞추고 싶을 때)
wget https://github.com/upx/upx/releases/download/vX.X.X/upx-X.X.X-amd64_linux.tar.xz
tar -xf upx-X.X.X-amd64_linux.tar.xz
./upx-X.X.X-amd64_linux/upx -V
```
오프라인 대회 전에는 반드시 `wget`/`apt`를 온라인 상태에서 미리 실행해 바이너리를 확보해 두어야 한다.

### 3) 실행 파일 압축(테스트용 패킹 샘플 만들기)
```bash
upx ./target -o ./target_packed
```
연습용으로 직접 UPX 패킹된 샘플을 만들어보면, 이후 실전에서 UPX로 패킹된 CTF 문제를 만났을 때 섹션 구조나 `strings` 결과가 어떻게 달라지는지 미리 감을 잡을 수 있다.

### 4) 압축 해제(언패킹)
```bash
upx -d ./chall -o ./chall_unpacked
```
성공하면 원본과 동일하게 동작하는(단, 언패킹된 형태의) 실행 파일이 만들어진다.

### 5) 압축 정보만 확인(해제하지 않고)
```bash
upx -l ./chall     # 압축률, 원본/압축 후 크기 정보만 출력
upx -t ./chall     # 압축 파일 무결성 테스트
```

## 명령어/단축키
```bash
upx -V                          # 버전 확인
upx ./target -o ./out           # 압축(패킹)
upx -d ./chall -o ./out         # 압축 해제(언패킹)
upx -l ./chall                  # 압축 정보만 확인
upx -t ./chall                  # 무결성 테스트
upx -9 ./target -o ./out        # 최고 압축률로 압축(테스트용)
```

## 흔한 실수
- `upx -d`가 "not packed by UPX" 오류를 내는데 UPX가 아니라고 오해하는 것 — 문제 출제자가 UPX 헤더를 일부러 손상/수정해 자동 언패킹을 막은 경우일 수 있다. 이 경우는 수동 언패킹이 필요하며 `../packing/rev-0226-upx-basic-unpacking.md`에서 다룬다.
- Windows용 `upx.exe`로 ELF를, 혹은 그 반대로 착각해서 압축을 시도하는 것 — UPX 자체는 크로스 포맷을 지원하지만 대상 아키텍처/포맷은 항상 먼저 확인해야 한다.
- 오프라인 대회 당일 처음으로 UPX 설치를 시도하다 인터넷이 없어 실패하는 것 — 반드시 사전에 준비하고 실행까지 검증해 둔다.

## 막혔을 때 다음 체크
- 이 바이너리가 UPX로 패킹된 것인지 판단하는 기준 → `../packing/rev-0225-identifying-upx.md`
- `upx -d`가 실패하는 경우의 수동 언패킹 절차 → `../packing/rev-0226-upx-basic-unpacking.md`
- 언패킹 후 다시 구조를 확인하고 싶으면 → [REV-0091 readelf 기본 사용법](../linux-elf/rev-0091-readelf-basics.md) / [REV-0294 readelf objdump nm strings 치트시트](./rev-0294-binutils-cheatsheet.md)

## 미니 예제
```bash
$ upx -V
upx 4.2.4

$ upx -d packed.exe -o unpacked.exe
                       Ultimate Packer for eXecutables
                          Copyright (C) 1996 - 2024
UPX 4.2.4       Markus Oberhumer, Laszlo Molnar & John Reiser   Jan 27th 2024

        File size         Ratio      Format      Name
   --------------------   ------   -----------   -----------
    204800 <-    98304   48.02%    win64/pe     unpacked.exe

Unpacked 1 file.
```

## 관련 글
- REV-0294 — readelf objdump nm strings 치트시트
- REV-0091 — readelf 기본 사용법
- REV-0096 — checksec 결과 읽는 법

## 출처/검증
- 설치 방법(GitHub 릴리스, 배포판 패키지명 `upx-ucl`)과 명령어 옵션(`-d`, `-l`, `-t`, `-9`): UPX 공식 GitHub 저장소(https://github.com/upx/upx) README 및 `upx --help` 기준.
- 이 문서에서 링크한 `../packing/rev-0225-identifying-upx.md`, `../packing/rev-0226-upx-basic-unpacking.md`는 이 문서 작성 시점에 별도 배치로 병행 작성 중이라 파일 존재 여부를 직접 확인하지 못했다. 두 문서가 아직 없다면 링크가 깨진 상태일 수 있으니, 통합 시점에 경로와 제목을 다시 검증할 것.
