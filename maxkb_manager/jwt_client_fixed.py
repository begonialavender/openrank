
import requests
import json
import time
from typing import Optional, List, Dict, Any

class MaxKBFixedClient:
    
    
    def __init__(self, base_url='http://localhost:8080', api_key=None, application_id=None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.application_id = application_id
        self.chat_id = None
        self.chat_history = []
        
        # 创建会话并禁用代理
        self.session = requests.Session()
        self.session.trust_env = False  # 不信任环境代理
        self.session.proxies = {"http": None, "https": None}  # 明确禁用代理
        
        # 设置基本headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
    
    def open_chat_session(self):
        """打开聊天会话 - 使用会话对象避免代理"""
        url = f"{self.base_url}/chat/api/open"
        
        print(f"[🔄] 打开聊天会话: {url}")
        
        # 使用API密钥作为Bearer Token
        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        try:
            # 使用会话对象，继承代理设置
            response = self.session.get(url, headers=headers, timeout=10)
            print(f"    状态码: {response.status_code}")
            print(f"    Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"    响应: {json.dumps(data, ensure_ascii=False)[:100]}")
                    
                    if data.get('code') == 200 and 'data' in data:
                        self.chat_id = data['data']
                        print(f"[✅] 聊天会话已打开: {self.chat_id}")
                        
                        # 保存认证头供后续使用
                        self.session.headers['Authorization'] = f'Bearer {self.api_key}'
                        
                        return self.chat_id
                    else:
                        print(f"[❌] 响应格式异常: {data.get('message', '未知错误')}")
                except json.JSONDecodeError:
                    
                    text_content = response.text.strip()
                    if len(text_content) > 20:
                        self.chat_id = text_content
                        print(f"[✅] 获取到纯文本chat_id: {self.chat_id}")
                        return self.chat_id
            else:
                print(f"[❌] 打开聊天会话失败: {response.status_code}")
                print(f"    响应: {response.text[:200]}")
                
        except Exception as e:
            print(f"[❌] 打开聊天会话异常: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    
    def send_message(self, message, stream=False):
    
        # 如果没有chat_id，先打开会话
        if not self.chat_id:
            self.chat_id = self.open_chat_session()
            if not self.chat_id:
                print("[❌] 无法获取聊天会话ID")
                return None
        
        # 防止重复调用
        if hasattr(self, '_last_message') and self._last_message == message:
            print("[⚠️] 检测到重复消息，跳过发送")
            return None
    
        self._last_message = message
       
        
        url = f"{self.base_url}/chat/api/chat_message/{self.chat_id}"
        
        print(f"\n[💬] 发送消息到会话: {self.chat_id}")
        print(f"[❓] 问题: {message}")
        
        # 使用会话的headers（包含认证信息）
        headers = {
            'Accept': 'application/json, text/event-stream',
            'Content-Type': 'application/json',
        }
        
        # 复制会话的认证头
        if 'Authorization' in self.session.headers:
            headers['Authorization'] = self.session.headers['Authorization']
        
        payload = {
            "message": message,
            "re_chat": False,
            "stream": stream
        }
        
        try:
            if stream:
                # 流式响应
                print(f"[📡] 使用流式响应...")
                response = self.session.post(url, headers=headers, json=payload, 
                                           timeout=60, stream=True)
                
                print(f"    状态码: {response.status_code}")
                
                if response.status_code == 200:
                    full_content = ""
                    print(f"[📥] 回答: ", end="", flush=True)
                    
                    for line in response.iter_lines():
                        if line:
                            line_str = line.decode('utf-8')
                            
                            # 处理SSE格式
                            if line_str.startswith('data: '):
                                data_content = line_str[6:]
                                
                                if data_content.strip() == '[DONE]':
                                    break
                                
                                try:
                                    json_data = json.loads(data_content)
                                    if 'data' in json_data and 'content' in json_data['data']:
                                        content = json_data['data']['content']
                                        print(content, end="", flush=True)
                                        full_content += content
                                    elif 'content' in json_data:
                                        content = json_data['content']
                                        print(content, end="", flush=True)
                                        full_content += content
                                except json.JSONDecodeError:
                                    if data_content.strip():
                                        print(data_content, end="", flush=True)
                                        full_content += data_content
                    
                    print()  # 换行
                    
                    # 保存到历史
                    self.chat_history.append({
                        "question": message,
                        "answer": full_content,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    return full_content
                else:
                    print(f"[❌] 流式响应失败: {response.status_code}")
                    print(f"    响应: {response.text[:500]}")
                    return None
            else:
                # 非流式响应
                print(f"[📡] 使用非流式响应...")
                response = self.session.post(url, headers=headers, json=payload, timeout=60)
                
                print(f"    状态码: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        # 提取回答内容
                        answer = None
                        if data.get('code') == 200 and 'data' in data and 'content' in data['data']:
                            answer = data['data']['content']
                        elif 'content' in data:
                            answer = data['content']
                        elif 'answer' in data:
                            answer = data['answer']
                        elif isinstance(data, str) and len(data) > 0:
                            answer = data
                        
                        if answer:
                            print(f"[📥] 回答: {answer[:200]}" + ("..." if len(answer) > 200 else ""))
                            
                            # 保存到历史
                            self.chat_history.append({
                                "question": message,
                                "answer": answer,
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                            })
                            
                            return answer
                        else:
                            print(f"[⚠️] 未找到回答内容")
                            return None
                            
                    except json.JSONDecodeError:
                        print(f"[⚠️] 响应不是JSON格式: {response.text[:200]}")
                        return response.text
                else:
                    print(f"[❌] 消息发送失败: {response.status_code}")
                    print(f"    响应: {response.text[:500]}")
                    return None
                    
        except Exception as e:
            print(f"[❌] 发送消息异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def chat(self, message, stream=False):
        """聊天接口（兼容旧代码）"""
        return self.send_message(message, stream)
    
    def test_connection(self):
        """测试连接"""
        print(f"\n{'='*60}")
        print("测试MaxKB修复客户端连接")
        print(f"{'='*60}")
        
        # 1. 测试打开聊天会话
        print(f"\n[1/3] 测试打开聊天会话...")
        chat_id = self.open_chat_session()
        
        if not chat_id:
            print(f"[❌] 无法打开聊天会话")
            return False
        
        print(f"[✅] 聊天会话ID: {chat_id}")
        
        # 2. 测试发送简单消息
        print(f"\n[2/3] 测试发送简单消息...")
        test_questions = ["你好", "介绍一下你自己"]
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n[Q{i}] {question}")
            answer = self.send_message(question, stream=False)
            
            if answer:
                print(f"[A{i}] {answer[:200]}" + ("..." if len(answer) > 200 else ""))
            else:
                print(f"[A{i}] 无回答")
        
        return True
    
    def get_chat_history(self):
        """获取聊天历史"""
        return self.chat_history
    
    def clear_chat_history(self):
        """清空聊天历史"""
        self.chat_history = []
        print("[✅] 聊天历史已清空")