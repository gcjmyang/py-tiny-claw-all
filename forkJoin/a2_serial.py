import time


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

results = []
results.append(get_weather())
results.append(get_news())
results.append(get_schedule())

print(results)
print(f"总耗时: {time.time() - start:.1f} 秒")
