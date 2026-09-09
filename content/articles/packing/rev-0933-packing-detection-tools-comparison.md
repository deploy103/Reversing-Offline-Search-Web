---
id: REV-0933
title: "패킹 탐지 도구 비교표"
slug: "rev-0933-packing-detection-tools-comparison"
category: "packing"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["Detect It Easy", "PE-bear", checksec]
keywords: ["패킹 탐지 도구", "DIE", "PE-bear", "checksec", "strings", "패커 확인 도구 비교", "packing detection tools"]
aliases: ["패킹 확인 어떤 도구", "die pe-bear 차이", "패킹 탐지 프로그램 비교", "어떤 툴로 패킹 확인"]
symptom_keywords: ["패킹 확인하려면 뭘 써야 하나", "die랑 pe-bear 뭐가 다른가", "checksec으로 패킹도 보이나", "linux 패킹 탐지 도구"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Windows PE 패킹 탐지는 Detect It Easy(패커 시그니처+엔트로피)와 PE-bear(섹션/헤더 세부 구조)를 조합하는 것이 표준이고, Linux ELF는 `checksec`(보호 기법 확인용, 패커 시그니처는 없음)과 `strings`/`readelf`(섹션 이름·엔트로피 대체 확인)를 함께 써야 한다.

## 언제 검색해야 하나
- 패킹 여부를 확인하고 싶은데 어떤 도구부터 열어야 할지 모를 때
- Detect It Easy와 PE-bear를 둘 다 쓰는 이유가 뭔지, 하나만 쓰면 안 되는지 궁금할 때
- Linux ELF 바이너리에서도 Windows처럼 "Packer: UPX" 같은 표시가 나오는 도구가 있는지 찾고 있을 때
- CTF 환경에 GUI 도구 설치가 어려워서 커맨드라인만으로 패킹을 의심할 방법을 찾을 때

## 핵심 개념
패킹 탐지에 쓰는 도구들은 서로 역할이 다르며, 하나로 모든 것을 확인할 수 없다. Detect It Easy(DIE)는 알려진 패커 시그니처 데이터베이스를 갖고 있어 "이름표"를 즉시 붙여주는 데 강하고, PE-bear는 시그니처 데이터베이스는 없지만 섹션 헤더/임포트 테이블을 사람이 직접 뜯어볼 수 있게 해주는 데 강하다. 즉 DIE로 1차 스크리닝을 하고, DIE가 확신하지 못하거나(Unknown) 더 자세히 봐야 할 때 PE-bear로 넘어가는 흐름이 자연스럽다. Linux ELF 쪽은 애초에 UPX 외에는 GUI 패커 탐지 생태계가 Windows만큼 발달하지 않아서, `strings`/`readelf`/`file` 같은 표준 binutils 도구와 `checksec`(원래 목적은 RELRO/Canary/NX/PIE 같은 보호 기법 확인이지만 패킹 의심 시 함께 확인하는 것이 관행)을 조합해서 판단한다.

## 화면/코드에서 보이는 징후
| 도구 | 대상 포맷 | 주 용도 | 패커 시그니처 DB | 엔트로피 표시 | 설치/실행 방식 |
|---|---|---|---|---|---|
| Detect It Easy(DIE) | PE, ELF, Mach-O | 패커/컴파일러 자동 판별 | 있음(수천 종) | 있음(섹션별 그래프) | GUI, Windows/Linux 모두 존재 |
| PE-bear | PE 전용 | 헤더/섹션/임포트 수동 분석 | 없음(사람이 직접 판단) | 있음(Section Headers 열) | GUI, Windows 전용(Wine으로 Linux 실행 가능) |
| checksec | ELF 전용 | RELRO/Canary/NX/PIE 등 보호 기법 확인 | 없음 | 없음 | CLI, Linux |
| strings | 모든 포맷 | 문자열 기반 매직 바이트/안내문 확인 | 없음(사람이 판단) | 없음 | CLI, binutils 기본 포함 |
| readelf / objdump | ELF 전용 | 섹션 이름/헤더 구조 확인 | 없음 | 없음(수동 계산 필요) | CLI, binutils 기본 포함 |
| upx -l | UPX로 패킹된 파일만 | UPX 여부/압축률 확정 | UPX 전용 | 없음 | CLI |

## 가장 먼저 할 것
Windows PE라면 DIE부터 드래그해서 상단 결과란을 본다. Linux ELF라면 먼저 `file sample`로 포맷을 확인한 뒤 `strings sample | grep -i upx`와 `readelf -S sample`(섹션 이름 목록)을 실행한다.

## 단계별 절차
**1) 포맷 확인**: `file sample`로 PE인지 ELF인지 확인한다.
**2) 1차 스크리닝(PE)**: DIE에 드래그해 패커/프로텍터/컴파일러 이름과 엔트로피를 확인한다.
**3) 세부 구조 확인(PE)**: DIE 결과가 애매하면 PE-bear로 섹션 이름, raw size vs virtual size 차이, 임포트 개수를 직접 확인한다(REV-0229 참고).
**4) 1차 스크리닝(ELF)**: `strings sample | grep -i upx`, `readelf -S sample`로 섹션 이름을 확인한다.
**5) 보호 기법 확인(ELF)**: `checksec --file=sample`로 RELRO/Canary/NX/PIE를 확인한다. 이 정보 자체는 패킹 여부를 알려주지 않지만, "PIE인데 임포트가 극단적으로 적다"처럼 다른 패킹 징후(REV-0229)와 조합해서 판단하는 데 쓰인다.
**6) 확정**: UPX로 의심되면 `upx -l sample`로 확정한다.

