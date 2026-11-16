"""Build a local SQLite quiz bank from the OCR of the user's scanned PDF."""

import hashlib
import json
import re
import sqlite3
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OCR_ARCHIVE = ROOT / "data" / "hubei_question_bank_ocr.zip"
DB_PATH = ROOT / "data" / "hubei_question_bank.sqlite"
PDF_PATH = Path(r"C:\Users\111\Desktop\湖北定向选调常识时政题库（500题）终版_分享版.pdf")

# The scan's red watermark obscures these four heading lines in Windows OCR.
MISSING_HEADINGS = {
    70: (2, "第169题．神舟二十一号航天员乘组在轨驻留210天，刷新中国航天员单个乘组在轨驻留最长纪录，该乘组由（）组成。"),
    114: (2, "第285题．根据我国宪法规定，下列职权中属于全国人民代表大会行使的是（）。"),
    131: (2, "第322题．根据《行政强制法》规定，下列属于行政强制执行方式的是（）。"),
    134: (2, "第328题．根据《公务员法》规定，下列人员中不得录用为公务员的是（）。"),
}

# Options whose labels were obscured or reordered by the watermark were read
# directly from the original page images. Keys are original question numbers.
MANUAL_CORRECTIONS = {
    42: {"options": {"A": "500亿元", "B": "1000亿元", "C": "3000亿元", "D": "6500亿元"}},
    44: {"options": {"A": "第一", "B": "第二", "C": "第三", "D": "第五"}},
    49: {"options": {"A": "32.4%", "B": "44.2%", "C": "85.8%", "D": "114%"}},
    63: {"options": {"A": "“一核两带三极”", "B": "“一线三片多点”", "C": "“一江两湖三山四城”", "D": "“一轴两廊三片四区”"}},
    66: {"stem": "2025年，湖北累计接待旅游客流量9.95亿人次，实现旅游综合收入1.05万亿元。其中，旅游综合收入的同比增速为：",
         "options": {"A": "14.01%", "B": "16.52%", "C": "12.9%", "D": "10.11%"}},
    70: {"stem": "湖北启动战略人才力量“十百千万”行动，提出用3至5年时间，培养引进战略科学家的数量为：",
         "options": {"A": "10名", "B": "100名", "C": "1000名", "D": "10000名"}},
    72: {"options": {"A": "500名", "B": "1000名", "C": "2000名", "D": "66名"}},
    76: {"stem": "截至2025年，武汉全市已建在建智算中心数量为：",
         "options": {"A": "8个", "B": "13个", "C": "23个", "D": "40个"}},
    104: {"stem": "《决定》明确了完成本决定提出的改革任务的时间节点，即（）。",
          "options": {"A": "二〇二五年", "B": "二〇二九年", "C": "二〇三〇年", "D": "二〇三五年"}},
    105: {"stem": "与党的十八届三中全会提出的改革总目标相比，二十届三中全会提出的进一步全面深化改革总目标增加了（）二字。"},
    118: {"stem": "“十五五”规划纲要提出，单位国内生产总值二氧化碳排放累计降低（）。",
          "options": {"A": "18%", "B": "15%", "C": "13.5%", "D": "17%"}},
    120: {"options": {"C": "1%左右"}},
    126: {"stem": "2026年《政府工作报告》提出，今年单位国内生产总值二氧化碳排放降低（）左右。",
          "options": {"A": "3.8%", "B": "3%", "C": "5%", "D": "2.5%"}},
    152: {"stem": "《国务院关于深入实施“人工智能+”行动的意见》印发的年份和月份是（）。",
          "options": {"A": "2025年8月", "B": "2025年3月", "C": "2025年10月", "D": "2024年8月"}},
    154: {"stem": "《关于深入实施“人工智能+”行动的意见》要求以科技、产业、消费、民生、治理、全球合作等领域为重点，加快实施（）大重点行动。",
          "options": {"A": "5", "B": "8", "C": "10", "D": "6"}},
    155: {"stem": "2024年9月，全国教育大会在北京召开，会议提出到（）年建成教育强国。",
          "options": {"A": "2035", "B": "2030", "C": "2025", "D": "本世纪中叶"}},
    160: {"stem": "全国生态日由（）表决通过决定设立。",
          "options": {"A": "国务院常务会议", "B": "全国政协常委会会议", "C": "十四届全国人大常委会第三次会议", "D": "中共中央、国务院"}},
    184: {"stem": "2025年7月，中央城市工作会议在北京举行，这是我国时隔（）年再次召开中央城市工作会议。",
          "options": {"A": "8", "B": "5", "C": "10", "D": "15"}},
    235: {"stem": "奠定马克思主义中国化的哲学基础、标志着毛泽东哲学思想系统形成的著作是：",
          "options": {"A": "《论持久战》", "B": "《新民主主义论》", "C": "《改造我们的学习》", "D": "《实践论》和《矛盾论》"}},
    238: {"options": {"A": "“两步走”", "B": "“一个中心，两个基本点”", "C": "“三面红旗”", "D": "“一化三改”"}},
    240: {"stem": "1957年毛泽东提出区分和处理社会主义社会两类不同性质矛盾的著作是：",
          "options": {"A": "《论十大关系》", "B": "《关于正确处理人民内部矛盾的问题》", "C": "《论人民民主专政》", "D": "《论联合政府》"}},
    246: {"stem": "社会主义初级阶段基本路线的核心内容是：",
          "options": {"A": "“一个中心，两个基本点”，即以经济建设为中心，坚持四项基本原则，坚持改革开放",
                       "B": "以阶级斗争为纲", "C": "以精神文明建设为中心", "D": "自力更生，艰苦奋斗"}},
    254: {"stem": "下列关于党的指导理论所回答的核心问题的表述，正确的是：",
          "options": {"A": "“三个代表”重要思想回答的是什么是社会主义、怎样建设社会主义的问题",
                       "B": "“三个代表”重要思想创造性地回答了建设什么样的党、怎样建设党的问题",
                       "C": "邓小平理论回答的是实现什么样的发展、怎样发展的问题",
                       "D": "科学发展观回答的是什么是社会主义、怎样建设社会主义的问题"}},
    266: {"stem": "新质生产力是：",
          "options": {"A": "以大量资源投入和规模扩张为主要特征的粗放型生产力", "B": "传统产业的简单升级",
                       "C": "由技术革命性突破、生产要素创新性配置、产业深度转型升级而催生的先进生产力质态",
                       "D": "以劳动密集型产业为主导的生产力"}},
    282: {"stem": "我国现行宪法是1982年通过的，截至目前先后经过了几次修正（）。", "options": {"A": "三次"}},
    292: {"options": {"A": "一个月"}},
    298: {"stem": "根据《民法典》规定，自然人下落不明满（）的，利害关系人可以向人民法院申请宣告该自然人为失踪人。",
          "options": {"A": "四年", "B": "三年", "C": "二年", "D": "一年"}},
    318: {"stem": "根据《行政处罚法》规定，违法行为在（）内未被发现的，不再给予行政处罚，但涉及公民生命健康安全、金融安全且有危害后果的，上述期限延长至（）。",
          "options": {"B": "一年；三年"}},
    337: {"stem": "根据2023年修订的《公司法》，有限责任公司全体股东认缴的出资额由股东按照公司章程的规定，自公司成立之日起（）内缴足。",
          "options": {"A": "二年", "B": "三年", "C": "五年", "D": "十年"}},
    341: {"stem": "根据2025年修订的《治安管理处罚法》，治安管理处罚的种类不包括（）。",
          "options": {"A": "警告"}},
    344: {"options": {"B": "已满十四周岁不满十八周岁的人违反治安管理的，不予处罚"}},
    369: {"options": {"C": "鼠疫、霍乱"}},
    386: {"stem": "2025年我国拟发行的超长期特别国债规模是（）。",
          "options": {"A": "1万亿元", "B": "5000亿元", "C": "3000亿元", "D": "1.3万亿元"}},
    392: {"stem": "2024年1月，国家数据局等17部门联合印发《“数据要素×”三年行动计划（2024—2026年）》，其先期选取的重点行业和领域数量是（）。",
          "options": {"A": "10个", "B": "12个", "C": "8个", "D": "15个"}},
    396: {"stem": "2025年1月对外公布的《全国统一大市场建设指引（试行）》从“要求做的”“禁止做的”“鼓励做的”三个维度提出要求，其工作着力点可概括为（）。",
          "options": {"B": "“三去一降一补”"}},
    447: {"stem": "关于国土空间规划中的“三区三线”，下列说法正确的是：",
          "options": {"A": "“三区三线”仅适用于城市范围，与农业、生态空间无关",
                       "B": "“三区”指农业空间、生态空间、城镇空间，“三线”指耕地和永久基本农田保护红线、生态保护红线、城镇开发边界",
                       "C": "“三区”指东部、中部、西部地区，“三线”指三条经济带",
                       "D": "“三线”指耕地保护红线、生态保护红线、海岸线"}},
    492: {"stem": "关于“楚辞”，下列说法正确的是：",
          "options": {"A": "《楚辞》是我国第一部诗歌总集，收录了从西周到春秋的诗歌"}},
}


