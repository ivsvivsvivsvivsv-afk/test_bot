"""
Database module для НЕЙРО-ЮНИТ бота.

HIGHLOAD АРХИТЕКТУРА:
- PostgreSQL через asyncpg (connection pooling)
- Fallback на SQLite для локальной разработки
- Поддержка горизонтального масштабирования

Для 100K+ пользователей используйте PostgreSQL!
"""

import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# ABSTRACT DATABASE INTERFACE
# =============================================================================

class DatabaseInterface(ABC):
    """Абстрактный интерфейс базы данных."""
    
    @abstractmethod
    async def init(self) -> None:
        pass
    
    @abstractmethod
    async def close(self) -> None:
        pass
    
    @abstractmethod
    async def save_user(self, user_id: int, username: str, first_name: str, 
                       specialization: str, weapon: str) -> None:
        pass
    
    @abstractmethod
    async def save_contacts(self, user_id: int, phone: str, email: str, name: str) -> None:
        pass
    
    @abstractmethod
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    async def user_exists(self, user_id: int) -> bool:
        pass
    
    # Promo methods
    @abstractmethod
    async def get_promo_slots(self) -> int:
        pass
    
    @abstractmethod
    async def decrement_promo_slots(self) -> int:
        pass
    
    @abstractmethod
    async def save_promo_message(self, user_id: int, chat_id: int, 
                                 message_id: int, status: str = 'sent') -> None:
        pass
    
    @abstractmethod
    async def get_user_promo_status(self, user_id: int) -> Optional[str]:
        pass
    
    @abstractmethod
    async def update_promo_status(self, user_id: int, status: str, 
                                  payment_id: Optional[str] = None) -> None:
        pass
    
    @abstractmethod
    async def get_all_sent_promo_messages(self) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    async def mark_promo_deleted(self, user_id: int) -> None:
        pass


# =============================================================================
# SQLITE IMPLEMENTATION (для разработки)
# =============================================================================

