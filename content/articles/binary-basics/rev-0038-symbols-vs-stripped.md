---
id: REV-0038
title: "심볼이 있는 바이너리와 Stripped 바이너리 차이"
slug: "rev-0038-symbols-vs-stripped"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["심볼", "symbol", "stripped", "strip", "디버그 심볼", "debug symbol", "PDB", "sub_ 함수 이름"]
aliases: ["stripped가 뭔가요", "sub_140001000이 뭔가요", "함수 이름이 다 sub_로 나와요", "pdb가 뭔가요"]
symptom_keywords: ["함수 이름이 다 sub_ 로만 나옴", "변수 이름이 다 v1 v2 a1으로만 나옴", "pdb 파일이 없어서 디버깅이 안됨", "strip 명령이 뭘 하는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
**심볼(symbol)** 은 컴파일러/링커가 만든 "주소 ↔ 함수명·변수명" 대응표이며, 이 표를 실행 파일에서 제거한 것을 **Stripped 바이너리**라 한다 — 심볼이 있으면 IDA/Ghidra가 `is_valid_password`처럼 원래 이름을 보여주지만, stripped 바이너리는 `sub_140001000`, `a1`, `v3`처럼 의미 없는 자동 생성 이름만 보여준다.

## 언제 검색해야 하나
- IDA/Ghidra에서 함수 이름이 전부 `sub_401000`, `sub_140002500` 형태의 주소 기반 이름으로만 나올 때
- 변수 이름이 전부 `a1`, `a2`, `v3`, `v4`처럼 순번만 붙어서 원래 의미를 전혀 알 수 없을 때
- Windows 바이너리 옆에 `.pdb` 파일이 있는지 없는지가 왜 중요한지 궁금할 때
- `strip` 명령어가 정확히 무엇을 하는지, 왜 배포용 바이너리에 이 명령을 쓰는지 궁금할 때
- CTF 문제 바이너리가 "분석하기 어렵게" 되어 있다고 느껴져서 이유를 알고 싶을 때

## 핵심 개념
컴파일 과정에서 컴파일러는 사람이 읽을 수 있는 이름(함수명, 전역 변수명, 타입명 등)과 그것이 최종적으로 배치되는 메모리 주소를 연결해주는 **심볼 테이블(symbol table)** 을 만든다. 이 표 덕분에 디버거는 "주소 0x401000에 브레이크포인트를 걸어라"가 아니라 "`main` 함수에 브레이크포인트를 걸어라"처럼 사람 친화적인 방식으로 동작할 수 있고, 디스어셈블러도 그 이름을 그대로 화면에 보여줄 수 있다.

문제는 이 심볼 정보가 파일 크기를 늘리고, 배포하는 소프트웨어의 내부 구조(함수 이름, 파일 경로, 때로는 개발자의 의도)를 노출한다는 점이다. 그래서 실제 배포되는 상용 소프트웨어나 악성코드, CTF 문제 바이너리는 이 정보를 의도적으로 제거하는 경우가 많다. 이 제거 과정을 **strip**이라 부르고, 그 결과물을 **stripped 바이너리**라 한다.

**심볼이 있을 때와 없을 때의 차이**를 IDA/Ghidra 화면 기준으로 보면:

| | 심볼 있음 (unstripped) | 심볼 없음 (stripped) |
|---|---|---|
| 함수 이름 | `check_password`, `main`, `xor_decrypt` | `sub_401000`, `sub_140002500` |
| 전역 변수 이름 | `g_secret_key`, `is_logged_in` | `dword_402010`, `unk_402020` |
| 지역 변수 이름 | (디버그 정보가 있으면) `password`, `i` | `v3`, `a1`, `result` (자동 생성) |
| 타입 정보 | 구조체/클래스 이름과 필드명 유지 | 대부분 소실, 오프셋만 남음(REV-0035 참고) |
| 함수 시그니처 | 정확한 인자 개수/타입 | 디스어셈블러가 호출 규약으로 추정(REV-0032 참고) |

**Linux(ELF)에서 심볼과 strip:**
```bash
gcc -g -o target src.c      # 디버그 심볼 포함 컴파일(-g)
strip target                 # 심볼 테이블 제거
nm target                    # 남아있는 심볼 목록 확인 (strip 후에는 거의 비어있음)
```
ELF는 크게 두 종류의 심볼 정보를 갖는다: 링크에 필요한 최소한의 **동적 심볼(dynamic symbol, `.dynsym`)** 은 공유 라이브러리 함수 호출(예: `printf`, `malloc`)을 위해 strip 후에도 대부분 남아있고, 개발/디버깅용 **정적 심볼(`.symtab`)** 은 strip으로 완전히 제거된다. 그래서 strip된 ELF라도 임포트된 라이브러리 함수 이름은 여전히 보이는 경우가 많다.

**Windows(PE)에서 심볼: PDB 파일.** Windows는 심볼 정보를 실행 파일(exe/dll) 안에 넣지 않고, 별도의 **PDB(Program Database) 파일**에 저장하는 방식을 표준으로 쓴다. PDB가 함께 배포되면 디버거/IDA가 자동으로 함수명, 변수명, 타입, 심지어 소스 줄 번호까지 연결해서 보여준다. 반대로 배포용 실행 파일은 PDB 없이 exe/dll만 배포하는 것이 일반적이라, 사실상 "기본값으로 stripped"인 상태로 유통되는 것과 비슷하다. 다만 Windows 표준 라이브러리 함수를 임포트하는 부분(Import Address Table)은 API 이름 자체가 실행 파일 안에 남아있어서 PDB 없이도 어떤 시스템 함수를 호출하는지는 알 수 있다(예: `CreateFileW`, `RegOpenKeyExA`).

**Stripped 바이너리를 분석할 때 잃는 것과 잃지 않는 것:**
- 잃는 것: 함수/변수의 **의미 있는 이름**, 정확한 **타입 정보**(특히 구조체 필드 이름), 소스 파일 경로와 줄 번호 매핑.
- 잃지 않는 것: **실제 코드 로직 자체**(명령어는 그대로 존재), 임포트된 외부 라이브러리 함수 이름(대부분의 경우), 문자열 리터럴(REV-0036 참고), 전체적인 제어 흐름 구조.

즉 strip은 "코드가 무엇을 하는지"를 감추는 게 아니라 "그 코드에 어떤 이름이 붙어 있었는지"를 감추는 것에 가깝다. 그래서 stripped 바이너리도 로직을 끝까지 따라가면 분석 자체는 가능하다 — 다만 훨씬 느리고 힘들다.

## 화면/코드에서 보이는 징후
- IDA의 함수 목록(Functions 창)에 `main`, `sub_401000`, `sub_401050`처럼 일부만 알려진 이름(`main`, 임포트 함수)이고 나머지는 전부 주소 기반 자동 이름이다.
- Ghidra의 Symbol Tree에서 `FUN_00401000` 형태(Ghidra의 자동 이름 규칙)가 대량으로 나열된다.
- `file` 명령으로 확인했을 때 ELF 파일 설명에 `not stripped` 또는 `stripped`라는 문구가 직접 나오기도 한다.
- PE 실행 파일과 같은 폴더에 `.pdb` 파일이 있는지 없는지로 심볼 제공 여부를 짐작할 수 있다.
- `checksec` 같은 도구가 심볼 관련 정보를 함께 보여주는 경우도 있다.

## 가장 먼저 할 것
분석을 시작하기 전에 대상 바이너리가 stripped인지 아닌지부터 확인한다. Linux는 `file target`으로, Windows는 실행 파일 옆에 `.pdb`가 있는지로 빠르게 판단할 수 있다. Stripped라면 처음부터 "이름 없이 로직만으로 분석한다"는 마음가짐으로 접근 전략을 바꾸는 것이 시간을 아낀다.

## 단계별 절차

**1) ELF 바이너리의 strip 여부 확인**
```bash
file ./target
# 출력 예: ELF 64-bit LSB executable, x86-64, ... , not stripped
#      또는: ..., stripped
nm ./target 2>&1 | head       # 심볼이 없으면 "no symbols" 메시지 출력
readelf -S ./target | grep -E '\.symtab|\.dynsym'   # .symtab 유무 확인
```

