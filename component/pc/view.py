import re
from typing import Iterable, List

from ..common.output import get_output
from .attributes import (
    SYNONYMS,
    find_attribute_key,
    format_attribute_display_value,
    get_attribute_display_name,
)
from .store import is_hidden_coc_skill

# 说明性信息（上限、阈值、本章累计、状态位）排在属性列表最后，顺序固定。
COC_TAIL_DISPLAY_ORDER = (
    "体力上限",
    "理智上限",
    "魔法上限",
    "异变阈值",
    "本章累计损失",
    "异变",
    "惊骇中",
    "余悸",
    "迷失",
    "安抚已手动加点",
    "安抚本章已用",
)

# 核心属性固定置顶，按此顺序展示；其余属性再按数值从大到小。
COC_PRIMARY_DISPLAY_ORDER = (
    "力量",
    "敏捷",
    "体质",
    "外貌",
    "智力",
    "灵感",
    "意志",
    "教育",
    "体型",
    "幸运",
    "体力",
    "魔法",
    "理智",
)

# 数值属性与说明性信息之间的分隔线
COC_TAIL_SEPARATOR = "——————"

# 与其它属性同义、但卡面上单独占一行的显示名（检定仍按同义键解析）
COC_INDEPENDENT_DISPLAY_NAMES = frozenset({"灵感"})


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def sort_display_attributes(primary_attributes: dict) -> list:
    """
    排序规则：核心属性（力量/敏捷/…/理智）固定置顶且顺序固定；
    其余数值属性从大到小；说明性信息（上限/阈值/累计/状态）统一放到最后。
    返回 [(display_name, original_attr, value), ...]
    """
    primary_items = []
    main_items = []
    tail_items = []
    for display_name, (original_attr, value) in primary_attributes.items():
        item = (display_name, original_attr, value)
        if display_name in COC_TAIL_DISPLAY_ORDER:
            tail_items.append(item)
        elif display_name in COC_PRIMARY_DISPLAY_ORDER:
            primary_items.append(item)
        else:
            main_items.append(item)

    def primary_key(item):
        display_name = item[0]
        return (0, COC_PRIMARY_DISPLAY_ORDER.index(display_name))

    def main_key(item):
        display_name, _attr, value = item
        if _is_number(value):
            return (0, -float(value), display_name)
        # 非数值属性排在数值之后，按名字排
        return (1, 0.0, display_name)

    def tail_key(item):
        display_name = item[0]
        try:
            return (0, COC_TAIL_DISPLAY_ORDER.index(display_name))
        except ValueError:
            return (1, len(COC_TAIL_DISPLAY_ORDER))

    primary_items.sort(key=primary_key)
    main_items.sort(key=main_key)
    tail_items.sort(key=tail_key)
    return primary_items + main_items + tail_items


def get_primary_attributes(attributes: dict) -> dict:
    """按「中文显示名」归并属性：同义键只留一条，英文键换成中文名。"""
    primary_attributes = {}
    for attr, value in attributes.items():
        if is_hidden_coc_skill(attr):
            continue
        # 灵感虽与智力同义（检定仍走智力），但卡面单独占一行
        if str(attr) in COC_INDEPENDENT_DISPLAY_NAMES:
            display_name = str(attr)
            primary_attributes.setdefault(display_name, (attr, value))
            continue
        primary_name = SYNONYMS.SYNONYM_MAP.get(attr, attr)
        if is_hidden_coc_skill(primary_name):
            continue
        display_name = get_attribute_display_name(primary_name)
        if display_name not in primary_attributes:
            primary_attributes[display_name] = (attr, value)
        else:
            current_attr = primary_attributes[display_name][0]
            if current_attr != primary_name and attr == primary_name:
                primary_attributes[display_name] = (attr, value)
    return primary_attributes


def format_sorted_attribute_lines(primary_attributes: dict, bullet: str = "") -> list:
    """
    把属性渲染成文本行：数值部分从大到小，说明性信息统一排在最后，
    两者之间插一条分隔线（某一侧为空时不插线），并顺带按显示名去重。
    """
    lines = []
    seen = set()
    tail_started = False
    for display_name, _attr, value in sort_display_attributes(primary_attributes):
        name = str(display_name).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        if name in COC_TAIL_DISPLAY_ORDER and not tail_started:
            tail_started = True
            if lines:
                lines.append(COC_TAIL_SEPARATOR)
        lines.append(f"{bullet}{name}: {format_attribute_display_value(value)}")
    return lines


def format_all_attributes(chara_data: dict) -> str:
    output_list = format_sorted_attribute_lines(
        get_primary_attributes(chara_data.get("attributes", {}))
    )
    return get_output(
        "pc.show.all",
        name=chara_data["name"],
        attributes="\n".join(output_list)
    )


def format_threshold_attributes(attributes: dict, threshold: int, header_prefix: str = "") -> str:
    """筛选数值 > threshold 的属性；上限／阈值／状态等说明性条目不参与筛选。"""
    above_threshold = {
        display_name: pair
        for display_name, pair in get_primary_attributes(attributes).items()
        if str(display_name).strip() not in COC_TAIL_DISPLAY_ORDER
        and _is_number(pair[1])
        and pair[1] > threshold
    }
    output_parts = format_sorted_attribute_lines(above_threshold, bullet="· ")

    if not output_parts:
        return get_output("pc.show.none_above", num=threshold)

    header = get_output("pc.show.above_threshold_header", num=threshold)
    return header_prefix + header + "\n" + "\n".join(output_parts)


def format_named_attributes(chara_data: dict, keys: Iterable[str], header_prefix: str = "") -> str:
    attributes = chara_data.get("attributes", {})
    found_attrs: List[str] = []
    not_found_attrs: List[str] = []

    for key in keys:
        if is_hidden_coc_skill(key):
            not_found_attrs.append(key)
            continue
        resolved_key = find_attribute_key(attributes, key)
        if resolved_key is not None:
            found_attrs.append(get_output(
                "pc.show.attr",
                attr=get_attribute_display_name(resolved_key),
                value=format_attribute_display_value(attributes[resolved_key]),
            ))
        elif key not in chara_data.get("name", ""):
            not_found_attrs.append(key)

    output_parts = []
    if header_prefix:
        output_parts.append(header_prefix.rstrip("\n"))
    if found_attrs:
        output_parts.append("\n".join(found_attrs))
    if not_found_attrs:
        output_parts.append(get_output("pc.show.attr_missing", attribute=", ".join(not_found_attrs)))

    return "\n".join(output_parts)


def clean_st_show_words(args_str: str, chara_name: str) -> List[str]:
    base_str = args_str.split("@")[0] if "@" in args_str else args_str
    clean_text = re.sub(r"\[CQ:at.*?\]", " ", base_str)
    valid_words = []

    for word in clean_text.split():
        upper_word = word.upper()
        if word.startswith("@"):
            continue
        if "HP:" in upper_word or "SAN:" in upper_word or "DEX:" in upper_word:
            continue
        if re.match(r"^\d+/\d+$", word):
            continue
        if word == chara_name:
            continue
        valid_words.append(word)

    return valid_words
