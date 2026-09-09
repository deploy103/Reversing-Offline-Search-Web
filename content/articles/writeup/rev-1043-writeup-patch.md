---
id: REV-1043
title: "[Write-up] patch"
slug: "rev-1043-writeup-patch"
category: "writeup"
difficulty: "intermediate"
platform: [windows]
architecture: [x64]
format: [PE]
tools: [IDA, x64dbg, "Resource Hacker"]
keywords: ["dreamhack patch", "드림핵 patch", "GDI+ 리버싱", "GdipDrawLineI", "WM_PAINT 분석"]
aliases: ["dreamhack patch 못풀겠음", "드림핵 patch flag 못찾음", "GDI+ 그림 리버싱 플래그"]
symptom_keywords: ["드림핵 patch 문제에서 플래그를 그리는 루틴을 못찾음", "WM_PAINT에서 뭘 그리는지 모르겠음", "GdipDrawLineI 호출이 계속 반복되는데 이유를 모름"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
드림핵 Silver 4 "patch"는 Win32 GUI 프로그램이 `WM_PAINT`에서 GDI+로 플래그 그림을 그려주긴 하는데, 같은 타이밍에 또 다른 서브루틴이 26번 넘게 선(line)을 겹쳐 그려서 플래그를 가려버리는 구조이며, 그 "가리는" 서브루틴의 시작 부분을 즉시 `ret`으로 패치해 실행을 무력화하면 가려지지 않은 원본 그림이 드러난다.

## 언제 검색해야 하나
- 드림핵 워게임 patch(챌린지 번호 49) 문제를 열었는데 실행하면 창이 뜨고 뭔가 그려지긴 하는데 플래그로 보이는 문자열이나 그림이 안 보일 때
- IDA에서 Import 목록에 `GdipCreateFromHDC`, `GdipDrawLineI`, `GdipCreatePen1` 같은 이름이 보여서 GDI+ API라는 것은 알았지만 이걸 어디서부터 봐야 할지 모를 때
- 문제 힌트에 "GDI+", "Graphics Functions", "x64dbg 공식 문서"가 적혀 있어서 그래픽 API 자체를 리버싱해야 한다는 것까지는 알겠는데 다음 스텝이 안 보일 때

## 핵심 개념

### WndProc과 WM_PAINT의 역할
Win32 GUI 프로그램은 메시지 루프(`GetMessage`/`DispatchMessage`)를 통해 윈도우로 들어오는 이벤트를 `WndProc`이라는 콜백 함수로 전달한다. `WM_PAINT`(메시지 값 `0xF`)는 "창의 일부 또는 전체를 다시 그려야 한다"는 신호이고, 정상적인 처리 순서는 `BeginPaint`로 그리기용 디바이스 컨텍스트(HDC)를 얻고, 실제로 뭔가를 그린 다음, `EndPaint`로 마무리하는 것이다. patch 문제의 WndProc은 `case 2`(WM_DESTROY)에서 `PostQuitMessage`를 부르고, `case 0xF`(WM_PAINT)에서 `BeginPaint` → `GdipCreateFromHDC`(HDC로부터 GDI+ Graphics 객체 생성) → 내부 드로잉 서브루틴 호출 → `GdipDeleteGraphics`/`GdipFree` → `EndPaint` 순서로 흐른다. `case 0x202`(WM_LBUTTONUP, 마우스 좌클릭을 뗄 때)에서는 `InvalidateRect`+`UpdateWindow`로 강제로 다시 그리게 만든다.

### GDI+ 드로잉 API가 코드에서 보이는 형태
GDI+는 C 스타일 export 함수(`Gdip` 접두사)로 구성되어 있고 각 함수는 핸들을 통해 객체를 다룬다.
- `GdipCreateFromHDC(hdc, &graphics)` — HDC로부터 그림을 그릴 대상 Graphics 객체를 만든다.
- `GdipCreatePen1(color, width, unit, &pen)` — 선 색상/두께를 가진 Pen 객체를 만든다.
- `GdipDrawLineI(graphics, pen, x1, y1, x2, y2)` — 정수 좌표로 직선을 하나 그린다.
- `GdipSetSmoothingMode(graphics, mode)` — 안티에일리어싱 모드를 설정한다(값 `4`는 고품질 안티에일리어싱).
- `GdipDeletePen`/`GdipDeleteGraphics`/`GdipFree` — 만든 객체와 버퍼를 해제한다.

이 문제에서는 이 다섯 개 API를 감싼 작은 헬퍼 함수가 하나 있고(코드 상 함수명은 사라져 있어 `sub_140002B80` 식으로 보인다), 상위 함수가 이 헬퍼를 좌표만 바꿔서 반복 호출한다.

### 왜 그림이 가려지는가 — 두 겹의 드로잉
WM_PAINT 핸들러가 부르는 드로잉 함수는 내부적으로 두 부류의 작업을 한다. 하나는 실제로 플래그 모양(문자/도형)을 구성하는 여러 서브루틴 호출이고, 다른 하나는 같은 함수 안에서 26회 가까이 반복되는 "선 하나 긋기" 호출(선 색이 불투명 검정, 즉 `0xFF000000`)이다. 반복되는 검정 선들이 플래그 위에 겹쳐 그려지면서 화면 전체를 덮어버리는 "가리는 모션"이 되는 구조로 파악된다. 즉 플래그 자체는 정상적으로 그려지지만, 그 위에 검정 선을 26번 덧그리는 별도 루프가 실행되어 결과적으로 안 보이게 되는 것이다.

### 패치 지점을 좁히는 방법
어느 호출이 "가리는" 역할인지는 x64dbg로 `WM_PAINT` 핸들러에 브레이크포인트를 걸고 한 줄씩(Step Into/Step Over) 실행하면서, 검정 선을 긋는 헬퍼 함수가 호출될 때마다 화면이 어떻게 바뀌는지 관찰하면 확인할 수 있다. 헬퍼 함수(위 `sub_140002B80`류)에 들어가면 `GdipCreatePen1` → `GdipDrawLineI` → `GdipSetSmoothingMode` → `GdipDeletePen` 순서로 실행되는 것이 보이고, 이 함수가 상위 함수에서 26번 호출되는 것도 x64dbg의 호출 스택/반복 실행으로 확인 가능하다.

## 화면/코드에서 보이는 징후
- 실행하면 창은 뜨지만 화면이 온통 검정 선으로 덮여 있거나, 그림이 그려지는 도중에 뭔가로 가려지는 애니메이션처럼 보인다.
- IDA Imports 탭에 `GdipCreateFromHDC`, `GdipCreatePen1`, `GdipDrawLineI`, `GdipSetSmoothingMode`, `GdipDeletePen`, `GdipDeleteGraphics`, `GdipFree`가 나열되어 있다.
- WndProc으로 보이는 함수에 `switch`문이 있고 `case`값이 `2`, `0xF`, `0x202` 등 메시지 상수로 보인다.
- 같은 짧은 함수가 좌표 인자만 바뀐 채 반복적으로 호출되는 패턴이 디스어셈블리에 보인다.

## 가장 먼저 할 것
IDA로 Imports 탭을 열어 `Gdip`으로 시작하는 함수를 찾고, 그 함수들을 호출하는 상위 함수(대개 WndProc)까지 Xref(X 키, REV-0145)로 올라간다. WndProc을 찾았으면 `WM_PAINT`(0xF) 분기를 먼저 읽고, 그 안에서 실제 드로잉을 담당하는 서브루틴을 특정한 뒤 x64dbg로 그 서브루틴 진입점에 브레이크포인트를 건다.

## 단계별 절차
1. IDA Imports 탭에서 `Gdip*` 함수들을 확인하고 각각의 Xref를 따라 호출부로 이동한다.
2. WndProc 함수를 찾아 `switch`의 `case` 값을 메시지 상수(WM_DESTROY=2, WM_PAINT=0xF, WM_LBUTTONUP=0x202)로 해석한다.
3. WM_PAINT 분기 안에서 `BeginPaint` → `GdipCreateFromHDC` → 드로잉 서브루틴 호출 → `EndPaint`로 이어지는 흐름을 확인한다.
4. 드로잉 서브루틴 내부에서 반복 호출되는 더 작은 헬퍼 함수(펜 생성 → 선 긋기 → 스무딩 설정 → 펜 삭제)를 찾는다.
5. x64dbg로 실행 파일을 열고 해당 헬퍼 함수 시작 주소에 브레이크포인트를 건 뒤, 몇 번 F9(Run)/F8(Step Over)를 눌러 이 함수가 호출될 때마다 화면에 검정 선이 하나씩 늘어나는지 확인한다.
6. 확인이 되면 x64dbg에서 그 함수의 첫 바이트를 `C3`(RET)으로 우클릭 → Binary → Edit로 패치한다.
7. 패치 후 실행(또는 Save를 눌러 새 exe로 저장 후 재실행)해서 검정 선이 더 이상 그려지지 않고 밑에 있던 그림/문자열이 그대로 드러나는지 확인한다.

## 명령어/단축키
- IDA: `X` — 현재 함수/데이터의 Xref 목록 보기
- IDA: Imports 탭에서 함수 더블클릭 — 해당 API의 stub으로 이동
- x64dbg: `F2` — 현재 주소에 브레이크포인트 설정/해제
- x64dbg: `F9` — Run, `F8` — Step Over, `F7` — Step Into
- x64dbg: 명령어 바이트 위에서 마우스 우클릭 → Binary → Edit(첫 바이트를 `C3`으로 변경)
- x64dbg: Ctrl+G — 특정 주소로 바로 이동(Go to Expression)

## 출력 해석
- 헬퍼 함수 진입 시마다 `GdipCreatePen1`의 반환 핸들 값이 매번 바뀌면, 매 호출마다 새 Pen 객체를 만들고 있다는 뜻이고 이는 "반복되는 덧그리기"라는 가설을 뒷받침한다.
- `GdipDrawLineI`에 전달되는 좌표(x1,y1,x2,y2)가 호출마다 조금씩 달라지면서도 색상 인자가 항상 `0xFF000000`(불투명 검정)으로 고정돼 있다면, 이 호출들이 "가려버리는" 용도라는 확신을 가질 수 있다.
- 패치 후에도 창이 비정상 종료되거나 아예 안 뜬다면, `ret`으로 바꾼 함수가 반환값을 어딘가에 저장해서 쓰는 함수였을 가능성이 있으므로 REV-0601(x64dbg 패치 후 크래시)을 참고해 레지스터 반환값(EAX)을 실패로 인식되지 않는 값으로 맞춰준다.

## 흔한 실수
- 그림이 안 보이는 이유를 "리소스가 암호화됐나?"로 오해하고 REV-0594류의 리소스 암호화 문제로 잘못 접근하는 것 — 이 문제는 리소스가 아니라 런타임에 GDI+로 직접 그리는 방식이라 리소스 섹션(REV-0141)에는 그림 데이터가 없다.
- 반복 호출되는 헬퍼 함수 전체를 통째로 NOP 처리하려다가 명령어 경계를 잘못 잘라 다음 함수 코드까지 깨뜨리는 것 — 함수 맨 앞을 `ret`으로 바꾸는 것이 훨씬 안전하고 간단하다.
- WM_PAINT가 한 번만 호출된다고 가정하고 디버깅을 끝내는 것 — 실제로는 창을 움직이거나 다른 창으로 덮었다가 복귀시키면 WM_PAINT가 여러 번 다시 호출되므로, 패치 없이 여러 번 다시 그려지는 과정을 관찰하는 것이 로직 파악에 도움이 된다.

## 막혔을 때 다음 체크
- 패치한 함수의 시작 주소를 잘못 잡아서 여전히 선이 그려진다면 → REV-0739 IDA Patch Program으로 바이트 수정하기에서 정확한 주소 지정과 저장 방법을 다시 확인한다.
- x64dbg 패치를 저장했는데 실행 시 계속 크래시가 난다면 → REV-0601 x64dbg 패치 후 저장했는데 실행하면 크래시 날 때
- GUI 프로그램의 메시지 루프/서브시스템 개념이 헷갈린다면 → REV-0564 콘솔 프로그램과 GUI 프로그램 서브시스템 차이
- 함수 호출 관계를 코드 상에서 다시 추적하고 싶다면 → REV-0145 IDA Xrefs와 X 키 사용법

## 미니 예제
```text
WndProc(hWnd, uMsg, wParam, lParam):
  switch(uMsg):
    case 2 (WM_DESTROY):
      PostQuitMessage(0)
    case 0xF (WM_PAINT):
      hdc = BeginPaint(hWnd, &ps)
      GdipCreateFromHDC(hdc, &graphics)
      sub_140002C40(graphics)      ; 실제 드로잉 총괄 함수
      GdipDeleteGraphics(graphics)
      GdipFree(...)
      EndPaint(hWnd, &ps)
    case 0x202 (WM_LBUTTONUP):
      InvalidateRect(hWnd, NULL, TRUE)
      UpdateWindow(hWnd)

sub_140002C40(graphics):
  ; 플래그를 구성하는 도형/문자 그리기 (여러 다른 서브루틴 호출)
  ...
  for i in 1..26:
    sub_140002B80(graphics, x1[i], y1[i], x2[i], y2[i], 0xFF000000)  ; 검정 선으로 덮기

sub_140002B80(graphics, x1, y1, x2, y2, color):
  GdipCreatePen1(color, width, unit, &pen)
  GdipDrawLineI(graphics, pen, x1, y1, x2, y2)
  GdipSetSmoothingMode(graphics, 4)
  GdipDeletePen(pen)
```
x64dbg에서 `sub_140002B80`의 첫 바이트를 `C3`(RET)으로 바꾸면 `for` 루프가 26번 돌아도 실제로는 아무 선도 그려지지 않으므로, `sub_140002C40`이 먼저 그려놓은 플래그 그림/문자가 가려지지 않고 그대로 남는다.

## 관련 글
- REV-0739 — IDA Patch Program으로 바이트 수정하기
- REV-0601 — x64dbg 패치 후 저장했는데 실행하면 크래시 날 때
- REV-0564 — 콘솔 프로그램과 GUI 프로그램 서브시스템 차이
- REV-0145 — IDA Xrefs와 X 키 사용법
- REV-0141 — Resource Section과 숨겨진 데이터 확인
- REV-1046 — [Write-up] Long Sleep

## 출처/검증
- 드림핵 워게임 patch(challenges/49) 공식 페이지: 문제 힌트에 "GDI+", "Graphics Functions", x64dbg 공식 문서 참고가 명시되어 있음(2026-09-10 접속 확인, 로그인 필요 구간은 접근하지 않음).
- WndProc/WM_PAINT 처리와 GDI+ 헬퍼 함수(펜 생성-선 긋기-삭제) 구조, 26회 반복 호출 패턴: velog.io/@mm0ck3r/Dreamhack-patch write-up의 분석 내용을 참고해 새로 서술함(원문 인용 없음).
- WM_PAINT 핸들러에서 BeginPaint/EndPaint 사이에 GdipAlloc/GdipCreateFromHDC가 호출된다는 구조: velog.io/@choiyj/Dreamhack-patchReversing write-up을 참고해 새로 서술함.
- 이 write-up은 문제를 직접 실행/디버깅해 검증한 것이 아니라 공개된 두 write-up의 분석 결과를 종합·재서술한 것이며, 정확한 함수 주소(`sub_140002B80` 등)와 반복 횟수(26회)는 원문 저자의 IDA 분석 결과를 그대로 인용한 값이므로 실제 바이너리 버전에 따라 달라질 수 있다.
