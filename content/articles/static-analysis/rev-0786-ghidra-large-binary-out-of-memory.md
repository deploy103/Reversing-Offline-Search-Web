---
id: REV-0786
title: "Ghidra가 큰 바이너리에서 메모리 부족으로 느려질 때"
slug: "rev-0786-ghidra-large-binary-out-of-memory"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra OutOfMemoryError", "Ghidra MAXMEM", "Ghidra launch.properties", "Ghidra 힙 메모리 설정", "Ghidra 큰 바이너리 느림"]
aliases: ["Ghidra 메모리 부족", "Ghidra Java heap space 에러", "Ghidra 큰 파일 분석 멈춤"]
symptom_keywords: ["Ghidra 분석 중 OutOfMemoryError 발생", "Ghidra가 큰 파일에서 계속 버벅임", "Ghidra 힙 메모리 부족 메시지", "Ghidra 컴퓨터 전체가 느려짐"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra는 자바(JVM) 위에서 동작하기 때문에 실행 시 할당되는 힙 메모리 상한이 정해져 있으며, 큰 바이너리(수십~수백 MB, 함수가 수만 개인 정적 링킹 바이너리 등)를 분석할 때 이 상한을 넘으면 `OutOfMemoryError`가 나거나, 그 직전 단계에서 가비지 컬렉션과 디스크 스와핑이 반복되며 CPU만 계속 도는 "체감상 멈춘 것 같은" 상태가 된다.

## 언제 검색해야 하나
- 큰 파일을 분석할 때 Ghidra나 시스템 전체가 눈에 띄게 느려지고 다른 프로그램까지 버벅일 때
- 콘솔/로그에 `java.lang.OutOfMemoryError: Java heap space` 계열 메시지가 보일 때
- 작업 관리자에서 Ghidra(Java) 프로세스의 메모리 사용량이 계속 늘어나기만 하고 CPU는 100%인데 진행이 거의 없을 때
- 여러 개의 큰 바이너리를 같은 프로젝트에서 동시에 분석하다가 문제가 생겼을 때

## 핵심 개념
Ghidra는 JVM 위에서 실행되므로, 실행 스크립트가 시작될 때 JVM에 넘기는 최대 힙 크기(`-Xmx` 옵션에 해당) 설정이 전체 성능의 상한선이 된다. 이 설정은 Ghidra 설치 폴더의 `support/launch.properties` 파일(또는 실행 스크립트 `ghidraRun`/`ghidraRun.bat` 내부)에서 `MAXMEM` 값으로 관리된다. 기본값은 시스템 물리 메모리를 기준으로 자동 계산되지만, 다음과 같은 상황에서는 부족해질 수 있다.

1. **바이너리 자체가 매우 큼**: 수백 MB짜리 펌웨어 이미지나 디버그 심볼이 잔뜩 포함된 바이너리는 그만큼 많은 함수/타입/주석 데이터를 메모리에 올려야 한다.
2. **함수 개수가 매우 많음**: 정적 링킹된 C++ 바이너리는 함수가 수만 개에 달할 수 있어, 각 함수의 분석 결과(타입, 변수, 데이터플로우 그래프)가 누적되며 메모리를 크게 소모한다.
3. **여러 프로그램을 한 프로젝트에서 동시에 열어둠**: 여러 바이너리를 동시에 CodeBrowser로 열어두면 각각의 캐시가 동시에 메모리를 점유한다.
4. **32비트 시스템/32비트 JVM 사용**: 32비트 프로세스는 주소 공간 자체가 제한되어 있어(대략 2~4GB), 물리 메모리가 충분해도 힙을 크게 키울 수 없다.

메모리가 부족해지면 즉시 에러가 나기보다, 먼저 JVM이 가비지 컬렉션을 훨씬 자주 돌리며 CPU를 소모하는 "GC 스래싱(thrashing)" 상태가 되고, 여기에 OS 스와핑까지 겹치면 실제 작업 진행 속도는 거의 0에 가까워진다. 이 상태는 REV-0781에서 설명하는 "느리지만 진행 중"인 정상 상태와 구분하기 어려우므로, 메모리 사용량을 직접 확인하는 것이 중요하다.

## 화면/코드에서 보이는 징후
- 작업 관리자/`top`에서 Java 프로세스의 메모리 사용량이 설정된 상한 근처까지 꾸준히 올라간 채로 유지된다.
- 콘솔(Ghidra를 터미널에서 실행한 경우) 또는 로그 파일에 `OutOfMemoryError`, `GC overhead limit exceeded` 메시지가 남는다.
- 시스템 전체 반응 속도가 느려지고, 디스크 사용률(스왑)이 비정상적으로 높다.
- Ghidra UI가 몇 초~몇 분 단위로 잠깐씩 멈췄다가 풀리는 것을 반복한다(긴 GC pause).

## 가장 먼저 할 것
작업 관리자/`top`으로 Ghidra(Java) 프로세스의 메모리 사용량이 상한에 가까운지부터 확인한다. 상한에 붙어 있고 그 상태로 오래 유지된다면 메모리 부족이 원인일 가능성이 크다.

## 단계별 절차

**1) 현재 메모리 설정 확인**

Ghidra 설치 폴더의 `support/launch.properties` 파일을 열어 `MAXMEM` 항목의 현재 값을 확인한다(예: `MAXMEM=2G`).

**2) 물리 메모리 여유분 확인**

시스템 전체 물리 메모리 중 다른 프로그램이 쓰지 않는 여유분이 얼마나 되는지 확인한다. 힙을 늘리려면 그만큼의 여유 물리 메모리가 있어야 스와핑 없이 효과가 있다.

**3) MAXMEM 값 늘리기**

