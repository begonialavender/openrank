
import sys
import os
import time
import asyncio
import requests
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from spider.tieba_spider import TiebaSpider
from data_processor.cleaner import clean_tieba_data
from data_processor.txt_converter import convert_cleaned_json_to_txt
from maxkb_manager.deploy import MaxKBDeployer
from maxkb_manager.api_client import MaxKBClient
from maxkb_manager.jwt_client_fixed import MaxKBFixedClient
from config import MAXKB_CONFIG

def run_spider_wrapper(tieba_name, max_pages):
    """包装异步爬虫，使其可在同步代码中调用"""
    async def _run():
        spider = TiebaSpider(tieba_name)
        await spider.crawl_tieba(max_pages=max_pages)
        json_path = spider.save_to_json(f"{tieba_name}_raw_{int(time.time())}.json")
        await spider.close()
        return json_path
    return asyncio.run(_run())

# 在 main.py 中修复重复日志
def check_maxkb_health(base_url, timeout=60):
    """检查MaxKB服务是否完全就绪"""
    print("等待服务就绪", end="", flush=True)
    start_time = time.time()
    health_url = f"{base_url}/api/health"
    
    # 创建禁用代理的会话
    session = requests.Session()
    session.trust_env = False
    session.proxies = {"http": None, "https": None}
    
    check_count = 0
    while time.time() - start_time < timeout:
        try:
            resp = session.get(health_url, timeout=5)
            if resp.status_code == 200:
                print(" ✅")
                return True
        except requests.exceptions.RequestException:
            pass
        check_count += 1
        if check_count % 3 == 0:  # 每3次检查打印一个点
            print(".", end="", flush=True)
        time.sleep(3)
    print(" ❌ (超时)")
    return False