def normalize(line: str) -> str:
    line = re.sub(r"\s+", "", line)
    return line.replace("【", "〖").replace("】", "〗")


def fix_heading(line: str) -> str:
    if line.startswith("第巧题"):
        return line.replace("第巧题", "第15题", 1)
    if line.startswith("第1巧题"):
        return line.replace("第1巧题", "第115题", 1)
    if re.match(r"^第巧\d题", line):
        return line.replace("第巧", "第15", 1)
    if line.startswith("第2巧题"):
        return line.replace("第2巧题", "第215题", 1)
    if line.startswith("第2四题"):
        return line.replace("第2四题", "第219题", 1)
    if line.startswith("第3巧题"):
        return line.replace("第3巧题", "第315题", 1)
    if line.startswith("第4巧题"):
        return line.replace("第4巧题", "第415题", 1)
    if line.startswith("第4四题"):
        return line.replace("第4四题", "第419题", 1)
    return line


def read_lines(source="original"):
    with zipfile.ZipFile(OCR_ARCHIVE) as archive:
        pages = [(name, archive.read(name).decode("utf-8"))
                 for name in sorted(archive.namelist())
                 if name.startswith(source + "/page-") and name.endswith(".txt")]
    for name, content in pages:
        page = int(Path(name).stem.split("-")[1])
        tag_count = 0
        for raw in content.splitlines():
            line = fix_heading(normalize(raw))
            if not line or line == str(page):
                continue
            if line.startswith("〖考点标签〗"):
                tag_count += 1
                yield page, line
                if page in MISSING_HEADINGS and tag_count == MISSING_HEADINGS[page][0]:
                    yield page, MISSING_HEADINGS[page][1]
                continue
            if page == 70 and tag_count == 2 and line.startswith("驻留最长纪录"):
                continue
            yield page, line


