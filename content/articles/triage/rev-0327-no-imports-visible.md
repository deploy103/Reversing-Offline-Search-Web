---
id: REV-0327
title: "Import 함수가 하나도 안 보일 때 원인 좁히기"
slug: "rev-0327-no-imports-visible"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, readelf, "PE-bear", "Detect It Easy"]
keywords: ["Import가 없음", "IAT 비어있음", "정적 링킹 import", "API 해싱", "ordinal import"]
aliases: ["Imports 창이 텅 비어있음", "readelf dyn-syms 없음", "IAT가 없는 PE", "임포트 함수 하나도 안 보임"]
symptom_keywords: ["IDA Imports 탭이 비어있음", "readelf --dyn-syms 결과가 없음", "함수 이름 대신 숫자로 임포트됨", "동적 링킹인데 import가 하나도 없음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Import 목록이 텅 비어 보이는 이유는 크게 네 가지 — 정적 링킹이라 애초에 import 개념이 없거나, 패킹으로 원래 IAT가 지워졌거나, PE에서 이름 대신 ordinal 번호로만 임포트되어 있거나, 프로그램이 `GetProcAddress`/`dlsym`으로 런타임에 함수를 직접 찾는 API 해싱/동적 로딩 패턴을 쓰고 있는 것 — 이므로 이 순서대로 하나씩 소거하며 원인을 좁혀야 한다.

## 언제 검색해야 하나
- IDA/Ghidra의 Imports 탭 또는 PE-bear의 Import Table 뷰가 텅 비어 있을 때
- Linux ELF에서 `readelf --dyn-syms ./chall`을 실행했는데 아무것도 안 나오거나 매우 적을 때
- 분명 `printf`, `CreateFileA` 같은 표준 함수를 쓰는 것 같은데 Import 목록에서는 찾을 수 없을 때
- Import 목록에 이름 대신 숫자만 나열되어 있을 때(PE ordinal import)

## 핵심 개념
가능성이 높은 순서대로 원인을 점검한다.

1. **정적 링킹(static linking)**: 가장 흔한 원인이다. 정적 링킹된 바이너리는 필요한 라이브러리 코드를 실행 파일 안에 전부 박아 넣으므로 PLT/GOT나 IAT 자체가 존재하지 않는다. `file`/`checksec`/`readelf -d`로 먼저 확인해야 한다(REV-0646).
2. **패킹으로 IAT가 사라짐**: UPX 등으로 패킹된 PE는 원래의 Import Table이 압축 스텁 뒤로 숨겨지고, 파일 상태에서 보이는 Import는 언패킹 스텁이 필요로 하는 최소한(`LoadLibraryA`, `GetProcAddress` 정도)뿐인 경우가 많다(REV-0229).
3. **Ordinal-only import**: 함수 이름이 아니라 번호(ordinal)로만 임포트되어 있어서 "임포트가 없다"가 아니라 "이름이 안 보인다"로 착각하는 경우다(REV-0587). Imports 탭 자체는 비어있지 않고 항목은 있는데 이름이 `Ordinal#42`처럼 표시된다.
4. **API 해싱/수동 임포트(런타임 동적 로딩)**: 안티 분석 기법 중 하나로, 컴파일 시점에 IAT에 함수를 등록하지 않고 런타임에 `GetProcAddress`/`dlsym`으로 필요한 함수 포인터를 직접 계산해서 쓰는 패턴이다. 이 경우 정적 Import 목록에는 `kernel32.dll`의 `LoadLibraryA`, `GetProcAddress` 딱 두 개 정도만 보이고 나머지는 전혀 안 보인다.
5. **static-PIE**: `-static-pie`로 빌드된 ELF는 재배치를 위한 최소한의 `.dynamic` 섹션은 있지만 외부 라이브러리(`NEEDED`)는 없다 — 사실상 정적 링킹과 같은 원인이다(REV-0646).

## 화면/코드에서 보이는 징후
IDA/Ghidra를 열어 Imports 탭을 확인했는데 항목이 하나도 없거나 극히 일부만 보인다. Linux라면 `readelf -d ./chall`에 `NEEDED` 항목이 없거나 `readelf --dyn-syms`가 텅 비어있다. Windows PE라면 PE-bear의 Import Table에 DLL 목록 자체가 없거나, DLL은 있는데 함수 이름 대신 숫자(ordinal)만 나열된다. 그런데 프로그램을 실행하면 파일 입출력, 문자열 출력 등 표준 라이브러리 기능이 정상적으로 동작한다.

## 가장 먼저 할 것
`file ./chall`, `checksec`, `readelf -d ./chall`(PE는 PE-bear)로 정적/동적 링킹 여부부터 확인한다. 정적 링킹으로 확인되면 이 문서의 나머지 원인을 더 따질 필요 없이 바로 REV-0646(정적 링킹 ELF 분석) 절차로 전환한다.

## 단계별 절차
1. `file ./chall`, `checksec`, `readelf -d ./chall`(또는 PE는 PE-bear)로 정적/동적 링킹 여부 확인 — `readelf -d`가 `There is no dynamic section in this file`을 출력하면 정적 링킹 확정
2. 정적 링킹이면 REV-0646(정적 링킹 분석)으로 전환, strip 안 됐다면 `nm ./chall`(REV-0666)로 함수 이름을 직접 나열하고 이 문서의 나머지 단계는 건너뜀
3. 동적 링킹인데도 Import가 비었으면 Detect It Easy로 패킹 여부 확인
4. 패킹이면 언패킹(REV-0225, REV-0226)을 먼저 하고 그 결과물의 Import Table로 1번부터 재확인
5. 패킹이 아닌데 일부만 보이면 이름이 아니라 ordinal로 표시되는지 확인(REV-0587) — 이 경우 해당 DLL의 알려진 export ordinal 표와 대조해 실제 함수명을 찾는다
6. 그래도 설명이 안 되면 `LoadLibraryA`/`GetProcAddress`/`dlopen`/`dlsym`만 홀로 임포트되어 있는지 확인 — 있다면 API 해싱/수동 임포트를 의심하고, 코드 안에서 DLL 이름 문자열/해시 상수를 찾거나 x64dbg/GDB로 `GetProcAddress` 호출 시점에 브레이크포인트를 걸어 두 번째 인자(함수 이름 또는 해시)를 직접 관찰하는 동적 분석으로 전환

## 명령어/단축키
```bash
file ./chall
checksec --file=./chall
readelf -d ./chall
readelf --dyn-syms ./chall
nm ./chall | grep ' T '
```
IDA/Ghidra: Imports 탭에서 항목 수와 이름 표시 여부 확인. PE-bear: Import Table 뷰에서 DLL별 함수 목록 확인.

## 출력 해석
- `readelf -d`가 `There is no dynamic section in this file`을 출력하면 정적 링킹이 확정이다 — 더 이상 Import를 찾을 필요가 없다.
- Import 개수가 `LoadLibraryA`, `GetProcAddress` 단 2개뿐이면 거의 확실히 런타임 수동 임포트/API 해싱 패턴이다.
- Import 항목에 이름 대신 숫자만 있으면 그 DLL의 export 순서표를 별도로 구해야 실제 함수명을 알 수 있다.

## 흔한 실수
- 정적 링킹 여부를 확인하지 않고 "Import가 없다 = 이상한 안티 분석 기법이다"라고 성급히 결론짓는 것 — 실제로는 훨씬 흔한 정적 링킹인 경우가 많다.
- Ordinal import 상태를 "임포트가 아예 없다"고 오해하는 것 — 항목 개수와 이름 표시 여부를 구분해서 봐야 한다.
- 패킹된 상태 그대로 Import Table을 분석하며 "이 프로그램은 API를 거의 안 쓴다"고 잘못 결론 내리는 것 — 언패킹 전 스텁의 최소 Import만 보고 있는 것이다.
- API 해싱이 의심되는데 정적 분석만으로 끝까지 해시값을 원본 함수명으로 되돌리려 애쓰는 것 — 동적으로 `GetProcAddress` 호출 시점을 직접 관찰하는 것이 훨씬 빠르다.

## 막혔을 때 다음 체크
- 정적 링킹 분석 절차 자체가 궁금하다 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법, REV-0666 nm으로 정적 바이너리에서 원하는 심볼 찾기
- 패킹 여부 판단이 헷갈린다 → REV-0224 패킹된 바이너리인지 의심하는 기준, REV-0229 Import가 거의 없는 PE를 봤을 때
- Ordinal import를 이름으로 바꾸는 법이 궁금하다 → REV-0587 Ordinal 번호로 Import가 표시되어 함수명을 모를 때
- checksec 결과 자체 해석이 헷갈린다 → REV-0096 checksec 결과 읽는 법
- 문자열도 같이 안 보인다 → REV-0326 어느 도구도 문자열을 못 찾을 때 확인할 것

## 미니 예제
```text
$ file ./chall
chall: ELF 64-bit LSB executable, x86-64, ... statically linked, not stripped

$ readelf -d ./chall
readelf: Warning: no .dynamic section in this file
There is no dynamic section in this file.

$ nm ./chall | grep -E ' T (printf|malloc|main)$'
0000000000403c50 T printf
0000000000403ae0 T malloc
0000000000401a1d T main
```
`readelf -d`가 동적 섹션이 없다고 알려주는 순간 "Import가 없는 것이 당연하다"는 결론이 나온다. 이어서 `nm`으로 `printf`, `malloc` 같은 익숙한 함수 이름이 그대로 보이므로, 이 바이너리는 안티 분석 기법이 아니라 단순한 정적 링킹이었다는 것이 확정된다.

## 관련 글
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0666 — nm으로 정적 바이너리에서 원하는 심볼 찾기
- REV-0229 — Import가 거의 없는 PE를 봤을 때
- REV-0587 — Ordinal 번호로 Import가 표시되어 함수명을 모를 때
- REV-0096 — checksec 결과 읽는 법
- REV-0326 — 어느 도구도 문자열을 못 찾을 때 확인할 것

## 출처/검증
- ELF `.dynamic` 섹션 부재와 정적 링킹의 관계: System V ABI 및 ELF Specification 기준, 본 위키 REV-0646과 동일 출처.
- PE Import Address Table(IAT) 구조와 ordinal import: Microsoft 공식 PE/COFF Specification 기준.
- `GetProcAddress`/`dlsym`을 이용한 런타임 수동 임포트(API 해싱)는 일반적으로 알려진 안티 분석/언패킹 스텁 기법으로, 다수의 리버싱 교육 자료에서 공통적으로 다뤄지는 패턴 (2026-09-09 검증).
