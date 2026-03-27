import os
import subprocess
import concurrent.futures
from debug_logger import log_debug

def perform_dump(host, user, password, database, dump_path, target_database_name=None, tables_to_dump=None, port=3306, job_control=None, 
                 include_views=False, include_routines=False, include_events=False, include_triggers=False, logger=None):
    """
    Exports the database with granular control over structure.
    """
    # Determine the database name to use in the dump files (source or renamed target)
    use_database_name = target_database_name if target_database_name else database

    # Create a directory for the database dump
    dump_dir = os.path.join(dump_path, database)
    if not os.path.exists(dump_dir):
        os.makedirs(dump_dir)

    print(f"Exporting database '{database}' (target: '{use_database_name}')...")
    print(f"Options: Views={include_views}, Routines={include_routines}, Events={include_events}, Triggers={include_triggers}")

    if job_control:
        job_control['status'] = "Preparing Export..."

    # 0. Create a database initialization script
    init_file = os.path.join(dump_dir, f"{use_database_name}_create_database.sql")
    if tables_to_dump is None or not os.path.exists(init_file):
        try:
            with open(init_file, "w", encoding='utf-8') as f:
                f.write(f"-- Database initialization script\n")
                f.write(f"CREATE DATABASE IF NOT EXISTS `{use_database_name}`;\n")
                f.write(f"USE `{use_database_name}`;\n\n")
        except Exception as e:
            if logger: logger.error(f"Failed to create init script: {e}", action="EXPORT_ERROR")
            return False, f"Failed to create init script: {e}", []

    tables = []
    if tables_to_dump:
        log_debug(f"Using provided tables: {len(tables_to_dump)}")
        tables = tables_to_dump
    else:
        try:
            # List Tables (and Views if requested)
            show_cmd = "SHOW TABLES" # Default All (Tables + Views)
            if not include_views:
                 # Filter only Base Tables
                 show_cmd = "SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'"
            
            list_cmd = [
                "mysql",
                "--protocol=TCP",
                "--skip-ssl",
                "-h", host,
                "-P", str(port),
                "-u", user
            ]
            if password:
                list_cmd.append(f"-p{password}")
            list_cmd.extend([
                "-D", database,
                "-N",
                "-e", show_cmd
            ])

            env = os.environ.copy()
            
            result = subprocess.run(list_cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                log_debug(f"SHOW TABLES failed: {result.stderr}")
                msg = f"Failed to list tables: {result.stderr}"
                print(f"[EXPORT DEBUG] mysql SHOW TABLES failed. CMD: {' '.join(list_cmd)}")
                print(f"[EXPORT DEBUG] STDERR: {result.stderr}")
                print(f"[EXPORT DEBUG] STDOUT: {result.stdout}")
                if logger: logger.error(msg, action="EXPORT_ERROR")
                return False, msg, []
            
            tables = []
            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = line.split('\t')
                if parts and parts[0]:
                    tables.append(parts[0])
            
            log_debug(f"Found {len(tables)} tables in {use_database_name}")

            if not tables:
                return True, "Database dump completed (no tables found)", []

        except Exception as e:
             if logger: logger.error(f"Error listing tables: {str(e)}", action="EXPORT_ERROR")
             return False, f"Error listing tables: {str(e)}", []
             
    # Update Job Control Total
    if job_control:
        job_control['progress']['total'] = len(tables)

    print(f"Exporting {len(tables)} objects...")
    failed_tables = []
    
    # Separate function to dump Routines and Events
    def dump_routines_events():
        # Check Cancel
        if job_control and job_control['cancel_event'].is_set(): return

        filename = f"{use_database_name}_routines.sql"
        output_file = os.path.join(dump_dir, filename)
        
        flags = ["--no-create-info", "--no-data", "--skip-triggers"]
        if include_routines: flags.append("--routines")
        if include_events: flags.append("--events")
        
        cmd = [
            "mysqldump",
            "--protocol=TCP",
            "--skip-ssl",
            "-h", host,
            "-P", str(port),
            "-u", user
        ]
        if password:
            cmd.append(f"-p{password}")
        cmd.extend([
            "--no-create-db"  # Prevent CREATE DATABASE in output
        ] + flags + [database])
        
        env = os.environ.copy()
            
        try:
            if job_control: job_control['pause_event'].wait()

            print(f"Exporting Routines ({include_routines}) and Events ({include_events})...")
            if job_control: job_control['status'] = "Exporting Routines & Events..."
            
            # Use timeout to prevent hanging
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True, timeout=300)
            
            out_text = result.stdout
            if use_database_name != database:
                out_text = out_text.replace(f"Database: {database}", f"Database: {use_database_name}")
            
            with open(output_file, "w", encoding='utf-8') as f:
                f.write(out_text)
                
        except subprocess.CalledProcessError as e:
            print(f"[WARN] Failed to dump routines/events: {e}")
            print(f"Details (STDERR): {e.stderr}")
            if logger: 
                logger.warning(f"Failed to dump routines/events: {e.stderr}", action="EXPORT_WARNING")
        except Exception as e:
            if logger:
                logger.warning(f"Failed to dump routines/events: {e}", action="EXPORT_WARNING")

    def dump_triggers():
        # Check Cancel
        if job_control and job_control['cancel_event'].is_set(): return

        filename = f"{use_database_name}_triggers.sql"
        output_file = os.path.join(dump_dir, filename)
        
        # Dump ONLY triggers
        cmd = [
            "mysqldump",
            "--protocol=TCP",
            "--skip-ssl",
            "-h", host,
            "-P", str(port),
            "-u", user
        ]
        if password:
            cmd.append(f"-p{password}")
        cmd.extend([
            "--no-create-db"  # Prevent CREATE DATABASE in output
        ] + ["--triggers", "--no-create-info", "--no-data", "--skip-opt"] + [database])
        # skip-opt is important to avoid adding other things, but we might need some opts.
        # Actually standard mysqldump doesn't have a clean "ONLY TRIGGERS" flag easily without dumping tables.
        # But if we use --no-create-info --no-data --triggers, it dumps triggers attached to tables.
        
        env = os.environ.copy()
            
        try:
            if job_control: job_control['pause_event'].wait()

            print(f"Exporting Triggers...")
            if job_control: job_control['status'] = "Exporting Triggers..."
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True, timeout=300)
            
            out_text = result.stdout
            if use_database_name != database:
                out_text = out_text.replace(f"Database: {database}", f"Database: {use_database_name}")
                
            with open(output_file, "w", encoding='utf-8') as f:
                f.write(out_text)
                
        except Exception as e:
            print(f"[WARN] Failed to dump triggers: {e}") 
            if logger:
                logger.warning(f"Failed to dump triggers: {e}", action="EXPORT_WARNING")

    # Dump Routines/Events if EITHER is requested
    if include_routines or include_events:
         dump_routines_events()

    if include_triggers:
         dump_triggers()

    # Parallel processing
    max_workers = min(os.cpu_count() or 4, 8)
    
    # Active Table Tracking
    active_tables = set()
    import threading
    status_lock = threading.Lock()

    def dump_single_table(table):
        import time
        start_time = time.time()
        
        # 1. Check Cancel
        if job_control and job_control['cancel_event'].is_set():
            return "CANCELLED"
        
        # 2. Check Pause
        if job_control: 
            job_control['pause_event'].wait()
            
            # Update Status (Start)
            with status_lock:
                active_tables.add(table)
                display_list = list(active_tables)[:2]
                remaining = len(active_tables) - 2
                status_text = f"Exporting: {', '.join(display_list)}"
                if remaining > 0: status_text += f" + {remaining} more..."
                job_control['status'] = status_text

        filename = f"{use_database_name}_{table}.sql"
        output_file = os.path.join(dump_dir, filename)
        
        # Triggers logic - ALWAYS SKIP in per-table dump (handled separately now)
        trigger_flag = "--skip-triggers"
        
        # Add --compress for stability if needed (optional, keeping standard for now)
        table_dump_cmd = [
            "mysqldump",
            "--protocol=TCP",
            "--skip-ssl",
            "-h", host,
            "-P", str(port),
            "-u", user
        ]
        if password:
            table_dump_cmd.append(f"-p{password}")
        table_dump_cmd.extend([
            "--single-transaction",
            "--add-drop-table",
            "--no-create-db",  # Prevent CREATE DATABASE in output
            "--max_allowed_packet=1G", # Handle large rows
            trigger_flag,
            database, 
            table
        ])
        
        env = os.environ.copy()
        
        f = None
        try:
            # MEMORY OPTIMIZATION: Write directly to file, don't buffer in RAM
            f = open(output_file, "w", encoding='utf-8')
            
            log_debug(f"START dump table {table}")
            
            # Execute mysqldump using Popen for better control
            proc = subprocess.Popen(
                table_dump_cmd, env=env, 
                stdout=f, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor Loop
            max_duration = 3600 # 1 hour timeout
            while proc.poll() is None:
                # Check Cancel
                if job_control and job_control['cancel_event'].is_set():
                    log_debug(f"CANCEL dump table {table} (User Request)")
                    proc.terminate()
                    try: proc.wait(timeout=5)
                    except: proc.kill()
                    f.close()
                    if os.path.exists(output_file): os.remove(output_file)
                    return "CANCELLED"
                
                # Check Timeout
                if time.time() - start_time > max_duration:
                    log_debug(f"TIMEOUT dump table {table}")
                    proc.terminate()
                    f.close()
                    if logger: logger.error(f"Timeout dumping {table}", action="EXPORT_TIMEOUT")
                    return table

                time.sleep(0.5)
            
            # Process finished
            _, stderr_output = proc.communicate()
            f.close()
            
            # Rewrite output file header to replace temporary database name
            if use_database_name != database:
                try:
                    with open(output_file, 'r+b') as pf:
                        head = pf.read(8192)
                        search_str = f"Database: {database}".encode('utf-8')
                        replace_str = f"Database: {use_database_name}".encode('utf-8')
                        if search_str in head:
                            if len(replace_str) < len(search_str):
                                replace_str = replace_str.ljust(len(search_str), b' ')
                            if len(replace_str) == len(search_str):
                                pf.seek(head.find(search_str))
                                pf.write(replace_str)
                except Exception as hdr_err:
                    log_debug(f"Warning: could not rewrite header in {table}: {hdr_err}")
            
            duration = time.time() - start_time
            log_debug(f"END dump table {table} ({duration:.2f}s)")
            
            # Warning for slow tables
            if duration > 60:
                print(f"[WARN] Table {table} took {duration:.2f}s")
                if logger: logger.warning(f"Flow table {table} took {duration:.2f}s", action="EXPORT_SLOW")

            # Check Success
            if proc.returncode != 0:
                err_msg = stderr_output or "Unknown Error"
                log_debug(f"FAIL dump table {table}: {err_msg}")
                print(f"[ERROR] Failed to dump table {table}: {err_msg}")
                if logger:
                    logger.error(f"Failed to dump table {table}: {err_msg}", action="EXPORT_TABLE_ERROR")
                # Remove incomplete file
                if os.path.exists(output_file): os.remove(output_file)
                return table 

            # Update Status (Finish)
            if job_control:
                job_control['progress']['current'] += 1
                with status_lock:
                    if table in active_tables: active_tables.remove(table)
                    if active_tables:
                        display_list = list(active_tables)[:2]
                        remaining = len(active_tables) - 2
                        status_text = f"Exporting: {', '.join(display_list)}"
                        if remaining > 0: status_text += f" + {remaining} more..."
                        job_control['status'] = status_text
                    else:
                        job_control['status'] = "Processing complete."

            return None 
            
        except Exception as e:
            if f: f.close()
            msg = f"Error dumping table {table}: {str(e)}"
            log_debug(f"EXCEPTION dump table {table}: {msg}")
            print(f"[ERROR] {msg}")
            if logger: logger.error(msg, action="EXPORT_TABLE_ERROR")
            if job_control: 
                job_control['progress']['current'] += 1
                with status_lock:
                    if table in active_tables: active_tables.remove(table)
            return table

    print(f"Exporting {len(tables)} tables sequentially...")
    
    results = []
    # Sequential Loop
    for t in tables:
        res = dump_single_table(t)
        results.append(res)
        
        # Check Cancel after each table (also handled inside dump_single_table)
        if job_control and job_control['cancel_event'].is_set():
             break
    
    if job_control and job_control['cancel_event'].is_set():
        return False, "Export Cancelled by User", []

    failed_tables = [t for t in results if t is not None and t != "CANCELLED"]

    # Create import instructions file
    readme_file = os.path.join(dump_dir, "README_IMPORT.txt")
    with open(readme_file, "w") as f:
        f.write(f"Export Date: {use_database_name}\n")
        f.write("Import Order for DB Tool (MySQL Workbench handles this automatically via Dump Project Folder):\n")
        f.write(f"1. {use_database_name}_create_database.sql\n")
        f.write(f"2. {use_database_name}_*.sql (Tables)\n")
        if include_routines or include_events:
            f.write(f"3. {use_database_name}_routines.sql\n")
        if include_triggers:
            f.write(f"4. {use_database_name}_triggers.sql\n")
            
    return True, "Export Completed Successfully", failed_tables
