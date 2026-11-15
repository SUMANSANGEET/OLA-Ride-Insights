/* =====================================================================
   OLA RIDE INSIGHTS  |  MySQL 8.0  |  SQL Query Development
   Dataset : ola_rides_clean.csv  (103,024 bookings, Jul-2024)
   Parts   : 0 Setup -> 1 Load & Clean -> 2 Validate -> 3 Index/Optimize
             -> 4 The 10 required SQL questions -> 5 Bonus insight queries
             -> 6 Reconciliation checks
   Tip     : every query tagged  -- >>> ID | title  is read by the
             companion notebook, so this file is the single source of truth.
   ===================================================================== */


/* ---------------------------------------------------------------------
   PART 0 - DATABASE SETUP
   --------------------------------------------------------------------- */
CREATE DATABASE IF NOT EXISTS ola_ride_insights
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE ola_ride_insights;

-- Needed once for LOAD DATA LOCAL (fixes Error 3948 / 2068):
--   (a) server side - run this (needs admin rights):
-- SET GLOBAL local_infile = 1;   -- not needed when using the Import Wizard
--   (b) client side - Workbench: Database > Manage Connections > your
--       connection > Advanced tab > "Others" box, add:  OPT_LOCAL_INFILE=1
--       then reconnect. Use forward slashes in the path below.


/* ---------------------------------------------------------------------
   PART 1 - LOAD  &  CLEAN
   Step 1.1  Land the CSV as-is in a staging table (all text, nothing lost)
   Step 1.2  Build a typed, constrained production table
   Step 1.3  Cleanse while moving data: trim, blank -> NULL, cast, parse
   --------------------------------------------------------------------- */

-- 1.1 Staging table ----------------------------------------------------
CREATE TABLE IF NOT EXISTS ola_rides_raw (
  Booking_ID VARCHAR(30), Booking_Status VARCHAR(30), Customer_ID VARCHAR(30),
  Vehicle_Type VARCHAR(30), Pickup_Location VARCHAR(80), Drop_Location VARCHAR(80),
  V_TAT VARCHAR(20), C_TAT VARCHAR(20),
  Canceled_Rides_by_Customer VARCHAR(80), Canceled_Rides_by_Driver VARCHAR(80),
  Incomplete_Rides VARCHAR(10), Incomplete_Rides_Reason VARCHAR(50),
  Booking_Value VARCHAR(20), Payment_Method VARCHAR(30), Ride_Distance VARCHAR(20),
  Driver_Ratings VARCHAR(10), Customer_Rating VARCHAR(10), Booking_DT VARCHAR(30),
  Hour_ VARCHAR(5), Weekday VARCHAR(15), Is_Weekend VARCHAR(8), Day_Part VARCHAR(30),
  Is_Success VARCHAR(8), Is_Incomplete VARCHAR(8), Cancel_Reason VARCHAR(80),
  Cancel_By VARCHAR(20), Same_Pickup_Drop VARCHAR(8)
) ENGINE=InnoDB;

-- LOAD DATA LOCAL is blocked in this Workbench setup (Error 2068), so load the CSV with:
--   Schemas > ola_ride_insights > Tables > ola_rides_raw > right-click >
--   Table Data Import Wizard > ola_rides_clean.csv > 'Use existing table'.
-- Run this script from the next line ONLY after the wizard has finished.
/*
-- Change the path. (Alternative: MySQL Workbench > Table Data Import Wizard)
SHOW GLOBAL VARIABLES LIKE 'local_infile';   -- must be ON
LOAD DATA LOCAL INFILE 'C:/Users/TECH-GENIUSES/Desktop/LABMENTIX/Data Analytics with AI/Project_15 Ola Ride Insights/OLA Ride Insights/outputs/ola_rides_clean.csv'
INTO TABLE ola_rides_raw
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

*/

SELECT COUNT(*) AS rows_loaded FROM ola_rides_raw;          -- expect 103,024

-- 1.2 Typed production table --------------------------------------------
DROP TABLE IF EXISTS ola_rides;

