"""GUI 문구 다국어 (한국어 / English / 中文).

게임 데이터 이름(오퍼레이터, 맹약, 보스)은 게임 표기(중국어) 그대로 둔다.
"""
from __future__ import annotations

LANGUAGES = {"ko": "한국어", "en": "English", "zh": "中文"}

_S: dict[str, dict[str, str]] = {
    # 조작 창
    "app_title": {"ko": "위수 협의 오버레이", "en": "Stronghold Overlay", "zh": "卫戍协议悬浮窗"},
    "strategy_pick": {"ko": "전략 (자동 감지 실패 시 수동 선택)", "en": "Strategy (pick manually if not detected)",
                      "zh": "策略（未识别时可手动选择）"},
    "auto_detect": {"ko": "(자동 감지)", "en": "(auto detect)", "zh": "（自动识别）"},
    "open_settings": {"ko": "설정", "en": "Settings", "zh": "设置"},
    "data_date": {"ko": "PRTS 데이터: {d}", "en": "PRTS data: {d}", "zh": "PRTS数据：{d}"},
    "status_wait": {"ko": "게임 창을 찾는 중… ({t})", "en": "Looking for game window… ({t})", "zh": "正在寻找游戏窗口…（{t}）"},
    "status_ok": {"ko": "인식 중: {s}", "en": "Tracking: {s}", "zh": "识别中：{s}"},
    "screen_unknown": {"ko": "기타 화면", "en": "other screen", "zh": "其他界面"},
    "screen_match_info": {"ko": "본국 정보", "en": "match info", "zh": "本局信息"},
    "screen_strategy": {"ko": "전략 선택", "en": "strategy select", "zh": "选择策略"},
    "screen_battle": {"ko": "전투/상점", "en": "battle/shop", "zh": "战斗/商店"},
    # 설정 창
    "settings_title": {"ko": "설정", "en": "Settings", "zh": "设置"},
    "tab_general": {"ko": "일반", "en": "General", "zh": "常规"},
    "tab_operators": {"ko": "선호 오퍼레이터", "en": "Preferred operators", "zh": "偏好干员"},
    "tab_alliances": {"ko": "선호 맹약", "en": "Preferred alliances", "zh": "偏好盟约"},
    "tab_presets": {"ko": "전략 프리셋", "en": "Strategy presets", "zh": "策略预设"},
    "tab_notes": {"ko": "보스 메모", "en": "Boss notes", "zh": "领袖备注"},
    "language": {"ko": "언어", "en": "Language", "zh": "语言"},
    "window_title": {"ko": "게임 창 제목", "en": "Game window title", "zh": "游戏窗口标题"},
    "interval": {"ko": "인식 간격", "en": "Scan interval", "zh": "识别间隔"},
    "search": {"ko": "검색 (이름 / 맹약)", "en": "Search (name / alliance)", "zh": "搜索（名称／盟约）"},
    "only_checked": {"ko": "선택한 것만 보기", "en": "Show selected only", "zh": "仅显示已选"},
    "selected_n": {"ko": "{n}개 선택됨", "en": "{n} selected", "zh": "已选 {n} 个"},
    "clear": {"ko": "모두 해제", "en": "Clear all", "zh": "全部取消"},
    "ops_hint": {"ko": "상점에 이 이름이 나오면 노란 테두리로 표시합니다. 원형 카드(Sharp, Misery 등)도 이름으로 고를 수 있습니다.",
                 "en": "Shop cards with these names get a yellow border. Prototype cards (Sharp, Misery…) can be picked by name too.",
                 "zh": "商店出现这些名称时以黄色边框标示。原型卡（Sharp、Misery 等）也可按名称选择。"},
    "alliances_hint": {"ko": "선호 맹약이 이번 판에 밴되면 경고합니다.",
                       "en": "You will be warned when a preferred alliance is banned this match.",
                       "zh": "偏好盟约在本局被禁用时会提示。"},
    "prototype": {"ko": "원형 카드", "en": "prototype card", "zh": "原型卡"},
    "core": {"ko": "핵심", "en": "Core", "zh": "核心"},
    "extra": {"ko": "부가", "en": "Extra", "zh": "附加"},
    "preset_strategy": {"ko": "전략", "en": "Strategy", "zh": "策略"},
    "preset_hint": {"ko": "이 전략을 고르면 아래 선택이 기본 선호에 더해집니다.",
                    "en": "When this strategy is chosen, the selections below are added to your base preferences.",
                    "zh": "选择该策略时，以下选择会叠加到基础偏好中。"},
    "preset_has": {"ko": "● 설정됨", "en": "● set", "zh": "● 已设置"},
    "note": {"ko": "메모", "en": "Note", "zh": "备注"},
    "boss": {"ko": "보스", "en": "Boss", "zh": "领袖"},
    "save": {"ko": "저장", "en": "Save", "zh": "保存"},
    "cancel": {"ko": "취소", "en": "Cancel", "zh": "取消"},
    "ms": {"ko": " ms", "en": " ms", "zh": " 毫秒"},
    # 오버레이
    "ov_strategy": {"ko": "전략: {l} 【{n}】 HP {hp}", "en": "Strategy: {l} 【{n}】 HP {hp}", "zh": "策略：{l} 【{n}】 生命 {hp}"},
    "ov_strategy_unknown": {"ko": "전략: {l} (PRTS 데이터에 없음)", "en": "Strategy: {l} (not in PRTS data)",
                            "zh": "策略：{l}（PRTS数据中无此项）"},
    "ov_note": {"ko": "  메모: {t}", "en": "  Note: {t}", "zh": "  备注：{t}"},
    "ov_banned": {"ko": "밴(이번 판 미등장): {x}", "en": "Banned this match: {x}", "zh": "本局禁用：{x}"},
    "ov_banned_pref": {"ko": "⚠ 선호 맹약 밴됨: {x}", "en": "⚠ Preferred alliance banned: {x}", "zh": "⚠ 偏好盟约被禁用：{x}"},
    "ov_banned_ops": {"ko": "⚠ 밴 맹약 소속 선호 오퍼레이터: {x}", "en": "⚠ Preferred operators in banned alliances: {x}",
                      "zh": "⚠ 属于禁用盟约的偏好干员：{x}"},
    "ov_boss": {"ko": "보스: {b}  {n}", "en": "Boss: {b}  {n}", "zh": "领袖：{b}  {n}"},
    "ov_boss_multi": {"ko": "보스: {b}? (후보: {c})", "en": "Boss: {b}? (candidates: {c})", "zh": "领袖：{b}？（候选：{c}）"},
    "ov_special": {"ko": "특훈[{g}]: {e}", "en": "Special[{g}]: {e}", "zh": "特训[{g}]：{e}"},
    "ov_more": {"ko": " 외", "en": " …", "zh": " 等"},
}


class Tr:
    def __init__(self, lang: str = "ko") -> None:
        self.lang = lang if lang in LANGUAGES else "ko"

    def __call__(self, key: str, **kw) -> str:
        entry = _S.get(key)
        if entry is None:
            return key
        text = entry.get(self.lang) or entry["en"]
        return text.format(**kw) if kw else text


tr = Tr()


def set_language(lang: str) -> None:
    tr.lang = lang if lang in LANGUAGES else "ko"
