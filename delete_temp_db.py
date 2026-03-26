import mysql.connector
import time


def drop_temp_database(host, user, password, database):
    """
    Drops a temporary database safely using Python MySQL connector
    """

    # SAFETY CHECK VERY IMPORTANT
    # Allow temp databases OR databases starting with backup_ (auto-generated for default target)
    is_temp_db = "temp" in database.lower()
    is_backup_db = database.startswith("backup_")
    
    if not (is_temp_db or is_backup_db):
        raise RuntimeError(
            f"Refusing to drop database '{database}' - not a temp database"
        )

    # Retry logic for connection issues
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            # Use Python connector - more reliable than command line
            conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password
            )
            
            cursor = conn.cursor()
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except mysql.connector.Error as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                # Silent failure - manual cleanup may be needed
                return False
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return False
    
    return False

