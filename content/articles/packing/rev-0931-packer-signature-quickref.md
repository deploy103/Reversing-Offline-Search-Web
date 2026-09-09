---
id: REV-0931
title: "흔한 패커 시그니처 빠른 참조표(UPX/ASPack/PECompact 등)"
slug: "rev-0931-packer-signature-quickref"
category: "packing"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: ["Detect It Easy"]
keywords: ["패커 시그니처", "UPX", "ASPack", "PECompact", "FSG", "MEW", "Petite", "packer signature", "섹션 이름 패커", "패커 목록"]
aliases: ["패커 종류 표", "패커 시그니처 목록", "패커 이름 정리", "이 섹션 이름이 무슨 패커야"]
symptom_keywords: ["섹션 이름이 낯섦", "die에서 패커 이름 뜸", "aspack이라고 뜸", "pecompact라고 뜸", "fsg라고 뜸", "이 패커 처음 들어봄"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Detect It Easy가 표시하는 패커 이름이나 섹션 헤더에 보이는 낯선 이름(`.aspack`, `PECompact2`, `FSG!` 등)만 봐도 어떤 패커인지 즉시 감을 잡을 수 있도록, 흔히 등장하는 PE 패커들의 대표 시그니처를 한 표로 정리한다.

## 언제 검색해야 하나
- Detect It Easy(DIE) 결과란에 `UPX`가 아닌 낯선 패커 이름이 떴을 때, 그 이름이 뭘 의미하는지 빠르게 확인하고 싶을 때
- IDA/PE-bear에서 섹션 이름이 `.text`/`.data`가 아니라 `.aspack`, `.petite`, `PEC2` 같은 이상한 이름으로 보일 때
- CTF 문제 설명이나 writeup에 패커 이름만 언급되어 있는데 그게 UPX처럼 자동 언패킹 도구가 있는 종류인지 궁금할 때
- 여러 패커 이름을 한 번에 비교해서 "이 문제에서 어떤 패커가 가장 자주 나오는지" 감을 잡고 싶을 때

## 핵심 개념
UPX 외에도 Windows PE 실행 파일 압축에 흔히 쓰이는 패커가 여러 개 있다. UPX와 마찬가지로 대부분 원본 섹션을 압축된 형태로 저장하고, 실행 시 압축을 풀어주는 스텁 코드를 앞에 붙이는 구조는 동일하다. 다만 패커마다 스텁이 만드는 섹션 이름, 파일에 남기는 매직 문자열, 압축 알고리즘이 다르기 때문에 이를 알아두면 정적 분석 단계에서 시간을 크게 아낄 수 있다. UPX처럼 공식 도구로 자동 언패킹이 가능한 것도 있고(ASPack, FSG, Petite 일부 버전), 공식 언패커가 없어서 REV-0227의 수동 언패킹 개념이 필요한 것도 있다.

## 화면/코드에서 보이는 징후
아래 표는 대표적인 오픈소스/프리웨어 계열 PE 패커의 흔적을 정리한 것이다.

| 패커 | 대표 섹션 이름 | strings에 남는 흔적 | DIE 표시 예 | 자동 언패커 |
|---|---|---|---|---|
| UPX | `UPX0`, `UPX1`, `UPX2` | `UPX!`, `$Info: This file is packed with the UPX` | `Packer: UPX(4.2.4)` | `upx -d` (REV-0226) |
| ASPack | `.aspack`, `.adata` | `ASPack` 문자열, 경우에 따라 `.aspack` 자체 | `Packer: ASPack(2.12)` | 공식 ASPack 언패커 존재(구버전) |
| PECompact | `PEC2`, `PECompact2` | `PECompact2` 문자열 | `Packer: PECompact(2.x)` | 플러그인 기반, 자동화 난이도 있음 |
| FSG (Fast Small Good) | 섹션 이름이 거의 없거나 랜덤 | `FSG!` 매직 바이트 | `Packer: FSG(2.0)` | 공식 언패커 있음(구버전 한정) |
| MEW | 섹션이 하나로 병합됨 | `MEW` 문자열이 거의 안 남음(매우 압축률 지향) | `Packer: MEW` | 전용 스크립트 필요 |
| Petite | `.petite` | `Petite` 문자열 | `Packer: Petite(2.x)` | 없음, 수동 언패킹 |
| NSPack | `.nsp0`, `.nsp1` | `NSPack` 문자열 | `Packer: NSPack` | 없음, 수동 언패킹 |
| Themida/WinLicense | 랜덤/난독화된 이름, 다수 섹션 | 거의 없음(강한 안티 분석) | `Protector: Themida/WinLicense` | 없음(REV-0935 참고) |
| VMProtect | 랜덤/`.vmp0`, `.vmp1` | 거의 없음 | `Protector: VMProtect` | 없음(REV-0935 참고) |

## 가장 먼저 할 것
DIE에 파일을 드래그해 상단 결과란의 패커/프로텍터 이름부터 확인한다. UPX면 REV-0225/REV-0226으로, 표에 있는 다른 이름이면 이 표에서 자동 언패커 여부를 먼저 확인하고, 표에 없는 이름이면 해당 패커 이름 그대로 검색해 공식 언패커가 있는지 찾아본다.

## 단계별 절차
**1) DIE로 1차 판별**: 파일을 열어 상단 결과란의 이름과 버전을 확인한다.
**2) 위 표와 대조**: 표에 있는 이름이면 자동 언패커 열을 확인한다.
**3) 섹션 이름으로 교차 확인**: DIE가 "Unknown"이라도 섹션 이름이 표의 패턴과 일치하면 해당 패커일 가능성이 높다.
**4) strings로 매직 문자열 재확인**: `strings sample.exe | grep -iE "aspack|pecompact|fsg|mew|petite|nspack"`로 문자열 흔적을 찾는다.
**5) 결론에 따라 분기**: 자동 언패커가 있으면 그것부터 시도하고, 없으면 REV-0227의 수동 언패킹 개념 또는 REV-0241의 동적 분석 전환을 검토한다.

