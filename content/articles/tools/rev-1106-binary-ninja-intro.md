---
id: REV-1106
title: "Binary Ninja 기초 소개(IDA/Ghidra 대비 언제 쓰는지)"
slug: "rev-1106-binary-ninja-intro"
category: "tools"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["Binary Ninja", IDA, Ghidra]
keywords: ["Binary Ninja", "Binary Ninja 소개", "IDA 대안", "BNIL", "MLIL", "HLIL", "Vector 35"]
aliases: ["바이너리 닌자", "Binary Ninja 무료판", "Binary Ninja Free", "Binary Ninja Cloud"]
symptom_keywords: ["Binary Ninja가 뭔지 모름", "IDA 말고 다른 디스어셈블러 찾는 중", "Binary Ninja 무료로 쓸 수 있는지 궁금함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Binary Ninja는 Vector 35가 만든 상용 디스어셈블러/디컴파일러로, IDA·Ghidra와 달리 자체 IL(중간 표현)을 저수준→고수준 3단계(LLIL → MLIL → HLIL)로 분리해 놓아서 분석 자동화 스크립트를 짤 때 원하는 추상화 단계를 정확히 골라 조작할 수 있다는 점이 가장 큰 차별점이며, `Binary Ninja Free`(x86/x64/ARM만 지원, 비상업 전용, API/플러그인 불가)라는 무료 데스크톱판과 `Binary Ninja Cloud`(브라우저 기반, 바이너리를 Vector 35 서버에 업로드해야 함)도 존재한다.

## 언제 검색해야 하나
- CTF writeup이나 툴 목록에서 "Binary Ninja", "binja"라는 이름이 나왔는데 IDA/Ghidra랑 뭐가 다른지 모를 때
- 기본 툴 목록에는 Binary Ninja가 없는데, 누군가 "무료로 쓸 수 있는 디스어셈블러"를 찾다가 발견했을 때
- Python으로 분석을 자동화하고 싶은데 IDAPython/Ghidra 스크립팅이 번거롭게 느껴져서 대안을 찾을 때
- writeup에 `MLIL`, `HLIL` 같은 낯선 용어가 나와서 뜻을 확인해야 할 때

## 핵심 개념

### Binary Ninja는 무엇인가
Binary Ninja는 Vector 35가 개발한 상용 리버스 엔지니어링 플랫폼이다. IDA, Ghidra와 마찬가지로 바이너리를 디스어셈블하고 함수를 인식하며, 디컴파일(의사 C코드) 결과도 보여준다. 가장 큰 특징은 자체 IL 체계인 **BNIL(Binary Ninja Intermediate Language)**이다.

### BNIL — LLIL / MLIL / HLIL 3단계
BNIL은 하나의 IL이 아니라 서로 다른 추상화 단계에서 동작하는 IL들의 모음이다.

- **LLIL(Low Level IL)**: 원본 명령어 의미를 거의 그대로 옮긴 가장 저수준 표현이다. NOP을 제거하고 플래그를 조건부 명령에 접어 넣는 정도의 정리만 하며, 나머지는 실제 기계어 명령어와 거의 1:1 대응이다.
- **MLIL(Medium Level IL)**: 레지스터/메모리 접근을 "변수"로 변환하고, 변수에 타입을 부여하며, 호출 규약 정보를 이용해 함수 호출에 인자·타입을 채워 넣는다. 데이터 흐름 분석과 상수 전파도 이 단계에서 이루어진다. 즉 레지스터가 아니라 이미 의미 있는 변수 이름으로 로직을 볼 수 있다.
- **HLIL(High Level IL)**: MLIL 위에 고수준 제어 흐름(if/while/for 형태)과 각종 죽은 코드 제거·단순화 패스를 추가한 것으로, 실제 소스코드에 가장 가까운 의사 C코드 형태다. HLIL은 트리(AST) 구조로 되어 있어서 IDA의 Hex-Rays 디컴파일 결과나 Ghidra의 Decompile 창과 비슷하게 읽힌다.

각 단계(SSA 폼 제외)는 사람이 읽을 수 있도록 설계되어 있고, 부호 있는/없는 비교 연산자나 `sx`(부호 확장), `zx`(제로 확장), 크기 접미사(`.q`, `.d`, `.w`, `.b`) 같은 표기를 사용해 정보를 압축해서 보여준다. 스크립트를 짤 때 "레지스터 단위로 세밀하게 손대고 싶으면 LLIL, 변수/타입 단위로 다루고 싶으면 MLIL, 소스코드 수준 로직만 보고 싶으면 HLIL"처럼 목적에 맞는 단계를 선택할 수 있다는 게 IDA(디스어셈블리 vs Hex-Rays 의사코드, 2단계)나 Ghidra(P-code 기반, 사용자에게 직접 노출되는 단계가 제한적)보다 세분화된 장점이다.

### 무료로 쓸 수 있는 방법 두 가지
Binary Ninja는 기본적으로 유료(Ultimate 등 상용 라이선스) 제품이지만, 두 가지 무료 경로가 있다.

- **Binary Ninja Cloud**: 다운로드 없이 브라우저에서 쓰는 버전이다. 협업 기능, 그래프 임베딩, 코드 직접 링크, 여러 IL 뷰를 제공하지만 바이너리를 Vector 35 서버에 업로드해야 하고, PE/Mach-O/ELF 포맷만 지원하며, API/플러그인은 쓸 수 없고, 성능 제한이 엄격하다.
- **Binary Ninja Free**: 다운로드해서 쓰는 데스크톱판이다. 디컴파일 가능한 아키텍처가 x86, x86_64, ARMv7(Thumb2 포함), ARMv8(AArch64)로 제한되고(PowerPC/MIPS/RISC-V 등은 디컴파일 지원 안 됨), IL 뷰도 Disassembly/HLIL/Pseudo C만 볼 수 있으며(MLIL/LLIL 뷰 제한), API/플러그인 접근이 없어 자동화 스크립트를 못 쓴다. 명시적으로 "상업적 용도로 사용 불가"라는 라이선스 조건이 붙는다.

즉 CTF 연습 목적(비상업)으로 x86/x64/ARM 바이너리를 데스크톱에서 가볍게 열어보는 용도라면 Binary Ninja Free로 충분하지만, 이 저장소가 다루는 스크립팅 자동화(IDAPython/Ghidra 스크립트에 대응하는 것)를 Binary Ninja에서 하려면 API가 열려 있는 유료 라이선스가 필요하다.

### IDA/Ghidra 대비 언제 쓰는가
- 이미 IDA Pro(유료) 라이선스가 있고 팀이 IDA에 익숙하다면 Binary Ninja로 갈아탈 이유는 적다.
- Ghidra는 완전 무료·오픈소스이고 API(Java, GhidraScript, 일부 Python 지원)도 열려 있어서 예산이 없는 CTF 환경에서는 여전히 1순위 선택이다.
- Binary Ninja는 Python 친화적인 API 설계로 유명해서(정식 라이선스가 있다면) 분석 자동화 스크립트를 빠르게 짜고 싶을 때, 또는 BNIL의 3단계 IL을 이용해 변수/타입 단위로 프로그래밍적으로 조작하고 싶을 때 강점이 있다. 이 저장소의 필수 툴킷에는 포함되어 있지 않으므로, IDA Free나 Ghidra로 막힌 특정 상황(예: 특정 아키텍처의 디컴파일 품질, 팀이 이미 쓰던 스크립트 자산)에서 "선택적으로" 고려하는 도구로 취급하면 된다.

## 화면/코드에서 보이는 징후
- writeup에 "Binary Ninja", "binja", "BNIL", "MLIL", "HLIL"이라는 단어가 등장
- 스크립트 코드에 `import binaryninja`, `bv.functions`, `func.mlil`, `func.hlil` 같은 API 호출이 보임
- 화면 캡처에 IDA/Ghidra와 다른 다크 테마 UI, 그래프 뷰 옆에 "Pseudo C"나 "HLIL" 탭이 나란히 있는 구성

## 가장 먼저 할 것
CTF 문제를 당장 풀어야 하는 상황이면 이미 설치되어 있는 IDA Free/Ghidra를 그대로 쓰는 게 낫다. Binary Ninja를 처음 써보고 싶다면 공식 사이트에서 `Binary Ninja Free`(비상업용) 데스크톱판을 받아 x86/x64/ARM 샘플 바이너리를 열어 HLIL 뷰가 IDA의 Hex-Rays 디컴파일과 어떻게 다르게 보이는지 비교해보는 정도로 충분하다.

## 단계별 절차
1. 공식 사이트에서 무료 옵션이 데스크톱판(`Binary Ninja Free`)인지 브라우저판(`Binary Ninja Cloud`)인지 확인하고 목적에 맞는 쪽을 선택한다.
2. 데스크톱판을 받았다면 라이선스 동의 후 설치하고, 분석할 x86/x64/ARM 바이너리를 연다.
3. 하단/우측 탭에서 Disassembly, HLIL(Pseudo C) 뷰를 전환해보며 같은 함수가 어떻게 다르게 표현되는지 비교한다.
4. 자동화가 필요하면 API/플러그인이 열려 있는 정식 라이선스가 있는지부터 확인한다(무료판은 API가 막혀 있음).
5. 팀에 이미 IDA/Ghidra 스크립트 자산이 많다면 굳이 옮기지 말고, Binary Ninja는 "두 번째 의견"이 필요할 때 보조로만 사용한다.

## 명령어/단축키
Binary Ninja Free 데스크톱판은 File → Open으로 바이너리를 로드한다. 정식 라이선스에서 API를 쓸 때 기본 패턴은 다음과 같다(개념 확인용, 무료판에서는 동작하지 않음).
```python
import binaryninja as bn

bv = bn.open_view("./chall")
for func in bv.functions:
    print(func.name, hex(func.start))
    for block in func.hlil:      # HLIL(고수준 IL) 단위로 순회
        print(block)
```

## 출력 해석
- HLIL 뷰는 IDA Hex-Rays의 의사 C코드, Ghidra의 Decompile 창과 목적이 같다 — 변수 이름·제어 흐름이 소스코드에 가깝게 재구성된 결과다.
- MLIL 뷰가 안 보이고 Disassembly/HLIL/Pseudo C만 보인다면 무료판(Binary Ninja Free/Cloud)의 IL 뷰 제한 때문이다. 유료판에서는 LLIL/MLIL/HLIL을 모두 전환해가며 볼 수 있다.
- 특정 아키텍처(PowerPC, MIPS, RISC-V 등)에서 디컴파일 탭 자체가 안 나온다면 무료판의 아키텍처 제한 때문일 가능성이 높다.

## 흔한 실수
- Binary Ninja Free를 상업 프로젝트나 유료 컨설팅 작업에 그대로 쓰는 것 — 라이선스에 "상업적 용도로 사용 불가"가 명시되어 있다.
- 무료판에서 플러그인/스크립트를 설치하려다가 API 자체가 막혀 있다는 걸 모르고 시간을 낭비하는 것.
- Binary Ninja Cloud에 CTF 문제 파일(대회 규정상 외부 유출 금지일 수 있는)을 무심코 업로드하는 것 — Cloud는 바이너리를 Vector 35 서버에 제출해야 동작한다는 점을 반드시 인지해야 한다.
- LLIL/MLIL/HLIL을 그냥 "같은 디컴파일 결과"로 오해하는 것 — 각 단계는 추상화 수준이 다르고 스크립트에서 다루는 API 객체도 다르다.

## 막혔을 때 다음 체크
- IDA 자체의 설치/단축키가 궁금하면 → REV-0274 IDA 설치와 오프라인 준비, REV-0275 IDA 단축키 치트시트
- Ghidra 자체의 설치/단축키가 궁금하면 → REV-0277 Ghidra 설치와 오프라인 준비, REV-0278 Ghidra 단축키 치트시트
- IDA에서 반복 작업을 자동화하고 싶다면 → REV-1107 IDAPython으로 반복 작업 자동화하기
- 무료·오픈소스 디스어셈블러 자동화가 필요하면 → REV-1108 radare2 r2pipe로 스크립팅하기

## 미니 예제
Binary Ninja Free로 같은 `strcmp` 검증 함수를 열었을 때 화면 구성 예시(개념 설명):
```text
[Disassembly]                    [Pseudo C (HLIL)]
0x1040: push rbp                 int32_t check(char* input)
0x1041: mov rbp, rsp             {
0x1044: sub rsp, 0x10                if (strcmp(input, "flag_value") == 0)
0x1048: mov [rbp-8], rdi                  return 1;
...                                   return 0;
                                  }
```
무료판에서는 이 두 뷰(Disassembly, Pseudo C/HLIL)만 전환 가능하고, LLIL/MLIL 뷰나 API를 통한 자동 순회는 정식 라이선스가 필요하다.

## 관련 글
- REV-0274 — IDA 설치와 오프라인 준비
- REV-0277 — Ghidra 설치와 오프라인 준비
- REV-1107 — IDAPython으로 반복 작업 자동화하기
- REV-1108 — radare2 r2pipe로 스크립팅하기

## 출처/검증
- Binary Ninja Free/Cloud의 라이선스 조건(비상업 전용, 지원 아키텍처 제한, API/플러그인 불가, Cloud의 서버 업로드 요구사항): Vector 35 공식 사이트 `binary.ninja/free/` 페이지 기준 (2026-09-10 확인).
- BNIL의 LLIL/MLIL/HLIL 3단계 정의와 각 단계의 역할(변수화, 타입 부여, 고수준 제어 흐름 재구성): Binary Ninja 공식 개발자 문서 `docs.binary.ninja` BNIL Overview 페이지 기준 (2026-09-10 확인).