def question_blocks(source="original"):
    current = None
    for page, line in read_lines(source):
        match = re.match(r"^第(\d+)题[.．·、:：]?(.*)$", line)
        if match:
            if current:
                yield current
            current = {"number": int(match.group(1)), "start_page": page,
                       "end_page": page, "lines": [match.group(2)]}
        elif current:
            current["lines"].append(line)
            current["end_page"] = page
    if current:
        yield current


def split_parts(block):
    lines = block["lines"]
    text = "\n".join(lines)
    answer_match = re.search(r"〖正确答案〗\s*([ABCDabcd])", text)
    explanation_match = re.search(r"〖(?:津仕)?解析〗", text)
    tag_match = re.search(r"〖考点标签〗", text)
    notes = []
    if not answer_match:
        notes.append("answer_marker_missing")
    if not explanation_match:
        notes.append("explanation_marker_missing")
    if not tag_match:
        notes.append("tag_marker_missing")
    preanswer = text[:answer_match.start()] if answer_match else text
    head, *option_parts = re.split(r"(?m)^([ABCDabcd])\s*[.．·。、:：,，]\s*", preanswer)
    stem = head.replace("\n", "").strip()
    options = {}
    if len(option_parts) % 2:
        notes.append("option_split_odd")
    for label, value in zip(option_parts[::2], option_parts[1::2]):
        label = label.upper()
        if label in options:
            notes.append("duplicate_option_" + label)
        options[label] = value.replace("\n", "").strip()
    for label in "ABCD":
        if not options.get(label):
            notes.append("option_" + label + "_missing")
    explanation = ""
    if explanation_match:
        end = tag_match.start() if tag_match and tag_match.start() > explanation_match.end() else len(text)
        explanation = text[explanation_match.end():end].replace("\n", "").strip()
    tag = ""
    if tag_match:
        tag = text[tag_match.end():].split("\n", 1)[0].strip()
    block.update(stem=stem, options=options,
                 answer=answer_match.group(1).upper() if answer_match else "",
                 explanation=explanation, tag=tag, notes=notes, raw_ocr=text)
    return block


