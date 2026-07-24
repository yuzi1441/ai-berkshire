from pathlib import Path
path = Path(r"E:\ai-berkshire\tools\build_investment_dashboard.py")
text = path.read_text(encoding="utf-8")

old = '''    def heading_score(line: str, level: int) -> int:
        score = 0
        if re.search(r"估值与安全边际", line):
            score = 100
        elif re.search(r"财务质量与估值|估值与价格纪律", line):
            score = 90
        elif re.search(r"估值与行动|估值锚点|估值判断", line):
            score = 88
        elif re.search(r"最终投资建议|分层操作建议|分层价格区间", line):
            score = 82
        elif re.search(r"行动价格带|价格区间建议|合理价格区间|什么价位", line):
            score = 75
        elif re.search(r"三情景估值|情景估值|压力测试|反向估值", line):
            score = 68
        elif re.search(r"估值更新|估值复核", line):
            score = 58
        elif re.search(r"财务估值|估值基准|估值分析|估值", line) and level <= 3:
            score = 45 if re.search(r"财务估值|估值基准|估值分析", line) else 28
        # Nested tiny fragments should not outrank full chapters.
        if level >= 4:
            score = max(0, score - 15)
        return score

    def is_related_valuation_heading(line: str) -> bool:
        return bool(
            re.search(
                r"估值|安全边际|情景|价格带|价格区间|目标价|压力测试|反向估值|"
                r"分层操作|分层价格|行动价格|买入价|建仓|操作建议|合理价|"
                r"内在价值|对的价格|安全垫",
                line,
            )
        )

    def is_hard_stop_heading(line: str, level: int, start_level: int) -> bool:
        """Major sections that should end the valuation capture."""
        if level > start_level:
            return False
        # Same-or-higher level related valuation headings are continuations.
        if is_related_valuation_heading(line) and not re.search(
            r"最终决策与行动|第八步|第九步|第十步|附录|数据来源|免责声明|"
            r"风险矩阵|看多 vs|系列总结|参考资料|信息来源|Checklist|论文|"
            r"新闻|跟踪|下一步研究",
            line,
        ):
            return False
        if re.search(
            r"最终决策|行动清单|风险|附录|数据来源|免责|Checklist|论文跟踪|"
            r"新闻脉搏|下一步|信息来源|参考资料|系列总结|研究框架|目录",
            line,
        ):
            return True
        # Generic next major step: 第八步 / 第8部分 without valuation keywords.
        if re.search(r"第[八九十\\d]+[步部分章节]", line) and not is_related_valuation_heading(line):
            return True
        if level <= start_level and not is_related_valuation_heading(line):
            return True
        return False
'''

