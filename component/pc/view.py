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


def get_primary_attributes(attributes: dict) -> dict:
    """按「中文显示名」归并属性：同义键只留一条，英文键换成中文名。"""
    primary_attributes = {}
    for attr, value in attributes.items():
        if is_hidden_coc_skill(attr):
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


def format_all_attributes(chara_data: dict) -> str:
    output_list = []
    for display_name, (_original_attr, value) in sorted(get_primary_attributes(chara_data.get("attributes", {})).items()):
        output_list.append(f"{display_name}: {format_attribute_display_value(value)}")
    return get_output(
        "pc.show.all",
        name=chara_data["name"],
        attributes="\n".join(output_list)
    )


def format_threshold_attributes(attributes: dict, threshold: int, header_prefix: str = "") -> str:
    output_parts = []
    for display_name, (_attr, value) in sorted(get_primary_attributes(attributes).items()):
        try:
            if value <= threshold:
                continue
        except TypeError:
            continue
        output_parts.append(f"· {display_name}: {format_attribute_display_value(value)}")

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
