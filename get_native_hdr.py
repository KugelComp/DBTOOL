import subprocess
import os

try:
    cmd_init = ["mysql", "-u", "root", "-pKartikey@1", "-e", "CREATE DATABASE IF NOT EXISTS temp_test; USE temp_test; CREATE TABLE IF NOT EXISTS temp_t (id INT);"]
    subprocess.run(cmd_init, check=True)
    
    cmd = ["mysqldump", "-u", "root", "-pKartikey@1", "temp_test", "temp_t"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    with open("native_headers.txt", "w") as f:
        f.write(result.stdout[:2000])
    
    # Cleanup
    subprocess.run(["mysql", "-u", "root", "-pKartikey@1", "-e", "DROP DATABASE temp_test;"], check=True)
    
    print("Done! Check native_headers.txt")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Failed: {e}")