def main():
    blocks = [split_parts(b) for b in question_blocks()]
    clean_blocks = {b["number"]: split_parts(b) for b in question_blocks("clean")}
    for block in blocks:
        number = block["number"]
        block["section"] = ("湖北时政" if number <= 100 else "全国时政" if number <= 200
                            else "政治理论" if number <= 280 else "法律常识" if number <= 380
                            else "经济管理" if number <= 400 else "历史文化科技生活常识")
        clean = clean_blocks.get(number)
        used_second_ocr = False
        if clean:
            if number in (16, 205, 330):
                for field in ("stem", "options", "answer", "explanation", "tag"):
                    block[field] = clean[field]
                used_second_ocr = True
            else:
                for field in ("answer", "explanation", "tag"):
                    if not block[field] and clean[field]:
                        block[field] = clean[field]
                        used_second_ocr = True
                for label in "ABCD":
                    if not block["options"].get(label) and clean["options"].get(label):
                        block["options"][label] = clean["options"][label]
                        used_second_ocr = True
        manual = MANUAL_CORRECTIONS.get(number, {})
        if "stem" in manual:
            block["stem"] = manual["stem"]
        block["options"].update(manual.get("options", {}))
        if manual:
            block["notes"].append("checked_against_scan")
        if number in (169, 285, 322, 328):
            block["notes"].append("heading_checked_against_scan")
        if used_second_ocr:
            block["notes"].append("recovered_with_second_ocr")
        block["notes"] = [note for note in block["notes"] if not (
            (note == "answer_marker_missing" and block["answer"]) or
            (note == "explanation_marker_missing" and block["explanation"]) or
            (note == "tag_marker_missing" and block["tag"]) or
            (note.startswith("option_") and note.endswith("_missing") and block["options"].get(note[7]))
        )]
    numbers = [b["number"] for b in blocks]
    if numbers != list(range(1, 501)):
        raise ValueError(f"Question sequence incorrect: {numbers[:10]} ... {numbers[-10:]}; missing {sorted(set(range(1,501))-set(numbers))}")
    incomplete = [(b["number"], b["notes"]) for b in blocks if not (
        b["stem"] and b["answer"] in "ABCD" and b["explanation"] and
        all(b["options"].get(label) for label in "ABCD")
    )]
    if incomplete:
        raise ValueError(f"Incomplete records: {incomplete}")
    digest = hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        DROP TABLE IF EXISTS questions;
        DROP TABLE IF EXISTS metadata;
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE questions(
            number INTEGER PRIMARY KEY CHECK(number BETWEEN 1 AND 500),
            section TEXT NOT NULL, stem TEXT NOT NULL,
            option_a TEXT NOT NULL, option_b TEXT NOT NULL,
            option_c TEXT NOT NULL, option_d TEXT NOT NULL,
            answer TEXT NOT NULL CHECK(answer IN ('A','B','C','D')),
            explanation TEXT NOT NULL, tag TEXT NOT NULL,
            start_page INTEGER NOT NULL, end_page INTEGER NOT NULL,
            review_notes TEXT NOT NULL, raw_ocr TEXT NOT NULL
        );
        """)
        conn.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("source_pdf", str(PDF_PATH)), ("source_sha256", digest),
            ("source_pages", "207"), ("extraction", "Windows zh-Hans-CN OCR with four headings checked against scan"),
        ])
        conn.executemany("""INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [
            (b["number"], b["section"], b["stem"],
             *(b["options"].get(x, "") for x in "ABCD"), b["answer"],
             b["explanation"], b["tag"], b["start_page"], b["end_page"],
             ",".join(b["notes"]), b["raw_ocr"])
            for b in blocks
        ])
        conn.commit()
    anomalies = [dict(number=b["number"], pages=[b["start_page"], b["end_page"]],
                      notes=b["notes"], stem=b["stem"][:65]) for b in blocks if b["notes"]]
    print(json.dumps({"count": len(blocks), "anomaly_count": len(anomalies),
                      "anomalies": anomalies}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
