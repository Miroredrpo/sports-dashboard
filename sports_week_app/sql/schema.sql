-- Create the houses table
CREATE TABLE houses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
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
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT
);

-- Create the events (formerly games) table
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    start_time TIMESTAMPTZ,
    venue VARCHAR(255),
    scoring_model VARCHAR(50) NOT NULL CHECK (scoring_model IN ('points', 'victory'))
);

-- Create the competitions table for head-to-head matchups
CREATE TABLE competitions (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('group', 'individual')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create a linking table for houses in a group competition
CREATE TABLE competition_houses (
    competition_id INTEGER REFERENCES competitions(id) ON DELETE CASCADE,
    house_id INTEGER REFERENCES houses(id) ON DELETE CASCADE,
    PRIMARY KEY (competition_id, house_id)
);

-- Create a linking table for students in an individual competition
CREATE TABLE competition_students (
    competition_id INTEGER REFERENCES competitions(id) ON DELETE CASCADE,
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    PRIMARY KEY (competition_id, student_id)
);

-- Create the competition_rounds table
CREATE TABLE competition_rounds (
    id SERIAL PRIMARY KEY,
    competition_id INTEGER REFERENCES competitions(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    details TEXT, -- For scores like in cricket
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create the scores table (now simplified and linked to rounds)
CREATE TABLE scores (
    id SERIAL PRIMARY KEY,
    round_id INTEGER REFERENCES competition_rounds(id) ON DELETE CASCADE,
    house_id INTEGER REFERENCES houses(id),
    points INTEGER NOT NULL,
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

-- Role tables
CREATE TABLE admins (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id)
);

CREATE TABLE teachers (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id)
);

-- Indexes
CREATE INDEX ON students (roll_no);
CREATE INDEX ON scores (round_id);
CREATE INDEX ON scores (house_id);
