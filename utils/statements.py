"""
Загрузка утверждений (statements) для квеста.

Утверждения хранятся в текстовых файлах по специализациям (weapons).
Формат файла: LEVEL|TYPE|STATEMENT|WISDOM_PROMPT

Пример:
1|false|Email-маркетинг мёртв|Проверь статистику Mailchimp
"""

import logging
import random
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Путь к папке с утверждениями
STATEMENTS_DIR = Path(__file__).parent.parent / "statements"


@dataclass
class Statement:
    """Структура утверждения."""
    text: str
    is_truth: bool
    wisdom_prompt: str
    level: int


def load_statements(weapon: str) -> dict[int, list[Statement]]:
    """
    Загружает утверждения из файла для конкретного оружия (специализации).
    
    Args:
        weapon: Название оружия/специализации (marketing, analytics, etc.)
    
    Returns:
        Словарь {level: [Statement, ...]}
    
    Формат файла:
        LEVEL|TYPE|STATEMENT|WISDOM_PROMPT
        1|false|Email-маркетинг мёртв|Проверь статистику Mailchimp
    """
    filepath = STATEMENTS_DIR / f"{weapon}.txt"
    
    if not filepath.exists():
        logger.warning(f"Statements file not found: {filepath}, using fallback")
        filepath = STATEMENTS_DIR / "other.txt"
    
    if not filepath.exists():
        logger.error(f"Fallback statements file not found: {filepath}")
        return {1: [], 2: [], 3: []}
    
    statements: dict[int, list[Statement]] = {1: [], 2: [], 3: []}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split('|')
                if len(parts) < 4:
                    logger.warning(f"Invalid line {line_num} in {filepath}: {line[:50]}")
                    continue
                
                try:
                    level = int(parts[0])
                    is_truth = parts[1].lower() == 'true'
                    statement_text = parts[2]
                    wisdom_prompt = parts[3]
                    
                    if level in [1, 2, 3]:
                        statements[level].append(Statement(
                            text=statement_text,
                            is_truth=is_truth,
                            wisdom_prompt=wisdom_prompt,
                            level=level
                        ))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing line {line_num} in {filepath}: {e}")
                    continue
        
        total = sum(len(v) for v in statements.values())
        logger.info(f"Loaded {total} statements from {filepath.name}")
        
    except Exception as e:
        logger.error(f"Error loading statements from {filepath}: {e}")
    
    return statements


def get_statement_for_round(weapon: str, round_num: int) -> Optional[Statement]:
    """
    Возвращает случайное утверждение для раунда.
    
    Args:
        weapon: Название оружия/специализации
        round_num: Номер раунда (1-3)
    
    Returns:
        Statement или None если не найдено
    """
    statements = load_statements(weapon)
    pool = statements.get(round_num, [])
    
    if not pool:
        logger.warning(f"No statements for weapon={weapon}, round={round_num}")
        # Возвращаем fallback
        return Statement(
            text="Нейросети могут заменить 100% профессий к 2030 году.",
            is_truth=False,
            wisdom_prompt="Проверь прогнозы экспертов о влиянии ИИ на рынок труда в Perplexity",
            level=round_num
        )
    
    return random.choice(pool)


def get_statement_text_formatted(statement: Statement, round_num: int, total_rounds: int = 3) -> str:
    """
    Форматирует текст утверждения для отображения.
    
    Args:
        statement: Объект Statement
        round_num: Номер текущего раунда
        total_rounds: Всего раундов
    
    Returns:
        Отформатированный текст
    """
    return (
        f"🎯 <b>Раунд {round_num}/{total_rounds}</b>\n\n"
        f"<i>«{statement.text}»</i>\n\n"
        "Это правда или ложь?"
    )


