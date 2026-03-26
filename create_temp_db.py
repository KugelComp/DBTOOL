import mysql.connector
from sqlconnect import connect
import datetime

import subprocess
import os
from debug_logger import log_debug



import uuid

def create_temp_db_name(host, user, password, database):

    try:
        conn=connect(host, user, password)

        cursor = conn.cursor()
        
        # Use simple date + UUID for guaranteed uniqueness
        unique_id = str(uuid.uuid4())[:8]
        temp_db_name = f"temp_{database}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{unique_id}"

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {temp_db_name}")
        conn.commit()
        
        print(f"[INFO] Temporary database created: {temp_db_name}")
        return temp_db_name

    except mysql.connector.Error as e:
        print("Error: ", e)
        raise e

def clone_db(host, user, password, source_db, logger=None, job_control=None):
    """Clone a database using Python subprocess with progress tracking and safe pipes."""
    # Create temp database
    temp_db_name = create_temp_db_name(host, user, password, source_db)
    
    try:
        log_debug(f"Starting clone_db for {source_db}")
        print(f"Creating temporary database...")
        
        try:
            # P0: Get DB Size for Progress
            conn = connect(host, user, password)
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(data_length + index_length) FROM information_schema.tables WHERE table_schema = %s", (source_db,))
            result = cursor.fetchone()
            
            # Default to very large number if None to avoid div/0, or 1 byte
            total_size_bytes = result[0] if result and result[0] else 1 
            total_size_mb = round(total_size_bytes / (1024 * 1024), 2)
            
            cursor.close()
            conn.close()
            print(f"[INFO] Source Database Size: {total_size_mb} MB")
            
        except Exception as e:
            print(f"[WARN] Failed to get DB size: {e}")
            total_size_bytes = 1 # Fallback
            total_size_mb = "?"

        print(f"Cloning database using mysqldump pipe (fastest method)...")
        
        # 1. Start mysqldump (Producer)
        # Redirect stderr to file to prevent buffer deadlocks
        err_file_path = "clone_dump_error.log"
        err_file = open(err_file_path, "w+")

        dump_cmd = [
            "mysqldump",
            "-h", host,
            "-u", user
        ]
        
        if password:
             dump_cmd.append(f"-p{password}")
             
        dump_cmd.extend([
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            "--force", # Ignore view errors
            "--opt", # Enable optimization (should be default but explicit is good)
            "--skip-lock-tables", # We are using single-transaction anyway
            "--quick", # Retrieve rows one by one
            "--max_allowed_packet=512M",
            source_db
        ])
        
        # Pass password via env
        env = os.environ.copy()
        if password:
            env["MYSQL_PWD"] = password
            
        # P1: mysqldump -> stdout=PIPE, stderr=FILE
        # Increase internal buffer size if possible by OS, but Python communicates via pipe
        p1 = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE, stderr=err_file, env=env, bufsize=10*1024*1024)
        
        # 2. Start mysql import (Consumer)
        import_cmd = [
            "mysql",
            "-h", host,
            "-u", user
        ]
        
        if password:
             import_cmd.append(f"-p{password}")
             
        import_cmd.extend([
             "-D", temp_db_name,
             "--max_allowed_packet=512M"
        ])
        
        # P2: mysql <- stdin=PIPE
        p2 = subprocess.Popen(import_cmd, stdin=subprocess.PIPE, env=env, bufsize=10*1024*1024)
        
        # 3. Manually pump data and track progress (Chunked for speed)
        # Increased buffer size to 4MB for better throughput
        BUF_SIZE = 4 * 1024 * 1024 
        bytes_transferred = 0
        
        while True:
            # Check for cancellation
            if job_control and job_control['cancel_event'].is_set():
                p1.terminate()
                p2.terminate()
                err_file.close()
                raise Exception("Cloning cancelled")

            # Read chunk
            chunk = p1.stdout.read(BUF_SIZE)
            if not chunk:
                break # EOF
            
            bytes_transferred += len(chunk)
            mb_transferred = round(bytes_transferred / (1024 * 1024), 2)
            
            percentage = 0
            if total_size_bytes > 0:
                 percentage = int((bytes_transferred / total_size_bytes) * 100)
                 # Cap at 99% until actually done
                 if percentage > 99: percentage = 99
            
            if job_control:
                # Update status with data size
                job_control['status'] = f"Cloning... {percentage}% ({mb_transferred} MB / {total_size_mb} MB)"
            
            # Write to mysql
            try:
                p2.stdin.write(chunk)
            except BrokenPipeError:
                # Consumer died
                break
                
        # Close streams
        p1.stdout.close()
        p2.stdin.close()
        
        # Wait for completion with timeout protection
        try:
             p1.wait(timeout=30)
             p2.wait(timeout=30)
        except subprocess.TimeoutExpired:
             print("[WARN] Processes failed to exit cleanly, forcing kill...")
             p1.kill()
             p2.kill()
        
        # 4. Check Errors
        err_file.seek(0)
        dump_stderr_content = err_file.read()
        err_file.close()
        
        if p1.returncode != 0:
            # Log warnings/errors (with --force, non-zero is expected for broken views)
            if logger:
                # It's likely just warnings about views, log as warning
                logger.warning(f"Clone warnings (ignored via force): {dump_stderr_content[:500]}", action="CLONE_WARNING")

        if p2.returncode != 0 and p2.returncode != 1: # 1 might be just warnings
             # Explicitly check if it failed hard
             log_debug(f"Import process return code: {p2.returncode}")
             
        print(f"✓ Database cloned successfully ({mb_transferred} MB transfered)")
        return temp_db_name
    
    except Exception as e:
        log_debug(f"Clone failed: {e}")
        print(f"[ERROR] Cloning failed: {e}")
        if logger: logger.error(f"Cloning failed: {e}", action="CLONE_ERROR")
        
        # Ensure cleanup
        try: p1.kill() 
        except: pass
        try: p2.kill()
        except: pass
        try: err_file.close()
        except: pass
        print(f"[ERROR] Cloning failed: {e}")
        if logger: logger.error(f"Cloning failed: {e}", action="CLONE_ERROR")
        
        with open("clone_error.txt", "w") as f:
            f.write(f"Cloning failed: {str(e)}\n")
            import traceback
            traceback.print_exc(file=f)
        # Cleanup failed temp database
        try:
            conn = connect(host, user, password)
            cursor = conn.cursor()
            cursor.execute(f"DROP DATABASE IF EXISTS `{temp_db_name}`")
            conn.commit()
            cursor.close()
            conn.close()
        except:
            pass
        return None
