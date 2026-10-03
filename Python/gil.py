import threading
import time


def task():
    for i in range(100000000):
        pass


t1 = threading.Thread(target=task)
t2 = threading.Thread(target=task)

time1 = time.time()

t1.start()
t2.start()

t1.join()
t2.join()

time2 = time.time()

print(time2 - time1)


# from multiprocessing import Process


# def compute():
#     for i in range(100000000):
#         pass

# if __name__ == "__main__":
#     p1 = Process(target=compute)
#     p2 = Process(target=compute)

#     time3 = time.time()
#     p1.start()
#     p2.start()

#     p1.join()
#     p2.join()

#     time4 = time.time()

#     print(f"Total execution time: {time4 - time3:.4f} seconds")
