import mysql.connector
import config



def connect(host, user, password):
    try:
        conn = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        
        )

        print("Connection successful")
        return conn  # Return the connection object
        
    except mysql.connector.Error as e:
        print("Error: ", e)
        exit()