CREATE TABLE ola_rides (
  Booking_ID                 VARCHAR(30)  NOT NULL,
  Booking_Status             VARCHAR(30)  NOT NULL,
  Customer_ID                VARCHAR(30)  NOT NULL,
  Vehicle_Type               VARCHAR(30)  NOT NULL,
  Pickup_Location            VARCHAR(80)  NOT NULL,
  Drop_Location              VARCHAR(80)  NOT NULL,
  V_TAT                      DECIMAL(8,1) NULL,
  C_TAT                      DECIMAL(8,1) NULL,
  Canceled_Rides_by_Customer VARCHAR(80)  NULL,
  Canceled_Rides_by_Driver   VARCHAR(80)  NULL,
  Incomplete_Rides           ENUM('Yes','No') NULL,
  Incomplete_Rides_Reason    VARCHAR(50)  NULL,
  Booking_Value              INT          NOT NULL,
  Payment_Method             VARCHAR(30)  NULL,
  Ride_Distance              INT          NOT NULL,
  Driver_Ratings             DECIMAL(2,1) NULL,
  Customer_Rating            DECIMAL(2,1) NULL,
  Booking_DT                 DATETIME     NOT NULL,
  Hour_Of_Day                TINYINT      NOT NULL,
  Weekday                    VARCHAR(15)  NOT NULL,
  Is_Weekend                 TINYINT(1)   NOT NULL,
  Day_Part                   VARCHAR(30)  NOT NULL,
  Is_Success                 TINYINT(1)   NOT NULL,
  Is_Incomplete              TINYINT(1)   NULL,
  Cancel_Reason              VARCHAR(80)  NULL,
  Cancel_By                  VARCHAR(20)  NULL,
  Same_Pickup_Drop           TINYINT(1)   NOT NULL,
  PRIMARY KEY (Booking_ID),
  CONSTRAINT chk_rating_d CHECK (Driver_Ratings  IS NULL OR Driver_Ratings  BETWEEN 1 AND 5),
  CONSTRAINT chk_rating_c CHECK (Customer_Rating IS NULL OR Customer_Rating BETWEEN 1 AND 5),
  CONSTRAINT chk_value    CHECK (Booking_Value >= 0)
) ENGINE=InnoDB;

-- 1.3 Cleanse while loading ---------------------------------------------
-- Pattern: TRIM -> treat '', 'null', 'NaN' as NULL -> CAST / parse
-- 1) Diagnose: how many bad rows and what they look like
SELECT COUNT(*) AS total_rows,
       SUM(Customer_ID IS NULL) AS null_cust,
       SUM(Booking_ID IS NULL)  AS null_booking,
       SUM(TRIM(Customer_ID) = '') AS blank_cust
FROM ola_rides_raw;

SELECT * FROM ola_rides_raw WHERE Customer_ID IS NULL LIMIT 10;

-- 2) Fix: same insert, skipping rows with no key fields
INSERT INTO ola_rides
SELECT
  TRIM(Booking_ID),
  TRIM(Booking_Status),
  TRIM(Customer_ID),
  TRIM(Vehicle_Type),
  TRIM(Pickup_Location),
  TRIM(Drop_Location),
  CAST(NULLIF(NULLIF(NULLIF(TRIM(V_TAT),''),'null'),'NaN') AS DECIMAL(8,1)),
  CAST(NULLIF(NULLIF(NULLIF(TRIM(C_TAT),''),'null'),'NaN') AS DECIMAL(8,1)),
  NULLIF(NULLIF(TRIM(Canceled_Rides_by_Customer),''),'null'),
  NULLIF(NULLIF(TRIM(Canceled_Rides_by_Driver),''),'null'),
  NULLIF(NULLIF(TRIM(Incomplete_Rides),''),'null'),
  NULLIF(NULLIF(TRIM(Incomplete_Rides_Reason),''),'null'),
  CAST(ROUND(COALESCE(CAST(NULLIF(TRIM(Booking_Value),'') AS DECIMAL(12,2)),0)) AS UNSIGNED),
  NULLIF(NULLIF(TRIM(Payment_Method),''),'null'),
  CAST(ROUND(COALESCE(CAST(NULLIF(TRIM(Ride_Distance),'') AS DECIMAL(12,2)),0)) AS UNSIGNED),
  CAST(NULLIF(NULLIF(NULLIF(TRIM(Driver_Ratings),''),'null'),'NaN')  AS DECIMAL(2,1)),
  CAST(NULLIF(NULLIF(NULLIF(TRIM(Customer_Rating),''),'null'),'NaN') AS DECIMAL(2,1)),
  STR_TO_DATE(TRIM(Booking_DT), '%Y-%m-%d %H:%i:%s'),
  CAST(ROUND(CAST(TRIM(Hour_) AS DECIMAL(5,1))) AS UNSIGNED),
  TRIM(Weekday),
  UPPER(TRIM(Is_Weekend)) = 'TRUE',
  TRIM(Day_Part),
  UPPER(TRIM(Is_Success)) = 'TRUE',
  CASE UPPER(TRIM(Is_Incomplete)) WHEN 'TRUE' THEN 1 WHEN 'FALSE' THEN 0 END,
  NULLIF(NULLIF(TRIM(Cancel_Reason),''),'null'),
  NULLIF(NULLIF(TRIM(Cancel_By),''),'null'),
  UPPER(TRIM(REPLACE(Same_Pickup_Drop, '\r', ''))) = 'TRUE'
