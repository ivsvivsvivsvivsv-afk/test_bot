"""
Модуль работы с базой данных SQLite
===================================
Асинхронные операции с aiosqlite.
Класс-based подход для dependency injection.
"""

import logging
import aiosqlite
from typing import Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """
    Асинхронный класс для работы с SQLite.
    Используется через dependency injection в handlers.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        logger.info(f"Database initialized with path: {db_path}")
    
    async def init(self) -> bool:
        """Инициализация базы данных и создание таблиц."""
        try:
            # Создаём директорию если нужно
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        source TEXT,
                        
                        -- Состояние квеста
                        current_step TEXT DEFAULT 'start',
                        quest_completed INTEGER DEFAULT 0,
                        
                        -- Выборы игрока
                        hero_class TEXT,
                        weapon TEXT,
                        
                        -- Результаты
                        score INTEGER DEFAULT 0,
                        current_round INTEGER DEFAULT 0,
                        
                        -- Контакты
                        phone TEXT,
                        email TEXT,
                        
                        -- Арена
                        arena_spec TEXT,
                        arena_completed INTEGER DEFAULT 0,
                        
                        -- Метаданные
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.commit()
            
            logger.info("✅ Database tables initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database init error: {e}")
            return False
    
    async def close(self):
        """Закрытие соединения."""
        if self._connection:
            await self._connection.close()
            logger.info("Database connection closed")
    
    # =========================================================================
    # ПОЛЬЗОВАТЕЛИ
    # =========================================================================
    
    async def add_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        source: Optional[str] = None
    ) -> bool:
        """Создание нового пользователя."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR IGNORE INTO users 
                    (user_id, username, first_name, last_name, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, source))
                await db.commit()
            
            logger.debug(f"User added: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")
            return False
    
    async def get_user(self, user_id: int) -> Optional[dict]:
        """Получение данных пользователя."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    async def update_user(self, user_id: int, **kwargs) -> bool:
        """
        Обновление данных пользователя.
        
        Пример:
            await db.update_user(123, current_step="round_1", score=1)
        """
        if not kwargs:
            return True
            
        try:
            fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
            values = list(kwargs.values())
            values.append(user_id)
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    f"UPDATE users SET {fields}, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
                    values
                )
                await db.commit()
            
            logger.debug(f"User {user_id} updated: {list(kwargs.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return False
    
    async def update_user_activity(self, user_id: int) -> bool:
        """Обновление last_activity."""
        return await self.update_user(user_id)  # Просто триггерит last_activity
    
    async def update_user_step(self, user_id: int, step: str) -> bool:
        """Обновление текущего шага."""
        return await self.update_user(user_id, current_step=step)
    
    async def update_user_class(self, user_id: int, hero_class: str) -> bool:
        """Обновление класса героя."""
        return await self.update_user(user_id, hero_class=hero_class)
    
    async def update_user_weapon(self, user_id: int, weapon: str) -> bool:
        """Обновление оружия."""
        return await self.update_user(user_id, weapon=weapon)
    
    async def update_user_round(self, user_id: int, round_num: int) -> bool:
        """Обновление текущего раунда."""
        return await self.update_user(user_id, current_round=round_num)
    
    async def update_user_score(self, user_id: int, score: int) -> bool:
        """Обновление очков."""
        return await self.update_user(user_id, score=score)
    
    async def update_user_contacts(
        self,
        user_id: int,
        phone: Optional[str] = None,
        email: Optional[str] = None
    ) -> bool:
        """Обновление контактов."""
        kwargs = {}
        if phone is not None:
            kwargs["phone"] = phone
        if email is not None:
            kwargs["email"] = email
        
        if kwargs:
            return await self.update_user(user_id, **kwargs)
        return True
    
    async def update_user_arena_spec(self, user_id: int, spec: str) -> bool:
        """Обновление специализации арены."""
        return await self.update_user(user_id, arena_spec=spec)
    
    async def complete_quest(self, user_id: int, score: int) -> bool:
        """Отметка о завершении квеста."""
        return await self.update_user(user_id, quest_completed=1, score=score)
    
    async def reset_user_progress(self, user_id: int) -> bool:
        """Сброс прогресса пользователя."""
        return await self.update_user(
            user_id,
            current_step="start",
            quest_completed=0,
            hero_class=None,
            weapon=None,
            score=0,
            current_round=0,
            arena_spec=None,
            arena_completed=0
        )
    
    # =========================================================================
    # СТАТИСТИКА
    # =========================================================================
    
    async def get_user_count(self) -> int:
        """Количество пользователей."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                row = await cursor.fetchone()
                return row[0] if row else 0
                
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            return 0
    
    async def get_stats(self) -> dict:
        """Полная статистика."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}
                
                # Всего пользователей
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                row = await cursor.fetchone()
                stats["total_users"] = row[0] if row else 0
                
                # Завершили квест
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM users WHERE quest_completed = 1"
                )
                row = await cursor.fetchone()
                stats["completed_quest"] = row[0] if row else 0
                
                # С контактами
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM users WHERE phone IS NOT NULL OR email IS NOT NULL"
                )
                row = await cursor.fetchone()
                stats["with_contacts"] = row[0] if row else 0
                
                # Арена
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM users WHERE arena_spec IS NOT NULL"
                )
                row = await cursor.fetchone()
                stats["arena_started"] = row[0] if row else 0
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    async def get_all_contacts(self) -> list[dict]:
        """Получение всех контактов для экспорта."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT user_id, username, first_name, last_name, 
                           phone, email, score, created_at
                    FROM users 
                    WHERE phone IS NOT NULL OR email IS NOT NULL
                    ORDER BY created_at DESC
                """)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting contacts: {e}")
            return []