**2) Windows PE + PDB 확인**
```bash
dumpbin /headers target.exe | findstr /i "pdb"
```
또는 IDA/x64dbg가 파일을 열 때 자동으로 같은 폴더/심볼 서버에서 PDB를 찾아 로드한다. 로드에 성공하면 함수 이름이 자동으로 채워진다.

**3) Stripped 바이너리 분석 시 이름 대신 활용할 단서 모으기**
- 임포트된 라이브러리 함수 이름(예: `strcpy`, `CreateFileW`) — 이 함수를 호출하는 시점 근처의 코드가 무엇을 하려는지 강한 힌트가 된다.
- 문자열 리터럴(REV-0036) — 에러 메시지, 포맷 문자열, 설정 키 이름 등이 근처 함수의 역할을 암시한다.
- 함수 인자 개수/패턴(REV-0032) — 특정 라이브러리 함수와 같은 시그니처를 가진 함수는 비슷한 역할을 할 가능성이 있다.
- 코드 구조(반복문, 분기 개수, 상수값) — 알고리즘의 "모양"으로 정체를 추정(예: 특정 상수가 보이면 REV-0026에서 다룬 FNV 해시처럼 알려진 알고리즘일 수 있다).

**4) 직접 이름을 붙여가며 분석 진행**

IDA/Ghidra에서 함수나 변수를 분석해서 역할을 알아내면, 그 자리에서 바로 이름을 바꿔둔다(`N` 단축키). 처음에는 `sub_401000`이었던 함수를 `check_password`로 바꿔두면, 이후 그 함수를 참조하는 모든 곳에 자동으로 새 이름이 반영되어 분석이 누적된다.