FROM ola_rides_raw
WHERE Booking_ID IS NOT NULL AND TRIM(Booking_ID) <> ''
  AND Customer_ID IS NOT NULL AND TRIM(Customer_ID) <> '';

-- DROP TABLE ola_rides_raw;   -- optional: run only after V1 shows 103024 rows


/* ---------------------------------------------------------------------
   PART 2 - DATA-QUALITY VALIDATION  (run after load; all should be 0
   unless noted)
   --------------------------------------------------------------------- */
-- >>> V1 | Row count and uniqueness (expect 103024 / 103024)
SELECT COUNT(*) AS total_rows, COUNT(DISTINCT Booking_ID) AS unique_bookings
FROM ola_rides;

-- >>> V2 | Null audit - NULLs are EXPECTED only where a ride never happened
SELECT Booking_Status,
       COUNT(*)                                AS bookings,
       SUM(Payment_Method  IS NULL)            AS null_payment,
       SUM(Driver_Ratings  IS NULL)            AS null_driver_rating,
       SUM(Customer_Rating IS NULL)            AS null_customer_rating,
       SUM(Incomplete_Rides IS NULL)           AS null_incomplete_flag
FROM ola_rides
GROUP BY Booking_Status;

-- >>> V3 | Logical consistency (every column should be 0)
SELECT
  SUM(Booking_Status = 'Success' AND Payment_Method IS NULL)               AS success_without_payment,
  SUM(Booking_Status <> 'Success' AND Payment_Method IS NOT NULL)          AS paid_but_not_success,
  SUM(Incomplete_Rides = 'Yes' AND Incomplete_Rides_Reason IS NULL)        AS incomplete_without_reason,
  SUM(Booking_Status = 'Success' AND Ride_Distance = 0)                    AS success_zero_distance
FROM ola_rides;


/* ---------------------------------------------------------------------
   PART 3 - PERFORMANCE: INDEXES  +  EXPLAIN
   Design rule: index the columns that appear in WHERE / GROUP BY / JOIN,
   put equality filters first, and add the aggregated column last so the
   index "covers" the query (no table lookups).
   --------------------------------------------------------------------- */
CREATE INDEX idx_status_vehicle ON ola_rides (Booking_Status, Vehicle_Type, Ride_Distance);
CREATE INDEX idx_vehicle_status ON ola_rides (Vehicle_Type, Booking_Status, Customer_Rating);
CREATE INDEX idx_customer       ON ola_rides (Customer_ID);
CREATE INDEX idx_payment        ON ola_rides (Payment_Method, Booking_Value);
CREATE INDEX idx_booking_dt     ON ola_rides (Booking_DT);
CREATE INDEX idx_incomplete     ON ola_rides (Incomplete_Rides, Incomplete_Rides_Reason);
ANALYZE TABLE ola_rides;

