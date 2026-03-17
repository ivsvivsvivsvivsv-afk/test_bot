-- Patch 4: vk_active_scenario for VK revolver
-- Run: psql -U hydra -d hydra_bot -f migrations/patch4_001_vk_active_scenario.sql

INSERT INTO config (key, value) VALUES ('vk_active_scenario', 'vk_main_quest')
ON CONFLICT (key) DO NOTHING;
