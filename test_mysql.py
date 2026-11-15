import mysql.connector

try:
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="@Suman2002"
    )

    if connection.is_connected():
        print("Successfully connected to MySQL!")
        print("MySQL Version:", connection.get_server_info())

except mysql.connector.Error as error:
    print("MySQL Connection Error:", error)

finally:
    if 'connection' in locals() and connection.is_connected():
        connection.close()
        print("Connection closed.")