-- Prove it: look for  type=ref/range  and  "Using index"  in the plan
-- EXPLAIN ANALYZE SELECT COUNT(*) FROM ola_rides WHERE Booking_Status = 'Canceled by Customer';
-- Optimization habits used below: no SELECT * on large scans (except Q1, which
-- the task requires), sargable filters (no functions on indexed columns),
-- aggregation pushed into SQL, deterministic ORDER BY tie-breakers.


/* =====================================================================
   PART 4 - THE 10 REQUIRED SQL QUESTIONS
   ===================================================================== */

-- >>> Q1 | Retrieve all successful bookings
-- Returns 63,967 rows. Booking_Status = 'Success' is the system of record.
SELECT *
FROM ola_rides
WHERE Booking_Status = 'Success'
ORDER BY Booking_DT;

-- >>> Q2 | Average ride distance for each vehicle type
-- Measured on COMPLETED rides: cancelled bookings carry distance = 0 and
-- would drag every average down. (All-bookings variant: Q2b.)
SELECT Vehicle_Type,
       COUNT(*)                       AS successful_rides,
       ROUND(AVG(Ride_Distance), 2)   AS avg_distance_km
FROM ola_rides
WHERE Booking_Status = 'Success'
GROUP BY Vehicle_Type
ORDER BY avg_distance_km DESC;

-- >>> Q2b | Average ride distance per vehicle type - all bookings (variant)
SELECT Vehicle_Type,
       COUNT(*)                       AS bookings,
       ROUND(AVG(Ride_Distance), 2)   AS avg_distance_km
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY avg_distance_km DESC;

-- >>> Q3 | Total number of cancelled rides by customers
SELECT COUNT(*) AS cancelled_by_customer
FROM ola_rides
WHERE Booking_Status = 'Canceled by Customer';

-- >>> Q4 | Top 5 customers with the highest number of rides
-- Many customers tie at 4 rides, so Customer_ID is the tie-breaker to keep
-- the result deterministic. (Tie-inclusive variant: Q4b.)
SELECT Customer_ID,
       COUNT(*) AS total_rides
FROM ola_rides
GROUP BY Customer_ID
ORDER BY total_rides DESC, Customer_ID
LIMIT 5;

-- >>> Q4b | Top customers including ties (first two rank levels)
WITH ranked AS (
  SELECT Customer_ID,
         COUNT(*) AS total_rides,
         DENSE_RANK() OVER (ORDER BY COUNT(*) DESC) AS rnk
  FROM ola_rides
  GROUP BY Customer_ID
)
SELECT Customer_ID, total_rides, rnk
FROM ranked
WHERE rnk <= 2
ORDER BY total_rides DESC, Customer_ID;

-- >>> Q5 | Rides cancelled by drivers for personal and car-related issues
SELECT COUNT(*) AS driver_cancel_personal_car_issue
FROM ola_rides
WHERE Canceled_Rides_by_Driver = 'Personal & Car related issue';

-- >>> Q6 | Maximum and minimum driver ratings for Prime Sedan bookings
-- MAX/MIN ignore NULLs, so unrated (cancelled) bookings are safely excluded.
SELECT MAX(Driver_Ratings) AS max_driver_rating,
       MIN(Driver_Ratings) AS min_driver_rating
FROM ola_rides
WHERE Vehicle_Type = 'Prime Sedan';

-- >>> Q7 | All rides where payment was made using UPI
SELECT Booking_ID, Customer_ID, Vehicle_Type, Pickup_Location, Drop_Location,
       Booking_Value, Payment_Method, Ride_Distance, Booking_DT
FROM ola_rides
WHERE Payment_Method = 'UPI'
ORDER BY Booking_DT;

-- >>> Q8 | Average customer rating per vehicle type
SELECT Vehicle_Type,
       COUNT(Customer_Rating)            AS rated_rides,
       ROUND(AVG(Customer_Rating), 2)    AS avg_customer_rating
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY avg_customer_rating DESC, Vehicle_Type;

-- >>> Q9 | Total booking value of rides completed successfully
SELECT COUNT(*)           AS successful_rides,
       SUM(Booking_Value) AS total_booking_value
FROM ola_rides
WHERE Booking_Status = 'Success';

