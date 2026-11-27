import time
from concurrent.futures import ThreadPoolExecutor


def read_file(name):
    time.sleep(1)
    return "读 " + name


def write_file(name, content):
    time.sleep(1)
    return "写 " + name


def run_tool(call):
    if call[0] == "read":
        return read_file(call[1])
    else:
        return write_file(call[1], call[2])


READ_ONLY = ["read"]


def run_batch(batch):
    start = time.time()
    can_parallel = all(call[0] in READ_ONLY for call in batch)
    if can_parallel:  # 全是读：并发
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(run_tool, call) for call in batch]
            results = [f.result() for f in futures]
    else:  # 有写：串行（原来的代码）
        results = []
        for call in batch:
            results.append(run_tool(call))
    print(results)
    print(f"耗时: {time.time() - start:.1f} 秒")


batch1 = [("read", "a.txt"), ("read", "b.txt"), ("read", "c.txt")]
batch2 = [("write", "d.txt", "你好"), ("read", "d.txt")]
run_batch(batch1)
run_batch(batch2)
