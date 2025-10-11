-- Seed the houses table with the four initial houses
-- This script is idempotent, it will not insert duplicates
INSERT INTO houses (name, color) VALUES
    ('Karnali', '#98FB98'),
    ('Koshi', '#87CEFA'),
    ('Mahakali', '#9B59B6'),
    ('Mechi', '#FFA500')
ON CONFLICT (name) DO NOTHING;
