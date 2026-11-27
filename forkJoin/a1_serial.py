import time
from concurrent.futures import ThreadPoolExecutor

def download(name):
    time.sleep(1)  # 下载要 1 秒
    return name + " 下载完成"

start = time.time()
pictures = ["猫.jpg", "狗.jpg", "兔.jpg"]

results = []
for p in pictures:
    results.append(download(p))  # 一张一张下

with ThreadPoolExecutor(max_workers=3) as executor:
    features = []
    for p in pictures:
        feature = executor.submit(download, p)
        features.append(feature)

    results = []
    for feature in features:
        results.append(feature.result())

with ThreadPoolExecutor(max_workers=3) as executor:
    features = [executor.submit(download, p) for p in pictures]
    results = [feature.result() for feature in features]

print(results)
print(f"总耗时: {time.time() - start:.1f} 秒")
