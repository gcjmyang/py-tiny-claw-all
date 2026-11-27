import time
from concurrent.futures import ThreadPoolExecutor


def get_weather():
    time.sleep(2)
    return "天气：晴"


def get_news():
    time.sleep(1)
    return "新闻：运动会"


def get_schedule():
    time.sleep(3)
    return "日程：上课"


start = time.time()

with ThreadPoolExecutor(max_workers=3) as executor:
    # Fork：派 3 次活
    f1 = executor.submit(get_weather)
    f2 = executor.submit(get_news)
    f3 = executor.submit(get_schedule)
    # Join：凭小票取结果
    results = [f1.result(), f2.result(), f3.result()]

print(results)
print(f"总耗时: {time.time() - start:.1f} 秒")
