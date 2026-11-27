import time


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

results = []
results.append(book_ticket("杭州"))
results.append(book_hotel("杭州", 2))
results.append(check_weather("杭州"))

print(results)
print(f"总耗时: {time.time() - start:.1f} 秒")