class SQLiteDatabase(DatabaseInterface):
    """
    SQLite реализация.
    
    ⚠️ ТОЛЬКО для локальной разработки!
    Не подходит для production с множеством инстансов.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection = None
    
    async def init(self) -> None:
        import aiosqlite
        
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        
        await self._create_tables()
        logger.info(f"SQLite initialized: {self.db_path}")
    
    async def _create_tables(self) -> None:
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                specialization TEXT,
                weapon TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                phone TEXT,
                email TEXT,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS promo_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                chat_id INTEGER,
                message_id INTEGER,
                status TEXT DEFAULT 'sent',
                payment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self._connection.commit()
        
        # Инициализируем promo_remaining_slots
        from config import settings
        cursor = await self._connection.execute(
            "SELECT value FROM settings WHERE key = 'promo_remaining_slots'"
        )
        row = await cursor.fetchone()
        if not row:
            await self._connection.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                ('promo_remaining_slots', str(settings.promo_slots_total))
            )
            await self._connection.commit()
    
    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("SQLite connection closed")
    
    async def save_user(self, user_id: int, username: str, first_name: str,
                       specialization: str, weapon: str) -> None:
        await self._connection.execute("""
            INSERT OR REPLACE INTO users (user_id, username, first_name, specialization, weapon)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, first_name, specialization, weapon))
        await self._connection.commit()
    
    async def save_contacts(self, user_id: int, phone: str, email: str, name: str) -> None:
        await self._connection.execute("""
            INSERT OR REPLACE INTO contacts (user_id, phone, email, name)
            VALUES (?, ?, ?, ?)
        """, (user_id, phone, email, name))
        await self._connection.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        cursor = await self._connection.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def user_exists(self, user_id: int) -> bool:
        cursor = await self._connection.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        )
        return await cursor.fetchone() is not None
    
    async def get_promo_slots(self) -> int:
        cursor = await self._connection.execute(
            "SELECT value FROM settings WHERE key = 'promo_remaining_slots'"
        )
        row = await cursor.fetchone()
        return int(row['value']) if row else 0
    
    async def decrement_promo_slots(self) -> int:
        await self._connection.execute("""
            UPDATE settings 
            SET value = CAST(CAST(value AS INTEGER) - 1 AS TEXT),
                updated_at = CURRENT_TIMESTAMP
            WHERE key = 'promo_remaining_slots' AND CAST(value AS INTEGER) > 0
        """)
        await self._connection.commit()
        return await self.get_promo_slots()
    
    async def save_promo_message(self, user_id: int, chat_id: int,
                                 message_id: int, status: str = 'sent') -> None:
        await self._connection.execute("""
            INSERT OR REPLACE INTO promo_messages (user_id, chat_id, message_id, status)
            VALUES (?, ?, ?, ?)
        """, (user_id, chat_id, message_id, status))
        await self._connection.commit()
    
    async def get_user_promo_status(self, user_id: int) -> Optional[str]:
        cursor = await self._connection.execute(
            "SELECT status FROM promo_messages WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row['status'] if row else None
    
    async def update_promo_status(self, user_id: int, status: str,
                                  payment_id: Optional[str] = None) -> None:
        if payment_id:
            await self._connection.execute("""
                UPDATE promo_messages 
                SET status = ?, payment_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (status, payment_id, user_id))
        else:
            await self._connection.execute("""
                UPDATE promo_messages 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (status, user_id))
        await self._connection.commit()
    
    async def get_all_sent_promo_messages(self) -> List[Dict[str, Any]]:
        cursor = await self._connection.execute(
            "SELECT user_id, chat_id, message_id FROM promo_messages WHERE status = 'sent'"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def mark_promo_deleted(self, user_id: int) -> None:
        await self.update_promo_status(user_id, 'deleted')


# =============================================================================
# POSTGRESQL IMPLEMENTATION (для production)
# =============================================================================

class PostgreSQLDatabase(DatabaseInterface):
    """
    PostgreSQL реализация с connection pooling.
    
    ✅ Для production с 100K+ пользователей!
    """
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool = None
    
    async def init(self) -> None:
        import asyncpg
        
        self._pool = await asyncpg.create_pool(
            self.dsn,
            min_size=5,
            max_size=20,
            command_timeout=60,
            statement_cache_size=100,
        )
        
        await self._create_tables()
        logger.info(f"PostgreSQL pool initialized (5-20 connections)")
    
    async def _create_tables(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    specialization TEXT,
                    weapon TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS contacts (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE,
                    phone TEXT,
                    email TEXT,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS promo_messages (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE,
                    chat_id BIGINT,
                    message_id BIGINT,
                    status TEXT DEFAULT 'sent',
                    payment_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_promo_status ON promo_messages(status);
                CREATE INDEX IF NOT EXISTS idx_contacts_user ON contacts(user_id);
            """)
            
            from config import settings
            await conn.execute("""
                INSERT INTO settings (key, value) 
                VALUES ('promo_remaining_slots', $1)
                ON CONFLICT (key) DO NOTHING
            """, str(settings.promo_slots_total))
    
    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL pool closed")
    
    async def save_user(self, user_id: int, username: str, first_name: str,
                       specialization: str, weapon: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, first_name, specialization, weapon)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    specialization = EXCLUDED.specialization,
                    weapon = EXCLUDED.weapon
            """, user_id, username, first_name, specialization, weapon)
    
    async def save_contacts(self, user_id: int, phone: str, email: str, name: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO contacts (user_id, phone, email, name)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE SET
                    phone = EXCLUDED.phone,
                    email = EXCLUDED.email,
                    name = EXCLUDED.name
            """, user_id, phone, email, name)
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )
            return dict(row) if row else None
    
    async def user_exists(self, user_id: int) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM users WHERE user_id = $1)", user_id
            )
            return result
    
    async def get_promo_slots(self) -> int:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval(
                "SELECT value FROM settings WHERE key = 'promo_remaining_slots'"
            )
            return int(value) if value else 0
    
    async def decrement_promo_slots(self) -> int:
        """Атомарное уменьшение с UPDATE ... RETURNING."""
        async with self._pool.acquire() as conn:
            result = await conn.fetchval("""
                UPDATE settings 
                SET value = (CAST(value AS INTEGER) - 1)::TEXT,
                    updated_at = NOW()
                WHERE key = 'promo_remaining_slots' 
                  AND CAST(value AS INTEGER) > 0
                RETURNING value
            """)
            return int(result) if result else 0
    
    async def save_promo_message(self, user_id: int, chat_id: int,
                                 message_id: int, status: str = 'sent') -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO promo_messages (user_id, chat_id, message_id, status)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE SET
                    chat_id = EXCLUDED.chat_id,
                    message_id = EXCLUDED.message_id,
                    status = EXCLUDED.status,
                    updated_at = NOW()
            """, user_id, chat_id, message_id, status)
    
    async def get_user_promo_status(self, user_id: int) -> Optional[str]:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT status FROM promo_messages WHERE user_id = $1", user_id
            )
    
    async def update_promo_status(self, user_id: int, status: str,
                                  payment_id: Optional[str] = None) -> None:
        async with self._pool.acquire() as conn:
            if payment_id:
                await conn.execute("""
                    UPDATE promo_messages 
                    SET status = $2, payment_id = $3, updated_at = NOW()
                    WHERE user_id = $1
                """, user_id, status, payment_id)
            else:
                await conn.execute("""
                    UPDATE promo_messages 
                    SET status = $2, updated_at = NOW()
                    WHERE user_id = $1
                """, user_id, status)
    
    async def get_all_sent_promo_messages(self) -> List[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id, chat_id, message_id FROM promo_messages WHERE status = 'sent'"
            )
            return [dict(row) for row in rows]
    
    async def mark_promo_deleted(self, user_id: int) -> None:
        await self.update_promo_status(user_id, 'deleted')


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def Database(dsn_or_path: str) -> DatabaseInterface:
    """
    Фабрика для создания нужного типа базы данных.
    
    - postgres:// или postgresql:// → PostgreSQL
    - Иначе → SQLite
    """
    if dsn_or_path.startswith(('postgres://', 'postgresql://')):
        logger.info("Using PostgreSQL database")
        return PostgreSQLDatabase(dsn_or_path)
    else:
        logger.warning("Using SQLite database (NOT for production!)")
        return SQLiteDatabase(dsn_or_path)
