import time
from concurrent.futures import ThreadPoolExecutor


def book_ticket(city):
    time.sleep(2)
    return "车票：" + city


def book_hotel(city, nights):
    time.sleep(3)
    return "酒店：" + city + str(nights) + "晚"


def check_weather(city):
    time.sleep(1)
    return "天气：" + city + "多云"


start = time.time()

with ThreadPoolExecutor(max_workers=3) as executor:
    # Fork：参数跟在函数名后
    f1 = executor.submit(book_ticket, "杭州")
    f2 = executor.submit(book_hotel, "杭州", 2)
    f3 = executor.submit(check_weather, "杭州")
    # Join：凭小票取结果
    results = [f1.result(), f2.result(), f3.result()]

print(results)
print(f"总耗时: {time.time() - start:.1f} 秒")
