import random
import re
import os
import json

from ..common.output import get_output

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ===== 修订版规则常量（改规则只改这里）=====
# 单次理智损失达到该值触发惊骇检定（INT）。
SHOCK_TRIGGER_LOSS = 5
# 已异变（changed）的角色因「异变期间更难陷入惊骇」，触发阈值翻倍。
SHOCK_TRIGGER_LOSS_CHANGED = 10
# 安抚成功恢复的理智值。
SOOTHE_SAN_GAIN = 2
# 安抚大失败的理智损失骰面数：p.23 技能条目写 1D4，p.93 写 1D6，KP 裁定取 1D4。
SOOTHE_FUMBLE_SAN_LOSS_DIE = 4

# 恐惧
with open(PLUGIN_DIR + "/../data/phobias.json", "r", encoding="utf-8") as f:
    phobias = json.load(f)["phobias"]

# 躁狂
with open(PLUGIN_DIR + "/../data/mania.json", "r", encoding="utf-8") as f:
    manias = json.load(f)["manias"]

LOSS_TERM = re.compile(r"([0-9]+)d([0-9]+)([+-][0-9]+)?")

def is_valid_loss_term(term) -> bool:
    """单个损失项是否合法：纯数字或 XdY[+-N]。"""
    text = "" if term is None else str(term).strip().lower()
    if not text:
        return False
    return text.isdigit() or bool(LOSS_TERM.fullmatch(text))

def is_valid_loss_formula(formula) -> bool:
    """
    判断理智损失公式是否可用：成功/失败两段都必须是合法损失项。
    例如 "1d6/1d10"、"1/1d6"、"0" 合法；""、"abc"、"1d6/" 非法。
    """
    text = "" if formula is None else str(formula).strip().lower()
    if not text:
        return False
    parts = [part.strip() for part in text.split("/")]
    if len(parts) > 2:
        return False
    return all(is_valid_loss_term(part) for part in parts)

def parse_san_loss_formula(formula: str):
    """
    解析 SAN 损失公式，返回成功和失败时的损失表达式。
    例如 "1d6/1d10" -> ("1d6", "1d10")
    例如 "1d6+1/1d10-1" -> ("1d6+1", "1d10-1")
    """
    text = "" if formula is None else str(formula).strip().lower()
    if not text:
        raise ValueError("Empty san loss formula")
    parts = [part.strip() for part in text.split("/")]
    
    # 成功部分就是分隔符前的部分
    success_part = parts[0]
    
    # 如果包含 '/', 则失败部分是 '/' 后的部分
    # 否则失败部分和成功部分相同
    failure_part = parts[1] if len(parts) > 1 else parts[0]
    
    if not is_valid_loss_term(success_part) or not is_valid_loss_term(failure_part):
        raise ValueError(f"Invalid san loss formula: {formula}")

    return success_part, failure_part

def roll_loss(loss_expr: str):
    """
    根据损失表达式计算损失值，并返回计算过程。
    支持 "XdY" 或纯数字，并支持加法和减法运算。
    例如： "1d6", "1d6+1", "1d6-2"
    """
    # 处理加法和减法
    expr_text = "" if loss_expr is None else str(loss_expr).strip().lower()
    match = LOSS_TERM.fullmatch(expr_text)
    if match:
        num_dice, dice_size, modifier = match.groups()
        num_dice = int(num_dice)
        dice_size = int(dice_size)
        modifier = int(modifier) if modifier else 0

        # 计算骰子结果
        dice_results = [random.randint(1, dice_size) for _ in range(num_dice)]
        dice_total = sum(dice_results)

        # 总损失计算
        total_loss = dice_total + modifier

        # 确保损失不会小于0
        total_loss = max(0, total_loss)

        # 构造计算过程表达式
        if modifier != 0:
            # 处理减法时不显示 "+ -"，只显示 "-"
            if modifier > 0:
                expr = f"[{dice_total} + {modifier}] = {total_loss}"
            else:
                expr = f"[{dice_total} - {-modifier}] = {total_loss}"
        else:
            # 没有modifier时，只返回骰子的总和
            expr = f"{dice_total}"

        # 返回损失值和计算过程
        return total_loss, expr
    
    # 纯数字情况，直接返回
    elif expr_text.isdigit():
        loss = int(expr_text)
        return max(0, loss), f"{loss}"

    # 走到这里说明公式不可用：明确报错，不再返回 None 让调用方 unpack 崩掉
    raise ValueError(f"Invalid san loss expression: {loss_expr}")

def san_check(chara_data: dict, loss_formula: str):
    """
    进行一次理智检定，返回检定结果和损失值。
    chara_data: 当前人物卡数据（需包含'san'属性）
    loss_formula: 损失公式，如 "1d6/1d10"
    返回：(roll_result, san_value, result_msg, loss, new_san)
    """
    san_value = chara_data["attributes"].get("san", 0)
    roll_result = random.randint(1, 100)
    success_loss, failure_loss = parse_san_loss_formula(loss_formula)

    if roll_result <= san_value:
        loss, expr = roll_loss(success_loss)
        result_msg = get_output("san.result.success")
        succ = True
    else:
        loss, expr = roll_loss(failure_loss)
        result_msg = get_output("san.result.failure")
        succ = False

    new_san = max(0, san_value - loss)
    return roll_result, san_value, result_msg, loss, new_san, expr

def get_temporary_insanity(phobias: dict, manias: dict):
    """
    随机生成临时疯狂症状，返回症状文本。
    phobias, manias: 恐惧症和躁狂症字典
    """
    temporary_insanity = {i: get_output(f"san.temporary.{i}") for i in range(1, 11)}
    roll = random.randint(1, 10)
    result = temporary_insanity[roll].replace("1D10", str(random.randint(1, 10)))
    if roll == 9:
        fear_roll = random.randint(1, 100)
        result += "\n" + get_output("san.specific_phobia", phobia=phobias[str(fear_roll)], roll=fear_roll)
    if roll == 10:
        mania_roll = random.randint(1, 100)
        result += "\n" + get_output("san.specific_mania", mania=manias[str(mania_roll)], roll=mania_roll)
    return result

def get_long_term_insanity(phobias: dict, manias: dict):
    """
    随机生成长期疯狂症状，返回症状文本。
    phobias, manias: 恐惧症和躁狂症字典
    """
    long_term_insanity = {i: get_output(f"san.long_term.{i}") for i in range(1, 11)}
    roll = random.randint(1, 10)
    result = long_term_insanity[roll].replace("1D10", str(random.randint(1, 10)))
    if roll == 9:
        fear_roll = random.randint(1, 100)
        result += "\n" + get_output("san.specific_phobia", phobia=phobias[str(fear_roll)], roll=fear_roll)
    if roll == 10:
        mania_roll = random.randint(1, 100)
        result += "\n" + get_output("san.specific_mania", mania=manias[str(mania_roll)], roll=mania_roll)
    return result