## 명령어/단축키
```bash
file ./target                 # ELF strip 여부, 아키텍처 확인
nm ./target                    # 심볼 테이블 나열(stripped면 거의 비어있음)
objdump -t ./target            # 심볼 테이블 상세 (nm과 유사)
readelf -s ./target            # ELF 심볼 테이블 확인
strip --strip-all ./target     # (참고용) 심볼을 강제로 제거하는 명령
```
IDA: `N` (함수/변수 이름 바꾸기), `Shift+F12` (Strings), Functions 창에서 자동 이름(`sub_`)과 사용자 지정 이름을 시각적으로 구분 가능(색상/기본값).
Ghidra: 심볼 위에서 `L`(Rename) 또는 우클릭 → Rename.

## 출력 해석
- `nm target` 결과가 `nm: target: no symbols`면 완전히 strip된 바이너리다.
- `readelf -S`에서 `.symtab` 섹션이 없고 `.dynsym`만 있다면, 정적 심볼은 제거됐지만 동적 링크에 필요한 최소 심볼(외부 함수 이름 등)은 남아있는 일반적인 strip 상태다.
- IDA에서 `sub_`로 시작하는 이름의 비율이 매우 높다면(90% 이상) stripped 바이너리로 보고 분석 전략을 조정해야 한다.
- 함수 이름 중 `main`, `_start`, `printf`, `malloc` 같은 표준 이름이 남아있는 이유는 각각 진입점 관례, 동적 링크 심볼, PLT(Procedure Linkage Table) 참조 때문이지 strip이 덜 된 것이 아니다.

