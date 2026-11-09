import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from sync_prts import parse, plain, templates  # noqa: E402

SAMPLE = """==S.W.E.E.P.盟约报告==
=== 核心盟约 ===
{{卫戍协议/盟约|盟约=炎|人数=3|效果=【炎】攻击力{{color|#0098DC|+23%}}<br>说明|干员={{干员头像|仇白|60px}}{{干员头像|老鲤|60px}}}}
=== 附加盟约 ===
{{卫戍协议/盟约|盟约=灵巧|人数=2|效果=x|干员={{干员头像|仇白|60px}}}}
==S.W.E.E.P.策略报告==
{{:卫戍协议/策略
|发起人=阿米娅
|策略=众志合一
|血量=25
|效果={{color|#40B196|被动效果}}：说明
}}
==敌方资料==
=== 领袖 ===
| {{敌人头像|假想敌：铳|px=60}}<br>假想敌：铳
=== 战术特训敌人 ===
|-
|style="color:white"|{{popup|图标=x|内容=y}}<br>飞行
|{{敌人头像|妖怪|px=60}}{{敌人头像|威龙|px=60}}
|}
==干员数据库==
! {{color|#c5c5c5|Ⅳ}}阶干员
{{卫戍协议/参战干员|干员=仇白|原型=Sharp(卫戍协议)|盟约1=炎|盟约2=灵巧|特质1=a|特质2=b}}
"""


def test_parse_sample():
    d = parse(SAMPLE)
    assert d["alliances"]["炎"]["type"] == "core"
    assert d["alliances"]["炎"]["operators"] == ["仇白", "老鲤"]
    assert d["alliances"]["灵巧"]["type"] == "extra"
    assert d["strategies"][0]["name"] == "众志合一" and d["strategies"][0]["hp"] == "25"
    assert d["bosses"] == ["假想敌：铳"]
    assert d["special_enemies"] == {"飞行": ["妖怪", "威龙"]}
    assert d["operators"]["仇白"] == {"tier": "Ⅳ", "prototype": "Sharp",
                                     "alliances": ["炎", "灵巧"], "trait": "b"}


def test_helpers():
    assert plain("a{{color|#fff|B}}<br>c") == "aB\nc"
    assert templates("{{x|a={{y|1}}|b=2}}", "x") == [{"a": "{{y|1}}", "b": "2"}]
