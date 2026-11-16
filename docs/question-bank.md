# 湖北定向选调题库

本地题库见 [`data/hubei_question_bank.sqlite`](../data/hubei_question_bank.sqlite)，包含原 PDF 的第 1—500 题。每条记录保存题干、四个原始选项、原始答案、解析、考点标签和 PDF 页码。六个部分的题量分别为 100、100、80、100、20、100。

原件是扫描 PDF，文本由本机中文 OCR 提取。题号、缺失的选项及若干错位题干已对照原页修复；其他条目仍可能有个别识别错字。原始 OCR 结果保存在 [`data/hubei_question_bank_ocr.zip`](../data/hubei_question_bank_ocr.zip)，数据库也保留每题的原始 OCR 段落，便于日后校订。题库答案按原 PDF 记录，未另行核验时政事实的现行有效性。

在聊天中说“从湖北时政出 5 题”或“考我第 100—120 题”，即可从数据库抽题。出题时用 [`scripts/quiz_question_bank.py`](../scripts/quiz_question_bank.py) 打乱每题选项；答题前不展示答案。你回答后再按该次测验的记录判分并展示解析。

命令行示例（在本工作区运行）：

```text
python scripts/quiz_question_bank.py start --count 5
python scripts/quiz_question_bank.py start --section 湖北时政 --count 10
python scripts/quiz_question_bank.py grade <session_id> --answers ABCDA
```

`start` 会生成测验编号，并把换序对应关系存在数据库中。`grade` 根据该编号评分，返回换序后的正确字母与原解析。重建题库的脚本是 [`scripts/build_question_bank.py`](../scripts/build_question_bank.py)；它需要桌面上的原 PDF 以及 OCR 归档。
