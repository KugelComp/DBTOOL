
def log_debug(msg):
    try:
        with open("debug_trace.txt", "a") as f:
            f.write(f"{datetime.datetime.now()}: {msg}\n")
    except:
        pass