## 명령어/단축키
```bash
file sample
strings sample | grep -i upx
readelf -S sample
checksec --file=sample
upx -l sample
```
- DIE/PE-bear는 GUI이므로 파일을 드래그하거나 `File → Open`으로 연다.

## 출력 해석
- DIE 결과란이 `Packer: UPX(4.2.4)`처럼 구체적 버전까지 나오면 신뢰도가 높다. `Nothing found`가 뜨면 알려진 시그니처가 없다는 뜻이지 "패킹이 아니다"는 뜻은 아니다(REV-0224 참고).
- `checksec`이 `RELRO: No` 등 보호 기법 미적용을 다수 보여준다고 해서 그 자체가 패킹의 증거는 아니다. 다만 오래된 CTF 문제나 커스텀 로더 바이너리는 보호 기법과 패킹 여부가 함께 허술한 경우가 실무적으로 흔하다는 정도의 참고 신호일 뿐이다.
- `readelf -S`에서 섹션 이름이 표준(`.text`, `.data`, `.bss`)과 다르거나 섹션 개수가 비정상적으로 적으면 커스텀 로더/패커 가능성을 의심한다.

## 흔한 실수
- DIE 결과 하나만 보고 "패킹 아님"으로 단정하는 것 — 시그니처 DB에 없는 커스텀 패커는 놓칠 수 있다.
- `checksec`을 패커 탐지 전용 도구로 오해하는 것 — `checksec`은 보호 기법(RELRO/Canary/NX/PIE) 확인 도구이며 패커 시그니처 DB가 없다(REV-0096, REV-0295 참고).
- PE-bear로 ELF 파일을 열려고 시도하는 것 — PE-bear는 PE 포맷 전용이다.
- Linux에도 DIE가 있다는 사실을 몰라서 매번 Windows로 파일을 옮겨 확인하는 것 — DIE는 Linux 빌드도 공식 배포된다.

## 막혔을 때 다음 체크
- 어떤 패커 이름이 나왔는데 처음 본다면 → REV-0931 흔한 패커 시그니처 빠른 참조표.
- DIE가 아무것도 못 찾았는데 여전히 의심된다면 → REV-0934 Entropy 값 해석 기준으로 섹션별 수치를 직접 확인한다.
- `checksec` 결과 자체를 더 깊이 읽는 법이 필요하면 → REV-0096 checksec 결과 읽는 법.

## 미니 예제
```text
$ file chall
chall: ELF 64-bit LSB pie executable, x86-64, ...

$ strings chall | grep -i upx
UPX!

$ readelf -S chall | grep UPX
  [ 1] UPX0              NOBITS
  [ 2] UPX1              PROGBITS

$ upx -l chall
     18432 <-      9216   50.00%   linux/amd64   chall
```
`strings`와 `readelf` 조합만으로 GUI 도구 없이도 Linux 환경에서 UPX 패킹을 확정할 수 있다.

## 관련 글
- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0225 — UPX인지 확인하는 법
- REV-0096 — checksec 결과 읽는 법
- REV-0931 — 흔한 패커 시그니처 빠른 참조표(UPX/ASPack/PECompact 등)
- REV-0934 — Entropy 값 해석 기준 빠른 참조 (예정)

## 출처/검증
- Detect It Easy와 PE-bear의 기능 범위는 각 프로젝트 공식 저장소(github.com/horsicq/Detect-It-Easy, github.com/hasherezade/pe-bear) 설명을 기준으로 정리했다(2026-09-09 검증).
- `checksec`, `readelf`, `strings`의 옵션과 출력 형식은 GNU binutils 및 `checksec.sh`(slimm609/checksec.sh) 공식 문서를 기준으로 확인했다.
- 도구별 버전에 따라 옵션명과 출력 형식이 달라질 수 있으므로, 실제 설치된 버전에서 `--help`로 재확인하는 것을 권장한다.
