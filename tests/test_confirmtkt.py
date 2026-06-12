import unittest
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from availability_scraper.parsers.confirmtkt import ConfirmTktParser

class TestConfirmTktParser(unittest.TestCase):
    def test_get_availability_success(self):
        result = ConfirmTktParser.get_availability(
            train_no="12002",
            from_stn="NDLS",
            to_stn="VGLB",
            date="25-06-2026",
            travel_class="CC",
            quota="GN"
        )
        print("\nTest Result:", result.to_dict())
        self.assertTrue(result.success, f"Scraper failed with error: {result.error}")
        self.assertEqual(result.train_number, "12002")
        self.assertEqual(result.from_station, "NDLS")
        self.assertEqual(result.to_station, "VGLB")
        self.assertTrue(len(result.availability) > 0, "Availability list is empty")
        
        # Check details of first availability item
        first = result.availability[0]
        self.assertIsNotNone(first.date)
        self.assertIsNotNone(first.status)
        self.assertIsNotNone(first.fare)

if __name__ == "__main__":
    unittest.main()
