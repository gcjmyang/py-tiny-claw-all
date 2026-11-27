import random
import time
from concurrent.futures import ThreadPoolExecutor

places = ["教室", "走廊", "操场"]
temps = []  # 共享列表


def measure(place):
    time.sleep(random.random())  # 时间随机
    temps.append(place + " 26度")


with ThreadPoolExecutor(max_workers=3) as executor:
    for p in places:
        executor.submit(measure, p)

print(temps)
