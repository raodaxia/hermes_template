"""_summary_

Raises:
    Exception: _description_
    Exception: _description_

Returns:
    _type_: _description_
"""

import os
import time
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from DrissionPage import Chromium, ChromiumOptions  # 新增ChromiumOptions导入
from tenacity import retry, stop_after_attempt, wait_fixed
# from fake_useragent import UserAgent

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawl.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 测试 URL 列表


# 保存文件的文件夹
save_dir = 'html_pages'
os.makedirs(save_dir, exist_ok=True)

# 已完成的URL记录文件
COMPLETED_FILE = 'completed_urls.txt'
# 检测封禁的关键词（保留作为辅助检测）
BLOCK_KEYWORDS = ["您的访问已被禁止", "访问被拒绝", "403 Forbidden"]

# 配置无痕模式
co = ChromiumOptions()
co.incognito() # 添加无痕模式参数
# 全局浏览器实例（使用无痕模式）
browser = Chromium(co)
# 随机 User-Agent 生成器
# ua = UserAgent()

def load_urls(url_file: str='urls.txt'):
    """从文件加载URL列表"""
    if os.path.exists(url_file):
        with open(url_file, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    return []

urls = load_urls()

def load_completed_urls():
    """加载已完成的URL列表，避免重复爬取"""
    if os.path.exists(COMPLETED_FILE):
        with open(COMPLETED_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_completed_url(url):
    """保存已完成的URL到文件"""
    with open(COMPLETED_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{url}\n")


def extract_filename(url):
    """从URL中提取产品编号作为文件名（如H242899ZA01）"""
    # 正则匹配产品编号模式（H开头+数字和字母组合）
    match = re.search(r'H\d+[A-Z0-9]+', url)
    if match:
        product_code = match.group()
        # 截取前12位（根据示例H242899ZA01390 -> H242899ZA01）
        return f"{product_code[:12]}.html"
    #  fallback: 使用原始处理方式
    return (
        url.replace('https://', '').replace('http://', '')
        .translate(str.maketrans({'/': '_', ':': '_', '?': '_', '&': '_', '=': '_'}))
        .strip('_') + '.html'
    )


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
def fetch_and_save(url):
    """爬取HTML并保存到本地（带重试机制和封禁检测）"""
    tab = None
    try:
        # 新建标签页并设置随机请求头
        tab = browser.new_tab()
        # tab.set.headers({'User-Agent': ua.random})
        
        # 带超时的页面请求
        tab.get(url, timeout=15)
        
        # 智能等待页面加载
        tab.wait(10, 15)
        
        # 获取页面HTML
        html = tab.html
        
        # 检测h1元素是否存在（主要封禁判断依据）
        h1_elements = tab.ele('tag:h1')
        if not h1_elements:  # 如果没有找到h1元素
            logging.error(f"未检测到h1元素，可能被封禁，URL: {url}")
            raise Exception("访问被禁止，未找到h1元素")
        
        # 辅助检测：关键词匹配（保留作为双重保险）
        for keyword in BLOCK_KEYWORDS:
            if keyword in html:
                logging.error(f"检测到封禁关键词，URL: {url}")
                raise Exception("访问被禁止，检测到封禁关键词")
        
        # 生成文件名并保存
        filename = extract_filename(url)
        filepath = os.path.join(save_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logging.info(f"保存完成: {url} -> {filename}")
        save_completed_url(url)  # 记录已完成的URL
        return True
    
    except Exception as e:
        logging.error(f"爬取失败: {url}, 错误: {str(e)}")
        raise  # 抛出异常以触发重试
    
    finally:
        if tab:
            tab.close()


if __name__ == '__main__':
    start_time = time.time()
    success_count = 0
    fail_count = 0
    blocked = False  # 标记是否被封禁
    
    # 加载已完成的URL，只处理未完成的
    completed_urls = load_completed_urls()
    urls_to_process = [url for url in urls if url not in completed_urls]
    
    logging.info(f"待处理URL数量: {len(urls_to_process)}, 已完成: {len(completed_urls)}")
    
    # 调整并发数
    max_threads = 1  # 降低并发以减少被封禁概率
    
    try:
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = {executor.submit(fetch_and_save, url): url for url in urls_to_process}
            
            for future in as_completed(futures):
                url = futures[future]
                try:
                    result = future.result()
                    if result:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as exc:
                    # 检测是否是封禁错误
                    if "访问被禁止" in str(exc):
                        blocked = True
                        logging.error("检测到封禁，停止所有爬取任务")
                        # 取消所有未完成的任务
                        for f in futures:
                            if not f.done():
                                f.cancel()
                        break
                    logging.error(f"{url} 最终失败: {str(exc)}")
                    fail_count += 1
                if blocked:
                    break
    
    finally:
        browser.quit()
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # 输出统计结果
    logging.info(f"爬取完成 - 总耗时: {total_time:.2f} 秒")
    logging.info(f"成功: {success_count} 个, 失败: {fail_count} 个")
    print(f"\n爬取总结: 成功 {success_count} 个, 失败 {fail_count} 个, 总耗时 {total_time:.2f} 秒")
    if blocked:
        print("检测到访问被禁止，请更换IP后重新运行程序，将从失败处继续爬取")