# Stronghold Overlay

명일방주 중국 PC 클라이언트 **위수 협의(卫戍协议)** 전용 화면 인식 오버레이 (Windows).

게임 메모리나 패킷은 건드리지 않습니다. 창을 캡처한 뒤 OCR로 화면을 읽고, 투명 창(클릭 통과)에 정보를 표시합니다. 자동 클릭 기능은 없습니다.

## 기능
| 화면 | 동작 |
|---|---|
| 1/3 确认本局信息 | 활성 맹약과 **밴(회색) 맹약**을 감지합니다. 선호 맹약이나 밴된 맹약에 속한 선호 오퍼레이터가 있으면 경고합니다. **보스**는 초상화를 PRTS 이미지와 비교해 식별합니다(OCR이 읽지 못하는 한자 대비). **특훈 적** 분류별 적 목록도 표시합니다. |
| 2/3 选择策略 | 오른쪽 상세 패널의 발기인 이름(예: 阿米娅)을 읽어 PRTS 전략(【众志合一】, HP, 효과)을 표시하고, 같은 이름의 프리셋으로 선호를 전환합니다. 조작 창에서 직접 고를 수도 있습니다. |
| 전투/상점 | 카드 6칸의 **오퍼레이터 이름만** 읽어 선호 오퍼레이터 칸을 **노란 테두리**로 표시합니다. 미보유 시 나오는 원형 카드는 표시 이름(Sharp, Misery 등) 그대로 비교하므로, 원하면 선호 목록에 `Sharp`처럼 넣으세요. |

## 데이터: PRTS 위키
위수 협의 정보(맹약과 소속 오퍼레이터, 전략, 보스, 특훈 적, 오퍼레이터 등급/원형)는 [PRTS 위키](https://prts.wiki/w/卫戍协议·规程/PRTS盟约记录)에서 가져옵니다.

```
python tools/sync_prts.py                       # data/prts_stronghold.json, data/bosses/*.png 갱신
python tools/sync_prts.py --page "<새 시즌>/PRTS盟约记录"
```
OCR 결과(맹약, 오퍼레이터 이름)의 오타는 이 데이터로 보정합니다.

## 실행 방법 (Windows)
1. **Python 3.10 이상 설치:** [python.org](https://www.python.org/downloads/)에서 받아 설치합니다. 설치 화면에서 **"Add python.exe to PATH"를 꼭 체크**하세요.
2. **코드 받기:** GitHub 저장소에서 `ccr-bb857231-z090js` 브랜치를 선택하고 **Code → Download ZIP**으로 받아 압축을 풉니다. git을 쓴다면 아래처럼 받습니다.
   ```
   git clone -b ccr-bb857231-z090js https://github.com/moring-m/Stronghold-Overlay.git
   ```
3. **명령 프롬프트 열기:** 압축을 푼 폴더(`README.md`가 있는 곳)의 주소창에 `cmd`를 입력하고 Enter를 누릅니다.
4. **설치 (처음 한 번만):**
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
5. **실행:** 게임을 **16:9 창 모드**로 켜 둔 상태에서 실행합니다.
   ```
   .venv\Scripts\activate
   python -m stronghold_overlay
   ```
   - 작은 "Stronghold Overlay" 조작 창이 뜨고, 게임 화면을 인식하면 게임 창 위에 정보가 겹쳐 표시됩니다.
   - 처음 실행할 때는 OCR 모델을 불러오느라 몇 초 걸립니다.
   - 끝낼 때는 조작 창을 닫습니다.
6. **선호 설정:** 조작 창의 **"설정 파일 열기"**를 누르면 `data/user_settings.json`이 열립니다. 오퍼레이터 이름을 게임 표기(중국어) 그대로 적고 저장한 뒤 프로그램을 다시 실행하세요.
   ```json
   "base_operators": ["忍冬", "复奏", "Sharp"],
   "presets": { "阿米娅": { "operators": ["承曦格雷伊"], "alliances": [], "note": "" } }
   ```
   `presets`의 키는 전략 선택 화면에 보이는 발기인 이름(또는 전략 이름)입니다. 그 전략을 고르면 해당 오퍼레이터가 선호 목록에 더해집니다.

**문제가 생기면**
- 오버레이가 안 뜨면: 게임이 전체 화면이 아닌 창 모드인지 확인하세요. 게임을 관리자 권한으로 실행했다면 cmd도 관리자 권한으로 여세요.
- 테두리 위치가 어긋나면: 게임 창 비율이 16:9인지 확인하세요.

## OCR 속도 (참고: 클라우드 4코어 CPU, 1353x761)
| 처리 | 시간 |
|---|---|
| 전체 화면 (화면 판별, 맹약/보스, 전략) | 약 0.4~0.6초 (+ 보스 초상화 매칭 약 0.05초) |
| 상점 이름 6칸만 (전투 중 기본 동작, 5회 중 1회는 전체 화면) | 약 0.29초 |

## 설정 (`data/presets.json` → 조작 창 "설정 파일 열기"로 열면 `data/user_settings.json`)
- `base_operators` / `base_alliances`: 항상 적용되는 선호 오퍼레이터와 맹약 (PRTS 표기)
- `presets`: `"발기인 또는 전략 이름": {operators, alliances, note}` 형식입니다. 예: `"阿米娅"`, `"众志合一"`
- `enemy_notes`: 보스 이름별 메모

## 알려진 한계
- 한 글자 맹약 라벨(예: 炎)은 OCR이 놓칠 수 있습니다.
- 좌표는 1353x761 스크린샷 기준 비율값입니다(`detectors.py` 상단 상수).
