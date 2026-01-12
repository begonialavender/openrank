import subprocess
import time
import os

class MaxKBDeployer:
    def __init__(self, compose_path='./docker-compose.yml'):
        self.compose_path = compose_path

    def start(self):
        """启动MaxKB服务"""
        try:
            # 使用docker-compose启动服务
            subprocess.run(['docker-compose', '-f', self.compose_path, 'up', '-d'], 
                          check=True, capture_output=True, text=True)
            print("[✅] MaxKB服务启动命令已发送。")
            
            self._wait_for_service()
        except subprocess.CalledProcessError as e:
            print(f"[❌] 启动MaxKB服务失败: {e.stderr}")

    def _wait_for_service(self, timeout=120):
        """等待MaxKB服务完全就绪"""
        print("[⏳] 等待MaxKB服务就绪...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            
            time.sleep(5)
            print("  服务启动中...")
        print("[✅] 服务等待完成（建议手动确认 http://localhost:8080 可访问）。")

    def stop(self):
        """停止MaxKB服务"""
        subprocess.run(['docker-compose', '-f', self.compose_path, 'down'])
        print("[✅] MaxKB服务已停止。")