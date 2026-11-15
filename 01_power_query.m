// =====================================================================
// OLA RIDE INSIGHTS - Power Query (M)   |  Query name: Fact_Rides
// Home > Transform data > New Source > Blank Query > Advanced Editor
// Paste this whole script. Pick ONE source (A = CSV, B = MySQL).
// =====================================================================
let
    // ---- A) CSV source (simplest; edit the path) ----------------------
    Source = Csv.Document(
        File.Contents("C:\Ola\ola_rides_clean.csv"),
        [Delimiter = ",", Columns = 27, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Renamed  = Table.RenameColumns(Promoted, {{"Hour", "Hour_Of_Day"}}),

    // ---- B) MySQL source (use instead of A; the table already has typed columns) ----
    // Source  = MySQL.Database("localhost:3306", "ola_ride_insights", [ReturnSingleDatabase = true]),
    // Renamed = Source{[Schema = "ola_ride_insights", Item = "ola_rides"]}[Data],

    // ---- 1. Data types ---------------------------------------------------
    Typed = Table.TransformColumnTypes(Renamed, {
        {"Booking_ID", type text}, {"Booking_Status", type text}, {"Customer_ID", type text},
        {"Vehicle_Type", type text}, {"Pickup_Location", type text}, {"Drop_Location", type text},
        {"V_TAT", type number}, {"C_TAT", type number},
        {"Canceled_Rides_by_Customer", type text}, {"Canceled_Rides_by_Driver", type text},
        {"Incomplete_Rides", type text}, {"Incomplete_Rides_Reason", type text},
        {"Booking_Value", Int64.Type}, {"Payment_Method", type text}, {"Ride_Distance", Int64.Type},
        {"Driver_Ratings", type number}, {"Customer_Rating", type number},
        {"Booking_DT", type datetime}, {"Hour_Of_Day", Int64.Type},
        {"Weekday", type text}, {"Day_Part", type text},
        {"Is_Weekend", type logical}, {"Is_Success", type logical}, {"Is_Incomplete", type logical},
        {"Cancel_Reason", type text}, {"Cancel_By", type text}, {"Same_Pickup_Drop", type logical}
    }, "en-US"),

    // ---- 2. Clean text: trim + standardise labels ------------------------
    Trimmed = Table.TransformColumns(Typed, {
        {"Booking_Status", Text.Trim, type text}, {"Vehicle_Type", Text.Trim, type text},
        {"Payment_Method", each if _ = null then null else Text.Trim(_), type text}}),

    // ---- 3. Missing values: label the "not applicable" dimension --------
    //  (ratings / distances stay null so averages are never diluted by zeros)
    FillPay = Table.ReplaceValue(Trimmed, null, "Not Applicable", Replacer.ReplaceValue, {"Payment_Method"}),

    // ---- 4. Feature engineering -----------------------------------------
    AddDate = Table.AddColumn(FillPay, "Booking_Date", each Date.From([Booking_DT]), type date),

    AddDistBand = Table.AddColumn(AddDate, "Distance_Band", each
        if [Ride_Distance] = 0 then "0 (no ride)"
        else if [Ride_Distance] <= 10 then "01-10 km"
        else if [Ride_Distance] <= 20 then "11-20 km"
        else if [Ride_Distance] <= 30 then "21-30 km"
        else if [Ride_Distance] <= 40 then "31-40 km"
        else "41-50 km", type text),

    AddDriverBand = Table.AddColumn(AddDistBand, "Driver_Rating_Band", each
        if [Driver_Ratings] = null then null else Number.RoundDown([Driver_Ratings] * 2) / 2, type number),

    AddCustBand = Table.AddColumn(AddDriverBand, "Customer_Rating_Band", each
        if [Customer_Rating] = null then null else Number.RoundDown([Customer_Rating] * 2) / 2, type number),

    // ---- 5. Quality gate: drop exact duplicate bookings ------------------
    Result = Table.Distinct(AddCustBand, {"Booking_ID"})
in
    Result