`launch.properties`의 `MAXMEM` 값을 물리 메모리 여유분을 고려해 늘린다(예: 8GB 이상 여유가 있다면 `MAXMEM=4G` 이상으로). 값을 변경한 뒤에는 Ghidra를 완전히 종료하고 다시 실행해야 반영된다.

**4) 분석 범위 줄이기**

메모리를 늘릴 수 없는 환경이라면, 분석 대상 자체를 줄인다. 불필요한 대형 리소스/데이터 섹션을 Program Trees에서 분석 대상 블록으로 지정하지 않거나, Decompiler Switch Analysis/Parameter ID처럼 메모리를 많이 쓰는 Analyzer를 꺼서 1차 분석 부담을 줄인다(REV-0781 참고).

**5) 동시에 여는 프로그램 개수 줄이기**

한 프로젝트 안에서 여러 바이너리를 동시에 CodeBrowser 탭으로 열어두고 있다면, 지금 분석에 필요한 것만 남기고 나머지는 닫는다.

**6) 32비트 환경이라면 64비트로 전환**

32비트 JVM/OS를 쓰고 있다면 애초에 힙을 크게 늘릴 수 없으므로, 가능하다면 64비트 OS와 64비트 Ghidra 배포본으로 전환한다.

**7) 그래도 부족하면 바이너리 분할 검토**

펌웨어 이미지처럼 여러 독립된 모듈이 하나로 합쳐진 파일이라면, 필요한 모듈만 잘라 별도로 분석하는 것도 현실적인 대안이 될 수 있다.

## 명령어/단축키
```text
support/launch.properties      MAXMEM 값 설정(설치 폴더 기준 상대 경로)
MAXMEM=4G                       힙 최대 크기 예시(환경에 맞게 조정)
작업 관리자 / top               Java 프로세스 메모리·CPU 사용량 확인
Analysis Options 창             무거운 Analyzer 선택적 해제
```

## 출력 해석
- `OutOfMemoryError: Java heap space`는 힙 자체가 부족했다는 뜻이므로 MAXMEM을 늘리는 것이 직접적인 해결책이다.
- `GC overhead limit exceeded`는 힙이 거의 다 찬 상태에서 가비지 컬렉션만 계속 반복하며 실제 작업은 거의 못 하고 있다는 뜻으로, 역시 메모리 부족의 신호다.
- MAXMEM을 늘렸는데도 물리 메모리 자체가 부족해 스와핑이 계속된다면, 힙 설정보다 시스템 메모리 자체를 늘리거나(RAM 추가) 분석 범위를 줄이는 것이 더 근본적인 해결책이다.

## 흔한 실수
- MAXMEM 값을 파일에서 수정만 하고 Ghidra를 재시작하지 않아 변경이 반영되지 않은 채로 "안 고쳐진다"고 오해하는 것.
- 물리 메모리보다 훨씬 큰 값으로 MAXMEM을 설정해서 오히려 심한 스와핑을 유발하는 것 — 물리 메모리 여유분 안에서 늘려야 한다.
- CPU가 100%인 것만 보고 "분석이 잘 진행되고 있다"고 판단하는 것 — GC 스래싱 상태에서도 CPU는 계속 사용된다.
- 32비트 환경의 근본적인 주소 공간 제약을 모르고 설정값만 계속 올리는 것.

## 막혔을 때 다음 체크
- 분석 자체가 느린 것과 진짜로 멈춘 것을 구분하는 절차가 더 필요하면 → REV-0781.
- 메모리를 늘려도 여전히 분석이 오래 걸리는 큰 바이너리라면 무거운 Analyzer를 꺼두는 전략 → REV-0157.
- 프로젝트 파일 자체가 손상/버전 문제로 안 열리는 별개의 상황이면 → REV-0785.

## 미니 예제
8GB RAM 환경에서 200MB짜리 정적 링킹 ELF를 분석하다가 문제가 생긴 상황이다.

1. 분석 도중 작업 관리자에서 Ghidra(Java) 프로세스 메모리 사용량이 기본 MAXMEM 값(예: 1G) 근처에 붙은 채 CPU만 100%로 도는 것을 확인.
2. Ghidra를 종료하고 `support/launch.properties`에서 `MAXMEM=1G`를 `MAXMEM=3G`로 수정.
3. Ghidra를 다시 실행해 같은 프로젝트를 열고 재분석.
4. 메모리 사용량이 여유 있게 유지되며 분석이 정상 속도로 완료되는 것을 확인.

## 관련 글
- REV-0781 — Ghidra Auto Analysis가 끝나지 않을 때
- REV-0157 — Ghidra Auto Analysis 옵션
- REV-0785 — Ghidra 프로젝트가 열리지 않을 때(버전 불일치)

## 출처/검증
- Ghidra가 JVM 위에서 동작하며 `support/launch.properties`의 `MAXMEM` 값으로 최대 힙 크기를 지정한다는 점: Ghidra 공식 설치/실행 가이드(Ghidra 배포 패키지 내 `docs/InstallationGuide` 및 `launch.properties` 파일 자체의 설명 주석) 기준.
- `OutOfMemoryError`/`GC overhead limit exceeded`가 JVM 힙 부족의 표준적인 신호라는 점은 자바 플랫폼 공식 문서(JVM 트러블슈팅 가이드) 기준의 일반적인 JVM 동작이다.
- 이 문서는 실제로 메모리 부족 상황을 직접 재현해 로그를 캡처하지 않았으며, 공식 문서와 일반적인 JVM 동작 원리를 바탕으로 정리했다. 정확한 기본 MAXMEM 값과 파일 경로는 Ghidra 버전/설치 방식에 따라 다를 수 있다.
