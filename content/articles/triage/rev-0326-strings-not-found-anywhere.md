---
id: REV-0326
title: "어느 도구도 문자열을 못 찾을 때 확인할 것"
slug: "rev-0326-strings-not-found-anywhere"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [strings, IDA, Ghidra, binwalk, "Detect It Easy"]
keywords: ["strings 안 나옴", "문자열 못 찾음", "IDA strings 창 비어있음", "UTF-16 문자열", "패킹된 문자열"]
aliases: ["strings 명령이 아무것도 안 보여줌", "IDA Shift+F12 결과 없음", "문자열이 하나도 없는 바이너리", "문자열 검색 실패"]
symptom_keywords: ["strings 명령 출력이 텅 비어있음", "IDA Strings 창에 기대한 문자열이 없음", "분명 printf를 쓰는데 문자열이 안 보임", "문자열이 이상한 문자로만 나옴"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`strings` 명령이나 IDA/Ghidra의 Strings 창에 기대한 문자열이 하나도 안 나온다면 바이너리에 정말로 문자열이 없는 것이 아니라, UTF-16 인코딩, 문자열 자체 암호화, 패킹, 짧은 최소 길이 필터 중 하나 이상에 걸려 있을 가능성이 매우 높으므로 옵션을 바꿔가며 재확인하는 것이 우선이다.

## 언제 검색해야 하나
- `strings ./chall` 실행 결과가 텅 비어 있거나 관련 없는 잡음만 나올 때
- IDA Shift+F12(Strings 창)에 프로그램이 분명히 출력할 법한 메시지(`Correct!`, `Wrong password` 등)가 안 보일 때
- Windows PE인데 `strings`로는 아무것도 안 나오지만 프로그램 실행 시 메시지박스에 텍스트가 정상적으로 뜰 때
- 파일 크기가 꽤 큰데도 사람이 읽을 수 있는 문자열이 거의 없을 때

## 핵심 개념
증상(`strings`도 IDA Strings 창도 텅 비어 있는데 프로그램은 실제로 텍스트를 출력하는 상태)의 원인은 아래 여섯 가지 중 하나 이상이며, 확률이 높은 순서대로 점검한다.

1. **UTF-16(wide string) 인코딩**: Windows API의 `MessageBoxW`, `wprintf` 계열은 문자열을 2바이트 단위(UTF-16LE)로 저장한다. 기본 `strings` 명령은 1바이트 ASCII 연속만 찾으므로, 각 문자 사이에 `\x00`이 끼어 있는 UTF-16 문자열을 놓친다. IDA도 기본 스캔 옵션에 따라 유니코드 문자열을 놓칠 수 있다(REV-0612).
2. **문자열 암호화/난독화**: 문자열을 컴파일 시점에 XOR 등으로 인코딩해두고 런타임에 복호화해서 쓰는 패턴(REV-0233)이면, 정적 상태의 파일에는 원문이 아예 존재하지 않는다.
3. **패킹**: UPX 등으로 패킹된 바이너리는 실제 코드/데이터가 실행 시점에 압축 해제되어 메모리에 펼쳐진다. 파일 상태 그대로 `strings`를 돌리면 압축된 바이트만 보이므로 의미 있는 문자열이 나올 수 없다(REV-0224, REV-0226).
4. **strings 최소 길이 필터**: 기본 `strings`는 4바이트 이상 연속된 출력 가능 문자만 문자열로 인식한다. 짧은 문자열(2~3글자)은 기본 옵션으로 아예 걸러진다.
5. **로케일/코드페이지 문제**: 한글(EUC-KR, CP949) 등 비UTF-8/ASCII 인코딩 문자열은 기본 `strings`가 바이트 나열로만 취급해 깨진 문자로 보이거나 필터링될 수 있다.
6. **리소스 섹션/오버레이에 위치**: PE의 `.rsrc`(대화상자, 메뉴 리소스) 안에 문자열이 있거나, 파일 끝의 오버레이 영역에 별도로 붙어 있는 경우 도구의 기본 스캔 범위를 벗어날 수 있다.

## 화면/코드에서 보이는 징후
`strings ./chall` 명령의 출력이 비어 있거나, 나오더라도 프로그램 로직과 무관한 라이브러리 잡음 문자열만 보인다. IDA/Ghidra의 문자열 목록 창도 마찬가지로 텅 비어 있거나 극히 적다. 하지만 프로그램을 실제로 실행하면 화면에 분명히 텍스트 메시지가 출력된다 — 즉 문자열은 분명 어딘가에 존재하는데 도구가 못 찾고 있는 상태다.

## 가장 먼저 할 것
`strings -a -n 2 ./chall`로 최소 길이 필터부터 낮춰서 재시도하고, 곧바로 `strings -e l ./chall`(UTF-16LE)까지 시도한다. 이 두 옵션 조합만으로 원인의 상당수가 해결된다. 그래도 안 나오면 Detect It Easy로 패킹 여부부터 확인한다.

## 단계별 절차
1. `file ./chall`로 포맷/아키텍처/strip 여부 확인
2. `strings -a -n 2 ./chall`로 기본 필터를 낮춰 재시도
3. `strings -e l ./chall`, `strings -e b ./chall`로 UTF-16 인코딩 재시도 — IDA는 Strings 창(Shift+F12) 우클릭 → Setup에서 `Unicode C-style` 옵션이 켜져 있는지 함께 확인(REV-0612)
4. Detect It Easy로 패킹 여부 확인, 패킹되어 있으면 `upx -d`(또는 해당 패커의 언패킹 절차, REV-0225/0226) 후 2~3번 반복
5. 그래도 안 나오면 `binwalk ./chall`로 임베디드 리소스/오버레이 존재 여부 확인
6. 전부 실패하면 문자열 암호화(REV-0233)를 의심하고, GDB/x64dbg로 메시지를 출력하는 시점에 브레이크포인트를 걸어 레지스터/메모리에서 복호화된 문자열을 직접 관찰하는 동적 분석으로 전환(REV-0241)

## 명령어/단축키
```bash
file ./chall
strings -a -n 2 ./chall
strings -e l ./chall
strings -e b ./chall
binwalk ./chall
upx -d ./chall -o ./chall_unpacked
```

## 출력 해석
- `strings -e l`로 갑자기 의미 있는 문자열이 쏟아지면 UTF-16LE 인코딩이 원인이었다는 뜻이다 — Windows GUI 프로그램에서 매우 흔하다.
- `strings` 옵션을 다 바꿔봐도 여전히 아무것도 안 나오는데 DIE에서 패커가 확인되면, 언패킹이 선행되어야 한다는 뜻이다.
- 언패킹 후에도 안 나오면 문자열 자체가 코드로 암호화되어 있다는 뜻이므로, 이제는 정적 분석이 아니라 동적 분석으로 접근 방법을 바꿔야 한다.

## 흔한 실수
- `strings` 결과가 비었다고 곧바로 "이 바이너리는 문자열이 없다"고 단정하고 분석을 포기하는 것.
- strip된 바이너리라서 문자열이 안 보인다고 착각하는 것 — strip은 심볼 테이블 제거이지 문자열(.rodata 등 데이터) 제거와는 무관하다.
- UTF-16 옵션을 시도하지 않고 바로 "암호화됐다"고 결론 내리는 것 — 실제로는 인코딩 문제인 경우가 훨씬 흔하다.
- 패킹된 원본 파일에 계속 `strings`를 돌리며 옵션만 바꾸는 것 — 언패킹이 선행되지 않으면 어떤 옵션을 써도 의미 있는 결과가 안 나온다.

## 막혔을 때 다음 체크
- UTF-16 문자열이 IDA에서 계속 안 잡힌다 → REV-0612 UTF-16 문자열이 IDA Strings에 안 잡힐 때
- 문자열 난독화가 의심된다 → REV-0233 문자열 난독화가 보일 때
- 패킹 여부 판단 자체가 헷갈린다 → REV-0224 패킹된 바이너리인지 의심하는 기준, REV-0228 Entropy가 높은 Section의 의미
- 문자열은 찾았는데 어디서 쓰이는지 추적이 안 된다 → REV-0008 성공/실패 문자열에서 역참조 따라가는 방법

## 미니 예제
```bash
$ strings ./chall.exe | head
(아무 것도 안 나옴)

$ strings -e l ./chall.exe | head
Enter password:
Wrong password!
Correct! Here is your flag.
```
기본 `strings`로는 아무것도 안 나왔지만, `-e l`(리틀엔디안 UTF-16) 옵션을 주자 프로그램의 핵심 메시지가 그대로 드러났다. 이는 이 프로그램이 `MessageBoxW`나 `wprintf` 계열로 유니코드 문자열을 다룬다는 뜻이며, IDA에서도 같은 이유로 Strings 창 설정에 Unicode 타입을 추가해야 한다는 신호다.

## 관련 글
- REV-0612 — UTF-16 문자열이 IDA Strings에 안 잡힐 때
- REV-0233 — 문자열 난독화가 보일 때
- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0228 — Entropy가 높은 Section의 의미
- REV-0008 — 성공/실패 문자열에서 역참조 따라가는 방법

## 출처/검증
- GNU binutils `strings` 명령의 `-e`(인코딩), `-n`(최소 길이) 옵션: GNU binutils 공식 매뉴얼(`man strings`) 기준.
- Windows API의 `MessageBoxW`/`wprintf` 계열이 UTF-16LE로 문자열을 저장하는 것: Microsoft 공식 문서(Unicode and Character Sets) 기준 (2026-09-09 검증).
