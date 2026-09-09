---
id: REV-0966
title: "smali 명령어(opcode) 빠른 참조"
slug: "rev-0966-smali-opcode-quickref"
category: "dotnet-android"
difficulty: "basic"
platform: [linux]
architecture: [ARM, ARM64]
format: [APK]
tools: [smali, apktool]
keywords: ["smali opcode", "smali 명령어 목록", "invoke-kind", "move-result", "packed-switch", "sparse-switch", "aget aput", "iget iput", "sget sput"]
aliases: ["smali 명령어표", "smali opcode 정리", "달빅 바이트코드 명령어", "smali 명령어 검색"]
symptom_keywords: ["smali에서 처음 보는 명령어를 만났다", "aget-object가 뭔지 모르겠다", "packed-switch 문법을 모르겠다", "check-cast가 뭔지 모르겠다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
smali 명령어는 대략 데이터 이동, 산술/논리 연산, 필드/배열 접근, 메서드 호출, 분기/스위치, 객체 생성/타입 검사 여섯 갈래로 나뉘며, [REV-0252](./rev-0252-smali-basics.md)에서 다룬 핵심 문법 외에 나머지 명령어도 이 표 하나로 즉시 뜻을 찾아 읽을 수 있다.

## 언제 검색해야 하나
- `.smali` 파일을 읽다가 [REV-0252](./rev-0252-smali-basics.md)에 안 나온 명령어(`aget-object`, `sget-boolean`, `packed-switch`, `check-cast` 등)를 만났을 때
- 필드 접근(`iget`/`sput` 계열)과 배열 접근(`aget`/`aput` 계열)이 헷갈릴 때
- `packed-switch`/`sparse-switch` 블록의 문법을 모를 때
- `check-cast`, `instance-of`, `new-instance`, `new-array`처럼 타입 관련 명령어의 차이를 모를 때
- 산술 명령어 접미사(`-int`, `-long`, `-float`, `/lit8`, `/2addr`)의 의미를 모를 때

## 핵심 개념
smali 명령어 이름은 대부분 **동작_타입** 또는 **동작-타입/서식** 형태로 조합되어 있어서, 접두사/접미사 규칙만 알면 처음 보는 opcode도 뜻을 추측할 수 있다. 타입 접미사는 `-object`(객체 참조), `-boolean`, `-byte`, `-char`, `-short`, `-int`, `-long`, `-float`, `-double`, `-wide`(64비트 값 전반, long/double 공용)로 구성된다. 서식 접미사는 `/2addr`(레지스터 2개로 압축된 형태, 결과를 첫 인자에 덮어씀), `/lit8`, `/lit16`(리터럴 상수를 명령어에 직접 인코딩), `/from16`, `/jumbo`(더 큰 레지스터/오프셋 범위)처럼 같은 의미의 명령어를 크기별로 나눈 것이다. 즉 `add-int/2addr v0, v1`은 `add-int v0, v0, v1`과 같은 뜻이며 단지 바이트코드가 더 짧을 뿐이다.

## 화면/코드에서 보이는 징후
`smali/` 폴더의 `.smali` 파일 본문 어디서나 아래 표에 나오는 명령어들이 섞여 나타난다. JADX의 "Smali" 보기 모드에서도 동일한 표기를 볼 수 있다.

## 가장 먼저 할 것
명령어 이름의 접두사(동작)와 접미사(타입/서식)를 분리해서 읽는다. 예를 들어 `sget-object`를 봤다면 "sget"(정적 필드 읽기) + "object"(참조 타입)로 나눠 "정적 필드에서 객체 참조를 읽어온다"고 바로 해석할 수 있다.

## 단계별 절차
1. 명령어를 동작 부분과 타입/서식 접미사로 분리한다.
2. 아래 표에서 동작 부분을 찾아 기본 의미를 확인한다.
3. 피연산자 순서(대상 레지스터가 먼저 오는지, 나중에 오는지)를 표의 "형식" 열로 확인한다.
4. `packed-switch`/`sparse-switch`처럼 별도 데이터 블록을 참조하는 명령어는 `.method` 끝부분의 `:pswitch_data_...` 또는 `:sswitch_data_...` 레이블 블록을 함께 찾아 대응 케이스를 확인한다.

## 명령어/단축키
```bash
# 특정 opcode가 쓰인 곳을 전부 찾기
grep -rn "packed-switch" out/smali/

# 필드 접근 명령어만 모아보기
grep -rnE '^\s*[si](get|put)' out/smali/com/example/
```

## 출력 해석

### 데이터 이동 / 상수
| 명령어 | 형식 | 의미 |
|---|---|---|
| `move vA, vB` | 레지스터→레지스터 | `vB` 값을 `vA`로 복사(32비트) |
| `move-object vA, vB` | 레지스터→레지스터 | 객체 참조 복사 |
| `move-wide vA, vB` | 레지스터쌍→레지스터쌍 | long/double(64비트) 복사 |
| `move-result vA` | invoke 직후 | 방금 호출의 32비트 반환값을 `vA`에 저장 |
| `move-result-object vA` | invoke 직후 | 반환된 객체 참조를 `vA`에 저장 |
| `move-result-wide vA` | invoke 직후 | 반환된 long/double을 `vA`에 저장 |
| `move-exception vA` | catch 블록 시작 | 예외 객체를 `vA`에 저장 |
| `const/4 vA, #lit4` | 즉시값 | 작은 정수 상수 대입 |
| `const/16 vA, #lit16` | 즉시값 | 16비트 범위 정수 상수 대입 |
| `const vA, #lit32` | 즉시값 | 32비트 정수/float 비트패턴 대입 |
| `const-wide vA, #lit64` | 즉시값 | 64비트 long/double 대입 |
| `const-string vA, "s"` | 즉시값 | 문자열 상수 참조 대입 |
| `const-class vA, Lfoo;` | 즉시값 | 클래스 리터럴(`Foo.class`) 대입 |

### 필드 접근
| 명령어 | 의미 |
|---|---|
| `iget vA, vB, Lclass;->field:T` | 인스턴스 필드 읽기 (`vB` 객체의 `field`를 `vA`로) |
| `iput vA, vB, Lclass;->field:T` | 인스턴스 필드 쓰기 (`vA` 값을 `vB` 객체의 `field`에) |
| `sget vA, Lclass;->field:T` | 정적(static) 필드 읽기 |
| `sput vA, Lclass;->field:T` | 정적 필드 쓰기 |
| (접미사) `-object`/`-boolean`/`-byte`/`-char`/`-short`/`-wide` | 필드 타입에 맞춰 붙는 접미사 |

### 배열 접근
| 명령어 | 의미 |
|---|---|
| `array-length vA, vB` | `vB` 배열의 길이를 `vA`에 저장 |
| `new-array vA, vB, [I` | 길이 `vB`인 `int[]` 배열을 새로 만들어 `vA`에 저장 |
| `aget vA, vB, vC` | `vB[vC]` 값을 `vA`에 저장(배열 읽기) |
| `aput vA, vB, vC` | `vA` 값을 `vB[vC]`에 저장(배열 쓰기) |
| (접미사) `-object`/`-boolean`/`-byte`/`-char`/`-short`/`-wide` | 배열 원소 타입별 접미사 |
| `fill-array-data vA, :arr_data` | 리터럴 배열 데이터를 `vA` 배열에 한 번에 채움 |

### 메서드 호출 / 반환
| 명령어 | 의미 |
|---|---|
| `invoke-virtual {인자...}, Lc;->m(P)R` | 가상 메서드(오버라이드 가능) 호출 |
| `invoke-direct {인자...}, Lc;->m(P)R` | 생성자/private 메서드 호출 |
| `invoke-static {인자...}, Lc;->m(P)R` | static 메서드 호출(`this` 없음) |
| `invoke-super {인자...}, Lc;->m(P)R` | 부모 클래스의 메서드를 명시적으로 호출 |
| `invoke-interface {인자...}, Lc;->m(P)R` | 인터페이스 타입으로 선언된 메서드 호출 |
| `return vA` / `return-wide vA` / `return-object vA` | 값 반환 후 메서드 종료 |
| `return-void` | 값 없이 메서드 종료 |

### 분기 / 스위치
| 명령어 | 의미 |
|---|---|
| `goto :label` | 무조건 분기 |
| `if-eq/if-ne/if-lt/if-ge/if-gt/if-le vA, vB, :label` | 두 레지스터 비교 후 분기 |
| `if-eqz/if-nez/if-ltz/if-gez/if-gtz/if-lez vA, :label` | 레지스터를 0과 비교 후 분기 |
| `packed-switch vA, :pswitch_data_0` | `vA` 값에 따라 연속된 정수 케이스로 분기(테이블 점프) |
| `sparse-switch vA, :sswitch_data_0` | `vA` 값에 따라 불연속 정수 케이스로 분기 |
| `:pswitch_data_0 .packed-switch 시작값 :case1 :case2 ... .end packed-switch` | packed-switch용 케이스 테이블 정의 |

### 산술 / 논리
| 명령어 | 의미 |
|---|---|
| `add-int`, `sub-int`, `mul-int`, `div-int`, `rem-int` | 정수 사칙연산/나머지 |
| `and-int`, `or-int`, `xor-int`, `not-int`, `neg-int` | 비트 논리 연산/부호 반전 |
| `shl-int`, `shr-int`, `ushr-int` | 왼쪽/오른쪽(부호 유지)/오른쪽(논리) 시프트 |
| `add-int/2addr vA, vB` | `vA = vA + vB` (압축 서식) |
| `add-int/lit8 vA, vB, #lit8` | `vA = vB + 리터럴상수` (상수가 명령어에 직접 포함) |
| `int-to-long`, `long-to-int`, `int-to-float` 등 | 형변환(cast) |

### 타입 / 객체
| 명령어 | 의미 |
|---|---|
| `new-instance vA, Lclass;` | 객체를 위한 메모리만 할당(생성자는 아직 안 부름) |
| `check-cast vA, Lclass;` | `vA`가 `Lclass;` 타입인지 검사, 아니면 `ClassCastException` |
| `instance-of vA, vB, Lclass;` | `vB`가 `Lclass;` 인스턴스인지 boolean으로 `vA`에 저장 |
| `throw vA` | `vA`(예외 객체)를 던진다 |
| `monitor-enter vA` / `monitor-exit vA` | `synchronized` 블록의 락 획득/해제 |

## 흔한 실수
- `new-instance`만 보고 생성자까지 다 실행됐다고 착각하는 것. 실제로는 메모리만 할당되며, 바로 뒤에 `invoke-direct {...}, Lclass;-><init>(...)` 호출이 있어야 생성자가 실행된다.
- `/2addr` 서식을 별도 명령어로 착각해서 온전한 3-피연산자 버전과 다르게 해석하는 것. 둘은 완전히 같은 연산이고 인코딩 크기만 다르다.
- `packed-switch`의 케이스 데이터 블록(`:pswitch_data_0`)을 못 찾고 각 `:case` 레이블이 어디서 오는지 헷갈리는 것 — 항상 메서드 끝부분에 `.packed-switch` 블록이 별도로 있다.
- `if-eqz` 계열을 두 레지스터 비교 명령(`if-eq`)과 혼동하는 것. 끝의 `z`는 "0과 비교"라는 뜻으로 피연산자가 하나뿐이다.

## 막혔을 때 다음 체크
- 레지스터(`v`/`p`)와 기본 문법 자체가 헷갈리면 → [REV-0252 smali 기초 문법](./rev-0252-smali-basics.md)
- 코틀린/자바 코드와 smali를 나란히 대조하고 싶으면 → [REV-0253 Java Kotlin 코드와 smali 연결](./rev-0253-smali-to-java-kotlin.md)
- smali를 뽑고 다시 조립하는 절차가 궁금하면 → [REV-0251 apktool 기본 사용법](./rev-0251-apktool-basics.md)
- apktool/JADX 옵션 자체가 궁금하면 → REV-0968 JADX/apktool 옵션 빠른 참조

## 미니 예제
```smali
:pswitch_data_0
.packed-switch 0x1
    :case_one
    :case_two
    :case_three
.end packed-switch

.method public grade(I)Ljava/lang/String;
    .locals 1
    packed-switch p1, :pswitch_data_0
    const-string v0, "unknown"
    return-object v0

    :case_one
    const-string v0, "one"
    return-object v0

    :case_two
    const-string v0, "two"
    return-object v0

    :case_three
    const-string v0, "three"
    return-object v0
.end method
```
`packed-switch p1, :pswitch_data_0`은 `p1` 값에서 시작값(`0x1`)을 뺀 인덱스로 케이스 테이블을 찾아간다. `p1`이 1이면 `:case_one`, 2면 `:case_two`, 3이면 `:case_three`로 분기하고, 그 범위를 벗어나면 `packed-switch` 바로 다음 줄(`const-string v0, "unknown"`)로 그대로 흘러간다(fall-through). 이 구조는 자바의 `switch(grade)` 문이 정수 케이스가 연속적일 때 컴파일되는 전형적인 형태다.

## 관련 글
- REV-0252 — smali 기초 문법
- REV-0253 — Java Kotlin 코드와 smali 연결
- REV-0251 — apktool 기본 사용법
- REV-0968 — JADX/apktool 옵션 빠른 참조

## 출처/검증
- smali/baksmali 명령어 목록과 서식(`/2addr`, `/lit8`, `/lit16` 등) 표기는 공식 저장소(`JesusFreke/smali`, GitHub) 문서 및 wiki 기준으로 정리했다.
- Dalvik 바이트코드 명령어 집합(opcode) 의미는 Android 오픈소스 프로젝트(AOSP)의 Dalvik bytecode 명세 문서를 기준으로 확인했다 (2026-09-09 확인).
