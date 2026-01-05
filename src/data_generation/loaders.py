"""
Data loader for inserting synthetic data into PostgreSQL.
Handles bulk inserts with transaction management.
"""

import logging
from typing import List

import psycopg2
from psycopg2.extras import execute_batch
from .schemas import BillingEventSchema, UserEventSchema, UserSchema

logger = logging.getLogger(__name__)


class DataLoader:
    """Loads synthetic data into PostgreSQL."""

    def __init__(
        self,
        host: str = "postgres",
        port: int = 5432,
        database: str = "churn_db",
        user: str = "churn_user",
        password: str = "churn_password",
    ):
        """
        Initialize database connection parameters.
        
        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
        """
        self.connection_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }
        self.conn = None

    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.connection_params)
            logger.info(f"Connected to PostgreSQL: {self.connection_params['host']}")
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from PostgreSQL")

    def insert_users(self, users: List[UserSchema], batch_size: int = 1000) -> int:
        """
        Insert users into raw_data.users table.
        
        Args:
            users: List of user records
            batch_size: Number of records per batch insert
            
        Returns:
            Number of rows inserted
        """
        if not users:
            return 0

        cursor = self.conn.cursor()
        try:
            sql = """
                INSERT INTO raw_data.users (user_id, plan_type, signup_date, country)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """

            records = [
                (u.user_id, u.plan_type, u.signup_date, u.country) for u in users
            ]

            execute_batch(cursor, sql, records, page_size=batch_size)
            self.conn.commit()
            
            logger.info(f"Inserted {len(users)} users")
            return len(users)

        except psycopg2.Error as e:
            self.conn.rollback()
            logger.error(f"Error inserting users: {e}")
            raise
        finally:
            cursor.close()

    def insert_user_events(
        self, events: List[UserEventSchema], batch_size: int = 5000
    ) -> int:
        """
        Insert user events into raw_data.user_events table.
        
        Args:
            events: List of user event records
            batch_size: Number of records per batch insert
            
        Returns:
            Number of rows inserted
        """
        if not events:
            return 0

        cursor = self.conn.cursor()
        try:
            sql = """
                INSERT INTO raw_data.user_events 
                (user_id, event_type, event_time, session_id)
                VALUES (%s, %s, %s, %s)
            """

            records = [
                (e.user_id, e.event_type, e.event_time, e.session_id)
                for e in events
            ]

            execute_batch(cursor, sql, records, page_size=batch_size)
            self.conn.commit()
            
            logger.info(f"Inserted {len(events)} user events")
            return len(events)

        except psycopg2.Error as e:
            self.conn.rollback()
            logger.error(f"Error inserting user events: {e}")
            raise
        finally:
            cursor.close()

    def insert_billing_events(
        self, events: List[BillingEventSchema], batch_size: int = 5000
    ) -> int:
        """
        Insert billing events into raw_data.billing_events table.
        
        Args:
            events: List of billing event records
            batch_size: Number of records per batch insert
            
        Returns:
            Number of rows inserted
        """
        if not events:
            return 0

        cursor = self.conn.cursor()
        try:
            sql = """
                INSERT INTO raw_data.billing_events 
                (user_id, amount, status, event_time)
                VALUES (%s, %s, %s, %s)
            """

            records = [
                (e.user_id, e.amount, e.status, e.event_time) for e in events
            ]

            execute_batch(cursor, sql, records, page_size=batch_size)
            self.conn.commit()
            
            logger.info(f"Inserted {len(events)} billing events")
            return len(events)

        except psycopg2.Error as e:
            self.conn.rollback()
            logger.error(f"Error inserting billing events: {e}")
            raise
        finally:
            cursor.close()

    def get_row_counts(self) -> dict:
        """Get current row counts for all tables."""
        cursor = self.conn.cursor()
        try:
            counts = {}
            for table in ["users", "user_events", "billing_events"]:
                cursor.execute(f"SELECT COUNT(*) FROM raw_data.{table}")
                counts[table] = cursor.fetchone()[0]
            return counts
        finally:
            cursor.close()


def load_data(
    users,
    user_events,
    billing_events,
    host: str = "postgres",
    port: int = 5432,
    database: str = "churn_db",
    user: str = "churn_user",
    password: str = "churn_password",
) -> dict:
    """
    Convenience function to load all data at once.
    
    Args:
        users: List of user records
        user_events: List of user event records
        billing_events: List of billing event records
        host: Database host
        port: Database port
        database: Database name
        user: Database user
        password: Database password
        
    Returns:
        Dictionary with row counts
    """
    loader = DataLoader(host=host, port=port, database=database, user=user, password=password)
    
    try:
        loader.connect()
        loader.insert_users(users)
        loader.insert_user_events(user_events)
        loader.insert_billing_events(billing_events)
        
        counts = loader.get_row_counts()
        logger.info(f"Final counts: {counts}")
        return counts
    finally:
        loader.disconnect()