-- >>> Q10 | All incomplete rides along with the reason
-- Incomplete = status Success, but the ride was not finished (flag = 'Yes').
SELECT Booking_ID, Customer_ID, Vehicle_Type, Pickup_Location, Drop_Location,
       Booking_Value, Incomplete_Rides_Reason AS reason, Booking_DT
FROM ola_rides
WHERE Incomplete_Rides = 'Yes'
ORDER BY reason, Booking_DT;

-- >>> Q10b | Incomplete rides summarised by reason
SELECT Incomplete_Rides_Reason AS reason,
       COUNT(*) AS incomplete_rides,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_incomplete
FROM ola_rides
WHERE Incomplete_Rides = 'Yes'
GROUP BY Incomplete_Rides_Reason
ORDER BY incomplete_rides DESC;


/* =====================================================================
   PART 5 - BONUS: INSIGHT QUERIES (feed the dashboard visuals)
   Joins / CTEs / window functions / conditional aggregation
   ===================================================================== */

-- >>> B1 | Daily ride trend: volume, outcomes and revenue
SELECT DATE(Booking_DT)                                   AS ride_date,
       COUNT(*)                                           AS bookings,
       SUM(Booking_Status = 'Success')                    AS successful,
       SUM(Booking_Status LIKE 'Canceled%')               AS cancelled,
       SUM(CASE WHEN Booking_Status = 'Success' THEN Booking_Value ELSE 0 END) AS revenue
FROM ola_rides
GROUP BY DATE(Booking_DT)
ORDER BY ride_date;

-- >>> B2 | Hourly demand and success rate
SELECT Hour_Of_Day                                        AS hr,
       COUNT(*)                                           AS bookings,
       ROUND(100.0 * AVG(Booking_Status = 'Success'), 1)    AS success_rate_pct
FROM ola_rides
GROUP BY Hour_Of_Day
ORDER BY hr;

-- >>> B3 | Weekday vs weekend performance
SELECT Weekday,
       COUNT(*)                                           AS bookings,
       ROUND(100.0 * AVG(Booking_Status = 'Success'), 1)    AS success_rate_pct,
       SUM(CASE WHEN Booking_Status = 'Success' THEN Booking_Value ELSE 0 END) AS revenue
FROM ola_rides
GROUP BY Weekday
ORDER BY bookings DESC;

-- >>> B4 | Cancellation reasons with share of all cancellations
SELECT Cancel_By,
       Cancel_Reason,
       COUNT(*)                                           AS cancellations,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct_of_cancellations
FROM ola_rides
WHERE Cancel_Reason IS NOT NULL
GROUP BY Cancel_By, Cancel_Reason
ORDER BY cancellations DESC;

-- >>> B5 | Vehicle scorecard (CTE + RANK window)
WITH v AS (
  SELECT Vehicle_Type,
         COUNT(*)                                                         AS bookings,
         SUM(Booking_Status = 'Success')                                  AS successful,
         SUM(CASE WHEN Booking_Status = 'Success' THEN Booking_Value END) AS revenue,
         AVG(CASE WHEN Booking_Status = 'Success' THEN Ride_Distance END) AS avg_km,
         AVG(Driver_Ratings)                                              AS avg_driver_rating,
         AVG(Customer_Rating)                                             AS avg_customer_rating
  FROM ola_rides
  GROUP BY Vehicle_Type
)
SELECT Vehicle_Type, bookings, successful,
       ROUND(100.0 * successful / bookings, 1)   AS success_rate_pct,
       revenue,
       ROUND(revenue / successful, 0)          AS avg_fare,
       ROUND(avg_km, 1)                        AS avg_km,
       ROUND(avg_driver_rating, 2)             AS avg_driver_rating,
       ROUND(avg_customer_rating, 2)           AS avg_customer_rating,
       RANK() OVER (ORDER BY revenue DESC)     AS revenue_rank
FROM v
ORDER BY revenue_rank;

-- >>> B6 | Revenue by payment method
SELECT Payment_Method,
       COUNT(*)                                             AS rides,
       SUM(Booking_Value)                                   AS revenue,
       ROUND(100.0 * SUM(Booking_Value) / SUM(SUM(Booking_Value)) OVER (), 2) AS revenue_share_pct
