"""GUI 문구 다국어 (한국어 / English / 中文).

게임 데이터 이름(오퍼레이터, 맹약, 보스)은 게임 표기(중국어) 그대로 둔다.
"""
from __future__ import annotations

LANGUAGES = {"ko": "한국어", "en": "English", "zh": "中文"}

_S: dict[str, dict[str, str]] = {
    # 조작 창
    "app_title": {"ko": "위수 협의 오버레이", "en": "Stronghold Overlay", "zh": "卫戍协议悬浮窗"},
    "strategy_pick": {"ko": "이번 판 전략", "en": "Strategy this match", "zh": "本局策略"},
    "auto_detect": {"ko": "(자동 감지)", "en": "(auto detect)", "zh": "（自动识别）"},
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
    "language": {"ko": "언어", "en": "Language", "zh": "语言"},
    "window_title": {"ko": "게임 창 제목", "en": "Game window title", "zh": "游戏窗口标题"},
    "interval": {"ko": "인식 간격", "en": "Scan interval", "zh": "识别间隔"},
    "only_checked": {"ko": "선택한 것만 보기", "en": "Show selected only", "zh": "仅显示已选"},
    "clear": {"ko": "모두 해제", "en": "Clear all", "zh": "全部取消"},
    "ops_hint": {"ko": "카드를 눌러 선택하세요. 선택한 오퍼레이터가 상점에 나오면 노란 테두리로 표시됩니다. ⓘ로 특질을 봅니다.",
                 "en": "Click cards to select. Selected operators get a yellow border in the shop. ⓘ shows the trait.",
                 "zh": "点击卡片进行选择。所选干员出现在商店时以黄色边框标示。ⓘ 查看特质。"},
    "alliances_hint": {"ko": "선호 맹약이 이번 판에 밴되면 게임 화면에 알림이 뜹니다.",
                       "en": "You get a notification when a preferred alliance is banned this match.",
                       "zh": "偏好盟约在本局被禁用时会弹出提示。"},
    "prototype": {"ko": "원형 카드", "en": "prototype card", "zh": "原型卡"},
    "core": {"ko": "핵심", "en": "Core", "zh": "核心"},
    "extra": {"ko": "부가", "en": "Extra", "zh": "附加"},
    "preset_hint": {"ko": "게임에서 이 전략을 고르면 아래에서 고른 오퍼레이터·장비·맹약이 선호에 더해집니다. ●는 설정된 전략입니다.",
                    "en": "When you pick this strategy in game, the operators, equipment and alliances below are added to your preferences. ● marks strategies with a preset.",
                    "zh": "在游戏中选择该策略时，下方所选干员、装备与盟约会加入偏好。● 表示已设置的策略。"},
    "note": {"ko": "메모", "en": "Note", "zh": "备注"},
    # 설정 패널 / 선택기
    "search_ops": {"ko": "이름·맹약 검색 (한/中/EN)", "en": "Search name or alliance (EN/中/한)", "zh": "搜索名称或盟约（中/EN/한）"},
    "no_result": {"ko": "조건에 맞는 오퍼레이터가 없습니다.", "en": "No operators match.", "zh": "没有符合条件的干员。"},
    "selected": {"ko": "선택", "en": "selected", "zh": "已选"},
    "tier_n": {"ko": "{n}단계", "en": "Tier {n}", "zh": "{n} 阶"},
    "tier": {"ko": "단계", "en": "Tier", "zh": "阶级"},
    "all": {"ko": "전체", "en": "All", "zh": "全部"},
    "all_core": {"ko": "전체 핵심 맹약", "en": "All core alliances", "zh": "全部核心盟约"},
    "all_extra": {"ko": "전체 부가 맹약", "en": "All extra alliances", "zh": "全部附加盟约"},
    "core_alliances": {"ko": "핵심 맹약", "en": "Core alliances", "zh": "核心盟约"},
    "extra_alliances": {"ko": "부가 맹약", "en": "Extra alliances", "zh": "附加盟约"},
    "members_n": {"ko": "오퍼레이터 {n}명", "en": "{n} operators", "zh": "{n} 名干员"},
    "clear_confirm": {"ko": "선택을 모두 해제할까요?", "en": "Clear all selections?", "zh": "要取消全部选择吗？"},
    "close_hint": {"ko": "닫기 (Esc)", "en": "Close (Esc)", "zh": "关闭（Esc）"},
    "strategy_search": {"ko": "전략 검색", "en": "Search strategy", "zh": "搜索策略"},
    "note_placeholder": {"ko": "메모를 입력하세요", "en": "Write a note", "zh": "输入备注"},
    "operators": {"ko": "오퍼레이터", "en": "Operators", "zh": "干员"},
    "alliances": {"ko": "맹약", "en": "Alliances", "zh": "盟约"},
    "speed_fast": {"ko": "빠르게 ({ms}ms, CPU 사용 많음)", "en": "Fast ({ms} ms, more CPU)", "zh": "快（{ms} 毫秒，CPU 占用高）"},
    "speed_normal": {"ko": "보통 ({ms}ms, 권장)", "en": "Normal ({ms} ms, recommended)", "zh": "标准（{ms} 毫秒，推荐）"},
    "speed_slow": {"ko": "느리게 ({ms}ms, CPU 절약)", "en": "Slow ({ms} ms, saves CPU)", "zh": "慢（{ms} 毫秒，节省 CPU）"},
    "saved": {"ko": "✓ 저장됨", "en": "✓ Saved", "zh": "✓ 已保存"},
    # 트레이 / 오버레이 버튼
    "tray_settings": {"ko": "설정 열기", "en": "Open settings", "zh": "打开设置"},
    "tray_overlay": {"ko": "오버레이 표시", "en": "Show overlay", "zh": "显示悬浮窗"},
    "tray_language": {"ko": "언어", "en": "Language", "zh": "语言"},
    "tray_quit": {"ko": "종료", "en": "Quit", "zh": "退出"},
    "tray_started": {"ko": "트레이에서 실행 중입니다. 아이콘 더블클릭 또는 {s}로 설정을 엽니다.",
                     "en": "Running in the tray. Double-click the icon or press {s} to open settings.",
                     "zh": "已在托盘中运行。双击图标或按 {s} 打开设置。"},
    "tray_log": {"ko": "로그 폴더 열기", "en": "Open log folder", "zh": "打开日志文件夹"},
    "status_paused": {"ko": "일시정지됨", "en": "Paused", "zh": "已暂停"},
    "toast_preset": {"ko": "전략 프리셋 적용: {l} 【{n}】", "en": "Strategy preset applied: {l} 【{n}】",
                     "zh": "已应用策略预设：{l} 【{n}】"},
    "toast_banned": {"ko": "선호 맹약이 이번 판에 밴됨: {x}", "en": "Preferred alliance banned this match: {x}",
                     "zh": "偏好盟约本局被禁用：{x}"},
    "tab_equipment": {"ko": "선호 장비", "en": "Preferred equipment", "zh": "偏好装备"},
    "items_hint": {"ko": "카드를 눌러 선택하세요. 선택한 장비가 상점에 나오면 노란 테두리로 표시됩니다. ⓘ로 효과를 봅니다.",
                   "en": "Click cards to select. Selected equipment gets a yellow border in the shop. ⓘ shows its effect.",
                   "zh": "点击卡片进行选择。所选装备出现在商店时以黄色边框标示。ⓘ 查看效果。"},
    "search_items": {"ko": "장비 이름 검색 (한/中)", "en": "Search equipment (한/中)", "zh": "搜索装备（中/한）"},
    "equipment": {"ko": "장비", "en": "Equipment", "zh": "装备"},
    "price_n": {"ko": "가격 {n}", "en": "Cost {n}", "zh": "售价 {n}"},
    "trait": {"ko": "특질", "en": "Trait", "zh": "特质"},
    "effect": {"ko": "효과", "en": "Effect", "zh": "效果"},
    "prototype_desc": {"ko": "해당 오퍼레이터를 보유하지 않았을 때 상점에 대신 나오는 원형 카드입니다.",
                       "en": "Shown in the shop in place of an operator you don't own.",
                       "zh": "未持有对应干员时在商店中代替出现的原型卡。"},
    "opacity": {"ko": "설정 창 불투명도", "en": "Panel opacity", "zh": "设置窗口不透明度"},
    "notify": {"ko": "알림", "en": "Notifications", "zh": "提示"},
    "notify_desc": {"ko": "전략 프리셋 적용, 선호 맹약 밴을 게임 화면에 잠깐 표시", "en": "Briefly show preset applied / preferred alliance banned",
                    "zh": "在游戏画面短暂显示预设应用与偏好盟约禁用"},
    "autostart": {"ko": "자동 실행", "en": "Autostart", "zh": "开机启动"},
    "autostart_desc": {"ko": "Windows 시작 시 실행", "en": "Start with Windows", "zh": "随 Windows 启动"},
    "hotkeys": {"ko": "단축키", "en": "Hotkeys", "zh": "快捷键"},
    "hotkeys_desc": {"ko": "설정 열기/닫기 {s} · 오버레이 켜기/끄기 {o}", "en": "Settings {s} · Toggle overlay {o}",
                     "zh": "打开/关闭设置 {s} · 开关悬浮窗 {o}"},
    "gear_tip": {"ko": "오버레이 설정", "en": "Overlay settings", "zh": "悬浮窗设置"},
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
