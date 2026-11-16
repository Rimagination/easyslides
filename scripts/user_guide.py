"""Conversation-first onboarding; HTML is an explicit optional reference."""
import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', action='store_true', help='Locate the optional web guide only when the user explicitly requests it.')
    args = parser.parse_args(argv)
    if not args.html:
        print('默认在对话中逐步问清需求，不打开浏览器。先读已有信息，每轮优先用原生弹出选项问一个关键问题；根据回答调整下一问。')
        print('先选原生可编辑，或先生图再转可编辑。原生且未指定模板时默认 academic_general；再确认主题色，以及使用模板主题图还是单独生成主题图。读取材料中的学科、汇报人、学校和日期，只补问缺项，再匹配或生成主题图。')
        print('补齐必要的用途、听众、来源边界和时长后开工。明确指定的模板、配色和配图优先；沿用同一任务已有选择。')
        print('读取 workflows/clarification-gate.md；用 clarify init --known-json 保存已知项，clarify next <request.json> 准备下一道原生问题。')
        return 0
    path = Path(__file__).resolve().parents[1] / 'assets/guide/index.html'
    if not path.is_file():
        raise FileNotFoundError('Install the complete EasySlides plugin to use the guide')
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