new = '''    def heading_score(line: str, level: int) -> int:
        score = 0
        if re.search(r"估值与安全边际", line):
            score = 100
        elif re.search(r"财务质量与估值|估值与价格纪律", line):
            score = 90
        elif re.search(r"估值与行动|估值锚点|估值判断", line):
            score = 88
        elif re.search(r"最终决策与行动|最终决策|行动清单", line):
            # Many reports put action price bands in step 8; keep it eligible.
            score = 86
        elif re.search(r"最终投资建议|分层操作建议|分层价格区间", line):
            score = 82
        elif re.search(r"行动价格带|价格区间建议|合理价格区间|什么价位", line):
            score = 75
        elif re.search(r"三情景估值|情景估值|压力测试|反向估值", line):
            score = 68
        elif re.search(r"估值更新|估值复核", line):
            score = 58
        elif re.search(r"财务估值|估值基准|估值分析|估值", line) and level <= 3:
            score = 45 if re.search(r"财务估值|估值基准|估值分析", line) else 28
        # Nested tiny fragments should not outrank full chapters.
        if level >= 4:
            score = max(0, score - 15)
        return score

    def is_decision_action_heading(line: str) -> bool:
        """Step-8 style chapters that often hold the actionable price tables."""
        return bool(
            re.search(
                r"最终决策与行动|最终决策|行动清单|最终投资建议|最终建议|"
                r"操作建议|分层操作|行动价格|价格与动作|价格纪律",
                line,
            )
        )

    def is_related_valuation_heading(line: str) -> bool:
        if is_decision_action_heading(line):
            return True
        return bool(
            re.search(
                r"估值|安全边际|情景|价格带|价格区间|目标价|压力测试|反向估值|"
                r"分层操作|分层价格|行动价格|买入价|建仓|操作建议|合理价|"
                r"内在价值|对的价格|安全垫|第八步",
                line,
            )
        )

    def is_hard_stop_heading(line: str, level: int, start_level: int) -> bool:
        """Major sections that should end the valuation capture."""
        if level > start_level:
            return False
        # Decision/action chapters belong with valuation tables — never hard-stop.
        if is_decision_action_heading(line):
            return False
        # Same-or-higher level related valuation headings are continuations.
        if is_related_valuation_heading(line):
            return False
        if re.search(
            r"附录|数据来源|免责|Checklist|论文跟踪|新闻脉搏|下一步研究|"
            r"信息来源|参考资料|系列总结|研究框架|目录|风险矩阵|看多 vs|"
            r"第九步|第十步|第9部分|第10部分",
            line,
        ):
            return True
        # Bare "风险" section without valuation wording ends the capture.
        if re.search(r"风险", line) and not is_related_valuation_heading(line):
            return True
        # Generic next major step after decision chapter, without price content.
        if re.search(r"第[九九十\\d]+[步部分章节]", line):
            return True
        if level <= start_level and not is_related_valuation_heading(line):
            return True
        return False
'''

# Fix double escaping - the file uses single backslash in regex
old = old.replace("\\\\d", "\\d")
new = new.replace("\\\\d", "\\d")

if old not in text:
    # show snippet
    idx = text.find("def heading_score")
    print("found heading_score at", idx)
    print(repr(text[idx:idx+200]))
    raise SystemExit("block not found")

text = text.replace(old, new, 1)

# After primary end is found, force-include trailing decision section if present
# Find the section that sets end from hard_stop and add post-pass

marker = '''    # Primary end: next hard-stop heading at same or higher level.
    end = len(lines)
    for index in range(start + 1, len(lines)):
        level = heading_level(lines[index])
        if level is None:
            continue
        if is_hard_stop_heading(lines[index], level, start_level):
            end = index
            break
'''

# Need to read actual file content after first replace for the rest of function
path.write_text(text, encoding="utf-8")
text = path.read_text(encoding="utf-8")

# Add post-extension after the while expand loop, before body = lines[start:end]
insert_before = "    body = lines[start:end]"
post = '''    # Always try to append the following decision/action chapter when present.
    # Many full-research reports put price bands under 「第八步：最终决策与行动清单」.
    peek = end
    while peek < len(lines) and not lines[peek].strip():
        peek += 1
    if peek < len(lines):
        peek_level = heading_level(lines[peek])
        if peek_level is not None and is_decision_action_heading(lines[peek]):
            decision_end = len(lines)
            for index in range(peek + 1, len(lines)):
                level = heading_level(lines[index])
                if level is not None and level <= peek_level and not is_decision_action_heading(lines[index]):
                    if is_hard_stop_heading(lines[index], level, start_level) or level <= start_level:
                        decision_end = index
                        break
            end = max(end, decision_end)

'''

if insert_before not in text:
    raise SystemExit("body= marker missing")
if "Always try to append the following decision" not in text:
    text = text.replace(insert_before, post + insert_before, 1)

# Also: if best heading is only valuation step 7, and start is step 7, the expand loop should continue into step 8 because is_hard_stop is false for decision. Good.

path.write_text(text, encoding="utf-8")
import py_compile
py_compile.compile(str(path), doraise=True)
print("ok")
