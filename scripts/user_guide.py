"""Conversation-first onboarding; HTML is an explicit optional reference."""
import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', action='store_true', help='Locate the optional web guide only when the user explicitly requests it.')
    args = parser.parse_args(argv)
    if not args.html:
        print('默认在对话中逐步问清需求，不打开浏览器。先读已有信息，每轮优先用原生弹出选项问一个关键问题；根据回答调整下一问。')
        print('用途与听众 → 材料和来源边界 → 时长/篇幅 → 制作方式 → 适用的配图方式与模板 → 样页验收。跳过已明确项，解决冲突后简短复述并开工。')
        print('读取 workflows/clarification-gate.md；用 clarify init --known-json 保存已知项，clarify next <request.json> 准备下一道原生问题。')
        return 0
    path = Path(__file__).resolve().parents[1] / 'assets/guide/index.html'
    if not path.is_file():
        raise FileNotFoundError('Install the complete EasySlides plugin to use the guide')
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
