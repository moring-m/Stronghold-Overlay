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
==干员数据库==
! {{color|#c5c5c5|Ⅳ}}阶干员
{{卫戍协议/参战干员|干员=仇白|原型=Sharp(卫戍协议)|盟约1=炎|盟约2=灵巧|特质类型=单次叠加|特质1=<获得时>a|特质2=b}}
== 装备数据库 ==
{{:卫戍协议/道具
|类型=装备
|等阶=2
|名称=歌利亚头盔
|售价=2
|效果=【基础】生命+25%<br>{{color|#b78000|【进阶】生命+45%}}
|描述=头盔。
}}
"""


def test_parse_sample():
    d = parse(SAMPLE)
    assert d["alliances"]["炎"]["type"] == "core"
    assert d["alliances"]["炎"]["operators"] == ["仇白", "老鲤"]
    assert d["alliances"]["灵巧"]["type"] == "extra"
    assert d["strategies"][0]["name"] == "众志合一" and d["strategies"][0]["hp"] == "25"
    assert d["operators"]["仇白"] == {"tier": "Ⅳ", "prototype": "Sharp", "alliances": ["炎", "灵巧"],
                                     "trait_type": "单次叠加", "trait": "<获得时>a", "trait_adv": "b"}
    assert d["equipment"]["歌利亚头盔"] == {"tier": "Ⅱ", "price": "2", "effect": "生命+25%",
                                         "effect_adv": "生命+45%", "desc": "头盔。"}


def test_helpers():
    assert plain("a{{color|#fff|B}}<br>c") == "aB\nc"
    assert templates("{{x|a={{y|1}}|b=2}}", "x") == [{"a": "{{y|1}}", "b": "2"}]
