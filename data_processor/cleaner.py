
import json
import re

def clean_tieba_data(raw_json_path, output_json_path):
    
    with open(raw_json_path, 'r', encoding='utf-8') as f:
        raw_posts = json.load(f)
    
    cleaned_posts = []
    for post in raw_posts:
        # 1. 合并标题和内容作为最终分析文本
        combined_text = f"标题：{post.get('title', '')}\n内容：{post.get('content', '')}"
        
        # 2. 清洗掉“点击展开，查看完整图片”等无效文本
        cleaned_text = re.sub(r'点击展开，查看完整图片|快捷键说明|播放出现小问题.*', '', combined_text)
        
        # 3. 去除过多空白字符
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        # 4. 只保留有实质内容的帖子
        if len(cleaned_text) > 20:
            cleaned_post = {
                # 保留原始字段用于追溯
                'original_title': post.get('title', ''),
                'original_author': post.get('author', ''),
                # 清洗后的核心字段，用于构建知识库
                'cleaned_text': cleaned_text,
                'crawl_time': post.get('crawl_time', '')
            }
            cleaned_posts.append(cleaned_post)
    
    # 保存清洗后的数据
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_posts, f, ensure_ascii=False, indent=2)
    
    print(f"[✅] 数据清洗完成。原始帖子数：{len(raw_posts)}，清洗后有效帖子数：{len(cleaned_posts)}")
    return output_json_path