import time


def look_book(name):
    time.sleep(1)
    return "看 " + name


def edit_book(name, text):
    time.sleep(1)
    return "改 " + name


def run_tool(call):
    if call[0] == "look":
        return look_book(call[1])
    else:
        return edit_book(call[1], call[2])


def run_batch(batch):
    start = time.time()
    results = []
    for call in batch:
        results.append(run_tool(call))
    print(results)
    print(f"耗时: {time.time() - start:.1f} 秒")


batch1 = [("look", "西游记"), ("look", "红楼梦"), ("look", "水浒传")]
batch2 = [("edit", "西游记", "新序言"), ("look", "西游记")]
run_batch(batch1)
run_batch(batch2)