FROM ola_rides
WHERE Payment_Method IS NOT NULL
GROUP BY Payment_Method
ORDER BY revenue DESC;

-- >>> B7 | Top 10 busiest routes (successful rides)
SELECT Pickup_Location, Drop_Location,
       COUNT(*)           AS rides,
       SUM(Booking_Value) AS revenue
FROM ola_rides
WHERE Booking_Status = 'Success'
GROUP BY Pickup_Location, Drop_Location
ORDER BY rides DESC, revenue DESC
LIMIT 10;

-- >>> B8 | Customer rating distribution (whole-star bands)
SELECT FLOOR(Customer_Rating) AS rating_bucket,
       COUNT(*)                          AS rides
FROM ola_rides
WHERE Customer_Rating IS NOT NULL
GROUP BY FLOOR(Customer_Rating)
ORDER BY rating_bucket;

-- >>> B9 | Cumulative revenue (running total window)
SELECT ride_date, daily_revenue,
       SUM(daily_revenue) OVER (ORDER BY ride_date) AS cumulative_revenue
FROM (
  SELECT DATE(Booking_DT) AS ride_date, SUM(Booking_Value) AS daily_revenue
  FROM ola_rides
  WHERE Booking_Status = 'Success'
  GROUP BY DATE(Booking_DT)
) d
ORDER BY ride_date;

-- >>> B10 | Revenue lost to cancellations and unfulfilled bookings
SELECT Booking_Status,
       COUNT(*)           AS bookings,
       SUM(Booking_Value) AS booking_value_lost
FROM ola_rides
WHERE Booking_Status <> 'Success'
GROUP BY Booking_Status
ORDER BY booking_value_lost DESC;


/* =====================================================================
   PART 6 - RECONCILIATION: validate SQL results against the dataset
   Each check compares a query result with an independent figure.
   ===================================================================== */
-- >>> R1 | Status buckets must add up to the table total (diff = 0)
SELECT (SELECT COUNT(*) FROM ola_rides) -
       (SELECT SUM(c) FROM (SELECT COUNT(*) AS c FROM ola_rides GROUP BY Booking_Status) s) AS diff;

-- >>> R2 | Q9 revenue must equal payment_summary.csv total (35,080,467)
SELECT SUM(Booking_Value) AS sql_total,
       35080467           AS payment_summary_total,
       SUM(Booking_Value) - 35080467 AS diff
FROM ola_rides
WHERE Booking_Status = 'Success';

-- >>> R3 | Q3 + Q5 pieces tie to Cancel_By / Cancel_Reason helper columns (both diffs 0)
SELECT (SELECT COUNT(*) FROM ola_rides WHERE Booking_Status = 'Canceled by Customer')
     - (SELECT COUNT(*) FROM ola_rides WHERE Cancel_By = 'Customer')                    AS diff_q3,
       (SELECT COUNT(*) FROM ola_rides WHERE Canceled_Rides_by_Driver = 'Personal & Car related issue')
     - (SELECT COUNT(*) FROM ola_rides WHERE Cancel_Reason = 'Personal & Car related issue') AS diff_q5;

-- >>> R4 | Q10 rows must equal the sum of its reasons (diff = 0)
SELECT (SELECT COUNT(*) FROM ola_rides WHERE Incomplete_Rides = 'Yes')
     - (SELECT COUNT(*) FROM ola_rides WHERE Incomplete_Rides_Reason IS NOT NULL) AS diff;

USE ola_ride_insights;

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT Booking_ID) AS unique_bookings
FROM ola_rides;

SELECT *
FROM ola_rides
LIMIT 10;

USE ola_ride_insights;

SELECT
    COUNT(*) AS total_bookings,
    SUM(Driver_Ratings IS NULL) AS missing_driver_ratings,
    SUM(Customer_Rating IS NULL) AS missing_customer_ratings,
    SUM(Payment_Method IS NULL) AS missing_payment_methods,
    SUM(`V_TAT` IS NULL) AS missing_vtat,
    SUM(`C_TAT` IS NULL) AS missing_ctat
FROM ola_rides;