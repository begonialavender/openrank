import asyncio
import pandas as pd
import time
import random
from requests_html import AsyncHTMLSession, HTML
from fake_useragent import UserAgent
import logging
from urllib.parse import urlencode, urljoin
import json
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TiebaSpider:
    def __init__(self, tieba_name):
        self.tieba_name = tieba_name
        self.base_url = "https://tieba.baidu.com/f"
        self.session = AsyncHTMLSession()
        self.ua = UserAgent()
        self.posts_data = []
        
    def get_headers(self):
        return {'User-Agent': self.ua.random}
        
    async def get_total_pages(self):
        """【翻页】采用最初版本稳定翻页逻辑"""
        try:
            params = {'kw': self.tieba_name, 'ie': 'utf-8'}
            url = f"{self.base_url}?{urlencode(params)}"
            logger.info(f"正在获取贴吧总页数: {url}")
            response = await self.session.get(url, headers=self.get_headers(), timeout=10)
            await response.html.arender(timeout=20, sleep=2)
            
            page_elements = response.html.find('.th_footer_1 .last')
            if page_elements:
                page_url = page_elements[0].attrs.get('href', '')
                total_pages = int(page_url.split('=')[-1]) if 'pn=' in page_url else 1
            else:
                page_links = response.html.find('.pagination .page')
                if page_links:
                    total_pages = max([int(link.text) for link in page_links if link.text.isdigit()])
                else:
                    total_pages = 1
                    
            logger.info(f"贴吧 '{self.tieba_name}' 总页数: {total_pages}")
            return total_pages
        except Exception as e:
            logger.error(f"获取总页数失败: {e}")
            return 1
            
    async def fetch_page_posts(self, page_num):
        """【翻页】采用最初版本获取帖子列表逻辑"""
        try:
            params = {'kw': self.tieba_name, 'ie': 'utf-8', 'pn': (page_num - 1) * 50}
            url = f"{self.base_url}?{urlencode(params)}"
            logger.info(f"正在抓取第 {page_num} 页: {url}")
            
            response = await self.session.get(url, headers=self.get_headers(), timeout=15)
            await response.html.arender(timeout=25, sleep=3)
            
            posts = []
            post_elements = response.html.find('.j_thread_list')
            
            for post_element in post_elements:
                try:
                    post_data = await self.parse_post_element(post_element)
                    if post_data:
                        posts.append(post_data)
                except Exception as e:
                    logger.warning(f"解析帖子元素失败: {e}")
                    continue
                    
            logger.info(f"第 {page_num} 页抓取到 {len(posts)} 个帖子")
            return posts
        except Exception as e:
            logger.error(f"抓取第 {page_num} 页失败: {e}")
            return []
            
    async def parse_post_element(self, post_element):
        """【内容】采用上传文件版本解析帖子元素逻辑"""
        try:
            title = "无标题"
            post_link = ""
            title_selectors = ['a.j_th_tit', '.threadlist_title a', 'a.th_title']
            for selector in title_selectors:
                title_element = post_element.find(selector, first=True)
                if title_element:
                    title = title_element.text.strip()
                    post_link = title_element.attrs.get('href', '')
                    break
            
            author = "匿名用户"
            author_selectors = ['.tb_icon_author', '.frs-author-name', '.threadlist_author']
            for selector in author_selectors:
                author_element = post_element.find(selector, first=True)
                if author_element:
                    author = author_element.text.strip()
                    break
            
            reply_count = "0"
            reply_selectors = ['.threadlist_rep_num', '.j_reply_num']
            for selector in reply_selectors:
                reply_element = post_element.find(selector, first=True)
                if reply_element:
                    reply_count = reply_element.text.strip()
                    break
            
            content = ""
            if post_link:
                content = await self.fetch_post_content(post_link)
            
            return {
                'title': title,
                'author': author,
                'reply_count': reply_count,
                'content': content[:500] if content else "无法获取内容",
                'post_url': f"https://tieba.baidu.com{post_link}" if post_link else '',
                'crawl_time': time.strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            logger.warning(f"解析帖子元素失败: {e}")
            return None
    
    async def fetch_post_content(self, post_link):
        """【内容】采用上传文件版本获取内容逻辑（建议增加重试机制）"""
        try:
            if not post_link:
                return "无内容链接"
                
            url = f"https://tieba.baidu.com{post_link}"
            logger.info(f"获取帖子内容: {url}")
            
            # 可考虑在此处添加重试循环，例如 for attempt in range(2):
            response = await self.session.get(url, headers=self.get_headers(), timeout=15)
            await response.html.arender(timeout=20, sleep=3)  # 可适当增加sleep时间
            
            content_selectors = ['.d_post_content', '.post_content', '.j_d_post_content', '.core_reply_content', '.l_post_content']
            for selector in content_selectors:
                content_elements = response.html.find(selector)
                if content_elements:
                    for elem in content_elements:
                        content_text = elem.text.strip()
                        if content_text and len(content_text) > 10:
                            return content_text
            return "无法提取内容"
        except Exception as e:
            logger.warning(f"获取帖子内容失败: {e}")
            return f"内容获取失败: {str(e)}"
    
    async def crawl_tieba(self, max_pages=5):
        """主爬虫方法"""
        logger.info(f"开始爬取贴吧: {self.tieba_name}")
        try:
            total_pages = await self.get_total_pages()
            pages_to_crawl = min(total_pages, max_pages)
            logger.info(f"计划抓取前 {pages_to_crawl} 页")
            
            tasks = [self.fetch_page_posts(page_num) for page_num in range(1, pages_to_crawl + 1)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"第 {i+1} 页抓取异常: {result}")
                elif result:
                    self.posts_data.extend(result)
                    
            logger.info(f"爬取完成! 总共获取 {len(self.posts_data)} 个帖子")
        except Exception as e:
            logger.error(f"爬虫执行失败: {e}")
    
    def save_to_csv(self, filename=None):
        if not filename:
            filename = f"{self.tieba_name}_posts_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        if self.posts_data:
            df = pd.DataFrame(self.posts_data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"数据已保存到: {filename}")
            return filename
        else:
            logger.warning("没有数据可保存")
            return None
    
    def save_to_json(self, filename=None):
        if not filename:
            filename = f"{self.tieba_name}_posts_{time.strftime('%Y%m%d_%H%M%S')}.json"
        if self.posts_data:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.posts_data, f, ensure_ascii=False, indent=2)
            logger.info(f"数据已保存到: {filename}")
            return filename
        else:
            logger.warning("没有数据可保存")
            return None
    
    def display_statistics(self):
        if not self.posts_data:
            print("没有爬取到数据")
            return
        df = pd.DataFrame(self.posts_data)
        print(f"\n贴吧 '{self.tieba_name}' 爬取统计")
        print(f"总帖子数: {len(self.posts_data)}")
        print(f"作者数量: {df['author'].nunique()}")
        if len(self.posts_data) > 0:
            print(f"标题平均长度: {df['title'].str.len().mean():.2f} 字符")
            print(f"内容平均长度: {df['content'].str.len().mean():.2f} 字符")
        print("\n前3个帖子示例:")
        for i, post in enumerate(self.posts_data[:3]):
            print(f"{i+1}. 标题: {post['title'][:50]}...")
            print(f"   作者: {post['author']}")
            print(f"   回复: {post['reply_count']}")
            content_preview = post['content'][:100] + "..." if post['content'] and len(post['content']) > 100 else post['content']
            print(f"   内容预览: {content_preview}")
            print()
    
    async def close(self):
        await self.session.close()

async def main():
    tieba_name = input('欢迎使用"听涛"！请输入要检索分析的贴吧名称: ').strip() or "python"
    try:
        max_pages = int(input("请输入取样的页数（默认1）: ") or "1")
    except:
        max_pages = 1
    
    spider = TiebaSpider(tieba_name)
    try:
        start_time = time.time()
        await spider.crawl_tieba(max_pages=max_pages)
        end_time = time.time()
        spider.display_statistics()
        csv_file = spider.save_to_csv()
        json_file = spider.save_to_json()
        print(f"\n爬取完成！耗时：{end_time - start_time:.2f} 秒")
        if csv_file:
            print(f"数据已保存到：{csv_file} 和 {json_file}")
    finally:
        await spider.close()
        
if __name__ == "__main__":
    asyncio.run(main())
