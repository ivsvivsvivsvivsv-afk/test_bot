"""
Telegram file_id для всех изображений воронки.

Все картинки хранятся в Telegram-серверах и вызываются ТОЛЬКО по file_id.
Файлы на диске сервера НЕ используются — это исключает content/media и FSInputFile.
"""

from __future__ import annotations

# Все file_id получены однажды через send_photo и сохранены — Telegram их хранит.
MEDIA_FILE_IDS: dict[str, str] = {
    # Старт воронки
    "img_start": "AgACAgIAAxkBAAIG_2mTXxk3cZ9Lst7juDhy2sH-bVsVAALsFGsbDbugSEpmjVsIbKqyAQADAgADeQADOgQ",
    # Подготовка к битве (шаг 2)
    "img_prepare": "AgACAgIAAxkDAAIIoWmq-iNVzfdt19fjd900Flhe1x8GAAIbFmsbqu9YSXczRSmUVU1SAQADAgADeQADOgQ",
    # Выбор босс/фрилансер (класс)
    "img_free_boss": "AgACAgIAAxkBAAIHAmmTX0D9v2RiDGmr8rd5Fdkxg59yAALuFGsbDbugSJ2Khynw3Pr1AQADAgADeQADOgQ",
    # Выбор профессии (оружие)
    "img_proff": "AgACAgIAAxkBAAIHBWmTX57E-eM5i9jt6YPBbQrhCsu-AAL5FGsbDbugSIRQXpvckkp6AQADAgADeQADOgQ",
    # По профессиям
    "img_analit": "AgACAgIAAxkBAAIG_GmTRpUfIS2_vBBiEgmTbVbEcqy_AAKuE2sbDbugSAtg0yncoXKvAQADAgADeQADOgQ",
    "img_copy": "AgACAgIAAxkBAAIHCGmTX-JMYyDQbKnZhcaKZJDijDQkAAIEFWsbDbugSNTtaW5Zq-DHAQADAgADeQADOgQ",
    "img_design": "AgACAgIAAxkBAAIHCmmTX_VDx_e4nHnGzhFDbRhXEtsiAAIFFWsbDbugSHhwqWVHzg8pAQADAgADeQADOgQ",
    "img_managment": "AgACAgIAAxkBAAIHD2mTYH-l0U2-kPgmtLynz6D_9ENoAAIOFWsbDbugSImJmFdHgLM0AQADAgADeQADOgQ",
    "img_marketing": "AgACAgIAAxkBAAIHEmmTYKQt_gfOnwXvGCS95zHwfGmiAAIUFWsbDbugSHRY3qB5YIvGAQADAgADeQADOgQ",
    "img_video": "AgACAgIAAxkBAAIHFWmTYNFQ5wTX5gga_kGLTYqhyqoTAAIVFWsbDbugSJNA6wAB0pv6hQEAAwIAA3kAAzoE",
    "img_other": "AgACAgIAAxkBAAIHJGmTYjp2suO-P5tngaeoUfw6j2mNAAIkFWsbDbugSLm1JL7SubAJAQADAgADeQADOgQ",
    # Результат ответа в раунде
    "img_kill": "AgACAgIAAxkBAAIHGGmTYRjhg1VPNkBxYN5dE8l0LBTjAAIYFWsbDbugSFbmWagOPVjdAQADAgADeQADOgQ",  # верный ответ
    "img_gidratt": "AgACAgIAAxkBAAIG-WmTQg9VKc47CBi7rwyz1g7rlmvzAAKRE2sbDbugSIb3wlOPDq95AQADAgADeQADOgQ",  # неверный ответ
    # Итог квеста
    "img_win": "AgACAgIAAxkDAAIIommq-iPKzrXdDyQC-PCjPKu7FIzqAAIcFmsbqu9YSdh-3sam4pTvAQADAgADeQADOgQ",  # победил гидру (новая)
    "img_lose": "AgACAgIAAxkBAAIHHGmTYa1pWKvmL-3aXmA4J039lOu7AAIeFWsbDbugSH1JzvYSFXiVAQADAgADeQADOgQ",  # проиграл гидре
    # Мораль и финал
    "img_stark": "AgACAgIAAxkBAAIHHmmTYd9iQQHNA1SJvXpuT1GG42HEAAIfFWsbDbugSLYaVhyFpZU-AQADAgADeQADOgQ",  # тони старк
    "img_final": "AgACAgIAAxkBAAIHIGmTYf2-91QgSxRSoODg4wc8jPbbAAIgFWsbDbugSOuMvbGbCzHAAQADAgADeQADOgQ",  # приглашение на курс
}

# Маппинг weapon_id → ключ картинки
WEAPON_TO_IMAGE: dict[str, str] = {
    "marketing": "img_marketing",
    "analytics": "img_analit",
    "copywriting": "img_copy",
    "design": "img_design",
    "management": "img_managment",
    "video": "img_video",
    "other": "img_other",
}


def get_file_id(key: str) -> str | None:
    """Возвращает file_id по ключу или None, если ключа нет."""
    return MEDIA_FILE_IDS.get(key)


def get_weapon_image(weapon_id: str) -> str | None:
    """Возвращает file_id картинки для выбранного оружия."""
    img_key = WEAPON_TO_IMAGE.get(weapon_id, "img_other")
    return MEDIA_FILE_IDS.get(img_key)


# Миниквесты 1–5: file_id пока нет (картинки не сгенерированы).
# Когда будут — добавить: MINIQUEST_FILE_IDS = {1: "...", 2: "...", ...}
MINIQUEST_FILE_IDS: dict[int, str] = {}


def get_miniquest_file_id(day: int) -> str | None:
    """Возвращает file_id картинки миниквеста для дня day (1–5) или None."""
    return MINIQUEST_FILE_IDS.get(day)
