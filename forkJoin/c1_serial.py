import time
from concurrent.futures import ThreadPoolExecutor
from forkJoin.a1_serial import results
from forkJoin.c1_answer import READ_ONLY


def read(name):
    time.sleep(1)
    return "读 " + name

def write(name, content):
    time.sleep(1)
    return "写 " + name

def registry(batch):
    if batch[0] == "read":
        return read(batch[1])
    else:
        return write(batch[1], batch[2])

def run(batchs):
    start = time.time()
    results = []
    for batch in batchs:
        results.append(registry(batch))
    print(results)
    print(f"耗时: {time.time() - start:.1f} 秒")

batchs1 = [("read", "a.txt"), ("read", "b.txt"), ("read", "c.txt")]
batchs2 = [("write", "d.txt", "你好"), ("read", "d.txt")]

READ_ONLY = ['read']



can_parallel = True
for batch in batchs1:
    if batch[0] not in READ_ONLY:
        can_parallel = False




run(batchs1)
run(batchs2)
