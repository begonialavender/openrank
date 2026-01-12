
import requests
import json
import os
import time
from typing import Optional, Dict, Any, List

class MaxKBClient:
    
    
    def __init__(self, base_url='http://localhost:8080', admin_username='', admin_password='', 
                 workspace='default', api_key='', application_id=''):
        
        self.base_url = base_url.rstrip('/')
        self.workspace = workspace
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.api_key = api_key
        self.application_id = application_id
        
        # 会话管理 - 修复代理问题
        self.session = requests.Session()
        self.session.trust_env = False  # 不信任环境代理
        self.session.proxies = {"http": None, "https": None}  # 明确禁用代理
        
        self.bearer_token = None
        self.current_chat_id = None
        
        # API路径
        self.admin_api_base = f"{self.base_url}/admin/api"
        self.workspace_api_base = f"{self.admin_api_base}/workspace/{workspace}"
        self.chat_api_base = f"{self.base_url}/chat/api"
        
        # 初始化会话
        self._init_session()
        
        # 调试模式
        self.debug = True
    
    def _init_session(self):
        """初始化会话"""
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'MaxKB-Client/1.0',
        })
        
        # 如果有管理员凭据，先登录
        if self.admin_username and self.admin_password:
            self._admin_login()
    
    def _admin_login(self):
        """管理员登录"""
        login_url = f"{self.base_url}/admin/api/user/login"
        
        data = {
            "username": self.admin_username,
            "password": self.admin_password
        }
        
        try:
            # 使用会话对象，它会继承代理设置
            response = self.session.post(login_url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200 and 'data' in result and 'token' in result['data']:
                    self.bearer_token = result['data']['token']
                    self.session.headers['Authorization'] = f'Bearer {self.bearer_token}'
                    print(f"[✅] 管理员登录成功")
                    return True
                else:
                    print(f"[❌] 登录响应格式异常: {result}")
            else:
                print(f"[❌] 登录失败: {response.status_code}")
                print(f"响应: {response.text}")
                
        except Exception as e:
            print(f"[❌] 登录请求异常: {e}")
        
        return False
    
    # ==================== 聊天功能 ====================
    
    def open_chat_session(self):
        """打开聊天会话 - 使用会话对象避免代理"""
        url = f"{self.base_url}/chat/api/open"
        
        print(f"[🔄] 打开聊天会话: {url}")
        
        # 根据抓包结果，这个接口可能不需要任何认证
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'MaxKB-Client/1.0',
        }
        
        # 如果有API密钥，尝试添加认证
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        try:
            # 使用会话对象
            response = self.session.get(url, headers=headers, timeout=10)
            print(f"    状态码: {response.status_code}")
            print(f"    Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            if response.status_code == 200:
                # 尝试解析JSON
                try:
                    data = response.json()
                    print(f"    响应数据: {json.dumps(data, ensure_ascii=False)}")
                    
                    # 提取chat_id
                    chat_id = None
                    if isinstance(data, dict):
                        if 'data' in data:
                            chat_id = data['data']
                        elif 'chat_id' in data:
                            chat_id = data['chat_id']
                        elif 'id' in data:
                            chat_id = data['id']
                    elif isinstance(data, str) and len(data) > 20:
                        chat_id = data
                    
                    if chat_id:
                        self.current_chat_id = chat_id
                        print(f"[✅] 聊天会话已打开: {chat_id}")
                        return chat_id
                    else:
                        print(f"[⚠️] 无法从响应中提取chat_id")
                        
                except json.JSONDecodeError as e:
                    print(f"[⚠️] 响应不是有效的JSON: {e}")
                    print(f"    响应内容: {response.text[:200]}")
                    
                    # 如果不是JSON，可能是纯文本的chat_id
                    text_content = response.text.strip()
                    if text_content and len(text_content) > 20:
                        self.current_chat_id = text_content
                        print(f"[✅] 获取到纯文本chat_id: {text_content}")
                        return text_content
            else:
                print(f"[❌] 打开聊天会话失败: {response.status_code}")
                print(f"    响应: {response.text[:200]}")
                
        except Exception as e:
            print(f"[❌] 打开聊天会话异常: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def send_message(self, message, stream=True, re_chat=False):
        """发送消息 - 使用会话对象"""
        # 如果没有chat_id，先打开会话
        if not self.current_chat_id:
            self.current_chat_id = self.open_chat_session()
            if not self.current_chat_id:
                print("[❌] 无法获取聊天会话ID")
                return None
        
        print(f"[💬] 发送消息到会话: {self.current_chat_id}")
        print(f"[❓] 问题: {message}")
        
        url = f"{self.base_url}/chat/api/chat_message/{self.current_chat_id}"
        
        # 准备请求头
        headers = {
            'Accept': 'application/json, text/event-stream',
            'Content-Type': 'application/json',
            'User-Agent': 'MaxKB-Client/1.0',
        }
        
        # 添加认证（如果需要）
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        payload = {
            "message": message,
            "re_chat": re_chat,
            "stream": stream
        }
        
        try:
            if stream:
                # 流式响应（Server-Sent Events）
                print(f"[📡] 使用流式响应...")
                response = self.session.post(url, headers=headers, json=payload, 
                                           timeout=60, stream=True)
                
                print(f"    状态码: {response.status_code}")
                print(f"    Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                
                if response.status_code == 200:
                    full_content = ""
                    
                    # 处理Server-Sent Events格式
                    for line in response.iter_lines():
                        if line:
                            line_str = line.decode('utf-8')
                            
                            # 调试：打印原始行
                            if self.debug:
                                print(f"[调试] 原始行: {line_str[:100]}")
                            
                            # 处理SSE格式：以"data: "开头的行
                            if line_str.startswith('data: '):
                                data_content = line_str[6:]  # 去掉"data: "前缀
                                
                                # 如果是"[DONE]"表示结束
                                if data_content.strip() == '[DONE]':
                                    print(f"[✅] 流式响应结束")
                                    break
                                
                                try:
                                    # 解析JSON数据
                                    json_data = json.loads(data_content)
                                    
                                    # 提取内容
                                    content = None
                                    if 'data' in json_data and 'content' in json_data['data']:
                                        content = json_data['data']['content']
                                    elif 'content' in json_data:
                                        content = json_data['content']
                                    elif isinstance(json_data, str):
                                        content = json_data
                                    
                                    if content:
                                        print(content, end='', flush=True)
                                        full_content += content
                                        
                                except json.JSONDecodeError:
                                    # 如果不是JSON，直接输出
                                    if data_content.strip():
                                        print(data_content, end='', flush=True)
                                        full_content += data_content
                    
                    print()  # 换行
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
                print(f"    Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                
                if response.status_code == 200:
                    try:
                        # 尝试解析JSON
                        data = response.json()
                        print(f"    响应数据: {json.dumps(data, ensure_ascii=False)[:500]}")
                        
                        # 提取回答
                        answer = None
                        if 'data' in data and 'content' in data['data']:
                            answer = data['data']['content']
                        elif 'content' in data:
                            answer = data['content']
                        elif 'answer' in data:
                            answer = data['answer']
                        elif isinstance(data, str) and len(data) > 0:
                            answer = data
                        
                        if answer:
                            print(f"[✅] 获取到回答，长度: {len(answer)} 字符")
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
    
    def chat(self, message, stream=True):
        """统一的聊天方法"""
        return self.send_message(message, stream)
    
    # ==================== 知识库管理 ====================
    
    def list_knowledge_bases(self):
        """列出所有知识库"""
        url = f"{self.workspace_api_base}/knowledge"
        
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200 and 'data' in data:
                    return data['data']
            return []
            
        except Exception as e:
            print(f"[❌] 获取知识库失败: {e}")
            return []
    
    def get_knowledge_base(self, kb_id):
        """获取指定知识库详情"""
        url = f"{self.workspace_api_base}/knowledge/{kb_id}"
        
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200 and 'data' in data:
                    return data['data']
            return None
            
        except Exception as e:
            print(f"[❌] 获取知识库详情失败: {e}")
            return None
    
    # ==================== 文档上传 ====================
    
    # 在 api_client.py 的 upload_document 方法中

    def upload_document(self, kb_id, file_path):
    
        if not os.path.exists(file_path):
            print(f"[❌] 文件不存在: {file_path}")
            return False

        filename = os.path.basename(file_path)
        print(f"[📤] 正在上传文档: {filename} -> 知识库 {kb_id}")

        endpoint = f"{self.workspace_api_base}/knowledge/{kb_id}/document/split"
        
        print(f"    完整URL: {endpoint}")

        try:
            # 1. 以二进制模式读取文件
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # 2. 构建 multipart/form-data 数据
            files = {
                'file': (filename, file_content, 'text/plain; charset=utf-8')
            }
            data = {}

            print(f"    文件名: {filename}")
            print(f"    文件大小: {len(file_content)} 字节")

            # 3. 关键步骤：临时移除 Content-Type 头
            original_headers = self.session.headers.copy()
            if 'Content-Type' in self.session.headers:
                del self.session.headers['Content-Type']

            # 4. 发送请求
            response = self.session.post(endpoint, files=files, data=data, timeout=120)
            
            # 5. 恢复原始的 headers
            self.session.headers.clear()
            self.session.headers.update(original_headers)

            print(f"[📊] 响应状态: {response.status_code}")

            if response.status_code in [200, 201]:
                result = response.json()
                print(f"[📄] 响应内容: {json.dumps(result, ensure_ascii=False)}")

                if result.get('code') in [200, 201]:
                    segment_list = result.get('data', [])
                    
                    if isinstance(segment_list, list) and len(segment_list) > 0:
                        doc_name = segment_list[0].get('name', '未知文档')
                        total_paragraphs = len(segment_list[0].get('content', []))
                        print(f"[✅] 文档上传并解析成功！")
                        print(f"[📊] 文档名称: '{doc_name}'，共解析出 {total_paragraphs} 个内容段落。")
                        
                        # 转换为批量创建格式
                        documents_to_create = []
                        for doc_data in segment_list:
                            paragraphs = []
                            for segment in doc_data.get('content', []):
                                paragraphs.append({
                                    'title': segment.get('title', ''),
                                    'content': segment.get('content', ''),
                                    'similarity': 0.8
                                })
                            
                            documents_to_create.append({
                                'name': doc_data.get('name', ''),
                                'title': doc_data.get('name', ''),
                                'paragraphs': paragraphs,
                                'source_file_id': doc_data.get('source_file_id')
                            })
                        
                        # 批量创建段落
                        batch_create_url = f"{self.workspace_api_base}/knowledge/{kb_id}/document/batch_create"
                        print(f"[🔄] 正在将解析出的 {total_paragraphs} 个段落导入知识库...")
                        
                        try:
                            batch_response = self.session.put(batch_create_url, json=documents_to_create, timeout=60)
                            
                            if batch_response.status_code in [200, 201]:
                                batch_result = batch_response.json()
                                if batch_result.get('code') in [200, 201]:
                                    print(f"[✅] 知识库文档批量创建成功！知识库内容已更新。")
                                    return True
                                else:
                                    print(f"[⚠️] 段落导入时服务器返回业务错误: {batch_result.get('message')}")
                            else:
                                print(f"[⚠️] 段落导入请求失败 (HTTP {batch_response.status_code}): {batch_response.text[:200]}")
                        
                        except Exception as e:
                            print(f"[⚠️] 调用 batch_create 接口时发生异常: {e}")
                    else:
                        print(f"[⚠️] 文档解析后未获得有效内容段落")
                    
                    return False
                else:
                    print(f"[❌] 服务器返回业务逻辑错误: {result.get('message')}")
                    return False
            else:
                print(f"[❌] 请求失败 (HTTP {response.status_code}): {response.text[:500]}")
                return False

        except Exception as e:
            print(f"[❌] 上传过程发生异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_chat_connection(self):
        """测试聊天连接"""
        print(f"\n{'='*60}")
        print("测试聊天连接")
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
        test_questions = ["你好", "你是谁？"]
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n[Q{i}] {question}")
            answer = self.send_message(question, stream=False)
            
            if answer:
                print(f"[A{i}] {answer[:200]}" + ("..." if len(answer) > 200 else ""))
            else:
                print(f"[A{i}] 无回答")
        
        return True