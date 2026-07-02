import tempfile
import unittest
from pathlib import Path

from scripts.validate_svg_text_slots import validate_svg_text_slots


def write_svg(body: str) -> tuple[tempfile.TemporaryDirectory, Path]:
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / "slide.svg"
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">{body}</svg>',
        encoding="utf-8",
    )
    return tmp, path


class ValidateSvgTextSlotsTests(unittest.TestCase):
    def test_boxed_wrapped_text_passes(self):
        tmp, path = write_svg(
            """
            <text x="100" y="100" font-size="20" font-weight="700"
              data-pptx-textbox="true" data-pptx-box-x="100" data-pptx-box-y="80"
              data-pptx-box-w="260" data-pptx-box-h="62">
              <tspan x="100" y="100">短句能够放入</tspan>
              <tspan x="100" y="126">固定卡片槽</tspan>
            </text>
            """
        )
        with tmp:
            report = validate_svg_text_slots(path, strict_unboxed=True)

        self.assertEqual(report["status"], "pass", report["issues"])

    def test_boxed_single_line_overflow_fails(self):
        tmp, path = write_svg(
            """
            <text x="100" y="100" font-size="28" font-weight="700"
              data-pptx-textbox="true" data-pptx-box-x="100" data-pptx-box-y="80"
              data-pptx-box-w="160" data-pptx-box-h="40">这是一段明显会越过卡片边界的中文标题</text>
            """
        )
        with tmp:
            report = validate_svg_text_slots(path, strict_unboxed=True)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(issue["code"] == "SVG-TEXT-OVERFLOW-X" for issue in report["issues"]), report["issues"])

    def test_strict_unboxed_long_text_fails(self):
        tmp, path = write_svg('<text x="100" y="100" font-size="20">这段长文本没有声明卡片文本槽</text>')
        with tmp:
            report = validate_svg_text_slots(path, strict_unboxed=True)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(issue["code"] == "SVG-TEXT-UNBOXED" for issue in report["issues"]), report["issues"])


if __name__ == "__main__":
    unittest.main()
