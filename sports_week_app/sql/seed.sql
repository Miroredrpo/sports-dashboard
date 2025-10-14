-- Seed the houses table with the four initial houses
-- Seed the houses table with the four initial houses for each school level
-- This script is idempotent, it will not insert duplicates
INSERT INTO houses (name, color, school_level) VALUES
    ('Karnali', '#98FB98', 'high_school'),
    ('Koshi', '#87CEFA', 'high_school'),
    ('Mahakali', '#9B59B6', 'high_school'),
    ('Mechi', '#FFA500', 'high_school'),
    ('Karnali', '#98FB98', 'middle_school'),
    ('Koshi', '#87CEFA', 'middle_school'),
    ('Mahakali', '#9B59B6', 'middle_school'),
    ('Mechi', '#FFA500', 'middle_school'),
    ('Karnali', '#98FB98', 'elementary'),
    ('Koshi', '#87CEFA', 'elementary'),
    ('Mahakali', '#9B59B6', 'elementary'),
    ('Mechi', '#FFA500', 'elementary')
ON CONFLICT (name, school_level) DO NOTHING;
