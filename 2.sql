USE ola_ride_insights;

SELECT
    COUNT(*) AS total_bookings,
    COUNT(DISTINCT Booking_ID) AS unique_bookings,
    MIN(Booking_DT) AS first_booking,
    MAX(Booking_DT) AS last_booking
FROM ola_rides;

USE ola_ride_insights;

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT Booking_ID) AS unique_bookings
FROM ola_rides;

SELECT *
FROM ola_rides
LIMIT 10;
