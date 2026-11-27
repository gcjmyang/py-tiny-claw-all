import time
from concurrent.futures import ThreadPoolExecutor
from pyexpat import features


def download(name):
    time.sleep(1)  # 下载要 1 秒
    return name + " 下载完成"


start = time.time()
pictures = ["猫.jpg", "狗.jpg", "兔.jpg"]

with ThreadPoolExecutor(max_workers=3) as executor:
    # Fork：派活，拿小票
    futures = [executor.submit(download, p) for p in pictures]
    # Join：凭小票取结果
    results = [f.result() for f in futures]

with ThreadPoolExecutor(max_workers=3) as executor:
    features = []
    for p in pictures:
        feature = executor.submit(download, p)
        features.append(feature)

    results = []
    for f in features:
        results.append(f.result())

print(results)
print(f"总耗时: {time.time() - start:.1f} 秒")
