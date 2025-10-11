-- Create the houses table
CREATE TABLE houses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    color VARCHAR(7) NOT NULL
);

-- Create the students table
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    roll_no VARCHAR(255) UNIQUE,
    house_id INTEGER REFERENCES houses(id),
    email VARCHAR(255)
);

-- Create the sports table
CREATE TABLE sports (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    date_range DATERANGE
);

-- Create the games table
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(id),
    title VARCHAR(255) NOT NULL,
    start_time TIMESTAMPTZ,
    venue VARCHAR(255),
    is_team_event BOOLEAN DEFAULT FALSE
);

-- Create the participants table
CREATE TABLE participants (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id),
    student_id INTEGER REFERENCES students(id)
);

-- Create the scoring_rules table
CREATE TABLE scoring_rules (
    id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_json JSONB,
    active_flag BOOLEAN DEFAULT TRUE
);

-- Create the scores table
CREATE TABLE scores (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id),
    student_id INTEGER REFERENCES students(id),
    house_id INTEGER REFERENCES houses(id),
    points INTEGER NOT NULL,
    type VARCHAR(50) CHECK (type IN ('individual', 'group')),
    recorded_by UUID REFERENCES auth.users(id),
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create the audit_log table
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    action_type VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    record_id INTEGER,
    old_value JSONB,
    new_value JSONB,
    performed_by UUID REFERENCES auth.users(id),
    performed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create admins table to store admin user IDs
CREATE TABLE admins (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id)
);

-- Create teachers table to store teacher user IDs
CREATE TABLE teachers (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id)
);

-- Add indexes
CREATE INDEX ON scores (game_id);
CREATE INDEX ON scores (house_id);
CREATE INDEX ON students (roll_no);
