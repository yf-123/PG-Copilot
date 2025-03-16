def pdf_translate(self, input_path: str, output_path: str) -> str:
    """
    Translate all PDF files in the specified directory and save the translated versions.

    Args:
        self (Agent): The agent instance calling the function.
        input_path (str): The path to the directory containing PDF files to be translated.
        output_path (str): The path to the directory where the translated PDF files will be saved.

    Returns:
        str: A status message indicating the result of the translation process.
    """
    import fitz  # PyMuPDF，用于拆分 PDF 文件
    import os
    import requests
    import json
    from concurrent.futures import ThreadPoolExecutor
    from bs4 import BeautifulSoup

    # Sambanova API 配置
    BASE_URL = "https://api.sambanova.ai/v1"
    API_KEY = "614e1948-9d06-4764-8124-9cad201c8281"

    from openai import OpenAI

    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


    def read_and_clean_pdf_text(fp):
        """
        这个函数用于分割pdf，用了很多trick，逻辑较乱，效果奇好

        **输入参数说明**
        - `fp`：需要读取和清理文本的pdf文件路径

        **输出参数说明**
        - `meta_txt`：清理后的文本内容字符串
        - `page_one_meta`：第一页清理后的文本内容列表

        **函数功能**
        读取pdf文件并清理其中的文本内容，清理规则包括：
        - 提取所有块元的文本信息，并合并为一个字符串
        - 去除短块（字符数小于100）并替换为回车符
        - 清理多余的空行
        - 合并小写字母开头的段落块并替换为空格
        - 清除重复的换行
        - 将每个换行符替换为两个换行符，使每个段落之间有两个换行符分隔
        """
        import fitz, copy
        import re
        import numpy as np
        fc = 0  # Index 0 文本
        fs = 1  # Index 1 字体
        fb = 2  # Index 2 框框
        REMOVE_FOOT_NOTE = True # 是否丢弃掉 不是正文的内容 （比正文字体小，如参考文献、脚注、图注等）
        REMOVE_FOOT_FFSIZE_PERCENT = 0.95 # 小于正文的？时，判定为不是正文（有些文章的正文部分字体大小不是100%统一的，有肉眼不可见的小变化）
        def primary_ffsize(l):
            """
            提取文本块主字体
            """
            fsize_statiscs = {}
            for wtf in l['spans']:
                if wtf['size'] not in fsize_statiscs: fsize_statiscs[wtf['size']] = 0
                fsize_statiscs[wtf['size']] += len(wtf['text'])
            return max(fsize_statiscs, key=fsize_statiscs.get)

        def ffsize_same(a,b):
            """
            提取字体大小是否近似相等
            """
            return abs((a-b)/max(a,b)) < 0.02

        with fitz.open(fp) as doc:
            meta_txt = []
            meta_font = []

            meta_line = []
            meta_span = []
            ############################## <第 1 步，搜集初始信息> ##################################
            for index, page in enumerate(doc):
                # file_content += page.get_text()
                text_areas = page.get_text("dict")  # 获取页面上的文本信息
                for t in text_areas['blocks']:
                    if 'lines' in t:
                        pf = 998
                        for l in t['lines']:
                            txt_line = "".join([wtf['text'] for wtf in l['spans']])
                            if len(txt_line) == 0: continue
                            pf = primary_ffsize(l)
                            meta_line.append([txt_line, pf, l['bbox'], l])
                            for wtf in l['spans']: # for l in t['lines']:
                                meta_span.append([wtf['text'], wtf['size'], len(wtf['text'])])
                        # meta_line.append(["NEW_BLOCK", pf])
                # 块元提取                           for each word segment with in line                       for each line         cross-line words                          for each block
                meta_txt.extend([" ".join(["".join([wtf['text'] for wtf in l['spans']]) for l in t['lines']]).replace(
                    '- ', '') for t in text_areas['blocks'] if 'lines' in t])
                meta_font.extend([np.mean([np.mean([wtf['size'] for wtf in l['spans']])
                                for l in t['lines']]) for t in text_areas['blocks'] if 'lines' in t])
                if index == 0:
                    page_one_meta = [" ".join(["".join([wtf['text'] for wtf in l['spans']]) for l in t['lines']]).replace(
                        '- ', '') for t in text_areas['blocks'] if 'lines' in t]

            ############################## <第 2 步，获取正文主字体> ##################################
            try:
                fsize_statiscs = {}
                for span in meta_span:
                    if span[1] not in fsize_statiscs: fsize_statiscs[span[1]] = 0
                    fsize_statiscs[span[1]] += span[2]
                main_fsize = max(fsize_statiscs, key=fsize_statiscs.get)
                if REMOVE_FOOT_NOTE:
                    give_up_fize_threshold = main_fsize * REMOVE_FOOT_FFSIZE_PERCENT
            except:
                raise RuntimeError(f'抱歉, 我们暂时无法解析此PDF文档: {fp}。')
            ############################## <第 3 步，切分和重新整合> ##################################
            mega_sec = []
            sec = []
            for index, line in enumerate(meta_line):
                if index == 0:
                    sec.append(line[fc])
                    continue
                if REMOVE_FOOT_NOTE:
                    if meta_line[index][fs] <= give_up_fize_threshold:
                        continue
                if ffsize_same(meta_line[index][fs], meta_line[index-1][fs]):
                    # 尝试识别段落
                    if meta_line[index][fc].endswith('.') and\
                        (meta_line[index-1][fc] != 'NEW_BLOCK') and \
                        (meta_line[index][fb][2] - meta_line[index][fb][0]) < (meta_line[index-1][fb][2] - meta_line[index-1][fb][0]) * 0.7:
                        sec[-1] += line[fc]
                        sec[-1] += "\n\n"
                    else:
                        sec[-1] += " "
                        sec[-1] += line[fc]
                else:
                    if (index+1 < len(meta_line)) and \
                        meta_line[index][fs] > main_fsize:
                        # 单行 + 字体大
                        mega_sec.append(copy.deepcopy(sec))
                        sec = []
                        sec.append("# " + line[fc])
                    else:
                        # 尝试识别section
                        if meta_line[index-1][fs] > meta_line[index][fs]:
                            sec.append("\n" + line[fc])
                        else:
                            sec.append(line[fc])
            mega_sec.append(copy.deepcopy(sec))

            finals = []
            for ms in mega_sec:
                final = " ".join(ms)
                final = final.replace('- ', ' ')
                finals.append(final)
            meta_txt = finals

            ############################## <第 4 步，乱七八糟的后处理> ##################################
            def 把字符太少的块清除为回车(meta_txt):
                for index, block_txt in enumerate(meta_txt):
                    if len(block_txt) < 100:
                        meta_txt[index] = '\n'
                return meta_txt
            meta_txt = 把字符太少的块清除为回车(meta_txt)

            def 清理多余的空行(meta_txt):
                for index in reversed(range(1, len(meta_txt))):
                    if meta_txt[index] == '\n' and meta_txt[index-1] == '\n':
                        meta_txt.pop(index)
                return meta_txt
            meta_txt = 清理多余的空行(meta_txt)

            def 合并小写开头的段落块(meta_txt):
                def starts_with_lowercase_word(s):
                    pattern = r"^[a-z]+"
                    match = re.match(pattern, s)
                    if match:
                        return True
                    else:
                        return False
                # 对于某些PDF会有第一个段落就以小写字母开头,为了避免索引错误将其更改为大写
                if starts_with_lowercase_word(meta_txt[0]):
                    meta_txt[0] = meta_txt[0].capitalize()
                for _ in range(100):
                    for index, block_txt in enumerate(meta_txt):
                        if starts_with_lowercase_word(block_txt):
                            if meta_txt[index-1] != '\n':
                                meta_txt[index-1] += ' '
                            else:
                                meta_txt[index-1] = ''
                            meta_txt[index-1] += meta_txt[index]
                            meta_txt[index] = '\n'
                return meta_txt
            meta_txt = 合并小写开头的段落块(meta_txt)
            meta_txt = 清理多余的空行(meta_txt)

            meta_txt = '\n'.join(meta_txt)
            # 清除重复的换行
            for _ in range(5):
                meta_txt = meta_txt.replace('\n\n', '\n')

            # 换行 -> 双换行
            meta_txt = meta_txt.replace('\n', '\n\n')

            ############################## <第 5 步，展示分割效果> ##################################
            # for f in finals:
            #    print亮黄(f)
            #    print亮绿('***************************')

        return meta_txt, page_one_meta


    # 调用SambaNova API的通用方法
    def call_sambanova_api(messages, model="Meta-Llama-3.1-8B-Instruct"):
        """
        调用SambaNova的API，完成对给定消息的处理。
        """
        response = client.chat.completions.create(model=model, messages=messages)
        if hasattr(response, 'choices') and len(response.choices) > 0:
            return response.choices[0].message.content
        return ""

    def force_breakdown(txt, limit, get_token_fn):
        """
        当无法用标点、空行分割时，暴力切割文本。
        """
        for i in reversed(range(len(txt))):
            if get_token_fn(txt[:i]) < limit:
                return txt[:i], txt[i:]
        return "切分错误", "切分错误"


    def maintain_storage(remain_txt_to_cut, remain_txt_to_cut_storage):
        """
        为了加速计算，当文本长度超出一定范围时，将多余部分存储在缓冲区。
        """
        _min = int(5e4)
        _max = int(1e5)
        if len(remain_txt_to_cut) < _min and len(remain_txt_to_cut_storage) > 0:
            remain_txt_to_cut += remain_txt_to_cut_storage
            remain_txt_to_cut_storage = ""
        if len(remain_txt_to_cut) > _max:
            remain_txt_to_cut_storage = remain_txt_to_cut[_max:] + remain_txt_to_cut_storage
            remain_txt_to_cut = remain_txt_to_cut[:_max]
        return remain_txt_to_cut, remain_txt_to_cut_storage


    def cut(limit, get_token_fn, txt_tocut, must_break_at_empty_line, break_anyway=False):
        """
        将文本切分为满足Token限制的小段。
        """
        res = []
        total_len = len(txt_tocut)
        fin_len = 0
        remain_txt_to_cut = txt_tocut
        remain_txt_to_cut_storage = ""

        remain_txt_to_cut, remain_txt_to_cut_storage = maintain_storage(remain_txt_to_cut, remain_txt_to_cut_storage)

        while True:
            if get_token_fn(remain_txt_to_cut) <= limit:
                res.append(remain_txt_to_cut)
                fin_len += len(remain_txt_to_cut)
                break
            else:
                lines = remain_txt_to_cut.split('\n')
                estimated_line_cut = int(limit / get_token_fn(remain_txt_to_cut) * len(lines))

                cnt = 0
                for cnt in reversed(range(estimated_line_cut)):
                    if must_break_at_empty_line:
                        if lines[cnt] != "":
                            continue
                    prev = "\n".join(lines[:cnt])
                    post = "\n".join(lines[cnt:])
                    if get_token_fn(prev) < limit:
                        break

                if cnt == 0:
                    if break_anyway:
                        prev, post = force_breakdown(remain_txt_to_cut, limit, get_token_fn)
                    else:
                        raise RuntimeError(f"存在极长的文本无法切分！{remain_txt_to_cut}")

                res.append(prev)
                fin_len += len(prev)
                remain_txt_to_cut = post
                remain_txt_to_cut, remain_txt_to_cut_storage = maintain_storage(remain_txt_to_cut, remain_txt_to_cut_storage)
                process = fin_len / total_len
                print(f'正在文本切分 {int(process * 100)}%')
                if len(remain_txt_to_cut.strip()) == 0:
                    break
        return res


    # 主函数：处理PDF文件并生成报告


    def breakdown_text_to_satisfy_token_limit(txt, limit, llm_model="Meta-Llama-3.1-8B-Instruct"):
        """
        根据 Token 限制切分文本，适配 SambaNova 的 API。
        """
        # 定义获取 Token 数的函数
        def get_token_fn(txt):
            # 使用简单字符长度估算 Token 数
            return len(txt) // 4  # 假设平均每 4 个字符是 1 个 Token

        try:
            # 尝试按双空行分割
            return cut(limit, get_token_fn, txt, must_break_at_empty_line=True)
        except RuntimeError:
            try:
                # 尝试按单空行分割
                return cut(limit, get_token_fn, txt, must_break_at_empty_line=False)
            except RuntimeError:
                try:
                    # 尝试按英文句号分割
                    res = cut(limit, get_token_fn, txt.replace('.', '。\n'), must_break_at_empty_line=False)
                    return [r.replace('。\n', '.') for r in res]
                except RuntimeError:
                    try:
                        # 尝试按中文句号分割
                        res = cut(limit, get_token_fn, txt.replace('。', '。。\n'), must_break_at_empty_line=False)
                        return [r.replace('。。\n', '。') for r in res]
                    except RuntimeError:
                        # 最后一步，暴力切分
                        return cut(limit, get_token_fn, txt, must_break_at_empty_line=False, break_anyway=True)



    def process_pdf(fp):
        """
        处理PDF文件，提取元信息、翻译内容，并生成报告。
        """
        TOKEN_LIMIT_PER_FRAGMENT = 1024
        # 步骤1：读取和预处理PDF文本
        file_content,page_one = read_and_clean_pdf_text(fp)  # 需要实现此函数以读取PDF内容

        # 编码清理
        file_content = file_content.encode('utf-8', 'ignore').decode()
        page_one = str(page_one).encode('utf-8', 'ignore').decode()

        # 分割PDF文本
        paper_fragments = breakdown_text_to_satisfy_token_limit(
            txt=file_content, limit=TOKEN_LIMIT_PER_FRAGMENT
        )
        page_one_fragments = breakdown_text_to_satisfy_token_limit(
            txt=page_one, limit=TOKEN_LIMIT_PER_FRAGMENT
        )

        # 提取论文元信息
        paper_meta = page_one_fragments[0].split('introduction')[0].split('Introduction')[0].split('INTRODUCTION')[0]
        meta_prompt = f"以下是一篇学术论文的基础信息，请从中提取出“标题”、“收录会议或期刊”、“作者”、“摘要”、“编号”、“作者邮箱”这六个部分。请用markdown格式输出，最后用中文翻译摘要部分。请提取：{paper_meta}"
        message_meta = [{"role": "user", "content": meta_prompt}]
        paper_meta_info = call_sambanova_api(messages=message_meta)

        # 翻译论文正文
        translation_prompts = [
            {"role": "user", "content": f"请翻译以下内容：\n{frag}"} for frag in paper_fragments
        ]
        translations = []
        for prompt in translation_prompts:
            translations.append(call_sambanova_api(messages=[prompt]))

        # 整理翻译结果
        gpt_response_collection_md = []
        for i, frag in enumerate(paper_fragments):
            gpt_response_collection_md.append(
                f"\n\n---\n\n ## 原文[{i + 1}/{len(paper_fragments)}]： \n\n {frag.replace('#', '')}  \n\n---\n\n ## 翻译[{i + 1}/{len(translations)}]：\n {translations[i]}"
            )

        # 生成Markdown报告
        final_report_md = [
            "一、论文概况\n\n---\n\n",
            paper_meta_info.replace('# ', '### ') + '\n\n---\n\n',
            "二、论文翻译\n",
            "",
        ]
        final_report_md.extend(gpt_response_collection_md)
        create_report_file_name_md = f"{os.path.basename(fp)}.trans.md"
        
        with open(create_report_file_name_md, 'w', encoding='utf-8') as f:
            f.write("\n".join(final_report_md))

        print(f"Markdown报告生成: {create_report_file_name_md}")
        return(paper_meta_info.replace('# ', '### '))



    # 验证输入 PDF 文件是否存在
    if not os.path.isfile(input_path):
        print(f"Error: The file '{input_path}' does not exist.")
        return

    # 验证输出目录是否有效
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        print(f"Output directory '{output_path}' created.")
    elif not os.path.isdir(output_path):
        print(f"Error: The output path '{output_path}' is not a directory.")
        return

    # 调用处理函数
    try:
        print(f"Processing PDF file: {input_path}")
        result = process_pdf(fp=input_path)

        # 将生成的 Markdown 文件移动到输出目录
        md_report_name = f"{os.path.basename(input_path)}.trans.md"
        md_report_path = os.path.join(output_path, md_report_name)
        os.rename(md_report_name, md_report_path)
        print("result:")
        return(result)
        #return(f"Markdown report saved to: {md_report_path}")
    except Exception as e:
        return(f"Error occurred during processing: {e}")