def main():
    """主函数：贴吧舆论分析全流程"""
    print("\n" + "="*80)
    print("               贴吧舆论智能分析系统")
    print("                       听涛")
    print("="*80)

    # --- 1. 用户交互输入 ---
    tieba_name = input(">>> 请输入要分析的贴吧名称: ").strip()
    if not tieba_name:
        print("[❌] 贴吧名称不能为空，程序退出。")
        return

    try:
        max_pages = int(input(">>> 请输入要爬取的页数 (默认1页): ") or "1")
    except ValueError:
        max_pages = 1
        print("[⚠️] 输入页数无效，将使用默认值1页。")

    print(f"\n[📊] 分析目标: 贴吧「{tieba_name}」，爬取页数: {max_pages}")
    print("-" * 80)

    # --- 2. 执行爬虫与清洗 ---
    enable_crawl = input(">>> 是否爬取新数据？(y/n, 默认y): ").strip().lower()
    if enable_crawl in ['y', 'yes', '']:
        try:
            print("\n[1/5] 爬取贴吧数据...")
            raw_data_path = run_spider_wrapper(tieba_name, max_pages)
            print(f"    ✅ 原始数据: {os.path.basename(raw_data_path)}")

            print("\n[2/5] 清洗数据...")
            cleaned_dir = Path(__file__).parent / "data" / "cleaned"
            cleaned_dir.mkdir(parents=True, exist_ok=True)
            cleaned_data_path = cleaned_dir / f"cleaned_{tieba_name}_{int(time.time())}.json"
            clean_tieba_data(raw_data_path, str(cleaned_data_path))
            print(f"    ✅ 清洗完成: {cleaned_data_path.name}")

            print("\n[2.5/5] 转换为MaxKB格式文档...")
            txt_for_maxkb_path = convert_cleaned_json_to_txt(str(cleaned_data_path))
            print(f"    ✅ 转换完成: {os.path.basename(txt_for_maxkb_path)}")
            document_to_upload_path = txt_for_maxkb_path

        except Exception as e:
            print(f"[❌] 数据准备阶段失败: {e}")
            print("将使用已有数据进行聊天...")
            document_to_upload_path = None
    else:
        print("跳过数据爬取，直接进入聊天分析...")
        document_to_upload_path = None

    # --- 3. 启动MaxKB服务 ---
    print("\n[3/5] 启动MaxKB分析引擎...")
    try:
        deployer = MaxKBDeployer('./docker-compose.yml')
        deployer.start()

        if not check_maxkb_health(MAXKB_CONFIG['base_url']):
            print("[❌] MaxKB服务健康检查失败，请检查日志。")
            return

    except Exception as e:
        print(f"[❌] 启动MaxKB服务时出错: {e}")
        print("请确保Docker Desktop正在运行，且端口8080未被占用。")
        return

    # --- 4. 上传数据到知识库---
    if document_to_upload_path:
        print("\n[4/5] 上传数据到知识库...")
        try:
            # 使用原始客户端上传文档（需要管理员权限）
            admin_client = MaxKBClient(
                base_url=MAXKB_CONFIG['base_url'],
                admin_username=MAXKB_CONFIG['admin']['username'],
                admin_password=MAXKB_CONFIG['admin']['password'],
                api_key=MAXKB_CONFIG['application']['api_key'],
                application_id=MAXKB_CONFIG['application']['id'],
                workspace=MAXKB_CONFIG['admin'].get('workspace', 'default')
            )
            print("    ✅ 已连接MaxKB管理服务")

            # 使用固定的知识库ID
            kb_id = MAXKB_CONFIG['knowledge_base_id']
            print(f"    📚 目标知识库ID: {kb_id}")

            # 验证知识库是否存在
            kb_info = admin_client.get_knowledge_base(kb_id)
            if kb_info:
                print(f"    ✅ 知识库「{kb_info.get('name')}」验证通过")
            else:
                print(f"    ⚠️  未找到知识库 {kb_id}，但将继续尝试上传")

            # 上传文档
            print(f"    📤 正在上传数据文件...")
            upload_success = admin_client.upload_document(kb_id, document_to_upload_path)

            if upload_success:
                print("    ✅ 数据上传并处理成功！")
            else:
                print("    ❌ 数据上传失败，但聊天功能仍可尝试使用旧数据。")

        except Exception as e:
            print(f"[❌] 上传数据时出错: {e}")
            print("将尝试继续启动聊天功能...")
    else:
        print("\n[4/5] 跳过数据上传，使用已有知识库...")

    # --- 5. 启动交互式分析助手 ---
    print("\n[5/5] 🎉 分析助手准备就绪！")
    print("=" * 80)
    print(f"此会话将基于「{tieba_name}」贴吧的最新数据进行分析。")
    print("系统已为您准备了一个预设分析问题，您也可以自由提问。")
    print("\n📋 可用命令:")
    print("  - 'sentiment': 分析贴吧舆论情绪倾向")
    print("  - 'history': 查看聊天历史")
    print("  - 'clear': 清空聊天历史")
    print("  - 'help': 显示此帮助信息")
    print("  - 'quit' 或 'exit': 退出程序")
    print("\n💡 提示: 直接输入问题即可开始自由对话")
    print("=" * 80)

    # 使用修复后的客户端进行聊天
    try:
        client = MaxKBFixedClient(
            base_url=MAXKB_CONFIG['base_url'],
            api_key=MAXKB_CONFIG['application']['api_key'],
            application_id=MAXKB_CONFIG['application']['id']
        )
        
        print("[🔄] 初始化聊天连接...")
        if client.test_connection():
            print("[✅] 聊天连接测试成功！")
        else:
            print("[⚠️] 聊天连接测试失败，但将继续尝试...")
            
    except Exception as e:
        print(f"[❌] 初始化客户端失败: {e}")
        import traceback
        traceback.print_exc()
        client = None

    # 唯一的预设问题
    sentiment_question = f"根据「{tieba_name}」贴吧的讨论内容，舆论的整体情绪倾向是正面、负面还是中性？请给出具体理由。"

    # 显示欢迎消息和预设问题建议
    print(f"\n✨ 预设分析问题: {sentiment_question}")
    print(f"   输入 'sentiment' 即可执行此分析")
    print("-" * 80)

    while True:
        user_input = input("\n>>> 您的问题或命令: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("感谢使用贴吧舆论分析系统，再见！")
            break
        elif user_input.lower() == 'help':
            print("\n📋 可用命令:")
            print("  - 'sentiment': 分析贴吧舆论情绪倾向")
            print("  - 'history': 查看聊天历史")
            print("  - 'clear': 清空聊天历史")
            print("  - 'help': 显示此帮助信息")
            print("  - 'quit' 或 'exit': 退出程序")
            print("\n💡 提示: 直接输入问题即可开始自由对话")
            continue
        elif user_input.lower() == 'history':
            if client:
                history = client.get_chat_history()
                if history:
                    print(f"\n📜 聊天历史 (共{len(history)}条):")
                    print("-" * 60)
                    for i, chat in enumerate(history, 1):
                        print(f"{i:2d}. [{chat['timestamp'][11:19]}]")
                        print(f"    Q: {chat['question'][:70]}" + ("..." if len(chat['question']) > 70 else ""))
                        if len(chat['answer']) > 50:
                            print(f"    A: {chat['answer'][:50]}...")
                        else:
                            print(f"    A: {chat['answer']}")
                        print()
                else:
                    print("暂无聊天历史")
            else:
                print("聊天客户端未初始化")
            continue
        elif user_input.lower() == 'clear':
            if client:
                confirm = input("确认清空聊天历史？(y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    client.clear_chat_history()
                    print("聊天历史已清空")
                else:
                    print("操作已取消")
            continue
        elif user_input.lower() == 'sentiment':
            question = sentiment_question
            print(f"\n[预设问题] {question}")
        elif not user_input:
            continue
        else:
            question = user_input

        try:
            print("[思考中", end="", flush=True)
            for i in range(3):
                time.sleep(0.3)
                print(".", end="", flush=True)
            print("]")

            # 使用客户端聊天
            if client:
                start_time = time.time()
                answer = client.chat(question, stream=False)
                elapsed_time = time.time() - start_time
                
                if answer:
                    # 显示回答
                    print(f"\n{'='*60}")
                    print("分析结果:")
                    print(f"{'='*60}")
                    print(answer)
                    print(f"{'='*60}")
                    print(f"⏱️  响应时间: {elapsed_time:.2f}秒")
                    print(f"📝 回答长度: {len(answer)} 字符")
                else:
                    print("[❌] 获取回答失败")
            else:
                print("[❌] 聊天客户端未初始化")
                
        except Exception as e:
            print(f"[❌] 获取回答失败: {e}")
            print("可能的原因：网络连接问题或服务未响应。")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断。")
    except Exception as e:
        print(f"\n[❌] 程序运行出现未预期错误: {e}")
        import traceback
        traceback.print_exc()