"""临时脚本：从顺丰 2026 半年报 PDF 中按页/按栏抽取现金流量表与分部信息。用完即删。"""

import re
import sys

import pdfplumber

PDF = "research/source_docs/顺丰控股/顺丰控股-2026年半年度报告.pdf"
TARGETS = ["合并及公司现金流量表", "七 分部信息", "分部信息"]


def find_pages(pdf):
    hits = {}
    for i, page in enumerate(pdf.pages):
        try:
            txt = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            continue
        for t in TARGETS:
            if t in txt:
                hits.setdefault(t, []).append(i)
    return hits


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "find"
    with pdfplumber.open(PDF) as pdf:
        if which == "find":
            for t, pages in find_pages(pdf).items():
                print(t, "->", pages)
            return
        mode = "full"
        nums = which.split(":")
        if len(nums) == 2:
            mode, which = nums
        pages = [int(p) for p in which.split(",")]
        for p in pages:
            page = pdf.pages[p]
            print(f"===== page {p} =====")
            if mode == "full":
                print(page.extract_text())
                continue
            w = float(page.width)
            # 左栏（合并口径）约占页面左侧 62%
            left = page.crop((0, 0, w * float(mode), float(page.height)))
            print(left.extract_text())


if __name__ == "__main__":
    main()
