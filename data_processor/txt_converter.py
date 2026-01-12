
import json
import os
from datetime import datetime
from pathlib import Path

class TXTConverter:
    
    
    def __init__(self, output_dir="./data/maxkb_docs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def convert_for_maxkb(self, json_path, source_name="tieba_data"):
    
        print(f"[INFO] 转换JSON文件: {json_path}")
        
        try:
            # 读取JSON数据
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[❌] 读取JSON失败: {e}")
            raise
        
        # 生成TXT内容
        if isinstance(data, list):
            content = self._convert_list(data, source_name)
        elif isinstance(data, dict):
            content = self._convert_dict(data, source_name)
        else:
            raise TypeError(f"不支持的数据类型: {type(data)}")
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"maxkb_{source_name}_{timestamp}.txt"
        output_path = self.output_dir / filename
        
        # 保存文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[✅] TXT文件已生成: {output_path}")
        print(f"     文件大小: {os.path.getsize(output_path)} 字节")
        
        return str(output_path)
    
    def _convert_list(self, data_list, source_name):
        """转换列表数据"""
        if not data_list:
            return "# 空数据列表\n"
        
        lines = []
        lines.append(f"# 贴吧数据分析文档 - {source_name}\n")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"数据条数: {len(data_list)}\n")
        lines.append("=" * 60 + "\n")
        
        for idx, item in enumerate(data_list, 1):
            lines.append(f"\n## 记录 {idx}\n")
            lines.append("-" * 40 + "\n")
            
            if isinstance(item, dict):
                for key, value in item.items():
                    value_str = str(value)
                    # 清理和格式化值
                    if len(value_str) > 300:
                        value_str = value_str[:297] + "..."
                    lines.append(f"{key}: {value_str}\n")
            else:
                lines.append(f"数据: {str(item)}\n")
            
            lines.append("-" * 40 + "\n")
        
        # 添加总结
        lines.append(f"\n## 数据总结\n")
        lines.append(f"共收集 {len(data_list)} 条贴吧数据\n")
        
        return ''.join(lines)
    
    def _convert_dict(self, data_dict, source_name):
        """转换字典数据"""
        lines = []
        lines.append(f"# 贴吧数据摘要 - {source_name}\n")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("=" * 60 + "\n")
        
        for key, value in data_dict.items():
            value_str = str(value)
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False, indent=2)
                if len(value_str) > 500:
                    value_str = value_str[:497] + "..."
            elif len(value_str) > 200:
                value_str = value_str[:197] + "..."
            
            lines.append(f"## {key}\n")
            lines.append(f"{value_str}\n\n")
        
        return ''.join(lines)

# 便捷函数，用于兼容旧代码
def convert_cleaned_json_to_txt(cleaned_json_path, output_txt_dir="./data/maxkb_docs"):
    """
    将清洗后的JSON文件转换为TXT文件的便捷函数
    注意：这是一个包装函数，实际使用 TXTConverter 类
    """
    converter = TXTConverter(output_dir=output_txt_dir)
    # 从文件名提取贴吧名称
    base_name = os.path.basename(cleaned_json_path)
    if 'cleaned_' in base_name:
        name_part = base_name.replace('cleaned_', '').replace('.json', '')
        tieba_name = name_part.split('_')[0] if '_' in name_part else name_part
    else:
        tieba_name = "贴吧数据"
    
    return converter.convert_for_maxkb(cleaned_json_path, tieba_name)