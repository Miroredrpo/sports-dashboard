CREATE OR REPLACE FUNCTION get_competition_between_houses(house1_id_param int, house2_id_param int, sport_id_param int)
RETURNS TABLE(id int) AS $$
BEGIN
    RETURN QUERY
    SELECT c.id
    FROM competitions c
    JOIN events e ON c.event_id = e.id
    WHERE e.sport_id = sport_id_param
    AND (
        SELECT COUNT(*)
        FROM competition_houses ch
        WHERE ch.competition_id = c.id
        AND (ch.house_id = house1_id_param OR ch.house_id = house2_id_param)
    ) = 2;
END;
$$ LANGUAGE plpgsql;