def get_wisdom_text(statement: Statement, user_was_correct: bool) -> str:
    """
    Возвращает текст мудрости после ответа на утверждение.
    
    Args:
        statement: Объект Statement
        user_was_correct: Пользователь ответил правильно
    
    Returns:
        Текст с результатом и подсказкой для проверки
    """
    if user_was_correct:
        result_emoji = "✅"
        result_text = "Правильно!"
    else:
        result_emoji = "❌"
        result_text = "Неверно!"
    
    truth_label = "✓ ПРАВДА" if statement.is_truth else "✗ ЛОЖЬ"
    
    return (
        f"{result_emoji} <b>{result_text}</b>\n\n"
        f"Утверждение: <b>{truth_label}</b>\n\n"
        f"💡 <b>Проверь сам:</b>\n"
        f"<i>{statement.wisdom_prompt}</i>\n\n"
        "Используй Perplexity для проверки фактов!"
    )


# =============================================================================
# РЕЗУЛЬТАТЫ КВЕСТА
# =============================================================================

# Специализации и их описания
SPECIALIZATIONS = {
    "marketing": {
        "name": "📊 Маркетолог",
        "emoji": "📊",
        "description": "Вы прирождённый маркетолог! ИИ-инструменты помогут вам создавать вирусный контент, анализировать аудиторию и автоматизировать рутину.",
        "tools": ["ChatGPT для контент-плана", "Midjourney для визуалов", "Perplexity для анализа конкурентов"]
    },
    "analytics": {
        "name": "📈 Аналитик",
        "emoji": "📈",
        "description": "Данные — ваша стихия! С ИИ вы сможете обрабатывать массивы данных, строить прогнозы и находить инсайты, которые другие пропускают.",
        "tools": ["Claude для анализа документов", "ChatGPT Code Interpreter", "NotebookLM для исследований"]
    },
    "copywriting": {
        "name": "✍️ Копирайтер",
        "emoji": "✍️",
        "description": "Слова — ваша сила! ИИ станет вашим соавтором, помогая создавать тексты, которые цепляют и продают.",
        "tools": ["ChatGPT для генерации текстов", "Claude для редактуры", "Perplexity для фактчекинга"]
    },
    "design": {
        "name": "🎨 Дизайнер",
        "emoji": "🎨",
        "description": "Визуал — ваш язык! ИИ-инструменты генерации изображений откроют новые горизонты творчества.",
        "tools": ["Midjourney", "DALL-E 3", "Stable Diffusion", "Canva AI"]
    },
    "management": {
        "name": "📋 Менеджер",
        "emoji": "📋",
        "description": "Организация — ваш конёк! ИИ поможет управлять проектами, автоматизировать процессы и координировать команду.",
        "tools": ["ChatGPT для планирования", "Notion AI", "Автоматизация через n8n"]
    },
    "video": {
        "name": "🎬 Видеомейкер",
        "emoji": "🎬",
        "description": "Видео — ваша страсть! ИИ-инструменты для генерации и монтажа видео ускорят ваш workflow в разы.",
        "tools": ["Veo3 от Google", "Runway ML", "HeyGen для аватаров", "Descript"]
    },
    "universal": {
        "name": "💼 Универсал",
        "emoji": "💼",
        "description": "Вы многогранная личность! ИИ поможет вам стать профессионалом сразу в нескольких областях.",
        "tools": ["Полный стек ИИ-инструментов", "Интеграции между сервисами", "Кастомные решения"]
    }
}


def get_specialization_info(spec_key: str) -> dict:
    """
    Получает информацию о специализации.
    
    Args:
        spec_key: Ключ специализации (marketing, analytics, etc.)
    
    Returns:
        Словарь с информацией о специализации
    """
    return SPECIALIZATIONS.get(spec_key, SPECIALIZATIONS["universal"])


def format_result_text(spec_key: str, score: int) -> str:
    """
    Форматирует текст результата квеста.
    
    Args:
        spec_key: Ключ специализации
        score: Набранные очки
    
    Returns:
        Отформатированный текст
    """
    spec = get_specialization_info(spec_key)
    tools_list = "\n".join(f"• {tool}" for tool in spec["tools"])
    
    return (
        f"🏆 <b>Ваш результат: {spec['name']}</b>\n\n"
        f"⭐ Очки: {score}\n\n"
        f"{spec['description']}\n\n"
        f"<b>Рекомендуемые инструменты:</b>\n{tools_list}"
    )
