---
id: REV-0791
title: "변수 이름이 계속 sub_ 형태로만 나올 때"
slug: "rev-0791-sub-prefix-unnamed-function"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["sub_ 이름", "IDA sub_ prefix", "FUN_ Ghidra", "함수 이름 자동 생성", "stripped binary 함수 이름", "정적 링킹 함수 이름 없음"]
aliases: ["sub_401000만 보임", "FUN_00401000만 보임", "함수 이름이 다 sub_로 시작함", "Ghidra FUN_ 이름만 나옴"]
symptom_keywords: ["Functions 창에 sub_밖에 없음", "Ghidra에서 FUN_으로만 나옴", "의미있는 함수 이름이 하나도 없음", "import된 함수 이름도 안 보임", "printf malloc 이름이 안 보임"]
source_ids: ["SRC-HEXRAYS-DOCS", "SRC-GHIDRA-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`sub_` 이름은 IDA가 특정 주소에 함수가 있다는 것 자체는 인식했지만 그 이름을 알려줄 근거(심볼 테이블/시그니처 매칭)가 하나도 없을 때 자동으로 붙이는 placeholder이며, 대부분 (1) 바이너리가 strip되었거나 (2) 정적 링킹된 라이브러리 코드라서 FLIRT 시그니처가 안 맞거나 (3) 애초에 심볼 없이 컴파일된 사용자 코드이기 때문이다 — 이 셋을 구분한 뒤 각각 다른 해결책을 적용해야 한다.

## 언제 검색해야 하나
- Functions 창(Ctrl+P)을 열었는데 이름 있는 함수가 거의 없고 전부 `sub_401000`, `sub_401230` 같은 이름뿐일 때
- Ghidra에서도 마찬가지로 `FUN_00401000`처럼 전부 자동 생성된 이름만 보일 때
- `printf`, `malloc`, `strcpy`처럼 당연히 있어야 할 라이브러리 함수 이름도 안 보일 때
- Imports 탭에도 이름이 거의 없을 때(정적 링킹 의심)

## 핵심 개념
IDA/Ghidra는 함수의 "존재"와 "이름"을 서로 다른 정보 출처에서 얻는다. 함수가 어디서 시작하고 끝나는지는 디스어셈블 엔진의 코드 흐름 분석만으로도 알아낼 수 있지만, 그 함수가 무엇을 하는 함수인지 알려주는 **이름**은 다음 세 출처 중 하나에서 와야 한다.

1. **심볼 테이블(symbol table)** — 컴파일러/링커가 남긴 이름 정보(ELF의 `.symtab`/`.dynsym`, PE의 PDB나 export/import 테이블). `strip` 명령이나 배포 빌드에서 이 정보가 통째로 제거되면 IDA는 이름을 알아낼 방법이 없어 주소 기반 `sub_<주소>`를 자동 생성한다.
2. **동적 링킹 정보(import table)** — `printf`, `malloc`처럼 공유 라이브러리에서 가져오는 함수는 심볼 테이블이 없어도 Import 테이블에 이름이 남아 보통 보인다. 그런데 바이너리가 **정적 링킹**되면 이 함수들의 코드 자체가 바이너리 안에 복사되어 들어가고 Import 테이블에는 아무 흔적도 남지 않는다. 이 경우 `printf`도 그냥 `sub_...`로 보인다.
3. **FLIRT/FunctionID 시그니처 매칭** — 정적 링킹된 라이브러리 코드라도 IDA의 FLIRT나 Ghidra의 FunctionID는 바이트 패턴을 보고 "이건 glibc의 malloc과 일치한다"는 식으로 이름을 붙여줄 수 있다. 다만 컴파일러/버전/최적화 옵션이 시그니처 데이터베이스와 다르면 매칭이 실패해 역시 `sub_...`로 남는다(REV-0804 참고).

`sub_` 이름 자체는 "함수가 없다"는 뜻이 아니라 "이름을 알아낼 근거가 하나도 안 통했다"는 뜻이다. 원인마다 대응이 다르므로 순서대로 확인해야 한다.

## 화면/코드에서 보이는 징후
- Functions 창 대부분이 `sub_숫자` 또는 `FUN_숫자`
- `main`, `printf`, `strcpy`처럼 있어야 할 이름이 안 보임
- Imports 탭이 텅 비었거나 항목이 매우 적음
- `file` 명령으로 확인 시 "statically linked" 또는 "stripped" 표시

## 가장 먼저 할 것
분석 대상 바이너리를 셸에서 `file <파일명>`으로 먼저 확인한다. 정적/동적 링킹 여부와 strip 여부가 이 문제의 원인을 절반 이상 알려준다.

## 단계별 절차

**1) stripped 여부 확인**
```bash
file chall
readelf -S chall | grep -i symtab
nm chall
```
`.symtab` 섹션이 없거나 `nm`이 `no symbols`를 출력하면 strip된 것이다. 원본 심볼을 복구할 방법은 없으므로(별도 디버그 정보가 없다면), 이후 절차는 수동 분석/FLIRT/문자열 단서 활용으로 넘어간다.

**2) 정적 링킹 여부 확인**
```bash
ldd chall          # "not a dynamic executable"면 정적 링킹
```
정적 링킹이 맞다면 REV-0646과 REV-0804를 이어서 확인한다.