## 흔한 실수
- Stripped 바이너리를 보고 "심볼이 없으니 로직도 알 수 없다"고 지레 포기하는 것 — 심볼은 이름표일 뿐, 명령어와 로직 자체는 그대로 남아있다.
- `sub_401000`같은 자동 이름을 그냥 방치하고 분석을 진행하다가, 나중에 어떤 함수가 어떤 역할이었는지 헷갈려서 처음부터 다시 분석하는 것 — 알아낸 즉시 이름을 바꿔두는 습관이 중요하다.
- ELF의 `.dynsym`(동적 심볼)이 남아있는 걸 보고 "이 바이너리는 strip이 안 됐다"고 착각하는 것 — `.symtab`(정적/디버그 심볼)이 없으면 일반적인 배포용 strip 상태다.
- PDB 파일을 심볼과 별개의 "옵션 파일" 정도로 여기고 무시하는 것 — Windows 분석에서는 PDB 유무가 분석 난이도를 극적으로 바꾼다. 공개된 시스템 DLL은 Microsoft 심볼 서버에서 PDB를 내려받을 수 있는 경우가 많다.
- 최적화(REV-0037)로 인한 "이상한 코드 구조"와 strip으로 인한 "이름 없음"을 같은 원인으로 혼동하는 것 — 최적화와 strip은 독립적으로 켜고 끌 수 있는 서로 다른 빌드 옵션이다.

## 막혔을 때 다음 체크
- 이름이 사라진 이유가 최적화 때문인지 strip 때문인지 헷갈리면 → REV-0037(컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유)로 이동해서 둘을 구분.
- 구조체 필드 이름이 사라진 stripped 바이너리에서 오프셋만으로 구조체를 재구성하는 방법이 궁금하면 → REV-0035(구조체 접근이 어셈블리로 변하는 방식)로 이동.
- 함수 인자 개수/타입을 이름 없이 레지스터 패턴만으로 추정하는 방법이 궁금하면 → REV-0032(함수 인자와 반환값이 어디에 있는지)로 이동.
- 문자열을 단서로 활용하는 구체적인 방법이 궁금하면 → REV-0036(문자열이 메모리에 저장되는 방식)으로 이동.

## 미니 예제
다음 두 화면은 같은 바이너리를 심볼이 있을 때와 없을 때 IDA로 열었을 때의 차이를 보여준다.

**심볼 있음(디버그 빌드, `-g` 옵션):**
```c
int check_password(char *input) {
    int is_valid;
    is_valid = strcmp(input, "s3cr3t") == 0;
    return is_valid;
}
```

**동일 바이너리를 strip한 후 (`strip --strip-all`):**
```c
int sub_401136(char *a1) {
    int v2;
    v2 = strcmp(a1, "s3cr3t") == 0;
    return v2;
}
```

함수 이름이 `check_password` → `sub_401136`으로, 지역 변수 `is_valid`가 `v2`로 바뀌었을 뿐, **실제 비교 로직(`strcmp`로 `"s3cr3t"`와 비교)은 완전히 동일하게 남아있다.** `strcmp`라는 라이브러리 함수 이름과 `"s3cr3t"`라는 문자열 리터럴은 strip 이후에도 여전히 보이기 때문에, 이 함수가 비밀번호를 검사한다는 사실은 stripped 상태에서도 충분히 추론할 수 있다. 이것이 "심볼이 없어도 분석은 가능하지만 훨씬 느리다"는 말의 실제 의미다.

## 관련 글
- REV-0030 — Code Data BSS Stack Heap 기초
- REV-0032 — 함수 인자와 반환값이 어디에 있는지
- REV-0035 — 구조체 접근이 어셈블리로 변하는 방식
- REV-0036 — 문자열이 메모리에 저장되는 방식 ASCII UTF-8 UTF-16
- REV-0037 — 컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유

## 출처/검증
- ELF 심볼 테이블(`.symtab`)과 동적 심볼(`.dynsym`)의 구분, `strip` 유틸리티 동작: `man 1 strip`, `man 5 elf` 및 System V ABI 공식 스펙 기준 (2026-09-08 검증).
- Windows PDB(Program Database) 심볼 파일과 디버깅 정보 분리 방식: Microsoft 공식 문서 "PDB Files" 및 Debugging Tools for Windows 문서 기준.
