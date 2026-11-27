import random
import time
from concurrent.futures import ThreadPoolExecutor

names = ["小明", "小红", "小刚"]
results = []  # 共享列表

# def check(name):
#     time.sleep(random.random())  # 时间随机
#     results.append(name + " 已批改")  # 先完先放

results =[None] * len(names)
def check(idx, name):
    time.sleep(random.random())
    results[idx] = name + " 已批改"

with ThreadPoolExecutor(max_workers=3) as executor:
    for idx, name in enumerate(names):
        executor.submit(check, idx, name)

print(results)
