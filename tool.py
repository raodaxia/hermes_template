from pathlib import Path
import json
import pandas as pd
from loguru import logger
    
sku = "H011682UK05 | H075406CANB110"
sku2 = "H242899ZA01390"
sku3 = "H242899ZA01440"

def process_sku(sku: str) -> str:
    """处理sku，返回mpn

    Args:
        sku (str): 两种sku, 一种是带|的，一种是不带|的. 如果带|的，取前25位作为mpn, 不带|的取前11位作为mpn

    Returns:
        str: 返回处理后规范的mpn
    """
    if '|' in sku:
        mpn = sku[0:26]
        return mpn
    return sku[0:11]

def generate_norepeat_sku(file_path: str) -> None:

    df = pd.read_excel(file_path)
    df["mpn"] = df.apply(lambda x: process_sku(x['sku']), axis=1)
    # 对mpn列去重
    df_unique = df.drop_duplicates(subset=['mpn'])
    df_unique.to_excel("unique_sku.xlsx", index=False)  
 

def process_json_files(root_dir: str, handler):
    """
    遍历目录下所有JSON文件并应用处理函数
    
    参数:
        root_dir (str or Path): 要搜索的根目录
        handler (function): 处理单个JSON数据的函数，接收两个参数:
                           - file_path: 文件路径(Path对象)
                           - data: JSON解析后的数据
    """
    root = Path(root_dir)
    
    for json_path in root.rglob('*.json'):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 处理解析的数据
                handler(data)
        except json.JSONDecodeError:
            logger.error(f"❌ JSON解析错误: {json_path}")
        except Exception as e:
            logger.error(f"❌ 处理文件出错 {json_path}: {e}")

#  调用示例
# generate_norepeat_sku("/Users/raodaxia/Documents/update_spus/2025年09月26日/副本out.xlsx") 