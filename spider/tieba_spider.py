import asyncio
import pandas as pd
import time
import random
from requests_html import AsyncHTMLSession, HTML
from fake_useragent import UserAgent
import logging
from urllib.parse import urlencode, urljoin
import json
import os
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TiebaSpider:
    """
    百度贴吧爬虫类
    用于抓取指定贴吧的帖子标题、作者和内容
    """
    
    def __init__(self, tieba_name):
        """
        初始化爬虫
        
        Args:
            tieba_name (str): 贴吧名称
        """
        self.tieba_name = tieba_name
        self.base_url = f"https://tieba.baidu.com/f"
        self.session = AsyncHTMLSession()
        self.ua = UserAgent()
        self.posts_data = []
        
    def get_headers(self):
        """生成随机请求头"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    async def get_total_pages(self):
        """获取贴吧总页数"""
        try:
            params = {'kw': self.tieba_name, 'ie': 'utf-8'}
            url = f"{self.base_url}?{urlencode(params)}"
            #logger.info(f"正在获取贴吧总页数: {url}")
            
            response = await self.session.get(
                url,
                headers=self.get_headers(),
                timeout=15
            )
            
            # 使用JavaScript渲染页面
            await response.html.arender(timeout=20, sleep=3)
            
            # 查找分页元素
            total_pages = 1
            try:
                # 尝试多种分页选择器
                page_selectors = [
                    '.pagination .last',
                    'a.last',
                    '.pagination a:last-child',
                    '#frs_list_pager .last',
                    '.pagination-item[title*="尾页"]'
                ]
                
                for selector in page_selectors:
                    page_elements = response.html.find(selector)
                    if page_elements:
                        page_url = page_elements[0].attrs.get('href', '')
                        if page_url and 'pn=' in page_url:
                            page_num = page_url.split('pn=')[-1]
                            try:
                                total_pages = int(page_num) // 50 + 1
                                break
                            except:
                                continue
            
            except Exception as e:
                logger.warning(f"解析分页失败: {e}")
            
            #logger.info(f"贴吧 '{self.tieba_name}' 总页数: {total_pages}")
            return total_pages
            
        except Exception as e:
            #logger.error(f"获取总页数失败: {e}")
            return 1
            
    async def fetch_page_posts(self, page_num):
        """获取指定页面的帖子列表"""
        try:
            params = {
                'kw': self.tieba_name,
                'ie': 'utf-8',
                'pn': (page_num - 1) * 50  # 贴吧每页50个帖子
            }
            url = f"{self.base_url}?{urlencode(params)}"
            
            #logger.info(f"正在抓取第 {page_num} 页: {url}")
            
            response = await self.session.get(
                url,
                headers=self.get_headers(),
                timeout=20
            )
            
            # 重要：使用JavaScript渲染页面
            await response.html.arender(timeout=30, sleep=5)
            
            # 调试：保存页面HTML以便分析
            html_content = response.html.html
            debug_filename = f"debug_page_{page_num}.html"
            with open(debug_filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            #logger.info(f"已保存第 {page_num} 页HTML到 {debug_filename}")
            
            posts = []
            
            # 方法1：尝试使用CSS选择器查找帖子
            post_selectors = [
                'li.j_thread_list',
                '.j_thread_list',
                '.threadlist_bright',
                '.thread_item',
                'div[data-field]',
                '.threadlist_lz'
            ]
            
            for selector in post_selectors:
                post_elements = response.html.find(selector)
                if post_elements:
                    logger.info(f"使用选择器 '{selector}' 找到 {len(post_elements)} 个帖子元素")
                    for post_element in post_elements[:10]:  # 限制数量
                        try:
                            post_data = await self.parse_post_element(post_element)
                            if post_data:
                                posts.append(post_data)
                        except Exception as e:
                            logger.warning(f"解析帖子元素失败: {e}")
                            continue
                    break
            
            # 方法2：如果方法1失败，尝试查找所有链接
            if not posts:
                logger.info("方法1失败，尝试方法2：查找所有链接")
                all_links = response.html.find('a')
                logger.info(f"页面共有 {len(all_links)} 个链接")
                
                for link in all_links[:50]:  # 只检查前50个链接
                    href = link.attrs.get('href', '')
                    text = link.text.strip()
                    
                    # 判断是否是帖子链接
                    if href and text and len(text) > 5 and '/p/' in href:
                        logger.info(f"发现可能为帖子的链接: {text[:30]}... -> {href}")
                        try:
                            post_data = await self.create_post_from_link(link, href, text)
                            if post_data:
                                posts.append(post_data)
                        except Exception as e:
                            logger.warning(f"从链接创建帖子失败: {e}")
            
            # 方法3：查找包含特定模式的div
            if not posts:
                logger.info("方法2失败，尝试方法3：查找特定div")
                all_divs = response.html.find('div')
                for div in all_divs[:100]:
                    class_attr = div.attrs.get('class', '')
                    if isinstance(class_attr, list):
                        class_attr = ' '.join(class_attr)
                    
                    # 如果div有特定的class，可能是帖子
                    if 'thread' in class_attr.lower() or 'post' in class_attr.lower():
                        try:
                            post_data = await self.parse_div_as_post(div)
                            if post_data:
                                posts.append(post_data)
                        except Exception as e:
                            continue
            
            #logger.info(f"第 {page_num} 页抓取到 {len(posts)} 个帖子")
            return posts
            
        except Exception as e:
            logger.error(f"抓取第 {page_num} 页失败: {e}")
            return []
    
    async def parse_post_element(self, post_element):
        """解析帖子元素"""
        try:
            # 提取标题
            title = "无标题"
            post_link = ""
            
            # 查找标题链接
            title_selectors = ['a.j_th_tit', '.threadlist_title a', 'a.th_title']
            for selector in title_selectors:
                title_element = post_element.find(selector, first=True)
                if title_element:
                    title = title_element.text.strip()
                    post_link = title_element.attrs.get('href', '')
                    break
            
            # 提取作者
            author = "匿名用户"
            author_selectors = ['.tb_icon_author', '.frs-author-name', '.threadlist_author']
            for selector in author_selectors:
                author_element = post_element.find(selector, first=True)
                if author_element:
                    author = author_element.text.strip()
                    break
            
            # 提取回复数
            reply_count = "0"
            reply_selectors = ['.threadlist_rep_num', '.j_reply_num']
            for selector in reply_selectors:
                reply_element = post_element.find(selector, first=True)
                if reply_element:
                    reply_count = reply_element.text.strip()
                    break
            
            # 获取内容
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
    
    async def create_post_from_link(self, link_element, href, text):
        """从链接创建帖子"""
        try:
            # 获取完整URL
            full_url = f"https://tieba.baidu.com{href}"
            
            # 尝试获取作者信息
            author = "匿名用户"
            parent = link_element.parent
            for _ in range(3):
                if parent:
                    # 在父元素中查找作者
                    author_elements = parent.find('.author, .frs-author-name')
                    if author_elements:
                        author = author_elements[0].text.strip()
                        break
                    parent = parent.parent
            
            # 获取内容
            content = await self.fetch_post_content(href)
            
            return {
                'title': text,
                'author': author,
                'reply_count': "0",  # 从链接无法获取回复数
                'content': content[:500] if content else "无法获取内容",
                'post_url': full_url,
                'crawl_time': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            logger.warning(f"从链接创建帖子失败: {e}")
            return None
    
    async def parse_div_as_post(self, div_element):
        """将div解析为帖子"""
        try:
            # 查找链接
            links = div_element.find('a')
            for link in links:
                href = link.attrs.get('href', '')
                text = link.text.strip()
                
                if href and text and '/p/' in href:
                    return await self.create_post_from_link(link, href, text)
            
            return None
            
        except Exception as e:
            logger.warning(f"解析div为帖子失败: {e}")
            return None
    
    async def fetch_post_content(self, post_link):
        """获取帖子详细内容"""
        try:
            if not post_link:
                return "无内容链接"
                
            url = f"https://tieba.baidu.com{post_link}"
            logger.info(f"获取帖子内容: {url}")
            
            response = await self.session.get(
                url,
                headers=self.get_headers(),
                timeout=15
            )
            await response.html.arender(timeout=20, sleep=3)
            
            # 尝试多种内容选择器
            content_selectors = [
                '.d_post_content',
                '.post_content',
                '.j_d_post_content',
                '.core_reply_content',
                '.l_post_content'
            ]
            
            for selector in content_selectors:
                content_elements = response.html.find(selector)
                if content_elements:
                    # 取第一个有效内容
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
            # 获取总页数
            total_pages = await self.get_total_pages()
            pages_to_crawl = min(total_pages, max_pages)
            
            #logger.info(f"计划抓取前 {pages_to_crawl} 页")
            
            # 创建抓取任务
            tasks = [self.fetch_page_posts(page_num) for page_num in range(1, pages_to_crawl + 1)]
            
            # 并发执行所有任务
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"第 {i+1} 页抓取异常: {result}")
                elif result:
                    self.posts_data.extend(result)
                    
            logger.info(f"爬取完成! 总共获取 {len(self.posts_data)} 个帖子")
            
        except Exception as e:
            logger.error(f"爬虫执行失败: {e}")
    
    def save_to_csv(self, filename=None):
        """保存数据到CSV文件"""
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
        """保存数据到JSON文件"""
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
        """显示爬取统计信息"""
        if not self.posts_data:
            print("没有爬取到数据")
            return
            
        df = pd.DataFrame(self.posts_data)
        
        print("\n" + "="*50)
        print(f"贴吧 '{self.tieba_name}' 爬取统计")
        print("="*50)
        print(f"总帖子数: {len(self.posts_data)}")
        print(f"作者数量: {df['author'].nunique()}")
        if len(self.posts_data) > 0:
            print(f"标题平均长度: {df['title'].str.len().mean():.2f} 字符")
            print(f"内容平均长度: {df['content'].str.len().mean():.2f} 字符")
        
        # 显示前几个帖子
        print("\n前5个帖子示例:")
        print("-" * 30)
        for i, post in enumerate(self.posts_data[:5]):
            print(f"{i+1}. 标题: {post['title'][:50]}...")
            print(f"   作者: {post['author']}")
            print(f"   回复: {post['reply_count']}")
            if post['content'] and post['content'] != "无法获取内容":
                print(f"   内容预览: {post['content'][:100]}...")
            else:
                print(f"   内容预览: {post['content']}")
            print(f"   链接: {post['post_url']}")
            print()
    
    async def close(self):
        """关闭会话"""
        await self.session.close()

async def main():
    """主函数"""
    # 用户输入贴吧名称
    tieba_name = input("欢迎使用“听涛”！请输入要检索分析的贴吧名称: ").strip()
    if not tieba_name:
        tieba_name = "python"  # 默认贴吧
        
    try:
        max_pages = int(input("请输入取样的页数（默认1）: ") or "1")
    except:
        max_pages = 1
    
    # 创建爬虫实例
    spider = TiebaSpider(tieba_name)
    
    try:
        # 开始爬取
        start_time = time.time()
        await spider.crawl_tieba(max_pages=max_pages)
        end_time = time.time()
        
        # 显示统计信息
        spider.display_statistics()
        
        # 保存数据
        csv_file = spider.save_to_csv()
        json_file = spider.save_to_json()
        
        print(f"\n爬取完成！耗时：{end_time - start_time:.2f} 秒")
        if csv_file:
            print(f"数据已保存到：{csv_file} 和 {json_file}")
        else:
            print("未能保存数据")
    finally:
        # 确保关闭会话
        await spider.close()
        
if __name__ == "__main__":
    # 运行爬虫
    asyncio.run(main())