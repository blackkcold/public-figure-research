#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""public-figure-research 标准报告生成器。

汇总调研结果表、平台覆盖统计、失败排障、文件路径链接。
"""
import argparse
import csv
import json
import sys
from pathlib import Path


def _read_csv(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _coverage_stats(rows):
    platforms = ["微博粉丝", "抖音粉丝", "小红书粉丝", "B站粉丝"]
    total = len(rows)
    stats = {}
    for p in platforms:
        filled = sum(1 for r in rows if r.get(p) and r[p] not in ("未找到", "不适用", ""))
        stats[p] = {"filled": filled, "total": total, "rate": f"{filled}/{total}"}
    return stats


def _failures(rows):
    failures = []
    for i, r in enumerate(rows, start=2):
        for p in ["微博粉丝", "抖音粉丝", "小红书粉丝", "B站粉丝"]:
            v = r.get(p)
            if v in ("未找到", "不适用", ""):
                failures.append(f"第{i}行 {r.get('人物','?')} - {p}: {v or '空'}")
    return failures


def generate(csv_path, output_dir):
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"CSV 不存在: {csv_path}")
        sys.exit(1)

    rows = _read_csv(csv_path)
    stats = _coverage_stats(rows)
    failures = _failures(rows)

    lines = []
    lines.append("# 公众人物调研报告")
    lines.append("")
    lines.append(f"- 调研对象数: {len(rows)}")
    lines.append(f"- CSV 文件: {csv_path}")
    lines.append("")
    lines.append("## 平台覆盖统计")
    lines.append("")
    lines.append("| 平台 | 已获取 | 覆盖率 |")
    lines.append("|------|--------|--------|")
    for p, s in stats.items():
        lines.append(f"| {p} | {s['filled']} | {s['rate']} |")
    lines.append("")
    lines.append("## 失败排障")
    lines.append("")
    if failures:
        for f in failures:
            lines.append(f"- {f}")
    else:
        lines.append("- 无失败项")
    lines.append("")
    lines.append("## 结果表")
    lines.append("")
    if rows:
        headers = list(rows[0].keys())
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for r in rows:
            lines.append("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |")
    lines.append("")
    lines.append("## 文件路径")
    lines.append("")
    lines.append(f"- CSV: `{csv_path}`")
    lines.append(f"- 报告: `{Path(output_dir) / 'report.md'}`")
    lines.append("")

    report_path = Path(output_dir) / "report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已生成: {report_path}")
    return str(report_path)


def main():
    parser = argparse.ArgumentParser(description="生成调研报告")
    parser.add_argument("csv_path", help="CSV 文件路径")
    parser.add_argument("--output-dir", default=".", help="报告输出目录")
    args = parser.parse_args()
    generate(args.csv_path, args.output_dir)


if __name__ == "__main__":
    main()
