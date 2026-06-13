import json
# ConfirmTkt parser module for seat availability scraper
try:
    from ..core.network import NetworkClient
    from ..models.schema import AvailabilityResponse, AvailabilityStatus
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.network import NetworkClient
    from models.schema import AvailabilityResponse, AvailabilityStatus

class ConfirmTktParser:
    @staticmethod
    def generate_search_url(from_stn, to_stn, date):
        # Expected date format: DD-MM-YYYY
        return f"https://www.confirmtkt.com/rbooking/trains/from/{from_stn}/to/{to_stn}/{date}"

    @staticmethod
    def get_availability(train_no, from_stn, to_stn, date, travel_class, quota):
        # Format date for ConfirmTkt (usually DD-MM-YYYY or YYYY-MM-DD)
        formatted_date = date # In a real app, we'd validate/convert this
        
        url = "https://cttrainsapi.confirmtkt.com/api/v1/availability/fetchAvailability"
        params = {
            "trainNo": train_no,
            "travelClass": travel_class,
            "quota": quota,
            "sourceStationCode": from_stn,
            "destinationStationCode": to_stn,
            "dateOfJourney": formatted_date,
            "enableTG": "false",
            "tGPlan": "",
            "showTGPrediction": "false",
            "tgColor": "DEFAULT",
            "showPredictionGlobal": "true",
            "showNewMealOptions": "true",
            "showNewAlternates": "false",
            "showNewAltText": "true"
        }
        
        try:
            content = NetworkClient.post(url, params=params)
            data = json.loads(content)
            
            if not data or "data" not in data or "avlDayList" not in data["data"]:
                return AvailabilityResponse(
                    success=False, train_number=train_no, from_station=from_stn,
                    to_station=to_stn, quota=quota, travel_class=travel_class,
                    availability=[], error="Invalid response from source"
                )
            
            fare = str(data["data"].get("fareInfo", {}).get("totalFare", ""))
            avail_list = []
            for item in data["data"].get("avlDayList", []):
                avail_list.append(AvailabilityStatus(
                    date=item.get("availablityDate"),
                    status=item.get("availablityStatus"),
                    prediction=item.get("prediction"),
                    fare=fare
                ))
                
            return AvailabilityResponse(
                success=True, train_number=train_no, from_station=from_stn,
                to_station=to_stn, quota=quota, travel_class=travel_class,
                availability=avail_list
            )
            
        except Exception as e:
            return AvailabilityResponse(
                success=False, train_number=train_no, from_station=from_stn,
                to_station=to_stn, quota=quota, travel_class=travel_class,
                availability=[], error=str(e)
            )
