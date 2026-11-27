import random
import time
from concurrent.futures import ThreadPoolExecutor

places = ["教室", "走廊", "操场"]
temps = [None] * len(places)  # 3 个空座位


def measure(idx, place):
    time.sleep(random.random())  # 时间随机
    temps[idx] = place + " 26度"


with ThreadPoolExecutor(max_workers=3) as executor:
    for i, p in enumerate(places):
        executor.submit(measure, i, p)

print(temps)
