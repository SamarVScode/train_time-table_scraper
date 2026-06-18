# API Documentation

This document describes the API endpoints provided by the backend application to interact with train data, train searching, and train ticket availability.

All requests should be made relative to the base URL of the API.

## 1. Get Train Schedule / Route Data

Retrieves detailed schedule and route information for a given train number.

**Endpoint:** `GET /api/train/<train_number>`

**Description:**
Fetches the route details, schedule, and train information. The application first attempts to retrieve the data from the Supabase database cache. If not found, it scrapes the data from IndiaRailInfo and saves it to the database for future requests.

**Path Parameters:**
*   `train_number` (string, required): A 5-digit train number (e.g., `12345`).

**Sample Request:**
```http
GET /api/train/12951
```

**Sample Success Response (200 OK):**
```json
{
  "success": true,
  "train_number": "12951",
  "train_name": "Mumbai Central - New Delhi Tejas Rajdhani Express",
  "total_stations": 7,
  "source": "Mumbai Central",
  "destination": "New Delhi",
  "cached": true,
  "route": [
    {
      "stop": 1,
      "code": "MMCT",
      "name": "Mumbai Central",
      "arrival": "-",
      "departure": "17:00",
      "halt_time": "-",
      "platform": "1",
      "day": "1",
      "distance_covered": "0 km",
      "quota": "GN",
      "leg_from": "Origin",
      "next_segment": {
        "intermediate_stops": 0,
        "travel_time": "00:42",
        "distance_covered": "29 km"
      }
    },
    {
      "stop": 2,
      "code": "BVI",
      "name": "Borivali",
      "arrival": "17:42",
      "departure": "17:45",
      "halt_time": "3m",
      "platform": "6",
      "day": "1",
      "distance_covered": "29 km",
      "quota": "RL",
      "leg_from": "Borivali"
    }
  ]
}
```

**Sample Error Response (400 Bad Request):**
```json
{
  "success": false,
  "error": "Invalid train number. Must be exactly 5 digits.",
  "example": "12345"
}
```


## 2. Search Trains Between Stations

Finds all trains that operate between a given origin station and destination station.

**Endpoint:** `GET /api/search-train`

**Description:**
Queries the database for trains that pass through the specified origin and destination stations, ensuring that the origin station precedes the destination station in the train's route.

**Query Parameters:**
*   `from` (string, required): The station code of the origin station (e.g., `MMCT`).
*   `to` (string, required): The station code of the destination station (e.g., `NDLS`).

**Sample Request:**
```http
GET /api/search-train?from=MMCT&to=NDLS
```

**Sample Success Response (200 OK):**
```json
{
  "success": true,
  "trains": [
    {
      "train_number": "12951",
      "train_name": "Mumbai Central - New Delhi Tejas Rajdhani Express",
      "departure_time": "17:00"
    },
    {
      "train_number": "12953",
      "train_name": "August Kranti Tejas Rajdhani Express",
      "departure_time": "17:10"
    }
  ]
}
```

**Sample Error Response (400 Bad Request):**
```json
{
  "success": false,
  "error": "Missing required query parameters: from, to"
}
```


## 3. Check Seat Availability

Retrieves train seat availability information for a specific train on a given date.

**Endpoint:** `GET /api/availability`

**Description:**
Fetches seat availability using the ConfirmTkt API integration for a specified train, class, and quota.

**Query Parameters:**
*   `train_no` (string, required): The 5-digit train number (e.g., `12951`).
*   `from` (string, required): Origin station code (e.g., `MMCT`).
*   `to` (string, required): Destination station code (e.g., `NDLS`).
*   `date` (string, required): Date of journey (Expected format is typically DD-MM-YYYY or YYYY-MM-DD depending on ConfirmTkt expectations).
*   `class` (string, optional): Travel class code. Defaults to `SL` (Sleeper). Examples: `1A`, `2A`, `3A`, `SL`, `CC`.
*   `quota` (string, optional): Travel quota code. Defaults to `GN` (General). Examples: `GN`, `TQ`, `PT`.

**Sample Request:**
```http
GET /api/availability?train_no=12951&from=MMCT&to=NDLS&date=20-12-2023&class=3A&quota=GN
```

**Sample Success Response (200 OK):**
```json
{
  "success": true,
  "train_number": "12951",
  "from_station": "MMCT",
  "to_station": "NDLS",
  "quota": "GN",
  "travel_class": "3A",
  "availability": [
    {
      "date": "20-12-2023",
      "status": "AVAILABLE-0150",
      "prediction": "Available",
      "fare": "2450"
    },
    {
      "date": "21-12-2023",
      "status": "WL10/WL5",
      "prediction": "High Chances",
      "fare": "2450"
    }
  ]
}
```

**Sample Error Response (400 Bad Request):**
```json
{
  "success": false,
  "error": "Missing required query parameters: train_no, from, to, date"
}
```