**3) FLIRT/FunctionID 적용**
IDA에서는 File → Load file → FLIRT signature file로 컴파일러/라이브러리에 맞는 `.sig`를 적용한다. Ghidra에서는 Analysis → Auto Analyze 옵션에서 Function ID 분석기가 켜져 있는지 확인하고, 필요하면 관련 FunctionID 데이터베이스를 추가한다.

**4) 그래도 안 잡히면 수동 분석**
문자열 xref(REV-0163), Import/외부 호출 패턴, 상수(REV-0165), 호출 그래프(REV-0166)를 이용해 함수의 역할을 추정하고 직접 이름을 붙인다(REV-0147, N 단축키). 특히 `main`은 `_start`에서 `__libc_start_main` 호출 인자로 넘어가는 첫 번째 함수 포인터로 특정할 수 있다.

**5) Functions 창이 아예 텅 비어 있다면 다른 문제**
sub_ 이름이 많이 보이는 게 아니라 함수 자체가 거의 안 잡혀 있다면 이는 이름 문제가 아니라 코드 인식 실패이므로 REV-0772를 먼저 본다.

## 명령어/단축키
```bash
file <binary>
readelf -S <binary> | grep -i symtab
readelf -d <binary>
ldd <binary>
nm <binary>
```
- IDA: File → Load file → FLIRT signature file
- IDA: 함수 위에서 `N` — 이름 직접 변경(REV-0147)
- Ghidra: Analysis → Auto Analyze → Function ID 옵션 확인

## 출력 해석
- `nm <binary>`가 `no symbols`를 출력하면 strip된 것이 확정이다.
- `ldd`가 "not a dynamic executable"이라고 하면 정적 링킹이며, 이 경우 Import 탭이 비어 있는 것은 정상이다.
- FLIRT 적용 후 Output window에 매칭 개수가 뜨는데, 0에 가깝다면 시그니처 버전이 안 맞는 것이다(REV-0804).

## 흔한 실수
- Import 탭이 비어 있으니 "분석이 잘못됐다"고 착각하는 것 — 정적 링킹이면 원래 비어 있는 게 정상이다.
- strip된 바이너리에서 원본 이름을 어떻게든 복구하려고 시간을 낭비하는 것 — 심볼 테이블이 없으면 원래 이름은 알 수 없고, 기능 기반으로 새로 이름 붙이는 것이 유일한 방법이다.
- FLIRT를 한 번 적용해보고 안 되면 포기하는 것 — 컴파일러 버전별로 여러 시그니처가 있으므로 후보를 더 시도해봐야 한다.
- sub_ 함수를 전부 열어보려는 것 — main에서 시작하는 호출 그래프(REV-0166)를 따라가며 실제로 문제와 관련된 함수만 추려서 봐야 시간을 아낀다.

## 막혔을 때 다음 체크
- Functions 창 자체가 텅 비어 있다면 → REV-0772
- 정적 링킹된 바이너리 전반의 분석 전략이 필요하면 → REV-0646
- FLIRT 시그니처를 적용했는데도 매칭이 안 된다면 → REV-0804
- 이름은 있는데 그 이름을 믿을 수 없는 상황(난독화)이라면 → REV-0801
- 심볼과 stripped의 기본 개념 자체가 헷갈리면 → REV-0038

## 미니 예제
`file chall` 결과가 `ELF 64-bit LSB executable, x86-64, statically linked, stripped`라고 나왔다고 하자. Functions 창에는 `sub_401000`부터 `sub_40C000`까지 수백 개가 있고 이름 있는 함수는 하나도 없다. 이 경우 `main` 자체도 이름이 없으므로, 먼저 `_start`(엔트리 포인트)로 가서 `__libc_start_main` 호출 직전에 인자로 들어가는 함수 포인터를 찾아 그것을 `main`으로 이름 붙인다. 그다음 IDA의 FLIRT나 Ghidra의 FunctionID를 적용해 libc 내부 함수들에 자동으로 이름이 붙는지 확인하고, 매칭 안 된 나머지는 REV-0646의 절차대로 문자열/상수 단서로 좁혀나간다.

## 관련 글
- REV-0772 — IDA에서 함수가 아예 하나도 안 잡힐 때
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0804 — FLIRT 시그니처가 안 맞아서 라이브러리 함수를 놓칠 때
- REV-0801 — 난독화된 이름 때문에 심볼을 못 믿을 때
- REV-0147 — IDA 함수 변수 이름 N으로 바꾸기
- REV-0163 — 문자열에서 검증 함수로 이동하는 정적 분석
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이

## 출처/검증
- FLIRT(Fast Library Identification and Recognition Technology)의 시그니처 매칭 개념은 Hex-Rays 공식 문서("FLIRT technology") 기준.
- Ghidra의 Function ID 분석기 개념은 Ghidra 공식 문서(Analyzers 관련 챕터) 기준.
- ELF `.symtab`/`.dynsym`, strip, 정적/동적 링킹 구분은 System V ABI 문서 및 binutils(`readelf`, `nm`, `ldd`, `file`) 공식 매뉴얼 기준.
- 이 글은 2026-09-09 기준으로 작성되었다.
