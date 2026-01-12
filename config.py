
import os
from pathlib import Path

# ==================== 项目路径配置 ====================
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CLEANED_DATA_DIR = DATA_DIR / "cleaned"
MAXKB_DOCS_DIR = DATA_DIR / "maxkb_docs"

# 确保目录存在
for dir_path in [DATA_DIR, RAW_DATA_DIR, CLEANED_DATA_DIR, MAXKB_DOCS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==================== MaxKB v2 配置 ====================
MAXKB_CONFIG = {
    # 基础URL
    "base_url": "http://localhost:8080",
    
    # ======【管理后台认证】=====
    "admin": {
        "username": "admin",
        "password": "Tian@123.",
        "workspace": "default"  # 默认工作空间
    },
    
    # ======【知识库配置】=====
    # 知识库ID（从知识库详情页URL获取）
    "knowledge_base_id": "019ba290-e38c-7652-a42b-e010a3579248",
    
    # ======【应用配置】=====
    "application": {
        "id": "019ba291-05d8-7fa0-ab34-e0dd256a7aca",  # 应用ID
        "name": "听涛",
        "api_key": "agent-51ebf92b169cdc8b923092833fe5be0f"  # 应用API密钥
    },

    
    #"jwt_token": "eyJhcHBsaWNhdGlvbl9pZCI6IjAxOWI5N2U3LThiNjktNzhlMC05NzU5LTUzMTg4NzY3OTVmYyIsInVzZXJfaWQiOiJOb25lIiwiYWNjZXNzX3Rva2VuIjoiMTVjZjZiODE5OWRkMmY0MiIsInR5cGUiOiJDSEFUX0FOT05ZTU9VU19VU0VSIiwiY2hhdF91c2VyX3R5cGUiOiJBTk9OWU1PVVNfVVNFUiIsImNoYXRfdXNlcl9pZCI6IjAxOWI5ODA0LTU5ODUtN2U3MS1hNThlLTVmOGM4OTI1ODQyZSIsImF1dGhlbnRpY2F0aW9uIjoiZXVDbzlmNjkrZEYyaUNxYnUyY1VBK0FibS9oZ1NLdk52Qyt6KzRDK0xKcHNNVE1FTlRTbjNGQnpLdnpDcktxbE1",
    
    # ======【上传配置】=====
    "upload": {
        "chunk_size": 1000,  # 分块大小（字符数）
        "max_file_size": 10 * 1024 * 1024,  # 最大10MB
        "supported_formats": [".txt", ".md", ".json", ".pdf"]
    },
    
    # API超时设置
    "timeout": 120
}

# ==================== 日志配置 ====================
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": BASE_DIR / "tieba_analysis.log",
}

# ==================== 调试开关 ====================
DEBUG = True