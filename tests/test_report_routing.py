import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import report_routing  # noqa: E402


REGISTRY = {
    "schema_version": 1,
    "companies": [
        {
            "canonical_name": "国电南瑞",
            "tickers": ["600406.SH"],
            "aliases": ["国电南瑞", "国电南瑞科技股份有限公司", "600406", "600406.SH"],
            "directory": "reports/国电南瑞",
        },
        {
            "canonical_name": "腾讯",
            "tickers": ["00700.HK"],
            "aliases": ["腾讯", "0700.HK"],
            "directory": "reports/腾讯",
        },
    ],
}


class ReportRoutingTests(unittest.TestCase):
    def test_nari_ticker_variants_resolve_to_existing_company_directory(self):
        for ticker in ("600406", "600406.SH"):
            result = report_routing.resolve_route(
                ticker=ticker,
                market="A股",
                filename="国电南瑞-investment-research-20260723.md",
                registry=REGISTRY,
            )
            self.assertEqual(result["status"], "resolved_registered_company")
            self.assertEqual(result["destination_dir"], "reports/国电南瑞")
            self.assertEqual(
                result["destination_path"],
                "reports/国电南瑞/国电南瑞-investment-research-20260723.md",
            )

    def test_existing_company_name_resolves_without_a_ticker(self):
        result = report_routing.resolve_route(
            company="国电南瑞科技股份有限公司",
            filename="国电南瑞-news-20260723.md",
            registry=REGISTRY,
        )
        self.assertEqual(result["destination_dir"], "reports/国电南瑞")

    def test_explicit_new_company_creates_only_its_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = report_routing.resolve_route(
                company="示例公司",
                filename="示例公司-investment-research-20260723.md",
                repo_root=root,
                registry=REGISTRY,
                create=True,
            )
            self.assertEqual(result["status"], "resolved_new_company")
            self.assertTrue((root / "reports" / "示例公司").is_dir())
            self.assertFalse((root / "reports" / "示例公司" / result["filename"]).exists())

    def test_topic_and_comparison_routes_are_deterministic(self):
        topic = report_routing.resolve_route(
            topic="电力设备",
            report_type="topic",
            filename="电力设备-industry-funnel-20260723.md",
            registry=REGISTRY,
        )
        comparison = report_routing.resolve_route(
            report_type="comparison",
            filename="腾讯vs阿里-估值对比-20260723.md",
            registry=REGISTRY,
        )
        self.assertEqual(topic["destination_dir"], "reports/电力设备")
        self.assertEqual(comparison["destination_dir"], "reports/多公司对比")

    def test_unknown_input_uses_the_shared_inbox(self):
        result = report_routing.resolve_route(
            ticker="999999.SH",
            filename="unknown-report.md",
            report_type="unknown",
            registry=REGISTRY,
        )
        self.assertEqual(result["status"], "routed_to_inbox")
        self.assertEqual(result["destination_dir"], "reports/_inbox/待归档")

    def test_resolver_does_not_rewrite_the_registry_or_filename(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            registry_path = Path(temporary_directory) / "company_registry.json"
            registry_path.write_text(json.dumps(REGISTRY, ensure_ascii=False), encoding="utf-8")
            before = registry_path.read_text(encoding="utf-8")
            report_routing.resolve_route(
                company="国电南瑞",
                filename="原始文件名.md",
                registry=report_routing.load_registry(registry_path),
            )
            self.assertEqual(registry_path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
