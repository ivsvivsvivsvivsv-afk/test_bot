"""
Telegram file_id для всех изображений воронки.

Все картинки хранятся в Telegram-серверах и вызываются ТОЛЬКО по file_id.
Файлы на диске сервера НЕ используются — это исключает content/media и FSInputFile.

ВАЖНО: file_id привязан к конкретному боту. В sandbox берём SANDBOX_MEDIA_FILE_IDS.
Обновить: python scripts/copy_media_prod_to_sandbox.py --fetch-from-server
"""

from __future__ import annotations

import os

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


# Sandbox: file_id от prod не работает. Получены через copy_media_prod_to_sandbox.py (re-upload через @Neurounit_Sandbox_bot).
SANDBOX_MEDIA_FILE_IDS: dict[str, str] = {
    "img_analit": "AgACAgIAAxkDAAMZabEpRQSSwEk7K_h2H-C9TIfd0UsAAkYVaxttUolJxvQfQGE2kyIBAAMCAAN5AAM6BA",
    "img_copy": "AgACAgIAAxkDAAMaabEpRYm192qIG-p74KlEc7rAJj4AAkcVaxttUolJ3pjlX8X-S_gBAAMCAAN5AAM6BA",
    "img_design": "AgACAgIAAxkDAAMbabEpRjCSUJ5t_VWG8a1QXZM9XPAAAkgVaxttUolJm3Htphit_CEBAAMCAAN5AAM6BA",
    "img_final": "AgACAgIAAxkDAAMlabEpTrU2tO3TtprEOzpYNM_NPOcAAlMVaxttUolJVrsf2wem9uwBAAMCAAN5AAM6BA",
    "img_free_boss": "AgACAgIAAxkDAAMXabEpQ6dHCU66hfG0Sl8ptfTwqk0AAkQVaxttUolJLp_3qO-t2uYBAAMCAAN5AAM6BA",
    "img_gidratt": "AgACAgIAAxkDAAMhabEpS1XNJHsGmmNYTFrvlwrt3QIAAk4VaxttUolJwhOdZBGHT2gBAAMCAAN5AAM6BA",
    "img_kill": "AgACAgIAAxkDAAMgabEpSmneK5PXnB3EScezw5LcI7AAAk0VaxttUolJHW_rGGiJ_nsBAAMCAAN5AAM6BA",
    "img_lose": "AgACAgIAAxkDAAMjabEpTE9UGsyDhxwcoJcPmp3vZfUAAlAVaxttUolJlojPzxPJsX8BAAMCAAN5AAM6BA",
    "img_managment": "AgACAgIAAxkDAAMcabEpRz4EoIm-ac5zw6ZVYv6R-vUAAkkVaxttUolJs0y1JX-wuOcBAAMCAAN5AAM6BA",
    "img_marketing": "AgACAgIAAxkDAAMdabEpSLRcKSsYYVXep-pO-NnADeEAAkoVaxttUolJAllcCoy513cBAAMCAAN5AAM6BA",
    "img_other": "AgACAgIAAxkDAAMfabEpSYnphxkM0ZvOW__ZEvBztggAAkwVaxttUolJ6UptfxLD68IBAAMCAAN5AAM6BA",
    "img_prepare": "AgACAgIAAxkDAAMWabEpQ2fDwcoJ5lbF0MhpAhXp_ZkAAkMVaxttUolJ9SGH1kbuHvYBAAMCAAN5AAM6BA",
    "img_proff": "AgACAgIAAxkDAAMYabEpRJ8ft3nPzVgr2584qU6t578AAkUVaxttUolJWhg2LGfH2lwBAAMCAAN5AAM6BA",
    "img_stark": "AgACAgIAAxkDAAMkabEpTefCa8tK_yaVUKeIXa9MDdgAAlIVaxttUolJpXb9Z1bWs5cBAAMCAAN5AAM6BA",
    "img_start": "AgACAgIAAxkDAAMVabEpQu85wxBRSMeSlMTrjH5QZBUAAkIVaxttUolJJbzCNsF2rVIBAAMCAAN5AAM6BA",
    "img_video": "AgACAgIAAxkDAAMeabEpSX6mHjSTv1uIavDB-qEM4KcAAksVaxttUolJ7MiGsU-zjykBAAMCAAN5AAM6BA",
    "img_win": "AgACAgIAAxkDAAMiabEpTBzi949xNije0r8z2AABGViNAAJPFWsbbVKJSekgC73hiivCAQADAgADeQADOgQ",
}


def get_file_id(key: str) -> str | None:
    """Возвращает file_id по ключу или None, если ключа нет. В sandbox — None (file_id от prod не работает)."""
    if os.getenv("APP_ENV", "").strip().lower() == "sandbox":
        return SANDBOX_MEDIA_FILE_IDS.get(key) if SANDBOX_MEDIA_FILE_IDS else None
    return MEDIA_FILE_IDS.get(key)


def get_weapon_image(weapon_id: str) -> str | None:
    """Возвращает file_id картинки для выбранного оружия."""
    img_key = WEAPON_TO_IMAGE.get(weapon_id, "img_other")
    return get_file_id(img_key)


# Миниквесты 1–5: file_id пока нет (картинки не сгенерированы).
# Когда будут — добавить: MINIQUEST_FILE_IDS = {1: "...", 2: "...", ...}
MINIQUEST_FILE_IDS: dict[int, str] = {}


def get_miniquest_file_id(day: int) -> str | None:
    """Возвращает file_id картинки миниквеста для дня day (1–5) или None."""
    return MINIQUEST_FILE_IDS.get(day)
