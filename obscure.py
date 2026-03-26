import mysql.connector
from sqlconnect import connect
import create_temp_db
import config
import subprocess
import os

# System databases that should not be obscured
SYSTEM_DATABASES = ['mysql', 'information_schema', 'performance_schema', 'sys']

def obscure_data(host, user, password, database, sql_file_path=config.obscure_file):
    """
    Obscure sensitive data in a database by cloning it and running SQL masking queries.
    
    Args:
        host: MySQL host
        user: MySQL user
        password: MySQL password
        database: Source database name
        sql_file_path: Path to SQL file containing obscuring queries
        
    Returns:
        str: Name of obscured temporary database, or None if failed
    """
    # Validation: Don't allow system databases
    if database in SYSTEM_DATABASES:
        print(f"[ERROR] Cannot obscure system database: {database}")
        return None
    
    # Validation: Check SQL file exists
    if not os.path.exists(sql_file_path):
        print(f"[ERROR] Obscure SQL file not found: {sql_file_path}")
        return None
    
    try:
        clone_db = create_temp_db.clone_db(host, user, password, database)
        
        if not clone_db:
            print("[ERROR] Database cloning failed")
            return None 

        print(f"Applying data masking...")
        if apply_sql_to_db(host, user, password, clone_db, sql_file_path):
             return clone_db
        else:
             return None

    except Exception as e:
        print(f"[ERROR] Failed to obscure data: {str(e)}")
        return None

def apply_sql_to_db(host, user, password, database, sql_file_path, logger=None):
    """
    Executes masking SQL on the given database
    """
    try:
        # Connect to the database using Python connector
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        
        cursor = conn.cursor()
        
        # Read the SQL file
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Split by semicolons and execute each statement
        # Filter out empty statements and comments
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
        
        success_count = 0
        warning_count = 0
        
        for i, statement in enumerate(statements, 1):
            if statement:
                try:
                    # Execute each statement
                    cursor.execute(statement)
                    conn.commit()
                    success_count += 1
                except mysql.connector.Error as e:
                    # Log errors but continue with other statements
                    # Table not existing is common and expected (obscure.sql has all possible tables)
                    if e.errno == 1146:  # Table doesn't exist
                        if logger:
                            # Skip logging - table not existing is expected
                            pass
                        warning_count += 1
                    else:
                        # Other errors should be logged as warnings
                        error_msg = f"Error executing statement {i}: {e}"
                        print(f"[WARNING] {error_msg}")
                        if logger:
                            logger.warning(error_msg, action="SQL_EXECUTION_WARNING")
                        warning_count += 1
                    continue
        
        cursor.close()
        conn.close()
        
        success_msg = f"✓ SQL script applied: {os.path.basename(sql_file_path)} ({success_count} statements executed"
        if warning_count > 0:
            success_msg += f", {warning_count} skipped/warnings)"
        else:
            success_msg += ")"
        
        print(success_msg)
        if logger:
            logger.info(success_msg, action="SQL_SCRIPT_APPLIED")
        
        return True
        
    except mysql.connector.Error as e:
        error_msg = f"MySQL error during SQL application: {e}"
        print(f"[ERROR] {error_msg}")
        if logger:
            logger.error(error_msg, action="SQL_APPLICATION_ERROR")
        return False
    except Exception as e:
        error_msg = f"Failed to execute SQL script: {e}"
        print(f"[ERROR] {error_msg}")
        if logger:
            logger.error(error_msg, action="SQL_APPLICATION_ERROR")
        return False