## 명령어/단축키
```bash
strings sample.exe | grep -iE "upx|aspack|pecompact|fsg|mew|petite|nspack"
```
- DIE: 파일 드래그 → 상단 결과란(패커/프로텍터 이름, 버전)
- PE-bear/IDA: Section Headers/Segments에서 섹션 이름 확인

## 출력 해석
- DIE가 `Packer:`로 시작하면 압축형(자동 언패킹 가능성 있음), `Protector:`로 시작하면 보호형(코드 실행 방해/가상화 포함, REV-0935 대상)임을 구분하는 신호로 볼 수 있다.
- 섹션 이름이 표에 없는 완전히 낯선 이름이라면 커스텀 패커이거나 섹션 이름을 일부러 지운 경우이므로, 엔트로피(REV-0934)와 entry point 코드 패턴을 함께 봐야 한다.

## 흔한 실수
- 섹션 이름만 보고 패커를 단정하는 것 — 일부 패커/CTF 문제는 섹션 이름을 임의로 바꾸거나 지워서 자동 탐지를 회피한다.
- 오래된 패커(FSG, MEW 등)의 공식 언패퍼가 최신 OS/아키텍처에서 그대로 동작할 것이라 가정하는 것 — 상당수가 32비트 전용이며 유지보수가 끊긴 도구다.
- `Packer:`와 `Protector:` 구분 없이 모두 "UPX처럼 몇 초 만에 풀린다"고 기대하는 것.

## 막혔을 때 다음 체크
- 표에 없는 완전히 낯선 패커명이 나온다면 → REV-0224로 돌아가 엔트로피/entry point 패턴을 재확인한다.
- 이름이 `Protector:`로 뜬다면 → REV-0935에서 상용 프로텍터 목록과 대응 방향을 확인한다.
- 자동 언패커가 없는 패커라면 → REV-0227 수동 언패킹 개념 또는 REV-0241 동적 분석 전환을 확인한다.

## 미니 예제
```text
DIE 결과: Packer: ASPack(2.12) [-]
섹션: .aspack, .adata

$ strings sample.exe | grep -i aspack
ASPack

-> ASPack로 확인. 공식 ASPack 자체 언패킹 도구 또는 x64dbg + OllyDbg 스크립트로
   OEP 탐색 후 REV-0227 절차로 진행.
```

## 관련 글
- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0225 — UPX인지 확인하는 법
- REV-0226 — UPX 기본 언패킹
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- REV-0934 — Entropy 값 해석 기준 빠른 참조
- REV-0935 — VMProtect/Themida 등 상용 프로텍터 존재만 알아두는 참조표

## 출처/검증
- UPX/ASPack/PECompact/FSG/MEW/Petite/NSPack의 섹션 명명 규칙과 매직 문자열은 각 프로젝트 공식 문서 또는 저장소(예: github.com/upx/upx)와 다수의 공개 리버싱 교육 자료에서 공통적으로 확인되는 내용을 정리한 것이다(2026-09-09 검증).
- Detect It Easy의 패커/프로텍터 시그니처 표기 방식(`Packer:` vs `Protector:`)은 프로젝트 공식 저장소(github.com/horsicq/Detect-It-Easy)의 시그니처 데이터베이스 구조를 참고했다.
- 오래된 패커(FSG, MEW, NSPack 등)는 유지보수가 끊긴 경우가 많아 버전별 정확한 동작은 실제 샘플에서 재검증이 필요하다.
