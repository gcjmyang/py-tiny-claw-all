import random
import time
from concurrent.futures import ThreadPoolExecutor

names = ["小明", "小红", "小刚"]
results = [None] * len(names)  # 3 个空座位


def check(idx, name):
    time.sleep(random.random())  # 时间随机
    results[idx] = name + " 已批改"  # 坐自己的座位


with ThreadPoolExecutor(max_workers=3) as executor:
    for i, n in enumerate(names):
        executor.submit(check, i, n)

print(results)
