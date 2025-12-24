import bcrypt
import mysql.connector
from mysql.connector import Error

class phpBBAuth:
    def __init__(self, db_config):
        """
        db_config: dict with host, user, password, database, prefix
        """
        self.config = db_config

    def verify_password(self, password, hashed_password):
        # phpBB password hashes start with $2y$ (bcrypt)
        # Python's bcrypt expects bytes
        try:
            # Handle phpBB's bcrypt prefix if necessary (bcrypt lib expects $2b$ or $2a$)
            # Most modern bcrypt libs handle $2y$ fine.
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False

    def authenticate(self, username, password):
        connection = None
        try:
            connection = mysql.connector.connect(
                host=self.config['host'],
                database=self.config['database'],
                user=self.config['user'],
                password=self.config['password']
            )
            if connection.is_connected():
                cursor = connection.cursor(dictionary=True)
                table = f"{self.config['prefix']}users"
                query = f"SELECT user_id, username, user_password, user_email FROM {table} WHERE username_clean = %s"
                cursor.execute(query, (username.lower(),))
                user = cursor.fetchone()

                if user and self.verify_password(password, user['user_password']):
                    return {
                        'id': user['user_id'],
                        'username': user['username'],
                        'email': user['user_email']
                    }
                return None

        except Error as e:
            # log or print error
            return None
        finally:
            if connection and connection.is_connected():
                connection.close()
